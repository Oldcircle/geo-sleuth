"""Shared reading of user photos and candidate images: an explicit set of raster formats, content sniffing
instead of trusting the suffix, RAW rejected with a request to export, and one failure category per file.

Scripts that read a photo or candidate images go through `open_image`; scripts that only read their own
outputs (map tiles, panoramas) keep plain `Image.open`. Callers that import this declare `pillow-heif` in their
PEP 723 header.

Pixel coordinates (crop boxes, OCR boxes, ridge points, pose points) refer to the upright frame, the photo as an
image viewer shows it: `open_photo` / `upright` apply the EXIF orientation exactly once. Records a script writes
with pixel coordinates in them (ridge.json, a pose record's `_frame`) say so with "frame": "upright". A record
without the key was written before orientation was applied, when those scripts drew on the stored pixels; it is
read in that "stored" frame whatever the image size (`frame_of`), so old records give the overlays they gave then.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps, features

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF = True
except ImportError:  # without pillow-heif, HEIC/HEIF is reported as a missing decoder; other formats work as usual
    HEIF = False

# Pillow format names accepted as a photo or candidate; anything else Pillow can open is "unsupported"
SUPPORTED = {"JPEG", "MPO", "PNG", "WEBP", "GIF", "BMP", "TIFF", "HEIF", "AVIF"}
# Directory scans: these suffixes (any case) after the historical *.jp*g then *.png order; other files are sniffed
SCAN_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".avif")
RAW_SUFFIXES = {".3fr", ".arw", ".cr2", ".cr3", ".crw", ".dcr", ".dng", ".erf", ".iiq", ".k25", ".kdc", ".mef",
                ".mos", ".mrw", ".nef", ".nrw", ".orf", ".pef", ".raf", ".raw", ".rw2", ".rwl", ".sr2", ".srf",
                ".srw", ".x3f"}
HEIF_BRANDS = {b"heic", b"heix", b"heim", b"heis", b"hevc", b"hevx", b"heif", b"mif1", b"msf1"}
AVIF_BRANDS = {b"avif", b"avis"}
HEAD = 32   # bytes read to sniff a file
ORIENTATION = 0x0112


class ImageReadError(Exception):
    """category: unreadable | empty | raw | not-image | unsupported | missing-decoder | decode-error"""

    def __init__(self, category: str, reason: str):
        super().__init__(reason)
        self.category = category
        self.reason = reason


def sniff(head: bytes, suffix: str = "") -> str | None:
    """Format from the first bytes: JPEG, PNG, WEBP, GIF, BMP, TIFF, HEIF, AVIF, RAW or TEXT; None if unknown."""
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "WEBP"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "GIF"
    if head[:2] == b"BM" and len(head) >= 14:
        return "BMP"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in HEIF_BRANDS:
            return "HEIF"
        if brand in AVIF_BRANDS:
            return "AVIF"
        if brand == b"crx ":
            return "RAW"                                    # Canon CR3
    if head.startswith((b"FUJIFILMCCD-RAW", b"IIRO", b"IIRS", b"MMOR", b"IIU\x00", b"FOVb")):
        return "RAW"                                        # Fujifilm RAF, Olympus ORF, Panasonic RW2, Sigma X3F
    if head[:4] in (b"II*\x00", b"MM\x00*"):
        if head[8:10] == b"CR" or suffix.lower() in RAW_SUFFIXES:
            return "RAW"                                    # Canon CR2; DNG, NEF, ARW, PEF ... are TIFF inside
        return "TIFF"
    if head.lstrip()[:1] in (b"<", b"{", b"["):
        return "TEXT"
    return None


def _head(path: Path) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read(HEAD)
    except OSError as e:
        raise ImageReadError("unreadable", f"cannot read the file ({e.strerror or type(e).__name__})") from None


def _tiff_is_raw(im: Image.Image) -> bool:
    """A TIFF that is really a camera RAW: a DNG version tag, raw photometric data, or a first image marked as a
    reduced-resolution preview with the real image in SubIFDs (Pillow would only ever read the preview)."""
    tags = getattr(im, "tag_v2", {})
    preview = int(tags.get(254, 0) or 0) & 1
    return 50706 in tags or tags.get(262) in (32803, 34892) or bool(preview and 330 in tags)


def _first_line(e: Exception) -> str:
    text = str(e).strip().splitlines()
    return f"{type(e).__name__}: {text[0]}" if text else type(e).__name__


def open_image(path: Path | str, load: bool = True) -> Image.Image:
    """Open a photo or candidate image. Raises ImageReadError with a category and a one-line reason.
    load=True decodes the pixels now, so a damaged file fails here instead of in the middle of a run."""
    path = Path(path)
    head = _head(path)
    if not head:
        raise ImageReadError("empty", "empty file")
    kind = sniff(head, path.suffix)
    if kind == "RAW" or (kind is None and path.suffix.lower() in RAW_SUFFIXES):
        raise ImageReadError("raw", f"camera RAW ({path.suffix or 'no suffix'}), which is not decoded here: export it as JPEG or PNG first")
    if kind == "TEXT":
        raise ImageReadError("not-image", "text, not an image (probably an error page saved by a download)")
    if kind == "HEIF" and not HEIF:
        raise ImageReadError("missing-decoder", "HEIC/HEIF, which needs pillow-heif (run the script with uv run, or convert to JPEG/PNG)")
    if kind == "AVIF" and not features.check("avif"):
        raise ImageReadError("missing-decoder", "AVIF, which this Pillow build cannot decode (upgrade Pillow, or convert to JPEG/PNG)")
    try:
        im = Image.open(path)
        if im.format == "TIFF" and _tiff_is_raw(im):    # checked from the tags, before any pixels are decoded
            im.close()
            raise ImageReadError("raw", f"camera RAW ({path.suffix or 'no suffix'}, TIFF-based: only its embedded preview would be read), "
                                        "which is not decoded here: export it as JPEG or PNG first")
        if load:
            im.load()
    except ImageReadError:
        raise
    except Exception as e:  # noqa: BLE001
        if kind is None:
            raise ImageReadError("not-image", f"not a recognised image ({_first_line(e)})") from None
        raise ImageReadError("decode-error", f"{kind} that could not be decoded ({_first_line(e)})") from None
    if im.format not in SUPPORTED:
        fmt = im.format
        im.close()
        raise ImageReadError("unsupported", f"{fmt} is not a supported photo format (JPEG, PNG, WebP, HEIC/HEIF, AVIF, GIF, BMP, TIFF): convert it first")
    return im


def open_or_exit(path: Path | str, what: str = "photo", load: bool = True) -> Image.Image:
    """open_image for a single required input: exit with one line instead of a traceback."""
    try:
        return open_image(path, load=load)
    except ImageReadError as e:
        sys.exit(f"cannot read {what} {path}: {e.reason}")


def find_images(directory: Path | str) -> list[Path]:
    """Image files in a folder, not recursive. Keeps the historical order (*.jp*g, then *.png, each sorted), then
    adds other image suffixes in any case (WebP, HEIC/HEIF, AVIF, uppercase names), then files whose first bytes
    show an image or a camera RAW despite a missing or misleading suffix (RAW is kept so it can be reported)."""
    d = Path(directory)
    files = sorted(d.glob("*.jp*g")) + sorted(d.glob("*.png"))
    seen = {f.resolve() for f in files}
    rest = sorted(f for f in d.iterdir() if f.is_file() and f.resolve() not in seen)
    by_suffix = [f for f in rest if f.suffix.lower() in SCAN_SUFFIXES or f.suffix.lower() in RAW_SUFFIXES]
    sniffed = []
    for f in rest:
        if f in by_suffix:
            continue
        try:
            with open(f, "rb") as fh:
                kind = sniff(fh.read(HEAD), f.suffix)
        except OSError:
            continue
        if kind not in (None, "TEXT"):
            sniffed.append(f)
    return files + by_suffix + sniffed


def orientation(im: Image.Image) -> int:
    """EXIF orientation (1–8) still to apply to the decoded pixels. HEIF is always 1: libheif applies the file's
    irot/imir transforms and pillow-heif resets the EXIF tag, which the HEIF spec says to ignore."""
    if im.format == "HEIF":
        return 1
    try:
        o = int(im.getexif().get(ORIENTATION, 1) or 1)
    except Exception:  # noqa: BLE001
        return 1
    return o if 1 <= o <= 8 else 1


def upright(im: Image.Image) -> Image.Image:
    """The image as a viewer shows it. Returns the same object when there is nothing to apply; otherwise
    exif_transpose, whose result carries no orientation tag, so a second call changes nothing."""
    return im if orientation(im) == 1 else ImageOps.exif_transpose(im)


FRAMES = ("upright", "stored")


def frame_of(record: dict, default: str = "stored") -> str:
    """Frame of the pixel coordinates in a record: its "frame" value, else `default`. For records a script wrote
    (ridge.json, a pose record's _frame) the default "stored" is the frame every record without the key was written in."""
    frame = record.get("frame", default)
    if frame not in FRAMES:
        sys.exit(f'"frame" must be one of {", ".join(FRAMES)}, not {frame!r}')
    return frame


def open_photo(path: Path | str, what: str = "photo", frame: str = "upright", size=None) -> Image.Image:
    """open_or_exit, in the frame of the coordinates that will be drawn on it: "upright" (EXIF orientation applied) or
    "stored" (the decoded pixels as they are, the frame of records written before orientation was applied).
    size: the image size a record gives, checked against the photo in that frame (records may be scaled, so the
    aspect ratio is what must agree)."""
    im = open_or_exit(path, what)
    o = orientation(im)
    if frame == "stored":
        if o != 1:
            print(f"note: {path} has EXIF orientation {o}; this record's coordinates are in the stored frame (a record without "
                  f"\"frame\": \"upright\" was written before orientation was applied), so it is drawn on the stored "
                  f"{im.width}x{im.height} pixels, unrotated", file=sys.stderr)
    else:
        im = upright(im)
    if size is not None and size[0] > 0 and size[1] > 0 and abs(size[0] / size[1] - im.width / im.height) > 0.01 * im.width / im.height:
        print(f"warning: the record's image size {size[0]}x{size[1]} doesn't match {path} in the {frame} frame "
              f"({im.width}x{im.height}); its points won't line up with the photo. If they were measured in the other frame, "
              f"set \"frame\": \"{'stored' if frame == 'upright' else 'upright'}\" in the record", file=sys.stderr)
    return im


# Formats every later step and the search engines take as they are; anything else gets a working copy
NATIVE = {"JPEG", "MPO", "PNG"}


def working_copy_reason(im: Image.Image) -> str | None:
    """Why a photo needs a working copy, or None: a format outside NATIVE, or an EXIF orientation still to apply."""
    if im.format not in NATIVE:
        return f"{'HEIC/HEIF' if im.format == 'HEIF' else im.format} decoded to PNG"
    o = orientation(im)
    return f"EXIF orientation {o} applied" if o != 1 else None


def write_working_copy(path: Path | str, out: Path | str) -> dict | None:
    """Lossless upright PNG of a photo that needs one (see working_copy_reason), with the original's EXIF kept
    (focal length, time, GPS) and its orientation tag reset. Returns None for photos used as they are; raises
    ImageReadError for unreadable ones. The original file is never touched."""
    path, out = Path(path), Path(out)
    im = open_image(path)
    why = working_copy_reason(im)
    if why is None:
        return None
    up = upright(im)
    if up.mode not in ("RGB", "RGBA", "L", "LA"):
        up = up.convert("RGBA" if "A" in up.getbands() else "RGB")
    exif = im.getexif()
    if ORIENTATION in exif:
        exif[ORIENTATION] = 1
    out.parent.mkdir(parents=True, exist_ok=True)
    extra = {"icc_profile": im.info["icc_profile"]} if im.info.get("icc_profile") else {}
    up.save(out, format="PNG", exif=exif, **extra)
    return {"original": str(path), "working": str(out), "reason": why, "format": im.format,
            "original_size": list(im.size), "working_size": list(up.size)}
