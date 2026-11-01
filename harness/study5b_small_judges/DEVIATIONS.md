# Deviations (addendum 36 amendment B)
1. Qwen3.8-8B and Qwen3.8-4B do not exist (checked 2026-10-20); Qwen3.5-9B and Qwen3.5-4B are used instead (PLAN B.1). The three ladder judges are not in the pre-fixed independent-family count (PLAN B.2).
2. The 27B was launched once with a 32k context and replaced within two minutes, before any scoring call, by the same model with a 131072 context so that no Study 5 cell would exceed it.
3. Workers = 4 per judge (server `max-num-seqs` 4) instead of 3: these are private containers, not shared endpoints.
4. Serving on a GPU of the shared a shared server (GPU 0 was empty at the time); no other container was touched.
