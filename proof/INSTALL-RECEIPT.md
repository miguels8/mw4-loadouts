# Install receipt: MW4 Loadouts (job mw4-webapp-r3, 2026-11-16 CT)

Target: GitHub only (no ~/.hermes or other local live target). Approved by Miguel 2026-11-16 21:28 CT.

| Step | Result |
| --- | --- |
| Repo `miguels8/mw4-loadouts` (public) | exists; `main` created by the bootstrap commit 5094ba6 |
| Backup before change | none needed: nothing existed before (new repo, new site, new schedule) |
| Reviewed PR | https://github.com/miguels8/mw4-loadouts/pull/1 squash-merged as 4bc8a37 after 2 Codex review rounds |
| GitHub Pages | `POST repos/miguels8/mw4-loadouts/pages build_type=workflow`; html_url https://miguels8.github.io/mw4-loadouts/ |
| First real run in Actions | `refresh-and-deploy` (workflow_dispatch, run 44017510226): tests pass, refresh read 30/30 guns from GitHub's runners (sources are not blocked), data commit aca5836 on main, Pages deployed |
| Live check | site returns 200; `data/status.json` served with checked 2026-11-17 UTC, failed []; 390 px headless run in `proof/live/` (all checks PASS, no console errors, KG-7 Vulcan at Lv 54 matches the card) |
| Schedule that is live | GitHub Actions cron `17 9 * * *` UTC (04:17 CT). No MiguelPC timer was needed or installed |
| Test of the install | the Actions run above plus `proof/live/shot-checks.json`; rollback if the test had failed: `UNDO.sh` |
| UNDO | `UNDO.sh` in the repo root (disable workflow, remove Pages, archive repo); not run |

## Install: level + prestige controls on every gun card (job mw4-app-inline-levels, 2026-11-16 CT)

Target: GitHub only (repo + Pages site); no `~/.hermes` or other local live target.

| Step | Result |
| --- | --- |
| Backup before change | git tag `pre-inline-levels` = d1684de (the live site before this change), pushed to origin |
| Reviewed PR | https://github.com/miguels8/mw4-loadouts/pull/3 squash-merged as ca16169 after 3 Codex review rounds (gpt-6.1-sol): r1 NO-GO (focused box vs +), r2 NO-GO (typed text lost at a step limit), r3 GO at 22f733d. Both findings fixed test-first |
| Deploy | `refresh-and-deploy` run 44026187652 (push to main): tests pass, Pages deployed |
| Live check | https://miguels8.github.io/mw4-loadouts/app.js serves the new code; `tests/tools/card-shot.mjs` against the live site at 390 px: all checks PASS (KG-7 Vulcan 63 -> 64 flips the muzzle from "Add Schlager Visiv-5 for now" to ready Ivanov QR600, ready count 4 -> 5, header Lv 64 + P3, no sideways scroll, no console errors). Evidence: `proof/live-inline/` |
| UNDO | `UNDO-inline-levels.sh` (opens a revert PR of ca16169; previous state = tag `pre-inline-levels`); not run |

## Install: game modes as one dropdown (job mw4-app-inline-levels, Amendment A, 2026-11-17 CT)

Target: GitHub only (repo + Pages site); no `~/.hermes` or other local live target.

| Step | Result |
| --- | --- |
| Backup before change | git tag `pre-mode-dropdown` = 43ec44d (the live site before this change), pushed to origin |
| Reviewed PR | https://github.com/miguels8/mw4-loadouts/pull/5 squash-merged as da488d8 after 1 Codex review round (gpt-6.1-sol): GO at 1e5d4f0, no findings |
| Deploy | `refresh-and-deploy` run 44031409690 (push to main): tests pass, Pages deployed |
| Live check | `app.js` on https://miguels8.github.io/mw4-loadouts/ contains the dropdown; `tests/tools/card-shot.mjs` against the live site at 390 px: all checks PASS (one dropdown and no chips, Hardpoint re-ranks the list, TDM order returns, KG-7 63 -> 64 still flips the muzzle). Evidence: `proof/live-mode/` |
| UNDO | `UNDO-mode-dropdown.sh` (opens a revert PR of da488d8; previous state = tag `pre-mode-dropdown`); not run |
