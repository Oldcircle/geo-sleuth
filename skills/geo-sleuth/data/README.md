# 查表数据 · Lookup tables

`clues.py lookup` 读这个目录的 JSON。每个文件的 `_meta` 记录来源 URL、抓取日期和条数；`clues.py update` 按 `_meta.source` 重抓。

*`clues.py lookup` reads the JSON files in this directory. Each file's `_meta` records the source URL, fetch date and row count; `clues.py update` re-fetches from `_meta.source`.*

| 文件 · File | 内容 · Contents | 来源 · Source | 抓取 · Fetched | 条数 · Rows | 许可证 · Licence |
|---|---|---|---|---|---|
| `cn_plates.json` | 中国民用机动车号牌省份前缀 · Chinese civil vehicle plate prefixes by province | [zh.wikipedia.org/zh-cn/中华人民共和国民用机动车号牌](https://zh.wikipedia.org/zh-cn/中华人民共和国民用机动车号牌) | 2026-09-14 | 31 | 派生自维基百科 · derived from Wikipedia, CC BY-SA 4.0 |
| `cn_area_codes.json` | 中国大陆固定电话区号 · Mainland China landline area codes | [zh.wikipedia.org/zh-cn/中国大陆固定电话号码](https://zh.wikipedia.org/zh-cn/中国大陆固定电话号码) | 2026-09-14 | 349 | 派生自维基百科 · derived from Wikipedia, CC BY-SA 4.0 |
| `calling_codes.json` | 国家和地区电话国家码 · Telephone country calling codes | [en.wikipedia.org/wiki/List_of_telephone_country_codes](https://en.wikipedia.org/wiki/List_of_telephone_country_codes) | 2026-09-14 | 281 | 派生自维基百科 · derived from Wikipedia, CC BY-SA 4.0 |
| `driving_side.json` | 各国行驶方向 · Driving side by country | [en.wikipedia.org/wiki/Left-_and_right-hand_traffic](https://en.wikipedia.org/wiki/Left-_and_right-hand_traffic) | 2026-09-14 | 236 | 派生自维基百科 · derived from Wikipedia, CC BY-SA 4.0 |
| `territories.json` | 海外领地和属地 · Dependent territories | [en.wikipedia.org/wiki/List_of_dependent_territories](https://en.wikipedia.org/wiki/List_of_dependent_territories) | 2026-09-14 | 60 | 派生自维基百科 · derived from Wikipedia, CC BY-SA 4.0 |
| `cn_admin.json` | 中国省市县三级行政区代码 · Chinese province / city / county codes | [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China) `dist/pca-code.json` | 2026-09-14 | 3420 | WTFPL |
| `country_names.json` | 中英文国家和地区名对照及别名 · Chinese/English country and region names with aliases | 手工整理 · compiled by hand | 2026-09-14 | 300 | MIT（随本仓库 · with this repository） |

说明：

- 维基百科来源的五张表是从对应条目的表格抓取整理的事实数据。维基百科文本按 CC BY-SA 4.0 授权；这五张表按同一许可证发布，署名维基百科及其编辑者。
- `cn_plates.json` 里 `渝` 条目下的 `letter_notes_unverified` 块（直辖市车牌字母分区）不来自维基百科，来自常识表，未核实。`clues.py` 输出时会标 unverified。
- `country_names.json` 是手工整理的对照表，`en2zh` 的键与其他各表里的英文写法一致，`aliases` 把简称、繁体、旧名、英文缩写映射到 `en2zh` 的键。
- 这个目录不包含 OpenStreetMap 数据；`gazetteer.py`、`osm.py` 现查 Overpass。

*Notes:*

- *The five Wikipedia-sourced tables are factual data extracted from the tables in the linked articles. Wikipedia text is licensed CC BY-SA 4.0; these five tables are released under the same licence, with attribution to Wikipedia and its editors.*
- *The `letter_notes_unverified` block under the `渝` entry in `cn_plates.json` (letter sub-regions of a municipality's plates) does not come from Wikipedia. It comes from a common-knowledge table and has not been verified. `clues.py` marks it unverified in its output.*
- *`country_names.json` is a hand-compiled mapping. Keys in `en2zh` match the English spellings used in the other tables; `aliases` maps short forms, traditional-character forms, old names and English abbreviations onto `en2zh` keys.*
- *This directory contains no OpenStreetMap data; `gazetteer.py` and `osm.py` query Overpass live.*
