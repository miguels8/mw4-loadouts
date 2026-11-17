import {
  normalizeProfile, importProfile, gunOpen, buildView, earlyView, kitFor, rankGuns, modeBuildKey, fitFor,
  freshness, dateText, numOrNull, setGun, stepLevel, gunBadges, LEVEL_MAX,
  variantsFor, defaultVariant, variantView,
} from "./engine.js";

const STORE = "mw4-loadouts-v1";
const TYPES = ["All", "AR", "SMG", "Shotgun", "LMG", "Marksman", "Sniper", "Pistol"];
const FIT = { 3: "★★★ Great", 2: "★★ OK", 1: "★ Weak" };
const TIER = { S: "Meta top 5", A: "Meta", B: "Solid", C: "Niche", D: "Off-meta" };
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let data, statics, changes, status, strategy = {}, templates = {};
let profile = normalizeProfile();
let ui = { view: "loadouts", mode: "TDM", type: "All", open: {}, variant: {}, sub: {} };
const STATUS_RAW = "https://raw.githubusercontent.com/miguels8/mw4-loadouts/status/status.json";

function load() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) ?? "null");
    if (s) { profile = normalizeProfile(s.profile); ui = { ...ui, ...s.ui, open: {}, sub: {}, variant: s.ui?.variant ?? {} }; }
  } catch { /* a bad save is ignored, the app starts empty */ }
}
function save() {
  try {
    localStorage.setItem(STORE, JSON.stringify({ profile, ui: { view: ui.view, mode: ui.mode, type: ui.type, variant: ui.variant } }));
  } catch { /* storage can be blocked (private window): the app keeps working for this visit */ }
}

async function getJson(p) {
  const r = await fetch(p, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${p}: ${r.status}`);
  return r.json();
}

function partLi(p) {
  return `<li class="s-${p.state}"><span class="ico">${p.icon}</span><span><span class="pname">${esc(p.label)}</span>` +
    `<span class="pnote">${esc(p.slot)}${p.note ? " · " + esc(p.note) : ""}</span></span></li>`;
}

function buildHtml(v, extra = "") {
  const apex = v.apex.state === "off" ? "" :
    `<li class="s-${v.apex.state}"><span class="ico">${v.apex.icon}</span><span><span class="pname">Apex: ${esc(v.apex.label)}</span>` +
    `<span class="pnote">${esc(v.apex.note)}</span></span></li>`;
  return `<h3>${esc(v.label)} build ${v.until ? `<span class="badge">until Lv ${v.until}</span>` : ""}</h3>` +
    `<ul class="parts">${v.parts.map(partLi).join("")}${apex}</ul>` +
    v.notes.map((n) => `<p class="note">${esc(n)}</p>`).join("") +
    `<p class="src">${esc(v.label)} · source date ${esc(dateText(v.date))} · <a href="${esc(v.url)}" target="_blank" rel="noopener">source</a>${extra}</p>`;
}

function kitHtml(k) {
  return `<h3>Perks and gear</h3><ul class="parts kit">${k.items.map((i) =>
    `<li class="s-${i.state}"><span class="ico">${i.icon}</span><span><span class="pname">${esc(i.label)}</span>` +
    `<span class="pnote">${esc(i.slot)}${i.note ? " · " + esc(i.note) : ""}</span></span></li>`).join("")}</ul>` +
    `<p class="mute">${esc(k.why)}</p>`;
}

// ---------------------------------------------------------------- variant card (one button per real published build)
const modeKey = (slug) => `${ui.mode}|${slug}`;
function chosenVariant(gun, mode) {
  const vars = variantsFor(gun);
  return vars.find((v) => v.id === ui.variant[modeKey(gun.slug)]) ?? defaultVariant(mode, gun, statics);
}

function bestForText(v) {
  const m = v.best_for ?? [];
  return `Best for: ${m.slice(0, 3).join(", ")}${m.length > 3 ? ` +${m.length - 3}` : ""}`;
}

function variantButtons(gun, pressed) {
  return `<div class="vbtns" role="group" aria-label="Builds for ${esc(gun.name)}">` + variantsFor(gun).map((v) =>
    `<button type="button" class="vbtn${v.id === pressed.id ? " on" : ""}" data-variant="${esc(v.id)}" aria-pressed="${v.id === pressed.id}">` +
    `<span class="vbest">${esc(bestForText(v))}</span>` +
    `<span class="vsub">${esc(v.label)} · ${v.agree > 1 ? `${v.agree} sites agree` : esc(v.sources[0].site)} · ${esc(dateText(v.date))}</span></button>`).join("") + `</div>`;
}

function sourcesHtml(v) {
  const list = v.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.site)}${s.name && s.name !== v.label ? " · " + esc(s.name) : ""}</a> (${esc(dateText(s.date))})`).join(", ");
  const sites = [...new Set(v.sources.map((s) => s.site))];
  const head = v.agree > 1 ? `<b>${v.agree} sites agree:</b> ${esc(sites.join(", "))}` : `Source: ${esc(sites[0])}`;
  const alts = (v.alternatives ?? []).map((a) => `<p class="alt">Alternative: ${esc(a.name)} (${esc(a.slot.toLowerCase())}, ${esc(a.site)}${a.level != null ? ", Lv " + a.level : ""})</p>`).join("");
  return `<p class="src">${head}<br>${list}</p>${alts}` + (v.label_note ? `<p class="note">${esc(v.label_note)}</p>` : "");
}

function pickLi(p) {
  return `<li class="s-${p.state}"><span class="ico">${p.icon}</span><span><span class="pname">${esc(p.label)}</span>` +
    `<span class="pnote">${esc(p.slot)}${p.note ? " · " + esc(p.note) : ""}${p.tag ? ` <span class="tag">${esc(p.tag)}</span>` : ""}</span></span></li>`;
}

function ladderHtml(vv, gun) {
  const steps = vv.ladder.map((s, i) => {
    if (i === 0) {
      const have = s.setup.picks.filter((p) => p.state !== "locked" && p.state !== "plain" && p.state !== "unknown");
      return have.length ? `<li><b>Start</b> ${have.map((p) => esc(p.name)).join(", ")}</li>` : "";
    }
    return `<li><b>Lv ${s.level}</b> ${s.changes.filter((c) => c.to).map((c) => c.from ? `swap ${esc(c.from)} → ${esc(c.to)}` : `add ${esc(c.to)}`).join("; ")}</li>`;
  }).join("");
  const open = ui.sub[`${gun.slug}|ladder`] ? " open" : "";
  return `<details class="sub" data-sub="${esc(gun.slug)}|ladder"${open}><summary>Full ladder (every level step)</summary><ol class="ladder">${steps || "<li>No level steps.</li>"}</ol></details>`;
}

function howtoHtml(v, gun) {
  const note = strategy[v.id]?.text;
  const text = note ?? templates.types?.[v.type] ?? templates.fallback ?? "";
  const credit = note ? "Summary of the source site's own text." : v.source_text ? "Standard note for this build type (a summary of the site's text is being written)." : "Standard note for this build type: the source site has no text for it.";
  const open = ui.sub[`${gun.slug}|howto`] ? " open" : "";
  return `<details class="sub" data-sub="${esc(gun.slug)}|howto"${open}><summary>How to use it</summary><p>${esc(text)}</p><p class="src">${esc(credit)}</p></details>`;
}

function variantBody(gun, mode, row, kit) {
  const vars = variantsFor(gun);
  if (!vars.length) {
    const dropped = (gun.dropped ?? []).map((d) => `<li>${esc(d.site)} · ${esc(d.name)} · ${esc(dateText(d.date))} · <a href="${esc(d.url)}" target="_blank" rel="noopener">source</a> · ${esc(d.reason)}</li>`).join("");
    return { html: `<p class="note">No build re-checked since the ${esc(dateText(gun.patch_date))} patch.</p>` +
      (dropped ? `<details class="sub"><summary>Builds that were dropped</summary><ul class="dropped">${dropped}</ul></details>` : ""), ready: 0, total: 0 };
  }
  const v = chosenVariant(gun, mode);
  const vv = variantView(gun, v, profile, data, mode);
  const lvl = gunSt(gun.slug).level;
  const apex = vv.apex.state === "off" ? "" :
    `<li class="s-${vv.apex.state}"><span class="ico">${vv.apex.icon}</span><span><span class="pname">Apex: ${esc(vv.apex.label)}</span><span class="pnote">${esc(vv.apex.note)}</span></span></li>`;
  const next = lvl == null ? `<p class="mute next">Type your level above to see what to use now and your next upgrade.</p>` : `<p class="next">${esc(vv.next)}</p>`;
  const html = variantButtons(gun, v) + `<h3>${esc(v.label)} build</h3>` + sourcesHtml(v) +
    `<ul class="parts">${vv.picks.map(pickLi).join("")}${apex}</ul>` +
    (v.notes ?? []).map((n) => `<p class="note">${esc(n)}</p>`).join("") + next + ladderHtml(vv, gun) + howtoHtml(v, gun);
  return { html, ready: vv.ready, total: vv.total };
}

const PRESTIGES = ["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "master"];
const prestigeLabel = (o) => (o === "" ? "None" : o === "master" ? "Master" : "Prestige " + o);
const gunSt = (slug) => profile.guns[slug] ?? {};

// The control row at the top of an open card: level - / number / +, and the prestige dropdown.
function ctlHtml(gun) {
  const st = gunSt(gun.slug);
  const n = esc(gun.name);
  return `<div class="ctl" data-ctl="${esc(gun.slug)}"><div class="lvl">` +
    `<button type="button" class="step${st.level == null || st.level <= 1 ? " dim" : ""}" data-step="-1" aria-label="Lower ${n} level by 1">−</button>` +
    `<input type="number" inputmode="numeric" min="0" max="${LEVEL_MAX}" data-cl="level" value="${st.level ?? ""}" placeholder="Set level" aria-label="${n} level">` +
    `<button type="button" class="step${st.level >= LEVEL_MAX ? " dim" : ""}" data-step="1" aria-label="Raise ${n} level by 1">+</button></div>` +
    `<label class="pr"><span class="cl">Prestige</span><select data-cl="prestige" aria-label="${n} prestige">${PRESTIGES.map((o) =>
      `<option value="${o}"${(st.prestige ?? "") === o ? " selected" : ""}>${prestigeLabel(o)}</option>`).join("")}</select></label></div>`;
}

// One card as pieces, so a level edit can redraw the header and parts without touching the control row under a finger.
function cardParts(row, index, mode) {
  const { gun, key, open } = row;
  const slug = gun.slug;
  const hasVariants = Array.isArray(gun.variants);
  const badges = [`<span class="badge">${esc(gun.type)}</span>`, `<span class="badge">${esc(TIER[gun.tier] ?? gun.tier)}</span>`];
  if (!open.open) badges.push(`<span class="badge bad">🔒 ${esc(open.reason)}</span>`);
  let ready, total, buildPart, same = "";
  const kitVariant = hasVariants && variantsFor(gun).length ? chosenVariant(gun, mode) : null;
  if (hasVariants) {
    const vb = variantBody(gun, mode, row);
    ready = vb.ready; total = vb.total; buildPart = vb.html;
  } else {
    const view = buildView(gun, key, profile, data);
    const early = earlyView(gun, profile, data);
    ready = view.ready; total = view.total;
    same = key === "close" ? "Close-range build" : gun.builds.close ? "All-round build" : "Same build in every mode";
    buildPart = buildHtml(view) +
      (early ? `<h2>While you level up</h2><p class="mute">Your ${esc(gun.name)} is level ${profile.guns[slug].level}. Use this early build until it reaches level ${early.until}.</p>${buildHtml(early)}` : "");
  }
  const meta = `${FIT[row.fit]} · ${ready}/${total} ready`;
  const kit = kitFor(mode, gun, profile, data, statics, kitVariant);
  const gb = gunBadges(profile, slug);
  const summary = `<span class="rank">${index + 1}</span><span class="gname">${esc(gun.name)}</span>` +
    `<span class="glv"><span class="lvb${profile.guns[slug]?.level == null ? " none" : ""}">${esc(gb.level)}</span>` +
    (gb.prestige ? `<span class="pbadge" title="Weapon prestige">${esc(gb.prestige)}</span>` : "") + `</span>` +
    `<span class="gmeta">${esc(meta)}</span>`;
  const body = `<p>${badges.join(" ")}</p>` +
    (gun.line ? `<p class="mute">${esc(gun.line)}</p>` : "") +
    (gun.note ? `<p class="note">${esc(gun.note)}</p>` : "") +
    (same ? `<p class="mute">${esc(same)}</p>` : "") +
    buildPart + kitHtml(kit);
  return { summary, body, best: index === 0 && open.open };
}

function gunCard(row, index, mode) {
  const slug = row.gun.slug;
  const isOpen = ui.open[slug] ?? (index === 0);
  const c = cardParts(row, index, mode);
  return `<details class="gun${c.best ? " best" : ""}" data-slug="${esc(slug)}"${isOpen ? " open" : ""}>` +
    `<summary>${c.summary}</summary><div class="body">${ctlHtml(row.gun)}<div class="cbody">${c.body}</div></div></details>`;
}

function renderLoadouts() {
  const modes = statics.modes;
  const noClass = statics.no_class;
  const isNo = noClass.some((n) => n.name === ui.mode);
  const mode = modes.find((m) => m.id === ui.mode) ?? modes[0];
  const current = isNo ? ui.mode : mode.id; // an unknown saved mode falls back to the first one
  const pick = (v) => (v === current ? " selected" : "");
  let html = `<h2>Pick a game mode</h2><select id="modeSel" class="modesel" aria-label="Game mode">` +
    modes.map((m) => `<option value="${esc(m.id)}"${pick(m.id)}>${esc(m.id)}</option>`).join("") +
    noClass.map((m) => `<option value="${esc(m.name)}"${pick(m.name)}>${esc(m.name)}</option>`).join("") +
    `</select>`;
  if (isNo) {
    const n = noClass.find((x) => x.name === ui.mode);
    html += `<div class="mode-head"><p><b>${esc(n.name)}</b></p><p>${esc(n.what)}</p><p class="mute">${esc(n.tip)}</p></div>`;
    return html;
  }
  const rows = rankGuns(mode, profile, data, statics);
  const shown = rows.filter((r) => ui.type === "All" || r.gun.type === ui.type);
  html += `<div class="mode-head"><p><b>${esc(mode.name)}</b> · ${esc(mode.what)}</p>` +
    `<p>${esc(mode.why)}</p><p class="mute">Tip: ${esc(mode.tip)}</p></div>` +
    `<div class="chips">${TYPES.map((t) => `<button data-type="${t}" class="${t === ui.type ? "on" : ""}">${t}</button>`).join("")}</div>` +
    (shown.length ? `<div id="cards">${shown.map((r, i) => gunCard(r, i, mode)).join("")}</div>` : `<p class="mute">No guns of that type.</p>`);
  return html;
}

function gunsForLevels() {
  const order = statics.type_order;
  return [...data.guns].sort((a, b) => order.indexOf(a.type) - order.indexOf(b.type) || a.name.localeCompare(b.name));
}

function renderLevels() {
  const p = profile.player;
  const val = (v) => (v === null || v === undefined ? "" : v);
  const gunRows = gunsForLevels().map((g) => {
    const s = profile.guns[g.slug] ?? {};
    const bp = !!(g.unlock?.bp_tier && g.unlock.level == null);
    return `<div class="g" data-gun="${esc(g.slug)}"><div class="gn">${esc(g.name)} <span class="badge">${esc(g.type)}</span></div><div class="cells">` +
      `<label>Level <input type="number" inputmode="numeric" min="0" max="200" data-f="level" value="${val(s.level)}" placeholder="—"></label>` +
      `<label>Prestige <select data-f="prestige">${["", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "master"].map((o) =>
        `<option value="${o}"${(s.prestige ?? "") === o ? " selected" : ""}>${o === "" ? "None" : o === "master" ? "Master" : "Prestige " + o}</option>`).join("")}</select></label>` +
      `<label>Max level <input type="number" inputmode="numeric" min="1" max="200" data-f="max" value="${val(s.max)}" placeholder="${val(g.max_level)}"></label>` +
      (bp ? `<label><input type="checkbox" data-f="owned"${s.owned ? " checked" : ""}> I own it</label>` : "") +
      `<label><input type="checkbox" data-f="token"${s.token ? " checked" : ""}> Unlock token</label>` +
      `</div></div>`;
  }).join("");
  const items = Object.keys(statics.kit_unlock).sort();
  return `<h2>You</h2><p class="mute">Leave a box empty if you do not know it. Empty means not entered, not level 0.</p><div class="form" id="player">` +
    `<label class="row">Player level <input type="number" inputmode="numeric" min="1" max="1000" data-p="level" value="${val(p.level)}" placeholder="—"></label>` +
    `<label class="row">Prestige <input type="number" inputmode="numeric" min="0" max="10" data-p="prestige" value="${p.prestige || ""}" placeholder="0"></label>` +
    `<label class="row">Prestige type <select data-p="prestigeType"><option${p.prestigeType === "Classic" ? " selected" : ""}>Classic</option><option${p.prestigeType === "Regular" ? " selected" : ""}>Regular</option></select></label>` +
    `<label class="row">Battle Pass tier <input type="number" inputmode="numeric" min="0" max="200" data-p="bpTier" value="${val(p.bpTier)}" placeholder="—"></label></div>` +
    `<h3>Permanent Unlock tokens</h3><details><summary class="mute">Tap to tick the perks and gear you kept</summary><div class="glist" id="tokens">` +
    items.map((n) => `<label class="row"><span>${esc(n)}</span><input type="checkbox" data-t="${esc(n)}"${profile.tokens[n] ? " checked" : ""}></label>`).join("") +
    `</div></details><h2>Your guns</h2><div class="btns"><button class="main" id="imp">Load Miguel's levels</button><button id="clr">Clear everything</button></div>` +
    `<p class="mute">Level is the gun's level now. Weapon Prestige relocks its ordinary parts; an Apex stays yours.</p><div class="glist" id="guns">${gunRows}</div>`;
}

function renderChanged() {
  const hist = changes.history ?? [];
  if (!hist.length) return `<h2>What changed</h2><p class="mute">No changes recorded yet. Each daily check that finds a different build is listed here.</p>`;
  return `<h2>What changed</h2>` + hist.map((h) => `<h3>${esc(dateText(h.date))}</h3>` + h.changes.map((c) => {
    const what = c.kind === "added" ? `new ${esc(c.build)} build: ${esc(c.new ?? "")}` :
      c.kind === "removed" ? `${esc(c.build)} build removed` :
      c.kind === "variant-added" ? `new build option: ${esc(c.new)}${c.sites ? " (" + esc(c.sites.join(", ")) + ")" : ""}` :
      c.kind === "variant-removed" ? `build option gone: ${esc(c.old)}${c.sites ? " (" + esc(c.sites.join(", ")) + ")" : ""}` :
      c.kind === "patch" ? `balance patch ${esc(dateText(c.new))}` :
      `${esc(c.build)} · ${esc(c.slot)}: <span class="old">${esc(c.old ?? "(empty)")}</span> → <span class="new">${esc(c.new ?? "(empty)")}</span>`;
    return `<div class="change"><b>${esc(c.gun)}</b> · ${what}<br><span class="mute">source date ${esc(dateText(c.source_date))}</span></div>`;
  }).join("")).join("");
}

function render() {
  document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.view === ui.view));
  $("#app").innerHTML = ui.view === "levels" ? renderLevels() : ui.view === "changed" ? renderChanged() : renderLoadouts();
}

// Redraw only what a level edit can change: each card's header and parts, the ranking order and the control values.
// The control row elements stay in the page, so a finger held on + keeps working while the list re-ranks.
const cardMemo = new WeakMap();
function updateCards(editedSlug) {
  const box = $("#cards");
  if (!box) return;
  const mode = statics.modes.find((m) => m.id === ui.mode) ?? statics.modes[0];
  const rows = rankGuns(mode, profile, data, statics).filter((r) => ui.type === "All" || r.gun.type === ui.type);
  const nodes = rows.map((r) => box.querySelector(`details.gun[data-slug="${CSS.escape(r.gun.slug)}"]`));
  if (nodes.length !== box.children.length || nodes.some((n) => !n)) { render(); return; }
  nodes.forEach((n) => { ui.open[n.dataset.slug] ??= n.open; });
  const E = nodes[rows.findIndex((r) => r.gun.slug === editedSlug)] ?? null;
  const top0 = E?.getBoundingClientRect().top;
  rows.forEach((row, i) => {
    const n = nodes[i];
    const c = cardParts(row, i, mode);
    const memo = cardMemo.get(n) ?? {};
    if (memo.summary !== c.summary) n.querySelector("summary").innerHTML = c.summary;
    if (memo.body !== c.body) n.querySelector(".cbody").innerHTML = c.body;
    cardMemo.set(n, { summary: c.summary, body: c.body });
    n.classList.toggle("best", c.best);
    const st = gunSt(row.gun.slug);
    const inp = n.querySelector("[data-cl=level]");
    const want = String(st.level ?? "");
    if (inp.value !== want) inp.value = want; // always show the saved level, focused or not
    const sel = n.querySelector("[data-cl=prestige]");
    if (sel.value !== (st.prestige ?? "")) sel.value = st.prestige ?? "";
    n.querySelector("[data-step='-1']").classList.toggle("dim", st.level == null || st.level <= 1);
    n.querySelector("[data-step='1']").classList.toggle("dim", st.level >= LEVEL_MAX);
  });
  // Put the cards in rank order without ever moving the edited card (moving it would drop a held finger).
  const at = E ? nodes.indexOf(E) : -1;
  if (at < 0) nodes.forEach((n) => box.appendChild(n));
  else {
    nodes.slice(0, at).forEach((n) => box.insertBefore(n, E));
    let prev = E;
    nodes.slice(at + 1).forEach((n) => { if (prev.nextSibling !== n) box.insertBefore(n, prev.nextSibling); prev = n; });
  }
  if (E && top0 !== undefined) {
    const d = E.getBoundingClientRect().top - top0;
    if (Math.abs(d) > 1) window.scrollBy(0, d);
  }
}

// + / - buttons: one step on press, then repeat while held (thumb or mouse).
let hold = null;
function stopHold() {
  if (!hold) return;
  clearTimeout(hold.t); clearInterval(hold.i);
  hold = null;
}
function stepCard(slug, delta) {
  // text typed in the box but not yet committed (the press keeps focus, so no change event yet) counts first
  const box = document.querySelector(`[data-ctl="${CSS.escape(slug)}"] input[data-cl=level]`);
  const committed = !!box && box.value !== String(gunSt(slug).level ?? "");
  if (committed) profile = setGun(profile, slug, { level: box.value });
  const cur = gunSt(slug).level ?? null;
  const next = stepLevel(cur, delta);
  if (next === cur) {
    // the step cannot move (at 1, at the top, or empty and minus), but the typed text still counts: save and redraw it
    if (committed) { save(); updateCards(slug); }
    return false;
  }
  profile = setGun(profile, slug, { level: next });
  save();
  updateCards(slug);
  return true;
}
function bindSteppers(app) {
  app.addEventListener("pointerdown", (e) => {
    const b = e.target.closest?.("[data-step]");
    if (!b || e.button > 0) return;
    e.preventDefault();
    stopHold();
    const slug = b.closest("[data-ctl]").dataset.ctl;
    const delta = Number(b.dataset.step);
    try { b.setPointerCapture(e.pointerId); } catch { /* capture is a nicety */ }
    stepCard(slug, delta);
    const h = { t: null, i: null };
    h.t = setTimeout(() => { h.i = setInterval(() => { if (!stepCard(slug, delta)) stopHold(); }, 110); }, 450);
    hold = h;
  });
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture"]) window.addEventListener(ev, stopHold, true);
  window.addEventListener("blur", stopHold);
  app.addEventListener("contextmenu", (e) => { if (e.target.closest?.("[data-step]")) e.preventDefault(); });
  // keyboard (Enter / Space) arrives as a click with no pointer; a pointer press was already handled
  app.addEventListener("click", (e) => {
    const b = e.target.closest?.("[data-step]");
    if (b && e.detail === 0) stepCard(b.closest("[data-ctl]").dataset.ctl, Number(b.dataset.step));
  });
}

function bind() {
  document.querySelector(".tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    ui.view = b.dataset.view; save(); render(); window.scrollTo(0, 0);
  });
  const app = $("#app");
  bindSteppers(app);
  app.addEventListener("click", (e) => {
    const t = e.target.closest("[data-type]"); if (t) { ui.type = t.dataset.type; save(); render(); return; }
    const vb = e.target.closest("[data-variant]");
    if (vb) {
      const slug = vb.closest("details.gun").dataset.slug;
      ui.variant[modeKey(slug)] = vb.dataset.variant;
      save(); updateCards(slug);
      return;
    }
    if (e.target.id === "imp") {
      getJson("miguel-levels.json").then((f) => { profile = importProfile(f); save(); render(); });
    }
    if (e.target.id === "clr" && confirm("Clear every level you typed?")) { profile = normalizeProfile(); save(); render(); }
  });
  app.addEventListener("toggle", (e) => {
    const sub = e.target.closest?.("details.sub[data-sub]");
    if (sub) { ui.sub[sub.dataset.sub] = sub.open; return; }
    const d = e.target.closest?.("details.gun"); if (d) ui.open[d.dataset.slug] = d.open;
  }, true);
  app.addEventListener("change", (e) => {
    const el = e.target;
    if (el.id === "modeSel") { ui.mode = el.value; ui.open = {}; save(); render(); return; }
    if (el.dataset.p) {
      const k = el.dataset.p;
      profile.player[k] = k === "prestigeType" ? el.value : k === "prestige" ? (numOrNull(el.value) ?? 0) : numOrNull(el.value);
    } else if (el.dataset.t) {
      if (el.checked) profile.tokens[el.dataset.t] = true; else delete profile.tokens[el.dataset.t];
    } else if (el.dataset.f) {
      const f = el.dataset.f;
      const slug = el.closest("[data-gun]").dataset.gun;
      profile = setGun(profile, slug, { [f]: el.type === "checkbox" ? el.checked : el.value });
      if (f === "level") el.value = profile.guns[slug].level ?? ""; // show the clamped value
    } else if (el.dataset.cl) {
      profile = setGun(profile, el.closest("[data-ctl]").dataset.ctl, { [el.dataset.cl]: el.value });
      save();
      updateCards(el.closest("[data-ctl]").dataset.ctl);
      return;
    } else return;
    profile = normalizeProfile(profile);
    save();
  });
}

// The data banner. Red = failed refresh, unreadable record or last check over 24 h ago (Q7). The record on the status
// branch is the live heartbeat (it moves every 3 h even when nothing changed); the copy shipped with the page is the fallback.
function showFresh(st) {
  const f = freshness(st, new Date().toISOString());
  const el = $("#fresh");
  el.textContent = f.text;
  el.className = "fresh" + (f.bad ? " bad" : "");
  el.setAttribute("role", f.bad ? "alert" : "status");
}

const isLive = () => /github\.io$/.test(location.hostname);   // local copies and tests only use the shipped record

async function upgradeStatus() {
  if (!isLive()) return;
  try {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), 8000);
    const r = await fetch(`${STATUS_RAW}?t=${Date.now()}`, { cache: "no-store", signal: ctl.signal });
    clearTimeout(t);
    if (r.ok) { status = await r.json(); showFresh(status); return; }
  } catch { /* fall through to the record shipped with the page */ }
  showFresh(status);
}

async function main() {
  load();
  try {
    [data, statics, changes, status, strategy, templates] = await Promise.all([
      getJson("data/weapons.json"), getJson("data/static.json"),
      getJson("data/changes.json").catch(() => ({ history: [] })), getJson("data/status.json").catch(() => null),
      getJson("data/strategy.json").catch(() => ({})), getJson("data/strategy_templates.json").catch(() => ({})),
    ]);
  } catch (e) {
    $("#fresh").textContent = `Could not load the data (${e.message}). Reload the page.`;
    $("#fresh").className = "fresh bad";
    return;
  }
  if (isLive()) $("#fresh").textContent = "Checking when the data was last refreshed…"; else showFresh(status);
  bind();
  render();
  upgradeStatus();
}

main();
