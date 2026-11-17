"""Parsers for saved CODMunity weapon pages and Infil loadout pages (stdlib only, no AI).

Both sites are read as visible text, one text node per line, so a layout change that keeps the words keeps working.
A page that no longer parses returns no builds; the refresher then reports it as a failure instead of guessing."""
import datetime as dt
import re
from html.parser import HTMLParser

SLOTS = {"Optic", "Muzzle", "Barrel", "Underbarrel", "Magazine", "Rear Grip", "Stock", "Laser", "Ammunition",
         "Bolt", "Comb", "Guard", "Trigger Action", "Cylinder", "Apex", "Handle", "Ammo", "Sight", "Receiver"}
LEVEL = re.compile(r"^· (?:Level (\d+)|Event Reward)$")
STAT = re.compile(r"^[+-]?\d|^—")
STAT_VALUE = re.compile(r"^[+-]\d+(?:\.\d+)?%?$|^\d+(?:\.\d+)?%$|^—$")
DOT_LABELS = {"Reflex", "Mini Reflex", "Holo"}
INFIL_SLOTS = {"Ammo": "Ammunition"}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.out = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag == "img":
            alt = dict(attrs).get("alt")
            if alt:
                self.out.append("[img] " + alt)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        data = data.strip()
        if data and not self.skip:
            self.out.append(data)


def html_lines(text):
    """Visible text of an HTML page, one text node per line."""
    p = _Text()
    p.feed(text)
    p.close()
    return p.out


def optic_class(name, label):
    """'dot' (1x reflex, mini reflex, holo), 'iron' (iron sights) or 'scope' (anything bigger or unlabelled)."""
    if "ironsight" in name.lower():
        return "iron"
    return "dot" if label in DOT_LABELS else "scope"


def _iso(d, fmt):
    try:
        return dt.datetime.strptime(d, fmt).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _builds(L):
    builds = []
    for i, ln in enumerate(L):
        if ln != "Loadout (MW4 Multiplayer)" or i < 2:
            continue
        if any("reserved for Premium" in x for x in L[i:i + 30]):   # a Premium-locked build: no parts shown, no account
            continue
        j = i - 2
        while j > 0 and L[j] != "Last Updated:":
            j -= 1
        date = _iso(L[j + 1], "%d/%m/%Y") if L[j] == "Last Updated:" and j + 1 < len(L) else None
        rank = L[i + 2] if i + 2 < len(L) and L[i + 1] == "#" else None
        nxt = next((x for x in range(i + 1, len(L)) if L[x] == "Loadout (MW4 Multiplayer)"), len(L))
        k = i
        while k < nxt and L[k] != "Weapon Level for this loadout":
            k += 1
        if k >= nxt:   # no weapon-level marker (newer layout): the build ends at its "Build code" line
            k = next((x for x in range(i, nxt) if L[x] == "Build code"), nxt)
        blk = L[i:k]
        parts, apex, tags, m, missing = [], None, [], 0, False
        while m < len(blk):
            if blk[m] in ("Pro Favorite", "Buff", "Nerf", "Apex") and m < 8:
                tags.append(blk[m])
            lv = LEVEL.match(blk[m + 1]) if m + 1 < len(blk) else None
            if blk[m] in SLOTS and not lv and _loose_name(blk, m):
                # layout without any "· Level N" line (CODMunity MAR-9 page, 2026-11-16): the part is known, its level is not
                missing = True
                if blk[m] == "Apex":
                    apex = [blk[m + 1], None]
                else:
                    parts.append([blk[m], blk[m + 1], None])
                m += 2
                continue
            if blk[m] in SLOTS and lv and m + 2 < len(blk):
                slot, level, name = blk[m], (int(lv.group(1)) if lv.group(1) else None), blk[m + 2]
                if name == "·" and m + 5 < len(blk) and blk[m + 3] == "of":   # MAR-9 layout: "· / of / Mar-9 / Name"
                    name = blk[m + 5]
                    m += 3
                if slot == "Apex":
                    apex = [name, level]
                else:
                    parts.append([slot, name, level])
                m += 3
                continue
            m += 1
        wl = int(L[k + 1]) if k + 1 < len(L) and L[k + 1].isdigit() else None
        builds.append({"name": L[i - 1], "rank": rank, "date": date, "parts": parts, "apex": apex,
                       "weapon_level": wl, "tags": tags, "levels_missing": missing,
                       # CODMunity pages carry no prose about a build (checked 2026-11-17 on m4, kg-7-vulcan, han-86:
                       # only gun and attachment descriptions, which say nothing about how to use the build)
                       "text": None})
    return builds

    for x in range(c + 1, nxt):
        if L[x] == "Last Updated:":
            break
        if len(L[x]) > 60 and counts.get(L[x]) == 1 and not L[x].startswith("Avg TTK"):
            return L[x][:1500]
    return None


def _loose_name(blk, m):
    """True when blk[m] (a slot word) is followed by an attachment name, not a stat, tag or another slot."""
    if m + 2 >= len(blk):
        return False
    name = blk[m + 1]
    if name in SLOTS or name in ("Attachments", "·", "Apex Attachments", "Without Apex") or STAT_VALUE.match(name) \
            or name.startswith("[img]") or name.startswith("Build code"):
        return False
    return STAT_VALUE.match(blk[m + 2]) is not None or blk[m + 2] in SLOTS or blk[m + 2] == "Build code"


def _num(v):
    return float(v.rstrip("%"))


def _is_row(L, j):
    return j + 2 < len(L) and L[j + 1] in SLOTS and L[j + 2].startswith("Level ")


def _table_full(L):
    """Attachment table: name -> [slot, unlock level]; optic name -> label (the site's own size word);
    name -> {stat: signed number} (the table's own per-attachment deltas; "—" = none)."""
    try:
        start = L.index("Attachment name")
    except ValueError:
        return {}, {}, {}
    table, labels, stats, i = {}, {}, {}, start
    while i < len(L) - 2:
        if L[i + 1] in SLOTS and L[i + 2].startswith("Level ") and L[i + 2][6:].isdigit():
            table.setdefault(L[i], [L[i + 1], int(L[i + 2][6:])])
            j = i + 3
            cand = L[j] if j < len(L) else ""
            if L[i + 1] == "Optic":
                labels.setdefault(L[i], "" if STAT.match(cand) or _is_row(L, j) else cand)
            if not STAT_VALUE.match(cand) and not _is_row(L, j):   # a label word (optic size, barrel family)
                j += 1
            row = {}
            while j + 1 < len(L) and STAT_VALUE.match(L[j]) and not _is_row(L, j):
                if L[j] == "—":
                    j += 1
                    break
                row[L[j + 1]] = _num(L[j])
                j += 2
            stats.setdefault(L[i], row)
            i = max(i + 3, j)
        else:
            i += 1
    return table, labels, stats


def _table(L):
    t, lab, _ = _table_full(L)
    return t, lab


def _patch_dates(L):
    """dd/mm/yyyy lines inside the per-gun 'Nerfs & Buffs - Patch Notes' block, newest first."""
    if "Nerfs & Buffs - Patch Notes" not in L:
        return []
    i = L.index("Nerfs & Buffs - Patch Notes") + 1
    out = set()
    while i < len(L) and not L[i].startswith("All the attachments"):
        d = _iso(L[i], "%d/%m/%Y") if re.match(r"^\d{2}/\d{2}/\d{4}$", L[i]) else None
        if d:
            out.add(d)
        i += 1
    return sorted(out, reverse=True)


def parse_codmunity(L):
    table, labels, stats = _table_full(L)
    return {"title": L[0] if L else "", "builds": _builds(L), "table": table, "optic_labels": labels,
            "stats": stats, "patch_dates": _patch_dates(L)}


def _infil_build(L, heading, label):
    """One Infil build block ('Early game build' / 'Endgame build'): ({complete_level, parts} | None, broken)."""
    if heading not in L:
        return None, False
    i = L.index(heading) + 1
    parts = []
    while i + 3 < len(L) and L[i] != "Copy build":
        if L[i].isdigit() and L[i + 2].startswith("Weapon Lvl "):
            slot = INFIL_SLOTS.get(L[i + 1], L[i + 1])
            parts.append([slot, L[i + 3], int(L[i + 2][11:])])
            i += 4
        else:
            i += 1
    complete = None
    if label in L:
        j = L.index(label) + 1
        if j < len(L) and L[j].startswith("Weapon Lvl ") and L[j][11:].isdigit():
            complete = int(L[j][11:])
    if not parts:
        return None, True   # heading present but nothing parses
    return {"complete_level": complete if complete is not None else max(p[2] for p in parts), "parts": parts}, False


def _infil_history(L):
    if "Patch history" not in L:
        return []
    i = L.index("Patch history") + 1
    out = []
    while i + 2 < len(L):
        d = _iso(L[i + 1], "%b %d, %Y")
        if not d:
            break
        text, step = L[i + 2], 3
        if _iso(text, "%b %d, %Y") or text.startswith("Apex attachment"):
            text, step = "", 2
        out.append({"date": d, "name": L[i], "text": text})
        i += step
    return out


def infil_balance_dates(inf):
    """Dates of the gun's Infil patch-history entries that buffed or nerfed it (a tier-only move is not a balance change)."""
    return sorted({h["date"] for h in (inf or {}).get("patch_history", [])
                   if re.search(r"\b(Buffed|Nerfed)\b", h["text"])}, reverse=True)


def parse_infil(L):
    """Infil 'Early game' build: [slot, part, weapon level] list plus the level where it is complete; also the endgame
    build, the gun's one-line blurb and its dated patch history."""
    # valid = the page is recognisably an Infil loadout page (it lists its builds); a challenge page or an error
    # page is not, so "no early build" can be told apart from "page unreadable"
    out = {"checked": None, "early": None, "endgame": None, "blurb": None, "patch_history": [],
           "valid": "Endgame build" in L or "Early game build" in L}
    for i, ln in enumerate(L):
        if ln == "Checked" and i + 1 < len(L):
            out["checked"] = _iso(L[i + 1], "%b %d, %Y")
            break
    if "Unlocks" in L:
        b = L[L.index("Unlocks") - 1]
        out["blurb"] = b if " " in b and len(b) > 25 else None
    out["patch_history"] = _infil_history(L)
    out["endgame"], _ = _infil_build(L, "Endgame build", "Endgame")
    early, broken = _infil_build(L, "Early game build", "Early game")
    out["early"] = early
    if broken:
        out["valid"] = False   # the heading is there but its build no longer parses: unreadable, not "no early build"
    return out


def parse_infil_patches(L):
    """Infil patch recap list: [{date, name, tuned}] newest first; tuned = guns tuned (None = tier moves only)."""
    out = []
    for i in range(len(L) - 3):
        d = _iso(L[i], "%b %d, %Y")
        if d and not _iso(L[i + 1], "%b %d, %Y"):
            m = re.search(r"(\d+) guns? tuned", L[i + 3])
            out.append({"date": d, "name": L[i + 1], "tuned": int(m.group(1)) if m else None})
    return out


def latest_balance_patch(patches):
    return next((p for p in patches if p["tuned"]), None)


# ------------------------------------------------------------------ MW4 Intel (mw4intel.app)
def parse_mw4intel_loadout(L):
    """The plain-text 'Print' block of a loadout page: name, mode, primary, parts, perks, equipment, notes, updated."""
    blk = next((L[i + 1] for i, x in enumerate(L) if x == "Print" and i + 1 < len(L) and "Primary:" in L[i + 1]), None)
    if blk is None:
        return None
    r = {"name": None, "mode": None, "primary": None, "parts": [], "perks": [], "tactical": None, "lethal": None,
         "field": None, "notes": None, "updated": None}
    rows = blk.split("\n")
    r["name"] = re.sub(r"\s*\([^)]*tier\)\s*$", "", rows[0].split(" — ")[0]).strip()
    for row in rows[1:]:
        t = row.strip()
        m = re.match(r"^•\s*([^:]+):\s*(.+)$", t)
        if m:
            slot = INFIL_SLOTS.get(m.group(1).strip(), m.group(1).strip())
            r["parts"].append([slot, m.group(2).strip()])
        elif t.startswith("Mode:"):
            r["mode"] = t[5:].strip()
        elif t.startswith("Primary:"):
            r["primary"] = t[8:].strip()
        elif t.startswith("Perks:"):
            r["perks"] = [x.strip() for x in t[6:].split(",") if x.strip()]
        elif t.startswith("Tactical:"):
            for key, lab in (("tactical", "Tactical"), ("lethal", "Lethal"), ("field", "Field upgrade")):
                mm = re.search(lab + r":\s*([^·]+?)\s*(?:·|$)", t)
                if mm:
                    r[key] = mm.group(1).strip()
        elif t.startswith("Notes:"):
            r["notes"] = t[6:].strip()
    for i, x in enumerate(L):
        if x == "Updated" and i + 1 < len(L):
            r["updated"] = _iso(L[i + 1], "%d %b %Y")
            break
    return r


def parse_mw4intel_weapon(L, gun_name):
    """Weapon page: the 'How to use the <gun>' bullets and the page's update date."""
    howto = []
    head = f"How to use the {gun_name}"
    if head in L:
        i = L.index(head) + 1
        while i < len(L) and not L[i].startswith("Written by") and len(howto) < 8:
            howto.append(L[i])
            i += 1
    upd = None
    for i, x in enumerate(L):
        if x == "Updated" and i + 1 < len(L):
            upd = _iso(L[i + 1], "%d %b %Y")
            break
    return {"howto": howto, "updated": upd}


def parse_mw4intel_sitemap(xml):
    """Multiplayer loadout page slugs from sitemap.xml: no dmz-/warzone-/community pages, no builder or index pages."""
    out = []
    for m in re.finditer(r"<loc>https?://[^/]+/loadouts/([^<]+)</loc>", xml):
        slug = m.group(1).strip("/")
        if "/" in slug or slug.startswith(("dmz-", "warzone-")) or slug in ("builder", "community"):
            continue
        out.append(slug)
    return out


# ------------------------------------------------------------------ Dexerto
def parse_dexerto(L):
    """Dexerto wiki weapon page: attachments as (name, slot) pairs, perks, equipment, and its 'Updated' else
    'Published' date. None when the page has no loadout."""
    if "Attachments" not in L:
        return None
    i = L.index("Attachments") + 1
    parts = []
    while i + 1 < len(L) and L[i + 1] in SLOTS:
        parts.append([L[i + 1], L[i]])
        i += 2
    if not parts:
        return None
    perks, equip = [], []
    for j in range(i, len(L) - 1):
        if j > 0 and L[j - 1] == "[img] " + L[j]:   # an item row is: [img] Name / Name / Perks|Equipment|Killstreaks
            if L[j + 1] == "Perks":
                perks.append(L[j])
            elif L[j + 1] == "Equipment":
                equip.append(L[j])
    date = None
    for key in ("Updated:", "Published:"):
        if key in L and L.index(key) + 1 < len(L):
            date = _iso(L[L.index(key) + 1].rsplit(",", 1)[0], "%b %d, %Y")
            if date:
                break
    return {"parts": parts, "perks": perks, "equipment": equip, "date": date}
