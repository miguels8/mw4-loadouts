#!/usr/bin/env python3
"""Writes the review tables Opus and Miguel read after a refresh: per-gun Q4 gate, variants per gun with sources and dates,
dropped builds by site (Q6), builds whose "best for" fell to the default (Q10), guns with no variant.

  make_report.py [--data-dir site/data]   prints markdown on stdout (stdlib only, read-only)"""
import argparse
import collections
import json
import os


def load(d, name, default):
    try:
        with open(os.path.join(d, name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def report(d):
    w = load(d, "weapons.json", {"guns": []})
    gate = load(d, "calc_gate.json", {})
    st = load(d, "status.json", {})
    out = ["## Q4 gate: does the calculation reproduce the CODMunity build in at least 4 of 5 slots? (per gun)", "",
           "| gun | pass | matched | profile | reason |", "|---|---|---|---|---|"]
    for g in w["guns"]:
        x = gate.get(g["slug"], {})
        out.append(f"| {g['slug']} | {'PASS' if x.get('pass') else 'fail'} | {x.get('matched', '-')}/{x.get('of', '-')} | "
                   f"{x.get('profile', '-')} | {x.get('reason') or ''} |")
    passed = sum(1 for g in w["guns"] if gate.get(g["slug"], {}).get("pass"))
    out += ["", f"{passed} of {len(w['guns'])} guns may use calculated picks (step 3); every other gun never does.", "",
            "## Variants per gun (site, build name, date)", ""]
    total = 0
    for g in w["guns"]:
        vs = g.get("variants", [])
        total += len(vs)
        out.append(f"### {g['name']} ({g['slug']}) - patch date {g.get('patch_date') or 'none recorded'} - {len(vs)} variant(s)")
        for v in vs:
            srcs = "; ".join(f"{s['site']}: {s['name']} ({s['date']})" for s in v["sources"])
            out.append(f"- `{v['id']}` {v['type']} - best for {', '.join(v['best_for'][:4])}{'...' if len(v['best_for']) > 4 else ''} "
                       f"[{v['best_for_source']}] - {v['agree']} site(s) agree - {srcs}")
        if not vs:
            out.append("- no build re-checked since the patch")
        out.append("")
    by_site = collections.Counter()
    guns_lost = []
    for g in w["guns"]:
        for dr in g.get("dropped", []):
            by_site[dr["site"]] += 1
        if not g.get("variants") and g.get("dropped"):
            guns_lost.append(g["slug"])
    out += ["## Dropped before the latest balance patch (Q6)", "", ", ".join(f"{k}: {v}" for k, v in sorted(by_site.items())) or "none",
            "", f"Guns left with no variant: {', '.join(guns_lost) or 'none'}", "",
            "## Builds whose 'best for' fell to the default (Versatile, source default)", ""]
    dflt = [f"{g['slug']}: {s['site']} {s['name']}" for g in w["guns"] for v in g.get("variants", [])
            if v["best_for_source"] == "default" for s in v["sources"]]
    out += [f"- {x}" for x in dflt] or ["- none"]
    out += ["", f"Totals: {len(w['guns'])} guns, {total} variants. status: checked_at {st.get('checked_at')}, failed {st.get('failed')}, "
                f"patch {st.get('patch')}"]
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "site", "data"))
    print(report(ap.parse_args().data_dir))
