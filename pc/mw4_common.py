"""Shared helpers for the MiguelPC user-timer scripts (stdlib only, no secrets).

The scripts run from a dedicated clone (~/.local/share/mw4-loadouts/repo) under systemd user timers; state lives in
~/.local/state/mw4-loadouts/. Nothing here reads a credential: Telegram goes through the existing tg_route.py, the
cheap model through the existing ask_opencode_go.py, the review through the existing job-dispatch."""
import datetime as dt
import json
import os
import urllib.request

STATUS_URL = "https://raw.githubusercontent.com/miguels8/mw4-loadouts/status/status.json"
STATE_DIR = os.path.expanduser("~/.local/state/mw4-loadouts")
REPO = os.path.expanduser("~/.local/share/mw4-loadouts/repo")


def parse_ts(s):
    """ISO timestamp (Z or offset) or a bare date (00:00Z) -> aware datetime, else None."""
    if not s:
        return None
    try:
        if len(s) == 10:
            s += "T00:00:00Z"
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def hours_between(then, now):
    a, b = parse_ts(then), parse_ts(now)
    return None if a is None or b is None else (b - a).total_seconds() / 3600


def fetch_status(url=STATUS_URL, timeout=20):
    """The heartbeat on the status branch, or None when it cannot be read."""
    try:
        req = urllib.request.Request(f"{url}?t={int(dt.datetime.now().timestamp())}", headers={"User-Agent": "mw4-loadouts-timer"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - any failure means "cannot read it", which the callers treat as bad
        return None


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
