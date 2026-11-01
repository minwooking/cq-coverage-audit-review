# PREREG addendum 36, amendment B (exploratory, post hoc) -- a one-vendor size ladder of judges on the Study 5 cells

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-20. Post hoc: written after addendum 36 and with knowledge of its first judge results. This file is committed alone, before any model call of this amendment (only read-only checks were made: Hugging Face model pages, `nvidia-smi`, `a container listing`, a directory listing of the weight cache). `main.tex`, `main_ko.tex`, `supplement.tex` and the folder `study5_judge_panel/` are not touched (code is imported or copied, never edited there). All code named here is AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system. Before this file or any output is shared outside the team, check that no confidential company information, host name, address, port, key or personal data is in it.

## B.1 Request and what exists

Request: add Qwen3.8-27B, Qwen3.8-8B and Qwen3.8-4B as judges on the same cells as Study 5, same prompt, rubric and views, 3 repeats at temperature 0, so the panel covers one model family across sizes.

Checked on huggingface.co on 2026-10-20: `Qwen/Qwen3.8-27B` exists (dense, 27B, Apache 2.0; also `Qwen/Qwen3.8-27B-FP8`). `Qwen/Qwen3.8-8B` and `Qwen/Qwen3.8-4B` return "page does not exist". Independent sources (model-lineup articles, Ollama library listing, the Qwen organisation page) agree that the Qwen3.8 line has only: 27B dense, Flash-Next (about 180B MoE) and 2.4T-A95B; there is no Qwen3.8 below 27B, so **no "nearest Qwen3.8 size" exists for 8B or 4B**. Deviation, decided by this file before any call: the two small judges are taken from the generation whose architecture Qwen3.8 is built on ("Built on the architectural foundation of Qwen3.5", model card of Qwen3.8-27B), at the sizes nearest to the request:

| id | model (exact HF id) | note |
|---|---|---|
| `q38_27b` | `Qwen/Qwen3.8-27B` | as requested |
| `q35_9b` | `Qwen/Qwen3.5-9B` | stands in for "8B": Qwen3.5 has no 8B; 9B is the nearest size in the Qwen3.5 line (Qwen3.8 has none) |
| `q35_4b` | `Qwen/Qwen3.5-4B` | stands in for "4B" (same size, earlier generation) |

Not used, recorded for the author: `Qwen/Qwen3-8B` and `Qwen/Qwen3-4B` have the exact sizes but are an older, different architecture (the extractor's generation, Qwen3-Next being a Qwen3-lineage model). The author may ask for them as a further amendment.

## B.2 Family labelling and the pre-fixed rule

All three are the extractor's vendor but not its model: Qwen3.8-27B is the same generation as `q38` (Flash-Next); Qwen3.5-9B/4B are an earlier generation than Qwen3.8 and a later one than Qwen3. Labelled **"same vendor, different generation"**. The pre-fixed interpretation rule of addendum 36 (set of independent judges `glm`, `gptoss`, `q38`, `gw`; `q80` excluded) is **unchanged**; the three new judges do **not** enter its count (`q38` was counted by the brief; adding three more same-vendor judges to a pre-fixed count after seeing data would change the rule). They get their own labelled count ("vendor-ladder judges") beside it.

## B.3 Cells, scorer, analysis (all unchanged)

* Cells: `study5_judge_panel/cells_ab.json`, `jobs_ab.jsonl` (372 A/B cells) and `jobs_f.jsonl` (105 F cells); prompts byte-identical, stored `prompt_sha256` verified by the scorer. 3 repeats, temperature 0, `json_object`, max_tokens 1024 and two retries at 4096, thinking switched off (`chat_template_kwargs.enable_thinking=false`, the same switch as `q38`/GLM), nothing imputed. Scorer = Study 5 `score_panel.py` / addendum 26 `score_judges.py`, imported, with the three judge entries added in this folder.
* Analysis: same code path as addendum 36 (`study5_judge_panel/analyze.py` functions): per-cluster paired difference, question-clustered BCa (seed 20260913, B = 10,000), 95% resolved, 90% inside +-0.50 equivalent, else unresolved; fewer than 10 clusters = underpowered. Scopes: four Brick banks, Brick pool, DCAT, SOSA/SSN, PROV, three-domain pool, F contrasts (A->F, B->F per domain and pooled). Plus pairwise quadratic-weighted kappa against `glm`, `gptoss`, `q38`, `q80`, `gw` and among the three new judges, on shared cells (per-cell median-low of repeats). No threshold, margin, seed or rule is changed after any score is seen. Results are reported whatever they show.

## B.4 Serving (request-only elsewhere)

Read-only survey, 2026-10-20: a shared server both GPUs 99% used (no room); <internal-host> GPUs have 3.8 / 21 / 12 / 5.8 GB free, none below 2 GB used (rule not met, not used); <internal-host> GPU 0 shows 0 MiB used, GPUs 1-4 are full. **Plan: <internal-host> GPU 0 only, one vLLM container at a time** (96 GB: 27B bf16 first; then 9B and 4B together), image `<image>` (already present, the tag the Flash-Next container runs on), container names `study5b-qwen38-27b`, `study5b-qwen35-9b`, `study5b-qwen35-4b`, bound to <loopback>, API key from a local file outside the repository, weights from the existing HF cache (27B, 52 GB, already present; 9B and 4B downloaded to the same cache if absent). Single launch attempt per container; a driver/library failure is reported and that model skipped, not retried in a loop. Only containers started here are stopped and removed at the end; weights stay. The exact launch commands (without key, host or port) are appended to `PROGRESS.md` before the first scoring call. Workers <= 3 (probe-based), halved on error bursts; resumable JSONL under `raw/`.

## B.5 Order of work and commits

1. This file, committed alone. 2. Code (scorer wrapper, job assembly reuse, `analyze.py`, tests) committed before results. 3. Raw records, `results.json`, `REPORT_auto.md`, `tables.tex` committed last; `PROGRESS.md` with ETA per model. Deviations to `DEVIATIONS.md`. Only explicit paths are staged; `index.lock` is retried. No host, port or key in a committed file.
