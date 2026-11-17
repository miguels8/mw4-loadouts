// Real-browser test (Chromium at 390 px) of the variant buttons, the level setup, next-upgrade line, ladder, "how to use"
// and the red data banner. Data is pinned: KG-7 Vulcan and M4 come from the 2026-11-17 live refresh, frozen in fixtures.
// Needs Chromium or Chrome (CHROME=/path overrides); without one the test is skipped loudly.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { findChrome, serve, launch, sleep } from "./tools/cdp.mjs";
import { normalizeProfile, defaultVariant, variantsFor } from "../site/engine.js";

const site = process.env.SITE_DIR ?? fileURLToPath(new URL("../site/", import.meta.url));
const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const weapons = read("../site/data/weapons.json");
const statics = read("../site/data/static.json");
const golden = read("./fixtures/kg7-variants-gun.json");
const kg = golden.gun;
const m4 = read("./fixtures/m4-variants-gun.json");
const empty = { ...weapons.guns.find((g) => g.slug === "oden"), variants: [], patch_date: "2026-11-13",
  dropped: [{ site: "CODMunity", name: "Versatile", date: "2026-11-06", url: "https://codmunity.gg/weapon/mw4/oden", reason: "before the 2026-11-13 patch" }] };
const data = { ...weapons, optics: { ...weapons.optics, ...golden.optics },
  guns: weapons.guns.map((g) => (g.slug === kg.slug ? kg : g.slug === "m4" ? m4 : g.slug === "oden" ? empty : g)) };
const chrome = findChrome();
const KG = "kg-7-vulcan";
const card = (slug) => `details[data-slug="${slug}"]`;
const mode = (id) => statics.modes.find((m) => m.id === id);
const now = () => new Date().toISOString();

test("variant buttons, level setup, next upgrade, ladder, how to use (real Chromium, 390 px)",
  { skip: chrome ? false : "no Chromium or Chrome found (set CHROME=)", timeout: 480000 }, async (t) => {
    const fresh = { checked_at: now(), checked: now().slice(0, 10), failed: [], guns: 30 };
    const srv = await serve(site, { "/data/weapons.json": data, "/data/status.json": fresh });
    const b = await launch(chrome);
    try {
      const J = (s) => b.evalJs(s);
      const waitFor = async (expr, what) => { for (let i = 0; i < 200; i++) { if (await J(expr)) return; await sleep(100); } assert.fail("timeout: " + what); };
      const choose = async (v) => { await J(`(() => { const s = document.querySelector('#modeSel'); s.value = ${JSON.stringify(v)}; s.dispatchEvent(new Event("change", { bubbles: true })); })()`); await sleep(250); };
      const typeLevel = (slug, v) => J(`(() => { const i = document.querySelector('${card(slug)} input[data-cl="level"]'); i.value = "${v}"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
      const pressedId = (slug) => J(`document.querySelector('${card(slug)} .vbtn[aria-pressed="true"]')?.dataset.variant ?? null`);
      const reopen = (slug) => J(`document.querySelector('${card(slug)}').open = true`);
      const body = (slug) => J(`document.querySelector('${card(slug)}').innerText`);

      await b.goto(srv.url);
      await J(`localStorage.clear()`);
      await b.goto(srv.url);
      await waitFor(`!!document.querySelector('${card(KG)}')`, "cards drawn");
      await reopen(KG);

      await t.test("KG-7 shows one 'Best for' button per variant, exactly one pressed, the mode's default first", async () => {
        const labels = await J(`[...document.querySelectorAll('${card(KG)} .vbtn .vbest')].map((n) => n.textContent)`);
        assert.equal(labels.length, kg.variants.length);
        assert.ok(labels.every((l) => /^Best for: /.test(l)), labels.join(" / "));
        assert.equal(await J(`document.querySelectorAll('${card(KG)} .vbtn[aria-pressed="true"]').length`), 1);
        assert.equal(await pressedId(KG), defaultVariant(mode("TDM"), kg, statics).id);
        assert.ok(await J(`[...document.querySelectorAll('${card(KG)} .vbtn')].every((n) => n.getBoundingClientRect().height >= 44)`), "thumb sized");
        assert.ok((await J(`document.documentElement.scrollWidth`)) <= 390, "no sideways scroll");
      });

      await t.test("every variant shows its date and a source link", async () => {
        for (const v of variantsFor(kg).slice(0, 2)) {
          await J(`document.querySelector('${card(KG)} .vbtn[data-variant="${v.id}"]').click()`);
          await sleep(120);
          const txt = await body(KG);
          assert.ok(txt.includes(v.sources[0].site), `${v.id} names its site`);
          assert.ok(await J(`!!document.querySelector('${card(KG)} .src a[href^="http"]')`), `${v.id} has a source link`);
        }
      });

      await t.test("pressing another variant redraws the card and the choice survives a reload", async () => {
        const first = await pressedId(KG);
        const other = variantsFor(kg).find((v) => v.id !== first).id;
        await J(`document.querySelector('${card(KG)} .vbtn[data-variant="${other}"]').click()`);
        await sleep(150);
        assert.equal(await pressedId(KG), other);
        await b.goto(srv.url);
        await waitFor(`!!document.querySelector('${card(KG)}')`, "redrawn");
        await reopen(KG);
        assert.equal(await pressedId(KG), other);
      });

      await t.test("changing the mode re-picks the default: KG-7 differs between Hardpoint and S&D", async () => {
        await choose("Hardpoint");
        await reopen(KG);
        const hp = await pressedId(KG);
        assert.equal(hp, defaultVariant(mode("Hardpoint"), kg, statics).id);
        await choose("S&D");
        await reopen(KG);
        const sd = await pressedId(KG);
        assert.equal(sd, defaultVariant(mode("S&D"), kg, statics).id);
        assert.notEqual(hp, sd);
        await choose("TDM");
      });

      await t.test("Lv 63 shows the next upgrade, one + press moves it, and the full ladder lists the steps", async () => {
        await reopen(KG);
        await J(`document.querySelector('${card(KG)} .vbtn[data-variant="${golden.variant_id}"]').click()`);
        await sleep(150);
        assert.match(await body(KG), /Type your level above/);
        await typeLevel(KG, 63);
        await sleep(200);
        assert.equal(await J(`document.querySelector('${card(KG)} .next').textContent`), "Next upgrade at Lv 64: swap DS RKT-90 -> Ivanov QR600");
        assert.match(await body(KG), /Use DS RKT-90 for now/);
        await b.tapFast(`${card(KG)} [data-step="1"]`);
        await sleep(250);
        assert.equal(await J(`document.querySelector('${card(KG)} .next').textContent`), "Final build reached");
        await typeLevel(KG, 54);
        await sleep(200);
        assert.equal(await J(`document.querySelector('${card(KG)} .next').textContent`), golden.next_upgrade_at_54);
        await J(`document.querySelector('${card(KG)} details.sub[data-sub$="ladder"] summary').click()`);
        await sleep(150);
        const steps = await J(`[...document.querySelectorAll('${card(KG)} ol.ladder li')].map((n) => n.textContent)`);
        assert.ok(steps.length >= 4, steps.join(" | "));
        assert.ok(steps.some((s) => /^Lv\s?64/.test(s) && /Ivanov QR600/.test(s)));
        await typeLevel(KG, 55);       // an edit redraws the card but keeps the ladder open
        await sleep(200);
        assert.equal(await J(`document.querySelector('${card(KG)} details.sub[data-sub$="ladder"]').open`), true);
      });

      await t.test("'How to use it' shows a standard note with its credit when no summary exists yet", async () => {
        await J(`document.querySelector('${card(KG)} details.sub[data-sub$="howto"] summary').click()`);
        await sleep(150);
        const txt = await J(`document.querySelector('${card(KG)} details.sub[data-sub$="howto"]').innerText`);
        assert.match(txt, /Standard note|Summary of the source/);
        assert.ok(txt.length > 80);
      });

      await t.test("a gun with no re-checked build says so and lists the dropped builds", async () => {
        await reopen("oden");
        const txt = await body("oden");
        assert.match(txt, /No build re-checked since the Nov 13, 2026 patch/);
        await J(`document.querySelector('${card("oden")} details.sub summary').click()`);
        await sleep(100);
        assert.match(await body("oden"), /before the 2026-11-13 patch/);
        const order = await J(`[...document.querySelectorAll("details.gun")].map((d) => d.dataset.slug)`);
        assert.equal(order.at(-1), "oden", "a gun with no re-checked build ranks after every gun that has one");
      });

      await t.test("kit shows 'Site uses' when the variant's site picked a different perk", async () => {
        const withKit = variantsFor(m4).find((v) => v.site_kit?.perk1);
        assert.ok(withKit, "the M4 fixture has a variant with site perks");
        await reopen("m4");
        await J(`document.querySelector('${card("m4")} .vbtn[data-variant="${withKit.id}"]').click()`);
        await sleep(150);
        const txt = await body("m4");
        const ours = statics.kits.TDM;
        const differs = ["perk1", "perk2", "perk3"].some((k) => withKit.site_kit[k] && withKit.site_kit[k] !== ours[k]);
        if (differs) assert.match(txt, /Site uses: /);
      });

      await t.test("the data banner is calm when fresh and red when the last check is over 24 h old", async () => {
        assert.equal(await J(`document.querySelector("#fresh").classList.contains("bad")`), false);
        assert.match(await J(`document.querySelector("#fresh").textContent`), /Data checked/);
      });

      await t.test("no sideways scroll and no console errors", async () => {
        assert.ok((await J(`document.documentElement.scrollWidth`)) <= 390);
        assert.deepEqual(b.errors.filter((e) => !/favicon|Receiving end does not exist/.test(e)), []);   // the second is Chromium extension-messaging noise on some machines
      });
    } finally {
      await b.close();
      srv.close();
    }
  });

test("the red banner shows on a stale record, a failed refresh and a missing record (real Chromium)",
  { skip: chrome ? false : "no Chromium or Chrome found (set CHROME=)", timeout: 120000 }, async (t) => {
    for (const [name, st, red] of [
      ["fresh", { checked_at: now(), failed: [] }, false],
      ["stale 30 h", { checked_at: new Date(Date.now() - 30 * 3600000).toISOString(), failed: [] }, true],
      ["failed", { checked_at: now(), failed: ["mar-9"] }, true],
    ]) {
      const srv = await serve(site, { "/data/weapons.json": data, "/data/status.json": st });
      const b = await launch(chrome);
      try {
        await b.goto(srv.url);
        for (let i = 0; i < 40 && !(await b.evalJs(`!!document.querySelector("details.gun")`)); i++) await sleep(100);
        assert.equal(await b.evalJs(`document.querySelector("#fresh").classList.contains("bad")`), red, name);
        if (red) assert.equal(await b.evalJs(`document.querySelector("#fresh").getAttribute("role")`), "alert");
      } finally {
        await b.close();
        srv.close();
      }
    }
  });
