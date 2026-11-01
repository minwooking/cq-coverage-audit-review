# Brick holdout harness

This directory contains the executable scaffolding for the pre-registered Brick
holdout. The formal runner sends one request per registered cell to an
OpenAI-compatible `/chat/completions` endpoint (216 primary plus 24 ablated
and 12 preserved controls). It writes raw judge records, but
never invents the human evidence label `A`.

## Frozen guards

`run_holdout.py` verifies, **before the first network request**, all of the
following:

- CQ bank: 36 rows and SHA256 `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`;
- rubric SHA256 `d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf`;
- rendering specification SHA256 `eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e`;
- seed `20260913`.

A mismatch is a hard stop. Before a registered six-variant load, the runner
resolves every manifest `graph_path`/`graph_file` and rendered-view source,
requires both files, and compares their SHA256 values with
`graph_sha256`/`rendered_view_sha256`. A path-shaped `view` is loaded as a file
when used; explicit `rendered_view_path`/`view_path` fields take precedence.
Inline views remain available only for non-registered (`require_six=False`)
fixtures. Every run manifest records the three digests, seed, model, endpoint
**host only**, UTC timestamp, schema-view digest, and `SIMULATED`.
The API key is read only from `HOLDOUT_JUDGE_API_KEY`; it is never accepted as a
CLI argument, written to a manifest, or echoed.

## Eligibility preflight

Before endpoint/model resolution or API-key lookup, the runner performs a deterministic, network-free eligibility preflight over every registered primary cell (all registered views crossed with the 36 frozen CQs). It checks the existing grounding substring matcher, the seeded 24-cell ablation sample, and the 12 preserved-control paraphrases. If any registered source is not computable, it exits nonzero with `REFUSING TO RUN: eligibility preflight failed` and a stable JSON diagnostic containing all missing groundings and control failures; no judge request is made. The diagnostic records matching line numbers and flags local-name-only matches as false positives without changing formal matcher semantics.

## Configuration

For a real run, set all three variables:

```bash
export HOLDOUT_JUDGE_ENDPOINT='https://api.openai.com/v1'
export HOLDOUT_JUDGE_MODEL='gpt-5.4'
export HOLDOUT_JUDGE_API_KEY='paste-the-key-in-your-shell-only'
```

The endpoint and model may also be passed with `--endpoint` and `--model`; the
key has no CLI/file fallback. The formal runner defaults the registered seed
and still refuses any other seed.

## Commands

```bash
# Validate the frozen inputs without calling a judge (no key required):
uv run python harness/run_holdout.py --out <tmp>/holdout-check --dry-run

# Probe only one or two cells; output is always harness/smoke_run/ and is
# always labelled SIMULATED. --force replaces an earlier probe.
make holdout-smoke
# equivalent:
uv run python harness/run_holdout.py --smoke --limit 2

# Formal run (36 requests; never use --force on a different registration):
make holdout-real
# equivalent:
uv run python harness/run_holdout.py --out harness/real_run \
  --answer-key /secure/holdout-answer-key.jsonl

# Analyze a completed primary-pass CSV without mutating cells.jsonl:
uv run python harness/analyze_holdout.py harness/real_run/cells.jsonl \
  --labels annotation/packet/labels_primary_pass.csv \
  --label-source human \
  --seed 20260913 --out harness/real_run/holdout_results.json

# Add the separate washout reassessment for the G2 rater_L1 point estimate:
uv run python harness/analyze_holdout.py harness/real_run/cells.jsonl \
  --labels annotation/packet/labels_primary_pass.csv \
  --labels-washout annotation/packet/labels_washout_reassessment_pass.csv \
  --label-source human \
  --seed 20260913 --out harness/real_run/holdout_results.json
```

The formal runner resumes idempotently from existing `cells.jsonl` records when
rerun with `--force`; already-recorded `cq_id`s are skipped. A failed cell is
still recorded (with `judge_response_parsed: false`) so inspect the JSONL before
retrying; delete only a deliberately failed record if you want to retry it.
Smoke output never writes `real_run/` or `simulated_run/`.

## What a human must still supply

- the endpoint, model, and environment-only key;
- human evidence labels from `../annotation/` (the analysis cannot manufacture
  them);
- the washout re-score (n=72) and any registered external spot checks;
- a deposit DOI once the registration is publicly archived.

`analyze_holdout.py` requires `--seed` and uses the explicit pre-registered
confidence-level option for G1. The existing synthetic test suite is run with:

```bash
uv run pytest harness/test_analyze_holdout.py -q
```

## Domains (Brick, IOF Core)

Domain parameters live in `../domains/<name>.toml` and are loaded by `domains.py`: snapshot path and sha,
namespaces, bank path/sha/rows, output directories, cluster-id prefix. `brick.toml` carries exactly the values
that used to be hard-coded; `test_domain_regression.py` pins the Brick outputs (corpus, B-F rendered views,
`run_holdout --dry-run` cell plan, `analyse()` result) to the pre-parameterisation digests. Offline, no LLM.

- `iof.toml` leaves `bank.sha256`/`bank.rows` unset (bank not frozen): `run_holdout.py --domain iof` and
  `analyze_domain.py --domain iof` refuse to run. Set both only after the bank is frozen and registered.
- IOF corpus: `python build_iof_corpus.py` (rules: `../data/iof_core_202603/CORPUS_RENDERING.md`).
- Variant build for any domain, dry run by default: `variants/build_domain.sh <domain>` (add `--execute` to run;
  needs an LLM endpoint). Packaging: `variants/package_variants.py --domain <name>` (non-Brick needs `--model`, `--endpoint-host`).
- `analyze_domain.py --domain brick ...` forwards to `analyze_holdout.py` unchanged (that file is pinned by SHA-256 in
  committed artifacts and is not edited). `pooled_g1.py` is the unregistered pooled G1 (domain-qualified clusters,
  Clopper-Pearson); disabled by default.

AI-generated tooling: review and test before relying on it.
