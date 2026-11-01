#!/usr/bin/env python3
"""Rerun the registered ASK (SPARQL) oracle on the six holdout variant graphs after a
mechanical, rule-based alignment of the pipeline namespace to Brick terms.

EXPLORATORY and POST HOC. The alignment below was designed and run AFTER the holdout judge
scores and the AH labels were known (PREREG.md section 7 records that the registered
queries return false 108/108 because the pipeline mints ``ct:`` (http://example.org/chunktograph#)
terms while the bank queries use ``brick:``). Nothing here is registered, nothing feeds a
gate, and no number from this file may be read as a pre-registered result.

What it does
------------
1. For each variant graph (A..F) it indexes the pipeline vocabulary (every ``ct:`` IRI in the
   graph, with its rdfs:label / skos:prefLabel values) and maps every Brick-side term used
   by the 18 ``ask_expressible == yes`` bank queries to ``ct:`` terms with deterministic
   rules only (no LLM, no manual edit). Rules, in priority order; the first rule that finds
   any candidate decides:

   1. ``local_exact``             ct local name == Brick local name (case-sensitive)
   2. ``local_normalized``        equal token sequences after splitting camelCase, ``_``,
                                  ``-``, whitespace and case-folding
   3. ``local_joined``            equal after additionally dropping token boundaries
                                  (the pipeline lower-cases ``hasPoint`` to ``haspoint``)
   4. ``label``                   a Brick rdfs:label / skos:prefLabel (frozen snapshot) equals
                                  a ct rdfs:label / skos:prefLabel, both normalized + joined
   5. ``label_to_local``          a Brick label equals the ct local name, normalized + joined
   6. ``ns_prefixed_local``       ct local name == <namespace prefix of the Brick term> +
                                  Brick local name, normalized + joined (the pipeline mints
                                  ``brick-haspoint`` / ``brick_hasPoint`` for ``brick:hasPoint``)

   Pipeline scaffolding terms (local names starting ``Class_``, ``p_``, ``section_``) are not
   candidates. One candidate at the deciding rule -> ``mapped``. Several -> ``ambiguous``. None ->
   ``unmapped``. Candidates found only by lower-priority rules are recorded as alternates.
2. It rewrites each ASK QUERY (never the graph): every IRI in a rewritable namespace
   (brick:, rec:, ref:, qudt:; the W3C core vocabularies rdf/rdfs/owl/skos/sh/xsd are
   never rewritten) becomes the mapped ``ct:`` IRI. A query with any unmapped or ambiguous
   term in a variant is ``not_evaluable`` there; it is NOT counted as false.
3. It executes the rewritten queries (18 CQs x 6 variants) with rdflib, joins the outcomes
   to the judge score J and the AH label A of the primary cells, and reports true / false /
   not-evaluable counts, 2x2 concordance tables with Cohen's kappa, per-variant pass rates
   beside judge-only coverage, and cluster-bootstrap (BCa) intervals from
   analyze_holdout.cluster_bootstrap_stat (B = 10,000, seed 20260913).
4. A secondary any-candidate run (a charitable upper bound that tries every candidate of
   every rule for every term, capped) brackets the arbitrariness of the single-candidate
   choice.

Reads no free-text notes or evidence spans; per-cell J / A are NOT written to the output
(the per-cell file carries its own "keep sealed" warning); only aggregates and the
judge-independent ASK outcome per (CQ, variant) are written.

Usage (from the worktree root)::

    PYTHONPATH=$PWD/src <repo>/.venv/bin/python \
        paper/access2026/harness/real_run/ask_alignment/ask_alignment.py

Outputs (next to this script): mapping.csv, ask_results.json. Re-running on the same inputs is
byte-identical (no timestamps, sorted keys).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                      # paper/access2026
HARNESS = ROOT / "harness"

CT_NS = "http://example.org/chunktograph#"
VARIANTS = ("A", "B", "C", "D", "E", "F")

# Namespaces whose IRIs in a query are rewritten to ct: terms, with the short name the
# pipeline uses as a local-name prefix (brick-haspoint, rec-locatedin, ...).
REWRITE_NAMESPACES = {
    "https://brickschema.org/schema/Brick#": "brick",
    "https://w3id.org/rec#": "rec",
    "https://brickschema.org/schema/Brick/ref#": "ref",
    "http://qudt.org/schema/qudt/": "qudt",
}

# Structural predicates the ASK forms rely on; reported as absent from a variant graph when
# the graph has no triple with that predicate (a false can then not come from the facts alone).
CORE_PREDICATES = {
    "rdfs:subClassOf": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "rdfs:subPropertyOf": "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
    "owl:inverseOf": "http://www.w3.org/2002/07/owl#inverseOf",
    "owl:disjointWith": "http://www.w3.org/2002/07/owl#disjointWith",
    "sh:path": "http://www.w3.org/ns/shacl#path",
    "sh:class": "http://www.w3.org/ns/shacl#class",
}

# Pipeline scaffolding, not content terms: ``Class_<type>`` are the extraction-type classes that
# typed individuals are members of, ``p_<verb>`` the extraction relation predicates, ``section_*``
# the heading nodes. They are excluded from the candidate vocabulary (counted per variant) so a
# Brick term is never mapped onto the typing scheme itself (e.g. brick:Alarm -> ct:Class_alarm).
SCAFFOLD_LOCAL = re.compile(r"^(Class_|p_|section_)")

# The pipeline's own relation predicates that play the role of the structural predicates above.
# Diagnostic only: query predicates are NOT rewritten (the brief restricts rewriting to terms).
CT_ANALOGUE_PREDICATES = {"ct:p_subclass": CT_NS + "p_subclass", "ct:p_inverse": CT_NS + "p_inverse"}

RULES = (
    "local_exact",
    "local_normalized",
    "local_joined",
    "label",
    "label_to_local",
    "ns_prefixed_local",
)

BOOTSTRAP_B = 10_000
BOOTSTRAP_SEED = 20260913
ANY_CANDIDATE_CAP = 256                     # max term-assignment combinations per query

INPUT_FILES = {
    "bank_csv": "bank/cq_bank_brick_v1.csv",
    "brick_snapshot": "data/brick-v1.4.4.ttl",
    "per_cell": "harness/real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json",
    "cells_jsonl": "harness/real_run/cells.jsonl",
    "analyze_holdout_py": "harness/analyze_holdout.py",
}
for _v in VARIANTS:
    INPUT_FILES[f"variant_graph_{_v}"] = f"harness/variants/{_v}/graph_{_v}.ttl"


# ---------------------------------------------------------------------------
# normalization
# ---------------------------------------------------------------------------
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def norm_tokens(text: str) -> tuple[str, ...]:
    """camelCase / ``_`` / ``-`` / whitespace split, case-folded, as a token tuple."""
    spaced = _CAMEL_BOUNDARY.sub(" ", text)
    return tuple(t.lower() for t in re.split(r"[\W_]+", spaced) if t)


def norm_joined(text: str) -> str:
    """Token boundaries dropped: ``hasPoint`` == ``has_point`` == ``Has point`` == ``haspoint``."""
    return "".join(norm_tokens(text))


# ---------------------------------------------------------------------------
# pipeline vocabulary and mapping
# ---------------------------------------------------------------------------
_IRIREF_OK = re.compile(r"[^\s<>\"{}|^`\\]+")


@dataclass
class CtTerm:
    iri: str
    local: str
    labels: list[str] = field(default_factory=list)


class CtVocab:
    """Index of the ``ct:`` terms of one variant graph."""

    def __init__(self, terms: Iterable[CtTerm]):
        self.n_scaffold_excluded = 0
        self.terms = {t.iri: t for t in terms}
        self.by_local: dict[str, set[str]] = defaultdict(set)
        self.by_tokens: dict[tuple[str, ...], set[str]] = defaultdict(set)
        self.by_joined: dict[str, set[str]] = defaultdict(set)
        self.by_label_joined: dict[str, set[str]] = defaultdict(set)
        for t in self.terms.values():
            self.by_local[t.local].add(t.iri)
            self.by_tokens[norm_tokens(t.local)].add(t.iri)
            self.by_joined[norm_joined(t.local)].add(t.iri)
            for lab in t.labels:
                key = norm_joined(lab)
                if key:
                    self.by_label_joined[key].add(t.iri)


def ct_vocab_from_graph(graph: Graph, ct_ns: str = CT_NS) -> CtVocab:
    """Index the ct: terms of a graph; scaffolding terms (SCAFFOLD_LOCAL) are left out and
    counted in ``vocab.n_scaffold_excluded``."""
    terms: dict[str, CtTerm] = {}
    n_scaffold = 0
    for node in set(graph.subjects()) | set(graph.predicates()) | set(graph.objects()):
        if isinstance(node, URIRef) and str(node).startswith(ct_ns):
            iri = str(node)
            local = iri[len(ct_ns):]
            if not local or not _IRIREF_OK.fullmatch(iri):
                continue
            if SCAFFOLD_LOCAL.match(local):
                n_scaffold += 1
                continue
            terms[iri] = CtTerm(iri=iri, local=local)
    for pred in (RDFS.label, SKOS.prefLabel):
        for subj, obj in graph.subject_objects(pred):
            if str(subj) in terms and isinstance(obj, Literal):
                terms[str(subj)].labels.append(str(obj))
    vocab = CtVocab(terms.values())
    vocab.n_scaffold_excluded = n_scaffold
    return vocab


def brick_labels(snapshot: Graph, iri: str) -> list[str]:
    out = []
    for pred in (RDFS.label, SKOS.prefLabel):
        for obj in snapshot.objects(URIRef(iri), pred):
            if isinstance(obj, Literal):
                out.append(str(obj))
    return sorted(set(out))


@dataclass
class MapResult:
    brick_iri: str
    prefix: str
    local: str
    labels: list[str]
    status: str                              # mapped | ambiguous | unmapped
    rule: str                                # deciding rule ('' when unmapped)
    top_candidates: list[str]                # ct IRIs found by the deciding rule
    alt_candidates: dict[str, list[str]]     # other rules -> ct IRIs not in top_candidates
    all_candidates: list[str]                # union over every rule (any-candidate run)

    @property
    def ct_iri(self) -> str:
        return self.top_candidates[0] if self.status == "mapped" else ""


def map_term(brick_iri: str, prefix: str, local: str, labels: list[str], vocab: CtVocab) -> MapResult:
    cands: dict[str, set[str]] = {r: set() for r in RULES}
    cands["local_exact"] = set(vocab.by_local.get(local, ()))
    cands["local_normalized"] = set(vocab.by_tokens.get(norm_tokens(local), ()))
    cands["local_joined"] = set(vocab.by_joined.get(norm_joined(local), ()))
    for lab in labels:
        key = norm_joined(lab)
        if key:
            cands["label"] |= vocab.by_label_joined.get(key, set())
            cands["label_to_local"] |= vocab.by_joined.get(key, set())
    cands["ns_prefixed_local"] = set(vocab.by_joined.get(norm_joined(prefix) + norm_joined(local), ()))

    rule = next((r for r in RULES if cands[r]), "")
    top = sorted(cands[rule]) if rule else []
    alts = {r: sorted(cands[r] - set(top)) for r in RULES if r != rule and cands[r] - set(top)}
    union = sorted(set().union(*cands.values()))
    status = "unmapped" if not top else ("mapped" if len(top) == 1 else "ambiguous")
    return MapResult(brick_iri, prefix, local, labels, status, rule, top, alts, union)


# ---------------------------------------------------------------------------
# query parsing and rewriting (queries only, never graphs)
# ---------------------------------------------------------------------------
_PREFIX_DECL = re.compile(r"^[ \t]*PREFIX[ \t]+([A-Za-z][\w\-]*)?[ \t]*:[ \t]*<([^>]*)>[ \t]*$", re.I | re.M)
_TOKEN = re.compile(
    r"""
      (?P<iri><[^<>"\s]*>)
    | (?P<str>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
    | (?P<comment>\#[^\n]*)
    | (?P<pname>(?<![\w:])(?P<pfx>[A-Za-z][\w\-]*):(?P<loc>[A-Za-z_][\w\-]*))
    """,
    re.X,
)
_LOCAL_OK = re.compile(r"[A-Za-z_][\w\-]*")


def split_query(query: str) -> tuple[dict[str, str], str]:
    """-> (prefix map name->namespace, body without the PREFIX declarations)."""
    prefixes = {(m.group(1) or ""): m.group(2) for m in _PREFIX_DECL.finditer(query)}
    body = _PREFIX_DECL.sub("", query)
    return prefixes, body


def _resolve(match: re.Match, prefixes: Mapping[str, str], rewrite_ns: Mapping[str, str]):
    """-> (namespace, local) when the token is an IRI in a rewritable namespace, else None."""
    if match.group("iri"):
        iri = match.group("iri")[1:-1]
        for ns in rewrite_ns:
            if iri.startswith(ns) and _LOCAL_OK.fullmatch(iri[len(ns):] or ""):
                return ns, iri[len(ns):]
        return None
    if match.group("pname"):
        ns = prefixes.get(match.group("pfx"))
        if ns in rewrite_ns:
            return ns, match.group("loc")
    return None


def query_terms(query: str, rewrite_ns: Mapping[str, str] = REWRITE_NAMESPACES) -> list[tuple[str, str]]:
    """Distinct (namespace, local) pairs of the rewritable terms used in the query body."""
    prefixes, body = split_query(query)
    seen: dict[tuple[str, str], None] = {}
    for m in _TOKEN.finditer(body):
        hit = _resolve(m, prefixes, rewrite_ns)
        if hit:
            seen[hit] = None
    return sorted(seen)


def rewrite_query(
    query: str,
    mapping: Mapping[str, str],
    rewrite_ns: Mapping[str, str] = REWRITE_NAMESPACES,
) -> tuple[str, list[str]]:
    """Rewrite rewritable-namespace IRIs of the query body to ``<ct IRI>`` via ``mapping``
    (brick-side IRI -> ct IRI). Returns (rewritten query, sorted brick IRIs with no mapping).
    A rewritten query is only meaningful when the second element is empty."""
    prefixes, body = split_query(query)
    missing: set[str] = set()

    def sub(m: re.Match) -> str:
        hit = _resolve(m, prefixes, rewrite_ns)
        if hit is None:
            return m.group(0)
        brick_iri = hit[0] + hit[1]
        target = mapping.get(brick_iri)
        if not target:
            missing.add(brick_iri)
            return m.group(0)
        return f"<{target}>"

    return _TOKEN.sub(sub, body).strip() + "\n", sorted(missing)


def core_predicates_used(query: str) -> list[str]:
    """Prefixed names of the CORE_PREDICATES the query mentions (by IRI or prefixed name)."""
    prefixes, body = split_query(query)
    used = set()
    for m in _TOKEN.finditer(body):
        if m.group("iri"):
            iri = m.group("iri")[1:-1]
        elif m.group("pname") and m.group("pfx") in prefixes:
            iri = prefixes[m.group("pfx")] + m.group("loc")
        else:
            continue
        for name, full in CORE_PREDICATES.items():
            if iri == full:
                used.add(name)
    return sorted(used)


# ---------------------------------------------------------------------------
# execution
# ---------------------------------------------------------------------------
def run_ask(graph: Graph, query: str) -> bool:
    return bool(graph.query(query).askAnswer)


def any_candidate_outcome(graph: Graph, query: str, results: Mapping[str, MapResult],
                          cap: int = ANY_CANDIDATE_CAP) -> str:
    """Charitable upper bound: true if SOME assignment of one candidate (from any rule) per
    Brick term makes the ASK true. 'not_evaluable' when a term has no candidate at all;
    'cap_exceeded' when the number of assignments exceeds ``cap``."""
    terms = sorted(results)
    if any(not results[t].all_candidates for t in terms):
        return "not_evaluable"
    n = 1
    for t in terms:
        n *= len(results[t].all_candidates)
        if n > cap:
            return "cap_exceeded"
    for combo in itertools.product(*(results[t].all_candidates for t in terms)):
        rewritten, missing = rewrite_query(query, dict(zip(terms, combo)))
        if not missing and run_ask(graph, rewritten):
            return "true"
    return "false"


def short_name(iri: str) -> str:
    """``https://brickschema.org/schema/Brick#Sensor`` -> ``brick:Sensor``."""
    for ns, prefix in REWRITE_NAMESPACES.items():
        if iri.startswith(ns):
            return f"{prefix}:{iri[len(ns):]}"
    return iri


def evaluate_cq(graph: Graph, query: str, term_iris: Iterable[str], results: Mapping[str, MapResult],
                absent_core_predicates: Iterable[str] = ()) -> dict:
    """Rewrite one ASK query with the single-candidate mapping and run it on ``graph``.

    A term that is not ``mapped`` (unmapped or ambiguous) makes the query ``not_evaluable``;
    it is never scored false. ``results`` maps each Brick IRI to its MapResult."""
    used = {i: results[i] for i in term_iris}
    bad = {i: res for i, res in used.items() if res.status != "mapped"}
    term_map = {i: res.ct_iri for i, res in used.items() if res.status == "mapped"}
    rewritten, _missing = rewrite_query(query, term_map)
    if bad:
        outcome = "not_evaluable"
    else:
        outcome = "true" if run_ask(graph, rewritten) else "false"
    absent = set(absent_core_predicates)
    return {
        "outcome": outcome,
        "unmapped_terms": sorted(short_name(i) for i, r in bad.items() if r.status == "unmapped"),
        "ambiguous_terms": sorted(short_name(i) for i, r in bad.items() if r.status == "ambiguous"),
        "core_predicates_absent": [p for p in core_predicates_used(query) if p in absent],
        "rewritten_query_sha256": sha256_text(rewritten) if not bad else None,
        "any_candidate_outcome": any_candidate_outcome(graph, query, used),
    }


# ---------------------------------------------------------------------------
# statistics
# ---------------------------------------------------------------------------
def table_2x2(pairs: Iterable[tuple[int, int]]) -> dict:
    """pairs of (ask, other), each 0/1 -> counts keyed ask{T,F}_other{1,0}."""
    c = Counter(pairs)
    return {
        "ask_true__other_1": c[(1, 1)], "ask_true__other_0": c[(1, 0)],
        "ask_false__other_1": c[(0, 1)], "ask_false__other_0": c[(0, 0)],
    }


def cohen_kappa(a: int, b: int, c: int, d: int) -> dict:
    """Cohen's kappa for the 2x2 table [[a, b], [c, d]] (rows = ASK true/false, cols = other 1/0)."""
    n = a + b + c + d
    if n == 0:
        return {"n": 0, "kappa": None, "percent_agreement": None, "reason": "empty table"}
    po = (a + d) / n
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (n * n)
    if math.isclose(pe, 1.0):
        return {"n": n, "kappa": None, "percent_agreement": po,
                "reason": "undefined: a rater is constant (expected agreement = 1)"}
    return {"n": n, "kappa": (po - pe) / (1 - pe), "percent_agreement": po}


def kappa_stat(left: str, right: str):
    def stat(records: list[dict]) -> float:
        t = table_2x2((r[left], r[right]) for r in records)
        k = cohen_kappa(t["ask_true__other_1"], t["ask_true__other_0"],
                        t["ask_false__other_1"], t["ask_false__other_0"])
        if k["kappa"] is None:
            raise ValueError(f"kappa undefined in a resample ({k['reason']})")
        return k["kappa"]
    return stat


def share_stat(key: str):
    return lambda records: sum(r[key] for r in records) / len(records)


def coverage_stat(records: list[dict]) -> float:
    """judge-only coverage, same statistic as results_human_pass/judge_only_J.py."""
    return 100.0 * sum(r["J"] for r in records) / (3 * len(records))


def bca(ah, records: list[dict], stat_fn) -> dict:
    """BCa cluster-bootstrap interval via analyze_holdout.cluster_bootstrap_stat, or a
    'not computable' note (few clusters / degenerate resamples)."""
    clusters = len({r["cluster_id"] for r in records})
    try:
        res = ah.cluster_bootstrap_stat(records, stat_fn, None, "cluster_id",
                                        BOOTSTRAP_B, BOOTSTRAP_SEED, "midrank")
    except ValueError as exc:
        return {"computable": False, "n_cells": len(records), "n_clusters": clusters, "reason": str(exc)}
    out = {"computable": True, "estimate": res["estimate"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
           "n_cells": res["n_cells"], "n_clusters": res["n_clusters"], "tie_share": res["tie_share"]}
    if res["ci_lo"] == res["ci_hi"]:
        out["degenerate"] = "interval has zero width (statistic is constant across resamples)"
    return out


# ---------------------------------------------------------------------------
# io helpers
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _round(obj, nd=6):
    if isinstance(obj, float):
        return round(obj, nd)
    if isinstance(obj, dict):
        return {k: _round(v, nd) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v, nd) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# main pipeline
# ---------------------------------------------------------------------------
def load_ask_cqs(root: Path) -> list[dict]:
    with (root / INPUT_FILES["bank_csv"]).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    ask = [r for r in rows if r["ask_expressible"] == "yes"]
    for r in ask:
        r["query_text"] = (root / "bank" / r["ask_query_file"]).read_text(encoding="utf-8")
    return sorted(ask, key=lambda r: r["cq_id"])


def load_primary_cells(root: Path) -> dict[tuple[str, str], dict]:
    """(cq_id, variant) -> {cluster_id, J, A}; J cross-checked against cells.jsonl."""
    data = json.loads((root / INPUT_FILES["per_cell"]).read_text(encoding="utf-8"))
    cells_j = {}
    with (root / INPUT_FILES["cells_jsonl"]).open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            cells_j[row["cell_id"]] = row
    out = {}
    for c in data["primary_cells"]:
        raw = cells_j[c["cell_id"]]
        if int(raw["J"]) != int(c["J"]) or raw["cq_id"] != c["cq_id"] or raw["variant"] != c["variant"]:
            raise SystemExit(f"per_cell / cells.jsonl disagree on {c['cell_id']}")
        key = (c["cq_id"], c["variant"])
        if key in out:
            raise SystemExit(f"duplicate primary cell for {key}")
        out[key] = {"cluster_id": c["cluster_id"], "J": int(c["J"]), "A": int(c["A"])}
    return out


def build(root: Path = ROOT, ah=None) -> tuple[dict, list[dict]]:
    """Run everything; -> (results dict for ask_results.json, rows for mapping.csv)."""
    if ah is None:
        sys.path.insert(0, str(root / "harness"))
        import analyze_holdout as ah  # noqa: PLC0415
    if ah.BOOTSTRAP_RESAMPLES != BOOTSTRAP_B or ah.REGISTERED_SEED != BOOTSTRAP_SEED:
        raise SystemExit("analyze_holdout bootstrap constants differ from the registered B / seed")

    inputs = {name: sha256_file(root / rel) for name, rel in INPUT_FILES.items()}
    asks = load_ask_cqs(root)
    for r in asks:
        inputs[f"ask_query_{r['cq_id']}"] = sha256_file(root / "bank" / r["ask_query_file"])
    primary = load_primary_cells(root)

    snapshot = Graph()
    snapshot.parse(root / INPUT_FILES["brick_snapshot"], format="turtle")

    # Brick-side terms used by the queries (namespace-qualified), with the CQs that use them.
    term_users: dict[str, set[str]] = defaultdict(set)
    q_terms: dict[str, list[str]] = {}
    for r in asks:
        terms = query_terms(r["query_text"])
        q_terms[r["cq_id"]] = [ns + loc for ns, loc in terms]
        for ns, loc in terms:
            term_users[ns + loc].add(r["cq_id"])

    mapping_rows: list[dict] = []
    outcomes: list[dict] = []
    structural: dict[str, dict] = {}
    map_stats: dict[str, dict] = {}
    for v in VARIANTS:
        graph = Graph()
        graph.parse(root / INPUT_FILES[f"variant_graph_{v}"], format="turtle")
        vocab = ct_vocab_from_graph(graph)
        pred_triples = {n: sum(1 for _ in graph.triples((None, URIRef(full), None)))
                        for n, full in CORE_PREDICATES.items()}
        absent = [n for n, c in pred_triples.items() if c == 0]
        analogue_triples = {n: sum(1 for _ in graph.triples((None, URIRef(full), None)))
                            for n, full in CT_ANALOGUE_PREDICATES.items()}
        structural[v] = {"triples": len(graph), "ct_terms_candidate_vocabulary": len(vocab.terms),
                         "scaffold_terms_excluded": vocab.n_scaffold_excluded,
                         "core_predicate_triples": pred_triples, "core_predicates_absent": absent,
                         "ct_analogue_predicate_triples": analogue_triples}

        results: dict[str, MapResult] = {}
        for iri in sorted(term_users):
            ns = next(n for n in REWRITE_NAMESPACES if iri.startswith(n))
            prefix, local = REWRITE_NAMESPACES[ns], iri[len(ns):]
            res = map_term(iri, prefix, local, brick_labels(snapshot, iri), vocab)
            results[iri] = res
            mapping_rows.append({
                "variant": v,
                "brick_term": short_name(iri),
                "brick_iri": iri,
                "brick_labels": "|".join(res.labels),
                "status": res.status,
                "rule": res.rule,
                "ct_iri": res.ct_iri,
                "n_candidates_at_rule": len(res.top_candidates),
                "candidates_at_rule": "|".join(c[len(CT_NS):] for c in res.top_candidates),
                "alternate_candidates": ";".join(
                    f"{r}={'|'.join(c[len(CT_NS):] for c in cs)}" for r, cs in sorted(res.alt_candidates.items())),
                "used_by_cqs": "|".join(sorted(term_users[iri])),
            })
        stat_counts = Counter(r.status for r in results.values())
        rule_counts = Counter(r.rule for r in results.values() if r.status == "mapped")
        map_stats[v] = {
            "terms": len(results),
            "mapped": stat_counts["mapped"], "ambiguous": stat_counts["ambiguous"],
            "unmapped": stat_counts["unmapped"],
            "mapped_by_rule": {r: rule_counts[r] for r in RULES if rule_counts[r]},
            "with_alternate_candidates": sum(1 for r in results.values() if r.alt_candidates),
            "unmapped_terms": sorted(short_name(i) for i, r in results.items() if r.status == "unmapped"),
            "ambiguous_terms": sorted(short_name(i) for i, r in results.items() if r.status == "ambiguous"),
        }

        for r in asks:
            cq = r["cq_id"]
            ev = evaluate_cq(graph, r["query_text"], q_terms[cq], results, absent)
            outcomes.append({"cq_id": cq, "variant": v, "category": r["category"], "cluster_id": r["cluster_id"],
                             "has_primary_cell": (cq, v) in primary, **ev})

    results_json = analyse(outcomes, primary, ah)
    results_json.update({
        "schema": "ask_alignment results v1",
        "status": ("EXPLORATORY and POST HOC. The ct:->brick: alignment was designed and run after the "
                   "holdout judge scores and the AH labels were known; it is not registered and feeds no gate."),
        "inputs_sha256": inputs,
        "config": {
            "ct_namespace": CT_NS, "variants": list(VARIANTS), "rules_in_priority_order": list(RULES),
            "rewrite_namespaces": REWRITE_NAMESPACES, "core_predicates_checked": CORE_PREDICATES,
            "bootstrap": {"B": BOOTSTRAP_B, "seed": BOOTSTRAP_SEED, "method": "BCa (analyze_holdout.cluster_bootstrap_stat, midrank)",
                          "cluster": "cluster_id (= CQ)"},
            "any_candidate_cap": ANY_CANDIDATE_CAP,
        },
        "variant_graphs": structural,
        "mapping_summary": map_stats,
        "per_cq_variant": sorted(outcomes, key=lambda o: (o["cq_id"], o["variant"])),
    })
    mapping_rows.sort(key=lambda r: (r["variant"], r["brick_term"]))
    return results_json, mapping_rows


def analyse(outcomes: list[dict], primary: Mapping[tuple[str, str], dict], ah) -> dict:
    per_variant_counts = {v: Counter(o["outcome"] for o in outcomes if o["variant"] == v) for v in VARIANTS}
    any_counts = Counter(o["any_candidate_outcome"] for o in outcomes)

    def cnt(c: Counter) -> dict:
        return {"true": c["true"], "false": c["false"], "not_evaluable": c["not_evaluable"],
                **({"cap_exceeded": c["cap_exceeded"]} if c["cap_exceeded"] else {}), "total": sum(c.values())}

    # cells: primary cells of ASK-expressible CQs with an evaluable ASK outcome
    joined = []
    for o in outcomes:
        cell = primary.get((o["cq_id"], o["variant"]))
        if cell is None:
            continue
        joined.append({**o, **cell})
    evaluable = [
        {"cluster_id": j["cluster_id"], "variant": j["variant"], "ask": int(j["outcome"] == "true"),
         "j2": int(j["J"] >= 2), "a": j["A"], "J": j["J"]}
        for j in joined if j["outcome"] != "not_evaluable"
    ]

    def conc(other: str, rows: list[dict], ask_key: str = "ask", with_bca: bool = True) -> dict:
        t = table_2x2((r[ask_key], r[other]) for r in rows)
        k = cohen_kappa(t["ask_true__other_1"], t["ask_true__other_0"],
                        t["ask_false__other_1"], t["ask_false__other_0"])
        out = {"table": t, **k, "clusters_with_ask_true": len({r["cluster_id"] for r in rows if r[ask_key] == 1})}
        if with_bca:
            # kappa is 0 when one rater is constant, so degenerate resamples do not break the BCa call
            out["bca_kappa"] = bca(ah, rows, kappa_stat(ask_key, other)) if rows else None
        return out

    # secondary: any-candidate upper bound (cells whose any-candidate run is neither NE nor capped)
    any_rows = [
        {"cluster_id": j["cluster_id"], "variant": j["variant"], "ask_any": int(j["any_candidate_outcome"] == "true"),
         "j2": int(j["J"] >= 2), "a": j["A"]}
        for j in joined if j["any_candidate_outcome"] in ("true", "false")
    ]

    per_variant = {}
    for v in VARIANTS:
        all_cells = [j for j in joined if j["variant"] == v]
        ev = [r for r in evaluable if r["variant"] == v]
        recs_all = [{"cluster_id": j["cluster_id"], "J": j["J"]} for j in all_cells]
        recs_ev = [{"cluster_id": r["cluster_id"], "J": r["J"], "ask": r["ask"], "j2": r["j2"], "a": r["a"]} for r in ev]
        n_true = sum(r["ask"] for r in ev)
        entry = {
            "ask_cqs_run": len({o["cq_id"] for o in outcomes}), "ask_outcomes_all_18": cnt(per_variant_counts[v]),
            "primary_cells_on_ask_cqs": len(all_cells), "evaluable_cells": len(ev), "ask_true_cells": n_true,
            "ask_pass_rate_over_evaluable": (n_true / len(ev)) if ev else None,
            "ask_pass_rate_bca": bca(ah, recs_ev, share_stat("ask")) if len(ev) else None,
            "judge_coverage_pct_on_primary_ask_cells": coverage_stat(recs_all) if recs_all else None,
            "judge_coverage_bca_on_primary_ask_cells": bca(ah, recs_all, coverage_stat) if recs_all else None,
            "judge_coverage_pct_on_evaluable_cells": coverage_stat(recs_ev) if recs_ev else None,
            "judge_j_ge_2_share_on_evaluable_cells": (sum(r["j2"] for r in recs_ev) / len(recs_ev)) if recs_ev else None,
            "ah_a_share_on_evaluable_cells": (sum(r["a"] for r in recs_ev) / len(recs_ev)) if recs_ev else None,
        }
        per_variant[v] = entry

    # pooled, restricted to the CQ-by-variant cells that exist for all comparisons
    pooled_ev_all = evaluable
    return {
        "ask_counts": {"overall": cnt(Counter(o["outcome"] for o in outcomes)),
                       "per_variant": {v: cnt(per_variant_counts[v]) for v in VARIANTS},
                       "per_cq": {cq: cnt(Counter(o["outcome"] for o in outcomes if o["cq_id"] == cq))
                                  for cq in sorted({o["cq_id"] for o in outcomes})}},
        "ask_counts_any_candidate_upper_bound": cnt(any_counts),
        "ask_counts_any_candidate_per_variant": {v: cnt(Counter(o["any_candidate_outcome"] for o in outcomes if o["variant"] == v))
                                                 for v in VARIANTS},
        "concordance": {
            "universe": {"primary_cells_on_ask_cqs": len(joined), "evaluable_primary_cells": len(pooled_ev_all),
                         "clusters_evaluable": len({r["cluster_id"] for r in pooled_ev_all}),
                         "note": "cells = (CQ, variant) pairs with a primary cell and an evaluable ASK outcome; "
                                 "cells of one CQ are resampled together (cluster = CQ)"},
            "ask_vs_judge_J_ge_2": conc("j2", evaluable),
            "ask_vs_ah_label_A": conc("a", evaluable),
            "by_variant_group_no_ci": {
                grp: {"ask_vs_judge_J_ge_2": conc("j2", rows, with_bca=False),
                      "ask_vs_ah_label_A": conc("a", rows, with_bca=False)}
                for grp, rows in (("A", [r for r in evaluable if r["variant"] == "A"]),
                                  ("B-F", [r for r in evaluable if r["variant"] != "A"]))
            },
            "ask_true_share_bca": bca(ah, pooled_ev_all, share_stat("ask")) if pooled_ev_all else None,
            "judge_j_ge_2_share_on_evaluable_cells": (sum(r["j2"] for r in pooled_ev_all) / len(pooled_ev_all)) if pooled_ev_all else None,
            "ah_a_share_on_evaluable_cells": (sum(r["a"] for r in pooled_ev_all) / len(pooled_ev_all)) if pooled_ev_all else None,
        },
        "sensitivity_any_candidate": {
            "note": ("SECONDARY. Upper bound: an ASK is true if ANY assignment of one candidate (from any rule) "
                     "per Brick term makes it true. Cells with a term that has no candidate, or more than the cap "
                     "of assignments, are excluded."),
            "evaluable_primary_cells": len(any_rows),
            "ask_vs_judge_J_ge_2": conc("j2", any_rows, "ask_any"),
            "ask_vs_ah_label_A": conc("a", any_rows, "ask_any"),
        },
        "per_variant": per_variant,
    }


MAPPING_COLUMNS = ["variant", "brick_term", "brick_iri", "brick_labels", "status", "rule", "ct_iri",
                   "n_candidates_at_rule", "candidates_at_rule", "alternate_candidates", "used_by_cqs"]


def write_outputs(results: dict, rows: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "mapping.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MAPPING_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    results = dict(results)
    results["script_sha256"] = sha256_file(Path(__file__).resolve())
    results["mapping_csv_sha256"] = sha256_file(out_dir / "mapping.csv")
    (out_dir / "ask_results.json").write_text(
        json.dumps(_round(results), indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT, help="paper/access2026 directory")
    ap.add_argument("--out-dir", type=Path, default=HERE)
    a = ap.parse_args(argv)
    results, rows = build(a.root)
    write_outputs(results, rows, a.out_dir)
    c = results["ask_counts"]["overall"]
    print(f"ASK outcomes over 18 CQs x 6 variants: {c}")
    print(f"wrote {a.out_dir / 'mapping.csv'} and {a.out_dir / 'ask_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
