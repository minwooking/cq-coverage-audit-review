#!/usr/bin/env python3
"""Build the subgraph views and cell manifests of Tiers 3a-3e (addendum 30, amendment A1).  AI-generated; review and test
before use.  NO model call.  Python + rdflib; reuses harness/length_experiment/make_inputs.build_subgraph_text and graph_view.

Method (the one of the length experiment): ego_graph around the nodes that match the QUESTION TEXT ONLY, rendered by the
same schema_view renderer on a temporary Turtle that holds only the subgraph.  A pair with no matching node or an empty
render is `not_applicable` and is listed, not rated.  Only the question (and its category / translation) is read from a
bank: no grounding, expected_answer or other column.

Output (inputs/ and the internal manifests are git-ignored; the Brick manifests are committed):
  inputs/<set>/<V>/<question id>/subgraph.txt
  manifests/<set>.json   {"set", "rows": [cell rows], "not_applicable": [...], "bank": {...sha256...}}
Cell row format = cells_manifest.json (cell_id, variant, cq_id, cluster_id, cat, catKo, q, qko, view_kind, view_path (relative
to paper/access2026), view_sha256, view_chars, est_input_tokens).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
REPO = ACCESS.parent.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "length_experiment"))
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
import graph_view as gv  # noqa: E402
import make_inputs as mi  # noqa: E402
import rater_luna as rl  # noqa: E402

BANK = ACCESS / "bank"
EVAL = REPO / "eval"
VARIANTS = HARNESS / "variants"
OUT_IN = HERE / "inputs"
OUT_MAN = HERE / "manifests"

BRICK_CAT_KO = {}  # filled from the primary manifest
INTERNAL = {"mfg", "mfgko"}


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Ctx:
    """Duck type of make_inputs.VariantContext for build_subgraph_text (needs .vg and .graph)."""

    def __init__(self, ttl: Path):
        from rdflib import Graph
        self.vg = gv.load_variant_ttl(ttl)
        self.graph = Graph().parse(str(ttl), format="turtle")
        self.ttl_sha256 = sha256_file(ttl)


def brick_cat_ko() -> dict:
    m = json.loads((HARNESS / "review6_raters" / "cells_manifest.json").read_text(encoding="utf-8"))
    return {c["cat"]: c["catKo"] for c in m["cells"]}


def read_csv(path: Path, keys: tuple[str, ...], skip_comments=False) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        lines = [l for l in fh if not (skip_comments and l.startswith("#"))]
    return [{k: r[k] for k in keys} for r in csv.DictReader(lines)]


def sets() -> dict:
    cat_ko = brick_cat_ko()
    v1 = read_csv(BANK / "cq_bank_brick_v1.csv", ("cq_id", "category", "question", "cluster_id"))
    v1cat = {r["cq_id"]: r["category"] for r in v1}
    v1q = {r["question"] for r in v1}
    brick_graph = lambda v: VARIANTS / v / f"graph_{v}.ttl"
    out = {}
    para = read_csv(BANK / "cq_bank_brick_v1_paraphrases.csv", ("cq_id", "paraphrase_text"))
    out["para"] = {"prefix": "para", "variants": "ABCDEF", "graph": brick_graph, "bank_files": ["cq_bank_brick_v1_paraphrases.csv"],
                   "questions": [{"id": r["cq_id"], "q": r["paraphrase_text"], "qko": "", "cat": v1cat[r["cq_id"]], "catKo": cat_ko[v1cat[r["cq_id"]]]} for r in para]}
    v2 = read_csv(BANK / "cq_bank_brick_v2.csv", ("cq_id", "category", "question"))
    out["v2x"] = {"prefix": "v2x", "variants": "ABCDEF", "graph": brick_graph, "bank_files": ["cq_bank_brick_v2.csv"],
                  "questions": [{"id": r["cq_id"], "q": r["question"], "qko": "", "cat": r["category"], "catKo": cat_ko[r["category"]]} for r in v2 if r["question"] not in v1q]}
    # development bank: the 18 distinct questions of the ext file (the base file's 16 are among them)
    d = json.loads((EVAL / "competency_questions_ext.json").read_text(encoding="utf-8"))
    dko = {c["id"]: c["ko"] for c in d["categories"]}
    out["dev"] = {"prefix": "dev", "variants": "ABCDEF", "graph": lambda v: REPO / "output" / f"ontology_{v}.ttl", "bank_files": ["../../../eval/competency_questions_ext.json"],
                  "questions": [{"id": q["id"], "q": q["question"], "qko": q.get("question_ko", ""), "cat": q["category"], "catKo": dko.get(q["category"], q["category"])} for q in d["questions"]]}
    for key, fn, ko in (("mfg", "competency_questions_mfg.json", False), ("mfgko", "competency_questions_mfg_ko.json", True)):
        m = json.loads((EVAL / fn).read_text(encoding="utf-8"))
        mko = {c["id"]: c["ko"] for c in m["categories"]}
        out[key] = {"prefix": key, "variants": "ABC", "graph": lambda v: REPO / "output_mfg" / f"ontology_{v}.ttl", "bank_files": [f"../../../eval/{fn}"],
                    "questions": [{"id": q["id"], "q": q["question"], "qko": ("" if ko else q.get("question_ko", "")), "cat": q["category"], "catKo": mko.get(q["category"], q["category"])} for q in m["questions"]]}
    ex = read_csv(BANK / "expansion_2026-10" / "cq_bank_brick_expansion_draft_v1.csv", ("cq_id", "category", "question"), skip_comments=True)
    out["exp"] = {"prefix": "exp", "variants": "ABCDEF", "graph": brick_graph, "bank_files": ["expansion_2026-10/cq_bank_brick_expansion_draft_v1.csv"],
                  "questions": [{"id": r["cq_id"], "q": r["question"], "qko": "", "cat": r["category"], "catKo": cat_ko[r["category"]]} for r in ex]}
    return out


def build(name: str, spec: dict) -> dict:
    rows, na = [], []
    for v in spec["variants"]:
        ttl = spec["graph"](v)
        ctx = Ctx(ttl)
        for q in spec["questions"]:
            text, roots, n_nodes = mi.build_subgraph_text(ctx, q["q"])
            cid = f"{spec['prefix']}:{v}:{q['id']}"
            if roots == 0 or not text.strip():
                na.append({"cell_id": cid, "reason": "no_matching_nodes" if roots == 0 else "empty_render"})
                continue
            p = OUT_IN / name / v / q["id"] / "subgraph.txt"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            cell = {"catKo": q["catKo"], "q": q["q"], "qko": q["qko"]}
            est = -(-(len(rl.RATER_PROMPT) + len(rl.user_message(text, cell))) // 4)
            rows.append({"cell_id": cid, "variant": v, "cq_id": q["id"], "cluster_id": q["id"], "cat": q["cat"], "catKo": q["catKo"],
                         "q": q["q"], "qko": q["qko"], "view_kind": "subgraph", "view_path": str(p.relative_to(ACCESS)),
                         "view_sha256": sha256_text(text), "view_chars": len(text), "est_input_tokens": est,
                         "matched_nodes": roots, "subgraph_nodes": n_nodes})
    return {"set": name, "n_questions": len(spec["questions"]), "variants": spec["variants"], "rows": sorted(rows, key=lambda r: r["cell_id"]),
            "not_applicable": na, "bank_files": spec["bank_files"]}


def main(argv=None) -> int:
    only = (argv or sys.argv[1:])
    OUT_MAN.mkdir(exist_ok=True)
    allsets = sets()
    summary = {}
    for name, spec in allsets.items():
        if only and name not in only:
            continue
        m = build(name, spec)
        (OUT_MAN / f"{name}.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[name] = {"questions": m["n_questions"], "variants": m["variants"], "cells": len(m["rows"]), "not_applicable": len(m["not_applicable"]),
                         "est_input_tokens": sum(r["est_input_tokens"] for r in m["rows"])}
        print(name, summary[name], flush=True)
    if not only:
        (OUT_MAN / "build_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
