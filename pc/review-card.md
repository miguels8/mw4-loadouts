---
kind: report
---
# Job mw4-review-{date}: refine the MW4 Loadouts builds ({reason})

Miguel's decision Q9 (2026-11-17, Telegram): "After every balance patch (the script spots it) plus once a month. Opus writes a findings report, Sonnet applies the fixes, and I check before it goes live". This card was filed by the MiguelPC timer `mw4-review.timer`. Reason it fired: {reason}.

Repo: miguels8/mw4-loadouts (clone at /home/santo/dev/mw4-loadouts; site https://miguels8.github.io/mw4-loadouts/). Miguel's grill answers Q1-Q13 are in /home/santo/Obsidian/00-Meta/decisions/2026-11-17.md (lines tagged `mw4-level-ladder-grill`). They are decisions: a finding that contradicts one is a question to Eva (an ASK file), never a change.

## What the planner reads
1. `site/data/bestfor.json` (the fixed "best for" table, Q10): is every type and keyword still right after the patch? Which builds fell to `best_for_source: default`?
2. `site/data/calc_gate.json` (the per-gun Q4 gate) and `site/data/stat_weights.json`: did any gun cross the 4-of-5 line either way? Is any weight now doubtful? Weights are global, one table, never tuned for one gun.
3. `site/data/weapons.json`: variants per gun (sources, dates, `agree`), the `dropped` builds and their reasons (Q6), guns with no variant, `patch_date` per gun.
4. `site/data/status.json` and the status branch heartbeat: failed sources, the `patch` record.
5. `site/data/strategy.json`: notes that no longer match their variant (a variant id changes when its parts change, so stale notes are simply unused; list orphans).
6. The patch notes on https://infil.app/patches/ and the per-gun "Nerfs & Buffs" on https://codmunity.gg/weapon/mw4/<gun>.

## What the planner writes
A findings report at `/home/santo/.hermes/cache/scratch/claude-jobs/mw4-review-{date}-findings.md`: numbered findings with evidence, each marked fix / no-action (with the reason) / question for Miguel. Then, only if there is a fix, write a `kind: build` card and start it with `job-dispatch mw4-review-fix-{date} --card <card>` (no model flags: the role defaults pick the builder). The fix card must say the PR waits for Eva to verify it before it goes live: put `Land: hold - Miguel's Q9: he checks the review fixes before they go live` in its finish file. Never edit the live site from this job.

## Finish
Write the finish file named by the dispatcher: line 1 your model id, line 2 DONE, then `Findings: <path>` and `Fix job: <slug or none>`.

## Out of scope
No new accounts, secrets or credentials. No root. Warzone and DMZ are out. Do not touch the Google Sheet.
