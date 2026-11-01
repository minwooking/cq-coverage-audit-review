"""Preflight checks for the Access reproducibility chain.

This verifier checks frozen inputs and provenance metadata only. It never calls a
judge, creates labels, or writes manuscript numbers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Import constants from the existing runner rather than maintaining a second set
# of frozen values. These imports have no network or output side effects.
from build_brick_corpus import FROZEN_TTL_SHA256  # noqa: E402
from run_holdout import (  # noqa: E402
    FROZEN_BANK_ROWS,
    FROZEN_BANK_SHA256,
    FROZEN_RENDERING_SHA256,
    FROZEN_RUBRIC_SHA256,
    REGISTERED_SEED,
)

FILES = {
    ROOT / "bank" / "cq_bank_brick_v1.csv": FROZEN_BANK_SHA256,
    ROOT / "rubric" / "RUBRIC_L1.md": FROZEN_RUBRIC_SHA256,
    ROOT / "rubric" / "RENDERING_SPEC.md": FROZEN_RENDERING_SHA256,
    ROOT / "data" / "brick-v1.4.4.ttl": FROZEN_TTL_SHA256,
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_frozen_inputs() -> list[str]:
    errors: list[str] = []
    for path, expected in FILES.items():
        if not path.is_file():
            errors.append(f"missing frozen input: {path}")
            continue
        found = digest(path)
        if found != expected:
            errors.append(
                f"digest mismatch: {path} expected {expected}, found {found}"
            )
    bank = ROOT / "bank" / "cq_bank_brick_v1.csv"
    if bank.is_file():
        rows = bank.read_text(encoding="utf-8").splitlines()
        # Header is not a row. This is intentionally independent of csv parsing;
        # the runner performs the authoritative DictReader parse.
        if len(rows) - 1 != FROZEN_BANK_ROWS:
            errors.append(
                f"bank row count mismatch: expected {FROZEN_BANK_ROWS}, found {len(rows) - 1}"
            )
    return errors


def check_prereg_digest() -> list[str]:
    prereg = ROOT / "PREREG.md"
    manuscript = ROOT / "main.tex"
    errors: list[str] = []
    if not prereg.is_file() or not manuscript.is_file():
        return [f"missing PREREG/main.tex for digest check: {prereg}, {manuscript}"]
    expected = digest(prereg)
    # The digest is split across a TeX line break in main.tex. Removing only
    # backslashes and newlines makes that representation comparable without
    # interpreting the manuscript or changing it.
    compact = manuscript.read_text(encoding="utf-8").replace("\\", "").replace("\n", "")
    if expected not in compact:
        errors.append(
            f"main.tex does not contain the current PREREG.md SHA-256 ({expected})"
        )
    return errors


def check_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return [f"manifest not found: {path}"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot parse manifest {path}: {exc}"]
    expected = {
        "bank_sha256": FROZEN_BANK_SHA256,
        "rubric_sha256": FROZEN_RUBRIC_SHA256,
        "rendering_spec_sha256": FROZEN_RENDERING_SHA256,
        "seed": REGISTERED_SEED,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            errors.append(
                f"manifest {path}: {key} expected {value!r}, found {manifest.get(key)!r}"
            )
    if manifest.get("bank_rows") != FROZEN_BANK_ROWS:
        errors.append(
            f"manifest {path}: bank_rows expected {FROZEN_BANK_ROWS}, found {manifest.get('bank_rows')!r}"
        )
    return errors


def check_bank_groundings() -> list[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "bank" / "verify_bank.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return []
    detail = (result.stdout + result.stderr).strip().splitlines()
    return ["bank/verify_bank.py failed: " + (detail[-1] if detail else "unknown error")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        action="append",
        default=[],
        help="optional MANIFEST.json to validate; may be repeated",
    )
    args = parser.parse_args()

    errors = check_frozen_inputs()
    errors.extend(check_prereg_digest())
    for manifest in args.manifest:
        errors.extend(check_manifest(manifest))
    errors.extend(check_bank_groundings())

    if errors:
        print("REPRODUCIBILITY PREFLIGHT: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("REPRODUCIBILITY PREFLIGHT: PASS")
    print(f"- frozen inputs: {len(FILES)} SHA-256 checks")
    print(f"- bank rows: {FROZEN_BANK_ROWS}")
    print(f"- registered seed: {REGISTERED_SEED}")
    print("- PREREG.md digest is present in main.tex")
    if args.manifest:
        print(f"- manifests checked: {len(args.manifest)}")
    print("- bank groundings resolve in the frozen Brick snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
