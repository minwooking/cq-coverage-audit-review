#!/usr/bin/env python3
"""EXPLORATORY, POST-HOC re-analysis of the Brick holdout (reviewer request).

Nothing here is registered. It adds no human label and makes no LLM call: it
re-reads labels that already exist (the unsealed per-cell file, the AI drafts of A
before author revision, and the GPT-5.6 auxiliary A labels) and re-slices them.
Every output block carries ``exploratory_post_hoc: true``. The AH labels are an
LLM-assisted adjudication, not a reference standard, so every rate is named by what
is counted ("agreement among A=1 cells", "over-credit among judge-credited cells"),
never by a diagnostic-test or reference-standard term.

What it computes (188 primary cells, 33 CQ clusters, B = 10,000 BCa cluster
bootstrap, seed 20260913, mid-rank z0, all through ``analyze_holdout``):

1. 2x2 table of 1[J>=2] against the A label: counts, raw agreement, Cohen kappa,
   conditional agreement rates, each with a CQ-cluster BCa interval.
2. Over-credit and under-credit: pi-hat = Pr[J>=2 and A=0] as registered, the rate among
   judge-credited cells, the under-credit rates, and a two-sided disagreement rate.
3. The same table, pi-hat and the variant A->B L1* contrast under three label
   sources (A_draft, AH, GPT-5.6 auxiliary), the agreement among the three, and the
   paired differences between them (same cluster resamples, so the interval is
   for the paired difference).
4. Rater-error tipping points on the AH labels: the fewest A-label flips that move
   the pi-hat upper bound across 10%, or reverse the sign / the CI-excludes-0 status
   of the variant A->B contrast, in each direction.
5. The G1 design fact: the one-sided 97.5% Clopper-Pearson upper bound for zero events
   among 33 clusters.

Method notes the reader needs
  * Intervals are marginal 95% BCa intervals, uncorrected for the number of
    quantities reported; no p-value is computed; nothing here is a test.
  * Tipping points. A flip changes one cell's A label (1->0 or 0->1). Flips on cells with
    J<=1 change neither pi-hat nor L1* (min(J,1)=J there), so only J>=2 cells are
    candidates. The search is exhaustive over flip sets of size k = 1, 2, ... while the
    number of sets stays within a budget, so a size that is reported as a lower bound
    is certified; beyond the budget a greedy adversary supplies a witness (an upper bound
    on the true minimum), and the record says which of the two it is. The bootstrap
    replay used inside the search draws the same cluster indices as
    ``analyze_holdout.cluster_bootstrap_stat`` (same seed, same sorted cluster order) and is
    checked against that function at the baseline and at every reported witness.
  * With zero pi-hat events the analyzer refuses the bootstrap and the operative bound is
    the cluster-level Clopper-Pearson bound (10.58% at 33 clusters), so a zero-event state
    is scored with that bound, not with a degenerate bootstrap interval.

Usage (worktree root; PYTHONPATH=$PWD/src and the root .venv python)::

    python paper/access2026/harness/real_run/results_human_pass/exploratory_reanalysis.py \
        --drafts locked_labels/draft_224.csv

Output: ``exploratory_reanalysis.json`` next to this script. Aggregates only: no cell id,
CQ id, cluster id, note or span is written, and the draft file's note and span columns
are never read.

REVIEW BEFORE USE: this is analysis code written for a one-off reviewer response. It was
tested on synthetic fixtures and checked against the analyzer's own numbers, not audited.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Callable, Iterator

import numpy as np
import scipy

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[1]
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))
import analyze_holdout as ah  # noqa: E402

SEED = ah.REGISTERED_SEED
B_REGISTERED = ah.BOOTSTRAP_RESAMPLES
TIES = ah.DEFAULT_BCA_TIES
THRESHOLD = ah.G1_UPPER_BOUND_THRESHOLD  # 0.10
G1_ALPHA = 0.025
LOW_VARIANT, HIGH_VARIANT = ah.CONFIRMATORY_CONTRASTS[0]  # variant A -> variant B
SOURCES = ("draft", "AH", "aux")
SOURCE_DESCRIPTION = {
    "draft": "AI drafts of the A label before author revision (A_draft)",
    "AH": "AH labels: AI draft, human-revised (the registered A)",
    "aux": "GPT-5.6 auxiliary A labels (A_auxiliary)",
}
PAIRS = (("draft", "AH"), ("draft", "aux"), ("AH", "aux"))  # (first, second): "1->0" = first 1, second 0
TOL = 1e-9
MAX_STATES_PER_K = 60_000
MAX_STATES_TOTAL = 300_000
FLAG = {"exploratory_post_hoc": True}
STATUS = ("EXPLORATORY AND POST-HOC. Not registered; no new labels and no new LLM calls. "
          "The AH labels are an LLM-assisted adjudication and are not a reference standard, "
          "so every rate below describes agreement between two label sources, not error "
          "against a truth.")


class InputRefused(ValueError):
    """A path or value this script refuses to read or write."""


# --------------------------------------------------------------------------
# path guards and provenance
# --------------------------------------------------------------------------
def _refuse_persona_pass(path: Path) -> None:
    resolved = Path(path).expanduser().resolve()
    if any("persona_pass" in part for part in resolved.parts):
        raise InputRefused(f"refusing to touch a persona_pass path: {resolved.name}")


def _labels_roots() -> list[Path]:
    return [Path("<home>/labels").resolve(), (Path.home() / "labels").resolve()]


def refuse_input(path: Path) -> Path:
    _refuse_persona_pass(path)
    return Path(path).expanduser().resolve()


def refuse_output(path: Path, inputs: list[Path]) -> Path:
    _refuse_persona_pass(path)
    resolved = Path(path).expanduser().resolve()
    for root in _labels_roots():
        if resolved == root or root in resolved.parents:
            raise InputRefused("refusing to write under the labels directory")
    if any(resolved == Path(p).resolve() for p in inputs):
        raise InputRefused("the output path is one of the inputs")
    return resolved


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# --------------------------------------------------------------------------
# loading (strict; the draft file's note and span columns are never read)
# --------------------------------------------------------------------------
def _bin(value, what: str) -> int:
    if type(value) is not int or value not in (0, 1):
        raise InputRefused(f"{what} must be the int 0 or 1, got {value!r}")
    return value


def _j(value, what: str = "J") -> int:
    if type(value) is not int or not 0 <= value <= 3:
        raise InputRefused(f"{what} must be an int in 0..3, got {value!r}")
    return value


def _draft_bin(text, what: str) -> int:
    if text not in ("0", "1"):
        raise InputRefused(f"{what} must be '0' or '1', got {text!r}")
    return int(text)


def l1_star(j: int, a: int) -> int:
    return j if a == 1 else min(j, 1)


def load_inputs(per_cell: Path, cells: Path, drafts: Path, aux: Path) -> tuple[list[dict], dict, dict]:
    """Join the four inputs on cell_id for the primary cells.

    Returns (rows, checks, provenance_extras). The placeholder ``A`` in cells.jsonl is
    never read; the draft file contributes ``cell_id``, ``A_draft`` and ``model`` only.
    """
    for p in (per_cell, cells, drafts, aux):
        refuse_input(p)
    pc = json.loads(Path(per_cell).read_text(encoding="utf-8"))
    primary = pc["primary_cells"]
    run = {}
    for line in Path(cells).read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("cell_kind") == "primary":
            run[str(rec["cell_id"])] = {"J": rec["J"], "cq_id": str(rec["cq_id"]),
                                        "cluster_id": str(rec["cluster_id"]),
                                        "variant": str(rec["variant"])}
    draft_a: dict[str, int] = {}
    draft_models: collections.Counter = collections.Counter()
    with open(drafts, newline="", encoding="utf-8") as handle:
        for rec in csv.DictReader(handle):
            draft_a[rec["cell_id"]] = _draft_bin(rec["A_draft"], "A_draft")
            draft_models[rec.get("model", "")] += 1
    aux_a: dict[str, tuple[int, int]] = {}
    aux_models: collections.Counter = collections.Counter()
    for line in Path(aux).read_text(encoding="utf-8").split("\n"):
        if line.strip():
            rec = json.loads(line)
            aux_a[str(rec["cell_id"])] = (_bin(rec["A_auxiliary"], "A_auxiliary"), rec["J"])
            aux_models[str(rec.get("model", ""))] += 1

    ids = [str(c["cell_id"]) for c in primary]
    if len(set(ids)) != len(ids):
        raise InputRefused("duplicate cell_id among the per-cell primary cells")
    if set(ids) != set(run):
        raise InputRefused("the primary cell_id sets of per_cell and cells.jsonl differ")
    for name, source in (("drafts", draft_a), ("aux", aux_a)):
        missing = set(ids) - set(source)
        if missing:
            raise InputRefused(f"{len(missing)} primary cell(s) have no row in {name}")

    rows = []
    for c in sorted(primary, key=lambda c: str(c["cell_id"])):
        cid = str(c["cell_id"])
        j = _j(c["J"])
        info = run[cid]
        rows.append({
            "cell_id": cid, "cq_id": str(c["cq_id"]), "cluster_id": str(c["cluster_id"]),
            "variant": str(c["variant"]), "J": j, "span_edited": bool(c.get("span_edited", False)),
            "A": {"AH": _bin(c["A"], "A (AH)"), "draft": draft_a[cid], "aux": aux_a[cid][0]},
            "_per_cell_L1_star": c.get("L1_star"), "_per_cell_draft_A": c.get("draft_A"),
            "_run_J": info["J"], "_aux_J": aux_a[cid][1],
            "_run_cluster": info["cluster_id"], "_run_variant": info["variant"],
        })
    checks = {
        "n_primary_cells": len(rows),
        "n_clusters": len({r["cluster_id"] for r in rows}),
        "J_equals_cells_jsonl_J": all(r["J"] == r["_run_J"] for r in rows),
        "cluster_and_variant_equal_cells_jsonl": all(
            r["cluster_id"] == r["_run_cluster"] and r["variant"] == r["_run_variant"] for r in rows),
        "AH_L1_star_equals_demote": all(r["_per_cell_L1_star"] == l1_star(r["J"], r["A"]["AH"]) for r in rows),
        "draft_file_A_equals_per_cell_draft_A": all(
            r["_per_cell_draft_A"] is None or r["_per_cell_draft_A"] == r["A"]["draft"] for r in rows),
        "aux_J_equals_cells_jsonl_J": all(r["J"] == r["_aux_J"] for r in rows),
        "cluster_id_equals_cq_id": all(r["cluster_id"] == r["cq_id"] for r in rows),
    }
    extras = {"draft_file_model_field_values": dict(sorted(draft_models.items())),
              "aux_file_model_field_values": dict(sorted(aux_models.items()))}
    return rows, checks, extras


# --------------------------------------------------------------------------
# 2x2 table and the rates (all counted, none renamed)
# --------------------------------------------------------------------------
class Table(collections.namedtuple("Table", "n11 n10 n01 n00")):
    """Rows: J>=2 / J<=1.  Columns: A=1 / A=0.  n11 = J>=2 and A=1; n10 = J>=2 and A=0;
    n01 = J<=1 and A=1; n00 = J<=1 and A=0."""

    @property
    def n(self) -> int:
        return self.n11 + self.n10 + self.n01 + self.n00


def table_of(cells: list[dict]) -> Table:
    n11 = n10 = n01 = n00 = 0
    for c in cells:
        hi, a = c["J"] >= 2, c["A"] == 1
        if hi and a:
            n11 += 1
        elif hi:
            n10 += 1
        elif a:
            n01 += 1
        else:
            n00 += 1
    return Table(n11, n10, n01, n00)


def _div(num: float, den: float) -> float:
    return num / den if den else float("nan")


def kappa_of(n11: int, n10: int, n01: int, n00: int) -> float:
    n = n11 + n10 + n01 + n00
    if n == 0:
        return float("nan")
    po = (n11 + n00) / n
    pe = ((n11 + n10) * (n11 + n01) + (n01 + n00) * (n10 + n00)) / (n * n)
    return float("nan") if pe == 1.0 else (po - pe) / (1.0 - pe)


# name -> (numerator, denominator) from a Table; the estimate is num/den.
RATE_COUNTS: dict[str, Callable[[Table], tuple[float, float]]] = {
    "raw_agreement": lambda t: (t.n11 + t.n00, t.n),
    "positive_agreement_both_credit": lambda t: (2 * t.n11, 2 * t.n11 + t.n10 + t.n01),
    "negative_agreement_both_no_credit": lambda t: (2 * t.n00, 2 * t.n00 + t.n10 + t.n01),
    "agreement_among_A1_cells": lambda t: (t.n11, t.n11 + t.n01),
    "agreement_among_A0_cells": lambda t: (t.n00, t.n10 + t.n00),
    "agreement_among_Jge2_cells": lambda t: (t.n11, t.n11 + t.n10),
    "agreement_among_Jle1_cells": lambda t: (t.n00, t.n01 + t.n00),
    "judge_credit_rate_Jge2": lambda t: (t.n11 + t.n10, t.n),
    "A1_rate": lambda t: (t.n11 + t.n01, t.n),
    "net_marginal_difference_Jge2_minus_A1": lambda t: (t.n10 - t.n01, t.n),
}
TABLE_METRICS = dict(RATE_COUNTS)
CREDIT_RATE_COUNTS: dict[str, Callable[[Table], tuple[float, float]]] = {
    "over_credit_among_judge_credited_cells": lambda t: (t.n10, t.n11 + t.n10),
    "under_credit_among_Jle1_cells": lambda t: (t.n01, t.n01 + t.n00),
    "under_credit_among_A1_cells": lambda t: (t.n01, t.n11 + t.n01),
    "under_credit_cell_rate": lambda t: (t.n01, t.n),
    "two_sided_disagreement_rate": lambda t: (t.n10 + t.n01, t.n),
}


def _stat_from_counts(fn) -> Callable[[list[dict]], float]:
    def stat(sample: list[dict]) -> float:
        num, den = fn(table_of(sample))
        return _div(num, den)
    return stat


def _stat_kappa(sample: list[dict]) -> float:
    return kappa_of(*table_of(sample))


def _stat_balanced(sample: list[dict]) -> float:
    t = table_of(sample)
    a, b = _div(t.n10, t.n11 + t.n10), _div(t.n01, t.n01 + t.n00)
    return 0.5 * (a + b)


def _stat_under_j0(sample: list[dict]) -> float:
    zero = [c for c in sample if c["J"] == 0]
    return _div(sum(c["A"] == 1 for c in zero), len(zero))


def _finite_or_none(x) -> float | None:
    return None if x is None or not math.isfinite(float(x)) else float(x)


def interval(cells: list[dict], stat: Callable[[list[dict]], float], B: int, seed: int) -> dict:
    """Point estimate and BCa cluster-bootstrap interval through the analyzer's helper."""
    try:
        r = ah.cluster_bootstrap_stat(cells, stat, None, "cluster_id", B, seed, TIES)
    except ValueError as exc:  # an undefined statistic in some resample: say so, do not guess
        reason = ("undefined in at least one resample (an empty denominator), so no interval is reported"
                  if "not finite" in str(exc) else str(exc))
        return {"estimate": _finite_or_none(stat(cells)), "ci_lo": None, "ci_hi": None, "ci_reason": reason}
    if r["ci_lo"] == r["ci_hi"]:
        # every resample returns one value: a bootstrap cannot resample an event (or a non-event)
        # it never saw, so a zero-width interval would overstate what is known
        return {"estimate": r["estimate"], "ci_lo": None, "ci_hi": None,
                "ci_reason": "degenerate: every resample gives the same value, so no interval is reported"}
    return {"estimate": r["estimate"], "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"]}


def _with_counts(res: dict, num, den) -> dict:
    out = {"numerator": num, "denominator": den}
    out.update(res)
    return out


def table_block(cells: list[dict], B: int, seed: int) -> dict:
    t = table_of(cells)
    metrics = {}
    for name, fn in TABLE_METRICS.items():
        num, den = fn(t)
        metrics[name] = _with_counts(interval(cells, _stat_from_counts(fn), B, seed), num, den)
    metrics["cohen_kappa"] = interval(cells, _stat_kappa, B, seed)
    return {
        **FLAG,
        "rows_by_columns": "rows 1[J>=2] / 1[J<=1]; columns A=1 / A=0",
        "counts": {"Jge2_A1": t.n11, "Jge2_A0": t.n10, "Jle1_A1": t.n01, "Jle1_A0": t.n00, "n": t.n},
        "metrics": metrics,
    }


def credit_block(cells: list[dict], B: int, seed: int) -> dict:
    t = table_of(cells)
    out: dict = {**FLAG}
    pi = ah.silent_over_credit_rate(cells, B=B, seed=seed, ties=TIES)
    out["pi_hat_J_ge2_and_A0"] = {
        "events": pi["events"], "n_cells": pi["n_cells"], "estimate": pi["pi_hat"],
        "ci_lo": pi["ci_lo"], "ci_hi": pi["ci_hi"], "clusters_with_event": pi["clusters_with_event"],
        "n_clusters": pi["n_clusters"], "ci_reason": pi.get("ci_reason"),
        "basis": "analyze_holdout.silent_over_credit_rate (registered pi-hat; BCa cluster bootstrap)"}
    rates = {}
    for name, fn in CREDIT_RATE_COUNTS.items():
        num, den = fn(t)
        rates[name] = _with_counts(interval(cells, _stat_from_counts(fn), B, seed), num, den)
    zero = [c for c in cells if c["J"] == 0]
    rates["under_credit_among_J0_cells"] = _with_counts(
        interval(cells, _stat_under_j0, B, seed), sum(c["A"] == 1 for c in zero), len(zero))
    rates["balanced_two_sided_disagreement"] = {
        **interval(cells, _stat_balanced, B, seed),
        "definition": "mean of over-credit among judge-credited cells and under-credit among J<=1 cells"}
    out["rates"] = rates
    out["definitions"] = {
        "over_credit_among_judge_credited_cells": "Pr[A=0 | J>=2]",
        "under_credit_among_J0_cells": "Pr[A=1 | J=0]",
        "under_credit_among_Jle1_cells": "Pr[A=1 | J<=1]",
        "under_credit_among_A1_cells": "Pr[J<=1 | A=1]",
        "under_credit_cell_rate": "Pr[J<=1 and A=1] over all cells",
        "two_sided_disagreement_rate": "(Pr[J>=2 and A=0] + Pr[J<=1 and A=1]) = 1 - raw agreement; "
                                       "the brief's 'two-sided error rate', named for what is counted",
    }
    return out


# --------------------------------------------------------------------------
# the variant A -> B L1* contrast
# --------------------------------------------------------------------------
def _cells_for(rows: list[dict], src: str) -> list[dict]:
    return [{"cluster_id": r["cluster_id"], "cq_id": r["cq_id"], "variant": r["variant"],
             "J": r["J"], "A": r["A"][src]} for r in rows]


def paired_records(cells: list[dict]) -> list[dict]:
    """One record per CQ that has both a variant-A and a variant-B cell:
    d = L1*(B) - L1*(A), with the J values and A labels kept for the tipping search."""
    by_q: dict[str, dict[str, dict]] = {}
    for c in cells:
        if c["variant"] in (LOW_VARIANT, HIGH_VARIANT):
            slot = by_q.setdefault(c["cq_id"], {})
            if c["variant"] in slot:
                raise InputRefused("more than one primary cell for one (variant, CQ)")
            slot[c["variant"]] = c
    out = []
    for q in sorted(by_q):
        s = by_q[q]
        if LOW_VARIANT in s and HIGH_VARIANT in s:
            lo, hi = s[LOW_VARIANT], s[HIGH_VARIANT]
            out.append({"cq_id": q, "cluster_id": hi["cluster_id"],
                        "d": float(l1_star(hi["J"], hi["A"]) - l1_star(lo["J"], lo["A"])),
                        "lo": lo, "hi": hi})
    return out


def _mean_d(rs: list[dict]) -> float:
    return float(np.mean([r["d"] for r in rs]))


def contrast_block(cells: list[dict], B: int, seed: int) -> dict:
    recs = paired_records(cells)
    if len({r["cluster_id"] for r in recs}) < 2:
        return {**FLAG, "status": "not_computable", "reason": "fewer than two paired clusters"}
    res = interval([{"cluster_id": r["cluster_id"], "d": r["d"]} for r in recs], _mean_d, B, seed)
    lo, hi = res["ci_lo"], res["ci_hi"]
    return {
        **FLAG,
        "contrast": f"mean over paired CQs of L1*(variant {HIGH_VARIANT}) - L1*(variant {LOW_VARIANT})",
        "n_paired_cqs": len(recs),
        "mean_L1_star_variant_A": float(np.mean([l1_star(r["lo"]["J"], r["lo"]["A"]) for r in recs])),
        "mean_L1_star_variant_B": float(np.mean([l1_star(r["hi"]["J"], r["hi"]["A"]) for r in recs])),
        "delta": res["estimate"], "ci_lo": lo, "ci_hi": hi, "ci_reason": res.get("ci_reason"),
        "ci_status": _ci_status(lo, hi),
        "basis": "analyze_holdout.cluster_bootstrap_stat on one record per paired CQ (the analyzer's "
                 "pooled mean of per-question differences, clusters resampled)",
    }


def _ci_status(lo, hi) -> str | None:
    if lo is None or hi is None:
        return None
    if lo > TOL:
        return "excludes_0_positive"
    if hi < -TOL:
        return "excludes_0_negative"
    return "includes_0"


# --------------------------------------------------------------------------
# label sources: per-source blocks, agreement between sources, paired differences
# --------------------------------------------------------------------------
def source_block(rows: list[dict], src: str, B: int, seed: int) -> dict:
    cells = _cells_for(rows, src)
    credit = credit_block(cells, B, seed)
    return {
        **FLAG,
        "label_source": SOURCE_DESCRIPTION[src],
        "n_cells": len(cells),
        "n_A1": sum(c["A"] == 1 for c in cells),
        "n_A0": sum(c["A"] == 0 for c in cells),
        "table_2x2": table_block(cells, B, seed),
        "credit_rates": credit,
        "pi_hat": credit["pi_hat_J_ge2_and_A0"],
        "variant_A_to_B_L1_star_contrast": contrast_block(cells, B, seed),
    }


def _pair_cells(rows: list[dict], first: str, second: str) -> list[dict]:
    return [{"cluster_id": r["cluster_id"], "J": r["J"], "A": r["A"][first], "B": r["A"][second]}
            for r in rows]


def agreement_block(rows: list[dict], first: str, second: str, B: int, seed: int) -> dict:
    cells = _pair_cells(rows, first, second)
    n11 = sum(c["A"] == 1 and c["B"] == 1 for c in cells)
    n10 = sum(c["A"] == 1 and c["B"] == 0 for c in cells)
    n01 = sum(c["A"] == 0 and c["B"] == 1 for c in cells)
    n00 = sum(c["A"] == 0 and c["B"] == 0 for c in cells)

    def kappa(sample):
        return kappa_of(*(sum(1 for c in sample if c["A"] == x and c["B"] == y)
                          for x, y in ((1, 1), (1, 0), (0, 1), (0, 0))))

    def raw(sample):
        return sum(c["A"] == c["B"] for c in sample) / len(sample)

    by_j = {str(j): {"1_to_0": sum(1 for c in cells if c["J"] == j and c["A"] == 1 and c["B"] == 0),
                     "0_to_1": sum(1 for c in cells if c["J"] == j and c["A"] == 0 and c["B"] == 1)}
            for j in range(4)}
    return {
        **FLAG,
        "first": first, "second": second,
        "direction": f"'1->0' means A=1 in {first} and A=0 in {second}",
        "both_1": n11, "changed_1_to_0": n10, "changed_0_to_1": n01, "both_0": n00,
        "cohen_kappa": interval(cells, kappa, B, seed),
        "raw_agreement": interval(cells, raw, B, seed),
        "changes_by_judge_score": by_j,
    }


def paired_difference_block(rows: list[dict], first: str, second: str, B: int, seed: int) -> dict:
    """second - first for pi-hat and for the A->B contrast. The statistic is computed on the
    same cells, and ``cluster_bootstrap_stat`` draws the same resamples for the same cluster
    set, so each interval is an interval for the paired difference."""
    pi_cells = [{"cluster_id": r["cluster_id"], "e1": float(r["J"] >= 2 and r["A"][first] == 0),
                 "e2": float(r["J"] >= 2 and r["A"][second] == 0)} for r in rows]
    pi = interval(pi_cells, lambda s: sum(c["e2"] - c["e1"] for c in s) / len(s), B, seed)
    r1 = paired_records(_cells_for(rows, first))
    r2 = paired_records(_cells_for(rows, second))
    both = [{"cluster_id": a["cluster_id"], "d1": a["d"], "d2": b["d"]} for a, b in zip(r1, r2)]
    con = interval(both, lambda s: float(np.mean([c["d2"] - c["d1"] for c in s])), B, seed)
    return {**FLAG, "difference": f"{second} minus {first}",
            "pi_hat_difference": pi, "variant_A_to_B_contrast_difference": con}


# --------------------------------------------------------------------------
# bootstrap replay for the tipping search (checked against the analyzer's helper)
# --------------------------------------------------------------------------
class Replay:
    """The cluster draws of ``cluster_bootstrap_stat`` for one cluster set, made once.

    The helper draws, for each replicate, ``rng.integers(0, n, n)`` from
    ``default_rng(seed)`` over the sorted clusters. Replaying that stream lets a
    decomposable statistic (a ratio of per-cluster sums) be re-evaluated for many candidate
    flip sets without rebuilding cell lists, and the BCa step is the analyzer's own."""

    def __init__(self, n_clusters: int, B: int, seed: int):
        rng = np.random.default_rng(seed)
        # counts[b, j] = how often cluster j (sorted order) is drawn in replicate b
        self.counts = np.empty((B, n_clusters), dtype=float)
        for b in range(B):
            self.counts[b] = np.bincount(rng.integers(0, n_clusters, n_clusters), minlength=n_clusters)
        self.n, self.B, self.seed = n_clusters, B, seed

    def ratio_interval(self, num, den, alpha: float = ah.RESOLVE_ALPHA) -> tuple[float, float, float]:
        """BCa interval of sum(num)/sum(den) over clusters. ``num`` and ``den`` are integers
        here (event counts, cell counts, L1* differences), so every replicate sum is exact in
        float64 whatever the summation order and the replicates equal the helper's."""
        num = np.asarray(num, dtype=float)
        den = np.asarray(den, dtype=float)
        theta = float(num.sum() / den.sum())
        boot = (self.counts @ num) / (self.counts @ den)
        jack = (num.sum() - num) / (den.sum() - den)
        lo, hi = ah._bca_interval(theta, boot, jack, alpha, TIES)
        return theta, float(lo), float(hi)


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOL


# --------------------------------------------------------------------------
# exhaustive-then-greedy search for the fewest flips
# --------------------------------------------------------------------------
def _count_states(caps: list[int], k: int) -> int:
    ways = [1] + [0] * k
    for cap in caps:
        new = [0] * (k + 1)
        for s, w in enumerate(ways):
            if w:
                for t in range(0, min(cap, k - s) + 1):
                    new[s + t] += w
        ways = new
    return ways[k]


def _iter_states(caps: list[int], k: int) -> Iterator[tuple[int, ...]]:
    n = len(caps)
    suffix = [0] * (n + 1)
    for i in range(n - 1, -1, -1):
        suffix[i] = suffix[i + 1] + caps[i]
    x = [0] * n

    def rec(i: int, left: int):
        if i == n:
            if left == 0:
                yield tuple(x)
            return
        for v in range(max(0, left - suffix[i + 1]), min(caps[i], left) + 1):
            x[i] = v
            yield from rec(i + 1, left - v)
        x[i] = 0

    yield from rec(0, k)


def search_min_flips(caps: list[int], bound: Callable[[tuple[int, ...]], float],
                     crossed: Callable[[float], bool], prefer: str, *,
                     max_states_per_k: int = MAX_STATES_PER_K,
                     max_states_total: int = MAX_STATES_TOTAL) -> dict:
    """Fewest flips (total of x, with 0 <= x_i <= caps_i) whose bound is ``crossed``.

    ``prefer`` is the direction the adversary pushes the bound ("min" or "max"). Exhaustive
    over sizes k = 1, 2, ... while the state count is within budget (so "no crossing through
    k" is certified); a greedy adversary then supplies a witness. ``exact`` means the
    certified lower bound equals the witness."""
    if prefer not in ("min", "max"):
        raise ValueError("prefer must be 'min' or 'max'")
    better = (lambda a, b: a < b) if prefer == "min" else (lambda a, b: a > b)
    total = sum(caps)
    certified_none_through = 0
    spent = 0
    exhausted_all = True
    for k in range(1, total + 1):
        states = _count_states(caps, k)
        if states > max_states_per_k or spent + states > max_states_total:
            exhausted_all = False
            break
        spent += states
        best = None
        for x in _iter_states(caps, k):
            b = bound(x)
            if best is None or better(b, best[0]):
                best = (b, x)
        if crossed(best[0]):
            return {"reachable": True, "min_flips_lower_bound": k, "min_flips_witness": k, "exact": True,
                    "method": "exhaustive over all flip sets of each size", "state": best[1],
                    "bound_at_witness": best[0], "states_evaluated": spent}
        certified_none_through = k
    if exhausted_all:
        return {"reachable": False, "min_flips_lower_bound": None, "min_flips_witness": None,
                "exact": True, "method": "exhaustive: no flip set within the available flips crosses",
                "state": None, "bound_at_witness": None, "states_evaluated": spent,
                "available_flips": total}
    # greedy witness
    x = [0] * len(caps)
    for step in range(1, total + 1):
        best = None
        for i in range(len(caps)):
            if x[i] < caps[i]:
                x[i] += 1
                b = bound(tuple(x))
                x[i] -= 1
                if best is None or better(b, best[0]):
                    best = (b, i)
        x[best[1]] += 1
        if crossed(best[0]):
            lower = certified_none_through + 1
            return {"reachable": True, "min_flips_lower_bound": lower, "min_flips_witness": step,
                    "exact": lower == step,
                    "method": ("exhaustive through size %d, then greedy witness" % certified_none_through
                               if certified_none_through else "greedy witness only"),
                    "state": tuple(x), "bound_at_witness": best[0], "states_evaluated": spent,
                    "available_flips": total}
    return {"reachable": None, "min_flips_lower_bound": certified_none_through + 1,
            "min_flips_witness": None, "exact": False,
            "method": "exhaustive through size %d; greedy found no crossing (not proven unreachable)"
                      % certified_none_through,
            "state": None, "bound_at_witness": None, "states_evaluated": spent, "available_flips": total}


# --------------------------------------------------------------------------
# tipping points on the AH labels
# --------------------------------------------------------------------------
def _clip_result(res: dict) -> dict:
    out = {k: v for k, v in res.items() if k != "state"}
    return out


def tipping_pi(rows: list[dict], B: int, seed: int) -> dict:
    """Does the pi-hat 95% BCa upper bound cross 10%? Flips: A 0->1 on J>=2 & A=0 cells lower
    pi-hat ("down"); A 1->0 on J>=2 & A=1 cells raise it ("up")."""
    cells = _cells_for(rows, "AH")
    clusters = sorted({c["cluster_id"] for c in cells})
    pos = {cl: i for i, cl in enumerate(clusters)}
    n_k = np.zeros(len(clusters))
    ev = np.zeros(len(clusters), dtype=int)
    cand = np.zeros(len(clusters), dtype=int)  # J>=2 & A=1 cells per cluster
    for c in cells:
        i = pos[c["cluster_id"]]
        n_k[i] += 1
        if c["J"] >= 2:
            if c["A"] == 0:
                ev[i] += 1
            else:
                cand[i] += 1
    replay = Replay(len(clusters), B, seed)
    cp_zero = ah.clopper_pearson_upper(0, len(clusters), G1_ALPHA)
    base = ah.silent_over_credit_rate(cells, B=B, seed=seed, ties=TIES)
    events = int(ev.sum())
    if events == 0:
        base_ub = cp_zero
    else:
        t_, lo_, base_ub = replay.ratio_interval(ev, n_k)
        if not (_close(base_ub, base["ci_hi"]) and _close(lo_, base["ci_lo"])):
            raise AssertionError("bootstrap replay disagrees with analyze_holdout at the pi-hat baseline")

    def ub_of(e_vec) -> float:
        if int(e_vec.sum()) == 0:
            return cp_zero  # the analyzer refuses the bootstrap at zero events
        return replay.ratio_interval(e_vec, n_k)[2]

    out = {**FLAG,
           "criterion": "95% BCa upper bound of pi-hat versus 10%",
           "baseline": {"events": events, "n_cells": len(cells), "pi_hat": events / len(cells),
                        "ci_hi": base_ub, "above_threshold": bool(base_ub > THRESHOLD + 1e-12),
                        "replay_matches_analyzer": True},
           "zero_event_rule": ("a state with zero events is scored with the cluster-level one-sided 97.5%% "
                               "Clopper-Pearson bound for zero events (%.4f), as the analyzer does" % cp_zero)}
    above = base_ub > THRESHOLD + 1e-12
    for direction in ("down", "up"):
        rec: dict = {"direction": direction}
        if direction == "down":
            rec["flip_type"] = "A 0->1 on J>=2 cells that are currently A=0 (removes pi-hat events)"
            slots = [i for i in range(len(clusters)) if ev[i] > 0]
            caps = [int(ev[i]) for i in slots]

            def bound(x, slots=slots):
                e = ev.copy()
                for s, v in zip(slots, x):
                    e[s] -= v
                return ub_of(e)
        else:
            rec["flip_type"] = "A 1->0 on J>=2 cells that are currently A=1 (adds pi-hat events)"
            slots = [i for i in range(len(clusters)) if cand[i] > 0]
            caps = [int(cand[i]) for i in slots]

            def bound(x, slots=slots):
                e = ev.copy()
                for s, v in zip(slots, x):
                    e[s] += v
                return ub_of(e)
        if (direction == "down") != above:
            rec["applicable"] = False
            rec["reason"] = ("the upper bound is already %s 10%%, so flips in this direction move it "
                             "away from the line" % ("above" if above else "at or below"))
            out[direction] = rec
            continue
        crossed = (lambda b: b <= THRESHOLD + 1e-12) if direction == "down" else (lambda b: b > THRESHOLD + 1e-12)
        res = search_min_flips(caps, bound, crossed, "min" if direction == "down" else "max")
        rec["applicable"] = True
        rec["crossing"] = "upper bound <= 10%" if direction == "down" else "upper bound > 10%"
        rec.update(_clip_result(res))
        rec["available_flips"] = int(sum(caps))
        if res.get("state") is not None:
            x = res["state"]
            e = ev.copy()
            for s, v in zip(slots, x):
                e[s] += (-v if direction == "down" else v)
            rec["n_clusters_touched"] = int(sum(1 for v in x if v))
            rec["statistic_at_witness"] = _pi_witness_check(cells, clusters, slots, x, direction, B, seed,
                                                            replay, e, n_k)
        out[direction] = rec
    # the registered G1 gate (cluster-level Clopper-Pearson) cannot be crossed downward at 33 clusters
    out["registered_G1_cluster_level_cp"] = {
        "clusters_with_event": int((ev > 0).sum()),
        "bound_at_baseline": ah.clopper_pearson_upper(int((ev > 0).sum()), len(clusters), G1_ALPHA),
        "bound_at_zero_event_clusters": cp_zero,
        "fewest_flips_to_reach_zero_event_clusters": events,
        "crossable_by_flips": bool(cp_zero <= THRESHOLD),
        "note": "see g1_design_fact: at this number of clusters the bound exceeds 10% even with no events",
    }
    return out


def _pi_witness_check(cells, clusters, slots, x, direction, B, seed, replay, e_vec, n_k) -> dict:
    """Apply the witness flips to cell copies and evaluate pi-hat through the analyzer's helper."""
    flipped = copy.deepcopy(cells)
    by_cluster: dict[str, list[dict]] = collections.defaultdict(list)
    for c in flipped:
        by_cluster[c["cluster_id"]].append(c)
    for s, v in zip(slots, x):
        pool = [c for c in by_cluster[clusters[s]] if c["J"] >= 2 and
                c["A"] == (0 if direction == "down" else 1)]
        for c in pool[:v]:
            c["A"] = 1 - c["A"]
    res = ah.silent_over_credit_rate(flipped, B=B, seed=seed, ties=TIES)
    if res["events"] == 0:
        return {"events": 0, "pi_hat": 0.0, "ci_hi": ah.clopper_pearson_upper(0, len(clusters), G1_ALPHA),
                "ci_hi_source": "cluster-level Clopper-Pearson (zero events)", "replay_matches_analyzer": True}
    ok = _close(replay.ratio_interval(e_vec, n_k)[2], res["ci_hi"])
    if not ok:
        raise AssertionError("bootstrap replay disagrees with analyze_holdout at a pi-hat witness")
    return {"events": res["events"], "pi_hat": res["pi_hat"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
            "ci_hi_source": "analyze_holdout.silent_over_credit_rate", "replay_matches_analyzer": True}


def tipping_contrast(rows: list[dict], B: int, seed: int) -> dict:
    """Flips that reverse the sign of the variant A->B delta, or its CI-excludes-0 status."""
    cells = _cells_for(rows, "AH")
    recs = paired_records(cells)
    clusters = [r["cluster_id"] for r in recs]
    if len(set(clusters)) != len(clusters) or len(recs) < 2:
        return {**FLAG, "status": "not_computable"}
    order = sorted(range(len(recs)), key=lambda i: recs[i]["cluster_id"])  # the helper sorts by cluster
    recs = [recs[i] for i in order]
    d0 = np.array([r["d"] for r in recs])
    n = len(recs)
    replay = Replay(n, B, seed)
    ones = np.ones(n)
    base = interval([{"cluster_id": r["cluster_id"], "d": r["d"]} for r in recs], _mean_d, B, seed)
    if base["ci_lo"] is None:
        return {**FLAG, "status": "not_computable", "reason": base.get("ci_reason", "no baseline interval")}
    theta, lo_r, hi_r = replay.ratio_interval(d0, ones)
    if not (_close(lo_r, base["ci_lo"]) and _close(hi_r, base["ci_hi"]) and _close(theta, base["estimate"])):
        raise AssertionError("bootstrap replay disagrees with analyze_holdout at the contrast baseline")
    base_status = _ci_status(base["ci_lo"], base["ci_hi"])
    sum0 = int(round(float(d0.sum())))

    # candidate slots: a J>=2 cell of variant A or B in a paired CQ; effect on that CQ's d
    slots: list[dict] = []
    for qi, r in enumerate(recs):
        for variant, cell in ((HIGH_VARIANT, r["hi"]), (LOW_VARIANT, r["lo"])):
            if cell["J"] >= 2:
                mag = cell["J"] - 1
                sign = 1 if variant == HIGH_VARIANT else -1  # d = L1*(B) - L1*(A)
                eff_if_credited_removed = -mag * sign        # A 1->0 on this cell
                eff = eff_if_credited_removed if cell["A"] == 1 else -eff_if_credited_removed
                slots.append({"q": qi, "variant": variant, "J": cell["J"], "from_A": cell["A"],
                              "flip": "1->0" if cell["A"] == 1 else "0->1", "effect": int(eff)})
    def d_after(x, subset):
        d = d0.copy()
        for s, v in zip(subset, x):
            if v:
                d[s["q"]] += s["effect"]
        return d

    def composition(subset, x):
        c = collections.Counter((s["variant"], s["J"], s["flip"]) for s, v in zip(subset, x) if v)
        return [{"variant": k[0], "J": k[1], "A_flip": k[2], "count": c[k]} for k in sorted(c)]

    out = {**FLAG,
           "baseline": {"delta": base["estimate"], "ci_lo": base["ci_lo"], "ci_hi": base["ci_hi"],
                        "ci_status": base_status, "n_paired_cqs": n, "replay_matches_analyzer": True},
           "candidate_flips": {"down": int(sum(1 for s in slots if s["effect"] < 0)),
                               "up": int(sum(1 for s in slots if s["effect"] > 0)),
                               "rule": "only J>=2 cells of variant A or B in a paired CQ can move L1*"}}

    for direction in ("down", "up"):
        subset = [s for s in slots if (s["effect"] < 0) == (direction == "down")]
        caps = [1] * len(subset)
        sgn = -1 if direction == "down" else 1
        # --- sign of the point estimate: exact (independent integer effects, take the largest) ---
        sign_rec: dict = {"direction": direction, "criterion": "point estimate reverses sign"}
        if sum0 == 0 or (sum0 > 0) == (direction == "up"):
            sign_rec.update(applicable=False, reason="the baseline delta is already on that side of 0"
                            if sum0 != 0 else "the baseline delta is exactly 0")
        else:
            gains = sorted((abs(s["effect"]) for s in subset), reverse=True)
            k_zero = k_strict = None
            cum = 0
            for k, g in enumerate(gains, 1):
                cum += g
                run = sum0 + sgn * cum
                if k_zero is None and ((run <= 0) if sum0 > 0 else (run >= 0)):
                    k_zero = k
                if (run < 0) if sum0 > 0 else (run > 0):
                    k_strict = k
                    break
            sign_rec.update(applicable=True, exact=True,
                            method="exact: independent integer effects, largest first",
                            min_flips_delta_reaches_zero=k_zero, min_flips_delta_strictly_reversed=k_strict,
                            available_flips=len(subset))
            if k_strict is not None:
                # witness: the k_strict largest-effect slots, ties by slot order
                pick = sorted(range(len(subset)), key=lambda i: (-abs(subset[i]["effect"]), i))[:k_strict]
                x = tuple(1 if i in pick else 0 for i in range(len(subset)))
                sign_rec["witness"] = _contrast_witness(recs, d_after(x, subset), B, seed, replay)
                sign_rec["witness_composition"] = composition(subset, x)
        out.setdefault("sign_reversal", {})[direction] = sign_rec
        # --- CI-excludes-0 status ---
        ci_rec: dict = {"direction": direction, "criterion": "95% BCa CI status for 0 changes",
                        "baseline_status": base_status}
        target = _ci_target(base_status, direction)
        if target is None:
            ci_rec.update(applicable=False, reason="flips in this direction move the interval away from the "
                                                   "status boundary")
        else:
            which, goal, crossed_fn = target

            def bound(x, subset=subset, which=which):
                _, lo_, hi_ = replay.ratio_interval(d_after(x, subset), ones)
                return lo_ if which == "ci_lo" else hi_

            res = search_min_flips(caps, bound, crossed_fn, goal)
            ci_rec.update(applicable=True, pushed_bound=which,
                          crossing={"includes_0": "interval includes 0",
                                    "excludes_0_positive": "ci_lo > 0",
                                    "excludes_0_negative": "ci_hi < 0"}[_target_status(base_status, direction)],
                          available_flips=len(subset))
            ci_rec.update(_clip_result(res))
            if res.get("state") is not None:
                ci_rec["witness"] = _contrast_witness(recs, d_after(res["state"], subset), B, seed, replay)
                ci_rec["witness_composition"] = composition(subset, res["state"])
        out.setdefault("ci_status_change", {})[direction] = ci_rec
    return out


def _target_status(base_status: str, direction: str) -> str:
    if base_status == "includes_0":
        return "excludes_0_positive" if direction == "up" else "excludes_0_negative"
    return "includes_0"


def _ci_target(base_status: str, direction: str):
    """(bound to push, 'min'/'max', crossed predicate) for moving the CI status in a direction."""
    if base_status == "includes_0":
        if direction == "up":
            return ("ci_lo", "max", lambda b: b > TOL)
        return ("ci_hi", "min", lambda b: b < -TOL)
    if base_status == "excludes_0_positive" and direction == "down":
        return ("ci_lo", "min", lambda b: b <= TOL)
    if base_status == "excludes_0_negative" and direction == "up":
        return ("ci_hi", "max", lambda b: b >= -TOL)
    return None


def _contrast_witness(recs, d_vec, B, seed, replay) -> dict:
    res = interval([{"cluster_id": r["cluster_id"], "d": float(d)} for r, d in zip(recs, d_vec)],
                   _mean_d, B, seed)
    _, lo_r, hi_r = replay.ratio_interval(d_vec, np.ones(len(recs)))
    if not (_close(lo_r, res["ci_lo"]) and _close(hi_r, res["ci_hi"])):
        raise AssertionError("bootstrap replay disagrees with analyze_holdout at a contrast witness")
    return {"delta": res["estimate"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
            "ci_status": _ci_status(res["ci_lo"], res["ci_hi"]), "replay_matches_analyzer": True}


# --------------------------------------------------------------------------
# G1 design fact
# --------------------------------------------------------------------------
def g1_design_fact(n_clusters: int) -> dict:
    g = ah.g1_achievability(n_clusters, G1_ALPHA)
    return {
        **FLAG,
        "n_clusters": n_clusters,
        "one_sided_level": 1 - G1_ALPHA,
        "zero_event_upper_bound": ah.clopper_pearson_upper(0, n_clusters, G1_ALPHA),
        "zero_event_upper_bound_pct_2dp": round(100 * ah.clopper_pearson_upper(0, n_clusters, G1_ALPHA), 2),
        "one_sided_95_zero_event_upper_bound": ah.clopper_pearson_upper(0, n_clusters, 0.05),
        "threshold": THRESHOLD,
        "passable_at_this_n": bool(g["achievable"]),
        "min_clusters_for_a_zero_event_pass": g["min_clusters_for_zero_event_pass"],
        "note": ("A property of the design (the number of clusters), not of the data: with zero events among "
                 "%d clusters the bound already exceeds 10%%." % n_clusters),
    }


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------
def analyze(rows: list[dict], *, B: int, seed: int) -> dict:
    blocks = {s: source_block(rows, s, B, seed) for s in SOURCES}
    ah_block = blocks["AH"]
    out = {
        "status": STATUS,
        "design": {
            "n_primary_cells": len(rows), "n_clusters": len({r["cluster_id"] for r in rows}),
            "unit": "CQ cluster (cluster_id equals cq_id)", "interval": "95% BCa cluster bootstrap",
            "resamples": B, "seed": seed, "bca_ties": TIES,
            "registered_scheme": bool(B == B_REGISTERED and seed == SEED),
            "multiplicity": "none applied; marginal intervals; no p-values; nothing here is a test",
            "J_distribution": {str(j): sum(r["J"] == j for r in rows) for j in range(4)},
            "variant_cells": {v: sum(r["variant"] == v for r in rows)
                              for v in sorted({r["variant"] for r in rows})},
        },
        "item1_table_2x2_AH": ah_block["table_2x2"],
        "item2_over_and_under_credit_AH": ah_block["credit_rates"],
        "item3_label_source_comparison": {
            **FLAG,
            "sources": blocks,
            "agreement_between_sources": [agreement_block(rows, f, s, B, seed) for f, s in PAIRS],
            "paired_differences_between_sources": [paired_difference_block(rows, f, s, B, seed)
                                                   for f, s in PAIRS],
        },
        "item4_rater_error_tipping_points_AH": {
            **FLAG,
            "what_is_flipped": "A labels of the AH source, one cell at a time; adversarial (worst-case) flip "
                               "sets; each criterion has its own adversary",
            "pi_hat_upper_bound_vs_10pct": tipping_pi(rows, B, seed),
            "variant_A_to_B_contrast": tipping_contrast(rows, B, seed),
        },
        "item5_g1_design_fact": g1_design_fact(len({r["cluster_id"] for r in rows})),
        "descriptive": {
            **FLAG,
            "AH_A1_on_J0_cells": {
                "n": sum(r["J"] == 0 and r["A"]["AH"] == 1 for r in rows),
                "of_which_span_edited": sum(r["J"] == 0 and r["A"]["AH"] == 1 and r["span_edited"] for r in rows),
                "note": "J=0 coincides with an empty judge span in every cell (legacy_counts.json), "
                        "so A=1 there is not a verdict on a span the judge cited; L1* never rises with A"},
        },
    }
    return out


def _scrub(x):
    """JSON-safe: tuples to lists, NaN/inf to None, numpy scalars to Python."""
    if isinstance(x, dict):
        return {str(k): _scrub(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_scrub(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return _finite_or_none(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def build_report(per_cell: Path, cells: Path, drafts: Path, aux: Path, *, B: int, seed: int) -> dict:
    rows, checks, extras = load_inputs(per_cell, cells, drafts, aux)
    out = analyze(rows, B=B, seed=seed)
    t = table_of(_cells_for(rows, "AH"))
    n_j2 = t.n11 + t.n10
    n_j0 = sum(r["J"] == 0 for r in rows)
    checks["consistency_with_the_brief"] = {
        "pi_events_14_of_188": bool((t.n10, t.n) == (14, 188)),
        "over_credit_14_of_132": bool((t.n10, n_j2) == (14, 132)),
        "under_credit_17_of_47": bool((sum(r["J"] == 0 and r["A"]["AH"] == 1 for r in rows), n_j0) == (17, 47)),
        "informational": "expected counts from the request; they describe the real data, not a rule",
    }
    out["checks"] = checks
    out["inputs"] = {
        "per_cell": {"file": Path(per_cell).name, "sha256": sha256_file(per_cell),
                     "role": "per-cell J, A (AH), rater_L1, L1* (unsealed 2026-10-09)"},
        "cells": {"file": Path(cells).name, "sha256": sha256_file(cells), "role": "judge run; J and ids only"},
        "drafts": {"file": Path(drafts).name, "sha256": sha256_file(drafts),
                   "role": "A_draft before author revision; only cell_id, A_draft and model are read",
                   **{"model_field_values": extras["draft_file_model_field_values"]}},
        "aux": {"file": Path(aux).name, "sha256": sha256_file(aux), "role": "GPT-5.6 auxiliary A labels",
                "model_field_values": extras["aux_file_model_field_values"]},
    }
    out["code"] = {
        "exploratory_reanalysis.py": sha256_file(Path(__file__)),
        "analyze_holdout.py": sha256_file(HARNESS / "analyze_holdout.py"),
        "python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__,
    }
    out["no_new_data"] = "no new human label and no new LLM call; aggregates only (no cell, CQ or cluster id, no span, no note)"
    return _scrub(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--per-cell", type=Path,
                    default=HERE / "unsealed_2026-10-09" / "per_cell.rerun_0dbe6e9.json")
    ap.add_argument("--cells", type=Path, default=HERE.parent / "cells.jsonl")
    ap.add_argument("--drafts", type=Path, required=True)
    ap.add_argument("--aux", type=Path, default=HERE.parent / "llm_auxiliary_labels.jsonl")
    ap.add_argument("--out", type=Path, default=HERE / "exploratory_reanalysis.json")
    ap.add_argument("--resamples", type=int, default=B_REGISTERED)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    inputs = [args.per_cell, args.cells, args.drafts, args.aux]
    for p in inputs:
        refuse_input(p)
    out_path = refuse_output(args.out, inputs)
    print(STATUS, file=sys.stderr)
    report = build_report(args.per_cell, args.cells, args.drafts, args.aux, B=args.resamples, seed=args.seed)
    text = json.dumps(report, indent=1, allow_nan=False) + "\n"
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {out_path.name} sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
