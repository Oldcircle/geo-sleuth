# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""铁路高架桥 × 近旁陡山 共现扫描。

这是第 13 集案例的专用脚本，阈值按那张照片的估计写死（山仰角、平地平线长度、近处起伏），
只作复现记录，不保证在别的照片上能跑。输入 geojson 来自 osm.py geom 的铁路桥查询。

对 rail_bridges.geojson 里每条桥沿线每 STEP 米取点，用 Terrarium DEM(z10) 算：
- 点位地面是否平原（1.2 km 内高程起伏小）
- 方位 0–355° 每 5° 的地平线仰角（1.5–9 km）
- 是否存在"连续 ≥30° 平地平线(<1°)" 紧挨 "仰角 ≥7° 的山体"
输出候选点及特征，按山体仰角与陡峭度排序。
"""
import json, math, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/geo-sleuth/scripts"))
import terrain  # noqa

Z = 10
STEP = 400.0
CACHE = Path(".geo-cache/dem")
CACHE.mkdir(parents=True, exist_ok=True)
R = 6371008.8


def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(d))


gj = json.load(open(sys.argv[1]))
pts = []
for f in gj["features"]:
    g = f["geometry"]
    if g["type"] != "LineString" or f.get("properties", {}).get("electrified") == "no":
        continue
    c = [(y, x) for x, y in g["coordinates"]]
    tags = f.get("properties", {})
    acc = 0.0
    last = None
    for i in range(1, len(c)):
        d = hav(c[i - 1], c[i])
        n = int((acc + d) // STEP)
        for k in range(n):
            t = (STEP * (k + 1) - acc) / d if d else 0
            pts.append((c[i - 1][0] + (c[i][0] - c[i - 1][0]) * t, c[i - 1][1] + (c[i][1] - c[i - 1][1]) * t, tags))
        acc = (acc + d) % STEP
    if not pts or len(c) >= 2 and hav(c[0], c[-1]) < STEP:
        pts.append((c[len(c) // 2][0], c[len(c) // 2][1], tags))
print("samples", len(pts), file=sys.stderr)

# 切片缓存
tiles = {}
def tile_of(lat, lon):
    n = 2 ** Z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y

need = set()
for lat, lon, _ in pts:
    x, y = tile_of(lat, lon)
    r = 9500 / (40075016.7 * math.cos(math.radians(lat)) / 2 ** Z)
    for tx in range(int(x - r), int(x + r) + 1):
        for ty in range(int(y - r), int(y + r) + 1):
            need.add((tx, ty))
print("tiles", len(need), file=sys.stderr)
with ThreadPoolExecutor(24) as ex:
    for (tx, ty), arr in zip(need, ex.map(lambda t: terrain._fetch(Z, t[0], t[1], CACHE, None), need)):
        tiles[(tx, ty)] = arr


TX0 = min(t[0] for t in need); TY0 = min(t[1] for t in need)
TX1 = max(t[0] for t in need); TY1 = max(t[1] for t in need)
MOS = np.zeros(((TY1 - TY0 + 1) * 256, (TX1 - TX0 + 1) * 256), dtype=np.int16)
for (tx, ty), arr in tiles.items():
    MOS[(ty - TY0) * 256:(ty - TY0 + 1) * 256, (tx - TX0) * 256:(tx - TX0 + 1) * 256] = np.clip(arr, -500, 9000).astype(np.int16)
tiles.clear()


def elev(lat, lon):
    n = 256 * 2 ** Z
    x = ((lon + 180) / 360 * n - TX0 * 256).astype(int)
    y = ((1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n - TY0 * 256).astype(int)
    x = np.clip(x, 0, MOS.shape[1] - 1); y = np.clip(y, 0, MOS.shape[0] - 1)
    return MOS[y, x].astype(np.float32)


AZ = np.arange(0, 360, 5.0)
DIST = np.array([1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000, 7000, 8000, 9000], dtype=float)
NEAR = np.array([0, 300, 600, 900, 1200], dtype=float)

res = []
for idx, (lat, lon, tags) in enumerate(pts):
    la, lo = terrain._dest_np(lat, lon, AZ, DIST)
    h = elev(la, lo)
    ln, lon_n = terrain._dest_np(lat, lon, AZ, NEAR)
    hn = elev(ln, lon_n)
    h0 = float(np.median(hn))
    if hn.max() - hn.min() > 40:     # 近处不平
        continue
    ang = np.degrees(np.arctan2(h - h0 - 1.5, DIST[None, :]))
    hor = ang.max(axis=1)
    rel = (h - h0).max(axis=1)
    mt = hor >= 6.0
    low = hor < 1.2
    if not mt.any() or low.sum() < 6:
        continue
    # 找紧挨山体的连续平地平线段
    best = 0
    for i in range(72):
        if not mt[i]:
            continue
        for sgn in (-1, 1):
            j = (i + sgn) % 72
            # 允许 1 格过渡
            k = 0
            run = 0
            while k < 20:
                jj = (i + sgn * (k + 1)) % 72
                if low[jj]:
                    run += 1
                elif run == 0 and k < 2:
                    pass
                else:
                    break
                k += 1
            best = max(best, run)
    if best < 6:
        continue
    i = int(np.argmax(hor))
    res.append({"lat": round(lat, 5), "lon": round(lon, 5), "h0": round(h0), "max_ang": round(float(hor[i]), 1),
                "az": float(AZ[i]), "relief": round(float(rel[i])), "flat_run_deg": best * 5,
                "name": tags.get("name", ""), "hs": tags.get("highspeed", ""), "elec": tags.get("electrified", ""),
                "id": tags.get("id", tags.get("@id", ""))})

print("hits", len(res), file=sys.stderr)
json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=0)
