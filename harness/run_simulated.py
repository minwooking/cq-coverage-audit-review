"""SIMULATED holdout dry run — NOT the pre-registered confirmatory study.

Every output of this script is LLM-generated, including the evidence verdicts
that the protocol reserves for a human annotator. Nothing it produces may enter
the manuscript as a result, and the "A" column it writes is NOT a human label.

Three reasons this is not the registered study, recorded so they cannot be
forgotten later:

 1. The pre-registered confirmatory judge is gpt-5.4 (OpenAI). This runs against
    a local qwen model. Qwen is also the extraction family, so judge/extractor
    independence -- the thing the registration cares about -- is absent.
 2. The registered design compares pipeline variants (A->B, B->B'). No Brick-
    derived variants exist in this checkout, so there is nothing to contrast.
    This scores a single artifact and reports no contrast at all.
 3. The evidence verdict A must come from a human reading a verbatim span. Here
    a model produces it. That makes the silent-over-credit estimand a
    self-report, which is exactly the quantity it was designed to police.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse
from pathlib import Path

import urllib.request

from rdflib import Graph, Literal, RDF, RDFS, OWL
from rdflib.namespace import SKOS

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent
FROZEN_BANK_SHA256 = "993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507"
FROZEN_RUBRIC_SHA256 = "d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf"
FROZEN_RENDERING_SHA256 = "eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e"
REGISTERED_SEED = 20260913
API_KEY_ENV = "HOLDOUT_JUDGE_API_KEY"
ENDPOINT_ENV = "HOLDOUT_JUDGE_ENDPOINT"
MODEL_ENV = "HOLDOUT_JUDGE_MODEL"

RUBRIC = """You score whether a question can be ANSWERED from the artifact shown.
Score 0-3 on answerability only. Do not score factual accuracy of the world.
  0 = no related concept or relation present
  1 = partial: concepts present, key relation or hierarchy missing
  2 = mostly: core concept and relation present, minor gaps
  3 = complete
If nothing in the artifact supports an answer, score 0. Never reward fluency.
Return JSON: {"score": <0-3>, "evidence": "<verbatim span from the artifact, or empty>"}"""

ADJUDICATION = """A scorer claimed a question is answerable and quoted a span as
its evidence. The span has already been confirmed to occur verbatim in the
artifact, so do not re-check that. Decide only whether the span actually
SUPPORTS an answer to the question, or is merely topically nearby.
You may only WITHDRAW credit, never add it.
Return JSON: {"supported": 0 or 1, "reason": "<one short clause>"}"""


def chat_json(endpoint: str, model: str, system: str, user: str,
              temperature: float, max_tokens: int) -> dict:
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise RuntimeError(f"{API_KEY_ENV} is not set; simulated calls still require the environment-only key")
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                payload = json.loads(r.read())
            text = payload["choices"][0]["message"].get("content")
            if not text:
                # vLLM can return content=null (empty generation, length stop).
                # Treat as an unusable response rather than crashing the run.
                last_err = "empty content"
                continue
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return {"_unparsed": text}
        except Exception as exc:  # transient network / server error
            last_err = repr(exc)
    return {"_error": last_err}


def _qname(u) -> str:
    s = str(u)
    for pre, ns in (("brick:", "https://brickschema.org/schema/Brick#"),
                    ("rec:", "https://w3id.org/rec#"),
                    ("ref:", "https://brickschema.org/schema/Brick/ref#"),
                    ("sosa:", "http://www.w3.org/ns/sosa/"),
                    ("qudt:", "http://qudt.org/schema/qudt/"),
                    ("skos:", "http://www.w3.org/2004/02/skos/core#"),
                    ("owl:", "http://www.w3.org/2002/07/owl#"),
                    ("rdfs:", "http://www.w3.org/2000/01/rdf-schema#"),
                    ("sh:", "http://www.w3.org/ns/shacl#")):
        if s.startswith(ns):
            return pre + s[len(ns):]
    return s


def schema_view(ttl: Path, cache: Path | None = None) -> str:
    """A deterministic schema+instance rendering, identical for every question.

    Built from the artifact alone -- never from a question's grounding terms,
    which would leak the answer into the material being scored.

    Written compactly (prefixed names, no padding) so that the WHOLE TBox fits
    in one view. An earlier version truncated at a character budget, which cut
    off terms alphabetically: questions about terms past the cut scored low for
    a rendering reason rather than an artifact reason. A truncation that removes
    the very term under test measures the renderer, not the artifact.

    Individuals (owl:NamedIndividual) are rendered after the class/property
    schema, one line per individual, sorted by IRI like everything else. This
    was added 2026-09-20 (re-freeze) because an instance-centric artifact (the
    chunktograph pipeline's own graphs, not the Brick v1.4.4 snapshot this
    renderer was first written against) carries essentially all of its content
    as owl:NamedIndividual assertions; a schema-only view of such an artifact
    is empty in substance even when the artifact itself is not. See
    harness/variants/RENDERING_MISMATCH.md for the artifact that exposed this.
    The individual line dumps every asserted predicate generically (not just
    the fixed rdfs:label/comment/subClassOf set used for classes) because
    different pipeline variants use different, non-standard vocabularies
    (e.g. chunktograph's own ct:p_define, ct:p_subclass, dct:source) to carry
    the same grounding content that rdfs:comment/rdfs:label carry for classes;
    hard-coding the class-only predicate set would silently drop that content
    again, the same failure mode this change exists to fix. On the frozen
    Brick v1.4.4 snapshot, which declares zero owl:NamedIndividual, this
    section is empty and the rendered view is byte-identical to the prior
    schema-only version.
    """
    if cache and cache.exists():
        return cache.read_text(encoding="utf-8")
    g = Graph()
    g.parse(ttl, format="turtle")
    lines: list[str] = []
    # Walk BOTH owl:Class and rdfs:Class. The rec: vocabulary types its terms
    # rdfs:Class (plus sh:NodeShape), so an owl:Class-only walk silently drops
    # every rec: term -- and with it every question about them.
    classes = set(g.subjects(RDF.type, OWL.Class)) | set(g.subjects(RDF.type, RDFS.Class))
    for s in sorted(classes, key=str):
        if str(s).startswith("_"):
            continue
        parents = sorted({_qname(x) for x in g.objects(s, RDFS.subClassOf)
                          if not str(x).startswith("_")})
        # Definition text lives under skos:definition for brick: terms but under
        # rdfs:comment for rec: terms. Reading only one loses half the corpus.
        defn = (next(g.objects(s, SKOS.definition), None)
                or next(g.objects(s, RDFS.comment), None))
        label = next(g.objects(s, RDFS.label), None)
        row = _qname(s)
        if label:
            row += f" | {label}"
        if parents:
            row += " < " + ",".join(parents)
        if defn:
            row += " :: " + str(defn)
        lines.append(row)
    for pred_type, tag in ((OWL.ObjectProperty, "OP"), (OWL.DatatypeProperty, "DP")):
        for s in sorted(set(g.subjects(RDF.type, pred_type)), key=str):
            dom = sorted({_qname(x) for x in g.objects(s, RDFS.domain)})
            rng = sorted({_qname(x) for x in g.objects(s, RDFS.range)})
            inv = sorted({_qname(x) for x in g.objects(s, OWL.inverseOf)})
            row = f"{tag} {_qname(s)}"
            if dom:
                row += " dom:" + ",".join(dom)
            if rng:
                row += " rng:" + ",".join(rng)
            if inv:
                row += " inv:" + ",".join(inv)
            lines.append(row)
    # Individuals: the content of an instance-centric artifact. Rendered after
    # the schema so a schema-only reader is unaffected; see the docstring.
    individuals = set(g.subjects(RDF.type, OWL.NamedIndividual))
    shown_preds = {RDF.type, RDFS.label, SKOS.prefLabel, SKOS.definition, RDFS.comment}
    for s in sorted(individuals, key=str):
        if str(s).startswith("_"):
            continue
        types = sorted({_qname(x) for x in g.objects(s, RDF.type)
                        if x != OWL.NamedIndividual and not str(x).startswith("_")})
        # rdfs:label is the class-rendering convention; skos:prefLabel is the
        # equivalent chunktograph actually emits. Reading only one loses the
        # label for every individual in this checkout's artifacts.
        label = next(g.objects(s, RDFS.label), None) or next(g.objects(s, SKOS.prefLabel), None)
        # Same skos:definition/rdfs:comment fallback as the class walk above.
        defn = (next(g.objects(s, SKOS.definition), None)
                or next(g.objects(s, RDFS.comment), None))
        row = f"IND {_qname(s)}"
        if label:
            row += f" | {label}"
        if types:
            row += " a " + ",".join(types)
        if defn:
            row += " :: " + str(defn)
        # Every other asserted predicate, generic and vocabulary-agnostic:
        # different variants carry their grounding content under different,
        # non-standard property names (ct:p_define, dct:source, ...), and a
        # fixed allow-list would drop whichever one a given variant happens
        # to use -- the same failure this rendering change exists to avoid.
        extra = sorted(
            (p, o) for p, o in g.predicate_objects(s) if p not in shown_preds
        )
        if extra:
            fields = [
                f"{_qname(p)}={o if isinstance(o, Literal) else _qname(o)}"
                for p, o in extra if not str(o).startswith("_")
            ]
            if fields:
                row += " {" + "; ".join(fields) + "}"
        lines.append(row)
    view = "\n".join(lines)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(view, encoding="utf-8")
    return view


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default=os.environ.get(ENDPOINT_ENV, "http://localhost:PORT/v1"))
    ap.add_argument("--model", default=os.environ.get(MODEL_ENV, "qwen-next-flash"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--out", type=Path, default=HERE / "simulated_run")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=REGISTERED_SEED)
    a = ap.parse_args()
    if a.seed != REGISTERED_SEED:
        raise SystemExit(f"REFUSING TO RUN: seed must be {REGISTERED_SEED}, got {a.seed}")

    bank = ACCESS / "bank" / "cq_bank_brick_v1.csv"
    digest = hashlib.sha256(bank.read_bytes()).hexdigest()
    rubric = ACCESS / "rubric" / "RUBRIC_L1.md"
    rendering = ACCESS / "rubric" / "RENDERING_SPEC.md"
    frozen = {
        "bank": (digest, FROZEN_BANK_SHA256),
        "rubric": (hashlib.sha256(rubric.read_bytes()).hexdigest(), FROZEN_RUBRIC_SHA256),
        "rendering_spec": (hashlib.sha256(rendering.read_bytes()).hexdigest(), FROZEN_RENDERING_SHA256),
    }
    for name, (found, expected) in frozen.items():
        if found != expected:
            raise SystemExit(f"{name} digest mismatch: expected {expected}, found {found}")
    rows = list(csv.DictReader(bank.open(newline="", encoding="utf-8")))
    if a.limit:
        rows = rows[: a.limit]

    ttl = ACCESS / "data" / "brick-v1.4.4.ttl"
    view = schema_view(ttl, cache=a.out / "schema_view.txt")
    sys.stderr.write(f"schema view: {len(view)} chars, {view.count(chr(10)) + 1} lines\n")

    a.out.mkdir(parents=True, exist_ok=True)
    cells_path = a.out / "cells.jsonl"
    done = set()
    if cells_path.exists():
        for line in cells_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["cq_id"])
        sys.stderr.write(f"resuming: {len(done)} cell(s) already scored\n")
    with cells_path.open("a", encoding="utf-8") as fh:
        for i, row in enumerate(rows, 1):
            if row["cq_id"] in done:
                continue
            q = row["question"]
            judged = chat_json(a.endpoint, a.model, RUBRIC,
                               f"ARTIFACT:\n{view}\n\nQUESTION: {q}",
                               a.temperature, a.max_tokens)
            raw = judged.get("score")
            ok = isinstance(raw, (int, float)) and 0 <= int(raw) <= 3
            j = int(raw) if ok else 0
            judge_failed = bool(judged.get("_error") or judged.get("_unparsed")) or not ok
            claimed = (judged.get("evidence") or "")[:2000]

            # Whether the quoted span really occurs in what the judge was shown
            # is a string question, not a judgement call -- decide it by string
            # matching rather than asking a model to introspect. The protocol
            # sets A=1 only if a VERBATIM supporting span can be quoted, so a
            # span that is not in the artifact fails the condition outright and
            # needs no adjudication call.
            probe = claimed.strip()[:120]
            verbatim = bool(probe) and probe in view
            adj_reason = ""
            if not verbatim:
                A = 0
                adj_reason = "no verbatim span in the artifact"
            else:
                # The span is present; the remaining question is whether it
                # actually supports an answer. That is cheap to ask, and does
                # not need the whole artifact back in context.
                adj = chat_json(a.endpoint, a.model, ADJUDICATION,
                                f"QUESTION: {q}\n\nQUOTED SPAN: {claimed}",
                                a.temperature, 256)
                sup = adj.get("supported")
                A = 1 if sup in (1, True, "1", "true") else 0
                adj_reason = str(adj.get("reason", ""))[:300]
            span = claimed if verbatim else ""
            fh.write(json.dumps({
                "cq_id": row["cq_id"], "cluster_id": row["cluster_id"],
                "category": row["category"], "variant": "BRICK_SOURCE",
                "J": j, "A": A,
                "claimed_evidence": claimed, "adjudicator_span": span,
                "adjudicator_reason": adj_reason,
                "span_found_verbatim_in_artifact": verbatim,
                "judge_response_unusable": judge_failed,
                "SIMULATED": True, "label_source": "LLM, not human",
            }, ensure_ascii=False) + "\n")
            fh.flush()
            sys.stderr.write(f"[{i}/{len(rows)}] {row['cq_id']} J={j} A={A} verbatim={verbatim}\n")

    (a.out / "MANIFEST.json").write_text(json.dumps({
        "WARNING": "SIMULATED DRY RUN. Not the pre-registered study. "
                   "The A column is LLM-generated and is NOT a human label.",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "judge_model": a.model, "endpoint_host": urlparse(a.endpoint).hostname or a.endpoint,
        "temperature": a.temperature, "max_tokens": a.max_tokens,
        "SIMULATED": True,
        "bank_sha256": digest,
        "rubric_sha256": FROZEN_RUBRIC_SHA256,
        "rendering_spec_sha256": FROZEN_RENDERING_SHA256,
        "seed": REGISTERED_SEED,
        "n_rows": len(rows),
        "schema_view_chars": len(view),
        "preregistered_judge": "gpt-5.4 (NOT used here)",
        "variants_compared": "none - no Brick-derived variants exist",
    }, indent=2))
    print(f"wrote {cells_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
