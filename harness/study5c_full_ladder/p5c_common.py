"""Shared paths for addendum 36 amendment C (study5c_full_ladder).  AI-generated; review and test before use.  No network, no model."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
S5 = HERE.parent / "study5_judge_panel"
sys.path.insert(0, str(S5))
import p5_common as C  # noqa: E402  (study 5 constants: SEED, BOOT_B, DOMAINS, sha256 helpers, ...)

NEW_VARIANTS = ("C", "D", "E")
ALL_VARIANTS = ("A", "B", "C", "D", "E", "F")
MARGINS = (0.50, 0.30)
