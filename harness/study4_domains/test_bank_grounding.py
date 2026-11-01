"""Bank grounding check (addendum 35 PLAN 35.4): every grounding term of every bank row exists in the frozen ontology snapshot.
AI-generated; review before reuse.  Run: .venv/bin/python -m pytest harness/study4_domains/test_bank_grounding.py  (needs `fetch_sources.py <d>` first)."""
import csv
import sys
from pathlib import Path

import pytest
from rdflib import Graph, URIRef, BNode

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import s4_common as C  # noqa: E402
import run_holdout as rh  # noqa: E402

CATS = {"concept_definition", "taxonomy", "relations", "slots_facets", "instances", "methodology"}
FIELDS = ["cq_id", "category", "question", "grounding", "expected_answer", "status", "cluster_id", "created"]


def snapshot_locals(d):
    g = Graph()
    for _, _, _ in []:
        pass
    for fn, _, _ in C.DOMAINS[d]["ontology"]:
        g.parse(C.ddir(d) / "raw" / fn, format="turtle")
    out = set()
    for t in g:
        for x in t:
            if isinstance(x, URIRef):
                u = str(x)
                out.add(u.split("#")[-1] if "#" in u else u.rstrip("/").rsplit("/", 1)[-1])
    return out


def bank_rows(d):
    p = C.ddir(d) / "bank" / f"bank_{d}_v1.csv"
    if not p.exists():
        pytest.skip("no bank")
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def grounding_terms(grounding):
    """Real term names of a grounding string (control prefixes and metadata predicates removed)."""
    terms = []
    for a in rh._grounding_anchors(grounding):
        terms.append(a.split(":", 1)[1] if ":" in a else a)
    return sorted(set(terms))


@pytest.mark.parametrize("d", ["dcat", "ssn", "prov"])
def test_bank_grounding_terms_exist_in_snapshot(d):
    rows = bank_rows(d)
    if not all((C.ddir(d) / "raw" / fn).exists() for fn, _, _ in C.DOMAINS[d]["ontology"]):
        pytest.skip("snapshot not fetched")
    loc = snapshot_locals(d)
    bad = [(r["cq_id"], t) for r in rows for t in grounding_terms(r["grounding"]) if t not in loc]
    assert not bad, bad


@pytest.mark.parametrize("d", ["dcat", "ssn", "prov"])
def test_bank_shape(d):
    rows = bank_rows(d)
    assert 30 <= len(rows) <= 50
    assert list(rows[0].keys())[:8] == FIELDS
    assert {r["category"] for r in rows} == CATS
    assert len({r["cq_id"] for r in rows}) == len(rows)
    assert all(r["cluster_id"] == r["cq_id"] for r in rows)
    assert all(r["question"].strip() and r["grounding"].strip() and r["expected_answer"].strip() for r in rows)
    assert len({r["question"] for r in rows}) == len(rows)


def test_term_extractor_on_control_syntax():
    assert grounding_terms("subclassof:Catalog>Dataset") == ["Catalog", "Dataset"]
    assert grounding_terms("inverse:distribution~isDistributionOf") == ["distribution", "isDistributionOf"]
    assert grounding_terms("skos:definition dcat:Dataset") == ["Dataset"]
