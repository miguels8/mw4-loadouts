#!/usr/bin/env python3
"""Strategy notes (Q8): for each variant that has the source site's own text and no note yet, ask the cheap OpenCode Go
pool for a 3-sentence summary of THAT text (never Claude, never invented), write site/data/strategy.json and push it to
main (a data-only commit; the push deploys the site). Runs every 3 h from a user timer; does nothing when no variant is new.

  mw4_strategy.py [--repo DIR] [--dry-run] [--no-push]

Every call goes through /home/santo/.hermes/scripts/ask_opencode_go.py, which records it in the Go usage ledger
(~/.hermes/state/usage-gate/go-usage.jsonl); this script also appends {at, variant_id, status} to
~/.local/state/mw4-loadouts/strategy-calls.jsonl so the ledger lines can be matched to variants.
Max 20 calls per run. A failed or malformed reply counts an attempt; after 2 attempts the fixed template stays."""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mw4_common as C  # noqa: E402

ASK = "/home/santo/.hermes/scripts/ask_opencode_go.py"
MAX_CALLS = 20
MAX_ATTEMPTS = 2


def pending(weapons, strat):
    """[(gun, variant)] with source text and no usable note yet, still within the attempt cap."""
    out = []
    for g in weapons.get("guns", []):
        for v in g.get("variants") or []:
            if not v.get("source_text"):
                continue
            e = strat.get(v["id"])
            if e is None or (not e.get("text") and e.get("attempts", 0) < MAX_ATTEMPTS):
                out.append((g, v))
    return out


def prompt_for(gun, v):
    return (f"Summarize, in 3 short plain sentences for a casual player, how to use this {gun['name']} {v['type']} build, "
            f"using ONLY this text:\n\n{v['source_text']}")


def valid(reply):
    """3 short plain sentences (2 to 5 accepted), not empty, not a wall of text."""
    t = (reply or "").strip()
    if not 30 <= len(t) <= 600:
        return False
    return 2 <= len(re.split(r"(?<=[.!?])\s+", t)) <= 5


def run(weapons, strat, runner, now, model, max_calls=MAX_CALLS, log=None):
    """Pure core. runner(prompt) -> (exit code, reply). Returns {"strategy", "changed", "calls"}."""
    new = {k: dict(v) for k, v in strat.items()}
    calls = 0
    for gun, v in pending(weapons, strat):
        if calls >= max_calls:
            break
        calls += 1
        code, reply = runner(prompt_for(gun, v))
        ok = code == 0 and valid(reply)
        prev = new.get(v["id"], {}).get("attempts", 0)
        new[v["id"]] = {"text": reply.strip() if ok else None, "model": model if ok else None, "at": now, "attempts": prev + 1}
        if log:
            log({"at": now, "variant_id": v["id"], "status": "ok" if ok else f"failed (exit {code})"})
    return {"strategy": new, "changed": new != strat, "calls": calls}


def _runner(prompt):
    p = subprocess.run(["python3", ASK], input=prompt, capture_output=True, text=True, timeout=240, check=False)
    return p.returncode, p.stdout.strip()


def _git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, check=False)


def main(argv=None, now=None, runner=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=C.REPO)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)
    now = now or C.utc_now()
    if not a.dry_run and runner is None:
        pull = _git(a.repo, "pull", "--ff-only", "--quiet")
        if pull.returncode != 0:
            print("git pull failed: " + pull.stderr.strip(), file=sys.stderr)
            return 1
    weapons = C.read_json(os.path.join(a.repo, "site", "data", "weapons.json"), {"guns": []})
    path = os.path.join(a.repo, "site", "data", "strategy.json")
    strat = C.read_json(path, {})
    todo = pending(weapons, strat)
    if not todo:
        print("nothing new")
        return 0
    if a.dry_run:
        print(f"dry run: {len(todo)} variant(s) would be summarized: " + ", ".join(v["id"] for _, v in todo[:20]))
        return 0
    calls_log = os.path.join(C.STATE_DIR, "strategy-calls.jsonl")
    os.makedirs(C.STATE_DIR, exist_ok=True)

    def log(row):
        with open(calls_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    model = os.environ.get("OPENCODE_GO_MODEL") or "opencode-go pool (ask_opencode_go.py default)"
    res = run(weapons, strat, runner or _runner, now, model, log=log)
    print(f"{res['calls']} call(s), changed={res['changed']}")
    if not res["changed"]:
        return 0
    C.write_json(path, res["strategy"])
    if a.no_push or runner is not None:
        return 0
    _git(a.repo, "add", "site/data/strategy.json")
    c = _git(a.repo, "commit", "-m", "data: strategy notes")
    if c.returncode != 0:
        print("commit: " + (c.stderr or c.stdout).strip(), file=sys.stderr)
        return 1
    p = _git(a.repo, "push", "origin", "HEAD:main")
    if p.returncode != 0:
        _git(a.repo, "pull", "--rebase", "--quiet")
        p = _git(a.repo, "push", "origin", "HEAD:main")
    if p.returncode != 0:
        print("push failed: " + p.stderr.strip(), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
