#!/usr/bin/env python3
"""Analysis of addendum 32 (Study 2: LLM evidence labels on a retrieval view).  AI-generated; a person must review and test
it before reuse.  LLM-labeled; not human-validated beyond Stage 1.  Rules and thresholds are those of PLAN.md (commit 678d938),
implemented without change.

  python3 analyze.py stage1     Stage 1 calibration gate (reads raw/<model>_stage1.jsonl, the two de-identified human analysis
                                files through review6_reanalysis/common.load_188 ONLY here, never in tests) -> results_stage1.json
  python3 analyze.py stage2     Stage 2 audit (only if results_stage1.json says PASS) -> results_stage2.json
  python3 analyze.py merge      results.json + REPORT_auto.md from the two parts

Intervals: question-clustered BCa, 95%, B = 10,000, seed 20260913 (review6_reanalysis/common.fast_bca = the analyzer's draws).
No per-cell human label and no per-cell human-LLM disagreement is written (aggregates only).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HARNESS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


RC = _load("rc_common", HARNESS / "review6_reanalysis" / "common.py")     # loaders and the vectorised BCa
import analyze_holdout as ah  # noqa: E402
import s2_personas as PS  # noqa: E402

SEED, B = ah.REGISTERED_SEED, ah.BOOTSTRAP_RESAMPLES
assert (SEED, B) == (20260913, 10_000)
PERSONAS = list(PS.PERSONAS)
SEEDS = [1, 2, 3, 4, 5]
SLOTS = [(p, s) for p in PERSONAS for s in SEEDS]
N_SLOTS = 25
MIN_VALID = 15                 # PLAN 32.5: a cell label needs >= 15 valid slots of 25
THR_CONSISTENT = 23            # R25
MIN_CELLS = 30                 # PLAN 32.6
MARGIN = 0.10
PRIMARY_MODELS = ["glm", "gptoss"]
MODELS = ["glm", "gptoss", "qwen"]
LAT_FLOOR_S = 0.5              # PLAN 32.9 G7
RAW = HERE / "raw"
BANNER = "LLM-labeled; not human-validated beyond Stage 1."


def rnd(x, nd=4):
    if x is None:
        return None
    try:
        if isinstance(x, (float, np.floating)):
            return None if not math.isfinite(float(x)) else round(float(x), nd)
    except Exception:
        pass
    return x


# ---------------------------------------------------------------- slot matrices and cell labels (PLAN 32.5)
def read_jsonl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def slot_matrices(records: list[dict], cell_ids: list[str]) -> dict:
    """S_final and R_raw per (cell, slot); NaN = invalid / missing.  The last terminal record of a slot wins."""
    pos = {c: i for i, c in enumerate(cell_ids)}
    col = {(p, s): k for k, (p, s) in enumerate(SLOTS)}
    S = np.full((len(cell_ids), N_SLOTS), np.nan)
    R = np.full((len(cell_ids), N_SLOTS), np.nan)
    skip = set()
    for r in records:
        c = r.get("cell_id")
        if c not in pos:
            continue
        if r.get("status") == "context_skip":
            skip.add(c)
            continue
        k = col.get((r.get("persona"), r.get("seed")))
        if k is None or r.get("status") not in ("ok", "invalid"):
            continue
        i = pos[c]
        if r["status"] == "ok":
            S[i, k] = float(r["S_final"])
            R[i, k] = float(r["R_raw"])
        else:
            S[i, k] = np.nan
            R[i, k] = np.nan
    return {"S": S, "R": R, "context_skip": skip}


def cell_labels(S: np.ndarray, R: np.ndarray) -> dict:
    """Majority label (needs >= MIN_VALID valid slots; a tie -> undefined), lower-median rating, R25 consistency."""
    valid = ~np.isnan(S)
    nv = valid.sum(1)
    c1 = np.nansum(np.where(valid, S, 0.0), axis=1)
    c0 = nv - c1
    L = np.where(c1 > c0, 1.0, np.where(c0 > c1, 0.0, np.nan))
    L = np.where(nv >= MIN_VALID, L, np.nan)
    srt = np.sort(np.where(np.isnan(R), np.inf, R), axis=1)
    idx = np.clip((np.isfinite(srt).sum(1) - 1) // 2, 0, N_SLOTS - 1)
    med = srt[np.arange(len(srt)), idx]
    Rc = np.where((nv >= MIN_VALID) & np.isfinite(med), med, np.nan)
    cons = np.maximum(c0, c1) >= THR_CONSISTENT
    return {"L": L, "R": Rc, "n_valid": nv, "c1": c1, "c0": c0, "consistent": cons}


def split_half_rating(R: np.ndarray):
    """G2 analogue: lower median of the seed-1..3 slots (15) and of the seed-4..5 slots (10), per cell (PLAN 32.9)."""
    cols_a = [k for k, (p, s) in enumerate(SLOTS) if s in (1, 2, 3)]
    cols_b = [k for k, (p, s) in enumerate(SLOTS) if s in (4, 5)]

    def lower_median(M):
        v = ~np.isnan(M)
        srt = np.sort(np.where(np.isnan(M), np.inf, M), axis=1)
        n = v.sum(1)
        out = srt[np.arange(len(srt)), np.clip((n - 1) // 2, 0, M.shape[1] - 1)]
        return np.where(n >= 1, out, np.nan)
    return lower_median(R[:, cols_a]), lower_median(R[:, cols_b])


# ---------------------------------------------------------------- statistics helpers (copies of review10's, checked in tests)
def csum(cluster_ids, cols: np.ndarray) -> np.ndarray:
    ids = [str(c) for c in cluster_ids]
    u = sorted(set(ids))
    pos = {c: i for i, c in enumerate(u)}
    M = np.zeros((len(u), cols.shape[1]))
    np.add.at(M, [pos[c] for c in ids], cols)
    return M


def bca(M: np.ndarray, f, B_: int = B, seed: int = SEED) -> dict:
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
    cols = np.stack([np.asarray(flag, float), np.ones(len(flag))], 1)
    return stat(cl, cols, lambda s: s[:, 0] / s[:, 1])


def pi_flags(J: np.ndarray, S: np.ndarray) -> np.ndarray:
    return ((J >= 2) & (S == 0)).astype(float)


# ---------------------------------------------------------------- the Stage 1 gate rule (PLAN 32.6) -- pure functions
def pair_passes(n_cells: int, kappa_lo, hh_kappa) -> bool:
    """(model, human) passes iff n >= 30 and the lower bound of kappa(L, h) >= kappa(AH, R2) on the same cells - 0.10."""
    if n_cells < MIN_CELLS or kappa_lo is None or hh_kappa is None:
        return False
    return bool(kappa_lo >= hh_kappa - MARGIN)


def stage1_verdict(per_model: dict[str, dict]) -> dict:
    """PASS iff at least one PRIMARY model passes both humans.  per_model[m] = {"AH": bool, "R2": bool}."""
    passing = [m for m in PRIMARY_MODELS if m in per_model and per_model[m].get("AH") and per_model[m].get("R2")]
    headline = "glm" if "glm" in passing else ("gptoss" if "gptoss" in passing else None)
    return {"pass": bool(passing), "passing_models": passing, "headline_labeler": headline,
            "rule": "PASS iff at least one primary model (glm, gptoss) passes both humans; qwen never counts"}


def human_block(cl, L, hum: dict, J) -> dict:
    out = {"n_cells": int(len(L)), "n_clusters": len(set(map(str, cl)))}
    a, r = hum["AH"], hum["R2"]
    hh = {"kappa": kappa_ci(cl, a, r), "agreement": agree_ci(cl, a, r)}
    out["human_human_same_cells"] = hh
    out["vs_human"] = {}
    for h, x in (("AH", a), ("R2", r)):
        kap = kappa_ci(cl, L, x)
        d = stat(cl, np.hstack([pair_cols(L, x), pair_cols(a, r)]), lambda s: kappa_flat(s[:, :4]) - kappa_flat(s[:, 4:]))
        ref = None if hh["kappa"]["est"] is None else hh["kappa"]["est"] - MARGIN
        close = pair_passes(out["n_cells"], kap["lo"], hh["kappa"]["est"])
        out["vs_human"][h] = {"kappa": kap, "agreement": agree_ci(cl, L, x), "delta_kappa_vs_human_human": d,
                              "gate_ref_kappa_minus_0.10": rnd(ref), "gate_pass": close}
    pl = lambda x: stat(cl, np.stack([pi_flags(J, x), np.ones(len(x))], 1), lambda s: s[:, 0] / s[:, 1])
    out["pi_hat"] = {"LLM": pl(L), "AH": pl(a), "R2": pl(r)}
    for h, x in (("AH", a), ("R2", r)):
        cols = np.stack([pi_flags(J, L), pi_flags(J, x), np.ones(len(L))], 1)
        out["pi_hat"][f"LLM_minus_{h}"] = stat(cl, cols, lambda s: (s[:, 0] - s[:, 1]) / s[:, 2])
    out["share_label1"] = share_ci(cl, L)
    return out


def latency_stats(records: list[dict]) -> dict:
    lat = np.array([r["latency_s"] for r in records if r.get("latency_s") is not None and r.get("status") in ("ok", "invalid")], float)
    n_calls = sum(1 for r in records if r.get("status") in ("ok", "invalid"))
    n_ts = sum(1 for r in records if r.get("status") in ("ok", "invalid") and r.get("started_at_utc"))
    if not len(lat):
        return {"n_calls": n_calls, "n_with_latency": 0}
    return {"n_calls": n_calls, "n_with_latency": int(len(lat)), "n_with_timestamp": n_ts,
            "p05": rnd(np.percentile(lat, 5), 2), "p50": rnd(np.percentile(lat, 50), 2), "p95": rnd(np.percentile(lat, 95), 2),
            "max": rnd(lat.max(), 2), f"share_below_{LAT_FLOOR_S}s": rnd(float((lat < LAT_FLOOR_S).mean()), 4),
            "prompt_tokens": int(sum((r.get("prompt_tokens") or 0) for r in records)),
            "completion_tokens": int(sum((r.get("completion_tokens") or 0) for r in records))}


# ---------------------------------------------------------------- Stage 1
def model_block_stage1(df, ids, recs, hum_cols, J, cluster) -> dict:
    m = slot_matrices(recs, ids)
    lab = cell_labels(m["S"], m["R"])
    ok = ~np.isnan(lab["L"])
    out = {"cells_attempted": int(len(ids)), "context_skip": len(m["context_skip"]),
           "cells_with_label": int(ok.sum()), "cells_undefined": int((~ok).sum()),
           "parse_valid_slot_share": rnd(float((~np.isnan(m["S"])).mean()), 4)}
    if ok.sum() == 0:
        return out
    cl = cluster[ok]
    L = lab["L"][ok]
    hum = {h: hum_cols[h][ok] for h in hum_cols}
    out["primary"] = human_block(cl, L, hum, J[ok])
    cons = lab["consistent"][ok]
    out["R25_coverage"] = share_ci(cl, cons)
    if cons.sum() >= 5:
        out["R25_subset"] = human_block(cl[cons], L[cons], {h: hum[h][cons] for h in hum}, J[ok][cons])
    else:
        out["R25_subset"] = {"n_cells": int(cons.sum()), "note": "fewer than 5 consistent cells: not evaluated"}
    out["alpha_25_slots"] = stat(cluster, alpha_cols(m["S"]), alpha_from)
    # rating agreement with the humans' R (descriptive; the model rating has no floor)
    Rl = lab["R"][ok]
    for h, key in (("AH", "R_AH"), ("R2", "R_2")):
        if key in df:
            Rh = df[key].to_numpy(float)[ok]
            out.setdefault("rating_vs_human", {})[h] = {"exact": rnd(float((Rl == Rh).mean())), "mae": rnd(float(np.abs(Rl - Rh).mean())),
                                                        "mean_R_llm": rnd(float(Rl.mean())), "mean_R_human": rnd(float(Rh.mean()))}
    out["mae_J_vs_R_llm"] = rnd(float(np.abs(J[ok] - Rl).mean()))
    return out


def stage1(write: bool = True) -> dict:
    man = json.loads((HERE / "manifests" / "stage1.json").read_text(encoding="utf-8"))
    rows = man["rows"]
    prim = sorted([r for r in rows if r["cell_kind"] == "primary"], key=lambda r: r["cell_id"])
    ctrl = sorted([r for r in rows if r["cell_kind"] != "primary"], key=lambda r: r["cell_id"])
    df = RC.load_188().sort_values("cell_id").reset_index(drop=True)          # human labels: here and only here
    ids = [r["cell_id"] for r in prim]
    assert ids == list(df.cell_id), "manifest cells differ from the 188 analysis cells"
    cluster = df.cq_id.to_numpy()
    J = df.J.to_numpy(float)
    hum_cols = {"AH": df.S_AH.to_numpy(float), "R2": df.S_2.to_numpy(float)}
    res = {"banner": BANNER, "stage": 1, "plan": "PLAN.md (addendum 32)", "n_cells": len(ids), "n_clusters": int(len(set(cluster))),
           "human_human_all188": {"kappa": kappa_ci(cluster, hum_cols["AH"], hum_cols["R2"]),
                                  "pi_hat_AH": stat(cluster, np.stack([pi_flags(J, hum_cols["AH"]), np.ones(len(J))], 1), lambda s: s[:, 0] / s[:, 1]),
                                  "pi_hat_R2": stat(cluster, np.stack([pi_flags(J, hum_cols["R2"]), np.ones(len(J))], 1), lambda s: s[:, 0] / s[:, 1])},
           "models": {}, "controls": {}, "latency": {}}
    cids = [r["cell_id"] for r in ctrl]
    verdict_in = {}
    for model in MODELS:
        recs = read_jsonl(RAW / f"{model}_stage1.jsonl")
        if not recs:
            res["models"][model] = {"status": "no records (endpoint down or not run)"}
            continue
        blk = model_block_stage1(df, ids, recs, hum_cols, J, cluster)
        res["models"][model] = blk
        res["latency"][model] = latency_stats(recs)
        if model in PRIMARY_MODELS and "primary" in blk:
            verdict_in[model] = {h: blk["primary"]["vs_human"][h]["gate_pass"] for h in ("AH", "R2")}
        # negative control (diagnostic): share of the 24 registered ablated controls labeled S = 0
        mc = slot_matrices(recs, cids)
        lc = cell_labels(mc["S"], mc["R"])
        n_ok = int((~np.isnan(lc["L"])).sum())
        res["controls"][model] = {"n_controls": len(cids), "labeled": n_ok, "label0": int((lc["L"] == 0).sum()),
                                  "label1": int((lc["L"] == 1).sum()), "undefined": len(cids) - n_ok}
    res["gate"] = stage1_verdict(verdict_in)
    man_p = [r for r in prim]
    res["view_coverage"] = view_coverage(man_p)
    res["raw_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RAW.glob("*_stage1.jsonl"))}
    if write:
        (HERE / "results_stage1.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def view_coverage(prim_rows: list[dict]) -> dict:
    out = {"n_cells": len(prim_rows), "target": 0.90}
    for key in ("view_holds_terms", "full_holds_terms", "subgraph_view_holds_terms"):
        out[key] = int(sum(bool(r[key]) for r in prim_rows))
        out[key + "_share"] = rnd(out[key] / max(1, len(prim_rows)))
    ceil = [r for r in prim_rows if r["full_holds_terms"]]
    out["view_holds_given_full_holds"] = {"n": len(ceil), "k": int(sum(bool(r["view_holds_terms"]) for r in ceil)),
                                          "share": rnd(sum(bool(r["view_holds_terms"]) for r in ceil) / max(1, len(ceil)))}
    out["by_variant"] = {}
    for v in sorted({r["variant"] for r in prim_rows}):
        rs = [r for r in prim_rows if r["variant"] == v]
        out["by_variant"][v] = {"n": len(rs), "view": int(sum(bool(r["view_holds_terms"]) for r in rs)),
                                "full": int(sum(bool(r["full_holds_terms"]) for r in rs)),
                                "subgraph": int(sum(bool(r["subgraph_view_holds_terms"]) for r in rs))}
    out["span_located"] = {"cells_with_span": int(sum(1 for r in prim_rows if r["span_given"])),
                           "all_pieces_found": int(sum(1 for r in prim_rows if r["span_given"] and r["span_pieces_found"] == r["span_pieces_total"] > 0))}
    out["fallback_used"] = int(sum(bool(r["fallback_used"]) for r in prim_rows))
    out["cap_reached"] = int(sum(bool(r["cap_reached"]) for r in prim_rows))
    return out


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stage1"
    if mode == "stage1":
        r = stage1()
        print(json.dumps({"gate": r["gate"], "models": {m: {k: v for k, v in b.items() if k in ("cells_with_label", "cells_undefined")} for m, b in r["models"].items()}}, indent=1))
    else:
        import s2_stage2_analysis as S2A  # noqa: E402  (written with Stage 2)
        raise SystemExit(S2A.main(mode))
