# Auditing an LLM Judge for Competency Question Coverage: Verbatim Quotes Are Not Support: replication package

> **Review-site notes (added on GitHub Pages after packaging; data files unchanged).**
> **AH** = the first author's labels, as defined in the manuscript (LLM-assisted, revised by the first author).
> **Dwell** = the server's save time minus the page-load time of each label (median 9.3 s). A few long values (e.g. 3,482 s, 424.6 s) mean the labeling page stayed open before the save; they are kept as recorded.
> This README differs from the packaged copy only by this note; `index.html` and `.nojekyll` were added for the site.


Version 1.0.0, built 2026-11-01 (`cq-coverage-access2026-20261101.zip`).
Archive DOI: to be assigned by Zenodo (this line and `CITATION.cff` are updated when the package is rebuilt with the reserved DOI).

Authors: Minwoo Kim, Mingyu Jeon, Philje Bang, Junpyo Lee, Hail Jung and Hongdon Lee, in the order of the paper (affiliations and ORCIDs: `CITATION.cff`).
Contact: the corresponding-author addresses printed in the paper. How to cite: see `CITATION.cff`.

This package accompanies the IEEE Access manuscript above (`main.pdf`, with its supplement `supplement.pdf`). It
contains what the manuscript's Data and Code Availability statement promises, minus the items listed under
"Not included".

## Read this first

- **AI-generated material.** The judge outputs (`harness/real_run/cells.jsonl`), the auxiliary labels
  (`harness/real_run/llm_auxiliary_*`, `llm_aux_corrected.json`), the AI drafts (`locked_labels/draft_224.csv`), the Korean
  translations of the questions (`harness/real_run/annotation_pending/cq_ko.json`) and the paraphrase drafts in `bank/`
  are AI-generated.
- **The locked labels are not independent human labels.** `locked_labels/` holds the AH pass: LLM-assisted labels
  (AI-drafted, author-revised) from a single rater who is the author, who also consulted a chat model on about half of
  the cells without recording which. Every statistic computed from them is exploratory.
- **Not conducted.** No washout re-score and no second, non-author annotation was carried out (`PREREG.public.md`,
  addendum 14). The sealed copies of the per-cell results were unsealed by that addendum; the unsealed copies are in
  `harness/real_run/results_human_pass/unsealed_2026-10-09/`.
- **Scrubbed copies.** Files here are copies from which local paths, hostnames, endpoints and tool session identifiers
  were removed (see "Scrubbing and integrity"). Digests quoted in the manuscript refer to the original files.

## What is in the package

| path | content |
|---|---|
| `bank/` | the frozen 36-question scored Brick bank (`cq_bank_brick_v1.csv`), its 60-row pool (`cq_bank_brick_v2.csv`) and the earlier draft (`v0`), groundings, the 60 SPARQL `ASK` queries in `ask_queries/` (one per pool question), paraphrases and their freeze record, verifiers and their tests |
| `data/`, `domains/brick.toml` | the frozen Brick Schema v1.4.4 snapshot, its freeze record and the upstream licence; the Brick domain parameters that the harness loads by default |
| `rubric/` | the Layer-1 rubric and the rendering specification (both frozen by digest) |
| `annotation/` | labeling protocol, calibration plan, label-packet builder and templates; the blind multi-rater package (`multirater_2026-10/`: packet builder, agreement and adjudication scripts, rater guide, tests, a synthetic dry run and the labeling site; `[[TBD]]` marks fields that `RATER_GUIDE_ko.md` and `ADJUDICATION_MULTIRATER.md` leave open for the author); the second rater's labels (`second_pass_2026-10-13/v3/`) |
| `harness/*.py` | judge runner, registered analyzers, packet builders, validators, labeling tool, and their tests |
| `harness/variants/` | the six pipeline-variant artifacts A to F (graphs, rendered views, manifests) |
| `harness/release_graphs/` | the graph files A to F of the development corpus (*Ontology Development 101*) and of DCAT 3 with the F-stage shapes and dedup reports, a README with source, build and sha256 per file. The two source e-mail literals of `ontology_A.ttl` and one W3C mailing-list address of `graph_A.ttl` are masked in this copy. SOSA/SSN and PROV graphs are not included (their digests and counts are) |
| `harness/real_run/` | the run: `MANIFEST.json`, `cells.jsonl` (224 judged cells), auxiliary checks, lock record, label sheets, rendered views, results |
| `harness/real_run/results_human_pass/` | registered analysis outputs: rater-safe, strict-ties sensitivity, judge-only, legacy counts, dwell-skew check, `unsealed_2026-10-09/` (including per-cell values) |
| `harness/real_run/ask_alignment/`, `second_judge/`, `results_human_pass/exploratory_reanalysis*` | later analyses, present when finished at build time (`second_judge/` is a small probe, marked by `PROBE_NOTICE.md`, not used as a result) |
| `harness/review6_reanalysis/`, `review6_judges/`, `review6_natural/`, `review6_raters/`, `review9_verbatim/` (when committed) | the review-round analyses: scripts, per-call records, `results.json`, reports and the plan of each (`PLAN.md` of the last three are addenda 26 to 28). `review6_natural/corpus/` holds third-party text (see Licences). Scrubbed at build time |
| `harness/length_experiment/`, `harness/r34_bprime/`, `harness/real_run/ask_alignment_v2/`, `harness/real_run/paired_ai_audit_48/`, `harness/cost_latency/`, `harness/r31_analyses/`, `harness/llm_rater_luna_2026-10-15/` | further post hoc analyses named in the supplement (rendering-length experiment, B to B-prime recovery on the second domain (aggregate scores and graph counts only), predicate-aligned oracle, paired AI audit, call and latency tally, LLM-rater labels) |
| `locked_labels/` | the locked AH-pass files: labels, audit log, session log, AI drafts, and their digest list |
| `PREREG.public.md`, `REDACTION_LOG.md` | redacted public copy of the pre-registration (addenda 1 to 14) and the log of what was redacted |
| `PREREG_ADDENDUM_16_DRAFT.md`, `_17`, `_18_DRAFT.md`, `_21` to `_25` | later addenda that exist as separate files, scrubbed (16 is the freeze body; 16 and 18 are the unfrozen drafts that the supplement names; addenda 26 to 28 are the `PLAN.md` files above) |
| `MANIFEST.sha256`, `SCRUB_NOTES.md` | integrity manifest of this package; before/after digests of every scrubbed file |
| `LICENSE`, `LICENSE-DATA-CC-BY-4.0.txt`, `data/LICENSE-Brick-BSD-3-Clause.txt` | licences |
| `requirements.txt`, `.python-version` | environment |

The root of the package corresponds to `paper/access2026/` of the source repository, so relative paths in the code and
in the provenance files resolve from the package root. Provenance files that named the author's private, read-only
directory of locked files now say `locked_labels/`, which is the directory of that name in this package.

## Licences

| part | licence |
|---|---|
| code: `*.py`, tests, scripts | MIT (`LICENSE`) |
| data and documents: bank, rubric, protocol documents, results, locked labels, `PREREG.public.md`, this README, the PDFs | CC BY 4.0 (`LICENSE-DATA-CC-BY-4.0.txt`) |
| `data/brick-v1.4.4.ttl` and files derived from it (`harness/brick_corpus.json`, `harness/variants/`, definitions quoted in the bank) | BSD-3-Clause, Brick Consortium, Inc. (`data/LICENSE-Brick-BSD-3-Clause.txt`). The upstream notice is retained and applies to those files in addition to the licence above |
| `harness/release_graphs/` | graphs derived from *Ontology Development 101* (Noy and McGuinness 2001, publicly distributed technical report: concept labels and structure only, the document text is not included) and from the W3C DCAT 3 Recommendation (W3C Software and Document Notice and License, which permits copying and redistribution with notice; the ontology file is CC BY 4.0). Released under CC BY 4.0 with attribution to the two sources; rights in the sources stay with their owners |
| `harness/review6_natural/corpus/` and the Brick-derived graphs and judge inputs next to it | text of public Brick documentation and web pages and of two open-access papers; the upstream licences apply (BSD-3-Clause for the Brick, docs and py-brickschema repositories, MIT for the website repository, CC BY for the papers; sources, pins and licence texts: `harness/review6_natural/SOURCES.md`). E-mail addresses in these texts are masked |
| `annotation/multirater_2026-10/labeling_site/index.html` | released as used; it loads web fonts from Google Fonts and the Cytoscape.js library from cdnjs when opened (note appended to the README of that folder) |

Judge outputs and drafts were generated by third-party models; no claim of exclusive rights is made over model output.
The published version of the article is governed by the publisher's terms.

## Scrubbing and integrity

- `sha256sum -c MANIFEST.sha256` (run in the package root) checks every file in the package.
- `SCRUB_NOTES.md` lists each file that was changed during release preparation, with its SHA-256 before and after.
  The changes are only: absolute local paths replaced by relative paths or `<repo>/`, `<home>/`, `<tmp>/`,
  `<labels>/`; tool session identifiers replaced by one-way pseudonyms (`S-` plus eight hex digits of the SHA-256 of
  the identifier); internal hostnames, local endpoints and proxy names in provenance text replaced by placeholders;
  and, in a few code files, internal endpoint constants replaced by `localhost:PORT` and one hostname in a comment
  replaced by "an internal host". In the review-round material (and any other text file) host nicknames, container and image
  names, port numbers, ssh options and the proxy's name and model route are replaced by placeholders (`<internal-host>`, `shared server`,
  `<container>`, `<image>`, `PORT`, `<internal-proxy>`; in Python code, identifiers that carried the proxy's name became
  `INTERNAL_PROXY`/`internal_proxy`), third-party e-mail addresses in `harness/review6_*` by `<email>`, and a few sentences about
  accounts, credentials and container launch arguments by neutral wording. Set `HOLDOUT_JUDGE_ENDPOINT` (and `AUX_CHECK_ENDPOINT`) yourself to rerun a judge.
- The digests of the locked files cited in the manuscript are the digests of the originals. `locked_labels/` here
  carries the scrubbed copies (absolute paths in the `rendered_view_path` column and tool session identifiers). The
  label columns (`A`, `rater_L1`, `evidence_span_verbatim`, `note`) are unchanged. The registered analysis run on these
  copies reproduces every reported number (see below); only the recorded input digests differ.
- `PREREG.public.md` replaces `PREREG.md` (original digest `05ad3e0f1840ee0a346356c47a3cc38e48060383418f6a13bc9700c0ba3eecf0`,
  the digest printed in the manuscript). See `REDACTION_LOG.md`. The unredacted original is available to editors and
  reviewers on request.

## Environment

Linux, Python 3.12 (`.python-version`; checked with 3.12.3), `numpy 2.4.6`, `scipy 1.17.1`, `rdflib 7.6.0`,
`pytest 9.0.3` (`requirements.txt`). Everything else is the standard library. No network access and no API key is
needed for the commands below.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
sha256sum -c MANIFEST.sha256
```

## Reproduce

Run from the package root. Write outputs outside the package tree. (The analyzer prints a notice that per-cell output
should stay sealed until after the washout; addendum 14 lifted that seal. The helper scripts in `results_human_pass/`
write their JSON next to themselves, so run them on a copy of the package or restore the file afterwards.)

1. **Frozen inputs.**
   `python3 bank/verify_bank.py` re-derives the bank groundings against the frozen snapshot (expect `missing: 0`).
   `python3 harness/verify_reproducibility.py` checks the digests of the bank, rubric, rendering specification and
   snapshot and the seed. It also looks for `PREREG.md` and `main.tex`, which are not in this package, and therefore
   reports exactly one failure ("missing PREREG/main.tex"). All other checks pass. To check the pre-registration,
   compare the original's digest in `REDACTION_LOG.md` with the one printed in the manuscript.
2. **Tests.**
   ```bash
   python3 -m pytest -q harness bank annotation scripts \
     --deselect harness/test_ask_alignment_v2.py::test_determinism_byte_identical \
     --deselect harness/test_ask_alignment_v2.py::test_before_equals_v1_and_mapping_unchanged \
     --deselect harness/test_ask_alignment_v2.py::test_graphs_untouched_and_schema \
     --deselect harness/test_ask_alignment.py::test_outputs_record_the_current_input_hashes \
     --deselect harness/test_build_washout_packet.py::test_the_main_checkout_is_refused_as_well_as_the_worktree \
     --deselect harness/test_label_assist_security.py::test_the_real_checkouts_are_refused_for_out_and_sealed_paths \
     --deselect harness/test_packet_common.py::test_repo_relative_never_leaks_a_foreign_absolute_path \
     --deselect harness/test_exploratory_reanalysis.py::test_path_guards \
     --deselect harness/test_exploratory_reanalysis.py::test_committed_artifacts_are_consistent_with_the_code
   ```
   The deselected tests assume the original git checkout (they call `git rev-parse` or check the repository layout), or
   compare a recorded digest of a file that the release scrub changed, or test a guard on a path literal that the
   scrub rewrote, or read a file that is withheld (the labeling-sheet key). Outside the original repository they fail by construction, not through a defect in the analysis code.
   Everything else is expected to pass.
3. **Registered analysis** (from `harness/real_run/results_human_pass/README.md`, with the package paths):
   ```bash
   L=locked_labels; O=/path/outside/the/package
   python3 harness/analyze_holdout.py harness/real_run/cells.jsonl \
     --labels $L/primary_working.csv --label-source human \
     --label-audit $L/primary_working.csv.audit.jsonl \
     --unblind-boundary 2026-10-09T00:23:09+09:00 --drafts $L/draft_224.csv --seed 20260913 \
     --out $O/holdout_results_human.json --out-cells $O/per_cell.json
   # strict-ties sensitivity: add  --bca-ties strict  and write to sensitivity_bca_strict.json
   ```
   Expected: every number equals the file in `harness/real_run/results_human_pass/unsealed_2026-10-09/`
   (`*.rerun_0dbe6e9.json`). The only differences are `input_provenance` entries (the path prefix, and the digests of the
   scrubbed label and audit files; compare them with `SCRUB_NOTES.md`).

| result in the manuscript | where it comes from | how |
|---|---|---|
| Brick holdout Layer-1 Coverage per variant, with CQ-cluster BCa intervals, and the A to B contrast (table `holdout-coverage`) | `results_human_pass/holdout_results_human.rater_safe.json`, `sensitivity_bca_strict.rater_safe.json`, `unsealed_2026-10-09/` | step 3 |
| Registered gates G1 to G8 (table `gates`), including G4 and G5 | `unsealed_2026-10-09/holdout_results_human.rerun_0dbe6e9.json` | step 3 |
| Judge score against the rater's 0 to 3 score (table `confusion`) | `unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json` | step 3 (`--out-cells`) |
| Judge-only coverage and contrasts, no labels | `results_human_pass/judge_only_J.json` | `python3 harness/real_run/results_human_pass/judge_only_J.py harness harness/real_run/cells.jsonl` (rerun result is byte-identical) |
| Counts from the judge pass and the auxiliary check | `results_human_pass/legacy_counts.json` | `python3 harness/real_run/results_human_pass/legacy_counts.py` (byte-identical) |
| Corrected auxiliary-check values (deviation D2) | `results_human_pass/llm_aux_corrected.json` | step 3 with `--labels harness/real_run/llm_auxiliary_as_labels.csv --label-source "LLM, not human"` and without the audit, boundary and drafts options |
| Time-measurement check behind gate G7 | `results_human_pass/dwell_skew_check.json` | `python3 harness/real_run/results_human_pass/dwell_skew_check.py locked_labels/primary_working.csv.audit.jsonl locked_labels/primary_working.csv.session_log.txt` (same numbers; only the two recorded input digests differ) |
| `ASK`-oracle concordance (not computable on the holdout graphs) | `scripts/probe_ask_oracle_vs_holdout_graphs.py`, `bank/ask_queries/`, `harness/real_run/ask_alignment/` | the scripts' own docstrings |
| Design and deviation tables (`related`, `deviations`), plan and power tables of the supplement | derived from `PREREG.public.md` and the files above; not computed from data | n/a |
| Ontology-101 pilot tables (`contrasts`, `budget`, supplement S4 to S6) and the second-domain section | **not reproducible from this package** | see "Not included" |

The judge pass itself (`harness/run_holdout.py`) needs an OpenAI-compatible endpoint and a key; it cannot be rerun
here, and the serving endpoint of the original run is internal. `harness/real_run/MANIFEST.json` records model and
decoding parameters, and `cells.jsonl` records every raw judge response.

## Not included

- `persona_pass` material (an exploratory run that was not completed and is not reported).
- The sealed pre-unsealing copies of the per-cell results (the unsealed copies are included).
- Internal operations documents (owner runbook, run runbook, dry-run report), drafts, caches, logs, regenerable
  pipeline intermediates (`harness/variants/_work/`), simulated and discarded runs, and the pipeline package needed to
  regenerate the variants.
- The Ontology-101 pilot and the second-domain study: the Ontology-101 source document and the second domain's source
  manual are third-party or internal material whose redistribution is not cleared. No text, graph or question derived from them is
  included; only aggregate scores and graph counts of the second domain's B to B-prime recovery (`harness/r34_bprime/`) are.
- `harness/run_second_judge.py`, `harness/paired_ai_audit_preflight.py`, `harness/analyze_paired_ai_audit.py` and their tests: they carry the
  endpoint configuration of an internal model proxy (the analyzer imports the runner). Their outputs are here
  (`harness/real_run/paired_ai_audit_48/` and, when present, `harness/real_run/second_judge/`).
- Answer keys and rater material of the blind multi-rater study (the site key, the labeling-sheet key, the export of rater labels and the
  rater view package) and two author-only files of `annotation/expert_quality_2026-10/` (`artifacts.json`, `coverage_reference.csv`).
- Two operations scripts for shared GPU hosts (an idle-check probe in `review6_natural/` and an ssh port-forward launcher in `review6_raters/`), operation logs, and the PDF files of two third-party papers
  (`review6_natural/corpus/raw/paper-*/paper.pdf`; their text extraction with masked e-mail addresses, the URL and the digest are here).
- Two test files that cannot run here (`harness/test_domain_regression.py` needs second-domain inputs and the unreleased pipeline package; `harness/test_readability_guards.py` reads `main.tex`).
- Anything that was not committed in git when the package was built: the package is made from committed files only.
- The washout sheet (the washout was not conducted), `PREREG.md` and `main.tex` themselves, and the unfrozen drafts of addenda 12, 15, 19 and 20.
- Files the included documents mention by name but that are not here (for example `OWNER_RUNBOOK.md`,
  `RUNBOOK_REAL_RUN.md`, `washout_pass_72_ready_to_fill.csv`, `harness/repair_candidate/`, `harness/simulated_run/`,
  `harness/persona_pass/`, `BRIEF.md`) are among the withheld items above.
