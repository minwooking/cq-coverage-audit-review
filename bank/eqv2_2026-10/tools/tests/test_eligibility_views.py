"""Tests for eligibility.py and views.py (addendum 47, C4).  AI-generated draft: a person must review them.

Synthetic inputs only, except one small smoke on the real graphs with three bank question sentences (no model call).
"""
import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import eligibility as el  # noqa: E402
import views as vw  # noqa: E402

LEAK = "ZZLEAKZZ"

# blind_audit.py exempts eligibility.py and views.py BY NAME (they run only after the bank freeze).  The in-process audit
# hook that other test modules leave installed matches the substring "eligibility" in a path, so merely READING
# tools/eligibility.py (test_frame's vocabulary scan globs tools/*.py) would raise once test_draft has run.  Applied at
# import (collection) time, for the test process only: the same by-name exemption, exactly these two files in this
# directory; the tools' runtime and blind_audit.py are untouched.
import os  # noqa: E402
import common  # noqa: E402

if not getattr(common.forbidden_hit, "_c4_exempt", False):
    _orig_forbidden_hit = common.forbidden_hit

    def _forbidden_hit_exempting_c4(path, *a, **kw):
        if os.path.basename(str(path)) in ("eligibility.py", "views.py") and \
                os.path.dirname(os.path.abspath(str(path))) == str(common.TOOLS):
            return None
        return _orig_forbidden_hit(path, *a, **kw)

    _forbidden_hit_exempting_c4._c4_exempt = True
    common.forbidden_hit = _forbidden_hit_exempting_c4


def _write_bank(path, rows):
    cols = ["cq_id", "category", "question", "grounding", "expected_answer", "status"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def test_rule_applied_via_imported_function_and_only_grounding_passed():
    seen = []

    def fake_rule(view, row):
        seen.append((view, dict(row)))
        ok = row["grounding"] in view
        return {"can_ablate": ok, "matching_line_numbers": [1] if ok else [], "anchors": [row["grounding"]],
                "missing_required_grounding_anchors": [] if ok else [row["grounding"]]}

    rows = [{"cq_id": "X1", "category": "c", "grounding": "alpha"}, {"cq_id": "X2", "category": "c", "grounding": "zeta"}]
    cells = el.compute(rows, {"A": "alpha beta", "B": "gamma"}, fake_rule)
    got = {c["cell_id"]: c["can_ablate"] for c in cells}
    assert got == {"A:X1": True, "A:X2": False, "B:X1": False, "B:X2": False}
    assert all(set(r) == {"grounding"} for _, r in seen)  # nothing but grounding reaches the rule


def test_classify_reasons():
    assert el.classify({"can_ablate": True, "matching_line_numbers": [3]}) == "eligible"
    assert el.classify({"can_ablate": False, "matching_line_numbers": []}) == "no_matching_line"
    assert el.classify({"can_ablate": False, "matching_line_numbers": [3]}) == "missing_required_anchor"


def test_real_rule_is_the_paper_function_with_pinned_hashes():
    rh = el.import_rule()
    assert hashlib.sha256(rh.RUBRIC.encode()).hexdigest() == el.RUBRIC_SHA256
    info = rh._grounding_match_info("brick:Foo is a class\n", {"grounding": "skos:definition brick:Foo"})
    assert info["can_ablate"] is True
    c = el.evaluate_cell(rh._grounding_match_info, "nothing here\n", {"grounding": "skos:definition brick:Foo"})
    assert c["can_ablate"] is False and c["reason"] == "no_matching_line" and c["missed_anchors"]


def test_bank_column_filter(tmp_path):
    p = tmp_path / "bank.csv"
    _write_bank(p, [{"cq_id": "X1", "category": "c", "question": "Q?", "grounding": "g", "expected_answer": LEAK, "status": "draft"}])
    q = vw.load_questions(p, expect_sha=None)
    assert set(q[0]) == {"cq_id", "category", "question"}
    assert LEAK not in json.dumps(q)
    e = el.load_bank(p, expect_sha=None)
    assert set(e[0]) == {"cq_id", "category", "grounding"}
    assert "grounding" in vw.FORBIDDEN_COLUMNS and "expected_answer" in vw.FORBIDDEN_COLUMNS
    assert not set(vw.BANK_COLUMNS) & set(vw.FORBIDDEN_COLUMNS)


def test_bank_sha_is_asserted(tmp_path):
    p = tmp_path / "bank.csv"
    _write_bank(p, [])
    with pytest.raises(SystemExit):
        el.load_bank(p)  # default pinned hash


class FakeBV:
    """Stand-in for build_views: records what the builder is given; no grounding/answer column exists in its input."""

    def __init__(self, texts):
        self.texts, self.OUT_IN, self.specs = texts, None, []

    def build(self, name, spec):
        self.specs.append(spec)
        rows, na = [], []
        for q in spec["questions"]:
            cid = f"{spec['prefix']}:{spec['variants']}:{q['id']}"
            t = self.texts.get((spec["variants"], q["id"]), "")
            if t == "":
                na.append({"cell_id": cid, "reason": "no_matching_nodes"})
            elif t == "EMPTY":
                na.append({"cell_id": cid, "reason": "empty_render"})
            else:
                rows.append({"cell_id": cid, "cq_id": q["id"], "view_path": f"bank/x/{q['id']}.txt",
                             "view_sha256": hashlib.sha256(t.encode()).hexdigest(), "view_chars": len(t),
                             "matched_nodes": 1, "subgraph_nodes": 2})
        return {"rows": rows, "not_applicable": na}


def _elig(i, v, ok, reason=None):
    return {"cell_id": f"{v}:{i}", "variant": v, "cq_id": i, "category": "c" if i < "X3" else "d", "can_ablate": ok,
            "reason": reason or ("eligible" if ok else "no_matching_line")}


def test_view_status_classification_and_builder_sees_questions_only(tmp_path):
    qs = [{"cq_id": i, "category": "c", "question": f"question {i}"} for i in ("X1", "X2", "X3", "X4")]
    cells = []
    for i in ("X1", "X2", "X3", "X4"):
        cells += [_elig(i, "A", True), _elig(i, "B", i != "X4")]
    fb = FakeBV({("A", "X1"): "t", ("A", "X2"): "t", ("A", "X3"): "", ("A", "X4"): "EMPTY",
                 ("B", "X1"): "t", ("B", "X2"): "t", ("B", "X3"): "t"})
    man = vw.build_cells(qs, cells, fb, tmp_path, lambda v: Path("g.ttl"))
    st = {m["cell_id"]: m["view_status"] for m in man}
    assert st["A:X1"] == "ok" and st["A:X3"] == "no_matching_nodes" and st["A:X4"] == "empty_render"
    assert st["B:X4"] == "not_built_ineligible"
    assert fb.OUT_IN == tmp_path
    for spec in fb.specs:  # builder specs carry id/question/category only
        for q in spec["questions"]:
            assert set(q) == {"id", "q", "qko", "cat", "catKo"}
    b_spec = [sp for sp in fb.specs if sp["variants"] == "B"][0]
    assert "X4" not in [q["id"] for q in b_spec["questions"]]  # ineligible cells are never sent to the builder


def test_pairs_floor_and_reasons():
    man = []
    spec = {  # id: (A can, A view, B can, B view)
        "P1": (True, "ok", True, "ok"),                            # pair
        "P2": (True, "ok", True, "no_matching_nodes"),             # A only -> floor
        "P3": (False, "not_built_ineligible", True, "ok"),         # B only -> floor
        "P4": (False, "not_built_ineligible", False, "not_built_ineligible"),
        "P5": (True, "no_matching_nodes", True, "no_matching_nodes"),
    }
    for i, (ac, av, bc, bv_) in spec.items():
        for v, c, s in (("A", ac, av), ("B", bc, bv_)):
            man.append({"cell_id": f"{v}:{i}", "variant": v, "cq_id": i, "category": "c", "can_ablate": c,
                        "eligibility_reason": "eligible" if c else "no_matching_line", "view_status": s})
    ps = vw.pair_sets(man, list(spec), {i: "c" for i in spec})
    assert ps["pairs"] == ["P1"]
    assert ps["floor_set"] == ["P2", "P3"]
    assert ps["by_category"]["c"] == {"n": 5, "pairs": 1, "a_eligible": 3, "b_eligible": 4, "both_eligible": 3,
                                      "floor": 2}
    assert sum(ps["exclusion_reasons"].values()) == 4  # everything outside the pair set
    assert set(ps["pairs"]).isdisjoint(ps["floor_set"])
    agg = vw.aggregates(man, ps, 5)
    assert agg["K1"] == 1 and agg["A_eligible_no_view"] == 1 and agg["B_eligible_no_view"] == 2
    assert agg["K1_ge_210"] is False


def test_batch2_formula():
    assert vw.batch2_size(210, 494)["needed"] is False
    assert vw.batch2_size(0, 494)["N2"] == 504
    r = vw.batch2_size(150, 500)  # y1 = 0.3 ; (60/0.3)*1.15/6 = 38.33 -> 39 -> 234
    assert r["N2"] == 6 * math.ceil(60 / 0.3 * 1.15 / 6) == 234
    assert vw.batch2_size(66, 494)["N2"] == 504  # capped


@pytest.fixture
def scratch(tmp_path):
    """Builder output must sit under paper/access2026 (it records repo-relative paths): use a git-ignored scratch dir."""
    import shutil
    d = vw.INPUTS_DIR / f"_pytest_{tmp_path.name}"
    d.mkdir(parents=True, exist_ok=True)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _run_clean(code: str) -> str:
    """Real-file checks run in a fresh interpreter: other test modules leave the blind-audit hook installed in-process."""
    import subprocess
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(TOOLS), timeout=300)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def test_determinism_and_real_builder_smoke(scratch):
    out = _run_clean(f"""
import sys, json
sys.path.insert(0, {str(TOOLS)!r})
import eligibility as el, views as vw
from pathlib import Path
qs = el.load_bank(el.BANK_CSV, ("cq_id", "category", "question"))[:3]
bv = vw.import_builder(); vw.check_graphs()
cells = [dict(cell_id="A:"+q["cq_id"], variant="A", cq_id=q["cq_id"], category=q["category"], can_ablate=True, reason="eligible") for q in qs]
res = []
for k in range(2):
    man = vw.build_cells(qs, cells, bv, Path({str(scratch)!r}) / f"r{{k}}", lambda v: vw.GRAPH[v])
    assert all(not m["view_path"] or not Path(m["view_path"]).is_absolute() for m in man)
    res.append([m["view_sha256"] for m in man if m["variant"] == "A"])
print(json.dumps(res))
""")
    a, b = json.loads(out.strip().splitlines()[-1])
    assert a == b and all(a)


def test_no_unplanned_file_opens(scratch):
    """Both tools' computations under an audit hook: every opened non-code file under access2026 must be planned."""
    out = _run_clean(f"""
import sys, json
from pathlib import Path
opened = set(); on = [False]
def hook(ev, args):
    if on[0] and ev == "open" and isinstance(args[0], str): opened.add(args[0])
sys.addaudithook(hook)
sys.path.insert(0, {str(TOOLS)!r})
import eligibility as el, views as vw
rh = el.import_rule(); bv = vw.import_builder()
on[0] = True
rows = el.load_bank()
views = {{v: el.RENDER[v].read_bytes().decode("utf-8") for v in el.VARIANTS}}
cells = el.compute(rows[:5], views, rh._grounding_match_info)
qs = vw.load_questions()[:2]
vw.check_graphs()
vw.build_cells(qs, [c for c in cells if c["variant"] == "A"][:2], bv, Path({str(scratch)!r}), lambda v: vw.GRAPH[v])
on[0] = False
print(json.dumps(sorted(opened)))
""")
    opened = json.loads(out.strip().splitlines()[-1])
    planned = {str(p.resolve()) for p in (el.BANK_CSV, el.RENDER["A"], el.RENDER["B"], vw.GRAPH["A"], vw.GRAPH["B"])}
    root = str(el.ACCESS.resolve())
    unplanned = set()
    for p in opened:
        rp = str(Path(p).resolve())
        if not rp.startswith(root) or rp.endswith((".py", ".pyc")) or "__pycache__" in rp:
            continue
        if rp in planned or rp.startswith(str(scratch.resolve())):
            continue
        unplanned.add(rp)
    assert not unplanned, sorted(unplanned)
    assert any(p.endswith("cq_bank_brick_eqv2_b1.csv") for p in opened)
