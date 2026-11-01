# PREREG addendum 27 (exploratory) -- natural-document Brick corpus: does the instrument still separate A from B when the artifacts are built from real prose?

> AI-drafted plan; to be reviewed by the author before any result is used. All scripts written under this plan are AI-generated and must be reviewed and tested before reuse; nothing here is applied to a production system.
> Date: 2026-10-17. This file is committed alone, before any corpus is built, any extractor call is made, or any judge call is made. The manuscript (`main.tex`, `main_ko.tex`, `supplement.tex`) is not touched by this addendum.

## 27.1 Status, question, and what this can and cannot show

**Exploratory and post hoc.** No confirmatory hypothesis, no pass/fail threshold, no multiplicity correction.

Reviewer concern: the Brick holdout corpus (`harness/brick_corpus.json`, from `harness/build_brick_corpus.py`) is the Brick schema TTL rendered as template sentences, so every answer in the bank is present in the input by construction (the builder's own docstring says so: it measures extraction *fidelity*, not discovery).

Question: when baseline A and the pipeline's base build B are built from **natural-language Brick documentation** (hand-written prose, no TTL, nothing generated from the schema), and scored with the frozen 36-question Brick bank by the substitute judge (luna), does the A -> B contrast behave sensibly (direction, size, interval) compared with the template-corpus A -> B contrast under the same judge and view?

Bound on what the experiment can show: the bank was authored blind against the TTL snapshot (Brick v1.4.4), not against prose documentation. Natural documentation may simply not contain the answers to many bank questions (especially the `rec:` definition-comment questions and the rare-property questions). Coverage on such questions is limited by the corpus, not by A or B. Section 27.4 therefore measures, before any build, how many bank questions have their answer present in the natural corpus at all.

## 27.2 Frozen inputs (digests checked by the run code; the run stops on mismatch)

- Bank `bank/cq_bank_brick_v1.csv`, sha256 `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`, 36 rows, unchanged. Questions only are sent to any model; the `grounding` and `expected_answer` columns are never sent to the extractor, to subgraph extraction, or to the judge.
- Judge rubric `RUBRIC` in `harness/run_holdout.py` (same string, used through `run_holdout.call_judge`/`_judge_one_cell`); `rubric/RUBRIC_L1.md` sha256 `d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf`; rendering spec `rubric/RENDERING_SPEC.md` sha256 `eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e`.
- Code identity at plan time (repo HEAD `0c9ca139a21b94e2cfe2401bb2fabfe089961ed4`; sha256 of the harness files reused unchanged and imported, never edited):
  - `harness/run_holdout.py` `2fcc43516b45b80dab9022e4f0e03dcb1730a62456e920b61b9cff32eaf12c38`
  - `harness/run_simulated.py` (`schema_view`) `9181a9c587574fac24ba689da20e969c1c2a7ab352183e88ddc70216f4157f65`
  - `harness/graph_view.py` `c12c9de26e37528e9b8e36f5921e255476d62162562abff34c87061c783ff234`
  - `harness/length_experiment/make_inputs.py` `585c7e37ea5f2504ab17e0dc55847b708f8b30ec01628962f4768cdf500d1f99`
  - `harness/length_experiment/run_length_judge.py` `1542af72110f65d34725fc64ef977caa714bc7478d7248cc567d61235288816c`
  - `harness/analyze_holdout.py` `3278d71c70829889838aa8f61c4f5b0217b9ef3e921976a8ea5fc0c0fd122e10`
  - `harness/variants/package_variants.py` `b65bc232d6897161d7104c6a50b09f59b1ad8e7c653d83382c8989bc6ecc56f7`
  - pipeline package `src/chunktograph/` (git blob-list digest prefix `00ec0660e933d2b5`; the run records the full `git rev-parse HEAD` and `git status --short src` again at build time).
- Seed 20260913 everywhere (shuffle order, bootstrap). BCa bootstrap B = 10,000, question-cluster resampling (`cluster_id` = one cluster per question in this bank, 36 clusters), `analyze_holdout.cluster_bootstrap_stat`, midrank ties (default).

All new code lives under `harness/review6_natural/`. No file outside that directory is edited. Nothing is committed except this PLAN.md.

## 27.3 Corpus

**Rule (fixed here, independent of the bank).** Natural-language Brick documentation: hand-written prose in public repositories of the BrickSchema organization, pinned to a commit and fetched from `raw.githubusercontent.com` with a plain request (no User-Agent customization, no e-mail or personal identifier in any header or URL; the default client UA only). Candidate set, decided from the repositories' file trees without reading any bank-related overlap:

| Source | Pin | Included paths | License |
|---|---|---|---|
| `BrickSchema/docs` (source of docs.brickschema.org) | `main` @ `3f92114a643078432c50bc7f9de3ffb8f5980fe1` | `intro.md` and every `*.md` under `brick/`, `extra/`, `lifecycle/`, `metadata/`, `modeling/`, `software/` | BSD-3-Clause text in `LICENSE` ("Brick Development Team") |
| `BrickSchema/brick-website` (source of brickschema.org) | `master` @ `b9506a909d4ccc1abe3234147ce13377f17a6bf9` | every `*.md` under `webpages/`, `blog/`, `tools/`, `ontologyPages/`, `usageDetails/` | MIT (`LICENSE`) |
| `BrickSchema/py-brickschema` | `master` @ `50c7670acce806baa4a1d2c47101bff9bf37162e` | `README.md` and `docs/**/*.rst` except `docs/source/` (API stubs generated from code) | BSD-style text in `LICENSE` |
| `BrickSchema/Brick` | tag `v1.4.4` @ `4b5be60d27f9b4d96fe477f45513fa71afebe684` (the snapshot version of the bank) | `README.md`, `CONTRIBUTING.md`, `extensions/README.md`, `alignments/*/README.md` (top-level `alignments/README.md` included), `examples/simple_apartment/README.md` | BSD-3-Clause (GitHub-reported SPDX) |

Excluded by rule: any TTL/OWL/SHACL/CSV schema file; the `bricksrc/`, `ontology.brickschema.org` and `brick-owl-dl` repositories and every ontology reference page generated from the schema (class/property listings, RealEstateCore ontology pages); `CHANGELOG.md` files (version logs that list term names, not prose); issue templates and repository meta files (`.github/`, `src/`, `static/`); dependency lists. Papers: a paper is added only if its publisher page states a CC-BY/CC0-type reuse license and a plain-text version is fetchable without login; if none qualifies the corpus is documentation-only (decided and recorded in `SOURCES.md`; this is not tuned to the bank).

**Cleaning (deterministic, `build_natural_corpus.py`).** Remove YAML front matter; remove every fenced code block (any language, including `ttl`, `sparql`, `python`, MyST `{code-cell}`), except that MyST admonition directives (`{note}`, `{warning}`, `{tip}`, `{important}`, `{seealso}`, `{attention}`, `{caution}`) keep their inner text as ordinary prose; for `.rst`, drop `.. code-block::`/literal blocks (indented block after a paragraph ending in `::`) and all other directives with bodies except note/warning/tip/important/seealso; remove images, HTML tags and comments, `[[wiki/links]]`, bare URLs; keep link text of `[text](url)`; keep headings (as hierarchy), list items, and table rows (cells joined by ` | `); collapse whitespace; NFC-normalize. Per-file counts of removed code blocks and characters are logged. A file with fewer than 200 characters of prose after cleaning is dropped and listed.

**Chunking.** The pipeline has no raw-text chunker: its stage 1 (`chunktograph extract`, `stage1_extract.extract_atomic_chunks`) consumes a pre-chunked JSON (`chunks[].toc_hierarchy / toc_index / child_chunks.advanced_chunking_result[].title / atomic_chunks[].content.text`, the same nested shape `build_brick_corpus.py` writes and the upstream chunker emits). `build_natural_corpus.py` writes that shape: one top-level chunk per source file (`toc_hierarchy` = [source, file title]); one `advanced_chunking_result` entry per heading section; atomic chunks = paragraphs (a list stays attached to its introducing paragraph), with paragraphs under 120 characters merged into the next paragraph of the same section and paragraphs over 1,000 characters split at sentence boundaries into pieces of at most 1,000 characters. Calibration: the pipeline's own upstream chunking sample (`data/chunking_result.json`) has mean 389, median 315, p90 692 characters per atomic chunk. The output file, its sha256, chunk-length statistics and per-source totals go into `SOURCES.md`/`corpus_stats.json`. Then `chunktograph extract --granularity leaf` is run unchanged on it.

`SOURCES.md` records, per file: source URL (raw), repo, commit/tag, path, license, retrieval date (UTC), sha256 of the fetched bytes, cleaned characters, removed code characters.

## 27.4 Grounding check (before any build; stop gate)

Run once after the corpus is frozen, with no network and no model. Code: `grounding_check.py`. Output: `grounding_check.json` + `GROUNDING.md`; its sha256 is written to the checkpoint file before step 3 starts, and the file is never edited afterwards.

Automated tiers, per question (term search over the cleaned atomic chunks / heading sections):
- **Anchors:** local names from `run_holdout._grounding_anchors(grounding)` (qualified duplicates collapsed to the local name; metadata locals such as `definition`/`comment` already dropped by that function).
- **Term match:** case-insensitive at token boundaries; an anchor's forms are its lowercase string and its camelCase/underscore split into words (`hasPoint` -> `has point`, `Energy_Sensor` -> `energy sensor`); an optional plural `s`/`es` on the last token is accepted. This is a stated relaxation of the artifact-side `_anchor_present`, because prose uses plain words.
- **L0** all anchors occur somewhere in the corpus. **L1** all anchors occur inside one heading section. **L2** L1 and that section also contains at least half of the distinct content terms (>= 4 letters, not in a fixed English stop list, anchors excluded) of the bank's `expected_answer`.

Analyst read (the primary "answer present" measure): for each question, the three highest-scoring passages by term overlap (question + anchors; no model) are read by the person/agent running the experiment, who has seen the bank's `expected_answer`; so this is **not blind**. Rating: `full` (the corpus states the answer as the question is posed, paraphrase allowed), `partial` (the concept is there, the key relation/definition detail is missing; the rubric's "partial"), `none`. The supporting span (or the best near-miss) is stored per question. Reported: counts of L0/L1/L2 and of full/partial/none, per bank category.

**Stop rule.** If (full + partial) / 36 < 0.20 (that is, 7 or fewer questions), **no extractor or judge call is made**: the final report is the grounding check and the statement that the natural corpus cannot support the bank. Otherwise continue.

**Eligible sets (fixed here, from this check only, never from A/B outputs or judge scores).**
- `S_full`: all 36 questions (the primary set).
- `S_elig`: questions rated `full` or `partial` by the analyst read.
- `S_elig_L1` (sensitivity): questions passing automated L1.
- `S_art` (descriptive, depends on the build): questions for which both the A view and the B view pass the holdout's own artifact preflight (`run_holdout._grounding_match_info(view, row)` has no missing required grounding anchors). This set uses only the artifacts, never judge scores.

## 27.5 Variants A and B (built exactly as the holdout variants)

- **Same code and config as the holdout.** Commands are the `harness/variants/README.md` / `build_domain.sh` sequence restricted to A and B: `chunktograph extract`, `chunktograph triples`, `chunktograph build`, `chunktograph split` (B; yields `ontology_B.ttl`) and `chunktograph build-a` (A; yields `ontology_A.ttl`), all with `--granularity leaf`, default pipeline settings (concurrency 8, `CHUNKTOGRAPH_LLM_TIMEOUT=900`, temperature 0 inside the pipeline), the repository HEAD source. C-F are not built. The pipeline-side CQ file is not needed by A/B; the bank is never given to construction.
- **Extractor.** The holdout A/B were built (2026-09-20/21, MANIFEST `model` and `endpoint_host`) with `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8` on <internal-host> through an SSH tunnel. Read-only inspection on 2026-10-17 shows the <internal-host> container `<container>` (<image>, started 2026-09-29, i.e. after those builds) serving `nvidia/Qwen3-Next-80B-A3B-Instruct-NVFP4` under the served-model-name `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8`. This run uses that same served name through a new SSH tunnel (`<local-endpoint> -> <internal-host>:PORT`), **request-only**: no container is stopped, started, reconfigured or touched; nothing is run on <internal-host> except the tunnel. Deviation recorded: the weights behind the registered name may not be the weights used for the holdout build (the alias is identical; the quantization of the 2026-09-20 server cannot be confirmed). A and B in this experiment share the same server, model and window, so the A -> B contrast here is matched.
- If <internal-host> cannot be reached, the shared server (`ssh -p PORT`, request-only) is the fallback; if neither serves the model, the run stops and reports it. The local `qwen-next-flash` (<internal-host>, :PORT) is the holdout's *original* stand-in and is NOT used silently; using it would be a logged deviation.
- **Instrumentation only.** `run_pipeline.py` imports `chunktograph.cli.app` and wraps `chat.completions.create` of the OpenAI client held by `LLMClient` to accumulate `usage` (prompt/completion tokens, calls, failures) per command into `build_usage.jsonl`. The request bodies are not changed. An LLM call that raises is recorded, not retried by this wrapper.
- **Failure handling.** The pipeline's existing guards are kept (stage A refuses a hollow baseline; stage 4 refuses a silently untyped ontology). If A or B fails a guard, that is reported as a finding; the guard is not loosened, and the experiment stops without scoring a hollow artifact.
- **Packaging.** `package_natural.py` copies `ontology_A.ttl` / `ontology_B.ttl` to `variants/<V>/graph_<V>.ttl` and writes `variants/<V>/rendered_view.txt` with the registered `run_simulated.schema_view` (identical call to `package_variants.py`), plus a `MANIFEST.json` per variant with graph/view/corpus/bank digests, model name, endpoint kind, and the SIMULATED-style warning. The frozen rendering spec is unchanged.

## 27.6 Views and judge

- **Subgraph view (primary).** `make_inputs.generate(bank, out_dir, ("A","B"), variants_dir=<natural variants dir>, exclusions=frozenset())` -- the same function the luna subgraph run used (hop-2 ego graph from question tokens only, rendered with `schema_view` on the induced sub-graph). Questions with no matched node are `not_applicable` (no call).
- **Full view (conditional).** The whole `rendered_view.txt` per question. Run only if, after the subgraph run, (actual subgraph input tokens + estimated full-view input tokens of all 72 calls) <= the budget below, and every full view is below 3,300,000 characters (luna's context window is 922,000 tokens; the estimate is chars/4). Otherwise the full view is not run, and the report says why.
- **Judge.** `gpt-5.6-luna` via <internal-proxy> `http://<local-endpoint>/v1` (the endpoint of the earlier luna runs; model supply only through <internal-proxy>), temperature 0.0, `max_tokens` 1024, same `RUBRIC`, same `call_judge` pacing/429 rules, `response_format` overridden to `{"type":"text"}` through the top-level extra field exactly as in addendum 23, response parsed with `json.loads` (unparseable = invalid cell). The API credential is read from the environment, with the <internal-proxy> local placeholder as the fallback used in the earlier luna scripts; nothing credential-like is printed or written.
- **Order and concurrency.** All A and B cells of a condition are shuffled together with seed 20260913 (so any serving drift hits both variants alike); `workers` <= 3.
- **Token budget.** 6,000,000 estimated input tokens in total (estimate = ceil((artifact chars + rubric + framing + question chars)/4), `run_length_judge.overhead_chars`; actual `usage` from responses is recorded too). Pre-call rule: do not issue a call if (tokens already used + that call's estimate) > budget. Stop rule: any HTTP 402/403, or a 429 that survives the retry loop, stops new calls and keeps finished cells (the 2026-10-14 quota exhaustion is the precedent); invalid cells are retried once per resume, never silently dropped.
- Estimates are made and recorded before the first judge call (dry run).

## 27.7 Analysis (descriptive; intervals, no decisions)

For each condition (subgraph; full if run) and each question set (`S_full`, `S_elig`, `S_elig_L1`, `S_art`):
1. **Coverage per variant** = mean(J)/3 x 100 (the paper's coverage formula applied to the raw judge score J, since no human evidence label exists here), and share of J >= 2, each with a question-cluster BCa 95% interval (`cluster_bootstrap_stat`, B = 10,000, seed 20260913). J distribution (0-3 counts).
2. **A -> B contrast** = pooled mean of per-question differences (J_B - J_A), question clusters resampled (the same estimator and routine as the holdout's primary contrast, `analyze_holdout` lines 2348-2370): 95% BCa interval (90% also), reported on the J scale and in coverage points (x 100/3); number of questions in `S`; share of questions where B > A, B = A, B < A; Wilcoxon signed-rank with zeros dropped (descriptive; `wilcoxon_zeros_dropped`), exact agreement and QWK between A and B scores.
3. **Not-applicable handling (subgraph).** Primary: a question whose A or B subgraph is `not_applicable` leaves the paired set (addendum 17 rule); count reported. Sensitivity: not_applicable scored J = 0 (the rubric's "no related concept present"). If the full view is run, the full-view fallback is reported as a third reading.
4. **Machine evidence check (descriptive, not a label).** For each scored cell with J >= 2, test whether the judge's `evidence` span occurs verbatim (whitespace-normalized, case-sensitive) in the view that was sent. Report, per variant, the share of J >= 2 cells with a verbatim span, and a "machine-adjusted" score `J*` = J if span verbatim else min(J, 1) with its A -> B contrast, mirroring the holdout's one-sided demotion. This substitutes a string test for the human evidence label, so it says nothing about whether the span truly supports the answer.
5. **Reference comparison (descriptive).** The same contrast from the template-corpus luna subgraph cells already on disk (`harness/length_experiment/cells_length.jsonl`, condition `subgraph`, variants A and B, valid cells, read-only; their questions are the template corpus' eligible questions, 22 paired). Side by side with the natural result on the same questions, and the question-cluster BCa interval of the difference of the two per-question contrasts on the questions present in both. Different corpora and different scoring dates; no formal test of "equal".
6. **Grounding bound.** Coverage and contrast on `S_elig` versus `S_full`, with the analyst-read counts, state how much of the bank the natural corpus can reach at all.
7. Artifact descriptives: triples, entities, classes per variant; view lines/chars; extractor calls and token use per stage (from `build_usage.jsonl`).

Nothing in the analysis uses a human label, the sealed annotation files, or any model other than the extractor and luna.

## 27.8 Outputs (all under `harness/review6_natural/`)

`PLAN.md` (this file, committed), `SOURCES.md`, `corpus/` (raw fetched files with sha256 list, cleaned text, `natural_corpus.json`), `corpus_stats.json`, `grounding_check.json`, `GROUNDING.md`, `_work/` (pipeline outputs, caches), `build_usage.jsonl`, `variants/{A,B}/`, `inputs/` (subgraph texts + manifest), `cells_natural_subgraph.jsonl` (and `..._full.jsonl` if run), `results.json`, `REPORT.md`. Checkpoint lines go to the session scratchpad progress file after each step. Only `PLAN.md` is committed.

## 27.9 Limitations and interpretation limits (fixed in advance)

- The bank was authored against the TTL snapshot, so a low coverage on prose is partly a corpus-coverage fact, not an artifact fact; this is why `S_elig` and the grounding counts accompany every number.
- Docs are pinned to current documentation commits (docs/website/py-brickschema) plus the `v1.4.4` repo README files; wording may describe Brick versions other than v1.4.4.
- luna is a substitute judge, not the registered judge, and scores raw J without human evidence labels; results are not comparable to the registered holdout J.
- The extractor weights behind the registered served-name may differ from the 2026-09 build (27.5); A and B here are matched with each other, not provably with the holdout.
- 36 questions, one corpus draw, one run per cell: an interval, not a demonstration. `J` at temperature 0 is not guaranteed deterministic; no repeat is planned.
- If the stop rule fires, the finding is the grounding result itself.
- Before any external use of numbers from this run, confirm no confidential company information, personal information or credentials entered the outputs (the corpus is public documentation; no such data is intended).

---

## 27.A1 Amendment 1 (dated 2026-10-17, written after the luna block and before any valid scoring): replacement judges and same-judge template comparison

> AI-drafted; the author must review it. This section changes 27.1, 27.6 and 27.7 only where stated; everything else (corpus, grounding check, eligible sets, A/B build, the frozen bank, the subgraph inputs and their manifest) is unchanged. All code and commands named here are AI-generated and must be reviewed and tested by a person before reuse.

**A1.1 Reason.** The planned judge (`gpt-5.6-luna` via <internal-proxy> `http://<local-endpoint>/v1`) answered HTTP 429 (three retries, Retry-After 3-60 s) and then HTTP **402 Payment Required** on all three in-flight calls (B:CQB01, B:CQB10, B:CQB29) on 2026-10-17. PLAN 27.6 stops new calls on a 402. Those three records are **invalid, carry no score, and are discarded from every analysis**; they are kept only as evidence of the block in `luna_402_discarded/`. **No luna score exists for the natural corpus and none will be used.** The luna runner `run_natural_judge.py` is superseded and refuses to run.

**A1.2 Replacement judges (two, both non-Qwen; the judges of addendum 26 / `harness/review6_judges/PLAN.md`, plan commit `87355a0`).**

| id | model | server |
|---|---|---|
| `gptoss` | `openai/gpt-oss-20b` | vLLM container on the shared server (`<internal-host>`), `max_model_len` 65,536 |
| `glm` | `zai-org/GLM-4.7-Flash` | vLLM container on the same server, `max_model_len` 65,536 |

Both judges are run and reported **separately**; no pooled number is primary. They are not the registered holdout judge, not luna, and not the extractor's family; their scores are not comparable to the registered holdout J or to luna scores.

**A1.3 Prompt and decoding (identical to addendum 26's holdout study; reused, not edited).**
- System message `run_holdout.RUBRIC` (string sha256 `85e208799f10b756125c524dc43222064ac946f3c01f000ee03cf331800cee72`, the holdout judge prompt: 0-3 answerability anchors and the JSON instruction); user message `ARTIFACT:\n{view}\n\nQUESTION: {question}` as `run_holdout.call_judge` builds it. Only the question text and the subgraph view are sent; the bank's `grounding` and `expected_answer` never are.
- Scoring code: `harness/review6_judges/score_judges.py` imported unchanged (sha256 `3788576cd22eb73d7568d032a4db869de3a195c76c5cbeb6e6f42f5e6239a753`, checked at run time): temperature 0.0, `response_format` json_object, `max_tokens` 1024, thinking-minimal switch (`gptoss`: `reasoning_effort: "low"`; `glm`: `chat_template_kwargs.enable_thinking=false`), retry of an empty/malformed/out-of-range/truncated reply with `max_tokens` 4096 at most twice, nothing imputed (a cell that stays invalid is excluded and listed), 429/5xx/network retries 3 times, a 400 context error recorded as `context_skip`. **3 repeats** per (cell, judge), separate passes in a seeded shuffle (seed 20260913 + 1000 x repeat), as in addendum 26. Temperature 0 means repeat differences are serving nondeterminism, not sampling variance.
- Cell score of a judge = **mean of its valid repeats**.

**A1.4 Natural-corpus jobs.** 72 subgraph cells (A 36, B 36; no `not_applicable`) built by `build_natural_jobs.py` from `inputs/manifest.jsonl` (sha256 `0048910bf97d3ebfdfed58852201911b168fea4481ff61ad058ef777c229ac2e`) into `jobs_natural.jsonl` with the same record schema and `prompt_sha256` rule as `review6_judges/build_jobs.py`. Largest view about 10.6k tokens by chars/4. Calls: 72 x 3 repeats x 2 judges = **432**. A tokenizer preflight (`/tokenize`, no generation) runs on every cell first; a cell with prompt + 4,096 > 65,536 is skipped and logged. **Full views are not scored**: B's full view (1,053,272 chars) cannot fit a 65,536-token window and the estimate (11.97M tokens) exceeded the budget anyway.

**A1.5 Same-judge template comparison.** To keep the natural-versus-template comparison inside one judge, the template-corpus A and B **subgraph** views are scored by the same two judges: the 54 `holdout_subgraph` cells of addendum 26 (A 22, B 32; the 188 primary holdout cells minus documented exclusions and minus the 6 cells without a subgraph; paired A->B questions: 22). **Addendum 26's records are reused** for a (cell, judge, repeat) when the record is valid, its `prompt_sha256` equals the value recomputed here from the same inputs (`length_experiment/inputs/<V>/<CQ>/subgraph.txt`, manifest sha256 `46277713...ceaa32` checked), and the scorer is the pinned file above. Anything missing or not matching is scored here with the same code. Reused records are copied into this directory with a `reused_from_addendum26` flag; nothing in addendum 26's files is edited. The luna template numbers (+0.09 J on 22 questions) stay outside the comparison and are quoted only as historical context.

**A1.6 Timing and access (request-only).** No call to the shared-server endpoints before addendum 26's call phase is finished: both its scoring processes (`score_judges.py` in `tmux` on the host) have ended and both endpoints show zero running and waiting requests; the wait uses a monitor loop, not repeated sleep polling. Access is read-only status checks plus SSH port forwarding from this machine to the two endpoints; at most **3 concurrent requests per endpoint**; no container is stopped, started, restarted or reconfigured; nothing is installed or written on the host. If an endpoint is unreachable or its context is too small for the 72 texts, that is reported and the run stops for that judge (no fallback judge). Stop rule per judge: 10 consecutive cells that end as network/5xx errors or context errors stop that judge's run; finished cells are kept.

**A1.7 Budget.** Estimated natural prompt tokens (chars/4, rubric included) about 0.5M per pass, so about 3.0M for 432 calls, plus up to about 2.6M if all template cells had to be scored here. Budget **12,000,000 prompt tokens** (server `usage`) across both judges; a judge stops before a call that would exceed its share (6,000,000 each).

**A1.8 Analysis (replaces 27.7 where it differs; descriptive, no decisions).** Per judge: (1) coverage per variant = mean(cell score)/3 x 100 and share of cells with mean score >= 2, with question-cluster BCa 95% intervals (`cluster_bootstrap_stat`, B = 10,000, seed 20260913); score distribution of rounded cell means. (2) A->B = pooled mean of per-question differences of cell scores (B minus A), same routine, 95% and 90% intervals, in score units and coverage points, with counts of B>A/B=A/B<A, Wilcoxon (zeros dropped) and exact agreement/QWK of A vs B. Question sets `S_full`, `S_elig`, `S_elig_L1`, `S_art` as in 27.4 (fixed before any call). (3) Run-to-run: per judge and corpus, mean pairwise exact agreement over repeats and the share of cells with identical repeats; invalid and context-skip counts. (4) Machine evidence check as in 27.7-4, applied per record (a string `evidence` must occur verbatim in the view after whitespace normalization; a list counts only if every non-empty element does). (5) **Natural vs template under the same judge:** per judge, the template A->B on the 22 paired questions, and on the questions present in both corpora the question-cluster BCa interval of the difference of the two per-question A->B contrasts (natural minus template). (6) Cross-judge: sign agreement of the natural A->B and quadratic weighted kappa between the judges' per-repeat scores on the natural cells. (7) Cost: calls, prompt and completion tokens from server `usage`, wall time. Not-applicable rule, sensitivity (NA = 0, none arises) and set definitions are as in 27.7.

**A1.9 What this session knows before the first valid call.** The luna block; the grounding check (full 15 / partial 9 / none 12 of 36) and eligible sets; the artifact-anchor retention (A 22/36, B 20/36); the template luna A->B (+0.09 J on 22 questions); addendum 26's plan and progress checkpoints (invalid counts only). **No judge score of `gptoss` or `glm` for any natural or template cell has been read.**

**A1.10 Limitations added.** Two judges from two families, one natural corpus draw, 36 questions; shared servers with uncontrolled load and quantization; thinking-minimal switch and the 4,096-token retry are deviations from the registered single 1,024-token attempt; reused template records were produced by another session under addendum 26's plan and are read here as given; a different judge pair than 27.6 means no result of this amendment is comparable to luna or to registered-judge scores.

---

## 27.A2 Amendment 2 (dated 2026-10-17, written before any valid scoring): a same-family contrast judge on <internal-host> and side-by-side reporting

> AI-drafted; the author must review it. Adds one judge to amendment 27.A1; nothing else in 27.A1 changes.

**A2.1 Instruction and role.** The author asked that the Qwen model served on <internal-host> also score the same cells, in place of luna, labelled **"same-family judge (contrast)"**. The reviewers' main attack is the overlap between the judge's family and the extractor's family (the extractor is `Qwen/Qwen3-Next-80B-A3B-Instruct`). The **primary judges stay the two non-Qwen shared-server judges** of 27.A1 (`gptoss`, `glm`); the Qwen judge is a contrast, never the headline, and no judge is ranked as better. A->B is reported under all judges **side by side**.

**A2.2 Server (confirmed read-only on 2026-10-17).** On `<internal-host>` the container `<container>` (<image>, started 2026-09-30, up, healthy) serves `nvidia/Qwen3.8-Flash-Next-NVFP4` under the served-model-name **`Qwen/Qwen3.8-Flash-Next`** on host port PORT (`max_model_len` 262,144; reasoning parser `qwen3`, thinking on by default). `/v1/models` answered 200 with the placeholder key committed in the pipeline's own config; no other credential was read, copied or printed. This is the Qwen3.8-Flash-Next model line the author called "qwen-next-flash"; the server itself does not use that name, and the <internal-host>-local `qwen-next-flash` (Qwen3.8-Flash-Next-125B-A5B INT4-AutoRound) is a different serving that is **not** used. Whether the weights match any earlier "qwen-next-flash" run cannot be confirmed. The `nvidia-smi` NVML mismatch on that host is irrelevant to request-only use.

**A2.3 Judge id and settings.** Judge id `qwenflash`, label "same-family judge (contrast)". Same system and user prompt as 27.A1 (`run_holdout.RUBRIC`, `ARTIFACT:\n{view}\n\nQUESTION: {question}`), same unmodified scoring code (`score_judges.py`, sha256 `3788576c...a753`); the driver registers the judge at run time in the scorer's judge table (no file edited): model `Qwen/Qwen3.8-Flash-Next`, thinking-off switch `chat_template_kwargs: {"enable_thinking": false}` (the vLLM switch used for the earlier Qwen substitute judges; it is this judge's analogue of the other judges' thinking-minimal switch), temperature 0.0, json_object, `max_tokens` 1024, retry with 4096 at most twice, nothing imputed, 3 repeats, seeded shuffles, cell score = mean of valid repeats.

**A2.4 Cells and budget.** The same 72 natural A/B subgraph cells and the same 54 template A/B subgraph cells (A 22, B 32) as 27.A1, all scored here (addendum 26 has no Qwen-judge records): 126 cells x 3 repeats = **378 calls**. Budget 3,000,000 prompt tokens (server `usage`). A tokenizer preflight runs first; a cell over the window is skipped and logged (none expected at 262k).

**A2.5 Access and timing.** Request-only through SSH port forwarding from this machine to <internal-host>:PORT; **at most 3 concurrent requests**; no container stopped, started or restarted; nothing written on the host. The server is shared (other jobs run on it), so the same stop rule as 27.A1.6 applies (10 consecutive network/5xx/context failures stop this judge's run; finished cells are kept). This run does not depend on addendum 26's shared-server phase and may run while the shared-server judges wait for it.

**A2.6 Analysis additions.** Everything in 27.A1.8 is computed for `qwenflash` as well, and the report puts the three judges in one table: natural A->B and template A->B (with 95% BCa intervals, `S_full` and `S_elig`) per judge, the natural-minus-template difference per judge, the sign agreement of A->B across judges, and the family labels (primary: non-Qwen; contrast: same-family). The comparison is descriptive: a difference between the contrast judge and the primary judges is a fact to report, not evidence about which judge is right.

**A2.7 What this session knows before the first valid call.** As in 27.A1.9; additionally the container facts in A2.2 (read-only). No `qwenflash`, `gptoss` or `glm` score for any natural or template cell has been read.

**A2.8 Limitations added.** The contrast judge shares a vendor and model line with the extractor but is a different checkpoint and quantization (NVFP4), so "same family" means shared lineage and training recipe, not the same weights; a shared server whose load is uncontrolled; a thinking-off switch that deviates from the registered single 1,024-token attempt exactly as for the shared-server judges.
