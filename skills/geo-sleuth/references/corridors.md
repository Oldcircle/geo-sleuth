# 线状走廊与结构化查询

没有地标、没有文字，但画面里有**线路号、铁路、输电线、大河、高速**时用。
核心思路两句话：**先把范围变成一条线，再在线上找离散的点**；**几种设施同框时，用查询把全省的共现点一次枚举出来**，不要满地图扫。
来源：v002 v003 v007 v008 v010-3 v011。

脚本：`scripts/osm.py`（find / near / crossings / route / along / intersect / street-scan / buildings / geom / raw）。输出 `{名字: [lat, lon]}`，直接给 `tiles.py mark` 画点、`tiles.py sheet` 出带编号的候选缩略图。
国内 OSM 数据不全：查到的是候选，查不到不能当排除依据。国内访问要 `--proxy socks5h://127.0.0.1:10808`（子命令前后写都行）。

国内 OSM 的已知空缺（盲测实测）：
- 县乡的 `building`、`parking` 基本为空，连地级市城区很多也没有——**国内不要拿建筑、停车场当共现条件**。
- 不少江河只有中心线、没有水面多边形，河岸形状只能从卫星图取。
- 整省查询可能要几分钟，公共服务器还会限流；放后台跑，或者按省分开跑。
- 山地城市里弯道、回头弯、挡墙到处都是，不当共现条件（盲测里主城核心区回头弯近 700 处，加上"学校、干道"还剩几十处，全不对）。
- **枚举候选前先查覆盖**：`osm.py coverage --areas <区县A>,<区县B> --filter '<要素>'`。某个候选区县的要素数明显少，共现查询会把它整个静默排除（国内常见：整个区县的学校、跑道几乎没画）。

## 1. 线路号 → 走廊

公交车尾顶部的运营商缩写 + 线路号、站牌、地铁线号、长途车牌子上的起讫点（v007：车尾的运营商缩写 + 线路号 → 一条线路走廊）。

```bash
python3 scripts/osm.py route --bbox <s,w,n,e> --kind bus --ref <线路号> --step 150 --out route.json
python3 scripts/tiles.py fetch <沿线某段中心> --zoom 17 --radius 4 --out seg.jpg --proxy socks5h://127.0.0.1:10808
python3 scripts/tiles.py mark seg.jpg --points route.json --out seg_route.jpg
```

- OSM 没收录这条线时，搜"<城市> <线路号> 路 线路图 / bus route"，在地图上手工记几个站点坐标连线。
- 沿线扫之前，把照片里"楼背后""镜头身后"的环境组合成筛选条件：楼顶上方露出围挡、塔吊 = 背后是工地；玻璃幕墙倒影里全是树 = 街对面是绿地（v007）。

## 2. 铁路

| 看到什么 | 推出什么 | 怎么查 |
|---|---|---|
| 道口标牌上的铁路公司名（JR西日本、私铁名） | 运营区域或具体线路 | 公司运营范围 |
| 接触网支柱只在一侧 | 多为单线电气化铁路（全国占比小） | `["railway"="rail"]["electrified"="contact_line"]["tracks"="1"]`（国内 tracks 常没标） |
| 两侧都有支柱或有横跨门架 | 双线 | — |
| 同一道口并排 4 条轨道 | 复复线或多线并行，全国只有少数区段 | `osm.py crossings --kind level_crossing`：OSM 里每条轨道一个道口节点，脚本按节点数估轨道数 |
| 高铁高架桥 | 高铁沿线 | `["railway"="rail"]["highspeed"="yes"]["bridge"]` |

```bash
# 一段铁路上所有道口，按轨道数看（每处会标"约N轨"）
python3 scripts/osm.py crossings --bbox <s,w,n,e> --line '["railway"="rail"]' --kind level_crossing
```

铁路场景的顺序：线路（公司名、轨道数、电气化）→ 站点（临海、临河等地形条件）→ 沿线逐个道口或桥比卫星图。
网页版 OpenRailwayMap（openrailwaymap.org）看线路等级和单双线很直观，适合人工对照。

## 3. 输电线

- 杆塔形式只能分"输电 / 配电"：高大钢管单柱或角钢塔、长绝缘子串 = 输电；矮水泥杆、木杆 = 配电。
- 电压看分裂导线（国内常见）：单根 ≈220 kV 以下，2 根一束 220–330 kV，**4 根一束 500 kV**，6 根一束 750 kV 或 ±800 kV 直流，8 根一束 1000 kV。
- 远处数不清根数时，看导线上有没有隔一段一个的小黑点（间隔棒）：有 → 分裂导线，按 ≥220 kV 算；再细分不出就别写死电压。
- 电压也可以反查：在任一已知位置的街景里找到同款杆，到 OpenInfraMap（openinframap.org）点那条线看电压，得到"这种杆 ≈ X kV"（v002）。
- **单独没用，求交才有用**：和铁路、河流、高速的交叉或平行关系才缩圈。几条线状物之间的角度（输电线和铁路垂直、车位和铁路垂直）是卫星图上一眼可见的空间签名（v011）。

OSM 标签：`["power"="line"]["voltage"="500000"]`、`["power"="tower"]`。

## 4. 共现查询（几种设施同框）

把画面里同时出现、OSM 里有标签的要素写成"A 的 x 米内有 B，B 的 y 米内有 C"，在整省或整市范围枚举（v010-3：电塔 700 m 内的高铁桥，桥 100 m 内的河流 → 全省几十处 → 按平原/山地和远山轮廓筛）。

```bash
python3 scripts/osm.py near --area <省级行政区全名> \
  --a '["railway"="rail"]["highspeed"="yes"]["bridge"]' --b '["power"="tower"]' --within 700 \
  --c '["waterway"="river"]' --within-c 100 --out cands.json
```

- 距离阈值按画面估计**放宽**一倍，宁多勿漏，再用地形、远山轮廓、卫星图筛。
- `--area` 用 OSM 里的行政区全名（如"江苏省""深圳市"）；查不到就换 `--bbox`。
- 结果超过 200 个就加条件，不逐个看。
- 加 `--report near.json` 会写出每个候选到 B、C 的实际距离和关键标签（电压、电气化、线路名），用来排序。
- **排序再看**：离城镇和道路的远近（`--rank-near`）、电压等级是否和画面一致、实际距离是否接近画面估计、地形（`terrain.py elev` 看铁路在不在坡上）。
- `--rank-near` 只是粗排：国内 OSM 的城镇节点、酒店、住宅用地标注都不均匀（住宅用地连村庄都算，拿它排序几乎没用）。城镇节点 `'["place"~"^(city|town)$"]'` 相对最稳；服务区用 `'["highway"="services"]'`。
- **真正缩小候选的是画面里核实得了的属性**：数得清分裂导线 → 电压，看得见接触网 → 电气化，道口轨道数。一条核实过的属性常把候选砍掉八成，比任何距离排序都有效；核实不了就放宽成区间（如 220–500 kV），不要猜一个值。
- **停止线**：用 `tiles.py sheet` 按排序看缩略图，看完 100 个仍没有匹配就停，报告"省/市级 + 候选区 + 为什么没对上"，不要继续肉眼扫。

## 4.1 两类线交叉（铁路 × 输电线、河 × 公路）

```bash
python3 scripts/osm.py intersect --area <省级行政区全名> \
  --a '["railway"="rail"]["electrified"="contact_line"]' --b '["power"="line"]["voltage"~"^(220000|500000)$"]' \
  --bend-min 25 --bend-within 100:900 --rank-near '["place"~"^(city|town)$"]' \
  --cluster 600 --out crossings.json      # voltage 只写画面里核实得了的区间
python3 scripts/tiles.py sheet --points crossings.json --zoom 18 --out crossings_sheet.jpg
```

- `--bend-min`：标出 B 在交点外有折角（转角塔、河湾）的交点，默认**只标注、排在前面，不删**。
- `--bend-filter` 才真的删，被删的写到 `<out>_dropped.json`。只在"线在这座塔上转弯、塔在交点哪一侧"是画面里亲眼确认的事实时用；从远景里推测出来的折角位置不算。
- `--ring lat,lon:最小m:最大m`：只留离某点这个距离环带里的交点（例如按地标像素大小和视角区间算出的距离）。
- 电压、电气化只在画面里数得清分裂导线、看得到接触网时才写进过滤条件，否则放宽成排序。
- 标签里带线路名、电压、电气化、折角、离参照要素的距离，按画面对得上的先看。

## 4.2 街景几何模板（没有锚点、但街道格局清楚）

照片只定到城镇级，但画面格局很清楚：镜头顺着一条街看过去，右边是一栋大楼，左边是围墙和花园。把格局写成模板，全城一次筛：

```bash
# 镜头朝向（sun.py facing 或影子定出的区间）→ 街道方位 320°–80°；右侧 4–22 m 有占地 ≥250 m² 的楼；左侧 3–10 m 没有楼
python3 scripts/osm.py street-scan --bbox <城镇 s,w,n,e> --bearing 320:80 --right building --left empty \
  --band 4:22 --clear 3:10 --ahead 0:40 --min-area 250 --out cands.json
python3 scripts/tiles.py sheet --points cands.json --zoom 19 --out cands_sheet.jpg
```

- 默认假设镜头站在路口、顺着支路看；不在路口加 `--anywhere --every 30`。
- 回归验证：一道视频题整镇 2265 条路、5132 栋楼筛出 38 个候选，正确路口离候选点 3 m。
- 只适合 OSM 建筑数据完整的地方（欧美、日本、国内部分大城市核心区）；国内县乡别用。
- 常用标签：`["railway"="level_crossing"]`、`["man_made"="water_tower"]`、`["aerialway"]`（索道缆车）、`["bridge"="yes"]`、`["waterway"="dam"]`、`["leisure"="pitch"]`、`["amenity"="fuel"]`、`["man_made"="communications_tower"]`、`["historic"]`、`["tourism"="attraction"]`。

## 4.3 线状设施 × 地形：没有文字，只有设施和一座认不出的山

第 4 节的共现查询只能用 OSM 标签，"远处有座陡山"写不进去。做法是把设施上的点逐个接到高程数据上算地平线，整个大区一次过滤。单一来源（实战一例：一个大区的铁路桥约 2.7 万段（其中电气化或未标注的约 2.5 万段）→ 171 片，真值在内）。

1. `osm.py geom '<设施过滤>' --bbox <大区> --out lines.geojson` 取线。
2. `terrain.py scan` 沿线取点，每点用 Terrarium 高程算 360° 地平线，按形状条件过滤并聚簇：

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/terrain.py scan --lines lines.geojson --out hits.json \
  [--clusters-out clusters.json] [--bbox s,w,n,e] [--step 400] [--zoom 10] \
  [--near-flat 40] [--near-radius 1200] [--near-step 300] \
  [--min-peak 4.5] [--max-low 1.2] [--flat-run 20] [--min-low-deg 默认=--flat-run] [--flat-run-cap 100] \
  [--eye 1.5] [--az-step 5] [--dist 1500,2000,2500,3000,3500,4000,5000,6000,7000,8000,9000] \
  [--skip-tag electrified=no ...] [--cluster-km 3.5] [--threads 24] [--max-tiles 4000]
```

- `--step` 沿线取点间距（米），`--zoom` 高程切片层级（z10 一格约 150 m，够用且切片少）。
- 过滤条件只用和朝向无关、画面里看得出的形状：`--near-flat` = `--near-radius` 米内起伏不超过多少米（近处平）、`--min-peak` = 几公里内要有仰角 ≥X° 的山、`--max-low` = 多低才算平地平线、`--flat-run` = 平地平线要连续多少度。`--dist` 是算山用的距离阶梯。
- `--skip-tag` 按标签跳过线（可重复），`--cluster-km` 是命中点聚簇半径。切片超过 `--max-tiles` 直接报错退出，先缩 `--bbox` 或降 `--zoom`。
- 全局参数照 `terrain.py` 原样：`--proxy`（默认读 `GEO_PROXY`）、`--cache`（默认 `.geo-cache/dem`，高程切片直连即可，缓存能反复用）。
- 输出 `hits.json`：`{params:{...}, n_samples, n_hits, n_clusters, hits:[{lat, lon, h0: 地面高程 m, max_ang: 最高地平线仰角°, az: 那个方位°, relief: 该方位最大相对高差 m, flat_run_deg: 紧挨山体的平地平线长度°, name/hs/elec/id: 线的 OSM 标签}...], clusters:[...]}`。簇按 `max_ang` 从大到小，簇代表就是簇里最陡的那个点（字段和 `hits` 一样，多一个 `n` = 簇内点数）；`--clusters-out` 另写一份只有簇列表的 JSON。
3. 结果簇进 `geometry.md` 7.4 的天际线批量打分（`terrain.py fit --hits`）。

- **阈值取照片估计值的一半左右**。z10 一格约 150 m，山头被抹平，算出来的仰角偏小。实战里按照片估计值设阈值，真值附近一个点都没留下，放宽后才进来。宁多勿漏，数量交给下一步排序。
- 设施离画面左缘、中间、右缘各有多远也是一条独立的数值约束：用等间距构件当尺（`geometry.md` 第 3 节）估出三处距离，交给 `terrain.py fit` 的 `--line` / `--line-dist` 一起打分。

## 5. 大河：认河 → 河段 → 线变点

1. **认河三要素**：宽度（两岸房屋、车道、梯田当尺）、颜色（含沙量）、两岸地貌（平原 / 高山峡谷 / 低矮碎沟壑）。三者组合，比单看颜色可靠（汛期很多河都黄）。
2. **定走向**要有时刻：用太阳算方向（`sky.md`），不要默认"阴坡朝北"。
3. **按走向 + 两岸地形筛河段**：列出同走向、同宽度、同样两岸地貌的河段，逐条排除。
4. **线变点**：在画面里找线上的离散结构——桥（桥身看不清时看水面上的细长影子）、坝、渡口、隧道口、立交、码头，列出这段河上所有这类结构。v008：850 km 的一段大河 → 26 处跨河建筑 → 7 → 2 → 1。

```bash
python3 scripts/osm.py crossings --bbox <s,w,n,e> --line '["waterway"="river"]["name"="<河名>"]' --kind bridge,dam,ferry --out crossings.json
```

5. **候选表逐个过**：每个点只问照片里直接看得到的几个问题（河道在视野里弯不弯、有没有水库、两岸是否都是山、有没有大片聚落），一次过完再细比。**标准只比照片视野内那一段**（v008 用视野外的弯道排除了候选，差点把答案筛掉）。
6. 剩几个时用 `terrain.py view` 或 Google Earth 倾斜视角比山脊和山脊上的路。

## 6. 城市之间的模板比对

候选城市有好几个时（v006：三个格局相近的候选城市），把照片里的大尺度结构写成模板再逐城比：

- 水系：几条河、各自走向（配合朝向）、交汇角、有无江心洲、河宽、桥的位置、对岸是否城区。
- 山体：山在哪一侧、离城区多远、山顶有无塔或雕像。
- 路网：高架、环岛、铁路在城区的位置。

江心洲、交汇与否、河宽这类特征一眼就能排除，先比它们。注意卫星图年份（岸线和江心洲随水位、工程变化）。

## 常见错误

- 概率押注当过滤条件："绿色出租车四川最多"就只查四川；"前 20 大城市"（v002、v006）。能加分，不能排除。
- 两个样本的共现当规律："两处这种电杆都靠铁路 → 照片附近也有铁路"（v002）。
- 在假前提上叠推断："远处是雪山 → 一定在某省 → 只查该省的铁路"，前提没核实，后面全错。
- 把没核实的解读当硬过滤："转角塔一定在交点外侧"——真点就在被滤掉的那一批里。解读只排序，全部没对上时先回头看被滤掉的。
- OSM 查不到就排除：国内数据缺线很常见。
- 候选全部没对上就宣布失败，不回头检查过滤条件（硬规则 9）。
