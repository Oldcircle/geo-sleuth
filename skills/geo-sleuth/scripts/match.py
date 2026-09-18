#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy", "torch", "transformers", "opencv-python-headless", "socksio", "pysocks", "requests"]
# ///
"""照片 vs 一批候选实景图（街景渲染图、卫星缩略图、参考图）的相似度排名：机器先排，人只看前几名。

用途：
- 街景确认：候选全景点几十上百个，先按相似度排序，只打开前 10 名比不变特征。
- 卫星缩略图：候选点的俯视图和照片里能看到的俯视特征比（效果弱于街景，只当粗排）。
- 参考图库：公交涂装、路灯样式等参考图和照片裁剪块比。

  rank    对候选打分排名，输出 ranked.json + 前 N 名拼图
  index   一批图片的嵌入向量落盘（同城反复用）

候选来源三选一：
  --images <目录或glob>                          现成图片，文件名当 id
  --items <.index.json> --render baidu|gsv      baidu_pano.py sheet/sample 或 gsv.py sheet 写出的 index，逐项渲染
  --panos panos.json --toward lat,lon | --headings 0,60,…   baidu_pano.py scan 的输出，按朝向渲染（可加 --within、--spread）

打分：
  全局描述子 DINOv2（facebook/dinov2-small，CLS+patch均值）或 CLIP（openai/clip-vit-base-patch32）余弦相似度；
  --refine sift 对前 --refine-top 名做 SIFT + RANSAC 内点数精排（内点 ≥ 15 才算有几何一致性）。
  最终排序：有内点的按内点数，其余按全局分。分数只是排序依据，是否同一地点仍要人比 ≥3 项不变特征。

模型第一次用会从 HuggingFace 下载（走 --proxy / GEO_PROXY），缓存在 ~/.cache/huggingface。

示例：
  match.py rank --query photo.jpg --panos panos.json --toward <lat,lon> --spread 15 --refine sift --top 10 --out ranked.json --sheet ranked.jpg
  match.py rank --query photo.jpg --query-box 200,100,900,700 --items around.index.json --render baidu --spread-headings -30,0,30 --out r.json --sheet r.jpg
  match.py rank --query photo.jpg --images cands/ --method clip --out r.json
  match.py index --images city_panos/ --out city.npz
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

MODELS = {"dino": "facebook/dinov2-small", "clip": "openai/clip-vit-base-patch32"}


def _proxy_env(proxy: str | None) -> None:
    if proxy:
        os.environ.setdefault("HTTPS_PROXY", proxy)
        os.environ.setdefault("HTTP_PROXY", proxy)


def _device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


IMNET = ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
CLIPN = ([0.48145466, 0.4578275, 0.40821073], [0.26862954, 0.26130258, 0.27577711])


def _tensor(ims: list[Image.Image], norm: tuple, torch):
    """PIL 224×224 → (N,3,224,224) 归一化张量。自己做预处理，不依赖 torchvision。"""
    mean, std = (np.array(v, dtype=np.float32).reshape(1, 3, 1, 1) for v in norm)
    arr = np.stack([np.asarray(im.convert("RGB"), dtype=np.float32) / 255.0 for im in ims]).transpose(0, 3, 1, 2)
    return torch.from_numpy((arr - mean) / std)


def _feat(out):
    """transformers 5 的 get_*_features 返回 BaseModelOutputWithPooling，投影后的向量在 pooler_output；老版本直接返回张量。"""
    if hasattr(out, "shape"):
        return out
    for k in ("pooler_output", "text_embeds", "image_embeds"):
        v = getattr(out, k, None)
        if v is not None and hasattr(v, "shape"):
            return v
    return out[0]


class Embedder:
    """全局描述子。dino：DINOv2 CLS + patch 均值；clip：图像塔嵌入。"""

    def __init__(self, method: str):
        import torch
        from transformers import AutoModel, CLIPModel
        self.method = method
        self.dev = _device()
        t0 = time.time()
        try:
            self.model = (CLIPModel if method == "clip" else AutoModel).from_pretrained(MODELS[method]).to(self.dev).eval()
        except Exception as e:  # noqa: BLE001
            sys.exit(f"模型 {MODELS[method]} 加载失败：{str(e)[:300]}\n"
                     f"国内下载要代理：--proxy socks5h://127.0.0.1:10808（示例）（或 export GEO_PROXY）；"
                     f"也可以 export HF_ENDPOINT=https://hf-mirror.com 直连镜像。")
        self.torch = torch
        print(f"模型 {MODELS[method]} 就绪（{self.dev}，{time.time() - t0:.1f}s）", file=sys.stderr)

    def _views(self, im: Image.Image, multi: bool) -> list[Image.Image]:
        im = im.convert("RGB")
        vs = [im.resize((224, 224), Image.BICUBIC)]
        if multi:
            w, h = im.size
            s = min(w, h)
            vs.append(im.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2)).resize((224, 224), Image.BICUBIC))
            # 左右两半：街景和照片视角错开时，重叠的那一半更像
            vs.append(im.crop((0, 0, int(w * 0.6), h)).resize((224, 224), Image.BICUBIC))
            vs.append(im.crop((int(w * 0.4), 0, w, h)).resize((224, 224), Image.BICUBIC))
        return vs

    def embed(self, ims: list[Image.Image], multi: bool = False, batch: int = 32) -> np.ndarray:
        """返回 (N, V, D)：每张图 V 个视图的归一化向量。"""
        views = [self._views(im, multi) for im in ims]
        flat = [v for vs in views for v in vs]
        out = []
        with self.torch.no_grad():
            for i in range(0, len(flat), batch):
                chunk = flat[i:i + batch]
                if self.method == "clip":
                    x = _tensor(chunk, CLIPN, self.torch).to(self.dev)
                    f = _feat(self.model.get_image_features(pixel_values=x))
                else:
                    x = _tensor(chunk, IMNET, self.torch).to(self.dev)
                    h = self.model(pixel_values=x).last_hidden_state
                    f = self.torch.cat([h[:, 0], h[:, 1:].mean(1)], dim=1)
                f = f / f.norm(dim=1, keepdim=True)
                out.append(f.float().cpu().numpy())
        arr = np.concatenate(out, 0)
        nv = len(views[0]) if views else 1
        return arr.reshape(len(ims), nv, -1)


def sift_inliers(a: Image.Image, b: Image.Image, max_side: int = 1024) -> tuple[int, int]:
    """SIFT + 比率检验 + RANSAC 单应矩阵的内点数（和匹配数）。"""
    import cv2

    def prep(im):
        im = im.convert("L")
        s = max_side / max(im.size)
        if s < 1:
            im = im.resize((int(im.width * s), int(im.height * s)), Image.BICUBIC)
        return np.array(im)

    sift = cv2.SIFT_create(nfeatures=3000)
    ka, da = sift.detectAndCompute(prep(a), None)
    kb, db = sift.detectAndCompute(prep(b), None)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8:
        return 0, 0
    m = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [x[0] for x in m if len(x) == 2 and x[0].distance < 0.75 * x[1].distance]
    if len(good) < 8:
        return 0, len(good)
    pa = np.float32([ka[g.queryIdx].pt for g in good])
    pb = np.float32([kb[g.trainIdx].pt for g in good])
    _, mask = cv2.findHomography(pa, pb, cv2.RANSAC, 6.0)
    return (int(mask.sum()) if mask is not None else 0), len(good)


# ---------------------------------------------------------------- 候选来源

def _items_from_panos(args) -> list[dict]:
    import baidu_pano as bp
    panos = json.loads(Path(args.panos).read_text())
    if args.within:
        wl, wo, wr = (float(v) for v in args.within.split(","))
        panos = {k: v for k, v in panos.items() if geo.distance((wl, wo), tuple(v["wgs"])) <= wr}
    if args.spread:
        panos = bp.thin(panos, args.spread)
    target = tuple(float(v) for v in args.toward.split(",")) if args.toward else None
    items = []
    for pid, v in panos.items():
        heads = [float(x) for x in args.headings.split(",")] if args.headings else (
            [geo.bearing(tuple(v["wgs"]), target) + args.offset] if target else None)
        if heads is None:
            sys.exit("--panos 需要 --toward 或 --headings")
        for hd in heads:
            items.append({"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov, "wgs": v["wgs"],
                          "road": v.get("road", ""), "date": v.get("date", "")})
    return items


def _render_items(items: list[dict], engine: str, proxy: str | None, cache: Path) -> list[Image.Image | None]:
    if engine == "gsv":
        import gsv
        def one(it):
            try:
                return gsv.render(it["id"], it["heading"], it.get("pitch", 0), it.get("fov", 90), 640, 480, proxy, cache / "gsv")
            except Exception:  # noqa: BLE001
                return None
    else:
        import baidu_pano as bp
        def one(it):
            try:
                return bp.render(it["id"], it["heading"], it.get("pitch", 10), it.get("fov", 80), cache=cache / "pano")
            except Exception:  # noqa: BLE001
                return None
    with ThreadPoolExecutor(12) as ex:
        return list(ex.map(one, items))


def _load_candidates(args) -> tuple[list[dict], list[Image.Image]]:
    cache = Path(args.cache)
    if args.images:
        p = Path(args.images)
        files = sorted(p.glob("*.jp*g")) + sorted(p.glob("*.png")) if p.is_dir() else [Path(x) for x in sorted(glob.glob(args.images))]
        if not files:
            sys.exit(f"--images 没有图片：{args.images}")
        items = [{"id": f.stem, "file": str(f)} for f in files]
        return items, [Image.open(f) for f in files]
    if args.items:
        items = json.loads(Path(args.items).read_text())
        if args.spread_headings:
            ds = [float(x) for x in args.spread_headings.split(",")]
            items = [dict(it, heading=(it["heading"] + d) % 360) for it in items for d in ds]
    elif args.panos:
        items = _items_from_panos(args)
    else:
        sys.exit("候选来源：--images / --items / --panos 三选一")
    if len(items) > args.max_candidates:
        if args.toward and all(it.get("wgs") for it in items):
            tgt = tuple(float(v) for v in args.toward.split(","))
            items.sort(key=lambda it: geo.distance(tuple(it["wgs"]), tgt))
            how = "按离 --toward 目标由近到远取"
        else:
            how = "只取前"
        print(f"候选 {len(items)} 张，超过 --max-candidates {args.max_candidates}，{how} {args.max_candidates} 张（先用 --within/--spread 缩）", file=sys.stderr)
        items = items[: args.max_candidates]
    engine = args.render or ("gsv" if items and str(items[0].get("id", "")).startswith(("CAoS", "CIHM")) or len(str(items[0].get("id", ""))) == 22 else "baidu")
    ims = _render_items(items, engine, args.proxy, cache)
    ok_items, ok_ims = [], []
    for it, im in zip(items, ims):
        if im is not None:
            ok_items.append(it)
            ok_ims.append(im)
    if not ok_ims:
        sys.exit("一张候选都没渲染出来：百度全景要直连，Google 街景要代理；看 id 是否正确")
    if len(ok_ims) < len(items):
        print(f"{len(items) - len(ok_ims)} 张渲染失败已跳过", file=sys.stderr)
    return ok_items, ok_ims


def _sheet(rows: list[dict], ims: dict, out: Path, cols: int = 3, tw: int = 480, th: int = 360) -> None:
    from baidu_pano import _font
    n = len(rows)
    S = Image.new("RGB", (cols * tw, max(1, (n + cols - 1) // cols) * th), "black")
    d = ImageDraw.Draw(S)
    f = _font(16)
    for i, r in enumerate(rows):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(ims[r["id_key"]].convert("RGB").resize((tw, th)), (x, y))
        t = f"#{r['rank']} 内点{r['inliers'] if r['inliers'] is not None else '-'} 全局{r['score_global']:.3f} …{str(r['id'])[-9:]}"
        if r.get("heading") is not None:
            t += f" h{r['heading']:.0f}"
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        d.text((x + 4, y + 2), t, fill="yellow", font=f)
    S.save(out, quality=88)


def cmd_rank(args) -> None:
    _proxy_env(args.proxy)
    q = Image.open(args.query)
    if args.query_box:
        x0, y0, x1, y1 = (int(float(v)) for v in args.query_box.split(","))
        q = q.crop((x0, y0, x1, y1))
    items, ims = _load_candidates(args)
    t0 = time.time()
    methods = ["dino", "clip"] if args.method == "both" else [args.method]
    sims = np.zeros(len(ims))
    for m in methods:
        emb = Embedder(m)
        qf = emb.embed([q], multi=True)[0]              # (V, D)
        cf = emb.embed(ims, multi=False)[:, 0]          # (N, D)
        s = (cf @ qf.T).max(axis=1)                     # 每个候选取查询各视图的最大相似度
        sims += s / len(methods)
    order = np.argsort(-sims)
    rows = []
    for rk, i in enumerate(order):
        it = items[i]
        rows.append({"rank": rk + 1, "id": it.get("id"), "id_key": i, "file": it.get("file"), "score_global": round(float(sims[i]), 4),
                     "inliers": None, "matches": None, "heading": it.get("heading"), "wgs": it.get("wgs"),
                     "road": it.get("road", ""), "date": it.get("date", ""), "label": it.get("label", "")})
    t1 = time.time()
    if args.refine != "none":
        top = rows[: args.refine_top]
        def one(r):
            return sift_inliers(q, ims[r["id_key"]])
        with ThreadPoolExecutor(4) as ex:
            for r, (inl, mt) in zip(top, ex.map(one, top)):
                r["inliers"], r["matches"] = inl, mt
        rows.sort(key=lambda r: (-(r["inliers"] or 0) if (r["inliers"] or 0) >= args.min_inliers else 0, -r["score_global"]))
        for k, r in enumerate(rows):
            r["rank"] = k + 1
    t2 = time.time()
    out_rows = rows[: args.top]
    print(f"候选 {len(ims)} 张；全局打分 {t1 - t0:.1f}s，精排 {t2 - t1:.1f}s")
    print(f"{'#':>3} {'内点':>5} {'全局':>7}  id / 朝向 / 位置")
    for r in out_rows:
        pos = f"{r['wgs'][0]:.5f},{r['wgs'][1]:.5f}" if r.get("wgs") else (r.get("file") or "")
        print(f"{r['rank']:>3} {(r['inliers'] if r['inliers'] is not None else '-'):>5} {r['score_global']:>7.3f}  …{str(r['id'])[-10:]}"
              f" h{r['heading']:.0f} {pos} {r.get('road', '')}" if r.get("heading") is not None else
              f"{r['rank']:>3} {(r['inliers'] if r['inliers'] is not None else '-'):>5} {r['score_global']:>7.3f}  {r['id']} {pos}")
    strong = [r for r in out_rows if (r["inliers"] or 0) >= args.min_inliers]
    if args.refine != "none":
        print(f"内点 ≥{args.min_inliers} 的有 {len(strong)} 张" + ("：优先打开这些比不变特征" if strong else "：不能据此判定都不对——换季、老批次、照片在人行道而街景在路中间时，真值也常只有个位数内点。先打开 --sheet 前 10 张比不变特征，都不对再换朝向（--spread-headings）或扩大范围"))
    if args.out:
        Path(args.out).write_text(json.dumps([{k: v for k, v in r.items() if k != "id_key"} for r in rows], ensure_ascii=False, indent=1))
        print(f"-> {args.out}（全部 {len(rows)} 条）")
    if args.sheet:
        _sheet(out_rows, {r["id_key"]: ims[r["id_key"]] for r in out_rows}, Path(args.sheet))
        print(f"-> {args.sheet}")


def cmd_index(args) -> None:
    _proxy_env(args.proxy)
    p = Path(args.images)
    files = sorted(p.glob("*.jp*g")) + sorted(p.glob("*.png")) if p.is_dir() else [Path(x) for x in sorted(glob.glob(args.images))]
    emb = Embedder(args.method)
    feats = emb.embed([Image.open(f) for f in files], multi=False)[:, 0]
    np.savez(args.out, ids=np.array([f.stem for f in files]), files=np.array([str(f) for f in files]), feats=feats, method=args.method)
    print(f"{len(files)} 张 -> {args.out}")


def _neg_coords(argv: list[str]) -> list[str]:
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("rank")
    r.add_argument("--query", required=True)
    r.add_argument("--query-box", help="x0,y0,x1,y1 只比这一块")
    r.add_argument("--images")
    r.add_argument("--items", help="baidu_pano.py / gsv.py 的 .index.json")
    r.add_argument("--render", choices=["baidu", "gsv"], help="--items 用哪个引擎渲染；不给按 id 形状猜")
    r.add_argument("--spread-headings", help="--items 每项额外朝向偏移，如 -30,0,30")
    r.add_argument("--panos", help="baidu_pano.py scan 的输出")
    r.add_argument("--toward", help="lat,lon")
    r.add_argument("--headings")
    r.add_argument("--offset", type=float, default=0)
    r.add_argument("--within", help="lat,lon,半径米")
    r.add_argument("--spread", type=float, help="抽稀间距米")
    r.add_argument("--pitch", type=float, default=10)
    r.add_argument("--fov", type=float, default=80)
    r.add_argument("--max-candidates", type=int, default=400)
    r.add_argument("--method", choices=["dino", "clip", "both"], default="dino")
    r.add_argument("--refine", choices=["none", "sift"], default="sift")
    r.add_argument("--refine-top", type=int, default=30)
    r.add_argument("--min-inliers", type=int, default=15)
    r.add_argument("--top", type=int, default=10)
    r.add_argument("--out")
    r.add_argument("--sheet")
    r.add_argument("--proxy", default=argparse.SUPPRESS)
    r.add_argument("--cache", type=Path, default=argparse.SUPPRESS)

    i = sub.add_parser("index")
    i.add_argument("--images", required=True)
    i.add_argument("--method", choices=["dino", "clip"], default="dino")
    i.add_argument("--out", required=True)
    i.add_argument("--proxy", default=argparse.SUPPRESS)

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "rank":
        cmd_rank(args)
    else:
        cmd_index(args)


if __name__ == "__main__":
    main()
