#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pillow-heif"]
# ///
"""读照片元数据：GPS、拍摄时间、机型、焦距。定位前第一件事。

  exif.py <照片> [<照片> ...]

- 有 GPS：直接给出 WGS84 坐标和 GCJ-02 换算（高德/腾讯用），但仍要用画面核对（元数据能被改）。
- 有拍摄时间：可以喂给 sun.py（注意 EXIF 时间通常是拍摄地本地时间，不带时区，看 OffsetTime 字段）。
- 有 35mm 等效焦距：可以喂给 geo.py range / geometry.md 算视角，不用猜倍率。
- 微信、QQ、大多数社交平台转发会抹掉元数据；截图、翻拍没有元数据。输出为空是常态，不代表什么。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import ExifTags, Image

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:  # 没装 pillow-heif 时 HEIC 读不了，其它格式照常
    pass


def _deg(v, ref) -> float:
    d, m, s = (float(x) for x in v)
    val = d + m / 60 + s / 3600
    return -val if ref in ("S", "W") else val


def read(path: Path) -> dict:
    im = Image.open(path)
    ex = im.getexif()
    out: dict = {"file": str(path), "size": list(im.size)}
    base = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
    sub = {ExifTags.TAGS.get(k, k): v for k, v in ex.get_ifd(0x8769).items()}
    for k in ("Make", "Model", "Software"):
        if base.get(k):
            out[k.lower()] = str(base[k]).strip("\x00 ")
    for k in ("DateTimeOriginal", "OffsetTimeOriginal"):
        if sub.get(k):
            out[k] = str(sub[k])
    if not out.get("DateTimeOriginal") and base.get("DateTime"):
        out["DateTime"] = str(base["DateTime"])
    if sub.get("FocalLengthIn35mmFilm"):
        out["focal_35mm"] = int(sub["FocalLengthIn35mmFilm"])
        lf, sf = geo.fov_from_equiv_focal(out["focal_35mm"])
        out["fov_4x3_long_short"] = [round(lf, 1), round(sf, 1)]
    elif sub.get("FocalLength"):
        out["focal_mm_actual"] = float(sub["FocalLength"])
    g = ex.get_ifd(0x8825)
    if g and 2 in g and 4 in g:
        lat, lon = _deg(g[2], g.get(1, "N")), _deg(g[4], g.get(3, "E"))
        out["gps_wgs84"] = [round(lat, 7), round(lon, 7)]
        out["gps_gcj02"] = [round(x, 7) for x in geo.convert(lat, lon, "wgs", "gcj")]
        if 6 in g:
            out["altitude_m"] = round(float(g[6]), 1)
        if 17 in g:
            out["image_direction_deg"] = round(float(g[17]), 1)   # 部分手机会写镜头朝向
    return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        try:
            print(json.dumps(read(Path(p)), ensure_ascii=False))
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"file": p, "error": str(e)}, ensure_ascii=False))


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
