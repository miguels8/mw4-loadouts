#!/usr/bin/env python3
"""One-time helper: cut small, real fixtures out of saved CODMunity/Infil page text.

Usage: make_fixtures.py SAVED_TEXT_DIR OUT_DIR   (SAVED_TEXT_DIR holds <slug>.txt, one text node per line)
Each fixture keeps the page title, the Multiplayer build blocks and the head of the attachment table,
wrapped one text node per <div> so the real HTML-to-lines parser reads it. Not run in CI."""
import html
import os
import sys

TABLE_ROWS = 100000


def wrap(lines):
    return "<html><body>\n" + "\n".join(f"<div>{html.escape(x)}</div>" for x in lines) + "\n</body></html>\n"


def cut_codmunity(L):
    first = next(i for i, x in enumerate(L) if x == "Loadout (MW4 Multiplayer)")
    start = first
    while L[start] != "Last Updated:":
        start -= 1
    last = max(i for i, x in enumerate(L) if x == "Weapon Level for this loadout")
    table = L.index("Attachment name")
    notes = []
    if "Nerfs & Buffs - Patch Notes" in L:   # the per-gun balance list (dates), cut up to the attachment section
        n0 = L.index("Nerfs & Buffs - Patch Notes")
        n1 = next((i for i in range(n0, len(L)) if L[i].startswith("All the attachments")), table)
        notes = L[n0:n1]
    return [L[0]] + L[start - 1:last + 3] + notes + L[table:table + TABLE_ROWS]


def cut_visible(L, keep):
    """Generic cut: the first line plus every line from index keep[0] to keep[1]."""
    return [L[0]] + L[keep[0]:keep[1]]


def from_html(path):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
    import mw4_parse as P
    return P.html_lines(open(path, encoding="utf-8").read())


def live(raw, out):
    """Cut the 2026-11-17 live pages (raw/<name>.html saved with curl) into fixtures for the variants parsers."""
    os.makedirs(out, exist_ok=True)
    for g in ("m4", "kg-7-vulcan", "han-86"):
        L = from_html(f"{raw}/cm-{g}.html")
        open(f"{out}/codmunity-live-{g}.html", "w", encoding="utf-8").write(wrap(cut_codmunity(L)))
        L = from_html(f"{raw}/inf-{g}.html")
        end = next(i for i, x in enumerate(L) if x in ("Your " + g.upper() + " camos", "More assault rifles") or x.startswith("Your "))
        open(f"{out}/infil-live-{g}.html", "w", encoding="utf-8").write(wrap(L[:end]))
    L = from_html(f"{raw}/inf-patches.html")
    open(f"{out}/infil-patches.html", "w", encoding="utf-8").write(wrap(L[:40]))
    for n in ("domination-m4-flag-control", "hijack-m4-defuse-cover", "search-and-destroy-suppressed-m4-entry",
              "m4-all-rounder", "pro-dashy-m4"):
        L = from_html(f"{raw}/mi-{n}.html")
        end = next(i for i, x in enumerate(L) if x == "Where next")
        open(f"{out}/mi-{n}.html", "w", encoding="utf-8").write(wrap(L[:end]))
    L = from_html(f"{raw}/mi-weapon-m4.html")
    a = L.index("Updated")
    b = next(i for i, x in enumerate(L) if x.startswith("Stats") and i > a + 30)
    open(f"{out}/mi-weapon-m4.html", "w", encoding="utf-8").write(wrap([L[0]] + L[a - 6:b]))
    open(f"{out}/mi-sitemap.xml", "w", encoding="utf-8").write(open(f"{raw}/mi-sitemap.xml", encoding="utf-8").read())
    L = from_html(f"{raw}/dx-patriot-xmr.html")
    a = next(i for i, x in enumerate(L) if x == "Published:")
    b = next(i for i, x in enumerate(L) if x == "Related Items")
    open(f"{out}/dx-patriot-xmr.html", "w", encoding="utf-8").write(wrap([L[0]] + L[a - 4:b]))


def main(src, out):
    if src == "--live":   # make_fixtures.py --live RAW_DIR OUT_DIR
        return live(out, sys.argv[3])
    os.makedirs(out, exist_ok=True)
    for slug in sys.argv[3:] or ["m4", "kg-7-vulcan", "mosin-nagant", "oris-8-6"]:
        L = open(f"{src}/{slug}.txt", encoding="utf-8").read().split("\n")
        open(f"{out}/codmunity-{slug}.html", "w", encoding="utf-8").write(wrap(cut_codmunity(L)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
