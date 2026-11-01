# Addendum 30 -- schedule from the 10-call pilot (committed before Tier 1)

> AI-generated; review before use. This note changes no rule, prompt, persona, cell set or threshold of `PLAN.md` (commit `798a04f`). It records the probe, the pilot and the wall-clock plan.

## Probe (read-only, 2026-10-18 about 08:20 UTC)

All three endpoints answered `/v1/models` and were idle (no running or waiting request from anybody else): `glm` and `gptoss` through the local port-forward to the shared server host (window 65,536 each), `qwen` through the local <internal-proxy> gateway (listed as the vLLM-served Qwen3.8-Flash-Next). No endpoint was down. Nothing was started, stopped or written on any server.

## Pilot (10 calls per model: first two cells of the Tier-1 order x 5 personas x seed 1; excluded from every analysis, files under `pilot/`)

| model | calls ok / sent | prompt tokens / call | completion tokens / call | wall for 10 calls at 3 workers | seed parameter |
|---|---|---|---|---|---|
| `glm` | 10 / 10 | 12.6k | 109 | 29 s | accepted |
| `gptoss` | 10 / 10 | 12.2k | 122 | 21 s | accepted |
| `qwen` | 10 / 10 | 12.4k | 1,618 | 85 s | accepted (whether the gateway honours it is unknown; recorded as sent) |

Parse rate 30 / 30 (first attempt). The pilot has no prefix-cache hits (every call is a new prompt), so the per-call times below are upper bounds for `glm` and `gptoss`; seeds 2-5 of each (cell, persona) pair reuse the prefix.

## Estimate and plan

* Tier 1, `glm`: 182 cells x 25 = 4,550 calls; at the pilot's 2.9 s/call (3 workers) at most about 3.7 h, likely 1.5-2.5 h with cache hits.
* Tier 1, `gptoss`: 4,550 calls; at 2.1 s/call at most about 2.7 h.
* Tier 1, `qwen` (secondary): 183 cells x 25 = 4,575 calls; at 8.5 s/call about 10.8 h and about 64M tokens for the full set, which is more than the secondary model warrants. **Plan:** run it concurrently with the primary models (a different endpoint, 3 workers) in the same seeded cell order, with a **wall-clock cap of 6 h** and a **token budget of 45M** (prompt + completion); no new cell starts after a cap. Its evaluated set is the cells it completed (all 25 slots), a random subset because the order is a seeded shuffle that uses no label. It is reported descriptively and never enters the verdict.
* `glm` and `gptoss` run concurrently (different endpoints, 3 workers each, courtesy gate on). Tier 2 (28 + 72 = 100 cells x 25 = 2,500 calls per model) starts for a primary model only after its Tier 1 is complete and the pilot-independent checks of `PROGRESS.md` are written; Tier 2 is not run for `qwen`.
* Analysis: `analyze.py` and its tests are committed before the first real comparison with the human labels, which is run when `glm` and `gptoss` have completed Tier 1; a final run follows when `qwen` has stopped.
