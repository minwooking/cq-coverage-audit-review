#!/usr/bin/env python3
"""Review 9 (post hoc, exploratory, label-free check): verbatim-span check on the 188 primary Brick holdout cells.

AI-generated; a person must review and test it before reuse.  No model call, no network, no server access.

Question.  Does the span a judge quotes (``evidence``) occur verbatim in the rendering the judge saw?  The check is
applied to every primary cell, and then scored against the evidence labels: how many of the unsupported-credit events
(J >= 2 and S = 0, the events of pi-hat) fail the check (recall), how many supported credits fail it (false-flag rate),
what pi-hat becomes when credit is withdrawn on failing cells (withdraw-only, like L1*), and what happens to the A->B
contrast.

Matcher.  ``norm`` and ``verbatim`` are IMPORTED from harness/review6_natural/analyze_natural.py (the natural-corpus
check of Addendum 27), so the two checks are literally the same test: whitespace runs collapse to one space and the
ends are stripped, case sensitive, plain substring test against the whitespace-normalised view; a list of spans counts
only if every non-empty string element does; an empty or non-string span fails.

Credit.  A credited cell is a cell with J >= 2 (the check's domain in the natural-corpus check and the domain of the
registered pi-hat event).  Withdrawal: J* = J if J < 2 or the span is verbatim, else min(J, 1) (the natural-corpus
demotion).  Sensitivities (flagged as such): full withdrawal (J* = 0 on a failing credit) and an elision-tolerant
matcher (a span split at '...' or the ellipsis character; every fragment of at least 12 characters must be verbatim;
a strict pass is always a pass).

Inputs (all existing, none restricted): see INPUTS.  Labels are the de-identified analysis files that the paper's own
scripts read (harness/review6_reanalysis/common.py): the unsealed AH per-cell file and the second rater's v3 per-cell
file.  Only aggregates are written; no per-cell label or label disagreement is written.

Intervals: question(CQ)-clustered BCa, 95%, B = 10,000, seed 20260913, the analyzer's resampling (same draws, same
``_bca_interval``; ``fast_ci`` is checked against ``analyze_holdout.cluster_bootstrap_stat`` in the self-test and on the
headline statistics of the run).

Usage:  python3 analyze.py            (self-test, then the analysis, writes results.json next to this file)
        python3 analyze.py --selftest  (matcher and bootstrap tests only; also collected by ``pytest analyze.py``)
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
H = HERE.parent                      # paper/access2026/harness
PAPER = H.parent                     # paper/access2026
sys.path.insert(0, str(H))
sys.path.insert(0, str(H / "review6_natural"))

import analyze_holdout as ah  # noqa: E402
from analyze_natural import norm, verbatim, view_of  # noqa: E402  (THE matcher of the natural-corpus check)

B, SEED = ah.BOOTSTRAP_RESAMPLES, ah.REGISTERED_SEED
assert (B, SEED) == (10_000, 20260913)

INPUTS = {
    "judge_cells_gemini": H / "real_run/cells.jsonl",
    "variant_views": H / "variants",                                   # {A..F}/rendered_view.txt
    "labels_AH": H / "real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json",
    "labels_second_rater_v3": PAPER / "annotation/second_pass_2026-10-13/v3/results_v3_cells.json",
    "labels_second_rater_v1_csv": PAPER / "annotation/second_pass_2026-10-13/labels_for_analysis.csv",
    "luna_length_cells": H / "length_experiment/cells_length.jsonl",
    "luna_length_inputs": H / "length_experiment/inputs",
    "luna_full_r35_cells": H / "length_experiment/luna_full_r35/cells_luna_full_r35.jsonl",
    "panel48_luna": H / "real_run/paired_ai_audit_48/gpt-5.6-luna/cells.jsonl",
    "panel48_sonnet": H / "real_run/paired_ai_audit_48/anthropic__claude-sonnet-5-5/cells.jsonl",
    "gptoss_raw": H / "review6_judges/raw/raw_gptoss.jsonl",
    "glm_raw": H / "review6_judges/raw/raw_glm.jsonl",
    "judge_jobs": H / "review6_judges/jobs.jsonl",
    "existing_output_r4": H / "review6_reanalysis/parts/r4.json",              # cross-check only
    "existing_output_review6_judges": H / "review6_judges/results.json",       # cross-check only
}
VARIANTS = list("ABCDEF")
DWELL_FAST_S = 20.0           # G7's "fast" threshold (PREREG L349)
MIN_FRAGMENT = 12
_ELIDE = re.compile(r"\.{3,}|…")


# ------------------------------------------------------------------ matcher variants (strict = natural-corpus rule)
def verbatim_elided(evidence, view_n: str) -> bool:
    """Sensitivity only.  Strict pass OR every >=12-character fragment (split at '...'/ellipsis) occurs verbatim."""
    if verbatim(evidence, view_n):
        return True

    def frags(e: str) -> list[str]:
        return [f for f in (norm(x) for x in _ELIDE.split(norm(e))) if len(f) >= MIN_FRAGMENT]

    if isinstance(evidence, str):
        ps = frags(evidence)
    elif isinstance(evidence, list):
        ps = [f for x in evidence if isinstance(x, str) for f in frags(x)]
    else:
        return False
    return bool(ps) and all(p in view_n for p in ps)


def j_star(j: int, ok: bool, to_zero: bool = False) -> int:
    """Withdraw-only: a credit (J >= 2) without a verbatim span is cut to min(J, 1) (or to 0 in the sensitivity)."""
    if j < 2 or ok:
        return j
    return 0 if to_zero else min(j, 1)


# ------------------------------------------------------------------ bootstrap (the analyzer's draws)
_DRAWS: dict[int, np.ndarray] = {}


def _draws(n: int) -> np.ndarray:
    if n not in _DRAWS:
        rng = np.random.default_rng(SEED)
        _DRAWS[n] = np.stack([rng.integers(0, n, n) for _ in range(B)])
    return _DRAWS[n]


def cluster_sums(clusters, cols: list) -> np.ndarray:
    """Per-cluster additive statistics, clusters in sorted string order (the analyzer's order)."""
    keys = sorted({str(c) for c in clusters})
    pos = {k: i for i, k in enumerate(keys)}
    M = np.zeros((len(keys), len(cols)))
    ix = np.array([pos[str(c)] for c in clusters])
    for j, col in enumerate(cols):
        np.add.at(M[:, j], ix, np.asarray(col, dtype=float))
    return M


def fast_ci(M: np.ndarray) -> dict | None:
    """Ratio statistic sum(col0)/sum(col1) over resampled clusters; BCa 95% as analyze_holdout.cluster_bootstrap_stat.
    Resamples (or leave-one-cluster-out jackknife values) with a zero denominator are dropped and counted."""
    M = np.asarray(M, dtype=float)
    n = M.shape[0]
    tot = M.sum(0)
    if n < 2 or tot[1] <= 0:
        return None
    theta = float(tot[0] / tot[1])
    S = M[_draws(n)].sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        boot = S[:, 0] / S[:, 1]
        jk = tot[None, :] - M
        jack = jk[:, 0] / jk[:, 1]
    undef = int((~np.isfinite(boot)).sum())
    boot, jack = boot[np.isfinite(boot)], jack[np.isfinite(jack)]
    lo, hi = ah._bca_interval(theta, boot, jack, ah.RESOLVE_ALPHA, ah.DEFAULT_BCA_TIES)
    out = {"est": theta, "lo": float(lo), "hi": float(hi), "n_clusters": n}
    if undef:
        out["n_undefined_resamples"] = undef
    return out


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list | None:
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def rnd(x, nd=4):
    if isinstance(x, dict):
        return {k: rnd(v, nd) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [rnd(v, nd) for v in x]
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else round(float(x), nd)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


# ------------------------------------------------------------------ loaders
def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def valid_score(r: dict) -> bool:
    j = r.get("J")
    return bool(r.get("judge_response_parsed")) and type(j) is int and 0 <= j <= 3


def load_views() -> dict[str, str]:
    """Normalised full views (what the primary and luna-full judges saw) with a digest check against the cells."""
    out = {}
    for v in VARIANTS:
        txt = (INPUTS["variant_views"] / v / "rendered_view.txt").read_text(encoding="utf-8")
        out[v] = (hashlib.sha256(txt.encode()).hexdigest(), norm(txt))
    return out


def load_labels() -> dict[str, dict]:
    """cell_id -> {S_AH, S_2, R_AH, R_2, dwell, variant, cq, J_label_file}.  The 188 primary cells."""
    ahc = {c["cell_id"]: c for c in json.loads(INPUTS["labels_AH"].read_text())["primary_cells"]}
    v3 = {c["cell_id"]: c for c in json.loads(INPUTS["labels_second_rater_v3"].read_text())["primary_cells"]}
    assert len(ahc) == 188 and set(ahc) == set(v3)
    lab = {}
    for cid, a in ahc.items():
        assert a["J"] == v3[cid]["J"]
        lab[cid] = {"S_AH": int(a["A"]), "S_2": int(v3[cid]["A"]), "R_AH": int(a["rater_L1"]), "R_2": int(v3[cid]["rater_L1"]),
                    "dwell_AH_s": a.get("audit_elapsed_s"), "variant": a["variant"], "cq": a["cq_id"], "cluster": a["cluster_id"],
                    "J_file": int(a["J"])}
    return lab


class Run:
    def __init__(self, name: str, desc: str, view_note: str):
        self.name, self.desc, self.view_note = name, desc, view_note
        self.recs: list[dict] = []
        self.notes: dict = {}

    def add(self, cell_id, J, evidence, view_n, repeat=None):
        _, v, cq = cell_id.split(":")
        self.recs.append({"cell_id": cell_id, "variant": v, "cq": cq, "cluster": cq, "J": int(J), "evidence": evidence,
                          "view_n": view_n, "repeat": repeat})


def _evidence(r: dict):
    jr = r.get("judge_response")
    if isinstance(jr, dict):
        return jr.get("evidence")
    return r.get("evidence")


def build_runs(views: dict[str, tuple[str, str]]) -> list[Run]:
    runs: list[Run] = []
    # 1. primary holdout judge (gemini-3.6-flash), full views, 188 primary cells
    r = Run("gemini_primary", "registered holdout judge (gemini-3.6-flash), full renderings", "full view (variants/<V>/rendered_view.txt)")
    for c in jsonl(INPUTS["judge_cells_gemini"]):
        if c["cell_kind"] != "primary":
            continue
        assert valid_score(c), c["cell_id"]
        assert views[c["variant"]][0] == c["artifact_digest"], f"view digest mismatch {c['cell_id']}"
        r.add(c["cell_id"], c["J"], _evidence(c), views[c["variant"]][1])
    runs.append(r)

    # 2. luna (gpt-5.6-luna) on the same full views: A from the length experiment, B-F from luna_full_r35; last valid record wins
    L = INPUTS["luna_length_inputs"]
    len_rows = jsonl(INPUTS["luna_length_cells"])
    full_rows = [x for x in len_rows if x["condition"] == "full"] + jsonl(INPUTS["luna_full_r35_cells"])
    last: dict[str, dict] = {}
    for x in sorted(full_rows, key=lambda x: x["started_at_utc"]):
        if valid_score(x):
            last["primary:" + x["pair_id"]] = x
    r = Run("luna_full", "gpt-5.6-luna (substitute judge), full renderings", "full view (variants/<V>/rendered_view.txt)")
    for cid, x in sorted(last.items()):
        assert views[x["variant"]][0] == x["artifact_digest"], f"view digest mismatch {cid}"
        r.add(cid, x["J"], _evidence(x), views[x["variant"]][1])
    runs.append(r)

    # 3/4. luna on the subgraph and the 60k-character 'limited' views (view file digest checked against the cell)
    for cond, name, note in (("subgraph", "luna_subgraph", "question-relevant subgraph text"),
                             ("limited", "luna_limited60k", "view truncated to 60,000 characters")):
        last = {}
        for x in sorted((x for x in len_rows if x["condition"] == cond), key=lambda x: x["started_at_utc"]):
            if valid_score(x):
                last["primary:" + x["pair_id"]] = x
        r = Run(name, f"gpt-5.6-luna (substitute judge), {note}", note)
        for cid, x in sorted(last.items()):
            txt = (L / x["variant"] / x["cq_id"] / f"{cond}.txt").read_text(encoding="utf-8")
            assert hashlib.sha256(txt.encode()).hexdigest() == x["artifact_digest"], f"view digest mismatch {cid}"
            r.add(cid, x["J"], _evidence(x), norm(txt))
        runs.append(r)

    # 5/6. 48-cell cross-family panel on the full views
    for key, name, desc in (("panel48_luna", "panel48_luna", "gpt-5.6-luna on the 48 registered panel cells, full renderings"),
                            ("panel48_sonnet", "panel48_sonnet", "claude-sonnet-5-5 on the 48 registered panel cells, full renderings")):
        r = Run(name, desc, "full view")
        for x in jsonl(INPUTS[key]):
            if x["cell_kind"] != "primary" or not valid_score(x):
                continue
            assert views[x["variant"]][0] == x["artifact_digest"], f"view digest mismatch {x['cell_id']}"
            r.add(x["cell_id"], x["J"], _evidence(x), views[x["variant"]][1])
        runs.append(r)

    # 7-12. gpt-oss-20b and GLM-4.7-Flash (shared-server, review6_judges), subgraph views, three temperature-0 repeats each
    jobs = {j["cell_id"]: j for j in jsonl(INPUTS["judge_jobs"]) if j["study"] == "holdout_subgraph"}
    for key, jn, desc in (("gptoss_raw", "gptoss", "openai/gpt-oss-20b (non-Qwen)"), ("glm_raw", "glm", "zai-org/GLM-4.7-Flash (non-Qwen)")):
        raw = [x for x in jsonl(INPUTS[key]) if x["study"] == "holdout_subgraph" and x["valid"] and x["J"] in (0, 1, 2, 3)]
        views_n = {cid: norm(view_of(j)) for cid, j in jobs.items()}
        for rep in (1, 2, 3):
            r = Run(f"{jn}_r{rep}", f"{desc}, subgraph views, repeat {rep}", "question-relevant subgraph text (jobs.jsonl)")
            seen = set()
            for x in raw:
                if int(x["repeat"]) != rep:
                    continue
                assert x["prompt_sha256"] == jobs[x["cell_id"]]["prompt_sha256"], x["cell_id"]
                assert x["cell_id"] not in seen
                seen.add(x["cell_id"])
                r.add(x["cell_id"], x["J"], x.get("evidence"), views_n[x["cell_id"]], repeat=rep)
            runs.append(r)
    return runs


# ------------------------------------------------------------------ per-run analysis
def _ratio(clusters, num, den):
    return fast_ci(cluster_sums(clusters, [num, den]))


def _fmt_ci(d):
    if d is None:
        return None
    out = {"est": d["est"], "ci95": [d["lo"], d["hi"]], "n_clusters": d["n_clusters"]}
    if "n_undefined_resamples" in d:
        out["n_undefined_resamples"] = d["n_undefined_resamples"]
    if d["lo"] == d["hi"]:
        out["degenerate_interval_note"] = "every resample gave the same value (estimate on the boundary); the interval carries no information"
    return out


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> list | None:
    """Exact two-sided interval (cluster-level proportions of a few clusters)."""
    if n <= 0:
        return None
    lo = 0.0 if k == 0 else float(stats.beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - alpha / 2, k + 1, n - k))
    return [lo, hi]


def contrast(score_by_cell: dict[str, float], v1="A", v2="B") -> dict | None:
    """Pooled mean of per-question (v2 - v1) differences; question clusters; the paper's A->B estimator."""
    a = {c.split(":")[2]: s for c, s in score_by_cell.items() if c.split(":")[1] == v1}
    b = {c.split(":")[2]: s for c, s in score_by_cell.items() if c.split(":")[1] == v2}
    qs = sorted(set(a) & set(b))
    if len(qs) < 2:
        return None
    d = [b[q] - a[q] for q in qs]
    ci = fast_ci(cluster_sums(qs, [d, [1.0] * len(qs)]))
    out = _fmt_ci(ci)
    out["n_paired_questions"] = len(qs)
    out["B_gt_A_eq_lt"] = [sum(x > 1e-9 for x in d), sum(abs(x) <= 1e-9 for x in d), sum(x < -1e-9 for x in d)]
    return out


def analyze_run(run: Run, lab: dict, matcher) -> dict:
    recs = run.recs
    for r in recs:
        r["ok"] = matcher(r["evidence"], r["view_n"])
    cid = [r["cell_id"] for r in recs]
    cl = [r["cluster"] for r in recs]
    J = np.array([r["J"] for r in recs])
    ok = np.array([r["ok"] for r in recs])
    var = np.array([r["variant"] for r in recs])
    cred = J >= 2
    fail = cred & ~ok
    out: dict = {"n_cells": len(recs), "n_clusters": len({str(c) for c in cl}),
                 "cells_by_variant": {v: int((var == v).sum()) for v in VARIANTS if (var == v).any()}}
    # share of credits whose span is verbatim (label-free)
    one = np.ones(len(recs))
    out["credited_J_ge2"] = int(cred.sum())
    out["credited_verbatim"] = int((cred & ok).sum())
    out["share_verbatim_of_credited"] = _fmt_ci(_ratio(cl, (cred & ok).astype(float), cred.astype(float)))
    out["credited_failing_by_J"] = {str(j): int(((J == j) & fail).sum()) for j in (2, 3)}
    out["credited_by_J"] = {str(j): int(((J == j) & cred).sum()) for j in (2, 3)}
    out["J1_cells"] = int((J == 1).sum())
    out["J1_cells_verbatim"] = int(((J == 1) & ok).sum())
    out["by_variant"] = {}
    for v in VARIANTS:
        m = var == v
        if m.any():
            out["by_variant"][v] = {"credited": int((cred & m).sum()), "verbatim": int((cred & ok & m).sum()),
                                    "failing": int((fail & m).sum())}
    # effect on J and on pi-hat / contrast
    Js = np.array([j_star(int(j), bool(o)) for j, o in zip(J, ok)])
    Js0 = np.array([j_star(int(j), bool(o), True) for j, o in zip(J, ok)])
    out["mean_J"] = float(J.mean())
    out["mean_Jstar"] = float(Js.mean())
    sc_J = {c: float(x) for c, x in zip(cid, J)}
    sc_Js = {c: float(x) for c, x in zip(cid, Js)}
    sc_Js0 = {c: float(x) for c, x in zip(cid, Js0)}
    out["A_to_B"] = {"J": contrast(sc_J), "Jstar_withdraw_to_min(J,1)": contrast(sc_Js), "Jstar_zero_sensitivity": contrast(sc_Js0)}
    out["labels"] = {}
    for src, key in (("AH", "S_AH"), ("second_rater", "S_2")):
        S = np.array([lab[c][key] for c in cid])
        ev = cred & (S == 0)                     # unsupported-credit event (the registered pi event)
        sup = cred & (S == 1)
        evf, supf = ev & ~ok, sup & ~ok
        ev_after = ev & ok                       # events that survive the withdrawal
        n_ev, n_sup, n_flag = int(ev.sum()), int(sup.sum()), int(fail.sum())
        table = {"events_fail": int(evf.sum()), "events_pass": int(ev_after.sum()),
                 "supported_credited_fail": int(supf.sum()), "supported_credited_pass": int((sup & ok).sum())}
        fisher_p = None
        if n_ev and n_sup:
            fisher_p = float(stats.fisher_exact([[table["events_fail"], table["events_pass"]],
                                                 [table["supported_credited_fail"], table["supported_credited_pass"]]])[1])
        sc_L = {c: float(J[i] if S[i] == 1 else min(J[i], 1)) for i, c in enumerate(cid)}               # L1*
        sc_Lc = {c: float(Js[i] if S[i] == 1 else min(Js[i], 1)) for i, c in enumerate(cid)}             # L1* after the check
        cl_arr = np.array([str(c) for c in cl])
        ev_cl = {c for c in cl_arr[ev]}
        evf_cl = {c for c in cl_arr[evf]}
        sup_cl = {c for c in cl_arr[sup]}
        supf_cl = {c for c in cl_arr[supf]}
        pi_raw = _ratio(cl, ev.astype(float), one)
        pi_after = _ratio(cl, ev_after.astype(float), one)
        res = {
            "events": n_ev, "supported_credited": n_sup, "flagged_credits": n_flag,
            "table_2x2_credited_cells": table, "fisher_exact_p_cell_level_ignores_clustering": fisher_p,
            "recall_events_failing": {"k": int(evf.sum()), "n": n_ev, "frac": (int(evf.sum()) / n_ev) if n_ev else None,
                                      "wilson95_cell_level": wilson(int(evf.sum()), n_ev),
                                      "cluster_bca95": _fmt_ci(_ratio(cl, evf.astype(float), ev.astype(float)))},
            "recall_cluster_level": {"clusters_with_event": len(ev_cl), "of_which_with_a_failing_event": len(evf_cl),
                                     "clopper_pearson95": clopper_pearson(len(evf_cl), len(ev_cl))},
            "false_flag_cluster_level": {"clusters_with_supported_credit": len(sup_cl), "of_which_with_a_failing_supported_credit": len(supf_cl),
                                         "clopper_pearson95": clopper_pearson(len(supf_cl), len(sup_cl))},
            "false_flag_supported_credited_failing": {"k": int(supf.sum()), "n": n_sup, "frac": (int(supf.sum()) / n_sup) if n_sup else None,
                                                      "wilson95_cell_level": wilson(int(supf.sum()), n_sup),
                                                      "cluster_bca95": _fmt_ci(_ratio(cl, supf.astype(float), sup.astype(float)))},
            "precision_flagged_that_are_events": {"k": int(evf.sum()), "n": n_flag, "frac": (int(evf.sum()) / n_flag) if n_flag else None,
                                                  "wilson95_cell_level": wilson(int(evf.sum()), n_flag)},
            "base_rate_event_among_credited": {"k": n_ev, "n": int(cred.sum()), "frac": (n_ev / int(cred.sum())) if cred.sum() else None},
            "sensitivity_credit_defined_as_J_ge_1_counts_only": {
                "unsupported_J_ge1_S0": int(((J >= 1) & (S == 0)).sum()),
                "unsupported_J_ge1_S0_failing": int(((J >= 1) & (S == 0) & ~ok).sum()),
                "supported_J_ge1_S1": int(((J >= 1) & (S == 1)).sum()),
                "supported_J_ge1_S1_failing": int(((J >= 1) & (S == 1) & ~ok).sum())},
            "pi_hat_raw": _fmt_ci(pi_raw),
            "pi_hat_after_withdrawal": _fmt_ci(pi_after),
            "pi_events_after": int(ev_after.sum()),
            "pi_clusters_with_event_raw": len({cl[i] for i in np.where(ev)[0]}),
            "pi_clusters_with_event_after": len({cl[i] for i in np.where(ev_after)[0]}),
            "A_to_B": {"L1star": contrast(sc_L), "L1star_after_check": contrast(sc_Lc)},
        }
        if int(ev_after.sum()) == 0 and n_ev:
            res["pi_hat_after_withdrawal_note"] = ("zero events remain: the registered BCa interval is undefined (a bootstrap cannot resample an "
                                                   "event it has never seen); cell-level Clopper-Pearson 97.5% upper limit (ignores clustering) "
                                                   f"= {ah.clopper_pearson_upper(0, len(recs)):.4f}")
        out["labels"][src] = res
    return out


# ------------------------------------------------------------------ failure modes (label-free) for one run
def longest_verbatim_prefix(e: str, view_n: str) -> int:
    lo, hi = 0, len(e)
    while lo < hi:
        m = (lo + hi + 1) // 2
        if e[:m] in view_n:
            lo = m
        else:
            hi = m - 1
    return lo


def divergence_detail(run: Run) -> list[dict]:
    """Label-free: for each failing J >= 1 string span, where the longest verbatim prefix stops and what the view has there."""
    rows = []
    for r in sorted(run.recs, key=lambda r: r["cell_id"]):
        e = r["evidence"]
        if r["J"] < 1 or verbatim(e, r["view_n"]):
            continue
        if isinstance(e, list):
            parts = [norm(x) for x in e if isinstance(x, str) and norm(x)]
            rows.append({"cell_id": r["cell_id"], "J": r["J"], "span_kind": "list", "elements": len(parts),
                         "elements_verbatim": sum(p in r["view_n"] for p in parts)})
            continue
        n_e = norm(e)
        k = longest_verbatim_prefix(n_e, r["view_n"])
        pos = r["view_n"].find(n_e[:k]) if k else -1
        rows.append({"cell_id": r["cell_id"], "J": r["J"], "span_kind": "string", "span_chars": len(n_e), "verbatim_prefix_chars": k,
                     "span_next_30": n_e[k:k + 30], "view_next_30": (r["view_n"][pos + k:pos + k + 30] if pos >= 0 else None)})
    return rows


def failure_modes(run: Run) -> dict:
    cnt, ex, rescued, pf = Counter(), [], 0, []
    for r in run.recs:
        if r["J"] < 2 or verbatim(r["evidence"], r["view_n"]):
            continue
        e = r["evidence"]
        txt = e if isinstance(e, str) else " ".join(x for x in e if isinstance(x, str)) if isinstance(e, list) else ""
        kind = "list_of_spans" if isinstance(e, list) else "contains_ellipsis" if _ELIDE.search(txt) else "other"
        cnt[kind] += 1
        if isinstance(e, str):
            n_e = norm(e)
            pf.append(longest_verbatim_prefix(n_e, r["view_n"]) / len(n_e))
        rescued += verbatim_elided(e, r["view_n"])
        if kind == "other" and len(ex) < 3:
            ex.append({"variant": r["variant"], "J": r["J"], "span_head_100": norm(txt)[:100], "span_chars": len(norm(txt))})
    return {"failing_credits": sum(cnt.values()), "by_kind": dict(cnt), "rescued_by_elision_tolerant_rule": rescued,
            "longest_verbatim_prefix_share_of_span_string_spans_only": ({"n": len(pf), "median": float(np.median(pf)), "min": float(min(pf)),
                                                                          "max": float(max(pf))} if pf else None),
            "examples_other": ex}


# ------------------------------------------------------------------ dwell (AH rater) versus second rater
def dwell_analysis(lab: dict, J_gem: dict) -> dict:
    cells = [c for c in lab if lab[c]["dwell_AH_s"] is not None]
    out = {"source": "harness/real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json, field audit_elapsed_s "
                     "(server save time minus page-load stamp; every cell saved once)",
           "second_rater_dwell": "blank for all 188 cells in the second rater's files (labels_v3 REPORT, dwell_seconds 0 filled): not usable",
           "n_cells_with_dwell": len(cells), "threshold_s": DWELL_FAST_S}
    d = np.array([lab[c]["dwell_AH_s"] for c in cells], dtype=float)
    out["dwell_summary_s"] = {"median": float(np.median(d)), "min": float(d.min()), "max": float(d.max()),
                              "n_under_20": int((d < DWELL_FAST_S).sum()), "n_at_or_over_20": int((d >= DWELL_FAST_S).sum())}
    fast = d < DWELL_FAST_S
    cl = [lab[c]["cluster"] for c in cells]
    rng = np.random.default_rng(SEED)

    def block(mask_extra, name):
        m = mask_extra
        r = {}
        for tag, y in (("S_disagree", np.array([lab[c]["S_AH"] != lab[c]["S_2"] for c in cells], float)),
                       ("R_disagree_exact", np.array([lab[c]["R_AH"] != lab[c]["R_2"] for c in cells], float))):
            nf, ns = int((fast & m).sum()), int((~fast & m).sum())
            kf, ks = int((y[fast & m]).sum()), int((y[~fast & m]).sum())
            ent = {"under_20s": {"n": nf, "disagree": kf, "rate": kf / nf if nf else None, "wilson95": wilson(kf, nf)},
                   "at_or_over_20s": {"n": ns, "disagree": ks, "rate": ks / ns if ns else None, "wilson95": wilson(ks, ns)}}
            if nf and ns:
                ent["risk_difference_under_minus_over"] = kf / nf - ks / ns
                ent["fisher_exact_p_cell_level_ignores_clustering"] = float(stats.fisher_exact([[kf, nf - kf], [ks, ns - ks]])[1])
                # question-cluster percentile bootstrap of the risk difference (same draws as the analyzer)
                M = cluster_sums([c for c, mm in zip(cl, m) if mm],
                                 [y[m] * fast[m], fast[m].astype(float), y[m] * (~fast[m]), (~fast[m]).astype(float)])
                idx = _draws(M.shape[0])
                S = M[idx].sum(1)
                with np.errstate(divide="ignore", invalid="ignore"):
                    rd = S[:, 0] / S[:, 1] - S[:, 2] / S[:, 3]
                bad = int((~np.isfinite(rd)).sum())
                rd = rd[np.isfinite(rd)]
                ent["risk_difference_cluster_bootstrap_percentile95"] = [float(np.percentile(rd, 2.5)), float(np.percentile(rd, 97.5))]
                ent["bootstrap_undefined_resamples"] = bad
                ent["n_clusters"] = M.shape[0]
            r[tag] = ent
        mad = np.array([abs(lab[c]["R_AH"] - lab[c]["R_2"]) for c in cells], float)
        r["mean_abs_R_difference"] = {"under_20s": float(mad[fast & m].mean()) if (fast & m).any() else None,
                                      "at_or_over_20s": float(mad[~fast & m].mean()) if (~fast & m).any() else None}
        return {name: r}

    allm = np.ones(len(cells), bool)
    j2 = np.array([J_gem[c] >= 2 for c in cells])
    out.update(block(allm, "all_188_cells"))
    out.update(block(j2, "credited_cells_J_ge2_only"))
    return out


# ------------------------------------------------------------------ analyzer cross-check on the headline statistics
def analyzer_crosscheck(run: Run, lab: dict) -> dict:
    """Recompute three headline statistics with analyze_holdout's own cluster_bootstrap_stat and compare to fast_ci."""
    out = {}
    cells = [{"cell_id": r["cell_id"], "cluster_id": r["cluster"], "J": r["J"], "A": lab[r["cell_id"]]["S_AH"]} for r in run.recs]
    pi_an = ah.silent_over_credit_rate(cells, B=B, seed=SEED)
    ev = np.array([r["J"] >= 2 and lab[r["cell_id"]]["S_AH"] == 0 for r in run.recs], float)
    mine = fast_ci(cluster_sums([r["cluster"] for r in run.recs], [ev, np.ones(len(ev))]))
    out["pi_hat_AH_raw"] = {"analyzer": [pi_an["pi_hat"], pi_an["ci_lo"], pi_an["ci_hi"]], "fast_ci": [mine["est"], mine["lo"], mine["hi"]],
                            "max_abs_diff": max(abs(pi_an["pi_hat"] - mine["est"]), abs(pi_an["ci_lo"] - mine["lo"]), abs(pi_an["ci_hi"] - mine["hi"]))}
    # check-adjusted pi-hat through the analyzer: J replaced by J*
    cells_c = [dict(c, J=j_star(c["J"], bool(r["ok"]))) for c, r in zip(cells, run.recs)]
    pa = ah.silent_over_credit_rate(cells_c, B=B, seed=SEED)
    evc = np.array([r["J"] >= 2 and r["ok"] and lab[r["cell_id"]]["S_AH"] == 0 for r in run.recs], float)
    mc = fast_ci(cluster_sums([r["cluster"] for r in run.recs], [evc, np.ones(len(evc))]))
    out["pi_hat_AH_after_withdrawal"] = {"analyzer": [pa["pi_hat"], pa["ci_lo"], pa["ci_hi"]], "fast_ci": [mc["est"], mc["lo"], mc["hi"]],
                                         "max_abs_diff": max(abs(pa["pi_hat"] - mc["est"]), abs(pa["ci_lo"] - mc["lo"]), abs(pa["ci_hi"] - mc["hi"]))}
    # A->B on J
    byq: dict[str, dict[str, float]] = defaultdict(dict)
    for r in run.recs:
        byq[r["cq"]][r["variant"]] = r["J"]
    recs = [{"cluster_id": q, "d": v["B"] - v["A"]} for q, v in sorted(byq.items()) if "A" in v and "B" in v]
    bt = ah.cluster_bootstrap_stat(recs, ah._mean_d, None, "cluster_id", B, SEED)
    mine = contrast({r["cell_id"]: float(r["J"]) for r in run.recs})
    out["A_to_B_J"] = {"analyzer": [bt["estimate"], bt["ci_lo"], bt["ci_hi"]], "fast_ci": [mine["est"], mine["ci95"][0], mine["ci95"][1]],
                       "max_abs_diff": max(abs(bt["estimate"] - mine["est"]), abs(bt["ci_lo"] - mine["ci95"][0]), abs(bt["ci_hi"] - mine["ci95"][1]))}
    return out


def crosscheck_existing(runs_res: dict) -> dict:
    """The raw-J A->B contrasts of this script's judge-run loaders against two outputs the paper's own scripts already wrote."""
    out = {}
    r4 = json.loads(INPUTS["existing_output_r4"].read_text())["per_judge_question_set"]
    for run, key in (("luna_full", "luna full"), ("luna_limited60k", "luna limited (60k chars)"), ("luna_subgraph", "luna subgraph")):
        mine = runs_res[run]["strict"]["A_to_B"]["J"]
        ref = r4[key]
        out[f"{run}_vs_review6_reanalysis_r4"] = {"mine": [mine["est"], mine["ci95"][0], mine["ci95"][1]], "existing": [ref["est"], ref["lo"], ref["hi"]],
                                                   "max_abs_diff": max(abs(mine["est"] - ref["est"]), abs(mine["ci95"][0] - ref["lo"]), abs(mine["ci95"][1] - ref["hi"]))}
    rj = json.loads(INPUTS["existing_output_review6_judges"].read_text())["judges"]
    for jn in ("gptoss", "glm"):
        for rep in (1, 2, 3):
            mine = runs_res[f"{jn}_r{rep}"]["strict"]["A_to_B"]["J"]
            ref = rj[jn]["holdout_subgraph"]["A_to_B_per_repeat"][str(rep)]
            out[f"{jn}_r{rep}_vs_review6_judges"] = {"mine": [mine["est"], mine["ci95"][0], mine["ci95"][1]],
                                                     "existing": [ref["delta"], ref["ci_lo"], ref["ci_hi"]],
                                                     "max_abs_diff": max(abs(mine["est"] - ref["delta"]), abs(mine["ci95"][0] - ref["ci_lo"]), abs(mine["ci95"][1] - ref["ci_hi"]))}
    return out


# ------------------------------------------------------------------ self-test (pytest-collectable: pytest analyze.py)
def test_matcher_rule_cases():
    v = norm("IND a  b\n  c | d\te {x=1;}")
    assert verbatim("a b c", v) and verbatim("  a\n b   c ", v)             # whitespace runs collapse, ends stripped
    assert not verbatim("A b c", v)                                           # case sensitive
    assert not verbatim("", v) and not verbatim("   ", v) and not verbatim(None, v)   # empty or missing span fails
    assert not verbatim(["a b", "zzz"], v) and verbatim(["a b", "c | d"], v)  # a list needs every element
    assert not verbatim([], v) and not verbatim(["", "  "], v)                # no non-empty element fails
    assert verbatim(["a b", "", 5], v)                                        # empty and non-string elements are ignored
    assert not verbatim(5, v) and not verbatim({"x": 1}, v)
    assert verbatim("d e", v)                                                 # tab collapses
    assert not verbatim("a b ... x=1;", v)                                    # strict rule: an ellipsis breaks the match


def test_matcher_equals_natural_rule_on_random_cases():
    """The imported matcher equals an independent re-implementation of the natural-corpus rule."""
    def ref(e, vn):
        if isinstance(e, str):
            s = re.sub(r"\s+", " ", e or "").strip()
            return bool(s) and s in vn
        if isinstance(e, list):
            ps = [re.sub(r"\s+", " ", x or "").strip() for x in e if isinstance(x, str) and re.sub(r"\s+", " ", x or "").strip()]
            return bool(ps) and all(p in vn for p in ps)
        return False

    rnd_ = random.Random(1)
    words = ["IND", "OP", "http://x#a", "a", "b", "{k=v;}", "|", "::"]
    for _ in range(400):
        view = norm(" ".join(rnd_.choice(words) + rnd_.choice([" ", "  ", "\n", "\t"]) for _ in range(30)))
        toks = view.split(" ")
        i = rnd_.randrange(len(toks))
        span = (" " + rnd_.choice(["", "\n"])).join(toks[i:i + rnd_.randrange(1, 6)])
        for e in (span, span + " zz", [span, span], [span, "qq"], "", None, [], 7, span.upper()):
            assert verbatim(e, view) == ref(e, view)


def test_elision_tolerant_is_superset_and_withdrawal_rule():
    v = norm("IND http://x#building | building a http://x#Class,skos:Concept {skos:broader=http://x#location;} IND http://x#floor | floor")
    e = "IND http://x#building | building a ... {skos:broader=http://x#location;}"
    assert not verbatim(e, v) and verbatim_elided(e, v)
    assert not verbatim_elided("IND http://x#building | building a ... NOT PRESENT ANYWHERE", v)
    assert verbatim_elided("IND http://x#floor | floor", v) and not verbatim_elided("", v)
    assert j_star(3, True) == 3 and j_star(3, False) == 1 and j_star(2, False) == 1 and j_star(1, False) == 1 and j_star(0, False) == 0
    assert j_star(3, False, True) == 0 and j_star(1, False, True) == 1


def test_fast_ci_matches_analyzer():
    global B, _DRAWS
    saved = (B, _DRAWS)
    B, _DRAWS = 400, {}
    try:
        rng = np.random.default_rng(3)
        cl = [f"Q{i:02d}" for i in range(12) for _ in range(3)]
        ev = (rng.random(len(cl)) < 0.25).astype(float)
        cells = [{"cluster_id": c, "e": e} for c, e in zip(cl, ev)]
        an = ah.cluster_bootstrap_stat(cells, lambda s: float(np.mean([x["e"] for x in s])), None, "cluster_id", B, SEED)
        mine = fast_ci(cluster_sums(cl, [ev, np.ones(len(ev))]))
        assert abs(an["estimate"] - mine["est"]) < 1e-12
        assert abs(an["ci_lo"] - mine["lo"]) < 1e-12 and abs(an["ci_hi"] - mine["hi"]) < 1e-12
    finally:
        B, _DRAWS = saved


def selftest() -> None:
    for fn in (test_matcher_rule_cases, test_matcher_equals_natural_rule_on_random_cases,
               test_elision_tolerant_is_superset_and_withdrawal_rule, test_fast_ci_matches_analyzer):
        fn()
    print("self-test ok (4 tests)")


# ------------------------------------------------------------------ main
def git_head() -> str | None:
    try:
        return subprocess.check_output(["git", "-C", str(PAPER), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def main() -> int:
    selftest()
    if "--selftest" in sys.argv:
        return 0
    views = load_views()
    lab = load_labels()
    # cross-check: the v1 second-rater CSV carries the same S as the v3 per-cell file (S unchanged across sheets)
    with INPUTS["labels_second_rater_v1_csv"].open(encoding="utf-8", newline="") as f:
        v1 = {r["cell_id"]: int(r["A"]) for r in csv.DictReader(f)}
    s_same = sum(v1[c] == lab[c]["S_2"] for c in lab)
    runs = build_runs(views)
    run_by = {r.name: r for r in runs}
    gem = run_by["gemini_primary"]
    assert len(gem.recs) == 188 and len({r["cluster"] for r in gem.recs}) == 33
    assert all(lab[r["cell_id"]]["J_file"] == r["J"] for r in gem.recs), "J differs between cells.jsonl and the label files"
    assert Counter(r["variant"] for r in gem.recs) == {"A": 23, "B": 33, "C": 33, "D": 33, "E": 33, "F": 33}
    J_gem = {r["cell_id"]: r["J"] for r in gem.recs}

    results: dict = {
        "schema": "review9_verbatim/1",
        "status": "post hoc, exploratory, label-free check scored against evidence labels; no model call, no network, no server access",
        "repo_head_at_run": git_head(), "seed": SEED, "B": B, "interval": "question-cluster BCa 95% (analyzer's draws)",
        "matcher": {"source": "harness/review6_natural/analyze_natural.py::verbatim (imported)",
                    "rule": "whitespace runs collapse to one space and ends are stripped; case sensitive; plain substring test against the "
                            "whitespace-normalised view the judge received; a list needs every non-empty string element to match; empty or "
                            "non-string spans fail",
                    "credit": "J >= 2; withdrawal J* = J if J < 2 or span verbatim else min(J, 1)",
                    "sensitivities": {"full_withdrawal": "J* = 0 on a failing credit (A->B only)",
                                      "elision_tolerant": f"split at '...'/ellipsis, fragments >= {MIN_FRAGMENT} chars all verbatim, or strict pass"}},
        "inputs": {k: (str(v.relative_to(PAPER)) if v.exists() else str(v)) for k, v in INPUTS.items()},
        "input_sha256": {k: sha256_file(v) for k, v in INPUTS.items() if v.is_file()},
        "view_sha256": {v: views[v][0] for v in VARIANTS},
        "label_sources": {
            "AH": "first-author-revised AI-drafted labels (AH); unsealed per-cell file used by review6_reanalysis/common.py",
            "second_rater": "second rater v3 labels (S); same file as review6_reanalysis/common.py",
            "second_rater_S_equal_to_v1_csv_cells": f"{s_same}/188"},
        "primary_judge_emitted_spans": True,
        "primary_judge_note": "the registered rubric asks for {\"score\", \"evidence\": \"<verbatim span, or empty>\"}; every J>=1 cell of the primary judge "
                              "(gemini-3.6-flash) carries a non-empty evidence value, every J=0 cell an empty one",
        "population": "188 primary cells, 33 question clusters (A 23, B-F 33 each); controls excluded",
        "cluster_equals_cq": all(r["cluster"] == r["cq"] for r in gem.recs),
        "runs": {},
    }
    # paper's reference values reproduced from the same files (sanity)
    ref = {}
    cred = [r for r in gem.recs if r["J"] >= 2]
    for src, key in (("AH", "S_AH"), ("second_rater", "S_2")):
        ref[f"events_{src}"] = sum(lab[r["cell_id"]][key] == 0 for r in cred)
    assert ref["events_AH"] == 14 and ref["events_second_rater"] == 26, ref
    results["reproduced_reference_counts"] = {"events_J_ge2_S0_AH": ref["events_AH"], "events_J_ge2_S0_second_rater": ref["events_second_rater"],
                                              "paper": "14 on AH, 26 on the second rater (pi-hat 7.4% and 13.8%)"}

    for run in runs:
        strict = analyze_run(run, lab, verbatim)
        elided = analyze_run(run, lab, verbatim_elided)
        results["runs"][run.name] = {"description": run.desc, "view": run.view_note, "strict": strict, "elision_tolerant_sensitivity": elided,
                                     "failure_modes_strict": failure_modes(run)}
    results["crosscheck_J_contrasts_vs_existing_outputs"] = cx = crosscheck_existing(results["runs"])
    assert max(v["max_abs_diff"] for v in cx.values()) < 1e-3, cx   # existing outputs are stored at full float precision; rounding only
    # analyzer cross-check needs the strict flags on the primary run
    for r in gem.recs:
        r["ok"] = verbatim(r["evidence"], r["view_n"])
    cc = analyzer_crosscheck(gem, lab)
    results["analyzer_crosscheck_primary"] = cc
    assert max(v["max_abs_diff"] for v in cc.values()) < 1e-9, cc

    results["primary_failing_span_divergence_label_free"] = divergence_detail(gem)
    # label-free per-cell flags of the primary judge (no label)
    results["primary_cell_flags_label_free"] = [
        {"cell_id": r["cell_id"], "J": r["J"], "verbatim": bool(r["ok"])} for r in sorted(gem.recs, key=lambda r: r["cell_id"]) if r["J"] >= 1 and not r["ok"]]
    results["dwell_AH_vs_second_rater"] = dwell_analysis(lab, J_gem)

    out = HERE / "results.json"
    out.write_text(json.dumps(rnd(results), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    summarize(results)
    return 0


def summarize(res: dict) -> None:
    def ci(d, pct=False):
        if not d:
            return "n/a"
        s = 100 if pct else 1
        return f"{d['est']*s:.3f} [{d['ci95'][0]*s:.3f}, {d['ci95'][1]*s:.3f}]" if "ci95" in d else f"{d['est']*s:.3f}"
    print("\nrun | cells | credited | verbatim share | AH: events/recall/falseflag | pi raw -> after | 2nd: events/recall/falseflag | pi raw -> after")
    for name, rr in res["runs"].items():
        s = rr["strict"]
        la, lb = s["labels"]["AH"], s["labels"]["second_rater"]
        def rf(l):
            return (f"{l['events']}/{l['recall_events_failing']['k']}/{l['false_flag_supported_credited_failing']['k']}of{l['supported_credited']}"
                    f" | {ci(l['pi_hat_raw'], True)} -> {ci(l['pi_hat_after_withdrawal'], True)}")
        print(f"{name} | {s['n_cells']} | {s['credited_J_ge2']} | {s['credited_verbatim']}/{s['credited_J_ge2']} | {rf(la)} | {rf(lb)}")
    print("\nA->B (gemini_primary):")
    s = res["runs"]["gemini_primary"]["strict"]
    print(" J", ci(s["A_to_B"]["J"]), " J*", ci(s["A_to_B"]["Jstar_withdraw_to_min(J,1)"]), " J*0", ci(s["A_to_B"]["Jstar_zero_sensitivity"]))
    for src in ("AH", "second_rater"):
        print(f" {src}: L1*", ci(s["labels"][src]["A_to_B"]["L1star"]), " L1*+check", ci(s["labels"][src]["A_to_B"]["L1star_after_check"]))


if __name__ == "__main__":
    raise SystemExit(main())
