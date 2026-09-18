#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright", "pillow"]
# ///
"""以图搜图 + 中文关键词搜索：无头 Chrome 打开搜索引擎，保存结果截图，提取猜测文字和链接。

  revimg.py <图片> [<图片> ...] --out-dir rev/ [--engines baidu,yandex]      以图搜图
  revimg.py --query "关键词" [--query ...] --out-dir q/ [--text-engines bing,baiduimg,sogouimg]   关键词搜索

以图搜图：
- baidu：国内主力。中文网页、微博、百家号、电商、景区内容覆盖最好；会给一句"图中可能是…"。直连。
  "相似图片"卡片不是链接，从页面发出的 pcsimi 请求里截获（滚动几次多拿几页），按 contsign 去重后写进 JSON 的 `similar`，
  前 --similar-sheet 张下载拼成带编号的 `<名>_baidu_similar.jpg`（第一格是查询图）：同一物体/场景的近重复照片是最快的定位路径，务必打开看。
- yandex：建筑、街景、外国内容补充；给"Image appears to contain"标签和来源网站。需要代理（--proxy）。
- Google Lens 从服务器出口会被要求人机验证，脚本不做；有浏览器操作工具（如 Claude in Chrome）时在用户自己的浏览器里搜，见 references/search.md。

关键词搜索（通用网页搜索工具搜中文国内内容常常无效时用）：
- bing：必应国内版网页结果（标题 + 链接），直连。
- baiduimg / sogouimg：百度图片、搜狗图片的结果页截图，看同类场景照片。
- 百度网页搜索会弹安全验证，不做。

每项输出 `<名>_<引擎>.png`（结果页截图，务必打开看）和 `.json`（猜测文字 + 链接；百度另有 `similar` 和相似图拼图）。
以图搜图前先用 `imgprep.py variants` 做紧裁 / 翻转 / 去色偏几个版本，逐个搜——整图搜不到很正常。
依赖本机 Google Chrome（没有就先 `uvx playwright install chromium`）。

示例：
  revimg.py photo.jpg --out-dir rev/
  revimg.py v/left_crop.jpg v/left_flip.jpg --out-dir rev/ --engines baidu
  revimg.py photo.jpg --out-dir rev/ --engines yandex --proxy socks5://127.0.0.1:10808（示例）
  revimg.py --query "蓝色拱形顶棚 人行天桥" --query "<城市> 出租车 颜色" --out-dir q/
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import sys
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qs, urlparse

OWN = {"baidu": ("baidu.com", "bdimg.com", "bdstatic.com"), "yandex": ("yandex.", "ya.ru", "yastatic.net"),
       "bing": ("bing.com", "bing.net", "microsoft.com"), "baiduimg": ("baidu.com", "bdimg.com", "bdstatic.com"),
       "sogouimg": ("sogou.com", "sogoucdn.com")}
BAIDU_REFUSED = ("功能优化中", "建议您重新上传其他图片")
TEXT_URL = {"bing": "https://cn.bing.com/search?q={q}", "baiduimg": "https://image.baidu.com/search/index?tn=baiduimage&word={q}",
            "sogouimg": "https://pic.sogou.com/pics?query={q}"}
_direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 百度缩略图必须直连
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"


async def _collect(page, engine: str) -> dict:
    text = await page.evaluate("document.body ? document.body.innerText : ''")
    links = await page.evaluate("""() => [...document.querySelectorAll('a[href^="http"]')]
        .map(a => ({t: (a.innerText || a.title || '').trim().replace(/\\s+/g, ' ').slice(0, 120), h: a.href}))
        .filter(x => x.t.length >= 4)""")
    seen, out = set(), []
    for ln in links:
        host = urlparse(ln["h"]).netloc
        if any(o in host for o in OWN[engine]) or ln["h"] in seen:
            continue
        seen.add(ln["h"])
        out.append({"title": ln["t"], "url": ln["h"], "site": host})
    lines = [s.strip() for s in text.splitlines() if s.strip()]
    guess = [s for s in lines if s.startswith("图中可能是") or "appears to contain" in s.lower()]
    if engine == "yandex" and guess:            # 标签在"appears to contain"下一行起的几行
        i = lines.index(guess[0])
        guess = [guess[0] + "：" + " / ".join(lines[i + 1:i + 8])]
    return {"url": page.url, "guess": guess, "links": out[:25], "text_head": "\n".join(lines[:60])[:2500]}


def _site(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    for pre in ("www.", "m.", "wap.", "mobile."):
        if host.startswith(pre) and host.count(".") > 1:
            return host[len(pre):]
    return host


def _font(size: int):
    from PIL import ImageFont

    for p in ("/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:  # noqa: BLE001
            continue
    return ImageFont.load_default()


def _similar_sheet(query: Path, items: list[dict], out: Path, cols: int = 5, tile: int = 300) -> int:
    """查询图 + 前 N 张相似图缩略图 → 编号拼图（编号 = similar 数组下标）。返回下载成功的张数。"""
    from PIL import Image, ImageDraw

    def fetch(url: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://graph.baidu.com/"})
            return Image.open(io.BytesIO(_direct.open(req, timeout=15).read())).convert("RGB")
        except Exception:  # noqa: BLE001
            return None

    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(fetch, [it["thumb"] for it in items]))
    try:
        q = Image.open(query).convert("RGB")
    except Exception:  # noqa: BLE001
        q = None
    tiles = [(q, "查询图", "cyan")] + [
        (im, f"{i:02d} {it['site'] or '?'}", "yellow") for i, (it, im) in enumerate(zip(items, ims))]
    bar = 24
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new("RGB", (cols * tile, rows * (tile + bar)), (40, 40, 40))
    d = ImageDraw.Draw(S)
    f = _font(17)
    for k, (im, label, color) in enumerate(tiles):
        x, y = (k % cols) * tile, (k // cols) * (tile + bar)
        d.rectangle([x, y, x + tile - 1, y + bar - 1], fill="black")
        d.text((x + 4, y + 2), label[:30], fill=color, font=f)
        if im is None:
            d.text((x + 10, y + bar + tile // 2), "下载失败", fill="gray", font=f)
            continue
        im.thumbnail((tile - 4, tile - 4))
        S.paste(im, (x + (tile - im.width) // 2, y + bar + (tile - im.height) // 2))
    S.save(out, quality=88)
    return sum(im is not None for im in ims)


async def _baidu(ctx, img: Path, shot: Path, similar_pages: int = 2, sheet_n: int = 24) -> dict:
    page = await ctx.new_page()
    simi: list = []                                   # "相似图片"卡片不在 DOM 链接里，来自 ajax/pcsimi 响应

    async def grab(resp):
        try:
            data = (await resp.json()).get("data") or {}
            simi.append((int(parse_qs(urlparse(resp.url).query).get("page", ["0"])[0] or 0), data.get("list") or []))
        except Exception:  # noqa: BLE001
            simi.append((0, []))

    pending: list = []
    page.on("response", lambda r: pending.append(asyncio.ensure_future(grab(r))) if "graph.baidu.com/ajax/pcsimi" in r.url else None)
    await page.goto("https://graph.baidu.com/pcpage/index?tpl_from=pc", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2000)
    inp = await page.query_selector("input[type=file]")
    if not inp:
        await page.screenshot(path=str(shot))
        return {"error": "没找到上传入口（页面改版或被拦截），看截图"}
    await inp.set_input_files(str(img))
    for _ in range(60):
        await page.wait_for_timeout(500)
        if "graph.baidu.com/s" in page.url:
            break
    await page.wait_for_timeout(4500)
    await page.screenshot(path=str(shot), full_page=True, clip={"x": 0, "y": 0, "width": 1400, "height": 3200})
    res = await _collect(page, "baidu")
    misses, got = 0, 0                                # 滚到底触发下一页；连续两次没新页就停
    while got < similar_pages and misses < 2 and pending:
        n0 = len(pending)
        await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        for _ in range(16):
            await page.wait_for_timeout(250)
            if len(pending) > n0:
                break
        got, misses = (got + 1, 0) if len(pending) > n0 else (got, misses + 1)
    await asyncio.gather(*pending)
    await page.close()
    seen, similar = set(), []
    for _, lst in sorted(simi, key=lambda t: t[0]):
        for it in lst:
            key = it.get("contsign") or it.get("thumbUrl")
            if not it.get("thumbUrl") or key in seen:
                continue
            seen.add(key)
            similar.append({"thumb": it["thumbUrl"], "from": it.get("fromUrl") or "", "site": _site(it.get("fromUrl") or "")})
    res["similar"] = similar
    if similar and sheet_n > 0:
        sheet = shot.with_name(shot.stem + "_similar.jpg")
        ok = await asyncio.to_thread(_similar_sheet, img, similar[:sheet_n], sheet)
        res["similar_sheet"] = str(sheet)
        if ok < min(sheet_n, len(similar)):
            res["similar_sheet_note"] = f"缩略图下载失败 {min(sheet_n, len(similar)) - ok} 张"
    if not res["guess"] and any(w in res["text_head"] for w in BAIDU_REFUSED):
        res["error"] = "百度拒绝处理这张图（\"功能优化中\"页面），不算搜过无果：换个裁剪、稍后重试，或只用 Yandex"
    return res


async def _yandex(ctx, img: Path, shot: Path) -> dict:
    page = await ctx.new_page()
    await page.goto("https://yandex.com/images/search?rpt=imageview", wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)
    inp = await page.query_selector("input[type=file]")
    if not inp:
        await page.screenshot(path=str(shot))
        return {"error": "没找到上传入口（可能被要求验证），看截图"}
    await inp.set_input_files(str(img))
    for _ in range(60):
        await page.wait_for_timeout(500)
        if "url=" in page.url or "cbir_id" in page.url:
            break
    await page.wait_for_timeout(4500)
    for label in ("Allow essential cookies", "Only essential", "Accept essential", "Allow all", "Accept all"):
        try:                                            # cookie 弹窗会盖住截图右下角
            btn = page.get_by_role("button", name=label)
            if await btn.count():
                await btn.first.click(timeout=2000)
                await page.wait_for_timeout(800)
                break
        except Exception:  # noqa: BLE001
            continue
    await page.screenshot(path=str(shot), full_page=True, clip={"x": 0, "y": 0, "width": 1400, "height": 3200})
    res = await _collect(page, "yandex")
    await page.close()
    return res


async def _text(ctx, engine: str, query: str, shot: Path) -> dict:
    from urllib.parse import quote

    page = await ctx.new_page()
    await page.goto(TEXT_URL[engine].format(q=quote(query)), wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(3500)
    head = await page.evaluate("document.body ? document.body.innerText.slice(0, 400) : ''")
    if "安全验证" in head or "captcha" in page.url.lower():
        await page.screenshot(path=str(shot))
        await page.close()
        return {"error": "被要求人机验证（不要绕），换一个引擎"}
    await page.screenshot(path=str(shot), full_page=True, clip={"x": 0, "y": 0, "width": 1400, "height": 3000})
    if engine == "bing":
        rows = await page.evaluate("""() => [...document.querySelectorAll('li.b_algo')].map(li => ({
            t: (li.querySelector('h2') || {}).innerText || '',
            h: (li.querySelector('h2 a') || {}).href || '',
            site: (li.querySelector('cite') || {}).innerText || '',
            s: ((li.querySelector('.b_caption p, .b_lineclamp2, .b_lineclamp3, .b_paractl') || {}).innerText || '').slice(0, 200)}))""")
        links = [{"title": r["t"].strip(), "url": r["h"], "site": r["site"].strip()[:80], "snippet": r["s"].strip()} for r in rows if r["t"]]
        res = {"url": page.url, "guess": [], "links": links[:20], "text_head": ""}
    else:
        res = await _collect(page, engine)
    await page.close()
    return res


async def run(images: list[Path], engines: list[str], out_dir: Path, proxy: str | None,
              queries: list[str] | None = None, text_engines: list[str] | None = None,
              similar_pages: int = 2, sheet_n: int = 24) -> list[dict]:
    from playwright.async_api import async_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    async with async_playwright() as p:
        async def browser(use_proxy: bool):
            kw = {"headless": True, "args": ["--disable-blink-features=AutomationControlled"]}
            if use_proxy and proxy:
                kw["proxy"] = {"server": proxy.replace("socks5h://", "socks5://")}
            else:
                kw["args"].append("--no-proxy-server")
            try:
                return await p.chromium.launch(channel="chrome", **kw)
            except Exception:  # noqa: BLE001
                return await p.chromium.launch(**kw)

        if queries:
            b = await browser(use_proxy=False)
            ctx = await b.new_context(viewport={"width": 1400, "height": 1000}, locale="zh-CN")
            for k, q in enumerate(queries):
                for eng in text_engines or []:
                    shot = out_dir / f"q{k + 1:02d}_{eng}.png"
                    try:
                        res = await _text(ctx, eng, q, shot)
                    except Exception as e:  # noqa: BLE001
                        res = {"error": str(e)[:300]}
                    res.update({"query": q, "engine": eng, "screenshot": str(shot), "image": f"q{k + 1:02d}"})
                    (out_dir / f"q{k + 1:02d}_{eng}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
                    results.append(res)
            await b.close()

        for eng in engines if images else []:
            b = await browser(use_proxy=(eng == "yandex"))
            ctx = await b.new_context(viewport={"width": 1400, "height": 1000},
                                      locale="zh-CN" if eng == "baidu" else "en-US")
            stems = [i.stem for i in images]
            for k, img in enumerate(images):
                name = img.stem if stems.count(img.stem) == 1 else f"{k + 1:02d}_{img.stem}"
                shot = out_dir / f"{name}_{eng}.png"
                try:
                    res = await (_baidu(ctx, img, shot, similar_pages, sheet_n) if eng == "baidu" else _yandex(ctx, img, shot))
                except Exception as e:  # noqa: BLE001
                    res = {"error": str(e)[:300]}
                res.update({"image": str(img), "engine": eng, "screenshot": str(shot)})
                (out_dir / f"{name}_{eng}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
                results.append(res)
            await b.close()
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--engines", default="baidu,yandex", help="以图搜图引擎")
    ap.add_argument("--query", action="append", help="关键词搜索，可重复")
    ap.add_argument("--text-engines", default="bing,baiduimg,sogouimg", help="关键词搜索引擎")
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"), help="Yandex 用，如 socks5://127.0.0.1:10808（示例）")
    ap.add_argument("--exclude", help="逗号分隔的排除词：标题含这些词的结果不列出（例如盲测时屏蔽题目出处）")
    ap.add_argument("--similar-pages", type=int, default=2, help="百度相似图片首页之外再滚动加载几页（每页约 30 张）")
    ap.add_argument("--similar-sheet", type=int, default=24, help="前几张相似图下载拼图，0 不拼")
    args = ap.parse_args()
    excl = [w for w in (args.exclude or "").split(",") if w]
    if not args.images and not args.query:
        ap.error("给图片路径做以图搜图，或用 --query 做关键词搜索")
    missing = [str(p) for p in args.images if not p.is_file()]
    if missing:
        ap.error("图片不存在：" + "、".join(missing))
    engines = [e for e in args.engines.split(",") if e in ("baidu", "yandex")]
    text_engines = [e for e in args.text_engines.split(",") if e in TEXT_URL]
    if args.images and "yandex" in engines and not args.proxy:
        print("提示：国内直连 Yandex 通常不通，建议加 --proxy socks5://127.0.0.1:10808（示例）", file=sys.stderr)
    for r in asyncio.run(run(args.images, engines, args.out_dir, args.proxy, args.query, text_engines,
                             args.similar_pages, args.similar_sheet)):
        head = f"[{r['engine']}] {r['query'] if r.get('query') else Path(r['image']).name}"
        if r.get("error"):
            print(f"{head}  出错：{r['error']}  截图 {r['screenshot']}")
            continue
        print(f"{head}  截图 {r['screenshot']}")
        for g in r["guess"][:2]:
            print(f"   猜测：{g[:160]}")
        links = [ln for ln in r["links"] if not any(w in ln["title"] for w in excl)]
        if excl and (len(links) < len(r["links"]) or any(w in r.get("text_head", "") for w in excl)):
            print(f"   注意：结果里出现了排除词，已隐藏 {len(r['links']) - len(links)} 条；截图里仍可能看到")
        for ln in links[:8]:
            print(f"   - {ln['title'][:60]}  ({ln['site']})")
        if r.get("similar"):
            tally = "、".join(f"{s} {n}" for s, n in Counter(x["site"] for x in r["similar"]).most_common(6))
            print(f"   相似图片 {len(r['similar'])} 张（{tally}）" + (f"  拼图 {r['similar_sheet']}（打开找同一物体/场景）" if r.get("similar_sheet") else ""))
        elif r["engine"] == "baidu":
            print("   相似图片：没截到")


if __name__ == "__main__":
    main()
