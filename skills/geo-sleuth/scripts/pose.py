#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""反解机位（相机后方交会）：照片里 ≥4 个认得出位置的点 → 机位经纬度、高度、朝向、俯仰、横滚、视角 + 误差半径。

适合窗景、高楼俯拍、隔江远眺这类"能在卫星图上认出好几个点"的照片。比两条视线交会多用了高度和俯仰信息，还能把楼层算出来。

  solve    解算机位
  project  已知机位，把一批经纬度点投到照片上（核对河岸、路、楼是否对得上）

spec.json 格式：
{
  "image_size": [1476, 827],
  "points": [
    {"name": "桥头", "px": [212, 431], "ll": [lat, lon], "h": 470},
    {"name": "塔尖", "px": [1180, 120], "ll": [lat, lon], "h": 620}
  ],
  "init": {"at": [lat, lon], "height": 560, "heading": 190, "pitch": -8, "hfov": 65},
  "fix": ["hfov"]
}
- px：点在照片里的像素坐标（原图，左上为 0,0）。
- h：点的高度，**和机位高度用同一个基准**。一律用海拔最稳：地面点用 `terrain.py elev`，楼顶 = 地面海拔 + 楼高。
- init：大致机位和朝向；不知道就给候选区中心，--restarts 会在 --search-radius 范围里多点起算。
- fix：可以固定的参数（hfov、roll、height），知道焦距就固定 hfov，点少时更稳。

示例：
  pose.py solve spec.json --photo photo.jpg --out pose.png --search-radius 500
  pose.py project --pose pose.json --points river.json --photo photo.jpg --out check.png
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

NAMES = ["east_m", "north_m", "height", "heading", "pitch", "roll", "focal_px"]


def _frame(lat0: float):
    return 111320.0 * math.cos(math.radians(lat0)), 110540.0


def project(params: np.ndarray, pts_enu: np.ndarray, W: int, H: int) -> tuple[np.ndarray, np.ndarray]:
    e, n, u, yaw, pitch, roll, f = params
    ps, ts, rs = map(math.radians, (yaw, pitch, roll))
    fwd = np.array([math.sin(ps) * math.cos(ts), math.cos(ps) * math.cos(ts), math.sin(ts)])
    r0 = np.array([math.cos(ps), -math.sin(ps), 0.0])
    u0 = np.cross(r0, fwd)
    right = r0 * math.cos(rs) + u0 * math.sin(rs)
    up = -r0 * math.sin(rs) + u0 * math.cos(rs)
    v = pts_enu - np.array([e, n, u])
    z = v @ fwd
    x, y = v @ right, v @ up
    zz = np.where(z > 1e-3, z, np.nan)
    return np.stack([W / 2 + f * x / zz, H / 2 - f * y / zz], axis=1), z


def residuals(p, pts, obs, W, H):
    uv, z = project(p, pts, W, H)
    r = (uv - obs).ravel()
    return np.where(np.isnan(r), 5000.0, r)


def lm(p0, free, pts, obs, W, H, iters=200):
    p = p0.astype(float).copy()
    steps = np.array([0.5, 0.5, 0.5, 0.01, 0.01, 0.01, 1.0])
    lam = 1e-2
    r = residuals(p, pts, obs, W, H)
    cost = float(r @ r)
    J = None
    for _ in range(iters):
        J = np.zeros((r.size, len(free)))
        for j, k in enumerate(free):
            dp = p.copy()
            dp[k] += steps[k]
            J[:, j] = (residuals(dp, pts, obs, W, H) - r) / steps[k]
        A = J.T @ J
        g = J.T @ r
        improved = False
        for _ in range(10):
            try:
                delta = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            except np.linalg.LinAlgError:
                lam *= 10
                continue
            cand = p.copy()
            cand[free] += delta
            rc = residuals(cand, pts, obs, W, H)
            cc = float(rc @ rc)
            if cc < cost:
                p, r, cost, lam, improved = cand, rc, cc, max(lam / 3, 1e-7), True
                break
            lam *= 4
        if not improved or float(np.abs(delta).max()) < 1e-4:
            break
    return p, cost, J


def solve(spec: dict, search_radius: float, restarts: int, seed: int = 7) -> dict:
    W, H = spec["image_size"]
    init = spec.get("init", {})
    lat0, lon0 = init["at"]
    kx, ky = _frame(lat0)
    pts = np.array([[(q["ll"][1] - lon0) * kx, (q["ll"][0] - lat0) * ky, q.get("h", 0.0)] for q in spec["points"]])
    obs = np.array([q["px"] for q in spec["points"]], dtype=float)
    hfov = init.get("hfov", 65)
    f0 = (W / 2) / math.tan(math.radians(hfov / 2))
    fixed = set(spec.get("fix", []))
    free = [i for i, name in enumerate(NAMES)
            if not ((name == "focal_px" and "hfov" in fixed) or (name == "roll" and "roll" in fixed)
                    or (name == "height" and "height" in fixed))]
    n_obs, k = obs.size, len(free)
    if n_obs < k:
        raise SystemExit(f"点太少：{len(obs)} 个点只有 {n_obs} 个方程，未知数 {k} 个。至少给 {math.ceil(k / 2)} 个点，或用 fix 固定 hfov/roll")
    base = np.array([0.0, 0.0, init.get("height", 30.0), init.get("heading", 0.0), init.get("pitch", 0.0), 0.0, f0])
    rng = np.random.default_rng(seed)
    best = None
    for t in range(max(1, restarts)):
        p0 = base.copy()
        if t:
            ang = rng.uniform(0, 2 * math.pi)
            rad = search_radius * math.sqrt(rng.uniform())
            p0[0], p0[1] = rad * math.sin(ang), rad * math.cos(ang)
            if "height" not in fixed:
                p0[2] = max(1.0, base[2] * rng.uniform(0.5, 1.5))
            p0[3] = (base[3] + rng.uniform(-90, 90)) % 360 if "heading" in init else rng.uniform(0, 360)
            p0[4] = base[4] + rng.uniform(-15, 15)
        p, cost, J = lm(p0, free, pts, obs, W, H)
        if best is None or cost < best[1]:
            best = (p, cost, J)
    p, cost, J = best
    dof = n_obs - k
    rms = math.sqrt(cost / len(obs))
    out = {"camera_ll": [round(lat0 + p[1] / ky, 7), round(lon0 + p[0] / kx, 7)], "height": round(p[2], 1),
           "heading": round(p[3] % 360, 2), "pitch": round(p[4], 2), "roll": round(p[5], 2),
           "hfov": round(2 * math.degrees(math.atan((W / 2) / p[6])), 2), "rms_px": round(rms, 2),
           "points": len(obs), "unknowns": k, "dof": dof}
    uv, _ = project(p, pts, W, H)
    out["residuals_px"] = {q.get("name", str(i)): [round(float(a), 1), round(float(b), 1)]
                           for i, (q, (a, b)) in enumerate(zip(spec["points"], uv - obs))}
    if dof > 0 and J is not None:
        sigma2 = cost / dof
        try:
            cov = sigma2 * np.linalg.inv(J.T @ J)
            idx = {v: i for i, v in enumerate(free)}
            se = [math.sqrt(max(cov[idx[i], idx[i]], 0)) if i in idx else 0.0 for i in range(len(NAMES))]
            out["sigma"] = {"east_m": round(se[0], 1), "north_m": round(se[1], 1), "height_m": round(se[2], 1),
                            "heading_deg": round(se[3], 2)}
            out["radius_m"] = round(3 * math.hypot(se[0], se[1]), 1)       # 取 3σ，宁可报大
        except np.linalg.LinAlgError:
            out["sigma"] = "奇异：点的分布太集中（都在一条线上或一个方向），加不同方向、不同远近的点"
    else:
        out["sigma"] = "自由度为 0，没法估误差；再加点"
    out["_params"] = [float(x) for x in p]
    out["_frame"] = {"lat0": lat0, "lon0": lon0, "image_size": [W, H]}
    return out


def draw(photo: Path, pose: dict, pts: list[dict], out: Path, observed: bool) -> None:
    im = Image.open(photo).convert("RGB")
    W, H = pose["_frame"]["image_size"]
    sx, sy = im.width / W, im.height / H
    lat0, lon0 = pose["_frame"]["lat0"], pose["_frame"]["lon0"]
    kx, ky = _frame(lat0)
    enu = np.array([[(q["ll"][1] - lon0) * kx, (q["ll"][0] - lat0) * ky, q.get("h", 0.0)] for q in pts])
    uv, z = project(np.array(pose["_params"]), enu, W, H)
    d = ImageDraw.Draw(im)
    for q, (u, v), zz in zip(pts, uv, z):
        if observed and "px" in q:
            ox, oy = q["px"][0] * sx, q["px"][1] * sy
            d.line([ox - 9, oy, ox + 9, oy], fill="lime", width=3)
            d.line([ox, oy - 9, ox, oy + 9], fill="lime", width=3)
        if zz > 0 and not math.isnan(u):
            cx, cy = u * sx, v * sy
            d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline="red", width=3)
            d.text((cx + 9, cy - 8), q.get("name", ""), fill="yellow")
    im.save(out, quality=90)



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("solve")
    s.add_argument("spec", type=Path)
    s.add_argument("--search-radius", type=float, default=300, help="初值位置不确定的半径 m")
    s.add_argument("--restarts", type=int, default=40)
    s.add_argument("--photo", type=Path, help="画出观测点（绿十字）和反投影点（红圈）")
    s.add_argument("--out", type=Path, help="叠图输出")
    s.add_argument("--save", type=Path, default=Path("pose.json"))
    pr = sub.add_parser("project")
    pr.add_argument("--pose", type=Path, required=True)
    pr.add_argument("--points", type=Path, required=True, help='[{"name":…,"ll":[lat,lon],"h":…}] 或 {name:[lat,lon,h]}')
    pr.add_argument("--photo", type=Path, required=True)
    pr.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(_neg_coords(sys.argv[1:]))

    if args.cmd == "solve":
        spec = json.loads(args.spec.read_text())
        pose = solve(spec, args.search_radius, args.restarts)
        args.save.write_text(json.dumps(pose, ensure_ascii=False, indent=1))
        show = {k: v for k, v in pose.items() if not k.startswith("_")}
        print(json.dumps(show, ensure_ascii=False, indent=1))
        if pose["rms_px"] > 15:
            print("注意：重投影误差偏大，可能有点对错了、高度基准不一致，或初值离得太远（加大 --search-radius / --restarts）")
        if args.photo and args.out:
            draw(args.photo, pose, spec["points"], args.out, observed=True)
            print(f"叠图 -> {args.out}")
    else:
        pose = json.loads(args.pose.read_text())
        raw = json.loads(args.points.read_text())
        pts = raw if isinstance(raw, list) else [{"name": k, "ll": v[:2], "h": (v[2] if len(v) > 2 else 0.0)} for k, v in raw.items()]
        draw(args.photo, pose, pts, args.out, observed=False)
        print(args.out)


if __name__ == "__main__":
    main()
