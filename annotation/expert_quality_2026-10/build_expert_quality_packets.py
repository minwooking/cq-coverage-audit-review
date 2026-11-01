#!/usr/bin/env python3
"""Build blinded expert-quality review packets (needs rdflib; the analysis script is stdlib-only).

Input : artifacts.json (set, variant, graph path). Coverage, judge scores and the CQ bank are never read.
Output: packets/<RATER>/ (give to the rater) and keys/ (author only, never distribute).

Blinding steps
  1. every graph is re-serialized from its triples in one neutral Turtle style, run-id tokens
     (buildrun_<letter>) are replaced, and the namespace prefix is unified (variant-specific prefix
     and file-name cues vanish);
  2. artifacts whose scrubbed graphs are identical (E and F) are one group and are presented ONCE
     (default; --keep-duplicates presents both as a hidden test-retest);
  3. per rater: random opaque IDs, random file names, artifact order shuffled within each batch,
     batch order shuffled; the dossier sample itself is the same for all raters (seeded by the
     master seed and the graph content, not by the rater), so rater agreement is not confounded
     with different samples;
  4. a leak scan over every rater-facing file aborts the build on variant-revealing tokens.
Dossier content is generic (concepts, hierarchy, relations, statements); it does not mention
competency questions, scores or coverage. Variant concealment is incomplete: modelling style differs
(see README, limitation L1). Output must be reviewed and tested before use.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import secrets
import shutil
import sys
from collections import defaultdict
from pathlib import Path

try:
    from rdflib import BNode, Graph, Literal, Namespace, URIRef
    from rdflib.namespace import DCTERMS, OWL, PROV, RDF, RDFS, SKOS
except ImportError as e:  # pragma: no cover
    raise SystemExit("rdflib is required for the packet builder: " + str(e))

HERE = Path(__file__).resolve().parent
KB = Namespace("http://example.org/chunktograph#")
CONCEPT_TYPES = {OWL.Class, RDFS.Class, SKOS.Concept}
PROP_TYPES = {OWL.ObjectProperty, OWL.DatatypeProperty, RDF.Property, OWL.AnnotationProperty}
LABEL_P = (RDFS.label, SKOS.prefLabel)
DEF_P = (URIRef(str(OWL) + "definition"), SKOS.definition, RDFS.comment, DCTERMS.description)
PARENT_P = (RDFS.subClassOf, SKOS.broader)
NON_CONTENT = {RDF.type, RDFS.label, SKOS.prefLabel, SKOS.altLabel, RDFS.subClassOf, SKOS.broader,
               SKOS.inScheme, SKOS.definition, RDFS.comment, RDFS.domain, RDFS.range, OWL.inverseOf,
               DCTERMS.source, DCTERMS.description, URIRef(str(OWL) + "definition"),
               OWL.sameAs, RDFS.seeAlso}
NON_CONTENT_NS = (str(PROV), "http://www.w3.org/ns/shacl#")
NON_CONTENT_LOCAL = {"updateCount", "weightStrength"}
LEAK_PATTERNS = [r"buildrun_[A-Za-z]\b", r"graph_[A-F]\b", r"SIMULATED", r"rendered_view",
                 r"(?i)\bvariant[ _]?[A-F]\b", r"(?i)qwen", r"(?i)\bpro[ -]?\d{4}\b", r"(?i)ontology_[A-F]\b"]


# ---------------------------------------------------------------- graph handling
def scrub_graph(path: Path) -> tuple[Graph, str]:
    g0 = Graph()
    g0.parse(str(path), format="turtle")
    if any(isinstance(x, BNode) for t in g0 for x in t):  # deterministic blank-node labels (reproducible hash/sample)
        from rdflib.compare import to_canonical_graph
        g0 = to_canonical_graph(g0)
    nt = g0.serialize(format="nt")
    nt = re.sub(r"buildrun_[A-Za-z]\b", "buildrun_1", nt)
    g = Graph()
    g.parse(data=nt, format="nt")
    g.bind("kb", KB, override=True)
    for p, ns in (("owl", OWL), ("rdfs", RDFS), ("skos", SKOS), ("prov", PROV), ("dct", DCTERMS)):
        g.bind(p, ns, override=True)
    digest = hashlib.sha256("\n".join(sorted(nt.splitlines())).encode()).hexdigest()
    return g, digest


def local(u) -> str:
    s = str(u)
    for sep in ("#", "/"):
        if sep in s:
            s = s.rsplit(sep, 1)[1]
    return s


def humanize(u) -> str:
    return local(u).replace("_", " ")


def text_of(g: Graph, node, preds) -> str | None:
    for p in preds:
        vals = sorted(str(v) if isinstance(v, Literal) else humanize(v) for v in g.objects(node, p))
        if vals:
            return " | ".join(vals)
    return None


def label_of(g: Graph, node) -> str:
    if isinstance(node, Literal):
        return '"' + str(node) + '"'
    return text_of(g, node, LABEL_P) or humanize(node)


class Dossier:
    def __init__(self, g: Graph, seed: str, n_concepts: int, n_props: int, n_stmts: int,
                 tree_roots: int, tree_depth: int, tree_children: int, tree_lines: int = 14):
        self.g, self.rng = g, random.Random(seed)
        self.k = (n_concepts, n_props, n_stmts, tree_roots, tree_depth, tree_children, tree_lines)
        self.concepts = sorted({s for t in CONCEPT_TYPES for s in g.subjects(RDF.type, t)
                                if isinstance(s, URIRef)}, key=str)
        cset = set(self.concepts)
        self.parents, self.children = defaultdict(set), defaultdict(set)
        for p in PARENT_P:
            for s, o in g.subject_objects(p):
                if isinstance(s, URIRef) and isinstance(o, URIRef) and o != OWL.Thing and s != o:
                    self.parents[s].add(o)
                    self.children[o].add(s)
        self.nodes = sorted(cset | set(self.parents) | set(self.children), key=str)
        self.stmts = []
        for s, p, o in sorted(g, key=lambda t: tuple(map(str, t))):
            if p in NON_CONTENT or str(p).startswith(NON_CONTENT_NS) or local(p) in NON_CONTENT_LOCAL:
                continue
            if isinstance(s, URIRef) and isinstance(o, (URIRef, Literal)):
                self.stmts.append((s, p, o))
        declared = {s for t in PROP_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
        used = defaultdict(list)
        for s, p, o in self.stmts:
            used[p].append((s, o))
        self.props = sorted(declared | set(used), key=str)
        self.used = used

    def depth(self) -> int:
        memo: dict = {}

        def d(n, stack):
            if n in memo:
                return memo[n]
            if n in stack:
                return 0
            stack.add(n)
            v = 1 + max((d(c, stack) for c in self.children.get(n, ())), default=0)
            stack.discard(n)
            memo[n] = v
            return v
        roots = [n for n in self.nodes if not self.parents.get(n)]
        return max((d(r, set()) for r in roots), default=0)

    def subtree_size(self, n) -> int:
        seen, stack = {n}, [n]
        while stack:
            for c in self.children.get(stack.pop(), ()):
                if c not in seen:
                    seen.add(c)
                    stack.append(c)
        return len(seen) - 1

    def overview(self) -> list[str]:
        g, cs = self.g, self.concepts
        n = max(len(cs), 1)
        with_def = sum(1 for c in cs if text_of(g, c, DEF_P))
        with_par = sum(1 for c in cs if self.parents.get(c))
        roots = [x for x in self.nodes if not self.parents.get(x)]
        dr = sum(1 for p in self.props if g.value(p, RDFS.domain) and g.value(p, RDFS.range))
        return [f"- concepts/classes: {len(cs)}",
                f"- concepts with a definition: {with_def} ({100*with_def/n:.0f}%)",
                f"- concepts with at least one parent: {with_par} ({100*with_par/n:.0f}%)",
                f"- hierarchy roots: {len(roots)}; longest parent-child chain: {self.depth()} levels",
                f"- distinct relation/attribute predicates: {len(self.props)} "
                f"(with both domain and range declared: {dr})",
                f"- content statements (excluding typing, labels, hierarchy, provenance): {len(self.stmts)}"]

    def tree(self) -> list[str]:
        n_roots, depth, nchild = self.k[3], self.k[4], self.k[5]
        roots = [x for x in self.nodes if not self.parents.get(x) and self.children.get(x)]
        sized = sorted(((self.subtree_size(r), str(r), r) for r in roots), reverse=True)[:n_roots]
        out = [f"({len(roots)} roots have children; the {len(sized)} largest are shown, depth <= {depth}, "
               f"<= {nchild} children per node, <= {self.k[6]} lines per root; the rest is elided)"]

        def walk(n, lvl, seen, buf):
            kids = sorted(self.children.get(n, ()), key=lambda c: (-self.subtree_size(c), str(c)))
            kids = [c for c in kids if c not in seen]
            for c in kids[:nchild]:
                sz = self.subtree_size(c)
                buf.append("  " * lvl + f"- {label_of(self.g, c)}" + (f"  [{sz} below]" if sz else ""))
                if lvl < depth:
                    walk(c, lvl + 1, seen | {c}, buf)
            if len(kids) > nchild:
                buf.append("  " * lvl + f"- ... (+{len(kids)-nchild} more)")
        for sz, _, r in sized:
            buf = [f"- {label_of(self.g, r)}  [{sz} below]"]
            walk(r, 1, {r}, buf)
            if len(buf) > self.k[6]:
                buf = buf[:self.k[6]] + ["  - ... (branch display truncated)"]
            out += buf
        return out

    def concept_cards(self) -> list[str]:
        pick = sorted(self.rng.sample(self.concepts, min(self.k[0], len(self.concepts))), key=str)
        out = []
        for i, c in enumerate(pick, 1):
            d = text_of(self.g, c, DEF_P)
            par = ", ".join(sorted(label_of(self.g, p) for p in self.parents.get(c, ()))[:4]) or "(none)"
            rel = [f"{humanize(p)} -> {label_of(self.g, o)}" for s, p, o in self.stmts if s == c][:5]
            out += [f"**C{i}. {label_of(self.g, c)}**",
                    f"- definition: {d if d else '(none)'}",
                    f"- parent(s): {par}",
                    f"- statements about it: {'; '.join(rel) if rel else '(none)'}", ""]
        return out

    def property_cards(self) -> list[str]:
        pick = sorted(self.rng.sample(self.props, min(self.k[1], len(self.props))), key=str)
        out = []
        for i, p in enumerate(pick, 1):
            dom, rng_ = self.g.value(p, RDFS.domain), self.g.value(p, RDFS.range)
            ex = self.rng.sample(self.used.get(p, []), min(2, len(self.used.get(p, []))))
            exs = "; ".join(f"{label_of(self.g, s)} -> {label_of(self.g, o)}" for s, o in ex)
            out += [f"**R{i}. {label_of(self.g, p)}**",
                    f"- declared domain / range: {label_of(self.g, dom) if dom else '(none)'} / "
                    f"{label_of(self.g, rng_) if rng_ else '(none)'}",
                    f"- used {len(self.used.get(p, []))} time(s); examples: {exs if exs else '(none)'}", ""]
        return out

    def statements(self) -> list[str]:
        pick = self.rng.sample(self.stmts, min(self.k[2], len(self.stmts)))
        return [f"S{i}. {label_of(self.g, s)}  --[{humanize(p)}]-->  {label_of(self.g, o)}"
                for i, (s, p, o) in enumerate(pick, 1)]


def render_dossier(art_id: str, task: str, d: Dossier, appendix_name: str | None) -> str:
    L = [f"# Review material {art_id}", "",
         "Intended use (same for every artifact): " + task, "",
         "Judge the artifact itself on the five criteria in RATER_FORM_QUALITY.md. All samples below are",
         "random draws of the same size from the artifact; they are not chosen to look good or bad.", "",
         "## 1. Overview (counts computed uniformly)", ""] + d.overview() + \
        ["", "## 2. Hierarchy (largest branches)", ""] + d.tree() + \
        ["", f"## 3. Random sample of {d.k[0]} concepts", ""] + d.concept_cards() + \
        [f"## 4. Random sample of {d.k[1]} relation/attribute predicates", ""] + d.property_cards() + \
        [f"## 5. Random sample of {d.k[2]} statements", ""] + d.statements()
    if appendix_name:
        L += ["", f"## 6. Full artifact (optional lookup)", "", f"File: `{appendix_name}` (Turtle; use search)."]
    return "\n".join(L) + "\n"


def leak_hits(text: str) -> list[str]:
    return [m.group(0) for pat in LEAK_PATTERNS for m in re.finditer(pat, text)][:5]


# ---------------------------------------------------------------- main build
SHEET_COLS = ["artifact_id", "batch", "position", "material_file", "full_ttl_file",
              "Q1_concept_accuracy", "Q2_hierarchy", "Q3_relations", "Q4_naming_definitions",
              "Q5_task_fitness", "overall_rank", "confidence_1to5", "strengths", "weaknesses",
              "free_text", "minutes_spent"]


def build(cfg_path: Path, raters: list[str], master_seed: str, out_dir: Path, keys_dir: Path,
          keep_duplicates: bool, sets: list[str] | None, sizes: dict, appendix: bool,
          form_src: Path | None) -> dict:
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    task = cfg.get("task_statement", "[[TBD]]")
    arts = [a for a in cfg["artifacts"] if not sets or a["set"] in sets]
    groups: dict[tuple, dict] = {}
    for a in arts:
        g, h = scrub_graph((cfg_path.parent / a["graph"]).resolve())
        key = (a["set"], h)
        grp = groups.setdefault(key, {"set": a["set"], "hash": h, "graph": g, "members": []})
        grp["members"].append(a["variant"])
    units = []  # presented artifacts
    for grp in groups.values():
        if keep_duplicates:
            for v in grp["members"]:
                units.append({**grp, "variant": v, "group_id": f"{grp['set']}:{grp['hash'][:8]}"})
        else:
            units.append({**grp, "variant": "+".join(sorted(grp["members"])),
                          "group_id": f"{grp['set']}:{grp['hash'][:8]}"})
    for u in units:
        u["dossier_seed"] = hashlib.sha256(f"{master_seed}|{u['hash']}".encode()).hexdigest()
    sets_present = sorted({u["set"] for u in units})
    out_dir.mkdir(parents=True, exist_ok=True)
    keys_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"master_seed_sha256": hashlib.sha256(master_seed.encode()).hexdigest(),
                "keep_duplicates": keep_duplicates, "sizes": sizes, "units": [
                    {"set": u["set"], "variant": u["variant"], "group_id": u["group_id"],
                     "members": u["members"], "scrubbed_graph_sha256": u["hash"]} for u in units],
                "raters": {}}
    cache: dict[str, tuple[str, str]] = {}
    for u in units:
        d = Dossier(u["graph"], u["dossier_seed"], **sizes)
        ttl = u["graph"].serialize(format="turtle")
        ttl = ttl if isinstance(ttl, str) else ttl.decode()
        cache[u["group_id"] + "|" + u["variant"]] = (d, ttl)
    for rid in raters:
        rrng = random.Random(int.from_bytes(hashlib.sha256(f"{master_seed}|{rid}".encode()).digest()[:8], "big"))
        batch_order = sets_present[:]
        rrng.shuffle(batch_order)
        rdir = out_dir / rid
        mdir = rdir / "materials"
        if rdir.exists():
            shutil.rmtree(rdir)
        mdir.mkdir(parents=True)
        rows, keyrows, used = [], [], set()
        for bi, st in enumerate(batch_order, 1):
            members = [u for u in units if u["set"] == st]
            rrng.shuffle(members)
            for pos, u in enumerate(members, 1):
                while True:
                    aid = "Q" + format(rrng.getrandbits(36), "09x")
                    if aid not in used:
                        used.add(aid)
                        break
                fname = "m_" + secrets.token_hex(5)
                d, ttl = cache[u["group_id"] + "|" + u["variant"]]
                app = f"{fname}_full.ttl" if appendix else None
                text = render_dossier(aid, task, d, app)
                hits = leak_hits(text) + (leak_hits(ttl) if appendix else [])
                if hits:
                    raise SystemExit(f"leak scan failed for {u['group_id']}: {hits}")
                (mdir / f"{fname}.md").write_text(text, encoding="utf-8")
                if appendix:
                    (mdir / app).write_text(ttl, encoding="utf-8")
                rows.append({"artifact_id": aid, "batch": f"Batch {bi}", "position": pos,
                             "material_file": f"materials/{fname}.md",
                             "full_ttl_file": f"materials/{app}" if appendix else ""})
                keyrows.append([aid, u["set"], u["variant"], u["group_id"], f"Batch {bi}", pos])
        sheet = rdir / f"rating_sheet_{rid}.csv"
        with sheet.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=SHEET_COLS)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, "") for c in SHEET_COLS})
        if form_src and form_src.exists():
            shutil.copyfile(form_src, rdir / form_src.name)
        with (keys_dir / f"key_{rid}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["artifact_id", "set", "variant", "group_id", "batch", "position"])
            w.writerows(keyrows)
        manifest["raters"][rid] = {"sheet_sha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
                                   "batch_order": batch_order}
    (keys_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=HERE / "artifacts.json")
    ap.add_argument("--raters", nargs="+", required=True, help="rater IDs, e.g. R1 R2 R3")
    ap.add_argument("--master-seed", required=True)
    ap.add_argument("--out-dir", type=Path, default=HERE / "packets")
    ap.add_argument("--keys-dir", type=Path, default=HERE / "keys")
    ap.add_argument("--sets", nargs="+", help="subset of sets (default: all in config)")
    ap.add_argument("--keep-duplicates", action="store_true",
                    help="present identical-content artifacts (E,F) separately (hidden test-retest)")
    ap.add_argument("--no-appendix", action="store_true")
    ap.add_argument("--n-concepts", type=int, default=30)
    ap.add_argument("--n-props", type=int, default=25)
    ap.add_argument("--n-stmts", type=int, default=30)
    ap.add_argument("--tree-roots", type=int, default=6)
    ap.add_argument("--tree-depth", type=int, default=3)
    ap.add_argument("--tree-children", type=int, default=6)
    ap.add_argument("--tree-lines", type=int, default=14, help="max lines per root branch")
    a = ap.parse_args(argv)
    sizes = dict(n_concepts=a.n_concepts, n_props=a.n_props, n_stmts=a.n_stmts,
                 tree_roots=a.tree_roots, tree_depth=a.tree_depth, tree_children=a.tree_children,
                 tree_lines=a.tree_lines)
    m = build(a.config, a.raters, a.master_seed, a.out_dir, a.keys_dir, a.keep_duplicates, a.sets,
              sizes, not a.no_appendix, HERE / "RATER_FORM_QUALITY.md")
    for u in m["units"]:
        print(f"unit {u['group_id']}  members={'+'.join(u['members'])}")
    print(f"packets -> {a.out_dir}; keys -> {a.keys_dir} (do NOT distribute keys/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
