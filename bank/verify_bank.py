"""Verify that every CQ grounding in the bank resolves in the frozen snapshot.
Exit code is non-zero when any grounding term is missing, so this can gate a freeze.
"""
import csv
import re
import sys
from pathlib import Path

from rdflib import Graph

# Resolve relative to this script's own location (bank/ -> access2026/), never a
# hardcoded checkout path: the script must verify the bank sitting next to it, in
# whatever worktree/clone it is run from, or the freeze gate proves nothing.
BASE = Path(__file__).resolve().parent.parent
NS = {
    "brick": "https://brickschema.org/schema/Brick#",
    "rec": "https://w3id.org/rec#",
    "ref": "https://brickschema.org/schema/Brick/ref#",
}
TERM = re.compile(r"\b(brick|rec|ref):([A-Za-z0-9_]+)")


def main() -> int:
    # Optional CLI arg: bank CSV filename (relative to bank/), defaults to v1
    # for backward compatibility with existing callers/CI.
    bank_name = sys.argv[1] if len(sys.argv) > 1 else "cq_bank_brick_v1.csv"
    if Path(bank_name).is_absolute():
        print("ERROR: bank filename must be relative", file=sys.stderr)
        return 2
    bank_dir = (BASE / "bank").resolve()
    snapshot = BASE / "data" / "brick-v1.4.4.ttl"
    try:
        bank = (bank_dir / bank_name).resolve()
        bank.relative_to(bank_dir)
    except ValueError:
        print("ERROR: bank filename escapes", bank_dir, file=sys.stderr)
        return 2
    for path in (snapshot, bank):
        if not path.is_file():
            print("ERROR: required input not found:", path, file=sys.stderr)
            return 2
    print("base:", BASE)
    graph = Graph()
    graph.parse(snapshot, format="turtle")
    known = {str(s) for s in set(graph.subjects())} | {str(o) for o in set(graph.objects())} | {
        str(p) for p in set(graph.predicates())
    }
    with bank.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    missing = []
    checked = 0
    for row in rows:
        text = row["grounding"] + " " + row["expected_answer"]
        for prefix, local in TERM.findall(text):
            uri = NS[prefix] + local
            checked += 1
            if uri not in known:
                missing.append((row["cq_id"], prefix + ":" + local))
    print("rows:", len(rows), "| terms checked:", checked, "| missing:", len(missing))
    for cq_id, term in missing:
        print("  MISSING", cq_id, term)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
