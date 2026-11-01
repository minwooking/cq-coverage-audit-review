#!/usr/bin/env python3
"""Helpers shared by the two PREREG sec.12 packet builders (stdlib only).

Used by ``build_second_annotator_packet.py`` (sec.12.4) and
``build_washout_packet.py`` (sec.12.3). Nothing here reads a judge score or a label.

The presentation order is the registered constrained shuffle: the same-CQ spacing
rule (PREREG sec.3, "순서 무작위화"; seed 20260913) implemented by
``annotation/packet/build_label_packet.py::_constrained_shuffle``, the function that
produced the AH-pass order. It is loaded from that file, not copied, so there is one
definition. For a row set where the 20-position separation is infeasible that function
falls back to a heuristic that can leave pairs much closer than necessary, so
``constrained_order`` re-runs it at decreasing ``min_gap`` and keeps the largest gap
the registered greedy actually attains. The achieved minimum is always reported.
"""
from __future__ import annotations

import collections
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
import sys
from pathlib import Path
from typing import Iterable, Sequence

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent
REGISTERED_SEED = 20260913          # PREREG freeze block (L14)
REGISTERED_MIN_GAP = 20             # PREREG sec.3 (L529-536)
LABEL_COLUMNS = ("evidence_span_verbatim", "A", "rater_L1", "note")
SHUFFLE_SOURCE = ACCESS / "annotation" / "packet" / "build_label_packet.py"

_shuffle_module = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(obj: object) -> bytes:
    """Deterministic bytes for a manifest/mapping: sorted keys, 2-space indent, LF."""
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def fsync_dir(directory: Path) -> None:
    """Make a rename or a new file in ``directory`` durable (POSIX; a no-op where unsupported)."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def ensure_private_dir(path: Path, mode: int = 0o700) -> Path:
    """Create ``path`` (and parents) and set its mode exactly (a sealed or server-side directory)."""
    Path(path).mkdir(parents=True, exist_ok=True)
    os.chmod(path, mode)
    return Path(path)


def write_bytes_atomic(path: Path, data: bytes, *, mode: int | None = None) -> None:
    """Write ``data`` to ``path`` through a temp file: the bytes are fsynced before the rename, the
    directory after it, so a crash leaves the old file or the new one, never a torn one. ``mode``
    (e.g. 0o600 for a sealed output) is set exactly; None keeps the process default."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666 if mode is None else mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    fsync_dir(path.parent)


def write_checked(path: Path, data: bytes, *, force: bool = False, mode: int | None = None) -> str:
    """Write ``data`` to ``path``: 'created', 'unchanged' (same bytes already there) or
    'overwritten' (only with ``force``). A differing existing file is refused, never
    silently replaced. With ``mode`` an unchanged file is tightened to that mode."""
    if path.exists():
        if path.read_bytes() == data:
            if mode is not None:
                os.chmod(path, mode)
            return "unchanged"
        if not force:
            raise FileExistsError(f"refusing to overwrite {path} (different bytes); use --force")
        write_bytes_atomic(path, data, mode=mode)
        return "overwritten"
    write_bytes_atomic(path, data, mode=mode)
    return "created"


def registered_shuffle_module():
    """The module that defines the registered ``_constrained_shuffle`` (loaded by path)."""
    global _shuffle_module
    if _shuffle_module is None:
        spec = importlib.util.spec_from_file_location(
            "_registered_build_label_packet", SHUFFLE_SOURCE)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {SHUFFLE_SOURCE}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _shuffle_module = module
    return _shuffle_module


def min_same_key_gap(order: Sequence[dict], key: str = "cq_id") -> int | None:
    """Smallest position difference between two rows with the same ``key`` value, or None
    when no value repeats."""
    positions: dict[str, list[int]] = collections.defaultdict(list)
    for position, row in enumerate(order):
        positions[str(row[key])].append(position)
    gaps = [b - a for values in positions.values() for a, b in zip(values, values[1:])]
    return min(gaps) if gaps else None


def gap_feasible(group_sizes: Iterable[int], gap: int) -> bool:
    """Necessary and sufficient length bound for "same group at least ``gap`` positions
    apart" (position difference >= gap): (M - 1) * gap + k <= n, where M is the largest
    group size and k the number of groups of that size."""
    sizes = [s for s in group_sizes if s > 0]
    if not sizes:
        return True
    biggest = max(sizes)
    return (biggest - 1) * gap + sum(1 for s in sizes if s == biggest) <= sum(sizes)


def constrained_order(rows: Sequence[dict], seed: int = REGISTERED_SEED,
                      target_gap: int = REGISTERED_MIN_GAP,
                      key: str = "cq_id") -> tuple[list[dict], dict]:
    """Seeded presentation order with same-``key`` rows at least ``target_gap`` apart when
    feasible; otherwise the largest gap the registered greedy attains. The caller fixes
    the input order (the shuffle is a function of it); this function never reorders it.
    Returns ``(order, report)``; ``report`` holds counts only."""
    module = registered_shuffle_module()
    if key != "cq_id":
        raise ValueError("the registered shuffle groups on the 'cq_id' key")
    sizes = collections.Counter(str(r[key]) for r in rows)
    chosen: list[dict] | None = None
    applied = None
    for gap in range(target_gap, 0, -1):
        with contextlib.redirect_stderr(io.StringIO()):   # the registered fn warns when infeasible
            order = module._constrained_shuffle(list(rows), seed, min_gap=gap)
        achieved = min_same_key_gap(order, key)
        if achieved is None or achieved >= gap:
            chosen, applied = order, gap
            break
    if chosen is None:   # unreachable: gap 1 is always met
        raise RuntimeError("constrained shuffle found no arrangement")
    achieved = min_same_key_gap(chosen, key)
    feasible_at_target = gap_feasible(sizes.values(), target_gap)
    # the largest gap <= target that the length bound allows: the shuffle must reach it (the
    # bound is necessary and sufficient, and the greedy attains it), or the build stops
    best_by_bound = next((g for g in range(target_gap, 0, -1) if gap_feasible(sizes.values(), g)), 1)
    if achieved is not None and achieved < best_by_bound:
        raise RuntimeError(
            f"the {best_by_bound}-position separation is feasible for this row set "
            f"(length bound) but the shuffle reached only {achieved}")
    biggest = max(sizes.values(), default=0)
    report = {
        "method": "annotation/packet/build_label_packet.py::_constrained_shuffle "
                  "(greedy, most-remaining eligible group first) re-run at decreasing "
                  "min_gap until the gap is met",
        "seed": seed,
        "n_rows": len(rows),
        "target_min_gap": target_gap,
        "applied_min_gap": applied,
        "achieved_min_gap": achieved,
        "target_met": achieved is None or achieved >= target_gap,
        "same_cq_repeats": achieved is not None,
        "largest_same_cq_group": biggest,
        "target_feasible_by_length_bound": feasible_at_target,
        "best_gap_by_length_bound": best_by_bound,
        "shuffle_module_sha256": sha256_file(SHUFFLE_SOURCE),
    }
    return chosen, report


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not installed"


def provenance(script: Path, sources: dict[str, Path] | None = None) -> dict:
    """What produced a manifest: the builder's own sha256, this module's, the interpreter and the
    numpy/scipy versions (the registered analyzer imports both), and the sha256 of the sibling
    sources the builder imports. No path, no timestamp: two runs give identical manifests."""
    out: dict = {"script": Path(script).name, "script_sha256": sha256_file(Path(script)),
                 "packet_common_sha256": sha256_file(Path(__file__)),
                 "python": platform.python_version(),
                 "numpy": _package_version("numpy"), "scipy": _package_version("scipy")}
    if sources:
        out["imported_sources_sha256"] = {name: sha256_file(Path(path))
                                          for name, path in sorted(sources.items())}
    return out


def repo_relative(path: Path) -> str:
    """POSIX path relative to the repository root when inside it, else the file name only
    (an absolute path would bake a worktree location into a committed manifest)."""
    resolved = Path(path).resolve()
    for root in (ACCESS.parent.parent, ACCESS):
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return resolved.name


if __name__ == "__main__":  # pragma: no cover
    print(__doc__)
    sys.exit(0)
