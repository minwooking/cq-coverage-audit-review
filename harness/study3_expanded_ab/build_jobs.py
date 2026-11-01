#!/usr/bin/env python3
"""Addendum 34 A1: judge jobs for the A and B cells that have no judge score yet.  AI-generated; review and test before use.
No model call.  Views = question-only subgraph views of addendum 30 (sha256 checked); prompt = run_holdout.RUBRIC + Stage 2 user message.
Sets: para (Tier 3a), v2x (3b), dev (3c, extended bank, subgraph view), mfg, mfgko (second domain; aggregate only)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS))
import run_holdout as rh  # noqa: E402

MAN = HARNESS / "review10_llm_labels" / "manifests"
SETS = ["para", "v2x", "dev", "mfg", "mfgko"]


def sha(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def main() -> int:
    n = 0
    with (HERE / "jobs_new.jsonl").open("w", encoding="utf-8") as fh:
        for s in SETS:
            for r in json.loads((MAN / f"{s}.json").read_text(encoding="utf-8"))["rows"]:
                if r["variant"] not in ("A", "B"):
                    continue
                view = (ACCESS / r["view_path"]).read_text(encoding="utf-8")
                assert sha(view) == r["view_sha256"], r["cell_id"]
                user = f"ARTIFACT:\n{view}\n\nQUESTION: {r['q']}"
                job = {"job_id": f"s3|{r['cell_id']}", "study": f"s3_{s}", "cell_id": r["cell_id"], "cell_kind": "primary",
                       "variant": r["variant"], "cq_id": r["cq_id"], "cluster_id": r["cluster_id"], "category": r["cat"],
                       "view_kind": "subgraph", "view_chars": len(view), "artifact_sha256": r["view_sha256"],
                       "system": rh.RUBRIC, "user": user, "prompt_sha256": sha(rh.RUBRIC + "\n\x00\n" + user)}
                fh.write(json.dumps(job, ensure_ascii=False) + "\n")
                n += 1
    print(json.dumps({"jobs": n}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
