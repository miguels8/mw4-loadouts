// Headless phone check: drives a real Chromium over the DevTools protocol at 390 px wide.
// Usage: node tests/tools/shot.mjs BASE_URL OUT_DIR   (CHROME=/path/to/chromium to override)
// Saves PNG screenshots, fails on console errors or sideways scrolling, and checks the KG-7 Vulcan card text.
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [base, out] = process.argv.slice(2);
const chrome = process.env.CHROME || "chromium";
mkdirSync(out, { recursive: true });
const port = 9300 + Math.floor(Math.random() * 500);
const proc = spawn(chrome, ["--headless=new", "--no-sandbox", "--disable-gpu", `--remote-debugging-port=${port}`,
  `--user-data-dir=${mkdtempSync(join(tmpdir(), "mw4shot-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws, nextId = 1;
const pending = new Map();
const errors = [];

async function connect() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      const page = list.find((t) => t.type === "page");
      if (page) return page.webSocketDebuggerUrl;
    } catch { /* browser still starting */ }
    await sleep(250);
  }
  throw new Error("Chromium did not start");
}
const send = (method, params = {}) => new Promise((res, rej) => {
  const id = nextId++;
  pending.set(id, { res, rej });
  setTimeout(() => rej(new Error("timeout " + method)), 90000);
  ws.send(JSON.stringify({ id, method, params }));
});
const evalJs = async (expression) => {
  const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + " " + JSON.stringify(r.exceptionDetails.exception?.description));
  return r.result.value;
};
async function view(name) {
  await send("Page.bringToFront");
  const r = await send("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false });
  writeFileSync(join(out, name), Buffer.from(r.data, "base64"));
  console.log("saved", name, "(viewport)");
}
async function shot(name) {
  const m = await send("Page.getLayoutMetrics");
  const h = Math.ceil(m.cssContentSize?.height ?? m.contentSize.height);
  const r = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: 390, height: Math.min(h, 6000), scale: 1 } });
  writeFileSync(join(out, name), Buffer.from(r.data, "base64"));
  console.log("saved", name, "height", h);
  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
}

try {
  ws = new WebSocket(await connect());
  await new Promise((r) => { ws.onopen = r; });
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id); pending.delete(msg.id);
      msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result);
    } else if (msg.method === "Runtime.exceptionThrown") errors.push(msg.params.exceptionDetails.text);
    else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") errors.push("console.error");
    else if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") errors.push(msg.params.entry.text + " " + (msg.params.entry.url ?? ""));
  };
  await send("Page.enable"); await send("Runtime.enable"); await send("Log.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send("Page.navigate", { url: base });
  await sleep(2000);
  await evalJs("localStorage.clear()");
  await send("Page.navigate", { url: base });
  await sleep(2000);

  const text = () => evalJs("document.body.innerText");
  const wide = () => evalJs("document.documentElement.scrollWidth");
  const checks = [];
  const check = (name, ok, detail = "") => { checks.push({ name, ok, detail }); console.log(ok ? "PASS" : "FAIL", name, detail); };
  // KG-7 text depends on today's refreshed data; it is informational unless STRICT_KG7=1 (the logic itself is unit-tested on pinned data).
  const soft = (name, ok, detail = "") => { if (process.env.STRICT_KG7) return check(name, ok, detail); checks.push({ name, ok: true, detail: ok ? "" : "WARN " + name + " " + detail }); console.log(ok ? "PASS" : "WARN", name); };

  for (let i = 0; i < 20 && !/Data checked .* ago \(|data may be out of date|Data last checked/.test(await text()); i++) await sleep(500);
  let t = await text();
  check("first screen shows the data date", /Data checked .* ago \(|data may be out of date|Data last checked/.test(t));
  check("page is not wider than 390 px", (await wide()) <= 390, String(await wide()));
  await shot("01-loadouts-empty.png");

  await evalJs("document.querySelector('[data-view=levels]').click()");
  await sleep(300);
  await evalJs("document.querySelector('#imp').click()");
  await sleep(800);
  check("levels page not wider than 390 px", (await wide()) <= 390, String(await wide()));
  check("import filled player level 47", (await evalJs("document.querySelector('[data-p=level]').value")) === "47");
  await shot("02-my-levels.png");

  await evalJs("document.querySelector('[data-view=loadouts]').click()");
  await sleep(300);
  await evalJs("(() => { const s = document.querySelector('#modeSel'); s.value = 'TDM'; s.dispatchEvent(new Event('change', { bubbles: true })); })()");
  await sleep(300);
  await evalJs("document.querySelector('details[data-slug=kg-7-vulcan]').open = true");
  t = await evalJs("document.querySelector('details[data-slug=kg-7-vulcan]').innerText");
  soft("KG-7 shows Schlager 7x", /Schlager 7x/.test(t));
  soft("KG-7 shows TT Baem 12", /TT Baem 12/.test(t));
  soft("KG-7 shows Bruen KG-7 Mk. IV", /Bruen KG-7 Mk\. IV/.test(t));
  soft("KG-7 shows TT Type 40 Comb", /TT Type 40 Comb/.test(t));
  soft("KG-7 muzzle: Visiv-5 for now, QR600 at Lv 64", /Visiv-5[^\n]*for now/.test(t) && /Ivanov QR600 opens at Lv\s64/.test(t), t.replace(/\n/g, " | ").slice(0, 400));
  check("page still not wider than 390 px", (await wide()) <= 390, String(await wide()));
  await evalJs("document.querySelector('details[data-slug=kg-7-vulcan]').scrollIntoView()");
  await view("03-tdm-miguel-levels.png");
  await evalJs("document.querySelector('[data-type=SMG]').click()");
  await sleep(300);
  await view("04-tdm-smg-filter.png");
  await evalJs("document.querySelector('[data-view=changed]').click()");
  await sleep(300);
  check("What changed page renders", /What changed/.test(await text()));
  await shot("05-what-changed.png");
  check("no console errors", errors.length === 0, errors.join("; "));
  writeFileSync(join(out, "shot-checks.json"), JSON.stringify({ base, width: 390, checks }, null, 1));
  if (checks.some((c) => !c.ok)) process.exitCode = 1;
} catch (e) {
  console.error("shot failed:", e.message);
  process.exitCode = 1;
} finally {
  try { ws?.close(); } catch { /* closing anyway */ }
  proc.kill("SIGKILL");
}
