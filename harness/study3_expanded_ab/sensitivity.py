#!/usr/bin/env python3
"""Addendum 34 A2: floor-imputation sensitivity (a cell with no view / no score gets J = 0) over ALL eligible clusters of each bank.
AI-generated; review and test before use.  No model call.  Sensitivity, post hoc; not human-labelled.  Does not replace the main analysis."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_all as aa  # noqa: E402

HARNESS = aa.HARNESS
BANNER = "sensitivity, post hoc, not human-labelled: a missing A or B cell is set to J = 0 (judge floor); main analysis unchanged"


def mfile(name: str) -> list[dict]:
    return json.loads((aa.MAN10 / f"{name}.json").read_text(encoding="utf-8"))["rows"]


def v2x_rule() -> tuple[set[tuple[str, str]], set[str]]:
    import run_holdout as rh
    import s2_views as V
    rows = {r["cq_id"]: r for r in csv.DictReader((HARNESS.parent / "bank" / "cq_bank_brick_v2.csv").open(encoding="utf-8"))}
    qs = {r["cq_id"] for r in mfile("v2x")}
    ok = set()
    for v in "ABCDEF":
        t = V.rendering(v)
        for q in qs:
            if rh._grounding_match_info(t, {"grounding": rows[q]["grounding"]})["can_ablate"]:
                ok.add((v, q))
    return ok, {q for _, q in ok}


def universes() -> dict[str, dict]:
    m6 = json.loads((HARNESS / "review6_raters" / "cells_manifest.json").read_text())["cells"]
    ho = {(c["variant"], c["cq_id"]) for c in m6}
    el = json.loads((aa.S2 / "manifests" / "eligibility.json").read_text())["cells"]
    exp_ok = {(c["variant"], c["cq_id"]) for c in el.values() if c["eligible"]}
    v2_all, v2_clusters = v2x_rule()
    v2_ab = {(v, q) for v, q in v2_all if v in "AB"}
    allq = lambda name: {r["cq_id"] for r in mfile(name)}  # noqa: E731
    return {
        "holdout": dict(U={q for _, q in ho}, rule={x for x in ho if x[0] in "AB"}),
        "paraphrases": dict(U={q for _, q in ho}, rule={x for x in ho if x[0] in "AB"}),
        "v2_extras": dict(U=v2_clusters, rule=v2_ab),
        "expansion": dict(U={q for _, q in exp_ok}, rule={x for x in exp_ok if x[0] in "AB"}),
        "dev_summary": dict(U={f"CQ{i:02d}" for i in range(1, 17)}, rule=None),
        "dev_ext_subgraph": dict(U=allq("dev"), rule=None),
        "natural_docs": dict(U={r["cq_id"] for r in json.loads(json.dumps([{"cq_id": f"CQB{i:02d}"} for i in range(1, 37)]))}, rule=None),
        "second_domain_mfg": dict(U=allq("mfg"), rule=None),
    }


def impute(partial: dict, U: set, rule) -> tuple[dict, dict]:
    out, cnt = {}, {"n_clusters": len(U), "missing_A": 0, "missing_B": 0, "missing_both": 0, "missing_A_eligible_no_view": 0,
                    "missing_B_eligible_no_view": 0, "clusters_scored_in_main": 0}
    for c in sorted(U):
        v = partial.get(c, {})
        cell = {}
        for var in "AB":
            if var in v:
                cell[var] = v[var]
            else:
                cell[var] = 0.0
                cnt[f"missing_{var}"] += 1
                if rule is not None and (var, c) in rule:
                    cnt[f"missing_{var}_eligible_no_view"] += 1
        cnt["missing_both"] += int("A" not in v and "B" not in v)
        cnt["clusters_scored_in_main"] += int("A" in v and "B" in v)
        out[c] = cell
    return out, cnt


def main() -> int:
    U = universes()
    res = {"banner": BANNER, "addendum": "34 A2", "judges": {}}
    for j in aa.JUDGES:
        P = aa.build_banks(j, require_both=False)
        r = {"model": aa.JUDGES[j], "banks": {}, "pools": {}, "domains": {}}
        imp = {}
        for name, b in P.items():
            u = U[name]
            partial = {c: v for c, v in b["bank"].items() if c in u or True}
            ib, cnt = impute(partial, u["U"], u["rule"])
            extra = sorted(set(partial) - set(u["U"]))
            cnt["scored_clusters_outside_universe"] = len(extra)
            imp[name] = ib
            r["banks"][name] = {**cnt, **aa.summarize(ib)}
        brick = [imp[k] for k in ("holdout", "paraphrases", "v2_extras", "expansion")]
        r["pools"]["brick_frozen_only (holdout)"] = aa.summarize(aa.pool([brick[0]]))
        r["pools"]["brick_frozen (holdout + expansion)"] = aa.summarize(aa.pool([brick[0], brick[3]]))
        r["pools"]["brick_all (+ paraphrases, v2 extras; AI-draft)"] = aa.summarize(aa.pool(brick))
        r["domains"]["brick holdout graphs (all pool)"] = r["pools"]["brick_all (+ paraphrases, v2 extras; AI-draft)"]
        r["domains"]["development corpus (summary + ext)"] = aa.summarize(aa.pool([imp["dev_summary"], imp["dev_ext_subgraph"]]))
        r["domains"]["natural Brick documentation"] = r["banks"]["natural_docs"]
        r["domains"]["second domain (aggregate only)"] = r["banks"]["second_domain_mfg"]
        res["judges"][j] = r
    (HERE / "results_sensitivity.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (HERE / "REPORT_sensitivity.md").write_text(report(res), encoding="utf-8")
    return 0


def report(res: dict) -> str:
    main_res = json.loads((HERE / "results_all.json").read_text())
    L = [f"## A2 sensitivity -- {BANNER}", "",
         "Universe per bank = all eligible clusters (expansion 70). A missing A or B cell (not eligible by the paper's rule, or no subgraph view) is J = 0. Main = the main analysis (clusters with both cells scored). Counts are cells in the universe; 'elig, no view' = eligible by rule but no view or score.", ""]
    hdr = "| row | universe n | miss A / B / both (elig, no view A / B) | main n, delta | sens. J(A) | sens. J(B) | sens. delta [95% BCa] | MDE (1.155 / 1.343 / realized) | sign p / Wilcoxon p | decision (main -> sens.) |\n|---|---|---|---|---|---|---|---|---|---|"
    for j, r in res["judges"].items():
        mj = main_res["judges"][j]
        L += [f"### {r['model']}", "", "#### per bank", hdr]
        for k, s in r["banks"].items():
            m = mj["banks"][k]
            L.append(row(k, s, m))
        L += ["", "#### pooled and per domain", hdr]
        for grp, mg in (("pools", "pools"), ("domains", "domains")):
            for k, s in r[grp].items():
                mk = {"brick_frozen (holdout + expansion)": "brick_frozen (holdout + expansion; expansion unreviewed)",
                      "development corpus (summary + ext)": "development corpus (summary + ext subgraph, clustered by question)"}.get(k, k)
                m = mj[mg].get(mk) or mj["pools"].get(mk) or {}
                L.append(row(k, s, m))
        L.append("")
    L += ["Reading: the floor is an assumption, not a measurement (PLAN A2.3); it favors the variant whose graph has more matching content.", ""]
    return "\n".join(L)


def row(name, s, m):
    miss = f"{s.get('missing_A','-')} / {s.get('missing_B','-')} / {s.get('missing_both','-')} ({s.get('missing_A_eligible_no_view','-')} / {s.get('missing_B_eligible_no_view','-')})" if "missing_A" in s else "-"
    md = f"{m['n_clusters']}, {m['delta']:+.3f}" if m and "delta" in m else "-"
    p = s["prospective_mde"]
    w = s["wilcoxon"]["p"]
    return (f"| {name} | {s['n_clusters']} | {miss} | {md} | {s['mean_J_A']:.3f} | {s['mean_J_B']:.3f} | {s['delta']:+.3f} [{s['ci95'][0]:+.3f}, {s['ci95'][1]:+.3f}] | "
            f"{p['prespecified_1.155']:.2f} / {p['holdout_J_1.343']:.2f} / {s['realized_mde']:.2f} | {s['sign_test']['p']:.3f} / {'-' if w is None else f'{w:.3f}'} | {m.get('decision','-') if m else '-'} -> {s['decision']} |")


if __name__ == "__main__":
    raise SystemExit(main())
