# 脚本、数据源与坐标系

## 脚本总表（`scripts/`）

| 脚本 | 做什么 | 网络 |
|---|---|---|
| `exif.py` | GPS、拍摄时间、等效焦距、镜头朝向 | — |
| `imgprep.py` | zoom 放大读字 / edges 四边四角 / variants 搜图变体 / grid 切块 / `piers` 沿指定行取亮度剖面找等间距构件的像素列（出核对图） | — |
| `revimg.py` | 百度识图 + Yandex 以图搜图；`--query` 中文关键词搜索（必应国内版、百度/搜狗图片） | 百度、必应直连；Yandex 走代理 |
| `geo.py` | 坐标系换算、方位距离、相机几何（`range --hfov a:b` 距离区间）、`line` 对齐线、`intersect` 视线交会、`frame` 排除前算画框和遮挡、`spacing` 等间距构件像素列 × 已知折线反解机位（可选和天际线联合打分） | 仅 `spacing` 取高程切片，直连或代理均可 |
| `poi.py` | 地名、小区名、楼盘名、店名 → 坐标候选（360 地图 + OSM Nominatim + 百度联想），全国同名点都列出 | 360、百度直连；Nominatim 走代理 |
| `sun.py` | 太阳位置、影长比、`locate` 地带、`when` 时刻、`street` 街道走向、`facing` 受光面定朝向、`dish` 卫星锅 | — |
| `osm.py` | Overpass：find / near 共现 / crossings 线变点 / route 线路走廊 / intersect 两类线交叉（折角只标注，`--rank-near` 排序）/ street-scan 街景几何模板 / geom 导出几何 | 代理 |
| `tiles.py` | 卫星切片拼图、`mark` 标点 + 叠 GeoJSON 线 + 视野扇形、`sheet` 候选点带编号缩略图 | 代理（Google） |
| `baidu_pano.py` | 百度全景：near / info / scan / render / sheet（`--headings` 单点环视、`--road` `--spread`）/ sample 候选城市街景抽样 | 直连 |
| `gsv.py` | Google 街景（国外）：near / render / sheet，免 key，只取官方覆盖 | 代理 |
| `pose.py` | 多点反解机位：经纬度、高度、朝向、俯仰、横滚、视角 + 误差半径；`project` 把地图点投回照片 | — |
| `terrain.py` | 高程：view 合成山体视图（`--overlay` 天际线叠照片、`--roll`）/ profile 天际线 / elev / `ridge` 从照片读山脊像素点 / `scan` 沿设施线整区筛「近处平 + 有山」的点并聚簇 / `fit` 候选机位批量天际线打分（可选设施距离约束，出前 N 名叠图） | 直连或代理均可（`ridge` 不联网） |
| `evidence.py` | 证据图：卫星图 + 机位扇形 + 比对格 | — |
| `intake.py` | 第 0–3 步一条命令：exif + 边缘图 + 变体 + OCR + 百度/Yandex 识图并行，出 intake.md（分级计票、疑似地名） | 百度直连；Yandex 代理 |
| `ocr.py` | 读照片文字（Apple Vision，回退 RapidOCR）：整图 + 放大 + 切块合并，放大才读出的标 pass | — |
| `clues.py` | 查表：车牌前缀、固话区号、国家电话码、行驶方向、海外领地、行政区上下级；表在 `data/`，`update` 重抓 | lookup 不联网；update 代理 |
| `board.py` | 候选盘：候选、线索、证据似然比、排除（要算过的文件）、排名、扫描成本、下一步、出结论检查、生成 result.json 字段 | — |
| `gazetteer.py` | 行政区名录：下级列全（带 bbox）、建成区范围、扫描页数 | 代理（Overpass） |
| `sat_scan.py` | 卫星图网格/候选点 CLIP 零样本打分排序（操场、厂房、筒仓、水坝…），前 N 名缩略图 + 热图 | 代理（Google 切片、首次下模型） |
| `match.py` | 照片 vs 候选实景图排名：DINOv2 全局相似度 + SIFT 内点精排；候选可由全景 id 现场渲染 | 百度直连 / Google 代理；首次下模型 |
| `geo.py bearings` | 机位 → GeoJSON 里每个轮廓的方位角、角宽、距离；配 `sun.py compass` 先算方位再认构件 | — |

## 坐标系（国内必须分清）

| 代号 | 名称 | 谁在用 |
|---|---|---|
| wgs | WGS84 | GPS、照片 EXIF、Google 卫星图、OpenStreetMap、高程切片 |
| gcj | GCJ-02 | 高德、腾讯、360 地图、Google 中国区道路图，**Google Earth 国内的中文标注图层** |
| bd | BD-09 | 百度地图经纬度 |
| bdmc | 百度墨卡托 | 百度地图 URL 里的 `@x,y`、百度全景接口 |

国内同一个点在 WGS84 和 GCJ-02 之间差几百米。换算：`scripts/geo.py convert --from X --to Y a b`。
- 高德链接用 gcj：`https://uri.amap.com/marker?position=经度,纬度`；Google 链接用 wgs。
- **Google Earth 在国内：影像是 WGS84，中文地名标注是 GCJ-02，两者错开几百米**（v005：码头的中文标签落在江面上）。打点、读坐标以影像为准。
- 从国内地图 App 或网页读来的坐标，先确认坐标系再用。

## 卫星图

| 来源 | 说明 |
|---|---|
| Google 卫星切片 | `mt1.google.com/vt/lyrs=s`，WGS84，国内清晰；需要代理。`tiles.py` 默认 |
| Esri World Imagery | 备用，国内部分地区较旧；有 Wayback 历史存档 |
| Google Earth 桌面版 | 历史影像时间轴、倾斜 3D（人工用）；国内 3D 模型旧，新建超高层常缺 |

- 同一地点不同缩放级别可能是不同年份、不同倾斜角度的影像。
- 17 级约 1.1 m/像素看片区；19 级约 0.28 m/像素看单栋楼；7–9 级给 `sun.py locate --mosaic` 当底图。

## 街景与实景

### 百度全景（国内主力）

接口都在 `https://mapsv0.bdimg.com/`，不需要 key，必须直连：

| 用途 | 参数 |
|---|---|
| 某点最近的全景 | `?qt=qsdata&x=<bdmc x>&y=<bdmc y>` |
| 全景信息（日期、位置、整条路的点、历史版本） | `?qt=sdata&sid=<panoid>` |
| 按朝向渲染透视图 | `?qt=pr3d&panoid=<id>&heading=<罗盘角>&pitch=<俯仰>&fovy=<竖直视角>&width=<≤1024>&height=<>` |

- heading 是罗盘方位，0 = 正北，顺时针；宽度超过 1024 返回 404。
- 覆盖城市主干道和不少工业区内部路；小区内部基本没有。采集多在 2017–2019 年，新楼看不到。
- map.baidu.com 的地点搜索会触发验证码，不要去绕；查地名用 `poi.py`。

### 其他

| 来源 | 用途 | 已知问题 |
|---|---|---|
| Google 街景 | 国外街景，有历史日期；`gsv.py` | 国内几乎没有；用户上传的全景照片（id 形如 CIHM0og…）出不了透视图，脚本已过滤 |
| Mapillary、KartaView | 众包街景，国外乡村道路 | 国内几乎没有 |
| 腾讯街景 | 国内备选 | 接口待调研 |
| 地图 POI 图片、酒店/景区网上实拍、游客照 | 没有街景时比天际线、楼形 | 拍摄角度不可控 |

## 搜索

| 来源 | 擅长 | 用法 |
|---|---|---|
| 百度识图 | 中文网页、微博、百家号、电商、景区；会给"图中可能是…" | `revimg.py`，直连 |
| Yandex 图片 | 建筑、街景、外国内容；给标签和来源站 | `revimg.py --proxy` |
| Google Lens | 认"这是什么"（物种、车型、雕像、景点），常比百度 Yandex 强 | 服务器出口会被要求验证；有浏览器操作工具时在用户浏览器里用；AI 概览会凭相似图硬报地名 |
| 必应国内版、百度图片、搜狗图片 | 中文关键词网页和图片搜索 | `revimg.py --query`；百度网页搜索会弹验证，不用 |
| 抖音、小红书、微博 | 网红打卡点、景区官方号、同城内容 | 网页搜索或用户协助 |
| 房产网楼盘相册（安居客、房天下、楼盘网等） | 新楼盘、商业综合体，相册里有立牌 | 网页搜索楼盘名 |
| 旅游点评站（Tripadvisor、携程） | 雕像、公园、景点用户图 | 网页搜索 |
| 图库（视觉中国、Getty、Alamy） | 图片说明带精确地名、年代 | 网页搜索 |
| 地方政府、地方媒体网站 | 核对景区、塔、雕像的名称和尺寸 | 网页搜索 |

## 地名 → 坐标（国内）

| 来源 | 说明 |
|---|---|
| 360 地图搜索 `restapi.map.so.com/newapi` | 免 key、直连；小区、楼盘、店铺、单位覆盖好，带地址和区县；坐标 GCJ-02（`poi.py` 已转 WGS84）；不给城市时返回全国有同名结果的城市列表 |
| OpenStreetMap Nominatim | 走代理；有名字的小区、公园、道路；WGS84 |
| 百度地图搜索联想 `map.baidu.com/su` | 免 key、直连；只有"城市 + 区县 + 名字"，没有坐标 |
| 百度地图地点搜索、腾讯、高德接口 | 百度要验证码，腾讯高德要 key，不用 |

## 地名 → 坐标（国外）

- `poi.py "<地址或地名>" --sources osm --country <两位国家代码> --proxy socks5h://127.0.0.1:10808`（Nominatim，WGS84）。门牌地址搜不到时去掉门牌号只搜街道 + 区名。

## 地面照片（没有街景时）

| 来源 | 说明 |
|---|---|
| 新闻、百科、企业官网、博客配图 | 先给设施找名字（OSM 名字、附近地名 + 当地语言的设施类型词）再搜；乡间厂房、废弃设施常只有这一种地面照片 |
| Wikimedia Commons 按坐标搜图 | `commons.wikimedia.org/w/api.php?action=query&list=geosearch&gscoord=<lat>|<lon>&gsradius=10000&gsnamespace=6&format=json`，免 key、走代理；偏远地区常只有几张 |
| Mapillary | 覆盖广，但接口要 OAuth token，脚本不用 |
| KartaView | 接口免 key，覆盖很少 |

## 专题图与结构化数据

| 来源 | 用途 | 已知问题 |
|---|---|---|
| OpenStreetMap Overpass | 要素共现、线变点、线路走廊、线交叉、街景模板、沿路取点、大建筑 | `osm.py`；公共服务器常忙或限流（脚本换镜像重试，结果带 remark 会提示不全）；**上百公里的范围加名字正则（`[~"name"~...]`）常超时**，去掉正则或分区查；国内县乡建筑、停车场基本为空，江河常只有中心线 |
| OpenRailwayMap（openrailwaymap.org） | 铁路等级、单双线、电气化、车站 | 网页人工看；数据同 OSM |
| OpenInfraMap（openinframap.org） | 输电线路和电压、变电站 | 网页人工看；电压可能没标 |
| AWS Terrain Tiles（Terrarium） | 全球约 30 m 高程 | `terrain.py`；细节小于百米不可靠 |
| 城市开放数据 | 行道树（树种、胸径、位置）等 | 国外城市多，国内少 |

## 时间与天气

| 来源 | 用途 |
|---|---|
| `sun.py`（NOAA 算法，和 NREL SPA 差 ≤0.02°） | 太阳位置，替代 SunCalc |
| 历史逐日天气（气温、晴雨） | 核对"结冰""晴天"；有日期时排除阴雨地区 |
| 历史气象卫星云图 | 当天大片云区排除（台风、锋面时才有明显效果） |
| Flightradar24、FlightAware | 按注册号查航班历史；付费档可下载 KML/CSV 航迹 |

## 网络

- 走代理 `socks5h://127.0.0.1:10808`（脚本参数 `--proxy` 或环境变量 `GEO_PROXY`）：Google 卫星图、Google 街景、Overpass、Yandex。
- 必须直连：百度全景、百度识图、必应国内版。高程切片两种都行。
- macOS 没有 `timeout` 命令；zsh 的 for 循环里 `$var` 不分词（写 `${=var}` 或用 `bash -c`）；zsh 里 `echo =====` 这类以 `=` 开头的词会被当成命令路径展开而报错，分隔线用 `-----`。
- `revimg.py` 用的 Chrome 代理写 `socks5://`（脚本会自动把 `socks5h://` 改掉）。
- 国外新闻站 WebFetch 报 "Socket closed" 时，改 `curl -s -A 'Mozilla/5.0' --socks5-hostname 127.0.0.1:10808 <url>` 抓 HTML 再提正文。
