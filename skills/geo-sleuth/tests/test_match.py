#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy", "opencv-python-headless", "torch"]
# ///
"""Offline descriptor and geometric verification regressions; no model download."""
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import match


class RendererOverlayTests(unittest.TestCase):
    def test_each_renderer_owns_its_overlay_and_plain_images_have_none(self):
        import baidu_pano
        import gsv
        box = (.8, 0., 1., .1)
        self.assertIsNone(match._overlay(None))
        self.assertIsNone(match._overlay('gsv'))
        with patch.object(baidu_pano, 'LOGO_BOX', box):
            self.assertEqual(match._overlay('baidu'), box)
        with patch.object(gsv, 'LOGO_BOX', box, create=True):
            self.assertEqual(match._overlay('gsv'), box)


class SiftTests(unittest.TestCase):
    def projected_matches(self, H, repeated=False):
        pa = np.float32([(x, y) for x in (20, 40, 60, 70) for y in (20, 40, 60)])
        pb = cv2.perspectiveTransform(pa[None], np.asarray(H, np.float64))[0]
        if repeated:
            pb = np.tile(pb[:3], (4, 1))
        descriptors = np.random.default_rng(1).random((len(pa), 128)).astype(np.float32)
        sift = SimpleNamespace(detectAndCompute=lambda *args: None)
        keypoints = lambda pts: [cv2.KeyPoint(float(x), float(y), 2) for x, y in pts]
        im = Image.new("RGB", (1024, 768))
        with patch.object(cv2, "SIFT_create", return_value=sift), patch.object(
            sift, "detectAndCompute", side_effect=[(keypoints(pa), descriptors), (keypoints(pb), descriptors)]
        ):
            if repeated:
                with patch.object(cv2, "findHomography", return_value=(np.eye(3), np.ones((len(pa), 1), np.uint8))):
                    return match.sift_inliers(im, im)
            return match.sift_inliers(im, im)

    def test_valid_perspective_with_negative_affine_minor_is_kept(self):
        self.assertEqual(self.projected_matches([[-1, 0, 300], [0, 1, 0], [-0.01, 0, 1]]), (12, 12))

    def test_mirrored_perspective_with_positive_affine_minor_is_rejected(self):
        self.assertEqual(self.projected_matches([[1, 0, 300], [0, 1, 0], [0.01, 0, 1]]), (0, 12))

    def test_affine_and_mirrored_matches(self):
        self.assertEqual(self.projected_matches([[1, 0, 25], [0, 1, 12], [0, 0, 1]]), (12, 12))
        self.assertEqual(self.projected_matches([[-1, 0, 300], [0, 1, 0], [0, 0, 1]]), (0, 12))

    def test_collapsed_matches_are_rejected(self):
        self.assertEqual(self.projected_matches(np.eye(3), repeated=True), (0, 12))

    def test_real_texture_survives_perspective(self):
        rng = np.random.default_rng(8)
        a = cv2.GaussianBlur(rng.integers(0, 256, (480, 640, 3), np.uint8), (3, 3), 0)
        b = cv2.warpPerspective(a, np.array([[.9, .06, 15], [-.04, .95, 20], [.0001, .0002, 1]]), (640, 480))
        self.assertGreater(match.sift_inliers(Image.fromarray(a), Image.fromarray(b))[0], 100)

    def test_logo_only_matches_do_not_verify_a_place(self):
        rng = np.random.default_rng(42)
        a = np.full((768, 1024), 128, np.uint8)
        a[718:768, :120] = cv2.resize(rng.integers(0, 256, (25, 60), np.uint8), (120, 50), interpolation=cv2.INTER_CUBIC)
        im = Image.fromarray(a)
        self.assertGreaterEqual(match.sift_inliers(im, im)[0], 15)
        self.assertEqual(match.sift_inliers(im, im, skip_b=match._overlay("baidu")), (0, 0))

    def test_blank_images_have_no_match(self):
        im = Image.new("RGB", (640, 480), "gray")
        self.assertEqual(match.sift_inliers(im, im), (0, 0))


class DescriptorTests(unittest.TestCase):
    def test_dino_halves_have_equal_weight_across_batches(self):
        emb = match.Embedder.__new__(match.Embedder)
        emb.method, emb.dev, emb.torch = "dino", "cpu", torch
        hidden = torch.tensor([[[3., 4.], [0., 2.], [0., 2.]]])
        emb.model = lambda pixel_values: SimpleNamespace(last_hidden_state=hidden.repeat(len(pixel_values), 1, 1))
        images = [Image.new("RGB", (80, 60)), Image.new("RGB", (100, 70))]
        features = emb.embed(images, multi=True, batch=3)
        self.assertEqual(features.shape, (2, 4, 4))
        np.testing.assert_allclose(np.linalg.norm(features, axis=-1), 1, atol=1e-6)
        np.testing.assert_allclose(features[0, 0], np.array([.6, .8, 0, 1]) / np.sqrt(2), atol=1e-6)
        np.testing.assert_allclose(features, np.broadcast_to(features[0, 0], features.shape))


if __name__ == "__main__":
    unittest.main()
