// Real-browser test (Chromium at 390 px) of the level and prestige controls on each gun card.
// The data is pinned: KG-7 Vulcan comes from tests/fixtures/kg7-card-gun.json so the 63 -> 64 case never drifts with the daily refresh.
// Needs Chromium or Chrome (CHROME=/path overrides); without one the test is skipped loudly.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { findChrome, serve, launch, sleep } from "./tools/cdp.mjs";
import { normalizeProfile, buildView, earlyView, rankGuns } from "../site/engine.js";

const site = process.env.SITE_DIR ?? fileURLToPath(new URL("../site/", import.meta.url)); // SITE_DIR lets a RED run point at an older copy of the site
const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const weapons = read("../site/data/weapons.json");
const statics = read("../site/data/static.json");
const kg = read("./fixtures/kg7-card-gun.json");
const data = { ...weapons, guns: weapons.guns.map((g) => (g.slug === kg.slug ? kg : g)) };
const chrome = findChrome();
const KG = "kg-7-vulcan";
const card = (slug) => `details[data-slug="${slug}"]`;
const tdm = statics.modes.find((m) => m.id === "TDM");

test("card level and prestige controls (real Chromium, 390 px)", { skip: chrome ? false : "no Chromium or Chrome found (set CHROME=)", timeout: 120000 }, async (t) => {
  const srv = await serve(site, { "/data/weapons.json": data });
  const b = await launch(chrome);
  try {
    const J = (s) => b.evalJs(s);
    const stored = async () => normalizeProfile(JSON.parse((await J(`localStorage.getItem("mw4-loadouts-v1")`)) ?? "{}").profile);
    const cardText = (slug) => J(`document.querySelector('${card(slug)}').innerText`);
    const head = (slug) => J(`document.querySelector('${card(slug)} summary').innerText`);
    const order = () => J(`[...document.querySelectorAll("details.gun")].map((d) => d.dataset.slug)`);
    const waitFor = async (expr, what) => { for (let i = 0; i < 40; i++) { if (await J(expr)) return; await sleep(100); } assert.fail("timeout: " + what); };
    const readyCount = async (slug) => /(\d+)\/(\d+) ready/.exec(await head(slug)).slice(1).map(Number);
    const typeLevel = (slug, v) => J(`(() => { const i = document.querySelector('${card(slug)} input[data-cl="level"]'); i.value = "${v}"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    const pick = (slug, v) => J(`(() => { const s = document.querySelector('${card(slug)} select[data-cl="prestige"]'); s.value = "${v}"; s.dispatchEvent(new Event("change", { bubbles: true })); })()`);
    const tab = async (v) => { await J(`document.querySelector("[data-view=${v}]").click()`); await sleep(250); };
    const reopen = (slug) => J(`document.querySelector('${card(slug)}').open = true`);

    await b.goto(srv.url);
    await J(`localStorage.clear()`);
    await b.goto(srv.url);
    await waitFor(`!!document.querySelector('${card(KG)}')`, "cards drawn");
    await reopen(KG);

    await t.test("every card has the control row; targets are thumb sized; fits 390 px", async () => {
      assert.equal(await J(`document.querySelectorAll("details.gun").length`), data.guns.length);
      const ok = await J(`[...document.querySelectorAll("details.gun")].every((d) => d.querySelector(".ctl [data-step='-1']") && d.querySelector(".ctl [data-step='1']") && d.querySelector(".ctl input[data-cl='level']") && d.querySelector(".ctl select[data-cl='prestige']"))`);
      assert.ok(ok, "every gun card has -, +, level input and prestige select");
      const sizes = await J(`["[data-step='-1']", "[data-step='1']", "input[data-cl='level']", "select[data-cl='prestige']"].map((s) => { const r = document.querySelector('${card(KG)} .ctl ' + s).getBoundingClientRect(); return [r.width, r.height]; })`);
      for (const [w, h] of sizes) assert.ok(w >= 44 && h >= 44, `target ${w}x${h} is under 44 px`);
      assert.ok((await J(`document.documentElement.scrollWidth`)) <= 390, "no sideways scroll");
      const opts = await J(`[...document.querySelector('${card(KG)} select[data-cl="prestige"]').options].map((o) => o.text)`);
      assert.deepEqual(opts, ["None", ...Array.from({ length: 10 }, (_, i) => `Prestige ${i + 1}`), "Master"]);
    });

    await t.test("empty is 'Set level' and 'Lv ?', never 0", async () => {
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "");
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').placeholder`), "Set level");
      assert.match(await head(KG), /Lv \?/);
      await b.tapFast(`${card(KG)} [data-step="-1"]`);
      assert.equal((await stored()).guns[KG]?.level ?? null, null, "minus on empty stays empty");
      assert.match(await head(KG), /Lv \?/);
    });

    await t.test("typing 63 saves, updates the header and shows 'add Visiv-5 for now'", async () => {
      await typeLevel(KG, 63);
      assert.equal((await stored()).guns[KG].level, 63);
      assert.match(await cardText(KG), /Add Schlager Visiv-5 \(laser\) for now/);
      assert.match(await head(KG), /Lv 63/);
    });

    await t.test("tapping + (63 -> 64) flips the muzzle to ready and raises the ready count", async () => {
      const before = await readyCount(KG);
      await b.tapFast(`${card(KG)} [data-step="1"]`);
      assert.equal((await stored()).guns[KG].level, 64);
      assert.doesNotMatch(await cardText(KG), /Add Schlager Visiv-5/);
      assert.ok(await J(`[...document.querySelectorAll('${card(KG)} li.s-ready .pname')].some((n) => n.textContent === "Ivanov QR600")`), "QR600 is ready");
      assert.equal((await readyCount(KG))[0], before[0] + 1);
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "64");
      assert.match(await head(KG), /Lv 64/);
    });

    await t.test("the card and the engine agree on the ready count after the edit", async () => {
      const v = buildView(kg, "main", await stored(), data);
      assert.deepEqual(await readyCount(KG), [v.ready, v.total]);
    });

    await t.test("My levels shows the same level, and edits flow both ways", async () => {
      await tab("levels");
      assert.equal(await J(`document.querySelector('[data-gun="${KG}"] [data-f=level]').value`), "64");
      await J(`(() => { const i = document.querySelector('[data-gun="${KG}"] [data-f=level]'); i.value = "70"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      await tab("loadouts");
      await reopen(KG);
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "70");
      assert.match(await head(KG), /Lv 70/);
      await b.tapFast(`${card(KG)} [data-step="-1"]`);
      await tab("levels");
      assert.equal(await J(`document.querySelector('[data-gun="${KG}"] [data-f=level]').value`), "69");
      await tab("loadouts");
      await reopen(KG);
    });

    await t.test("prestige dropdown saves, shows the badge, and the parts follow the engine", async () => {
      await pick(KG, "master");
      assert.equal((await stored()).guns[KG].prestige, "master");
      assert.match(await head(KG), /Master/);
      assert.equal(await J(`document.querySelector('${card(KG)} select[data-cl="prestige"]').value`), "master");
      const v = buildView(kg, "main", await stored(), data);
      assert.deepEqual(await readyCount(KG), [v.ready, v.total]);
      await pick(KG, "3");
      assert.match(await head(KG), /P3/);
      await pick(KG, "");
      assert.doesNotMatch(await head(KG), /P3|Master/);
    });

    await t.test("an edit re-ranks the whole list the same way the engine does", async () => {
      const slug = (await order()).at(-1);
      await reopen(slug);
      await typeLevel(slug, 200);
      const expect = rankGuns(tdm, await stored(), data, statics).map((r) => r.gun.slug);
      assert.deepEqual(await order(), expect);
      assert.deepEqual(await J(`[...document.querySelectorAll("details.gun .rank")].map((n) => n.textContent)`), expect.map((_, i) => String(i + 1)));
      assert.equal(await J(`document.querySelector('${card(slug)} input[data-cl="level"]').value`), "200");
    });

    await t.test("the early build appears at a low level and goes away at a high level", async () => {
      const g = data.guns.find((x) => x.builds.early && x.slug !== KG);
      await reopen(g.slug);
      await typeLevel(g.slug, 1);
      assert.match(await cardText(g.slug), /While you level up/);
      assert.ok(earlyView(g, await stored(), data));
      await typeLevel(g.slug, 200);
      assert.doesNotMatch(await cardText(g.slug), /While you level up/);
    });

    await t.test("holding + repeats and stops on release", async () => {
      await typeLevel(KG, 10);
      const [x, y] = await b.press(`${card(KG)} [data-step="1"]`);
      for (let i = 0; i < 100 && (await stored()).guns[KG].level < 16; i++) await sleep(100); // a loaded machine delays the 450 ms hold timer
      await b.release(x, y);
      const held = (await stored()).guns[KG].level;
      assert.ok(held >= 14, `hold raised 10 to ${held}`);
      await sleep(500);
      assert.equal((await stored()).guns[KG].level, held, "stops after release");
    });

    await t.test("typing in the focused box then pressing + uses the typed number (review r1 F1 A)", async () => {
      await typeLevel(KG, "");
      await J(`(() => { const i = document.querySelector('${card(KG)} input[data-cl="level"]'); i.focus(); i.value = "63"; i.dispatchEvent(new Event("input", { bubbles: true })); })()`);
      await b.tapFast(`${card(KG)} [data-step="1"]`);
      assert.equal((await stored()).guns[KG].level, 64, "typed 63 then + saves 64, not 1");
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "64");
      assert.match(await head(KG), /Lv 64/);
    });

    await t.test("the number box always shows the saved level, even while focused (review r1 F1 B)", async () => {
      await J(`(() => { const i = document.querySelector('${card(KG)} input[data-cl="level"]'); i.focus(); i.value = "63"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      await b.tapFast(`${card(KG)} [data-step="1"]`);
      await b.tapFast(`${card(KG)} [data-step="1"]`);
      assert.equal((await stored()).guns[KG].level, 65);
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "65");
      assert.match(await head(KG), /Lv 65/);
    });

    await t.test("out-of-range typing is normalised in the box, the profile and the header (review r1 F1 C)", async () => {
      await J(`(() => { const i = document.querySelector('${card(KG)} input[data-cl="level"]'); i.focus(); i.value = "999"; i.dispatchEvent(new Event("change", { bubbles: true })); i.blur(); })()`);
      assert.equal((await stored()).guns[KG].level, 200);
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "200");
      assert.match(await head(KG), /Lv 200/);
      await J(`(() => { const i = document.querySelector('${card(KG)} input[data-cl="level"]'); i.value = "-5"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      assert.equal(await J(`document.querySelector('${card(KG)} input[data-cl="level"]').value`), "0");
      await tab("levels");
      await J(`(() => { const i = document.querySelector('[data-gun="${KG}"] [data-f=level]'); i.value = "999"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      assert.equal(await J(`document.querySelector('[data-gun="${KG}"] [data-f=level]').value`), "200", "My levels shows the clamped value too");
      await tab("loadouts");
      await reopen(KG);
    });

    await t.test("clearing the box goes back to not entered", async () => {
      await typeLevel(KG, "");
      assert.equal((await stored()).guns[KG].level, null);
      assert.match(await head(KG), /Lv \?/);
      assert.ok(await J(`document.querySelector('${card(KG)} li.s-plain')`), "parts are plain (not locked) when not entered");
    });

    await t.test("no sideways scroll and no console errors after all edits", async () => {
      assert.ok((await J(`document.documentElement.scrollWidth`)) <= 390);
      assert.deepEqual(b.errors, []);
    });
  } finally {
    b.close();
    srv.close();
  }
});
