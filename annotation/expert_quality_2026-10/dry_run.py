#!/usr/bin/env python3
"""Dry run with 3 SYNTHETIC raters: packets -> filled sheets -> analysis. Writes only to a temp dir.

The synthetic ratings are random numbers (latent = 0.6 * standardized coverage + artifact effect + rater
noise). They carry no information about real expert opinion; the run only tests the pipeline.
"""
import csv
import json
import random
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_expert_quality as A  # noqa: E402


def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("NOTE: all ratings below are SYNTHETIC random numbers; this run tests the pipeline only.")
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        out, keys = tmp / "packets", tmp / "keys"
        print("== 1. build packets (3 raters, holdout + dev sets, E/F merged)")
        r = subprocess.run([sys.executable, str(HERE / "build_expert_quality_packets.py"), "--raters", "R1", "R2", "R3",
                            "--master-seed", "DRYRUN-NOT-A-REAL-SEED", "--out-dir", str(out), "--keys-dir", str(keys)],
                           capture_output=True, text=True)
        print(r.stdout.strip(), r.stderr.strip()[-500:])
        if r.returncode:
            return r.returncode
        print(f"   packet build took {time.time()-t0:.0f}s")
        for rid in ("R1", "R2", "R3"):
            files = sorted(p.relative_to(out / rid) for p in (out / rid).rglob("*") if p.is_file())
            md = [p for p in files if str(p).endswith(".md") and "materials" in str(p)]
            sz = [(out / rid / p).stat().st_size for p in md]
            print(f"   {rid}: {len(files)} files, dossiers {len(md)} (size KB: {[s//1024 for s in sz]}), sheet cols ok")
        print("   first lines of one dossier (R1, first material):")
        first = sorted((out / "R1" / "materials").glob("*.md"))[0]
        print("   | " + "\n   | ".join(first.read_text().splitlines()[:14]))
        print("== 2. synthetic raters fill sheets")
        cov = A.load_coverage(HERE / "coverage_reference.csv")
        rng = random.Random(42)
        eff = {}
        filled = {}
        for rid in ("R1", "R2", "R3"):
            key = {k["artifact_id"]: k for k in A.read_csv(keys / f"key_{rid}.csv")}
            sheet = A.read_csv(out / rid / f"rating_sheet_{rid}.csv")
            per_batch = {}
            for row in sheet:
                k = key[row["artifact_id"]]
                members = k["variant"].split("+")
                c = sum(cov[(k["set"], m)]["J_pct"] for m in members) / len(members)
                eff.setdefault((k["set"], k["variant"]), rng.gauss(0, 0.5))
                lat = 0.06 * (c - 70) + eff[(k["set"], k["variant"])] + rng.gauss(0, 0.45)
                row["_lat"] = lat
                per_batch.setdefault(row["batch"], []).append(row)
                for q in A.CRITERIA:
                    row[q] = str(max(1, min(5, round(3 + lat + rng.gauss(0, 0.6)))))
                row["confidence_1to5"] = str(rng.randint(3, 5))
                row["minutes_spent"] = str(rng.randint(18, 32))
            for rows in per_batch.values():
                for i, row in enumerate(sorted(rows, key=lambda r: -r["_lat"]), 1):
                    row["overall_rank"] = str(i)
            for row in sheet:
                row.pop("_lat")
            p = tmp / f"filled_{rid}.csv"
            with p.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(sheet[0].keys()))
                w.writeheader()
                w.writerows(sheet)
            filled[rid] = str(p)
        print("== 3. analysis")
        res = A.analyze(A.load_ratings(keys, filled), A.load_coverage(HERE / "coverage_reference.csv"),
                        n_boot=2000, n_mc=20000)
        print(A.summarize(res))
        print("== 4. power (n=5/6/10/12, observed J pattern)")
        subprocess.run([sys.executable, str(HERE / "analyze_expert_quality.py"), "power", "--coverage",
                        str(HERE / "coverage_reference.csv"), "--set", "holdout", "--metric", "J_pct", "--n-sim", "1500"])
        print(f"== done in {time.time()-t0:.0f}s (temp dir removed; no keys/packets left behind)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
