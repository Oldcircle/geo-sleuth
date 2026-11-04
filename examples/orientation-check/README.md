# Orientation check: does a sideways-stored photo still find itself?

The reproducer from [#29](https://github.com/Oldcircle/geo-sleuth/issues/29). A phone held upright stores the pixels sideways and writes EXIF `Orientation=6`; image viewers turn it upright, and since stage 2 of the shared image loading, so do the scripts.

`rotation_test.py` takes 6 queries from a candidate folder, transforms each one, and reports the rank at which it finds its own original among all candidates (1 = found itself). The last case stores the query sideways with `Orientation=6` and opens it the way the given version of `match.py` opens `--query`.

## Run it

From the repository root, with any folder of candidate JPEGs (downloads DINOv2 and CLIP on first use):

```bash
uv run examples/orientation-check/rotation_test.py skills/geo-sleuth/scripts <candidate folder> result.json
```

## What it showed

540 candidate JPEGs, the same 6 queries, Windows 11, RTX 4070 SUPER. Ranks per query:

| query | DINOv2 | CLIP |
|---|---|---|
| as is | 1 1 1 1 1 1 | 1 1 1 1 1 1 |
| tilted 5° | 1 1 1 1 1 2 | 1 1 1 1 1 1 |
| tilted 15° | 2 1 1 1 1 1 | 2 1 1 1 1 1 |
| mirrored | 1 1 1 1 1 1 | 1 1 1 1 1 1 |
| rotated 90° | 2 14 8 1 8 23 | 1 33 2 1 5 1 |
| upside down | 1 1 2 1 2 4 | 1 3 81 1 3 40 |
| sideways + `Orientation=6`, `main` before #29 | 2 15 8 1 8 23 | 1 33 1 1 6 1 |
| sideways + `Orientation=6`, after stage 2 | 1 1 1 1 1 1 | 1 1 1 1 1 1 |

Small tilts and mirroring hardly matter; a quarter turn does, and before #29 an upright phone photo used as `--query` was ranked as if it lay on its side. Finding an identical image is the easy case; matches across years and viewpoints have less margin.

Content that is genuinely rotated (a photo of a photo held sideways) has no EXIF tag to go by and is not handled here.
