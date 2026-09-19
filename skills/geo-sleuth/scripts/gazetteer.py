#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""行政区名录：把候选区域"列全"并给出范围、面积、扫描成本。给 board.py 用，也可以单独查。

  children  列出一个行政区的全部下一级（或指定级别）行政区，带 bbox、bbox 面积、中心
  info      一个行政区的 OSM 关系、admin_level、bbox、中心
  urban     一个行政区的建成区范围（OSM 住宅/商业/工业用地的最大连片块），给扫描成本和 scan_bbox 用
  cost      一个 bbox 按 tiles.py sheet --grid 的口径要扫几格、几页

数据来自 OSM Overpass（走代理，结果按查询缓存在 .geo-cache/osm/）。OSM 的行政区列表可能缺项：
children 会和本地 data/cn_admin.json（国内三级行政区表，若存在）合并，缺 bbox 的条目标出来。
admin_level 各国不同：中国 省 4 / 地级 5 / 县级 6，法国 大区 4 / 省 6，美国 州 4 / 县 6。不确定就不给 --level，
脚本会从上级的 admin_level 往下试。

示例：
  gazetteer.py children <省级行政区全名> --out districts.json          # 直辖市 → 全部区县
  gazetteer.py children <国家名> --level 4                               # 国家 → 一级行政区
  gazetteer.py info <行政区名>
  gazetteer.py urban <区县名> --within <省级行政区全名>                   # 建成区 bbox + 面积
  gazetteer.py cost --bbox <s,w,n,e> --zoom 16 --cell 320 --cols 5
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402
import osm  # noqa: E402

DATA = Path(__file__).parent.parent / "data"
LEVEL_NAMES = {"CN": {4: "省级", 5: "地级", 6: "县级", 7: "乡镇"}, "FR": {4: "大区", 6: "省", 8: "市镇"},
               "US": {4: "州", 6: "县", 8: "市"}, "*": {2: "国家", 4: "一级行政区", 6: "二级行政区", 8: "三级行政区"}}


def _cache(args) -> Path:
    return Path(getattr(args, "cache", None) or ".geo-cache/osm")


def _bbox_km2(b: list[float]) -> float:
    s, w, n, e = b
    return abs(n - s) * 110.574 * abs(e - w) * 111.320 * math.cos(math.radians((s + n) / 2))


def _rel_rows(data: dict) -> list[dict]:
    rows = []
    for el in data.get("elements", []):
        if el.get("type") != "relation":
            continue
        t, b = el.get("tags") or {}, el.get("bounds") or {}
        if not b:
            continue
        bbox = [b["minlat"], b["minlon"], b["maxlat"], b["maxlon"]]
        rows.append({"name": t.get("name", str(el["id"])), "name_en": t.get("name:en", ""), "osm_id": el["id"],
                     "admin_level": int(t.get("admin_level") or 0), "bbox": [round(v, 5) for v in bbox],
                     "bbox_km2": round(_bbox_km2(bbox), 1),
                     "center": [round((bbox[0] + bbox[2]) / 2, 5), round((bbox[1] + bbox[3]) / 2, 5)],
                     "population": t.get("population", "")})
    return rows


def find_relation(name: str, proxy: str | None, cache: Path, within: str | None = None,
                  level: int | None = None) -> list[dict]:
    """按名字找行政区关系（可能多个同名：北京朝阳区、长春朝阳区），带 bbox。"""
    lv = f'["admin_level"="{level}"]' if level else ""
    if within:
        ql = (f'[out:json][timeout:120];rel["name"="{within}"]["boundary"="administrative"];map_to_area->.p;'
              f'rel(area.p)["name"="{name}"]["boundary"="administrative"]{lv};out tags bb;')
    else:
        ql = f'[out:json][timeout:120];rel["name"="{name}"]["boundary"="administrative"]{lv};out tags bb;'
    rows = _rel_rows(osm.run(ql, proxy, cache))
    rows.sort(key=lambda r: (r["admin_level"], -r["bbox_km2"]))
    return rows


def children(parent: str, proxy: str | None, cache: Path, level: int | None, within: str | None) -> tuple[dict, list[dict]]:
    ps = find_relation(parent, proxy, cache, within)
    if not ps:
        sys.exit(f"OSM 里没有叫“{parent}”的行政区关系：换全名（带不带“市/省/区”）、或加 --within 上级名")
    p = ps[0]
    levels = [level] if level else [p["admin_level"] + k for k in (1, 2, 3, 4)]
    for lv in levels:
        ql = (f'[out:json][timeout:180];rel({p["osm_id"]});map_to_area->.a;'
              f'rel(area.a)["boundary"="administrative"]["admin_level"="{lv}"];out tags bb;')
        rows = _rel_rows(osm.run(ql, proxy, cache))
        rows = [r for r in rows if r["osm_id"] != p["osm_id"]]
        if len(rows) >= 2:
            return p, sorted(rows, key=lambda r: r["name"])
    return p, []


def _cn_admin_children(parent: str) -> list[str]:
    """本地三级行政区表里 parent 的直接下级名（表不存在就空）。"""
    f = DATA / "cn_admin.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    # 兼容两种结构：{"_meta":…, "items":[{name, code, parent, level}]} 或 modood 的嵌套 [{name, code, children:[…]}]
    items = d.get("items") if isinstance(d, dict) else None
    if items:
        names = {it["name"] for it in items if it.get("parent") == parent}
        if not names:  # parent 可能是"重庆市"而表里是"重庆"或反过来
            names = {it["name"] for it in items if it.get("parent", "").rstrip("市省") == parent.rstrip("市省")}
        return sorted(names)
    nodes = d if isinstance(d, list) else d.get("data") or []

    def walk(ns):
        for n in ns:
            if n.get("name", "").rstrip("市省") == parent.rstrip("市省"):
                ch = n.get("children") or []
                # 直辖市：省 → 市辖区（一个假层）→ 区县
                if len(ch) == 1 and (ch[0].get("children") or []):
                    ch = ch[0]["children"]
                return [c["name"] for c in ch]
            r = walk(n.get("children") or [])
            if r:
                return r
        return []

    return walk(nodes)


def urban(name: str, proxy: str | None, cache: Path, within: str | None) -> dict:
    """建成区：OSM 用地面的最大连片块。用地没画时退到 place=city/town 节点按人口估半径。"""
    rs = find_relation(name, proxy, cache, within)
    if not rs:
        sys.exit(f"OSM 里没有叫“{name}”的行政区：换全名或加 --within")
    r = rs[0]
    ql = (f'[out:json][timeout:180];rel({r["osm_id"]});map_to_area->.a;'
          f'way["landuse"~"^(residential|commercial|retail|industrial)$"](area.a);out bb;')
    els = osm.run(ql, proxy, cache).get("elements", [])
    boxes = [(e["bounds"]["minlat"], e["bounds"]["minlon"], e["bounds"]["maxlat"], e["bounds"]["maxlon"])
             for e in els if e.get("bounds")]
    out = {"name": r["name"], "admin_bbox": r["bbox"], "admin_bbox_km2": r["bbox_km2"], "landuse_polygons": len(boxes)}
    # 行政中心：place=city/town 节点里人口最多的那个；用地连片块优先取离它最近的（OSM 只画了一半时，最大的块常是别的镇）
    ql2 = (f'[out:json][timeout:120];rel({r["osm_id"]});map_to_area->.a;'
           f'node["place"~"^(city|town)$"](area.a);out;')
    nodes = osm.run(ql2, proxy, cache).get("elements", [])
    seat = None
    if nodes:
        def pop(n):
            return int(re.sub(r"\D", "", (n.get("tags") or {}).get("population", "0") or "0") or 0)
        best = max(nodes, key=lambda n: (pop(n), (n.get("tags") or {}).get("place") == "city"))
        seat = {"name": (best.get("tags") or {}).get("name", ""), "ll": (best["lat"], best["lon"]), "population": pop(best)}
        out["seat"] = seat
    if len(boxes) >= 3:
        # 2 km 网格连通块，取面积最大的块
        cs = 2 / 110.574
        cell_of = {}
        for i, b in enumerate(boxes):
            cell_of.setdefault((int(((b[0] + b[2]) / 2) / cs), int(((b[1] + b[3]) / 2) / cs)), []).append(i)
        seen, blocks = set(), []
        for c0 in cell_of:
            if c0 in seen:
                continue
            stack, comp = [c0], []
            seen.add(c0)
            while stack:
                c = stack.pop()
                comp.extend(cell_of[c])
                for di in (-1, 0, 1):
                    for dj in (-1, 0, 1):
                        nb = (c[0] + di, c[1] + dj)
                        if nb in cell_of and nb not in seen:
                            seen.add(nb)
                            stack.append(nb)
            blocks.append(comp)
        def block_bbox(comp):
            return [min(boxes[i][0] for i in comp), min(boxes[i][1] for i in comp),
                    max(boxes[i][2] for i in comp), max(boxes[i][3] for i in comp)]

        def block_area(comp):
            return sum(_bbox_km2(list(boxes[i])) for i in comp)

        chosen, how = None, ""
        if seat:
            near = [c for c in blocks if geo.distance(seat["ll"], (((bb := block_bbox(c))[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)) <= 12000]
            if near:
                chosen, how = max(near, key=block_area), f"离行政中心 {seat['name']} 最近的连片用地"
        if chosen is None:
            chosen, how = max(blocks, key=block_area), "最大连片用地（没找到行政中心节点，可能是别的镇）"
        bb = block_bbox(chosen)
        if seat and not (bb[0] <= seat["ll"][0] <= bb[2] and bb[1] <= seat["ll"][1] <= bb[3]):
            # 连片块没盖住行政中心：把中心点周围 1.5 km 并进来
            s2, w2 = geo.dest(geo.dest(seat["ll"], 180, 1500), 270, 1500)
            n2, e2 = geo.dest(geo.dest(seat["ll"], 0, 1500), 90, 1500)
            bb = [min(bb[0], s2), min(bb[1], w2), max(bb[2], n2), max(bb[3], e2)]
            how += "，并入行政中心周围 1.5 km"
        out.update({"urban_bbox": [round(v, 5) for v in bb], "urban_bbox_km2": round(_bbox_km2(bb), 1),
                    "urban_landuse_km2": round(block_area(chosen), 1), "blocks": len(blocks), "source": "landuse", "how": how})
        return out
    if seat:
        pop = seat["population"]
        rad = max(1500.0, min(12000.0, math.sqrt(max(pop, 20000) / 6000 / math.pi) * 1000))  # 约 6000 人/km²
        s, w = geo.dest(geo.dest(seat["ll"], 180, rad), 270, rad)
        n, e = geo.dest(geo.dest(seat["ll"], 0, rad), 90, rad)
        out.update({"urban_bbox": [round(s, 5), round(w, 5), round(n, 5), round(e, 5)],
                    "urban_bbox_km2": round(_bbox_km2([s, w, n, e]), 1), "source": "place-node",
                    "place": seat["name"], "population": pop,
                    "note": "OSM 没画用地，按 place 节点人口估的建成区半径，只能当数量级"})
        return out
    out["note"] = "OSM 既没有用地也没有 place 节点：自己在卫星图上框 scan_bbox"
    return out


def cost(bbox: list[float], zoom: int, cell: int, cols: int) -> dict:
    s, w, n, e = bbox
    mpp = 156543.03392 * math.cos(math.radians((s + n) / 2)) / 2 ** zoom
    step = cell * mpp * 0.9
    rows_ = max(1, math.ceil((n - s) * 110574 / step))
    cols_ = max(1, math.ceil((e - w) * 111320 * math.cos(math.radians((s + n) / 2)) / step))
    cells = rows_ * cols_
    return {"bbox": bbox, "km2": round(_bbox_km2(bbox), 1), "zoom": zoom, "cell_px": cell, "cell_m": round(cell * mpp),
            "cells": cells, "pages": math.ceil(cells / (cols * cols)), "per_page": cols * cols}


def _neg_coords(argv: list[str]) -> list[str]:
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache/osm"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--proxy", default=argparse.SUPPRESS)
        sp.add_argument("--cache", type=Path, default=argparse.SUPPRESS)

    c = sub.add_parser("children", help="一个行政区的全部下级行政区（带 bbox），候选要“列全”时用")
    common(c)
    c.add_argument("name")
    c.add_argument("--level", type=int, help="OSM admin_level；不给就从上级往下试")
    c.add_argument("--within", help="上级行政区名，同名消歧")
    c.add_argument("--out", type=Path, help="写出 {名字: {bbox, bbox_km2, center, ...}}")

    i = sub.add_parser("info")
    common(i)
    i.add_argument("name")
    i.add_argument("--within")
    i.add_argument("--level", type=int)

    u = sub.add_parser("urban", help="建成区范围：扫描成本按这个算，不按整个行政区")
    common(u)
    u.add_argument("name")
    u.add_argument("--within")
    u.add_argument("--out", type=Path)

    k = sub.add_parser("cost", help="一个 bbox 按 tiles.py sheet --grid 口径要扫几页")
    k.add_argument("--bbox", required=True)
    k.add_argument("--zoom", type=int, default=16)
    k.add_argument("--cell", type=int, default=320)
    k.add_argument("--cols", type=int, default=5)

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    cache = _cache(args)
    if args.cmd == "cost":
        print(json.dumps(cost([float(v) for v in args.bbox.split(",")], args.zoom, args.cell, args.cols), ensure_ascii=False))
        return
    if args.cmd == "info":
        rows = find_relation(args.name, args.proxy, cache, args.within, args.level)
        if not rows:
            sys.exit("没找到；换全名或加 --within")
        for r in rows[:8]:
            print(json.dumps(r, ensure_ascii=False))
        return
    if args.cmd == "urban":
        out = urban(args.name, args.proxy, cache, args.within)
        if args.out:
            args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    if args.cmd == "children":
        p, rows = children(args.name, args.proxy, cache, args.level, args.within)
        local = _cn_admin_children(p["name"])
        names = {r["name"] for r in rows}
        missing = [n for n in local if n not in names and not any(n.rstrip("区县市") == m.rstrip("区县市") for m in names)]
        out = {r["name"]: {k: r[k] for k in ("osm_id", "admin_level", "bbox", "bbox_km2", "center", "name_en")} for r in rows}
        for n in missing:
            out[n] = {"osm_id": None, "admin_level": None, "bbox": None, "bbox_km2": None, "center": None,
                      "name_en": "", "note": "只在本地行政区表里有，OSM 没查到关系：bbox 用 info/urban 单独补，或先按上级范围估"}
        lvl = rows[0]["admin_level"] if rows else None
        print(f"{p['name']}（admin_level {p['admin_level']}）下级 admin_level {lvl}：OSM {len(rows)} 个"
              + (f"，本地表补 {len(missing)} 个（{', '.join(missing)}）" if missing else "")
              + ("；本地表没有这个上级，无法核对是否列全" if not local else ""))
        for name, r in sorted(out.items(), key=lambda kv: -(kv[1]["bbox_km2"] or 0)):
            b = r["bbox"]
            print(f"  {name:<14} {r['bbox_km2'] or '?':>9} km²  {b if b else '（无 bbox）'}")
        if args.out:
            args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"-> {args.out}")


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
