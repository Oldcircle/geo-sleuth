#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""用高程数据从候选机位"看"出去：合成山体层次图和天际线，拿来和照片比山脊。

没有街景、只有远山（山区合影、隔江远眺、航拍、窗外山脊线）时，替代 Google Earth 倾斜 3D。
高程用 AWS Terrain Tiles（Terrarium 编码，全球约 30 m，免 key，国内可直连；不通就加 --proxy）。

  view     从一个机位按朝向和视角渲染：远近分层着色 + 红色天际线 + 方位刻度，可和照片上下并排
  profile  输出每个方位的天际线仰角和距离（JSON），做数值比对
  elev     查某点地面高程
  scan     沿线状设施（铁路、公路、输电线）逐点算 360° 地平线，筛出"近处平 + 有山 + 山紧挨一段平地平线"
           的点并聚簇——画面里只有一条设施和一座认不出的山时，用它把整个大区筛成几百片
  ridge    照片山脊取点：逐列找天空到山体的亮度突变，输出像素点列表 + 平地平线列范围 + 地平线行 + 焦距（ridge.json）
  fit      拿 ridge.json 给 scan 的每个簇打分：簇内摆机位网格，搜朝向 × 焦距 × 地平线偏移，
           天际线 RMS + 平地平线罚分 (+ 可选：线状设施离画面左/中/右各多远)，按分排序，--sheet 出前 N 名叠图

重要：天际线轮廓对上，只能说明机位在某条视线附近——沿视线前后挪几百米，远山轮廓几乎不变。
要定点，需要第二条独立约束（另一组近物—远物对齐、地图上的路或河岸）。见 references/geometry.md。

示例：
  terrain.py elev --at 35.3606,138.7274
  terrain.py view --at 35.4983,138.7688 --heading 194 --hfov 50 --range 30000 --out fuji.png   # 河口湖看富士山
  terrain.py view --at <候选机位> --height 20 --heading <朝向> --hfov 65 --out v.png --photo photo.jpg
  terrain.py profile --at 35.4983,138.7688 --heading 194 --hfov 50 --out prof.json
  terrain.py scan --lines rail_bridges.geojson --bbox 35.1,138.3,36.0,139.2 --out hits.json   # 先用 osm.py geom 取线
  terrain.py ridge photo.jpg --x0 760 --x1 1260 --step 20 --flat 0:280 --out ridge.json --png ridge.png
  terrain.py fit --hits hits.json --ridge ridge.json --out fit.json --sheet top.jpg            # 粗搜：每簇 2 km / 250 m / z11
  terrain.py fit --at 35.4983,138.7688 --ridge ridge.json --radius 800 --grid 100 --zoom 13 --az-step 0.25 \\
             --line rail.geojson --line-dist 350-750:550-900:800-1700 --out fine.json          # 精搜 + 设施距离约束

ridge.json 和 fit.json 的字段见各子命令的 --help。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

TILE = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
R_EARTH = 6371008.8
K_REFRACTION = 0.13


def _fetch(z: int, x: int, y: int, cache: Path, proxy: str | None) -> np.ndarray:
    p = cache / f"terrarium_{z}_{x}_{y}.png"
    if not (p.exists() and p.stat().st_size > 100):
        cmd = ["curl", "-s", "-m", "60", "-o", str(p), TILE.format(z=z, x=x, y=y)]
        if proxy:
            cmd[1:1] = ["-x", proxy]
        else:
            cmd[1:1] = ["--noproxy", "*"]
        subprocess.run(cmd, check=False)
    try:
        a = np.asarray(Image.open(p).convert("RGB"), dtype=np.float32)
    except Exception:  # noqa: BLE001
        return np.zeros((256, 256), dtype=np.float32)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


class DEM:
    """以 Web 墨卡托像素为索引的高程拼图。"""

    def __init__(self, center: tuple[float, float], radius_m: float, zoom: int, cache: Path, proxy: str | None):
        cache.mkdir(parents=True, exist_ok=True)
        self.z = zoom
        mpp = geo.meters_per_px(zoom, center[0])
        cx, cy = geo.ll2px(zoom, *center)
        r_px = radius_m / mpp + 256
        self.tx0, self.ty0 = int((cx - r_px) // 256), int((cy - r_px) // 256)
        tx1, ty1 = int((cx + r_px) // 256), int((cy + r_px) // 256)
        nx, ny = tx1 - self.tx0 + 1, ty1 - self.ty0 + 1
        if nx * ny > 400:
            sys.exit(f"范围太大（{nx}x{ny} 块切片），减小 --range 或调低 --zoom")
        self.h = np.zeros((ny * 256, nx * 256), dtype=np.float32)
        jobs = [(x, y) for y in range(self.ty0, ty1 + 1) for x in range(self.tx0, tx1 + 1)]
        with ThreadPoolExecutor(16) as ex:
            for (x, y), arr in zip(jobs, ex.map(lambda t: _fetch(zoom, t[0], t[1], cache, proxy), jobs)):
                self.h[(y - self.ty0) * 256:(y - self.ty0 + 1) * 256, (x - self.tx0) * 256:(x - self.tx0 + 1) * 256] = arr

    def sample(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        n = 256 * 2 ** self.z
        x = (lon + 180) / 360 * n - self.tx0 * 256
        y = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n - self.ty0 * 256
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - x0, y - y0
        H, W = self.h.shape
        x0, y0 = np.clip(x0, 0, W - 2), np.clip(y0, 0, H - 2)
        a, b = self.h[y0, x0], self.h[y0, x0 + 1]
        c, d = self.h[y0 + 1, x0], self.h[y0 + 1, x0 + 1]
        return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _dest_np(lat0: float, lon0: float, brg: np.ndarray, dist: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    la1, lo1 = math.radians(lat0), math.radians(lon0)
    b = np.radians(brg)[:, None]
    d = (dist / R_EARTH)[None, :]
    la2 = np.arcsin(math.sin(la1) * np.cos(d) + math.cos(la1) * np.sin(d) * np.cos(b))
    lo2 = lo1 + np.arctan2(np.sin(b) * np.sin(d) * math.cos(la1), np.cos(d) - math.sin(la1) * np.sin(la2))
    return np.degrees(la2), np.degrees(lo2)


def cast(dem: DEM, at, eye_alt: float, azimuths: np.ndarray, rng: float, near: float = 40.0, n: int = 900):
    """返回 (每列每个采样的仰角°, 采样距离 m)。n = 每条视线的采样数（view/profile 用 900；fit 用 --nsamp）。"""
    dist = near * (rng / near) ** (np.arange(n) / (n - 1))          # 近处密、远处疏
    lat, lon = _dest_np(at[0], at[1], azimuths, dist)
    h = dem.sample(lat, lon)
    drop = dist ** 2 / (2 * R_EARTH) * (1 - K_REFRACTION)
    ang = np.degrees(np.arctan2(h - drop[None, :] - eye_alt, dist[None, :]))
    return ang, dist


def render(ang: np.ndarray, dist: np.ndarray, azimuths: np.ndarray, pitch: float, vfov: float, height: int) -> tuple[Image.Image, np.ndarray, np.ndarray]:
    W = ang.shape[0]
    img = np.zeros((height, W, 3), dtype=np.uint8)
    img[:] = (205, 225, 245)                                         # 天空
    top = pitch + vfov / 2

    def row(a):
        return (top - a) / vfov * (height - 1)

    sky_ang = np.full(W, -90.0)
    sky_dist = np.full(W, np.nan)
    runmax = np.maximum.accumulate(ang, axis=1)
    visible = ang >= np.concatenate([np.full((W, 1), -90.0), runmax[:, :-1]], axis=1)
    logd = np.log(dist / dist[0]) / np.log(dist[-1] / dist[0])
    for c in range(W):
        idx = np.nonzero(visible[c])[0]
        prev = row(-90.0)
        # 从近到远：每个可见采样把这一列从"它的仰角"涂到"之前最高点"，颜色按距离由深到浅
        lo_row = height
        for i in idx:
            r = row(ang[c, i])
            if r >= lo_row:
                continue
            shade = int(60 + 150 * logd[i])
            r0 = max(0, int(r))
            img[r0:lo_row, c] = (shade - 25, shade, shade - 35)
            lo_row = r0
        if idx.size:
            j = idx[-1]
            sky_ang[c], sky_dist[c] = ang[c, j], dist[j]
            rr = int(round(row(ang[c, j])))
            if 0 <= rr < height:
                img[max(0, rr - 1):rr + 2, c] = (220, 30, 30)
        _ = prev
    return Image.fromarray(img), sky_ang, sky_dist


def _font(size: int):
    for p in ("/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def annotate(im: Image.Image, azimuths: np.ndarray, pitch: float, vfov: float, title: str) -> Image.Image:
    W, H = im.size
    d = ImageDraw.Draw(im)
    f = _font(16)
    hr = (pitch + vfov / 2) / vfov * (H - 1)
    d.line([(0, hr), (W, hr)], fill=(90, 90, 200), width=1)           # 眼睛高度的水平线
    names = {0: "北", 45: "东北", 90: "东", 135: "东南", 180: "南", 225: "西南", 270: "西", 315: "西北"}
    span = azimuths[-1] - azimuths[0]
    stepdeg = 5 if span <= 60 else 10 if span <= 150 else 30
    first = math.ceil(azimuths[0] / stepdeg) * stepdeg
    for a in np.arange(first, azimuths[-1] + 1e-6, stepdeg):
        x = (a - azimuths[0]) / span * (W - 1)
        d.line([(x, H - 14), (x, H)], fill="black", width=1)
        lab = f"{a % 360:.0f}°" + (names.get(int(a % 360), ""))
        d.text((x + 3, H - 32), lab, fill="black", font=f)
    d.rectangle([0, 0, W, 24], fill=(0, 0, 0))
    d.text((6, 3), title, fill="yellow", font=f)
    return im



# ---------------------------------------------------------------- scan ----
# 线状设施 × 地形筛选。方法见 references/corridors.md 4.3。
# 和 view/profile 的区别：这里要覆盖一个省级大区，切片数远超 DEM 类的 400 块上限，
# 所以自己拼一张只填"用得到的切片"的大图，按最近邻采样（z10 一格约 150 m，插值没意义）。


def _tile_xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(d))


class _Mosaic:
    """一批 Terrarium 切片拼成的大图，最近邻采样。没下到的切片留 0（当海平面）。"""

    def __init__(self, need: set[tuple[int, int]], zoom: int, cache: Path, proxy: str | None, threads: int):
        cache.mkdir(parents=True, exist_ok=True)
        self.z = zoom
        self.tx0 = min(t[0] for t in need)
        self.ty0 = min(t[1] for t in need)
        nx = max(t[0] for t in need) - self.tx0 + 1
        ny = max(t[1] for t in need) - self.ty0 + 1
        gb = nx * ny * 256 * 256 * 2 / 1e9
        print(f"拼图 {nx}x{ny} 块，{gb:.2f} GB 内存", file=sys.stderr)
        self.h = np.zeros((ny * 256, nx * 256), dtype=np.int16)
        jobs = sorted(need)
        done = 0
        with ThreadPoolExecutor(threads) as ex:
            for (x, y), arr in zip(jobs, ex.map(lambda t: _fetch(zoom, t[0], t[1], cache, proxy), jobs)):
                self.h[(y - self.ty0) * 256:(y - self.ty0 + 1) * 256,
                       (x - self.tx0) * 256:(x - self.tx0 + 1) * 256] = np.clip(arr, -500, 9000).astype(np.int16)
                done += 1
                if done % 200 == 0:
                    print(f"  切片 {done}/{len(jobs)}", file=sys.stderr)

    def sample(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        n = 256 * 2 ** self.z
        x = ((lon + 180) / 360 * n - self.tx0 * 256).astype(int)
        y = ((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n - self.ty0 * 256).astype(int)
        x = np.clip(x, 0, self.h.shape[1] - 1)
        y = np.clip(y, 0, self.h.shape[0] - 1)
        return self.h[y, x].astype(np.float32)


def _line_points(gj: dict, step: float, skip: list[tuple[str, str]], bbox: tuple[float, float, float, float] | None):
    """沿每条 LineString 每 step 米取一个点，返回 [(lat, lon, properties)]。"""
    pts = []
    n_line = n_skip = 0
    for f in gj.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") != "LineString" or len(g.get("coordinates", [])) < 2:
            continue
        tags = f.get("properties", {}) or {}
        n_line += 1
        if any(str(tags.get(k, "")) == v for k, v in skip):
            n_skip += 1
            continue
        c = [(y, x) for x, y in g["coordinates"]]                     # geojson 是 lon,lat
        if bbox and not (min(p[0] for p in c) <= bbox[2] and max(p[0] for p in c) >= bbox[0]
                         and min(p[1] for p in c) <= bbox[3] and max(p[1] for p in c) >= bbox[1]):
            continue
        got = 0
        acc = 0.0
        for i in range(1, len(c)):
            d = _haversine(c[i - 1], c[i])
            for k in range(int((acc + d) // step)):
                t = (step * (k + 1) - acc) / d if d else 0
                pts.append((c[i - 1][0] + (c[i][0] - c[i - 1][0]) * t,
                            c[i - 1][1] + (c[i][1] - c[i - 1][1]) * t, tags))
                got += 1
            acc = (acc + d) % step
        # 整条比 step 还短、或首尾几乎重合（环线）的，补一个中点，免得整条线漏掉
        if got == 0 or _haversine(c[0], c[-1]) < step:
            pts.append((c[len(c) // 2][0], c[len(c) // 2][1], tags))
    if bbox:
        s, w, n, e = bbox
        pts = [p for p in pts if s <= p[0] <= n and w <= p[1] <= e]
    print(f"线 {n_line} 条（按 --skip-tag 跳过 {n_skip} 条），采样点 {len(pts)} 个", file=sys.stderr)
    return pts


def _cluster(hits: list[dict], km: float) -> list[dict]:
    """按 max_ang 从大到小贪心聚簇：最陡的点当簇代表，km 内的点归入，代表加一个 n=簇内点数。"""
    order = sorted(hits, key=lambda h: -h["max_ang"])
    used = [False] * len(order)
    out = []
    for i, p in enumerate(order):
        if used[i]:
            continue
        n = 0
        for j in range(i, len(order)):
            if not used[j] and _haversine((p["lat"], p["lon"]), (order[j]["lat"], order[j]["lon"])) <= km * 1000:
                used[j] = True
                n += 1
        out.append({**p, "n": n})
    return out


def _cmd_scan(args) -> None:
    az_step = args.az_step
    naz = int(round(360 / az_step))
    if abs(naz * az_step - 360) > 1e-6:
        sys.exit("--az-step 必须能整除 360")
    if args.step <= 0 or args.near_step <= 0 or args.near_radius < 0:
        sys.exit("--step / --near-step 要大于 0，--near-radius 不能为负")
    dist = np.array([float(x) for x in args.dist.split(",")], dtype=float)
    near = np.arange(0, args.near_radius + 1e-6, args.near_step, dtype=float)
    skip = []
    for s in (args.skip_tag or ["electrified=no"]):
        if s.lower() in ("none", "-"):
            continue
        if "=" not in s:
            sys.exit(f"--skip-tag 要写成 键=值，收到 {s!r}")
        k, v = s.split("=", 1)
        skip.append((k, v))
    bbox = None
    if args.bbox:
        b = [float(x) for x in args.bbox.split(",")]
        if len(b) != 4:
            sys.exit("--bbox 要 4 个数：s,w,n,e")
        bbox = (min(b[0], b[2]), min(b[1], b[3]), max(b[0], b[2]), max(b[1], b[3]))

    gj = json.loads(Path(args.lines).read_text())
    pts = _line_points(gj, args.step, skip, bbox)
    if not pts:
        sys.exit("采样点为 0：--bbox 圈空了，或 geojson 里没有 LineString")

    reach = float(dist.max()) + 500                                   # 多留半公里，采样点落在切片边上也够用
    need: set[tuple[int, int]] = set()
    for lat, lon, _ in pts:
        x, y = _tile_xy(lat, lon, args.zoom)
        r = reach / (40075016.7 * math.cos(math.radians(lat)) / 2 ** args.zoom)
        for tx in range(int(x - r), int(x + r) + 1):
            for ty in range(int(y - r), int(y + r) + 1):
                need.add((tx, ty))
    print(f"要 {len(need)} 块 z{args.zoom} 切片", file=sys.stderr)
    if len(need) > args.max_tiles:
        sys.exit(f"切片 {len(need)} 块 > --max-tiles {args.max_tiles}：缩小 --bbox、调低 --zoom，或分块跑")
    mos = _Mosaic(need, args.zoom, args.cache, args.proxy, args.threads)

    az = np.arange(0, 360, az_step)
    min_low = int(round((args.min_low_deg if args.min_low_deg is not None else args.flat_run) / az_step))
    need_run = int(round(args.flat_run / az_step))
    cap = int(round(args.flat_run_cap / az_step))
    hits = []
    for idx, (lat, lon, tags) in enumerate(pts):
        if idx and idx % 2000 == 0:
            print(f"  扫描 {idx}/{len(pts)}，命中 {len(hits)}", file=sys.stderr)
        ln, lo = _dest_np(lat, lon, az, near)
        hn = mos.sample(ln, lo)
        if hn.max() - hn.min() > args.near_flat:                      # 近处不平：山谷、山腰，不是画面里那种平地
            continue
        h0 = float(np.median(hn))
        la, lo = _dest_np(lat, lon, az, dist)
        h = mos.sample(la, lo)
        ang = np.degrees(np.arctan2(h - h0 - args.eye, dist[None, :]))  # 几公里内地球曲率 <5 m，和 z10 的误差比可以忽略
        hor = ang.max(axis=1)                                         # 每个方位的地平线仰角
        rel = (h - h0).max(axis=1)
        mt = hor >= args.min_peak
        low = hor < args.max_low
        if not mt.any() or low.sum() < min_low:
            continue
        best = 0                                                      # 紧挨山体的那段平地平线有多长
        for i in range(naz):
            if not mt[i]:
                continue
            for sgn in (-1, 1):
                k = run = 0
                while k < cap:
                    jj = (i + sgn * (k + 1)) % naz
                    if low[jj]:
                        run += 1
                    elif run == 0 and k < 2:                          # 允许山脚到平地之间有 2 格过渡
                        pass
                    else:
                        break
                    k += 1
                best = max(best, run)
        if best < need_run:
            continue
        i = int(np.argmax(hor))
        hits.append({"lat": round(lat, 5), "lon": round(lon, 5), "h0": round(h0), "max_ang": round(float(hor[i]), 1),
                     "az": float(az[i]), "relief": round(float(rel[i])), "flat_run_deg": best * az_step,
                     "name": tags.get("name", ""), "hs": tags.get("highspeed", ""),
                     "elec": tags.get("electrified", ""), "id": tags.get("id", tags.get("@id", ""))})

    clusters = _cluster(hits, args.cluster_km)
    print(f"命中 {len(hits)} 点 → {len(clusters)} 簇", file=sys.stderr)
    out = {
        "params": {"lines": str(args.lines), "bbox": list(bbox) if bbox else None, "step_m": args.step,
                   "zoom": args.zoom, "near_flat_m": args.near_flat, "near_radius_m": args.near_radius,
                   "min_peak_deg": args.min_peak, "max_low_deg": args.max_low, "flat_run_deg": args.flat_run,
                   "min_low_deg": args.min_low_deg if args.min_low_deg is not None else args.flat_run,
                   "eye_m": args.eye, "az_step_deg": az_step, "dist_m": dist.tolist(),
                   "skip_tag": [f"{k}={v}" for k, v in skip], "cluster_km": args.cluster_km},
        "n_samples": len(pts), "n_hits": len(hits), "n_clusters": len(clusters),
        "hits": hits, "clusters": clusters,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(f"→ {args.out}", file=sys.stderr)
    if args.clusters_out:
        Path(args.clusters_out).write_text(json.dumps(clusters, ensure_ascii=False, indent=0))
        print(f"→ {args.clusters_out}（只有簇列表）", file=sys.stderr)


# ---------------------------------------------------------------- ridge ----
# 照片山脊取点。方法见 references/geometry.md 7.4：逐列从上往下找天空→山体的亮度突变。


def _focal_px(photo: Path, w: int, h: int, f0_arg: float | None, f35_default: float):
    """照片焦距（像素）。优先级：--f0 > EXIF 的 35mm 等效焦距 > 按 --f35 假设。
    35mm 等效焦距按对角线换算：f_px = f35 / 43.27 × 对角线像素；照片缩过尺寸也成立。
    返回 (f_px, 来源, f35)。"""
    diag = math.hypot(w, h)
    if f0_arg:
        return float(f0_arg), "arg", round(f0_arg * 43.2666 / diag, 1)
    try:
        ifd = Image.open(photo).getexif().get_ifd(0x8769)
        f35 = ifd.get(0xA405)                                          # FocalLengthIn35mmFilm
        if f35 and float(f35) > 0:
            return float(f35) / 43.2666 * diag, "exif", float(f35)
    except Exception:  # noqa: BLE001
        pass
    return f35_default / 43.2666 * diag, "assumed", f35_default


def _sky_edge(prof: np.ndarray, ymin: int, ymax: int, k: int, drop: float, hold: int) -> int | None:
    """一列亮度剖面里，从上往下找第一处"上面 k 行均值比下面 k 行均值高出 drop、且再往下 hold 行仍然暗"的行，
    再在它 ±k 行内取梯度最大处。返回山体第一行的行号；找不到返回 None。
    hold 是为了跳过电线、天线这类竖向只有几像素的东西。"""
    n = len(prof)
    cs = np.concatenate([[0.0], np.cumsum(prof, dtype=np.float64)])
    y = np.arange(max(ymin, k), min(ymax, n - k - hold))
    if y.size == 0:
        return None
    above = (cs[y] - cs[y - k]) / k
    below = (cs[y + k] - cs[y]) / k
    held = (cs[y + k + hold] - cs[y + k]) / hold
    ok = (above - below >= drop) & (above - held >= drop)
    if not ok.any():
        return None
    y0 = int(y[np.argmax(ok)])
    yy = np.arange(max(k, y0 - k), min(n - k, y0 + k + 1))
    g = (cs[yy] - cs[yy - k]) / k - (cs[yy + k] - cs[yy]) / k
    return int(yy[np.argmax(g)])


def _cmd_ridge(args) -> None:
    im = Image.open(args.photo).convert("RGB")
    W, H = im.size
    a = np.asarray(im, dtype=np.float32)
    L = a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114
    if not (0 <= args.x0 < args.x1 < W):
        sys.exit(f"--x0/--x1 要满足 0 ≤ x0 < x1 < 宽 {W}")
    if args.step <= 0:
        sys.exit("--step 要大于 0")
    ymin = args.ymin if args.ymin is not None else 0
    ymax = args.ymax if args.ymax is not None else H
    f0, f_src, f35 = _focal_px(args.photo, W, H, args.f0, args.f35)

    def edge(x: int) -> int | None:
        x0, x1 = max(0, x - args.halfw), min(W, x + args.halfw + 1)
        return _sky_edge(L[:, x0:x1].mean(axis=1), ymin, ymax, args.k, args.drop, args.hold)

    ridge, missing = [], []
    for x in range(args.x0, args.x1 + 1, args.step):
        y = edge(x)
        (ridge.append([x, y]) if y is not None else missing.append(x))
    flat = None
    flat_rows: list[int] = []
    flat_pts: list[list[int]] = []                                    # 画核对图用：flat_rows 只有行号，没找到突变的列不在里面，按序号对不回列
    if args.flat:
        b = args.flat.split(":")
        if len(b) != 2:
            sys.exit("--flat 要写成 x0:x1")
        flat = [int(b[0]), int(b[1])]
        if not (0 <= flat[0] < flat[1] < W):
            sys.exit(f"--flat 要满足 0 ≤ x0 < x1 < 宽 {W}")
        for x in range(flat[0], flat[1] + 1, args.step):
            y = edge(x)
            if y is not None:
                flat_rows.append(y)
                flat_pts.append([x, y])
    if args.hrow is not None:
        hrow, h_src = float(args.hrow), "arg"
    elif flat_rows:
        hrow, h_src = float(np.median(flat_rows)), "flat"
    else:
        hrow, h_src = H / 2, "center"
    if len(ridge) < 3:
        print(f"警告：只取到 {len(ridge)} 个山脊点（缺 {len(missing)} 列），fit 至少要 3 个；调 --drop/--ymin/--ymax 或看 --png", file=sys.stderr)
    out = {
        "photo": str(args.photo), "image_size": [W, H], "cx": W / 2,
        "ridge": ridge, "missing_cols": missing,
        "flat": flat, "flat_rows": flat_rows,
        "hrow": round(hrow, 1), "hrow_source": h_src,
        "f0": round(f0, 1), "f0_source": f_src, "f35_equiv": f35,
        "params": {"x0": args.x0, "x1": args.x1, "step": args.step, "ymin": ymin, "ymax": ymax,
                   "drop": args.drop, "k": args.k, "hold": args.hold, "halfw": args.halfw},
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False))
    src_txt = {"arg": "--f0", "exif": "EXIF 35mm 等效", "assumed": f"没有 EXIF，按 {f35} mm 等效假设"}[f_src]
    h_txt = {"arg": "--hrow", "flat": f"--flat 列里天空→地面的中位行（{len(flat_rows)} 列）", "center": "没给 --flat，取画面中线"}[h_src]
    print(f"{W}x{H}  山脊 {len(ridge)} 点（缺 {len(missing)} 列）  平地平线列 {flat}  "
          f"hrow {hrow:.0f}（{h_txt}）  f0 {f0:.0f} px（{src_txt}，水平视角 {2 * math.degrees(math.atan(W / 2 / f0)):.1f}°）→ {args.out}")
    if args.png:
        d = ImageDraw.Draw(im)
        d.line([(0, hrow), (W, hrow)], fill=(80, 80, 255), width=1)
        if flat:
            d.line([(flat[0], hrow), (flat[1], hrow)], fill=(0, 200, 255), width=4)
            for x, y in flat_pts:
                d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=(0, 200, 255), width=2)
        for x, y in ridge:
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(255, 220, 0))
        for x in missing:
            d.line([(x, ymin), (x, ymax - 1)], fill=(255, 0, 0), width=1)
        d.text((8, 8), f"ridge {len(ridge)} pts  hrow {hrow:.0f} ({h_src})  f0 {f0:.0f}px ({f_src})", fill="yellow", font=_font(20))
        im.save(args.png, quality=90)
        print(f"检查图 → {args.png}（黄点=山脊点，红竖线=没找到的列，蓝线=hrow，青线=平地平线列范围）")


# ------------------------------------------------------------------ fit ----
# 天际线批量打分。方法见 references/geometry.md 7.4；设施距离约束见 corridors.md 4.3。
# 每个候选机位算一圈 360° 地平线 hor(az)，照片山脊点换成 (方位偏移, 仰角) 后在所有朝向上一次比对：
#   rms = 山脊仰角残差的 RMS（残差中位数当地平线偏移 cc，限 ±cc_max）
#   flatpen = 平地平线列上 max(0, hor - cc - flat_clear) 的均值
#   score = rms + flat_w × flatpen
# 给了 --line 时再加：对每个朝向，设施采样点落在画面左/中/右三个方位窗内的最近距离 dL/dC/dR，
#   line_pen = 各自落在 --line-dist 区间外的米数 / --line-scale (+ 顺序不对罚 1)
#   total = score + line_w × line_pen；没给 --line 时 total = score。


def _parse_pairs(s: str, name: str, n: int = 3, sep: str = ",", rng: str = ":") -> list[tuple[float, float]]:
    out = []
    for part in s.split(sep):
        b = part.split(rng)
        if len(b) != 2:
            sys.exit(f"{name} 每段要写成 a{rng}b，收到 {part!r}")
        out.append((float(b[0]), float(b[1])))
    if len(out) != n:
        sys.exit(f"{name} 要 {n} 段，收到 {len(out)} 段")
    return out


def _load_centers(args) -> list[dict]:
    if args.at:
        lat, lon = map(float, args.at.split(","))
        return [{"lat": lat, "lon": lon, "name": "", "src_idx": 0}]
    j = json.loads(Path(args.hits).read_text())
    items = j["clusters"] if isinstance(j, dict) and "clusters" in j else j
    if not isinstance(items, list):
        sys.exit("--hits 要是 scan 的输出（带 clusters 字段）或簇/点的列表")
    centers = []
    for i, c in enumerate(items):
        if "lat" not in c or "lon" not in c:
            sys.exit(f"--hits 第 {i} 项没有 lat/lon")
        centers.append({**c, "src_idx": c.get("src_idx", i)})
    if args.select:
        want = [int(x) for x in args.select.split(",")]
        bad = [i for i in want if not 0 <= i < len(centers)]
        if bad:
            sys.exit(f"--select 里 {bad} 超出范围 0–{len(centers) - 1}")
        centers = [centers[i] for i in want]
    return centers


def _skyline_xy(hor: np.ndarray, az: np.ndarray, H: float, f: float, cc: float, cx: float, hrow: float, half_w: float):
    """把 360° 地平线按 fit 用的针孔模型投到照片像素：x = cx + f·tan(方位偏移)，y = hrow − f·tan(仰角 − cc)。"""
    rel = (az - H + 180) % 360 - 180
    lim = math.degrees(math.atan(half_w / f)) + 1
    m = np.abs(rel) <= lim
    x = cx + f * np.tan(np.radians(rel[m]))
    y = hrow - f * np.tan(np.radians(hor[m] - cc))
    o = np.argsort(x)
    return list(zip(x[o].tolist(), y[o].tolist()))


def _fit_sheet(recs: list[dict], ridge: dict, photo: Path | None, out: Path, args, az: np.ndarray, dist_n: int) -> None:
    W, H = ridge["image_size"]
    tw = args.sheet_width
    s = tw / W
    th = int(H * s)
    base = None
    if photo and photo.exists():
        base = Image.open(photo).convert("RGB").resize((tw, th))
    cols = max(1, args.sheet_cols)
    rows = math.ceil(len(recs) / cols)
    sheet = Image.new("RGB", (tw * cols, th * rows), "white")
    font = _font(13)
    for i, r in enumerate(recs):
        tile = base.copy() if base else Image.new("RGB", (tw, th), (120, 120, 120))
        d = ImageDraw.Draw(tile)
        hrow, f, cx = ridge["hrow"], r["f"], ridge.get("cx", W / 2)
        d.line([(0, hrow * s), (tw, hrow * s)], fill=(80, 80, 255), width=1)
        if ridge.get("flat"):
            d.line([(ridge["flat"][0] * s, hrow * s), (ridge["flat"][1] * s, hrow * s)], fill=(0, 200, 255), width=3)
        try:
            dem = DEM(tuple(r["cam"]), args.range + 500, args.zoom, args.cache, args.proxy)
            ang, _ = cast(dem, tuple(r["cam"]), r["g"] + args.eye, az, args.range, near=args.near, n=dist_n)
            pts = _skyline_xy(ang.max(axis=1), az, r["H"], f, r["cc"], cx, hrow, W / 2)
            d.line([(x * s, y * s) for x, y in pts], fill=(255, 40, 40), width=2)
        except SystemExit as e:
            d.text((6, th - 20), f"DEM 失败：{e}", fill="red", font=font)
        for x, y in ridge["ridge"]:
            d.ellipse([x * s - 2, y * s - 2, x * s + 2, y * s + 2], fill=(255, 220, 0))
        line_txt = f"  L/C/R {r['dL']:.0f}/{r['dC']:.0f}/{r['dR']:.0f} pen {r['line_pen']:.2f}" if "line_pen" in r else ""
        txt = (f"#{i + 1} hit{r['hit']} {r['name'] or '-'}  {r['cam'][0]:.5f},{r['cam'][1]:.5f}\n"
               f"H {r['H']:.1f}  f {f:.0f}  cc {r['cc']:+.2f}  rms {r['rms']:.3f}  flat {r['flatpen']:.3f}{line_txt}\n"
               f"total {r['total']:.3f}")
        d.rectangle([0, 0, tw, 46], fill=(0, 0, 0))
        d.text((4, 2), txt, fill="yellow", font=font)
        sheet.paste(tile, ((i % cols) * tw, (i // cols) * th))
    sheet.save(out, quality=88)
    print(f"叠图 → {out}（红线=合成天际线，黄点=照片山脊点，蓝线=hrow，青线=平地平线列）", file=sys.stderr)


def _cmd_fit(args) -> None:
    if bool(args.hits) == bool(args.at):
        sys.exit("--hits 和 --at 二选一")
    ridge = json.loads(Path(args.ridge).read_text())
    RX = np.array([p[0] for p in ridge["ridge"]], float)
    RY = np.array([p[1] for p in ridge["ridge"]], float)
    if RX.size < 3:
        sys.exit(f"ridge.json 里只有 {RX.size} 个山脊点，至少要 3 个")
    W, Hh = ridge["image_size"]
    hrow, f0, cx = float(ridge["hrow"]), float(ridge["f0"]), float(ridge.get("cx", W / 2))
    flat = ridge.get("flat")
    FLX = np.arange(flat[0], flat[1] + 1e-6, args.flat_step, dtype=float) if flat else np.zeros(0)
    fscales = [float(x) for x in args.focal_scales.split(",")]
    if args.grid <= 0 or args.radius < 0 or args.nsamp < 2 or args.near <= 0 or args.range <= args.near:
        sys.exit("--grid > 0、--radius ≥ 0、--nsamp ≥ 2、0 < --near < --range")
    az_step = args.az_step
    naz = int(round(360 / az_step))
    if abs(naz * az_step - 360) > 1e-6:
        sys.exit("--az-step 必须能整除 360")
    AZ = np.arange(naz) * az_step
    HS = np.arange(naz)

    centers = _load_centers(args)
    if not centers:
        sys.exit("没有候选簇")

    # 线状设施采样点（可选）
    LP = None
    if args.line:
        if not args.line_dist:
            sys.exit("给了 --line 就要给 --line-dist L:C:R（三段距离区间，如 350-750:550-900:800-1700）")
        wins = _parse_pairs(args.line_win, "--line-win", 3, ",", ":")
        dwin = _parse_pairs(args.line_dist, "--line-dist", 3, ":", "-")
        scales = [float(x) for x in args.line_scale.split(",")]
        if len(scales) != 3 or min(scales) <= 0:
            sys.exit("--line-scale 要 3 个正数，逗号分隔")
        skip = []
        for s_ in (args.skip_tag or ["electrified=no"]):
            if s_.lower() in ("none", "-"):
                continue
            if "=" not in s_:
                sys.exit(f"--skip-tag 要写成 键=值，收到 {s_!r}")
            skip.append(tuple(s_.split("=", 1)))
        reach_deg = (args.radius + args.line_reach) / 110540 + 0.01
        lat_c = [c["lat"] for c in centers]
        lon_c = [c["lon"] for c in centers]
        bbox = (min(lat_c) - reach_deg, min(lon_c) - reach_deg * 1.2, max(lat_c) + reach_deg, max(lon_c) + reach_deg * 1.2)
        gj = json.loads(Path(args.line).read_text())
        pts = _line_points(gj, args.line_sample, skip, bbox)
        LP = np.array([[p[0], p[1]] for p in pts], dtype=float) if pts else np.zeros((0, 2))
        print(f"设施采样点 {len(LP)} 个（每 {args.line_sample} m）", file=sys.stderr)

    ring_az = np.arange(0, 360, 45.0)
    ring_d = np.array([0.0, args.cam_flat_radius / 2, args.cam_flat_radius])
    done: set[tuple[int, int]] = set()
    recs: list[dict] = []
    clusters_out: list[dict] = []
    skipped = {"not_flat": 0, "no_peak": 0, "no_line": 0, "dup": 0}
    grid_pts = [(dx, dy) for dy in np.arange(-args.radius, args.radius + 1e-6, args.grid)
                for dx in np.arange(-args.radius, args.radius + 1e-6, args.grid) if dx * dx + dy * dy <= args.radius ** 2]
    if args.radius == 0:
        grid_pts = [(0.0, 0.0)]
    for ci, c in enumerate(centers):
        lat, lon = float(c["lat"]), float(c["lon"])
        name = c.get("name", "")
        try:
            dem = DEM((lat, lon), args.radius + args.range + 500, args.zoom, args.cache, args.proxy)
        except SystemExit as e:
            print(f"簇 {c['src_idx']} {name}：DEM 失败（{e}），跳过", file=sys.stderr)
            continue
        kx = 111320 * math.cos(math.radians(lat))
        sub = None
        if LP is not None and len(LP):
            m = (np.abs(LP[:, 0] - lat) * 110540 < args.radius + args.line_reach) & (np.abs(LP[:, 1] - lon) * kx < args.radius + args.line_reach)
            sub = LP[m]
        n_c = 0
        best_c = None
        for dx, dy in grid_pts:
            dx, dy = float(dx), float(dy)
            clat = lat + dy / 110540
            clon = lon + dx / kx
            key = (round(clat * 110540 / args.grid), round(clon * kx / args.grid))
            if key in done:
                skipped["dup"] += 1
                continue
            done.add(key)
            rla, rlo = _dest_np(clat, clon, ring_az, ring_d)
            g = dem.sample(rla, rlo)
            if g.max() - g.min() > args.cam_flat:
                skipped["not_flat"] += 1
                continue
            g0 = float(g[:, 0].mean())
            ang, _ = cast(dem, (clat, clon), g0 + args.eye, AZ, args.range, near=args.near, n=args.nsamp)
            hor = ang.max(axis=1)
            if hor.max() < args.min_peak:
                skipped["no_peak"] += 1
                continue
            line_pen = None
            dmins = None
            if LP is not None:
                if sub is None or not len(sub):
                    skipped["no_line"] += 1
                    continue
                by = (sub[:, 0] - clat) * 110540
                bx = (sub[:, 1] - clon) * 111320 * math.cos(math.radians(clat))
                bd = np.hypot(bx, by)
                baz = np.degrees(np.arctan2(bx, by)) % 360
                off = (baz[None, :] - AZ[:, None] + 180) % 360 - 180            # (naz, n点)
                far = bd > args.line_min
                dmins = []
                for lo_, hi_ in wins:
                    mm = (off > lo_) & (off < hi_) & far[None, :]
                    dmins.append(np.where(mm, bd[None, :], np.inf).min(axis=1))
                line_pen = np.zeros(naz)
                for dm, (dlo, dhi), sc in zip(dmins, dwin, scales):
                    line_pen += np.maximum(0, dlo - dm) / sc + np.maximum(0, dm - dhi) / sc
                if args.line_order == "asc":
                    line_pen += ((dmins[0] >= dmins[1]) | (dmins[1] >= dmins[2])) * 1.0
                elif args.line_order == "desc":
                    line_pen += ((dmins[0] <= dmins[1]) | (dmins[1] <= dmins[2])) * 1.0
                if not np.isfinite(line_pen).any():
                    skipped["no_line"] += 1
                    continue
            best = None
            for fs in fscales:
                f = f0 * fs
                r_off = np.degrees(np.arctan((RX - cx) / f))
                r_el = np.degrees(np.arctan((hrow - RY) / f))
                ri = (HS[:, None] + np.round(r_off / az_step).astype(int)[None, :]) % naz
                diff = hor[ri] - r_el[None, :]
                cc = np.clip(np.median(diff, axis=1), -args.cc_max, args.cc_max)
                rms = np.sqrt(np.mean((diff - cc[:, None]) ** 2, axis=1))
                if FLX.size:
                    fl_off = np.degrees(np.arctan((FLX - cx) / f))
                    fi = (HS[:, None] + np.round(fl_off / az_step).astype(int)[None, :]) % naz
                    pen = np.mean(np.clip(hor[fi] - cc[:, None] - args.flat_clear, 0, None), axis=1)
                else:
                    pen = np.zeros(naz)
                score = rms + args.flat_w * pen
                total = score + args.line_w * line_pen if line_pen is not None else score
                k = int(np.argmin(total))
                if not np.isfinite(total[k]):
                    continue
                if best is None or total[k] < best["total"]:
                    best = {"hit": c["src_idx"], "name": name, "hit_ll": [round(lat, 5), round(lon, 5)],
                            "cam": [round(clat, 5), round(clon, 5)],
                            "d": round(math.hypot(dx, dy)), "brg": round(math.degrees(math.atan2(dx, dy)) % 360),
                            "g": round(g0, 1), "H": round(k * az_step, 2), "fs": fs, "f": round(f, 1),
                            "cc": round(float(cc[k]), 2), "rms": round(float(rms[k]), 3), "flatpen": round(float(pen[k]), 3),
                            "score": round(float(score[k]), 3)}
                    if line_pen is not None:
                        best.update({"dL": round(float(dmins[0][k])), "dC": round(float(dmins[1][k])), "dR": round(float(dmins[2][k])),
                                     "line_pen": round(float(line_pen[k]), 3)})
                    best["total"] = round(float(total[k]), 3)
            if best is None:
                skipped["no_line"] += 1
                continue
            recs.append(best)
            n_c += 1
            if best_c is None or best["total"] < best_c["total"]:
                best_c = best
        clusters_out.append({"hit": c["src_idx"], "name": name, "hit_ll": [round(lat, 5), round(lon, 5)],
                             "n": c.get("n"), "max_ang": c.get("max_ang"), "n_cams": n_c, "best": best_c})
        print(f"簇 {ci + 1}/{len(centers)} hit{c['src_idx']} {name or '-'}：打分 {n_c} 个机位"
              + (f"，最好 total {best_c['total']}  H {best_c['H']}  cam {best_c['cam']}" if best_c else "，没有机位通过筛选"), file=sys.stderr)

    recs.sort(key=lambda r: r["total"])
    clusters_out.sort(key=lambda x: x["best"]["total"] if x["best"] else float("inf"))
    for i, x in enumerate(clusters_out):
        x["rank"] = i + 1
    hfov = 2 * math.degrees(math.atan(cx / f0))
    out = {
        "params": {"hits": args.hits, "at": args.at, "select": args.select, "ridge": str(args.ridge),
                   "radius_m": args.radius, "grid_m": args.grid, "zoom": args.zoom, "focal_scales": fscales,
                   "az_step_deg": az_step, "near_m": args.near, "range_m": args.range, "nsamp": args.nsamp, "eye_m": args.eye,
                   "cam_flat_m": args.cam_flat, "cam_flat_radius_m": args.cam_flat_radius, "min_peak_deg": args.min_peak,
                   "cc_max_deg": args.cc_max, "flat_clear_deg": args.flat_clear, "flat_w": args.flat_w, "flat_step_px": args.flat_step,
                   "line": args.line, "line_dist": args.line_dist, "line_win": args.line_win if args.line else None,
                   "line_scale": args.line_scale if args.line else None, "line_order": args.line_order if args.line else None,
                   "line_w": args.line_w, "line_min_m": args.line_min, "line_sample_m": args.line_sample, "line_reach_m": args.line_reach,
                   "photo": {"f0_px": f0, "hrow": hrow, "cx": cx, "hfov_deg_at_fs1": round(hfov, 1), "n_ridge": int(RX.size), "flat": flat}},
        "n_clusters": len(clusters_out), "n_cams": len(recs), "n_skipped": skipped,
        "clusters": clusters_out,
        "cams": recs[:args.keep],
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=0))
    print(f"簇 {len(clusters_out)}，机位 {len(recs)}，跳过 {skipped} → {args.out}", file=sys.stderr)
    for x in clusters_out[:min(args.top, 10)]:
        b = x["best"]
        if b:
            line_txt = f"  L/C/R {b['dL']}/{b['dC']}/{b['dR']} pen {b['line_pen']}" if "line_pen" in b else ""
            print(f"  {x['rank']:>3}. hit{x['hit']} {x['name'] or '-'}  cam {b['cam']}  H {b['H']}  f {b['f']:.0f}  "
                  f"rms {b['rms']}  flat {b['flatpen']}{line_txt}  total {b['total']}", file=sys.stderr)
    if args.sheet:
        top = [x["best"] for x in clusters_out if x["best"]][:args.top] if len(clusters_out) > 1 else recs[:args.top]
        if not top:
            print("没有可画的机位，不出叠图", file=sys.stderr)
            return
        photo = Path(args.photo) if args.photo else None
        if photo is None and ridge.get("photo"):
            # ridge.json 里记的是命令行原样，可能是相对路径：先按当前目录，再按 ridge.json 所在目录
            cands = [Path(ridge["photo"]), Path(args.ridge).parent / ridge["photo"]]
            photo = next((p for p in cands if p.exists()), cands[0])
        if photo is None or not photo.exists():
            print("找不到照片（--overlay 没给、ridge.json 里的 photo 路径也找不到），叠图画在灰底上", file=sys.stderr)
            photo = None
        _fit_sheet(top, ridge, photo, Path(args.sheet), args, AZ, args.nsamp)


def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。
    fit 的 --line-win -27:-21,-3:3,18:27 也是这种情况（逗号或冒号分隔的一串数）。"""
    return [" " + a if re.match(r"^-\d[\d.]*([,:]-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--cache", type=Path, default=Path(".geo-cache/dem"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("elev")
    e.add_argument("--at", required=True)
    e.add_argument("--zoom", type=int, default=13)

    def common(sp):
        sp.add_argument("--at", required=True, help="候选机位 lat,lon（WGS84）")
        g = sp.add_mutually_exclusive_group()
        g.add_argument("--height", type=float, default=1.6, help="离地高度 m（楼上拍就填楼层×3）")
        g.add_argument("--alt", type=float, help="绝对海拔 m（航拍、山顶机位用）")
        sp.add_argument("--heading", type=float, required=True, help="画面中心的罗盘方位")
        sp.add_argument("--hfov", type=float, default=65, help="水平视角，手机主摄横拍约 65，竖拍约 50")
        sp.add_argument("--range", type=float, default=30000, help="看多远（m）")
        sp.add_argument("--zoom", type=int, default=12, help="高程切片级别，12≈25–30 m 一格")
        sp.add_argument("--width", type=int, default=1400)
        sp.add_argument("--near", type=float, default=40, help="从多近开始采样 m；近处出现尖刺假山脊时调大到 150–300")
        sp.add_argument("--out", type=Path, required=True)

    v = sub.add_parser("view")
    common(v)
    v.add_argument("--pitch", type=float, default=0, help="画面中心的俯仰角，抬头为正")
    v.add_argument("--vfov", type=float, help="竖直视角，默认按 3:2 画幅从 hfov 推")
    v.add_argument("--photo", type=Path, help="把照片缩放到同宽，放在渲染图上方对照")
    v.add_argument("--roll", type=float, default=0, help="画面横滚角（顺时针为正），高楼俯拍、手持歪斜时用")
    v.add_argument("--overlay", action="store_true", help="另出一张：把合成天际线（红线）按同样的朝向/俯仰/视角直接画在照片上")

    pr = sub.add_parser("profile")
    common(pr)

    sc = sub.add_parser("scan", formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
沿线状设施逐点算 360° 地平线，筛"近处平 + 有山 + 山紧挨一段平地平线"的点，再聚簇。

用在：画面里只有一条铁路/公路/输电线和一座认不出的山，没有任何文字。先用
`osm.py geom '<过滤>' --bbox <大区> --out lines.geojson` 取线，再跑这一条把大区筛成几百片，
挑出的簇进 `terrain.py fit` 做天际线打分。方法和取值理由见 references/corridors.md 4.3。

阈值取照片估计值的一半左右：z10 一格约 150 m，山头被抹平，算出来的仰角比实际小。
实战里按照片估计的 6° 设阈值，真值附近一个点都没留下，放宽到 4.5° 才进来——宁多勿漏，数量交给下一步排序。

输出 JSON（--out）：
  {"params": {...原样记下这次用的全部阈值...},
   "n_samples": 采样点数, "n_hits": 命中点数, "n_clusters": 簇数,
   "hits":     [{"lat","lon","h0": 点位地面高程 m, "max_ang": 最高地平线仰角°,
                 "az": 那个方位°, "relief": 该方位最大相对高差 m, "flat_run_deg": 紧挨山体的平地平线长度°,
                 "name","hs"(highspeed),"elec"(electrified),"id": 线的 OSM 标签}, ...],
   "clusters": [{...同上..., "n": 簇内点数}, ...]}   # 按 max_ang 从大到小，簇代表就是最陡的那个点
--clusters-out 另写一份只有簇列表的 JSON（就是 clusters 字段本身）。""")
    sc.add_argument("--lines", required=True, help="线状设施 GeoJSON（osm.py geom 的输出），只读 LineString")
    sc.add_argument("--out", required=True, help="输出 JSON")
    sc.add_argument("--clusters-out", help="另写一份只含簇列表的 JSON")
    sc.add_argument("--bbox", help="只扫这个范围内的采样点 s,w,n,e（验证、分块跑时用；不给=整份 geojson）")
    sc.add_argument("--step", type=float, default=400, help="沿线每多少米取一个点（默认 400；300–500 都行）")
    sc.add_argument("--zoom", type=int, default=10, help="高程切片级别（默认 10，一格约 150 m，够看山体轮廓）")
    sc.add_argument("--near-flat", type=float, default=40,
                    help="近处起伏上限 m：点位周围 --near-radius 内高差超过它就算不平，丢弃（默认 40；放宽版用过 60）")
    sc.add_argument("--near-radius", type=float, default=1200, help="判断近处平不平的半径 m（默认 1200）")
    sc.add_argument("--near-step", type=float, default=300, help="近处采样间距 m（默认 300）")
    sc.add_argument("--min-peak", type=float, default=4.5,
                    help="山：地平线仰角至少多少度（默认 4.5，实战放宽后的值；原严格值 6，按那张照片估的，真值全被筛掉）")
    sc.add_argument("--max-low", type=float, default=1.2,
                    help="平：地平线仰角低于多少度算平地平线（默认 1.2；放宽版用过 1.5）")
    sc.add_argument("--flat-run", type=float, default=20,
                    help="紧挨山体的那段平地平线至少多少度（默认 20；原严格值 30）")
    sc.add_argument("--min-low-deg", type=float,
                    help="全周平地平线总量至少多少度（默认跟 --flat-run 一样）")
    sc.add_argument("--flat-run-cap", type=float, default=100, help="平地平线长度往一侧最多数到多少度（默认 100）")
    sc.add_argument("--eye", type=float, default=1.5, help="离地眼高 m（默认 1.5）")
    sc.add_argument("--az-step", type=float, default=5, help="方位步长°（默认 5，要能整除 360）")
    sc.add_argument("--dist", default="1500,2000,2500,3000,3500,4000,5000,6000,7000,8000,9000",
                    help="每个方位往外量的距离阶梯 m，逗号分隔（默认 1.5–9 km）")
    sc.add_argument("--skip-tag", action="append",
                    help="跳过带这个标签的线，键=值，可重复（默认 electrified=no；写 --skip-tag none 表示一条都不跳）")
    sc.add_argument("--cluster-km", type=float, default=3.5, help="聚簇半径 km（默认 3.5）")
    sc.add_argument("--threads", type=int, default=24, help="切片下载并发数（默认 24）")
    sc.add_argument("--max-tiles", type=int, default=4000,
                    help="要下的切片数上限，超了直接退出（默认 4000）。内存按这些切片的外接矩形算，"
                         "线网稀疏时能比切片数大好几倍，拼图前会先打印实际占用")

    rg = sub.add_parser("ridge", formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
照片山脊取点：在 --x0..--x1 每 --step 列，从上往下找天空→山体的亮度突变（上面 k 行比下面 k 行亮 --drop 以上、
且再往下 --hold 行仍然暗），取梯度最大的行当山脊像素。输出给 terrain.py fit 用。

--flat 给"画面里是平地平线"的列范围（左边或右边远处没山的那一段）；fit 用它罚"该平的地方被山挡住"。
没给 --hrow 时，地平线行取 --flat 列里天空→地面突变行的中位数；没有 --flat 就取画面中线。
注意这个估计落在远处树梢、桥面这类东西的顶上，比真正的 0° 地平线高 10–30 像素（那张照片自动估 909、
手定 935）；fit 里的地平线偏移 cc 只吸收 ±0.7°（f≈1300 px 时约 ±16 像素），远处有高物时手动给 --hrow。
焦距：--f0 > EXIF 35mm 等效焦距 > 按 --f35 假设（默认 26 mm，手机主摄），按对角线换算成像素，来源写进 f0_source。

输出 JSON（--out）：
  {"photo": 照片路径（命令行给什么记什么；fit 找不到时会按 ridge.json 所在目录再试一次）,
   "image_size": [宽, 高], "cx": 中心列,
   "ridge": [[x, y], ...],           # 山脊像素点，x 列 y 行（y 是山体第一行）
   "missing_cols": [x, ...],         # 没找到突变的列
   "flat": [x0, x1] | null, "flat_rows": [该范围内每列的突变行],
   "hrow": 地平线行, "hrow_source": "arg"|"flat"|"center",
   "f0": 焦距 px, "f0_source": "arg"|"exif"|"assumed", "f35_equiv": 35mm 等效焦距,
   "params": {...这次用的参数...}}
--png 另出一张检查图：黄点=山脊点，红竖线=没找到的列，蓝线=hrow，青线=平地平线列范围。先看图再进 fit。""")
    rg.add_argument("photo", type=Path, help="照片")
    rg.add_argument("--x0", type=int, required=True, help="山脊起始列（含）")
    rg.add_argument("--x1", type=int, required=True, help="山脊结束列（含）")
    rg.add_argument("--step", type=int, default=20, help="每多少列取一点（默认 20）")
    rg.add_argument("--flat", help="平地平线的列范围 x0:x1（如 0:280）；没有就不给")
    rg.add_argument("--hrow", type=float, help="地平线所在行；不给就按 --flat 列估，再没有就取画面中线")
    rg.add_argument("--f0", type=float, help="焦距 px，给了就不看 EXIF")
    rg.add_argument("--f35", type=float, default=26.0, help="没有 EXIF 时假设的 35mm 等效焦距 mm（默认 26，手机主摄；2x 长焦 48–52）")
    rg.add_argument("--ymin", type=int, help="只在这一行以下找（默认 0；天上有云或前景挡住时用）")
    rg.add_argument("--ymax", type=int, help="只在这一行以上找（默认画面底）")
    rg.add_argument("--drop", type=float, default=30, help="天空比山体至少亮多少（0–255 亮度，默认 30；雾大调到 15–20）")
    rg.add_argument("--k", type=int, default=4, help="比较亮度时上下各取几行（默认 4）")
    rg.add_argument("--hold", type=int, default=12, help="突变以下要持续暗多少行才算山（默认 12，用来跳过电线、天线）")
    rg.add_argument("--halfw", type=int, default=1, help="每列左右各再平均几列（默认 1，即 3 列）")
    rg.add_argument("--out", required=True, help="输出 ridge.json")
    rg.add_argument("--png", help="检查图路径")

    ft = sub.add_parser("fit", formatter_class=argparse.RawDescriptionHelpFormatter, description="""\
天际线批量打分：每个候选簇内摆机位网格（--radius 内每 --grid 米一个），每个机位算 360° 地平线，
把 ridge.json 的山脊点换成（方位偏移, 仰角），在所有朝向 × --focal-scales 上一次比对：
  rms     = 山脊仰角残差的 RMS（残差中位数当地平线偏移 cc，限 ±--cc-max）
  flatpen = 平地平线列上 max(0, 地平线仰角 − cc − --flat-clear) 的均值
  score   = rms + --flat-w × flatpen
机位先过两道筛：周围 --cam-flat-radius 内高差 ≤ --cam-flat（画面里机位站在平地上），
地平线最高仰角 ≥ --min-peak（有山可比）。
给了 --line（osm.py geom 的 GeoJSON）再加一条独立约束：对每个朝向，设施采样点落在画面左/中/右三个方位窗
（--line-win）内的最近距离 dL/dC/dR，落在 --line-dist 区间外按米数/--line-scale 罚分（--line-order 还能罚顺序），
total = score + --line-w × line_pen；三个窗里有一个没设施的朝向不算。没给 --line 时 total = score。

粗搜默认值就是实战那次的：2 km / 250 m / z11 / 0.5°；精搜换 --radius 800 --grid 100 --zoom 13 --az-step 0.25。
天际线只给一条视线（沿视线前后挪几百米轮廓不变），前几名一律看 --sheet 叠图，再用第二条约束定点。

两条别当结论用：
  1. 输出的 H 和 f 有系统偏差，来源是 ridge.json 里的 hrow。同一次粗搜，hrow 手定 935 给 H 80.5 / f 1436，
     用自动估的 909 给 H 79.0 / f 1282——差 1.5° 和 12% 焦距（cc 只能吸收 ±--cc-max）。排簇不受影响
     （两次真值簇都排第 1），但要拿 H/f 说事就先把 hrow 定准（ridge --png 上看蓝线）。
  2. 精搜（z13）不保证比粗搜更准。实测同一条链精搜反而比粗搜离真值更远：
     z13 的平地筛（--cam-flat / --cam-flat-radius）会把真值附近的点筛掉，而天际线本来就只给一条视线。
     精搜在这条链里的作用是给 geo.py spacing 一个靠谱的 --center，不是自己把误差压下去。
方法见 references/geometry.md 7.4、corridors.md 4.3。

输出 JSON（--out）：
  {"params": {...这次用的全部参数, 含 photo 里的 f0/hrow/cx/hfov...},
   "n_clusters", "n_cams": 打过分的机位数, "n_skipped": {"not_flat","no_peak","no_line","dup"},
   "clusters": [{"hit": 簇在 --hits 里的序号, "name", "hit_ll": [lat,lon], "n", "max_ang", "n_cams", "rank",
                 "best": <机位记录>}, ...],                      # 每簇最好的机位，按 total 升序
   "cams":     [<机位记录>, ...]}                                 # 全部机位按 total 升序，最多 --keep 条
  机位记录：{"hit","name","hit_ll", "cam": [lat,lon], "d": 离簇中心 m, "brg": 簇中心→机位方位°,
            "g": 地面高程 m, "H": 朝向°, "fs": 焦距倍率, "f": 焦距 px, "cc": 地平线偏移°,
            "rms", "flatpen", "score", [给了 --line 时: "dL","dC","dR" m, "line_pen"], "total"}
--sheet：多簇时画每簇最佳机位的前 --top 名，单簇/--at 时画前 --top 个机位；红线=合成天际线，黄点=照片山脊点。""")
    src = ft.add_mutually_exclusive_group(required=True)
    src.add_argument("--hits", help="scan 的输出 JSON（用 clusters 字段）或簇列表 JSON")
    src.add_argument("--at", help="不用 --hits，直接给一个中心 lat,lon（精搜用）")
    ft.add_argument("--select", help="只跑 --hits 里这些序号的簇，逗号分隔（验证、分块跑时用）")
    ft.add_argument("--ridge", type=Path, required=True, help="terrain.py ridge 的输出")
    ft.add_argument("--out", required=True, help="输出 JSON")
    ft.add_argument("--radius", type=float, default=2000, help="每簇机位网格半径 m（默认 2000；精搜 800）")
    ft.add_argument("--grid", type=float, default=250, help="机位网格间距 m（默认 250；精搜 100）")
    ft.add_argument("--zoom", type=int, default=11, help="高程切片级别（默认 11，一格约 70 m；精搜 13）")
    ft.add_argument("--focal-scales", default="0.9,1,1.12", help="焦距倍率，逗号分隔（默认 0.9,1,1.12；精搜用过 1,1.08,1.16）")
    ft.add_argument("--az-step", type=float, default=0.5, help="朝向/方位步长°（默认 0.5；精搜 0.25；要能整除 360）")
    ft.add_argument("--near", type=float, default=150, help="视线从多近开始采样 m（默认 150）")
    ft.add_argument("--range", type=float, default=15000, help="视线看多远 m（默认 15000）")
    ft.add_argument("--nsamp", type=int, default=260, help="每条视线的采样数，近密远疏（默认 260；精搜 400）")
    ft.add_argument("--eye", type=float, default=1.6, help="离地眼高 m（默认 1.6）")
    ft.add_argument("--cam-flat", type=float, default=8, help="机位周围高差上限 m，超过就不是平地机位（默认 8；精搜用过 6）")
    ft.add_argument("--cam-flat-radius", type=float, default=300, help="判断机位平不平的半径 m（默认 300；精搜用过 200）")
    ft.add_argument("--min-peak", type=float, default=6, help="地平线最高仰角至少多少度才打分（默认 6）")
    ft.add_argument("--cc-max", type=float, default=0.7, help="地平线偏移 cc 的上限°（默认 0.7，即 hrow 允许错十几像素）")
    ft.add_argument("--flat-clear", type=float, default=1.0, help="平地平线列上地平线高出 cc 多少度以内不罚（默认 1.0）")
    ft.add_argument("--flat-w", type=float, default=1.5, help="flatpen 权重（默认 1.5）")
    ft.add_argument("--flat-step", type=float, default=20, help="平地平线列范围内每多少像素取一列（默认 20）")
    ft.add_argument("--line", help="线状设施 GeoJSON（osm.py geom 的输出），给了就加左/中/右距离约束")
    ft.add_argument("--line-dist", help="左:中:右三个距离区间 m，如 350-750:550-900:800-1700（给了 --line 必填）")
    ft.add_argument("--line-win", default="-27:-21,-3:3,18:27",
                    help="左/中/右三个方位窗，相对画面中心的偏角°（默认 -27:-21,-3:3,18:27，按水平视角 53° 定的；"
                         "写成 --line-win=-27:... 或直接跟在后面都行）")
    ft.add_argument("--line-scale", default="200,200,300", help="三个窗各自的罚分尺度 m（默认 200,200,300：出界 200 m 罚 1）")
    ft.add_argument("--line-order", choices=["none", "asc", "desc"], default="none",
                    help="三个距离的顺序约束：asc = 左<中<右（设施从左近往右远斜穿画面），desc 反之；不满足罚 1（默认 none）")
    ft.add_argument("--line-w", type=float, default=0.3, help="line_pen 权重（默认 0.3）")
    ft.add_argument("--line-min", type=float, default=150, help="离机位近于这个距离的设施点不算（默认 150）")
    ft.add_argument("--line-sample", type=float, default=50, help="沿设施线每多少米取一个点（默认 50）")
    ft.add_argument("--line-reach", type=float, default=3000, help="只看机位这个距离内的设施点 m（默认 3000）")
    ft.add_argument("--skip-tag", action="append", help="--line 里跳过带这个标签的线，键=值，可重复（默认 electrified=no；none 表示不跳）")
    ft.add_argument("--top", type=int, default=20, help="终端打印和 --sheet 画前几名（默认 20）")
    ft.add_argument("--keep", type=int, default=5000, help="cams 列表最多写多少条（默认 5000）")
    ft.add_argument("--sheet", help="前 --top 名叠图 jpg")
    ft.add_argument("--overlay", "--photo", dest="photo", help="叠图用的照片；不给就用 ridge.json 里记的路径")
    ft.add_argument("--sheet-cols", type=int, default=4, help="叠图每行几张（默认 4）")
    ft.add_argument("--sheet-width", type=int, default=360, help="叠图每张宽 px（默认 360）")

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "scan":
        _cmd_scan(args)
        return
    if args.cmd == "ridge":
        _cmd_ridge(args)
        return
    if args.cmd == "fit":
        _cmd_fit(args)
        return
    lat, lon = map(float, args.at.split(","))
    if args.cmd == "elev":
        dem = DEM((lat, lon), 300, args.zoom, args.cache, args.proxy)
        print(f"{float(dem.sample(np.array([lat]), np.array([lon]))[0]):.0f} m")
        return

    dem = DEM((lat, lon), args.range, args.zoom, args.cache, args.proxy)
    ground = float(dem.sample(np.array([lat]), np.array([lon]))[0])
    eye = args.alt if args.alt is not None else ground + args.height
    az = np.linspace(args.heading - args.hfov / 2, args.heading + args.hfov / 2, args.width)
    if eye < ground + 1:
        print(f"注意：眼高 {eye:.0f} m 低于该点地面 {ground:.0f} m，近处地形会被当成天际线（--alt 给错了，或该用 --height）")
    ang, dist = cast(dem, (lat, lon), eye, az % 360, args.range, near=args.near)

    if args.cmd == "profile":
        runmax = np.max(ang, axis=1)
        far = dist[np.argmax(ang, axis=1)]
        step = max(1, args.width // 180)
        out = [{"azimuth": round(float(az[i] % 360), 2), "skyline_deg": round(float(runmax[i]), 3), "skyline_dist_m": round(float(far[i]))}
               for i in range(0, args.width, step)]
        args.out.write_text(json.dumps({"at": [lat, lon], "eye_alt_m": round(eye, 1), "ground_m": round(ground, 1), "profile": out}, indent=1))
        print(f"地面 {ground:.0f} m，眼高 {eye:.0f} m → {args.out}")
        return

    vfov = args.vfov or 2 * math.degrees(math.atan(math.tan(math.radians(args.hfov / 2)) * 2 / 3))
    height = int(args.width * vfov / args.hfov)
    im, sky_ang, sky_dist = render(ang, dist, az, args.pitch, vfov, height)
    title = (f"机位 {lat:.5f},{lon:.5f}  地面 {ground:.0f} m 眼高 {eye:.0f} m  朝向 {args.heading % 360:.0f}°  "
             f"水平视角 {args.hfov:.0f}°  天际线最远 {np.nanmax(sky_dist) / 1000:.1f} km")
    im = annotate(im, az, args.pitch, vfov, title)
    if args.roll:
        im = im.rotate(-args.roll, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    if args.photo and args.overlay:
        ph = Image.open(args.photo).convert("RGB")
        fpx = (ph.width / 2) / math.tan(math.radians(args.hfov / 2))
        cr, sr = math.cos(math.radians(args.roll)), math.sin(math.radians(args.roll))
        pts = []
        for a, e in zip(az, sky_ang):
            if e <= -89:
                continue
            x = fpx * math.tan(math.radians(a - args.heading))
            y = -fpx * math.tan(math.radians(e - args.pitch)) / math.cos(math.radians(a - args.heading))
            pts.append((ph.width / 2 + x * cr - y * sr, ph.height / 2 + x * sr + y * cr))
        ImageDraw.Draw(ph).line(pts, fill=(255, 40, 40), width=max(2, ph.width // 400))
        ov = args.out.with_name(args.out.stem + "_overlay" + args.out.suffix)
        ph.save(ov, quality=90)
        print(f"天际线叠到照片 -> {ov}（红线和照片山脊对不上时，先调 --heading/--pitch/--hfov/--roll，再怀疑机位）")
    if args.photo:
        ph = Image.open(args.photo).convert("RGB")
        ph = ph.resize((args.width, int(ph.height * args.width / ph.width)))
        S = Image.new("RGB", (args.width, ph.height + im.height), "white")
        S.paste(ph, (0, 0))
        S.paste(im, (0, ph.height))
        im = S
    im.save(args.out)
    print(f"地面 {ground:.0f} m，眼高 {eye:.0f} m，天际线距离 {np.nanmin(sky_dist) / 1000:.1f}–{np.nanmax(sky_dist) / 1000:.1f} km → {args.out}")


if __name__ == "__main__":
    main()
