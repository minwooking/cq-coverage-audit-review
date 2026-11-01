"""Tests for blind_audit.py -- B1 static scan, B2 runtime open-log, B3 transcript scan
(addendum 47, plan-based, exploratory). AI-generated draft: a person must review and test it
before use. Transcript fixtures are synthetic jsonl in tmp_path -- no real session file is
opened, no forbidden path is touched.
"""
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import blind_audit as ba  # noqa: E402

# A string with the forbidden pattern glued to a path separator is the "violation" form.
HITS = "harness/variants/A/rendered_view.txt"
HITS2 = str(Path("review6_judges") / "raw" / "x.jsonl")
BANNED_TEXT = "harness/variants/A/rendered_view.txt"


# ---------------------------------------------------------------- B1 static
def test_b1_flags_path_reference_in_tool(tmp_path):
    t = tmp_path / "evil_tool.py"
    t.write_text('p = "/root/' + BANNED_TEXT + '"\nopen(p)\n', encoding="utf-8")
    hits = ba.scan_tool_static(t, [BANNED_TEXT, "annotation/"])
    assert any(h["severity"] == "violation" for h in hits)
    assert not ba.scan_tool_static(t, [BANNED_TEXT]) == []


def test_b1_prose_and_config_are_not_violations(tmp_path):
    t = tmp_path / "prose_tool.py"
    t.write_text('"""do not read harness/variants/A/rendered_view.txt ever."""\n'
                 'P = "' + BANNED_TEXT + '"  # config string equals the pattern\n', encoding="utf-8")
    hits = ba.scan_tool_static(t, [BANNED_TEXT])
    sevs = {h["severity"] for h in hits}
    assert "violation" not in sevs
    assert sevs <= {"prose-mention", "pattern-config", "exempt-listed"}


def test_b1_exempt_by_name():
    rep = ba.audit_static(common.TOOLS)
    # the two post-freeze scripts are exempt; every real tool must come back clean
    for f in rep:
        if f.endswith(".py") and f not in ("eligibility.py", "views.py"):
            assert not [h for h in rep[f] if isinstance(h, dict) and h.get("severity") == "violation"], f
    # and the tools directory contains no real forbidden-path string constants:
    # blind_patterns.json (a config) keeps the pattern strings themselves, which the
    # scanner classifies as informational, not violations.


def test_b1_scans_every_tool_file():
    rep = ba.audit_static(common.TOOLS)
    for name in ("common.py", "frame.py", "draft.py", "validate.py", "dedup.py",
                 "blind_audit.py"):
        assert name in rep


def test_static_main_reports_clean():
    assert ba.main(["--static"]) == 0


# ---------------------------------------------------------------- B2 runtime logs
def test_b2_counts_forbidden_paths(tmp_path):
    good = tmp_path / "blind_open_log_b1.jsonl"
    good.write_text(json.dumps({"event": "open", "path": "/some/data/brick-v1.4.4.ttl"}) + "\n",
                    encoding="utf-8")
    bad = tmp_path / "blind_open_log_b2.jsonl"
    bad.write_text(json.dumps({"event": "open",
                               "path": "/x/harness/variants/A/rendered_view.txt"}) + "\n" +
                   json.dumps({"event": "os.listdir", "path": "/x/annotation/multirater"}) + "\n",
                   encoding="utf-8")
    res = ba.audit_runtime_logs(tmp_path)
    assert res["per_log"]["blind_open_log_b1.jsonl"] == 0
    assert res["per_log"]["blind_open_log_b2.jsonl"] == 2
    assert res["total_forbidden_opens"] == 2


def test_b2_empty_dir_zero(tmp_path):
    assert ba.audit_runtime_logs(tmp_path / "none")["total_forbidden_opens"] == 0


# ---------------------------------------------------------------- B3 transcripts
def test_b3_counts_only(tmp_path):
    t = tmp_path / "session.jsonl"
    t.write_text(json.dumps({
        "type": "tool_use", "name": "Read",
        "input": {"file_path": "/x/harness/variants/A/rendered_view.txt"}}) + "\n" +
        json.dumps({"type": "tool_use", "name": "Read",
                    "input": {"file_path": "/x/data/brick-v1.4.4.ttl"}}) + "\n",
        encoding="utf-8")
    res = ba.audit_transcripts([t])
    d = res[t.name]
    assert d["status"] == "scanned" and d["tool_calls"] == 2
    # counts are keyed by the CONFIG patterns; the transcript's own content (e.g. the
    # allowed snapshot path) is never kept or echoed
    assert sum(d["forbidden_pattern_counts"].values()) == d["total_forbidden_hits"]
    assert d["total_forbidden_hits"] >= 1
    assert "brick-v1" not in json.dumps(d)


def test_b3_missing_transcript_not_verifiable(tmp_path):
    res = ba.audit_transcripts([tmp_path / "absent.jsonl"])
    assert "not verifiable" in res["absent.jsonl"]["status"]


# ---------------------------------------------------------------- report
def test_report_contains_limit_sentence(tmp_path):
    static = {"draft.py": []}
    runtime = {"per_log": {"blind_open_log_b1.jsonl": 0}, "total_forbidden_opens": 0}
    out = tmp_path / "BLIND_AUDIT_b1.md"
    ba.write_report(out, static, runtime, {})
    txt = out.read_text(encoding="utf-8")
    assert "B1-B2 cannot prove what a human or agent saw" in txt
    assert "B1 PASS" in txt and "B2 PASS" in txt and "NOT RUN" in txt


def test_report_flags_violations(tmp_path):
    static = {"evil.py": [{"severity": "violation", "line": 1, "kind": "path-join",
                           "pattern": "annotation/", "snippet": "x"}]}
    runtime = {"per_log": {}, "total_forbidden_opens": 0}
    out = tmp_path / "R.md"
    ba.write_report(out, static, runtime, {})
    txt = out.read_text(encoding="utf-8")
    assert "B1 FAIL" in txt
