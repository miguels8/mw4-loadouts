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
