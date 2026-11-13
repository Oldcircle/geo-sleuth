#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""Offline regressions for yandex_pano.py: metadata parsing and ray-traced perspective projection."""
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import yandex_pano
import match


class YandexPanoTests(unittest.TestCase):
    def test_parse_meta_extracts_fields(self):
        sample = {
            "status": "success",
            "Point": {"coordinates": ["69.279700", "41.311100"]},
            "Properties": {
                "PanoramaDescription": {
                    "id": "1342674921_672349120_23_1623838291",
                    "direction": [120.5, 5.0],
                    "timestamp": 1623838291,
                    "name": "Amir Temur Avenue"
                }
            },
            "Images": {
                "tiles": {"width": 256, "height": 256},
                "sizes": [[512, 256], [1024, 512], [2048, 1024]]
            },
            "Connections": [
                {
                    "Point": {"coordinates": ["69.280100", "41.311500"]},
                    "Properties": {"Connection": {"id": "next_pano_id_123"}}
                }
            ]
        }
        res = yandex_pano._parse_meta(sample)
        self.assertEqual(res["id"], "1342674921_672349120_23_1623838291")
        self.assertAlmostEqual(res["lat"], 41.3111)
        self.assertAlmostEqual(res["lon"], 69.2797)
        self.assertAlmostEqual(res["heading"], 120.5)
        self.assertAlmostEqual(res["pitch"], 5.0)
        self.assertEqual(res["date"], "2021-06-16")
        self.assertEqual(len(res["connections"]), 1)
        self.assertEqual(res["connections"][0]["id"], "next_pano_id_123")

    def test_parse_meta_modern_schema(self):
        sample = {
            "Data": {
                "panoramaId": "1487010902_804195183_23_1570679630",
                "timestamp": 1571140800,
                "Point": {"coordinates": [69.279628, 41.311031, 0]},
                "EquirectangularProjection": {"Origin": [118.81, 22.74]},
                "Images": {
                    "imageId": "BmtLVZGKdvn1",
                    "Tiles": {"width": 256, "height": 256},
                    "Zooms": [{"level": 3, "width": 1792, "height": 669}]
                }
            },
            "Annotation": {
                "Graph": {
                    "Nodes": [
                        {"id": 0, "panoid": "1487010902_804195183_23_1570679630", "lat": 41.311031, "lon": 69.279628},
                        {"id": 1, "panoid": "1487011543_804195358_23_1570679594", "lat": 41.311008, "lon": 69.279735}
                    ]
                }
            }
        }
        res = yandex_pano._parse_meta(sample)
        self.assertEqual(res["id"], "1487010902_804195183_23_1570679630")
        self.assertEqual(res["image_id"], "BmtLVZGKdvn1")
        self.assertAlmostEqual(res["lat"], 41.311031)
        self.assertAlmostEqual(res["lon"], 69.279628)
        self.assertAlmostEqual(res["heading"], 118.81)
        self.assertAlmostEqual(res["pitch"], 22.74)
        self.assertEqual(res["date"], "2019-10-15")
        self.assertEqual(len(res["connections"]), 1)
        self.assertEqual(res["connections"][0]["id"], "1487011543_804195358_23_1570679594")

    def test_project_perspective_quadrant_angles(self):
        # 1000x500 synthetic equirectangular panorama split into 4 color quadrants
        W_eq, H_eq = 1000, 500
        pano = np.zeros((H_eq, W_eq, 3), dtype=np.uint8)
        pano[:, :250] = [255, 0, 0]      # 0..90 deg: Red (North to East)
        pano[:, 250:500] = [0, 255, 0]    # 90..180 deg: Green (East to South)
        pano[:, 500:750] = [0, 0, 255]    # 180..270 deg: Blue (South to West)
        pano[:, 750:] = [255, 255, 0]     # 270..360 deg: Yellow (West to North)

        # Looking East (heading 90) -> center pixel should land in Green quadrant
        im_east = yandex_pano.project_perspective(pano, heading_deg=90, pitch_deg=0, hfov_deg=60, width=100, height=100)
        arr_east = np.array(im_east)
        np.testing.assert_array_equal(arr_east[50, 50], [0, 255, 0])

        # Looking South (heading 180) -> center pixel should land in Blue quadrant
        im_south = yandex_pano.project_perspective(pano, heading_deg=180, pitch_deg=0, hfov_deg=60, width=100, height=100)
        arr_south = np.array(im_south)
        np.testing.assert_array_equal(arr_south[50, 50], [0, 0, 255])

    def test_match_overlay_support(self):
        # yandex has no default logo box overlay
        self.assertIsNone(match._overlay("yandex"))


if __name__ == "__main__":
    unittest.main()
