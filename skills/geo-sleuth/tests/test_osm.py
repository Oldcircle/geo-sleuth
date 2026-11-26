#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline osm.py regressions with a mocked Overpass answer. Run: uv run skills/geo-sleuth/tests/test_osm.py"""
from __future__ import annotations

import argparse
import contextlib
import io
import math
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import osm  # noqa: E402


def building(eid: int, lat: float, lon: float, side_m: float = 60.0) -> dict:
    dlat = side_m / 111000
    dlon = side_m / (111000 * math.cos(math.radians(lat)))
    ring = [(lat, lon), (lat, lon + dlon), (lat + dlat, lon + dlon), (lat + dlat, lon), (lat, lon)]
    return {"type": "way", "id": eid, "tags": {"building": "yes"}, "geometry": [{"lat": a, "lon": b} for a, b in ring]}


def neighbor_counts(elements: list[dict], within: float) -> list[int]:
    args = argparse.Namespace(filter=None, min_area=1000, within=within, sort="area", proxy=None, cache=None)
    with patch.object(osm, "_scope", lambda a: ("", "")), patch.object(osm, "run", lambda *a, **k: {"elements": elements}), \
            contextlib.redirect_stdout(io.StringIO()):
        pts = osm.cmd_buildings(args)
    return [int(re.search(r"nb(\d+)", label).group(1)) for label in pts]


class BuildingsNeighbors(unittest.TestCase):
    def test_east_west_neighbor_within_radius_counts_at_any_latitude(self):
        # A degree of longitude is shorter than a degree of latitude: two buildings 190 m apart east-west are neighbors within 200 m
        for lat in (0.5, 30.0, 45.0, 60.0):
            for lon in (100.0, 100.0013, 100.0031):
                dlon = 190 / (111195 * math.cos(math.radians(lat)))
                els = [building(1, lat, lon), building(2, lat, lon + dlon)]
                self.assertEqual(neighbor_counts(els, 200), [1, 1], (lat, lon))

    def test_neighbor_beyond_radius_is_not_counted(self):
        lat = 60.0
        dlon = 260 / (111195 * math.cos(math.radians(lat)))
        els = [building(1, lat, 100.0), building(2, lat, 100.0 + dlon)]
        self.assertEqual(neighbor_counts(els, 200), [0, 0])


if __name__ == "__main__":
    unittest.main()
