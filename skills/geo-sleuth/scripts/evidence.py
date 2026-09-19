#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""出证据图：卫星图上标拍摄点、朝向扇形、关键地物，下面拼街景对比图。

输入一个 JSON 描述文件：
{
  "map": "area.jpg",                         # tiles.py fetch 的输出（旁边要有同名 .json）
  "crop": [x0, y0, x1, y1],                  # 可选，按原图像素裁剪
  "width": 1280,                             # 输出宽度
  "camera": [lat, lon],
  "heading": 52, "hfov": 54, "range_m": 560, # 朝向扇形
  "labels": [{"at": [lat, lon], "text": "星河双子塔", "color": "#ffdd55", "dx": 0, "dy": 0}],
  "lines":  [{"from": [lat, lon], "bearing": 47, "length_m": 75, "color": "#00ffff"}],
  "panels": [{"image": "sv1.jpg", "caption": "街景：同一条路朝东北看"}]
}

示例：evidence.py spec.json --out evidence.jpg
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402
from baidu_pano import _font  # noqa: E402
from tiles import Mosaic  # noqa: E402


def build(spec: dict, base: Path, out: Path) -> None:
    map_path = base / spec["map"]
    m = Mosaic(map_path)
    im = Image.open(map_path).convert("RGBA")
    scale_font = max(im.size) / 1400

    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    if "camera" in spec:
        cam = tuple(spec["camera"])
        if "heading" in spec:
            h, fov, rng = spec["heading"], spec.get("hfov", 54), spec.get("range_m", 400)
            pts = [m.to_px(*cam)] + [m.to_px(*geo.dest(cam, h - fov / 2 + k * fov / 24, rng)) for k in range(25)]
            d.polygon(pts, fill=(255, 220, 0, 55), outline=(255, 220, 0, 210))
    for ln in spec.get("lines", []):
        a = m.to_px(*ln["from"])
        b = m.to_px(*geo.dest(tuple(ln["from"]), ln["bearing"], ln["length_m"]))
        d.line([a, b], fill=ln.get("color", "#00ffff"), width=int(8 * scale_font) or 3)
    if "camera" in spec:
        x, y = m.to_px(*spec["camera"])
        r = 18 * scale_font
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 40, 40, 255), outline="white", width=4)
    im = Image.alpha_composite(im, ov).convert("RGB")

    d = ImageDraw.Draw(im)
    f = _font(int(42 * scale_font))
    for lb in spec.get("labels", []):
        ax, ay = m.to_px(*lb["at"])
        r = 8 * scale_font
        d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=lb.get("color", "white"), outline="black")   # 锚点
        x, y = ax + lb.get("dx", 12), ay + lb.get("dy", -12)
        bb = d.textbbox((0, 0), lb["text"], font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = min(max(8, x), im.size[0] - tw - 16)                                                   # 不出图边
        y = min(max(8, y), im.size[1] - th - 16)
        d.rectangle([x - 8, y - 6, x + tw + 8, y + th + 10], fill="black")
        d.text((x, y), lb["text"], font=f, fill=lb.get("color", "white"))

    if spec.get("crop"):
        im = im.crop(tuple(spec["crop"]))
    W = spec.get("width", 1280)
    im = im.resize((W, int(im.size[1] * W / im.size[0])))

    panels = spec.get("panels", [])
    if panels:
        pw = W // len(panels)
        ph = int(pw * 3 / 4)
        cf = _font(20)
        lines_per = []
        for p in panels:                                   # 说明文字按格宽折行，不和隔壁格重叠
            cap, cur, lines = p.get("caption", ""), "", []
            for ch in cap:
                if cf.getlength(cur + ch) > pw - 12:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
            lines_per.append(lines[:3])
        cap_h = 10 + 26 * max(len(x) for x in lines_per)
        S = Image.new("RGB", (W, im.size[1] + ph + cap_h), "black")
        S.paste(im, (0, 0))
        d = ImageDraw.Draw(S)
        for k, (p, lines) in enumerate(zip(panels, lines_per)):
            pim = Image.open(base / p["image"]).convert("RGB")
            pim.thumbnail((pw, ph))                        # 保持纵横比，居中留黑边
            S.paste(pim, (k * pw + (pw - pim.width) // 2, im.size[1] + cap_h + (ph - pim.height) // 2))
            for li, text in enumerate(lines):
                d.text((k * pw + 6, im.size[1] + 6 + 26 * li), text, font=cf, fill="white")
        im = S
    im.save(out, quality=88)



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    build(json.loads(args.spec.read_text(encoding="utf-8")), args.spec.parent, args.out)
    print(args.out)


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
