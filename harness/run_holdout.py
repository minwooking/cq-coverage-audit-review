"""Execute the pre-registered Brick holdout against an OpenAI-compatible judge.

The formal run writes one JSONL record per randomized cell and a manifest.  The
cell plan is 36 frozen questions crossed with every rendered variant in the
variant manifest, plus the registered ablated and preserved controls.  Control
cells are generated from the definitions in the preregistered protocol: an
ablated cell has its supporting rendered line removed, while a preserved control
uses a frozen paraphrase with the rendered view intact.

No variant is synthesized.  A missing or malformed variant manifest is a hard
failure before any judge request (or API-key lookup).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent
REPO = ACCESS.parent.parent
from domains import DEFAULT_DOMAIN, DomainConfig, known_domains, load_domain  # noqa: E402
FROZEN_BANK_SHA256 = "993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507"
FROZEN_RUBRIC_SHA256 = "d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf"
FROZEN_RENDERING_SHA256 = "eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e"
FROZEN_BANK_ROWS = 36
REGISTERED_SEED = 20260913
REGISTERED_ABLATED = 24
REGISTERED_PRESERVED = 12
SMOKE_ENDPOINT = "http://localhost:PORT/v1"
SMOKE_MODEL = "qwen-next-flash"
DEFAULT_MAX_TOKENS = 1024
API_KEY_ENV = "HOLDOUT_JUDGE_API_KEY"
ENDPOINT_ENV = "HOLDOUT_JUDGE_ENDPOINT"
MODEL_ENV = "HOLDOUT_JUDGE_MODEL"
# Optional, judge-agnostic decoding overrides merged verbatim into the request
# body under the "extra_body" key (e.g. Gemini's thinking_config: PREREG.md
# [2026-09-20] addendum).  Unset by default -- a judge that needs no such
# override (gpt-5.4 has none) sees byte-identical request bodies to before
# this variable existed.
EXTRA_BODY_ENV = "HOLDOUT_JUDGE_EXTRA_BODY"
# [2026-09-21] A second, differently-shaped override, added for qwen-next-flash
# (PREREG.md's "Confirmatory judge 세 번째 재결정" addendum). Gemini's
# OpenAI-compatible translator specifically wants extra fields nested under a
# literal top-level "extra_body" JSON key (EXTRA_BODY_ENV above, verified
# against Google's own curl example). vLLM's OpenAI-compatible server wants
# the opposite: fields such as chat_template_kwargs must be genuine top-level
# request keys -- nesting them under "extra_body" is silently ignored (probed
# directly against this endpoint: with nesting, reasoning_tokens stayed
# nonzero; as flattened top-level fields, reasoning_tokens dropped to 0 and a
# real 70k-token cell that had been returning null content under HTTP 200
# (the entire 1024-token budget consumed by internal <think> reasoning,
# finish_reason="length") started returning a well-formed
# {"score":..,"evidence":..} instead). This variable exists so that fix does
# not require changing EXTRA_BODY_ENV's already-verified Gemini shape.
EXTRA_TOP_LEVEL_ENV = "HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS"
RUBRIC_PATH = ACCESS / "rubric" / "RUBRIC_L1.md"
RENDERING_PATH = ACCESS / "rubric" / "RENDERING_SPEC.md"
TTL_PATH = ACCESS / "data" / "brick-v1.4.4.ttl"
DEFAULT_VARIANTS_MANIFEST = HERE / "variants" / "MANIFEST.json"
PARAPHRASE_PATH = ACCESS / "bank" / "cq_bank_brick_v1_paraphrases.csv"

# [2026-09-21] Network-level resilience for the judge HTTP call, added after a
# real run against Gemini 3.6-flash hit HTTP 429 on 158/224 cells (no pacing
# or retry existed before this).  This is a transport-layer retry ONLY -- it
# is orthogonal to the cell-level "attempt" counter that G7 audits (see the
# `attempts` dict in main()): a network retry that eventually succeeds still
# records attempt=1 for that cell, exactly as before this change.  Decoding
# parameters (temperature, max_tokens) and the judging/parsing logic below
# are untouched.
#
# The 1.0s default was sized for a remote, rate-limited API (Gemini).  A
# self-hosted local judge has no such limit, so the interval is overridable
# via HOLDOUT_JUDGE_MIN_INTERVAL_S; main() also auto-relaxes it to 0.0 when
# the resolved endpoint host is localhost/127.0.0.1 and the env var was not
# explicitly set (see the "local endpoint" block in main()).
MIN_INTERVAL_ENV = "HOLDOUT_JUDGE_MIN_INTERVAL_S"
JUDGE_MIN_REQUEST_INTERVAL_S = float(os.environ.get(MIN_INTERVAL_ENV, "1.0"))
JUDGE_MAX_RETRIES = 5
JUDGE_BACKOFF_BASE_S = 2.0
JUDGE_BACKOFF_CAP_S = 16.0
# A Retry-After longer than this is not waited out: the cell is recorded as failed (HTTP 429 in
# _error, so callers' quota detectors still fire).  2026-10-14: a ~2.5M s Retry-After hung a run.
JUDGE_RETRY_AFTER_CAP_S = 300.0

# [2026-09-21] 4-way concurrent judge dispatch (PREREG.md's qwen-next-flash
# addendum).  Overridable for tests / a differently-provisioned judge; the
# registered protocol does not depend on this value -- it only changes how
# fast the same 224 independent cell requests are issued, not what is asked
# or how a response is scored.
JUDGE_CONCURRENCY_ENV = "HOLDOUT_JUDGE_CONCURRENCY"
JUDGE_CONCURRENCY = max(1, int(os.environ.get(JUDGE_CONCURRENCY_ENV, "4") or "4"))

# [2026-09-21] Documented, coordinate-based eligibility exclusions -- see
# PREREG.md's "[2026-09-21] Eligibility gate 조정 -- 확인된 코퍼스 희소성"
# addendum for the full evidentiary basis (this comment is a pointer, not a
# restatement -- the addendum is the source of truth).
#
# Each entry is one specific (variant, cq_id) PRIMARY cell -- never a whole
# CQ, never a whole variant -- whose grounding anchor was independently
# reconfirmed absent from that exact rendered artifact on 2026-09-21, AFTER
# every one of the six variants (A-F) had already been regenerated under the
# PREREG.md-registered extraction model (Qwen/Qwen3-Next-80B-A3B-Instruct-FP8
# on an internal host; see commits 87d3c7e and 3163f9a). The same 28 cells failed,
# identically, before and after that regeneration -- this is not a
# model-quality artifact.
#
#   - 3 CQs (CQB15 prop:feeds, CQB22 prop:buildingPrimaryFunction, CQB23
#     skos:definition brick:yearBuilt) are missing in ALL SIX variants. Their
#     grounding terms are extremely rare in the frozen extraction corpus
#     (harness/brick_corpus.json) itself -- 5, 2, and 1 exact,
#     word-boundary occurrences respectively (re-verified 2026-09-21) -- so
#     no extraction condition, not even the full structured B-F pipeline,
#     can surface them. 3 of the 36 frozen CQs are therefore genuinely
#     undecidable in this domain, in every variant.
#   - 10 CQs are missing ONLY in Variant A (the naive, single-pass baseline
#     -- see harness/variants/MANIFEST.json's per-variant "description").
#     Their grounding terms are also corpus-rare (2-6 occurrences) but ARE
#     recovered by the full structured pipeline (Variants B-F: triple
#     extraction + spaCy refinement + LLM typing); Variant A's much shorter
#     rendered output (~1913 lines vs. B-F's 4623+) does not retain them.
#     This is expected behaviour for a deliberately naive baseline, not a
#     hollow/broken artifact (contrast harness/variants/VARIANT_A_BLOCKED.md,
#     the actual hollow-artifact defect, already resolved separately). These
#     10 CQs remain answerable and gradable in 5 of 6 variants -- only their
#     single Variant-A primary cell is excluded.
#
# Do NOT add an entry here without a corresponding dated PREREG.md addendum
# explaining the evidence. Do NOT remove an entry to silence a preflight
# failure without first re-verifying against real (non-synthetic-fixture)
# render output -- removing an entry here re-enables the hard gate for that
# cell. Any (variant, cq_id) pair NOT listed here still hard-refuses the run
# on any grounding failure, exactly as before this change.
DOCUMENTED_EXCLUSIONS: tuple[dict[str, str], ...] = (
    {"variant": "A", "cq_id": "CQB15", "reason": "corpus_sparsity_all_variants"},
    {"variant": "B", "cq_id": "CQB15", "reason": "corpus_sparsity_all_variants"},
    {"variant": "C", "cq_id": "CQB15", "reason": "corpus_sparsity_all_variants"},
    {"variant": "D", "cq_id": "CQB15", "reason": "corpus_sparsity_all_variants"},
    {"variant": "E", "cq_id": "CQB15", "reason": "corpus_sparsity_all_variants"},
    {"variant": "F", "cq_id": "CQB15", "reason": "corpus_sparsity_all_variants"},
    {"variant": "A", "cq_id": "CQB22", "reason": "corpus_sparsity_all_variants"},
    {"variant": "B", "cq_id": "CQB22", "reason": "corpus_sparsity_all_variants"},
    {"variant": "C", "cq_id": "CQB22", "reason": "corpus_sparsity_all_variants"},
    {"variant": "D", "cq_id": "CQB22", "reason": "corpus_sparsity_all_variants"},
    {"variant": "E", "cq_id": "CQB22", "reason": "corpus_sparsity_all_variants"},
    {"variant": "F", "cq_id": "CQB22", "reason": "corpus_sparsity_all_variants"},
    {"variant": "A", "cq_id": "CQB23", "reason": "corpus_sparsity_all_variants"},
    {"variant": "B", "cq_id": "CQB23", "reason": "corpus_sparsity_all_variants"},
    {"variant": "C", "cq_id": "CQB23", "reason": "corpus_sparsity_all_variants"},
    {"variant": "D", "cq_id": "CQB23", "reason": "corpus_sparsity_all_variants"},
    {"variant": "E", "cq_id": "CQB23", "reason": "corpus_sparsity_all_variants"},
    {"variant": "F", "cq_id": "CQB23", "reason": "corpus_sparsity_all_variants"},
    {"variant": "A", "cq_id": "CQB13", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB14", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB18", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB19", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB20", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB24", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB32", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB33", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB35", "reason": "corpus_sparsity_variant_a_naive_baseline"},
    {"variant": "A", "cq_id": "CQB36", "reason": "corpus_sparsity_variant_a_naive_baseline"},
)
assert len(DOCUMENTED_EXCLUSIONS) == 28, "documented exclusion list drifted from the PREREG.md addendum count"
DOCUMENTED_EXCLUSION_KEYS: frozenset[tuple[str, str]] = frozenset(
    (entry["variant"], entry["cq_id"]) for entry in DOCUMENTED_EXCLUSIONS
)
assert len(DOCUMENTED_EXCLUSION_KEYS) == 28, "duplicate (variant, cq_id) entry in DOCUMENTED_EXCLUSIONS"
DOCUMENTED_EXCLUSION_REASONS: dict[tuple[str, str], str] = {
    (entry["variant"], entry["cq_id"]): entry["reason"] for entry in DOCUMENTED_EXCLUSIONS
}

# [2026-10-10] PREREG.md addendum 15 §15.2 (frozen): "제외는 Brick과 같은 규칙으로
# 셀 단위로 적용된다 -- 그 변이의 뷰에 grounding 앵커가 없어 ablation이 불가능한
# 셀이 제외된다. 제외된 셀은 사유와 함께 manifest에 기록되며, 제외 규칙은 IOF
# 결과를 본 뒤에 바꿀 수 없다." A domain that opts in via
# ``[eligibility] auto_exclude_grounding_ineligible = true`` in its toml
# (domains/iof.toml; brick.toml leaves it unset -> strict, unchanged) has
# preflight cells that fail EXACTLY the mechanical grounding-absence category
# (``can_ablate=false`` because the grounding anchor token is absent from that
# variant's rendered view -- missing_grounding / missing_qualified_grounding)
# recorded as exclusions carrying this reason, instead of refusing the run.
# The exclusions are derived only from the check itself -- never hand-authored
# -- and any OTHER preflight failure category still aborts. Unlike the Brick
# DOCUMENTED_EXCLUSIONS above (a frozen, hand-authored coordinate allowlist),
# there is no list here to curate: an exclusion exists exactly as long as the
# unchanged matcher says the anchor is not in the view.
GROUNDING_ABSENT_EXCLUSION_REASON = "grounding_anchor_absent_from_view per addendum 15 §15.2"

RUBRIC = """You score whether a question can be ANSWERED from the artifact shown.
Score 0-3 on answerability only. Do not score factual accuracy of the world.
0 = no related concept or relation present; 1 = partial; 2 = mostly; 3 = complete.
Return JSON: {\"score\": <0-3>, \"evidence\": \"<verbatim span, or empty>\"}"""


@dataclass(frozen=True)
class Variant:
    variant_id: str
    view: str
    source: str


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen(bank: Path, domain: DomainConfig | None = None) -> tuple[list[dict], dict[str, str]]:
    """Verify every registered input before making any judge request.

    ``domain=None`` is the registered Brick holdout (module constants, unchanged). A
    DomainConfig substitutes that domain's frozen bank digest and row count, and refuses
    outright when the domain's bank is not frozen.
    """
    bank_sha, bank_rows = FROZEN_BANK_SHA256, FROZEN_BANK_ROWS
    if domain is not None and domain.name != DEFAULT_DOMAIN:
        domain.require_frozen_bank()
        bank_sha, bank_rows = domain.bank_sha256, domain.bank_rows
    expected = {
        bank: bank_sha,
        RUBRIC_PATH: FROZEN_RUBRIC_SHA256,
        RENDERING_PATH: FROZEN_RENDERING_SHA256,
    }
    digests: dict[str, str] = {}
    for path, expected_digest in expected.items():
        if not path.exists():
            raise SystemExit(f"REFUSING TO RUN: required file not found: {path}")
        found = sha256_file(path)
        digests[path.name] = found
        if found != expected_digest:
            raise SystemExit(
                f"REFUSING TO RUN: digest mismatch for {path}\n"
                f"  expected {expected_digest}\n  found    {found}"
            )
    with bank.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != bank_rows:
        raise SystemExit(
            f"REFUSING TO RUN: expected {bank_rows} rows, found {len(rows)}"
        )
    return rows, digests


def host_only(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    return parsed.hostname or endpoint


_last_judge_request_mono: float | None = None
# [2026-09-21] The runner now dispatches judge calls from up to
# JUDGE_CONCURRENCY worker threads (see main()).  _last_judge_request_mono is
# shared module state, so it needs a lock now that the caller is no longer
# guaranteed single-threaded; holding the lock across the sleep is
# intentional -- that is what makes the pacing a true minimum interval
# between *any* two consecutive judge requests, not just within one thread.
_pace_judge_request_lock = threading.Lock()


def _pace_judge_request() -> None:
    """Enforce a minimum interval between consecutive judge HTTP requests.

    Best-effort pacing to avoid tripping the judge API's rate limit in the
    first place; the 429 retry below is the fallback when pacing alone isn't
    enough. Thread-safe: guarded by _pace_judge_request_lock so concurrent
    judge-call workers still serialize on this shared timestamp.
    """
    global _last_judge_request_mono
    with _pace_judge_request_lock:
        now = time.monotonic()
        if _last_judge_request_mono is not None:
            remaining = JUDGE_MIN_REQUEST_INTERVAL_S - (now - _last_judge_request_mono)
            if remaining > 0:
                time.sleep(remaining)
        _last_judge_request_mono = time.monotonic()


def call_judge(
    endpoint: str,
    model: str,
    question: str,
    artifact: str,
    key: str,
    max_tokens: int,
    extra_body: dict | None = None,
    extra_top_level: dict | None = None,
) -> tuple[dict, bool]:
    body_dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": RUBRIC},
            {
                "role": "user",
                "content": f"ARTIFACT:\n{artifact}\n\nQUESTION: {question}",
            },
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if extra_body:
        # Verbatim top-level "extra_body" key -- this is the documented shape
        # of Google's OpenAI-compatible chat-completions translator for
        # provider-specific fields (e.g. {"google": {"thinking_config": ...}}).
        # A judge that ignores unknown top-level keys is unaffected.
        body_dict["extra_body"] = extra_body
    if extra_top_level:
        # The opposite shape: fields merged directly at the top level of the
        # request (e.g. vLLM's {"chat_template_kwargs": {"enable_thinking":
        # false}}, PREREG.md's qwen-next-flash addendum). Deliberately
        # separate from extra_body above -- see EXTRA_TOP_LEVEL_ENV's comment
        # for why the two providers need different shapes.
        body_dict.update(extra_top_level)
    body = json.dumps(body_dict).encode()
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
    )
    last_exc: Exception | None = None
    for retry_num in range(JUDGE_MAX_RETRIES + 1):
        _pace_judge_request()
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.loads(response.read())
            content = payload.get("choices", [{}])[0].get("message", {}).get("content")
            if content is None:
                return {"_error": "content is null"}, False
            if not content:
                return {"_error": "empty content"}, False
            if isinstance(content, dict):
                return content, True
            try:
                return json.loads(content), True
            except (TypeError, json.JSONDecodeError):
                return {"_unparsed": str(content)}, False
        except urllib.error.HTTPError as exc:
            last_exc = exc
            # [2026-09-21] Capture the response body, not just repr(exc) --
            # without it a 400 (malformed request/context-length/etc.) is
            # indistinguishable from a 429 (rate limit) or any other 4xx in
            # the recorded cell, which made real failures impossible to
            # diagnose. exc.read() can only be called once and is best-effort
            # (some servers may not send a body, or the socket may already be
            # closed); failure to read it must never mask the original error.
            try:
                raw_body = exc.read()
                body_text = raw_body.decode("utf-8", errors="replace") if raw_body else ""
            except Exception:
                body_text = "<failed to read response body>"
            body_snippet = body_text[:500]
            if exc.code != 429 or retry_num >= JUDGE_MAX_RETRIES:
                return {"_error": repr(exc), "_error_body": body_snippet}, False
            retry_after = exc.headers.get("Retry-After") if exc.headers is not None else None
            wait_s: float
            if retry_after is not None:
                try:
                    wait_s = float(retry_after)
                except ValueError:
                    wait_s = min(JUDGE_BACKOFF_BASE_S * (2 ** retry_num), JUDGE_BACKOFF_CAP_S)
            else:
                wait_s = min(JUDGE_BACKOFF_BASE_S * (2 ** retry_num), JUDGE_BACKOFF_CAP_S)
            if wait_s > JUDGE_RETRY_AFTER_CAP_S:
                return {
                    "_error": repr(exc),
                    "_error_body": body_snippet,
                    "_retry_after_s": wait_s,
                    "_retry_after_capped": JUDGE_RETRY_AFTER_CAP_S,
                }, False
            print(
                f"judge HTTP 429, retry {retry_num + 1}/{JUDGE_MAX_RETRIES} in {wait_s:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait_s)
        except Exception as exc:  # preserve the cell and allow an idempotent resume
            return {"_error": repr(exc)}, False
    # Defensive: the loop above always returns on success or a terminal
    # failure; this only fires if retries were exhausted without one of the
    # explicit returns above running (should not happen given the bounds).
    return {"_error": repr(last_exc) if last_exc is not None else "judge request failed: retries exhausted"}, False


def resolve_endpoint_model(args: argparse.Namespace, smoke: bool) -> tuple[str, str]:
    endpoint = args.endpoint or os.environ.get(ENDPOINT_ENV)
    model = args.model or os.environ.get(MODEL_ENV)
    if smoke:
        endpoint = endpoint or SMOKE_ENDPOINT
        model = model or SMOKE_MODEL
    missing = [name for name, value in ((ENDPOINT_ENV, endpoint), (MODEL_ENV, model)) if not value]
    if missing:
        raise SystemExit(
            "missing required judge configuration: " + ", ".join(missing)
            + ". Set the environment variable or pass the corresponding CLI option."
        )
    return endpoint, model


def _manifest_entries(payload: object) -> list[dict]:
    """Accept the small manifest shape used by the variant builder.

    The builder may emit ``{"variants": [...]}``, a top-level list, or a
    mapping from variant id to an artifact descriptor.  This keeps the runner
    coupled to the contract (six named variants and their rendered views), not
    to incidental JSON formatting.
    """
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        raw = payload.get("variants", payload.get("artifacts"))
        if isinstance(raw, dict):
            entries = [dict(value, id=key) if isinstance(value, dict) else {"id": key, "view": value}
                       for key, value in raw.items()]
        elif isinstance(raw, list):
            entries = raw
        else:
            entries = []
    else:
        entries = []
    return [entry for entry in entries if isinstance(entry, dict)]


def _resolve_manifest_path(value: str | Path, manifest_path: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else manifest_path.parent / path


def _manifest_ref(entry: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _read_rendered_source(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"rendered view not found: {path}")
    if path.suffix.lower() in {".ttl", ".rdf", ".nt", ".xml"}:
        from run_simulated import schema_view
        return schema_view(path)
    return path.read_text(encoding="utf-8")


def _render_descriptor(
    entry: dict,
    manifest_path: Path,
    *,
    require_artifacts: bool = False,
) -> tuple[str, str]:
    """Load a manifest view, preferring explicit path fields over inline data."""
    explicit_source = _manifest_ref(
        entry, ("rendered_view_path", "view_path", "rendered_view_file")
    )
    if explicit_source is not None:
        path = _resolve_manifest_path(explicit_source, manifest_path)
        return _read_rendered_source(path), str(path.resolve())

    inline = entry.get("rendered_view")
    if isinstance(inline, str):
        if require_artifacts:
            raise ValueError("rendered view path is missing")
        return inline, "inline"

    view = entry.get("view")
    if isinstance(view, str):
        # Check for multiline content before constructing a Path (a rendered
        # view can be much longer than the filesystem filename limit).
        if "\n" in view or "\r" in view:
            if require_artifacts:
                raise ValueError("rendered view path is missing")
            return view, "inline"
        candidate = _resolve_manifest_path(view, manifest_path)
        try:
            if candidate.is_file():
                return _read_rendered_source(candidate), str(candidate.resolve())
        except OSError:
            if require_artifacts:
                raise
        if require_artifacts or entry.get("rendered_view_sha256") is not None:
            raise ValueError(f"rendered view not found: {candidate}")
        return view, "inline"

    fallback_source = _manifest_ref(entry, ("artifact_path", "artifact", "path"))
    if fallback_source is None:
        raise ValueError("rendered view path is missing")
    path = _resolve_manifest_path(fallback_source, manifest_path)
    return _read_rendered_source(path), str(path.resolve())


def _verify_manifest_artifacts(
    entry: dict,
    manifest_path: Path,
    view: str,
    source: str,
    *,
    require_artifacts: bool,
) -> None:
    """Verify registered graph/view files against manifest SHA256 values."""
    graph_ref = _manifest_ref(entry, ("graph_path", "graph_file"))
    if require_artifacts and graph_ref is None:
        raise ValueError("graph path is missing")
    if graph_ref is not None:
        graph_path = _resolve_manifest_path(graph_ref, manifest_path)
        if not graph_path.is_file():
            raise ValueError(f"graph file not found: {graph_path}")
        expected_graph = entry.get("graph_sha256")
        if require_artifacts and not isinstance(expected_graph, str):
            raise ValueError("graph_sha256 is missing")
        if expected_graph is not None:
            if not isinstance(expected_graph, str) or len(expected_graph) != 64:
                raise ValueError(f"invalid graph_sha256 for {graph_path}")
            actual_graph = sha256_file(graph_path)
            if actual_graph != expected_graph:
                raise ValueError(
                    f"graph SHA256 mismatch for {graph_path}: "
                    f"expected {expected_graph}, found {actual_graph}"
                )

    expected_view = entry.get("rendered_view_sha256")
    if require_artifacts and source == "inline":
        raise ValueError("rendered view path is missing")
    if require_artifacts and not isinstance(expected_view, str):
        raise ValueError("rendered_view_sha256 is missing")
    if expected_view is not None:
        if not isinstance(expected_view, str) or len(expected_view) != 64:
            raise ValueError("invalid rendered_view_sha256")
        actual_view = (
            sha256_file(Path(source)) if source != "inline"
            else hashlib.sha256(view.encode("utf-8")).hexdigest()
        )
        if actual_view != expected_view:
            raise ValueError(
                f"rendered view SHA256 mismatch for {source}: "
                f"expected {expected_view}, found {actual_view}"
            )


def load_variant_manifest(path: Path = DEFAULT_VARIANTS_MANIFEST, *, require_six: bool = True) -> list[Variant]:
    """Load actual variant renderings; never fabricate a missing variant."""
    if not path.exists():
        raise SystemExit(f"변이 산출물이 없다: 변이 매니페스트가 없습니다: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries = _manifest_entries(payload)
        registered_artifacts = require_six or any(
            _manifest_ref(entry, ("graph_path", "graph_file")) is not None
            or entry.get("graph_sha256") is not None
            or entry.get("rendered_view_sha256") is not None
            for entry in entries
        )
        variants: list[Variant] = []
        seen: set[str] = set()
        for entry in entries:
            variant_id = entry.get("id", entry.get("variant_id", entry.get("variant", entry.get("name"))))
            if not isinstance(variant_id, str) or not variant_id.strip():
                raise ValueError("variant id is missing")
            variant_id = variant_id.strip()
            if variant_id in seen:
                raise ValueError(f"duplicate variant id: {variant_id}")
            view, source = _render_descriptor(entry, path, require_artifacts=registered_artifacts)
            _verify_manifest_artifacts(
                entry, path, view, source, require_artifacts=registered_artifacts
            )
            if not view.strip():
                raise ValueError(f"rendered view is empty for variant {variant_id}")
            seen.add(variant_id)
            variants.append(Variant(variant_id, view, source))
    except (OSError, json.JSONDecodeError, UnicodeError, ValueError) as exc:
        raise SystemExit(f"변이 산출물이 없다: 변이 매니페스트를 읽지 못했습니다 ({path}): {exc}") from exc
    if not variants:
        raise SystemExit(f"변이 산출물이 없다: 매니페스트에 렌더링 변이가 없습니다: {path}")
    if require_six and len(variants) != 6:
        raise SystemExit(
            f"변이 산출물이 없다: 등록된 6개 변이가 필요하지만 {len(variants)}개가 있습니다: {path}"
        )
    return variants

def _constrained_shuffle(cells: list[dict], seed: int, min_gap: int = 20) -> list[dict]:
    """Seeded order with same-CQ cells separated when feasible."""
    rng = random.Random(seed)
    groups: dict[str, list[dict]] = defaultdict(list)
    for cell in cells:
        groups[cell["cq_id"]].append(cell)
    if max((len(group) for group in groups.values()), default=0) <= 1:
        result = list(cells)
        rng.shuffle(result)
        return result
    # This is the same greedy/restart strategy used by the frozen annotation
    # packet builder.  It reports no hidden random state and is deterministic.
    for _ in range(500):
        remaining = {key: list(value) for key, value in groups.items()}
        result: list[dict] = []
        last_position: dict[str, int] = {}
        while remaining:
            eligible = [
                key for key in remaining
                if key not in last_position or len(result) - last_position[key] >= min_gap
            ]
            if not eligible:
                break
            rng.shuffle(eligible)
            key = max(eligible, key=lambda item: len(remaining[item]))
            result.append(remaining[key].pop())
            last_position[key] = len(result) - 1
            if not remaining[key]:
                del remaining[key]
        if len(result) == len(cells):
            return result
    result = list(cells)
    rng.shuffle(result)
    return result


def _paraphrases(path: Path = PARAPHRASE_PATH) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(f"REFUSING TO RUN: preserved-control paraphrase file not found: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    result = {row["cq_id"]: row["paraphrase_text"] for row in rows
              if row.get("cq_id") and row.get("paraphrase_text")}
    if not result:
        raise SystemExit(f"REFUSING TO RUN: preserved-control paraphrase file is empty: {path}")
    return result


def _grounding_anchors(grounding: str) -> list[str]:
    # Groundings are frozen strings such as ``skos:definition brick:Sensor`` or
    # ``inverse:hasPoint~isPointOf``.  Match qnames and local names in the view;
    # punctuation is protocol metadata, not part of the rendered span.
    #
    # Two disjoint kinds of non-literal token appear in the frozen bank, and they
    # must be told apart by which HALF of the qname carries the meaning:
    #
    # 1. Bank-internal control syntax, keyed by PREFIX (``prop:hasLocation``,
    #    ``children:Point``, ``children_count:Equipment``, ``subclassof:X>Y``,
    #    ``disjoint:X``, ``inverse:X~Y``).  The prefix is not a namespace -- the
    #    renderer never emits e.g. "prop:" -- so only the bare LOCAL name
    #    (``hasLocation``, ``Point``, ...) is a real anchor.
    # 2. References to the RDF/RDFS/SKOS/SHACL predicate a grounding lives under
    #    (``skos:definition``, ``rdfs:comment``, ``rdfs:subClassOf``,
    #    ``sh:path``), keyed by LOCAL name.  The renderer never writes these
    #    predicate names literally either -- it writes the definition text, the
    #    " < " parent list, or nothing at all for excluded SHACL constructs --
    #    so the whole token contributes no anchor.
    #
    # The previous implementation checked only the LOCAL half against a single
    # combined set, which let every ``prop:``/``children:``-style control token
    # survive as a spurious REQUIRED qualified anchor (e.g. literal
    # "prop:hasLocation") that the renderer can never produce, and let
    # "rdfs:comment"/"rdfs:subClassOf" (missing "comment" and case-mismatched
    # "subClassOf" in that set) survive the same way. That made every grounding
    # tagged with a control prefix or ``rdfs:comment``/``rdfs:subClassOf``
    # eligibility-fail regardless of what the rendered view actually contains.
    control_prefixes = {
        "prop", "children", "children_count", "subclassof", "disjoint", "inverse", "count", "meth",
    }
    metadata_locals = {"definition", "comment", "subClassOf", "domain", "range", "inverseOf", "path"}
    # "meth" also appears as a hyphenated LOCAL suffix on control-prefixed
    # tokens (``prop:hasQuantity-meth``), tagging the row's methodology
    # category rather than naming part of the term itself; strip it the same
    # way the colon-prefixed control syntax is stripped, so the bare anchor is
    # the real local name (``hasQuantity``), not the suffixed control tag.
    control_local_suffixes = {"meth"}
    anchors: list[str] = []
    for token in re.findall(r"[A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?", grounding or ""):
        if ":" in token:
            prefix, local = token.split(":", 1)
            if prefix in control_prefixes:
                base_local, sep, suffix = local.rpartition("-")
                if sep and suffix in control_local_suffixes and base_local:
                    local = base_local
                if local not in metadata_locals:
                    anchors.append(local)
                continue
            if local in metadata_locals:
                continue
            anchors.extend((token, local))
        elif token not in metadata_locals:
            anchors.append(token)
    # Preserve order while de-duplicating.
    return list(dict.fromkeys(anchors))


def _matching_line_numbers(view: str, anchors: list[str]) -> list[int]:
    """Return lines matching the protocol's existing substring predicate."""
    return [
        line_number
        for line_number, line in enumerate(view.splitlines(keepends=True), start=1)
        if any(anchor in line for anchor in anchors)
    ]


def _qualified_name_char(char: str) -> bool:
    return char.isalnum() or char in "_.-"


def _qualified_anchor_present(line: str, anchor: str) -> bool:
    """Return whether anchor is a complete qname/control token."""
    if not anchor:
        return False

    structural = frozenset(":>~")

    for match in re.finditer(re.escape(anchor), line):
        start, end = match.span()

        # Reject an occurrence embedded in a preceding qname/control token.
        if start:
            previous = line[start - 1]
            if _qualified_name_char(previous) or previous in structural:
                continue

        if end == len(line):
            return True

        following = line[end]

        # Local-name continuation or compound/control continuation.
        if _qualified_name_char(following) or following in structural:
            # A final "." is sentence punctuation only when it is not
            # followed by another local-name character.
            if following == ".":
                next_char = line[end + 1] if end + 1 < len(line) else ""
                if next_char and _qualified_name_char(next_char):
                    continue
                return True
            continue

        # Commas, semicolons, !, ?, closing delimiters, whitespace, etc.
        # terminate the exact anchor.
        return True

    return False


# A node's own local name (an IRI fragment) is hyphen-joined, never
# space-joined -- e.g. "#brick-sensor", "#brick-hassubmeter" -- so this
# naturally stops at the next real delimiter (space, "|", ",", ";", "{",
# end of line, ...) without ever running on into unrelated surrounding
# prose or a trailing "a http://...#Class_x,skos:Concept" rdf:type clause.
_IRI_FRAGMENT_LOCAL_NAME = re.compile(r"#([A-Za-z0-9_.]+(?:-[A-Za-z0-9_.]+)*)")
# A local name this short is a genuine, on-topic concept identifier in this
# corpus -- every verified true match (Sensor, hasSubMeter, Portfolio,
# yearBuilt, Building, ...) resolves at 1 or 2 hyphen-joined words. A real
# chunktograph extraction artifact that stitches an entire garbled
# definition SENTENCE into a pseudo class name (e.g.
# "standalone-building-manage-entrance-campus-building-ground", 7 words --
# the only place the word "campus" occurs in any real B-F variant, with a
# clean gap to every genuine match below it) runs far longer -- see the
# manual audit in the commit message / final report.
_MAX_CONCEPT_WORD_RUN = 3


def _local_name_present_ci(view: str, local: str) -> bool:
    """Return whether ``local`` names -- case-insensitively, as a complete
    hyphen-joined word, not a substring/stem -- some node's own short IRI
    fragment local name anywhere in ``view``, regardless of what namespace
    prefix (if any) the bank grounding was authored against.

    This is namespace-agnostic on purpose: real renderer output is not
    obligated to reproduce the bank's authoring-time prefix (``brick:``,
    ``rec:``, ``ref:``) literally -- a renderer may use its own namespace
    (e.g. chunktograph's ``ct:``/``http://example.org/chunktograph#``) while
    still preserving the underlying vocabulary term as a class/property/
    individual local name. Only the identity of the TERM -- not the prefix
    it happens to be written under -- is what a grounding anchor is
    actually asserting exists in the artifact.

    Restricting the search to IRI-fragment local names (hyphen-joined only,
    never crossing a space) rather than scanning arbitrary label/definition
    prose is what keeps this an EXACT identity match rather than a
    substring/stem one: "Sensor" matches the node named "brick-sensor" but
    never "SensorSuffix", "ifcFileLocation" (a camelCase token with no
    hyphen boundary at all), "sensors" (a different, plural token), or a
    word merely swept into some other node's long, garbled,
    extraction-artifact name (the ``_MAX_CONCEPT_WORD_RUN`` cap above).
    """
    if not local:
        return False
    local_lower = local.lower()
    for match in _IRI_FRAGMENT_LOCAL_NAME.finditer(view):
        words = match.group(1).split("-")
        if len(words) > _MAX_CONCEPT_WORD_RUN:
            continue
        if any(word.lower() == local_lower for word in words):
            return True
    return False


def _anchor_present(text: str, anchor: str) -> bool:
    """Namespace- and case-agnostic presence check for one grounding anchor.

    - "prefix:Local" (a qname referring to a real ontology namespace, e.g.
      brick:/rec:/ref: -- bank-internal control syntax like
      prop:/children:/subclassof:/inverse: is already reduced to its bare
      local form by _grounding_anchors before it ever reaches this
      function) is satisfied by either:
        (a) the literal, case-sensitive, exact-token qname
            (_qualified_anchor_present) -- for renderers, like the direct
            Brick-TBox rendering, that write qnames out literally; or
        (b) a case-insensitive, alphanumeric-token-boundary match of the
            bare local name alone (_local_name_present_ci) -- for
            renderers, like the chunktograph pipeline's own ct: namespace,
            that keep the underlying term but never write the bank's
            authoring-time prefix, and additionally fold case (chunktograph
            renders every label/local-name lowercase).
    - Any other anchor (already bare -- either originally unqualified in
      the bank's control syntax, e.g. hasLocation/deprecation, or the bare
      local half of a qualified anchor) is matched the same
      case-insensitive, token-boundary way: for a control-syntax grounding
      the bare term IS the whole real anchor, and nothing obligates the
      renderer to reproduce the bank's PascalCase/camelCase spelling of it
      either -- chunktograph renders those lowercase too.

    In both branches this is still an EXACT term match, never a
    substring/stem match: see _local_name_present_ci's docstring for the
    token-boundary discipline that keeps "Sensor" from matching
    "SensorSuffix", "ifcFileLocation" (embedded in a larger camelCase
    token), or "sensors" (a different, plural token).
    """
    if ":" in anchor:
        if _qualified_anchor_present(text, anchor):
            return True
        return _local_name_present_ci(text, anchor.split(":", 1)[1])
    return _local_name_present_ci(text, anchor)


def _matching_line_numbers_namespace_agnostic(view: str, anchors: list[str]) -> list[int]:
    """Like ``_matching_line_numbers`` but namespace- and case-agnostic (see
    ``_anchor_present``). Used to decide which lines a real ablated-control
    cell can actually remove, so eligibility (``can_ablate``) and the
    ablation it promises stay consistent -- unlike the frozen, deliberately
    naive ``_matching_line_numbers`` (locked down by
    ``test_substring_matcher_and_ablation_remain_unchanged``), which this
    function does not replace or modify.
    """
    return [
        line_number
        for line_number, line in enumerate(view.splitlines(keepends=True), start=1)
        if any(_anchor_present(line, anchor) for anchor in anchors)
    ]


def _grounding_match_info(view: str, row: dict) -> dict:
    """Describe substring matches and apply the strict eligibility gate."""
    grounding = row.get("grounding", "")
    base_anchors = _grounding_anchors(grounding)
    anchors = list(base_anchors)
    compound_anchor = grounding.strip() if any(op in grounding for op in (">", "~")) else ""
    if compound_anchor and compound_anchor not in anchors:
        anchors.insert(0, compound_anchor)
    matching_line_numbers = _matching_line_numbers_namespace_agnostic(view, anchors)
    matched_anchors: list[str] = []
    exact_literal_matched_anchors: list[str] = []
    for line in view.splitlines(keepends=True):
        for anchor in anchors:
            if ":" in anchor and _qualified_anchor_present(line, anchor):
                if anchor not in exact_literal_matched_anchors:
                    exact_literal_matched_anchors.append(anchor)
            if _anchor_present(line, anchor) and anchor not in matched_anchors:
                matched_anchors.append(anchor)
    # Anchors that matched only through the namespace-agnostic/case-folded
    # fallback -- never via a literal, exact, case-sensitive token -- are
    # surfaced separately so a reviewer can resample exactly the matches
    # this fix newly introduces (see the final report's manual spot-check).
    relaxed_matches = [anchor for anchor in matched_anchors if anchor not in exact_literal_matched_anchors]
    qualified_anchors = [anchor for anchor in base_anchors if ":" in anchor]
    missing_anchors = [anchor for anchor in anchors if anchor not in matched_anchors]
    required_qualified_anchors = qualified_anchors
    required_unqualified_anchors = [
        anchor for anchor in anchors
        if ":" not in anchor
        and not any(
            qname != anchor and qname.split(":", 1)[1] == anchor
            for qname in required_qualified_anchors
        )
    ]
    required_grounding_anchors = required_qualified_anchors + required_unqualified_anchors
    missing_required_grounding_anchors = [
        anchor for anchor in required_grounding_anchors
        if anchor not in matched_anchors
        and not (
            compound_anchor in matched_anchors
            and compound_anchor.startswith(anchor)
            and compound_anchor[len(anchor):len(anchor) + 1] in {">", "~"}
        )
    ]
    false_positive_local_name_matches = [
        anchor for anchor in matched_anchors
        if ":" not in anchor
        and any(
            qname != anchor and qname.split(":", 1)[1] == anchor and qname not in matched_anchors
            for qname in qualified_anchors
        )
    ]
    return {
        "anchors": anchors,
        "matched_anchors": matched_anchors,
        "missing_anchors": missing_anchors,
        "required_qualified_anchors": required_qualified_anchors,
        "required_unqualified_anchors": required_unqualified_anchors,
        "required_grounding_anchors": required_grounding_anchors,
        "missing_required_grounding_anchors": missing_required_grounding_anchors,
        "relaxed_matches": relaxed_matches,
        "false_positive_local_name_matches": false_positive_local_name_matches,
        "matching_line_numbers": matching_line_numbers,
        "can_ablate": bool(matching_line_numbers) and not missing_required_grounding_anchors,
    }


def ablate_rendered_view(view: str, row: dict) -> str:
    """Remove lines carrying the frozen CQ's supporting rendered span."""
    anchors = _grounding_anchors(row.get("grounding", ""))
    lines = view.splitlines(keepends=True)
    matching_line_numbers = set(_matching_line_numbers_namespace_agnostic(view, anchors))
    kept = [line for line_number, line in enumerate(lines, start=1)
            if line_number not in matching_line_numbers]
    if not matching_line_numbers:
        raise ValueError(
            f"ablated control cannot remove supporting span for {row.get('cq_id')} "
            f"(grounding={row.get('grounding')!r})"
        )
    return "".join(kept)


def cell_key(cell: dict) -> str:
    return str(cell.get("cell_id") or f"{cell.get('cell_kind', 'primary')}:{cell['variant']}:{cell['cq_id']}")


def _primary_cells(rows: list[dict], variants: list[Variant]) -> list[dict]:
    cells: list[dict] = []
    for variant in variants:
        digest = hashlib.sha256(variant.view.encode()).hexdigest()
        for row in rows:
            cells.append({
                "cell_id": f"primary:{variant.variant_id}:{row['cq_id']}",
                "cq_id": row["cq_id"], "cluster_id": row["cluster_id"],
                "category": row["category"], "question": row["question"],
                "grounding": row.get("grounding", ""),
                "variant": variant.variant_id, "cell_kind": "primary",
                "artifact": variant.view, "artifact_digest": digest,
            })
    return cells


def _preflight_failure(result: dict) -> SystemExit:
    """Build a stable, network-free refusal message for eligibility failures."""
    summary = {
        "ablated_control_failures": result["ablated_control_failures"],
        "checked_primary_cells": result["checked_primary_cells"],
        "documented_exclusions": result["documented_exclusions"],
        "missing_grounding": result["missing_grounding"],
        "missing_qualified_grounding": result["missing_qualified_grounding"],
        "false_positive_local_name_matches": result["false_positive_local_name_matches"],
        "registered_abated": result["registered_abated"],
        "seed": result["seed"],
        "variants": result["variants"],
    }
    if result.get("preserved_control_failures"):
        summary["preserved_control_failures"] = result["preserved_control_failures"]
    return SystemExit(
        "REFUSING TO RUN: eligibility preflight failed\n"
        + json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    )


def eligibility_preflight(
    rows: list[dict],
    variants: list[Variant],
    seed: int = REGISTERED_SEED,
    paraphrase_path: Path | None = PARAPHRASE_PATH,
    exclusion_reasons: dict[tuple[str, str], str] | None = None,
    *,
    domain_name: str | None = None,
    auto_exclude_grounding_ineligible: bool = False,
) -> dict:
    """Check every registered primary/control source before judge configuration.

    A primary cell whose (variant, cq_id) coordinate is listed in
    ``DOCUMENTED_EXCLUSIONS`` is reported under ``documented_exclusions``
    instead of ``missing_grounding`` and does not, by itself, cause this
    function to raise -- see the constant's docstring/comment and the
    PREREG.md [2026-09-21] addendum. It is also removed from the pool used
    to draw ablated/preserved controls and from the primary cells the
    confirmatory judge is asked to score (``build_cell_plan``). Any OTHER
    missing-grounding cell -- any coordinate not on that frozen allowlist --
    still hard-refuses exactly as before this change.

    ``auto_exclude_grounding_ineligible=True`` (PREREG.md addendum 15 §15.2,
    set per-domain via ``[eligibility]`` in the domain toml -- IOF only;
    Brick leaves it unset) additionally turns each primary cell that fails
    EXACTLY the mechanical grounding-absence category (``can_ablate=false``
    because the anchor is not in the view: missing_grounding /
    missing_qualified_grounding) into a mechanically derived entry under
    ``auto_exclusions`` + ``eligibility_counts`` instead of a refusal, and
    draws the registered ablated controls from the remaining eligible cells
    only. Any other preflight failure category still raises; a shrunken
    eligible pool that can no longer supply REGISTERED_ABLATED controls
    still raises. With False this function's behaviour is unchanged, and
    ``auto_exclusions``/``eligibility_counts`` stay None so the manifest
    writers add no new fields.

    ``paraphrase_path=None`` means the domain registers no frozen paraphrase
    file at all (e.g. IOF, whose toml has no ``[bank].paraphrases`` entry):
    per PREREG.md addendum 15 §15.2 the preserved-control kind is then OMITTED
    from the plan and ``preserved_controls_omitted_reason`` records why; this
    is not a preflight failure. A registered path that is missing on disk
    still fails exactly as before this change.
    """
    # None = the registered Brick allowlist; another domain passes its own (usually empty).
    reasons = DOCUMENTED_EXCLUSION_REASONS if exclusion_reasons is None else exclusion_reasons
    primary = _primary_cells(rows, variants)
    row_by_cq = {row["cq_id"]: row for row in rows}
    primary_diagnostics: list[dict] = []
    missing_grounding: list[dict] = []
    documented_exclusions: list[dict] = []
    auto_exclusions: list[dict] = []
    for cell in primary:
        row = row_by_cq[cell["cq_id"]]
        match = _grounding_match_info(cell["artifact"], row)
        diagnostic = {
            "cell_id": cell["cell_id"],
            "variant": cell["variant"],
            "cq_id": cell["cq_id"],
            "grounding": row.get("grounding", ""),
            **match,
        }
        primary_diagnostics.append(diagnostic)
        if not match["can_ablate"]:
            exclusion_reason = reasons.get((cell["variant"], cell["cq_id"]))
            grounding_absent = not match["matching_line_numbers"] or match["missing_required_grounding_anchors"]
            if exclusion_reason is not None:
                documented_exclusions.append({
                    **diagnostic,
                    "documented_exclusion_reason": exclusion_reason,
                })
            elif auto_exclude_grounding_ineligible and grounding_absent:
                auto_exclusions.append({
                    "cell_id": cell["cell_id"],
                    "variant": cell["variant"],
                    "cq_id": cell["cq_id"],
                    "missing_required_grounding_anchors": list(match["missing_required_grounding_anchors"]),
                    "reason": GROUNDING_ABSENT_EXCLUSION_REASON,
                })
            else:
                missing_grounding.append(diagnostic)

    auto_excluded_keys = {entry["cell_id"] for entry in auto_exclusions}
    eligible_primary = [
        cell for cell in primary
        if (cell["variant"], cell["cq_id"]) not in reasons
        and cell["cell_id"] not in auto_excluded_keys
    ]

    result = {
        "seed": seed,
        "variants": [variant.variant_id for variant in variants],
        "checked_primary_cells": len(primary),
        "eligible_primary_cells": len(eligible_primary),
        "primary_cells": primary_diagnostics,
        "missing_grounding": missing_grounding,
        "documented_exclusions": documented_exclusions,
        "missing_qualified_grounding": [
            diagnostic for diagnostic in primary_diagnostics
            if diagnostic["missing_required_grounding_anchors"]
        ],
        "false_positive_local_name_matches": [
            diagnostic for diagnostic in primary_diagnostics
            if diagnostic["false_positive_local_name_matches"]
        ],
        "registered_abated": REGISTERED_ABLATED,
        "ablated_sources": [],
        "ablated_control_failures": [],
        "registered_preserved": REGISTERED_PRESERVED,
        "preserved_candidates": 0,
        "preserved_sources": [],
        "preserved_control_failures": [],
        "preserved_controls_omitted_reason": None,
        "auto_exclusions": auto_exclusions if auto_exclude_grounding_ineligible else None,
        "eligibility_counts": {
            "checked_primary_cells": len(primary),
            "excluded_grounding_absent": len(auto_exclusions),
            "eligible_primary_cells": len(eligible_primary),
        } if auto_exclude_grounding_ineligible else None,
    }

    if len(eligible_primary) < REGISTERED_ABLATED:
        result["ablated_control_failures"] = [{"reason": "fewer_than_registered_eligible_primary_cells"}]
        raise _preflight_failure(result)

    control_rng = random.Random(seed)
    ablated_sources = control_rng.sample(eligible_primary, REGISTERED_ABLATED)
    result["ablated_sources"] = [cell_key(cell) for cell in ablated_sources]
    diagnostics_by_key = {cell["cell_id"]: diagnostic for cell, diagnostic in zip(primary, primary_diagnostics)}
    result["ablated_control_failures"] = [
        diagnostics_by_key[cell["cell_id"]] for cell in ablated_sources
        if not diagnostics_by_key[cell["cell_id"]]["can_ablate"]
    ]

    ablated_keys = {cell_key(cell) for cell in ablated_sources}
    preserved_pool = [cell for cell in eligible_primary if cell_key(cell) not in ablated_keys]
    if paraphrase_path is None:
        # PREREG.md addendum 15 §15.2: no frozen paraphrase file registered for
        # the domain -> the preserved-control kind is omitted from the plan and
        # the reason is recorded in the manifest (never a preflight failure).
        result["preserved_controls_omitted_reason"] = (
            f"no frozen paraphrase file for domain {domain_name!r}; "
            "preserved controls omitted per PREREG.md addendum 15 §15.2"
        )
    else:
        try:
            paraphrases = _paraphrases(paraphrase_path)
        except SystemExit:
            paraphrases = {}
            result["preserved_control_failures"] = [{"reason": "paraphrases_unavailable"}]
        preserved_candidates = [cell for cell in preserved_pool if cell["cq_id"] in paraphrases]
        result["preserved_candidates"] = len(preserved_candidates)
        if len(preserved_candidates) < REGISTERED_PRESERVED:
            result["preserved_control_failures"].append({
                "reason": "fewer_than_registered_preserved_candidates",
                "available": len(preserved_candidates),
                "required": REGISTERED_PRESERVED,
            })
        else:
            preserved_sources = control_rng.sample(preserved_candidates, REGISTERED_PRESERVED)
            result["preserved_sources"] = [cell_key(cell) for cell in preserved_sources]

    if result["missing_grounding"] or result["ablated_control_failures"] or result["preserved_control_failures"]:
        raise _preflight_failure(result)
    return result


def build_cell_plan(
    rows: list[dict],
    variants: list[Variant],
    seed: int = REGISTERED_SEED,
    paraphrase_path: Path | None = PARAPHRASE_PATH,
    eligibility: dict | None = None,
    exclusion_reasons: dict[tuple[str, str], str] | None = None,
    auto_exclude_grounding_ineligible: bool = False,
) -> list[dict]:
    """Build and deterministically shuffle primary and registered controls.

    Primary cells on the ``DOCUMENTED_EXCLUSIONS`` allowlist (see that
    constant / PREREG.md [2026-09-21] addendum) are excluded from the
    ``"primary"``-kind cells actually placed in the plan -- the confirmatory
    judge is never asked those 28 cells. They were already excluded from the
    ablated/preserved control source pool inside ``eligibility_preflight``.

    When the eligibility result carries §15.2 ``auto_exclusions`` (only ever
    produced by an ``auto_exclude_grounding_ineligible=True`` preflight, see
    that flag / PREREG.md addendum 15 §15.2), those cells are likewise kept
    out of the plan's primaries; with no auto-exclusion mode active the
    filter set is empty and the plan is exactly what it was before.
    """
    reasons = DOCUMENTED_EXCLUSION_REASONS if exclusion_reasons is None else exclusion_reasons
    eligibility = eligibility or eligibility_preflight(
        rows, variants, seed, paraphrase_path, exclusion_reasons,
        auto_exclude_grounding_ineligible=auto_exclude_grounding_ineligible)
    primary = _primary_cells(rows, variants)
    auto_excluded_keys = {entry["cell_id"] for entry in eligibility.get("auto_exclusions") or []}
    eligible_primary = [
        cell for cell in primary
        if (cell["variant"], cell["cq_id"]) not in reasons
        and cell["cell_id"] not in auto_excluded_keys
    ]
    if len(eligible_primary) < REGISTERED_ABLATED:
        raise SystemExit("REFUSING TO RUN: fewer than 24 eligible primary cells are available for ablated controls")
    by_key = {cell_key(cell): cell for cell in primary}
    by_cq = {row["cq_id"]: row for row in rows}
    ablated_sources = [by_key[key] for key in eligibility["ablated_sources"]]
    preserved_omitted = bool(eligibility.get("preserved_controls_omitted_reason"))
    paraphrases = {} if preserved_omitted else _paraphrases(paraphrase_path)
    preserved_sources = [] if preserved_omitted else [by_key[key] for key in eligibility["preserved_sources"]]
    ablated: list[dict] = []
    for source in ablated_sources:
        source_row = by_cq[source["cq_id"]]
        try:
            view = ablate_rendered_view(source["artifact"], source_row)
        except ValueError as exc:
            raise SystemExit(f"REFUSING TO RUN: {exc}") from exc
        ablated.append({
            **source,
            "cell_id": f"ablated_control:{source['variant']}:{source['cq_id']}",
            "cell_kind": "ablated_control", "artifact": view,
            "artifact_digest": hashlib.sha256(view.encode()).hexdigest(),
        })

    preserved = []
    for source in preserved_sources:
        preserved.append({
            **source,
            "cell_id": f"preserved_control:{source['variant']}:{source['cq_id']}",
            "cell_kind": "preserved_control",
            "question": paraphrases[source["cq_id"]],
            # Evidence is intentionally preserved; digest remains that of the
            # actual view sent to the judge.
        })
    plan = _constrained_shuffle(eligible_primary + ablated + preserved, seed)
    expected_preserved = 0 if preserved_omitted else REGISTERED_PRESERVED
    if len(plan) != len(eligible_primary) + REGISTERED_ABLATED + expected_preserved:
        raise AssertionError("cell plan contains duplicate or missing cells")
    return plan


def _valid_score(record: dict) -> bool:
    raw = record.get("judge_response", {}).get("score") if isinstance(record.get("judge_response"), dict) else None
    return bool(record.get("judge_response_parsed")) and isinstance(raw, (int, float)) and int(raw) in range(4)


def _audit_complete(record: dict) -> bool:
    return (
        isinstance(record.get("started_at_utc"), str) and bool(record["started_at_utc"])
        and isinstance(record.get("elapsed_s"), (int, float)) and float(record["elapsed_s"]) >= 0
        and isinstance(record.get("attempt"), int) and record["attempt"] >= 1
        and isinstance(record.get("artifact_digest"), str) and len(record["artifact_digest"]) == 64
        and record.get("cell_kind") in {"primary", "ablated_control", "preserved_control"}
        and isinstance(record.get("variant"), str) and bool(record["variant"])
    )


def _record_key(record: dict) -> str:
    return str(record.get("cell_id") or f"{record.get('cell_kind', 'primary')}:{record.get('variant', 'BRICK_SOURCE')}:{record['cq_id']}")


def _relative(path: Path) -> str:
    """Repo-relative POSIX path for a manifest field, absolute otherwise.

    Manifests are committed as run evidence (see PREREG.md), so an absolute
    path bakes in whichever worktree produced the run -- e.g. a stray
    ``.claude/worktrees/<session-id>/...`` prefix that means nothing once the
    worktree is gone. Mirrors build_repair_candidate.py's REPO/_relative()
    pattern. Falls back to the resolved absolute path when the file lives
    outside this repo (e.g. a manifest supplied from elsewhere on disk).
    """
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _judge_one_cell(
    cell: dict,
    endpoint: str,
    model: str,
    key: str,
    max_tokens: int,
    extra_body: dict | None,
    extra_top_level: dict | None,
    smoke: bool,
    attempt: int,
) -> dict:
    """Score one cell and return its record. Pure w.r.t. shared state -- no
    file or stdout I/O happens here, so it is safe to run from any number of
    concurrent worker threads (call_judge's own shared state, the request
    pacer, is separately locked; see _pace_judge_request).

    Any exception escaping call_judge itself (it already catches broad
    Exception and returns a (_error, False) tuple, so this is a defensive
    second line, not the expected path) is recorded honestly as a failed
    cell rather than being allowed to silently drop the cell from the run or
    crash the whole pool for the other in-flight cells.
    """
    started_at = datetime.now(timezone.utc).isoformat()
    started_mono = time.monotonic()
    judge_kwargs: dict = {}
    if extra_body:
        judge_kwargs["extra_body"] = extra_body
    if extra_top_level:
        judge_kwargs["extra_top_level"] = extra_top_level
    try:
        response, parsed = call_judge(endpoint, model, cell["question"], cell["artifact"], key, max_tokens, **judge_kwargs)
    except Exception as exc:  # noqa: BLE001 -- see docstring: honest failure record, not a crash
        response, parsed = {"_error": repr(exc)}, False
    elapsed = float(time.monotonic() - started_mono)
    raw_score = response.get("score")
    valid = isinstance(raw_score, (int, float)) and int(raw_score) in range(4)
    return {
        "cell_id": cell["cell_id"], "cq_id": cell["cq_id"], "cluster_id": cell["cluster_id"],
        "category": cell["category"], "variant": cell["variant"], "cell_kind": cell["cell_kind"],
        "J": int(raw_score) if valid else 0, "A": 0,
        "judge_response": response, "judge_response_parsed": parsed,
        "SIMULATED": smoke,
        "label_source": "LLM smoke probe" if smoke else "pending human evidence",
        "started_at_utc": started_at, "elapsed_s": elapsed, "attempt": attempt,
        "artifact_digest": cell["artifact_digest"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain", default=DEFAULT_DOMAIN, choices=known_domains(),
                    help="holdout domain (domains/<name>.toml); a domain whose CQ bank is "
                         "not frozen is refused")
    ap.add_argument("--bank", type=Path, default=None,
                    help="CQ bank CSV (default: the domain's bank)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--answer-key", type=Path, default=None,
                    help="optional sealed key path; never read into the run output")
    ap.add_argument("--model", default=None, help=f"judge model (or {MODEL_ENV})")
    ap.add_argument("--endpoint", default=None, help=f"judge base URL (or {ENDPOINT_ENV})")
    ap.add_argument("--variants-manifest", type=Path, default=None,
                    help="manifest containing real rendered variant views (default: the domain's)")
    ap.add_argument("--seed", type=int, default=REGISTERED_SEED)
    ap.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    ap.add_argument("--limit", type=int, default=0,
                    help="score only the first N randomized cells (smoke/SIMULATED mode)")
    ap.add_argument("--smoke", action="store_true",
                    help="run a bounded simulated probe in harness/smoke_run")
    ap.add_argument("--dry-run", action="store_true",
                    help="verify frozen inputs and write the complete cell plan without network calls")
    ap.add_argument("--force", action="store_true",
                    help="allow/resume in an existing output directory")
    args = ap.parse_args()

    domain = load_domain(args.domain)
    is_brick = domain.name == DEFAULT_DOMAIN
    if not is_brick:
        domain.require_frozen_bank()
    if args.bank is None:
        args.bank = ACCESS / "bank/cq_bank_brick_v1.csv" if is_brick else domain.bank_path
    if args.variants_manifest is None:
        args.variants_manifest = DEFAULT_VARIANTS_MANIFEST if is_brick else domain.variants_manifest
    paraphrase_path = PARAPHRASE_PATH if is_brick else domain.paraphrases_path
    exclusion_reasons = None if is_brick else {(v, q): r for v, q, r in domain.documented_exclusions}

    if args.seed != REGISTERED_SEED:
        raise SystemExit(f"REFUSING TO RUN: seed must be {REGISTERED_SEED}, got {args.seed}")
    if args.limit < 0:
        raise SystemExit("REFUSING TO RUN: --limit must be non-negative")
    if args.limit > 0 and not args.smoke and not args.dry_run:
        raise SystemExit("REFUSING TO RUN: --limit requires --smoke (or --dry-run for a plan probe)")
    smoke = args.smoke or bool(args.limit)
    rows, digests = verify_frozen(args.bank, domain)
    # verify_frozen() already refuses any bank that is not the registered
    # 36 rows, so there is no smaller-bank path to accommodate here.  Keeping
    # one would let a corrupted bank silently degrade the registered 252-cell
    # design to a single-variant run instead of failing loudly.
    variants = load_variant_manifest(args.variants_manifest, require_six=not (args.dry_run or smoke))
    eligibility = eligibility_preflight(
        rows, variants, args.seed, paraphrase_path, exclusion_reasons, domain_name=domain.name,
        auto_exclude_grounding_ineligible=domain.auto_exclude_grounding_ineligible)
    plan = build_cell_plan(
        rows, variants, args.seed, paraphrase_path, eligibility, exclusion_reasons,
        auto_exclude_grounding_ineligible=domain.auto_exclude_grounding_ineligible)

    if args.dry_run:
        if args.out is None:
            raise SystemExit("--out is required for a dry run")
        if args.out.exists() and not args.force:
            raise SystemExit(f"REFUSING TO RUN: output directory already exists: {args.out} (use --force)")
        args.out.mkdir(parents=True, exist_ok=True)
        full_plan = plan
        if args.limit:
            plan = plan[:args.limit]
        queue_digest = hashlib.sha256("\n".join(cell_key(cell) for cell in plan).encode()).hexdigest()
        manifest = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "bank_sha256": digests[args.bank.name], "rubric_sha256": digests[RUBRIC_PATH.name],
            "rendering_spec_sha256": digests[RENDERING_PATH.name], "bank_rows": len(rows),
            "seed": args.seed, "SIMULATED": False, "dry_run": True,
            "variant_manifest": _relative(args.variants_manifest),
            "variant_ids": [variant.variant_id for variant in variants],
            "planned_cells": len(plan), "full_planned_cells": len(full_plan),
            "primary_cells": sum(c["cell_kind"] == "primary" for c in plan),
            "ablated_control_cells": sum(c["cell_kind"] == "ablated_control" for c in plan),
            "preserved_control_cells": sum(c["cell_kind"] == "preserved_control" for c in plan),
            "queue_sha256": queue_digest, "results_present": False,
            "documented_exclusions": eligibility["documented_exclusions"],
            "documented_exclusion_count": len(eligibility["documented_exclusions"]),
            "preserved_controls_omitted_reason": eligibility["preserved_controls_omitted_reason"],
        }
        if eligibility.get("auto_exclusions") is not None:
            manifest["eligibility_exclusions"] = eligibility["auto_exclusions"]
            manifest["eligibility_exclusion_count"] = len(eligibility["auto_exclusions"])
            manifest["eligibility_counts"] = eligibility["eligibility_counts"]
        _write_manifest(args.out / "MANIFEST.json", manifest)
        (args.out / "CELL_PLAN.json").write_text(
            json.dumps([{key: cell[key] for key in ("cell_id", "cq_id", "variant", "cell_kind")}
                        for cell in plan], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"dry run ok: {len(plan)} cells planned, frozen inputs verified, manifest written to {args.out}")
        return 0

    endpoint, model = resolve_endpoint_model(args, smoke)
    if MIN_INTERVAL_ENV not in os.environ and host_only(endpoint) in {"localhost", "127.0.0.1"}:
        # A self-hosted local judge has no external rate limit to protect --
        # the 1.0s default exists only for remote, rate-limited APIs (see the
        # comment on JUDGE_MIN_REQUEST_INTERVAL_S above). Only relaxed when
        # the operator has not explicitly set the env var themselves.
        global JUDGE_MIN_REQUEST_INTERVAL_S
        JUDGE_MIN_REQUEST_INTERVAL_S = 0.0
    if smoke:
        out = HERE / "smoke_run"
        if out.exists():
            if not args.force:
                raise SystemExit(
                    f"REFUSING TO RUN: smoke output directory is not empty: {out} (use --force to replace the prior probe)"
                )
            shutil.rmtree(out)
        plan = plan[: args.limit or 2]
    else:
        if args.out is None:
            raise SystemExit("--out is required for a formal holdout run")
        out = args.out
        if out.exists() and not args.force:
            raise SystemExit(
                f"REFUSING TO RUN: formal output directory already exists: {out} (use --force only to resume deliberately)"
            )

    if args.answer_key and args.answer_key.resolve().is_relative_to(out.resolve()):
        raise SystemExit(f"REFUSING TO RUN: answer key is inside output directory: {args.answer_key}")
    key = os.environ.get(API_KEY_ENV)
    if not key:
        raise SystemExit(f"{API_KEY_ENV} is not set; provide it via the environment only (never a flag, default, or file).")
    extra_body_raw = os.environ.get(EXTRA_BODY_ENV)
    extra_body: dict | None = None
    if extra_body_raw:
        try:
            extra_body = json.loads(extra_body_raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{EXTRA_BODY_ENV} is not valid JSON: {exc}")
        if not isinstance(extra_body, dict):
            raise SystemExit(f"{EXTRA_BODY_ENV} must decode to a JSON object")
    extra_top_level_raw = os.environ.get(EXTRA_TOP_LEVEL_ENV)
    extra_top_level: dict | None = None
    if extra_top_level_raw:
        try:
            extra_top_level = json.loads(extra_top_level_raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{EXTRA_TOP_LEVEL_ENV} is not valid JSON: {exc}")
        if not isinstance(extra_top_level, dict):
            raise SystemExit(f"{EXTRA_TOP_LEVEL_ENV} must decode to a JSON object")

    out.mkdir(parents=True, exist_ok=True)
    cells_path = out / "cells.jsonl"
    done: set[str] = set()
    attempts: defaultdict[str, int] = defaultdict(int)
    retained: list[dict] = []
    if cells_path.exists() and not smoke:
        for line in cells_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            key_for_record = _record_key(record)
            attempts[key_for_record] = max(attempts[key_for_record], int(record.get("attempt", 0) or 0))
            if _valid_score(record) and _audit_complete(record):
                done.add(key_for_record)
                retained.append(record)
        # Failed/legacy records are deliberately removed before retry, but
        # their attempt number above is retained so G7 can audit retries.
        if retained or cells_path.read_text(encoding="utf-8").strip():
            cells_path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in retained), encoding="utf-8")
        print(f"resuming: {len(done)} cell(s) already scored", file=sys.stderr)

    # Import the registered reference renderer only after all frozen-file guards.
    from run_simulated import schema_view
    # The variant manifest already supplied the views.  TTL_PATH is only used
    # as the compatibility fallback for an explicit empty cache in old probes.
    _ = schema_view  # keep the frozen renderer import guard explicit
    schema_sha = hashlib.sha256("\n".join(f"{v.variant_id}:{hashlib.sha256(v.view.encode()).hexdigest()}" for v in variants).encode()).hexdigest()
    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "bank_sha256": digests[args.bank.name],
        "rubric_sha256": digests[RUBRIC_PATH.name], "rendering_spec_sha256": digests[RENDERING_PATH.name],
        "bank_rows": len(rows), "seed": args.seed, "judge_model": model,
        "endpoint_host": host_only(endpoint), "temperature": 0.0, "max_tokens": args.max_tokens,
        "judge_extra_body": extra_body,
        "judge_extra_top_level_fields": extra_top_level,
        "SIMULATED": smoke, "smoke": smoke, "results_present": False,
        "variant_manifest": _relative(args.variants_manifest),
        "variant_ids": [variant.variant_id for variant in variants],
        "planned_cells": len(plan), "primary_cells": sum(c["cell_kind"] == "primary" for c in plan),
        "ablated_control_cells": sum(c["cell_kind"] == "ablated_control" for c in plan),
        "preserved_control_cells": sum(c["cell_kind"] == "preserved_control" for c in plan),
        "variant_views_sha256": schema_sha,
        "queue_sha256": hashlib.sha256("\n".join(cell_key(cell) for cell in plan).encode()).hexdigest(),
        "documented_exclusions": eligibility["documented_exclusions"],
        "documented_exclusion_count": len(eligibility["documented_exclusions"]),
        "preserved_controls_omitted_reason": eligibility["preserved_controls_omitted_reason"],
    }
    if eligibility.get("auto_exclusions") is not None:
        manifest["eligibility_exclusions"] = eligibility["auto_exclusions"]
        manifest["eligibility_exclusion_count"] = len(eligibility["auto_exclusions"])
        manifest["eligibility_counts"] = eligibility["eligibility_counts"]
    _write_manifest(out / "MANIFEST.json", manifest)

    # [2026-09-21] Concurrent judge dispatch (JUDGE_CONCURRENCY workers,
    # default 4; PREREG.md's qwen-next-flash addendum). Each cell is still
    # scored exactly once -- `pending` is the fixed set of not-yet-done plan
    # cells computed up front, and every cell in it gets exactly one
    # executor.submit(). What changes vs. the previous sequential loop is
    # only *when* results land: as each worker finishes, not necessarily in
    # `plan` order. The one piece of state every worker thread touches is
    # the output file, so all writes (and the matching stdout progress line)
    # are serialized under `write_lock` -- each worker's full record is
    # formed in its own thread (_judge_one_cell) and handed to the lock as a
    # single, already-complete JSON string, so cells.jsonl can never see a
    # partial or interleaved line. `attempts[key_for_cell] + 1` is read once
    # per cell before submission from the (now read-only for the rest of
    # this run) resume-scan dict, so it is exactly the same value each cell
    # would have gotten from the old sequential loop.
    pending = [cell for cell in plan if cell_key(cell) not in done]
    write_lock = threading.Lock()
    with cells_path.open("a", encoding="utf-8") as fh:
        if pending:
            with ThreadPoolExecutor(max_workers=JUDGE_CONCURRENCY) as executor:
                future_to_cell = {
                    executor.submit(
                        _judge_one_cell, cell, endpoint, model, key, args.max_tokens,
                        extra_body, extra_top_level, smoke, attempts[cell_key(cell)] + 1,
                    ): cell
                    for cell in pending
                }
                for future in as_completed(future_to_cell):
                    record = future.result()
                    with write_lock:
                        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                        fh.flush()
                        print(
                            f"{record['cell_id']}: parsed={record['judge_response_parsed']} "
                            f"content_null={record['judge_response'].get('_error') == 'content is null'}"
                        )

    manifest["results_present"] = True
    manifest["completed_cells"] = sum(
        1 for line in cells_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    _write_manifest(out / "MANIFEST.json", manifest)
    print(f"wrote {cells_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
