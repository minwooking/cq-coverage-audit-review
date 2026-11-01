"""Post-washout (G2, G3-W) and second-annotation statistics: PREREG.md sec.12.3-12.4 and sec.13.1.

Implements the post-washout and second-annotator statistics as registered in PREREG.md sec.12.3 ("G2
computation", DN-4b to DN-7), sec.12.4 (i)-(iv) and sec.13.1 (items 5-7, 9, 10 and 13):

  washout   sec.12.3  G2 rule, DN-4b, DN-6, DN-7 (G3-W), the DN-5 dwell check and washout gap
  second    sec.12.4  DN-10 and the 48-cell report (descriptive, never a gate)

``analyze_holdout.py`` is the registered analyzer and is NOT modified: this module imports its
helpers (``cluster_bootstrap_stat`` with its BCa interval and mid-rank z0, ``silent_over_credit*``,
``clopper_pearson_upper``, ``load_label_csv``, ``load_label_audit``, ``load_cells``, its output-path
guard) so every interval comes from the same resampling code.  Nothing here reads a real label unless
the operator points the CLI at one; the washout labels do not exist yet.  The code is exercised only
on synthetic fixtures (``test_analyze_washout.py``).

``washout`` compares two passes of the SAME rater: the AH pass (LLM-assisted, AI-drafted and
author-revised labels) and the washout pass (no AI draft shown).  That is "same-rater agreement
between the AH pass and the washout pass" (DN-6).  ``second`` compares a second, non-author annotator
with the AH labels.  The label-source strings written to every output are the constants LABEL_SOURCE_*,
and the text of every output is scanned before it is written (see GUARDS).  Every output is stamped
exploratory (PREREG sec.12.2 (7), sec.13.1 (13)), in the output and in its provenance block.

----------------------------------------------------------------------------
COMMAND LINE
----------------------------------------------------------------------------
  analyze_washout.py washout --design D --ah-labels AH --washout-labels W --seed 20260913
        --out OUT.json [--out-cells CELLS.json] [--audit W.audit.jsonl]
        [--session-log W.session_log.txt] [--exclude-controls LIST] [--label-source human]
        [--ah-last-save ISO] [--allow-design-deviation] [--expect-sha256 NAME=HEX ...] [--overwrite]
  analyze_washout.py second  --cells CELLS.jsonl --ah-labels AH --second-labels S
        --sample-list LIST --seed 20260913 --out OUT.json [--out-cells CELLS.json]
        [--id-map MAP] [--audit S.audit.jsonl] [--session-log S.session_log.txt]
        [--label-source human] [--allow-unregistered-sample] [--washout-locked]
        [--expect-sha256 NAME=HEX ...] [--overwrite]

B = 10,000 resamples (the registered value; no flag), BCa with the mid-rank z0, the seed is required
and never defaulted (a seed other than 20260913 is warned about and stamped).

----------------------------------------------------------------------------
INPUT SCHEMAS
----------------------------------------------------------------------------
Every input is read-only.  A "table" is a CSV with a header row (UTF-8, a BOM is tolerated) or a
``.json`` file holding a list of objects (or an object with a ``rows`` list).

``--design``  (washout; the SEALED build file that maps washout ids to the AH pass) a table, one row
    per cell shown in the washout.  Columns read, and only these:
      cell_id          the opaque id the rater saw (= ``cell_id`` of --washout-labels)
      source_cell_id   the id of the same cell in the AH sheet (= ``cell_id`` of --ah-labels); for a
                       control row, the control's AH-sheet id
      cell_kind        primary | ablated_control | preserved_control   (never blank)
      stratum          primary rows only: proportional | enriched
      inclusion_prob   primary rows only: the cell's inclusion probability pi in (0, 1] in the 72-cell
                       sample (4 decimals; DN-4a, sec.13.1 (5): a fixed property of the cell, pi = 0 is
                       an error)
      excluded_reason  optional, controls only: non-empty = the control was NOT presented (DN-7: the
                       rebuilt view's sha256 differs from ``artifact_digest``); the row is kept in the
                       design, counted by reason, and has no valid label
    The sealed ``washout_mapping.json`` of ``build_washout_packet.py`` is read as it is: a JSON object with
    a ``rows`` list.  Its other keys are not read: ``w`` (the weight is recomputed as 1 / inclusion_prob),
    ``position``, ``selection``, ``category_stratum``, ``view_ref``, ``cq_text_source`` and
    ``cq_shown_differs_from_judge_input``.  Its control rows say ``stratum: control`` and
    ``inclusion_prob: 1.0``; both are ignored.  (The builder says the first six keys of its rows are the ones
    read here; the six names above are, and its sixth key ``w`` is not among them while its seventh,
    ``excluded_reason``, is.)
``--ah-labels``  the AH label sheet (label_assist 12-column CSV): ``cell_id``, ``cluster_id`` (the CQ
    cluster that is resampled), ``A`` (0/1), ``rater_L1`` (0..3).  Control rows of this file are never
    read: the controls of the design and every id starting ``ablated_control:`` or ``preserved_control:``
    are only tolerated.
``--washout-labels``  the washout label sheet, same columns, keyed by the opaque id.  Primary rows must
    carry A and rater_L1.  A presented control without an A is allowed: it is not a valid control.  The sheet
    has 12 columns (the AH layout) or, in ``--packet`` mode, 14: the 13th is ``ai_used`` (yes = ticked, blank =
    not recorded) and the 14th ``dwell_ms`` (a running total in ms over the row's saves, not read here: the
    audit holds every save).  The first packet layout, 13 columns without ``dwell_ms``, is read alike; columns
    are found by name.
``--label-source``  ``human`` or an explicit simulation marker when a label CSV has no
    ``label_source``/``source`` column (the rule of analyze_holdout: never inferred).  A simulation
    marker stamps the output ``rehearsal: true``.
``--audit``  label_assist ``<out>.audit.jsonl`` of that pass: save records with ``cell_id``, ``ts``,
    ``elapsed_s``, ``session_id`` and, in ``--packet`` mode, ``dwell_ms`` (integer ms: the client's
    performance.now() delta from opening the row to saving it), ``sitting_id`` and the per-row tick
    ``ai_used`` (true = ticked; null or absent = not recorded).  Source of the dwell check, of the washout
    gap and of the per-row AI tick.  The working CSV's own ``dwell_ms`` column is not read: the audit holds
    every save.
``--session-log``  label_assist ``<out>.session_log.txt``: ``SESSION start=.. pid=.. session_id=..`` (and
    optionally ``sitting_id=..``) and ``SESSION end=.. pid=.. saved=..`` lines, and in ``--packet`` mode the
    sitting-end self-report ``AI_USE {"used": "yes"|"no"|"not recorded", "tool": "..", "approx_cells": n,
    "session_id": "..", "sitting_id": ".."}``: one report per sitting, append-only (a second line of the
    same sitting_id supersedes the first and is counted).  A cell's report is the one of the sitting of
    its last audit save, joined on ``sitting_id``; when the audit lines or the reports carry no
    ``sitting_id`` the join falls back to ``session_id`` (the last report of the session).  The tool is kept
    normalized (NFKC, whitespace collapsed, case-folded).
``--exclude-controls``  text file (one id per line, ``#`` comments) or ``.json`` list: the 8 ablated controls
    seen with the id prefix in S6 (the DN-7 rerun; sec.13.1 (12)).  Matched against ``source_cell_id`` or
    ``cell_id`` of control rows; an entry that matches nothing, or a primary row, is an error.
``--ah-last-save``  ISO-8601 time with an offset (default the registered 2026-10-08T23:58:55+09:00): the AH
    pass's last save, from which the washout gap is measured.
``--cells``  the judge run (cells.jsonl, read with ``load_cells``): ``cell_id``, ``cell_kind``,
    ``category``, ``cluster_id``, ``J``.  Used by ``second`` only.
``--sample-list``  the 48-cell list: one ``cell_id`` per line, sorted, trailing newline (768 bytes in
    the registration).  Its sha256 is checked against the registered ``bd2333d4...854b7e`` (DN-8).
``--second-labels``  the second annotator's label sheet; ``cell_id`` as shown to that annotator.  In
    ``--packet`` mode it has 14 columns: the 13th is ``ai_used`` (yes = ticked; blank = not recorded), a per-row
    AI-use flag that needs no audit, and the 14th ``dwell_ms`` (a running total in ms, not read: the audit holds
    every save); the 13-column layout without ``dwell_ms`` is read alike.
``--id-map``  optional table ``cell_id,source_cell_id`` when the second annotator saw opaque ids.
``--expect-sha256 NAME=HEX``  assert an input file's sha256 (e.g. the lock manifest value) before the
    analysis; NAME is the flag name without dashes (``washout_labels``, ``ah_labels``, ...).

----------------------------------------------------------------------------
STATISTICS (as registered in sec.12.3-12.4 and sec.13.1)
----------------------------------------------------------------------------
G2, reweighted pooled estimate (the gate input, DN-4b):
    w_i = 1 / pi_i, pi_i from the sealed design file;  M_jk = sum_i w_i 1[AH_L1 = j, WO_L1 = k];
    O = sum (j-k)^2 M_jk;  E = sum (j-k)^2 M_j+ M_+k / M_++;  QWK_w = 1 - O / E.
    Interval: 95% two-sided BCa from ``cluster_bootstrap_stat``: unstratified, whole CQ clusters, the
    weights stay fixed per cell (no renormalisation), B = 10,000, default_rng(20260913), leave-one-
    cluster-out jackknife, mid-rank z0.  Gate: lower end >= 0.70.  A resample with E = 0 counts as
    QWK = 0 (not 1.0) and is counted in the output.  If E = 0 on the observed data the estimate is
    undefined and G2 is not computable.  Kish n_eff = (sum w)^2 / sum w^2 is reported.  The E = 0 -> 0
    rule belongs to G2 alone (sec.12.3, sec.13.1 (6)).
G2, per stratum (proportional 48, enriched 24): the plain, UNWEIGHTED QWK of the stratum's own cells.  Its
    BCa interval resamples THAT STRATUM'S OWN CQ CLUSTERS (whole clusters, no weights; sec.13.1 (6)), with the
    same E = 0 rule.  The Fleiss-Cohen-Everitt (1969) non-null SE of that unweighted QWK is beside it; it
    is reported for the two strata only and is never a decision input.
G2, washout gap (DN-5, sec.13.1 (10)): days from the AH pass's last save to the first washout save of any
    row of the design, from the audit, in the G2 output with the 21-day minimum and the 28-day target.
G3-W (DN-7): a verdict only if all 24 ablated controls were presented and labeled (pass iff at least 22
    carry A = 0); otherwise no verdict, the A = 0 count over the valid count is reported.  The rerun that
    excludes a given list of controls (16 expected) never gives a verdict: the A = 0 count out of the
    valid count only.  Preserved controls: the A = 1 count.
Binary A between the passes (2x2, rows = AH pass): raw agreement and Cohen kappa per stratum and weighted
    pooled; no unweighted pooled (sec.13.1 (6)).  Descriptive only.
Binary A, second annotator (2x2, rows = the AH labels, columns = the second annotator): raw agreement,
    Cohen kappa, Gwet AC1 with p_e = 2 pi (1 - pi), pi = (p_1+ + p_+1) / 2; PPA = n11 / (n11 + n10) and
    NPA = n00 / (n00 + n01).  No symmetric specific agreement is computed.
Undefined statistics (sec.12.4 (i), sec.13.1 (6)): for every sec.12.4 statistic (A agreement, the QWKs of
    rater_L1 and of J, exact agreement, kappa) a resample on which it is undefined (a zero denominator, E = 0
    for a QWK) is EXCLUDED from the interval and counted; nothing is substituted.  An undefined point
    estimate is reported as undefined, with its reason.
pi-hat (second): Pr[J >= 2 and A = 0] over the 48 cells (``silent_over_credit_rate``), with the CLUSTER-
    level one-sided Clopper-Pearson upper bounds at 97.5% and 95%: an event cluster has at least one cell
    with J >= 2 and A = 0, n is the number of clusters the cells cover.  Not a G1 decision, and not an
    estimate of the 188-cell pi (sec.12.4 (ii)).
Judge vs the second annotator: QWK(J, rater_L1), exact agreement and the Cohen kappa of 1[J >= 2] against
    A, each also restricted to the cells with J in {1, 2, 3}.
AI use (sec.12.1 D20, sec.13.1 (7)): the second-annotation statistics are also given by AI use; the washout
    gets the classification counts (``ai_use_classification``) and its own results by the same groups
    (``ai_use_stratified``, below).  PRIMARY stratification (``by_ai_use``: yes / no / not
    recorded): the sitting reported AI use.  yes = a ticked cell (the sheet's ``ai_used`` column or the
    ``ai_used`` tick on the cell's last audit save; a tick in either counts, a disagreement is counted) or an
    unticked cell of a sitting whose report says yes; no = an unticked cell of a sitting that reported no;
    not recorded = anything else.  SENSITIVITY (``by_ai_use_tick_only``): ticked / not ticked.
    ``by_tool_among_yes_cells``: the yes cells split by the normalized tool of their sitting's report.  Only
    a ticked cell is ever called a cell that used AI; the other cells of the yes group are cells of
    sittings that reported AI use.
Washout by AI use (D20; ``ai_use_stratified``; descriptive, labelled "descriptive; not a gate", never a decision
    input): for each group of the primary stratification (yes / no / not recorded), for each tool among the yes
    cells, and for the tick-only sensitivity (ticked / not ticked, and each tool among the ticked cells): n cells
    and n CQ clusters; the QWK of rater_L1 between the passes WEIGHTED (the table weighted by 1/pi_i, the
    estimator of pooled G2, restricted to the group's cells) and UNWEIGHTED, each with a 95% BCa interval that
    resamples THE GROUP'S OWN CQ clusters (whole clusters, weights fixed); a resample on which the QWK is
    undefined (E = 0) is EXCLUDED and counted (the sec.12.4 rule), NOT set to 0 (the G2 rule belongs to the
    gate alone); a group with no cell, with fewer than two CQ clusters (the cluster resampling needs two) or
    with an undefined QWK is ``not_computable``, shown with its n and the reason and no result; and the binary A
    agreement between the passes per design stratum and as a weighted pool (no unweighted pool).  No minimum
    group size beyond that, no adjustment for multiplicity, no test of a difference between groups.
Dwell (DN-5, G7-style; sec.13.1 (9)): per cell the TOTAL dwell over all its saves, where a save counts
    ``dwell_ms`` / 1000 when its audit line has a usable ``dwell_ms`` (packet mode) and ``elapsed_s``
    otherwise (AH mode), and the output records which basis was used; share under 20 s against the 3% limit
    (strictly below), median and IQR (linear quartiles) of the cells whose total is fully known; controls
    apart; sessions = SESSION start lines; no cell is dropped.

QWK everywhere uses the squared level distance on the 4x4 table of rater_L1 (the quantity of
``analyze_holdout._qwk_from_values``) and is None when E = 0.  Intervals are 95% BCa.

----------------------------------------------------------------------------
OUTPUT AND GUARDS
----------------------------------------------------------------------------
``--out``: JSON, AGGREGATES ONLY: no cell, CQ or washout identifier (checked with
``find_cell_level_leaks`` before writing).  ``--out-cells``: per-cell values, a separate file to be kept
sealed.  Both carry a ``provenance`` block (analyzer and helper sha256, git HEAD, every input path and
sha256, seed, B, label-source strings, the exploratory status, environment).  Guards: an output may not be
an input (symlinks and hard links included, ``analyze_holdout``'s guard); ``--out`` and ``--out-cells`` must
differ; an existing output is not overwritten without ``--overwrite``; ``--out-cells`` may not sit in a
rater-readable directory (``annotation_pending``, ``packet``, ``views``); the text of every output is
scanned for the wording the registration rules out (the list is FORBIDDEN_WORDING: it covers how the AH,
washout and second-annotator labels may be described, the names of PPA/NPA and of G2, and who may be called
a cell that used AI) and nothing is written if one is found; operator-entered tool names and input paths
are data and are masked in that scan.  Washout labels are never an input to any primary estimate (PREREG
L597).

Generated code: review and test it before use, and run it on the synthetic fixtures first.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import platform
import random
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import analyze_holdout as ah  # noqa: E402  (the registered analyzer; never edited here)

# --- helpers taken from the registered analyzer, by import --------------------
cluster_bootstrap_stat = ah.cluster_bootstrap_stat
silent_over_credit = ah.silent_over_credit
silent_over_credit_rate = ah.silent_over_credit_rate
clopper_pearson_upper = ah.clopper_pearson_upper
load_label_csv = ah.load_label_csv
load_label_audit = ah.load_label_audit
load_cells = ah.load_cells
find_cell_level_leaks = ah.find_cell_level_leaks
_bca_interval = ah._bca_interval            # the mid-rank z0 (ah._bca_z0) lives inside
_group_clusters = ah._group_clusters
_gate = ah._gate
_parse_utc = ah._parse_utc
_cell_kind = ah._cell_kind
_same_file = ah._same_file
_refuse_outputs_that_are_inputs = ah._refuse_outputs_that_are_inputs
_json_default = ah._json_default
_sha256_file = ah._sha256_file

# --------------------------------------------------------------------------
# registered and pinned constants
# --------------------------------------------------------------------------
REGISTERED_SEED = ah.REGISTERED_SEED
BOOTSTRAP_RESAMPLES = ah.BOOTSTRAP_RESAMPLES  # looked up at call time; tests may shrink it
DEFAULT_BCA_TIES = ah.DEFAULT_BCA_TIES        # "midrank"
CI_LEVEL = ah.RESOLVE_CI_LEVEL                # 0.95, two-sided
CI_ALPHA = ah.RESOLVE_ALPHA

G2_CI_LOWER_THRESHOLD = 0.70                  # PREREG L344, DN-4b
G3W_REGISTERED_N = ah.G3_REGISTERED_N         # 24 ablated controls
G3W_MIN_UNSUPPORTED = ah.G3_MIN_UNSUPPORTED   # at least 22 of them with A = 0
G3W_REGISTERED_PRESERVED_N = 12
DWELL_FAST_SECONDS = ah.G7_FAST_SECONDS       # 20 s
DWELL_FAST_SHARE_LIMIT = ah.G7_FAST_SHARE_BELOW  # 3%, strictly below
JUDGE_CREDIT_THRESHOLD = 2                    # pi = Pr[J >= 2 and A = 0]
PI_UPPER_BOUND_LIMIT = ah.G1_UPPER_BOUND_THRESHOLD  # 0.10, used only in the zero-event note
JUDGE_RESTRICTED_LEVELS = (1, 2, 3)
L1_LEVELS = 4
MAX_UNDEFINED_REPLICATE_SHARE = 0.5           # above this a conditional interval is not reported
_DEGENERATE_TOL = 1e-12

WASHOUT_N_PRIMARY = 72
WASHOUT_STRATA = ("proportional", "enriched")
WASHOUT_REGISTERED_STRATA_SIZES = {"proportional": 48, "enriched": 24}
REGISTERED_FRAME_SIZE = len(ah.REGISTERED_PRIMARY_SET)  # 188 primary cells
CELL_KIND_PRIMARY = ah.CELL_KIND_PRIMARY
CONTROL_KINDS = ah.CONTROL_CELL_KINDS         # ("ablated_control", "preserved_control")
CONTROL_ID_PREFIXES = tuple(f"{kind}:" for kind in CONTROL_KINDS)   # control ids name their kind (D6)

SECOND_N = 48
SECOND_PER_CATEGORY = 8
SECOND_SAMPLE_SHA256 = "bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e"
AI_USE_GROUPS = ("yes", "no", "not recorded")
TICK_ONLY_GROUPS = ("ticked", "not ticked")
TOOL_NOT_GIVEN = "(tool not given)"
TOOL_NO_YES_REPORT = "(ticked, no report of AI use for the sitting)"
AH_LAST_SAVE = "2026-10-08T23:58:55+09:00"    # PREREG sec.12.3 DN-5, sec.13.1 (10): the AH pass's last save
WASHOUT_MIN_GAP_DAYS = 21                     # L522: not earlier than 21 days after that save
WASHOUT_TARGET_GAP_DAYS = 28                  # DN-5: the target
AI_RECORDING_NOTE = ("AI chat tools are permitted in the washout and second-annotation passes. Use is "
                     "self-reported: a report at the end of each sitting (yes or no, the tool, about how many "
                     "cells) and an optional tick on each row; a row or sitting with neither is 'not "
                     "recorded'. The AH pass has no cell-level AI record (PREREG sec.12.1 D3, D20, sec.13.1 (7))")
EVIDENCE_STATUS = "exploratory"               # PREREG sec.12.2 (7), sec.13.1 (13)
EVIDENCE_STATUS_NOTE = ("exploratory, not confirmatory (PREREG sec.12.2 (7)): label-based statistics are "
                        "reported as computed and no gate pass is a basis for a calibration claim")

# The ONLY wording used for where these labels come from.
LABEL_SOURCE_AH = "LLM-assisted (AI-drafted, author-revised) labels"
LABEL_SOURCE_WASHOUT = "same-rater washout pass"
LABEL_SOURCE_SECOND = "second, non-author annotator (AI tools permitted, self-reported)"

RATER_VISIBLE_DIR_NAMES = frozenset({"annotation_pending", "packet", "views"})
SCHEMA_VERSION = "analyze_washout v1"

# Wording the registration rules out of every output (case-insensitive).
FORBIDDEN_WORDING = (
    ("verified", re.compile(r"\bverified\b", re.I)),
    ("reference", re.compile(r"\breference\w*", re.I)),
    ("independent human/annotator/rater", re.compile(
        r"independent(?:ly)?[\s\-]+(?:blind[\s\-]+)?(?:human|annotator|rater)", re.I)),
    ("test-retest", re.compile(r"test[\s\-\u2010-\u2015]*retest", re.I)),
    ("specificity", re.compile(r"specificity", re.I)),
    # only a cell the labeler ticked may be said to have used AI (PREREG sec.13.1 (7)); the output says
    # "ticked cells" and "cells of sittings that reported AI use" instead
    ("cells that used AI", re.compile(r"cells?\s+(?:that\s+)?used\s+(?:an?\s+)?(?:AI|chat)", re.I)),
)

UNDEFINED_REASONS = {
    "qwk": "both rater_L1 columns use one level only (E = 0): QWK is 0/0",
    "cohen_kappa": "chance agreement is 1 (both label columns are constant and equal): kappa is 0/0",
    "ppa": "the AH column has no positive (A=1) cell: PPA has an empty denominator",
    "npa": "the AH column has no negative (A=0) cell: NPA has an empty denominator",
}


# --------------------------------------------------------------------------
# tables and agreement statistics (pure functions)
# --------------------------------------------------------------------------
def _levels(values, k: int, what: str) -> np.ndarray:
    out = []
    for v in values:
        if isinstance(v, (bool, np.bool_)) or not isinstance(v, (int, np.integer)) \
                or not 0 <= int(v) < k:
            raise ValueError(f"{what} must be an int in 0..{k - 1}, got {v!r}")
        out.append(int(v))
    return np.array(out, dtype=np.int64)


def confusion_table(x, y, w=None, k: int = L1_LEVELS) -> np.ndarray:
    """k x k table of (summed) weights: rows = ``x`` (the first rater, or the AH column), columns
    = ``y``.  Values must be ints in 0..k-1; weights finite and positive."""
    xs, ys = _levels(x, k, "x"), _levels(y, k, "y")
    if len(xs) != len(ys):
        raise ValueError("x and y must be equally long")
    if w is None:
        ws = np.ones(len(xs), dtype=float)
    else:
        ws = np.asarray(list(w), dtype=float)
        if len(ws) != len(xs) or not np.all(np.isfinite(ws)) or np.any(ws <= 0):
            raise ValueError("weights must be finite, positive and one per cell")
    return np.bincount(xs * k + ys, weights=ws, minlength=k * k).reshape(k, k)


def qwk_from_table(table) -> float | None:
    """QWK_w = 1 - O / E of a (weighted) table M:  O = sum (j-k)^2 M_jk and
    E = sum (j-k)^2 M_j+ M_+k / M_++.  None if M is empty or E = 0.

    Equal weights give exactly ``analyze_holdout._qwk_from_values``; that function maps the E = 0 case
    to 1.0 or 0.0, this one reports it as undefined (a bootstrap caller then counts it as 0)."""
    t = np.asarray(table, dtype=float)
    total = float(t.sum())
    if not total > 0:
        return None
    lv = np.arange(t.shape[0], dtype=float)
    d = (lv[:, None] - lv[None, :]) ** 2
    observed = float((d * t).sum())
    expected = float((d * np.outer(t.sum(1), t.sum(0))).sum()) / total
    if expected <= _DEGENERATE_TOL * total:
        return None
    return 1.0 - observed / expected


def weighted_qwk(x, y, w=None, k: int = L1_LEVELS) -> float | None:
    return qwk_from_table(confusion_table(x, y, w, k))


def exact_agreement_from_table(table) -> float | None:
    t = np.asarray(table, dtype=float)
    total = float(t.sum())
    return float(np.trace(t)) / total if total > 0 else None


def kish_effective_n(weights) -> float:
    """(sum w)^2 / sum w^2; equals n when all weights are equal."""
    w = np.asarray(list(weights), dtype=float)
    if len(w) == 0 or np.any(w <= 0):
        raise ValueError("Kish effective n needs one or more positive weights")
    return float(w.sum() ** 2 / np.sum(w ** 2))


def fleiss_cohen_se(table, n: float | None = None) -> float | None:
    """Large-sample standard error of the quadratic-weighted kappa of a table
    (Fleiss, Cohen & Everitt 1969, general / non-null variance):

      Var = [ sum_ij p_ij (w_ij (1 - pe) - (wbar_i. + wbar_.j)(1 - po))^2
              - (po pe - 2 pe + po)^2 ] / (n (1 - pe)^4)

    with agreement weights w_ij = 1 - (i-j)^2 / (k-1)^2, po = sum w p, pe = sum w p_i. p_.j,
    wbar_i. = sum_j w_ij p_.j, wbar_.j = sum_i w_ij p_i..  ``n`` defaults to the table total.  None
    when pe = 1.  Used for the two unweighted strata only, never as a decision input."""
    t = np.asarray(table, dtype=float)
    total = float(t.sum())
    if not total > 0:
        return None
    n_obs = total if n is None else float(n)
    p = t / total
    k = t.shape[0]
    lv = np.arange(k, dtype=float)
    w = 1.0 - (lv[:, None] - lv[None, :]) ** 2 / float(k - 1) ** 2
    pr, pc = p.sum(1), p.sum(0)
    po = float((w * p).sum())
    pe = float((w * np.outer(pr, pc)).sum())
    if 1.0 - pe <= _DEGENERATE_TOL:
        return None
    w_row = (w * pc[None, :]).sum(1)
    w_col = (w * pr[:, None]).sum(0)
    term = w * (1.0 - pe) - (w_row[:, None] + w_col[None, :]) * (1.0 - po)
    var = (float((p * term ** 2).sum()) - (po * pe - 2.0 * pe + po) ** 2) / (n_obs * (1.0 - pe) ** 4)
    return math.sqrt(max(var, 0.0))


def raw_agreement_from_table(t) -> float | None:
    return exact_agreement_from_table(t)


def cohen_kappa_from_table(t) -> float | None:
    """Cohen's kappa of a 2x2 table (rows = first column); None when chance agreement is 1."""
    t = np.asarray(t, dtype=float)
    n = float(t.sum())
    if not n > 0:
        return None
    po = float(t[0, 0] + t[1, 1]) / n
    r1, c1 = float(t[1, :].sum()) / n, float(t[:, 1].sum()) / n
    pe = r1 * c1 + (1.0 - r1) * (1.0 - c1)
    if 1.0 - pe <= _DEGENERATE_TOL:
        return None
    return (po - pe) / (1.0 - pe)


def gwet_ac1_from_table(t) -> float | None:
    """Gwet's AC1 for two raters, binary: p_e = 2 pi (1 - pi), pi = (p_1+ + p_+1) / 2.  Since
    p_e <= 1/2 it is defined whenever the table is non-empty."""
    t = np.asarray(t, dtype=float)
    n = float(t.sum())
    if not n > 0:
        return None
    po = float(t[0, 0] + t[1, 1]) / n
    pi1 = (float(t[1, :].sum()) + float(t[:, 1].sum())) / (2.0 * n)
    pe = 2.0 * pi1 * (1.0 - pi1)
    return (po - pe) / (1.0 - pe)


def ppa_from_table(t) -> float | None:
    """PPA = n11 / (n11 + n10) with rows = the AH labels: of the AH positives, the share the second
    annotator also marks positive.  None if the AH column has no positive."""
    t = np.asarray(t, dtype=float)
    den = float(t[1, :].sum())
    return float(t[1, 1]) / den if den > 0 else None


def npa_from_table(t) -> float | None:
    """NPA = n00 / (n00 + n01) with rows = the AH labels.  None if the AH column has no negative."""
    t = np.asarray(t, dtype=float)
    den = float(t[0, :].sum())
    return float(t[0, 0]) / den if den > 0 else None


BINARY_STATS = {
    "raw_agreement": raw_agreement_from_table,
    "cohen_kappa": cohen_kappa_from_table,
    "gwet_ac1": gwet_ac1_from_table,
    "ppa": ppa_from_table,
    "npa": npa_from_table,
}


def binary_agreement(ref, cand, w=None) -> dict:
    """The five binary statistics of two 0/1 columns (rows = ``ref``, the AH column); None where
    undefined."""
    t = confusion_table(ref, cand, w, k=2)
    out = {name: fn(t) for name, fn in BINARY_STATS.items()}
    out["table"] = {"n11": float(t[1, 1]), "n10": float(t[1, 0]),
                    "n01": float(t[0, 1]), "n00": float(t[0, 0])}
    return out


def clopper_pearson_two_sided(k: int, n: int, conf: float = CI_LEVEL) -> tuple[float, float]:
    """Exact two-sided binomial interval (a descriptive companion of a count)."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError("need 0 <= k <= n and n > 0")
    a = 1.0 - conf
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return lo, hi


# --------------------------------------------------------------------------
# resampling: the registered helper, with undefined replicates handled openly
# --------------------------------------------------------------------------
class _UndefinedStatistic(Exception):
    """Raised inside the registered helper's loop when a statistic is undefined."""


def _table_from_records(sample, kx: str, ky: str, kw: str | None, k: int) -> np.ndarray:
    n = len(sample)
    x = np.fromiter((r[kx] for r in sample), dtype=np.int64, count=n)
    y = np.fromiter((r[ky] for r in sample), dtype=np.int64, count=n)
    w = None if kw is None else np.fromiter((r[kw] for r in sample), dtype=float, count=n)
    return np.bincount(x * k + y, weights=w, minlength=k * k).reshape(k, k).astype(float)


def table_stat(fn, kx: str, ky: str, *, kw: str | None = None, k: int = L1_LEVELS):
    """stat_fn(records) -> float | None for a statistic of the (weighted) table of two record
    fields.  Record values are validated once, when the records are built."""
    def stat(sample):
        return fn(_table_from_records(sample, kx, ky, kw, k))
    return stat


def _undefined_interval(reason: str, **extra) -> dict:
    return {"estimate": None, "ci_lo": None, "ci_hi": None, "ci_level": CI_LEVEL,
            "ci_status": "undefined_estimate", "ci_reason": reason, **extra}


def cluster_bca(
    cells: list[dict],
    stat_fn,
    *,
    seed: int | None,
    B: int | None = None,
    cluster_key: str = "cluster_id",
    ties: str = DEFAULT_BCA_TIES,
    undefined_reason: str = "the statistic is undefined on these data",
    undefined_replicate_value: float | None = None,
) -> dict:
    """95% two-sided BCa interval of ``stat_fn(cells)``: whole clusters, unstratified, B resamples,
    ``np.random.default_rng(seed)``, leave-one-cluster-out jackknife, mid-rank z0 -- all from the
    registered ``cluster_bootstrap_stat``.

    ``stat_fn`` returns None where the statistic is undefined.  The point estimate is checked first:
    undefined means no interval and the stated reason.  On a resample or jackknife sample:
      * ``undefined_replicate_value=None`` (default): the undefined replicates are EXCLUDED from the
        interval and counted.  When none is undefined the result is bit-identical to calling the
        registered helper directly; otherwise the same draws are made and the BCa routine is run on
        the defined replicates.  A leave-one-cluster-out sample that is undefined sets the BCa
        acceleration to 0 and says so; more than half undefined gives no interval;
      * ``undefined_replicate_value=v``: an undefined replicate counts as ``v`` (0.0 for QWK with E = 0)
        and is counted; the registered helper runs unchanged on the substituted values."""
    if seed is None:
        raise ValueError("the randomization seed is pre-registered; refusing to default it")
    B = BOOTSTRAP_RESAMPLES if B is None else B
    cells = list(cells)
    clusters = [cl for stratum in _group_clusters(cells, None, cluster_key) for cl in stratum]
    policy = "dropped" if undefined_replicate_value is None else f"set_to_{undefined_replicate_value:g}"
    base = {"n_cells": len(cells), "n_clusters": len(clusters), "resamples": B, "seed": seed,
            "bca_ties": ties, "ci_level": CI_LEVEL, "ci_method": "BCa cluster bootstrap",
            "unit": "CQ cluster (whole clusters, unstratified)", "undefined_replicate_policy": policy}
    theta = stat_fn(cells)
    if theta is None:
        return _undefined_interval(undefined_reason, **base)
    theta = float(theta)
    if len(clusters) < 2:
        return {**base, "estimate": theta, "ci_lo": None, "ci_hi": None,
                "ci_status": "fewer_than_two_clusters",
                "ci_reason": "fewer than two clusters: nothing to resample"}
    if undefined_replicate_value is not None:
        return _bca_substituting(cells, stat_fn, base, seed, B, cluster_key, ties,
                                 float(undefined_replicate_value), len(clusters))

    def total(sample):
        value = stat_fn(sample)
        if value is None:
            raise _UndefinedStatistic
        return value

    try:
        res = cluster_bootstrap_stat(cells, total, None, cluster_key, B, seed, ties)
    except _UndefinedStatistic:
        return _bca_dropping(cells, stat_fn, theta, base, seed, B, cluster_key, ties)
    return {**base, "estimate": res["estimate"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
            "ci_status": "computed", "n_undefined_replicates": 0, "undefined_replicate_share": 0.0,
            "n_undefined_jackknife_samples": 0, "acceleration_defined": True,
            "tie_share": res["tie_share"]}


def _bca_substituting(cells, stat_fn, base, seed, B, cluster_key, ties, value, n_clusters) -> dict:
    undefined_at: list[int] = []
    n_calls = [0]

    def wrapped(sample):
        i = n_calls[0]
        n_calls[0] += 1
        v = stat_fn(sample)
        if v is None:
            undefined_at.append(i)
            return value
        return v

    res = cluster_bootstrap_stat(cells, wrapped, None, cluster_key, B, seed, ties)
    # The helper evaluates the point estimate first, then the B resamples, then the
    # leave-one-cluster-out samples; the split below relies on that order and checks the call count.
    split = n_calls[0] == 1 + B + n_clusters
    n_boot = sum(1 for i in undefined_at if 1 <= i <= B) if split else None
    n_jack = sum(1 for i in undefined_at if i > B) if split else None
    out = {**base, "estimate": res["estimate"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
           "ci_status": "computed", "n_undefined_replicates": n_boot,
           "undefined_replicate_share": (n_boot / B) if n_boot is not None else None,
           "n_undefined_jackknife_samples": n_jack, "acceleration_defined": True,
           "tie_share": res["tie_share"]}
    if not split:
        out["n_undefined_evaluations_total"] = len(undefined_at)
    return out


def _bca_dropping(cells, stat_fn, theta, base, seed, B, cluster_key, ties) -> dict:
    groups = _group_clusters(cells, None, cluster_key)
    clusters = [cl for stratum in groups for cl in stratum]
    rng = np.random.default_rng(seed)
    values: list[float] = []
    n_undefined = 0
    for _ in range(B):                      # the draw loop of ``cluster_bootstrap_stat``
        sample: list = []
        for stratum in groups:
            n_s = len(stratum)
            for i in rng.integers(0, n_s, n_s).tolist():
                sample.extend(stratum[i])
        value = stat_fn(sample)
        if value is None:
            n_undefined += 1
        else:
            values.append(float(value))
    out = {**base, "estimate": theta, "n_undefined_replicates": n_undefined,
           "undefined_replicate_share": n_undefined / B}
    if n_undefined / B > MAX_UNDEFINED_REPLICATE_SHARE or len(values) < 2:
        return {**out, "ci_lo": None, "ci_hi": None, "ci_status": "too_many_undefined_replicates",
                "n_undefined_jackknife_samples": None, "acceleration_defined": None,
                "ci_reason": f"the statistic is undefined on {n_undefined} of {B} resamples; a "
                             "conditional interval is not reported"}
    jack: list[float] | None = []
    n_jack_undefined = 0
    for k in range(len(clusters)):
        value = stat_fn([c for j, cl in enumerate(clusters) if j != k for c in cl])
        if value is None:
            n_jack_undefined += 1
        elif jack is not None:
            jack.append(float(value))
    accel_defined = n_jack_undefined == 0
    if not accel_defined:
        jack = [theta] * len(clusters)       # a constant jackknife gives acceleration 0
    lo, hi = _bca_interval(theta, np.asarray(values), jack, CI_ALPHA, ties)
    return {**out, "ci_lo": lo, "ci_hi": hi, "ci_status": "computed_without_undefined_replicates",
            "n_undefined_jackknife_samples": n_jack_undefined, "acceleration_defined": accel_defined,
            "ci_reason": "undefined replicates were excluded and counted; the interval is "
                         "conditional on the statistic being defined"}


_INTERVAL_KEYS = ("estimate", "ci_lo", "ci_hi", "ci_level", "ci_status", "ci_reason", "n_cells",
                  "n_clusters", "resamples", "undefined_replicate_policy", "n_undefined_replicates",
                  "undefined_replicate_share", "n_undefined_jackknife_samples", "acceleration_defined")


def _interval_block(res: dict) -> dict:
    """The fields of a ``cluster_bca`` result that go into an output."""
    return {k: res[k] for k in _INTERVAL_KEYS if k in res}


def _analytic_check(table, n_for_se: float, bca: dict) -> dict:
    """Fleiss-Cohen-Everitt SE and Wald interval beside the BCa interval (descriptive only)."""
    est = qwk_from_table(table)
    se = fleiss_cohen_se(table, n_for_se)
    out = {"method": "Fleiss-Cohen-Everitt 1969 large-sample SE of the unweighted QWK (non-null)",
           "decision_input": False, "n_for_se": float(n_for_se), "se": se, "wald_ci95": None,
           "bca_halfwidth_over_wald_halfwidth": None}
    if est is None or se is None:
        return out
    z = float(stats.norm.ppf(1 - CI_ALPHA / 2))
    lo, hi = est - z * se, est + z * se
    out["wald_ci95"] = [lo, hi]
    if bca.get("ci_lo") is not None and se > 0:
        out["bca_halfwidth_over_wald_halfwidth"] = (bca["ci_hi"] - bca["ci_lo"]) / (hi - lo)
    return out


# --------------------------------------------------------------------------
# small file helpers
# --------------------------------------------------------------------------
def read_table(path: Path) -> list[dict]:
    """A CSV (header row) or a ``.json`` list of objects -> list of str-valued dicts."""
    if not path.is_file():
        raise ValueError(f"no such file: {path}")
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("rows"), list):
            data = data["rows"]
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise ValueError(f"{path} must hold a JSON list of objects")
        return [{str(k).strip(): ("" if v is None else str(v).strip()) for k, v in r.items()}
                for r in data]
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return [{str(k).strip(): ("" if v is None else str(v).strip())
                 for k, v in row.items() if k is not None} for row in reader]


def _require_columns(rows: list[dict], columns, path: Path) -> None:
    if not rows:
        raise ValueError(f"{path} has no rows")
    missing = [c for c in columns if c not in set(rows[0])]
    if missing:
        raise ValueError(f"{path} lacks column(s) {missing}")


def read_id_list(path: Path) -> list[str]:
    """One id per line (``#`` comments and blank lines ignored) or a ``.json`` list."""
    if not path.is_file():
        raise ValueError(f"no such file: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"{path} must hold a JSON list")
        return [str(x).strip() for x in data if str(x).strip()]
    return [ln.strip() for ln in text.split("\n") if ln.strip() and not ln.strip().startswith("#")]


def read_sheet_fields(path: Path, columns=("cluster_id",), *, required: bool = True) -> dict[str, dict[str, str]]:
    """cell_id -> {column: value} for a label sheet (the label values are NOT read here).  With
    ``required=False`` a sheet without those columns gives {} instead of an error."""
    rows = read_table(path)
    if not required and (not rows or any(c not in rows[0] for c in columns)):
        return {}
    _require_columns(rows, ("cell_id", *columns), path)
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        cid = row.get("cell_id", "")
        if cid:
            out[cid] = {c: row.get(c, "") for c in columns}
    return out


# --------------------------------------------------------------------------
# washout design (the sealed build file) and the join with the labels
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class DesignRow:
    cell_id: str
    source_cell_id: str
    cell_kind: str
    stratum: str | None
    inclusion_prob: float | None
    excluded_reason: str | None


def load_washout_design(path: Path) -> list[DesignRow]:
    rows = read_table(path)
    _require_columns(rows, ("cell_id", "source_cell_id", "cell_kind"), path)
    out: list[DesignRow] = []
    seen_id: set[str] = set()
    seen_src: set[str] = set()
    for n, row in enumerate(rows, start=1):
        cid, src = row.get("cell_id", ""), row.get("source_cell_id", "")
        if not cid or not src:
            raise ValueError(f"design row {n}: cell_id and source_cell_id are required")
        if cid in seen_id:
            raise ValueError(f"design: duplicate cell_id {cid!r}")
        if src in seen_src:
            raise ValueError(f"design: duplicate source_cell_id {src!r}")
        seen_id.add(cid)
        seen_src.add(src)
        if not row.get("cell_kind", ""):
            raise ValueError(f"design row {n}: cell_kind is required (a blank kind is not read as primary)")
        kind = _cell_kind({"cell_id": cid, "cell_kind": row["cell_kind"]})
        stratum = row.get("stratum", "") or None
        prob = None
        reason = row.get("excluded_reason", "") or None
        if kind == CELL_KIND_PRIMARY:
            if stratum not in WASHOUT_STRATA:
                raise ValueError(f"design row {n}: a primary row needs stratum in "
                                 f"{list(WASHOUT_STRATA)}, got {stratum!r}")
            raw = row.get("inclusion_prob", "")
            try:
                prob = float(raw)
            except ValueError:
                prob = float("nan")
            if not (math.isfinite(prob) and 0.0 < prob <= 1.0):
                raise ValueError(f"design row {n}: inclusion_prob must be a probability in "
                                 f"(0, 1], got {raw!r} (PREREG sec.12.3 DN-4a)")
            if reason is not None:
                raise ValueError(f"design row {n}: a primary cell is never excluded after the fact "
                                 "(DN-5: no cell is dropped); excluded_reason is for controls")
        else:
            stratum = None
        out.append(DesignRow(cid, src, kind, stratum, prob, reason))
    return out


def check_washout_design(rows: list[DesignRow]) -> dict:
    """Compare the design with the registration (72 primary = 48 + 24; 24 ablated and 12 preserved
    controls).  Counts only.  DN-4a lets the strata sizes move when fewer than 24 mismatch cells
    exist, so only the total is required of the strata."""
    prim = [r for r in rows if r.cell_kind == CELL_KIND_PRIMARY]
    by_stratum = {s: sum(r.stratum == s for r in prim) for s in WASHOUT_STRATA}
    n_abl = sum(r.cell_kind == "ablated_control" for r in rows)
    n_pre = sum(r.cell_kind == "preserved_control" for r in rows)
    problems = []
    if len(prim) != WASHOUT_N_PRIMARY:
        problems.append(f"{len(prim)} primary cells, registered {WASHOUT_N_PRIMARY} (L456: not below)")
    if n_abl != G3W_REGISTERED_N:
        problems.append(f"{n_abl} ablated controls, registered {G3W_REGISTERED_N}")
    if n_pre != G3W_REGISTERED_PRESERVED_N:
        problems.append(f"{n_pre} preserved controls, registered {G3W_REGISTERED_PRESERVED_N}")
    return {
        "conforms": not problems, "problems": problems,
        "n_primary": len(prim), "registered_n_primary": WASHOUT_N_PRIMARY,
        "primary_by_stratum": by_stratum,
        "registered_primary_by_stratum": dict(WASHOUT_REGISTERED_STRATA_SIZES),
        "strata_sizes_as_registered": by_stratum == WASHOUT_REGISTERED_STRATA_SIZES,
        "n_ablated_controls": n_abl, "n_preserved_controls": n_pre,
        "n_controls_excluded_by_design": sum(r.excluded_reason is not None for r in rows),
        "source": "PREREG sec.12.3 DN-3 (72 = 48 + 24, controls counted apart), DN-4a (shortfall rule), DN-7",
    }


@dataclass(frozen=True)
class WashoutCell:
    cell_id: str
    source_cell_id: str
    cluster_id: str
    stratum: str
    pi: float
    w: float
    ah_a: int
    ah_l1: int
    wo_a: int
    wo_l1: int


@dataclass(frozen=True)
class ControlCell:
    cell_id: str
    source_cell_id: str
    kind: str
    excluded_reason: str | None   # not None: the control was not presented (design exclusion)
    a: int | None                 # None: not labeled (or not presented)

    @property
    def presented(self) -> bool:
        return self.excluded_reason is None

    @property
    def valid(self) -> bool:
        """Presented AND labeled."""
        return self.presented and self.a is not None


def join_washout(design: list[DesignRow], ah_labels, ah_fields: dict, wo_labels):
    """Join the design with the AH labels (primary rows only) and the washout labels.

    Returns (primary cells, controls).  Every primary row must carry its labels in both sheets and a
    cluster id (G2 needs all of them).  A control that was presented but has no A is kept as not valid
    (G3-W then gives no verdict).  A label row that is not in the design, and an excluded control that
    carries a label, are errors.  Control values of the AH sheet are never read."""
    design_ids = {r.cell_id for r in design}
    extra = sorted(set(wo_labels.labels) - design_ids)
    if extra:
        raise ValueError(f"washout labels contain {len(extra)} cell_id(s) absent from the design "
                         f"(e.g. {extra[:3]})")
    leaked = sorted(set(wo_labels.tolerated_nonblank_ids))
    if leaked:
        raise ValueError(f"{len(leaked)} control(s) the design marks as excluded carry a label "
                         f"(e.g. {leaked[:3]}): a control that was not presented cannot be labeled")
    primary: list[WashoutCell] = []
    controls: list[ControlCell] = []
    problems: list[str] = []
    for r in design:
        if r.cell_kind == CELL_KIND_PRIMARY:
            a0, l0 = ah_labels.labels.get(r.source_cell_id), ah_labels.rater_l1.get(r.source_cell_id)
            a1, l1 = wo_labels.labels.get(r.cell_id), wo_labels.rater_l1.get(r.cell_id)
            cl = (ah_fields.get(r.source_cell_id) or {}).get("cluster_id", "")
            if r.source_cell_id not in ah_labels.labels:
                problems.append(f"AH labels lack source cell {r.source_cell_id}")
            elif a0 is None or l0 is None:
                problems.append(f"AH labels lack A or rater_L1 for source cell {r.source_cell_id}")
            if r.cell_id not in wo_labels.labels:
                problems.append(f"washout labels lack cell {r.cell_id}")
            elif a1 is None or l1 is None:
                problems.append(f"washout labels lack A or rater_L1 for cell {r.cell_id}")
            if not cl:
                problems.append(f"AH sheet has no cluster_id for source cell {r.source_cell_id}")
            if None in (a0, l0, a1, l1) or not cl:
                continue
            primary.append(WashoutCell(r.cell_id, r.source_cell_id, cl, r.stratum, r.inclusion_prob,
                                       1.0 / r.inclusion_prob, a0, l0, a1, l1))
        elif r.excluded_reason is not None:
            controls.append(ControlCell(r.cell_id, r.source_cell_id, r.cell_kind, r.excluded_reason, None))
        else:
            controls.append(ControlCell(r.cell_id, r.source_cell_id, r.cell_kind, None,
                                        wo_labels.labels.get(r.cell_id)))
    if problems:
        raise ValueError("washout join failed: " + "; ".join(problems[:10])
                         + (f" (+{len(problems) - 10} more)" if len(problems) > 10 else ""))
    return sorted(primary, key=lambda c: c.cell_id), sorted(controls, key=lambda c: c.cell_id)


def _records(cells: list[WashoutCell]) -> list[dict]:
    return [{"cell_id": c.cell_id, "cluster_id": c.cluster_id, "stratum": c.stratum, "w": c.w,
             "x": c.ah_l1, "y": c.wo_l1, "a_ah": c.ah_a, "a_wo": c.wo_a} for c in cells]


# --------------------------------------------------------------------------
# G2 and the binary A agreement between the two passes
# --------------------------------------------------------------------------
def _weights_summary(cells: list[WashoutCell]) -> dict:
    w = [c.w for c in cells]
    if not w:
        return {"n_cells": 0}
    total = float(sum(w))
    return {"weights": "1 / inclusion_prob, from the sealed design file (fixed per cell)",
            "min_weight": float(min(w)), "max_weight": float(max(w)),
            "kish_n_eff": kish_effective_n(w),
            "ht_frame_size_estimate": total, "registered_frame_size": REGISTERED_FRAME_SIZE,
            "frame_size_relative_difference": (total - REGISTERED_FRAME_SIZE) / REGISTERED_FRAME_SIZE,
            "frame_size_note": "diagnostic only: the sum of 1/pi should be close to the 188 primary "
                               "cells the sample was drawn from; a large gap suggests the inclusion "
                               "probabilities are not the ones used in the draw"}


def _cluster_structure(cells: list[WashoutCell]) -> dict:
    """How the CQ clusters sit across the two strata (counts only)."""
    by_cq: dict[str, set[str]] = {}
    for c in cells:
        by_cq.setdefault(c.cluster_id, set()).add(c.stratum)
    return {"n_cq_clusters": len(by_cq),
            "n_cq_clusters_in_both_strata": sum(len(s) > 1 for s in by_cq.values())}


def g2_analysis(cells: list[WashoutCell], *, seed: int, B: int | None = None,
                ties: str = DEFAULT_BCA_TIES, threshold: float = G2_CI_LOWER_THRESHOLD) -> dict:
    """G2: same-rater agreement of rater_L1 between the AH pass and the washout pass (DN-4b, DN-6).

    The gate reads the REWEIGHTED POOLED QWK: weights 1/pi_i fixed per cell, unstratified whole-CQ-cluster
    BCa, a resample with E = 0 counted as QWK = 0.  The two strata are reported beside it, each with the
    plain, unweighted QWK of its own cells; the interval of a stratum is a BCa over THAT STRATUM'S OWN CQ
    CLUSTERS (whole clusters, no weights, the other stratum plays no part; PREREG sec.13.1 (6)) with the same
    E = 0 rule, and the Fleiss-Cohen-Everitt SE of that unweighted QWK is beside it (never a decision
    input)."""
    records = _records(cells)
    qwk_unw = table_stat(qwk_from_table, "x", "y")
    qwk_w = table_stat(qwk_from_table, "x", "y", kw="w")
    per_stratum: dict[str, dict] = {}
    for s in WASHOUT_STRATA:
        sub = [r for r in records if r["stratum"] == s]
        if not sub:
            per_stratum[s] = {"n_cells": 0, "n_clusters": 0, "qwk": None, "ci_lo": None, "ci_hi": None,
                              "ci_status": "empty_stratum", "ci_reason": "no cell in this stratum"}
            continue
        res = cluster_bca(sub, qwk_unw, seed=seed, B=B, ties=ties, undefined_reason=UNDEFINED_REASONS["qwk"],
                          undefined_replicate_value=0.0)
        tab = _table_from_records(sub, "x", "y", None, L1_LEVELS)
        entry = _interval_block(res)
        entry["qwk"] = entry.pop("estimate")
        entry["n_replicates_with_E_zero"] = res.get("n_undefined_replicates")
        entry["estimator"] = "plain QWK of the stratum's own cells (unweighted)"
        entry["resampling"] = ("BCa over this stratum's own CQ clusters: whole clusters, no weights "
                               "(PREREG sec.13.1 (6))")
        entry["confusion_table_AH_rows_washout_cols"] = tab.astype(int).tolist()
        entry["exact_agreement"] = exact_agreement_from_table(tab)
        entry["fleiss_cohen_everitt"] = _analytic_check(tab, float(len(sub)), res)
        per_stratum[s] = entry

    res = cluster_bca(records, qwk_w, seed=seed, B=B, ties=ties, undefined_reason=UNDEFINED_REASONS["qwk"],
                      undefined_replicate_value=0.0)
    tab_w = _table_from_records(records, "x", "y", "w", L1_LEVELS) if records else None
    pooled = _interval_block(res)
    pooled["qwk"] = pooled.pop("estimate", None)
    pooled.update(
        estimator="QWK_w = 1 - O/E of the confusion table weighted by 1/inclusion_prob (estimates "
                  "the 188-cell population)",
        resampling="unstratified whole CQ clusters; weights fixed per cell, no renormalisation; "
                   "default_rng(seed); leave-one-cluster-out jackknife; mid-rank z0",
        n_replicates_with_E_zero=res.get("n_undefined_replicates"),
        n_jackknife_samples_with_E_zero=res.get("n_undefined_jackknife_samples"),
        E_zero_convention="a resample with E = 0 counts as QWK = 0, not 1.0",
        kish_n_eff=(kish_effective_n([r["w"] for r in records]) if records else None),
        weighted_confusion_table_AH_rows_washout_cols=(None if tab_w is None else tab_w.tolist()))
    if res.get("estimate") is None:
        status, why = "not_computable", res.get("ci_reason") or "QWK undefined"
    elif res.get("ci_lo") is None:
        status, why = "not_computable", f"no interval: {res.get('ci_status')}"
    else:
        ok = res["ci_lo"] >= threshold
        status = "pass" if ok else "fail"
        why = f"lower end of the 95% BCa interval {res['ci_lo']:.4f} {'>=' if ok else '<'} {threshold:.2f}"
    return _gate(
        status, res.get("estimate"), threshold, why,
        name="G2: same-rater agreement between the AH pass and the washout pass (PREREG sec.12.3 DN-6)",
        score_column="rater_L1",
        gate_rule="pass iff the lower end of the 95% two-sided CQ-cluster BCa interval of the "
                  "reweighted pooled QWK is >= 0.70 (DN-4b); necessary, not sufficient (PREREG G2 row)",
        gate_input="reweighted_pooled",
        ci_lo=res.get("ci_lo"), ci_hi=res.get("ci_hi"), resamples=res.get("resamples"),
        estimates={"per_stratum": per_stratum, "reweighted_pooled": pooled},
        strata_present=[s for s in WASHOUT_STRATA if per_stratum[s]["n_cells"]],
        empty_strata=[s for s in WASHOUT_STRATA if not per_stratum[s]["n_cells"]],
        cluster_structure=_cluster_structure(cells),
        weights_summary=_weights_summary(cells),
        n_primary_cells=len(cells),
        reported_with="the dwell check (DN-5) is reported beside G2; no cell is removed after the fact",
    )


def a_agreement_between_passes(cells: list[WashoutCell], *, seed: int, B: int | None = None,
                               ties: str = DEFAULT_BCA_TIES) -> dict:
    """Binary A, AH pass vs washout pass: raw agreement and Cohen kappa, DESCRIPTIVE ONLY.

    Per stratum and reweighted pooled (weights 1/pi, unstratified whole-CQ-cluster BCa), like G2.  No
    unweighted pooled value is given: the enriched stratum is selected on 1[J>=2] != A_AH, so a plain
    pool of the two strata mixes a selected sample in arbitrary proportion.  Undefined replicates
    (kappa with a constant column) are excluded and counted."""
    records = _records(cells)
    out: dict = {"descriptive_only": True, "table_orientation": "rows = AH pass, columns = washout pass",
                 "per_stratum": {}, "reweighted_pooled": {}}
    names = {"raw_agreement": raw_agreement_from_table, "cohen_kappa": cohen_kappa_from_table}
    for s in WASHOUT_STRATA:
        sub = [r for r in records if r["stratum"] == s]
        entry: dict = {"n_cells": len(sub)}
        if sub:
            t = _table_from_records(sub, "a_ah", "a_wo", None, 2)
            entry["table"] = {"n11": int(t[1, 1]), "n10": int(t[1, 0]), "n01": int(t[0, 1]),
                              "n00": int(t[0, 0])}
            for name, fn in names.items():
                entry[name] = _interval_block(cluster_bca(
                    sub, table_stat(fn, "a_ah", "a_wo", k=2), seed=seed, B=B, ties=ties,
                    undefined_reason=UNDEFINED_REASONS.get(name, "undefined")))
        out["per_stratum"][s] = entry
    pooled: dict = {"n_cells": len(records),
                    "estimator": "weighted 2x2 table, weights 1/inclusion_prob; unstratified whole "
                                 "CQ clusters"}
    if records:
        t = _table_from_records(records, "a_ah", "a_wo", "w", 2)
        pooled["weighted_table"] = {"n11": float(t[1, 1]), "n10": float(t[1, 0]),
                                    "n01": float(t[0, 1]), "n00": float(t[0, 0])}
        for name, fn in names.items():
            pooled[name] = _interval_block(cluster_bca(
                records, table_stat(fn, "a_ah", "a_wo", kw="w", k=2), seed=seed, B=B, ties=ties,
                undefined_reason=UNDEFINED_REASONS.get(name, "undefined")))
    out["reweighted_pooled"] = pooled
    return out


# --------------------------------------------------------------------------
# G3-W (DN-7): the washout negative control
# --------------------------------------------------------------------------
def g3w_rule(a_values: list[int], *, n_in_design: int, n_presented: int,
             verdict_allowed: bool = True) -> dict:
    """The ablated-control rule.  A verdict (pass iff at least 22 of the 24 carry A = 0) is given only if
    all 24 ablated controls were presented and labeled; otherwise there is NO verdict and the A = 0
    count over the valid count is reported.  ``verdict_allowed=False`` (the rerun that excludes listed
    controls) never gives a verdict."""
    n_valid = len(a_values)
    n0 = sum(1 for a in a_values if a == 0)
    threshold = G3W_MIN_UNSUPPORTED / G3W_REGISTERED_N
    complete = (n_in_design == G3W_REGISTERED_N and n_presented == G3W_REGISTERED_N
                and n_valid == G3W_REGISTERED_N)
    extra = dict(n_in_design=n_in_design, n_presented=n_presented, n_valid=n_valid,
                 n_unsupported_A0=n0, n_supported_A1=n_valid - n0,
                 A0_over_valid=f"{n0}/{n_valid}",
                 registered_n=G3W_REGISTERED_N, registered_min_unsupported=G3W_MIN_UNSUPPORTED,
                 rule="a verdict only if all 24 ablated controls were presented and labeled: pass iff "
                      "n(A=0) >= 22; otherwise no verdict, the A=0 count over the valid count is given")
    if n_valid:
        lo, hi = clopper_pearson_two_sided(n0, n_valid)
        extra.update(exact_ci95_share_A0=[lo, hi],
                     ci_note="descriptive exact interval for the share; it does not decide G3-W")
    if verdict_allowed and complete:
        ok = n0 >= G3W_MIN_UNSUPPORTED
        return _gate("pass" if ok else "fail", n0 / G3W_REGISTERED_N, threshold,
                     f"{n0}/{G3W_REGISTERED_N} ablated controls were marked unsupported (A=0); "
                     f"need >= {G3W_MIN_UNSUPPORTED}", **extra)
    if not verdict_allowed:
        why = (f"no verdict (descriptive rerun excluding the listed controls): {n0} of {n_valid} valid "
               "ablated controls carry A=0")
    else:
        why = (f"no verdict: the rule needs all {G3W_REGISTERED_N} ablated controls presented and "
               f"labeled (design {n_in_design}, presented {n_presented}, valid {n_valid}); "
               f"{n0} of {n_valid} valid ablated controls carry A=0")
    return _gate("not_computable", None, threshold, why, **extra)


def _preserved_block(a_values: list[int], n_in_design: int, n_presented: int) -> dict:
    n = len(a_values)
    n1 = sum(1 for a in a_values if a == 1)
    out = {"descriptive_only": True, "n_in_design": n_in_design, "n_presented": n_presented,
           "n_valid": n, "n_supported_A1": n1, "n_unsupported_A0": n - n1,
           "A1_over_valid": f"{n1}/{n}"}
    if n:
        lo, hi = clopper_pearson_two_sided(n1, n)
        out.update(share_A1=n1 / n, exact_ci95_share_A1=[lo, hi])
    return out


def g3_w(controls: list[ControlCell], *, listed_exclusions=()) -> dict:
    """G3-W on the washout controls (DN-7).  ``listed_exclusions`` are control ids (source or washout
    ids) seen earlier; they enter only the rerun, which never gives a verdict."""
    abl = [c for c in controls if c.kind == "ablated_control"]
    pre = [c for c in controls if c.kind == "preserved_control"]
    reasons: dict[str, int] = {}
    for c in controls:
        if c.excluded_reason is not None:
            reasons[c.excluded_reason] = reasons.get(c.excluded_reason, 0) + 1
    primary_rule = g3w_rule([c.a for c in abl if c.valid], n_in_design=len(abl),
                            n_presented=sum(c.presented for c in abl))
    out = {
        "name": "G3-W: ablated-control negative check in the washout (PREREG sec.12.3 DN-7)",
        "ablated": {**primary_rule,
                    "n_not_presented_by_design": sum(not c.presented for c in abl),
                    "n_presented_not_labeled": sum(c.presented and c.a is None for c in abl)},
        "preserved": _preserved_block([c.a for c in pre if c.valid], len(pre),
                                      sum(c.presented for c in pre)),
        "excluded_by_design_reasons": dict(sorted(reasons.items())),
        "reported_apart_from": "G2 (controls are never among the 72 primary cells) and from the AH-pass G3",
    }
    listed = {str(x) for x in listed_exclusions}
    if listed:
        ids: dict[str, ControlCell] = {}
        for c in controls:
            ids.setdefault(c.source_cell_id, c)
            ids.setdefault(c.cell_id, c)
        unknown = sorted(x for x in listed if x not in ids)
        if unknown:
            raise ValueError(f"{len(unknown)} listed control id(s) match no control row of the design "
                             f"(e.g. {unknown[:3]}); a list that matches nothing would silently "
                             "reproduce the unrestricted rule")
        matched = {ids[x].cell_id for x in listed}
        abl_v = [c for c in abl if c.valid and c.cell_id not in matched]
        pre_v = [c for c in pre if c.valid and c.cell_id not in matched]
        out["sensitivity_excluding_listed_controls"] = {
            "n_listed": len(listed),
            "n_listed_matched_ablated": sum(c.cell_id in matched for c in abl),
            "n_listed_matched_preserved": sum(c.cell_id in matched for c in pre),
            "n_listed_not_presented_anyway": sum(c.cell_id in matched and not c.presented
                                                 for c in controls),
            "ablated": g3w_rule([c.a for c in abl_v], n_in_design=len(abl),
                                n_presented=sum(c.presented and c.cell_id not in matched for c in abl),
                                verdict_allowed=False),
            "preserved": _preserved_block([c.a for c in pre_v], len(pre),
                                          sum(c.presented and c.cell_id not in matched for c in pre)),
        }
    return out


# --------------------------------------------------------------------------
# dwell check (G7-style) and sessions
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class SessionRecord:
    pid: str | None
    session_id: str | None
    start: datetime.datetime | None
    end: datetime.datetime | None
    saved: int | None
    sitting_id: str | None = None


AI_USE_PREFIX = "AI_USE "
_SITTING_ID = re.compile(r"\bsitting_id=(\S+)")
_SESSION_START = re.compile(r"^SESSION start=(\S+) pid=(\S+) session_id=(\S+)")
_SESSION_END = re.compile(r"^SESSION end=(\S+) pid=(\S+) saved=(\d+)")


def load_session_log(path: Path) -> tuple[list[SessionRecord], dict]:
    """Parse label_assist's ``session_log.txt``.  An end line closes the latest open start with the
    same pid.  Unparseable lines are counted, never guessed."""
    if not path.is_file():
        raise ValueError(f"no session log at {path}")
    raw = path.read_bytes()
    starts: list[dict] = []
    n_edit = n_other = n_orphan_end = n_ai = 0
    for line in raw.decode("utf-8").split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(AI_USE_PREFIX):
            n_ai += 1                             # parsed by ``load_ai_use_reports``
            continue
        m = _SESSION_START.match(line)
        if m:
            sit = _SITTING_ID.search(line)
            starts.append({"pid": m.group(2), "session_id": m.group(3), "start": _parse_utc(m.group(1)),
                           "sitting_id": sit.group(1) if sit else None,
                           "end": None, "saved": None, "open": True})
            continue
        m = _SESSION_END.match(line)
        if m:
            open_ = [s for s in starts if s["open"] and s["pid"] == m.group(2)]
            if open_:
                open_[-1].update(end=_parse_utc(m.group(1)), saved=int(m.group(3)), open=False)
            else:
                n_orphan_end += 1
            continue
        if line.startswith("EDIT "):
            n_edit += 1
        else:
            n_other += 1
    records = [SessionRecord(s["pid"], s["session_id"], s["start"], s["end"], s["saved"], s["sitting_id"])
               for s in starts]
    return records, {"sha256": hashlib.sha256(raw).hexdigest(), "n_session_starts": len(starts),
                     "n_session_starts_with_sitting_id": sum(1 for s in starts if s["sitting_id"]),
                     "n_edit_lines": n_edit, "n_ai_use_lines": n_ai, "n_unparsed_lines": n_other,
                     "n_end_lines_without_start": n_orphan_end,
                     "n_starts_without_end": sum(1 for s in starts if s["open"])}


def _iso(ts) -> str | None:
    return ts.isoformat() if ts is not None else None


def _dwell_basis_used(counts: dict) -> str:
    a, b = counts["dwell_ms"], counts["elapsed_s"]
    return "mixed" if a and b else ("dwell_ms" if a else ("elapsed_s" if b else "none"))


def dwell_stats(cell_ids, audit, extras: AuditExtras | None = None) -> dict:
    """Share under 20 s, median and IQR of the per-cell TOTAL dwell: the sum over all saves of the cell of
    each save's dwell.  A save's dwell is ``dwell_ms`` / 1000 when its audit line has a usable ``dwell_ms``
    (packet mode: the client's performance.now() delta in integer ms, PREREG sec.13.1 (9)), else
    ``elapsed_s`` (AH mode: server minus client wall clock, as ``analyze_holdout._g7`` (c)); the output says
    which basis was used.  A cell with no audit record, or with a save that has neither value and whose
    known part is still under 20 s, has unknown dwell: it is kept and widens the share bounds.  No cell is
    dropped."""
    ids = sorted(set(cell_ids))
    n = len(ids)
    extras = extras or NO_AUDIT_EXTRAS
    out: dict = {"n_cells": n, "fast_share_limit": DWELL_FAST_SHARE_LIMIT,
                 "fast_threshold_s": DWELL_FAST_SECONDS, "cells_dropped": 0,
                 "fast_share_rule": "share of cells under 20 s must be strictly below 3% (PREREG L349)",
                 "basis": "total dwell per cell = sum over its saves of dwell_ms/1000 where a save has "
                          "dwell_ms (packet mode), else elapsed_s (AH mode)"}
    if audit is None or n == 0:
        out.update(status="not_computable",
                   reason="no --audit: dwell cannot be computed" if audit is None else "no cells")
        return out
    n_fast = n_known_slow = n_unknown = n_no_record = 0
    totals: list[float] = []
    by_basis = {"dwell_ms": 0, "elapsed_s": 0, "none": 0}
    for cid in ids:
        recs = audit.saves.get(cid, ())
        if not recs:
            n_no_record += 1
            n_unknown += 1
            continue
        values: list[float] = []
        for r in recs:
            ms = extras.dwell_ms.get(r.seq)
            if ms is not None:
                values.append(ms / 1000.0)
                by_basis["dwell_ms"] += 1
            elif r.elapsed_s is not None:
                values.append(float(r.elapsed_s))
                by_basis["elapsed_s"] += 1
            else:
                by_basis["none"] += 1
        total = float(sum(values))
        if len(values) == len(recs):
            totals.append(total)
            if total < DWELL_FAST_SECONDS:
                n_fast += 1
            else:
                n_known_slow += 1
        elif total >= DWELL_FAST_SECONDS:
            n_known_slow += 1
        else:
            n_unknown += 1
    lower = n_fast / n
    upper = (n_fast + n_unknown) / n
    meets = True if upper < DWELL_FAST_SHARE_LIMIT else (False if lower >= DWELL_FAST_SHARE_LIMIT else None)
    out.update(status="computed", n_under_20s=n_fast, n_unknown_dwell=n_unknown,
               n_without_audit_record=n_no_record, n_20s_or_more=n_known_slow,
               share_under_20s=(n_fast / n if n_unknown == 0 else None),
               share_under_20s_bounds=[lower, upper], meets_fast_share_limit=meets,
               n_cells_with_known_total=len(totals), basis_used=_dwell_basis_used(by_basis),
               saves_by_basis=by_basis, n_dwell_ms_unusable=extras.n_dwell_ms_unusable)
    if totals:
        q1, med, q3 = (float(v) for v in np.percentile(np.asarray(totals), [25, 50, 75]))
        out.update(median_s=med, q1_s=q1, q3_s=q3, iqr_s=q3 - q1,
                   quantile_method="numpy linear interpolation over cells with a fully known total")
    else:
        out.update(median_s=None, q1_s=None, q3_s=None, iqr_s=None)
    return out


def session_summary(cell_ids, audit, log_records: list[SessionRecord] | None,
                    extras: AuditExtras | None = None) -> dict:
    """Number of sessions and their start and end times (UTC).  ``n_sessions`` counts the SESSION start
    lines of the log when one is given (PREREG sec.13.1 (9)), else the sessions that saved one of
    ``cell_ids``; both counts are always shown, and so is the number of sittings (``sitting_id``) when the
    audit lines carry one."""
    ids = set(cell_ids)
    by_sid: dict[str, dict] = {}
    sittings: set[str] = set()
    if audit is not None:
        for cid in ids:
            for rec in audit.saves.get(cid, ()):
                sid = rec.session_id or "(no session_id)"
                d = by_sid.setdefault(sid, {"n_saves": 0, "first": rec.ts, "last": rec.ts})
                d["n_saves"] += 1
                d["first"], d["last"] = min(d["first"], rec.ts), max(d["last"], rec.ts)
                if extras is not None and rec.seq in extras.sitting_ids:
                    sittings.add(extras.sitting_ids[rec.seq])
    sessions: list[dict] = []
    seen: set[str] = set()
    for rec in log_records or []:
        d = by_sid.get(rec.session_id or "")
        if rec.session_id:
            seen.add(rec.session_id)
        sessions.append({"session_id": rec.session_id, "sitting_id": rec.sitting_id, "in_session_log": True,
                         "start_utc": _iso(rec.start), "end_utc": _iso(rec.end),
                         "saved_per_log_end_line": rec.saved,
                         "n_saves_on_these_cells": d["n_saves"] if d else 0,
                         "first_save_utc": _iso(d["first"]) if d else None,
                         "last_save_utc": _iso(d["last"]) if d else None})
    for sid, d in sorted(by_sid.items()):
        if sid not in seen:
            sessions.append({"session_id": sid, "sitting_id": None, "in_session_log": False,
                             "start_utc": None, "end_utc": None, "saved_per_log_end_line": None,
                             "n_saves_on_these_cells": d["n_saves"], "first_save_utc": _iso(d["first"]),
                             "last_save_utc": _iso(d["last"])})
    starts = [r.start for r in (log_records or []) if r.start is not None]
    ends = [r.end for r in (log_records or []) if r.end is not None]
    n_log = len(log_records) if log_records is not None else None
    log_sittings = {r.sitting_id for r in (log_records or []) if r.sitting_id}
    return {
        "n_sessions": n_log if n_log is not None else len(by_sid),
        "n_sessions_basis": ("SESSION start lines of the session log" if n_log is not None
                             else "distinct session_id values among the audit saves of these cells"),
        "n_session_starts_in_log": n_log, "n_sessions_with_saves": len(by_sid),
        "n_sittings_with_saves": len(sittings) if (extras is not None and extras.sitting_ids) else None,
        "n_sittings_in_log": len(log_sittings) if log_sittings else None,
        "first_session_start_utc": _iso(min(starts)) if starts else None,
        "last_session_end_utc": _iso(max(ends)) if ends else None,
        "first_save_utc": _iso(min(d["first"] for d in by_sid.values())) if by_sid else None,
        "last_save_utc": _iso(max(d["last"] for d in by_sid.values())) if by_sid else None,
        "sessions": sessions,
        "times_are": "UTC, ISO-8601; log times come from the session log, save times from the audit",
    }


def dwell_check(primary_ids, audit, log_records=None, *, other_ids=(),
                extras: AuditExtras | None = None) -> dict:
    """The G7-style dwell check of DN-5 / sec.12.4 / sec.13.1 (9): per primary cell the total dwell over all
    its saves, share under 20 s against the 3% limit, median and IQR (linear quartiles), number of
    sessions (SESSION start lines), session start and end.  Descriptive; it never removes a cell and never
    changes G2.  ``other_ids`` (the presented controls) get their own block.  ``extras`` supplies
    ``dwell_ms`` and ``sitting_id`` from the audit lines."""
    out = {"purpose": "G7-style dwell check (PREREG sec.12.3 DN-5, sec.12.4, sec.13.1 (9)): reported with "
                      "the result, no cell is dropped, no minimum dwell was enforced",
           "primary_cells": dwell_stats(primary_ids, audit, extras)}
    if other_ids:
        out["all_presented_rows"] = dwell_stats(list(primary_ids) + list(other_ids), audit, extras)
    out["sessions"] = session_summary(list(primary_ids) + list(other_ids), audit, log_records, extras)
    return out


def washout_gap_report(audit, design_ids, *, ah_last_save: str = AH_LAST_SAVE,
                       source: str = "registered (PREREG sec.12.3 DN-5, sec.13.1 (10))") -> dict:
    """Days from the AH pass's last save to the first save of any washout row (the primary cells and the
    controls of the design), read from the washout audit.  Reported in the G2 output with the 21-day
    minimum and the 28-day target of DN-5; a gap under the minimum is reported with its actual length."""
    ah_ts = _parse_utc(ah_last_save)
    if ah_ts is None:
        raise ValueError(f"ah_last_save must be ISO-8601 with an explicit UTC offset, got {ah_last_save!r}")
    out: dict = {"ah_last_save": ah_last_save, "ah_last_save_utc": _iso(ah_ts), "ah_last_save_source": source,
                 "registered_minimum_days": WASHOUT_MIN_GAP_DAYS, "target_days": WASHOUT_TARGET_GAP_DAYS,
                 "basis": "days (86,400 s) from the AH pass's last save to the first save of any washout row "
                          "in the audit"}
    if audit is None:
        out.update(status="not_computable", reason="no --audit: the first washout save is not known")
        return out
    firsts = [rec.ts for cid in sorted(set(design_ids)) for rec in audit.saves.get(cid, ())]
    if not firsts:
        out.update(status="not_computable", reason="the audit holds no save of any washout row")
        return out
    first = min(firsts)
    gap = (first - ah_ts).total_seconds() / 86400.0
    out.update(status="computed", first_washout_save_utc=_iso(first), gap_days=gap,
               meets_registered_minimum=bool(gap >= WASHOUT_MIN_GAP_DAYS),
               meets_target=bool(gap >= WASHOUT_TARGET_GAP_DAYS))
    return out


# --------------------------------------------------------------------------
# AI use of the labelers: the per-row tick and the report of the sitting
# --------------------------------------------------------------------------
def parse_ai_use(raw, what: str = "ai_used") -> str:
    """yes | no (a JSON boolean or the strings yes/no/true/false); anything else is an error."""
    if isinstance(raw, bool):
        return "yes" if raw else "no"
    text = str(raw).strip().lower()
    if text in ("yes", "true"):
        return "yes"
    if text in ("no", "false"):
        return "no"
    raise ValueError(f"{what} must be yes or no (or true/false), got {raw!r}")


def normalize_tool(raw) -> str:
    """A tool name as one comparable string: NFKC, whitespace collapsed, the ends trimmed of space and
    ``. , ; : / |``, case-folded.  Empty means the report named no tool.  A field that names several tools
    is one string (it is not split)."""
    text = unicodedata.normalize("NFKC", "" if raw is None else str(raw))
    return re.sub(r"\s+", " ", text).strip(" .,;:/|").casefold()


@dataclass(frozen=True)
class AiUseReports:
    """The AI-use self-reports (``AI_USE {json}`` lines) of a label_assist --packet session log."""
    by_session: dict[str, dict]     # session_id -> the last report line of that session (the fallback join)
    by_sitting: dict[str, dict]     # sitting_id -> the last report line of that sitting (the join)
    has_sitting_ids: bool           # at least one report line carries a sitting_id
    meta: dict


NO_AI_REPORTS = AiUseReports({}, {}, False, {"n_ai_use_lines": 0, "n_unusable": 0, "n_superseded": 0,
                                             "n_lines_with_sitting_id": 0})


def load_ai_use_reports(path: Path) -> AiUseReports:
    """The AI use the labeler declared at the end of each sitting, from the ``AI_USE {json}`` lines of a
    label_assist session log (PREREG D20, sec.13.1 (7)): ``used`` yes | no | not recorded, the tool (kept
    normalized: ``normalize_tool``), ``approx_cells``, and the ``sitting_id`` and ``session_id`` the line
    belongs to.  Reports are append-only: one line per sitting.  A second line for the same key (the
    sitting_id, else the session_id of an older log) supersedes the first and is counted.  A line that is
    not valid JSON, has no session_id or has any other ``used`` value is counted as unusable, never guessed."""
    if not path.is_file():
        raise ValueError(f"no session log at {path}")
    by_session: dict[str, dict] = {}
    by_sitting: dict[str, dict] = {}
    seen: set[tuple[str, str]] = set()
    n_lines = n_unusable = n_superseded = n_with_sitting = 0
    for line in path.read_bytes().decode("utf-8").split("\n"):
        line = line.strip()
        if not line.startswith(AI_USE_PREFIX):
            continue
        n_lines += 1
        try:
            entry = json.loads(line[len(AI_USE_PREFIX):])
        except ValueError:
            n_unusable += 1
            continue
        sid = entry.get("session_id") if isinstance(entry, dict) else None
        used = entry.get("used") if isinstance(entry, dict) else None
        if not isinstance(sid, str) or not sid or used not in AI_USE_GROUPS:
            n_unusable += 1
            continue
        raw_sit = entry.get("sitting_id")
        sit = str(raw_sit) if isinstance(raw_sit, (str, int)) and not isinstance(raw_sit, bool) and str(raw_sit) else None
        approx = entry.get("approx_cells")
        report = {"used": used,
                  "approx_cells": approx if isinstance(approx, int) and not isinstance(approx, bool) else None,
                  "how": str(entry.get("how") or ""), "tool": normalize_tool(entry.get("tool")),
                  "session_id": sid, "sitting_id": sit}
        key = ("sitting", sit) if sit is not None else ("session", sid)
        if key in seen:
            n_superseded += 1
        seen.add(key)
        if sit is not None:
            n_with_sitting += 1
            by_sitting[sit] = report
        by_session[sid] = report
    return AiUseReports(by_session, by_sitting, n_with_sitting > 0,
                        {"n_ai_use_lines": n_lines, "n_unusable": n_unusable, "n_superseded": n_superseded,
                         "n_lines_with_sitting_id": n_with_sitting})


@dataclass(frozen=True)
class AuditExtras:
    """What an audit save line carries beyond the registered loader's fields, keyed by the line index
    (``AuditSave.seq``): the per-row AI tick, the sitting_id and the client dwell in milliseconds."""
    ai_flags: dict[int, str]
    sitting_ids: dict[int, str]
    dwell_ms: dict[int, int]
    n_dwell_ms_unusable: int


NO_AUDIT_EXTRAS = AuditExtras({}, {}, {}, 0)


def load_audit_extras(path: Path) -> AuditExtras:
    """``ai_used`` (label_assist --packet: true for a ticked row, null for an unticked one, which means not
    recorded and is skipped), ``sitting_id`` and ``dwell_ms`` of every save line.  ``dwell_ms`` must be a
    non-negative integer; anything else is counted as unusable and the save falls back to ``elapsed_s``.
    The index is that of ``load_label_audit`` (``AuditSave.seq``)."""
    if not path.is_file():
        raise ValueError(f"no label audit at {path}")
    flags: dict[int, str] = {}
    sittings: dict[int, str] = {}
    dwell: dict[int, int] = {}
    n_bad = 0
    for seq, line in enumerate(path.read_bytes().decode("utf-8").split("\n")):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue                          # counted by load_label_audit, not guessed here
        if not isinstance(rec, dict) or "cell_id" not in rec or "A" not in rec:
            continue
        if rec.get("ai_used") not in (None, ""):
            flags[seq] = parse_ai_use(rec["ai_used"], f"{path} line {seq + 1} ai_used")
        sit = rec.get("sitting_id")
        if isinstance(sit, (str, int)) and not isinstance(sit, bool) and str(sit):
            sittings[seq] = str(sit)
        ms = rec.get("dwell_ms")
        if ms is not None:
            if isinstance(ms, int) and not isinstance(ms, bool) and ms >= 0:
                dwell[seq] = ms
            else:
                n_bad += 1
    return AuditExtras(flags, sittings, dwell, n_bad)


def load_audit_ai_flags(path: Path) -> dict[int, str]:
    """The per-save AI ticks of an audit .jsonl (see ``load_audit_extras``)."""
    return load_audit_extras(path).ai_flags


def load_sheet_ai_flags(path: Path) -> dict[str, str] | None:
    """cell_id -> yes | no from the optional ``ai_used`` column of a label sheet (label_assist --packet:
    "yes" = ticked, blank = not recorded and skipped).  None when the sheet has no such column."""
    rows = read_table(path)
    if not rows or "ai_used" not in rows[0]:
        return None
    out: dict[str, str] = {}
    for n, row in enumerate(rows, start=2):
        value = row.get("ai_used", "")
        if value:
            out[row.get("cell_id", "")] = parse_ai_use(value, f"{path} row {n} ai_used")
    return out


@dataclass(frozen=True)
class AiUse:
    """One cell's AI-use classification (PREREG sec.13.1 (7)).  ``group`` is the PRIMARY stratum, "the
    sitting reported AI use": yes = the labeler ticked the cell, or the cell is unticked but the report of
    its sitting says yes; no = unticked and the sitting reported no; not recorded = anything else.  Only a
    ``ticked`` cell may be described as a cell that used AI; the other cells of the yes group are cells of
    sittings that reported AI use.  ``tool`` (yes cells only) is the normalized tool of the sitting's report."""
    group: str
    ticked: bool
    tool: str | None
    source: str      # tick | sitting_report | session_report | none


NOT_RECORDED_AI = AiUse("not recorded", False, None, "none")

GROUP_MEANING = {
    "yes": "cells the labeler ticked, and unticked cells of sittings that reported AI use (the latter are "
           "cells of sittings that reported it, not cells shown to have used it)",
    "no": "unticked cells of sittings that reported no AI use",
    "not recorded": "unticked cells of sittings with no usable report, and cells with no audit record",
}
TICK_ONLY_MEANING = {
    "ticked": "cells the labeler ticked as AI use",
    "not ticked": "every other cell, whatever its sitting reported",
}


def classify_ai_use(shown_ids: dict[str, str], audit, extras: AuditExtras | None = None,
                    reports: AiUseReports | None = None,
                    sheet_flags: dict[str, str] | None = None) -> tuple[dict[str, AiUse], dict]:
    """cell key -> ``AiUse``, and the counts (never a cell id).  ``shown_ids`` maps the cell key to the id
    used in the audit and the sheet.

    Tick: the ``ai_used`` tick on the cell's LAST audit save (``extras``) or in the sheet's ``ai_used``
    column (``sheet_flags``, None when the sheet has no such column); a tick in either source counts, and a
    cell whose two sources disagree is counted.  Report: the report of the sitting of that last save,
    joined on ``sitting_id`` when the audit line and the reports carry one, else on ``session_id`` (the older
    rule).  Primary group: ticked -> yes; else the report's yes/no; else not recorded.  A report that says
    not recorded is no information.  The tick-only counts are the sensitivity."""
    extras = extras or NO_AUDIT_EXTRAS
    reports = reports or NO_AI_REPORTS
    out: dict[str, AiUse] = {}
    by_source = {"tick": 0, "sitting_report": 0, "session_report": 0, "none": 0}
    join = {"by_sitting_id": 0, "by_session_id": 0, "no_report": 0}
    conflicts = ticks_in_no = explicit_no = 0
    for key, audit_id in shown_ids.items():
        recs = audit.saves.get(audit_id, ()) if audit is not None else ()
        last = recs[-1] if recs else None
        a_val = extras.ai_flags.get(last.seq) if last is not None else None
        s_val = sheet_flags.get(audit_id) if sheet_flags is not None else None
        a_tick, s_tick = a_val == "yes", s_val == "yes"
        explicit_no += (a_val == "no") + (s_val == "no")
        if last is not None and sheet_flags is not None and a_tick != s_tick:
            conflicts += 1
        ticked = a_tick or s_tick
        rep, kind = None, None
        if last is not None:
            sit = extras.sitting_ids.get(last.seq)
            if sit is not None and reports.has_sitting_ids:
                rep, kind = reports.by_sitting.get(sit), "sitting_id"
            else:
                rep, kind = reports.by_session.get(last.session_id), "session_id"
        if rep is None:
            join["no_report"] += 1
        else:
            join["by_sitting_id" if kind == "sitting_id" else "by_session_id"] += 1
        used = rep["used"] if rep is not None else None
        if ticked:
            group, source = "yes", "tick"
            ticks_in_no += used == "no"
        elif used in ("yes", "no"):
            group, source = used, ("sitting_report" if kind == "sitting_id" else "session_report")
        else:
            group, source = "not recorded", "none"
        tool = None
        if group == "yes":
            tool = (rep["tool"] or TOOL_NOT_GIVEN) if used == "yes" else TOOL_NO_YES_REPORT
        out[key] = AiUse(group, ticked, tool, source)
        by_source[source] += 1
    tool_counts: dict[str, int] = {}
    for item in out.values():
        if item.group == "yes":
            tool_counts[item.tool] = tool_counts.get(item.tool, 0) + 1
    n_ticked = sum(item.ticked for item in out.values())
    return out, {
        "stratification": "primary: the sitting reported AI use (a ticked cell counts as yes); sensitivity: "
                          "the labeler's tick only (PREREG sec.13.1 (7))",
        "by_group": {g: sum(1 for item in out.values() if item.group == g) for g in AI_USE_GROUPS},
        "group_meaning": dict(GROUP_MEANING),
        "by_source": by_source,
        "tick_only": {"by_group": {"ticked": n_ticked, "not ticked": len(out) - n_ticked},
                      "meaning": dict(TICK_ONLY_MEANING)},
        "tools_among_yes_cells": [{"tool": t, "n_cells": n} for t, n in sorted(tool_counts.items())],
        "join": {**join, "key": "sitting_id when the cell's last audit save and the reports carry one, "
                                "else session_id"},
        "sheet_column_present": sheet_flags is not None,
        "n_sheet_audit_conflicts": conflicts,
        "n_ticks_in_sittings_reporting_no": ticks_in_no,
        "n_explicit_no_flags": explicit_no,
        "rule": "yes = ticked (the sheet's ai_used column or the tick on the last audit save) or unticked in a "
                "sitting whose report says yes; no = unticked in a sitting whose report says no; otherwise "
                "not recorded",
    }


def ai_use_session_summary(reports: AiUseReports) -> dict:
    """Counts of the AI-use reports: by declared use, the labeler's own approximate cell counts of the
    yes reports (reported, never used to classify), the tools they named, and the lines that were
    superseded or unusable."""
    unique = list(reports.by_sitting.values()) + [r for r in reports.by_session.values()
                                                  if r["sitting_id"] is None]
    yes_reports = [r for r in unique if r["used"] == "yes"]
    tools: dict[str, int] = {}
    for r in yes_reports:
        tools[r["tool"] or TOOL_NOT_GIVEN] = tools.get(r["tool"] or TOOL_NOT_GIVEN, 0) + 1
    return {"n_reports": len(unique), "n_reports_with_sitting_id": len(reports.by_sitting),
            "by_declared_use": {g: sum(1 for r in unique if r["used"] == g) for g in AI_USE_GROUPS},
            "tools_in_yes_reports": [{"tool": t, "n_reports": n} for t, n in sorted(tools.items())],
            "n_yes_reports_without_approx_cells": sum(1 for r in yes_reports if r["approx_cells"] is None),
            "approx_cells_declared_in_yes_reports": sum(r["approx_cells"] for r in yes_reports
                                                        if r["approx_cells"] is not None),
            **reports.meta,
            "note": "a yes report puts the unticked cells of its sitting into the yes group, however few "
                    "cells its approx_cells names; approx_cells is the labeler's own count and is not used"}


# --------------------------------------------------------------------------
# washout results by AI use (PREREG sec.12.1 D20): descriptive, never a gate
# --------------------------------------------------------------------------
D20_TEXT = ("PREREG sec.12.1 D20: the washout results are reported by AI-tool use (yes / no) and by tool; "
            "sessions and cells without a record are counted apart as 'not recorded'")
D20_LABEL = "descriptive; not a gate"
D20_MIN_CLUSTERS = 2        # the registered cluster resampling needs two CQ clusters; no larger minimum is registered
D20_NOTES = [
    "descriptive; not a gate: nothing here is an input to G2, G3-W or any other decision, no difference between "
    "groups is tested and no adjustment for multiplicity is made",
    "the groups partition the primary cells. yes = the cells the labeler ticked and the unticked cells of "
    "sittings that reported AI use (only a ticked cell is one the labeler marked as AI use); no = the unticked "
    "cells of sittings that reported no AI use; not recorded = anything else, which is not the same as no (D20). "
    "The tick-only sensitivity splits the same cells by the tick alone. A tool is the normalized tool of the "
    "sitting's report",
    "weighted QWK: the table weighted by the design weights 1/pi_i of the 72-cell sample, restricted to the group "
    "(a domain estimate: the weights are not recalibrated to the group's share of the 188-cell frame); "
    "unweighted QWK: the plain QWK of the group's cells",
    "intervals: 95% BCa over the group's own CQ clusters (whole clusters, weights fixed per cell). A resample on "
    "which the QWK is undefined (E = 0) is excluded and counted (the sec.12.4 rule); it is NOT set to 0, which is "
    "the rule of G2 for the gate alone. An undefined QWK is reported as not computable, with the group's n",
    "no minimum group size beyond the method's: a group is not computable, and no result is shown for it, when it "
    "has no cell, covers fewer than two CQ clusters (the cluster resampling needs two) or has an undefined QWK "
    "(E = 0); an interval is also withheld when the QWK is undefined on more than half of the resamples. A "
    "computed result over a handful of clusters is unreliable and is to be read as such",
    "binary A agreement between the passes: per design stratum and as a weighted pool, no unweighted pool "
    "(sec.13.1 (6)), rows = the AH pass, columns = the washout pass",
]


def _not_computable(reason: str, n_cells: int, n_clusters: int) -> dict:
    return {"status": "not_computable", "reason": reason, "n_cells": n_cells, "n_clusters": n_clusters}


def _ai_group_block(cells: list[WashoutCell], *, seed: int, B: int | None, ties: str) -> dict:
    """The washout quantities of ONE AI-use group; descriptive, never a gate.

    ``n_cells`` and ``n_clusters`` (the CQ clusters the cells cover: the resampling unit).  ``G2_quantity``: the
    QWK of rater_L1 between the AH pass and the washout pass, WEIGHTED (the table weighted by 1/pi_i, the
    estimator of pooled G2, restricted to the group's cells) and UNWEIGHTED, each with a 95% BCa interval that
    resamples the group's own CQ clusters (whole clusters, weights fixed).  A resample on which the QWK is
    undefined (E = 0) is EXCLUDED and counted (the sec.12.4 rule); the E = 0 -> 0 rule belongs to the gate
    alone.  ``A_agreement_between_passes``: the binary A agreement per design stratum and as a weighted pool,
    exactly as in the main block (no unweighted pool).

    A group is ``not_computable``, with its n and the reason and no result, when it has no cell, covers fewer
    than ``D20_MIN_CLUSTERS`` CQ clusters (the cluster resampling needs two; a one-cell group can even have a
    defined QWK of 0, which says nothing), or, for the QWK, when E = 0."""
    n_cells, n_clusters = len(cells), len({c.cluster_id for c in cells})
    out: dict = {"n_cells": n_cells, "n_clusters": n_clusters}
    if cells:
        weights = [c.w for c in cells]
        out["weights"] = {"sum_of_weights": float(sum(weights)), "kish_n_eff": kish_effective_n(weights)}
    reason = None
    if not cells:
        reason = "no cell in this group"
    elif n_clusters < D20_MIN_CLUSTERS:
        reason = (f"the group covers {n_clusters} CQ cluster: the cluster resampling needs at least "
                  f"{D20_MIN_CLUSTERS}")
    if reason is not None:
        out["G2_quantity"] = _not_computable(reason, n_cells, n_clusters)
        out["A_agreement_between_passes"] = _not_computable(reason, n_cells, n_clusters)
        return out
    records = _records(cells)
    stat_w = table_stat(qwk_from_table, "x", "y", kw="w")
    if stat_w(records) is None:                  # E = 0 (the unweighted QWK is undefined together with it)
        out["G2_quantity"] = _not_computable(UNDEFINED_REASONS["qwk"], n_cells, n_clusters)
    else:
        kw = dict(seed=seed, B=B, ties=ties, undefined_reason=UNDEFINED_REASONS["qwk"])     # excluded and counted
        quantity: dict = {}
        for name, stat in (("qwk_weighted", stat_w), ("qwk_unweighted", table_stat(qwk_from_table, "x", "y"))):
            entry = _interval_block(cluster_bca(records, stat, **kw))
            entry["qwk"] = entry.pop("estimate")
            quantity[name] = entry
        out["G2_quantity"] = {"status": "computed", "n_cells": n_cells, "n_clusters": n_clusters, **quantity}
    out["A_agreement_between_passes"] = {"status": "computed",
                                         **a_agreement_between_passes(cells, seed=seed, B=B, ties=ties)}
    return out


def ai_use_stratified_results(cells: list[WashoutCell], ai: dict[str, AiUse] | None, *, seed: int,
                              B: int | None = None, ties: str = DEFAULT_BCA_TIES) -> dict:
    """PREREG sec.12.1 D20: the washout results by AI-tool use and by tool.  Descriptive; none of it is an input
    to G2, G3-W or any other decision.  ``cells``: the primary cells; ``ai``: cell_id -> ``AiUse`` (a cell with no
    entry is "not recorded").  Four partitions of the cells, each group a ``_ai_group_block``:
      by_ai_use                    PRIMARY: yes / no / not recorded (the sitting reported AI use; a ticked cell
                                   counts as yes)
      by_tool_among_yes_cells      the yes cells split by the normalized tool of their sitting's report
      by_ai_use_tick_only          SENSITIVITY: ticked / not ticked (the labeler's tick alone)
      by_tool_among_ticked_cells   the ticked cells split by tool"""
    ai = ai or {}
    kw = dict(seed=seed, B=B, ties=ties)

    def info(c: WashoutCell) -> AiUse:
        return ai.get(c.cell_id, NOT_RECORDED_AI)

    primary = {g: [c for c in cells if info(c).group == g] for g in AI_USE_GROUPS}
    tick = {"ticked": [c for c in cells if info(c).ticked], "not ticked": [c for c in cells if not info(c).ticked]}
    yes_tools: dict[str, list[WashoutCell]] = {}
    ticked_tools: dict[str, list[WashoutCell]] = {}
    for c in cells:
        item = info(c)
        if item.group == "yes":
            yes_tools.setdefault(item.tool or TOOL_NOT_GIVEN, []).append(c)
        if item.ticked:
            ticked_tools.setdefault(item.tool or TOOL_NOT_GIVEN, []).append(c)

    def by_tool(groups: dict[str, list[WashoutCell]]) -> list[dict]:
        return [{"tool": t, "n_cells": len(sub), "block": _ai_group_block(sub, **kw)}
                for t, sub in sorted(groups.items())]

    return {
        "prereg": D20_TEXT, "label": D20_LABEL, "decision_input": False,
        "by_ai_use": {g: _ai_group_block(sub, **kw) for g, sub in primary.items()},
        "by_tool_among_yes_cells": by_tool(yes_tools),
        "by_ai_use_tick_only": {g: _ai_group_block(sub, **kw) for g, sub in tick.items()},
        "by_tool_among_ticked_cells": by_tool(ticked_tools),
        "group_meaning": dict(GROUP_MEANING), "tick_only_meaning": dict(TICK_ONLY_MEANING),
        "quantities": {
            "G2_quantity": "the same-rater QWK of rater_L1 between the AH pass and the washout pass, the quantity "
                           "G2 is computed on, weighted and unweighted; for a group it is descriptive, with no gate",
            "A_agreement_between_passes": "binary A: raw agreement and Cohen kappa, per design stratum and as a "
                                          "weighted pool"},
        "notes": list(D20_NOTES),
    }


# --------------------------------------------------------------------------
# second annotation (sec.12.4, DN-9, DN-10): descriptive, never a gate
# --------------------------------------------------------------------------
def second_annotator_sample(cells: list[dict], *, per_category: int = SECOND_PER_CATEGORY,
                            seed: int = REGISTERED_SEED) -> list[str]:
    """The registered draw (sec.12.4): primary cells only, categories in name order, cell_ids sorted
    inside a category, one ``random.Random(seed)``, ``sample(sorted_ids, 8)`` per category; returns the
    picked ids sorted.  Reads only cell_id, cell_kind and category."""
    pools: dict[str, list[str]] = {}
    for c in cells:
        if _cell_kind(c) == CELL_KIND_PRIMARY:
            category = str(c.get("category", "")).strip()
            if not category:
                raise ValueError(f"primary cell {c.get('cell_id')!r} has no category")
            pools.setdefault(category, []).append(str(c["cell_id"]))
    rng = random.Random(seed)
    picked: list[str] = []
    for cat in sorted(pools):
        pool = sorted(pools[cat])
        if len(pool) < per_category:
            raise ValueError(f"category {cat!r} has {len(pool)} primary cells, fewer than {per_category}")
        picked += rng.sample(pool, per_category)
    return sorted(picked)


def sample_list_bytes(ids) -> bytes:
    return ("\n".join(sorted(ids)) + "\n").encode("utf-8")


@dataclass(frozen=True)
class SecondCell:
    cell_id: str
    cluster_id: str
    category: str
    j: int
    ah_a: int
    ah_l1: int
    s_a: int
    s_l1: int


def _second_records(cells: list[SecondCell]) -> list[dict]:
    return [{"cell_id": c.cell_id, "cluster_id": c.cluster_id, "category": c.category, "J": c.j,
             "j_ge2": int(c.j >= JUDGE_CREDIT_THRESHOLD), "a_ah": c.ah_a, "a_s": c.s_a,
             "l1_ah": c.ah_l1, "l1_s": c.s_l1} for c in sorted(cells, key=lambda c: c.cell_id)]


def _stat_block(records, fn, kx, ky, *, seed, B, ties, name, k) -> dict:
    """One sec.12.4 statistic with its interval.  A statistic that is undefined on a resample (a zero
    denominator, or E = 0 for a QWK) is EXCLUDED from the interval and the number of such resamples is
    reported; no value is substituted (the E = 0 -> 0 rule belongs to G2 alone; PREREG sec.12.4 (i), sec.13.1
    (6)).  An undefined point estimate is reported as undefined."""
    res = cluster_bca(records, table_stat(fn, kx, ky, k=k), seed=seed, B=B, ties=ties,
                      undefined_reason=UNDEFINED_REASONS.get(name, "undefined on these data"))
    return _interval_block(res)


def _table_dict(t) -> dict:
    return {"n11": int(t[1, 1]), "n10": int(t[1, 0]), "n01": int(t[0, 1]), "n00": int(t[0, 0])}


def zero_event_bound_note(n_clusters: int) -> dict:
    """What the cluster-level Clopper-Pearson upper bound is at ZERO events for ``n_clusters``
    clusters, at both levels, and whether it can go below 10% at all."""
    out: dict = {"n_clusters": n_clusters, "limit": PI_UPPER_BOUND_LIMIT}
    cannot = []
    for label, alpha in (("one_sided_97_5", 0.025), ("one_sided_95", 0.05)):
        bound = clopper_pearson_upper(0, n_clusters, alpha)
        out[f"zero_event_upper_bound_{label}"] = bound
        out[f"cannot_go_below_10pct_even_with_zero_events_{label}"] = bool(bound > PI_UPPER_BOUND_LIMIT)
        if bound > PI_UPPER_BOUND_LIMIT:
            cannot.append(f"{label.replace('one_sided_', '').replace('_', '.')}%")
    if len(cannot) == 2:
        out["note"] = (f"With {n_clusters} clusters the upper bound cannot go below 10% even with zero "
                       f"events (zero-event bounds {out['zero_event_upper_bound_one_sided_97_5']:.1%} at "
                       f"97.5% and {out['zero_event_upper_bound_one_sided_95']:.1%} at 95%). "
                       "Not a G1 decision.")
    elif cannot:
        out["note"] = (f"With {n_clusters} clusters the upper bound cannot go below 10% even with zero "
                       f"events at the {cannot[0]} level ({out['zero_event_upper_bound_one_sided_97_5']:.1%}"
                       f" at 97.5%); at 95% the zero-event bound is "
                       f"{out['zero_event_upper_bound_one_sided_95']:.1%}. Not a G1 decision.")
    else:
        out["note"] = (f"With {n_clusters} clusters the zero-event bound is "
                       f"{out['zero_event_upper_bound_one_sided_97_5']:.1%} at 97.5% and "
                       f"{out['zero_event_upper_bound_one_sided_95']:.1%} at 95%, so a bound below 10% is "
                       "reachable at both levels. Not a G1 decision.")
    return out


def _pi_block(cells: list[dict], *, seed: int, B: int | None, ties: str) -> dict:
    """pi-hat for one label set, with the cluster-level Clopper-Pearson upper bounds at both levels."""
    B = BOOTSTRAP_RESAMPLES if B is None else B
    rate = silent_over_credit_rate(cells, B=B, seed=seed, ties=ties)
    events, n_clusters = silent_over_credit(cells)
    keep = ("events", "n_cells", "pi_hat", "n_clusters", "clusters_with_event", "ci_lo", "ci_hi",
            "ci_method", "ci_reason", "resamples")
    cp = {"events_clusters": events, "n_clusters": n_clusters,
          "definition": "an event cluster has at least one cell with J >= 2 and A = 0; n is the number "
                        "of clusters the cells cover; exact one-sided binomial upper bound"}
    for label, alpha in (("one_sided_97_5", 0.025), ("one_sided_95", 0.05)):
        cp[label] = {"alpha": alpha, "upper_bound": clopper_pearson_upper(events, n_clusters, alpha)}
    cp["zero_event_note"] = zero_event_bound_note(n_clusters)
    out = {**{k: rate[k] for k in keep if k in rate}, "ci_level": CI_LEVEL,
           "cluster_level_clopper_pearson": cp}
    if str(out.get("ci_reason", "")).startswith("zero observed events"):
        out["ci_reason"] = ("zero observed events: a bootstrap cannot resample an event it has never "
                            "seen (PREREG sec.4 item 3); see the cluster-level Clopper-Pearson bounds")
    return out


def _judge_block(rec: list[dict], *, seed: int, B: int | None, ties: str) -> dict:
    """Judge J against the second annotator on a set of records: QWK(J, rater_L1), exact agreement,
    and the Cohen kappa of 1[J >= 2] against A."""
    out: dict = {"n_cells": len(rec), "n_clusters": len({r["cluster_id"] for r in rec})}
    if not rec:
        return out
    kw = dict(seed=seed, B=B, ties=ties)
    tab_l = _table_from_records(rec, "J", "l1_s", None, L1_LEVELS)
    tab_b = _table_from_records(rec, "j_ge2", "a_s", None, 2)
    out["L1_scale"] = {
        "what": "judge J against the second annotator's rater_L1 (0..3)",
        "qwk": _stat_block(rec, qwk_from_table, "J", "l1_s", name="qwk", k=L1_LEVELS, **kw),
        "exact_agreement": _stat_block(rec, exact_agreement_from_table, "J", "l1_s",
                                       name="exact_agreement", k=L1_LEVELS, **kw),
        "confusion_table_judge_rows_second_cols": tab_l.astype(int).tolist()}
    out["binary_scale"] = {
        "what": f"1[J >= {JUDGE_CREDIT_THRESHOLD}] against the second annotator's A",
        "table": _table_dict(tab_b),
        "cohen_kappa": _stat_block(rec, cohen_kappa_from_table, "j_ge2", "a_s", name="cohen_kappa",
                                   k=2, **kw)}
    return out


def second_annotation_block(cells: list[SecondCell], *, seed: int, B: int | None = None,
                            ties: str = DEFAULT_BCA_TIES) -> dict:
    """All second-annotation statistics for one set of cells (DN-10): descriptive, never a gate."""
    rec = _second_records(cells)
    out: dict = {"n_cells": len(cells), "n_clusters": len({c.cluster_id for c in cells})}
    if not rec:
        return out
    kw = dict(seed=seed, B=B, ties=ties)
    tab_a = confusion_table([r["a_ah"] for r in rec], [r["a_s"] for r in rec], k=2)
    a_block = {"comparison_column": "AH labels (rows); the second annotator's labels are the columns",
               "table": _table_dict(tab_a),
               "ppa_npa_note": "PPA and NPA are agreement rates relative to the AH column; that column "
                               "is LLM-assisted labels, not a gold standard, so they are not accuracy "
                               "rates"}
    for name, fn in BINARY_STATS.items():
        a_block[name] = _stat_block(rec, fn, "a_ah", "a_s", name=name, k=2, **kw)
    tab_l = confusion_table([r["l1_ah"] for r in rec], [r["l1_s"] for r in rec])
    l1_block = {"scale": "rater_L1 0..3, squared level distance",
                "qwk": _stat_block(rec, qwk_from_table, "l1_ah", "l1_s", name="qwk", k=L1_LEVELS, **kw),
                "exact_agreement": _stat_block(rec, exact_agreement_from_table, "l1_ah", "l1_s",
                                               name="exact_agreement", k=L1_LEVELS, **kw),
                "confusion_table_AH_rows_second_cols": tab_l.astype(int).tolist()}
    ah_cells = [{"cluster_id": r["cluster_id"], "J": r["J"], "A": r["a_ah"]} for r in rec]
    s_cells = [{"cluster_id": r["cluster_id"], "J": r["J"], "A": r["a_s"]} for r in rec]
    pi_block = {"estimand": "pi = Pr[J >= 2 AND A = 0] over these cells (cell level), per label set",
                "AH": _pi_block(ah_cells, **kw),
                "second_annotator": _pi_block(s_cells, **kw),
                "note": "descriptive; not a G1 decision and not a gate input (sec.12.4, L510-512). Eight cells "
                        "per category give inclusion probabilities from 8/36 to 8/21, so this pi-hat does not "
                        "estimate the 188-cell pi; only the paired AH versus second-annotator comparison is "
                        "interpreted (sec.12.4 (ii))"}
    restricted = [r for r in rec if r["J"] in JUDGE_RESTRICTED_LEVELS]
    cats: dict[str, int] = {}
    for c in cells:
        cats[c.category] = cats.get(c.category, 0) + 1
    out.update(
        cells_by_category=dict(sorted(cats.items())),
        A_agreement_AH_vs_second=a_block, L1_agreement_AH_vs_second=l1_block, pi_hat=pi_block,
        judge_vs_second_annotator={
            "descriptive_only": True,
            "all_cells": _judge_block(rec, **kw),
            "restricted_to_J_in_1_2_3": {
                **_judge_block(restricted, **kw),
                "why": "the judge span is shown on the label screen and is empty exactly when J = 0, so "
                       "the J = 0 versus J >= 1 split was visible to the annotator (sec.12.1 D16)"}},
        gates="none: every quantity here is descriptive (sec.12.4, DN-10)")
    return out


def second_annotation_report(cells: list[SecondCell], ai: dict[str, AiUse] | None, *, seed: int,
                             B: int | None = None, ties: str = DEFAULT_BCA_TIES) -> dict:
    """The 48-cell report: all cells, then the same statistics by AI use.  ``by_ai_use`` is the PRIMARY
    stratification (yes / no / not recorded: the sitting reported AI use, a ticked cell counts as yes),
    ``by_ai_use_tick_only`` the sensitivity (ticked / not ticked), and ``by_tool_among_yes_cells`` splits the
    yes group of the primary stratification by the tool the sitting reported (PREREG sec.12.4, 13.1 (7))."""
    ai = ai or {}
    kw = dict(seed=seed, B=B, ties=ties)

    def info(c: SecondCell) -> AiUse:
        return ai.get(c.cell_id, NOT_RECORDED_AI)

    primary = {g: [c for c in cells if info(c).group == g] for g in AI_USE_GROUPS}
    tick = {"ticked": [c for c in cells if info(c).ticked], "not ticked": [c for c in cells if not info(c).ticked]}
    tools: dict[str, list[SecondCell]] = {}
    for c in cells:
        if info(c).group == "yes":
            tools.setdefault(info(c).tool or TOOL_NOT_GIVEN, []).append(c)
    return {"all_cells": second_annotation_block(cells, **kw),
            "by_ai_use": {g: second_annotation_block(sub, **kw) for g, sub in primary.items()},
            "by_ai_use_tick_only": {g: second_annotation_block(sub, **kw) for g, sub in tick.items()},
            "by_tool_among_yes_cells": [{"tool": t, "n_cells": len(sub), "block": second_annotation_block(sub, **kw)}
                                        for t, sub in sorted(tools.items())],
            "notes": "by_ai_use is the primary stratification (the sitting reported AI use); "
                     "by_ai_use_tick_only is the sensitivity (the labeler's tick only); "
                     "by_tool_among_yes_cells splits the yes group by the tool of the sitting's report. "
                     "Separate descriptive blocks, no test of a difference; groups of a few cells give "
                     "wide or undefined intervals, stated in each block"}


def join_second(sample_ids, id_map: dict[str, str] | None, cells_by_id: dict, ah_labels,
                ah_fields: dict, second_labels):
    """Join the sample cells: judge J and cluster (cells.jsonl), the AH labels, the second labels."""
    sample = sorted(set(sample_ids))
    if id_map is None:
        mapped = {sid: sid for sid in sample}
    else:
        inverse = {src: opaque for opaque, src in id_map.items()}
        missing = [sid for sid in sample if sid not in inverse]
        if missing:
            raise ValueError(f"id map lacks {len(missing)} sample cell(s) (e.g. {missing[:3]})")
        mapped = {sid: inverse[sid] for sid in sample}
    extra = sorted(set(second_labels.labels) - set(mapped.values()))
    if extra:
        raise ValueError(f"second-annotator labels contain {len(extra)} cell_id(s) outside the sample "
                         f"(e.g. {extra[:3]})")
    problems: list[str] = []
    out: list[SecondCell] = []
    for sid in sample:
        cell = cells_by_id.get(sid)
        if cell is None or _cell_kind(cell) != CELL_KIND_PRIMARY:
            problems.append(f"{sid}: not a primary cell of the judge run")
            continue
        a0, l0 = ah_labels.labels.get(sid), ah_labels.rater_l1.get(sid)
        oid = mapped[sid]
        a1, l1 = second_labels.labels.get(oid), second_labels.rater_l1.get(oid)
        if a0 is None or l0 is None:
            problems.append(f"{sid}: AH labels lack A or rater_L1")
        if a1 is None or l1 is None:
            problems.append(f"{sid}: second-annotator labels lack A or rater_L1 (DN-9: all four columns)")
        sheet_cl = (ah_fields.get(sid) or {}).get("cluster_id")
        if sheet_cl and sheet_cl != str(cell["cluster_id"]):
            problems.append(f"{sid}: cluster_id differs between the AH sheet and the judge run")
        if None in (a0, l0, a1, l1):
            continue
        out.append(SecondCell(sid, str(cell["cluster_id"]), str(cell.get("category", "")),
                              int(cell["J"]), a0, l0, a1, l1))
    if problems:
        raise ValueError("second-annotation join failed: " + "; ".join(problems[:10])
                         + (f" (+{len(problems) - 10} more)" if len(problems) > 10 else ""))
    return out


# --------------------------------------------------------------------------
# provenance, wording and output-path guards
# --------------------------------------------------------------------------
def _git_info(path: Path) -> dict:
    """Best-effort git HEAD and whether the two analyzer files are clean at HEAD."""
    def run(*args):
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True,
                              timeout=15, check=False)
    try:
        head = run("rev-parse", "HEAD")
        if head.returncode != 0:
            return {"head": None, "analyzer_files_clean_at_head": None}
        files = [str(Path(__file__).resolve()), str(Path(ah.__file__).resolve())]
        st = run("status", "--porcelain", "--", *files)
        return {"head": head.stdout.strip(),
                "analyzer_files_clean_at_head": (st.stdout.strip() == "") if st.returncode == 0 else None}
    except (OSError, subprocess.SubprocessError):
        return {"head": None, "analyzer_files_clean_at_head": None}


def build_provenance(command: str, inputs: dict, *, seed: int, B: int, ties: str,
                     label_sources: dict, csv_source_marker: str | None, simulated: bool,
                     assertions: dict | None = None, expected_sha256_checked: dict | None = None) -> dict:
    """The provenance block stamped on every output."""
    files = {}
    for name, path in inputs.items():
        if path is not None:
            files[name] = {"path": str(path), "sha256": _sha256_file(Path(path)),
                           "n_bytes": Path(path).stat().st_size}
    return {
        "schema": SCHEMA_VERSION, "command": command,
        "analyzer": {"file": Path(__file__).name, "sha256": _sha256_file(Path(__file__).resolve()),
                     "registered_helpers_file": Path(ah.__file__).name,
                     "registered_helpers_sha256": _sha256_file(Path(ah.__file__).resolve()),
                     "git": _git_info(Path(__file__).resolve().parent)},
        "inputs": files,
        "input_hash_assertions": expected_sha256_checked or {},
        "bootstrap": {"method": "BCa cluster bootstrap (registered helper, mid-rank z0)",
                      "unit": "CQ cluster, whole clusters, unstratified", "resamples": B,
                      "registered_resamples": ah.BOOTSTRAP_RESAMPLES, "seed": seed,
                      "registered_seed": REGISTERED_SEED, "registered_seed_used": seed == REGISTERED_SEED,
                      "bca_ties": ties, "ci_level": CI_LEVEL},
        "label_sources": label_sources,
        "label_csv_source_marker": {"marker": csv_source_marker, "simulated": simulated},
        "evidence_status": EVIDENCE_STATUS, "evidence_status_note": EVIDENCE_STATUS_NOTE,
        "ai_assistance": AI_RECORDING_NOTE,
        "assertions": assertions or {},
        "preregistration": "PREREG.md sec.12.3 (G2 rule, DN-4b, DN-6, DN-7), sec.12.4 (DN-10); washout "
                           "labels are not an input to any primary estimate (L597)",
        "environment": {"python": platform.python_version(), "implementation": platform.python_implementation(),
                        "numpy": np.__version__, "scipy": scipy.__version__},
    }


DATA_STRING_KEYS = frozenset({"tool", "ai_tool"})     # operator-entered tool names: data, not our wording


def _mask_data_strings(node):
    if isinstance(node, dict):
        return {k: ("<tool name>" if k in DATA_STRING_KEYS and isinstance(v, str) else _mask_data_strings(v))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_mask_data_strings(v) for v in node]
    return node


def _text_for_wording_scan(payload: dict) -> str:
    """The output text with the operator-supplied strings masked: input paths and tool names are data, not
    our wording."""
    clone = json.loads(json.dumps(payload, default=_json_default, allow_nan=False))
    for entry in ((clone.get("provenance") or {}).get("inputs") or {}).values():
        if isinstance(entry, dict) and "path" in entry:
            entry["path"] = "<input path>"
    return json.dumps(_mask_data_strings(clone), indent=2, ensure_ascii=False)


def scan_forbidden_wording(text: str) -> list[str]:
    """Names of the forbidden phrases found in an output's text (see FORBIDDEN_WORDING)."""
    return [name for name, pat in FORBIDDEN_WORDING if pat.search(text)]


def refuse_unsafe_outputs(outputs: dict, inputs: dict, *, overwrite: bool) -> None:
    """analyze_holdout's guard (an output may not be an input) plus: --out and --out-cells differ,
    an existing output is not overwritten without --overwrite, and the sealed per-cell file does not
    go into a rater-readable directory."""
    _refuse_outputs_that_are_inputs(outputs, inputs)
    out, cells = outputs.get("--out"), outputs.get("--out-cells")
    if out is not None and cells is not None and _same_file(out, cells):
        raise SystemExit("--out-cells must differ from --out")
    for flag, path in outputs.items():
        if path is not None and not Path(path).resolve().parent.is_dir():
            raise SystemExit(f"{flag} {path}: the directory does not exist (it is not created here)")
        if path is not None and Path(path).exists() and not overwrite:
            raise SystemExit(f"refusing to overwrite {flag} {path}: it exists (pass --overwrite)")
    if cells is not None:
        bad = sorted(RATER_VISIBLE_DIR_NAMES & set(Path(cells).resolve().parts))
        if bad:
            raise SystemExit(f"refusing to write --out-cells {cells}: it is inside a directory the "
                             f"rater can read ({bad[0]}); the per-cell file stays sealed (PREREG sec.12.3)")


def _write_output(path: Path, text: str, overwrite: bool) -> None:
    with open(path, "w" if overwrite else "x", encoding="utf-8") as fh:
        fh.write(text)


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------
INPUT_FLAG_NAMES = ("design", "ah_labels", "washout_labels", "second_labels", "cells", "audit",
                    "session_log", "sample_list", "id_map", "exclude_controls")

PINNED_WASHOUT = [
    "G2 gate input (sec.12.3 'G2 computation'): reweighted pooled QWK_w with w_i = 1/pi_i fixed per cell (pi "
    "rounded to 4 decimals, pi = 0 is an error), unstratified whole-CQ-cluster BCa (B=10,000, "
    "default_rng(20260913), mid-rank z0, no renormalisation), lower end >= 0.70; a resample with E=0 counts "
    "as QWK=0 and is counted; an observed E=0 is not computable (sec.13.1 (6))",
    "per-stratum QWK: its interval resamples that stratum's own CQ clusters, unweighted; the "
    "Fleiss-Cohen-Everitt SE is for these two unweighted QWKs only and is never a decision input",
    "G3-W: a verdict only if all 24 ablated controls were presented and labeled; the rerun without the 8 "
    "ablated controls seen in S6 never gives a verdict (sec.12.3 DN-7, sec.13.1 (12))",
    "binary A between the passes: per stratum and weighted pooled, no unweighted pooled (sec.13.1 (6))",
    "dwell check: total over all saves of each primary cell (dwell_ms in packet mode, else elapsed_s), "
    "controls apart, linear quartiles, sessions = SESSION start lines (sec.13.1 (9))",
    "washout gap: days from the AH pass's last save to the first washout save (sec.13.1 (10))",
    "AI use: primary stratification = the sitting reported AI use (a ticked cell counts as yes), the tick "
    "alone as a sensitivity; a claim about AI use of a cell itself is limited to ticked cells, the other "
    "cells of the yes group are cells of sittings that reported AI use (sec.13.1 (7))",
    "washout results by AI use (D20; descriptive, not a gate): the weighted and the unweighted QWK of rater_L1 "
    "between the passes and the binary A agreement (per stratum and weighted pool) by AI-use group, by tool "
    "among the yes cells and for the tick-only sensitivity; an undefined resample is excluded and counted (the "
    "sec.12.4 rule), not set to 0 (the rule of G2); a group with no cell, fewer than two CQ clusters or an "
    "undefined QWK is not computable, with its n",
    "every output is stamped exploratory (sec.12.2 (7), sec.13.1 (13))",
]
UNPINNED_WASHOUT = [
    "the group-level weighted QWK keeps the 1/pi weights of the 72-cell sample (a domain estimate, not "
    "recalibrated to the group's share of the frame); the unweighted QWK is given beside it",
    "the AI-use groups have no minimum size beyond the method's: a group is not computable (no result is shown) "
    "when it has no cell, covers fewer than two CQ clusters (D20_MIN_CLUSTERS; the registered resampling needs "
    "two) or has an undefined QWK; no adjustment for multiplicity and no test of a difference between groups",
    "tool names are normalized (NFKC, whitespace, case) and a tool field naming several tools is one group",
    "the first washout save is the earliest save in the audit of any row of the design",
    "a tick in a sitting that reported no counts as yes (the count is reported); a disagreement between the "
    "sheet's ai_used column and the audit tick is counted and either tick counts",
]
PINNED_SECOND = [
    "A as a 2x2 table, rows = AH, columns = second annotator; PPA = n11/(n11+n10), NPA = n00/(n00+n01); no "
    "symmetric specific agreement; AC1 with p_e = 2 pi (1-pi), pi = (p_1+ + p_+1)/2 (sec.12.4 (i))",
    "a statistic that is undefined on a resample (a zero denominator, E=0 for a QWK) is excluded and "
    "counted, nothing is substituted; an undefined point estimate is reported as undefined (sec.12.4 (i), "
    "sec.13.1 (6))",
    "cluster Clopper-Pearson: event cluster = a cluster with at least one cell with J>=2 and A=0, n = the "
    "clusters the cells cover, the zero-event bound stated (sec.12.4 (iii))",
    "judge vs second annotator: QWK(J, rater_L1), exact agreement, kappa of 1[J>=2] vs A, each also with J "
    "in {1, 2, 3} (sec.12.4 (iv))",
    "by AI use: primary = the sitting reported AI use, tick-only sensitivity, tools within the yes cells "
    "(sec.13.1 (7))",
]
UNPINNED_SECOND = [
    "interval level for the DN-10 statistics is not restated: two-sided 95% BCa",
    "tool names are normalized (NFKC, whitespace, case) and a tool field naming several tools is one group",
    "a tick in a sitting that reported no counts as yes (the count is reported); a disagreement between the "
    "sheet's ai_used column and the audit tick is counted and either tick counts",
    "second annotator's ids: the same as the AH ids unless an id map is given",
]


def _parse_expect(items) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in items or []:
        name, sep, value = item.partition("=")
        name, value = name.strip().replace("-", "_"), value.strip().lower()
        if not sep or name not in INPUT_FLAG_NAMES or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise SystemExit(f"--expect-sha256 wants NAME=<64 hex>, NAME one of {list(INPUT_FLAG_NAMES)}; "
                             f"got {item!r}")
        out[name] = value
    return out


def _check_expected(inputs: dict, expect: dict) -> dict:
    checked = {}
    for name, want in expect.items():
        path = inputs.get(name)
        if path is None:
            raise SystemExit(f"--expect-sha256 {name}=...: that input was not given")
        got = _sha256_file(Path(path))
        if got != want:
            raise SystemExit(f"input {name} {path} has sha256 {got}, expected {want} "
                             "(not the locked file); refusing to analyse")
        checked[name] = {"expected": want, "matched": True}
    return checked


def _common_arguments(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--seed", type=int, required=True, help="pre-registered seed (never defaulted)")
    ap.add_argument("--out", type=Path, required=True, help="aggregates-only results JSON")
    ap.add_argument("--out-cells", type=Path, help="per-cell detail JSON (keep sealed)")
    ap.add_argument("--overwrite", action="store_true", help="replace an existing output")
    ap.add_argument("--ah-labels", type=Path, required=True)
    ap.add_argument("--label-source", help="human or an explicit simulation marker (rule of analyze_holdout)")
    ap.add_argument("--audit", type=Path, help="label_assist .audit.jsonl of this pass")
    ap.add_argument("--session-log", type=Path, help="label_assist session_log.txt of this pass")
    ap.add_argument("--expect-sha256", action="append", metavar="NAME=HEX",
                    help="assert an input file's sha256 (e.g. the lock manifest value)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    w = sub.add_parser("washout", help="G2, binary A agreement, dwell check, G3-W (sec.12.3)")
    _common_arguments(w)
    w.add_argument("--design", type=Path, required=True, help="sealed washout design table")
    w.add_argument("--washout-labels", type=Path, required=True)
    w.add_argument("--exclude-controls", type=Path, help="controls seen earlier (DN-7 rerun)")
    w.add_argument("--allow-design-deviation", action="store_true",
                   help="proceed although the design is not 72 primary + 24 ablated + 12 preserved; reported")
    w.add_argument("--ah-last-save", default=AH_LAST_SAVE,
                   help="ISO-8601 time WITH an offset: the AH pass's last save, from which the washout gap is "
                        "measured (default: the registered value " + AH_LAST_SAVE + ")")
    s = sub.add_parser("second", help="second-annotator report on the 48 cells (sec.12.4)")
    _common_arguments(s)
    s.add_argument("--cells", type=Path, required=True, help="judge run cells.jsonl")
    s.add_argument("--second-labels", type=Path, required=True)
    s.add_argument("--sample-list", type=Path, required=True, help="the 48-cell list (sha256 registered)")
    s.add_argument("--id-map", type=Path, help="table cell_id,source_cell_id if the annotator saw opaque ids")
    s.add_argument("--allow-unregistered-sample", action="store_true",
                   help="accept a sample list whose sha256 is not the registered one (rehearsal); reported")
    s.add_argument("--washout-locked", action="store_true",
                   help="assert that the washout labels are locked (sec.12.3 exposure control); recorded")
    return ap


def _load_labels(path: Path, label_source, tolerate=()):
    try:
        return load_label_csv(path, label_source=label_source, allow_partial=True, tolerate_ids=tolerate)
    except ValueError as exc:
        raise SystemExit(f"label validation failed: {exc}") from exc


def _finish(a, res: dict, cells_payload: dict | None, ids_for_leak, prov: dict) -> int:
    res["provenance"] = prov
    res["output_policy"] = {
        "main_json": "aggregates only: no cell, CQ or washout identifier",
        "per_cell_detail": "written only to --out-cells (keep sealed)" if a.out_cells else "not written"}
    text = json.dumps(res, indent=2, default=_json_default, allow_nan=False)
    leaks = find_cell_level_leaks(text, [i for i in ids_for_leak if i])
    if leaks:
        raise SystemExit(f"refusing to write: cell-level identifiers found in the aggregates-only JSON: {leaks[:5]}")
    bad = scan_forbidden_wording(_text_for_wording_scan(res))
    if bad:
        raise SystemExit(f"refusing to write: forbidden wording in the output: {bad}")
    cells_text = None
    if cells_payload is not None:
        cells_payload = {"WARNING": "per-cell values: keep sealed", "schema": SCHEMA_VERSION + " per-cell",
                         **cells_payload, "provenance": prov}
        cells_text = json.dumps(cells_payload, indent=2, default=_json_default, allow_nan=False)
        bad = scan_forbidden_wording(_text_for_wording_scan(cells_payload))
        if bad:
            raise SystemExit(f"refusing to write: forbidden wording in the per-cell output: {bad}")
    _write_output(a.out, text, a.overwrite)
    if cells_text is not None and a.out_cells is not None:
        _write_output(a.out_cells, cells_text, a.overwrite)
        print(f"NOTE: {a.out_cells} holds per-cell values; keep it sealed", file=sys.stderr)
    print(json.dumps(_stdout_summary(res), indent=2, default=_json_default))   # aggregates only
    return 0


def _stdout_summary(res: dict) -> dict:
    """A few aggregate lines for the terminal (never an identifier)."""
    out: dict = {"analysis": res.get("analysis"), "rehearsal": res.get("rehearsal")}
    out["evidence_status"] = res.get("evidence_status")
    g2 = res.get("G2")
    if g2:
        out["G2"] = {k: g2.get(k) for k in ("status", "value", "ci_lo", "ci_hi", "threshold")}
        out["washout_gap_days"] = (g2.get("washout_gap") or {}).get("gap_days")
        out["G3_W"] = {"ablated": {k: res["G3_W"]["ablated"].get(k) for k in ("status", "A0_over_valid")}}
        out["ai_use_primary_cells"] = res["ai_use_classification"]["primary_cells"]["by_group"]
    sec = res.get("second_annotation")
    if sec:
        out["second_annotation"] = {"n_cells": sec["all_cells"].get("n_cells"),
                                    "ai_use": res.get("ai_use_classification", {}).get("by_group")}
    return out


def _run_washout(a) -> int:
    inputs = {"design": a.design, "ah_labels": a.ah_labels, "washout_labels": a.washout_labels,
              "audit": a.audit, "session_log": a.session_log, "exclude_controls": a.exclude_controls}
    refuse_unsafe_outputs({"--out": a.out, "--out-cells": a.out_cells},
                          {f"--{k.replace('_', '-')}": v for k, v in inputs.items()}, overwrite=a.overwrite)
    checked = _check_expected(inputs, _parse_expect(a.expect_sha256))
    try:
        design = load_washout_design(a.design)
    except ValueError as exc:
        raise SystemExit(f"design: {exc}") from exc
    check = check_washout_design(design)
    if not check["conforms"] and not a.allow_design_deviation:
        raise SystemExit("the washout design is not the registered one: " + "; ".join(check["problems"])
                         + ". Pass --allow-design-deviation to analyse it anyway (reported).")
    # AH control rows are never read: the controls of the design, and any AH-sheet id that carries the control
    # prefix (PREREG D6: ``ablated_control:F:CQB05``), so a design that lacks some controls cannot expose them
    try:
        ah_sheet_ids = read_sheet_fields(a.ah_labels, ())
    except ValueError as exc:
        raise SystemExit(f"AH labels: {exc}") from exc
    control_src = {r.source_cell_id for r in design if r.cell_kind != CELL_KIND_PRIMARY}
    control_src |= {i for i in ah_sheet_ids if i.startswith(CONTROL_ID_PREFIXES)}
    excluded_wid = {r.cell_id for r in design if r.excluded_reason is not None}
    ah_labels = _load_labels(a.ah_labels, a.label_source, tolerate=control_src)
    wo_labels = _load_labels(a.washout_labels, a.label_source, tolerate=excluded_wid)
    if (ah_labels.source, ah_labels.simulated) != (wo_labels.source, wo_labels.simulated):
        raise SystemExit("label sources of the AH and washout sheets disagree: "
                         f"{ah_labels.source!r} vs {wo_labels.source!r}")
    try:
        ah_fields = read_sheet_fields(a.ah_labels, ("cluster_id",))
        primary, controls = join_washout(design, ah_labels, ah_fields, wo_labels)
        listed = read_id_list(a.exclude_controls) if a.exclude_controls else []
        prim_ids = {r.cell_id for r in design if r.cell_kind == CELL_KIND_PRIMARY} | \
                   {r.source_cell_id for r in design if r.cell_kind == CELL_KIND_PRIMARY}
        if prim_ids & set(listed):
            raise ValueError("--exclude-controls names a primary cell; only controls may be listed")
        g3 = g3_w(controls, listed_exclusions=listed)
    except ValueError as exc:
        raise SystemExit(f"washout analysis refused: {exc}") from exc
    if _parse_utc(a.ah_last_save) is None:
        raise SystemExit("--ah-last-save must be ISO-8601 with an explicit UTC offset "
                         "(e.g. 2026-10-08T23:58:55+09:00)")
    audit = extras = None
    if a.audit:
        try:
            audit = load_label_audit(a.audit)
            extras = load_audit_extras(a.audit)
        except ValueError as exc:
            raise SystemExit(f"audit: {exc}") from exc
    log_records = log_meta = None
    ai_reports = NO_AI_REPORTS
    if a.session_log:
        try:
            log_records, log_meta = load_session_log(a.session_log)
            ai_reports = load_ai_use_reports(a.session_log)
        except ValueError as exc:
            raise SystemExit(f"session log: {exc}") from exc
    try:
        sheet_flags = load_sheet_ai_flags(a.washout_labels)
    except ValueError as exc:
        raise SystemExit(f"washout labels: {exc}") from exc
    if a.seed != REGISTERED_SEED:
        print(f"WARNING: --seed {a.seed} is not the registered seed {REGISTERED_SEED}; this output "
              "is not the registered analysis", file=sys.stderr)
    if "washout_labels" not in checked:
        print("WARNING: no --expect-sha256 washout_labels=...: the lock-manifest check was not "
              "performed (G2 is computed only after the washout labels are locked)", file=sys.stderr)
    B = BOOTSTRAP_RESAMPLES
    ties = DEFAULT_BCA_TIES
    primary_ai, primary_ai_counts = classify_ai_use({c.cell_id: c.cell_id for c in primary}, audit, extras,
                                                    ai_reports, sheet_flags)
    shown_controls = [c for c in controls if c.presented]
    control_ai, control_ai_counts = classify_ai_use({c.cell_id: c.cell_id for c in shown_controls}, audit,
                                                    extras, ai_reports, sheet_flags)
    res = {
        "schema": SCHEMA_VERSION, "analysis": "washout (PREREG sec.12.3)",
        "evidence_status": EVIDENCE_STATUS,
        "rehearsal": bool(ah_labels.simulated),
        "label_sources": {"ah_pass": LABEL_SOURCE_AH, "washout_pass": LABEL_SOURCE_WASHOUT},
        "design_check": {**check, "allow_design_deviation": bool(a.allow_design_deviation)},
        "G2": g2_analysis(primary, seed=a.seed, B=B, ties=ties),
        "A_agreement_between_passes": a_agreement_between_passes(primary, seed=a.seed, B=B, ties=ties),
        "dwell_check": dwell_check([c.cell_id for c in primary], audit, log_records,
                                   other_ids=[c.cell_id for c in shown_controls], extras=extras),
        "G3_W": g3,
        "ai_use_classification": {
            "counts_only": True,
            "note": "classification counts only; the washout results by group are in ai_use_stratified "
                    "(PREREG sec.12.1 D20)",
            "primary_cells": primary_ai_counts, "presented_controls": control_ai_counts,
            "session_reports": ai_use_session_summary(ai_reports)},
        "ai_use_stratified": ai_use_stratified_results(primary, primary_ai, seed=a.seed, B=B, ties=ties),
        "pinned_choices": PINNED_WASHOUT,
        "unpinned_choices": UNPINNED_WASHOUT,
        "limitations": [
            "G2 compares two passes of one rater; the AH pass began from an AI draft the washout pass "
            "did not show (sec.12.3 DN-6); judge_evidence_span is shown in both passes and may cue "
            "recall (DN-2).",
            "AI chat tools were permitted in both passes. Use is self-reported per sitting with an "
            "optional tick on each row, and anything unreported is 'not recorded'; the AH pass has no "
            "cell-level AI record, so the two passes are not comparable on AI use (D3, D20).",
            "Controls are mixed into the washout and the rater knows they exist, so 'unannounced' (L453) "
            "is not restored (DN-7).",
            "The AI-use groups partition the 72 primary cells and are small: their intervals are wide, not "
            "adjusted for multiplicity and withheld when a group covers fewer than two CQ clusters, and "
            "'not recorded' is not 'no' (D20).",
        ],
    }
    res["G2"]["washout_gap"] = washout_gap_report(
        audit, [r.cell_id for r in design], ah_last_save=a.ah_last_save,
        source=("registered (PREREG sec.12.3 DN-5, sec.13.1 (10))" if a.ah_last_save == AH_LAST_SAVE
                else "--ah-last-save"))
    if ah_labels.simulated:
        res["rehearsal_note"] = "simulated label source: a rehearsal on synthetic data, never a manuscript result"
    if log_meta is not None:
        res["session_log_parse"] = log_meta
    if audit is not None:
        res["audit_parse"] = {"sha256": audit.sha256, "n_lines": audit.n_lines,
                              "n_save_records": audit.n_save_records,
                              "n_unparseable_lines": audit.n_unparseable_lines,
                              "n_save_records_unusable": audit.n_save_records_unusable}
    prov = build_provenance(
        "washout", inputs, seed=a.seed, B=B, ties=ties,
        label_sources={"ah_pass": LABEL_SOURCE_AH, "washout_pass": LABEL_SOURCE_WASHOUT},
        csv_source_marker=ah_labels.source, simulated=ah_labels.simulated,
        assertions={"washout_lock_manifest_sha256_checked": "washout_labels" in checked,
                    "ah_control_label_values_read": False,
                    "washout_control_label_values_read": True,
                    "ah_last_save": a.ah_last_save,
                    "ah_last_save_is_the_registered_value": a.ah_last_save == AH_LAST_SAVE},
        expected_sha256_checked=checked)
    cell_rows = [{"cell_id": c.cell_id, "source_cell_id": c.source_cell_id, "cluster_id": c.cluster_id,
                  "stratum": c.stratum, "inclusion_prob": c.pi, "weight": c.w,
                  "AH_A": c.ah_a, "AH_rater_L1": c.ah_l1, "washout_A": c.wo_a,
                  "washout_rater_L1": c.wo_l1, "ai_use": primary_ai[c.cell_id].group,
                  "ai_ticked": primary_ai[c.cell_id].ticked, "ai_tool": primary_ai[c.cell_id].tool}
                 for c in primary]
    ctrl_rows = [{"cell_id": c.cell_id, "source_cell_id": c.source_cell_id, "kind": c.kind,
                  "excluded_reason": c.excluded_reason, "washout_A": c.a,
                  "ai_use": control_ai[c.cell_id].group if c.presented else None,
                  "ai_ticked": control_ai[c.cell_id].ticked if c.presented else None,
                  "ai_tool": control_ai[c.cell_id].tool if c.presented else None} for c in controls]
    ids = ([r.cell_id for r in design] + [r.source_cell_id for r in design]
           + [c.cluster_id for c in primary])
    return _finish(a, res, {"primary_cells": cell_rows, "controls": ctrl_rows}, ids, prov)


def _run_second(a) -> int:
    inputs = {"cells": a.cells, "ah_labels": a.ah_labels, "second_labels": a.second_labels,
              "sample_list": a.sample_list, "id_map": a.id_map, "audit": a.audit,
              "session_log": a.session_log}
    refuse_unsafe_outputs({"--out": a.out, "--out-cells": a.out_cells},
                          {f"--{k.replace('_', '-')}": v for k, v in inputs.items()}, overwrite=a.overwrite)
    checked = _check_expected(inputs, _parse_expect(a.expect_sha256))
    list_sha = _sha256_file(a.sample_list)
    registered = list_sha == SECOND_SAMPLE_SHA256
    if not registered and not a.allow_unregistered_sample:
        raise SystemExit(f"the sample list's sha256 {list_sha} is not the registered {SECOND_SAMPLE_SHA256} "
                         "(PREREG sec.12.4 DN-8); pass --allow-unregistered-sample for a rehearsal")
    try:
        sample = read_id_list(a.sample_list)
        if len(sample) != len(set(sample)):
            raise ValueError("the sample list holds a repeated id")
        if len(sample) != SECOND_N and not a.allow_unregistered_sample:
            raise ValueError(f"the sample list has {len(sample)} ids, registered {SECOND_N}")
        cells = load_cells(a.cells, require_a=False)
        cells_by_id = {str(c["cell_id"]): c for c in cells}
        control_ids = {cid for cid, c in cells_by_id.items() if _cell_kind(c) != CELL_KIND_PRIMARY}
        id_map = None
        if a.id_map:
            rows = read_table(a.id_map)
            _require_columns(rows, ("cell_id", "source_cell_id"), a.id_map)
            id_map = {r["cell_id"]: r["source_cell_id"] for r in rows}
            if len(id_map) != len(rows) or len(set(id_map.values())) != len(rows):
                raise ValueError("id map has a repeated cell_id or source_cell_id")
        try:                                  # a cross-check, not a guard: it never blocks the run
            derived = second_annotator_sample(cells)
        except ValueError:
            derived = None
        cats: dict[str, int] = {}
        for sid in sample:
            c = cells_by_id.get(sid)
            if c is None:
                raise ValueError(f"sample id {sid!r} is not in the judge run")
            cats[str(c.get("category", ""))] = cats.get(str(c.get("category", "")), 0) + 1
        if not all(v == SECOND_PER_CATEGORY for v in cats.values()) and not a.allow_unregistered_sample:
            raise ValueError(f"the sample is not {SECOND_PER_CATEGORY} cells per category: "
                             f"{dict(sorted(cats.items()))}")
        ah_labels = _load_labels(a.ah_labels, a.label_source, tolerate=control_ids)
        s_labels = _load_labels(a.second_labels, a.label_source)
        if (ah_labels.source, ah_labels.simulated) != (s_labels.source, s_labels.simulated):
            raise ValueError("label sources of the AH and second-annotator sheets disagree: "
                             f"{ah_labels.source!r} vs {s_labels.source!r}")
        ah_fields = read_sheet_fields(a.ah_labels, ("cluster_id",), required=False)
        joined = join_second(sample, id_map, cells_by_id, ah_labels, ah_fields, s_labels)
        ai_reports = load_ai_use_reports(a.session_log) if a.session_log else NO_AI_REPORTS
        extras = load_audit_extras(a.audit) if a.audit else None
        sheet_flags = load_sheet_ai_flags(a.second_labels)
    except ValueError as exc:
        raise SystemExit(f"second-annotation analysis refused: {exc}") from exc
    audit = None
    if a.audit:
        try:
            audit = load_label_audit(a.audit)
        except ValueError as exc:
            raise SystemExit(f"audit: {exc}") from exc
    log_records = None
    if a.session_log:
        try:
            log_records, _ = load_session_log(a.session_log)
        except ValueError as exc:
            raise SystemExit(f"session log: {exc}") from exc
    if a.seed != REGISTERED_SEED:
        print(f"WARNING: --seed {a.seed} is not the registered seed {REGISTERED_SEED}", file=sys.stderr)
    if a.session_log and not a.audit:
        print("WARNING: --session-log without --audit: the session reports cannot be linked to cells "
              "(no session id per cell); only per-cell ticks are used", file=sys.stderr)
    if not a.session_log and not a.audit and sheet_flags is None:
        print("WARNING: no ai_used column in the second-annotator sheet, no --audit and no --session-log: "
              "AI use cannot be determined, every cell is reported as not recorded", file=sys.stderr)
    if not a.washout_locked:
        print("WARNING: outputs derived from the second annotator's labels are sealed from the rater "
              "until the washout labels are locked (sec.12.3); --washout-locked was not asserted",
              file=sys.stderr)
    reproduced = derived is not None and derived == sorted(sample)
    if not reproduced:
        print("WARNING: the sample list is not what the registered draw gives on this cells.jsonl",
              file=sys.stderr)
    B = BOOTSTRAP_RESAMPLES
    ties = DEFAULT_BCA_TIES
    shown_as = {src: opaque for opaque, src in id_map.items()} if id_map else {}
    audit_ids = {c.cell_id: shown_as.get(c.cell_id, c.cell_id) for c in joined}
    ai_use, ai_counts = classify_ai_use(audit_ids, audit, extras, ai_reports, sheet_flags)
    res = {
        "schema": SCHEMA_VERSION, "analysis": "second annotation (PREREG sec.12.4)",
        "evidence_status": EVIDENCE_STATUS,
        "rehearsal": bool(ah_labels.simulated) or not registered,
        "label_sources": {"ah_pass": LABEL_SOURCE_AH, "second_annotation": LABEL_SOURCE_SECOND},
        "sample_check": {"n_ids": len(sample), "sha256": list_sha, "registered_sha256": SECOND_SAMPLE_SHA256,
                         "matches_registered_sha256": registered,
                         "cells_per_category": dict(sorted(cats.items())),
                         "reproduced_by_registered_draw_on_cells": reproduced,
                         "allow_unregistered_sample": bool(a.allow_unregistered_sample)},
        "ai_use_classification": {**ai_counts, "session_reports": ai_use_session_summary(ai_reports)},
        "second_annotation": second_annotation_report(joined, ai_use, seed=a.seed, B=B, ties=ties),
        "dwell_check": (dwell_check(list(audit_ids.values()), audit, log_records, extras=extras)
                        if (audit is not None or log_records is not None) else
                        {"status": "not_computable", "reason": "no --audit / --session-log given"}),
        "pinned_choices": PINNED_SECOND,
        "unpinned_choices": UNPINNED_SECOND,
        "limitations": [
            "The AH labels are LLM-assisted (AI-drafted, author-revised) labels, not a gold standard: "
            "agreement with them is not accuracy.",
            "AI chat tools were permitted. Use is self-reported per sitting with an optional tick on each "
            "row, and anything unreported is 'not recorded' (D20). The yes group holds ticked cells and "
            "unticked cells of sittings that reported AI use.",
            "n = 48 cells: every interval is wide, and the AI-use groups are smaller still; the "
            "intervals are unadjusted 95% intervals and none of them is a gate.",
        ],
    }
    if res["rehearsal"]:
        res["rehearsal_note"] = "simulated labels or an unregistered sample: not a manuscript result"
    prov = build_provenance(
        "second", inputs, seed=a.seed, B=B, ties=ties,
        label_sources={"ah_pass": LABEL_SOURCE_AH, "second_annotation": LABEL_SOURCE_SECOND},
        csv_source_marker=ah_labels.source, simulated=ah_labels.simulated,
        assertions={"washout_locked_asserted": bool(a.washout_locked),
                    "second_annotator_labels_sealed_until_washout_lock": True},
        expected_sha256_checked=checked)
    cell_rows = [{"cell_id": c.cell_id, "cluster_id": c.cluster_id, "category": c.category, "J": c.j,
                  "AH_A": c.ah_a, "AH_rater_L1": c.ah_l1, "second_A": c.s_a, "second_rater_L1": c.s_l1,
                  "ai_use": ai_use[c.cell_id].group, "ai_ticked": ai_use[c.cell_id].ticked,
                  "ai_tool": ai_use[c.cell_id].tool} for c in joined]
    ids = list(sample) + [c.cluster_id for c in joined] + list((id_map or {}).keys())
    return _finish(a, res, {"cells": cell_rows}, ids, prov)


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    return _run_washout(a) if a.command == "washout" else _run_second(a)


if __name__ == "__main__":
    raise SystemExit(main())
