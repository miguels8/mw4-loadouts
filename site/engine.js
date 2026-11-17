// MW4 Loadouts engine: pure functions, no DOM, no network. The page (app.js) only draws what this returns.
//
// Rules (owner's, from the Sheet builder this replaces):
//  - an empty level is "not entered", never level 0; a typed 0 is a real level;
//  - a part is ready (✅), has a stand-in (🔁) until the real part opens, or is locked (🔒 opens at Lv N);
//    an unpublished unlock level shows "level not published", it is never guessed;
//  - Muzzle / Underbarrel / Laser / Optic / Rear Grip are shared: open on one gun = open on others that take it;
//  - Weapon Prestige turns that gun's own sharing off; an Apex stays owned after prestige;
//  - Classic prestige resets player-level gates (a Permanent Unlock Token keeps one item); Regular keeps them.

export const SHARE_SLOTS = ["Muzzle", "Underbarrel", "Laser", "Optic", "Rear Grip"];
const KIT_SLOTS = ["Perk 1", "Perk 2", "Perk 3", "Lethal", "Tactical", "Field upgrade", "Pistol"];
const KIT_FIELDS = ["perk1", "perk2", "perk3", "lethal", "tactical", "field", "pistol"];
const TIER_ORDER = { S: 0, A: 1, B: 2, C: 3, D: 4 };

export function numOrNull(v) {
  if (v === null || v === undefined) return null;
  const s = String(v).trim();
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function prestigeText(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim().toLowerCase();
  return s === "" || s === "none" || s === "0" || s === "—" ? "" : s;
}

export function normalizeProfile(raw = {}) {
  const p = raw.player ?? {};
  const guns = {};
  for (const [slug, g] of Object.entries(raw.guns ?? {})) {
    guns[slug] = {
      level: numOrNull(g?.level),
      prestige: prestigeText(g?.prestige),
      owned: !!g?.owned,
      token: !!g?.token,
      max: numOrNull(g?.max),
    };
  }
  return {
    player: {
      level: numOrNull(p.level),
      prestige: numOrNull(p.prestige) ?? 0,
      prestigeType: p.prestigeType === "Regular" ? "Regular" : "Classic",
      bpTier: numOrNull(p.bpTier),
    },
    tokens: Object.fromEntries(Object.entries(raw.tokens ?? {}).filter(([, v]) => v).map(([k]) => [k, true])),
    guns,
  };
}

export function importProfile(file) {
  return normalizeProfile({ player: file.player, tokens: file.tokens, guns: file.guns });
}

const gunState = (profile, slug) => profile.guns[slug] ?? { level: null, prestige: "", owned: false, token: false, max: null };
const prestiged = (profile, slug) => gunState(profile, slug).prestige !== "";
const lvTxt = (n) => `Lv ${n}`;

export const LEVEL_MAX = 200;
const EMPTY_GUN = { level: null, prestige: "", owned: false, token: false, max: null };

// One edit to one gun, shared by the My levels page and the card controls. Returns a new profile.
// patch fields: level (empty = not entered), prestige ("" / "1".."10" / "master"), owned, token, max.
export function setGun(profile, slug, patch) {
  const cur = profile.guns[slug] ?? EMPTY_GUN;
  if ("level" in patch) {
    const n = numOrNull(patch.level);
    patch = { ...patch, level: n === null ? null : Math.max(0, Math.min(LEVEL_MAX, Math.round(n))) };
  }
  return normalizeProfile({ ...profile, guns: { ...profile.guns, [slug]: { ...cur, ...patch } } });
}

// The + / - buttons. Not entered: + starts at 1, - stays not entered. Stepping stays between 1 and LEVEL_MAX.
export function stepLevel(level, delta) {
  if (level === null || level === undefined) return delta > 0 ? Math.min(delta, LEVEL_MAX) : null;
  return Math.max(1, Math.min(LEVEL_MAX, level + delta));
}

// Text for the collapsed card header: "Lv 54" or "Lv ?", plus "P3" / "Master" when the gun is prestiged.
export function gunBadges(profile, slug) {
  const g = profile.guns[slug] ?? EMPTY_GUN;
  const pr = g.prestige;
  return {
    level: g.level === null ? "Lv ?" : `Lv ${g.level}`,
    prestige: pr === "" ? "" : pr === "master" ? "Master" : `P${pr}`,
  };
}

// No player-level gate when the level is not entered, or after a Regular prestige (it keeps every unlock).
function noGate(profile) {
  const pl = profile.player;
  return pl.level === null || (pl.prestige >= 1 && pl.prestigeType !== "Classic");
}

export function gunOpen(gun, profile) {
  const u = gun.unlock ?? {};
  const st = gunState(profile, gun.slug);
  if (u.level == null && u.bp_tier) {
    const t = profile.player.bpTier;
    const open = st.owned || t === null || t >= u.bp_tier;
    return { open, reason: open ? null : `Needs Battle Pass tier ${u.bp_tier}` };
  }
  if (u.level == null) return { open: true, reason: null };
  const open = noGate(profile) || profile.player.level >= u.level ||
    (profile.player.prestigeType === "Classic" && st.token);
  return { open, reason: open ? null : `Opens at player ${lvTxt(u.level)}` };
}

export function sharedFrom(gun, part, profile, data) {
  if (!SHARE_SLOTS.includes(part.slot) || prestiged(profile, gun.slug)) return null;
  for (const other of data.guns) {
    if (other.slug === gun.slug) continue;
    const e = other.table?.[part.name];
    if (!e || e[0] !== part.slot) continue;
    const st = gunState(profile, other.slug);
    // an unpublished donor level (null) never opens a part; a prestiged donor reached max level once, so it counts
    if ((st.level !== null && Number.isInteger(e[1]) && st.level >= e[1]) || prestiged(profile, other.slug)) return other.name;
  }
  return null;
}

function standInUsable(part) {
  const s = part.stand_in;
  return !!(s && part.level !== null && s.level !== null && s.level < part.level && s.slot !== "Optic");
}

export function partStatus(gun, part, profile, data) {
  const L = gunState(profile, gun.slug).level;
  const base = { slot: part.slot, name: part.name, level: part.level, standIn: null, sharedFrom: null };
  const shared = sharedFrom(gun, part, profile, data);
  if (shared && (part.level === null || L === null || L < part.level)) {
    return { ...base, state: "ready", icon: "✅", label: part.name, note: `Open from your ${shared}`, sharedFrom: shared };
  }
  if (part.level === null) {
    return { ...base, state: "unknown", icon: "❓", label: part.name, note: "Level not published" };
  }
  if (L === null) return { ...base, state: "plain", icon: "", label: part.name, note: lvTxt(part.level) };
  if (L >= part.level) return { ...base, state: "ready", icon: "✅", label: part.name, note: "" };
  if (standInUsable(part)) {
    const s = part.stand_in;
    const sShared = sharedFrom(gun, { slot: s.slot, name: s.name }, profile, data);
    if (L >= s.level || sShared) {
      const label = s.slot === part.slot ? `Use ${s.name} for now` : `Add ${s.name} (${s.slot.toLowerCase()}) for now`;
      return { ...base, state: "standin", icon: "🔁", label, standIn: s,
        note: `${part.name} opens at ${lvTxt(part.level)}` };
    }
  }
  return { ...base, state: "locked", icon: "🔒", label: part.name, note: `Opens at ${lvTxt(part.level)}` };
}

export function apexView(gun, build, profile) {
  if (!build.apex_on || !gun.apex?.name) {
    return { state: "off", icon: "", label: "No Apex needed", note: "The best build does not use it" };
  }
  const st = gunState(profile, gun.slug);
  const max = st.max ?? gun.apex.level ?? gun.max_level ?? null;
  const name = gun.apex.name;
  if (prestiged(profile, gun.slug)) {
    return { state: "ready", icon: "✅", label: `Use ${name}`, note: "You own it: an Apex stays after prestige" };
  }
  if (max === null) return { state: "unknown", icon: "❓", label: `Use ${name}`, note: "Level not published" };
  if (st.level === null) return { state: "plain", icon: "", label: `Use ${name}`, note: `Opens at max level ${max}` };
  if (st.level >= max) return { state: "ready", icon: "✅", label: `Use ${name}`, note: "" };
  return { state: "locked", icon: "🔒", label: name, note: `Opens at max level ${max} (you: ${st.level})` };
}

export function buildView(gun, key, profile, data) {
  const b = gun.builds[key];
  if (!b) return null;
  const parts = b.parts.map((p) => partStatus(gun, p, profile, data));
  return {
    key, label: b.label, date: b.date, url: b.url, notes: b.notes ?? [], parts,
    ready: parts.filter((p) => p.state === "ready").length, total: parts.length,
    known: parts.filter((p) => p.level !== null).length, until: b.complete_level ?? null,
    apex: apexView(gun, b, profile),
  };
}

// Infil's early-game build, only for a typed gun level where the main build is not mostly open yet.
export function earlyView(gun, profile, data) {
  if (!gun.builds.early || gunState(profile, gun.slug).level === null) return null;
  const main = buildView(gun, "main", profile, data);
  if (main.ready >= Math.min(4, main.known)) return null;
  return buildView(gun, "early", profile, data);
}

export function modeBuildKey(mode, gun) {
  return mode.build === "close" && gun.builds.close ? "close" : "main";
}

export function fitFor(mode, gun, statics) {
  const f = statics.profiles[mode.profile][gun.type] ?? 1;
  return gun.tier === "C" || gun.tier === "D" ? Math.min(f, 2) : f;
}

function kitItemOpen(name, profile, statics) {
  const lvl = statics.kit_unlock[name]?.level ?? null;
  if (lvl === null || noGate(profile)) return true;
  return profile.player.level >= lvl || (profile.player.prestigeType === "Classic" && !!profile.tokens[name]);
}

export function kitFor(mode, gun, profile, data, statics, variant = null) {
  const kit = statics.kits[mode.id];
  const k = KIT_FIELDS.map((f) => kit[f]);
  let why = kit.why;
  let whyItem = kit.whyItem;
  const marksman = gun.type === "Marksman";
  const long = marksman || gun.type === "Sniper";
  const rush = gun.type === "SMG" || gun.type === "Shotgun";
  if (rush && k[1] === "Blood Rush" && mode.id !== "Hijack") {
    k[1] = "Ninja";
    why = `${why} ${statics.role_notes.rush}`;
  } else if (marksman && mode.id !== "Infected") {
    statics.marksman_kit.forEach((n, i) => { k[i] = n; });
    why = statics.role_notes.marksman;
    whyItem = "Ghost";
  } else if (long && mode.id !== "Infected" && !(k[0] === "Ghost" && k[1] === "Ninja" && k[2] === "Cold-Blooded")) {
    [k[0], k[1], k[2]] = ["Ghost", "Ninja", "Cold-Blooded"];
    why = statics.role_notes.long;
    whyItem = "Ghost";
  }
  if (variant && !marksman) {   // Q11: adjust for the variant's role; our kit wins over the site's published perks
    const vt = variant.type;
    if ((vt === "Long Range" || vt === "Sniper") && mode.id !== "Infected" && !(k[0] === "Ghost" && k[1] === "Ninja" && k[2] === "Cold-Blooded")) {
      [k[0], k[1], k[2]] = ["Ghost", "Ninja", "Cold-Blooded"];
      why = statics.role_notes.long;
      whyItem = "Ghost";
    } else if (vt === "Close Range" && k[1] === "Blood Rush" && mode.id !== "Hijack") {
      k[1] = "Ninja";
      why = `${why} ${statics.role_notes.rush}`;
    }
  }
  const siteKit = variant?.site_kit ?? null;
  const never = new Set(statics.mode_never?.[mode.id] ?? []);
  const entered = profile.player.level !== null;
  const items = k.map((name, i) => {
    const slot = KIT_SLOTS[i];
    const isGun = slot === "Pistol";
    const pistol = isGun ? data.guns.find((g) => g.name === name) : null;
    const open = isGun ? (pistol ? gunOpen(pistol, profile).open : true) : kitItemOpen(name, profile, statics);
    const lvl = isGun ? pistol?.unlock?.level ?? null : statics.kit_unlock[name]?.level ?? null;
    const siteName = siteKit?.[KIT_FIELDS[i]] ?? null;
    const siteUses = siteName && siteName !== name ? siteName : null;
    const withSite = (note) => (siteUses ? [note, `Site uses: ${siteUses}`].filter(Boolean).join(" · ") : note);
    const base = { slot, name, level: lvl, standIn: null, siteUses };
    if (!entered) return { ...base, state: "plain", icon: "", label: name, note: withSite(lvl ? `Opens at player ${lvTxt(lvl)}` : "") };
    if (open) return { ...base, state: "ready", icon: "✅", label: name, note: withSite("") };
    const alt = (statics.slot_pref[slot] ?? []).find((n) => n !== name && !never.has(n) && (isGun
      ? (() => { const g = data.guns.find((x) => x.name === n); return !g || gunOpen(g, profile).open; })()
      : kitItemOpen(n, profile, statics)));
    if (alt) {
      return { ...base, state: "standin", icon: "🔁", label: alt, standIn: alt,
        note: withSite(`${name} opens at player ${lvTxt(lvl)}`) };
    }
    return { ...base, state: "locked", icon: "🔒", label: name, note: withSite(`Opens at player ${lvTxt(lvl)}`) };
  });
  return { items, why, whyItem };
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export function dateText(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  return m ? `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}` : "unknown";
}

// The data banner (Q7): red when the last refresh failed, when the check record cannot be read, or when the last
// successful check is more than 24 hours old. status: {checked_at | checked, failed}; nowIso: a full timestamp.
export function freshness(status, nowIso) {
  const now = Date.parse(nowIso);
  const stamp = status?.checked_at ?? (status?.checked ? `${status.checked}T00:00:00Z` : null);
  const t = stamp ? Date.parse(stamp) : NaN;
  if (!status || Number.isNaN(t) || Number.isNaN(now)) {
    return { text: "Data freshness unknown: the check record could not be read. Builds may be out of date", bad: true, hours: null };
  }
  const hours = (now - t) / 3600000;
  const age = hours < 1 ? "under 1 h" : `${Math.round(hours)} h`;
  let text = `Data checked ${age} ago (${dateText(stamp.slice(0, 10))})`;
  let bad = false;
  if (status.failed?.length) {
    text += `. The last refresh could not read: ${status.failed.join(", ")}`;
    bad = true;
  }
  if (hours > 24) {
    text += `. That is over 24 h: builds may be out of date`;
    bad = true;
  }
  return { text, bad, hours };
}

export function rankGuns(mode, profile, data, statics) {
  const rows = data.guns.map((gun) => {
    const key = modeBuildKey(mode, gun);
    const head = mode.head.indexOf(gun.slug);
    const hasVariants = Array.isArray(gun.variants);
    const variant = hasVariants ? defaultVariant(mode, gun, statics) : null;
    let ready;
    if (variant) ready = setupAt(gun, variant, gunState(profile, gun.slug).level, profile, data, mode).ready;
    else ready = buildView(gun, key, profile, data)?.ready ?? 0;
    return { gun, key, head, variant, noVariants: hasVariants && gun.variants.length === 0,
      open: gunOpen(gun, profile), fit: fitFor(mode, gun, statics), ready };
  });
  const typeIdx = (t) => { const i = statics.type_order.indexOf(t); return i < 0 ? 99 : i; };
  rows.sort((a, b) =>
    (a.open.open ? 0 : 1) - (b.open.open ? 0 : 1) ||
    (a.noVariants ? 1 : 0) - (b.noVariants ? 1 : 0) ||
    (a.head < 0 ? 1 : 0) - (b.head < 0 ? 1 : 0) || (a.head - b.head) ||
    b.fit - a.fit ||
    (TIER_ORDER[a.gun.tier] ?? 9) - (TIER_ORDER[b.gun.tier] ?? 9) ||
    b.ready - a.ready ||
    typeIdx(a.gun.type) - typeIdx(b.gun.type) ||
    a.gun.name.localeCompare(b.gun.name));
  return rows;
}

// ---------------------------------------------------------------- variants and the level ladder (Q1-Q5)
export const variantsFor = (gun) => (Array.isArray(gun?.variants) ? gun.variants : []);

export const isCloseMode = (mode) => mode?.profile === "close" || mode?.profile === "survive";
const calcProfile = (m) => (typeof m === "string" ? m : isCloseMode(m) ? "close" : "range");

const TYPE_RANK_CLOSE = { "Close Range": 0, "Pro (Ranked)": 1, Versatile: 2, "Apex Attachment": 3, "Long Range": 4, Sniper: 4 };
const TYPE_RANK_OTHER = { Versatile: 0, "Long Range": 1, Sniper: 1, "Apex Attachment": 2, "Pro (Ranked)": 3, "Close Range": 4 };

// The variant that opens first for the selected mode: the ones whose "best for" lists the mode, then (close modes) the
// Close Range type or (other modes) Versatile then Long; then more sites agreeing; then newest. None lists the mode:
// close modes fall back to a Close Range build, the others to Versatile, else the newest.
export function defaultVariant(mode, gun, statics) {
  const vars = variantsFor(gun);
  if (!vars.length) return null;
  const rank = isCloseMode(mode) ? TYPE_RANK_CLOSE : TYPE_RANK_OTHER;
  const names = [mode.id, mode.name];
  const listed = vars.filter((v) => (v.best_for ?? []).some((x) => names.includes(x)));
  const pool = listed.length ? listed : vars;
  return [...pool].sort((a, b) =>
    (rank[a.type] ?? 9) - (rank[b.type] ?? 9) ||
    (b.agree ?? 1) - (a.agree ?? 1) ||
    String(b.date ?? "").localeCompare(String(a.date ?? "")) ||
    a.id.localeCompare(b.id))[0];
}

// Parts another gun has already unlocked for you (shared slots only), computed once per profile object.
const sharedCache = new WeakMap();
function sharedSet(gun, profile, data) {
  let byData = sharedCache.get(profile);
  if (!byData) { byData = new WeakMap(); sharedCache.set(profile, byData); }
  let bySlug = byData.get(data);
  if (!bySlug) { bySlug = new Map(); byData.set(data, bySlug); }
  let set = bySlug.get(gun.slug);
  if (set) return set;
  set = new Set();
  if (!prestiged(profile, gun.slug)) {
    for (const other of data.guns) {
      if (other.slug === gun.slug) continue;
      const st = gunState(profile, other.slug);
      for (const [name, e] of Object.entries(other.table ?? {})) {
        if (!SHARE_SLOTS.includes(e[0])) continue;
        if ((st.level !== null && Number.isInteger(e[1]) && st.level >= e[1]) || prestiged(profile, other.slug)) set.add(`${e[0]}|${name}`);
      }
    }
  }
  bySlug.set(gun.slug, set);
  return set;
}

const NO_BIG_SCOPE = ["AR", "SMG", "LMG", "Marksman"];
function scopeOk(gun, slot, name, data) {   // standing rule: no scope above a 1x dot on rifles/SMGs/LMGs/marksman; Mosin iron sights
  if (slot !== "Optic") return true;
  if (gun.iron_sights) return false;
  return NO_BIG_SCOPE.includes(gun.type) ? data.optics?.[name] === "dot" : true;
}

function openAt(gun, slot, name, unlock, L, profile, data) {
  if (sharedSet(gun, profile, data).has(`${slot}|${name}`)) return true;
  return unlock !== null && unlock !== undefined && L !== null && L >= unlock;
}

const STEP_TAG = { 0: "", 1: "early build", 2: "swap", 3: "calc", "4a": "stand-in", "4b": "filler" };

// One slot of a variant at a (possibly hypothetical) gun level L. Order (Miguel's Q1): the variant's own part when open;
// 1 a published early build's part; 2 the best open part of the same slot that published builds use; 3 the calculated
// pick (only when the gun passed the Q4 gate); 4a the old cross-slot stand-in; 4b the lowest-level open part of the slot.
// A slot only shows 🔒 when no part of it is open at all.
export function slotPick(gun, variant, own, L, profile, data, mode) {
  const slot = own.slot;
  const prof = calcProfile(mode);
  const close = prof === "close";
  const mk = (step, state, icon, name, label, note, extra = {}) =>
    ({ slot, step, state, icon, name, label, note, tag: STEP_TAG[step] ?? "", own: { name: own.name, level: own.level }, ...extra });
  if (L === null || L === undefined) return mk(0, "plain", "", own.name, own.name, own.level === null ? "Level not published" : lvTxt(own.level));
  const shared = sharedFrom(gun, { slot, name: own.name }, profile, data);
  if (openAt(gun, slot, own.name, own.level, L, profile, data)) {
    return mk(0, "ready", "✅", own.name, own.name, shared && (own.level === null || L < own.level) ? `Open from your ${shared}` : "", { sharedFrom: shared });
  }
  if (own.level === null) return mk(0, "unknown", "❓", own.name, own.name, "Level not published");
  const opens = `${own.name} opens at ${lvTxt(own.level)}`;
  const use = (name) => `Use ${name} for now`;
  const open = (c) => c.level !== null && c.level !== undefined && c.name !== own.name && scopeOk(gun, slot, c.name, data) &&
    openAt(gun, slot, c.name, c.level, L, profile, data);
  // 1: a published build for this level (Infil's early build while it applies)
  for (const pub of gun.published ?? []) {
    if (pub.complete_level != null && L > pub.complete_level) continue;
    const p = pub.parts.find((x) => x.slot === slot);
    if (p && open(p)) return mk(1, "standin", "🔁", p.name, use(p.name), opens, { level: p.level });
  }
  const cands = gun.cands?.[slot] ?? [];
  // 2: pro anchor + same-slot swap: the open part published builds use most (close modes: close-typed builds first)
  const typed = (c) => (close ? (c.types ?? []).includes("Close Range")
    : (c.types ?? []).some((t) => t === "Versatile" || t === "Long Range" || t === "Sniper"));
  const used = cands.filter((c) => (c.used ?? 0) > 0 && open(c)).sort((a, b) =>
    b.used - a.used || (typed(b) ? 1 : 0) - (typed(a) ? 1 : 0) || b.level - a.level || a.name.localeCompare(b.name));
  if (used.length) return mk(2, "standin", "🔁", used[0].name, use(used[0].name), opens, { level: used[0].level });
  // 3: calculated from stats, only on a gun that reproduced the CODMunity build at max level
  if (gun.calc_gate?.pass) {
    const calc = cands.filter((c) => c.score && open(c)).sort((a, b) =>
      b.score[prof] - a.score[prof] || b.level - a.level || a.name.localeCompare(b.name));
    if (calc.length) return mk(3, "standin", "🔁", calc[0].name, use(calc[0].name), opens, { level: calc[0].level });
  }
  // 4a: the old stand-in from a published build (may sit in another slot)
  for (const b of Object.values(gun.builds ?? {})) {
    for (const p of b?.parts ?? []) {
      const si = p.stand_in;
      if (p.name !== own.name || !si || si.level === null || p.level === null || si.level >= p.level || si.slot === "Optic") continue;
      if (openAt(gun, si.slot, si.name, si.level, L, profile, data)) {
        const label = si.slot === slot ? use(si.name) : `Add ${si.name} (${si.slot.toLowerCase()}) for now`;
        return mk("4a", "standin", "🔁", si.name, label, opens, { level: si.level });
      }
    }
  }
  // 4b: the lowest-level open part of the slot (a real part from the table, not calculated)
  const filler = cands.filter(open).sort((a, b) => a.level - b.level || a.name.localeCompare(b.name));
  if (filler.length) {
    return mk("4b", "standin", "🔁", filler[0].name, use(filler[0].name), `Filler: no meta part open yet · ${opens}`, { level: filler[0].level });
  }
  return mk("locked", "locked", "🔒", own.name, own.name, `Opens at ${lvTxt(own.level)}`);
}

export function setupAt(gun, variant, L, profile, data, mode) {
  const picks = variant.parts.map((p) => slotPick(gun, variant, p, L, profile, data, mode));
  return { level: L, picks, total: picks.length, ready: picks.filter((p) => p.step === 0 && p.state === "ready").length };
}

const usable = (p) => !!p && p.state !== "locked" && p.state !== "unknown" && p.state !== "plain";

// Every level step of one variant: the setup at each unlock level of any part that can matter, consecutive identical
// setups collapsed. The first entry is the starting setup (changes []). Each change is {slot, from, to} by part name.
export function ladder(gun, variant, profile, data, mode) {
  const levels = new Set([0]);
  const add = (l) => { if (Number.isInteger(l) && (gun.max_level == null || l <= gun.max_level)) levels.add(l); };
  variant.parts.forEach((p) => add(p.level));
  for (const pub of gun.published ?? []) { pub.parts.forEach((p) => add(p.level)); if (pub.complete_level != null) add(pub.complete_level + 1); }
  for (const lst of Object.values(gun.cands ?? {})) lst.forEach((c) => add(c.level));
  const out = [];
  let prev = null;
  for (const lv of [...levels].sort((a, b) => a - b)) {
    const setup = setupAt(gun, variant, lv, profile, data, mode);
    const changes = [];
    if (prev) {
      setup.picks.forEach((p, i) => {
        const o = prev.picks[i];
        const from = usable(o) ? o.name : null;
        const to = usable(p) ? p.name : null;
        if (from !== to) changes.push({ slot: p.slot, from, to, step: p.step });
      });
      if (!changes.length) continue;
    }
    out.push({ level: lv, setup, changes });
    prev = setup;
  }
  return out;
}

export function nextUpgrade(lad, L, gun, variant) {
  if (L === null || L === undefined) return null;
  const next = lad.find((s) => s.level > L && s.changes.length);
  if (next) {
    const txt = next.changes.filter((c) => c.to).map((c) => (c.from ? `swap ${c.from} -> ${c.to}` : `add ${c.to}`)).join("; ");
    if (txt) return `Next upgrade at Lv ${next.level}: ${txt}`;
  }
  const max = gun.apex?.level ?? gun.max_level ?? null;
  if (variant?.apex_on && gun.apex?.name && max !== null && L < max) return `Apex at max level ${max}`;
  return "Final build reached";
}

// Everything a card needs for one variant at the gun's typed level.
export function variantView(gun, variant, profile, data, mode) {
  const L = gunState(profile, gun.slug).level;
  const setup = setupAt(gun, variant, L, profile, data, mode);
  const lad = ladder(gun, variant, profile, data, mode);
  return { variant, picks: setup.picks, ready: setup.ready, total: setup.total, ladder: lad,
    next: nextUpgrade(lad, L, gun, variant), apex: apexView(gun, { apex_on: variant.apex_on }, profile) };
}
