// Proof screenshots at 390 px of the variant card: (a) KG-7 Vulcan with its variant buttons, (b) KG-7 at Lv 54 with the
// full ladder open and the next-upgrade line, (c) the same gun in Hardpoint and in S&D showing different pressed variants.
// Usage: node tests/tools/variant-shot.mjs BASE_URL OUT_DIR   (CHROME=/path to override). Works on the live site.
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
const pressed = () => J(`(() => { const p = document.querySelector('${KG} .vbtn[aria-pressed="true"]'); return p ? p.innerText.replace(/\\n/g, " | ") : null; })()`);
const pressedId = () => J(`document.querySelector('${KG} .vbtn[aria-pressed="true"]')?.dataset.variant ?? null`);
const choose = async (v) => { await J(`(() => { const s = document.querySelector('#modeSel'); s.value = ${JSON.stringify(v)}; s.dispatchEvent(new Event("change", { bubbles: true })); })()`); await sleep(500); };
const show = async () => { await J(`document.querySelector('${KG}').open = true; document.querySelector('${KG}').scrollIntoView()`); await sleep(500); };
try {
  await b.goto(base);
  await J(`localStorage.clear()`);
  await b.goto(base);
  for (let i = 0; i < 80 && !(await J(`!!document.querySelector('${KG} .vbtn')`)); i++) await sleep(250);
  await show();
  const labels = await J(`[...document.querySelectorAll('${KG} .vbtn .vbest')].map((n) => n.textContent)`);
  check("KG-7 has one 'Best for' button per variant", labels.length >= 2 && labels.every((l) => /^Best for: /.test(l)), labels.join(" / "));
  check("exactly one variant is pressed", (await J(`document.querySelectorAll('${KG} .vbtn[aria-pressed="true"]').length`)) === 1);
  check("the data banner is calm", !(await J(`document.querySelector("#fresh").classList.contains("bad")`)), await J(`document.querySelector("#fresh").textContent`));
  await b.shot(join(out, "a-kg7-variant-buttons.png"));
  // (b) Lv 54 with the ladder open and the next-upgrade line
  await J(`(() => { const i = document.querySelector('${KG} input[data-cl=level]'); i.value = "54"; i.dispatchEvent(new Event("change", { bubbles: true })); })()`);
  await sleep(500);
  await show();
  const next = await J(`document.querySelector('${KG} .next')?.textContent ?? null`);
  check("Lv 54 shows a next-upgrade line", /^(Next upgrade at Lv \d+: (swap|add) .+|Final build reached|Apex at max level \d+)$/.test(next ?? ""), String(next));
  await J(`document.querySelector('${KG} details.sub[data-sub$="ladder"] summary').click()`);
  await sleep(400);
  const steps = await J(`document.querySelectorAll('${KG} ol.ladder li').length`);
  check("the full ladder lists level steps", steps >= 2, `${steps} steps`);
  await J(`document.querySelector('${KG} .next').scrollIntoView({ block: "start" })`);
  await sleep(300);
  await b.shot(join(out, "b-kg7-lv54-ladder-next-upgrade.png"));
  // (c) the default variant follows the mode
  await J(`localStorage.clear()`);
  await choose("Hardpoint");
  await show();
  const hp = await pressedId();
  const hpText = await pressed();
  await b.shot(join(out, "c1-kg7-hardpoint.png"));
  await choose("S&D");
  await show();
  const sd = await pressedId();
  const sdText = await pressed();
  await b.shot(join(out, "c2-kg7-snd.png"));
  check("Hardpoint and S&D open different variants", !!hp && !!sd && hp !== sd, `Hardpoint: ${hpText} || S&D: ${sdText}`);
  check("page is not wider than 390 px", (await J(`document.documentElement.scrollWidth`)) <= 390);
  check("no console errors", b.errors.filter((e) => !/favicon|Receiving end does not exist/.test(e)).length === 0, b.errors.join("; "));
  writeFileSync(join(out, "variant-checks.json"), JSON.stringify({ base, width: 390, checks }, null, 1));
  if (checks.some((c) => !c.ok)) process.exitCode = 1;
} finally {
  b.close();
}
