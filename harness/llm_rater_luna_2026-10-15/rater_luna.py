#!/usr/bin/env python3
"""LLM-rater (luna) labels for the primary holdout cells -- PREREG addendum 24.

AI-generated code: review before use.  Exploratory (post hoc).

The rater sees exactly what a human rater sees on the labeling site, minus the
site mechanics: the rater instructions (rubric, anchors, legend, examples),
the category label, the question (and its reference Korean translation), and
the full rendered view text of that cell.  It never sees judge scores, judge
spans, variant names, view file names, AI drafts, AH labels, the independent
rater's labels or any human multirater label.

Sub-commands
  estimate   chars/4 input-token estimate for the pilot and for all 188 cells
  run        call <internal-proxy> gpt-5.6-luna; resumable jsonl, skips cells already valid
  analyze    agreement tables (pilot; full when all 188 cells are valid)

Read-only inputs (never copied, never committed): the site key
(annotation/multirater_2026-10/site_key_2026-10-13.csv) and the rater views
(annotation/multirater_2026-10/views_for_raters.zip, read in place).  The
output jsonl stores only the original cell id (primary:<variant>:<CQ>), never
the opaque site id, so the key mapping is not reproduced in the repository.
The <internal-proxy> proxy needs no external key; HOLDOUT_JUDGE_API_KEY is used if set and
a fixed local placeholder otherwise.  No key is ever printed or written.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import run_holdout as rh  # noqa: E402  (pacing + retry constants)

MR = ACCESS / "annotation" / "multirater_2026-10"
SITE_CELLS = MR / "labeling_site" / "data" / "cells.json"
VIEWS_MANIFEST = MR / "labeling_site" / "data" / "views_manifest.json"
SITE_KEY = MR / "site_key_2026-10-13.csv"
VIEWS_ZIP = MR / "views_for_raters.zip"
HUMAN_EXPORT = MR / "human_labels_export_2026-10-15.csv"
AH_LABELS = Path.home() / "labels" / "locked" / "2026-10-09" / "primary_working.csv"
INDEP_LABELS = ACCESS / "annotation" / "second_pass_2026-10-13" / "v3" / "labels_for_analysis_v3.csv"
HOLDOUT_CELLS = ACCESS / "harness" / "real_run" / "cells.jsonl"

ENDPOINT = "http://localhost:PORT/v1"
MODEL = "gpt-5.6-luna"
TEMPERATURE = 0.0
SEED = 20260913
MAX_TOKENS = 2048
TOKEN_BUDGET = 6_000_000
MAX_WORKERS = 3
HTTP_TIMEOUT_S = 900
LABEL_SOURCE_NAME = "LLM-rater (luna) labels"

RATER_PROMPT = """당신은 온톨로지 자료가 질문에 답할 수 있는지 확인하는 평가자입니다. 아래 판정 기준은 사람 평가자가 라벨링 사이트에서 받는 기준과 같습니다(사이트 조작 방법만 뺐습니다). 질문 하나와 그 질문에 딸린 자료(텍스트) 하나를 받습니다. 자료에서 답의 근거를 찾아 판정해 주세요.

## 무엇을 판정하나요
각 질문마다 두 가지를 서로 독립적으로 입력합니다.
- S: 제공 자료 안에 글자 그대로의 구간이 질문의 답을 뒷받침하는가 (있다 / 없다)
- R: 자료가 질문에 얼마나 답하는가 (0~3점)
자료 밖 지식, 외부 검색, 본인의 배경지식으로 빈틈을 채우지 마세요.

## S와 R은 어떻게 다른가요
S는 '인용할 수 있는 문장이 있는가'를 묻고, R은 '자료 전체가 답으로 충분한가'를 묻습니다. S를 먼저 정하고, R은 S에 맞추지 말고 따로 판단합니다.
아래는 이 작업의 자료와 무관한 가상 예시(도서관 시스템)입니다.
Reservation | A request to hold an Item for a Member.
Loan | A borrowing of one Item by one Member for a fixed period.
Member | A person registered to borrow Items.
Event
Item
- 질문 A: What is a Reservation? — 첫 줄이 직접 정의합니다. S=1이고, 인용할 구간은 첫 줄입니다. 질문에 완전히 답하므로 R은 3입니다.
- 질문 B: Is Loan a subclass of Event? — Loan과 Event라는 이름은 보이지만 둘의 포함 관계를 말하는 문장은 없습니다. 주제가 가까운 것만으로는 근거가 아니므로 S=0입니다. 개념은 있고 핵심 관계가 빠졌으므로 R은 1에 가깝습니다. S=0이면 근거 칸을 비우고 메모에 이유를 씁니다.

## S: 근거 지지 여부 (0/1)
연구 프로토콜(PROTOCOL.md) 원문:
"Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, preserving punctuation and whitespace where practical; if unsupported, leave the span empty and explain briefly why no supporting span exists. Do not infer support from the graph, external sources, or the annotator's knowledge."
제공 자료 안의 글자 그대로의 구간이 질문의 답을 뒷받침할 때만 S=1(근거 있음)입니다. 아니면 S=0(근거 없음)입니다. S=1이면 가장 짧은 충분 구간을 근거 칸에 복사하고, S=0이면 근거 칸을 비우고 메모에 이유를 짧게 씁니다. 자료 밖 지식, 외부 출처, 그래프 추론으로 채우지 않습니다.

## R: 자료가 질문에 답하는 정도 (0–3)
- 0  관련된 개념이나 관계가 없다.
- 1  부분적: 개념은 있지만 핵심 관계나 계층이 빠져 있다.
- 2  대체로: 핵심 개념과 관계가 있고 사소한 빈틈만 있다.
- 3  완전: 질문에 완전히 답한다.
R은 S를 정한 뒤에 입력하되, S 값에 맞추지 말고 자료의 답변 충분성만 보고 매깁니다. S=0인데 R이 높거나 그 반대도 가능합니다.

## 경계 예시(안내서 기준)
- 관련 개념은 있지만 질문이 묻는 핵심 관계나 계층을 문장으로 말하지 않으면 S=0입니다. 주제가 가깝다는 것만으로는 근거가 아닙니다(R 앵커 1의 '부분적'에 해당).
- 핵심 개념과 요구된 관계가 있고 작은 세부만 빠졌다면 S=1이며, 답을 뒷받침하는 구간을 인용합니다(R 앵커 2의 '대체로'에 해당).
- 개념과 관계·정의가 질문에 직접 답하도록 적혀 있으면 S=1이며, 가장 짧은 충분 구간을 인용합니다(R 앵커 3의 '완전'에 해당).
확신이 없으면 자료를 머릿속으로 보충하지 마세요. 글자 그대로 인용할 충분한 구간이 없으면 S=0으로 하고, 불확실한 이유를 메모에 적습니다.

## 근거 구간은 어떻게 고르나요
- 자료에서 질문의 핵심 단어를 찾습니다(대소문자 구분 없음).
- 답을 뒷받침하는 가장 짧은 구간을 고릅니다.
- 관계는 기호로 적혀 있어요. 'A < B'는 A가 B의 하위 클래스, 'IND X a T'는 X가 T의 사례라는 뜻이에요.
- 구두점과 공백은 가능한 한 원문 그대로 둡니다. 직접 고쳐 쓰면 '원문에서 찾을 수 없음'으로 표시됩니다.

## 자료 읽는 법 (기호 설명)
- `A | 이름 < B,C` : A는 B와 C의 하위 클래스(subClassOf)예요. 예: `Building < …#Location`은 Building이 Location의 하위 클래스라는 뜻.
- `:: 문장` : 그 항목의 정의·설명이에요.
- `IND X | 이름 a T` : X는 T의 사례(인스턴스, type)예요.
- `OP P dom:D rng:R inv:I` : 속성 P의 정의역(D)·치역(R)·역관계(I)예요. DP는 값 속성이에요.
- `{p=o; …}` : 그 밖의 관계(술어 p의 값 o)예요.

## 지켜 주세요
- 파이프라인·모델 출력, 점수, 정답 후보를 알아내려 하지 않습니다. 자료 이름이나 내용으로 어떤 변형인지 추측하지 않습니다.

## 출력 형식
다른 글 없이 JSON 객체 하나만 출력합니다.
{"S": 0 또는 1, "R": 0~3의 정수, "span": "S=1이면 자료 원문 그대로의 가장 짧은 충분 구간, S=0이면 빈 문자열", "note": "S=0이면 근거가 없는 이유(필수), S=1이면 필요할 때만 짧은 메모"}"""

RATER_PROMPT_SHA256 = hashlib.sha256(RATER_PROMPT.encode("utf-8")).hexdigest()


def user_message(view_text: str, cell: dict) -> str:
    parts = ["자료:", view_text, "", f"범주: {cell['catKo']}", f"질문: {cell['q']}"]
    if cell.get("qko"):
        parts.append(f"참고 번역: {cell['qko']}")
    return "\n".join(parts)


# ---------------------------------------------------------------- inputs

def load_site():
    """Return {original_cell_id: site cell dict} (the opaque id stays in memory)."""
    cells = json.loads(SITE_CELLS.read_text(encoding="utf-8"))
    key = {}
    with SITE_KEY.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["kind"] == "cell":
                key[row["opaque"]] = row["original"]
    out = {}
    for c in cells:
        orig = key[c["id"]]
        if orig in out:
            raise SystemExit(f"duplicate original id {orig}")
        out[orig] = c
    if len(out) != 188:
        raise SystemExit(f"expected 188 cells, got {len(out)}")
    return out, key


def load_views() -> dict[str, str]:
    manifest = json.loads(VIEWS_MANIFEST.read_text(encoding="utf-8"))
    views = {}
    with zipfile.ZipFile(VIEWS_ZIP) as zf:
        for name, meta in manifest.items():
            data = zf.read(f"views/{name}")
            if hashlib.sha256(data).hexdigest() != meta["sha256"]:
                raise SystemExit(f"view {name}: sha256 mismatch")
            views[name] = data.decode("utf-8")
    return views


def human_labels(key: dict) -> list[dict]:
    with HUMAN_EXPORT.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [{"rater": r["rater"], "cell_id": key[r["cell_id"]], "R": int(r["R"]),
             "S": int(r["S"]), "span": r["span"]} for r in rows]


def pilot_ids(key: dict) -> list[str]:
    return sorted({h["cell_id"] for h in human_labels(key)})


def est_tokens(cell: dict, views: dict) -> int:
    n = len(RATER_PROMPT) + len(user_message(views[cell["view"]], cell))
    return -(-n // 4)


# ---------------------------------------------------------------- calls

STOP = threading.Event()
STOP_REASON: list[str] = []
_write_lock = threading.Lock()


def parse_content(content: str):
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None, "no JSON object"
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None, "JSON parse failed"
    if not isinstance(obj, dict):
        return None, "not an object"
    try:
        s, r = int(obj.get("S")), int(obj.get("R"))
    except (TypeError, ValueError):
        return None, "S/R not integers"
    if s not in (0, 1) or r not in (0, 1, 2, 3):
        return None, "S/R out of range"
    return {"S": s, "R": r, "span": str(obj.get("span") or ""), "note": str(obj.get("note") or "")}, None


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def call_rater(system: str, user: str, key: str):
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": TEMPERATURE,
        "seed": SEED,
        "max_tokens": MAX_TOKENS,
        "response_format": {"type": "text"},
    }).encode()
    req = urllib.request.Request(f"{ENDPOINT}/chat/completions", data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    for attempt in range(rh.JUDGE_MAX_RETRIES + 1):
        if STOP.is_set():
            return {"_error": "stopped before call"}
        rh._pace_judge_request()
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_S) as resp:
                payload = json.loads(resp.read())
            msg = payload.get("choices", [{}])[0].get("message", {})
            return {"content": msg.get("content"), "usage": payload.get("usage"),
                    "model_returned": payload.get("model"), "attempt": attempt + 1}
        except urllib.error.HTTPError as exc:
            try:
                snippet = exc.read().decode("utf-8", "replace")[:500]
            except Exception:
                snippet = ""
            if exc.code in (402, 403):
                STOP.set(); STOP_REASON.append(f"HTTP {exc.code}")
                return {"_error": f"HTTP {exc.code}", "_error_body": snippet}
            if exc.code != 429:
                return {"_error": f"HTTP {exc.code}", "_error_body": snippet}
            ra = exc.headers.get("Retry-After") if exc.headers is not None else None
            try:
                wait = float(ra) if ra is not None else min(rh.JUDGE_BACKOFF_BASE_S * 2 ** attempt, rh.JUDGE_BACKOFF_CAP_S)
            except ValueError:
                wait = min(rh.JUDGE_BACKOFF_BASE_S * 2 ** attempt, rh.JUDGE_BACKOFF_CAP_S)
            if wait > rh.JUDGE_RETRY_AFTER_CAP_S or attempt >= rh.JUDGE_MAX_RETRIES:
                STOP.set(); STOP_REASON.append(f"HTTP 429 Retry-After {wait:.0f}s")
                return {"_error": "HTTP 429", "_error_body": snippet, "_retry_after_s": wait}
            print(f"429, retry in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
        except Exception as exc:  # timeout etc.; the cell stays retryable
            return {"_error": repr(exc)}
    return {"_error": "retries exhausted"}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def valid_by_id(records: list[dict]) -> dict[str, dict]:
    """Dedupe by cell id: the first valid record of a cell wins."""
    out = {}
    for rec in records:
        if rec.get("valid") and rec["cell_id"] not in out:
            out[rec["cell_id"]] = rec
    return out


def cmd_estimate(a):
    site, key = load_site()
    views = load_views()
    pids = pilot_ids(key)
    pilot = sum(est_tokens(site[c], views) for c in pids)
    full = sum(est_tokens(site[c], views) for c in site)
    print(json.dumps({"prompt_sha256": RATER_PROMPT_SHA256, "pilot_cells": len(pids),
                      "pilot_est_input_tokens": pilot, "all_cells": len(site),
                      "all_est_input_tokens": full, "budget": TOKEN_BUDGET}, indent=1))


def cmd_run(a):
    if a.workers > MAX_WORKERS:
        raise SystemExit(f"workers must be <= {MAX_WORKERS}")
    site, key = load_site()
    views = load_views()
    targets = pilot_ids(key) if a.cells == "pilot" else sorted(site)
    out = Path(a.out)
    done = valid_by_id(read_jsonl(out))
    pending = [c for c in targets if c not in done]
    used = sum((r.get("usage") or {}).get("prompt_tokens") or r["est_input_tokens"] for r in done.values())
    planned = sum(est_tokens(site[c], views) for c in pending)
    print(f"targets {len(targets)}, done {len(done)}, pending {len(pending)}, "
          f"used {used}, planned est {planned}, budget {a.token_budget}", file=sys.stderr)
    if used + planned > a.token_budget:
        raise SystemExit("estimated input tokens exceed the budget; not calling (addendum 24.4)")
    api_key = os.environ.get(rh.API_KEY_ENV) or "<internal-proxy>-local"

    def job(cid):
        cell = site[cid]
        view = views[cell["view"]]
        user = user_message(view, cell)
        t0 = time.time()
        started = datetime.now(timezone.utc).isoformat()
        res = call_rater(RATER_PROMPT, user, api_key)
        rec = {"cell_id": cid, "label_source": LABEL_SOURCE_NAME, "model": MODEL,
               "prompt_sha256": RATER_PROMPT_SHA256, "view_sha256": hashlib.sha256(view.encode()).hexdigest(),
               "est_input_tokens": est_tokens(cell, views), "started_at_utc": started,
               "elapsed_s": round(time.time() - t0, 1)}
        if "_error" in res:
            rec.update(valid=False, error=res["_error"], error_body=res.get("_error_body", ""),
                       retry_after_s=res.get("_retry_after_s"))
        else:
            parsed, err = parse_content(res.get("content") or "")
            rec.update(usage=res.get("usage"), model_returned=res.get("model_returned"),
                       attempt=res.get("attempt"), raw_content=res.get("content"))
            if parsed is None:
                rec.update(valid=False, error=f"unparsed: {err}")
            else:
                rec.update(valid=True, **parsed)
                rec["span_verbatim"] = (bool(collapse(parsed["span"])) and
                                        collapse(parsed["span"]) in collapse(view)) if parsed["S"] == 1 else None
        with _write_lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        u = rec.get("usage") or {}
        print(f"{cid} valid={rec['valid']} S={rec.get('S')} R={rec.get('R')} "
              f"in={u.get('prompt_tokens')} out={u.get('completion_tokens')} {rec['elapsed_s']}s "
              f"{rec.get('error', '')}", file=sys.stderr)
        return rec

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(job, c) for c in pending]
        for f in as_completed(futs):
            f.result()
    if STOP.is_set():
        print("STOPPED: " + "; ".join(STOP_REASON), file=sys.stderr)


# ---------------------------------------------------------------- analysis

def read_labels(path: Path) -> dict[str, dict]:
    out = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["cell_id"].startswith("primary:"):
                out[row["cell_id"]] = {"S": int(row["A"]), "R": int(row["rater_L1"])}
    return out


def cohen_kappa_binary(x, y) -> float | None:
    n = len(x)
    if n == 0:
        return None
    po = sum(a == b for a, b in zip(x, y)) / n
    px, py = sum(x) / n, sum(y) / n
    pe = px * py + (1 - px) * (1 - py)
    return None if pe == 1 else (po - pe) / (1 - pe)


def agreement(a_lab: dict, b_lab: dict, ids) -> dict:
    ids = [i for i in ids if i in a_lab and i in b_lab]
    import analyze_holdout as ah
    ra = [a_lab[i]["R"] for i in ids]; rb = [b_lab[i]["R"] for i in ids]
    sa = [a_lab[i]["S"] for i in ids]; sb = [b_lab[i]["S"] for i in ids]
    n = len(ids)
    return {
        "n": n,
        "R_exact": sum(x == y for x, y in zip(ra, rb)) / n if n else None,
        "R_within1": sum(abs(x - y) <= 1 for x, y in zip(ra, rb)) / n if n else None,
        "R_qwk": ah._qwk_from_values(ra, rb) if n >= 5 else None,
        "S_agree": sum(x == y for x, y in zip(sa, sb)) / n if n else None,
        "S_kappa": cohen_kappa_binary(sa, sb) if n >= 5 else None,
    }


def agreement_ci(a_lab: dict, b_lab: dict, ids, seed: int, B: int) -> dict:
    import analyze_holdout as ah
    recs = [{"cluster_id": i.split(":")[2], "ra": a_lab[i]["R"], "rb": b_lab[i]["R"],
             "sa": a_lab[i]["S"], "sb": b_lab[i]["S"]} for i in ids if i in a_lab and i in b_lab]
    stats = {
        "R_qwk": lambda c: ah._qwk_from_values([r["ra"] for r in c], [r["rb"] for r in c]),
        "R_exact": lambda c: sum(r["ra"] == r["rb"] for r in c) / len(c),
        "R_within1": lambda c: sum(abs(r["ra"] - r["rb"]) <= 1 for r in c) / len(c),
        "S_agree": lambda c: sum(r["sa"] == r["sb"] for r in c) / len(c),
        "S_kappa": lambda c: (cohen_kappa_binary([r["sa"] for r in c], [r["sb"] for r in c]) or 0.0),
    }
    out = {}
    for name, fn in stats.items():
        res = ah.cluster_bootstrap_stat(recs, fn, B=B, seed=seed)
        out[name] = {k: res[k] for k in ("estimate", "ci_lo", "ci_hi", "n_cells", "n_clusters", "B", "seed", "method")}
    return out


def cmd_analyze(a):
    site, key = load_site()
    recs = read_jsonl(Path(a.raw))
    luna = {cid: {"S": r["S"], "R": r["R"]} for cid, r in valid_by_id(recs).items()}
    ah_lab = read_labels(AH_LABELS)
    ind_lab = read_labels(INDEP_LABELS)
    hum = human_labels(key)
    res = {"label_source": LABEL_SOURCE_NAME, "model": MODEL, "prompt_sha256": RATER_PROMPT_SHA256,
           "status": "exploratory, post hoc (addendum 24)", "n_luna_valid": len(luna)}
    usage = [r.get("usage") or {} for r in recs if r.get("usage")]
    res["token_usage"] = {
        "calls_recorded": len(recs), "calls_with_usage": len(usage),
        "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
        "completion_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
        "est_input_tokens_chars_div4": sum(r.get("est_input_tokens", 0) for r in recs),
    }
    vb = valid_by_id(recs).values()
    s1 = [r for r in vb if r["S"] == 1]
    res["span_verbatim"] = {"S1": len(s1), "verbatim": sum(bool(r.get("span_verbatim")) for r in s1)}

    # pilot: luna vs each human label
    rows = []
    for h in hum:
        cid = h["cell_id"]
        rows.append({"rater": h["rater"], "cell_id": cid, "H_S": h["S"], "H_R": h["R"],
                     "luna_S": luna.get(cid, {}).get("S"), "luna_R": luna.get(cid, {}).get("R"),
                     "AH_S": ah_lab[cid]["S"], "AH_R": ah_lab[cid]["R"],
                     "IND_S": ind_lab[cid]["S"], "IND_R": ind_lab[cid]["R"]})
    # per-cell AH / human labels are sealed (washout, ongoing multirater): never in the committed json
    Path(a.out_cells).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    res["pilot_cells_file"] = "written outside the repository (sealed; --out-cells)"
    hum_lab = {}
    for h in hum:
        hum_lab.setdefault(h["rater"], {})[h["cell_id"]] = {"S": h["S"], "R": h["R"]}
    pooled = {h["cell_id"]: {"S": h["S"], "R": h["R"]} for h in hum}  # one human label per cell here
    pilot = {}
    for name, ref in [("pooled_humans", pooled)] + sorted(hum_lab.items()):
        ids = sorted(ref)
        pilot[name] = {
            "luna_vs_human": agreement(luna, ref, ids),
            "AH_vs_human": agreement(ah_lab, ref, ids),
            "IND_vs_human": agreement(ind_lab, ref, ids),
        }
    pids = sorted(pooled)
    pilot["same_cells"] = {"luna_vs_AH": agreement(luna, ah_lab, pids),
                           "luna_vs_IND": agreement(luna, ind_lab, pids),
                           "AH_vs_IND": agreement(ah_lab, ind_lab, pids)}
    res["pilot"] = pilot

    all_ids = sorted(site)
    res["baseline_188_AH_vs_IND"] = agreement_ci(ah_lab, ind_lab, all_ids, a.seed, a.B)
    if len([c for c in all_ids if c in luna]) == 188:
        res["full_188"] = {"luna_vs_AH": agreement_ci(luna, ah_lab, all_ids, a.seed, a.B),
                           "luna_vs_IND": agreement_ci(luna, ind_lab, all_ids, a.seed, a.B)}
        lab_csv = HERE / "labels_for_analysis_luna.csv"
        with lab_csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cell_id", "A", "rater_L1", "label_source"])
            for cid in all_ids:
                w.writerow([cid, luna[cid]["S"], luna[cid]["R"], "LLM, not human"])
        res["full_188"]["analyzer_labels_csv"] = lab_csv.name
    else:
        res["full_188"] = {"status": "not run", "reason": a.full_reason}
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("n_luna_valid", "token_usage", "span_verbatim")}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estimate")
    r = sub.add_parser("run")
    r.add_argument("--cells", choices=("pilot", "all"), required=True)
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--out", default=str(HERE / "luna_rater_raw.jsonl"))
    r.add_argument("--token-budget", type=int, default=TOKEN_BUDGET)
    r.add_argument("--confirm-addendum24-frozen", action="store_true", required=True)
    n = sub.add_parser("analyze")
    n.add_argument("--raw", default=str(HERE / "luna_rater_raw.jsonl"))
    n.add_argument("--out", default=str(HERE / "results_llm_rater_luna.json"))
    n.add_argument("--out-cells", required=True,
                   help="per-cell pilot table (sealed); write it OUTSIDE the repository")
    n.add_argument("--seed", type=int, default=20260913)
    n.add_argument("--B", type=int, default=10000)
    n.add_argument("--full-reason", default="estimated input tokens for 188 cells exceed the 6M budget (addendum 24.4)")
    a = ap.parse_args()
    {"estimate": cmd_estimate, "run": cmd_run, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
