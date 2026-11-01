#!/usr/bin/env python3
"""Addendum 37 analysis (study6_rescoring).  AI-generated draft; review and test before use.  No network, no model call.

Reads raw/*.jsonl of this study, addendum 26's raw scores (subgraph and development with-hint) and the reference scores of the paper.
Statistics = the paper's rule: question-clustered paired BCa, seed 20260913, B = 10,000 (analyze_holdout.cluster_bootstrap_*),
resolved = 95% interval excludes 0, equivalent = 90% interval inside +-margin (0.30 and 0.50), MDE = 2.8 sigma / sqrt(n).
Readings are those of PLAN.md 37.6, applied as written.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
REPO = ACCESS.parent.parent
sys.path.insert(0, str(HARNESS))
import analyze_holdout as ah  # noqa: E402

SEED, B = 20260913, 10_000
VARIANTS = list("ABCDEF")
CONTRASTS = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F"), ("D", "F"), ("B", "D")]
MARGINS = (0.30, 0.50)
RAW = HERE / "raw"
R26 = HARNESS / "review6_judges" / "raw"
LABEL = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b", "qwen35": "Qwen3.5-4B (Qwen-lineage proxy)",
         "q38": "Qwen3.8-Flash-Next", "gw": "gpt-5.6-luna (gateway)"}
REG_AB = {"delta": 0.565, "ci95": [0.043, 1.130]}  # registered holdout judge J, A->B (paper Section VII)
REG_DB = {"delta": -0.273, "ci95": [-0.576, -0.091]}


# ------------------------------------------------------------------ loading
def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def parse_key(cell_id: str) -> tuple[str, str]:
    parts = cell_id.split("|")[-1].split(":")  # 'A_nohint|dev:A:CQ01' / 'primary:A:CQB01' / 'dev:A:CQ01'
    return parts[1], parts[2]


def repeats(records: list[dict], study: str | None = None, cell_filter=None) -> dict[tuple, dict[int, int]]:
    """(variant, cq) -> {repeat: J} for the first valid record per (cell, repeat); context_skip / invalid cells absent."""
    out: dict[tuple, dict[int, int]] = {}
    for r in records:
        if r.get("repeat", 0) < 1 or not r.get("valid") or r.get("J") is None:
            continue
        if study is not None and r.get("study") != study:
            continue
        if cell_filter is not None and not cell_filter(r["cell_id"]):
            continue
        k = parse_key(r["cell_id"])
        out.setdefault(k, {}).setdefault(r["repeat"], int(r["J"]))
    return out


def cellmean(rep: dict) -> dict[tuple, float]:
    return {k: float(np.mean(list(v.values()))) for k, v in rep.items()}


def round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def skips(records: list[dict], study: str | None = None) -> list[str]:
    return sorted({r["cell_id"] for r in records if r.get("status") == "context_skip" and (study is None or r.get("study") == study)})


# ------------------------------------------------------------------ statistics
def mde(sigma: float, n: int) -> float:
    return 2.8 * sigma / math.sqrt(n) if n else float("nan")


def contrast(scores: dict, v1: str, v2: str) -> dict | None:
    qs = sorted({q for (v, q) in scores if v == v1} & {q for (v, q) in scores if v == v2})
    if len(qs) < 2:
        return None
    a = np.array([scores[(v1, q)] for q in qs])
    b = np.array([scores[(v2, q)] for q in qs])
    d = b - a
    boot = ah.cluster_bootstrap_delta({q: [float(x)] for q, x in zip(qs, d)}, B, SEED)
    out = {"n": len(qs), "mean_first": float(a.mean()), "mean_second": float(b.mean()), "delta": float(d.mean()),
           "sd_d": float(d.std(ddof=1)), "ci95": [boot["ci_lo"], boot["ci_hi"]], "ci90": [boot["ci90_lo"], boot["ci90_hi"]],
           "n_pos": int((d > 0).sum()), "n_neg": int((d < 0).sum()), "n_zero": int((d == 0).sum())}
    out["mde"] = mde(out["sd_d"], len(qs))
    for m in MARGINS:
        out[f"decision_{m:.2f}"] = ah.tost_decision(out["ci95"][0], out["ci95"][1], m, eq_lo=out["ci90"][0], eq_hi=out["ci90"][1])
    out["decision"] = out["decision_0.30"]
    out["sign"] = int(d.mean() > 0) - int(d.mean() < 0)
    out["_d"] = {q: float(x) for q, x in zip(qs, d)}
    return out


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [strip(x) for x in o]
    return o


def contrasts(scores: dict) -> dict:
    return {f"{a}->{b}": contrast(scores, a, b) for a, b in CONTRASTS}


def variant_table(rep: dict) -> dict:
    out = {}
    for v in VARIANTS:
        cells = [(k, r) for k, r in rep.items() if k[0] == v]
        js = [j for _, r in cells for j in r.values()]
        cov = [float(np.mean([x >= 2 for x in r.values()])) for _, r in cells]
        out[v] = {"n": len(cells), "mean_J": float(np.mean(js)) if js else None,
                  "coverage": float(np.mean(cov)) if cov else None,
                  "share_le1": float(np.mean([x <= 1 for x in js])) if js else None}
    return out


def qwk(a, b) -> float:
    return float(ah._qwk_from_values(list(a), list(b)))


def agree(rep_a: dict, ref: dict, cluster_of=lambda k: k[1]) -> dict:
    """rep_a: (cell)->{repeat:J}; ref: cell->int.  Exact agreement and QWK per repeat averaged; offset BCa on cell means."""
    keys = sorted(k for k in rep_a if k in ref)
    if len(keys) < 3:
        return {"n_cells": len(keys)}
    exact, kap = [], []
    for r in (1, 2, 3):
        ks = [k for k in keys if r in rep_a[k]]
        if len(ks) < 3:
            continue
        exact.append(float(np.mean([rep_a[k][r] == ref[k] for k in ks])))
        kap.append(qwk([rep_a[k][r] for k in ks], [ref[k] for k in ks]))
    cells = [{"cluster_id": cluster_of(k), "d": float(np.mean(list(rep_a[k].values()))) - ref[k]} for k in keys]
    off = ah.cluster_bootstrap_stat(cells, lambda cs: float(np.mean([c["d"] for c in cs])), None, "cluster_id", B, SEED)
    return {"n_cells": len(keys), "n_clusters": len({cluster_of(k) for k in keys}), "exact": float(np.mean(exact)),
            "qwk": float(np.mean(kap)), "offset": off["estimate"], "offset_ci95": [off["ci_lo"], off["ci_hi"]]}


def qwk_diff(new: dict, other: dict, ref: dict) -> dict:
    """QWK(new, ref) - QWK(other, ref) with cluster BCa; new: cell->{repeat:J} (half-up rounded mean), other/ref cell->int."""
    keys = sorted(k for k in new if k in other and k in ref)
    cells = [{"cluster_id": k[1], "n": round_half_up(float(np.mean(list(new[k].values())))), "o": other[k], "g": ref[k]} for k in keys]

    def stat(cs):
        return qwk([c["n"] for c in cs], [c["g"] for c in cs]) - qwk([c["o"] for c in cs], [c["g"] for c in cs])

    r = ah.cluster_bootstrap_stat(cells, stat, None, "cluster_id", B, SEED)
    return {"n_cells": len(keys), "diff": r["estimate"], "ci95": [r["ci_lo"], r["ci_hi"]],
            "qwk_new": qwk([c["n"] for c in cells], [c["g"] for c in cells]),
            "qwk_other": qwk([c["o"] for c in cells], [c["g"] for c in cells])}


def run_to_run(rep: dict) -> dict:
    ps, ident = [], []
    for r in rep.values():
        if len(r) == 3:
            v = list(r.values())
            ps += [v[0] == v[1], v[0] == v[2], v[1] == v[2]]
            ident.append(v[0] == v[1] == v[2])
    return {"n_cells_3rep": len(ident), "pairwise_exact": float(np.mean(ps)) if ps else None,
            "all_identical": float(np.mean(ident)) if ident else None}


# ------------------------------------------------------------------ references
def references() -> dict:
    out: dict = {}
    gem = {}
    for c in jl(HARNESS / "real_run" / "cells.jsonl"):
        if c.get("cell_kind") == "primary" and c.get("judge_response_parsed") and int(c["J"]) in range(4):
            gem[(c["variant"], c["cq_id"])] = int(c["J"])
    out["gemini_full"] = gem
    L = {"full": {}, "limited": {}, "subgraph": {}}
    for c in jl(HARNESS / "length_experiment" / "cells_length.jsonl") + jl(HARNESS / "length_experiment" / "luna_full_r35" / "cells_luna_full_r35.jsonl"):
        if c.get("judge_response_parsed") and type(c.get("J")) is int and 0 <= c["J"] <= 3:
            cond = c["cell_id"].split(":")[1]
            L.setdefault(cond, {})[(c["variant"], c["cq_id"])] = int(c["J"])
    out["luna_full"], out["luna_limited"], out["luna_subgraph"] = L["full"], L["limited"], L["subgraph"]
    for name, folder in (("luna_panel48", "gpt-5.6-luna"), ("sonnet_panel48", "anthropic__claude-sonnet-5-5")):
        d = {}
        for c in jl(HARNESS / "real_run" / "paired_ai_audit_48" / folder / "cells.jsonl"):
            if c.get("judge_response_parsed") and type(c.get("J")) is int and 0 <= c["J"] <= 3:
                d[(c["variant"], c["cq_id"])] = int(c["J"])
        out[name] = d
    ev = json.loads((REPO / "output" / "abcdef_evaluation.json").read_text(encoding="utf-8"))["layer1"]["cq_scores"]
    out["dev_qwen"] = {(v, q): int(s) for v, d in ev.items() for q, s in d.items()}
    out["list48"] = {tuple(l.strip().split(":")[1:]) for l in (HARNESS / "real_run" / "second_annotator" / "cell_list_48.txt").read_text().splitlines() if l.strip()}
    return out


def ref_block(ref: dict, sel=None) -> dict:
    sc = {k: float(v) for k, v in ref.items() if sel is None or k in sel}
    return {"variant_table": variant_table({k: {1: int(v)} for k, v in sc.items()}), "contrasts": strip(contrasts(sc))}


# ------------------------------------------------------------------ sub-study A
def hint_reading(label_nohint: dict | None, label_hint: dict | None) -> str:
    def res_pos(c):
        return c is not None and c["decision_0.30"] == "resolved" and c["delta"] > 0
    if label_nohint is None:
        return "not computable"
    if res_pos(label_nohint):
        return "hint-independent"
    if label_hint is not None and res_pos(label_hint):
        return "hint-dependent"
    return "never resolved" if label_hint is not None else "not resolved under no-hint (no with-hint arm to compare)"


def sub_A(refs: dict) -> dict:
    res: dict = {"judges": {}}
    r26 = {"glm": jl(R26 / "raw_glm.jsonl"), "gptoss": jl(R26 / "raw_gptoss.jsonl")}
    for j in ("glm", "gptoss", "qwen35", "q38", "gw"):
        recs = jl(RAW / f"A_{j}.jsonl")
        if not recs and j not in r26:
            res["judges"][j] = {"status": "not run"}
            continue
        arms = {}
        for arm in ("A_hint", "A_nohint", "A_holdout"):
            if arm == "A_hint" and j in r26:
                rep = repeats([r for r in r26[j] if r.get("study") == "dev"])
                src = "addendum 26 (reused, byte-identical prompt)"
            else:
                rep = repeats(recs, arm)
                src = "this addendum"
            if not rep:
                continue
            sc = cellmean(rep)
            arms[arm] = {"source": src, "n_cells_valid": len(rep), "n_context_skip": len(skips(recs, arm)),
                         "variant_table": variant_table(rep), "contrasts": strip(contrasts(sc)), "_contrasts": contrasts(sc),
                         "run_to_run": run_to_run(rep), "_rep": rep}
        if not arms:
            res["judges"][j] = {"status": "no valid records"}
            continue
        e = {"label": LABEL[j], "arms": {}}
        for arm, a in arms.items():
            e["arms"][arm] = {k: v for k, v in a.items() if not k.startswith("_")}
        if "A_nohint" in arms:
            nh = arms["A_nohint"]["_contrasts"]["A->B"]
            h = arms.get("A_hint", {}).get("_contrasts", {}).get("A->B")
            e["reading"] = hint_reading(nh, h)
            if "A_hint" in arms:
                rh_, rn_ = arms["A_hint"]["_rep"], arms["A_nohint"]["_rep"]
                keys = sorted(set(rh_) & set(rn_))
                cells = [{"cluster_id": k[1], "d": float(np.mean(list(rn_[k].values()))) - float(np.mean(list(rh_[k].values())))} for k in keys]
                off = ah.cluster_bootstrap_stat(cells, lambda cs: float(np.mean([c["d"] for c in cs])), None, "cluster_id", B, SEED)
                ex = [rn_[k][1] == rh_[k][1] for k in keys if 1 in rn_[k] and 1 in rh_[k]]
                e["hint_effect"] = {"n_cells": len(keys), "mean_nohint_minus_hint": off["estimate"], "ci95": [off["ci_lo"], off["ci_hi"]],
                                    "exact_agreement_repeat1": float(np.mean(ex)) if ex else None,
                                    "qwk_repeat1": qwk([rn_[k][1] for k in keys if 1 in rn_[k] and 1 in rh_[k]],
                                                       [rh_[k][1] for k in keys if 1 in rn_[k] and 1 in rh_[k]]) if ex else None}
                qs = sorted(set(arms["A_nohint"]["_contrasts"]["A->B"]["_d"]) & set(arms["A_hint"]["_contrasts"]["A->B"]["_d"]))
                dd = {q: [arms["A_nohint"]["_contrasts"]["A->B"]["_d"][q] - arms["A_hint"]["_contrasts"]["A->B"]["_d"][q]] for q in qs}
                if len(qs) >= 2:
                    bt = ah.cluster_bootstrap_delta(dd, B, SEED)
                    e["A_to_B_shift_nohint_minus_hint"] = {"n": len(qs), "delta": bt["delta"], "ci95": [bt["ci_lo"], bt["ci_hi"]]}
        res["judges"][j] = e
    q = refs["dev_qwen"]
    res["reference_dev_qwen_original"] = {"note": "output/abcdef_evaluation.json layer1 cq_scores (paper's convention), with the hint",
                                          "variant_table": variant_table({k: {1: v} for k, v in q.items()}),
                                          "contrasts": strip(contrasts({k: float(v) for k, v in q.items()}))}
    prox = [j for j in ("q38", "qwen35") if res["judges"].get(j, {}).get("reading")]
    res["original_family_reading"] = (
        {"judge": prox[0], "label": LABEL[prox[0]], "reading": res["judges"][prox[0]]["reading"],
         "is_original_model": False, "note": "Qwen-lineage proxy, not Qwen3-Next-80B-A3B" if prox[0] == "qwen35" else "Qwen3.8-Flash-Next"}
        if prox else {"reading": "not tested for the original family"})
    return res


# ------------------------------------------------------------------ sub-studies B and C
def sub_BC(refs: dict) -> dict:
    res: dict = {"full_view_cells_scored": 0, "full_view_note": "no full view fits a 65,536-token window (fit_full_preflight.json)",
                 "judges": {}}
    r26 = {"glm": jl(R26 / "raw_glm.jsonl"), "gptoss": jl(R26 / "raw_gptoss.jsonl")}
    l48 = refs["list48"]
    gem, lunafull, sonnet = refs["gemini_full"], refs["luna_panel48"], refs["sonnet_panel48"]
    res["references"] = {
        "gemini_full": ref_block(gem), "luna_limited": ref_block(refs["luna_limited"]), "luna_subgraph": ref_block(refs["luna_subgraph"]),
        "luna_full": ref_block(refs["luna_full"]),
        "panel48_QWK_vs_gemini": {"luna_full": agree({k: {1: v} for k, v in lunafull.items()}, {k: gem[k] for k in lunafull}),
                                  "sonnet_full": agree({k: {1: v} for k, v in sonnet.items()}, {k: gem[k] for k in sonnet})}}
    for j in ("glm", "gptoss"):
        recs = jl(RAW / f"L_{j}.jsonl")
        views = {}
        if recs:
            views["limited"] = repeats(recs, "L_limited")
        sub = repeats([r for r in r26[j] if r.get("study") == "holdout_subgraph"])
        if sub:
            views["subgraph"] = sub
        e = {"label": LABEL[j], "views": {}, "n_context_skip_limited": len(skips(recs, "L_limited"))}
        for vname, rep in views.items():
            sc = cellmean(rep)
            ve = {"source": "this addendum" if vname == "limited" else "addendum 26 (reused)", "n_cells_valid": len(rep),
                  "variant_table": variant_table(rep), "contrasts": strip(contrasts(sc)), "run_to_run": run_to_run(rep)}
            ve["C_reading_D_minus_B"] = reading_DB(contrasts(sc)["B->D"])
            ve["C_reading_A_to_B"] = reading_AB(contrasts(sc)["A->B"])
            # C: agreement with each reference over all cells; B: the 48-cell subset
            lun = refs["luna_limited"] if vname == "limited" else refs["luna_subgraph"]
            for scope, sel in (("C_188", None), ("B_48", l48)):
                sub_rep = {k: v for k, v in rep.items() if sel is None or k in sel}
                ve[scope] = {"vs_gemini_full": agree(sub_rep, gem), "vs_luna_same_view": agree(sub_rep, lun),
                             "vs_luna_full": agree(sub_rep, refs["luna_full"]),
                             "share_J_le1": float(np.mean([x <= 1 for r in sub_rep.values() for x in r.values()])) if sub_rep else None}
                if sel is not None:
                    ve[scope]["vs_sonnet_full"] = agree(sub_rep, sonnet)
                    ve[scope]["vs_luna_panel48_full"] = agree(sub_rep, lunafull)
                    if sub_rep:
                        ve[scope]["QWK_new_minus_sonnet_vs_gemini"] = qwk_diff(sub_rep, sonnet, gem)
                        ve[scope]["QWK_new_minus_luna_vs_gemini"] = qwk_diff(sub_rep, lunafull, gem)
                        ve[scope]["floor_warning"] = ve[scope]["share_J_le1"] > 0.8 if ve[scope]["share_J_le1"] is not None else None
                        d = ve[scope]["QWK_new_minus_sonnet_vs_gemini"]
                        ve[scope]["B_reading_vs_sonnet"] = ("comparable" if d["ci95"][0] <= 0 <= d["ci95"][1] else
                                                            "lower" if d["ci95"][1] < 0 else "higher")
            e["views"][vname] = ve
            e.setdefault("_rep", {})[vname] = rep
        res["judges"][j] = e
    # inter-judge agreement per view
    res["inter_judge"] = {}
    for vname, lun in (("limited", refs["luna_limited"]), ("subgraph", refs["luna_subgraph"])):
        a, b = res["judges"]["glm"].get("_rep", {}).get(vname), res["judges"]["gptoss"].get("_rep", {}).get(vname)
        if a and b:
            rb = {k: round_half_up(float(np.mean(list(v.values())))) for k, v in b.items()}
            res["inter_judge"][vname] = {"glm_vs_gptoss": agree(a, rb), "gptoss_vs_gemini_direction": None}
    for j in res["judges"]:
        res["judges"][j].pop("_rep", None)
    return res


def reading_DB(c: dict | None) -> str:
    if c is None:
        return "not computable"
    if c["delta"] < 0 and c["ci95"][1] < 0:
        return "replicates (D-B < 0, 95% interval excludes 0)"
    if c["delta"] < 0:
        return "direction only (D-B < 0, interval includes 0)"
    return "does not replicate (D-B >= 0)"


def reading_AB(c: dict | None) -> str:
    if c is None:
        return "not computable"
    s = "direction agrees (A->B > 0)" if c["delta"] > 0 else "direction differs (A->B <= 0)"
    return s + "; " + c["decision_0.30"] + " at 0.30, " + c["decision_0.50"] + " at 0.50"


# ------------------------------------------------------------------ report
def f(x, k=3, plus=False):
    return "n/a" if x is None else (f"{x:+.{k}f}" if plus else f"{x:.{k}f}")


def ci(c, k=3):
    return "n/a" if c is None else f"[{c[0]:+.{k}f}, {c[1]:+.{k}f}]"


def crow(c):
    if c is None:
        return "n/a"
    return f"n={c['n']}, {c['delta']:+.3f} {ci(c['ci95'])}, MDE {c['mde']:.2f}, {c['decision_0.30']}/0.30 {c['decision_0.50']}/0.50"


def render(res: dict) -> str:
    L = ["# REPORT (auto) -- addendum 37, study6_rescoring", "",
         "> AI-generated; exploratory and post hoc; readings are PLAN.md 37.6 as written. Review before use.", ""]
    A = res["A"]
    L += ["## A. Development study without the hint", ""]
    L += [f"Reference, original Qwen development judge (with hint): A->B {crow(A['reference_dev_qwen_original']['contrasts']['A->B'])}", ""]
    for j, e in A["judges"].items():
        if "arms" not in e:
            L.append(f"* `{j}`: {e.get('status')}")
            continue
        L.append(f"### {e['label']} (`{j}`): reading **{e.get('reading')}**")
        for arm, a in e["arms"].items():
            L.append(f"* {arm} ({a['source']}; valid cells {a['n_cells_valid']}, context-skipped {a['n_context_skip']}): A->B {crow(a['contrasts']['A->B'])}")
        if "hint_effect" in e:
            h = e["hint_effect"]
            L.append(f"* hint effect (no-hint minus hint, cells): {h['mean_nohint_minus_hint']:+.3f} {ci(h['ci95'])}, exact {f(h['exact_agreement_repeat1'])}, QWK {f(h['qwk_repeat1'])}")
        if "A_to_B_shift_nohint_minus_hint" in e:
            s = e["A_to_B_shift_nohint_minus_hint"]
            L.append(f"* A->B shift (no-hint minus hint): {s['delta']:+.3f} {ci(s['ci95'])} over {s['n']} questions")
        L.append("")
    L += [f"Original-family reading: {json.dumps(A['original_family_reading'])}", ""]
    BC = res["BC"]
    L += ["## B and C. Re-scoring on the 60,000-character view and reuse of addendum-26 subgraph scores", "",
          f"Full-view cells scored: {BC['full_view_cells_scored']} ({BC['full_view_note']}).", ""]
    for j, e in BC["judges"].items():
        L.append(f"### {e['label']} (`{j}`)")
        for vname, v in e["views"].items():
            L.append(f"* view {vname} ({v['source']}, valid cells {v['n_cells_valid']}): A->B {crow(v['contrasts']['A->B'])}; D-B {crow(v['contrasts']['B->D'])}")
            L.append(f"  * D vs B reading: {v['C_reading_D_minus_B']}; A->B: {v['C_reading_A_to_B']}")
            vt = v["variant_table"]
            L.append("  * coverage by variant: " + ", ".join(f"{k} {f(x['coverage'],2)}" for k, x in vt.items()))
            for scope in ("C_188", "B_48"):
                s = v[scope]
                g = s["vs_gemini_full"]
                lu = s["vs_luna_same_view"]
                L.append(f"  * {scope}: vs Gemini full exact {f(g.get('exact'))} QWK {f(g.get('qwk'))} offset {f(g.get('offset'),3,True)} {ci(g.get('offset_ci95')) if g.get('offset_ci95') else ''}; "
                         f"vs luna same view exact {f(lu.get('exact'))} QWK {f(lu.get('qwk'))} offset {f(lu.get('offset'),3,True)}; share J<=1 {f(s['share_J_le1'],2)}")
                if scope == "B_48":
                    L.append(f"  * B_48 QWK(new,Gemini)-QWK(Sonnet,Gemini): {json.dumps(s.get('QWK_new_minus_sonnet_vs_gemini'))}; reading {s.get('B_reading_vs_sonnet')}; floor warning {s.get('floor_warning')}")
        L.append("")
    L += ["### Inter-judge", "```", json.dumps(BC["inter_judge"], indent=1), "```", ""]
    L += ["### References", "```", json.dumps({k: {"A->B": v['contrasts']['A->B'], "B->D": v['contrasts']['B->D'],
                                                   "cov": {x: y['coverage'] for x, y in v['variant_table'].items()}}
                                              for k, v in BC["references"].items() if k != "panel48_QWK_vs_gemini"}, indent=1), "```", ""]
    L += ["Panel-48 QWK vs Gemini (references):", "```", json.dumps(BC["references"]["panel48_QWK_vs_gemini"], indent=1), "```"]
    return "\n".join(L) + "\n"


def tables(res: dict) -> str:
    rows = ["% AI-generated; addendum 37; review before use", "\\begin{tabular}{@{}llrrl@{}}", "\\toprule",
            "Judge / arm & contrast & $n$ & $\\Delta$ [95\\% BCa] & decision (0.30 / 0.50) \\\\", "\\midrule"]
    for j, e in res["A"]["judges"].items():
        for arm, a in e.get("arms", {}).items():
            c = a["contrasts"]["A->B"]
            if c:
                rows.append(f"{j} {arm.replace('_', '-')} & A$\\to$B & {c['n']} & {c['delta']:+.3f} [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}] & {c['decision_0.30']} / {c['decision_0.50']} \\\\")
    rows += ["\\midrule"]
    for j, e in res["BC"]["judges"].items():
        for vn, v in e["views"].items():
            for key, lab in (("A->B", "A$\\to$B"), ("B->D", "B$\\to$D")):
                c = v["contrasts"][key]
                if c:
                    rows.append(f"{j} {vn} & {lab} & {c['n']} & {c['delta']:+.3f} [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}] & {c['decision_0.30']} / {c['decision_0.50']} \\\\")
    rows += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(rows) + "\n"


def main() -> int:
    refs = references()
    res = {"addendum": 37, "seed": SEED, "B": B, "post_hoc": True, "A": sub_A(refs), "BC": sub_BC(refs)}
    # drop private keys
    def clean(o):
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items() if not str(k).startswith("_")}
        if isinstance(o, list):
            return [clean(x) for x in o]
        return o
    res = clean(res)
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    (HERE / "REPORT_auto.md").write_text(render(res), encoding="utf-8")
    (HERE / "tables.tex").write_text(tables(res), encoding="utf-8")
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
