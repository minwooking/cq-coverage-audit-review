"""Offline tests of study6_rescoring (no network, no model).  AI-generated; review before use."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as an  # noqa: E402


def rec(cid, rep, j, study="A_nohint", valid=True):
    return {"cell_id": cid, "repeat": rep, "J": j, "valid": valid, "study": study, "status": "ok" if valid else "invalid"}


def test_parse_key():
    assert an.parse_key("A_nohint|dev:B:CQ03") == ("B", "CQ03")
    assert an.parse_key("primary:D:CQB09") == ("D", "CQB09")
    assert an.parse_key("dev:A:CQ01") == ("A", "CQ01")


def test_repeats_first_valid_and_mean():
    recs = [rec("A_nohint|dev:A:CQ01", 1, 2), rec("A_nohint|dev:A:CQ01", 1, 3), rec("A_nohint|dev:A:CQ01", 2, 3),
            rec("A_nohint|dev:A:CQ02", 1, 1, valid=False), rec("A_hint|dev:A:CQ01", 1, 0, study="A_hint")]
    rep = an.repeats(recs, "A_nohint")
    assert rep == {("A", "CQ01"): {1: 2, 2: 3}}
    assert an.cellmean(rep)[("A", "CQ01")] == 2.5


def test_contrast_and_decision():
    qs = [f"CQ{i:02d}" for i in range(16)]
    sc = {}
    for i, q in enumerate(qs):
        sc[("A", q)] = 1.0
        sc[("B", q)] = 2.0 + (0.0 if i % 2 else 1.0)
    c = an.contrast(sc, "A", "B")
    assert c["n"] == 16 and abs(c["delta"] - 1.5) < 1e-9 and c["decision"] == "resolved" and c["sign"] == 1
    sc2 = {k: 1.0 for k in sc}
    c2 = an.contrast(sc2, "A", "B")
    assert c2["delta"] == 0 and c2["decision_0.30"] == "equivalent" or c2["decision_0.30"] == "unresolved"


def test_hint_reading():
    pos = {"decision_0.30": "resolved", "delta": 0.5}
    neg = {"decision_0.30": "unresolved", "delta": 0.1}
    assert an.hint_reading(pos, pos) == "hint-independent"
    assert an.hint_reading(neg, pos) == "hint-dependent"
    assert an.hint_reading(neg, neg) == "never resolved"
    assert an.hint_reading(None, None) == "not computable"


def test_qwk_and_agree():
    rep = {("A", f"Q{i}"): {1: i % 4, 2: i % 4, 3: i % 4} for i in range(12)}
    ref = {k: v[1] for k, v in rep.items()}
    a = an.agree(rep, ref)
    assert a["exact"] == 1.0 and abs(a["qwk"] - 1.0) < 1e-9 and a["offset"] == 0


def test_readings():
    assert an.reading_DB({"delta": -0.3, "ci95": [-0.5, -0.1]}).startswith("replicates")
    assert an.reading_DB({"delta": -0.3, "ci95": [-0.5, 0.1]}).startswith("direction only")
    assert an.reading_DB({"delta": 0.0, "ci95": [-0.5, 0.1]}).startswith("does not")


def test_job_prompts_differ_only_by_hint():
    jobs = [json.loads(l) for l in (HERE / "jobs_A.jsonl").read_text().splitlines()]
    by = {j["cell_id"]: j for j in jobs}
    assert len(jobs) == 288
    h, n = by["A_hint|dev:A:CQ01"], by["A_nohint|dev:A:CQ01"]
    assert h["system"] == n["system"] and "What a good answer needs" in h["user"] and "What a good answer needs" not in n["user"]
    ho = by["A_holdout|dev:A:CQ01"]
    assert "COMPETENCY QUESTION" not in ho["user"] and "ONTOLOGY A" not in ho["user"] and ho["user"].startswith("ARTIFACT:")
