# Action items
- Done: mw4-webapp-r3 and mw4-app-inline-levels incl. Amendment A (merged, live). Nothing waiting on Miguel.
- Watch: the daily run (04:17 CT) goes red if any source cannot be read; the app then shows the data line in red. Fallback if GitHub is ever blocked: user-level timer on MiguelPC running scripts/refresh.py.
- Done: mw4-build-variants (merged, live, timers installed). Watch: red banner in the app or an #alerts post means a source cannot be read or the data is over 24 h old. Heads-up for Miguel: Q6 drops builds older than the gun's latest balance patch; the dropped counts are in reports/build-variants-report.md.
[by:claude-sonnet-5-5/mw4-webapp-r3]
- Done: mw4-refresh-fix-20261117 (heartbeat push fixed, mw4-kick fallback timer, 7 h stale threshold). Watch: a red banner or an #alerts post now means the data is over 7 h old (was 24 h); `journalctl --user -u mw4-kick` shows each kick decision. Nothing waiting on Miguel.
[by:claude-sonnet-5-5/mw4-refresh-fix-20261117]
