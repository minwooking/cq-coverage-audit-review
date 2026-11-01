import numpy as np
import analyze as an


def test_mde_reproduces_paper():
    assert abs(an.mde(1.155, 23) - 0.675) < 0.002


def test_cell_scores_mean_and_invalid():
    recs = [{"cell_id": "primary:A:X", "J": 1, "valid": True}, {"cell_id": "primary:A:X", "J": 2, "valid": True},
            {"cell_id": "primary:A:X", "J": 3, "valid": False}]
    assert an.cell_scores(recs)["primary:A:X"] == 1.5


def test_contrast_synthetic():
    ids = [f"Q{i}" for i in range(20)]
    sc = {}
    for i, c in enumerate(ids):
        sc[f"primary:A:{c}"] = 1.0
        sc[f"primary:B:{c}"] = 2.0 if i < 18 else 1.0
    r = an.contrast(sc, set(ids))
    assert r["n_clusters"] == 20 and abs(r["delta"] - 0.9) < 1e-9
    assert r["decision"] == "resolved" and r["sign_test"]["n_pos"] == 18
