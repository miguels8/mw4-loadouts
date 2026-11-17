"""Heartbeat push (job mw4-refresh-fix): the status branch must be updatable when it exists, created when it is missing,
and a probe that cannot reach the remote must fail loudly (never fall through to "create"). Real git against local bare
repos, no network. Root cause on record: proof/refresh-fix/ROOT-CAUSE-heartbeat.txt."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import heartbeat as H  # noqa: E402

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True).stdout.strip()


def write_status(d, obj):
    with open(os.path.join(d, "status.json"), "w", encoding="utf-8") as f:
        json.dump(obj, f)


class Remote:
    """A bare repo standing in for GitHub; optionally with a `status` branch already holding history."""

    def __init__(self, tmp, with_status=False):
        self.path = os.path.join(tmp, "remote.git")
        git("init", "-q", "--bare", self.path)
        self.url = "file://" + self.path
        if with_status:
            seed = os.path.join(tmp, "seed")
            git("init", "-q", seed)
            git("switch", "-q", "--orphan", "status", cwd=seed)
            write_status(seed, {"checked_at": "2026-11-17T08:55:33Z"})
            git("add", "status.json", cwd=seed)
            git("commit", "-q", "-m", "status: seed", cwd=seed)
            git("push", "-q", self.url, "status", cwd=seed)

    def log(self):
        return git("--git-dir", self.path, "log", "--format=%s", "status").splitlines()

    def content(self):
        return json.loads(git("--git-dir", self.path, "show", "status:status.json"))

    def commit_count(self):
        return int(git("--git-dir", self.path, "rev-list", "--count", "status"))

    def has_status(self):
        return subprocess.run(["git", "--git-dir", self.path, "rev-parse", "--verify", "-q", "refs/heads/status"],
                              capture_output=True).returncode == 0


class Base(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.tmp = self._t.name
        self.src = os.path.join(self.tmp, "src-status.json")
        with open(self.src, "w", encoding="utf-8") as f:
            json.dump({"checked_at": "2026-11-17T16:36:14Z", "failed": []}, f)
        self._real = H.run_git

    def tearDown(self):
        H.run_git = self._real
        self._t.cleanup()


class PushHeartbeat(Base):
    def test_updates_an_existing_status_branch_and_keeps_its_history(self):
        r = Remote(self.tmp, with_status=True)
        out = H.push_heartbeat(r.url, "status", self.src, now="2026-11-17T16:41:38Z")
        self.assertEqual(out, "updated")
        self.assertEqual(r.content()["checked_at"], "2026-11-17T16:36:14Z")
        self.assertEqual(r.commit_count(), 2)
        self.assertEqual(r.log()[0], "status: 2026-11-17T16:41:38Z")

    def test_creates_the_status_branch_when_it_is_missing(self):
        r = Remote(self.tmp, with_status=False)
        self.assertFalse(r.has_status())
        out = H.push_heartbeat(r.url, "status", self.src, now="2026-11-17T16:41:38Z")
        self.assertEqual(out, "created")
        self.assertTrue(r.has_status())
        self.assertEqual(r.commit_count(), 1)
        self.assertEqual(r.content()["checked_at"], "2026-11-17T16:36:14Z")

    def test_unchanged_record_makes_no_commit(self):
        r = Remote(self.tmp, with_status=True)
        with open(self.src, "w", encoding="utf-8") as f:
            json.dump({"checked_at": "2026-11-17T08:55:33Z"}, f)
        self.assertEqual(H.push_heartbeat(r.url, "status", self.src), "unchanged")
        self.assertEqual(r.commit_count(), 1)

    def test_second_run_after_create_updates(self):
        r = Remote(self.tmp, with_status=False)
        H.push_heartbeat(r.url, "status", self.src, now="a")
        with open(self.src, "w", encoding="utf-8") as f:
            json.dump({"checked_at": "2026-11-17T19:20:00Z"}, f)
        self.assertEqual(H.push_heartbeat(r.url, "status", self.src, now="b"), "updated")
        self.assertEqual(r.commit_count(), 2)

    def test_an_unreachable_remote_fails_loudly_and_never_takes_the_create_path(self):
        missing = "file://" + os.path.join(self.tmp, "no-such-remote.git")
        with self.assertRaises(H.HeartbeatError) as cm:
            H.push_heartbeat(missing, "status", self.src)
        self.assertIn("could not reach", str(cm.exception).lower())
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "no-such-remote.git")))

    def test_a_missing_source_file_fails_loudly(self):
        r = Remote(self.tmp, with_status=True)
        with self.assertRaises(H.HeartbeatError):
            H.push_heartbeat(r.url, "status", os.path.join(self.tmp, "nope.json"))
        self.assertEqual(r.commit_count(), 1)

    def test_a_push_race_is_retried_on_top_of_the_new_commit(self):
        r = Remote(self.tmp, with_status=True)
        real = H.run_git
        state = {"raced": False}

        def racing(args, cwd, env=None):
            if args and args[0] == "push" and not state["raced"]:
                state["raced"] = True     # someone else pushes to status between our fetch and our push
                other = os.path.join(self.tmp, "other")
                git("clone", "-q", "--branch", "status", r.url, other)
                write_status(other, {"checked_at": "2026-11-17T16:40:00Z", "other": True})
                git("add", "status.json", cwd=other)
                git("commit", "-q", "-m", "status: other writer", cwd=other)
                git("push", "-q", "origin", "status", cwd=other)
            return real(args, cwd, env)

        H.run_git = racing
        out = H.push_heartbeat(r.url, "status", self.src, now="2026-11-17T16:41:38Z")
        self.assertEqual(out, "updated")
        self.assertTrue(state["raced"])
        self.assertEqual(r.commit_count(), 3)           # seed, other writer, ours on top (fast-forward, nothing lost)
        self.assertEqual(r.content()["checked_at"], "2026-11-17T16:36:14Z")

    def test_a_push_that_keeps_losing_the_race_gives_up_loudly(self):
        r = Remote(self.tmp, with_status=True)
        real = H.run_git

        def always_rejected(args, cwd, env=None):
            if args and args[0] == "push":
                raise H.GitFailed(args, 1, " ! [rejected] status -> status (fetch first)")
            return real(args, cwd, env)

        H.run_git = always_rejected
        with self.assertRaises(H.HeartbeatError):
            H.push_heartbeat(r.url, "status", self.src, retries=3)
        self.assertEqual(r.commit_count(), 1)


class Isolation(Base):
    """Root cause: the probe ran inside the checked-out repo, which already carries checkout's auth header, so the
    extra header made GitHub answer 400 Duplicate header. Every git call must run in a fresh empty directory, and the
    token must travel in the environment, not in argv."""

    def test_every_git_call_runs_outside_the_callers_repo_and_the_token_is_not_in_argv(self):
        r = Remote(self.tmp, with_status=True)
        real = H.run_git
        calls = []

        def spy(args, cwd, env=None):
            calls.append((list(args), cwd, dict(env or {})))
            return real(args, cwd, env)

        H.run_git = spy
        H.push_heartbeat(r.url, "status", self.src, extraheader="AUTHORIZATION: basic SECRET")
        self.assertTrue(calls)
        for args, cwd, env in calls:
            self.assertNotEqual(os.path.realpath(cwd), os.path.realpath(os.getcwd()))
            self.assertNotIn("SECRET", " ".join(args))
        net = [c for c in calls if c[0][0] in ("ls-remote", "fetch", "push")]
        self.assertTrue(net)
        for args, cwd, env in net:
            self.assertEqual(env.get("GIT_CONFIG_COUNT"), "1")
            self.assertEqual(env.get("GIT_CONFIG_KEY_0"), "http.extraheader")
            self.assertEqual(env.get("GIT_CONFIG_VALUE_0"), "AUTHORIZATION: basic SECRET")

    def test_the_probe_reads_exit_2_as_missing_and_anything_else_as_an_error(self):
        r = Remote(self.tmp, with_status=False)
        self.assertEqual(H.probe(r.url, "status", os.path.join(self.tmp, "p1")), "missing")
        with self.assertRaises(H.HeartbeatError):
            H.probe("file://" + os.path.join(self.tmp, "nope.git"), "status", os.path.join(self.tmp, "p2"))


class Cli(Base):
    def run_cli(self, remote, env=None):
        return subprocess.run([sys.executable, "-I", os.path.join(ROOT, "scripts", "heartbeat.py"), "--remote", remote,
                               "--file", self.src], env=env or GIT_ENV, capture_output=True, text=True)

    def test_cli_runs_and_prints_the_outcome(self):
        r = Remote(self.tmp, with_status=True)
        p = self.run_cli(r.url)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("heartbeat updated", p.stdout)

    def test_cli_exits_nonzero_on_an_unreachable_remote(self):
        p = self.run_cli("file://" + os.path.join(self.tmp, "nope.git"))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("could not reach", (p.stderr + p.stdout).lower())

    def test_the_token_comes_from_the_environment_variable_and_is_never_printed(self):
        r = Remote(self.tmp, with_status=True)
        p = self.run_cli(r.url, {**GIT_ENV, "MW4_GIT_EXTRAHEADER": "AUTHORIZATION: basic X"})
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn("basic X", p.stdout + p.stderr)


class Workflow(unittest.TestCase):
    """The workflow must call the tested script and must not hide a failed probe again."""

    def setUp(self):
        with open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8") as f:
            self.text = f.read()
        m = re.search(r"- name: Heartbeat to the status branch.*?(?=\n      - (?:uses|id|name):)", self.text, re.S)
        self.assertIsNotNone(m, "heartbeat step not found")
        self.step = m.group(0)

    def test_heartbeat_step_calls_the_script_and_keeps_its_guards(self):
        self.assertIn("python3 -I scripts/heartbeat.py", self.step)
        self.assertIn("if: always() && github.event_name != 'push'", self.step)
        self.assertIn("MW4_GIT_EXTRAHEADER", self.step)

    def test_heartbeat_step_has_no_stderr_hiding_probe(self):
        self.assertNotIn("ls-remote", self.step)
        self.assertNotIn("/dev/null", self.step)
        self.assertNotIn("git init", self.step)

    def test_the_github_schedule_stays(self):
        self.assertIn('cron: "17 */3 * * *"', self.text)
        self.assertIn("workflow_dispatch", self.text)


if __name__ == "__main__":
    unittest.main()
