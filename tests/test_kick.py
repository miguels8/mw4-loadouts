"""Fallback trigger (job mw4-refresh-fix): when GitHub's scheduler skips the 3-hour run, the MiguelPC timer starts the
workflow. Pure decision function plus a main() with injected clock, status fetch and gh runner: nothing here touches
the network or GitHub."""
import datetime as dt
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "pc"))
import mw4_kick as K  # noqa: E402

NOW = "2026-11-17T20:00:00Z"
T0 = dt.datetime.fromisoformat(NOW.replace("Z", "+00:00"))


def ago(hours=0.0, minutes=0.0):
    return (T0 - dt.timedelta(hours=hours, minutes=minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def st(hours):
    return {"checked_at": ago(hours=hours), "failed": []}


def run(minutes, status="completed", event="schedule", conclusion="success"):
    return {"databaseId": 1, "event": event, "status": status, "conclusion": conclusion, "createdAt": ago(minutes=minutes)}


class Decide(unittest.TestCase):
    def d(self, status, runs=(), state=None):
        return K.decide(status, list(runs), state or {}, NOW)

    def test_threshold_is_three_and_a_half_hours(self):
        self.assertEqual(K.KICK_AFTER_HOURS, 3.5)
        self.assertEqual(self.d(st(2))[0], "skip")
        self.assertEqual(self.d(st(3.4))[0], "skip")
        self.assertEqual(self.d(st(3.6))[0], "kick")

    def test_unreadable_or_timeless_record_is_stale(self):
        self.assertEqual(self.d(None)[0], "kick")
        self.assertEqual(self.d({"failed": []})[0], "kick")

    def test_failed_sources_alone_do_not_trigger_a_kick_only_age_does(self):
        self.assertEqual(self.d({"checked_at": ago(hours=1), "failed": ["mar-9"]})[0], "skip")

    def test_a_refresh_run_in_flight_blocks_the_kick(self):
        for s in ("queued", "in_progress", "waiting", "pending", "requested"):
            self.assertEqual(self.d(st(9), [run(90, status=s)])[0], "skip", s)

    def test_a_run_that_has_been_stuck_over_two_hours_does_not_block(self):
        self.assertEqual(self.d(st(9), [run(150, status="queued")])[0], "kick")

    def test_a_run_started_in_the_last_30_minutes_blocks_even_when_finished(self):
        self.assertEqual(self.d(st(9), [run(20)])[0], "skip")
        self.assertEqual(self.d(st(9), [run(40)])[0], "kick")

    def test_push_runs_do_not_count_they_never_refresh_data(self):
        self.assertEqual(self.d(st(9), [run(5, status="in_progress", event="push")])[0], "kick")

    def test_manual_runs_count(self):
        self.assertEqual(self.d(st(9), [run(5, status="in_progress", event="workflow_dispatch")])[0], "skip")

    def test_one_kick_per_hour(self):
        self.assertEqual(self.d(st(9), state={"last_kick": ago(minutes=30)})[0], "skip")
        self.assertEqual(self.d(st(9), state={"last_kick": ago(minutes=70)})[0], "kick")

    def test_no_run_information_still_kicks_when_stale_and_rate_limited(self):
        self.assertEqual(K.decide(st(9), None, {}, NOW)[0], "kick")
        self.assertEqual(K.decide(st(9), None, {"last_kick": ago(minutes=10)}, NOW)[0], "skip")

    def test_the_reason_is_readable(self):
        self.assertIn("9 h", self.d(st(9))[1])
        self.assertIn("fresh", self.d(st(1))[1])


class Main(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.state = os.path.join(self._t.name, "kick.json")
        self.calls = []

    def tearDown(self):
        self._t.cleanup()

    def go(self, status, runs, gh_code=0, extra=(), now=NOW):
        def gh(cmd):
            self.calls.append(cmd)
            if cmd[1:3] == ["run", "list"]:
                return (0, runs) if runs is not None else (1, None)
            return gh_code, None
        return K.main(["--state", self.state, *extra], now=now, fetch=lambda url: status, gh=gh)

    def test_stale_kicks_with_the_exact_gh_command_and_records_state(self):
        code = self.go(st(9), [])
        self.assertEqual(code, 0)
        kick = [c for c in self.calls if c[1:3] == ["workflow", "run"]]
        self.assertEqual(len(kick), 1)
        self.assertEqual(kick[0][1:], ["workflow", "run", "refresh-and-deploy", "--repo", "miguels8/mw4-loadouts", "--ref", "main"])
        self.assertTrue(os.path.basename(kick[0][0]).startswith("gh"))
        import json
        self.assertEqual(json.load(open(self.state))["last_kick"], NOW)

    def test_a_second_pass_right_after_does_not_kick_again(self):
        self.go(st(9), [])
        self.calls.clear()
        self.assertEqual(self.go(st(9), [], now="2026-11-17T20:30:00Z"), 0)
        self.assertEqual([c for c in self.calls if c[1:3] == ["workflow", "run"]], [])

    def test_fresh_status_never_calls_gh_at_all(self):
        self.assertEqual(self.go(st(1), []), 0)
        self.assertEqual(self.calls, [])

    def test_a_failed_gh_kick_exits_nonzero_and_records_nothing(self):
        code = self.go(st(9), [], gh_code=1)
        self.assertNotEqual(code, 0)
        self.assertFalse(os.path.exists(self.state))

    def test_run_list_failure_still_kicks(self):
        self.assertEqual(self.go(st(9), None), 0)
        self.assertEqual(len([c for c in self.calls if c[1:3] == ["workflow", "run"]]), 1)

    def test_dry_run_decides_but_never_kicks_or_records(self):
        self.assertEqual(self.go(st(9), [], extra=["--dry-run"]), 0)
        self.assertEqual([c for c in self.calls if c[1:3] == ["workflow", "run"]], [])
        self.assertFalse(os.path.exists(self.state))

    def test_gh_run_list_is_asked_for_the_workflow_by_name(self):
        self.go(st(9), [])
        lst = [c for c in self.calls if c[1:3] == ["run", "list"]][0]
        self.assertIn("refresh-and-deploy", lst)
        self.assertIn("--json", lst)


class Units(unittest.TestCase):
    def read(self, *p):
        with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
            return f.read()

    def test_timer_runs_every_half_hour_and_catches_up(self):
        t = self.read("pc", "systemd", "mw4-kick.timer")
        self.assertRegex(t, r"OnCalendar=\*:0/30|OnCalendar=\*:\d\d,\d\d")
        self.assertIn("Persistent=true", t)
        self.assertIn("WantedBy=timers.target", t)

    def test_service_runs_the_script_from_the_clone_with_isolated_python(self):
        s = self.read("pc", "systemd", "mw4-kick.service")
        self.assertIn("ExecStart=/usr/bin/python3 -I %h/.local/share/mw4-loadouts/repo/pc/mw4_kick.py", s)
        self.assertIn("Type=oneshot", s)

    def test_install_enables_the_kick_timer_and_backs_up_its_units(self):
        i = self.read("pc", "install.sh")
        self.assertIn("mw4-kick", i)
        self.assertRegex(i, r"enable --now [^\n]*mw4-kick\.timer")
        self.assertRegex(i, r"for u in [^\n]*mw4-kick")

    def test_undo_removes_the_kick_timer_and_reverts_the_merge(self):
        u = self.read("UNDO-refresh-fix.sh")
        self.assertIn("mw4-kick", u)
        self.assertIn("git revert", u)
        self.assertIn("disable --now", u)


class Threshold(unittest.TestCase):
    def test_stale_alarm_threshold_matches_a_three_hour_cadence(self):
        import mw4_alarm as A
        self.assertEqual(A.STALE_HOURS, 7)
        self.assertEqual(A.assess({"checked_at": ago(hours=6.5), "failed": []}, NOW), (False, None))
        bad, why = A.assess({"checked_at": ago(hours=8), "failed": []}, NOW)
        self.assertTrue(bad)
        self.assertIn("over 7 h", why)

    def test_the_site_threshold_is_the_same_number(self):
        with open(os.path.join(ROOT, "site", "engine.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertRegex(js, r"hours > 7\b")
        self.assertNotRegex(js, r"hours > 24\b")
        self.assertIn("over 7 h", js)


if __name__ == "__main__":
    unittest.main()
