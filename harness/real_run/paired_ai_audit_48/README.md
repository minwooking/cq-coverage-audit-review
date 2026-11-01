# Paired 48-cell AI audit: lineage and execution runbook

Status: **EXPLORATORY, POST HOC.** This directory is the output root of a paired audit in which
two AI judges of distinct model families score the same 48 registered cells independently.
It holds no measured result yet. Phase A (tooling, this file) is complete when the code and tests
are committed; Phases B and C are human-gated and are never run automatically.

Design source: `docs/superpowers/specs/2026-10-09-paired-48-cell-audit.md`.
Plan source: `docs/superpowers/plans/2026-10-09-paired-48-cell-audit.md`.

## 1. Lineage

- **Cell selection.** The 48 cell IDs come from
  `paper/access2026/harness/real_run/second_annotator/cell_list_48.txt`
  (sha256 `bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e`,
  composition A3 / B9 / C13 / D7 / E10 / F6). The list was frozen with PREREG addendum 12.
  It is reused here **only as a pre-frozen cell-ID selection** for a new AI-audit lineage.
- **48 unique cell IDs, not 48 unique CQs.** CQ IDs repeat across variants; the list covers 28
  distinct CQ clusters. All intervals therefore resample CQ clusters, not cells.
- **The human second annotation was not conducted** (PREREG addendum 14, D23). This audit
  neither performs it nor substitutes for it. The registered packet sheet and the section 12.4
  human procedure are not used. `packet/MANIFEST.json` and `packet/SHA256SUMS.txt` stay untouched.
- **New lineage, fresh scoring.** Every cell is scored anew by both judges against the frozen
  224-cell plan (digests verified before any filtering). The 5-cell pilot in
  `paper/access2026/harness/real_run/second_judge/` stays exploratory and unreported;
  never point `--out` at that directory.
- **Frozen inputs.** `PREREG.md`, `BRIEF.md`, `harness/real_run/cells.jsonl`, `rubric/`, `bank/`
  and the sealed artifacts are not modified by any step below.

## 2. Claim rules

- The only permitted statement is: two AI judges of distinct families **agree or disagree** on
  these 48 registered cells, with the stated intervals.
- It is not a human validation and not a reference standard for the J scores, not a non-author
  annotation, not a G6 evaluation. The registered G1, G5 and G7 gate failures stand unchanged.
- Agreement between two AI judges is not correctness: it depends on the J skew of the sample and
  on the shared rubric (the analyzer prints this as `agreement.interpretation_note`).
- Forbidden framing in any text derived from this audit: "human validation", "human-validated",
  "ground truth", "gold standard", "reference standard", "expert agreement", "author-verified".
  The analyzer scans its own output against this list (`BANNED_CLAIM_TERMS`).
- Flow is run -> `BRIEF.md` -> `main.tex` (BRIEF rules 1, 2, 4). No invented numbers, unmeasured
  stays TBD. A sentence about this audit reaches the manuscript only through `BRIEF.md` and
  human review.

## 3. Secrets and provenance

- The API key is read from the environment variable `HOLDOUT_JUDGE_API_KEY` only and is never
  logged or written. Outputs in this directory must contain no key, no host names, no personal
  data. Check before any external distribution.
- Model supply goes through the <internal-proxy> proxy only. Both tools refuse any other endpoint.
- The preflight has no model default. The runner's `--model` does default to the pilot model and
  `--out` to the pilot directory, so in this audit every runner command, `--estimate` included,
  passes `--model` and `--out` explicitly. The placeholders `<MODEL_A_ID>`, `<MODEL_B_ID>` and
  `<TOKENS>` below are human-gate inputs, never executable defaults.

## 4. Phase B runbook (gated, human-run)

Commands are AI-generated drafts: review and test them before use, and do not run them without
the approvals in step 2. The preflight and the scoring runs need `HOLDOUT_JUDGE_API_KEY` set in
the environment of the human operator; never put a key value in a command, file or log. For the
worktree and `.venv` caveat on the `PYTHONPATH` lines, see the environment note under Phase C
step 1.

1. **Preflight (live availability, provenance, family check, token estimate).** This is a live
   call, run by a human: per model it sends two small probe completions (a plain one and one in
   the registered request form) and reads `/v1/models`, so it spends a small number of tokens.

   ```bash
   PYTHONPATH=$PWD/src .venv/bin/python paper/access2026/harness/paired_ai_audit_preflight.py \
     --cell-list paper/access2026/harness/real_run/second_annotator/cell_list_48.txt \
     --cell-list-sha256 bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e \
     --model-a <MODEL_A_ID> --family-a <FAMILY_A> \
     --model-b <MODEL_B_ID> --family-b <FAMILY_B> \
     [--quota-note "<operator-pasted quota line>"]
   ```

   Writes `paired_preflight.json` here (default `--out`). Exit 0 only when `verdict` is `ready`;
   otherwise `verdict` is `blocked:<reason>` and exit is 1. It blocks on: list sha or composition
   differing from the registered 48, same family for A and B, a model absent from `/v1/models`,
   a reported ID that differs from the requested one, or a failed probe.
2. **Human approval.** A human reads `models[]`, `families_distinct` and
   `estimates.two_model_total_prompt_tokens_conservative` in `paired_preflight.json`, then approves
   both model IDs, both families and a per-invocation token budget. The estimate comes from the
   runner's `--estimate` machinery; no number is stored in this README. Quota windows can be
   smaller than the total, so plan several invocations.
3. **Optional offline estimate** (no network). Pass the same `--model` and `--out` as the
   scoring run, otherwise the runner reads the pilot directory's state:

   ```bash
   PYTHONPATH=$PWD/src .venv/bin/python paper/access2026/harness/run_second_judge.py \
     --cell-list paper/access2026/harness/real_run/second_annotator/cell_list_48.txt \
     --cell-list-sha256 bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e \
     --model <MODEL_A_ID> \
     --out paper/access2026/harness/real_run/paired_ai_audit_48/<slug-a> \
     --estimate
   ```

   `<slug-a>` is `slugify(<MODEL_A_ID>)` as in step 4. `--estimate` returns before the output
   directory is created and writes no file; it only reads `cells.jsonl` and `failures.jsonl` in
   `--out` if they exist, so on a new directory `already_done` is 0. The output includes
   `selection.selected_cells` (expected 48).
4. **Scoring, once per model**, each into its own directory under this root:

   ```bash
   PYTHONPATH=$PWD/src .venv/bin/python paper/access2026/harness/run_second_judge.py \
     --cell-list paper/access2026/harness/real_run/second_annotator/cell_list_48.txt \
     --cell-list-sha256 bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e \
     --model <MODEL_A_ID or MODEL_B_ID> \
     --out paper/access2026/harness/real_run/paired_ai_audit_48/<slug> \
     --token-budget <TOKENS> --workers 3
   ```

   `<slug>` is the runner's `slugify(model)`; the preflight prints the exact resume-ready command
   pair with `<TOKENS>` left open. `--workers` is capped at 3.
5. **Stop and resume semantics.**
   - A real run requires `--token-budget`; the invocation stops cleanly when the budget is spent
     and records `last_stop_reason` and `cells_remaining` in `run_manifest.json`.
   - Error handling follows the runner's `classify_error`. An HTTP 429 whose body contains a
     quota or usage-limit marker (`QUOTA_MARKERS`) stops the whole run at once, with no retry and
     no waiting. A 429 without such a marker is a plain rate error: the call is retried up to 3
     times with backoff, and if it still fails the cell counts as failed and stays pending. Three
     consecutive failed cells trip the breaker.
   - Resuming means running the command again; every re-run is a new paid invocation. After a
     budget or `quota_exhausted` stop, a human first checks the provider's quota window and
     approves a fresh `--token-budget` for that call, and only then runs it. Never re-run from a
     script, cron job or loop.
   - Cells already in `cells.jsonl` are not scored again. Failed attempts are in `failures.jsonl`.
   - One output directory holds one selection and one model. Resuming with a different list
     sha256, a record outside the list, or a different model is refused. `--cell-list` without
     `--cell-list-sha256` is refused, and a wrong sha256 is refused before any HTTP call.
   - Both directories must reach 48 of 48 cells before Phase C.

## 5. Phase C checklist (gated, human-reviewed)

1. Run the analyzer on the two completed directories (offline):

   ```bash
   PYTHONPATH=$PWD/paper/access2026/harness:$PWD/src .venv/bin/python \
     paper/access2026/harness/analyze_paired_ai_audit.py \
     --model-a-dir paper/access2026/harness/real_run/paired_ai_audit_48/<slug-a> \
     --model-b-dir paper/access2026/harness/real_run/paired_ai_audit_48/<slug-b> \
     --out paper/access2026/harness/real_run/paired_ai_audit_48/paired_analysis.json
   ```

   Defaults: `--resamples` 10000 and the registered seed. The analyzer refuses on a digest
   mismatch against the frozen plan, on the same `model_requested` in both directories, on J
   outside 0..3, and on any path containing a locked-label or persona-pass component. It also
   refuses an `--out` that resolves to one of the four input files (both `cells.jsonl` and both
   `run_manifest.json`) or to a fixed provenance file (the registered cell list
   `cell_list_48.txt`, `analyze_holdout.py`, or the analyzer itself).

   Environment: a git worktree may have no `.venv`. Use the `.venv` of the repository-root
   checkout and set `PYTHONPATH` so that the `src` and harness of the current checkout come first;
   otherwise the root checkout's code is imported silently. Do not write absolute paths or user
   names into commands or outputs.
2. Read `paired_analysis.json`:
   - `completeness`: `n_list`, `a_scored`, `b_scored`, `paired`, `missing_in_a`, `missing_in_b`,
     `missing_in_both`, `clusters_paired`. `missing_in_a` lists cells scored by B but not A,
     `missing_in_b` the reverse, `missing_in_both` registered cells scored by neither. Missing
     cells are excluded and named, never imputed.
   - `agreement.status`: `computed` (all 48 paired), `computed_on_partial_data` (some missing;
     missing cells may be non-random), or `not_computable` (fewer than 2 paired cells or
     2 clusters; `agreement.reason` names the counts).
   - Metrics, each with `estimate`, `n_cells`, `n_clusters`, and a CQ-cluster BCa interval
     (`ci_lo`, `ci_hi`, `ci_method`): `exact_agreement`, `qwk_ja_jb`, `binary_kappa_j_ge_2`,
     `mean_signed_diff_b_minus_a`, `mean_abs_diff`. `ci_method` is present only when an interval
     was computed. Also `confusion_counts` (rows J of A, columns J of B), `j_marginals` per model
     (`counts_j0_to_j3`, `share_j_ge_2`) and `interpretation_note`.
   - **Per-metric fields, each with one meaning.**
     - `partial_note`: present when the data are partial (`computed_on_partial_data`); it says the
       cluster count fell and missing cells may be non-random. It appears even when the interval
       is computed. It never explains a withheld interval.
     - `ci_reason`: present only when the interval is withheld (`ci_lo`, `ci_hi` null). The two
       causes are fewer than 10 CQ clusters (a choice of the analyzer, not registered) and more
       than 1% degenerate bootstrap resamples.
     - `status: undefined_degenerate_margin` with `reason`: a judge-pair margin has a single
       level (QWK, kappa), so `estimate`, `ci_lo`, `ci_hi` are null and no interval is attempted.
     - `degenerate_share` (QWK, kappa, on the interval path): share of bootstrap resamples with a
       single-level margin. `degenerate_jackknife_n` (same metrics): number of leave-one-cluster-out
       subsets with a single-level margin; the convention value 1.0 enters the BCa acceleration.
       `tie_share`: tie share of the bootstrap, reported on the interval path for every metric.
     - `note`: may appear on any metric; several notes are joined with "; ". Content: fewer than 5
       paired cells outside the modal level (low variance); at most 1% degenerate resamples kept
       in the interval under the convention value; degenerate jackknife subsets; `tie_share` of
       0.95 or more (near-zero resampling variance, not evidence of certainty); for
       `binary_kappa_j_ge_2`, a supplementary-metric caution that coverage under skewed prevalence
       is "not simulated here".
   - **Reading rule.** A metric that carries `note`, `partial_note`, `ci_reason` or
     `status: undefined_degenerate_margin` is cited descriptively only, never as a precise or
     confirmed value. Agreement between two AI judges is not verification by humans.
   - `status` must keep all disclaimer marks (`DISCLAIMER_MARKS`); `claim_guard` must show both flags true;
     `settings.registered_scheme` is false by design.
3. Add an exploratory `PAIRED AI AUDIT` section to `BRIEF.md` with source-keyed values. Only after
   that, and only with human-approved wording, touch `main.tex`. The existing statements that a
   second-family judge was not run stay true until then.
4. Re-sync the Korean mirror and PDFs, and rerun the release builder scan, if the release set
   changes.

## 6. Output files in this directory

| Path | Written by |
|---|---|
| `paired_preflight.json` | preflight (Phase B step 1) |
| `<slug-a>/cells.jsonl`, `<slug-a>/run_manifest.json` | runner, judge A |
| `<slug-b>/cells.jsonl`, `<slug-b>/run_manifest.json` | runner, judge B |
| `paired_analysis.json` | analyzer (Phase C) |

None of these exist until Phase B runs. Review each file for secrets, host names and personal
data before it leaves the repository.
