#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pyobjc-framework-Vision; sys_platform == 'darwin'", "pyobjc-framework-Quartz; sys_platform == 'darwin'", "rapidocr-onnxruntime"]
# ///
"""读照片里的文字（第二读者）：整图、放大、切块各跑一遍，合并去重，标出哪些字只有放大后才读得出。

后端：macOS 用 Apple Vision（本机、免下载、中英日韩都行），其他系统或 Vision 不可用时用 RapidOCR。
放大或切块后才读出来的字（pass = up / tile）只是假设，要回原图放大看一眼。

  ocr.py photo.jpg [--langs zh-Hans,en] [--upscale 2] [--tiles 2x2] [--min-conf 0.3] [--out ocr.json] [--draw ocr.png]

示例：
  ocr.py photo.jpg --out ocr.json --draw ocr.png
  ocr.py photo.jpg --langs zh-Hans,zh-Hant,en,ja --tiles 3x3 --upscale 3     # 远处小字多时切细一点、放大一点
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def _iou(a, b) -> float:
    x0, y0, x1, y1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


class VisionOCR:
    name = "apple-vision"

    def __init__(self, langs: list[str]):
        import Quartz  # noqa: F401
        import Vision
        self.Vision = Vision
        self.langs = langs

    def run(self, im: Image.Image) -> list[dict]:
        import io
        from Foundation import NSData
        Vision = self.Vision
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="PNG")
        data = NSData.dataWithBytes_length_(buf.getvalue(), len(buf.getvalue()))
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(False)      # 别把专名"纠正"掉
        try:
            req.setRecognitionLanguages_(self.langs)
        except Exception:  # noqa: BLE001
            pass
        ok, err = handler.performRequests_error_([req], None)
        if not ok:
            raise RuntimeError(f"Vision 失败：{err}")
        W, H = im.size
        out = []
        for obs in req.results() or []:
            cand = obs.topCandidates_(1)
            if not cand:
                continue
            text = str(cand[0].string())
            conf = float(cand[0].confidence())
            bb = obs.boundingBox()          # 归一化，原点左下
            x, y, w, h = bb.origin.x, bb.origin.y, bb.size.width, bb.size.height
            out.append({"text": text, "conf": round(conf, 3), "box": [int(x * W), int((1 - y - h) * H), int((x + w) * W), int((1 - y) * H)]})
        return out


class RapidOCRBackend:
    name = "rapidocr"

    def __init__(self, langs: list[str]):
        from rapidocr_onnxruntime import RapidOCR
        self.ocr = RapidOCR()

    def run(self, im: Image.Image) -> list[dict]:
        import numpy as np
        res, _ = self.ocr(np.array(im.convert("RGB"))[:, :, ::-1])
        out = []
        for box, text, conf in res or []:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            out.append({"text": str(text), "conf": round(float(conf), 3), "box": [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]})
        return out


def backend(langs: list[str]):
    if sys.platform == "darwin":
        try:
            return VisionOCR(langs)
        except Exception as e:  # noqa: BLE001
            print(f"Apple Vision 不可用（{str(e)[:120]}），改用 RapidOCR", file=sys.stderr)
    try:
        return RapidOCRBackend(langs)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"没有可用的 OCR 后端：{e}")


def recognize(im: Image.Image, be, upscale: float, tiles: tuple[int, int], min_conf: float) -> list[dict]:
    W, H = im.size
    found: list[dict] = []

    def add(items, pass_name, ox=0, oy=0, scale=1.0):
        for it in items:
            if it["conf"] < min_conf or not it["text"].strip():
                continue
            b = it["box"]
            box = [int(ox + b[0] / scale), int(oy + b[1] / scale), int(ox + b[2] / scale), int(oy + b[3] / scale)]
            new = {"text": it["text"].strip(), "conf": it["conf"], "box": box, "pass": pass_name}
            for old in found:
                if _iou(old["box"], box) > 0.4:
                    if new["conf"] > old["conf"] + 0.05 or (len(new["text"]) > len(old["text"]) and new["conf"] >= old["conf"] - 0.1):
                        old.update(new)
                    break
            else:
                found.append(new)

    add(be.run(im), "full")
    if upscale and upscale > 1:
        big = im.resize((int(W * upscale), int(H * upscale)), Image.LANCZOS)
        add(be.run(big), "up", scale=upscale)
    r, c = tiles
    if r * c > 1:
        tw, th = W / c, H / r
        for i in range(r):
            for j in range(c):
                # 各块留一成重叠，免得字被切在边上
                x0, y0 = max(0, int(j * tw - tw * 0.1)), max(0, int(i * th - th * 0.1))
                x1, y1 = min(W, int((j + 1) * tw + tw * 0.1)), min(H, int((i + 1) * th + th * 0.1))
                s = max(upscale or 1, 2)
                crop = im.crop((x0, y0, x1, y1)).resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)
                add(be.run(crop), "tile", ox=x0, oy=y0, scale=s)
    found.sort(key=lambda t: -t["conf"])
    return found


def _where(box, W, H) -> str:
    cx, cy = (box[0] + box[2]) / 2 / W, (box[1] + box[3]) / 2 / H
    v = "上" if cy < 0.33 else ("下" if cy > 0.67 else "中")
    h = "左" if cx < 0.33 else ("右" if cx > 0.67 else "中")
    return f"{v}{h}" if v + h != "中中" else "中间"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--langs", default="zh-Hans,zh-Hant,en,ja,ko,fr,es,pt,de,it,ru,th,vi")
    ap.add_argument("--upscale", type=float, default=2)
    ap.add_argument("--tiles", default="2x2")
    ap.add_argument("--min-conf", type=float, default=0.3)
    ap.add_argument("--out")
    ap.add_argument("--draw")
    args = ap.parse_args()
    im = ImageOps.exif_transpose(Image.open(args.image))
    t0 = time.time()
    be = backend([x.strip() for x in args.langs.split(",") if x.strip()])
    r, c = (int(v) for v in args.tiles.lower().split("x"))
    found = recognize(im, be, args.upscale, (r, c), args.min_conf)
    W, H = im.size
    print(f"{be.name}：{len(found)} 条，{time.time() - t0:.1f}s（图 {W}×{H}）")
    print(f"{'置信':>5} {'来源':<5} {'位置':<4} 文字")
    for t in found:
        print(f"{t['conf']:>5.2f} {t['pass']:<5} {_where(t['box'], W, H):<4} {t['text']}")
    if any(t["pass"] != "full" for t in found):
        print("pass=up/tile 的字只有放大后才读出来，算假设：回原图放大看一眼再用")
    if args.out:
        Path(args.out).write_text(json.dumps({"image": args.image, "size": [W, H], "backend": be.name, "items": found}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.out}")
    if args.draw:
        d = ImageDraw.Draw(im)
        for t in found:
            col = "lime" if t["pass"] == "full" else "yellow"
            d.rectangle(t["box"], outline=col, width=2)
            d.text((t["box"][0], max(0, t["box"][1] - 12)), f"{t['text'][:20]} {t['conf']:.2f}", fill=col)
        im.save(args.draw)
        print(f"-> {args.draw}（绿=整图读出，黄=放大/切块读出）")


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
