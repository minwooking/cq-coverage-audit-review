# Deviations from PLAN.md (amendment C)
1. **Gateway judge not run.** The 1-call probe of `gpt-5.6-luna` through the local gateway returned HTTP 402 (Payment Required), not 200; per PLAN C.3 it is skipped. The ladder therefore has four judges (glm, gptoss, q38, q80); the independent set for the panel summary is glm, gptoss, q38.
2. **Prompt-file name only.** Jobs were assembled by `prepare_cde.py` (a generalisation of Study 5's `prepare_f.py` to a variant letter); the scorer is Study 5's `score_panel.py`, unchanged.
