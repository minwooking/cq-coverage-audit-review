#!/usr/bin/env python3
"""Analysis of the addendum-26 non-Qwen judge runs (exploratory, descriptive).

AI-generated draft; the author must review and test it before the numbers are used.

Implements PLAN.md 26.6 and nothing else: per-judge A->B (holdout subgraph, development) with
question-clustered BCa intervals (B = 10,000, seed 20260913, via analyze_holdout.cluster_bootstrap_delta),
per-variant means and coverage, run-to-run exact agreement and ICC, offsets and agreement against luna
(subgraph) and the registered holdout judge, contrast-direction agreement, unsupported-credit rate pi-hat
against the independent rater's S labels, controls, and cost.  Writes results.json and REPORT.md.
Reads no sealed file: AH labels are only read when the author passes --ah-labels PATH.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
REPO = ACCESS.parent.parent
sys.path.insert(0, str(HARNESS))

import analyze_holdout as ah  # noqa: E402

SEED = 20260913
B = 10_000
JUDGES = ("gptoss", "glm")
JUDGE_LABEL = {"gptoss": "gpt-oss-20b", "glm": "GLM-4.7-Flash"}
VARIANTS = list("ABCDEF")
CONTRASTS = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"), ("D", "F")]
STUDIES = ("holdout_subgraph", "dev")
REPEATS = (1, 2, 3)

HOLDOUT_CELLS = HARNESS / "real_run" / "cells.jsonl"
LUNA_CELLS = HARNESS / "length_experiment" / "cells_length.jsonl"
DEV_QWEN = REPO / "output" / "abcdef_evaluation.json"
DEV_GEMINI = REPO / "output_judge3" / "abcdef_evaluation.json"
SALVAGE_RE = re.compile(r'^\s*\{\s*"score"\s*:\s*([0-3])(?:\.0+)?\s*[,}]')
IND_LABELS = ACCESS / "annotation" / "second_pass_2026-10-13" / "v3" / "labels_for_analysis_v3.csv"


# ----------------------------------------------------------------------------- loading
def load_jobs(path: Path) -> dict[str, dict]:
    return {j["cell_id"]: {k: j[k] for k in ("study", "cell_id", "cell_kind", "variant", "cq_id", "cluster_id")}
            for j in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


def load_raw(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def first_valid(records: list[dict], salvage: bool = False) -> dict[tuple[str, int], dict]:
    """First valid record per (cell, repeat).  salvage=True (POST-FREEZE sensitivity, not in PLAN) also accepts an
    invalid record whose raw reply starts with {"score": N, (truncated JSON: the score is the first key)."""
    out: dict[tuple[str, int], dict] = {}
    for r in records:
        if r["repeat"] < 1 or (r["cell_id"], r["repeat"]) in out:
            continue
        if r.get("valid"):
            out[(r["cell_id"], r["repeat"])] = r
        elif salvage and r.get("status") == "invalid" and r.get("raw_content"):
            m = SALVAGE_RE.match(str(r["raw_content"]))
            if m:
                out[(r["cell_id"], r["repeat"])] = dict(r, J=int(m.group(1)), valid=True, salvaged=True)
    return out


def holdout_reference_scores() -> tuple[dict, dict]:
    """(variant, cq) -> J for the registered holdout judge (full view) and luna (subgraph), primary cells."""
    gem = {}
    for line in HOLDOUT_CELLS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            if c.get("cell_kind") == "primary" and c.get("judge_response_parsed") and int(c["J"]) in range(4):
                gem[(c["variant"], c["cq_id"])] = int(c["J"])
    luna = {}
    for line in LUNA_CELLS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            c = json.loads(line)
            if c["condition"] == "subgraph" and c.get("judge_response_parsed") and int(c["J"]) in range(4):
                luna[(c["variant"], c["cq_id"])] = int(c["J"])
    return gem, luna


def dev_reference_scores() -> tuple[dict, dict]:
    out = []
    for p in (DEV_QWEN, DEV_GEMINI):
        ev = json.loads(p.read_text(encoding="utf-8"))["layer1"]["cq_scores"]
        out.append({(v, q): int(s) for v, d in ev.items() for q, s in d.items()})
    return out[0], out[1]


def load_labels(path: Path) -> dict[tuple[str, str], int]:
    out = {}
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cid = r["cell_id"]
            if cid.startswith("primary:"):
                _, v, cq = cid.split(":")
                out[(v, cq)] = int(r["A"])
    return out


# ----------------------------------------------------------------------------- statistics
def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def mean(xs):
    xs = list(xs)
    return float(np.mean(xs)) if xs else float("nan")


def bca_stat(cells: list[dict], stat_fn) -> dict:
    """BCa cluster bootstrap of stat_fn over cells (dicts with cluster_id)."""
    if len({c["cluster_id"] for c in cells}) < 2:
        return {"estimate": float(stat_fn(cells)) if cells else None, "ci_lo": None, "ci_hi": None, "n_cells": len(cells)}
    r = ah.cluster_bootstrap_stat(cells, stat_fn, None, "cluster_id", B, SEED)
    return {"estimate": r["estimate"], "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"], "n_cells": r["n_cells"],
            "n_clusters": r["n_clusters"]}


def contrast(scores: dict, v1: str, v2: str, cluster_of: dict) -> dict | None:
    """Mean per-question (v2 - v1) with a question-clustered BCa interval."""
    d: dict[str, list[float]] = defaultdict(list)
    for (v, cq), s in scores.items():
        if v == v2 and (v1, cq) in scores:
            d[cluster_of[cq]].append(s - scores[(v1, cq)])
    n_pairs = sum(len(x) for x in d.values())
    if len(d) < 2:
        return None
    r = ah.cluster_bootstrap_delta(d, B, SEED)
    return {"delta": r["delta"], "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"], "n_pairs": n_pairs,
            "n_clusters": r["n_clusters"]}


def sign(x: float) -> int:
    return 0 if abs(x) < 1e-9 else (1 if x > 0 else -1)


def pair_deltas(scores: dict, v1: str, v2: str) -> dict[str, float]:
    return {cq: s - scores[(v1, cq)] for (v, cq), s in scores.items() if v == v2 and (v1, cq) in scores}


def icc_from_matrix(mat: np.ndarray) -> tuple[float, float]:
    n, k = mat.shape
    gm = mat.mean()
    ssr = k * float(((mat.mean(1) - gm) ** 2).sum())
    ssc = n * float(((mat.mean(0) - gm) ** 2).sum())
    sse = float(((mat - gm) ** 2).sum()) - ssr - ssc
    msr, msc, mse = ssr / (n - 1), ssc / (k - 1), max(sse, 0.0) / ((n - 1) * (k - 1))
    if msr <= 1e-15:
        return float("nan"), float("nan")
    denom1 = msr + (k - 1) * mse + k * (msc - mse) / n
    denom2 = msr + (msc - mse) / n
    return (msr - mse) / denom1, (msr - mse) / denom2


def icc_ci(rows: list[tuple[str, tuple]]) -> dict:
    """ICC(2,1), ICC(2,3) with a percentile question-clustered bootstrap (nan resamples dropped)."""
    mat = np.array([r[1] for r in rows], dtype=float)
    p21, p2k = icc_from_matrix(mat)
    clusters = defaultdict(list)
    for cid, vec in rows:
        clusters[cid].append(vec)
    keys = sorted(clusters)
    rng = np.random.default_rng(SEED)
    b21, b2k = [], []
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        sample = np.array([v for i in pick for v in clusters[keys[i]]], dtype=float)
        a, b = icc_from_matrix(sample)
        if not math.isnan(a):
            b21.append(a)
            b2k.append(b)

    def ci(x):
        return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if x else [None, None]
    return {"icc_2_1": p21, "icc_2_1_ci": ci(b21), "icc_2_k": p2k, "icc_2_k_ci": ci(b2k),
            "n_cells": len(rows), "n_boot_valid": len(b21), "ci_method": "percentile question-clustered bootstrap"}


def agreement(left: list[int], right: list[int]) -> dict:
    left, right = np.asarray(left), np.asarray(right)
    return {"n": int(len(left)), "exact": float(np.mean(left == right)), "within1": float(np.mean(np.abs(left - right) <= 1)),
            "qwk": float(ah._qwk_from_values(left, right)), "mean_diff": float(np.mean(left - right))}


# ----------------------------------------------------------------------------- per judge analysis
class JudgeRuns:
    def __init__(self, judge: str, records: list[dict], jobs: dict[str, dict], salvage: bool = False):
        self.judge, self.records, self.jobs = judge, records, jobs
        self.valid = first_valid(records, salvage)
        self.n_salvaged = sum(1 for r in self.valid.values() if r.get("salvaged"))
        self.n_salvaged_by_study = dict(Counter(jobs[c]["study"] for (c, _), r in self.valid.items() if r.get("salvaged")))
        self.j: dict[tuple[str, int], int] = {k: int(r["J"]) for k, r in self.valid.items()}

    def cells(self, study: str, kind: str | None = None) -> list[str]:
        return sorted(c for c, m in self.jobs.items()
                      if m["study"] == study and (kind is None or m["cell_kind"] == kind))

    def repeat_scores(self, study: str, r: int, kind: str = "primary") -> dict[tuple[str, str], int]:
        return {(self.jobs[c]["variant"], self.jobs[c]["cq_id"]): self.j[(c, r)]
                for c in self.cells(study, kind) if (c, r) in self.j}

    def mean_scores(self, study: str, kind: str = "primary") -> dict[tuple[str, str], float]:
        out = {}
        for c in self.cells(study, kind):
            vals = [self.j[(c, r)] for r in REPEATS if (c, r) in self.j]
            if vals:
                out[(self.jobs[c]["variant"], self.jobs[c]["cq_id"])] = float(np.mean(vals))
        return out

    def full_cells(self, study: str, kind: str = "primary") -> list[str]:
        return [c for c in self.cells(study, kind) if all((c, r) in self.j for r in REPEATS)]


def cluster_map(jobs: dict[str, dict], study: str) -> dict[str, str]:
    """cq -> cluster; the whole bank for the holdout (references also cover cells the jobs do not)."""
    out = {m["cq_id"]: m["cluster_id"] for m in jobs.values() if m["study"] == study}
    if study.startswith("holdout"):
        with (ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
            out.update({r["cq_id"]: r["cluster_id"] for r in csv.DictReader(fh)})
    return out


def contrasts_block(scores: dict, cmap: dict) -> dict:
    return {f"{a}->{b}": contrast(scores, a, b, cmap) for a, b in CONTRASTS}


def variant_table(scores: dict, cmap: dict) -> dict:
    """per variant: n, mean J, coverage (share J >= 2; per-cell mean over repeats for the judges)."""
    out = {}
    for v in VARIANTS:
        cells = [{"cluster_id": cmap[cq], "x": s, "cov": float(s >= 2)} for (vv, cq), s in sorted(scores.items()) if vv == v]
        if not cells:
            out[v] = None
            continue
        out[v] = {"n": len(cells), "mean_J": bca_stat(cells, lambda cs: float(np.mean([c["x"] for c in cs]))),
                  "coverage": bca_stat(cells, lambda cs: float(np.mean([c["cov"] for c in cs])))}
    return out


def coverage_scores(runs: JudgeRuns, study: str) -> dict:
    """per-cell share of valid repeats with J >= 2 (used for coverage means)."""
    out = {}
    for c in runs.cells(study, "primary"):
        vals = [runs.j[(c, r)] for r in REPEATS if (c, r) in runs.j]
        if vals:
            out[(runs.jobs[c]["variant"], runs.jobs[c]["cq_id"])] = float(np.mean([v >= 2 for v in vals]))
    return out


def run_to_run(runs: JudgeRuns, study: str, cmap: dict) -> dict:
    full = runs.full_cells(study)
    if len(full) < 3:
        return {"n_cells": len(full), "note": "too few cells with 3 valid repeats"}
    mat = [(cmap[runs.jobs[c]["cq_id"]], tuple(runs.j[(c, r)] for r in REPEATS)) for c in full]
    pair_ag = [np.mean([v[0] == v[1], v[0] == v[2], v[1] == v[2]]) for _, v in mat]
    ident = [len(set(v)) == 1 for _, v in mat]
    cells_a = [{"cluster_id": cid, "x": float(a)} for (cid, _), a in zip(mat, pair_ag)]
    cells_i = [{"cluster_id": cid, "x": float(i)} for (cid, _), i in zip(mat, ident)]
    sd = float(np.mean([np.std(v) for _, v in mat]))
    return {"n_cells": len(full), "pairwise_exact_agreement": bca_stat(cells_a, lambda cs: float(np.mean([c["x"] for c in cs]))),
            "all_three_identical": bca_stat(cells_i, lambda cs: float(np.mean([c["x"] for c in cs]))),
            "mean_within_cell_sd": sd, **icc_ci(mat),
            "n_cells_with_any_disagreement": int(sum(not i for i in ident))}


def vs_reference(runs: JudgeRuns, study: str, ref: dict, cmap: dict) -> dict:
    """offset (mean J_judge - J_ref), exact, within-1 and QWK per repeat (then averaged) on shared cells."""
    per_rep = []
    for r in REPEATS:
        sc = runs.repeat_scores(study, r)
        keys = sorted(k for k in sc if k in ref)
        if keys:
            per_rep.append({"repeat": r, **agreement([sc[k] for k in keys], [ref[k] for k in keys])})
    ms = runs.mean_scores(study)
    keys = sorted(k for k in ms if k in ref)
    cells = [{"cluster_id": cmap[cq], "d": ms[(v, cq)] - ref[(v, cq)]} for (v, cq) in keys]
    off = bca_stat(cells, lambda cs: float(np.mean([c["d"] for c in cs]))) if cells else None
    avg = {m: float(np.mean([p[m] for p in per_rep])) for m in ("exact", "within1", "qwk", "mean_diff")} if per_rep else None
    return {"n_shared_cells": len(keys), "offset_repeat_mean": off, "per_repeat": per_rep, "mean_over_repeats": avg}


def direction_agreement(js: dict, ref: dict, label: str) -> dict:
    """sign agreement of the six contrasts on shared cells, and per-question A->B delta signs."""
    shared = set(js) & set(ref)
    jj = {k: js[k] for k in shared}
    rr = {k: ref[k] for k in shared}
    rows, agree = {}, 0
    for a, b in CONTRASTS:
        dj, dr = pair_deltas(jj, a, b), pair_deltas(rr, a, b)
        if not dj:
            continue
        mj, mr = mean(dj.values()), mean(dr.values())
        rows[f"{a}->{b}"] = {"judge_delta": mj, "ref_delta": mr, "judge_sign": sign(mj), "ref_sign": sign(mr),
                             "same_sign": sign(mj) == sign(mr), "n_pairs": len(dj)}
        agree += sign(mj) == sign(mr)
    dj, dr = pair_deltas(jj, "A", "B"), pair_deltas(rr, "A", "B")
    per_q = {"n_pairs": len(dj), "same_sign": int(sum(sign(dj[q]) == sign(dr[q]) for q in dj)),
             "both_nonzero_same_direction": int(sum(sign(dj[q]) != 0 and sign(dj[q]) == sign(dr[q]) for q in dj)),
             "both_nonzero": int(sum(sign(dj[q]) != 0 and sign(dr[q]) != 0 for q in dj))}
    return {"reference": label, "contrasts": rows, "n_contrasts_same_sign": int(agree), "n_contrasts": len(rows),
            "per_question_A_to_B": per_q}


def pi_hat_block(scores_by_repeat: dict[int, dict], labels: dict, jobs_cluster: dict) -> dict:
    out = {}
    for r, sc in scores_by_cell_items(scores_by_repeat):
        cells = [{"cell_id": f"primary:{v}:{cq}", "cluster_id": jobs_cluster[cq], "J": j, "A": labels[(v, cq)]}
                 for (v, cq), j in sorted(sc.items()) if (v, cq) in labels]
        if len(cells) < 2:
            continue
        res = ah.silent_over_credit_rate(cells, B=B, seed=SEED)
        out[str(r)] = {k: res.get(k) for k in ("events", "n_cells", "pi_hat", "ci_lo", "ci_hi", "n_clusters",
                                               "clusters_with_event")}
    if out:
        vals = [v["pi_hat"] for v in out.values()]
        out["summary"] = {"mean": float(np.mean(vals)), "min": float(np.min(vals)), "max": float(np.max(vals)),
                          "n_repeats": len(vals)}
    return out


def scores_by_cell_items(d: dict[int, dict]):
    return sorted(d.items())


def controls_block(runs: JudgeRuns) -> dict:
    out = {}
    for kind in ("ablated_control", "preserved_control"):
        cells = runs.cells("holdout_control", kind)
        per_rep = []
        for r in REPEATS:
            js = [runs.j[(c, r)] for c in cells if (c, r) in runs.j]
            if js:
                per_rep.append({"repeat": r, "n": len(js), "share_J_ge_2": float(np.mean([j >= 2 for j in js])),
                                "mean_J": float(np.mean(js))})
        out[kind] = {"n_cells_planned": len(cells), "per_repeat": per_rep,
                     "mean_share_J_ge_2": float(np.mean([p["share_J_ge_2"] for p in per_rep])) if per_rep else None}
    return out


def cost_block(runs: JudgeRuns) -> dict:
    out = {}
    for study in ("holdout_subgraph", "holdout_control", "dev", "all"):
        recs = [r for r in runs.records if r["repeat"] >= 1 and (study == "all" or r["study"] == study)]
        if not recs:
            continue
        att = [len(r.get("attempts", [])) or 1 for r in recs]
        starts = [datetime.fromisoformat(r["started_utc"]) for r in recs]
        ends = [s.timestamp() + (r.get("latency_s") or 0) for s, r in zip(starts, recs)]
        out[study] = {
            "calls": len(recs), "valid": sum(1 for r in recs if r.get("valid")),
            "invalid": sum(1 for r in recs if r["status"] == "invalid"),
            "context_skip": sum(1 for r in recs if r["status"] == "context_skip"),
            "cells_needing_retry": sum(1 for a in att if a > 1), "requests_sent": int(sum(att)),
            "prompt_tokens_final_attempt": int(sum(r.get("prompt_tokens") or 0 for r in recs)),
            "prompt_tokens_all_attempts_est": int(sum((r.get("prompt_tokens") or 0) * a for r, a in zip(recs, att))),
            "completion_tokens_final_attempt": int(sum(r.get("completion_tokens") or 0 for r in recs)),
            "sum_latency_s": round(sum(r.get("latency_s") or 0 for r in recs), 1),
            "wall_span_s": round(max(ends) - min(s.timestamp() for s in starts), 1),
            "lenient_parse": sum(1 for r in recs if r.get("lenient_parse")),
            "finish_length": sum(1 for r in recs if r.get("finish_reason") == "length"),
        }
    return out


def distribution(runs: JudgeRuns, study: str, kind: str = "primary") -> dict:
    cnt = Counter(j for (c, r), j in runs.j.items() if runs.jobs[c]["study"] == study and runs.jobs[c]["cell_kind"] == kind)
    n = sum(cnt.values())
    return {"counts": {str(k): cnt.get(k, 0) for k in range(4)}, "n": n,
            "mean": float(sum(k * v for k, v in cnt.items()) / n) if n else None}


def invalid_cells(runs: JudgeRuns) -> list[dict]:
    """(cell, repeat) pairs without a valid score."""
    out = []
    for c, m in sorted(runs.jobs.items()):
        for r in REPEATS:
            if (c, r) not in runs.j:
                rec = next((x for x in runs.records if x["cell_id"] == c and x["repeat"] in (r, 0)), None)
                out.append({"cell_id": c, "repeat": r, "status": rec["status"] if rec else "not_run"})
    return out


def invalid_summary(items: list[dict]) -> dict:
    """missing (cell, repeat) pairs by study and variant, and the number of cells with no valid repeat."""
    out: dict = {}
    by_cell = Counter((i["cell_id"]) for i in items)
    for i in items:
        m = i["cell_id"].split(":")
        st = "dev" if m[0] == "dev" else ("holdout_control" if m[0] != "primary" else "holdout_subgraph")
        out.setdefault(st, Counter())[m[1]] += 1
    return {"missing_pairs_by_study_variant": {k: dict(v) for k, v in out.items()},
            "cells_with_no_valid_repeat": sum(1 for c, n in by_cell.items() if n == 3),
            "cells_with_some_missing_repeat": len(by_cell)}


def analyse(jobs_path: Path, raw_dir: Path, labels: dict[str, Path], salvage: bool = False) -> dict:
    jobs = load_jobs(jobs_path)
    gem, luna = holdout_reference_scores()
    qwen, gem3 = dev_reference_scores()
    cm = {s: cluster_map(jobs, s) for s in ("holdout_subgraph", "dev", "holdout_control")}
    label_sets = {name: load_labels(p) for name, p in labels.items()}
    res: dict = {"generated_utc": datetime.now(timezone.utc).isoformat(), "seed": SEED, "B": B,
                 "judges": {}, "references": {}, "interjudge": {}}
    runs = {j: JudgeRuns(j, load_raw(raw_dir / f"raw_{j}.jsonl"), jobs, salvage) for j in JUDGES}

    # references on their own full sets
    ref_sets = {"holdout_subgraph": {"registered_gemini_J_full_view": gem, "luna_subgraph": luna},
                "dev": {"qwen_dev_judge": qwen, "gemini3_flash_lite_dev": gem3}}
    for study, refs in ref_sets.items():
        res["references"][study] = {}
        for name, sc in refs.items():
            res["references"][study][name] = {
                "n_cells": len(sc), "contrasts": contrasts_block(sc, cm[study]),
                "variant_means": variant_table({k: float(v) for k, v in sc.items()}, cm[study]),
                "variant_coverage_only": {v: mean([float(s >= 2) for (vv, q), s in sc.items() if vv == v]) for v in VARIANTS}}
    # pi-hat references on the 182 subgraph cells
    sub_keys = {(m["variant"], m["cq_id"]) for m in jobs.values() if m["study"] == "holdout_subgraph" and m["cell_kind"] == "primary"}
    for name, sc in ref_sets["holdout_subgraph"].items():
        on_jobs = {k: float(v) for k, v in sc.items() if k in sub_keys}
        res["references"]["holdout_subgraph"][name]["contrasts_on_job_cells"] = contrasts_block(on_jobs, cm["holdout_subgraph"])
        res["references"]["holdout_subgraph"][name]["n_job_cells"] = len(on_jobs)
    for lname, labs in label_sets.items():
        res["references"].setdefault("pi_hat", {})[lname] = {
            "registered_gemini_J_full_view": pi_hat_block({1: {k: v for k, v in gem.items() if k in sub_keys}}, labs, cm["holdout_subgraph"]),
            "luna_subgraph": pi_hat_block({1: {k: v for k, v in luna.items() if k in sub_keys}}, labs, cm["holdout_subgraph"])}

    for j, rn in runs.items():
        jr: dict = {"label": JUDGE_LABEL[j], "n_records": len(rn.records), "n_salvaged_scores": rn.n_salvaged,
                    "n_salvaged_by_study": rn.n_salvaged_by_study}
        if not rn.records:
            jr["note"] = "no records (endpoint unusable or not run)"
            res["judges"][j] = jr
            continue
        jr["cost"] = cost_block(rn)
        jr["invalid_or_missing"] = invalid_cells(rn)
        jr["invalid_summary"] = invalid_summary(jr["invalid_or_missing"])
        for study in STUDIES:
            ms = rn.mean_scores(study)
            if not ms:
                continue
            sr: dict = {"n_cells_scored": len(ms), "distribution": distribution(rn, study),
                        "contrasts": contrasts_block(ms, cm[study]),
                        "variant_means": variant_table(ms, cm[study]),
                        "variant_coverage": variant_table(coverage_scores(rn, study), cm[study]),
                        "run_to_run": run_to_run(rn, study, cm[study])}
            sr["A_to_B_per_repeat"] = {str(r): contrast(rn.repeat_scores(study, r), "A", "B", cm[study]) for r in REPEATS
                                       if rn.repeat_scores(study, r)}
            if study == "dev":
                two = {}
                for (c, m) in [(c, m) for c, m in jobs.items() if m["study"] == "dev"]:
                    if (c, 1) in rn.j and (c, 2) in rn.j:
                        two[(m["variant"], m["cq_id"])] = round_half_up((rn.j[(c, 1)] + rn.j[(c, 2)]) / 2)
                sr["A_to_B_paper_convention_halfup_mean_of_repeats_1_2"] = contrast({k: float(v) for k, v in two.items()}, "A", "B", cm[study])
            refs = ref_sets[study]
            sr["vs_reference"] = {name: vs_reference(rn, study, sc, cm[study]) for name, sc in refs.items()}
            sr["direction_agreement"] = {name: direction_agreement(ms, {k: float(v) for k, v in sc.items()}, name)
                                         for name, sc in refs.items()}
            if study == "holdout_subgraph":
                sr["pi_hat"] = {}
                for lname, labs in label_sets.items():
                    sr["pi_hat"][lname] = pi_hat_block({r: rn.repeat_scores(study, r) for r in REPEATS if rn.repeat_scores(study, r)},
                                                       labs, cm[study])
            jr[study] = sr
        jr["holdout_control"] = controls_block(rn)
        res["judges"][j] = jr

    # inter-judge agreement
    a, b = runs["gptoss"], runs["glm"]
    for study in STUDIES:
        per = []
        for r in REPEATS:
            sa, sb = a.repeat_scores(study, r), b.repeat_scores(study, r)
            keys = sorted(set(sa) & set(sb))
            if keys:
                per.append({"repeat": r, **agreement([sa[k] for k in keys], [sb[k] for k in keys])})
        if per:
            res["interjudge"][study] = {"per_repeat": per, "mean_exact": float(np.mean([p["exact"] for p in per])),
                                        "mean_qwk": float(np.mean([p["qwk"] for p in per]))}
        ma, mb = a.mean_scores(study), b.mean_scores(study)
        if ma and mb:
            res["interjudge"].setdefault(study, {})["direction_agreement_gptoss_vs_glm"] = direction_agreement(
                ma, mb, "glm")
    return res


# ----------------------------------------------------------------------------- report
def f(x, nd=3, plus=False):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:+.{nd}f}" if plus else f"{x:.{nd}f}"


def ci(d, nd=3, plus=False):
    if not d or d.get("ci_lo") is None:
        return "n/a"
    return f"[{f(d['ci_lo'], nd, plus)}, {f(d['ci_hi'], nd, plus)}]"


def crow(label, name, c):
    if not c:
        return f"| {label} | {name} | n/a | n/a | n/a |"
    return f"| {label} | {name} | {f(c['delta'], 3, True)} | {ci(c, 3, True)} | {c['n_pairs']} |"


def render(res: dict, narrative: str = "") -> str:
    L: list[str] = []
    A = L.append
    A("# REPORT -- addendum 26 (exploratory): non-Qwen judges on views that fit their context\n")
    A("> AI-generated draft; the author must review it before use. Exploratory and post hoc; descriptive only (PLAN.md 26.1). "
      "Intervals are question-clustered BCa 95% (B = 10,000, seed 20260913) unless a table says otherwise. "
      "Do not copy this into external material without checking it for internal addresses and unpublished data.\n")
    if narrative:
        A(narrative.rstrip() + "\n")
    A("## 1. A->B and the six contrasts\n")
    for study, title in (("dev", "Development study (16 questions, development rendering)"),
                         ("holdout_subgraph", "Brick holdout, subgraph view (22 paired questions)")):
        A(f"### {title}\n")
        A("| source | contrast | mean delta | 95% BCa | pairs |\n|---|---|---|---|---|")
        for j, jr in res["judges"].items():
            sr = jr.get(study)
            if sr:
                for name, c in sr["contrasts"].items():
                    A(crow(jr["label"], name, c))
        for name, rf in res["references"].get(study, {}).items():
            for cname, c in rf["contrasts"].items():
                A(crow("ref: " + name, cname, c))
            for cname, c in (rf.get("contrasts_on_job_cells") or {}).items():
                A(crow(f"ref (judges' {rf['n_job_cells']} cells only): " + name, cname, c))
        A("")
        for j, jr in res["judges"].items():
            sr = jr.get(study)
            if not sr:
                continue
            per = sr["A_to_B_per_repeat"]
            A(f"A->B per single repeat, {jr['label']}: " + "; ".join(
                f"r{r} {f(c['delta'], 3, True)} {ci(c, 3, True)}" for r, c in per.items() if c))
            if study == "dev" and sr.get("A_to_B_paper_convention_halfup_mean_of_repeats_1_2"):
                c = sr["A_to_B_paper_convention_halfup_mean_of_repeats_1_2"]
                A(f"A->B, paper convention (half-up mean of repeats 1 and 2), {jr['label']}: {f(c['delta'], 3, True)} {ci(c, 3, True)}")
        A("")
    A("## 2. Per-variant means (J) and coverage (share J >= 2)\n")
    for study in ("dev", "holdout_subgraph"):
        A(f"### {study}\n")
        A("| source | " + " | ".join(VARIANTS) + " |\n|---|" + "---|" * 6)
        for j, jr in res["judges"].items():
            sr = jr.get(study)
            if sr:
                A(f"| {jr['label']} mean J | " + " | ".join(f(sr['variant_means'][v]['mean_J']['estimate'], 2) if sr['variant_means'][v] else "n/a" for v in VARIANTS) + " |")
                A(f"| {jr['label']} coverage | " + " | ".join(f(sr['variant_coverage'][v]['mean_J']['estimate'], 3) if sr['variant_coverage'][v] else "n/a" for v in VARIANTS) + " |")
        for name, rf in res["references"].get(study, {}).items():
            A(f"| ref {name} mean J | " + " | ".join(f(rf['variant_means'][v]['mean_J']['estimate'], 2) if rf['variant_means'][v] else "n/a" for v in VARIANTS) + " |")
            A(f"| ref {name} coverage | " + " | ".join(f(rf['variant_coverage_only'][v], 3) for v in VARIANTS) + " |")
        A("")
    A("## 3. Run-to-run (3 repeats, temperature 0: serving nondeterminism, not sampling variance)\n")
    A("| judge | study | cells | pairwise exact agr. | 95% | all 3 identical | cells with any disagreement | ICC(2,1) | 95% | ICC(2,3) |\n|---|---|---|---|---|---|---|---|---|---|")
    for j, jr in res["judges"].items():
        for study in STUDIES:
            rr = (jr.get(study) or {}).get("run_to_run")
            if rr and "pairwise_exact_agreement" in rr:
                A(f"| {jr['label']} | {study} | {rr['n_cells']} | {f(rr['pairwise_exact_agreement']['estimate'])} | {ci(rr['pairwise_exact_agreement'])} | "
                  f"{f(rr['all_three_identical']['estimate'])} | {rr['n_cells_with_any_disagreement']} | {f(rr['icc_2_1'])} | "
                  f"[{f(rr['icc_2_1_ci'][0])}, {f(rr['icc_2_1_ci'][1])}] | {f(rr['icc_2_k'])} |")
    A("\nExact agreement is BCa; ICC intervals are percentile question-clustered bootstrap.\n")
    A("## 4. Offsets and agreement against luna (subgraph) and the registered holdout judge / dev Qwen judge\n")
    A("| judge | study | reference | shared cells | offset (judge - ref) | 95% BCa | exact (mean of repeats) | within 1 | QWK |\n|---|---|---|---|---|---|---|---|---|")
    for j, jr in res["judges"].items():
        for study in STUDIES:
            for name, v in ((jr.get(study) or {}).get("vs_reference") or {}).items():
                m = v["mean_over_repeats"] or {}
                A(f"| {jr['label']} | {study} | {name} | {v['n_shared_cells']} | {f((v['offset_repeat_mean'] or {}).get('estimate'), 3, True)} | "
                  f"{ci(v['offset_repeat_mean'], 3, True)} | {f(m.get('exact'))} | {f(m.get('within1'))} | {f(m.get('qwk'))} |")
    for study, v in res["interjudge"].items():
        if "mean_exact" in v:
            A(f"\nInter-judge (gpt-oss vs GLM), {study}: exact {f(v['mean_exact'])}, QWK {f(v['mean_qwk'])} (mean over repeats).")
    A("\nReference rows on the holdout compare different inputs for the registered judge (full view) and the same input for luna (subgraph).\n")
    A("## 5. Contrast-direction agreement (sign of mean delta, six contrasts, shared cells)\n")
    A("| judge | study | reference | contrasts with same sign | per-question A->B same sign | both nonzero & same direction / both nonzero |\n|---|---|---|---|---|---|")
    for j, jr in res["judges"].items():
        for study in STUDIES:
            for name, v in ((jr.get(study) or {}).get("direction_agreement") or {}).items():
                q = v["per_question_A_to_B"]
                A(f"| {jr['label']} | {study} | {name} | {v['n_contrasts_same_sign']}/{v['n_contrasts']} | {q['same_sign']}/{q['n_pairs']} | {q['both_nonzero_same_direction']}/{q['both_nonzero']} |")
    A("")
    A("## 6. Unsupported-credit rate pi-hat (J >= 2 and S = 0) on the 182 subgraph cells\n")
    A("S labels: the independent rater (v3); AH labels are not read (see PLAN 26.6-6) unless the author supplied a path.\n")
    A("| label set | source | pi-hat (repeat mean; min-max) | per-repeat pi-hat [95% BCa] |\n|---|---|---|---|")
    for lname, rows in res["references"].get("pi_hat", {}).items():
        for name, blk in rows.items():
            if "1" in blk:
                A(f"| {lname} | ref {name} | {f(blk['1']['pi_hat'])} (events {blk['1']['events']}/{blk['1']['n_cells']}) | {f(blk['1']['pi_hat'])} [{f(blk['1']['ci_lo'])}, {f(blk['1']['ci_hi'])}] |")
    for j, jr in res["judges"].items():
        for lname, blk in ((jr.get("holdout_subgraph") or {}).get("pi_hat") or {}).items():
            if "summary" in blk:
                s = blk["summary"]
                per = "; ".join(f"r{r} {f(blk[r]['pi_hat'])} [{f(blk[r]['ci_lo'])}, {f(blk[r]['ci_hi'])}]" for r in ("1", "2", "3") if r in blk)
                A(f"| {lname} | {jr['label']} | {f(s['mean'])} ({f(s['min'])}-{f(s['max'])}) | {per} |")
    A("\n### Controls (subgraph analogue; share of cells with J >= 2)\n")
    A("| judge | ablated (15 planned) | preserved (12 planned) |\n|---|---|---|")
    for j, jr in res["judges"].items():
        c = jr.get("holdout_control")
        if c:
            A(f"| {jr['label']} | {f(c['ablated_control']['mean_share_J_ge_2'])} (n per repeat "
              f"{[p['n'] for p in c['ablated_control']['per_repeat']]}) | {f(c['preserved_control']['mean_share_J_ge_2'])} (n per repeat {[p['n'] for p in c['preserved_control']['per_repeat']]}) |")
    A("\n## 7. Score distributions, validity and cost\n")
    A("| judge | study | J=0 | J=1 | J=2 | J=3 | calls | valid | invalid | cells needing retry | prompt tokens (final attempt) | completion tokens | wall span (s) |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for j, jr in res["judges"].items():
        for study in ("holdout_subgraph", "holdout_control", "dev", "all"):
            c = (jr.get("cost") or {}).get(study)
            if not c:
                continue
            d = (jr.get(study) or {}).get("distribution") if study in STUDIES else None
            cnt = d["counts"] if d else {}
            A(f"| {jr['label']} | {study} | {cnt.get('0', '')} | {cnt.get('1', '')} | {cnt.get('2', '')} | {cnt.get('3', '')} | {c['calls']} | {c['valid']} | {c['invalid']} | "
              f"{c['cells_needing_retry']} | {c['prompt_tokens_final_attempt']:,} | {c['completion_tokens_final_attempt']:,} | {c['wall_span_s']} |")
    A("\nCells without a valid score are listed per judge in `results.json` (`invalid_or_missing`); nothing was imputed.\n")
    sal = res.get("sensitivity_salvage")
    if sal:
        A("## 8. Sensitivity added after the freeze (not in PLAN.md): scores salvaged from truncated JSON\n")
        A("A reply that is cut off at the token limit but starts with `{\"score\": N,` has its score read from that prefix; "
          "replies with no content (reasoning used the whole budget) stay invalid. The primary analysis above does not use these scores.\n")
        A("| judge | study | salvaged (cell, repeat) scores | A->B primary | A->B with salvage | pairwise exact agr. primary | with salvage |\n|---|---|---|---|---|---|---|")
        for j, sj in sal.items():
            for study in STUDIES:
                prim = res["judges"][j].get(study) or {}
                alt = sj.get(study) or {}
                pc = (prim.get("contrasts") or {}).get("A->B")
                ac = (alt.get("contrasts") or {}).get("A->B")
                pr = (prim.get("run_to_run") or {}).get("pairwise_exact_agreement")
                ar = (alt.get("run_to_run") or {}).get("pairwise_exact_agreement")
                A(f"| {res['judges'][j]['label']} | {study} | {(sj.get('n_salvaged_by_study') or {}).get(study, 0)} | "
                  f"{f(pc['delta'], 3, True) + ' ' + ci(pc, 3, True) if pc else 'n/a'} | {f(ac['delta'], 3, True) + ' ' + ci(ac, 3, True) if ac else 'n/a'} | "
                  f"{f(pr['estimate']) if pr else 'n/a'} | {f(ar['estimate']) if ar else 'n/a'} |")
        A("")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=Path, default=HERE / "jobs.jsonl")
    ap.add_argument("--raw-dir", type=Path, default=HERE / "raw")
    ap.add_argument("--out-dir", type=Path, default=HERE)
    ap.add_argument("--ah-labels", type=Path, default=None, help="author-supplied AH label CSV (cell_id, A); never opened otherwise")
    ap.add_argument("--narrative", type=Path, default=HERE / "narrative.md")
    ap.add_argument("--no-salvage", action="store_true", help="skip the post-freeze salvage sensitivity run")
    a = ap.parse_args(argv)
    labels = {"independent rater (v3)": IND_LABELS}
    if a.ah_labels:
        labels["AH (author-supplied path)"] = a.ah_labels
    res = analyse(a.jobs, a.raw_dir, labels)
    if not a.no_salvage:
        sal = analyse(a.jobs, a.raw_dir, labels, salvage=True)
        res["sensitivity_salvage"] = {
            j: {"n_salvaged_scores": jr.get("n_salvaged_scores"), "n_salvaged_by_study": jr.get("n_salvaged_by_study"),
                **{st: {k: (jr.get(st) or {}).get(k) for k in ("n_cells_scored", "distribution", "contrasts",
                                                               "A_to_B_per_repeat", "run_to_run", "variant_means")}
                   for st in STUDIES}}
            for j, jr in sal["judges"].items() if jr.get("n_records")}
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    narrative = a.narrative.read_text(encoding="utf-8") if a.narrative.exists() and a.out_dir == HERE else ""
    (a.out_dir / "REPORT.md").write_text(render(res, narrative), encoding="utf-8")
    print(f"wrote {a.out_dir/'results.json'} and {a.out_dir/'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
