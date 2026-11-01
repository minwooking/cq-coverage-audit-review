# DEVIATIONS b2 (draft, validation, de-duplication, audit and sample of batch b2)

Caller-side only. No file under `tools/`, no item, no rule, no pinned hash and no request
parameter other than those listed below was changed. Drivers live outside the repository.

## D1 - thinking-off as `reasoning_effort: "none"` (same as r2 D1)
The gateway ignores `enable_thinking: false`; with it the hidden reasoning can use the whole
256-token budget (`content: null`, `finish=length`). The driver adds `reasoning_effort: "none"`.
Everything else is `draft.make_request_body`: temperature 0, max_tokens 256, JSON object, no tools.

## D2 - null content treated as retryable (same as r2 D2)
Inside the tool's own 4-attempt budget. In this run: 0 retries (875 of 875 logged calls ok at attempt 1).

## D3 - URL shape
`EQV2_DRAFT_ENDPOINT` carries no path, so the driver resolves `<endpoint>/v1/chat/completions`
(verified by a model-list GET and one connectivity call). Host and port are in no file.

## D4 - route health
A model-list GET answered and listed the drafting route; the primary route was used for all
calls. The fallback route was not needed. The environment had no EQV2_* variables preset, so
the endpoint was taken from the session's gateway variable and the model id set explicitly.

## D5 - replacement wave drafter (same as r2)
`validate.py` has no CLI seam for the wave; the driver wraps `validate_batch` to pass a drafter
that calls `draft.draft_one`. Wave drafts are in `draft_calls_b2.jsonl` after the 504 first calls.
Methodology had no tail left, so its drops stay dropped.

## D6 - local embedding cache for D5
The default model cache of the user account was empty, so `local_embed_fn` raised
`EmbedMissingError`. A pre-existing local backup of that cache holds all-MiniLM-L6-v2; the
process was pointed at it with `HF_HOME` and `HF_HUB_OFFLINE=1`. Nothing was downloaded.
tau_emb is the pinned value from `tau_emb.json`.

## D7 - blind_audit.py crash (tool not edited)
`write_report` raised KeyError on the informational entries of exempt tools (no `line` or
`pattern` key). The audit was run through a driver that executes a copy of the source with the
informational line made `.get`-tolerant. B1 and B2 logic is unchanged.

## D8 - B3 not run
The target session transcripts were not identified, so B3 was skipped (reported as NOT RUN).

## D9 - extra hook log
`blind_audit.py` installs its hook with the fixed name `blind_open_log_b1.jsonl`, so
`logs_b2/` holds that file (audit and plan runs) next to `blind_open_log_b2.jsonl`. Both have zero forbidden opens.

## D10 - de-duplication log recomputed on the final rows (added by the maintainer, before the author saw the sample)
The first `dedup_log_b2.csv` came from running `dedup.py` over the **504 original drafts** (206 excluded, 2 log-only).
That is not the set that enters the bank: the validation pass keeps 253 of those drafts and replaces 203 dropped ones
with other questions that reuse the dropped row's id, so 160 of the 456 kept ids carried an "exclude" or "log_only"
decision that belonged to the dropped original row. The maintainer re-ran the same rules (D1-D5, tau 0.5168, the five
reference banks and the frozen b1 bank as `--extra`) over `validated_b2.jsonl`, the 456 final rows: **450 keep, 6
log_only, 0 excluded**, one row per kept id, as in b1. The new file is `dedup_log_b2.csv`; the original is kept,
unchanged, as `dedup_log_b2_rawdraft.csv` (the counts of D-rule hits among dropped rows in `validate_report_b2.json`
refer to the dropped rows and differ from it for the same reason). The embedding model for this re-run was read from the
same local backup cache as D6 (revision `1110a243...`), offline.
Sample ordering: ids run CQE505..CQE1008, so `screen_sample.py` sorts them by number before the seeded shuffle (the
string order would put CQE1000 before CQE505); for b1's and round 2's three-digit ids the two orders are identical.
