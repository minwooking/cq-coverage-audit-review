#!/usr/bin/env python3
"""LLM-rater (luna) labels, subgraph view, on all 188 primary cells -- PREREG addendum 25.

AI-generated code: review before use.  Exploratory (post hoc).

Same rater prompt (RATER_PROMPT, sha256 efb8a43f...), same blinding, same call
settings and parsing as addendum 24 (imported from ../rater_luna.py, unchanged).
Only the material changes: instead of the full rendered view of the variant,
the user message carries the question-relevant SUBGRAPH rendering that the
length experiment built (harness/length_experiment/make_inputs.py,
build_subgraph_text; files under length_experiment/inputs/<V>/<CQ>/subgraph.txt,
sha256-checked against length_experiment/inputs/manifest.jsonl).  For the 6
cells where the length experiment has no subgraph (status not_applicable:
A-CQB27, B..F-CQB32) the rater receives the full rendered view (the same text
human raters see), as frozen in addendum 25.3.

Sub-commands
  estimate   chars/4 input-token estimate per view kind
  run        call <internal-proxy> gpt-5.6-luna; resumable jsonl, dedupe by cell id
  analyze    the frozen analysis of addendum 25.5-25.7
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent.parent))
import rater_luna as rl  # noqa: E402  (prompt, call, parse, labels, agreement)
import analyze_holdout as ah  # noqa: E402

ACCESS = rl.ACCESS
LENGTH_MANIFEST = ACCESS / "harness" / "length_experiment" / "inputs" / "manifest.jsonl"
FULLVIEW_RAW = HERE.parent / "luna_rater_raw.jsonl"  # addendum-24 pilot (full view)
RAW = HERE / "luna_rater_subgraph_raw.jsonl"
LABEL_SOURCE_NAME = "LLM-rater (luna) labels, subgraph view"
EXPECTED_PROMPT_SHA = "efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769"
TOKEN_BUDGET = 6_000_000
SEED = 20260913
B = 10_000
AH_RESULTS = ACCESS / "harness" / "real_run" / "results_human_pass" / "holdout_results_human.rater_safe.json"
IND_RESULTS = ACCESS / "annotation" / "second_pass_2026-10-13" / "v3" / "results_v3.json"
BASELINE = {"R_qwk": (0.728, 0.567, 0.859), "R_exact": 0.718, "S_agree": 0.830, "S_kappa": 0.595}
PRIMARY_METRICS = ("R_qwk", "R_exact", "S_agree", "S_kappa")

assert rl.RATER_PROMPT_SHA256 == EXPECTED_PROMPT_SHA, "rater prompt changed"


def load_inputs():
    """{cell_id: (site cell, material text, view_kind)} for all 188 primary cells."""
    site, key = rl.load_site()
    views = rl.load_views()
    man = [json.loads(line) for line in LENGTH_MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()]
    sg = {(r["variant"], r["cq_id"]): r for r in man if r["condition"] == "subgraph"}
    full = {(r["variant"], r["cq_id"]): r for r in man if r["condition"] == "full"}
    out = {}
    for cid, cell in site.items():
        _, v, q = cid.split(":")
        fv = views[cell["view"]]
        if hashlib.sha256(fv.encode()).hexdigest() != full[(v, q)]["sha256"]:
            raise SystemExit(f"{cid}: rater view differs from the frozen rendered view")
        r = sg[(v, q)]
        if r["status"] == "ok":
            text = (ACCESS / r["path"]).read_text(encoding="utf-8")
            if hashlib.sha256(text.encode()).hexdigest() != r["sha256"]:
                raise SystemExit(f"{cid}: subgraph sha256 mismatch")
            out[cid] = (cell, text, "subgraph")
        else:
            out[cid] = (cell, fv, "full_view_fallback")
    return out, key


def est(cell, text) -> int:
    return -(-(len(rl.RATER_PROMPT) + len(rl.user_message(text, cell))) // 4)


def cmd_estimate(a):
    inp, key = load_inputs()
    pids = rl.pilot_ids(key)
    by = {}
    for cid, (cell, text, kind) in inp.items():
        by.setdefault(kind, [0, 0])
        by[kind][0] += 1
        by[kind][1] += est(cell, text)
    print(json.dumps({"prompt_sha256": rl.RATER_PROMPT_SHA256, "cells": len(inp), "by_view_kind": by,
                      "total_est_input_tokens": sum(v[1] for v in by.values()),
                      "bridge_cells": len(pids), "bridge_in_188": all(p in inp for p in pids),
                      "bridge_est_input_tokens": sum(est(inp[p][0], inp[p][1]) for p in pids),
                      "budget": TOKEN_BUDGET}, indent=1))


def cmd_run(a):
    if a.workers > rl.MAX_WORKERS:
        raise SystemExit(f"workers must be <= {rl.MAX_WORKERS}")
    inp, _ = load_inputs()
    out = Path(a.out)
    done = rl.valid_by_id(rl.read_jsonl(out))
    pending = [c for c in sorted(inp) if c not in done]
    used = sum((r.get("usage") or {}).get("prompt_tokens") or 0 for r in rl.read_jsonl(out))
    planned = sum(est(inp[c][0], inp[c][1]) for c in pending)
    print(f"targets {len(inp)}, done {len(done)}, pending {len(pending)}, used {used}, "
          f"planned est {planned}, budget {a.token_budget}", file=sys.stderr)
    if used + planned > a.token_budget:
        raise SystemExit("estimated input tokens exceed the budget; not calling (addendum 25.4)")
    api_key = rl.os.environ.get(rl.rh.API_KEY_ENV) or "<internal-proxy>-local"

    def job(cid):
        if rl.STOP.is_set():
            return None
        cell, text, kind = inp[cid]
        user = rl.user_message(text, cell)
        t0 = time.time()
        started = datetime.now(timezone.utc).isoformat()
        res = rl.call_rater(rl.RATER_PROMPT, user, api_key)
        rec = {"cell_id": cid, "label_source": LABEL_SOURCE_NAME, "view_kind": kind, "model": rl.MODEL,
               "prompt_sha256": rl.RATER_PROMPT_SHA256, "view_sha256": hashlib.sha256(text.encode()).hexdigest(),
               "est_input_tokens": est(cell, text), "started_at_utc": started,
               "elapsed_s": round(time.time() - t0, 1)}
        if "_error" in res:
            rec.update(valid=False, error=res["_error"], error_body=res.get("_error_body", ""),
                       retry_after_s=res.get("_retry_after_s"))
        else:
            parsed, err = rl.parse_content(res.get("content") or "")
            rec.update(usage=res.get("usage"), model_returned=res.get("model_returned"),
                       attempt=res.get("attempt"), raw_content=res.get("content"))
            if parsed is None:
                rec.update(valid=False, error=f"unparsed: {err}")
            else:
                rec.update(valid=True, **parsed)
                rec["span_verbatim"] = (bool(rl.collapse(parsed["span"])) and
                                        rl.collapse(parsed["span"]) in rl.collapse(text)) if parsed["S"] == 1 else None
        with rl._write_lock:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        u = rec.get("usage") or {}
        print(f"{cid} {kind} valid={rec['valid']} S={rec.get('S')} R={rec.get('R')} "
              f"in={u.get('prompt_tokens')} out={u.get('completion_tokens')} {rec['elapsed_s']}s "
              f"{rec.get('error', '')}", file=sys.stderr, flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for f in as_completed([ex.submit(job, c) for c in pending]):
            f.result()
    if rl.STOP.is_set():
        print("STOPPED: " + "; ".join(rl.STOP_REASON), file=sys.stderr)


# ---------------------------------------------------------------- analysis

def paired_diff_ci(luna, other, ah_lab, ind_lab, ids, metric):
    """(luna vs other) minus (AH vs IND) on the same clusters/resamples."""
    recs = [{"cluster_id": i.split(":")[2], "l": luna[i], "o": other[i], "a": ah_lab[i], "n": ind_lab[i]}
            for i in ids]

    def m(c, x, y):
        if metric == "R_qwk":
            return ah._qwk_from_values([r[x]["R"] for r in c], [r[y]["R"] for r in c])
        if metric == "R_exact":
            return sum(r[x]["R"] == r[y]["R"] for r in c) / len(c)
        if metric == "R_within1":
            return sum(abs(r[x]["R"] - r[y]["R"]) <= 1 for r in c) / len(c)
        if metric == "S_agree":
            return sum(r[x]["S"] == r[y]["S"] for r in c) / len(c)
        if metric == "S_kappa":
            return rl.cohen_kappa_binary([r[x]["S"] for r in c], [r[y]["S"] for r in c]) or 0.0
        raise KeyError(metric)

    res = ah.cluster_bootstrap_stat(recs, lambda c: m(c, "l", "o") - m(c, "a", "n"), B=B, seed=SEED)
    return {k: res[k] for k in ("estimate", "ci_lo", "ci_hi", "n_cells", "n_clusters", "B", "seed", "method")}


def gate_summary(d):
    return {"pi_hat": d["pi_hat"]["pi_hat"],
            "gates": {k: {"status": v.get("status"), "value": v.get("value")} for k, v in d["gates"].items()}}


def cmd_analyze(a):
    inp, key = load_inputs()
    recs = rl.read_jsonl(Path(a.raw))
    vb = rl.valid_by_id(recs)
    luna = {cid: {"S": r["S"], "R": r["R"]} for cid, r in vb.items()}
    ah_lab = rl.read_labels(rl.AH_LABELS)
    ind_lab = rl.read_labels(rl.INDEP_LABELS)
    all_ids = sorted(inp)
    res = {"label_source": LABEL_SOURCE_NAME, "model": rl.MODEL, "prompt_sha256": rl.RATER_PROMPT_SHA256,
           "status": "exploratory, post hoc (addendum 25)", "n_cells": len(all_ids),
           "n_luna_valid": sum(c in luna for c in all_ids),
           "view_kind_counts": {k: sum(1 for c in all_ids if inp[c][2] == k)
                                for k in ("subgraph", "full_view_fallback")}}
    usage = [r.get("usage") or {} for r in recs if r.get("usage")]
    res["token_usage"] = {"calls_recorded": len(recs), "calls_invalid": sum(not r.get("valid") for r in recs),
                          "prompt_tokens": sum(u.get("prompt_tokens") or 0 for u in usage),
                          "completion_tokens": sum(u.get("completion_tokens") or 0 for u in usage),
                          "est_input_tokens_chars_div4": sum(r.get("est_input_tokens", 0) for r in recs)}
    s1 = [vb[c] for c in all_ids if c in vb and vb[c]["S"] == 1]
    res["span_verbatim"] = {"S1": len(s1), "verbatim": sum(bool(r.get("span_verbatim")) for r in s1)}
    res["label_distribution"] = {
        src: {"S1": sum(lab[c]["S"] for c in all_ids if c in lab),
              "R": {str(k): sum(lab[c]["R"] == k for c in all_ids if c in lab) for k in range(4)}}
        for src, lab in (("luna_subgraph", luna), ("AH", ah_lab), ("IND", ind_lab))}

    complete = all(c in luna for c in all_ids)
    res["complete_188"] = complete
    if not complete:
        res["agreement_188"] = {"status": "not computed", "reason": "fewer than 188 valid luna labels",
                                "missing": [c for c in all_ids if c not in luna]}
    else:
        base = rl.agreement_ci(ah_lab, ind_lab, all_ids, SEED, B)
        la = rl.agreement_ci(luna, ah_lab, all_ids, SEED, B)
        li = rl.agreement_ci(luna, ind_lab, all_ids, SEED, B)
        verdict = {}
        for pair, d, other in (("luna_vs_AH", la, ah_lab), ("luna_vs_IND", li, ind_lab)):
            verdict[pair] = {}
            for m in PRIMARY_METRICS + ("R_within1",):
                inside = base[m]["ci_lo"] <= d[m]["estimate"] <= base[m]["ci_hi"]
                verdict[pair][m] = {
                    "estimate": d[m]["estimate"], "baseline_estimate": base[m]["estimate"],
                    "baseline_ci": [base[m]["ci_lo"], base[m]["ci_hi"]],
                    "comparable": inside if m in PRIMARY_METRICS else None,
                    "direction": ("inside" if inside else
                                  ("above" if d[m]["estimate"] > base[m]["ci_hi"] else "below")),
                    "rule": "point estimate inside the AH-vs-IND BCa 95% CI" if m in PRIMARY_METRICS
                            else "descriptive (not a primary metric)",
                    "paired_diff_vs_baseline": paired_diff_ci(luna, other, ah_lab, ind_lab, all_ids, m)}
        res["agreement_188"] = {"baseline_AH_vs_IND": base, "luna_vs_AH": la, "luna_vs_IND": li,
                                "verdict": verdict}
        sg_ids = [c for c in all_ids if inp[c][2] == "subgraph"]
        res["sensitivity_subgraph_only"] = {
            "n_cells": len(sg_ids), "luna_vs_AH": rl.agreement_ci(luna, ah_lab, sg_ids, SEED, B),
            "luna_vs_IND": rl.agreement_ci(luna, ind_lab, sg_ids, SEED, B),
            "AH_vs_IND": rl.agreement_ci(ah_lab, ind_lab, sg_ids, SEED, B)}

    # bridge: subgraph vs full-view luna labels on the 12 pilot cells
    full_luna = {cid: {"S": r["S"], "R": r["R"]} for cid, r in rl.valid_by_id(rl.read_jsonl(FULLVIEW_RAW)).items()}
    pids = rl.pilot_ids(key)
    res["bridge_12"] = {"subgraph_vs_fullview_luna": rl.agreement(luna, full_luna, pids),
                        "transitions": {f"S{full_luna[c]['S']}R{full_luna[c]['R']}->S{luna[c]['S']}R{luna[c]['R']}": 0
                                        for c in pids if c in luna and c in full_luna}}
    for c in pids:
        if c in luna and c in full_luna:
            res["bridge_12"]["transitions"][f"S{full_luna[c]['S']}R{full_luna[c]['R']}->S{luna[c]['S']}R{luna[c]['R']}"] += 1

    # 12 new human labels (descriptive)
    hum = rl.human_labels(key)
    pooled = {h["cell_id"]: {"S": h["S"], "R": h["R"]} for h in hum}
    hids = sorted(pooled)
    res["human_12"] = {"luna_subgraph_vs_human": rl.agreement(luna, pooled, hids),
                       "luna_fullview_vs_human": rl.agreement(full_luna, pooled, hids),
                       "AH_vs_human": rl.agreement(ah_lab, pooled, hids),
                       "IND_vs_human": rl.agreement(ind_lab, pooled, hids)}
    sealed_rows = [{"rater": h["rater"], "cell_id": h["cell_id"], "H_S": h["S"], "H_R": h["R"],
                    "luna_sg_S": luna.get(h["cell_id"], {}).get("S"), "luna_sg_R": luna.get(h["cell_id"], {}).get("R"),
                    "luna_full_S": full_luna.get(h["cell_id"], {}).get("S"),
                    "luna_full_R": full_luna.get(h["cell_id"], {}).get("R"),
                    "AH_S": ah_lab[h["cell_id"]]["S"], "AH_R": ah_lab[h["cell_id"]]["R"],
                    "IND_S": ind_lab[h["cell_id"]]["S"], "IND_R": ind_lab[h["cell_id"]]["R"]} for h in hum]
    Path(a.out_cells).write_text(json.dumps(sealed_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    res["sealed_cells_file"] = "written outside the repository (--out-cells)"

    # unsupported credit + gates with luna labels as reference (analyzer unchanged)
    if complete:
        lab_csv = Path(a.out).parent / "labels_for_analysis_luna_subgraph.csv"
        with lab_csv.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cell_id", "A", "rater_L1", "label_source"])
            for cid in all_ids:
                w.writerow([cid, luna[cid]["S"], luna[cid]["R"], "LLM, not human"])
        an_out = Path(a.out).parent / "holdout_results_luna_subgraph.json"
        cmd = [sys.executable, str(ACCESS / "harness" / "analyze_holdout.py"),
               str(ACCESS / "harness" / "real_run" / "cells.jsonl"), "--seed", str(SEED),
               "--labels", str(lab_csv), "--out", str(an_out), "--out-cells", a.out_analyzer_cells]
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ACCESS))
        res["analyzer"] = {"cmd": " ".join(Path(x).name if x.startswith("/") else x for x in cmd[1:]),
                           "returncode": p.returncode}
        if p.returncode == 0:
            res["unsupported_credit_and_gates"] = {
                "luna_subgraph": gate_summary(json.loads(an_out.read_text(encoding="utf-8"))),
                "AH": gate_summary(json.loads(AH_RESULTS.read_text(encoding="utf-8"))),
                "IND_v3": gate_summary(json.loads(IND_RESULTS.read_text(encoding="utf-8")))}
        else:
            res["analyzer"]["stderr_tail"] = p.stderr[-2000:]
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: res.get(k) for k in ("n_luna_valid", "token_usage", "span_verbatim", "complete_188")}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estimate")
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--out", default=str(RAW))
    r.add_argument("--token-budget", type=int, default=TOKEN_BUDGET)
    r.add_argument("--confirm-addendum25-frozen", action="store_true", required=True)
    n = sub.add_parser("analyze")
    n.add_argument("--raw", default=str(RAW))
    n.add_argument("--out", default=str(HERE / "results_llm_rater_luna_subgraph.json"))
    n.add_argument("--out-cells", required=True, help="sealed per-cell 12-label table; OUTSIDE the repository")
    n.add_argument("--out-analyzer-cells", required=True, help="analyzer per-cell output; OUTSIDE the repository")
    a = ap.parse_args()
    {"estimate": cmd_estimate, "run": cmd_run, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
