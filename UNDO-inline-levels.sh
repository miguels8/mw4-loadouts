#!/usr/bin/env bash
# UNDO for job mw4-app-inline-levels (level + prestige controls on every gun card). Not run by the job. Review, then run by hand.
# Backup of the previous live state: git tag pre-inline-levels (commit d1684de, the site before PR #3).
# This opens a revert PR for the squash commit ca16169; merging it redeploys the site through the normal workflow.
set -euo pipefail
REPO=miguels8/mw4-loadouts
WORK=$(mktemp -d)
git clone -q "https://github.com/$REPO.git" "$WORK/repo"
cd "$WORK/repo"
git checkout -q -b undo-inline-levels
git revert --no-edit ca16169dd2c73f3bf106922823d6b265f123d50a
git push -q -u origin undo-inline-levels
gh pr create -R "$REPO" --base main --head undo-inline-levels --title "Revert: level and prestige controls on cards" --body "Undo of #3. Previous site state is tag pre-inline-levels (d1684de)."
echo "revert PR opened; merge it to redeploy the previous site. Clone kept at $WORK/repo"
