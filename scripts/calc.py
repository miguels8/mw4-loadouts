"""Calculated picks (ladder step 3) and the Q4 gate. Pure functions, stdlib only, no AI.

Per-part stats are the CODMunity attachment table's own deltas. ONE global weight table per profile
(site/data/stat_weights.json) turns them into a score; there are no per-gun weights. A gun may use calculated picks only
when, at max level, the calculation reproduces the CODMunity build in >= 4 of 5 slots (Miguel's Q4)."""

NO_BIG_SCOPE = {"AR", "SMG", "LMG", "Marksman"}
PROFILES = ("close", "range")


def score(part_stats, weights, profile):
    """Sum of direction x weight x value over the stats a part changes. A stat with no weight counts nothing."""
    total = 0.0
    for stat, val in (part_stats or {}).items():
        w = weights["stats"].get(stat)
        if w:
            total += w["dir"] * w[profile] * val
    return total


def _eligible(name, row, gun_type, rules):
    if row["slot"] == "Apex" or row["level"] is None:
        return False   # an Apex is its own thing; an unknown unlock level can never be shown as open
    if row["slot"] == "Optic":
        if rules.get("iron_sights"):
            return False
        if gun_type in NO_BIG_SCOPE and rules["optics"].get(name) != "dot":
            return False
    return True


def calc_build(table, weights, profile, gun_type, rules, n=5):
    """The calculated build: the best-scoring part of each slot, then the n best slots (n distinct slots).
    table: {name: {slot, level, stats}}; rules: {optics: {name: dot|scope|iron}, iron_sights: bool}."""
    best = {}
    for name, row in table.items():
        if not _eligible(name, row, gun_type, rules):
            continue
        s = score(row["stats"], weights, profile)
        cur = best.get(row["slot"])
        # ties: higher unlock level, then name, so the result never depends on dict order
        key = (s, row["level"], name)
        if cur is None or key > cur[0]:
            best[row["slot"]] = (key, name, row["level"])
    ranked = sorted(best.items(), key=lambda kv: (-kv[1][0][0], kv[0]))
    return [[slot, v[1], v[2]] for slot, v in ranked[:n] if v[0][0] > 0]


def gate(calc, pro):
    """Match = same slot AND same part name. Pass when matched >= 4 of the pro build's parts (of >= 4)."""
    cs = {(p[0], p[1]) for p in calc}
    matched = sum(1 for p in pro if (p[0], p[1]) in cs)
    of = len(pro)
    return {"pass": of >= 4 and matched >= 4, "matched": matched, "of": of}


def gun_gate(table, weights, pro, pro_type, gun_type, rules):
    """The per-gun Q4 record: {pass, matched, of, calc, pro, profile, reason}."""
    profile = "close" if pro_type == "Close Range" else "range"
    base = {"pass": False, "matched": 0, "of": len(pro), "calc": [], "pro": [[p[0], p[1]] for p in pro],
            "profile": profile, "reason": None}
    if not any(r["stats"] for r in table.values()):
        return {**base, "reason": "no stats published"}
    calc = calc_build(table, weights, profile, gun_type, rules)
    g = gate(calc, pro)
    out = {**base, **g, "calc": [[p[0], p[1]] for p in calc]}
    if len(pro) < 4:
        out["reason"] = "the CODMunity build has fewer than 4 parts"
    elif not g["pass"]:
        out["reason"] = f"{g['matched']} of {g['of']} slots match the CODMunity build"
    return out


def cands(table, weights, passed):
    """Every candidate part per slot: {slot: [{name, level, score?}]}. Scores (both profiles) only when the gate passed,
    best range-profile score first; otherwise lowest unlock level first and no score at all."""
    out = {}
    for name, row in table.items():
        if row["slot"] == "Apex":
            continue
        c = {"name": name, "level": row["level"]}
        if passed:
            c["score"] = {p: round(score(row["stats"], weights, p), 2) for p in PROFILES}
        out.setdefault(row["slot"], []).append(c)
    for lst in out.values():
        if passed:
            lst.sort(key=lambda c: (-c["score"]["range"], c["level"] if c["level"] is not None else 999, c["name"]))
        else:
            lst.sort(key=lambda c: (c["level"] if c["level"] is not None else 999, c["name"]))
    return dict(sorted(out.items()))
