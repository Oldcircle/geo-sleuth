#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""OpenStreetMap Overpass 查询：按"要素组合"和"线状走廊"找候选点，而不是满地图找。

适合"没有名字，但有结构"的照片：电塔挨着高铁桥、河湾边的教堂、四条轨道的道口……
国外数据很全；国内道路、河流、铁路、输电线、大型建筑可用，小店和小区内部基本没有。
国内 OSM 数据不全，结果只能当候选来源，不能当排除依据。
国内访问 Overpass 需要代理：--proxy socks5h://127.0.0.1:10808（示例） 或环境变量 GEO_PROXY。

  find       在范围内找某类要素
  near       找"A 附近 N 米内有 B（还可以再加 C）"的 A
  crossings  线变点：一条河/铁路/公路上的桥、坝、渡口、道口（道口按节点数估轨道数）
  route      公交/铁路/轮渡线路号 → 沿线采样点，把"满城找"变成"沿一条线找"
  intersect  两类线状要素的交叉点（铁路×输电线…），可要求交点外侧有折角（转角塔、河湾）
  street-scan 街景几何模板：顺着一条街看过去的方位 + 街两侧"有楼/没楼" → 整个城镇的候选路口
  along      沿任意公路/河/线按步长取点（可往路的一侧偏移），给卫星缩略图或街景扫路边
  buildings  按占地面积列大建筑（厂房、仓库、农场棚），标出周围稀疏程度
  coverage   各候选行政区里某类要素有几个：枚举候选之前先查 OSM 覆盖
  geom       任意过滤条件导出 GeoJSON（保留线和面的几何），做自定义分析
  raw        跑一段自己写的 Overpass QL（{{bbox}} 会被替换成 s,w,n,e）

输出 JSON {名字或id: [lat, lon]}（WGS84），可以直接给 tiles.py mark --points 画到卫星图上。

示例：
  osm.py find --bbox 30.24,120.12,30.27,120.17 '["highway"="street_lamp"]'
  osm.py near --area 江苏省 --a '["railway"="rail"]["highspeed"="yes"]["bridge"]' --b '["power"="tower"]' --within 700 --c '["waterway"="river"]' --within-c 100
  osm.py crossings --bbox 31.9,118.4,32.3,119.0 --line '["waterway"="river"]["name"="长江"]' --kind bridge,dam,ferry
  osm.py crossings --bbox <s,w,n,e> --line '["railway"="rail"]' --kind level_crossing
  osm.py route --bbox <s,w,n,e> --kind bus --ref <线路号> --step 150 --out route.json
  osm.py intersect --area <省级行政区全名> --a '["railway"="rail"]["electrified"="contact_line"]' --b '["power"="line"]' --bend-min 25 --rank-near '["place"~"^(city|town)$"]'
  osm.py street-scan --bbox <城镇 s,w,n,e> --bearing 320:80 --right building --left empty --out cands.json
  osm.py geom '["building"]' --bbox 30.25,120.15,30.26,120.16 --out b.geojson
  osm.py along --bbox <s,w,n,e> --line '["highway"]["ref"="<道路编号>"]' --step 400 --side north --offset 80 --out pts.json
  osm.py buildings --bbox <s,w,n,e> --min-area 1500 --sort sparse --out big.json
  osm.py coverage --areas <区县A>,<区县B>,<区县C> --filter '["leisure"~"^(pitch|track)$"]'
  osm.py raw query.overpassql --bbox 30.2,120.1,30.3,120.2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def run(ql: str, proxy: str | None, cache: Path, timeout: int = 180, rounds: int = 3) -> dict:
    """依次试各个镜像；服务器忙（公共 Overpass 常见）时隔一会儿整轮重试。结果按查询缓存。"""
    cache.mkdir(parents=True, exist_ok=True)
    key = cache / (hashlib.sha1(ql.encode()).hexdigest()[:16] + ".json")
    if key.exists():
        return json.loads(key.read_text(encoding="utf-8"))
    last = ""
    for rnd in range(rounds):
        for ep in ENDPOINTS:
            cmd = ["curl", "-s", "-m", str(timeout + 30), "--data-urlencode", f"data={ql}", ep]
            if proxy:
                cmd[1:1] = ["-x", proxy]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            try:
                data = json.loads(r.stdout)
            except json.JSONDecodeError:
                last = " ".join(re.sub(r"<[^>]+>", " ", r.stdout or r.stderr).split())[-240:]
                continue
            if data.get("remark"):
                print(f"Overpass 提示（结果可能不全）：{data['remark'][:200]}", file=sys.stderr)
            key.write_text(json.dumps(data), encoding="utf-8")
            return data
        if rnd < rounds - 1:
            print(f"Overpass 各镜像都没返回结果，{15 * (rnd + 1)} 秒后重试：{last}", file=sys.stderr)
            time.sleep(15 * (rnd + 1))
    sys.exit(f"Overpass 查询失败（公共服务器忙就换个时间，查询报错就检查写法、缩小范围）：{last}")


def _scope(args) -> tuple[str, str]:
    """返回 (前置语句, 过滤后缀)。"""
    if args.area:
        return f'area["name"="{args.area}"]->.searchArea;', "(area.searchArea)"
    if args.bbox:
        s, w, n, e = args.bbox
        return "", f"({s},{w},{n},{e})"
    sys.exit("需要 --bbox 或 --area")


def _center(el: dict) -> list[float] | None:
    if el["type"] == "node":
        return [el.get("lat"), el.get("lon")]
    c = el.get("center") or {}
    return [c["lat"], c["lon"]] if "lat" in c else None


def _points(data: dict) -> dict:
    out = {}
    for el in data.get("elements", []):
        ll = _center(el)
        if not ll or ll[0] is None:
            continue
        name = (el.get("tags") or {}).get("name") or f"{el['type']}/{el['id']}"
        if name in out:
            name = f"{name}#{el['id']}"
        out[name] = [round(ll[0], 6), round(ll[1], 6)]
    return out


def _dist(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def _cluster(items: list[tuple[str, list[float], dict]], radius: float) -> list[dict]:
    """相距 radius 米以内的结果并成一处（一座桥常被切成几段 way；一个道口每条轨道一个节点）。"""
    groups: list[dict] = []
    for name, ll, tags in items:
        for g in groups:
            if _dist(g["center"], ll) <= radius:
                g["members"].append((name, ll, tags))
                n = len(g["members"])
                g["center"] = [(g["center"][0] * (n - 1) + ll[0]) / n, (g["center"][1] * (n - 1) + ll[1]) / n]
                break
        else:
            groups.append({"center": list(ll), "members": [(name, ll, tags)]})
    return groups


def _sample(elements: list[dict], step: float) -> list[list[float]]:
    """把 out geom 的线沿线每隔 step 米取一个点。"""
    pts = []
    for el in elements:
        geom = el.get("geometry") or []
        acc = 0.0
        for a, b in zip(geom, geom[1:]):
            pa, pb = (a["lat"], a["lon"]), (b["lat"], b["lon"])
            seg = _dist(pa, pb)
            while seg > 0 and acc <= seg:
                t = acc / seg
                pts.append([round(pa[0] + (pb[0] - pa[0]) * t, 6), round(pa[1] + (pb[1] - pa[1]) * t, 6)])
                acc += step
            acc -= seg
    return pts


def cmd_crossings(args) -> dict:
    pre, sc = _scope(args)
    kinds = set(args.kind.split(","))
    buf = f"{args.buffer:.0f}"
    parts = []
    if "bridge" in kinds:
        parts.append(f'way["bridge"]["bridge"!="no"](around.L:{buf}){sc};')
    if "dam" in kinds:
        parts.append(f'nwr["waterway"~"^(dam|weir)$"](around.L:{buf}){sc};')
    if "ferry" in kinds:
        parts.append(f'way["route"="ferry"](around.L:{buf}){sc};')
    if "level_crossing" in kinds:
        parts.append(f'node["railway"~"^(level_crossing|crossing)$"](around.L:{buf}){sc};')
    if not parts:
        sys.exit("--kind 只支持 bridge,dam,ferry,level_crossing")
    ql = f"[out:json][timeout:180];{pre}way{args.line}{sc}->.L;(" + "".join(parts) + ");out center tags;"
    items = []
    for el in run(ql, args.proxy, args.cache).get("elements", []):
        ll = _center(el)
        if not ll or ll[0] is None:
            continue
        tags = el.get("tags") or {}
        items.append((tags.get("name") or "", ll, tags))
    groups = _cluster(items, 25 if kinds == {"level_crossing"} else 150)
    print(f"{len(groups)} 处（由 {len(items)} 个 OSM 要素合并）")
    pts = {}
    for i, g in enumerate(groups, 1):
        tags = [m[2] for m in g["members"]]
        names = sorted({m[0] for m in g["members"] if m[0]})
        if any(t.get("railway") in ("level_crossing", "crossing") for t in tags):
            kind = f"道口·约{len(g['members'])}轨"
        elif any(t.get("waterway") in ("dam", "weir") for t in tags):
            kind = "坝/堰"
        elif any(t.get("route") == "ferry" for t in tags):
            kind = "渡口航线"
        else:
            use = {("铁路" if t.get("railway") else "公路" if t.get("highway") else "其他") for t in tags}
            kind = "桥·" + "/".join(sorted(use))
        label = f"{i:02d} {kind} {'、'.join(names)[:40]}".strip()
        pts[label] = [round(g["center"][0], 6), round(g["center"][1], 6)]
    return pts


def cmd_route(args) -> dict:
    pre, sc = _scope(args)
    flt = f'["type"="route"]["route"="{args.kind}"]'
    if args.ref:
        flt += f'["ref"="{args.ref}"]'
    if args.name:
        flt += f'["name"~"{args.name}"]'
    ql = f"[out:json][timeout:180];{pre}relation{flt}{sc}->.R;.R out tags;way(r.R);out geom;"
    data = run(ql, args.proxy, args.cache)
    rels = [e for e in data.get("elements", []) if e["type"] == "relation"]
    ways = [e for e in data.get("elements", []) if e["type"] == "way"]
    for rel in rels:
        t = rel.get("tags") or {}
        print(f"  线路 {t.get('ref', '')} {t.get('name', '')} {t.get('from', '')}→{t.get('to', '')}")
    pts = _sample(ways, args.step)
    print(f"{len(rels)} 条线路关系、{len(ways)} 段路，沿线每 {args.step:.0f} m 取点共 {len(pts)} 个")
    if pts:
        lats, lons = [p[0] for p in pts], [p[1] for p in pts]
        print(f"  线路范围 bbox: {min(lats):.4f},{min(lons):.4f},{max(lats):.4f},{max(lons):.4f}")
    return {f"R{i}": p for i, p in enumerate(pts)}


def cmd_intersect(args) -> dict:
    """两类线状要素的交叉点（铁路×输电线、河×公路…），可要求 B 在交点外侧有折角（转角塔、河湾）。"""
    pre, sc = _scope(args)
    ql = (f"[out:json][timeout:280];{pre}way{args.a}{sc}->.a;way{args.b}(around.a:30){sc}->.b;"
          f".a out geom tags;.b out geom tags;")
    data = run(ql, args.proxy, args.cache, timeout=280)
    A = [e for e in data.get("elements", []) if e.get("geometry") and _match(e, args.a)]
    B = [e for e in data.get("elements", []) if e.get("geometry") and e not in A]
    if not A or not B:
        print(f"A {len(A)} 条、B {len(B)} 条，凑不出交点（换范围或标签）")
        return {}
    lat0 = A[0]["geometry"][0]["lat"]
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110540

    def pr(g):
        return (g["lon"] * kx, g["lat"] * ky)

    cells: dict[tuple[int, int], list] = {}
    for el in A:
        pts = [pr(g) for g in el["geometry"]]
        for s0, s1 in zip(pts, pts[1:]):
            for c in {(int(s0[0] // 500), int(s0[1] // 500)), (int(s1[0] // 500), int(s1[1] // 500))}:
                cells.setdefault(c, []).append((s0, s1, el))

    def cross(p1, p2, p3, p4):
        d = (p2[0] - p1[0]) * (p4[1] - p3[1]) - (p2[1] - p1[1]) * (p4[0] - p3[0])
        if abs(d) < 1e-9:
            return None
        t = ((p3[0] - p1[0]) * (p4[1] - p3[1]) - (p3[1] - p1[1]) * (p4[0] - p3[0])) / d
        u = ((p3[0] - p1[0]) * (p2[1] - p1[1]) - (p3[1] - p1[1]) * (p2[0] - p1[0])) / d
        if 0 <= t <= 1 and 0 <= u <= 1:
            return (p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1]))
        return None

    def find_bend(el, hit):
        """B 在交点外 bend_within 范围内的第一个 ≥bend_min 的折角：返回 (距离m, 转角°) 或 None。"""
        if args.bend_min <= 0:
            return None
        lo, hi = _band(args.bend_within)
        pts = [pr(g) for g in el["geometry"]]
        k = min(range(len(pts)), key=lambda i: math.dist(pts[i], hit))
        for direction in (1, -1):
            d = 0.0
            i = k
            while 0 < i + direction < len(pts) - 1:
                nxt = i + direction
                d += math.dist(pts[i], pts[nxt])
                i = nxt
                if d > hi:
                    break
                if d < lo:
                    continue
                a1 = math.atan2(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
                a2 = math.atan2(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                turn = abs(math.degrees(a2 - a1))
                turn = min(turn % 360, 360 - turn % 360)
                if turn >= args.bend_min:
                    return round(d), round(turn)
        return None

    hits = []
    for el in B:
        pts = [pr(g) for g in el["geometry"]]
        for s0, s1 in zip(pts, pts[1:]):
            for c in {(int(s0[0] // 500), int(s0[1] // 500)), (int(s1[0] // 500), int(s1[1] // 500))}:
                for a0, a1, ael in cells.get(c, []):
                    x = cross(a0, a1, s0, s1)
                    if not x:
                        continue
                    ta, tb = ael.get("tags") or {}, el.get("tags") or {}
                    lbl = " ".join(filter(None, [ta.get("name", ""), tb.get("name", ""), tb.get("voltage", ""),
                                                 ta.get("electrified", "")]))
                    hits.append((lbl[:40], [x[1] / ky, x[0] / kx], {"bend": find_bend(el, x)}))
    groups = _cluster(hits, args.cluster)
    rows = []
    for g in groups:
        bends = [m[2]["bend"] for m in g["members"] if m[2]["bend"]]
        rows.append({"label": g["members"][0][0], "ll": [round(g["center"][0], 6), round(g["center"][1], 6)],
                     "bend": min(bends) if bends else None})
    if args.ring:
        c_ll, rmin, rmax = args.ring.split(":")
        c = tuple(map(float, c_ll.split(",")))
        before = len(rows)
        rows = [r for r in rows if float(rmin) <= _dist(c, r["ll"]) <= float(rmax)]
        print(f"--ring：离 {c_ll} {rmin}–{rmax} m 的环带内留下 {len(rows)}/{before} 处")
    print(f"A {len(A)} 条 × B {len(B)} 条 → {len(hits)} 个交点，合并成 {len(groups)} 簇")
    if args.bend_min > 0:
        with_bend = [r for r in rows if r["bend"]]
        print(f"  其中 {len(with_bend)} 处 B 在交点外 {args.bend_within} m 内有 ≥{args.bend_min:g}° 折角"
              f"（标\"折角\"；只作排序参考，见 --bend-filter）")
        if args.bend_filter:
            dropped = [r for r in rows if not r["bend"]]
            rows = with_bend
            print(f"  --bend-filter：丢掉 {len(dropped)} 处没有折角的交点。折角来自对画面的解读，"
                  f"候选全部没对上时先回头看被丢掉的这批")
            if args.out and dropped:
                dp = args.out.with_name(args.out.stem + "_dropped.json")
                dp.write_text(json.dumps({f"{i:03d} {r['label']}".strip(): r["ll"] for i, r in enumerate(dropped, 1)},
                                         ensure_ascii=False, indent=1), encoding="utf-8")
                print(f"  被丢掉的 -> {dp}")
    if args.rank_near:
        rows = _rank_rows(rows, args.rank_near, args)
    elif args.bend_min > 0:
        rows.sort(key=lambda r: r["bend"] is None)
    out = {}
    for i, r in enumerate(rows, 1):
        extra = []
        if r["bend"]:
            extra.append(f"折角{r['bend'][0]}m/{r['bend'][1]}°")
        if r.get("near_m") is not None:
            extra.append(f"距{r['near_name'][:6]}{r['near_m'] / 1000:.1f}km")
        out[f"{i:03d} {r['label']} {' '.join(extra)}".strip()] = r["ll"]
    return out



_SIDES = {"north": (0.0, 1.0), "south": (0.0, -1.0), "east": (1.0, 0.0), "west": (-1.0, 0.0)}


def cmd_along(args) -> dict:
    """沿任意线状要素（按 ref / 名字过滤的公路、河、输电线）每隔 step 米取点，可整体往路的某一侧偏移。
    给了 --bbox 时只留框内的点（Overpass 会把穿过框的整条路都返回）。

    给 tiles.py sheet（卫星缩略图扫路边的厂、店、田）、gsv.py / baidu_pano.py sheet --points（街景扫门脸）用。
    """
    pre, sc = _scope(args)
    data = run(f"[out:json][timeout:180];{pre}way{args.line}{sc};out geom;", args.proxy, args.cache)
    ways = [e for e in data.get("elements", []) if e["type"] == "way" and e.get("geometry")]
    side = _SIDES.get(args.side) if args.side else None
    pts, seen = {}, []
    for w in ways:
        g = [(n["lat"], n["lon"]) for n in w["geometry"]]
        acc = 0.0
        for a, b in zip(g, g[1:]):
            seg = _dist(a, b)
            if seg <= 0:
                continue
            kx = 111320 * math.cos(math.radians(a[0]))
            ux, uy = (b[1] - a[1]) * kx / seg, (b[0] - a[0]) * 110574 / seg  # 东、北方向的单位向量
            while acc <= seg:
                t = acc / seg
                lat, lon = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                if side and args.offset:
                    nx, ny = -uy, ux  # 左法线
                    if nx * side[0] + ny * side[1] < 0:
                        nx, ny = uy, -ux
                    lat += ny * args.offset / 110574
                    lon += nx * args.offset / kx
                ll = (round(lat, 6), round(lon, 6))
                inside = not args.bbox or (args.bbox[0] <= ll[0] <= args.bbox[2] and args.bbox[1] <= ll[1] <= args.bbox[3])
                if inside and not any(_dist(ll, s) < args.step * 0.5 for s in seen[-200:]):
                    seen.append(ll)
                    name = (w.get("tags") or {}).get("ref") or (w.get("tags") or {}).get("name") or f"w{w['id']}"
                    pts[f"{len(pts):04d} {name}"] = list(ll)
                acc += args.step
            acc -= seg
    print(f"{len(ways)} 段线，每 {args.step:.0f} m 取点共 {len(pts)} 个" + (f"，往{args.side}侧偏 {args.offset:.0f} m" if side else ""))
    if pts:
        lats, lons = [v[0] for v in pts.values()], [v[1] for v in pts.values()]
        print(f"  范围 bbox: {min(lats):.4f},{min(lons):.4f},{max(lats):.4f},{max(lons):.4f}")
    return pts


def _ring_area(coords: list[tuple[float, float]]) -> float:
    if len(coords) < 3:
        return 0.0
    lat0 = sum(c[0] for c in coords) / len(coords)
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
    xy = [(c[1] * kx, c[0] * ky) for c in coords]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))) / 2


def cmd_buildings(args) -> dict:
    """找占地大的建筑（厂房、仓库、农场棚、矿场设施）：按占地面积筛，标出周围有几栋别的建筑。

    OSM 在很多国家的乡间建筑轮廓来自卫星描图，没有名字也有面积；国内县乡建筑常常为空，不能当排除依据。
    "周围稀疏"只用来排序（--sort sparse），不当过滤：厂区自己常被拆成一堆小棚子。
    """
    pre, sc = _scope(args)
    flt = args.filter or '["building"]'
    data = run(f"[out:json][timeout:240];{pre}way{flt}{sc};out geom;", args.proxy, args.cache)
    rows = []
    for el in data.get("elements", []):
        g = [(n["lat"], n["lon"]) for n in el.get("geometry") or []]
        if len(g) < 4:
            continue
        area = _ring_area(g[:-1] if g[0] == g[-1] else g)
        c = (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))
        rows.append({"id": el["id"], "c": c, "area": area, "tags": el.get("tags") or {}})
    big = [r for r in rows if r["area"] >= args.min_area]
    cells: dict[tuple[int, int], list] = {}
    cs = args.within / 111000
    for r in rows:
        cells.setdefault((int(r["c"][0] / cs), int(r["c"][1] / cs)), []).append(r)
    for r in big:
        ci, cj = int(r["c"][0] / cs), int(r["c"][1] / cs)
        r["neighbors"] = sum(1 for di in (-1, 0, 1) for dj in (-1, 0, 1) for o in cells.get((ci + di, cj + dj), [])
                             if o is not r and _dist(r["c"], o["c"]) <= args.within)
    big.sort(key=(lambda r: (r["neighbors"], -r["area"])) if args.sort == "sparse" else (lambda r: -r["area"]))
    print(f"{len(rows)} 栋建筑，占地 ≥{args.min_area:.0f} m² 的 {len(big)} 栋（按{'周围稀疏' if args.sort == 'sparse' else '面积'}排序；邻=周围 {args.within:.0f} m 内其他建筑数）")
    pts = {}
    for i, r in enumerate(big, 1):
        t = r["tags"]
        kind = t.get("building", "")
        label = f"{i:03d} {int(r['area'])}m² 邻{r['neighbors']} {kind if kind != 'yes' else ''} {t.get('name', '')}"
        pts[" ".join(label.split())] = [round(r["c"][0], 6), round(r["c"][1], 6)]
    return pts


def cmd_coverage(args) -> dict:
    """各候选行政区里某类要素有几个。用 OSM 枚举候选之前先跑：数量明显偏少的区县不能靠 OSM 结果排除，要单独用卫星图网格扫。"""
    rows = []
    for name in [a for a in args.areas.split(",") if a]:
        ql = f'[out:json][timeout:120];area["name"="{name}"]->.a;.a out count;nwr{args.filter}(area.a);out count;'
        els = run(ql, args.proxy, args.cache).get("elements") or []
        counts = [int((e.get("tags") or {}).get("total", 0)) for e in els]
        rows.append((name, counts[1] if len(counts) > 1 and counts[0] > 0 else -1))
    top = max((n for _, n in rows), default=0)
    print(f"OSM 里 {args.filter} 的数量（只比同类行政区；数量少可能是真的少，也可能是没人画）：")
    for name, n in rows:
        if n < 0:
            flag = "  ← OSM 里没有叫这个名字的行政区，换写法（带不带\"区/县/市\"）"
        elif n < max(5, top * 0.25):
            flag = "  ← 偏少：不能用 OSM 结果排除这里，改用 tiles.py sheet --grid 扫"
        else:
            flag = ""
        print(f"  {name}: {'?' if n < 0 else n}{flag}")
    return {}


def _rank_rows(rows: list[dict], flt: str, args) -> list[dict]:
    """按"离最近的某类要素（城镇、服务区、车站…）多远"给候选排序，近的在前。只排序，不删。"""
    pre, sc = _scope(args)
    if args.bbox:                                         # bbox 边上的城镇也要算进来
        s, w, n, e = args.bbox
        sc = f"({s - 0.2},{w - 0.2},{n + 0.2},{e + 0.2})"
    data = run(f"[out:json][timeout:180];{pre}nwr{flt}{sc};out center tags;", args.proxy, args.cache)
    refs = []
    for el in data.get("elements", []):
        ll = _center(el)
        if ll and ll[0] is not None:
            refs.append(((el.get("tags") or {}).get("name", "?"), ll))
    if not refs:
        print(f"--rank-near {flt} 没查到要素，不排序")
        return rows
    for r in rows:
        name, ll = min(refs, key=lambda t: _dist(r["ll"], t[1]))
        r["near_m"], r["near_name"] = _dist(r["ll"], ll), name
    rows.sort(key=lambda r: r["near_m"])
    print(f"  已按离最近的 {flt}（{len(refs)} 个）排序，近的在前")
    return rows


def _match(el: dict, flt: str) -> bool:
    """粗略判断一个要素是否满足 A 的标签过滤（只看 key=value 形式的条件）。"""
    tags = el.get("tags") or {}
    for k, v in re.findall(r'\["([^"]+)"="([^"]+)"\]', flt):
        if tags.get(k) != v:
            return False
    for k in re.findall(r'\["([^"=\]]+)"\]', flt):
        if k not in tags:
            return False
    return True


def cmd_geom(args) -> dict:
    """任意过滤条件 → GeoJSON（线、面、点都保留几何），给自定义分析或叠图用。"""
    pre, sc = _scope(args)
    data = run(f"[out:json][timeout:180];{pre}nwr{args.filter}{sc};out geom tags;", args.proxy, args.cache)
    feats = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        if el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif el.get("geometry"):
            coords = [[g["lon"], g["lat"]] for g in el["geometry"]]
            closed = len(coords) > 3 and coords[0] == coords[-1]
            geom = {"type": "Polygon", "coordinates": [coords]} if closed and ("building" in tags or "area" in tags) \
                else {"type": "LineString", "coordinates": coords}
        else:
            continue
        feats.append({"type": "Feature", "id": f"{el['type']}/{el['id']}", "properties": tags, "geometry": geom})
    gj = {"type": "FeatureCollection", "features": feats}
    out = args.out or Path("osm_geom.geojson")
    out.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    print(f"{len(feats)} 个要素 -> {out}")
    args.out = None
    return {}


def _band(s: str) -> tuple[float, float]:
    a, b = s.split(":")
    return float(a), float(b)


def cmd_street_scan(args) -> dict:
    """街景几何模板：镜头站在路口（或路上），顺着一条街看过去，街两侧"有楼 / 没楼"的格局 → 全城候选点。"""
    if not args.bbox:
        sys.exit("street-scan 只支持 --bbox（一个城镇的范围，边长别超过 ~15 km）")
    s, w, n, e = args.bbox
    if (n - s) > 0.2 or (e - w) > 0.25:
        print("提示：范围很大，查询可能超时；按城镇分几次跑更稳", file=sys.stderr)
    excl = "footway|path|cycleway|steps|track|pedestrian|bridleway|corridor|platform|proposed|construction|elevator"
    ql = (f'[out:json][timeout:280];way["highway"]["highway"!~"^({excl})$"]({s},{w},{n},{e});out body geom;'
          f'way["building"]({s},{w},{n},{e});out body geom;')
    data = run(ql, args.proxy, args.cache, timeout=280)
    lat0, lon0 = (s + n) / 2, (w + e) / 2
    kx, ky = 111320 * math.cos(math.radians(lat0)), 110540

    def P(g):
        return ((g["lon"] - lon0) * kx, (g["lat"] - lat0) * ky)

    types = set(args.types.split(","))
    ways = [el for el in data.get("elements", []) if el["type"] == "way" and el.get("geometry")]
    hw = [el for el in ways if "highway" in (el.get("tags") or {})]
    bl = [el for el in ways if "building" in (el.get("tags") or {})]
    node_ways: dict[int, set] = {}
    for wy in hw:
        for nd in wy["nodes"]:
            node_ways.setdefault(nd, set()).add(wy["id"])
    grid: dict[tuple[int, int], list] = {}
    area: dict[int, float] = {}
    for b in bl:
        pts = [P(g) for g in b["geometry"]]
        area[b["id"]] = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:]))) / 2 if len(pts) > 2 else 0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            k = max(1, int(math.hypot(x2 - x1, y2 - y1) / 2))
            for i in range(k + 1):
                x, y = x1 + (x2 - x1) * i / k, y1 + (y2 - y1) * i / k
                grid.setdefault((int(x // 50), int(y // 50)), []).append((x, y, b["id"]))
    b_lo, b_hi = _band(args.bearing)
    near_lo, near_hi = _band(args.band)
    clr_lo, clr_hi = _band(args.clear)
    ah_lo, ah_hi = _band(args.ahead)
    reach = int(max(ah_hi, near_hi, clr_hi) // 50) + 2

    def bearing_ok(brg):
        return (b_lo <= brg <= b_hi) if b_lo <= b_hi else (brg >= b_lo or brg <= b_hi)

    def along(pts, dist):
        acc = 0.0
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if L > 0 and acc + L >= dist:
                f = (dist - acc) / L
                return (x1 + (x2 - x1) * f, y1 + (y2 - y1) * f)
            acc += L
        return None

    def side_ok(J, ux, uy, want, sign):
        if want == "any":
            return True
        nx, ny = uy * sign, -ux * sign            # sign=+1 右侧，-1 左侧
        cx, cy = int(J[0] // 50), int(J[1] // 50)
        hits = set()
        blocked = False
        for gx in range(cx - reach, cx + reach + 1):
            for gy in range(cy - reach, cy + reach + 1):
                for x, y, bid in grid.get((gx, gy), []):
                    t = (x - J[0]) * ux + (y - J[1]) * uy
                    lat_d = (x - J[0]) * nx + (y - J[1]) * ny
                    if ah_lo <= t <= ah_hi:
                        if near_lo <= lat_d <= near_hi and area.get(bid, 0) >= args.min_area:
                            hits.add(bid)
                        if clr_lo <= lat_d <= clr_hi:
                            blocked = True
        return bool(hits) if want == "building" else not blocked

    cands = {}
    for wy in hw:
        if wy["tags"]["highway"] not in types:
            continue
        g = [P(x) for x in wy["geometry"]]
        starts = []
        for end in (0, -1):
            if args.anywhere or len(node_ways.get(wy["nodes"][end], ())) >= 2:
                starts.append((g if end == 0 else g[::-1], "s" if end == 0 else "e", 0.0))
        if args.anywhere:
            total = sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(g, g[1:]))
            d = args.every
            while d < total - args.look:
                starts.append((g, f"m{int(d)}", d))
                d += args.every
        for pts, tag, off in starts:
            J = along(pts, off) if off else pts[0]
            p_far, p_mid = along(pts, off + args.look), along(pts, off + args.look / 2)
            if not J or not p_far or not p_mid:
                continue
            ux, uy = p_far[0] - J[0], p_far[1] - J[1]
            L = math.hypot(ux, uy)
            ux, uy = ux / L, uy / L
            brg = math.degrees(math.atan2(ux, uy)) % 360
            if not bearing_ok(brg):
                continue
            b_mid = math.degrees(math.atan2(p_mid[0] - J[0], p_mid[1] - J[1])) % 360
            if abs((b_mid - brg + 180) % 360 - 180) > 15:                    # 前半段要够直
                continue
            if side_ok(J, ux, uy, args.right, +1) and side_ok(J, ux, uy, args.left, -1):
                name = (wy.get("tags") or {}).get("name", "")
                key = f"{len(cands) + 1:03d} {name[:20]} 朝{brg:.0f}° way{wy['id']}{tag}".strip()
                cands[key] = [round(J[1] / ky + lat0, 6), round(J[0] / kx + lon0, 6)]
    print(f"道路 {len(hw)} 条、建筑 {len(bl)} 栋 → 候选 {len(cands)} 个（点位 = 镜头所在的路口/路上位置）")
    return cands



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache/osm"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def scope(sp):
        sp.add_argument("--proxy", default=argparse.SUPPRESS, help="子命令后面写也行")
        sp.add_argument("--cache", type=Path, default=argparse.SUPPRESS)
        sp.add_argument("--bbox", type=lambda s: tuple(map(float, s.split(","))), help="south,west,north,east")
        sp.add_argument("--area", help='OSM 行政区名，如 "Bayern"、"江苏省"、"深圳市"')
        sp.add_argument("--out", type=Path, help="写出 {name:[lat,lon]}")
        sp.add_argument("--limit", type=int, default=30, help="终端最多打印几条")

    f = sub.add_parser("find")
    f.add_argument("filter", help='Overpass 标签过滤，如 \'["amenity"="fuel"]\'')
    scope(f)

    n = sub.add_parser("near")
    n.add_argument("--a", required=True, help="要找的主体")
    n.add_argument("--b", required=True, help="主体附近必须有的要素")
    n.add_argument("--within", type=float, default=200, help="B 离 A 的最大距离（米）")
    n.add_argument("--c", help="可选：第三个必须有的要素")
    n.add_argument("--within-c", type=float, default=200)
    n.add_argument("--report", type=Path, help="写出逐个 A 的 B/C 实际距离和关键标签（JSON），用来排序")
    n.add_argument("--rank-near", help='按离最近的某类要素排序，如 \'["place"~"^(city|town)$"]\'（只排序不删）')
    scope(n)

    c = sub.add_parser("crossings")
    c.add_argument("--line", required=True, help='线状要素标签，如 \'["waterway"="river"]["name"="长江"]\'、\'["railway"="rail"]\'')
    c.add_argument("--kind", default="bridge,dam,ferry", help="bridge,dam,ferry,level_crossing，逗号分隔")
    c.add_argument("--buffer", type=float, default=40, help="离线状要素多少米内算在线上")
    scope(c)

    ro = sub.add_parser("route")
    ro.add_argument("--kind", default="bus", help="bus / trolleybus / tram / subway / train / light_rail / ferry")
    ro.add_argument("--ref", help="线路号，如 79")
    ro.add_argument("--name", help="线路名的正则片段")
    ro.add_argument("--step", type=float, default=200, help="沿线每隔多少米取一个点")
    scope(ro)

    r = sub.add_parser("raw")
    r.add_argument("file", type=Path, help="Overpass QL 文件")
    scope(r)

    it = sub.add_parser("intersect")
    it.add_argument("--a", required=True, help='第一类线，如 \'["railway"="rail"]["electrified"="contact_line"]\'')
    it.add_argument("--b", required=True, help='第二类线，如 \'["power"="line"]\'')
    it.add_argument("--bend-min", type=float, default=0,
                    help="标出 B 在交点外有 ≥这么多度折角（转角塔/河湾）的交点，并排在前面；0=不看折角。默认只标注不删")
    it.add_argument("--bend-within", default="100:1000", help="折角离交点的距离范围 m")
    it.add_argument("--bend-filter", action="store_true",
                    help="真的删掉没有折角的交点（被删的写到 <out>_dropped.json）。只在折角是画面里亲眼确认的事实时用")
    it.add_argument("--rank-near", help='按离最近的某类要素排序，如 \'["place"~"^(city|town)$"]\'、\'["highway"="services"]\'')
    it.add_argument("--ring", help="lat,lon:最小m:最大m —— 只留离某点这个距离环带里的交点（如按地标像素大小算出的距离区间）")
    it.add_argument("--cluster", type=float, default=100, help="多少米内的交点合成一处")
    scope(it)

    cv = sub.add_parser("coverage", help="各候选行政区里某类要素有几个：枚举前先查 OSM 覆盖，空白区不能当排除")
    cv.add_argument("--areas", required=True, help='逗号分隔的 OSM 行政区名，如 "某某区,某某县"')
    cv.add_argument("--filter", required=True, help='要素过滤，如 \'["leisure"~"^(pitch|track)$"]\'、\'["building"]\'')
    cv.add_argument("--proxy", default=argparse.SUPPRESS)
    cv.add_argument("--cache", type=Path, default=argparse.SUPPRESS)

    al = sub.add_parser("along", help="沿公路/河/输电线按步长取点（可往一侧偏移），给卫星缩略图或街景扫路边")
    al.add_argument("--line", required=True, help='线状要素过滤，如 \'["highway"]["ref"="<道路编号>"]\'、\'["highway"]["name"~"<路名片段>"]\'')
    al.add_argument("--step", type=float, default=150, help="每隔多少米取一个点；街景找门脸 ≤150，卫星缩略图可 300–500")
    al.add_argument("--side", choices=list(_SIDES), help="往路的哪一侧偏移（按罗盘方向）")
    al.add_argument("--offset", type=float, default=0, help="偏移米数，看路一侧的厂房时取建筑到路的距离")
    scope(al)

    bu = sub.add_parser("buildings", help="按占地面积找大建筑（厂房、仓库、农场棚），标出周围稀疏程度")
    bu.add_argument("--min-area", type=float, default=1000, help="最小占地 m²")
    bu.add_argument("--within", type=float, default=200, help="数周围建筑用的半径 m")
    bu.add_argument("--sort", choices=["area", "sparse"], default="area", help="sparse：周围建筑少的排前面（乡间孤立的厂房），只排序不删")
    bu.add_argument("--filter", help='建筑过滤，默认 \'["building"]\'，如 \'["building"~"industrial|warehouse|farm_auxiliary"]\'')
    scope(bu)

    gm = sub.add_parser("geom")
    gm.add_argument("filter", help='标签过滤，如 \'["building"]\'、\'["highway"]\'')
    scope(gm)

    ss = sub.add_parser("street-scan")
    ss.add_argument("--bearing", required=True, help="镜头顺着看的那条街的方位范围，如 320:80（可跨北）")
    ss.add_argument("--right", choices=["building", "empty", "any"], default="any", help="街的右侧")
    ss.add_argument("--left", choices=["building", "empty", "any"], default="any", help="街的左侧")
    ss.add_argument("--band", default="4:22", help="'有楼'的判定带：离街中线的横向距离 m")
    ss.add_argument("--clear", default="3:10", help="'没楼'的判定带：这个横向范围里不能有楼 m")
    ss.add_argument("--ahead", default="0:40", help="沿街往前看多远 m")
    ss.add_argument("--min-area", type=float, default=150, help="'有楼'要求的最小占地面积 m²")
    ss.add_argument("--look", type=float, default=60, help="用前多少米算街的方位")
    ss.add_argument("--types", default="residential,unclassified,living_street,tertiary,secondary,service")
    ss.add_argument("--anywhere", action="store_true", help="镜头不一定在路口：沿街每隔 --every 米都试")
    ss.add_argument("--every", type=float, default=30)
    scope(ss)

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "crossings":
        pts = cmd_crossings(args)
    elif args.cmd == "route":
        pts = cmd_route(args)
    elif args.cmd == "intersect":
        pts = cmd_intersect(args)
    elif args.cmd == "geom":
        pts = cmd_geom(args)
    elif args.cmd == "coverage":
        cmd_coverage(args)
        return
    elif args.cmd == "along":
        pts = cmd_along(args)
    elif args.cmd == "buildings":
        pts = cmd_buildings(args)
    elif args.cmd == "street-scan":
        pts = cmd_street_scan(args)
    else:
        if args.cmd == "raw":
            ql = args.file.read_text(encoding="utf-8")
            if args.bbox:
                ql = ql.replace("{{bbox}}", ",".join(map(str, args.bbox)))
        else:
            pre, sc = _scope(args)
            if args.cmd == "find":
                ql = f"[out:json][timeout:180];{pre}nwr{args.filter}{sc};out center tags;"
            else:
                ql = f"[out:json][timeout:180];{pre}nwr{args.b}{sc}->.b;nwr{args.a}(around.b:{args.within:.0f}){sc}->.a;"
                if args.c:
                    ql += f"nwr{args.c}{sc}->.c;nwr.a(around.c:{args.within_c:.0f})->.a;"
                ql += ".a out center tags;"
        pts = _points(run(ql, args.proxy, args.cache))
        print(f"{len(pts)} 个结果")
        if not pts:
            print("  0 个不等于没有：这一片 OSM 可能根本没画（国内县乡常见），不能当排除依据；先 osm.py coverage 比一比，或改用 tiles.py sheet --grid")
        if args.cmd == "near" and args.rank_near and pts:
            rows = _rank_rows([{"label": k, "ll": v, "bend": None} for k, v in pts.items()], args.rank_near, args)
            pts = {f"{r['label']} 距{r['near_name'][:6]}{r['near_m'] / 1000:.1f}km" if r.get("near_m") is not None
                   else r["label"]: r["ll"] for r in rows}
        if args.cmd == "near" and args.report and pts:
            pre2, sc2 = _scope(args)
            rep = {}
            a_ids = f"nwr{args.b}{sc2}->.b;nwr{args.a}(around.b:{args.within:.0f}){sc2}->.a;"
            if args.c:
                a_ids += f"nwr{args.c}{sc2}->.c;nwr.a(around.c:{args.within_c:.0f})->.a;"
            q2 = (f"[out:json][timeout:200];{pre2}{a_ids}.a out center tags;"
                  f"nwr{args.b}(around.a:{args.within:.0f}){sc2};out geom tags;")
            if args.c:
                q2 += f"nwr{args.c}(around.a:{args.within_c:.0f}){sc2};out geom tags;"
            d2 = run(q2, args.proxy, args.cache)
            others = [e for e in d2.get("elements", []) if e.get("geometry") or e["type"] == "node"]
            for name, ll in pts.items():
                near_list = []
                for el in others:
                    geom = el.get("geometry") or ([{"lat": el["lat"], "lon": el["lon"]}] if el["type"] == "node" else [])
                    if not geom:
                        continue
                    dmin = min(_dist(ll, (g["lat"], g["lon"])) for g in geom)
                    t = el.get("tags") or {}
                    keep = {k2: v for k2, v in t.items() if k2 in
                            ("name", "voltage", "electrified", "highspeed", "railway", "power", "waterway", "highway", "tracks")}
                    near_list.append({"dist_m": round(dmin), "tags": keep})
                near_list.sort(key=lambda x: x["dist_m"])
                rep[name] = {"ll": ll, "nearest": near_list[:4]}
            args.report.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"报告 -> {args.report}")
    for k, (name, ll) in enumerate(pts.items()):
        if k >= args.limit:
            print("  …")
            break
        print(f"  {name}  {ll[0]},{ll[1]}")
    if args.out:
        args.out.write_text(json.dumps(pts, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
