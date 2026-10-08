# Contributing

Thanks for looking. Four kinds of contribution help most; each has a short rule so the result stays usable by the model.

## 1. A clue that transfers

`skills/geo-sleuth/references/clues/global.md` holds the clues that tell countries apart; clues that only work inside one country live in that country's region pack (`regions/<cc>/clues.md`). Add one when it tells a place apart from its neighbours and you can point at a source (a public table, an official page, a photo you took). One landmark is not a clue; a bus livery that only one city uses is. Entry format: `references/clues/README.md`.

## 2. A region pack

Everything that only works inside one country goes in `skills/geo-sleuth/regions/<cc>/`: a manifest, clue entries, prefix tables (plates, area codes, postcodes) with tests, preferred services. Packs hold **data and documents only** (`.json`, `.md`), so a pack PR is reviewed as data. The contract, the table format and the three tiers (clues only → lookup tables → anything that needs code) are in [`regions/README.md`](skills/geo-sleuth/regions/README.md). Start from `regions/_template/`; before opening the PR:

```bash
uv run skills/geo-sleuth/scripts/regions.py lint <cc>    # must print ok
uv run skills/geo-sleuth/scripts/regions.py show <cc>    # what the agent will see
```

A key that covers several places lists every one of them; never merge two places into one name. Global tables (calling codes, driving side, territories) stay in `data/`, each with `_meta` (source URL, fetch date, row count, licence) and a parser in `scripts/refresh.py`. Live queries use the shared `_net.py` helpers; add new sources to `references/data-sources.md`.

## 3. A change to the core scripts

Open it as its own PR, separate from any region pack, and bring four things:

1. **The failure.** A photo or case the current code gets wrong or can't separate, with the output that shows it.
2. **A general change.** Something that holds for other photos, not a parameter tuned to this one. If it adds freedom (a new fitted parameter, a looser filter), cap it, and keep a switch that reproduces the old output.
3. **Before and after** on that case, runnable by a reviewer.
4. **No regression elsewhere**: an operator-level check on cases the change wasn't built for, plus `tests/`.

The model is the [desert case](README.md#2-a-desert-skyline-one-degree-off) and [`examples/desert-roll-fix/`](examples/desert-roll-fix/): the skill was stuck on a real photo, solving camera roll in `terrain.py fit` (capped at 1°, `--roll-max 0` = old behaviour) solved it, the true site went from #8 at 12.0 px to #1 at 6.2 px, and 8 synthetic skylines plus an earlier real case checked that it didn't break anything.

## 4. A run that went wrong

Open an issue with: your own photo (or a description if you would rather not post it), what the skill concluded, what the truth was, and which step first went off. The first wrong step is the useful part. For setup or connection failures, include the relevant output of `uv run skills/geo-sleuth/scripts/doctor.py --network --json`, your OS and the failing command. Remove private paths or source text before posting.

## House rules

- Every conclusion in the docs must map to a command and a file. No prose rules that cannot be checked.
- Do not add anything that identifies a real person or a private home, and keep case answers out of the skill itself (`SKILL.md`, `references/`, region packs): an agent reading them would be told the answer.
- Scripts declare their dependencies in the PEP 723 header and run with `uv run`.
- Keep `SKILL.md` under control: long material goes into `references/`.
- `SKILL.md`, `references/`, script output and comments are in English. Chinese stays only where it is data: text found in photos (plates, signs), queries sent to Chinese services, and patterns that match Chinese text.
- Use the skill on photos you took yourself, or whose photographer agreed.

## Translations

`README.md` is the source of truth. When you change it, the Chinese README (`README.zh-CN.md`) should keep the same structure, the same images and the same numbers. A translation that only updates one section is still welcome.

## Runtime checks

Run `uv run skills/geo-sleuth/tests/test_runtime.py`, `test_board.py` and `test_regions.py` for offline regressions (routing, browser fallback, diagnostics, the candidate board, region packs). The tests use only loopback HTTP and mocked service calls; they do not upload photos or download ML models. Use `doctor.py --network` separately for live reachability.
