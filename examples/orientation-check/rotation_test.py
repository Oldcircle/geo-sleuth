#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pillow-heif", "numpy", "torch", "transformers", "opencv-python-headless", "socksio", "pysocks", "requests"]
# ///
"""How much do rotation and tilt of the query change match.py's ranking?

Takes 6 queries from the candidate folder itself, transforms each query, and reports the rank at which it
finds its own original among all candidates (1 = found itself). The last case stores the pixels sideways
with EXIF Orientation=6, as a phone held upright does, and opens the file the way this version of match.py
opens --query.

Usage: python rotation_test.py <scripts dir> <candidate dir> <out json>
Needs the match.py dependencies and downloads DINOv2 and CLIP on first use.
"""
import tempfile
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

scripts, cand_dir, out = sys.argv[1:4]
sys.path.insert(0, scripts)
import match  # noqa: E402

files = sorted(Path(cand_dir).glob("*.jpg"))
if len(files) < 6:
    sys.exit("needs a folder of candidate JPEGs (the README numbers used 540)")
ims = [Image.open(f).convert("RGB") for f in files]
queries = [files.index(f) for f in files[::90][:6]]


def tilt(im, deg):
    """Rotate by deg and crop the largest centered box without black corners."""
    w, h = im.size
    r = im.rotate(deg, resample=Image.BICUBIC, expand=False)
    a = abs(np.radians(deg))
    s = min(w, h) / (abs(np.cos(a)) + abs(np.sin(a)) * max(w, h) / min(w, h))
    cw, ch = int(s * w / min(w, h)), int(s * h / min(w, h))
    return r.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2))


def exif_sideways(im):
    """Pixels rotated 90° clockwise, Orientation=6 (what a phone held upright writes)."""
    ex = Image.Exif()
    ex[0x0112] = 6
    path = Path(tempfile.gettempdir()) / "rotation_test_sideways.jpg"
    im.transpose(Image.Transpose.ROTATE_90).save(path, format="JPEG", quality=95, exif=ex)
    loader = getattr(match, "open_photo", None)        # the way this version of match.py opens --query
    return loader(path, "query") if loader else Image.open(path)


variants = {
    "upright": lambda im: im,
    "tilt 5°": lambda im: tilt(im, 5),
    "tilt 15°": lambda im: tilt(im, 15),
    "rotated 90°": lambda im: im.rotate(90, expand=True),
    "upside down": lambda im: im.rotate(180),
    "mirrored": lambda im: im.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
    "EXIF sideways, opened like --query": lambda im: exif_sideways(im),
}

res = {"candidates": len(files), "queries": [files[q].name for q in queries]}
for method in ("dino", "clip"):
    emb = match.Embedder(method)
    cf = emb.embed(ims, multi=True)
    for name, fn in variants.items():
        ranks = []
        for q in queries:
            qf = emb.embed([fn(ims[q])], multi=True)[0]
            sims = (cf @ qf.T).max(axis=(1, 2))
            ranks.append(int((sims > sims[q]).sum()) + 1)
        res[f"{method} | {name}"] = ranks
        print(method, name, ranks, flush=True)
Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
