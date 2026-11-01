#!/usr/bin/env python3
# AI-generated analysis script (Claude, 2026-10-24). Human review required before use.
"""다중 평가자(H1/H2/H3) 내보내기 분석 — 기존 파일을 하나도 수정하지 않는다.

입력(읽기 전용):
  ../human_labels_export_2026-10-15.csv  … 라벨링 사이트 내보내기(불투명 cell_id)
  ../site_key_2026-10-13.csv             … opaque -> 원 cell_id/variant/cq_id 키(188셀, primary만)
  ../../../labeling_sheet_key_2026-10-13.csv … AH 라벨(cell_id,J,S_AH,L1_star,…; 저장소 내 AH 위치)
  ../../../../harness/real_run/cells.jsonl   … 등록 판정 J(224셀: primary 188 + control 36)
  G2 존재 확인: ../../../harness/real_run/annotation_pending/washout_pass_72_ready_to_fill.csv

출력(이 폴더에만 씀):
  consensus_labels.csv      … 다수결 consensus(분석기 호환 열 cell_id,A,rater_L1,evidence_span_verbatim + 근거 열)
  keys/key_<RID>.csv        … compute_multirater_agreement.py --keys-dir 형식 변환물
  filled/<RID>.csv          … 같은 스크립트의 --filled 형식 변환물(cell_id는 불투명 ID)
  results_multirater.json   … 아래 통계 전부

계산: rater 쌍별 n/%-agreement/Cohen κ(S)/QWK(R)/MAE(R), consensus vs AH, consensus vs J
(CQ 군집 부트스트래프 percentile CI, seed 20260913, B=10000 — 탐색적. 등록 BCa는
harness/analyze_holdout.py 결과를 따름), dwell 요약, note 기계 판정 가능 서명, 겹침 비율,
G2 재평가 데이터 존재 여부. 기존 compute_multirater_agreement.py의 κ/판정-대조 함수는
수정 없이 재사용한다(import; 그 스크립트는 --json-out 외 쓰는 곳 없음 — 확인함).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent                      # multirater_2026-10
ANNO = BASE.parent                      # paper/access2026/annotation
PAPER = ANNO.parent                     # paper/access2026
sys.path.insert(0, str(BASE))           # compute_multirater_agreement.py 재사용
from compute_multirater_agreement import cohen_kappa  # noqa: E402  (수정 없이 import)

SEED = 20260913
BOOT_B = 10000
G7_FAST_MS = 20_000
# second_pass v2 시트의 단일 문구 서명(annotation/second_pass_2026-10-13/REPORT_ko.md §1)
V2_TEMPLATES = [
    "AI exploratory draft; verify against rendered view.",
    "Related concept appears, but the requested defining detail/relation is not stated.",
]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def qwk(left: list[int], right: list[int], maximum: int = 3) -> float:
    """이차 가중 κ(등록 분석기와 동일 가중 (i-j)^2, 동일 퇴화 규칙)."""
    n = len(left)
    if n == 0 or n != len(right):
        return float("nan")
    obs = sum((a - b) ** 2 for a, b in zip(left, right)) / n
    lc = [sum(v == s for v in left) for s in range(maximum + 1)]
    rc = [sum(v == s for v in right) for s in range(maximum + 1)]
    exp = sum(lc[i] * rc[j] * (i - j) ** 2
              for i in range(maximum + 1) for j in range(maximum + 1)) / (n * n)
    if exp == 0:
        return 1.0 if obs == 0 else 0.0
    return 1.0 - obs / exp


def mae(left: list[int], right: list[int]) -> float:
    return sum(abs(a - b) for a, b in zip(left, right)) / len(left) if left else float("nan")


def cluster_bootstrap(records: list[dict], stat, clusters_key: str = "cluster",
                      b: int = BOOT_B, seed: int = SEED) -> dict:
    """CQ 군집 재추출 percentile CI(탐색적; 등록 BCa와 다른 방법임을 보고에 명시)."""
    clusters = sorted({r[clusters_key] for r in records})
    by = {c: [r for r in records if r[clusters_key] == c] for c in clusters}
    rng = random.Random(seed)
    draws = []
    for _ in range(b):
        sample: list[dict] = []
        for _ in range(len(clusters)):
            sample.extend(by[clusters[rng.randrange(len(clusters))]])
        if len({r[clusters_key] for r in sample}) < 2:
            continue
        try:
            draws.append(stat(sample))
        except (ValueError, ZeroDivisionError):
            continue
    draws.sort()
    if not draws:
        return {"ci_lo": None, "ci_hi": None, "b_effective": len(draws)}

    def pct(q: float) -> float:
        idx = min(len(draws) - 1, max(0, int(round(q * (len(draws) - 1)))))
        return draws[idx]
    return {"ci_lo": pct(0.025), "ci_hi": pct(0.975), "b_effective": len(draws)}


def read_csv(p: Path) -> list[dict]:
    with p.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    export = read_csv(BASE / "human_labels_export_2026-10-15.csv")
    site_key = {r["opaque"]: r for r in read_csv(BASE / "site_key_2026-10-13.csv")
                if r["kind"] == "cell"}
    ah_key = {r["cell_id"]: r for r in read_csv(PAPER / "annotation" / "labeling_sheet_key_2026-10-13.csv")}
    cells = {}
    with (PAPER / "harness" / "real_run" / "cells.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            d = json.loads(line)
            cells[d["cell_id"]] = d

    # ---------- 라벨 → 원 cell_id 조인 ----------
    rows = []
    unmapped = []
    for r in export:
        k = site_key.get(r["cell_id"])
        if k is None:
            unmapped.append(r["cell_id"])
            continue
        rows.append({
            "rater": r["rater"],
            "opaque": r["cell_id"],
            "cell_id": k["original"],
            "cq": k["cq_id"],
            "variant": k["variant"],
            "S": int(r["S"]),
            "R": int(r["R"]),
            "span": r.get("span") or "",
            "span_verbatim": (r.get("span_verbatim") or "").strip(),
            "note": (r.get("note") or "").strip(),
            "dwell_ms": int(r["dwell_ms"]),
            "saved_at": r.get("saved_at") or "",
            "J": cells.get(k["original"], {}).get("J"),
            "S_AH": int(ah_key[k["original"]]["S_AH"]) if k["original"] in ah_key else None,
            "L1_star_AH": int(ah_key[k["original"]]["L1_star"]) if k["original"] in ah_key else None,
        })
    assert not unmapped, f"site_key에 없는 cell_id: {unmapped}"

    raters = sorted({r["rater"] for r in rows})
    per_cell = {}
    for r in rows:
        per_cell.setdefault(r["cell_id"], []).append(r)

    # ---------- rater 쌍별 ----------
    pairs = {}
    for i, a in enumerate(raters):
        for b in raters[i + 1:]:
            common = sorted({x["cell_id"] for x in rows if x["rater"] == a}
                            & {x["cell_id"] for x in rows if x["rater"] == b})
            la = {x["cell_id"]: x for x in rows if x["rater"] == a}
            lb = {x["cell_id"]: x for x in rows if x["rater"] == b}
            if not common:
                pairs[f"{a}-{b}"] = {"n": 0, "pct_agreement_S": None, "cohen_kappa_S": None,
                                     "qwk_R": None, "mae_R": None}
                continue
            sa = [la[c]["S"] for c in common]; sb = [lb[c]["S"] for c in common]
            ra = [la[c]["R"] for c in common]; rb = [lb[c]["R"] for c in common]
            pairs[f"{a}-{b}"] = {
                "n": len(common),
                "pct_agreement_S": sum(x == y for x, y in zip(sa, sb)) / len(common),
                "cohen_kappa_S": cohen_kappa(sa, sb),
                "qwk_R": qwk(ra, rb),
                "mae_R": mae(ra, rb),
            }

    # ---------- rater별 요약 ----------
    per_rater = {}
    for rid in raters:
        rr = [x for x in rows if x["rater"] == rid]
        dw = sorted(x["dwell_ms"] for x in rr)
        per_rater[rid] = {
            "n_cells": len(rr),
            "n_S1": sum(x["S"] == 1 for x in rr),
            "R_hist": {str(v): sum(x["R"] == v for x in rr) for v in range(4)},
            "dwell_ms_median": statistics.median(dw),
            "dwell_ms_min": dw[0], "dwell_ms_max": dw[-1],
            "share_under_20s": sum(d < G7_FAST_MS for d in dw) / len(dw),
        }

    # ---------- consensus(다수결) ----------
    consensus = {}
    for cid, votes in sorted(per_cell.items()):
        s_vals = [v["S"] for v in votes]
        r_vals = sorted(v["R"] for v in votes)
        ones = sum(s_vals)
        s_final = 1 if ones * 2 > len(s_vals) else 0  # ADJUDICATION_MULTIRATER: 동률 시 unsupported 우선
        med = statistics.median(r_vals)
        r_final = int(math.floor(med + 0.5))           # 홀수 중앙값/짝수 반올림 (여기선 모두 단일 표)
        consensus[cid] = {
            "cell_id": cid,
            "cq": votes[0]["cq"],
            "variant": votes[0]["variant"],
            "A": s_final,
            "rater_L1": r_final,
            "S_votes": "/".join(str(s) for s in s_vals),
            "R_values": "/".join(str(v) for v in r_vals),
            "n_raters": len(votes),
            "raters": "/".join(sorted(v["rater"] for v in votes)),
            "evidence_span_verbatim": votes[0]["span"] if s_final == 1 else "",
            "J": votes[0]["J"],
            "S_AH": votes[0]["S_AH"],
            "L1_star_AH": votes[0]["L1_star_AH"],
        }

    out_csv = HERE / "consensus_labels.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "A", "rater_L1", "evidence_span_verbatim",
                    "n_raters", "raters", "S_votes", "R_values", "J", "S_AH", "L1_star_AH"])
        for c in consensus.values():
            w.writerow([c["cell_id"], c["A"], c["rater_L1"], c["evidence_span_verbatim"],
                        c["n_raters"], c["raters"], c["S_votes"], c["R_values"],
                        c["J"], c["S_AH"], c["L1_star_AH"]])

    # ---------- consensus vs AH ----------
    ah_cells = [c for c in consensus.values() if c["S_AH"] is not None]
    ah_mismatch = []
    for c in ah_cells:
        if c["A"] != c["S_AH"] or c["rater_L1"] != c["L1_star_AH"]:
            ah_mismatch.append({"cell_id": c["cell_id"], "J": c["J"],
                                "consensus_S": c["A"], "S_AH": c["S_AH"],
                                "consensus_R": c["rater_L1"], "L1_star_AH": c["L1_star_AH"]})
    vs_ah = None
    if ah_cells:
        cs = [c["A"] for c in ah_cells]; ca = [c["S_AH"] for c in ah_cells]
        rs = [c["rater_L1"] for c in ah_cells]; ra_ = [c["L1_star_AH"] for c in ah_cells]
        vs_ah = {
            "n": len(ah_cells),
            "S_agreement": sum(x == y for x, y in zip(cs, ca)) / len(cs),
            "S_cohen_kappa": cohen_kappa(cs, ca),
            "R_qwk": qwk(rs, ra_),
            "R_mae": mae(rs, ra_),
            "R_exact": sum(x == y for x, y in zip(rs, ra_)) / len(rs),
            "mismatches": ah_mismatch,
            "basis": "저장소 내 AH 키: S_AH, L1_star(=f(J,A) 파생). 주의: G4/인간-인간 기준은 AH의 새 rater_L1을 씀 → vs_ah_fresh 참조",
        }

    # ---------- consensus vs AH fresh rater_L1(봉인 사본, 저장소 밖; 존재 시에만) ----------
    # 기준선 AH vs IND(QWK 0.728 / MAE 0.287, CLAIMS-LEDGER 547)와 동일 지표.
    ah_lock_path = Path.home() / "labels" / "locked" / "2026-10-09" / "primary_working.csv"
    vs_ah_fresh = {"present": ah_lock_path.exists()}
    if vs_ah_fresh["present"]:
        ahf = {r["cell_id"]: r for r in read_csv(ah_lock_path)
               if r["cell_id"] in consensus and r["cell_id"].startswith("primary:")}
        cells_ok = sorted(set(ahf) & set(consensus))
        cs = [consensus[c]["A"] for c in cells_ok]
        ca = [int(ahf[c]["A"]) for c in cells_ok]
        rs = [consensus[c]["rater_L1"] for c in cells_ok]
        ra_ = [int(ahf[c]["rater_L1"]) for c in cells_ok]
        vs_ah_fresh.update({
            "sha256": sha256(ah_lock_path), "n": len(cells_ok),
            "A_agreement": sum(x == y for x, y in zip(cs, ca)) / len(cs),
            "A_cohen_kappa": cohen_kappa(cs, ca),
            "R_qwk": qwk(rs, ra_), "R_mae": mae(rs, ra_),
            "R_exact": sum(x == y for x, y in zip(rs, ra_)) / len(rs),
            "mismatches": [{"cell_id": c, "consensus_S": consensus[c]["A"], "AH_A": int(ahf[c]["A"]),
                            "consensus_R": consensus[c]["rater_L1"],
                            "AH_rater_L1": int(ahf[c]["rater_L1"])}
                           for c in cells_ok
                           if consensus[c]["A"] != int(ahf[c]["A"])
                           or consensus[c]["rater_L1"] != int(ahf[c]["rater_L1"])],
            "S_AH_key_vs_locked_A_all_match": all(
                consensus[c]["S_AH"] == int(ahf[c]["A"]) for c in cells_ok
                if consensus[c]["S_AH"] is not None),
            "basis": "AH 라벨의 새 rater_L1(0-3) — 인간-인간 기준선과 동일 지표",
        })

    # ---------- consensus vs IND(second_pass v3 두 번째 인간 라벨, 저장소 내) ----------
    ind_path = ANNO / "second_pass_2026-10-13" / "v3" / "labels_for_analysis_v3.csv"
    vs_ind = {"present": ind_path.exists()}
    if ind_path.exists():
        ind = {r["cell_id"]: r for r in read_csv(ind_path) if r["cell_id"] in consensus}
        ids = sorted(set(ind) & set(consensus))
        cs = [consensus[c]["A"] for c in ids]
        ca = [int(ind[c]["A"]) for c in ids]
        rs = [consensus[c]["rater_L1"] for c in ids]
        ra_ = [int(ind[c]["rater_L1"]) for c in ids]
        vs_ind.update({
            "n": len(ids),
            "S_agreement": sum(x == y for x, y in zip(cs, ca)) / len(cs),
            "S_cohen_kappa": cohen_kappa(cs, ca),
            "R_qwk": qwk(rs, ra_), "R_mae": mae(rs, ra_),
            "R_exact": sum(x == y for x, y in zip(rs, ra_)) / len(rs),
            "basis": "IND = second_pass v3 rater_L1(새 0-3) — 인간-인간(OTHER pair) 참고치",
        })

    # ---------- consensus vs registered judge J ----------
    j_cells = [c for c in consensus.values() if c["J"] is not None]
    js = [c["J"] for c in j_cells]; hs = [c["rater_L1"] for c in j_cells]
    rec = [{"cluster": c["cq"], "j": c["J"], "h": c["rater_L1"]} for c in j_cells]
    vs_judge = None
    if j_cells:
        boot_mae = cluster_bootstrap(rec, lambda s: mae([r["j"] for r in s], [r["h"] for r in s]))
        boot_qwk = cluster_bootstrap(rec, lambda s: qwk([r["j"] for r in s], [r["h"] for r in s]))
        vs_judge = {
            "n": len(j_cells),
            "n_cq_clusters": len({c["cq"] for c in j_cells}),
            "mae": mae(js, hs), "mae_ci": boot_mae,
            "qwk": qwk(js, hs), "qwk_ci": boot_qwk,
            "J_hist": {str(v): sum(j == v for j in js) for v in range(4)},
            "H_hist": {str(v): sum(h == v for h in hs) for v in range(4)},
            "confusion_rows_J_cols_H": [[sum(1 for r in rec if r["j"] == i and r["h"] == j)
                                          for j in range(4)] for i in range(4)],
            "note": "percentile CI(탐색적). 등록 BCa 수치는 피닝된 analyze_holdout.py 결과 참조",
        }

    # ---------- dwell 요약 ----------
    dw_all = sorted(x["dwell_ms"] for x in rows)
    dwell = {
        "n": len(dw_all),
        "median_ms": statistics.median(dw_all),
        "mean_ms": round(sum(dw_all) / len(dw_all)),
        "min_ms": dw_all[0], "max_ms": dw_all[-1],
        "iqr_ms": [statistics.quantiles(dw_all, n=4)[0], statistics.quantiles(dw_all, n=4)[2]],
        "share_under_20s": sum(d < G7_FAST_MS for d in dw_all) / len(dw_all),
        "per_rater": {r: per_rater[r]["dwell_ms_median"] for r in raters},
    }

    # ---------- note 인간성(기계 판정 가능 서명만) ----------
    notes = [x["note"] for x in rows]
    nonempty = [n for n in notes if n]

    def common_prefix(a: str, b: str) -> int:
        n = 0
        while n < min(len(a), len(b)) and a[n] == b[n]:
            n += 1
        return n
    all_pref = 0
    if nonempty:
        all_pref = len(nonempty[0])
        for n in nonempty[1:]:
            all_pref = min(all_pref, common_prefix(nonempty[0], n))
    max_pair_pref = max((common_prefix(a, b) for a in nonempty for b in nonempty if a != b),
                        default=0)
    hangul = sum(1 for n in nonempty if any("가" <= ch <= "힯" for ch in n))
    v2_hits = sum(1 for n in nonempty if n in V2_TEMPLATES)
    dup_across_raters = [n for n in set(nonempty)
                         if len({x["rater"] for x in rows if x["note"] == n}) > 1]
    note_checks = {
        "n_rows": len(notes),
        "n_nonempty": len(nonempty),
        "n_distinct_nonempty": len(set(nonempty)),
        "v2_template_hits": v2_hits,
        "common_prefix_all_nonempty_chars": all_pref,
        "max_pairwise_prefix_chars": max_pair_pref,
        "notes_with_hangul": hangul,
        "identical_note_across_raters": dup_across_raters,
        "edit_marker_수정함_count": sum(1 for n in nonempty if "수정함" in n),
        "span_verbatim_False_rows": [x["cell_id"] for x in rows if x["span_verbatim"] == "False"],
        "s0_rows_with_empty_span": sum(1 for x in rows if x["S"] == 0 and x["span"] == ""),
        "s1_rows_with_nonempty_span": sum(1 for x in rows if x["S"] == 1 and x["span"] != ""),
        "s1_rows_with_note": sum(1 for x in rows if x["S"] == 1 and x["note"] != ""),
        "s0_rows_with_note": sum(1 for x in rows if x["S"] == 0 and x["note"] != ""),
        "v2_signature_conclusion": ("v2와 같은 전건 동일 접두/단일 문구 서명 없음"
                                     if v2_hits == 0 and (all_pref == 0 or len(nonempty) <= 1)
                                     else "서명 의심 — 검토 필요"),
        "limit": "이 검사들은 '기계 복제 서명 부재'만 확인한다. 인간/생성기 출처를 증명하지는 못한다.",
    }

    # ---------- 겹침 비율 ----------
    cell_sets = {r: {x["cell_id"] for x in rows if x["rater"] == r} for r in raters}
    overlap = {
        "pairwise_shared_cells": {f"{a}-{b}": len(cell_sets[a] & cell_sets[b])
                                   for i, a in enumerate(raters) for b in raters[i + 1:]},
        "cells_with_2plus_raters": sum(len(v) >= 2 for v in per_cell.values()),
        "n_labeled_cells": len(per_cell),
        "in_ah_set_188": sum(c["S_AH"] is not None for c in consensus.values()),
        "coverage_of_ah_188": len(per_cell) / len(ah_key),
        "in_cells_jsonl": sum(c["cell_id"] in cells for c in consensus.values()),
    }

    # ---------- G2 재평가 데이터 존재 여부 ----------
    washout_csv = PAPER / "harness" / "real_run" / "annotation_pending" / "washout_pass_72_ready_to_fill.csv"
    washout_filled = 0
    if washout_csv.exists():
        washout_filled = sum(1 for r in read_csv(washout_csv) if (r.get("A") or "").strip())
    retest_in_export = sum(len(v) >= 2 for v in per_cell.values())
    g2 = {
        "washout_ready_to_fill_nonblank_A": washout_filled,
        "g2_washout_2026_10_dir_files": sorted(p.name for p in
                                               (PAPER / "annotation" / "g2_washout_2026-10").iterdir()
                                               if p.is_file()),
        "export_retest_cells_same_rater": retest_in_export,
        "conclusion": "G2 불가 계속 — washout 라벨 0건, 내보내기에 동일 rater 재평가 0건",
    }
    g3 = {"site_key_control_cells": sum(1 for k in site_key.values()
                                        if not k["original"].startswith("primary:")),
          "conclusion": "사이트 키는 primary 188셀만 포함 → 이 내보내기로 ablated 24셀 라벨 불가 → G3 불가 계속"}

    result = {
        "banner": "AI-generated analysis (Claude, 2026-10-24). Not human-reviewed.",
        "inputs": {
            "export": {"path": str(BASE / "human_labels_export_2026-10-15.csv"),
                        "sha256": sha256(BASE / "human_labels_export_2026-10-15.csv"),
                        "rows": len(export)},
            "site_key": {"sha256": sha256(BASE / "site_key_2026-10-13.csv")},
            "ah_key": {"sha256": sha256(PAPER / "annotation" / "labeling_sheet_key_2026-10-13.csv"),
                        "n": len(ah_key)},
            "cells_jsonl_j_present": len(cells),
        },
        "per_rater": per_rater,
        "pairs": pairs,
        "consensus": {"n_cells": len(consensus),
                       "n_multi_rater": sum(c["n_raters"] >= 2 for c in consensus.values()),
                       "n_single_rater": sum(c["n_raters"] == 1 for c in consensus.values()),
                       "rows": list(consensus.values())},
        "vs_ah": vs_ah,
        "vs_ah_fresh": vs_ah_fresh,
        "vs_ind_v3": vs_ind,
        "vs_judge": vs_judge,
        "dwell": dwell,
        "note_checks": note_checks,
        "overlap": overlap,
        "g2": g2,
        "g3": g3,
        "seed": SEED,
        "boot_B": BOOT_B,
    }
    (HERE / "results_multirater.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---------- compute_multirater_agreement.py용 형식 변환(신규 파일) ----------
    (HERE / "keys").mkdir(exist_ok=True)
    (HERE / "filled").mkdir(exist_ok=True)
    for rid in raters:
        rr = [x for x in rows if x["rater"] == rid]
        with (HERE / "keys" / f"key_{rid}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["opaque_id", "cell_id"])
            for x in rr:
                w.writerow([x["opaque"], x["cell_id"]])
        with (HERE / "filled" / f"{rid}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(["cell_id", "S_label", "R_score"])
            for x in rr:
                w.writerow([x["opaque"], x["S"], x["R"]])

    # ---------- 요약 출력 ----------
    print(f"labels={len(rows)} raters={raters} cells={len(per_cell)} "
          f"multi-rater cells={result['consensus']['n_multi_rater']}")
    print("pairs:", json.dumps(pairs, ensure_ascii=False))
    if vs_ah:
        print(f"vs AH(key L1*): n={vs_ah['n']} Sagree={vs_ah['S_agreement']:.3f} "
              f"κ(S)={vs_ah['S_cohen_kappa']:.3f} QWK={vs_ah['R_qwk']:.3f} "
              f"MAE={vs_ah['R_mae']:.3f} mismatches={len(vs_ah['mismatches'])}")
    if vs_ah_fresh.get("present"):
        print(f"vs AH(fresh L1): n={vs_ah_fresh['n']} Agree={vs_ah_fresh['A_agreement']:.3f} "
              f"κ={vs_ah_fresh['A_cohen_kappa']:.3f} QWK={vs_ah_fresh['R_qwk']:.3f} "
              f"MAE={vs_ah_fresh['R_mae']:.3f} exact={vs_ah_fresh['R_exact']:.3f} "
              f"key/lock S_AH all match={vs_ah_fresh['S_AH_key_vs_locked_A_all_match']}")
    if vs_ind.get("present") and vs_ind.get("n"):
        print(f"vs IND(v3):     n={vs_ind['n']} Sagree={vs_ind['S_agreement']:.3f} "
              f"κ={vs_ind['S_cohen_kappa']:.3f} QWK={vs_ind['R_qwk']:.3f} MAE={vs_ind['R_mae']:.3f}")
    if vs_judge:
        print(f"vs J : n={vs_judge['n']} MAE={vs_judge['mae']:.3f} "
              f"CI[{vs_judge['mae_ci']['ci_lo']:.3f},{vs_judge['mae_ci']['ci_hi']:.3f}] "
              f"QWK={vs_judge['qwk']:.3f} "
              f"CI[{vs_judge['qwk_ci']['ci_lo']:.3f},{vs_judge['qwk_ci']['ci_hi']:.3f}]")
    print(f"dwell median={dwell['median_ms']/1000:.1f}s under20s={dwell['share_under_20s']:.1%}")
    print("notes:", note_checks["v2_signature_conclusion"],
          f"distinct={note_checks['n_distinct_nonempty']}/{note_checks['n_nonempty']}")
    print(f"G2: {g2['conclusion']}")
    print(f"wrote {out_csv.name}, results_multirater.json, keys/, filled/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
