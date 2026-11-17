#!/usr/bin/env bash
# UNDO for job mw4-refresh-fix-20261117 (heartbeat push fix, mw4-kick fallback timer, 7 h stale threshold). Not run by the job:
# review, then run by hand. Nothing is deleted or reset; data commits after the merge are data only and are kept.
#   1. stops and removes the mw4-kick timer and service (earlier unit files come back from the install backup)
#   2. opens a PR that reverts the job's merge commit (heartbeat step back to the old shell, site threshold back to 24 h)
# The timer clone (~/.local/share/mw4-loadouts/repo) is NOT touched: the strategy timer commits notes there and pulls main
# on every run, so the clone follows main by itself once the revert PR is merged (a reset would only be undone by that pull,
# and could discard unpublished notes). After merging, check with:  git -C ~/.local/share/mw4-loadouts/repo log -1 --format=%h
# The old heartbeat shell fails on an existing status branch; reverting restores that known bug, so only undo for a bigger reason.
# Backup tag of the state before this job: pre-refresh-fix.
set -euo pipefail
REPO=miguels8/mw4-loadouts
MERGE_SHA="__MERGE_SHA__"        # filled in at install time (the job's merge commit on main)
UNITS="$HOME/.config/systemd/user"
STATE="$HOME/.local/state/mw4-loadouts"

case "$MERGE_SHA" in *__*) echo "UNDO not filled in: MERGE_SHA unset" >&2; exit 2;; esac

systemctl --user disable --now mw4-kick.timer || true
systemctl --user stop mw4-kick.service || true
BK="$(cat "$STATE/last-backup" 2>/dev/null || true)"
rm -f "$UNITS/mw4-kick.timer" "$UNITS/mw4-kick.service"
if [ -n "$BK" ]; then
  for ext in service timer; do
    if [ -f "$BK/mw4-kick.$ext" ]; then cp -a "$BK/mw4-kick.$ext" "$UNITS/"; fi
  done
fi
systemctl --user daemon-reload

work="$(mktemp -d)"
git clone --quiet "https://github.com/$REPO.git" "$work/repo"
cd "$work/repo"
git switch -c undo-refresh-fix
if [ "$(git rev-list --parents -n1 "$MERGE_SHA" | wc -w)" -gt 2 ]; then
  git revert --no-edit -m 1 "$MERGE_SHA"
else
  git revert --no-edit "$MERGE_SHA"
fi
git push origin undo-refresh-fix
gh pr create -R "$REPO" --base main --head undo-refresh-fix \
  --title "Undo: refresh fix (heartbeat push, kick timer, 7 h threshold)" \
  --body "Reverts $MERGE_SHA. Restores the old heartbeat shell (which fails when the status branch already exists) and the 24 h threshold. Data commits after the merge are data only and are kept."
echo "undone: mw4-kick timer removed, revert PR opened. Merge the revert PR to finish; the timer clone then follows main on the next strategy run."
