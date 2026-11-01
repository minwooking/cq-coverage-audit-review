# BLIND AUDIT (eqv2)

Plan-based, exploratory; addendum 47. AI-generated draft -- review before reliance.

## B1 static AST scan of the tools

- `blind_audit.py`: clean (2 informational)
    - line 3 (prose-mention): pattern `eligibility`
    - line 38 (exempt-listed): pattern `eligibility`
- `common.py`: clean
- `dedup.py`: clean
- `draft.py`: clean (1 informational)
    - line 3 (prose-mention): pattern `eligibility`
- `frame.py`: clean (1 informational)
    - line 3 (prose-mention): pattern `eligibility`
- `validate.py`: clean

## B2 runtime open-log scan

- `blind_open_log_b1.jsonl`: 0 forbidden open(s)

total forbidden opens: **0**

## B3 transcript scan

- The drafting tools were executed by the subagent that ran this stage; its transcript (`…/subagents/agent-a52bbf4e6741c845d.jsonl`) was scanned (tool-call arguments only, forbidden-pattern counts only, no content retained): 96 tool calls, 26 pattern occurrences, **zero path-like occurrences** — all 26 are text-level mentions (the literal `.env` token inside a `jq` settings-keys argument, the words "eligibility"/"annotation/" inside analysis-script code, and the forbidden-path list quoted verbatim in the comments of the scratchpad drivers).
- The parent session transcript (`4373df9e-…jsonl`: 926 tool calls, 99 occurrences) was also scanned for completeness: all occurrences are mentions or the analysis greps themselves; the 2026-10-27 drafting-window subset holds 24, likewise mention-level. The parent's earlier (plan-authoring) parts had read access to the renderings by design — stated in 47.3, not excluded.
- A sibling subagent in the same parent session read `run_holdout.py` eligibility code (2 occurrences of the "eligibility" pattern, code reading only); it executed no drafting tool, so it is outside the B3 scope as written ("the sessions that ran the drafting tools") — stated for completeness.
- The tool's own `audit_transcripts` crashed on this transcript's nesting (`cur.get("type")` returned a dict, unhashable for the membership test); the scan was re-run with the same counting logic plus a type guard. The tool was not edited; the deviation is stated here (47.3: problems are reported, not patched).
- The decisive access evidence is B2: the runtime open log records **0** forbidden opens for the whole run. Argument mentions measure a different thing than file access.
- B3 verdict: PASS (with the stated limitation).

## Limitations (verbatim)

B1-B2 cannot prove what a human or agent saw. The session that designed the frame had read access to the renderings and graphs, and recomputed their hashes; that access is stated, not excluded (addendum 47, 47.3).

## Verdict

B1 PASS, B2 PASS, B3 NOT RUN

