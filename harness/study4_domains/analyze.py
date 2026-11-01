#!/usr/bin/env python3
"""Addendum 35 analysis: per-domain and pooled A->B judge-score contrast.  AI-generated; review and test before use.

  analyze.py extract <d> <judge>   raw judge records + jobs -> <d>/scores_<judge>.csv (cell, repeat, J, evidence-verbatim flags; no text)
  analyze.py run [--domains dcat,ssn,prov]   scores CSV + eligibility.json -> results.json, REPORT_auto.md, tables.tex
  analyze.py selftest

Judge-score contrast on standards-based domains; not human-labelled.  No label, no threshold changed after a score: constants below are the PLAN's.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import statistics
import sys
from pathlib import Path

import numpy as np
from scipy import stats

import s4_common as C

sys.path.insert(0, str(C.HARNESS))
sys.path.insert(0, str(C.HARNESS / "review6_natural"))
import analyze_holdout as ah  # noqa: E402
import analyze_natural as an  # noqa: E402

_spec = importlib.util.spec_from_file_location("review9_analyze", C.HARNESS / "review9_verbatim" / "analyze.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)

HERE = C.HERE
SEED, B = C.SEED, C.BOOT_B
Z_SUM = 1.959963984540054 + 0.8416212335729143
SIGMAS = {"prespecified_1.155": 1.155, "holdout_J_1.343": 1.343}
MARGIN = 0.50
MIN_BOTH = 10
JUDGES = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b"}
BANNER = "judge-score contrast on standards-based domains; not human-labelled; exploratory"
FIELDS = ["cell_id", "variant", "cq_id", "repeat", "valid", "J", "verbatim", "verbatim_elided"]


def mde(sigma: float, n: int) -> float:
    return float(Z_SUM * sigma / np.sqrt(n))


def jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def extract(d: str, judge: str) -> int:
    dd = C.ddir(d)
    jobs = {j["cell_id"]: j for j in jsonl(dd / "jobs.jsonl")}
    recs = jsonl(dd / "judge_raw" / f"{judge}.jsonl")
    rows = []
    best: dict = {}
    for r in recs:                                     # one record per (cell, repeat): a valid one wins, else the last
        k = (r["cell_id"], r.get("repeat", 0))
        if k not in best or r.get("valid") or not best[k].get("valid"):
            best[k] = r
    for r in best.values():
        if r.get("repeat", 0) == 0:
            continue                                   # context-skip marker rows
        j = jobs.get(r["cell_id"])
        view_n = an.norm(an.view_of(j)) if j else ""
        valid = bool(r.get("valid")) and r.get("J") is not None
        ev = r.get("evidence")
        rows.append({"cell_id": r["cell_id"], "variant": r["variant"], "cq_id": r["cq_id"], "repeat": r["repeat"], "valid": int(valid),
                     "J": int(r["J"]) if valid else "", "verbatim": int(an.verbatim(ev, view_n)) if valid else "",
                     "verbatim_elided": int(r9.verbatim_elided(ev, view_n)) if valid else ""})
    rows.sort(key=lambda x: (x["cell_id"], x["repeat"]))
    out = dd / f"scores_{judge}.csv"
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(out.name, len(rows), "records;", sum(1 for x in rows if not x["valid"]), "invalid")
    return 0


def load_scores(d: str, judge: str) -> list[dict]:
    p = C.ddir(d) / f"scores_{judge}.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["valid"] = int(r["valid"])
        r["repeat"] = int(r["repeat"])
        for k in ("J", "verbatim", "verbatim_elided"):
            r[k] = int(r[k]) if r[k] != "" else None
    return rows


def cell_scores(rows: list[dict], how: str = "mean") -> dict[str, float]:
    by: dict[str, list[int]] = {}
    for r in rows:
        if r["valid"] and r["J"] is not None:
            by.setdefault(r["cell_id"], []).append(r["J"])
    agg = (lambda v: float(np.mean(v))) if how == "mean" else (lambda v: float(statistics.median_low(sorted(v))))
    return {c: agg(v) for c, v in by.items()}


def coverage_ci(scores: dict[str, float], ids: list[str], v: str) -> dict | None:
    cells = [{"cluster_id": c, "J": scores[f"primary:{v}:{c}"]} for c in ids if f"primary:{v}:{c}" in scores]
    if len(cells) < 2:
        return None
    cov = lambda cs: 100.0 * sum(x["J"] for x in cs) / (3 * len(cs))
    r = ah.cluster_bootstrap_stat(cells, cov, None, "cluster_id", B, SEED)
    return {"n_cells": len(cells), "coverage_pct": r["estimate"], "ci95": [r["ci_lo"], r["ci_hi"]]}


def contrast_from_d(d_by_cluster: dict[str, float]) -> dict:
    ids = sorted(d_by_cluster)
    d = np.array([d_by_cluster[c] for c in ids])
    n = len(ids)
    out = {"n_clusters": n, "delta": float(d.mean()) if n else None}
    if n < 2:
        out.update(decision="underpowered", note="fewer than 2 clusters")
        return out
    out["sd_d"] = float(d.std(ddof=1))
    boot = ah.cluster_bootstrap_delta({c: [float(x)] for c, x in zip(ids, d)}, B, SEED)
    out["ci95"], out["ci90"] = [boot["ci_lo"], boot["ci_hi"]], [boot["ci90_lo"], boot["ci90_hi"]]
    nz = d[d != 0]
    npos, nneg = int((nz > 0).sum()), int((nz < 0).sum())
    out["sign_test"] = {"n_pos": npos, "n_neg": nneg, "n_zero": int((d == 0).sum()),
                        "p": float(stats.binomtest(npos, npos + nneg, 0.5).pvalue) if nz.size else None}
    wil = ah.wilcoxon_zeros_dropped([float(x) for x in d])
    out["wilcoxon"] = wil
    dec = ah.tost_decision(out["ci95"][0], out["ci95"][1], MARGIN, eq_lo=out["ci90"][0], eq_hi=out["ci90"][1])
    out["decision"] = dec
    out["decision_with_rank_rule"] = ah._decision_with_rank_rule(dec, ah._rank_agrees_in_sign(out["delta"], wil))
    out["prospective_mde"] = {k: mde(s, n) for k, s in SIGMAS.items()}
    out["realized_sigma"] = out["sd_d"]
    out["realized_mde"] = mde(out["sd_d"], n)
    out["underpowered_flag"] = n < MIN_BOTH
    return out


def verbatim_summary(rows: list[dict]) -> dict:
    out = {}
    for v in "AB":
        cr = [r for r in rows if r["variant"] == v and r["valid"] and r["J"] is not None and r["J"] >= 2]
        k = sum(r["verbatim"] for r in cr)
        ke = sum(r["verbatim_elided"] for r in cr)
        out[v] = {"credits_J_ge_2": len(cr), "verbatim_strict": k, "verbatim_elided": ke,
                  "share_strict": (k / len(cr)) if cr else None, "share_elided": (ke / len(cr)) if cr else None}
    return out


def domain_result(d: str, judge: str) -> dict:
    el = json.loads((C.ddir(d) / "eligibility.json").read_text(encoding="utf-8"))
    rows = load_scores(d, judge)
    both = el["eligible_in_both"]
    res = {"domain": d, "judge": judge, "model": JUDGES[judge], "bank_sha256": el["bank_sha256"], "n_questions": el["n_questions"],
           "eligible_cells": el["eligible_cells"], "eligible_clusters_A_or_B": el["eligible_clusters_A_or_B"],
           "eligible_clusters_A_and_B": len(both), "eligible_clusters_per_variant": {
               v: sum(1 for x in el["cells"].values() if x["variant"] == v and x["eligible"]) for v in "AB"},
           "n_records": len(rows), "n_invalid": sum(1 for r in rows if not r["valid"])}
    for how, key in (("mean", "mean_of_repeats"), ("median", "median_of_repeats_sensitivity")):
        sc = cell_scores(rows, how)
        ids = [c for c in both if f"primary:A:{c}" in sc and f"primary:B:{c}" in sc]
        dd = {c: sc[f"primary:B:{c}"] - sc[f"primary:A:{c}"] for c in ids}
        r = contrast_from_d(dd)
        r["n_missing"] = len(both) - len(ids)
        if ids:
            r["mean_J_A"] = float(np.mean([sc[f"primary:A:{c}"] for c in ids]))
            r["mean_J_B"] = float(np.mean([sc[f"primary:B:{c}"] for c in ids]))
        if how == "mean":
            r["coverage_both_set"] = {v: coverage_ci(sc, ids, v) for v in "AB"}
            ea = [x["cq_id"] for x in el["cells"].values() if x["variant"] == "A" and x["eligible"]]
            eb = [x["cq_id"] for x in el["cells"].values() if x["variant"] == "B" and x["eligible"]]
            r["coverage_all_eligible"] = {"A": coverage_ci(sc, ea, "A"), "B": coverage_ci(sc, eb, "B")}
            r["_d"] = dd
        res[key] = r
    res["verbatim"] = verbatim_summary(rows)
    return res


def pooled(per_domain: dict[str, dict], judge: str) -> dict | None:
    ds = [d for d in per_domain if judge in per_domain[d] and per_domain[d][judge]["mean_of_repeats"].get("_d")]
    if len(ds) < 2:
        return None
    out = {"domains": ds}
    for key, how in (("mean_of_repeats", "mean"), ("median_of_repeats_sensitivity", "median")):
        dd = {}
        for d in ds:
            sc = cell_scores(load_scores(d, judge), how)
            el = json.loads((C.ddir(d) / "eligibility.json").read_text(encoding="utf-8"))
            for c in el["eligible_in_both"]:
                if f"primary:A:{c}" in sc and f"primary:B:{c}" in sc:
                    dd[f"{d}:{c}"] = sc[f"primary:B:{c}"] - sc[f"primary:A:{c}"]
        r = contrast_from_d(dd)
        r["per_domain_n"] = {d: sum(1 for k in dd if k.startswith(d + ":")) for d in ds}
        out[key] = r
    vs = {}
    for v in "AB":
        k = sum(per_domain[d][judge]["verbatim"][v]["verbatim_strict"] for d in ds)
        n = sum(per_domain[d][judge]["verbatim"][v]["credits_J_ge_2"] for d in ds)
        vs[v] = {"credits_J_ge_2": n, "verbatim_strict": k, "share_strict": (k / n) if n else None}
    out["verbatim"] = vs
    return out


def _f(x, k=3):
    return "n/a" if x is None else f"{x:.{k}f}"


def report(res: dict) -> str:
    L = [f"# Addendum 35 results -- {BANNER}", "",
         "Post hoc, judge-score only. Banks are AI drafts not reviewed by an author. Extractor: the paper's model id on a different serving deployment; judges GLM-4.7-Flash and gpt-oss-20b (non-Qwen), each its own analysis. Views: question-only sub-graphs (not the full renderings).", ""]
    for d, b in res.get("builds", {}).items():
        L.append(f"- build {d}: {b['atomic_chunks']} chunks / {b['corpus_chars']} chars; triples A {b['triples']['A']}, B {b['triples']['B']}; baseline sections skipped {b['build_a_sections_skipped']}; extractor calls failed {b['llm_failures']}; jobs {b['jobs']}; eligible-but-no-subgraph {b['eligible_but_no_subgraph']}")
    L.append("")
    for d, byj in res["domains"].items():
        for j, r in byj.items():
            c = r["mean_of_repeats"]
            L += [f"## {d} -- {r['model']}", f"- bank {r['n_questions']} questions; eligible clusters: A {r['eligible_clusters_per_variant']['A']}, B {r['eligible_clusters_per_variant']['B']}, both {r['eligible_clusters_A_and_B']}; records {r['n_records']} ({r['n_invalid']} invalid)"]
            if c.get("delta") is not None and c["n_clusters"] >= 2:
                cv = c["coverage_both_set"]
                L += [f"- coverage (both-eligible set, 100*sumJ/3n): A {_f(cv['A']['coverage_pct'],1) if cv['A'] else 'n/a'}, B {_f(cv['B']['coverage_pct'],1) if cv['B'] else 'n/a'}; all-eligible: A {_f((c['coverage_all_eligible']['A'] or {}).get('coverage_pct'),1)} (n {(c['coverage_all_eligible']['A'] or {}).get('n_cells')}), B {_f((c['coverage_all_eligible']['B'] or {}).get('coverage_pct'),1)} (n {(c['coverage_all_eligible']['B'] or {}).get('n_cells')})",
                      f"- n {c['n_clusters']} (missing {c['n_missing']}); mean J A {_f(c.get('mean_J_A'))}, B {_f(c.get('mean_J_B'))}; delta {c['delta']:+.3f}, 95% BCa [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}], 90% BCa [{c['ci90'][0]:+.3f}, {c['ci90'][1]:+.3f}]",
                      f"- sign test {c['sign_test']['n_pos']} up / {c['sign_test']['n_neg']} down / {c['sign_test']['n_zero']} tied, p {_f(c['sign_test']['p'],4)}; Wilcoxon p {_f(c['wilcoxon']['p'],4)}",
                      "- MDE: " + ", ".join(f"{k} {v:.3f}" for k, v in c["prospective_mde"].items()) + f"; realized sigma {c['realized_sigma']:.3f} -> {c['realized_mde']:.3f}",
                      f"- decision **{c['decision']}** (rank rule: {c['decision_with_rank_rule']}), margin +-0.50" + ("; UNDERPOWERED (n<10), not interpreted" if c.get("underpowered_flag") else "")]
            else:
                L += [f"- contrast not computable (n {c['n_clusters']})"]
            vb = r["verbatim"]
            L += ["- verbatim-span check (credits J>=2): " + "; ".join(f"{v}: {x['verbatim_strict']}/{x['credits_J_ge_2']} strict, {x['verbatim_elided']}/{x['credits_J_ge_2']} elision-tolerant" for v, x in vb.items()), ""]
    for j, p in res.get("pooled", {}).items():
        if not p:
            continue
        c = p["mean_of_repeats"]
        L += [f"## pooled over {', '.join(p['domains'])} -- {JUDGES[j]}", f"- n {c['n_clusters']} ({p['mean_of_repeats']['per_domain_n']}); delta {c['delta']:+.3f}, 95% BCa [{c['ci95'][0]:+.3f}, {c['ci95'][1]:+.3f}], 90% [{c['ci90'][0]:+.3f}, {c['ci90'][1]:+.3f}]; sign {c['sign_test']['n_pos']}/{c['sign_test']['n_neg']}/{c['sign_test']['n_zero']} p {_f(c['sign_test']['p'],4)}; Wilcoxon p {_f(c['wilcoxon']['p'],4)}; MDE {', '.join(f'{k} {v:.3f}' for k,v in c['prospective_mde'].items())}, realized {c['realized_mde']:.3f}; decision **{c['decision']}**", ""]
    return "\n".join(L)


def tables(res: dict) -> str:
    rows = []
    for d, byj in res["domains"].items():
        for j, r in byj.items():
            c = r["mean_of_repeats"]
            if c.get("delta") is None or c["n_clusters"] < 2:
                continue
            rows.append(f"{d} & {r['model']} & {c['n_clusters']} & {c['mean_J_A']:.2f} & {c['mean_J_B']:.2f} & ${c['delta']:+.3f}$ [${c['ci95'][0]:+.2f}$, ${c['ci95'][1]:+.2f}$] & {c['prospective_mde']['holdout_J_1.343']:.2f} & {c['decision']} \\\\")
    for j, p in res.get("pooled", {}).items():
        if p:
            c = p["mean_of_repeats"]
            rows.append(f"pooled & {JUDGES[j]} & {c['n_clusters']} & -- & -- & ${c['delta']:+.3f}$ [${c['ci95'][0]:+.2f}$, ${c['ci95'][1]:+.2f}$] & {c['prospective_mde']['holdout_J_1.343']:.2f} & {c['decision']} \\\\")
    return "% Addendum 35: " + BANNER + "\n% rows: domain & judge & n & J(A) & J(B) & delta [95% BCa] & MDE(sigma 1.343) & decision\n" + "\n".join(rows) + "\n"


def run(domains: list[str]) -> int:
    res = {"banner": BANNER, "addendum": 35, "seed": SEED, "B": B, "domains": {}, "pooled": {}, "builds": {}}
    for d in domains:
        p = C.ddir(d) / "build_facts.json"
        if p.exists():
            res["builds"][d] = json.loads(p.read_text(encoding="utf-8"))
    for d in domains:
        for j in JUDGES:
            if (C.ddir(d) / f"scores_{j}.csv").exists():
                res["domains"].setdefault(d, {})[j] = domain_result(d, j)
    for j in JUDGES:
        res["pooled"][j] = pooled(res["domains"], j)
    for d in res["domains"].values():
        for r in d.values():
            r["mean_of_repeats"].pop("_d", None)
    (HERE / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (HERE / "REPORT_auto.md").write_text(report(res), encoding="utf-8")
    (HERE / "tables.tex").write_text(tables(res), encoding="utf-8")
    print(report(res))
    return 0


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    if a[:1] == ["extract"]:
        return extract(a[1], a[2])
    if a[:1] == ["run"]:
        ds = a[a.index("--domains") + 1].split(",") if "--domains" in a else ["dcat", "ssn", "prov"]
        return run([d for d in ds if (C.ddir(d) / "eligibility.json").exists()])
    raise SystemExit(__doc__)


if __name__ == "__main__":
    raise SystemExit(main())
