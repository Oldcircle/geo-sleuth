# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy"]
# ///
"""Round 3: filter camera positions by the bridge-line geometry inferred from the pier spacing in the frame.

This is a case-specific script for episode 13; the three bridge-distance windows are hard-coded from estimates for that photo.
Kept only as a reproduction record; not guaranteed to run on another photo.
Inferred from the photo (f≈1281–1435 px, 32 m spans): the bridge line's perpendicular distance from the camera position is about 450–750 m, its nearest point about 30–45° left of frame center,
the distance along the center sight line about 600–800 m, at the right edge about 0.9–1.4 km; the bridge line crosses the frame diagonally from near-left to far-right.
For each stage-2 camera position (with its best heading H), take the bridge sample points within field of view [-27°,27°] and 300–2500 m, and check one by one:
- nearest bridge point on the center sight line (±3°) at 550–900 m
- bridge point at the left edge (-26°±3°) at 350–750 m
- bridge point at the right edge (+22°±4°) at 800–1700 m
"""
import json, math, sys, glob
import numpy as np

gj = json.load(open("rail_bridges.geojson"))
cell = {}
for f in gj["features"]:
    if f["properties"].get("electrified") == "no":
        continue
    c = f["geometry"]["coordinates"]
    for (x1, y1), (x2, y2) in zip(c, c[1:]):
        d = math.hypot((x2 - x1) * 111320 * math.cos(math.radians(y1)), (y2 - y1) * 110540)
        n = max(1, int(d // 50))
        for k in range(n + 1):
            la, lo = y1 + (y2 - y1) * k / n, x1 + (x2 - x1) * k / n
            cell.setdefault((int(la / 0.02), int(lo / 0.02)), []).append((la, lo))

def near(lat, lon):
    i, j = int(lat / 0.02), int(lon / 0.02)
    out = []
    for di in (-2, -1, 0, 1, 2):
        for dj in (-2, -1, 0, 1, 2):
            out += cell.get((i + di, j + dj), [])
    return np.array(out) if out else np.zeros((0, 2))

recs = []
for f in sorted(glob.glob("f2_?.json")):
    recs += json.load(open(f))
out = []
for r in recs:
    if r["rms"] > 0.6 or r["flatpen"] > 0.15:
        continue
    lat, lon = r["cam"]
    br = near(lat, lon)
    if not len(br):
        continue
    by = (br[:, 0] - lat) * 110540
    bx = (br[:, 1] - lon) * 111320 * math.cos(math.radians(lat))
    bd = np.hypot(bx, by)
    baz = np.degrees(np.arctan2(bx, by)) % 360
    best = None
    for dH in np.arange(-6, 6.1, 1.5):
        H = r["H"] + dH
        off = (baz - H + 180) % 360 - 180
        def dmin(lo_, hi_):
            m = (off > lo_) & (off < hi_) & (bd > 150)
            return float(bd[m].min()) if m.any() else None
        c = dmin(-3, 3); L = dmin(-27, -21); Rr = dmin(18, 27)
        if c is None or L is None or Rr is None:
            continue
        pen = 0
        pen += max(0, 550 - c) / 200 + max(0, c - 900) / 200
        pen += max(0, 350 - L) / 200 + max(0, L - 750) / 200
        pen += max(0, 800 - Rr) / 300 + max(0, Rr - 1700) / 300
        if L >= c or c >= Rr:
            pen += 1
        if best is None or pen < best[0]:
            best = (pen, H, c, L, Rr)
    if best is None:
        continue
    out.append({**r, "rail_pen": round(best[0], 2), "H2": best[1], "dC": round(best[2]), "dL": round(best[3]), "dR": round(best[4]),
                "total": round(r["rms"] + r["flatpen"] + 0.3 * best[0], 3)})
out.sort(key=lambda x: x["total"])
sel = []
for x in out:
    if all(abs(x["cam"][0] - y["cam"][0]) > 0.02 or abs(x["cam"][1] - y["cam"][1]) > 0.02 for y in sel):
        sel.append(x)
json.dump(sel, open("f3_sel.json", "w"), ensure_ascii=False)
print(len(out), len(sel))
for i, x in enumerate(sel[:30]):
    print(i, x["name"] or "-", x["cam"], "H", x["H2"], "rms", x["rms"], "railpen", x["rail_pen"], "dL/C/R", x["dL"], x["dC"], x["dR"], "total", x["total"])
