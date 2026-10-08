# Desert skyline: before and after the roll fix

The data behind [case 2](../../README.md#2-a-desert-skyline-one-degree-off). It shows what a change to the core scripts should come with: a real photo the skill could not solve, the same photo solved after a general change, and commands anyone can rerun.

| File | What it is |
|---|---|
| `ridge.json` | the ridge line traced from the photo (`terrain.py ridge`), 127 points on a 2048 × 1152 frame |
| `clusters.json` | the 12 best candidate sites from a blind run's scan of Qinghai's power lines (`terrain.py scan`); the true one is `hit0` |

## Run it

From the repository root (downloads elevation tiles on first run, a minute or two):

```bash
cd examples/desert-roll-fix
S=../../skills/geo-sleuth/scripts
# before: the image is assumed level, as fit did before the change
uv run $S/terrain.py fit --hits clusters.json --ridge ridge.json --min-peak 3 --cam-flat 30 --eye 10 --range 20000 --roll-max 0 --out before.json
# after: roll solved together with the horizon offset (default --roll-max 1)
uv run $S/terrain.py fit --hits clusters.json --ridge ridge.json --min-peak 3 --cam-flat 30 --eye 10 --range 20000 --out after.json
```

## What you should see

| | true site (`hit0`) | best other site | spread of the other 11 |
|---|---|---|---|
| before, `--roll-max 0` | **#8**, 12.0 px | 10.2 px | 10.2–13.6 px |
| after, default | **#1, 6.2 px** | 9.9 px | 9.1–10.4 px |

Before the change, the true site is one of many with nearly equal scores. After it, every site improves a little, since each can absorb some tilt, but only the true site drops by about half, because most of its error was the tilt. The solved roll is about 1° (the printout's `roll`).

## Why this is the reference for core changes

The skill was stuck on this photo: the top 25 sites in Qinghai scored between 9.6 and 11.7 px. The fix is not specific to this desert; any handheld photo can be tilted. The roll is capped (`--roll-max`, default 1°) so that a wrong site can't improve its score by tilting the image, and `--roll-max 0` gives the old output value for value. With the fix, the same photo and the same sites, the true site separates from the rest.

It was also checked on cases it wasn't built for. On 8 synthetic skylines (random heading, focal length, ±1° roll) the median position error went from 324 to 238 m, and from 324 to 89 m for the untilted ones. On an earlier real case the true cluster moved from #3 to #1. Looser caps (1.5°, 2.5°) let wrong sites catch up, so the default stayed at 1°.

A pull request that changes the core scripts should include the same things: the photo or case it fails on, the change, a before and after anyone can rerun, and a check on cases it wasn't built for.
