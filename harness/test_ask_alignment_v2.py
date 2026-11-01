"""Tests for real_run/ask_alignment_v2/run_oracle_v2.py (addendum 16).

Rule tests use small synthetic graphs. The regression and determinism tests run the real
pipeline once (about a minute) and are marked slow-ish but are not skipped.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from rdflib import Graph

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "real_run" / "ask_alignment"))
_spec = importlib.util.spec_from_file_location("run_oracle_v2", HERE / "real_run" / "ask_alignment_v2" / "run_oracle_v2.py")
r2 = importlib.util.module_from_spec(_spec)
sys.modules["run_oracle_v2"] = r2
_spec.loader.exec_module(r2)
aa = r2.aa

CT = aa.CT_NS
RULES = r2.active_rules(r2.load_predicate_map(ROOT))
PFX = ("PREFIX brick: <https://brickschema.org/schema/Brick#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
       "PREFIX owl: <http://www.w3.org/2002/07/owl#>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
       "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n")


def run(ttl: str, body: str) -> bool:
    g = Graph()
    g.parse(data="@prefix ex: <%s> .\n@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
                 "@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n%s" % (CT, ttl), format="turtle")
    q, _ = r2.rewrite_predicates(PFX + body, RULES)
    # terms are already ct: IRIs in these fixtures, so only step 7 is exercised
    return bool(g.query(q).askAnswer)


def test_rule_counts():
    rows = r2.load_predicate_map(ROOT)
    assert len(rows) == 18
    assert sum(r["status"] == "active" for r in rows) == 7
    assert {r["variant_predicate"].split("#")[-1] for r in rows if r["status"] == "excluded"} == {"p_is-a", "p_is", "p_be", "p_is-an", "p_are"}


@pytest.mark.parametrize("pred", ["ex:p_subclass", "skos:broader"])
def test_subclass_rules_forward(pred):
    ttl = f"ex:zone {pred} ex:location ."
    assert run(ttl, "ASK { ex:zone rdfs:subClassOf ex:location }")
    assert not run(ttl, "ASK { ex:location rdfs:subClassOf ex:zone }")      # direction is not reversed


@pytest.mark.parametrize("pred", ["ex:p_is-a", "ex:p_is", "ex:p_be", "ex:p_is-an", "ex:p_are"])
def test_copula_predicates_are_not_mapped(pred):
    assert not run(f"ex:zone {pred} ex:location .", "ASK { ex:zone rdfs:subClassOf ex:location }")


def test_inverse_symmetric_for_ct_only():
    ttl = "ex:a ex:p_inverse ex:b ."
    assert run(ttl, "ASK { ex:a owl:inverseOf ex:b }")
    assert run(ttl, "ASK { ex:b owl:inverseOf ex:a }")          # symmetric for ex:p_inverse
    assert run("ex:a owl:inverseOf ex:b .", "ASK { ex:a owl:inverseOf ex:b }")
    assert not run("ex:a owl:inverseOf ex:b .", "ASK { ex:b owl:inverseOf ex:a }")  # no symmetry added to native owl:inverseOf


def test_definition_label_type_rules():
    assert run("ex:t ex:p_define ex:text .", "ASK { ex:t skos:definition ?d }")
    assert run('ex:t skos:definition "x" .', "ASK { ex:t skos:definition ?d }")   # identity
    assert run('ex:t ex:p_label "zone" .', "ASK { ex:t rdfs:label ?l }")
    assert run('ex:t skos:prefLabel "zone" .', "ASK { ex:t rdfs:label ?l }")
    assert run("ex:t ex:p_class-schema ex:schema .", "ASK { ex:t rdf:type ex:schema }")


def test_no_analogue_predicates_untouched():
    q, fired = r2.rewrite_predicates(PFX + "ASK { ex:a rdfs:comment ?c . ex:a owl:disjointWith ex:b }", RULES)
    assert fired == [] and "p_" not in q


def test_rewrite_reports_fired_rules_and_does_not_touch_strings():
    q, fired = r2.rewrite_predicates(PFX + 'ASK { ?c rdfs:subClassOf ex:x . # rdfs:subClassOf in a comment\n FILTER(?s != "rdfs:subClassOf") }', RULES)
    assert fired == ["P1", "P2"]
    assert '"rdfs:subClassOf"' in q and "# rdfs:subClassOf in a comment" in q


def test_predicate_absent_flag():
    g = Graph()
    g.parse(data="@prefix ex: <%s> .\nex:a ex:p_subclass ex:b .\n" % CT, format="turtle")
    q = PFX + "ASK { ?x rdfs:subClassOf ?y . ?x owl:disjointWith ?y }"
    assert r2.absent_predicates(g, q, RULES) == ["owl:disjointWith"]        # subClassOf is present through P1


def test_v2_queries_equal_v1_modulo_rdf_type():
    import re
    for f in sorted((ROOT / "bank" / "ask_queries_v2").glob("CQB*.rq")):
        v1 = (ROOT / "bank" / "ask_queries" / f.name).read_text().split("\n\n", 1)[1]
        v2 = f.read_text().split("\n\n", 1)[1]
        assert re.sub(r'(?<![\w:<?"\'-])a(?=\s+[a-z]+:)', "rdf:type", v1) == v2, f.name


@pytest.fixture(scope="module")
def two_runs(tmp_path_factory):
    outs = []
    for i in range(2):
        d = tmp_path_factory.mktemp(f"run{i}")
        res, rows = r2.build(ROOT)
        r2.write_outputs(res, rows, d)
        outs.append(d)
    return outs


def test_determinism_byte_identical(two_runs):
    for name in ("ask_results_v2.json", "mapping_v2.csv", "comparison_v2.md"):
        assert (two_runs[0] / name).read_bytes() == (two_runs[1] / name).read_bytes(), name


def test_before_equals_v1_and_mapping_unchanged(two_runs):
    res = json.loads((two_runs[0] / "ask_results_v2.json").read_text())
    v1 = json.loads((ROOT / r2.V1_RESULTS).read_text())
    old = {(o["cq_id"], o["variant"]): o["outcome"] for o in v1["per_cq_variant"]}
    new = {(o["cq_id"], o["variant"]): o["before_outcome"] for o in res["per_cq_variant"] if o["class"] == "deterministic"}
    assert new == old
    import csv
    v1m = {(r["variant"], r["brick_term"]): (r["status"], r["rule"], r["ct_iri"]) for r in csv.DictReader((ROOT / r2.V1_MAPPING).open())}
    v2m = {(r["variant"], r["brick_term"]): (r["status"], r["rule"], r["ct_iri"]) for r in csv.DictReader((two_runs[0] / "mapping_v2.csv").open())}
    assert all(v2m[k] == v for k, v in v1m.items())


def test_graphs_untouched_and_schema(two_runs):
    res = json.loads((two_runs[0] / "ask_results_v2.json").read_text())
    for o in res["per_cq_variant"]:
        assert {"before_outcome", "after_outcome", "predicate_map_applied"} <= set(o)
    assert res["config"]["active_rewrite_rules"] == 7
