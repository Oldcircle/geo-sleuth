#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""候选盘：定位过程中所有候选、线索、证据、排除都记在这里，排名和下一步由脚本算，不靠记忆。

规则写成代码，不靠自觉：
- 没有"删除候选"的操作。排除只有一个入口 `exclude`，必须给算过的文件（geo.py frame、terrain.py 之类的产出），
  线索本身必须是读出来的字或算出来的结果；推测只能降权（似然比被夹在 1/3–3 之间）。
- 排除范围必须 ≤ 证据范围：区县/片区/路这类有延展的候选，exclude 要用 --covers 写明证据覆盖到哪一段，
  覆盖不足一半会被拒；在一个点上看过就整条排除（以点代面）是复发过两次的错。
- 离散候选不取中点：report 的主答案永远是第一名，其余进备选。
- 人口、名气不是证据：先验默认均匀（可选按面积），没有按人口的选项。
- 扫描顺序按"份额 ÷ 页数"排：小城区先扫，大城区放最后并设页数上限。
- 区分检验分不出高低时，next 给出确定的下一步，而不是停在原地。

  init       新建 board.json
  add        加候选（国家/省/市/区县/片区/点）；--from 批量导入 poi.py / gazetteer.py / osm.py geom 的输出
  children   用 gazetteer.py 把某个行政区的下级全部加为候选（"类别推断先列全"）
  clue       登记一条线索：看到的 / 读出的字 / 推测 / 算出来的
  evidence   一条线索对若干候选的似然比（>1 支持，<1 反对）
  exclude    排除一个候选（要算过的文件）
  scan-bbox  给候选设扫描范围（建成区），页数按它算
  urban      用 gazetteer.py urban 自动填 scan-bbox
  falsify    扫描/确认前先写证伪条件
  rank       当前排名（分数、份额、证据、页数、份额/页）
  next       下一步建议
  check      出结论前的检查清单
  report     生成 result.json 的候选/备选/排除/未用线索字段
  apply      查表线索（车牌、区号、国家码、行驶方向、海外领地）自动加候选和证据（用 clues.py）
  log        打印账本

示例：
  board.py init --photo photo.jpg
  board.py children <直辖市或省名>                       # 38 个区县全部进候选，先验均匀
  board.py add --from pois.json --level area --parent <城市>   # 同名多校区、OSM 围墙这类细层候选全部进盘，不手挑
  board.py clue "公交上黄下绿，车尾绿色下弯" --kind livery --status observed --file bus_zoom.png
  board.py evidence --clue K1 --for <区县A>:5 --for <区县B>:2 --why "两区公交图逐张比车尾" --file livery_sheet.jpg
  board.py apply --kind plate --value <车牌前两位>
  board.py urban <区县A> --within <直辖市或省名>
  board.py rank
  board.py next
  board.py falsify <区县A> --text "操场长轴不是南北向就放弃"
  board.py exclude <区县B> --clue K4 --computed frame.json --why "按视角区间算 X 应在框内且 ≥40px，画面里没有"
  board.py check
  board.py report --merge result.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
# uv run 会把自己的路径写进环境变量 UV：照它调子脚本，uv 不在 PATH 里（比如刚装完没重开终端）也找得到
UV = os.environ.get("UV") or "uv"
LEVELS = ["country", "admin1", "admin2", "city", "district", "area", "road", "point"]
LEVEL_ZH = {"country": "国家", "admin1": "省/州", "admin2": "地级/郡", "city": "城市", "district": "区县",
            "area": "片区", "road": "路", "point": "点"}
# 有延展的候选：排除范围必须 <= 证据范围。在一条路/一个片区的某一个点上看过就整条排除，是复发过两次的错
EXTENDED_LEVELS = {"district", "area", "road"}
COVERS_MIN = 0.5  # --covers 至少要覆盖候选范围的这个比例，才允许整体排除
STATUS = ["observed", "read", "inferred", "computed"]
# 似然比上限：推测只能排序，读出的字和算出来的结果才能大幅改分
LR_CAP = {"inferred": 3.0, "observed": 5.0, "read": 50.0, "computed": 50.0}
CHEAP_OPS = [
    ("plate/area-code/calling-code", "读得出车牌、区号、国家码 → `clues.py lookup` + `board.py apply`"),
    ("terrain", "画面平坦 vs 山城 → `terrain.py view` 或 z13 卫星图逐候选看地形，一次调用排一批"),
    ("livery", "公交/出租车涂装 → `revimg.py --query \"<城市> <颜色> 公交\"` 从结果读线路牌，按区县比车尾腰线"),
    ("municipal", "护栏、路灯、站台、路缘样式 → `baidu_pano.py sample --bbox <候选建成区> --n 24` 逐候选一张拼图"),
    ("network", "水系/路网模板 → `tiles.py fetch --zoom 13` 逐候选比河的走向、桥的数量"),
    ("phenology", "植被 + 月份 → 只当弱证据，不能单独排除"),
]


def _norm(s: str) -> str:
    return re.sub(r"[\s（）()]", "", s or "").rstrip("市省区县自治州自治县自治区特别行政区")


def _load(p: Path) -> dict:
    if not p.exists():
        sys.exit(f"没有 {p}：先 `board.py init --photo photo.jpg`")
    return json.loads(p.read_text(encoding="utf-8"))


def _save(p: Path, b: dict) -> None:
    b["updated"] = datetime.now().isoformat(timespec="seconds")
    p.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")


def _find(b: dict, name: str) -> str:
    if name in b["candidates"]:
        return name
    hits = [k for k in b["candidates"] if _norm(k) == _norm(name)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit(f"候选里没有“{name}”：先 add 或 children（现有：{', '.join(list(b['candidates'])[:12])}…）")
    sys.exit(f"“{name}”对应多个候选：{hits}，写全名")


def _log(b: dict, text: str) -> None:
    b.setdefault("log", []).append(f"{datetime.now():%H:%M} {text}")


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    """跑 gazetteer.py、clues.py。子脚本和这边都用 UTF-8：中文 Windows 默认按 GBK 读写，两边不一致就乱码或崩。"""
    return subprocess.run(cmd, text=True, encoding="utf-8", errors="replace", capture_output=True,
                          env={**os.environ, "PYTHONUTF8": "1"})


def _bbox_km2(bb: list[float]) -> float:
    s, w, n, e = bb
    return abs(n - s) * 110.574 * abs(e - w) * 111.320 * math.cos(math.radians((s + n) / 2))


def _pages(bb: list[float], zoom: int, cell: int, cols: int) -> int:
    s, w, n, e = bb
    mpp = 156543.03392 * math.cos(math.radians((s + n) / 2)) / 2 ** zoom
    step = cell * mpp * 0.9
    r = max(1, math.ceil((n - s) * 110574 / step))
    c = max(1, math.ceil((e - w) * 111320 * math.cos(math.radians((s + n) / 2)) / step))
    return math.ceil(r * c / (cols * cols))


def _scores(b: dict, level: str, prior_by: str) -> list[dict]:
    rows = []
    for name, c in b["candidates"].items():
        if c["level"] != level:
            continue
        prior = 1.0
        if prior_by == "area" and c.get("bbox"):
            prior = max(_bbox_km2(c["bbox"]), 1.0)
        logit = math.log(prior) + math.log(max(c.get("prior", 1.0), 1e-9))
        ev = [e for e in b["evidence"] if e["candidate"] == name]
        for e in ev:
            logit += math.log(max(e["lr"], 1e-9))
        rows.append({"name": name, "logit": logit, "n_ev": len(ev),
                     "n_verified": sum(1 for e in ev if b["clues"][e["clue"]]["status"] in ("read", "computed")),
                     "excluded": c.get("status") == "excluded", "c": c})
    open_rows = [r for r in rows if not r["excluded"]]
    if open_rows:
        m = max(r["logit"] for r in open_rows)
        z = sum(math.exp(r["logit"] - m) for r in open_rows)
        for r in open_rows:
            r["share"] = math.exp(r["logit"] - m) / z
    for r in rows:
        r.setdefault("share", 0.0)
    rows.sort(key=lambda r: (r["excluded"], -r["share"]))
    return rows


def _frontier(b: dict) -> str | None:
    """最细的、还有 ≥2 个未排除候选的级别；没有就是最细的有候选的级别。"""
    for lv in reversed(LEVELS):
        if sum(1 for c in b["candidates"].values() if c["level"] == lv and c.get("status") != "excluded") >= 2:
            return lv
    for lv in reversed(LEVELS):
        if any(c["level"] == lv and c.get("status") != "excluded" for c in b["candidates"].values()):
            return lv
    return None


def _cost_of(c: dict, args) -> tuple[int | None, str]:
    bb = c.get("scan_bbox") or c.get("bbox")
    if not bb:
        return None, "无范围"
    pages = _pages(bb, args.zoom, args.cell, args.cols)
    return pages, ("建成区" if c.get("scan_bbox") else "整区bbox")


# ---------------------------------------------------------------- 子命令

def cmd_init(args, p: Path) -> None:
    if p.exists() and not args.force:
        sys.exit(f"{p} 已存在（加 --force 覆盖）")
    b = {"case": args.case or Path.cwd().name, "photo": args.photo, "created": datetime.now().isoformat(timespec="seconds"),
         "candidates": {}, "clues": {}, "evidence": [], "falsify": {}, "log": []}
    _save(p, b)
    print(f"新建 {p}")


def _bbox_around(lat: float, lon: float, r: float) -> list[float]:
    dy, dx = r / 110574, r / (111320 * math.cos(math.radians(lat)))
    return [round(lat - dy, 6), round(lon - dx, 6), round(lat + dy, 6), round(lon + dx, 6)]


def _coords(g) -> list[tuple[float, float]]:
    """GeoJSON 几何里的全部 (lon, lat)。"""
    if isinstance(g, (list, tuple)) and g and isinstance(g[0], (int, float)):
        return [(float(g[0]), float(g[1]))]
    out = []
    for x in g or []:
        out += _coords(x)
    return out


def _read_from(path: Path, radius: float) -> list[tuple[str, dict]]:
    """--from 文件 → [(名字, {bbox, center})]。认四种：
    poi.py/tiles.py 的 {名字: [lat, lon]}；gazetteer.py 的 {名字: {bbox, center}}；
    GeoJSON（osm.py geom，按 properties.name 取名）；[{name, lat, lon} 或 {name, bbox}]。点按 --radius 给范围。"""
    d = json.loads(path.read_text(encoding="utf-8"))
    rows: list[tuple[str, dict]] = []

    def one(name: str, v) -> None:
        if isinstance(v, (list, tuple)) and len(v) >= 2 and all(isinstance(x, (int, float)) for x in v[:2]):
            lat, lon = float(v[0]), float(v[1])
            rows.append((name, {"center": [lat, lon], "bbox": _bbox_around(lat, lon, radius)}))
        elif isinstance(v, dict):
            bb = v.get("bbox")
            c = v.get("center") or ([v["lat"], v["lon"]] if "lat" in v and "lon" in v else None)
            if bb:
                rows.append((name, {"center": c or [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2], "bbox": bb}))
            elif c:
                rows.append((name, {"center": c, "bbox": _bbox_around(float(c[0]), float(c[1]), radius)}))

    if isinstance(d, dict) and d.get("type") == "FeatureCollection":
        for i, f in enumerate(d.get("features", []), 1):
            pr = f.get("properties") or {}
            pts = _coords((f.get("geometry") or {}).get("coordinates"))
            if not pts:
                continue
            lons, lats = [q[0] for q in pts], [q[1] for q in pts]
            name = pr.get("name") or f"{pr.get('@id') or pr.get('id') or f'#{i}'}"
            bb = [min(lats), min(lons), max(lats), max(lons)]
            if len(pts) == 1:
                bb = _bbox_around(lats[0], lons[0], radius)
            rows.append((name, {"center": [round((bb[0] + bb[2]) / 2, 6), round((bb[1] + bb[3]) / 2, 6)],
                                "bbox": [round(v, 6) for v in bb]}))
    elif isinstance(d, dict):
        for name, v in d.items():
            if not str(name).startswith("_"):
                one(str(name), v)
    elif isinstance(d, list):
        for i, v in enumerate(d, 1):
            if isinstance(v, dict):
                one(str(v.get("name") or f"#{i}"), v)
    # 同名的（同一所学校的几个校区、OSM 里几块同名围墙）加序号，一个都不丢
    seen: dict[str, int] = {}
    out = []
    for name, v in rows:
        seen[name] = seen.get(name, 0) + 1
        out.append((name if seen[name] == 1 else f"{name}#{seen[name]}", v))
    return out


def cmd_add(args, p: Path) -> None:
    b = _load(p)
    if args.level not in LEVELS:
        sys.exit(f"--level 只能是 {LEVELS}")
    if not args.names and not args.from_:
        sys.exit("给候选名，或 --from 文件（poi.py --out、gazetteer.py --out、osm.py geom 的 GeoJSON）")
    if args.from_:
        rows = _read_from(Path(args.from_), args.radius)
        if not rows:
            sys.exit(f"{args.from_} 里没读出带坐标的候选")
        n = 0
        for name, v in rows:
            if name in b["candidates"]:
                continue
            b["candidates"][name] = {"level": args.level, "parent": args.parent, "bbox": v["bbox"], "scan_bbox": None,
                                     "center": v["center"], "prior": args.prior, "status": "open",
                                     "note": args.note or "", "from": str(args.from_)}
            n += 1
        _log(b, f"add --from {args.from_} → +{n} 个 {args.level}")
        _save(p, b)
        print(f"从 {args.from_} 加入 {n} 个 {LEVEL_ZH[args.level]}候选（共读出 {len(rows)} 个，重名的已跳过）。"
              f"全部进盘、先验均匀：看过的每一个都要登记 evidence（对不上也记 --against），check 会列出没看过的。")
    for name in args.names:
        if name in b["candidates"]:
            print(f"已有 {name}，跳过")
            continue
        c = {"level": args.level, "parent": args.parent, "bbox": None, "scan_bbox": None, "prior": args.prior,
             "status": "open", "note": args.note or ""}
        if args.bbox:
            c["bbox"] = [float(v) for v in args.bbox.split(",")]
        b["candidates"][name] = c
        _log(b, f"add {name} ({args.level})")
    _save(p, b)
    print(f"候选 {len(b['candidates'])} 个")


def cmd_children(args, p: Path) -> None:
    b = _load(p)
    cmd = [UV, "run", str(HERE / "gazetteer.py"), "children", args.parent, "--out", str(p.parent / ".gz_children.json")]
    if args.level:
        cmd += ["--level", str(args.level)]
    if args.within:
        cmd += ["--within", args.within]
    if args.proxy:
        cmd += ["--proxy", args.proxy]
    r = _run(cmd)
    for line in r.stderr.splitlines():
        if "不当下一级" in line or "退回第一个" in line:
            print(line)
    out = r.stdout.strip(); print(out if len(out) < 1800 else out[:1800].rsplit('\n', 1)[0] + '\n  …')
    if r.returncode != 0:
        sys.exit(f"gazetteer 失败：{r.stderr.strip()[-600:]}")
    kids = json.loads((p.parent / ".gz_children.json").read_text(encoding="utf-8"))
    as_level, why = _child_level(b, args, out)
    n = 0
    for name, k in kids.items():
        if name in b["candidates"]:
            continue
        b["candidates"][name] = {"level": as_level, "parent": args.parent, "bbox": k.get("bbox"), "scan_bbox": None,
                                 "prior": 1.0, "status": "open", "note": k.get("note", ""), "osm_id": k.get("osm_id")}
        n += 1
    _log(b, f"children {args.parent} → +{n} 个 {as_level}")
    _save(p, b)
    print(f"加入 {n} 个候选（级别 {as_level}：{why}；先验均匀）。人口、名气不进分数。")


# 上级在 board 里是哪一级 → 下级记成哪一级
NEXT_LEVEL = {"country": "admin1", "admin1": "admin2", "admin2": "district", "city": "district", "district": "area",
              "area": "road", "road": "point"}


def _child_level(b: dict, args, gz_out: str) -> tuple[str, str]:
    """children 的候选级别：--as-level 给了就用；上级是国家 → admin1；上级已在 board 里 → 它的下一级
    （省下面隔了一级直接是区县的，如直辖市，记成 district）；都不是 → district。"""
    if args.as_level:
        return args.as_level, "--as-level 指定"
    m = re.search(r"admin_level (\d+)）下级 admin_level (\d+)", gz_out)
    p_lv, c_lv = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    if p_lv is not None and p_lv <= 2:
        # 直接从国家跳到更细的级别（--level 5/6）时别记成省级
        lv = "admin1" if c_lv is None or c_lv <= 4 else ("admin2" if c_lv == 5 else "district")
        return lv, f"上级是国家，下级 admin_level {c_lv}"
    hits = [k for k in b["candidates"] if _norm(k) == _norm(args.parent)]
    if len(hits) == 1:
        lv = b["candidates"][hits[0]]["level"]
        nxt = NEXT_LEVEL.get(lv, "district")
        if lv == "admin1" and p_lv is not None and c_lv is not None and c_lv >= p_lv + 2:
            nxt = "district"
        return nxt, f"上级 {hits[0]} 在候选盘里是 {lv}"
    return "district", "默认"


def cmd_clue(args, p: Path) -> None:
    b = _load(p)
    kid = f"K{len(b['clues']) + 1}"
    if args.status not in STATUS:
        sys.exit(f"--status 只能是 {STATUS}：observed=画面里直接看到的形状/颜色，read=读出的字/号码，inferred=推测（楼大概8层、路在上坡），computed=脚本算出来的")
    b["clues"][kid] = {"text": args.text, "kind": args.kind, "status": args.status, "file": args.file or "",
                       "source": args.source or "", "used": False}
    _log(b, f"clue {kid} [{args.kind}/{args.status}] {args.text}")
    _save(p, b)
    cap = LR_CAP[args.status]
    print(f"{kid} 登记。状态 {args.status}：似然比上限 {cap:g}" + ("，只能排序不能排除" if args.status in ("inferred", "observed") else "，可用于 exclude（还需算过的文件）"))


def _parse_lr(items: list[str] | None, default: float | None) -> list[tuple[str, float]]:
    out = []
    for it in items or []:
        if ":" in it:
            name, v = it.rsplit(":", 1)
            out.append((name, float(v)))
        elif default is not None:
            out.append((it, default))
        else:
            sys.exit(f"写成 名字:似然比，例如 {it}:5")
    return out


def cmd_evidence(args, p: Path) -> None:
    b = _load(p)
    if args.clue not in b["clues"]:
        sys.exit(f"没有线索 {args.clue}，先 `board.py clue`")
    cl = b["clues"][args.clue]
    cap = LR_CAP[cl["status"]]
    pairs = _parse_lr(args.for_, 3.0) + [(n, v) for n, v in _parse_lr(args.against, 1 / 3)]
    if not pairs:
        sys.exit("至少给一个 --for 名字:似然比 或 --against 名字:似然比")
    clipped = []
    for name, lr in pairs:
        cname = _find(b, name)
        if lr <= 0:
            sys.exit("似然比 0 等于排除，请走 `board.py exclude`（需要算过的文件）")
        lr2 = min(max(lr, 1 / cap), cap)
        if abs(lr2 - lr) > 1e-9:
            clipped.append(f"{cname}:{lr:g}→{lr2:g}")
        b["evidence"].append({"id": f"E{len(b['evidence']) + 1}", "clue": args.clue, "candidate": cname, "lr": lr2,
                              "why": args.why or "", "file": args.file or "", "cmd": args.command_ or ""})
    cl["used"] = True
    if args.file and not Path(args.file).exists():
        print(f"提示：{args.file} 不存在；证据文件必须是本次会话真实产出")
    _log(b, f"evidence {args.clue} → {', '.join(f'{n}:{v:g}' for n, v in pairs)}")
    _save(p, b)
    if clipped:
        print(f"线索 {args.clue} 是“{cl['status']}”，似然比夹到 1/{cap:g}–{cap:g}：{'; '.join(clipped)}。"
              f"要更大的权重，先把线索核实成 read/computed（读出字、跑脚本）再登记新线索。")
    print("已记录。" + ("" if args.why else "建议补 --why 写清依据。"))


def cmd_exclude(args, p: Path) -> None:
    b = _load(p)
    cname = _find(b, args.name)
    if args.clue not in b["clues"]:
        sys.exit(f"没有线索 {args.clue}")
    cl = b["clues"][args.clue]
    if cl["status"] not in ("read", "computed"):
        sys.exit(f"线索 {args.clue} 是“{cl['status']}”（推测/观察）：不能排除，只能 `evidence --against {cname}:0.34`。"
                 f"硬规则 9：排除和确认用同一个标准。")
    if not args.computed or not Path(args.computed).exists():
        sys.exit("排除必须附算过的文件（--computed，例如 geo.py frame 的输出、terrain.py 的比对图），文件要真实存在")
    c = b["candidates"][cname]
    if c["level"] in EXTENDED_LEVELS:
        if not args.covers:
            sys.exit(
                f"{cname} 是{LEVEL_ZH[c['level']]}级候选（有延展）：排除要加 --covers 写明证据实际覆盖到哪里"
                f"（'lat,lon' 或 'lat,lon:lat,lon'）。硬规则 9：排除范围必须 ≤ 证据范围——"
                f"在一个点上看过就整条排除是以点代面。只验了一段就改用："
                f"board.py evidence --clue {args.clue} --against {cname}:0.34 --file {args.computed}")
        pts = _parse_covers(args.covers)
        if not pts:
            sys.exit("--covers 要能解析出坐标：'lat,lon'（单点）或 'lat,lon:lat,lon'（区间）")
        r = _covers_ratio(c, pts)
        if r is not None and r[0] < COVERS_MIN:
            cov_m = _cov_span_m(pts[0], pts[-1]) if len(pts) >= 2 else 0.0
            sys.exit(
                f"--covers 只覆盖 {cname} 的约 {r[0]:.0%}（证据 {cov_m:.0f} m / 候选范围对角 {r[1]:.0f} m）："
                f"不足以整条排除。补足其余段的比对图再排除，或先降权："
                f"board.py evidence --clue {args.clue} --against {cname}:0.34 --file {args.computed}")
    c["status"] = "excluded"
    c["excluded_by"] = {"clue": args.clue, "computed": args.computed, "why": args.why or "",
                        "covers": args.covers or ""}
    cl["used"] = True
    _log(b, f"exclude {cname} by {args.clue} ({args.computed})")
    _save(p, b)
    print(f"已排除 {cname}。被排除的候选仍在账本里，check 会回头看。")


def cmd_scan_bbox(args, p: Path) -> None:
    b = _load(p)
    cname = _find(b, args.name)
    b["candidates"][cname]["scan_bbox"] = [float(v) for v in args.bbox.split(",")]
    _log(b, f"scan-bbox {cname} {args.bbox}")
    _save(p, b)
    print("ok")


def cmd_urban(args, p: Path) -> None:
    b = _load(p)
    cname = _find(b, args.name)
    cmd = [UV, "run", str(HERE / "gazetteer.py"), "urban", cname]
    if args.within:
        cmd += ["--within", args.within]
    if args.proxy:
        cmd += ["--proxy", args.proxy]
    r = _run(cmd)
    if r.returncode != 0:
        sys.exit(f"gazetteer urban 失败：{r.stderr.strip()[-600:]}")
    d = json.loads(r.stdout[r.stdout.index("{"):])
    if d.get("urban_bbox"):
        b["candidates"][cname]["scan_bbox"] = d["urban_bbox"]
        b["candidates"][cname]["urban_source"] = d.get("source")
        _log(b, f"urban {cname} {d['urban_bbox']} ({d.get('source')})")
        _save(p, b)
        print(f"{cname} 建成区 {d['urban_bbox']}，约 {d.get('urban_bbox_km2')} km²（来源 {d.get('source')}）"
              + (f"；{d['note']}" if d.get("note") else ""))
    else:
        print(f"{cname}：{d.get('note', '没有建成区数据')}；用 `board.py scan-bbox` 手动给")


def cmd_falsify(args, p: Path) -> None:
    b = _load(p)
    cname = _find(b, args.name)
    b["falsify"].setdefault(cname, []).append(args.text)
    _log(b, f"falsify {cname}: {args.text}")
    _save(p, b)
    print("已记录证伪条件。出现就放弃，不找理由圆。")


def cmd_rank(args, p: Path, quiet: bool = False) -> dict:
    b = _load(p)
    out = {}
    for lv in LEVELS:
        rows = _scores(b, lv, args.prior_by)
        if not rows:
            continue
        out[lv] = rows
        if quiet:
            continue
        print(f"\n[{LEVEL_ZH[lv]}] {len(rows)} 个候选（未排除 {sum(1 for r in rows if not r['excluded'])}）")
        print(f"  {'候选':<14}{'份额':>7}{'证据':>5}{'核实':>5}{'页数':>6}  {'份额/页':>8}  备注")
        for r in rows[: args.limit]:
            pages, src = _cost_of(r["c"], args)
            ratio = (r["share"] / pages) if pages else None
            flag = "已排除" if r["excluded"] else ""
            print(f"  {r['name']:<14}{r['share']:>7.1%}{r['n_ev']:>5}{r['n_verified']:>5}{(pages if pages is not None else '?'):>6}"
                  f"  {(f'{ratio:.4f}' if ratio is not None else '?'):>8}  {flag} {src if pages is not None else ''} {r['c'].get('note', '')[:30]}")
        if len(rows) > args.limit:
            print(f"  … 还有 {len(rows) - args.limit} 个（--limit 调大）")
    if not out and not quiet:
        print("没有候选：先 `board.py add` 或 `board.py children`")
    return out


def cmd_next(args, p: Path) -> None:
    b = _load(p)
    lv = _frontier(b)
    if not lv:
        print("没有候选。先做第 2 步查表线索或第 4 步环境粗定位，把候选列全（board.py children）")
        return
    rows = [r for r in _scores(b, lv, args.prior_by) if not r["excluded"]]
    top = rows[0]
    second = rows[1] if len(rows) > 1 else None
    unused = [k for k, c in b["clues"].items() if not c["used"]]
    print(f"当前前沿：{LEVEL_ZH[lv]}，未排除 {len(rows)} 个；第一 {top['name']} {top['share']:.0%}"
          + (f"，第二 {second['name']} {second['share']:.0%}" if second else ""))
    if unused:
        pending = ", ".join(f"{k}({b['clues'][k]['kind']})" for k in unused)
        print(f"还没用上的线索：{pending} → 先 evidence 或 apply")
    separable = (not second) or (top["share"] >= 0.7 and top["share"] / max(second["share"], 1e-9) >= 3)
    if separable and top["n_verified"] == 0 and second:
        print(f"{top['name']} 领先但没有任何核实过的证据（read/computed），只是推测堆出来的：先做一项便宜的核实再扫。")
    if separable:
        pages, src = _cost_of(top["c"], args)
        print(f"→ 可以进入缩圈/扫描：{top['name']}（{src}，约 {pages if pages is not None else '?'} 页）。")
        if src == "整区bbox":
            print("  先 `board.py urban <名>` 或 `scan-bbox` 把范围缩到建成区，页数会小一个数量级。")
        elif pages is None:
            print(f"  它还没有范围：`board.py urban {top['name']} --within <上级>` 或 `board.py scan-bbox {top['name']} --bbox s,w,n,e`，否则算不出页数。")
        if top["name"] not in b["falsify"]:
            print(f"  扫之前先写证伪条件：`board.py falsify {top['name']} --text \"…\"`")
        print("  扫描用机器先排序：`sat_scan.py grid --bbox <scan_bbox> --preset …`、`osm.py buildings`、`poi.py`；只看前 20–30 名。")
        return
    print("→ 分不开。按便宜到贵做区分检验，每项对全部未排除候选一起做，不是只查第一名：")
    kinds_have = {c["kind"] for c in b["clues"].values()}
    for kind, tip in CHEAP_OPS:
        mark = "（已有这类线索，登记 evidence）" if any(k in kinds_have for k in kind.split("/")) else ""
        print(f"  - {kind}: {tip} {mark}")
    print("→ 便宜检验都做过仍分不开：不要停。按“份额 ÷ 页数”顺序扫，小的先扫完，大的设页数上限：")
    order = []
    for r in rows:
        pages, src = _cost_of(r["c"], args)
        order.append((r["share"] / pages if pages else 0, r, pages, src))
    order.sort(key=lambda t: -t[0])
    for ratio, r, pages, src in order[:8]:
        print(f"    {r['name']:<14} 份额 {r['share']:.0%}  页数 {pages if pages is not None else '?'} ({src})  份额/页 {ratio:.4f}")
    if any(pages is None for _, _, pages, _ in order):
        print("    有候选没有范围：`board.py urban` 或 `scan-bbox` 补上，否则排不了序")


def _parse_covers(s: str) -> list[tuple[float, float]]:
    """--covers：'lat,lon' 或 'lat,lon:lat,lon'（证据实际覆盖到的点/区间）。解析不出坐标返回 []。"""
    pts = []
    for part in str(s).split(":"):
        m = re.findall(r"-?\d+\.\d+|-?\d+", part)
        if len(m) >= 2:
            pts.append((float(m[0]), float(m[1])))
    return pts


def _cov_span_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    kx = 111320.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((b[1] - a[1]) * kx, (b[0] - a[0]) * 110540.0)


def _covers_ratio(c: dict, pts: list[tuple[float, float]]) -> tuple[float, float] | None:
    """(证据覆盖长度 / 候选范围对角, 对角米数)。候选没有 bbox 时返回 None（算不出，只能提示）。"""
    bb = c.get("bbox") or c.get("scan_bbox")
    if not bb or len(bb) != 4:
        return None
    try:
        sw, ww, nn, ee = (float(v) for v in bb)
    except (TypeError, ValueError):
        return None
    diag = _cov_span_m((sw, ww), (nn, ee))
    if diag <= 1.0:
        return None
    cov = _cov_span_m(pts[0], pts[-1]) if len(pts) >= 2 else 0.0
    return cov / diag, diag


def _unseen(rows: list[dict], lv: str) -> list[str]:
    """细层（片区/路/点）里一条证据都没有的未排除候选。粗层按份额/页数排着扫，没证据是常态，不算。"""
    if lv not in ("area", "road", "point"):
        return []
    return [r["name"] for r in rows if r["n_ev"] == 0 and not r["excluded"]]


def cmd_check(args, p: Path) -> None:
    b = _load(p)
    ok = True
    print("出结论前检查：")
    for name, c in b["candidates"].items():
        if c.get("status") == "excluded":
            ex = c.get("excluded_by", {})
            if not ex.get("computed") or not Path(ex["computed"]).exists():
                ok = False
                print(f"  FAIL 排除 {name} 的文件不存在：{ex.get('computed')}")
    for name, c in b["candidates"].items():
        if c.get("status") != "excluded" or c["level"] not in EXTENDED_LEVELS:
            continue
        ex = c.get("excluded_by", {})
        pts = _parse_covers(ex.get("covers", ""))
        if not pts:
            ok = False
            print(f"  FAIL 排除 {name}（{LEVEL_ZH[c['level']]}级）没有记录 --covers：证据覆盖了多少无从判断，"
                  f"可能是以点代面 → 重新 exclude 并补 --covers，或改成 evidence --against 降权")
            continue
        r = _covers_ratio(c, pts)
        if r is None:
            print(f"  NOTE 排除 {name} 的证据覆盖 {ex['covers']}；候选没有 bbox，覆盖比例算不出 → "
                  f"结论里写明只验了这一段")
        elif r[0] < COVERS_MIN:
            ok = False
            print(f"  FAIL 排除 {name} 的证据只覆盖约 {r[0]:.0%}（候选范围对角 {r[1]:.0f} m）：排除范围大于证据范围")
    lv = _frontier(b)
    if lv:
        rows = [r for r in _scores(b, lv, args.prior_by) if not r["excluded"]]
        top = rows[0]
        if top["n_verified"] == 0:
            ok = False
            print(f"  FAIL 主答案 {top['name']} 没有 read/computed 级证据，只有观察和推测：不能自报到这一级以下")
        else:
            print(f"  ok   主答案 {top['name']}：证据 {top['n_ev']} 条，其中核实 {top['n_verified']} 条")
        weak = [r["name"] for r in rows[1:] if r["share"] >= 0.15]
        if weak:
            print(f"  WARN 还有份额 ≥15% 的备选：{', '.join(weak)} → 写进 alternatives 并给区分检验，不取中点")
        unseen = _unseen(rows, lv)
        if unseen:
            print(f"  WARN {len(unseen)}/{len(rows)} 个{LEVEL_ZH[lv]}候选一条证据都没有，等于没看过："
                  f"{'、'.join(unseen[:10])}{' …' if len(unseen) > 10 else ''} → 逐个看，对不上也登记 evidence --against；"
                  f"没看过的不能算排除，结论里写明")
        down = [(e["candidate"], e["clue"]) for e in b["evidence"]
                if e["lr"] < 1 and b["clues"][e["clue"]]["status"] in ("inferred", "observed")
                and b["candidates"][e["candidate"]].get("status") != "excluded"]
        if down:
            names = sorted({n for n, _ in down})
            print(f"  NOTE 被推测降权但没排除的候选：{', '.join(names[:10])} → 候选全没对上时先回头看这些")
    for k, c in b["clues"].items():
        if c["status"] in ("read", "computed") and not c.get("file"):
            print(f"  WARN {k} 是 {c['status']} 但没有文件：读出的字要有放大图，算的结果要有输出文件")
    unused = [k for k, c in b["clues"].items() if not c["used"]]
    if unused:
        print(f"  NOTE 没用上的线索：{', '.join(unused)} → 写进 unused_clues")
    for name in [n for n, c in b["candidates"].items() if c.get("status") != "excluded"]:
        if b["falsify"].get(name):
            print(f"  ok   {name} 证伪条件：{'；'.join(b['falsify'][name])}")
    print("结果：" + ("通过" if ok else "有 FAIL，先补"))


def cmd_report(args, p: Path) -> None:
    b = _load(p)
    lv = _frontier(b)
    rep = {"candidate_levels": {}, "main": None, "alternatives": [], "excluded": [], "unused_clues": [],
           "downweighted_not_excluded": [], "falsify": b["falsify"]}
    for l2 in LEVELS:
        rows = _scores(b, l2, args.prior_by)
        if rows:
            rep["candidate_levels"][l2] = [{"name": r["name"], "share": round(r["share"], 3), "evidence": r["n_ev"],
                                            "verified": r["n_verified"], "excluded": r["excluded"]} for r in rows]
    if lv:
        rows = [r for r in _scores(b, lv, args.prior_by) if not r["excluded"]]
        top = rows[0]
        rep["main"] = {"level": lv, "name": top["name"], "share": round(top["share"], 3),
                       "evidence": [{"clue": b["clues"][e["clue"]]["text"], "status": b["clues"][e["clue"]]["status"],
                                     "lr": e["lr"], "why": e["why"], "file": e["file"]}
                                    for e in b["evidence"] if e["candidate"] == top["name"]]}
        for r in rows[1:]:
            if r["share"] >= 0.05:
                rep["alternatives"].append({"name": r["name"], "share": round(r["share"], 3),
                                            "how_to_separate": "对两者一起做一项便宜检验（地形/涂装/市政设施/水系模板），或各扫建成区前 3 页"})
        rep["unexamined"] = _unseen(rows, lv)
    for name, c in b["candidates"].items():
        if c.get("status") == "excluded":
            ex = c.get("excluded_by", {})
            rep["excluded"].append({"name": name, "clue": b["clues"].get(ex.get("clue"), {}).get("text", ""),
                                    "computed": ex.get("computed"), "why": ex.get("why", "")})
    rep["unused_clues"] = [c["text"] for c in b["clues"].values() if not c["used"]]
    rep["downweighted_not_excluded"] = sorted({e["candidate"] for e in b["evidence"] if e["lr"] < 1
                                               and b["clues"][e["clue"]]["status"] in ("inferred", "observed")
                                               and b["candidates"][e["candidate"]].get("status") != "excluded"})
    if args.merge:
        mp = Path(args.merge)
        base = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
        base["board"] = rep
        if rep["alternatives"]:
            base.setdefault("alternatives", [])
            base["alternatives"] = [f"{a['name']}（份额 {a['share']:.0%}）：{a['how_to_separate']}" for a in rep["alternatives"]] + \
                [x for x in base.get("alternatives", []) if not isinstance(x, str) or "份额" not in x]
        base["excluded"] = [f"{x['name']}：{x['why']}（{x['computed']}）" for x in rep["excluded"]] or base.get("excluded", [])
        base["unused_clues"] = rep["unused_clues"] or base.get("unused_clues", [])
        mp.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已并入 {mp}（board 字段 + alternatives/excluded/unused_clues）")
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:4000])
    if rep["main"] and rep["alternatives"]:
        print("\n提醒：主答案 = 第一名，备选另列；不取中点、不画大圆。")


def cmd_apply(args, p: Path) -> None:
    b = _load(p)
    cl = HERE / "clues.py"
    if not cl.exists():
        sys.exit("clues.py 还没就位：先手工 `board.py clue` + `evidence`")
    r = _run([UV, "run", str(cl), "lookup", args.kind, args.value, "--json"])
    if r.returncode != 0:
        sys.exit(f"clues.py 失败：{r.stderr.strip()[-400:]}")
    try:
        d = json.loads(r.stdout[r.stdout.index("{"):])
    except Exception:  # noqa: BLE001
        sys.exit(f"clues.py 输出不是 JSON：{r.stdout[:300]}")
    matches = d.get("matches") or []
    kid = args.clue
    if not kid:
        kid = f"K{len(b['clues']) + 1}"
        b["clues"][kid] = {"text": f"{args.kind} {args.value}", "kind": args.kind, "status": "read",
                           "file": args.file or "", "source": d.get("source", ""), "used": False}
    if not matches:
        print(f"查表没有结果：{d.get('note', '')}。线索 {kid} 已登记，未加证据。")
        _save(p, b)
        return
    MUNICIPALITIES = ("北京市", "上海市", "天津市", "重庆市")

    def level_of(key: str, m: dict) -> str:
        if key == "country":
            return "country"
        if key == "admin1":
            return "admin1"
        name = m.get("admin2", "")
        if m.get("admin1") in MUNICIPALITIES or name.endswith(("区", "县", "旗")):
            return "district"
        return "city"

    lr = args.lr
    touched = set()
    for m in matches:
        for key in ("country", "admin1", "admin2"):
            name = m.get(key)
            if not name:
                continue
            lv = level_of(key, m)
            cname = next((k for k in b["candidates"] if _norm(k) == _norm(name)), None)
            if not cname:
                b["candidates"][name] = {"level": lv, "parent": m.get("admin1") if key == "admin2" else None, "bbox": None,
                                        "scan_bbox": None, "prior": 1.0, "status": "open", "note": f"来自查表 {args.kind}"}
                cname = name
            b["evidence"].append({"id": f"E{len(b['evidence']) + 1}", "clue": kid, "candidate": cname, "lr": lr,
                                  "why": f"查表 {args.kind}={args.value}", "file": args.file or "", "cmd": f"clues.py lookup {args.kind} {args.value}"})
            touched.add((lv, cname))
    # 同级别其他未排除候选：反对但不排除（查表也可能有例外：外地车、总部电话）
    for lv, _ in set(touched):
        for k, c in b["candidates"].items():
            if c["level"] == lv and (lv, k) not in touched and c.get("status") != "excluded":
                b["evidence"].append({"id": f"E{len(b['evidence']) + 1}", "clue": kid, "candidate": k, "lr": 1 / lr,
                                      "why": f"查表 {args.kind}={args.value} 不指向这里", "file": "", "cmd": ""})
    b["clues"][kid]["used"] = True
    _log(b, f"apply {args.kind}={args.value} → {[n for _, n in touched]}")
    _save(p, b)
    print(f"{kid}：{args.kind}={args.value} → {', '.join(n for _, n in sorted(touched))}（似然比 {lr:g}；同级其余 1/{lr:g}，未排除）")


def cmd_log(args, p: Path) -> None:
    b = _load(p)
    print("\n".join(b.get("log", [])[-args.n:]))
    print(f"\n线索 {len(b['clues'])} 条，证据 {len(b['evidence'])} 条，候选 {len(b['candidates'])} 个")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", type=Path, default=Path("board.json"))
    sub = ap.add_subparsers(dest="cmd", required=True)

    def rank_opts(sp):
        sp.add_argument("--prior-by", choices=["none", "area"], default="none", help="先验：均匀（默认）或按 bbox 面积。没有按人口的选项")
        sp.add_argument("--zoom", type=int, default=16, help="扫描页数按这个缩放算（找操场 z16 总览，厂房 z16，楼 z17）")
        sp.add_argument("--cell", type=int, default=320)
        sp.add_argument("--cols", type=int, default=5)

    i = sub.add_parser("init")
    i.add_argument("--photo", required=True)
    i.add_argument("--case")
    i.add_argument("--force", action="store_true")

    a = sub.add_parser("add")
    a.add_argument("names", nargs="*")
    a.add_argument("--from", dest="from_", help="批量导入：poi.py --out / gazetteer.py --out 的 JSON，或 osm.py geom 的 GeoJSON")
    a.add_argument("--radius", type=float, default=500, help="--from 里只有点坐标时，候选范围取点周围多少米（默认 500）")
    a.add_argument("--level", required=True, help=f"{'/'.join(LEVELS)}")
    a.add_argument("--parent")
    a.add_argument("--bbox", help="s,w,n,e")
    a.add_argument("--prior", type=float, default=1.0)
    a.add_argument("--note")

    ch = sub.add_parser("children", help="gazetteer.py 列全下级行政区并加为候选")
    ch.add_argument("parent")
    ch.add_argument("--level", type=int, help="OSM admin_level（不给就自动）")
    ch.add_argument("--within")
    ch.add_argument("--as-level", help=f"记成哪一级候选：{'/'.join(LEVELS)}。不给就自动：上级是国家记 admin1，"
                                        "上级已在候选盘里记它的下一级，否则 district")
    ch.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))

    c = sub.add_parser("clue")
    c.add_argument("text")
    c.add_argument("--kind", required=True, help="plate/area-code/text/livery/terrain/sun/infra/vegetation/network/municipal/ip/hint/…")
    c.add_argument("--status", required=True, help="/".join(STATUS))
    c.add_argument("--file", help="放大图、脚本输出")
    c.add_argument("--source", help="在图里哪、谁说的")

    e = sub.add_parser("evidence")
    e.add_argument("--clue", required=True)
    e.add_argument("--for", dest="for_", action="append", help="名字:似然比（>1），可重复；只写名字默认 3")
    e.add_argument("--against", action="append", help="名字:似然比（<1），可重复；只写名字默认 1/3")
    e.add_argument("--why")
    e.add_argument("--file")
    e.add_argument("--command", dest="command_", help="产出这份证据的命令")

    x = sub.add_parser("exclude")
    x.add_argument("name")
    x.add_argument("--clue", required=True)
    x.add_argument("--computed", required=True, help="算过的文件（必须存在）")
    x.add_argument("--covers", help="证据实际覆盖到哪里：'lat,lon' 或 'lat,lon:lat,lon'；区县/片区/路级候选必填")
    x.add_argument("--why")

    sb = sub.add_parser("scan-bbox")
    sb.add_argument("name")
    sb.add_argument("--bbox", required=True)

    u = sub.add_parser("urban")
    u.add_argument("name")
    u.add_argument("--within")
    u.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))

    f = sub.add_parser("falsify")
    f.add_argument("name")
    f.add_argument("--text", required=True)

    r = sub.add_parser("rank")
    rank_opts(r)
    r.add_argument("--limit", type=int, default=15)

    n = sub.add_parser("next")
    rank_opts(n)

    k = sub.add_parser("check")
    rank_opts(k)

    rp = sub.add_parser("report")
    rank_opts(rp)
    rp.add_argument("--merge", help="并入已有的 result.json")

    ap_ = sub.add_parser("apply", help="查表线索自动加候选和证据（clues.py）")
    ap_.add_argument("--kind", required=True, help="plate/area-code/calling-code/driving-side/territories")
    ap_.add_argument("--value", required=True)
    ap_.add_argument("--clue", help="已登记的线索 id；不给就新建一条 read 线索")
    ap_.add_argument("--file", help="读出这个字的放大图")
    ap_.add_argument("--lr", type=float, default=20.0)

    lg = sub.add_parser("log")
    lg.add_argument("-n", type=int, default=40)

    args = ap.parse_args()
    p = args.board
    fn = {"init": cmd_init, "add": cmd_add, "children": cmd_children, "clue": cmd_clue, "evidence": cmd_evidence,
          "exclude": cmd_exclude, "scan-bbox": cmd_scan_bbox, "urban": cmd_urban, "falsify": cmd_falsify,
          "rank": cmd_rank, "next": cmd_next, "check": cmd_check, "report": cmd_report, "apply": cmd_apply, "log": cmd_log}
    fn[args.cmd](args, p)


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
