#!/usr/bin/env python3
"""Addendum 34 A1: A->B judge-score contrast per bank, pooled over Brick-holdout-graph banks (clustered by source question)
and per domain.  AI-generated; review and test before use.  Reads judge records only; no label, no model call.
Judge-score contrast; not human-labelled."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "study2_llm_labels"))
sys.path.insert(0, str(HERE))
import analyze as an  # noqa: E402

JUDGES = an.JUDGES
BANNER = "judge-score contrast (J, subgraph views, named non-registered judges) across question banks; not human-labelled; only the holdout and expansion banks are frozen, the rest are AI-draft/unreviewed"
R6 = HARNESS / "review6_judges" / "raw"
NAT = HARNESS / "review6_natural" / "raw"
S2 = HARNESS / "study2_llm_labels"
MAN10 = HARNESS / "review10_llm_labels" / "manifests"


def read(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def cell_means(recs: list[dict], study_prefix: str | None = None) -> dict[str, float]:
    by: dict[str, list[int]] = {}
    for r in recs:
        if study_prefix and not str(r.get("study", "")).startswith(study_prefix):
            continue
        if r.get("valid") and r.get("J") is not None:
            by.setdefault(r["cell_id"], []).append(int(r["J"]))
    return {c: sum(v) / len(v) for c, v in by.items()}


def to_bank(scores: dict[str, float], prefix: str, ok, require_both: bool = True) -> dict[str, dict[str, float]]:
    """{cluster: {"A": J, "B": J}} for cells 'prefix:V:cq' that satisfy ok(variant, cq)."""
    out: dict[str, dict[str, float]] = {}
    for cid, j in scores.items():
        p = cid.split(":")
        if len(p) != 3 or p[0] != prefix or p[1] not in "AB" or not ok(p[1], p[2]):
            continue
        out.setdefault(p[2], {})[p[1]] = j
    return {c: v for c, v in out.items() if not require_both or ("A" in v and "B" in v)}


def v2x_eligible() -> set[tuple[str, str]]:
    import run_holdout as rh
    import s2_views as V
    rows = {r["cq_id"]: r for r in csv.DictReader((HARNESS.parent / "bank" / "cq_bank_brick_v2.csv").open(encoding="utf-8"))}
    ok = set()
    for v in "AB":
        text = V.rendering(v)
        for cq in {r["cq_id"] for r in json.loads((MAN10 / "v2x.json").read_text())["rows"]}:
            if rh._grounding_match_info(text, {"grounding": rows[cq]["grounding"]})["can_ablate"]:
                ok.add((v, cq))
    return ok


def build_banks(judge: str, require_both: bool = True) -> dict[str, dict]:
    m6 = json.loads((HARNESS / "review6_raters" / "cells_manifest.json").read_text())["cells"]
    holdout_ok = {(c["variant"], c["cq_id"]) for c in m6}
    s3 = cell_means(read(HERE / "raw" / f"judge_{judge}_s3.jsonl"))
    r6 = read(R6 / f"raw_{judge}.jsonl")
    v2ok = v2x_eligible()
    # Stage 2: eligible cells only
    s2 = cell_means(read(S2 / "raw" / f"judge_{judge}_stage2.jsonl"))
    B = {}
    B["holdout"] = dict(bank=to_bank(cell_means(r6, "holdout_subgraph"), "primary", lambda v, q: (v, q) in holdout_ok, require_both=require_both), frozen=True, view="subgraph", elig="paper rule (registered 188 primary cells)", pool="brick")
    B["paraphrases"] = dict(bank=to_bank(s3, "para", lambda v, q: (v, q) in holdout_ok, require_both=require_both), frozen=False, view="subgraph",
                            elig="paper rule via source question's grounding", pool="brick")
    B["v2_extras"] = dict(bank=to_bank(s3, "v2x", lambda v, q: (v, q) in v2ok, require_both=require_both), frozen=False, view="subgraph",
                          elig="paper rule (v2 bank grounding)", pool="brick")
    B["expansion"] = dict(bank=to_bank(s2, "primary", lambda v, q: True, require_both=require_both), frozen=True, view="subgraph",
                          elig="paper rule (Stage 2 eligible cells)", pool="brick")
    B["dev_summary"] = dict(bank=to_bank(cell_means(r6, "dev"), "dev", lambda v, q: True, require_both=require_both), frozen=False, view="dev rendering summary",
                            elig="view-exists", pool="dev")
    B["dev_ext_subgraph"] = dict(bank=to_bank(s3, "dev", lambda v, q: True, require_both=require_both), frozen=False, view="subgraph", elig="view-exists", pool="dev")
    B["natural_docs"] = dict(bank=to_bank(cell_means(read(NAT / f"raw_{judge}_natural.jsonl")), "natural", lambda v, q: True),
                             frozen=False, view="subgraph", elig="view-exists (36 question S_full)", pool="natural")
    mf = {}
    for pre in ("mfg", "mfgko"):
        mf[pre] = to_bank(s3, pre, lambda v, q: True, require_both)
    B["second_domain_mfg"] = dict(bank=pool([mf["mfg"], mf["mfgko"]]) if require_both else merge_partial([mf["mfg"], mf["mfgko"]]),
                                  frozen=False, view="subgraph", elig="view-exists", pool="second", aggregate_only=True)
    return B


def merge_partial(banks: list[dict]) -> dict[str, dict[str, float]]:
    """Union of partial banks: per cluster and variant, the mean over the banks that hold that variant."""
    acc: dict[str, dict[str, list[float]]] = {}
    for b in banks:
        for c, v in b.items():
            for var, j in v.items():
                acc.setdefault(c, {}).setdefault(var, []).append(j)
    return {c: {var: sum(l) / len(l) for var, l in v.items()} for c, v in acc.items()}


def pool(banks: list[dict]) -> dict[str, dict[str, float]]:
    """Cluster = source question id.  Per cluster: mean over contributing banks of A and of B."""
    acc: dict[str, list[tuple[float, float]]] = {}
    for b in banks:
        for c, v in b.items():
            acc.setdefault(c, []).append((v["A"], v["B"]))
    return {c: {"A": sum(a for a, _ in l) / len(l), "B": sum(b for _, b in l) / len(l)} for c, l in acc.items()}


def summarize(bank: dict[str, dict[str, float]]) -> dict | None:
    if len(bank) < 3:
        return {"n_clusters": len(bank), "note": "fewer than 3 eligible clusters; no interval"}
    scores = {}
    for c, v in bank.items():
        scores[f"primary:A:{c}"], scores[f"primary:B:{c}"] = v["A"], v["B"]
    return an.contrast(scores, set(bank))


def main() -> int:
    out = {"banner": BANNER, "addendum": "34 A1", "judges": {}}
    for j in JUDGES:
        B = build_banks(j)
        res = {"banks": {}, "pools": {}, "domains": {}}
        for name, b in B.items():
            s = summarize(b["bank"])
            res["banks"][name] = {"frozen": b["frozen"], "view": b["view"], "eligibility": b["elig"], **s}
        brick = [B[k]["bank"] for k in ("holdout", "paraphrases", "v2_extras", "expansion")]
        res["pools"]["brick_frozen_only (holdout)"] = summarize(pool([brick[0]]))
        res["pools"]["brick_frozen (holdout + expansion; expansion unreviewed)"] = summarize(pool([brick[0], brick[3]]))
        res["pools"]["brick_all (+ paraphrases, v2 extras; AI-draft)"] = summarize(pool(brick))
        res["domains"]["brick holdout graphs (all pool)"] = res["pools"]["brick_all (+ paraphrases, v2 extras; AI-draft)"]
        res["domains"]["development corpus (summary + ext subgraph, clustered by question)"] = summarize(pool([B["dev_summary"]["bank"], B["dev_ext_subgraph"]["bank"]]))
        res["domains"]["natural Brick documentation"] = res["banks"]["natural_docs"]
        res["domains"]["second domain (aggregate only)"] = res["banks"]["second_domain_mfg"]
        out["judges"][j] = {"model": JUDGES[j], **res}
    (HERE / "results_all.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (HERE / "REPORT_all.md").write_text(report(out), encoding="utf-8")
    (HERE / "tables_all.tex").write_text(tables(out), encoding="utf-8")
    return 0


def _row(name, s):
    if "delta" not in s:
        return f"| {name} | {s.get('n_clusters')} | - | - | - | - | - | - | {s.get('note','')} |"
    m = s.get("prospective_mde")
    mde = f"{m['prespecified_1.155']:.2f} / {m['holdout_J_1.343']:.2f} / {s['realized_mde']:.2f}" if m else "-"
    p = s.get("sign_test", {}).get("p")
    return (f"| {name} | {s['n_clusters']} | {s['mean_J_A']:.3f} | {s['mean_J_B']:.3f} | {s['delta']:+.3f} [{s['ci95'][0]:+.3f}, {s['ci95'][1]:+.3f}] | "
            f"{mde} | {'-' if p is None else f'{p:.3f}'} / {'-' if not s.get('wilcoxon') or s['wilcoxon']['p'] is None else f'{s['wilcoxon']['p']:.3f}'} | {s.get('decision','-')} | |")


def report(out: dict) -> str:
    L = [f"# Addendum 34 A1 -- {BANNER}", "", inventory(out), "", "Post hoc. Mean of repeats per cell; paired B - A per cluster; BCa 95% (seed 20260913, B = 10,000). MDE at sigma 1.155 / 1.343 / realized. Frozen = holdout and expansion (hash/tag); all other banks are AI-draft/unreviewed and sit in separate rows.", ""]
    hdr = "| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |\n|---|---|---|---|---|---|---|---|---|"
    for j, r in out["judges"].items():
        L += [f"## {r['model']}", "", "### (a) per bank", hdr]
        for k, s in r["banks"].items():
            L.append(_row(f"{k} ({'frozen' if s['frozen'] else 'AI-draft'}; {s['view']}; elig {s['eligibility']})", s))
        L += ["", "### (b) pooled, Brick holdout graphs, clustered by source question", hdr] + [_row(k, s) for k, s in r["pools"].items()]
        L += ["", "### (c) per domain", hdr] + [_row(k, s) for k, s in r["domains"].items()] + [""]
    return "\n".join(L)


INV = [  # bank, manifest/source, frozen, blind (as documented; not re-audited unless stated)
    ("holdout", None, "yes (registered, PREREG freeze)", "as documented in the paper; not re-audited here"),
    ("paraphrases (Tier 3a)", "para", "no freeze record checked", "AI-completed paraphrases of the holdout questions; same grounding as source"),
    ("v2 extras (Tier 3b)", "v2x", "no freeze record checked (v2 pool, 60 rows)", "not assessed here"),
    ("expansion (Study 2)", "exp", "yes (sha256 a39bcc0f..., tag access2026-study2-bank-freeze)", "artifact-blind per README, static builder scan only (BANK_PROVENANCE); author-unreviewed AI draft"),
    ("development (Ontology-101)", "dev", "no", "not assessed; extended bank adds CQ17-18"),
    ("natural documentation (Brick)", None, "no (same 36 holdout questions, other graphs)", "analyst-read grounding check before build, not blind (addendum 27)"),
    ("second domain (manufacturing)", "mfg", "no", "aggregate only"),
]


def inventory(out: dict) -> str:
    L = ["### Inventory (questions with A and B variant graphs)", "", "| bank | questions | with A and B view | eligible clusters in A and B (glm / gptoss) | frozen | artifact-blind |", "|---|---|---|---|---|---|"]
    key = {"holdout": "holdout", "paraphrases (Tier 3a)": "paraphrases", "v2 extras (Tier 3b)": "v2_extras", "expansion (Study 2)": "expansion",
           "development (Ontology-101)": "dev_summary", "natural documentation (Brick)": "natural_docs", "second domain (manufacturing)": "second_domain_mfg"}
    for name, man, fz, bl in INV:
        nq = nab = "-"
        if man:
            m = json.loads((MAN10 / f"{man}.json").read_text(encoding="utf-8"))
            qs = {r["cq_id"] for r in m["rows"]}
            both = {q for q in qs if {"A", "B"} <= {r["variant"] for r in m["rows"] if r["cq_id"] == q}}
            nq, nab = m["n_questions"], len(both)
        elif name == "holdout":
            nq, nab = 36, "36 subgraph views exist; 22 with both A and B scored-eligible"
        else:
            nq, nab = 36, 36
        el = " / ".join(str(out["judges"][j]["banks"][key[name]]["n_clusters"]) for j in out["judges"])
        L.append(f"| {name} | {nq} | {nab} | {el} | {fz} | {bl} |")
    L += ["", "Heterogeneity is visible and not tested here: gpt-oss-20b has holdout +0.409 but expansion -0.564, so the pooled Brick estimate mixes banks that disagree in sign for that judge. Pooling raises n but is a different estimand than the holdout's.", ""]
    return "\n".join(L)


def tables(out: dict) -> str:
    L = ["% Addendum 34 A1: " + BANNER, "% rows: judge & row & n & J(A) & J(B) & delta [95% BCa] & MDE(1.343) & decision"]
    for j, r in out["judges"].items():
        for grp in ("banks", "pools", "domains"):
            for k, s in r[grp].items():
                if "delta" not in s:
                    continue
                kk = k.replace("_", "\\_").replace("&", "\\&")
                L.append(f"{r['model']} & {kk} & {s['n_clusters']} & {s['mean_J_A']:.2f} & {s['mean_J_B']:.2f} & ${s['delta']:+.2f}$ [${s['ci95'][0]:+.2f}$, ${s['ci95'][1]:+.2f}$] & {s['prospective_mde']['holdout_J_1.343'] if 'prospective_mde' in s else float('nan'):.2f} & {s.get('decision','-')} \\\\" if 'prospective_mde' in s else f"{r['model']} & {kk} & {s['n_clusters']} & {s['mean_J_A']:.2f} & {s['mean_J_B']:.2f} & ${s['delta']:+.2f}$ [${s['ci95'][0]:+.2f}$, ${s['ci95'][1]:+.2f}$] & - & aggregate only \\\\")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
