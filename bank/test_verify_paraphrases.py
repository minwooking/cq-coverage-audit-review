import csv
import importlib.util
from pathlib import Path


BANK = Path(__file__).parent
SPEC = importlib.util.spec_from_file_location("verify_paraphrases", BANK / "verify_paraphrases.py")
assert SPEC and SPEC.loader
verify_paraphrases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_paraphrases)

SOURCE = BANK / "cq_bank_brick_v1.csv"
PARAPHRASE = BANK / "cq_bank_brick_v1_paraphrases.csv"


def _copy_rows(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write(path, rows):
    fields = ["cq_id", "cluster_id", "paraphrase_text", "grounding", "author_note"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_normal_paraphrases_pass():
    assert verify_paraphrases.validate(SOURCE, PARAPHRASE) == []


def test_missing_row_is_detected(tmp_path):
    rows = _copy_rows(PARAPHRASE)[:-1]
    path = tmp_path / "missing.csv"
    _write(path, rows)
    errors = verify_paraphrases.validate(SOURCE, path)
    assert any("row count" in error or "missing paraphrase row" in error for error in errors)
    assert any("CQB36" in error for error in errors)


def test_grounding_mismatch_is_detected(tmp_path):
    rows = _copy_rows(PARAPHRASE)
    rows[0]["grounding"] = "rdfs:comment rec:Campus"
    path = tmp_path / "bad_grounding.csv"
    _write(path, rows)
    errors = verify_paraphrases.validate(SOURCE, path)
    assert any("CQB01" in error and "grounding mismatch" in error for error in errors)


def test_surface_overlap_is_detected(tmp_path):
    rows = _copy_rows(PARAPHRASE)
    rows[0]["paraphrase_text"] = "What is a brick:Sensor?"
    path = tmp_path / "too_similar.csv"
    _write(path, rows)
    errors = verify_paraphrases.validate(SOURCE, path)
    assert any("CQB01" in error and "Jaccard" in error for error in errors)


def test_identical_sentence_is_detected_even_at_custom_threshold(tmp_path):
    rows = _copy_rows(PARAPHRASE)
    rows[0]["paraphrase_text"] = "What is a brick:Sensor?"
    path = tmp_path / "identical.csv"
    _write(path, rows)
    errors = verify_paraphrases.validate(SOURCE, path, max_jaccard=1.0)
    assert any("CQB01" in error and "identical" in error for error in errors)
