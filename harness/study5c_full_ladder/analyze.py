#!/usr/bin/env python3
"""Amendment C analysis: the full A-F ladder on DCAT, SOSA/SSN, PROV for the judge panel.  AI-generated; review and test before use.

  analyze.py extract   raw/cde_<judge>.jsonl -> scores_cde_<judge>.csv, calls_summary.json
  analyze.py run       -> results.json, REPORT_auto.md, tables.tex
A, B, F scores are read from the committed Study 5 CSVs (reused).  C, D, E scores are this amendment's.  The gateway judge has no C-E scores (402, skipped) and is left out.
Contrast code = Study 5's `d_by_cluster` + Study 4's `contrast_from_d` (BCa, seed 20260913, B = 10000, rule as in PLAN C.4); margin 0.50 pre-fixed, 0.30 also reported.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

import p5c_common as K

C = K.C
_spec = importlib.util.spec_from_file_location("s5analyze", K.S5 / "analyze.py")
s5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s5)
s4 = s5.s4

BANNER = "judge-score ladder A-F on three W3C domains; not human-labelled; exploratory, post hoc (addendum 36 amendment C)"
JUDGES = ["glm", "gptoss", "q38", "q80"]
INDEP = ["glm", "gptoss", "q38"]
SCOPES = list(C.DOMAINS) + ["new_domains_pooled"]
ADJ = [("A", "B"), ("B", "C"), ("C", "D"), ("D", "E"), ("E", "F")]
VS_A = [("A", "B"), ("A", "C"), ("A", "D"), ("A", "E"), ("A", "F")]
PAIRS = ADJ + VS_A[1:]
CHAIN = ["B", "C", "D", "E", "F"]


# ------------------------------------------------------------------------------------------------------------------------------ extraction
def extract() -> int:
    summ = {}
    for j in JUDGES:
        p = K.HERE / "raw" / f"cde_{j}.jsonl"
        best: dict = {}
        calls = {"records": 0, "valid": 0, "invalid": 0, "prompt_tokens": 0, "completion_tokens": 0, "model": None}
        for r in C.jsonl(p):
            if r.get("repeat", 0) == 0:
                continue
            k = (r["cell_id"], r["repeat"])
            if k not in best or r.get("valid") or not best[k].get("valid"):
                best[k] = r
            calls["records"] += 1
            calls["prompt_tokens"] += r.get("prompt_tokens") or 0
            calls["completion_tokens"] += r.get("completion_tokens") or 0
            calls["model"] = r.get("model")
        with (K.HERE / f"scores_cde_{j}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["panel_id", "repeat", "J"])
            for (cid, rep), r in sorted(best.items()):
                if r.get("valid") and r.get("J") is not None:
                    w.writerow([cid, rep, int(r["J"])])
                    calls["valid"] += 1
                else:
                    calls["invalid"] += 1
        summ[j] = calls
    (K.HERE / "calls_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps({j: {k: v for k, v in c.items() if k in ("records", "valid", "invalid")} for j, c in summ.items()}))
    return 0


# ------------------------------------------------------------------------------------------------------------------------------ statistics
def d_by_cluster(cells, means, first, second):
    return s5.d_by_cluster(cells, means, first, second)


def scope_d(cells, means, scope, first, second):
    if scope in C.DOMAINS:
        return d_by_cluster([c for c in cells if c["scope"] == scope], means, first, second)
    if scope == "new_domains_pooled":
        out: dict = {}
        for d in C.DOMAINS:
            out.update(d_by_cluster([c for c in cells if c["scope"] == d], means, first, second))
        return out
    raise KeyError(scope)


def verdict30(r: dict) -> str:
    """second reading at +-0.30: resolved (95% BCa excludes 0, unchanged) | equivalent_030 (90% BCa inside +-0.30) | unresolved_030 | none/underpowered"""
    if not r or r.get("n_clusters", 0) < 2 or "ci90" not in r:
        return "none"
    if r.get("underpowered_flag"):
        return "underpowered"
    lo, hi = r["ci95"]
    if lo > 0 or hi < 0:
        return "resolved"
    lo9, hi9 = r["ci90"]
    return "equivalent" if (lo9 > -0.30 and hi9 < 0.30) else "unresolved"


def contrasts_for(cells, means, pairs=PAIRS) -> dict:
    out: dict = {}
    for first, second in pairs:
        for sc in SCOPES:
            d = scope_d(cells, means, sc, first, second)
            key = f"{first}->{second}|{sc}"
            if not d:
                out[key] = {"n_clusters": 0, "verdict": "none", "verdict_030": "none"}
                continue
            r = s4.contrast_from_d(d)
            r["verdict"] = s5.verdict(r, first, second)
            r["verdict_030"] = verdict30(r)
            out[key] = r
    return out


def ladder_means(cells, means) -> dict:
    """scope -> variant -> {n_cells, mean_J} over eligible and scored cells."""
    out: dict = {}
    for sc in SCOPES:
        cs = [c for c in cells if (c["scope"] == sc if sc in C.DOMAINS else True) and c["panel_id"] in means]
        out[sc] = {}
        for v in K.ALL_VARIANTS:
            vals = [means[c["panel_id"]] for c in cs if c["variant"] == v]
            out[sc][v] = {"n_cells": len(vals), "mean_J": float(np.mean(vals)) if vals else None}
    return out


def common_clusters_means(cells, means) -> dict:
    """mean J per variant B..F over the clusters whose cells are all scored in all five variants (a balanced set)."""
    out: dict = {}
    for sc in SCOPES:
        cs = [c for c in cells if (c["scope"] == sc if sc in C.DOMAINS else True) and c["panel_id"] in means and c["variant"] in CHAIN]
        by: dict = {}
        for c in cs:
            by.setdefault(c["cluster"], {})[c["variant"]] = means[c["panel_id"]]
        full = {k: v for k, v in by.items() if all(x in v for x in CHAIN)}
        out[sc] = {"n_clusters": len(full), **{v: (float(np.mean([x[v] for x in full.values()])) if full else None) for v in CHAIN}}
    return out


def monotone(seq: list) -> dict:
    s = [x for x in seq]
    if any(x is None for x in s):
        return {"steps_nondecreasing": None, "steps": None, "monotone_nondecreasing": None}
    ups = sum(b >= a for a, b in zip(s, s[1:]))
    return {"steps_nondecreasing": ups, "steps": len(s) - 1, "monotone_nondecreasing": ups == len(s) - 1,
            "strictly_increasing_steps": sum(b > a for a, b in zip(s, s[1:]))}


def counts(per: dict, key: str, judges: list[str]) -> dict:
    first, second = key.split("|")[0].split("->")
    cnt = {"second_gt_first": 0, "first_gt_second": 0, "equivalent": 0, "unresolved": 0, "underpowered": 0, "none": 0}
    for j in judges:
        v = per[j]["contrasts"].get(key, {}).get("verdict", "none")
        v = "second_gt_first" if v == f"resolved_{second}_gt_{first}" else "first_gt_second" if v == f"resolved_{first}_gt_{second}" else v
        cnt[v] += 1
    cnt["n_judges"] = len(judges)
    return cnt


def load_cells() -> tuple[list[dict], dict]:
    ab = json.loads((K.S5 / "cells_ab.json").read_text(encoding="utf-8"))["cells"]
    f = json.loads((K.S5 / "cells_f.json").read_text(encoding="utf-8"))["cells"]
    cde = json.loads((K.HERE / "cells_cde.json").read_text(encoding="utf-8"))["cells"]
    cells = [c for c in ab if c["scope"] in C.DOMAINS] + f + cde
    return cells, {"A_B_domain": sum(c["scope"] in C.DOMAINS for c in ab), "F": len(f), "C_D_E": len(cde)}


def load_scores() -> dict:
    sc = {}
    for j in JUDGES:
        d = s5.read_panel_csv(K.S5 / f"scores_{j}.csv")
        for pid, v in s5.read_panel_csv(K.HERE / f"scores_cde_{j}.csv").items():
            d.setdefault(pid, []).extend(v)
        sc[j] = d
    return sc


def run() -> int:
    cells, ncells = load_cells()
    ids = {c["panel_id"] for c in cells}
    scores = {j: {k: v for k, v in s.items() if k in ids} for j, s in load_scores().items()}
    calls = json.loads((K.HERE / "calls_summary.json").read_text(encoding="utf-8")) if (K.HERE / "calls_summary.json").exists() else {}
    per = {}
    for j in JUDGES:
        means = {c: s5.cell_mean(v) for c, v in scores[j].items() if v}
        lad, com = ladder_means(cells, means), common_clusters_means(cells, means)
        per[j] = {"label": C.JUDGES[j][0], "family": C.JUDGES[j][1], "counts_toward_panel": C.JUDGES[j][2], "calls_cde": calls.get(j, {}),
                  "n_cells_scored": len(means), "ladder": lad, "common_clusters_B_to_F": com, "contrasts": contrasts_for(cells, means),
                  "monotone_B_to_F": {sc: {"all_eligible_cells": monotone([lad[sc][v]["mean_J"] for v in CHAIN]),
                                           "common_clusters": monotone([com[sc][v] for v in CHAIN])} for sc in SCOPES}}
    agg = {}
    for name, excl in (("panel_mean_all", set()), ("panel_mean_without_q80", {"q80"})):
        pool: dict = {}
        for j in JUDGES:
            if j in excl:
                continue
            for c, v in scores[j].items():
                pool.setdefault(c, []).extend(v)
        means = {c: s5.cell_mean(v) for c, v in pool.items() if v}
        lad, com = ladder_means(cells, means), common_clusters_means(cells, means)
        agg[name] = {"judges": [j for j in JUDGES if j not in excl], "ladder": lad, "common_clusters_B_to_F": com, "contrasts": contrasts_for(cells, means),
                     "monotone_B_to_F": {sc: {"all_eligible_cells": monotone([lad[sc][v]["mean_J"] for v in CHAIN]),
                                              "common_clusters": monotone([com[sc][v] for v in CHAIN])} for sc in SCOPES}}
    panel = {}
    for first, second in PAIRS:
        for sc in SCOPES:
            k = f"{first}->{second}|{sc}"
            panel[k] = {"independent": counts(per, k, INDEP), "same_family_q80": counts(per, k, ["q80"])}
    cde_ids = {c["panel_id"] for c in cells if c["variant"] in K.NEW_VARIANTS}
    allc = {j: scores[j] for j in JUDGES}
    agree = s5.agreement(allc, cde_ids)
    res = {"banner": BANNER, "addendum": "36C", "seed": C.SEED, "B": C.BOOT_B, "margins": list(K.MARGINS), "independent_judges": INDEP,
           "cells": ncells, "cells_per_domain_variant": {d: {v: sum(c["scope"] == d and c["variant"] == v for c in cells) for v in K.ALL_VARIANTS} for d in C.DOMAINS},
           "per_judge": per, "panel_aggregate": agg, "panel_summary": panel, "agreement_qwk_cde_cells": agree,
           "gateway": "gpt-5.6-luna probe returned HTTP 402 (Payment Required); not scored, not in the ladder"}
    (K.HERE / "results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    (K.HERE / "REPORT_auto.md").write_text(report(res), encoding="utf-8")
    (K.HERE / "tables.tex").write_text(tables(res), encoding="utf-8")
    return 0


# ------------------------------------------------------------------------------------------------------------------------------ rendering
def _f(x, k=2):
    return "n/a" if x is None else f"{x:.{k}f}"


def _cell(r: dict) -> str:
    if not r or "ci95" not in r:
        return f"n={r.get('n_clusters', 0)}; {r.get('verdict', 'none')}"
    return f"n={r['n_clusters']}; {r['delta']:+.3f} [{r['ci95'][0]:+.2f}, {r['ci95'][1]:+.2f}]; {r['verdict']}" + ("" if r["verdict_030"] == r["verdict"].split("_")[0] or r["verdict"].startswith("resolved") else f" (at 0.30: {r['verdict_030']})")


def report(res: dict) -> str:
    P = res["per_judge"]
    L = [f"# Addendum 36 amendment C -- {res['banner']}", "",
         "Post hoc, exploratory. A, B, F scores reused from Study 5; C, D, E new. Independent set = GLM-4.7-Flash, gpt-oss-20b, Qwen3.8-Flash-Next (Qwen lineage, flagged); Qwen3-Next-80B is the extractor's model id (same family), shown separately. "
         "Equivalence margin +-0.50 (pre-fixed), +-0.30 shown in brackets only where it differs. The gateway judge (gpt-5.6-luna) returned HTTP 402 on its probe and was not scored.", "",
         "## Cells (eligible, scored) per domain and variant", "", "| domain | " + " | ".join(K.ALL_VARIANTS) + " |", "|---|" + "---|" * 6]
    for d, v in res["cells_per_domain_variant"].items():
        L.append(f"| {d} | " + " | ".join(str(v[x]) for x in K.ALL_VARIANTS) + " |")
    L += ["", "## Ladder: mean J per judge (n cells)", ""]
    for j in JUDGES:
        L += [f"### {P[j]['label']} ({P[j]['family']})", "", "| scope | " + " | ".join(K.ALL_VARIANTS) + " |", "|---|" + "---|" * 6]
        for sc in SCOPES:
            lad = P[j]["ladder"][sc]
            L.append(f"| {sc} | " + " | ".join(f"{_f(lad[v]['mean_J'])} ({lad[v]['n_cells']})" for v in K.ALL_VARIANTS) + " |")
        L.append("")
    L += ["## Monotonicity along B -> C -> D -> E -> F (descriptive)", "", "| judge | scope | means B..F (all eligible cells) | non-decreasing steps | monotone | common clusters (n) means B..F | monotone |", "|---|---|---|---|---|---|---|"]
    for name, src in [(P[j]["label"], P[j]) for j in JUDGES] + [(k, v) for k, v in res["panel_aggregate"].items()]:
        for sc in SCOPES:
            lad, com, mo = src["ladder"][sc], src["common_clusters_B_to_F"][sc], src["monotone_B_to_F"][sc]
            a, b = mo["all_eligible_cells"], mo["common_clusters"]
            L.append(f"| {name} | {sc} | " + " ".join(_f(lad[v]["mean_J"]) for v in CHAIN) + f" | {a['steps_nondecreasing']}/{a['steps']} | {a['monotone_nondecreasing']} | "
                     + " ".join(_f(com[v]) for v in CHAIN) + f" ({com['n_clusters']}) | {b['monotone_nondecreasing']} |")
    L += ["", "## Adjacent contrasts, per judge (n; delta [95% BCa]; decision)", ""]
    for first, second in ADJ:
        L += [f"### {first} -> {second}", "", "| scope | " + " | ".join(P[j]["label"] for j in JUDGES) + " | panel mean (descr.) |", "|---|" + "---|" * (len(JUDGES) + 1)]
        for sc in SCOPES:
            k = f"{first}->{second}|{sc}"
            L.append(f"| {sc} | " + " | ".join(_cell(P[j]["contrasts"][k]) for j in JUDGES) + f" | {_cell(res['panel_aggregate']['panel_mean_all']['contrasts'][k])} |")
        L.append("")
    L += ["## Contrasts against A (per judge)", ""]
    for first, second in VS_A[1:]:
        L += [f"### {first} -> {second}", "", "| scope | " + " | ".join(P[j]["label"] for j in JUDGES) + " |", "|---|" + "---|" * len(JUDGES)]
        for sc in SCOPES:
            k = f"{first}->{second}|{sc}"
            L.append(f"| {sc} | " + " | ".join(_cell(P[j]["contrasts"][k]) for j in JUDGES) + " |")
        L.append("")
    L += ["## Panel summary (independent judges: second>first / first>second / equivalent / unresolved / underpowered; same-family q80 decision)", "",
          "| contrast | scope | n judges | independent | q80 |", "|---|---|---|---|---|"]
    for k, v in res["panel_summary"].items():
        c = v["independent"]
        L.append(f"| {k.split('|')[0]} | {k.split('|')[1]} | {c['n_judges']} | {c['second_gt_first']} / {c['first_gt_second']} / {c['equivalent']} / {c['unresolved']} / {c['underpowered']} | "
                 + next(x for x, n in v["same_family_q80"].items() if x != "n_judges" and n) + " |")
    L += ["", "## Agreement on the C, D, E cells (QWK on per-cell median-low of repeats)", ""]
    for k, v in res["agreement_qwk_cde_cells"].items():
        L.append(f"- {k}: n={v['n_cells']}, QWK {_f(v['qwk'], 3)}, exact {_f(v['exact_agreement'], 3)}")
    L += ["", "## Calls (C, D, E)", ""] + [f"- {j}: " + json.dumps(P[j]["calls_cde"]) for j in JUDGES]
    return "\n".join(L) + "\n"


def tables(res: dict) -> str:
    P = res["per_judge"]
    L = ["% Addendum 36C: " + res["banner"], "% ladder rows: judge & scope & mean J (n) for A..F"]
    for j in JUDGES:
        for sc in SCOPES:
            lad = P[j]["ladder"][sc]
            L.append(f"{P[j]['label']} & {sc.replace('_', ' ')} & " + " & ".join(f"{_f(lad[v]['mean_J'])} ({lad[v]['n_cells']})" for v in K.ALL_VARIANTS) + " \\\\")
    L += ["", "% adjacent contrasts: judge & contrast & scope & n & delta [95% BCa] & decision"]
    for j in JUDGES:
        for first, second in ADJ:
            for sc in SCOPES:
                r = P[j]["contrasts"][f"{first}->{second}|{sc}"]
                if "ci95" in r:
                    L.append(f"{P[j]['label']} & {first}$\\to${second} & {sc.replace('_', ' ')} & {r['n_clusters']} & ${r['delta']:+.3f}$ [${r['ci95'][0]:+.2f}$, ${r['ci95'][1]:+.2f}$] & {r['verdict'].replace('_', ' ')} \\\\")
    L += ["", "% panel summary (independent judges): contrast & scope & n judges & second>first / first>second / equivalent / unresolved"]
    for k, v in res["panel_summary"].items():
        c = v["independent"]
        L.append(f"{k.split('|')[0]} & {k.split('|')[1].replace('_', ' ')} & {c['n_judges']} & {c['second_gt_first']} / {c['first_gt_second']} / {c['equivalent']} / {c['unresolved']} \\\\")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    return {"extract": extract, "run": run}[a[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
