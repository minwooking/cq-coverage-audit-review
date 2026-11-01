#!/usr/bin/env python3
"""Addendum 36 analysis: judge panel x scope A->B contrasts, panel summary, pairwise agreement, and F contrasts.  AI-generated; review and test before use.

  analyze.py extract     raw judge records (local) + existing score CSVs -> scores_<judge>.csv (panel_id, repeat, J; committed) + calls_summary.json
  analyze.py run         scores_*.csv + cells_*.json -> results.json, REPORT_auto.md, tables.tex
  analyze.py selftest    (see test_analyze.py)

Judge-score contrasts; not human-labelled; exploratory.  Every constant is the PLAN's (36.6): seed 20260913, B = 10,000, margin +-0.50, the paper's decision rule via
harness/study4_domains/analyze.contrast_from_d (BCa, sign, Wilcoxon, TOST, MDE).  No threshold is changed after a score.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import statistics
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

import p5_common as C

_spec = importlib.util.spec_from_file_location("s4analyze", C.S4 / "analyze.py")
sys.path.insert(0, str(C.S4))
s4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s4)

BANNER = "judge-score contrasts across a judge panel; not human-labelled; exploratory, post hoc (addendum 36)"
AB_SCOPES = list(C.BRICK_BANKS) + ["brick_pool"] + list(C.DOMAINS) + ["new_domains_pooled"]
F_SCOPES = list(C.DOMAINS) + ["new_domains_pooled"]
JUDGE_ORDER = ["glm", "gptoss", "q38", "q80", "gw"]
RAW = {"glm": ("existing_scores_glm.csv", "raw/f_glm.jsonl"), "gptoss": ("existing_scores_gptoss.csv", "raw/f_gptoss.jsonl"),
       "q38": ("raw/ab_q38.jsonl", "raw/f_q38.jsonl"), "q80": ("raw/ab_q80.jsonl", "raw/f_q80.jsonl"), "gw": ("raw/ab_gw.jsonl", "raw/f_gw.jsonl")}


def read_panel_csv(p: Path) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    if Path(p).exists():
        for r in csv.DictReader(Path(p).open(encoding="utf-8", newline="")):
            out.setdefault(r["panel_id"], []).append(int(r["J"]))
    return out


def extract() -> int:
    summ = {}
    for j, files in RAW.items():
        lists: dict[str, list[tuple[int, int]]] = {}
        calls = {"records": 0, "valid": 0, "invalid": 0, "context_skip": 0, "prompt_tokens": 0, "completion_tokens": 0, "model": None}
        for f in files:
            p = C.HERE / f
            if not p.exists():
                continue
            if p.suffix == ".csv":
                for r in csv.DictReader(p.open(encoding="utf-8", newline="")):
                    lists.setdefault(r["panel_id"], []).append((int(r["repeat"]), int(r["J"])))
                    calls["valid"] += 1
                calls["note"] = "A/B scores of Studies 3-4 reused (not re-requested); F cells below are new calls"
                continue
            best: dict = {}
            for r in C.jsonl(p):
                if r.get("repeat", 0) == 0:
                    calls["context_skip"] += 1
                    continue
                k = (r["cell_id"], r["repeat"])
                if k not in best or r.get("valid") or not best[k].get("valid"):
                    best[k] = r
                calls["records"] += 1
                calls["prompt_tokens"] += r.get("prompt_tokens") or 0
                calls["completion_tokens"] += r.get("completion_tokens") or 0
                calls["model"] = r.get("model")
            for (cid, rep), r in best.items():
                if r.get("valid") and r.get("J") is not None:
                    lists.setdefault(cid, []).append((rep, int(r["J"])))
                    calls["valid"] += 1
                else:
                    calls["invalid"] += 1
        with (C.HERE / f"scores_{j}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["panel_id", "repeat", "J"])
            for cid in sorted(lists):
                for rep, J in sorted(lists[cid]):
                    w.writerow([cid, rep, J])
        summ[j] = calls
    (C.HERE / "calls_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps({j: {k: v for k, v in c.items() if k in ("records", "valid", "invalid")} for j, c in summ.items()}))
    return 0


# ----------------------------------------------------------------------------------------------------------------- scopes and contrasts
def cell_mean(vals: list[int | float]) -> float:
    return float(np.mean(vals))


def d_by_cluster(cells: list[dict], means: dict[str, float], first: str, second: str) -> dict[str, float]:
    """cluster -> J(second) - J(first), for the cells given (already restricted to one scope); a cluster needs both cells scored."""
    by: dict[str, dict[str, float]] = {}
    for c in cells:
        if c["variant"] in (first, second) and c["panel_id"] in means:
            by.setdefault(c["cluster"], {})[c["variant"]] = means[c["panel_id"]]
    return {k: v[second] - v[first] for k, v in by.items() if first in v and second in v}


def scope_d(cells: list[dict], means: dict[str, float], scope: str, first: str, second: str) -> dict[str, float]:
    if scope in C.BRICK_BANKS or scope in C.DOMAINS:
        return d_by_cluster([c for c in cells if c["scope"] == scope], means, first, second)
    if scope == "brick_pool":                       # per source question: mean over the banks that contribute (addendum 34 A1)
        acc: dict[str, list[float]] = {}
        for b in C.BRICK_BANKS:
            for k, v in d_by_cluster([c for c in cells if c["scope"] == b], means, first, second).items():
                acc.setdefault(k, []).append(v)
        return {k: float(np.mean(v)) for k, v in acc.items()}
    if scope == "new_domains_pooled":
        out: dict[str, float] = {}
        for d in C.DOMAINS:
            out.update(d_by_cluster([c for c in cells if c["scope"] == d], means, first, second))
        return out
    raise KeyError(scope)


def verdict(res: dict, first: str, second: str) -> str:
    """resolved_<second>_gt_<first> | resolved_<first>_gt_<second> | equivalent | unresolved | underpowered | none"""
    if not res or res.get("decision") in (None, "underpowered") or res.get("n_clusters", 0) < 2:
        return "none" if not res or res.get("n_clusters", 0) < 2 else "underpowered"
    if res.get("underpowered_flag"):
        return "underpowered"
    if res["decision"] == "resolved":
        return f"resolved_{second}_gt_{first}" if res["delta"] > 0 else f"resolved_{first}_gt_{second}"
    return res["decision"]


def contrasts_for(cells: list[dict], means: dict[str, float], contrasts: list[tuple[str, str]]) -> dict:
    out: dict = {}
    for first, second in contrasts:
        scopes = AB_SCOPES if (first, second) == ("A", "B") else F_SCOPES
        for sc in scopes:
            d = scope_d(cells, means, sc, first, second)
            if not d:
                out[f"{first}->{second}|{sc}"] = {"n_clusters": 0, "verdict": "none"}
                continue
            r = s4.contrast_from_d(d)
            r["verdict"] = verdict(r, first, second)
            out[f"{first}->{second}|{sc}"] = r
    return out


def qwk(x: list[int], y: list[int]) -> float | None:
    if not x:
        return None
    k = 4
    O = np.zeros((k, k))
    for a, b in zip(x, y):
        O[a, b] += 1
    n = O.sum()
    hx, hy = O.sum(1), O.sum(0)
    E = np.outer(hx, hy) / n
    W = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)], float) / (k - 1) ** 2
    den = (W * E).sum()
    return None if den == 0 else float(1 - (W * O).sum() / den)


def agreement(scores: dict[str, dict[str, list[int]]], cell_ids: set[str]) -> dict:
    med = {j: {c: int(statistics.median_low(sorted(v))) for c, v in s.items() if c in cell_ids and v} for j, s in scores.items()}
    out = {}
    for a, b in combinations([j for j in JUDGE_ORDER if j in med and med[j]], 2):
        shared = sorted(set(med[a]) & set(med[b]))
        out[f"{a}~{b}"] = {"n_cells": len(shared), "qwk": qwk([med[a][c] for c in shared], [med[b][c] for c in shared]),
                           "exact_agreement": (float(np.mean([med[a][c] == med[b][c] for c in shared])) if shared else None)}
    return out


def panel_counts(per_judge: dict[str, dict], key: str, judges: list[str]) -> dict:
    cats = ["resolved_second_gt_first", "resolved_first_gt_second", "equivalent", "unresolved", "underpowered", "none"]
    first, second = key.split("|")[0].split("->")
    cnt = {c: 0 for c in cats}
    for j in judges:
        v = per_judge[j]["contrasts"].get(key, {}).get("verdict", "none")
        v = "resolved_second_gt_first" if v == f"resolved_{second}_gt_{first}" else "resolved_first_gt_second" if v == f"resolved_{first}_gt_{second}" else v
        cnt[v] += 1
    cnt["judges"] = list(judges)
    return cnt


def run() -> int:
    ab = json.loads((C.HERE / "cells_ab.json").read_text(encoding="utf-8"))
    cellsF = json.loads((C.HERE / "cells_f.json").read_text(encoding="utf-8"))["cells"] if (C.HERE / "cells_f.json").exists() else []
    cells = ab["cells"] + cellsF
    f_ids = {c["panel_id"] for c in cellsF}
    calls = json.loads((C.HERE / "calls_summary.json").read_text(encoding="utf-8")) if (C.HERE / "calls_summary.json").exists() else {}
    scores = {j: read_panel_csv(C.HERE / f"scores_{j}.csv") for j in JUDGE_ORDER}
    present = [j for j in JUDGE_ORDER if scores[j]]
    contrasts = [("A", "B")] + ([("A", "F"), ("B", "F")] if cellsF else [])
    per_judge = {}
    for j in present:
        means = {c: cell_mean(v) for c, v in scores[j].items() if v}
        per_judge[j] = {"label": C.JUDGES[j][0], "family": C.JUDGES[j][1], "counts_toward_rule": C.JUDGES[j][2],
                        "n_cells_scored": len(means), "calls": calls.get(j, {}), "contrasts": contrasts_for(cells, means, contrasts)}
    # descriptive panel-mean aggregate (not a judge)
    agg = {}
    for name, excl in (("panel_mean_all", set()), ("panel_mean_without_q80", {"q80"})):
        pool: dict[str, list[int]] = {}
        for j in present:
            if j in excl:
                continue
            for c, v in scores[j].items():
                pool.setdefault(c, []).extend(v)
        agg[name] = {"judges": [j for j in present if j not in excl], "n_cells": len(pool),
                     "contrasts": contrasts_for(cells, {c: cell_mean(v) for c, v in pool.items() if v}, contrasts)}
    indep = [j for j in present if C.JUDGES[j][2]]
    indep_no_q38 = [j for j in indep if j != "q38"]
    same = [j for j in present if not C.JUDGES[j][2]]
    keys = sorted({k for j in present for k in per_judge[j]["contrasts"]})
    panel = {}
    for k in keys:
        panel[k] = {"independent": panel_counts(per_judge, k, indep), "same_family": panel_counts(per_judge, k, same),
                    "all": panel_counts(per_judge, k, present), "independent_without_q38": panel_counts(per_judge, k, indep_no_q38)}
    rule = {}
    for sc in ("brick_pool", "new_domains_pooled"):
        k = f"A->B|{sc}"
        n_pos = panel[k]["independent"]["resolved_second_gt_first"]
        n_pos2 = panel[k]["independent_without_q38"]["resolved_second_gt_first"]
        rule[sc] = {"independent_judges_answered": len(indep), "resolved_B_gt_A": n_pos, "meets_ge3": n_pos >= 3,
                    "sensitivity_without_q38": {"independent_judges": len(indep_no_q38), "resolved_B_gt_A": n_pos2, "meets_ge3": n_pos2 >= 3}}
    rule["wording"] = ("a majority of judge families resolved B>A" if any(rule[s]["meets_ge3"] for s in ("brick_pool", "new_domains_pooled")) else "judge-dependent")
    ab_ids = {c["panel_id"] for c in ab["cells"]}
    agree = {"A_B_cells": agreement({j: scores[j] for j in present}, ab_ids), "F_cells": agreement({j: scores[j] for j in present}, f_ids)}
    res = {"banner": BANNER, "addendum": 36, "seed": C.SEED, "B": C.BOOT_B, "margin": C.MARGIN, "judges_present": present,
           "cells": {"A_B": len(ab["cells"]), "F": len(cellsF), "ab_summary": ab["summary"]}, "per_judge": per_judge, "panel_aggregate": agg,
           "panel_summary": panel, "interpretation_rule": rule, "agreement_qwk": agree}
    (C.HERE / "results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    (C.HERE / "REPORT_auto.md").write_text(report(res), encoding="utf-8")
    (C.HERE / "tables.tex").write_text(tables(res), encoding="utf-8")
    return 0


# ----------------------------------------------------------------------------------------------------------------- rendering
def _f(x, k=3):
    return "n/a" if x is None else f"{x:.{k}f}"


def _cell(r: dict) -> str:
    if not r or not r.get("n_clusters") or "ci95" not in r:
        return f"n={r.get('n_clusters', 0)}; no interval"
    return f"n={r['n_clusters']}; {r['delta']:+.3f} [{r['ci95'][0]:+.3f}, {r['ci95'][1]:+.3f}]; {r['verdict']}"


def report(res: dict) -> str:
    L = [f"# Addendum 36 results -- {res['banner']}", "",
         "Post hoc. Named non-registered judges only (the registered holdout judge has no route). Views = question-only sub-graphs (Studies 3-4). `qwen3-next-80B` shares the extractor's model id (same family) and is excluded from the interpretation rule; `Qwen3.8-Flash-Next` is Qwen lineage and is counted independent as instructed (sensitivity without it is given). Banks are AI drafts for the new domains and for the non-holdout Brick banks.", ""]
    rule = res["interpretation_rule"]
    L += ["## Interpretation rule (pre-fixed, PLAN 36.6)", "",
          f"Wording permitted: **{rule['wording']}**.", ""]
    for sc in ("brick_pool", "new_domains_pooled"):
        r = rule[sc]
        s = r["sensitivity_without_q38"]
        L.append(f"- {sc}: {r['resolved_B_gt_A']} of {r['independent_judges_answered']} independent-family judges resolved B > A (rule >= 3: {r['meets_ge3']}); without Qwen3.8-Flash-Next: {s['resolved_B_gt_A']} of {s['independent_judges']} ({s['meets_ge3']}).")
    L += ["", "## Per-judge decisions, A -> B (n; delta [95% BCa]; decision)", "", "| scope | " + " | ".join(res["per_judge"][j]["label"] for j in res["judges_present"]) + " | panel mean (descriptive) |", "|---|" + "---|" * (len(res["judges_present"]) + 1)]
    for sc in AB_SCOPES:
        k = f"A->B|{sc}"
        L.append(f"| {sc} | " + " | ".join(_cell(res["per_judge"][j]["contrasts"].get(k, {})) for j in res["judges_present"]) + f" | {_cell(res['panel_aggregate']['panel_mean_all']['contrasts'].get(k, {}))} |")
    L += ["", "## Panel summary (number of judges per decision)", "", "| contrast | scope | independent (n judges) | resolved B>A / A>B / equivalent / unresolved / underpowered | same-family | without Qwen3.8-Flash-Next |", "|---|---|---|---|---|---|"]
    for k, v in res["panel_summary"].items():
        c = v["independent"]
        fmt = lambda c: f"{c['resolved_second_gt_first']} / {c['resolved_first_gt_second']} / {c['equivalent']} / {c['unresolved']} / {c['underpowered']}"
        L.append(f"| {k.split('|')[0]} | {k.split('|')[1]} | {len(c['judges'])} | {fmt(c)} | {fmt(v['same_family'])} | {fmt(v['independent_without_q38'])} |")
    for name, a in res["panel_aggregate"].items():
        L += ["", f"### {name} (descriptive aggregate, not a judge; judges: {', '.join(a['judges'])}; cells {a['n_cells']})", ""]
        for k, r in a["contrasts"].items():
            L.append(f"- {k}: {_cell(r)}")
    L += ["", "## Variant F contrasts (per judge)", ""]
    for j in res["judges_present"]:
        L.append(f"### {res['per_judge'][j]['label']}")
        for k, r in res["per_judge"][j]["contrasts"].items():
            if not k.startswith("A->B"):
                L.append(f"- {k}: {_cell(r)}")
        L.append("")
    L += ["## Pairwise judge agreement (QWK on the per-cell median-low of repeats)", ""]
    for scope, ag in res["agreement_qwk"].items():
        L.append(f"**{scope}**")
        for k, v in ag.items():
            L.append(f"- {k}: n={v['n_cells']}, QWK {_f(v['qwk'])}, exact agreement {_f(v['exact_agreement'])}")
        L.append("")
    L += ["## Calls", ""] + [f"- {j}: " + json.dumps({k: v for k, v in res['per_judge'][j]['calls'].items() if k != 'note'}) for j in res["judges_present"]]
    return "\n".join(L) + "\n"


def tables(res: dict) -> str:
    L = ["% Addendum 36: " + res["banner"], "% rows: judge & scope & n & delta [95% BCa] & decision   (A->B; appendix)"]
    for j in res["judges_present"]:
        for sc in ("brick_pool", "new_domains_pooled") + tuple(C.DOMAINS):
            r = res["per_judge"][j]["contrasts"].get(f"A->B|{sc}", {})
            if "ci95" in r:
                L.append(f"{res['per_judge'][j]['label']} & {sc.replace('_', ' ')} & {r['n_clusters']} & ${r['delta']:+.3f}$ [${r['ci95'][0]:+.2f}$, ${r['ci95'][1]:+.2f}$] & {r['verdict'].replace('_', ' ')} \\\\")
    L += ["", "% panel summary: contrast & scope & independent judges & B>A / A>B / equivalent / unresolved"]
    for k, v in res["panel_summary"].items():
        c = v["independent"]
        L.append(f"{k.split('|')[0]} & {k.split('|')[1].replace('_', ' ')} & {len(c['judges'])} & {c['resolved_second_gt_first']} / {c['resolved_first_gt_second']} / {c['equivalent']} / {c['unresolved']} \\\\")
    L += ["", "% F contrasts: judge & contrast & scope & n & delta [95% BCa] & decision"]
    for j in res["judges_present"]:
        for k, r in res["per_judge"][j]["contrasts"].items():
            if not k.startswith("A->B") and "ci95" in r:
                c, sc = k.split("|")
                L.append(f"{res['per_judge'][j]['label']} & {c} & {sc.replace('_', ' ')} & {r['n_clusters']} & ${r['delta']:+.3f}$ [${r['ci95'][0]:+.2f}$, ${r['ci95'][1]:+.2f}$] & {r['verdict'].replace('_', ' ')} \\\\")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    return {"extract": extract, "run": run}[a[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
