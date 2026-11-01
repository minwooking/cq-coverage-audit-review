"""Disclosed, non-confirmatory LLM auxiliary check over the 224 judged cells.

This is a supplementary, rater-independent sanity signal, NOT the
pre-registered Channel-2 evidence-anchored adjudication described in
``annotation/PROTOCOL.md``. It exists because the human annotation pass that
protocol requires has not run yet (Section "Study Design" of ``main.tex``).
It is deliberately kept out of ``analyze_holdout.py``: that script accepts
only ``--label-source human`` or an explicit simulation marker
(``canonical_label_source``'s closed set), and this file's records are never
passed to it. See PREREG.md's dated addendum for the full rationale.

Independence from the confirmatory judge and the extraction pipeline:
  - The confirmatory Layer-1 judge for this run is gemini-3.6-flash (Google).
    Using it again here would be self-enhancement bias (the same family
    grading its own evidence).
  - The extraction pipeline that produced the six rendered variants uses
    Qwen/Qwen3-Next-80B-A3B-Instruct-FP8 (Alibaba). Using a Qwen judge here
    would not be independent of the artifact under test.
  - This script therefore calls an OpenAI-family model (gpt-5.6-luna, served
    locally through an OpenAI-compatible proxy at
    http://localhost:PORT/v1) -- a third, unrelated model family.

What the check actually asks: for every cell where the confirmatory judge
quoted a non-empty evidence span, an independent prompt (NOT the judge's
scoring rubric in run_holdout.py -- a separate yes/no support question) asks
whether that quoted span, read at face value, supports answering the CQ. The
judge's own score is never shown to the auxiliary model. Cells where the
judge quoted no evidence at all (J=0, evidence="") are scored A_auxiliary=0
without a model call: an empty span cannot support an answer by definition,
the same rule ``annotation/PROTOCOL.md`` uses for the human verdict.

Output: one JSON object per line in
``harness/real_run/llm_auxiliary_labels.jsonl`` with fields
``cell_id``, ``A_auxiliary``, ``model``, ``timestamp``, plus
``label_source`` (always ``llm_auxiliary_<model>``, never ``human`` or any
value ``analyze_holdout.canonical_label_source`` would accept), ``J`` (the
judge score, for convenience only), ``evidence_empty``, and ``rationale``.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent
DEFAULT_CELLS = HERE / "real_run" / "cells.jsonl"
DEFAULT_BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"
DEFAULT_OUT = HERE / "real_run" / "llm_auxiliary_labels.jsonl"

# Local OpenAI-compatible proxy already configured in this environment
# (ANTHROPIC_BASE_URL uses the same host for the Anthropic-shaped API; this
# is its OpenAI-compatible chat/completions route, verified reachable and
# unauthenticated for localhost during this session). Overridable via env
# for reproduction on a machine without this exact proxy.
DEFAULT_ENDPOINT = "http://localhost:PORT/v1"
DEFAULT_MODEL = "gpt-5.6-luna"
ENDPOINT_ENV = "AUX_CHECK_ENDPOINT"
MODEL_ENV = "AUX_CHECK_MODEL"
API_KEY_ENV = "AUX_CHECK_API_KEY"  # optional; empty string is fine locally
CONCURRENCY_ENV = "AUX_CHECK_CONCURRENCY"
MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 12.0

# Deliberately NOT run_holdout.RUBRIC: that prompt asks a model to produce a
# fresh 0-3 completeness score plus its own evidence quote for a whole
# artifact. This prompt asks a narrower, independent yes/no question about
# evidence someone else (the confirmatory judge) already quoted -- an
# evidence-verification task, not a re-judging task.
SYSTEM_PROMPT = (
    "You audit whether a quoted piece of textual evidence actually supports "
    "answering a question. You are not scoring completeness, quality, or "
    "correctness of any underlying knowledge graph or model -- only whether "
    "the quoted text, read at face value, contains information that "
    "directly helps answer the question, even partially. You were not told "
    "and must not guess any other score assigned to this evidence. Respond "
    "with ONLY a single JSON object, no other text before or after it, "
    'exactly in this shape: {"supported": 0 or 1, "rationale": "<one short '
    'sentence>"}. supported=1 only if the quoted evidence is directly '
    "relevant to answering the question. supported=0 if it is irrelevant, "
    "only tangentially related, or does not actually address the question."
)


def build_user_prompt(question: str, evidence: str) -> str:
    return (
        f"QUESTION: {question}\n\n"
        f"QUOTED EVIDENCE (verbatim span from a rendered knowledge-graph "
        f"artifact, produced by a separate process you are not otherwise "
        f"told about):\n{evidence}\n\n"
        "Does this quoted evidence support answering the question?"
    )


def normalise_evidence(raw: object) -> str:
    """cells.jsonl stores judge evidence as either a str or a list[str]
    (observed: 221 str, 3 single-element list -- an artifact of the judge's
    own JSON formatting, not something this script should paper over
    silently)."""
    if raw is None:
        return ""
    if isinstance(raw, list):
        return " | ".join(str(item) for item in raw if str(item).strip())
    return str(raw)


def load_questions(bank_path: Path) -> dict[str, str]:
    with bank_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    questions = {row["cq_id"]: row["question"] for row in rows}
    if len(questions) != 36:
        raise SystemExit(
            f"REFUSING TO RUN: expected 36 CQs in {bank_path}, found {len(questions)}"
        )
    return questions


def _extract_json_object(content: str) -> dict | None:
    """Lenient fallback parse: the model was told to return only JSON, but
    is not run in a schema-constrained decoding mode (see the
    response_format note below), so tolerate stray surrounding prose by
    locating the outermost {...} span."""
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(content[start : end + 1])
    except json.JSONDecodeError:
        return None


def call_aux_model(
    endpoint: str, model: str, question: str, evidence: str, api_key: str
) -> tuple[dict, bool]:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(question, evidence)},
        ],
        "temperature": 0.0,
        "max_tokens": 256,
        # Deliberately NOT response_format={"type": "json_object"}: verified
        # during development that this local proxy returns HTTP 502
        # ("upstream stream ended early") specifically when structured
        # JSON-mode is combined with real evidence-span content (reproduced
        # 5/5 on one real cell; the identical request without
        # response_format returns 200 every time). Plain prompting + the
        # lenient extractor below is the reliable path against this
        # endpoint; a schema-enforcing endpoint would not need it.
    }
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read())
            content = payload.get("choices", [{}])[0].get("message", {}).get("content")
            if not content:
                return {"_error": "empty content"}, False
            if isinstance(content, dict):
                return content, True
            parsed = _extract_json_object(str(content))
            if parsed is not None:
                return parsed, True
            return {"_unparsed": str(content)}, False
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2**attempt)))
                continue
    return {"_error": f"request failed after retries: {last_exc!r}"}, False


def score_cell(
    cell: dict, questions: dict[str, str], endpoint: str, model: str, api_key: str
) -> dict:
    cell_id = cell["cell_id"]
    cq_id = cell["cq_id"]
    question = questions.get(cq_id)
    if question is None:
        raise SystemExit(f"REFUSING TO RUN: cq_id {cq_id!r} (cell {cell_id}) not in bank")
    evidence = normalise_evidence((cell.get("judge_response") or {}).get("evidence"))
    timestamp = datetime.now(timezone.utc).isoformat()
    if not evidence.strip():
        # Same rule annotation/PROTOCOL.md gives the human rater: an empty
        # span cannot support an answer. No model call needed or made.
        return {
            "cell_id": cell_id,
            "cq_id": cq_id,
            "J": cell.get("J"),
            "A_auxiliary": 0,
            "evidence_empty": True,
            "rationale": "no evidence span quoted by the confirmatory judge",
            "model": model,
            "label_source": f"llm_auxiliary_{model}",
            "timestamp": timestamp,
        }
    parsed, ok = call_aux_model(endpoint, model, question, evidence, api_key)
    if not ok or "supported" not in parsed:
        return {
            "cell_id": cell_id,
            "cq_id": cq_id,
            "J": cell.get("J"),
            "A_auxiliary": None,
            "evidence_empty": False,
            "rationale": None,
            "model": model,
            "label_source": f"llm_auxiliary_{model}",
            "timestamp": timestamp,
            "error": parsed,
        }
    try:
        supported = int(parsed["supported"])
    except (TypeError, ValueError):
        supported = None
    return {
        "cell_id": cell_id,
        "cq_id": cq_id,
        "J": cell.get("J"),
        "A_auxiliary": supported,
        "evidence_empty": False,
        "rationale": parsed.get("rationale"),
        "model": model,
        "label_source": f"llm_auxiliary_{model}",
        "timestamp": timestamp,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    ap.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--endpoint", default=os.environ.get(ENDPOINT_ENV, DEFAULT_ENDPOINT))
    ap.add_argument("--model", default=os.environ.get(MODEL_ENV, DEFAULT_MODEL))
    ap.add_argument("--api-key", default=os.environ.get(API_KEY_ENV, ""))
    ap.add_argument(
        "--concurrency",
        type=int,
        default=int(os.environ.get(CONCURRENCY_ENV, "4") or "4"),
    )
    args = ap.parse_args()

    cells = [
        json.loads(line)
        for line in args.cells.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    questions = load_questions(args.bank)

    results: dict[str, dict] = {}
    has_evidence = {
        c["cell_id"]: bool(normalise_evidence((c.get("judge_response") or {}).get("evidence")).strip())
        for c in cells
    }
    to_call = [c for c in cells if has_evidence[c["cell_id"]]]
    trivial = [c for c in cells if not has_evidence[c["cell_id"]]]

    for cell in trivial:
        record = score_cell(cell, questions, args.endpoint, args.model, args.api_key)
        results[record["cell_id"]] = record

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {
            pool.submit(score_cell, cell, questions, args.endpoint, args.model, args.api_key): cell
            for cell in to_call
        }
        done = 0
        for future in as_completed(futures):
            record = future.result()
            results[record["cell_id"]] = record
            done += 1
            if done % 20 == 0 or done == len(to_call):
                print(f"[llm_auxiliary_check] scored {done}/{len(to_call)} model-call cells", flush=True)

    ordered = [results[c["cell_id"]] for c in cells]
    failures = [r for r in ordered if r.get("A_auxiliary") is None]
    if failures:
        print(f"WARNING: {len(failures)} cell(s) failed to parse an auxiliary verdict:")
        for r in failures[:10]:
            print(f"  {r['cell_id']}: {r.get('error')}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for record in ordered:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    n = len(ordered)
    n_ones = sum(1 for r in ordered if r.get("A_auxiliary") == 1)
    n_zeros = sum(1 for r in ordered if r.get("A_auxiliary") == 0)
    print(
        f"[llm_auxiliary_check] wrote {n} records to {args.out} "
        f"(A_auxiliary=1: {n_ones}, A_auxiliary=0: {n_zeros}, failed: {len(failures)})"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
