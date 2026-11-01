#!/usr/bin/env python3
"""Addendum 27 step 3b/4a: package variants A and B and generate the judge inputs.  Offline, no model.

AI-generated; review before reuse.  Mirrors harness/variants/package_variants.py (copy graph, render with the
registered run_simulated.schema_view, per-variant MANIFEST) and then calls the length experiment's own
make_inputs.generate (hop-2 ego sub-graph from the question text only) with variants_dir pointing here.

Output: variants/{A,B}/{graph_X.ttl,rendered_view.txt,MANIFEST.json}, variants/MANIFEST.json,
        inputs/{A,B}/<CQ>/subgraph.txt, inputs/manifest.jsonl, art_eligibility.json, artifacts.json
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parents[1]
HARNESS = ACCESS / "harness"
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "length_experiment"))

import run_holdout as rh  # noqa: E402
import make_inputs as mi  # noqa: E402

spec = importlib.util.spec_from_file_location("run_simulated", HARNESS / "run_simulated.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)
schema_view = rs.schema_view

WORK = HERE / "_work"
VARIANTS = HERE / "variants"
INPUTS = HERE / "inputs"
MODEL = "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"
SRC = {"A": WORK / "ontology_A.ttl", "B": WORK / "ontology_B.ttl"}
DESC = {"A": "Naive direct-LLM baseline: each atomic chunk rendered to Turtle section by section (chunktograph build-a).",
        "B": "Full structured pipeline: triple extraction, spaCy refinement, SKOS hierarchy, base-IRI unification, LLM typing (chunktograph triples/build/split)."}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    from rdflib import Graph, RDF, OWL, RDFS
    corpus = HERE / "corpus" / "natural_corpus.json"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    VARIANTS.mkdir(exist_ok=True)
    arts = {}
    views = {}
    for v, src in SRC.items():
        if not src.exists():
            raise SystemExit(f"missing graph for {v}: {src}")
        dest = VARIANTS / v
        dest.mkdir(parents=True, exist_ok=True)
        g_dest = dest / f"graph_{v}.ttl"
        shutil.copyfile(src, g_dest)
        view = schema_view(g_dest)
        v_dest = dest / "rendered_view.txt"
        v_dest.write_text(view, encoding="utf-8")
        views[v] = view
        g = Graph()
        g.parse(g_dest, format="turtle")
        info = {"variant_id": v, "description": DESC[v], "comparison_role": "exploratory addendum 27 (natural-document corpus)",
                "input_corpus": str(corpus.relative_to(ACCESS)), "input_corpus_sha256": sha(corpus),
                "model": MODEL, "endpoint_host": "<internal-host> via SSH tunnel (request-only)",
                "graph_file": g_dest.name, "graph_sha256": sha(g_dest),
                "rendered_view_file": v_dest.name, "rendered_view_sha256": sha(v_dest),
                "rendered_view_lines": view.count("\n") + (1 if view else 0), "rendered_view_chars": len(view),
                "rendering_spec_sha256": sha(ACCESS / "rubric" / "RENDERING_SPEC.md"),
                "triples": len(g),
                "owl_classes": len(set(g.subjects(RDF.type, OWL.Class)) | set(g.subjects(RDF.type, RDFS.Class))),
                "named_individuals": len(set(g.subjects(RDF.type, OWL.NamedIndividual))),
                "exploratory": True, "generated_utc": now,
                "note": "Addendum 27 exploratory artifact built from natural documentation; not a holdout result."}
        (dest / "MANIFEST.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        arts[v] = info
    (VARIANTS / "MANIFEST.json").write_text(json.dumps({"schema": "access2026-addendum27-variants/1", "generated_utc": now,
                                                        "variants": list(arts.values())}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    # judge inputs: same generator as the luna length experiment (question text only)
    bank_rows = list(csv.DictReader(rh.BANK_PATH.open(encoding="utf-8", newline=""))) if hasattr(rh, "BANK_PATH") else \
        list(csv.DictReader((ACCESS / "bank" / "cq_bank_brick_v1.csv").open(encoding="utf-8", newline="")))
    records = mi.generate(mi.BANK_PATH, INPUTS, ("A", "B"), VARIANTS, frozenset())
    INPUTS.mkdir(parents=True, exist_ok=True)
    with (INPUTS / "manifest.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    na = [r for r in records if r["status"] == "not_applicable"]
    # holdout artifact preflight per (variant, question): descriptive eligibility S_art (artifact text only)
    pre = {}
    for row in bank_rows:
        ok = {}
        for v in ("A", "B"):
            info = rh._grounding_match_info(views[v], row)
            ok[v] = {"missing_required_anchors": info["missing_required_grounding_anchors"],
                     "pass": not info["missing_required_grounding_anchors"]}
        pre[row["cq_id"]] = {**ok, "both": ok["A"]["pass"] and ok["B"]["pass"]}
    (HERE / "art_eligibility.json").write_text(json.dumps({"S_art": [c for c, x in pre.items() if x["both"]], "per_question": pre},
                                                          indent=1, ensure_ascii=False), encoding="utf-8")
    summ = {"variants": {v: {k: arts[v][k] for k in ("triples", "owl_classes", "named_individuals", "rendered_view_lines",
                                                     "rendered_view_chars", "graph_sha256", "rendered_view_sha256")} for v in arts},
            "subgraph_not_applicable": {v: [r["cq_id"] for r in na if r["variant"] == v] for v in ("A", "B")},
            "subgraph_chars": {v: sum(r["chars"] for r in records if r["variant"] == v and r["condition"] == "subgraph" and r["status"] == "ok")
                               for v in ("A", "B")},
            "manifest_sha256": sha(INPUTS / "manifest.jsonl"),
            "S_art_size": sum(1 for x in pre.values() if x["both"]),
            "preflight_pass_counts": {v: sum(1 for x in pre.values() if x[v]["pass"]) for v in ("A", "B")}}
    (HERE / "artifacts.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
