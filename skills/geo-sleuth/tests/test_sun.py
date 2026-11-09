#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["tzdata"]
# ///
"""Offline sun.py regressions. Run: uv run skills/geo-sleuth/tests/test_sun.py"""
from __future__ import annotations

import argparse
import contextlib
import io
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sun


def _compass(**kw) -> str:
    a = dict(at=(64.84, -147.72), tz="America/Anchorage", dates="2024-12-10:2024-12-20", time=None, step_days=3,
             elev=None, elev_max=12.0, sun_x=2000.0, width=4000.0, hfov="60:60", x=None)
    a.update(kw)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sun.cmd_compass(argparse.Namespace(**a))
    return buf.getvalue()


def _group(out: str, name: str) -> tuple[float, float]:
    m = re.search(name + r"[^:]*: sun azimuth ([\d.]+)°–([\d.]+)°", out)
    return float(m.group(1)), float(m.group(2))


class CompassGroups(unittest.TestCase):
    def test_groups_split_at_solar_noon_not_clock_noon(self):
        # Fairbanks in December: solar noon is about 12:45 local, so the sun is still east of south after 12:00
        out = _compass()
        self.assertLessEqual(_group(out, "morning")[1], 180)
        self.assertGreaterEqual(_group(out, "evening")[0], 180)

    def test_far_west_of_time_zone_meridian(self):
        # Kashgar on Beijing time: a late-morning sun at 12:30 is still south-east
        out = _compass(at=(39.47, 75.99), tz="Asia/Shanghai", elev="5:20")
        self.assertLessEqual(_group(out, "morning")[1], 180)
        self.assertGreaterEqual(_group(out, "evening")[0], 180)


class CompassAcrossNorth(unittest.TestCase):
    """A range that crosses north is printed clockwise (358°–1°), not as its complement (0°–360°)."""

    @staticmethod
    def _span(lo: float, hi: float) -> float:
        return (hi - lo) % 360

    def test_sun_azimuth_range_crossing_north(self):
        # Sydney at noon in June–July: the sun sits just either side of due north
        out = _compass(at=(-33.87, 151.21), tz="Australia/Sydney", dates="2024-06-01:2024-07-30", time="12:00",
                       hfov="60:70")
        lo, hi = _group(out, "12:00")
        self.assertLess(self._span(lo, hi), 10, out)
        self.assertGreater(lo, hi, out)

    def test_camera_heading_range_crossing_north(self):
        # Fairbanks in June: the morning sun is north-east, so the camera can face just west of north
        out = _compass(dates="2024-06-15:2024-06-25", sun_x=3000.0, hfov="60:70")
        m = re.search(r"morning[^\n]*camera heading about (\d+)°–(\d+)°", out)
        lo, hi = float(m.group(1)), float(m.group(2))
        self.assertLess(self._span(lo, hi), 90, out)
        self.assertGreater(lo, hi, out)


class StreetHalves(unittest.TestCase):
    def test_morning_label_follows_the_sun_side(self):
        a = argparse.Namespace(at=(39.47, 75.99), tz="Asia/Shanghai", date="2024-06-21", shadow_rel=90.0, both=False,
                               elev=None, ratio=None, tol=3.0, step_min=10)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sun.cmd_street(a)
        rows = re.findall(r"^\d\d:\d\d (morning|afternoon)  sun\s+([\d.]+)°", buf.getvalue(), re.M)
        self.assertTrue(rows)
        for half, az in rows:
            self.assertEqual(half, "morning" if float(az) < 180 else "afternoon", (half, az))


if __name__ == "__main__":
    unittest.main()
