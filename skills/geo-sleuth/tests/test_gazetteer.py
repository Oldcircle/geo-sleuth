#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Offline gazetteer regressions: bilingual OSM names and region-pack extra children. Run: uv run skills/geo-sleuth/tests/test_gazetteer.py"""
from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import gazetteer  # noqa: E402

BOUNDS = {"minlat": 1.0, "minlon": 2.0, "maxlat": 3.0, "maxlon": 4.0}


def rel(osm_id: int, level: int, **tags) -> dict:
    tags = {k.replace("_", ":").replace(":Hans", "-Hans"): v for k, v in tags.items()}
    return {"type": "relation", "id": osm_id, "bounds": BOUNDS, "tags": {"admin_level": str(level), **tags}}


# Tags as OSM has them (2026-10): the ethnic autonomous regions and Hong Kong carry a second script in `name`
INNER_MONGOLIA = rel(161349, 4, name="内蒙古自治区 ᠦᠪᠦᠷ ᠮᠣᠩᠭᠤᠯ ᠤᠨ ᠥᠪᠡᠷᠲᠡᠭᠡᠨ ᠵᠠᠰᠠᠬᠣ ᠣᠷᠣᠨ", name_zh="内蒙古自治区", name_en="Inner Mongolia")
TIBET = rel(153292, 4, name="西藏自治区 བོད་རང་སྐྱོང་ལྗོངས།", name_zh="西藏自治区", name_en="Xizang")
HONG_KONG_4 = rel(20044132, 4, name="香港 Hong Kong", name_zh="香港", name_en="Hong Kong")
HONG_KONG_3 = rel(913110, 3, name="香港 Hong Kong", name_zh="香港", name_en="Hong Kong")
MACAU = rel(1867188, 3, name="澳門 Macau", name_zh="澳門", name_zh_Hans="澳门", name_en="Macau")
TAIWAN = rel(449220, 2, name="臺灣", name_zh_Hans="台湾", name_en="Taiwan")
SICHUAN = rel(913068, 4, name="四川省", name_zh="四川省", name_en="Sichuan")
RIO = rel(57963, 4, **{"name": "Rio de Janeiro", "name:pt": "Rio de Janeiro", "name:en": "Rio de Janeiro"})


class BilingualNames(unittest.TestCase):
    def test_rows_use_the_plain_name_and_keep_every_variant(self):
        rows = {r["osm_id"]: r for r in gazetteer._rel_rows({"elements": [INNER_MONGOLIA, TIBET, HONG_KONG_4, MACAU, SICHUAN, RIO]})}
        self.assertEqual(rows[161349]["name"], "内蒙古自治区")
        self.assertEqual(rows[153292]["name"], "西藏自治区")
        self.assertEqual(rows[20044132]["name"], "香港")
        self.assertEqual(rows[1867188]["name"], "澳門")
        self.assertIn("澳门", rows[1867188]["names"])
        self.assertEqual(rows[913068]["name"], "四川省")
        self.assertEqual(rows[57963]["name"], "Rio de Janeiro")     # a name with spaces that isn't bilingual stays whole

    def test_duplicate_elements_from_a_union_query_are_listed_once(self):
        self.assertEqual(len(gazetteer._rel_rows({"elements": [TIBET, TIBET]})), 1)

    def test_name_lookup_matches_every_name_key_and_escapes_quotes(self):
        sel = gazetteer._by_name('A "B"', '["admin_level"="4"]', "(area.p)")
        for key in gazetteer.regions.osm_name_keys():
            self.assertIn(f'rel(area.p)["{key}"="A \\"B\\""]["boundary"="administrative"]["admin_level"="4"];', sel)

    def test_extra_name_keys_come_from_region_packs_not_core(self):
        self.assertEqual(gazetteer.regions.osm_name_keys(), ("name", "name:zh", "name:zh-Hans"))   # declared by the CN pack
        with patch.object(gazetteer.regions, "packs", return_value={}):
            self.assertEqual(gazetteer.regions.osm_name_keys(), ("name",))
            self.assertEqual(gazetteer._by_name("X"), '(rel["name"="X"]["boundary"="administrative"];)')
            self.assertEqual(gazetteer.osm._area_sel("X", "a"), '(area["name"="X"];)->.a;')


class AlsoChildren(unittest.TestCase):
    def setUp(self):
        self.china = {"name": "中国", "admin_level": 2, "osm_id": 270056}
        self.provinces = gazetteer._rel_rows({"elements": [SICHUAN, INNER_MONGOLIA, HONG_KONG_4]})

    def test_pack_lists_macau_and_taiwan_once_without_repeating_hong_kong(self):
        reply = {"elements": [HONG_KONG_3, MACAU, TAIWAN]}
        with patch.object(gazetteer.osm, "run", return_value=reply) as run:
            extra, missing = gazetteer.also_children(self.china, self.provinces, None, Path("."))
        self.assertEqual([r["name"] for r in extra], ["澳門", "臺灣"])
        self.assertEqual(missing, [])
        query = run.call_args.args[0]
        self.assertIn('"name:zh-Hans"="澳门"', query)
        self.assertNotIn('"香港"', query)                          # already on the list, not asked again

    def test_names_osm_lacks_are_reported(self):
        with patch.object(gazetteer.osm, "run", return_value={"elements": [MACAU]}):
            extra, missing = gazetteer.also_children(self.china, self.provinces, None, Path("."))
        self.assertEqual([r["name"] for r in extra], ["澳門"])
        self.assertEqual(missing, ["臺灣"])

    def test_only_a_country_parent_gets_extra_children(self):
        province = {"name": "中国", "admin_level": 4, "osm_id": 1}
        with patch.object(gazetteer.osm, "run") as run:
            self.assertEqual(gazetteer.also_children(province, self.provinces, None, Path(".")), ([], []))
        run.assert_not_called()


class CountryNameResolution(unittest.TestCase):
    """Filter the fixture by the actual selectors, so an incorrect query cannot get the right country."""

    def setUp(self):
        def place(osm_id, level, **tags):
            return rel(osm_id, level, boundary="administrative", **tags)
        self.china = place(270056, 2, name="中国", name_zh="中国", name_en="China", **{"ISO3166-1": "CN"})
        self.swiss = place(51701, 2, name="Schweiz/Suisse/Svizzera/Svizra", name_en="Switzerland", **{"ISO3166-1:alpha2": "CH"})
        self.mexico = place(114686, 2, name="México", name_en="Mexico", **{"ISO3166-1": "MX"})
        self.namesake = place(5605656, 6, name="China", name_en="China")
        self.england = place(58447, 4, name="England", name_en="England")
        self.uk = place(62149, 2, name="United Kingdom", name_en="United Kingdom", **{"ISO3166-1": "GB"})
        self.hk = place(913110, 3, name="香港 Hong Kong", name_zh="香港", name_en="Hong Kong", **{"ISO3166-1": "HK"})
        self.elements = [self.namesake, self.mexico, self.china, self.swiss, self.england, self.uk, self.hk]
        self.membership = {self.namesake["id"]: {self.mexico["id"]}, self.england["id"]: {self.uk["id"]}}

    def overpass(self, query, *_):
        def select(text, elements):
            selectors = re.findall(r'rel(?:\(area\.p\))?((?:\["[^"\\]+"="(?:\\.|[^"\\])*"\])+);', text)
            self.assertTrue(selectors, text)
            filters = [[(key, json.loads('"' + value + '"'))
                        for key, value in re.findall(r'\["([^"\\]+)"="((?:\\.|[^"\\])*)"\]', s)]
                       for s in selectors]
            return [el for el in elements if any(all(el["tags"].get(k) == v for k, v in f) for f in filters)]
        if "map_to_area->.p;" in query:
            parent_query, child_query = query.split("map_to_area->.p;")
            parent_ids = {el["id"] for el in select(parent_query, self.elements)}
            elements = [el for el in self.elements if self.membership.get(el["id"], set()) & parent_ids]
            return {"elements": select(child_query, elements)}
        return {"elements": select(query, self.elements)}

    def lookup(self, name, **kwargs):
        with patch.object(gazetteer.osm, "run", side_effect=self.overpass) as run:
            rows = gazetteer.find_relation(name, None, Path("."), **kwargs)
        self.assertEqual(run.call_count, 1)   # no extra network round trip to resolve a country
        return [r["osm_id"] for r in rows]

    def test_country_names_codes_and_bilingual_tags_without_any_packs(self):
        with patch.object(gazetteer.regions, "packs", return_value={}):
            for name, expected in (("China", 270056), ("中国", 270056), ("CN", 270056), (" china ", 270056),
                                   ("Switzerland", 51701), ("瑞士", 51701), ("ch", 51701)):
                with self.subTest(name=name):
                    self.assertEqual(self.lookup(name), [expected])

    def test_pack_alias_remains_usable(self):
        self.assertEqual(self.lookup("PRC"), [270056])

    def test_english_name_fallback_only_selects_a_country(self):
        del self.china["tags"]["ISO3166-1"]
        self.assertEqual(self.lookup("China"), [270056])

    def test_missing_country_does_not_return_a_namesake(self):
        self.elements.remove(self.china)
        with self.assertRaisesRegex(SystemExit, "no country/territory boundary.*China.*CN"):
            self.lookup("China")

    def test_multiple_country_boundaries_are_reported(self):
        copy = {**self.china, "id": 270057}
        self.elements.append(copy)
        with self.assertRaisesRegex(SystemExit, "several country/territory boundaries.*270056.*270057"):
            self.lookup("China")

    def test_within_resolves_the_country_but_keeps_the_local_target(self):
        self.assertEqual(self.lookup("China", within="Mexico"), [5605656])
        self.assertEqual(self.lookup("England", within="United Kingdom"), [58447])
        self.membership[self.namesake["id"]] = {self.china["id"]}
        self.assertEqual(self.lookup("China", within="中国"), [5605656])

    def test_missing_scope_country_does_not_search_its_namesake(self):
        self.elements.remove(self.mexico)
        self.assertEqual(self.lookup("China", within="Mexico"), [])

    def test_explicit_local_level_is_not_forced_to_a_country(self):
        self.assertEqual(self.lookup("China", level=6), [5605656])
        self.assertEqual(self.lookup("China", level=2), [270056])

    def test_subregions_and_iso_territories_keep_their_own_boundaries(self):
        self.assertEqual(self.lookup("England"), [58447])  # broad clue alias must not turn this into the UK
        self.assertEqual(self.lookup("香港"), [913110])    # ISO territory, OSM admin_level 3
        self.assertEqual(self.lookup("Hong Kong"), [913110])
        self.assertIsNone(gazetteer._country("Canary Islands"))
        self.assertIsNone(gazetteer._country("Svalbard"))

    def test_country_code_index_is_unambiguous_and_excludes_reserved_codes(self):
        index, codes = gazetteer._country_index()
        self.assertEqual(len(codes), 249)
        for code, names in codes.items():
            self.assertEqual(index[code.lower()], code)
            for name in names:
                self.assertEqual(index[name.casefold()], code)
        self.assertNotIn("EU", codes)
        self.assertNotIn("IC", codes)

    def test_unknown_name_keeps_a_single_name_selector(self):
        with patch.object(gazetteer.osm, "run", return_value={"elements": []}) as run:
            gazetteer.find_relation("Nowhere", None, Path("."))
        self.assertEqual(run.call_args.args[0].count('["name"='), 1)


class LiveMessages(unittest.TestCase):
    def test_live_run_passes_stderr_through_and_still_returns_stdout(self):
        code = "import sys; print('retrying in 15 s', file=sys.stderr); print('result')"
        r = subprocess.run([sys.executable, "-c",
                            f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); import board; "
                            f"r = board._run([sys.executable, '-c', {code!r}], live=True); print('child stdout:', r.stdout.strip(), r.stderr)"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("retrying in 15 s", r.stderr)               # reached the caller's terminal as it happened
        self.assertIn("child stdout: result None", r.stdout)


class ChildMembership(unittest.TestCase):
    def test_membership_uses_any_pack_and_preserves_unknown_or_ambiguous_names(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            items = [{"name": n, "parent": p, "level": lv} for n, p, lv in
                     [("North", "", 1), ("South", "", 1), ("Inside", "North", 2),
                      ("Outside", "South", 2), ("Shared", "North", 2), ("Shared", "South", 2)]]
            (root / 'admin.json').write_text(json.dumps({'items': items}), encoding='utf-8')
            pack = {'code': 'QQ', 'dir': root, 'admin_table': 'admin.json'}
            rows = [{'name': n} for n in ('Inside', 'Outside', 'Shared', 'Unmapped')]
            with patch.object(gazetteer.regions, 'packs', return_value={'QQ': pack}):
                kept = gazetteer._filter_known_neighbours({'name': 'North'}, rows)
            self.assertEqual([r['name'] for r in kept], ['Inside', 'Shared', 'Unmapped'])

    def test_known_neighbour_is_not_added_to_the_wrong_province(self):
        parent = gazetteer._rel_rows({"elements": [INNER_MONGOLIA]})[0]
        data = {"elements": [rel(1, 5, name="呼和浩特市"), rel(2, 5, name="包头市"), rel(3, 5, name="忻州市")]}
        with patch.object(gazetteer, "find_relation", return_value=[parent]), patch.object(gazetteer.osm, "run", return_value=data):
            _, rows = gazetteer.children(parent["name"], None, Path('.'), 5, None)
        self.assertEqual({r['name'] for r in rows}, {"呼和浩特市", "包头市"})

    def test_absent_pack_does_not_silently_filter_osm_children(self):
        parent = gazetteer._rel_rows({"elements": [INNER_MONGOLIA]})[0]
        data = {"elements": [rel(1, 5, name="呼和浩特市"), rel(2, 5, name="包头市"), rel(3, 5, name="忻州市")]}
        with patch.object(gazetteer.regions, "packs", return_value={}), patch.object(gazetteer, "find_relation", return_value=[parent]), patch.object(gazetteer.osm, "run", return_value=data):
            _, rows = gazetteer.children(parent["name"], None, Path('.'), 5, None)
        self.assertEqual(len(rows), 3)

    def test_explicit_level_keeps_a_single_valid_child(self):
        parent = gazetteer._rel_rows({"elements": [INNER_MONGOLIA]})[0]
        data = {"elements": [rel(1, 5, name="呼和浩特市"), rel(2, 5, name="忻州市")]}
        with patch.object(gazetteer, 'find_relation', return_value=[parent]), patch.object(gazetteer.osm, 'run', return_value=data):
            _, rows = gazetteer.children(parent['name'], None, Path('.'), 5, None)
        self.assertEqual([r['name'] for r in rows], ['呼和浩特市'])


if __name__ == "__main__":
    unittest.main()
