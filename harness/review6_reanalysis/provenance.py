#!/usr/bin/env python3
"""Writes parts/provenance.json: input hashes, versions, repo HEAD (read-only), seed.  No sealed file is opened."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


inputs = {
    "per_cell AH (unsealed 2026-10-09)": C.P_AH,
    "second rater v3 per-cell results": C.P_V3,
    "registered judge cells (224)": C.P_CELLS,
    "luna length experiment cells": C.P_LEN,
    "luna full-view B-F cells": C.P_LUNA_FULL,
    "panel luna 48 cells": C.P_PANEL / "gpt-5.6-luna/cells.jsonl",
    "panel sonnet 48 cells": C.P_PANEL / "anthropic__claude-sonnet-5-5/cells.jsonl",
    "panel 48-cell list": C.P_LIST48,
    "analyzer (BCa, definitions)": C.H / "analyze_holdout.py",
    "AH registered rerun results (reproduction target)": C.H / "real_run/results_human_pass/unsealed_2026-10-09/holdout_results_human.rerun_0dbe6e9.json",
    "second rater v3 analyzer results (reproduction target)": C.PAPER / "annotation/second_pass_2026-10-13/v3/results_v3.json",
}
out = {"seed": C.SEED, "B": C.B, "bca_ties": C.TIES,
       "inputs_sha256": {k: {"path": str(v.relative_to(C.PAPER)), "sha256": sha(v)} for k, v in inputs.items()},
       "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                    "scipy": scipy.__version__},
       "not_opened": ["site_key*", "labeling_sheet_key*", "human_labels_export*", "views_for_raters.zip", ".env",
                      "persona_pass/*", "raw label CSVs with spans/notes (labels_v3.csv, primary_working.csv)"]}
try:
    out["repo_head"] = subprocess.run(["git", "-C", str(C.PAPER), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out["repo_dirty_files_in_this_dir_only"] = "this directory is untracked; nothing else is modified by these scripts"
except Exception as e:  # pragma: no cover
    out["repo_head"] = f"unavailable: {e}"
json.dump(out, open(Path(__file__).resolve().parent / "parts/provenance.json", "w"), indent=1)
print(json.dumps(out["inputs_sha256"], indent=1)[:600], out["repo_head"])
