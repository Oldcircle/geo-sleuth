#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""Offline runtime regressions. Run: uv run skills/geo-sleuth/tests/test_runtime.py"""
from __future__ import annotations

import asyncio
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import _net
import _browser
import baidu_pano
import clues
import doctor
import ocr
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
            await revimg.run([Path("photo.jpg")], ["baidu", "yandex"], Path(folder), "direct", ["school"], ["bing"])
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


class IndiaLookupTests(unittest.TestCase):
    """India tables (data/in_*.json) and lookups; China lookups must keep working alongside."""

    def states(self, r):
        return [m.get("admin1") for m in r["matches"]]

    def test_plate_state_and_rto(self):
        r = clues.lookup_plate("MH 12 AB 1234")
        self.assertEqual(r["kind"], "plate")
        self.assertEqual(self.states(r), ["Maharashtra"])
        self.assertIn("Pune", r["matches"][0]["admin2"])
        self.assertEqual(self.states(clues.lookup_plate("ka05mn1234")), ["Karnataka"])

    def test_plate_bh_series_is_country_only(self):
        r = clues.lookup_plate("22 BH 1234 AA")
        self.assertEqual([m.get("country") for m in r["matches"]], ["India"])
        self.assertFalse(any(m.get("admin1") for m in r["matches"]))

    def test_plate_former_codes_and_moved_registrations(self):
        self.assertEqual(self.states(clues.lookup_plate("OR 02")), ["Odisha"])
        self.assertEqual(self.states(clues.lookup_plate("TS 09")), ["Telangana"])
        self.assertEqual(self.states(clues.lookup_plate("AP 09")), ["Telangana"])   # pre-2014 Hyderabad registration
        self.assertEqual(clues.lookup_plate("XX 12")["matches"], [])

    def test_chinese_plate_still_routes_to_china_table(self):
        r = clues.lookup_plate("渝G")
        self.assertTrue(r["matches"])
        self.assertEqual(r["matches"][0]["admin1"], "重庆市")

    def test_std_code_forms(self):
        for value in ("0484 2345678", "(0484) 2345678", "+91 484 2345678", "0091-484-2345678"):
            with self.subTest(value=value):
                self.assertEqual(self.states(clues.lookup_std_code(value)), ["Kerala"])
        r = clues.lookup_std_code("080 2222 3333")
        self.assertEqual(self.states(r), ["Karnataka"])

    def test_std_code_state_resolution_inside_multi_state_circles(self):
        cases = {"0651": "Jharkhand", "07752": "Chhattisgarh", "0870": "Telangana", "03592": "Sikkim", "01982": "Ladakh",
                 "04368": "Puducherry", "0832": "Goa", "0260": "Dadra and Nagar Haveli and Daman and Diu"}
        for code, state in cases.items():
            with self.subTest(code=code):
                self.assertEqual(self.states(clues.lookup_std_code(code)), [state])
        self.assertGreater(len(clues.lookup_std_code("02875")["matches"]), 1)   # Una-Diu straddles a state/UT border

    def test_mobile_number_is_not_a_place(self):
        r = clues.lookup_std_code("+91 98765 43210")
        self.assertEqual(r["matches"], [])
        self.assertIn("mobile", r["note"])

    def test_cli_routes_india_kinds_and_keeps_china_area_codes(self):
        script = Path(clues.__file__)
        def run(*argv):
            out = subprocess.run([sys.executable, str(script), "lookup", *argv, "--json"], capture_output=True, text=True, check=True).stdout
            return json.loads(out)
        self.assertEqual(run("area-code", "+91 40 2345 6789")["kind"], "std-code")
        self.assertEqual(run("area-code", "0755", "--country", "IN")["matches"][0]["admin1"], "Madhya Pradesh")
        self.assertEqual(run("area-code", "023")["kind"], "area-code")
        self.assertTrue(run("area-code", "023")["matches"])
        self.assertEqual(run("pin", "560001")["matches"][0]["admin1"], "Karnataka")
        self.assertEqual(run("admin", "Orissa", "--country", "IN")["matches"][0]["admin1"], "Odisha")

    def test_pin_prefixes(self):
        self.assertEqual(self.states(clues.lookup_pin("403 001")), ["Goa"])          # 3-digit exception inside Maharashtra's 40
        self.assertEqual(self.states(clues.lookup_pin("396210")), ["Dadra and Nagar Haveli and Daman and Diu"])
        self.assertEqual(self.states(clues.lookup_pin("110001")), ["Delhi"])
        self.assertEqual(clues.lookup_pin("999001")["matches"], [])                   # Army Postal Service
        self.assertEqual(clues.lookup_pin("012345")["matches"], [])

    def test_admin_and_script(self):
        r = clues.lookup_in_admin("TS")
        self.assertEqual(self.states(r), ["Telangana"])
        self.assertIn("Telugu", r["matches"][0]["note"])
        self.assertEqual(len(clues.lookup_in_admin(None)["matches"]), 36)
        self.assertEqual(set(self.states(clues.lookup_script("Gurmukhi")))  & {"Punjab"}, {"Punjab"})
        self.assertIn("Tamil Nadu", self.states(clues.lookup_script("Tamil")))
        self.assertEqual(self.states(clues.lookup_script("Meitei")), ["Manipur"])

    def test_india_tables_have_pinned_sources(self):
        for table in ("in_plates", "in_std_codes", "in_pin_prefixes", "in_admin"):
            with self.subTest(table=table):
                d = clues.load(table)
                self.assertTrue(d)
                wiki = [u for u in (clues.SOURCES[table] if isinstance(clues.SOURCES[table], list) else [clues.SOURCES[table]]) if "wikipedia" in u]
                self.assertTrue(all("oldid=" in u for u in wiki), wiki)


class TesseractTests(unittest.TestCase):
    TSV = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n" \
          "1\t1\t0\t0\t0\t0\t0\t0\t900\t400\t-1\t\n" \
          "5\t1\t1\t1\t1\t1\t40\t50\t200\t60\t95.5\tजयपुर\n" \
          "5\t1\t1\t1\t1\t2\t260\t52\t80\t58\t90.5\t45\n" \
          "5\t1\t2\t1\t1\t1\t40\t160\t300\t50\t-1\t \n" \
          "5\t1\t2\t1\t1\t2\t40\t160\t300\t50\t88\tJAIPUR\n"

    def test_tsv_words_become_lines(self):
        items = ocr.TesseractBackend.parse_tsv(self.TSV)
        self.assertEqual([i["text"] for i in items], ["जयपुर 45", "JAIPUR"])
        self.assertEqual(items[0]["box"], [40, 50, 340, 110])
        self.assertAlmostEqual(items[0]["conf"], 0.93)

    def test_missing_language_data_is_reported(self):
        listing = SimpleNamespace(stdout='List of available languages in "/x" (2):\neng\nosd\n', stderr="")
        with patch.object(ocr.shutil, "which", return_value="/usr/bin/tesseract"), patch.object(ocr.subprocess, "run", return_value=listing):
            with self.assertRaisesRegex(RuntimeError, "missing: hin"):
                ocr.TesseractBackend("hin+eng")
            self.assertEqual(ocr.TesseractBackend("eng").langs, "eng")

    def test_absent_tesseract_gives_install_hint(self):
        with patch.object(ocr.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "tesseract-ocr"):
                ocr.TesseractBackend("hin")


if __name__ == "__main__":
    unittest.main()
