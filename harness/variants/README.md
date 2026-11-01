# Brick pipeline variants (SIMULATED)

This directory contains six Brick-derived pipeline artifacts built from the
frozen input `../brick_corpus.json`. Every artifact is marked `SIMULATED: true`.
The graphs and rendered views were generated with the local
`qwen-next-flash` OpenAI-compatible endpoint; they are preparation artifacts,
not confirmatory holdout results.

## Variant definitions

These definitions are copied from `paper/access2026/main.tex`, Table
`tab:variants`; they are not new definitions made for Brick.

- **A** — naive direct-LLM baseline: each chunk is rendered to Turtle section
  by section, with no triple extraction and no typing stage.
- **B** — full structured pipeline: triple extraction, spaCy refinement, a SKOS
  hierarchy, base-IRI unification, and an LLM typing pass.
- **C** — incremental weighted builder: B's triples are ingested in batches
  with weight intensity and domain/range inference.
- **D** — upstream remediation added to C: pronoun and ungrounded-triple
  removal, deduplication, and label normalization before the incremental build.
- **E** — standard-first: D's triples are aligned to standard properties, plus
  a PROV-O provenance layer.
- **F** — E plus a SHACL validation pass and HTML export. The scored graph
  construction follows E; validation and HTML are additional outputs.

**A/B/B-prime mapping.** A and B are the two endpoints of the confirmatory
`A -> B` contrast. `B-prime` is not a seventh Brick variant: in the paper it is
the second-domain, one-variable recovery contrast that restores only the
upstream deduplication step identified as the failure cause. Therefore no
`B-prime` directory is fabricated here. The six Brick variants are A--F.

**Confirmatory contrasts.** The two registered confirmatory contrasts are
`A -> B` and `B -> B-prime` (the latter is the separate second-domain recovery
contrast). C--F are exploratory for the Brick family.

## Rendering

Every `rendered_view.txt` is produced by the reference
`harness/run_simulated.py::schema_view` implementation and the registered
`rubric/RENDERING_SPEC.md` rules: both `owl:Class` and `rdfs:Class`; labels;
named superclass links; `skos:definition` or `rdfs:comment`; object and datatype
properties with domain, range, and inverse; sorted by IRI; no truncation.
SHACL shapes, individuals, provenance, ontology metadata, blank nodes, and
other excluded material are not added to the view.

The per-variant `MANIFEST.json` records graph and rendered-view SHA256 values,
model, endpoint host, rendering-spec digest, timestamp, and the `SIMULATED`
flag. `SHA256.txt` summarizes the six digest pairs. If any rendered-view hashes
match, that is reported as an observed artifact of the registered renderer; no
content is changed to manufacture a distinction.

## Reproduction

From the repository root, use the local endpoint and a dummy key:

```bash
export CHUNKTOGRAPH_LLM_BASE_URL=http://<local-endpoint>/v1
export CHUNKTOGRAPH_LLM_MODEL=qwen-next-flash
export CHUNKTOGRAPH_LLM_API_KEY=dummy

uv run chunktograph extract --input paper/access2026/harness/brick_corpus.json \
  --output-dir paper/access2026/harness/variants/_work --granularity leaf
uv run chunktograph triples --input paper/access2026/harness/brick_corpus.json \
  --output-dir paper/access2026/harness/variants/_work --granularity leaf
uv run chunktograph build --input paper/access2026/harness/brick_corpus.json \
  --output-dir paper/access2026/harness/variants/_work --granularity leaf
uv run chunktograph split --output-dir paper/access2026/harness/variants/_work
uv run chunktograph build-a --input paper/access2026/harness/brick_corpus.json \
  --output-dir paper/access2026/harness/variants/_work --granularity leaf
uv run chunktograph build-c --output-dir paper/access2026/harness/variants/_work \
  --cq eval/competency_questions.json
uv run chunktograph refine-d --output-dir paper/access2026/harness/variants/_work
uv run chunktograph build-d --output-dir paper/access2026/harness/variants/_work \
  --cq eval/competency_questions.json
uv run chunktograph select-standards --output-dir paper/access2026/harness/variants/_work \
  --cq eval/competency_questions.json
uv run chunktograph build-e --output-dir paper/access2026/harness/variants/_work \
  --cq eval/competency_questions.json
uv run chunktograph build-f --output-dir paper/access2026/harness/variants/_work \
  --cq eval/competency_questions.json
```

After the six `ontology_*.ttl` files exist, package them into this directory
with the repository-local packaging helper used for this run. Before the real
submission, regenerate all LLM-dependent artifacts with the registered model
and record the new model, endpoint, timestamp, and digests; local Qwen output
cannot serve as the registered confirmatory result.
