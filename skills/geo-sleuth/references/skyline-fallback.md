# Skyline fallback: when `terrain.py ridge` misses the ridge

`terrain.py ridge` finds the sky→mountain brightness drop column by column. It works on clear skies; it breaks where cloud sits on the peaks, snow meets a pale sky, or haze flattens the contrast, and then it follows the cloud edge and `fit` never brings the residual down. Always look at `ridge --png` before fitting. If the yellow dots leave the real ridge, work down this list and stop at the first step that puts them back.

## 1. Tune the default detector

- `--ymin ROW` skips a cloud band above the ridge; `--ymax ROW` skips foreground (trees, roofs, a car) that rises into the search.
- `--x0/--x1` keeps only the clean stretch. A shorter correct ridge beats a longer wrong one.
- `--drop/--k/--hold` loosen or tighten the brightness test (lower `--drop` for haze).

## 2. Drop the bad points

When most points are right and a few columns follow cloud, delete those points from `ridge.json` and pass the file back with `--points ridge.json` (it reads the `ridge` list). Leave the gap; don't move points to where you guess the ridge is.

## 3. Learned detector (optional, needs the hardware below)

[Crestline](https://github.com/ExtReMLapin/crestline) by @ExtReMLapin is a U-Net (ConvNeXt-Base) that segments sky, skyline and inner ridges. On clear skies it matches the default detector to 1–2 px; on snow ranges with cloud it cut the error 2–4× in our tests, and the true camera position ranked as well as or better than with a hand-traced ridge. Weights: [`LPN64/crestline-convnext-base`](https://huggingface.co/LPN64/crestline-convnext-base), CC BY-SA 4.0, downloaded at run time (185 MB, pinned revision below), not shipped with this skill. Trained on Swiss Alps photos only.

**Hardware.** No GPU is required. Long side 1024 px, fp32:

| Device | Peak memory | Time per photo | Source |
|---|---|---|---|
| Apple Silicon, CPU | 3.2–3.9 GB RAM | 6–10 s | measured |
| Apple Silicon, MPS | ~1.3 GB process + ~1.4 GB GPU (shared memory) | < 1 s | measured |
| NVIDIA GPU | ~0.85 GB VRAM | | reported by the author |
| x86 Linux CPU | under 2.1 GB (2.1 GB at 1536 px) | | reported by the author |

- A machine with 8 GB RAM runs it on CPU. With less free memory, add `--bf16`: same output, ~1.7 GB on Apple CPU, but 3–6× slower. Don't use fp16.
- Keep the long side at 1024: the model was trained at ~1024 px wide; 1536 px needs 4–7 GB on macOS CPU and is no more accurate.
- First run also installs torch (already present if you have run `match.py`).

Save this as `crestline_skyline.py` in your working directory and run `uv run crestline_skyline.py photo.jpg crest.json [--step 20] [--device auto|cpu|mps|cuda] [--bf16]`:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["torch", "segmentation-models-pytorch>=0.5", "timm", "safetensors", "huggingface_hub", "pillow", "numpy"]
# ///
"""Crestline skyline -> [[x,y],...] in original pixels, for terrain.py ridge --points."""
import argparse, json
import numpy as np, torch, torch.nn.functional as F
from PIL import Image, ImageOps
import segmentation_models_pytorch as smp
from safetensors.torch import load_file
from huggingface_hub import snapshot_download

REPO, REV = "LPN64/crestline-convnext-base", "3e12157a349088dfc8824ff3ddab65ea265fa2f1"
ap = argparse.ArgumentParser()
ap.add_argument("photo"); ap.add_argument("out")
ap.add_argument("--step", type=int, default=20)
ap.add_argument("--device", default="auto")
ap.add_argument("--bf16", action="store_true")
a = ap.parse_args()
dev = a.device if a.device != "auto" else "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
dt = torch.bfloat16 if a.bf16 else torch.float32
wdir = snapshot_download(REPO, revision=REV, allow_patterns=["config.json", "model.safetensors"])
cfg = json.load(open(f"{wdir}/config.json"))
model = smp.Unet(cfg["encoder"], encoder_weights=None, classes=3)
model.load_state_dict({k: v.float() for k, v in load_file(f"{wdir}/model.safetensors").items()})
model = model.to(dev, dt).eval()

img = ImageOps.exif_transpose(Image.open(a.photo)).convert("RGB"); W0, H0 = img.size
img.thumbnail((1024, 1024), Image.LANCZOS)  # downscale only
x = ((np.asarray(img, np.float32) / 255 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]).astype(np.float32)
x = torch.from_numpy(x).permute(2, 0, 1)[None].to(dev)
h, w = x.shape[-2:]
x = F.pad(x, (0, -w % 32, 0, -h % 32), mode="reflect").to(dt)
with torch.no_grad():
    prob = torch.sigmoid(model(x).float())[0, :, :h, :w].cpu().numpy()  # sky, skyline, inner ridges

rows = np.argmin(np.vstack([prob[0] > 0.5, np.zeros((1, w), bool)]), axis=0)  # first non-sky row
r, cols = np.clip(rows, 0, h - 1), np.arange(w)
conf = np.stack([prob[1][np.clip(r + d, 0, h - 1), cols] for d in range(-3, 4)]).max(0)
conf = np.convolve(np.pad(conf, 7, mode="edge"), np.ones(15) / 15, "valid")  # edge pad keeps border columns
ok = (rows > 0) & (rows < h) & (conf >= 0.6)
pts, dropped = [], []
for X in range(0, W0, a.step):
    u = min(int((X + 0.5) * w / W0), w - 1)
    (pts.append([X, round((rows[u] + 0.5) * H0 / h - 0.5)]) if ok[u] else dropped.append(X))
json.dump(pts, open(a.out, "w"))
print(f"{len(pts)} points; {len(dropped)} low-confidence columns dropped: {dropped}")
```

Then `terrain.py ridge photo.jpg --points crest.json --png check.png [--hrow ROW ...] --out ridge.json` as usual.

**Known failure: cloud on a peak.** The model then traces the top of the cloud (15–36 px too high in our tests), and the confidence check drops only a few of those columns. Check `--png` at every peak with cloud and remove those points (step 2).

## 4. Hand-pick points (last resort)

`--points "x,y;x,y;..."` on the stretches where the real ridge is visible. Skip columns hidden by cloud or haze: in one real case, tracing through cloud put the points on the cloud edge and the residual never came down. For a near range in front of a far one, also use `--near` (`geometry.md` 7.4).
