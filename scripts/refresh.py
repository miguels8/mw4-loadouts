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
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mw4_parse as P  # noqa: E402

CODMUNITY = "https://codmunity.gg/weapon/mw4/{slug}"
MIRROR = "https://codloadout.gitlab.io/mw4/weapons/{slug}/"
INFIL = "https://infil.app/loadouts/{slug}/"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
NO_BIG_SCOPE = {"AR", "SMG", "LMG", "Marksman"}
SHARE_SLOTS = {"Muzzle", "Underbarrel", "Laser", "Optic", "Rear Grip"}
GAP = 5   # a stand-in must open at least this many weapon levels before the part it covers


def part(slot, name, level, stand_in=None):
    return {"slot": slot, "name": name, "level": level, "stand_in": stand_in}


def apply_pick(parts, pick, level):
    """The owner's own pick: put pick['name'] in place of the part in slot pick['replaces']."""
    out = [p for p in parts if p[0] != pick["replaces"]] + [[pick["slot"], pick["name"], level]]
    return out, [f"{pick['name']} in place of its {pick['replaces'].lower()} part is Miguel's own pick"]


def _best_dot(table, optics, use):
    cands = sorted((-use.get(n, 0), e[1], n) for n, e in table.items()
                   if e[0] == "Optic" and optics.get(n) == "dot" and e[1] is not None)
    return (cands[0][2], cands[0][1]) if cands else None


def _apply_scope_rule(reg, parts, table, optics, use):
    """No big scope: AR/SMG/LMG/marksman get a 1x dot at most; Mosin-Nagant runs iron sights; snipers keep scopes."""
    notes, out = [], []
    for slot, name, level in parts:
        if slot == "Optic" and reg["type"] in NO_BIG_SCOPE:
            if reg.get("iron_sights"):
                notes.append(f"{name} dropped: iron sights only (no big scope rule)")
                continue
            if optics.get(name) != "dot":
                dot = _best_dot(table, optics, use)
                if dot:
                    notes.append(f"{name} (a scope above 1x) swapped for {dot[0]} (1x dot, Lv {dot[1]}): "
                                 "no big scope rule")
                    name, level = dot
                else:
                    notes.append(f"{name} dropped: no 1x dot published for this gun (no big scope rule)")
                    continue
        out.append([slot, name, level])
    return out, notes


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


def build_data(registry, pages, old, today):
    """Pure core. registry: list of gun facts; pages: slug -> {codmunity, infil} | None; old: previous weapons.json.
    Returns {"data", "changes", "failed"}."""
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
    guns, failed, changes = [], [], []
    for reg in registry:
        slug, pg, prev = reg["slug"], pages.get(reg["slug"]), old_by.get(reg["slug"])
        c = pg["codmunity"] if pg else None
        if not c or not c["builds"]:
            failed.append(slug)
            if prev:
                guns.append(prev)
            continue
        listed = [b for b in c["builds"] if b["name"] != "Apex Attachment"] or c["builds"]
        if len(listed[0]["parts"]) < 4:   # the page parsed to a build with no parts: layout changed, say so loudly
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
        if pi is None:
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
        guns.append(gun)
        changes += diff_gun(prev, gun)
    data = {"schema": 1, "checked": today if not failed else old.get("checked"), "season": "Season 1",
            "sources": ["https://codmunity.gg/weapon/mw4/<gun>", "https://infil.app/loadouts/<gun>/"],
            "optics": dict(sorted(optics.items())), "guns": guns}
    return {"data": data, "changes": changes, "failed": failed}


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
    return out


def add_history(history, date, changes):
    """Newest first; a refresh with no changes adds nothing; a second refresh on the same day replaces its entry."""
    if not changes:
        return history
    return [{"date": date, "changes": changes}] + [h for h in history if h["date"] != date]


def exit_code(failed):
    return 1 if failed else 0


# ------------------------------------------------------------------ fetching
def fetch(url, tries=3, wait=3.0):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(wait * (i + 1))
    print(f"  fetch failed {url}: {last}", file=sys.stderr)
    return None


def load_pages(registry, offline=None, pause=1.5):
    pages = {}
    for reg in registry:
        slug = reg["slug"]
        if offline:
            def read(name):
                p = os.path.join(offline, name)
                return open(p, encoding="utf-8").read() if os.path.exists(p) else None
            cm, inf = read(f"codmunity-{slug}.html"), read(f"infil-{slug}.html")
        else:
            cm = fetch(CODMUNITY.format(slug=slug))
            parsed = P.parse_codmunity(P.html_lines(cm)) if cm else None
            if not parsed or not parsed["builds"]:
                cm = fetch(MIRROR.format(slug=slug))
            inf = fetch(INFIL.format(slug=reg.get("infil_slug", slug)))
            time.sleep(pause)
        pages[slug] = ({"codmunity": P.parse_codmunity(P.html_lines(cm)),
                        "infil": P.parse_infil(P.html_lines(inf)) if inf else None} if cm else None)
    return pages


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


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data"))
    ap.add_argument("--offline")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    d = a.data_dir
    registry = read_json(os.path.join(d, "registry.json"), {"guns": []})["guns"]
    if a.only:
        registry = [g for g in registry if g["slug"] in a.only]
    old = read_json(os.path.join(d, "weapons.json"), {"guns": []})
    pages = load_pages(registry, a.offline)
    res = build_data(registry, pages, old, a.today)
    if a.only:   # a partial run keeps the other guns exactly as they were
        keep = [g for g in old.get("guns", []) if g["slug"] not in a.only]
        res["data"]["guns"] = keep + res["data"]["guns"]
    hist = read_json(os.path.join(d, "changes.json"), {"history": []})["history"]
    write_json(os.path.join(d, "weapons.json"), res["data"])
    write_json(os.path.join(d, "changes.json"), {"history": add_history(hist, a.today, res["changes"])})
    write_json(os.path.join(d, "status.json"), {"checked": res["data"]["checked"], "last_attempt": a.today,
                                                "failed": res["failed"], "guns": len(res["data"]["guns"]),
                                                "changes": len(res["changes"])})
    print(f"refresh {a.today}: {len(res['data']['guns'])} guns, {len(res['changes'])} changes, "
          f"{len(res['failed'])} failed {res['failed']}")
    return exit_code(res["failed"])


if __name__ == "__main__":
    sys.exit(main())
