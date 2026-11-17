// Real-browser test (Chromium, 390 px) of the game-mode dropdown at the top of the Loadouts tab (Amendment A).
// Needs Chromium or Chrome (CHROME=/path overrides); without one the test is skipped loudly.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { findChrome, serve, launch, sleep } from "./tools/cdp.mjs";
import { normalizeProfile, rankGuns } from "../site/engine.js";

const site = process.env.SITE_DIR ?? fileURLToPath(new URL("../site/", import.meta.url));
const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const data = read("../site/data/weapons.json");
const statics = read("../site/data/static.json");
const chrome = findChrome();
const SEL = "select#modeSel";
const mode = (id) => statics.modes.find((m) => m.id === id);

test("game mode dropdown (real Chromium, 390 px)", { skip: chrome ? false : "no Chromium or Chrome found (set CHROME=)", timeout: 150000 }, async (t) => {
  const srv = await serve(site);
  const b = await launch(chrome);
  try {
    const J = (s) => b.evalJs(s);
    const waitFor = async (expr, what) => { for (let i = 0; i < 60; i++) { if (await J(expr)) return; await sleep(100); } assert.fail("timeout: " + what); };
    const order = () => J(`[...document.querySelectorAll("details.gun")].map((d) => d.dataset.slug)`);
    const choose = async (v) => { await J(`(() => { const s = document.querySelector('${SEL}'); s.value = ${JSON.stringify(v)}; s.dispatchEvent(new Event("change", { bubbles: true })); })()`); await sleep(150); };
    const reload = async () => { await b.goto(srv.url); await waitFor(`!!document.querySelector('${SEL}')`, "page drawn"); };

    await b.goto(srv.url);
    await J(`localStorage.clear()`);
    await reload();

    await t.test("one dropdown replaces the chips and lists every mode in the current order, no-class modes included", async () => {
      assert.equal(await J(`document.querySelectorAll('${SEL}').length`), 1);
      assert.equal(await J(`document.querySelectorAll("[data-mode]").length`), 0, "no mode chips left");
      const expect = [...statics.modes.map((m) => m.id), ...statics.no_class.map((n) => n.name)];
      assert.deepEqual(await J(`[...document.querySelector('${SEL}').options].map((o) => o.value)`), expect);
      assert.deepEqual(await J(`[...document.querySelector('${SEL}').options].map((o) => o.text)`), expect);
      assert.equal(await J(`document.querySelector('${SEL}').value`), "TDM", "default mode");
    });

    await t.test("thumb sized, full width, dark, fits 390 px", async () => {
      const r = await J(`(() => { const e = document.querySelector('${SEL}'); const r = e.getBoundingClientRect(); const p = e.parentElement, cs = getComputedStyle(p); return { w: r.width, h: r.height, pw: p.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight), bg: getComputedStyle(e).backgroundColor, fg: getComputedStyle(e).color }; })()`);
      assert.ok(r.h >= 44, `height ${r.h}`);
      assert.ok(r.w >= r.pw - 2, `select ${r.w} is not full width of ${r.pw}`);
      assert.ok(r.w >= 300, `width ${r.w}`);
      const rgb = (s) => s.match(/\d+/g).slice(0, 3).map(Number);
      assert.ok(rgb(r.bg).every((c) => c < 90), `dark background ${r.bg}`);
      assert.ok(rgb(r.fg).every((c) => c > 160), `light text ${r.fg}`);
      assert.ok((await J(`document.documentElement.scrollWidth`)) <= 390);
    });

    await t.test("switching the dropdown re-ranks the list and updates the description", async () => {
      const empty = normalizeProfile();
      const tdm = rankGuns(mode("TDM"), empty, data, statics).map((r) => r.gun.slug);
      const hp = rankGuns(mode("Hardpoint"), empty, data, statics).map((r) => r.gun.slug);
      assert.notDeepEqual(tdm, hp, "test needs two modes that rank differently");
      assert.deepEqual(await order(), tdm);
      await choose("Hardpoint");
      assert.deepEqual(await order(), hp);
      const head = await J(`document.querySelector(".mode-head").innerText`);
      assert.ok(head.includes(mode("Hardpoint").name) && head.includes(mode("Hardpoint").tip), head);
      assert.equal(await J(`document.querySelector('${SEL}').value`), "Hardpoint");
    });

    await t.test("a no-class mode shows its description and no gun list", async () => {
      await choose("Gunfight");
      const n = statics.no_class.find((x) => x.name === "Gunfight");
      const head = await J(`document.querySelector(".mode-head").innerText`);
      assert.ok(head.includes(n.what) && head.includes(n.tip), head);
      assert.equal(await J(`document.querySelectorAll("details.gun").length`), 0);
      assert.equal(await J(`document.querySelector('${SEL}').value`), "Gunfight");
    });

    await t.test("the chosen mode is remembered and survives a reload", async () => {
      await reload();
      assert.equal(await J(`document.querySelector('${SEL}').value`), "Gunfight");
      await choose("Domination");
      await reload();
      assert.equal(await J(`document.querySelector('${SEL}').value`), "Domination");
      assert.equal(JSON.parse(await J(`localStorage.getItem("mw4-loadouts-v1")`)).ui.mode, "Domination");
      const dom = rankGuns(mode("Domination"), normalizeProfile(), data, statics).map((r) => r.gun.slug);
      assert.deepEqual(await order(), dom);
    });

    await t.test("the gun-type filter still works and keeps working after a mode switch", async () => {
      await J(`document.querySelector("[data-type=SMG]").click()`);
      await sleep(150);
      const smg = data.guns.filter((g) => g.type === "SMG").length;
      assert.equal(await J(`document.querySelectorAll("details.gun").length`), smg);
      await choose("TDM");
      assert.equal(await J(`document.querySelectorAll("details.gun").length`), smg, "filter kept across the mode change");
      assert.equal(await J(`document.querySelector("[data-type=SMG]").classList.contains("on")`), true);
    });

    await t.test("no sideways scroll and no console errors", async () => {
      assert.ok((await J(`document.documentElement.scrollWidth`)) <= 390);
      // Chromium's own extension messaging can log "Receiving end does not exist" after a reload; the app uses no chrome.runtime.
      assert.deepEqual(b.errors.filter((e) => !/Receiving end does not exist/.test(e)), []);
    });
  } finally {
    b.close();
    srv.close();
  }
});
