#!/usr/bin/env python3
"""Addendum 27 (amendments 1-2) analysis: natural-corpus vs template-corpus A->B under three judges.  Offline.

AI-generated; review before reuse.  Judges: gptoss, glm (primary, non-Qwen) and qwenflash (same-family contrast).
Reads raw/raw_<judge>_<corpus>.jsonl (score_judges.py record format), jobs_*.jsonl (view text for the machine
evidence check), grounding_check.json, art_eligibility.json, artifacts.json, build_usage.jsonl.  Writes results.json.
Estimators/bootstrap are analyze_holdout's own (cluster_bootstrap_stat, _mean_d, wilcoxon_zeros_dropped,
_qwk_from_values); B = 10,000, seed 20260913, question clusters.  Cell score = mean of the judge's valid repeats.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parents[1]
sys.path.insert(0, str(ACCESS / "harness"))

import analyze_holdout as ah  # noqa: E402
import run_holdout as rh  # noqa: E402

B, SEED = 10_000, rh.REGISTERED_SEED
JUDGES = [("gptoss", "primary non-Qwen"), ("glm", "primary non-Qwen"), ("qwenflash", "same-family judge (contrast)")]
RAW = HERE / "raw"


def norm(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def view_of(job: dict) -> str:
    u = job["user"]
    return u[len("ARTIFACT:\n"):u.rindex("\n\nQUESTION: ")]


def verbatim(evidence, view_n: str) -> bool:
    if isinstance(evidence, str):
        e = norm(evidence)
        return bool(e) and e in view_n
    if isinstance(evidence, list):
        parts = [norm(x) for x in evidence if isinstance(x, str) and norm(x)]
        return bool(parts) and all(p in view_n for p in parts)
    return False


def load(judge: str, corpus: str):
    """-> records by (variant, cq): list of valid per-repeat records; plus counts."""
    p = RAW / f"raw_{judge}_{corpus}.jsonl"
    by: dict[tuple[str, str], dict[int, dict]] = defaultdict(dict)
    counts = Counter()
    if not p.exists():
        return None, counts
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        counts["records"] += 1
        counts[f"status_{r.get('status')}"] += 1
        if r.get("reused_from_addendum26"):
            counts["reused"] += 1
        if r.get("valid") and r.get("repeat", 0) >= 1 and r["J"] in (0, 1, 2, 3):
            by[(r["variant"], r["cq_id"])].setdefault(r["repeat"], r)
    return by, counts


def cell_scores(by, jobs_by_cell, key="J"):
    """by -> {variant: {cq: score}} using mean of valid repeats (machine-adjusted if key == 'Jstar')."""
    out: dict[str, dict[str, float]] = {"A": {}, "B": {}}
    for (v, cq), reps in by.items():
        out[v][cq] = float(np.mean([r[key] for r in reps.values()]))
    return out


def cov_stat(records):
    return float(np.mean([r["J"] for r in records])) / 3 * 100.0


def share2_stat(records):
    return float(np.mean([1.0 if r["J"] >= 2 else 0.0 for r in records])) * 100.0


def boot(records, fn):
    if len({r["cluster_id"] for r in records}) < 2:
        return None
    r = ah.cluster_bootstrap_stat(records, fn, None, "cluster_id", B, SEED)
    return {"estimate": r["estimate"], "ci95": [r["ci_lo"], r["ci_hi"]], "ci90": [r["ci90_lo"], r["ci90_hi"]], "n_clusters": r["n_clusters"]}


def contrast(name, qids, sc, bank):
    rows = [(q, sc["A"][q], sc["B"][q]) for q in qids if q in sc["A"] and q in sc["B"]]
    res = {"set": name, "n_questions_in_set": len(qids), "n_paired": len(rows)}
    if len(rows) < 2:
        return res
    for v, idx in (("A", 1), ("B", 2)):
        recs = [{"cluster_id": bank[r[0]]["cluster_id"], "J": r[idx]} for r in rows]
        res[f"coverage_{v}"] = boot(recs, cov_stat)
        res[f"share_ge2_{v}"] = boot(recs, share2_stat)
        res[f"rounded_dist_{v}"] = {str(k): sum(1 for r in rows if int(round(r[idx] + 1e-9)) == k) for k in range(4)}
    d = [{"cluster_id": bank[q]["cluster_id"], "d": b - a} for q, a, b in rows]
    bt = ah.cluster_bootstrap_stat(d, ah._mean_d, None, "cluster_id", B, SEED)
    flat = [x["d"] for x in d]
    wil = ah.wilcoxon_zeros_dropped(flat)
    ja, jb = [int(round(r[1] + 1e-9)) for r in rows], [int(round(r[2] + 1e-9)) for r in rows]
    res["A_to_B"] = {"mean_diff_score": bt["estimate"], "ci95_score": [bt["ci_lo"], bt["ci_hi"]], "ci90_score": [bt["ci90_lo"], bt["ci90_hi"]],
                     "mean_diff_coverage_points": bt["estimate"] * 100 / 3,
                     "ci95_coverage_points": [bt["ci_lo"] * 100 / 3, bt["ci_hi"] * 100 / 3],
                     "B_gt_A": sum(1 for x in flat if x > 1e-9), "B_eq_A": sum(1 for x in flat if abs(x) <= 1e-9), "B_lt_A": sum(1 for x in flat if x < -1e-9),
                     "wilcoxon_zeros_dropped": {k: wil.get(k) for k in ("p", "n_nonzero", "sign")},
                     "exact_agreement_rounded": sum(1 for x, y in zip(ja, jb) if x == y) / len(rows),
                     "qwk_A_vs_B_rounded": ah._qwk_from_values(ja, jb) if len(set(ja + jb)) > 1 else None}
    res["per_question"] = [{"cq_id": q, "A": a, "B": b} for q, a, b in rows]
    return res


def run_to_run(by):
    agree, same3, n3, n2 = [], 0, 0, 0
    for reps in by.values():
        js = [r["J"] for r in reps.values()]
        if len(js) >= 2:
            n2 += 1
            agree.extend(1.0 if x == y else 0.0 for x, y in combinations(js, 2))
        if len(js) == 3:
            n3 += 1
            same3 += len(set(js)) == 1
    return {"cells_with_>=2_valid_repeats": n2, "mean_pairwise_exact_agreement": float(np.mean(agree)) if agree else None,
            "cells_with_3_valid_repeats": n3, "share_identical_across_3": (same3 / n3) if n3 else None}


def main() -> int:
    bank = {r["cq_id"]: r for r in rh.csv.DictReader((ACCESS / "bank" / "cq_bank_brick_v1.csv").open(encoding="utf-8", newline=""))}
    grounding = json.loads((HERE / "grounding_check.json").read_text(encoding="utf-8"))
    sets = {"S_full": grounding["S_full"], "S_elig": grounding["S_elig"], "S_elig_L1": grounding["S_elig_L1"]}
    ap_ = HERE / "art_eligibility.json"
    if ap_.exists():
        sets["S_art"] = json.loads(ap_.read_text(encoding="utf-8"))["S_art"]
    jobs = {c: {j["cell_id"]: j for j in map(json.loads, (HERE / f"jobs_{c}.jsonl").read_text(encoding="utf-8").splitlines() if (HERE / f"jobs_{c}.jsonl").exists() else [])}
            for c in ("natural", "template_AB")}
    jobs_nat = jobs["natural"]
    jobs_tpl = jobs["template_AB"]
    results: dict = {"seed": SEED, "B": B, "judges": {j: lab for j, lab in JUDGES},
                     "plan_note": "PLAN.md addendum 27 + amendments 27.A1/27.A2; descriptive, no decisions",
                     "grounding": {k: grounding[k] for k in ("automated_counts", "analyst_counts", "answerable_share", "stop_rule")},
                     "sets": {k: len(v) for k, v in sets.items()}, "per_judge": {}, "side_by_side": {}}
    scores: dict = {}
    for judge, label in JUDGES:
        jres: dict = {"label": label}
        scores[judge] = {}
        for corpus, jb in (("natural", jobs_nat), ("template", jobs_tpl)):
            by, counts = load(judge, corpus)
            if by is None:
                jres[corpus] = {"status": "not run"}
                continue
            # machine evidence check per record
            view_n = {cid: norm(view_of(j)) for cid, j in jb.items()}
            ev = {"A": Counter(), "B": Counter()}
            for (v, cq), reps in by.items():
                cid = (f"natural:{v}:{cq}" if corpus == "natural" else f"primary:{v}:{cq}")
                for r in reps.values():
                    ok = verbatim(r.get("evidence"), view_n[cid])
                    r["verbatim"] = ok
                    r["Jstar"] = r["J"] if ok else min(r["J"], 1)
                    if r["J"] >= 2:
                        ev[v]["J_ge2_records"] += 1
                        ev[v]["verbatim"] += ok
            sc = cell_scores(by, jb)
            scs = cell_scores(by, jb, "Jstar")
            scores[judge][corpus] = sc
            cres = {"status": "run", "record_counts": dict(counts), "valid_cells": {v: len(sc[v]) for v in sc},
                    "usage": {"prompt_tokens": sum(r.get("prompt_tokens") or 0 for reps in by.values() for r in reps.values()),
                              "completion_tokens": sum(r.get("completion_tokens") or 0 for reps in by.values() for r in reps.values())},
                    "run_to_run": run_to_run(by),
                    "machine_evidence": {v: {"J_ge2_records": ev[v]["J_ge2_records"], "verbatim": ev[v]["verbatim"],
                                             "verbatim_share": (ev[v]["verbatim"] / ev[v]["J_ge2_records"]) if ev[v]["J_ge2_records"] else None} for v in ev},
                    "sets": {}, "machine_adjusted": {}}
            if corpus == "natural":
                for sname, qids in sets.items():
                    cres["sets"][sname] = contrast(sname, qids, sc, bank)
                    cres["machine_adjusted"][sname] = contrast(sname, qids, scs, bank)
            else:
                allq = sorted(set(sc["A"]) & set(sc["B"]))
                cres["sets"]["tpl_paired"] = contrast("template paired questions", allq, sc, bank)
                cres["machine_adjusted"]["tpl_paired"] = contrast("template paired questions", allq, scs, bank)
            jres[corpus] = cres
        # natural vs template under this judge
        if all(isinstance(jres.get(c), dict) and jres[c].get("status") == "run" for c in ("natural", "template")):
            nat, tpl = scores[judge]["natural"], scores[judge]["template"]
            both = sorted(q for q in tpl["A"] if q in tpl["B"] and q in nat["A"] and q in nat["B"])
            res = {"questions_in_both": len(both)}
            if len(both) >= 2:
                nd = [{"cluster_id": bank[q]["cluster_id"], "d": nat["B"][q] - nat["A"][q]} for q in both]
                td = [{"cluster_id": bank[q]["cluster_id"], "d": tpl["B"][q] - tpl["A"][q]} for q in both]
                dd = [{"cluster_id": a["cluster_id"], "d": a["d"] - b["d"]} for a, b in zip(nd, td)]
                bn, bt_, bd = (ah.cluster_bootstrap_stat(x, ah._mean_d, None, "cluster_id", B, SEED) for x in (nd, td, dd))
                res.update({"natural_A_to_B": {"mean": bn["estimate"], "ci95": [bn["ci_lo"], bn["ci_hi"]]},
                            "template_A_to_B": {"mean": bt_["estimate"], "ci95": [bt_["ci_lo"], bt_["ci_hi"]]},
                            "natural_minus_template": {"mean": bd["estimate"], "ci95": [bd["ci_lo"], bd["ci_hi"]]}})
            jres["natural_vs_template"] = res
        results["per_judge"][judge] = jres
    # cross-judge agreement on natural cells (per repeat, averaged)
    cross = {}
    raw_nat = {j: load(j, "natural")[0] for j, _ in JUDGES}
    for (j1, _), (j2, _) in combinations(JUDGES, 2):
        if raw_nat[j1] is None or raw_nat[j2] is None:
            continue
        qw, ag = [], []
        for rep in (1, 2, 3):
            pairs = [(raw_nat[j1][k][rep]["J"], raw_nat[j2][k][rep]["J"]) for k in raw_nat[j1] if k in raw_nat[j2] and rep in raw_nat[j1][k] and rep in raw_nat[j2][k]]
            if len(pairs) >= 5 and len({x for p in pairs for x in p}) > 1:
                qw.append(ah._qwk_from_values([p[0] for p in pairs], [p[1] for p in pairs]))
                ag.append(sum(1 for p in pairs if p[0] == p[1]) / len(pairs))
        cross[f"{j1}_vs_{j2}"] = {"qwk_per_repeat_mean": float(np.mean(qw)) if qw else None, "exact_agreement_per_repeat_mean": float(np.mean(ag)) if ag else None, "repeats_used": len(qw)}
    results["cross_judge_natural"] = cross
    # side by side
    for judge, label in JUDGES:
        jr = results["per_judge"][judge]
        row = {"label": label}
        for corpus, key, sname in (("natural", "natural_S_full", "S_full"), ("natural", "natural_S_elig", "S_elig"), ("template", "template_paired", "tpl_paired")):
            c = jr.get(corpus, {})
            if c.get("status") == "run" and "A_to_B" in c["sets"].get(sname, {}):
                s = c["sets"][sname]
                row[key] = {"n_paired": s["n_paired"], "coverage_A": s["coverage_A"]["estimate"], "coverage_B": s["coverage_B"]["estimate"],
                            "A_to_B_score": s["A_to_B"]["mean_diff_score"], "ci95": s["A_to_B"]["ci95_score"], "B_gt_A/eq/lt": [s["A_to_B"]["B_gt_A"], s["A_to_B"]["B_eq_A"], s["A_to_B"]["B_lt_A"]]}
        row["natural_minus_template"] = jr.get("natural_vs_template")
        results["side_by_side"][judge] = row
    signs = {j: (1 if (r.get("natural_S_full") or {}).get("A_to_B_score", 0) > 0 else -1 if (r.get("natural_S_full") or {}).get("A_to_B_score", 0) < 0 else 0)
             for j, r in results["side_by_side"].items() if r.get("natural_S_full")}
    results["natural_A_to_B_sign_by_judge_S_full"] = signs
    # artifact descriptives and extractor usage, anchor retention
    for name in ("artifacts.json",):
        if (HERE / name).exists():
            results["artifacts"] = json.loads((HERE / name).read_text(encoding="utf-8"))
    usage_p = HERE / "build_usage.jsonl"
    if usage_p.exists():
        agg: dict = {}
        for r in map(json.loads, usage_p.read_text(encoding="utf-8").splitlines()):
            a = agg.setdefault(r["command"], {"calls": 0, "failures": 0, "prompt_tokens": 0, "completion_tokens": 0, "elapsed_s": 0.0})
            for k in ("calls", "failures", "prompt_tokens", "completion_tokens"):
                a[k] += r[k]
            a["elapsed_s"] += r["elapsed_s"]
        results["extractor_usage"] = {"by_command": agg, "total_calls": sum(a["calls"] for a in agg.values()),
                                      "total_prompt_tokens": sum(a["prompt_tokens"] for a in agg.values()),
                                      "total_completion_tokens": sum(a["completion_tokens"] for a in agg.values())}
    prev = HERE / "results_artifact_retention.json"
    if prev.exists():
        results["artifact_anchor_retention"] = json.loads(prev.read_text(encoding="utf-8"))
    ctx = HERE / "results_luna_context.json"
    if ctx.exists():
        results["luna_402_context"] = json.loads(ctx.read_text(encoding="utf-8"))
    # plain-text side-by-side table (A->B in score units, 95% BCa question-cluster interval)
    lines = ["judge | family | natural S_full A->B [95%] | natural S_elig A->B [95%] | template (22 q) A->B [95%] | natural-template (22 q) [95%] | verbatim J>=2 share nat A/B"]
    for judge, label in JUDGES:
        sb = results["side_by_side"].get(judge, {})
        def cell(k):
            x = sb.get(k)
            return "n/a" if not x else "%+.3f [%+.3f, %+.3f]" % (x["A_to_B_score"], x["ci95"][0], x["ci95"][1])
        nt = (sb.get("natural_minus_template") or {}).get("natural_minus_template")
        nt_s = "n/a" if not nt else "%+.3f [%+.3f, %+.3f]" % (nt["mean"], nt["ci95"][0], nt["ci95"][1])
        me = results["per_judge"][judge].get("natural", {}).get("machine_evidence", {})
        me_s = "/".join("n/a" if not me.get(v, {}).get("verbatim_share") else "%.2f" % me[v]["verbatim_share"] for v in ("A", "B"))
        lines.append(f"{judge} | {label} | {cell('natural_S_full')} | {cell('natural_S_elig')} | {cell('template_paired')} | {nt_s} | {me_s}")
    results["text_table"] = lines
    (HERE / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print("results.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
