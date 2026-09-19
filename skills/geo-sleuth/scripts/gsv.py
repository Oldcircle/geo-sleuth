#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Google 街景（国外主力）：找点、看日期和周边点、按朝向出图、拼对比图。用法和 baidu_pano.py 对齐。

用的是 Google 地图网页自己调用的接口，不需要 key。国内必须走代理（--proxy 或 GEO_PROXY）。
国内几乎没有 Google 街景覆盖，国内照片用 baidu_pano.py。

示例：
  gsv.py near 35.6595,139.7005 --radius 50                   # 最近的全景点：id、坐标、拍摄日期、历史批次、地址、周边点
  gsv.py render XlVh96-Z9lAI5tKrU2O4Yg --heading 90 --out v.jpg
  gsv.py sheet --at 35.6595,139.7005 --headings 0,60,120,180,240,300 --out around.jpg   # 单点环视
  gsv.py sheet --ids ID1,ID2 --toward 35.6600,139.7010 --out s.jpg                     # 每个点朝向同一目标
  gsv.py sheet --points pts.json --heading 90 --date 2018 --out s2018.jpg              # 只取某一批次（照片里街景水印的年份）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402
from baidu_pano import _font  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
# 只要官方街景车覆盖（用户上传的全景照片 id 形如 CIHM0og…，透视图接口出不了图）
META = ("https://maps.googleapis.com/maps/api/js/GeoPhotoService.SingleImageSearch?pb=!1m5!1sapiv3!5sUS!11m2!1m1!1b0"
        "!2m4!1m2!3d{lat}!4d{lon}!2d{radius}!3m10!2m2!1sen!2sUS!9m1!1e2!11m4!1m3!1e2!2b1!3e2"
        "!4m6!1e1!1e2!1e3!1e4!1e8!1e6&callback=cb")
THUMB = ("https://streetviewpixels-pa.googleapis.com/v1/thumbnail?panoid={id}&cb_client=maps_sv.tactile"
         "&w={w}&h={h}&yaw={yaw:.1f}&pitch={pitch:.1f}&thumbfov={fov:.0f}")


def _curl(url: str, proxy: str | None, out: Path | None = None) -> bytes:
    cmd = ["curl", "-s", "-m", "40", "-A", UA]
    if proxy:
        cmd += ["-x", proxy]
    if out:
        cmd += ["-o", str(out)]
    r = subprocess.run(cmd + [url], capture_output=True)
    return r.stdout


def near(lat: float, lon: float, radius: float, proxy: str | None) -> dict | None:
    t = _curl(META.format(lat=lat, lon=lon, radius=radius), proxy).decode("utf-8", "replace")
    m = re.search(r"cb\(\s*(.*)\s*\)\s*;?\s*$", t, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
        body = d[1]
    except (json.JSONDecodeError, IndexError, TypeError):
        return None
    out: dict = {}
    try:
        out["id"] = body[1][1]
        loc = body[5][0][1]
        out["wgs"] = [loc[0][2], loc[0][3]]
        out["pano_heading"] = round(loc[2][0], 1) if loc[2] else None
    except (IndexError, TypeError):
        return None
    try:
        out["address"] = " / ".join(x[0] for x in body[3][2])
    except (IndexError, TypeError):
        out["address"] = ""
    # 本全景的拍摄日期在 body[6][7]；body[5][0][8] 是历史批次 [邻点序号, [年, 月(, 日)]]，别拿它当本全景日期
    try:
        out["date"] = _ym(body[6][7])
    except (IndexError, TypeError):
        out["date"] = None
    nbrs = []
    try:
        for e in body[5][0][3][0]:
            nbrs.append({"id": e[0][1], "wgs": [e[2][0][2], e[2][0][3]]})
    except (IndexError, TypeError):
        pass
    hist = []
    try:
        for idx, ym, *_ in body[5][0][8] or []:
            # 历史批次里会混进用户上传的全景（透视图出灰图）：id 以 CIHM0og/CIAB/CAoS 开头，长度 22–28 位不等
            pid = nbrs[idx]["id"] if idx < len(nbrs) else ""
            if len(pid) == 22 and not pid.startswith(("CIHM", "CIAB", "CAoS")):
                hist.append({**nbrs[idx], "date": _ym(ym)})
    except (IndexError, TypeError, ValueError):
        pass
    out["history"] = sorted(hist, key=lambda h: h["date"], reverse=True)
    out["dates_seen"] = sorted({d for d in [out["date"], *(h["date"] for h in hist)] if d})
    out["neighbors"] = nbrs[:40]
    return out


def _ym(v: list) -> str:
    return f"{v[0]}-{int(v[1]):02d}"


def pick_date(res: dict, date: str) -> dict | None:
    """near() 的结果里挑某一批次（'2018' 或 '2018-07'）：本全景或历史批次里第一个匹配的；没有返回 None。"""
    for p in [{"id": res["id"], "wgs": res["wgs"], "date": res["date"]}, *res.get("history", [])]:
        if p["date"] and p["date"].startswith(date):
            return p
    return None


def render(pid: str, heading: float, pitch: float, fov: float, w: int, h: int, proxy: str | None,
           cache: Path) -> Image.Image:
    """heading 罗盘方位；pitch 正=抬头；fov 水平视角。"""
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / f"{pid}_{heading:.0f}_{pitch:.0f}_{fov:.0f}_{w}x{h}.jpg"
    if not (p.exists() and p.stat().st_size > 2000):
        _curl(THUMB.format(id=pid, w=w, h=h, yaw=heading % 360, pitch=-pitch, fov=fov), proxy, p)
    try:
        return Image.open(p).convert("RGB")
    except Exception:  # noqa: BLE001
        return Image.new("RGB", (w, h), "gray")


def sheet(items: list[dict], out: Path, proxy: str | None, cache: Path, cols: int = 3, tw: int = 480, th: int = 360) -> None:
    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(lambda it: render(it["id"], it["heading"], it.get("pitch", 0), it.get("fov", 90),
                                           640, 480, proxy, cache), items))
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, max(1, rows) * th), "black")
    d = ImageDraw.Draw(S)
    f = _font(16)
    for i, (it, im) in enumerate(zip(items, ims)):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im.resize((tw, th)), (x, y))
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        d.text((x + 4, y + 2), it.get("label") or f"{i}: …{it['id'][-8:]} h{it['heading']:.0f}", fill="yellow", font=f)
    S.save(out, quality=88)



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache/gsv"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--proxy", default=argparse.SUPPRESS, help="写在子命令前后都行")
        sp.add_argument("--cache", type=Path, default=argparse.SUPPRESS)

    n = sub.add_parser("near")
    common(n)
    n.add_argument("latlon")
    n.add_argument("--radius", type=float, default=50)

    r = sub.add_parser("render")
    common(r)
    r.add_argument("id")
    r.add_argument("--heading", type=float, required=True)
    r.add_argument("--pitch", type=float, default=0, help="正=抬头")
    r.add_argument("--fov", type=float, default=90, help="水平视角")
    r.add_argument("--width", type=int, default=1024)
    r.add_argument("--height", type=int, default=768)
    r.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("sheet")
    common(s)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", help="逗号分隔的 panoid")
    g.add_argument("--at", help="lat,lon：取最近的全景点")
    g.add_argument("--points", type=Path, help="JSON {name:[lat,lon]}：每个点各取最近的全景点")
    h = s.add_mutually_exclusive_group(required=True)
    h.add_argument("--heading", type=float)
    h.add_argument("--headings", help="逗号分隔，如 0,60,120,180,240,300")
    h.add_argument("--toward", help="lat,lon：每个点朝向这个目标")
    s.add_argument("--offset", type=float, default=0)
    s.add_argument("--pitch", type=float, default=0)
    s.add_argument("--fov", type=float, default=90)
    s.add_argument("--radius", type=float, default=50)
    s.add_argument("--date", help="只取这一批次（2018 或 2018-07），从本全景和历史批次里挑；照片里的街景水印年份就用它")
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if not args.proxy:
        print("提示：国内访问 Google 街景需要 --proxy socks5h://127.0.0.1:10808（示例）", file=sys.stderr)
    if args.cmd == "near":
        lat, lon = map(float, args.latlon.split(","))
        res = near(lat, lon, args.radius, args.proxy)
        print(json.dumps(res, ensure_ascii=False, indent=1) if res else "附近没有 Google 街景（加大 --radius，或这里没覆盖）")
    elif args.cmd == "render":
        render(args.id, args.heading, args.pitch, args.fov, args.width, args.height, args.proxy, args.cache).save(args.out)
        print(args.out)
    else:
        panos: dict[str, dict] = {}
        if args.ids:
            panos = {pid: {"ll": None, "name": "", "date": ""} for pid in args.ids.split(",")}
        else:
            pts = {"at": list(map(float, args.at.split(",")))} if args.at else json.loads(args.points.read_text(encoding="utf-8"))
            for name, (la, lo) in pts.items():
                res = near(la, lo, args.radius, args.proxy)
                if res and args.date:
                    p = pick_date(res, args.date)
                    if not p:
                        print(f"{name}: 没有 {args.date} 批次（有 {', '.join(res['dates_seen'])}）", file=sys.stderr)
                        continue
                    panos.setdefault(p["id"], {"ll": p["wgs"], "name": name, "date": p["date"]})
                elif res:
                    panos.setdefault(res["id"], {"ll": res["wgs"], "name": name, "date": res.get("date") or ""})
                else:
                    print(f"{name}: 附近没有全景", file=sys.stderr)
        target = tuple(map(float, args.toward.split(","))) if args.toward else None
        items = []
        for pid, meta in panos.items():
            ll = meta["ll"]
            if args.headings:
                heads = [float(x) for x in args.headings.split(",")]
            elif target:
                if ll is None:
                    info = near(*target, 5000, args.proxy)  # 只有 id 时拿不到坐标，按目标附近估；建议用 --points
                    ll = info["wgs"] if info else list(target)
                heads = [geo.bearing(tuple(ll), target) + args.offset]
            else:
                heads = [args.heading]
            for hd in heads:
                where = f"{ll[0]:.5f},{ll[1]:.5f}" if ll else f"…{pid[-8:]}"
                label = " ".join(x for x in (meta["name"][:18], where, meta["date"], f"h{hd % 360:.0f}") if x)
                items.append({"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov,
                              "label": f"{len(items)}: {label}", "point": meta["name"], "wgs": ll, "date": meta["date"]})
        pages = [items[k:k + args.limit] for k in range(0, len(items), args.limit)] or [[]]
        for pi, page in enumerate(pages):
            out = args.out if pi == 0 else args.out.with_name(f"{args.out.stem}_{pi + 1}{args.out.suffix}")
            sheet(page, out, args.proxy, args.cache)
            print(out)
        args.out.with_suffix(".index.json").write_text(json.dumps(items, indent=1), encoding="utf-8")


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
