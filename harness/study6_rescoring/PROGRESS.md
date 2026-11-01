# PROGRESS (addendum 37), UTC
- 2026-10-20 plan committed (581b453); code and frozen jobs committed.
- 15:26 sub-study A started on glm, gptoss, qwen35 (3 workers each). luna gateway probe: HTTP 402 -> skipped. q38: no key in session -> skipped.
- 16:38 A done for gptoss, qwen35; glm A at 75%. L (limited view, 188 cells) started for gptoss; glm L to follow. Machine memory is critically low from other processes; background waiters were reaped by the harness and not restarted.
- 16:50 A complete (glm 63 invalid calls, gptoss 12, qwen35 38 + 96 context_skip cells). STATUS A: all three judges read hint-independent (A->B resolved positive without hint).
- 16:52 L (limited view, 188 cells x 3) complete for gptoss (0 invalid) and glm (2 invalid). Tunnels closed. analyze.py run; results.json, REPORT_auto.md, tables.tex written. Deviations: none after freeze. Note: the plan's 37.2 table lists qwen35 max_model_len 32,768; 96 of 288 qwen35 dev cells (all variants incl. large summaries) were context_skip.
