# PREREG addendum 35 (exploratory, post hoc) -- the A -> B judge-score contrast on three further standards-based domains

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-20. Post hoc: written after the Brick holdout and after addenda 26-34, and with the knowledge of their results (A -> B observed +0.478 on 23 questions, unresolved). This file is committed alone, before any build, extractor call or judge call of this addendum. `main.tex`, `main_ko.tex` and `supplement.tex` are not touched. All code named here is AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system. Before this file or any output is shared outside the team, check that no confidential company information, host name, address, port, key or personal data is in it.

## 35.1 Question and status

The author asked for the evaluation on more diverse domains. For each new domain: build the baseline A and the pipeline base build B from the natural documentation of a public standard, score both with the paper's coverage instrument and report the A -> B contrast. **Exploratory, judge-score only, no human labels, no confirmatory hypothesis, no threshold changed after any score is seen.** Banks are AI drafts not reviewed by an author. Nothing here changes a registered result.

## 35.2 Domains, sources, licenses (checked on the fetched pages, 2026-10-20)

Selection rule (fixed): public standard with an ontology (RDF/OWL) and human-written documentation, W3C/OGC, license of every source recorded; no internal or confidential material; plain HTTP GET with a generic User-Agent and no e-mail address or personal identifier in any request. Order of work = order below; the next domain starts only when the previous one is complete.

| # | Domain (id) | Documentation (corpus) | Ontology snapshot (grounding source) | License as stated by the source |
|---|---|---|---|---|
| 1 | Data catalogs (`dcat`) | W3C Recommendation "Data Catalog Vocabulary (DCAT) - Version 3" | `dcat.ttl` of the W3C namespace | Page: "W3C liability, trademark and permissive document license rules apply" (W3C Software and Document Notice and License, 2023; copying, modification and redistribution with notice). Ontology file: `dcterms:license` CC BY 4.0. Redistribution permitted: cleaned corpus text, graphs and views of this domain may be committed with attribution. |
| 2 | Sensors / IoT (`ssn`) | W3C/OGC Recommendation "Semantic Sensor Network Ontology" (SOSA/SSN) | `sosa.ttl` + `ssn.ttl` of the W3C namespace | Page: "Copyright 2017 OGC & W3C; W3C liability, trademark and document use rules apply" (document use license: copying with notice, no derivative works). Ontology files: `dcterms:license` W3C Software and Document License 2015 and OGC Software license. Because the document license forbids derivative works, **no text of this domain is committed**: the fetch script, sha256 of every source, and aggregate outputs only. |
| 3 | Provenance (`prov`), only if time allows | W3C Recommendations "PROV-O: The PROV Ontology" and "PROV-DM: The PROV Data Model" | `prov.ttl` of the W3C namespace | Pages: "Copyright 2011-2013 W3C; W3C liability, trademark and document use rules apply" (as domain 2). Ontology file carries no license statement. Same handling as domain 2: fetch script, hashes, aggregates only. |

Candidates considered and not chosen: SAREF core (documentation license not checked, ETSI), QUDT (documentation too thin for a prose corpus). If a fetch fails or a license statement cannot be read, the domain is skipped and the next candidate (QUDT, then W3C ORG) is taken without asking.

## 35.3 Corpora (offline, no model)

* Source documents = the pages of 35.2 as served; raw HTML kept uncommitted (hash only) for domains 2-3.
* Conversion HTML -> text, then the chunker of addendum 27 (`harness/review6_natural/build_natural_corpus.py`: `to_sections`, `chunk_section`; merge under 120, split over 1000, drop under 40 characters), imported unchanged. Output = the nested `chunking_result` shape that `chunktograph extract` reads.
* Kept: headings, paragraphs, list items, and the documentation's definition tables as `Label: text` lines (definition, usage note, domain, range, equivalent class text), because they are the documentation's prose. Dropped: code and example listings, figures, navigation, tables of contents, the sections titled Acknowledgements, Change history / Changes since, References, Examples, Conformance boilerplate, and the "Status of this document" block. These drop rules are fixed here, before any bank or build.
* Corpus statistics (sections, atomic chunks, characters, length quantiles) are recorded in `corpus_stats_<d>.json`. Note for the reading: the documentation's class and property tables restate ontology definitions, so a definition question is answerable from the prose; this is natural documentation but not free of the ontology's own wording.

## 35.4 Question banks (artifact-blind, frozen before any build)

* One bank per domain, 30-50 questions (target 36), the paper's format (`cq_id,category,question,grounding,expected_answer,status,cluster_id,created`), the six categories of the Brick bank (`concept_definition`, `taxonomy`, `relations`, `slots_facets`, `instances`, `methodology`), the grounding syntax of `run_holdout._grounding_anchors` (`skos:definition X`, `subclassof:X>Y`, `children:X`, `prop:p`, `inverse:p~q`, `rdfs:comment X`), one question per cluster (`cluster_id` = `cq_id`).
* Written from the ontology snapshot and the documentation only; no graph, view or build output exists when the bank is written. Terms are chosen by the drafter; expected answers are taken verbatim from the snapshot's `rdfs:comment`, `skos:definition`, `skos:scopeNote`, `rdfs:subClassOf`, `rdfs:domain`/`rdfs:range` statements by a script, so no answer is invented.
* **Grounding rule, tested** (`test_bank_grounding.py`): every term in a grounding string must be a term that exists in the frozen snapshot (local name of a subject, predicate or object IRI).
* Freeze: sha256 of the CSV and a git tag `access2026-study4-<d>-bank-freeze` on the commit that adds it, before the first extractor call of that domain. After the tag the bank is not edited. The banks are AI drafts that no author has reviewed; every report says so.

## 35.5 Builds

* Variants **A** (`chunktograph build-a`) and **B** (`chunktograph extract`, `triples`, `build`, `split`), exactly the command sequence of `harness/variants/build_domain.sh` and `review6_natural/build_AB.sh`, `--granularity leaf`, repository HEAD source, default pipeline settings. The bank is never given to construction. Rendering = the registered `run_simulated.schema_view` (same as the holdout variants).
* **Variant F (full pipeline) is not planned.** It needs a separate pipeline-side competency-question file per domain (never the bank), which is a second authored artifact; it is out of the requested minimum. If A and B of all domains finish with time left, an amendment to this file will say so before F is built.
* **Extractor = the paper's own**: model id `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8`, served by the existing container on the internal model server (request-only through an SSH tunnel; nothing is started, stopped or reconfigured; GPUs are not touched beyond sending requests). The authentication value is the pipeline's committed default; it is never printed or written. The endpoint is passed through `CHUNKTOGRAPH_LLM_BASE_URL` only; no host, address, port or key appears in any committed file. **Difference to state:** the container serving the model today is a different deployment of the same model id (its container name indicates NVFP4 quantisation, the holdout used the FP8 weights); the served model id and the pipeline decoding (temperature 0 inside the pipeline) are the same. The extractor's request bodies are not changed (a token-usage wrapper only, as `review6_natural/run_pipeline.py`).
* Concurrency: moderate on the shared server: 4 pipeline workers (the paper's default is 8); halve on any burst of errors; the build commands are resumable (they cache per chunk), re-run until complete. Extractor-side failures are recorded, not hidden.
* An earlier probe used the GLM-4.7-Flash endpoint on the shared server only to test reachability and latency (a 40-token request); no build was started with it.

## 35.6 Judging

* Instrument = the paper's: rubric `run_holdout.RUBRIC`, user message `ARTIFACT:\n{view}\n\nQUESTION: {question}`, scorer `harness/review6_judges/score_judges.py` imported unchanged (temperature 0, `json_object`, max_tokens 1024 with two retries at 4096, thinking-minimal switch, nothing imputed, 3 repeats, seed 20260913).
* Views = the question-only sub-graph of the variant's graph (hop 2, the question's tokens only; `length_experiment/make_inputs.generate`), as in Study 2 Stage 2 and addendum 34. The full renderings do not fit a 65,536-token judge window. This is a deviation from the registered judge's full view and is named in every report.
* Cells scored = the cells (variant x question) that pass the paper's strict eligibility rule on the full rendering (`run_holdout._grounding_match_info(...)["can_ablate"]`, no allowlist). Cells that fail it are not scored.
* **Judges: GLM-4.7-Flash and gpt-oss-20b on the shared server (non-Qwen), request-only through an SSH tunnel; each judge is its own analysis, never pooled across judges.** Extractor family (Qwen) differs from both judges. The registered holdout judge (an external API) has no route here; these are named substitutes whose numbers are not the registered judge's. At most 3 workers per judge endpoint; the endpoints are shared with another scoring job, so the rate is probed first and reduced on errors.

## 35.7 Analysis (fixed before any score)

Per domain and judge, `analyze.py` reports:

* eligible clusters: in A, in B, in both (the contrast set);
* coverage of each variant over its own eligible cells: `100 * sum(J) / (3 n)` with J = mean of the cell's valid repeats (the paper's `coverage` on J, not L1*; no label exists), clustered by question;
* contrast `d = mean_J(B) - mean_J(A)` per question eligible in both; mean `d`; question-clustered paired BCa bootstrap by `analyze_holdout.cluster_bootstrap_delta` (seed 20260913, B = 10,000, mid-rank ties): 95% BCa for "resolved", 90% BCa for the equivalence reading, margin +-0.50; exact two-sided sign test and Wilcoxon (zeros dropped); the paper's decision rule (`tost_decision`, `_decision_with_rank_rule`) unchanged;
* MDE = `2.8016 * sigma / sqrt(n)` at the pre-specified sigma 1.155, at the holdout sigma 1.343 (J) and at the realised sigma of `d`;
* the verbatim-span check of `harness/review9_verbatim` (`norm`, `verbatim`, strict matcher; elision-tolerant matcher as sensitivity): the share of credits (`J >= 2`) whose quoted evidence occurs verbatim in the view the judge saw, per variant;
* pooled over the new domains (per judge): the same contrast with clusters qualified `<domain>:<cq_id>`, clustered by question within domain, only for the domains that finished;
* sensitivity (labelled): median of repeats instead of mean.

Decision (the paper's three, unchanged): resolved = the 95% BCa interval excludes 0; equivalent within +-0.50 = not resolved and the 90% interval inside (-0.50, +0.50); otherwise unresolved. Results are reported whatever they are; a domain with fewer than 10 questions eligible in both is reported as underpowered and not interpreted.

## 35.8 Order of work, outputs, commits

1. This file, committed alone.
2. Per domain: fetch and corpus (hashes), bank CSV + sha256 + test, commit with the tag; then builds, packaging, judge runs, analysis. Code (fetch, corpus, pipeline wrapper, packaging, jobs, analyze, tests) is committed after the banks; results (`results.json`, `REPORT_auto.md`, `tables.tex`, raw judge records) last. `PROGRESS.md` gets a line with an ETA at each stage.
3. Any deviation from this file goes to `DEVIATIONS.md` with its reason. Only explicit paths are staged; `index.lock` is retried.
4. Reserved files (`site_key*`, `labeling_sheet_key*`, `human_labels_export*`, `views_for_raters.zip`, `.env`) are not opened. The SSH tunnels are closed at the end.
