# rail-skyline-session: case-specific scripts for episode 13

The 5 scripts in this directory are the case scripts for the episode-13 photo. Every parameter is tuned to that photo (focal length, horizon row, 26 ridge pixels, 17 pier pixel columns, three bridge-distance windows, candidate center coordinates). They are kept only as a reproduction record and are not guaranteed to run on another photo.

Day to day, use the skill subcommands (`terrain.py scan / ridge / fit`, `imgprep.py piers`, `geo.py spacing`), not these scripts; the new subcommands were checked against these scripts on the same photo.

The method itself is written into the skill docs: `skills/geo-sleuth/references/corridors.md` 4.3 (linear feature × terrain scan) and `references/geometry.md` 7.4, 7.7 (batch skyline scoring, solving the camera position from evenly spaced structures).

## Dependencies

The scripts import `skills/geo-sleuth/scripts/terrain.py` from this repository via `sys.path` (`DEM`, `_dest_np`, `_fetch`), so they must run inside this repository's directory layout. Run them with `uv run <script>`; dependencies are declared in the file headers. Elevation tiles come from AWS Terrain Tiles and are cached in `.geo-cache/dem/` under the current directory.

## Input files

Input data is not in the repository. Both geojson files are railway-bridge queries against Overpass made with `skills/geo-sleuth/scripts/osm.py geom`; the other inputs are outputs of the previous script.

| Script | Input | Output |
|---|---|---|
| `rail_mtn_scan.py` | `argv[1]`: railway-bridge geojson for a large region (Overpass railway-bridge query via `osm.py geom`) | `argv[2]`: hit-point json (per point: coordinates, max elevation angle, bearing, flat-horizon length) |
| `skyfit2.py` | `argv[1]`: hit-point json from the previous step; `argv[3]`: range of hits to process, `a:b`; `rail_bridges.geojson` in the current directory (the same Overpass railway-bridge query) | `argv[2]`: camera-position score json (run in batches during the session; outputs named `f2_0.json`, `f2_1.json`…) |
| `railgeom.py` | `f2_?.json` in the current directory (previous step's output, merged via glob); `rail_bridges.geojson` | `f3_sel.json` (camera positions sorted by skyline + bridge-distance total score, deduplicated) |
| `refine.py` | `argv[1]`: center `lat,lon` (a candidate picked from `f3_sel.json`); `argv[2]`: radius in m; `rail_bridges.geojson` | `argv[3]`: fine-search result json |
| `joint.py` | `qy_rail.geojson` in the current directory (railway-line query via `osm.py geom`; the script takes one line by name); the candidate center is hard-coded in the script (from the refine result) | `joint.json` (top 25 by joint pier-spacing + skyline score) |

## Run order

```
rail_mtn_scan.py → skyfit2.py → railgeom.py → refine.py → joint.py
```

1. `rail_mtn_scan.py`: sample a point every 400 m along the bridge lines, compute the 360° horizon from the DEM, keep points that are "flat nearby, a mountain within a few km, a flat horizon run next to the mountain".
2. `skyfit2.py`: place camera positions on a 250 m grid within a 2 km radius of each hit, search heading × focal length × horizon offset, score against the photo's ridgeline.
3. `railgeom.py`: filter the previous step's camera positions by bridge-distance windows at the left edge, center, and right edge of the frame.
4. `refine.py`: fine search on a 100 m grid around the chosen candidate, scoring skyline and bridge distances together.
5. `joint.py`: pier pixel columns → rays intersected with the bridge line → spacing between adjacent piers along the line should be constant; scored jointly with the skyline.

## Two steps done by hand in the session

"Sample a point every 20 px along the ridge" and "find the 17 pier pixel columns in the photo" were done in the session and the numbers were written straight into the scripts; there is no corresponding tool here.
