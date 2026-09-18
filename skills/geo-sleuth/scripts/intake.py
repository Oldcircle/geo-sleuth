#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""定位第 0–3 步一条命令跑完：元数据、四边四角放大、搜图变体、OCR、以图搜图，并行执行，出一份报告。

产出（都在 --out-dir 里）：
  exif.json  edges/  variants/  ocr.json ocr.png  rev/<名>_<引擎>.png + .json  intake.md  intake.json
intake.md 是给人（和 LLM）看的：元数据、OCR 文字、百度相似图片（数量、来源站点、编号拼图 rev/<名>_baidu_similar.jpg）、
识图标签分级计票、疑似小区/楼盘/酒店名、产出清单、没做和失败的项。
识图截图和相似图拼图务必打开看；"没搜到"和"没搜"在报告里分开写。

  intake.py photo.jpg --out-dir intake/ [--box x0,y0,x1,y1 ...] [--engines baidu,yandex] [--exclude 词1,词2]
            [--no-rev] [--no-ocr] [--max-variants 4] [--proxy socks5://127.0.0.1:10808（示例）]

示例：
  intake.py photo.jpg --out-dir intake/
  intake.py photo.jpg --out-dir intake/ --box 300,120,900,760 --exclude 网络迷踪,某博主      # 盲测时排除讲解帖
  intake.py photo.jpg --out-dir intake/ --no-rev                                              # 只要元数据、边缘图、OCR（30 秒内）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
CITY_SUFFIX = ("省", "市", "区", "县", "州", "盟", "旗", "国", "府", "道", "自治区", "特别行政区", "City", "Province", "County", "Prefecture")
PLACE_WORDS = ("公园", "大厦", "小区", "花园", "广场", "学校", "中学", "小学", "大学", "酒店", "宾馆", "景区", "寺", "塔", "桥", "大楼",
               "中心", "村", "镇", "街", "路", "湖", "山", "站", "港", "码头", "厂", "园", "苑", "府", "城", "馆", "庙", "教堂", "Park",
               "Tower", "Hotel", "Bridge", "Station", "Square", "Plaza", "Church", "Temple", "Mall", "Street", "Road", "Avenue")
KNOWN_CITIES = ("北京", "上海", "天津", "重庆", "广州", "深圳", "成都", "杭州", "武汉", "西安", "南京", "苏州", "郑州", "长沙", "青岛", "沈阳",
                "大连", "厦门", "福州", "济南", "合肥", "昆明", "贵阳", "南宁", "哈尔滨", "长春", "石家庄", "太原", "兰州", "乌鲁木齐", "拉萨",
                "呼和浩特", "银川", "西宁", "海口", "三亚", "宁波", "无锡", "东莞", "佛山", "珠海", "香港", "澳门", "台北", "东京", "大阪", "首尔",
                "曼谷", "新加坡", "吉隆坡", "伦敦", "巴黎", "纽约", "洛杉矶", "悉尼", "墨尔本", "温哥华", "多伦多", "莫斯科", "柏林", "罗马", "马德里")


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 900) -> tuple[int, str, str]:
    try:
        r = subprocess.run(cmd, text=True, capture_output=True, cwd=cwd, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"超时 {timeout}s"


def _script(name: str) -> str:
    return str(HERE / name)


GENERIC = ("城市街道", "城市", "街道", "市区", "街景", "建筑", "楼房", "高楼", "夜景", "风景", "天空", "道路", "马路", "小镇", "乡村", "都市",
           "city", "street", "town", "building", "skyline", "road", "urban")
KNOWN_CITIES_EN = ("hong kong", "kowloon", "tokyo", "osaka", "kyoto", "seoul", "bangkok", "singapore", "kuala lumpur", "taipei", "shanghai",
                   "beijing", "shenzhen", "guangzhou", "chengdu", "chongqing", "london", "paris", "new york", "los angeles", "sydney",
                   "melbourne", "vancouver", "toronto", "moscow", "berlin", "rome", "madrid", "dubai", "istanbul", "mumbai", "delhi",
                   "hanoi", "ho chi minh", "manila", "jakarta", "macau", "lisbon", "barcelona", "amsterdam", "prague", "vienna", "cairo")


def _classify(tag: str) -> str:
    t = tag.strip("：: ，,。.")
    low = t.lower()
    if low in GENERIC or t in GENERIC:
        return "other"
    if any(c in low for c in KNOWN_CITIES_EN):
        return "city"
    if any(c in t for c in KNOWN_CITIES):
        return "city"
    if len(t) >= 3 and any(t.endswith(s) for s in CITY_SUFFIX) and not any(g in t for g in ("街道", "城市")):
        return "city"
    if any(w in t for w in PLACE_WORDS):
        return "place"
    return "other"


def _collect_rev(rev_dir: Path) -> tuple[list[dict], dict]:
    """读 revimg 的 .json：每张图每个引擎的 guess/links，做分级计票。"""
    entries = []
    for jf in sorted(rev_dir.glob("*.json")):
        try:
            d = json.loads(jf.read_text())
        except Exception:  # noqa: BLE001
            continue
        m = re.match(r"(.+)_(baidu|yandex|bing|baiduimg|sogouimg)$", jf.stem)
        if not m:
            continue
        simi = d.get("similar") or []
        entries.append({"variant": m.group(1), "engine": m.group(2), "guess": d.get("guess") or [], "links": (d.get("links") or [])[:8],
                        "error": d.get("error"), "refused": bool(d.get("refused")), "shot": str(jf.with_suffix(".png").name),
                        "json": jf.name, "similar_n": len(simi), "similar_sites": Counter(x.get("site") or "?" for x in simi).most_common(),
                        "similar_sheet": Path(d["similar_sheet"]).name if d.get("similar_sheet") else None,
                        "similar_note": d.get("similar_sheet_note")})
    votes: dict = {"city": {}, "place": {}}
    for e in entries:
        seen_city = set()
        for g in e["guess"]:
            body = re.sub(r"^(图中可能是|Image appears to contain)[：:]?", "", g).strip()
            for tag in re.split(r"[、/，,;；|]", body):
                tag = tag.strip()
                if len(tag) < 2:
                    continue
                k = _classify(tag)
                if k == "city":
                    key = tag
                    if (e["engine"], key) in seen_city:      # 同一引擎多个变体说同一城只算一票
                        continue
                    seen_city.add((e["engine"], key))
                    votes["city"].setdefault(key, set()).add(e["engine"])
                elif k == "place":
                    votes["place"].setdefault(tag, set()).add(f"{e['engine']}/{e['variant']}")
    return entries, {k: {t: sorted(v) for t, v in d.items()} for k, d in votes.items()}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo")
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--box", action="append", help="x0,y0,x1,y1：紧裁变体，可重复")
    ap.add_argument("--engines", default="baidu,yandex")
    ap.add_argument("--exclude", help="以图搜图结果里排除的词（盲测用）")
    ap.add_argument("--no-rev", action="store_true")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--max-variants", type=int, default=4, help="每个引擎最多搜几张变体（原图之外）")
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    args = ap.parse_args()

    photo = Path(args.photo).resolve()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "edges").mkdir(exist_ok=True)
    (out / "variants").mkdir(exist_ok=True)
    t_all = time.time()
    timings: dict = {}
    status: dict = {}

    def timed(name, fn):
        t0 = time.time()
        try:
            res = fn()
            status[name] = "ok" if res[0] == 0 else f"失败: {(res[2] or res[1])[-300:].strip()}"
        except Exception as e:  # noqa: BLE001
            status[name] = f"异常: {e}"
            res = (1, "", str(e))
        timings[name] = round(time.time() - t0, 1)
        return res

    def exif():
        return _run(["uv", "run", _script("exif.py"), str(photo)])

    def edges():
        return _run(["uv", "run", _script("imgprep.py"), "edges", str(photo), "--out-dir", str(out / "edges")])

    def variants():
        rc, so, se = _run(["uv", "run", _script("imgprep.py"), "variants", str(photo), "--prefix", "full", "--out-dir", str(out / "variants")])
        for i, b in enumerate(args.box or [], 1):
            r2 = _run(["uv", "run", _script("imgprep.py"), "variants", str(photo), "--box", b, "--prefix", f"box{i}", "--out-dir", str(out / "variants")])
            rc, so, se = max(rc, r2[0]), so + r2[1], se + r2[2]
        return rc, so, se

    def ocr():
        return _run(["uv", "run", _script("ocr.py"), str(photo), "--out", str(out / "ocr.json"), "--draw", str(out / "ocr.png")])

    # 第一批：元数据、边缘、变体、OCR 并行
    with ThreadPoolExecutor(4) as ex:
        f_exif = ex.submit(timed, "exif", exif)
        f_edges = ex.submit(timed, "edges", edges)
        f_var = ex.submit(timed, "variants", variants)
        f_ocr = None if args.no_ocr else ex.submit(timed, "ocr", ocr)
        exif_res = f_exif.result()
        f_edges.result()
        f_var.result()
        if f_ocr:
            f_ocr.result()
    try:
        exif_json = json.loads(exif_res[1].strip().splitlines()[0]) if exif_res[1].strip() else {}
    except Exception:  # noqa: BLE001
        exif_json = {"raw": exif_res[1][:500]}
    (out / "exif.json").write_text(json.dumps(exif_json, ensure_ascii=False, indent=1))

    # 第二批：以图搜图，两个引擎并行，各搜原图 + 最多 max-variants 张变体
    rev_dir = out / "rev"
    entries, votes = [], {"city": {}, "place": {}}
    if not args.no_rev:
        rev_dir.mkdir(exist_ok=True)
        var_files = sorted((out / "variants").glob("*.jpg")) + sorted((out / "variants").glob("*.png"))
        prefer = [f for f in var_files if any(k in f.stem for k in ("crop", "flip", "box"))] + [f for f in var_files if not any(k in f.stem for k in ("crop", "flip", "box"))]
        images = [str(photo)] + [str(f) for f in prefer[: args.max_variants]]

        def rev(engine):
            cmd = ["uv", "run", _script("revimg.py"), *images, "--out-dir", str(rev_dir), "--engines", engine]
            if args.exclude:
                cmd += ["--exclude", args.exclude]
            if engine == "yandex" and args.proxy:
                cmd += ["--proxy", args.proxy]
            return _run(cmd, timeout=900)

        with ThreadPoolExecutor(2) as ex:
            futs = {eng: ex.submit(timed, f"rev-{eng}", (lambda e=eng: (lambda: rev(e)))()) for eng in [e for e in args.engines.split(",") if e]}
            for eng, f in futs.items():
                f.result()
        entries, votes = _collect_rev(rev_dir)

    ocr_items = []
    if (out / "ocr.json").exists():
        try:
            ocr_items = json.loads((out / "ocr.json").read_text()).get("items", [])
        except Exception:  # noqa: BLE001
            pass

    # ---- 报告
    L = [f"# 第 0–3 步报告：{photo.name}", "", f"总用时 {time.time() - t_all:.0f}s；各步：" + "，".join(f"{k} {v}s" for k, v in timings.items()), ""]
    L += ["## 元数据", ""]
    gps = exif_json.get("gps") or exif_json.get("GPS")
    if exif_json and (gps or exif_json.get("datetime") or exif_json.get("DateTimeOriginal")):
        L.append("```\n" + json.dumps(exif_json, ensure_ascii=False, indent=1)[:1500] + "\n```")
        L.append("元数据是假设（可被改、可被抹）：GPS 和时间都要用画面核对。")
    else:
        L.append("无元数据（转发、截图、翻拍常见）。" + (f" 原始输出：`{json.dumps(exif_json, ensure_ascii=False)[:300]}`" if exif_json else ""))
    L += ["", "## OCR 读到的文字（第二读者；pass=up/tile 的只有放大后才读出，算假设）", ""]
    if args.no_ocr:
        L.append("没做（--no-ocr）。")
    elif ocr_items:
        L.append("| 置信 | 来源 | 位置(px) | 文字 |")
        L.append("|---|---|---|---|")
        for t in ocr_items[:40]:
            L.append(f"| {t['conf']:.2f} | {t['pass']} | {t['box']} | {t['text']} |")
        L.append("")
        L.append("电话号码、车牌、路牌专名、发牌单位：先 `clues.py lookup`，再 `board.py apply`。")
    else:
        L.append("没读到文字" + (f"（OCR {status.get('ocr')}）" if status.get("ocr") != "ok" else "。可能是真没字，也可能字太小：用 imgprep.py zoom 手动放大再看"))
    L += ["", "## 以图搜图", ""]
    if args.no_rev:
        L.append("没做（--no-rev）。这不是“搜过无果”。")
    else:
        for eng in args.engines.split(","):
            st = status.get(f"rev-{eng}", "未跑")
            L.append(f"- {eng}: {st}")
        refused = [e for e in entries if e["error"] or e["refused"]]
        if refused:
            L.append("- 引擎拒绝/失败的项（不等于没搜到）：" + "，".join(f"{e['variant']}/{e['engine']}: {e['error'] or '拒绝处理'}" for e in refused))
        L.append("")
        baidu = sorted([e for e in entries if e["engine"] == "baidu"], key=lambda e: e["variant"] != photo.stem)
        if baidu:
            L.append("### 相似图片（百度；先打开拼图看）")
            L.append("")
            L.append("近重复照片是最快的定位路径：同一个物体、同一处场景常被别人拍过并发在点评、抖音、小红书上，来源页的店名、景区名、定位直接给地点。"
                     "打开拼图，逐格和左上角的查询图比**固定特征**（构件形状、熏黑和破损、背后的山/楼/桥/电塔），只是同类物体的不算。"
                     "有近重复的：编号 i 就是该图 JSON 里 `similar[i]`，`from` 是来源页、`site` 是站点；同一来源页的其他图也看一遍。"
                     "要登录才能看的来源不登录、不绕验证，改用画面特征 + 站点类型做关键词搜索。先看原图那张，原图拼图里没有近重复再看变体的。")
            L.append("")
            for e in baidu:
                head = f"**{e['variant']}**："
                if e["error"]:
                    L.append(f"- {head}百度出错（{e['error'][:80]}），没截到相似图片，不算搜过无果")
                elif not e["similar_n"]:
                    L.append(f"- {head}没截到相似图片（百度没给，或页面改版）；打开截图 `rev/{e['shot']}` 看有没有“相似图片”区")
                else:
                    sites = "、".join(f"{s} {n}" for s, n in e["similar_sites"][:8])
                    sheet = f"拼图 `rev/{e['similar_sheet']}`（前 {min(24, e['similar_n'])} 张）" if e["similar_sheet"] else "没有拼图"
                    note = f"；{e['similar_note']}" if e["similar_note"] else ""
                    L.append(f"- {head}{e['similar_n']} 张（{sites}）；{sheet}{note}；来源列表 `rev/{e['json']}` 的 `similar`")
            L.append("")
        L.append("### 分级计票（同一引擎多个变体说同一城算一票；具体地点互相矛盾不抵消城市票）")
        L.append("")
        if votes["city"]:
            for t, engs in sorted(votes["city"].items(), key=lambda kv: -len(kv[1])):
                L.append(f"- 城市级 **{t}**：{len(engs)} 票（{', '.join(engs)}）")
        else:
            L.append("- 城市级：没有")
        if votes["place"]:
            for t, srcs in sorted(votes["place"].items(), key=lambda kv: -len(kv[1])):
                L.append(f"- 具体地点 **{t}**：{len(srcs)} 次（{', '.join(srcs)}）→ `poi.py \"{t}\" --city <城市>` 落坐标，同名全列出再核")
        else:
            L.append("- 具体地点级：没有")
        L.append("")
        L.append("### 每张图每个引擎")
        L.append("")
        for e in entries:
            L.append(f"**{e['variant']} / {e['engine']}**（截图 `rev/{e['shot']}`，务必打开看）")
            if e["similar_sheet"]:
                L.append(f"- 相似图片 {e['similar_n']} 张，拼图 `rev/{e['similar_sheet']}`（见上）")
            for g in e["guess"]:
                L.append(f"- 标签：{g[:200]}")
            for ln in e["links"][:8]:
                L.append(f"- [{ln.get('site', '')}] {ln.get('title', '')[:80]} — {ln.get('url', '')[:100]}")
            L.append("")
    L += ["## 产出文件", "", f"- 边缘图：`edges/`（{len(list((out / 'edges').glob('*')))} 张，四边四角逐张看）",
          f"- 变体：`variants/`（{len(list((out / 'variants').glob('*')))} 张）", "- OCR 标注图：`ocr.png`" if not args.no_ocr else "",
          f"- 识图截图：`rev/`（{len(list(rev_dir.glob('*.png'))) if rev_dir.exists() else 0} 张）" if not args.no_rev else "",
          f"- 百度相似图拼图：`rev/*_baidu_similar.jpg`（{len(list(rev_dir.glob('*_baidu_similar.jpg'))) if rev_dir.exists() else 0} 张）" if not args.no_rev else "", "",
          "## 状态", ""]
    for k, v in status.items():
        L.append(f"- {k}: {v}")
    L += ["", "接下来：把线索登记到 board.py（`clue`），查表线索用 `apply`；候选先列全（`children`）再排。"]
    (out / "intake.md").write_text("\n".join(x for x in L if x is not None))
    (out / "intake.json").write_text(json.dumps({"photo": str(photo), "exif": exif_json, "ocr": ocr_items, "rev": entries, "votes": votes,
                                                 "status": status, "timings": timings}, ensure_ascii=False, indent=1))
    print("\n".join(L[:6]))
    print(f"-> {out / 'intake.md'}（读这份）")


if __name__ == "__main__":
    main()
