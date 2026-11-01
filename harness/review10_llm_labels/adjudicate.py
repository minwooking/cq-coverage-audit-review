#!/usr/bin/env python3
"""Addendum 31 (review10_llm_labels): objective adjudication of the disagreements between the persona-ensemble LLM labels
(addendum 30) and the two human evidence labels, by the frozen bank's grounding anchors and expected-answer terms.

AI-generated; a person must review and test it before reuse.  Exploratory and post hoc.  The rules are those of
ADJUDICATION_PLAN.md (commit 88e5cbc) and are implemented here without change.  No model call, no server access, no new label.

Reads   bank/cq_bank_brick_v1.csv (columns question, grounding, expected_answer; never sent to a model), the cell manifest of
        addendum 28 (view the model saw, full rendering the humans saw), raw/<model>_t1.jsonl(.gz) (slot labels and quoted spans),
        the two de-identified human analysis files (via review6_reanalysis/common.load_188), the second rater's de-identified
        span file (annotation/second_pass_2026-10-13/v3/labels_for_analysis_v3.csv), results.json (reliability numbers).
Writes  results_adjudication.json (aggregates only: no per-cell human label, no per-cell human-LLM disagreement).
Never opens site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, labels_v3.csv, .env or sealed files.

Usage:  python3 adjudicate.py             (self-test, then the analysis)
        python3 adjudicate.py --selftest  (self-test only; synthetic data, no human label, no model output)
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
for p in (HERE, HARNESS, HARNESS / "review6_natural", HARNESS / "review6_raters", HARNESS / "review6_reanalysis",
          HARNESS / "llm_rater_luna_2026-10-15"):
    sys.path.insert(0, str(p))

import analyze as AN  # noqa: E402  (addendum 30: Raw, consistent, majority, bca, csum, kappa_flat, alpha_cols, ...)
import grounding_check as GC  # noqa: E402  (addendum 27: local_anchors, content_terms, forms_of, form_regex)
import common as RC  # noqa: E402  (load_188, draw_indices)
import run_holdout as rh  # noqa: E402

SEED, B = AN.SEED, AN.B
assert (SEED, B) == (20260913, 10_000)
BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"
SPANS_R2 = ACCESS / "annotation" / "second_pass_2026-10-13" / "v3" / "labels_for_analysis_v3.csv"
MIN_GROUP = 5            # PLAN 31.3: fewer cells -> counts only, no interval
MIN_D = 10               # PLAN 31.8: fewer disagreement cells -> not evaluable
ANSWER_FRACTION = 0.5    # PLAN 31.4 (the L2 threshold of the grounding check, not varied)
HUMANS = {"AH": "S_AH", "R2": "S_2"}
PRIMARY_RULE_THR = AN.THR_CONSISTENT      # 23 of 25
GROUPS = ("D", "D10", "D01", "Ag", "Ag11", "Ag00")


# ---------------------------------------------------------------- normalization and the term test (PLAN 31.4)
def norm_lc(s) -> str:
    """analyze_natural.norm (whitespace collapse + strip), then lower case (grounding_check's text_lc)."""
    return re.sub(r"\s+", " ", s or "").strip().lower()


class Crit:
    """Anchors and answer terms of one bank row; the term test of one text unit."""

    def __init__(self, row: dict):
        self.cq_id = row["cq_id"]
        self.anchors = GC.local_anchors(row["grounding"])
        exclude = {w for a in self.anchors for f in GC.forms_of(a) for w in f.split(" ")}
        self.terms = GC.content_terms(row["expected_answer"], exclude)
        self.anchor_res = [[GC.form_regex(f) for f in GC.forms_of(a)] for a in self.anchors]
        self.term_res = [re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?:s|es)?(?![a-z0-9])") for t in self.terms]

    def unit(self, t_lc: str) -> tuple[bool, float]:
        """-> (every anchor present, fraction of the answer terms present).  t_lc is already normalised and lower case."""
        a = all(any(r.search(t_lc) for r in rs) for rs in self.anchor_res)
        if not a or not self.term_res:
            return a, 0.0
        return a, sum(1 for r in self.term_res if r.search(t_lc)) / len(self.term_res)

    def passes(self, t_lc: str) -> tuple[bool, float]:
        a, f = self.unit(t_lc)
        return bool(a and f >= ANSWER_FRACTION), (f if a else 0.0)

    def best_line(self, lines_lc: list[str]) -> tuple[bool, float]:
        """Rendering-level test: one line must pass.  -> (any line passes, best fraction among lines holding every anchor)."""
        best = 0.0
        ok = False
        for ln in lines_lc:
            p, f = self.passes(ln)
            ok = ok or p
            best = max(best, f)
        return ok, best

    def span_whole(self, span: str) -> tuple[bool, float]:
        return self.passes(norm_lc(span))

    def span_any_line(self, span: str) -> tuple[bool, float]:
        return self.best_line([norm_lc(x) for x in span.splitlines() if x.strip()])


def load_crits() -> dict[str, Crit]:
    assert hashlib.sha256(BANK.read_bytes()).hexdigest() == rh.FROZEN_BANK_SHA256, "bank digest mismatch"
    with BANK.open(encoding="utf-8", newline="") as fh:
        return {r["cq_id"]: Crit(r) for r in csv.DictReader(fh)}


# ---------------------------------------------------------------- intervals (PLAN 31.6: BCa, percentile fallback marked)
def pct_ci(M: np.ndarray, f):
    n = M.shape[0]
    tot = M.sum(0)
    theta = float(f(tot[None, :])[0])
    if not math.isfinite(theta) or n < 2:
        return None
    idx = RC.draw_indices(n, B, SEED)
    boot = f(M[idx].sum(1))
    boot = boot[np.isfinite(boot)]
    if len(boot) < 100:
        return None
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"est": theta, "lo": float(lo), "hi": float(hi), "n_clusters": n, "note": "percentile (BCa undefined)"}


def interval(cl, cols: np.ndarray, f) -> dict:
    M = AN.csum(cl, cols)
    try:
        r = AN.bca(M, f)
    except Exception as e:  # BCa can fail on a degenerate resampling distribution
        r = {"est": None, "lo": None, "hi": None, "note": f"bca error: {type(e).__name__}"}
    lo, hi = r.get("lo"), r.get("hi")
    if r.get("est") is not None and (lo is None or hi is None or not (math.isfinite(lo) and math.isfinite(hi))):
        alt = pct_ci(M, f)
        if alt is not None:
            r = alt
    return AN.ci_out(r)


def share_of(cl, flag: np.ndarray, defined: np.ndarray) -> dict:
    """Share of `flag` among the `defined` cells.  n < MIN_GROUP -> counts only."""
    nd = int(defined.sum())
    k = int((flag.astype(bool) & defined.astype(bool)).sum())
    out = {"n": nd, "k": k}
    if nd == 0:
        out["share"] = None
        return out
    out["share"] = AN.rnd(k / nd)
    if nd >= MIN_GROUP:
        cols = np.stack([(flag.astype(float) * defined), defined.astype(float)], 1)
        out["ci"] = interval(cl, cols, lambda s: s[:, 0] / s[:, 1])
    return out


def mean_of(x: np.ndarray, defined: np.ndarray):
    d = defined.astype(bool)
    return AN.rnd(float(np.mean(x[d]))) if d.any() else None


# ---------------------------------------------------------------- per-cell verdict and group split (PLAN 31.3, 31.5)
def split_groups(L: np.ndarray, S: np.ndarray) -> dict[str, np.ndarray]:
    L = np.asarray(L, float)
    S = np.asarray(S, float)
    D10 = (S == 1) & (L == 0)
    D01 = (S == 0) & (L == 1)
    Ag11 = (S == 1) & (L == 1)
    Ag00 = (S == 0) & (L == 0)
    return {"D": D10 | D01, "D10": D10, "D01": D01, "Ag": Ag11 | Ag00, "Ag11": Ag11, "Ag00": Ag00}


def verdict_human_right(L, S, T_H, T_llm) -> np.ndarray:
    """PLAN 31.5: on D10 the human credits -> human right iff T_H; on D01 the model credits -> human right iff NOT T_llm.
    NaN outside D.  T_H, T_llm are 0/1 floats (T_llm NaN where undefined)."""
    L = np.asarray(L, float)
    S = np.asarray(S, float)
    out = np.full(len(L), np.nan)
    d10 = (S == 1) & (L == 0)
    d01 = (S == 0) & (L == 1)
    out[d10] = np.asarray(T_H, float)[d10]
    out[d01] = 1.0 - np.asarray(T_llm, float)[d01]
    return out


def modal_span(spans_in_slot_order: list[str]) -> str | None:
    """Most frequent whitespace-normalised span; ties -> the first in slot order."""
    cnt: dict[str, int] = {}
    first: dict[str, int] = {}
    for i, s in enumerate(spans_in_slot_order):
        k = AN.collapse(s or "")
        if not k:
            continue
        cnt[k] = cnt.get(k, 0) + 1
        first.setdefault(k, i)
    if not cnt:
        return None
    return sorted(cnt, key=lambda k: (-cnt[k], first[k]))[0]


def slot_spans(recs: list[dict], cell_ids: list[str]) -> dict[str, list[str]]:
    """Spans of the S_final = 1 slots per cell, in slot order (domain..generalist x seed 1..5); first record per slot, as Raw."""
    pos = {c: i for i, c in enumerate(cell_ids)}
    slot_pos = {s: k for k, s in enumerate(AN.SLOTS)}
    seen = set()
    got: dict[str, dict[int, str]] = {}
    for r in recs:
        cid = r.get("cell_id")
        if cid not in pos or r.get("status") == "context_skip":
            continue
        key = (r.get("persona"), r.get("seed"))
        if key not in slot_pos or (cid, key) in seen or r.get("status") not in ("ok", "invalid"):
            continue
        seen.add((cid, key))
        if r["status"] == "ok" and int(r["S_final"]) == 1:
            got.setdefault(cid, {})[slot_pos[key]] = r.get("span") or ""
    return {cid: [d[k] for k in sorted(d)] for cid, d in got.items()}


# ---------------------------------------------------------------- self-test (synthetic data; no human label, no model output)
def run_selftests(check) -> int:
    fails = 0

    def ck(cond, msg):
        nonlocal fails
        check(bool(cond), msg)
        fails += 0 if cond else 1

    row = {"cq_id": "X1", "grounding": "skos:definition brick:Sensor",
           "expected_answer": "An input point representing the value of a device designed to detect and measure a variable; subclass of brick:Point."}
    cr = Crit(row)
    ck(cr.anchors == ["Sensor"], f"anchors of a definition grounding: {cr.anchors}")
    ck("sensor" not in cr.terms and "point" in cr.terms and "measure" in cr.terms, f"answer terms exclude the anchor word: {cr.terms}")
    good = norm_lc("brick sensor a Class  { An input point representing the value of a device designed to detect and measure a variable }")
    bad_terms = norm_lc("brick sensor a Class skos:Concept")
    no_anchor = norm_lc("An input point representing the value of a device designed to detect and measure a variable")
    ck(cr.passes(good)[0], "unit with anchor and the answer terms passes")
    ck(not cr.passes(bad_terms)[0], "anchor without the answer terms fails")
    ck(not cr.passes(no_anchor)[0], "answer terms without the anchor fail")
    ck(cr.passes(no_anchor)[1] == 0.0 and cr.passes(good)[1] > 0.5, "best fraction is 0 without the anchor")
    sensors = norm_lc("brick_sensors a class")
    ck(cr.unit(sensors)[0], "plural suffix and underscore separators match the anchor")
    ck(not cr.unit(norm_lc("sensorial"))[0], "whole-word boundary: 'sensorial' is not 'sensor'")
    ok, best = cr.best_line([bad_terms, good, no_anchor])
    ck(ok and best > 0.5, "rendering-level test: one passing line suffices")
    ck(not cr.best_line([bad_terms, no_anchor])[0], "rendering-level test: terms and anchor on different lines fail")
    span = "brick sensor a Class\n{ An input point representing the value of a device designed to detect and measure a variable }"
    ck(cr.span_whole(span)[0], "a span passes as a whole")
    ck(cr.span_any_line(span)[0] is False, "single-line variant: anchor and terms on different lines fail")
    ck(norm_lc("  A\n\tB  ") == "a b", "normalization: whitespace collapse + lower case")
    # groups and verdict
    L = np.array([0, 0, 1, 1, 0, 1, 0])
    S = np.array([1, 0, 0, 1, 1, 1, 0])
    g = split_groups(L, S)
    ck(g["D10"].tolist() == [True, False, False, False, True, False, False], "D10 = human credits, model does not")
    ck(g["D01"].tolist() == [False, False, True, False, False, False, False], "D01 = model credits, human does not")
    ck(g["Ag11"].sum() == 2 and g["Ag00"].sum() == 2 and (g["D"] | g["Ag"]).all() and not (g["D"] & g["Ag"]).any(), "groups partition the cells")
    TH = np.array([1, 0, 0, 0, 0, 1, 0], float)
    Tl = np.array([np.nan, np.nan, 0.0, 1, np.nan, 1, np.nan])
    v = verdict_human_right(L, S, TH, Tl)
    ck(v[0] == 1 and v[4] == 0, "D10: human right iff its text carries the terms")
    ck(v[2] == 1.0, "D01: model credit not confirmed -> human right")
    v2 = verdict_human_right(L, S, TH, np.array([np.nan, np.nan, 1.0, 1, np.nan, 1, np.nan]))
    ck(v2[2] == 0.0, "D01: model credit confirmed -> model right")
    ck(np.isnan(v[[1, 3, 5, 6]]).all(), "verdict is undefined outside D")
    ck(modal_span(["a b", "a  b", "c", "c", ""]) == "a b", "modal span: whitespace-normalised, ties -> first in slot order")
    ck(modal_span(["", ""]) is None, "modal span: none when there is no span")
    recs = [{"cell_id": "c1", "persona": "domain", "seed": 1, "status": "ok", "S_final": 1, "span": "x y"},
            {"cell_id": "c1", "persona": "domain", "seed": 1, "status": "ok", "S_final": 0, "span": "dup ignored"},
            {"cell_id": "c1", "persona": "domain", "seed": 2, "status": "ok", "S_final": 0, "span": "no"},
            {"cell_id": "c1", "persona": "ontology", "seed": 1, "status": "ok", "S_final": 1, "span": "z"}]
    ck(slot_spans(recs, ["c1"]) == {"c1": ["x y", "z"]}, "slot spans: first record per slot, label-1 slots only, slot order")
    # share and the interval helper against a direct bootstrap on a toy example
    cl = np.array(list("aabbccddeeff"))
    flag = np.array([1, 0, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0])
    defined = np.ones(12)
    sh = share_of(cl, flag, defined)
    ck(sh["k"] == 7 and sh["n"] == 12 and abs(sh["share"] - 7 / 12) < 1e-3, "share counts")
    ck(sh["ci"]["lo"] is not None and sh["ci"]["lo"] <= 7 / 12 <= sh["ci"]["hi"], "interval contains the estimate")
    rng = np.random.default_rng(1)
    boots = []
    ids = sorted(set(cl))
    for _ in range(4000):
        pick = rng.integers(0, len(ids), len(ids))
        num = den = 0
        for j in pick:
            m = cl == ids[j]
            num += flag[m].sum()
            den += m.sum()
        boots.append(num / den)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    ck(abs(sh["ci"]["lo"] - lo) < 0.12 and abs(sh["ci"]["hi"] - hi) < 0.12, "interval close to a brute-force cluster bootstrap")
    small = share_of(cl[:3], flag[:3], np.ones(3))
    ck("ci" not in small and small["n"] == 3, "fewer than 5 cells -> counts only")
    allone = share_of(cl, np.ones(12), defined)
    ck(allone["share"] == 1.0 and "ci" in allone and allone["ci"]["lo"] is not None, "degenerate share (all 1) still gets an interval")
    # difference of two shares in one resample
    cols = np.stack([flag * 1.0, np.ones(12), (1 - flag) * 1.0, np.ones(12)], 1)
    d = interval(cl, cols, lambda s: s[:, 0] / s[:, 1] - s[:, 2] / s[:, 3])
    ck(abs(d["est"] - (7 / 12 - 5 / 12)) < 1e-3, "paired-difference estimate")
    return fails


# ---------------------------------------------------------------- main analysis
def read_span_file(d_labels: dict[str, float]) -> dict[str, str]:
    """R2 spans from the de-identified analysis file; checks against the per-cell label file (PLAN 31.2)."""
    with SPANS_R2.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == ["cell_id", "A", "rater_L1", "evidence_span_verbatim"], "unexpected columns in the span file"
    assert len(rows) == 188
    spans = {}
    for r in rows:
        s = r["evidence_span_verbatim"]
        a = int(r["A"])
        assert a == int(d_labels[r["cell_id"]]), f"label mismatch between span file and v3 per-cell file: {r['cell_id']}"
        assert (a == 1) == bool(s.strip()), f"span presence does not follow the label: {r['cell_id']}"
        spans[r["cell_id"]] = s
    return spans


def reliability_block(res_old: dict, cells, raws, cl_all, lab_cons, lab_maj, ev):
    out = {"source": "results.json of addendum 30 (copied) and raw files (LLM-LLM kappa, computed here)"}
    hh = res_old["meta"]["human_human_all_188"]
    out["human_human"] = {"all_188": {"n": hh["n_cells"], "kappa": hh["kappa"], "agreement": hh["agreement"]}, "per_model_evaluated_cells": {}, "per_model_consistent_cells": {}}
    out["per_model"] = {}
    for m in AN.MODELS:
        blk = res_old["models"][m]["S_final"]
        hhe = blk["human_human_all_evaluated"]
        out["human_human"]["per_model_evaluated_cells"][m] = {"n": hhe["n_cells"], "kappa": hhe["kappa"]}
        ag = blk["R25"].get("agreement", {})
        out["human_human"]["per_model_consistent_cells"][m] = {"n": ag.get("n_cells"), "kappa": ag.get("human_human_same_cells", {}).get("kappa")}
        out["per_model"][m] = {
            "n_evaluated": blk["R25"]["n_evaluated"], "n_consistent": blk["R25"]["n_consistent"], "coverage": blk["R25"]["coverage"],
            "S1_share_of_consistent_labels": blk["R25"]["S1_share_of_consistent_labels"],
            "kappa_with_AH_on_consistent": ag.get("vs_human", {}).get("AH", {}).get("kappa"),
            "kappa_with_R2_on_consistent": ag.get("vs_human", {}).get("R2", {}).get("kappa"),
            "pi_hat_LLM_on_consistent": ag.get("pi_hat", {}).get("LLM"),
            "alpha_all_25_slots": blk["alpha_all_25_slots"], "alpha_seeds_per_persona": blk["alpha_seeds_per_persona"],
            "alpha_between_persona_labels": blk["alpha_between_persona_labels"]}
        # cross-check one alpha against the raw file
        a = AN.alpha_from(AN.csum(cl_all[ev[m]], AN.alpha_cols(raws[m].S_final[ev[m]])).sum(0)[None, :])[0]
        assert abs(a - blk["alpha_all_25_slots"]["est"]) < 1e-3, f"alpha recomputation differs for {m}"
    pairs = [("glm", "gptoss"), ("glm", "qwen"), ("gptoss", "qwen")]
    out["llm_llm_kappa"] = {}
    for a, b in pairs:
        both_c = ~np.isnan(lab_cons[a]) & ~np.isnan(lab_cons[b]) & ev[a] & ev[b]
        both_m = ~np.isnan(lab_maj[a]) & ~np.isnan(lab_maj[b]) & ev[a] & ev[b]
        blk = {}
        for name, sel, la, lb in (("consistent_labels", both_c, lab_cons[a], lab_cons[b]), ("unfiltered_majority_of_25", both_m, lab_maj[a], lab_maj[b])):
            n = int(sel.sum())
            e = {"n_cells": n}
            if n >= 2:
                e["n_clusters"] = len(set(map(str, cl_all[sel])))
                e["kappa"] = AN.kappa_ci(cl_all[sel], la[sel], lb[sel])
                e["agreement"] = AN.agree_ci(cl_all[sel], la[sel], lb[sel])
                e["S1_share_first"] = AN.rnd(float(np.mean(la[sel] == 1)))
                e["S1_share_second"] = AN.rnd(float(np.mean(lb[sel] == 1)))
            blk[name] = e
        out["llm_llm_kappa"][f"{a}|{b}"] = blk
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    def check(cond, msg):
        print(("ok   " if cond else "FAIL ") + msg)

    nfail = run_selftests(check)
    if nfail:
        print(f"{nfail} self-test(s) FAILED")
        return 1
    if "--selftest" in argv:
        print("self-test OK")
        return 0

    crits = load_crits()
    man = json.loads(AN.MANIFEST6.read_text(encoding="utf-8"))
    cells = sorted(man["cells"], key=lambda c: c["cell_id"])
    ids = [c["cell_id"] for c in cells]
    cl_all = np.array([c["cluster_id"] for c in cells])
    variants = np.array([c["variant"] for c in cells])
    res_old = json.loads((HERE / "results.json").read_text(encoding="utf-8"))

    # human labels: de-identified analysis files only (as addendum 30)
    d = RC.load_188().set_index("cell_id").loc[ids].reset_index()
    hum = {"AH": d["S_AH"].to_numpy(float), "R2": d["S_2"].to_numpy(float)}
    spans_r2 = read_span_file(dict(zip(d["cell_id"], d["S_2"])))

    # texts: full renderings (what the humans saw) and the views the models saw, as line lists (normalised, lower case)
    line_cache: dict[str, list[str]] = {}

    def lines_of(path: str) -> list[str]:
        if path not in line_cache:
            line_cache[path] = [norm_lc(x) for x in (ACCESS / path).read_text(encoding="utf-8").splitlines() if x.strip()]
        return line_cache[path]

    T_full = np.zeros(len(cells)); F_full = np.zeros(len(cells))
    T_view = np.zeros(len(cells)); F_view = np.zeros(len(cells))
    memo: dict[tuple[str, str], tuple[bool, float]] = {}
    for i, c in enumerate(cells):
        cr = crits[c["cq_id"]]
        for path, T, F in ((c["full_path"], T_full, F_full), (c["view_path"], T_view, F_view)):
            k = (path, c["cq_id"])
            if k not in memo:
                memo[k] = cr.best_line(lines_of(path))
            T[i], F[i] = memo[k]
    T_span = np.full(len(cells), np.nan); T_span_line = np.full(len(cells), np.nan); F_span = np.full(len(cells), np.nan)
    for i, c in enumerate(cells):
        s = spans_r2[c["cell_id"]]
        if s.strip():
            cr = crits[c["cq_id"]]
            T_span[i], F_span[i] = cr.span_whole(s)
            T_span_line[i] = cr.span_any_line(s)[0]

    # LLM labels, consistent cells, modal spans
    raws, ev, lab_cons, lab_maj, T_llm, T_llm_line, F_llm = {}, {}, {}, {}, {}, {}, {}
    cache: dict = {}
    vt = AN.make_view_text(cache)
    for m in AN.MODELS:
        p = AN.raw_file(AN.RAW, f"{m}_t1")
        recs = AN.jsonl(p)
        raw = AN.Raw(cells, recs, vt)
        assert raw.recheck_mismatch == 0
        raws[m] = raw
        ev[m] = raw.evaluated
        ok, lab = AN.consistent(raw.S_final, PRIMARY_RULE_THR)
        lab_cons[m] = np.where(raw.evaluated & ok, lab, np.nan)
        lab_maj[m] = np.where(raw.evaluated, AN.majority(raw.S_final), np.nan)
        assert int((~np.isnan(lab_cons[m])).sum()) == res_old["models"][m]["S_final"]["R25"]["n_consistent"], f"consistent count of {m} differs from results.json"
        sp = slot_spans(recs, ids)
        tl = np.full(len(cells), np.nan); tll = np.full(len(cells), np.nan); fl = np.full(len(cells), np.nan)
        for i, c in enumerate(cells):
            if lab_cons[m][i] == 1:
                ms = modal_span(sp.get(c["cell_id"], []))
                assert ms is not None, f"consistent label 1 without a span: {m} {c['cell_id']}"
                cr = crits[c["cq_id"]]
                tl[i], fl[i] = cr.span_whole(ms)
                tll[i] = cr.span_any_line(ms)[0]
        T_llm[m], T_llm_line[m], F_llm[m] = tl, tll, fl

    out: dict = {"meta": {"plan": "ADJUDICATION_PLAN.md (addendum 31)", "plan_commit": "88e5cbc", "B": B, "seed": SEED,
                          "answer_fraction_threshold": ANSWER_FRACTION, "consistency_threshold": PRIMARY_RULE_THR,
                          "n_cells": len(cells), "n_clusters": len(set(cl_all.tolist())),
                          "sha256": {"plan": AN.sha256_file(HERE / "ADJUDICATION_PLAN.md"), "bank": rh.FROZEN_BANK_SHA256,
                                     "span_file_R2": AN.sha256_file(SPANS_R2), "results_json_addendum30": AN.sha256_file(HERE / "results.json"),
                                     "cells_manifest": AN.sha256_file(AN.MANIFEST6)}},
                 "criterion_sanity": {"n_questions": len(crits), "n_questions_without_anchor": sum(1 for c in crits.values() if not c.anchors),
                                      "n_questions_without_answer_terms": sum(1 for c in crits.values() if not c.terms),
                                      "mean_answer_terms": AN.rnd(float(np.mean([len(c.terms) for c in crits.values()])))},
                 "texts_all_188_cells": {"T_full_share": AN.rnd(float(T_full.mean())), "T_view_share": AN.rnd(float(T_view.mean())),
                                         "T_span_R2_share_of_label1_cells": AN.rnd(float(np.nanmean(T_span))), "n_R2_spans": int((~np.isnan(T_span)).sum()),
                                         "T_full_by_variant": {v: AN.rnd(float(T_full[variants == v].mean())) for v in "ABCDEF"},
                                         "T_view_by_variant": {v: AN.rnd(float(T_view[variants == v].mean())) for v in "ABCDEF"}},
                 "pairs": {}, "reading": {}}
    for m in AN.MODELS:
        cons = ~np.isnan(lab_cons[m])
        for h in HUMANS:
            S_h = hum[h]
            L = lab_cons[m]
            idx = np.where(cons)[0]
            Lc, Sc, cl = L[idx], S_h[idx], cl_all[idx]
            # primary human-side measure: the R2 span where defined, else the full rendering (PLAN 31.5)
            if h == "R2":
                has_span = ~np.isnan(T_span[idx])
                TH = np.where(has_span, T_span[idx], T_full[idx])
                FH = np.where(has_span, F_span[idx], F_full[idx])
                TH_line = np.where(has_span, T_span_line[idx], T_full[idx])
            else:
                has_span = np.zeros(len(idx), bool)
                TH, FH, TH_line = T_full[idx], F_full[idx], T_full[idx]
            Tll = T_llm[m][idx]
            Tll_line = T_llm_line[m][idx]
            g = split_groups(Lc, Sc)
            blk = {"n_consistent": int(len(idx)), "n_clusters": len(set(cl.tolist())),
                   "counts": {k: int(v.sum()) for k, v in g.items()},
                   "human_span_available": "R2: quoted span for label-1 cells (non-restricted analysis file); AH: none, rendering-level fallback" if h == "R2" else "none in any non-restricted file; rendering-level fallback",
                   "groups": {}}
            for name, msk in g.items():
                cg = cl[msk]
                e = {"n": int(msk.sum())}
                if msk.sum() == 0:
                    blk["groups"][name] = e
                    continue
                e["T_H"] = share_of(cg, TH[msk], np.ones(int(msk.sum())))
                e["T_full"] = share_of(cg, T_full[idx][msk], np.ones(int(msk.sum())))
                e["T_view"] = share_of(cg, T_view[idx][msk], np.ones(int(msk.sum())))
                if h == "R2":
                    dsp = (~np.isnan(T_span[idx]))[msk]
                    e["T_span"] = share_of(cg, np.nan_to_num(T_span[idx][msk]), dsp.astype(float))
                dl = (~np.isnan(Tll))[msk]
                e["T_llm"] = share_of(cg, np.nan_to_num(Tll[msk]), dl.astype(float))
                e["best_fraction_H_mean"] = mean_of(FH[msk], np.ones(int(msk.sum())))
                blk["groups"][name] = e
            # headline pair: T_H on D vs Ag, paired difference
            if g["D"].sum() >= 1 and g["Ag"].sum() >= 1:
                cols = np.stack([TH * g["D"], g["D"].astype(float), TH * g["Ag"], g["Ag"].astype(float)], 1)
                blk["headline_T_H"] = {"share_D": blk["groups"]["D"]["T_H"], "share_Ag": blk["groups"]["Ag"]["T_H"],
                                       "Ag_minus_D": interval(cl, cols, lambda s: s[:, 2] / s[:, 3] - s[:, 0] / s[:, 1]) if g["D"].sum() >= MIN_GROUP and g["Ag"].sum() >= MIN_GROUP else {"note": "group below 5 cells"}}
            # per-cell verdict on D
            hr = verdict_human_right(Lc, Sc, TH, Tll)
            hr_line = verdict_human_right(Lc, Sc, TH_line, Tll_line)
            nD = int(g["D"].sum())
            ver = {"n_D": nD}
            if nD:
                cgD = cl[g["D"]]
                ver["human_right"] = share_of(cgD, hr[g["D"]], np.ones(nD))
                ver["model_right_count"] = int(nD - np.nansum(hr[g["D"]]))
                ver["human_right_single_line_variant"] = share_of(cgD, hr_line[g["D"]], np.ones(nD))
                for dn in ("D10", "D01"):
                    mk = g[dn]
                    if mk.sum():
                        ver[f"human_right_{dn}"] = share_of(cl[mk], hr[mk], np.ones(int(mk.sum())))
                d10 = g["D10"]
                if d10.sum():
                    ver["D10_T_full_and_not_T_view"] = share_of(cl[d10], ((T_full[idx] == 1) & (T_view[idx] == 0))[d10], np.ones(int(d10.sum())))
                    ver["D10_neither_T_full_nor_T_view"] = share_of(cl[d10], ((T_full[idx] == 0) & (T_view[idx] == 0))[d10], np.ones(int(d10.sum())))
            blk["verdict_on_D"] = ver
            out["pairs"][f"{m}|{h}"] = blk
            # reading rule (PLAN 31.8)
            if nD < MIN_D:
                reading = "not evaluable (fewer than 10 disagreement cells)"
            else:
                ci = ver["human_right"].get("ci", {})
                lo, hi = ci.get("lo"), ci.get("hi")
                if lo is not None and lo > 0.5:
                    reading = "human side"
                elif hi is not None and hi < 0.5:
                    reading = "model side"
                else:
                    reading = "not separated"
            out["reading"][f"{m}|{h}"] = {"n_D": nD, "human_right": ver.get("human_right", {}).get("share"), "interval": ver.get("human_right", {}).get("ci"), "reading": reading}
    out["reading_summary"] = {k: sum(1 for v in out["reading"].values() if v["reading"] == k)
                              for k in ("human side", "model side", "not separated", "not evaluable (fewer than 10 disagreement cells)")}
    out["reliability"] = reliability_block(res_old, cells, raws, cl_all, lab_cons, lab_maj, ev)
    (HERE / "results_adjudication.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"reading": out["reading"], "summary": out["reading_summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
