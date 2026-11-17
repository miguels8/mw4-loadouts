"""Slice B: variants core (collect, standing rules, patch-date drop, best-for table, near-duplicate merge)."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import mw4_parse as P  # noqa: E402
import variants as V  # noqa: E402

DATA = os.path.join(HERE, "..", "site", "data")


def jload(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


BF = jload("bestfor.json")
STATIC = jload("static.json")
REG = {g["slug"]: g for g in jload("registry.json")["guns"]}
MODES = [{"id": m["id"], "name": m["name"]} for m in STATIC["modes"]]


def lines(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return P.html_lines(f.read())


def b(site, name, date, parts, **kw):
    return {"site": site, "name": name, "mode": kw.get("mode"), "kind": kw.get("kind"), "date": date,
            "url": f"https://x/{site}/{name}", "parts": [list(p) for p in parts], "apex": kw.get("apex"),
            "text": kw.get("text"), "site_kit": kw.get("site_kit"), "type": kw.get("type", "Versatile"),
            "best_for": kw.get("best_for", ["TDM"]), "best_for_source": "type"}


P5 = [("Muzzle", "A", 1), ("Barrel", "B", 2), ("Rear Grip", "C", 3), ("Ammunition", "D", 4), ("Underbarrel", "E", 5)]
P5_ALT = [("Muzzle", "A", 1), ("Barrel", "B", 2), ("Rear Grip", "C", 3), ("Ammunition", "D", 4), ("Laser", "Z", 9)]
OTHER = [("Muzzle", "Q", 1), ("Optic", "R", 2), ("Stock", "S", 3), ("Magazine", "T", 4), ("Laser", "U", 5)]


class Merge(unittest.TestCase):
    def test_variant_merge_newest_wins_and_sites_agree(self):
        builds = [b("CODMunity", "Versatile", "2026-11-13", P5, best_for=["TDM", "Frontline"]),
                  b("MW4 Intel", "All-Rounder", "2026-11-16", P5_ALT, best_for=["Domination"]),
                  b("Infil", "Endgame", "2026-11-14", OTHER, type="Close Range", best_for=["Hardpoint"])]
        out = V.merge("m4", builds)
        self.assertEqual(len(out), 2)
        v = next(x for x in out if x["agree"] == 2)
        self.assertEqual(v["date"], "2026-11-16")           # newest site's version
        self.assertEqual(v["parts"][-1], {"slot": "Laser", "name": "Z", "level": 9})
        self.assertEqual([s["site"] for s in v["sources"]], ["MW4 Intel", "CODMunity"])
        self.assertEqual(v["alternatives"], [{"slot": "Underbarrel", "name": "E", "level": 5, "site": "CODMunity"}])
        self.assertEqual(v["best_for"], ["Domination", "TDM", "Frontline"])
        solo = next(x for x in out if x["agree"] == 1)
        self.assertEqual(solo["type"], "Close Range")
        self.assertEqual(solo["alternatives"], [])

    def test_three_of_five_do_not_merge(self):
        three = [("Muzzle", "A", 1), ("Barrel", "B", 2), ("Rear Grip", "C", 3), ("Ammunition", "X", 4), ("Underbarrel", "Y", 5)]
        out = V.merge("m4", [b("CODMunity", "Versatile", "2026-11-13", P5), b("Infil", "Endgame", "2026-11-14", three)])
        self.assertEqual(len(out), 2)

    def test_same_date_tie_prefers_codmunity(self):
        out = V.merge("m4", [b("Infil", "Endgame", "2026-11-14", P5), b("CODMunity", "Versatile", "2026-11-14", P5)])
        self.assertEqual(out[0]["sources"][0]["site"], "CODMunity")
        self.assertEqual(out[0]["agree"], 2)

    def test_two_pages_of_one_site_count_as_one_site(self):
        out = V.merge("m4", [b("MW4 Intel", "Domination", "2026-11-16", P5), b("MW4 Intel", "Hijack", "2026-11-16", P5)])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["agree"], 1)
        self.assertEqual(len(out[0]["sources"]), 2)

    def test_variant_id_is_stable_and_names_the_gun_and_type(self):
        v = V.merge("m4", [b("CODMunity", "Versatile", "2026-11-13", P5)])[0]
        again = V.merge("m4", [b("CODMunity", "Versatile", "2026-11-13", list(reversed(P5)))])[0]
        self.assertEqual(v["id"], again["id"])
        self.assertTrue(v["id"].startswith("m4-versatile-"))
        self.assertEqual(len(v["id"].rsplit("-", 1)[1]), 6)


class StalePatch(unittest.TestCase):
    def test_patch_date_drop(self):
        old = b("CODMunity", "Close Range", "2026-11-07", P5)
        new = b("CODMunity", "Versatile", "2026-11-13", OTHER)
        kept, dropped = V.drop_stale([old, new], "2026-11-13")
        self.assertEqual(kept, [new])
        self.assertEqual(len(dropped), 1)
        self.assertEqual(dropped[0]["reason"], "before the 2026-11-13 patch")
        self.assertEqual((dropped[0]["site"], dropped[0]["name"], dropped[0]["date"]), ("CODMunity", "Close Range", "2026-11-07"))

    def test_no_patch_date_drops_nothing(self):
        kept, dropped = V.drop_stale([b("CODMunity", "Close Range", "2020-01-01", P5)], None)
        self.assertEqual((len(kept), dropped), (1, []))

    def test_undated_build_is_dropped_when_a_patch_exists(self):
        kept, dropped = V.drop_stale([b("Dexerto", "Dexerto build", None, P5)], "2026-11-13")
        self.assertEqual((kept, dropped[0]["reason"]), ([], "no date, cannot show it was re-checked after the 2026-11-13 patch"))

    def test_all_dropped_gives_no_variants(self):
        reg = REG["m4"]
        page = {"codmunity": {"builds": [{"name": "Versatile", "date": "2026-11-01", "parts": [list(p) for p in P5], "apex": None,
                                           "tags": [], "text": None, "levels_missing": False, "rank": "1", "weapon_level": 5}],
                              "table": {}, "optic_labels": {}, "stats": {}, "patch_dates": ["2026-11-13"]},
                "infil": None, "mw4intel": [], "mw4intel_weapon": None, "dexerto": None}
        r = V.build_variants(reg, page, {}, {}, {}, BF, MODES)
        self.assertEqual(r["variants"], [])
        self.assertEqual(len(r["dropped"]), 1)
        self.assertEqual(r["patch_date"], "2026-11-13")

    def test_gun_patch_date_and_latest_patch(self):
        self.assertEqual(V.gun_patch_date(["2026-11-13", "2026-11-06"], ["2026-11-05"]), "2026-11-13")
        self.assertIsNone(V.gun_patch_date([], []))
        lp = V.latest_patch([{"date": "2026-11-13", "name": "Nov 13 tuning update", "tuned": 23}], ["2026-11-15"])
        self.assertEqual(lp["date"], "2026-11-15")
        lp = V.latest_patch([{"date": "2026-11-13", "name": "Nov 13 tuning update", "tuned": 23}], ["2026-11-06"])
        self.assertEqual((lp["date"], lp["name"]), ("2026-11-13", "Nov 13 tuning update"))


class BestFor(unittest.TestCase):
    def test_close_range_type(self):
        c = V.classify("Close Range", None, BF, MODES)
        self.assertEqual(c["type"], "Close Range")
        self.assertEqual(c["best_for"][:3], ["Hardpoint", "Hijack", "Kill Confirmed"])
        self.assertEqual(c["source"], "type")

    def test_mw4intel_mode_is_included_first(self):
        c = V.classify("M4 Flag Control", "Domination", BF, MODES)
        self.assertEqual(c["best_for"][0], "Domination")
        self.assertEqual(c["source"], "mode")
        c = V.classify("Suppressed M4 Entry", "Search & Destroy", BF, MODES)
        self.assertEqual(c["best_for"][0], "S&D")

    def test_keyword(self):
        c = V.classify("ISO Hill Rush", None, BF, MODES)
        self.assertEqual(c["type"], "Close Range")
        self.assertEqual(c["source"], "keyword")
        self.assertIn("Hardpoint", c["best_for"])

    def test_unknown_name_is_versatile_default(self):
        c = V.classify("Zebra Stripe", None, BF, MODES)
        self.assertEqual((c["type"], c["source"]), ("Versatile", "default"))
        self.assertEqual(c["best_for"][:2], ["TDM", "Frontline"])

    def test_sniper_and_pro_and_apex(self):
        self.assertEqual(V.classify("Sniper", None, BF, MODES)["best_for"][0], "S&D")
        p = V.classify("Dashy M4", "Launch-week pro tournaments", BF, MODES, kind="pro")
        self.assertEqual((p["type"], p["best_for"]), ("Pro (Ranked)", ["Hardpoint", "S&D"]))
        a = V.classify("Apex Attachment", None, BF, MODES)
        self.assertEqual(a["type"], "Apex Attachment")
        self.assertEqual(a["note"], "needs max level (Apex)")

    def test_mode_not_ours_falls_back_to_the_name(self):
        c = V.classify("M4 Suppressed Laser", "Shipment", BF, MODES)
        self.assertNotIn("Shipment", c["best_for"])
        self.assertEqual(c["source"], "default")


class StandingRules(unittest.TestCase):
    TABLE = {"Slimline Elite": ["Optic", 10], "ZLR Type C": ["Optic", 27], "Schlager 7x": ["Optic", 19]}
    OPTICS = {"Slimline Elite": "scope", "ZLR Type C": "dot", "Schlager 7x": "scope"}

    def test_ar_variant_with_a_scope_gets_the_one_x_dot(self):
        bld = b("MW4 Intel", "x", "2026-11-16", [("Muzzle", "A", 1), ("Optic", "Slimline Elite", 10), ("Stock", "S", 3), ("Magazine", "T", 4)])
        out = V.apply_rules(REG["m4"], bld, self.TABLE, self.OPTICS, {"ZLR Type C": 3})
        self.assertIn(["Optic", "ZLR Type C", 27], out["parts"])
        self.assertTrue(any("no big scope rule" in n for n in out["notes"]))

    def test_mosin_runs_iron_sights(self):
        bld = b("MW4 Intel", "x", "2026-11-16", [("Muzzle", "A", 1), ("Optic", "Schlager 7x", 19), ("Stock", "S", 3), ("Magazine", "T", 4)])
        out = V.apply_rules(REG["mosin-nagant"], bld, self.TABLE, self.OPTICS, {})
        self.assertFalse([p for p in out["parts"] if p[0] == "Optic"])

    def test_sniper_keeps_its_scope(self):
        bld = b("CODMunity", "Sniper", "2026-11-11", [("Muzzle", "A", 1), ("Optic", "Schlager 7x", 19), ("Stock", "S", 3), ("Comb", "T", 4)])
        out = V.apply_rules(REG["kg-7-vulcan"], bld, self.TABLE, self.OPTICS, {})
        self.assertIn(["Optic", "Schlager 7x", 19], out["parts"])

    def test_hyeon_pick_replaces_ammunition_in_every_variant(self):
        bld = b("CODMunity", "Versatile", "2026-11-11", [("Muzzle", "A", 1), ("Ammunition", "Overpressured", 4), ("Stock", "S", 3), ("Magazine", "T", 4)])
        table = {"IOTA-D": ["Optic", 21]}
        out = V.apply_rules(REG["hyeon-burst"], bld, table, {"IOTA-D": "dot"}, {})
        self.assertIn(["Optic", "IOTA-D", 21], out["parts"])
        self.assertFalse([p for p in out["parts"] if p[0] == "Ammunition"])


class RealM4(unittest.TestCase):
    """The 2026-11-17 live pages for the M4, cut into fixtures."""

    def page(self):
        mi = []
        for slug in ("domination-m4-flag-control", "hijack-m4-defuse-cover", "search-and-destroy-suppressed-m4-entry",
                     "m4-all-rounder", "pro-dashy-m4"):
            r = P.parse_mw4intel_loadout(lines(f"mi-{slug}.html"))
            r["slug"] = slug
            mi.append(r)
        return {"codmunity": P.parse_codmunity(lines("codmunity-live-m4.html")),
                "infil": P.parse_infil(lines("infil-live-m4.html")), "mw4intel": mi,
                "mw4intel_weapon": P.parse_mw4intel_weapon(lines("mi-weapon-m4.html"), "M4"), "dexerto": None}

    def test_m4_variants(self):
        pg = self.page()
        r = V.build_variants(REG["m4"], pg, pg["codmunity"]["table"], {}, {}, BF, MODES)
        self.assertEqual(r["patch_date"], "2026-11-13")
        self.assertEqual([d["name"] for d in r["dropped"]], ["Close Range"])      # 2026-11-07 is before the patch
        self.assertEqual(len(r["variants"]), 4)
        versatile = next(v for v in r["variants"] if v["agree"] == 2)
        self.assertEqual({s["site"] for s in versatile["sources"]}, {"CODMunity", "Infil"})
        self.assertEqual(versatile["date"], "2026-11-14")
        klass = next(v for v in r["variants"] if any(s["name"] == "M4 Flag Control" for s in v["sources"]))
        self.assertEqual(len(klass["sources"]), 3)       # Domination, Hijack and All-Rounder pages share their parts
        self.assertIn("Domination", klass["best_for"])
        self.assertIn("Hijack", klass["best_for"])
        self.assertIn(klass["site_kit"]["perk1"], ("Quick Fix", "Ghost"))
        pro = next(v for v in r["variants"] if v["type"] == "Pro (Ranked)")
        self.assertEqual(pro["best_for"], ["Hardpoint", "S&D"])
        # unlock levels for MW4 Intel parts come from the CODMunity table, never invented
        for v in r["variants"]:
            for p in v["parts"]:
                same = [e[1] for n, e in pg["codmunity"]["table"].items() if n.lower() == p["name"].lower() and e[0] == p["slot"]]
                self.assertEqual(p["level"], same[0] if same else None)
        self.assertTrue(all(v["source_text"] is None or len(v["source_text"]) <= 1500 for v in r["variants"]))


if __name__ == "__main__":
    unittest.main()
