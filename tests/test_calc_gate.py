"""Slice C: calculated picks (step 3) and the Q4 gate (>= 4 of 5 slots must match the CODMunity build at max level)."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import calc as C  # noqa: E402
import mw4_parse as P  # noqa: E402

W = {"stats": {"ADS Speed": {"dir": -1, "close": 3.0, "range": 0.5},
               "Horizontal Recoil": {"dir": -1, "close": 1.0, "range": 2.0},
               "Range": {"dir": 1, "close": 1.0, "range": 3.0},
               "Movement": {"dir": 1, "close": 1.5, "range": 0.3}}}


def row(slot, level, **stats):
    return {"slot": slot, "level": level, "stats": stats}


# Per slot there is one clear winner for the range profile, and a different winner for the close profile.
TABLE = {
    "Muzzle-R": row("Muzzle", 5, Range=6.0), "Muzzle-C": row("Muzzle", 6, Movement=4.0, **{"ADS Speed": -9.0}),
    "Barrel-R": row("Barrel", 7, Range=15.0, **{"ADS Speed": 11.0}), "Barrel-C": row("Barrel", 8, Movement=4.0),
    "Grip-R": row("Rear Grip", 9, **{"Horizontal Recoil": -10.0}), "Grip-C": row("Rear Grip", 9, Movement=3.0),
    "Mag-R": row("Magazine", 10, Range=2.0), "Mag-C": row("Magazine", 11, Movement=-1.0),
    "UB-R": row("Underbarrel", 12, **{"Horizontal Recoil": -8.0}), "UB-C": row("Underbarrel", 13, Movement=2.0),
    "Laser-X": row("Laser", 14, Movement=0.5), "Dot": row("Optic", 15, Movement=1.0), "Scope": row("Optic", 16, Range=50.0),
    "Event": row("Stock", None, Range=99.0), "Apex-X": row("Apex", 70, Range=99.0),
}
RULES = {"optics": {"Dot": "dot", "Scope": "scope"}, "iron_sights": False}


class Score(unittest.TestCase):
    def test_score_uses_direction_and_profile(self):
        self.assertEqual(C.score({"ADS Speed": -9.0, "Movement": 4.0}, W, "close"), 3.0 * 9 + 1.5 * 4)
        self.assertEqual(C.score({"Horizontal Recoil": -10.0}, W, "range"), 20.0)
        self.assertEqual(C.score({"Unknown Stat": 5.0}, W, "range"), 0.0)   # a stat with no weight counts nothing


class CalcBuild(unittest.TestCase):
    def test_range_profile_picks_the_range_parts_and_five_distinct_slots(self):
        b = C.calc_build(TABLE, W, "range", "AR", RULES)
        slots = [p[0] for p in b]
        self.assertEqual(len(b), 5)
        self.assertEqual(len(set(slots)), 5)
        names = {p[1] for p in b}
        self.assertTrue({"Barrel-R", "Muzzle-R", "Grip-R", "UB-R"} <= names)

    def test_unknown_level_and_apex_are_never_calculated(self):
        names = {p[1] for p in C.calc_build(TABLE, W, "range", "AR", RULES)}
        self.assertNotIn("Event", names)
        self.assertNotIn("Apex-X", names)

    def test_optic_rule_for_rifles_one_x_dot_only(self):
        b = C.calc_build(TABLE, W, "range", "AR", RULES)
        self.assertNotIn("Scope", {p[1] for p in b})
        s = C.calc_build(TABLE, W, "range", "Sniper", RULES)
        self.assertIn("Scope", {p[1] for p in s})

    def test_iron_sights_gun_gets_no_optic(self):
        b = C.calc_build(TABLE, W, "close", "Marksman", {"optics": RULES["optics"], "iron_sights": True})
        self.assertNotIn("Optic", {p[0] for p in b})


class Gate(unittest.TestCase):
    PRO = [["Muzzle", "Muzzle-R"], ["Barrel", "Barrel-R"], ["Rear Grip", "Grip-R"], ["Underbarrel", "UB-R"], ["Magazine", "Mag-R"]]

    def test_pass_fixture_five_of_five_and_four_of_five(self):
        calc = C.calc_build(TABLE, W, "range", "AR", RULES)
        g = C.gate(calc, self.PRO)
        self.assertEqual((g["matched"], g["of"], g["pass"]), (5, 5, True))
        four = [list(x) for x in self.PRO]
        four[4] = ["Magazine", "Mag-C"]
        g = C.gate(calc, four)
        self.assertEqual((g["matched"], g["pass"]), (4, True))

    def test_fail_fixture_three_of_five(self):
        calc = C.calc_build(TABLE, W, "range", "AR", RULES)
        three = [list(x) for x in self.PRO]
        three[3], three[4] = ["Underbarrel", "UB-C"], ["Magazine", "Mag-C"]
        g = C.gate(calc, three)
        self.assertEqual((g["matched"], g["of"], g["pass"]), (3, 5, False))

    def test_same_slot_and_same_name_both_count(self):
        g = C.gate([["Muzzle", "A"]], [["Muzzle", "B"], ["Barrel", "A"]])
        self.assertEqual(g["matched"], 0)

    def test_cands_carry_scores_only_when_the_gate_passed(self):
        passed = C.cands(TABLE, W, True)
        failed = C.cands(TABLE, W, False)
        self.assertEqual(passed["Barrel"][0]["name"], "Barrel-R")      # best first for the range profile
        self.assertEqual(set(passed["Barrel"][0]["score"]), {"close", "range"})
        for slot, lst in failed.items():
            self.assertTrue(all("score" not in c for c in lst))
        self.assertTrue(all(c["level"] is None or isinstance(c["level"], int) for lst in failed.values() for c in lst))

    def test_gun_gate_without_stats_fails_with_reason(self):
        r = C.gun_gate({"Muzzle-R": {"slot": "Muzzle", "level": 5, "stats": {}}}, W, [["Muzzle", "Muzzle-R"]] * 5,
                       "Versatile", "AR", RULES)
        self.assertFalse(r["pass"])
        self.assertEqual(r["reason"], "no stats published")

    def test_gun_gate_picks_profile_from_the_pro_build_type(self):
        r = C.gun_gate(TABLE, W, Gate.PRO, "Versatile", "AR", RULES)
        self.assertEqual((r["profile"], r["pass"], r["matched"]), ("range", True, 5))
        r = C.gun_gate(TABLE, W, Gate.PRO, "Close Range", "AR", RULES)
        self.assertEqual(r["profile"], "close")


class RealWeights(unittest.TestCase):
    def test_weights_file_has_evidence_for_the_time_style_stats(self):
        with open(os.path.join(HERE, "..", "site", "data", "stat_weights.json"), encoding="utf-8") as f:
            w = json.load(f)
        for k in ("ADS Speed", "Sprint To Fire", "Horizontal Recoil", "Range", "Movement"):
            self.assertIn(k, w["stats"])
        self.assertEqual(w["stats"]["ADS Speed"]["dir"], -1)       # a time: the stock-less build shows -17 and is the fast one
        self.assertIn("evidence", w)


if __name__ == "__main__":
    unittest.main()
