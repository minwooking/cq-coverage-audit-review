#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C4.)
"""Question-only subgraph views, view manifest and judgeable-pair sets for bank b1 (addendum 47.4/47.5).

Input: eligibility_b1.json (output of eligibility.py), the frozen bank (columns cq_id, category,
question ONLY -- grounding and expected_answer never reach the view builder), and the graphs
graph_A.ttl / graph_B.ttl.  Views for ELIGIBLE cells are built by importing addendum 30's builder
(build_views.build + make_inputs.build_subgraph_text); nothing in this file re-implements it.
Pure local computation: no model call, no network.

Writes (bank/eqv2_2026-10/):
  inputs/b1/<V>/<cq_id>/subgraph.txt   view files (git-ignored, see .gitignore there)
  view_manifest_b1.jsonl               one line per cell: view status, repo-relative path, view sha256
  pairs_b1.json                        judgeable pairs, floor set, exclusion counts
  C4_REPORT.md                         aggregate tables (English)
  BATCH2_SIZE.json                     only when K1 < 210 (formula of 47.3 'Batch 2')

Determinism: no randomness anywhere; cells, rows and ids are sorted; the builder's own ordering is
checked by repeating the run (see C4_REPORT.md).

Usage:  python views.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
BANK_DIR = TOOLS.parent
ACCESS = BANK_DIR.parent.parent
HARNESS = ACCESS / "harness"

sys.path.insert(0, str(TOOLS))
import eligibility as el  # noqa: E402  (same directory; hashes and bank loader reused)

GRAPH = {"A": HARNESS / "variants" / "A" / "graph_A.ttl", "B": HARNESS / "variants" / "B" / "graph_B.ttl"}
GRAPH_SHA256 = {"A": "1a5cc075065ac1f493e7731ac20e638481754c1a79f586b6e82a25320cb1bc32",
                "B": "20d015a83b1158fdf1bc598b75127f63eed088f0a10bc54e91d88d411b4fe490"}
BUILD_VIEWS = HARNESS / "review10_llm_labels" / "build_views.py"
BUILD_VIEWS_SHA256 = "732d42167f6725321eb072a8e28f9a56271f9d2bde1904d5bb372dab7937c007"
MAKE_INPUTS = HARNESS / "length_experiment" / "make_inputs.py"
MAKE_INPUTS_SHA256 = "585c7e37ea5f2504ab17e0dc55847b708f8b30ec01628962f4768cdf500d1f99"
ELIG_JSON = BANK_DIR / "eligibility_b1.json"
INPUTS_DIR = BANK_DIR / "inputs"
SET_NAME = "b1"
# Column filter (47.4): ONLY these bank columns are read by this tool.
BANK_COLUMNS = ("cq_id", "category", "question")
FORBIDDEN_COLUMNS = ("grounding", "expected_answer")
VARIANTS = el.VARIANTS
TARGET_PAIRS = 210
Q_CAP = 504
MARGIN = 1.15
REF_YIELD = "26/84"


def load_questions(path: Path = el.BANK_CSV, expect_sha: str | None = el.BANK_SHA256) -> list[dict]:
    return el.load_bank(path, BANK_COLUMNS, expect_sha)


def import_builder():
    for p, h in ((BUILD_VIEWS, BUILD_VIEWS_SHA256), (MAKE_INPUTS, MAKE_INPUTS_SHA256)):
        got = el.sha256_file(p)
        if got != h:
            raise SystemExit(f"{p.name} sha256 mismatch: {got}")
    sys.path.insert(0, str(HARNESS))
    sys.path.insert(0, str(HARNESS / "length_experiment"))
    sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
    sys.path.insert(0, str(BUILD_VIEWS.parent))
    import build_views as bv  # noqa: E402
    return bv


def check_graphs() -> None:
    for v in VARIANTS:
        got = el.sha256_file(GRAPH[v])
        if got != GRAPH_SHA256[v]:
            raise SystemExit(f"graph {v} sha256 mismatch: {got}")


def view_status(row: dict | None, na_reason: str | None) -> str:
    """ok | no_matching_nodes | empty_render (built cells); ineligible cells are never built."""
    if row is not None:
        return "ok"
    return na_reason or "empty_render"


def build_cells(questions: list[dict], elig_cells: list[dict], bv, out_dir: Path, graph_for) -> list[dict]:
    """Manifest entries for all cells.  Builds views only for eligible cells (via bv.build)."""
    qtext = {q["cq_id"]: q for q in questions}
    bv.OUT_IN = out_dir  # builder writes <OUT_IN>/<set>/<V>/<id>/subgraph.txt
    manifest: list[dict] = []
    for v in VARIANTS:
        vcells = sorted((c for c in elig_cells if c["variant"] == v), key=lambda c: c["cq_id"])
        elig_ids = [c["cq_id"] for c in vcells if c["can_ablate"]]
        spec = {"prefix": "eqv2b1", "variants": v, "graph": lambda x: graph_for(x), "bank_files": [el.BANK_CSV.name],
                "questions": [{"id": i, "q": qtext[i]["question"], "qko": "", "cat": qtext[i]["category"],
                               "catKo": qtext[i]["category"]} for i in elig_ids]}
        built = bv.build(SET_NAME, spec) if elig_ids else {"rows": [], "not_applicable": []}
        by_id = {r["cq_id"]: r for r in built["rows"]}
        na = {n["cell_id"].split(":", 2)[2]: n["reason"] for n in built["not_applicable"]}
        for c in vcells:
            base = {"cell_id": c["cell_id"], "variant": v, "cq_id": c["cq_id"], "category": c["category"],
                    "can_ablate": c["can_ablate"], "eligibility_reason": c["reason"]}
            if not c["can_ablate"]:
                manifest.append({**base, "view_status": "not_built_ineligible", "view_path": None,
                                 "view_sha256": None, "view_chars": None})
                continue
            r = by_id.get(c["cq_id"])
            st = view_status(r, na.get(c["cq_id"]))
            manifest.append({**base, "view_status": st,
                             "view_path": r["view_path"] if r else None,
                             "view_sha256": r["view_sha256"] if r else None,
                             "view_chars": r["view_chars"] if r else None,
                             "matched_nodes": r["matched_nodes"] if r else 0,
                             "subgraph_nodes": r["subgraph_nodes"] if r else 0})
    return sorted(manifest, key=lambda m: (m["variant"], m["cq_id"]))


def judgeable(m: dict) -> bool:
    return bool(m["can_ablate"]) and m["view_status"] == "ok"


def pair_sets(manifest: list[dict], all_ids: list[str], category: dict[str, str]) -> dict:
    cell = {(m["variant"], m["cq_id"]): m for m in manifest}
    pairs, floor, excl = [], [], Counter()
    per_item = {}
    for i in sorted(all_ids):
        a, b = cell[("A", i)], cell[("B", i)]
        ja, jb = judgeable(a), judgeable(b)
        if ja and jb:
            pairs.append(i)
        elif ja != jb:
            floor.append(i)
        if not (ja and jb):
            def why(m):
                return "judgeable" if judgeable(m) else (m["eligibility_reason"] if not m["can_ablate"] else m["view_status"])
            excl[f"A {why(a)} / B {why(b)}"] += 1
        per_item[i] = (ja, jb)
    cats = sorted(set(category.values()))
    by_cat = {}
    for k in cats:
        ids = [i for i in all_ids if category[i] == k]
        by_cat[k] = {"n": len(ids), "pairs": sum(1 for i in ids if i in set(pairs)),
                     "a_eligible": sum(1 for i in ids if cell[("A", i)]["can_ablate"]),
                     "b_eligible": sum(1 for i in ids if cell[("B", i)]["can_ablate"]),
                     "both_eligible": sum(1 for i in ids if cell[("A", i)]["can_ablate"] and cell[("B", i)]["can_ablate"]),
                     "floor": sum(1 for i in ids if i in set(floor))}
    return {"pairs": pairs, "floor_set": floor,
            "exclusion_reasons": dict(sorted(excl.items())), "by_category": by_cat}


def batch2_size(k1: int, n1: int, target: int = TARGET_PAIRS) -> dict:
    """47.3 'Batch 2': N2 = min(504, 6*ceil((target-K1)/y1 * 1.15 / 6)); y1 = K1/N1; y1 = 0 gives 504."""
    y1 = k1 / n1
    if k1 >= target:
        return {"needed": False, "K1": k1, "N1": n1, "y1": y1}
    n2 = Q_CAP if y1 == 0 else min(Q_CAP, 6 * math.ceil((target - k1) / y1 * MARGIN / 6))
    return {"needed": True, "K1": k1, "N1": n1, "y1": y1, "target": target, "margin": MARGIN, "N2": n2}


def aggregates(manifest: list[dict], ps: dict, n1: int) -> dict:
    out: dict = {"n_questions": n1}
    for v in VARIANTS:
        vm = [m for m in manifest if m["variant"] == v]
        out[f"{v}_eligible"] = sum(m["can_ablate"] for m in vm)
        out[f"{v}_eligible_no_view"] = sum(1 for m in vm if m["can_ablate"] and m["view_status"] != "ok")
        out[f"{v}_view_status"] = dict(sorted(Counter(m["view_status"] for m in vm).items()))
        out[f"{v}_eligibility_reasons"] = dict(sorted(Counter(m["eligibility_reason"] for m in vm).items()))
    out["K1"] = len(ps["pairs"])
    out["floor_size"] = len(ps["floor_set"])
    out["y1"] = out["K1"] / n1
    out["K1_ge_210"] = out["K1"] >= TARGET_PAIRS
    return out


def report_md(agg: dict, ps: dict, b2: dict) -> str:
    L = ["# C4 report: eligibility and judgeable pairs, bank b1 (addendum 47.4; plan-based, exploratory)", "",
         "> AI-generated draft: a person must review and test the code and these numbers before use. Structure only:",
         "> no model or judge call, no judge score; eligibility is the paper's rule applied to the full renderings,",
         "> views are question-only subgraphs built by addendum 30's builder.", "",
         "## Headline", "", "| quantity | value |", "|---|---|",
         f"| bank rows N1 | {agg['n_questions']} |",
         f"| A eligible (can_ablate on full A) | {agg['A_eligible']} |",
         f"| B eligible (can_ablate on full B) | {agg['B_eligible']} |",
         f"| judgeable pairs K1 (A and B eligible, both views non-empty) | {agg['K1']} |",
         f"| floor set (judgeable in exactly one of A, B) | {agg['floor_size']} |",
         f"| eligible cells with no view, A / B | {agg['A_eligible_no_view']} / {agg['B_eligible_no_view']} |",
         f"| pair yield y1 = K1/N1 | {agg['y1']:.4f} (expansion bank {REF_YIELD} = {26/84:.4f}) |",
         f"| K1 >= {TARGET_PAIRS} | {'yes' if agg['K1_ge_210'] else 'no'} |", "",
         "## By category", "",
         "| category | rows | A elig. (rate) | B elig. (rate) | both elig. | pairs | pair yield | floor |", "|---|---|---|---|---|---|---|---|"]
    for k, d in ps["by_category"].items():
        L.append(f"| {k} | {d['n']} | {d['a_eligible']} ({d['a_eligible'] / max(d['n'], 1):.2f}) | {d['b_eligible']} ({d['b_eligible'] / max(d['n'], 1):.2f}) | {d['both_eligible']} | {d['pairs']} | "
                 f"{(d['pairs'] / d['n'] if d['n'] else 0):.3f} | {d['floor']} |")
    L += ["", "Rate = eligible / rows.", "", "## Reasons per variant", "",
          "| variant | eligibility reason | cells |", "|---|---|---|"]
    for v in VARIANTS:
        for r, n in agg[f"{v}_eligibility_reasons"].items():
            L.append(f"| {v} | {r} | {n} |")
    L += ["", "## View status per variant (eligible cells are built; ineligible cells are not)", "",
          "| variant | view status | cells |", "|---|---|---|"]
    for v in VARIANTS:
        for r, n in agg[f"{v}_view_status"].items():
            L.append(f"| {v} | {r} | {n} |")
    L += ["", "## Items outside the pair set, by (A, B) cause", "", "| cause | items |", "|---|---|"]
    for r, n in ps["exclusion_reasons"].items():
        L.append(f"| {r} | {n} |")
    L += ["", "## Batch 2 size (47.3)", ""]
    if b2["needed"]:
        L.append(f"K1 < {TARGET_PAIRS}: N2 = min({Q_CAP}, 6 * ceil(({TARGET_PAIRS} - {b2['K1']}) / {b2['y1']:.6f} * {MARGIN} / 6)) = **{b2['N2']}**. "
                 "Recorded in `BATCH2_SIZE.json`. No b2 drafting or call was made; that needs the author's approval.")
    else:
        L.append("K1 meets the target; batch 2 is not needed.")
    L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--inputs-dir", type=Path, default=INPUTS_DIR)
    args = ap.parse_args(argv)
    check_graphs()
    bv = import_builder()
    doc = json.loads(ELIG_JSON.read_text(encoding="utf-8"))
    if doc["inputs"]["bank_sha256"] != el.BANK_SHA256:
        raise SystemExit("eligibility_b1.json was computed on another bank")
    questions = load_questions()
    manifest = build_cells(questions, doc["cells"], bv, args.inputs_dir, lambda v: GRAPH[v])
    for m in manifest:
        if m["view_path"]:  # repository-relative to paper/access2026, never absolute
            m["view_path"] = m["view_path"] if not Path(m["view_path"]).is_absolute() else str(Path(m["view_path"]).relative_to(ACCESS))
    ids = [q["cq_id"] for q in questions]
    cat = {q["cq_id"]: q["category"] for q in questions}
    ps = pair_sets(manifest, ids, cat)
    agg = aggregates(manifest, ps, len(ids))
    b2 = batch2_size(agg["K1"], len(ids))
    with (BANK_DIR / "view_manifest_b1.jsonl").open("w", encoding="utf-8") as fh:
        for m in manifest:
            fh.write(json.dumps(m, ensure_ascii=False, sort_keys=True) + "\n")
    (BANK_DIR / "pairs_b1.json").write_text(json.dumps({"aggregates": agg, **ps}, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (BANK_DIR / "C4_REPORT.md").write_text(report_md(agg, ps, b2), encoding="utf-8")
    b2p = BANK_DIR / "BATCH2_SIZE.json"
    if b2["needed"]:
        b2p.write_text(json.dumps(b2, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"K1={agg['K1']} floor={agg['floor_size']} A_elig={agg['A_eligible']} B_elig={agg['B_eligible']} N2={b2.get('N2')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
