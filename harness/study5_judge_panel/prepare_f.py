#!/usr/bin/env python3
"""Addendum 36 Step 2: package variant F of each domain, build the question-only sub-graph views, apply the paper's strict eligibility test on F's
full rendering, and write jobs_f.jsonl (local only: contains view text) and eligibility_f.json (no text).  AI-generated; review before reuse.

  prepare_f.py <domain> [<domain> ...]
Offline, no model.  Same code path as harness/study4_domains/prepare.py (rendering = run_simulated.schema_view; views = make_inputs.generate; strict rule =
run_holdout._grounding_match_info(...)["can_ablate"]).  The bank's expected_answer is never read; its grounding is used for the eligibility test only.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone

import p5_common as C

sys.path.insert(0, str(C.HARNESS))
sys.path.insert(0, str(C.HARNESS / "length_experiment"))
import run_holdout as rh  # noqa: E402
import make_inputs as mi  # noqa: E402

spec = importlib.util.spec_from_file_location("run_simulated", C.HARNESS / "run_simulated.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def one(d: str) -> dict:
    from rdflib import Graph
    dd = C.HERE / d
    bank = C.S4 / d / "bank" / f"bank_{d}_v1.csv"
    freeze = json.loads((C.S4 / d / "bank_freeze.json").read_text(encoding="utf-8"))
    assert C.sha256_file(bank) == freeze["sha256"], "bank differs from its freeze hash"
    rows = list(csv.DictReader(bank.open(encoding="utf-8", newline="")))
    src = dd / "work" / "ontology_F.ttl"
    if not src.exists():
        return {"domain": d, "built": False}
    vdir = dd / "variants" / "F"
    vdir.mkdir(parents=True, exist_ok=True)
    gp = vdir / "graph_F.ttl"
    shutil.copyfile(src, gp)
    view = rs.schema_view(gp)
    (vdir / "rendered_view.txt").write_text(view, encoding="utf-8")
    g = Graph().parse(gp, format="turtle")
    info = {"variant_id": "F", "description": "Full pipeline F (chunktograph build-f on the B-side triples, CQ file of the Brick build).", "domain": d,
            "graph_sha256": C.sha256_file(gp), "rendered_view_sha256": C.sha256_file(vdir / "rendered_view.txt"), "rendered_view_chars": len(view),
            "triples": len(g), "input_corpus_sha256": C.sha256_file(C.S4 / d / "corpus" / "corpus.json"),
            "model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8", "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (vdir / "MANIFEST.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    inputs = dd / "inputs"
    records = mi.generate(bank, inputs, ("F",), dd / "variants", frozenset())
    sub = {r["cq_id"]: r for r in records if r["condition"] == "subgraph"}
    elig, jobs, nosub = {}, [], []
    for row in rows:
        inf = rh._grounding_match_info(view, row)
        ok = bool(inf["can_ablate"])
        elig[row["cq_id"]] = {"eligible": ok, "missing_required": inf["missing_required_grounding_anchors"]}
        if not ok:
            continue
        s = sub.get(row["cq_id"])
        if s is None or s["status"] != "ok":
            nosub.append(row["cq_id"])
            continue
        text = (C.ACCESS / s["path"]).read_text(encoding="utf-8")
        assert C.sha256_text(text) == s["sha256"]
        user = f"ARTIFACT:\n{text}\n\nQUESTION: {row['question']}"
        cid = f"primary:F:{row['cq_id']}"
        pid = C.panel_id(d, cid)
        jobs.append({"job_id": f"s5|{pid}", "study": f"s5_{d}_F", "cell_id": pid, "cell_kind": "primary", "variant": "F", "cq_id": row["cq_id"],
                     "cluster_id": row["cq_id"], "category": row["category"], "view_kind": "subgraph", "view_chars": len(text),
                     "artifact_sha256": s["sha256"], "system": rh.RUBRIC, "user": user,
                     "prompt_sha256": C.sha256_text(rh.RUBRIC + "\n\x00\n" + user)})
    summ = {"domain": d, "built": True, "bank_sha256": freeze["sha256"], "n_questions": len(rows), "eligible_F": sum(v["eligible"] for v in elig.values()),
            "eligible_but_no_subgraph": nosub, "n_jobs": len(jobs), "F_triples": len(g), "F_rendered_chars": len(view),
            "graph_sha256": info["graph_sha256"], "rendered_view_sha256": info["rendered_view_sha256"], "cells": elig}
    (dd / "eligibility_f.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    return {"summary": summ, "jobs": jobs}


def main(argv=None) -> int:
    ds = list(argv or sys.argv[1:]) or list(C.DOMAINS)
    allj, cells = [], []
    for d in ds:
        r = one(d)
        if not r.get("summary"):
            print(json.dumps(r))
            continue
        allj += r["jobs"]
        for j in r["jobs"]:
            cells.append({"panel_id": j["cell_id"], "scope": d, "domain": d, "variant": "F", "cq_id": j["cq_id"], "cluster": f"{d}:{j['cq_id']}"})
        print(json.dumps({k: v for k, v in r["summary"].items() if k != "cells"}))
    with (C.HERE / "jobs_f.jsonl").open("w", encoding="utf-8") as fh:
        for j in allj:
            fh.write(json.dumps(j, ensure_ascii=False) + "\n")
    (C.HERE / "cells_f.json").write_text(json.dumps({"cells": cells}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
