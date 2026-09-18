# rail-skyline-session：第 13 集案例的专用脚本

这个目录里的 5 个脚本是第 13 集那张照片的案例脚本，参数都按那张照片调过（焦距、地平线行、26 个山脊像素点、17 个桥墩像素列、三处桥距区间、候选中心坐标），只作复现记录，不保证在别的照片上能跑。

*The five scripts here are the case scripts for the episode-13 photo. Every parameter is tuned to that one photo (focal length, horizon row, 26 ridge pixels, 17 pier pixel columns, three bridge-distance windows, candidate centre coordinates). They are kept as a reproduction record and are not expected to run on another photo.*

现在日常用 skill 的子命令（`terrain.py scan / ridge / fit`、`imgprep.py piers`、`geo.py spacing`），不用这些脚本；新子命令和这些脚本在同一张照片上对过结果。

*Day to day, use the skill subcommands (`terrain.py scan / ridge / fit`, `imgprep.py piers`, `geo.py spacing`) instead of these scripts; the subcommands were checked against these scripts on the same photo.*

方法本身已写进 skill 文档：`skills/geo-sleuth/references/corridors.md` 4.3（线状设施 × 地形扫描）和 `references/geometry.md` 7.4、7.7（天际线批量打分、等间距构件反解机位）。

*The method itself is documented in the skill: `skills/geo-sleuth/references/corridors.md` section 4.3 (linear feature × terrain scan) and `references/geometry.md` sections 7.4 and 7.7 (batch skyline scoring, camera position from equally spaced structures).*

## 依赖 / Dependencies

脚本通过 `sys.path` 引用仓库里的 `skills/geo-sleuth/scripts/terrain.py`（`DEM`、`_dest_np`、`_fetch`），所以要在这个仓库的目录结构里运行；用 `uv run <脚本>`，依赖写在文件头。高程切片走 AWS Terrain Tiles，缓存在当前目录的 `.geo-cache/dem/`。

*The scripts import `terrain.py` from `skills/geo-sleuth/scripts/` in this repository via `sys.path`, so they must stay inside this repository layout. Run them with `uv run <script>`; dependencies are declared in each file header. Elevation tiles come from AWS Terrain Tiles and are cached under `.geo-cache/dem/` in the working directory.*

## 输入文件 / Input files

输入数据不在仓库里。两个 geojson 都是用 `skills/geo-sleuth/scripts/osm.py geom` 对 Overpass 做的铁路桥查询，其余输入是上一步脚本的输出。

*Input data is not in the repository. Both geojson files were produced by railway-bridge Overpass queries through `skills/geo-sleuth/scripts/osm.py geom`; the other inputs are outputs of the previous step.*

| 脚本 / Script | 输入 / Input | 输出 / Output |
|---|---|---|
| `rail_mtn_scan.py` | `argv[1]`：大区铁路桥 geojson（`osm.py geom` 的 Overpass 铁路桥查询） | `argv[2]`：命中点 json（每点坐标、最大仰角、方位、平地平线长度） |
| `skyfit2.py` | `argv[1]`：上一步的命中点 json；`argv[3]`：处理的命中区间 `a:b`；当前目录 `rail_bridges.geojson`（同一份 Overpass 铁路桥查询） | `argv[2]`：机位打分 json（会话里分批跑，输出命名为 `f2_0.json`、`f2_1.json`…） |
| `railgeom.py` | 当前目录 `f2_?.json`（上一步输出，glob 合并）；`rail_bridges.geojson` | `f3_sel.json`（按天际线 + 桥距总分排序、去重后的机位） |
| `refine.py` | `argv[1]`：中心 `lat,lon`（从 `f3_sel.json` 里挑的候选）；`argv[2]`：半径 m；`rail_bridges.geojson` | `argv[3]`：精搜结果 json |
| `joint.py` | 当前目录 `qy_rail.geojson`（`osm.py geom` 的铁路线查询，脚本按线名取一条）；候选中心写死在脚本里（来自 refine 的结果） | `joint.json`（桥墩间距 + 天际线联合打分的前 25 名） |

## 运行顺序 / Run order

```
rail_mtn_scan.py → skyfit2.py → railgeom.py → refine.py → joint.py
```

1. `rail_mtn_scan.py`：沿桥线每 400 m 取点，DEM 算 360° 地平线，留下「近处平、几公里内有山、山旁一段平地平线」的点。
2. `skyfit2.py`：每个命中点周围 2 km 半径、250 m 网格放机位，搜朝向 × 焦距 × 地平线偏移，用照片山脊线打分。
3. `railgeom.py`：按画面左缘、中心、右缘的桥距区间筛上一步的机位。
4. `refine.py`：在选定候选周围 100 m 网格精搜，天际线和桥距一起打分。
5. `joint.py`：桥墩像素列 → 射线与桥线求交 → 相邻桥墩沿线间距应恒定，与天际线联合打分。

*1. `rail_mtn_scan.py`: sample the bridge lines every 400 m, compute the 360° horizon from the DEM, keep points with flat ground nearby, a mountain within a few km, and a flat horizon run next to it. 2. `skyfit2.py`: place camera positions on a 250 m grid within 2 km of each hit, search heading × focal length × horizon offset, score against the photo's ridge line. 3. `railgeom.py`: filter the previous positions by bridge-distance windows at the left edge, centre and right edge of the frame. 4. `refine.py`: fine search on a 100 m grid around the chosen candidate, scoring skyline and bridge distances together. 5. `joint.py`: pier pixel columns → rays intersected with the bridge line → adjacent pier spacing along the line should be constant, scored jointly with the skyline.*

## 会话里没进脚本的两步 / Two steps done by hand in the session

「山脊每 20 px 取一点」和「照片里找出 17 个桥墩像素列」是在会话里做完直接把数字写进脚本的，这里没有对应工具。

*Sampling the ridge every 20 px and locating the 17 pier pixel columns in the photo were done during the session and the numbers were typed into the scripts; there is no tool for them here.*
