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

## Install: build variants, level ladder, 3-hourly refresh, MiguelPC timers (job mw4-build-variants, 2026-11-17 CT)

Targets: GitHub (repo, Pages site, `status` branch) and MiguelPC user-level systemd timers. No root, no sudo, no new credential.

| Step | Result |
| --- | --- |
| Backup before change | git tag `pre-build-variants` = da488d8 pushed to origin; timer install backed up earlier units (none existed) to `~/.local/state/mw4-loadouts/backup-20261117T085954Z`, path in `~/.local/state/mw4-loadouts/last-backup` |
| Reviewed PRs | https://github.com/miguels8/mw4-loadouts/pull/7 squash-merged as 9fdead9 (gpt-6.1-sol: r1 NO-GO, r2 GO-WITH-CONDITIONS at 8879ece); https://github.com/miguels8/mw4-loadouts/pull/9 (r3 GO-WITH-CONDITIONS at c932b37) |
| Deploy | `refresh-and-deploy` run 44049699790 (push to main) success; run 44050334428 (workflow_dispatch) success, created the `status` branch; raw URL https://raw.githubusercontent.com/miguels8/mw4-loadouts/status/status.json serves the heartbeat |
| Schedule | cron `17 */3 * * *`; scheduled runs deploy only when a source changed |
| PC timers | `bash pc/install.sh` (clone `~/.local/share/mw4-loadouts/repo`, units in `~/.config/systemd/user`, `systemctl --user enable --now`): `proof/pc/install-output.txt`, `proof/pc/timers.txt` (mw4-stale-alarm hourly, mw4-strategy every 3 h at :47, mw4-review daily 10:05, all enabled) |
| Live checks | `tests/tools/variant-shot.mjs` against https://miguels8.github.io/mw4-loadouts/ at 390 px: all PASS (`proof/live-variants/variant-checks.json`, 4 screenshots); forced alarm test `proof/pc/alarm-test.txt`; strategy run (20 Go calls, 20 ledger lines); see `reports/build-variants-report.md` |
| UNDO | `UNDO-build-variants.sh` (removes the timers and restores earlier units, opens a revert PR of 9fdead9, deletes the `status` branch); previous state = tag `pre-build-variants`; not run |


## Install: refresh fix (job mw4-refresh-fix-20261117, 2026-11-17 CT)

Target: GitHub (workflow, Pages) and one new MiguelPC user timer (`mw4-kick`, no root, no new credential: the existing `gh` login).

| Step | Result |
| --- | --- |
| Backup before change | git tag `pre-refresh-fix` = 98b4cb2 (main before the job), pushed; `pc/install.sh` copied the earlier unit files to `~/.local/state/mw4-loadouts/backup-20261117T172320Z` (the first install backup, 20261117T085954Z, is kept) |
| Reviewed PR | https://github.com/miguels8/mw4-loadouts/pull/11 squash-merged as e7f0fca after 2 Codex review rounds (reviewer-crossvendor, tier risky): r1 NO-GO-pending (4 findings: kick timestamp validation, UNDO clone reset x2, full undo missed the kick timer), all folded test-first (proof/refresh-fix/RED-review-r1.txt, GREEN-review-r1.txt); r2 GO at 35356ec, no findings, score 9.5/10 |
| Side fix | PR 12 (https://github.com/miguels8/mw4-loadouts/pull/12, merged 225d458): published the 66 strategy notes the strategy timer could not push (branch protection, GH006, runs 03:47/06:48/09:47 CST); clone realigned with main, original commits kept on clone branch `backup-unpublished-strategy-20261117` |
| Install | `pc/install.sh` from clone commit 225d458 at 11:23 CST: `mw4-kick.timer` enabled, first tick 11:30:56 CST; the other three timers unchanged |
| Test of the install | the kick fired on its own at 11:30:56 CST ("kick: last check is 9 h old", `kicked refresh-and-deploy`), starting run 44137830095 (attempt 1 failed in a flaky Chromium test before any refresh, attempt 2 passed): refresh success, heartbeat step success (the step that failed in run 44126897076), Pages deployed with the 7 h threshold; `status.json` on the status branch checked_at 2026-11-17T17:52:10Z, second commit on top of the old history. Evidence: `proof/refresh-fix/live/` |
| Live check | https://miguels8.github.io/mw4-loadouts/engine.js serves `hours > 7`; kick dry run "no kick: data is fresh"; alarm dry run "no post (bad=False)" |
| UNDO | `UNDO-refresh-fix.sh` (removes the kick timer, opens a revert PR of e7f0fca; never resets or deletes the clone); `UNDO-build-variants.sh` now also removes the kick timer and works on a squash commit. Not run |
