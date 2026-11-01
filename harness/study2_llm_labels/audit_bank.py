#!/usr/bin/env python3
"""Provenance audit and freeze of the expansion bank (addendum 32, PLAN.md 32.7).  AI-generated; review and test before use.
No model call.  Deterministic.

  audit_bank.py audit    -> bank_audit.json + BANK_PROVENANCE.md   (written BEFORE the freeze; reports what it finds, honestly)
  audit_bank.py freeze   -> bank_frozen_v1.csv + BANK_FREEZE.md    (draft minus its '#' comment header line; sha256 of both)

The audit is an independent re-implementation of the grounding-term existence test (it does not call the draft's own screen):
it parses the groundings itself and tests the terms against the frozen Brick snapshot with rdflib.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent.parent
REPO = ACCESS.parent.parent
DRAFT = ACCESS / "bank" / "expansion_2026-10" / "cq_bank_brick_expansion_draft_v1.csv"
BUILDER = ACCESS / "bank" / "expansion_2026-10" / "build_and_screen.py"
SCREEN = ACCESS / "bank" / "expansion_2026-10" / "screen_results.json"
SNAPSHOT = ACCESS / "data" / "brick-v1.4.4.ttl"
SNAPSHOT_SHA = "b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7"
FROZEN = HERE / "bank_frozen_v1.csv"
PREFIXES = {"brick": "https://brickschema.org/schema/Brick#", "rec": "https://w3id.org/rec#",
            "ref": "https://brickschema.org/schema/Brick/ref#", "sh": "http://www.w3.org/ns/shacl#",
            "skos": "http://www.w3.org/2004/02/skos/core#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "bsh": "https://brickschema.org/schema/BrickShape#", "tag": "https://brickschema.org/schema/BrickTag#"}
PREDICATES = {"skos:definition", "skos:broader", "rdfs:subClassOf", "rdfs:comment", "rdfs:label", "sh:path", "skos:related"}
ARTIFACT_WORDS = ["variants", "rendered_view", "graph_", "cells.jsonl", "real_run", "length_experiment", "judge", "label", "output/",
                  "subgraph", "review6", "review10"]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read_draft() -> list[dict]:
    with DRAFT.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith("#")))


def git_log(path: Path) -> list[str]:
    r = subprocess.run(["git", "log", "--format=%h %aI %s", "--", str(path)], cwd=REPO, capture_output=True, text=True)
    return [l[:160] for l in r.stdout.splitlines()]


def tokens(grounding: str) -> list[str]:
    return re.findall(r"\b(?:%s):[A-Za-z0-9_\-]+" % "|".join(PREFIXES), grounding)


def audit() -> dict:
    assert sha256_file(SNAPSHOT) == SNAPSHOT_SHA, "snapshot digest mismatch"
    rows = read_draft()
    out = {"draft_sha256": sha256_file(DRAFT), "n_rows": len(rows), "snapshot_sha256": SNAPSHOT_SHA}
    # 1. when written
    out["created_column"] = sorted({r["created"] for r in rows})
    out["git_log_draft"] = git_log(DRAFT)
    out["git_log_builder"] = git_log(BUILDER)
    out["author_review_values"] = sorted({r["author_review"] for r in rows})
    # 2. artifact exposure at writing time: static scan of the builder's source
    src = BUILDER.read_text(encoding="utf-8").splitlines()
    hits = []
    for i, line in enumerate(src, 1):
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        for w in ARTIFACT_WORDS:
            if w in line:
                hits.append({"line": i, "word": w, "text": s[:140]})
    opened = [{"line": i, "text": l.strip()[:140]} for i, l in enumerate(src, 1)
              if re.search(r"\b(open|read_text|read_bytes|parse)\(|ACCESS\s*/|HERE\s*/", l) and not l.strip().startswith("#")]
    out["builder_paths_touched"] = opened
    out["builder_artifact_word_hits"] = hits
    out["readme_claim"] = "artifact-blind: read data/brick-v1.4.4.ttl and the existing bank's question/grounding text only"
    # 3. grounding terms in the snapshot (independent check)
    import rdflib
    g = rdflib.Graph()
    g.parse(str(SNAPSHOT), format="turtle")
    uri_seen = set()
    for s, p, o in g:
        for x in (s, p, o):
            if isinstance(x, rdflib.URIRef):
                uri_seen.add(str(x))
    SKOS_DEF = rdflib.URIRef(PREFIXES["skos"] + "definition")
    per_row, n_terms, n_missing, n_def_missing = [], 0, 0, 0
    for r in rows:
        toks = tokens(r["grounding"])
        terms = [t for t in toks if t not in PREDICATES]
        missing, nodef = [], []
        for t in terms:
            pre, loc = t.split(":", 1)
            uri = PREFIXES[pre] + loc
            n_terms += 1
            if uri not in uri_seen:
                missing.append(t)
                n_missing += 1
            elif "skos:definition" in toks:
                lits = [str(o) for o in g.objects(rdflib.URIRef(uri), SKOS_DEF)]
                if not any(l.strip() for l in lits) and t.split(":")[0] == "brick":
                    nodef.append(t)
        n_def_missing += len(nodef)
        per_row.append({"cq_id": r["cq_id"], "n_terms": len(terms), "missing": missing, "no_definition_literal": nodef})
    out["grounding_check"] = {"n_terms": n_terms, "n_terms_missing_in_snapshot": n_missing,
                              "n_brick_terms_without_skos_definition_where_required": n_def_missing,
                              "rows_with_any_missing": [p["cq_id"] for p in per_row if p["missing"]],
                              "rows_with_no_definition": [p["cq_id"] for p in per_row if p["no_definition_literal"]],
                              "rows_checked": len(per_row)}
    out["draft_own_screen"] = json.loads(SCREEN.read_text(encoding="utf-8"))
    return out


def write_audit(a: dict) -> None:
    (HERE / "bank_audit.json").write_text(json.dumps(a, indent=1, ensure_ascii=False), encoding="utf-8")
    gc = a["grounding_check"]
    md = ["# Provenance audit of the expansion bank (addendum 32, written before the freeze)", "",
          "> LLM-labeled study; the bank is an AI-drafted, author-unreviewed set. This file reports what the audit found; nothing is smoothed.", "",
          f"- Draft: `bank/expansion_2026-10/cq_bank_brick_expansion_draft_v1.csv`, {a['n_rows']} rows, sha256 `{a['draft_sha256']}`.",
          f"- **When written.** `created` = {', '.join(a['created_column'])}. Commits touching the draft: " + "; ".join(f"`{l}`" for l in a["git_log_draft"]) + ".",
          f"- **Author review.** `author_review` values: {a['author_review_values']} -- the author has not reviewed any row.",
          "- **Was any artifact seen when it was written?** The README says artifact-blind (Brick snapshot and the existing bank's question and grounding text only). "
          f"Static scan of the builder: {len(a['builder_artifact_word_hits'])} source line(s) mention an artifact-related word "
          f"({', '.join(sorted({h['word'] for h in a['builder_artifact_word_hits']})) or 'none'}); the lines that open or parse files: "
          + "; ".join(f"L{x['line']} `{x['text'][:70]}`" for x in a["builder_paths_touched"][:12]) + ". "
          "A static scan cannot prove what a person or an agent looked at; it shows only that the builder code does not open variants, graphs, renderings, judge cells or labels.",
          "- **Seen later (stated separately).** After the draft was written, the questions were used by code that built question-only subgraph views of the holdout variants "
          "and by LLM label runs on those views (addendum 30, Tier 3e: no judge call, no human label). Those label outputs were not opened for this study.",
          f"- **Grounding terms in the frozen snapshot** (independent check, snapshot sha256 `{a['snapshot_sha256']}`): {gc['n_terms']} terms over {gc['rows_checked']} rows; "
          f"missing from the snapshot: {gc['n_terms_missing_in_snapshot']} (rows: {gc['rows_with_any_missing'] or 'none'}); "
          f"brick terms under a `skos:definition` grounding without a non-empty definition literal: {gc['n_brick_terms_without_skos_definition_where_required']} "
          f"(rows: {gc['rows_with_no_definition'] or 'none'}).",
          f"- The draft's own screen (for comparison): {a['draft_own_screen'].get('all_three_pass')} of {a['draft_own_screen'].get('rows')} rows pass all three channels.",
          "- **Not evaluated before this study:** the eligibility of any row in the A-F renderings."]
    (HERE / "BANK_PROVENANCE.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def freeze() -> dict:
    raw = DRAFT.read_bytes().decode("utf-8")
    lines = raw.splitlines(keepends=True)
    assert lines[0].startswith("#"), "expected the '#' comment header line"
    body = "".join(lines[1:])
    FROZEN.write_bytes(body.encode("utf-8"))
    rows = list(csv.DictReader(body.splitlines(keepends=True)))
    info = {"draft_sha256": sha256_file(DRAFT), "frozen_sha256": sha256_file(FROZEN), "n_rows": len(rows),
            "per_category": {c: sum(1 for r in rows if r["category"] == c) for c in sorted({r["category"] for r in rows})},
            "removed": "the first '#' comment header line only; no row edited, none deleted"}
    md = ["# Freeze of the expansion bank (addendum 32)", "",
          f"- Frozen file: `harness/study2_llm_labels/bank_frozen_v1.csv`, {info['n_rows']} rows, **sha256 `{info['frozen_sha256']}`**.",
          f"- Source: the draft, sha256 `{info['draft_sha256']}`; change: {info['removed']}.",
          f"- Per category: {info['per_category']}.",
          "- Tag: `access2026-study2-bank-freeze` on the commit that holds this file. No judge call on a new question precedes that commit.",
          "- No row was reviewed by the author; all 84 rows are kept (no balancing deletion)."]
    (HERE / "BANK_FREEZE.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "bank_freeze.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if cmd == "audit":
        a = audit()
        write_audit(a)
        print(json.dumps({"grounding_check": a["grounding_check"], "hits": len(a["builder_artifact_word_hits"])}, indent=1))
    elif cmd == "freeze":
        print(json.dumps(freeze(), indent=1))
    else:
        raise SystemExit("usage: audit_bank.py audit|freeze")
