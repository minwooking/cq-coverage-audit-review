#!/usr/bin/env python3
"""Multi-rater agreement (stdlib only).

S (binary): Fleiss kappa, Krippendorff alpha (nominal), pairwise Cohen kappa.
R (ordinal): Krippendorff alpha (ordinal metric).
Vs judge: each rater / majority / adjudicated S against J>=2, with Cohen kappa
and a one-sided Clopper-Pearson interval on raw agreement (cell level) plus a
cluster-level (per CQ) one-sided upper bound on the silent over-credit rate.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from pathlib import Path

# ---------- basic stats ----------

def cohen_kappa(a: list[int], b: list[int]) -> float:
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def fleiss_kappa_counts(counts: list[list[int]]) -> float:
    """counts[i][j] = number of raters assigning item i to category j (constant n)."""
    N = len(counts)
    n = sum(counts[0])
    if any(sum(r) != n for r in counts):
        raise ValueError("Fleiss needs a constant number of ratings per item")
    k = len(counts[0])
    pj = [sum(r[j] for r in counts) / (N * n) for j in range(k)]
    Pi = [(sum(x * x for x in r) - n) / (n * (n - 1)) for r in counts]
    Pbar = sum(Pi) / N
    Pe = sum(p * p for p in pj)
    return 1.0 if Pe == 1 else (Pbar - Pe) / (1 - Pe)


def krippendorff_alpha(units: list[list], level: str = "nominal", values: list | None = None) -> float:
    """units: list of lists of ratings per unit (None = missing). level: nominal|ordinal."""
    units = [[v for v in u if v is not None] for u in units]
    units = [u for u in units if len(u) >= 2]
    cats = sorted(set(values) if values is not None else {v for u in units for v in u})
    idx = {c: i for i, c in enumerate(cats)}
    k = len(cats)
    o = [[0.0] * k for _ in range(k)]
    for u in units:
        m = len(u)
        for x, y in itertools.permutations(range(m), 2):
            o[idx[u[x]]][idx[u[y]]] += 1.0 / (m - 1)
    nc = [sum(row) for row in o]
    n = sum(nc)
    if n <= 1:
        return float("nan")

    def delta2(i: int, j: int) -> float:
        if i == j:
            return 0.0
        if level == "nominal":
            return 1.0
        lo, hi = min(i, j), max(i, j)
        s = sum(nc[lo:hi + 1]) - (nc[lo] + nc[hi]) / 2.0
        return s * s

    Do = sum(o[i][j] * delta2(i, j) for i in range(k) for j in range(k)) / n
    De = sum(nc[i] * nc[j] * delta2(i, j) for i in range(k) for j in range(k)) / (n * (n - 1))
    if De == 0:
        return 1.0 if Do == 0 else float("nan")
    return 1.0 - Do / De


def _binom_cdf(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def cp_upper(x: int, n: int, conf: float = 0.975) -> float:
    """One-sided Clopper-Pearson upper bound: P(X<=x | p)=1-conf."""
    if n == 0:
        return float("nan")
    if x >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if _binom_cdf(x, n, mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cp_lower(x: int, n: int, conf: float = 0.975) -> float:
    if n == 0:
        return float("nan")
    if x <= 0:
        return 0.0
    return 1.0 - cp_upper(n - x, n, conf)

# ---------- IO ----------

def read_key(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8") as fh:
        return {r["opaque_id"]: r["cell_id"] for r in csv.DictReader(fh)}


def read_rater(sheet: Path, key: Path) -> dict[str, dict]:
    km = read_key(key)
    out = {}
    with sheet.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cid = km.get(r["cell_id"])
            if cid is None:
                raise ValueError(f"unknown opaque id {r['cell_id']!r} in {sheet}")
            s, rr = r.get("S_label", "").strip(), r.get("R_score", "").strip()
            out[cid] = {"S": int(s) if s != "" else None, "R": int(rr) if rr != "" else None}
    return out


def majority(vals: list[int | None]) -> int | None:
    v = [x for x in vals if x is not None]
    if not v:
        return None
    ones = sum(v)
    if ones * 2 > len(v):
        return 1
    return 0  # strict majority needed for 1; tie -> unsupported-first (S=0)

# ---------- analysis ----------

def vs_judge(name: str, labels: dict[str, int], judge: dict[str, int], conf: float) -> dict:
    cells = [c for c in labels if c in judge and labels[c] is not None]
    s = [labels[c] for c in cells]
    j = [1 if judge[c] >= 2 else 0 for c in cells]
    agree = sum(x == y for x, y in zip(s, j))
    # over-credit event: J>=2 and S=0; cluster = CQ id (last token of cell_id)
    ev = [c for c in cells if judge[c] >= 2 and labels[c] == 0]
    clusters = {c.rsplit(":", 1)[-1] for c in cells}
    ev_cl = {c.rsplit(":", 1)[-1] for c in ev}
    return {"who": name, "n_cells": len(cells), "kappa_vs_J_ge2": cohen_kappa(s, j),
            "raw_agreement": agree / len(cells) if cells else None,
            "agreement_CP_lower": cp_lower(agree, len(cells), conf),
            "overcredit_cells": len(ev), "overcredit_clusters": len(ev_cl), "n_clusters": len(clusters),
            "overcredit_cluster_CP_upper": cp_upper(len(ev_cl), len(clusters), conf)}


def analyze(raters: dict[str, dict[str, dict]], judge: dict[str, int] | None,
            adjudicated: dict[str, int] | None, conf: float = 0.975) -> dict:
    ids = sorted(raters)
    cells = sorted(set.intersection(*[set(raters[r]) for r in ids]))
    res: dict = {"raters": ids, "n_cells_common": len(cells)}
    S = {r: {c: raters[r][c]["S"] for c in cells} for r in ids}
    complete = [c for c in cells if all(S[r][c] is not None for r in ids)]
    res["n_cells_complete_S"] = len(complete)
    counts = [[sum(S[r][c] == 0 for r in ids), sum(S[r][c] == 1 for r in ids)] for c in complete]
    res["S_fleiss_kappa"] = fleiss_kappa_counts(counts) if complete and len(ids) >= 2 else None
    res["S_krippendorff_alpha_nominal"] = krippendorff_alpha([[S[r][c] for r in ids] for c in cells], "nominal")
    res["S_pairwise_cohen_kappa"] = {
        f"{a}-{b}": cohen_kappa([S[a][c] for c in complete], [S[b][c] for c in complete])
        for a, b in itertools.combinations(ids, 2)}
    rv = sorted({raters[r][c]["R"] for r in ids for c in cells if raters[r][c]["R"] is not None})
    res["R_levels"] = rv
    res["R_krippendorff_alpha_ordinal"] = (
        krippendorff_alpha([[raters[r][c]["R"] for r in ids] for c in cells], "ordinal", rv) if rv else None)
    maj = {c: majority([S[r][c] for r in ids]) for c in cells}
    res["n_unanimous"] = sum(len({S[r][c] for r in ids}) == 1 for c in complete)
    res["n_disagree_cells"] = len(complete) - res["n_unanimous"]
    if judge:
        rows = [vs_judge(r, S[r], judge, conf) for r in ids]
        rows.append(vs_judge("majority", maj, judge, conf))
        if adjudicated:
            rows.append(vs_judge("adjudicated", adjudicated, judge, conf))
        res["vs_judge"] = rows
        res["conf"] = conf
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--keys-dir", required=True, type=Path)
    ap.add_argument("--filled", required=True, nargs="+", help="RATER_ID=filled_sheet.csv ...")
    ap.add_argument("--judge-key", type=Path, help="CSV with cell_id,J (author-side; raters never see it)")
    ap.add_argument("--adjudicated", type=Path, help="CSV with cell_id,S_final")
    ap.add_argument("--conf", type=float, default=0.975)
    ap.add_argument("--json-out", type=Path)
    a = ap.parse_args(argv)
    raters = {}
    for spec in a.filled:
        rid, _, p = spec.partition("=")
        raters[rid] = read_rater(Path(p), a.keys_dir / f"key_{rid}.csv")
    judge = adj = None
    if a.judge_key:
        with a.judge_key.open(newline="", encoding="utf-8") as fh:
            judge = {r["cell_id"]: int(r["J"]) for r in csv.DictReader(fh)}
    if a.adjudicated:
        with a.adjudicated.open(newline="", encoding="utf-8") as fh:
            adj = {r["cell_id"]: int(r["S_final"]) for r in csv.DictReader(fh)}
    res = analyze(raters, judge, adj, a.conf)
    txt = json.dumps(res, indent=2, ensure_ascii=False)
    print(txt)
    if a.json_out:
        a.json_out.write_text(txt, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
