#!/usr/bin/env python3
"""Build the frozen job lists of addendum 37 (study6_rescoring).  NO network call.  AI-generated draft; review and test before use.

jobs_A.jsonl  development study, 96 cells x arms: A_hint (original dev prompt, byte-identical), A_nohint (the same prompt with ONLY the
              "What a good answer needs:" line removed), A_holdout (holdout system prompt + ARTIFACT/QUESTION user message, no ontology letter,
              no question id/category, no hint).
jobs_L.jsonl  holdout, 188 primary cells, the registered 60,000-character truncated view (length_experiment limited.txt, sha256 checked
              against the manifest), registered holdout prompt.  Sub-study B uses the 48-cell subset, sub-study C all 188.
No full-view job exists: every full view exceeds the 65,536-token window (fit_full_preflight.json).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent

spec = importlib.util.spec_from_file_location("bj26", HARNESS / "review6_judges" / "build_jobs.py")
bj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bj)
rh = bj.rh

LIST48 = HARNESS / "real_run" / "second_annotator" / "cell_list_48.txt"


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def main() -> int:
    judge_system, rubric1 = bj.dev_prompt_parts()
    ev = json.loads(bj.DEV_EVAL.read_text(encoding="utf-8"))
    cqs = json.loads(bj.DEV_CQ.read_text(encoding="utf-8"))["questions"]
    assert len(cqs) == 16
    jobs = []
    for v in "ABCDEF":
        summary = ev["summaries"][v]
        for cq in cqs:
            full = bj.dev_user_message(rubric1, cq, v, summary)
            hint_line = f"What a good answer needs: {cq.get('needs', '')}\n"
            assert full.count(hint_line) == 1
            nohint = full.replace(hint_line, "", 1)
            assert len(full) - len(nohint) == len(hint_line)
            arms = {
                "A_hint": (judge_system, full),
                "A_nohint": (judge_system, nohint),
                "A_holdout": (bj.rh.RUBRIC, bj.holdout_user_message(summary, cq["question"])),
            }
            for arm, (s, u) in arms.items():
                jobs.append({"job_id": f"{arm}|dev:{v}:{cq['id']}", "study": arm, "cell_id": f"{arm}|dev:{v}:{cq['id']}",
                             "cell_kind": "primary", "variant": v, "cq_id": cq["id"], "cluster_id": cq["id"],
                             "category": cq["category"], "view_kind": "dev_summary", "view_chars": len(summary),
                             "artifact_sha256": sha(summary), "system": s, "user": u, "prompt_sha256": bj.prompt_sha(s, u)})
    (HERE / "jobs_A.jsonl").write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in jobs), encoding="utf-8")
    nA = len(jobs)

    manifest = [json.loads(l) for l in bj.MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    if bj.sha256_file(bj.MANIFEST) != bj.EXPECTED_MANIFEST_SHA256:
        raise SystemExit("manifest sha differs")
    lim = {(r["variant"], r["cq_id"]): r for r in manifest if r["condition"] == "limited"}
    rows, digests = rh.verify_frozen(bj.BANK)
    bank = {r["cq_id"]: r for r in rows}
    holdout = [json.loads(l) for l in bj.HOLDOUT_CELLS.read_text(encoding="utf-8").splitlines() if l.strip()]
    prim = sorted((c["variant"], c["cq_id"]) for c in holdout if c["cell_kind"] == "primary")
    assert len(prim) == 188
    l48 = {l.strip() for l in LIST48.read_text().splitlines() if l.strip()}
    assert len(l48) == 48
    Ljobs = []
    for v, cq in prim:
        r = lim[(v, cq)]
        assert r["status"] == "ok", (v, cq, r["status"])
        text = (ACCESS / r["path"]).read_text(encoding="utf-8")
        assert sha(text) == r["sha256"]
        cid = f"primary:{v}:{cq}"
        u = bj.holdout_user_message(text, bank[cq]["question"])
        Ljobs.append({"job_id": f"L|{cid}", "study": "L_limited", "cell_id": cid, "cell_kind": "primary", "variant": v,
                      "cq_id": cq, "cluster_id": bank[cq]["cluster_id"], "category": bank[cq]["category"],
                      "view_kind": "limited_60000", "in_cell_list_48": cid in l48, "view_chars": len(text),
                      "artifact_sha256": sha(text), "system": rh.RUBRIC, "user": u, "prompt_sha256": bj.prompt_sha(rh.RUBRIC, u)})
    assert sum(j["in_cell_list_48"] for j in Ljobs) == 48
    (HERE / "jobs_L.jsonl").write_text("".join(json.dumps(j, ensure_ascii=False) + "\n" for j in Ljobs), encoding="utf-8")
    meta = {"n_A": nA, "n_L": len(Ljobs), "n_L_in_48": 48,
            "jobs_A_sha256": hashlib.sha256((HERE / "jobs_A.jsonl").read_bytes()).hexdigest(),
            "jobs_L_sha256": hashlib.sha256((HERE / "jobs_L.jsonl").read_bytes()).hexdigest(),
            "holdout_rubric_sha256": sha(rh.RUBRIC), "dev_judge_system_sha256": sha(judge_system),
            "dev_layer1_rubric_sha256": sha(rubric1), "manifest_sha256": bj.EXPECTED_MANIFEST_SHA256,
            "build_jobs_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (HERE / "jobs_meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
