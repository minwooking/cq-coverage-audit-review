"""Tests for real_run/ask_alignment/ask_alignment.py on synthetic fixtures.

The mapping rules and the query rewriting are checked on small hand-written vocabularies,
graphs and queries; no holdout data is needed except by the one provenance test, which only
compares sha256 values of the committed outputs with the input files.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "real_run" / "ask_alignment" / "ask_alignment.py"
_spec = importlib.util.spec_from_file_location("ask_alignment", SCRIPT)
aa = importlib.util.module_from_spec(_spec)
sys.modules["ask_alignment"] = aa          # dataclasses resolves string annotations through sys.modules
_spec.loader.exec_module(aa)

BRICK = "https://brickschema.org/schema/Brick#"
REC = "https://w3id.org/rec#"
CT = aa.CT_NS


def vocab(*specs):
    """specs: local name, or (local name, [labels])."""
    terms = []
    for spec in specs:
        local, labels = (spec, []) if isinstance(spec, str) else spec
        terms.append(aa.CtTerm(iri=CT + local, local=local, labels=list(labels)))
    return aa.CtVocab(terms)


def mapped(local, v, labels=(), prefix="brick"):
    return aa.map_term(BRICK + local, prefix, local, list(labels), v)


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text, tokens", [
    ("hasPoint", ("has", "point")),
    ("HVAC_Equipment", ("hvac", "equipment")),
    ("Outdoor_Area", ("outdoor", "area")),
    ("outdoor-area", ("outdoor", "area")),
    ("Has point", ("has", "point")),
    ("haspoint", ("haspoint",)),
    ("isSubMeterOf", ("is", "sub", "meter", "of")),
])
def test_norm_tokens(text, tokens):
    assert aa.norm_tokens(text) == tokens


def test_norm_joined_drops_token_boundaries():
    assert {aa.norm_joined(t) for t in ("hasPoint", "has_point", "has-point", "Has point", "haspoint")} == {"haspoint"}


# ---------------------------------------------------------------------------
# mapping rules, one fixture per rule
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("local, ct_locals, expected_rule, expected_ct", [
    ("Sensor", ["Sensor", "sensor"], "local_exact", "Sensor"),
    ("Outdoor_Area", ["outdoor-area"], "local_normalized", "outdoor-area"),
    ("hasPoint", ["haspoint"], "local_joined", "haspoint"),
    ("hasPoint", ["brick_hasPoint"], "ns_prefixed_local", "brick_hasPoint"),
    ("hasPoint", ["brick-haspoint"], "ns_prefixed_local", "brick-haspoint"),
])
def test_local_name_rules(local, ct_locals, expected_rule, expected_ct):
    res = mapped(local, vocab(*ct_locals))
    assert (res.status, res.rule, res.ct_iri) == ("mapped", expected_rule, CT + expected_ct)


def test_label_rule_matches_ct_label():
    v = vocab(("term-7", ["Has Point"]))
    res = mapped("hasPoint", v, labels=["Has point"])
    assert (res.status, res.rule, res.ct_iri) == ("mapped", "label", CT + "term-7")


def test_label_to_local_rule_matches_ct_local_name():
    v = vocab("deprecation-notice")
    res = mapped("deprecation", v, labels=["Deprecation Notice"])
    assert (res.status, res.rule, res.ct_iri) == ("mapped", "label_to_local", CT + "deprecation-notice")


def test_rule_priority_first_rule_with_a_candidate_decides_and_others_are_alternates():
    v = vocab("hasPoint", ("brick_hasPoint", ["hasPoint"]))
    res = mapped("hasPoint", v, labels=["Has point"])
    assert res.rule == "local_exact" and res.ct_iri == CT + "hasPoint"
    assert res.alt_candidates["label"] == [CT + "brick_hasPoint"]
    assert res.alt_candidates["ns_prefixed_local"] == [CT + "brick_hasPoint"]
    assert set(res.all_candidates) == {CT + "hasPoint", CT + "brick_hasPoint"}


def test_ambiguity_within_the_deciding_rule_is_not_resolved_by_picking_one():
    res = mapped("Region", vocab("region_a", ("x", ["Region"]), ("y", ["Region"])), labels=["Region"])
    assert res.rule == "label" and res.status == "ambiguous"
    assert res.top_candidates == [CT + "x", CT + "y"] and res.ct_iri == ""


def test_unmapped_when_no_rule_finds_anything():
    res = mapped("yearBuilt", vocab("sensor", "point"), labels=["Year built"])
    assert (res.status, res.rule, res.ct_iri, res.all_candidates) == ("unmapped", "", "", [])


def test_ns_prefix_rule_uses_the_prefix_of_the_terms_own_namespace():
    v = vocab("rec-point", "brick-point")
    assert mapped("Point", v).ct_iri == CT + "brick-point"
    rec = aa.map_term(REC + "Point", "rec", "Point", [], v)
    assert rec.ct_iri == CT + "rec-point"


def test_vocab_excludes_pipeline_scaffolding_and_reads_labels():
    g = Graph()
    g.parse(format="turtle", data=f"""
        @prefix ct: <{CT}> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        ct:sensor a ct:Class_class ; skos:prefLabel "sensor" ; ct:p_subclass ct:point .
        ct:point rdfs:label "Point" ; skos:broader ct:section_classes .
    """)
    v = aa.ct_vocab_from_graph(g)
    assert set(v.terms) == {CT + "sensor", CT + "point"}
    assert v.n_scaffold_excluded == 3          # Class_class, p_subclass, section_classes
    assert v.terms[CT + "sensor"].labels == ["sensor"] and v.terms[CT + "point"].labels == ["Point"]
    # Class_alarm must never be offered as the counterpart of brick:Alarm
    g.parse(format="turtle", data=f"@prefix ct: <{CT}> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> . "
                                  'ct:Class_alarm skos:prefLabel "alarm" .')
    assert mapped("Alarm", aa.ct_vocab_from_graph(g), labels=["Alarm"]).status == "unmapped"


# ---------------------------------------------------------------------------
# query parsing / rewriting (queries only)
# ---------------------------------------------------------------------------
HEADER = f"""PREFIX brick: <{BRICK}>
PREFIX rec: <{REC}>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX sh: <http://www.w3.org/ns/shacl#>
"""


def test_query_terms_lists_distinct_rewritable_terms_only():
    q = HEADER + "ASK { brick:Sensor rdfs:subClassOf brick:Point . brick:Sensor a owl:Class . ?s sh:path rec:locatedIn }"
    assert aa.query_terms(q) == sorted([(BRICK, "Sensor"), (BRICK, "Point"), (REC, "locatedIn")])


def test_rewrite_replaces_prefixed_and_full_iris_and_keeps_core_vocabulary():
    q = HEADER + (f"ASK {{ brick:Sensor rdfs:subClassOf <{BRICK}Point> . "
                  f"?s sh:path rec:locatedIn . brick:hasPoint owl:inverseOf brick:isPointOf }}")
    mapping = {BRICK + "Sensor": CT + "sensor", BRICK + "Point": CT + "point", REC + "locatedIn": CT + "rec-locatedin",
               BRICK + "hasPoint": CT + "brick-haspoint", BRICK + "isPointOf": CT + "brick-ispointof"}
    out, missing = aa.rewrite_query(q, mapping)
    assert missing == []
    assert out == (f"ASK {{ <{CT}sensor> rdfs:subClassOf <{CT}point> . ?s sh:path <{CT}rec-locatedin> . "
                   f"<{CT}brick-haspoint> owl:inverseOf <{CT}brick-ispointof> }}\n")
    assert "PREFIX" not in out and "brickschema" not in out
    # the rewritten query is valid SPARQL
    assert aa.run_ask(Graph(), out) is False


def test_rewrite_does_not_touch_strings_comments_or_longer_prefixed_names():
    q = HEADER + 'ASK { ?s rdfs:comment "see brick:Sensor" . # brick:Point in a comment\n ?s brick:Sensor ?o . ?s xbrick:Sensor ?o }'
    out, missing = aa.rewrite_query(q, {BRICK + "Sensor": CT + "sensor"})
    assert '"see brick:Sensor"' in out and "# brick:Point in a comment" in out
    assert f"<{CT}sensor> ?o" in out and "xbrick:Sensor" in out
    assert missing == []


def test_rewrite_reports_terms_without_mapping():
    q = HEADER + "ASK { brick:Sensor rdfs:subClassOf brick:Point }"
    out, missing = aa.rewrite_query(q, {BRICK + "Sensor": CT + "sensor"})
    assert missing == [BRICK + "Point"] and "brick:Point" in out


def test_core_predicates_used():
    q = HEADER + "ASK { brick:A rdfs:subClassOf brick:B . brick:A owl:inverseOf brick:C . ?x a owl:Class }"
    assert aa.core_predicates_used(q) == ["owl:inverseOf", "rdfs:subClassOf"]


# ---------------------------------------------------------------------------
# evaluation: true / false / not evaluable
# ---------------------------------------------------------------------------
GRAPH_TTL = f"""
@prefix ct: <{CT}> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
ct:Sensor rdfs:subClassOf ct:Point .
ct:Alarm rdfs:subClassOf ct:Point .
ct:hasPoint a owl:ObjectProperty .
ct:brick_hasPoint owl:inverseOf ct:brick_isPointOf .
"""


@pytest.fixture(scope="module")
def graph():
    g = Graph()
    g.parse(format="turtle", data=GRAPH_TTL)
    return g


def results_for(v, *locals_):
    return {BRICK + loc: aa.map_term(BRICK + loc, "brick", loc, [], v) for loc in locals_}


def evaluate(graph, v, query_body, *locals_):
    q = HEADER + query_body
    return aa.evaluate_cq(graph, q, [BRICK + loc for loc in locals_], results_for(v, *locals_))


def test_verbatim_brick_query_is_false_on_a_ct_graph_but_rewritten_query_is_true(graph):
    q = HEADER + "ASK { brick:Sensor rdfs:subClassOf brick:Point }"
    assert aa.run_ask(graph, q) is False                              # the namespace artifact
    v = vocab("Sensor", "Point", "Alarm")
    assert evaluate(graph, v, "ASK { brick:Sensor rdfs:subClassOf brick:Point }", "Sensor", "Point")["outcome"] == "true"


def test_a_mapped_term_missing_the_fact_is_false_not_unevaluable(graph):
    v = vocab("Sensor", "Point", "Alarm")
    out = evaluate(graph, v, "ASK { brick:Point rdfs:subClassOf brick:Sensor }", "Sensor", "Point")
    assert out["outcome"] == "false" and out["unmapped_terms"] == []


def test_an_unmapped_term_makes_the_query_not_evaluable_never_false(graph):
    v = vocab("Sensor", "Point")
    out = evaluate(graph, v, "ASK { brick:Sensor rdfs:subClassOf brick:Wing }", "Sensor", "Wing")
    assert out["outcome"] == "not_evaluable" and out["unmapped_terms"] == ["brick:Wing"]
    assert out["rewritten_query_sha256"] is None


def test_an_ambiguous_term_is_not_evaluable_and_reported(graph):
    v = vocab("Sensor", "point-a", ("point-b", ["Point"]), ("point-c", ["Point"]))
    res = {BRICK + "Sensor": mapped("Sensor", v), BRICK + "Point": mapped("Point", v, labels=["Point"])}
    assert res[BRICK + "Point"].status == "ambiguous"
    q = HEADER + "ASK { brick:Sensor rdfs:subClassOf brick:Point }"
    out = aa.evaluate_cq(graph, q, list(res), res)
    assert out["outcome"] == "not_evaluable" and out["ambiguous_terms"] == ["brick:Point"]
    assert out["unmapped_terms"] == []


def test_absent_core_predicates_are_reported_for_the_query(graph):
    v = vocab("Sensor", "Point")
    res = results_for(v, "Sensor", "Point")
    q = HEADER + "ASK { brick:Sensor owl:inverseOf brick:Point }"
    out = aa.evaluate_cq(graph, q, [BRICK + "Sensor", BRICK + "Point"], res, absent_core_predicates=["owl:inverseOf"])
    assert out["outcome"] == "false" and out["core_predicates_absent"] == ["owl:inverseOf"]


def test_any_candidate_run_brackets_the_single_candidate_choice(graph):
    # exact tier picks ct:hasPoint (no inverse); the prefixed ct:brick_hasPoint carries the fact
    v = vocab("hasPoint", "brick_hasPoint", "brick_isPointOf")
    body = "ASK { brick:hasPoint owl:inverseOf brick:isPointOf }"
    out = evaluate(graph, v, body, "hasPoint", "isPointOf")
    assert out["outcome"] == "false" and out["any_candidate_outcome"] == "true"


def test_any_candidate_cap_and_no_candidate(graph):
    many = vocab(*[f"brick-t{i}" for i in range(3)], *[f"t{i}" for i in range(3)])
    res = {BRICK + f"t{i}": aa.map_term(BRICK + f"t{i}", "brick", f"t{i}", [], many) for i in range(3)}
    q = HEADER + "ASK { brick:t0 rdfs:subClassOf brick:t1 . brick:t1 rdfs:subClassOf brick:t2 }"
    assert aa.any_candidate_outcome(graph, q, res, cap=4) == "cap_exceeded"    # 2*2*2 = 8 > 4
    assert aa.any_candidate_outcome(graph, q, res, cap=8) == "false"
    res[BRICK + "t9"] = aa.map_term(BRICK + "t9", "brick", "t9", [], many)
    assert aa.any_candidate_outcome(graph, q + "", res) == "not_evaluable"


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def test_cohen_kappa_known_table():
    k = aa.cohen_kappa(20, 5, 10, 15)       # po = .70, pe = .50
    assert k["kappa"] == pytest.approx(0.4) and k["percent_agreement"] == pytest.approx(0.7)


def test_cohen_kappa_degenerate_cases():
    assert aa.cohen_kappa(0, 0, 3, 9)["kappa"] == pytest.approx(0.0)      # one rater constant -> 0
    undefined = aa.cohen_kappa(0, 0, 0, 9)                                 # both constant -> undefined
    assert undefined["kappa"] is None and "undefined" in undefined["reason"]
    assert aa.cohen_kappa(0, 0, 0, 0)["kappa"] is None


class StubAh:
    """Stands in for analyze_holdout: point estimate only, no resampling."""
    @staticmethod
    def cluster_bootstrap_stat(cells, stat_fn, strata_key, cluster_key, B, seed, ties):
        return {"estimate": stat_fn(list(cells)), "ci_lo": 0.0, "ci_hi": 1.0, "n_cells": len(cells),
                "n_clusters": len({c[cluster_key] for c in cells}), "tie_share": 0.0}


def test_analyse_joins_primary_cells_and_excludes_not_evaluable():
    def o(cq, v, outcome, any_out=None):
        return {"cq_id": cq, "variant": v, "cluster_id": cq, "category": "x", "outcome": outcome,
                "any_candidate_outcome": any_out or outcome}
    outcomes = [o("Q1", "A", "true"), o("Q2", "A", "false"), o("Q3", "A", "not_evaluable"),
                o("Q1", "B", "false"), o("Q4", "B", "true")]          # Q4/B has no primary cell
    primary = {("Q1", "A"): {"cluster_id": "Q1", "J": 3, "A": 1},
               ("Q2", "A"): {"cluster_id": "Q2", "J": 1, "A": 0},
               ("Q3", "A"): {"cluster_id": "Q3", "J": 3, "A": 1},      # not evaluable -> out of the 2x2
               ("Q1", "B"): {"cluster_id": "Q1", "J": 2, "A": 1}}
    res = aa.analyse(outcomes, primary, StubAh)
    assert res["ask_counts"]["overall"] == {"true": 2, "false": 2, "not_evaluable": 1, "total": 5}
    conc = res["concordance"]
    assert conc["universe"] == {**conc["universe"], "primary_cells_on_ask_cqs": 4, "evaluable_primary_cells": 3}
    j = conc["ask_vs_judge_J_ge_2"]
    assert j["table"] == {"ask_true__other_1": 1, "ask_true__other_0": 0,
                          "ask_false__other_1": 1, "ask_false__other_0": 1}
    assert j["kappa"] == pytest.approx(0.4) and j["bca_kappa"]["estimate"] == pytest.approx(0.4)
    a = conc["ask_vs_ah_label_A"]
    assert a["table"]["ask_true__other_1"] == 1 and a["table"]["ask_false__other_0"] == 1
    pv = res["per_variant"]["A"]
    assert (pv["primary_cells_on_ask_cqs"], pv["evaluable_cells"], pv["ask_true_cells"]) == (3, 2, 1)
    assert pv["ask_pass_rate_over_evaluable"] == 0.5
    assert pv["judge_coverage_pct_on_primary_ask_cells"] == pytest.approx(100 * (3 + 1 + 3) / 9)
    assert res["per_variant"]["C"]["evaluable_cells"] == 0 and res["per_variant"]["C"]["ask_pass_rate_over_evaluable"] is None


def test_registered_bootstrap_constants_are_the_analyzers():
    sys.path.insert(0, str(HERE))
    import analyze_holdout as ah
    assert (ah.BOOTSTRAP_RESAMPLES, ah.REGISTERED_SEED) == (aa.BOOTSTRAP_B, aa.BOOTSTRAP_SEED) == (10_000, 20260913)


# ---------------------------------------------------------------------------
# provenance of the committed outputs
# ---------------------------------------------------------------------------
def test_outputs_record_the_current_input_hashes():
    out = SCRIPT.parent / "ask_results.json"
    if not out.is_file():
        pytest.skip("ask_results.json not generated yet")
    data = json.loads(out.read_text(encoding="utf-8"))
    for name, rel in aa.INPUT_FILES.items():
        assert data["inputs_sha256"][name] == aa.sha256_file(aa.ROOT / rel), name
    assert data["mapping_csv_sha256"] == aa.sha256_file(SCRIPT.parent / "mapping.csv")
    assert data["script_sha256"] == aa.sha256_file(SCRIPT)
