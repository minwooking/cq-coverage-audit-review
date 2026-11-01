"""Tests for build_washout_packet (PREREG sec.12.3, DN-2/3/4a/7, and the pinned selection rules).

ALL DATA HERE IS SYNTHETIC scaffolding material. The builder is never run on the real inputs:
every path below lives under pytest's tmp_path, and the real pins (cells.jsonl, AH labels,
paraphrase, bank sha256) are bypassed with ``expected={}`` or fixture hashes.

The builder writes three directories for three audiences: ``packet`` (the rater: the sheet and
the manifest), ``server`` (the operator's label_assist: views/ with one opaque file per row, and
the sums file beside it) and ``sealed`` (the mapping). The tests pin that split, the modes, the
salt rules and the id-free error output.
"""
from __future__ import annotations

import collections
import csv
import hashlib
import hmac
import json
import math
import os
import random
import re
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_washout_packet as bwp  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import packet_common as pc  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import run_holdout as rh  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

HERE = Path(__file__).resolve().parent
HEADER = list(la.SHEET_COLUMNS)
SEMANTIC_HEADER = ("cq_id", "verdict", "checker", "date")        # PREREG sec.13.1 item 3
CATS = ["cat_a", "cat_b", "cat_c"]
VARIANTS = "ABCDEF"
N_CQ = 12
SALT = b"0123456789abcdef0123456789abcdef"
N_PROP, N_ENR, RUNS = 16, 8, 300       # small design for the fixtures (the registered one is 48/24/100000)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cq_of(i: int) -> str:
    return f"CQB{i:02d}"


# ---------------------------------------------------------------------------
# the synthetic world
# ---------------------------------------------------------------------------
@dataclass
class World:
    root: Path
    cells: Path
    labels: Path
    paraphrases: Path
    bank: Path
    semantic: Path
    variants: Path
    salt: Path
    primary: list[dict] = field(default_factory=list)
    controls: list[dict] = field(default_factory=list)
    views: dict[str, str] = field(default_factory=dict)
    bank_rows: dict[str, dict] = field(default_factory=dict)
    para: dict[str, str] = field(default_factory=dict)

    def rewrite_cells(self, edit) -> None:
        recs = [json.loads(l) for l in self.cells.read_text(encoding="utf-8").split("\n") if l.strip()]
        edit(recs)
        self.cells.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs),
                              encoding="utf-8")


def view_text(variant: str) -> str:
    lines = [f"# variant {variant} rendered view"]
    lines += [f"brick:T{i} is-a brick:Thing in variant {variant}" for i in range(N_CQ)]
    lines.append("end of view")
    return "\n".join(lines) + "\n"


def make_world(root: Path, *, n_discordant: int | None = None, failing: tuple[int, ...] = (),
               salt: bytes = SALT, ablated: tuple = (("A", 1), ("B", 2), ("C", 4), ("D", 7)),
               preserved: tuple = (("B", 3), ("E", 5)), seed: int = 11) -> World:
    root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    w = World(root, root / "cells.jsonl", root / "ah_labels.csv", root / "paraphrases.csv",
              root / "bank.csv", root / "semantic.csv", root / "variants", root / "salt.txt")
    w.views = {v: view_text(v) for v in VARIANTS}
    for v, text in w.views.items():
        (w.variants / v).mkdir(parents=True, exist_ok=True)
        (w.variants / v / "rendered_view.txt").write_text(text, encoding="utf-8")
    bank_cols = ["cq_id", "category", "question", "grounding", "expected_answer", "status",
                 "cluster_id", "created", "ask_expressible", "ask_query_file"]
    with open(w.bank, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(bank_cols)
        for i in range(N_CQ):
            row = {"cq_id": cq_of(i), "category": CATS[i % 3], "question": f"What is concept T{i}?",
                   "grounding": f"brick:T{i}", "expected_answer": "x", "status": "candidate",
                   "cluster_id": cq_of(i), "created": "2026-09-12", "ask_expressible": "yes",
                   "ask_query_file": ""}
            w.bank_rows[cq_of(i)] = row
            wr.writerow([row[c] for c in bank_cols])
    with open(w.paraphrases, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["cq_id", "cluster_id", "paraphrase_text", "grounding", "author_note"])
        for i in range(N_CQ):
            w.para[cq_of(i)] = f"Which statement describes T{i}?"
            wr.writerow([cq_of(i), cq_of(i), w.para[cq_of(i)], f"brick:T{i}", "note"])
    with open(w.semantic, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(list(SEMANTIC_HEADER))
        for i in range(N_CQ):
            wr.writerow([cq_of(i), "fail" if i in failing else "pass", "checker-1", "2026-10-20"])
    w.salt.write_bytes(salt)           # the builder reads the exact bytes and wants mode 0600
    os.chmod(w.salt, 0o600)

    recs: list[dict] = []
    for v in VARIANTS:
        for i in range(N_CQ):
            j = rng.choice([0, 1, 2, 3])
            span = "" if j == 0 else f"brick:T{i} is-a brick:Thing in variant {v}"
            cell = {"cell_id": f"primary:{v}:{cq_of(i)}", "cell_kind": "primary", "cq_id": cq_of(i),
                    "cluster_id": cq_of(i), "category": CATS[i % 3], "variant": v, "J": j, "A": 0,
                    "judge_response": {"score": j, "evidence": span}, "judge_response_parsed": True,
                    "artifact_digest": sha(w.views[v].encode()), "SIMULATED": False}
            recs.append(cell)
            w.primary.append({"cell_id": cell["cell_id"], "category": cell["category"], "J": j,
                              "cq_id": cq_of(i), "variant": v, "evidence": span,
                              "A_AH": int(j >= 2)})
    flips = ([p for p in sorted(w.primary, key=lambda p: p["cell_id"])][:n_discordant]
             if n_discordant is not None else [p for p in w.primary if rng.random() < 0.35])
    for p in flips:
        p["A_AH"] = 1 - p["A_AH"]
    for kind, picks in (("ablated_control", ablated), ("preserved_control", preserved)):
        for v, i in picks:
            view = w.views[v]
            if kind == "ablated_control":
                view = rh.ablate_rendered_view(view, w.bank_rows[cq_of(i)])
            cell = {"cell_id": f"{kind}:{v}:{cq_of(i)}", "cell_kind": kind, "cq_id": cq_of(i),
                    "cluster_id": cq_of(i), "category": CATS[i % 3], "variant": v, "J": 1, "A": 0,
                    "judge_response": {"score": 1, "evidence": f"quoted line {v}{i}"},
                    "judge_response_parsed": True, "artifact_digest": sha(view.encode())}
            recs.append(cell)
            w.controls.append({**cell, "view": view})
    w.cells.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    with open(w.labels, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(HEADER)
        for p in sorted(w.primary, key=lambda p: p["cell_id"]):
            wr.writerow([p["cell_id"], "", "", "", "", "", "", "", "", str(p["A_AH"]), "", ""])
        for k, c in enumerate(w.controls):   # control labels exist but must never be read: junk values
            wr.writerow([c["cell_id"], "", "", "", "", "", "", "", "", "x" if k % 2 else "", "", ""])
    return w


def run_build(w: World, out: Path, **kw):
    params = dict(cells_path=w.cells, labels_path=w.labels, paraphrases_path=w.paraphrases,
                  bank_path=w.bank, semantic_path=w.semantic, variants_dir=w.variants,
                  salt_file=w.salt, sealed_dir=out / "sealed", packet_dir=out / "packet",
                  server_dir=out / "server", allow_partial=True, expected={}, n_proportional=N_PROP, n_enriched=N_ENR,
                  n_runs=RUNS)
    params.update(kw)
    return bwp.build(**params)


def read_sheet(out: Path) -> list[list[str]]:
    with open(out / "packet" / bwp.SHEET_NAME, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def read_mapping(out: Path) -> dict:
    return json.loads((out / "sealed" / bwp.MAPPING_NAME).read_text(encoding="utf-8"))


def mapping_rows(out: Path) -> list[dict]:
    """The design rows of cells that were shown (in sheet order)."""
    return [m for m in read_mapping(out)["rows"] if m["excluded_reason"] == ""]


def excluded_rows(out: Path) -> list[dict]:
    return [m for m in read_mapping(out)["rows"] if m["excluded_reason"] != ""]


def read_manifest(out: Path) -> dict:
    return json.loads((out / "packet" / bwp.MANIFEST_NAME).read_text(encoding="utf-8"))


def server_views(out: Path) -> Path:
    return out / "server" / bwp.VIEWS_DIR


def server_sums(out: Path) -> Path:
    return out / "server" / bwp.SUMS_NAME


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory):
    root = tmp_path_factory.mktemp("washout")
    w = make_world(root / "in")
    result = run_build(w, root / "out")
    return w, root / "out", result


# ---------------------------------------------------------------------------
# allocation: n_h = max(1, largest remainder), pinned tie orders
# ---------------------------------------------------------------------------
def test_allocation_is_largest_remainder_with_a_one_seat_floor() -> None:
    got = bwp.allocate_proportional({("a", 0): 10, ("a", 1): 1, ("b", 0): 1, ("b", 3): 28}, 8)
    # quotas 2.0 / 0.2 / 0.2 / 5.6 -> floors 2,0,0,5 (+1 to b3) -> floor of one seat -> 10 > 8 -> trim b3 twice
    assert got == {("a", 0): 2, ("a", 1): 1, ("b", 0): 1, ("b", 3): 4}
    assert sum(got.values()) == 8


def test_allocation_remainder_ties_go_to_category_then_J_ascending() -> None:
    sizes = {("b", 1): 3, ("a", 1): 3, ("b", 0): 3, ("a", 0): 3}        # every quota is 1.5
    assert bwp.allocate_proportional(sizes, 6) == {("a", 0): 2, ("a", 1): 2, ("b", 0): 1, ("b", 1): 1}
    sizes = {("a", 0): 3, ("a", 2): 3, ("a", 1): 3}                       # quotas 4/3; one extra seat
    assert bwp.allocate_proportional({("a", 0): 3, ("a", 1): 3, ("a", 2): 3}, 4) == \
        {("a", 0): 2, ("a", 1): 1, ("a", 2): 1}
    assert bwp.allocate_proportional(sizes, 4) == {("a", 0): 2, ("a", 1): 1, ("a", 2): 1}


def test_allocation_excess_is_removed_one_seat_at_a_time_from_the_largest_stratum() -> None:
    sizes = {("a", 0): 10, ("b", 0): 10, ("c", 0): 1, ("d", 0): 1, ("e", 0): 1}
    got = bwp.allocate_proportional(sizes, 12)
    # floors 5,5,0,0,0 + remainder seats to c,d; floor of one gives e a seat: 13 > 12; a and b tie at 5 -> a first
    assert got == {("a", 0): 4, ("b", 0): 5, ("c", 0): 1, ("d", 0): 1, ("e", 0): 1}
    assert sum(got.values()) == 12


def test_allocation_over_non_empty_strata_only_and_refusals() -> None:
    got = bwp.allocate_proportional({("a", 0): 4, ("a", 1): 0, ("b", 2): 4}, 4)
    assert got == {("a", 0): 2, ("b", 2): 2}                              # the empty stratum gets nothing
    with pytest.raises(bwp.WashoutError, match="exceed"):
        bwp.allocate_proportional({("a", 0): 5, ("a", 1): 5, ("a", 2): 5}, 2)
    with pytest.raises(bwp.WashoutError, match="requested"):
        bwp.allocate_proportional({("a", 0): 2}, 3)
    with pytest.raises(bwp.WashoutError, match="no non-empty"):
        bwp.allocate_proportional({("a", 0): 0}, 1)


def test_allocation_registered_shape_sums_to_48() -> None:
    rng = random.Random(5)
    sizes = {(c, j): rng.randint(1, 14) for c in "abcdef" for j in range(4)}
    scale = 188 / sum(sizes.values())
    sizes = {k: max(1, round(v * scale)) for k, v in sizes.items()}
    got = bwp.allocate_proportional(sizes, 48)
    assert sum(got.values()) == 48 and all(1 <= got[k] <= sizes[k] for k in got)
    assert list(got) == sorted(got)


# ---------------------------------------------------------------------------
# the pinned drawing procedure, re-implemented here from the rule text
# ---------------------------------------------------------------------------
def spec_allocation(pool: list[dict], n_prop: int) -> dict:
    by = collections.defaultdict(list)
    for c in pool:
        by[(c["category"], c["J"])].append(c["cell_id"])
    keys = sorted(by)
    total = len(pool)
    quota = {k: Fraction(n_prop * len(by[k]), total) for k in keys}
    n = {k: math.floor(quota[k]) for k in keys}
    seats = n_prop - sum(n.values())
    for k in sorted(keys, key=lambda k: (-(quota[k] - n[k]), k[0], k[1]))[:seats]:
        n[k] += 1
    for k in keys:
        n[k] = max(1, n[k])
    while sum(n.values()) > n_prop:
        big = max(n.values())
        n[min(k for k in keys if n[k] == big)] -= 1
    return {"by": by, "keys": keys, "n": n}


def spec_selection(pool: list[dict], n_prop: int, m: int, seed: int):
    a = spec_allocation(pool, n_prop)
    rng = random.Random(seed)
    s1: list[str] = []
    for k in a["keys"]:
        s1 += rng.sample(sorted(a["by"][k]), a["n"][k])
    d = sorted(c["cell_id"] for c in pool if int(c["J"] >= 2) != c["A_AH"])
    rest = sorted(set(d) - set(s1))
    if len(rest) >= m:
        return s1, rng.sample(rest, m), []
    remaining = sorted(set(c["cell_id"] for c in pool) - set(s1) - set(rest))
    return s1, list(rest), rng.sample(remaining, m - len(rest))


def pool_of(w: World) -> list[dict]:
    return [{k: p[k] for k in ("cell_id", "category", "J", "A_AH")} for p in w.primary]


def test_select_once_is_the_pinned_procedure_with_one_rng(tmp_path: Path) -> None:
    w = make_world(tmp_path)
    design = bwp.build_design(pool_of(w), N_PROP, N_ENR)
    got = bwp.select_once(design, random.Random(20260913))
    s1, enriched, fill = spec_selection(pool_of(w), N_PROP, N_ENR, 20260913)
    assert (got.proportional, got.enriched, got.fill) == (s1, enriched, fill)
    assert fill == [] and len(enriched) == N_ENR and len(s1) == N_PROP
    assert len(set(got.all_ids())) == N_PROP + N_ENR                     # disjoint groups, no repeats
    # enriched cells are discordant and were not in the proportional layer
    d = {c["cell_id"] for c in pool_of(w) if int(c["J"] >= 2) != c["A_AH"]}
    assert set(enriched) <= d and not set(enriched) & set(s1)
    # per-stratum counts equal the allocation
    per = collections.Counter(design.stratum_of[c] for c in s1)
    assert dict(per) == design.alloc
    # another seed, another draw
    other = bwp.select_once(design, random.Random(20260914))
    assert other.proportional != got.proportional


def test_shortfall_takes_all_remaining_discordant_cells_and_fills_the_rest(tmp_path: Path) -> None:
    w = make_world(tmp_path, n_discordant=3)
    design = bwp.build_design(pool_of(w), N_PROP, N_ENR)
    assert len(design.discordant_sorted) == 3
    got = bwp.select_once(design, random.Random(20260913))
    s1, enriched, fill = spec_selection(pool_of(w), N_PROP, N_ENR, 20260913)
    assert (got.proportional, got.enriched, got.fill) == (s1, enriched, fill)
    assert len(enriched) <= 3 and len(fill) == N_ENR - len(enriched) > 0
    assert len(set(got.all_ids())) == N_PROP + N_ENR                     # the total is still met
    d = set(design.discordant_sorted)
    assert set(enriched) == d - set(s1)                                  # all of D - S1, sorted
    assert enriched == sorted(enriched)
    assert not set(fill) & (d | set(s1))                                 # fill: remaining, non-discordant
    # a pool with too few remaining cells for the fill is refused
    tiny = [{"cell_id": f"c{i}", "category": "a", "J": 0, "A_AH": 0} for i in range(3)]
    d2 = bwp.build_design(tiny, 2, 5)
    with pytest.raises(bwp.WashoutError, match="remaining"):
        bwp.select_once(d2, random.Random(1))


def test_discordance_is_J_at_least_2_versus_A_AH(tmp_path: Path) -> None:
    pool = [{"cell_id": f"c{i}", "category": "a", "J": j, "A_AH": a}
            for i, (j, a) in enumerate([(0, 0), (1, 0), (2, 1), (3, 1), (0, 1), (1, 1), (2, 0), (3, 0)])]
    design = bwp.build_design(pool, 4, 2)
    assert design.discordant_sorted == ["c4", "c5", "c6", "c7"]


def test_build_design_refuses_a_duplicate_cell() -> None:
    cell = {"cell_id": "c1", "category": "a", "J": 0, "A_AH": 0}
    with pytest.raises(bwp.WashoutError, match="duplicate"):
        bwp.build_design([cell, dict(cell)], 1, 1)


# ---------------------------------------------------------------------------
# inclusion probabilities: reruns with random.Random(seed + r), r = 1..n
# ---------------------------------------------------------------------------
def test_pi_is_the_share_of_reruns_with_seeds_seed_plus_r(tmp_path: Path) -> None:
    w = make_world(tmp_path)
    design = bwp.build_design(pool_of(w), N_PROP, N_ENR)
    runs = 150
    pi = bwp.inclusion_probabilities(design, seed=20260913, n_runs=runs)
    counts: collections.Counter[str] = collections.Counter()
    for r in range(1, runs + 1):
        s1, en, fill = spec_selection(pool_of(w), N_PROP, N_ENR, 20260913 + r)
        counts.update(s1 + en + fill)
    expected = {c["cell_id"]: bwp.round_share(counts[c["cell_id"]], runs) for c in pool_of(w)}
    assert pi == expected
    assert all(isinstance(v, Decimal) and v == v.quantize(Decimal("0.0001")) for v in pi.values())
    assert math.isclose(sum(float(v) for v in pi.values()), N_PROP + N_ENR, abs_tol=0.5)
    # the real draw (seed itself, r = 0) is not one of the reruns
    assert 20260913 + 0 not in {20260913 + r for r in range(1, runs + 1)}


def test_round_share_is_half_up_in_exact_decimals() -> None:
    assert bwp.round_share(1, 32) == Decimal("0.0313")          # 0.03125 -> half up (float round gives 0.0312)
    assert bwp.round_share(3, 100000) == Decimal("0.0000")
    assert bwp.round_share(5, 100000) == Decimal("0.0001")      # 0.00005 -> half up
    assert bwp.round_share(99999, 100000) == Decimal("1.0000")
    assert bwp.round_share(12345, 100000) == Decimal("0.1235")  # 0.12345
    assert bwp.round_share(1, 3) == Decimal("0.3333")


def test_registered_constants() -> None:
    assert (bwp.SEED, bwp.N_PROPORTIONAL, bwp.N_ENRICHED, bwp.PI_RUNS, bwp.PI_DECIMALS) == (
        20260913, 48, 24, 100_000, 4)
    assert bwp.G3W_NOT_JUDGED == "G3-W not judged (n_valid < 24)"
    assert bwp.PINNED_PARAPHRASES_SHA256 == "c02ecda3f2c6c3c27dc47e7f4845ac57739d5d85b059bfa813328c125682341f"
    assert bwp.PINNED_CELLS_SHA256 == "bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af"


def test_pi_with_the_registered_run_count_on_a_tiny_design() -> None:
    pool = [{"cell_id": f"c{i}", "category": "a" if i < 4 else "b", "J": 0, "A_AH": 1}
            for i in range(8)]                                    # two strata, every cell discordant
    design = bwp.build_design(pool, 2, 1)
    pi = bwp.inclusion_probabilities(design)                      # n_runs = PI_RUNS = 100000
    assert set(pi) == {f"c{i}" for i in range(8)}
    assert all(v == v.quantize(Decimal("0.0001")) for v in pi.values())
    assert abs(sum(float(v) for v in pi.values()) - 3) < 0.01      # 2 proportional + 1 enriched cell


def test_pi_matches_the_exact_probabilities_on_a_pool_small_enough_to_enumerate() -> None:
    # strata a:{c1,c2,c3} and b:{c4,c5,c6}, one seat each; D = {c1, c2, c4}; one enriched cell
    pool = [{"cell_id": c, "category": cat, "J": 0, "A_AH": a}
            for c, cat, a in [("c1", "a", 1), ("c2", "a", 1), ("c3", "a", 0),
                              ("c4", "b", 1), ("c5", "b", 0), ("c6", "b", 0)]]
    design = bwp.build_design(pool, 2, 1)
    assert design.discordant_sorted == ["c1", "c2", "c4"] and design.alloc == {("a", 0): 1, ("b", 0): 1}
    exact: dict[str, Fraction] = collections.defaultdict(Fraction)
    for x in ("c1", "c2", "c3"):
        for y in ("c4", "c5", "c6"):
            rest = [c for c in ("c1", "c2", "c4") if c not in (x, y)]
            for c in (x, y):
                exact[c] += Fraction(1, 9)
            for c in rest:                                        # the enriched draw: 1 of len(rest)
                exact[c] += Fraction(1, 9) * Fraction(1, len(rest))
    pi = bwp.inclusion_probabilities(design, seed=20260913, n_runs=20000)
    for cid, p in exact.items():
        assert abs(float(pi[cid]) - float(p)) < 0.02, (cid, float(pi[cid]), float(p))
    assert abs(sum(float(v) for v in pi.values()) - 3) < 1e-9 + 0.01


# ---------------------------------------------------------------------------
# opaque ids, view names, the sealed salt
# ---------------------------------------------------------------------------
def test_opaque_ids_come_from_the_sealed_salt() -> None:
    a = bwp.opaque_id(SALT, "primary:A:CQB01")
    assert a == hmac.new(SALT, b"primary:A:CQB01", hashlib.sha256).hexdigest()[:16]
    assert len(a) == 16 and re.fullmatch(r"[0-9a-f]{16}", a)
    assert a != bwp.opaque_id(b"another salt value!!", "primary:A:CQB01")
    assert a != hashlib.sha256(b"primary:A:CQB01").hexdigest()[:16]      # not derivable without the salt
    assert a != bwp.opaque_id(SALT, "primary:B:CQB01")


def test_view_names_are_per_row_hmacs_of_the_opaque_id_under_the_salt() -> None:
    opaque = bwp.opaque_id(SALT, "primary:A:CQB01")
    ref = bwp.view_ref(SALT, opaque)
    expected = "v_" + hmac.new(SALT, b"view-row:" + opaque.encode("ascii"), hashlib.sha256).hexdigest()[:16] + ".txt"
    assert ref == expected and re.fullmatch(r"v_[0-9a-f]{16}\.txt", ref)
    assert ref != bwp.view_ref(SALT, bwp.opaque_id(SALT, "primary:B:CQB01"))   # one name per row
    assert ref != bwp.view_ref(b"another salt value!!!!!!!!!!!!!!", opaque)      # and a function of the salt
    assert opaque not in ref                                                      # not the id itself


def test_salt_file_is_read_exactly_and_must_be_long_enough_and_private(tmp_path: Path) -> None:
    f = tmp_path / "salt"
    f.write_bytes(SALT)
    os.chmod(f, 0o600)
    assert bwp.read_salt(f) == SALT
    f.write_bytes(SALT + b"\n")                                  # nothing is stripped: the bytes ARE the salt
    assert bwp.read_salt(f) == SALT + b"\n"
    f.write_bytes(b"x" * 32)
    assert bwp.read_salt(f) == b"x" * 32                         # the minimum
    for short in (b"x" * 31, b"short\n", b""):
        f.write_bytes(short)
        with pytest.raises(bwp.WashoutError, match="at least 32"):
            bwp.read_salt(f)
    f.write_bytes(SALT)
    for mode in (0o644, 0o640, 0o604, 0o660, 0o666, 0o601, 0o602, 0o610, 0o620):   # any group or other bit
        os.chmod(f, mode)
        with pytest.raises(bwp.WashoutError, match="group/others"):
            bwp.read_salt(f)
    for mode in (0o600, 0o400):
        os.chmod(f, mode)
        assert bwp.read_salt(f) == SALT


def test_init_salt_writes_32_random_bytes_mode_0600_and_never_overwrites(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / "newdir" / "salt.bin"
    old = os.umask(0o022)
    try:
        bwp.create_salt_file(f)
    finally:
        os.umask(old)
    assert mode_of(f) == 0o600 and f.stat().st_size == bwp.SALT_BYTES == 32
    assert mode_of(f.parent) == 0o700                             # a directory it had to create is private
    assert bwp.read_salt(f) == f.read_bytes() and len(set(f.read_bytes())) > 1
    first = f.read_bytes()
    with pytest.raises(bwp.WashoutError, match="already exists"):
        bwp.create_salt_file(f)
    assert f.read_bytes() == first
    other = tmp_path / "salt2.bin"
    bwp.create_salt_file(other)
    assert other.read_bytes() != first                            # fresh randomness every time
    link = tmp_path / "link.bin"                                  # an existing name, even a dangling link, is not followed
    link.symlink_to(tmp_path / "elsewhere.bin")
    with pytest.raises(OSError):
        bwp.create_salt_file(link)
    assert not (tmp_path / "elsewhere.bin").exists()
    monkeypatch.setattr(bwp.secrets, "token_bytes", lambda n: b"\x07" * n)   # the bytes come from `secrets`
    fixed = tmp_path / "fixed.bin"
    bwp.create_salt_file(fixed)
    assert fixed.read_bytes() == b"\x07" * 32


def test_init_salt_is_refused_inside_the_repository(tmp_path: Path) -> None:
    inside = HERE / "_salt_must_not_be_created" / "salt.bin"
    with pytest.raises(bwp.WashoutError, match="inside the repository"):
        bwp.create_salt_file(inside)
    assert not inside.parent.exists()
    wt = tmp_path / ".claude" / "worktrees" / "wt" / "salt.bin"
    with pytest.raises(bwp.WashoutError, match="inside the repository"):
        bwp.create_salt_file(wt)
    assert not wt.parent.exists()


def test_cli_init_salt_creates_the_file_and_prints_no_secret(tmp_path: Path,
                                                             capsys: pytest.CaptureFixture[str]) -> None:
    f = tmp_path / "s" / "salt.bin"
    assert bwp.main(["--init-salt", "--salt-file", str(f)]) == 0
    shown = capsys.readouterr()
    data = f.read_bytes()
    assert len(data) == 32 and mode_of(f) == 0o600
    assert "salt file created" in shown.out and data.hex() not in shown.out and sha(data) not in shown.out
    assert bwp.read_salt(f) == data
    assert bwp.main(["--init-salt", "--salt-file", str(f)]) == 1             # never overwritten
    assert "refused" in capsys.readouterr().err and f.read_bytes() == data
    inside = HERE / "_salt_must_not_be_created"
    assert bwp.main(["--init-salt", "--salt-file", str(inside)]) == 1 and not inside.exists()
    capsys.readouterr()
    with pytest.raises(SystemExit) as exc:
        bwp.main(["--init-salt"])
    assert exc.value.code == 2


def test_a_weak_or_shared_salt_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    os.chmod(w.salt, 0o644)
    with pytest.raises(bwp.WashoutError, match="group/others"):
        run_build(w, tmp_path / "out")
    os.chmod(w.salt, 0o600)
    w.salt.write_bytes(b"too short")
    with pytest.raises(bwp.WashoutError, match="at least"):
        run_build(w, tmp_path / "out")
    assert not (tmp_path / "out").exists()


# ---------------------------------------------------------------------------
# the built packet
# ---------------------------------------------------------------------------
def test_sheet_is_the_12_column_ah_format_with_opaque_ids_and_empty_labels(built) -> None:
    w, out, result = built
    rows = read_sheet(out)
    assert rows[0] == HEADER
    body = rows[1:]
    expected_rows = N_PROP + N_ENR + len(w.controls)
    assert len(body) == expected_rows == result["counts"]["rows_total"]
    for r in body:
        assert len(r) == 12
        assert r[1:5] == ["", "", "", ""]                      # cq_id, cluster_id, category, variant blank
        assert r[8:] == ["", "", "", ""]                       # label columns empty
        assert re.fullmatch(r"[0-9a-f]{16}", r[0])
    raw = (out / "packet" / bwp.SHEET_NAME).read_bytes().decode("utf-8")
    for needle in ("primary", "control", "CQB", "cat_a", "cat_b", "cat_c", "ablated", "preserved"):
        assert needle not in raw, needle
    cell_ids = [p["cell_id"] for p in w.primary] + [c["cell_id"] for c in w.controls]
    assert not any(c in raw for c in cell_ids)
    ids = [r[0] for r in body]
    assert len(set(ids)) == len(ids)


def test_every_row_shows_the_paraphrased_cq(built) -> None:
    w, out, _ = built
    mapping = {m["cell_id"]: m for m in mapping_rows(out)}
    texts = {p["cell_id"]: w.para[p["cq_id"]] for p in w.primary}
    texts.update({c["cell_id"]: w.para[c["cq_id"]] for c in w.controls})
    for r in read_sheet(out)[1:]:
        assert r[5] == texts[mapping[r[0]]["source_cell_id"]]
        assert mapping[r[0]]["cq_text_source"] == "paraphrase"
    assert read_manifest(out)["counts"]["rows_showing_original_cq"] == 0


def test_judge_evidence_span_is_the_judges_quote_exactly(built) -> None:
    w, out, _ = built
    mapping = {m["cell_id"]: m["source_cell_id"] for m in mapping_rows(out)}
    spans = {p["cell_id"]: p["evidence"] for p in w.primary}
    spans.update({c["cell_id"]: c["judge_response"]["evidence"] for c in w.controls})
    for r in read_sheet(out)[1:]:
        assert r[6] == spans[mapping[r[0]]]


def test_view_files_are_one_per_row_opaque_and_hash_to_the_judges_digests(built) -> None:
    w, out, _ = built
    views, sums_path = server_views(out), server_sums(out)
    sums = dict((line.split("  ")[1], line.split("  ")[0])
                for line in sums_path.read_text(encoding="utf-8").splitlines())
    mapping = {m["cell_id"]: m for m in mapping_rows(out)}
    digest_of = {p["cell_id"]: sha(w.views[p["variant"]].encode()) for p in w.primary}
    digest_of.update({c["cell_id"]: c["artifact_digest"] for c in w.controls})
    refs = []
    for r in read_sheet(out)[1:]:
        ref = r[7]
        refs.append(ref)
        digest = digest_of[mapping[r[0]]["source_cell_id"]]
        assert re.fullmatch(r"v_[0-9a-f]{16}\.txt", ref) and (views / ref).is_file()
        assert ref == bwp.view_ref(SALT, r[0]) == mapping[r[0]]["view_ref"]   # a function of the row's id and the salt
        assert sums[ref] == sha((views / ref).read_bytes()) == digest
        assert digest[:16] not in ref                                           # the name says nothing of the content
    # ONE file per row: no two rows share a name, even when they show the same view
    assert len(set(refs)) == len(refs) == len(list(views.iterdir()))
    assert set(sums) == {p.name for p in views.iterdir()} == set(refs)
    assert not (views / "SHA256SUMS.txt").exists()                              # the sums sit BESIDE views/, not in it
    same_view = collections.defaultdict(list)
    for r in read_sheet(out)[1:]:
        same_view[digest_of[mapping[r[0]]["source_cell_id"]]].append(r[7])
    assert any(len(v) > 1 for v in same_view.values())                          # the fixture does repeat views ...
    assert all(len(set(v)) == len(v) for v in same_view.values())               # ... and every repeat has its own name
    # the view of an ablated control is the regenerated one (the supporting line is gone)
    ablated = next(c for c in w.controls if c["cell_kind"] == "ablated_control")
    ref = next(m["view_ref"] for m in mapping.values() if m["source_cell_id"] == ablated["cell_id"])
    assert (views / ref).read_bytes() == ablated["view"].encode("utf-8")
    assert f"brick:T{int(ablated['cq_id'][3:])} is-a" not in ablated["view"]
    # a preserved control shows the original view
    preserved = next(c for c in w.controls if c["cell_kind"] == "preserved_control")
    ref = next(m["view_ref"] for m in mapping.values() if m["source_cell_id"] == preserved["cell_id"])
    assert (views / ref).read_text(encoding="utf-8") == w.views[preserved["variant"]]


def test_the_packet_loads_in_label_assist_packet_mode_with_the_right_view_per_row(built, tmp_path: Path) -> None:
    w, out, _ = built
    sheet = out / "packet" / bwp.SHEET_NAME
    refs = la.sheet_view_refs(sheet)
    with pytest.raises(la.SafetyError):                      # no SHA256SUMS.txt inside views/: --sums is required
        la.verify_packet_views(server_views(out), refs)
    views = la.verify_packet_views(server_views(out), refs, server_sums(out))
    work = tmp_path / "labels" / "working.csv"
    work.parent.mkdir()
    store = la.Store(sheet, work, views, packet=True)
    mapping = {m["cell_id"]: m for m in mapping_rows(out)}
    by_cell = {p["cell_id"]: w.views[p["variant"]] for p in w.primary}
    by_cell.update({c["cell_id"]: c["view"] for c in w.controls})
    import html
    for idx in range(1, len(store.rows)):
        row = store.row(idx)
        assert store.row_view_text(row) == by_cell[mapping[row.cell_id]["source_cell_id"]]
        page = la.render_page(store, idx).decode("utf-8")
        assert html.unescape(row.cq_text) in html.unescape(page.split("<script>")[0])
        assert '<span class="chip">' not in page


def test_the_documented_serve_command_starts_on_the_built_packet(built, tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    _, out, _ = built

    class Dummy:
        server_address = ("127.0.0.1", 4321)

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    monkeypatch.setattr(la, "make_server", lambda store, addr, ttl_dir=None, **kw: Dummy())
    monkeypatch.setattr(la.signal, "signal", lambda *a, **k: None)     # keep the test process's handlers
    monkeypatch.setattr(la.atexit, "register", lambda *a, **k: None)   # and its exit hooks
    sheet = str(out / "packet" / bwp.SHEET_NAME)
    served = ["--packet", "--sheet", sheet, "--views", str(server_views(out)), "--sums", str(server_sums(out)),
              "--out", str(tmp_path / "labels" / "w.csv")]
    assert la.main(served) == 0
    # without --sums the same views directory is refused: the rater-side files alone cannot serve it
    unsummed = ["--packet", "--sheet", sheet, "--views", str(server_views(out)),
                "--out", str(tmp_path / "labels2" / "w.csv")]
    assert la.main(unsummed) == 1


def test_sealed_mapping_is_the_design_table_with_pi_and_w_and_follows_the_sheet(built) -> None:
    w, out, result = built
    mapping = read_mapping(out)
    rows = mapping["rows"]
    sheet = read_sheet(out)[1:]
    assert [m["cell_id"] for m in rows] == [r[0] for r in sheet]         # same order as the sheet
    assert [m["position"] for m in rows] == list(range(1, len(rows) + 1))
    assert [m["view_ref"] for m in rows] == [r[7] for r in sheet]        # the mapping names each row's own view
    assert all(m["excluded_reason"] == "" for m in rows)
    # the columns analyze_washout.py --design reads, in its vocabulary
    for key in ("cell_id", "source_cell_id", "cell_kind", "stratum", "inclusion_prob", "excluded_reason"):
        assert all(key in m for m in rows), key
    assert all(m["cell_id"] == bwp.opaque_id(SALT, m["source_cell_id"]) for m in rows)
    kinds = collections.Counter(m["cell_kind"] for m in rows)
    assert kinds == {"primary": N_PROP + N_ENR, "ablated_control": 4, "preserved_control": 2}
    sel = collections.Counter(m["selection"] for m in rows)
    assert sel["proportional"] == N_PROP and sel["enriched"] + sel["shortfall_fill"] == N_ENR
    assert sel["control"] == 6
    layers = collections.Counter(m["stratum"] for m in rows)
    assert layers == {"proportional": N_PROP, "enriched": N_ENR, "control": 6}
    prim = {p["cell_id"]: p for p in w.primary}
    for m in rows:
        if m["cell_kind"] == "primary":
            p = prim[m["source_cell_id"]]
            assert m["category_stratum"] == f"{p['category']}|J{p['J']}"
            assert 0 < m["inclusion_prob"] <= 1 and m["w"] == 1.0 / m["inclusion_prob"]
            assert round(m["inclusion_prob"], 4) == m["inclusion_prob"]
            assert m["stratum"] == ("proportional" if m["selection"] == "proportional" else "enriched")
        else:
            assert m["inclusion_prob"] == 1.0 and m["w"] == 1.0 and m["stratum"] == "control"
            assert m["category_stratum"] == ""
    d = mapping["design"]
    assert sum(a["n"] for a in d["allocation"]) == N_PROP and d["n_shortfall_filled"] == 0
    assert d["layer_rows"] == {"proportional": N_PROP, "enriched": N_ENR, "shortfall_fill": 0}   # sealed, not public
    assert d["n_controls_excluded"] == 0
    assert mapping["pi_runs"] == RUNS and mapping["pi_decimals"] == 4 and mapping["seed"] == 20260913
    assert mapping["sealed"] is True and "SEALED" in mapping["warning"]
    assert mapping["inputs_sha256"]["cells_jsonl"] == sha(w.cells.read_bytes())
    # the selection in the mapping is the pinned one (same rng, same stratum order)
    s1, enriched, fill = spec_selection(pool_of(w), N_PROP, N_ENR, 20260913)
    chosen = {m["source_cell_id"] for m in rows if m["cell_kind"] == "primary"}
    assert chosen == set(s1) | set(enriched) | set(fill)
    assert {m["source_cell_id"] for m in rows if m["selection"] == "proportional"} == set(s1)
    # inclusion_prob is at least the stage-one probability n_h / N_h (up to the noise of 300 reruns)
    alloc = {(a["category"], a["J"]): (a["n"], a["N"]) for a in d["allocation"]}
    for m in rows:
        if m["cell_kind"] == "primary":
            category, j = m["category_stratum"].split("|J")
            n_h, big_n = alloc[(category, int(j))]
            assert m["inclusion_prob"] >= n_h / big_n - 0.12
    assert abs(d["sum_w_primary"] - sum(m["w"] for m in rows if m["cell_kind"] == "primary")) < 1e-4


def test_the_mapping_reads_as_a_table_with_the_design_columns(built) -> None:
    """analyze_washout.read_table takes a JSON object with a rows list; its design loader needs
    cell_id, source_cell_id, cell_kind and, for a primary row, stratum and inclusion_prob."""
    aw = pytest.importorskip("analyze_washout")
    if not hasattr(aw, "load_washout_design"):
        pytest.skip("analyze_washout has no load_washout_design")
    _, out, _ = built
    design = aw.load_washout_design(out / "sealed" / bwp.MAPPING_NAME)
    assert len(design) == N_PROP + N_ENR + 6
    prim = [d for d in design if d.cell_kind == "primary"]
    assert {d.stratum for d in prim} == {"proportional", "enriched"}
    assert all(0 < d.inclusion_prob <= 1 for d in prim) and all(d.excluded_reason is None for d in design)


def test_manifest_has_counts_hashes_provenance_and_nothing_per_cell(built) -> None:
    w, out, result = built
    manifest_bytes = (out / "packet" / bwp.MANIFEST_NAME).read_bytes()
    text = manifest_bytes.decode("utf-8")
    manifest = json.loads(manifest_bytes)
    c = manifest["counts"]
    assert c["rows_total"] == N_PROP + N_ENR + 6 and c["primary_rows"] == N_PROP + N_ENR
    assert c["controls_included"] == {"ablated": 4, "preserved": 2}
    assert c["controls_excluded"] == {"ablated": 0, "preserved": 0}
    assert c["rows_showing_paraphrase"] == c["rows_total"] and c["registered_design_conforms"] is False
    assert c["ablated_control_rows_whose_cq_differs_from_judge_input"] == 4   # DN-7: recorded
    assert c["semantic_check"] == {"pass": N_CQ, "fail": 0}
    # the rater-visible manifest carries NO layer count (proportional / enriched): those are sealed
    assert set(c) == {"rows_total", "primary_rows", "controls_included", "controls_excluded",
                      "rows_showing_paraphrase", "rows_showing_original_cq", "semantic_check",
                      "ablated_control_rows_whose_cq_differs_from_judge_input", "registered_design_conforms"}
    for needle in ('"proportional', '"enriched', "shortfall", "allocation", "layer_rows", "sum_w", "n_discordant"):
        assert needle not in text, needle
    # rule 3: input sha256s (cells.jsonl and the locked AH working CSV), the script's own sha256,
    # python/numpy/scipy versions, next to the output sha256s
    assert manifest["inputs"]["cells_jsonl"]["sha256"] == sha(w.cells.read_bytes())
    assert manifest["inputs"]["ah_labels_locked_working_csv"]["sha256"] == sha(w.labels.read_bytes())
    assert manifest["inputs"]["paraphrases_csv"]["sha256"] == sha(w.paraphrases.read_bytes())
    assert manifest["inputs"]["bank_csv"]["sha256"] == sha(w.bank.read_bytes())
    assert manifest["inputs"]["semantic_check"]["sha256"] == sha(w.semantic.read_bytes())
    tool = manifest["tool"]
    assert tool["script"] == "build_washout_packet.py" and tool["script_sha256"] == pc.sha256_file(Path(bwp.__file__))
    assert tool["python"] and tool["numpy"] != "" and tool["scipy"] != ""
    assert set(tool["imported_sources_sha256"]) == {"analyze_holdout.py", "run_holdout.py", "label_assist.py"}
    outs = manifest["outputs"]
    n_rows = N_PROP + N_ENR + 6
    assert set(outs) == {bwp.SHEET_NAME, f"sealed/{bwp.MAPPING_NAME}", f"server/{bwp.SUMS_NAME}"}
    assert outs[bwp.SHEET_NAME] == {"sha256": sha((out / "packet" / bwp.SHEET_NAME).read_bytes()), "rows": n_rows}
    assert outs[f"sealed/{bwp.MAPPING_NAME}"]["sha256"] == sha((out / "sealed" / bwp.MAPPING_NAME).read_bytes())
    assert outs[f"server/{bwp.SUMS_NAME}"] == {"sha256": sha(server_sums(out).read_bytes()), "n_view_files": n_rows}
    # no per-view digest and no view file name: they stay on the server
    for line in server_sums(out).read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ")
        assert digest not in text and name not in text
    assert bwp.SUMS_NAME in manifest["serving"] and "--sums" in manifest["serving"]
    # nothing per cell: no cell id, no opaque id, no CQ id, no category, no stratum, no J value
    mapping = read_mapping(out)
    forbidden = [m["source_cell_id"] for m in mapping["rows"]] + [m["cell_id"] for m in mapping["rows"]]
    forbidden += [f"CQB{i:02d}" for i in range(N_CQ)] + CATS + ["|J", "stratum\":", "\"selection\":",
                                                                "\"inclusion_prob\""]
    for needle in forbidden:
        assert needle not in text, needle
    assert str(out) not in text and str(w.root) not in text                           # no absolute path
    assert "SEALED" not in text and "salt" in text.lower()                            # says the salt is sealed
    for word in ("verified", "reference"):
        assert word not in text.lower()
    assert result["manifest_sha256"] == sha(manifest_bytes)


def test_g3w_statement_when_fewer_than_24_ablated_controls_are_valid(built) -> None:
    _, out, _ = built
    manifest_bytes = (out / "packet" / bwp.MANIFEST_NAME).read_bytes().decode("utf-8")
    g3w = read_manifest(out)["g3w"]
    assert g3w == {"n_valid_ablated": 4, "n_ablated_controls_in_cells": 4, "required_n_valid": 24,
                   "status": "G3-W not judged (n_valid < 24)"}
    assert "G3-W not judged (n_valid < 24)" in manifest_bytes


def test_g3w_is_judgeable_only_when_every_ablated_control_passes(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bwp, "G3W_MIN_VALID_ABLATED", 4)          # the fixture has 4 ablated controls
    w = make_world(tmp_path / "ok")
    run_build(w, tmp_path / "ok_out")
    assert read_manifest(tmp_path / "ok_out")["g3w"]["status"] == bwp.G3W_JUDGEABLE
    w2 = make_world(tmp_path / "bad")
    w2.rewrite_cells(lambda recs: next(r for r in recs if r["cell_kind"] == "ablated_control"
                                       ).__setitem__("artifact_digest", "0" * 64))
    run_build(w2, tmp_path / "bad_out")
    g = read_manifest(tmp_path / "bad_out")["g3w"]
    assert g["n_valid_ablated"] == 3 and g["status"] == "G3-W not judged (n_valid < 24)"


# ---------------------------------------------------------------------------
# controls: digest check, exclusion and reporting (DN-7)
# ---------------------------------------------------------------------------
def test_an_ablated_control_whose_regenerated_view_misses_the_digest_is_excluded_and_reported(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    victim = next(c for c in w.controls if c["cell_kind"] == "ablated_control")
    w.rewrite_cells(lambda recs: next(r for r in recs if r["cell_id"] == victim["cell_id"]
                                      ).__setitem__("artifact_digest", "f" * 64))
    result = run_build(w, tmp_path / "out")
    out = tmp_path / "out"
    ex = excluded_rows(out)
    assert len(ex) == 1 and (ex[0]["source_cell_id"], ex[0]["cell_kind"], ex[0]["excluded_reason"]) == (
        victim["cell_id"], "ablated_control", "digest_mismatch")      # kept in the design, with its reason
    assert ex[0]["position"] is None and ex[0]["view_ref"] is None
    assert victim["cell_id"] not in {m["source_cell_id"] for m in mapping_rows(out)}   # but never shown
    assert ex[0]["cell_id"] not in {r[0] for r in read_sheet(out)[1:]}
    assert read_mapping(out)["design"]["n_controls_excluded"] == 1
    assert len(read_sheet(out)) - 1 == N_PROP + N_ENR + 5
    c = read_manifest(out)["counts"]
    assert c["controls_excluded"] == {"ablated": 1, "preserved": 0}
    assert c["controls_included"] == {"ablated": 3, "preserved": 2}
    assert result["g3w"]["status"] == "G3-W not judged (n_valid < 24)"
    assert victim["cell_id"] not in (out / "packet" / bwp.MANIFEST_NAME).read_text(encoding="utf-8")


def test_a_preserved_control_with_a_wrong_digest_is_excluded(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    victim = next(c for c in w.controls if c["cell_kind"] == "preserved_control")
    w.rewrite_cells(lambda recs: next(r for r in recs if r["cell_id"] == victim["cell_id"]
                                      ).__setitem__("artifact_digest", "e" * 64))
    run_build(w, tmp_path / "out")
    ex = excluded_rows(tmp_path / "out")
    assert [(e["source_cell_id"], e["cell_kind"], e["excluded_reason"]) for e in ex] == [
        (victim["cell_id"], "preserved_control", "digest_mismatch")]


def test_an_ablation_that_finds_no_supporting_line_excludes_the_control(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    victim = next(c for c in w.controls if c["cell_kind"] == "ablated_control")
    rows = list(csv.reader(open(w.bank, newline="", encoding="utf-8")))
    for r in rows[1:]:
        if r[0] == victim["cq_id"]:
            r[3] = "brick:NoSuchTerm"
    with open(w.bank, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    run_build(w, tmp_path / "out")
    ex = excluded_rows(tmp_path / "out")
    assert ex[0]["source_cell_id"] == victim["cell_id"] and ex[0]["excluded_reason"] == "ablation_failed"


def test_a_primary_view_that_misses_the_judges_digest_aborts(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    (w.variants / "A" / "rendered_view.txt").write_text(view_text("A") + "tampered\n", encoding="utf-8")
    with pytest.raises(bwp.WashoutError, match="primary cell's original view"):
        run_build(w, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_control_label_values_are_never_read(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")                                  # control A cells hold "x" and ""
    rows = list(csv.reader(open(w.labels, newline="", encoding="utf-8")))
    assert any(r[0].startswith("ablated_control") and r[9] == "x" for r in rows)
    run_build(w, tmp_path / "out")                                   # an invalid control A does not matter


# ---------------------------------------------------------------------------
# paraphrase text, failed clusters
# ---------------------------------------------------------------------------
def test_rows_of_a_failed_cluster_show_the_original_cq_primary_and_control_alike(tmp_path: Path) -> None:
    failing = (1, 3)       # both have a control in the fixture (ablated A/1, preserved B/3)
    w = make_world(tmp_path / "in", failing=failing)
    run_build(w, tmp_path / "out")
    out = tmp_path / "out"
    mapping = {m["cell_id"]: m for m in mapping_rows(out)}
    bad = {cq_of(i) for i in failing}
    cq_of_cell = {p["cell_id"]: p["cq_id"] for p in w.primary}
    cq_of_cell.update({c["cell_id"]: c["cq_id"] for c in w.controls})
    shown_original = 0
    for r in read_sheet(out)[1:]:
        m = mapping[r[0]]
        cq = cq_of_cell[m["source_cell_id"]]
        if cq in bad:
            assert r[5] == w.bank_rows[cq]["question"] and m["cq_text_source"] == "original"
            shown_original += 1
        else:
            assert r[5] == w.para[cq] and m["cq_text_source"] == "paraphrase"
    manifest = read_manifest(out)["counts"]
    assert shown_original > 0 and manifest["rows_showing_original_cq"] == shown_original
    assert manifest["semantic_check"] == {"pass": N_CQ - 2, "fail": 2}
    # the ablated control on a failed cluster now shows the CQ the judge saw; the preserved one
    # on a failed cluster shows a CQ that differs from the paraphrase the judge saw
    flags = {m["source_cell_id"]: m["cq_shown_differs_from_judge_input"] for m in mapping.values()}
    assert flags["ablated_control:A:CQB01"] is False and flags["preserved_control:B:CQB03"] is True
    assert flags["ablated_control:C:CQB04"] is True and flags["preserved_control:E:CQB05"] is False
    assert manifest["ablated_control_rows_whose_cq_differs_from_judge_input"] == 3


def semantic_rows(ids: set[str], verdict: str = "pass", checker: str = "checker-1",
                  date: str = "2026-10-20") -> list[list[str]]:
    return [[c, verdict, checker, date] for c in sorted(ids)]


def write_semantic(path: Path, rows: list[list[str]], header: tuple[str, ...] = SEMANTIC_HEADER) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(header)
        wr.writerows(rows)
    return path


def test_the_semantic_check_file_must_be_complete_and_unambiguous(tmp_path: Path) -> None:
    ids = {cq_of(i) for i in range(N_CQ)}
    path = tmp_path / "s.csv"
    write_semantic(path, semantic_rows(ids))
    assert all(bwp.read_semantic_check(path, ids).values())
    write_semantic(path, [r + ["a free note"] for r in semantic_rows(ids)], header=(*SEMANTIC_HEADER, "note"))
    assert all(bwp.read_semantic_check(path, ids).values())              # further columns are ignored
    mixed = semantic_rows(ids)
    mixed[3][1] = "fail"
    write_semantic(path, mixed)
    got = bwp.read_semantic_check(path, ids)
    assert [c for c, ok in got.items() if not ok] == [mixed[3][0]] and sum(got.values()) == N_CQ - 1
    write_semantic(path, semantic_rows(ids)[:-1])
    with pytest.raises(bwp.WashoutError, match="covers"):
        bwp.read_semantic_check(path, ids)
    write_semantic(path, semantic_rows(ids) + [["CQB99", "pass", "checker-1", "2026-10-20"]])
    with pytest.raises(bwp.WashoutError, match="covers"):
        bwp.read_semantic_check(path, ids)
    write_semantic(path, semantic_rows(ids) + [["", "pass", "checker-1", "2026-10-20"]])   # a blank id is unknown
    with pytest.raises(bwp.WashoutError, match=r"covers 12 of 12 .*unknown ids: 1"):
        bwp.read_semantic_check(path, ids)
    write_semantic(path, [])
    with pytest.raises(bwp.WashoutError, match=r"covers 0 of 12"):
        bwp.read_semantic_check(path, ids)
    write_semantic(path, semantic_rows(ids) + [[sorted(ids)[0], "fail", "checker-1", "2026-10-20"]])
    with pytest.raises(bwp.WashoutError, match="repeats"):
        bwp.read_semantic_check(path, ids)


@pytest.mark.parametrize("dropped", SEMANTIC_HEADER)
def test_a_semantic_check_file_missing_any_of_the_four_columns_is_refused(tmp_path: Path, dropped: str) -> None:
    ids = {cq_of(i) for i in range(N_CQ)}
    keep = [i for i, c in enumerate(SEMANTIC_HEADER) if c != dropped]
    path = write_semantic(tmp_path / "s.csv", [[r[i] for i in keep] for r in semantic_rows(ids)],
                          header=tuple(SEMANTIC_HEADER[i] for i in keep))
    with pytest.raises(bwp.WashoutError, match=rf"columns missing.*{dropped}"):
        bwp.read_semantic_check(path, ids)
    path = write_semantic(tmp_path / "t.csv", semantic_rows(ids), header=("cq_id", "result", "who", "when"))
    with pytest.raises(bwp.WashoutError, match="columns missing"):                 # a differently named file
        bwp.read_semantic_check(path, ids)


@pytest.mark.parametrize("column", ["checker", "date"])
@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_every_semantic_check_row_needs_a_checker_and_a_date(tmp_path: Path, column: str, blank: str) -> None:
    ids = {cq_of(i) for i in range(N_CQ)}
    at = SEMANTIC_HEADER.index(column)
    rows = semantic_rows(ids)
    rows[7][at] = blank                                                  # one row of the twelve is enough
    path = write_semantic(tmp_path / "s.csv", rows)
    with pytest.raises(bwp.WashoutError, match=r"1 semantic-check rows have an empty checker or date") as err:
        bwp.read_semantic_check(path, ids)
    assert "CQB" not in str(err.value)                                   # a count, never the id
    rows = semantic_rows(ids)
    for row in rows:
        row[at] = blank
    with pytest.raises(bwp.WashoutError, match=rf"{N_CQ} semantic-check rows have an empty checker or date"):
        bwp.read_semantic_check(write_semantic(tmp_path / "t.csv", rows), ids)
    row_short = ",".join(semantic_rows(ids)[0][:at]) + "\n"            # a short row: the missing cell is empty too
    (tmp_path / "u.csv").write_text(",".join(SEMANTIC_HEADER) + "\n" + row_short, encoding="utf-8")
    with pytest.raises(bwp.WashoutError):
        bwp.read_semantic_check(tmp_path / "u.csv", ids)


@pytest.mark.parametrize("verdict", ["Pass", "PASS", "FAIL", "Fail", " pass", "pass ", "yes", "ok", "", "passed",
                                     "1", "true", "n/a", "pass/fail", "fail?"])
def test_a_verdict_other_than_exactly_pass_or_fail_is_refused(tmp_path: Path, verdict: str) -> None:
    ids = {cq_of(i) for i in range(N_CQ)}
    rows = semantic_rows(ids)
    rows[2][1] = verdict
    path = write_semantic(tmp_path / "s.csv", rows)
    with pytest.raises(bwp.WashoutError) as err:
        bwp.read_semantic_check(path, ids)
    # a count only: neither the id of the row nor the offending value is echoed
    assert str(err.value) == "1 semantic-check rows have a verdict that is not exactly pass or fail"
    assert all(bwp.read_semantic_check(write_semantic(tmp_path / "ok.csv", semantic_rows(ids)), ids).values())


def test_an_incomplete_semantic_check_file_stops_the_build_before_anything_is_written(tmp_path: Path) -> None:
    ids = {cq_of(i) for i in range(N_CQ)}
    for name, rows, header in (
            ("no_date_column", [r[:3] for r in semantic_rows(ids)], SEMANTIC_HEADER[:3]),
            ("blank_checker", [[c, v, "", d] for c, v, _, d in semantic_rows(ids)], SEMANTIC_HEADER),
            ("verdict", semantic_rows(ids, verdict="Pass"), SEMANTIC_HEADER)):
        w = make_world(tmp_path / name)
        write_semantic(w.semantic, rows, header=header)
        with pytest.raises(bwp.WashoutError):
            run_build(w, tmp_path / f"{name}_out")
        assert not (tmp_path / f"{name}_out").exists(), name


# ---------------------------------------------------------------------------
# paraphrase mode: the frozen paraphrase (default) or --no-paraphrase-fallback (PREREG sec.13.1 item 3)
# ---------------------------------------------------------------------------
def test_the_default_mode_is_frozen_paraphrase_in_both_manifests(built) -> None:
    _, out, result = built
    manifest, mapping = read_manifest(out), read_mapping(out)
    assert bwp.PARAPHRASE_FROZEN == "frozen_paraphrase" and bwp.PARAPHRASE_ORIGINAL == "original_cq_fallback"
    assert manifest["paraphrase_mode"] == mapping["paraphrase_mode"] == result["paraphrase_mode"] == "frozen_paraphrase"
    assert "frozen paraphrase" in manifest["paraphrase_mode_statement"]
    assert "--no-paraphrase-fallback" not in manifest["paraphrase_mode_statement"]
    assert "semantic_check" in manifest["inputs"] and "semantic_check" in mapping["inputs_sha256"]
    assert "paraphrase_mode" in mapping["schema"]


def test_a_failed_cluster_keeps_the_frozen_paraphrase_mode(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in", failing=(1, 3))
    run_build(w, tmp_path / "out")
    assert read_manifest(tmp_path / "out")["paraphrase_mode"] == "frozen_paraphrase"      # some rows show the original CQ,
    assert read_mapping(tmp_path / "out")["paraphrase_mode"] == "frozen_paraphrase"       # the mode is still the paraphrase


def test_no_paraphrase_fallback_shows_the_original_cq_on_every_row_and_needs_no_check_file(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    w.semantic.unlink()                                                  # the fallback has no semantic-check file
    out = tmp_path / "out"
    result = run_build(w, out, semantic_path=None, no_paraphrase_fallback=True)
    assert result["paraphrase_mode"] == "original_cq_fallback"
    mapping = {m["cell_id"]: m for m in mapping_rows(out)}
    original = {p["cell_id"]: w.bank_rows[p["cq_id"]]["question"] for p in w.primary}
    original.update({c["cell_id"]: w.bank_rows[c["cq_id"]]["question"] for c in w.controls})
    sheet = read_sheet(out)[1:]
    assert len(sheet) == N_PROP + N_ENR + 6
    for r in sheet:
        m = mapping[r[0]]
        assert r[5] == original[m["source_cell_id"]] and m["cq_text_source"] == "original"
    raw = (out / "packet" / bwp.SHEET_NAME).read_bytes().decode("utf-8")
    assert not any(text in raw for text in w.para.values())              # no paraphrase on any row
    manifest, mapping_json = read_manifest(out), read_mapping(out)
    assert manifest["paraphrase_mode"] == mapping_json["paraphrase_mode"] == "original_cq_fallback"
    statement = manifest["paraphrase_mode_statement"]
    assert "original CQ" in statement and "--no-paraphrase-fallback" in statement and "13.1 item 3" in statement
    c = manifest["counts"]
    assert c["rows_showing_paraphrase"] == 0 and c["rows_showing_original_cq"] == c["rows_total"]
    assert c["semantic_check"] is None                                   # no check was run
    assert "semantic_check" not in manifest["inputs"] and "semantic_check" not in mapping_json["inputs_sha256"]
    # the judge saw the paraphrase on a preserved control, so its row now differs from the judge's input; the
    # judge saw the original on an ablated control, so it does not
    flags = {m["source_cell_id"]: m["cq_shown_differs_from_judge_input"] for m in mapping.values()}
    assert all(v is True for k, v in flags.items() if k.startswith("preserved_control"))
    assert not any(v for k, v in flags.items() if not k.startswith("preserved_control"))
    assert c["ablated_control_rows_whose_cq_differs_from_judge_input"] == 0
    # nothing else moved: same selection, probabilities, order, views as the paraphrase build of the same world
    w2 = make_world(tmp_path / "in2")
    run_build(w2, tmp_path / "frozen")
    frozen = read_mapping(tmp_path / "frozen")

    def keyed(m: dict) -> list:
        return [(r["source_cell_id"], r["selection"], r["inclusion_prob"], r["position"]) for r in m["rows"]]

    assert keyed(mapping_json) == keyed(frozen)
    assert server_sums(out).read_bytes() == server_sums(tmp_path / "frozen").read_bytes()
    frozen_sheet = (tmp_path / "frozen" / "packet" / bwp.SHEET_NAME).read_bytes().decode("utf-8")
    assert any(text in frozen_sheet for text in w.para.values())         # the paraphrase build does show them
    assert (out / "packet" / bwp.SHEET_NAME).read_bytes() != frozen_sheet.encode("utf-8")


def test_no_paraphrase_fallback_builds_are_deterministic_and_still_pin_the_paraphrase_file(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    first = run_build(w, tmp_path / "one", semantic_path=None, no_paraphrase_fallback=True)
    second = run_build(w, tmp_path / "two", semantic_path=None, no_paraphrase_fallback=True)
    keys = ("sheet_sha256", "mapping_sha256", "manifest_sha256", "views_sums_sha256")
    assert {k: first[k] for k in keys} == {k: second[k] for k in keys}
    with pytest.raises(bwp.WashoutError, match="sha256"):                # the preserved controls need the frozen bytes
        run_build(w, tmp_path / "pinned", semantic_path=None, no_paraphrase_fallback=True,
                  expected={"paraphrases": "0" * 64})
    assert not (tmp_path / "pinned").exists()


def test_the_fallback_and_a_semantic_check_file_exclude_each_other(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    with pytest.raises(bwp.WashoutError, match="mutually exclusive"):
        run_build(w, tmp_path / "both", no_paraphrase_fallback=True)     # run_build still passes the check file
    with pytest.raises(bwp.WashoutError, match="semantic-check file is required"):
        run_build(w, tmp_path / "neither", semantic_path=None)
    assert not (tmp_path / "both").exists() and not (tmp_path / "neither").exists()
    assert bwp.paraphrase_mode_for(None, True) == "original_cq_fallback"
    assert bwp.paraphrase_mode_for(w.semantic, False) == "frozen_paraphrase"
    with pytest.raises(bwp.WashoutError, match="mutually exclusive"):
        bwp.paraphrase_mode_for(w.semantic, True)
    with pytest.raises(bwp.WashoutError, match="--no-paraphrase-fallback"):
        bwp.paraphrase_mode_for(None, False)


# ---------------------------------------------------------------------------
# order, salt dependence, determinism
# ---------------------------------------------------------------------------
def test_order_is_the_registered_constrained_shuffle_and_reports_the_spacing(built) -> None:
    w, out, result = built
    rows = mapping_rows(out)
    pos: dict[str, list[int]] = collections.defaultdict(list)
    cq_of_cell = {p["cell_id"]: p["cq_id"] for p in w.primary}
    cq_of_cell.update({c["cell_id"]: c["cq_id"] for c in w.controls})
    for i, m in enumerate(rows):
        pos[cq_of_cell[m["source_cell_id"]]].append(i)
    gaps = [b - a for v in pos.values() for a, b in zip(v, v[1:])]
    order = read_manifest(out)["order"]
    assert order["achieved_min_gap"] == (min(gaps) if gaps else None) == result["order"]["achieved_min_gap"]
    assert order["target_min_gap"] == 20 and order["seed"] == 20260913 and order["n_rows"] == len(rows)
    achieved = order["achieved_min_gap"]
    assert order["target_met"] == (achieved is None or achieved >= 20)
    assert order["target_feasible_by_length_bound"] == pc.gap_feasible(
        collections.Counter(cq_of_cell[m["source_cell_id"]] for m in rows).values(), 20)
    if order["target_feasible_by_length_bound"]:
        assert achieved >= 20                       # feasible by the length bound: the rule is met


def test_a_large_feasible_row_set_meets_the_20_position_rule(tmp_path: Path) -> None:
    rows = [{"cell_id": f"c{g:02d}-{m}", "cq_id": f"CQ{g:02d}"} for g in range(40) for m in range(3)]
    order, report = pc.constrained_order(sorted(rows, key=lambda r: r["cell_id"]), 20260913)
    assert report["target_met"] and report["achieved_min_gap"] >= 20 and len(order) == 120


def test_another_salt_changes_ids_view_names_and_order_but_not_the_selection_or_pi(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    run_build(w, tmp_path / "one")
    w.salt.write_bytes(b"a-completely-different-salt-0123456789\n")
    run_build(w, tmp_path / "two")
    one, two = read_mapping(tmp_path / "one"), read_mapping(tmp_path / "two")

    def by_source(mapping: dict) -> dict:
        return {m["source_cell_id"]: (m["selection"], m["stratum"], m["category_stratum"],
                                      m["inclusion_prob"], m["w"]) for m in mapping["rows"]}

    assert by_source(one) == by_source(two)                     # WHICH cells, their layer and pi: salt-free
    assert {m["cell_id"] for m in one["rows"]}.isdisjoint({m["cell_id"] for m in two["rows"]})
    assert {m["view_ref"] for m in one["rows"]}.isdisjoint({m["view_ref"] for m in two["rows"]})
    # the shuffle input is sorted by the OPAQUE id, so the position -> cell mapping is a function of the
    # salt: a throwaway salt cannot rebuild it
    assert [m["source_cell_id"] for m in one["rows"]] != [m["source_cell_id"] for m in two["rows"]]
    assert read_manifest(tmp_path / "one")["order"]["achieved_min_gap"] is not None


def test_the_shuffle_input_is_sorted_by_the_opaque_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, list[str]] = {}
    real = pc.constrained_order

    def spy(rows, seed, gap):
        seen["opaque"] = [r["opaque_id"] for r in rows]
        seen["cells"] = [r["cell_id"] for r in rows]
        return real(rows, seed, gap)

    monkeypatch.setattr(pc, "constrained_order", spy)
    w = make_world(tmp_path / "in")
    run_build(w, tmp_path / "out")
    assert seen["opaque"] == sorted(seen["opaque"]) and len(seen["opaque"]) == N_PROP + N_ENR + 6
    assert seen["cells"] != sorted(seen["cells"])                # and NOT by the public cell id
    order = read_manifest(tmp_path / "out")["order"]
    assert order["shuffle_input_order"] == "opaque_id ascending (depends on the sealed salt)"
    assert order["best_gap_by_length_bound"] >= 1


def test_two_runs_give_identical_output_hashes(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    first = run_build(w, tmp_path / "one")
    second = run_build(w, tmp_path / "two")
    keys = ("sheet_sha256", "mapping_sha256", "manifest_sha256", "views_sums_sha256")
    assert {k: first[k] for k in keys} == {k: second[k] for k in keys}

    def tree(root: Path) -> dict[str, str]:
        return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(root.rglob("*")) if p.is_file()}

    assert tree(tmp_path / "one") == tree(tmp_path / "two")            # every file, views included
    again = run_build(w, tmp_path / "one")                             # rerun over its own output
    assert set(again["write_status"].values()) == {"unchanged"}
    # the manifest repeats the output hashes the runs reported
    assert first["manifest_sha256"] == sha((tmp_path / "one" / "packet" / bwp.MANIFEST_NAME).read_bytes())


def test_each_output_directory_holds_only_what_its_audience_needs(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    before = {p for p in tmp_path.rglob("*")}
    run_build(w, tmp_path / "out")
    out = tmp_path / "out"
    new = {p for p in tmp_path.rglob("*")} - before
    assert all(out in p.parents or p == out for p in new)
    assert {p.name for p in out.iterdir()} == {"sealed", "packet", "server"}
    assert {p.name for p in (out / "sealed").iterdir()} == {bwp.MAPPING_NAME}
    assert {p.name for p in (out / "packet").iterdir()} == {bwp.SHEET_NAME, bwp.MANIFEST_NAME}   # all the rater gets
    assert {p.name for p in (out / "server").iterdir()} == {bwp.VIEWS_DIR, bwp.SUMS_NAME}
    assert not any("salt" in p.name or ".tmp" in p.name for p in out.rglob("*"))


def test_sealed_and_server_side_files_are_private(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    old = os.umask(0o022)
    try:
        run_build(w, tmp_path / "out")
    finally:
        os.umask(old)
    out = tmp_path / "out"
    for directory in (out / "sealed", out / "server", server_views(out)):
        assert mode_of(directory) == 0o700, directory.name
    private = [out / "sealed" / bwp.MAPPING_NAME, server_sums(out), *server_views(out).iterdir()]
    assert len(private) == 2 + N_PROP + N_ENR + 6
    for f in private:
        assert mode_of(f) == 0o600, f.name
    os.chmod(out / "sealed" / bwp.MAPPING_NAME, 0o644)           # a rerun tightens what was loosened in between
    os.chmod(server_sums(out), 0o664)
    again = run_build(w, out)
    assert mode_of(out / "sealed" / bwp.MAPPING_NAME) == 0o600 and mode_of(server_sums(out)) == 0o600
    assert again["write_status"]["mapping"] == again["write_status"]["views_sums"] == "unchanged"


# ---------------------------------------------------------------------------
# guards and refusals
# ---------------------------------------------------------------------------
def test_sealed_and_server_outputs_inside_the_repository_are_refused_and_nothing_is_written(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    inside = HERE / "_sealed_must_not_be_created"
    with pytest.raises(bwp.WashoutError, match="sealed output directory.*inside the repository"):
        run_build(w, tmp_path / "out", sealed_dir=inside)
    inside_server = HERE / "_server_must_not_be_created"
    with pytest.raises(bwp.WashoutError, match="server-side output directory.*inside the repository"):
        run_build(w, tmp_path / "out", server_dir=inside_server)
    assert not inside.exists() and not inside_server.exists() and not (tmp_path / "out").exists()
    wt = tmp_path / ".claude" / "worktrees" / "wt"
    for name in ("sealed_dir", "server_dir"):
        with pytest.raises(bwp.WashoutError, match="inside the repository"):
            run_build(w, tmp_path / "out2", **{name: wt / name})
    assert not wt.exists() and not (tmp_path / "out2").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_the_main_checkout_is_refused_as_well_as_the_worktree(tmp_path: Path) -> None:
    """A worktree's own .git lookup finds only that worktree; the guard must also know the main
    checkout (git --git-common-dir). Pure checks: nothing is created if the guard were broken."""
    common = subprocess.run(["git", "rev-parse", "--git-common-dir"], cwd=HERE, capture_output=True, text=True,
                            check=True).stdout.strip()
    main_root = (HERE / common).resolve().parent
    for what in ("the sealed output directory", "the server-side output directory", "the salt file"):
        with pytest.raises(bwp.WashoutError, match="inside the repository"):
            bwp.refuse_inside_repo(main_root / "never_created" / "x", what)
        with pytest.raises(bwp.WashoutError, match="inside the repository"):
            bwp.refuse_inside_repo(HERE / "never_created" / "x", what)
    bwp.refuse_inside_repo(tmp_path / "outside" / "x", "the sealed output directory")


def test_salt_inside_the_repository_the_packet_or_the_server_directory_is_refused(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    with pytest.raises(bwp.WashoutError, match="salt file"):
        run_build(w, tmp_path / "out", salt_file=HERE / "salt.txt")
    inside_packet = tmp_path / "out" / "packet" / "salt.txt"
    inside_packet.parent.mkdir(parents=True)
    inside_packet.write_bytes(SALT)
    with pytest.raises(bwp.WashoutError, match="packet directory"):
        run_build(w, tmp_path / "out", salt_file=inside_packet)
    inside_server = tmp_path / "out2" / "server" / "salt.txt"
    inside_server.parent.mkdir(parents=True)
    inside_server.write_bytes(SALT)
    with pytest.raises(bwp.WashoutError, match="server-side directory"):
        run_build(w, tmp_path / "out2", salt_file=inside_server)


def test_the_three_output_directories_must_be_apart(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    with pytest.raises(bwp.WashoutError, match="sealed and packet directories must not contain one another"):
        run_build(w, tmp_path / "out", sealed_dir=tmp_path / "out", packet_dir=tmp_path / "out" / "packet")
    with pytest.raises(bwp.WashoutError, match="contain one another"):
        run_build(w, tmp_path / "out", sealed_dir=tmp_path / "x" / "sealed", packet_dir=tmp_path / "x")
    with pytest.raises(bwp.WashoutError, match="sealed and server directories must not contain one another"):
        run_build(w, tmp_path / "out", sealed_dir=tmp_path / "s", server_dir=tmp_path / "s" / "server")
    with pytest.raises(bwp.WashoutError, match="packet and server directories must not contain one another"):
        run_build(w, tmp_path / "out", packet_dir=tmp_path / "p", server_dir=tmp_path / "p" / "views_here")
    with pytest.raises(bwp.WashoutError, match="contain one another"):
        run_build(w, tmp_path / "out", packet_dir=tmp_path / "p" / "packet", server_dir=tmp_path / "p")
    assert not (tmp_path / "out").exists()


def test_an_output_that_is_an_input_is_refused(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    # a collision: the manifest path is the semantic-check input
    clash = tmp_path / "clash"
    (clash / "packet").mkdir(parents=True)
    (clash / "packet" / bwp.MANIFEST_NAME).write_bytes(w.semantic.read_bytes())
    with pytest.raises(bwp.WashoutError, match="same file"):
        run_build(w, clash, semantic_path=clash / "packet" / bwp.MANIFEST_NAME)
    # ... or the server-side sums file
    sums_clash = tmp_path / "sums_clash"
    (sums_clash / "server").mkdir(parents=True)
    (sums_clash / "server" / bwp.SUMS_NAME).write_bytes(w.semantic.read_bytes())
    with pytest.raises(bwp.WashoutError, match="same file"):
        run_build(w, sums_clash, semantic_path=sums_clash / "server" / bwp.SUMS_NAME)


def test_an_existing_different_output_is_not_overwritten_without_force(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    run_build(w, tmp_path / "out")
    (tmp_path / "out" / "packet" / bwp.SHEET_NAME).write_bytes(b"tampered")
    with pytest.raises(FileExistsError):
        run_build(w, tmp_path / "out")
    assert run_build(w, tmp_path / "out", force=True)["write_status"]["sheet"] == "overwritten"


def test_pins_refuse_a_changed_input(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    for key, flag in (("cells_jsonl", "cells"), ("ah_labels", "labels"), ("paraphrases", "paraphrases"),
                      ("bank", "bank")):
        with pytest.raises(bwp.WashoutError, match="sha256"):
            run_build(w, tmp_path / f"out_{key}", expected={key: "0" * 64})
        assert not (tmp_path / f"out_{key}").exists()
    good = {"cells_jsonl": sha(w.cells.read_bytes()), "ah_labels": sha(w.labels.read_bytes()),
            "paraphrases": sha(w.paraphrases.read_bytes()), "bank": sha(w.bank.read_bytes())}
    run_build(w, tmp_path / "out_ok", expected=good)


def test_the_registered_design_check_needs_allow_partial(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    with pytest.raises(bwp.WashoutError, match="registered 188-cell design"):
        run_build(w, tmp_path / "out", allow_partial=False)


def test_an_invalid_judge_call_a_missing_ah_label_or_unknown_label_row_is_refused(tmp_path: Path) -> None:
    w = make_world(tmp_path / "a")
    w.rewrite_cells(lambda recs: recs[0].__setitem__("judge_response_parsed", False))
    with pytest.raises(bwp.WashoutError, match="invalid judge call"):
        run_build(w, tmp_path / "a_out")
    w = make_world(tmp_path / "b")
    rows = list(csv.reader(open(w.labels, newline="", encoding="utf-8")))
    rows[1][9] = ""
    with open(w.labels, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    with pytest.raises(bwp.WashoutError, match="AH label CSV rejected") as rejected:
        run_build(w, tmp_path / "b_out")
    assert "primary:" not in str(rejected.value) and "CQB" not in str(rejected.value)   # no cell id in the text
    w = make_world(tmp_path / "c")
    with open(w.labels, "a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(["primary:Z:CQB99", "", "", "", "", "", "", "", "", "1", "", ""])
    with pytest.raises(bwp.WashoutError, match="not in cells.jsonl"):
        run_build(w, tmp_path / "c_out")


def test_a_cq_missing_from_the_paraphrase_file_or_a_cluster_mismatch_is_refused(tmp_path: Path) -> None:
    w = make_world(tmp_path / "a")
    rows = [r for r in csv.reader(open(w.paraphrases, newline="", encoding="utf-8")) if r[0] != "CQB03"]
    with open(w.paraphrases, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    with pytest.raises(bwp.WashoutError):
        run_build(w, tmp_path / "a_out")
    w = make_world(tmp_path / "b")
    rows = list(csv.reader(open(w.paraphrases, newline="", encoding="utf-8")))
    rows[2][1] = "OTHER"
    with open(w.paraphrases, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    with pytest.raises(bwp.WashoutError, match="cluster_id"):
        run_build(w, tmp_path / "b_out")


def test_too_few_strata_seats_is_refused(tmp_path: Path) -> None:
    w = make_world(tmp_path / "in")
    with pytest.raises(bwp.WashoutError, match="exceed"):
        run_build(w, tmp_path / "out", n_proportional=3)


# ---------------------------------------------------------------------------
# the command line: counts and hashes only on stdout
# ---------------------------------------------------------------------------
def cli_argv(w: World, out: Path) -> list[str]:
    return ["--cells", str(w.cells), "--ah-labels", str(w.labels), "--paraphrases", str(w.paraphrases),
            "--bank", str(w.bank), "--semantic-check", str(w.semantic), "--variants-dir", str(w.variants),
            "--salt-file", str(w.salt), "--sealed-dir", str(out / "sealed"), "--packet-dir", str(out / "packet"),
            "--server-dir", str(out / "server"), "--allow-partial",
            "--expected-cells-sha256", sha(w.cells.read_bytes()),
            "--expected-ah-labels-sha256", sha(w.labels.read_bytes()),
            "--expected-paraphrases-sha256", sha(w.paraphrases.read_bytes()),
            "--expected-bank-sha256", sha(w.bank.read_bytes())]


def test_cli_prints_only_counts_and_hashes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(bwp, "N_PROPORTIONAL", N_PROP)
    monkeypatch.setattr(bwp, "N_ENRICHED", N_ENR)
    monkeypatch.setattr(bwp, "PI_RUNS", RUNS)
    w = make_world(tmp_path / "in")
    out = tmp_path / "out"
    assert bwp.main(cli_argv(w, out)) == 0
    captured = capsys.readouterr()
    shown = captured.out
    mapping = read_mapping(out)
    secrets = ([m["source_cell_id"] for m in mapping["rows"]] + [m["cell_id"] for m in mapping["rows"]]
               + [m["view_ref"] for m in mapping["rows"] if m["view_ref"]] + [f"CQB{i:02d}" for i in range(N_CQ)] + CATS
               + ["|J", "stratum", "pi=", "w=", "J=", "A=", "primary:", "_control:", SALT.decode()])
    for needle in secrets:
        assert needle not in shown and needle not in captured.err, needle
    assert f"rows={N_PROP + N_ENR + 6}" in shown and "g3w: G3-W not judged (n_valid < 24)" in shown
    assert "paraphrase_mode=frozen_paraphrase" in shown
    assert "achieved_min_gap=" in shown
    lines = shown.strip().splitlines()
    hashes = [l.split("=", 1)[1] for l in lines if l.split("=", 1)[0].endswith("_sha256")]
    assert len(hashes) == 4 and all(re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes)
    assert hashes[1] == sha((out / "sealed" / bwp.MAPPING_NAME).read_bytes())
    assert hashes[2] == sha(server_sums(out).read_bytes())            # views_sha256sums_sha256
    assert "views_sha256sums_sha256=" in shown


def fallback_argv(w: World, out: Path) -> list[str]:
    argv = cli_argv(w, out)
    at = argv.index("--semantic-check")
    del argv[at:at + 2]
    return argv + ["--no-paraphrase-fallback"]


def test_cli_no_paraphrase_fallback_builds_without_a_semantic_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                                   capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(bwp, "N_PROPORTIONAL", N_PROP)
    monkeypatch.setattr(bwp, "N_ENRICHED", N_ENR)
    monkeypatch.setattr(bwp, "PI_RUNS", RUNS)
    w = make_world(tmp_path / "in")
    w.semantic.unlink()
    out = tmp_path / "out"
    assert bwp.main(fallback_argv(w, out)) == 0
    shown = capsys.readouterr().out
    assert "paraphrase_mode=original_cq_fallback" in shown and f"rows={N_PROP + N_ENR + 6}" in shown
    assert read_manifest(out)["paraphrase_mode"] == read_mapping(out)["paraphrase_mode"] == "original_cq_fallback"
    for needle in ("CQB", "primary:", "_control:", "stratum"):
        assert needle not in shown, needle


def test_cli_the_fallback_excludes_a_semantic_check_file_and_one_of_them_is_required(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(bwp, "N_PROPORTIONAL", N_PROP)
    monkeypatch.setattr(bwp, "N_ENRICHED", N_ENR)
    monkeypatch.setattr(bwp, "PI_RUNS", RUNS)
    w = make_world(tmp_path / "in")
    out = tmp_path / "out"
    with pytest.raises(SystemExit) as both:                              # argparse: mutually exclusive
        bwp.main(cli_argv(w, out) + ["--no-paraphrase-fallback"])
    assert both.value.code == 2 and "not allowed with" in capsys.readouterr().err
    neither = cli_argv(w, out)
    at = neither.index("--semantic-check")
    del neither[at:at + 2]
    with pytest.raises(SystemExit) as none_given:
        bwp.main(neither)
    err = capsys.readouterr().err
    assert none_given.value.code == 2 and "missing --semantic-check" in err and "--no-paraphrase-fallback" in err
    assert not out.exists()


def test_cli_refusals_exit_1_with_nothing_on_stdout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(bwp, "N_PROPORTIONAL", N_PROP)
    monkeypatch.setattr(bwp, "N_ENRICHED", N_ENR)
    monkeypatch.setattr(bwp, "PI_RUNS", RUNS)
    w = make_world(tmp_path / "in")
    out = tmp_path / "out"
    argv = cli_argv(w, out)
    assert bwp.main(argv + ["--seed", "1"]) == 1
    assert bwp.main([a for a in argv if a != "--allow-partial"]) == 1            # not the registered design
    bad = list(argv)
    bad[bad.index("--expected-cells-sha256") + 1] = "0" * 64
    assert bwp.main(bad) == 1
    inside = Path(bwp.__file__).resolve().parent / "_sealed_must_not_be_created"
    refused = list(argv)
    refused[refused.index("--sealed-dir") + 1] = str(inside)
    assert bwp.main(refused) == 1 and not inside.exists()
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.count("refused") == 4
    assert not out.exists()


def test_the_default_pins_refuse_a_synthetic_world(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    w = make_world(tmp_path / "in")
    argv = ["--cells", str(w.cells), "--ah-labels", str(w.labels), "--paraphrases", str(w.paraphrases),
            "--bank", str(w.bank), "--semantic-check", str(w.semantic), "--variants-dir", str(w.variants),
            "--salt-file", str(w.salt), "--sealed-dir", str(tmp_path / "out" / "sealed"),
            "--packet-dir", str(tmp_path / "out" / "packet"), "--server-dir", str(tmp_path / "out" / "server"),
            "--allow-partial"]
    assert bwp.main(argv) == 1
    assert "sha256" in capsys.readouterr().err and not (tmp_path / "out").exists()


def test_cli_needs_every_directory_and_the_salt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    w = make_world(tmp_path / "in")
    argv = cli_argv(w, tmp_path / "out")
    for flag in ("--server-dir", "--sealed-dir", "--packet-dir", "--salt-file", "--ah-labels", "--semantic-check"):
        cut = list(argv)
        at = cut.index(flag)
        del cut[at:at + 2]
        with pytest.raises(SystemExit) as exc:
            bwp.main(cut)
        assert exc.value.code == 2, flag
        assert f"missing {flag}" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_cli_refuses_a_shared_or_short_salt_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                               capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(bwp, "N_PROPORTIONAL", N_PROP)
    monkeypatch.setattr(bwp, "N_ENRICHED", N_ENR)
    monkeypatch.setattr(bwp, "PI_RUNS", RUNS)
    w = make_world(tmp_path / "in")
    os.chmod(w.salt, 0o640)
    assert bwp.main(cli_argv(w, tmp_path / "out")) == 1
    assert "group/others" in capsys.readouterr().err
    os.chmod(w.salt, 0o600)
    w.salt.write_bytes(b"x" * 16)
    assert bwp.main(cli_argv(w, tmp_path / "out")) == 1
    assert "at least 32" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("exc", [ValueError("primary:A:CQB01 has a bad value"), KeyError("primary:A:CQB01")])
def test_loader_errors_are_reported_by_type_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str], exc: Exception) -> None:
    w = make_world(tmp_path / "in")

    def boom(**kwargs: object) -> None:
        raise exc

    monkeypatch.setattr(bwp, "build", boom)
    assert bwp.main(cli_argv(w, tmp_path / "out")) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and type(exc).__name__ in captured.err and "withheld" in captured.err
    assert "primary:" not in captured.err and "CQB01" not in captured.err


def break_judge(w: World) -> None:
    w.rewrite_cells(lambda recs: recs[0].__setitem__("judge_response_parsed", False))


def break_label_missing(w: World) -> None:
    rows = list(csv.reader(open(w.labels, newline="", encoding="utf-8")))
    rows[1][9] = ""
    with open(w.labels, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def break_label_unknown(w: World) -> None:
    with open(w.labels, "a", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerow(["primary:Z:CQB99", "", "", "", "", "", "", "", "", "1", "", ""])


def break_paraphrase_missing(w: World) -> None:
    rows = [r for r in csv.reader(open(w.paraphrases, newline="", encoding="utf-8")) if r[0] != "CQB03"]
    with open(w.paraphrases, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def break_cluster(w: World) -> None:
    rows = list(csv.reader(open(w.paraphrases, newline="", encoding="utf-8")))
    rows[2][1] = "OTHER"
    with open(w.paraphrases, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def break_primary_view(w: World) -> None:
    for v in VARIANTS:
        (w.variants / v / "rendered_view.txt").write_text(view_text(v) + "tampered\n", encoding="utf-8")


def break_semantic_blank_checker(w: World) -> None:
    rows = list(csv.reader(open(w.semantic, newline="", encoding="utf-8")))
    rows[3][2] = ""
    with open(w.semantic, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def break_semantic_no_date(w: World) -> None:
    rows = [r[:3] for r in csv.reader(open(w.semantic, newline="", encoding="utf-8"))]
    with open(w.semantic, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def break_semantic_verdict(w: World) -> None:
    rows = list(csv.reader(open(w.semantic, newline="", encoding="utf-8")))
    rows[2][1] = "Pass"
    with open(w.semantic, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def break_semantic(w: World) -> None:
    rows = list(csv.reader(open(w.semantic, newline="", encoding="utf-8")))[:-1]
    with open(w.semantic, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


@pytest.mark.parametrize("breaker", [break_judge, break_label_missing, break_label_unknown, break_paraphrase_missing,
                                     break_cluster, break_primary_view, break_semantic,
                                     break_semantic_blank_checker, break_semantic_no_date,
                                     break_semantic_verdict], ids=lambda f: f.__name__)
def test_refusals_name_no_cell_or_cq_ids_on_the_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str], breaker) -> None:
    monkeypatch.setattr(bwp, "N_PROPORTIONAL", N_PROP)
    monkeypatch.setattr(bwp, "N_ENRICHED", N_ENR)
    monkeypatch.setattr(bwp, "PI_RUNS", RUNS)
    w = make_world(tmp_path / "in")
    breaker(w)
    argv = cli_argv(w, tmp_path / "out")
    assert bwp.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "refused" in captured.err
    ids = [p["cell_id"] for p in w.primary] + [c["cell_id"] for c in w.controls] + [cq_of(i) for i in range(N_CQ)]
    for needle in ids + ["primary:", "_control:", "CQB99"]:
        assert needle not in captured.err, needle
    assert not (tmp_path / "out").exists()
