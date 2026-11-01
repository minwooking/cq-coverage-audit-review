#!/usr/bin/env python3
"""E2 step 3: coverage per variant, B'-B paired question-level bootstrap. usage: analyze_bprime.py"""
import json, random
from pathlib import Path
OUT = Path(__file__).resolve().parent
SEED, NB = 20261014, 10000
def boot(d):
    rnd = random.Random(SEED); n = len(d); m = sorted(sum(rnd.choice(d) for _ in range(n)) / n for _ in range(NB))
    return m[int(0.025 * NB)], m[int(0.975 * NB) - 1]
res = {"seed": SEED, "n_boot": NB, "banks": {}}
for tag in ("ko", "en"):
    f = OUT / f"eval_{tag}.json"
    if not f.exists(): continue
    e = json.loads(f.read_text()); sc = e["layer1"]["cq_scores"]; ids = [q["id"] for q in e["questions"]]
    cov = {v: round(100 * sum(sc[v][i] for i in ids) / (3 * len(ids)), 2) for v in sc}
    out = {"n_cq": len(ids), "coverage_pct": cov, "per_cq": {v: [sc[v][i] for i in ids] for v in sc},
           "quality_pct": {v: e["aggregate"][v]["quality_pct"] for v in sc},
           "graph_stats": e["stats"], "contrasts": {}}
    for a, b in (("B", "Bp"), ("A", "Bp"), ("C", "Bp"), ("A", "B"), ("C", "B")):
        d = [sc[b][i] - sc[a][i] for i in ids]; lo, hi = boot(d); mean = sum(d) / len(d)
        out["contrasts"][f"{b}-{a}"] = {"mean_score_diff_0to3": round(mean, 4), "coverage_pp": round(100 * mean / 3, 2),
            "ci95_score": [round(lo, 4), round(hi, 4)], "ci95_pp": [round(100 * lo / 3, 2), round(100 * hi / 3, 2)],
            "n_improved": sum(x > 0 for x in d), "n_worse": sum(x < 0 for x in d), "primary": (a, b) == ("B", "Bp") and tag == "ko"}
    res["banks"][tag] = out
(OUT / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({t: {"cov": b["coverage_pct"], "Bp-B": b["contrasts"]["Bp-B"]} for t, b in res["banks"].items()}, ensure_ascii=False, indent=1))
