#!/usr/bin/env bash
# Installs the four MW4 Loadouts user timers on MiguelPC. No root, no sudo. Safe to run twice.
#   1. backs up any unit files already there (state dir, backup-<UTC stamp>/)
#   2. clones (or fast-forwards) the dedicated repo clone the timers run from
#   3. copies pc/systemd/mw4-*.{service,timer} into ~/.config/systemd/user, reloads, enables and starts the timers
# Undo: UNDO-build-variants.sh and UNDO-refresh-fix.sh in the repo root.
set -euo pipefail
REPO_URL="${MW4_REPO_URL:-https://github.com/miguels8/mw4-loadouts.git}"
CLONE="${MW4_CLONE:-$HOME/.local/share/mw4-loadouts/repo}"
STATE="${MW4_STATE:-$HOME/.local/state/mw4-loadouts}"
UNITS="${MW4_UNITS:-$HOME/.config/systemd/user}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$STATE/backup-$STAMP"
mkdir -p "$BK" "$STATE" "$UNITS" "$(dirname "$CLONE")"
for u in mw4-stale-alarm mw4-strategy mw4-review mw4-kick; do
  for ext in service timer; do
    if [ -f "$UNITS/$u.$ext" ]; then cp -a "$UNITS/$u.$ext" "$BK/"; fi
  done
done
echo "$BK" > "$STATE/last-backup"
if [ -d "$CLONE/.git" ]; then
  git -C "$CLONE" pull --ff-only --quiet
else
  git clone --quiet "$REPO_URL" "$CLONE"
fi
for f in "$CLONE"/pc/systemd/mw4-*.service "$CLONE"/pc/systemd/mw4-*.timer; do
  cp "$f" "$UNITS/"
done
systemctl --user daemon-reload
systemctl --user enable --now mw4-stale-alarm.timer mw4-strategy.timer mw4-review.timer mw4-kick.timer
echo "installed from $(git -C "$CLONE" rev-parse --short HEAD); backup of earlier units: $BK"
systemctl --user list-timers 'mw4-*' --all --no-pager
