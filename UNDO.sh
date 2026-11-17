#!/usr/bin/env bash
# UNDO for the MW4 Loadouts install (job mw4-webapp-r3). Not run by the job. Review, then run by hand.
# Stops the daily refresh, takes the Pages site down, archives the repo (read-only, nothing is deleted).
# There was no earlier live state to restore: the repo, the site and the schedule were all created by this job.
set -euo pipefail
REPO=miguels8/mw4-loadouts
gh workflow disable refresh-and-deploy -R "$REPO"
gh api -X DELETE "repos/$REPO/pages"
gh repo archive "$REPO" --yes
echo "undone: refresh disabled, Pages removed, repo archived"
