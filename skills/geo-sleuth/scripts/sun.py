#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""天空几何：太阳位置、影子、卫星电视锅。

太阳位置用 NOAA 算法（Meeus），1950–2050 年误差约 0.01°，含大气折射修正。
方位角一律是罗盘方位：0=北，顺时针。时间可以带时区（--tz Asia/Shanghai），默认当作 UTC。

  pos     某地某时的太阳方位角、高度角、1 米物体的影长、影子朝向
  ratio   影长比 ↔ 太阳高度角 换算（物体高 1，影长 r）
  locate  已知拍摄时刻 + 量出的高度角（或影长比）/影子朝向 → 在一个范围里找出符合的地带
  when    已知地点 + 高度角/影子朝向 → 反推一天里的哪些时刻（或一段日期里哪些天）符合
  dish    地球静止卫星的锅朝向；给锅的方位角还能反推经度
  street  已知地点和日期 + 影子与街道的夹角 → 街道走向候选（上午、下午分开列）
  facing  哪几面墙受光、哪几面背光 → 镜头朝向区间（没有可量的影子时用）
  compass 太阳在画面里 → 镜头朝向，和画面里任意物体的真实方位（没给时刻就分日出、日落两组）

示例：
  sun.py pos --at 39.9042,116.4074 --time 2023-08-15T16:20 --tz Asia/Shanghai
  sun.py ratio --shadow 1.2
  sun.py locate --time 2023-08-15T16:20 --tz Asia/Shanghai --ratio 1.2 --tol 1.5 --bbox 34,110,42,122
  sun.py locate --time 2023-08-15T16:20 --tz Asia/Shanghai --elev 40 --shadow-bearing 60 --az-tol 10 \
                --bbox 34,110,42,122 --mosaic north.jpg --out band.jpg
  sun.py when --at 30.25,120.16 --date 2024-10-01 --tz Asia/Shanghai --ratio 1.2 --shadow-bearing 30
  sun.py when --at 30.25,120.16 --dates 2024-01-01:2024-12-31 --tz Asia/Shanghai --elev 40 --shadow-bearing 330
  sun.py dish --at 31.23,121.47 --sat 92.2
  sun.py dish --lat 31.2 --sat 92.2 --azimuth 215     # 锅朝 215°，反推经度
  sun.py compass --at <lat,lon> --time 07:40 --dates 2024-09-01:2024-10-15 --tz <IANA 时区> --sun-x 1200 --width 4000 --hfov 60:70 --x 2900
  sun.py compass --at <lat,lon> --tz <IANA 时区> --sun-x 2600 --width 4032 --x 1500        # 没时刻没日期：全年早晚两组
  sun.py street --at 49.25,-123.10 --date 2025-04-01 --tz America/Vancouver --ratio 1.5 --tol 4 --shadow-rel 90
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------- 太阳位置

_D = math.degrees
_R = math.radians


def _sun_core(dt_utc: datetime) -> tuple[float, float]:
    """返回 (太阳赤纬°, 均时差 分钟)。"""
    jd = dt_utc.timestamp() / 86400 + 2440587.5
    t = (jd - 2451545) / 36525
    l0 = (280.46646 + t * (36000.76983 + t * 0.0003032)) % 360
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    c = (math.sin(_R(m)) * (1.914602 - t * (0.004817 + 0.000014 * t))
         + math.sin(_R(2 * m)) * (0.019993 - 0.000101 * t) + math.sin(_R(3 * m)) * 0.000289)
    app_long = l0 + c - 0.00569 - 0.00478 * math.sin(_R(125.04 - 1934.136 * t))
    obliq0 = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60
    obliq = obliq0 + 0.00256 * math.cos(_R(125.04 - 1934.136 * t))
    decl = _D(math.asin(math.sin(_R(obliq)) * math.sin(_R(app_long))))
    y = math.tan(_R(obliq / 2)) ** 2
    eqt = 4 * _D(y * math.sin(2 * _R(l0)) - 2 * e * math.sin(_R(m))
                 + 4 * e * y * math.sin(_R(m)) * math.cos(2 * _R(l0))
                 - 0.5 * y * y * math.sin(4 * _R(l0)) - 1.25 * e * e * math.sin(2 * _R(m)))
    return decl, eqt


def _refraction(h: float) -> float:
    if h > 85:
        return 0.0
    te = math.tan(_R(h))
    if h > 5:
        r = 58.1 / te - 0.07 / te ** 3 + 0.000086 / te ** 5
    elif h > -0.575:
        r = 1735 + h * (-518.2 + h * (103.4 + h * (-12.79 + h * 0.711)))
    else:
        r = -20.772 / te
    return r / 3600


def sun_position(lat: float, lon: float, dt_utc: datetime, refraction: bool = True) -> tuple[float, float]:
    """(方位角°, 高度角°)。dt_utc 必须带 UTC 时区。"""
    decl, eqt = _sun_core(dt_utc)
    minutes = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60 + dt_utc.microsecond / 6e7
    tst = (minutes + eqt + 4 * lon) % 1440
    ha = tst / 4 + 180 if tst / 4 < 0 else tst / 4 - 180
    cz = math.sin(_R(lat)) * math.sin(_R(decl)) + math.cos(_R(lat)) * math.cos(_R(decl)) * math.cos(_R(ha))
    zen = _D(math.acos(max(-1.0, min(1.0, cz))))
    elev = 90 - zen
    denom = math.cos(_R(lat)) * math.sin(_R(zen))
    if abs(denom) < 1e-9:
        az = 180.0
    else:
        ca = max(-1.0, min(1.0, (math.sin(_R(lat)) * math.cos(_R(zen)) - math.sin(_R(decl))) / denom))
        az = (_D(math.acos(ca)) + 180) % 360 if ha > 0 else (540 - _D(math.acos(ca))) % 360
    if refraction:
        elev += _refraction(elev)
    return az, elev


def subsolar_point(dt_utc: datetime) -> tuple[float, float]:
    """太阳直射点 (lat, lon)。同一时刻太阳高度角相同的点，是以它为圆心、半径 90°-高度角 的圆。"""
    decl, eqt = _sun_core(dt_utc)
    minutes = dt_utc.hour * 60 + dt_utc.minute + dt_utc.second / 60
    lon = -(minutes + eqt - 720) / 4
    return decl, (lon + 540) % 360 - 180


def shadow_ratio(elev: float) -> float:
    """1 米竖直物体在水平地面上的影长（米）。"""
    return math.inf if elev <= 0 else 1 / math.tan(_R(elev))


def elev_from_ratio(ratio: float) -> float:
    return _D(math.atan(1 / ratio))


def _ang_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


# ---------------------------------------------------------------- 卫星锅

_RE, _RGEO = 6378.137, 42164.0


def dish_pointing(lat: float, lon: float, sat_lon: float) -> tuple[float, float]:
    """地面 (lat, lon) 指向经度 sat_lon 的地球静止卫星：(方位角°, 仰角°)。"""
    la, lo = _R(lat), _R(lon)
    gx, gy, gz = _RE * math.cos(la) * math.cos(lo), _RE * math.cos(la) * math.sin(lo), _RE * math.sin(la)
    sx, sy, sz = _RGEO * math.cos(_R(sat_lon)), _RGEO * math.sin(_R(sat_lon)), 0.0
    dx, dy, dz = sx - gx, sy - gy, sz - gz
    east = -math.sin(lo) * dx + math.cos(lo) * dy
    north = -math.sin(la) * math.cos(lo) * dx - math.sin(la) * math.sin(lo) * dy + math.cos(la) * dz
    up = math.cos(la) * math.cos(lo) * dx + math.cos(la) * math.sin(lo) * dy + math.sin(la) * dz
    return (_D(math.atan2(east, north)) + 360) % 360, _D(math.atan2(up, math.hypot(east, north)))


# 常见卫星（经度，东经为正）
SATELLITES = {
    "chinasat9": (92.2, "中星9号：国内户户通/村村通小锅，全国最常见"),
    "chinasat6b": (115.5, "中星6B：有线电视前端、单位的大锅"),
    "asiasat7": (105.5, "亚洲7号"),
    "apstar6c": (134.0, "亚太6C"),
    "astra1": (19.2, "Astra 1：德国、奥地利等中欧"),
    "hotbird": (13.0, "Hot Bird：意大利、波兰等"),
    "astra2": (28.2, "Astra 2：英国、爱尔兰"),
    "eutelsat5w": (-5.0, "Eutelsat 5W：法国、西班牙部分"),
    "nilesat": (-7.0, "Nilesat：中东、北非"),
    "turksat": (42.0, "Türksat：土耳其"),
}


# ---------------------------------------------------------------- 输入解析

def _pair(s: str) -> tuple[float, float]:
    a, b = s.split(",")
    return float(a), float(b)


def _to_utc(s: str, tz: str | None) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz) if tz else timezone.utc)
    return dt.astimezone(timezone.utc)


def _target_elev(args) -> float | None:
    if getattr(args, "ratio", None) is not None:
        return elev_from_ratio(args.ratio)
    return getattr(args, "elev", None)


def _target_az(args) -> float | None:
    """统一成太阳方位角。影子朝向 = 太阳方位 + 180。"""
    if getattr(args, "shadow_bearing", None) is not None:
        return (args.shadow_bearing + 180) % 360
    return getattr(args, "sun_azimuth", None)


# ---------------------------------------------------------------- 子命令

def cmd_pos(args) -> None:
    lat, lon = args.at
    t = _to_utc(args.time, args.tz)
    az, el = sun_position(lat, lon, t)
    ss = subsolar_point(t)
    print(json.dumps({
        "utc": t.isoformat(timespec="minutes"), "sun_azimuth": round(az, 2), "sun_elevation": round(el, 2),
        "shadow_len_per_1m": None if el <= 0 else round(shadow_ratio(el), 3),
        "shadow_bearing": round((az + 180) % 360, 1), "subsolar_point": [round(ss[0], 3), round(ss[1], 3)],
    }, ensure_ascii=False))


def cmd_ratio(args) -> None:
    if args.shadow is not None:
        print(f"影长比 1:{args.shadow} → 太阳高度角 {elev_from_ratio(args.shadow):.2f}°")
    else:
        print(f"太阳高度角 {args.elev}° → 1 米物体影长 {shadow_ratio(args.elev):.3f} 米")


def _matches(lat, lon, times, tel, tol, taz, az_tol) -> bool:
    for t in times:
        az, el = sun_position(lat, lon, t)
        if tel is not None and abs(el - tel) > tol:
            continue
        if taz is not None and _ang_diff(az, taz) > az_tol:
            continue
        if el <= 0:
            continue
        return True
    return False


def cmd_locate(args) -> None:
    tel, taz = _target_elev(args), _target_az(args)
    if tel is None and taz is None:
        sys.exit("需要 --elev / --ratio 或 --shadow-bearing / --sun-azimuth 至少一个")
    t0 = _to_utc(args.time, args.tz)
    k = max(0, int(args.time_tol // 5))
    times = [t0 + timedelta(minutes=5 * i) for i in range(-k, k + 1)] if args.time_tol else [t0]
    s, w, n, e = args.bbox
    step = args.step
    pts = []
    lat = s
    while lat <= n + 1e-9:
        lon = w
        while lon <= e + 1e-9:
            if _matches(lat, lon, times, tel, args.tol, taz, args.az_tol):
                pts.append((round(lat, 4), round(lon, 4)))
            lon += step
        lat += step
    ss = subsolar_point(t0)
    out = {"utc": t0.isoformat(timespec="minutes"), "target_elev": None if tel is None else round(tel, 2),
           "target_sun_azimuth": None if taz is None else round(taz, 1), "subsolar_point": [round(ss[0], 3), round(ss[1], 3)],
           "equal_elev_circle_radius_km": None if tel is None else round((90 - tel) * 111.195, 0),
           "grid_step_deg": step, "matched_points": len(pts)}
    if pts:
        lats, lons = [p[0] for p in pts], [p[1] for p in pts]
        out["matched_bbox"] = [min(lats), min(lons), max(lats), max(lons)]
        cols: dict[float, list[float]] = {}
        for la, lo in pts:
            cols.setdefault(round(lo, 2), []).append(la)
        every = max(1, len(cols) // 12)
        out["lat_range_by_lon"] = {f"{lo:.2f}": [min(v), max(v)] for i, (lo, v) in enumerate(sorted(cols.items())) if i % every == 0}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.points:
        args.points.write_text(json.dumps({f"p{i}": list(p) for i, p in enumerate(pts)}), encoding="utf-8")
        print(f"points -> {args.points}")
    if args.mosaic:
        _draw(args.mosaic, pts, step, args.out or args.mosaic.with_name(args.mosaic.stem + "_sun.jpg"))


def _draw(mosaic: Path, pts, step, out: Path) -> None:
    from PIL import Image, ImageDraw
    from tiles import Mosaic
    m = Mosaic(mosaic)
    im = Image.open(mosaic).convert("RGBA")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for la, lo in pts:
        x0, y0 = m.to_px(la + step / 2, lo - step / 2)
        x1, y1 = m.to_px(la - step / 2, lo + step / 2)
        d.rectangle([x0, y0, x1, y1], fill=(255, 210, 0, 90))
    Image.alpha_composite(im, ov).convert("RGB").save(out, quality=88)
    print(f"map -> {out}")


def _scan_day(lat, lon, day: date, tz: ZoneInfo, tel, tol, taz, az_tol, step_min: int):
    """返回这一天里符合条件的时间窗 [(开始, 结束, 中点方位角, 中点高度角)]。"""
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    wins, cur = [], None
    for i in range(0, 24 * 60, step_min):
        lt = start + timedelta(minutes=i)
        az, el = sun_position(lat, lon, lt.astimezone(timezone.utc))
        ok = el > 0 and (tel is None or abs(el - tel) <= tol) and (taz is None or _ang_diff(az, taz) <= az_tol)
        if ok:
            cur = [lt, lt, []] if cur is None else [cur[0], lt, cur[2]]
            cur[2].append((az, el))
        elif cur is not None:
            wins.append(cur)
            cur = None
    if cur is not None:
        wins.append(cur)
    res = []
    for a, b, vals in wins:
        az, el = vals[len(vals) // 2]
        res.append((a, b, az, el))
    return res


def cmd_when(args) -> None:
    tel, taz = _target_elev(args), _target_az(args)
    if tel is None and taz is None:
        sys.exit("需要 --elev / --ratio 或 --shadow-bearing / --sun-azimuth 至少一个")
    tz = ZoneInfo(args.tz) if args.tz else timezone.utc
    lat, lon = args.at
    if args.dates:
        a, b = (date.fromisoformat(x) for x in args.dates.split(":"))
        days = [a + timedelta(days=i) for i in range((b - a).days + 1)]
    else:
        days = [date.fromisoformat(args.date)]
    hits = 0
    for d in days:
        for s, e, az, el in _scan_day(lat, lon, d, tz, tel, args.tol, taz, args.az_tol, args.step_min):
            hits += 1
            mid = s + (e - s) / 2
            _, e1 = sun_position(lat, lon, (mid - timedelta(minutes=5)).astimezone(timezone.utc))
            _, e2 = sun_position(lat, lon, (mid + timedelta(minutes=5)).astimezone(timezone.utc))
            rate = abs(e2 - e1) / 10
            sens = f"  高度角每分钟变 {rate:.2f}°，差 1° ≈ {1 / rate:.0f} 分钟" if rate > 1e-3 else "  正午前后高度角几乎不变，时刻分辨率很差"
            print(f"{d} {s:%H:%M}–{e:%H:%M}  太阳方位 {az:5.1f}°  高度 {el:4.1f}°  影子朝 {(az + 180) % 360:5.1f}°  "
                  f"影长比 1:{shadow_ratio(el):.2f}{sens}")
    if not hits:
        print("没有符合条件的时刻（放宽 --tol / --az-tol，或检查时区与方位是否弄反）")


def cmd_dish(args) -> None:
    sat = args.sat
    if args.at:
        lat, lon = args.at
        az, el = dish_pointing(lat, lon, sat)
        print(f"地点 {lat},{lon} 指向东经 {sat}° 卫星：方位角 {az:.1f}°，仰角 {el:.1f}°")
        return
    if args.azimuth is None or args.lat is None:
        sys.exit("正算给 --at；反推经度给 --lat 和 --azimuth")
    best = []
    for i in range(-1800, 1801):
        lon = i / 10
        az, el = dish_pointing(args.lat, lon, sat)
        if el > 0 and _ang_diff(az, args.azimuth) <= args.az_tol:
            best.append((lon, az, el))
    if not best:
        print("该纬度上没有经度符合（锅可能对的是别的卫星）")
        return
    print(f"纬度 {args.lat}、锅方位 {args.azimuth}±{args.az_tol}° 对东经 {sat}° 卫星 → 经度范围 {best[0][0]}° ~ {best[-1][0]}°，"
          f"仰角约 {best[len(best) // 2][2]:.0f}°")


def cmd_facing(args) -> None:
    """哪几面墙受光 / 背光 → 镜头朝向区间。墙受光 ⟺ |太阳方位 − 墙面法向| < 90°。

    墙面按"在画面里朝哪边"描述：camera=正对镜头（法向 = 朝向+180）、left=朝画面左（朝向−90）、
    right=朝画面右（朝向+90）、away=背对镜头（法向 = 朝向）。
    """
    lat, lon = args.at
    t = _to_utc(args.time, args.tz)
    az, el = sun_position(lat, lon, t)
    if el <= 0:
        print(f"该时刻太阳在地平线下（高度 {el:.1f}°），受光面法用不上")
        return
    offs = {"camera": 180.0, "left": -90.0, "right": 90.0, "away": 0.0}
    lit = [w for w in (args.lit or "").split(",") if w]
    shaded = [w for w in (args.shaded or "").split(",") if w]
    bad = [w for w in lit + shaded if w not in offs]
    if bad:
        sys.exit(f"墙面只能写 camera/left/right/away，收到：{bad}")
    ok = []
    for h in range(0, 360):
        good = True
        for w in lit:
            if _ang_diff(az, (h + offs[w]) % 360) >= 90 - args.margin:
                good = False
        for w in shaded:
            if _ang_diff(az, (h + offs[w]) % 360) <= 90 + args.margin:
                good = False
        if good:
            ok.append(h)
    print(f"太阳方位 {az:.1f}°、高度 {el:.1f}°（影子朝 {(az + 180) % 360:.1f}°）")
    if not ok:
        print("没有朝向能同时满足这些受光/背光条件：检查哪面墙受光看错了，或时刻/时区不对（也可能是拼图）")
        return
    runs, start = [], ok[0]
    for a, b in zip(ok, ok[1:] + [None]):
        if b is None or b != a + 1:
            runs.append((start, a))
            start = b
    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == 359:      # 跨北方向合并
        runs = [(runs[-1][0] - 360, runs[0][1])] + runs[1:-1]
    print("镜头朝向可能区间：" + "，".join(f"{a % 360}°–{b % 360}°" for a, b in runs))
    print("提示：区间边界处墙面几乎平行于阳光，明暗差别很小，别当硬边界（--margin 调保守程度）")


def cmd_street(args) -> None:
    """夹角在俯视图里量：从街道方向顺时针转到影子方向。分不清顺逆时针时两个都列（--both）。"""
    tz = ZoneInfo(args.tz) if args.tz else timezone.utc
    lat, lon = args.at
    tel = _target_elev(args)
    day = date.fromisoformat(args.date)
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    rows = []
    for i in range(0, 24 * 60, args.step_min):
        lt = start + timedelta(minutes=i)
        az, el = sun_position(lat, lon, lt.astimezone(timezone.utc))
        if el <= 2 or (tel is not None and abs(el - tel) > args.tol):
            continue
        shadow = (az + 180) % 360
        cands = {round((shadow - args.shadow_rel) % 180)}
        if args.both:
            cands.add(round((shadow + args.shadow_rel) % 180))
        rows.append((lt, az, el, shadow, sorted(cands)))
    if not rows:
        print("没有符合的时刻（高度角容差放宽，或检查日期/时区）")
        return
    step = max(1, len(rows) // 16)
    for k, (lt, az, el, shadow, cands) in enumerate(rows):
        if k % step and k != len(rows) - 1:
            continue
        half = "上午" if lt.hour < 12 else "下午"
        print(f"{lt:%H:%M} {half}  太阳 {az:5.1f}°/{el:4.1f}°  影子朝 {shadow:5.1f}°  → 街道走向 "
              + " 或 ".join(f"{c}°–{c + 180}°" for c in cands))
    print("街道走向按 0–180° 表示（47° 即东北—西南向）。上午和下午两组结果都要带着，除非有别的证据分出上下午。")



def _px_angle(x: float, width: float, hfov: float) -> float:
    """像素列 x 相对画面中心的水平角（°，右为正）。"""
    f = (width / 2) / math.tan(math.radians(hfov) / 2)
    return math.degrees(math.atan((x - width / 2) / f))


def cmd_compass(args) -> None:
    """太阳在画面里 → 镜头朝向，以及画面里任意一列像素（塔、烟囱、路口）的真实方位。

    给了时刻：直接用那一刻的太阳方位（日期不确定时 --dates 给区间，方位跟着变成区间）。
    没给时刻：按 --dates 里每天太阳高度在 0–--elev-max 之间的早晚两段分别算，日出、日落两组结果都列。
    """
    lat, lon = args.at
    tz = ZoneInfo(args.tz) if args.tz else timezone.utc
    if args.dates:
        a, b = (date.fromisoformat(x) for x in args.dates.split(":"))
    elif args.time and "T" in args.time:
        a = b = datetime.fromisoformat(args.time).date()
    else:
        a, b = date(2025, 1, 1), date(2025, 12, 31)
        print("没给日期：按全年算。发帖时间不等于拍摄时间，有物候、穿着、雪能定季节再用 --dates 缩小")
    groups: dict[str, list[float]] = {}
    lo_el, hi_el = (float(x) for x in args.elev.split(":")) if args.elev else (None, None)
    dropped: list[date] = []
    d = a
    while d <= b:
        if args.time:
            hh, mm = (args.time.split("T")[-1].split(":") + ["0"])[:2]
            lt = datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=tz)
            az, el = sun_position(lat, lon, lt.astimezone(timezone.utc))
            if (el > -1 if lo_el is None else lo_el <= el <= hi_el):
                groups.setdefault(f"{int(hh):02d}:{int(mm):02d}", []).append(az)
            elif lo_el is not None:
                dropped.append(d)
        else:
            start = datetime(d.year, d.month, d.day, tzinfo=tz)
            for i in range(0, 24 * 60, 4):
                lt = start + timedelta(minutes=i)
                az, el = sun_position(lat, lon, lt.astimezone(timezone.utc))
                if (0 < el <= args.elev_max) if lo_el is None else (lo_el <= el <= hi_el):
                    groups.setdefault("早上（日出一侧）" if lt.hour < 12 else "傍晚（日落一侧）", []).append(az)
        d += timedelta(days=max(1, args.step_days))
    if dropped:
        runs, s0 = [], dropped[0]
        for x, y in zip(dropped, dropped[1:] + [None]):
            if y is None or (y - x).days > max(1, args.step_days):
                runs.append((s0, x))
                s0 = y
        print("太阳高度不在 --elev 区间、已排除的日期：" + "，".join(f"{p:%m-%d}–{q:%m-%d}" for p, q in runs))
    if not groups:
        print("这些日期里没有符合的太阳位置（太阳在地平线下，或 --elev / --elev-max 给得太窄）")
        return
    h0, h1 = (float(x) for x in args.hfov.split(":"))
    xs = [float(v) for s in (args.x or []) for v in s.split(",")]
    for name, azs in groups.items():
        lo, hi = min(azs), max(azs)
        cands = []
        for hf in (h0, h1):
            off = _px_angle(args.sun_x, args.width, hf)
            cands += [(lo - off) % 360, (hi - off) % 360]
        print(f"{name}：太阳方位 {lo:.1f}°–{hi:.1f}°；太阳在画面 x={args.sun_x:.0f}（偏离中心 "
              f"{_px_angle(args.sun_x, args.width, h0):+.1f}° 到 {_px_angle(args.sun_x, args.width, h1):+.1f}°）"
              f" → 镜头朝向约 {min(cands):.0f}°–{max(cands):.0f}°")
        for x in xs:
            bs = []
            for hf in (h0, h1):
                rel = _px_angle(x, args.width, hf) - _px_angle(args.sun_x, args.width, hf)
                bs += [(lo + rel) % 360, (hi + rel) % 360]
            print(f"    x={x:.0f} 的物体：方位约 {min(bs):.0f}°–{max(bs):.0f}°（相对太阳 "
                  f"{_px_angle(x, args.width, h0) - _px_angle(args.sun_x, args.width, h0):+.1f}° 到 "
                  f"{_px_angle(x, args.width, h1) - _px_angle(args.sun_x, args.width, h1):+.1f}°）")
    print("跨北方向（如 350°–10°）时区间按顺时针读。视角不确定就放宽 --hfov；日出、日落两组分不开时两个朝向都要建俯视模板。")


def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pos", help="某地某时的太阳位置")
    p.add_argument("--at", type=_pair, required=True, help="lat,lon")
    p.add_argument("--time", required=True, help="2024-06-06T15:39，可带 +08:00")
    p.add_argument("--tz", help="IANA 时区，如 Asia/Shanghai、Europe/Berlin")

    r = sub.add_parser("ratio", help="影长比 ↔ 高度角")
    g = r.add_mutually_exclusive_group(required=True)
    g.add_argument("--shadow", type=float, help="物体高 1 时的影长")
    g.add_argument("--elev", type=float)

    def targets(sp):
        sp.add_argument("--elev", type=float, help="太阳高度角°")
        sp.add_argument("--ratio", type=float, help="影长比（物体高 1 时的影长），和 --elev 二选一")
        sp.add_argument("--tol", type=float, default=2.0, help="高度角容差°，默认 2")
        sp.add_argument("--shadow-bearing", type=float, help="影子指向的罗盘方位°（从物体指向影子末端）")
        sp.add_argument("--sun-azimuth", type=float, help="太阳方位角°，和 --shadow-bearing 二选一")
        sp.add_argument("--az-tol", type=float, default=10.0, help="方位容差°，默认 10")
        sp.add_argument("--tz")

    lo = sub.add_parser("locate", help="已知时刻 → 找出符合太阳条件的地带")
    lo.add_argument("--time", required=True)
    targets(lo)
    lo.add_argument("--time-tol", type=float, default=0, help="拍摄时刻不确定的分钟数（±）")
    lo.add_argument("--bbox", type=lambda s: tuple(map(float, s.split(","))), required=True, help="south,west,north,east")
    lo.add_argument("--step", type=float, default=0.1, help="网格步长°，默认 0.1（约 11 km）")
    lo.add_argument("--points", type=Path, help="把命中点写成 {name:[lat,lon]}，可给 tiles.py mark")
    lo.add_argument("--mosaic", type=Path, help="tiles.py fetch 出的底图，在上面画出命中地带")
    lo.add_argument("--out", type=Path)

    w = sub.add_parser("when", help="已知地点 → 反推拍摄时刻/日期")
    w.add_argument("--at", type=_pair, required=True)
    dg = w.add_mutually_exclusive_group(required=True)
    dg.add_argument("--date", help="单日 2024-10-01")
    dg.add_argument("--dates", help="日期范围 2024-01-01:2024-12-31")
    targets(w)
    w.add_argument("--step-min", type=int, default=2)

    d = sub.add_parser("dish", help="卫星锅朝向 / 由朝向反推经度")
    d.add_argument("--sat", type=float, default=92.2, help="卫星经度，默认中星9号 92.2")
    d.add_argument("--at", type=_pair, help="lat,lon：正算")
    d.add_argument("--lat", type=float, help="反推：已知纬度")
    d.add_argument("--azimuth", type=float, help="反推：锅的方位角")
    d.add_argument("--az-tol", type=float, default=5.0)

    st = sub.add_parser("street", help="影子与街道的夹角 → 街道走向候选")
    st.add_argument("--at", type=_pair, required=True, help="城市内任一点 lat,lon")
    st.add_argument("--date", required=True)
    st.add_argument("--shadow-rel", type=float, required=True, help="俯视图里从街道方向顺时针到影子方向的角度；影子垂直街道填 90")
    st.add_argument("--both", action="store_true", help="分不清顺时针还是逆时针时，两种都列")
    st.add_argument("--elev", type=float, help="量得的太阳高度角，用来只保留符合的时刻")
    st.add_argument("--ratio", type=float, help="影长比，和 --elev 二选一")
    st.add_argument("--tol", type=float, default=3.0)
    st.add_argument("--tz")
    st.add_argument("--step-min", type=int, default=10)

    fc = sub.add_parser("facing", help="哪几面墙受光 → 镜头朝向区间")
    fc.add_argument("--at", type=_pair, required=True)
    fc.add_argument("--time", required=True)
    fc.add_argument("--tz")
    fc.add_argument("--lit", help="受光的墙，逗号分隔：camera,left,right,away")
    fc.add_argument("--shaded", help="背光的墙，同上")
    fc.add_argument("--margin", type=float, default=5, help="边界余量°，默认 5")

    cp = sub.add_parser("compass", help="太阳在画面里 → 镜头朝向、画面里物体的方位（没时刻时列日出日落两组）")
    cp.add_argument("--at", type=_pair, required=True, help="候选地区里任一点 lat,lon")
    cp.add_argument("--time", help="钟表时刻 07:40，或完整 2024-09-20T07:40；不给就按低太阳算早晚两组")
    cp.add_argument("--dates", help="日期区间 2024-09-01:2024-10-15；不给就按全年算")
    cp.add_argument("--step-days", type=int, default=3)
    cp.add_argument("--tz")
    cp.add_argument("--elev-max", type=float, default=12, help="没给时刻时：太阳高度上限°（画面里太阳贴近地平线取 5–12）")
    cp.add_argument("--elev", help="太阳高度区间° lo:hi（按画面里太阳离地平线/林线多高估）：给了时刻时剔除高度不符的日期，没给时刻时代替 0–--elev-max")
    cp.add_argument("--sun-x", type=float, required=True, help="太阳在画面里的像素列")
    cp.add_argument("--width", type=float, required=True, help="画面宽度（像素）")
    cp.add_argument("--hfov", default="55:75", help="水平视角区间°；手机横拍主摄约 65–75，竖拍约 50–60，截图/变焦更窄")
    cp.add_argument("--x", action="append", help="要算方位的物体像素列，逗号分隔或重复写")

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    {"pos": cmd_pos, "ratio": cmd_ratio, "locate": cmd_locate, "when": cmd_when, "dish": cmd_dish,
     "street": cmd_street, "facing": cmd_facing, "compass": cmd_compass}[args.cmd](args)


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
