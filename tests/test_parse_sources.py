"""Slice A: parsers for the new sources (MW4 Intel, Dexerto, Infil patches/endgame, CODMunity patch notes + stats)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import mw4_parse as P  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def lines(name):
    return P.html_lines(open(os.path.join(FIX, name), encoding="utf-8").read())


class CodmunityNew(unittest.TestCase):
    def test_patch_dates_of_m4(self):
        c = P.parse_codmunity(lines("codmunity-live-m4.html"))
        self.assertEqual(c["patch_dates"], ["2026-11-13", "2026-11-06", "2026-10-28"])

    def test_page_without_patch_block_has_no_patch_dates(self):
        self.assertEqual(P.parse_codmunity(lines("codmunity-m4.html"))["patch_dates"], [])

    def test_attachment_stats_read(self):
        c = P.parse_codmunity(lines("codmunity-live-m4.html"))
        st = c["stats"]
        self.assertEqual(st["5.56 NATO High Velocity"], {"Bullet Velocity": 20.0, "Range": 6.0})
        self.assertEqual(st["5.56 NATO Hollow Point"], {})            # "—" = no stats
        self.assertEqual(st["11.5 Shortline Barrel"]["ADS Speed"], -9.0)
        self.assertEqual(st["11.5 Shortline Barrel"]["Sprint"], 2.0)

    def test_only_multiplayer_builds_count(self):
        c = P.parse_codmunity(lines("codmunity-live-m4.html"))
        self.assertEqual([b["name"] for b in c["builds"]], ["Versatile", "Close Range"])

    def test_premium_locked_block_is_not_a_build(self):
        L = lines("codmunity-live-m4.html")
        L = L + ["Loadout (MW4 Multiplayer)", "#", "9", "This build’s attachments and code are reserved for Premium members."]
        L.insert(len(L) - 4, "Max Damage Range")
        c = P.parse_codmunity(L)
        self.assertEqual(len(c["builds"]), 2)

    def test_build_text_is_none_when_page_has_no_prose(self):
        c = P.parse_codmunity(lines("codmunity-live-m4.html"))
        self.assertTrue(all(b.get("text") in (None, "") for b in c["builds"]))


class InfilNew(unittest.TestCase):
    def test_endgame_build_and_blurb_and_history(self):
        i = P.parse_infil(lines("infil-live-m4.html"))
        self.assertEqual(i["checked"], "2026-11-14")
        self.assertEqual([p[:2] for p in i["endgame"]["parts"]],
                         [["Muzzle", "FSS IS300"], ["Barrel", 'FT Cannonade 7"'], ["Rear Grip", "Schlager STB Grip"],
                          ["Ammunition", "5.56 NATO Overpressured"], ["Underbarrel", "FSS Tac90 Grip"]])
        self.assertEqual(i["endgame"]["complete_level"], 22)
        self.assertTrue(i["blurb"].startswith("Fires faster than the HAN 86"))
        self.assertEqual(i["patch_history"][0], {"date": "2026-11-13", "name": "Nov 13 tuning update",
                                                 "text": "Buffed: Its full-damage range grows from about 28 m to about 35 m. · Tier A → S"})
        self.assertEqual(i["early"]["complete_level"], 14)

    def test_old_fixture_still_has_early_and_no_endgame_crash(self):
        i = P.parse_infil(lines("infil-m4.html"))
        self.assertIsNotNone(i["early"])
        self.assertIn("endgame", i)

    def test_balance_dates_only_buffed_or_nerfed(self):
        i = P.parse_infil(lines("infil-live-m4.html"))
        self.assertEqual(P.infil_balance_dates(i), ["2026-11-13", "2026-11-05", "2026-10-28"])   # Nov 2 was tier-only

    def test_patches_page(self):
        pp = P.parse_infil_patches(lines("infil-patches.html"))
        self.assertEqual(pp[0], {"date": "2026-11-13", "name": "Nov 13 tuning update", "tuned": 23})
        self.assertEqual(pp[2], {"date": "2026-11-02", "name": "Nov 2 update", "tuned": None})
        self.assertEqual(P.latest_balance_patch(pp)["date"], "2026-11-13")


class MW4Intel(unittest.TestCase):
    def test_print_block_domination(self):
        r = P.parse_mw4intel_loadout(lines("mi-domination-m4-flag-control.html"))
        self.assertEqual(r["name"], "M4 Flag Control")
        self.assertEqual(r["mode"], "Domination")
        self.assertEqual(r["primary"], "M4")
        self.assertEqual(r["parts"], [["Muzzle", "TZL-110 V1"], ["Laser", "SA LAZ-500"], ["Magazine", "45 Round Mag"],
                                      ["Rear Grip", "ZLR Phase Grip"], ["Underbarrel", "FSS Fireline Grip"]])
        self.assertEqual(r["perks"], ["Quick Fix", "Fast Hands", "Battle Hardened"])
        self.assertEqual((r["tactical"], r["lethal"], r["field"]), ("Concussion Grenade", "Frag Grenade", "Trophy System"))
        self.assertEqual(r["updated"], "2026-11-16")
        self.assertIn("Trophy protects the point", r["notes"])

    def test_print_block_without_perks_or_notes(self):
        r = P.parse_mw4intel_loadout(lines("mi-pro-dashy-m4.html"))
        self.assertEqual(r["mode"], "Launch-week pro tournaments")
        self.assertEqual(len(r["parts"]), 5)
        self.assertEqual(r["perks"], [])
        self.assertEqual(r["updated"], "2026-11-16")

    def test_snd_page_parts(self):
        r = P.parse_mw4intel_loadout(lines("mi-search-and-destroy-suppressed-m4-entry.html"))
        self.assertEqual(r["mode"], "Search & Destroy")
        self.assertEqual(r["parts"][-1], ["Optic", "Slimline Elite"])

    def test_no_print_block_is_none(self):
        self.assertIsNone(P.parse_mw4intel_loadout(["nothing", "here"]))

    def test_weapon_page(self):
        w = P.parse_mw4intel_weapon(lines("mi-weapon-m4.html"), "M4")
        self.assertEqual(w["howto"], ["Build for recoil and range; it already handles well.",
                                      "Use it as your first class while you level everything else.",
                                      "On SMG-heavy maps, try the Hurricane Apex instead of switching guns."])
        self.assertEqual(w["updated"], "2026-11-16")

    def test_sitemap_keeps_mp_loadouts_only(self):
        xml = open(os.path.join(FIX, "mi-sitemap.xml"), encoding="utf-8").read()
        slugs = P.parse_mw4intel_sitemap(xml)
        self.assertIn("domination-m4-flag-control", slugs)
        self.assertIn("pro-dashy-m4", slugs)
        self.assertFalse([s for s in slugs if s.startswith(("dmz-", "warzone-", "community"))])
        self.assertNotIn("builder", slugs)
        self.assertTrue(len(slugs) > 40)


class Dexerto(unittest.TestCase):
    def test_patriot_page(self):
        d = P.parse_dexerto(lines("dx-patriot-xmr.html"))
        self.assertEqual(d["date"], "2026-08-21")
        self.assertEqual(d["parts"], [["Muzzle", "Meiko 30CAL-SP"], ["Laser", "SA Laz-500"], ["Optic", "SZ Prima-4 Dot"],
                                      ["Rear Grip", "Schlager Attack-7 Grip"], ["Magazine", "35 Round Mag"]])
        self.assertEqual(d["perks"], ["Ghost", "Ninja", "Battle Hardened"])
        self.assertEqual(d["equipment"], ["Concussion Grenade", "Frag Grenade", "Trophy System"])

    def test_not_a_loadout_page_is_none(self):
        self.assertIsNone(P.parse_dexerto(["Some", "page"]))


if __name__ == "__main__":
    unittest.main()
