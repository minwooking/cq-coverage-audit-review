# PROGRESS (addendum 36 amendment B) -- times UTC, 2026-10-20
- 10:25 plan committed (945d7f9). Model check: Qwen3.8 has only 27B below Flash-Next; 8B and 4B do not exist -> Qwen3.5-9B and Qwen3.5-4B (PLAN B.1).
- 10:33 serving: GPU room only on <internal-host> GPU 0 (shared-server and <internal-host> have none). Launch #1 (27B, 32k context) replaced at 10:35 by the same model with 131072 context so that no Study 5 cell exceeds the context (Study 5 q38 used 262144); no failure, no driver error.
  Launch command (key from a local env file, host path and port bound to loopback only; key, host and port omitted):
  `docker run -d --name study5b-qwen38-27b --gpus device=0 --ipc host --env-file <keyfile> -v <hf-cache>:/root/.cache/huggingface -p <loopback>:<port>:8000 <image> --model Qwen/Qwen3.8-27B --served-model-name Qwen/Qwen3.8-27B --gpu-memory-utilization 0.80 --max-model-len 131072 --max-num-seqs 4 --reasoning-parser qwen3 --language-model-only`
- 10:39 q38_27b scoring started: 372 A/B cells x 3 + 105 F cells x 3 = 1431 calls, 4 workers, ~1.2 calls/s; ETA ~11:00.
- 11:09 q38_27b A/B done (1116 valid of 1116), 11:20 F done (315 of 315). Pre-fix: 4 workers, ~0.65 calls/s.
- 11:21 27B container removed; Qwen3.5-9B (utilisation 0.35) and Qwen3.5-4B (0.25) served together on the same GPU, same image and flags except model, utilisation and port.
- 11:48-11:50 q35_9b and q35_4b done: 9B 1426 valid of 1431 (5 invalid), 4B 1428 of 1431 (3 invalid); invalid = no parseable score after the two retries; nothing imputed (cells keep the repeats that are valid).
- 11:55 study5b-* containers stopped and removed, key file deleted, tunnels closed. Weights left in the shared HF cache of the host (27B 52 GB, 9B 19 GB, 4B 8.8 GB).
- Results: results.json, REPORT_auto.md, tables.tex, scores_<judge>.csv, calls_summary.json. Agreement with the other panel judges reads Study 5's committed scores if present, else its local raw files (the Study 5 gateway judge may have been partial at read time).
