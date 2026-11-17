#!/usr/bin/env python3
"""Hourly stale alarm (Q7): read the site's heartbeat (status.json on the status branch) and, when it is unreadable, lists
failed sources, or the last check is more than 24 h old, post to #alerts through the existing tg_route.py.

  mw4_alarm.py [--status-file PATH] [--state PATH] [--force] [--dry-run]

De-dupe: post when the state turns bad, again at most every 12 h while it stays bad, and once when it is back to normal.
--force posts a "TEST:" message whatever the state and never touches the alarm state (the proof that an alert arrives).
No credential is read here: the route script holds the bot token."""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mw4_common as C  # noqa: E402

TG_ROUTE = "/home/santo/.hermes/scripts/tg_route.py"
REPEAT_HOURS = 12
STALE_HOURS = 24


def assess(status, now):
    """(bad, reason). Bad: unreadable record, failed sources, or the last check over 24 h ago."""
    if not status:
        return True, "the site's check record could not be read"
    stamp = status.get("checked_at") or status.get("checked")
    h = C.hours_between(stamp, now)
    if h is None:
        return True, "the site's check record has no readable time"
    if status.get("failed"):
        return True, "the last refresh could not read: " + ", ".join(status["failed"])
    if h > STALE_HOURS:
        return True, f"data is {round(h)} h old (over {STALE_HOURS} h)"
    return False, None


def decide(state, bad, reason, now, last_check_text):
    """(post, text, new_state) from the previous alarm state."""
    state = dict(state or {})
    if bad:
        since = C.hours_between(state.get("last_post"), now)
        post = (not state.get("bad")) or since is None or since >= REPEAT_HOURS
        text = f"MW4 Loadouts: {reason} (last check {last_check_text}). Site shows a red banner."
        return post, text, {**state, "bad": True, "reason": reason}
    if state.get("bad"):
        return True, "MW4 Loadouts: back to normal, data is fresh again.", {**state, "bad": False, "reason": None}
    return False, None, {**state, "bad": False}


def after_post(state, now):
    return {**state, "last_post": now}


def _run(cmd, text):
    return subprocess.run(cmd, check=False, timeout=60).returncode


def main(argv=None, now=None, fetch=None, run=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--status-file")
    ap.add_argument("--state", default=os.path.join(C.STATE_DIR, "alarm.json"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    now = now or C.utc_now()
    run = run or _run
    if a.status_file:
        status = C.read_json(a.status_file, None)
    else:
        status = (fetch or C.fetch_status)(C.STATUS_URL)
    bad, reason = assess(status, now)
    last = (status or {}).get("checked_at") or (status or {}).get("checked") or "unknown"
    if a.force:
        text = "TEST: " + f"MW4 Loadouts: {reason or 'forced alarm test, data is fine'} (last check {last}). Site shows a red banner."
        print(text)
        if a.dry_run:
            return 0
        return run(["python3", TG_ROUTE, "alerts", text], text)
    state = C.read_json(a.state, {})
    post, text, new_state = decide(state, bad, reason, now, last)
    print(text if post else f"no post (bad={bad}, reason={reason})")
    if not post:
        if new_state != state and not a.dry_run:
            C.write_json(a.state, new_state)
        return 0
    if a.dry_run:
        return 0
    code = run(["python3", TG_ROUTE, "alerts", text], text)
    if code == 0:
        C.write_json(a.state, after_post(new_state, now))
    return code


if __name__ == "__main__":
    sys.exit(main())
