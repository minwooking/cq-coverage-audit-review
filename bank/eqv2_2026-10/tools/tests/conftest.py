"""Pytest fixtures and path setup for the eqv2 bank tools (addendum 47, plan-based, exploratory).
AI-generated draft: a person must review and test it before use.
"""
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))


@pytest.fixture
def tools_dir():
    return TOOLS


@pytest.fixture
def tmp_logs(tmp_path):
    """Redirect common.LOG_DIR to a temp directory so test writes never touch the repo logs."""
    import common
    old_log = common.LOG_DIR
    old_state = dict(common._HOOK_STATE)
    logp = tmp_path / "logs"
    logp.mkdir()
    common.LOG_DIR = logp
    common._HOOK_STATE["log"] = logp / "blind_open_log_b1.jsonl"
    yield logp
    common.LOG_DIR = old_log
    common._HOOK_STATE.clear()
    common._HOOK_STATE.update(old_state)


@pytest.fixture
def snap():
    """The frozen snapshot (session-wide: parse only, sha asserted in Snapshot.__init__)."""
    import common
    if not hasattr(snap, "_cache"):
        snap._cache = [common.Snapshot(common.SNAPSHOT)]
    return snap._cache[0]


@pytest.fixture
def frame_plan(snap):
    """Deterministic frame plan computed in-memory (frame_summary.json is never read)."""
    import frame as frame_mod
    if not hasattr(frame_plan, "_cache"):
        frame_plan._cache = [frame_mod.frame_plan(snap)]
    return frame_plan._cache[0]


# ---------------------------------------------------------------- mock embedding (no model,
# no network): deterministic pseudo-vectors from a hash, normalized -- good enough to
# exercise D5's threshold logic and tau calibration arithmetic.
class MockEmbed:
    def __init__(self, dim=16):
        self.dim = dim

    def __call__(self, texts):
        import hashlib
        import numpy as np
        out = []
        for t in texts:
            seed = int.from_bytes(hashlib.sha256(t.lower().encode()).digest()[:8], "little")
            v = np.array([(seed >> (i * 3)) % 13 for i in range(self.dim)], dtype=float) + 1.0
            v = v / float(np.linalg.norm(v))
            out.append(v)
        return np.array(out)


@pytest.fixture
def mock_embed():
    return MockEmbed()


@pytest.fixture
def frame_items_fixture(frame_plan):
    import common
    return common.frame_items(frame_plan)
