#!/usr/bin/env python3
"""Washout (G2) packet builder -- PREREG sec.12.3 (DN-2, DN-3, DN-4a, DN-7) and the
selection rules pinned in review.

INPUTS (all read-only): ``cells.jsonl`` (J, judge span, artifact_digest), the locked AH
working CSV (A_AH), the frozen paraphrase CSV, the CQ bank (original CQs, groundings), the
variants directory (original views), a semantic-check result file, and a SEALED salt file.
The registered seed is 20260913.

SEMANTIC-CHECK FILE (``--semantic-check``, PREREG sec.13.1 item 3): a CSV with the columns
``cq_id``, ``verdict`` (exactly ``pass`` or ``fail``), ``checker`` (an identifier or the initials of a
person other than the rater) and ``date``, one row for every row of the paraphrase file. The builder
refuses a file that lacks one of the four columns, repeats or omits a cq_id, has a verdict that is
not exactly pass or fail, or has an empty checker or date on any row; it says how many rows, never
which. Commit the file and its sha256 before the first washout save.

PARAPHRASE MODE. Default ``frozen_paraphrase``: every row shows the frozen paraphrase, except the rows
of a cluster that failed the check, which show the original CQ. ``--no-paraphrase-fallback`` (sec.13.1
item 3: no check by a person other than the rater by the washout date) needs no semantic-check file
and is mutually exclusive with ``--semantic-check``: every row shows the original CQ, and both the
sealed mapping and the rater-visible manifest say ``paraphrase_mode: "original_cq_fallback"``. The
frozen paraphrase file is still read (and pinned) in that mode: it tells what the judge saw on the
preserved controls.

SELECTION over the primary cells (strata = non-empty (category, J), sorted):
  1. Proportional layer, 48 cells. n_h = max(1, largest remainder): start from
     floor(48 N_h / N), add seats by largest remainder (ties: category ascending, then J
     ascending), raise every stratum to at least one seat, then remove any excess one seat at
     a time from the stratum with the largest current n_h (same tie order).
  2. One rng = random.Random(20260913): for each stratum in order ``rng.sample(sorted(ids),
     n_h)``; then ``rng.sample(sorted(D - S1), 24)`` with D = {cells with 1[J >= 2] != A_AH};
     when |D - S1| < 24 all of D - S1 is taken and the shortfall k is filled with
     ``rng.sample(sorted(remaining cells), k)`` (k is recorded).
  3. Inclusion probability pi_i = the share of 100000 reruns of the whole procedure, run r
     with random.Random(20260913 + r), r = 1..100000, that select cell i, rounded half-up to 4
     decimals; the weight is w_i = 1 / pi_i. A control is always included: pi = w = 1.

CONTROLS (DN-7): all 36. An ablated control's view is regenerated with
``run_holdout.ablate_rendered_view`` and shown only if its sha256 equals the cell's
``artifact_digest`` (otherwise the control is excluded and reported); a preserved control shows
the original view, under the same digest check. Every row shows the paraphrased CQ; the rows of a
cluster that failed the semantic check show the original CQ instead (primary and control alike).

OUTPUTS (three directories, three audiences)
  --packet-dir  (the rater gets THIS and nothing else)  washout_sheet.csv (12-column AH sheet
                format: opaque id in cell_id, CQ text, judge_evidence_span, an opaque view file name
                per ROW, empty label columns; cq_id/cluster_id/category/variant blank) and
                MANIFEST.json (sha256s and aggregate counts only; no layer or stratum counts).
  --server-dir  (the operator's label_assist process; refused inside the repository)  views/ with
                one file per row, named opaquely per row, and views.SHA256SUMS.txt. Both stay
                server-side: identical views would otherwise share a name or a digest, and each
                ablated control view is unique, which would single the controls out. The sums file
                lives beside views/ and is passed to label_assist as --sums.
  --sealed-dir  (sealed; refused inside the repository)  washout_mapping.json: one row per cell of
                the washout with cell_id (the opaque id the rater saw), source_cell_id (the id in
                cells.jsonl and the AH sheet), cell_kind, stratum (proportional | enriched |
                control), inclusion_prob, w = 1 / inclusion_prob (the rounded value), excluded_reason,
                position, selection, category_stratum, view file name. The columns cell_id,
                source_cell_id, cell_kind, stratum, inclusion_prob and excluded_reason are the ones
                ``analyze_washout.py --design`` reads (it accepts a JSON object with a ``rows``
                list); the rest are extra. An excluded control keeps a row with its reason. The
                rater never sees this file; its sha256 is in the manifest (commit that, not the file).
All sealed and server-side files are written with mode 0600 (directories 0700).
Opaque ids are hex(HMAC-SHA256(salt, cell_id))[:16] and cannot be derived without the salt; the
salt file holds at least 32 random bytes, is mode 0600 and lives outside the repository
(``--init-salt`` creates one). The order is the registered constrained shuffle (same CQ >= 20
positions apart where feasible; the achieved minimum is reported); its input is sorted by opaque id,
so the sealed position -> cell mapping cannot be rebuilt without the salt. Stdout carries counts
and hashes only, and an error never prints cell ids.

Serve with:  label_assist.py --packet --sheet <packet>/washout_sheet.csv
             --views <server-dir>/views --sums <server-dir>/views.SHA256SUMS.txt
             --out <path outside the repository>
(no --require-note: the washout takes the note as optional, sec.13.1 item 8; the second
annotator's command adds it.)
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import hmac
import io
import os
import random
import secrets
import stat
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The registered analyzer is imported, never edited: its loaders/guards define how the cells and
# the AH labels are read. run_holdout owns the ablation. label_assist owns the repo guard.
import analyze_holdout as ah  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import packet_common as pc  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import run_holdout as rh  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

REAL_RUN = pc.HERE / "real_run"
BANK_DIR = pc.ACCESS / "bank"
SEED = pc.REGISTERED_SEED
N_PROPORTIONAL = 48
N_ENRICHED = 24
PI_RUNS = 100_000
PI_DECIMALS = 4
G3W_MIN_VALID_ABLATED = 24
OPAQUE_HEX = 16
SALT_MIN_BYTES = 32
SHEET_NAME = "washout_sheet.csv"
MAPPING_NAME = "washout_mapping.json"
MANIFEST_NAME = "MANIFEST.json"
VIEWS_DIR = "views"
SUMS_NAME = "views.SHA256SUMS.txt"
SALT_BYTES = 32
SEMANTIC_COLUMNS = ("cq_id", "verdict", "checker", "date")
PARAPHRASE_FROZEN = "frozen_paraphrase"
PARAPHRASE_ORIGINAL = "original_cq_fallback"
G3W_NOT_JUDGED = "G3-W not judged (n_valid < 24)"
G3W_JUDGEABLE = "G3-W judgeable (n_valid = 24)"
PINNED_CELLS_SHA256 = "bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af"
PINNED_AH_LABELS_SHA256 = "60347b3fa1b591ba74695602656007eebc342b29e57aad1c80476760f1d6bae2"
PINNED_PARAPHRASES_SHA256 = "c02ecda3f2c6c3c27dc47e7f4845ac57739d5d85b059bfa813328c125682341f"
PINNED_BANK_SHA256 = "993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507"
CONTROL_KINDS = tuple(ah.CONTROL_CELL_KINDS)  # ablated_control, preserved_control


class WashoutError(Exception):
    """A refusal: an input or an output location does not satisfy the registered rules."""


# --------------------------------------------------------------------------
# selection (pure functions of the pool and an rng)
# --------------------------------------------------------------------------
Stratum = tuple[str, int]


def allocate_proportional(sizes: dict[Stratum, int], n_total: int) -> dict[Stratum, int]:
    """n_h = max(1, largest remainder), then trim to ``n_total``. Exact (Fraction) arithmetic;
    ties go to the smaller (category, J). Raises when ``n_total`` cannot hold one seat per
    non-empty stratum."""
    keys = sorted(k for k, n in sizes.items() if n > 0)
    population = sum(sizes[k] for k in keys)
    if not keys:
        raise WashoutError("no non-empty stratum")
    if n_total > population:
        raise WashoutError(f"{n_total} seats requested from {population} cells")
    quota = {k: Fraction(n_total * sizes[k], population) for k in keys}
    alloc = {k: quota[k].numerator // quota[k].denominator for k in keys}
    seats = n_total - sum(alloc.values())
    for k in sorted(keys, key=lambda key: (-(quota[key] - alloc[key]), key))[:seats]:
        alloc[k] += 1
    for k in keys:
        alloc[k] = max(1, alloc[k])
    while sum(alloc.values()) > n_total:
        above_one = [k for k in keys if alloc[k] > 1]
        if not above_one:
            raise WashoutError(f"{len(keys)} non-empty strata exceed the {n_total} proportional seats")
        biggest = max(alloc[k] for k in above_one)
        alloc[min(k for k in above_one if alloc[k] == biggest)] -= 1
    for k in keys:
        if alloc[k] > sizes[k]:
            raise WashoutError("a stratum was allocated more seats than it has cells")
    return {k: alloc[k] for k in keys}


@dataclass(frozen=True)
class Design:
    """Everything the draw depends on, fixed before any rng is touched."""
    keys: tuple[Stratum, ...]
    ids: dict[Stratum, list[str]]            # sorted cell ids per stratum
    alloc: dict[Stratum, int]
    pool_sorted: list[str]
    discordant_sorted: list[str]             # D = {1[J >= 2] != A_AH}, sorted
    n_enriched: int
    stratum_of: dict[str, Stratum]


@dataclass(frozen=True)
class Selection:
    proportional: list[str]                  # S1, stratum order
    enriched: list[str]                      # sample of D - S1 (or all of it on a shortfall)
    fill: list[str]                          # shortfall filled from the remaining cells

    def all_ids(self) -> list[str]:
        return self.proportional + self.enriched + self.fill


def build_design(pool: list[dict], n_proportional: int, n_enriched: int) -> Design:
    """``pool``: dicts with cell_id, category, J (int 0..3) and A_AH (int 0/1)."""
    by_stratum: dict[Stratum, list[str]] = collections.defaultdict(list)
    stratum_of: dict[str, Stratum] = {}
    discordant: list[str] = []
    for cell in pool:
        key = (str(cell["category"]), int(cell["J"]))
        if cell["cell_id"] in stratum_of:
            raise WashoutError("duplicate primary cell_id")
        by_stratum[key].append(cell["cell_id"])
        stratum_of[cell["cell_id"]] = key
        if int(int(cell["J"]) >= 2) != int(cell["A_AH"]):
            discordant.append(cell["cell_id"])
    sizes = {k: len(v) for k, v in by_stratum.items()}
    alloc = allocate_proportional(sizes, n_proportional)
    keys = tuple(sorted(alloc))
    return Design(keys=keys, ids={k: sorted(by_stratum[k]) for k in keys}, alloc=alloc,
                  pool_sorted=sorted(stratum_of), discordant_sorted=sorted(discordant),
                  n_enriched=n_enriched, stratum_of=stratum_of)


def select_once(design: Design, rng: random.Random) -> Selection:
    """One run of the registered procedure with the given rng (all draws from this one rng)."""
    s1: list[str] = []
    for key in design.keys:
        s1.extend(rng.sample(design.ids[key], design.alloc[key]))
    taken = set(s1)
    rest = [c for c in design.discordant_sorted if c not in taken]       # sorted(D - S1)
    if len(rest) >= design.n_enriched:
        return Selection(s1, rng.sample(rest, design.n_enriched), [])
    shortfall = design.n_enriched - len(rest)
    taken.update(rest)
    remaining = [c for c in design.pool_sorted if c not in taken]        # sorted(remaining)
    if shortfall > len(remaining):
        raise WashoutError("fewer remaining cells than the shortfall to fill")
    return Selection(s1, list(rest), rng.sample(remaining, shortfall))


def inclusion_probabilities(design: Design, seed: int = SEED, n_runs: int | None = None,
                            decimals: int = PI_DECIMALS) -> dict[str, Decimal]:
    """pi_i = share of the reruns r = 1..n_runs (rng = random.Random(seed + r)) whose selection
    contains cell i, rounded half-up to ``decimals`` places (exact decimal arithmetic)."""
    n_runs = PI_RUNS if n_runs is None else n_runs
    counts: collections.Counter[str] = collections.Counter()
    for r in range(1, n_runs + 1):
        counts.update(select_once(design, random.Random(seed + r)).all_ids())
    return {cid: round_share(counts[cid], n_runs, decimals) for cid in design.pool_sorted}


def round_share(count: int, n_runs: int, decimals: int = PI_DECIMALS) -> Decimal:
    """count / n_runs rounded half-up to ``decimals`` places, in exact decimal arithmetic (a
    binary float would round 0.03125 to 0.0312)."""
    return (Decimal(count) / Decimal(n_runs)).quantize(Decimal(1).scaleb(-decimals),
                                                     rounding=ROUND_HALF_UP)


# --------------------------------------------------------------------------
# opaque ids, sheet text
# --------------------------------------------------------------------------
def read_salt(path: Path) -> bytes:
    """The salt file's exact bytes (no stripping). It must hold at least 32 bytes and must not be
    readable by group or others: a weak or shared salt lets anyone with the public cell ids
    rebuild the opaque ids and the sealed mapping."""
    path = Path(path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise WashoutError(f"the salt file is accessible to group/others (mode {mode:04o}); chmod 600 it")
    salt = path.read_bytes()
    if len(salt) < SALT_MIN_BYTES:
        raise WashoutError(f"the salt file holds {len(salt)} bytes; at least {SALT_MIN_BYTES} are needed")
    return salt


def create_salt_file(path: Path) -> None:
    """--init-salt: SALT_BYTES random bytes from ``secrets``, mode 0600, never over an existing file,
    never inside the repository."""
    path = Path(path)
    refuse_inside_repo(path, "the salt file")
    if path.exists():
        raise WashoutError("the salt file already exists; it is never overwritten")
    made = not path.parent.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    if made:
        os.chmod(path.parent, 0o700)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(secrets.token_bytes(SALT_BYTES))
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(path, 0o600)
    pc.fsync_dir(path.parent)


def opaque_id(salt: bytes, cell_id: str) -> str:
    return hmac.new(salt, cell_id.encode("utf-8"), hashlib.sha256).hexdigest()[:OPAQUE_HEX]


def view_ref(salt: bytes, opaque: str) -> str:
    """The view file name of ONE row: opaque, and different for every row even when two rows show
    the same view. A name shared by exactly the primary and preserved rows, with a unique name for
    every ablated control, would give the controls away in the sheet's rendered_view_path column."""
    return "v_" + hmac.new(salt, b"view-row:" + opaque.encode("ascii"), hashlib.sha256).hexdigest()[:OPAQUE_HEX] + ".txt"


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------
def _read_dict_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise WashoutError(f"{Path(path).name}: columns missing: {missing}")
        return [{k.strip(): (v or "") for k, v in row.items() if k is not None} for row in reader]


def read_semantic_check(path: Path, cq_ids: set[str]) -> dict[str, bool]:
    """cq_id -> equivalent? From a CSV with the columns cq_id, verdict, checker and date (PREREG sec.13.1
    item 3; further columns are ignored). Complete and unambiguous: all four columns, one row for every
    paraphrase row, no unknown or repeated cq_id, a verdict that is exactly ``pass`` or ``fail`` and a
    non-empty checker and date on every row. Messages give counts and column names, never ids or values."""
    rows = _read_dict_csv(path, SEMANTIC_COLUMNS)
    verdicts: dict[str, bool] = {}
    n_bad_verdict = n_unattributed = 0
    for row in rows:
        cq = row["cq_id"].strip()
        if cq in verdicts:
            raise WashoutError("semantic-check file repeats a cq_id")
        if row["verdict"] not in ("pass", "fail"):
            n_bad_verdict += 1
        if not row["checker"].strip() or not row["date"].strip():
            n_unattributed += 1
        verdicts[cq] = row["verdict"] == "pass"
    if n_bad_verdict:
        raise WashoutError(f"{n_bad_verdict} semantic-check rows have a verdict that is not exactly pass or fail")
    if n_unattributed:
        raise WashoutError(f"{n_unattributed} semantic-check rows have an empty checker or date")
    if set(verdicts) != cq_ids:
        raise WashoutError(f"semantic-check file covers {len(set(verdicts) & cq_ids)} of "
                           f"{len(cq_ids)} paraphrase rows (unknown ids: {len(set(verdicts) - cq_ids)})")
    return verdicts


def paraphrase_mode_for(semantic_path: Path | None, no_paraphrase_fallback: bool) -> str:
    """The paraphrase mode a build runs in: the frozen paraphrase with a semantic-check file, or the
    original CQ everywhere without one (--no-paraphrase-fallback). The two are mutually exclusive."""
    if no_paraphrase_fallback and semantic_path is not None:
        raise WashoutError("--no-paraphrase-fallback and --semantic-check are mutually exclusive "
                           "(the fallback needs no semantic-check file)")
    if not no_paraphrase_fallback and semantic_path is None:
        raise WashoutError("a semantic-check file is required; without one, build with "
                           "--no-paraphrase-fallback (every row then shows the original CQ)")
    return PARAPHRASE_ORIGINAL if no_paraphrase_fallback else PARAPHRASE_FROZEN


@dataclass
class Inputs:
    primary: list[dict]
    controls: list[dict]
    paraphrase: dict[str, dict[str, str]]     # cq_id -> row (cluster_id, paraphrase_text, ...)
    bank: dict[str, dict[str, str]]           # cq_id -> row (question, grounding, ...)
    failed_clusters: set[str]
    n_semantic_pass: int | None               # None: no semantic-check file (the fallback)
    n_semantic_fail: int | None
    variant_views: dict[str, str]
    registered_design: dict
    hashes: dict[str, str]
    paraphrase_mode: str = PARAPHRASE_FROZEN


def _check_sha(label: str, path: Path, expected: str | None, hashes: dict[str, str]) -> None:
    actual = pc.sha256_file(path)
    hashes[label] = actual
    if expected is not None and actual != expected:
        raise WashoutError(f"{label} sha256 {actual} is not the registered/recorded {expected}")


def load_inputs(*, cells_path: Path, labels_path: Path, paraphrases_path: Path, bank_path: Path,
                semantic_path: Path | None, variants_dir: Path, allow_partial: bool = False,
                expected: dict[str, str | None] | None = None,
                no_paraphrase_fallback: bool = False) -> Inputs:
    mode = paraphrase_mode_for(semantic_path, no_paraphrase_fallback)
    expected = expected or {}
    hashes: dict[str, str] = {}
    _check_sha("cells_jsonl", cells_path, expected.get("cells_jsonl"), hashes)
    _check_sha("ah_labels_locked_working_csv", labels_path, expected.get("ah_labels"), hashes)
    _check_sha("paraphrases_csv", paraphrases_path, expected.get("paraphrases"), hashes)
    _check_sha("bank_csv", bank_path, expected.get("bank"), hashes)
    if semantic_path is not None:
        _check_sha("semantic_check", semantic_path, None, hashes)

    cells = ah.load_cells(cells_path, require_a=False)
    primary_raw, controls_by_kind = ah.split_primary_and_controls(cells)
    controls_raw = [c for kind in CONTROL_KINDS for c in controls_by_kind[kind]]
    ah._assert_unique_primary_pairing(primary_raw)
    invalid = ah.invalid_judge_cell_ids(cells)
    if invalid:
        raise WashoutError(f"{len(invalid)} primary cells have an invalid judge call")
    design_summary, _ = ah.check_registered_design(primary_raw)
    if not design_summary["conforms"] and not allow_partial:
        raise WashoutError("the primary cell set is not the registered 188-cell design "
                           "(--allow-partial overrides, for synthetic fixtures only)")

    try:
        labels = ah.load_label_csv(labels_path, label_source="human",
                                   tolerate_ids=[c["cell_id"] for c in controls_raw])
    except ValueError:  # its message lists cell ids; keep them off the terminal
        raise WashoutError("AH label CSV rejected by analyze_holdout.load_label_csv "
                           "(details withheld: they name cell ids; run the loader on the file to see them)") from None
    unknown = set(labels.labels) - {c["cell_id"] for c in cells}
    if unknown:
        raise WashoutError(f"the AH label CSV names {len(unknown)} cells that are not in cells.jsonl")

    keep = ("cell_id", "cell_kind", "cq_id", "cluster_id", "category", "variant", "artifact_digest")
    primary: list[dict] = []
    for raw in primary_raw:
        a = labels.labels.get(raw["cell_id"])
        if a not in (0, 1):
            raise WashoutError("a primary cell has no AH label")
        row = {k: str(raw[k]) for k in keep if k != "cell_kind"}
        row.update(cell_kind="primary", J=int(raw["J"]), A_AH=int(a),
                   evidence=pc.registered_shuffle_module()._judge_evidence(raw))
        primary.append(row)
    controls: list[dict] = []
    for raw in controls_raw:
        row = {k: str(raw[k]) for k in keep}
        row["evidence"] = pc.registered_shuffle_module()._judge_evidence(raw)
        controls.append(row)

    paraphrase_rows = _read_dict_csv(paraphrases_path, ("cq_id", "cluster_id", "paraphrase_text"))
    paraphrase = {r["cq_id"]: r for r in paraphrase_rows}
    if len(paraphrase) != len(paraphrase_rows):
        raise WashoutError("the paraphrase file repeats a cq_id")
    bank_rows = _read_dict_csv(bank_path, ("cq_id", "question", "grounding"))
    bank = {r["cq_id"]: r for r in bank_rows}
    verdicts = read_semantic_check(semantic_path, set(paraphrase)) if semantic_path is not None else {}
    failed = {paraphrase[cq]["cluster_id"] for cq, ok in verdicts.items() if not ok}

    needed = {c["cq_id"] for c in primary + controls}
    if not needed <= set(paraphrase) or not needed <= set(bank):
        raise WashoutError("a cell's cq_id is missing from the paraphrase file or the bank")
    for cell in primary + controls:
        if paraphrase[cell["cq_id"]]["cluster_id"] != cell["cluster_id"]:
            raise WashoutError("a cell's cluster_id differs from its paraphrase row's cluster_id")
    variant_views: dict[str, str] = {}
    for variant in sorted({c["variant"] for c in primary + controls}):
        view_path = Path(variants_dir) / variant / "rendered_view.txt"
        if not view_path.is_file():
            raise WashoutError(f"no original view for variant {variant!r}")
        variant_views[variant] = view_path.read_text(encoding="utf-8")   # as run_holdout read it
    return Inputs(primary=primary, controls=controls, paraphrase=paraphrase, bank=bank,
                  failed_clusters=failed,
                  n_semantic_pass=sum(1 for ok in verdicts.values() if ok) if semantic_path is not None else None,
                  n_semantic_fail=sum(1 for ok in verdicts.values() if not ok) if semantic_path is not None else None,
                  variant_views=variant_views, registered_design=design_summary, hashes=hashes,
                  paraphrase_mode=mode)


# --------------------------------------------------------------------------
# rows
# --------------------------------------------------------------------------
def _digest(view: str) -> str:
    return hashlib.sha256(view.encode()).hexdigest()   # exactly how run_holdout hashes a view


def _cq_text(inputs: Inputs, cell: dict) -> tuple[str, str]:
    if inputs.paraphrase_mode == PARAPHRASE_ORIGINAL or cell["cluster_id"] in inputs.failed_clusters:
        return inputs.bank[cell["cq_id"]]["question"], "original"
    return inputs.paraphrase[cell["cq_id"]]["paraphrase_text"], "paraphrase"


def _judge_question(inputs: Inputs, cell: dict) -> str:
    """The CQ text the judge saw: the paraphrase for a preserved control, else the bank text."""
    if cell["cell_kind"] == "preserved_control":
        return inputs.paraphrase[cell["cq_id"]]["paraphrase_text"]
    return inputs.bank[cell["cq_id"]]["question"]


def control_view(inputs: Inputs, cell: dict) -> tuple[str | None, str | None]:
    """(view text, None) when the control's view reproduces the judge's artifact_digest, else
    (None, reason)."""
    original = inputs.variant_views[cell["variant"]]
    if cell["cell_kind"] == "ablated_control":
        try:
            view = rh.ablate_rendered_view(original, inputs.bank[cell["cq_id"]])
        except ValueError:
            return None, "ablation_failed"
    else:
        view = original
    if _digest(view) != cell["artifact_digest"]:
        return None, "digest_mismatch"
    return view, None


def assemble_rows(inputs: Inputs, design: Design, selection: Selection,
                  pi: dict[str, Decimal], salt: bytes) -> tuple[list[dict], list[dict]]:
    """Rows of the washout (before ordering) and the excluded controls."""
    primary_by_id = {c["cell_id"]: c for c in inputs.primary}
    layer_of = {**{c: "proportional" for c in selection.proportional},
                **{c: "enriched" for c in selection.enriched},
                **{c: "enriched" for c in selection.fill}}
    how = {**{c: "proportional" for c in selection.proportional},
           **{c: "enriched" for c in selection.enriched},
           **{c: "shortfall_fill" for c in selection.fill}}
    rows: list[dict] = []
    for cid in sorted(selection.all_ids()):
        cell = primary_by_id[cid]
        view = inputs.variant_views[cell["variant"]]
        if _digest(view) != cell["artifact_digest"]:
            raise WashoutError("a primary cell's original view does not reproduce the judge's artifact_digest")
        p = pi[cid]
        if p <= 0:
            raise WashoutError("a selected cell has an inclusion probability that rounds to 0")
        text, source = _cq_text(inputs, cell)
        key = design.stratum_of[cid]
        rows.append({
            "cell": cell, "cell_id": cid, "cq_id": cell["cq_id"], "cell_kind": "primary",
            "selection": how[cid], "layer": layer_of[cid], "category_stratum": f"{key[0]}|J{key[1]}",
            "pi": float(p), "w": 1.0 / float(p), "view": view, "cq_text": text,
            "cq_text_source": source,
            "cq_shown_differs_from_judge_input": text != _judge_question(inputs, cell)})
    excluded: list[dict] = []
    for cell in sorted(inputs.controls, key=lambda c: c["cell_id"]):
        view, reason = control_view(inputs, cell)
        if view is None:
            excluded.append({"cell_id": cell["cell_id"], "cell_kind": cell["cell_kind"], "reason": reason})
            continue
        text, source = _cq_text(inputs, cell)
        rows.append({
            "cell": cell, "cell_id": cell["cell_id"], "cq_id": cell["cq_id"],
            "cell_kind": cell["cell_kind"], "selection": "control", "layer": None,
            "category_stratum": "", "pi": 1.0, "w": 1.0,
            "view": view, "cq_text": text, "cq_text_source": source,
            "cq_shown_differs_from_judge_input": text != _judge_question(inputs, cell)})
    for row in rows:
        row["opaque_id"] = opaque_id(salt, row["cell_id"])
        row["view_digest"] = _digest(row["view"])
        row["view_ref"] = view_ref(salt, row["opaque_id"])
    if len({r["opaque_id"] for r in rows}) != len(rows) or len({r["view_ref"] for r in rows}) != len(rows):
        raise WashoutError("opaque id or view name collision; use another salt")
    return rows, excluded


def sheet_row(row: dict) -> list[str]:
    """The rater-visible 12-column row: nothing that names the cell, its CQ id, category or
    variant; the label columns empty."""
    return [row["opaque_id"], "", "", "", "", row["cq_text"], row["cell"]["evidence"],
            row["view_ref"], "", "", "", ""]


def sheet_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)   # default dialect (CRLF): the AH sheet's
    writer.writerow(list(la.SHEET_COLUMNS))
    writer.writerows(sheet_row(r) for r in rows)
    return buf.getvalue().encode("utf-8")


# --------------------------------------------------------------------------
# guards
# --------------------------------------------------------------------------
def refuse_inside_repo(path: Path, what: str) -> None:
    try:
        la.check_out_path(Path(path))
    except la.OutInsideRepo:
        raise WashoutError(f"{what} would be inside the repository tree: {path}") from None


def _contains(parent: Path, child: Path) -> bool:
    parent, child = Path(parent).resolve(), Path(child).resolve()
    return parent == child or parent in child.parents


def check_locations(*, sealed_dir: Path, packet_dir: Path, server_dir: Path, salt_file: Path,
                    inputs: dict[str, Path]) -> None:
    refuse_inside_repo(sealed_dir, "the sealed output directory")
    refuse_inside_repo(server_dir, "the server-side output directory")
    refuse_inside_repo(salt_file, "the salt file")
    dirs = {"sealed": sealed_dir, "packet": packet_dir, "server": server_dir}
    names = list(dirs)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            if _contains(dirs[first], dirs[second]) or _contains(dirs[second], dirs[first]):
                raise WashoutError(f"the {first} and {second} directories must not contain one another")
    if _contains(packet_dir, salt_file):
        raise WashoutError("the salt file must not sit inside the rater-visible packet directory")
    if _contains(server_dir, salt_file):
        raise WashoutError("the salt file must not sit inside the server-side directory")
    outputs = {"mapping": Path(sealed_dir) / MAPPING_NAME, "sheet": Path(packet_dir) / SHEET_NAME,
               "manifest": Path(packet_dir) / MANIFEST_NAME, "sums": Path(server_dir) / SUMS_NAME}
    try:
        ah._refuse_outputs_that_are_inputs(outputs, {**inputs, "--salt-file": salt_file})
    except SystemExit as exc:   # analyze_holdout's guard exits; here it is a refusal like the others
        raise WashoutError(str(exc)) from None


# --------------------------------------------------------------------------
# the build
# --------------------------------------------------------------------------
def build(*, cells_path: Path, labels_path: Path, paraphrases_path: Path, bank_path: Path,
          semantic_path: Path | None = None, variants_dir: Path, salt_file: Path, sealed_dir: Path,
          packet_dir: Path, server_dir: Path, seed: int = SEED, allow_partial: bool = False,
          force: bool = False,
          expected: dict[str, str | None] | None = None,
          n_proportional: int | None = None, n_enriched: int | None = None,
          n_runs: int | None = None, no_paraphrase_fallback: bool = False) -> dict:
    paraphrase_mode_for(semantic_path, no_paraphrase_fallback)   # refuse a bad combination before anything else
    n_proportional = N_PROPORTIONAL if n_proportional is None else n_proportional
    n_enriched = N_ENRICHED if n_enriched is None else n_enriched
    n_runs = PI_RUNS if n_runs is None else n_runs
    sealed_dir, packet_dir, server_dir = Path(sealed_dir), Path(packet_dir), Path(server_dir)
    input_paths = {"--cells": Path(cells_path), "--ah-labels": Path(labels_path),
                   "--paraphrases": Path(paraphrases_path), "--bank": Path(bank_path)}
    if semantic_path is not None:
        input_paths["--semantic-check"] = Path(semantic_path)
    check_locations(sealed_dir=sealed_dir, packet_dir=packet_dir, server_dir=server_dir,
                    salt_file=Path(salt_file), inputs=input_paths)
    salt = read_salt(salt_file)
    inputs = load_inputs(cells_path=cells_path, labels_path=labels_path,
                         paraphrases_path=paraphrases_path, bank_path=bank_path,
                         semantic_path=semantic_path, variants_dir=variants_dir,
                         allow_partial=allow_partial, expected=expected,
                         no_paraphrase_fallback=no_paraphrase_fallback)

    pool = [{k: c[k] for k in ("cell_id", "category", "J", "A_AH")} for c in inputs.primary]
    design = build_design(pool, n_proportional, n_enriched)
    selection = select_once(design, random.Random(seed))
    pi = inclusion_probabilities(design, seed=seed, n_runs=n_runs)
    rows, excluded = assemble_rows(inputs, design, selection, pi, salt)

    # The shuffle is a function of its input order. Sorting by the OPAQUE id (which needs the salt)
    # keeps the sealed position -> cell mapping from being rebuilt with a throwaway salt; for a fixed
    # salt the order is still deterministic. The registration does not pin the input order.
    ordered, order_report = pc.constrained_order(sorted(rows, key=lambda r: r["opaque_id"]), seed,
                                                 pc.REGISTERED_MIN_GAP)
    order_report["shuffle_input_order"] = "opaque_id ascending (depends on the sealed salt)"
    for position, row in enumerate(ordered, start=1):
        row["position"] = position
    sheet_data = sheet_bytes(ordered)

    view_files: dict[str, bytes] = {}   # one file per row, so len(view_files) == len(ordered)
    for row in ordered:
        view_files[row["view_ref"]] = row["view"].encode("utf-8")
        if hashlib.sha256(view_files[row["view_ref"]]).hexdigest() != row["view_digest"]:
            raise WashoutError("a view file does not hash to its artifact digest")
    sums_data = "".join(f"{pc.sha256_bytes(view_files[name])}  {name}\n"
                        for name in sorted(view_files)).encode("utf-8")

    kinds = collections.Counter(r["cell_kind"] for r in ordered)
    excluded_kinds = collections.Counter(e["cell_kind"] for e in excluded)
    n_valid_ablated = kinds["ablated_control"]
    g3w = {"n_valid_ablated": n_valid_ablated,
           "n_ablated_controls_in_cells": n_valid_ablated + excluded_kinds["ablated_control"],
           "required_n_valid": G3W_MIN_VALID_ABLATED,
           "status": G3W_JUDGEABLE if n_valid_ablated >= G3W_MIN_VALID_ABLATED else G3W_NOT_JUDGED}
    selection_counts = collections.Counter(r["selection"] for r in ordered)
    ablated_differs = sum(1 for r in ordered if r["cell_kind"] == "ablated_control"
                          and r["cq_shown_differs_from_judge_input"])

    mapping_rows = [
        {"cell_id": r["opaque_id"], "source_cell_id": r["cell_id"], "cell_kind": r["cell_kind"],
         "stratum": ("control" if r["cell_kind"] != "primary" else r["layer"]),
         "inclusion_prob": r["pi"], "w": r["w"], "excluded_reason": "",
         "position": r["position"], "selection": r["selection"],
         "category_stratum": r["category_stratum"], "view_ref": r["view_ref"],
         "cq_text_source": r["cq_text_source"],
         "cq_shown_differs_from_judge_input": r["cq_shown_differs_from_judge_input"]}
        for r in ordered]
    mapping_rows += [
        {"cell_id": opaque_id(salt, e["cell_id"]), "source_cell_id": e["cell_id"],
         "cell_kind": e["cell_kind"], "stratum": "control", "inclusion_prob": 1.0, "w": 1.0,
         "excluded_reason": e["reason"], "position": None, "selection": "control",
         "category_stratum": "", "view_ref": None, "cq_text_source": None,
         "cq_shown_differs_from_judge_input": None}
        for e in sorted(excluded, key=lambda e: e["cell_id"])]
    if len({m["cell_id"] for m in mapping_rows}) != len(mapping_rows):
        raise WashoutError("opaque id collision among the design rows; use another salt")
    mapping = {
        "kind": "washout_mapping", "sealed": True,
        "warning": "SEALED until the washout labels are locked (PREREG sec.12.3 exposure rule). "
                   "Only the sha256 of this file is published.",
        "schema": {
            "cell_id": "the opaque id the rater saw: hex(HMAC-SHA256(salt, source_cell_id))[:16]; "
                       "the sheet's cell_id column and the key of the washout label sheet",
            "source_cell_id": "the cell's id in cells.jsonl and in the AH sheet",
            "cell_kind": "primary | ablated_control | preserved_control",
            "stratum": "primary rows: proportional (the first layer) or enriched (the second layer, "
                       "shortfall fill included); control rows: control",
            "inclusion_prob": f"share of {n_runs} reruns of the whole selection, run r with "
                              f"random.Random({seed}+r), r=1..{n_runs}, that select the cell; "
                              f"{PI_DECIMALS} decimals, half-up; 1.0 for a control",
            "w": "1 / inclusion_prob (the rounded value)",
            "excluded_reason": "empty for a cell that was shown; a control that failed the digest "
                               "check keeps its row with the reason and was not shown",
            "paraphrase_mode": f"{PARAPHRASE_FROZEN} (every row shows the frozen paraphrase, the original "
                               "CQ on the rows of a cluster whose check failed) | "
                               f"{PARAPHRASE_ORIGINAL} (--no-paraphrase-fallback: every row shows the "
                               "original CQ; no semantic-check file)",
            "selection": "proportional | enriched | shortfall_fill | control",
            "category_stratum": "category|J<score> of a primary cell, empty for a control",
            "position": "1-based place in the sheet, null when not shown"},
        "paraphrase_mode": inputs.paraphrase_mode,
        "seed": seed, "n_proportional": n_proportional, "n_enriched": n_enriched,
        "pi_runs": n_runs, "pi_decimals": PI_DECIMALS,
        "design": {
            "allocation": [{"category": k[0], "J": k[1], "N": len(design.ids[k]), "n": design.alloc[k]}
                           for k in design.keys],
            "n_discordant_pool": len(design.discordant_sorted),
            "n_discordant_after_proportional": len(set(design.discordant_sorted)
                                                   - set(selection.proportional)),
            "n_shortfall_filled": len(selection.fill),
            "layer_rows": {"proportional": selection_counts["proportional"],
                           "enriched": selection_counts["enriched"],
                           "shortfall_fill": selection_counts["shortfall_fill"]},
            "n_controls_excluded": len(excluded),
            "sum_w_primary": round(sum(r["w"] for r in ordered if r["cell_kind"] == "primary"), 6)},
        "inputs_sha256": inputs.hashes,
        "rows": mapping_rows,
    }
    mapping_data = pc.canonical_json(mapping)

    n_paraphrase = sum(1 for r in ordered if r["cq_text_source"] == "paraphrase")
    manifest = {
        "kind": "washout_packet_manifest",
        "spec": "PREREG.md sec.12.3 (DN-2, DN-3, DN-4a, DN-7); built by harness/build_washout_packet.py",
        "contents_statement": "Hashes and aggregate counts only. This manifest holds no J, no AH "
                              "label, no layer or stratum count, no cell id, no per-view digest and "
                              "no mapping row. The rater-visible sheet holds no label, no draft and "
                              "no translation; its judge_evidence_span is the span the judge quoted "
                              "(not a score), and its view file names are opaque and different for "
                              "every row.",
        "seed": seed,
        "paraphrase_mode": inputs.paraphrase_mode,
        "paraphrase_mode_statement": (
            "Every row shows the original CQ. No semantic-equivalence check by a person other than the "
            "rater was finished by the washout date, so the build ran with --no-paraphrase-fallback "
            "(PREREG sec.13.1 item 3); there is no semantic-check file."
            if inputs.paraphrase_mode == PARAPHRASE_ORIGINAL else
            "Every row shows the frozen paraphrase, except the rows of a cluster that failed the "
            "semantic-equivalence check by a person other than the rater, which show the original CQ "
            "(PREREG sec.12.3 DN-2, sec.13.1 item 3)."),
        "counts": {
            "rows_total": len(ordered),
            "primary_rows": kinds["primary"],
            "controls_included": {"ablated": kinds["ablated_control"], "preserved": kinds["preserved_control"]},
            "controls_excluded": {"ablated": excluded_kinds["ablated_control"],
                                  "preserved": excluded_kinds["preserved_control"]},
            "rows_showing_paraphrase": n_paraphrase,
            "rows_showing_original_cq": len(ordered) - n_paraphrase,
            "semantic_check": ({"pass": inputs.n_semantic_pass, "fail": inputs.n_semantic_fail}
                               if inputs.paraphrase_mode == PARAPHRASE_FROZEN else None),
            "ablated_control_rows_whose_cq_differs_from_judge_input": ablated_differs,
            "registered_design_conforms": inputs.registered_design["conforms"],
        },
        "g3w": g3w,
        "order": order_report,
        "inclusion_probability": {"runs": n_runs, "decimals": PI_DECIMALS, "rounding": "half-up",
                                  "rng": f"random.Random({seed}+r), r=1..{n_runs}; w=1/pi"},
        "opaque_id": f"hex(HMAC-SHA256(salt, cell_id))[:{OPAQUE_HEX}]; the salt file is sealed and "
                     "not hashed here",
        "inputs": {k: {"sha256": v} for k, v in sorted(inputs.hashes.items())},
        "outputs": {
            SHEET_NAME: {"sha256": pc.sha256_bytes(sheet_data), "rows": len(ordered)},
            f"sealed/{MAPPING_NAME}": {"sha256": pc.sha256_bytes(mapping_data)},
            f"server/{SUMS_NAME}": {"sha256": pc.sha256_bytes(sums_data),
                                    "n_view_files": len(view_files)},
        },
        "serving": "the rater receives the sheet only; the operator serves it with label_assist.py "
                   f"--packet --views <server dir>/{VIEWS_DIR} --sums <server dir>/{SUMS_NAME}",
        "tool": pc.provenance(Path(__file__), {"analyze_holdout.py": Path(ah.__file__),
                                               "run_holdout.py": Path(rh.__file__),
                                               "label_assist.py": Path(la.__file__)}),
    }
    manifest_data = pc.canonical_json(manifest)

    pc.ensure_private_dir(sealed_dir)
    pc.ensure_private_dir(server_dir)
    pc.ensure_private_dir(server_dir / VIEWS_DIR)
    status = {
        "mapping": pc.write_checked(sealed_dir / MAPPING_NAME, mapping_data, force=force, mode=0o600),
        "views_sums": pc.write_checked(server_dir / SUMS_NAME, sums_data, force=force, mode=0o600),
    }
    for name in sorted(view_files):
        pc.write_checked(server_dir / VIEWS_DIR / name, view_files[name], force=force, mode=0o600)
    status["sheet"] = pc.write_checked(packet_dir / SHEET_NAME, sheet_data, force=force)
    status["manifest"] = pc.write_checked(packet_dir / MANIFEST_NAME, manifest_data, force=force)
    return {"counts": manifest["counts"], "g3w": g3w, "order": order_report,
            "paraphrase_mode": inputs.paraphrase_mode,
            "sheet_sha256": pc.sha256_bytes(sheet_data),
            "mapping_sha256": pc.sha256_bytes(mapping_data),
            "manifest_sha256": pc.sha256_bytes(manifest_data),
            "views_sums_sha256": pc.sha256_bytes(sums_data), "write_status": status}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells", type=Path, default=REAL_RUN / "cells.jsonl")
    ap.add_argument("--ah-labels", type=Path,
                    help="the locked AH working CSV (A_AH); read-only, outside the repository")
    ap.add_argument("--paraphrases", type=Path, default=BANK_DIR / "cq_bank_brick_v1_paraphrases.csv")
    ap.add_argument("--bank", type=Path, default=BANK_DIR / "cq_bank_brick_v1.csv")
    paraphrase_source = ap.add_mutually_exclusive_group()
    paraphrase_source.add_argument(
        "--semantic-check", type=Path,
        help="CSV with the columns cq_id, verdict (exactly pass or fail), checker and date, one complete "
             "row for every paraphrase row; incomplete files are refused (PREREG sec.13.1 item 3)")
    paraphrase_source.add_argument(
        "--no-paraphrase-fallback", action="store_true",
        help="no semantic check by a person other than the rater by the washout date: every row shows the "
             "original CQ and the manifests say paraphrase_mode original_cq_fallback. Needs no "
             "semantic-check file and excludes --semantic-check")
    ap.add_argument("--variants-dir", type=Path, default=pc.HERE / "variants",
                    help="holds <V>/rendered_view.txt, the original views")
    ap.add_argument("--salt-file", type=Path,
                    help=f"sealed salt (>= {SALT_MIN_BYTES} bytes, mode 0600); outside the repository, "
                         "the packet directory and the server directory")
    ap.add_argument("--init-salt", action="store_true",
                    help=f"create --salt-file ({SALT_BYTES} random bytes from secrets, mode 0600) and "
                         "exit; refuses to overwrite a file")
    ap.add_argument("--sealed-dir", type=Path,
                    help="receives washout_mapping.json (mode 0600); refused inside the repository")
    ap.add_argument("--packet-dir", type=Path,
                    help="receives the rater-visible sheet and MANIFEST.json: the rater gets only these")
    ap.add_argument("--server-dir", type=Path,
                    help="receives views/ (one opaque file per row) and views.SHA256SUMS.txt for the "
                         "operator's label_assist; refused inside the repository")
    ap.add_argument("--seed", type=int, default=SEED, help=f"must be the registered {SEED}")
    ap.add_argument("--allow-partial", action="store_true",
                    help="accept a primary set that is not the registered 188-cell design "
                         "(synthetic fixtures only)")
    ap.add_argument("--force", action="store_true", help="overwrite differing existing outputs")
    ap.add_argument("--expected-cells-sha256", default=PINNED_CELLS_SHA256)
    ap.add_argument("--expected-ah-labels-sha256", default=PINNED_AH_LABELS_SHA256)
    ap.add_argument("--expected-paraphrases-sha256", default=PINNED_PARAPHRASES_SHA256)
    ap.add_argument("--expected-bank-sha256", default=PINNED_BANK_SHA256)
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if args.seed != SEED:
        print(f"[build_washout_packet] refused: the seed must be the registered {SEED}", file=sys.stderr)
        return 1
    if args.init_salt:
        if args.salt_file is None:
            ap.error("--init-salt needs --salt-file")
        try:
            create_salt_file(args.salt_file)
        except (WashoutError, OSError) as exc:
            print(f"[build_washout_packet] refused: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        print(f"salt file created: {SALT_BYTES} random bytes, mode 0600 (contents and hash are never printed)")
        return 0
    required = [("--ah-labels", args.ah_labels), ("--salt-file", args.salt_file),
                ("--sealed-dir", args.sealed_dir), ("--packet-dir", args.packet_dir),
                ("--server-dir", args.server_dir)]
    if not args.no_paraphrase_fallback:
        required.insert(1, ("--semantic-check", args.semantic_check))
    missing = [flag for flag, value in required if value is None]
    if missing:
        hint = " (or use --no-paraphrase-fallback)" if "--semantic-check" in missing else ""
        ap.error("missing " + ", ".join(missing) + hint)
    try:
        result = build(
            cells_path=args.cells, labels_path=args.ah_labels, paraphrases_path=args.paraphrases,
            bank_path=args.bank, semantic_path=args.semantic_check, variants_dir=args.variants_dir,
            salt_file=args.salt_file, sealed_dir=args.sealed_dir, packet_dir=args.packet_dir,
            server_dir=args.server_dir, seed=args.seed, allow_partial=args.allow_partial,
            force=args.force, no_paraphrase_fallback=args.no_paraphrase_fallback,
            expected={"cells_jsonl": args.expected_cells_sha256, "ah_labels": args.expected_ah_labels_sha256,
                      "paraphrases": args.expected_paraphrases_sha256, "bank": args.expected_bank_sha256})
    except (WashoutError, FileExistsError, OSError) as exc:
        print(f"[build_washout_packet] refused: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except (ValueError, KeyError) as exc:
        # these come from the input loaders and routinely quote cell ids: name the type, withhold the text
        print(f"[build_washout_packet] refused: {type(exc).__name__} "
              "(message withheld: it may name cell ids)", file=sys.stderr)
        return 1
    c, order = result["counts"], result["order"]
    print(f"rows={c['rows_total']} primary={c['primary_rows']}")
    print(f"paraphrase_mode={result['paraphrase_mode']}")
    print(f"controls_included=ablated:{c['controls_included']['ablated']},preserved:"
          f"{c['controls_included']['preserved']} controls_excluded=ablated:"
          f"{c['controls_excluded']['ablated']},preserved:{c['controls_excluded']['preserved']}")
    print(f"g3w: {result['g3w']['status']} (n_valid_ablated={result['g3w']['n_valid_ablated']})")
    print(f"order: target_min_gap={order['target_min_gap']} achieved_min_gap={order['achieved_min_gap']} "
          f"target_met={order['target_met']}")
    print(f"sheet_sha256={result['sheet_sha256']}")
    print(f"mapping_sha256={result['mapping_sha256']}")
    print(f"views_sha256sums_sha256={result['views_sums_sha256']}")
    print(f"manifest_sha256={result['manifest_sha256']}")
    print("written: " + ", ".join(f"{k}={v}" for k, v in result["write_status"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
