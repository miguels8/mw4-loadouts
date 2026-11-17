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
        j = i - 2
        while j > 0 and L[j] != "Last Updated:":
            j -= 1
        date = _iso(L[j + 1], "%d/%m/%Y") if L[j] == "Last Updated:" and j + 1 < len(L) else None
        rank = L[i + 2] if i + 2 < len(L) and L[i + 1] == "#" else None
        k = i
        while k < len(L) and L[k] != "Weapon Level for this loadout":
            k += 1
        blk = L[i:k]
        parts, apex, tags, m = [], None, [], 0
        while m < len(blk):
            if blk[m] in ("Pro Favorite", "Buff", "Nerf", "Apex") and m < 8:
                tags.append(blk[m])
            lv = LEVEL.match(blk[m + 1]) if m + 1 < len(blk) else None
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
                       "weapon_level": wl, "tags": tags})
    return builds


def _table(L):
    """Attachment table: name -> [slot, unlock level]; optic name -> label (the site's own size word)."""
    try:
        start = L.index("Attachment name")
    except ValueError:
        return {}, {}
    table, labels, i = {}, {}, start
    while i < len(L) - 2:
        if L[i + 1] in SLOTS and L[i + 2].startswith("Level ") and L[i + 2][6:].isdigit():
            table.setdefault(L[i], [L[i + 1], int(L[i + 2][6:])])
            if L[i + 1] == "Optic":
                cand = L[i + 3] if i + 3 < len(L) else ""
                nxt_is_row = i + 5 < len(L) and L[i + 4] in SLOTS and L[i + 5].startswith("Level ")
                labels.setdefault(L[i], "" if STAT.match(cand) or nxt_is_row else cand)
            i += 3
        else:
            i += 1
    return table, labels


def parse_codmunity(L):
    table, labels = _table(L)
    return {"title": L[0] if L else "", "builds": _builds(L), "table": table, "optic_labels": labels}


def parse_infil(L):
    """Infil 'Early game' build: [slot, part, weapon level] list plus the level where it is complete."""
    out = {"checked": None, "early": None}
    for i, ln in enumerate(L):
        if ln == "Checked" and i + 1 < len(L):
            out["checked"] = _iso(L[i + 1], "%b %d, %Y")
            break
    if "Early game build" not in L:
        return out
    i = L.index("Early game build") + 1
    parts = []
    while i + 3 < len(L) and L[i] != "Copy build":
        if L[i].isdigit() and L[i + 2].startswith("Weapon Lvl "):
            slot = INFIL_SLOTS.get(L[i + 1], L[i + 1])
            parts.append([slot, L[i + 3], int(L[i + 2][11:])])
            i += 4
        else:
            i += 1
    complete = None
    if "Early game" in L:
        j = L.index("Early game") + 1
        if j < len(L) and L[j].startswith("Weapon Lvl ") and L[j][11:].isdigit():
            complete = int(L[j][11:])
    if parts:
        out["early"] = {"complete_level": complete if complete is not None else max(p[2] for p in parts), "parts": parts}
    return out
