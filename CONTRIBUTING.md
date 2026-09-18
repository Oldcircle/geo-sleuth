# Contributing

Thanks for looking. Three kinds of contribution help most; each has a short rule so the result stays usable by the model.

## 1. A clue that transfers

`skills/geo-sleuth/references/clues/china.md` and `global.md` hold the clues the model reads while looking at a photo. Add one when it tells a place apart from its neighbours and you can point at a source (a public table, an official page, a photo you took). One landmark is not a clue; a bus livery that only one city uses is.

## 2. A data source

Lookup tables live in `skills/geo-sleuth/data/`. Every file carries `_meta` with the source URL, fetch date, row count and licence, and `clues.py update` must be able to re-fetch it. Live queries (OSM, tiles, panoramas) go into a script with a `--proxy` flag and an entry in `references/data-sources.md`.

## 3. A run that went wrong

Open an issue with: your own photo (or a description if you would rather not post it), what the skill concluded, what the truth was, and which step first went off. The first wrong step is the useful part.

## House rules

- Every conclusion in the docs must map to a command and a file. No prose rules that cannot be checked.
- Do not add anything that identifies a real person, a private home or a specific case answer.
- Scripts declare their dependencies in the PEP 723 header and run with `uv run`.
- Keep `SKILL.md` under control: long material goes into `references/`.
- Use the skill on photos you took yourself, or whose photographer agreed.

## Translations

`README.md` is the source of truth. When you change it, the Chinese README (`README.zh-CN.md`) should keep the same structure, the same images and the same numbers. A translation that only updates one section is still welcome.
