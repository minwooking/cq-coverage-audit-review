#!/usr/bin/env python3
"""Addendum 34 A3: Brick pool without the expansion bank, and +-0.30 readings of stored Study 3/4 intervals.
AI-generated; review and test before use.  Reads judge records and stored results only; no label, no model call.
Post hoc, exploratory; judge-score contrast; not human-labelled."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "study2_llm_labels"))
sys.path.insert(0, str(HERE))
import analyze_all as aa  # noqa: E402
import analyze_holdout as ah  # noqa: E402

M30 = 0.30


def dec30(s: dict) -> str:
    return ah.tost_decision(s["ci95"][0], s["ci95"][1], M30, eq_lo=s["ci90"][0], eq_hi=s["ci90"][1])


def slim(s: dict) -> dict:
    keys = ("n_clusters", "mean_J_A", "mean_J_B", "delta", "ci95", "ci90", "decision", "prospective_mde", "realized_mde")
    out = {k: s[k] for k in keys if k in s}
    out["decision_0.50"] = s["decision"]
    out["decision_0.30"] = dec30(s)
    return out


def main() -> int:
    s3 = json.loads((HERE / "results_all.json").read_text())
    s4 = json.loads((HARNESS / "study4_domains" / "results.json").read_text())
    out = {"banner": "post hoc, exploratory; judge-score contrasts without human labels; margin 0.50 pre-fixed, 0.30 shown as sensitivity", "judges": {}}
    for j in aa.JUDGES:
        B = aa.build_banks(j)
        res = {"study3": {}, "study4": {}}
        for k, s in {**s3["judges"][j]["pools"], **s3["judges"][j]["domains"]}.items():
            if "delta" in s:
                res["study3"][k] = slim(s)
        for k in ("holdout", "paraphrases", "v2_extras"):
            res["study3"][f"bank: {k}"] = slim(aa.summarize(B[k]["bank"]))
        noexp = aa.summarize(aa.pool([B[k]["bank"] for k in ("holdout", "paraphrases", "v2_extras")]))
        res["study3"]["brick_no_expansion (holdout + paraphrases + v2 extras)"] = slim(noexp)
        res["study3"]["expansion bank alone"] = slim(aa.summarize(B["expansion"]["bank"]))
        for d, v in s4["domains"].items():
            res["study4"][d] = slim(v[j]["mean_of_repeats"])
        res["study4"]["pooled"] = slim(s4["pooled"][j]["mean_of_repeats"])
        out["judges"][j] = res
    (HERE / "results_a3.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    for j, r in out["judges"].items():
        print(j)
        for st in ("study3", "study4"):
            for k, s in r[st].items():
                print(f"  {st} | {k} | n={s['n_clusters']} | {s['delta']:+.3f} [{s['ci95'][0]:+.3f},{s['ci95'][1]:+.3f}] 90%[{s['ci90'][0]:+.3f},{s['ci90'][1]:+.3f}] | 0.50: {s['decision_0.50']} | 0.30: {s['decision_0.30']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
