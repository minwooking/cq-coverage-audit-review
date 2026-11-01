import sensitivity as se


def test_impute_floor_and_counts():
    partial = {"Q1": {"A": 2.0, "B": 3.0}, "Q2": {"A": 1.0}}
    out, c = se.impute(partial, {"Q1", "Q2", "Q3"}, {("B", "Q2")})
    assert out["Q2"] == {"A": 1.0, "B": 0.0} and out["Q3"] == {"A": 0.0, "B": 0.0}
    assert c["missing_A"] == 1 and c["missing_B"] == 2 and c["missing_both"] == 1
    assert c["missing_B_eligible_no_view"] == 1 and c["clusters_scored_in_main"] == 1
