#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""百度全景（国内街景）：找点、扫一片、按朝向出图、拼对比图。

用的是百度地图网页自己调用的公开接口，不需要 key。国内直连，不要走代理。
接口会限流，扫片区时步长别小于 15 米、并发别超过 32。
百度街景国内大多是 2017–2019 年采集，比对时看老建筑，新楼可能还没有。

示例：
  baidu_pano.py near 22.6047,114.0523                       # 最近的全景点
  baidu_pano.py info 09005700121709201230455178V            # 日期、位置、这条路上的所有点
  baidu_pano.py scan 22.6050,114.0535 --radius 300 --out panos.json
  baidu_pano.py render 09005700121709201230455178V --heading 47 --out v.jpg
  baidu_pano.py sheet --panos panos.json --toward 22.6072,114.0564 --offset -12 --out s.jpg
  baidu_pano.py sheet --ids ID1,ID2 --heading 45 --out s.jpg
  baidu_pano.py sheet --ids ID1 --headings 0,60,120,180,240,300 --out around.jpg   # 单点环视
  baidu_pano.py sheet --panos panos.json --road 某某路 --spread 60 --toward 22.6072,114.0564 --out s.jpg  # 只看一条路、抽稀
  baidu_pano.py sample --bbox 22.52,113.90,22.60,114.10 --n 24 --out cityA.jpg     # 候选城市街景抽样：比护栏、路灯、站台
"""
from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

API = "https://mapsv0.bdimg.com/"
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 强制直连


def _get(url: str, timeout: int = 20) -> bytes:
    return _opener.open(url, timeout=timeout).read()


def near_bdmc(x: float, y: float) -> dict | None:
    try:
        c = json.loads(_get(f"{API}?qt=qsdata&x={x:.0f}&y={y:.0f}")).get("content")
    except Exception:
        return None
    if not c:
        return None
    bx, by = c["x"] / 100, c["y"] / 100
    lat, lon = geo.convert(bx, by, "bdmc", "wgs")
    return {"id": c["id"], "bdmc": [bx, by], "wgs": [lat, lon], "road": c.get("RoadName", "")}


def near(lat: float, lon: float) -> dict | None:
    return near_bdmc(*geo.convert(lat, lon, "wgs", "bdmc"))


def info(pid: str) -> dict:
    c = json.loads(_get(f"{API}?qt=sdata&sid={pid}"))["content"][0]
    x, y = c["X"] / 100, c["Y"] / 100
    lat, lon = geo.convert(x, y, "bdmc", "wgs")
    roads = []
    for r in c.get("Roads") or []:
        roads.append([{"id": p["PID"], "wgs": list(geo.convert(p["X"] / 100, p["Y"] / 100, "bdmc", "wgs"))}
                      for p in (r.get("Panos") or [])])        # 部分点（施工便道、单点）没有路段信息
    return {"id": pid, "date": c.get("Date"), "wgs": [lat, lon], "bdmc": [x, y],
            "move_dir": c.get("MoveDir"), "roads": roads,
            "timeline": [t.get("ID") for t in (c.get("TimeLine") or [])]}


def scan(lat: float, lon: float, radius_m: float, step_m: float, workers: int = 24) -> dict:
    """在正方形网格上逐点查最近全景点，去重后返回 {id: {...}}。"""
    pts = []
    n = int(radius_m // step_m)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            p = geo.dest(geo.dest((lat, lon), 0, i * step_m), 90, j * step_m)
            pts.append(p)
    found: dict = {}
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(lambda p: near(*p), pts):
            if r:
                found[r["id"]] = r
    return found


def thin(panos: dict, spread_m: float) -> dict:
    """按最小间距抽稀：相距不到 spread_m 的点只留第一个。"""
    kept: dict = {}
    for k, v in panos.items():
        if all(geo.distance(tuple(v["wgs"]), tuple(u["wgs"])) >= spread_m for u in kept.values()):
            kept[k] = v
    return kept


def sample(bbox: tuple[float, float, float, float], n: int, spread_m: float, seed: int,
           skip: list[str], named_only: bool = True, workers: int = 16) -> list[dict]:
    """在范围内随机撒点找全景，去重、按间距抽稀，取 n 个；朝向用采集车行进方向（沿路）。"""
    import random
    rnd = random.Random(seed)
    s, w, nn, e = bbox
    found: dict = {}
    tries = 0
    while len(found) < n and tries < n * 8:
        batch = [(rnd.uniform(s, nn), rnd.uniform(w, e)) for _ in range(n * 2)]
        tries += len(batch)
        with ThreadPoolExecutor(workers) as ex:
            for r in ex.map(lambda p: near(*p), batch):
                if not r or r["id"] in found or any(k in (r.get("road") or "") for k in skip):
                    continue
                if named_only and not r.get("road"):        # 没路名的多是小区、校园内部路，看不到市政设施
                    continue
                if not (s <= r["wgs"][0] <= nn and w <= r["wgs"][1] <= e):
                    continue
                if all(geo.distance(tuple(r["wgs"]), tuple(u["wgs"])) >= spread_m for u in found.values()):
                    found[r["id"]] = r
                if len(found) >= n:
                    break
    items = []
    with ThreadPoolExecutor(8) as ex:
        infos = list(ex.map(lambda pid: info(pid), list(found)[:n]))
    for inf in infos:
        v = found[inf["id"]]
        items.append({"id": inf["id"], "heading": (inf.get("move_dir") or 0) % 360, "pitch": 0, "fov": 60,
                      "date": inf.get("date"), "wgs": v["wgs"], "road": v.get("road", ""),
                      "label": f"{(v.get('road') or '')[:10]} {str(inf.get('date') or '')[:6]}"})
    return items


def render(pid: str, heading: float, pitch: float = 10, fov: float = 80,
           w: int = 1024, h: int = 768, cache: Path | None = None) -> Image.Image:
    """按罗盘朝向渲染一张透视图。heading 0=北，pitch 正=抬头，fov 是竖直视角。宽最大 1024。"""
    w = min(w, 1024)
    key = f"{pid}_{heading:.0f}_{pitch:.0f}_{fov:.0f}_{w}x{h}.jpg"
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
        if (cache / key).exists():
            return Image.open(cache / key)
    url = (f"{API}?qt=pr3d&fovy={fov:.0f}&quality=80&panoid={pid}&heading={heading:.1f}"
           f"&pitch={pitch:.1f}&width={w}&height={h}")
    try:
        data = _get(url, 40)
    except Exception:
        return Image.new("RGB", (w, h), "gray")
    if cache:
        (cache / key).write_bytes(data)
    return Image.open(io.BytesIO(data))


def _font(size: int):
    for p in ("/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def sheet(items: list[dict], out: Path, cols: int = 3, tw: int = 480, th: int = 360,
          cache: Path | None = None) -> None:
    """items: [{id, heading, pitch?, fov?, label?}] → 带编号的拼图。"""
    def one(it):
        return render(it["id"], it["heading"], it.get("pitch", 10), it.get("fov", 80), cache=cache)

    with ThreadPoolExecutor(12) as ex:
        ims = list(ex.map(one, items))
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, rows * th), "black")
    d = ImageDraw.Draw(S)
    f = _font(16)
    for i, (it, im) in enumerate(zip(items, ims)):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im.convert("RGB").resize((tw, th)), (x, y))
        text = it.get("label") or f"{i}: …{it['id'][-9:]} h{it['heading']:.0f}"
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        d.text((x + 4, y + 2), text, fill="yellow", font=f)
    S.save(out, quality=88)



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache/pano"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("near")
    n.add_argument("latlon")

    i = sub.add_parser("info")
    i.add_argument("id")

    s = sub.add_parser("scan")
    s.add_argument("center")
    s.add_argument("--radius", type=float, default=250)
    s.add_argument("--step", type=float, default=20)
    s.add_argument("--out", type=Path, required=True)

    r = sub.add_parser("render")
    r.add_argument("id")
    r.add_argument("--heading", type=float, required=True)
    r.add_argument("--pitch", type=float, default=10)
    r.add_argument("--fov", type=float, default=80)
    r.add_argument("--out", type=Path, required=True)

    sh = sub.add_parser("sheet")
    g = sh.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", help="逗号分隔的 panoid")
    g.add_argument("--panos", type=Path, help="scan 输出的 JSON")
    g.add_argument("--spec", type=Path, help="JSON 列表 [{id, heading, pitch, fov, label}]")
    sh.add_argument("--heading", type=float, help="统一朝向")
    sh.add_argument("--headings", help="每个点都出这几个朝向，逗号分隔，如 0,60,120,180,240,300（单点环视）")
    sh.add_argument("--toward", help="lat,lon：每个点各自朝向这个目标")
    sh.add_argument("--offset", type=float, default=0, help="在 toward 方位上再加的角度")
    sh.add_argument("--pitch", type=float, default=10)
    sh.add_argument("--fov", type=float, default=80)
    sh.add_argument("--within", help="lat,lon,半径米：只取这个圆内的点")
    sh.add_argument("--road", help="只取路名包含这些字的点（scan 输出里的 road 字段），逗号分隔可给多个")
    sh.add_argument("--spread", type=float, help="抽稀：相邻两点至少相隔多少米")
    sh.add_argument("--limit", type=int, default=12, help="每张拼图最多几格，多了自动分页")
    sh.add_argument("--out", type=Path, required=True)

    sp = sub.add_parser("sample", help="候选城市/片区的街景随机抽样拼图：比护栏、路灯、站台、路缘这类市政设施的样式")
    sp.add_argument("--bbox", required=True, help="south,west,north,east（城区范围）")
    sp.add_argument("--n", type=int, default=24, help="抽几个点")
    sp.add_argument("--spread", type=float, default=300, help="两点最小间距 m")
    sp.add_argument("--seed", type=int, default=1)
    sp.add_argument("--skip", default="隧道,高速,高架,匝道,立交", help="路名含这些字的点跳过，逗号分隔")
    sp.add_argument("--heading-offset", type=float, default=0, help="在沿路方向上再转多少度（90 = 看路边）")
    sp.add_argument("--include-unnamed", action="store_true", help="也要没有路名的点（小区、校园内部路），默认跳过")
    sp.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "sample":
        bb = tuple(map(float, args.bbox.split(",")))
        items = sample(bb, args.n, args.spread, args.seed, [k for k in args.skip.split(",") if k],
                       named_only=not args.include_unnamed)
        for it in items:
            it["heading"] = (it["heading"] + args.heading_offset) % 360
        if not items:
            sys.exit("范围里没找到全景点（范围太小，或者这里没有百度街景）")
        pages = [items[k:k + 12] for k in range(0, len(items), 12)]
        for pi, page in enumerate(pages):
            out = args.out if pi == 0 else args.out.with_name(f"{args.out.stem}_{pi + 1}{args.out.suffix}")
            sheet(page, out, cache=args.cache)
            print(out)
        idx = args.out.with_suffix(".index.json")
        idx.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        dates = sorted(str(i.get("date") or "")[:4] for i in items)
        print(f"{len(items)} 个点，采集年份 {dates[0]}–{dates[-1]}；index -> {idx}")
        return
    if args.cmd == "near":
        print(json.dumps(near(*map(float, args.latlon.split(","))), ensure_ascii=False))
    elif args.cmd == "info":
        print(json.dumps(info(args.id), ensure_ascii=False, indent=1))
    elif args.cmd == "scan":
        lat, lon = map(float, args.center.split(","))
        res = scan(lat, lon, args.radius, args.step)
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(res)} panos -> {args.out}")
    elif args.cmd == "render":
        render(args.id, args.heading, args.pitch, args.fov, cache=args.cache).save(args.out)
        print(args.out)
    elif args.cmd == "sheet":
        if args.spec:
            items = json.loads(args.spec.read_text(encoding="utf-8"))
        else:
            if args.ids:
                need_pos = bool(args.within or args.toward)
                panos = {p: (info(p) if need_pos else None) for p in args.ids.split(",")}
            else:
                panos = json.loads(args.panos.read_text(encoding="utf-8"))
            if args.within:
                wl, wo, wr = map(float, args.within.split(","))
                panos = {k: v for k, v in panos.items() if geo.distance((wl, wo), v["wgs"]) <= wr}
            if args.road:
                keys = [k for k in args.road.split(",") if k]
                panos = {k: v for k, v in panos.items() if any(x in ((v or {}).get("road") or "") for x in keys)}
                print(f"--road 过滤后 {len(panos)} 个点")
            if args.spread:
                panos = thin(panos, args.spread)
                print(f"--spread 抽稀后 {len(panos)} 个点")
            target = tuple(map(float, args.toward.split(","))) if args.toward else None
            items = []
            for pid, v in panos.items():
                if args.headings:
                    for hd in (float(x) for x in args.headings.split(",")):
                        items.append({"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov})
                    continue
                if target:
                    hd = geo.bearing(tuple(v["wgs"]), target) + args.offset
                elif args.heading is not None:
                    hd = args.heading
                else:
                    ap.error("需要 --heading、--headings 或 --toward")
                items.append({"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov})
        pages = [items[k:k + args.limit] for k in range(0, len(items), args.limit)] or [[]]
        for pi, page in enumerate(pages):
            # 第 1 页就写到 --out 本身，后面的页加 _2、_3…，避免"--out 指定的文件不存在"
            out = args.out if pi == 0 else args.out.with_name(f"{args.out.stem}_{pi + 1}{args.out.suffix}")
            sheet(page, out, cache=args.cache)
            print(out)
        if len(pages) > 1:
            print(f"共 {len(pages)} 页：{args.out.name} 以及 {args.out.stem}_2 … _{len(pages)}，每页 {args.limit} 格")
        if len(pages) > 1 or args.spec is None:
            idx = args.out.with_suffix(".index.json")
            idx.write_text(json.dumps(items, indent=1), encoding="utf-8")
            print(f"index -> {idx}")


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
