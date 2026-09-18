#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow"]
# ///
"""看图和搜图前的图片处理。

  zoom      裁一块放大锐化，读小字、数轨道、看车牌底色
  edges     四条边缘和四个角各出一张放大图——角落的缆绳、底部船头、小路牌最容易漏
  variants  以图搜图用的变体：紧裁 / 水平翻转 / 灰度增强 / 去色偏 / 放大；可选透视拉正
  grid      切成 N×M 块，给以图搜图"只搜局部"用
  piers     沿桥面下方几行取亮度剖面，找出桥墩所在的像素列（给反解机位用）

坐标一律是原图像素 x0,y0,x1,y1（左上、右下）。先用 `exif.py` 或 PIL 看原图尺寸。

示例：
  imgprep.py zoom photo.jpg --box 820,40,1080,300 --scale 4 --out sign.png
  imgprep.py edges photo.jpg --out-dir edges/
  imgprep.py variants photo.jpg --box 300,120,900,760 --prefix left --out-dir v/     # → v/left_crop.jpg left_flip.jpg …
  imgprep.py variants photo.jpg --persp 312,140,880,95,905,770,290,720 --out-dir v/   # 四角（左上 右上 右下 左下）拉正
  imgprep.py grid photo.jpg --rows 2 --cols 3 --out-dir tiles/
  imgprep.py piers photo.jpg --rows 926:940 --out cols.json --sheet piers.jpg

piers 的输出 JSON：
  {"image": 路径, "size": [W, H], "rows": [r0, r1], "cols": [x0, x1],
   "polarity": "bright" | "dark",            # 桥墩比周围亮还是暗
   "params": {"min_gap": 20, "min_prominence": 12, "baseline": 61},
   "count": 峰数,
   "piers": [{"col": 38, "prominence": 100.5, "dev": 92.4, "level": 183.2}, ...]}
  col 是像素列（整数，原图坐标），prominence 是该峰的地形突起度（判断真假的主要依据），
  dev 是去基线后的高度，level 是该列在 rows 区间内的原始平均亮度。piers 按 col 升序。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, ImageStat


def _box(s: str) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = (int(float(v)) for v in s.split(","))
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def zoom(im: Image.Image, box, scale: float) -> Image.Image:
    c = im.crop(box)
    c = c.resize((max(1, int(c.width * scale)), max(1, int(c.height * scale))), Image.LANCZOS)
    return c.filter(ImageFilter.UnsharpMask(radius=2, percent=120, threshold=2))


def gray_world(im: Image.Image) -> Image.Image:
    """灰世界白平衡：老照片偏黄偏紫时用。"""
    r, g, b = ImageStat.Stat(im.convert("RGB")).mean
    avg = (r + g + b) / 3
    chans = [ch.point(lambda v, k=avg / max(m, 1): max(0, min(255, int(v * k))))
             for ch, m in zip(im.convert("RGB").split(), (r, g, b))]
    return ImageOps.autocontrast(Image.merge("RGB", chans), cutoff=1)


def perspective(im: Image.Image, quad: list[float]) -> Image.Image:
    """四角（左上 右上 右下 左下）→ 矩形。输出宽高取对边长度的最大值。"""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = (quad[i:i + 2] for i in range(0, 8, 2))
    w = int(max(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** .5, ((x2 - x3) ** 2 + (y2 - y3) ** 2) ** .5))
    h = int(max(((x3 - x0) ** 2 + (y3 - y0) ** 2) ** .5, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** .5))
    # PIL 的 QUAD 变换：输出矩形的四角依次取自源图的 左上、左下、右下、右上
    return im.transform((w, h), Image.QUAD, (x0, y0, x3, y3, x2, y2, x1, y1), Image.BICUBIC)


def _range(s: str) -> tuple[int, int]:
    """解析 "a:b"（含 a、不含 b）。"""
    a, b = s.split(":")
    a, b = int(float(a)), int(float(b))
    return (a, b) if a <= b else (b, a)


def _baseline(p, w: int):
    """滑动中值基线：把桥体、天空、地面这类缓变亮度抹平，只留下细的竖条。"""
    import numpy as np
    h = w // 2
    pad = np.pad(p, (h, h), mode="edge")
    return np.array([float(np.median(pad[i:i + w])) for i in range(len(p))])


def _prominence(d, i: int) -> float:
    """局部极大值 i 的地形突起度：峰高减去左右两侧下降到的较高那个谷底。"""
    h = d[i]
    lo = h
    j = i
    while j > 0 and d[j - 1] <= h:
        j -= 1
        lo = min(lo, d[j])
    left = lo
    lo = h
    j = i
    while j < len(d) - 1 and d[j + 1] <= h:
        j += 1
        lo = min(lo, d[j])
    return float(h - max(left, lo))


def _peaks(d, min_gap: int, min_prominence: float) -> list[tuple[int, float]]:
    """找 d 上的峰：突起度先过阈值，再按突起度从大到小贪心地留下相距 ≥ min_gap 的。"""
    cand = [i for i in range(1, len(d) - 1) if d[i] >= d[i - 1] and d[i] > d[i + 1]]
    res = [(i, _prominence(d, i)) for i in cand]
    res = [(i, pr) for i, pr in res if pr >= min_prominence]
    res.sort(key=lambda t: -t[1])
    keep: list[tuple[int, float]] = []
    for i, pr in res:
        if all(abs(i - j) >= min_gap for j, _ in keep):
            keep.append((i, pr))
    keep.sort()
    return keep


def piers(im: Image.Image, rows: tuple[int, int], cols: tuple[int, int] | None,
          min_gap: int, min_prominence: float, baseline_win: int, polarity: str) -> dict:
    """沿桥面下方的 rows 行取每列平均亮度 → 减滑动中值基线 → 找峰 = 桥墩像素列。

    桥墩在背光的桥体阴影里通常比周围亮（polarity=bright），逆光或阴天可能反过来（dark）；
    auto 就是两种都算一遍，取突起度总和大的那一种。
    """
    import numpy as np
    W, H = im.size
    r0, r1 = max(0, rows[0]), min(H, rows[1])
    if r1 - r0 < 1:
        raise SystemExit(f"--rows {rows[0]}:{rows[1]} 在 {W}x{H} 的图上取不到行")
    x0, x1 = (0, W) if cols is None else (max(0, cols[0]), min(W, cols[1]))
    a = np.asarray(im.convert("L"), dtype=float)
    p = a[r0:r1, x0:x1].mean(axis=0)
    base = _baseline(p, max(3, baseline_win | 1))
    dev = p - base
    opts = {"bright": _peaks(dev, min_gap, min_prominence),
            "dark": _peaks(-dev, min_gap, min_prominence)} if polarity == "auto" \
        else {polarity: _peaks(dev if polarity == "bright" else -dev, min_gap, min_prominence)}
    pol = max(opts, key=lambda k: sum(pr for _, pr in opts[k]))
    sign = 1.0 if pol == "bright" else -1.0
    found = [{"col": int(i + x0), "prominence": round(pr, 2),
              "dev": round(float(dev[i]) * sign, 2), "level": round(float(p[i]), 2)}
             for i, pr in opts[pol]]
    return {"size": [W, H], "rows": [r0, r1], "cols": [x0, x1], "polarity": pol,
            "params": {"min_gap": min_gap, "min_prominence": min_prominence, "baseline": baseline_win},
            "count": len(found), "piers": found}


def piers_sheet(im: Image.Image, r: dict, out: Path) -> None:
    """在原图上画出取样行带和每个桥墩列（带序号），给人一眼核对多没多、漏没漏。"""
    from PIL import ImageDraw
    sheet = im.copy()
    d = ImageDraw.Draw(sheet)
    r0, r1 = r["rows"]
    x0, x1 = r["cols"]
    d.rectangle([x0, r0, x1 - 1, r1 - 1], outline=(0, 200, 255), width=1)
    for n, pier in enumerate(r["piers"]):
        x = pier["col"]
        d.line([(x, max(0, r0 - 60)), (x, min(sheet.height, r1 + 60))], fill=(255, 0, 0), width=1)
        d.text((x + 2, max(0, r0 - 72)), str(n), fill=(255, 255, 0))
    sheet.save(out, quality=92)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    z = sub.add_parser("zoom")
    z.add_argument("image", type=Path)
    z.add_argument("--box", type=_box, required=True)
    z.add_argument("--scale", type=float, default=3)
    z.add_argument("--out", type=Path, required=True)

    e = sub.add_parser("edges")
    e.add_argument("image", type=Path)
    e.add_argument("--frac", type=float, default=0.18, help="边缘条带占整图的比例，默认 0.18")
    e.add_argument("--out-dir", type=Path, required=True)

    v = sub.add_parser("variants")
    v.add_argument("image", type=Path)
    v.add_argument("--box", type=_box, help="只搜这一块（去掉天空和背景）")
    v.add_argument("--persp", help="8 个数：左上 右上 右下 左下 四角，拉成正视")
    v.add_argument("--prefix", help="输出文件名前缀；默认 原图名 + 裁剪框，不同框的变体不会互相覆盖")
    v.add_argument("--out-dir", type=Path, required=True)

    g = sub.add_parser("grid")
    g.add_argument("image", type=Path)
    g.add_argument("--rows", type=int, default=2)
    g.add_argument("--cols", type=int, default=2)
    g.add_argument("--overlap", type=float, default=0.15)
    g.add_argument("--out-dir", type=Path, required=True)

    pr = sub.add_parser("piers", help="沿桥面下方几行的亮度剖面找桥墩像素列",
                        formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
沿 --rows 那几行取亮度剖面，减去滑动中值基线，找出突起度 ≥ --min-prominence 的峰，峰所在的像素列就是桥墩列。
取样行选桥面下方、桥墩露出来且背景（天空、远景、水面）连续的那几行；桥面在画面里倾斜时把行带放宽到覆盖两端。

输出 JSON（--out）：
  {"image": 路径, "size": [W, H], "rows": [r0, r1], "cols": [x0, x1],   # cols 是列的搜索范围，不是构件列
   "polarity": "bright" | "dark",            # 桥墩比周围亮还是暗
   "params": {"min_gap": 20, "min_prominence": 12, "baseline": 61},
   "count": 峰数,
   "piers": [{"col": 38, "prominence": 100.5, "dev": 92.4, "level": 183.2}, ...]}
  col 是像素列（整数，原图坐标），prominence 是该峰的突起度（判断真假的主要依据），
  dev 是去基线后的高度，level 是该列在 rows 区间内的原始平均亮度。piers 按 col 升序。

这份 JSON 可以直接给 geo.py spacing --cols @cols.json，但**先看 --sheet 核对**：
剔掉非桥墩的峰（前景亮斑、栏杆、树），被前景挡断的构件分段之间要用 ';' 隔开手写成 --cols 串。""")
    pr.add_argument("image", type=Path)
    pr.add_argument("--rows", type=_range, required=True,
                    help='取样行，"r0:r1"（含 r0 不含 r1）。取桥面下方、桥墩露出来的那几行，'
                         '先用 zoom 看一眼；桥面倾斜时把行带放宽到覆盖两端')
    pr.add_argument("--cols", type=_range, help='只在这段列里找，"x0:x1"；默认整幅宽')
    pr.add_argument("--min-gap", type=int, default=20, help="两个桥墩列至少隔多少像素，默认 20")
    pr.add_argument("--min-prominence", type=float, default=12,
                    help="峰的突起度阈值（0-255 灰度），默认 12；调小多出假峰，调大会漏远端的密桥墩")
    pr.add_argument("--baseline", type=int, default=61,
                    help="滑动中值基线的窗口宽度，默认 61 像素；比桥墩间距大、比桥体亮度变化尺度小")
    pr.add_argument("--polarity", choices=["auto", "bright", "dark"], default="auto",
                    help="桥墩比周围亮还是暗，默认 auto（两种都试，取突起度总和大的）")
    pr.add_argument("--out", type=Path, required=True, help="输出 JSON，结构见 --help 顶部")
    pr.add_argument("--sheet", type=Path, help="在原图上画出行带和每个列（带序号），给人核对")

    args = ap.parse_args()
    im = ImageOps.exif_transpose(Image.open(args.image)).convert("RGB")
    W, H = im.size

    if args.cmd == "zoom":
        zoom(im, args.box, args.scale).save(args.out)
        print(args.out)
        return

    if args.cmd == "piers":
        r = piers(im, args.rows, args.cols, args.min_gap, args.min_prominence, args.baseline, args.polarity)
        r = {"image": str(args.image), **r}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        print(f"行 {r['rows'][0]}:{r['rows'][1]}  列 {r['cols'][0]}:{r['cols'][1]}  "
              f"极性 {r['polarity']}  找到 {r['count']} 列")
        for n, pier in enumerate(r["piers"]):
            print(f"  {n:>2}  col {pier['col']:>5}  突起度 {pier['prominence']:>6.1f}  亮度 {pier['level']:>6.1f}")
        print("列表：" + ",".join(str(p["col"]) for p in r["piers"]))
        print("喂给 geo.py spacing 之前先看 --sheet：非桥墩的峰（前景亮斑、栏杆、树）要剔掉，"
              "被前景挡断的构件分段之间用 ';' 隔开，如 --cols '38,133,218;745,788,829'")
        print(args.out)
        if args.sheet:
            args.sheet.parent.mkdir(parents=True, exist_ok=True)
            piers_sheet(im, r, args.sheet)
            print(args.sheet)
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.image.stem
    if args.cmd == "variants":
        stem = args.prefix or (f"{stem}_{'-'.join(map(str, args.box))}" if args.box else stem)
    outs = []
    if args.cmd == "edges":
        fw, fh = int(W * args.frac), int(H * args.frac)
        regions = {"top": (0, 0, W, fh), "bottom": (0, H - fh, W, H), "left": (0, 0, fw, H), "right": (W - fw, 0, W, H),
                   "corner_tl": (0, 0, 2 * fw, 2 * fh), "corner_tr": (W - 2 * fw, 0, W, 2 * fh),
                   "corner_bl": (0, H - 2 * fh, 2 * fw, H), "corner_br": (W - 2 * fw, H - 2 * fh, W, H)}
        for name, box in regions.items():
            scale = max(1.0, 1600 / max(box[2] - box[0], box[3] - box[1]))
            p = args.out_dir / f"{stem}_{name}.jpg"
            zoom(im, box, scale).save(p, quality=92)
            outs.append(p)
    elif args.cmd == "variants":
        base = im
        if args.persp:
            base = perspective(im, [float(x) for x in args.persp.split(",")])
            p = args.out_dir / f"{stem}_persp.jpg"
            base.save(p, quality=95)
            outs.append(p)
        if args.box:
            base = base.crop(args.box)
            p = args.out_dir / f"{stem}_crop.jpg"
            base.save(p, quality=95)
            outs.append(p)
        for name, img in (("flip", ImageOps.mirror(base)),
                          ("gray", ImageOps.autocontrast(ImageOps.grayscale(base), cutoff=1)),
                          ("wb", gray_world(base))):
            p = args.out_dir / f"{stem}_{name}.jpg"
            img.save(p, quality=95)
            outs.append(p)
        if max(base.size) < 800:
            k = 1024 / max(base.size)
            p = args.out_dir / f"{stem}_up.jpg"
            base.resize((int(base.width * k), int(base.height * k)), Image.LANCZOS).save(p, quality=95)
            outs.append(p)
    elif args.cmd == "grid":
        tw, th = W / args.cols, H / args.rows
        ox, oy = tw * args.overlap, th * args.overlap
        for r in range(args.rows):
            for c in range(args.cols):
                box = (int(max(0, c * tw - ox)), int(max(0, r * th - oy)), int(min(W, (c + 1) * tw + ox)), int(min(H, (r + 1) * th + oy)))
                p = args.out_dir / f"{stem}_r{r}c{c}.jpg"
                im.crop(box).save(p, quality=92)
                outs.append(p)
    for p in outs:
        print(p)


if __name__ == "__main__":
    main()
