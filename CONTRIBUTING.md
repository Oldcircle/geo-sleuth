# Contributing

Thanks for looking. Three kinds of contribution help most; each has a short rule so the result stays usable by the model.

## 1. A clue that transfers

`skills/geo-sleuth/references/clues/china.md` and `global.md` hold the clues the model reads while looking at a photo. Add one when it tells a place apart from its neighbours and you can point at a source (a public table, an official page, a photo you took). One landmark is not a clue; a bus livery that only one city uses is.

## 2. A data source

Lookup tables live in `skills/geo-sleuth/data/`. Every file carries `_meta` with the source URL, fetch date, row count and licence, and `clues.py update` must be able to re-fetch it. Live queries (OSM, tiles, panoramas) use the shared `_net.py` helpers. Add an entry in `references/data-sources.md`.

## 3. A run that went wrong

Open an issue with: your own photo (or a description if you would rather not post it), what the skill concluded, what the truth was, and which step first went off. The first wrong step is the useful part. For setup or connection failures, include the relevant output of `uv run skills/geo-sleuth/scripts/doctor.py --network --json`, your OS and the failing command. Remove private paths or source text before posting.

## House rules

- Every conclusion in the docs must map to a command and a file. No prose rules that cannot be checked.
- Do not add anything that identifies a real person, a private home or a specific case answer.
- Scripts declare their dependencies in the PEP 723 header and run with `uv run`.
- Keep `SKILL.md` under control: long material goes into `references/`.
- `SKILL.md`, `references/`, script output and comments are in English. Chinese stays only where it is data: text found in photos (plates, signs), queries sent to Chinese services, and patterns that match Chinese text.
- Use the skill on photos you took yourself, or whose photographer agreed.

## Translations

`README.md` is the source of truth. When you change it, the Chinese README (`README.zh-CN.md`) should keep the same structure, the same images and the same numbers. A translation that only updates one section is still welcome.

## Runtime checks

Run `uv run skills/geo-sleuth/tests/test_runtime.py` for offline routing, browser fallback and diagnostics regressions. The test uses only loopback HTTP and mocked service calls; it does not upload photos or download ML models. Use `doctor.py --network` separately for live reachability.
