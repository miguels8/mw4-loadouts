// Engine side of the per-card level controls: edit helpers, header text, and what a level or prestige edit does.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  normalizeProfile, setGun, stepLevel, gunBadges, buildView, earlyView, rankGuns, partStatus, setupAt, LEVEL_MAX,
} from "../site/engine.js";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const statics = read("../site/data/static.json");
const kg = read("./fixtures/kg7-card-gun.json");
const prof = (o = {}) => normalizeProfile(o);

test("setGun stores the level, never mutates the old profile, and keeps empty as not entered", () => {
  const p0 = prof({ guns: { "kg-7-vulcan": { level: 63 } } });
  const p1 = setGun(p0, "kg-7-vulcan", { level: 64 });
  assert.equal(p1.guns["kg-7-vulcan"].level, 64);
  assert.equal(p0.guns["kg-7-vulcan"].level, 63);
  assert.equal(setGun(p1, "kg-7-vulcan", { level: "" }).guns["kg-7-vulcan"].level, null);
  assert.equal(setGun(p1, "kg-7-vulcan", { level: "abc" }).guns["kg-7-vulcan"].level, null);
  assert.equal(setGun(p1, "kg-7-vulcan", { level: "0" }).guns["kg-7-vulcan"].level, 0);
  const fresh = setGun(prof(), "m4", { level: 12 });
  assert.equal(fresh.guns.m4.level, 12);
  assert.equal(fresh.guns.m4.prestige, "");
});

test("setGun keeps the other fields and accepts prestige values from the dropdown", () => {
  const p = setGun(prof({ guns: { m4: { level: 40, owned: true, token: true, max: 72 } } }), "m4", { prestige: "master" });
  assert.deepEqual(p.guns.m4, { level: 40, prestige: "master", owned: true, token: true, max: 72 });
  assert.equal(setGun(p, "m4", { prestige: "3" }).guns.m4.prestige, "3");
  assert.equal(setGun(p, "m4", { prestige: "" }).guns.m4.prestige, "");
  assert.equal(setGun(p, "m4", { prestige: "None" }).guns.m4.prestige, "");
});

test("stepLevel: empty + goes to 1, empty - stays empty, bounded at 1 and the max", () => {
  assert.equal(stepLevel(null, +1), 1);
  assert.equal(stepLevel(null, -1), null);
  assert.equal(stepLevel(63, +1), 64);
  assert.equal(stepLevel(64, -1), 63);
  assert.equal(stepLevel(1, -1), 1);
  assert.equal(stepLevel(0, +1), 1);
  assert.equal(stepLevel(LEVEL_MAX, +1), LEVEL_MAX);
  assert.equal(stepLevel(10, +5), 15);
});

test("gunBadges: header text is Lv N or Lv ?, plus the prestige badge", () => {
  const p = prof({ guns: { a: { level: 54 }, b: { level: 0 }, c: { level: 12, prestige: "3" }, d: { level: 70, prestige: "master" } } });
  assert.deepEqual(gunBadges(p, "a"), { level: "Lv 54", prestige: "" });
  assert.deepEqual(gunBadges(p, "b"), { level: "Lv 0", prestige: "" });
  assert.deepEqual(gunBadges(p, "zzz"), { level: "Lv ?", prestige: "" });
  assert.deepEqual(gunBadges(p, "c"), { level: "Lv 12", prestige: "P3" });
  assert.deepEqual(gunBadges(p, "d"), { level: "Lv 70", prestige: "Master" });
});

test("KG-7 Vulcan 63 -> 64 flips the muzzle from 'add Visiv-5 for now' to ready Ivanov QR600", () => {
  const data = { guns: [kg], optics: {} };
  const muzzle = (p) => buildView(kg, "main", p, data).parts.find((x) => x.slot === "Muzzle");
  const p63 = setGun(prof(), "kg-7-vulcan", { level: 63 });
  assert.equal(muzzle(p63).state, "standin");
  assert.match(muzzle(p63).label, /Add Schlager Visiv-5 \(laser\) for now/);
  const p64 = setGun(p63, "kg-7-vulcan", { level: 64 });
  assert.equal(muzzle(p64).state, "ready");
  assert.equal(muzzle(p64).label, "Ivanov QR600");
  assert.equal(buildView(kg, "main", p64, data).ready, buildView(kg, "main", p63, data).ready + 1);
  // clearing the level goes back to "not entered": plain parts, no lock, no ready count
  const none = setGun(p64, "kg-7-vulcan", { level: "" });
  assert.equal(muzzle(none).state, "plain");
});

test("the early build appears below the threshold and disappears above it", () => {
  const g = read("../site/data/weapons.json").guns.find((x) => x.builds.early);
  const data = { guns: [g], optics: {} };
  const main = g.builds.main.parts.filter((p) => p.level !== null);
  const top = Math.max(...main.map((p) => p.level));
  assert.equal(earlyView(g, prof(), data), null, "not entered: no early build");
  assert.ok(earlyView(g, setGun(prof(), g.slug, { level: 1 }), data));
  assert.equal(earlyView(g, setGun(prof(), g.slug, { level: top }), data), null);
});

test("weapon prestige relocks parts that were open only through another gun", () => {
  const real = read("../site/data/weapons.json");
  let found = null;
  for (const g of real.guns) for (const part of g.builds.main.parts) {
    for (const o of real.guns) {
      const e = o.table?.[part.name];
      if (o.slug !== g.slug && e && e[0] === part.slot && Number.isInteger(e[1]) && ["Muzzle", "Underbarrel", "Laser", "Optic", "Rear Grip"].includes(part.slot) && part.level > 1) found ??= { g, part, o, lv: e[1] };
    }
  }
  assert.ok(found, "data has at least one shared part");
  const { g, part, o, lv } = found;
  const base = setGun(setGun(prof(), o.slug, { level: lv }), g.slug, { level: 1 });
  assert.equal(partStatus(g, part, base, real).state, "ready");
  const pres = setGun(base, g.slug, { prestige: "1" });
  assert.notEqual(partStatus(g, part, pres, real).state, "ready");
});

test("an edit re-ranks: a gun's ready count feeds the mode ranking", () => {
  const real = read("../site/data/weapons.json");
  const mode = statics.modes.find((m) => m.id === "TDM");
  const before = rankGuns(mode, prof({ player: { level: 80 } }), real, statics);
  const slug = before[before.length - 1].gun.slug;
  const g = real.guns.find((x) => x.slug === slug);
  const max = Math.max(...g.builds.main.parts.map((p) => p.level ?? 0));
  const p = setGun(prof({ player: { level: 80 } }), slug, { level: max });
  const row = rankGuns(mode, p, real, statics).find((r) => r.gun.slug === slug);
  const expect = row.variant ? setupAt(g, row.variant, p.guns[slug].level, p, real, mode).ready : buildView(g, row.key, p, real).ready;
  assert.equal(row.ready, expect);
});
