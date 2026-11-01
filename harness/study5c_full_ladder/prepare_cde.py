#!/usr/bin/env python3
"""Amendment C: package variants C, D, E of each domain (from the addendum 36 F build's work dir), build the question-only sub-graph views, apply the
paper's strict eligibility test on each variant's own full rendering, and write jobs_cde.jsonl (local only: contains view text), cells_cde.json and
<domain>/eligibility_cde.json (no text).  Generalisation of study5_judge_panel/prepare_f.py to a variant letter.  AI-generated; review before reuse.

  prepare_cde.py [<domain> ...]      offline, no model.  The bank's expected_answer is never read; its grounding is used for eligibility only.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone

import p5c_common as K

C = K.C
sys.path.insert(0, str(C.HARNESS))
sys.path.insert(0, str(C.HARNESS / "length_experiment"))
import run_holdout as rh  # noqa: E402
import make_inputs as mi  # noqa: E402

spec = importlib.util.spec_from_file_location("run_simulated", C.HARNESS / "run_simulated.py")
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def one(d: str) -> dict:
    from rdflib import Graph
    dd = K.HERE / d
    bank = C.S4 / d / "bank" / f"bank_{d}_v1.csv"
    freeze = json.loads((C.S4 / d / "bank_freeze.json").read_text(encoding="utf-8"))
    assert C.sha256_file(bank) == freeze["sha256"], "bank differs from its freeze hash"
    rows = list(csv.DictReader(bank.open(encoding="utf-8", newline="")))
    log = (K.S5 / d / "work" / "build_f.log").read_text(encoding="utf-8")
    for step in ("build-c", "refine-d", "build-d", "select-standards", "build-e", "build-f"):
        assert f"OK    {step}" in log, f"{d}: {step} not OK in the F build log"
    out = {"domain": d, "variants": {}}
    jobs, elig_all, view_for = [], {}, {}
    for v in K.NEW_VARIANTS:
        src = K.S5 / d / "work" / f"ontology_{v}.ttl"
        vdir = dd / "variants" / v
        vdir.mkdir(parents=True, exist_ok=True)
        gp = vdir / f"graph_{v}.ttl"
        shutil.copyfile(src, gp)
        view = rs.schema_view(gp)
        view_for[v] = view
        (vdir / "rendered_view.txt").write_text(view, encoding="utf-8")
        g = Graph().parse(gp, format="turtle")
        info = {"variant_id": v, "domain": d, "description": f"Variant {v} from the addendum 36 F build (same run and work directory as F).",
                "graph_sha256": C.sha256_file(gp), "rendered_view_sha256": C.sha256_file(vdir / "rendered_view.txt"), "rendered_view_chars": len(view),
                "triples": len(g), "input_corpus_sha256": C.sha256_file(C.S4 / d / "corpus" / "corpus.json"),
                "model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8", "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        (vdir / "MANIFEST.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    inputs = dd / "inputs"
    records = mi.generate(bank, inputs, K.NEW_VARIANTS, dd / "variants", frozenset())
    for v in K.NEW_VARIANTS:
        sub = {r["cq_id"]: r for r in records if r["condition"] == "subgraph" and r["variant"] == v}
        elig, nosub, n = {}, [], 0
        for row in rows:
            inf = rh._grounding_match_info(view_for[v], row)
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
            cid = f"primary:{v}:{row['cq_id']}"
            pid = C.panel_id(d, cid)
            jobs.append({"job_id": f"s5c|{pid}", "study": f"s5c_{d}_{v}", "cell_id": pid, "cell_kind": "primary", "variant": v, "cq_id": row["cq_id"],
                         "cluster_id": row["cq_id"], "category": row["category"], "view_kind": "subgraph", "view_chars": len(text),
                         "artifact_sha256": s["sha256"], "system": rh.RUBRIC, "user": user,
                         "prompt_sha256": C.sha256_text(rh.RUBRIC + "\n\x00\n" + user)})
            n += 1
        out["variants"][v] = {"n_questions": len(rows), "eligible": sum(x["eligible"] for x in elig.values()), "eligible_but_no_subgraph": nosub, "n_jobs": n,
                              "rendered_chars": len(view_for[v]), "graph_sha256": C.sha256_file(dd / "variants" / v / f"graph_{v}.ttl")}
        elig_all[v] = elig
    (dd / "eligibility_cde.json").write_text(json.dumps({"bank_sha256": freeze["sha256"], **out, "cells": elig_all}, indent=1), encoding="utf-8")
    return {"summary": out, "jobs": jobs}


def main(argv=None) -> int:
    ds = list(argv or sys.argv[1:]) or list(C.DOMAINS)
    allj, cells = [], []
    for d in ds:
        r = one(d)
        allj += r["jobs"]
        for j in r["jobs"]:
            cells.append({"panel_id": j["cell_id"], "scope": d, "domain": d, "variant": j["variant"], "cq_id": j["cq_id"], "cluster": f"{d}:{j['cq_id']}"})
        print(json.dumps(r["summary"]))
    with (K.HERE / "jobs_cde.jsonl").open("w", encoding="utf-8") as fh:
        for j in allj:
            fh.write(json.dumps(j, ensure_ascii=False) + "\n")
    (K.HERE / "cells_cde.json").write_text(json.dumps({"cells": cells}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
