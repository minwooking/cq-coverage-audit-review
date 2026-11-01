"""Clock-skew check on the human-pass dwell behind gate G7 (PREREG L349, dwell condition).

In the labeling audit, ``elapsed_s`` is the server clock at save minus a timestamp that the
rater's browser took when the row page loaded (label_assist.py @ f855e62, Store.save and the
page script). If the rater's device clock differed from the server's, every dwell shifted by
that difference. This script estimates the difference from the audit itself and recomputes
the G7 under-20-s count on the server clock alone.

Reads the locked audit sidecar (``*.audit.jsonl``) and the session log, and writes
``dwell_skew_check.json`` next to this script. From the audit it uses ts, first_opened_ts,
elapsed_s and session_id, plus the cell_id prefix to split control from primary cells. No
label, draft field, note, span, cell id or session id is written: the output holds counts,
quantiles and intervals only. Times are handled as integer milliseconds and the bootstrap is
seeded, so a rerun on the same inputs is byte-identical.

Usage (from the worktree root)::

    python paper/access2026/harness/real_run/results_human_pass/dwell_skew_check.py \
        locked_labels/primary_working.csv.audit.jsonl \
        locked_labels/primary_working.csv.session_log.txt

Seconds are stored as exact decimals of the millisecond values; proportions are stored at
full precision next to their numerator and denominator.
"""
import hashlib
import json
import math
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_NAME = "dwell_skew_check.json"

# CONTROL_PREFIXES of label_assist.py at the lock commit f855e62: a save whose cell_id starts
# with one of these is a control cell; every other save is a primary cell.
CONTROL_PREFIXES = ("ablated_control:", "preserved_control:")
G7_FAST_MS = 20_000      # PREREG L349: a cell is "fast" when its total dwell is under 20 s
G7_FAST_PCT_BELOW = 3    # G7 needs fewer than 3% fast cells
IDLE_GAP_MS = 5_000      # s above this is an idle gap between saves, not clock skew
ROUND_MS = 100           # label_assist rounds elapsed_s to 0.1 s
BOOT_B = 10_000
BOOT_SEED = 20261009
Z975 = 1.959963984540054
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

ELAPSED_FORMULA = (
    "elapsed_s = round(t_save - t_open, 1). t_save is time.time() on the server, read inside "
    "Store.save (label_assist.py @ f855e62, L383). t_open is "
    "datetime.fromisoformat(first_opened).timestamp(), where first_opened is the string "
    "new Date().toISOString() that the rater's browser took when the row page loaded (L704) "
    "and posted with the save (L787): the client clock. A negative result is stored as null "
    "(L400-401); a non-empty first_opened that does not parse also gives null, with no "
    "fallback to the previous-save interval (L391-397). With d = client clock - server "
    "clock, elapsed_s = dwell - d: a client clock ahead of the server shrinks dwell (null once "
    "d exceeds the dwell), one behind it inflates dwell. The audit ts is the server wall "
    "clock at audit write, truncated to whole seconds (now_iso, L130 and L416); "
    "first_opened_ts is the raw client string. The server never records when a row was served."
)
DELTA_DEFINITION = (
    "delta = ts(k) - ts(k-1) for consecutive saves of one session, ordered by (ts, file "
    "order). The next row page loads right after a save, so delta = dwell + page-load latency "
    "(+-1 s from the whole-second ts): a server-clock upper bound on dwell. The first save of a "
    "session has no delta. Sub-second variant: delta_p = t(k) - t(k-1) with t = first_opened + "
    "elapsed_s, which is the server save time because the client clock cancels (resolution "
    "0.1 s, the rounding of elapsed_s)."
)
SKEW_DEFINITION = (
    "s = first_opened(k) - t(k-1): the client's page-load stamp of row k minus the server's save "
    "time of the previous row, t as above. s = d + tau with d = client clock - server clock and "
    "tau >= 0 the latency from the previous save to the page script of the next row, so a "
    "constant skew d shifts every s by d. D = delta - elapsed_s equals s up to the whole-second "
    "ts quantization. client_lead_upper_bound_s = min(s) + 0.05 s (d <= s - tau <= s, plus the "
    "rounding of elapsed_s)."
)
CAVEATS = [
    "delta bounds a row's dwell from above only if the row page loaded after the previous "
    "save; delta_upper_bound_check counts the saves with elapsed_s > delta + 1 s.",
    "Whole-second delta has +-1 s quantization (the audit ts is truncated to seconds). The "
    "sub-second delta and the skew estimator carry the 0.1 s rounding of elapsed_s.",
    "A client clock behind the server inflates elapsed_s, the direction that would flatter G7; "
    "only a client clock ahead of the server could make the dwell look too short, and "
    "client_lead_upper_bound_s bounds that lead.",
    "Idle-gap rows (s above 5 s: the next row loaded more than 5 s after the previous save) are "
    "not skew. They stay in the all-rows statistics and are left out of the "
    "excluding_idle_gaps variants.",
    "Bootstrap intervals are percentile intervals over rows treated as independent; "
    "within-session correlation is ignored, so they are descriptive.",
    "Every cell was saved once, so a cell's total dwell (the registered G7 basis, the sum of "
    "elapsed_s over its saves) equals that save's value; the script stops if a cell has more "
    "than one save.",
    "A primary cell with no within-session predecessor has no delta: it is left out of the "
    "delta-basis share (n_with_value) and counted in share_bounds_all_primary_cells.",
    "The check validates the timing measurement only. It says nothing about rater effort, and "
    "the labels are AH (AI-drafted, human-revised); see annotation_locked/LOCK_2026-10-09.md.",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _epoch_ms(text: str) -> int:
    """ISO-8601 with an explicit offset (or a trailing Z) -> integer milliseconds since epoch."""
    t = text.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    d = datetime.fromisoformat(t)
    if d.tzinfo is None:
        raise ValueError("timestamp without a UTC offset")
    delta = d - _EPOCH
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def _sec(ms):
    return None if ms is None else ms / 1000


def _quantile(xs: list, p: float) -> float:
    """Linear-interpolation quantile of a sorted list (p in {.25, .5, .75}: exact in binary)."""
    h = (len(xs) - 1) * p
    lo = int(h)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (h - lo) * (xs[hi] - xs[lo])


def _dist(xs_ms: list) -> dict:
    xs = sorted(xs_ms)
    if not xs:
        return {"n": 0, "median_s": None, "q1_s": None, "q3_s": None, "min_s": None, "max_s": None}
    return {"n": len(xs), "median_s": _sec(_quantile(xs, 0.5)),
            "q1_s": _sec(_quantile(xs, 0.25)), "q3_s": _sec(_quantile(xs, 0.75)),
            "min_s": _sec(xs[0]), "max_s": _sec(xs[-1])}


def _boot_median_ci(xs_ms: list, b: int, seed: int):
    """95% percentile bootstrap interval of the median (seconds); a fresh generator per call."""
    n = len(xs_ms)
    if n == 0:
        return None
    rnd = random.Random(seed).random
    meds = sorted(_quantile(sorted(xs_ms[int(rnd() * n)] for _ in range(n)), 0.5)
                  for _ in range(b))
    return [_sec(meds[(25 * b) // 1000]), _sec(meds[(975 * b) // 1000])]


def _wilson(k: int, n: int):
    if n == 0:
        return None
    p = k / n
    d = 1 + Z975 ** 2 / n
    centre = (p + Z975 ** 2 / (2 * n)) / d
    half = Z975 * math.sqrt(p * (1 - p) / n + Z975 ** 2 / (4 * n * n)) / d
    return [centre - half, centre + half]


def _theil_sen(points: list):
    """Median pairwise slope in seconds per hour of (ts_ms, s_ms) points; needs >= 3 points."""
    if len(points) < 3:
        return None
    slopes = []
    for i, (ti, si) in enumerate(points):
        for tj, sj in points[i + 1:]:
            if tj != ti:
                slopes.append((sj - si) * 3600 / (tj - ti))
    return _quantile(sorted(slopes), 0.5) if slopes else None


def _parse_log(text: str) -> list:
    sessions = []
    for line in text.splitlines():
        m = re.match(r"SESSION start=\S+ pid=\d+ session_id=(\S+)", line)
        if m:
            sessions.append({"sid": m.group(1), "saved": None})
            continue
        m = re.match(r"SESSION end=\S+ pid=\d+ saved=(\d+)", line)
        if m and sessions:
            sessions[-1]["saved"] = int(m.group(1))
    return sessions


def _load_saves(text: str):
    """Project the audit's save records onto timing fields; ids and labels never leave here."""
    saves, cell_ids = [], set()
    n_records = n_events = n_dup = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            raise SystemExit("unreadable audit line") from None
        n_records += 1
        if "cell_id" not in rec:  # session events such as 12H_ACK_OVERRIDE carry no cell_id
            n_events += 1
            continue
        cid = str(rec["cell_id"])
        n_dup += cid in cell_ids
        cell_ids.add(cid)
        try:
            ts = _epoch_ms(rec["ts"])
            sid = rec["session_id"]
        except (KeyError, ValueError, TypeError, AttributeError):
            raise SystemExit("audit save record without a usable ts or session_id") from None
        el = rec.get("elapsed_s")
        if el is None:
            el_state, el_ms = "null", None
        elif isinstance(el, bool) or not isinstance(el, (int, float)) or not math.isfinite(el):
            el_state, el_ms = "invalid", None
        elif el < 0:
            el_state, el_ms = "negative", None
        else:
            el_state, el_ms = "ok", round(el * 1000)
        fo = rec.get("first_opened_ts")
        if not fo:
            fo_state, fo_ms = "missing", None
        else:
            try:
                fo_state, fo_ms = "ok", _epoch_ms(fo)
            except (ValueError, TypeError, AttributeError):
                fo_state, fo_ms = "unparsable", None
        saves.append({"i": len(saves), "sid": sid, "ts": ts, "el_state": el_state, "el_ms": el_ms,
                      "fo_state": fo_state, "fo_ms": fo_ms,
                      "kind": "control" if cid.startswith(CONTROL_PREFIXES) else "primary"})
    return saves, n_records, n_events, n_dup


def _derive(saves: list) -> dict:
    """Per-session ordering and the server-clock quantities; fills the save dicts in place."""
    by_sid = {}
    for s in saves:
        by_sid.setdefault(s["sid"], []).append(s)
    for lst in by_sid.values():
        lst.sort(key=lambda s: (s["ts"], s["i"]))
        prev = None
        for s in lst:
            el, fo = s["el_ms"], s["fo_ms"]
            pt = prev["t_ms"] if prev else None
            s["t_ms"] = fo + el if el is not None and fo is not None else None
            s["delta_ms"] = s["ts"] - prev["ts"] if prev else None
            s["D_ms"] = s["delta_ms"] - el if s["delta_ms"] is not None and el is not None else None
            s["delta_p_ms"] = s["t_ms"] - pt if s["t_ms"] is not None and pt is not None else None
            s["s_ms"] = fo - pt if fo is not None and pt is not None else None
            s["tcheck_ms"] = s["ts"] - s["t_ms"] if s["t_ms"] is not None else None
            prev = s
    return by_sid


def _s_block(points: list, b: int, seed: int) -> dict:
    xs = [p[1] for p in points]
    out = _dist(xs)
    out["n_negative"] = sum(x < 0 for x in xs)
    out["client_lead_upper_bound_s"] = _sec(min(xs) + ROUND_MS // 2) if xs else None
    out["median_ci95_s"] = _boot_median_ci(xs, b, seed)
    out["theil_sen_slope_s_per_h"] = _theil_sen(points)
    out["span_h"] = (points[-1][0] - points[0][0]) / 3_600_000 if points else None
    return out


def _session_block(lst: list, log_k, log_saved, b: int, seed: int) -> dict:
    d_vals = [s["D_ms"] for s in lst if s["D_ms"] is not None]
    points = [(s["ts"], s["s_ms"]) for s in lst if s["s_ms"] is not None]
    steady = [p for p in points if p[1] <= IDLE_GAP_MS]
    idle = [s for s in lst if s["s_ms"] is not None and s["s_ms"] > IDLE_GAP_MS]
    dist = _dist(d_vals)
    dist["n_within_minus1_to_plus2_s"] = sum(-1000 <= x <= 2000 for x in d_vals)
    dist["n_below_minus1_s"] = sum(x < -1000 for x in d_vals)
    dist["n_above_5_s"] = sum(x > 5000 for x in d_vals)
    return {
        "log_index": log_k,
        "n_saves": len(lst),
        "n_saves_in_session_log": log_saved,
        "n_primary_saves": sum(s["kind"] == "primary" for s in lst),
        "n_control_saves": sum(s["kind"] != "primary" for s in lst),
        "n_without_predecessor": sum(s["delta_ms"] is None for s in lst),
        "delta_minus_elapsed": dist,
        "skew_estimator": _s_block(points, b, seed),
        "skew_estimator_excluding_idle_gaps": _s_block(steady, b, seed),
        "idle_gap_rows": {
            "threshold_s": IDLE_GAP_MS / 1000, "n": len(idle),
            "n_with_elapsed_under_20s": sum(
                s["el_ms"] is not None and s["el_ms"] < G7_FAST_MS for s in idle)},
    }


def _g7_block(vals: list, b: int, seed: int) -> dict:
    """G7 dwell statistics for one basis: one value (integer ms or None) per primary cell."""
    known = sorted(v for v in vals if v is not None)
    n_all, n = len(vals), len(known)
    under = sum(v < G7_FAST_MS for v in known)
    unknown = n_all - n
    if 100 * under >= G7_FAST_PCT_BELOW * n_all:
        met = False
    elif 100 * (under + unknown) < G7_FAST_PCT_BELOW * n_all:
        met = True
    else:
        met = None
    block = {
        "n_primary_cells": n_all,
        "n_with_value": n,
        "n_without_value": unknown,
        "n_under_20s": under,
        "share_under_20s": under / n if n else None,
        "share_under_20s_wilson95": _wilson(under, n),
        "share_bounds_all_primary_cells": [under / n_all, (under + unknown) / n_all],
        "criterion_met": met,
    }
    dist = _dist(known)
    dist.pop("n")
    block.update(dist)
    block["median_ci95_s"] = _boot_median_ci(known, b, seed)
    return block


def _crossing(a_vals: list, b_vals: list) -> dict:
    pairs = [(a, b) for a, b in zip(a_vals, b_vals) if a is not None and b is not None]
    both_under = sum(a < G7_FAST_MS and b < G7_FAST_MS for a, b in pairs)
    only_a = sum(a < G7_FAST_MS <= b for a, b in pairs)
    only_b = sum(b < G7_FAST_MS <= a for a, b in pairs)
    both_over = sum(a >= G7_FAST_MS and b >= G7_FAST_MS for a, b in pairs)
    return {"n_cells_compared": len(pairs), "under_20s_on_both": both_under,
            "under_20s_registered_only": only_a, "under_20s_delta_only": only_b,
            "over_20s_on_both": both_over, "n_crossing_20s": only_a + only_b}


def analyze(audit_path, log_path, boot_b: int = BOOT_B, seed: int = BOOT_SEED) -> dict:
    audit_bytes = Path(audit_path).read_bytes()
    log_bytes = Path(log_path).read_bytes()
    log_sessions = _parse_log(log_bytes.decode("utf-8"))
    log_index = {s["sid"]: k for k, s in enumerate(log_sessions, start=1)}
    log_saved = {s["sid"]: s["saved"] for s in log_sessions}
    saves, n_records, n_events, n_dup = _load_saves(audit_bytes.decode("utf-8"))
    if n_dup:
        raise SystemExit("a cell was saved more than once: per-cell total dwell is not "
                         "implemented in this check")
    by_sid = _derive(saves)
    prim = [s for s in saves if s["kind"] == "primary"]

    sessions = {}
    for order, (sid, lst) in enumerate(by_sid.items(), start=1):
        k = log_index.get(sid)
        sessions[f"S{k}" if k else f"unlogged_{order}"] = _session_block(
            lst, k, log_saved.get(sid), boot_b, seed)

    tcheck = [s["tcheck_ms"] for s in saves if s["tcheck_ms"] is not None]
    n_outside = sum(not (-1050 <= x <= 150) for x in tcheck)
    d_all = [s["D_ms"] for s in saves if s["D_ms"] is not None]
    n_exceed = sum(x < -1000 for x in d_all)
    states = [s["el_state"] for s in saves]
    known_el = [s["el_ms"] for s in saves if s["el_ms"] is not None]
    n_fo_bad = sum(s["fo_state"] != "ok" for s in saves)
    inversions = sum(b["ts"] < a["ts"] for a, b in zip(saves, saves[1:]))

    reg = [s["el_ms"] for s in prim]
    delta = [s["delta_ms"] for s in prim]
    delta_p = [s["delta_p_ms"] for s in prim]
    unmatched_slow = sum(s["delta_ms"] is None and s["el_ms"] is not None
                         and s["el_ms"] >= G7_FAST_MS for s in prim)
    registered = _g7_block(reg, boot_b, seed)
    reg_known = sorted(v for v in reg if v is not None)
    registered["nearest_to_threshold_s"] = {
        "largest_under_20s": _sec(max((v for v in reg_known if v < G7_FAST_MS), default=None)),
        "smallest_at_or_over_20s": _sec(min((v for v in reg_known if v >= G7_FAST_MS),
                                            default=None))}
    whole = _g7_block(delta, boot_b, seed)
    whole["n_unmatched_primary_cells_elapsed_at_or_over_20s"] = unmatched_slow
    sub = _g7_block(delta_p, boot_b, seed)
    sub["n_unmatched_primary_cells_elapsed_at_or_over_20s"] = unmatched_slow
    crossing = {"whole_second": _crossing(reg, delta), "sub_second": _crossing(reg, delta_p)}

    allowed = (G7_FAST_PCT_BELOW * len(reg_known) - 1) // 100  # most cells under 20 s G7 tolerates
    if reg_known and allowed < len(reg_known):
        limiting = reg_known[allowed]
        break_even = {
            "n_primary_cells": len(reg_known),
            "max_cells_under_20s_allowed": allowed,
            "limiting_rank": allowed + 1,
            "limiting_elapsed_s": _sec(limiting),
            "lead_s": _sec(max(G7_FAST_MS - limiting, 0)),
            "already_met": limiting >= G7_FAST_MS,
            "meaning": "uniform amount (s) added to every elapsed_s, i.e. a client clock ahead of "
                       "the server by this much, for fewer than 3% of primary cells to stay "
                       "under 20 s"}
    else:
        break_even = None

    return {
        "source": {
            "audit_jsonl_sha256": _sha256(audit_bytes),
            "session_log_sha256": _sha256(log_bytes),
            "reads": "ts, first_opened_ts, elapsed_s and session_id of each audit save record, "
                     "the cell_id prefix (control vs primary) and the session log's start/end "
                     "lines; no label, draft field, note or span is used",
            "writes": "aggregates only; no cell id, session id, label, note or span",
        },
        "method": {
            "elapsed_s_formula": ELAPSED_FORMULA,
            "delta": DELTA_DEFINITION,
            "skew_estimator": SKEW_DEFINITION,
            "g7_total_dwell_rule": "a cell's total dwell is the sum of elapsed_s over all its "
                                   "saves (analyze_holdout._g7, condition c); it is fast when "
                                   "under 20 s; G7 needs fewer than 3% fast primary cells "
                                   "(PREREG L349)",
            "bootstrap": {
                "statistic": "median", "resamples": boot_b, "seed": seed,
                "draw": "int(random.Random(seed).random() * n) for each of n draws with "
                        "replacement; a fresh generator per interval",
                "interval": "percentile: sorted resampled medians at index B*25//1000 and "
                            "B*975//1000"},
            "wilson": f"Wilson score interval, z = {Z975}",
            "quantiles": "linear interpolation between order statistics (numpy default)",
        },
        "population": {
            "n_audit_records": n_records,
            "n_save_records": len(saves),
            "n_session_event_records": n_events,
            "n_primary_cells": len(prim),
            "n_control_cells": len(saves) - len(prim),
            "n_cells_saved_more_than_once": n_dup,
            "n_sessions_with_saves": len(by_sid),
        },
        "formula_check": {
            "quantity": "ts - (first_opened + elapsed_s); expected in [-1.05, +0.15] s: ts is "
                        "the server clock truncated to whole seconds and written a few ms "
                        "after the save time, elapsed_s is rounded to 0.1 s",
            "n": len(tcheck),
            "min_s": _sec(min(tcheck)) if tcheck else None,
            "max_s": _sec(max(tcheck)) if tcheck else None,
            "n_outside_expected_range": n_outside,
        },
        "sessions": sessions,
        "elapsed_s_null_or_negative": {
            "n_saves": len(saves),
            "n_null": states.count("null"),
            "n_negative": states.count("negative"),
            "n_invalid": states.count("invalid"),
            "n_null_or_negative": states.count("null") + states.count("negative"),
            "n_zero": sum(v == 0 for v in known_el),
            "min_elapsed_s": _sec(min(known_el)) if known_el else None,
            "n_null_with_first_opened_ts_present": sum(
                s["el_state"] == "null" and s["fo_state"] != "missing" for s in saves),
            "n_first_opened_ts_missing": sum(s["fo_state"] == "missing" for s in saves),
            "n_first_opened_ts_unparsable": sum(s["fo_state"] == "unparsable" for s in saves),
        },
        "delta_upper_bound_check": {
            "n_saves_with_delta_and_elapsed": len(d_all),
            "n_elapsed_exceeds_delta_plus_1s": n_exceed,
            "reading": "0 means every row page loaded after the previous save, so delta bounds "
                       "the dwell from above",
        },
        "g7_under_20s": {
            "registered_basis_elapsed_s": registered,
            "delta_basis_whole_second": whole,
            "delta_basis_sub_second": sub,
            "cells_crossing_20s": crossing,
        },
        "break_even_client_lead": break_even,
        "checks": {
            "audit_sessions_all_in_session_log": all(sid in log_index for sid in by_sid),
            "saves_per_session_equal_session_log_saved": all(
                log_saved.get(sid) == len(lst) for sid, lst in by_sid.items()),
            "ts_nondecreasing_in_file_order": inversions == 0,
            "every_save_has_parsable_first_opened_ts": n_fo_bad == 0,
            "no_cell_saved_twice": n_dup == 0,
            "ts_consistent_with_first_opened_plus_elapsed": n_outside == 0,
            "elapsed_never_exceeds_delta_plus_1s": n_exceed == 0,
        },
        "caveats": CAVEATS,
    }


def main(argv: list) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: dwell_skew_check.py AUDIT.jsonl SESSION_LOG.txt")
    text = json.dumps(analyze(Path(argv[1]), Path(argv[2])), indent=1) + "\n"
    (HERE / OUT_NAME).write_bytes(text.encode("utf-8"))
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
