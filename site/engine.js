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
    if ((st.level !== null && st.level >= e[1]) || prestiged(profile, other.slug)) return other.name;
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

export function kitFor(mode, gun, profile, data, statics) {
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
  const never = new Set(statics.mode_never?.[mode.id] ?? []);
  const entered = profile.player.level !== null;
  const items = k.map((name, i) => {
    const slot = KIT_SLOTS[i];
    const isGun = slot === "Pistol";
    const pistol = isGun ? data.guns.find((g) => g.name === name) : null;
    const open = isGun ? (pistol ? gunOpen(pistol, profile).open : true) : kitItemOpen(name, profile, statics);
    const lvl = isGun ? pistol?.unlock?.level ?? null : statics.kit_unlock[name]?.level ?? null;
    const base = { slot, name, level: lvl, standIn: null };
    if (!entered) return { ...base, state: "plain", icon: "", label: name, note: lvl ? `Opens at player ${lvTxt(lvl)}` : "" };
    if (open) return { ...base, state: "ready", icon: "✅", label: name, note: "" };
    const alt = (statics.slot_pref[slot] ?? []).find((n) => n !== name && !never.has(n) && (isGun
      ? (() => { const g = data.guns.find((x) => x.name === n); return !g || gunOpen(g, profile).open; })()
      : kitItemOpen(n, profile, statics)));
    if (alt) {
      return { ...base, state: "standin", icon: "🔁", label: alt, standIn: alt,
        note: `${name} opens at player ${lvTxt(lvl)}` };
    }
    return { ...base, state: "locked", icon: "🔒", label: name, note: `Opens at player ${lvTxt(lvl)}` };
  });
  return { items, why, whyItem };
}

export function rankGuns(mode, profile, data, statics) {
  const rows = data.guns.map((gun) => {
    const key = modeBuildKey(mode, gun);
    const head = mode.head.indexOf(gun.slug);
    const view = buildView(gun, key, profile, data);
    return { gun, key, head, open: gunOpen(gun, profile), fit: fitFor(mode, gun, statics), ready: view?.ready ?? 0 };
  });
  const typeIdx = (t) => { const i = statics.type_order.indexOf(t); return i < 0 ? 99 : i; };
  rows.sort((a, b) =>
    (a.open.open ? 0 : 1) - (b.open.open ? 0 : 1) ||
    (a.head < 0 ? 1 : 0) - (b.head < 0 ? 1 : 0) || (a.head - b.head) ||
    b.fit - a.fit ||
    (TIER_ORDER[a.gun.tier] ?? 9) - (TIER_ORDER[b.gun.tier] ?? 9) ||
    b.ready - a.ready ||
    typeIdx(a.gun.type) - typeIdx(b.gun.type) ||
    a.gun.name.localeCompare(b.gun.name));
  return rows;
}
