// Unlock / stand-in / prestige / ranking logic. Run: node --test tests/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  numOrNull, normalizeProfile, gunOpen, sharedFrom, partStatus, buildView, apexView, earlyView,
  modeBuildKey, kitFor, rankGuns, fitFor, importProfile,
} from "../site/engine.js";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const data = read("../site/data/weapons.json");
const statics = read("../site/data/static.json");
const miguel = read("../site/miguel-levels.json");

const gunBy = (slug) => data.guns.find((g) => g.slug === slug);
const prof = (o = {}) => normalizeProfile(o);
const P = (slot, name, level, stand_in = null) => ({ slot, name, level, stand_in });
const mini = (extra = {}) => ({
  slug: "t1", name: "Test One", type: "AR", tier: "A", unlock: { level: null, bp_tier: null }, max_level: 50,
  apex: { name: "Apex T", level: 50 }, table: {},
  builds: { main: { label: "Versatile", date: "2026-11-01", url: "u", apex_on: false, notes: [],
    parts: [P("Muzzle", "M1", 10), P("Laser", "L1", 40, { slot: "Laser", name: "L0", level: 20 }), P("Stock", "S1", null)] },
    close: null, early: null },
  ...extra,
});
const miniData = (guns) => ({ guns, optics: {} });

test("empty level is not entered, never level 0", () => {
  assert.equal(numOrNull(""), null);
  assert.equal(numOrNull(undefined), null);
  assert.equal(numOrNull(null), null);
  assert.equal(numOrNull("abc"), null);
  assert.equal(numOrNull("0"), 0);
  assert.equal(numOrNull(" 54 "), 54);
  const p = prof({ guns: { t1: { level: "" } } });
  assert.equal(p.guns.t1.level, null);
});

test("not entered shows the plain part with its level, no lock", () => {
  const g = mini();
  const s = partStatus(g, g.builds.main.parts[0], prof(), miniData([g]));
  assert.equal(s.state, "plain");
  assert.match(s.note, /Lv\s10/);
});

test("ready, stand-in, locked and unknown", () => {
  const g = mini();
  const d = miniData([g]);
  const at = (lv) => prof({ guns: { t1: { level: lv } } });
  assert.equal(partStatus(g, g.builds.main.parts[0], at(10), d).state, "ready");
  assert.equal(partStatus(g, g.builds.main.parts[0], at(9), d).state, "locked");
  assert.match(partStatus(g, g.builds.main.parts[0], at(9), d).note, /Lv\s10/);
  const l = partStatus(g, g.builds.main.parts[1], at(25), d);
  assert.equal(l.state, "standin");
  assert.equal(l.standIn.name, "L0");
  assert.match(l.label, /L0/);
  assert.match(l.note, /Lv\s40/);
  assert.equal(partStatus(g, g.builds.main.parts[1], at(19), d).state, "locked");
  assert.equal(partStatus(g, g.builds.main.parts[1], at(40), d).state, "ready");
  const u = partStatus(g, g.builds.main.parts[2], at(30), d);
  assert.equal(u.state, "unknown");
  assert.match(u.note, /level not published/i);
});

test("level 0 typed is a real level, not 'not entered'", () => {
  const g = mini();
  const s = partStatus(g, g.builds.main.parts[0], prof({ guns: { t1: { level: 0 } } }), miniData([g]));
  assert.equal(s.state, "locked");
});

test("shared attachments: a part open on another gun is open here", () => {
  const a = mini({ slug: "a", name: "A", table: { M1: ["Muzzle", 10] } });
  const b = mini({ slug: "b", name: "B", table: { M1: ["Muzzle", 30] } });
  b.builds.main.parts[0] = P("Muzzle", "M1", 30);
  const d = miniData([a, b]);
  const p = prof({ guns: { a: { level: 12 }, b: { level: 5 } } });
  assert.equal(sharedFrom(b, b.builds.main.parts[0], p, d), "A");
  const s = partStatus(b, b.builds.main.parts[0], p, d);
  assert.equal(s.state, "ready");
  assert.equal(s.sharedFrom, "A");
  // not shared when the other gun has not reached it
  const p2 = prof({ guns: { a: { level: 9 }, b: { level: 5 } } });
  assert.equal(sharedFrom(b, b.builds.main.parts[0], p2, d), null);
});

test("sharing only covers shareable slots", () => {
  const a = mini({ slug: "a", name: "A", table: { S1: ["Stock", 1] } });
  const b = mini({ slug: "b", name: "B" });
  const p = prof({ guns: { a: { level: 50 }, b: { level: 5 } } });
  assert.equal(sharedFrom(b, b.builds.main.parts[2], p, miniData([a, b])), null);
});

test("weapon prestige relocks that gun's own sharing; Apex stays", () => {
  const a = mini({ slug: "a", name: "A", table: { M1: ["Muzzle", 10] } });
  const b = mini({ slug: "b", name: "B", table: { M1: ["Muzzle", 30] } });
  b.builds.main.parts[0] = P("Muzzle", "M1", 30);
  const d = miniData([a, b]);
  const p = prof({ guns: { a: { level: 12 }, b: { level: 5, prestige: "1" } } });
  assert.equal(sharedFrom(b, b.builds.main.parts[0], p, d), null);
  assert.equal(partStatus(b, b.builds.main.parts[0], p, d).state, "locked");
  // a prestiged source gun counts as earned for others
  const p3 = prof({ guns: { a: { level: 2, prestige: "master" }, b: { level: 5 } } });
  assert.equal(sharedFrom(b, b.builds.main.parts[0], p3, d), "A");
  // apex: owned after prestige
  b.builds.main.apex_on = true;
  const ap = apexView(b, b.builds.main, p);
  assert.equal(ap.state, "ready");
});

test("apex: only when the build uses it; opens at max level", () => {
  const g = mini();
  g.builds.main.apex_on = true;
  assert.equal(apexView(g, g.builds.main, prof()).state, "plain");
  assert.equal(apexView(g, g.builds.main, prof({ guns: { t1: { level: 49 } } })).state, "locked");
  assert.equal(apexView(g, g.builds.main, prof({ guns: { t1: { level: 50 } } })).state, "ready");
  assert.equal(apexView(g, g.builds.main, prof({ guns: { t1: { level: 49, max: 49 } } })).state, "ready");
  g.builds.main.apex_on = false;
  assert.equal(apexView(g, g.builds.main, prof({ guns: { t1: { level: 50 } } })).state, "off");
});

test("gun opens by player level; empty player level never locks", () => {
  const g = mini({ unlock: { level: 30, bp_tier: null } });
  assert.equal(gunOpen(g, prof()).open, true);
  assert.equal(gunOpen(g, prof({ player: { level: 29 } })).open, false);
  assert.match(gunOpen(g, prof({ player: { level: 29 } })).reason, /Lv\s30/);
  assert.equal(gunOpen(g, prof({ player: { level: 30 } })).open, true);
});

test("prestige: Classic resets (token can keep a gun), Regular keeps everything", () => {
  const g = mini({ unlock: { level: 30, bp_tier: null } });
  const classic = { player: { level: 10, prestige: 1, prestigeType: "Classic" } };
  assert.equal(gunOpen(g, prof(classic)).open, false);
  assert.equal(gunOpen(g, prof({ ...classic, guns: { t1: { token: true } } })).open, true);
  assert.equal(gunOpen(g, prof({ player: { level: 10, prestige: 1, prestigeType: "Regular" } })).open, true);
});

test("Battle Pass gun: owned tick, empty tier = not locked, tier gates", () => {
  const g = mini({ unlock: { level: null, bp_tier: 16, note: "Battle Pass Tier 16" } });
  assert.equal(gunOpen(g, prof()).open, true);
  assert.equal(gunOpen(g, prof({ player: { bpTier: 10 } })).open, false);
  assert.match(gunOpen(g, prof({ player: { bpTier: 10 } })).reason, /tier 16/i);
  assert.equal(gunOpen(g, prof({ player: { bpTier: 16 } })).open, true);
  assert.equal(gunOpen(g, prof({ player: { bpTier: 3 }, guns: { t1: { owned: true } } })).open, true);
});

test("early build shows only below the level where the main build is ready", () => {
  const g = mini();
  g.builds.early = { label: "Early game", date: "2026-11-14", url: "e", complete_level: 14, notes: [],
    parts: [P("Muzzle", "M1", 10), P("Stock", "S0", 3)] };
  assert.equal(earlyView(g, prof(), miniData([g])), null);
  const low = earlyView(g, prof({ guns: { t1: { level: 5 } } }), miniData([g]));
  assert.ok(low);
  assert.equal(low.until, 14);
  assert.equal(earlyView(g, prof({ guns: { t1: { level: 45 } } }), miniData([g])), null);
});

test("buildView counts ready parts", () => {
  const g = mini();
  const v = buildView(g, "main", prof({ guns: { t1: { level: 10 } } }), miniData([g]));
  assert.equal(v.total, 3);
  assert.equal(v.ready, 1);
});

test("close modes use the close build when one is published", () => {
  const g = mini();
  const close = { ...g.builds.main, label: "Close Range" };
  g.builds.close = close;
  assert.equal(modeBuildKey({ build: "close" }, g), "close");
  assert.equal(modeBuildKey({ build: "mixed" }, g), "main");
  assert.equal(modeBuildKey({ build: "close" }, mini()), "main");
});

test("kit item locked at player level gets the first open stand-in from the slot list", () => {
  const mode = statics.modes.find((m) => m.id === "TDM");
  const gun = gunBy("m4");
  const k = kitFor(mode, gun, prof({ player: { level: 20 } }), data, statics);
  const perk1 = k.items.find((i) => i.slot === "Perk 1");
  assert.equal(perk1.name, "Ghost");
  assert.equal(perk1.state, "standin");
  assert.equal(perk1.standIn, "Quick Fix");
  const perk2 = k.items.find((i) => i.slot === "Perk 2");
  assert.equal(perk2.name, "Ninja");
  assert.equal(perk2.state, "standin");
});

test("permanent unlock token opens a kit item on a Classic prestige", () => {
  const mode = statics.modes.find((m) => m.id === "TDM");
  const gun = gunBy("m4");
  const p = prof({ player: { level: 10, prestige: 1, prestigeType: "Classic" }, tokens: { Ninja: true } });
  const ninja = kitFor(mode, gun, p, data, statics).items.find((i) => i.slot === "Perk 2");
  assert.equal(ninja.state, "ready");
});

test("kit with no level typed shows the plain kit", () => {
  const mode = statics.modes.find((m) => m.id === "TDM");
  const k = kitFor(mode, gunBy("m4"), prof(), data, statics);
  assert.ok(k.items.every((i) => i.state === "plain"));
});

test("Hardcore never swaps in Quick Fix", () => {
  const mode = statics.modes.find((m) => m.id === "Hardcore");
  const k = kitFor(mode, gunBy("m4"), prof({ player: { level: 4 } }), data, statics);
  assert.ok(k.items.every((i) => i.standIn !== "Quick Fix"));
});

test("SMG gets Ninja instead of Blood Rush; sniper keeps the stealth perks", () => {
  const mode = statics.modes.find((m) => m.id === "Frontline");
  assert.equal(kitFor(mode, gunBy("vel-46"), prof(), data, statics).items[1].name, "Ninja");
  const tdm = statics.modes.find((m) => m.id === "TDM");
  const sn = kitFor(tdm, gunBy("kg-7-vulcan"), prof(), data, statics).items;
  assert.deepEqual(sn.slice(0, 3).map((i) => i.name), ["Ghost", "Ninja", "Cold-Blooded"]);
});

test("ranking: every gun appears once, best first, locked guns last", () => {
  const mode = statics.modes.find((m) => m.id === "TDM");
  const ranked = rankGuns(mode, prof({ player: { level: 30 } }), data, statics);
  assert.equal(ranked.length, data.guns.length);
  assert.equal(new Set(ranked.map((r) => r.gun.slug)).size, data.guns.length);
  const firstClosed = ranked.findIndex((r) => !r.open.open);
  assert.ok(firstClosed > 0);
  assert.ok(ranked.slice(firstClosed).every((r) => !r.open.open));
  assert.equal(ranked[0].gun.slug, mode.head[0]);
});

test("ranking is by mode fit: close modes put an SMG above an LMG", () => {
  const mode = statics.modes.find((m) => m.id === "Hardpoint");
  const ranked = rankGuns(mode, prof(), data, statics).map((r) => r.gun);
  const rest = ranked.slice(mode.head.length);
  assert.ok(fitFor(mode, gunBy("ppsh-41"), statics) > fitFor(mode, gunBy("finn-lmg"), statics));
  assert.ok(rest.findIndex((g) => g.type === "SMG") < rest.findIndex((g) => g.type === "LMG"));
});

test("Miguel's one-time import fills only what he gave", () => {
  const p = importProfile(miguel);
  assert.equal(p.player.level, 47);
  assert.equal(p.player.prestige, 1);
  assert.equal(p.player.prestigeType, "Classic");
  assert.equal(p.player.bpTier, null);
  assert.equal(p.tokens.Ninja, true);
  assert.equal(p.guns.m4.level, 78);
  assert.equal(p.guns.m4.prestige, "master");
  assert.equal(p.guns["hyeon-burst"].level, 65);
  assert.equal(p.guns["hyeon-burst"].prestige, "1");
  assert.equal(p.guns["cronen-osprey"].level, 0);
  assert.equal(p.guns["cronen-osprey"].owned, true);
  assert.equal(p.guns["x-58-nyx"].level, 0);
  assert.equal(p.guns["kg-7-vulcan"].level, 54);
  assert.equal(p.guns["mosin-nagant"].level, 58);
  assert.equal(p.guns["csg-35"]?.level ?? null, null);
  for (const [slug, g] of Object.entries(p.guns)) assert.ok(gunBy(slug), slug);
});

test("card acceptance: KG-7 Vulcan at Lv 54 in TDM (pinned to the card's data of 2026-11-16)", () => {
  const kg = read("./fixtures/kg7-card-gun.json");
  const data = { guns: [kg], optics: {} };
  const tdm = statics.modes.find((m) => m.id === "TDM");
  const key = modeBuildKey(tdm, kg);
  assert.equal(key, "main");
  const p = prof({ guns: { "kg-7-vulcan": { level: 54 } } });
  const v = buildView(kg, key, p, data);
  const by = (slot) => v.parts.find((x) => x.slot === slot);
  assert.equal(by("Optic").name, "Schlager 7x");
  assert.equal(by("Optic").state, "ready");
  assert.equal(by("Barrel").name, 'TT Baem 12"');
  assert.equal(by("Stock").name, "Bruen KG-7 Mk. IV");
  assert.equal(by("Comb").name, "TT Type 40 Comb");
  const muzzle = by("Muzzle");
  assert.equal(muzzle.name, "Ivanov QR600");
  assert.equal(muzzle.state, "standin");
  assert.equal(muzzle.standIn.name, "Schlager Visiv-5");
  assert.match(muzzle.note, /Lv\s64/);
});

test("shipped data: no big scope, no invented levels, sources dated", () => {
  const big = new Set(["AR", "SMG", "LMG", "Marksman"]);
  for (const g of data.guns) {
    for (const [key, b] of Object.entries(g.builds)) {
      if (!b) continue;
      assert.ok(b.url && b.url.startsWith("https://"), `${g.slug} ${key} url`);
      assert.match(b.date ?? "", /^\d{4}-\d{2}-\d{2}$/, `${g.slug} ${key} date`);
      for (const p of b.parts) {
        assert.ok(p.level === null || Number.isInteger(p.level), `${g.slug} ${p.name} level`);
        if (p.slot === "Optic" && big.has(g.type)) {
          assert.equal(data.optics[p.name], "dot", `${g.slug} ${key} optic ${p.name}`);
        }
        if (p.stand_in) {
          assert.ok(Number.isInteger(p.stand_in.level), `${g.slug} stand-in level`);
          assert.notEqual(p.stand_in.slot, "Optic");
        }
      }
    }
  }
  const mosin = gunBy("mosin-nagant");
  for (const b of Object.values(mosin.builds)) if (b) assert.ok(!b.parts.some((p) => p.slot === "Optic"));
  assert.ok(data.checked);
  assert.equal(data.guns.length, read("../site/data/registry.json").guns.length);
});

test("every mode has a kit and head guns that exist", () => {
  const names = [
    "TDM", "Domination", "Hardpoint", "Kill Confirmed", "Free-for-All", "S&D", "Hijack", "Frontline", "Inflation",
    "Grind", "Drop Zone", "Ground War", "Infected", "Possession", "Hardcore",
  ];
  assert.deepEqual(statics.modes.map((m) => m.id), names);
  for (const m of statics.modes) {
    assert.ok(statics.kits[m.id], m.id);
    for (const h of m.head) assert.ok(gunBy(h), h);
  }
  assert.ok(statics.no_class.length >= 3);
  assert.equal(statics.modes.find((m) => m.id === "Hyeon") ?? null, null);
});

test("freshness: shows the check date, loud when stale or when the last run failed", async () => {
  const { freshness, dateText } = await import("../site/engine.js");
  assert.equal(dateText("2026-11-16"), "Nov 16, 2026");
  const ok = freshness({ checked: "2026-11-16", failed: [] }, "2026-11-17");
  assert.equal(ok.bad, false);
  assert.match(ok.text, /Data last checked Nov 16, 2026/);
  const stale = freshness({ checked: "2026-11-10", failed: [] }, "2026-11-17");
  assert.equal(stale.bad, true);
  assert.match(stale.text, /7 days ago/);
  const failed = freshness({ checked: "2026-11-16", failed: ["mar-9"] }, "2026-11-16");
  assert.equal(failed.bad, true);
  assert.match(failed.text, /mar-9/);
  assert.equal(freshness(null, "2026-11-16").bad, true);
});

test("Hyeon Burst keeps Miguel's IOTA-D pick", () => {
  const hb = gunBy("hyeon-burst");
  assert.ok(hb.builds.main.parts.some((p) => p.name === "IOTA-D"));
});
