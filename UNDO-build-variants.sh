#!/usr/bin/env bash
# UNDO for job mw4-build-variants (variants, ladder, 3-hourly refresh, status branch, MiguelPC timers). Not run by the job:
# review, then run by hand. Nothing is deleted without a copy: the data commits after the merge are data only and are kept.
#   1. stops and removes the three MiguelPC user timers (and their services); restores earlier unit files from the install backup
#   2. opens a PR that reverts the feature merge commit (this also puts the workflow cron back to `17 9 * * *`)
#   3. deletes the `status` heartbeat branch
# Backup tag of the state before this job: pre-build-variants.
set -euo pipefail
REPO=miguels8/mw4-loadouts
FEATURE_MERGE_SHA="__FEATURE_MERGE_SHA__"
UNITS="$HOME/.config/systemd/user"
STATE="$HOME/.local/state/mw4-loadouts"

systemctl --user disable --now mw4-stale-alarm.timer mw4-strategy.timer mw4-review.timer || true
BK="$(cat "$STATE/last-backup" 2>/dev/null || true)"
for u in mw4-stale-alarm mw4-strategy mw4-review; do
  rm -f "$UNITS/$u.timer" "$UNITS/$u.service"
  if [ -n "$BK" ]; then
    for ext in service timer; do
      if [ -f "$BK/$u.$ext" ]; then cp -a "$BK/$u.$ext" "$UNITS/"; fi
    done
  fi
done
systemctl --user daemon-reload

work="$(mktemp -d)"
git clone --quiet "https://github.com/$REPO.git" "$work/repo"
cd "$work/repo"
git switch -c undo-build-variants
git revert --no-edit -m 1 "$FEATURE_MERGE_SHA"
git push origin undo-build-variants
gh pr create -R "$REPO" --base main --head undo-build-variants \
  --title "Undo: build variants, level ladder, 3-hourly refresh" \
  --body "Reverts $FEATURE_MERGE_SHA (also puts the refresh schedule back to daily 09:17 UTC). Data commits after the merge are data only and are kept."
git push origin --delete status || true
echo "undone: timers removed, revert PR opened, status branch deleted. Merge the revert PR to finish."
