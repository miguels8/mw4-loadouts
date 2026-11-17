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
    return [L[0]] + L[start - 1:last + 3] + L[table:table + TABLE_ROWS]


def main(src, out):
    os.makedirs(out, exist_ok=True)
    for slug in sys.argv[3:] or ["m4", "kg-7-vulcan", "mosin-nagant", "oris-8-6"]:
        L = open(f"{src}/{slug}.txt", encoding="utf-8").read().split("\n")
        open(f"{out}/codmunity-{slug}.html", "w", encoding="utf-8").write(wrap(cut_codmunity(L)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
