#!/usr/bin/env python3
"""Addendum 36 gateway judge: probe (read-only /v1/models + 1 call per candidate) and budgeted scoring through the local <internal-proxy> proxy.
AI-generated; review before reuse.  Python stdlib + addendum 26's parser.

  score_gateway.py probe <jobs.jsonl> <probe.json>
  score_gateway.py run <model> <jobs.jsonl> <out.jsonl> [--workers N] [--budget-prompt-tokens N] [--omit-temperature]

Request form = the registered one minus `response_format` (the <internal-proxy> adapter rejects it, run_second_judge.py).  Quota rules (PLAN 36.4): workers <= 3, a
prompt-token budget, passes = repeat 1 over all cells, then 2, then 3; stop on 3 consecutive 402/429 or when the budget is spent.  Nothing is imputed.
The key (env HOLDOUT_JUDGE_API_KEY, optional for the local proxy) is never printed or written.
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import p5_common as C

spec = importlib.util.spec_from_file_location("sj", C.HARNESS / "review6_judges" / "score_judges.py")
sj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sj)

INTERNAL_PROXY = "http://127.0.0.1:10100/v1"
CANDIDATES = ["gpt-5.6-luna", "anthropic/claude-haiku-5-5", "anthropic/claude-sonnet-5-5"]
KEY = os.environ.get("HOLDOUT_JUDGE_API_KEY", "none")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def http(path: str, body: dict | None, timeout: float = 600.0) -> dict:
    req = urllib.request.Request(f"{INTERNAL_PROXY}{path}", data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"status": r.status, "payload": json.loads(r.read()), "text": "", "s": time.monotonic() - t0}
    except urllib.error.HTTPError as e:
        try:
            t = e.read().decode("utf-8", "replace")[:400]
        except Exception:  # noqa: BLE001
            t = ""
        return {"status": e.code, "payload": None, "text": t, "s": time.monotonic() - t0}
    except Exception as e:  # noqa: BLE001
        return {"status": None, "payload": None, "text": repr(e)[:300], "s": time.monotonic() - t0}


def body_for(model: str, job: dict, max_tokens: int, omit_temp: bool) -> dict:
    b = {"model": model, "messages": [{"role": "system", "content": job["system"]}, {"role": "user", "content": job["user"]}],
         "max_tokens": max_tokens}
    if not omit_temp:
        b["temperature"] = 0.0
    return b


def probe(jobs_path: str, out_path: str) -> int:
    jobs = C.jsonl(jobs_path)
    job = min(jobs, key=lambda j: len(j["user"]))
    listing = http("/models", None, 20)
    ids = [m.get("id") for m in (listing["payload"] or {}).get("data", [])] if listing["status"] == 200 else []
    res = {"utc": now(), "models_listing_status": listing["status"], "gemini-3.6-flash_listed": any("gemini" in str(i) for i in ids),
           "candidates": {}}
    chosen_claude = None
    for m in CANDIDATES:
        if m not in ids:
            res["candidates"][m] = {"result": "no route (not listed)"}
            continue
        if m.startswith("anthropic/") and chosen_claude:
            res["candidates"][m] = {"result": "not probed (a Claude judge was already chosen; one Claude model only)"}
            continue
        r = http("/chat/completions", body_for(m, job, 1024, False), 300)
        omit = False
        if r["status"] == 400 and "temperature" in r["text"].lower():
            omit = True
            r = http("/chat/completions", body_for(m, job, 1024, True), 300)
        entry = {"http_status": r["status"], "omit_temperature": omit, "seconds": round(r["s"], 2), "error": r["text"][:200] if r["status"] != 200 else ""}
        if r["status"] == 200:
            ch = (r["payload"].get("choices") or [{}])[0]
            j, ev, ok, note, _ = sj.parse_reply((ch.get("message") or {}).get("content"))
            u = r["payload"].get("usage") or {}
            entry.update(parsed_ok=ok, J=j, prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                         finish_reason=ch.get("finish_reason"), model_reported=r["payload"].get("model"))
            entry["result"] = "answers" if ok else "answers but unparseable"
            if ok and m.startswith("anthropic/"):
                chosen_claude = m
        else:
            entry["result"] = "no route" if r["status"] in (402, 404, 429, 502, 503, None) or r["status"] >= 400 else "error"
        res["candidates"][m] = entry
    res["gateway_judges"] = [m for m, e in res["candidates"].items() if e.get("result") == "answers"]
    open(out_path, "w", encoding="utf-8").write(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "candidates"}), {m: e.get("result") for m, e in res["candidates"].items()})
    return 0


def run(model: str, jobs_path: str, out_path: str, workers: int, budget: int, omit_temp: bool) -> int:
    workers = min(max(workers, 1), 3)
    jobs = C.jsonl(jobs_path)
    done = sj.done_keys(__import__("pathlib").Path(out_path))
    lock = threading.Lock()
    st = {"prompt": 0, "completion": 0, "calls": 0, "invalid": 0, "consec_quota": 0, "stop": None}

    def one(job: dict, rep: int) -> dict | None:
        with lock:
            if st["stop"]:
                return None
        rec = {"judge": "gw", "model": model, "study": job["study"], "cell_id": job["cell_id"], "cell_kind": job["cell_kind"], "variant": job["variant"],
               "cq_id": job["cq_id"], "cluster_id": job["cluster_id"], "repeat": rep, "prompt_sha256": job["prompt_sha256"], "started_utc": now(), "attempts": []}
        for att in range(3):
            mt = 1024 if att == 0 else 4096
            r = http("/chat/completions", body_for(model, job, mt, omit_temp))
            if r["status"] != 200:
                rec["attempts"].append({"max_tokens": mt, "http": r["status"], "body": r["text"][:200]})
                with lock:
                    if r["status"] in (402, 429):
                        st["consec_quota"] += 1
                        if st["consec_quota"] >= 3:
                            st["stop"] = f"3 consecutive HTTP {r['status']}"
                if r["status"] in (402,):
                    break
                time.sleep(min(60, 5 * 3 ** att))
                continue
            with lock:
                st["consec_quota"] = 0
            ch = (r["payload"].get("choices") or [{}])[0]
            content = (ch.get("message") or {}).get("content")
            u = r["payload"].get("usage") or {}
            j, ev, ok, note, lenient = sj.parse_reply(content)
            with lock:
                st["prompt"] += int(u.get("prompt_tokens") or 0)
                st["completion"] += int(u.get("completion_tokens") or 0)
                if st["prompt"] >= budget:
                    st["stop"] = "prompt-token budget reached"
            rec["attempts"].append({"max_tokens": mt, "finish_reason": ch.get("finish_reason"), "parse_ok": ok, "note": note})
            rec.update(raw_content=content, finish_reason=ch.get("finish_reason"), prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                       evidence=ev, lenient_parse=lenient, parse_note=note, model_reported=r["payload"].get("model"))
            if ok:
                rec.update(status="ok", valid=True, J=j, latency_s=round(r["s"], 3))
                return rec
        rec.update(status="invalid", valid=False, J=None)
        return rec

    outp = open(out_path, "a", encoding="utf-8")
    for rep in (1, 2, 3):
        pend = [j for j in jobs if (j["cell_id"], rep) not in done]
        random.Random(C.SEED + 1000 * rep).shuffle(pend)
        print(f"{now()} gw repeat {rep}: {len(pend)} cells", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for f in as_completed([pool.submit(one, j, rep) for j in pend]):
                rec = f.result()
                if rec is None:
                    continue
                with lock:
                    outp.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    outp.flush()
                    st["calls"] += 1
                    st["invalid"] += rec["status"] == "invalid"
        print(f"{now()} gw repeat {rep} done calls={st['calls']} invalid={st['invalid']} prompt_tokens={st['prompt']} stop={st['stop']}", flush=True)
        if st["stop"]:
            break
    print(f"{now()} gw DONE calls={st['calls']} invalid={st['invalid']} prompt_tokens={st['prompt']} completion_tokens={st['completion']} stop={st['stop']}", flush=True)
    return 0


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    if a[0] == "probe":
        return probe(a[1], a[2])
    w = int(a[a.index("--workers") + 1]) if "--workers" in a else 3
    b = int(a[a.index("--budget-prompt-tokens") + 1]) if "--budget-prompt-tokens" in a else 9_000_000
    return run(a[1], a[2], a[3], w, b, "--omit-temperature" in a)


if __name__ == "__main__":
    raise SystemExit(main())
