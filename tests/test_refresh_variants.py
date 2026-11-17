"""Slice D: refresher wiring (variants, patch dates, calc gate, status heartbeat, no change => no deploy)."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import mw4_parse as P  # noqa: E402
import refresh as R  # noqa: E402

FIX = os.path.join(HERE, "fixtures")
DATA = os.path.join(HERE, "..", "site", "data")
MI_PAGES = ["domination-m4-flag-control", "hijack-m4-defuse-cover", "search-and-destroy-suppressed-m4-entry",
            "m4-all-rounder", "pro-dashy-m4"]


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def make_offline(tmp):
    """An offline source folder (the names refresh.py --offline reads) holding the live M4 pages of 2026-11-17."""
    off = os.path.join(tmp, "offline")
    os.makedirs(off)
    cp = lambda src, dst: shutil.copy(os.path.join(FIX, src), os.path.join(off, dst))  # noqa: E731
    cp("codmunity-live-m4.html", "codmunity-m4.html")
    cp("infil-live-m4.html", "infil-m4.html")
    cp("infil-patches.html", "infil-patches.html")
    cp("mi-sitemap.xml", "mi-sitemap.xml")
    cp("mi-weapon-m4.html", "mi-weapon-m4.html")
    for slug in MI_PAGES:
        cp(f"mi-{slug}.html", f"mi-{slug}.html")
    return off


def make_data(tmp):
    d = os.path.join(tmp, "data")
    os.makedirs(d)
    for n in ("registry.json", "static.json", "bestfor.json", "stat_weights.json"):
        shutil.copy(os.path.join(DATA, n), os.path.join(d, n))
    return d


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = R.main(argv)
    return code, out.getvalue()


ARGS = ["--only", "m4", "--today", "2026-11-17", "--now", "2026-11-17T12:00:00Z"]


class Wiring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.off, self.d = make_offline(self.tmp), make_data(self.tmp)

    def first(self, extra=()):
        return run(["--data-dir", self.d, "--offline", self.off, *ARGS, *extra])

    def test_m4_gun_gets_variants_patch_date_dropped_cands(self):
        code, _ = self.first()
        self.assertEqual(code, 0)
        w = jload(os.path.join(self.d, "weapons.json"))
        self.assertEqual(w["schema"], 2)
        g = next(x for x in w["guns"] if x["slug"] == "m4")
        self.assertEqual(g["patch_date"], "2026-11-13")
        self.assertEqual([d["name"] for d in g["dropped"]], ["Close Range"])
        self.assertEqual(len(g["variants"]), 4)
        self.assertEqual(g["builds"]["main"]["label"], "Versatile")             # the old builds stay
        self.assertEqual([p["label"] for p in g["published"]], ["Early game"])
        self.assertIn("Muzzle", g["cands"])
        self.assertIn("calc_gate", g)
        self.assertEqual(set(g["calc_gate"]), {"pass", "matched", "of", "profile", "reason"})
        used = {c["name"]: c.get("used", 0) for c in g["cands"]["Muzzle"]}
        self.assertGreaterEqual(used["FSS IS300"], 2)                            # CODMunity, Infil early and endgame, MW4 Intel S&D

    def test_calc_gate_file_and_scores_only_when_passed(self):
        self.first()
        gate = jload(os.path.join(self.d, "calc_gate.json"))
        self.assertIn("m4", gate)
        w = jload(os.path.join(self.d, "weapons.json"))
        g = next(x for x in w["guns"] if x["slug"] == "m4")
        has_score = any("score" in c for lst in g["cands"].values() for c in lst)
        self.assertEqual(has_score, gate["m4"]["pass"])

    def test_status_heartbeat(self):
        self.first()
        st = jload(os.path.join(self.d, "status.json"))
        self.assertEqual(st["checked_at"], "2026-11-17T12:00:00Z")
        self.assertEqual(st["checked"], "2026-11-17")
        self.assertEqual(st["failed"], [])
        self.assertEqual(st["patch"]["date"], "2026-11-13")
        self.assertEqual(st["patch"]["name"], "Nov 13 tuning update")
        self.assertEqual(st["variants"], 4)
        self.assertEqual(st["dropped"], 1)
        self.assertEqual(len(st["data_hash"]), 64)

    def test_refresh_no_change_means_no_deploy(self):
        out = os.path.join(self.tmp, "gh_output")
        env = dict(os.environ, GITHUB_OUTPUT=out)
        with unittest.mock.patch.dict(os.environ, env):
            code, text = self.first()
        self.assertIn("DATA_CHANGED=1", text)
        self.assertIn("changed=true", open(out, encoding="utf-8").read())
        files = ("weapons.json", "changes.json", "calc_gate.json")
        before = {n: sha(os.path.join(self.d, n)) for n in files}
        open(out, "w").close()
        with unittest.mock.patch.dict(os.environ, env):
            code, text = run(["--data-dir", self.d, "--offline", self.off, "--only", "m4", "--today", "2026-11-18",
                              "--now", "2026-11-18T06:00:00Z"])
        self.assertEqual(code, 0)
        self.assertIn("DATA_CHANGED=0", text)
        self.assertIn("changed=false", open(out, encoding="utf-8").read())
        self.assertEqual({n: sha(os.path.join(self.d, n)) for n in files}, before)   # a later day alone rewrites nothing
        st = jload(os.path.join(self.d, "status.json"))
        self.assertEqual(st["checked_at"], "2026-11-18T06:00:00Z")                  # the heartbeat still moves

    def test_a_changed_page_means_deploy(self):
        self.first()
        p = os.path.join(self.off, "mi-pro-dashy-m4.html")
        txt = open(p, encoding="utf-8").read().replace("5.56 NATO High Velocity", "5.56 NATO Hollow Point")
        open(p, "w", encoding="utf-8").write(txt)
        code, text = self.first()
        self.assertIn("DATA_CHANGED=1", text)

    def test_mw4intel_page_error_is_loud_and_keeps_previous_variants(self):
        self.first()
        os.remove(os.path.join(self.off, "mi-weapon-m4.html"))
        for s in MI_PAGES:
            os.remove(os.path.join(self.off, f"mi-{s}.html"))
        # offline, a missing MW4 Intel page is "absent" (not an error); an error is simulated through the fetch layer
        real = R.fetch_status
        R.fetch_status = lambda url, *a, **k: ("error", None) if "mw4intel.app" in url else ("absent", None)
        self.addCleanup(setattr, R, "fetch_status", real)
        pages = R.load_extras(R.read_json(os.path.join(self.d, "registry.json"), {"guns": []})["guns"][1:2], {}, None, pause=0)
        self.assertIn("m4:mw4intel", pages["failed"])

    def test_failed_mw4intel_keeps_old_variants_in_build_data(self):
        self.first()
        old = jload(os.path.join(self.d, "weapons.json"))
        reg = [g for g in jload(os.path.join(self.d, "registry.json"))["guns"] if g["slug"] == "m4"]
        pg = {"m4": {"codmunity": P.parse_codmunity(P.html_lines(open(os.path.join(FIX, "codmunity-live-m4.html"), encoding="utf-8").read())),
                     "infil": {"absent": True, "valid": False, "checked": None, "early": None},
                     "mw4intel": [], "mw4intel_weapon": None, "dexerto": None, "mw4intel_failed": True}}
        ctx = R.make_ctx(self.d, [], "2026-11-17T12:00:00Z")
        res = R.build_data(reg, pg, old, "2026-11-17", ctx)
        self.assertIn("m4:mw4intel", res["failed"])
        g = res["data"]["guns"][0]
        self.assertEqual([v["id"] for v in g["variants"]], [v["id"] for v in old["guns"][0]["variants"]])

    def test_diff_logs_variants_added_removed_and_patch(self):
        old = {"name": "M4", "builds": {}, "variants": [{"id": "a", "type": "Versatile", "sources": [{"site": "CODMunity"}]}],
               "patch_date": "2026-11-06"}
        new = {"name": "M4", "builds": {}, "variants": [{"id": "b", "type": "Close Range", "sources": [{"site": "Infil"}]}],
               "patch_date": "2026-11-13"}
        kinds = [(c["kind"], c.get("new") or c.get("old")) for c in R.diff_gun(old, new)]
        self.assertIn(("variant-added", "Close Range"), kinds)
        self.assertIn(("variant-removed", "Versatile"), kinds)
        self.assertIn(("patch", "2026-11-13"), kinds)


class SitemapAssignment(unittest.TestCase):
    def test_loadout_page_goes_to_the_gun_named_by_its_primary(self):
        reg = [g for g in jload(os.path.join(DATA, "registry.json"))["guns"] if g["slug"] in ("m4", "wz-55-striga")]
        ld = {"primary": "M4"}
        self.assertEqual(R.assign_gun(reg, ld), "m4")
        self.assertEqual(R.assign_gun(reg, {"primary": "Wz.55 Striga"}), "wz-55-striga")
        self.assertIsNone(R.assign_gun(reg, {"primary": "Unknown Gun"}))


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
