"""Build variants core: pure functions, stdlib only, no network, no AI.

A variant is one real, published meta build of a gun (Q5), merged when sites publish near-identical builds (Q13),
dropped when the site has not re-checked it since the latest balance patch (Q6), and labelled with the modes it is
best for from one fixed table (Q10). Nothing here invents a part or an unlock level."""
import hashlib
import re

import mw4_parse as P

NO_BIG_SCOPE = {"AR", "SMG", "LMG", "Marksman"}
SITE_RANK = {"CODMunity": 0, "MW4 Intel": 1, "Infil": 2, "Dexerto": 3}   # tie order for the newest build
CODMUNITY = "https://codmunity.gg/weapon/mw4/{slug}"
INFIL = "https://infil.app/loadouts/{slug}/"
MW4INTEL = "https://mw4intel.app/loadouts/{slug}"
DEXERTO = "https://www.dexerto.com/wikis/modern-warfare-4/weapons/{path}/"


# ------------------------------------------------------------------ standing rules (moved from refresh.py)
def apply_pick(parts, pick, level):
    """The owner's own pick: put pick['name'] in place of the part in slot pick['replaces']."""
    out = [p for p in parts if p[0] != pick["replaces"]] + [[pick["slot"], pick["name"], level]]
    return out, [f"{pick['name']} in place of its {pick['replaces'].lower()} part is Miguel's own pick"]


def best_dot(table, optics, use):
    cands = sorted((-use.get(n, 0), e[1], n) for n, e in table.items()
                   if e[0] == "Optic" and optics.get(n) == "dot" and e[1] is not None)
    return (cands[0][2], cands[0][1]) if cands else None


def apply_scope_rule(reg, parts, table, optics, use):
    """No big scope: AR/SMG/LMG/marksman get a 1x dot at most; Mosin-Nagant runs iron sights; snipers keep scopes."""
    notes, out = [], []
    for slot, name, level in parts:
        if slot == "Optic" and reg["type"] in NO_BIG_SCOPE:
            if reg.get("iron_sights"):
                notes.append(f"{name} dropped: iron sights only (no big scope rule)")
                continue
            if optics.get(name) != "dot":
                dot = best_dot(table, optics, use)
                if dot:
                    notes.append(f"{name} (a scope above 1x) swapped for {dot[0]} (1x dot, Lv {dot[1]}): "
                                 "no big scope rule")
                    name, level = dot
                else:
                    notes.append(f"{name} dropped: no 1x dot published for this gun (no big scope rule)")
                    continue
        out.append([slot, name, level])
    return out, notes


def apply_rules(reg, build, table, optics, use):
    """Standing rules on one variant's parts: the scope rule, and the owner's pick (Hyeon Burst) when the build has a
    part in the slot the pick replaces. Returns a copy of the build with parts and notes."""
    b = dict(build)
    parts, notes = apply_scope_rule(reg, [list(p) for p in build["parts"]], table, optics, use)
    pk = reg.get("pick")
    if pk and any(p[0] == pk["replaces"] for p in parts) and not any(p[1] == pk["name"] for p in parts):
        e = table.get(pk["name"])
        parts, n2 = apply_pick(parts, pk, e[1] if e and e[0] == pk["slot"] else None)
        notes += n2
    b["parts"], b["notes"] = parts, list(build.get("notes") or []) + notes
    return b


# ------------------------------------------------------------------ best-for table (Q10)
def _alias_mode(mode, bf, modes):
    """MW4 Intel's mode text -> one of our mode ids, else None."""
    if not mode:
        return None
    m = mode.strip().lower()
    for md in modes:
        if m in (md["id"].lower(), md["name"].lower()):
            return md["id"]
    return bf.get("mode_aliases", {}).get(m)


def classify(name, mode, bf, modes, kind=None):
    """{type, best_for, source, note}. Order: pro page; MW4 Intel mode (+ the type list of the name); exact type key;
    keyword in the name; default type."""
    types = bf["types"]
    if kind == "pro":
        return {"type": "Pro (Ranked)", "best_for": list(types["Pro (Ranked)"]), "source": "type", "note": None}
    nl = (name or "").lower().strip()
    typ, src = None, None
    for k in types:
        if nl == k.lower():
            typ, src = k, "type"
            break
    if typ is None:
        for k in bf.get("keyword_order", list(bf["keywords"])):
            if any(w in nl for w in bf["keywords"][k]):
                typ, src = k, "keyword"
                break
    if typ is None:
        typ, src = bf["default_type"], "default"
    best = list(types[typ])
    mid = _alias_mode(mode, bf, modes)
    if mid:
        best = [mid] + [x for x in best if x != mid]
        src = "mode"
    return {"type": typ, "best_for": best, "source": src, "note": bf.get("type_notes", {}).get(typ)}


# ------------------------------------------------------------------ patch dates (Q6)
def gun_patch_date(cm_dates, infil_dates):
    """Latest balance date for one gun: CODMunity's Nerfs & Buffs dates and Infil's Buffed/Nerfed history entries."""
    alld = list(cm_dates or []) + list(infil_dates or [])
    return max(alld) if alld else None


def latest_patch(infil_patches, cm_dates_all):
    """The newest balance patch across Infil's recap list and every CODMunity per-gun date."""
    best = None
    for p in infil_patches or []:
        if p.get("tuned") and (best is None or p["date"] > best["date"]):
            best = {"date": p["date"], "name": p["name"], "source": "https://infil.app/patches/"}
    cm = max(cm_dates_all) if cm_dates_all else None
    if cm and (best is None or cm > best["date"]):
        best = {"date": cm, "name": "Balance change on CODMunity", "source": "https://codmunity.gg/weapon/mw4/"}
    return best


def drop_stale(builds, patch_date):
    """Q6: a build dated before the gun's latest balance patch is dropped unless its site re-checked it since (same day
    counts as re-checked). No patch on record drops nothing. Returns (kept, dropped entries)."""
    if not patch_date:
        return list(builds), []
    kept, dropped = [], []
    for b in builds:
        d = b.get("date")
        if d is None:
            reason = f"no date, cannot show it was re-checked after the {patch_date} patch"
        elif d < patch_date:
            reason = f"before the {patch_date} patch"
        else:
            kept.append(b)
            continue
        dropped.append({"site": b["site"], "name": b["name"], "date": d, "url": b["url"], "reason": reason})
    return kept, dropped


# ------------------------------------------------------------------ merge (Q13)
def variant_id(slug, typ, parts):
    key = ",".join(sorted(f"{p[0]}:{p[1]}" for p in parts))
    t = re.sub(r"[^a-z0-9]+", "-", typ.lower()).strip("-")
    return f"{slug}-{t}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:6]}"


def _pairs(b):
    return {(p[0], p[1]) for p in b["parts"]}


def _near_dup(a, b):
    if len(a["parts"]) < 4 or len(b["parts"]) < 4:
        return False
    return len(_pairs(a) & _pairs(b)) >= max(len(a["parts"]), len(b["parts"])) - 1


def _order(b):
    return (-int((b.get("date") or "0000-00-00").replace("-", "")), SITE_RANK.get(b["site"], 9), b["name"])


def merge(slug, builds):
    """Greedy clustering, newest first: each build joins the first cluster whose representative it nearly equals
    (>= larger part count - 1 shared slot+name pairs), else starts one. The representative is the newest build."""
    clusters = []
    for b in sorted(builds, key=_order):
        for c in clusters:
            if _near_dup(c[0], b):
                c.append(b)
                break
        else:
            clusters.append([b])
    out = []
    for c in clusters:
        rep = c[0]
        best, seen = [], set()
        for m in c:
            for x in m["best_for"]:
                if x not in seen:
                    seen.add(x)
                    best.append(x)
        alts, ak = [], set()
        rp = _pairs(rep)
        for m in c[1:]:
            for p in m["parts"]:
                if (p[0], p[1]) not in rp and (p[0], p[1], m["site"]) not in ak:
                    ak.add((p[0], p[1], m["site"]))
                    alts.append({"slot": p[0], "name": p[1], "level": p[2], "site": m["site"]})
        kit = next((m["site_kit"] for m in c if m.get("site_kit")), None)
        text = next((m["text"] for m in c if m.get("text")), None)
        notes = []
        for m in c:
            for n in m.get("notes") or []:
                if n not in notes:
                    notes.append(n)
        out.append({
            "id": variant_id(slug, rep["type"], rep["parts"]), "type": rep["type"], "label": rep["type"],
            "best_for": best, "best_for_source": rep.get("best_for_source", "type"),
            "label_note": rep.get("label_note"),
            "date": rep.get("date"), "url": rep["url"], "agree": len({m["site"] for m in c}),
            "sources": [{"site": m["site"], "name": m["name"], "date": m.get("date"), "url": m["url"]} for m in c],
            "parts": [{"slot": p[0], "name": p[1], "level": p[2]} for p in rep["parts"]],
            "alternatives": alts, "apex_on": bool(rep.get("apex")) and len(rep["parts"]) >= 5,
            "site_kit": kit, "notes": notes, "source_text": text[:1500] if text else None,
        })
    return out


# ------------------------------------------------------------------ collect
def _key(name):
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def canon(table, slot, name):
    """(name, unlock level) with the name spelled as the CODMunity attachment table spells it. MW4 Intel, Dexerto and Infil
    differ in case and punctuation (SA LAZ-500 / SA Laz-500, 12" / 12), so the same part must not look like two parts.
    No match in the same slot: the site's own name and level None (never a guess)."""
    e = table.get(name)
    if e and e[0] == slot:
        return name, e[1]
    k = _key(name)
    for n, e in table.items():
        if e[0] == slot and _key(n) == k:
            return n, e[1]
    return name, None


def _split_apex(parts):
    """A site that lists the Apex as a sixth part: it is the build's Apex, not one of the five slots."""
    apex = next(([p[1], p[2]] for p in parts if p[0] == "Apex"), None)
    return [p for p in parts if p[0] != "Apex"], apex


def _build_ok(parts):
    slots = [p[0] for p in parts]
    return len(slots) >= 4 and len(set(slots)) == len(slots)


def collect(reg, page, table, bf, modes):
    """Raw builds from every source for one gun. page: {codmunity, infil, mw4intel: [loadout dicts with slug],
    mw4intel_weapon, dexerto}. Each raw build carries its type/best_for already classified."""
    slug = reg["slug"]
    raw = []

    def add(site, name, mode, kind, date, url, parts, apex, text, kit):
        if not _build_ok(parts):
            return
        c = classify(name, mode, bf, modes, kind)
        raw.append({"site": site, "name": name, "mode": mode, "kind": kind, "date": date, "url": url,
                    "parts": [list(p) for p in parts], "apex": apex, "text": text, "site_kit": kit,
                    "type": c["type"], "best_for": c["best_for"], "best_for_source": c["source"],
                    "label_note": c["note"]})

    cm = page.get("codmunity")
    for b in (cm or {}).get("builds", []):
        add("CODMunity", b["name"], None, None, b["date"], CODMUNITY.format(slug=slug), b["parts"], b.get("apex"),
            b.get("text"), None)
    inf = page.get("infil")
    if inf and inf.get("endgame"):
        parts = [[sl, *canon(table, sl, n)[:1], lv if lv is not None else canon(table, sl, n)[1]]
                 for sl, n, lv in inf["endgame"]["parts"]]
        add("Infil", "Endgame", None, None, inf.get("checked"), INFIL.format(slug=reg.get("infil_slug", slug)),
            parts, None, inf.get("blurb"), None)
    howto = ((page.get("mw4intel_weapon") or {}).get("howto")) or []
    for ld in page.get("mw4intel") or []:
        parts, apex = _split_apex([[s, *canon(table, s, n)] for s, n in ld["parts"]])
        kind = "pro" if ld["slug"].startswith("pro-") else None
        text = " ".join(x for x in [ld.get("notes")] + howto if x) or None
        kit = None
        if ld.get("perks") or ld.get("tactical"):
            kit = {}
            for i, k in enumerate(ld.get("perks") or []):
                kit[f"perk{i + 1}"] = k
            for k in ("tactical", "lethal", "field"):
                if ld.get(k):
                    kit[k] = ld[k]
        add("MW4 Intel", ld["name"], ld.get("mode"), kind, ld.get("updated"), MW4INTEL.format(slug=ld["slug"]),
            parts, apex, text, kit)
    dx = page.get("dexerto")
    if dx and reg.get("dexerto_path"):
        parts, apex = _split_apex([[s, *canon(table, s, n)] for s, n in dx["parts"]])
        kit = {f"perk{i + 1}": k for i, k in enumerate(dx.get("perks") or [])} or None
        add("Dexerto", "Dexerto build", None, None, dx.get("date"), DEXERTO.format(path=reg["dexerto_path"]),
            parts, apex, None, kit)
    return raw


def build_variants(reg, page, table, optics, use, bf, modes):
    """collect -> standing rules -> drop pre-patch builds -> merge. Also the usage counts for the ladder."""
    cm = page.get("codmunity") or {}
    inf = page.get("infil") or {}
    patch = gun_patch_date(cm.get("patch_dates"), P.infil_balance_dates(inf))
    raw = [apply_rules(reg, b, table, optics, use) for b in collect(reg, page, table, bf, modes)]
    kept, dropped = drop_stale(raw, patch)
    return {"variants": merge(reg["slug"], kept), "dropped": dropped, "patch_date": patch, "kept": kept}
