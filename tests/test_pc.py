"""Slice H: the three MiguelPC user-timer scripts (stale alarm, strategy notes, Opus review trigger).
Pure functions with injected fetch/run, so nothing here touches the network, Telegram, the Go key or job-dispatch."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pc"))
import mw4_alarm as A  # noqa: E402
import mw4_review as RV  # noqa: E402
import mw4_strategy as S  # noqa: E402

NOW = "2026-11-17T12:00:00Z"


def hrs(n):
    import datetime as dt
    t = dt.datetime.fromisoformat(NOW.replace("Z", "+00:00")) - dt.timedelta(hours=n)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class Alarm(unittest.TestCase):
    def test_assess(self):
        self.assertEqual(A.assess({"checked_at": hrs(2), "failed": []}, NOW), (False, None))
        bad, why = A.assess({"checked_at": hrs(25), "failed": []}, NOW)
        self.assertTrue(bad)
        self.assertIn("25 h old", why)
        bad, why = A.assess({"checked_at": hrs(1), "failed": ["mar-9", "m4:mw4intel"]}, NOW)
        self.assertTrue(bad)
        self.assertIn("mar-9", why)
        self.assertTrue(A.assess(None, NOW)[0])
        self.assertTrue(A.assess({"failed": []}, NOW)[0])                       # no timestamp: unreadable
        self.assertFalse(A.assess({"checked_at": hrs(6.5), "failed": []}, NOW)[0])   # 7 h threshold (mw4-refresh-fix)

    def test_fresh_posts_nothing(self):
        post, text, st = A.decide({}, False, None, NOW, "x")
        self.assertFalse(post)
        self.assertFalse(st["bad"])

    def test_stale_posts_once_then_every_12_hours(self):
        post, text, st = A.decide({}, True, "data is 25 h old", NOW, "last check Nov 16")
        self.assertTrue(post)
        self.assertIn("MW4 Loadouts: data is 25 h old", text)
        self.assertIn("red banner", text)
        st = A.after_post(st, NOW)
        post2, _, _ = A.decide(st, True, "data is 26 h old", hrs(-5), "x")      # 5 h later: quiet
        self.assertFalse(post2)
        post3, _, _ = A.decide(st, True, "data is 40 h old", hrs(-13), "x")     # 13 h later: reminder
        self.assertTrue(post3)

    def test_back_to_normal_posts_once(self):
        st = {"bad": True, "last_post": hrs(3), "reason": "x"}
        post, text, st2 = A.decide(st, False, None, NOW, "x")
        self.assertTrue(post)
        self.assertIn("back to normal", text)
        self.assertFalse(st2["bad"])

    def test_main_with_status_file_posts_through_the_route_and_records_state_only_on_success(self):
        with tempfile.TemporaryDirectory() as d:
            sf = os.path.join(d, "status.json")
            json.dump({"checked_at": hrs(30), "failed": []}, open(sf, "w"))
            state = os.path.join(d, "alarm.json")
            calls = []
            code = A.main(["--status-file", sf, "--state", state], now=NOW, run=lambda cmd, text: calls.append((cmd, text)) or 0)
            self.assertEqual(code, 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0][-2:], ["alerts", calls[0][1]])
            self.assertTrue(json.load(open(state))["bad"])
            A.main(["--status-file", sf, "--state", state], now=NOW, run=lambda cmd, text: calls.append((cmd, text)) or 0)
            self.assertEqual(len(calls), 1, "second run within 12 h posts nothing")
            os.remove(state)
            calls.clear()
            A.main(["--status-file", sf, "--state", state], now=NOW, run=lambda cmd, text: 4)   # Telegram rejected it
            self.assertFalse(os.path.exists(state), "a failed post is not recorded, so the next run tries again")

    def test_force_posts_a_test_message_even_when_fresh_and_even_after_a_post(self):
        with tempfile.TemporaryDirectory() as d:
            sf = os.path.join(d, "status.json")
            json.dump({"checked_at": hrs(30), "failed": []}, open(sf, "w"))
            calls = []
            run = lambda cmd, text: calls.append(text) or 0  # noqa: E731
            A.main(["--status-file", sf, "--state", os.path.join(d, "s.json"), "--force"], now=NOW, run=run)
            A.main(["--status-file", sf, "--state", os.path.join(d, "s.json"), "--force"], now=NOW, run=run)
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(c.startswith("TEST: MW4 Loadouts:") for c in calls))
            self.assertFalse(os.path.exists(os.path.join(d, "s.json")), "a forced test never touches the alarm state")

    def test_dry_run_posts_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            sf = os.path.join(d, "status.json")
            json.dump({"checked_at": hrs(30), "failed": []}, open(sf, "w"))
            calls = []
            A.main(["--status-file", sf, "--state", os.path.join(d, "s.json"), "--dry-run"], now=NOW, run=lambda c, t: calls.append(t) or 0)
            self.assertEqual(calls, [])

    def test_unreadable_status_is_an_alarm(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            A.main(["--state", os.path.join(d, "s.json")], now=NOW, fetch=lambda url: None, run=lambda c, t: calls.append(t) or 0)
            self.assertEqual(len(calls), 1)
            self.assertIn("could not be read", calls[0])


def weapons(*variants):
    return {"guns": [{"slug": "m4", "name": "M4", "variants": [dict(id=i, type=t, label=t, source_text=txt, parts=[], sources=[]) for i, t, txt in variants]}]}


class Strategy(unittest.TestCase):
    def run_it(self, w, strat=None, reply=(0, "It is quick. Use it up close. Keep moving."), maxcalls=20):
        calls = []

        def runner(prompt):
            calls.append(prompt)
            return reply
        out = S.run(w, strat or {}, runner, NOW, model="test-model", max_calls=maxcalls)
        return out, calls

    def test_no_new_variant_means_no_call(self):
        out, calls = self.run_it(weapons(("a", "Versatile", "text")), {"a": {"text": "done", "model": "m", "at": NOW, "attempts": 1}})
        self.assertEqual(calls, [])
        self.assertFalse(out["changed"])

    def test_new_variant_means_exactly_one_call_with_only_the_site_text(self):
        out, calls = self.run_it(weapons(("a", "Versatile", "Site says: stay mid range."), ("b", "Close Range", "")))
        self.assertEqual(len(calls), 1)
        self.assertIn("ONLY this text", calls[0])
        self.assertIn("Site says: stay mid range.", calls[0])
        self.assertIn("M4", calls[0])
        self.assertTrue(out["changed"])
        self.assertEqual(out["strategy"]["a"]["text"], "It is quick. Use it up close. Keep moving.")
        self.assertEqual(out["strategy"]["a"]["model"], "test-model")
        self.assertNotIn("b", out["strategy"], "no source text: no call, the fixed template shows")

    def test_failure_counts_an_attempt_and_two_attempts_give_up(self):
        w = weapons(("a", "Versatile", "text"))
        out, calls = self.run_it(w, reply=(1, ""))
        self.assertEqual(out["strategy"]["a"]["attempts"], 1)
        self.assertIsNone(out["strategy"]["a"]["text"])
        out, calls = self.run_it(w, out["strategy"], reply=(1, ""))
        self.assertEqual(out["strategy"]["a"]["attempts"], 2)
        out, calls = self.run_it(w, out["strategy"], reply=(0, "fine fine fine fine fine fine fine fine."))
        self.assertEqual(calls, [], "after 2 failed attempts the template stays")

    def test_a_reply_that_is_not_three_plain_sentences_is_a_failed_attempt(self):
        w = weapons(("a", "Versatile", "text"))
        out, _ = self.run_it(w, reply=(0, "ok"))
        self.assertIsNone(out["strategy"]["a"]["text"])
        out, _ = self.run_it(w, reply=(0, "x" * 900))
        self.assertIsNone(out["strategy"]["a"]["text"])

    def test_at_most_max_calls_per_run(self):
        w = weapons(*[(f"v{i}", "Versatile", "text") for i in range(30)])
        out, calls = self.run_it(w, maxcalls=20)
        self.assertEqual(len(calls), 20)

    def test_the_helper_runs_under_the_hermes_python_with_its_source_tree(self):
        # found live 2026-11-17: ask_opencode_go.py cannot import hermes_cli/dotenv under the system python (20 calls failed at once)
        cmd, env = S.ask_command({"PATH": "/usr/bin"})
        self.assertEqual(cmd, ["/home/santo/.hermes/venv/bin/python3", "/home/santo/.hermes/scripts/ask_opencode_go.py"])
        self.assertIn("hermes-agent", env["PYTHONPATH"])
        self.assertEqual(env["PATH"], "/usr/bin")

    def test_variant_that_left_the_data_keeps_its_note_unused(self):
        out, calls = self.run_it(weapons(("a", "Versatile", "text")), {"gone": {"text": "old", "model": "m", "at": NOW, "attempts": 1}})
        self.assertIn("gone", out["strategy"])


class Review(unittest.TestCase):
    def test_same_patch_ten_days_later_does_not_fire(self):
        st = {"last_patch": "2026-11-13", "last_review": "2026-11-07T00:00:00Z"}
        self.assertFalse(RV.decide({"patch": {"date": "2026-11-13"}}, st, NOW)[0])

    def test_new_patch_fires(self):
        fire, why = RV.decide({"patch": {"date": "2026-11-16", "name": "Nov 16 update"}}, {"last_patch": "2026-11-13", "last_review": "2026-11-15T00:00:00Z"}, NOW)
        self.assertTrue(fire)
        self.assertIn("2026-11-16", why)

    def test_31_days_fires_monthly(self):
        fire, why = RV.decide({"patch": {"date": "2026-11-13"}}, {"last_patch": "2026-11-13", "last_review": "2026-10-16T00:00:00Z"}, NOW)
        self.assertTrue(fire)
        self.assertIn("month", why)
        self.assertFalse(RV.decide({"patch": {"date": "2026-11-13"}}, {"last_patch": "2026-11-13", "last_review": "2026-10-25T00:00:00Z"}, NOW)[0])

    def test_no_state_yet_records_the_baseline_without_firing(self):
        self.assertFalse(RV.decide({"patch": {"date": "2026-11-13"}}, {}, NOW)[0])

    def run_main(self, status, state, code=0, argv=()):
        with tempfile.TemporaryDirectory() as d:
            sf = os.path.join(d, "status.json")
            json.dump(status, open(sf, "w"))
            sp = os.path.join(d, "review.json")
            if state is not None:
                json.dump(state, open(sp, "w"))
            calls = []
            card_dir = os.path.join(d, "cards")
            rc = RV.main(["--status-file", sf, "--state", sp, "--card-dir", card_dir, *argv], now=NOW,
                         run=lambda cmd: calls.append(cmd) or code)
            return rc, calls, (json.load(open(sp)) if os.path.exists(sp) else None), card_dir

    def test_new_patch_writes_a_card_dispatches_with_no_model_and_records_state(self):
        rc, calls, st, card_dir = self.run_main({"patch": {"date": "2026-11-16", "name": "Nov 16 update"}},
                                                {"last_patch": "2026-11-13", "last_review": "2026-11-15T00:00:00Z"})
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 1)
        cmd = calls[0]
        self.assertEqual(cmd[1], "mw4-review-20261117")
        self.assertEqual(cmd[2], "--card")
        self.assertNotIn("--model", cmd)
        self.assertEqual(cmd[-2:], ["--role", "worker-private"])
        self.assertEqual(st["last_patch"], "2026-11-16")
        self.assertEqual(st["last_review"], NOW)

    def test_dispatch_failure_leaves_state_unchanged(self):
        rc, calls, st, _ = self.run_main({"patch": {"date": "2026-11-16", "name": "x"}},
                                         {"last_patch": "2026-11-13", "last_review": "2026-11-15T00:00:00Z"}, code=3)
        self.assertNotEqual(rc, 0)
        self.assertEqual(st, {"last_patch": "2026-11-13", "last_review": "2026-11-15T00:00:00Z"})

    def test_dry_run_passes_the_flag_and_records_nothing(self):
        rc, calls, st, _ = self.run_main({"patch": {"date": "2026-11-16", "name": "x"}},
                                         {"last_patch": "2026-11-13", "last_review": "2026-11-15T00:00:00Z"}, argv=["--dry-run"])
        self.assertIn("--dry-run", calls[0])
        self.assertEqual(st["last_patch"], "2026-11-13")

    def test_first_run_seeds_the_baseline(self):
        rc, calls, st, _ = self.run_main({"patch": {"date": "2026-11-13", "name": "x"}}, None)
        self.assertEqual(calls, [])
        self.assertEqual(st["last_patch"], "2026-11-13")

    def test_card_names_the_inputs_and_keeps_miguels_checkpoint(self):
        text = RV.card_text("2026-11-17", "new balance patch 2026-11-16 (Nov 16 update)")
        self.assertIn("kind: report", text)
        self.assertIn("bestfor.json", text)
        self.assertIn("calc_gate", text)
        self.assertIn("Land: hold", text)
        self.assertFalse([m for m in ("claude-opus", "claude-sonnet", "claude-fable", "gpt-", "deepseek") if m in text])   # no model names hard-coded


if __name__ == "__main__":
    unittest.main()
