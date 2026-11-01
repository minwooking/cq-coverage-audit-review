#!/usr/bin/env python3
"""Addendum 34: A->B judge-score contrast on the Study 2 expansion bank.  AI-generated; review and test before use.
Reads only study2_llm_labels/raw/judge_*_stage2.jsonl and manifests/eligibility.json.  No label, no model call.
Judge-score contrast on the expansion bank; not human-labelled."""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
import analyze_holdout as ah  # noqa: E402

S2 = HARNESS / "study2_llm_labels"
SEED, B = 20260913, 10000
Z_SUM = 1.959963984540054 + 0.8416212335729143
SIGMAS = {"prespecified_1.155": 1.155, "holdout_J_1.343": 1.343, "holdout_L1star_1.473": 1.473}
MARGIN = 0.50
BANNER = "judge-score contrast on the expansion bank; not human-labelled"
JUDGES = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b"}


def mde(sigma: float, n: int) -> float:
    return Z_SUM * sigma / np.sqrt(n)


def cell_scores(records: list[dict], how: str = "mean") -> dict[str, float]:
    by: dict[str, list[int]] = {}
    for r in records:
        if r.get("valid") and r.get("J") is not None:
            by.setdefault(r["cell_id"], []).append(int(r["J"]))
    agg = (lambda v: float(np.mean(v))) if how == "mean" else (lambda v: float(statistics.median_low(sorted(v))))
    return {c: agg(v) for c, v in by.items()}


def contrast(scores: dict[str, float], eligible_both: set[str]) -> dict:
    ids = sorted(c for c in eligible_both if f"primary:A:{c}" in scores and f"primary:B:{c}" in scores)
    a = np.array([scores[f"primary:A:{c}"] for c in ids])
    b = np.array([scores[f"primary:B:{c}"] for c in ids])
    d = b - a
    n = len(ids)
    out = {"n_clusters": n, "mean_J_A": float(a.mean()), "mean_J_B": float(b.mean()), "delta": float(d.mean()),
           "sd_d": float(d.std(ddof=1)), "n_missing": len(eligible_both) - n}
    boot = ah.cluster_bootstrap_delta({c: [float(x)] for c, x in zip(ids, d)}, B, SEED)
    out["ci95"] = [boot["ci_lo"], boot["ci_hi"]]
    out["ci90"] = [boot["ci90_lo"], boot["ci90_hi"]]
    nz = d[d != 0]
    npos, nneg = int((nz > 0).sum()), int((nz < 0).sum())
    out["sign_test"] = {"n_pos": npos, "n_neg": nneg, "n_zero": int((d == 0).sum()),
                        "p": float(stats.binomtest(npos, npos + nneg, 0.5).pvalue) if nz.size else None}
    wil = ah.wilcoxon_zeros_dropped([float(x) for x in d])
    out["wilcoxon"] = wil
    dec = ah.tost_decision(out["ci95"][0], out["ci95"][1], MARGIN, eq_lo=out["ci90"][0], eq_hi=out["ci90"][1])
    out["decision"] = dec
    out["decision_with_rank_rule"] = ah._decision_with_rank_rule(dec, ah._rank_agrees_in_sign(out["delta"], wil))
    out["prospective_mde"] = {k: float(mde(s, n)) for k, s in SIGMAS.items()}
    out["realized_sigma"] = out["sd_d"]
    out["realized_mde"] = float(mde(out["sd_d"], n))
    return out


def main() -> int:
    el = json.loads((S2 / "manifests" / "eligibility.json").read_text(encoding="utf-8"))
    elig_ids = set(el["ineligible_clusters"])
    cells = json.loads((S2 / "manifests" / "eligibility.json").read_text(encoding="utf-8"))
    # eligible-in-both set from the committed jobs (eligible cells of Stage 2)
    jobs = [json.loads(l) for l in (S2 / "jobs_stage2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    have = {}
    for j in jobs:
        have.setdefault(j["cq_id"], set()).add(j["variant"])
    both = {c for c, v in have.items() if {"A", "B"} <= v}
    assert len(both) == el["n_clusters_eligible_in_A_and_B"], (len(both), el["n_clusters_eligible_in_A_and_B"])
    res = {"banner": BANNER, "addendum": 34, "seed": SEED, "B": B, "bank_sha256": el["bank_sha256"],
           "n_eligible_clusters_total": el["n_eligible_clusters"], "n_clusters_eligible_in_A_and_B": len(both),
           "bridge": {"computable": False, "n_shared_questions": 0,
                      "note": "expansion and holdout banks share 0 question texts, 0 groundings, disjoint ids (PLAN 34.6)"},
           "judges": {}}
    for j in JUDGES:
        recs = [json.loads(l) for l in (S2 / "raw" / f"judge_{j}_stage2.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        res["judges"][j] = {"model": JUDGES[j], "n_records": len(recs), "n_invalid": sum(not r.get("valid") for r in recs),
                            "mean_of_repeats": contrast(cell_scores(recs, "mean"), both),
                            "median_of_repeats_sensitivity": contrast(cell_scores(recs, "median"), both)}
    (HERE / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (HERE / "REPORT_auto.md").write_text(report(res), encoding="utf-8")
    (HERE / "tables.tex").write_text(tables(res), encoding="utf-8")
    return 0


def _f(x, k=3):
    return "n/a" if x is None else f"{x:.{k}f}"


def report(res: dict) -> str:
    L = [f"# Addendum 34 results -- {BANNER}", "", "Post hoc. Views: question-only subgraphs (Study 2 Stage 2 judge views). Registered holdout judge has no route; named judges only.",
         f"Eligible clusters total {res['n_eligible_clusters_total']}; eligible in both A and B (the paired set) {res['n_clusters_eligible_in_A_and_B']}.",
         f"Bridge subset: not computable ({res['bridge']['note']}).", ""]
    for j, r in res["judges"].items():
        for key, lab in (("mean_of_repeats", "primary (mean of 3 repeats)"), ("median_of_repeats_sensitivity", "sensitivity (median of repeats)")):
            c = r[key]
            L += [f"## {r['model']} -- {lab}", f"- n clusters {c['n_clusters']} (missing {c['n_missing']}); mean J A {c['mean_J_A']:.3f}, B {c['mean_J_B']:.3f}; delta {c['delta']:+.3f}, 95% BCa [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}], 90% BCa [{c['ci90'][0]:+.3f}, {c['ci90'][1]:+.3f}]",
                  f"- sign test: {c['sign_test']['n_pos']} up / {c['sign_test']['n_neg']} down / {c['sign_test']['n_zero']} tied, p {_f(c['sign_test']['p'],4)}; Wilcoxon p {_f(c['wilcoxon']['p'],4)}",
                  f"- MDE prospective: " + ", ".join(f"{k} {v:.3f}" for k, v in c['prospective_mde'].items()) + f"; realized sigma {c['realized_sigma']:.3f} -> MDE {c['realized_mde']:.3f}",
                  f"- decision: **{c['decision']}** (with manuscript rank rule: {c['decision_with_rank_rule']}), margin +-0.50", ""]
    return "\n".join(L)


def tables(res: dict) -> str:
    rows_a, rows_s = [], []
    for j, r in res["judges"].items():
        c = r["mean_of_repeats"]
        rows_a.append(f"{r['model']} & {c['n_clusters']} & {c['mean_J_A']:.2f} & {c['mean_J_B']:.2f} & ${c['delta']:+.3f}$ [${c['ci95'][0]:+.2f}$, ${c['ci95'][1]:+.2f}$] & {c['prospective_mde']['holdout_J_1.343']:.2f} & {c['decision']} \\\\")
        s = c["sign_test"]
        rows_s.append(f"{r['model']} & {c['n_clusters']} & {c['mean_J_A']:.3f} & {c['mean_J_B']:.3f} & ${c['delta']:+.3f}$ & [${c['ci95'][0]:+.3f}$, ${c['ci95'][1]:+.3f}$] & {c['prospective_mde']['prespecified_1.155']:.3f} / {c['prospective_mde']['holdout_J_1.343']:.3f} / {c['realized_mde']:.3f} & {_f(s['p'],3)} & {_f(c['wilcoxon']['p'],3)} & {c['decision']} \\\\")
    rows_s.append(f"\\multicolumn{{10}}{{l}}{{Bridge to the 36-question holdout bank: not computable (0 shared questions).}} \\\\")
    return ("% Addendum 34: " + BANNER + "\n% appendix table rows: judge & n & J(A) & J(B) & delta [95% BCa] & MDE(sigma 1.343) & decision\n"
            + "\n".join(rows_a) + "\n\n% supplement table rows: judge & n & J(A) & J(B) & delta & 95% BCa & MDE (1.155 / 1.343 / realized) & sign p & Wilcoxon p & decision\n" + "\n".join(rows_s) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
