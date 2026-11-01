"""Cross-judge agreement and judge sensitivity of the Brick holdout (EXPLORATORY, POST HOC).

Judge 1 = gemini-3.6-flash (the judge that scored the holdout; PREREG.md 12.1 D1),
judge 2 = the second judge re-scored by ``harness/run_second_judge.py``.  Both saw
the identical frozen prompt, rubric and rendered views.  The labels are the
committed AH labels (``A`` in the unsealed ``per_cell.rerun_0dbe6e9.json``); this
script never reads the label store, any ``persona_pass`` directory, or any
per-cell file other than the committed ones named in ``--help``.

Every interval is the registered one: CQ-cluster BCa from
``analyze_holdout.cluster_bootstrap_stat`` (B = 10,000, seed 20260913, unstratified
semantic cluster, mid-rank bias correction).  Nothing here is registered: the run
happened after the results were known, and PREREG.md registers no second judge.

Sections (a section whose inputs are incomplete is ``not_computable`` and says
exactly why -- nothing is imputed, nothing is silently restricted):
  agreement    QWK(J1, J2), exact agreement, binary kappa of 1[J>=2]  (primary cells
               that have a J2; ``complete`` says whether that is all 188)
  sensitivity  coverage per variant (judge-only and L1* with the AH labels), the
               A->B contrast, pi-hat = Pr[J>=2 and A=0], the variant ranking --
               each for judge 1 and judge 2, plus the paired judge-2-minus-judge-1
               differences
  G6           the registered gate, computed by ``analyze_holdout._g6`` unchanged:
               A->B consistency + non-Qwen judge direction + fragility K >= 6.
               The "non-Qwen judge" slot is filled by judge 2 (judge 1 is non-Qwen
               too; PREREG 12.1 D10 forbids reading that as satisfying the slot).
               A mirrored reading (roles swapped) is reported as descriptive only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[2]                      # .../paper/access2026/harness
sys.path.insert(0, str(HARNESS))
import analyze_holdout as ah  # noqa: E402

UNSEALED = HARNESS / "real_run" / "results_human_pass" / "unsealed_2026-10-09"
DEFAULT_PER_CELL = UNSEALED / "per_cell.rerun_0dbe6e9.json"
DEFAULT_J1_RESULTS = UNSEALED / "holdout_results_human.rerun_0dbe6e9.json"
DEFAULT_ORIGINAL_CELLS = HARNESS / "real_run" / "cells.jsonl"
DEFAULT_J2_CELLS = HERE / "cells.jsonl"
DEFAULT_RUN_MANIFEST = HERE / "run_manifest.json"
DEFAULT_OUT = HERE / "analysis.json"

VARIANTS = ah.REGISTERED_VARIANTS              # ("A", ..., "F")
PRIMARY_CELLS_REGISTERED = 188
MIN_CLUSTERS_FOR_CI = 10                       # this script's choice, not registered
REPRODUCTION_TOLERANCE = 1e-9
STATUS = ("EXPLORATORY, POST HOC: computed after the holdout results and the human labels were "
          "known; the second judge is not in PREREG.md; no number here is confirmatory")
DISCLOSURES = [
    "Post hoc: the second-judge run happened after the holdout results were known (PREREG.md "
    "register: no second judge or panel; 12.1 D1 records that the primary judge itself was "
    "switched without registration; D10 records G6 as not_computable for want of a second judge).",
    "The AH labels (A) were adjudicated against judge-1-era material (the judge-1 evidence span "
    "and a Qwen draft; per_cell has draft_A, span_edited). pi-hat and L1* under judge 2 treat A "
    "as a judge-independent property of the (view, question) cell and inherit any judge-1 "
    "conditioning of A. Coverage computed on J alone does not use A.",
    "The second judge was called without response_format=json_object (the local proxy rejects "
    "it) and with the proxy's default reasoning effort; temperature 0.0 was sent, but a "
    "reasoning model behind a proxy is not bit-reproducible (see run_manifest.json settings).",
    "The A->B contrast and the variant ranking are descriptive here; PREREG sec.4 forbids "
    "reading differences below 0.53 L1 as ordered and forbids 'tie' language for unresolved "
    "contrasts.",
]

FORBIDDEN_PATH_PARTS = ("persona_pass", "<home>/labels")


# --------------------------------------------------------------------------
# input guards and loaders
# --------------------------------------------------------------------------
def guard_path(path: Path) -> Path:
    text = str(Path(path).resolve())
    for part in FORBIDDEN_PATH_PARTS:
        if part in text:
            raise SystemExit(f"REFUSING TO READ {text}: path contains {part!r} (hard rule)")
    return Path(path)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_per_cell(path: Path) -> list[dict]:
    """The committed AH-labelled primary cells: id fields, J (judge 1) and A (AH label).
    No other per-cell field (rater_L1, audit data, draft) is carried forward."""
    data = json.loads(guard_path(path).read_text(encoding="utf-8"))
    rows = data["primary_cells"] if isinstance(data, dict) else data
    cells, seen = [], set()
    for row in rows:
        cid = row["cell_id"]
        if cid in seen:
            raise ValueError(f"duplicate cell_id {cid!r} in {path}")
        seen.add(cid)
        cells.append({
            "cell_id": cid, "cq_id": str(row["cq_id"]), "cluster_id": str(row["cluster_id"]),
            "category": row.get("category"), "variant": str(row["variant"]),
            "J1": ah._strict_j(row["J"], f"J of {cid}"), "A": ah._strict_a(row["A"], f"A of {cid}"),
        })
    if not cells:
        raise ValueError(f"no primary cells in {path}")
    return cells


def load_jsonl_cells(path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for line in guard_path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["cell_id"] in out:
            raise ValueError(f"duplicate cell_id {record['cell_id']!r} in {path}")
        out[record["cell_id"]] = record
    return out


def valid_j(record: dict) -> int | None:
    """The record's J if it is a valid parsed judge reply, else None."""
    response = record.get("judge_response")
    raw = response.get("score") if isinstance(response, dict) else None
    if not record.get("judge_response_parsed") or isinstance(raw, bool):
        return None
    if not isinstance(raw, (int, float)) or (isinstance(raw, float) and not raw.is_integer()):
        return None
    raw = int(raw)
    j = record.get("J")
    if not 0 <= raw <= 3 or j != raw:
        return None
    return raw


def join_judges(per_cell: list[dict], original: dict[str, dict], second: dict[str, dict]) -> tuple[list[dict], dict]:
    """Attach J2 to each primary cell; check the J1 and digest provenance."""
    cells, integrity = [], {
        "j1_matches_original_cells_jsonl": 0, "j1_differs_from_original_cells_jsonl": [],
        "primary_cells_missing_in_original": [], "j2_digest_matches_original": 0,
        "j2_digest_differs_from_original": [], "j2_invalid_records": [],
        "j2_cluster_or_variant_differs": [], "j2_records_for_unknown_cells": [],
        "j2_control_cells_scored": 0,
    }
    ids = {c["cell_id"] for c in per_cell}
    integrity["j2_control_cells_scored"] = sum(
        1 for cid, r in second.items() if cid not in ids and str(r.get("cell_kind")) != "primary")
    integrity["j2_records_for_unknown_cells"] = sorted(
        cid for cid, r in second.items() if cid not in ids and str(r.get("cell_kind")) == "primary")
    for cell in per_cell:
        cid = cell["cell_id"]
        row = dict(cell, J2=None)
        orig = original.get(cid)
        if orig is None:
            integrity["primary_cells_missing_in_original"].append(cid)
        elif valid_j(orig) == cell["J1"]:
            integrity["j1_matches_original_cells_jsonl"] += 1
        else:
            integrity["j1_differs_from_original_cells_jsonl"].append(cid)
        rec = second.get(cid)
        if rec is not None:
            j2 = valid_j(rec)
            if j2 is None:
                integrity["j2_invalid_records"].append(cid)
            elif (str(rec.get("cluster_id")) != cell["cluster_id"]
                  or str(rec.get("variant")) != cell["variant"]):
                integrity["j2_cluster_or_variant_differs"].append(cid)
            else:
                row["J2"] = j2
                if orig is not None and rec.get("artifact_digest") == orig.get("artifact_digest"):
                    integrity["j2_digest_matches_original"] += 1
                else:
                    integrity["j2_digest_differs_from_original"].append(cid)
        cells.append(row)
    bad = (integrity["j1_differs_from_original_cells_jsonl"] or integrity["primary_cells_missing_in_original"]
           or integrity["j2_digest_differs_from_original"] or integrity["j2_invalid_records"]
           or integrity["j2_cluster_or_variant_differs"] or integrity["j2_records_for_unknown_cells"])
    integrity["ok"] = not bad
    return cells, integrity


def completeness(cells: list[dict]) -> dict:
    by_variant: dict[str, dict] = {}
    for v in sorted({c["variant"] for c in cells}):
        mine = [c for c in cells if c["variant"] == v]
        by_variant[v] = {"primary_cells": len(mine), "with_j2": sum(c["J2"] is not None for c in mine)}
        by_variant[v]["missing"] = by_variant[v]["primary_cells"] - by_variant[v]["with_j2"]
    scored = sum(c["J2"] is not None for c in cells)
    return {"primary_cells": len(cells), "primary_cells_with_j2": scored,
            "primary_cells_missing_j2": len(cells) - scored,
            "all_primary_scored": scored == len(cells),
            "by_variant": by_variant,
            "registered_primary_cells": PRIMARY_CELLS_REGISTERED,
            "matches_registered_design": len(cells) == PRIMARY_CELLS_REGISTERED}


def variant_complete(comp: dict, *variants: str) -> bool:
    by = comp["by_variant"]
    return all(v in by and by[v]["primary_cells"] > 0 and by[v]["missing"] == 0 for v in variants)


def missing_text(comp: dict, variants) -> str:
    return ", ".join(f"{v}: {comp['by_variant'].get(v, {}).get('missing', 'n/a')} of "
                     f"{comp['by_variant'].get(v, {}).get('primary_cells', 'n/a')} cells lack a valid J2"
                     for v in variants)


def not_computable(reason: str, **extra) -> dict:
    return {"status": "not_computable", "reason": reason, **extra}


# --------------------------------------------------------------------------
# statistics (every interval through analyze_holdout.cluster_bootstrap_stat)
# --------------------------------------------------------------------------
def ci_block(cells: list[dict], stat_fn, *, B: int, seed: int, label: str = "") -> dict:
    """Point estimate plus the registered CQ-cluster BCa 95% interval.  Below
    MIN_CLUSTERS_FOR_CI clusters the interval is withheld (BCa on a handful of
    clusters is not an interval worth printing); a non-finite resample statistic
    is reported, not hidden."""
    clusters = {str(c["cluster_id"]) for c in cells}
    out = {"estimate": float(stat_fn(cells)), "n_cells": len(cells), "n_clusters": len(clusters)}
    if len(clusters) < MIN_CLUSTERS_FOR_CI:
        out.update(ci_lo=None, ci_hi=None,
                   ci_reason=f"fewer than {MIN_CLUSTERS_FOR_CI} CQ clusters ({len(clusters)}): "
                             "BCa interval withheld; point estimate is descriptive only")
        return out
    try:
        boot = ah.cluster_bootstrap_stat(cells, stat_fn, None, "cluster_id", B, seed, ah.DEFAULT_BCA_TIES)
    except ValueError as exc:
        out.update(ci_lo=None, ci_hi=None, ci_reason=f"bootstrap refused: {exc}")
        return out
    out.update(estimate=boot["estimate"], ci_lo=boot["ci_lo"], ci_hi=boot["ci_hi"],
               ci_method="CQ-cluster BCa (analyze_holdout.cluster_bootstrap_stat)", B=boot["B"],
               seed=boot["seed"], bca_ties=boot["bca_ties"])
    return out


def _qwk_j(sample: list[dict]) -> float:
    return ah._qwk_from_values([c["J1"] for c in sample], [c["J2"] for c in sample])


def _exact(sample: list[dict]) -> float:
    return float(np.mean([c["J1"] == c["J2"] for c in sample]))


def binary_kappa(left, right) -> float:
    """Cohen's kappa of two 0/1 vectors.  When chance agreement is 1 (both raters
    constant and equal) kappa is 1.0 if they agree everywhere and 0.0 otherwise --
    the same convention as analyze_holdout._qwk_from_values, so a degenerate
    bootstrap resample never yields NaN."""
    x, y = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    po = float(np.mean(x == y))
    px, py = float(np.mean(x)), float(np.mean(y))
    pe = px * py + (1 - px) * (1 - py)
    if pe >= 1.0 - 1e-15:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def _kappa_ge2(sample: list[dict]) -> float:
    return binary_kappa([c["J1"] >= 2 for c in sample], [c["J2"] >= 2 for c in sample])


def _signed_diff(sample: list[dict]) -> float:
    return float(np.mean([c["J2"] - c["J1"] for c in sample]))


def _mean_abs_diff(sample: list[dict]) -> float:
    return float(np.mean([abs(c["J2"] - c["J1"]) for c in sample]))


def agreement_section(cells: list[dict], comp: dict, *, B: int, seed: int) -> dict:
    both = [c for c in cells if c["J2"] is not None]
    if len(both) < 2:
        return not_computable(f"{len(both)} primary cell(s) have a valid J2; agreement needs at least 2")
    confusion = [[0] * 4 for _ in range(4)]
    for c in both:
        confusion[c["J1"]][c["J2"]] += 1
    table = {"both_ge2": sum(c["J1"] >= 2 and c["J2"] >= 2 for c in both),
             "j1_ge2_only": sum(c["J1"] >= 2 and c["J2"] < 2 for c in both),
             "j2_ge2_only": sum(c["J1"] < 2 and c["J2"] >= 2 for c in both),
             "both_lt2": sum(c["J1"] < 2 and c["J2"] < 2 for c in both)}
    by_variant = {}
    for v in sorted({c["variant"] for c in both}):
        mine = [c for c in both if c["variant"] == v]
        by_variant[v] = {"n_cells": len(mine), "exact_agreement": _exact(mine),
                         "qwk_point_estimate_only": _qwk_j(mine), "note": "descriptive, no interval"}
    return {
        "status": "computed" if comp["all_primary_scored"] else "computed_on_partial_data",
        "population": "primary cells with a valid J2 (controls excluded)",
        "complete": comp["all_primary_scored"],
        "n_cells": len(both), "n_clusters": len({c["cluster_id"] for c in both}),
        "qwk_j1_j2": ci_block(both, _qwk_j, B=B, seed=seed),
        "exact_agreement": ci_block(both, _exact, B=B, seed=seed),
        "binary_kappa_j_ge_2": ci_block(both, _kappa_ge2, B=B, seed=seed),
        "mean_signed_diff_j2_minus_j1": ci_block(both, _signed_diff, B=B, seed=seed),
        "mean_abs_diff": ci_block(both, _mean_abs_diff, B=B, seed=seed),
        "confusion_counts": {"rows": "J1 (judge 1)", "cols": "J2 (judge 2)", "levels": [0, 1, 2, 3],
                             "counts": confusion},
        "binary_table_j_ge_2": table,
        "by_variant": by_variant,
    }


def _coverage_judge_only(judge: str):
    return lambda sample: ah.coverage([c[judge] for c in sample])


def _coverage_l1star(judge: str):
    return lambda sample: ah.coverage([ah.demote(c[judge], c["A"]) for c in sample])


def coverage_section(cells: list[dict], comp: dict, *, B: int, seed: int) -> dict:
    """Per variant: judge 1 always (it needs only the committed per_cell file); judge 2 only when
    every cell of that variant has a valid J2."""
    out: dict = {}
    for v in VARIANTS:
        mine = [c for c in cells if c["variant"] == v]
        if not mine:
            out[v] = not_computable(f"variant {v} has no primary cells")
            continue
        out[v] = {"n_cells": len(mine), "n_clusters": len({c["cluster_id"] for c in mine}),
                  "J1_judge_only_pct": ci_block(mine, _coverage_judge_only("J1"), B=B, seed=seed),
                  "J1_L1star_pct": ci_block(mine, _coverage_l1star("J1"), B=B, seed=seed)}
        if not variant_complete(comp, v):
            out[v]["judge_2"] = not_computable(
                f"{missing_text(comp, [v])}; coverage of a variant needs every one of its cells "
                "scored by judge 2")
            continue
        out[v]["J2_judge_only_pct"] = ci_block(mine, _coverage_judge_only("J2"), B=B, seed=seed)
        out[v]["J2_L1star_pct"] = ci_block(mine, _coverage_l1star("J2"), B=B, seed=seed)
    return out


def _paired_ab(cells: list[dict], score_of) -> tuple[list[dict], list[float]]:
    lo = {c["cq_id"]: c for c in cells if c["variant"] == "A"}
    records, flat = [], []
    for c in sorted((c for c in cells if c["variant"] == "B"), key=lambda c: c["cq_id"]):
        if c["cq_id"] not in lo:
            continue
        d = float(score_of(c) - score_of(lo[c["cq_id"]]))
        records.append({"cluster_id": c["cluster_id"], "d": d})
        flat.append(d)
    return records, flat


def contrast_ab(cells: list[dict], score_of, *, B: int, seed: int) -> dict:
    """A->B exactly as ``analyze_holdout.analyse`` computes it: the pooled mean of
    the per-question differences, clusters resampled; decision by the registered
    interval rule; Wilcoxon p; Holm over the registered family of m = 2."""
    records, flat = _paired_ab(cells, score_of)
    if len({r["cluster_id"] for r in records}) < 2 or not flat:
        return not_computable("fewer than two paired A/B clusters")
    boot = ah.cluster_bootstrap_stat(records, ah._mean_d, None, "cluster_id", B, seed, ah.DEFAULT_BCA_TIES)
    wil = ah.wilcoxon_zeros_dropped(flat)
    out = {
        "status": "computed",
        "delta": boot["estimate"], "ci_lo": boot["ci_lo"], "ci_hi": boot["ci_hi"],
        "n_clusters": boot["n_clusters"], "n_questions": len(flat),
        "decision": ah.tost_decision(boot["ci_lo"], boot["ci_hi"],
                                     eq_lo=boot["ci90_lo"], eq_hi=boot["ci90_hi"]),
        "equivalence_interval_90": [boot["ci90_lo"], boot["ci90_hi"]],
        "wilcoxon_p": wil["p"], "wilcoxon_sign": wil["sign"],
    }
    if wil["p"] is not None:
        out["p_holm_family_m2"] = ah.holm({"A->B": wil["p"]}, m=ah.HOLM_FAMILY_SIZE)["A->B"]
    return out


def contrast_difference(cells: list[dict], scale: str, *, B: int, seed: int) -> dict:
    """Paired (B-A under judge 2) minus (B-A under judge 1), per question."""
    if scale == "judge_only":
        s1, s2 = (lambda c: c["J1"]), (lambda c: c["J2"])
    else:
        s1, s2 = (lambda c: ah.demote(c["J1"], c["A"])), (lambda c: ah.demote(c["J2"], c["A"]))
    r1, _ = _paired_ab(cells, s1)
    r2, _ = _paired_ab(cells, s2)
    records = [{"cluster_id": a["cluster_id"], "d": b["d"] - a["d"]} for a, b in zip(r1, r2)]
    if len({r["cluster_id"] for r in records}) < 2:
        return not_computable("fewer than two paired A/B clusters")
    boot = ah.cluster_bootstrap_stat(records, ah._mean_d, None, "cluster_id", B, seed, ah.DEFAULT_BCA_TIES)
    return {"status": "computed", "delta_j2_minus_delta_j1": boot["estimate"],
            "ci_lo": boot["ci_lo"], "ci_hi": boot["ci_hi"], "n_clusters": boot["n_clusters"]}


def contrasts_section(cells: list[dict], comp: dict, *, B: int, seed: int) -> dict:
    """A->B per judge and per scale.  Judge 1 is always computed; judge 2 and the paired
    judge-2-minus-judge-1 difference need every A and B primary cell scored by judge 2."""
    have_j2 = variant_complete(comp, "A", "B")
    why = (f"A->B needs every A and B primary cell scored by judge 2 ({missing_text(comp, ['A', 'B'])})")
    out = {}
    for scale, fn1, fn2 in (
            ("judge_only", lambda c: c["J1"], lambda c: c["J2"]),
            ("L1star_AH", lambda c: ah.demote(c["J1"], c["A"]), lambda c: ah.demote(c["J2"], c["A"]))):
        j1 = contrast_ab(cells, fn1, B=B, seed=seed)
        if not have_j2:
            out[scale] = {"judge_1": j1, "judge_2": not_computable(why),
                          "paired_difference": not_computable(why)}
            continue
        j2 = contrast_ab(cells, fn2, B=B, seed=seed)
        both = j1.get("status") == "computed" and j2.get("status") == "computed"
        out[scale] = {
            "judge_1": j1, "judge_2": j2,
            "same_decision": (j1["decision"] == j2["decision"]) if both else None,
            "same_sign_of_delta": bool(np.sign(j1["delta"]) == np.sign(j2["delta"])) if both else None,
            "paired_difference": contrast_difference(cells, "judge_only" if scale == "judge_only"
                                                     else "L1star", B=B, seed=seed),
        }
    return {"status": "computed" if have_j2 else "computed_judge_1_only", **out}


def _is_event(judge: str):
    return lambda c: c[judge] >= 2 and c["A"] == 0


def pi_section(cells: list[dict], comp: dict, *, B: int, seed: int) -> dict:
    """pi-hat = Pr[J>=2 and A=0] over all primary cells.  Judge 1 is always computed; judge 2 and
    the paired difference need every primary cell scored by judge 2."""
    def block(judge: str) -> dict:
        view = [{"cell_id": c["cell_id"], "cluster_id": c["cluster_id"], "J": c[judge], "A": c["A"]}
                for c in cells]
        out = ah.silent_over_credit_rate(view, B=B, seed=seed)
        events, n_clusters = ah.silent_over_credit(view)
        out["g1_cluster_level_events"] = events
        out["g1_cluster_level_n"] = n_clusters
        return out

    out: dict = {"judge_1": block("J1")}
    if not comp["all_primary_scored"]:
        why = (f"pi-hat is a rate over all primary cells; {comp['primary_cells_missing_j2']} of "
               f"{comp['primary_cells']} lack a valid J2 ({missing_text(comp, sorted(comp['by_variant']))})")
        out.update(status="computed_judge_1_only", judge_2=not_computable(why),
                   paired_difference_j2_minus_j1=not_computable(why))
        return out

    def diff(sample: list[dict]) -> float:
        return float(np.mean([int(_is_event("J2")(c)) - int(_is_event("J1")(c)) for c in sample]))
    out.update(status="computed", judge_2=block("J2"),
               paired_difference_j2_minus_j1=ci_block(cells, diff, B=B, seed=seed))
    return out


def _variant_coverages(sample: list[dict], judge: str, l1star: bool) -> dict[str, float]:
    out = {}
    for v in VARIANTS:
        mine = [c for c in sample if c["variant"] == v]
        if mine:
            out[v] = ah.coverage([ah.demote(c[judge], c["A"]) if l1star else c[judge] for c in mine])
    return out


def _tau_between(left: dict, right: dict) -> float:
    shared = sorted(set(left) & set(right))
    if len(shared) < 3:
        return 0.0
    tau = stats.kendalltau([left[v] for v in shared], [right[v] for v in shared]).statistic
    return 0.0 if (tau is None or not math.isfinite(float(tau))) else float(tau)


def ranking_section(cells: list[dict], comp: dict, *, B: int, seed: int) -> dict:
    """Variant ranking by coverage.  Judge 1 is always reported; the comparison needs all six
    variants fully scored by judge 2."""
    caveat = ("descriptive; PREREG sec.4: differences below 0.53 L1 are unresolved and fine rankings "
              "(D, E, F) are not to be tested or ordered as conclusions; variants with exactly equal coverage "
              "are listed alphabetically, which is not a ranking")
    order = lambda cov: sorted(cov, key=lambda v: (-cov[v], v))  # noqa: E731
    have_j2 = variant_complete(comp, *VARIANTS)
    out: dict = {"status": "computed" if have_j2 else "computed_judge_1_only", "caveat": caveat}
    for scale, l1 in (("judge_only", False), ("L1star_AH", True)):
        cov1 = _variant_coverages(cells, "J1", l1)
        entry = {"coverage_pct_judge_1": cov1, "order_best_to_worst_judge_1": order(cov1)}
        if not have_j2:
            entry["judge_2"] = not_computable(
                "the ranking comparison needs all six variants fully scored by judge 2 "
                f"({missing_text(comp, VARIANTS)})")
            out[scale] = entry
            continue
        cov2 = _variant_coverages(cells, "J2", l1)
        o1, o2 = order(cov1), order(cov2)
        tau_stat = lambda sample, l1=l1: _tau_between(  # noqa: E731
            _variant_coverages(sample, "J1", l1), _variant_coverages(sample, "J2", l1))
        rho = stats.spearmanr([cov1[v] for v in VARIANTS], [cov2[v] for v in VARIANTS]).statistic
        entry.update(
            coverage_pct_judge_2=cov2, order_best_to_worst_judge_2=o2,
            same_order=o1 == o2, same_best_variant=o1[0] == o2[0], same_worst_variant=o1[-1] == o2[-1],
            kendall_tau_b_j1_vs_j2=ci_block(cells, tau_stat, B=B, seed=seed),
            spearman_rho_point=None if not math.isfinite(float(rho)) else float(rho))
        out[scale] = entry
    return out


# --------------------------------------------------------------------------
# G6 -- the registered gate, via analyze_holdout._g6 unchanged
# --------------------------------------------------------------------------
def _g6_cells(cells: list[dict], primary_judge: str, other_judge: str | None) -> list[dict]:
    out = []
    for c in cells:
        row = {"cell_id": c["cell_id"], "cq_id": c["cq_id"], "cluster_id": c["cluster_id"],
               "variant": c["variant"], "category": c["category"], "J": c[primary_judge], "A": c["A"],
               "L1_star": ah.demote(c[primary_judge], c["A"])}
        if other_judge is not None and c[other_judge] is not None:
            row["non_qwen_J"] = c[other_judge]
        out.append(row)
    return out


def _g6_for(cells: list[dict], primary_judge: str, other_judge: str, *, B: int, seed: int) -> dict:
    """``primary_judge`` supplies the A->B consistency and the fragility K (through
    L1* with the AH labels); ``other_judge`` supplies the 'non-Qwen direction'.
    The gate itself is ``analyze_holdout._g6``, called unchanged."""
    g6_cells = _g6_cells(cells, primary_judge, other_judge)
    ab = contrast_ab(g6_cells, lambda c: c["L1_star"], B=B, seed=seed)
    contrasts = {"A->B": ab} if ab.get("status") == "computed" else {}
    return ah._g6(g6_cells, contrasts, seed=seed, resamples=B)


def g6_section(cells: list[dict], comp: dict, *, B: int, seed: int) -> dict:
    if not variant_complete(comp, "A", "B"):
        # A->B consistency and fragility need only judge 1 and the labels; compute them so the
        # report says which G6 components are already known and which one is missing and why.
        gate = _g6_for(cells, "J1", "J2", B=B, seed=seed)
        gate["reason"] = (
            "non-Qwen direction not computable: " + missing_text(comp, ["A", "B"]) +
            ". G6's non-Qwen direction component needs the judge-2 score of every A and every B "
            "primary cell (analyze_holdout._direction reads variants A and B only); judge 1 alone "
            "gives A->B consistency and fragility K, shown in 'value'")
        return {"registered_reading": gate,
                "mirrored_reading_descriptive": not_computable(
                    "needs judge 2 on every A and B primary cell"),
                "judge_2_fills_the_non_qwen_slot": True}
    registered = _g6_for(cells, "J1", "J2", B=B, seed=seed)
    mirrored = _g6_for(cells, "J2", "J1", B=B, seed=seed)
    return {
        "registered_reading": registered,
        "mirrored_reading_descriptive": dict(
            mirrored, note="roles swapped: A->B consistency and fragility K from judge 2 with the AH "
                           "labels, direction from judge 1; NOT the registered reading"),
        "judge_2_fills_the_non_qwen_slot": True,
        "slot_note": ("PREREG.md registers G6 against a Qwen primary judge and a non-Qwen second "
                      "judge. Here neither judge is Qwen; judge 2 is used as the 'non-Qwen judge' "
                      "whose B-minus-A direction (raw J, mean over CQs) must agree in sign with the "
                      "L1* direction under judge 1. 12.1 D10 forbids counting judge 1's own "
                      "non-Qwen family as satisfying the slot."),
    }


# --------------------------------------------------------------------------
# reproduction of the committed judge-1 numbers
# --------------------------------------------------------------------------
def reproduction_check(cells: list[dict], j1_results_path: Path, *, B: int, seed: int) -> dict:
    """Recompute the judge-1 coverage, A->B and pi-hat with this script's code and
    compare with the committed rerun JSON.  A mismatch means this script does not
    reproduce analyze_holdout for judge 1 and no judge-2 comparison can be trusted."""
    committed = json.loads(guard_path(j1_results_path).read_text(encoding="utf-8"))
    diffs: dict[str, float] = {}
    for v in VARIANTS:
        mine = [c for c in cells if c["variant"] == v]
        if not mine or v not in committed.get("coverage_pct", {}):
            continue
        diffs[f"coverage_pct.{v}"] = abs(
            ah.coverage([ah.demote(c["J1"], c["A"]) for c in mine]) - committed["coverage_pct"][v])
        detail = (committed.get("coverage_detail") or {}).get(v) or {}
        if detail.get("ci_lo_pct") is not None:
            boot = ah.cluster_bootstrap_stat(mine, _coverage_l1star("J1"), None, "cluster_id", B, seed)
            diffs[f"coverage_ci_lo.{v}"] = abs(boot["ci_lo"] - detail["ci_lo_pct"])
            diffs[f"coverage_ci_hi.{v}"] = abs(boot["ci_hi"] - detail["ci_hi_pct"])
    ab = (committed.get("contrasts") or {}).get("A->B")
    if ab and {"A", "B"} <= {c["variant"] for c in cells}:
        mine = contrast_ab(cells, lambda c: ah.demote(c["J1"], c["A"]), B=B, seed=seed)
        for key_mine, key_committed in (("delta", "delta"), ("ci_lo", "ci_lo"), ("ci_hi", "ci_hi"),
                                        ("p_holm_family_m2", "p_holm")):
            if mine.get(key_mine) is not None and ab.get(key_committed) is not None:
                diffs[f"A->B.{key_committed}"] = abs(mine[key_mine] - ab[key_committed])
    pi = committed.get("pi_hat")
    if pi:
        view = [{"cell_id": c["cell_id"], "cluster_id": c["cluster_id"], "J": c["J1"], "A": c["A"]}
                for c in cells]
        mine = ah.silent_over_credit_rate(view, B=B, seed=seed)
        diffs["pi_hat"] = abs(mine["pi_hat"] - pi["pi_hat"])
        if mine.get("ci_lo") is not None and pi.get("ci_lo") is not None:
            diffs["pi_hat_ci_lo"] = abs(mine["ci_lo"] - pi["ci_lo"])
            diffs["pi_hat_ci_hi"] = abs(mine["ci_hi"] - pi["ci_hi"])
    worst = max(diffs.values()) if diffs else None
    return {"committed_file": str(j1_results_path), "compared_quantities": len(diffs),
            "max_abs_diff": worst, "tolerance": REPRODUCTION_TOLERANCE,
            "reproduces_committed_judge_1_results": (worst is not None and worst <= REPRODUCTION_TOLERANCE),
            "diffs": diffs,
            "note": ("this check is only meaningful at the registered B = 10,000 and seed; at any other "
                     "setting the interval comparisons are expected to differ")}


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------
def analyse_second_judge(cells: list[dict], integrity: dict, *, B: int, seed: int,
                         j1_results_path: Path | None) -> dict:
    comp = completeness(cells)
    result: dict = {
        "status": STATUS,
        "disclosures": DISCLOSURES,
        "settings": {
            "bootstrap": "CQ-cluster BCa, analyze_holdout.cluster_bootstrap_stat", "B": B, "seed": seed,
            "registered_B": ah.BOOTSTRAP_RESAMPLES, "registered_seed": ah.REGISTERED_SEED,
            "registered_scheme": B == ah.BOOTSTRAP_RESAMPLES and seed == ah.REGISTERED_SEED,
            "bca_ties": ah.DEFAULT_BCA_TIES, "strata": None, "resample_unit": "semantic cluster (cluster_id)",
            "ci_level": ah.RESOLVE_CI_LEVEL, "min_clusters_for_ci": MIN_CLUSTERS_FOR_CI,
            "labels": "AH labels: A from the committed per_cell.rerun_0dbe6e9.json (primary cells only)",
            "population": "primary cells only (cell_kind == 'primary'); controls never enter",
        },
        "completeness": comp, "integrity": integrity,
    }
    if j1_results_path is not None and integrity["ok"]:
        result["reproduction_check_judge_1"] = reproduction_check(cells, j1_results_path, B=B, seed=seed)
    result["agreement"] = agreement_section(cells, comp, B=B, seed=seed)
    sensitivity = {
        "coverage_pct": coverage_section(cells, comp, B=B, seed=seed),
        "contrasts_A_to_B": contrasts_section(cells, comp, B=B, seed=seed),
        "pi_hat_silent_over_credit": pi_section(cells, comp, B=B, seed=seed),
        "variant_ranking": ranking_section(cells, comp, B=B, seed=seed),
    }
    result["sensitivity"] = sensitivity
    result["G6"] = g6_section(cells, comp, B=B, seed=seed)

    missing = []
    def walk(node, path):
        if isinstance(node, dict):
            if node.get("status") == "not_computable":
                missing.append({"section": path, "reason": node.get("reason")})
            for key, value in node.items():
                if key != "reason":
                    walk(value, f"{path}.{key}" if path else key)
    walk({k: result[k] for k in ("agreement", "sensitivity", "G6")}, "")
    result["not_computable_sections"] = missing
    return result


def environment() -> dict:
    return {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-cell", type=Path, default=DEFAULT_PER_CELL,
                    help="committed unsealed per_cell file (AH labels A and judge-1 J)")
    ap.add_argument("--j1-results", type=Path, default=DEFAULT_J1_RESULTS,
                    help="committed unsealed results JSON, used only to check that this script "
                         "reproduces the judge-1 numbers")
    ap.add_argument("--original-cells", type=Path, default=DEFAULT_ORIGINAL_CELLS)
    ap.add_argument("--j2-cells", type=Path, default=DEFAULT_J2_CELLS)
    ap.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--resamples", type=int, default=ah.BOOTSTRAP_RESAMPLES)
    ap.add_argument("--seed", type=int, default=ah.REGISTERED_SEED)
    ap.add_argument("--no-reproduction-check", action="store_true")
    args = ap.parse_args(argv)

    per_cell = load_per_cell(args.per_cell)
    original = load_jsonl_cells(args.original_cells)
    second = load_jsonl_cells(args.j2_cells)
    cells, integrity = join_judges(per_cell, original, second)
    if not integrity["ok"]:
        print("INTEGRITY PROBLEM (see analysis.json integrity); sections that depend on the failed "
              "check are still computed on what joined, results flagged", file=sys.stderr)
    result = analyse_second_judge(cells, integrity, B=args.resamples, seed=args.seed,
                                  j1_results_path=None if args.no_reproduction_check else args.j1_results)
    inputs = {name: {"path": str(path), "sha256": sha256_path(path)} for name, path in (
        ("per_cell", args.per_cell), ("original_cells_jsonl", args.original_cells),
        ("j2_cells_jsonl", args.j2_cells), ("j1_results_for_reproduction", args.j1_results),
        ("analyze_holdout_py", HARNESS / "analyze_holdout.py"), ("analyze_second_judge_py", Path(__file__)))
        if Path(path).exists()}
    if args.run_manifest.exists():
        manifest = json.loads(args.run_manifest.read_text(encoding="utf-8"))
        inputs["run_manifest"] = {"path": str(args.run_manifest), "sha256": sha256_path(args.run_manifest),
                                  "model_requested": manifest.get("model_requested"),
                                  "model_id_reported_by_proxy": manifest.get("model_id_reported_by_proxy")}
    result["input_provenance"] = {**inputs, "environment": environment()}
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=ah._json_default) + "\n",
                        encoding="utf-8")
    comp = result["completeness"]
    print(f"wrote {args.out}: {comp['primary_cells_with_j2']}/{comp['primary_cells']} primary cells have "
          f"judge 2; not_computable sections: {len(result['not_computable_sections'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
