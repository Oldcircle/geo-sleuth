#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""地名、小区名、楼盘名、店名 → 坐标候选（免 key）。

以图搜图常给出"图中可能是 XX花园""XX大厦"，网页里读到一个小区名、酒店名，都要先落到坐标才能核对。
同名的地方全国常有几十个，脚本把各地的同名点都列出来，由画面里的其他线索去挑。

来源：
  so    360 地图搜索（直连）：小区、楼盘、店铺、单位覆盖好，带地址；原始坐标 GCJ-02，已转成 WGS84
  osm   OpenStreetMap Nominatim（走代理）：有名字的小区、公园、道路；坐标 WGS84
  sug   百度地图搜索联想（直连）：只有"城市 + 区县 + 名字"，没有坐标；用来看全国哪些区县有这个名字

示例：
  poi.py "<小区名>" --city <城市>                 # 城市里所有同名点，出 {名字: [lat, lon]}
  poi.py "<区县> <路名> 学校" --city <直辖市或地级市>   # --city 只认地级市，区县写进关键词
  poi.py "<门牌地址或地名>" --sources osm --country mx --proxy socks5h://127.0.0.1:10808（示例）   # 国外
  poi.py "<小区名>"                                # 不给城市：列出全国哪些城市有同名点
  poi.py "<酒店名>" --city <城市> --out pois.json && tiles.py sheet --points pois.json --zoom 18 --out pois_sheet.jpg

百度地图网页的地点搜索会要验证码，脚本不用；腾讯、高德接口要 key，也不用。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _curl(url: str, proxy: str | None = None, ua: str = UA, timeout: int = 25) -> str:
    cmd = ["curl", "-sS", "-m", str(timeout), "-A", ua, url]
    cmd[1:1] = ["-x", proxy] if proxy else ["--noproxy", "*"]
    # 网页是 UTF-8。不写 encoding 的话中文 Windows 按 GBK 解码，解不开时 stdout 是 None
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"请求没成功（curl 退出码 {r.returncode}）：{r.stderr.strip()[:200]}", file=sys.stderr)
    return r.stdout


def search_so(kw: str, city: str | None, n: int) -> tuple[list[dict], list[dict]]:
    q = {"keyword": kw, "batch": 1, "number": n, "ext": 1, "sid": 1000}
    if city:
        q["cityname"] = city
    raw = _curl("https://restapi.map.so.com/newapi?" + urllib.parse.urlencode(q))
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        print(f"360 地图没返回 JSON：{raw[:120]}", file=sys.stderr)
        return [], []
    rows = []
    for p in d.get("poi") or []:
        if not p.get("x") or not p.get("y"):
            continue
        lat, lon = geo.gcj2wgs(float(p["y"]), float(p["x"]))
        rows.append({"src": "so", "name": p.get("name", ""), "city": p.get("city", ""), "area": p.get("area", ""),
                     "address": p.get("address", ""), "type": p.get("cat_new_name") or p.get("type", ""),
                     "wgs": [round(lat, 6), round(lon, 6)]})
    cities = [{"city": c.get("name"), "province": c.get("province"), "count": c.get("resultnum")}
              for c in d.get("citysuggestion") or []]
    return rows, cities


def search_osm(kw: str, city: str | None, n: int, proxy: str | None, country: str) -> list[dict]:
    q = {"q": f"{kw} {city}" if city else kw, "format": "jsonv2", "limit": n, "accept-language": "zh-CN"}
    if country:
        q["countrycodes"] = country
    raw = _curl("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(q), proxy=proxy,
                ua="geo-sleuth/1.0 (photo geolocation research)")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        print(f"Nominatim 没返回 JSON（国内要走代理）：{raw[:120]}", file=sys.stderr)
        return []
    return [{"src": "osm", "name": p.get("name") or p.get("display_name", "").split(",")[0],
             "city": "", "area": "", "address": p.get("display_name", ""), "type": f"{p.get('category')}/{p.get('type')}",
             "wgs": [round(float(p["lat"]), 6), round(float(p["lon"]), 6)]} for p in d]


def search_sug(kw: str) -> list[dict]:
    raw = _curl("https://map.baidu.com/su?" + urllib.parse.urlencode({"wd": kw, "cid": 1, "type": 0, "newmap": 1, "ie": "utf-8"}))
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out = []
    for s in d.get("s") or []:
        parts = s.split("$")
        if len(parts) >= 4:
            out.append({"src": "sug", "city": parts[0], "area": parts[1], "name": parts[3]})
    return out



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keyword", help="地名、小区名、楼盘名、店名")
    ap.add_argument("--city", help="城市名，如 某某市 或 某某（不给就全国查）")
    ap.add_argument("--sources", default="so,osm,sug", help="so,osm,sug 任选，逗号分隔")
    ap.add_argument("--limit", type=int, default=10, help="每个来源最多几条")
    ap.add_argument("--country", default="cn", help="Nominatim 的国家代码，国外地名改成对应代码或留空")
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"), help="Nominatim 用；360 和百度联想始终直连")
    ap.add_argument("--out", type=Path, help="写出 {名字: [lat, lon]}（WGS84），给 tiles.py mark / sheet")
    args = ap.parse_args(_neg_coords(sys.argv[1:]))

    src = set(args.sources.split(","))
    rows: list[dict] = []
    if "so" in src:
        so_rows, cities = search_so(args.keyword, args.city, args.limit)
        if args.city and so_rows and not any(args.city in (r["city"] + r["area"] + r["address"]) for r in so_rows):
            print(f"注意：360 地图的结果里没有一条在\"{args.city}\"——它不认这个城市名，悄悄换成了别的城市。"
                  f"--city 填地级市或直辖市（如 重庆），区县名写进关键词（如 \"<区县> <名字>\"）")
        rows += so_rows
        if cities and not args.city:
            print("360 地图：全国有同名结果的城市（结果数）")
            print("  " + "、".join(f"{c['city']}({c['count']})" for c in cities[:30]))
    if "osm" in src:
        rows += search_osm(args.keyword, args.city, args.limit, args.proxy, args.country)
    if "sug" in src:
        sug = search_sug(args.keyword)
        if sug:
            print("百度联想（无坐标，只看哪些区县有这个名字）：")
            print("  " + "；".join(f"{s['city']}{s['area']} {s['name']}" for s in sug[:15]))

    # 同一个地方两个来源都有时去重（相距 150 m 内且名字互相包含）
    uniq: list[dict] = []
    for r in rows:
        if any(geo.distance(r["wgs"], u["wgs"]) < 150 and (r["name"] in u["name"] or u["name"] in r["name"]) for u in uniq):
            continue
        uniq.append(r)
    print(f"\n{len(uniq)} 个带坐标的候选（WGS84）：")
    pts = {}
    for i, r in enumerate(uniq, 1):
        label = f"{i:02d} {r['name']} {r['area']}".strip()
        pts[label] = r["wgs"]
        print(f"  {label}  {r['wgs'][0]},{r['wgs'][1]}  [{r['src']}] {r['type']}  {r['address'][:60]}")
    if not uniq:
        print("  没有。换写法（去掉\"小区/花园\"后缀、加区县名），或用 revimg.py --query 搜网页找地址")
    if args.out:
        args.out.write_text(json.dumps(pts, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.out}")
    if len(uniq) >= 2:
        # 同一所学校的几个校区、连锁店的几家分店都会列在这里，第一条不一定是对的那处
        print(f"\n{len(uniq)} 处都要当候选，不要只取第一条："
              + (f"`board.py add --from {args.out} --level area --parent <上级>` 全部进候选盘" if args.out
                 else "加 --out pois.json，再 `board.py add --from pois.json --level area` 全部进候选盘"))


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
