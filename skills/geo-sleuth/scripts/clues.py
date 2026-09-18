#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""查表类线索：车牌、固话区号、国家电话码、行驶方向、海外领地、行政区。表是本地 JSON（data/），查询不联网。

  lookup plate 渝G              车牌前两位 → 省 + 地级市/区县（发牌机关代号，来源维基百科；直辖市字母分区来自常识表，标 unverified）
  lookup plate-prefix 渝        省简称 → 省
  lookup area-code 0817         固话区号 → 省 + 市（也接受 "0817-1234567"、"(0817) 123"）
  lookup calling-code +594      国际电话码 → 国家/地区
  lookup driving-side left      靠左行驶的国家；`driving-side --country 日本` → left
  lookup territories 法国       海外领地/属地列表；`--continent 南美洲` 只列该洲
  lookup admin 渝北区            上级链；`admin --children 重庆市` 下级列表
  list                          各表条数、来源、抓取日期
  update [表名|all]             重新抓取（走 --proxy）；`--from-dir` 用已下载的 HTML

--json 输出统一契约（给 board.py apply 用）：
  {"kind": "...", "value": "...", "matches": [{"admin1": "...", "admin2": "...", "note": "..."}], "source": "...", "table_fetched": "..."}
  国家级：matches 里是 {"country": "...", "continent": "...", "subregion": "...", "note": "..."}

示例：
  clues.py lookup plate 粤B
  clues.py lookup area-code 023 --json
  clues.py lookup territories France --continent 南美洲
  clues.py update all --proxy socks5h://127.0.0.1:10808（示例）
"""
from __future__ import annotations

import argparse
import html as H
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

SOURCES = {
    "cn_plates": ["https://zh.wikipedia.org/zh-cn/中华人民共和国民用机动车号牌"],
    "cn_area_codes": ["https://zh.wikipedia.org/zh-cn/中国大陆固定电话号码"],
    "calling_codes": ["https://en.wikipedia.org/wiki/List_of_telephone_country_codes"],
    "driving_side": ["https://en.wikipedia.org/wiki/Left-_and_right-hand_traffic"],
    "territories": ["https://en.wikipedia.org/wiki/List_of_dependent_territories"],
    "cn_admin": ["https://raw.githubusercontent.com/modood/Administrative-divisions-of-China/master/dist/pca-code.json"],
}
LOCAL_NAMES = {"cn_plates": "plates_zh.html", "cn_area_codes": "areacodes2_zh.html", "calling_codes": "calling_en.html",
               "driving_side": "driving_en.html", "territories": "dependent_en.html", "cn_admin": "pca-code.json"}

# 国家中英别名（只放常用的；查不到时用英文名再试）
COUNTRY_ZH = {
    "中国": "China", "日本": "Japan", "英国": "United Kingdom", "法国": "France", "美国": "United States", "澳大利亚": "Australia",
    "香港": "Hong Kong", "澳门": "Macau", "美属维尔京群岛": "U.S. Virgin Islands", "直布罗陀": "Gibraltar", "百慕大": "Bermuda", "开曼群岛": "Cayman Islands", "新喀里多尼亚": "New Caledonia", "法属波利尼西亚": "French Polynesia", "马约特": "Mayotte", "加那利群岛": "Canary Islands", "印度": "India", "泰国": "Thailand", "印尼": "Indonesia", "印度尼西亚": "Indonesia",
    "马来西亚": "Malaysia", "新加坡": "Singapore", "新西兰": "New Zealand", "南非": "South Africa", "巴西": "Brazil", "墨西哥": "Mexico",
    "德国": "Germany", "意大利": "Italy", "西班牙": "Spain", "俄罗斯": "Russia", "韩国": "South Korea", "越南": "Vietnam",
    "菲律宾": "Philippines", "巴基斯坦": "Pakistan", "孟加拉国": "Bangladesh", "斯里兰卡": "Sri Lanka", "尼泊尔": "Nepal", "肯尼亚": "Kenya",
    "爱尔兰": "Ireland", "加拿大": "Canada", "法属圭亚那": "French Guiana", "荷兰": "Netherlands", "葡萄牙": "Portugal", "丹麦": "Denmark",
    "挪威": "Norway", "瑞典": "Sweden", "芬兰": "Finland", "阿根廷": "Argentina", "智利": "Chile", "秘鲁": "Peru", "哥伦比亚": "Colombia",
    "埃及": "Egypt", "土耳其": "Turkey", "伊朗": "Iran", "沙特阿拉伯": "Saudi Arabia", "阿联酋": "United Arab Emirates", "以色列": "Israel",
    "缅甸": "Myanmar", "柬埔寨": "Cambodia", "老挝": "Laos", "蒙古": "Mongolia", "朝鲜": "North Korea", "台湾": "Taiwan", "瑞士": "Switzerland",
    "奥地利": "Austria", "比利时": "Belgium", "波兰": "Poland", "捷克": "Czech Republic", "希腊": "Greece", "乌克兰": "Ukraine",
    "哈萨克斯坦": "Kazakhstan", "摩洛哥": "Morocco", "尼日利亚": "Nigeria", "埃塞俄比亚": "Ethiopia", "坦桑尼亚": "Tanzania", "乌干达": "Uganda",
    "莫桑比克": "Mozambique", "纳米比亚": "Namibia", "津巴布韦": "Zimbabwe", "赞比亚": "Zambia", "马耳他": "Malta", "塞浦路斯": "Cyprus",
    "冰岛": "Iceland", "古巴": "Cuba", "牙买加": "Jamaica", "巴哈马": "Bahamas", "圭亚那": "Guyana", "苏里南": "Suriname",
    "巴布亚新几内亚": "Papua New Guinea", "斐济": "Fiji", "萨摩亚": "Samoa", "汤加": "Tonga", "阿尔及利亚": "Algeria", "突尼斯": "Tunisia",
    "塞内加尔": "Senegal", "科特迪瓦": "Ivory Coast", "加纳": "Ghana", "喀麦隆": "Cameroon", "马达加斯加": "Madagascar", "毛里求斯": "Mauritius",
    "留尼汪": "Réunion", "马提尼克": "Martinique", "瓜德罗普": "Guadeloupe", "波多黎各": "Puerto Rico", "关岛": "Guam", "格陵兰": "Greenland",
}
CONTINENT_ZH = {"亚洲": ["Asia"], "欧洲": ["Europe"], "非洲": ["Africa"], "大洋洲": ["Oceania"], "北美洲": ["Northern America", "North America"],
                "南美洲": ["South America"], "美洲": ["Americas"], "加勒比": ["Caribbean"], "中美洲": ["Central America"], "南极洲": ["Antarctica"]}
# 直辖市字母分区：来源为原地区行署划分的常识，维基页面只写到“重庆市”。标 unverified，用前核实。
MUNICIPAL_LETTER_NOTES = {
    "渝": {"A": "主城区", "B": "主城区", "C": "永川、江津、合川、璧山、铜梁、大足、荣昌、潼南（原永川地区）", "D": "主城区（后增）",
          "F": "万州、开州、梁平、忠县、云阳、奉节、巫山、巫溪、城口（原万县地区）", "G": "涪陵、南川、垫江、丰都、武隆（原涪陵地区）",
          "H": "黔江、石柱、秀山、酉阳、彭水（原黔江地区）"},
}

# 维基“属地列表”不收本土一体化的海外领土（法国海外省、西班牙加那利、美国夏威夷…），但它们正是“IP 国家 × 提示大洲”要找的交集，这里补上。
# 来源：Wikipedia Overseas France / Outermost regions of the EU / 各国条目；region/subregion 按联合国地理方案。
INTEGRAL_OVERSEAS = [
    {"name": "French Guiana", "sovereign": "France", "region": "Americas", "subregion": "South America", "status": "Overseas department and region (integral part of France, EU)"},
    {"name": "Guadeloupe", "sovereign": "France", "region": "Americas", "subregion": "Caribbean", "status": "Overseas department and region"},
    {"name": "Martinique", "sovereign": "France", "region": "Americas", "subregion": "Caribbean", "status": "Overseas department and region"},
    {"name": "Réunion", "sovereign": "France", "region": "Africa", "subregion": "Eastern Africa", "status": "Overseas department and region"},
    {"name": "Mayotte", "sovereign": "France", "region": "Africa", "subregion": "Eastern Africa", "status": "Overseas department and region"},
    {"name": "Saint Martin", "sovereign": "France", "region": "Americas", "subregion": "Caribbean", "status": "Overseas collectivity"},
    {"name": "Saint Barthélemy", "sovereign": "France", "region": "Americas", "subregion": "Caribbean", "status": "Overseas collectivity"},
    {"name": "Saint Pierre and Miquelon", "sovereign": "France", "region": "Americas", "subregion": "Northern America", "status": "Overseas collectivity"},
    {"name": "French Polynesia", "sovereign": "France", "region": "Oceania", "subregion": "Polynesia", "status": "Overseas collectivity"},
    {"name": "New Caledonia", "sovereign": "France", "region": "Oceania", "subregion": "Melanesia", "status": "Sui generis collectivity"},
    {"name": "Wallis and Futuna", "sovereign": "France", "region": "Oceania", "subregion": "Polynesia", "status": "Overseas collectivity"},
    {"name": "Canary Islands", "sovereign": "Spain", "region": "Africa", "subregion": "Northern Africa (Atlantic)", "status": "Autonomous community (integral part of Spain)"},
    {"name": "Ceuta", "sovereign": "Spain", "region": "Africa", "subregion": "Northern Africa", "status": "Autonomous city (integral part of Spain)"},
    {"name": "Melilla", "sovereign": "Spain", "region": "Africa", "subregion": "Northern Africa", "status": "Autonomous city (integral part of Spain)"},
    {"name": "Azores", "sovereign": "Portugal", "region": "Europe", "subregion": "Southern Europe (Atlantic)", "status": "Autonomous region (integral part of Portugal)"},
    {"name": "Madeira", "sovereign": "Portugal", "region": "Europe", "subregion": "Southern Europe (Atlantic, off Africa)", "status": "Autonomous region (integral part of Portugal)"},
    {"name": "Hawaii", "sovereign": "United States", "region": "Oceania", "subregion": "Polynesia", "status": "State (integral part of the US)"},
    {"name": "Alaska", "sovereign": "United States", "region": "Americas", "subregion": "Northern America", "status": "State (integral part of the US)"},
    {"name": "Bonaire", "sovereign": "Netherlands", "region": "Americas", "subregion": "Caribbean", "status": "Special municipality (integral part of the Netherlands)"},
    {"name": "Sint Eustatius", "sovereign": "Netherlands", "region": "Americas", "subregion": "Caribbean", "status": "Special municipality"},
    {"name": "Saba", "sovereign": "Netherlands", "region": "Americas", "subregion": "Caribbean", "status": "Special municipality"},
    {"name": "Svalbard", "sovereign": "Norway", "region": "Europe", "subregion": "Northern Europe (Arctic)", "status": "Unincorporated area (integral part of Norway)"},
    {"name": "Easter Island", "sovereign": "Chile", "region": "Oceania", "subregion": "Polynesia", "status": "Special territory (integral part of Chile)"},
    {"name": "Galápagos Islands", "sovereign": "Ecuador", "region": "Americas", "subregion": "South America (Pacific)", "status": "Province (integral part of Ecuador)"},
    {"name": "Andaman and Nicobar Islands", "sovereign": "India", "region": "Asia", "subregion": "Southern Asia (Bay of Bengal)", "status": "Union territory (integral part of India)"},
    {"name": "Kaliningrad Oblast", "sovereign": "Russia", "region": "Europe", "subregion": "Eastern Europe (exclave on the Baltic)", "status": "Oblast (integral part of Russia)"},
    {"name": "Okinawa", "sovereign": "Japan", "region": "Asia", "subregion": "Eastern Asia", "status": "Prefecture (integral part of Japan)"},
]


# ---------------------------------------------------------------- HTML 表解析（处理 rowspan/colspan）

def _clean(c: str) -> str:
    c = re.sub(r"<sup[^>]*>.*?</sup>", "", c, flags=re.S)
    c = re.sub(r"<br\s*/?>", " | ", c)
    c = H.unescape(re.sub(r"<[^>]+>", "", c))
    c = re.sub(r"\[[^\]]*\]", "", c)
    return re.sub(r"\s+", " ", c).strip()


def _tables(html: str) -> list[list[list[str]]]:
    out = []
    for t in re.findall(r"<table[^>]*>(.*?)</table>", html, re.S):
        rows, pending = [], {}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            cells = re.findall(r"<t([dh])([^>]*)>(.*?)</t[dh]>", tr, re.S)
            row, col, k = [], 0, 0
            while k < len(cells) or col in pending:
                if col in pending:
                    text, left = pending[col]
                    row.append(text)
                    if left <= 1:
                        del pending[col]
                    else:
                        pending[col] = (text, left - 1)
                    col += 1
                    continue
                _, attrs, body = cells[k]
                k += 1
                text = _clean(body)
                rs = re.search(r'rowspan="?(\d+)', attrs)
                cs = re.search(r'colspan="?(\d+)', attrs)
                n = int(cs.group(1)) if cs else 1
                for _ in range(n):
                    row.append(text)
                    if rs and int(rs.group(1)) > 1:
                        pending[col] = (text, int(rs.group(1)) - 1)
                    col += 1
            rows.append(row)
        out.append(rows)
    return out


def _sections_h3(html: str) -> list[tuple[str, str]]:
    parts = re.split(r"<h3[^>]*>", html)
    secs = []
    for part in parts[1:]:
        if "</h3>" not in part:
            continue
        title, body = part.split("</h3>", 1)
        secs.append((_clean(title), body.split("<h2", 1)[0]))
    return secs


# ---------------------------------------------------------------- 各表解析

def parse_cn_plates(html: str) -> dict:
    out = {}
    for title, body in _sections_h3(html):
        m = re.match(r"^(.+?)（(.)）$", title)
        if not m:
            continue
        prov, abbr = m.group(1), m.group(2)
        letters = {}
        for li in re.findall(r"<li[^>]*>(.*?)</li>", body, re.S):
            text = _clean(li)
            text = re.split(r"[。；;]", text)[0]
            text = re.sub(r"^(参见：.*?)(?=[A-Z](?:[/、，,]|\s))", "", text)
            text = re.sub(r"^(汽车|小型汽车|大型汽车)\s*", "", text)
            if "摩托车" in text or "拖拉机" in text:
                continue
            mm = re.match(r"^([A-Z](?:\s*[/、，,–\-~～至]\s*[A-Z])*)\s*[：:]?\s*(.+)$", text)
            if not mm:
                continue
            place = mm.group(2).strip()
            spec = mm.group(1)
            Ls: list[str] = []
            for seg in re.split(r"[/、，,]", spec):
                seg = seg.strip()
                r = re.match(r"^([A-Z])\s*[–\-~～至]\s*([A-Z])$", seg)
                if r:
                    Ls += [chr(c) for c in range(ord(r.group(1)), ord(r.group(2)) + 1) if chr(c) not in "IO"]
                elif seg:
                    Ls.append(seg)
            for L in Ls:
                letters[L] = place
        if letters:
            out[abbr] = {"province": prov, "letters": letters}
    for abbr, notes in MUNICIPAL_LETTER_NOTES.items():
        if abbr in out:
            out[abbr]["letter_notes_unverified"] = notes
    return out


def parse_cn_area_codes(html: str) -> dict:
    out = {}
    for t in _tables(html):
        if not t or not t[0] or t[0][0] != "区号":
            continue
        for row in t[1:]:
            if len(row) < 3 or not re.match(r"^\d{2,4}$", row[0]):
                continue
            code = "0" + row[0]
            entry = {"admin1": row[1], "admin2": [x.strip() for x in row[2].split("|") if x.strip()],
                     "digits": row[3] if len(row) > 3 else "", "note": row[4] if len(row) > 4 else ""}
            if entry["digits"] == "/" or "弃用" in entry["note"]:
                entry["deprecated"] = True
            out[code] = entry
    return out


def parse_calling_codes(html: str) -> dict:
    out = {}
    for t in _tables(html):
        if len(t) < 50 or not t[0] or t[0][0] != "Serving":
            continue
        for row in t[1:]:
            if len(row) < 2 or not re.match(r"^\d", row[1]):
                continue
            country = row[0]
            m = re.match(r"^(\d+)\s*(?:\(([^)]*)\))?", row[1])
            if not m:
                continue
            code = m.group(1)
            subs = [s.strip() for s in (m.group(2) or "").split(",") if s.strip()]
            keys = [f"{code}-{s}" for s in subs] or [code]
            for k in keys:
                out.setdefault(k, []).append({"country": country, "utc": row[2] if len(row) > 2 else ""})
    return out


DRIVING_SUPPLEMENT = {  # 维基表里没有单独列的地区（来源：各地区条目，常识）
    "Hong Kong": ("left", "沿用英治时期，与内地相反"), "Macau": ("left", "沿用葡治时期，与内地相反"), "Taiwan": ("right", ""),
    "French Guiana": ("right", "法国海外省"), "Guadeloupe": ("right", "法国海外省"), "Martinique": ("right", "法国海外省"),
    "Réunion": ("right", "法国海外省"), "Mayotte": ("right", "法国海外省"), "New Caledonia": ("right", "法国属地"), "French Polynesia": ("right", "法国属地"),
    "Puerto Rico": ("right", "美国属地"), "Guam": ("right", "美国属地"), "U.S. Virgin Islands": ("left", "美国属地，少见的靠左"),
    "American Samoa": ("right", "美国属地"), "Northern Mariana Islands": ("right", "美国属地"),
    "Greenland": ("right", "丹麦"), "Faroe Islands": ("right", "丹麦"), "Aruba": ("right", "荷兰"), "Curaçao": ("right", "荷兰"), "Sint Maarten": ("right", "荷兰"),
    "Gibraltar": ("right", "英国属地，少见的靠右"), "Bermuda": ("left", "英国属地"), "Cayman Islands": ("left", "英国属地"),
    "British Virgin Islands": ("left", "英国属地"), "Anguilla": ("left", "英国属地"), "Montserrat": ("left", "英国属地"),
    "Turks and Caicos Islands": ("left", "英国属地"), "Falkland Islands": ("left", "英国属地"), "Saint Helena": ("left", "英国属地"),
    "Isle of Man": ("left", "英国王室属地"), "Jersey": ("left", "英国王室属地"), "Guernsey": ("left", "英国王室属地"),
    "Cook Islands": ("left", "新西兰联系邦"), "Niue": ("left", "新西兰联系邦"), "Tokelau": ("left", "新西兰属地"),
    "Canary Islands": ("right", "西班牙"), "Azores": ("right", "葡萄牙"), "Madeira": ("right", "葡萄牙"), "Svalbard": ("right", "挪威"),
}


def parse_driving_side(html: str) -> dict:
    out = {}
    for t in _tables(html):
        if len(t) < 100 or not t[0] or t[0][0] != "Country":
            continue
        for row in t[1:]:
            if len(row) < 2:
                continue
            idx = next((i for i, c in enumerate(row) if re.match(r"^(LHT|RHT)", c.upper())), None)
            if idx is None:
                continue
            side = "left" if row[idx].upper().startswith("LHT") else "right"
            out[row[0]] = {"side": side, "switched": row[idx + 1] if len(row) > idx + 1 else "", "note": row[idx + 2] if len(row) > idx + 2 else ""}
    for k, (side, note) in DRIVING_SUPPLEMENT.items():
        if k not in out:
            out[k] = {"side": side, "switched": "", "note": note, "curated": True}
    return out


def parse_territories(html: str) -> dict:
    items = []
    for t in _tables(html):
        if not t or not t[0] or t[0][0] != "Name" or "Sovereign state" not in t[0]:
            continue
        hi = {h: i for i, h in enumerate(t[0])}
        for row in t[1:]:
            if len(row) < len(t[0]) - 1:
                continue
            items.append({"name": row[hi["Name"]], "sovereign": row[hi["Sovereign state"]], "region": row[hi["UN region"]],
                          "subregion": row[hi["UN subregion"]], "status": row[hi.get("Legal status", len(row) - 1)],
                          "population": row[hi.get("Population (2016)", 1)], "area_km2": row[hi.get("Area (km)", 2)]})
    names = {it["name"].lower() for it in items}
    for it in INTEGRAL_OVERSEAS:
        if it["name"].lower() not in names:
            items.append(dict(it, population="", area_km2="", curated=True))
    by_sov: dict = {}
    for it in items:
        by_sov.setdefault(it["sovereign"], []).append(it)
    return {"by_sovereign": by_sov, "count": len(items),
            "note": "维基“属地列表”不含法国海外省这类本土一体化的海外领土，INTEGRAL_OVERSEAS 补上（curated=true）"}


def parse_cn_admin(raw: str) -> dict:
    nodes = json.loads(raw)
    items = []

    def walk(ns, parent, level):
        for n in ns:
            name, code = n.get("name", ""), n.get("code", "")
            ch = n.get("children") or []
            if level == 2 and name in ("市辖区", "县", "省直辖县级行政区划", "自治区直辖县级行政区划", "市"):
                walk(ch, parent, 3)      # 直辖市/省直辖的假层：下级直接挂省
                continue
            items.append({"name": name, "code": code, "level": level, "parent": parent})
            walk(ch, name, level + 1)

    walk(nodes, "", 1)
    return {"items": items}


PARSERS = {"cn_plates": parse_cn_plates, "cn_area_codes": parse_cn_area_codes, "calling_codes": parse_calling_codes,
           "driving_side": parse_driving_side, "territories": parse_territories, "cn_admin": parse_cn_admin}


# ---------------------------------------------------------------- 读写

def load(table: str) -> dict:
    f = DATA / f"{table}.json"
    if not f.exists():
        sys.exit(f"没有 {f}：先 `clues.py update {table} --proxy socks5h://127.0.0.1:10808（示例）`")
    return json.loads(f.read_text())


def _fetch(url: str, proxy: str | None) -> str:
    cmd = ["curl", "-s", "-m", "90", "-A", UA, "-L"]
    if proxy:
        cmd += ["--proxy", proxy]
    r = subprocess.run(cmd + [url], capture_output=True)
    if r.returncode != 0 or len(r.stdout) < 1000:
        sys.exit(f"抓取失败：{url}（国内要 --proxy socks5h://127.0.0.1:10808（示例））")
    return r.stdout.decode("utf-8", "replace")


def cmd_update(args) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    names = list(SOURCES) if args.table in ("all", None) else [args.table]
    for name in names:
        if args.from_dir:
            src = Path(args.from_dir) / LOCAL_NAMES[name]
            raw = src.read_text(encoding="utf-8", errors="replace")
        else:
            raw = _fetch(SOURCES[name][0], args.proxy)
        data = PARSERS[name](raw)
        n = data.get("count") or len(data.get("items") or data)
        payload = {"_meta": {"source": SOURCES[name], "fetched": date.today().isoformat(), "count": n}, **data}
        (DATA / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1))
        print(f"{name}: {n} 条 -> {DATA / f'{name}.json'}（{(DATA / f'{name}.json').stat().st_size // 1024} KB）")


# ---------------------------------------------------------------- 查询

def _norm_plate(v: str) -> tuple[str, str]:
    v = v.strip().replace("·", "").replace(" ", "").replace("　", "")
    v = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in v)
    m = re.match(r"^([\u4e00-\u9fff])\s*([A-Za-z])?", v)
    if not m:
        return "", ""
    return m.group(1), (m.group(2) or "").upper()


def _result(kind, value, matches, source, fetched, note=""):
    return {"kind": kind, "value": value, "matches": matches, "source": source, "table_fetched": fetched, "note": note}


def lookup_plate(value: str) -> dict:
    d = load("cn_plates")
    abbr, letter = _norm_plate(value)
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    if not abbr or abbr not in d:
        return _result("plate", value, [], src, fetched, "省简称没认出来，或表里没有（港澳台、军警牌不在表里）")
    prov = d[abbr]["province"]
    if not letter:
        return _result("plate-prefix", value, [{"admin1": prov, "admin2": "", "note": "只给了省简称"}], src, fetched)
    place = d[abbr]["letters"].get(letter)
    if not place:
        return _result("plate", value, [{"admin1": prov, "admin2": "", "note": f"字母 {letter} 不在分配表里（新增号段或表未更新）"}], src, fetched)
    matches = []
    for p in re.split(r"[、，,/]", place):
        p = p.strip()
        if not p:
            continue
        note = ""
        if p == prov or p.rstrip("市") == prov.rstrip("市"):
            unv = (d[abbr].get("letter_notes_unverified") or {}).get(letter)
            note = f"直辖市全境；分区常识（未核实）：{unv}" if unv else "直辖市全境"
            p = ""
        matches.append({"admin1": prov, "admin2": p, "note": note})
    return _result("plate", value, matches, src, fetched)


def lookup_area_code(value: str) -> dict:
    d = load("cn_area_codes")
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    digits = re.sub(r"\D", "", value)
    if not digits.startswith("0"):
        digits = "0" + digits
    for L in (4, 3):
        code = digits[:L]
        if code in d:
            e = d[code]
            note = ("已弃用；" if e.get("deprecated") else "") + (e.get("note") or "")
            return _result("area-code", value, [{"admin1": e["admin1"], "admin2": a, "note": note, "digits": e.get("digits", "")} for a in e["admin2"]] or
                           [{"admin1": e["admin1"], "admin2": "", "note": note}], src, fetched)
    return _result("area-code", value, [], src, fetched, "不是国内固话区号（手机号、400/800、国外号码），或位数切错：区号 010/02X 是 3 位，其余 4 位")


def lookup_calling_code(value: str) -> dict:
    d = load("calling_codes")
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    for L in (3, 2, 1):
        code = digits[:L]
        if code in d:
            hits = d[code]
            # 1、7 这类共用码：看后面的区号
            subs = [k for k in d if k.startswith(code + "-") and digits[L:].startswith(k.split("-")[1])]
            if subs:
                hits = [h for k in subs for h in d[k]]
            return _result("calling-code", value, [{"country": h["country"], "utc": h.get("utc", ""), "note": ""} for h in hits], src, fetched)
    return _result("calling-code", value, [], src, fetched, "没匹配到国家码")


_CN_NAMES: dict | None = None


def _country_en(name: str) -> str:
    """中文/别名 → 各表用的英文名。先查 data/country_names.json（300 国 + 别名），再查内置 COUNTRY_ZH。"""
    global _CN_NAMES
    n = name.strip()
    if _CN_NAMES is None:
        f = DATA / "country_names.json"
        _CN_NAMES = json.loads(f.read_text()) if f.exists() else {}
    aliases = _CN_NAMES.get("aliases") or {}
    en2zh = _CN_NAMES.get("en2zh") or {}
    if n in aliases:
        return aliases[n]
    for en, zh in en2zh.items():
        if zh == n:
            return en
    return COUNTRY_ZH.get(n, n)


def lookup_driving_side(value: str | None, country: str | None) -> dict:
    d = load("driving_side")
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    if country:
        en = _country_en(country)
        hit = next(((k, v) for k, v in d.items() if k != "_meta" and k.lower() == en.lower()), None) or \
            next(((k, v) for k, v in d.items() if k != "_meta" and en.lower() in k.lower()), None)
        if not hit:
            return _result("driving-side", country, [], src, fetched, "表里没有这个国家名，试英文名")
        k, v = hit
        return _result("driving-side", country, [{"country": k, "side": v["side"], "note": v.get("note", "")}], src, fetched)
    side = "left" if (value or "").lower().startswith(("l", "左")) else "right"
    ms = [{"country": k, "side": v["side"], "note": v.get("note", "")} for k, v in d.items() if k != "_meta" and v["side"] == side]
    return _result("driving-side", side, ms, src, fetched)


def lookup_territories(value: str, continent: str | None) -> dict:
    d = load("territories")
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    en = _country_en(value)
    sovs = [k for k in d["by_sovereign"] if k.lower() == en.lower()] or [k for k in d["by_sovereign"] if en.lower() in k.lower()]
    if not sovs:
        return _result("territories", value, [], src, fetched, "表里没有这个主权国（或它没有属地）；前殖民地不在此表")
    items = [it for k in sovs for it in d["by_sovereign"][k]]
    if continent:
        keys = [x.lower() for x in CONTINENT_ZH.get(continent, [continent])]
        items = [it for it in items if any(k in (it["region"] + " " + it["subregion"]).lower() for k in keys)]
    return _result("territories", value, [{"country": it["name"], "continent": it["region"], "subregion": it["subregion"],
                                           "note": f"{it['status']}；主权国 {it['sovereign']}"} for it in items], src, fetched)


def lookup_admin(value: str | None, children: str | None, level: str | None) -> dict:
    d = load("cn_admin")
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    items = d["items"]
    by_name: dict = {}
    for it in items:
        by_name.setdefault(it["name"], []).append(it)
    if children:
        parent = children.strip()
        hits = by_name.get(parent) or [it for it in items if it["name"].rstrip("市省") == parent.rstrip("市省")]
        if not hits:
            return _result("admin", parent, [], src, fetched, "没有这个行政区名")
        kids = [it for it in items if it["parent"] == hits[0]["name"]]
        want = {"city": 2, "county": 3}.get(level or "", None)
        if want:
            kids = [k for k in kids if k["level"] == want]
        return _result("admin-children", parent, [{"admin1": hits[0]["name"], "admin2": k["name"], "code": k["code"], "level": k["level"]} for k in kids], src, fetched)
    name = (value or "").strip()
    hits = by_name.get(name) or [it for it in items if it["name"].rstrip("市省区县") == name.rstrip("市省区县")]
    ms = []
    for h in hits:
        chain = [h["name"]]
        p = h["parent"]
        while p:
            chain.append(p)
            nxt = by_name.get(p)
            p = nxt[0]["parent"] if nxt else ""
        ms.append({"admin1": chain[-1], "admin2": h["name"] if h["level"] > 1 else "", "chain": list(reversed(chain)), "code": h["code"], "level": h["level"]})
    return _result("admin", name, ms, src, fetched, "" if ms else "没有这个行政区名（写全名，如“渝北区”）")


def cmd_lookup(args) -> None:
    k = args.kind
    if k in ("plate", "plate-prefix"):
        res = lookup_plate(args.value or "")
    elif k == "area-code":
        res = lookup_area_code(args.value or "")
    elif k == "calling-code":
        res = lookup_calling_code(args.value or "")
    elif k == "driving-side":
        res = lookup_driving_side(args.value, args.country)
    elif k == "territories":
        res = lookup_territories(args.value or "", args.continent)
    elif k == "admin":
        res = lookup_admin(args.value, args.children, args.level)
    else:
        sys.exit("kind: plate / plate-prefix / area-code / calling-code / driving-side / territories / admin")
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    print(f"[{res['kind']}] {res['value']} → {len(res['matches'])} 条" + (f"（{res['note']}）" if res["note"] else ""))
    for m in res["matches"][: args.limit]:
        if "country" in m:
            print("  " + " / ".join(str(m.get(x)) for x in ("country", "side", "continent", "subregion", "utc") if m.get(x)) + (f"  {m['note']}" if m.get("note") else ""))
        else:
            print("  " + " / ".join(str(m.get(x)) for x in ("admin1", "admin2") if m.get(x)) + (f"  {m['note']}" if m.get("note") else "")
                  + (f"  链:{'>'.join(m['chain'])}" if m.get("chain") else ""))
    if len(res["matches"]) > args.limit:
        print(f"  … 共 {len(res['matches'])} 条，--limit 调大")
    print(f"来源 {res['source']}（{res['table_fetched']}）")


def cmd_list(args) -> None:
    for name in SOURCES:
        f = DATA / f"{name}.json"
        if not f.exists():
            print(f"{name}: 未抓取")
            continue
        m = json.loads(f.read_text())["_meta"]
        print(f"{name}: {m.get('count')} 条，{f.stat().st_size // 1024} KB，抓取 {m.get('fetched')}，来源 {m['source'][0]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lk = sub.add_parser("lookup")
    lk.add_argument("kind")
    lk.add_argument("value", nargs="?")
    lk.add_argument("--country")
    lk.add_argument("--continent")
    lk.add_argument("--children")
    lk.add_argument("--level", choices=["city", "county"])
    lk.add_argument("--json", action="store_true")
    lk.add_argument("--limit", type=int, default=40)
    sub.add_parser("list")
    up = sub.add_parser("update")
    up.add_argument("table", nargs="?", default="all")
    up.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    up.add_argument("--from-dir", help="已下载的源文件目录（开发用）")
    args = ap.parse_args()
    {"lookup": cmd_lookup, "list": cmd_list, "update": cmd_update}[args.cmd](args)


if __name__ == "__main__":
    main()
