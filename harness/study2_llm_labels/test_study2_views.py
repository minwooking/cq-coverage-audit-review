"""Tests of the view builder (PLAN.md 32.4), the instruction text (32.5) and the labels (32.5).  Synthetic data only; no model,
no network, no human label.  Run:  python3 -m pytest -q test_study2_views.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s2_personas as PS  # noqa: E402
import s2_views as V  # noqa: E402
import run_holdout as rh  # noqa: E402

GROUND = "skos:definition brick:Sensor"
QUESTION = "What is a brick:Sensor?"


def make_rendering(n_noise=400, anchor_every=7, extra=None):
    lines = []
    for i in range(n_noise):
        if i % anchor_every == 0:
            lines.append(f"http://example.org/chunktograph#brick-sensor-{i} | Sensor number {i} :: a Sensor that measures things number {i}\n")
        else:
            lines.append(f"http://example.org/chunktograph#noise-{i} | Noise {i} < http://example.org/c#Thing\n")
    for pos, text in (extra or {}).items():
        lines[pos] = text + "\n"
    return "".join(lines)


def shown_lines(text):
    return [l for l in text.splitlines(keepends=True) if l != V.MARKER]


def test_deterministic_and_verbatim():
    R = make_rendering()
    a = V.build_view("A", GROUND, QUESTION, ["Sensor number 14"], rendering_text=R)
    b = V.build_view("A", GROUND, QUESTION, ["Sensor number 14"], rendering_text=R)
    assert a["text"] == b["text"]
    rl = set(R.splitlines(keepends=True))
    for l in shown_lines(a["text"]):
        assert l in rl                                      # every shown line is a verbatim rendering line (no line is long here)


def test_cap_and_marker():
    R = make_rendering(n_noise=4000, anchor_every=1)        # every line is an anchor line: far more than the cap
    d = V.build_view("A", GROUND, QUESTION, [], rendering_text=R)
    assert d["n_chars"] <= V.CAP_CHARS + len(V.MARKER) * 3000
    assert sum(len(l) for l in shown_lines(d["text"])) <= V.CAP_CHARS
    assert d["cap_reached"] and d["n_anchor_lines_included"] < d["n_anchor_lines"]


def test_span_has_priority_over_anchors_under_cap():
    long_noise = "X" * 3000
    lines = [f"http://example.org/chunktograph#brick-sensor-{i} | Sensor {i} :: {long_noise}\n" for i in range(200)]
    target = "http://example.org/chunktograph#special | Special :: the quoted answer sentence lives only here\n"
    lines[150] = target
    R = "".join(lines)
    d = V.build_view("A", GROUND, QUESTION, ["the quoted answer sentence lives only here"], rendering_text=R)
    assert target in d["text"] and d["n_span_lines_included"] == 1 and d["span_pieces_found"] == 1
    # without the span the target (not an anchor line) is not guaranteed; with it, it is present
    assert d["n_chars"] > 0


def test_window_and_marker_between_groups():
    R = make_rendering(n_noise=900, anchor_every=300)
    d = V.build_view("A", GROUND, QUESTION, [], rendering_text=R)
    assert V.MARKER in d["text"]
    kept = shown_lines(d["text"])
    assert kept and any("Sensor number 0 " in l for l in kept)
    # lines adjacent to the first anchor line (within N chars) come with it
    assert any("noise-1 " in l for l in kept)


def test_long_line_cut_is_a_substring():
    big = "http://example.org/chunktograph#brick-sensor | Sensor :: " + ("abc " * 5000) + "NEEDLE_IN_THE_MIDDLE " + ("xyz " * 5000) + "\n"
    R = make_rendering(n_noise=30) + big
    d = V.build_view("A", GROUND, QUESTION, ["NEEDLE_IN_THE_MIDDLE"], rendering_text=R)
    cut = [l for l in shown_lines(d["text"]) if "NEEDLE_IN_THE_MIDDLE" in l]
    assert cut and len(cut[0]) <= V.LINE_CAP + 1 and cut[0].rstrip("\n") in R


def test_fallback_when_no_anchor_lines():
    R = "".join(f"http://example.org/chunktograph#n-{i} | Thing {i} :: equipment sensor-free text about valves {i}\n" for i in range(300))
    R += "http://example.org/chunktograph#q | Zonal :: something unrelated\n"
    d = V.build_view("A", "skos:definition brick:Nonexistent_Term", "What are valves in equipment?", [], rendering_text=R)
    assert d["fallback_used"] and d["n_anchor_lines"] == 0 and d["n_chars"] > 0


def test_ablated_rendering_has_no_anchor_line_and_uses_fallback():
    R = make_rendering()
    abl = rh.ablate_rendered_view(R, {"grounding": GROUND, "cq_id": "T1"})
    d = V.build_view("A", GROUND, QUESTION, [], rendering_text=abl)
    assert d["n_anchor_lines"] == 0 and d["fallback_used"]


def test_span_pieces_with_ellipsis():
    R = make_rendering()
    sp = "Noise 1 < http://example.org/c#Thing ... Noise 2 < http://example.org/c#Thing"
    d = V.build_view("A", GROUND, QUESTION, [sp], rendering_text=R)
    assert d["span_pieces_total"] == 2 and d["span_pieces_found"] == 2 and d["n_span_lines_included"] == 2


def test_term_test_requires_anchor_and_half_of_answer_terms():
    row = {"cq_id": "T", "grounding": GROUND, "expected_answer": "Device that measures a physical quantity and reports temperature values"}
    c = V.Crit(row)
    ok, f = V.holds_terms("a Sensor is a device that measures a physical quantity\n[…]\nelse", c)
    assert ok and f >= 0.5
    ok2, _ = V.holds_terms("a Sensor is here\nand it measures a physical quantity elsewhere", c)
    assert not ok2                                           # anchor and terms are not on one line
    assert V.holds_terms("a device that measures a physical quantity", c)[0] is False   # no anchor


def test_view_builder_does_not_read_expected_answer():
    src = (HERE / "s2_views.py").read_text(encoding="utf-8")
    body = src.split("def build_view")[1].split("# ---------------------------------------------------------------- term test")[0]
    assert "expected_answer" not in body


def test_new_base_two_insertions_match_plan():
    plan = (HERE / "PLAN.md").read_text(encoding="utf-8")
    assert PS.INSERT_1.strip() in plan.replace("\\`", "`") or PS.INSERT_1.strip().replace("`", "") in plan.replace("`", "")
    assert PS.INSERT_2.strip() in plan
    assert PS.NEW_BASE.replace(PS.INSERT_1, "").replace(PS.INSERT_2, "") == PS.BASE
    for p in PS.PERSONAS:
        assert PS.SYSTEM[p].startswith(PS.PREAMBLE[p]) and PS.SYSTEM[p].endswith(PS.NEW_BASE)
    assert "하한이 없습니다" in PS.NEW_BASE and "R_floor" not in PS.NEW_BASE
