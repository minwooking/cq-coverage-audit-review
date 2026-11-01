"""Root aggregate MANIFEST.json derivation in package_variants.

run_holdout.py refuses a domain whose package dir has no root MANIFEST.json
("변이 매니페스트가 없습니다"), because package_variants only ever wrote per-variant
manifests plus the SHA256.txt root index; the Brick aggregate at
harness/variants/MANIFEST.json was created ad hoc and must stay untouched.
package_variants must now derive the aggregate itself, deterministically, from
the per-variant manifests, mirroring the Brick shape.

Because main() now also writes a derived aggregate for Brick (the task's chosen
safe rule: derive-and-write is idempotent and truthful), these tests prove the
derived shape is semantically loadable by the runner's registered loader — the
Brick dir's existing file and any future re-packaged one both load.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "variants"))

import package_variants  # noqa: E402
import run_holdout  # noqa: E402

SPEC_SHA = "eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e"
CORPUS = "data/iof_core_202603/iof_corpus.json"
NOW = "2026-10-10T00:00:00+00:00"


def _stage_variant(pkg: Path, vid: str, *, simulated: bool = True,
                   warning: str = "shared warning", spec: str = SPEC_SHA,
                   known_defect: str | None = None) -> dict:
    """One fake packaged variant dir: graph file, rendered view, per-variant manifest."""
    d = pkg / vid
    d.mkdir(parents=True)
    graph = d / f"graph_{vid}.ttl"
    graph.write_text(f"# fake graph {vid}\n", encoding="utf-8")
    view = d / "rendered_view.txt"
    view.write_text(f"view line 1 for {vid}\nview line 2 for {vid}\n", encoding="utf-8")
    manifest = {
        "variant_id": vid,
        "description": f"description of variant {vid}",
        "comparison_role": "confirmatory A -> B source endpoint" if vid == "A" else "exploratory",
        "generation_method": "uv run chunktograph ...",
        "input_corpus": f"paper/access2026/{CORPUS}",
        "input_corpus_sha256": "c" * 64,
        "model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8",
        "endpoint_host": "127.0.0.1",
        "temperature": 0.0,
        "graph_file": graph.name,
        "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "rendered_view_file": view.name,
        "rendered_view_sha256": hashlib.sha256(view.read_bytes()).hexdigest(),
        "rendered_view_lines": 2,
        "rendered_view_chars": len(view.read_text(encoding="utf-8")),
        "rendering_spec_sha256": spec,
        "SIMULATED": simulated,
        "simulation_warning": warning,
        "generated_utc": NOW,
    }
    if known_defect is not None:
        manifest["known_defect"] = known_defect
    (d / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _read(pkg: Path) -> dict:
    return json.loads((pkg / "MANIFEST.json").read_text(encoding="utf-8"))


def test_root_aggregate_derives_keys_paths_and_digests(tmp_path):
    # Two fake variant packages (non-Brick domain path); the derivation must not
    # hard-code the count -- the six-variant check belongs to the registered loader.
    pkg = tmp_path / "variants_fake"
    a = _stage_variant(pkg, "A")
    b = _stage_variant(pkg, "B")

    agg = package_variants.write_root_manifest(pkg, ["A", "B"], CORPUS, NOW)

    dest = pkg / "MANIFEST.json"
    assert dest.is_file(), "aggregate must be written at the package root"
    assert agg == _read(pkg)
    # Top-level keys in the Brick aggregate's exact order (one shape for reviewers).
    assert list(agg) == ["schema", "generated_utc", "input_corpus", "rendering_spec_sha256",
                         "SIMULATED", "simulation_warning", "known_defect", "variants"]
    assert agg["schema"] == "access2026-variants/1"
    assert agg["generated_utc"] == NOW
    assert agg["input_corpus"] == CORPUS
    assert agg["rendering_spec_sha256"] == SPEC_SHA
    assert agg["SIMULATED"] is True
    assert agg["simulation_warning"] == "shared warning"  # equal warnings collapse
    # IOF per-variant manifests carry no known_defect: the key stays, empty.
    assert agg["known_defect"] == ""

    assert [e["id"] for e in agg["variants"]] == ["A", "B"]
    entry_a = agg["variants"][0]
    assert list(entry_a) == ["id", "rendered_view_path", "graph_path", "graph_sha256",
                             "rendered_view_sha256", "rendered_view_lines", "description",
                             "comparison_role", "model", "SIMULATED"]
    # Loader resolves entry paths relative to the aggregate's dir -> dir-prefixed.
    assert entry_a["rendered_view_path"] == "A/rendered_view.txt"
    assert entry_a["graph_path"] == "A/graph_A.ttl"
    assert entry_a["graph_sha256"] == a["graph_sha256"]
    assert entry_a["rendered_view_sha256"] == a["rendered_view_sha256"]
    assert entry_a["rendered_view_lines"] == a["rendered_view_lines"]
    assert entry_a["description"] == a["description"]
    assert entry_a["comparison_role"] == a["comparison_role"]
    assert entry_a["model"] == a["model"]
    assert entry_a["SIMULATED"] is True
    assert agg["variants"][1]["graph_path"] == "B/graph_B.ttl"
    assert agg["variants"][1]["comparison_role"] == b["comparison_role"]


def test_simulated_flag_is_the_and_over_variants(tmp_path):
    pkg = tmp_path / "variants_fake"
    _stage_variant(pkg, "A")
    _stage_variant(pkg, "B", simulated=False)
    agg = package_variants.write_root_manifest(pkg, ["A", "B"], CORPUS, NOW)
    assert agg["SIMULATED"] is False
    assert [e["SIMULATED"] for e in agg["variants"]] == [True, False]


def test_unequal_simulation_warnings_are_joined(tmp_path):
    pkg = tmp_path / "variants_fake"
    _stage_variant(pkg, "A", warning="warn A")
    _stage_variant(pkg, "B", warning="warn B")
    agg = package_variants.write_root_manifest(pkg, ["A", "B"], CORPUS, NOW)
    assert agg["simulation_warning"] == "warn A | warn B"


def test_known_defect_is_carried_when_present(tmp_path):
    pkg = tmp_path / "variants_fake"
    _stage_variant(pkg, "A", known_defect="A was a stub (see BLOCKED.md)")
    _stage_variant(pkg, "B", known_defect="A was a stub (see BLOCKED.md)")
    agg = package_variants.write_root_manifest(pkg, ["A", "B"], CORPUS, NOW)
    assert agg["known_defect"] == "A was a stub (see BLOCKED.md)"


def test_mismatched_rendering_spec_sha_fails_loudly(tmp_path):
    pkg = tmp_path / "variants_fake"
    _stage_variant(pkg, "A")
    _stage_variant(pkg, "B", spec="0" * 64)
    with pytest.raises(SystemExit, match="rendering_spec_sha256"):
        package_variants.write_root_manifest(pkg, ["A", "B"], CORPUS, NOW)
    assert not (pkg / "MANIFEST.json").exists(), "a refused derivation must not leave a file"


def test_derived_aggregate_loads_under_the_registered_loader(tmp_path):
    """Brick-shape proof: the runner's registered six-variant loader accepts a derived
    aggregate (paths, digests, six ids) -- so the ad hoc Brick aggregate's role is
    reproduced by code and a future Brick re-package stays loadable."""
    pkg = tmp_path / "variants_fake"
    ids = ["A", "B", "C", "D", "E", "F"]
    for vid in ids:
        _stage_variant(pkg, vid)
    package_variants.write_root_manifest(pkg, ids, CORPUS, NOW)

    variants = run_holdout.load_variant_manifest(pkg / "MANIFEST.json", require_six=True)
    assert [v.variant_id for v in variants] == ids
    assert all(v.view.strip() for v in variants)
