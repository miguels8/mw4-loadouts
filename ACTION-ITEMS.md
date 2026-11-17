# Action items
- Done: mw4-webapp-r3 and mw4-app-inline-levels incl. Amendment A (merged, live). Nothing waiting on Miguel.
- Watch: the daily run (04:17 CT) goes red if any source cannot be read; the app then shows the data line in red. Fallback if GitHub is ever blocked: user-level timer on MiguelPC running scripts/refresh.py.
- Done: mw4-build-variants (merged, live, timers installed). Watch: red banner in the app or an #alerts post means a source cannot be read or the data is over 24 h old. Heads-up for Miguel: Q6 drops builds older than the gun's latest balance patch; the dropped counts are in reports/build-variants-report.md.
[by:claude-sonnet-5-5/mw4-webapp-r3]
- Done: mw4-refresh-fix-20261117 (heartbeat push fixed, mw4-kick fallback timer, 7 h stale threshold). Watch: a red banner or an #alerts post now means the data is over 7 h old (was 24 h); `journalctl --user -u mw4-kick` shows each kick decision. Nothing waiting on Miguel.
[by:claude-sonnet-5-5/mw4-refresh-fix-20261117]
- Follow-up (found by mw4-refresh-fix 2026-11-17): `mw4-strategy.timer` commits notes in its clone and pushes straight to `main`, which branch protection rejects (GH006, runs at 03:47, 06:48, 09:47 CST failed; its `git pull --ff-only` then also fails on the diverged clone). The 66 notes made so far were published by hand in a data PR and the clone was realigned (unpublished commits kept on branch `backup-unpublished-strategy-20261117` in the clone). Fix still needed: pc/mw4_strategy.py should push a branch and open/merge a data PR instead of pushing main.
[by:claude-sonnet-5-5/mw4-refresh-fix-20261117]
- Watch (mw4-refresh-fix 2026-11-17): the `dom.test.mjs` card-controls test failed once in CI (run 44137830095 attempt 1, 17:31 UTC, a different default build rendered and 90 s timeouts) and passed on rerun, 3 of 3 locally on the same commit. A test failure skips that refresh run; `mw4-kick` retries within ~1 h. If it repeats, make that test wait for the render or pin its mode.
[by:claude-sonnet-5-5/mw4-refresh-fix-20261117]
