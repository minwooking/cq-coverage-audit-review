# Deviations after the freeze (c8328bf), recorded as they happen

1. `run_rater.py` (2026-10-17, before the first scored call of the shared-server runs and after the qwen contrast run had been started with the frozen
   version): added the opt-in `--gate` (courtesy gate that reads the vLLM `/metrics` and sends nothing while another client uses the endpoint).
   Operational only: no request body, prompt, cell, decoding setting or stop rule changes. The qwen run used no gate (<internal-proxy> gateway).
2. `qwen` contrast run: 183 calls were sent; 179 cells have a valid label, 4 cells (B:CQB09, B:CQB12, D:CQB12, E:CQB09) stayed invalid after the
   two permitted retries (reasoning exhausted the 12,288-token budget), 5 cells (B-F CQB32) were not sent (context). No cell was re-sent and nothing
   is imputed (plan 4.1).
3. `analyze_raters.py` (after seeing only the qwen validity counts above, before any kappa was computed): the Experiment 2 primary block now holds the
   family raters only, and the descriptive raters (qwen, S21 luna) go into a second block on the cells every rater labeled. Reason: with the
   frozen code a descriptive rater's invalid cells (qwen: 4) would have shrunk the required cross-family comparisons from 182 to 178 cells. No
   threshold, status rule or statistic definition changed.
4. `analyze_raters.py` (after the first complete analysis, which returned `analyzer failed` for the majority-vote audit only): `--out-dir` is resolved
   to an absolute path, because the unchanged audit is run with a different working directory and could not find a relative label CSV. A
   path-handling bug fix; no number of any other section changed (the first run's other sections are identical to the rerun's).
