# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "pillow"]
# ///
"""Solve the camera position from pier column positions.

This is a case-specific script for episode 13 with that photo's parameters hard-coded: the 17 pier pixel columns LEFT/RIGHT, the ridge points ridge,
the candidate center lat0/lon0 and the line name are all example parameters from one real case. Kept only as a reproduction record; not guaranteed to run on another photo.

Pixel column of each pier in the photo → ray bearing → intersect with the OSM bridge line → spacing between adjacent piers along the line should be constant (32 m box girders).
Grid-search camera position, heading, and focal length over the candidate area; score = spacing dispersion + |log(mean/32)|. Independent of the skyline fit."""
import json, math, sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/geo-sleuth/scripts"))
import terrain

LEFT = [39, 133, 219, 296, 369]
RIGHT = [745, 788, 829, 869, 907, 944, 981, 1016, 1050, 1083, 1116, 1148]
PIERS = np.array(LEFT + RIGHT, float)
CX = 640.0
lat0, lon0 = 23.736, 113.121   # example parameters from one real case: candidate center given by the previous refine step
kx = 111320 * math.cos(math.radians(lat0)); ky = 110540

g = json.load(open("qy_rail.geojson"))
line = None
for f in g["features"]:
    if f["properties"].get("name") == "广清城际线":
        line = np.array(f["geometry"]["coordinates"]); break
P = np.c_[(line[:, 0] - lon0) * kx, (line[:, 1] - lat0) * ky]   # local metric coordinates (x east, y north)
seg_a, seg_b = P[:-1], P[1:]
seg_len = np.hypot(*(seg_b - seg_a).T)
chain0 = np.r_[0, np.cumsum(seg_len)][:-1]

def hits(cx, cy, az):
    """Nearest intersection of the ray with the polyline: returns (distance, chainage along the line)."""
    d = np.array([math.sin(math.radians(az)), math.cos(math.radians(az))])
    e = seg_b - seg_a
    den = d[0] * e[:, 1] - d[1] * e[:, 0]
    w = seg_a - np.array([cx, cy])
    with np.errstate(divide="ignore", invalid="ignore"):
        t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den      # ray parameter
        u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / den             # segment parameter
    ok = (t > 100) & (u >= 0) & (u <= 1)
    if not ok.any():
        return None
    i = np.argmin(np.where(ok, t, np.inf))
    return t[i], chain0[i] + u[i] * seg_len[i]

res = []
HS = np.arange(55, 115.1, 0.25)
e = seg_b - seg_a
nL = len(LEFT)
dem = terrain.DEM((lat0, lon0), 18000, 13, Path(".geo-cache/dem"), None)
ridge = {760: 826, 780: 816, 800: 813, 820: 811, 840: 810, 860: 804, 880: 794, 900: 787, 920: 783, 940: 771, 960: 765,
         980: 757, 1000: 755, 1020: 747, 1040: 741, 1060: 740, 1080: 738, 1100: 737, 1120: 738, 1140: 736, 1160: 735,
         1180: 734, 1200: 725, 1220: 728, 1240: 725, 1260: 724}
RX = np.array(list(ridge.keys()), float); RY = np.array(list(ridge.values()), float)
FLX = np.arange(0, 281, 20, dtype=float)
AZ = np.arange(0, 360, 0.1)
NS = 400
DIST = 100 * (16000 / 100) ** (np.arange(NS) / (NS - 1))
for yy in np.arange(-1500, 1501, 50):
    for xx in np.arange(-1500, 1501, 50):
        w = seg_a - np.array([xx, yy])
        clat = lat0 + yy / ky; clon = lon0 + xx / kx
        hor = None
        for f in (1200, 1281, 1350, 1430, 1500):
            offs = np.degrees(np.arctan((PIERS - CX) / f))
            az = np.radians(HS[:, None] + offs[None, :])
            dx, dy = np.sin(az)[..., None], np.cos(az)[..., None]
            den = dx * e[:, 1] - dy * e[:, 0]
            with np.errstate(divide="ignore", invalid="ignore"):
                t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den
                u = (w[:, 0] * dy - w[:, 1] * dx) / den
            ok = (t > 100) & (u >= 0) & (u <= 1)
            tt = np.where(ok, t, np.inf)
            i = np.argmin(tt, axis=2)
            tmin = np.take_along_axis(tt, i[..., None], 2)[..., 0]
            valid = np.all(np.isfinite(tmin), axis=1)
            if not valid.any():
                continue
            uu = np.take_along_axis(u, i[..., None], 2)[..., 0]
            ch = chain0[i] + uu * seg_len[i]
            dl = np.abs(np.diff(ch[:, :nL], axis=1)); dr = np.abs(np.diff(ch[:, nL:], axis=1))
            sp = np.concatenate([dl, dr], axis=1)
            m = sp.mean(axis=1); cv = sp.std(axis=1) / np.maximum(m, 1e-6)
            dch = np.diff(ch, axis=1)
            mono = np.all(dch > 0, axis=1) | np.all(dch < 0, axis=1)
            pscore = cv + np.abs(np.log(np.maximum(m, 1e-3) / 32)) + (~mono) * 1.0
            pscore[~valid] = np.inf
            k = int(np.argmin(pscore))
            if not np.isfinite(pscore[k]) or pscore[k] > 0.08:
                continue
            H = float(HS[k])
            if hor is None:
                g0 = float(dem.sample(np.array([clat]), np.array([clon]))[0])
                la, lo = terrain._dest_np(clat, clon, AZ, DIST)
                hh = dem.sample(la, lo)
                drop = DIST ** 2 / (2 * 6371008.8) * 0.87
                hor = np.degrees(np.arctan2(hh - drop[None, :] - g0 - 1.6, DIST[None, :])).max(axis=1)
            r_off = np.degrees(np.arctan((RX - CX) / f)); r_el = np.degrees(np.arctan((935 - RY) / f))
            fl_off = np.degrees(np.arctan((FLX - CX) / f))
            mr = np.interp((H + r_off) % 360, AZ, hor, period=360)
            mf = np.interp((H + fl_off) % 360, AZ, hor, period=360)
            diff = mr - r_el; cc = float(np.clip(np.median(diff), -0.8, 0.8))
            rms = float(np.sqrt(np.mean((diff - cc) ** 2)))
            fpen = float(np.mean(np.clip(mf - cc - 1.0, 0, None)))
            tot = rms + 1.5 * fpen + 2 * float(pscore[k])
            res.append((tot, rms, float(pscore[k]), float(m[k]), xx, yy, f, H, cc, float(tmin[k, 0]), float(tmin[k, -1])))
res.sort()
out = []
for r in res[:25]:
    lat = lat0 + r[5] / ky; lon = lon0 + r[4] / kx
    print(f"tot {r[0]:.3f} sky_rms {r[1]:.3f} pier {r[2]:.3f} span {r[3]:.1f}  cam {lat:.5f},{lon:.5f} f {r[6]} H {r[7]} cc {r[8]:.2f} dL {r[9]:.0f} dR {r[10]:.0f}")
    out.append({"tot": r[0], "rms": r[1], "pier": r[2], "cam": [round(lat, 5), round(lon, 5)], "f": r[6], "H": r[7], "cc": r[8]})
json.dump(out, open("joint.json", "w"))
