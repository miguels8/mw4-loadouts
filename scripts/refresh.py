#!/usr/bin/env python3
"""Daily data refresher for MW4 Loadouts. No AI, stdlib only.

  refresh.py [--data-dir data] [--offline DIR] [--today YYYY-MM-DD] [--only slug ...]

Pulls every gun's CODMunity page (mirror as fallback) and Infil page, writes data/weapons.json,
data/changes.json (the "What changed" history) and data/status.json. A page that cannot be read or no longer
parses is a FAILURE: the gun keeps its previous build, status.json lists it, and the exit code is 1, so the
scheduled run goes red and the app shows the data as stale. It never silently keeps old data as if it were new.
--offline DIR reads DIR/codmunity-<slug>.html and DIR/infil-<slug>.html instead of the network (tests, replays)."""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import calc as C  # noqa: E402
import mw4_parse as P  # noqa: E402
import variants as V  # noqa: E402

CODMUNITY = "https://codmunity.gg/weapon/mw4/{slug}"
MIRROR = "https://codloadout.gitlab.io/mw4/weapons/{slug}/"
INFIL = "https://infil.app/loadouts/{slug}/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
NO_BIG_SCOPE = V.NO_BIG_SCOPE
SHARE_SLOTS = {"Muzzle", "Underbarrel", "Laser", "Optic", "Rear Grip"}
GAP = 5   # a stand-in must open at least this many weapon levels before the part it covers


def part(slot, name, level, stand_in=None):
    return {"slot": slot, "name": name, "level": level, "stand_in": stand_in}


# the standing rules live in variants.py (shared by the old main/close/early builds and every variant)
apply_pick = V.apply_pick
_best_dot = V.best_dot
_apply_scope_rule = V.apply_scope_rule


def _stand_ins(parts, cand_all, old_alt, table, trust_old=False):
    """Attach a stand-in to each locked-able part: lowest unlock level that opens GAP levels early, never an optic."""
    def table_level(slot, name):
        e = table.get(name)
        return e[1] if e and e[0] == slot else None

    slots = {p[0] for p in parts}
    used_names = {p[1] for p in parts}
    used_alt_slots, out = set(), []
    for slot, name, level in parts:
        alt = None
        if level is not None and slot != "Optic":
            same = sorted((cl, cn) for (cs, cn), cl in cand_all.items()
                          if cs == slot and cl <= level - GAP and cn not in used_names)
            oa, oa_ok = old_alt.get(name.lower()), None
            if oa and oa["name"] not in used_names:
                tl = oa["level"] if trust_old else table_level(oa["slot"], oa["name"])
                if tl is not None and tl <= level - GAP and oa["slot"] != "Optic":
                    oa_ok = (oa["slot"], oa["name"], tl)
            cross = sorted((cl, cs, cn) for (cs, cn), cl in cand_all.items()
                           if cs != slot and cs not in slots and cs not in used_alt_slots
                           and cl <= level - GAP and cn not in used_names)
            if same:
                alt = (slot, same[0][1], same[0][0])
            elif oa_ok and oa_ok[0] == slot:
                alt = oa_ok
            elif cross:
                alt = (cross[0][1], cross[0][2], cross[0][0])
            elif oa_ok and oa_ok[0] not in slots and oa_ok[0] not in used_alt_slots:
                alt = oa_ok
            if alt:
                used_names.add(alt[1])
                if alt[0] != slot:
                    used_alt_slots.add(alt[0])
        out.append(part(slot, name, level, {"slot": alt[0], "name": alt[1], "level": alt[2]} if alt else None))
    return out


def _convert(reg, b, kind, url, cand_all, prev, table, optics, use, trust_old=False):
    parts, notes = _apply_scope_rule(reg, b["parts"], table, optics, use)
    if kind == "main" and reg.get("pick"):
        pk = reg["pick"]
        e = table.get(pk["name"])
        parts, n2 = apply_pick(parts, pk, e[1] if e and e[0] == pk["slot"] else None)
        notes += n2
    if b.get("levels_missing"):
        notes.append("The source page shows no unlock levels today: levels come from its attachment table or the "
                     "last check; a part with no known level says so")
    else:
        for p in b["parts"]:
            if p[2] is None:
                notes.append(f"{p[1]} is an event reward (no unlock level published)")
    return {"label": b["name"], "date": b["date"], "url": url,
            "parts": _stand_ins(parts, cand_all, _old_stand_ins(prev, kind), table, trust_old),
            "apex_on": bool(b["apex"]) and len(b["parts"]) >= 5, "notes": notes}


def _early(reg, infil, table, optics, use, url):
    e = infil["early"]
    parts, notes = _apply_scope_rule(reg, e["parts"], table, optics, use)
    return {"label": "Early game", "date": infil["checked"], "url": url, "complete_level": e["complete_level"],
            "parts": [part(*p) for p in parts], "apex_on": False, "notes": notes}


def _build_ok(b):
    """A source build is usable when it has at least 4 parts and no slot twice (a page bleed shows as a repeat)."""
    slots = [p[0] for p in b["parts"]]
    return len(slots) >= 4 and len(set(slots)) == len(slots)


def _fill_levels(c, prev):
    """Pages that stop showing "· Level N": take the level from the page's own attachment table, else from the
    last check of the same part. Never a guess: no source for it means the level stays None (level not published)."""
    c = copy.deepcopy(c)
    old = {}
    for b in ((prev or {}).get("builds") or {}).values():
        for p in (b or {}).get("parts", []):
            if p.get("level") is not None:
                old[(p["slot"], p["name"].lower())] = p["level"]
    for b in c["builds"]:
        if not b.get("levels_missing"):
            continue
        for p in b["parts"]:
            if p[2] is None:
                e = c["table"].get(p[1])
                p[2] = e[1] if e and e[0] == p[0] else old.get((p[0], p[1].lower()))
    return c


def _old_stand_ins(old_gun, kind):
    """Previous stand-ins by part name: this build's own first, other builds of the gun only as a fallback."""
    builds = (old_gun or {}).get("builds", {})
    out = {}
    for key in [kind] + [k for k in builds if k != kind]:
        for p in (builds.get(key) or {}).get("parts", []):
            if p.get("stand_in"):
                out.setdefault(p["name"].lower(), p["stand_in"])
    return out


EXTRA_KEYS = ("patch_date", "variants", "published", "cands", "dropped", "calc_gate")


def _gun_extras(reg, pg, c, optics, use, ctx, prev, builds, listed0, gates):
    """Variants, published builds, candidate parts and the Q4 gate for one gun (schema 2)."""
    slug = reg["slug"]
    table = c["table"]
    if not table and prev and "variants" in prev:   # the page lost its attachment table: keep the last full answer
        return {k: prev[k] for k in EXTRA_KEYS if k in prev}
    page = {"codmunity": c, "infil": pg.get("infil"), "mw4intel": pg.get("mw4intel") or [],
            "mw4intel_weapon": pg.get("mw4intel_weapon"), "dexerto": pg.get("dexerto")}
    res = V.build_variants(reg, page, table, optics, use, ctx["bf"], ctx["modes"])
    published = []
    e = builds.get("early")
    if e:
        published.append({"site": "Infil", "label": e["label"], "complete_level": e.get("complete_level"),
                          "date": e["date"], "url": e["url"],
                          "parts": [{"slot": p["slot"], "name": p["name"], "level": p["level"]} for p in e["parts"]]})
    stats = c.get("stats") or {}
    rows = {n: {"slot": en[0], "level": en[1], "stats": stats.get(n, {})} for n, en in table.items()}
    rules = {"optics": optics, "iron_sights": bool(reg.get("iron_sights"))}
    gate = C.gun_gate(rows, ctx["weights"], [[p[0], p[1]] for p in listed0["parts"]], listed0["name"], reg["type"], rules)
    gates[slug] = gate
    cands = C.cands(rows, ctx["weights"], gate["pass"])
    used = {}
    for b in res["kept"]:
        for sl, n, lv in b["parts"]:
            u = used.setdefault((sl, n), {"n": 0, "types": [], "level": lv})
            u["n"] += 1
            if b["type"] not in u["types"]:
                u["types"].append(b["type"])
    for pub in published:
        for p in pub["parts"]:
            u = used.setdefault((p["slot"], p["name"]), {"n": 0, "types": [], "level": p["level"]})
            u["n"] += 1
            if pub["label"] not in u["types"]:
                u["types"].append(pub["label"])
    for (sl, n), u in used.items():
        lst = cands.setdefault(sl, [])
        ent = next((x for x in lst if x["name"] == n), None)
        if ent is None:
            ent = {"name": n, "level": u["level"]}
            lst.append(ent)
        ent["used"] = u["n"]
        ent["types"] = u["types"]
    return {"patch_date": res["patch_date"], "variants": res["variants"], "published": published, "cands": cands,
            "dropped": res["dropped"],
            "calc_gate": {k: gate[k] for k in ("pass", "matched", "of", "profile", "reason")}}


def build_data(registry, pages, old, today, ctx=None):
    """Pure core. registry: list of gun facts; pages: slug -> {codmunity, infil, ...} | None; old: previous weapons.json;
    ctx (optional): {bf, modes, weights} turns on schema 2 (variants, patch dates, calc gate).
    Returns {"data", "changes", "failed", "gates", "cm_dates"}."""
    old_by = {g["slug"]: g for g in old.get("guns", [])}
    optics = dict(old.get("optics", {}))
    use = {}
    for pg in pages.values():
        if not pg or not pg["codmunity"]["builds"]:
            continue
        for n, label in pg["codmunity"]["optic_labels"].items():
            cls = P.optic_class(n, label)
            if optics.get(n) != "dot":
                optics[n] = cls
        for b in pg["codmunity"]["builds"]:
            for slot, name, _lv in b["parts"]:
                if slot == "Optic":
                    use[name] = use.get(name, 0) + 1
    guns, failed, changes, gates, cm_dates = [], [], [], {}, []
    for reg in registry:
        slug, pg, prev = reg["slug"], pages.get(reg["slug"]), old_by.get(reg["slug"])
        c = pg["codmunity"] if pg else None
        if not c or not c["builds"]:
            failed.append(slug)
            if prev:
                guns.append(prev)
            continue
        listed = [b for b in c["builds"] if b["name"] != "Apex Attachment"] or c["builds"]
        close_raw = next((b for b in c["builds"] if b["name"] == "Close Range"), None)
        if not all(_build_ok(b) for b in (listed[0], close_raw) if b):   # layout changed: say so loudly
            failed.append(slug)
            if prev:
                guns.append(prev)
            continue
        c = _fill_levels(c, prev)
        listed = [b for b in c["builds"] if b["name"] != "Apex Attachment"] or c["builds"]
        main_b = listed[0]
        close_b = next((b for b in c["builds"] if b["name"] == "Close Range"), None)
        url = CODMUNITY.format(slug=slug)
        table = c["table"] or (prev or {}).get("table", {})
        cand_all = {}
        for b in c["builds"]:
            for sl, n, lv in b["parts"]:
                if lv is not None and sl != "Optic":
                    cand_all[(sl, n)] = lv
        args = (url, cand_all, prev, table, optics, use, not c["table"])
        apex = next((b["apex"] for b in c["builds"] if b["apex"]), None)
        builds = {"main": _convert(reg, main_b, "main", *args),
                  "close": _convert(reg, close_b, "close", *args) if close_b else None, "early": None}
        pi = pg.get("infil")
        if pi is None or not (pi.get("absent") or pi.get("valid")):
            # Infil unreadable or not recognisable as an Infil page (error, challenge page): keep the old early build
            # and report it, never present it as freshly checked
            failed.append(f"{slug}:infil")
            builds["early"] = (prev or {}).get("builds", {}).get("early")
        elif pi.get("early"):
            builds["early"] = _early(reg, pi, table, optics, use, INFIL.format(slug=reg.get("infil_slug", slug)))
        gun = {k: reg[k] for k in ("slug", "name", "type", "tier", "unlock", "line") if k in reg}
        if reg.get("note"):
            gun["note"] = reg["note"]
        apex_name = apex[0] if apex else (prev or {}).get("apex", {}).get("name")
        apex_level = (apex[1] if apex and apex[1] else None) or ((prev or {}).get("apex") or {}).get("level") \
            or reg.get("max_level")
        gun["max_level"] = apex_level
        gun["apex"] = {"name": apex_name, "level": apex_level} if apex_name else None
        gun["builds"] = builds
        gun["table"] = {n: e for n, e in table.items() if e[0] in SHARE_SLOTS} or (prev or {}).get("table", {})
        if ctx:
            cm_dates += c.get("patch_dates") or []
            for src in ("mw4intel", "dexerto"):
                if pg.get(f"{src}_failed"):
                    failed.append(f"{slug}:{src}")
            if (pg.get("mw4intel_failed") or pg.get("dexerto_failed")) and prev and "variants" in prev:
                gun.update({k: prev[k] for k in EXTRA_KEYS if k in prev})   # a source page could not be read: keep the last answer
            else:
                gun.update(_gun_extras(reg, pg, c, optics, use, ctx, prev, builds, listed[0], gates))
        guns.append(gun)
        changes += diff_gun(prev, gun)
    sources = ["https://codmunity.gg/weapon/mw4/<gun>", "https://infil.app/loadouts/<gun>/"]
    if ctx:
        sources += ["https://mw4intel.app/loadouts/<page>", "https://www.dexerto.com/wikis/modern-warfare-4/weapons/"]
    data = {"schema": 2 if ctx else 1, "checked": today if not failed else old.get("checked"), "season": "Season 1",
            "sources": sources, "optics": dict(sorted(optics.items())), "guns": guns}
    return {"data": data, "changes": changes, "failed": failed, "gates": gates, "cm_dates": cm_dates}


def _txt(p):
    if p is None:
        return None
    return p["name"] if p.get("level") is None else f"{p['name']} (Lv {p['level']})"


def diff_gun(old, new):
    """Change-log entries: one per slot whose part changed, plus apex switches and builds that appeared or went."""
    out = []
    for key in ("main", "close", "early"):
        ob = ((old or {}).get("builds") or {}).get(key)
        nb = new["builds"].get(key)
        base = {"gun": new["name"], "build": key, "source_date": (nb or {}).get("date")}
        if not ob and not nb:
            continue
        if not ob or not nb:
            out.append({**base, "slot": None, "old": None if not ob else ob.get("label"),
                        "new": None if not nb else nb["label"], "kind": "added" if nb else "removed"})
            continue
        slots = []
        for p in ob["parts"] + nb["parts"]:
            if p["slot"] not in slots:
                slots.append(p["slot"])
        for slot in slots:
            o = [p for p in ob["parts"] if p["slot"] == slot]
            n = [p for p in nb["parts"] if p["slot"] == slot]
            for i in range(max(len(o), len(n))):
                op, np_ = (o[i] if i < len(o) else None), (n[i] if i < len(n) else None)
                if op and np_ and op["name"] == np_["name"] and op["level"] == np_["level"]:
                    continue
                if op and np_ and op["name"] != np_["name"]:
                    out.append({**base, "slot": slot, "old": op["name"], "new": np_["name"], "kind": "part"})
                else:
                    out.append({**base, "slot": slot, "old": _txt(op), "new": _txt(np_), "kind": "part"})
        if ob.get("apex_on") != nb.get("apex_on"):
            out.append({**base, "slot": "Apex", "old": "on" if ob.get("apex_on") else "off",
                        "new": "on" if nb.get("apex_on") else "off", "kind": "apex"})
    if old and "variants" in old and "variants" in new:   # first schema-2 run has nothing to compare: no flood of "added"
        base = {"gun": new["name"], "build": None, "slot": None}
        oid = {v["id"]: v for v in old["variants"]}
        nid = {v["id"]: v for v in new["variants"]}
        for i, v in nid.items():
            if i not in oid:
                out.append({**base, "old": None, "new": v["type"], "kind": "variant-added", "source_date": v.get("date"),
                            "sites": [x["site"] for x in v["sources"]]})
        for i, v in oid.items():
            if i not in nid:
                out.append({**base, "old": v["type"], "new": None, "kind": "variant-removed", "source_date": v.get("date"),
                            "sites": [x["site"] for x in v["sources"]]})
        if new.get("patch_date") and new.get("patch_date") != old.get("patch_date"):
            out.append({**base, "old": old.get("patch_date"), "new": new["patch_date"], "kind": "patch",
                        "source_date": new["patch_date"]})
    return out


def add_history(history, date, changes):
    """Newest first; a refresh with no changes adds nothing; a second refresh on the same day replaces its entry."""
    if not changes:
        return history
    return [{"date": date, "changes": changes}] + [h for h in history if h["date"] != date]


def exit_code(failed):
    return 1 if failed else 0


# ------------------------------------------------------------------ fetching
def fetch_status(url, tries=3, wait=3.0):
    """('ok', text) | ('absent', None) for HTTP 404/410 (the site has no page) | ('error', None)."""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return "ok", r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (404, 410):
                return "absent", None
            time.sleep(wait * (i + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(wait * (i + 1))
    print(f"  fetch failed {url}: {last}", file=sys.stderr)
    return "error", None


def fetch(url, tries=3, wait=3.0):
    return fetch_status(url, tries, wait)[1]


def load_pages(registry, offline=None, pause=1.5):
    pages = {}
    for reg in registry:
        slug = reg["slug"]
        if offline:
            def read(name):
                p = os.path.join(offline, name)
                if not os.path.exists(p):
                    return None
                with open(p, encoding="utf-8") as f:
                    return f.read()
            cm, inf = read(f"codmunity-{slug}.html"), read(f"infil-{slug}.html")
            inf_status = "ok" if inf else "absent"
        else:
            cm = fetch(CODMUNITY.format(slug=slug))
            parsed = P.parse_codmunity(P.html_lines(cm)) if cm else None
            if not parsed or not parsed["builds"]:
                cm = fetch(MIRROR.format(slug=slug))
            inf_status, inf = fetch_status(INFIL.format(slug=reg.get("infil_slug", slug)))
            time.sleep(pause)
        if inf_status == "ok":
            infil = P.parse_infil(P.html_lines(inf))
        elif inf_status == "absent":
            infil = {"absent": True, "valid": False, "checked": None, "early": None}
        else:
            infil = None   # unreadable: build_data reports it
        pages[slug] = {"codmunity": P.parse_codmunity(P.html_lines(cm)), "infil": infil} if cm else None
    return pages


MW4INTEL_SITEMAP = "https://mw4intel.app/sitemap.xml"
MW4INTEL_WEAPON = "https://mw4intel.app/weapons/{slug}"
MW4INTEL_LOADOUT = "https://mw4intel.app/loadouts/{slug}"
INFIL_PATCHES = "https://infil.app/patches/"
DEXERTO = "https://www.dexerto.com/wikis/modern-warfare-4/weapons/{path}/"


def _norm(s):
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def assign_gun(registry, ld):
    """The registry gun a MW4 Intel loadout page belongs to, by its 'Primary:' name (case and punctuation ignored)."""
    key = _norm(ld.get("primary"))
    for g in registry:
        if key and key in (_norm(g["name"]), _norm(g["slug"])):
            return g["slug"]
    return None


def load_extras(registry, pages, offline=None, old=None, pause=0.6):
    """MW4 Intel (weapon page, sitemap loadout pages), Dexerto and the Infil patch list.
    Returns {"extras": {slug: {mw4intel, mw4intel_weapon, dexerto, *_failed}}, "failed": [...], "patches": [...],
    "unmatched": n}. Offline: a missing file is a page the site does not have (absent), never an error."""
    extras = {g["slug"]: {"mw4intel": [], "mw4intel_weapon": None, "dexerto": None} for g in registry}
    failed, unmatched = [], 0

    def get(name, url):
        if offline:
            p = os.path.join(offline, name)
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    return "ok", f.read()
            return "absent", None
        st = fetch_status(url)
        time.sleep(pause)
        return st

    st, txt = get("infil-patches.html", INFIL_PATCHES)
    patches = P.parse_infil_patches(P.html_lines(txt)) if st == "ok" else []
    if st == "error" or (st == "ok" and not patches):
        failed.append("infil:patches")
    st, xml = get("mi-sitemap.xml", MW4INTEL_SITEMAP)
    page_slugs = P.parse_mw4intel_sitemap(xml) if st == "ok" else []
    if st == "error" or (st == "ok" and not page_slugs):
        failed.append("mw4intel:sitemap")
        for e in extras.values():
            e["mw4intel_failed"] = True   # the page list is unknown: every gun keeps what it had
    for slug in page_slugs:
        st, txt = get(f"mi-{slug}.html", MW4INTEL_LOADOUT.format(slug=slug))
        if st == "error":
            failed.append(f"mw4intel:{slug}")
            for g in registry:   # which gun was it? the one whose previous variants cite this page
                prev = next((x for x in (old or {}).get("guns", []) if x["slug"] == g["slug"]), None)
                if any(src["url"].endswith("/" + slug) for v in (prev or {}).get("variants", []) for src in v["sources"]):
                    extras[g["slug"]]["mw4intel_failed"] = True
            continue
        ld = P.parse_mw4intel_loadout(P.html_lines(txt)) if st == "ok" else None
        if not ld:
            continue
        ld["slug"] = slug
        gun = assign_gun(registry, ld)
        if gun:
            extras[gun]["mw4intel"].append(ld)
        else:
            unmatched += 1
    for g in registry:
        slug, e = g["slug"], extras[g["slug"]]
        if g.get("mw4intel_slug"):
            st, txt = get(f"mi-weapon-{slug}.html", MW4INTEL_WEAPON.format(slug=g["mw4intel_slug"]))
            if st == "ok":
                e["mw4intel_weapon"] = P.parse_mw4intel_weapon(P.html_lines(txt), g["name"])
            elif st == "error":
                failed.append(f"{slug}:mw4intel")
                e["mw4intel_failed"] = True
        if g.get("dexerto_path"):
            st, txt = get(f"dx-{slug}.html", DEXERTO.format(path=g["dexerto_path"]))
            if st == "ok":
                e["dexerto"] = P.parse_dexerto(P.html_lines(txt))
            elif st == "error":
                failed.append(f"{slug}:dexerto")
                e["dexerto_failed"] = True
    return {"extras": extras, "failed": sorted(set(failed)), "patches": patches, "unmatched": unmatched}


def make_ctx(data_dir, patches, now):
    def d(n):
        return read_json(os.path.join(data_dir, n), None)
    static = d("static.json") or {"modes": []}
    return {"bf": d("bestfor.json"), "weights": d("stat_weights.json"), "patches": patches, "now": now,
            "modes": [{"id": m["id"], "name": m["name"]} for m in static["modes"]]}


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _strip(w):
    return {k: v for k, v in (w or {}).items() if k != "checked"}


def _hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def _put(path, obj):
    """Write only when the bytes differ. Returns True when the file changed."""
    new = _dump(obj)
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == new:
                return False
    except FileNotFoundError:
        pass
    write_json(path, obj)
    return True


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data"))
    ap.add_argument("--offline")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--now", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    d = a.data_dir
    registry = read_json(os.path.join(d, "registry.json"), {"guns": []})["guns"]
    if a.only:
        registry = [g for g in registry if g["slug"] in a.only]
    old = read_json(os.path.join(d, "weapons.json"), {"guns": []})
    old_status = read_json(os.path.join(d, "status.json"), {})
    pages = load_pages(registry, a.offline)
    ex = load_extras(registry, pages, a.offline, old)
    for slug, e in ex["extras"].items():
        if pages.get(slug):
            pages[slug].update(e)
    ctx = make_ctx(d, ex["patches"], a.now)
    res = build_data(registry, pages, old, a.today, ctx)
    failed = sorted(set(res["failed"]) | set(ex["failed"]))
    if a.only:   # a partial run keeps the other guns exactly as they were
        keep = [g for g in old.get("guns", []) if g["slug"] not in a.only]
        res["data"]["guns"] = keep + res["data"]["guns"]
    hist = read_json(os.path.join(d, "changes.json"), {"history": []})["history"]
    gates = read_json(os.path.join(d, "calc_gate.json"), {}) if a.only else {}
    gates.update(res["gates"])
    new_hist = {"history": add_history(hist, a.today, res["changes"])}
    # weapons.json keeps its old "checked" date when nothing but the date moved: no change, no commit, no deploy
    data = res["data"]
    if _strip(data) == _strip(old):
        data = old
    changed = _put(os.path.join(d, "weapons.json"), data)
    changed |= _put(os.path.join(d, "changes.json"), new_hist)
    changed |= _put(os.path.join(d, "calc_gate.json"), gates)
    # the freshest balance patch: Infil's recap list and every CODMunity per-gun date; never older than the last one seen
    latest = V.latest_patch(ex["patches"], res["cm_dates"])
    prev_patch = old_status.get("patch")
    if latest is None or (prev_patch and prev_patch["date"] > latest["date"]):
        latest = prev_patch
    elif prev_patch and (prev_patch["date"], prev_patch["name"]) == (latest["date"], latest["name"]):
        latest = {**latest, "seen_at": prev_patch.get("seen_at", a.now)}
    else:
        latest = {**latest, "seen_at": a.now}
    guns = data["guns"]
    status = {"checked_at": a.now if not failed else old_status.get("checked_at"),
              "checked": a.today if not failed else old_status.get("checked", data.get("checked")),
              "last_attempt": a.now, "failed": failed, "guns": len(guns), "changes": len(res["changes"]),
              "data_hash": _hash(_strip(data)), "patch": latest,
              "variants": sum(len(g.get("variants", [])) for g in guns),
              "dropped": sum(len(g.get("dropped", [])) for g in guns)}
    write_json(os.path.join(d, "status.json"), status)
    print(f"refresh {a.today}: {len(guns)} guns, {status['variants']} variants, {len(res['changes'])} changes, "
          f"{len(failed)} failed {failed}, {ex['unmatched']} MW4 Intel pages matched no gun")
    print(f"DATA_CHANGED={1 if changed else 0}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")
    return exit_code(failed)


if __name__ == "__main__":
    sys.exit(main())
