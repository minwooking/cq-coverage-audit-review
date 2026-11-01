"""Tests for real_run/results_human_pass/dwell_skew_check.py on synthetic audit data.

The fixtures mimic label_assist.Store.save: elapsed_s = round(server save time - client
page-load stamp, 1), a negative value is stored as null, and the audit ts is the server wall
clock truncated to whole seconds. A client-clock offset is injected so the check can be seen to
detect a skew (positive control). No real audit data is read.
"""
import importlib.util
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "real_run" / "results_human_pass" / "dwell_skew_check.py"
_spec = importlib.util.spec_from_file_location("dwell_skew_check", SCRIPT)
dsc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dsc)

KST = timezone(timedelta(hours=9))
BASE = 1_790_000_000.0  # server epoch seconds at session start
SID = "SID-SECRET"


def _fixture(tmp_path, offset_s, n=60, seed=7):
    """One session of n saves; the client clock is the server clock plus offset_s."""
    rng = random.Random(seed)
    lines, t_prev, expected_null = [], BASE, 0
    for k in range(n):
        tau = 0.15 + 0.1 * rng.random()      # save -> next page script latency
        dwell = 6.0 + 10.0 * rng.random()    # time the rater spends on the row
        t_open = t_prev + tau
        t_save = t_open + dwell
        stamp = datetime.fromtimestamp(t_open + offset_s, timezone.utc)
        first_opened = stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        client = datetime.fromisoformat(first_opened.replace("Z", "+00:00")).timestamp()
        elapsed = round(t_save - client, 1)
        if elapsed < 0:  # label_assist stores a negative dwell as null
            elapsed, expected_null = None, expected_null + 1
        prefix = "ablated_control:" if k % 6 == 5 else ""
        lines.append(json.dumps({
            "ts": datetime.fromtimestamp(t_save + 0.01, KST).isoformat(timespec="seconds"),
            "cell_id": f"{prefix}SECRETCELL{k}", "row": k, "A": 1, "span_chars": 9,
            "rater_L1": 2, "first_opened_ts": first_opened, "elapsed_s": elapsed,
            "session_id": SID, "note": "SECRETNOTE", "draft_model": "SECRETMODEL"}))
        t_prev = t_save
    lines.append(json.dumps({"event": "12H_ACK_OVERRIDE", "session_id": SID,
                             "ts": "2026-10-08T19:47:33+09:00"}))
    audit, log = tmp_path / "a.audit.jsonl", tmp_path / "a.session_log.txt"
    audit.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.write_text(f"SESSION start=2026-10-08T19:46:03+09:00 pid=1 session_id={SID}\n"
                   f"SESSION end=2026-10-08T22:10:39+09:00 pid=1 saved={n}\n", encoding="utf-8")
    return audit, log, expected_null


def _run(tmp_path, offset_s, **kw):
    audit, log, expected_null = _fixture(tmp_path, offset_s, **kw)
    return dsc.analyze(audit, log, boot_b=200), expected_null


def test_no_skew_reads_as_page_load_latency(tmp_path):
    out, _ = _run(tmp_path, 0.0)
    sess = out["sessions"]["S1"]
    assert 0.1 <= sess["skew_estimator"]["median_s"] <= 0.3
    assert sess["skew_estimator"]["client_lead_upper_bound_s"] < 0.3
    assert -0.3 <= sess["delta_minus_elapsed"]["median_s"] <= 0.8
    assert out["elapsed_s_null_or_negative"]["n_null_or_negative"] == 0
    assert all(out["checks"].values())


def test_client_clock_ahead_is_detected(tmp_path):
    sess = _run(tmp_path, 5.0)[0]["sessions"]["S1"]
    assert 5.1 <= sess["skew_estimator"]["median_s"] <= 5.4
    assert sess["skew_estimator"]["client_lead_upper_bound_s"] > 4.9
    assert 4.8 <= sess["delta_minus_elapsed"]["median_s"] <= 5.9


def test_client_clock_behind_reads_negative(tmp_path):
    sk = _run(tmp_path, -5.0)[0]["sessions"]["S1"]["skew_estimator"]
    assert sk["median_s"] < -4.5
    assert sk["client_lead_upper_bound_s"] < 0


def test_negative_elapsed_is_stored_null_and_counted(tmp_path):
    out, expected_null = _run(tmp_path, 12.0)
    nn = out["elapsed_s_null_or_negative"]
    assert expected_null > 0
    assert nn["n_null"] == expected_null and nn["n_negative"] == 0
    assert nn["n_null_or_negative"] == expected_null
    assert nn["n_null_with_first_opened_ts_present"] == expected_null
    assert out["sessions"]["S1"]["skew_estimator"]["n"] < 59  # s needs the previous elapsed_s


def test_g7_counts_and_break_even_match_an_independent_count(tmp_path):
    audit, log, _ = _fixture(tmp_path, 0.0)
    out = dsc.analyze(audit, log, boot_b=200)
    recs = [json.loads(line) for line in audit.read_text().splitlines()]
    prim = [r for r in recs if "cell_id" in r and not r["cell_id"].startswith("ablated_control:")]
    reg = out["g7_under_20s"]["registered_basis_elapsed_s"]
    assert reg["n_primary_cells"] == len(prim) == out["population"]["n_primary_cells"]
    assert reg["n_under_20s"] == sum(r["elapsed_s"] < 20 for r in prim)
    assert reg["criterion_met"] is False
    assert out["g7_under_20s"]["cells_crossing_20s"]["whole_second"]["n_crossing_20s"] == 0
    allowed = (3 * len(prim) - 1) // 100
    limiting = sorted(r["elapsed_s"] for r in prim)[allowed]
    be = out["break_even_client_lead"]
    assert be["max_cells_under_20s_allowed"] == allowed
    assert be["lead_s"] == pytest.approx(20 - limiting)


def test_output_holds_no_identifier_and_is_deterministic(tmp_path):
    audit, log, _ = _fixture(tmp_path, 0.0)
    first = json.dumps(dsc.analyze(audit, log, boot_b=200), indent=1)
    assert first == json.dumps(dsc.analyze(audit, log, boot_b=200), indent=1)
    for token in ("SECRET", "ablated_control", "preserved_control"):
        assert token not in first


def test_cell_saved_twice_stops_the_check(tmp_path):
    audit, log, _ = _fixture(tmp_path, 0.0, n=8)
    lines = audit.read_text().splitlines()
    audit.write_text("\n".join(lines + [lines[0]]) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        dsc.analyze(audit, log, boot_b=200)
