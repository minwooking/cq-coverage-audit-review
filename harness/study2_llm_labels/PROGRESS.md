# Study 2 (addendum 32) -- progress (one line per checkpoint; ETA included). LLM-labeled; not human-validated beyond Stage 1.

[study2] 2026-10-19T00:47:30Z plan committed (678d938), code committed (f1fe1bf); tokenizer preflight: max prompt 29.7k tokens (glm) / 29.2k (gptoss), 0 of 212 cells over the window; view term coverage (manifest summary): view holds expected-answer terms in 57/188 cells, full rendering in 60/188, addendum-30 subgraph view in 21/188; launching Stage 1 labeling: glm 16 workers, gptoss 24, qwen 24 (token budget 150M, wall cap 8h)
[study2 stage1] 2026-10-19T00:47:30.246241+00:00 model=qwen start: 212 cells / 5300 calls pending, workers=24
[study2 stage1] 2026-10-19T00:47:30.248115+00:00 model=glm start: 212 cells / 5300 calls pending, workers=16
[study2 stage1] 2026-10-19T00:47:30.255503+00:00 model=gptoss start: 212 cells / 5300 calls pending, workers=24
[study2 stage1] 2026-10-19T00:49:12.838802+00:00 model=qwen FINAL calls 7/5300 parse_ok=0.0% rate=4/min ETA=21.5h workers=24 cells_done[stage1:0/212] stop=5 consecutive failed calls
[study2] 2026-10-19T00:50:48Z qwen route DOWN: the local <internal-proxy> gateway returns HTTP 502 'unknown certificate verification error' on every call (7 calls, 5-consecutive-failure stop rule fired), and the shared server does not answer SSH (banner timeout); nothing was touched on that host. Qwen (secondary) is recorded as down; Stage 1 continues with glm and gptoss. glm ~77 calls/min (ETA ~1.1h), gptoss ~150 calls/min (ETA ~0.6h) at 16/24 workers
[study2 stage1 25%] 2026-10-19T00:53:59.383894+00:00 model=gptoss calls 1325/5300 parse_ok=100.0% rate=204/min ETA=0.3h workers=24 cells_done[stage1:41/212] stop=-
[study2 stage1 25%] 2026-10-19T00:57:26.488091+00:00 model=glm calls 1325/5300 parse_ok=99.9% rate=133/min ETA=0.5h workers=16 cells_done[stage1:46/212] stop=-
[study2 stage1 50%] 2026-10-19T01:01:31.788939+00:00 model=gptoss calls 2650/5300 parse_ok=100.0% rate=180/min ETA=0.2h workers=24 cells_done[stage1:95/212] stop=-
[study2 stage1] 2026-10-19T01:02:30.253641+00:00 model=glm calls 1911/5300 parse_ok=99.9% rate=125/min ETA=0.5h workers=16 cells_done[stage1:70/212] stop=-
[study2 stage1] 2026-10-19T01:02:30.261941+00:00 model=gptoss calls 2884/5300 parse_ok=100.0% rate=184/min ETA=0.2h workers=24 cells_done[stage1:102/212] stop=-
[study2 stage1 75%] 2026-10-19T01:07:32.586470+00:00 model=gptoss calls 3975/5300 parse_ok=100.0% rate=208/min ETA=0.1h workers=24 cells_done[stage1:148/212] stop=-
[study2 stage1 50%] 2026-10-19T01:07:42.342045+00:00 model=glm calls 2650/5300 parse_ok=100.0% rate=129/min ETA=0.3h workers=16 cells_done[stage1:99/212] stop=-
[study2 stage1 100%] 2026-10-19T01:14:41.562229+00:00 model=gptoss calls 5300/5300 parse_ok=100.0% rate=198/min ETA=0.0h workers=24 cells_done[stage1:211/212] stop=-
[study2 stage1] 2026-10-19T01:14:41.563249+00:00 model=gptoss FINAL calls 5300/5300 parse_ok=100.0% rate=198/min ETA=0.0h workers=24 cells_done[stage1:212/212] stop=-
[study2 stage1 75%] 2026-10-19T01:15:30.877041+00:00 model=glm calls 3975/5300 parse_ok=99.9% rate=174/min ETA=0.1h workers=16 cells_done[stage1:150/212] stop=-
[study2 stage1] 2026-10-19T01:17:30.254619+00:00 model=glm calls 4650/5300 parse_ok=99.9% rate=204/min ETA=0.1h workers=16 cells_done[stage1:179/212] stop=-
[study2 stage1 100%] 2026-10-19T01:20:30.657748+00:00 model=glm calls 5300/5300 parse_ok=99.9% rate=221/min ETA=0.0h workers=16 cells_done[stage1:211/212] stop=-
[study2 stage1] 2026-10-19T01:20:30.659377+00:00 model=glm FINAL calls 5300/5300 parse_ok=99.9% rate=221/min ETA=0.0h workers=16 cells_done[stage1:212/212] stop=-
[study2] 2026-10-19T01:25:26Z STAGE 1 COMPLETE: glm 5300/5300 and gptoss 5300/5300 calls (parse ok 99.9% / 100%), analysis run: gate FAIL (kappa vs AH 0.245 / 0.310, vs R2 0.187 / 0.291; reference 0.495). Stage 2 is not run as an LLM-labeled audit. Next: bank freeze, eligibility count, descriptive judge scoring (ETA ~20 min), final report
[study2] 2026-10-19T01:26:22Z bank frozen (sha256 a39bcc0f...a33c8, tag access2026-study2-bank-freeze); eligibility: 70 eligible clusters (target 60 met), 208 eligible cells, 26 clusters eligible in A and B; starting DESCRIPTIVE judge scoring (glm, gptoss; 208 cells x 3 repeats each, ETA ~15 min); no label-based statistic
[study2] 2026-10-19T01:37:47Z descriptive judge scoring complete (glm 624/624, gptoss 624/624 calls, 0 invalid); Study 2 finished: Stage 1 gate FAIL, Stage 2 not run as an audit

[addendum33] 2026-10-19 preserved-control labels (post hoc): plan committed alone (a9e1fef), code and manifest (915e019), tokenizer preflight 28.4k / 28.0k max prompt tokens (0 of 12 over the window); both models labeled all 12 cells x 25 slots (300/300 calls each, parse ok 99.3% GLM / 99.7% gpt-oss) with 8 workers each through the request-only port-forward to the shared server; the port-forward is closed; nothing was started, stopped or changed on either host and the shared server was not touched. Result: majority S=1 on 4 (GLM) and 2 (gpt-oss) of 12, 2 for both models; consistent 1, 4 and 1; consistent and S=1 0, 1 and 0. See REPORT_preserved.md.
