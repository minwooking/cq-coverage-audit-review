#!/usr/bin/env python3
"""Expert-quality vs coverage analysis (standard library only).

Subcommands
  analyze : rater agreement, expert quality vs coverage (exact permutation tests), bootstrap, criteria
  power   : exact critical tau and simulated power for n artifacts (read before interpreting analyze)

Conventions
  * overall_rank 1 = best. Expert quality score q = mean over raters of (n_set + 1 - rank): higher = better.
  * Coverage unit = artifact group: identical-content variants (E, F) are one artifact; their coverage is
    the mean over members.
  * Rankings are within a set (batch). Pooling across sets uses a STRATIFIED Kendall tau-b (only
    within-set pairs; permutations within sets).
  * Directional hypothesis (registered in the addendum): tau > 0. One-sided exact permutation p is the
    primary p; two-sided is reported.
Output of this script must be reviewed before it is quoted anywhere.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

CRITERIA = ["Q1_concept_accuracy", "Q2_hierarchy", "Q3_relations", "Q4_naming_definitions", "Q5_task_fitness"]
EXACT_LIMIT = 1_000_000  # max permutations enumerated; above this use Monte Carlo
EPS = 1e-12


# ------------------------------------------------------------------ basic statistics
def mean(x):
    return sum(x) / len(x)


def avg_ranks(x):
    """Ascending average ranks (1 = smallest)."""
    order = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and x[order[j + 1]] == x[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def pearson(x, y):
    mx, my = mean(x), mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx < EPS or syy < EPS:
        return float("nan")
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def spearman(x, y):
    return pearson(avg_ranks(x), avg_ranks(y))


def _sgn(v):
    return (v > 0) - (v < 0)


def strat_tau_b(x, y, strata=None):
    """Kendall tau-b; with strata, only within-stratum pairs are used (sums, then one denominator)."""
    n = len(x)
    strata = strata or [0] * n
    c = d = tx = ty = n0 = 0
    for i in range(n):
        for j in range(i + 1, n):
            if strata[i] != strata[j]:
                continue
            n0 += 1
            sx, sy = _sgn(x[i] - x[j]), _sgn(y[i] - y[j])
            if sx == 0:
                tx += 1
            if sy == 0:
                ty += 1
            if sx and sy:
                if sx == sy:
                    c += 1
                else:
                    d += 1
    den = math.sqrt((n0 - tx) * (n0 - ty))
    return float("nan") if den == 0 else (c - d) / den


# ------------------------------------------------------------------ permutation tests
def _blocks(strata):
    idx = defaultdict(list)
    for i, s in enumerate(strata):
        idx[s].append(i)
    return list(idx.values())


def _n_perms(blocks):
    t = 1
    for b in blocks:
        t *= math.factorial(len(b))
        if t > 10 ** 12:
            break
    return t


def perm_null(stat, x, strata=None, seed=1, n_mc=100_000, limit=EXACT_LIMIT):
    """Return (list of statistic values under permutation of x within strata, is_exact)."""
    n = len(x)
    strata = strata or [0] * n
    blocks = _blocks(strata)
    if _n_perms(blocks) <= limit:
        vals = []
        per_block = [list(itertools.permutations([x[i] for i in b])) for b in blocks]
        for combo in itertools.product(*per_block):
            xs = list(x)
            for b, vals_b in zip(blocks, combo):
                for i, v in zip(b, vals_b):
                    xs[i] = v
            vals.append(stat(xs))
        return vals, True
    rng = random.Random(seed)
    vals = []
    for _ in range(n_mc):
        xs = list(x)
        for b in blocks:
            v = [x[i] for i in b]
            rng.shuffle(v)
            for i, w in zip(b, v):
                xs[i] = w
        vals.append(stat(xs))
    return vals, False


def perm_pvalues(stat, x, strata=None, seed=1, n_mc=100_000):
    obs = stat(x)
    if obs != obs:
        return {"obs": obs, "p_one_sided": float("nan"), "p_two_sided": float("nan"), "exact": None, "n_perm": 0}
    vals, exact = perm_null(stat, x, strata, seed, n_mc)
    vals = [v for v in vals if v == v]
    n = len(vals)
    ge = sum(1 for v in vals if v >= obs - EPS)
    ae = sum(1 for v in vals if abs(v) >= abs(obs) - EPS)
    if exact:
        p1, p2 = ge / n, ae / n
    else:
        p1, p2 = (ge + 1) / (n + 1), (ae + 1) / (n + 1)
    return {"obs": obs, "p_one_sided": p1, "p_two_sided": p2, "exact": exact, "n_perm": n}


def kendall_exact_counts(n):
    """Mahonian numbers: counts[k] = number of permutations of n with k inversions (no ties)."""
    counts = [1]
    for m in range(2, n + 1):
        new = [0] * (len(counts) + m - 1)
        for k, c in enumerate(counts):
            for t in range(m):
                new[k + t] += c
        counts = new
    return counts


def kendall_no_ties_p(n, tau_obs):
    """Exact one-sided P(tau >= tau_obs) for n objects, no ties."""
    n0 = n * (n - 1) // 2
    counts = kendall_exact_counts(n)
    tot = math.factorial(n)
    dmax = (n0 * (1 - tau_obs)) / 2 + EPS
    return sum(c for k, c in enumerate(counts) if k <= dmax) / tot


def critical_tau(n, alpha=0.05):
    """Smallest attainable tau with one-sided exact p <= alpha (no ties)."""
    n0 = n * (n - 1) // 2
    counts, tot = kendall_exact_counts(n), math.factorial(n)
    cum = 0
    best = None
    for k, c in enumerate(counts):
        cum += c
        if cum / tot <= alpha + EPS:
            best = 1 - 2 * k / n0
        else:
            break
    return best


# ------------------------------------------------------------------ agreement
def kendall_w(ranks):
    """ranks[rater][object] -> W with tie correction. Returns (W, m, n)."""
    m, n = len(ranks), len(ranks[0])
    R = [sum(r[i] for r in ranks) for i in range(n)]
    Rm = mean(R)
    S = sum((v - Rm) ** 2 for v in R)
    T = 0.0
    for r in ranks:
        cnt = defaultdict(int)
        for v in r:
            cnt[v] += 1
        T += sum(t ** 3 - t for t in cnt.values())
    den = m * m * (n ** 3 - n) - m * T
    return 12 * S / den if den > 0 else float("nan")


def w_pvalue(ranks, seed=1, n_mc=50_000):
    """Permutation p for W (rater 1 fixed, other raters' rankings permuted)."""
    m, n = len(ranks), len(ranks[0])
    obs = kendall_w(ranks)
    if m < 2 or obs != obs:
        return {"W": obs, "p": float("nan"), "exact": None}
    if math.factorial(n) ** (m - 1) <= EXACT_LIMIT:
        ge = tot = 0
        base = list(ranks[0])
        for combo in itertools.product(*[list(itertools.permutations(r)) for r in ranks[1:]]):
            w = kendall_w([base] + [list(c) for c in combo])
            ge += w >= obs - EPS
            tot += 1
        return {"W": obs, "p": ge / tot, "exact": True}
    rng, ge = random.Random(seed), 0
    for _ in range(n_mc):
        rs = [list(ranks[0])]
        for r in ranks[1:]:
            v = list(r)
            rng.shuffle(v)
            rs.append(v)
        ge += kendall_w(rs) >= obs - EPS
    return {"W": obs, "p": (ge + 1) / (n_mc + 1), "exact": False}


def icc_2(matrix):
    """Shrout-Fleiss ICC(2,1), ICC(2,k). matrix[target][rater], complete."""
    n, k = len(matrix), len(matrix[0])
    gm = mean([v for row in matrix for v in row])
    rm = [mean(row) for row in matrix]
    cm = [mean([matrix[i][j] for i in range(n)]) for j in range(k)]
    ssr = k * sum((v - gm) ** 2 for v in rm)
    ssc = n * sum((v - gm) ** 2 for v in cm)
    sst = sum((v - gm) ** 2 for row in matrix for v in row)
    sse = sst - ssr - ssc
    msr, msc = ssr / (n - 1), ssc / (k - 1) if k > 1 else float("nan")
    mse = sse / ((n - 1) * (k - 1))
    i1 = (msr - mse) / (msr + (k - 1) * mse + k * (msc - mse) / n)
    ik = (msr - mse) / (msr + (msc - mse) / n)
    return {"ICC2_1": i1, "ICC2_k": ik, "MSR": msr, "MSC": msc, "MSE": mse}


def krippendorff_alpha_interval(units):
    """units: list of lists of values (one list per object; missing values omitted)."""
    units = [u for u in units if len(u) >= 2]
    allv = [v for u in units for v in u]
    N = len(allv)
    if N < 2:
        return float("nan")
    do = 0.0
    for u in units:
        m = len(u)
        do += sum((a - b) ** 2 for a, b in itertools.permutations(u, 2)) / (m - 1)
    do /= N
    de = sum((a - b) ** 2 for a, b in itertools.permutations(allv, 2)) / (N * (N - 1))
    return float("nan") if de == 0 else 1 - do / de


# ------------------------------------------------------------------ loading
def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_coverage(path):
    """-> dict[(set, variant)] = {'J_pct': float|None, 'L1star_pct': float|None}"""
    out = {}
    for r in read_csv(path):
        out[(r["set"], r["variant"])] = {k: (float(r[k]) if r.get(k, "").strip() else None)
                                         for k in ("J_pct", "L1star_pct")}
    return out


def load_ratings(keys_dir, filled):
    """filled: dict rater -> csv path. Returns list of dict rows with set/variant/group/ratings."""
    rows = []
    for rid, path in filled.items():
        key = {r["artifact_id"]: r for r in read_csv(Path(keys_dir) / f"key_{rid}.csv")}
        for r in read_csv(path):
            k = key.get(r["artifact_id"])
            if k is None:
                raise SystemExit(f"{rid}: artifact_id {r['artifact_id']} not in key")
            rec = {"rater": rid, "set": k["set"], "variant": k["variant"],
                   "group": k["group_id"] + "/" + k["variant"],
                   "batch": k["batch"], "rank": _num(r["overall_rank"])}
            for c in CRITERIA:
                rec[c] = _num(r[c])
            rec["minutes"] = _num(r.get("minutes_spent", ""))
            rows.append(rec)
    return rows


def _num(v):
    v = (v or "").strip()
    return float(v) if v else None


def validate(rows):
    problems = []
    for r in rows:
        for c in CRITERIA:
            if r[c] is None or not 1 <= r[c] <= 5 or r[c] != int(r[c]):
                problems.append(f"{r['rater']} {r['group']}: {c} invalid ({r[c]})")
        if r["rank"] is None:
            problems.append(f"{r['rater']} {r['group']}: overall_rank missing")
    by = defaultdict(list)
    for r in rows:
        by[(r["rater"], r["set"])].append(r)
    for (rid, st), rs in by.items():
        ranks = sorted(x["rank"] for x in rs if x["rank"] is not None)
        if ranks and ranks != list(range(1, len(rs) + 1)):
            problems.append(f"{rid} set {st}: ranks {ranks} are not 1..{len(rs)} without ties")
    return problems


# ------------------------------------------------------------------ analysis
def build_tables(rows, coverage):
    """Per-set artifact tables. artifact key = group; coverage = mean over member variants."""
    sets = sorted({r["set"] for r in rows})
    raters = sorted({r["rater"] for r in rows})
    arts, tab = {}, {}
    for st in sets:
        groups = sorted({r["group"] for r in rows if r["set"] == st})
        arts[st] = groups
        for g in groups:
            members = g.rsplit("/", 1)[1].split("+")
            cov = {}
            for m in ("J_pct", "L1star_pct"):
                v = [coverage[(st, mm)][m] for mm in members if (st, mm) in coverage and coverage[(st, mm)][m] is not None]
                cov[m] = mean(v) if len(v) == len(members) else None
            tab[(st, g)] = {"members": members, "cov": cov}
    return sets, raters, arts, tab


def rater_matrix(rows, st, groups, raters, field):
    idx = {(r["rater"], r["group"]): r for r in rows if r["set"] == st}
    return [[idx[(rt, g)][field] for rt in raters] for g in groups]


def analyze(rows, coverage, seed=20261013, n_boot=5000, n_mc=100_000, w_threshold=0.6):
    sets, raters, arts, tab = build_tables(rows, coverage)
    n_by_set = {st: len(arts[st]) for st in sets}
    out = {"raters": raters, "n_artifacts": n_by_set, "sets": {}, "pooled": {}, "decision": {}}
    # --- agreement per set
    qual = {}  # (set, group) -> dict(rank_q, composite, criteria means)
    for st in sets:
        gs = arts[st]
        n = len(gs)
        rk = rater_matrix(rows, st, gs, raters, "rank")
        rank_by_rater = [[rk[i][j] for i in range(n)] for j in range(len(raters))]
        w = w_pvalue(rank_by_rater, seed=seed)
        comp = [[mean([rater_matrix(rows, st, gs, raters, c)[i][j] for c in CRITERIA]) for j in range(len(raters))]
                for i in range(n)]
        agree = {"kendall_W": w, "n": n,
                 "krippendorff_alpha_interval_rank": krippendorff_alpha_interval([[v for v in row] for row in rk]),
                 "krippendorff_alpha_interval_composite": krippendorff_alpha_interval(comp)}
        if len(raters) >= 2 and n >= 3:
            agree["ICC_composite"] = icc_2(comp)
            agree["ICC_by_criterion"] = {c: icc_2(rater_matrix(rows, st, gs, raters, c)) for c in CRITERIA}
        out["sets"][st] = {"artifacts": {g: tab[(st, g)]["members"] for g in gs}, "agreement": agree}
        for i, g in enumerate(gs):
            qual[(st, g)] = {
                "rank_score": mean([n + 1 - v for v in rk[i]]),
                "composite": mean(comp[i]),
                "composite_Q1_4": mean([mean([rater_matrix(rows, st, gs, raters, c)[i][j] for c in CRITERIA[:4]])
                                        for j in range(len(raters))]),
                **{c: mean(rater_matrix(rows, st, gs, raters, c)[i]) for c in CRITERIA}}
            out["sets"][st]["artifacts"][g] = {"members": tab[(st, g)]["members"], "coverage": tab[(st, g)]["cov"],
                                              "quality": qual[(st, g)]}
    # pooled composite ICC (absolute 1-5 scale comparable across sets)
    all_groups = [(st, g) for st in sets for g in arts[st]]
    if len(sets) > 1 and len(raters) >= 2:
        mat = []
        for st, g in all_groups:
            row = []
            for rt in raters:
                r = next(x for x in rows if x["rater"] == rt and x["group"] == g and x["set"] == st)
                row.append(mean([r[c] for c in CRITERIA]))
            mat.append(row)
        out["pooled"]["ICC_composite_all_artifacts"] = icc_2(mat)
        out["pooled"]["alpha_interval_composite"] = krippendorff_alpha_interval(mat)
    # --- adoption rule
    ws = {st: out["sets"][st]["agreement"]["kendall_W"]["W"] for st in sets}
    adopted = all(w == w and w >= w_threshold for w in ws.values())
    out["decision"]["W_by_set"] = ws
    out["decision"]["reference_ranking_adopted"] = adopted
    out["decision"]["w_threshold"] = w_threshold
    # --- coverage vs quality
    rng = random.Random(seed)
    for metric in ("L1star_pct", "J_pct"):
        for qname in ("rank_score", "composite", "composite_Q1_4"):
            keys = [(st, g) for st, g in all_groups if tab[(st, g)]["cov"][metric] is not None]
            if len(keys) < 4:
                continue
            sub_sets = sorted({st for st, _ in keys})
            x = [qual[k][qname] for k in keys]
            y = [tab[k]["cov"][metric] for k in keys]
            strata = [k[0] for k in keys]
            res = {"n": len(keys), "sets": sub_sets}
            # permute x (expert) against fixed y
            res["tau_b_stratified"] = perm_pvalues(lambda xs: strat_tau_b(xs, y, strata), x, strata, seed, n_mc)
            if len(sub_sets) == 1:
                res["spearman"] = spearman(x, y)
                res["spearman_perm"] = perm_pvalues(lambda xs: spearman(xs, y), x, None, seed, n_mc)
            else:
                res["tau_b_by_set"] = {s: strat_tau_b([a for a, k in zip(x, keys) if k[0] == s],
                                                      [b for b, k in zip(y, keys) if k[0] == s]) for s in sub_sets}
            res["bootstrap_artifacts"] = bootstrap_tau(x, y, strata, rng, n_boot)
            res["leave_one_rater_out"] = loro(rows, keys, tab, metric, qname, raters, arts, sets)
            res["max_attainable_tau_b"] = strat_tau_b(sorted(y), y, [0] * len(y)) if len(sub_sets) == 1 else None
            res["coverage_levels_distinct"] = len(set(round(v, 6) for v in y))
            out["pooled"][f"{metric}|{qname}"] = res
    # --- per criterion
    for metric in ("L1star_pct", "J_pct"):
        keys = [(st, g) for st, g in all_groups if tab[(st, g)]["cov"][metric] is not None]
        if len(keys) < 4:
            continue
        y = [tab[k]["cov"][metric] for k in keys]
        strata = [k[0] for k in keys]
        out["pooled"][f"{metric}|by_criterion"] = {
            c: perm_pvalues(lambda xs: strat_tau_b(xs, y, strata), [qual[k][c] for k in keys], strata, seed, n_mc)
            for c in CRITERIA}
    # --- decision classification (primary = J if available, else L1*)
    prim = "J_pct|rank_score" if "J_pct|rank_score" in out["pooled"] else None
    if prim:
        t = out["pooled"][prim]["tau_b_stratified"]
        if not adopted:
            cls = "reference ranking not adopted (W below threshold); tau reported descriptively"
        elif t["obs"] != t["obs"]:
            cls = "tau undefined"
        elif t["obs"] <= 0:
            cls = "tau <= 0: inconsistent with the directional hypothesis"
        elif t["p_one_sided"] < 0.05:
            cls = "tau > 0 and exact one-sided p < 0.05: consistent with the hypothesis"
        else:
            cls = "tau > 0 but not distinguishable from chance at this n"
        out["decision"]["primary_metric"] = prim
        out["decision"]["classification"] = cls
    return out


def bootstrap_tau(x, y, strata, rng, n_boot):
    blocks = _blocks(strata)
    taus = []
    for _ in range(n_boot):
        pick = []
        for b in blocks:
            pick += [rng.choice(b) for _ in b]
        t = strat_tau_b([x[i] for i in pick], [y[i] for i in pick], [strata[i] for i in pick])
        if t == t:
            taus.append(t)
    taus.sort()
    if len(taus) < 20:
        return {"n_valid": len(taus), "ci95": None}
    lo, hi = taus[int(0.025 * len(taus))], taus[min(len(taus) - 1, int(0.975 * len(taus)))]
    return {"n_valid": len(taus), "of": n_boot, "ci95": [lo, hi],
            "note": "percentile bootstrap over artifacts within sets; unstable at n<=12, indicative only"}


def loro(rows, keys, tab, metric, qname, raters, arts, sets):
    """Leave-one-rater-out tau (rater-uncertainty indication)."""
    res = {}
    for drop in raters:
        keep = [r for r in raters if r != drop]
        if len(keep) < 1:
            continue
        sub = [r for r in rows if r["rater"] in keep]
        qual = {}
        for st in sets:
            gs = arts[st]
            n = len(gs)
            for g in gs:
                rs = [r for r in sub if r["set"] == st and r["group"] == g]
                if qname == "rank_score":
                    qual[(st, g)] = mean([n + 1 - r["rank"] for r in rs])
                elif qname == "composite":
                    qual[(st, g)] = mean([mean([r[c] for c in CRITERIA]) for r in rs])
                else:
                    qual[(st, g)] = mean([mean([r[c] for c in CRITERIA[:4]]) for r in rs])
        res[drop] = strat_tau_b([qual[k] for k in keys], [tab[k]["cov"][metric] for k in keys], [k[0] for k in keys])
    return res


# ------------------------------------------------------------------ power
def power_table(ns, taus, alpha=0.05, n_sim=4000, seed=7, y_template=None):
    """Power of the one-sided exact test for population Kendall tau (bivariate normal, no rater noise).

    ns: list of per-stratum sizes (e.g. [6] or [5, 5]). y_template: optional coverage vector to reuse
    (keeps its tie pattern); otherwise y ~ continuous.
    """
    rng = random.Random(seed)
    strata = [i for i, n in enumerate(ns) for _ in range(n)]
    N = len(strata)
    ytmp = y_template if y_template is not None else [float(i) for i in range(N)]
    x0 = [float(i) for i in range(N)]  # the expert score has no ties; permute it against y
    null, exact = perm_null(lambda xs: strat_tau_b(xs, ytmp, strata), x0, strata, seed, 20_000)
    null = sorted(v for v in null if v == v)
    # critical value: smallest t with P(T>=t) <= alpha
    crit = None
    for v in sorted(set(null)):
        if sum(1 for u in null if u >= v - EPS) / len(null) <= alpha + EPS:
            crit = v
            break
    out = {"n": ns, "critical_tau_b": crit, "null_exact": exact, "power": {}}
    if crit is None:
        return out
    for tp in taus:
        rho = math.sin(math.pi * tp / 2)
        hit = 0
        for _ in range(n_sim):
            z = [rng.gauss(0, 1) for _ in range(N)]
            e = [rng.gauss(0, 1) for _ in range(N)]
            if y_template is None:
                y = z
            else:
                y = list(y_template)
                # latent follows the observed levels: standardized ranks
                rk = avg_ranks(y)
                m, s = mean(rk), math.sqrt(mean([(a - mean(rk)) ** 2 for a in rk])) or 1
                z = [(a - m) / s for a in rk]
            x = [rho * a + math.sqrt(1 - rho * rho) * b for a, b in zip(z, e)]
            t = strat_tau_b(x, y, strata)
            hit += (t == t and t >= crit - EPS)
        out["power"][tp] = hit / n_sim
    return out


def detectable_tau(ns, y_template=None, target=0.8, seed=7, n_sim=2000):
    grid = [round(0.05 * k, 2) for k in range(1, 20)] + [0.98]
    pt = power_table(ns, grid, 0.05, n_sim, seed, y_template)
    for tp in grid:
        if pt["power"].get(tp, 0) >= target:
            return tp, pt
    return None, pt


# ------------------------------------------------------------------ CLI
def fmt(o, ind=0):
    return json.dumps(o, indent=2, ensure_ascii=False, default=lambda v: float(v))


def cmd_analyze(a):
    filled = dict(kv.split("=", 1) for kv in a.filled)
    rows = load_ratings(a.keys_dir, filled)
    probs = validate(rows)
    if probs:
        print("VALIDATION PROBLEMS:\n  " + "\n  ".join(probs), file=sys.stderr)
        if not a.force:
            return 2
    res = analyze(rows, load_coverage(a.coverage), a.seed, a.n_boot, a.n_mc, a.w_threshold)
    txt = fmt(res)
    if a.json_out:
        Path(a.json_out).write_text(txt, encoding="utf-8")
    print(summarize(res))
    return 0


def summarize(res):
    L = [f"raters: {res['raters']}", f"artifacts per set: {res['n_artifacts']}"]
    for st, v in res["sets"].items():
        ag = v["agreement"]
        w = ag["kendall_W"]
        L.append(f"[{st}] Kendall W={w['W']:.3f} (perm p={w['p']:.4f}, exact={w['exact']}); "
                 f"alpha_interval rank={ag['krippendorff_alpha_interval_rank']:.3f}, "
                 f"composite={ag['krippendorff_alpha_interval_composite']:.3f}"
                 + (f"; ICC(2,1)={ag['ICC_composite']['ICC2_1']:.3f}, ICC(2,k)={ag['ICC_composite']['ICC2_k']:.3f}"
                    if "ICC_composite" in ag else ""))
        for g, d in v["artifacts"].items():
            L.append(f"    {g} ({'+'.join(d['members'])}): rank_score={d['quality']['rank_score']:.2f} "
                     f"composite={d['quality']['composite']:.2f} cov={d['coverage']}")
    for k, v in res["pooled"].items():
        if isinstance(v, dict) and "tau_b_stratified" in v:
            t = v["tau_b_stratified"]
            bt = v["bootstrap_artifacts"]["ci95"]
            L.append(f"{k}: n={v['n']} tau_b={t['obs']:.3f} p1={t['p_one_sided']:.4f} p2={t['p_two_sided']:.4f} "
                     f"exact={t['exact']} boot95={None if bt is None else [round(b, 3) for b in bt]} "
                     f"LORO={ {r: round(x, 2) for r, x in v['leave_one_rater_out'].items()} }")
    L.append("decision: " + json.dumps(res["decision"], ensure_ascii=False, default=float))
    return "\n".join(L)


def cmd_power(a):
    ycfg = None
    if a.coverage and a.set:
        cov = load_coverage(a.coverage)
        groups = defaultdict(list)
        for (st, v), d in cov.items():
            if st == a.set and d[a.metric] is not None:
                groups[v].append(d[a.metric])
        merged = defaultdict(list)
        for v, vals in groups.items():
            merged["+".join(sorted(m for m in a.merge.split("+") if m in groups)) if v in a.merge.split("+") else v].extend(vals)
        ycfg = [mean(v) for _, v in sorted(merged.items())]
    print("Exact one-sided critical tau (no ties), alpha=0.05:")
    for n in (4, 5, 6, 8, 10, 12):
        print(f"  n={n}: tau_crit={critical_tau(n):.3f}  (P at crit={kendall_no_ties_p(n, critical_tau(n)):.4f})")
    for ns in ([5], [6], [10], [12], [5, 5], [6, 6]):
        d, pt = detectable_tau(ns, None, 0.8, a.seed, a.n_sim)
        print(f"strata {ns}: critical tau_b={pt['critical_tau_b']}, "
              f"power at tau_pop " + ", ".join(f"{k}:{v:.2f}" for k, v in pt["power"].items() if k in (0.3, 0.5, 0.7, 0.9))
              + f"; smallest population tau with power>=0.8: {d}")
    if ycfg:
        d, pt = detectable_tau([len(ycfg)], ycfg, 0.8, a.seed, a.n_sim)
        print(f"observed coverage pattern ({a.set}, {a.metric}, distinct artifacts n={len(ycfg)}, "
              f"levels={sorted(set(round(v, 2) for v in ycfg))}): critical tau_b={pt['critical_tau_b']}, "
              f"power at 0.5/0.7/0.9: {pt['power'].get(0.5):.2f}/{pt['power'].get(0.7):.2f}/{pt['power'].get(0.9):.2f}; "
              f"smallest tau_pop with power>=0.8: {d}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("analyze")
    p.add_argument("--keys-dir", required=True)
    p.add_argument("--filled", nargs="+", required=True, help="R1=path R2=path ...")
    p.add_argument("--coverage", required=True)
    p.add_argument("--json-out")
    p.add_argument("--seed", type=int, default=20261013)
    p.add_argument("--n-boot", type=int, default=5000)
    p.add_argument("--n-mc", type=int, default=100000)
    p.add_argument("--w-threshold", type=float, default=0.6)
    p.add_argument("--force", action="store_true", help="continue despite validation problems")
    q = sub.add_parser("power")
    q.add_argument("--coverage")
    q.add_argument("--set", default="holdout")
    q.add_argument("--metric", default="J_pct")
    q.add_argument("--seed", type=int, default=7)
    q.add_argument("--n-sim", type=int, default=2000)
    q.add_argument("--merge", default="E+F", help="variants with identical content (one artifact)")
    a = ap.parse_args(argv)
    return cmd_analyze(a) if a.cmd == "analyze" else cmd_power(a)


if __name__ == "__main__":
    sys.exit(main())
