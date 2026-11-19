#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""Yandex Panoramas (street view in Eastern Europe and Central Asia): find points, scan an area, render by heading, build comparison sheets. Usage mirrors gsv.py and baidu_pano.py.

Uses the endpoints the Yandex Maps web client calls; no key required by default.
Optionally accepts YANDEX_API_KEY in the environment for official developer-tier routing.

Coverage spans Russia, Belarus, Kazakhstan, Uzbekistan, Armenia and other CIS regions where Google Street View coverage is absent or outdated.

Examples:
  yandex_pano.py near 41.3111,69.2797                             # nearest panorama point in Tashkent
  yandex_pano.py scan 41.3111,69.2797 --radius 200 --out panos.json
  yandex_pano.py render 1342674921_672349120_23_1623838291 --heading 120 --out v.jpg
  yandex_pano.py sheet --panos panos.json --toward 41.3120,69.2810 --out s.jpg
  yandex_pano.py sheet --ids ID1,ID2 --heading 45 --out s.jpg
  yandex_pano.py sheet --ids ID1 --headings 0,60,120,180,240,300 --out around.jpg
"""
from __future__ import annotations

import argparse
from _net import fetch_bytes, PROXY_HELP
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import io
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import geo

API_META = "https://api-maps.yandex.ru/services/panoramas/1.x"
TILE_CDN = "https://pano.maps.yandex.net"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
REFERER = "https://yandex.ru/maps/"

HEADERS = {
    "User-Agent": UA,
    "Referer": REFERER,
    "Accept": "application/json, image/*, */*"
}

CACHE_DIR = Path(os.environ.get("GEO_CACHE_DIR", "temnota/.cache/yandex"))


def _get(url: str, timeout: int = 20, proxy: str | None = None) -> bytes:
    return fetch_bytes(url, proxy=proxy, timeout=timeout, headers=HEADERS)


# ---------------------------------------------------------------- metadata


def get_meta_by_coords(lat: float, lon: float, proxy: str | None = None) -> dict | None:
    """Fetch panorama metadata near given coordinates."""
    key = os.environ.get("YANDEX_API_KEY", "").strip()
    url = f"{API_META}?l=stv&lang=ru_RU&ll={lon:.6f},{lat:.6f}&origin=userAction&format=json"
    if key:
        url += f"&apikey={key}"
    try:
        raw = _get(url, timeout=15, proxy=proxy)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict) or data.get("status") != "success":
        return None
    return _parse_meta(data.get("data", {}))


def get_meta_by_id(panoid: str, proxy: str | None = None) -> dict | None:
    """Fetch panorama metadata by panorama ID."""
    key = os.environ.get("YANDEX_API_KEY", "").strip()
    url = f"{API_META}?oid={panoid}&provider=streetview&l=stv&lang=ru_RU&format=json"
    if key:
        url += f"&apikey={key}"
    try:
        raw = _get(url, timeout=15, proxy=proxy)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict) or data.get("status") != "success":
        return None
    return _parse_meta(data.get("data", {}))


def _parse_meta(data: dict) -> dict:
    pdata = data.get("Data", {}) if "Data" in data else data
    panoid = pdata.get("panoramaId") or pdata.get("Properties", {}).get("PanoramaDescription", {}).get("id", "")
    pt = pdata.get("Point", {}).get("coordinates") or [0.0, 0.0]
    lon, lat = float(pt[0]), float(pt[1])

    origin = (
        pdata.get("EquirectangularProjection", {}).get("Origin")
        or pdata.get("Properties", {}).get("PanoramaDescription", {}).get("direction")
        or [0.0, 0.0]
    )
    heading = float(origin[0]) if len(origin) > 0 else 0.0
    pitch = float(origin[1]) if len(origin) > 1 else 0.0

    ts = pdata.get("timestamp") or pdata.get("Properties", {}).get("PanoramaDescription", {}).get("timestamp")
    date_str = ""
    if ts:
        try:
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OverflowError, OSError):
            date_str = str(ts)

    images = pdata.get("Images", {})
    image_id = images.get("imageId") or panoid
    tiles = images.get("Tiles") or images.get("tiles") or {}
    zooms = images.get("Zooms") or images.get("sizes") or []

    connections = []
    nodes = data.get("Annotation", {}).get("Graph", {}).get("Nodes", [])
    for node in nodes:
        nid = node.get("panoid")
        if nid and nid != panoid:
            connections.append({"id": nid, "lat": float(node.get("lat", 0.0)), "lon": float(node.get("lon", 0.0))})

    if not connections:
        for conn in data.get("Connections", []):
            cid = conn.get("Properties", {}).get("Connection", {}).get("id")
            cpt = conn.get("Point", {}).get("coordinates")
            if cid and cpt and cid != panoid:
                connections.append({"id": cid, "lat": float(cpt[1]), "lon": float(cpt[0])})

    return {
        "id": panoid,
        "image_id": image_id,
        "lat": lat,
        "lon": lon,
        "heading": heading,
        "pitch": pitch,
        "date": date_str,
        "name": pdata.get("Properties", {}).get("PanoramaDescription", {}).get("name", ""),
        "tile_width": tiles.get("width", 256),
        "tile_height": tiles.get("height", 256),
        "zooms": zooms,
        "connections": connections,
    }


def near(lat: float, lon: float, radius: float = 50, proxy: str | None = None) -> dict | None:
    meta = get_meta_by_coords(lat, lon, proxy=proxy)
    if not meta:
        return None
    dist = geo.distance((lat, lon), (meta["lat"], meta["lon"]))
    if dist > radius:
        return None
    meta["distance_m"] = round(dist, 1)
    return meta


def scan(lat: float, lon: float, radius: float = 300, max_points: int = 150,
         proxy: str | None = None) -> list[dict]:
    """Crawl interconnected panoramas within radius meters of lat,lon."""
    first = near(lat, lon, radius=radius, proxy=proxy)
    if not first:
        return []

    visited = {first["id"]: first}
    queue = [first]

    while queue and len(visited) < max_points:
        curr = queue.pop(0)
        for conn in curr.get("connections", []):
            cid = conn["id"]
            if cid in visited:
                continue
            dist = geo.distance((lat, lon), (conn["lat"], conn["lon"]))
            if dist <= radius:
                meta = get_meta_by_id(cid, proxy=proxy)
                if meta:
                    meta["distance_m"] = round(dist, 1)
                    visited[cid] = meta
                    queue.append(meta)
                    if len(visited) >= max_points:
                        break

    out = list(visited.values())
    out.sort(key=lambda p: p.get("distance_m", 0))
    return out


# ---------------------------------------------------------------- tile fetching & projection


def fetch_tile(image_id: str, zoom: int, x: int, y: int, cache: Path, proxy: str | None = None) -> Image.Image:
    cache_tile = cache / f"tile_{image_id}_{zoom}_{x}_{y}.jpg"
    if cache_tile.exists() and cache_tile.stat().st_size > 500:
        try:
            return Image.open(cache_tile).convert("RGB")
        except (OSError, ValueError):
            pass

    url = f"{TILE_CDN}/{image_id}/{zoom}.{x}.{y}"
    try:
        raw = _get(url, timeout=12, proxy=proxy)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        cache.mkdir(parents=True, exist_ok=True)
        cache_tile.write_bytes(raw)
        return im
    except (OSError, RuntimeError, ValueError):
        return Image.new("RGB", (256, 256), "black")


def get_equirectangular(panoid: str, zoom: int = 3, cache: Path | None = None,
                        proxy: str | None = None) -> tuple[np.ndarray, dict]:
    """Fetch tiles and stitch into an equirectangular panorama image (numpy array)."""
    cdir = cache or CACHE_DIR
    meta = get_meta_by_id(panoid, proxy=proxy) or {"id": panoid, "heading": 0.0}
    image_id = meta.get("image_id") or panoid
    tile_w, tile_h = meta.get("tile_width", 256), meta.get("tile_height", 256)

    # Find zoom details or fallback
    zoom_info = None
    for z in meta.get("zooms", []):
        if isinstance(z, dict) and z.get("level") == zoom:
            zoom_info = z
            break

    if zoom_info:
        full_w, full_h = zoom_info["width"], zoom_info["height"]
        cols = math.ceil(full_w / tile_w)
        rows = math.ceil(full_h / tile_h)
    else:
        cols = 7
        rows = 3
        full_w, full_h = cols * tile_w, rows * tile_h

    cache_pano = cdir / f"pano_{panoid}_z{zoom}.jpg"
    if cache_pano.exists() and cache_pano.stat().st_size > 5000:
        try:
            im = Image.open(cache_pano).convert("RGB")
            return np.array(im, dtype=np.uint8), meta
        except (OSError, ValueError):
            pass

    tasks = [(image_id, zoom, x, y) for y in range(rows) for x in range(cols)]
    with ThreadPoolExecutor(8) as ex:
        tiles = list(ex.map(lambda args: fetch_tile(*args, cache=cdir, proxy=proxy), tasks))

    stitched = Image.new("RGB", (cols * tile_w, rows * tile_h))
    idx = 0
    for y in range(rows):
        for x in range(cols):
            stitched.paste(tiles[idx], (x * tile_w, y * tile_h))
            idx += 1

    if full_w < stitched.width or full_h < stitched.height:
        stitched = stitched.crop((0, 0, full_w, full_h))

    # Canonical 2:1 equirectangular sphere padding (360x180 deg)
    sphere_h = stitched.width // 2
    if stitched.height < sphere_h:
        canonical = Image.new("RGB", (stitched.width, sphere_h), "black")
        canonical.paste(stitched, (0, (sphere_h - stitched.height) // 2))
    else:
        canonical = stitched

    try:
        cdir.mkdir(parents=True, exist_ok=True)
        canonical.save(cache_pano, quality=85)
    except (OSError, ValueError):
        pass

    return np.array(canonical, dtype=np.uint8), meta


def project_perspective(pano: np.ndarray, heading_deg: float, pitch_deg: float,
                        hfov_deg: float, width: int, height: int,
                        pano_heading_deg: float = 0.0) -> Image.Image:
    """Ray-trace a rectilinear perspective view from an equirectangular sphere using numpy."""
    H_eq, W_eq = pano.shape[:2]
    f = (width / 2.0) / math.tan(math.radians(hfov_deg / 2.0))
    cx, cy = width / 2.0, height / 2.0

    xs = np.arange(width, dtype=np.float32)
    ys = np.arange(height, dtype=np.float32)
    x_grid, y_grid = np.meshgrid(xs, ys)

    dx = x_grid - cx + 0.5
    dy = cy - y_grid - 0.5
    dz = np.full_like(dx, f)

    norm = np.sqrt(dx**2 + dz**2 + dy**2)
    x_c = dx / norm
    y_c = dz / norm
    z_c = dy / norm

    yaw = math.radians(heading_deg - pano_heading_deg)
    pitch = math.radians(pitch_deg)

    # Pitch rotation around X (pitch up -> look up)
    y_p = y_c * math.cos(pitch) - z_c * math.sin(pitch)
    z_p = y_c * math.sin(pitch) + z_c * math.cos(pitch)
    x_p = x_c

    # Yaw rotation around Z (clockwise from North/Forward)
    x_w = x_p * math.cos(yaw) + y_p * math.sin(yaw)
    y_w = -x_p * math.sin(yaw) + y_p * math.cos(yaw)
    z_w = z_p

    theta = np.arctan2(x_w, y_w)
    theta = np.where(theta < 0, theta + 2 * np.pi, theta)
    phi = np.arcsin(np.clip(z_w, -1.0, 1.0))

    u = (theta / (2 * np.pi)) * W_eq
    v = (0.5 - phi / np.pi) * H_eq

    try:
        import cv2
        map_x = u.astype(np.float32)
        map_y = v.astype(np.float32)
        out = cv2.remap(pano, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        return Image.fromarray(out)
    except ImportError:
        u0 = np.floor(u).astype(int) % W_eq
        u1 = (u0 + 1) % W_eq
        v0 = np.clip(np.floor(v).astype(int), 0, H_eq - 1)
        v1 = np.clip(v0 + 1, 0, H_eq - 1)

        du = (u - np.floor(u))[..., None]
        dv = (v - np.clip(np.floor(v), 0, H_eq - 1))[..., None]

        top = pano[v0, u0] * (1 - du) + pano[v0, u1] * du
        bot = pano[v1, u0] * (1 - du) + pano[v1, u1] * du
        out = (top * (1 - dv) + bot * dv).astype(np.uint8)
        return Image.fromarray(out)


def render(pid: str, heading: float, pitch: float = -8, fov: float = 90,
           w: int = 640, h: int = 480, cache: Path | None = None,
           proxy: str | None = None) -> Image.Image:
    """Render a perspective view at a given compass heading."""
    cdir = cache or CACHE_DIR
    key = f"{pid}_{heading:.0f}_{pitch:.0f}_{fov:.0f}_{w}x{h}.jpg"
    out_file = cdir / key

    if out_file.exists() and out_file.stat().st_size > 2000:
        try:
            return Image.open(out_file).convert("RGB")
        except (OSError, ValueError):
            pass

    zoom = 3 if max(w, h) <= 800 else 2
    try:
        pano, meta = get_equirectangular(pid, zoom=zoom, cache=cdir, proxy=proxy)
        im = project_perspective(pano, heading, pitch, fov, w, h, meta.get("heading", 0.0))
        cdir.mkdir(parents=True, exist_ok=True)
        im.save(out_file, quality=88)
        return im
    except (OSError, RuntimeError, ValueError):
        return Image.new("RGB", (w, h), "gray")


# ---------------------------------------------------------------- sheets and formatting


def _font(size: int):
    for p in (
        os.environ.get("GEO_FONT", "").strip(),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if p and Path(p).is_file():
            try:
                return ImageFont.truetype(p, size)
            except (OSError, ValueError):
                continue
    return ImageFont.load_default()


def sheet(items: list[dict], out: Path, cols: int = 3, tw: int = 480, th: int = 360,
          cache: Path | None = None, proxy: str | None = None) -> None:
    """Generate a numbered contact sheet from a list of panorama perspective views."""
    cdir = cache or CACHE_DIR
    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(lambda it: render(it["id"], it["heading"], it.get("pitch", -8),
                                            it.get("fov", 90), 640, 480, cache=cdir, proxy=proxy), items))
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, max(1, rows) * th), "black")
    d = ImageDraw.Draw(S)
    f = _font(15)

    for i, (it, im) in enumerate(zip(items, ims)):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im.resize((tw, th)), (x, y))
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        lbl = it.get("label") or f"#{i}: …{it['id'][-8:]} h{it['heading']:.0f}°"
        d.text((x + 4, y + 3), lbl, fill="yellow", font=f)

    out.parent.mkdir(parents=True, exist_ok=True)
    S.save(out, quality=88)


# ---------------------------------------------------------------- CLI


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--proxy", default=None, help=PROXY_HELP)
        sp.add_argument("--cache", type=Path, default=CACHE_DIR)

    # near
    p_near = sub.add_parser("near", help="find nearest panorama to coordinates")
    p_near.add_argument("coords", help="lat,lon")
    p_near.add_argument("--radius", type=float, default=50, help="maximum search distance in meters")
    common(p_near)

    # scan
    p_scan = sub.add_parser("scan", help="scan panoramas within radius")
    p_scan.add_argument("coords", help="lat,lon")
    p_scan.add_argument("--radius", type=float, default=300, help="radius in meters")
    p_scan.add_argument("--max", type=int, default=150, help="maximum panoramas to collect")
    p_scan.add_argument("--out", type=Path, default=Path("panos.json"), help="output JSON file")
    common(p_scan)

    # render
    p_rend = sub.add_parser("render", help="render perspective view by heading")
    p_rend.add_argument("id", help="panorama id")
    p_rend.add_argument("--heading", type=float, required=True, help="compass heading (0=North, 90=East)")
    p_rend.add_argument("--pitch", type=float, default=-8, help="pitch angle (-90=down, 0=level, +90=up)")
    p_rend.add_argument("--fov", type=float, default=90, help="horizontal field of view")
    p_rend.add_argument("--out", type=Path, default=Path("render.jpg"), help="output image path")
    common(p_rend)

    # sheet
    p_sheet = sub.add_parser("sheet", help="build contact sheet of panorama views")
    p_sheet.add_argument("--panos", type=Path, help="panos.json from scan")
    p_sheet.add_argument("--ids", help="comma-separated panorama IDs")
    p_sheet.add_argument("--heading", type=float, help="fixed heading for all points")
    p_sheet.add_argument("--headings", help="comma-separated headings (e.g. 0,60,120,180,240,300)")
    p_sheet.add_argument("--pitch", type=float, default=-8, help="pitch angle (-90=down, 0=level, +90=up)")
    p_sheet.add_argument("--fov", type=float, default=90, help="horizontal field of view")
    p_sheet.add_argument("--toward", help="lat,lon target point every panorama will face")
    p_sheet.add_argument("--offset", type=float, default=0, help="heading offset added to --toward")
    p_sheet.add_argument("--out", type=Path, default=Path("sheet.jpg"), help="output sheet image")
    common(p_sheet)

    args = p.parse_args()

    if args.cmd == "near":
        lat, lon = (float(x) for x in args.coords.split(","))
        res = near(lat, lon, radius=args.radius, proxy=args.proxy)
        if not res:
            sys.exit(f"No Yandex panorama found within {args.radius} m of {args.coords}")
        print(json.dumps(res, ensure_ascii=False, indent=2))

    elif args.cmd == "scan":
        lat, lon = (float(x) for x in args.coords.split(","))
        res = scan(lat, lon, radius=args.radius, max_points=args.max, proxy=args.proxy)
        print(f"Found {len(res)} panoramas within {args.radius} m of {args.coords}")
        args.out.write_text(json.dumps({"center": [lat, lon], "radius": args.radius, "panos": res},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved to {args.out}")

    elif args.cmd == "render":
        im = render(args.id, args.heading, pitch=args.pitch, fov=args.fov,
                    cache=args.cache, proxy=args.proxy)
        im.save(args.out, quality=90)
        print(f"Rendered {args.id} at heading {args.heading}° -> {args.out}")

    elif args.cmd == "sheet":
        items = []
        if args.panos and args.panos.is_file():
            data = json.loads(args.panos.read_text(encoding="utf-8"))
            pts = data.get("panos") if isinstance(data, dict) else data
            if args.toward:
                tlat, tlon = (float(x) for x in args.toward.split(","))
                for p_pt in pts:
                    hd = geo.bearing((p_pt["lat"], p_pt["lon"]), (tlat, tlon)) + args.offset
                    items.append({"id": p_pt["id"], "heading": hd % 360, "pitch": args.pitch, "fov": args.fov})
            elif args.heading is not None:
                for p_pt in pts:
                    items.append({"id": p_pt["id"], "heading": args.heading, "pitch": args.pitch, "fov": args.fov})
        elif args.ids:
            ids = [x.strip() for x in args.ids.split(",") if x.strip()]
            if args.headings:
                hds = [float(x) for x in args.headings.split(",")]
                for pid in ids:
                    for hd in hds:
                        items.append({"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov})
            elif args.heading is not None:
                for pid in ids:
                    items.append({"id": pid, "heading": args.heading, "pitch": args.pitch, "fov": args.fov})

        if not items:
            sys.exit("sheet: no items generated. Provide --panos + --toward/--heading, or --ids + --headings/--heading")
        sheet(items, out=args.out, cache=args.cache, proxy=args.proxy)
        print(f"Sheet with {len(items)} views saved to {args.out}")


if __name__ == "__main__":
    main()
