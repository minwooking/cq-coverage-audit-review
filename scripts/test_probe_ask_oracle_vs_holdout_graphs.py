from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("probe_ask_oracle_vs_holdout_graphs.py")
spec = importlib.util.spec_from_file_location("probe_ask_oracle_vs_holdout_graphs", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)


def test_eighteen_cqs_are_ask_expressible_yes():
    rows = probe.load_ask_expressible_rows()
    assert len(rows) == 18
    assert {row["cq_id"] for row in rows} == {
        "CQB07", "CQB08", "CQB09", "CQB10", "CQB11", "CQB12", "CQB13", "CQB14",
        "CQB15", "CQB16", "CQB17", "CQB18", "CQB21", "CQB22", "CQB23", "CQB24",
        "CQB32", "CQB33",
    }


def test_variant_graphs_load_and_use_pipeline_local_namespace_not_canonical_brick():
    # This is the regression lock for PREREG.md section 7's finding: as of this
    # holdout run, every variant graph renders Brick concepts under the
    # pipeline-local http://example.org/chunktograph# namespace, not the
    # canonical https://brickschema.org/schema/Brick# the bank's ASK queries
    # are written against. If this ever fails, the namespace-mismatch finding
    # in PREREG.md section 7 and main.tex's ASK-oracle-concordance paragraph
    # needs re-review, not a widened assertion.
    graphs = probe.load_variant_graphs()
    assert set(graphs) == {"A", "B", "C", "D", "E", "F"}
    for variant, graph in graphs.items():
        assert len(graph) > 0, f"variant {variant} graph is empty"
        assert probe.canonical_brick_iri_count(graph) == 0, (
            f"variant {variant} now contains canonical Brick IRIs; the "
            "ASK-oracle-vs-holdout-graphs blocker may no longer apply"
        )


def test_canonical_ask_queries_return_false_uniformly_against_current_holdout_graphs():
    rows = probe.load_ask_expressible_rows()
    graphs = probe.load_variant_graphs()
    results = []
    for row in rows:
        query_text = (probe.BASE / "bank" / row["ask_query_file"]).read_text(encoding="utf-8")
        for graph in graphs.values():
            results.append(bool(graph.query(query_text)))
    assert len(results) == 18 * 6
    assert not any(results), (
        "a canonical-namespace ASK query returned true against a holdout graph; "
        "the namespace-mismatch finding in PREREG.md section 7 may be stale"
    )
