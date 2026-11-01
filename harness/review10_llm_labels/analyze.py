#!/usr/bin/env python3
"""Addendum 30 (review10_llm_labels): analysis of the persona-ensemble LLM evidence labels.  AI-generated; a person must
review and test it before reuse.  Exploratory and post hoc; the rules and thresholds are the ones of PLAN.md (commit
798a04f) and are implemented here without change.

Reads   raw/<model>_t1.jsonl (and raw/<model>_t2a.jsonl, raw/<model>_t2b.jsonl if present): one record per call.
        The 188 primary cells and their views (harness/review6_raters/cells_manifest.json; only to re-check the verbatim
        span).  Human labels ONLY through the de-identified analysis files that review6_reanalysis/common.load_188 reads
        (the AH per-cell file and the second rater's v3 per-cell file), only in main(), never in the self-tests.
Writes  results.json (aggregates only: no per-cell human label, no per-cell human-LLM disagreement) and REPORT_auto.md.

Intervals: question(CQ)-clustered BCa, 95%, B = 10,000, seed 20260913, the analyzer's draws (``bca`` below is
``common.fast_bca`` plus a guard for undefined leave-one-cluster-out values; checked against
``analyze_holdout.cluster_bootstrap_stat`` in the self-test).
Usage:  python3 analyze.py             (self-test, then the analysis; writes results.json and REPORT_auto.md)
        python3 analyze.py --selftest  (self-test only)
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "review6_raters"))
sys.path.insert(0, str(HARNESS / "review6_reanalysis"))
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))

import analyze_holdout as ah  # noqa: E402
import common as RC  # noqa: E402  (review6_reanalysis/common.py: loaders and the vectorised BCa)

SEED, B = ah.REGISTERED_SEED, ah.BOOTSTRAP_RESAMPLES
assert (SEED, B) == (20260913, 10_000)
PERSONAS = ["domain", "ontology", "auditor", "kgqa", "generalist"]
SEEDS = [1, 2, 3, 4, 5]
SLOTS = [(p, s) for p in PERSONAS for s in SEEDS]
N_SLOTS = len(SLOTS)                       # 25
THR_CONSISTENT = 23                        # R25: at least 23 of the 25 labels agree
MIN_CELLS = 30                             # PLAN 30.8: fewer consistent cells -> not evaluable
MARGIN = 0.10                              # PLAN 30.8
PRIMARY_MODELS = ["glm", "gptoss"]
MODELS = ["glm", "gptoss", "qwen"]
HUMANS = {"AH": "S_AH", "R2": "S_2"}
RAW = HERE / "raw"
MANIFEST6 = HARNESS / "review6_raters" / "cells_manifest.json"


# ---------------------------------------------------------------- small utilities
def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rnd(x, nd=4):
    if x is None:
        return None
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), nd)
    return x


def _read_text(path: Path) -> str:
    import gzip
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    return path.read_text(encoding="utf-8")


def jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in _read_text(path).splitlines() if l.strip()]


def raw_file(directory: Path, stem: str):
    """raw/<stem>.jsonl, else the committed raw/<stem>.jsonl.gz, else None."""
    for ext in (".jsonl", ".jsonl.gz"):
        q = directory / (stem + ext)
        if q.exists():
            return q
    return None


def sha256_text_of(path: Path) -> str:
    return hashlib.sha256(_read_text(path).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- consistency rules (PLAN 30.6)
def counts(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """labels: (cells, slots) with NaN for an invalid / missing slot -> (c1, c0) per cell."""
    valid = ~np.isnan(labels)
    c1 = np.nansum(np.where(valid, labels, 0.0), axis=1)
    c0 = valid.sum(1) - c1
    return c1, c0


def consistent(labels: np.ndarray, thr: int = THR_CONSISTENT) -> tuple[np.ndarray, np.ndarray]:
    """R25: consistent iff max(c0, c1) >= thr over the slots (an invalid slot agrees with nothing).
    Returns (is_consistent bool per cell, label per cell: 1/0, NaN when not consistent)."""
    c1, c0 = counts(labels)
    ok = np.maximum(c0, c1) >= thr
    lab = np.where(ok, (c1 >= thr).astype(float), np.nan)
    return ok, lab


def majority(labels: np.ndarray) -> np.ndarray:
    """Majority of the valid labels per cell; a tie (or no valid label) -> NaN."""
    c1, c0 = counts(labels)
    out = np.where(c1 > c0, 1.0, np.where(c0 > c1, 0.0, np.nan))
    return out


def cross_model(per_model: dict[str, tuple[np.ndarray, np.ndarray]], models: list[str]):
    """RX: >= 2 models with a consistent label on the cell and all of them agree.
    per_model[m] = (evaluated bool per cell, consistent label per cell with NaN).  Returns (denominator bool, ok bool, label)."""
    n = len(next(iter(per_model.values()))[0])
    ev = np.stack([per_model[m][0] for m in models], 1)
    lab = np.stack([per_model[m][1] for m in models], 1)
    n_ev = ev.sum(1)
    den = n_ev >= 2
    has = ~np.isnan(lab)
    n_cons = has.sum(1)
    s1 = np.nansum(np.where(has, lab, 0.0), axis=1)
    agree = (s1 == 0) | (s1 == n_cons)
    ok = den & (n_cons >= 2) & agree
    out = np.where(ok, (s1 > 0).astype(float), np.nan)
    return den, ok, out


# ---------------------------------------------------------------- statistics on additive per-cell columns
def csum(cluster_ids, cols: np.ndarray) -> np.ndarray:
    ids = [str(c) for c in cluster_ids]
    u = sorted(set(ids))
    pos = {c: i for i, c in enumerate(u)}
    M = np.zeros((len(u), cols.shape[1]))
    np.add.at(M, [pos[c] for c in ids], cols)
    return M


def bca(M: np.ndarray, f, B_: int = B, seed: int = SEED) -> dict:
    """BCa 95% interval for f(sum of cluster rows); identical draws to common.fast_bca / the analyzer; leave-one-out
    values that are undefined (NaN) are dropped from the acceleration; an undefined estimate returns Nones."""
    n = M.shape[0]
    tot = M.sum(0)
    theta = float(f(tot[None, :])[0])
    if not math.isfinite(theta) or n < 2:
        return {"est": None, "lo": None, "hi": None, "n_clusters": n, "note": "undefined"}
    idx = RC.draw_indices(n, B_, seed)
    boot = f(M[idx].sum(1))
    jack = f(tot[None, :] - M)
    boot = boot[np.isfinite(boot)]
    jack = jack[np.isfinite(jack)]
    if len(boot) < 100:
        return {"est": theta, "lo": None, "hi": None, "n_clusters": n, "note": "too few defined resamples"}
    if len(jack) < 2:
        jack = np.array([theta, theta])
    lo, hi = ah._bca_interval(theta, boot, jack, 0.05, ah.DEFAULT_BCA_TIES)
    return {"est": theta, "lo": float(lo), "hi": float(hi), "n_clusters": n, "B": B_, "seed": seed}


def kappa_flat(s: np.ndarray) -> np.ndarray:
    """Cohen's kappa from flattened 2x2 [n00, n01, n10, n11] (row = first rater); degenerate chance term -> 0 (as kappa_bin)."""
    n = s.sum(1)
    po = (s[:, 0] + s[:, 3]) / n
    pa = (s[:, 2] + s[:, 3]) / n
    pb = (s[:, 1] + s[:, 3]) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    den = 1 - pe
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 1e-12, (po - pe) / den, 0.0)


def agree_flat(s: np.ndarray) -> np.ndarray:
    return (s[:, 0] + s[:, 3]) / s.sum(1)


def pair_cols(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    k = (2 * x + y).astype(int)
    out = np.zeros((len(x), 4))
    out[np.arange(len(x)), k] = 1.0
    return out


def alpha_cols(X: np.ndarray) -> np.ndarray:
    """per-cell additive columns [o_off, N1, N0] of Krippendorff's alpha (nominal, two categories; NaN = missing coder)."""
    valid = ~np.isnan(X)
    m = valid.sum(1)
    n1 = np.nansum(np.where(valid, X, 0.0), axis=1)
    n0 = m - n1
    use = m >= 2
    with np.errstate(invalid="ignore", divide="ignore"):
        o_off = np.where(use, 2.0 * n1 * n0 / np.maximum(m - 1, 1), 0.0)
    return np.stack([o_off, np.where(use, n1, 0.0), np.where(use, n0, 0.0)], 1)


def alpha_from(s: np.ndarray) -> np.ndarray:
    o, n1, n0 = s[:, 0], s[:, 1], s[:, 2]
    n = n1 + n0
    den = 2.0 * n1 * n0
    with np.errstate(invalid="ignore", divide="ignore"):
        a = 1.0 - (n - 1.0) * o / den
    return np.where(den > 0, a, np.where(o == 0, 1.0, 0.0))


def ci_out(r: dict, nd=4) -> dict:
    return {k: (rnd(v, nd) if isinstance(v, (float, np.floating)) else v) for k, v in r.items()
            if k in ("est", "lo", "hi", "n_clusters", "note")}


def stat(cl, cols, f) -> dict:
    return ci_out(bca(csum(cl, cols), f))


def kappa_ci(cl, x, y) -> dict:
    return stat(cl, pair_cols(x, y), kappa_flat)


def agree_ci(cl, x, y) -> dict:
    return stat(cl, pair_cols(x, y), agree_flat)


def share_ci(cl, flag) -> dict:
    cols = np.stack([flag.astype(float), np.ones(len(flag))], 1)
    return stat(cl, cols, lambda s: s[:, 0] / s[:, 1])


def pi_flags(J: np.ndarray, S: np.ndarray) -> np.ndarray:
    return ((J >= 2) & (S == 0)).astype(float)


# ---------------------------------------------------------------- block for one label vector on a subset
def human_block(cl, L, hum: dict[str, np.ndarray], J, ref_label="LLM") -> dict:
    """Agreement of label vector L with each human, human-human agreement on the same cells, paired differences and
    pi-hat on the same cells.  All arrays are restricted to the same cells (no NaN in L)."""
    out = {"n_cells": int(len(L)), "n_clusters": len(set(map(str, cl)))}
    a, r = hum["AH"], hum["R2"]
    hh = {"kappa": kappa_ci(cl, a, r), "agreement": agree_ci(cl, a, r)}
    out["human_human_same_cells"] = hh
    out["vs_human"] = {}
    for h, x in (("AH", a), ("R2", r)):
        kap = kappa_ci(cl, L, x)
        d = stat(cl, np.hstack([pair_cols(L, x), pair_cols(a, r)]), lambda s: kappa_flat(s[:, :4]) - kappa_flat(s[:, 4:]))
        ref = None if hh["kappa"]["est"] is None else hh["kappa"]["est"] - MARGIN
        lb = kap["lo"]
        close = bool(out["n_cells"] >= MIN_CELLS and lb is not None and ref is not None and lb >= ref)
        out["vs_human"][h] = {"kappa": kap, "agreement": agree_ci(cl, L, x), "delta_kappa_vs_human_human": d,
                              "lb": lb, "ref": rnd(ref), "evaluable": bool(out["n_cells"] >= MIN_CELLS), "close": close}
    pL, pA, pR = pi_flags(J, L), pi_flags(J, a), pi_flags(J, r)
    n = np.ones(len(L))
    cols = np.stack([pL, pA, pR, n], 1)
    out["pi_hat"] = {"LLM": stat(cl, cols, lambda s: s[:, 0] / s[:, 3]), "AH": stat(cl, cols, lambda s: s[:, 1] / s[:, 3]),
                     "R2": stat(cl, cols, lambda s: s[:, 2] / s[:, 3]),
                     "LLM_minus_AH": stat(cl, cols, lambda s: (s[:, 0] - s[:, 1]) / s[:, 3]),
                     "LLM_minus_R2": stat(cl, cols, lambda s: (s[:, 0] - s[:, 2]) / s[:, 3])}
    out["S1_share"] = {"LLM": share_ci(cl, L == 1), "AH": share_ci(cl, a == 1), "R2": share_ci(cl, r == 1)}
    return out


def hh_block(cl, a, r) -> dict:
    if len(a) == 0:
        return {"n_cells": 0}
    return {"n_cells": int(len(a)), "n_clusters": len(set(map(str, cl))), "kappa": kappa_ci(cl, a, r), "agreement": agree_ci(cl, a, r)}


# ---------------------------------------------------------------- one model, one label key
def rule_block(df, lab_ok: np.ndarray, lab: np.ndarray, ev: np.ndarray, hum_cols, J_all, variants) -> dict:
    """Coverage + agreement for one consistency rule.  df: per-cell frame (cluster ids etc.); ev: evaluated bool; lab_ok: consistent
    bool; lab: label (NaN when not consistent) -- all aligned with df rows."""
    cl_all = df["cluster_id"].to_numpy()[ev]
    ok_e = lab_ok[ev]
    out = {"n_evaluated": int(ev.sum()), "n_consistent": int(lab_ok[ev].sum()),
           "coverage": share_ci(cl_all, ok_e)}
    sel = ev & lab_ok
    cl = df["cluster_id"].to_numpy()[sel]
    L = lab[sel]
    out["n_consistent_clusters"] = len(set(map(str, cl)))
    out["S1_share_of_consistent_labels"] = share_ci(cl, L == 1) if len(L) else None
    out["consistent_by_variant"] = {v: int(((variants == v) & sel).sum()) for v in sorted(set(variants))}
    out["evaluated_by_variant"] = {v: int(((variants == v) & ev).sum()) for v in sorted(set(variants))}
    hum = {h: hum_cols[h][sel] for h in HUMANS}
    if len(L) >= 2:
        out["agreement"] = human_block(cl, L, hum, J_all[sel])
    else:
        out["agreement"] = {"n_cells": int(len(L)), "note": "too few consistent cells"}
    comp = ev & ~lab_ok
    out["human_human_complement"] = hh_block(df["cluster_id"].to_numpy()[comp], hum_cols["AH"][comp], hum_cols["R2"][comp])
    return out


def model_block(df, slot_labels: np.ndarray, ev: np.ndarray, hum_cols, J_all, variants) -> dict:
    """slot_labels: (cells, 25) with NaN; ev: evaluated bool per cell (all 25 slots attempted, none skipped)."""
    out = {}
    ok25, lab25 = consistent(slot_labels, THR_CONSISTENT)
    oku, labu = consistent(slot_labels, N_SLOTS)
    out["R25"] = rule_block(df, ok25, lab25, ev, hum_cols, J_all, variants)
    out["R25U"] = rule_block(df, oku, labu, ev, hum_cols, J_all, variants)
    cl_e = df["cluster_id"].to_numpy()[ev]
    out["human_human_all_evaluated"] = hh_block(cl_e, hum_cols["AH"][ev], hum_cols["R2"][ev])
    # unfiltered majority of the 25 labels, on all evaluated cells
    mj = majority(slot_labels)
    sel = ev & ~np.isnan(mj)
    cl = df["cluster_id"].to_numpy()[sel]
    hb = {h: hum_cols[h][sel] for h in HUMANS}
    out["unfiltered_majority25"] = {"n_cells_with_label": int(sel.sum()), "agreement": human_block(cl, mj[sel], hb, J_all[sel])}
    # persona effects
    pers = {}
    pl = {}
    for i, p in enumerate(PERSONAS):
        sub = slot_labels[:, 5 * i:5 * i + 5]
        pl[p] = majority(sub)
        s = ev & ~np.isnan(pl[p])
        cl = df["cluster_id"].to_numpy()[s]
        L = pl[p][s]
        hb = {h: hum_cols[h][s] for h in HUMANS}
        kap = {h: kappa_ci(cl, L, hb[h]) for h in HUMANS}
        pers[p] = {"n_cells_with_label": int(s.sum()), "S1_share": share_ci(cl, L == 1), "kappa_AH": kap["AH"], "kappa_R2": kap["R2"],
                   "pi_hat": stat(cl, np.stack([pi_flags(J_all[s], L), np.ones(len(L))], 1), lambda q: q[:, 0] / q[:, 1])}
    out["personas"] = pers

    def spread(key, sub=None):
        v = [(pers[p][key]["est"] if sub is None else pers[p][key][sub]) for p in PERSONAS]
        v = [x for x in v if x is not None]
        return rnd(max(v) - min(v)) if v else None

    out["persona_spread_max_minus_min"] = {"S1_share": spread("S1_share"), "kappa_AH": spread("kappa_AH"),
                                           "kappa_R2": spread("kappa_R2"), "pi_hat": spread("pi_hat")}
    # mean pairwise kappa between persona labels
    P = np.stack([pl[p] for p in PERSONAS], 1)
    pairs = [(i, j) for i in range(5) for j in range(i + 1, 5)]
    cols, ok = [], np.ones(len(P), dtype=bool)
    blocks = []
    for i, j in pairs:
        v = ~np.isnan(P[:, i]) & ~np.isnan(P[:, j]) & ev
        c = np.zeros((len(P), 4))
        c[v] = pair_cols(P[v, i], P[v, j])
        blocks.append(c)
    cols = np.hstack(blocks)
    out["persona_pairwise_kappa_mean"] = stat(df["cluster_id"].to_numpy()[ev], cols[ev],
                                               lambda s: np.mean([kappa_flat(s[:, 4 * k:4 * k + 4]) for k in range(len(pairs))], axis=0))
    # test-retest alpha
    al = {}
    for i, p in enumerate(PERSONAS):
        al[p] = stat(cl_e, alpha_cols(slot_labels[ev][:, 5 * i:5 * i + 5]), alpha_from)
    out["alpha_seeds_per_persona"] = al
    out["alpha_all_25_slots"] = stat(cl_e, alpha_cols(slot_labels[ev]), alpha_from)
    out["alpha_between_persona_labels"] = stat(cl_e, alpha_cols(P[ev]), alpha_from)
    # slot-level facts
    out["S1_share_of_all_valid_slots"] = rnd(float(np.nansum(slot_labels[ev]) / max(1, np.sum(~np.isnan(slot_labels[ev])))))
    return out


# ---------------------------------------------------------------- loading raw records
class Raw:
    """Per model and tier: slot labels (cells x 25) for S_final and S_raw, evaluated mask, parse facts."""

    def __init__(self, cells: list[dict], recs: list[dict], view_text):
        self.cells = cells
        self.ids = [c["cell_id"] for c in cells]
        pos = {c: i for i, c in enumerate(self.ids)}
        n = len(cells)
        slot_pos = {s: k for k, s in enumerate(SLOTS)}
        self.S_final = np.full((n, N_SLOTS), np.nan)
        self.S_raw = np.full((n, N_SLOTS), np.nan)
        self.attempted = np.zeros((n, N_SLOTS), dtype=bool)
        self.skipped = np.zeros(n, dtype=bool)
        self.recheck_mismatch = 0
        self.n_ok = self.n_invalid = self.n_error = 0
        seen = set()
        err_count: dict = {}
        for r in recs:
            cid = r.get("cell_id")
            if cid not in pos:
                continue
            i = pos[cid]
            if r.get("status") == "context_skip":
                self.skipped[i] = True
                continue
            key = (r.get("persona"), r.get("seed"))
            if key not in slot_pos or (cid, key) in seen:
                continue
            if r.get("status") not in ("ok", "invalid"):
                if r.get("status") == "error":
                    self.n_error += 1
                    err_count[(cid, key)] = err_count.get((cid, key), 0) + 1
                continue
            seen.add((cid, key))
            k = slot_pos[key]
            self.attempted[i, k] = True
            if r["status"] == "invalid":
                self.n_invalid += 1
                continue
            self.n_ok += 1
            s_raw = int(r["S_raw"])
            span = r.get("span") or ""
            s_final = 0
            if s_raw == 1:
                s_final = 1 if (collapse(span) and collapse(span) in collapse(view_text(cells[i]))) else 0
            if int(r["S_final"]) != s_final:
                self.recheck_mismatch += 1
            self.S_raw[i, k] = s_raw
            self.S_final[i, k] = s_final
        # PLAN 30.15 (A4): a slot whose calls failed at the gateway twice (the main pass and the final resume pass) and never got a
        # reply has been attempted and has no label: it is an unlabeled slot and counts as not agreeing, as an invalid slot does.
        self.n_error_slots = 0
        for (cid, key), n in err_count.items():
            i = pos[cid]
            k = slot_pos[key]
            if n >= 2 and not self.attempted[i, k]:
                self.attempted[i, k] = True
                self.n_error_slots += 1
        self.evaluated = self.attempted.all(1) & ~self.skipped


def make_view_text(cache: dict):
    def f(row):
        p = row["view_path"]
        if p not in cache:
            cache[p] = (ACCESS / p).read_text(encoding="utf-8")
        return cache[p]
    return f


# ---------------------------------------------------------------- synthetic-data self-tests (no human labels, no model)
def run_selftests(check) -> list[str]:
    fails: list[str] = []

    def chk(cond, msg):
        check(cond, msg)
        if not cond:
            fails.append(msg)

    rng = np.random.default_rng(7)
    # consistency rule
    rows = {
        "25 ones": [1] * 25, "23 ones + 2 zeros": [1] * 23 + [0] * 2, "22 ones + 3 zeros": [1] * 22 + [0] * 3,
        "2 ones + 23 zeros": [1] * 2 + [0] * 23, "3 ones + 22 zeros": [1] * 3 + [0] * 22, "25 zeros": [0] * 25,
        "23 ones + 2 invalid": [1] * 23 + [np.nan] * 2, "22 ones + 3 invalid": [1] * 22 + [np.nan] * 3,
        "12/13 split": [1] * 12 + [0] * 13,
    }
    X = np.array(list(rows.values()), dtype=float)
    ok, lab = consistent(X)
    want = [True, True, False, True, False, True, True, False, False]
    chk(ok.tolist() == want, f"R25 consistency flags {ok.tolist()}")
    chk(bool(np.isnan(lab[~ok]).all()) and not np.isnan(lab[ok]).any(), "label is NaN exactly where the cell is not consistent")
    chk([int(x) for x in lab[ok]] == [1, 1, 0, 0, 1], f"R25 consistent labels {[x for x in lab[ok]]}")
    oku, _ = consistent(X, 25)
    chk(oku.tolist() == [True, False, False, False, False, True, False, False, False], f"R25U (unanimous) flags {oku.tolist()}")
    # majority with ties and invalid
    m = majority(np.array([[1, 1, 0, 0], [1, 1, 1, 0], [np.nan, np.nan, np.nan, np.nan], [0, 0, 0, np.nan]], dtype=float))
    chk(np.isnan(m[0]) and m[1] == 1 and np.isnan(m[2]) and m[3] == 0, "majority: tie and empty -> NaN")
    # cross-model consensus
    pm = {"a": (np.array([1, 1, 1, 0, 1], bool), np.array([1, 0, np.nan, np.nan, 1.0])),
          "b": (np.array([1, 1, 1, 1, 0], bool), np.array([1, 1, 0, 1, np.nan])),
          "c": (np.array([1, 0, 1, 1, 1], bool), np.array([0, np.nan, 0, 1, 1.0]))}
    den, okx, lx = cross_model(pm, ["a", "b"])
    chk(den.tolist() == [True, True, True, False, False] and okx.tolist() == [True, False, False, False, False] and lx[0] == 1,
        f"RX-primary (two models, both consistent and equal): den {den.tolist()} ok {okx.tolist()}")
    den, okx, lx = cross_model(pm, ["a", "b", "c"])
    chk(den.tolist() == [True, True, True, True, True] and okx.tolist() == [False, False, True, True, True],
        f"RX-all (>=2 consistent, all consistent agree): ok {okx.tolist()}")
    # statistics against the existing implementations
    from analyze_raters import alpha_binary, kappa_bin
    x = rng.integers(0, 2, 200).astype(float)
    y = np.where(rng.random(200) < 0.2, 1 - x, x)
    chk(abs(kappa_flat(pair_cols(x, y).sum(0)[None, :])[0] - kappa_bin(x, y)) < 1e-12, "kappa_flat equals analyze_raters.kappa_bin")
    chk(float(kappa_flat(np.array([[10.0, 0, 0, 0]]))[0]) == 0.0, "degenerate chance term -> kappa 0")
    Xa = rng.integers(0, 2, (60, 5)).astype(float)
    Xa[rng.random(Xa.shape) < 0.1] = np.nan
    chk(abs(alpha_from(alpha_cols(Xa).sum(0)[None, :])[0] - alpha_binary(Xa)) < 1e-12, "alpha from additive columns equals analyze_raters.alpha_binary")
    # bca equals the analyzer's cluster bootstrap
    cl = np.repeat(np.arange(20), 5)
    xx = rng.integers(0, 2, 100)
    yy = np.where(rng.random(100) < 0.25, 1 - xx, xx)
    cells = [{"cluster_id": f"c{c:02d}", "x": int(a), "y": int(b)} for c, a, b in zip(cl, xx, yy)]
    cl_str = [f"c{c:02d}" for c in cl]
    r1 = bca(csum(cl_str, pair_cols(xx, yy)), kappa_flat, B_=1000, seed=SEED)
    r2 = ah.cluster_bootstrap_stat(cells, lambda cs: kappa_bin([c["x"] for c in cs], [c["y"] for c in cs]), B=1000, seed=SEED)
    chk(abs(r1["lo"] - r2["ci_lo"]) < 1e-9 and abs(r1["hi"] - r2["ci_hi"]) < 1e-9 and abs(r1["est"] - r2["estimate"]) < 1e-12,
        f"bca equals analyze_holdout.cluster_bootstrap_stat for kappa ([{r1['lo']:.4f}, {r1['hi']:.4f}])")
    # Raw: loading, span re-check, evaluated mask, invalid slots, context skip, partial cells
    cells_t = [{"cell_id": f"x{i}", "cluster_id": f"c{i}", "view_path": "v"} for i in range(1, 6)]
    view = "foo   bar baz"

    def rec(cid, p, sd, st="ok", s_raw=1, span="foo bar", s_final=None):
        r = {"cell_id": cid, "persona": p, "seed": sd, "status": st}
        if st == "ok":
            r.update(S_raw=s_raw, span=span, S_final=(1 if (s_raw == 1 and collapse(span) in collapse(view)) else 0) if s_final is None else s_final)
        return r

    recs_t = [rec("x1", p_, sd) for p_, sd in SLOTS]                                          # 25 supported, verbatim
    recs_t += [rec("x2", p_, sd, st=("invalid" if k < 2 else "ok"), span="not in view") for k, (p_, sd) in enumerate(SLOTS)]   # 2 invalid, rest S_raw 1 with a non-verbatim span
    recs_t += [{"cell_id": "x3", "persona": None, "seed": None, "status": "context_skip"}]
    recs_t += [rec("x4", p_, sd) for p_, sd in SLOTS[:10]]                                    # partial
    recs_t += [rec("x5", p_, sd, s_raw=0, span="") for p_, sd in SLOTS]                       # 25 unsupported
    recs_t += [rec("x1", "domain", 1, s_raw=0, span="")]                                      # a duplicate slot: the first record counts
    recs_t += [{"cell_id": "x4", "persona": p_, "seed": sd, "status": "error"} for p_, sd in SLOTS[10:12] * 2]        # x4: 2 slots with two gateway errors each
    recs_t += [{"cell_id": "x4", "persona": p_, "seed": sd, "status": "error"} for p_, sd in SLOTS[12:15]]            # one error only: still missing
    rt = Raw(cells_t, recs_t, lambda row: view)
    chk(rt.evaluated.tolist() == [True, True, False, False, True], f"evaluated mask {rt.evaluated.tolist()} (x3 skipped, x4 partial)")
    chk(rt.n_error_slots == 2 and bool(rt.attempted[3, 10]) and not bool(rt.attempted[3, 12]), "a slot with two gateway errors counts as attempted without a label; one error does not")
    chk(rt.skipped.tolist() == [False, False, True, False, False], "context-skip cell flagged")
    chk(np.nansum(rt.S_final[0]) == 25 and np.nansum(rt.S_final[1]) == 0 and np.isnan(rt.S_final[1][:2]).all(), "span re-check: verbatim keeps 1, non-verbatim gives 0, invalid slot has no label")
    chk(rt.recheck_mismatch == 0 and rt.n_invalid == 2, "re-check agrees with the stored flags; 2 invalid slots counted")
    okt, labt = consistent(rt.S_final)
    chk(bool(okt[0]) and labt[0] == 1.0, "x1: 25 of 25 agree -> consistent with label 1")
    chk(bool(okt[1]) and labt[1] == 0.0, "x2: 23 valid labels all 0 and 2 invalid -> consistent with label 0 (23 of 25 agree)")
    # end-to-end on synthetic data: planted agreement -> 'close'; random LLM -> 'not close'
    n_cl, per = 40, 4
    n = n_cl * per
    cid = np.repeat([f"q{i:02d}" for i in range(n_cl)], per)
    truth = rng.integers(0, 2, n)

    def noisy(v, p):
        return np.where(rng.random(n) < p, 1 - v, v)

    AH, R2 = noisy(truth, 0.15), noisy(truth, 0.15)
    Jv = rng.integers(0, 4, n)
    import pandas as pd
    df = pd.DataFrame({"cluster_id": cid, "variant": np.tile(list("ABCD"), n_cl)})
    hum = {"AH": AH.astype(float), "R2": R2.astype(float)}
    good = np.stack([np.where(rng.random(n) < 0.03, 1 - truth, truth) for _ in range(N_SLOTS)], 1).astype(float)
    bad = rng.integers(0, 2, (n, N_SLOTS)).astype(float)
    ev = np.ones(n, dtype=bool)
    mb = model_block(df, good, ev, hum, Jv, df["variant"].to_numpy())
    chk(mb["R25"]["n_consistent"] > 100 and mb["R25"]["agreement"]["vs_human"]["AH"]["close"], "synthetic: consistent labels that follow the truth are close to human")
    mb2 = model_block(df, bad, ev, hum, Jv, df["variant"].to_numpy())
    chk(mb2["R25"]["n_consistent"] < 10 and not mb2["R25"]["agreement"].get("vs_human", {"AH": {"close": False}})["AH"]["close"], "synthetic: random labels are not close to human (and not evaluable)")
    chk(0.5 < mb["alpha_all_25_slots"]["est"] <= 1.0 and abs(mb2["alpha_all_25_slots"]["est"]) < 0.1, "synthetic: alpha high for consistent, near 0 for random")
    chk(set(mb["personas"]) == set(PERSONAS), "persona block has the five personas")
    # the verdict function
    chk(verdict({"glm": mb, "gptoss": mb})["state"] == "close to human", "verdict: all four comparisons close -> close to human")
    chk(verdict({"glm": mb, "gptoss": mb2})["state"] == "mixed", "verdict: some close -> mixed")
    chk(verdict({"glm": mb2, "gptoss": mb2})["state"] == "supports the paper's current conclusion", "verdict: none close -> supports the paper's conclusion")
    return fails


def verdict(blocks: dict[str, dict]) -> dict:
    """PLAN 30.8: primary models, rule R25, both humans; close iff |C| >= 30 and LB >= human-human kappa (same cells) - 0.10."""
    det = {}
    n_close = 0
    n_tot = 0
    for m in PRIMARY_MODELS:
        if m not in blocks:
            continue
        ag = blocks[m]["R25"]["agreement"]
        for h in HUMANS:
            n_tot += 1
            if "vs_human" in ag:
                v = ag["vs_human"][h]
                det[f"{m}:{h}"] = {"n_consistent": ag["n_cells"], "lb": v["lb"], "ref": v["ref"], "evaluable": v["evaluable"], "close": v["close"]}
                n_close += bool(v["close"])
            else:
                det[f"{m}:{h}"] = {"n_consistent": ag.get("n_cells"), "evaluable": False, "close": False}
    if n_tot == 0:
        return {"state": "not computed (no primary model evaluated)", "detail": det}
    state = "close to human" if n_close == n_tot else ("mixed" if n_close > 0 else "supports the paper's current conclusion")
    return {"state": state, "n_close": n_close, "n_comparisons": n_tot, "detail": det}


# ---------------------------------------------------------------- main analysis
def natural_J(rows: list[dict], judge: str):
    """Judge score J (0-3) of the natural-documentation study (addendum 27) on the same subgraph view: median of the valid
    repeats per cell; NaN where no valid repeat exists.  Returns None if the judge file is absent."""
    p = HARNESS / "review6_natural" / "raw" / f"raw_{judge}_natural.jsonl"
    if not p.exists():
        return None
    by: dict[str, list[int]] = {}
    for r in jsonl(p):
        if r.get("valid") in (True, "True") and r.get("J") not in (None, ""):
            by.setdefault(r["cell_id"], []).append(int(r["J"]))
    return np.array([float(np.median(by[r["cell_id"]])) if r["cell_id"] in by else np.nan for r in rows])


def extra_block(rows: list[dict], raw: "Raw", Js=None) -> dict:
    """Descriptive block for cells WITHOUT a human reference (Tiers 2 and 3): coverage under R25 / R25U, label distribution,
    and pi-hat under the consistent LLM label where a judge score exists on the same cell (judge named)."""
    n = len(rows)
    variants = np.array([r["variant"] for r in rows])
    cl = np.array([r["cluster_id"] for r in rows])
    lab = raw.S_final
    ok25, l25 = consistent(lab, THR_CONSISTENT)
    oku, _ = consistent(lab, N_SLOTS)
    mj = majority(lab)
    nvalid = (~np.isnan(lab)).sum(1)

    def one(mask):
        e = raw.evaluated & mask
        d = {"n_cells": int(mask.sum()), "n_evaluated": int(e.sum()), "n_skipped_context": int((raw.skipped & mask).sum()),
             "n_partial_or_missing": int((~raw.evaluated & ~raw.skipped & mask).sum())}
        if not e.any():
            return d
        d["n_cells_without_any_valid_label"] = int((e & (nvalid == 0)).sum())
        d["R25"] = {"n_consistent": int((ok25 & e).sum()), "coverage": share_ci(cl[e], ok25[e]),
                    "n_label1": int((ok25 & e & (l25 == 1)).sum()), "n_label0": int((ok25 & e & (l25 == 0)).sum())}
        if (ok25 & e).sum() >= 1:
            d["R25"]["S1_share_of_consistent_labels"] = share_ci(cl[ok25 & e], l25[ok25 & e] == 1)
        d["R25U"] = {"n_consistent": int((oku & e).sum()), "coverage": share_ci(cl[e], oku[e])}
        s_ = e & ~np.isnan(mj)
        d["unfiltered_majority25"] = {"n_cells_with_label": int(s_.sum()),
                                      "S1_share": share_ci(cl[s_], mj[s_] == 1) if s_.any() else None}
        if Js:
            d["pi_hat_under_consistent_llm_label"] = {}
            for jn, J in Js.items():
                m2 = e & ok25 & ~np.isnan(J)
                if m2.sum() >= 2:
                    cols = np.stack([((J[m2] >= 2) & (l25[m2] == 0)).astype(float), np.ones(m2.sum())], 1)
                    d["pi_hat_under_consistent_llm_label"][jn] = {"n_cells": int(m2.sum()), **stat(cl[m2], cols, lambda q: q[:, 0] / q[:, 1])}
        return d

    return {"overall": one(np.ones(n, dtype=bool)), "by_variant": {v: one(variants == v) for v in sorted(set(variants))},
            "human_reference": "none (no human label exists for these cells)"}


def extra_cross(rows: list[dict], raws):
    ms = [m for m in PRIMARY_MODELS if m in raws]
    if len(ms) < 2:
        return None
    pm = {}
    for m in ms:
        ok, lab = consistent(raws[m].S_final, THR_CONSISTENT)
        pm[m] = (raws[m].evaluated, np.where(raws[m].evaluated, lab, np.nan))
    den, ok, lab = cross_model(pm, ms)
    cl = np.array([r["cluster_id"] for r in rows])
    return {"models": ms, "n_denominator": int(den.sum()), "n_consensus": int(ok.sum()),
            "coverage": share_ci(cl[den], ok[den]) if den.any() else None,
            "S1_share_of_consensus_labels": share_ci(cl[ok], lab[ok] == 1) if ok.any() else None}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    def check(cond, msg):
        print(("ok   " if cond else "FAIL ") + msg)

    fails = run_selftests(check)
    if fails:
        print(f"{len(fails)} self-test(s) FAILED")
        return 1
    if "--selftest" in argv:
        print("self-test OK")
        return 0
    man = json.loads(MANIFEST6.read_text(encoding="utf-8"))
    cells = sorted(man["cells"], key=lambda c: c["cell_id"])
    ids = [c["cell_id"] for c in cells]
    cache: dict = {}
    vt = make_view_text(cache)
    # human labels: de-identified analysis files only, only here
    d = RC.load_188().set_index("cell_id").loc[ids].reset_index()
    assert (d["J"].to_numpy() == np.array([c["J_registered_judge"] for c in cells])).all(), "J differs between manifest and analysis file"
    df = d[["cell_id", "cluster_id", "variant"]].copy()
    df["cluster_id"] = [c["cluster_id"] for c in cells]
    hum = {"AH": d["S_AH"].to_numpy(float), "R2": d["S_2"].to_numpy(float)}
    Jv = d["J"].to_numpy(int)
    variants = df["variant"].to_numpy()
    res: dict = {"meta": {"plan_commit": "798a04f", "B": B, "seed": SEED, "n_cells_tier1": len(cells), "n_clusters_tier1": len({c["cluster_id"] for c in cells}),
                          "consistency_threshold": THR_CONSISTENT, "n_slots": N_SLOTS, "min_consistent_cells": MIN_CELLS, "margin": MARGIN,
                          "human_human_all_188": hh_block(df["cluster_id"].to_numpy(), hum["AH"], hum["R2"])},
                 "models": {}, "tier2": {}}
    raws: dict[str, Raw] = {}
    for m in MODELS:
        p = raw_file(RAW, f"{m}_t1")
        if p is None:
            res["models"][m] = {"status": "no raw file"}
            continue
        recs = jsonl(p)
        raw = Raw(cells, recs, vt)
        raws[m] = raw
        ev = raw.evaluated
        blk = {"status": "analysed", "n_cells_evaluated": int(ev.sum()), "n_cells_context_skip": int(raw.skipped.sum()),
               "n_cells_partial_or_missing": int((~ev & ~raw.skipped).sum()),
               "slots": {"ok": raw.n_ok, "invalid": raw.n_invalid, "gateway_error_slots_without_label": raw.n_error_slots, "attempted": int(raw.attempted.sum()),
                         "parse_rate": rnd(raw.n_ok / max(1, raw.n_ok + raw.n_invalid))},
               "span_recheck_mismatches": raw.recheck_mismatch}
        blk["S_final"] = model_block(df, raw.S_final, ev, hum, Jv, variants)
        blk["S_raw_sensitivity"] = {"R25": rule_block(df, *consistent(raw.S_raw, THR_CONSISTENT), ev, hum, Jv, variants),
                                    "S1_share_of_all_valid_slots": rnd(float(np.nansum(raw.S_raw[ev]) / max(1, np.sum(~np.isnan(raw.S_raw[ev])))))}
        # verbatim facts
        res["models"][m] = blk
    # cross-model consensus (S_final)
    pm = {}
    for m, raw in raws.items():
        ok, lab = consistent(raw.S_final, THR_CONSISTENT)
        pm[m] = (raw.evaluated, np.where(raw.evaluated, lab, np.nan))
    cross = {}
    for name, ms in (("RX_primary", [m for m in PRIMARY_MODELS if m in pm]), ("RX_all", [m for m in MODELS if m in pm])):
        if len(ms) < 2:
            cross[name] = {"status": "fewer than two models"}
            continue
        den, ok, lab = cross_model(pm, ms)
        cl_den = df["cluster_id"].to_numpy()[den]
        c = {"models": ms, "n_denominator": int(den.sum()), "n_consensus": int(ok.sum()), "coverage": share_ci(cl_den, ok[den])}
        sel = ok
        if sel.sum() >= 2:
            cl = df["cluster_id"].to_numpy()[sel]
            c["agreement"] = human_block(cl, lab[sel], {h: hum[h][sel] for h in HUMANS}, Jv[sel])
        c["human_human_complement"] = hh_block(df["cluster_id"].to_numpy()[den & ~ok], hum["AH"][den & ~ok], hum["R2"][den & ~ok])
        cross[name] = c
    res["cross_model"] = cross
    res["verdict"] = verdict({m: res["models"][m]["S_final"] for m in PRIMARY_MODELS if res["models"].get(m, {}).get("status") == "analysed"})
    # Tiers 2 and 3 (amendment A1): descriptive, no human reference
    import cells as CELLS
    res["extra"] = {}
    for t in CELLS.TIERS[1:]:
        try:
            rows = CELLS.load_tier(t)
        except SystemExit:
            continue
        raws2 = {}
        for m in MODELS:
            p = raw_file(HERE / "raw_internal" if t in CELLS.INTERNAL_TIERS else RAW, f"{m}_t{t}")
            if p is not None and p.stat().st_size > 0:
                raws2[m] = Raw(rows, jsonl(p), make_view_text(cache))
        if not raws2:
            continue
        Js = None
        if t == "2b":
            Js = {f"judge_{j}": v for j in ("gptoss", "glm") if (v := natural_J(rows, j)) is not None}
        blk = {"n_cells": len(rows), "internal_aggregate_only": t in CELLS.INTERNAL_TIERS, "models": {}}
        for m, r2 in raws2.items():
            blk["models"][m] = extra_block(rows, r2, Js)
            blk["models"][m]["span_recheck_mismatches"] = r2.recheck_mismatch
            blk["models"][m]["slots"] = {"ok": r2.n_ok, "invalid": r2.n_invalid}
        blk["cross_model_primary"] = extra_cross(rows, raws2)
        res["extra"][t] = blk
    # file hashes
    res["meta"]["raw_sha256_of_uncompressed_text"] = {p.name.replace(".gz", ""): sha256_text_of(p) for p in sorted(list(RAW.glob("*_t*.jsonl")) + [q for q in RAW.glob("*_t*.jsonl.gz") if not (RAW / q.name[:-3]).exists()])}
    out = HERE / "results.json"
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    write_report(res, HERE / "REPORT_auto.md")
    print(json.dumps(res["verdict"], indent=1))
    return 0


def f3(r, nd=3):
    if r is None or r.get("est") is None:
        return "n/a"
    lo, hi = r.get("lo"), r.get("hi")
    if lo is None:
        return f"{r['est']:.{nd}f}"
    return f"{r['est']:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


def pct(r):
    if r is None or r.get("est") is None:
        return "n/a"
    lo, hi = r.get("lo"), r.get("hi")
    return f"{100 * r['est']:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]" if lo is not None else f"{100 * r['est']:.1f}%"


def write_report(res: dict, path: Path) -> None:
    L = ["# Addendum 30 -- automatic tables (results.json)", "",
         "AI-generated; post hoc. Intervals: question-clustered BCa 95%, B = 10,000, seed 20260913. No per-cell human label appears here.", ""]
    hh = res["meta"]["human_human_all_188"]
    L += [f"Human-human kappa on all 188 cells: {f3(hh['kappa'])}, agreement {pct(hh['agreement'])}.", ""]
    L += ["## Verdict (PLAN 30.8)", "", f"**{res['verdict']['state']}**", ""]
    L += ["| comparison | consistent cells | LB of kappa(LLM, human) | human-human kappa - 0.10 (same cells) | close |", "|---|---|---|---|---|"]
    for k, v in res["verdict"]["detail"].items():
        L.append(f"| {k} | {v.get('n_consistent')} | {rnd(v.get('lb'), 3)} | {v.get('ref')} | {v.get('close')} |")
    L.append("")
    for m, blk in res["models"].items():
        if blk.get("status") != "analysed":
            L += [f"## {m}: {blk.get('status')}", ""]
            continue
        s = blk["S_final"]
        L += [f"## {m}", "", f"Evaluated cells {blk['n_cells_evaluated']} (context skip {blk['n_cells_context_skip']}, partial or missing {blk['n_cells_partial_or_missing']}); "
              f"slots ok {blk['slots']['ok']} / invalid {blk['slots']['invalid']}, parse rate {blk['slots']['parse_rate']}; span re-check mismatches {blk['span_recheck_mismatches']}.", ""]
        L += ["| rule | consistent / evaluated | coverage | S=1 share of consistent labels | kappa AH | agreement AH | kappa R2 | agreement R2 | human-human kappa (same cells) | human-human kappa (complement) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for rn in ("R25", "R25U"):
            r = s[rn]
            ag = r["agreement"]
            if "vs_human" in ag:
                vh = ag["vs_human"]
                L.append(f"| {rn} | {r['n_consistent']} / {r['n_evaluated']} | {pct(r['coverage'])} | {pct(r['S1_share_of_consistent_labels'])} | {f3(vh['AH']['kappa'])} | {pct(vh['AH']['agreement'])} | {f3(vh['R2']['kappa'])} | {pct(vh['R2']['agreement'])} | {f3(ag['human_human_same_cells']['kappa'])} | {f3(r['human_human_complement'].get('kappa'))} |")
            else:
                L.append(f"| {rn} | {r['n_consistent']} / {r['n_evaluated']} | {pct(r['coverage'])} | n/a | n/a | n/a | n/a | n/a | n/a | {f3(r['human_human_complement'].get('kappa'))} |")
        L.append("")
        ag = s["R25"]["agreement"]
        if "pi_hat" in ag:
            ph = ag["pi_hat"]
            L += [f"pi-hat on the R25-consistent cells: LLM {pct(ph['LLM'])}, AH {pct(ph['AH'])}, R2 {pct(ph['R2'])}; LLM minus AH {f3(ph['LLM_minus_AH'])}, LLM minus R2 {f3(ph['LLM_minus_R2'])}.", ""]
        u = s["unfiltered_majority25"]["agreement"]
        L += [f"Unfiltered majority of the 25 labels (all evaluated cells): kappa AH {f3(u['vs_human']['AH']['kappa'])}, kappa R2 {f3(u['vs_human']['R2']['kappa'])}, S=1 share {pct(u['S1_share']['LLM'])}, pi-hat {pct(u['pi_hat']['LLM'])}.", ""]
        L += ["| persona | S=1 share | kappa AH | kappa R2 | pi-hat | alpha across 5 seeds |", "|---|---|---|---|---|---|"]
        for p in PERSONAS:
            q = s["personas"][p]
            L.append(f"| {p} | {pct(q['S1_share'])} | {f3(q['kappa_AH'])} | {f3(q['kappa_R2'])} | {pct(q['pi_hat'])} | {f3(s['alpha_seeds_per_persona'][p])} |")
        L += ["", f"alpha across all 25 slots {f3(s['alpha_all_25_slots'])}; alpha between persona labels {f3(s['alpha_between_persona_labels'])}; mean pairwise kappa between persona labels {f3(s['persona_pairwise_kappa_mean'])}.", ""]
        sr = blk["S_raw_sensitivity"]["R25"]
        L += [f"Sensitivity S_raw (R25): consistent {sr['n_consistent']} / {sr['n_evaluated']}.", ""]
    for name, c in res.get("cross_model", {}).items():
        if "coverage" in c:
            L += [f"## {name} (models {', '.join(c['models'])})", "", f"consensus {c['n_consensus']} / {c['n_denominator']} ({pct(c['coverage'])}).", ""]
            if "agreement" in c and "vs_human" in c["agreement"]:
                vh = c["agreement"]["vs_human"]
                L += [f"kappa AH {f3(vh['AH']['kappa'])}, kappa R2 {f3(vh['R2']['kappa'])}, human-human kappa on the same cells {f3(c['agreement']['human_human_same_cells']['kappa'])}.", ""]
    SETNAME = {"2a": "remaining holdout cells (36-question bank)", "2b": "natural-documentation cells", "3a": "holdout paraphrases",
               "3b": "holdout extra questions (v2)", "3c": "development bank", "3d": "second domain (internal; aggregate only)",
               "3e": "expansion draft (unfrozen)"}
    for t, tt in res.get("extra", {}).items():
        L += [f"## Tier {t}: {SETNAME.get(t, t)} ({tt['n_cells']} cells) -- NO HUMAN REFERENCE", ""]
        for m, c in tt["models"].items():
            o = c["overall"]
            if "R25" not in o:
                L.append(f"* {m}: evaluated {o['n_evaluated']} of {o['n_cells']} (skipped for context {o['n_skipped_context']}, partial or missing {o['n_partial_or_missing']})")
                continue
            ph = o.get("pi_hat_under_consistent_llm_label") or {}
            L.append(f"* {m}: evaluated {o['n_evaluated']}/{o['n_cells']}; R25 consistent {o['R25']['n_consistent']} ({pct(o['R25']['coverage'])}), "
                     f"label 1: {o['R25']['n_label1']}, label 0: {o['R25']['n_label0']}; R25U {o['R25U']['n_consistent']} ({pct(o['R25U']['coverage'])}); "
                     f"S=1 share of the unfiltered majority {pct(o['unfiltered_majority25']['S1_share'])}"
                     + (("; pi-hat under the consistent LLM label " + ", ".join(f"{k} {pct(v)} (n={v['n_cells']})" for k, v in ph.items())) if ph else ""))
        cm = tt.get("cross_model_primary")
        if cm:
            L.append(f"* RX-primary ({' + '.join(cm['models'])}): consensus {cm['n_consensus']}/{cm['n_denominator']} ({pct(cm['coverage'])})")
        L += ["", "| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |", "|---|---|---|---|---|---|---|"]
        for m, c in tt["models"].items():
            for v, d in c["by_variant"].items():
                if "R25" not in d:
                    continue
                L.append(f"| {m} | {v} | {d['n_evaluated']}/{d['n_cells']} | {d['R25']['n_consistent']} ({pct(d['R25']['coverage'])}) | "
                         f"{d['R25']['n_label1']} / {d['R25']['n_label0']} | {d['R25U']['n_consistent']} | {pct(d['unfiltered_majority25']['S1_share'])} |")
        L.append("")
    path.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
