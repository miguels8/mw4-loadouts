#!/usr/bin/env python3
"""Opus review trigger (Q9): after every balance patch the refresh script spots, and once a month, file a review card and
start it with job-dispatch. Automatic reviews explicitly use the registry worker-private Go role. Opus writes a findings report, Sonnet applies fixes in a PR, Eva verifies before it goes live.

  mw4_review.py [--status-file PATH] [--state PATH] [--card-dir DIR] [--dry-run]

State (~/.local/state/mw4-loadouts/review.json): last_patch, last_review. The first run only records the baseline
(the build job that installed this timer is the first review). State is recorded only after job-dispatch exits 0."""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mw4_common as C  # noqa: E402

JOB_DISPATCH = "/home/santo/.hermes/bin/job-dispatch"
CARD_DIR = "/home/santo/.hermes/cache/scratch/claude-jobs"
MONTH_HOURS = 30 * 24
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review-card.md")


def decide(status, state, now):
    """(fire, why). Fire on a new balance patch date, or when the last review is a month old."""
    patch = (status or {}).get("patch") or {}
    pd = patch.get("date")
    if not state.get("last_patch") and not state.get("last_review"):
        return False, "baseline"
    if pd and pd != state.get("last_patch"):
        return True, f"new balance patch {pd}" + (f" ({patch['name']})" if patch.get("name") else "")
    h = C.hours_between(state.get("last_review"), now)
    if h is None or h >= MONTH_HOURS:
        return True, "a month since the last review"
    return False, "nothing new"


def card_text(date, reason):
    with open(TEMPLATE, encoding="utf-8") as f:
        return f.read().replace("{date}", date.replace("-", "")).replace("{reason}", reason)


def go_role_args(registry):
    """Resolve the automatic worker role to the Go namespace T3 actually accepts."""
    spec = (C.read_json(registry, {}).get("role_models") or {}).get("worker-private") or {}
    if spec.get("provider") != "opencode-go" or not isinstance(spec.get("model"), str) or not spec["model"].strip():
        raise ValueError("worker-private must resolve to the direct Go provider; no job launched")
    return ["--model", "opencode/opencode-go/" + spec["model"].removeprefix("opencode-go/")]


def _run(cmd):
    return subprocess.run(cmd, check=False, timeout=300).returncode


def main(argv=None, now=None, fetch=None, run=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--status-file")
    ap.add_argument("--state", default=os.path.join(C.STATE_DIR, "review.json"))
    ap.add_argument("--card-dir", default=CARD_DIR)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--routing", default="/home/santo/.hermes/model-routing.json")
    a = ap.parse_args(argv)
    now = now or C.utc_now()
    run = run or _run
    status = C.read_json(a.status_file, None) if a.status_file else (fetch or C.fetch_status)(C.STATUS_URL)
    if not status:
        print("status record unreadable: nothing to do (the stale alarm reports this)")
        return 0
    state = C.read_json(a.state, {})
    fire, why = decide(status, state, now)
    pd = (status.get("patch") or {}).get("date")
    if why == "baseline":
        if not a.dry_run:
            C.write_json(a.state, {"last_patch": pd, "last_review": now})
        print(f"baseline recorded (patch {pd})")
        return 0
    if not fire:
        print(why)
        return 0
    date = now[:10].replace("-", "")
    slug = f"mw4-review-{date}"
    os.makedirs(a.card_dir, exist_ok=True)
    card = os.path.join(a.card_dir, f"CARD-{slug}.md")
    with open(card, "w", encoding="utf-8") as f:
        f.write(card_text(now[:10], why))
    cmd = [JOB_DISPATCH, slug, "--card", card, *go_role_args(a.routing)] + (["--dry-run"] if a.dry_run else [])
    code = run(cmd)
    print(f"{' '.join(cmd)} -> exit {code} ({why})")
    if code == 0 and not a.dry_run:
        C.write_json(a.state, {"last_patch": pd or state.get("last_patch"), "last_review": now})
    return code


if __name__ == "__main__":
    sys.exit(main())
