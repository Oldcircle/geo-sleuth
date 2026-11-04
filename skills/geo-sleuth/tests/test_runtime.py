#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "pillow-heif", "numpy", "pyyaml"]
# ///
"""Offline runtime regressions. Run: uv run skills/geo-sleuth/tests/test_runtime.py"""
from __future__ import annotations

import asyncio
import contextlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import http.server
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import urllib.parse

import numpy as np
from PIL import Image, ImageDraw

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _net
import _browser
import _device
import _image
import match
import pose
import baidu_pano
import doctor
import evidence
import gsv
import osm
import poi
import revimg


class NetworkTests(unittest.TestCase):
    def test_route_precedence(self):
        with patch.dict(os.environ, {"GEO_PROXY": "http://localhost:8123"}, clear=True):
            self.assertEqual(_net.resolve_proxy(), "http://localhost:8123")
            self.assertEqual(_net.resolve_proxy("http://localhost:8234"), "http://localhost:8234")
            self.assertIsNone(_net.resolve_proxy("direct"))
            self.assertIsNone(_net.resolve_proxy(""))
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://localhost:9999"}, clear=True):
            self.assertIsNone(_net.resolve_proxy())

    @unittest.skipUnless(shutil.which("curl"), "curl required")
    def test_curl_reaches_direct_and_explicit_proxy_despite_ambient_settings(self):
        paths = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                paths.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "http_proxy": "http://127.0.0.1:1",
                                         "ALL_PROXY": "http://127.0.0.1:1", "NO_PROXY": "*", "GEO_PROXY": "http://127.0.0.1:1"}):
                self.assertEqual(_net.fetch_bytes(base + "/direct", "direct"), b"ok")
                self.assertEqual(_net.fetch_bytes("http://example.invalid/proxied", base), b"ok")
            self.assertEqual(paths, ["/direct", "http://example.invalid/proxied"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_model_route_overrides_ambient_variables(self):
        with patch.dict(os.environ, {"GEO_PROXY": "http://chosen:8080", "https_proxy": "http://old:8080", "NO_PROXY": "*"}, clear=True):
            _net.model_proxy_env()
            self.assertEqual(os.environ["HTTPS_PROXY"], "http://chosen:8080")
            if os.name != "nt":   # Windows environment variable names are case-insensitive
                self.assertNotIn("https_proxy", os.environ)
            self.assertNotIn("NO_PROXY", os.environ)
            _net.model_proxy_env("direct")
            self.assertNotIn("HTTPS_PROXY", os.environ)
            self.assertEqual(os.environ["NO_PROXY"], "*")

    def test_baidu_near_forwards_proxy(self):
        with patch.object(baidu_pano, "fetch_bytes", return_value=b'{"content":null}') as fetch:
            self.assertIsNone(baidu_pano.near(35, 110, proxy="http://chosen:8080"))
            self.assertEqual(fetch.call_args.args[1], "http://chosen:8080")

    def test_all_poi_sources_forward_proxy(self):
        with patch.object(poi, "_curl", return_value='{}') as fetch:
            poi.search_so("school", None, 2, "direct")
            self.assertEqual(fetch.call_args.kwargs["proxy"], "direct")
            poi.search_sug("school", "http://chosen:8080")
            self.assertEqual(fetch.call_args.kwargs["proxy"], "http://chosen:8080")
        with patch.object(poi, "_curl", return_value='[]') as fetch:
            poi.search_osm("school", None, 2, "http://chosen:8080", "us")
            self.assertEqual(fetch.call_args.kwargs["proxy"], "http://chosen:8080")

    def test_intake_forwards_route_to_both_engines(self):
        import intake
        from PIL import Image
        commands = []
        def run(cmd, **kwargs):
            commands.append(cmd)
            return 0, "", ""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            photo = root / "photo.jpg"
            Image.new("RGB", (100, 100), "white").save(photo)
            # Preparation writes files used by intake; run the actual small local helpers.
            original = intake._run
            def local_or_search(cmd, **kwargs):
                if any(str(part).endswith("revimg.py") for part in cmd):
                    return run(cmd, **kwargs)
                return original([sys.executable, *cmd[2:]], **kwargs)
            with patch.object(intake, "_run", side_effect=local_or_search), patch.object(sys, "argv", ["intake.py", str(photo), "--out-dir", str(root / "out"), "--no-ocr", "--max-variants", "1", "--proxy", "direct"]):
                intake.main()
            self.assertEqual(len(commands), 2)
            for cmd in commands:
                self.assertEqual(cmd[cmd.index("--proxy") + 1], "direct")
            self.assertEqual({cmd[cmd.index("--engines") + 1] for cmd in commands}, {"baidu", "yandex"})


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_chromium_fallback_uses_same_route(self):
        browser = object()
        launch = AsyncMock(side_effect=[RuntimeError("Chrome absent"), browser])
        p = SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        actual, label = await _browser.launch_browser(p, "socks5h://localhost:8123")
        self.assertIs(actual, browser)
        self.assertEqual(label, "Playwright Chromium")
        for call in launch.call_args_list:
            self.assertEqual(call.kwargs["proxy"]["server"], "socks5://localhost:8123")
        self.assertEqual(launch.call_args_list[0].kwargs["channel"], "chrome")
        self.assertNotIn("channel", launch.call_args_list[1].kwargs)

    async def test_explicit_direct_overrides_saved_browser_proxy(self):
        launch = AsyncMock(return_value=object())
        p = SimpleNamespace(chromium=SimpleNamespace(launch=launch))
        with patch.dict(os.environ, {"GEO_PROXY": "http://old:8080"}):
            await _browser.launch_browser(p, "direct")
        self.assertNotIn("proxy", launch.call_args.kwargs)
        self.assertIn("--no-proxy-server", launch.call_args.kwargs["args"])

    async def test_both_browsers_missing_gives_install_fix(self):
        p = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(side_effect=RuntimeError("missing"))))
        with self.assertRaisesRegex(RuntimeError, "uvx playwright install chromium"):
            await _browser.launch_browser(p, "direct")

    async def test_reverse_search_all_engines_get_selected_route(self):
        browser = SimpleNamespace(new_context=AsyncMock(), close=AsyncMock())
        manager = AsyncMock()
        manager.__aenter__.return_value = object()
        # Avoid requiring Playwright in this offline test's environment.
        fake = SimpleNamespace(async_playwright=lambda: manager)
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {"playwright.async_api": fake}), patch.object(revimg, "launch_browser", AsyncMock(return_value=(browser, "test"))) as launch, patch.object(revimg, "_text", AsyncMock(return_value={"links": []})), patch.object(revimg, "_baidu", AsyncMock(return_value={"links": []})) as baidu, patch.object(revimg, "_yandex", AsyncMock(return_value={"links": []})):
            Image.new("RGB", (8, 8)).save(Path(folder) / "photo.jpg")
            await revimg.run([Path(folder) / "photo.jpg"], ["baidu", "yandex"], Path(folder), "direct", ["school"], ["bing"])
            self.assertEqual(launch.await_count, 3)
            self.assertTrue(all(call.args[1] == "direct" for call in launch.await_args_list))
            self.assertEqual(baidu.await_args.args[-1], "direct")


class DoctorTests(unittest.TestCase):
    def test_probe_distinguishes_transport_failure_and_service_block(self):
        for returncode, stdout, status in [(0, "200", "PASS"), (0, "429", "WARN"), (7, "000", "FAIL")]:
            with self.subTest(status=status), patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=returncode, stdout=stdout)):
                row = doctor.probe(("service", "https://example.invalid"), "direct")
                self.assertEqual(row["status"], status)

    def test_local_checks_do_not_probe_network_or_print_proxy_credentials(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(doctor, "browser_check", AsyncMock(return_value=doctor.check("browser", "PASS", "ready"))), patch.object(doctor, "probe") as probe, patch.dict(os.environ, {"GEO_PROXY": "http://user:secret@localhost:8080"}):
            report = doctor.diagnose(False, None)
            probe.assert_not_called()
            self.assertTrue(report["ok"])
            self.assertNotIn("secret", json.dumps(report))
            self.assertEqual(report["connection"], "configured proxy")


QH = '[out:json][timeout:180];(area["name"="青海省"];area["name:zh"="青海省"];area["name:zh-Hans"="青海省"];)->.searchArea;nwr["power"="line"](area.searchArea);out geom tags;'
LINE = {"type": "way", "id": 1, "geometry": [{"lat": 37.7, "lon": 95.3}, {"lat": 37.8, "lon": 95.4}], "tags": {"power": "line"}}


def count(n):
    return {"elements": [{"type": "count", "tags": {"total": str(n)}}]}


class OverpassMirrorTests(unittest.TestCase):
    """One mirror answered a whole-province --area query with a clean empty result while others had thousands of lines; it got cached."""

    def run_with(self, replies, ql=QH):
        calls = []

        def post(ep, q, proxy, timeout):
            calls.append(ep)
            return replies(ep, q)

        with tempfile.TemporaryDirectory() as d, patch.object(osm, "_post", side_effect=post), patch.object(osm.time, "sleep"):
            data = osm.run(ql, None, Path(d))
            cached = list(Path(d).glob("*.json"))
        return data, calls, cached

    def test_empty_from_one_mirror_is_checked_on_another(self):
        data, calls, cached = self.run_with(lambda ep, q: ({"elements": []} if ep == osm.ENDPOINTS[0] else {"elements": [LINE]}, ""))
        self.assertEqual(len(data["elements"]), 1)
        self.assertEqual(calls, osm.ENDPOINTS[:2])
        self.assertEqual(len(cached), 1)

    def test_empty_confirmed_by_two_mirrors_is_cached(self):
        data, calls, cached = self.run_with(lambda ep, q: ({"elements": []}, ""))
        self.assertEqual(data["elements"], [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(cached), 1)

    def test_unconfirmed_empty_is_returned_but_not_cached(self):
        data, calls, cached = self.run_with(lambda ep, q: ({"elements": []}, "") if ep == osm.ENDPOINTS[0] else (None, "503"))
        self.assertEqual(data["elements"], [])
        self.assertEqual(cached, [])
        self.assertEqual(len(calls), len(osm.ENDPOINTS))           # one round, no retry sleeps

    def test_zero_area_count_needs_a_second_mirror(self):
        ql = '[out:json][timeout:120];(area["name"="青海省"];)->.a;.a out count;'
        data, _, _ = self.run_with(lambda ep, q: (count(0) if ep == osm.ENDPOINTS[0] else count(1), ""), ql)
        self.assertEqual(data["elements"][0]["tags"]["total"], "1")

    def test_empty_admin_level_inside_a_relation_needs_a_second_mirror(self):
        ql = ('[out:json][timeout:180];rel(161349);map_to_area->.a;'
              'rel(area.a)["boundary"="administrative"]["admin_level"="5"];out tags bb;')
        data, calls, cached = self.run_with(lambda ep, q: ({"elements": []} if ep == osm.ENDPOINTS[0] else {"elements": [LINE]}, ""), ql)
        self.assertEqual(len(data["elements"]), 1)
        self.assertEqual(calls, osm.ENDPOINTS[:2])

    def test_legacy_empty_area_cache_is_rechecked_and_replaced(self):
        import hashlib
        ql = '[out:json];rel(161349);map_to_area->.a;rel(area.a);out tags bb;'
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)
            key = cache / (hashlib.sha1(ql.encode()).hexdigest()[:16] + '.json')
            key.write_text(json.dumps({'elements': []}), encoding='utf-8')
            with patch.object(osm, '_post', return_value=({'elements': [LINE]}, '')) as post:
                self.assertEqual(osm.run(ql, None, cache)['elements'], [LINE])
                self.assertEqual(post.call_count, 1)
            with patch.object(osm, '_post', side_effect=AssertionError('nonempty cache missed')):
                self.assertEqual(osm.run(ql, None, cache)['elements'], [LINE])

    def test_confirmed_empty_cache_is_reused_without_leaking_cache_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(osm, '_post', return_value=({'elements': []}, '')) as post:
                self.assertEqual(osm.run(QH, None, Path(d)), {'elements': []})
                self.assertEqual(post.call_count, 2)
            with patch.object(osm, '_post', side_effect=AssertionError('confirmed cache missed')):
                self.assertEqual(osm.run(QH, None, Path(d)), {'elements': []})

    def test_unconfirmed_refresh_does_not_turn_legacy_cache_into_confirmed_empty(self):
        import hashlib
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d)
            key = cache / (hashlib.sha1(QH.encode()).hexdigest()[:16] + '.json')
            key.write_text(json.dumps({'elements': []}), encoding='utf-8')
            with patch.object(osm, '_post', side_effect=lambda ep, *a: ({'elements': []}, '') if ep == osm.ENDPOINTS[0] else (None, '503')):
                self.assertEqual(osm.run(QH, None, cache), {'elements': []})
            with patch.object(osm, '_post', return_value=({'elements': [LINE]}, '')) as post:
                self.assertEqual(osm.run(QH, None, cache)['elements'], [LINE])
                self.assertEqual(post.call_count, 1)

    def test_bbox_empty_is_trusted(self):
        ql = '[out:json][timeout:180];nwr["power"="line"](37.6,95.2,37.8,95.4);out geom tags;'
        _, calls, cached = self.run_with(lambda ep, q: ({"elements": []}, ""), ql)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(cached), 1)

    def test_failure_names_every_mirror(self):
        replies = {osm.ENDPOINTS[0]: (None, "HTTP 406: Not Acceptable"), osm.ENDPOINTS[1]: (None, "HTTP 500: Internal Server Error"),
                   osm.ENDPOINTS[2]: (None, "HTTP 504: server too busy")}
        with self.assertRaises(SystemExit) as cm:
            self.run_with(lambda ep, q: replies[ep])
        for code in ("406", "500", "504"):
            self.assertIn(code, str(cm.exception))

    def test_error_remark_not_cached(self):
        def replies(ep, q):
            if ep == osm.ENDPOINTS[0]:
                return {"elements": [], "remark": "runtime error: Query timed out"}, ""
            return {"elements": [LINE]}, ""
        data, _, cached = self.run_with(replies)
        self.assertEqual(len(data["elements"]), 1)
        self.assertEqual(len(cached), 1)

    def test_tls_failure_resends_the_same_post_without_curl(self):
        """Windows 10's Schannel curl has no TLS 1.3, which overpass-api.de requires, so curl exits 35 before any HTTP."""
        got = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"])).decode()
                got.append((self.headers["User-Agent"], urllib.parse.parse_qs(body)["data"]))
                busy = self.path == "/busy"
                self.send_response(504 if busy else 200)
                self.end_headers()
                self.wfile.write(b"server too busy" if busy else json.dumps({"elements": [LINE]}).encode())
            def log_message(self, *args):
                pass
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with patch.object(osm.subprocess, "run", return_value=SimpleNamespace(returncode=35, stdout="")):
                self.assertEqual(osm._post(base + "/ok", QH, "direct", 5), ({"elements": [LINE]}, ""))
                self.assertEqual(osm._post(base + "/busy", QH, "direct", 5), (None, "HTTP 504: server too busy"))
            self.assertEqual(got, [(osm.UA, [QH])] * 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


class StreetViewTests(unittest.TestCase):
    def test_lookup_replies(self):
        ok = json.dumps([[0], [[1], [2, "Z4kP7jsHKunVOqfsg_khyw"], None, [None, None, [["168 W 60th Ave"], ["Vancouver"]]], None,
                               [[None, [[None, None, 49.21598, -123.10927], None, [90.4]], None, [[]], None, None, None, None, []]],
                               [None] * 7 + [[2024, 5]]]])
        cases = {
            ok: "Z4kP7jsHKunVOqfsg_khyw",
            '[[5,"generic","Search returned no images."]]': None,
        }
        for reply, want in cases.items():
            with patch.object(gsv, "_curl", return_value=reply.encode()):
                res = gsv.near(49.2161, -123.1093, 50, None)
                self.assertEqual(res and res["id"], want)
        ok_res = None
        with patch.object(gsv, "_curl", return_value=ok.encode()):
            ok_res = gsv.near(49.2161, -123.1093, 50, None)
        self.assertEqual(ok_res["date"], "2024-05")
        for bad in ('[[5,"generic","GeoPhotoService.SingleImageSearch is decommissioned and turned down."]]',
                    '[3,"Invalid JSON payload received."]', "<html>blocked</html>", ""):
            with patch.object(gsv, "_curl", return_value=bad.encode()), self.assertRaises(gsv.ServiceError):
                gsv.near(49.2161, -123.1093, 50, None)



def _coverage(panos: list[tuple[str, float, float]]) -> str:
    """A coverage tile reply in the layout photometa/ac/v1 returns; no panoramas gives the empty-tile layout."""
    if not panos:
        return ")]}'\n" + json.dumps([None, None, [["ChA0YTkw", [None, None, [None, None, 40.0, -40.0]]]]])
    rows = [[[[2, pid], None, [[None, None, la, lo], [19.2, None, 63.4], [45.9, 0.27, 1.5]]], [27, 113]] for pid, la, lo in panos]
    return ")]}'\n" + json.dumps([None, [None, rows]])


class CoverageTests(unittest.TestCase):
    PID = "77-Z-M-G0QlSNisjusa5DA"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cache = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def world(self, panos):
        """_curl stand-in serving each z17 tile only the panoramas inside it; records requested tiles."""
        asked = []

        def curl(url, proxy, out=None, data=None):
            x, y = map(int, re.search(r"!1i(\d+)!2i(\d+)", url).groups())
            asked.append((x, y))
            inside = [(pid, la, lo) for pid, la, lo in panos
                      if tuple(int(v // 256) for v in gsv.geo.ll2px(17, la, lo)) == (x, y)]
            return _coverage(inside).encode()
        return curl, asked

    def test_empty_tile_vs_failed_lookup(self):
        with patch.object(gsv, "_curl", return_value=_coverage([]).encode()):
            self.assertEqual(gsv.tile_panos(1, 1, None, self.cache), [])
        with patch.object(gsv, "_curl", return_value=_coverage([(self.PID, 51.44, 5.47)]).encode()):
            self.assertEqual(gsv.tile_panos(2, 2, None, self.cache), [(self.PID, 51.44, 5.47)])
        for bad in ("<html>429 Too Many Requests</html>", "", ")]}'\n<html>429 Too Many Requests</html>",
                    ")]}'\n[3,\"Invalid request\"]", ")]}'\n{\"error\": 1}"):
            with patch.object(gsv, "_curl", return_value=bad.encode()), self.assertRaises(gsv.ServiceError):
                gsv.tile_panos(3, 3, None, self.cache)

    def test_failed_reply_is_not_cached(self):
        bad = ")]}'\n<html>429 Too Many Requests</html>"
        with patch.object(gsv, "_curl", return_value=bad.encode()), self.assertRaises(gsv.ServiceError):
            gsv.tile_panos(5, 5, None, self.cache)
        self.assertEqual([f.name for f in self.cache.iterdir()], [])
        good = _coverage([(self.PID, 51.44, 5.47)]).encode()
        with patch.object(gsv, "_curl", return_value=good) as m:
            self.assertEqual(len(gsv.tile_panos(5, 5, None, self.cache)), 1)
            self.assertEqual(m.call_count, 1)  # retried, not served from cache
            self.assertEqual(len(gsv.tile_panos(5, 5, None, self.cache)), 1)
            self.assertEqual(m.call_count, 1)  # a valid reply is cached
        # an error reply left in the cache by an older version is fetched again
        (self.cache / "cov17_6_6.txt").write_text(bad, encoding="utf-8")
        with patch.object(gsv, "_curl", return_value=good) as m:
            self.assertEqual(len(gsv.tile_panos(6, 6, None, self.cache)), 1)
            self.assertEqual(m.call_count, 1)

    def test_disappearing_coverage_cache_is_refetched(self):
        cached = self.cache / "cov17_7_7.txt"
        cached.write_text(")]}'\n<html>429 Too Many Requests</html>", encoding="utf-8")
        read_text = Path.read_text

        def read(path, *args, **kwargs):
            if path == cached:
                path.unlink()  # another worker removed a stale entry before this read
            return read_text(path, *args, **kwargs)

        good = _coverage([(self.PID, 51.44, 5.47)]).encode()
        with patch.object(Path, "read_text", read), patch.object(gsv, "_curl", return_value=good) as fetch:
            self.assertEqual(gsv.tile_panos(7, 7, None, self.cache), [(self.PID, 51.44, 5.47)])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(gsv._coverage_rows(cached.read_text(encoding="utf-8")), gsv._coverage_rows(good.decode()))

    def test_shared_coverage_tile_uses_one_fetch(self):
        for stale in (False, True):
            with self.subTest(stale=stale):
                cached = self.cache / "cov17_8_8.txt"
                if stale:
                    cached.write_text(")]}'\n<html>429 Too Many Requests</html>", encoding="utf-8")
                fetching, release, started = threading.Event(), threading.Event(), threading.Event()
                good = _coverage([(self.PID, 51.44, 5.47)]).encode()

                def curl(*args, **kwargs):
                    fetching.set()
                    if not release.wait(5):
                        raise RuntimeError("test did not release coverage request")
                    return good

                def second():
                    started.set()
                    return gsv.tile_panos(8, 8, None, self.cache)

                with patch.object(gsv, "_curl", side_effect=curl) as fetch, ThreadPoolExecutor(2) as ex:
                    first = ex.submit(gsv.tile_panos, 8, 8, None, self.cache)
                    try:
                        self.assertTrue(fetching.wait(5))
                        other = ex.submit(second)
                        self.assertTrue(started.wait(5))
                        with self.assertRaises(TimeoutError):
                            other.result(timeout=0.1)
                    finally:
                        release.set()
                    expected = [(self.PID, 51.44, 5.47)]
                    self.assertEqual(first.result(timeout=5), expected)
                    self.assertEqual(other.result(timeout=5), expected)
                    self.assertEqual(fetch.call_count, 1)
                cached.unlink()

    def test_targets_reports_failed_lookups(self):
        pts = self.cache / "pts.json"
        pts.write_text(json.dumps({"church": [51.44, 5.47]}), encoding="utf-8")
        out = self.cache / "t.index.json"
        argv = ["gsv.py", "targets", "--points", str(pts), "--out", str(out), "--cache", str(self.cache / "c")]
        with patch.object(gsv, "_curl", return_value=b"<html>429 Too Many Requests</html>"), \
                patch.object(sys, "argv", argv), patch("sys.stdout", new=io.StringIO()) as stdout, \
                patch("sys.stderr", new=io.StringIO()), self.assertRaises(SystemExit) as e:
            gsv.main()
        self.assertIn("lookup failed", str(e.exception.code))
        self.assertIn("0 targets without a panorama", stdout.getvalue())
        self.assertIn("1 lookups failed", stdout.getvalue())

    def _edge_target(self, lat):
        """A target 1 px inside the eastern edge of its z17 tile."""
        x, y = gsv.geo.ll2px(17, lat, 5.0)
        tx = int(x // 256)
        tlat, tlon = gsv.geo.px2ll(17, (tx + 1) * 256 - 1, y)
        return tx, tlat, tlon

    def _east(self, lat, lon, metres):
        return lon + math.degrees(metres / (gsv.geo._R * math.cos(math.radians(lat))))

    def test_radius_wider_than_one_tile(self):
        tx, lat, lon = self._edge_target(51.5)
        plon = self._east(lat, lon, 250)
        self.assertEqual(int(gsv.geo.ll2px(17, lat, plon)[0] // 256), tx + 2)  # outside the old 3x3 block
        curl, asked = self.world([(self.PID, lat, plon)])
        with patch.object(gsv, "_curl", side_effect=curl):
            got = gsv.panos_around(lat, lon, 12, 300, 2, 15, None, self.cache)
        self.assertEqual([g[0] for g in got], [self.PID])
        self.assertAlmostEqual(got[0][3], 250, delta=1)
        self.assertIn(tx + 2, {a[0] for a in asked})
        with patch.object(gsv, "_curl", side_effect=curl):  # the exact distance filter still applies
            self.assertEqual(gsv.panos_around(lat, lon, 12, 200, 2, 15, None, self.cache), [])

    def test_high_latitude_default_radius(self):
        tx, lat, lon = self._edge_target(78.2)
        plon = self._east(lat, lon, 69)
        self.assertEqual(int(gsv.geo.ll2px(17, lat, plon)[0] // 256), tx + 2)
        curl, _ = self.world([(self.PID, lat, plon)])
        with patch.object(gsv, "_curl", side_effect=curl):
            got = gsv.panos_around(lat, lon, 12, 70, 2, 15, None, self.cache)
        self.assertEqual([g[0] for g in got], [self.PID])

    def test_tile_range_stays_small(self):
        self.assertLessEqual(len(gsv.tiles_around(51.5, 5.0, 70)), 4)  # a 70 m radius spans at most 2x2 tiles of ~190 m
        tiles = gsv.tiles_around(0.0, 179.9999, 300)  # wraps across the antimeridian
        self.assertTrue(all(0 <= x < 2 ** 17 for x, _ in tiles))
        self.assertIn(0, {x for x, _ in tiles})

class FontTests(unittest.TestCase):
    def _tried_paths(self, env):
        tried = []

        def fake_truetype(path, size):
            tried.append(path)
            raise OSError("not found")

        with patch.dict(os.environ, env, clear=True),                 patch.object(baidu_pano.ImageFont, "truetype", side_effect=fake_truetype),                 patch.object(baidu_pano.ImageFont, "load_default", return_value="default"):
            self.assertEqual(baidu_pano._font(16), "default")
        return tried

    def test_windows_cjk_fonts_are_tried(self):
        tried = self._tried_paths({})
        self.assertIn("C:/Windows/Fonts/msyh.ttc", tried)
        self.assertIn("C:/Windows/Fonts/msyhbd.ttc", tried)
        self.assertIn("C:/Windows/Fonts/simsun.ttc", tried)

    def test_geo_font_is_tried_first(self):
        tried = self._tried_paths({"GEO_FONT": "D:/fonts/custom.ttf"})
        self.assertEqual(tried[0], "D:/fonts/custom.ttf")

    def test_first_available_font_is_used(self):
        def fake_truetype(path, size):
            if path != "C:/Windows/Fonts/simhei.ttf":
                raise OSError("not found")
            return path

        with patch.dict(os.environ, {}, clear=True),                 patch.object(baidu_pano.ImageFont, "truetype", side_effect=fake_truetype):
            self.assertEqual(baidu_pano._font(16), "C:/Windows/Fonts/simhei.ttf")


class SkillMetadataTests(unittest.TestCase):
    def test_frontmatter_meets_agent_skills_spec(self):
        root = Path(__file__).resolve().parents[1]
        m = re.match(r"---\n(.*?)\n---\n", (root / "SKILL.md").read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(m, "frontmatter must open and close with --- lines")
        meta = yaml.safe_load(m.group(1))                  # strict parser: a ': ' inside the description breaks it
        self.assertIsInstance(meta, dict)
        self.assertEqual(meta["name"], root.name)
        self.assertIsInstance(meta["description"], str)
        self.assertTrue(meta["description"].strip())
        self.assertLessEqual(len(meta["description"]), 1024)   # https://agentskills.io/specification


class EvidenceSpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "area.jpg").write_bytes(b"jpg")
        (self.base / "area.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_map_is_named_instead_of_key_error(self):
        with self.assertRaises(SystemExit) as e:
            evidence.build({"camera": [1, 2]}, self.base, self.base / "out.jpg")
        self.assertIn("missing 'map'", str(e.exception.code))

    def test_map_without_georeference(self):
        (self.base / "area.json").unlink()
        self.assertIn("no georeference", evidence.check_spec({"map": "area.jpg"}, self.base)[0])

    def test_item_keys_and_panel_images(self):
        errs = evidence.check_spec({"map": "area.jpg", "labels": [{"at": [1, 2]}], "lines": [{"from": [1, 2], "bearing": 3}],
                                    "panels": [{"image": "sv1.jpg"}]}, self.base)
        self.assertEqual(len(errs), 3)
        self.assertIn("labels[0] is missing 'text'", errs[0])
        self.assertIn("lines[0] is missing 'length_m'", errs[1])
        self.assertIn("panels[0] image not found", errs[2])

    def test_valid_spec(self):
        self.assertEqual(evidence.check_spec({"map": "area.jpg", "labels": [{"at": [1, 2], "text": "x"}]}, self.base), [])

    def test_invalid_path_and_item_types_are_named(self):
        cases = [
            ([], "JSON object"),
            *[({"map": value}, "'map'") for value in (None, 7, "")],
            *[({"map": "area.jpg", key: value}, repr(key))
              for key, value in (("labels", None), ("labels", {}), ("lines", "bad"), ("panels", None))],
            *[({"map": "area.jpg", key: [value]}, f"{key}[0]")
              for key, value in (("labels", None), ("labels", "at text"), ("lines", 3))],
            ({"map": "area.jpg", "panels": [{"image": None}]}, "panels[0]"),
        ]
        for spec, expected in cases:
            with self.subTest(spec=spec):
                self.assertTrue(any(expected in error for error in evidence.check_spec(spec, self.base)))

    def test_missing_files_are_reported_together(self):
        errors = evidence.check_spec({"map": "missing.jpg", "panels": [{"image": "missing-panel.jpg"}]}, self.base)
        self.assertEqual(len(errors), 3)
        self.assertIn("map not found", errors[0])
        self.assertIn("no georeference", errors[1])
        self.assertIn("panels[0] image not found", errors[2])

    def test_invalid_spec_cli_exits_without_traceback(self):
        spec_path = self.base / "bad.json"
        spec_path.write_text(json.dumps({"map": None, "labels": None, "panels": [{"image": None}]}), encoding="utf-8")
        out = self.base / "out.jpg"
        result = subprocess.run([sys.executable, str(Path(evidence.__file__)), str(spec_path), "--out", str(out)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1)
        for expected in ("'map'", "'labels'", "panels[0]", "evidence.py --help"):
            self.assertIn(expected, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(out.exists())


class DeviceTests(unittest.TestCase):
    @staticmethod
    def _torch(cuda=False, mps=False):
        return SimpleNamespace(__version__="2.0.0+test",
                               cuda=SimpleNamespace(is_available=lambda: cuda),
                               backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: mps)))

    def _pick(self, value=None, **have):
        env = {} if value is None else {"GEO_DEVICE": value}
        with patch.dict(os.environ, env, clear=True):
            return _device.torch_device(self._torch(**have))

    def _exit_message(self, value, **have):
        with self.assertRaises(SystemExit) as caught:
            self._pick(value, **have)
        message = str(caught.exception.code)
        self.assertEqual(len(message.splitlines()), 1)
        self.assertIn("torch 2.0.0+test", message)
        return message

    def test_auto_selection_order(self):
        self.assertEqual(self._pick(cuda=True, mps=True), "cuda")
        self.assertEqual(self._pick(cuda=True), "cuda")
        self.assertEqual(self._pick(mps=True), "mps")
        self.assertEqual(self._pick(), "cpu")
        self.assertEqual(self._pick("", cuda=True), "cuda")

    def test_explicit_override(self):
        self.assertEqual(self._pick("cpu", cuda=True, mps=True), "cpu")
        self.assertEqual(self._pick("cuda", cuda=True, mps=True), "cuda")
        self.assertEqual(self._pick("mps", cuda=True, mps=True), "mps")
        self.assertEqual(self._pick(" CUDA ", cuda=True), "cuda")

    def test_invalid_value_exits_with_one_line(self):
        for value in ("gpu", "cuda:0", "auto"):
            message = self._exit_message(value, cuda=True)
            self.assertIn(repr(value), message)
            self.assertIn("cpu, cuda, mps", message)

    def test_unavailable_device_exits_instead_of_falling_back(self):
        message = self._exit_message("cuda", mps=True)
        self.assertIn("GEO_DEVICE=cuda", message)
        self.assertIn("cuda=False, mps=True", message)
        message = self._exit_message("mps", cuda=True)
        self.assertIn("GEO_DEVICE=mps", message)
        self.assertIn("cuda=True, mps=False", message)

    def test_both_model_scripts_use_the_shared_helper(self):
        scripts = Path(_device.__file__).parent
        for name in ("match.py", "sat_scan.py"):
            text = (scripts / name).read_text(encoding="utf-8")
            self.assertIn("self.dev = torch_device(torch)", text)
            self.assertNotIn("mps.is_available", text)


HEIC_HEAD = b"\x00\x00\x00\x1cftypheic" + b"\x00" * 64


class ImageLoadingTests(unittest.TestCase):
    """scripts/_image.py: explicit formats, content sniffing, RAW rejection, failure categories, folder discovery."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _save(self, name, fmt="JPEG", color=(200, 30, 30), size=(32, 24)):
        Image.new("RGB", size, color).save(self.d / name, format=fmt)
        return self.d / name

    def _category(self, path):
        with self.assertRaises(_image.ImageReadError) as caught:
            _image.open_image(path)
        self.assertEqual(len(caught.exception.reason.splitlines()), 1)
        return caught.exception.category, caught.exception.reason

    def test_sniff_reads_content_not_suffix(self):
        heads = {
            "JPEG": b"\xff\xd8\xff\xe0", "PNG": b"\x89PNG\r\n\x1a\n", "WEBP": b"RIFF\x00\x00\x00\x00WEBPVP8 ",
            "GIF": b"GIF89a", "HEIF": HEIC_HEAD[:16], "AVIF": b"\x00\x00\x00\x1cftypavif", "TIFF": b"II*\x00\x08\x00\x00\x00",
            "TEXT": b'{"status":400}',
        }
        for kind, head in heads.items():
            self.assertEqual(_image.sniff(head, ".jpg"), kind)
        self.assertEqual(_image.sniff(b"II*\x00\x10\x00\x00\x00CR\x02\x00", ".jpg"), "RAW")      # Canon CR2
        self.assertEqual(_image.sniff(b"\x00\x00\x00\x18ftypcrx ", ".cr3"), "RAW")               # Canon CR3
        self.assertEqual(_image.sniff(b"MM\x00*\x00\x00\x00\x08", ".NEF"), "RAW")               # TIFF-based RAW by suffix
        self.assertEqual(_image.sniff(b"FUJIFILMCCD-RAW 0201", ".raf"), "RAW")
        self.assertIsNone(_image.sniff(b"\x00\x01\x02\x03", ".jpg"))

    def test_supported_formats_open_whatever_the_suffix(self):
        for name, fmt in (("a.jpg", "JPEG"), ("b.png", "PNG"), ("c.webp", "WEBP"), ("d.jpg", "PNG"), ("e", "JPEG"), ("f.gif", "GIF")):
            with _image.open_image(self._save(name, fmt)) as im:
                self.assertEqual((im.format, im.size), (fmt, (32, 24)))

    @unittest.skipUnless(_image.HEIF, "pillow-heif not installed")
    def test_heic_decodes_and_keeps_metadata(self):
        ex = Image.Exif()
        ex[0x8769] = {0xA405: 26}                       # FocalLengthIn35mmFilm
        Image.new("RGB", (40, 30), (0, 0, 255)).save(self.d / "phone.heic", format="HEIF", exif=ex)
        im = _image.open_image(self.d / "phone.heic")
        self.assertEqual((im.format, im.size), ("HEIF", (40, 30)))
        self.assertGreater(im.getpixel((0, 0))[2], 200)
        self.assertEqual(im.getexif().get_ifd(0x8769).get(0xA405), 26)

    def test_failure_categories(self):
        (self.d / "empty.jpg").write_bytes(b"")
        (self.d / "error.jpg").write_bytes(b'{"status":400,"msg":"bad"}')
        (self.d / "noise.jpg").write_bytes(b"\x00\x01\x02\x03" * 20)
        (self.d / "IMG_1.CR2").write_bytes(b"II*\x00\x10\x00\x00\x00CR\x02\x00" + b"\x00" * 64)
        (self.d / "IMG_2.dng").write_bytes(b"II*\x00\x08\x00\x00\x00" + b"\x00" * 64)
        full = self._save("full.jpg").read_bytes()
        (self.d / "cut.jpg").write_bytes(full[: len(full) // 2])
        Image.new("RGB", (8, 8)).save(self.d / "frame.ppm", format="PPM")
        expect = {"empty.jpg": "empty", "error.jpg": "not-image", "noise.jpg": "not-image", "IMG_1.CR2": "raw",
                  "IMG_2.dng": "raw", "cut.jpg": "decode-error", "frame.ppm": "unsupported"}
        for name, category in expect.items():
            got, reason = self._category(self.d / name)
            self.assertEqual(got, category, f"{name}: {reason}")
        self.assertIn("export it as JPEG or PNG", self._category(self.d / "IMG_1.CR2")[1])

    def test_tiff_based_raw_is_rejected_by_content(self):
        """Structure of an iPhone ProRAW DNG: the first image is a full-size 8-bit preview marked reduced-resolution,
        the real 10-bit linear raw sits in a SubIFD. Pillow would read the preview, whatever the suffix."""
        from PIL import TiffImagePlugin
        for name, tags in (("dng_named.jpg", {254: 1, 50706: b"\x01\x06\x00\x00"}), ("preview_only", {254: 1, 330: 100})):
            info = TiffImagePlugin.ImageFileDirectory_v2()
            for k, v in tags.items():
                info[k] = v
            if 50706 in tags:
                info.tagtype[50706] = 1
            Image.new("RGB", (40, 30), (90, 120, 150)).save(self.d / name, format="TIFF", tiffinfo=info)
            category, reason = self._category(self.d / name)
            self.assertEqual(category, "raw", name)
            self.assertIn("embedded preview", reason)
        self._save("plain.tif", "TIFF")
        with _image.open_image(self.d / "plain.tif") as im:
            self.assertEqual(im.format, "TIFF")

    def test_heif_failure_keeps_its_cause(self):
        (self.d / "x.jpg").write_bytes(HEIC_HEAD)
        with patch.object(_image, "HEIF", False):
            self.assertEqual(self._category(self.d / "x.jpg")[0], "missing-decoder")
        if _image.HEIF:
            category, reason = self._category(self.d / "x.jpg")
            self.assertEqual(category, "decode-error")
            self.assertIn("HEIF that could not be decoded (", reason)     # the decoder's own message, not a guess

    def test_find_images_keeps_old_order_then_adds_new_formats(self):
        for name, fmt in (("b.jpg", "JPEG"), ("a.jpeg", "JPEG"), ("c.png", "PNG"), ("d.webp", "WEBP"),
                          ("e.HEIC", "PNG"), ("f.heif", "PNG"), ("g.bin", "PNG"), ("h", "JPEG")):
            self._save(name, fmt)
        (self.d / "notes.json").write_text("{}", encoding="utf-8")
        (self.d / "readme.txt").write_text("hello", encoding="utf-8")
        (self.d / "IMG_3.CR2").write_bytes(b"II*\x00\x10\x00\x00\x00CR\x02\x00")
        names = [f.name for f in _image.find_images(self.d)]
        old = sorted(["b.jpg", "a.jpeg"]) + ["c.png"]
        self.assertEqual(names[:3], old)
        self.assertEqual(sorted(names[3:]), sorted(["d.webp", "e.HEIC", "f.heif", "IMG_3.CR2", "g.bin", "h"]))
        self.assertNotIn("notes.json", names)
        self.assertNotIn("readme.txt", names)

    def test_open_or_exit_is_one_line(self):
        (self.d / "IMG_4.NEF").write_bytes(b"MM\x00*\x00\x00\x00\x08" + b"\x00" * 64)
        with self.assertRaises(SystemExit) as caught:
            _image.open_or_exit(self.d / "IMG_4.NEF", "photo")
        message = str(caught.exception.code)
        self.assertEqual(len(message.splitlines()), 1)
        self.assertIn("cannot read photo", message)
        self.assertIn("export it as JPEG or PNG", message)

    def test_photo_scripts_exit_cleanly_on_raw_and_read_heic(self):
        script = Path(_image.__file__).with_name("imgprep.py")
        raw = self.d / "IMG_5.ARW"
        raw.write_bytes(b"II*\x00\x08\x00\x00\x00" + b"\x00" * 64)
        r = subprocess.run([sys.executable, str(script), "zoom", str(raw), "--box", "0,0,4,4", "--out", str(self.d / "z.png")],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)
        self.assertIn("export it as JPEG or PNG", r.stderr)
        if _image.HEIF:
            Image.new("RGB", (40, 30), (0, 200, 0)).save(self.d / "p.heic", format="HEIF")
            r = subprocess.run([sys.executable, str(script), "zoom", str(self.d / "p.heic"), "--box", "0,0,20,20", "--out", str(self.d / "z.png")],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((self.d / "z.png").exists())


class MatchImageLoadingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _save(self, name, fmt="JPEG", color=(200, 30, 30)):
        Image.new("RGB", (32, 24), color).save(self.d / name, format=fmt)

    def _load(self, files):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            ok, ims = match._open_images(files)
        return ok, ims, err.getvalue()

    def test_unreadable_files_are_skipped_with_reasons(self):
        self._save("a.jpg")
        self._save("b.jpg", color=(30, 200, 30))
        (self.d / "heic.jpg").write_bytes(HEIC_HEAD)
        (self.d / "error.jpg").write_bytes('{"status":400,"msg":"bad"}'.encode())
        (self.d / "empty.jpg").write_bytes(b"")
        full = (self.d / "a.jpg").read_bytes()
        (self.d / "cut.jpg").write_bytes(full[: len(full) // 2])
        ok, ims, err = self._load(sorted(self.d.glob("*.jpg")))
        self.assertEqual([f.name for f in ok], ["a.jpg", "b.jpg"])
        self.assertEqual([im.size for im in ims], [(32, 24), (32, 24)])
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("skipped 4 of 6 files", err)
        self.assertIn("text, not an image", err)
        self.assertIn("1 empty file", err)

    def test_missing_decoder_is_reported_as_such(self):
        self._save("a.jpg")
        (self.d / "h.heic").write_bytes(HEIC_HEAD)
        with patch.object(_image, "HEIF", False):
            ok, _, err = self._load([self.d / "a.jpg", self.d / "h.heic"])
        self.assertEqual([f.name for f in ok], ["a.jpg"])
        self.assertIn("needs pillow-heif", err)

    def test_all_unreadable_exits_with_one_line(self):
        (self.d / "x.jpg").write_bytes(b"<html>blocked</html>")
        (self.d / "y.CR2").write_bytes(b"II*\x00\x10\x00\x00\x00CR\x02\x00")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            match._open_images([self.d / "x.jpg", self.d / "y.CR2"])
        self.assertEqual(len(str(caught.exception.code).splitlines()), 1)
        self.assertIn("none of the 2 candidate files", str(caught.exception.code))

    def _candidates(self):
        args = SimpleNamespace(images=str(self.d), items=None, panos=None, cache=str(self.d / ".cache"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            items, ims = match._load_candidates(args)
        return items, ims, err.getvalue()

    def test_mixed_folder_keeps_ids_aligned(self):
        self._save("first.jpg", color=(255, 0, 0))
        (self.d / "middle.jpg").write_bytes(HEIC_HEAD)
        self._save("last.png", "PNG", color=(0, 0, 255))
        self._save("UPPER.WEBP", "WEBP", color=(0, 255, 0))
        self._save("renamed.bin", "PNG", color=(255, 255, 0))
        items, ims, _ = self._candidates()
        ids = [it["id"] for it in items]
        self.assertEqual(ids[:2], ["first", "last"])
        self.assertEqual(sorted(ids[2:]), ["UPPER", "renamed"])
        colors = {it["id"]: im.convert("RGB").getpixel((0, 0)) for it, im in zip(items, ims)}
        self.assertGreater(colors["first"][0], 240)
        self.assertGreater(colors["last"][2], 240)
        self.assertGreater(colors["UPPER"][1], 240)

    @unittest.skipUnless(_image.HEIF, "pillow-heif not installed")
    def test_heic_only_folder(self):
        for i, c in enumerate(((255, 0, 0), (0, 0, 255))):
            Image.new("RGB", (40, 30), c).save(self.d / f"p{i}.HEIC", format="HEIF")
        Image.new("RGB", (40, 30), (0, 200, 0)).save(self.d / "phone.jpg", format="HEIF")
        items, ims, err = self._candidates()
        self.assertEqual([it["id"] for it in items], ["phone", "p0", "p1"])
        self.assertEqual([im.size for im in ims], [(40, 30)] * 3)
        self.assertEqual(err, "")


# EXIF orientation -> the transpose a viewer applies to the stored pixels; storing = applying the inverse
VIEW = {2: Image.Transpose.FLIP_LEFT_RIGHT, 3: Image.Transpose.ROTATE_180, 4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE, 6: Image.Transpose.ROTATE_270, 7: Image.Transpose.TRANSVERSE, 8: Image.Transpose.ROTATE_90}
INVERSE = {Image.Transpose.ROTATE_270: Image.Transpose.ROTATE_90, Image.Transpose.ROTATE_90: Image.Transpose.ROTATE_270}


def upright_control(w=60, h=40):
    """Asymmetric: every flip or rotation of it is a different image."""
    im = Image.new("RGB", (w, h), (230, 230, 230))
    im.paste((220, 30, 30), (0, 0, w // 3, h // 2))           # red, top-left
    im.paste((30, 30, 220), (w - w // 4, h // 2, w, h))       # blue, bottom-right
    im.paste((30, 160, 30), (w // 2, 0, w // 2 + 4, h // 4))  # green tick near the top
    return im


def stored_as(control, o):
    if o == 1:
        return control.copy()
    t = VIEW[o]
    return control.transpose(INVERSE.get(t, t))


def save_oriented(control, o, path, fmt="PNG", **kw):
    ex = Image.Exif()
    ex[0x0112] = o
    stored_as(control, o).save(path, format=fmt, exif=ex, **kw)


class OrientationTests(unittest.TestCase):
    """Stage 2 of #29: pixel coordinates refer to the upright frame; EXIF orientation is applied exactly once."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.control = upright_control()

    def test_all_eight_orientations_match_the_upright_control(self):
        for o in range(1, 9):
            save_oriented(self.control, o, self.d / f"o{o}.png")
            im = _image.open_photo(self.d / f"o{o}.png")
            self.assertEqual(im.size, self.control.size, f"orientation {o}")
            self.assertEqual(im.convert("RGB").tobytes(), self.control.tobytes(), f"orientation {o}")
            self.assertEqual(_image.upright(im).tobytes(), im.tobytes(), f"orientation {o} applied twice")

    def test_jpeg_orientations_match_within_compression_noise(self):
        ref = np.asarray(self.control, dtype=np.int16)
        for o in (3, 6, 8):
            save_oriented(self.control, o, self.d / f"o{o}.jpg", fmt="JPEG", quality=95)
            got = np.asarray(_image.open_photo(self.d / f"o{o}.jpg").convert("RGB"), dtype=np.int16)
            self.assertEqual(got.shape, ref.shape)
            self.assertLess(np.abs(got - ref).mean(), 3, f"orientation {o}")

    def test_normal_photo_is_returned_untouched(self):
        save_oriented(self.control, 1, self.d / "o1.png")
        im = _image.open_image(self.d / "o1.png")
        self.assertIs(_image.upright(im), im)

    @unittest.skipUnless(_image.HEIF, "pillow-heif not installed")
    def test_heif_is_not_rotated_again(self):
        """libheif applies irot/imir itself and pillow-heif resets the EXIF tag; the HEIF spec says EXIF orientation is
        ignored. Whatever the EXIF says, the result must be exactly what the HEIF decoder produced."""
        for o in (1, 3, 6, 8):
            save_oriented(self.control, o, self.d / f"h{o}.heic", fmt="HEIF", quality=-1)
            decoded = Image.open(self.d / f"h{o}.heic")
            decoded.load()
            im = _image.open_photo(self.d / f"h{o}.heic")
            self.assertEqual(_image.orientation(im), 1)
            self.assertEqual(im.size, decoded.size)
            self.assertEqual(im.tobytes(), decoded.tobytes(), f"orientation {o}")

    def test_frames_are_read_from_the_record_not_guessed_from_the_size(self):
        self.assertEqual(_image.frame_of({}), "stored")                     # written before orientation was applied
        self.assertEqual(_image.frame_of({"frame": "upright"}), "upright")
        self.assertEqual(_image.frame_of({}, "upright"), "upright")         # callers can explicitly override the default
        with self.assertRaises(SystemExit):
            _image.frame_of({"frame": "sideways"})
        for control in (self.control, upright_control(40, 40)):              # square: no size tells the frames apart
            for o in range(1, 9):
                save_oriented(control, o, self.d / f"o{o}.png")
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    stored = _image.open_photo(self.d / f"o{o}.png", frame="stored", size=stored_as(control, o).size)
                self.assertEqual(stored.convert("RGB").tobytes(), stored_as(control, o).tobytes(), f"orientation {o}")
                self.assertEqual("stored frame" in err.getvalue(), o != 1, err.getvalue())
                self.assertNotIn("warning", err.getvalue())
                up = _image.open_photo(self.d / f"o{o}.png", size=control.size)
                self.assertEqual(up.convert("RGB").tobytes(), control.tobytes(), f"orientation {o}")

    def test_a_size_that_fits_neither_frame_is_flagged(self):
        save_oriented(self.control, 6, self.d / "o6.png")                    # 40x60 stored, 60x40 upright
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            _image.open_photo(self.d / "o6.png", size=[40, 60])               # a stored-frame size in an upright record
        self.assertIn('set "frame": "stored"', err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            _image.open_photo(self.d / "o6.png", size=[120, 80])              # same aspect, scaled: fine
        self.assertEqual(err.getvalue(), "")

    def test_match_query_and_candidates_use_the_upright_frame(self):
        save_oriented(self.control, 6, self.d / "q.png")
        save_oriented(self.control, 8, self.d / "c8.png")
        self.control.save(self.d / "c1.png")
        self.assertEqual(match.open_photo(self.d / "q.png", "query").convert("RGB").tobytes(), self.control.tobytes())
        args = SimpleNamespace(images=str(self.d), items=None, panos=None, cache=str(self.d / ".cache"))
        with contextlib.redirect_stderr(io.StringIO()):
            items, ims = match._load_candidates(args)
        for it, im in zip(items, ims):
            self.assertEqual(im.convert("RGB").tobytes(), self.control.tobytes(), it["id"])

    def _run(self, script, *args):
        r = subprocess.run([sys.executable, str(Path(_image.__file__).with_name(script)), *map(str, args)],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_imgprep_crops_use_the_upright_frame(self):
        save_oriented(self.control, 6, self.d / "o6.png")
        self.control.save(self.d / "up.png")
        for name in ("o6", "up"):
            self._run("imgprep.py", "zoom", self.d / f"{name}.png", "--box", "0,0,30,20", "--scale", "2", "--out", self.d / f"z_{name}.png")
        self.assertEqual(Image.open(self.d / "z_o6.png").tobytes(), Image.open(self.d / "z_up.png").tobytes())

    def _pose_case(self, w, h):
        lat0, lon0 = 30.0, 120.0
        rec = {"_frame": {"lat0": lat0, "lon0": lon0, "image_size": [w, h]},
               "_params": [0.0, 0.0, 10.0, 0.0, 0.0, 0.0, 200.0]}         # east, north, height, heading, pitch, roll, focal_px
        pts = [{"name": "A", "ll": [lat0 + 0.0009, lon0 + 0.0002], "h": 5.0, "px": [w * 5 // 8, h * 9 // 16]},
               {"name": "B", "ll": [lat0 + 0.0009, lon0 - 0.0003], "h": 0.0, "px": [w // 4, h * 5 // 8]}]
        return rec, pts

    def _draw(self, photo, rec, pts, out):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            pose.draw(photo, rec, pts, out, observed=True)
        with Image.open(out) as im:
            return im.tobytes(), err.getvalue()

    def test_pose_overlay_uses_the_upright_frame(self):
        for w, h in ((240, 160), (160, 160)):
            scene = upright_control(w, h)
            scene.save(self.d / "up.png")
            rec, pts = self._pose_case(w, h)
            rec["_frame"]["frame"] = "upright"
            control, _ = self._draw(self.d / "up.png", rec, pts, self.d / "d_up.png")
            for o in range(2, 9):
                save_oriented(scene, o, self.d / f"o{o}.png")
                got, err = self._draw(self.d / f"o{o}.png", rec, pts, self.d / f"d_o{o}.png")
                self.assertEqual(got, control, f"{w}x{h} orientation {o}")
                self.assertEqual(err, "")

    def test_old_pose_records_draw_as_they_did(self):
        """A pose.json from before #29 has no frame: its points were drawn on the stored pixels, and still are. Covers the
        cases a size check can't tell apart: mirror / 180° (2, 3, 4) keep the size, and a square photo keeps it under 6."""
        for (w, h), orients in (((240, 160), (2, 3, 4, 6, 8)), ((160, 160), (6, 3))):
            scene = upright_control(w, h)
            for o in orients:
                stored = stored_as(scene, o)
                stored.save(self.d / "plain.png")                             # what the old pose.draw opened: no EXIF to apply
                save_oriented(scene, o, self.d / f"o{o}.png")
                rec, pts = self._pose_case(*stored.size)                      # recorded on the stored pixels
                old, _ = self._draw(self.d / "plain.png", rec, pts, self.d / "d_plain.png")
                got, err = self._draw(self.d / f"o{o}.png", rec, pts, self.d / f"d_o{o}.png")
                self.assertEqual(got, old, f"{w}x{h} orientation {o}")
                self.assertIn(f"EXIF orientation {o}", err)
                self.assertNotIn("warning", err)

    def _pose_spec(self, W=400, H=300):
        lat0, lon0 = 30.0, 120.0
        kx, ky = pose._frame(lat0)
        truth = np.array([3.0, -4.0, 12.0, 20.0, -2.0, 0.0, 350.0])
        enu = np.array([[-60, 220, 0], [40, 260, 25], [90, 180, 5], [-20, 140, 15], [10, 320, 40], [-90, 300, 8]], float)
        uv, _ = pose.project(truth, enu, W, H)
        return {"image_size": [W, H], "init": {"at": [lat0, lon0], "height": 10, "heading": 15, "pitch": 0, "hfov": 60},
                "points": [{"name": f"P{i}", "ll": [lat0 + n / ky, lon0 + e / kx], "h": u, "px": [float(x), float(y)]}
                           for i, ((e, n, u), (x, y)) in enumerate(zip(enu, uv))]}
    def test_pose_solve_records_the_frame_of_its_points(self):
        spec = self._pose_spec()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pose.solve(spec, 50, 2)["_frame"]["frame"], "stored")
            self.assertEqual(pose.solve(dict(spec, frame="stored"), 50, 2)["_frame"]["frame"], "stored")
            self.assertEqual(pose.solve(dict(spec, frame="upright"), 50, 2)["_frame"]["frame"], "upright")

    def _solve_photo(self, spec, photo, name):
        source, saved, overlay = (self.d / f"{name}{suffix}" for suffix in ("_spec.json", "_pose.json", ".png"))
        source.write_text(json.dumps(spec), encoding="utf-8")
        self._run("pose.py", "solve", source, "--photo", photo, "--out", overlay, "--save", saved,
                  "--search-radius", 50, "--restarts", 2)
        with Image.open(overlay) as im:
            pixels = im.tobytes()
        return json.loads(saved.read_text(encoding="utf-8")), pixels

    def test_legacy_pose_specs_solve_in_the_stored_frame(self):
        """Re-running an old input spec must preserve its overlay, not just reading an old solved pose.json."""
        for w, h, o in ((400, 300, 3), (400, 300, 6), (300, 300, 6)):
            with self.subTest(size=(w, h), orientation=o):
                scene = upright_control(w, h)
                stored = stored_as(scene, o)
                stored.save(self.d / "plain.png")
                save_oriented(scene, o, self.d / "oriented.png")
                spec = self._pose_spec(*stored.size)                         # legacy input: no frame key
                before, control = self._solve_photo(spec, self.d / "plain.png", "legacy_control")
                after, actual = self._solve_photo(spec, self.d / "oriented.png", "legacy_oriented")
                self.assertEqual(after["_frame"]["frame"], "stored")
                self.assertEqual(after["_params"], before["_params"])
                self.assertEqual(actual, control)

    def test_new_pose_specs_solve_in_the_upright_frame(self):
        scene = upright_control(400, 300)
        scene.save(self.d / "upright.png")
        spec = dict(self._pose_spec(), frame="upright")
        before, control = self._solve_photo(spec, self.d / "upright.png", "upright_control")
        for o in (3, 6):
            with self.subTest(orientation=o):
                save_oriented(scene, o, self.d / "oriented.png")
                after, actual = self._solve_photo(spec, self.d / "oriented.png", "upright_oriented")
                self.assertEqual(after["_frame"]["frame"], "upright")
                self.assertEqual(after["_params"], before["_params"])
                self.assertEqual(actual, control)

    def test_terrain_ridge_points_and_overlay_use_the_upright_frame(self):
        w, h = 240, 160
        scene = Image.new("RGB", (w, h), (210, 220, 235))         # sky
        ImageDraw.Draw(scene).polygon([(0, 70), (120, 40), (240, 90), (240, 160), (0, 160)], fill=(60, 70, 60))
        scene.save(self.d / "up.png")
        save_oriented(scene, 6, self.d / "o6.png")
        save_oriented(scene, 3, self.d / "o3.png")
        out = {}
        for name in ("up", "o6", "o3"):
            self._run("terrain.py", "ridge", self.d / f"{name}.png", "--x0", 10, "--x1", 230, "--step", 20,
                      "--out", self.d / f"r_{name}.json", "--png", self.d / f"r_{name}.png")
            out[name] = json.loads((self.d / f"r_{name}.json").read_text(encoding="utf-8"))
        for name in ("o6", "o3"):
            self.assertEqual(out[name]["image_size"], [w, h])
            self.assertEqual(out[name]["frame"], "upright")
            self.assertEqual(out[name]["ridge"], out["up"]["ridge"], name)
            self.assertEqual(Image.open(self.d / f"r_{name}.png").tobytes(), Image.open(self.d / "r_up.png").tobytes(), name)

    def test_exif_gives_the_upright_size_only_when_it_differs_in_frame(self):
        self.control.save(self.d / "o1.jpg", quality=95)
        save_oriented(self.control, 6, self.d / "o6.jpg", fmt="JPEG", quality=95)
        save_oriented(self.control, 3, self.d / "o3.jpg", fmt="JPEG", quality=95)
        out = {}
        for name in ("o1", "o6", "o3"):
            out[name] = json.loads(self._run("exif.py", self.d / f"{name}.jpg").stdout.splitlines()[0])
        self.assertEqual(sorted(out["o1"]), ["file", "size"])                 # ordinary photos: output as before
        self.assertEqual((out["o6"]["size"], out["o6"]["orientation"], out["o6"]["upright_size"]), ([40, 60], 6, [60, 40]))
        self.assertEqual((out["o3"]["size"], out["o3"]["orientation"], out["o3"]["upright_size"]), ([60, 40], 3, [60, 40]))
        if _image.HEIF:
            save_oriented(self.control, 6, self.d / "h6.heic", fmt="HEIF", quality=-1)
            self.assertNotIn("orientation", json.loads(self._run("exif.py", self.d / "h6.heic").stdout.splitlines()[0]))

    def _fit_sheet(self, photo, ridge, out):
        import terrain
        rec = {"f": 200.0, "cam": [30.0, 120.0], "g": 0.0, "H": 0.0, "cc": 0.0, "hit": 1, "name": "x",
               "rms": 0.1, "flatpen": 0.0, "total": 0.1}
        args = SimpleNamespace(sheet_width=120, sheet_cols=1, range=1000, zoom=12, cache=self.d, proxy=None,
                               allow_missing=False, eye=1.6, near=40)
        with patch.object(terrain, "DEM", side_effect=SystemExit("offline")), contextlib.redirect_stderr(io.StringIO()) as err:
            terrain._fit_sheet([rec], ridge, photo, out, args, np.arange(0, 360, 1.0), 8)
        with Image.open(out) as im:
            return im.tobytes(), err.getvalue()

    def test_fit_sheet_draws_old_ridge_records_on_the_stored_pixels(self):
        for w, h in ((240, 160), (160, 160)):
            scene = upright_control(w, h)
            scene.save(self.d / "up.png")
            for o in (3, 6):
                save_oriented(scene, o, self.d / f"o{o}.png")
                stored = stored_as(scene, o)
                stored.save(self.d / "plain.png")
                old = {"image_size": list(stored.size), "hrow": stored.height / 2, "cx": stored.width / 2, "flat": None,
                       "ridge": [[10, 20], [stored.width - 30, 45]]}          # ridge.json from before #29: no frame
                want, _ = self._fit_sheet(self.d / "plain.png", old, self.d / "s_plain.jpg")
                got, err = self._fit_sheet(self.d / f"o{o}.png", old, self.d / f"s_o{o}.jpg")
                self.assertEqual(got, want, f"{w}x{h} orientation {o}")
                self.assertIn("stored frame", err)
                new = dict(old, image_size=[w, h], hrow=h / 2, cx=w / 2, ridge=[[10, 20], [w - 30, 45]], frame="upright")
                want, _ = self._fit_sheet(self.d / "up.png", new, self.d / "s_up.jpg")
                got, err = self._fit_sheet(self.d / f"o{o}.png", new, self.d / f"s2_o{o}.jpg")
                self.assertEqual(got, want, f"{w}x{h} orientation {o}, upright record")
                self.assertNotIn("stored frame", err)

    def test_spacing_warns_when_an_old_ridge_meets_upright_columns(self):
        import geo
        save_oriented(self.control, 6, self.d / "o6.png")
        self.control.save(self.d / "up.png")
        pts = [[5, 10], [20, 12], [35, 9], [50, 14]]
        cases = {"old_o6": ({"photo": "o6.png", "ridge": pts}, True),       # photo path relative to the ridge file
                 "new_o6": ({"photo": str(self.d / "o6.png"), "frame": "upright", "ridge": pts}, False),
                 "old_up": ({"photo": str(self.d / "up.png"), "ridge": pts}, False),
                 "handwritten": ({"5": 10, "20": 12, "35": 9, "50": 14}, False)}
        for name, (rec, warn) in cases.items():
            path = self.d / f"{name}.json"
            path.write_text(json.dumps(rec), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(geo._spacing_ridge(str(path))["pts"], [[float(x), float(y)] for x, y in pts])
            self.assertEqual("stored frame" in err.getvalue(), warn, f"{name}: {err.getvalue()}")


class WorkingCopyTests(unittest.TestCase):
    """Stage 3 of #29: a lossless upright PNG only for photos that need one, original EXIF kept, uploads compatible."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.control = upright_control()

    def _exif(self, o):
        ex = Image.Exif()
        ex[0x0112] = o
        ex[0x8769] = {0xA405: 26}                         # FocalLengthIn35mmFilm
        return ex

    def test_native_upright_photos_are_used_as_they_are(self):
        self.control.save(self.d / "a.jpg", exif=self._exif(1))
        self.control.save(self.d / "b.png")
        self.assertIsNone(_image.write_working_copy(self.d / "a.jpg", self.d / "w" / "a.png"))
        self.assertIsNone(_image.write_working_copy(self.d / "b.png", self.d / "w" / "b.png"))
        self.assertFalse((self.d / "w").exists())

    def test_oriented_jpeg_gets_an_upright_png_with_its_exif(self):
        stored_as(self.control, 6).save(self.d / "o6.jpg", exif=self._exif(6), quality=95)
        before = (self.d / "o6.jpg").read_bytes()
        info = _image.write_working_copy(self.d / "o6.jpg", self.d / "w" / "o6.png")
        self.assertEqual((self.d / "o6.jpg").read_bytes(), before)               # original untouched
        self.assertEqual(info["reason"], "EXIF orientation 6 applied")
        self.assertEqual((info["original_size"], info["working_size"]), ([40, 60], [60, 40]))
        with Image.open(info["working"]) as wc:
            self.assertEqual(wc.format, "PNG")
            self.assertEqual(wc.tobytes(), _image.open_photo(self.d / "o6.jpg").convert("RGB").tobytes())   # lossless
            self.assertEqual(wc.getexif().get(0x0112), 1)
            self.assertEqual(wc.getexif().get_ifd(0x8769).get(0xA405), 26)
            self.assertIsNone(_image.working_copy_reason(wc))                  # a copy never needs another

    def test_webp_and_heic_get_a_copy(self):
        self.control.save(self.d / "w.webp", exif=self._exif(1))
        self.assertEqual(_image.write_working_copy(self.d / "w.webp", self.d / "w" / "w.png")["reason"], "WEBP decoded to PNG")
        if _image.HEIF:
            self.control.save(self.d / "h.heic", format="HEIF", exif=self._exif(1))
            info = _image.write_working_copy(self.d / "h.heic", self.d / "w" / "h.png")
            self.assertEqual(info["reason"], "HEIC/HEIF decoded to PNG")
            with Image.open(info["working"]) as wc:
                self.assertEqual(wc.getexif().get_ifd(0x8769).get(0xA405), 26)

    def test_unreadable_photo_raises(self):
        (self.d / "IMG.CR2").write_bytes(b"II*\x00\x10\x00\x00\x00CR\x02\x00" + b"\x00" * 64)
        with self.assertRaises(_image.ImageReadError):
            _image.write_working_copy(self.d / "IMG.CR2", self.d / "w" / "IMG.png")

    def test_revimg_uploads_a_compatible_copy_only_when_needed(self):
        import revimg
        self.control.save(self.d / "plain.jpg")
        stored_as(self.control, 8).save(self.d / "side.jpg", exif=self._exif(8))
        self.assertEqual(revimg._upload_path(self.d / "plain.jpg", self.d / "rev"), self.d / "plain.jpg")
        up = revimg._upload_path(self.d / "side.jpg", self.d / "rev")
        self.assertEqual(up, self.d / "rev" / "upload" / "side.png")
        with Image.open(up) as im:
            self.assertEqual(im.size, (60, 40))


class RevimgInputTests(unittest.TestCase):
    """revimg.py: every input gets its own upload copy, and an input the shared loader rejects is reported, never uploaded.
    The engines are fakes that note which file they were handed and what it shows at the moment of the call."""

    COLORS = {"red": (220, 30, 30), "green": (30, 160, 30), "blue": (30, 30, 220), "gray": (128, 128, 128)}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.out = self.d / "rev"

    def _solid(self, color, path, **kw):
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (48, 32), self.COLORS[color]).save(path, **kw)
        return path

    def _color_of(self, path):
        with Image.open(path) as im:
            px = im.convert("RGB").getpixel((24, 16))
        return min(self.COLORS, key=lambda c: sum((a - b) ** 2 for a, b in zip(self.COLORS[c], px)))

    def _unreadable(self):
        raw = self.d / "IMG_1.CR2"
        raw.write_bytes(b"II*\x00\x10\x00\x00\x00CR\x02\x00" + b"\x00" * 64)
        page = self.d / "tile.jpg"                                   # an error reply saved under an image name
        page.write_bytes(b'{"status":429,"msg":"rate limited"}')
        return raw, page

    def _search(self, call):
        sent = {"baidu": [], "yandex": []}

        async def baidu(ctx, up, shot, *rest):
            sent["baidu"].append((Path(up), self._color_of(up)))
            return {"guess": [], "links": []}

        async def yandex(ctx, up, shot):
            sent["yandex"].append((Path(up), self._color_of(up)))
            return {"guess": [], "links": []}

        browser = SimpleNamespace(new_context=AsyncMock(), close=AsyncMock())
        manager = AsyncMock()
        manager.__aenter__.return_value = object()
        fake = SimpleNamespace(async_playwright=lambda: manager)
        with patch.dict(sys.modules, {"playwright.async_api": fake}), \
                patch.object(revimg, "launch_browser", AsyncMock(return_value=(browser, "test"))) as launch, \
                patch.object(revimg, "_baidu", new=baidu), patch.object(revimg, "_yandex", new=yandex):
            got = call()
        return got, sent, launch

    def _main(self, *argv):
        err, code = io.StringIO(), 0
        with patch.object(sys, "argv", ["revimg.py", *map(str, argv)]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                revimg.main()
            except SystemExit as e:
                code = e.code
        return code, err.getvalue()

    def test_names_are_unique_without_regard_to_case(self):
        self.assertEqual(revimg._names([Path("photo.jpg"), Path("v/left_crop.jpg")]), ["photo", "left_crop"])
        self.assertEqual(revimg._names([Path("a/photo.jpg"), Path("b/PHOTO.png"), Path("c/02_photo.jpg"), Path("x.jpg")]),
                         ["01_photo", "02_PHOTO", "03_02_photo", "x"])

    def test_same_stems_upload_their_own_pixels(self):
        images = {self._solid("red", self.d / "a" / "photo.webp", lossless=True): "red",
                  self._solid("green", self.d / "b" / "Photo.webp", lossless=True): "green",   # same stem but for case
                  self._solid("gray", self.d / "c" / "photo.jpg", quality=95): "gray"}         # needs no copy
        if _image.HEIF:
            images[self._solid("blue", self.d / "d" / "photo.heic", format="HEIF", quality=-1)] = "blue"
        results, sent, _ = self._search(lambda: asyncio.run(revimg.run(list(images), ["baidu", "yandex"], self.out, "direct")))
        for eng, calls in sent.items():
            self.assertEqual([c for _, c in calls], list(images.values()), eng)
            self.assertEqual(len({p for p, _ in calls}), len(images), f"{eng}: two inputs shared one upload file")
        self.assertEqual(sent["baidu"][2][0], self.d / "c" / "photo.jpg")
        records = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(self.out.glob("*.json"))]
        self.assertEqual(len(records), 2 * len(images))
        for r in results + records:                                 # each record names the original whose pixels went out
            self.assertEqual(self._color_of(r.get("uploaded", r["image"])), images[Path(r["image"])], r)

    def test_unreadable_inputs_are_reported_and_not_uploaded(self):
        raw, page = self._unreadable()
        good = self._solid("red", self.d / "good.webp", lossless=True)
        results, sent, _ = self._search(lambda: asyncio.run(revimg.run([raw, page, good], ["baidu", "yandex"], self.out, "direct")))
        for eng, calls in sent.items():
            self.assertEqual([c for _, c in calls], ["red"], eng)
        bad = {(Path(r["image"]).name, r["engine"]): r["unreadable"] for r in results if r.get("unreadable")}
        self.assertEqual(bad, {("IMG_1.CR2", "baidu"): "raw", ("IMG_1.CR2", "yandex"): "raw",
                               ("tile.jpg", "baidu"): "not-image", ("tile.jpg", "yandex"): "not-image"})
        rec = json.loads((self.out / "IMG_1_baidu.json").read_text(encoding="utf-8"))
        self.assertIn("export it as JPEG or PNG", rec["error"])
        self.assertNotIn("screenshot", rec)
        self.assertEqual([f.name for f in (self.out / "upload").iterdir()], ["good.png"])

    def test_cli_exits_2_naming_each_unreadable_input(self):
        raw, page = self._unreadable()
        good = self._solid("red", self.d / "good.jpg")
        (code, err), sent, _ = self._search(lambda: self._main(raw, page, good, "--out-dir", self.out))
        self.assertEqual(code, 2)
        self.assertIn("2 of 3 images could not be read and were not uploaded", err)
        self.assertIn(f"{raw} (camera RAW", err)
        self.assertIn(f"{page} (text, not an image", err)
        self.assertEqual([p for p, _ in sent["baidu"]], [good])

    def test_cli_with_only_unreadable_inputs_starts_no_browser(self):
        raw, page = self._unreadable()
        (code, err), sent, launch = self._search(lambda: self._main(raw, page, "--out-dir", self.out))
        self.assertEqual(code, 2)
        self.assertEqual(launch.await_count, 0)
        self.assertEqual(sent, {"baidu": [], "yandex": []})
        self.assertEqual(sorted(f.name for f in self.out.iterdir()),
                         ["IMG_1_baidu.json", "IMG_1_yandex.json", "tile_baidu.json", "tile_yandex.json"])
        r = subprocess.run([sys.executable, revimg.__file__, str(raw), "--out-dir", str(self.d / "rev2")],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("1 of 1 images could not be read", r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class IntakeStatusTests(unittest.TestCase):
    """intake.py as a whole: working-copy routing, partial results, exit status. Child scripts run for real, with this Python."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def _intake(self, photo, *extra, fail=()):
        import intake
        original = intake._run

        def run(cmd, **kwargs):
            name = Path(str(cmd[2])).name
            if name in fail:
                return 1, "", f"{name}: simulated failure"
            return original([sys.executable, *cmd[2:]], **kwargs)

        out = self.d / "out"
        code = 0
        with patch.object(intake, "_run", side_effect=run), \
                patch.object(sys, "argv", ["intake.py", str(photo), "--out-dir", str(out), "--no-rev", *extra]), \
                contextlib.redirect_stdout(io.StringIO()):
            try:
                intake.main()
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
        return code, out, json.loads((out / "intake.json").read_text(encoding="utf-8")), (out / "intake.md").read_text(encoding="utf-8")

    def test_ordinary_photo_uses_the_original(self):
        upright_control(120, 80).save(self.d / "photo.jpg")
        code, out, js, md = self._intake(self.d / "photo.jpg", "--no-ocr")
        self.assertEqual((code, js["result"], js["input"]), (0, "ok", None))
        self.assertFalse((out / "work").exists())
        self.assertTrue((out / "edges" / "photo_top.jpg").exists())
        self.assertNotIn("Result:", md)

    def test_oriented_photo_is_routed_through_an_upright_copy(self):
        upright_control(120, 80).save(self.d / "photo.png")
        _, out, _, _ = self._intake(self.d / "photo.png", "--no-ocr")
        control = {f.name: f.read_bytes() for f in (out / "edges").glob("*.jpg")}
        (self.d / "out").rename(self.d / "out_control")
        save_oriented(upright_control(120, 80), 6, self.d / "photo.png")
        code, out, js, md = self._intake(self.d / "photo.png", "--no-ocr")
        self.assertEqual(code, 0)
        self.assertEqual(js["input"]["reason"], "EXIF orientation 6 applied")
        self.assertTrue((out / "work" / "photo.png").exists())
        got = {f.name: f.read_bytes() for f in (out / "edges").glob("*.jpg")}
        self.assertEqual(len(control), 8)
        self.assertEqual(got, control)                       # same names, same upright crops as the upright control
        self.assertIn("keep passing the original photo", md)

    @unittest.skipUnless(_image.HEIF, "pillow-heif not installed")
    def test_heic_photo_runs_every_step_with_metadata_from_the_original(self):
        ex = Image.Exif()
        ex[0x8769] = {0xA405: 24}
        upright_control(120, 80).save(self.d / "IMG_1.HEIC", format="HEIF", exif=ex)
        code, out, js, _ = self._intake(self.d / "IMG_1.HEIC", "--no-ocr")
        self.assertEqual((code, js["result"]), (0, "ok"))
        self.assertEqual(js["input"]["reason"], "HEIC/HEIF decoded to PNG")
        self.assertEqual(len(list((out / "edges").glob("IMG_1_*.jpg"))), 8)
        self.assertEqual(js["exif"]["file"], str((self.d / "IMG_1.HEIC").resolve()))

    def test_partial_failure_is_reported_as_partial(self):
        upright_control(120, 80).save(self.d / "photo.jpg")
        code, _, js, md = self._intake(self.d / "photo.jpg", fail=("ocr.py",))
        self.assertEqual((code, js["result"]), (0, "partial"))
        self.assertIn("**Result: partial.** Failed: ocr", md)

    def test_all_visual_steps_failing_exits_nonzero_and_keeps_the_report(self):
        upright_control(120, 80).save(self.d / "photo.jpg")
        code, _, js, md = self._intake(self.d / "photo.jpg", fail=("imgprep.py", "ocr.py"))
        self.assertEqual((code, js["result"]), (1, "failed"))
        self.assertIn("**Result: failed.**", md)
        self.assertEqual(js["status"]["exif"], "ok")

    def test_disabled_step_is_not_a_failure(self):
        upright_control(120, 80).save(self.d / "photo.jpg")
        code, _, js, _ = self._intake(self.d / "photo.jpg", "--no-ocr", fail=("ocr.py",))
        self.assertEqual((code, js["result"]), (0, "ok"))
        self.assertNotIn("ocr", js["status"])

    def test_unreadable_photo_exits_2_with_a_report(self):
        (self.d / "IMG_2.CR2").write_bytes(b"II*\x00\x10\x00\x00\x00CR\x02\x00" + b"\x00" * 64)
        code, out, js, md = self._intake(self.d / "IMG_2.CR2")
        self.assertEqual(code, 2)
        self.assertEqual((js["result"], js["input"]["error"]), ("input unreadable", "raw"))
        self.assertIn("export it as JPEG or PNG", md)
        self.assertFalse(any((out / "edges").glob("*")))


if __name__ == "__main__":
    unittest.main()
