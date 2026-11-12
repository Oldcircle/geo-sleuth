#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline example checks. Run: uv run examples/monid-maps-photo/test_maps_photo.py"""
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

import maps_photo


def response(status, body):
    stream = io.BytesIO(json.dumps(body).encode())
    stream.status = status
    return stream


class MapsPhotoTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"MONID_API_KEY": "fake-key"})
        env.start()
        self.addCleanup(env.stop)
        builder = patch.object(maps_photo.urllib.request, "build_opener")
        self.opener = builder.start().return_value
        self.addCleanup(builder.stop)

    def test_request_and_output(self):
        self.opener.open.return_value = response(200, {"output": {"date": "2026"}})
        self.assertEqual(maps_photo.maps_photo("photo_ID"), {"date": "2026"})
        req = self.opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.monid.ai/v1/run")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("Authorization"), "Bearer fake-key")
        self.assertEqual(req.get_header("Content-type"), "application/json; charset=utf-8")
        self.assertEqual(json.loads(req.data), {
            "provider": "litescrape", "endpoint": "/google/maps-photo",
            "input": {"queryParams": {"data_id": "photo_ID"}, "body": {}, "pathParams": {}}})

    def test_missing_key_does_not_request(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Set MONID_API_KEY"):
                maps_photo.maps_photo("photo_ID")
        self.opener.open.assert_not_called()

    @patch.object(maps_photo.time, "sleep")
    def test_polling(self, sleep):
        self.opener.open.side_effect = [response(202, {"runId": "run-1"}),
            response(200, {"status": "RUNNING"}),
            response(200, {"status": "COMPLETED", "output": {"date": "2026"}})]
        self.assertEqual(maps_photo.maps_photo("photo_ID"), {"date": "2026"})
        for call in self.opener.open.call_args_list[1:]:
            self.assertEqual(call.args[0].full_url, "https://api.monid.ai/v1/runs/run-1")
            self.assertEqual(call.args[0].get_method(), "GET")

    def test_provider_errors_preserve_status_and_body(self):
        for status in (400, 404, 429):
            with self.subTest(status=status):
                self.opener.open.return_value = response(200, {"status": "COMPLETED",
                    "providerResponse": {"httpStatus": status, "error": {"message": "no match"}}})
                with self.assertRaises(maps_photo.ProviderError) as caught:
                    maps_photo.maps_photo("photo_ID")
                self.assertEqual(caught.exception.status, status)
                self.assertEqual(caught.exception.error, {"message": "no match"})

    def test_monid_http_error(self):
        self.opener.open.side_effect = urllib.error.HTTPError(
            "https://api.monid.ai/v1/run", 401, "bad key", {}, None)
        with self.assertRaises(urllib.error.HTTPError):
            maps_photo.maps_photo("photo_ID")

    @patch.object(maps_photo.time, "sleep")
    def test_terminal_failures(self, sleep):
        for status in ("FAILED", "TIMED_OUT", "STOPPED", "BLOCKED"):
            self.opener.open.side_effect = [response(202, {"runId": "run-1"}),
                                          response(200, {"status": status})]
            with self.assertRaisesRegex(RuntimeError, status):
                maps_photo.maps_photo("photo_ID")

    @patch.object(maps_photo.time, "monotonic", side_effect=[0, 0, 61])
    def test_poll_timeout(self, monotonic):
        self.opener.open.return_value = response(202, {"runId": "run-1"})
        with self.assertRaisesRegex(TimeoutError, "timed out"):
            maps_photo.maps_photo("photo_ID")

    def test_cli_writes_json(self):
        path = MagicMock()
        args = MagicMock(data_id="photo_ID", out=path, proxy=None)
        with patch.object(maps_photo.argparse.ArgumentParser, "parse_args", return_value=args), \
                patch.object(maps_photo, "maps_photo", return_value={"date": "2026"}), \
                patch("builtins.print"):
            maps_photo.main()
        path.write_text.assert_called_once_with('{\n  "date": "2026"\n}\n', encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
