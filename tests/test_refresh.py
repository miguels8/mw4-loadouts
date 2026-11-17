"""Refresher tests: parsing on saved page fixtures, change log, no-big-scope rule, failure handling."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

import mw4_parse as P  # noqa: E402
import refresh as R  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
REGISTRY = json.load(open(os.path.join(HERE, "..", "site", "data", "registry.json"), encoding="utf-8"))


def lines(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return P.html_lines(f.read())


def reg(*slugs):
    return [g for g in REGISTRY["guns"] if g["slug"] in slugs]


INFIL_ABSENT = {"absent": True, "valid": False, "checked": None, "early": None}   # Infil has no page for the gun (404)


def parsed(slug, page=None, infil=None):
    return {"codmunity": P.parse_codmunity(lines(page or f"codmunity-{slug}.html")),
            "infil": P.parse_infil(lines(infil)) if infil else dict(INFIL_ABSENT)}


def sample(extra=None):
    pages = {"m4": parsed("m4", infil="infil-m4.html"),
             "kg-7-vulcan": parsed("kg-7-vulcan"),
             "mosin-nagant": parsed("mosin-nagant"),
             "oris-8-6": parsed("oris-8-6")}
    pages.update(extra or {})
    return pages


OLD_KG7_STAND_IN = {"slot": "Laser", "name": "Schlager Visiv-5", "level": 7}


def old_with_kg7_stand_in():
    return {"guns": [{"slug": "kg-7-vulcan", "builds": {"main": {"parts": [
        {"slot": "Muzzle", "name": "Ivanov QR600", "level": 64, "stand_in": OLD_KG7_STAND_IN}]}}}]}


class StandInCarryOver(unittest.TestCase):
    def test_each_build_keeps_its_own_old_stand_in_for_the_same_part(self):
        """Found in the first real run: main and close both carry Ivanov QR600 with different stand-ins."""
        old = {"guns": [{"slug": "kg-7-vulcan", "builds": {
            "main": {"parts": [{"slot": "Muzzle", "name": "Ivanov QR600", "level": 64, "stand_in": OLD_KG7_STAND_IN}]},
            "close": {"parts": [{"slot": "Muzzle", "name": "Ivanov QR600", "level": 64,
                                 "stand_in": {"slot": "Comb", "name": "TT Type 40 Comb", "level": 6}}]}}}]}
        out = R.build_data(reg("kg-7-vulcan"), {"kg-7-vulcan": parsed("kg-7-vulcan")}, old, "2026-11-16")
        b = out["data"]["guns"][0]["builds"]
        self.assertEqual(b["main"]["parts"][0]["stand_in"], OLD_KG7_STAND_IN)


class ParseCodmunity(unittest.TestCase):
    def test_m4_main_build_and_levels(self):
        c = P.parse_codmunity(lines("codmunity-m4.html"))
        main = c["builds"][0]
        self.assertEqual(main["name"], "Versatile")
        self.assertEqual(main["date"], "2026-11-13")
        self.assertEqual([(p[0], p[1], p[2]) for p in main["parts"]], [
            ("Muzzle", "FSS IS300", 4), ("Barrel", 'FT Cannonade 7"', 7), ("Rear Grip", "Schlager STB Grip", 22),
            ("Ammunition", "5.56 NATO Overpressured", 3), ("Underbarrel", "FSS Tac90 Grip", 17)])

    def test_close_range_build_listed(self):
        c = P.parse_codmunity(lines("codmunity-m4.html"))
        close = next(b for b in c["builds"] if b["name"] == "Close Range")
        self.assertEqual(len(close["parts"]), 5)

    def test_table_has_unlock_levels(self):
        c = P.parse_codmunity(lines("codmunity-m4.html"))
        self.assertEqual(c["table"]["FSS IS300"], ["Muzzle", 4])
        self.assertEqual(c["table"]["5.56 NATO Overpressured"], ["Ammunition", 3])

    def test_optic_labels_read_from_table(self):
        c = P.parse_codmunity(lines("codmunity-oris-8-6.html"))
        self.assertEqual(c["optic_labels"]["ZLR Type C"], "Mini Reflex")
        self.assertEqual(P.optic_class("ZLR Type C", "Mini Reflex"), "dot")
        self.assertEqual(P.optic_class("Cronen R808", ""), "scope")
        self.assertEqual(P.optic_class("Custom Ironsights", ""), "iron")
        self.assertEqual(P.optic_class("Bruen THRM-60 Optic", "Holo"), "dot")
        self.assertEqual(P.optic_class("Schlager 7x", "Rifle Scope"), "scope")

    def test_page_without_builds_parses_to_nothing(self):
        c = P.parse_codmunity(P.html_lines("<html><body><div>Cloudflare</div><div>Just a moment</div></body></html>"))
        self.assertEqual(c["builds"], [])


class ParseInfil(unittest.TestCase):
    def test_early_game_build(self):
        i = P.parse_infil(lines("infil-m4.html"))
        self.assertEqual(i["checked"], "2026-11-14")
        self.assertEqual(i["early"]["complete_level"], 14)
        self.assertEqual([(p[0], p[1], p[2]) for p in i["early"]["parts"]], [
            ("Muzzle", "FSS IS300", 4), ("Optic", "Slimline Elite", 13), ("Stock", "PF1 Fixed Stock", 14),
            ("Ammunition", "5.56 NATO Overpressured", 3), ("Laser", "SZ Gen.6 PEQ", 2)])

    def test_page_without_early_build_is_none(self):
        i = P.parse_infil(P.html_lines("<html><body><div>Best Nothing</div></body></html>"))
        self.assertIsNone(i["early"])


class BuildData(unittest.TestCase):
    def build(self, pages=None, old=None, today="2026-11-16"):
        return R.build_data(reg("m4", "kg-7-vulcan", "mosin-nagant", "oris-8-6"), pages or sample(),
                            old or {"guns": []}, today)

    def gun(self, data, slug):
        return next(g for g in data["data"]["guns"] if g["slug"] == slug)

    def test_kg7_main_build_matches_card(self):
        d = self.build(old=old_with_kg7_stand_in())
        main = self.gun(d, "kg-7-vulcan")["builds"]["main"]
        self.assertEqual([(p["slot"], p["name"], p["level"]) for p in main["parts"]], [
            ("Muzzle", "Ivanov QR600", 64), ("Barrel", 'TT Baem 12"', 5), ("Optic", "Schlager 7x", 19),
            ("Stock", "Bruen KG-7 Mk. IV", 28), ("Comb", "TT Type 40 Comb", 6)])
        self.assertEqual(main["parts"][0]["stand_in"], OLD_KG7_STAND_IN)
        self.assertEqual(main["date"], "2026-11-11")
        self.assertIn("codmunity.gg/weapon/mw4/kg-7-vulcan", main["url"])

    def test_stand_in_opens_five_levels_early_and_is_never_an_optic(self):
        d = self.build()
        seen = 0
        for g in d["data"]["guns"]:
            for b in g["builds"].values():
                for p in (b or {}).get("parts", []):
                    s = p.get("stand_in")
                    if s:
                        seen += 1
                        self.assertLessEqual(s["level"], p["level"] - 5)
                        self.assertNotEqual(s["slot"], "Optic")
        self.assertGreater(seen, 0)

    def test_close_build_present_and_early_build_attached(self):
        d = self.build()
        m4 = self.gun(d, "m4")
        self.assertEqual(m4["builds"]["close"]["label"], "Close Range")
        self.assertEqual(m4["builds"]["early"]["complete_level"], 14)
        self.assertIn("infil.app/loadouts/m4", m4["builds"]["early"]["url"])
        self.assertIsNone(self.gun(d, "kg-7-vulcan")["builds"]["early"])

    def test_no_big_scope_rule(self):
        d = self.build()
        oris = self.gun(d, "oris-8-6")
        for key in ("main", "close"):
            for p in oris["builds"][key]["parts"]:
                if p["slot"] == "Optic":
                    self.assertEqual(d["data"]["optics"][p["name"]], "dot", p)
        notes = oris["builds"]["main"].get("notes", []) + oris["builds"]["close"].get("notes", [])
        self.assertTrue(any("no big scope" in n.lower() for n in notes))

    def test_mosin_runs_iron_sights(self):
        d = self.build()
        mosin = self.gun(d, "mosin-nagant")
        for key in ("main", "close"):
            self.assertFalse([p for p in mosin["builds"][key]["parts"] if p["slot"] == "Optic"])

    def test_sniper_keeps_sniper_scope(self):
        d = self.build()
        kg7 = self.gun(d, "kg-7-vulcan")
        optic = next(p for p in kg7["builds"]["main"]["parts"] if p["slot"] == "Optic")
        self.assertEqual(optic["name"], "Schlager 7x")

    def test_event_reward_level_stays_unpublished(self):
        pg = parsed("m4")
        pg["codmunity"]["builds"][0]["parts"][0][2] = None
        d = R.build_data(reg("m4"), {"m4": pg}, {"guns": []}, "2026-11-16")
        self.assertIsNone(self.gun(d, "m4")["builds"]["main"]["parts"][0]["level"])

    def test_apex_on_only_when_source_build_lists_it(self):
        pg = parsed("m4")
        pg["codmunity"]["builds"][0]["apex"] = None
        d = R.build_data(reg("m4"), {"m4": pg}, {"guns": []}, "2026-11-16")
        self.assertFalse(self.gun(d, "m4")["builds"]["main"]["apex_on"])

    def test_pick_replaces_slot_part(self):
        parts = [["Muzzle", "A", 1], ["Ammunition", "B", 2]]
        out, notes = R.apply_pick(parts, {"slot": "Optic", "name": "IOTA-D", "replaces": "Ammunition"}, 35)
        self.assertEqual(out, [["Muzzle", "A", 1], ["Optic", "IOTA-D", 35]])
        self.assertTrue(notes)

    def test_pick_kept_in_hyeon_registry(self):
        hy = next(g for g in REGISTRY["guns"] if g["slug"] == "hyeon-burst")
        self.assertEqual(hy["pick"]["name"], "IOTA-D")


class ChangeLog(unittest.TestCase):
    def test_changed_page_makes_change_entry(self):
        base = R.build_data(reg("m4"), {"m4": parsed("m4")}, {"guns": []}, "2026-11-15")
        new = R.build_data(reg("m4"), {"m4": parsed("m4", page="codmunity-m4-changed.html")},
                           base["data"], "2026-11-16")
        e = next(x for x in new["changes"] if x["gun"] == "M4" and x["build"] == "main" and x["slot"] == "Muzzle")
        self.assertEqual((e["old"], e["new"]), ("FSS IS300", "FSS IS40"))
        self.assertEqual(e["source_date"], "2026-11-15")

    def test_identical_page_makes_no_entry(self):
        base = R.build_data(reg("m4"), {"m4": parsed("m4")}, {"guns": []}, "2026-11-15")
        again = R.build_data(reg("m4"), {"m4": parsed("m4")}, base["data"], "2026-11-16")
        self.assertEqual(again["changes"], [])

    def test_history_appends_newest_first(self):
        hist = R.add_history([{"date": "2026-11-15", "changes": [{"gun": "x"}]}], "2026-11-16", [{"gun": "M4"}])
        self.assertEqual([h["date"] for h in hist], ["2026-11-16", "2026-11-15"])

    def test_history_skips_empty_refresh(self):
        hist = R.add_history([{"date": "2026-11-15", "changes": [{"gun": "x"}]}], "2026-11-16", [])
        self.assertEqual(len(hist), 1)


class NoLevelLayout(unittest.TestCase):
    """CODMunity's MAR-9 page, read live on 2026-11-16, shows parts with no '· Level N' line and no attachment table."""

    def page(self):
        return {"codmunity": P.parse_codmunity(lines("codmunity-mar-9-nolevels.html")), "infil": dict(INFIL_ABSENT)}

    def test_parts_parse_with_unknown_levels(self):
        b = self.page()["codmunity"]["builds"][0]
        self.assertTrue(b["levels_missing"])
        self.assertEqual([p[:2] for p in b["parts"]][-1], ["Magazine", "30 Round Mag"])
        self.assertEqual(len(b["parts"]), 5)
        self.assertTrue(all(p[2] is None for p in b["parts"]))

    def test_levels_carried_from_last_check_never_invented(self):
        old = {"checked": "2026-11-15", "optics": {}, "guns": [{"slug": "mar-9", "apex": {"name": "MAR-9 Auto", "level": 73},
               "table": {}, "builds": {"main": {"parts": [
                   {"slot": "Muzzle", "name": "Meiko 30CAL-SP", "level": 2, "stand_in": None},
                   {"slot": "Laser", "name": "SZ Gen.6 PEQ", "level": 5, "stand_in": None}]}}}]}
        out = R.build_data(reg("mar-9"), {"mar-9": self.page()}, old, "2026-11-16")
        self.assertEqual(out["failed"], [])
        parts = {p["name"]: p["level"] for p in out["data"]["guns"][0]["builds"]["main"]["parts"]}
        self.assertEqual(parts["Meiko 30CAL-SP"], 2)
        self.assertEqual(parts["SZ Gen.6 PEQ"], 5)
        self.assertIsNone(parts["30 Round Mag"])
        self.assertTrue(out["data"]["guns"][0]["builds"]["main"]["notes"])

    def test_empty_build_is_a_failure(self):
        empty = {"codmunity": {"title": "x", "table": {}, "optic_labels": {},
                               "builds": [{"name": "Versatile", "date": "2026-11-16", "parts": [], "apex": None}]},
                 "infil": None}
        out = R.build_data(reg("m4"), {"m4": empty}, {"guns": []}, "2026-11-16")
        self.assertEqual(out["failed"], ["m4"])


class ReviewFindings(unittest.TestCase):
    """Independent review round 1 (gpt-6.1-sol): F1 Infil failures were silent, F2 only the main build was validated."""

    def base(self):
        return R.build_data(reg("m4"), {"m4": parsed("m4", infil="infil-m4.html")}, {"guns": []}, "2026-11-15")

    def run_with(self, infil):
        pg = parsed("m4")
        pg["infil"] = infil
        return R.build_data(reg("m4"), {"m4": pg}, self.base()["data"], "2026-11-16")

    def test_f1_unreadable_infil_is_a_failure_and_keeps_old_early_build(self):
        out = self.run_with(None)
        self.assertEqual(out["failed"], ["m4:infil"])
        self.assertEqual(out["data"]["checked"], "2026-11-15")
        self.assertEqual(out["data"]["guns"][0]["builds"]["early"]["complete_level"], 14)
        self.assertEqual(R.exit_code(out["failed"]), 1)

    def test_f1_challenge_page_is_a_failure_not_a_removed_early_build(self):
        out = self.run_with(P.parse_infil(P.html_lines("<h1>Just a moment</h1>")))
        self.assertEqual(out["failed"], ["m4:infil"])
        self.assertIsNotNone(out["data"]["guns"][0]["builds"]["early"])

    def test_f1_valid_page_without_early_build_is_fine_and_clears_it(self):
        page = P.parse_infil(P.html_lines("<div>Best M4</div><div>Builds</div><div>Endgame build</div>"
                                          "<div>1</div><div>Muzzle</div><div>Weapon Lvl 4</div><div>X</div>"
                                          "<div>Copy build</div>"))
        self.assertTrue(page["valid"])
        out = self.run_with(page)
        self.assertEqual(out["failed"], [])
        self.assertIsNone(out["data"]["guns"][0]["builds"]["early"])

    def test_f1_absent_page_is_not_a_failure(self):
        out = self.run_with(dict(INFIL_ABSENT))
        self.assertEqual(out["failed"], [])

    def test_f1_infil_slug_for_striga(self):
        g = next(x for x in REGISTRY["guns"] if x["slug"] == "wz-55-striga")
        self.assertEqual(g["infil_slug"], "wz55-striga")

    def test_f2_empty_close_build_is_a_failure(self):
        pg = parsed("m4", infil="infil-m4.html")
        close = next(b for b in pg["codmunity"]["builds"] if b["name"] == "Close Range")
        close["parts"] = []
        out = R.build_data(reg("m4"), {"m4": pg}, self.base()["data"], "2026-11-16")
        self.assertEqual(out["failed"], ["m4"])
        self.assertTrue(out["data"]["guns"][0]["builds"]["close"]["parts"])

    def test_f2_duplicate_slots_in_a_build_are_a_failure(self):
        pg = parsed("m4", infil="infil-m4.html")
        pg["codmunity"]["builds"][0]["parts"].append(["Muzzle", "Bleed", 9])
        out = R.build_data(reg("m4"), {"m4": pg}, self.base()["data"], "2026-11-16")
        self.assertEqual(out["failed"], ["m4"])


class Failures(unittest.TestCase):
    def test_failed_page_keeps_old_gun_and_is_reported(self):
        base = R.build_data(reg("m4"), {"m4": parsed("m4")}, {"guns": []}, "2026-11-15")
        bad = {"m4": {"codmunity": P.parse_codmunity(P.html_lines("<div>blocked</div>")), "infil": None}}
        out = R.build_data(reg("m4"), bad, base["data"], "2026-11-16")
        self.assertEqual(out["failed"], ["m4"])
        self.assertEqual(out["data"]["guns"][0]["builds"]["main"], base["data"]["guns"][0]["builds"]["main"])
        self.assertEqual(out["data"]["checked"], "2026-11-15")

    def test_missing_page_is_failure(self):
        out = R.build_data(reg("m4"), {"m4": None}, {"guns": []}, "2026-11-16")
        self.assertEqual(out["failed"], ["m4"])
        self.assertEqual(out["data"]["guns"], [])

    def test_clean_run_sets_checked_date(self):
        out = R.build_data(reg("m4"), {"m4": parsed("m4")}, {"guns": []}, "2026-11-16")
        self.assertEqual(out["failed"], [])
        self.assertEqual(out["data"]["checked"], "2026-11-16")

    def test_exit_code_is_nonzero_on_failure(self):
        self.assertEqual(R.exit_code(["m4"]), 1)
        self.assertEqual(R.exit_code([]), 0)

    def test_gun_without_infil_has_no_early_build(self):
        out = R.build_data(reg("m4"), {"m4": parsed("m4")}, {"guns": []}, "2026-11-16")
        self.assertEqual(out["failed"], [])
        self.assertIsNone(out["data"]["guns"][0]["builds"]["early"])


if __name__ == "__main__":
    unittest.main()
