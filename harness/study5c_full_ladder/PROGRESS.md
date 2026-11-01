# PROGRESS (amendment C) -- times UTC
- 10:50 plan committed (0b89bd8). Hash/log check: C, D, E graphs come from the same build run as F (all six steps OK in one log per domain); sha256 of each graph is in the variant MANIFEST (local).
- 10:55 `prepare_cde.py`: eligible cells (strict rule on each variant's full rendering) dcat 27/27/27, ssn 41/41/41, prov 36/36/37 for C/D/E (prov C, D: CQP38 eligible but no question-matched subgraph) = 313 cells, 939 calls per judge.
- 10:55 gpt-5.6-luna probe: HTTP 402, skipped. Tunnels opened (request-only); glm, gptoss, q38, q80 scoring started, 3 workers each.
- 11:28 scoring done (glm, gptoss, q38, q80: 939 calls each, 1 invalid for gptoss, none imputed); tunnels closed. 11:45 analysis (results.json, REPORT_auto.md, tables.tex) written and committed.
