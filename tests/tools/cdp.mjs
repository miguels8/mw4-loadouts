// Tiny Chromium driver over the DevTools protocol (no dependencies), shared by the DOM test and the proof screenshots.
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join, extname, normalize } from "node:path";

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export function findChrome() {
  if (process.env.CHROME) return process.env.CHROME;
  for (const c of ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]) {
    if (spawnSync("which", [c]).status === 0) return c;
  }
  return null;
}

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".css": "text/css" };

// Serve a folder; `overrides` maps a URL path to a JSON-able value served instead of the file.
export function serve(root, overrides = {}) {
  const srv = createServer((req, res) => {
    const path = new URL(req.url, "http://x").pathname;
    if (overrides[path] !== undefined) {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify(overrides[path]));
    }
    const f = normalize(join(root, path === "/" ? "index.html" : path));
    if (!f.startsWith(root) || !existsSync(f)) { res.writeHead(404); return res.end("no"); }
    res.writeHead(200, { "content-type": TYPES[extname(f)] ?? "application/octet-stream" });
    res.end(readFileSync(f));
  });
  return new Promise((res) => srv.listen(0, "127.0.0.1", () => res({ url: `http://127.0.0.1:${srv.address().port}/`, close: () => srv.close() })));
}

export async function launch(chrome, { width = 390, height = 844 } = {}) {
  const port = 9300 + Math.floor(Math.random() * 500);
  const proc = spawn(chrome, ["--headless=new", "--no-sandbox", "--disable-gpu", `--remote-debugging-port=${port}`,
    `--user-data-dir=${mkdtempSync(join(tmpdir(), "mw4cdp-"))}`, "about:blank"], { stdio: "ignore" });
  let wsUrl = null;
  for (let i = 0; i < 80 && !wsUrl; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
      wsUrl = list.find((t) => t.type === "page")?.webSocketDebuggerUrl ?? null;
    } catch { /* still starting */ }
    if (!wsUrl) await sleep(250);
  }
  if (!wsUrl) { proc.kill("SIGKILL"); throw new Error("Chromium did not start"); }
  const ws = new WebSocket(wsUrl);
  await new Promise((r) => { ws.onopen = r; });
  let nextId = 1;
  const pending = new Map();
  const errors = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const p = pending.get(msg.id); pending.delete(msg.id);
      msg.error ? p.rej(new Error(JSON.stringify(msg.error))) : p.res(msg.result);
    } else if (msg.method === "Runtime.exceptionThrown") errors.push(msg.params.exceptionDetails.text + " " + (msg.params.exceptionDetails.exception?.description ?? ""));
    else if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") errors.push(msg.params.entry.text + " " + (msg.params.entry.url ?? ""));
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const id = nextId++;
    pending.set(id, { res, rej });
    setTimeout(() => rej(new Error("timeout " + method)), 20000);
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evalJs = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + " " + JSON.stringify(r.exceptionDetails.exception?.description));
    return r.result.value;
  };
  await send("Page.enable"); await send("Runtime.enable"); await send("Log.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: true });
  const goto = async (url) => { await send("Page.navigate", { url }); await sleep(1200); };
  // real mouse press / release at the centre of a selector (fires pointer events like a thumb)
  const centre = (sel) => evalJs(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "center" }); const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; })()`);
  const press = async (sel) => { const [x, y] = await centre(sel); await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 }); return [x, y]; };
  const release = async (x, y) => send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  const tap = async (sel) => { const [x, y] = await press(sel); await release(x, y); };
  // a tap that finishes inside one JS turn (press and release can never be told apart from a hold by a slow machine)
  const tapFast = (sel) => evalJs(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); e.scrollIntoView({ block: "center" });
    e.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, cancelable: true, button: 0, pointerId: 7, pointerType: "touch" }));
    window.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, button: 0, pointerId: 7, pointerType: "touch" }));
    e.dispatchEvent(new MouseEvent("click", { bubbles: true, detail: 1 })); })()`);
  const shot = async (file) => {
    const r = await send("Page.captureScreenshot", { format: "png", fromSurface: true, captureBeyondViewport: false });
    writeFileSync(file, Buffer.from(r.data, "base64"));
  };
  const close = () => { try { ws.close(); } catch { /* closing anyway */ } proc.kill("SIGKILL"); };
  return { send, evalJs, goto, press, release, tap, tapFast, shot, close, errors };
}
