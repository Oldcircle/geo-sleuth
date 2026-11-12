# Google Maps photo metadata through Monid

Monid lets agents and developers query data providers with one API key, pay per call.
This standalone example resolves a Google Maps photo ID through Litescrape;
the skill's existing scripts and defaults stay unchanged.

## Run

Use a photo you took yourself or whose photographer agreed.
Take its `data_id` from a Google Maps `photo_meta_link`.

```bash
export MONID_API_KEY='your-key'
uv run examples/monid-maps-photo/maps_photo.py "$PHOTO_ID" photo.json
```

The command prints `photo.json`, which contains the provider's JSON metadata
(contributor, place, coordinates and date). It does not upload a photo.
Without `MONID_API_KEY`, it exits with a message before making a request.

The example uses the shared `GEO_PROXY` setting; `--proxy direct` selects a
direct connection. It submits to `/v1/run` and polls asynchronous runs for
up to 60 seconds. Monid HTTP failures and terminal run failures exit with an
error. Litescrape errors retain their HTTP status and error body, including
404 when no photo matches; no output file is written on failure.

## Offline checks

```bash
uv run examples/monid-maps-photo/test_maps_photo.py
```

The tests mock HTTP, set a fake key and check the request and output file.

[Monid docs](https://docs.monid.ai?utm_source=github&utm_medium=oss-pr&utm_campaign=oldcircle-geo-sleuth)
· [Get an API key](https://monid.ai?utm_source=github&utm_medium=oss-pr&utm_campaign=oldcircle-geo-sleuth&aid=OSS-PR)
