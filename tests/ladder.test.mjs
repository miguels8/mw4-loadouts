// Q1 ladder (1 published early build -> 2 pro anchor + same-slot swap -> 3 calculated), never-empty, Q4 gate,
// next-upgrade line. Run: node --test tests/
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeProfile, setupAt, ladder, nextUpgrade, slotPick } from "../site/engine.js";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const prof = (o = {}) => normalizeProfile(o);
const at = (lv) => prof({ guns: { t1: { level: lv } } });

const cand = (name, level, extra = {}) => ({ name, level, ...extra });
function fixture({ gate = true } = {}) {
  const variant = {
    id: "t1-versatile-aaaaaa", type: "Versatile", label: "Versatile", best_for: ["TDM"], date: "2026-11-16", agree: 1,
    sources: [{ site: "CODMunity", name: "Versatile", date: "2026-11-16", url: "u" }],
    parts: [{ slot: "Barrel", name: "Own Barrel", level: 40 }, { slot: "Muzzle", name: "Own Muzzle", level: 50 },
      { slot: "Stock", name: "Own Stock", level: 8 }],
    alternatives: [], apex_on: false, site_kit: null, notes: [], source_text: null,
  };
  const gun = {
    slug: "t1", name: "Test One", type: "AR", tier: "A", unlock: { level: null, bp_tier: null }, max_level: 60,
    apex: null, table: {}, calc_gate: { pass: gate, matched: gate ? 5 : 2, of: 5, profile: "range", reason: null },
    builds: { main: null, close: null, early: null },
    published: [{ site: "Infil", label: "Early game", complete_level: 19, date: "2026-11-14", url: "u",
      parts: [{ slot: "Barrel", name: "Early Barrel", level: 10 }] }],
    variants: [variant],
    cands: {
      Barrel: [cand("Early Barrel", 10, { used: 1, types: ["Early game"] }), cand("Swap Barrel", 20, { used: 3, types: ["Versatile"] }),
        cand("Own Barrel", 40, { used: 1, types: ["Versatile"] })],
      Muzzle: [cand("Plain Muzzle", 3, gate ? { score: { close: 1, range: 1 } } : {}),
        cand("Calc Muzzle", 25, gate ? { score: { close: 4, range: 9 } } : {}), cand("Own Muzzle", 50, { used: 1, types: ["Versatile"] })],
      Stock: [cand("Own Stock", 8, { used: 1, types: ["Versatile"] })],
    },
  };
  return { gun, variant, data: { guns: [gun], optics: {} } };
}
const nameAt = (f, lv, slot, profile = "range") =>
  setupAt(f.gun, f.variant, lv, prof({ guns: { t1: { level: lv } } }), f.data, profile).picks.find((p) => p.slot === slot);

test("ladder order 1 then 2 then 3, and the variant's own part at its unlock level", () => {
  const f = fixture();
  // Barrel: nothing open at Lv 5, the early build's part at Lv 10-19 (step 1), a same-slot swap at Lv 20 (step 2), own at Lv 40
  assert.equal(nameAt(f, 5, "Barrel").state, "locked");
  assert.deepEqual([nameAt(f, 10, "Barrel").label, nameAt(f, 10, "Barrel").step], ["Use Early Barrel for now", 1]);
  assert.equal(nameAt(f, 19, "Barrel").step, 1);
  assert.deepEqual([nameAt(f, 20, "Barrel").label, nameAt(f, 20, "Barrel").step], ["Use Swap Barrel for now", 2]);
  assert.equal(nameAt(f, 39, "Barrel").step, 2);
  assert.deepEqual([nameAt(f, 40, "Barrel").label, nameAt(f, 40, "Barrel").step], ["Own Barrel", 0]);
  // Muzzle has no used part but its own: the gate passed, so calculation (step 3) picks the best open part
  assert.deepEqual([nameAt(f, 3, "Muzzle").label, nameAt(f, 3, "Muzzle").step], ["Use Plain Muzzle for now", 3]);
  assert.deepEqual([nameAt(f, 25, "Muzzle").label, nameAt(f, 25, "Muzzle").step], ["Use Calc Muzzle for now", 3]);
  assert.equal(nameAt(f, 50, "Muzzle").step, 0);
});

test("Q4 gate respected: a gun that failed the gate never gets a calculated pick", () => {
  const f = fixture({ gate: false });
  const steps = new Set();
  for (let lv = 0; lv <= 60; lv += 1) for (const p of setupAt(f.gun, f.variant, lv, at(lv), f.data, "range").picks) steps.add(p.step);
  assert.ok(!steps.has(3));
  // without calculation the Muzzle slot falls to a real, open, published part of that slot: the filler (step 4b)
  const m = nameAt(f, 25, "Muzzle");
  assert.equal(m.step, "4b");
  assert.equal(m.name, "Plain Muzzle");
  assert.match(m.note, /Filler: no meta part open yet/);
});

test("never empty: every slot at every ladder step has a usable part when the table has any open part for it", () => {
  for (const gate of [true, false]) {
    const f = fixture({ gate });
    for (let lv = 0; lv <= 60; lv += 1) {
      for (const p of setupAt(f.gun, f.variant, lv, at(lv), f.data, "range").picks) {
        const openAny = (f.gun.cands[p.slot] ?? []).some((c) => c.level !== null && c.level <= lv);
        if (openAny) assert.notEqual(p.state, "locked", `${p.slot} at Lv ${lv} (gate ${gate})`);
        else assert.equal(p.state, "locked", `${p.slot} at Lv ${lv}`);
        assert.ok(p.label);
      }
    }
  }
});

test("review r1 F1: an own part with no published level never hides an open part of that slot", () => {
  const f = fixture();
  f.variant.parts[0] = { slot: "Barrel", name: "Mystery Barrel", level: null };
  const own = f.variant.parts[0];
  // an open candidate exists: it is offered, the unknown level stays null and is named in the note
  const p = slotPick(f.gun, f.variant, own, 10, at(10), f.data, "range");
  assert.equal(p.name, "Early Barrel");
  assert.equal(p.step, 1);
  assert.match(p.note, /Mystery Barrel \(level not published\)/);
  // nothing open in the slot at all: the honest unknown row, never a guess
  const q = slotPick(f.gun, f.variant, own, 5, at(5), f.data, "range");
  assert.deepEqual([q.state, q.name, q.note], ["unknown", "Mystery Barrel", "Level not published"]);
  // the ladder still moves on a level that opens a substitute
  const lad = ladder(f.gun, f.variant, at(1), f.data, "range");
  assert.ok(lad.some((s) => s.changes.some((c) => c.slot === "Barrel" && c.to === "Early Barrel")));
});

test("a locked slot says when its part opens; nothing is invented", () => {
  const f = fixture();
  const p = nameAt(f, 2, "Barrel");
  assert.equal(p.state, "locked");
  assert.match(p.note, /Opens at Lv\s40/);
});

test("ladder lists each change once, in level order, with from and to", () => {
  const f = fixture();
  const lad = ladder(f.gun, f.variant, prof({ guns: { t1: { level: 1 } } }), f.data, "range");
  const levels = lad.map((s) => s.level);
  assert.deepEqual(levels, [...levels].sort((a, b) => a - b));
  const barrelChanges = lad.flatMap((s) => s.changes.filter((c) => c.slot === "Barrel").map((c) => [s.level, c.from, c.to]));
  assert.deepEqual(barrelChanges, [[10, null, "Early Barrel"], [20, "Early Barrel", "Swap Barrel"], [40, "Swap Barrel", "Own Barrel"]]);
  assert.ok(lad.every((s, i) => i === 0 || s.changes.length > 0));
});

test("next upgrade line: swap, several changes at one level, final build", () => {
  const f = fixture();
  const lad = ladder(f.gun, f.variant, at(1), f.data, "range");
  assert.equal(nextUpgrade(lad, 10, f.gun, f.variant), "Next upgrade at Lv 20: swap Early Barrel -> Swap Barrel");
  assert.equal(nextUpgrade(lad, 3, f.gun, f.variant), "Next upgrade at Lv 8: add Own Stock");
  assert.equal(nextUpgrade(lad, 8, f.gun, f.variant), "Next upgrade at Lv 10: add Early Barrel");
  assert.match(nextUpgrade(lad, 25, f.gun, f.variant), /^Next upgrade at Lv 40: swap Swap Barrel -> Own Barrel$/);
  assert.equal(nextUpgrade(lad, 60, f.gun, f.variant), "Final build reached");
  assert.equal(nextUpgrade(lad, null, f.gun, f.variant), null);
});

test("next upgrade joins several changes at the same level with ;", () => {
  const f = fixture();
  f.gun.cands.Stock = [cand("Own Stock", 30, { used: 1, types: ["Versatile"] }), cand("Early Stock", 30, { used: 2, types: ["Versatile"] })];
  f.variant.parts[2] = { slot: "Stock", name: "Own Stock", level: 30 };
  f.gun.cands.Muzzle = [cand("Own Muzzle", 30, { used: 1, types: ["Versatile"] })];
  f.variant.parts[1] = { slot: "Muzzle", name: "Own Muzzle", level: 30 };
  const lad = ladder(f.gun, f.variant, at(1), f.data, "range");
  const txt = nextUpgrade(lad, 25, f.gun, f.variant);
  assert.match(txt, /^Next upgrade at Lv 30: add Early Stock; add Own Muzzle$|^Next upgrade at Lv 30: .*; .*$/);
});

test("apex at max level when the final step is the Apex", () => {
  const f = fixture();
  f.variant.apex_on = true;
  f.gun.apex = { name: "Apex T", level: 60 };
  const lad = ladder(f.gun, f.variant, at(1), f.data, "range");
  assert.equal(nextUpgrade(lad, 55, f.gun, f.variant), "Apex at max level 60");
});

test("KG-7 Vulcan golden: the build and next upgrade at Lv 54 from the live data snapshot", () => {
  const snap = read("./fixtures/kg7-variants-gun.json");
  const profile = prof({ guns: { "kg-7-vulcan": { level: 54 } } });
  const data = { guns: [snap.gun], optics: snap.optics };
  const v = snap.gun.variants.find((x) => x.id === snap.variant_id);
  const lad = ladder(snap.gun, v, profile, data, "range");
  assert.equal(nextUpgrade(lad, 54, snap.gun, v), snap.next_upgrade_at_54);
  const picks = setupAt(snap.gun, v, 54, profile, data, "range").picks;
  assert.equal(picks.length, v.parts.length);
  assert.ok(picks.every((p) => p.label));
});

test("slotPick for an own open part is step 0 and ready", () => {
  const f = fixture();
  const p = slotPick(f.gun, f.variant, f.variant.parts[2], 8, at(8), f.data, "range");
  assert.deepEqual([p.step, p.state, p.icon], [0, "ready", "✅"]);
});
