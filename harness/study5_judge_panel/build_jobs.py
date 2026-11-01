#!/usr/bin/env python3
"""Addendum 36 Step 0/1: assemble the A/B panel cells and their judge jobs (no model call).  AI-generated; review and test before use.

  build_jobs.py  ->  cells_ab.json (structure, no text), existing_scores_{glm,gptoss}.csv (panel_id, repeat, J),
                     jobs_ab.jsonl (local only: contains view text)
Cells = every A/B cell of the Brick pool (addendum 34 A1: holdout, paraphrases, v2 extras, expansion) and of the three Study 4 domains that has
BOTH a GLM and a gpt-oss score (Brick: paired clusters as in addendum 34 A1; domains: every such cell, paired or not, because A->F and B->F need the unpaired ones).  Prompts are the original jobs (prompt_sha256 re-verified); nothing is re-worded.
"""
from __future__ import annotations

import csv
import json
import sys

import p5_common as C

sys.path.insert(0, str(C.S3))
import analyze_all as aa  # noqa: E402


def main() -> int:
    jobs_src = {}
    for name, p in (("r6", C.HARNESS / "review6_judges" / "jobs.jsonl"), ("s2", C.HARNESS / "study2_llm_labels" / "jobs_stage2.jsonl"),
                    ("s3", C.S3 / "jobs_new.jsonl")):
        jobs_src[name] = {j["cell_id"] + "@" + j["study"]: j for j in C.jsonl(p)}
    cell_src = {"holdout": ("r6", "holdout_subgraph", "primary"), "paraphrases": ("s3", "s3_para", "para"),
                "v2_extras": ("s3", "s3_v2x", "v2x"), "expansion": ("s2", "stage2", "primary")}
    banks = {j: aa.build_banks(j) for j in ("glm", "gptoss")}
    cells, jobs, existing = [], [], {"glm": [], "gptoss": []}
    raw = {"glm": {"r6": C.jsonl(aa.R6 / "raw_glm.jsonl"), "s2": C.jsonl(aa.S2 / "raw" / "judge_glm_stage2.jsonl"), "s3": C.jsonl(C.S3 / "raw" / "judge_glm_s3.jsonl")},
           "gptoss": {"r6": C.jsonl(aa.R6 / "raw_gptoss.jsonl"), "s2": C.jsonl(aa.S2 / "raw" / "judge_gptoss_stage2.jsonl"), "s3": C.jsonl(C.S3 / "raw" / "judge_gptoss_s3.jsonl")}}
    summary = {}
    for scope in C.BRICK_BANKS:
        src, study, pre = cell_src[scope]
        cl_g, cl_o = set(banks["glm"][scope]["bank"]), set(banks["gptoss"][scope]["bank"])
        both = sorted(cl_g & cl_o)
        summary[scope] = {"clusters_glm": len(cl_g), "clusters_gptoss": len(cl_o), "clusters_used": len(both)}
        for cq in both:
            for v in "AB":
                cid = f"{pre}:{v}:{cq}"
                job = jobs_src[src][cid + "@" + study]
                assert C.sha256_text(job["system"] + "\n\x00\n" + job["user"]) == job["prompt_sha256"], cid
                pid = C.panel_id(scope, cid)
                cells.append({"panel_id": pid, "scope": scope, "domain": "brick", "variant": v, "cq_id": cq, "cluster": cq})
                jobs.append({**job, "job_id": f"s5|{pid}", "study": f"s5_{scope}", "cell_id": pid})
                for j in ("glm", "gptoss"):
                    recs = [r for r in raw[j][src] if r["cell_id"] == cid and r.get("study") == study]
                    for r in recs:
                        if r.get("valid") and r.get("J") is not None:
                            existing[j].append((pid, r["repeat"], int(r["J"])))
    for d in C.DOMAINS:
        dj = {j["cell_id"]: j for j in C.jsonl(C.S4 / d / "jobs.jsonl")}
        sc = {j: C.read_scores_csv(C.S4 / d / f"scores_{j}.csv") for j in ("glm", "gptoss")}
        qs = sorted({j["cq_id"] for j in dj.values()})
        used = pairs = 0
        for cq in qs:
            ids = [f"primary:{v}:{cq}" for v in "AB"]
            have = [i for i in ids if i in dj and i in sc["glm"] and i in sc["gptoss"]]
            if not have:
                continue
            used += 1
            pairs += len(have) == 2
            for cid in have:
                v = cid.split(":")[1]
                job = dj[cid]
                assert C.sha256_text(job["system"] + "\n\x00\n" + job["user"]) == job["prompt_sha256"], cid
                pid = C.panel_id(d, cid)
                cells.append({"panel_id": pid, "scope": d, "domain": d, "variant": v, "cq_id": cq, "cluster": f"{d}:{cq}"})
                jobs.append({**job, "job_id": f"s5|{pid}", "study": f"s5_{d}", "cell_id": pid})
                for j in ("glm", "gptoss"):
                    for k, J in enumerate(sc[j][cid], 1):
                        existing[j].append((pid, k, J))
        summary[d] = {"questions_with_an_A_or_B_cell_scored_by_both_judges": used, "questions_with_both_A_and_B": pairs}
    (C.HERE / "cells_ab.json").write_text(json.dumps({"summary": summary, "cells": cells}, indent=1), encoding="utf-8")
    with (C.HERE / "jobs_ab.jsonl").open("w", encoding="utf-8") as fh:
        for j in jobs:
            fh.write(json.dumps(j, ensure_ascii=False) + "\n")
    for j, rows in existing.items():
        with (C.HERE / f"existing_scores_{j}.csv").open("w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["panel_id", "repeat", "J"])
            w.writerows(sorted(rows))
    print(json.dumps({"cells": len(cells), "jobs": len(jobs), "summary": summary, "existing_rows": {j: len(r) for j, r in existing.items()}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
