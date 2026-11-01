# Rendering specification — schema + instance view (v2)

Registered 2026-09-13, re-frozen 2026-09-20 (v2, instance-inclusive). This
document fixes what an artifact shows a judge.

## v2 re-freeze: why individuals were added

v1 excluded individuals on the stated ground that the frozen Brick v1.4.4
snapshot declares zero `owl:NamedIndividual`, so there were none to omit in
practice. That premise held for the Brick snapshot itself but not for the
artifacts actually scored against it: the chunktograph pipeline's own output
graphs (the A–F variant set) are instance-centric — thousands of
`owl:NamedIndividual` assertions carrying the pipeline's extracted concepts,
against a handful of top-level `owl:Class` terms. Under v1, rendering such an
artifact produced a view of ~80-90 lines from a graph of tens of thousands of
triples: the schema skeleton, with essentially none of the extracted content
the pipeline actually produced. See `harness/variants/RENDERING_MISMATCH.md`
for the artifact and measurements that exposed this. v2 keeps every v1 rule
unchanged and adds one more: individuals are rendered too, after the
class/property schema. On the frozen Brick v1.4.4 snapshot, which still
declares zero `owl:NamedIndividual`, v2's output is byte-identical to v1's —
this re-freeze changes what is shown for instance-centric artifacts, not for
the Brick snapshot the bank's groundings were annotated against.

Note on scope: this re-freeze corrects what the rendering shows. It does not
by itself establish that the CQ bank's frozen groundings (written against
Brick's own `brick:`/`rec:` terms and predicates) are answerable from a
chunktograph-pipeline artifact, which uses its own `ct:` namespace and
predicate vocabulary throughout and contains no `brick:`/`rec:`-prefixed term
at all. Whether that gap is closed is an empirical question for the
eligibility preflight to answer on each concrete artifact, not something this
document can guarantee by construction.

## Why this is registered, not left to implementation

The rendering is not a presentation detail. Holding the bank, the rubric, the
judge, the decoding parameters and the artifact all constant, and changing only
which parts of the artifact are rendered, moved Layer-1 coverage by **21.3
points** in a dry run (54.6% to 75.9%). A protocol that registers the bank and
the rubric but leaves the rendering open therefore leaves open a knob large
enough to move any result this instrument can produce. Registering it removes
the option of changing the rendering after seeing an outcome.

## Included

Class-like terms, from BOTH `owl:Class` and `rdfs:Class`. Walking only
`owl:Class` silently drops every `rec:` term, which is typed `rdfs:Class` plus
`sh:NodeShape`.

Per class-like term, in this order:
1. the term as a prefixed name;
2. `rdfs:label`, if present;
3. named superclasses from `rdfs:subClassOf`, blank nodes excluded, sorted;
4. definition text: `skos:definition` if present, otherwise `rdfs:comment`.
   Reading only `skos:definition` loses the `rec:` definitions, which live in
   `rdfs:comment`.

Properties, from `owl:ObjectProperty` and `owl:DatatypeProperty`. Per property:
the prefixed name, then `rdfs:domain`, `rdfs:range` and `owl:inverseOf` where
present, each sorted.

Individuals (v2), from `owl:NamedIndividual`, rendered after the class and
property schema. Per individual, in this order:
1. the term as a prefixed name (or the full IRI when no namespace prefix in
   `_qname`'s table matches — this is the common case for pipeline-local
   namespaces such as chunktograph's `http://example.org/chunktograph#`);
2. a label, if present: `rdfs:label` if present, otherwise `skos:prefLabel`.
   Classes use only `rdfs:label`; individuals need the fallback because the
   chunktograph pipeline labels its concepts with `skos:prefLabel`, not
   `rdfs:label`, and reading only `rdfs:label` would render every individual
   unlabeled;
3. asserted types other than `owl:NamedIndividual` itself, sorted;
4. definition text, same `skos:definition`-then-`rdfs:comment` fallback as
   classes;
5. every other asserted predicate on the individual, generic and
   vocabulary-agnostic (predicate qname and object, sorted by predicate then
   object; blank-node objects excluded per the blank-node rule below). This
   step exists because different pipeline variants carry their grounding
   content under different, non-standard property names — chunktograph uses
   `ct:p_define`, `ct:p_subclass`, `dct:source` and others, none of them
   `rdfs:comment`/`rdfs:label` — and a fixed allow-list (mirroring the class
   walk's fixed predicate set) would silently drop whichever one a given
   variant happens to use. That is the same failure mode — content present in
   the artifact, absent from the view — that this re-freeze exists to fix, so
   the individual walk does not repeat it.

## Excluded, deliberately

- SHACL shapes: `sh:NodeShape` bodies, `sh:property`, cardinalities, validation
  outcomes. The scored bank does not cover them and the grounding verifier
  admits only `brick:`, `rec:` and `ref:` terms.
- Blank nodes and anything reachable only through them — for both classes and
  individuals.
- Provenance, versioning and ontology-header metadata.

v1 additionally excluded individuals outright; v2 includes them (see the
re-freeze note above).

## Ordering and budget

Terms are emitted in sorted order by IRI, classes and properties before
individuals. The view is not truncated: an earlier draft capped it at 60,000
characters, which cut terms alphabetically and scored questions about the cut
terms against material that could not contain their answers. v2 keeps that
policy for individuals too, deliberately: on the pipeline's instance-centric
artifacts this now produces multi-megabyte views (measured below), which may
not fit a given judge's context window. If a future run needs a size limit,
the truncation rule must be registered before that run, not chosen during it
or after seeing which terms would be cut — the same reasoning v1 already
established for the schema-only view, extended to individuals rather than
overridden for them.

## Identical across variants

The same rendering procedure, the same inclusion rules and the same ordering are
applied to every variant compared in a study. A comparison in which variants are
rendered differently measures the renderer.

## Reference implementation

`harness/run_simulated.py::schema_view` (and `_qname`). The implementation is
the reference, this document is the contract; if they disagree, that is a defect
in one of them and must be resolved before a run, not after.

Applied to the frozen Brick v1.4.4 snapshot this specification yields 1,985
lines and 259,186 characters — unchanged from v1, since that snapshot has no
individuals. Applied to the A–F variant artifacts (`harness/variants/`,
SIMULATED preparation set), which do, v2 yields substantially larger views;
measured sizes are recorded in `harness/variants/MANIFEST.json` and each
variant's own `MANIFEST.json` after each re-generation via
`harness/variants/package_variants.py`.
