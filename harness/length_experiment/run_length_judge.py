#!/usr/bin/env python3
"""Experiment 3: score the length-experiment inputs with the registered judge call.

Reuses run_holdout.call_judge (via run_holdout._judge_one_cell): same RUBRIC,
temperature 0, max_tokens 1024, json_object, pacing and 429 retry.  Output
``cells_length.jsonl`` follows the cells.jsonl schema plus ``condition`` and
``pair_id`` (= "<variant>:<cq_id>", the join key across conditions).

``--dry-run`` makes no network call and needs no API key: it prints the input
token totals per condition x variant (estimated tokens = chars / 4, ceil).
A real run is refused unless addendum 17 is frozen AND the caller says so with
``--confirm-addendum17-frozen`` (judge and budget are an author decision).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HERE))

import run_holdout as rh  # noqa: E402
from make_inputs import CONDITIONS, VARIANT_IDS, est_tokens, load_questions, BANK_PATH  # noqa: E402

MAX_WORKERS = 3
DESIGNS = ("full", "reduced", "registered-all", "luna-full-BF")
# full: 6x36x3 ; reduced: 'full' condition on A only ;
# registered-all (addendum 22): limited+subgraph on A-F with the REGISTERED holdout judge
# (the full views are reused from real_run/cells.jsonl, never re-sent)
REGISTERED_ALL_CONDITIONS = ("limited", "subgraph")
# luna-full-BF (addendum 23): the FULL rendering views of B-F with the luna substitute judge, via <internal-proxy>.
# Variants are processed one after another in this order (all cells of B, then C, ...), so that a
# stop (budget / quota) keeps whole variants.
LUNA_MODEL = "gpt-5.6-luna"
LUNA_HOSTS = ("localhost", "127.0.0.1")
LUNA_VARIANT_ORDER = ("B", "C", "D", "E", "F")
LUNA_OUT = HERE / "luna_full_r35" / "cells_luna_full_r35.jsonl"
LUNA_TOKEN_BUDGET = 100_000_000
QUOTA_RE = re.compile(r"HTTPError\D{0,3}(402|403|429)\b")
REGISTERED_MODEL = "gemini-3.6-flash"
REGISTERED_HOST = "generativelanguage.googleapis.com"
EXPECTED_MANIFEST_SHA256 = "46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32"
LEGACY_OUT = HERE / "cells_length.jsonl"
REGISTERED_OUT = HERE / "registered_r34" / "cells_registered_r34.jsonl"
HOLDOUT_CELLS = HARNESS / "real_run" / "cells.jsonl"
OUT_NAME = "cells_length.jsonl"
TOKEN_BUDGET = 7_000_000  # addendum 17: cumulative estimated input tokens; abort above this
PROGRESS_EVERY = 100


def load_manifest(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def select(manifest: list[dict], conditions, variants, design: str,
           include_excluded: bool) -> list[dict]:
    out = []
    for r in manifest:
        if r["condition"] not in conditions or r["variant"] not in variants:
            continue
        if design == "reduced" and r["condition"] == "full" and r["variant"] != "A":
            continue
        if design == "registered-all" and r["condition"] not in REGISTERED_ALL_CONDITIONS:
            continue
        if design == "luna-full-BF" and not (r["condition"] == "full" and r["variant"] in LUNA_VARIANT_ORDER):
            continue
        if r["documented_exclusion"] and not include_excluded:
            continue
        out.append(r)
    return out


def overhead_chars(question: str) -> int:
    """Characters of the request that are not the artifact (rubric + framing + question)."""
    return len(rh.RUBRIC) + len("ARTIFACT:\n") + len("\n\nQUESTION: ") + len(question)


def dry_run_table(selected: list[dict], questions: dict[str, str]) -> dict:
    """Token totals per condition x variant; not_applicable rows are not sent."""
    table: dict[tuple[str, str], dict] = {}
    for r in selected:
        cell = table.setdefault((r["condition"], r["variant"]),
                                {"calls": 0, "not_applicable": 0, "artifact_chars": 0,
                                 "artifact_tokens": 0, "total_tokens": 0})
        if r["status"] != "ok":
            cell["not_applicable"] += 1
            continue
        cell["calls"] += 1
        cell["artifact_chars"] += r["chars"]
        cell["artifact_tokens"] += r["est_tokens"]
        cell["total_tokens"] += est_tokens(r["chars"] + overhead_chars(questions[r["cq_id"]]))
    return table


def print_table(table: dict) -> None:
    print("condition variant calls n/a  mean_chars  artifact_tokens  total_input_tokens")
    for (cond, var), c in sorted(table.items()):
        mean = c["artifact_chars"] // c["calls"] if c["calls"] else 0
        print(f"{cond:9s} {var:7s} {c['calls']:5d} {c['not_applicable']:3d} {mean:11d} "
              f"{c['artifact_tokens']:16d} {c['total_tokens']:19d}")
    by_cond: dict[str, list[int]] = {}
    for (cond, _), c in table.items():
        t = by_cond.setdefault(cond, [0, 0, 0, 0])
        t[0] += c["calls"]; t[1] += c["artifact_chars"]; t[2] += c["artifact_tokens"]; t[3] += c["total_tokens"]
    for cond, t in sorted(by_cond.items()):
        print(f"TOTAL {cond:9s} calls={t[0]} mean_chars={t[1] // max(t[0], 1)} "
              f"artifact_tokens={t[2]} total_input_tokens={t[3]}")
    print(f"TOTAL ALL calls={sum(t[0] for t in by_cond.values())} "
          f"total_input_tokens={sum(t[3] for t in by_cond.values())}")


def artifact_text(record: dict) -> str:
    return (ACCESS / record["path"]).read_text(encoding="utf-8") if not Path(record["path"]).is_absolute() \
        else Path(record["path"]).read_text(encoding="utf-8")


def is_quota_error(rec: dict) -> bool:
    """True when a record failed with an HTTP 402/403/429 (429 is already retried inside call_judge,
    so a 429 here has persisted). These stop the luna-full-BF run gracefully."""
    jr = rec.get("judge_response") or {}
    return bool(QUOTA_RE.search(str(jr.get("_error", ""))))


def is_context_error(rec: dict) -> bool:
    jr = rec.get("judge_response") or {}
    txt = (str(jr.get("_error", "")) + " " + str(jr.get("_error_body", ""))).lower()
    return "HTTPError" in str(jr.get("_error", "")) and "400" in str(jr.get("_error", "")) and "context" in txt


def order_cells(cells: list[dict], design: str, seed: int) -> list[dict]:
    """Seeded shuffle; luna-full-BF: variant-major (B first, then C, D, E, F), shuffled within a variant."""
    random.Random(seed).shuffle(cells)
    if design == "luna-full-BF":
        rank = {v: i for i, v in enumerate(LUNA_VARIANT_ORDER)}
        cells.sort(key=lambda c: rank[c["variant"]])  # stable: keeps the shuffled order inside a variant
    return cells


def build_cells(selected: list[dict], questions: dict[str, dict], seed: int, design: str = "") -> list[dict]:
    cells = []
    for r in selected:
        if r["status"] != "ok":
            continue
        q = questions[r["cq_id"]]
        cells.append({
            "cell_id": f"length:{r['condition']}:{r['variant']}:{r['cq_id']}",
            "pair_id": f"{r['variant']}:{r['cq_id']}", "condition": r["condition"],
            "cq_id": r["cq_id"], "cluster_id": q["cluster_id"], "category": q["category"],
            "question": q["question"], "variant": r["variant"], "cell_kind": "primary",
            "artifact_path": r["path"], "artifact_digest": r["sha256"], "input_chars": r["chars"],
        })
    return order_cells(cells, design, seed)


def _done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    done = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rh._valid_score(rec):
                done.add(rec["cell_id"])
    return done


def sha256_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def holdout_reuse_check(manifest: list[dict], holdout_cells: Path) -> dict:
    """Reused full-view cells: count of valid primary holdout cells and digest agreement
    with the manifest's full-condition source view (no network, no scoring)."""
    full_sha = {(r["variant"], r["cq_id"]): r["sha256"] for r in manifest
                if r["condition"] == "full" and r["status"] == "ok" and not r["documented_exclusion"]}
    n_valid = n_match = n_extra = 0
    seen = set()
    for line in holdout_cells.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("cell_kind") != "primary" or not rh._valid_score(rec):
            continue
        key = (rec["variant"], rec["cq_id"])
        if key not in full_sha:
            n_extra += 1
            continue
        n_valid += 1
        seen.add(key)
        n_match += rec.get("artifact_digest") == full_sha[key]
    return {"manifest_full_pairs": len(full_sha), "holdout_valid_primary": n_valid,
            "digest_matches_manifest": n_match, "holdout_not_in_manifest": n_extra,
            "manifest_pairs_without_holdout_cell": len(set(full_sha) - seen)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", default=None, help=f"judge base URL (or {rh.ENDPOINT_ENV})")
    ap.add_argument("--model", default=None, help=f"judge model (or {rh.MODEL_ENV})")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--variants", default=",".join(VARIANT_IDS))
    ap.add_argument("--design", choices=DESIGNS, default="full")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-excluded", action="store_true",
                    help="also send the 28 documented-exclusion (variant, CQ) pairs of the holdout")
    ap.add_argument("--manifest", type=Path, default=HERE / "inputs" / "manifest.jsonl")
    ap.add_argument("--bank", type=Path, default=BANK_PATH)
    ap.add_argument("--out", type=Path, default=None,
                    help="default cells_length.jsonl; registered-all: registered_r34/cells_registered_r34.jsonl")
    ap.add_argument("--max-tokens", type=int, default=rh.DEFAULT_MAX_TOKENS)
    ap.add_argument("--seed", type=int, default=rh.REGISTERED_SEED)
    ap.add_argument("--confirm-addendum17-frozen", action="store_true")
    ap.add_argument("--token-budget", type=int, default=None,
                    help=f"cumulative estimated input tokens; default {TOKEN_BUDGET} "
                         f"({LUNA_TOKEN_BUDGET} for luna-full-BF)")
    ap.add_argument("--confirm-addendum23-frozen", action="store_true",
                    help="required for --design luna-full-BF (PREREG addendum 23 frozen and tagged)")
    ap.add_argument("--confirm-addendum22-frozen", action="store_true",
                    help="required for --design registered-all (PREREG addendum 22 frozen and tagged)")
    ap.add_argument("--holdout-cells", type=Path, default=HOLDOUT_CELLS,
                    help="registered-all: holdout cells whose full views are reused, not re-run")
    a = ap.parse_args(argv)

    if not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit(f"REFUSING TO RUN: --workers must be 1..{MAX_WORKERS}, got {a.workers}")
    registered = a.design == "registered-all"
    luna = a.design == "luna-full-BF"
    if luna and a.conditions == ",".join(CONDITIONS):
        a.conditions = "full"
    if luna and a.variants == ",".join(VARIANT_IDS):
        a.variants = ",".join(LUNA_VARIANT_ORDER)
    if registered and a.conditions == ",".join(CONDITIONS):
        a.conditions = ",".join(REGISTERED_ALL_CONDITIONS)
    if a.out is None:
        a.out = REGISTERED_OUT if registered else (LUNA_OUT if luna else HERE / OUT_NAME)
    if a.out.resolve() == LEGACY_OUT.resolve() and (registered or luna):
        raise SystemExit("REFUSING TO RUN: this design must not write cells_length.jsonl (existing luna results)")
    conditions = tuple(c for c in a.conditions.split(",") if c)
    variants = tuple(v for v in a.variants.split(",") if v)
    bad = [c for c in conditions if c not in CONDITIONS]
    if bad:
        raise SystemExit(f"unknown condition(s): {bad}")
    token_budget = a.token_budget if a.token_budget is not None else (LUNA_TOKEN_BUDGET if luna else TOKEN_BUDGET)
    manifest = load_manifest(a.manifest)
    questions = {r["cq_id"]: r for r in load_questions(a.bank)}
    selected = select(manifest, conditions, variants, a.design, a.include_excluded)

    if a.dry_run:
        print(f"design={a.design} conditions={','.join(conditions)} variants={','.join(variants)} "
              f"include_excluded={a.include_excluded}")
        print_table(dry_run_table(selected, {k: v["question"] for k, v in questions.items()}))
        if registered:
            got = sha256_file(a.manifest)
            print(f"manifest sha256 {got} "
                  f"{'MATCHES' if got == EXPECTED_MANIFEST_SHA256 else 'MISMATCH vs'} {EXPECTED_MANIFEST_SHA256}")
            print("holdout full-view reuse:", json.dumps(holdout_reuse_check(manifest, a.holdout_cells)))
            print(f"out={a.out}  (existing valid cells there are skipped on resume)")
        if luna:
            got = sha256_file(a.manifest)
            print(f"manifest sha256 {got} "
                  f"{'MATCHES' if got == EXPECTED_MANIFEST_SHA256 else 'MISMATCH vs'} {EXPECTED_MANIFEST_SHA256}")
            tot = sum(c["total_tokens"] for c in dry_run_table(selected, {k: v["question"] for k, v in questions.items()}).values())
            print(f"token budget {token_budget}; estimated {tot}; {'FITS' if tot <= token_budget else 'EXCEEDS'}; "
                  f"out={a.out}")
        return 0

    if registered:
        if not a.confirm_addendum22_frozen:
            raise SystemExit("REFUSING TO RUN: PREREG addendum 22 is not frozen; pass "
                             "--confirm-addendum22-frozen only after the freeze commit and tag.")
        if sha256_file(a.manifest) != EXPECTED_MANIFEST_SHA256:
            raise SystemExit("REFUSING TO RUN: inputs manifest sha256 differs from the registered value")
    elif luna:
        if not a.confirm_addendum23_frozen:
            raise SystemExit("REFUSING TO RUN: PREREG addendum 23 is not frozen; pass "
                             "--confirm-addendum23-frozen only after the freeze commit and tag.")
        if sha256_file(a.manifest) != EXPECTED_MANIFEST_SHA256:
            raise SystemExit("REFUSING TO RUN: inputs manifest sha256 differs from the registered value")
    elif not a.confirm_addendum17_frozen:
        raise SystemExit("REFUSING TO RUN: PREREG addendum 17 is not frozen. Judge, budget and design are "
                         "author decisions; pass --confirm-addendum17-frozen only after the freeze commit.")
    if a.seed != rh.REGISTERED_SEED:
        raise SystemExit(f"REFUSING TO RUN: seed must be {rh.REGISTERED_SEED}")
    endpoint, model = rh.resolve_endpoint_model(a, smoke=False)
    if registered:
        from urllib.parse import urlparse as _up
        if model != REGISTERED_MODEL or _up(endpoint).hostname != REGISTERED_HOST:
            raise SystemExit(f"REFUSING TO RUN: registered-all requires {REGISTERED_MODEL} on {REGISTERED_HOST}")
    if luna:
        from urllib.parse import urlparse as _up2
        if model != LUNA_MODEL or _up2(endpoint).hostname not in LUNA_HOSTS:
            raise SystemExit(f"REFUSING TO RUN: luna-full-BF requires {LUNA_MODEL} on a local <internal-proxy> endpoint")
    key = os.environ.get(rh.API_KEY_ENV)
    if not key:
        raise SystemExit(f"{rh.API_KEY_ENV} is not set")
    extra_body = json.loads(os.environ[rh.EXTRA_BODY_ENV]) if os.environ.get(rh.EXTRA_BODY_ENV) else None
    extra_top = (json.loads(os.environ[rh.EXTRA_TOP_LEVEL_ENV])
                 if os.environ.get(rh.EXTRA_TOP_LEVEL_ENV) else None)
    cells = build_cells(selected, questions, a.seed, a.design)
    done = _done_ids(a.out)
    todo = [c for c in cells if c["cell_id"] not in done]
    print(f"{len(cells)} cells, {len(done)} already scored, {len(todo)} to run, workers={a.workers}")
    a.out.parent.mkdir(parents=True, exist_ok=True)

    lock = threading.Lock()
    # resume: tokens already spent on valid cells count toward the budget; failed calls do not
    done_tokens = sum(est_tokens(c["input_chars"] + overhead_chars(c["question"]))
                      for c in cells if c["cell_id"] in done)
    state = {"calls": 0, "tokens": done_tokens, "failures": 0, "abort": False, "abort_reason": None,
             "context_errors": 0}
    progress = a.out.parent / "progress.log"
    started_utc = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()

    def run(cell: dict) -> dict | None:
        if state["abort"]:
            return None
        path = Path(cell["artifact_path"])
        full = path if path.is_absolute() else ACCESS / path
        job = {**cell, "artifact": full.read_text(encoding="utf-8")}
        rec = rh._judge_one_cell(job, endpoint, model, key, a.max_tokens, extra_body, extra_top, False, 1)
        rec.update({"condition": cell["condition"], "pair_id": cell["pair_id"],
                    "input_chars": cell["input_chars"]})
        toks = est_tokens(cell["input_chars"] + overhead_chars(cell["question"]))
        rec["est_input_tokens"] = toks
        with lock:
            state["calls"] += 1
            if rh._valid_score(rec):
                state["tokens"] += toks
            else:
                state["failures"] += 1
            if state["tokens"] > token_budget:
                state["abort"] = True
                state["abort_reason"] = state["abort_reason"] or "token_budget"
            if luna and not rh._valid_score(rec):
                if is_quota_error(rec):
                    state["abort"] = True
                    state["abort_reason"] = state["abort_reason"] or "quota_error"
                elif is_context_error(rec):
                    state["context_errors"] += 1
            if state["calls"] % PROGRESS_EVERY == 0 or state["abort"]:
                with progress.open("a", encoding="utf-8") as pf:
                    pf.write(f"{datetime.now(timezone.utc).isoformat()} calls={state['calls']} "
                             f"est_input_tokens={state['tokens']} failures={state['failures']} "
                             f"abort={state['abort']}\n")
        return rec

    # groups: luna-full-BF runs one variant at a time (B first); other designs are a single group
    if luna:
        groups = [[c for c in todo if c["variant"] == v] for v in LUNA_VARIANT_ORDER]
    else:
        groups = [todo]
    progress_md = a.out.parent / "PROGRESS.md"
    for g, group in enumerate(groups):
        if state["abort"]:
            break
        t_g = time.monotonic()
        before_fail = state["failures"]
        with a.out.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=a.workers) as pool:
            futures = [pool.submit(run, c) for c in group]
            for f in as_completed(futures):
                rec = f.result()
                if rec is not None:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
        if luna and group:
            v = group[0]["variant"]
            n_ok = len(_done_ids(a.out) & {c["cell_id"] for c in cells if c["variant"] == v})
            n_all = sum(1 for c in cells if c["variant"] == v)
            with progress_md.open("a", encoding="utf-8") as pf:
                pf.write(f"- {datetime.now(timezone.utc).isoformat()} variant {v}: cells {n_ok}/{n_all} valid, "
                         f"failures_this_variant={state['failures'] - before_fail}, "
                         f"est_input_tokens_so_far={state['tokens']}, variant_elapsed_s={round(time.monotonic() - t_g)}, "
                         f"total_elapsed_s={round(time.monotonic() - t0)}, abort={state['abort']} "
                         f"({state['abort_reason']})\n")
    from urllib.parse import urlparse
    manifest_out = {
        "judge_model": model, "endpoint_host_kind": urlparse(endpoint).hostname,
        "design": a.design, "calls_this_run": state["calls"], "cells_planned": len(cells),
        "est_input_tokens_this_run": state["tokens"], "token_budget": token_budget,
        "failures_this_run": state["failures"], "aborted_over_budget": state["abort"],
        "abort_reason": state["abort_reason"], "context_errors": state["context_errors"],
        "started_utc": started_utc, "ended_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_s": round(time.monotonic() - t0, 1), "workers": a.workers,
        "extra_top_level_fields": extra_top, "extra_body": extra_body, "seed": a.seed,
        "token_note": "estimated tokens = ceil(chars/4), not tokenizer counts",
    }
    (a.out.parent / (f"MANIFEST_run_{started_utc[:19].replace(':', '')}.json" if luna else "MANIFEST_length.json")).write_text(json.dumps(manifest_out, indent=2), encoding="utf-8")
    print(json.dumps(manifest_out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
