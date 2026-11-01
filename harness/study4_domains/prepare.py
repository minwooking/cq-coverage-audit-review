#!/usr/bin/env python3
"""Package variants A/B of one domain, build the judge inputs and the job list (addendum 35 PLAN 35.5-35.6).  AI-generated; review before reuse.

  prepare.py <domain>  -> <d>/variants/{A,B}/{graph_X.ttl,rendered_view.txt,MANIFEST.json}, <d>/inputs/{A,B}/<CQ>/subgraph.txt, <d>/inputs/manifest.jsonl,
                          <d>/eligibility.json, <d>/jobs.jsonl
Offline, no model.  The bank's grounding is used only for the paper's strict eligibility test on the full rendering; the subgraph is built from the
question text only (make_inputs leak guard).  The bank's expected_answer is never read.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone

import s4_common as C

sys.path.insert(0, str(C.HARNESS))
sys.path.insert(0, str(C.HARNESS / "length_experiment"))
import run_holdout as rh  # noqa: E402
import make_inputs as mi  # noqa: E402

spec = importlib.util.spec_from_file_location("run_simulated", C.HARNESS / "run_simulated.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

DESC = {"A": "Naive direct-LLM baseline (chunktograph build-a).",
        "B": "Pipeline base build: triples, refinement, SKOS hierarchy, base-IRI unification, LLM typing (chunktograph triples/build/split)."}


def main(argv=None) -> int:
    from rdflib import Graph
    d = (argv or sys.argv[1:])[0]
    dd = C.ddir(d)
    work, variants, inputs = dd / "work", dd / "variants", dd / "inputs"
    bank = dd / "bank" / f"bank_{d}_v1.csv"
    freeze = json.loads((dd / "bank_freeze.json").read_text(encoding="utf-8"))
    assert C.sha256_file(bank) == freeze["sha256"], "bank differs from its freeze hash"
    rows = list(csv.DictReader(bank.open(encoding="utf-8", newline="")))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    views, infos = {}, {}
    for v in "AB":
        src = work / f"ontology_{v}.ttl"
        if not src.exists():
            raise SystemExit(f"missing {src}")
        (variants / v).mkdir(parents=True, exist_ok=True)
        gp = variants / v / f"graph_{v}.ttl"
        shutil.copyfile(src, gp)
        view = rs.schema_view(gp)
        vp = variants / v / "rendered_view.txt"
        vp.write_text(view, encoding="utf-8")
        views[v] = view
        g = Graph().parse(gp, format="turtle")
        infos[v] = {"variant_id": v, "description": DESC[v], "domain": d, "graph_sha256": C.sha256_file(gp), "rendered_view_sha256": C.sha256_file(vp),
                    "rendered_view_chars": len(view), "rendered_view_lines": view.count("\n") + 1, "triples": len(g),
                    "input_corpus_sha256": C.sha256_file(dd / "corpus" / "corpus.json"), "model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8",
                    "extractor_note": "same model id as the paper; serving container differs (PLAN 35.5)", "generated_utc": now}
        (variants / v / "MANIFEST.json").write_text(json.dumps(infos[v], indent=2), encoding="utf-8")
    records = mi.generate(bank, inputs, ("A", "B"), variants, frozenset())
    with (inputs / "manifest.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    sub = {(r["variant"], r["cq_id"]): r for r in records if r["condition"] == "subgraph"}
    elig, jobs, nosub = {}, [], []
    for row in rows:
        for v in "AB":
            info = rh._grounding_match_info(views[v], row)
            ok = bool(info["can_ablate"])
            elig[f"primary:{v}:{row['cq_id']}"] = {"variant": v, "cq_id": row["cq_id"], "eligible": ok,
                                                   "missing_required": info["missing_required_grounding_anchors"]}
            if not ok:
                continue
            s = sub.get((v, row["cq_id"]))
            if s is None or s["status"] != "ok":
                nosub.append(f"primary:{v}:{row['cq_id']}")
                continue
            view = (C.ACCESS / s["path"] if not str(s["path"]).startswith("/") else __import__("pathlib").Path(s["path"])).read_text(encoding="utf-8")
            assert C.sha256_text(view) == s["sha256"]
            user = f"ARTIFACT:\n{view}\n\nQUESTION: {row['question']}"
            jobs.append({"job_id": f"s4|{d}|{v}|{row['cq_id']}", "study": f"study4_{d}", "cell_id": f"primary:{v}:{row['cq_id']}", "cell_kind": "primary",
                         "variant": v, "cq_id": row["cq_id"], "cluster_id": row["cq_id"], "category": row["category"], "view_kind": "subgraph",
                         "view_chars": len(view), "artifact_sha256": s["sha256"], "system": rh.RUBRIC, "user": user,
                         "prompt_sha256": C.sha256_text(rh.RUBRIC + "\n\x00\n" + user)})
    with (dd / "jobs.jsonl").open("w", encoding="utf-8") as fh:
        for j in jobs:
            fh.write(json.dumps(j, ensure_ascii=False) + "\n")
    both = sorted({r["cq_id"] for r in rows if elig[f"primary:A:{r['cq_id']}"]["eligible"] and elig[f"primary:B:{r['cq_id']}"]["eligible"]})
    summ = {"domain": d, "bank_sha256": freeze["sha256"], "n_questions": len(rows),
            "eligible_cells": {v: sum(1 for x in elig.values() if x["variant"] == v and x["eligible"]) for v in "AB"},
            "eligible_clusters_A_or_B": len({x["cq_id"] for x in elig.values() if x["eligible"]}),
            "eligible_clusters_A_and_B": len(both), "eligible_in_both": both,
            "eligible_but_no_subgraph": nosub, "n_jobs": len(jobs),
            "variants": {v: {k: infos[v][k] for k in ("triples", "rendered_view_chars", "graph_sha256", "rendered_view_sha256")} for v in "AB"},
            "jobs_sha256": C.sha256_file(dd / "jobs.jsonl"), "inputs_manifest_sha256": C.sha256_file(inputs / "manifest.jsonl"),
            "cells": elig}
    (dd / "eligibility.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summ.items() if k not in ("cells", "eligible_in_both")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
