#!/usr/bin/env python3
"""Build the frozen job list for the non-Qwen judge runs (addendum 26, exploratory).

AI-generated draft; the author must review and test it before the output is used.

Makes NO network call.  Writes ``jobs.jsonl`` (one record per scoring cell; the 3 repeats and the
two judges are expanded by ``score_judges.py``).  Three studies:

* ``holdout_subgraph``  primary Brick holdout cells (the 188 primary cells minus the 6 cells that have
  no subgraph), view = the question-relevant subgraph text that the length experiment (addenda 17, 23)
  and addendum 25 used.  Prompt = the registered holdout judge prompt (run_holdout.RUBRIC, user message
  ``ARTIFACT:\\n{view}\\n\\nQUESTION: {q}``), unchanged.
* ``holdout_control``   the 36 registered controls (24 ablated, 12 preserved) re-built on the SUBGRAPH
  text with the registered functions (``ablate_rendered_view``, paraphrase file).  New construction;
  the luna subgraph run (addendum 25) had no controls.
* ``dev``               Ontology-101 development study: 16 questions x 6 variants, the development
  judge prompt of ``src/chunktograph/eval_ab.py`` (``JUDGE_SYSTEM``, ``LAYER1_RUBRIC``, ``judge_cq`` user
  message with the ``needs`` hint) over the stored judge-facing summaries of
  ``output/abcdef_evaluation.json``.

Nothing from labels, the judge scores, the expected answers or variant names is put in a prompt.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
REPO = ACCESS.parent.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "length_experiment"))

import run_holdout as rh  # noqa: E402

MANIFEST = HARNESS / "length_experiment" / "inputs" / "manifest.jsonl"
EXPECTED_MANIFEST_SHA256 = "46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32"
HOLDOUT_CELLS = HARNESS / "real_run" / "cells.jsonl"
BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"
DEV_EVAL = REPO / "output" / "abcdef_evaluation.json"
DEV_CQ = REPO / "eval" / "competency_questions.json"
DEV_SRC = REPO / "src" / "chunktograph"
OUT = HERE / "jobs.jsonl"
SKIPS = HERE / "jobs_build_skips.json"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prompt_sha(system: str, user: str) -> str:
    return sha256_text(system + "\n\x00\n" + user)


def dev_prompt_parts():
    """Import the development judge prompt constants WITHOUT importing the package (it needs openai/rdflib)."""
    sys.path.insert(0, str(REPO / "src"))
    try:
        from chunktograph import eval_ab  # type: ignore
    finally:
        sys.path.pop(0)
    return eval_ab.JUDGE_SYSTEM, eval_ab.LAYER1_RUBRIC


def dev_user_message(layer1_rubric: str, cq: dict, ontology: str, summary: str) -> str:
    """Byte-for-byte the f-string of eval_ab.judge_cq."""
    return (
        f"{layer1_rubric}\n"
        f"COMPETENCY QUESTION ({cq['id']}, category={cq['category']}):\n{cq['question']}\n"
        f"What a good answer needs: {cq.get('needs', '')}\n\n"
        f"ONTOLOGY {ontology} SUMMARY:\n{summary}\n\n"
        'Return JSON exactly: {"score": 0..3, "evidence": ["IRI or triple ..."], "reasoning": "..."}'
    )


def holdout_user_message(artifact: str, question: str) -> str:
    """Same as run_holdout.call_judge."""
    return f"ARTIFACT:\n{artifact}\n\nQUESTION: {question}"


def build() -> tuple[list[dict], dict]:
    skips: dict = {"holdout_subgraph": [], "holdout_control": [], "dev": []}
    manifest_sha = sha256_file(MANIFEST)
    if manifest_sha != EXPECTED_MANIFEST_SHA256:
        raise SystemExit(f"manifest sha256 differs: {manifest_sha}")
    rows, digests = rh.verify_frozen(BANK)
    bank = {r["cq_id"]: r for r in rows}
    manifest = [json.loads(line) for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    sub_rows = {(r["variant"], r["cq_id"]): r for r in manifest if r["condition"] == "subgraph"}

    holdout = [json.loads(line) for line in HOLDOUT_CELLS.read_text(encoding="utf-8").splitlines() if line.strip()]
    primary_keys = [(c["variant"], c["cq_id"]) for c in holdout if c["cell_kind"] == "primary"]
    assert len(primary_keys) == 188 and len(set(primary_keys)) == 188

    jobs: list[dict] = []
    rubric = rh.RUBRIC

    def read_subgraph(key):
        r = sub_rows.get(key)
        if r is None or r["status"] != "ok":
            return None, r
        path = ACCESS / r["path"]
        text = path.read_text(encoding="utf-8")
        if sha256_text(text) != r["sha256"]:
            raise SystemExit(f"subgraph sha256 differs from manifest: {r['path']}")
        return text, r

    # ---- (a) holdout primary, subgraph view ----------------------------------------------
    for key in sorted(primary_keys):
        v, cq = key
        text, r = read_subgraph(key)
        cell_id = f"primary:{v}:{cq}"
        if text is None:
            skips["holdout_subgraph"].append({"cell_id": cell_id, "reason": "no subgraph (not_applicable); "
                                              "the full-view fallback does not fit a 65,536-token window"})
            continue
        q = bank[cq]["question"]
        user = holdout_user_message(text, q)
        jobs.append({
            "job_id": f"hs|{cell_id}", "study": "holdout_subgraph", "cell_id": cell_id, "cell_kind": "primary",
            "variant": v, "cq_id": cq, "cluster_id": bank[cq]["cluster_id"], "category": bank[cq]["category"],
            "view_kind": "subgraph", "view_chars": len(text), "artifact_sha256": sha256_text(text),
            "system": rubric, "user": user, "prompt_sha256": prompt_sha(rubric, user),
        })

    # ---- (b) controls rebuilt on the subgraph text ----------------------------------------------
    paraphrases = rh._paraphrases()
    controls = [c for c in holdout if c["cell_kind"] in ("ablated_control", "preserved_control")]
    assert len(controls) == 36
    for c in sorted(controls, key=lambda c: c["cell_id"]):
        key = (c["variant"], c["cq_id"])
        text, r = read_subgraph(key)
        if text is None:
            skips["holdout_control"].append({"cell_id": c["cell_id"], "reason": "no subgraph for the source cell"})
            continue
        if c["cell_kind"] == "ablated_control":
            try:
                art = rh.ablate_rendered_view(text, bank[c["cq_id"]])
            except ValueError as exc:
                skips["holdout_control"].append({"cell_id": c["cell_id"],
                                                 "reason": f"grounding span not in the subgraph: {exc}"[:200]})
                continue
            q = bank[c["cq_id"]]["question"]
        else:
            art = text
            q = paraphrases[c["cq_id"]]
        user = holdout_user_message(art, q)
        jobs.append({
            "job_id": f"hc|{c['cell_id']}", "study": "holdout_control", "cell_id": c["cell_id"],
            "cell_kind": c["cell_kind"], "variant": c["variant"], "cq_id": c["cq_id"],
            "cluster_id": c["cluster_id"], "category": c["category"],
            "view_kind": "subgraph_" + c["cell_kind"], "view_chars": len(art),
            "artifact_sha256": sha256_text(art), "system": rubric, "user": user,
            "prompt_sha256": prompt_sha(rubric, user),
        })

    # ---- (c) development study --------------------------------------------------------------
    judge_system, layer1_rubric = dev_prompt_parts()
    ev = json.loads(DEV_EVAL.read_text(encoding="utf-8"))
    cqs = json.loads(DEV_CQ.read_text(encoding="utf-8"))["questions"]
    assert len(cqs) == 16 and sorted(ev["summaries"]) == list("ABCDEF")
    for v in "ABCDEF":
        summary = ev["summaries"][v]
        for cq in cqs:
            user = dev_user_message(layer1_rubric, cq, v, summary)
            cell_id = f"dev:{v}:{cq['id']}"
            jobs.append({
                "job_id": f"dv|{cell_id}", "study": "dev", "cell_id": cell_id, "cell_kind": "primary",
                "variant": v, "cq_id": cq["id"], "cluster_id": cq["id"], "category": cq["category"],
                "view_kind": "dev_summary", "view_chars": len(summary),
                "artifact_sha256": sha256_text(summary), "system": judge_system, "user": user,
                "prompt_sha256": prompt_sha(judge_system, user),
            })

    meta = {
        "manifest_sha256": manifest_sha,
        "bank_sha256": digests.get("cq_bank_brick_v1.csv"),
        "holdout_rubric_string_sha256": sha256_text(rubric),
        "dev_judge_system_sha256": sha256_text(judge_system),
        "dev_layer1_rubric_sha256": sha256_text(layer1_rubric),
        "dev_eval_json_sha256": sha256_file(DEV_EVAL),
        "dev_cq_json_sha256": sha256_file(DEV_CQ),
        "dev_eval_ab_py_sha256": sha256_file(DEV_SRC / "eval_ab.py"),
        "holdout_cells_jsonl_sha256": sha256_file(HOLDOUT_CELLS),
        "n_jobs": len(jobs),
        "n_by_study": {s: sum(1 for j in jobs if j["study"] == s) for s in ("holdout_subgraph", "holdout_control", "dev")},
        "n_controls_by_kind": {k: sum(1 for j in jobs if j["cell_kind"] == k)
                               for k in ("ablated_control", "preserved_control")},
        "skips": {k: len(v) for k, v in skips.items()},
    }
    return jobs, {"meta": meta, "skips": skips}


def main() -> int:
    jobs, info = build()
    ids = [j["job_id"] for j in jobs]
    assert len(ids) == len(set(ids)), "duplicate job ids"
    with OUT.open("w", encoding="utf-8") as fh:
        for j in jobs:
            fh.write(json.dumps(j, ensure_ascii=False) + "\n")
    SKIPS.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    info["meta"]["jobs_jsonl_sha256"] = sha256_file(OUT)
    SKIPS.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(info["meta"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
