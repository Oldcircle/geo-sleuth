"""Shared torch device selection: CUDA, then MPS, then CPU; GEO_DEVICE overrides."""
from __future__ import annotations

import os
import sys

DEVICES = ("cpu", "cuda", "mps")


def _available(torch) -> dict:
    return {"cpu": True, "cuda": bool(torch.cuda.is_available()), "mps": bool(torch.backends.mps.is_available())}


def torch_device(torch=None) -> str:
    """Device for the ML models. GEO_DEVICE=cpu|cuda|mps forces one; an invalid or unavailable value exits with one line."""
    if torch is None:
        import torch
    have = _available(torch)
    want = os.environ.get("GEO_DEVICE", "").strip().lower()
    if not want:
        return "cuda" if have["cuda"] else "mps" if have["mps"] else "cpu"
    report = f"torch {torch.__version__} reports cuda={have['cuda']}, mps={have['mps']}"
    if want not in DEVICES:
        sys.exit(f"GEO_DEVICE={want!r} is not valid: use one of {', '.join(DEVICES)}, or unset it for automatic selection ({report}).")
    if not have[want]:
        sys.exit(f"GEO_DEVICE={want} was requested but that device is not available: {report}. Unset GEO_DEVICE or install a torch build that supports it.")
    return want
