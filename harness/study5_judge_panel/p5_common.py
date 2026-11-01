"""Shared constants and loaders for addendum 36 (study5_judge_panel).  AI-generated; review and test before use.  No network, no model."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
REPO = ACCESS.parent.parent
S3, S4 = HARNESS / "study3_expanded_ab", HARNESS / "study4_domains"
SEED, BOOT_B, MARGIN, MIN_N = 20260913, 10_000, 0.50, 10
DOMAINS = ("dcat", "ssn", "prov")
BRICK_BANKS = ("holdout", "paraphrases", "v2_extras", "expansion")
# judge id -> (label, family relative to the extractor, counts toward the interpretation rule)
JUDGES = {
    "glm": ("GLM-4.7-Flash", "independent", True),
    "gptoss": ("gpt-oss-20b", "independent", True),
    "q38": ("Qwen3.8-Flash-Next", "Qwen lineage (counted independent per brief)", True),
    "q80": ("Qwen3-Next-80B-A3B (extractor's model id)", "same family", False),
    "gw": ("gateway judge", "independent", True),
}


def jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()] if Path(p).exists() else []


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def panel_id(scope: str, cell_id: str) -> str:
    return f"{scope}|{cell_id}"


def score_lists(recs: list[dict]) -> dict[str, list[int]]:
    """valid repeats per cell id"""
    out: dict[str, list[int]] = {}
    for r in recs:
        if r.get("valid") and r.get("J") is not None:
            out.setdefault(r["cell_id"], []).append(int(r["J"]))
    return out


def read_scores_csv(p: Path) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    if Path(p).exists():
        for r in csv.DictReader(Path(p).open(encoding="utf-8", newline="")):
            if str(r["valid"]).lower() in ("1", "true") and r["J"] not in ("", None):
                out.setdefault(r["cell_id"], []).append(int(float(r["J"])))
    return out
