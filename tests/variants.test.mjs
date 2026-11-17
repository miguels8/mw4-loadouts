// Variant buttons: default variant per mode, perk override and "Site uses", 24 h staleness, ranking. Run: node --test tests/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeProfile, variantsFor, defaultVariant, kitFor, freshness, rankGuns, variantView } from "../site/engine.js";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const statics = read("../site/data/static.json");
const mode = (id) => statics.modes.find((m) => m.id === id);
const prof = (o = {}) => normalizeProfile(o);

const V = (id, type, best_for, extra = {}) => ({
  id, type, label: type, best_for, date: "2026-11-16", agree: 1, sources: [{ site: "MW4 Intel", name: id, date: "2026-11-16", url: "u" }],
  parts: [{ slot: "Muzzle", name: `${id}-m`, level: 5 }, { slot: "Barrel", name: `${id}-b`, level: 6 }, { slot: "Stock", name: `${id}-s`, level: 7 },
    { slot: "Laser", name: `${id}-l`, level: 8 }, { slot: "Underbarrel", name: `${id}-u`, level: 9 }],
  alternatives: [], apex_on: false, site_kit: null, notes: [], source_text: null, ...extra,
});
const gun = (slug, type, variants, extra = {}) => ({
  slug, name: slug.toUpperCase(), type, tier: "S", unlock: { level: null, bp_tier: null }, max_level: 70, apex: null, table: {},
  builds: { main: null, close: null, early: null }, published: [], cands: {}, calc_gate: { pass: false, matched: 0, of: 5, profile: "range", reason: "x" },
  variants, ...extra,
});

const m4 = () => gun("m4", "AR", [
  V("m4-close", "Close Range", ["Hardpoint", "Hijack", "Kill Confirmed"]),
  V("m4-vers", "Versatile", ["TDM", "Frontline"], { agree: 2 }),
  V("m4-long", "Long Range", ["S&D", "Ground War", "Domination"]),
]);

test("the default variant differs between Hardpoint and S&D on an M4", () => {
  const g = m4();
  assert.equal(defaultVariant(mode("Hardpoint"), g, statics).id, "m4-close");
  assert.equal(defaultVariant(mode("S&D"), g, statics).id, "m4-long");
  assert.equal(defaultVariant(mode("TDM"), g, statics).id, "m4-vers");
});

test("default variant: ties prefer the type for the mode, then more sites, then newest; no match falls back by mode kind", () => {
  const g = gun("x", "AR", [
    V("a", "Versatile", ["Hardpoint"], { agree: 3 }), V("b", "Close Range", ["Hardpoint"], { agree: 1 }),
  ]);
  assert.equal(defaultVariant(mode("Hardpoint"), g, statics).id, "b");          // close mode: Close Range type first
  assert.equal(defaultVariant(mode("TDM"), g, statics).id, "a");                // nothing lists TDM: Versatile for a mixed mode
  const h = gun("y", "AR", [V("c", "Versatile", ["TDM"], { date: "2026-11-10" }), V("d", "Long Range", ["TDM"], { date: "2026-11-12" })]);
  assert.equal(defaultVariant(mode("Hardpoint"), h, statics).id, "c");          // no Close Range exists: Versatile then newest
  const e = gun("z", "AR", [V("p", "Pro (Ranked)", ["Hardpoint"], { agree: 1 }), V("q", "Close Range", ["Hardpoint"], { agree: 1 })]);
  assert.equal(defaultVariant(mode("Hardpoint"), e, statics).id, "q");
  assert.equal(defaultVariant(mode("TDM"), gun("none", "AR", []), statics), null);
});

test("a page the site wrote for exactly this mode opens first", () => {
  const g = gun("w", "AR", [
    V("pro", "Pro (Ranked)", ["Hardpoint", "S&D"]),
    V("snd", "Close Range", ["S&D", "Hardpoint"], { best_for_source: "mode" }),
    V("long", "Long Range", ["S&D"]),
  ]);
  assert.equal(defaultVariant(mode("S&D"), g, statics).id, "snd");
  assert.equal(defaultVariant(mode("Hardpoint"), g, statics).id, "snd");        // its list starts with S&D, so for Hardpoint the type rule decides
});

test("variantsFor reads gun.variants and is empty for a legacy gun", () => {
  assert.equal(variantsFor(m4()).length, 3);
  assert.deepEqual(variantsFor({ builds: {} }), []);
});

const miniData = (guns) => ({ guns, optics: {} });
const names = (k) => k.items.map((i) => i.label);

test("perk override: a sniper variant gets Ghost, Ninja, Cold-Blooded and 'Site uses' on the differing perk", () => {
  const g = m4();
  const v = V("m4-snipe", "Long Range", ["S&D"], { site_kit: { perk1: "Ghost", perk2: "Fast Hands", perk3: "Cold-Blooded", lethal: "Frag Grenade" } });
  const k = kitFor(mode("TDM"), g, prof(), miniData([g]), statics, v);
  assert.deepEqual(names(k).slice(0, 3), ["Ghost", "Ninja", "Cold-Blooded"]);
  assert.equal(k.items[0].siteUses ?? null, null);                  // same as ours: nothing to show
  assert.equal(k.items[1].siteUses, "Fast Hands");                   // ours wins, the site's pick is shown
  assert.match(k.items[1].note, /Site uses: Fast Hands/);
  assert.match(k.why, /Ghost, Ninja, Cold-Blooded/);
});

test("rush variant: Ninja replaces Blood Rush, but not in Hijack", () => {
  const g = m4();
  const rush = V("m4-rush", "Close Range", ["Hardpoint"]);
  const hp = kitFor(mode("Hardpoint"), g, prof(), miniData([g]), statics, rush);
  const base = statics.kits.Hardpoint;
  if (base.perk2 === "Blood Rush") assert.equal(names(hp)[1], "Ninja");
  const hj = kitFor(mode("Hijack"), g, prof(), miniData([g]), statics, rush);
  assert.equal(names(hj)[1], statics.kits.Hijack.perk2);
  // our long/marksman rules from the gun type still hold with a variant
  const mg = gun("mosin", "Marksman", [V("mo", "Versatile", ["TDM"])]);
  assert.equal(names(kitFor(mode("TDM"), mg, prof(), miniData([mg]), statics, mg.variants[0]))[0], statics.marksman_kit[0]);
});

test("kitFor without a variant behaves as before", () => {
  const g = m4();
  const a = kitFor(mode("TDM"), g, prof(), miniData([g]), statics);
  assert.deepEqual(names(a).slice(0, 3), [statics.kits.TDM.perk1, statics.kits.TDM.perk2, statics.kits.TDM.perk3]);
});

test("staleness banner: 23 h ok, 25 h bad, a failed list bad, nothing bad", () => {
  const now = "2026-11-17T12:00:00Z";
  assert.equal(freshness({ checked_at: "2026-11-16T13:00:00Z", failed: [] }, now).bad, false);
  const old = freshness({ checked_at: "2026-11-16T11:00:00Z", failed: [] }, now);
  assert.equal(old.bad, true);
  assert.match(old.text, /25 h/);
  const failed = freshness({ checked_at: "2026-11-17T11:00:00Z", failed: ["mar-9"] }, now);
  assert.equal(failed.bad, true);
  assert.match(failed.text, /mar-9/);
  assert.equal(freshness(null, now).bad, true);
  assert.equal(freshness({ failed: [] }, now).bad, true);
  assert.equal(freshness({ checked: "2026-11-17", failed: [] }, now).bad, false);        // date only: counts from 00:00Z, 12 h old
  assert.equal(freshness({ checked: "2026-11-16", failed: [] }, now).bad, true);         // 36 h
  assert.equal(freshness({ checked_at: "2026-11-17T11:30:00Z", failed: [] }, now).bad, false);
  assert.equal(freshness({ checked_at: "2026-11-17T11:30:00Z", failed: [] }, "garbage").bad, true);
});

test("a gun with no variants ranks after every gun that has one; legacy data is not penalised", () => {
  const withV = gun("aa", "AR", [V("aa-v", "Versatile", ["TDM"])], { tier: "D" });
  const none = gun("zz", "AR", [], { tier: "S" });
  const rows = rankGuns(mode("TDM"), prof(), { guns: [none, withV], optics: {} }, statics);
  assert.deepEqual(rows.map((r) => r.gun.slug), ["aa", "zz"]);
  const legacy = { ...gun("lg", "AR", undefined), variants: undefined };
  delete legacy.variants;
  legacy.builds = { main: { label: "Versatile", date: "2026-11-01", url: "u", apex_on: false, notes: [], parts: [{ slot: "Muzzle", name: "M", level: 1, stand_in: null }] }, close: null, early: null };
  const r2 = rankGuns(mode("TDM"), prof(), { guns: [legacy], optics: {} }, statics);
  assert.equal(r2[0].gun.slug, "lg");
});

test("variantView shows the variant's setup at the typed level with ready counts", () => {
  const g = m4();
  const d = miniData([g]);
  const view = variantView(g, g.variants[0], prof({ guns: { m4: { level: 7 } } }), d, mode("Hardpoint"));
  assert.equal(view.total, 5);
  assert.equal(view.ready, 3);          // Muzzle 5, Barrel 6, Stock 7 are open at Lv 7
  assert.equal(view.picks.length, 5);
});
