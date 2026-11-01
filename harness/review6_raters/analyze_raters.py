#!/usr/bin/env python3
"""Analysis for PREREG addendum 28 (review6_raters): test-retest of the S21 LLM rater and cross-family raters.

AI-generated code: review and test before use.  Post hoc with respect to the original plan, pre-specified with
respect to the new rater runs (PLAN.md in this directory is frozen before any new rater call).

Reads (never the sealed files: site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env):
  cells_manifest.json                      188 primary cells, cluster ids, registered-judge J, material paths + sha256
  raw/<run>.jsonl                          one record per cell and run (run_rater.py): a1 a2 b1 b2 b3 c1 c2 (GLM-4.7-Flash),
                                           gptoss, haiku|opus (only if the Anthropic route exists); the S21 luna raw file is
                                           read as the separate label source "luna_s21" (no new luna call is made)
  locked_labels/primary_working.csv         AH labels      (columns cell_id, A = S, rater_L1 = R)
  annotation/second_pass_2026-10-13/v3/labels_for_analysis_v3.csv   second-rater labels
Writes results.json, REPORT.md, labels_for_analysis_majority.csv and the unchanged audit's aggregate output.
Per-cell human labels are never written to a repository file (aggregates only); the audit's per-cell file goes to --sealed-dir.

Usage (run from anywhere):
  python3 analyze_raters.py selfcheck
  python3 analyze_raters.py run [--raw-dir raw] [--out-dir .] [--claude haiku] [--B 10000] [--sealed-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
import analyze_holdout as ah  # noqa: E402  (resampling routine, QWK, BCa, audit)
import rater_luna as rl  # noqa: E402  (read_labels, AH_LABELS, INDEP_LABELS only)

SEED = 20260913
B_DEFAULT = 10_000
KAPPA_HH_SOURCE = 0.595          # AH vs second rater, S, 188 cells (S21 / main text)
MARGIN = 0.10                    # non-inferiority margin on kappa (pre-specified, PLAN.md section 5)
NI_FLOOR = round(KAPPA_HH_SOURCE - MARGIN, 3)   # 0.495
THR = {"alpha_lo": 0.80, "qwk_lo": 0.70, "pi_range_pp": 5.0}
S21_RAW = HARNESS / "llm_rater_luna_2026-10-15" / "subgraph_r25" / "luna_rater_subgraph_raw.jsonl"
S21_RESULTS = HARNESS / "llm_rater_luna_2026-10-15" / "subgraph_r25" / "results_llm_rater_luna_subgraph.json"
CELLS_JSONL = HARNESS / "real_run" / "cells.jsonl"
E1_RUNS = ["a1", "a2", "b1", "b2", "b3", "c1", "c2"]          # GLM-4.7-Flash, amended plan (no run 0: S21 luna labels are a separate source)
E1_SETS = {"all7": E1_RUNS, "a_temp0": ["a1", "a2"], "b_temp07": ["b1", "b2", "b3"], "c_paraphrase": ["a1", "c1", "c2"]}
DESCRIPTIVE = {"openai_luna_s21", "qwen_same_family"}   # reported next to the family raters, never a required family:
#   the existing S21 luna labels, and the same-family contrast rater (Qwen3.8-Flash-Next = the extractor's family)
N_FAMILIES_REQUIRED = 3


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ statistics (numpy, bit-checked in selfcheck)
def kappa_bin(x, y) -> float:
    """Cohen's kappa for two binary vectors; a degenerate chance term gives 0.0 (as agreement_ci in S21)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    po = float(np.mean(x == y))
    px, py = float(x.mean()), float(y.mean())
    pe = px * py + (1 - px) * (1 - py)
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def qwk(l, r, maximum: int = 3) -> float:
    l = np.asarray(l, dtype=int)
    r = np.asarray(r, dtype=int)
    n = len(l)
    cm = np.bincount(l * (maximum + 1) + r, minlength=(maximum + 1) ** 2).reshape(maximum + 1, maximum + 1).astype(float)
    lev = np.arange(maximum + 1)
    w = (lev[:, None] - lev[None, :]) ** 2
    observed = float((cm * w).sum()) / n
    lc, rc = cm.sum(1), cm.sum(0)
    expected = float((lc[:, None] * rc[None, :] * w).sum()) / (n * n)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1.0 - observed / expected


def alpha_binary(X) -> float:
    """Krippendorff's alpha, nominal, two categories, units x coders matrix (NaN = missing)."""
    X = np.asarray(X, dtype=float)
    valid = ~np.isnan(X)
    m = valid.sum(1)
    use = m >= 2
    X, m = X[use], m[use]
    n1 = np.nansum(X, axis=1)
    n0 = m - n1
    o_off = float(np.sum(2.0 * n1 * n0 / (m - 1)))
    N1, N0 = float(n1.sum()), float(n0.sum())
    n = N1 + N0
    den = 2.0 * N1 * N0
    if den == 0:
        return 1.0 if o_off == 0 else 0.0
    return 1.0 - (n - 1.0) * o_off / den


def mean_pairwise_qwk(R) -> float:
    k = R.shape[1]
    vals = [qwk(R[:, i], R[:, j]) for i in range(k) for j in range(i + 1, k)]
    return float(np.mean(vals))


def boot_multi(items: list[dict], stats: dict, B: int = B_DEFAULT, seed: int = SEED) -> dict:
    """Same resampling scheme as analyze_holdout.cluster_bootstrap_stat (whole clusters, unstratified, BCa 95%,
    leave-one-cluster-out jackknife, midrank ties), evaluating many statistics on the SAME resamples.
    Each item: {"cluster_id": str, "i": int index into the caller's arrays}.  Verified bit-exact in selfcheck."""
    groups = ah._group_clusters(items, None, "cluster_id")
    clusters = [cl for st in groups for cl in st]
    cl_idx = [np.array([c["i"] for c in cl], dtype=int) for cl in clusters]
    allidx = np.concatenate(cl_idx)
    theta = {k: ah._finite(f(allidx), f"estimate {k}") for k, f in stats.items()}
    rng = np.random.default_rng(seed)
    boot = {k: np.empty(B) for k in stats}
    n_s = len(groups[0])
    for b in range(B):
        draws = rng.integers(0, n_s, n_s).tolist()
        idx = np.concatenate([cl_idx[i] for i in draws])
        for k, f in stats.items():
            boot[k][b] = ah._finite(f(idx), f"bootstrap {k}")
    jack = {k: [] for k in stats}
    for j in range(len(clusters)):
        idx = np.concatenate([cl_idx[i] for i in range(len(clusters)) if i != j])
        for k, f in stats.items():
            jack[k].append(ah._finite(f(idx), f"jackknife {k}"))
    out = {}
    for k in stats:
        lo, hi = ah._bca_interval(theta[k], boot[k], jack[k], ah.RESOLVE_ALPHA, ah.DEFAULT_BCA_TIES)
        out[k] = {"estimate": theta[k], "ci_lo": lo, "ci_hi": hi, "n_cells": len(items), "n_clusters": len(clusters),
                  "B": B, "seed": seed, "method": "BCa cluster bootstrap"}
    return out


# ------------------------------------------------------------------ inputs
def load_manifest() -> tuple[dict, list[dict]]:
    m = json.loads((HERE / "cells_manifest.json").read_text(encoding="utf-8"))
    return m, sorted(m["cells"], key=lambda c: c["cell_id"])


def read_jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


class Labels:
    """Per run: first valid record per cell -> S_raw, R_raw, span check recomputed, S_final, R_floor."""

    def __init__(self, cells: list[dict]):
        self.cells = cells
        self.cmap = {c["cell_id"]: c for c in cells}
        self._text: dict[str, str] = {}
        self.mismatch: dict[str, int] = {}

    def text(self, path: str) -> str:
        if path not in self._text:
            self._text[path] = (ACCESS / path).read_text(encoding="utf-8")
        return self._text[path]

    def from_records(self, run: str, recs: list[dict]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        self.mismatch[run] = 0
        for r in recs:
            cid = r.get("cell_id")
            if not r.get("valid") or cid in out or cid not in self.cmap:
                continue
            row = self.cmap[cid]
            s_raw = int(r["S_raw"] if "S_raw" in r else r["S"])
            r_raw = int(r["R_raw"] if "R_raw" in r else r["R"])
            span = r.get("span") or ""
            path = row["full_path"] if r.get("view_kind") == "full_view" else row["view_path"]
            verb = None
            if s_raw == 1:
                verb = bool(collapse(span)) and collapse(span) in collapse(self.text(path))
            s_final = 1 if (s_raw == 1 and verb) else 0
            r_floor = max(r_raw, 1) if s_final == 1 else r_raw
            if "S_final" in r and (r["S_final"] != s_final or r["R_floor"] != r_floor):
                self.mismatch[run] += 1
            out[cid] = {"S_raw": s_raw, "R_raw": r_raw, "S_final": s_final, "R_floor": r_floor, "verbatim": verb,
                        "tok_in": ((r.get("usage") or {}).get("prompt_tokens")), "tok_out": ((r.get("usage") or {}).get("completion_tokens"))}
        return out


def human_labels(ids: list[str]) -> dict[str, dict[str, np.ndarray]]:
    ah_lab = rl.read_labels(rl.AH_LABELS)
    ind_lab = rl.read_labels(rl.INDEP_LABELS)
    return {"AH": {"S": np.array([ah_lab[i]["S"] for i in ids], float), "R": np.array([ah_lab[i]["R"] for i in ids], float)},
            "IND": {"S": np.array([ind_lab[i]["S"] for i in ids], float), "R": np.array([ind_lab[i]["R"] for i in ids], float)}}


def to_arrays(lab: dict[str, dict], ids: list[str]) -> dict[str, np.ndarray]:
    S = np.array([lab[i]["S_final"] if i in lab else np.nan for i in ids], float)
    Sr = np.array([lab[i]["S_raw"] if i in lab else np.nan for i in ids], float)
    R = np.array([lab[i]["R_floor"] if i in lab else np.nan for i in ids], float)
    Rr = np.array([lab[i]["R_raw"] if i in lab else np.nan for i in ids], float)
    return {"S_final": S, "S_raw": Sr, "R_floor": R, "R_raw": Rr}


# ------------------------------------------------------------------ Experiment 1
def e1_block(run_arr: dict, cells: list[dict], Jv: np.ndarray, sel: np.ndarray, skey: str, rkey: str, B: int,
             runs: list[str] | None = None, refs: dict | None = None) -> dict:
    runs = [r for r in (runs or E1_RUNS) if r in run_arr]
    # complete-case: cells valid in every available run of the set
    ok = sel.copy()
    for r in runs:
        ok &= ~np.isnan(run_arr[r][skey]) & ~np.isnan(run_arr[r][rkey])
    idx_cells = np.where(ok)[0]
    items = [{"cluster_id": cells[i]["cluster_id"], "i": int(i)} for i in idx_cells]
    SM = {r: run_arr[r][skey] for r in runs}
    RM = {r: run_arr[r][rkey] for r in runs}
    S = np.column_stack([SM[r] for r in runs])
    R = np.column_stack([RM[r] for r in runs])
    col = {r: k for k, r in enumerate(runs)}
    stats = {}
    for name, members in E1_SETS.items():
        members = [r for r in members if r in col]
        if len(members) < 2:
            continue
        cs = [col[r] for r in members]
        stats[f"alpha:{name}"] = (lambda idx, cs=cs: alpha_binary(S[idx][:, cs]))
        stats[f"qwk_mean_pairwise:{name}"] = (lambda idx, cs=cs: mean_pairwise_qwk(R[idx][:, cs]))
        stats[f"pi_range_pp:{name}"] = (lambda idx, cs=cs: 100.0 * float(np.ptp([np.mean((Jv[idx] >= 2) & (S[idx, c] == 0)) for c in cs])))
    for r in runs:
        stats[f"pi_hat:{r}"] = (lambda idx, c=col[r]: float(np.mean((Jv[idx] >= 2) & (S[idx, c] == 0))))
    for rn, sv in (refs or {}).items():
        stats[f"pi_hat_ref:{rn}"] = (lambda idx, sv=sv: float(np.mean((Jv[idx] >= 2) & (sv[idx] == 0))))
    res = boot_multi(items, stats, B=B)
    out = {"n_cells": len(items), "n_clusters": res[next(iter(res))]["n_clusters"] if res else None, "runs_used": runs,
           "S_key": skey, "R_key": rkey, "stats": res}
    # per-run summaries (point values)
    out["per_run"] = {r: {"S1_share": float(np.mean(SM[r][idx_cells])), "R_mean": float(np.mean(RM[r][idx_cells])),
                          "pi_hat": res[f"pi_hat:{r}"]["estimate"]} for r in runs}
    return out


def e1_status(block: dict) -> dict:
    """Pre-specified three-state rule (PLAN.md section 5.4)."""
    st = block["stats"]
    detail, point_fail, bound_fail, missing = {}, False, False, []
    for name in E1_SETS:
        ka, kq, kr = f"alpha:{name}", f"qwk_mean_pairwise:{name}", f"pi_range_pp:{name}"
        if ka not in st:
            missing.append(name)
            continue
        a, q, rg = st[ka], st[kq], st[kr]
        d = {"alpha": {"estimate": a["estimate"], "ci_lo": a["ci_lo"], "point_ok": a["estimate"] >= THR["alpha_lo"], "bound_ok": a["ci_lo"] >= THR["alpha_lo"]},
             "qwk": {"estimate": q["estimate"], "ci_lo": q["ci_lo"], "point_ok": q["estimate"] >= THR["qwk_lo"], "bound_ok": q["ci_lo"] >= THR["qwk_lo"]},
             "pi_range_pp": {"estimate": rg["estimate"], "ci_hi": rg["ci_hi"], "point_ok": rg["estimate"] <= THR["pi_range_pp"]}}
        d["all_point_ok"] = d["alpha"]["point_ok"] and d["qwk"]["point_ok"] and d["pi_range_pp"]["point_ok"]
        d["all_bound_ok"] = d["alpha"]["bound_ok"] and d["qwk"]["bound_ok"] and d["pi_range_pp"]["point_ok"]
        point_fail |= not d["all_point_ok"]
        bound_fail |= not d["all_bound_ok"]
        detail[name] = d
    if missing or "all7" not in detail:
        status = "unresolved"
        why = f"incomplete data: condition sets not computable: {missing or ['all7']}"
    elif point_fail:
        status = "not supported"
        why = "at least one criterion fails on its point estimate in the pooled set or in a condition set"
    elif bound_fail:
        status = "unresolved"
        why = "all point estimates meet the thresholds but at least one BCa lower bound (alpha, QWK) does not"
    else:
        status = "supported"
        why = "alpha lower bound >= 0.80, QWK lower bound >= 0.70 and pi-hat range <= 5 pp in the pooled set and in each condition set"
    return {"status": status, "reason": why, "sets": detail}


# ------------------------------------------------------------------ Experiment 2
def e2_block(fam: dict[str, dict], hum: dict, cells: list[dict], sel: np.ndarray, B: int, skey="S_final", rkey="R_floor") -> dict:
    names = [n for n in fam]
    ok = sel.copy()
    for n in names:
        ok &= ~np.isnan(fam[n][skey]) & ~np.isnan(fam[n][rkey])
    idx_cells = np.where(ok)[0]
    items = [{"cluster_id": cells[i]["cluster_id"], "i": int(i)} for i in idx_cells]
    Sx = {n: fam[n][skey] for n in names}
    Rx = {n: fam[n][rkey] for n in names}
    Sx.update({"AH": hum["AH"]["S"], "IND": hum["IND"]["S"]})
    Rx.update({"AH": hum["AH"]["R"], "IND": hum["IND"]["R"]})
    llm = names
    fam3 = [n for n in names if n not in DESCRIPTIVE]
    stats = {}
    stats["kappa:AH-IND"] = lambda idx: kappa_bin(Sx["AH"][idx], Sx["IND"][idx])
    stats["qwk:AH-IND"] = lambda idx: qwk(Rx["AH"][idx], Rx["IND"][idx])
    stats["alpha:AH-IND"] = lambda idx: alpha_binary(np.column_stack([Sx["AH"][idx], Sx["IND"][idx]]))
    if len(fam3) >= 2:
        stats["alpha:families"] = lambda idx: alpha_binary(np.column_stack([Sx[n][idx] for n in fam3]))
    if len(llm) > len(fam3):
        stats["alpha:families+descriptive"] = lambda idx: alpha_binary(np.column_stack([Sx[n][idx] for n in llm]))
    for i, a in enumerate(llm):
        for b in llm[i + 1:]:
            stats[f"kappa:{a}-{b}"] = (lambda idx, a=a, b=b: kappa_bin(Sx[a][idx], Sx[b][idx]))
            stats[f"qwk:{a}-{b}"] = (lambda idx, a=a, b=b: qwk(Rx[a][idx], Rx[b][idx]))
            stats[f"kappa_minus_HH:{a}-{b}"] = (lambda idx, a=a, b=b: kappa_bin(Sx[a][idx], Sx[b][idx]) - kappa_bin(Sx["AH"][idx], Sx["IND"][idx]))
    for a in llm:
        for h in ("AH", "IND"):
            stats[f"kappa:{a}-{h}"] = (lambda idx, a=a, h=h: kappa_bin(Sx[a][idx], Sx[h][idx]))
            stats[f"qwk:{a}-{h}"] = (lambda idx, a=a, h=h: qwk(Rx[a][idx], Rx[h][idx]))
            stats[f"kappa_minus_HH:{a}-{h}"] = (lambda idx, a=a, h=h: kappa_bin(Sx[a][idx], Sx[h][idx]) - kappa_bin(Sx["AH"][idx], Sx["IND"][idx]))
    if "qwen_same_family" in names and fam3:
        q = "qwen_same_family"
        for f in fam3:
            for h in ("AH", "IND"):
                stats[f"kappa_qwen_minus_family:{f}-{h}"] = (lambda idx, f=f, h=h: kappa_bin(Sx[q][idx], Sx[h][idx]) - kappa_bin(Sx[f][idx], Sx[h][idx]))
        def mean_q_fam(idx):
            return float(np.mean([kappa_bin(Sx[q][idx], Sx[f][idx]) for f in fam3]))
        def mean_q_hum(idx):
            return float(np.mean([kappa_bin(Sx[q][idx], Sx[h][idx]) for h in ("AH", "IND")]))
        def mean_x_hum(idx):
            return float(np.mean([kappa_bin(Sx[f][idx], Sx[h][idx]) for f in fam3 for h in ("AH", "IND")]))
        stats["contrast:mean_kappa_qwen_with_families"] = mean_q_fam
        stats["contrast:mean_kappa_qwen_with_humans"] = mean_q_hum
        stats["contrast:mean_kappa_families_with_humans"] = mean_x_hum
        stats["contrast:qwen_minus_families_with_humans"] = lambda idx: mean_q_hum(idx) - mean_x_hum(idx)
        if len(fam3) >= 2:
            def mean_x_x(idx):
                return float(np.mean([kappa_bin(Sx[a][idx], Sx[b][idx]) for i, a in enumerate(fam3) for b in fam3[i + 1:]]))
            stats["contrast:mean_kappa_between_families"] = mean_x_x
            stats["contrast:qwen_with_families_minus_between_families"] = lambda idx: mean_q_fam(idx) - mean_x_x(idx)
    res = boot_multi(items, stats, B=B)
    return {"n_cells": len(items), "raters": names, "S_key": skey, "R_key": rkey, "stats": res, "families_in_alpha": fam3}


def e2_status(block: dict) -> dict:
    """Pre-specified rule (PLAN.md section 5.4).  Required kappas = pairwise kappas among the family raters and each family
    rater with AH and with the second rater.  Reproducibility raters (gpt-oss next to luna) are reported, not required.
      not supported : the point kappa of at least one required pair is below 0.495 (0.595 - 0.10)
      unresolved    : fewer than 3 independent families have labels (the claim is about three), or every point kappa
                      is >= 0.495 but at least one BCa lower bound is below it
      supported     : 3 families and every required kappa has a BCa lower bound >= 0.495"""
    st = block["stats"]
    fam3 = block["families_in_alpha"]
    req = []
    for i, a in enumerate(fam3):
        for b in fam3[i + 1:]:
            req.append(f"kappa:{a}-{b}")
        for h in ("AH", "IND"):
            req.append(f"kappa:{a}-{h}")
    rows = {}
    for k in req:
        s = st[k]
        d = st[k.replace("kappa:", "kappa_minus_HH:")]
        rows[k] = {"kappa": s["estimate"], "ci_lo": s["ci_lo"], "ci_hi": s["ci_hi"],
                   "ni_fixed_reference_point": s["estimate"] >= NI_FLOOR, "ni_fixed_reference_bound": s["ci_lo"] >= NI_FLOOR,
                   "diff_vs_HH": d["estimate"], "diff_ci_lo": d["ci_lo"], "diff_ci_hi": d["ci_hi"],
                   "ni_paired_diff_bound": d["ci_lo"] > -MARGIN}
    if not req:
        return {"status": "unresolved", "reason": "fewer than two family raters have complete labels", "rows": {}, "n_families": len(fam3)}
    point_fail = [k for k, r in rows.items() if not r["ni_fixed_reference_point"]]
    bound_fail = [k for k, r in rows.items() if not r["ni_fixed_reference_bound"]]
    if point_fail:
        status, why = "not supported", f"point kappa below {NI_FLOOR} for: {point_fail}"
    elif len(fam3) < N_FAMILIES_REQUIRED:
        status, why = "unresolved", (f"only {len(fam3)} independent famil{'y' if len(fam3) == 1 else 'ies'} with labels ({', '.join(fam3)}); the claim is about "
                                     f"{N_FAMILIES_REQUIRED}.  Available required kappas: point >= {NI_FLOOR} for all; lower bound below it for {bound_fail or 'none'}")
    elif bound_fail:
        status, why = "unresolved", f"all point kappas >= {NI_FLOOR} but the BCa lower bound is below it for: {bound_fail}"
    else:
        status, why = "supported", f"every required kappa has a BCa lower bound >= {NI_FLOOR} (fixed reference 0.595, margin 0.10)"
    return {"status": status, "reason": why, "rows": rows, "ni_floor": NI_FLOOR, "n_families": len(fam3),
            "paired_sensitivity_all_ok": all(r["ni_paired_diff_bound"] for r in rows.values())}


def lean_block(fam: dict, hum: dict, sel: np.ndarray) -> dict:
    """Descriptive: on the cells where AH and the second rater disagree on S, which side each rater takes (aggregates)."""
    ah_s, in_s = hum["AH"]["S"], hum["IND"]["S"]
    dis = sel & (ah_s != in_s)
    out = {"n_disagree_cells_in_set": int(dis.sum()),
           "AH1_IND0": int((dis & (ah_s == 1)).sum()), "AH0_IND1": int((dis & (ah_s == 0)).sum()), "raters": {}}
    for n, a in fam.items():
        s = a["S_final"]
        d = dis & ~np.isnan(s)
        out["raters"][n] = {"n_scored": int(d.sum()), "agrees_with_AH": int((d & (s == ah_s)).sum()),
                            "agrees_with_IND": int((d & (s == in_s)).sum()),
                            "S1_when_AH1_IND0": int((d & (ah_s == 1) & (s == 1)).sum()),
                            "S1_when_AH0_IND1": int((d & (ah_s == 0) & (s == 1)).sum())}
    return out


def majority_audit(maj: list[str], fb_source: str, arr: dict, cells: list[dict], out_dir: Path, sealed_dir: Path, tag: str,
                   standin: bool) -> dict:
    """Majority-vote label source (S = majority of S_final, R = median of R_floor over the three raters in ``maj``).
    The 6 cells without a subgraph view cannot be scored by the open-weight / Claude raters: they carry the single
    ``fb_source`` label (the existing S21 luna label; documented).  Then the UNCHANGED analyzer."""
    ids = [c["cell_id"] for c in cells]
    fb_ids = {c["cell_id"] for c in cells if c["view_kind"] != "subgraph"}
    rows, n_single = [], 0
    for k, cid in enumerate(ids):
        svals = [arr[n]["S_final"][k] for n in maj]
        rvals = [arr[n]["R_floor"][k] for n in maj]
        if all(not np.isnan(v) for v in svals):
            s = 1 if sum(svals) * 2 > len(svals) else 0
            r = int(np.median(rvals))
        elif cid in fb_ids and not np.isnan(arr[fb_source]["S_final"][k]):
            s, r = int(arr[fb_source]["S_final"][k]), int(arr[fb_source]["R_floor"][k])
            n_single += 1
        else:
            return {"status": "not run", "reason": f"cell {cid} has no complete label set"}
        rows.append((cid, s, r))
    lab_csv = out_dir / f"labels_for_analysis_{tag}.csv"
    with lab_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "A", "rater_L1", "label_source"])
        for cid, s, r in rows:
            w.writerow([cid, s, r, "LLM, not human"])
    sealed_dir.mkdir(parents=True, exist_ok=True)
    an_out = out_dir / f"holdout_results_{tag}.json"
    cmd = [sys.executable, str(HARNESS / "analyze_holdout.py"), str(CELLS_JSONL), "--seed", str(SEED), "--labels", str(lab_csv),
           "--out", str(an_out), "--out-cells", str(sealed_dir / f"analyzer_cells_{tag}.json")]
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ACCESS))
    res = {"majority_raters": maj, "third_rater_is_standin_for_missing_family": standin, "single_label_cells_source": fb_source,
           "labels_csv": lab_csv.name, "single_label_cells": n_single, "S1": int(sum(s for _, s, _ in rows)), "n_cells": len(rows),
           "analyzer_cmd": "analyze_holdout.py real_run/cells.jsonl --seed 20260913 --labels <csv> --out <json> --out-cells <sealed>",
           "returncode": p.returncode}
    if p.returncode == 0:
        d = json.loads(an_out.read_text(encoding="utf-8"))
        res["pi_hat"] = d["pi_hat"]
        res["gates"] = {k: {"status": v.get("status"), "value": v.get("value")} for k, v in d["gates"].items()}
        res["status"] = "ok"
    else:
        res["status"] = "analyzer failed"
        res["stderr_tail"] = p.stderr[-1500:]
    return res


# ------------------------------------------------------------------ selfcheck
def selfcheck() -> int:
    rng = np.random.default_rng(1)
    bad = []
    for _ in range(200):
        l, r = rng.integers(0, 4, 40), rng.integers(0, 4, 40)
        if abs(qwk(l, r) - ah._qwk_from_values(l, r)) > 1e-12:
            bad.append("qwk")
    X = rng.integers(0, 2, (30, 4)).astype(float)
    X[3, 1] = np.nan
    X[7, 2] = np.nan
    # naive coincidence-matrix alpha
    o = np.zeros((2, 2))
    for u in X:
        v = u[~np.isnan(u)].astype(int)
        m = len(v)
        for i in range(m):
            for j in range(m):
                if i != j:
                    o[v[i], v[j]] += 1.0 / (m - 1)
    nc = o.sum(1)
    n = nc.sum()
    naive = 1 - (n - 1) * (o[0, 1] + o[1, 0]) / (2 * nc[0] * nc[1])
    if abs(naive - alpha_binary(X)) > 1e-12:
        bad.append("alpha")
    # bit-exact vs the registered routine, on S21 data (AH vs second rater, kappa and QWK)
    cells = []
    m, cl = load_manifest()
    ids = [c["cell_id"] for c in cl]
    hum = human_labels(ids)
    recs = [{"cluster_id": c["cluster_id"], "sa": int(hum["AH"]["S"][k]), "sb": int(hum["IND"]["S"][k]),
             "ra": int(hum["AH"]["R"][k]), "rb": int(hum["IND"]["R"][k])} for k, c in enumerate(cl)]
    ref_k = ah.cluster_bootstrap_stat(recs, lambda c: rl.cohen_kappa_binary([r["sa"] for r in c], [r["sb"] for r in c]) or 0.0, B=2000, seed=SEED)
    ref_q = ah.cluster_bootstrap_stat(recs, lambda c: ah._qwk_from_values([r["ra"] for r in c], [r["rb"] for r in c]), B=2000, seed=SEED)
    items = [{"cluster_id": c["cluster_id"], "i": k} for k, c in enumerate(cl)]
    mine = boot_multi(items, {"k": lambda idx: kappa_bin(hum["AH"]["S"][idx], hum["IND"]["S"][idx]),
                              "q": lambda idx: qwk(hum["AH"]["R"][idx], hum["IND"]["R"][idx])}, B=2000)
    for key, ref in (("k", ref_k), ("q", ref_q)):
        for f in ("estimate", "ci_lo", "ci_hi"):
            if abs(mine[key][f] - ref[f]) > 1e-12:
                bad.append(f"boot {key}.{f}: {mine[key][f]} vs {ref[f]}")
    # S21 published values reproduced (B = 10000)
    pub = json.loads(S21_RESULTS.read_text(encoding="utf-8"))["agreement_188"]["baseline_AH_vs_IND"]
    full = boot_multi(items, {"k": lambda idx: kappa_bin(hum["AH"]["S"][idx], hum["IND"]["S"][idx]),
                              "q": lambda idx: qwk(hum["AH"]["R"][idx], hum["IND"]["R"][idx])}, B=B_DEFAULT)
    for key, name in (("k", "S_kappa"), ("q", "R_qwk")):
        for f in ("estimate", "ci_lo", "ci_hi"):
            if abs(full[key][f] - pub[name][f]) > 1e-9:
                bad.append(f"S21 published {name}.{f}: {full[key][f]} vs {pub[name][f]}")
    print(json.dumps({"selfcheck": "FAIL" if bad else "PASS", "problems": bad, "kappa_HH": full["k"], "qwk_HH": full["q"]}, indent=1))
    return 1 if bad else 0


# ------------------------------------------------------------------ main analysis
def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def ci(d, nd=3):
    return f"{d['estimate']:.{nd}f} [{d['ci_lo']:.{nd}f}, {d['ci_hi']:.{nd}f}]"


def token_cost(raw_dir: Path) -> dict:
    out = {}
    for p in sorted(raw_dir.glob("*.jsonl")):
        if p.name.endswith(".meta.jsonl"):
            continue
        recs = read_jsonl(p)
        pt = sum((a.get("prompt_tokens") or 0) for r in recs for a in r.get("attempts", []))
        ct = sum((a.get("completion_tokens") or 0) for r in recs for a in r.get("attempts", []))
        meta = read_jsonl(p.with_name(p.stem + ".meta.jsonl"))
        wall = sum(m.get("wall_s", 0) for m in meta)
        starts = [m["started_utc"] for m in meta if m.get("started_utc")]
        ends = [m["finished_utc"] for m in meta if m.get("finished_utc")]
        span = None
        if starts and ends:
            span = round((datetime.fromisoformat(max(ends)) - datetime.fromisoformat(min(starts))).total_seconds(), 1)
        out[p.stem] = {"records": len(recs), "calls_valid": sum(1 for r in recs if r.get("valid")),
                       "prompt_tokens": pt, "completion_tokens": ct, "wall_s": round(wall, 1), "first_start_to_last_finish_s": span,
                       "first_start_utc": min(starts) if starts else None, "last_finish_utc": max(ends) if ends else None,
                       "stop_reasons": [r for m in meta for r in m.get("stop_reasons", [])],
                       "sha256": sha256_file(p), "invocations": len(meta)}
    return out


def main_run(a) -> int:
    t0 = time.time()
    raw = Path(a.raw_dir)
    out_dir = Path(a.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    m, cells = load_manifest()
    ids = [c["cell_id"] for c in cells]
    sub = np.array([c["view_kind"] == "subgraph" for c in cells])
    Jv = np.array([c["J_registered_judge"] for c in cells], float)
    L = Labels(cells)
    run_arr: dict[str, dict[str, np.ndarray]] = {}
    verb: dict[str, dict] = {}
    files = {"luna_s21": S21_RAW}
    for r in ("a1", "a2", "b1", "b2", "b3", "c1", "c2", "gptoss", "qwen", a.claude):
        files[r] = raw / f"{r}.jsonl"
    present = {}
    for r, p in files.items():
        recs = read_jsonl(p)
        lab = L.from_records(r, recs)
        if lab:
            present[r] = len(lab)
            run_arr[r] = to_arrays(lab, ids)
            s1 = [v for v in lab.values() if v["S_raw"] == 1]
            verb[r] = {"valid_cells": len(lab), "S_raw_1": len(s1), "verbatim": sum(bool(v["verbatim"]) for v in s1),
                       "verbatim_rate": (sum(bool(v["verbatim"]) for v in s1) / len(s1)) if s1 else None,
                       "forced_to_S0": sum(1 for v in s1 if not v["verbatim"]),
                       "S_final_1": sum(v["S_final"] for v in lab.values()),
                       "recomputed_vs_runner_mismatch": L.mismatch.get(r, 0)}
    hum = human_labels(ids)
    res = {"addendum": 28, "created_utc": now(), "B": a.B, "seed": SEED, "n_primary_cells": len(cells), "present_runs": present,
           "claude_run": a.claude, "verbatim_check": verb, "status_note": "post hoc w.r.t. the original plan; pre-specified w.r.t. these new runs"}

    # ---------------- Experiment 1 (rater = GLM-4.7-Flash; 182 cells with a subgraph view)
    have_e1 = [r for r in E1_RUNS if r in run_arr]
    e1 = {"rater": "zai-org/GLM-4.7-Flash", "runs_present": have_e1, "primary_set": "182 subgraph cells"}
    refs = {"AH": hum["AH"]["S"], "IND": hum["IND"]["S"]}
    if "luna_s21" in run_arr:
        refs["luna_s21"] = run_arr["luna_s21"]["S_final"]
    if len(have_e1) >= 2:
        e1["primary"] = e1_block(run_arr, cells, Jv, sub, "S_final", "R_floor", a.B, refs=refs)
        e1["primary_status"] = e1_status(e1["primary"])
        e1["sensitivity_S_raw_R_raw"] = e1_block(run_arr, cells, Jv, sub, "S_raw", "R_raw", a.B)
        e1["sensitivity_S_final_R_raw"] = e1_block(run_arr, cells, Jv, sub, "S_final", "R_raw", a.B)
    else:
        e1["primary_status"] = {"status": "unresolved", "reason": f"fewer than two GLM runs available ({have_e1})"}
    res["experiment1"] = e1

    # ---------------- Experiment 2
    fam_runs: dict[str, str] = {}
    if "a1" in run_arr:
        fam_runs["zhipu_glm"] = "a1"
    if "gptoss" in run_arr:
        fam_runs["openai_open_gptoss"] = "gptoss"
    if a.claude in run_arr:
        fam_runs["anthropic_claude"] = a.claude
    fam_all = {n: run_arr[r] for n, r in fam_runs.items()}
    if "luna_s21" in run_arr:
        fam_all["openai_luna_s21"] = run_arr["luna_s21"]
    if "qwen" in run_arr:
        fam_all["qwen_same_family"] = run_arr["qwen"]
    fam3 = list(fam_runs)
    e2 = {"claude_model_run": a.claude, "family_raters": fam_runs,
          "descriptive_label_sources": [n for n in ("openai_luna_s21", "qwen_same_family") if n in fam_all]}
    fam_primary = {n: fam_all[n] for n in fam3}
    if len(fam3) >= 2:
        # families only: a cell lost by a descriptive rater (e.g. an invalid Qwen reply) must not shrink the required comparisons
        e2["primary"] = e2_block(fam_primary, hum, cells, sub, a.B)
        e2["status"] = e2_status(e2["primary"])
        e2["lean_on_AH_IND_disagreements_182"] = lean_block(fam_all, hum, sub)
        e2["sensitivity_S_raw"] = e2_block(fam_primary, hum, cells, sub, a.B, skey="S_raw", rkey="R_raw")
        if len(fam_all) > len(fam_primary):
            # families + descriptive raters (qwen contrast, S21 luna) on the cells every one of them labeled
            e2["with_descriptive_raters"] = e2_block(fam_all, hum, cells, sub, a.B)
    else:
        e2["status"] = {"status": "unresolved", "reason": f"fewer than two independent families have labels ({fam3})", "n_families": len(fam3)}
    for dn in sorted(DESCRIPTIVE):
        if dn in fam_all:
            dsel = ~np.isnan(fam_all[dn]["S_final"])
            e2[f"{dn}_all_scored_vs_humans"] = e2_block({dn: fam_all[dn]}, hum, cells, dsel, a.B)
            e2[f"lean_on_AH_IND_disagreements_{dn}_all_scored"] = lean_block({dn: fam_all[dn]}, hum, dsel)
    if "openai_luna_s21" in fam_all and len(fam3) >= 2:
        if len(fam3) >= 3:
            maj, standin = fam3[:3], False
        else:
            maj, standin = fam3 + ["openai_luna_s21"], True
        if len(maj) == 3:
            e2["majority_vote_audit"] = majority_audit(maj, "openai_luna_s21", fam_all, cells, out_dir, Path(a.sealed_dir), "majority", standin)
        else:
            e2["majority_vote_audit"] = {"status": "not run", "reason": f"need three raters, have {maj}"}
    else:
        e2["majority_vote_audit"] = {"status": "not run", "reason": f"needs the S21 luna labels and at least two families; have {fam3}"}
    res["experiment2"] = e2

    res["auxiliary_full_rendering"] = {"status": "dropped (amended plan: the luna quota is exhausted; no full-rendering run)"}

    res["cost"] = token_cost(raw)
    res["cost_totals"] = {"prompt_tokens": sum(v["prompt_tokens"] for v in res["cost"].values()),
                          "completion_tokens": sum(v["completion_tokens"] for v in res["cost"].values()),
                          "wall_s_sum_of_invocations": round(sum(v["wall_s"] for v in res["cost"].values()), 1)}
    res["sources"] = {"cells_manifest.json": sha256_file(HERE / "cells_manifest.json"),
                      "S21_luna_raw": sha256_file(S21_RAW), "AH_labels_file": "locked label file read by the existing analyses (sha256 not printed)",
                      "second_rater_labels": str(rl.INDEP_LABELS.relative_to(ACCESS)),
                      "registered_judge_J": str(CELLS_JSONL.relative_to(ACCESS)),
                      "analyzer": "harness/analyze_holdout.py (unchanged)", "analysis_script_sha256": sha256_file(Path(__file__))}
    res["analysis_wall_s"] = round(time.time() - t0, 1)
    (out_dir / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_report(res, out_dir)
    print(json.dumps({"results": str(out_dir / "results.json"), "e1_status": (e1.get("primary_status") or {}).get("status"),
                      "e2_status": (e2.get("status") or {}).get("status"), "wall_s": res["analysis_wall_s"]}))
    return 0


def write_report(res: dict, out_dir: Path) -> None:
    L = ["# Addendum 28 -- LLM-rater stability and cross-family agreement (auto-generated tables)", "",
         "AI-generated analysis; post hoc w.r.t. the original plan, pre-specified w.r.t. these runs (PLAN.md frozen before the first scoring call). "
         "Generated by `analyze_raters.py`; review before use.", ""]
    e1, e2 = res["experiment1"], res["experiment2"]
    L += ["## Verbatim-span check (all labelers)", "", "| run | valid cells | S_raw=1 | verbatim | rate | forced to S=0 | S_final=1 | recomputed != runner |", "|---|---|---|---|---|---|---|---|"]
    for r, v in res["verbatim_check"].items():
        L.append(f"| {r} | {v['valid_cells']} | {v['S_raw_1']} | {v['verbatim']} | {fmt(v['verbatim_rate'])} | {v['forced_to_S0']} | {v['S_final_1']} | {v['recomputed_vs_runner_mismatch']} |")
    L.append("")
    L += ["## Experiment 1 -- test-retest (rater: GLM-4.7-Flash, S21 prompt, 182 subgraph cells)", ""]
    if "primary" in e1:
        st = e1["primary_status"]
        L += [f"Cells: {e1['primary']['n_cells']} ({e1['primary']['n_clusters']} clusters); runs: {', '.join(e1['primary']['runs_used'])}. "
              f"Labels: S after the span check, R with the R>=1 floor when S=1. **Status: {st['status']}** -- {st['reason']}.", "",
              "| set | alpha (S) [BCa 95%] | mean pairwise QWK (R) [BCa 95%] | pi-hat range, pp [BCa 95%] | all point ok | alpha/QWK bounds ok |", "|---|---|---|---|---|---|"]
        sx = e1["primary"]["stats"]
        for name, d in st.get("sets", {}).items():
            L.append(f"| {name} | {ci(sx['alpha:' + name])} | {ci(sx['qwk_mean_pairwise:' + name])} | {ci(sx['pi_range_pp:' + name], 2)} | {d['all_point_ok']} | {d['all_bound_ok']} |")
        L += ["", "Thresholds: alpha lower bound >= 0.80, QWK lower bound >= 0.70, pi-hat range <= 5 pp (point). pi-hat per run (J >= 2 and S = 0, registered-judge J):", "",
              "| run | S=1 share | mean R | pi-hat [BCa 95%] |", "|---|---|---|---|"]
        for r in e1["primary"]["runs_used"]:
            L.append(f"| {r} | {fmt(e1['primary']['per_run'][r]['S1_share'])} | {fmt(e1['primary']['per_run'][r]['R_mean'])} | {ci(sx['pi_hat:' + r])} |")
        refl = [(k[len('pi_hat_ref:'):], v) for k, v in sx.items() if k.startswith("pi_hat_ref:")]
        if refl:
            L += ["", "Reference pi-hat on the same cells: " + "; ".join(f"{n} {ci(v)}" for n, v in refl) + "."]
        for key, title in (("sensitivity_S_raw_R_raw", "S without the span check, raw R"), ("sensitivity_S_final_R_raw", "S after the span check, raw R (no floor)")):
            if key in e1:
                b = e1[key]
                L += ["", f"Sensitivity -- {title} ({b['n_cells']} cells): alpha(all7) {ci(b['stats']['alpha:all7'])}, QWK(all7) {ci(b['stats']['qwk_mean_pairwise:all7'])}, pi-hat range {ci(b['stats']['pi_range_pp:all7'], 2)} pp."]
    else:
        L.append(f"Not computed: {e1['primary_status']['reason']}.")
    L += ["", "## Experiment 2 -- cross-family raters (182 common cells)", ""]
    if "primary" in e2:
        b = e2["primary"]
        L += [f"Raters: {', '.join(b['raters'])}; family raters in the required comparisons: {', '.join(b['families_in_alpha'])}. **Status: {e2['status']['status']}** -- {e2['status']['reason']}.", "",
              f"Reference: AH vs second rater kappa(S) = {ci(b['stats']['kappa:AH-IND'])}, QWK(R) = {ci(b['stats']['qwk:AH-IND'])}, alpha = {ci(b['stats']['alpha:AH-IND'])} on these cells; "
              f"the human-human interval is wide. Non-inferiority floor = 0.595 - 0.10 = {NI_FLOOR}.", ""]
        if "alpha:families" in b["stats"]:
            L.append(f"Krippendorff alpha across the family raters ({', '.join(b['families_in_alpha'])}): {ci(b['stats']['alpha:families'])}.")
        if "alpha:families+descriptive" in b["stats"]:
            L.append(f"Including the S21 luna labels: {ci(b['stats']['alpha:families+descriptive'])}.")
        L += ["", "| pair | kappa(S) [BCa 95%] | NI (lower >= 0.495) | diff vs human-human [BCa 95%] | QWK(R) |", "|---|---|---|---|---|"]
        for k, v in b["stats"].items():
            if k.startswith("kappa:") and k != "kappa:AH-IND":
                pair = k[len("kappa:"):]
                d = b["stats"]["kappa_minus_HH:" + pair]
                q = b["stats"].get("qwk:" + pair)
                L.append(f"| {pair} | {ci(v)} | {v['ci_lo'] >= NI_FLOOR} | {ci(d)} | {ci(q) if q else ''} |")
        if "lean_on_AH_IND_disagreements_182" in e2:
            ln = e2["lean_on_AH_IND_disagreements_182"]
            L += ["", f"Descriptive: AH and the second rater disagree on S in {ln['n_disagree_cells_in_set']} of the common cells (AH=1/IND=0: {ln['AH1_IND0']}, AH=0/IND=1: {ln['AH0_IND1']}).", "",
                  "| rater | scored | agrees with AH | agrees with second rater | S=1 when AH=1,IND=0 | S=1 when AH=0,IND=1 |", "|---|---|---|---|---|---|"]
            for n, v in ln["raters"].items():
                L.append(f"| {n} | {v['n_scored']} | {v['agrees_with_AH']} | {v['agrees_with_IND']} | {v['S1_when_AH1_IND0']} | {v['S1_when_AH0_IND1']} |")
    else:
        L.append(f"Not computed: {e2['status']['reason']}.")
    for dn in sorted(DESCRIPTIVE):
        key = f"{dn}_all_scored_vs_humans"
        if key in e2:
            b = e2[key]
            L += ["", f"{dn} (descriptive; {b['n_cells']} cells it scored): kappa with AH {ci(b['stats'][f'kappa:{dn}-AH'])}, with the second rater {ci(b['stats'][f'kappa:{dn}-IND'])}; "
                  f"AH vs second rater on the same cells {ci(b['stats']['kappa:AH-IND'])}."]
    if "with_descriptive_raters" in e2:
        b = e2["with_descriptive_raters"]
        L += ["", f"### Pairs including the descriptive raters (cells labeled by every rater: {b['n_cells']})", "",
              "| pair | kappa(S) [BCa 95%] | diff vs human-human [BCa 95%] | QWK(R) |", "|---|---|---|---|"]
        for k, v in b["stats"].items():
            if k.startswith("kappa:") and k != "kappa:AH-IND" and any(d in k for d in DESCRIPTIVE):
                pair = k[len("kappa:"):]
                d = b["stats"]["kappa_minus_HH:" + pair]
                q = b["stats"].get("qwk:" + pair)
                L.append(f"| {pair} | {ci(v)} | {ci(d)} | {ci(q) if q else ''} |")
        L.append(f"AH vs second rater on these cells: {ci(b['stats']['kappa:AH-IND'])}.")
    if "with_descriptive_raters" in e2 and "contrast:mean_kappa_qwen_with_humans" in e2["with_descriptive_raters"]["stats"]:
        sx = e2["with_descriptive_raters"]["stats"]
        L += ["", "### Same-family contrast (Qwen3.8-Flash-Next, the extractor's family) next to the cross-family raters", "",
              f"Mean kappa(S) with the two humans: qwen {ci(sx['contrast:mean_kappa_qwen_with_humans'])}; cross-family raters {ci(sx['contrast:mean_kappa_families_with_humans'])}; "
              f"difference {ci(sx['contrast:qwen_minus_families_with_humans'])}."]
        if "contrast:mean_kappa_between_families" in sx:
            L.append(f"Mean kappa between raters: qwen with the cross-family raters {ci(sx['contrast:mean_kappa_qwen_with_families'])}; between the cross-family raters {ci(sx['contrast:mean_kappa_between_families'])}; "
                     f"difference {ci(sx['contrast:qwen_with_families_minus_between_families'])}.")
        L += ["", "| cross-family rater | kappa(qwen, AH) - kappa(rater, AH) | kappa(qwen, second rater) - kappa(rater, second rater) |", "|---|---|---|"]
        for f in e2["with_descriptive_raters"]["families_in_alpha"]:
            L.append(f"| {f} | {ci(sx[f'kappa_qwen_minus_family:{f}-AH'])} | {ci(sx[f'kappa_qwen_minus_family:{f}-IND'])} |")
        L.append("Descriptive; no threshold. Qwen is not counted among the cross-family raters in any status rule.")
    ma = e2.get("majority_vote_audit")
    if ma:
        L += ["", "### Majority-vote label source (unchanged audit)", ""]
        if ma.get("status") == "ok":
            ph = ma["pi_hat"]
            L += [f"Source: majority S over {', '.join(ma['majority_raters'])}, median R"
                  + ("; the third rater is the S21 luna labels standing in for the missing family" if ma["third_rater_is_standin_for_missing_family"] else "")
                  + f"; {ma['single_label_cells']} cells without a subgraph view carry the S21 luna label only. "
                  f"pi-hat = {ph['pi_hat']:.4f} [{fmt(ph.get('ci_lo'), 4)}, {fmt(ph.get('ci_hi'), 4)}] (events {ph['events']}/{ph['n_cells']}). Gates: "
                  + ", ".join(f"{k}={v['status']}" for k, v in ma["gates"].items()) + "."]
        else:
            L.append(f"{ma.get('status')}: {ma.get('reason', ma.get('stderr_tail', ''))}")
    L += ["", "## Cost", "", "| run file | valid | prompt tokens | completion tokens | wall s (sum of invocations) |", "|---|---|---|---|---|"]
    for r, v in res["cost"].items():
        L.append(f"| {r} | {v['calls_valid']} | {v['prompt_tokens']:,} | {v['completion_tokens']:,} | {v['wall_s']} |")
    t = res["cost_totals"]
    L += ["", f"Totals: {t['prompt_tokens']:,} prompt tokens, {t['completion_tokens']:,} completion tokens (usage fields; failed attempts included).", ""]
    (out_dir / "REPORT_auto.md").write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selfcheck")
    r = sub.add_parser("run")
    r.add_argument("--raw-dir", default=str(HERE / "raw"))
    r.add_argument("--out-dir", default=str(HERE))
    r.add_argument("--claude", default="haiku", choices=("haiku", "opus"))
    r.add_argument("--B", type=int, default=B_DEFAULT)
    r.add_argument("--sealed-dir", default="private_analyzer_cells")
    a = ap.parse_args()
    return selfcheck() if a.cmd == "selfcheck" else main_run(a)


if __name__ == "__main__":
    sys.exit(main())
