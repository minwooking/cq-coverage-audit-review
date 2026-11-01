#!/usr/bin/env python3
"""Experiment 3 analysis: does the rendering length (not the graph) move the judge's score?

Input: cells_length.jsonl (run_length_judge.py), inputs/manifest.jsonl (make_inputs.py).
Reuses analyze_holdout helpers: cluster_bootstrap_delta (CQ-cluster BCa) and
_qwk_from_values.  Descriptive statistics + intervals only (no pass/fail rule).

Judge error vs information deficit (analysis stage ONLY): the bank's ``grounding``
column is read here, after scoring, to decide whether a condition's input
contained the grounding terms (run_holdout._grounding_match_info(...)["can_ablate"]).
make_inputs.py never sees that column.  Splits, per reduced condition R in
{subgraph, limited}, the pairs where full scored J>=2 and R scored J<=1:
  * grounding present in R's input  -> ``judge_error_candidate`` (judge missed
    evidence it was shown);
  * grounding absent from R's input -> ``information_deficit`` (R did not show it).
The reverse direction (R J>=2, full J<=1) is reported as ``reduced_up``.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HERE))

import analyze_holdout as ah  # noqa: E402
import run_holdout as rh  # noqa: E402

CONDITIONS = ("full", "limited", "subgraph")
CONTRASTS = (("full", "limited"), ("full", "subgraph"), ("limited", "subgraph"))
HIGH, LOW = 2, 1


def load_scores(path: Path) -> tuple[dict[str, dict[str, dict]], Counter]:
    """{condition: {pair_id: record}} of VALID scores, plus invalid counts per condition."""
    by_cond: dict[str, dict[str, dict]] = defaultdict(dict)
    invalid: Counter = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rh._valid_score(rec):
            by_cond[rec["condition"]][rec["pair_id"]] = rec
        else:
            invalid[rec["condition"]] += 1
    return by_cond, invalid


def load_holdout_full(path: Path, manifest: list[dict]) -> dict[str, dict]:
    """Adapter: the holdout run's full-view cells (real_run/cells.jsonl) as condition 'full'.

    Only valid PRIMARY cells whose (variant, cq) is a non-excluded full-condition pair of the
    length manifest are taken; records get ``condition`` and ``pair_id`` (= variant:cq_id)."""
    ok = {(r["variant"], r["cq_id"]) for r in manifest
          if r["condition"] == "full" and r["status"] == "ok" and not r["documented_exclusion"]}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("cell_kind") != "primary" or not rh._valid_score(rec):
            continue
        if (rec["variant"], rec["cq_id"]) not in ok:
            continue
        pid = f"{rec['variant']}:{rec['cq_id']}"
        out[pid] = {**rec, "condition": "full", "pair_id": pid}
    return out


def agreement(by_a: dict, by_b: dict) -> list[dict]:
    """Per condition: agreement of two judges (a = registered, b = other) on matched pairs."""
    rows = []
    for cond in CONDITIONS:
        ids = sorted(set(by_a.get(cond, {})) & set(by_b.get(cond, {})))
        ja = [by_a[cond][i]["J"] for i in ids]
        jb = [by_b[cond][i]["J"] for i in ids]
        n = len(ids)
        rows.append({"condition": cond, "n_pairs": n,
                     "exact_agreement": (sum(x == y for x, y in zip(ja, jb)) / n) if n else None,
                     "qwk": ah._qwk_from_values(ja, jb) if n >= 2 else None,
                     "mean_registered": (sum(ja) / n) if n else None,
                     "mean_other": (sum(jb) / n) if n else None})
    return rows


def distribution(scores: dict[str, dict]) -> dict:
    js = [r["J"] for r in scores.values()]
    n = len(js)
    return {"n": n, "counts": {str(k): js.count(k) for k in range(4)},
            "mean": (sum(js) / n) if n else None,
            "coverage_j_ge2": (sum(1 for j in js if j >= HIGH) / n) if n else None}


def paired(by_cond, a: str, b: str) -> list[tuple[str, dict, dict]]:
    ids = sorted(set(by_cond.get(a, {})) & set(by_cond.get(b, {})))
    return [(i, by_cond[a][i], by_cond[b][i]) for i in ids]


def contrast(by_cond, a: str, b: str, *, B: int, seed: int) -> dict:
    """Mean of (J_a - J_b) over matched pairs with a CQ-cluster BCa interval."""
    pairs = paired(by_cond, a, b)
    out: dict = {"contrast": f"{a}-{b}", "n_pairs": len(pairs)}
    if not pairs:
        return {**out, "mean_diff": None, "qwk": None, "exact_agreement": None, "interval": None}
    deltas_by_cluster: dict[str, list[float]] = defaultdict(list)
    for _, ra, rb in pairs:
        deltas_by_cluster[ra["cluster_id"]].append(ra["J"] - rb["J"])
    ja, jb = [p[1]["J"] for p in pairs], [p[2]["J"] for p in pairs]
    out["mean_diff"] = sum(x - y for x, y in zip(ja, jb)) / len(pairs)
    out["exact_agreement"] = sum(x == y for x, y in zip(ja, jb)) / len(pairs)
    out["qwk"] = ah._qwk_from_values(ja, jb)
    out["n_clusters"] = len(deltas_by_cluster)
    if len(deltas_by_cluster) >= 2:
        r = ah.cluster_bootstrap_delta(deltas_by_cluster, resamples=B, seed=seed)
        out["interval"] = {"cluster_mean_diff": r["delta"], "ci95": [r["ci_lo"], r["ci_hi"]],
                           "ci90": [r["ci90_lo"], r["ci90_hi"]], "method": "BCa cluster bootstrap",
                           "resamples": B, "seed": seed}
    else:
        out["interval"] = None
    return out


def grounding_flags(manifest: list[dict], bank_path: Path, inputs_root: Path | None = None) -> dict:
    """{(condition, variant, cq_id): bool} - grounding terms present in that condition's input.

    ANALYSIS-ONLY use of the bank's grounding column (see module docstring)."""
    with bank_path.open(encoding="utf-8", newline="") as fh:
        bank = {r["cq_id"]: r for r in csv.DictReader(fh)}
    flags: dict[tuple, bool] = {}
    view_cache: dict[str, str] = {}
    for rec in manifest:
        if rec["status"] != "ok" or rec["condition"] == "full":
            continue
        p = Path(rec["path"])
        p = p if p.is_absolute() else (inputs_root or ACCESS) / p
        if str(p) not in view_cache:
            view_cache[str(p)] = p.read_text(encoding="utf-8")
        flags[(rec["condition"], rec["variant"], rec["cq_id"])] = bool(
            rh._grounding_match_info(view_cache[str(p)], bank[rec["cq_id"]])["can_ablate"])
    return flags


def separation(by_cond, flags: dict, reduced: str) -> dict:
    """Judge-error vs information-deficit split for ``reduced`` against ``full``."""
    pairs = paired(by_cond, "full", reduced)
    res = Counter()
    for pid, rf, rr in pairs:
        variant, cq = pid.split(":", 1)
        present = flags.get((reduced, variant, cq))
        if present is None:
            res["no_grounding_flag"] += 1
            continue
        if rf["J"] >= HIGH and rr["J"] <= LOW:
            res["judge_error_candidate" if present else "information_deficit"] += 1
        elif rr["J"] >= HIGH and rf["J"] <= LOW:
            res["reduced_up_grounding_present" if present else "reduced_up_grounding_absent"] += 1
    base = sum(1 for _, rf, _ in pairs if rf["J"] >= HIGH)
    return {"reduced_condition": reduced, "n_pairs": len(pairs), "n_full_J_ge2": base,
            "judge_error_candidate": res["judge_error_candidate"],
            "information_deficit": res["information_deficit"],
            "reduced_up_grounding_present": res["reduced_up_grounding_present"],
            "reduced_up_grounding_absent": res["reduced_up_grounding_absent"],
            "no_grounding_flag": res["no_grounding_flag"]}


def not_applicable_count(manifest: list[dict]) -> dict:
    return dict(Counter(r["condition"] for r in manifest if r["status"] != "ok"))


def restrict(by_cond: dict, variant: str | None) -> dict:
    """Same structure limited to one variant (None = all variants)."""
    if variant is None:
        return by_cond
    return {c: {k: r for k, r in d.items() if r["variant"] == variant} for c, d in by_cond.items()}


def analyze(cells: Path, manifest_path: Path, bank: Path, *, B: int, seed: int,
            holdout_cells: Path | None = None, compare_cells: Path | None = None,
            extra_full_cells: Path | None = None, per_variant: bool = False,
            sensitivity_variants: tuple[str, ...] = ()) -> dict:
    by_cond, invalid = load_scores(cells)
    if extra_full_cells is not None:
        # addendum 23: new luna full cells (B-F) join the existing luna cells' full (A) condition
        extra, extra_invalid = load_scores(extra_full_cells)
        by_cond["full"].update(extra.get("full", {}))
        extra_note = f"luna cells_length (full: A) + {extra_full_cells.parent.name} (full: B-F)"
        invalid = invalid + extra_invalid
    manifest = [json.loads(l) for l in manifest_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if holdout_cells is not None:
        by_cond["full"] = load_holdout_full(holdout_cells, manifest)
    flags = grounding_flags(manifest, bank)
    extra: dict = {}
    if extra_full_cells is not None:
        extra["full_source"] = extra_note
    if holdout_cells is not None:
        extra["full_source"] = f"holdout cells reused: {holdout_cells.name}"
    if compare_cells is not None:
        other, _ = load_scores(compare_cells)
        extra["agreement_with_other_judge"] = {"cells": str(compare_cells.name),
                                               "rows": agreement(by_cond, other)}
    pv: dict = {}
    if per_variant:
        for v in sorted({r["variant"] for d in by_cond.values() for r in d.values()}):
            bv = restrict(by_cond, v)
            pv[v] = {"distribution": {c: distribution(bv.get(c, {})) for c in CONDITIONS},
                     "contrasts": [contrast(bv, a, b, B=B, seed=seed) for a, b in CONTRASTS]}
    if sensitivity_variants:
        # analysis-only sensitivity: pooled over the listed variants (e.g. only variants whose full view is complete)
        sv = {c: {k: r for k, r in d.items() if r["variant"] in sensitivity_variants} for c, d in by_cond.items()}
        extra["pooled_sensitivity"] = {
            "variants": list(sensitivity_variants),
            "distribution": {c: distribution(sv.get(c, {})) for c in CONDITIONS},
            "contrasts": [contrast(sv, a, b, B=B, seed=seed) for a, b in CONTRASTS],
            "separation": [separation(sv, flags, r) for r in ("subgraph", "limited")]}
    return {
        **extra,
        **({"per_variant": pv} if per_variant else {}),
        "seed": seed, "resamples": B,
        "distribution": {c: distribution(by_cond.get(c, {})) for c in CONDITIONS},
        "distribution_by_variant": {
            c: {v: distribution({k: r for k, r in by_cond.get(c, {}).items() if r["variant"] == v})
                for v in sorted({r["variant"] for r in by_cond.get(c, {}).values()})}
            for c in CONDITIONS},
        "invalid_records": dict(invalid),
        "not_applicable_inputs": not_applicable_count(manifest),
        "contrasts": [contrast(by_cond, a, b, B=B, seed=seed) for a, b in CONTRASTS],
        "separation": [separation(by_cond, flags, r) for r in ("subgraph", "limited")],
    }


def _f(x, nd=3):
    return "-" if x is None else f"{x:.{nd}f}"


def report_ko(res: dict) -> str:
    """Korean markdown summary (descriptive; exploratory, post hoc after the luna run)."""
    if res.get("per_variant") is not None and "luna_full_r35" in str(res.get("full_source", "")):
        head = ["# luna 길이 실험 완결 보고 — full 뷰 B–F 추가 (addendum 23, 탐색적·사후)", "",
                "> 자동 생성. 지위: 탐색적·사후. judge는 gpt-5.6-luna 하나(<internal-proxy>). full = A(기존) + B–F(신규); limited·subgraph = 기존 luna 셀.", ""]
    else:
        head = ["# 등록 judge(gemini-3.6-flash) 길이 실험 재채점 보고 (addendum 22, 탐색적·사후)", "",
                "> 자동 생성. 지위: luna 실행 뒤에 한 사후 탐색 분석이며 확증이 아니다. full 조건은 holdout 셀 재사용.", ""]
    L = head + [
         f"- 시드 {res['seed']}, 부트스트랩 {res['resamples']}회, 질문 군집 BCa.",
         f"- full 출처: {res.get('full_source', '-')}", "", "## 점수 분포", "",
         "| 조건 | n | 0 | 1 | 2 | 3 | 평균 | 커버리지(J≥2) |", "|---|---|---|---|---|---|---|---|"]
    for c, d in res["distribution"].items():
        k = d["counts"]
        L.append(f"| {c} | {d['n']} | {k['0']} | {k['1']} | {k['2']} | {k['3']} | {_f(d['mean'])} | {_f(d['coverage_j_ge2'])} |")
    L += ["", "## 대비 (앞 − 뒤, 짝지은 셀)", "",
          "| 대비 | 쌍 | 군집 | 평균차 | 95% BCa | QWK | 정확 일치 |", "|---|---|---|---|---|---|---|"]
    for c in res["contrasts"]:
        iv = c.get("interval")
        ci = f"[{_f(iv['ci95'][0])}, {_f(iv['ci95'][1])}]" if iv else "-"
        L.append(f"| {c['contrast']} | {c['n_pairs']} | {c.get('n_clusters', '-')} | {_f(c['mean_diff'])} | "
                 f"{ci} | {_f(c['qwk'])} | {_f(c['exact_agreement'])} |")
    L += ["", "## 정보 부족 대 judge 오류 (분석 단계에서만 grounding 열 사용)", "",
          "| 축소 조건 | 쌍 | full J≥2 | judge 오류 후보 | 정보 부족 | 축소가 더 높음(근거 있음/없음) |", "|---|---|---|---|---|---|"]
    for s in res["separation"]:
        L.append(f"| {s['reduced_condition']} | {s['n_pairs']} | {s['n_full_J_ge2']} | {s['judge_error_candidate']} | "
                 f"{s['information_deficit']} | {s['reduced_up_grounding_present']}/{s['reduced_up_grounding_absent']} |")
    pv = res.get("per_variant")
    if pv:
        L += ["", "## variant별 (luna, full 뷰 B–F 신규 + A 기존)", "",
              "| variant | 조건 | n | 평균 J | 커버리지(J≥2) |", "|---|---|---|---|---|"]
        for v, d in pv.items():
            for c, dd in d["distribution"].items():
                L.append(f"| {v} | {c} | {dd['n']} | {_f(dd['mean'])} | {_f(dd['coverage_j_ge2'])} |")
        L += ["", "| variant | 대비 | 쌍 | 평균차 | 95% BCa | 정확 일치 | QWK |", "|---|---|---|---|---|---|---|"]
        for v, d in pv.items():
            for c in d["contrasts"]:
                iv = c.get("interval")
                ci = f"[{_f(iv['ci95'][0])}, {_f(iv['ci95'][1])}]" if iv else "-"
                L.append(f"| {v} | {c['contrast']} | {c['n_pairs']} | {_f(c['mean_diff'])} | {ci} | "
                         f"{_f(c['exact_agreement'])} | {_f(c['qwk'])} |")
    ps = res.get("pooled_sensitivity")
    if ps:
        L += ["", f"## 민감도: 풀링을 {','.join(ps['variants'])}로 제한 (full 뷰가 완결된 변형)", "",
              "| 조건 | n | 평균 J | 커버리지(J≥2) |", "|---|---|---|---|"]
        for c, dd in ps["distribution"].items():
            L.append(f"| {c} | {dd['n']} | {_f(dd['mean'])} | {_f(dd['coverage_j_ge2'])} |")
        L += ["", "| 대비 | 쌍 | 평균차 | 95% BCa | 정확 일치 | QWK |", "|---|---|---|---|---|---|"]
        for c in ps["contrasts"]:
            iv = c.get("interval")
            ci = f"[{_f(iv['ci95'][0])}, {_f(iv['ci95'][1])}]" if iv else "-"
            L.append(f"| {c['contrast']} | {c['n_pairs']} | {_f(c['mean_diff'])} | {ci} | "
                     f"{_f(c['exact_agreement'])} | {_f(c['qwk'])} |")
    ag = res.get("agreement_with_other_judge")
    if ag:
        L += ["", f"## 다른 judge({ag['cells']})와의 일치", "",
              "| 조건 | 쌍 | 정확 일치 | QWK | 평균(등록) | 평균(다른) |", "|---|---|---|---|---|---|"]
        for r in ag["rows"]:
            L.append(f"| {r['condition']} | {r['n_pairs']} | {_f(r['exact_agreement'])} | {_f(r['qwk'])} | "
                     f"{_f(r['mean_registered'])} | {_f(r['mean_other'])} |")
    L += ["", f"무효 기록: {res['invalid_records']}; 적용 불가 입력: {res['not_applicable_inputs']}", ""]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells", type=Path, default=HERE / "cells_length.jsonl")
    ap.add_argument("--manifest", type=Path, default=HERE / "inputs" / "manifest.jsonl")
    ap.add_argument("--bank", type=Path, default=ACCESS / "bank" / "cq_bank_brick_v1.csv")
    ap.add_argument("--resamples", type=int, default=ah.BOOTSTRAP_RESAMPLES)
    ap.add_argument("--seed", type=int, default=ah.REGISTERED_SEED)
    ap.add_argument("--out", type=Path, default=HERE / "results_length.json")
    ap.add_argument("--holdout-cells", type=Path, default=None,
                    help="reuse the holdout full-view cells (real_run/cells.jsonl) as condition 'full'")
    ap.add_argument("--compare-cells", type=Path, default=None,
                    help="another judge's cells (e.g. luna cells_length.jsonl) for agreement")
    ap.add_argument("--report-ko", type=Path, default=None, help="write a Korean markdown report")
    ap.add_argument("--extra-full-cells", type=Path, default=None,
                    help="addendum 23: additional full-condition cells (luna_full_r35) merged into --cells")
    ap.add_argument("--sensitivity-variants", default="",
                    help="comma list: also report pooled contrasts over these variants only")
    ap.add_argument("--per-variant", action="store_true", help="also report distributions and contrasts per variant")
    a = ap.parse_args()
    res = analyze(a.cells, a.manifest, a.bank, B=a.resamples, seed=a.seed,
                  holdout_cells=a.holdout_cells, compare_cells=a.compare_cells,
                  extra_full_cells=a.extra_full_cells, per_variant=a.per_variant,
                  sensitivity_variants=tuple(v for v in a.sensitivity_variants.split(",") if v))
    a.out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    if a.report_ko:
        a.report_ko.write_text(report_ko(res), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
