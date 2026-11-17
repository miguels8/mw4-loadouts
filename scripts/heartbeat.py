#!/usr/bin/env python3
"""Push the heartbeat (status.json) to the `status` branch. Stdlib only, no AI.

  heartbeat.py --remote URL --file site/data/status.json [--branch status]
  environment: MW4_GIT_EXTRAHEADER  optional "AUTHORIZATION: basic ..." header for the remote (never printed, never in argv)

Why a script: the old workflow step probed the branch with `git ls-remote ... 2>/dev/null` inside the checked-out repo.
actions/checkout already stores an auth header there, the step added a second one, GitHub answered 400 "Duplicate
header: Authorization" (exit 128), and the `if` read that as "branch missing": it created an orphan branch and its push
was rejected. So every git call here runs in a fresh empty directory, the probe tells exit 0 (exists) from 2 (missing)
from anything else (error, loud), and a push that loses a race is retried on top of the new commit.
Evidence: proof/refresh-fix/ROOT-CAUSE-heartbeat.txt."""
import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile


class HeartbeatError(Exception):
    pass


class GitFailed(Exception):
    def __init__(self, args, code, output):
        super().__init__(f"git {' '.join(args)} failed ({code}): {output}")
        self.git_args, self.code, self.output = list(args), code, output


def run_git(args, cwd, env=None):
    """Run git and return stdout; raise GitFailed on a non-zero exit."""
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise GitFailed(args, p.returncode, (p.stderr or p.stdout).strip())
    return p.stdout


def _env(extraheader):
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GIT_AUTHOR_NAME", "mw4-loadouts-bot")
    env.setdefault("GIT_AUTHOR_EMAIL", "mw4-loadouts-bot@users.noreply.github.com")
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    if extraheader:   # the environment keeps the token out of argv and out of the process list
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraheader", "GIT_CONFIG_VALUE_0": extraheader})
    return env


def probe(remote, branch, workdir, extraheader=None):
    """'exists' or 'missing'. Exit 2 of ls-remote means no such branch; any other failure raises HeartbeatError."""
    os.makedirs(workdir, exist_ok=True)
    env = _env(extraheader)
    run_git(["init", "-q"], workdir, env)
    try:
        run_git(["ls-remote", "--exit-code", "--heads", remote, branch], workdir, env)
        return "exists"
    except GitFailed as e:
        if e.code == 2:
            return "missing"
        raise HeartbeatError(f"could not reach {remote} to look for branch {branch}: {e.output or e.code}") from e


def push_heartbeat(remote, branch, src, extraheader=None, now=None, retries=3):
    """Put src (status.json) on `branch` of `remote`. Returns 'created', 'updated' or 'unchanged'."""
    if not os.path.isfile(src):
        raise HeartbeatError(f"heartbeat source file not found: {src}")
    stamp = now or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    env = _env(extraheader)
    base = tempfile.mkdtemp(prefix="mw4-heartbeat-")
    try:
        state = probe(remote, branch, os.path.join(base, "w"), extraheader)
        outcome = "updated" if state == "exists" else "created"
        for attempt in range(1, retries + 1):
            work = os.path.join(base, f"try{attempt}")
            os.makedirs(work)
            run_git(["init", "-q"], work, env)
            if state == "exists":
                try:
                    run_git(["fetch", "-q", "--depth", "1", remote, f"{branch}:refs/remotes/origin/{branch}"], work, env)
                except GitFailed as e:
                    raise HeartbeatError(f"could not fetch {branch} from {remote}: {e.output}") from e
                run_git(["switch", "-q", "-C", branch, f"refs/remotes/origin/{branch}"], work, env)
            else:
                run_git(["switch", "-q", "--orphan", branch], work, env)
            shutil.copyfile(src, os.path.join(work, "status.json"))
            run_git(["add", "status.json"], work, env)
            try:
                run_git(["diff", "--cached", "--quiet"], work, env)
                if state == "exists":
                    return "unchanged"
            except GitFailed:
                pass   # exit 1: the record changed (or the branch is new), which is the normal case
            run_git(["commit", "-q", "-m", f"status: {stamp}"], work, env)
            try:
                run_git(["push", "-q", remote, f"{branch}:refs/heads/{branch}"], work, env)
                return outcome
            except GitFailed as e:
                if attempt == retries:
                    raise HeartbeatError(f"push to {branch} was rejected {retries} times: {e.output}") from e
                if state == "missing":
                    state = probe(remote, branch, os.path.join(base, f"p{attempt}"), extraheader)   # someone created it meanwhile
                    outcome = "updated" if state == "exists" else "created"
        raise HeartbeatError("heartbeat push did not finish")
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--branch", default="status")
    a = ap.parse_args(argv)
    try:
        out = push_heartbeat(a.remote, a.branch, a.file, extraheader=os.environ.get("MW4_GIT_EXTRAHEADER"))
    except HeartbeatError as e:
        print(f"::error::heartbeat failed: {e}", file=sys.stderr)
        return 1
    print(f"heartbeat {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
