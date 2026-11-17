#!/usr/bin/env bash
# UNDO for job mw4-app-inline-levels Amendment A (game mode dropdown). Not run by the job. Review, then run by hand.
# Backup of the previous live state: git tag pre-mode-dropdown (commit 43ec44d, the site before PR #5).
# This opens a revert PR for the squash commit da488d8; merging it redeploys the site through the normal workflow.
set -euo pipefail
REPO=miguels8/mw4-loadouts
WORK=$(mktemp -d)
git clone -q "https://github.com/$REPO.git" "$WORK/repo"
cd "$WORK/repo"
git checkout -q -b undo-mode-dropdown
git revert --no-edit da488d80b8e0f57f6975565cfa739a5762d6f016
git push -q -u origin undo-mode-dropdown
gh pr create -R "$REPO" --base main --head undo-mode-dropdown --title "Revert: game mode dropdown" --body "Undo of #5. Previous site state is tag pre-mode-dropdown (43ec44d)."
echo "revert PR opened; merge it to redeploy the previous site. Clone kept at $WORK/repo"
