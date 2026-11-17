#!/usr/bin/env python3
"""Fallback trigger for the 3-hour refresh (job mw4-refresh-fix). GitHub's scheduler can skip runs (it skipped every slot
on 2026-11-17), so every 30 minutes this reads the site's heartbeat and, when the last check is older than 3.5 h, starts the
`refresh-and-deploy` workflow with `gh workflow run`. The GitHub schedule stays; this only covers a skipped slot.

  mw4_kick.py [--state PATH] [--dry-run]

It does not kick when a refresh (scheduled or manual) is already queued or running, when one started in the last 30 min,
or when it kicked in the last 60 min. Push-triggered runs never count: they do not refresh data.
Credentials: none of its own. `gh` uses the login already on this machine (scope `workflow`)."""
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mw4_common as C  # noqa: E402

REPO_SLUG = "miguels8/mw4-loadouts"
WORKFLOW = "refresh-and-deploy"
KICK_AFTER_HOURS = 3.5
RECENT_RUN_MINUTES = 30
STUCK_RUN_HOURS = 2
KICK_EVERY_MINUTES = 60
IN_FLIGHT = {"queued", "in_progress", "waiting", "pending", "requested"}
REFRESH_EVENTS = {"schedule", "workflow_dispatch"}


def _gh_path():
    here = os.path.expanduser("~/.local/bin/gh")
    return here if os.access(here, os.X_OK) else (shutil.which("gh") or "gh")


def _minutes_since(ts, now):
    h = C.hours_between(ts, now)
    return None if h is None else h * 60


def decide(status, runs, state, now):
    """('kick' | 'skip', reason). runs: list of workflow runs, or None when they could not be listed."""
    stamp = (status or {}).get("checked_at") or (status or {}).get("checked")
    hours = C.hours_between(stamp, now)
    if hours is not None and hours <= KICK_AFTER_HOURS:
        return "skip", f"data is fresh ({hours:.1f} h old)"
    why = "the check record is unreadable" if status is None else (
        "the check record has no readable time" if hours is None else f"last check is {round(hours)} h old")
    since_kick = _minutes_since((state or {}).get("last_kick"), now)
    if since_kick is not None and since_kick < KICK_EVERY_MINUTES:
        return "skip", f"{why}, but a kick went out {round(since_kick)} min ago"
    for r in runs or []:
        if r.get("event") not in REFRESH_EVENTS:
            continue
        age = _minutes_since(r.get("createdAt"), now)
        if age is None:
            continue
        if r.get("status") in IN_FLIGHT and age < STUCK_RUN_HOURS * 60:
            return "skip", f"{why}, but a refresh run is already {r.get('status')} (started {round(age)} min ago)"
        if age < RECENT_RUN_MINUTES:
            return "skip", f"{why}, but a refresh run started {round(age)} min ago"
    return "kick", why


def _run_gh(cmd):
    """(exit code, parsed json or None). Used for both `run list --json` and `workflow run`."""
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        print((p.stderr or p.stdout).strip(), file=sys.stderr)
        return p.returncode, None
    try:
        return 0, json.loads(p.stdout) if p.stdout.strip().startswith(("[", "{")) else None
    except ValueError:
        return 0, None


def main(argv=None, now=None, fetch=None, gh=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join(C.STATE_DIR, "kick.json"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    now = now or C.utc_now()
    gh = gh or _run_gh
    status = (fetch or C.fetch_status)(C.STATUS_URL)
    state = C.read_json(a.state, {})
    stamp = (status or {}).get("checked_at") or (status or {}).get("checked")
    hours = C.hours_between(stamp, now)
    if hours is not None and hours <= KICK_AFTER_HOURS:
        print(f"no kick: data is fresh ({hours:.1f} h old)")
        return 0
    ghbin = _gh_path()
    code, runs = gh([ghbin, "run", "list", "--repo", REPO_SLUG, "--workflow", WORKFLOW, "--limit", "10",
                     "--json", "databaseId,event,status,conclusion,createdAt"])
    if code != 0 or not isinstance(runs, list):
        runs = None
    action, why = decide(status, runs, state, now)
    print(f"{action}: {why}")
    if action != "kick" or a.dry_run:
        return 0
    code, _ = gh([ghbin, "workflow", "run", WORKFLOW, "--repo", REPO_SLUG, "--ref", "main"])
    if code != 0:
        print("kick failed: gh could not start the workflow (see the error above)", file=sys.stderr)
        return 1
    C.write_json(a.state, {**state, "last_kick": now, "kicks": int(state.get("kicks", 0)) + 1, "last_reason": why})
    print(f"kicked {WORKFLOW} at {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
