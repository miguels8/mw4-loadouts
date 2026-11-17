// Proof screenshots at 390 px: the KG-7 Vulcan card before and after pressing + (63 -> 64), plus the collapsed headers.
// Usage: node tests/tools/card-shot.mjs BASE_URL OUT_DIR   (CHROME=/path to override)
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { findChrome, launch, sleep } from "./cdp.mjs";

const [base, out] = process.argv.slice(2);
const chrome = findChrome();
if (!chrome) throw new Error("no Chromium or Chrome found");
mkdirSync(out, { recursive: true });
const b = await launch(chrome);
const checks = [];
const check = (name, ok, detail = "") => { checks.push({ name, ok, detail }); console.log(ok ? "PASS" : "FAIL", name, detail); };
const J = (s) => b.evalJs(s);
const KG = 'details[data-slug="kg-7-vulcan"]';
try {
  await b.goto(base);
  await J(`localStorage.clear()`);
  await b.goto(base);
  for (let i = 0; i < 40 && !(await J(`!!document.querySelector('${KG}')`)); i++) await sleep(250);
  await J(`document.querySelector('${KG}').open = true`);
  await J(`(() => { const i = document.querySelector('${KG} input[data-cl=level]'); i.value = "63"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await J(`document.querySelector('${KG}').scrollIntoView()`);
  await sleep(400);
  const before = await J(`document.querySelector('${KG}').innerText`);
  check("Lv 63: muzzle says add Visiv-5 for now", /Add Schlager Visiv-5 \(laser\) for now/.test(before));
  await b.shot(join(out, "card-1-before-lv63.png"));
  await b.tapFast(`${KG} [data-step="1"]`);
  await sleep(400);
  await J(`document.querySelector('${KG}').scrollIntoView()`);
  await sleep(300);
  const after = await J(`document.querySelector('${KG}').innerText`);
  check("Lv 64: muzzle is ready Ivanov QR600", await J(`[...document.querySelectorAll('${KG} li.s-ready .pname')].some((n) => n.textContent === "Ivanov QR600")`));
  check("Lv 64: Visiv-5 stand-in gone", !/Add Schlager Visiv-5/.test(after));
  const rc = (t) => Number(/(\d+)\/\d+ ready/.exec(t)[1]);
  check("ready count went up by one", rc(after) === rc(before) + 1, `${rc(before)} -> ${rc(after)}`);
  await b.shot(join(out, "card-2-after-lv64.png"));
  await J(`document.querySelector('${KG} select[data-cl=prestige]').value = "3"; document.querySelector('${KG} select[data-cl=prestige]').dispatchEvent(new Event("change", { bubbles: true }))`);
  await J(`document.querySelector('${KG}').open = false; document.querySelector('${KG}').scrollIntoView({ block: "center" })`);
  await sleep(300);
  check("collapsed header shows Lv 64 and P3", /Lv 64/.test(await J(`document.querySelector('${KG} summary').innerText`)) && /P3/.test(await J(`document.querySelector('${KG} summary').innerText`)));
  await b.shot(join(out, "card-3-collapsed-headers.png"));
  check("page is not wider than 390 px", (await J(`document.documentElement.scrollWidth`)) <= 390);
  check("no console errors", b.errors.length === 0, b.errors.join("; "));
  writeFileSync(join(out, "card-checks.json"), JSON.stringify({ base, width: 390, checks }, null, 1));
  if (checks.some((c) => !c.ok)) process.exitCode = 1;
} finally {
  b.close();
}
