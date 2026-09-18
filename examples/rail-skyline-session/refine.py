# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""局部精搜：给定中心，100 m 网格机位，z13 DEM 天际线 + 桥线距离一起打分。

这是第 13 集案例的专用脚本，照片参数写死（焦距、地平线行、山脊点、期望桥距 430/660/1150 m）。
只作复现记录，不保证在别的照片上能跑。
用法: refine.py lat,lon radius_m out.json
"""
import json, math, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/geo-sleuth/scripts"))
import terrain  # noqa

lat0, lon0 = map(float, sys.argv[1].split(","))
RAD = float(sys.argv[2])
Z = 13
F0, HROW, CX = 1281.0, 935.0, 640.0
ridge = {760: 826, 780: 816, 800: 813, 820: 811, 840: 810, 860: 804, 880: 794, 900: 787, 920: 783, 940: 771, 960: 765,
         980: 757, 1000: 755, 1020: 747, 1040: 741, 1060: 740, 1080: 738, 1100: 737, 1120: 738, 1140: 736, 1160: 735,
         1180: 734, 1200: 725, 1220: 728, 1240: 725, 1260: 724}
RX = np.array(list(ridge.keys()), float); RY = np.array(list(ridge.values()), float)
FLX = np.arange(0, 281, 20, dtype=float)
R = 6371008.8
dem = terrain.DEM((lat0, lon0), RAD + 16000, Z, Path(".geo-cache/dem"), None)

gj = json.load(open("rail_bridges.geojson"))
pts = []
for f in gj["features"]:
    c = f["geometry"]["coordinates"]
    if not any(abs(y - lat0) < 0.1 and abs(x - lon0) < 0.1 for x, y in c):
        continue
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        d = math.hypot((x2 - x1) * 111320 * math.cos(math.radians(y1)), (y2 - y1) * 110540)
        n = max(1, int(d // 25))
        for k in range(n + 1):
            pts.append((y1 + (y2 - y1) * k / n, x1 + (x2 - x1) * k / n))
BR = np.array(pts)

AZ = np.arange(0, 360, 0.25)
NA = len(AZ)
NS = 400
DIST = 100 * (16000 / 100) ** (np.arange(NS) / (NS - 1))
HS = np.arange(0, NA)
out = []
for dy in np.arange(-RAD, RAD + 1, 100):
    for dx in np.arange(-RAD, RAD + 1, 100):
        clat = lat0 + dy / 110540; clon = lon0 + dx / (111320 * math.cos(math.radians(lat0)))
        ring = terrain._dest_np(clat, clon, np.arange(0, 360, 45.0), np.array([0, 100, 200.0]))
        g = dem.sample(ring[0], ring[1])
        if g.max() - g.min() > 6:
            continue
        g0 = float(g[:, 0].mean())
        la, lo = terrain._dest_np(clat, clon, AZ, DIST)
        hh = dem.sample(la, lo)
        drop = DIST ** 2 / (2 * R) * 0.87
        ang = np.degrees(np.arctan2(hh - drop[None, :] - g0 - 1.6, DIST[None, :]))
        hor = ang.max(axis=1)
        by = (BR[:, 0] - clat) * 110540; bx = (BR[:, 1] - clon) * 111320 * math.cos(math.radians(clat))
        bd = np.hypot(bx, by); baz = np.degrees(np.arctan2(bx, by)) % 360
        best = None
        for fs in (1.0, 1.08, 1.16):
            f = F0 * fs
            r_off = np.degrees(np.arctan((RX - CX) / f)); r_el = np.degrees(np.arctan((HROW - RY) / f))
            fl_off = np.degrees(np.arctan((FLX - CX) / f))
            ri = (HS[:, None] + np.round(r_off / 0.25).astype(int)[None, :]) % NA
            fi = (HS[:, None] + np.round(fl_off / 0.25).astype(int)[None, :]) % NA
            diff = hor[ri] - r_el[None, :]
            cc = np.clip(np.median(diff, axis=1), -0.7, 0.7)
            rms = np.sqrt(np.mean((diff - cc[:, None]) ** 2, axis=1))
            pen = np.mean(np.clip(hor[fi] - cc[:, None] - 1.0, 0, None), axis=1)
            s = rms + 1.5 * pen
            for k in np.argsort(s)[:12]:
                H = k * 0.25
                off = (baz - H + 180) % 360 - 180
                def dmin(a, b):
                    m = (off > a) & (off < b) & (bd > 100)
                    return float(bd[m].min()) if m.any() else 99999
                hf = math.degrees(math.atan(640 / f))
                L = dmin(-hf, -hf + 5); C = dmin(-2, 2); Rr = dmin(hf - 8, hf)
                eL, eC, eR = 430 * fs, 660 * fs, 1150 * fs
                rp = abs(math.log(L / eL)) + abs(math.log(C / eC)) + abs(math.log(Rr / eR))
                tot = float(s[k]) + 0.5 * rp
                if best is None or tot < best["total"]:
                    best = {"cam": [round(clat, 5), round(clon, 5)], "g": round(g0, 1), "H": H, "fs": fs, "cc": round(float(cc[k]), 2),
                            "rms": round(float(rms[k]), 3), "flatpen": round(float(pen[k]), 3), "dL": round(L), "dC": round(C), "dR": round(Rr),
                            "railpen": round(rp, 3), "total": round(tot, 3)}
        if best:
            out.append(best)
out.sort(key=lambda x: x["total"])
json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False)
for x in out[:15]:
    print(x)
