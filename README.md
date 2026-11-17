# MW4 Loadouts

Phone web app: pick a game mode, see the best gun and exactly which parts to put on it, based on your own levels.

- **Site:** https://miguels8.github.io/mw4-loadouts/ (GitHub Pages)
- **Repo:** https://github.com/miguels8/mw4-loadouts
- **Data:** every real published meta build per gun: CODMunity (all public Multiplayer builds), Infil (early and endgame), MW4 Intel (mode classes, per-gun classes, curated and pro builds) and Dexerto. Refreshed every 3 hours by a script with no AI.
- **Game mode** is one dropdown at the top of the Loadouts tab (every mode, no-class modes included); the choice is remembered. **Your levels** are set right on each gun card (Loadouts tab: − / + around the level, tap the number to type, hold − or + to repeat, plus a Prestige dropdown None / 1..10 / Master) or on the "My levels" page; both write the same profile, saved in your browser only (localStorage). A card edit instantly re-draws that card and the mode's ranked list (parts flip ✅ / 🔁 / 🔒, the x/5 ready count, the early build, the rank). The collapsed card header shows "Lv N" (or "Lv ?") and a prestige badge. An empty box means "not entered", never level 0. "Load Miguel's levels" is an opt-in one-time import (`site/miguel-levels.json`).

## Build variants, the level ladder and strategy (Miguel's Q1-Q13, 2026-11-17)

- **One button per real build.** A gun card shows one button per published meta build, labelled `Best for: <modes>`; the build best for the mode in the dropdown is pressed when the card opens (a page a site wrote for exactly that mode first, then the type for the mode: close modes prefer Close Range, others Versatile then Long; then more sites agreeing; then newest). Your choice per mode is remembered. Nothing is invented (Q5): a variant is a build a site published.
- **Merged near-duplicates (Q13).** Builds sharing 4 of 5 slot+part pairs from different sites become one button: the newest site's version leads, "N sites agree: ..." lists them with dates and source links, and the one differing part shows as "Alternative: ...".
- **Stale builds are dropped (Q6).** A build dated before the gun's latest balance patch (CODMunity "Nerfs & Buffs" dates, Infil Buffed/Nerfed history) is dropped unless its site re-checked it since (same day counts). A gun left with nothing says "No build re-checked since the <date> patch" and lists the dropped builds; it ranks after every gun that has a build.
- **Best for (Q10)** comes from one fixed table, `site/data/bestfor.json`, applied to the site's own build name/type or MW4 Intel's page mode. Opus checks it at every review.
- **Setup for your level (Q1-Q3).** Per slot, in this order: the variant's own part when open; (1) a published early build while it applies; (2) the best open part of that slot that published builds use (close modes favour parts of close-typed builds); (3) a calculated pick, only on a gun whose calculation reproduced the CODMunity build in at least 4 of 5 slots at max level (Q4, `site/data/calc_gate.json`, global weights in `stat_weights.json`); (4) the old stand-in, then the lowest-level open part of the slot ("Filler"). A slot only shows 🔒 when no part of it is open at all. The card shows one line, `Next upgrade at Lv N: swap X -> Y`, and the full ladder (every level step of that variant) behind a tap (Q2).
- **Perks and gear (Q11/Q12).** The mode's kit, adjusted for the variant's role (Long/Sniper: Ghost, Ninja, Cold-Blooded; Close Range: Ninja instead of Blood Rush, not in Hijack). When the source site published perks that differ, the kit line shows `Site uses: <perk>`; ours wins.
- **How to use it (Q8).** A 3-sentence summary of the source site's own text, written on MiguelPC by the cheap OpenCode Go pool only when a variant is new (every call is in the Go usage ledger and `~/.local/state/mw4-loadouts/strategy-calls.jsonl`); when the site has no text, a fixed template per build type (`strategy_templates.json`). Claude never writes these.

## Freshness (Q7) and the Opus review (Q9)

- GitHub Actions runs `scripts/refresh.py` every 3 hours (`17 */3 * * *`). It rebuilds and deploys only when a source changed (`DATA_CHANGED=1`, step output `changed`). Every run, changed or not, pushes the heartbeat `status.json` to the orphan branch `status` (no Pages deploy) through `scripts/heartbeat.py`: every git call runs in a fresh empty directory (the checkout's own auth header plus a second one made GitHub answer 400 "Duplicate header", which the old step misread as "branch missing"), the probe tells exit 2 (missing, create it) from any other error (loud failure), and a push that loses a race is retried. The app reads `https://raw.githubusercontent.com/miguels8/mw4-loadouts/status/status.json`, falling back to the copy shipped with the page.
- **GitHub's scheduler can skip slots** (it skipped every one on 2026-11-17, ~8 h without a refresh). `mw4-kick.timer` (every 30 min, MiguelPC user timer) reads the heartbeat and, when the last check is over 3.5 h old, runs `gh workflow run refresh-and-deploy` (the machine's existing `gh` login, no new credential). It does nothing when a refresh run is already queued or running, when one started in the last 30 min, or when it already kicked in the last 60 min. The GitHub schedule stays; the kick only covers a skipped slot, so the data is at most ~4.5 h old even when GitHub skips (3.5 h + next 30 min tick + ~10 min run).
- A **red banner** shows when the last refresh failed, the record cannot be read, or the last successful check is over **7 h** old (two missed cycles; this replaced the 24 h of Q7 on 2026-11-17 because 24 h let an 8 h outage of a 3 h job pass silently). `mw4-stale-alarm.timer` (hourly, MiguelPC user timer) reads the same record and posts to #alerts through the existing `tg_route.py` (no new credential): once when the state turns bad, at most every 12 h while bad, once when back to normal.
- `status.json` also records the newest balance patch (`patch`). `mw4-review.timer` (daily 10:05) files a review card for `job-dispatch` when that patch changes or a month passed: the planner role writes a findings report, the build role applies fixes in a PR, and Eva verifies before it goes live. No model name is hard-coded.
- The four timers (`mw4-stale-alarm`, `mw4-strategy`, `mw4-review`, `mw4-kick`) and their scripts live in `pc/` (scripts, `systemd/` units, `review-card.md`); they run from a dedicated clone at `~/.local/share/mw4-loadouts/repo`, state in `~/.local/state/mw4-loadouts/` (`kick.json` holds the last kick). Install receipt: `proof/INSTALL-RECEIPT.md`; undo: `UNDO-build-variants.sh` (variants) and `UNDO-refresh-fix.sh` (heartbeat fix, kick timer, 7 h threshold). Tests for this part: `tests/test_heartbeat.py`, `tests/test_kick.py`.

## What each part shows

- ✅ ready: unlocked on that gun, or already unlocked on another gun that takes the same Muzzle / Underbarrel / Laser / Optic / Rear Grip.
- 🔁 use a stand-in until the real part opens (the stand-in comes from another published build of that gun).
- 🔒 opens at Lv N. ❓ the source does not publish the level ("level not published"): never guessed.
- Weapon Prestige turns that gun's sharing off; an Apex stays yours. Classic prestige resets player-level gates (a Permanent Unlock token keeps one item); Regular keeps them.
- Rules: best build even without the Apex (Apex only when the source build uses it); no scope above a 1x dot on AR/SMG/LMG/marksman, Mosin-Nagant on iron sights, snipers keep sniper scopes; Hyeon Burst keeps Miguel's IOTA-D pick.

## How it works

| Path | What |
| --- | --- |
| `site/` | The published static site: `index.html`, `app.js` (drawing), `engine.js` (all rules, pure), `style.css` |
| `site/data/weapons.json` | Every gun's builds, unlock levels, stand-ins, sharing table. Written by the refresher |
| `site/data/registry.json` | Hand-kept gun facts (type, tier, player unlock, picks). `static.json`: modes, kits, perk unlock levels |
| `site/data/changes.json` | "What changed" history. `status.json`: last check date and any guns that could not be read |
| `scripts/refresh.py` | The no-AI refresher (stdlib Python). `mw4_parse.py` reads saved/live pages as text; `variants.py` (collect, standing rules, patch-date drop, best-for, merge); `calc.py` (calculated picks and the Q4 gate) |
| `site/data/bestfor.json`, `stat_weights.json`, `calc_gate.json`, `strategy.json`, `strategy_templates.json` | The best-for table, the one global weight table, the per-gun Q4 result, the strategy notes and the fixed templates |
| `pc/` | MiguelPC user-timer scripts: stale alarm, refresh kick (fallback), strategy notes, Opus review trigger (+ systemd units) |
| `scripts/heartbeat.py` | Pushes `status.json` to the `status` branch (create or update, loud on error, race retry); run by the workflow |
| `scripts/seed_from_builder.py` | One-time seed from the old Sheet builder's data (read-only on the builder) |
| `tests/` | Python (`unittest`) and Node (`node --test`) tests, saved page fixtures, a real-Chromium DOM test of the card controls (`dom.test.mjs`, skipped loudly if no Chromium/Chrome), a 390 px Chromium check |
| `proof/` | Test receipts and phone screenshots of the live site |

Run everything locally: `python3 -I -m unittest discover -s tests -v && node --test tests/*.test.mjs`.
Refresh by hand: `python3 -I scripts/refresh.py` (writes `site/data/`, exit code 1 if any gun could not be read).

## Schedule (which one is live)

**GitHub Actions** (`.github/workflows/pages.yml`) runs every 3 hours (`17 */3 * * *`): tests, refresh, commit changed data to `main`, deploy Pages only when something changed, heartbeat to the `status` branch every time. **This is the live schedule** (the sources are not blocked from GitHub's runners). A gun whose page cannot be read keeps its previous build, appears in `status.json`, turns the app's data line red and makes the run fail. If GitHub skips a slot, the MiguelPC `mw4-kick` timer starts the same workflow (see Freshness). The MiguelPC timers (`mw4-stale-alarm`, `mw4-strategy`, `mw4-review`, `mw4-kick`) are user-level systemd timers, no root. Install receipt: `proof/INSTALL-RECEIPT.md`; undo: `UNDO-build-variants.sh`, `UNDO-refresh-fix.sh`.

## Prior art

CANDIDATES: `gh search repos codmunity loadout` (none), `gh search code codmunity.gg/weapon` (warzone-armory, dmz_guide: unrelated scrapers/guides without per-gun unlock levels, mixed licences), the owner's own Sheet builder and CODMunity resource parse (read-only). DECISION: build; adapt the owner-supplied data and parsing approach, no third-party code copied, because no candidate carries this player's MW4 progression, stand-in and sharing rules.

## Undo

- Take the site down: `gh api -X DELETE repos/miguels8/mw4-loadouts/pages` (or Settings, Pages, Unpublish).
- Retire the app: `gh repo archive miguels8/mw4-loadouts`.
- Stop the daily refresh: `gh workflow disable refresh-and-deploy -R miguels8/mw4-loadouts`.
