# Report: mw4-build-variants (2026-11-17)
[by:claude-sonnet-5-5/mw4-build-variants]

- Feature PR: https://github.com/miguels8/mw4-loadouts/pull/7 (merged, squash). Docs/proof PR: https://github.com/miguels8/mw4-loadouts/pull/9 (strategy helper fix) and the docs/proof PR that carries this file.
- Site: https://miguels8.github.io/mw4-loadouts/ (every gun card: one "Best for" button per real published build, setup for your level, next-upgrade line, full ladder, how to use).
- Prior art: CANDIDATES: the repo's own CODMunity/Infil parsers and engine, MW4 Intel's plain-text Print block, CODMunity's attachment-stat table | DECISION: extend in place, no third-party code, no new dependency.
- Reviewed: 3 rounds, gpt-6.1-sol (Codex), verdict GO-WITH-CONDITIONS: PR 7 r1 NO-GO (2 ALWAYS-FIX, folded test-first), r2 GO-WITH-CONDITIONS at 8879ece2e39f6d201fd481fd5a82e40b2255cd32; PR 9 r3 GO-WITH-CONDITIONS at c932b3706be4d9300f3abc56fd1869ea734b7d67. Verdicts: REVIEW-VERDICT-mw4-build-variants-r1/r2/r3.md in the jobs folder
- Checklist: all items met; see the list at the end.
- Undo: `UNDO-build-variants.sh` (repo root and the proof folder); backup tag `pre-build-variants` = da488d8.

## What was built (Miguel's Q1-Q13)
| Q | Done in | Where |
|---|---|---|
| Q5 only real published builds | `scripts/variants.py collect` (CODMunity all public MP builds, Infil endgame, MW4 Intel pages by Print block, Dexerto) | `weapons.json` `variants[].sources` |
| Q6 drop pre-patch builds | `drop_stale`, per-gun patch date from CODMunity "Nerfs & Buffs" + Infil Buffed/Nerfed history | `dropped[]`, card message when none left |
| Q13 merge 4-of-5 | `merge` | `agree`, `sources`, `alternatives` |
| Q10 best-for table | `site/data/bestfor.json`, `classify` | `best_for`, `best_for_source` |
| Q1-Q3 ladder | `site/engine.js slotPick/setupAt/ladder/nextUpgrade` | card + "Full ladder" |
| Q4 gate | `scripts/calc.py`, `site/data/stat_weights.json`, `calc_gate.json` | table below |
| Q8 strategy | `pc/mw4_strategy.py` (Go pool, only for new variants), `strategy_templates.json` | "How to use it" |
| Q11/Q12 kit | `kitFor(..., variant)`, `siteUses` | "Site uses: X" |
| Q7 freshness | workflow every 3 h, `status` branch heartbeat, 24 h red banner, `pc/mw4_alarm.py` | see proof |
| Q9 Opus review | `pc/mw4_review.py` + `review-card.md` (job-dispatch, no model named) | `mw4-review.timer` |

## Interpretations the plan fixed, and two small ones of mine
- Names differ between sites (case, `12"` vs `12`); the part name is canonicalised to the CODMunity attachment table's spelling (same slot, letters and digits only), else the site's own name with level null. Early-build part names were canonicalised too, so three "What changed" rows would have been spelling-only; they were not logged.
- A site's "Apex" row (MW4 Intel lists it as a part) is the variant's Apex, not a sixth slot.
- A merged variant's type is the most certain label in its cluster (a site's own type name beats a mode page, a keyword, a default); the newest site still leads the parts.
- A page a site wrote for exactly the selected mode opens first for that mode.
- CODMunity pages carry no prose about a build (checked on m4, kg-7-vulcan, han-86), so CODMunity gives no strategy text; MW4 Intel "Notes" plus its weapon "How to use" bullets and Infil's blurb do.

## Q4 weights
Weights are global (`stat_weights.json`). Sign evidence (ADS Speed, Sprint To Fire, Reload are times: lower is better, the plan assumed the opposite) is in the file's `evidence` field. The plan's one allowed tuning: three probes evaluated offline on the live pages: initial weights 3 of 30 guns pass; probe A (Bullet Penetration and Reload weights 0) 3; probe B (A plus larger magazine weights) 3; probe C (A plus larger sway/bob/flinch) 0. The initial weights were kept (no tuning applied, 3 before / 3 after). Pros pick ammunition (Overpressured) that the stat table cannot explain, so most guns correctly never use step 3.

## Heads-up for Eva (not an ask)
Q6 applied as written: 71 builds were dropped before their gun's latest patch; no gun is left without a variant because MW4 Intel and Infil are post-patch. Dexerto's builds are dated Aug 21 (pre-launch) and survive only on guns with no recorded balance change; they show their date.

## Q4 gate: does the calculation reproduce the CODMunity build in at least 4 of 5 slots? (per gun)

| gun | pass | matched | profile | reason |
|---|---|---|---|---|
| cronen-osprey | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| m4 | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| han-86 | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| hyeon-burst | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| patriot-xmr | fail | 3/5 | range | 3 of 5 slots match the CODMunity build |
| kastov-762 | fail | 0/5 | range | 0 of 5 slots match the CODMunity build |
| axion | fail | 3/5 | range | 3 of 5 slots match the CODMunity build |
| oden | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| cronen-squall | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| vel-46 | PASS | 4/5 | range |  |
| iso-nightshade | fail | 3/5 | range | 3 of 5 slots match the CODMunity build |
| ppsh-41 | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| wz-55-striga | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| x-58-nyx | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| csg-35 | fail | 1/5 | close | 1 of 5 slots match the CODMunity build |
| rezi-12 | fail | 0/5 | range | 0 of 5 slots match the CODMunity build |
| warlord | fail | 0/5 | range | 0 of 5 slots match the CODMunity build |
| finn-lmg | PASS | 4/5 | range |  |
| type-73 | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| apoc-338 | fail | 3/5 | range | 3 of 5 slots match the CODMunity build |
| oris-8-6 | PASS | 4/5 | range |  |
| mosin-nagant | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| mar-9 | fail | -/- | - |  |
| kg-7-vulcan | fail | 2/5 | range | 2 of 5 slots match the CODMunity build |
| signal-50 | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| astaroth-57 | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| sang-9mm | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| krait-p68 | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| 50-gs | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |
| mojave-357 | fail | 1/5 | range | 1 of 5 slots match the CODMunity build |

3 of 30 guns may use calculated picks (step 3); every other gun never does.

## Variants per gun (site, build name, date)

### Cronen Osprey (cronen-osprey) - patch date none recorded - 2 variant(s)
- `cronen-osprey-apex-attachment-2277ca` Apex Attachment - best for TDM, Frontline, Inflation, Hardcore... [type] - 3 site(s) agree - MW4 Intel: Cronen Osprey Suppressed (2026-11-16); MW4 Intel: Cronen Osprey class (2026-11-16); Infil: Endgame (2026-11-14); CODMunity: Apex Attachment (2026-11-07); CODMunity: Close Range (2026-11-07); CODMunity: Versatile (2026-11-06)
- `cronen-osprey-versatile-3a5d8a` Versatile - best for TDM, Frontline, Inflation, Hardcore [default] - 1 site(s) agree - Dexerto: Dexerto build (2026-10-28)

### M4 (m4) - patch date 2026-11-13 - 5 variant(s)
- `m4-versatile-1439ac` Versatile - best for TDM, Frontline, Inflation, Hardcore [default] - 1 site(s) agree - MW4 Intel: #1 Suppressed M4 (2026-11-16)
- `m4-pro-ranked-40eea0` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Dashy M4 (2026-11-16)
- `m4-versatile-5cb987` Versatile - best for TDM, Frontline, Inflation, Hardcore... [mode] - 1 site(s) agree - MW4 Intel: M4 All-Rounder (2026-11-16); MW4 Intel: M4 Defuse Cover (2026-11-16); MW4 Intel: M4 Flag Control (2026-11-16); MW4 Intel: M4 class (2026-11-16)
- `m4-close-range-a332c8` Close Range - best for S&D, Hardpoint, Hijack, Kill Confirmed... [mode] - 1 site(s) agree - MW4 Intel: Suppressed M4 Entry (2026-11-16)
- `m4-versatile-8737d7` Versatile - best for TDM, Frontline, Inflation, Hardcore [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Versatile (2026-11-13)

### Han 86 (han-86) - patch date 2026-11-13 - 7 variant(s)
- `han-86-versatile-d18051` Versatile - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [mode] - 1 site(s) agree - MW4 Intel: #4 Han 86 Fold-Stock Rush (2026-11-16); MW4 Intel: Han 86 Push (2026-11-16); MW4 Intel: Han 86 Starter (2026-11-16); MW4 Intel: Han 86 class (2026-11-16); MW4 Intel: SANG 9mm class (2026-11-16)
- `han-86-pro-ranked-119958` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Alluka Han 86 (2026-11-16)
- `han-86-pro-ranked-0520b2` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Beans Han 86 (2026-11-16)
- `han-86-pro-ranked-177c01` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Drazah Han 86 (2026-11-16)
- `han-86-pro-ranked-35f8e2` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Ghosty Han 86 (2026-11-16)
- `han-86-pro-ranked-83361b` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Simp Han 86 (2026-11-16)
- `han-86-versatile-0e89c7` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Hyeon Burst (hyeon-burst) - patch date 2026-11-13 - 2 variant(s)
- `hyeon-burst-versatile-afada2` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: Hyeon Burst class (2026-11-16)
- `hyeon-burst-versatile-9ba8b8` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Patriot XMR (patriot-xmr) - patch date 2026-11-13 - 3 variant(s)
- `patriot-xmr-versatile-f6a516` Versatile - best for TDM, Frontline, Inflation, Hardcore [default] - 1 site(s) agree - MW4 Intel: #5 Patriot XMR Red Dot (2026-11-16)
- `patriot-xmr-versatile-e14b68` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: Patriot XMR class (2026-11-16)
- `patriot-xmr-versatile-52265b` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Kastov 762 (kastov-762) - patch date 2026-11-13 - 3 variant(s)
- `kastov-762-long-range-8aeca7` Long Range - best for TDM, Frontline, Inflation, Hardcore... [mode] - 1 site(s) agree - MW4 Intel: Kastov 762 class (2026-11-16); MW4 Intel: Kastov Lane Control (2026-11-16); MW4 Intel: Kastov Lane Holder (2026-11-16)
- `kastov-762-versatile-43b265` Versatile - best for TDM, Frontline, Inflation, Hardcore [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Versatile (2026-11-13)
- `kastov-762-close-range-9ec5c0` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [type] - 1 site(s) agree - CODMunity: Close Range (2026-11-13)

### Axion (axion) - patch date 2026-11-13 - 2 variant(s)
- `axion-versatile-9d9b88` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: Axion class (2026-11-16)
- `axion-versatile-4d7105` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Oden (oden) - patch date 2026-11-13 - 2 variant(s)
- `oden-versatile-1311f5` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: Oden class (2026-11-16)
- `oden-versatile-a2fc2b` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Cronen Squall (cronen-squall) - patch date 2026-11-13 - 2 variant(s)
- `cronen-squall-versatile-8b24e8` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: Cronen Squall class (2026-11-16)
- `cronen-squall-versatile-d9ab89` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### VEL 46 (vel-46) - patch date 2026-11-06 - 3 variant(s)
- `vel-46-close-range-d14eee` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [mode] - 1 site(s) agree - MW4 Intel: #2 VEL 46 Snap Shredder (2026-11-16); MW4 Intel: VEL 46 Forward Shredder (2026-11-16); MW4 Intel: VEL 46 Shredder (2026-11-16); MW4 Intel: VEL 46 class (2026-11-16)
- `vel-46-pro-ranked-bd4c84` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: HyDra / Afro VEL 46 (2026-11-16)
- `vel-46-close-range-799a75` Close Range - best for TDM, Frontline, Inflation, Hardcore... [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Close Range (2026-11-07); CODMunity: Versatile (2026-11-06)

### ISO Nightshade (iso-nightshade) - patch date 2026-11-13 - 6 variant(s)
- `iso-nightshade-versatile-c173f2` Versatile - best for TDM, Frontline, Inflation, Hardcore [default] - 1 site(s) agree - MW4 Intel: #3 Silent ISO Nightshade (2026-11-16)
- `iso-nightshade-pro-ranked-32fdd6` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: HyDra ISO Nightshade (2026-11-16)
- `iso-nightshade-close-range-da68ba` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [mode] - 1 site(s) agree - MW4 Intel: ISO Hill Rush (2026-11-16); MW4 Intel: ISO Nightshade Rush (2026-11-16); MW4 Intel: ISO Nightshade class (2026-11-16); MW4 Intel: Krait P68 class (2026-11-16)
- `iso-nightshade-pro-ranked-d424a8` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Shotzzy ISO Nightshade (2026-11-16)
- `iso-nightshade-pro-ranked-eeff18` Pro (Ranked) - best for Hardpoint, S&D [type] - 1 site(s) agree - MW4 Intel: Simp ISO Nightshade (2026-11-16)
- `iso-nightshade-versatile-58eb1e` Versatile - best for TDM, Frontline, Inflation, Hardcore [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Versatile (2026-11-13)

### PPSh-41 (ppsh-41) - patch date 2026-11-13 - 2 variant(s)
- `ppsh-41-versatile-cd68ad` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: PPSh-41 class (2026-11-16)
- `ppsh-41-versatile-83ba9b` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Wz.55 Striga (wz-55-striga) - patch date 2026-11-13 - 2 variant(s)
- `wz-55-striga-close-range-6174ac` Close Range - best for Hijack, Hardpoint, Kill Confirmed, Drop Zone... [mode] - 1 site(s) agree - MW4 Intel: Striga Spike Runner (2026-11-16); MW4 Intel: Wz.55 Striga class (2026-11-16)
- `wz-55-striga-versatile-0716c7` Versatile - best for TDM, Frontline, Inflation, Hardcore [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Versatile (2026-11-13)

### X-58 Nyx (x-58-nyx) - patch date 2026-11-13 - 2 variant(s)
- `x-58-nyx-versatile-e5812c` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: X-58 Nyx class (2026-11-16)
- `x-58-nyx-versatile-bdff14` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### CSG-35 (csg-35) - patch date 2026-11-13 - 2 variant(s)
- `csg-35-versatile-93245e` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: CSG-35 class (2026-11-16)
- `csg-35-versatile-e94ad7` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Rezi 12 (rezi-12) - patch date 2026-11-13 - 2 variant(s)
- `rezi-12-close-range-949503` Close Range - best for TDM, Frontline, Inflation, Hardcore... [mode] - 1 site(s) agree - MW4 Intel: Rezi 12 class (2026-11-16); MW4 Intel: Rezi Enforcer Breacher (2026-11-16)
- `rezi-12-versatile-ecc60c` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Warlord (warlord) - patch date 2026-11-13 - 1 variant(s)
- `warlord-versatile-cc7b33` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 2 site(s) agree - MW4 Intel: Warlord class (2026-11-16); Infil: Endgame (2026-11-14)

### FiNN LMG (finn-lmg) - patch date 2026-11-13 - 2 variant(s)
- `finn-lmg-long-range-3218a0` Long Range - best for Domination, S&D, Ground War, TDM... [mode] - 1 site(s) agree - MW4 Intel: FiNN Flag Anchor (2026-11-16); MW4 Intel: FiNN LMG class (2026-11-16)
- `finn-lmg-versatile-77d041` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Type 73 (type-73) - patch date 2026-11-06 - 2 variant(s)
- `type-73-long-range-0f960d` Long Range - best for S&D, Ground War, Domination, TDM... [keyword] - 1 site(s) agree - MW4 Intel: Type 73 Hardpoint Anchor (2026-11-16); MW4 Intel: Type 73 class (2026-11-16)
- `type-73-apex-attachment-3a4758` Apex Attachment - best for TDM, Frontline, Inflation, Hardcore... [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Apex Attachment (2026-11-07); CODMunity: Close Range (2026-11-07); CODMunity: Versatile (2026-11-06)

### APOC-338 (apoc-338) - patch date 2026-11-06 - 2 variant(s)
- `apoc-338-versatile-076c80` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: APOC-338 class (2026-11-16)
- `apoc-338-versatile-317afd` Versatile - best for TDM, Frontline, Inflation, Hardcore... [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Versatile (2026-11-11); CODMunity: Apex Attachment (2026-11-07); CODMunity: Close Range (2026-11-07)

### Oris 8.6 (oris-8-6) - patch date 2026-11-13 - 2 variant(s)
- `oris-8-6-versatile-ff3e27` Versatile - best for TDM, Frontline, Inflation, Hardcore... [keyword] - 1 site(s) agree - MW4 Intel: Mojave .357 class (2026-11-16); MW4 Intel: Oris 8.6 Aggressive Sniper (2026-11-16); MW4 Intel: Oris 8.6 class (2026-11-16)
- `oris-8-6-versatile-d11d48` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Mosin-Nagant (mosin-nagant) - patch date 2026-11-13 - 4 variant(s)
- `mosin-nagant-versatile-3f3ef6` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: Mosin-Nagant class (2026-11-16)
- `mosin-nagant-apex-attachment-fa5877` Apex Attachment - best for TDM, Frontline, Inflation, Hardcore [type] - 1 site(s) agree - CODMunity: Apex Attachment (2026-11-14)
- `mosin-nagant-close-range-d7bc6a` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [type] - 1 site(s) agree - CODMunity: Close Range (2026-11-14)
- `mosin-nagant-versatile-b06282` Versatile - best for TDM, Frontline, Inflation, Hardcore [type] - 2 site(s) agree - CODMunity: Versatile (2026-11-14); Infil: Endgame (2026-11-14)

### MAR-9 (mar-9) - patch date 2026-11-13 - 3 variant(s)
- `mar-9-versatile-761f18` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - MW4 Intel: MAR-9 class (2026-11-16)
- `mar-9-versatile-293c14` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)
- `mar-9-close-range-7ba0b0` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [type] - 1 site(s) agree - CODMunity: Close Range (2026-11-13)

### KG-7 Vulcan (kg-7-vulcan) - patch date none recorded - 4 variant(s)
- `kg-7-vulcan-long-range-3faf1d` Long Range - best for TDM, Frontline, Inflation, Hardcore... [mode] - 1 site(s) agree - MW4 Intel: .50 GS class (2026-11-16); MW4 Intel: KG-7 + ISO Overkill (2026-11-16); MW4 Intel: KG-7 Vulcan + ISO (Overkill) (2026-11-16); MW4 Intel: KG-7 Vulcan class (2026-11-16)
- `kg-7-vulcan-sniper-025f0c` Sniper - best for TDM, Frontline, Inflation, Hardcore... [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Sniper (2026-11-11)
- `kg-7-vulcan-close-range-d328b4` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [type] - 1 site(s) agree - CODMunity: Close Range (2026-11-07)
- `kg-7-vulcan-versatile-005ccc` Versatile - best for TDM, Frontline, Inflation, Hardcore [default] - 1 site(s) agree - Dexerto: Dexerto build (2026-08-21)

### Signal 50 (signal-50) - patch date none recorded - 4 variant(s)
- `signal-50-long-range-cc5d94` Long Range - best for Ground War, S&D, Domination, TDM... [mode] - 1 site(s) agree - MW4 Intel: Signal 50 Support (2026-11-16); MW4 Intel: Signal 50 class (2026-11-16)
- `signal-50-sniper-952902` Sniper - best for TDM, Frontline, Inflation, Hardcore... [type] - 2 site(s) agree - Infil: Endgame (2026-11-14); CODMunity: Sniper (2026-11-11); CODMunity: Apex Attachment (2026-11-07)
- `signal-50-close-range-6af741` Close Range - best for Hardpoint, Hijack, Kill Confirmed, Drop Zone... [type] - 1 site(s) agree - CODMunity: Close Range (2026-11-07)
- `signal-50-versatile-bfc9fd` Versatile - best for TDM, Frontline, Inflation, Hardcore [default] - 1 site(s) agree - Dexerto: Dexerto build (2026-08-21)

### Astaroth .57 (astaroth-57) - patch date none recorded - 2 variant(s)
- `astaroth-57-sniper-7dbf8a` Sniper - best for TDM, Frontline, Inflation, Hardcore... [type] - 4 site(s) agree - MW4 Intel: Astaroth .57 class (2026-11-16); Infil: Endgame (2026-11-14); CODMunity: Sniper (2026-11-11); CODMunity: Close Range (2026-11-07); Dexerto: Dexerto build (2026-10-20)
- `astaroth-57-apex-attachment-b6e893` Apex Attachment - best for TDM, Frontline, Inflation, Hardcore [type] - 1 site(s) agree - CODMunity: Apex Attachment (2026-11-07)

### SANG 9mm (sang-9mm) - patch date 2026-11-13 - 1 variant(s)
- `sang-9mm-versatile-090ae7` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Krait P68 (krait-p68) - patch date 2026-11-13 - 1 variant(s)
- `krait-p68-versatile-c9f125` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### .50 GS (50-gs) - patch date 2026-11-13 - 1 variant(s)
- `50-gs-versatile-2564af` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

### Mojave .357 (mojave-357) - patch date 2026-11-13 - 1 variant(s)
- `mojave-357-versatile-4a950b` Versatile - best for TDM, Frontline, Inflation, Hardcore [keyword] - 1 site(s) agree - Infil: Endgame (2026-11-14)

## Dropped before the latest balance patch (Q6)

CODMunity: 46, Dexerto: 25

Guns left with no variant: none

## Builds whose 'best for' fell to the default (Versatile, source default)

- cronen-osprey: Dexerto Dexerto build
- m4: MW4 Intel #1 Suppressed M4
- patriot-xmr: MW4 Intel #5 Patriot XMR Red Dot
- iso-nightshade: MW4 Intel #3 Silent ISO Nightshade
- kg-7-vulcan: Dexerto Dexerto build
- signal-50: Dexerto Dexerto build

Totals: 30 guns, 77 variants. status: checked_at 2026-11-17T08:55:33Z, failed [], patch {'date': '2026-11-13', 'name': 'Nov 13 tuning update', 'source': 'https://infil.app/patches/', 'seen_at': '2026-11-17T08:16:35Z'}


## Checklist
- plan entry named: PLAN-mw4-build-variants.md. Prior art line above.
- smallest slice that works: A parsers, B variants, C calc, D refresher, E engine, F UI, G workflow, H timers, each with RED then GREEN in `proof/tdd/`.
- nothing it breaks later: old `builds`, What-changed, legacy card path kept; DOM tests for the old card still pass.
- tests ask the boundary: page fixtures, injected fetch/run; real Chromium at 390 px.
- independent review at the exact hash: see Reviewed.
- rollback stated: `UNDO-build-variants.sh`.
- docs and action-item row updated: README, ROADMAP, ACTION-ITEMS, WORKLOG.
- compound: none - nothing reusable beyond this repo.

## Live proof (everything below ran on 2026-11-17, MiguelPC, CT)
- Feature PR 7 squash-merged as 9fdead9; deploy run 44049699790 success; one workflow_dispatch run 44050334428 success created the `status` branch (raw URL serves a fresh `checked_at`).
- Cron `17 */3 * * *` is live (`gh api repos/miguels8/mw4-loadouts/actions/workflows/pages.yml`): runs at 00:17, 03:17, 06:17, 09:17, 12:17, 15:17, 18:17, 21:17 UTC; a scheduled run deploys only when `DATA_CHANGED=1`.
- 390 px screenshots from the LIVE site in `proof/live-variants/` (a: KG-7 Vulcan variant buttons; b: KG-7 at Lv 54 with the ladder open and the next-upgrade line; c1/c2: KG-7 in Hardpoint vs S&D pressing different variants) with `variant-checks.json` (all PASS).
- Timers: `proof/pc/timers.txt` (`systemctl --user list-timers 'mw4-*' --all`, all three enabled). Install output `proof/pc/install-output.txt` (backup of earlier units: none existed, empty backup dir `~/.local/state/mw4-loadouts/backup-20261117T085954Z`). Dry runs `proof/pc/dry-runs.txt`.
- Forced alarm test: `proof/pc/alarm-test.txt`: `pc/mw4_alarm.py --status-file tests/fixtures/status-stale.json --force` printed the TEST message (45 h old) and `tg_route.py alerts` exited 0 (Telegram accepted it).
- Strategy run for real through `systemctl --user start mw4-strategy.service`: 20 calls, 20 ok, 20 new lines in `~/.hermes/state/usage-gate/go-usage.jsonl` (name `ask_opencode_go`, model deepseek-v4.1-flash, 1673 -> 1693) matched by `~/.local/state/mw4-loadouts/strategy-calls.jsonl`; data commit `608c0bc` pushed to main and deployed. The first attempt failed all 20 calls (the helper needs the Hermes python); fixed in PR 9 and the notes reset; 46 variants still wait and the timer (every 3 h at :47) does 20 per run.
- Review trigger: `~/.local/state/mw4-loadouts/review.json` seeded with the baseline (patch 2026-11-13); `mw4-review.timer` daily 10:05.
