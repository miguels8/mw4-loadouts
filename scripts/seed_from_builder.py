#!/usr/bin/env python3
"""One-time seed: copy the data of the owner's Sheet builder into this repo's JSON files (read-only on the builder).

  seed_from_builder.py BUILDER_PY BUILDS_JSON OPTICS_JSON OUT_DATA_DIR

BUILDER_PY   the reviewed candidate builder (job mw4-codmunity-resource-r4, mw4_sheet.py)
BUILDS_JSON  that job's parsed CODMunity pages (builds.json: per slug builds + attachment table)
OPTICS_JSON  that job's optic labels (optics.json)
Writes registry.json (hand-kept gun facts), static.json (modes, kits, unlock levels) and the first weapons.json.
After this the daily refresher (scripts/refresh.py) owns weapons.json; registry.json and static.json are edited by hand."""
import importlib.util
import json
import os
import re
import sys

SLUG = {"Cronen Osprey": "cronen-osprey", "M4": "m4", "Han 86": "han-86", "Hyeon Burst": "hyeon-burst",
        "Patriot XMR": "patriot-xmr", "Kastov 762": "kastov-762", "Axion": "axion", "Oden": "oden",
        "Cronen Squall": "cronen-squall", "VEL 46": "vel-46", "ISO Nightshade": "iso-nightshade",
        "PPSh-41": "ppsh-41", "Wz.55 Striga": "wz-55-striga", "X-58 Nyx": "x-58-nyx", "CSG-35": "csg-35",
        "Rezi 12": "rezi-12", "Warlord": "warlord", "FiNN LMG": "finn-lmg", "Type 73": "type-73",
        "APOC-338": "apoc-338", "Oris 8.6": "oris-8-6", "Mosin-Nagant": "mosin-nagant", "MAR-9": "mar-9",
        "KG-7 Vulcan": "kg-7-vulcan", "Signal 50": "signal-50", "Astaroth .57": "astaroth-57",
        "SANG 9mm": "sang-9mm", "Krait P68": "krait-p68", ".50 GS": "50-gs", "Mojave .357": "mojave-357"}
SHARE_SLOTS = ["Muzzle", "Underbarrel", "Laser", "Optic", "Rear Grip"]
DOT_LABELS = {"Reflex", "Mini Reflex", "Holo"}
SRC = re.compile(r"CODMunity Multiplayer: (.+?) \((\d{4}-\d{2}-\d{2})\) (https://\S+?)(?:;|$)")


def load(path):
    spec = importlib.util.spec_from_file_location("builder", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def part(p):
    slot, name, level, alt = (list(p) + [None])[:4]
    stand = {"slot": alt[0], "name": alt[1], "level": alt[2]} if alt else None
    return {"slot": slot, "name": name, "level": level, "stand_in": stand}


def build(src, parts, apex_text):
    m = SRC.search(src)
    notes = [n.strip() for n in src.split(";")[1:] if n.strip()]
    return {"label": m.group(1), "date": m.group(2), "url": m.group(3), "parts": [part(p) for p in parts],
            "apex_on": apex_text.startswith("ON"), "notes": notes}


def unlock(m, gun):
    lvl, other = m.GUN_UNLOCK.get(gun, (None, None))
    return {"level": lvl, "bp_tier": m.bp_tier(gun), "note": other}


def main(builder, builds_json, optics_json, out):
    m = load(builder)
    pages = json.load(open(builds_json, encoding="utf-8"))
    optics = json.load(open(optics_json, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)

    guns_reg, guns = [], []
    for w in m.WEAPONS:
        gun, slug = w["gun"], SLUG[w["gun"]]
        reg = {"slug": slug, "name": gun, "type": w["type"], "tier": w["tier"], "max_level": w["max"],
               "unlock": unlock(m, gun), "infil_slug": slug, "line": w["line"]}
        if gun == "Mosin-Nagant":
            reg["iron_sights"] = True   # owner's rule: the Mosin runs iron sights, no scope
        if gun in m.GUN_NOTES:
            reg["note"] = m.GUN_NOTES[gun]
        for g, name in m.YOUR_PICKS:
            if g == gun:
                reg["pick"] = {"slot": "Optic", "name": name, "replaces": "Ammunition"}
        guns_reg.append(reg)
        builds = {"main": build(w["src"], w["parts"], w["apex"]), "close": None, "early": None}
        v = m.VARIANTS.get(gun, {}).get("close")
        if v:
            builds["close"] = build(v["src"], v["parts"], v["apex"])
        table = {n: e for n, e in pages[slug]["table"].items() if e[0] in SHARE_SLOTS}
        guns.append({**{k: reg[k] for k in ("slug", "name", "type", "tier", "max_level", "unlock", "line")},
                     **({"note": reg["note"]} if "note" in reg else {}),
                     "apex": {"name": w["apex_name"], "level": w["max"]}, "builds": builds, "table": table})

    classes = {}
    for name, per_gun in optics.items():
        labels = {v[0] for v in per_gun.values()}
        classes[name] = "iron" if "Ironsights" in name else "dot" if labels & DOT_LABELS else "scope"

    data = {"schema": 1, "checked": "2026-11-16", "season": "Season 1",
            "sources": ["https://codmunity.gg/weapon/mw4/<gun>", "https://infil.app/loadouts/<gun>/"],
            "optics": classes, "guns": guns}
    modes = []
    for mode in m.MODES:
        head = list(dict.fromkeys([mode["run"], mode["backup"]] + m.CARD_ALSO.get(mode["tab"], [])))
        modes.append({"id": mode["tab"], "name": mode["name"], "what": mode["what"], "profile": mode["profile"],
                      "build": mode["build"], "why": mode["why"], "tip": mode["tip"],
                      "head": [SLUG[g] for g in head]})
    static = {
        "schema": 1, "modes": modes,
        "kits": {k: dict(zip(["perk1", "perk2", "perk3", "lethal", "tactical", "field", "pistol", "why", "whyItem"], v))
                 for k, v in m.KITS.items()},
        "kit_unlock": {n: {"slot": s, "level": l} for n, (s, l) in m.KIT_UNLOCK.items()},
        "slot_pref": m.SLOT_PREF, "role_notes": m.ROLE_NOTE, "marksman_kit": list(m.MARKSMAN_KIT),
        "profiles": m.PROFILES, "profile_words": m.PROFILE_WORDS, "mode_never": {k: sorted(v) for k, v in m.MODE_NEVER.items()},
        "no_class": [{"name": a, "what": b, "tip": c} for a, b, c in m.NO_CLASS],
        "share_slots": SHARE_SLOTS, "type_order": m.TYPE_ORDER, "tier_words": m.TIER_WORDS,
        "tier_source": m.TIER_SOURCE, "share_source": m.SHARE_SOURCE}
    for name, obj in (("registry", {"schema": 1, "guns": guns_reg}), ("static", static), ("weapons", data)):
        with open(os.path.join(out, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)
            f.write("\n")
    print("seeded", len(guns), "guns,", len(modes), "modes")


if __name__ == "__main__":
    main(*sys.argv[1:5])
