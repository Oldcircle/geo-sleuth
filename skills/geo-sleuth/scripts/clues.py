#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Lookup-table clues. Tables are local JSON; lookups don't go online.

Global tables (data/):
  lookup calling-code +594      international calling code → country/region
  lookup driving-side left      countries that drive on the left; `driving-side --country Japan` → left
  lookup territories France     overseas territories/dependencies of France; `--continent "South America"` lists only that continent
Region-pack tables (regions/<cc>/, see `regions.py list`):
  lookup <kind> <value> [--country cc]   kinds the packs declare, e.g. plate, area-code; without --country every pack with
                                that kind is searched and matches from several countries are all returned; with --country only
                                that pack is used, and a pack that lacks the kind (or isn't installed) answers "unsupported"
  lookup admin <name> [--country cc]     parent chain from a pack's admin table; `admin --children <name>` lists the children
  list                          global tables and installed packs with entry counts and fetch dates

--json output follows one contract (used by board.py apply):
  {"kind", "value", "status": ok|no_match|unsupported|error (error = that country's pack is broken), "matches": [...], "searched": [pack codes], "source", "table_fetched", "note"}
  region matches: {"country", "country_code", "admin1", "admin2"?, "city"?, "district"?, "note", "unverified"?} — levels are explicit
  global matches: {"country", "continent"?, "subregion"?, "side"?, "utc"?, "note"}

Examples:
  clues.py lookup plate <plate prefix> --country cn
  clues.py lookup area-code 0817 --json
  clues.py lookup calling-code +594
  clues.py lookup territories France --continent "South America"
Tables are refreshed by maintainers with refresh.py.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import regions  # noqa: E402

DATA = Path(__file__).parent.parent / "data"
GLOBAL_TABLES = ("calling_codes", "driving_side", "territories", "country_names")
GLOBAL_KINDS = ("calling-code", "driving-side", "territories")

CONTINENT_ZH = {"亚洲": ["Asia"], "欧洲": ["Europe"], "非洲": ["Africa"], "大洋洲": ["Oceania"], "北美洲": ["Northern America", "North America"],
                "南美洲": ["South America"], "美洲": ["Americas"], "加勒比": ["Caribbean"], "中美洲": ["Central America"], "南极洲": ["Antarctica"]}

# ---------------------------------------------------------------- read/write

def load(table: str) -> dict:
    f = DATA / f"{table}.json"
    if not f.exists():
        sys.exit(f"{f} not found: reinstall the skill folder, or refetch with `refresh.py {table}`")
    return json.loads(f.read_text(encoding="utf-8"))


def _result(kind, value, matches, source, fetched, note="", status=None):
    return {"kind": kind, "value": value, "status": status or ("ok" if matches else "no_match"), "matches": matches,
            "searched": [], "source": source, "table_fetched": fetched, "note": note}

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
            # shared codes like 1 and 7: look at the area code that follows
            subs = [k for k in d if k.startswith(code + "-") and digits[L:].startswith(k.split("-")[1])]
            if subs:
                hits = [h for k in subs for h in d[k]]
            return _result("calling-code", value, [{"country": h["country"], "utc": h.get("utc", ""), "note": ""} for h in hits], src, fetched)
    return _result("calling-code", value, [], src, fetched, "no matching country code")


_CN_NAMES: dict | None = None


def _country_en(name: str) -> str:
    """Chinese name / alias → the English name the tables use, from data/country_names.json (300 countries + aliases)."""
    global _CN_NAMES
    n = name.strip()
    if _CN_NAMES is None:
        f = DATA / "country_names.json"
        _CN_NAMES = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    aliases = _CN_NAMES.get("aliases") or {}
    en2zh = _CN_NAMES.get("en2zh") or {}
    if n in aliases:
        return aliases[n]
    for en, zh in en2zh.items():
        if zh == n:
            return en
    return n


def lookup_driving_side(value: str | None, country: str | None) -> dict:
    d = load("driving_side")
    src, fetched = d["_meta"]["source"][0], d["_meta"]["fetched"]
    if country:
        en = _country_en(country)
        hit = next(((k, v) for k, v in d.items() if k != "_meta" and k.lower() == en.lower()), None) or \
            next(((k, v) for k, v in d.items() if k != "_meta" and en.lower() in k.lower()), None)
        if not hit:
            return _result("driving-side", country, [], src, fetched, "country name not in the table; try the English name")
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
        return _result("territories", value, [], src, fetched, "sovereign state not in the table (or it has no territories); former colonies are not in this table")
    items = [it for k in sovs for it in d["by_sovereign"][k]]
    if continent:
        keys = [x.lower() for x in CONTINENT_ZH.get(continent, [continent])]
        items = [it for it in items if any(k in (it["region"] + " " + it["subregion"]).lower() for k in keys)]
    return _result("territories", value, [{"country": it["name"], "continent": it["region"], "subregion": it["subregion"],
                                           "note": f"{it['status']}; sovereign state {it['sovereign']}"} for it in items], src, fetched)


# ---------------------------------------------------------------- region-pack lookups

def lookup_region(kind: str, value: str, country: str | None) -> dict:
    r = regions.lookup(kind, value, country)
    return {"kind": kind, "value": value, "status": r["status"], "matches": r["matches"], "searched": r.get("searched", []),
            "source": r.get("source", ""), "table_fetched": r.get("fetched", ""), "note": r.get("note", "")}


def lookup_admin(value: str | None, children: str | None, level: str | None, country: str | None) -> dict:
    want = {"city": "admin2", "county": "district"}.get(level or "", level)
    if children:
        p, kids = regions.admin_children(children.strip(), country)
        if not p:
            return _result("admin-children", children, [], "", "", "no installed pack has this admin area (use the full name, or gazetteer.py for OSM)",
                           status="unsupported" if country and not regions.resolve(country) else None)
        rows = []
        for k in kids:
            m = regions.match_from_item(p, k)
            m.update(code=k.get("code", ""), level=regions.level_name(p, k["level"]))
            if not want or m["level"] == want:
                rows.append(m)
        meta = regions.load_table(p, p["admin_table"]).get("_meta", {})
        return _result("admin-children", children, rows, ", ".join(meta.get("source") or []), meta.get("fetched", ""))
    name = (value or "").strip()
    rows, srcs = [], set()
    for p, it in regions.admin_find(name, country):
        m = regions.match_from_item(p, it)
        m.update(chain=regions.admin_chain(p, it), code=it.get("code", ""), level=regions.level_name(p, it["level"]))
        rows.append(m)
        srcs.add(", ".join(regions.load_table(p, p["admin_table"]).get("_meta", {}).get("source") or []))
    return _result("admin", name, rows, " | ".join(sorted(srcs)), "", "" if rows else "no admin area with this name in the installed packs (use the full name)")


def cmd_lookup(args) -> None:
    k = "plate" if args.kind == "plate-prefix" else args.kind
    if k == "calling-code":
        res = lookup_calling_code(args.value or "")
    elif k == "driving-side":
        res = lookup_driving_side(args.value, args.country)
    elif k == "territories":
        res = lookup_territories(args.value or "", args.continent)
    elif k == "admin":
        res = lookup_admin(args.value, args.children, args.level, args.country)
    else:
        kinds = sorted({x for p in regions.packs().values() for x in (p.get("lookups") or {})})
        if k not in kinds:
            sys.exit(f"kind: {' / '.join([*GLOBAL_KINDS, 'admin', *kinds])} (region kinds come from installed packs: `regions.py list`)")
        res = lookup_region(k, args.value or "", args.country)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    head = f"[{res['kind']}] {res['value']} → {len(res['matches'])} matches"
    if res["status"] == "unsupported":
        head = f"[{res['kind']}] {res['value']} → unsupported"
    if res.get("searched"):
        head += f" (packs searched: {', '.join(res['searched'])})"
    print(head + (f" ({res['note']})" if res["note"] else ""))
    for m in res["matches"][: args.limit]:
        if "country_code" in m:
            chain = " / ".join(m[lv] for lv in regions.MATCH_LEVELS if m.get(lv))
            print(f"  {m['country_code']}: {chain}" + (f"  [{m['level']}]" if m.get("level") else "") + ("  (unverified)" if m.get("unverified") else "")
                  + (f"  {m['note']}" if m.get("note") else ""))
        else:
            print("  " + " / ".join(str(m.get(x)) for x in ("country", "side", "continent", "subregion", "utc") if m.get(x)) + (f"  {m['note']}" if m.get("note") else ""))
    if len(res["matches"]) > args.limit:
        print(f"  … {len(res['matches'])} in total; raise --limit")
    if res["source"]:
        print(f"source {res['source']}" + (f" ({res['table_fetched']})" if res["table_fetched"] else ""))


def cmd_list(args) -> None:
    for name in GLOBAL_TABLES:
        f = DATA / f"{name}.json"
        if not f.exists():
            print(f"{name}: missing")
            continue
        m = json.loads(f.read_text(encoding="utf-8")).get("_meta", {})
        src = m.get("source") or ["hand-compiled"]
        print(f"{name}: {m.get('count')} entries, {f.stat().st_size // 1024} KB, fetched {m.get('fetched')}, source {src[0] if isinstance(src, list) else src}")
    for code, p in sorted(regions.packs().items()):
        for kind, spec in (p.get("lookups") or {}).items():
            try:
                meta = regions.load_table(p, spec["file"]).get("_meta", {})
            except regions.PACK_ERRORS as exc:
                print(f"{code.lower()}/{kind}: broken ({type(exc).__name__}); `regions.py lint {code.lower()}`")
                continue
            print(f"{code.lower()}/{kind}: {meta.get('count')} keys, fetched {meta.get('fetched')}, source {(meta.get('source') or ['?'])[0]}")
        if p.get("admin_table"):
            print(f"{code.lower()}/admin: {len(regions.admin_items(p))} areas")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lk = sub.add_parser("lookup")
    lk.add_argument("kind")
    lk.add_argument("value", nargs="?")
    lk.add_argument("--country", help="region-pack kinds: restrict to this country's pack (code or name); driving-side: the country to look up")
    lk.add_argument("--continent")
    lk.add_argument("--children")
    lk.add_argument("--level", help="with --children: keep one level (admin2/district; city/county also accepted)")
    lk.add_argument("--json", action="store_true")
    lk.add_argument("--limit", type=int, default=40)
    sub.add_parser("list")
    args = ap.parse_args()
    {"lookup": cmd_lookup, "list": cmd_list}[args.cmd](args)


if __name__ == "__main__":
    # Chinese-locale Windows writes GBK by default: m², ñ make it crash, and the Chinese the agent reads comes out garbled
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
