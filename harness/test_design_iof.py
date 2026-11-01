"""IOF registered analysis design (PREREG.md addendum 15 §15.7-2) — synthetic tests only.

Every cell and label here is SYNTHETIC test data (never research data, never a real
label). The IOF design facts themselves are NOT hardcoded from prose: they must be
derived by the code from the COMMITTED preflight manifest
``real_run_iof/MANIFEST.json`` (216 checked / 178 excluded / 38 eligible, variants
A-F, seed 20260913); these tests pin that derivation and the CLI route that consumes
it. ``analyze_holdout.py`` is pinned byte-for-byte (§15.7-2: "analyze_holdout.py
자체는 바이트 단위로 바뀌지 않는다"): the SHA-256 literal below is the commit-time
value of the registered analyzer and fails the suite the moment the file changes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import analyze_domain  # noqa: E402
import analyze_holdout as ah  # noqa: E402
import design_iof  # noqa: E402
import domains  # noqa: E402

ACCESS = HERE.parent
MANIFEST_PATH = ACCESS / "harness/real_run_iof/MANIFEST.json"

# analyze_holdout.py is referenced by SHA-256 from committed artifacts and must not
# change by a single byte (this task's whole route exists so that it does not have
# to). If this pin breaks, the change belongs in a new module, never in analyze_holdout.
ANALYZE_HOLDOUT_SHA256 = ("3278d71c70829889838aa8f61c4f5b0217b9ef3e921976a8ea5fc0c0fd122e10")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- the pinned analyzer ------------------------------------------------------
def test_analyze_holdout_py_is_byte_pinned():
    assert _sha((HERE / "analyze_holdout.py").read_bytes()) == ANALYZE_HOLDOUT_SHA256


def test_analyze_holdout_pin_agrees_with_committed_artifact():
    # the pre-existing pin in committed output stays authoritative and agrees
    pinned = json.loads(
        (ACCESS / "harness/real_run/results_human_pass/exploratory_reanalysis.json").read_text())
    assert pinned["code"]["analyze_holdout.py"] == ANALYZE_HOLDOUT_SHA256


# --- design derivation from the committed manifest ----------------------------
def test_iof_design_derives_from_the_committed_manifest():
    d = design_iof.load_iof_design()
    assert d.manifest_path == MANIFEST_PATH
    assert d.manifest_sha256 == _sha(MANIFEST_PATH.read_bytes())
    assert d.seed == ah.REGISTERED_SEED == 20260913
    assert d.variant_ids == ("A", "B", "C", "D", "E", "F")
    assert len(d.cq_ids) == 36 and d.cq_ids == tuple(sorted(d.cq_ids))
    assert d.checked_primary_cells == 216
    assert d.excluded_primary_cells == 178
    assert len(d.eligible_pairs) == d.eligible_primary_cells == 38
    assert {v: sum(1 for vv, _ in d.eligible_pairs if vv == v) for v in d.variant_ids} \
        == {"A": 8, "B": 6, "C": 6, "D": 6, "E": 6, "F": 6}
    assert d.exclusion_rule.startswith("grounding_anchor_absent_from_view")
    # §15.2/15.3/15.4 arithmetic: IOF clusters and A->B pairs, and the pooled totals
    assert d.n_clusters == 8          # IOF scored CQ count (N_IOF)
    assert d.m_ab_pairs == 6          # CQs scored by BOTH A and B
    assert d.brick_n_clusters == 33 and d.brick_m_ab_pairs == 23
    assert d.pooled_n_clusters == 33 + 8 == 41
    assert d.pooled_ab_pairs == 23 + 6 == 29
    assert d.ablated_control_cells == 24 and d.preserved_control_cells == 0
    assert d.preserved_controls_omitted_reason.startswith("no frozen paraphrase file")


def test_iof_design_eligible_grid_is_the_complement_of_the_manifest_exclusions():
    d = design_iof.load_iof_design()
    from_manifest = {(e["variant"], e["cq_id"]) for e in
                     json.loads(MANIFEST_PATH.read_text())["eligibility_exclusions"]}
    assert d.excluded_pairs == frozenset(from_manifest)
    grid = {(v, q) for v in d.variant_ids for q in d.cq_ids}
    assert d.eligible_pairs | d.excluded_pairs == grid
    assert not (d.eligible_pairs & d.excluded_pairs)


@pytest.mark.parametrize("tamper", ["counts", "bank_sha", "exclusion_variant", "seed", "grid"])
def test_iof_design_refuses_a_manifest_that_does_not_cross_validate(tmp_path, tamper):
    manifest = json.loads(MANIFEST_PATH.read_text())
    if tamper == "counts":
        manifest["eligibility_counts"]["eligible_primary_cells"] = 39
    elif tamper == "bank_sha":
        manifest["bank_sha256"] = "0" * 64
    elif tamper == "exclusion_variant":
        manifest["eligibility_exclusions"][0]["variant"] = "Z"
    elif tamper == "seed":
        manifest["seed"] = 20260914
    elif tamper == "grid":
        manifest["variant_ids"] = ["A", "B", "C", "D", "E"]
    bad = tmp_path / "MANIFEST.json"
    bad.write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match="REFUSING TO RUN"):
        design_iof.load_iof_design(manifest_path=bad)


def test_iof_design_requires_a_declared_manifest_seam(tmp_path):
    # a domain without [analysis].preflight_manifest has no registered design
    lines = (domains.DOMAINS_DIR / "iof.toml").read_text().splitlines(keepends=True)
    out, in_analysis = [], False
    for line in lines:
        if line.strip().startswith("["):
            in_analysis = line.strip() == "[analysis]"
        if in_analysis:
            continue
        out.append(line)
    (tmp_path / "iof.toml").write_text("".join(out))
    cfg = domains.load_domain("iof", tmp_path)
    assert cfg.preflight_manifest is None
    with pytest.raises(SystemExit, match="REFUSING TO RUN"):
        design_iof.load_iof_design(domain=cfg)


# --- the synthetic IOF run surface (fixtures are synthetic data, never labels) --
def _synthetic_iof_run(design: design_iof.IofDesign, tmp_path: Path, *,
                       events: int = 2, drop_one: bool = False,
                       add_excluded: bool = False) -> tuple[Path, Path]:
    """38 (or 37/39) primary cells + 24 ablated controls + a human-sourced label CSV,
    built from the manifest-derived design. All J/A values are synthetic placeholders."""
    cells_path, labels_path = tmp_path / "cells.jsonl", tmp_path / "labels.csv"
    pairs = sorted(design.eligible_pairs)
    if drop_one:
        pairs = pairs[:-1]
    if add_excluded:
        pairs = pairs + [("A", design.cq_ids[0])]  # an excluded pairing must be refused
    rows, labels = [], []
    for i, (v, q) in enumerate(pairs):
        j, a = (2, 0) if i < events else (1, 1)
        cell_id = f"synth-{v}-{q}"
        rows.append({"cell_id": cell_id, "variant": v, "cq_id": q, "cluster_id": q,
                     "J": j, "judge_response": {"score": j}, "judge_response_parsed": True,
                     "cell_kind": "primary"})
        labels.append({"cell_id": cell_id, "A": a, "rater_L1": j, "label_source": "human"})
    ctl_q = sorted({q for _, q in design.eligible_pairs})[0]
    for k in range(24):
        rows.append({"cell_id": f"synth-ctl-{k:02d}", "variant": "B", "cq_id": ctl_q,
                     "cluster_id": ctl_q, "J": 1, "judge_response": {"score": 1},
                     "judge_response_parsed": True, "cell_kind": "ablated_control"})
    cells_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    with labels_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["cell_id", "A", "rater_L1", "label_source"])
        writer.writeheader()
        writer.writerows(labels)
    return cells_path, labels_path


def _run_iof_cli(tmp_path: Path, cells: Path, labels: Path, *extra: str) -> dict:
    out = tmp_path / "iof_results.json"
    original = ah.check_registered_design
    rc = analyze_domain.main(["--domain", "iof", str(cells), "--labels", str(labels),
                              "--label-source", "human", "--seed", "20260913",
                              "--out", str(out), *extra])
    assert rc == 0
    assert ah.check_registered_design is original  # the route never leaks the patch
    return json.loads(out.read_text())


def test_cli_domain_iof_accepts_manifest_conforming_synthetic_cells(tmp_path):
    d = design_iof.load_iof_design()
    cells, labels = _synthetic_iof_run(d, tmp_path)
    res = _run_iof_cli(tmp_path, cells, labels)
    design = res["analysis_population"]["registered_design"]
    assert design is not None and design["conforms"] is True
    assert design["expected_primary_cells"] == 38
    assert res["analysis_population"]["n_primary_cells"] == 38
    assert res["analysis_population"]["n_primary_clusters"] == 8
    assert design["iof_design"] == {
        "manifest_sha256": d.manifest_sha256,
        "eligibility_rule": d.exclusion_rule,
        "n_iof_clusters": 8, "m_ab_pairs": 6,
        "pooled_n_clusters": 41, "pooled_ab_pairs": 29,
        "ablated_control_cells_planned": 24, "preserved_control_cells_planned": 0,
    }
    assert "A→B" in res["contrasts"] or "A->B" in res["contrasts"]
    # aggregates-only policy: no IOF CQ id may appear in the main results
    text = out_text = json.dumps(res)
    assert not any(f"CQI{i:02d}" in text for i in range(1, 37))


def test_cli_domain_iof_refuses_cells_outside_the_manifest_design(tmp_path):
    d = design_iof.load_iof_design()
    # an excluded (variant, cq) pair present in the cells: refuse with an IOF-worded error
    cells, labels = _synthetic_iof_run(d, tmp_path, add_excluded=True)
    with pytest.raises(SystemExit) as exc:
        _run_iof_cli(tmp_path, cells, labels)
    assert "manifest" in str(exc.value).lower()
    # --allow-partial downgrades the refusal to a recorded non-conformance
    res = _run_iof_cli(tmp_path, cells, labels, "--allow-partial")
    assert res["analysis_population"]["registered_design"]["conforms"] is False
    # a cell MISSING from the design is refused the same way
    cells2, labels2 = _synthetic_iof_run(d, tmp_path, drop_one=True)
    with pytest.raises(SystemExit) as exc:
        _run_iof_cli(tmp_path, cells2, labels2)
    assert "manifest" in str(exc.value).lower()


def test_cli_domain_iof_seed_mismatch_names_the_manifest(tmp_path):
    d = design_iof.load_iof_design()
    cells, labels = _synthetic_iof_run(d, tmp_path)
    with pytest.raises(SystemExit) as exc:
        analyze_domain.main(["--domain", "iof", str(cells), "--labels", str(labels),
                             "--label-source", "human", "--seed", "20260914",
                             "--out", str(tmp_path / "off.json")])
    msg = str(exc.value)
    assert "seed" in msg and "MANIFEST" in msg


def test_cli_domain_brick_still_delegates_byte_identically(tmp_path):
    # brick keeps the plain delegation: analyze_holdout's OWN refusal text appears
    with pytest.raises(SystemExit) as exc:
        analyze_domain.main(["--domain", "brick", str(tmp_path / "missing.jsonl"),
                             "--seed", "20260913"])
    assert "no cell file" in str(exc.value)
    assert ah.check_registered_design.__doc__ is not None  # not the IOF closure


def test_third_domain_still_refuses_without_a_design(tmp_path, monkeypatch):
    (tmp_path / "zeta.toml").write_text((domains.DOMAINS_DIR / "brick.toml").read_text()
                                        .replace('name = "brick"', 'name = "zeta"'))
    monkeypatch.setattr(analyze_domain, "known_domains", lambda: ["brick", "iof", "zeta"])
    monkeypatch.setattr(analyze_domain, "load_domain",
                        lambda name: domains.load_domain(name, tmp_path))
    with pytest.raises(SystemExit, match="no registered analysis design"):
        analyze_domain.main(["--domain", "zeta", str(tmp_path / "x.jsonl"), "--seed", "1"])
