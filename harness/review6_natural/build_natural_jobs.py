#!/usr/bin/env python3
"""Addendum 27 amendment 1: build the judge jobs for gpt-oss-20b / GLM-4.7-Flash.  Offline, no network.

AI-generated; review before reuse.  Same record schema and prompt rule as harness/review6_judges/build_jobs.py:
system = run_holdout.RUBRIC, user = "ARTIFACT:\\n{view}\\n\\nQUESTION: {question}", prompt_sha256 over
system + "\\n\\x00\\n" + user.

  jobs_natural.jsonl      72 cells: natural-corpus A and B subgraph views (inputs/manifest.jsonl, sha pinned)
  jobs_template_AB.jsonl  54 cells: template-corpus A (22) and B (32) subgraph views, rebuilt from the length
                          experiment's own subgraph files; every prompt_sha256 is cross-checked against the
                          addendum-26 jobs.jsonl (sha256 pinned) so that reused records are provably the same prompts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parents[1]
HARNESS = ACCESS / "harness"
sys.path.insert(0, str(HARNESS))

import run_holdout as rh  # noqa: E402

NAT_MANIFEST = HERE / "inputs" / "manifest.jsonl"
NAT_MANIFEST_SHA = "0048910bf97d3ebfdfed58852201911b168fea4481ff61ad058ef777c229ac2e"
TPL_MANIFEST = HARNESS / "length_experiment" / "inputs" / "manifest.jsonl"
TPL_MANIFEST_SHA = "46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32"
A26_JOBS = HARNESS / "review6_judges" / "jobs.jsonl"
A26_JOBS_SHA = "30190f072caa33a32b77586c76b60d5debf68febae3749bd27e0a483e8be524c"
BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"


def sha_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def prompt_sha(system: str, user: str) -> str:
    return sha_text(system + "\n\x00\n" + user)


def main() -> int:
    if sha_file(NAT_MANIFEST) != NAT_MANIFEST_SHA:
        raise SystemExit("natural inputs manifest sha256 differs from the plan value")
    if sha_file(TPL_MANIFEST) != TPL_MANIFEST_SHA:
        raise SystemExit("length-experiment manifest sha256 differs")
    if sha_file(A26_JOBS) != A26_JOBS_SHA:
        raise SystemExit("addendum 26 jobs.jsonl sha256 differs from its pinned value")
    rows, _ = rh.verify_frozen(BANK)
    bank = {r["cq_id"]: r for r in rows}
    a26 = {j["cell_id"]: j for j in map(json.loads, A26_JOBS.read_text(encoding="utf-8").splitlines()) if j["study"] == "holdout_subgraph"}

    def job(study, cell_id, v, cq, text, view_kind="subgraph"):
        user = f"ARTIFACT:\n{text}\n\nQUESTION: {bank[cq]['question']}"
        return {"job_id": f"{study}|{cell_id}", "study": study, "cell_id": cell_id, "cell_kind": "primary", "variant": v,
                "cq_id": cq, "cluster_id": bank[cq]["cluster_id"], "category": bank[cq]["category"],
                "view_kind": view_kind, "view_chars": len(text), "artifact_sha256": sha_text(text),
                "system": rh.RUBRIC, "user": user, "prompt_sha256": prompt_sha(rh.RUBRIC, user)}

    nat = []
    for r in map(json.loads, NAT_MANIFEST.read_text(encoding="utf-8").splitlines()):
        if r["condition"] != "subgraph" or r["variant"] not in ("A", "B"):
            continue
        if r["status"] != "ok":
            raise SystemExit(f"natural subgraph not applicable: {r['variant']} {r['cq_id']} (plan: none expected)")
        text = (ACCESS / r["path"]).read_text(encoding="utf-8")
        if sha_text(text) != r["sha256"]:
            raise SystemExit(f"subgraph sha256 differs from manifest: {r['path']}")
        nat.append(job("natural_subgraph", f"natural:{r['variant']}:{r['cq_id']}", r["variant"], r["cq_id"], text))
    nat.sort(key=lambda j: (j["variant"], j["cq_id"]))
    assert len(nat) == 72, len(nat)

    tpl = []
    for cell_id, ref in sorted(a26.items()):
        if ref["variant"] not in ("A", "B"):
            continue
        r = next(x for x in map(json.loads, TPL_MANIFEST.read_text(encoding="utf-8").splitlines())
                 if x["condition"] == "subgraph" and x["variant"] == ref["variant"] and x["cq_id"] == ref["cq_id"])
        text = (ACCESS / r["path"]).read_text(encoding="utf-8")
        if sha_text(text) != r["sha256"]:
            raise SystemExit(f"template subgraph sha256 differs: {r['path']}")
        j = job("template_subgraph", cell_id, ref["variant"], ref["cq_id"], text)
        if j["prompt_sha256"] != ref["prompt_sha256"]:
            raise SystemExit(f"prompt sha256 differs from addendum 26 job for {cell_id}")
        tpl.append(j)
    assert {j["variant"] for j in tpl} == {"A", "B"}
    for name, jobs in (("jobs_natural.jsonl", nat), ("jobs_template_AB.jsonl", tpl)):
        (HERE / name).write_text("\n".join(json.dumps(j, ensure_ascii=False) for j in jobs) + "\n", encoding="utf-8")
    summ = {"natural": {"n": len(nat), "sha256": sha_file(HERE / "jobs_natural.jsonl")},
            "template_AB": {"n": len(tpl), "A": sum(1 for j in tpl if j["variant"] == "A"), "B": sum(1 for j in tpl if j["variant"] == "B"),
                            "sha256": sha_file(HERE / "jobs_template_AB.jsonl"),
                            "prompt_sha256_all_match_addendum26": True},
            "pins": {"natural_manifest": NAT_MANIFEST_SHA, "length_manifest": TPL_MANIFEST_SHA, "a26_jobs": A26_JOBS_SHA,
                     "rubric_sha256": sha_text(rh.RUBRIC)}}
    (HERE / "jobs_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
