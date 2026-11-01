# Human-pass (AH) results — 2026-10-09

Registered analysis of the locked AH labels. Everything here is
**exploratory**: the reference is LLM-assisted (see the lock manifest and
main.tex, tab:deviations D3/D4).

- Labels: locked at commit `f855e62` (`annotation_locked/LOCK_2026-10-09.md`).
- Analyzer: commit `ef62ef8` (`harness/analyze_holdout.py`), committed before this run.
- Run time: 2026-10-09 01:47 KST. Unblinding boundary passed to G7:
  `2026-10-09T00:23:09+09:00` (the lock commit).

## Commands (worktree root, `PYTHONPATH=$PWD/src`, root `.venv` python)

```
L=locked_labels
analyze_holdout.py real_run/cells.jsonl --labels $L/primary_working.csv --label-source human \
  --label-audit $L/primary_working.csv.audit.jsonl --unblind-boundary 2026-10-09T00:23:09+09:00 \
  --drafts $L/draft_224.csv --seed 20260913 \
  --out .../holdout_results_human.json --out-cells .../SEALED_until_washout/per_cell.json
# sensitivity: same + --bca-ties strict  -> sensitivity_bca_strict.json
# corrected LLM-auxiliary values (D2): --labels real_run/llm_auxiliary_as_labels.csv -> llm_aux_corrected.json
```

`judge_only_J.json` (judge J only, no labels, same bootstrap helper) comes from
`judge_only_J.py`, which imports the analyzer's `cluster_bootstrap_stat` /
`cluster_bootstrap_delta` (B=10,000, seed 20260913, mid-rank z0):
`python judge_only_J.py paper/access2026/harness paper/access2026/harness/real_run/cells.jsonl`.

## Files

Current files (rater-safe copies rebuilt 2026-10-09 from the re-run with the
hardened analyzer `0dbe6e9`; numbers identical to the first run):

| file | sha256 | visible to the rater |
|---|---|---|
| `holdout_results_human.rater_safe.json` | `7508498e2114bf1f35aa95170a9487671fc7c26cd0cb380b4eb1ce676af57411` | yes |
| `sensitivity_bca_strict.rater_safe.json` | `9617622eacfe89cc3728fc7141d7ca6f2503cfbbfdc2b533f2a96bfe73635885` | yes |
| `judge_only_J.json` | `5aa9773d4fea757ef0450b1d83994a1e438bf730e15d1bf93c3da757fc431666` | yes |
| `llm_aux_corrected.json` | `aec993604aeb5669f9a31ade8df6d23492f75a8efdd5a50136bcd55c2feb0dfc` | yes |
| `SEALED_until_washout/holdout_results_human.rerun_0dbe6e9.json` | `ee2650c7cfa1e7655305def2c7437ee9972cf7f7e5813460b4c81c4a84d7da49` | **no** |
| `SEALED_until_washout/sensitivity_bca_strict.rerun_0dbe6e9.json` | `33f511ed6a5d8eb5013591492039ebd2d8f6b66789a99c515c52b090c47dd366` | **no** |
| `SEALED_until_washout/per_cell.rerun_0dbe6e9.json` | `5aebf70b6af9b4468f3c066ba84215699316ae5342d33b5c61d6cb4bd90a9248` | **no** |

First run (analyzer `ef62ef8`, 01:47 KST), kept sealed as the original record:

| file | sha256 |
|---|---|
| `SEALED_until_washout/holdout_results_human.json` | `bcb4cbb4f59a1831139f1de7af7fad89ebfeea3a43955b02babc895b11b6a379` |
| `SEALED_until_washout/sensitivity_bca_strict.json` | `a3f8b3aa863153d2763763862aa50027d4f73d3cef38e18ce94ff6f869ac54a8` |
| `SEALED_until_washout/per_cell.json` | `ec63237c5c00d9f009c2314de60240dddd7c8949bd0fe9853e64974382cd0de0` |

The rater-safe copies committed in `b66f532` still listed the mean rater_L1
per order quintile (see the seal note at the end); the current copies drop it.
`judge_only_J.json` now also carries the strict-tie interval of the judge-only
A→B contrast, the lattice step (1/23), and judge-only coverage of every variant
on A's 23-CQ set (PREREG L801–803 comparability); its earlier keys are unchanged.

## Seal

The `SEALED_until_washout/` files are untracked; read-only copies are in
`locked_labels/sealed_results_until_washout/`. They hold the
per-cell judge/rater values and the judge-versus-rater L1 agreement
(G4 QWK, G5 MAE, the J × rater_L1 confusion counts). Those are withheld from
the rater until the washout relabel (G2) is complete, because seeing them
could shift the rater's scale use in the washout. The rater-safe copies are
the full results with only those two gates and the gate summary replaced by
a pointer to the sealed file and its hash.

## Re-run check after hardening (2026-10-09 ~02:30 KST)

The analyzer was hardened afterwards (invalid-score guard, output-path guard,
G7 total-dwell basis and CSV-vs-audit check, AH provenance label). Re-running
all three analyses with it changed no number: the only differences are the
analyzer hash, `label_source` → "human-adjudicated AI draft (AH)", a
`label_provenance` block, and new G7 fields (`n_csv_audit_mismatch` = 0,
`n_under_20s_last_save_basis` = 171, same as the total-dwell count).

Note on the seal (historical): the rater-safe copies committed in `b66f532` listed
the mean rater_L1 per order quintile under `descriptive.order_drift`. Together with
`judge_only_J.json` that revealed the sign of mean(J − rater_L1), though not G4/G5
themselves. Commit `9189ccf` removed the field; the files in this directory no longer
contain it. Whether the earlier copies were opened is not recorded.

## Older manuscript counts

`legacy_counts.py` reads only the judge run (`cells.jsonl`) and the LLM
auxiliary labels (`llm_auxiliary_labels.jsonl`). No AH label is read, and no
cell or CQ id is written. It reproduces the counts the manuscript quotes from
earlier passes, both for all 224 cells and for the 188 primary cells: control
mean J, A_aux splits, empty spans, and the empty-span ⇔ J=0 check.
Output: `legacy_counts.json`, sha256 `3bf618b86f2531faa4d70b174b29085815549d624c934715ed38808bfb88587d`.

## Dwell clock-skew check

G7's dwell, `elapsed_s`, is the server's save clock minus a page-load stamp that the rater's
browser took, so a skewed client clock would shift it. `dwell_skew_check.py` estimates that
offset from the locked audit sidecar and session log (timestamps, `elapsed_s` and the
`cell_id` prefix only), records their sha256, and writes aggregates only (no cell id, label,
note or span) to `dwell_skew_check.json`. `harness/test_dwell_skew_check.py` checks it on
synthetic data, including an injected client-clock lead.

```
python paper/access2026/harness/real_run/results_human_pass/dwell_skew_check.py \
    locked_labels/primary_working.csv.audit.jsonl \
    locked_labels/primary_working.csv.session_log.txt
```

Output: `dwell_skew_check.json`, sha256 `db30c2b994b6127430e10726cf8f7ae415084d1a32c5ff9bec687a91f3d0f94e`.
Result: the client clock was not ahead of the server (lead at most 0.07 s; skew plus page-load latency 0.14 s in S6 and 0.23 s in S7), and on server-only inter-save intervals 171 of 187 primary cells are still under 20 s (median 9.0 to 9.4 s, no cell crosses 20 s), so G7 fails regardless of skew; a uniform 13.2 s client lead would be needed to pass.

## Unsealed (2026-10-09, PREREG §14)

The washout (G2) and the second annotation were not conducted. The author
decided this at 13:45:36 KST, while the sealed values were still unseen
(PREREG §14, D22/D23, committed in `9984f3c`). The seal existed only to
protect the washout, so it is lifted.

`unsealed_2026-10-09/` holds byte-identical copies of the six files in
`SEALED_until_washout/`; see `unsealed_2026-10-09/SHA256SUMS.txt`, whose
values match the hashes listed above. Nothing was recomputed. The rerun files
(`*.rerun_0dbe6e9.json`) are the ones the manuscript cites.

- G4: QWK(J, rater_L1) 0.500 [0.345, 0.642]. Not falsified (the registered
  rule fails G4 only if the CI upper bound is below 0.60).
- G5: MAE(J, rater_L1) 0.793 [0.644, 0.947]. Fails (registered rule: the
  upper bound must be at most 0.50).

The persona results (§12.5) remain unopened and unreported.

## Exploratory re-analysis (post-hoc, reviewer request)

**Exploratory and post-hoc.** Not registered. It adds no human label and makes no LLM
call; it re-slices labels that already exist. The AH labels are an LLM-assisted
adjudication and not a reference standard, so every rate describes agreement between
two label sources and is named by what is counted ("agreement among A=1 cells",
"over-credit among judge-credited cells"). Intervals are marginal 95% BCa intervals,
uncorrected for the number of quantities; no p-value is computed.

Command (worktree root, `PYTHONPATH=$PWD/src`, root `.venv` python; about 1.5 minutes):

```
python paper/access2026/harness/real_run/results_human_pass/exploratory_reanalysis.py \
    --drafts locked_labels/draft_224.csv
```

Defaults: `--per-cell unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json`,
`--cells ../cells.jsonl`, `--aux ../llm_auxiliary_labels.jsonl`,
`--out exploratory_reanalysis.json`. Resampling is the analyzer's own
`cluster_bootstrap_stat` (imported, not modified): CQ clusters, B = 10,000, seed 20260913,
mid-rank z0. A re-run is byte-identical (checked with one BLAS thread and with many).
The script refuses any path containing `persona_pass`, any output under the labels
directory, and an output that is also an input. It writes aggregates only: no cell, CQ or
cluster id, and no span or note (the draft file's note and span columns are never read).

| file | sha256 |
|---|---|
| `exploratory_reanalysis.json` | `1adcc697d6093e4e9026d5d2f6ea0b74a92c5e42618af38b912f919fda445c27` |
| `exploratory_reanalysis.py` | `e337ba482cbfeccf8a5b053cf708baba6747467b9907814f7bbc427741b7db75` |
| `../../analyze_holdout.py` (imported, unchanged) | `3278d71c70829889838aa8f61c4f5b0217b9ef3e921976a8ea5fc0c0fd122e10` |

Inputs (recorded in the JSON under `inputs`):

| file | sha256 | read for |
|---|---|---|
| `unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json` | `5aebf70b6af9b4468f3c066ba84215699316ae5342d33b5c61d6cb4bd90a9248` | J, A (AH), L1* of the 188 primary cells |
| `../cells.jsonl` | `bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af` | judge run: J and ids only (the placeholder A is never read) |
| `draft_224.csv` (locked) | `9489552d7c269b542553c36e78c8220b4c2800739c3b5d8074761df481e92abd` | A_draft, the AI draft of A before author revision |
| `../llm_auxiliary_labels.jsonl` | `5952874272327b85d253c7686c1faebd4b9b13f11f9ea58b1fe81b5fe9980d63` | GPT-5.6 auxiliary A labels |

What the JSON holds: (1) the 2x2 table of 1[J>=2] against A with raw agreement, Cohen's
kappa and conditional agreement rates; (2) pi-hat as registered, over-credit among
judge-credited cells, under-credit rates and a two-sided disagreement rate; (3) the same
table, pi-hat and the variant A to B L1* contrast under A_draft, AH and the auxiliary
labels, agreement between the three sources (kappa, 1 to 0 and 0 to 1 counts) and the
paired differences between them; (4) rater-error tipping points on the AH labels; (5) the
G1 design fact (one-sided 97.5% Clopper-Pearson bound for zero events among 33 clusters).
The AH values of pi-hat and of the A to B contrast reproduce `holdout_results_human.rerun_0dbe6e9.json`
exactly (checked).

Reading notes:

- Tipping points flip single A labels on J>=2 cells (cells with J<=1 cannot move pi-hat or
  L1*). The search is exhaustive over flip sets of each size while the number of sets stays
  within a budget; a greedy adversary is used beyond it, and each record states whether its
  minimum is exact or only a witness. The bootstrap replay inside the search draws the same
  cluster indices as the analyzer and is checked against it at the baseline and at every
  reported witness.
- A zero-event state is scored with the cluster-level Clopper-Pearson bound, as the analyzer
  does, so the registered G1 gate cannot be crossed by flips at 33 clusters.
- J=0 coincides with an empty judge span in every cell (`legacy_counts.json`), and L1*
  never rises with A, so "under-credit" is a statement about disagreement with the AH label,
  not about a span the judge cited.
- The `model` column of `draft_224.csv` reads `agent-draft(Sisyphus-Junior-deep)` on all
  224 rows; the script assumes no model identity for the drafts.

Tests (synthetic fixtures; the full harness suite also needs `--ignore` for the persona
directories, which this analysis never opens):

```
PYTHONPATH=$PWD/src python -m pytest paper/access2026/harness/test_exploratory_reanalysis.py -q
```
