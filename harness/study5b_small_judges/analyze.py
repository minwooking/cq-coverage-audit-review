#!/usr/bin/env python3
"""Addendum 36 amendment B analysis: Qwen size-ladder judges (Qwen3.8-27B, Qwen3.5-9B, Qwen3.5-4B) on the Study 5 cells.  AI-generated; review and test before use.

  analyze.py extract   raw/*.jsonl (local) -> scores_<judge>.csv (panel_id, repeat, J) + calls_summary.json
  analyze.py run       scores_*.csv (+ Study 5 judges' scores, read only) -> results.json, REPORT_auto.md, tables.tex

Same functions and constants as Study 5 (imported from study5_judge_panel/analyze.py): BCa seed 20260913, B = 10,000, margin +-0.50.  Judge-score
contrasts; not human-labelled; exploratory, post hoc.  Nothing here changes a threshold.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
S5 = HERE.parent / "study5_judge_panel"
sys.path.insert(0, str(S5))
_spec = importlib.util.spec_from_file_location("s5analyze", S5 / "analyze.py")
s5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s5)

BANNER = "judge-score contrasts for a Qwen size ladder; not human-labelled; exploratory, post hoc (addendum 36 amendment B)"
LADDER = {"q38_27b": "Qwen3.8-27B", "q35_9b": "Qwen3.5-9B", "q35_4b": "Qwen3.5-4B"}
LADDER_ORDER = ["q38_27b", "q35_9b", "q35_4b"]
OTHERS = list(s5.JUDGE_ORDER)  # glm, gptoss, q38, q80, gw


def lists_from_files(base: Path, files: tuple[str, ...]) -> tuple[dict[str, list[tuple[int, int]]], dict]:
    """(panel_id -> [(repeat, J)], call counts) from raw JSONL records (best record per (cell, repeat)) or a Study-5-style scores CSV."""
    lists: dict[str, list[tuple[int, int]]] = {}
    calls = {"records": 0, "valid": 0, "invalid": 0, "context_skip": 0, "prompt_tokens": 0, "completion_tokens": 0, "model": None}
    for f in files:
        p = base / f
        if not p.exists():
            continue
        if p.suffix == ".csv":
            for r in csv.DictReader(p.open(encoding="utf-8", newline="")):
                key = "panel_id" if "panel_id" in r else "cell_id"
                if "valid" in r and str(r["valid"]).lower() not in ("1", "true"):
                    continue
                lists.setdefault(r[key], []).append((int(r["repeat"]), int(float(r["J"]))))
                calls["valid"] += 1
            continue
        best: dict = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
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
    return lists, calls


def extract() -> int:
    summ = {}
    for j in LADDER_ORDER:
        lists, calls = lists_from_files(HERE, (f"raw/ab_{j}.jsonl", f"raw/f_{j}.jsonl"))
        with (HERE / f"scores_{j}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["panel_id", "repeat", "J"])
            for cid in sorted(lists):
                for rep, J in sorted(lists[cid]):
                    w.writerow([cid, rep, J])
        summ[j] = calls
    (HERE / "calls_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps({j: {k: v for k, v in c.items() if k in ("records", "valid", "invalid", "context_skip")} for j, c in summ.items()}))
    return 0


def read_scores(csv_path: Path) -> dict[str, list[int]]:
    return s5.read_panel_csv(csv_path)


def other_scores(j: str) -> dict[str, list[int]]:
    """A Study 5 judge's scores, read only: its committed scores_<j>.csv if present, else derived from its local raw files / existing CSVs."""
    p = S5 / f"scores_{j}.csv"
    if p.exists():
        return read_scores(p)
    lists, _ = lists_from_files(S5, s5.RAW[j])
    return {c: [J for _, J in v] for c, v in lists.items()}


def pair_agreement(scores: dict[str, dict[str, list[int]]], cell_ids: set[str]) -> dict:
    """QWK for every pair with at least one ladder judge (s5.agreement over the combined list, filtered)."""
    old = s5.JUDGE_ORDER
    s5.JUDGE_ORDER = list(scores)
    try:
        full = s5.agreement(scores, cell_ids)
    finally:
        s5.JUDGE_ORDER = old
    return {k: v for k, v in full.items() if any(x in LADDER for x in k.split("~"))}


def run() -> int:
    ab = json.loads((S5 / "cells_ab.json").read_text(encoding="utf-8"))
    cellsF = json.loads((S5 / "cells_f.json").read_text(encoding="utf-8"))["cells"] if (S5 / "cells_f.json").exists() else []
    cells = ab["cells"] + cellsF
    f_ids = {c["panel_id"] for c in cellsF}
    ab_ids = {c["panel_id"] for c in ab["cells"]}
    calls = json.loads((HERE / "calls_summary.json").read_text(encoding="utf-8")) if (HERE / "calls_summary.json").exists() else {}
    lad = {j: read_scores(HERE / f"scores_{j}.csv") for j in LADDER_ORDER}
    present = [j for j in LADDER_ORDER if lad[j]]
    contrasts = [("A", "B")] + ([("A", "F"), ("B", "F")] if cellsF else [])
    per_judge = {}
    for j in present:
        means = {c: s5.cell_mean(v) for c, v in lad[j].items() if v}
        per_judge[j] = {"label": LADDER[j], "family": "same vendor, different generation" if j != "q38_27b" else "same vendor, same generation as Flash-Next",
                        "n_cells_scored": len(means), "calls": calls.get(j, {}), "contrasts": s5.contrasts_for(cells, means, contrasts)}
    keys = sorted({k for j in present for k in per_judge[j]["contrasts"]})
    panel = {k: s5.panel_counts(per_judge, k, present) for k in keys}
    oth = {j: other_scores(j) for j in OTHERS}
    oth = {j: s for j, s in oth.items() if s}
    allsc = {**oth, **{j: lad[j] for j in present}}
    agree = {"A_B_cells": pair_agreement(allsc, ab_ids), "F_cells": pair_agreement(allsc, f_ids)}
    # reference: the Study 5 judges' own A->B decisions are in study5_judge_panel/results.json (not re-computed here)
    res = {"banner": BANNER, "addendum": "36B", "seed": s5.C.SEED, "B": s5.C.BOOT_B, "margin": s5.C.MARGIN, "judges_present": present,
           "other_judges_for_agreement": sorted(oth), "cells": {"A_B": len(ab["cells"]), "F": len(cellsF)},
           "per_judge": per_judge, "ladder_counts": panel, "agreement_qwk": agree}
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=float), encoding="utf-8")
    (HERE / "REPORT_auto.md").write_text(report(res), encoding="utf-8")
    (HERE / "tables.tex").write_text(tables(res), encoding="utf-8")
    return 0


def report(res: dict) -> str:
    cell = s5._cell
    L = [f"# Addendum 36B results -- {res['banner']}", "",
         "Models: Qwen3.8-27B (as requested); Qwen3.5-9B and Qwen3.5-4B stand in for the non-existent Qwen3.8-8B / -4B (PLAN B.1). All three are the extractor's vendor, not its model; "
         "they are **not** in the pre-fixed independent-family count of addendum 36 (PLAN B.2). Temperature 0, 3 repeats, thinking off, Study 5 prompts and scorer.", "",
         "## A -> B per judge (n; delta [95% BCa]; decision)", "", "| scope | " + " | ".join(res["per_judge"][j]["label"] for j in res["judges_present"]) + " |",
         "|---|" + "---|" * len(res["judges_present"])]
    for sc in s5.AB_SCOPES:
        k = f"A->B|{sc}"
        L.append(f"| {sc} | " + " | ".join(cell(res["per_judge"][j]["contrasts"].get(k, {})) for j in res["judges_present"]) + " |")
    L += ["", "## Ladder count (judges per decision)", "", "| contrast | scope | resolved B>A / A>B / equivalent / unresolved / underpowered |", "|---|---|---|"]
    for k, c in res["ladder_counts"].items():
        L.append(f"| {k.split('|')[0]} | {k.split('|')[1]} | {c['resolved_second_gt_first']} / {c['resolved_first_gt_second']} / {c['equivalent']} / {c['unresolved']} / {c['underpowered']} (of {len(c['judges'])}) |")
    L += ["", "## Variant F contrasts (per judge)", ""]
    for j in res["judges_present"]:
        L.append(f"### {res['per_judge'][j]['label']}")
        for k, r in res["per_judge"][j]["contrasts"].items():
            if not k.startswith("A->B"):
                L.append(f"- {k}: {cell(r)}")
        L.append("")
    L += ["## Pairwise agreement with the other panel judges (QWK on per-cell median-low of repeats)", ""]
    for scope, ag in res["agreement_qwk"].items():
        L.append(f"**{scope}**")
        for k, v in ag.items():
            L.append(f"- {k}: n={v['n_cells']}, QWK {s5._f(v['qwk'])}, exact agreement {s5._f(v['exact_agreement'])}")
        L.append("")
    L += ["## Calls", ""] + [f"- {j}: " + json.dumps(res["per_judge"][j]["calls"]) for j in res["judges_present"]]
    return "\n".join(L) + "\n"


def tables(res: dict) -> str:
    L = ["% Addendum 36B: " + res["banner"], "% judge & contrast & scope & n & delta [95% BCa] & decision"]
    for j in res["judges_present"]:
        for k, r in res["per_judge"][j]["contrasts"].items():
            if "ci95" in r:
                c, sc = k.split("|")
                L.append(f"{res['per_judge'][j]['label']} & {c} & {sc.replace('_', ' ')} & {r['n_clusters']} & ${r['delta']:+.3f}$ [${r['ci95'][0]:+.2f}$, ${r['ci95'][1]:+.2f}$] & {r['verdict'].replace('_', ' ')} \\\\")
    L += ["", "% pairwise QWK: pair & cells & n & QWK"]
    for scope, ag in res["agreement_qwk"].items():
        for k, v in ag.items():
            L.append(f"{k.replace('~', ' vs ').replace('_', ' ')} & {scope.replace('_', ' ')} & {v['n_cells']} & {s5._f(v['qwk'])} \\\\")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    return {"extract": extract, "run": run}[a[0]]()


if __name__ == "__main__":
    raise SystemExit(main())
