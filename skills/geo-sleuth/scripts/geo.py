#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow"]
# ///
"""坐标系换算 + 方位/距离 + 相机几何。其余脚本都 import 这个文件。

坐标系：
  wgs   WGS84，GPS / Google 卫星图 / OSM
  gcj   GCJ-02，高德 / 腾讯 / Google 中国区道路图
  bd    BD-09 经纬度，百度
  bdmc  百度墨卡托平面坐标（百度地图 URL 里的 @x,y，全景接口的 x,y）

所有经纬度参数一律 (lat, lon) 顺序。

CLI 示例：
  geo.py convert --from bdmc --to wgs 12697689.83 2568072.49
  geo.py bearing 22.6045,114.0520 22.6072,114.0564
  geo.py dest 22.6045,114.0520 --bearing 47 --dist 120
  geo.py range --real 55 --pixels 195 --image-width 1279 --hfov 53
  geo.py range --real 300 --pixels 420 --image-width 1080 --hfov 12:70     # 倍率未知：按视角区间给距离区间
  geo.py line --near 22.6060,114.0550 --far 22.6072,114.0564 --range 50:1500 --out line.json
  geo.py intersect --align1 N1lat,N1lon:F1lat,F1lon --align2 N2lat,N2lon:F2lat,F2lon --sigma 1
  geo.py bearings --at <lat,lon> --geojson buildings.geojson --target 306 --tol 8   # 先算方位再认构件：哪栋楼在那个方位上
  geo.py frame --at 22.60,114.10 --anchor A:22.61,114.05:px=1000 --width 1080 --hfov 12:70 \\
               --pt B:22.62,114.06:h=300:w=60 --pt C:22.58,114.04:h=150:w=40      # 排除前算：B、C 该不该在画面里
  geo.py spacing --cols '39,133,219,296,369;745,788,829' --line rail.geojson --line-name 城际 --span 32 \\
                 --center 35.4983,138.7688 --radius 1500 --grid 50 --headings 55:115 --focals 1200:1500 \\
                 --cx 640 --out spacing.json     # 一排桥墩的像素列 → 机位、朝向、焦距（7.7）
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------- 坐标系换算

_A = 6378245.0
_EE = 0.00669342162296594323


def _out_of_china(lat: float, lon: float) -> bool:
    return not (73.66 < lon < 135.05 and 3.86 < lat < 53.55)


def _t_lat(x: float, y: float) -> float:
    r = -100 + 2 * x + 3 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    r += (20 * math.sin(y * math.pi) + 40 * math.sin(y / 3 * math.pi)) * 2 / 3
    r += (160 * math.sin(y / 12 * math.pi) + 320 * math.sin(y * math.pi / 30)) * 2 / 3
    return r


def _t_lon(x: float, y: float) -> float:
    r = 300 + x + 2 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    r += (20 * math.sin(6 * x * math.pi) + 20 * math.sin(2 * x * math.pi)) * 2 / 3
    r += (20 * math.sin(x * math.pi) + 40 * math.sin(x / 3 * math.pi)) * 2 / 3
    r += (150 * math.sin(x / 12 * math.pi) + 300 * math.sin(x / 30 * math.pi)) * 2 / 3
    return r


def _gcj_delta(lat: float, lon: float) -> tuple[float, float]:
    dlat = _t_lat(lon - 105, lat - 35)
    dlon = _t_lon(lon - 105, lat - 35)
    rad = lat / 180 * math.pi
    m = 1 - _EE * math.sin(rad) ** 2
    sm = math.sqrt(m)
    dlat = dlat * 180 / ((_A * (1 - _EE)) / (m * sm) * math.pi)
    dlon = dlon * 180 / (_A / sm * math.cos(rad) * math.pi)
    return dlat, dlon


def wgs2gcj(lat: float, lon: float) -> tuple[float, float]:
    if _out_of_china(lat, lon):
        return lat, lon
    dlat, dlon = _gcj_delta(lat, lon)
    return lat + dlat, lon + dlon


def gcj2wgs(lat: float, lon: float) -> tuple[float, float]:
    """迭代反解，误差 < 0.5 m。"""
    if _out_of_china(lat, lon):
        return lat, lon
    wlat, wlon = lat, lon
    for _ in range(5):
        glat, glon = wgs2gcj(wlat, wlon)
        wlat += lat - glat
        wlon += lon - glon
    return wlat, wlon


_XPI = math.pi * 3000 / 180


def gcj2bd(lat: float, lon: float) -> tuple[float, float]:
    z = math.hypot(lon, lat) + 0.00002 * math.sin(lat * _XPI)
    th = math.atan2(lat, lon) + 0.000003 * math.cos(lon * _XPI)
    return z * math.sin(th) + 0.006, z * math.cos(th) + 0.0065


def bd2gcj(lat: float, lon: float) -> tuple[float, float]:
    x, y = lon - 0.0065, lat - 0.006
    z = math.hypot(x, y) - 0.00002 * math.sin(y * _XPI)
    th = math.atan2(y, x) - 0.000003 * math.cos(x * _XPI)
    return z * math.sin(th), z * math.cos(th)


_MCBAND = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
_MC2LL = [
    [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331, 200.9824383106796, -187.2403703815547, 91.6087516669843, -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289, 96.32687599759846, -1.85204757529826, -59.36935905485877, 47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616, 59.74293618442277, 7.357984074871, -25.38371002664745, 13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591, 40.31678527705744, 0.65659298677277, -4.44255534477492, 0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062, 23.10934304144901, -0.00023663490511, -0.6321817810242, -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8, 7.47137025468032, -0.00000353937994, -0.02145144861037, -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5],
]
_LLBAND = [75, 60, 45, 30, 15, 0]
_LL2MC = [
    [-0.0015702102444, 111320.7020616939, 1704480524535203, -10338987376042340, 26112667856603880, -35149669176653700, 26595700718403920, -10725012454188240, 1800819912950474, 82.5],
    [0.0008277824516172526, 111320.7020463578, 647795574.6671607, -4082003173.641316, 10774905663.51142, -15171875531.51559, 12053065338.62167, -5124939663.577472, 913311935.9512032, 67.5],
    [0.00337398766765, 111320.7020202162, 4481351.045890365, -23393751.19931662, 79682215.47186455, -115964993.2797253, 97236711.15602145, -43661946.33752821, 8477230.501135234, 52.5],
    [0.00220636496208, 111320.7020209128, 51751.86112841131, 3796837.749470245, 992013.7397791013, -1221952.21711287, 1340652.697009075, -620943.6990984312, 144416.9293806241, 37.5],
    [-0.0003441963504368392, 111320.7020576856, 278.2353980772752, 2485758.690035394, 6070.750963243378, 54821.18345352118, 9540.606633304236, -2710.55326746645, 1405.483844121726, 22.5],
    [-0.0003218135878613132, 111320.7020701615, 0.00369383431289, 823725.6402795718, 0.46104986909093, 2351.343141331292, 1.58060784298199, 8.77738589078284, 0.37238884252424, 7.45],
]


def _poly(x: float, y: float, c: list[float]) -> tuple[float, float]:
    fx = c[0] + c[1] * abs(x)
    t = abs(y) / c[9]
    fy = c[2] + c[3] * t + c[4] * t ** 2 + c[5] * t ** 3 + c[6] * t ** 4 + c[7] * t ** 5 + c[8] * t ** 6
    return (-fx if x < 0 else fx), (-fy if y < 0 else fy)


def bdmc2bd(x: float, y: float) -> tuple[float, float]:
    c = next(_MC2LL[i] for i, b in enumerate(_MCBAND) if abs(y) >= b)
    lon, lat = _poly(x, y, c)
    return lat, lon


def bd2bdmc(lat: float, lon: float) -> tuple[float, float]:
    lat = max(min(lat, 74), -74)
    c = next(_LL2MC[i] for i, b in enumerate(_LLBAND) if abs(lat) >= b)
    return _poly(lon, lat, c)


def convert(a: float, b: float, src: str, dst: str) -> tuple[float, float]:
    """a,b 对经纬度系是 lat,lon；对 bdmc 是 x,y。"""
    if src == dst:
        return a, b
    # 先统一到 wgs
    if src == "wgs":
        lat, lon = a, b
    elif src == "gcj":
        lat, lon = gcj2wgs(a, b)
    elif src == "bd":
        lat, lon = gcj2wgs(*bd2gcj(a, b))
    elif src == "bdmc":
        lat, lon = gcj2wgs(*bd2gcj(*bdmc2bd(a, b)))
    else:
        raise ValueError(src)
    if dst == "wgs":
        return lat, lon
    g = wgs2gcj(lat, lon)
    if dst == "gcj":
        return g
    bd = gcj2bd(*g)
    if dst == "bd":
        return bd
    if dst == "bdmc":
        return bd2bdmc(*bd)
    raise ValueError(dst)


# ---------------------------------------------------------------- 方位与距离

_R = 6371008.8


def distance(p: tuple[float, float], q: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*p, *q))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * _R * math.asin(math.sqrt(h))


def bearing(p: tuple[float, float], q: tuple[float, float]) -> float:
    """p 看向 q 的罗盘方位角，0=北，顺时针。"""
    la1, lo1, la2, lo2 = map(math.radians, (*p, *q))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def dest(p: tuple[float, float], brg: float, dist_m: float) -> tuple[float, float]:
    la1, lo1 = map(math.radians, p)
    b = math.radians(brg)
    d = dist_m / _R
    la2 = math.asin(math.sin(la1) * math.cos(d) + math.cos(la1) * math.sin(d) * math.cos(b))
    lo2 = lo1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(la1), math.cos(d) - math.sin(la1) * math.sin(la2))
    return math.degrees(la2), math.degrees(lo2)


# ---------------------------------------------------------------- Web 墨卡托切片

def ll2px(zoom: int, lat: float, lon: float) -> tuple[float, float]:
    """经纬度 → 该缩放级别下的全局像素坐标（256 切片）。"""
    n = 256 * 2 ** zoom
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def px2ll(zoom: int, x: float, y: float) -> tuple[float, float]:
    n = 256 * 2 ** zoom
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def meters_per_px(zoom: int, lat: float) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / 2 ** zoom


# ---------------------------------------------------------------- 相机几何

def focal_px(image_width_px: float, hfov_deg: float) -> float:
    """针孔模型下以像素计的焦距。"""
    return (image_width_px / 2) / math.tan(math.radians(hfov_deg) / 2)


def range_from_size(real_size_m: float, size_px: float, image_width_px: float, hfov_deg: float) -> float:
    """已知物体真实宽度和它在画面里的像素宽度 → 深度距离（米）。"""
    return real_size_m * focal_px(image_width_px, hfov_deg) / size_px


def angle_from_center(px: float, center_px: float, image_width_px: float, hfov_deg: float) -> float:
    """画面上某点相对光轴的水平夹角（度，右正）。竖直方向同理，传竖直像素即可。"""
    return math.degrees(math.atan((px - center_px) / focal_px(image_width_px, hfov_deg)))


# 常见手机主摄视角（35mm 等效焦距 → 4:3 画幅长边/短边视角）
def fov_from_equiv_focal(focal_mm: float, aspect: tuple[int, int] = (4, 3)) -> tuple[float, float]:
    diag = 43.2666
    w, h = aspect
    k = diag / math.hypot(w, h)
    long_side, short_side = w * k, h * k
    return (math.degrees(2 * math.atan(long_side / 2 / focal_mm)),
            math.degrees(2 * math.atan(short_side / 2 / focal_mm)))


# ---------------------------------------------------------------- 视线交会

def _enu(p: tuple[float, float], o: tuple[float, float]) -> tuple[float, float]:
    """以 o 为原点的局部平面坐标（米，东、北）。50 km 内误差可忽略。"""
    return ((p[1] - o[1]) * math.cos(math.radians(o[0])) * 111320.0, (p[0] - o[0]) * 110540.0)


def _ll(xy: tuple[float, float], o: tuple[float, float]) -> tuple[float, float]:
    return (o[0] + xy[1] / 110540.0, o[1] + xy[0] / (math.cos(math.radians(o[0])) * 111320.0))


def ray_from_alignment(near: tuple[float, float], far: tuple[float, float]) -> tuple[tuple[float, float], float]:
    """画面里 near 挡在 far 前面（或上下对齐）→ 机位在 far→near 的延长线上、near 之外。返回 (起点, 方位)。"""
    return near, bearing(far, near)


def ray_from_sighting(landmark: tuple[float, float], seen_bearing: float) -> tuple[tuple[float, float], float]:
    """从机位看 landmark 的方位是 seen_bearing → 机位在 landmark 反方向的射线上。"""
    return landmark, (seen_bearing + 180) % 360


def intersect_rays(r1, r2) -> tuple[tuple[float, float], float, float, float] | None:
    """两条射线求交。返回 (交点, 夹角°, 沿射线1的距离m, 沿射线2的距离m)；平行或交点在射线背后时返回 None。"""
    (p1, b1), (p2, b2) = r1, r2
    o = p1
    x1, y1 = _enu(p1, o)
    x2, y2 = _enu(p2, o)
    d1 = (math.sin(math.radians(b1)), math.cos(math.radians(b1)))
    d2 = (math.sin(math.radians(b2)), math.cos(math.radians(b2)))
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t1 = ((x2 - x1) * d2[1] - (y2 - y1) * d2[0]) / den
    t2 = ((x2 - x1) * d1[1] - (y2 - y1) * d1[0]) / den
    if t1 < 0 or t2 < 0:
        return None
    pt = _ll((x1 + t1 * d1[0], y1 + t1 * d1[1]), o)
    ang = abs((b1 - b2 + 180) % 360 - 180)
    return pt, min(ang, 180 - ang), t1, t2


def intersect_with_error(r1, r2, sigma_deg: float) -> dict | None:
    """两条射线的交点，外加方位各偏 ±sigma 时交点移动的最大距离（当作误差半径）。"""
    base = intersect_rays(r1, r2)
    if base is None:
        return None
    pt, ang, t1, t2 = base
    spread = 0.0
    for s1 in (-sigma_deg, sigma_deg):
        for s2 in (-sigma_deg, sigma_deg):
            q = intersect_rays((r1[0], r1[1] + s1), (r2[0], r2[1] + s2))
            spread = max(spread, math.inf if q is None else distance(pt, q[0]))
    return {"point": [round(pt[0], 7), round(pt[1], 7)], "crossing_angle_deg": round(ang, 1),
            "dist_from_ray1_origin_m": round(t1), "dist_from_ray2_origin_m": round(t2),
            "error_radius_m": None if math.isinf(spread) else round(spread)}


# ---------------------------------------------------------------- 画框预测：某地标该不该出现在画面里

def _band_f(s: str) -> tuple[float, float]:
    """'65' → (65, 65)；'12:70' → (12, 70)。"""
    if ":" in s:
        a, b = s.split(":")
        return float(a), float(b)
    return float(s), float(s)


def _landmark(s: str) -> dict:
    """name:lat,lon[:h=高度m][:w=宽度m][:px=像素x] → dict。"""
    parts = s.split(":")
    d = {"name": parts[0], "ll": _pair(parts[1])}
    for kv in parts[2:]:
        k, v = kv.split("=")
        d[k] = float(v)
    return d


def _drop_m(dist_m: float) -> float:
    """地球曲率 + 常规大气折射（k≈0.13）让远处物体看起来矮掉的高度。"""
    return dist_m * dist_m / (2 * _R) * (1 - 0.13)


def frame_predict(cam: tuple[float, float], heading: float, hfov: float, width_px: float,
                  pts: list[dict], cam_h: float = 0.0) -> list[dict]:
    """给定机位、朝向、水平视角，逐个地标算：相对光轴的角度、像素 x、是否在画框内、角高度和角宽度。"""
    f = focal_px(width_px, hfov)
    out = []
    for p in pts:
        dist = distance(cam, p["ll"])
        rel = (bearing(cam, p["ll"]) - heading + 540) % 360 - 180
        row = {"name": p["name"], "dist_m": round(dist), "rel_deg": round(rel, 2)}
        half_w = math.degrees(math.atan2(p.get("w", 0) / 2, dist)) if dist > 0 else 0
        row["half_width_deg"] = round(half_w, 3)
        if abs(rel) < 90:
            x = width_px / 2 + f * math.tan(math.radians(rel))
            row["px"] = round(x)
            lo = width_px / 2 + f * math.tan(math.radians(rel - half_w))
            hi = width_px / 2 + f * math.tan(math.radians(rel + half_w))
            row["in_frame"] = "全在" if lo >= 0 and hi <= width_px else ("部分" if hi >= 0 and lo <= width_px else "不在")
        else:
            row["px"], row["in_frame"] = None, "不在（在身后）"
        if "h" in p and dist > 0:
            top = p["h"] - _drop_m(dist) - cam_h
            row["top_elev_deg"] = round(math.degrees(math.atan2(top, dist)), 3)
            row["angular_height_deg"] = round(math.degrees(math.atan2(p["h"], dist)), 3)
            row["height_px"] = round(f * math.tan(math.radians(row["angular_height_deg"])))
        out.append(row)
    return out


def occluders(cam: tuple[float, float], pts: list[dict], cam_h: float = 0.0) -> list[str]:
    """两两检查：近的地标（给了 w、h）能不能把远的地标整个挡住。"""
    notes = []
    info = []
    for p in pts:
        d = distance(cam, p["ll"])
        info.append((p, d, bearing(cam, p["ll"])))
    for near, dn, bn in info:
        if "w" not in near or "h" not in near:
            for far, df, bf in info:
                gap = abs((bf - bn + 540) % 360 - 180)
                if far is not near and df > dn and gap < 3:
                    notes.append(f"{far['name']} 可能被 {near['name']} 挡住：两者方位只差 {gap:.2f}°，"
                                 f"{near['name']} 没给 w、h，算不了（给上再跑）")
            continue
        for far, df, bf in info:
            if far is near or df <= dn:
                continue
            half_n = math.degrees(math.atan2(near["w"] / 2, dn))
            half_f = math.degrees(math.atan2(far.get("w", 0) / 2, df))
            gap = abs((bf - bn + 540) % 360 - 180)
            top_n = math.degrees(math.atan2(near["h"] - _drop_m(dn) - cam_h, dn))
            top_f = math.degrees(math.atan2(far.get("h", 0) - _drop_m(df) - cam_h, df)) if "h" in far else None
            if gap + half_f <= half_n and (top_f is None or top_n >= top_f):
                notes.append(f"{far['name']} 可能被 {near['name']} 整个挡住（方位差 {gap:.2f}°，{near['name']} 半宽 {half_n:.2f}°）")
            elif gap < half_n + half_f and (top_f is None or top_n >= top_f):
                notes.append(f"{far['name']} 被 {near['name']} 挡住一部分（方位差 {gap:.2f}°）")
            elif gap < half_n + half_f and top_f is not None:
                notes.append(f"{far['name']} 比 {near['name']} 高出一截露在上方（{top_f:.2f}° > {top_n:.2f}°）")
    return notes


def _ring_positions(spec: str) -> dict:
    """lat,lon:rmin:rmax:rstep:azstep → 以某点为中心的一圈圈候选机位。"""
    ll, rmin, rmax, rstep, azstep = spec.split(":")
    c = _pair(ll)
    out = {}
    r = float(rmin)
    while r <= float(rmax) + 1e-6:
        az = 0.0
        while az < 360 - 1e-6:
            out[f"R{int(r)}m@{int(az)}"] = list(dest(c, az, r))
            az += float(azstep)
        r += float(rstep)
    return out


# ---------------------------------------------------------------- 等间距构件反解机位（spacing）

SPACING_DOC = """画面里一排等间距的构件（高架桥墩、电杆、路灯、护栏立柱）落在地图上一条已知的线上时，
反解机位、朝向、焦距。方法见 references/geometry.md 7.7。

原理：每个构件的像素列 x → 相对画面中心的偏角 atan((x-cx)/f) → 一条射线；射线与 GeoJSON 折线求交，
得到该构件的沿线里程。机位/朝向/焦距都对的时候，相邻构件的里程差恒定，且等于标准跨度（--span）。
打分 pier = 里程差的离散度 CV + |log(里程差均值 / span)|（里程不单调再加 --mono-penalty）。

只用间距这一条，解是沿视线方向的一条带（实战散在约 800 m 内）。给 --ridge 就和天际线联合打分
（照 joint.py：tot = 天际线 rms + --flat-weight × 平地平线罚分 + --ridge-weight × 间距分），
实战收到约 300 m。天际线那部分要下载高程切片（terrain.py 用的 AWS Terrain Tiles，缓存在 --cache）。

--cols 的分组：构件被前景挡断成几段时用 ';' 分组，只在组内算相邻差（跨段的那个差不是一跨）。
单调性检查仍然跨全部列做——整排构件沿线的里程必须一路增或一路减。

输出 JSON：
  {"line": {…选中的那条线…},
   "params": {…这次跑的全部参数…},
   "best": <candidates[0]>,
   "candidates": [{"tot": 总分, "rms": 天际线 rms（没给 --ridge 时为 null）,
                   "pier": 间距分, "cam": [lat, lon], "f": 焦距 px, "H": 朝向°,
                   "cc": 天际线俯仰改正°（没给 --ridge 时为 null）,
                   "span_m": 解出来的平均跨度 m, "d_first": 到第一个构件的距离 m,
                   "d_last": 到最后一个构件的距离 m}, …按 tot 从小到大 --top 个]}
  cam/f/H/cc 这几个字段名沿用那次实战现写脚本（joint.py）的输出，两边的结果能直接对比。"""


def _spacing_col_val(v) -> float:
    """一个像素列：数字、[x, …]，或 imgprep.py piers 那种 {"col": x, "prominence": …}。"""
    if isinstance(v, dict):
        if "col" not in v:
            sys.exit(f"JSON 里的构件记录没有 col 字段：{v}")
        return float(v["col"])
    if isinstance(v, (list, tuple)):
        return float(v[0])
    return float(v)


def _spacing_cols(spec: str) -> list[list[float]]:
    """像素列分组：'39,133,219;745,788' → [[39,133,219],[745,788]]。

    也接受 JSON 文件（'@路径' 或以 .json 结尾）：list、list[list]、list[{"col": …}]、
    {"piers": [{"col": …}, …]}（imgprep.py piers 的输出）、{"groups": [[…]]}、{"cols": […]} 都认。
    键的优先级是 piers > groups > cols：imgprep.py piers 输出里的 "cols" 是列的搜索范围 [x0, x1]，不是构件列。
    每组内部升序排列，组之间按首列排序。"""
    raw = spec
    if raw.startswith("@") or raw.lower().endswith(".json"):
        with open(raw[1:] if raw.startswith("@") else raw) as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            for key in ("piers", "groups", "cols"):
                if key in data:
                    data = data[key]
                    break
            else:
                sys.exit("JSON 里没找到 piers / groups / cols")
        if data is None:
            sys.exit("JSON 里的 piers / groups / cols 是空的")
        groups = data if (data and isinstance(data[0], (list, tuple))) else [data]
        groups = [[_spacing_col_val(v) for v in g] for g in groups]
    else:
        groups = [[float(v) for v in part.split(",") if v.strip() != ""] for part in raw.split(";")]
    groups = [sorted(g) for g in groups if g]
    groups.sort(key=lambda g: g[0])
    if not groups:
        sys.exit("--cols 为空")
    return groups


def _spacing_focals(spec: str, step: float) -> list[float]:
    """'1200,1281,1350' → 列表；'1200:1500' → 按 step 等差。那次实战用的是列表 1200,1281,1350,1430,1500。"""
    if ":" in spec:
        parts = [float(v) for v in spec.split(":")]
        lo, hi = parts[0], parts[1]
        st = parts[2] if len(parts) > 2 else step
        n = int(round((hi - lo) / st))
        return [lo + st * k for k in range(n + 1)]
    return [float(v) for v in spec.split(",") if v.strip() != ""]


def _spacing_band(spec: str) -> tuple[float, float]:
    a, b = spec.split(":")
    return float(a), float(b)


def _spacing_line(path: str, name: str | None, index: int):
    """从 GeoJSON 里取一条折线，返回 (Nx2 的 [lon,lat] 列表, 说明 dict)。

    --line-name 按 properties.name 子串匹配；同名要素（上下行两条股道）用 --line-index 选第几个。
    不给名字时：只有一条线就用它，多条就用最长的那条并打印提示。"""
    with open(path) as fh:
        g = json.load(fh)
    feats = g.get("features") if isinstance(g, dict) and g.get("type") == "FeatureCollection" else None
    if feats is None:
        feats = [g] if isinstance(g, dict) else list(g)
    cands = []
    for f in feats:
        geom = f.get("geometry", f) or {}
        props = f.get("properties") or {}
        parts = []
        if geom.get("type") == "LineString":
            parts = [geom["coordinates"]]
        elif geom.get("type") == "MultiLineString":
            parts = list(geom["coordinates"])
        for c in parts:
            if len(c) < 2:
                continue
            ln = sum(math.dist(c[k], c[k + 1]) for k in range(len(c) - 1)) * 111000
            cands.append({"name": str(props.get("name") or ""), "coords": c, "length_m": ln})
    if not cands:
        sys.exit(f"{path} 里没有 LineString")
    if name:
        hit = [c for c in cands if name in c["name"]]
        if not hit:
            names = sorted({c["name"] for c in cands if c["name"]})
            sys.exit(f"没有名字含 {name!r} 的线；文件里的名字：{names}")
        if index >= len(hit):
            sys.exit(f"名字含 {name!r} 的线有 {len(hit)} 条，--line-index 只能到 {len(hit) - 1}")
        pick = hit[index]
        note = f"名字含 {name!r} 的 {len(hit)} 条里第 {index} 条"
    elif len(cands) == 1:
        pick = cands[0]
        note = "文件里只有这一条线"
    else:
        pick = max(cands, key=lambda c: c["length_m"])
        note = f"文件里有 {len(cands)} 条线，没给 --line-name，用了最长的那条；要别的线就给 --line-name / --line-index"
    info = {"name": pick["name"], "note": note, "points": len(pick["coords"]),
            "length_m": round(pick["length_m"]),
            "ends": [[round(pick["coords"][0][1], 6), round(pick["coords"][0][0], 6)],
                     [round(pick["coords"][-1][1], 6), round(pick["coords"][-1][0], 6)]]}
    return pick["coords"], info


def _spacing_ridge(path: str) -> dict:
    """读 terrain.py ridge 的输出 {"ridge": [[x,y]…], "flat": [x0,x1], "hrow":…, "f0":…}。

    也认两种手写格式：{"760": 826, …}（列→山脊行）和裸 [[x,y]…]。"""
    with open(path) as fh:
        d = json.load(fh)
    out = {"flat": None, "hrow": None, "f0": None}
    if isinstance(d, list):
        pts = d
    else:
        pts = d.get("ridge")
        out["flat"] = d.get("flat")
        out["hrow"] = d.get("hrow")
        out["f0"] = d.get("f0")
        if pts is None:
            pts = [[float(k), float(v)] for k, v in d.items() if str(k).lstrip("-").replace(".", "", 1).isdigit()]
    if isinstance(pts, dict):
        pts = [[float(k), float(v)] for k, v in pts.items()]
    pts = [[float(p[0]), float(p[1])] for p in pts]
    if len(pts) < 4:
        sys.exit(f"{path} 里山脊点太少（{len(pts)} 个），至少要 4 个")
    out["pts"] = sorted(pts)
    return out


def _spacing_run(args) -> dict:
    """网格搜机位×朝向×焦距，逐个算间距分（可选联合天际线）。返回写进 --out 的那个 dict。"""
    import numpy as np

    groups = _spacing_cols(args.cols)
    cols = [c for g in groups for c in g]
    if len(cols) < 3:
        sys.exit(f"--cols 只有 {len(cols)} 个列，至少 3 个（geometry.md 7.7 建议 ≥6）。"
                 "给的是 JSON 文件时注意：imgprep.py piers 的构件列在 piers 字段，cols 字段是搜索范围")
    pier = np.array(cols, float)

    pair_a, pair_b, off = [], [], 0                      # 组内相邻对：只有同一段里的相邻构件才是一跨
    for g in groups:
        pair_a += list(range(off, off + len(g) - 1))
        pair_b += list(range(off + 1, off + len(g)))
        off += len(g)
    if not pair_a:
        sys.exit("--cols 每组都只有一个列，算不出相邻间距")
    pair_a, pair_b = np.array(pair_a), np.array(pair_b)

    lat0, lon0 = args.center
    kx = 111320 * math.cos(math.radians(lat0))
    ky = 110540.0

    coords, line_info = _spacing_line(args.line, args.line_name, args.line_index)
    ll = np.array(coords, float)
    P = np.c_[(ll[:, 0] - lon0) * kx, (ll[:, 1] - lat0) * ky]     # 局部米坐标（x 东、y 北）
    seg_a, seg_b = P[:-1], P[1:]
    e = seg_b - seg_a
    seg_len = np.hypot(*e.T)
    chain0 = np.r_[0, np.cumsum(seg_len)][:-1]                    # 每段起点的沿线里程

    hs = np.arange(args.headings[0], args.headings[1] + 1e-9, args.heading_step)
    focals = _spacing_focals(args.focals, args.focal_step)
    xs = np.arange(-args.radius, args.radius + 1e-9, args.grid)
    print(f"线：{line_info['name'] or '（无名）'} {line_info['points']} 点 {line_info['length_m']} m（{line_info['note']}）")
    print(f"机位 {len(xs)}×{len(xs)} 格 × 朝向 {len(hs)} × 焦距 {len(focals)}；{len(cols)} 个像素列分 {len(groups)} 组，"
          f"标准跨 {args.span} m")

    dem = ridge = None
    if args.ridge:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import terrain                                            # noqa: PLC0415 —— 只有联合天际线才用得上，别让别的子命令等它
        ridge = _spacing_ridge(args.ridge)
        hrow = args.hrow if args.hrow is not None else ridge["hrow"]
        if hrow is None:
            sys.exit("--ridge 文件里没有 hrow（照片上地平线在第几行），用 --hrow 给一个")
        rp = np.array(ridge["pts"], float)
        rx, ry = rp[:, 0], rp[:, 1]
        flat = args.flat if args.flat is not None else (tuple(ridge["flat"]) if ridge["flat"] else None)
        flx = np.arange(flat[0], flat[1] + 1e-9, args.flat_step) if flat else None
        az = np.arange(0, 360, args.az_step)
        dist = args.sky_near * (args.sky_range / args.sky_near) ** (np.arange(args.sky_samples) / (args.sky_samples - 1))
        drop = dist ** 2 / (2 * terrain.R_EARTH) * (1 - terrain.K_REFRACTION)   # 地球曲率 + 大气折射
        dem = terrain.DEM((lat0, lon0), args.dem_range, args.dem_zoom, args.cache, args.proxy)
        print(f"天际线联合：山脊 {len(rx)} 点，地平线行 {hrow}，"
              f"平地平线列 {f'{flat[0]:g}–{flat[1]:g}' if flat else '不用'}，DEM z{args.dem_zoom} 半径 {args.dem_range} m")

    res, nfit, t0 = [], 0, time.time()
    for iy, yy in enumerate(xs):
        for xx in xs:
            w = seg_a - np.array([xx, yy])
            hor = None
            for f in focals:
                offs = np.degrees(np.arctan((pier - args.cx) / f))            # 每个构件相对画面中心的偏角
                a = np.radians(hs[:, None] + offs[None, :])
                dx, dy = np.sin(a)[..., None], np.cos(a)[..., None]           # (朝向, 构件, 1)
                den = dx * e[:, 1] - dy * e[:, 0]
                with np.errstate(divide="ignore", invalid="ignore"):
                    t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den         # 射线参数 = 距离 m
                    u = (w[:, 0] * dy - w[:, 1] * dx) / den                   # 线段参数 0–1
                ok = (t > args.min_dist) & (u >= 0) & (u <= 1)
                tt = np.where(ok, t, np.inf)
                i = np.argmin(tt, axis=2)                                     # 取最近的那个交点
                tmin = np.take_along_axis(tt, i[..., None], 2)[..., 0]
                valid = np.all(np.isfinite(tmin), axis=1)
                if not valid.any():
                    continue
                uu = np.take_along_axis(u, i[..., None], 2)[..., 0]
                ch = chain0[i] + uu * seg_len[i]                              # 每个构件的沿线里程
                sp = np.abs(ch[:, pair_b] - ch[:, pair_a])
                m = sp.mean(axis=1)
                cv = sp.std(axis=1) / np.maximum(m, 1e-6)
                dch = np.diff(ch, axis=1)
                mono = np.all(dch > 0, axis=1) | np.all(dch < 0, axis=1)
                ps = cv + np.abs(np.log(np.maximum(m, 1e-3) / args.span)) + (~mono) * args.mono_penalty
                ps[~valid] = np.inf
                k = int(np.argmin(ps))
                if not np.isfinite(ps[k]) or ps[k] > args.pier_max:
                    continue
                nfit += 1
                H = float(hs[k])
                clat, clon = lat0 + yy / ky, lon0 + xx / kx
                rms = cc = None
                tot = float(ps[k])
                if dem is not None:
                    if hor is None:                                           # 一个机位只算一次地平线，几个焦距共用
                        g0 = float(dem.sample(np.array([clat]), np.array([clon]))[0])
                        la, lo = terrain._dest_np(clat, clon, az, dist)
                        hh = dem.sample(la, lo)
                        hor = np.degrees(np.arctan2(hh - drop[None, :] - g0 - args.eye, dist[None, :])).max(axis=1)
                    r_off = np.degrees(np.arctan((rx - args.cx) / f))         # 山脊点：像素列 → 方位偏角
                    r_el = np.degrees(np.arctan((hrow - ry) / f))             #          像素行 → 仰角
                    mr = np.interp((H + r_off) % 360, az, hor, period=360)
                    diff = mr - r_el
                    cc = float(np.clip(np.median(diff), -args.cc_max, args.cc_max))   # 俯仰改正（地平线行估偏了）
                    rms = float(np.sqrt(np.mean((diff - cc) ** 2)))
                    fpen = 0.0
                    if flx is not None:
                        mf = np.interp((H + np.degrees(np.arctan((flx - args.cx) / f))) % 360, az, hor, period=360)
                        fpen = float(np.mean(np.clip(mf - cc - args.flat_margin, 0, None)))  # 该平的那段不许冒山
                    tot = rms + args.flat_weight * fpen + args.ridge_weight * float(ps[k])
                res.append({"tot": tot, "rms": rms, "pier": float(ps[k]), "cam": [round(clat, 5), round(clon, 5)],
                            "f": int(f) if float(f).is_integer() else f, "H": H, "cc": cc, "span_m": round(float(m[k]), 1),
                            "d_first": round(float(tmin[k, 0])), "d_last": round(float(tmin[k, -1]))})
        if args.progress and (iy + 1) % args.progress == 0:
            print(f"  {iy + 1}/{len(xs)} 行，命中 {nfit}，{time.time() - t0:.0f}s", file=sys.stderr)

    res.sort(key=lambda r: r["tot"])
    top = res[:args.top]
    return {"line": line_info,
            "params": {"cols": [[int(c) if float(c).is_integer() else c for c in g] for g in groups],
                       "span": args.span, "cx": args.cx, "center": [lat0, lon0], "radius": args.radius,
                       "grid": args.grid, "headings": list(args.headings), "heading_step": args.heading_step,
                       "focals": focals, "pier_max": args.pier_max, "min_dist": args.min_dist,
                       "ridge": args.ridge, "ridge_weight": args.ridge_weight if args.ridge else None,
                       "hrow": (args.hrow if args.hrow is not None else (ridge["hrow"] if ridge else None)),
                       "dem_zoom": args.dem_zoom if args.ridge else None},
            "n_fit": nfit, "best": top[0] if top else None, "candidates": top}


# ---------------------------------------------------------------- CLI

def _pair(s: str) -> tuple[float, float]:
    a, b = s.split(",")
    return float(a), float(b)



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="坐标系换算")
    c.add_argument("--from", dest="src", required=True, choices=["wgs", "gcj", "bd", "bdmc"])
    c.add_argument("--to", dest="dst", required=True, choices=["wgs", "gcj", "bd", "bdmc"])
    c.add_argument("a", type=float)
    c.add_argument("b", type=float)

    b = sub.add_parser("bearing", help="两点方位角与距离（wgs）")
    b.add_argument("p", type=_pair)
    b.add_argument("q", type=_pair)

    d = sub.add_parser("dest", help="从一点按方位走多少米（wgs）")
    d.add_argument("p", type=_pair)
    d.add_argument("--bearing", type=float, required=True)
    d.add_argument("--dist", type=float, required=True)

    r = sub.add_parser("range", help="按物体真实尺寸和像素尺寸估距离")
    r.add_argument("--real", type=float, required=True, help="真实尺寸，米")
    r.add_argument("--pixels", type=float, required=True, help="画面里的像素尺寸")
    r.add_argument("--image-width", type=float, required=True, help="与 hfov 对应那条边的像素数")
    r.add_argument("--hfov", help="该边视角（度）；倍率不知道就给区间，如 12:70，输出距离区间")
    r.add_argument("--equiv-focal", type=float, help="35mm 等效焦距；给了就自动算视角")
    r.add_argument("--side", choices=["long", "short"], default="short", help="image-width 是长边还是短边")

    f = sub.add_parser("fov", help="等效焦距 → 视角")
    f.add_argument("focal", type=float)

    ln = sub.add_parser("line", help="对齐线：near 挡在 far 前面 → 机位所在的延长线，输出沿线采样点")
    ln.add_argument("--near", type=_pair, required=True, help="画面里靠前的物体 lat,lon")
    ln.add_argument("--far", type=_pair, required=True, help="画面里靠后、和 near 对齐的物体 lat,lon")
    ln.add_argument("--range", default="0:2000", help="从 near 往外延伸的距离范围（米），如 50:1500")
    ln.add_argument("--step", type=float, default=100)
    ln.add_argument("--out", help="写出 {name:[lat,lon]}，可给 tiles.py mark")

    it = sub.add_parser("intersect", help="两条视线求交点（带误差半径）")
    it.add_argument("--align1", help="near_lat,near_lon:far_lat,far_lon（第一组对齐物）")
    it.add_argument("--align2", help="第二组对齐物，格式同上")
    it.add_argument("--sight1", help="lat,lon@方位：从机位看这个地标的罗盘方位")
    it.add_argument("--sight2", help="同上")
    it.add_argument("--sigma", type=float, default=1.0, help="每条视线的方位误差（度），默认 1")

    fr = sub.add_parser("frame", help="排除前的画框检查：从候选机位看，某地标该不该出现在画面里、会不会被挡",
                        formatter_class=argparse.RawDescriptionHelpFormatter, description=(
        "用途：想用\"画面里没有 X\"排除一个候选机位或一整个方向之前，先算 X 到底落不落在画框里。\n"
        "朝向有两种给法：--heading 直接给；或 --anchor 给一个已认出的地标和它在画面里的像素 x，\n"
        "脚本按每个视角反推朝向（视角越小，画框越窄，旁边的地标越容易出框）。\n"
        "视角不知道（视频截图、裁剪、变焦）就给区间，脚本扫一遍，报每个地标在哪段视角里进画框。\n"
        "只有\"整个视角区间里都全在画框内、又没被挡\"的地标，才能拿它的缺席去排除。"))
    pos = fr.add_mutually_exclusive_group(required=True)
    pos.add_argument("--at", action="append", type=_pair, help="候选机位 lat,lon，可重复")
    pos.add_argument("--points", help="候选机位 JSON {name:[lat,lon]}")
    pos.add_argument("--ring", help="lat,lon:最小半径:最大半径:半径步长:方位步长 —— 围着某地标一圈圈摆候选机位")
    fr.add_argument("--heading", type=float, help="镜头朝向（罗盘角）")
    fr.add_argument("--anchor", help="name:lat,lon:px=像素x —— 已认出的地标及其在画面里的水平像素位置")
    fr.add_argument("--width", type=float, required=True, help="画面宽度像素（和 hfov 同一条边）")
    fr.add_argument("--hfov", default="65", help="水平视角，单值或区间 12:70（默认 65）")
    fr.add_argument("--pt", action="append", default=[], type=_landmark,
                    help="要检查的地标 name:lat,lon[:h=高m][:w=宽m]，可重复；h、w 用于角高度和遮挡判断")
    fr.add_argument("--cam-h", type=float, default=0.0, help="机位高度，和地标 h 同一基准（都用离地高度或都用海拔）")
    fr.add_argument("--min-px", type=float, default=12, help="地标在画面里至少多少像素高才算\"应该看得出来\"")
    fr.add_argument("--out", help="完整结果写 JSON")

    bg = sub.add_parser("bearings", help="从机位看 GeoJSON 里每个要素的方位角、角宽、距离；给 --target 时按方位差排序（先算方位，再认构件）")
    bg.add_argument("--at", type=_pair, required=True, help="机位 lat,lon")
    bg.add_argument("--geojson", required=True, help="osm.py geom 的输出（建筑轮廓、线、点）")
    bg.add_argument("--target", type=float, help="目标真实方位（sun.py compass 算出的照片里那根塔的方位）")
    bg.add_argument("--tol", type=float, default=8, help="方位差在这个度数内的标为候选")
    bg.add_argument("--max-dist", type=float, default=3000, help="只看这个距离内的要素（米）")
    bg.add_argument("--out", help="写出 {名字: [lat, lon]}，可给 tiles.py mark")

    sp = sub.add_parser("spacing", help="一排等间距构件（桥墩、电杆）反解机位：像素列 → 射线 → 与线求交 → 相邻里程差应恒定",
                        formatter_class=argparse.RawDescriptionHelpFormatter, description=SPACING_DOC)
    sp.add_argument("--cols", required=True,
                    help="构件的像素列，逗号分隔；被挡断成几段用 ';' 分组（记得加引号），如 '39,133,219,296,369;745,788,829'。"
                         "也可以给 JSON 文件（@cols.json），imgprep.py piers 的输出（piers 字段）直接能用。"
                         "先对着 piers 的 --sheet 把非构件的峰剔掉、按前景遮挡分好段——这两件事是没有解的头号原因")
    sp.add_argument("--line", required=True, help="构件所在的线，GeoJSON（osm.py 取的铁路/电力线）")
    sp.add_argument("--line-name", help="按 properties.name 子串挑一条线；不给就用文件里最长的那条")
    sp.add_argument("--line-index", type=int, default=0, help="同名的线有几条（上下行股道）时选第几条，默认 0")
    sp.add_argument("--span", type=float, required=True, help="标准跨度 m（高铁简支箱梁 32，电杆按当地标准）；没把握就换几个值各跑一次")
    sp.add_argument("--center", type=_pair, required=True, help="候选区中心 lat,lon（同时是局部平面坐标的原点）")
    sp.add_argument("--radius", type=float, default=1500, help="候选区半边长 m，默认 1500（搜 ±radius 的方格）")
    sp.add_argument("--grid", type=float, default=50, help="机位网格间距 m，默认 50")
    sp.add_argument("--headings", type=_spacing_band, default=(0.0, 360.0), help="朝向搜索范围 lo:hi（度），默认 0:360；知道大致朝向就收窄，快很多")
    sp.add_argument("--heading-step", type=float, default=0.25, help="朝向步长（度），默认 0.25")
    sp.add_argument("--focals", required=True, help="焦距（像素），列表 1200,1281,1350,1430,1500 或区间 1200:1500[:步长]")
    sp.add_argument("--focal-step", type=float, default=50, help="--focals 给区间时的步长，默认 50")
    sp.add_argument("--cx", type=float, default=640, help="画面水平中心像素，默认 640（宽 1280 的照片）；裁过的照片要按裁法算")
    sp.add_argument("--min-dist", type=float, default=100, help="交点至少多远才算数 m，默认 100（滤掉机位脚下的假交点）")
    sp.add_argument("--pier-max", type=float, default=0.08, help="间距分高于这个值的解直接丢掉，默认 0.08")
    sp.add_argument("--mono-penalty", type=float, default=1.0, help="里程不单调（射线打到线的两侧）的罚分，默认 1.0")
    sp.add_argument("--top", type=int, default=25, help="输出前几名，默认 25")
    sp.add_argument("--progress", type=int, default=10, help="每几行网格往 stderr 报一次进度，0=不报")
    sp.add_argument("--out", help="结果写 JSON（结构见上）")
    sp.add_argument("--ridge", help="山脊像素点 JSON（terrain.py ridge 的输出）；给了就和天际线联合打分，要下高程切片")
    sp.add_argument("--hrow", type=float, help="照片上地平线在第几行像素；--ridge 文件里有 hrow 就不用给")
    sp.add_argument("--flat", type=_spacing_band, help="画面里该是平地平线的列范围 x0:x1（如 0:280）；默认取 --ridge 文件里的 flat")
    sp.add_argument("--flat-step", type=float, default=20, help="平地平线列的采样步长 px，默认 20")
    sp.add_argument("--flat-margin", type=float, default=1.0, help="平地平线容许高出改正后地平线多少度，默认 1.0")
    sp.add_argument("--flat-weight", type=float, default=1.5, help="平地平线罚分的权重，默认 1.5")
    sp.add_argument("--ridge-weight", "--pier-weight", dest="ridge_weight", type=float, default=2.0,
                    help="联合打分里间距分的权重，默认 2.0（tot = 天际线 rms + flat-weight×平地平线罚分 + 这个权重×间距分）")
    sp.add_argument("--cc-max", type=float, default=0.8, help="俯仰改正的绝对值上限（度），默认 0.8")
    sp.add_argument("--eye", type=float, default=1.6, help="机位离地高度 m，默认 1.6")
    sp.add_argument("--dem-zoom", type=int, default=13, help="高程切片级别，默认 13")
    sp.add_argument("--dem-range", type=float, default=18000, help="高程拼图半径 m，默认 18000（要盖住候选区 + 看得到的山）")
    sp.add_argument("--sky-range", type=float, default=16000, help="天际线往外看多远 m，默认 16000")
    sp.add_argument("--sky-near", type=float, default=100, help="天际线从多近开始采样 m，默认 100")
    sp.add_argument("--sky-samples", type=int, default=400, help="每个方位采样几个距离，默认 400（近密远疏）")
    sp.add_argument("--az-step", type=float, default=0.1, help="地平线方位表的步长（度），默认 0.1")
    sp.add_argument("--cache", type=Path, default=Path(".geo-cache/dem"), help="高程切片缓存目录，默认 .geo-cache/dem（和 terrain.py 同一个）")
    sp.add_argument("--proxy", default=os.environ.get("GEO_PROXY"), help="高程切片走代理；国内一般能直连，默认取环境变量 GEO_PROXY")

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "convert":
        x, y = convert(args.a, args.b, args.src, args.dst)
        print(f"{x:.7f},{y:.7f}")
    elif args.cmd == "bearing":
        print(f"bearing={bearing(args.p, args.q):.1f}deg distance={distance(args.p, args.q):.1f}m")
    elif args.cmd == "dest":
        la, lo = dest(args.p, args.bearing, args.dist)
        print(f"{la:.7f},{lo:.7f}")
    elif args.cmd == "range":
        if args.hfov is None:
            if args.equiv_focal is None:
                ap.error("需要 --hfov 或 --equiv-focal")
            lf, sf = fov_from_equiv_focal(args.equiv_focal)
            lo = hi = lf if args.side == "long" else sf
        else:
            lo, hi = _band_f(args.hfov)
        if lo == hi:
            dist = range_from_size(args.real, args.pixels, args.image_width, lo)
            print(f"fov={lo:.1f}deg focal={focal_px(args.image_width, lo):.0f}px range={dist:.0f}m")
        else:
            steps = 6
            for k in range(steps + 1):
                hf = lo * (hi / lo) ** (k / steps)          # 按倍率等比取样
                dist = range_from_size(args.real, args.pixels, args.image_width, hf)
                print(f"fov={hf:5.1f}deg focal={focal_px(args.image_width, hf):6.0f}px range={dist:7.0f}m")
            print(f"视角 {lo:g}–{hi:g}° → 距离 {range_from_size(args.real, args.pixels, args.image_width, hi):.0f}–"
                  f"{range_from_size(args.real, args.pixels, args.image_width, lo):.0f} m。倍率没定下来之前，按整个区间找候选")
    elif args.cmd == "frame":
        if args.heading is None and not args.anchor:
            ap.error("需要 --heading 或 --anchor")
        if args.at:
            cams = {f"P{i + 1}": list(p) for i, p in enumerate(args.at)}
        elif args.points:
            with open(args.points) as fh:
                cams = {k: v[:2] for k, v in json.load(fh).items()}
        else:
            cams = _ring_positions(args.ring)
        anchor = _landmark(args.anchor) if args.anchor else None
        lo, hi = _band_f(args.hfov)
        hfovs = [lo] if lo == hi else [lo * (hi / lo) ** (k / 40) for k in range(41)]
        pts = args.pt + ([anchor] if anchor else [])
        W = args.width
        full: dict = {}
        summary_rows = []
        for cname, cll in cams.items():
            cam = tuple(cll)
            per_hfov = []
            status: dict[str, list[float]] = {p["name"]: [] for p in args.pt}
            min_px: dict[str, float] = {}
            for hf in hfovs:
                if anchor:
                    f = focal_px(W, hf)
                    off = math.degrees(math.atan((anchor["px"] - W / 2) / f))
                    hd = (bearing(cam, anchor["ll"]) - off) % 360
                else:
                    hd = args.heading
                rows = frame_predict(cam, hd, hf, W, pts, args.cam_h)
                per_hfov.append({"hfov": round(hf, 2), "heading": round(hd, 2), "points": rows})
                for r in rows:
                    if r["name"] in status and r["in_frame"] == "全在":
                        status[r["name"]].append(hf)
                        if "height_px" in r:
                            min_px[r["name"]] = min(min_px.get(r["name"], 1e9), r["height_px"])
            occ = occluders(cam, pts, args.cam_h)
            full[cname] = {"ll": cll, "frames": per_hfov, "occlusion": occ}
            verdict = {}
            for p in args.pt:
                inside = status[p["name"]]
                hidden = any(o.startswith(p["name"] + " 可能被") for o in occ)
                if len(hfovs) == 1:
                    v = "全在画框内" if inside else "不全在画框内"
                elif len(inside) == len(hfovs):
                    v = "整个视角区间都在画框内"
                elif inside:
                    v = f"视角 {min(inside):.0f}–{max(inside):.0f}° 时在画框内，其余出框"
                else:
                    v = "整个视角区间都不在画框内"
                if hidden:
                    v += "；可能被挡"
                small = False
                if inside and "h" not in p:
                    v += "；没给高度 h，没检查够不够大、露不露出前景"
                    small = True
                elif inside and min_px.get(p["name"], 0) < args.min_px:
                    v += f"；最小只有 {min_px.get(p['name'], 0):.0f} px 高，可能看不出来"
                    small = True
                can_exclude = (v.startswith("整个视角区间都在") or (len(hfovs) == 1 and bool(inside))) \
                    and not hidden and not small
                verdict[p["name"]] = {"判断": v, "缺席能否排除此机位": "能" if can_exclude else "不能"}
            full[cname]["verdict"] = verdict
            summary_rows.append((cname, cll, verdict))
        for cname, cll, verdict in summary_rows[:60]:
            print(f"{cname} {cll[0]:.5f},{cll[1]:.5f}")
            frames = full[cname]["frames"]
            for n, v in verdict.items():
                print(f"   {n}: {v['判断']} → 缺席{'能' if v['缺席能否排除此机位'] == '能' else '不能'}排除")
            if len(hfovs) == 1:
                f0 = frames[0]
                print(f"   朝向 {f0['heading']}°：" + "；".join(
                    f"{r['name']} x={r['px']} {r['in_frame']}" + (f" 高{r['height_px']}px" if "height_px" in r else "")
                    for r in f0["points"]))
            else:
                a, b = frames[0], frames[-1]
                print(f"   朝向随视角 {a['hfov']}°→{b['hfov']}° 在 {a['heading']}°→{b['heading']}° 之间")
            for o in full[cname]["occlusion"]:
                print(f"   遮挡：{o}")
        if len(summary_rows) > 60:
            print(f"  …共 {len(summary_rows)} 个机位，完整结果看 --out")
        excl = [c for c, _, v in summary_rows if any(x["缺席能否排除此机位"] == "能" for x in v.values())]
        print(f"\n{len(summary_rows)} 个候选机位里，{len(excl)} 个可以用\"画面里没有某地标\"排除"
              "（前提：照片里确实没有该地标，且近处没有未列出的楼挡住那个方向）")
        if args.out:
            with open(args.out, "w") as fh:
                json.dump(full, fh, ensure_ascii=False, indent=1)
            excl_pts = {c: cams[c] for c in excl}
            keep_pts = {c: cams[c] for c in cams if c not in excl}
            base = args.out.rsplit(".", 1)[0]
            with open(base + "_keep.json", "w") as fh:
                json.dump(keep_pts, fh, indent=1)
            with open(base + "_excluded.json", "w") as fh:
                json.dump(excl_pts, fh, indent=1)
            print(f"-> {args.out}（保留的机位 {base}_keep.json，可排除的 {base}_excluded.json，可直接给 tiles.py mark）")
    elif args.cmd == "bearings":
        with open(args.geojson) as fh:
            gj = json.load(fh)
        rows = []
        for f in gj.get("features", []):
            g = f.get("geometry") or {}
            t = g.get("type")
            if t == "Polygon":
                coords = [(c[1], c[0]) for c in g["coordinates"][0]]
            elif t == "MultiPolygon":
                coords = [(c[1], c[0]) for poly in g["coordinates"] for c in poly[0]]
            elif t == "LineString":
                coords = [(c[1], c[0]) for c in g["coordinates"]]
            elif t == "Point":
                coords = [(g["coordinates"][1], g["coordinates"][0])]
            else:
                continue
            dists = [distance(args.at, c) for c in coords]
            if min(dists) > args.max_dist:
                continue
            brgs = [bearing(args.at, c) for c in coords]
            mx = sum(math.cos(math.radians(b)) for b in brgs)
            my = sum(math.sin(math.radians(b)) for b in brgs)
            center = math.degrees(math.atan2(my, mx)) % 360
            rel = [((b - center + 180) % 360) - 180 for b in brgs]
            props = f.get("properties") or {}
            tags = props.get("tags") or props
            name = tags.get("name") or f.get("id") or ""
            rows.append({"name": str(name), "bearing": round(center, 1), "span_deg": round(max(rel) - min(rel), 1),
                         "dist_m": round(min(dists)), "height": tags.get("height") or tags.get("building:height") or "",
                         "levels": tags.get("building:levels") or "", "kind": tags.get("building") or tags.get("man_made") or tags.get("power") or "",
                         "center": [round(sum(c[0] for c in coords) / len(coords), 6), round(sum(c[1] for c in coords) / len(coords), 6)]})
        if args.target is not None:
            for r in rows:
                r["d_bearing"] = round(((r["bearing"] - args.target + 180) % 360) - 180, 1)
            rows.sort(key=lambda r: abs(r["d_bearing"]))
        else:
            rows.sort(key=lambda r: r["bearing"])
        print(f"{len(rows)} 个要素（{args.max_dist:.0f} m 内）" + (f"，目标方位 {args.target}°，±{args.tol}° 内的标 *" if args.target is not None else ""))
        print(f"{'':1} {'方位':>6} {'角宽':>5} {'距离':>6} {'高/层':>7}  名字/类型")
        for r in rows[:60]:
            star = "*" if args.target is not None and abs(r["d_bearing"]) <= args.tol else " "
            print(f"{star} {r['bearing']:>6.1f} {r['span_deg']:>5.1f} {r['dist_m']:>6} {str(r['height'] or r['levels']):>7}  {r['name'][:28]} {r['kind']}")
        if args.target is not None:
            hits = [r for r in rows if abs(r["d_bearing"]) <= args.tol]
            print(f"方位对上的 {len(hits)} 个" + ("；对不上任何要素时，先怀疑朝向和倍率，再怀疑 OSM 没画" if not hits else "。角宽大的近处大楼会挡住后面的，高的才可能露出来"))
        if args.out:
            with open(args.out, "w") as fh:
                json.dump({(f"{'*' if args.target is not None and abs(r['d_bearing']) <= args.tol else ''}{r['bearing']:.0f}° {r['name'][:12]}"): r["center"] for r in rows}, fh, ensure_ascii=False, indent=1)
            print(f"-> {args.out}")
    elif args.cmd == "spacing":
        out = _spacing_run(args)
        cands = out["candidates"]
        if not cands:
            print(f"没有解：{out['n_fit']} 个组合通过 --pier-max {args.pier_max}。按这个顺序排查："
                  "① --cols 里混了非构件的峰（前景亮斑、栏杆、树），对着 imgprep.py piers 的 --sheet 剔干净；"
                  "② 被前景挡断的构件没用 ';' 分段（跨段的那个差不是一跨，整组就废了）；"
                  "③ 放宽 --pier-max；④ 检查 --span、--cx、--cols 是不是同一张图上量的；"
                  "⑤ 最后才怀疑 --center/--radius 圈错了地方")
        else:
            print(f"通过 --pier-max 的 {out['n_fit']} 个，按 tot 排前 {len(cands)}：")
            print(f"{'tot':>6} {'rms':>6} {'pier':>6} {'span':>6}  {'机位':^17} {'f':>6} {'H':>7} {'cc':>6} {'d首':>6} {'d尾':>6}")
            for r in cands:
                rms = "     -" if r["rms"] is None else format(r["rms"], "6.3f")
                cc = "     -" if r["cc"] is None else format(r["cc"], "6.2f")
                print(f"{r['tot']:6.3f} {rms} {r['pier']:6.3f} {r['span_m']:6.1f}  "
                      f"{r['cam'][0]:.5f},{r['cam'][1]:.5f} {r['f']:6.0f} {r['H']:7.2f} {cc} "
                      f"{r['d_first']:6.0f} {r['d_last']:6.0f}")
            b = cands[0]
            spread = max(distance(b["cam"], r["cam"]) for r in cands)
            print(f"最佳解：{b['cam'][0]:.5f},{b['cam'][1]:.5f} 朝向 {b['H']:.2f}° 焦距 {b['f']:.0f}px "
                  f"平均跨 {b['span_m']:.1f} m（标称 {args.span:g}）")
            print(f"前 {len(cands)} 名散在 {spread:.0f} m 内" + (
                "。只用间距这一条，解是沿视线的一条带；给 --ridge 和天际线联合能收窄（geometry.md 7.7）"
                if not args.ridge else "。拿最佳解去卫星图上核对桥墩位置，别只看分数"))
        if args.out:
            with open(args.out, "w") as fh:
                json.dump(out, fh, ensure_ascii=False, indent=1)
            print(f"-> {args.out}")
    elif args.cmd == "fov":
        lf, sf = fov_from_equiv_focal(args.focal)
        print(f"4:3 long_side={lf:.1f}deg short_side={sf:.1f}deg")
    elif args.cmd == "line":
        origin, brg = ray_from_alignment(args.near, args.far)
        a, b = (float(x) for x in args.range.split(":"))
        pts, k, dcur = {}, 0, a
        while dcur <= b + 1e-6:
            pts[f"L{int(dcur)}m"] = [round(v, 7) for v in dest(origin, brg, dcur)]
            dcur += args.step
            k += 1
        print(f"机位在 near 之外、方位 {brg:.1f}° 的射线上；{k} 个采样点")
        if args.out:
            with open(args.out, "w") as fh:
                json.dump(pts, fh, indent=1)
            print(f"-> {args.out}")
        else:
            for name, ll in pts.items():
                print(f"  {name}: {ll[0]},{ll[1]}")
    elif args.cmd == "intersect":
        def ray(align, sight):
            if align:
                n, fr = align.split(":")
                return ray_from_alignment(_pair(n), _pair(fr))
            if sight:
                ll, brg = sight.split("@")
                return ray_from_sighting(_pair(ll), float(brg))
            ap.error("每条线需要 --alignN 或 --sightN")
        r1, r2 = ray(args.align1, args.sight1), ray(args.align2, args.sight2)
        res = intersect_with_error(r1, r2, args.sigma)
        if res is None:
            print("两条线平行，或交点落在物体背后（检查 near/far 是否写反）")
        else:
            print(json.dumps(res, ensure_ascii=False))
            if res["crossing_angle_deg"] < 15:
                print("注意：两线夹角小于 15°，交点对方位误差很敏感，再找一条夹角更大的线")


if __name__ == "__main__":
    main()
