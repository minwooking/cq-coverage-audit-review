#!/usr/bin/env python3
"""Shared loaders and statistics for the review-6 zero-cost reanalyses (R1-R9).

POST HOC, EXPLORATORY.  No LLM call, no new label.  Every interval is a
question(CQ)-clustered BCa interval with the registered seed 20260913 and
B = 10,000 (the same resampling as harness/analyze_holdout.py).

Inputs read (all committed / unsealed, none of the sealed key or export files):
  harness/real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json
      188 primary cells: J, AH label A, AH rater score rater_L1 (unsealed by PREREG sec.14.1)
  annotation/second_pass_2026-10-13/v3/results_v3_cells.json
      second rater's S (stored in field A) and R (stored in field rater_L1), same 188 cells
  harness/real_run/cells.jsonl                       registered judge J (224 cells)
  harness/length_experiment/cells_length.jsonl       substitute judge (luna) full A / limited / subgraph
  harness/length_experiment/luna_full_r35/cells_luna_full_r35.jsonl   luna full view B-F
  harness/real_run/paired_ai_audit_48/*/cells.jsonl  luna / sonnet on 48 cells

``fast_bca`` re-implements the analyzer's cluster bootstrap in vectorised form
(identical draws: same seed, sorted cluster order, one ``rng.integers(0, n, n)``
per resample, the analyzer's own ``_bca_interval``) and is checked against
``analyze_holdout.cluster_bootstrap_stat`` in ``selfcheck.py``.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
H = HERE.parent                      # paper/access2026/harness
PAPER = H.parent                     # paper/access2026
sys.path.insert(0, str(H))
import analyze_holdout as ah  # noqa: E402

SEED = ah.REGISTERED_SEED            # 20260913
B = ah.BOOTSTRAP_RESAMPLES           # 10000
TIES = ah.DEFAULT_BCA_TIES           # midrank
VARIANTS = list("ABCDEF")

P_AH = H / "real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json"
P_V3 = PAPER / "annotation/second_pass_2026-10-13/v3/results_v3_cells.json"
P_CELLS = H / "real_run/cells.jsonl"
P_LEN = H / "length_experiment/cells_length.jsonl"
P_LUNA_FULL = H / "length_experiment/luna_full_r35/cells_luna_full_r35.jsonl"
P_PANEL = H / "real_run/paired_ai_audit_48"
P_LIST48 = H / "real_run/second_annotator/cell_list_48.txt"


# ---------------------------------------------------------------- loaders
def load_188() -> pd.DataFrame:
    """188 primary cells with J, S_AH, R_AH (AH labels) and S_2, R_2 (second rater)."""
    ahc = pd.DataFrame(json.load(open(P_AH))["primary_cells"])
    v3 = pd.DataFrame(json.load(open(P_V3))["primary_cells"])
    d = ahc[["cell_id", "cq_id", "category", "variant", "J", "A", "rater_L1", "draft_A", "L1_star"]].rename(
        columns={"A": "S_AH", "rater_L1": "R_AH", "L1_star": "L1star_AH"})
    v = v3[["cell_id", "J", "A", "rater_L1", "L1_star"]].rename(
        columns={"J": "J_v3", "A": "S_2", "rater_L1": "R_2", "L1_star": "L1star_2"})
    d = d.merge(v, on="cell_id", validate="1:1")
    assert (d.J == d.J_v3).all(), "J differs between AH and second-rater result files"
    d = d.drop(columns="J_v3")
    d["cluster_id"] = d.cq_id
    assert len(d) == 188 and d.cq_id.nunique() == 33
    assert d.groupby("variant").size().to_dict() == {"A": 23, "B": 33, "C": 33, "D": 33, "E": 33, "F": 33}
    for c in ("J", "S_AH", "R_AH", "S_2", "R_2"):
        d[c] = d[c].astype(int)
    # internal consistency with the analyzer's L1* definition
    for sc, lc in (("S_AH", "L1star_AH"), ("S_2", "L1star_2")):
        calc = np.where(d[sc] == 1, d.J, np.minimum(d.J, 1))
        assert (calc == d[lc]).all()
    d["S_AH"] = d["S_AH"].astype(int)
    return d


def load_registered_J() -> pd.DataFrame:
    c = pd.read_json(P_CELLS, lines=True)
    return c


def jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path) if l.strip()]


def valid_score(r: dict) -> bool:
    j = r.get("J")
    return bool(r.get("judge_response_parsed")) and type(j) is int and 0 <= j <= 3


# ---------------------------------------------------------------- bootstrap
def cluster_matrix(df: pd.DataFrame, cols: list[str], cluster="cluster_id") -> tuple[np.ndarray, list[str]]:
    """per-cluster additive statistics, clusters in sorted string order (analyzer order)."""
    g = df.groupby(df[cluster].astype(str))[cols].sum()
    g = g.sort_index()
    return g.to_numpy(dtype=float), list(g.index)


_IDX_CACHE: dict = {}


def draw_indices(n: int, B_: int = B, seed: int = SEED) -> np.ndarray:
    key = (n, B_, seed)
    if key not in _IDX_CACHE:
        rng = np.random.default_rng(seed)
        _IDX_CACHE[key] = np.stack([rng.integers(0, n, n) for _ in range(B_)])
    return _IDX_CACHE[key]


def fast_bca(M: np.ndarray, f, B_: int = B, seed: int = SEED, ties: str = TIES) -> dict:
    """BCa 95% and 90% interval for f(sum over clusters of M).

    M: (n_clusters, k) additive per-cluster statistics (sorted cluster order);
    f: callable (m, k) -> (m,).  Same draws as analyze_holdout.cluster_bootstrap_stat."""
    n = M.shape[0]
    tot = M.sum(0)
    theta = float(f(tot[None, :])[0])
    idx = draw_indices(n, B_, seed)
    boot = f(M[idx].sum(1))
    jack = f(tot[None, :] - M)
    bad = ~np.isfinite(boot)
    out_extra = {}
    if bad.any():
        out_extra["n_undefined_resamples"] = int(bad.sum())
        boot = boot[~bad]
    lo, hi = ah._bca_interval(theta, boot, jack, 0.05, ties)
    lo90, hi90 = ah._bca_interval(theta, boot, jack, 0.10, ties)
    return {"est": theta, "lo": float(lo), "hi": float(hi), "lo90": float(lo90), "hi90": float(hi90),
            "n_clusters": n, "B": B_, "seed": seed, **out_extra}


def ci_str(r: dict, nd: int = 3, scale: float = 1.0) -> str:
    return f"{r['est']*scale:.{nd}f} [{r['lo']*scale:.{nd}f}, {r['hi']*scale:.{nd}f}]"


def mean_bca(df: pd.DataFrame, col: str) -> dict:
    """BCa for the pooled cell mean of df[col] (cells grouped by CQ)."""
    d = df.assign(_x=df[col].astype(float), _n=1.0)
    M, _ = cluster_matrix(d, ["_x", "_n"])
    return fast_bca(M, lambda s: s[:, 0] / s[:, 1])


def paired_delta(x: pd.Series, y: pd.Series) -> dict:
    """paired BCa for mean(y - x) over the CQs both series index (one cell per CQ)."""
    sh = sorted(set(x.index) & set(y.index))
    diff = (y.loc[sh].astype(float) - x.loc[sh].astype(float))
    M = diff.to_numpy()[:, None]
    # clusters in sorted string order, as in the analyzer
    order = np.argsort([str(i) for i in sh], kind="stable")
    M = M[order]
    r = fast_bca(M, lambda s: s[:, 0] / len(sh))
    d = diff.to_numpy()
    r.update({"n_pairs": len(sh), "n_up": int((d > 0).sum()), "n_down": int((d < 0).sum()),
              "n_tie": int((d == 0).sum()), "sd_diff": float(d.std(ddof=1)) if len(d) > 1 else None,
              "diffs": d.tolist(), "cqs": [sh[i] for i in range(len(sh))]})
    return r


# ---------------------------------------------------------------- tests
def signflip_exact_p(d) -> dict:
    """Exact two-sided sign-flip permutation p for integer paired differences d.

    H0: each d_i symmetric about 0 (sign exchangeable).  Statistic: sum d.  P(|S| >= |S_obs|)
    from the exact distribution (dynamic programming over integer |d_i|); also the
    one-sided tail in the direction of the observed sum."""
    d = [int(round(x)) for x in d]
    assert all(abs(x - y) < 1e-9 for x, y in zip(d, d))
    nz = [abs(x) for x in d if x != 0]
    obs = sum(d)
    tot = sum(nz)
    dist = {0: 1.0}
    for a in nz:
        new: dict[int, float] = {}
        for s, p in dist.items():
            new[s + a] = new.get(s + a, 0.0) + 0.5 * p
            new[s - a] = new.get(s - a, 0.0) + 0.5 * p
        dist = new
    p_two = sum(p for s, p in dist.items() if abs(s) >= abs(obs))
    p_one = sum(p for s, p in dist.items() if (s >= obs if obs >= 0 else s <= obs))
    return {"p_two_sided": float(min(1.0, p_two)), "p_one_sided_in_observed_direction": float(p_one),
            "sum_diff": obs, "n_nonzero": len(nz), "exact": True, "max_abs_sum": tot}


def wilcoxon_p(d) -> float | None:
    return ah.wilcoxon_zeros_dropped([float(x) for x in d])["p"]


# ---------------------------------------------------------------- agreement statistics
def conf_flat(a, b, k: int) -> np.ndarray:
    m = np.zeros((k, k))
    for x, y in zip(a, b):
        m[int(x), int(y)] += 1
    return m.ravel()


def _unflat(s: np.ndarray, k: int) -> np.ndarray:
    return s.reshape(s.shape[0], k, k)


def qwk_from_flat(s: np.ndarray, k: int) -> np.ndarray:
    """Quadratic weighted kappa, vectorised over rows of flattened k x k confusion counts.
    Equals analyze_holdout._qwk_from_values for ordinal levels 0..k-1."""
    m = _unflat(s, k)
    n = m.sum((1, 2))
    r = m.sum(2)
    c = m.sum(1)
    i = np.arange(k)
    w = (i[:, None] - i[None, :]) ** 2 / (k - 1) ** 2
    obs = (w[None] * m).sum((1, 2)) / n
    exp = (w[None] * (r[:, :, None] * c[:, None, :])).sum((1, 2)) / n ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        return 1 - obs / exp


def mae_from_flat(s: np.ndarray, k: int) -> np.ndarray:
    m = _unflat(s, k)
    i = np.arange(k)
    err = np.abs(i[:, None] - i[None, :])
    return (err[None] * m).sum((1, 2)) / m.sum((1, 2))


def exact_from_flat(s: np.ndarray, k: int) -> np.ndarray:
    m = _unflat(s, k)
    return np.trace(m, axis1=1, axis2=2) / m.sum((1, 2))


def bin_stats_from_flat(s: np.ndarray) -> dict[str, np.ndarray]:
    """2x2 flat [n00,n01,n10,n11] (row = first rater, col = second rater)."""
    n00, n01, n10, n11 = s[:, 0], s[:, 1], s[:, 2], s[:, 3]
    n = n00 + n01 + n10 + n11
    po = (n00 + n11) / n
    p1a = (n10 + n11) / n          # first rater positive share
    p1b = (n01 + n11) / n          # second rater positive share
    pe_k = p1a * p1b + (1 - p1a) * (1 - p1b)
    with np.errstate(invalid="ignore", divide="ignore"):
        kappa = (po - pe_k) / (1 - pe_k)
    pi = (p1a + p1b) / 2
    pe_g = 2 * pi * (1 - pi)
    with np.errstate(invalid="ignore", divide="ignore"):
        ac1 = (po - pe_g) / (1 - pe_g)
    pabak = 2 * po - 1
    return {"agreement": po, "kappa": kappa, "ac1": ac1, "pabak": pabak}


def design_arithmetic(n_clusters: int) -> dict:
    return {"n_clusters": n_clusters}


Z_MDE = float(stats.norm.ppf(0.975) + stats.norm.ppf(0.80))   # 2.8016, as in main.tex
