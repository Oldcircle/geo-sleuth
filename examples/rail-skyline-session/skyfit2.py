# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""第二轮：机位网格 + 三条约束一起打分。

这是第 13 集案例的专用脚本，照片参数写死：焦距 F0、地平线行 HROW、山脊 26 个像素点 ridge、
平地平线列范围 FLX 都是那张照片量出来的。只作复现记录，不保证在别的照片上能跑。
A 机位地面平（300 m 内起伏 < 8 m）
B 画面左段 [-27°,-10°] 有桥（250–1000 m），右段 [3°,27°] 有桥（400–2000 m）
C 山脊线 RMS（朝向、地平线偏移、焦距比例一起搜）
D 左段 [-27°,-12°] 天际线 < 1°
"""
import json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/geo-sleuth/scripts"))
import terrain  # noqa

Z = 11
CACHE = Path(".geo-cache/dem")
F0, HROW, CX = 1281.0, 935.0, 640.0
ridge = {760: 826, 780: 816, 800: 813, 820: 811, 840: 810, 860: 804, 880: 794, 900: 787, 920: 783, 940: 771, 960: 765,
         980: 757, 1000: 755, 1020: 747, 1040: 741, 1060: 740, 1080: 738, 1100: 737, 1120: 738, 1140: 736, 1160: 735,
         1180: 734, 1200: 725, 1220: 728, 1240: 725, 1260: 724}
RX = np.array(list(ridge.keys()), float); RY = np.array(list(ridge.values()), float)
FLX = np.arange(0, 281, 20, dtype=float)
R = 6371008.8

hits = json.load(open(sys.argv[1]))
a0, a1 = (int(v) for v in sys.argv[3].split(":"))

# 桥采样点（100 m）
gj = json.load(open("rail_bridges.geojson"))
cell = {}
def add(lat, lon):
    cell.setdefault((int(lat / 0.02), int(lon / 0.02)), []).append((lat, lon))
for f in gj["features"]:
    if f["properties"].get("electrified") == "no":
        continue
    c = f["geometry"]["coordinates"]
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        d = math.hypot((x2 - x1) * 111320 * math.cos(math.radians(y1)), (y2 - y1) * 110540)
        n = max(1, int(d // 100))
        for k in range(n + 1):
            add(y1 + (y2 - y1) * k / n, x1 + (x2 - x1) * k / n)

def bridges_near(lat, lon):
    i, j = int(lat / 0.02), int(lon / 0.02)
    out = []
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            out += cell.get((i + di, j + dj), [])
    return np.array(out) if out else np.zeros((0, 2))

AZ = np.arange(0, 360, 0.5)
NS = 260
DIST = 150 * (15000 / 150) ** (np.arange(NS) / (NS - 1))
HS = np.arange(0, 720)  # 0.5° 步长朝向

def fit(hor):
    best = None
    for fs in (0.9, 1.0, 1.12):
        f = F0 * fs
        r_off = np.degrees(np.arctan((RX - CX) / f)); r_el = np.degrees(np.arctan((HROW - RY) / f))
        fl_off = np.degrees(np.arctan((FLX - CX) / f))
        ri = (HS[:, None] + np.round(r_off / 0.5).astype(int)[None, :]) % 720
        fi = (HS[:, None] + np.round(fl_off / 0.5).astype(int)[None, :]) % 720
        diff = hor[ri] - r_el[None, :]
        cc = np.clip(np.median(diff, axis=1), -0.7, 0.7)
        rms = np.sqrt(np.mean((diff - cc[:, None]) ** 2, axis=1))
        pen = np.mean(np.clip(hor[fi] - cc[:, None] - 1.0, 0, None), axis=1)
        s = rms + 1.5 * pen
        k = int(np.argmin(s))
        if best is None or s[k] < best[0]:
            best = (float(s[k]), float(rms[k]), float(pen[k]), k * 0.5, fs, float(cc[k]))
    return best

out = []
done_cams = set()
for hi, h in list(enumerate(hits))[a0:a1]:
    lat, lon = h["lat"], h["lon"]
    try:
        dem = terrain.DEM((lat, lon), 17500, Z, CACHE, None)
    except SystemExit:
        continue
    br = bridges_near(lat, lon)
    # 机位网格：半径 2 km，250 m 间距
    for dy in np.arange(-2000, 2001, 250):
        for dx in np.arange(-2000, 2001, 250):
            if dx * dx + dy * dy > 2000 ** 2:
                continue
            clat = lat + dy / 110540; clon = lon + dx / (111320 * math.cos(math.radians(lat)))
            key = (round(clat / 0.00225), round(clon / 0.00245))
            if key in done_cams:
                continue
            done_cams.add(key)
            # A 平地
            ring = terrain._dest_np(clat, clon, np.arange(0, 360, 45.0), np.array([0, 150, 300.0]))
            g = dem.sample(ring[0], ring[1])
            if g.max() - g.min() > 8:
                continue
            g0 = float(g[:, 0].mean())
            # B 桥分布（先粗算方位，朝向未知 → 存下每个桥点的方位和距离）
            if len(br) == 0:
                continue
            by = (br[:, 0] - clat) * 110540; bx = (br[:, 1] - clon) * 111320 * math.cos(math.radians(clat))
            bd = np.hypot(bx, by); baz = np.degrees(np.arctan2(bx, by)) % 360
            m = (bd > 250) & (bd < 2000)
            if m.sum() < 3:
                continue
            baz, bd = baz[m], bd[m]
            la, lo = terrain._dest_np(clat, clon, AZ, DIST)
            hh = dem.sample(la, lo)
            drop = DIST ** 2 / (2 * R) * 0.87
            ang = np.degrees(np.arctan2(hh - drop[None, :] - g0 - 1.6, DIST[None, :]))
            hor = ang.max(axis=1)
            if hor.max() < 6:
                continue
            best = fit(hor)
            s, rms, pen, H, fs, cc = best
            f = F0 * fs
            hf = math.degrees(math.atan(640 / f))
            off = (baz - H + 180) % 360 - 180
            left = ((off > -hf) & (off < -10) & (bd < 1000)).sum()
            right = ((off > 3) & (off < hf) & (bd > 400)).sum()
            bpen = (0 if left else 0.25) + (0 if right else 0.25)
            out.append({"hit": hi, "name": h["name"], "cam": [round(clat, 5), round(clon, 5)], "g": round(g0),
                        "H": H, "fs": fs, "cc": round(cc, 2), "rms": round(rms, 3), "flatpen": round(pen, 3),
                        "left_br": int(left), "right_br": int(right), "score": round(s + bpen, 3)})
    print(hi, h["name"], len(out), file=sys.stderr, flush=True)
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False)
