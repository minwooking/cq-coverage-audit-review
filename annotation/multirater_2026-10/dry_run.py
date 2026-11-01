#!/usr/bin/env python3
"""Synthetic 3-rater dry run: build packets -> fake labels -> agreement. Writes only to a temp dir."""
import csv, random, subprocess, sys, tempfile
from pathlib import Path
here = Path(__file__).parent
blind = here.parent / "labeling_sheet_blind_2026-10-13.csv"
judge_src = here.parent / "labeling_sheet_key_2026-10-13.csv"
tmp = Path(tempfile.mkdtemp(prefix="mr_dry_"))
py = sys.executable
run = lambda *a: subprocess.run([py, *map(str, a)], check=True)
run(here/"build_multirater_packets.py", "--input", blind, "--raters", "R1", "R2", "R3",
    "--master-seed", "DRYRUN-NOT-REAL", "--out-dir", tmp/"packets", "--keys-dir", tmp/"keys", "--anonymize-views")
# truth from author-side key only to make synthetic labels correlated; raters' files get noise
J = {r["cell_id"]: int(r["J"]) for r in csv.DictReader(open(judge_src, newline="", encoding="utf-8"))}
(tmp/"judge.csv").write_text("cell_id,J\n" + "".join(f"{k},{v}\n" for k, v in J.items()))
filled = []
for i, rid in enumerate(["R1", "R2", "R3"]):
    rng = random.Random(100 + i)
    kmap = {r["opaque_id"]: r["cell_id"] for r in csv.DictReader(open(tmp/"keys"/f"key_{rid}.csv"))}
    src = tmp/"packets"/rid/f"sheet_{rid}.csv"
    rows = list(csv.DictReader(open(src, newline="", encoding="utf-8")))
    for r in rows:
        truth = 1 if J[kmap[r["cell_id"]]] >= 2 else 0
        s = truth if rng.random() > 0.15 else 1 - truth
        r["S_label"] = s
        r["R_score"] = max(0, min(3, J[kmap[r["cell_id"]]] + rng.choice([-1, 0, 0, 0, 1])))
    out = tmp/f"filled_{rid}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    filled.append(f"{rid}={out}")
run(here/"compute_multirater_agreement.py", "--keys-dir", tmp/"keys", "--filled", *filled,
    "--judge-key", tmp/"judge.csv", "--json-out", tmp/"agreement.json")
print("DRY RUN OK; temp dir (synthetic, safe to delete):", tmp)
