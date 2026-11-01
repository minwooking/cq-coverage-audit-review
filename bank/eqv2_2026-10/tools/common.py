#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C2.)
"""Shared machinery for the eqv2 bank tools (addendum 47 / plan-based, exploratory).

Read-only helpers over data/brick-v1.4.4.ttl, the per-category grounding/expected/ASK
builders (a re-implementation of the expansion builder's helper grammar -- that builder
is NOT imported because its module-level code runs on import), the prompt template whose
sha256 is pinned in frame_summary.json, and the blind-open audit hook.

Nothing in this file performs a network call or touches any endpoint; endpoints arrive
only from the environment or the command line and are never persisted in any file.

Usage: not runnable on its own; imported by frame.py, draft.py, validate.py, dedup.py.
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

# ---------------------------------------------------------------- paths and constants
TOOLS = Path(__file__).resolve().parent
BANK = TOOLS.parent
ACCESS = BANK.parent.parent
SNAPSHOT = ACCESS / "data" / "brick-v1.4.4.ttl"
SNAPSHOT_SHA256 = "b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7"
REFERENCE_BANKS = [
    ACCESS / "bank" / "cq_bank_brick_v1.csv",
    ACCESS / "harness" / "study2_llm_labels" / "bank_frozen_v1.csv",
    ACCESS / "bank" / "expansion_2026-10" / "cq_bank_brick_expansion_v1.csv",
    ACCESS / "bank" / "cq_bank_brick_v2.csv",
    ACCESS / "bank" / "cq_bank_brick_v1_paraphrases.csv",
]
SEED = 20260913
CATEGORIES = ("concept_definition", "taxonomy", "relations", "slots_facets", "instances", "methodology")
B1_QUOTA_PER_CATEGORY = 84
FRAME_SUMMARY = Path(os.environ.get("EQV2_FRAME_SUMMARY", str(BANK / "frame_summary.json")))
# Amendment 47.A1: the revised template's pinned hash lives in its own file, because
# frame_summary.json is committed and never rewritten. Unset/absent = no revision pinned.
PROMPT_SHA256_FILE = Path(os.environ.get("EQV2_PROMPT_SHA256", str(BANK / "prompt_sha256_r2.json")))
LOG_DIR = Path(os.environ.get("EQV2_LOG_DIR", str(BANK / "logs")))
PATTERNS_PATH = TOOLS / "blind_patterns.json"

B = Namespace("https://brickschema.org/schema/Brick#")
R = Namespace("https://w3id.org/rec#")
F = Namespace("https://brickschema.org/schema/Brick/ref#")
SH = Namespace("http://www.w3.org/ns/shacl#")
NSMAP = {"brick": B, "rec": R, "ref": F}
PREAMBLE = (
    "PREFIX brick: <https://brickschema.org/schema/Brick#>\n"
    "PREFIX rec: <https://w3id.org/rec#>\n"
    "PREFIX ref: <https://brickschema.org/schema/Brick/ref#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
    "PREFIX owl: <http://www.w3.org/2002/07/owl#>\n"
    "PREFIX sh: <http://www.w3.org/ns/shacl#>\n"
    "PREFIX qudt: <http://qudt.org/schema/qudt/>\n\n"
)

# ---------------------------------------------------------------- qname helpers
def iri(t: str) -> URIRef:
    p, l = t.split(":", 1)
    return NSMAP[p][l]


def q(u) -> str | None:
    if not isinstance(u, URIRef):
        return None
    s = str(u)
    for p, n in NSMAP.items():
        if s.startswith(str(n)):
            return f"{p}:{s[len(str(n)):]}"
    return None


def local(t: str) -> str:
    return t.split(":", 1)[1]


# ---------------------------------------------------------------- the snapshot (read-only)
class Snapshot:
    """Frozen snapshot wrapper. Reads data/brick-v1.4.4.ttl only; sha is asserted."""

    def __init__(self, path: Path | None = None):
        path = path or SNAPSHOT
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if self.sha256 != SNAPSHOT_SHA256:
            raise SystemExit(f"snapshot sha mismatch: {self.sha256}")
        self.g = Graph()
        self.g.parse(path, format="turtle")

    # -- raw accessors
    def terms(self) -> set[str]:
        return {q(s) for s in self.g.subjects() if q(s)}

    def exists(self, t: str) -> bool:
        return t.split(":")[0] in NSMAP and (iri(t), None, None) in self.g

    def def_pred(self, t: str):
        return RDFS.comment if t.startswith("rec:") else SKOS.definition

    def def_pred_name(self, t: str) -> str:
        return "rdfs:comment" if t.startswith("rec:") else "skos:definition"

    def def_text(self, t: str) -> str | None:
        v = self.g.value(iri(t), self.def_pred(t))
        if v is None:
            return None
        return str(v).replace("\n", " ").replace("­", "").strip()

    def has_def(self, t: str) -> bool:
        return self.def_text(t) is not None

    def label(self, t: str) -> str:
        v = self.g.value(iri(t), RDFS.label)
        return str(v).strip() if v is not None else ""

    def parents(self, t: str) -> list[str]:
        return sorted(q(o) for o in self.g.objects(iri(t), RDFS.subClassOf)
                      if q(o) and (q(o) or "").split(":")[0] in NSMAP)

    def children(self, t: str) -> list[str]:
        return sorted({q(s) for s in self.g.subjects(RDFS.subClassOf, iri(t)) if q(s)})

    def owner_of_prop(self, prop: str) -> str | None:
        owners = sorted(q(s) for s in self.g.subjects(SH.property, None) if q(s) and any(
            (shp, SH.path, iri(prop)) in self.g for shp in self.g.objects(s, SH.property)))
        return owners[0] if owners else None

    def shape_info(self, owner: str, prop: str) -> tuple[str, str]:
        for shp in self.g.objects(iri(owner), SH.property):
            if (shp, SH.path, iri(prop)) in self.g:
                tgt = q(self.g.value(shp, SH["class"]))
                desc = self.g.value(shp, SH.description)
                return (tgt or ""), (str(desc).strip() if desc else "")
        return "", ""

    def prop_shapes(self) -> dict[str, str]:
        """property term -> one owner term that owns a class-targeted shape for it."""
        out: dict[str, str] = {}
        for s in self.g.subjects(SH.property, None):
            sq = q(s)
            if not sq:
                continue
            for shp in self.g.objects(s, SH.property):
                for pth in self.g.objects(shp, SH.path):
                    pq = q(pth)
                    if pq and self.g.value(shp, SH["class"]) is not None:
                        out.setdefault(pq, sq)
        return out

    def entity_props(self) -> set[str]:
        return {q(s) for s in self.g.subjects(RDF.type, B.EntityProperty) if q(s)}

    def deprecation(self, t: str) -> tuple[str, str, str] | None:
        u = iri(t)
        ver = self.g.value(u, B.deprecatedInVersion)
        if ver is None:
            return None
        rep = self.g.value(u, B.isReplacedBy)
        msg = self.g.value(u, B.deprecationMitigationMessage)
        if rep is None or msg is None:
            return None
        return str(ver), (q(rep) or str(rep)), str(msg)

    def equivalents(self):
        return self.g.subject_objects(OWL.equivalentClass)

    def ask(self, body: str) -> bool:
        try:
            return bool(self.g.query(PREAMBLE + "ASK { " + body + " }").askAnswer)
        except Exception:  # noqa: BLE001 -- validation channel, failures are reported as False
            return False

    def all_locals(self) -> set[str]:
        locs = set()
        for s in self.g.subjects():
            t = q(s)
            if t:
                locs.add(local(t))
        return locs


# ---------------------------------------------------------------- grounding grammar
def A(body: str) -> str:
    return "ASK { " + body + " }"


ENUM_CUE = re.compile(r"such as|e\.g\.|for example|for instance|including|examples? (?:include|are|given)", re.I)


def taxonomy_kind(snap: Snapshot, term: str, rank: int) -> int:
    """1 = children form (frame rank 1), 0 = parents form; childless terms always 0."""
    return 1 if (rank == 1 and snap.children(term)) else 0


def build_facts(snap: Snapshot, term: str, category: str, rank: int) -> dict:
    """Grounding / expected_answer / ASK per category, re-implementing the expansion
    builder's helper grammar without importing that builder. kind is derived from rank
    (taxonomy: rank 1 -> children form, otherwise parents form) and returned so the
    caller uses the SAME kind for the ASK body and the prompt frame (no mismatch path)."""
    facts = _build_facts_impl(snap, term, category, rank)
    facts["kind"] = taxonomy_kind(snap, term, rank) if category == "taxonomy" else 0
    return facts


def _build_facts_impl(snap: Snapshot, term: str, category: str, rank: int) -> dict:
    kind = taxonomy_kind(snap, term, rank) if category == "taxonomy" else 0
    if category == "concept_definition":
        d = snap.def_text(term) or ""
        ps = snap.parents(term)
        pred = snap.def_pred_name(term)
        grounding = f"{pred} {term}"
        expected = d.rstrip(".") + "." + (f" Subclass of {', '.join(ps)}." if ps else "")
        body = f"{term} {pred} ?d" + "".join(f" . {term} rdfs:subClassOf {p}" for p in ps)
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="partial", def_sentence=d, parents=ps, children=[], props=[])
    if category == "taxonomy" and kind == 1:
        ch = snap.children(term)
        n = len(ch)
        names = ", ".join(local(c) for c in ch[:8])
        grounding = f"rdfs:subClassOf {term}"
        expected = f"{n} direct subclasses" + (f": {names}." if n <= 8 else f" incl. {names}.")
        body = ("{ SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c rdfs:subClassOf " + term +
                " . FILTER(isIRI(?c)) } } FILTER(?n = " + str(n) + ")")
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="yes", def_sentence=snap.def_text(term) or "", parents=[],
                    children=ch, props=[])
    if category == "taxonomy":
        ps = snap.parents(term)
        grounding = f"rdfs:subClassOf {term}"
        expected = "Direct superclass" + ("es" if len(ps) > 1 else "") + ": " + " and ".join(ps) + "."
        body = " . ".join(f"{term} rdfs:subClassOf {p}" for p in ps)
        body += f" . FILTER NOT EXISTS {{ {term} rdfs:subClassOf ?o . FILTER(isIRI(?o) && ?o NOT IN (" + \
                ", ".join(ps) + ")) }"
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="yes", def_sentence=snap.def_text(term) or "", parents=ps,
                    children=snap.children(term), props=[])
    if category == "relations":
        owner = snap.owner_of_prop(term)
        if owner is None:
            raise ValueError(f"relations frame term has no shape owner: {term}")
        tgt, desc = snap.shape_info(owner, term)
        grounding = f"sh:path {term}"
        expected = f"{term} (a property shape on {owner} with sh:class {tgt})." + (f" Shape description: {desc}" if desc else "")
        body = f"{owner} sh:property ?ps . ?ps sh:path {term} ; sh:class {tgt}"
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="yes", def_sentence=snap.def_text(term) or "", parents=[],
                    children=[], props=[term], owner=owner, tgt=tgt)
    if category == "slots_facets":
        d = snap.def_text(term) or ""
        grounding = f"skos:definition {term}"
        expected = f"{term}: " + d.rstrip(".") + "."
        body = f"{term} skos:definition ?d . {term} a brick:EntityProperty"
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="partial", def_sentence=d, parents=[], children=[], props=[term])
    if category == "instances":
        d = snap.def_text(term) or ""
        key = example_key(d)
        grounding = f"{snap.def_pred_name(term)} {term}"
        expected = f"{term}: " + d.rstrip(".") + "."
        body = f'{term} {snap.def_pred_name(term)} ?d . FILTER(CONTAINS(STR(?d), "{key}"))'
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="partial", def_sentence=d, parents=[], children=[],
                    props=[], example_key=key)
    if category == "methodology":
        dep = snap.deprecation(term)
        if dep is None:
            raise ValueError(f"methodology frame term lacks full deprecation record: {term}")
        ver, repl, msg = dep
        replg = repl if repl.split(":")[0] in NSMAP else ""
        grounding = f"{term} {replg}".strip()
        expected = (f"Deprecated in {ver}; replaced by {repl}; the mitigation message reads: \"{msg}\"")
        esc = msg.replace("\\", "\\\\").replace('"', '\\"')
        replq = repl if repl.split(":")[0] in NSMAP else f"<{repl}>"
        body = (f'{term} brick:deprecatedInVersion "{ver}" . {term} brick:isReplacedBy {replq} . '
                f'{term} brick:deprecationMitigationMessage ?m . FILTER(CONTAINS(STR(?m), "{esc[:48]}"))')
        return dict(grounding=grounding, expected_answer=expected, ask=A(body),
                    ask_expressible="yes", def_sentence=snap.def_text(term) or "", parents=[],
                    children=[], props=[], deprecation=(ver, repl, msg))
    raise ValueError(f"unknown category {category}")


def example_key(d: str) -> str:
    """A literal substring of the definition, just after an enumeration cue (used as the
    ASK CONTAINS key, like the expansion builder's inst() helper)."""
    m = ENUM_CUE.search(d)
    if not m:
        raise ValueError("definition carries no enumeration cue")
    rest = d[m.end():].lstrip(" :,")
    toks = re.findall(r"[A-Za-z][A-Za-z0-9_.-]*", rest)
    if not toks:
        raise ValueError("no tokens after cue")
    for n in (4, 3, 2, 1):
        cand = " ".join(toks[:n])
        if cand in d:
            return cand
    raise ValueError("example key not a literal substring")


# ---------------------------------------------------------------- reference-bank anchors
_CONTROL_PREFIXES = {"prop", "children", "children_count", "subclassof", "disjoint", "inverse", "count", "meth"}
_METADATA_LOCALS = {"definition", "comment", "subClassOf", "domain", "range", "inverseOf", "path"}


def grounding_anchors_from_text(grounding: str) -> list[str]:
    """Local-name view of the run_holdout anchor grammar (independent re-derivation;
    validate.py calls the run_holdout function itself as the V3 check)."""
    out: list[str] = []
    for token in re.findall(r"[A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?", grounding or ""):
        if ":" in token:
            p, l = token.split(":", 1)
            if p in _CONTROL_PREFIXES:
                b, sep, sfx = l.rpartition("-")
                if sep and sfx == "meth" and b:
                    l = b
                if l not in _METADATA_LOCALS:
                    out.append(l)
                continue
            if l not in _METADATA_LOCALS:
                out.extend((token, l))
        elif token not in _METADATA_LOCALS:
            out.append(token)
    return list(dict.fromkeys(out))


def reference_anchor_locals() -> set[str]:
    locals_: set[str] = set()
    for p in REFERENCE_BANKS:
        with p.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                for a in grounding_anchors_from_text((row.get("grounding") or "")):
                    locals_.add(a.split(":")[-1])
    return locals_


# ---------------------------------------------------------------- run_holdout's pure function
_PATTERNS_CACHE: dict = {}


def _patterns_cfg() -> dict:
    """Load blind_patterns.json once per process. A re-entrancy guard makes the first
    read (which itself touches PATTERNS_PATH, and that open fires the hook that calls
    back into here) resolve without recursion: while loading, return an empty config so
    the hook treats that one config read as allowed (it is the tool's own config file)."""
    if "cfg" in _PATTERNS_CACHE:
        return _PATTERNS_CACHE["cfg"]
    if _PATTERNS_CACHE.get("loading"):
        return {"patterns": [], "boundary_patterns": []}
    _PATTERNS_CACHE["loading"] = True
    try:
        _PATTERNS_CACHE["cfg"] = json.loads(PATTERNS_PATH.read_text(encoding="utf-8"))
    finally:
        _PATTERNS_CACHE.pop("loading", None)
    return _PATTERNS_CACHE["cfg"]


def _forbidden_patterns() -> list[str]:
    cfg = _patterns_cfg()
    return cfg if isinstance(cfg, list) else cfg["patterns"]


def _boundary_patterns() -> list[str]:
    cfg = _patterns_cfg()
    return [] if isinstance(cfg, list) else (cfg.get("boundary_patterns") or [])


def forbidden_hit(path: str, patterns: list[str] | None = None) -> str | None:
    """A forbidden-pattern hit. Patterns from blind_patterns.json 'patterns' match as
    substrings; 'boundary_patterns' (job-file tokens) match only at a path-SEGMENT START
    -- a token that merely sits inside an unrelated library's file name is not a job file.
    Pass patterns=None (the normal call) to enforce both lists."""
    norm = str(path).replace("\\", "/")
    subs = patterns if patterns is not None else _forbidden_patterns()
    for pat in subs:
        if pat in norm:
            return pat
    if patterns is None:
        for pat in _boundary_patterns():
            idx = 0
            while True:
                idx = norm.find(pat, idx)
                if idx < 0:
                    break
                if idx == 0 or norm[idx - 1] == "/":
                    return pat
                idx += len(pat)
    return None


def _run_holdout_is_import_safe(harness_dir: Path) -> bool:
    """AST gate: module-level code (excluding imports/defs/classes/docstrings) must not
    contain open()/Graph()/parse() calls or module-level Path.read_bytes()/read_text().
    run_holdout.py currently only defines constants and functions at module level; if it
    ever starts opening files on import, validate.py falls back to extracting the one
    function's source with AST."""
    src = (harness_dir / "run_holdout.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Import, ast.ImportFrom, ast.Expr)):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
                continue  # module docstring
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                fn = sub.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name in {"open", "parse", "read_bytes", "read_text", "Glob", "listdir", "scandir"}:
                    return False
    return True


def load_run_holdout_anchors(harness_dir: Path) -> tuple[object, str]:
    """Return (_grounding_anchors, route) with route in {"import", "ast-extract"}.
    The import route is only taken when the AST gate says importing run_holdout.py
    cannot touch any file on its own."""
    if _run_holdout_is_import_safe(harness_dir):
        sys.path.insert(0, str(harness_dir))
        try:
            import run_holdout as rh  # noqa: PLC0415 -- deliberate late import
            return rh._grounding_anchors, "import"
        except Exception:  # noqa: BLE001 -- any import trouble -> AST route
            pass
    src = (harness_dir / "run_holdout.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_grounding_anchors":
            code = ast.get_source_segment(src, node)
            ns: dict = {"re": re}
            exec(compile(code, "<_grounding_anchors>", "exec"), ns)  # noqa: S102 -- extracted text of one pure function
            return ns["_grounding_anchors"], "ast-extract"
    raise RuntimeError("_grounding_anchors not found in run_holdout.py")


# ---------------------------------------------------------------- prompt template
SYSTEM_PROMPT = (
    "You write ONE short exam question in English about the named term of the Brick "
    "schema, using ONLY the supplied facts. Output JSON: {\"question\": \"...\"}. "
    "Exactly one question mark. At most 30 words. The question must name the term exactly "
    "as given. Do not invent facts not shown. No other keys, no explanation."
)
# 3 wording frames per category (seed-picked per item to blunt template repetition).
FRAME_TEMPLATES: dict[str, list[str]] = {
    "concept_definition": [
        "Ask what the term {local} is or represents.",
        "Ask what the term {local} represents, in your own words.",
        "Ask for a definition of {local}, phrased differently from a textbook gloss.",
    ],
    "taxonomy": [
        "Ask for the direct superclass(es) of {local}.",
        "Ask which classes are the direct subclasses of {local}.",
        "Ask where {local} sits in the class hierarchy (parent side), phrased freshly.",
    ],
    # 47.A1 (CP-1 rejection): {owner} is now the shape OWNER, not the property term, and
    # each frame names {local} and {owner} exactly once and asks for the shape's target
    # class, which is what expected_answer states (47.A1 "what changed").
    "relations": [
        "Ask which class {owner} reaches through the property {local}.",
        "Ask what kind of thing {local} points to when it is used on {owner}.",
        "Ask which class the property shape on {owner} that uses {local} selects.",
    ],
    "slots_facets": [
        "Ask what the property {local} records.",
        "Ask which quantity or facet {local} captures.",
        "Ask for the meaning of {local} as an entity property.",
    ],
    # 47.A1 (CP-1 rejection): a definition may enumerate more than one example, so the
    # frame must not force the singular ("an example"), which the screen judged ambiguous.
    "instances": [
        "Ask which examples the definition of {local} gives ({key_side}).",
        "Ask what the definition of {local} lists as instances or examples.",
        "Ask which example(s) the {local} definition gives, naming all of them when it "
        "names more than one.",
    ],
    "methodology": [
        "Ask how the schema documents the change to the term {local}.",
        "Ask what happened to {local} and what replaces it.",
        "Ask how users should handle the term {local} now.",
    ],
}


def prompt_sha256() -> str:
    blob = json.dumps({"system": SYSTEM_PROMPT, "frames": FRAME_TEMPLATES}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def expected_prompt_sha256() -> str:
    """The pinned prompt hash the drafting/validate run must match (47.A1). Read from
    PROMPT_SHA256_FILE when present, otherwise from frame_summary.json -- so a revision
    that must not rewrite frame_summary.json can still be enforced. Returns "" when
    neither is present (no pin asserted)."""
    for p in (PROMPT_SHA256_FILE, FRAME_SUMMARY):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        v = d.get("prompt_sha256")
        if isinstance(v, str) and len(v) == 64:
            return v
    return ""


def build_prompt(category: str, rank: int, facts: dict, term: str, kind: int) -> list[dict]:
    text = FRAME_TEMPLATES[category][rank % 3].format(
        local=term, owner=facts.get("owner", "") if category == "relations" else "",
        key_side=(facts.get("example_key") or ""))
    if category == "taxonomy":
        # Ask prompt and ASK form must agree (addendum 47, 47.3): kind 1 -> children
        # question; kind 0 (parents form) must never land on the children template.
        idx = 1 if (kind == 1 and facts.get("children")) else (0 if rank % 3 == 1 else rank % 3)
        text = FRAME_TEMPLATES["taxonomy"][idx].format(local=term, owner="", key_side="")
    facts_lines = []
    if facts.get("def_sentence"):
        facts_lines.append(f"definition sentence: {facts['def_sentence']}")
    if facts.get("parents"):
        facts_lines.append("parent class(es): " + ", ".join(local(p) for p in facts["parents"]))
    if facts.get("children"):
        facts_lines.append("child class(es): " + ", ".join(local(c) for c in facts["children"]))
    if category == "relations":
        if facts.get("props"):
            facts_lines.append("property name: " + facts["props"][0])
        if facts.get("owner"):
            facts_lines.append("shape owner: " + facts["owner"])
    user = (f"Category: {category}\nFrame: {rank}\nTerm: {term}  "
            f"Local name: {local(term)}  Label: {facts.get('label', '')}\n" + "\n".join(facts_lines) +
            f"\nInstruction: {text}")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


# ---------------------------------------------------------------- blind audit hook
_HOOK_STATE = {"installed": False, "log": None, "patterns": None}
# forbidden_hit (single definition, above, with the boundary-pattern rule) is used here.


class BlindAuditError(RuntimeError):
    pass


def install_blind_hooks(log_name: str | None = None) -> None:
    """sys.addaudithook-based open/listdir/scandir logger; raises on forbidden paths.
    Idempotent within a process (the log target switches per batch run)."""
    _HOOK_STATE["log"] = LOG_DIR / (log_name or "blind_open_log_b1.jsonl")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if _HOOK_STATE["installed"]:
        return
    # patterns=None at call time: forbidden_hit enforces both the plain list and the
    # segment-boundary job-file list (see blind_patterns.json).

    def _hook(event, args):
        if event == "open":
            path = args[0] if args else ""
            try:
                p = os.fspath(path)
            except TypeError:
                return
            p = str(p)
            hit = forbidden_hit(p)  # patterns=None: plain + boundary lists (see forbidden_hit)
            log_path = _HOOK_STATE.get("log")
            if log_path and os.path.abspath(p) == os.path.abspath(str(log_path)):
                return  # our own log append: allowed, not logged (would recurse)
            _append_log(event, p)
            if hit:
                raise BlindAuditError(f"EQV2-BLIND: forbidden path touched: {hit}")
        elif event in ("os.listdir", "os.scandir"):
            p = str(args[0]) if args else ""
            hit = forbidden_hit(p)  # same: plain + boundary lists
            _append_log(event, p)
            if hit:
                raise BlindAuditError(f"EQV2-BLIND: forbidden directory touched: {hit}")

    sys.addaudithook(_hook)
    _HOOK_STATE["installed"] = True


def _append_log(event: str, path: str) -> None:
    log_path = _HOOK_STATE.get("log")
    if not log_path:
        return  # hook installed but no log target (test reset): enforcement stands, logging is off
    try:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, "path": path}
        with Path(log_path).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass  # logging must never mask the raise or crash the tool


def reset_blind_hooks_for_tests(log_path: Path) -> None:
    """Test-only: point the hook log at a temp dir (hook itself stays installed)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _HOOK_STATE["log"] = Path(log_path)


# ---------------------------------------------------------------- misc
def token_set(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", (s or "").strip()) if w])


def lcs_len(a: str, b: str) -> int:
    """Length of the longest common substring (O(n*m), questions are short)."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    best = 0
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b):
            v = prev[j] + 1 if ca == cb else 0
            cur.append(v)
            best = max(best, v)
        prev = cur
    return best


def norm_text(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").lower().strip())
    return re.sub(r"[^a-z0-9 ]", "", s)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_frame(frame: dict) -> dict:
    """Single source of truth: guarantee every b1 term carries a frame_rank. kind is NOT
    stored -- it is derived from rank by build_facts (taxonomy rank 1 = children form)."""
    for cat in CATEGORIES:
        catd = frame["categories"][cat]
        n = len(catd["b1_terms"])
        if len(catd.get("b1_frame_rank", [])) != n:
            rng = random.Random(SEED)
            catd["b1_frame_rank"] = [rng.randrange(3) for _ in range(n)]
    return frame


# ---------------------------------------------------------------- batch 2 (BATCH2_PROCEDURE.md)
# b2 is read from batch2_plan.json, written once by plan_b2.py; the drafting tools never
# read the size file nor any b1 outcome file.  The plan is cross-checked against the
# frame tail here, so a hand-edited plan cannot drift from frame_summary.json.
BATCH2_PLAN = Path(os.environ.get("EQV2_BATCH2_PLAN", str(BANK / "batch2_plan.json")))
B2_FIRST_ID = 505


def cq_sort_key(cq_id: str) -> tuple[int, str]:
    """Numeric order of CQE ids.  b2 ids run CQE505..CQE1008 (four digits from 1000), so a
    plain string sort would put CQE1000 before CQE505; for b1's three-digit ids numeric
    and string order coincide."""
    digits = "".join(ch for ch in str(cq_id) if ch.isdigit())
    return (int(digits) if digits else -1, str(cq_id))


def load_batch2_plan(path: Path | None = None) -> dict:
    return json.loads(Path(path or BATCH2_PLAN).read_text(encoding="utf-8"))


def batch2_items(frame: dict, plan_path: Path | None = None) -> list[dict]:
    """b2 items in plan order (canonical category order, tail order within a category,
    ids CQE505.. in that walk), each verified against the frame tail and its tail rank."""
    plan = load_batch2_plan(plan_path)
    items = []
    for n, it in enumerate(plan["items"]):
        cat, ti = it["category"], it["tail_index"]
        catd = frame["categories"][cat]
        if catd["frame_tail"][ti] != it["term"] or catd["frame_tail_frame_rank"][ti] != it["frame_rank"]:
            raise ValueError(f"batch2_plan item {it['cq_id']} does not match the frame tail")
        if it["cq_id"] != f"CQE{B2_FIRST_ID + n:03d}":
            raise ValueError(f"batch2_plan id {it['cq_id']} breaks the CQE{B2_FIRST_ID}.. sequence")
        items.append({"cq_id": it["cq_id"], "category": cat, "term": it["term"],
                      "frame_rank": it["frame_rank"], "batch": "b2"})
    return items


def batch2_leftover_tails(frame: dict, plan_path: Path | None = None) -> tuple[dict, dict]:
    """(tails, ranks) still unused after b1's replacement wave AND the b2 items: the
    pool for b2's single replacement wave.  Per category, the tail past the last
    planned index (b2 items are a contiguous run starting right after b1's use)."""
    plan = load_batch2_plan(plan_path)
    tails, ranks = {}, {}
    for cat in CATEGORIES:
        start = plan["categories"][cat]["tail_next_index"]
        catd = frame["categories"][cat]
        tails[cat] = list(catd["frame_tail"][start:])
        ranks[cat] = list(catd["frame_tail_frame_rank"][start:])
    return tails, ranks


def frame_items(frame: dict, batch: str = "b1") -> list[dict]:
    """The single deterministic cq_id -> (category, term, frame_rank) mapping shared by
    draft.py and validate.py: canonical category order, frame order within a category,
    ids assigned as CQE001.. in that walk.  batch == "b2" returns the b2 items of
    batch2_plan.json instead (ids from CQE505)."""
    if batch == "b2":
        return batch2_items(frame)
    items = []
    i = 0
    for cat in CATEGORIES:
        catd = frame["categories"][cat]
        for rank, term in zip(catd["b1_frame_rank"], catd["b1_terms"]):
            i += 1
            items.append({"cq_id": f"CQE{i:03d}", "category": cat, "term": term,
                          "frame_rank": rank, "batch": batch})
    return items
