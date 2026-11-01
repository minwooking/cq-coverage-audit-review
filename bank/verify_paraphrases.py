"""Verify the frozen test-retest paraphrase CSV against the source CQ bank.

The verifier is a mechanical freeze gate.  It checks complete row coverage,
cell/cluster identity, unchanged grounding, and enough surface change to avoid
showing the rater the original question again.  It does not replace the human
semantic-equivalence review required for a paraphrase freeze.

Exit codes follow verify_bank.py: 0 = pass, 1 = validation failure,
2 = invalid invocation or missing input.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Iterable, Mapping, Sequence

BASE = Path(__file__).resolve().parent.parent
BANK_DIR = BASE / "bank"
SOURCE_NAME = "cq_bank_brick_v1.csv"
PARAPHRASE_NAME = "cq_bank_brick_v1_paraphrases.csv"
EXPECTED_ROWS = 36
MAX_JACCARD = 0.60
SOURCE_FIELDS = {"cq_id", "question", "grounding", "expected_answer", "cluster_id"}
PARAPHRASE_FIELDS = {"cq_id", "cluster_id", "paraphrase_text", "grounding"}
TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.casefold()))


def normalized(text: str) -> str:
    """Return a comparison form that ignores case and punctuation/whitespace."""
    return " ".join(TOKEN.findall(text.casefold()))


def jaccard_tokens(left: str, right: str) -> float:
    """Return set-token Jaccard overlap, treating two empty texts as identical."""
    a, b = _tokens(left), _tokens(right)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _read_csv(path: Path, required: set[str]) -> tuple[list[dict[str, str]], list[str]]:
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fields = set(reader.fieldnames or [])
            missing = sorted(required - fields)
            if missing:
                return [], [f"{path.name}: missing columns: {', '.join(missing)}"]
            return list(reader), []
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], [f"{path.name}: cannot read CSV: {exc}"]


def _duplicates(rows: Iterable[Mapping[str, str]], key: str) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        value = row.get(key, "")
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def validate(
    source_path: Path,
    paraphrase_path: Path,
    *,
    max_jaccard: float = MAX_JACCARD,
) -> list[str]:
    """Return validation errors; an empty list means the pair passes."""
    source_rows, errors = _read_csv(source_path, SOURCE_FIELDS)
    para_rows, para_errors = _read_csv(paraphrase_path, PARAPHRASE_FIELDS)
    errors.extend(para_errors)
    if errors:
        return errors

    if len(source_rows) != EXPECTED_ROWS:
        errors.append(
            f"source row count is {len(source_rows)}; expected exactly {EXPECTED_ROWS}"
        )
    if len(para_rows) != EXPECTED_ROWS:
        errors.append(
            f"paraphrase row count is {len(para_rows)}; expected exactly {EXPECTED_ROWS}"
        )

    source_dupes = _duplicates(source_rows, "cq_id")
    para_dupes = _duplicates(para_rows, "cq_id")
    if source_dupes:
        errors.append("source duplicate cq_id: " + ", ".join(source_dupes))
    if para_dupes:
        errors.append("paraphrase duplicate cq_id: " + ", ".join(para_dupes))

    source_by_id = {row["cq_id"]: row for row in source_rows}
    para_by_id = {row["cq_id"]: row for row in para_rows}
    source_ids, para_ids = set(source_by_id), set(para_by_id)
    for cq_id in sorted(source_ids - para_ids):
        errors.append(f"missing paraphrase row for cq_id {cq_id}")
    for cq_id in sorted(para_ids - source_ids):
        errors.append(f"unknown paraphrase cq_id {cq_id}")

    for cq_id in sorted(source_ids & para_ids):
        source = source_by_id[cq_id]
        para = para_by_id[cq_id]
        if para["cluster_id"] != source["cluster_id"]:
            errors.append(
                f"{cq_id}: cluster_id mismatch: {para['cluster_id']!r} != "
                f"{source['cluster_id']!r}"
            )
        if para["grounding"] != source["grounding"]:
            errors.append(
                f"{cq_id}: grounding mismatch: {para['grounding']!r} != "
                f"{source['grounding']!r}"
            )

        paraphrase = para["paraphrase_text"].strip()
        if not paraphrase:
            errors.append(f"{cq_id}: paraphrase_text is empty")
            continue
        if normalized(paraphrase) == normalized(source["question"]):
            errors.append(f"{cq_id}: paraphrase is identical to source question")
        overlap = jaccard_tokens(source["question"], paraphrase)
        if overlap > max_jaccard:
            errors.append(
                f"{cq_id}: token Jaccard overlap {overlap:.3f} exceeds "
                f"maximum {max_jaccard:.3f}"
            )

    return errors


def _resolve_input(name: str, label: str) -> Path:
    path = Path(name)
    if path.is_absolute():
        raise ValueError(f"{label} filename must be relative")
    resolved = (BANK_DIR / path).resolve()
    try:
        resolved.relative_to(BANK_DIR.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} filename escapes {BANK_DIR}") from exc
    return resolved


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) > 2:
        print("ERROR: expected [paraphrase CSV] [source bank CSV]", file=sys.stderr)
        return 2
    try:
        paraphrase_path = _resolve_input(
            args[0] if args else PARAPHRASE_NAME, "paraphrase bank"
        )
        source_path = _resolve_input(
            args[1] if len(args) == 2 else SOURCE_NAME, "source bank"
        )
    except ValueError as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 2

    for path in (source_path, paraphrase_path):
        if not path.is_file():
            print("ERROR: required input not found:", path, file=sys.stderr)
            return 2

    errors = validate(source_path, paraphrase_path)
    print("source:", source_path.name, "| paraphrases:", paraphrase_path.name)
    print(
        "rows:", EXPECTED_ROWS,
        "| max token Jaccard:", f"{MAX_JACCARD:.2f}",
        "| errors:", len(errors),
    )
    for error in errors:
        print("  ERROR", error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
