import analyze_all as aa


def test_pool_clusters_paraphrase_with_source():
    a = {"CQB01": {"A": 1.0, "B": 2.0}}
    b = {"CQB01": {"A": 2.0, "B": 2.0}, "CQB02": {"A": 0.0, "B": 1.0}}
    p = aa.pool([a, b])
    assert set(p) == {"CQB01", "CQB02"} and p["CQB01"] == {"A": 1.5, "B": 2.0}


def test_to_bank_needs_both_variants():
    sc = {"para:A:Q1": 1.0, "para:B:Q1": 2.0, "para:A:Q2": 1.0}
    assert set(aa.to_bank(sc, "para", lambda v, q: True)) == {"Q1"}
