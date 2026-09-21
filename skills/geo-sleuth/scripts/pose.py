#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""反解机位（相机后方交会）：照片里 ≥4 个认得出位置的点 → 机位经纬度、高度、朝向、俯仰、横滚、视角 + 误差半径。

适合窗景、高楼俯拍、隔江远眺这类"能在卫星图上认出好几个点"的照片。比两条视线交会多用了高度和俯仰信息，还能把楼层算出来。
平视（站在地上拍远处的塔、桥、码头）也能用：fix 掉 height，给眼高。

  solve    解算机位；输出里带逐点检查（leave_one_out）：每次去掉一个点重解，看它被其余点预测差多少
  check    离散候选机位打分：几处都说得通、要挑一个时用；每个候选只解朝向，逐个去掉一个点再打分，
           稳健Δchi2 > 9（去掉任何一个点都救不回来）才算和照片对不上
  project  已知机位，把一批经纬度点投到照片上（核对河岸、路、楼是否对得上）；
           带 --horizon <海天线行号> 时校验 pitch：目标的俯角不是相机的俯仰角，海天线在画面中心就说明 pitch≈0

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
  pose.py check spec.json --cands cands.json        # cands.json：{"候选A": [lat, lon], "候选B": [lat, lon, 眼高海拔]}
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


def solve(spec: dict, search_radius: float, restarts: int, seed: int = 7,
          pt_sigma: float = 5.0) -> dict:
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
            out["radius_px_only_m"] = round(3 * math.hypot(se[0], se[1]), 1)   # 只含像素噪声的 3σ，覆盖不住真值，别直接用
        except np.linalg.LinAlgError:
            out["sigma"] = "奇异：点的分布太集中（都在一条线上或一个方向），加不同方向、不同远近的点"
    else:
        out["sigma"] = "自由度为 0，没法估误差；再加点"
    out["_params"] = [float(x) for x in p]
    out["_frame"] = {"lat0": lat0, "lon0": lon0, "image_size": [W, H]}
    mc = mc_radius(p, free, pts, obs, W, H, pt_sigma, rms)
    out["radius_m"] = mc["radius_m"]
    out["radius_note"] = (f"95% 半径，蒙特卡洛 {mc['trials']} 次：控制点坐标按 ±{pt_sigma:g} m 扰动"
                          f"（--pt-sigma），像素按 ±{mc['px_sigma_used']:g} px。"
                          f"中位偏移 {mc['p50_m']:g} m。只算像素噪声的旧口径见 radius_px_only_m，它盖不住真值。")
    out["pt_sigma_m"] = pt_sigma
    out["leave_one_out"] = leave_one_out(p, free, pts, obs, W, H, spec["points"])
    return out


def mc_radius(p, free, pts, obs, W, H, pt_sigma: float, rms_px: float,
              trials: int = 60, seed: int = 11, px_sigma: float | None = None) -> dict:
    """控制点坐标误差传不进重投影残差：把所有点同向挪一点，相机跟着挪，残差一点不变。
    所以 inv(JtJ) 那套协方差对这个方向是瞎的——实测坐标噪声 5 m 时，3σ 半径覆盖真值只剩 67%（该是 97%）。
    这里按 pt_sigma 扰动控制点、按 rms 扰动像素，从已收敛解重解，取位置偏移的 95 分位当半径。
    像素那一路不扣掉坐标误差的贡献：略微重复计一点，正好补上"从已收敛解重解够不着大偏移"的低估。
    标定实测：像素那一路扣减的版本覆盖 91%，不扣减 95%；换三种没标定过的几何验证，286/300 = 95%。"""
    rng = np.random.default_rng(seed)
    if px_sigma is None:
        px_sigma = max(rms_px, 1.0)
    offs = []
    for _ in range(trials):
        pts_j = pts.copy()
        if pt_sigma > 0:
            pts_j[:, :2] += rng.normal(0, pt_sigma, (len(pts_j), 2))
        q, _, _ = lm(p.copy(), free, pts_j, obs + rng.normal(0, px_sigma, obs.shape), W, H, iters=60)
        offs.append(math.hypot(q[0] - p[0], q[1] - p[1]))
    return {"radius_m": round(float(np.percentile(offs, 95)), 1),
            "p50_m": round(float(np.percentile(offs, 50)), 1),
            "q": {k: round(float(np.percentile(offs, k)), 1) for k in (50, 90, 95, 99)},
            "px_sigma_used": round(px_sigma, 1), "trials": trials}

def leave_one_out(p, free, pts, obs, W, H, spec_pts) -> dict:
    """逐个去掉一个点重解：这个点被别的点"预测"到哪、差多少像素，机位挪了多远。
    认错的点（地物认错、坐标取错、高度基准不一致）去掉后其余点拟合得很好，它自己却差得远。"""
    if 2 * (len(obs) - 1) < len(free) + 1:
        return {"note": f"点数 {len(obs)} 去掉一个后方程不多于未知数，做不了逐点检查；再加一个点，或 fix 掉 height/roll"}
    rows, errs = {}, []
    for i in range(len(obs)):
        keep = [j for j in range(len(obs)) if j != i]
        q, cost, _ = lm(p, free, pts[keep], obs[keep], W, H)
        uv, _ = project(q, pts[i:i + 1], W, H)
        e = float(np.hypot(*(uv[0] - obs[i]))) if not np.isnan(uv[0]).any() else float("inf")
        rest = math.sqrt(cost / len(keep))
        rows[spec_pts[i].get("name", str(i))] = {"pred_err_px": round(e, 1), "rest_rms_px": round(rest, 1),
                                                  "shift_m": round(math.hypot(q[0] - p[0], q[1] - p[1]), 1)}
        errs.append((e, rest, i))
    # 只标一个：去掉它后其余点 rms 最低、且明显低于其他去法（中位数的 0.4 倍），它自己的预测误差又是其余 rms 的 3 倍以上。
    # 合成题实测（注入一个挪 40–80 m 的点）：俯拍 7 点误报 0–2/20、检出 12–13/20；平视 6 点误报 2–5/20、检出 6–17/20（不稳）。
    dof_after = 2 * (len(obs) - 1) - len(free)
    e, rest, i = min(errs, key=lambda t: t[1])
    med = float(np.median([t[1] for t in errs]))
    flag = [spec_pts[i].get("name", str(i))] if (dof_after >= 2 and e > 3 * max(rest, 2.0) and rest < 0.4 * med) else []
    return {"points": rows, "suspect": flag,
            "most_improved": {"name": spec_pts[i].get("name", str(i)), "rest_rms_px": round(rest, 1), "median_rest_rms_px": round(med, 1)},
            "rule": "只标一个：去掉它后其余点 rms 最低（< 其他去法中位数的 0.4 倍）且它的预测误差 > 3×其余 rms；"
                    "平视、点少时不可靠，没标出来不代表没有认错的点；most_improved 不管过没过门槛都列出来，先核它"}


def _fit_at(e, n, h, pts, obs, W, H, free, f0, pitch0, p_start=None):
    """机位固定在 (e, n, h)，只解朝向/俯仰/横滚（和没固定的焦距）。给 p_start 时从它起算，不再多点试。"""
    starts = [p_start] if p_start is not None else [np.array([e, n, h, hd, pt, 0.0, f0])
                                                    for hd in range(0, 360, 30) for pt in (pitch0 - 10, pitch0, pitch0 + 10)]
    best = None
    for p0 in starts:
        p, cost, _ = lm(np.array(p0, dtype=float), free, pts, obs, W, H)
        if abs(p[4]) > 89 or abs(p[5]) > 60:          # 翻过头的解（镜头朝后、倒置）不算
            continue
        if best is None or cost < best[1]:
            best = (p, cost)
    return best if best else (np.array(starts[0], dtype=float), float("inf"))


def check(spec: dict, cands: dict, px_sigma: float) -> dict:
    """离散候选机位打分：每个候选只放开朝向、俯仰、横滚（和没固定的焦距），比重投影误差。
    适合"几何上两三处都说得通、要挑一个"的场合，比如地图上标的观景台 vs 卫星图上另一段岸边、同一条对齐线上的几栋楼。
    一个认错的点就能把排名翻过来（合成题：俯拍题真值第一从 15/15 掉到 1/15），所以还要逐个去掉一个点再打分：
    robust_delta_chi2 取所有去法里最小的那个，只有它也大的候选才算对不上。"""
    W, H = spec["image_size"]
    init = spec.get("init", {})
    lat0, lon0 = init["at"]
    kx, ky = _frame(lat0)
    pts = np.array([[(q["ll"][1] - lon0) * kx, (q["ll"][0] - lat0) * ky, q.get("h", 0.0)] for q in spec["points"]])
    obs = np.array([q["px"] for q in spec["points"]], dtype=float)
    names = [q.get("name", str(i)) for i, q in enumerate(spec["points"])]
    fixed = set(spec.get("fix", []))
    f0 = (W / 2) / math.tan(math.radians(init.get("hfov", 65) / 2))
    free = [3, 4, 5] + ([] if "hfov" in fixed else [6])
    subsets = [("全部点", list(range(len(obs))))]
    if 2 * (len(obs) - 1) >= len(free) + 1:
        subsets += [(f"去掉{names[i]}", [j for j in range(len(obs)) if j != i]) for i in range(len(obs))]
    res, costs = {}, {}
    for name, c in cands.items():
        ll, h = (c[:2], c[2]) if len(c) > 2 else (c, init.get("height", 30.0))
        e, n = (ll[1] - lon0) * kx, (ll[0] - lat0) * ky
        p, cost = _fit_at(e, n, h, pts, obs, W, H, free, f0, init.get("pitch", 0.0))
        costs[name] = {"全部点": cost}
        for sname, keep in subsets[1:]:
            costs[name][sname] = _fit_at(e, n, h, pts[keep], obs[keep], W, H, free, f0, 0, p_start=p)[1]
        uv, _ = project(p, pts, W, H)
        res[name] = {"rms_px": round(math.sqrt(cost / len(obs)), 1),
                     "heading": round(p[3] % 360, 1), "pitch": round(p[4], 1), "roll": round(p[5], 1),
                     "hfov": round(2 * math.degrees(math.atan((W / 2) / p[6])), 1),
                     "residuals_px": {nm: [round(float(a), 1), round(float(b), 1)] for nm, (a, b) in zip(names, uv - obs)}}
    for sname, keep in subsets:
        best = min(costs[c][sname] for c in cands)
        sig2 = max(px_sigma ** 2, best / len(keep))           # 最好的候选都拟合不到 px_sigma 时，按它的 rms 放宽
        for c in cands:
            costs[c][sname] = (costs[c][sname] - best) / sig2
    for c in cands:
        d = costs[c]
        res[c]["delta_chi2"] = round(d["全部点"], 1)
        worst_drop = min(d, key=d.get)
        res[c]["robust_delta_chi2"] = round(d[worst_drop], 1)
        res[c]["robust_by"] = worst_drop
    return dict(sorted(res.items(), key=lambda kv: (kv[1]["robust_delta_chi2"], kv[1]["delta_chi2"])))


def sanity(pose: dict, pts: list[dict], horizon_row: float | None = None) -> list[str]:
    """报机位前的自洽自检。犯过的错：把画面里某个目标的俯角当成相机的俯仰角填进 pitch，
    以及机位高程和画面俯角对不上却照报（4 m 高差配 7.6° 俯角，差了四倍）。"""
    H = pose["_frame"]["image_size"][1]
    e0, n0, h_cam, _yaw, pitch, _roll, f = pose["_params"]
    lat0, lon0 = pose["_frame"]["lat0"], pose["_frame"]["lon0"]
    kx, ky = _frame(lat0)
    out = [(f"自检 pitch={pitch:.1f}°：真地平线（海天线 / 远处平地平线）应落在画面第 "
            f"{H / 2 - f * math.tan(math.radians(pitch)):.0f} 行（共 {H} 行，画面中心 {H // 2}）。"
            f"照片里的海天线不在这一行附近，就是 pitch 填错了——目标的俯角 ≠ 相机的俯仰角。")]
    if horizon_row is not None:
        pitch_h = math.degrees(math.atan2(H / 2 - float(horizon_row), f))
        d = abs(pitch_h - pitch)
        out.append(f"  照片海平线在第 {float(horizon_row):.0f} 行 → pitch 应为 {pitch_h:.1f}°（当前 {pitch:.1f}°，差 {d:.1f}°）")
        if d > 2.0:
            out.append(f"  !! pitch 与海平线矛盾 {d:.1f}° > 2°：先用海平线标定 pitch，再投影/反解")
    out.append(f"自检 相机高度 {h_cam:.1f}（与各点 h 同基准）；下表的「应落在第几行」要和照片里该地物的实际行数对得上：")
    for q in pts:
        e = (q["ll"][1] - lon0) * kx - e0
        n = (q["ll"][0] - lat0) * ky - n0
        dist = math.hypot(e, n)
        if dist < 1.0:
            continue
        dh = h_cam - q.get("h", 0.0)
        dep = math.degrees(math.atan2(dh, dist))
        row = H / 2 + f * math.tan(math.radians(dep + pitch))
        note = ""
        if "px" in q and len(q["px"]) > 1:
            note = f"  实际第 {q['px'][1]:.0f} 行，差 {abs(row - q['px'][1]):.0f} px"
        out.append(f"  {q.get('name', '?'):<14} 水平 {dist:6.0f} m  高差 {dh:6.1f} m  几何俯角 {dep:5.1f}°  应落在第 {row:6.0f} 行{note}")
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
    s.add_argument("--pt-sigma", type=float, default=5.0,
                   help="控制点自身的坐标误差 m（卫星图上点一个楼角典型 5–15 m）。误差半径靠它做蒙特卡洛；设 0 退回只算像素噪声")
    ck = sub.add_parser("check", help="离散候选机位打分：每个候选只解朝向，比重投影误差")
    ck.add_argument("spec", type=Path)
    ck.add_argument("--cands", type=Path, required=True, help='{"候选名": [lat, lon] 或 [lat, lon, 高度]}；不给高度用 init.height')
    ck.add_argument("--px-sigma", type=float, default=5.0, help="像素量测误差，换算 chi2 用")
    ck.add_argument("--save", type=Path, default=Path("pose_check.json"))
    pr = sub.add_parser("project")
    pr.add_argument("--pose", type=Path, required=True)
    pr.add_argument("--points", type=Path, required=True, help='[{"name":…,"ll":[lat,lon],"h":…}] 或 {name:[lat,lon,h]}')
    pr.add_argument("--photo", type=Path, required=True)
    pr.add_argument("--out", type=Path, required=True)
    pr.add_argument("--horizon", type=float, help="照片里海天线/远处平地平线所在的行号（原图像素）：用来标定并校验 pitch")
    args = ap.parse_args(_neg_coords(sys.argv[1:]))

    if args.cmd == "solve":
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        pose = solve(spec, args.search_radius, args.restarts, pt_sigma=args.pt_sigma)
        args.save.write_text(json.dumps(pose, ensure_ascii=False, indent=1), encoding="utf-8")
        show = {k: v for k, v in pose.items() if not k.startswith("_")}
        print(json.dumps(show, ensure_ascii=False, indent=1))
        if pose["rms_px"] > 15:
            print("注意：重投影误差偏大，可能有点对错了、高度基准不一致，或初值离得太远（加大 --search-radius / --restarts）")
        loo = pose["leave_one_out"]
        if loo.get("suspect"):
            print(f"注意：逐点检查标出疑似认错的点 {loo['suspect']}：先回头核它的地物和坐标，核完再决定留不留")
        elif loo.get("most_improved"):
            m = loo["most_improved"]
            print(f"逐点检查：去掉「{m['name']}」后其余点 rms {m['rest_rms_px']} px（其他去法中位 {m['median_rest_rms_px']} px）；没过疑似门槛，差得多时仍先核它")
        for line in sanity(pose, spec["points"]):
            print(line)
        if args.photo and args.out:
            draw(args.photo, pose, spec["points"], args.out, observed=True)
            print(f"叠图 -> {args.out}")
    elif args.cmd == "check":
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        cands = json.loads(args.cands.read_text(encoding="utf-8"))
        out = check(spec, cands, args.px_sigma)
        args.save.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        for name, v in out.items():
            print(f"{name:24s} rms {v['rms_px']:6.1f} px  Δchi2 {v['delta_chi2']:8.1f}  稳健Δchi2 {v['robust_delta_chi2']:8.1f}（{v['robust_by']}）"
                  f"  朝向 {v['heading']:6.1f}  俯仰 {v['pitch']:5.1f}")
        print(f"-> {args.save}（稳健Δchi2 > 9 才算对不上：去掉任何一个点都救不回来；两个候选只差在某一个点上时，先核那个点）")
    else:
        pose = json.loads(args.pose.read_text(encoding="utf-8"))
        raw = json.loads(args.points.read_text(encoding="utf-8"))
        pts = raw if isinstance(raw, list) else [{"name": k, "ll": v[:2], "h": (v[2] if len(v) > 2 else 0.0)} for k, v in raw.items()]
        draw(args.photo, pose, pts, args.out, observed=False)
        for line in sanity(pose, pts, args.horizon):
            print(line)
        print(args.out)


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
