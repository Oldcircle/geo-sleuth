# Desert skyline: before and after the roll fix

The data behind [case 2](../../README.md#2-a-desert-skyline-one-degree-off), and the example of what a core change should show: a real photo the skill could not solve, the same photo solved after a general change, and a way for anyone to check.

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

Before, the true site hides in a band of near-equal scores and nothing separates them. After, every site gets a little better, because each can absorb some tilt, but only the true one drops by half: its residual was the tilt. The solved roll is about 1° (the printout's `roll`).

## Why this is the bar

- **A real failure first.** The skill was stuck on this photo: the top 25 sites in Qinghai sat between 9.6 and 11.7 px.
- **A general change.** Solving camera roll is about phones, not about this desert. It is capped (`--roll-max`, default 1°) so a wrong site can't buy a better score by tilting the image, and `--roll-max 0` reproduces the old output value for value.
- **Solved after.** The same photo, the same sites: the true one breaks away.
- **No regression elsewhere.** On 8 synthetic skylines (random heading, focal length, ±1° roll) the median position error went from 324 to 238 m, untilted cases included (324 → 89 m); on an earlier real case the true cluster moved from #3 to #1. A looser cap (1.5°, 2.5°) let wrong sites catch up, which is why the default is 1°.

A pull request that changes the core scripts should bring the same four things: the photo or case it fails on, the change, the before and after, and a check on cases it wasn't built for.
