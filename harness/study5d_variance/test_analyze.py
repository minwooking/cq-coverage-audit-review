"""Synthetic-data tests for analyze.py (no real data).  Run: python3 test_analyze.py"""
import numpy as np
import analyze as A


def synth(Q=120, J=6, delta=None, tau_j=0.0, seed=0):
    rng = np.random.default_rng(seed)
    q = rng.normal(0, 1.0, (Q, 1, 1))
    qv = rng.normal(0, 0.3, (Q, 2, 1))
    qj = rng.normal(0, 0.4, (Q, 1, J))
    e = rng.normal(0, 0.2, (Q, 2, J))
    jo = rng.normal(0, 0.5, J)
    inter = np.zeros((2, J))
    inter[1] = rng.normal(0, tau_j, J) if tau_j else 0
    return q + qv + qj + e + jo[None, None, :] + inter[None] + np.array([0, 0.3])[None, :, None]


def test_null_no_interaction():
    Y = synth(tau_j=0.0)
    c = A.components(Y)
    assert c["interaction_share"] < 0.02, c["interaction_share"]
    assert A.boot_test(Y, B=300)["p"] > 0.05


def test_strong_interaction_detected():
    Y = synth(tau_j=0.8)
    c = A.components(Y)
    assert c["interaction_share"] > 0.05
    assert A.boot_test(Y, B=300)["p"] < 0.05
    assert A.perm_test(Y, B=200)["p"] < 0.05
    assert A.reading(A.boot_test(Y, B=300)["p"], c["interaction_share"]).startswith("judge-dependent")


def test_components_recover_truth():
    Y = synth(Q=2000, J=8, tau_j=0.0, seed=3)
    c = A.components(Y)["components"]
    assert abs(c["question"] - 1.0) < 0.15 and abs(c["question_x_variant"] - 0.09) < 0.03 and abs(c["question_x_judge"] - 0.16) < 0.04, c


def test_qwk_and_icc():
    x = [0, 1, 2, 3, 3, 2]
    assert abs(A.qwk(x, x) - 1.0) < 1e-12
    assert A.qwk([0, 0, 3, 3], [3, 3, 0, 0]) < 0
    M = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2], [3, 3, 3]], float)
    assert abs(A.icc2_1(M) - 1.0) < 1e-9


def test_contrast_block_and_median_low():
    Y = synth(tau_j=0.0)
    b = A.contrast_block(Y, [f"j{i}" for i in range(Y.shape[2])], B=200)
    assert abs(b["between_judge_sd"]["mean_delta"] - 0.3) < 0.1
    assert A.median_low([3, 0, 1]) == 1 and A.median_low([0, 1]) == 0


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
