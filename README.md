# MW4 Loadouts

Phone web app: pick a game mode, see the best gun and exactly which parts to put on it, based on your own levels.

- **Site:** https://miguels8.github.io/mw4-loadouts/ (GitHub Pages)
- **Repo:** https://github.com/miguels8/mw4-loadouts
- **Data:** CODMunity Season 1 Multiplayer builds (main + "Close Range") and Infil "Early game" builds, refreshed daily. No AI is involved.
- **Your levels** are typed once on the "My levels" page and saved in your browser only (localStorage). An empty box means "not entered", never level 0. "Load Miguel's levels" is an opt-in one-time import (`site/miguel-levels.json`).

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
| `scripts/refresh.py` | The no-AI refresher (stdlib Python). `mw4_parse.py` reads saved/live pages as text |
| `scripts/seed_from_builder.py` | One-time seed from the old Sheet builder's data (read-only on the builder) |
| `tests/` | Python (`unittest`) and Node (`node --test`) tests, saved page fixtures, a 390 px Chromium check |
| `proof/` | Test receipts and phone screenshots of the live site |

Run everything locally: `python3 -I -m unittest discover -s tests -v && node --test tests/*.test.mjs`.
Refresh by hand: `python3 -I scripts/refresh.py` (writes `site/data/`, exit code 1 if any gun could not be read).

## Schedule (which one is live)

**GitHub Actions** (`.github/workflows/pages.yml`) runs daily at 09:17 UTC: tests, refresh, commit changed data to `main`, deploy Pages. **This is the live schedule**: the first run read all 30 guns from GitHub's runners, so the sources are not blocked and no MiguelPC timer is installed. If GitHub is ever blocked, the fallback is a user-level systemd timer on MiguelPC running the same script and pushing (no root). Install receipt: `proof/INSTALL-RECEIPT.md`; undo: `UNDO.sh`.

A gun whose page cannot be read keeps its previous build, appears in `status.json`, turns the app's "Data last checked" line red, and makes the run fail. Data older than 3 days also turns it red.

## Prior art

CANDIDATES: `gh search repos codmunity loadout` (none), `gh search code codmunity.gg/weapon` (warzone-armory, dmz_guide: unrelated scrapers/guides without per-gun unlock levels, mixed licences), the owner's own Sheet builder and CODMunity resource parse (read-only). DECISION: build; adapt the owner-supplied data and parsing approach, no third-party code copied, because no candidate carries this player's MW4 progression, stand-in and sharing rules.

## Undo

- Take the site down: `gh api -X DELETE repos/miguels8/mw4-loadouts/pages` (or Settings, Pages, Unpublish).
- Retire the app: `gh repo archive miguels8/mw4-loadouts`.
- Stop the daily refresh: `gh workflow disable refresh-and-deploy -R miguels8/mw4-loadouts`.
