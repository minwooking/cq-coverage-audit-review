#!/usr/bin/env python3
"""Addendum 27 step 2c: grounding check of the natural corpus against the frozen bank (PLAN.md 27.4).

AI-generated; review before reuse.  Offline, no model, no network.

  grounding_check.py auto       -> grounding_auto.json + GROUNDING_PASSAGES.md   (automated tiers L0/L1/L2
                                    and the three top passages per question for the analyst read)
  grounding_check.py finalize   -> grounding_check.json + GROUNDING.md           (merges analyst_read.json,
                                    applies the stop rule, fixes the eligible sets)

The bank's `grounding` and `expected_answer` columns are read here only (corpus-side measurement).  They
are never sent to the extractor, to subgraph extraction or to the judge.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parents[1]
HARNESS = ACCESS / "harness"
sys.path.insert(0, str(HARNESS))

import run_holdout as rh  # noqa: E402  (imported for _grounding_anchors only; no network at import)

BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"
CORPUS = HERE / "corpus" / "natural_corpus.json"
STOP = set("""a an the of and or to in on for with by is are was were be been being as at from that this these those it its
into than then there their them they which who whom what when where how why does do did has have had not no can could should
would will shall may might must also such each any all both either neither one two more most other some only own same so too
very per via about above after again against before below between during over under until while within without used use using
uses based given which whose if else but however""".split())


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def forms_of(local: str) -> list[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", local).replace("_", " ")
    out = []
    for f in (local.lower(), spaced.lower()):
        f = re.sub(r"\s+", " ", f).strip()
        if f and f not in out:
            out.append(f)
    return out


def form_regex(form: str) -> re.Pattern:
    body = r"[\s_-]+".join(re.escape(t) for t in form.split(" "))
    return re.compile(r"(?<![a-z0-9])" + body + r"(?:s|es)?(?![a-z0-9])")


def present(text_lc: str, local: str) -> bool:
    return any(form_regex(f).search(text_lc) for f in forms_of(local))


def local_anchors(grounding: str) -> list[str]:
    out: list[str] = []
    for a in rh._grounding_anchors(grounding):
        loc = a.split(":", 1)[1] if ":" in a else a
        if loc and loc not in out and loc not in {"sh", "path"}:
            out.append(loc)
    return out


def content_terms(text: str, exclude_forms: set[str]) -> list[str]:
    toks = re.findall(r"[A-Za-z][A-Za-z_]{3,}", text)
    seen: list[str] = []
    for t in toks:
        for piece in re.split(r"_", re.sub(r"(?<=[a-z])(?=[A-Z])", "_", t)):
            w = piece.lower()
            if len(w) < 4 or w in STOP or w in exclude_forms:
                continue
            w = w[:-1] if w.endswith("s") and len(w) > 4 else w
            if w not in seen:
                seen.append(w)
    return seen


def load_sections() -> list[dict]:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    secs = []
    for ci, ch in enumerate(data["chunks"]):
        src = " / ".join(ch["toc_hierarchy"])
        for si, adv in enumerate(ch["child_chunks"]["advanced_chunking_result"]):
            chunks = [a["content"]["text"] for a in adv["atomic_chunks"]]
            secs.append({"sid": f"c{ci}.s{si}", "source": src, "title": adv["title"], "chunks": chunks,
                         "text_lc": (adv["title"] + "\n" + "\n".join(chunks)).lower()})
    return secs


def auto() -> int:
    rows = list(csv.DictReader(BANK.open(encoding="utf-8", newline="")))
    assert hashlib.sha256(BANK.read_bytes()).hexdigest() == rh.FROZEN_BANK_SHA256, "bank digest mismatch"
    secs = load_sections()
    corpus_lc = "\n".join(s["text_lc"] for s in secs)
    results = []
    for row in rows:
        anchors = local_anchors(row["grounding"])
        exclude = {w for a in anchors for f in forms_of(a) for w in f.split(" ")}
        l0 = all(present(corpus_lc, a) for a in anchors)
        sec_hits = [s for s in secs if all(present(s["text_lc"], a) for a in anchors)]
        l1 = bool(sec_hits)
        ans_terms = content_terms(row["expected_answer"], exclude)
        best_frac, best_sid = 0.0, None
        for s in sec_hits:
            hit = sum(1 for t in ans_terms if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?:s|es)?(?![a-z0-9])", s["text_lc"]))
            frac = hit / len(ans_terms) if ans_terms else 0.0
            if frac > best_frac:
                best_frac, best_sid = frac, s["sid"]
        l2 = best_frac >= 0.5
        # passage ranking: question + anchors only (never the expected answer)
        q_terms = content_terms(row["question"], set())
        scored = []
        for s in secs:
            for ci_, text in enumerate(s["chunks"]):
                t = (s["title"] + " " + text).lower()
                score = 3 * sum(1 for a in anchors if present(t, a)) + sum(
                    1 for w in q_terms if re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?:s|es)?(?![a-z0-9])", t))
                if score:
                    scored.append((score, s["sid"], ci_, s["source"], s["title"], text))
        scored.sort(key=lambda x: (-x[0], x[1], x[2]))
        top = [{"score": sc, "sid": sid, "chunk_index": ci_, "source": src, "section": ttl, "text": txt}
               for sc, sid, ci_, src, ttl, txt in scored[:3]]
        results.append({"cq_id": row["cq_id"], "category": row["category"], "question": row["question"],
                        "grounding": row["grounding"], "anchors": anchors, "L0": l0, "L1": l1,
                        "n_sections_L1": len(sec_hits), "L2": l2, "best_section_answer_term_fraction": round(best_frac, 3),
                        "best_section": best_sid, "answer_terms_n": len(ans_terms), "top_passages": top})
    out = {"corpus_sha256": sha256_file(CORPUS), "bank_sha256": rh.FROZEN_BANK_SHA256, "n_sections": len(secs),
           "n_atomic_chunks": sum(len(s["chunks"]) for s in secs), "questions": results,
           "counts": {"L0": sum(r["L0"] for r in results), "L1": sum(r["L1"] for r in results),
                      "L2": sum(r["L2"] for r in results), "n": len(results)}}
    (HERE / "grounding_auto.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["# Passages for the analyst read (auto-ranked by question + anchor terms only)", ""]
    bank = {r["cq_id"]: r for r in rows}
    for r in results:
        b = bank[r["cq_id"]]
        md += [f"## {r['cq_id']} [{r['category']}] {r['question']}", "",
               f"- grounding: `{r['grounding']}`; anchors {r['anchors']}; L0={r['L0']} L1={r['L1']} (sections {r['n_sections_L1']}) "
               f"L2={r['L2']} (best answer-term fraction {r['best_section_answer_term_fraction']})",
               f"- expected_answer (bank): {b['expected_answer']}", ""]
        for i, p in enumerate(r["top_passages"], 1):
            md += [f"**P{i}** (score {p['score']}; {p['source']} :: {p['section']}; {p['sid']}#{p['chunk_index']})", "",
                   "> " + p["text"].replace("\n", "\n> "), ""]
        if not r["top_passages"]:
            md += ["_no passage contains any anchor or question term_", ""]
    (HERE / "GROUNDING_PASSAGES.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps(out["counts"]))
    return 0


def finalize() -> int:
    auto_p = HERE / "grounding_auto.json"
    read_p = HERE / "analyst_read.json"
    auto_d = json.loads(auto_p.read_text(encoding="utf-8"))
    read = json.loads(read_p.read_text(encoding="utf-8"))
    by_read = {r["cq_id"]: r for r in read["ratings"]}
    merged = []
    for q in auto_d["questions"]:
        r = by_read[q["cq_id"]]
        assert r["rating"] in {"full", "partial", "none"}, r
        merged.append({k: v for k, v in q.items() if k != "top_passages"} |
                      {"top_passage_ids": [f"{p['sid']}#{p['chunk_index']}" for p in q["top_passages"]],
                       "analyst_rating": r["rating"], "analyst_span": r["span"], "analyst_note": r.get("note", "")})
    n = len(merged)
    cnt = Counter(m["analyst_rating"] for m in merged)
    by_cat: dict[str, Counter] = {}
    for m in merged:
        by_cat.setdefault(m["category"], Counter())[m["analyst_rating"]] += 1
    answerable = cnt["full"] + cnt["partial"]
    stop = answerable / n < 0.20
    s_elig = [m["cq_id"] for m in merged if m["analyst_rating"] in {"full", "partial"}]
    s_elig_l1 = [m["cq_id"] for m in merged if m["L1"]]
    out = {"corpus_sha256": auto_d["corpus_sha256"], "bank_sha256": auto_d["bank_sha256"],
           "analyst_read_not_blind": True,
           "automated_counts": auto_d["counts"],
           "analyst_counts": {"full": cnt["full"], "partial": cnt["partial"], "none": cnt["none"], "n": n},
           "analyst_counts_by_category": {k: dict(v) for k, v in by_cat.items()},
           "answerable_full_plus_partial": answerable, "answerable_share": round(answerable / n, 4),
           "stop_rule": {"threshold_share": 0.20, "triggered": stop},
           "S_full": [m["cq_id"] for m in merged], "S_elig": s_elig, "S_elig_L1": s_elig_l1,
           "questions": merged}
    (HERE / "grounding_check.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["# Grounding check -- natural corpus vs frozen bank (addendum 27.4)", "",
          f"Corpus sha256 `{out['corpus_sha256']}`; bank sha256 `{out['bank_sha256']}`. The analyst read is NOT blind "
          "(the reader had the bank's expected answers).", "",
          f"- Automated: L0 (anchors anywhere) {auto_d['counts']['L0']}/{n}; L1 (anchors in one heading section) {auto_d['counts']['L1']}/{n}; "
          f"L2 (L1 + >=50% of answer terms in that section) {auto_d['counts']['L2']}/{n}.",
          f"- Analyst read: full {cnt['full']}, partial {cnt['partial']}, none {cnt['none']} (of {n}); answerable (full+partial) = {answerable}/{n} = {answerable / n:.1%}.",
          f"- Stop rule (answerable share < 20%): **{'TRIGGERED' if stop else 'not triggered'}**.", "",
          "## By category (analyst read)", "", "| category | full | partial | none |", "|---|---:|---:|---:|"]
    for k, v in by_cat.items():
        md.append(f"| {k} | {v['full']} | {v['partial']} | {v['none']} |")
    md += ["", "## Per question", "", "| cq | category | L0 | L1 | L2 | analyst | span or near miss |", "|---|---|:-:|:-:|:-:|---|---|"]
    for m in merged:
        span = (m["analyst_span"] or "").replace("|", "/").replace("\n", " ")
        md.append(f"| {m['cq_id']} | {m['category']} | {'y' if m['L0'] else 'n'} | {'y' if m['L1'] else 'n'} | "
                  f"{'y' if m['L2'] else 'n'} | {m['analyst_rating']} | {span[:200]} |")
    md += ["", f"S_elig ({len(s_elig)}): {', '.join(s_elig)}", "", f"S_elig_L1 ({len(s_elig_l1)}): {', '.join(s_elig_l1)}", ""]
    (HERE / "GROUNDING.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("automated_counts", "analyst_counts", "answerable_share", "stop_rule")}))
    print("grounding_check.json sha256", sha256_file(HERE / "grounding_check.json"))
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    raise SystemExit(auto() if cmd == "auto" else finalize() if cmd == "finalize" else
                     print(__doc__) or 2)
