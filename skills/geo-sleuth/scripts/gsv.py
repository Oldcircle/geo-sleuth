#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Google Street View (the main source outside China): find points, see dates and nearby points, render by heading, build comparison sheets. Usage mirrors baidu_pano.py.

Uses the endpoints the Google Maps web page itself calls; no key needed.
There is almost no Google Street View coverage in mainland China; for photos from mainland China use baidu_pano.py.

Examples:
  gsv.py near 35.6595,139.7005 --radius 50                   # nearest panorama point: id, coordinates, capture date, historical captures, address, nearby points
  gsv.py render XlVh96-Z9lAI5tKrU2O4Yg --heading 90 --out v.jpg
  gsv.py sheet --at 35.6595,139.7005 --headings 0,60,120,180,240,300 --out around.jpg   # look around from a single point
  gsv.py sheet --ids ID1,ID2 --toward 35.6600,139.7010 --out s.jpg                     # every point faces the same target
  gsv.py sheet --points pts.json --heading 90 --date 2018 --out s2018.jpg              # only one capture (the year of the street-view watermark in the photo)
  gsv.py targets --points churches.json --per 2 --out churches.index.json              # every target seen from the panoramas around it, for match.py rank --items
"""
from __future__ import annotations

import argparse
from _net import curl_args, PROXY_HELP
import json
import os
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402
from baidu_pano import _font  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
# official Street View car coverage only (user-uploaded panorama photos have ids like CIHM0og…, and the perspective endpoint can't render them)
# The Maps JS API's own panorama lookup (the GET endpoint GeoPhotoService.SingleImageSearch was turned down in 2026; same response layout)
META = "https://maps.googleapis.com/$rpc/google.internal.maps.mapsjs.v1.MapsJsInternalService/SingleImageSearch"
THUMB = ("https://streetviewpixels-pa.googleapis.com/v1/thumbnail?panoid={id}&cb_client=maps_sv.tactile"
         "&w={w}&h={h}&yaw={yaw:.1f}&pitch={pitch:.1f}&thumbfov={fov:.0f}")
# Coverage layer the Maps web client draws: every official panorama inside one z17 tile (~300 m), one request per tile
COVERAGE = "https://www.google.com/maps/photometa/ac/v1?pb=!1m1!1smaps_sv.tactile!6m3!1i{x}!2i{y}!3i17!8b1"


def _curl(url: str, proxy: str | None, out: Path | None = None, data: str | None = None) -> bytes:
    cmd = ["curl", "-q", "-s", "-m", "40", "-A", UA]
    cmd += curl_args(proxy)
    if out:
        cmd += ["-o", str(out)]
    if data is not None:
        cmd += ["-X", "POST", "-H", "content-type: application/json+protobuf",
                "-H", "x-user-agent: grpc-web-javascript/0.1", "--data", data]
    r = subprocess.run(cmd + [url], capture_output=True)
    return r.stdout


class ServiceError(RuntimeError):
    """Google answered with an error instead of a lookup result (endpoint changed, blocked, rate-limited)."""


def _meta_query(lat: float, lon: float, radius: float) -> str:
    # official Street View car coverage only ([2, true, 2]); the last list asks for address, date, neighbors and history
    return json.dumps([["apiv3", None, None, None, "US", None, None, None, None, None, [[0]]],
                       [[None, None, lat, lon], radius],
                       [None, ["en", "US"], None, None, None, None, None, None, [2], None, [[[2, True, 2]]]],
                       [[1, 2, 3, 4, 8, 6]]])


def near(lat: float, lon: float, radius: float, proxy: str | None) -> dict | None:
    """Nearest panorama within radius; None when there is none. Raises ServiceError when the lookup itself fails."""
    t = _curl(META, proxy, data=_meta_query(lat, lon, radius)).decode("utf-8", "replace")
    try:
        d = json.loads(t)
    except json.JSONDecodeError:
        raise ServiceError(f"unreadable reply: {' '.join(t.split())[:160] or 'empty (network?)'}") from None
    try:
        code = d[0][0]
        body = d[1] if len(d) > 1 else None
    except (IndexError, TypeError, KeyError):
        raise ServiceError(f"unexpected reply: {t[:160]}") from None
    if body is None:
        if code == 5 and "no images" in t.lower():  # [[5, "generic", "Search returned no images."]]
            return None
        raise ServiceError(f"error reply: {t[:160]}")
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
    # this panorama's capture date is in body[6][7]; body[5][0][8] holds historical captures [neighbor index, [year, month(, day)]], don't take it as this panorama's date
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
            # user-uploaded panoramas get mixed into historical captures (perspective renders come out gray): ids start with CIHM0og/CIAB/CAoS, length varies from 22 to 28
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
    """Pick one capture ('2018' or '2018-07') from a near() result: the first match among this panorama and its historical captures; None if there is none."""
    for p in [{"id": res["id"], "wgs": res["wgs"], "date": res["date"]}, *res.get("history", [])]:
        if p["date"] and p["date"].startswith(date):
            return p
    return None


def tile_panos(x: int, y: int, proxy: str | None, cache: Path) -> list[tuple[str, float, float]]:
    """All official panoramas in z17 tile (x, y) as (id, lat, lon). Cached; an empty tile (sea, no coverage) is []."""
    cache.mkdir(parents=True, exist_ok=True)
    p = cache / f"cov17_{x}_{y}.txt"
    if p.exists() and p.stat().st_size > 0:
        t = p.read_text(encoding="utf-8", errors="replace")
    else:
        t = _curl(COVERAGE.format(x=x, y=y), proxy).decode("utf-8", "replace")
        if t.startswith(")]}'"):
            # several targets share tiles and run in parallel: write then rename so nobody reads a half-written file
            tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(t, encoding="utf-8")
            os.replace(tmp, p)
    try:
        d = json.loads(t[t.index("\n") + 1:])
        rows = d[1][1] or []
    except (ValueError, IndexError, TypeError):
        return []
    out = []
    for r in rows:
        try:
            pid, ll = r[0][0][1], r[0][2][0]
            # same filter as near(): user-uploaded panoramas can't be rendered as perspective views
            if len(pid) == 22 and not pid.startswith(("CIHM", "CIAB", "CAoS")):
                out.append((pid, float(ll[2]), float(ll[3])))
        except (IndexError, TypeError, ValueError):
            continue
    return out


def panos_around(lat: float, lon: float, min_d: float, max_d: float, per: int, spacing: float,
                 proxy: str | None, cache: Path) -> list[tuple[str, float, float, float]]:
    """Up to `per` panoramas between min_d and max_d metres from (lat, lon), nearest first and at least `spacing` m apart.
    Returns (id, lat, lon, distance)."""
    cx, cy = (int(v // 256) for v in geo.ll2px(17, lat, lon))
    cands = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for pid, la, lo in tile_panos(cx + dx, cy + dy, proxy, cache):
                d = geo.distance((lat, lon), (la, lo))
                if min_d <= d <= max_d:
                    cands.append((d, pid, la, lo))
    picked: list[tuple[str, float, float, float]] = []
    for d, pid, la, lo in sorted(cands):
        if all(geo.distance((la, lo), (p[1], p[2])) >= spacing for p in picked):
            picked.append((pid, la, lo, d))
        if len(picked) >= per:
            break
    return picked


def render(pid: str, heading: float, pitch: float, fov: float, w: int, h: int, proxy: str | None,
           cache: Path) -> Image.Image:
    """heading: compass bearing; positive pitch = looking up; fov: horizontal field of view."""
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
    """argparse treats negative coordinates like -1.45,-48.5 as option names; prefixing a space makes them plain values (float ignores the space). Needed for every puzzle in the southern or western hemisphere."""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"), help=PROXY_HELP)
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache/gsv"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--proxy", default=argparse.SUPPRESS, help="can go before or after the subcommand")
        sp.add_argument("--cache", type=Path, default=argparse.SUPPRESS)

    n = sub.add_parser("near")
    common(n)
    n.add_argument("latlon")
    n.add_argument("--radius", type=float, default=50)

    r = sub.add_parser("render")
    common(r)
    r.add_argument("id")
    r.add_argument("--heading", type=float, required=True)
    r.add_argument("--pitch", type=float, default=0, help="positive = looking up")
    r.add_argument("--fov", type=float, default=90, help="horizontal field of view")
    r.add_argument("--width", type=int, default=1024)
    r.add_argument("--height", type=int, default=768)
    r.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("sheet")
    common(s)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", help="comma-separated panoids")
    g.add_argument("--at", help="lat,lon: take the nearest panorama point")
    g.add_argument("--points", type=Path, help="JSON {name:[lat,lon]}: take the nearest panorama point for each")
    h = s.add_mutually_exclusive_group(required=True)
    h.add_argument("--heading", type=float)
    h.add_argument("--headings", help="comma-separated, e.g. 0,60,120,180,240,300")
    h.add_argument("--toward", help="lat,lon: every point faces this target")
    s.add_argument("--offset", type=float, default=0)
    s.add_argument("--pitch", type=float, default=0)
    s.add_argument("--fov", type=float, default=90)
    s.add_argument("--radius", type=float, default=50)
    s.add_argument("--date", help="only this capture (2018 or 2018-07), picked from this panorama and its historical captures; use it for the street-view watermark year in the photo")
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--out", type=Path, required=True)

    t = sub.add_parser("targets", help="for every target point, the panoramas around it rendered facing it -> .index.json for match.py")
    common(t)
    t.add_argument("--points", type=Path, required=True, help="JSON {name:[lat,lon]}, e.g. osm.py find output (every church in a region)")
    t.add_argument("--per", type=int, default=2, help="panoramas per target")
    t.add_argument("--min-dist", type=float, default=12, help="skip panoramas closer than this (m): too close shows only a wall")
    t.add_argument("--max-dist", type=float, default=70, help="m")
    t.add_argument("--spacing", type=float, default=15, help="minimum distance between the panoramas picked for one target (m)")
    t.add_argument("--pitch", type=float, default=8)
    t.add_argument("--fov", type=float, default=90)
    t.add_argument("--sheet", type=Path, help="also draw the first --limit items as a contact sheet")
    t.add_argument("--limit", type=int, default=12)
    t.add_argument("--out", type=Path, required=True, help="writes the .index.json for match.py rank --items")

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "near":
        lat, lon = map(float, args.latlon.split(","))
        try:
            res = near(lat, lon, args.radius, args.proxy)
        except ServiceError as e:
            sys.exit(f"Google Street View lookup failed ({e}); run doctor.py --network to check service access")
        print(json.dumps(res, ensure_ascii=False, indent=1) if res else f"no Google Street View panorama within {args.radius:.0f} m (increase --radius or check coverage)")
    elif args.cmd == "render":
        render(args.id, args.heading, args.pitch, args.fov, args.width, args.height, args.proxy, args.cache).save(args.out)
        print(args.out)
    elif args.cmd == "targets":
        pts = json.loads(args.points.read_text(encoding="utf-8"))

        def around(kv):
            name, (la, lo) = kv
            return name, (la, lo), panos_around(la, lo, args.min_dist, args.max_dist, args.per, args.spacing,
                                                args.proxy, args.cache)

        items, empty = [], []
        with ThreadPoolExecutor(8) as ex:
            for name, tgt, picked in ex.map(around, pts.items()):
                if not picked:
                    empty.append(name)
                for pid, la, lo, d in picked:
                    hd = geo.bearing((la, lo), tgt)
                    items.append({"id": pid, "heading": round(hd, 1), "pitch": args.pitch, "fov": args.fov,
                                  "label": f"{len(items)}: {str(name)[:18]} {d:.0f}m h{hd:.0f}", "point": name,
                                  "wgs": [la, lo], "target": list(tgt), "dist": round(d), "date": ""})
        out = args.out if args.out.name.endswith(".index.json") else args.out.with_suffix(".index.json")
        out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(pts)} targets -> {len(items)} views ({len(empty)} targets without a panorama "
              f"within {args.min_dist:.0f}–{args.max_dist:.0f} m) -> {out}")
        if len(items) > 400:
            print(f"match.py caps candidates at --max-candidates 400 by default: pass --max-candidates {len(items)}", file=sys.stderr)
        if args.sheet and items:
            sheet(items[:args.limit], args.sheet, args.proxy, args.cache)
            print(args.sheet)
    else:
        panos: dict[str, dict] = {}
        if args.ids:
            panos = {pid: {"ll": None, "name": "", "date": ""} for pid in args.ids.split(",")}
        else:
            pts = {"at": list(map(float, args.at.split(",")))} if args.at else json.loads(args.points.read_text(encoding="utf-8"))
            for name, (la, lo) in pts.items():
                try:
                    res = near(la, lo, args.radius, args.proxy)
                except ServiceError as e:
                    sys.exit(f"Google Street View lookup failed ({e}); run doctor.py --network to check service access")
                if res and args.date:
                    p = pick_date(res, args.date)
                    if not p:
                        print(f"{name}: no {args.date} capture (available: {', '.join(res['dates_seen'])})", file=sys.stderr)
                        continue
                    panos.setdefault(p["id"], {"ll": p["wgs"], "name": name, "date": p["date"]})
                elif res:
                    panos.setdefault(res["id"], {"ll": res["wgs"], "name": name, "date": res.get("date") or ""})
                else:
                    print(f"{name}: no panorama nearby", file=sys.stderr)
        target = tuple(map(float, args.toward.split(","))) if args.toward else None
        items = []
        for pid, meta in panos.items():
            ll = meta["ll"]
            if args.headings:
                heads = [float(x) for x in args.headings.split(",")]
            elif target:
                if ll is None:
                    try:
                        info = near(*target, 5000, args.proxy)
                    except ServiceError:
                        info = None
                    # with only an id there are no coordinates, so estimate from near the target; --points is recommended
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
    # Chinese-locale Windows writes GBK by default: m², ñ make it crash, and the Chinese the agent reads comes out garbled
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
