"""Stage 2 analysis of addendum 32 (PLAN.md 32.9-32.10).  AI-generated; review and test before use.  LLM-labeled; not
human-validated beyond Stage 1.  Uses the registered analyzer's own functions (analyze_holdout.analyse and helpers), seed
20260913, B = 10,000, BCa, question clusters.  No human label is read here.

  analyze.py stage2   -> results_stage2.json   (only if results_stage1.json says PASS; otherwise writes the descriptive judge-only file)
  analyze.py merge    -> results.json + REPORT_auto.md
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
spec = importlib.util.spec_from_file_location("s2_analyze_core", HERE / "analyze.py")
AN = importlib.util.module_from_spec(spec)
sys.modules["s2_analyze_core"] = AN
spec.loader.exec_module(AN)
import analyze_holdout as ah  # noqa: E402
import s2_stage2 as S2  # noqa: E402

RC, SEED, B = AN.RC, AN.SEED, AN.B
JUDGES = ["glm", "gptoss"]
RAW = HERE / "raw"
Z_MDE = 2.8016


def collapse(s):
    return re.sub(r"\s+", " ", s or "").strip()


def verbatim_in(evidence: list[str], view: str) -> bool | None:
    """Whitespace-normalised containment of the judge's evidence in the view it saw; pieces split at '...'/ellipsis (>= 20 chars)."""
    if not evidence:
        return None
    nv = collapse(view)
    for ev in evidence:
        ne = collapse(ev)
        if ne and ne in nv:
            continue
        pieces = [collapse(p) for p in re.split(r"\.\.\.|…", ev)]
        pieces = [p for p in pieces if len(p) >= 20]
        if not pieces or not all(p in nv for p in pieces):
            return False
    return True


def other(j: str) -> str:
    return "gptoss" if j == "glm" else "glm"


def two_way(J, S) -> dict:
    over = int(((J >= 2) & (S == 0)).sum())
    under = int(((J <= 1) & (S == 1)).sum())
    return {"over_credit_J_ge2_S0": over, "under_credit_J_le1_S1": under, "both_credit": int(((J >= 2) & (S == 1)).sum()),
            "both_none": int(((J <= 1) & (S == 0)).sum()), "n": int(len(J)), "total_errors": over + under}


def g2_split_half(cl, R) -> dict:
    a, b = AN.split_half_rating(R)
    ok = ~np.isnan(a) & ~np.isnan(b)
    cols = np.stack([RC.conf_flat([x], [y], 4) for x, y in zip(a[ok].astype(int), b[ok].astype(int))])
    M = AN.csum(cl[ok], cols)
    r = AN.bca(M, lambda s: RC.qwk_from_flat(s, 4))
    return {"intra_rater_qwk": r["est"], "ci_lo": r["lo"], "ci_hi": r["hi"], "n": int(ok.sum()), "kind": "split-half test-retest of the LLM rating (seeds 1-3 vs 4-5)"}


def g7_gate(recs: list[dict]) -> dict:
    calls = [r for r in recs if r.get("status") in ("ok", "invalid")]
    n = len(calls)
    with_ts = sum(1 for r in calls if r.get("started_at_utc") and r.get("latency_s") is not None)
    lat = np.array([r["latency_s"] for r in calls if r.get("latency_s") is not None], float)
    share = float((lat < AN.LAT_FLOOR_S).mean()) if len(lat) else None
    ok = bool(n and with_ts == n and share is not None and share < 0.03)
    return {"status": "pass" if ok else "fail", "value": {"calls": n, "calls_with_timestamp_and_latency": with_ts,
            f"share_latency_below_{AN.LAT_FLOOR_S}s": AN.rnd(share, 4)}, "threshold": {"all_logged": True, "share_below_floor_lt": 0.03},
            "note": "latency clause replaces the dwell-time clause (PLAN 32.9); blindness holds by construction (a prompt holds no judge score or rationale); "
                    "append-only raw files are identified by sha256 in results"}


def load_judges() -> dict[str, dict]:
    recs = {}
    for j in JUDGES:
        p = RAW / f"judge_{j}_stage2.jsonl"
        recs[j] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
    return S2.judge_median(recs)


def judge_views() -> dict[str, str]:
    out = {}
    for l in S2.JOBS.read_text(encoding="utf-8").splitlines():
        if l.strip():
            j = json.loads(l)
            u = j["user"]
            out[j["cell_id"]] = u[len("ARTIFACT:\n"):u.rindex("\n\nQUESTION:")]
    return out


def audit_one(rows, labels, jm, jviews, labeler: str, judge: str, label_recs: list[dict]) -> dict:
    cells, prim = [], [r for r in rows if r["cell_kind"] == "primary"]
    n_undef = n_nojudge = 0
    for r in prim:
        L = labels["prim"].get(r["cell_id"])
        jj = jm.get(r["cell_id"], {}).get(judge)
        if L is None:
            n_undef += 1
            continue
        if jj is None:
            n_nojudge += 1
            continue
        c = {"cell_id": r["cell_id"], "cq_id": r["cq_id"], "cluster_id": r["cq_id"], "category": r["cat"], "variant": r["variant"],
             "cell_kind": "primary", "J": int(jj["J"]), "A": int(L[0]), "rater_L1": int(L[1])}
        o = jm.get(r["cell_id"], {}).get(other(judge))
        if o is not None:
            c["non_qwen_J"] = int(o["J"])
        cells.append(c)
    ctrl = []
    for r in rows:
        if r["cell_kind"] != "primary":
            L = labels["ctrl"].get(r["cell_id"])
            ctrl.append({"cell_id": r["cell_id"], "cq_id": r["cq_id"], "cluster_id": r["cq_id"], "category": r["cat"], "variant": r["variant"],
                         "cell_kind": "ablated_control", "J": 0, "A": 1 if L is None else int(L[0])})      # undefined counts as a failure
    out = {"labeler": labeler, "judge": judge, "n_cells": len(cells), "cells_label_undefined": n_undef, "cells_judge_invalid": n_nojudge,
           "n_clusters": len({c["cq_id"] for c in cells})}
    if len(cells) < 4:
        out["note"] = "too few cells"
        return out
    cl = np.array([c["cq_id"] for c in cells])
    Jv = np.array([c["J"] for c in cells], float)
    Sv = np.array([c["A"] for c in cells], float)
    Rv = np.array([c["rater_L1"] for c in cells], float)
    res = ah.analyse(cells + ctrl, SEED, g1_alpha=0.025, label_source="LLM labels (Study 2)", simulated=False, controls_valid=True,
                     g2=labels["g2"], g4=None, g8=None, label_audit=None)
    res["gates"]["G7_audit_trail"] = g7_gate(label_recs)
    out["pi_hat"] = res["pi_hat"]
    out["two_way_counts"] = two_way(Jv, Sv)
    out["coverage_pct_L1star"] = res["coverage_pct"]
    out["contrasts"] = {k: {kk: v for kk, v in c.items() if kk in ("delta", "ci_lo", "ci_hi", "n_clusters", "n_questions", "decision")} for k, c in res["contrasts"].items()}
    paired = ah._paired_ab_deltas(cells)
    if paired:
        d = np.array(list(paired[0].values()))
        sd = float(d.std(ddof=1)) if len(d) > 1 else None
        out["A_to_B_mde"] = {"n_pairs": int(len(d)), "sd_paired_diff": AN.rnd(sd), "mde_80pct_power": AN.rnd(Z_MDE * sd / np.sqrt(len(d))) if sd else None,
                             "observed_delta": AN.rnd(float(d.mean())), "formula": "2.8016 * SD / sqrt(n_pairs) (PREREG section 4)"}
    out["gates"] = {k: {kk: v for kk, v in g.items() if kk not in ("reasons", "counts", "confusion", "registered_text", "g1_achievable_at_registered_n")} for k, g in res["gates"].items()}
    out["gates_summary"] = res["gates_summary"]
    out["mae_J_vs_R_llm_no_floor"] = AN.rnd(float(np.abs(Jv - Rv).mean()))
    out["share_label1"] = AN.rnd(float(Sv.mean()))
    # verbatim-span check of the judge's evidence
    ver, hit, flags = 0, 0, []
    for c in cells:
        if c["J"] >= 2:
            ev = jm[c["cell_id"]][judge]["evidence_at_median"]
            v = verbatim_in(ev, jviews[c["cell_id"]])
            hit += 1
            ver += 1 if v else 0
            flags.append(0 if v else 1)
        else:
            flags.append(0)
    nv = np.array(flags, float)
    pi_v = ((Jv >= 2) & ((Sv == 0) | (nv == 1))).astype(float)
    out["verbatim_span_check"] = {"cells_J_ge2": hit, "evidence_verbatim_in_judge_view": ver,
                                  "share_verbatim": AN.rnd(ver / hit) if hit else None,
                                  "pi_hat_treating_nonverbatim_J_ge2_as_unsupported": AN.stat(cl, np.stack([pi_v, np.ones(len(cl))], 1), lambda s: s[:, 0] / s[:, 1])}
    return out


def labels_for(model: str, rows: list[dict]) -> dict | None:
    recs = AN.read_jsonl(RAW / f"{model}_stage2.jsonl")
    if not recs:
        return None
    ids = [r["cell_id"] for r in rows]
    m = AN.slot_matrices(recs, ids)
    lab = AN.cell_labels(m["S"], m["R"])
    prim, ctrl = {}, {}
    for i, r in enumerate(rows):
        v = None if np.isnan(lab["L"][i]) else (int(lab["L"][i]), int(lab["R"][i]))
        (prim if r["cell_kind"] == "primary" else ctrl)[r["cell_id"]] = v
    prim = {k: v for k, v in prim.items() if v is not None}
    ctrl = {k: v for k, v in ctrl.items() if v is not None}
    pr_idx = [i for i, r in enumerate(rows) if r["cell_kind"] == "primary"]
    cl = np.array([rows[i]["cq_id"] for i in pr_idx])
    okm = ~np.isnan(lab["L"][pr_idx])
    g2 = g2_split_half(cl[okm], m["R"][pr_idx][okm]) if okm.sum() > 3 else None
    ablated_ok = [r["cell_id"] for r in rows if r["cell_kind"] != "primary"]
    return {"prim": prim, "ctrl": ctrl, "g2": g2, "records": recs, "alpha": AN.stat(cl, AN.alpha_cols(m["S"][pr_idx]), AN.alpha_from),
            "label_cov": {"cells": len(pr_idx), "with_label": int(okm.sum()), "R25_consistent": int(lab["consistent"][pr_idx].sum()),
                          "context_skip": len(m["context_skip"])}, "n_ablated": len(ablated_ok)}


def descriptive_judge_only(rows, jm) -> dict:
    out = {"banner": AN.BANNER, "note": "judge scores only; no label-based statistic (Stage 1 did not pass or labels absent)"}
    for j in JUDGES:
        cells = [{"cq_id": r["cq_id"], "variant": r["variant"], "J": jm[r["cell_id"]][j]["J"]} for r in rows
                 if r["cell_kind"] == "primary" and j in jm.get(r["cell_id"], {})]
        by = {}
        for v in "ABCDEF":
            xs = [c["J"] for c in cells if c["variant"] == v]
            by[v] = {"n": len(xs), "mean_J": AN.rnd(float(np.mean(xs))) if xs else None, "share_J_ge2": AN.rnd(float(np.mean([x >= 2 for x in xs]))) if xs else None}
        out[j] = {"n_cells": len(cells), "by_variant": by}
    return out


def run_stage2() -> dict:
    s1 = json.loads((HERE / "results_stage1.json").read_text(encoding="utf-8"))
    rows = json.loads((HERE / "manifests" / "stage2.json").read_text(encoding="utf-8"))["rows"]
    jm, jv = load_judges(), judge_views()
    el = json.loads((HERE / "manifests" / "eligibility.json").read_text(encoding="utf-8"))
    res = {"banner": AN.BANNER, "stage": 2, "stage1_gate": s1["gate"],
           "bank": {k: v for k, v in el.items() if k != "cells"}, "judges": ["GLM-4.7-Flash (glm)", "gpt-oss-20b (gptoss)"],
           "judge_note": "the registered holdout judge has no route here; named non-Qwen judges on question-only subgraph views (deviation stated in PLAN 32.8)"}
    if not s1["gate"]["pass"]:
        res["audit_run"] = False
        res["reason"] = "Stage 1 gate failed: Stage 2 is not run as an LLM-labeled audit"
        res["descriptive_judge_only"] = descriptive_judge_only(rows, jm)
        return res
    res["audit_run"] = True
    res["combinations"] = []
    head = s1["gate"]["headline_labeler"]
    for m in s1["gate"]["passing_models"]:
        lb = labels_for(m, rows)
        if lb is None:
            res["combinations"].append({"labeler": m, "note": "no Stage 2 label records"})
            continue
        res.setdefault("labeler_summary", {})[m] = {"label_cov": lb["label_cov"], "alpha_25_slots": lb["alpha"], "latency": AN.latency_stats(lb["records"]),
                                                    "raw_sha256": hashlib.sha256((RAW / f"{m}_stage2.jsonl").read_bytes()).hexdigest()}
        for j in JUDGES:
            blk = audit_one(rows, lb, jm, jv, m, j, lb["records"])
            blk["headline"] = bool(m == head and j == other(head))
            res["combinations"].append(blk)
    res["view_coverage"] = {"n_cells": sum(1 for r in rows if r["cell_kind"] == "primary"),
                            "view_holds_terms": sum(bool(r["view_holds_terms"]) for r in rows if r["cell_kind"] == "primary"),
                            "full_holds_terms": sum(bool(r["full_holds_terms"]) for r in rows if r["cell_kind"] == "primary")}
    return res


def main(mode: str) -> int:
    if mode == "stage2":
        r = run_stage2()
        (HERE / "results_stage2.json").write_text(json.dumps(r, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        print(json.dumps({"audit_run": r["audit_run"], "n_combinations": len(r.get("combinations", []))}))
        return 0
    if mode == "merge":
        import s2_report
        return s2_report.main()
    raise SystemExit("usage: analyze.py stage1|stage2|merge")
