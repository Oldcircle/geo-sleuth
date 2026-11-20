#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Resolve a Google Maps photo ID through Monid and write its metadata as JSON."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/geo-sleuth/scripts"))
from _net import resolve_proxy  # noqa: E402


class ProviderError(Exception):
    """Keep Litescrape's status and error separate from Monid failures."""
    def __init__(self, status, error):
        self.status, self.error = status, error
        super().__init__(f"Litescrape HTTP {status}: {json.dumps(error, ensure_ascii=False)}")


def maps_photo(data_id, *, proxy=None, timeout=60):
    key = os.environ.get("MONID_API_KEY")
    if not key:
        raise ValueError("Set MONID_API_KEY to run this optional example.")
    value = resolve_proxy(proxy)
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": value, "https": value} if value else {}))
    headers = {"Authorization": f"Bearer {key}",
               "Content-Type": "application/json; charset=utf-8"}
    payload = {"provider": "litescrape", "endpoint": "/google/maps-photo",
               "input": {"queryParams": {"data_id": data_id}, "body": {}, "pathParams": {}}}
    deadline = time.monotonic() + timeout

    def request(url, data=None):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Monid run timed out")
        req = urllib.request.Request(url, data=data, headers=headers)
        with opener.open(req, timeout=remaining) as response:
            return response.status, json.load(response)

    status, run = request("https://api.monid.ai/v1/run",
                          json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if status == 202:
        run_id = urllib.parse.quote(run["runId"], safe="")
        while run.get("status") not in ("COMPLETED", "FAILED", "TIMED_OUT", "STOPPED", "BLOCKED"):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Monid run timed out")
            time.sleep(min(2, remaining))
            _, run = request(f"https://api.monid.ai/v1/runs/{run_id}")
    if run.get("status") not in (None, "COMPLETED"):
        raise RuntimeError(f"Monid run {run['status']}")
    provider = run.get("providerResponse") or {}
    if provider.get("httpStatus", 200) >= 400:
        raise ProviderError(provider["httpStatus"], provider.get("error"))
    return run["output"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_id", help="Google Maps photo ID (from a photo_meta_link)")
    parser.add_argument("out", type=Path, help="output JSON file")
    parser.add_argument("--proxy", help="proxy URL or 'direct'; otherwise uses GEO_PROXY")
    args = parser.parse_args()
    try:
        output = maps_photo(args.data_id, proxy=args.proxy)
    except urllib.error.HTTPError as exc:
        sys.exit(f"Monid HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
    except (ValueError, ProviderError, RuntimeError, OSError) as exc:
        sys.exit(str(exc))
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
