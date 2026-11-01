"""Synthetic test of s2_preserved_analysis (no model call, no human label)."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_preserved_analysis as P  # noqa: E402
import analyze as A  # noqa: E402


def test_counts(tmp_path=None):
    d = Path(tempfile.mkdtemp())
    man = json.loads((Path(__file__).resolve().parent / "manifests" / "preserved.json").read_text())
    ids = [r["cell_id"] for r in man["rows"]]
    for m, pat in (("glm", lambda i: 25 if i < 4 else 12), ("gptoss", lambda i: 24 if i < 3 else 0)):
        with (d / f"{m}_preserved.jsonl").open("w") as fh:
            for i, c in enumerate(ids):
                ones = pat(i)
                for k, (p, s) in enumerate(A.SLOTS):
                    fh.write(json.dumps({"cell_id": c, "persona": p, "seed": s, "status": "ok", "S_final": 1 if k < ones else 0, "R_raw": 2}) + "\n")
    res = P.run(d, Path(__file__).resolve().parent / "manifests" / "preserved.json")
    g = res["per_model"]["glm"]
    assert res["per_model"]["glm"]["a_majority_S1"] == 4      # 12 of 25 -> majority 0 for i>=4
    assert res["per_model"]["gptoss"]["a_majority_S1"] == 3
    assert res["per_model"]["gptoss"]["b_consistent"] == 12   # 0/25 agree (all S=0) is consistent too
    assert res["both_models"]["c_consistent_and_S1"] == 3


if __name__ == "__main__":
    test_counts(); print("ok")
