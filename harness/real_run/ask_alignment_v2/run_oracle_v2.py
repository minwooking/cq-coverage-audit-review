#!/usr/bin/env python3
"""Addendum 16: ASK oracle with a registered predicate map (step 7), run after the freeze.

EXPLORATORY and POST HOC (PREREG_ADDENDUM_16_DRAFT.md, tag access2026-addendum16-freeze).
Steps 1-6 (term mapping, rewriting of Brick terms, not_evaluable rule) are imported unchanged from
``harness/real_run/ask_alignment/ask_alignment.py``. Step 7 rewrites predicates of the *query*
(never the graph) into SPARQL property-path alternatives from ``predicate_map.csv``.

Usage (from paper/access2026)::

    PYTHONPATH=<repo>/src <repo>/.venv/bin/python harness/real_run/ask_alignment_v2/run_oracle_v2.py

Outputs next to this file: ask_results_v2.json, mapping_v2.csv, comparison_v2.md.
Deterministic: no timestamps, sorted keys; the only randomness is the registered BCa seed.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                      # paper/access2026
sys.path.insert(0, str(HERE.parent / "ask_alignment"))
import ask_alignment as aa  # noqa: E402
from rdflib import Graph, URIRef  # noqa: E402

VARIANTS = aa.VARIANTS
BANK_CSV = "bank/cq_bank_brick_v1.csv"
QUERY_DIR = "bank/ask_queries_v2"
PRED_MAP = "harness/real_run/ask_alignment_v2/predicate_map.csv"
KEY_CSV = "annotation/labeling_sheet_key_2026-10-13.csv"
INDEP_CSV = "annotation/second_pass_2026-10-13/v3/labels_v3.csv"
V1_RESULTS = "harness/real_run/ask_alignment/ask_results.json"
V1_MAPPING = "harness/real_run/ask_alignment/mapping.csv"

# registered decision constants (addendum 16, 16.4)
NE_MAX = 0.10
KAPPA_MIN = 0.40
N_MIN_EVALUABLE = 20

# predicates whose absence from a variant graph is flagged (rdf:type is always present)
STRUCT_PREDICATES = {
    "rdfs:subClassOf": "http://www.w3.org/2000/01/rdf-schema#subClassOf",
    "rdfs:subPropertyOf": "http://www.w3.org/2000/01/rdf-schema#subPropertyOf",
    "rdfs:comment": "http://www.w3.org/2000/01/rdf-schema#comment",
    "rdfs:label": "http://www.w3.org/2000/01/rdf-schema#label",
    "owl:inverseOf": "http://www.w3.org/2002/07/owl#inverseOf",
    "owl:disjointWith": "http://www.w3.org/2002/07/owl#disjointWith",
    "skos:definition": "http://www.w3.org/2004/02/skos/core#definition",
    "sh:path": "http://www.w3.org/ns/shacl#path",
    "sh:class": "http://www.w3.org/ns/shacl#class",
}
IRI_TO_SHORT = {v: k for k, v in STRUCT_PREDICATES.items()}


# ---------------------------------------------------------------------------
# predicate map (step 7)
# ---------------------------------------------------------------------------
def load_predicate_map(root: Path = ROOT) -> list[dict]:
    with (root / PRED_MAP).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def active_rules(rows: list[dict]) -> dict[str, list[dict]]:
    """query predicate IRI -> active rules (status == 'active'), in file order."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["status"] == "active":
            out[r["query_predicate"]].append(r)
    return dict(out)


def _path_for(key: str, rules: list[dict]) -> str:
    parts = [f"<{key}>"]
    for r in rules:
        v = r["variant_predicate"]
        parts.append(f"<{v}>")
        if r["direction"] == "symmetric":
            parts.append(f"^<{v}>")
    return "(" + "|".join(parts) + ")"


def rewrite_predicates(query: str, rules: dict[str, list[dict]]) -> tuple[str, list[str]]:
    """Step 7. Replace every token that resolves to a rule's query predicate by a property-path
    alternative. Returns (query text, sorted rule_ids that fired). Queries only, never graphs."""
    prefixes, body = aa.split_query(query)
    fired: set[str] = set()

    def sub(m):
        if m.group("iri"):
            iri = m.group("iri")[1:-1]
        elif m.group("pname") and m.group("pfx") in prefixes:
            iri = prefixes[m.group("pfx")] + m.group("loc")
        else:
            return m.group(0)
        rs = rules.get(iri)
        if not rs:
            return m.group(0)
        fired.update(r["rule_id"] for r in rs)
        return _path_for(iri, rs)

    new_body = aa._TOKEN.sub(sub, body)
    decl = "".join(f"PREFIX {p}: <{ns}>\n" for p, ns in sorted(prefixes.items()))
    return decl + new_body.strip() + "\n", sorted(fired)


def query_predicate_iris(query: str) -> set[str]:
    prefixes, body = aa.split_query(query)
    out = set()
    for m in aa._TOKEN.finditer(body):
        if m.group("iri"):
            out.add(m.group("iri")[1:-1])
        elif m.group("pname") and m.group("pfx") in prefixes:
            out.add(prefixes[m.group("pfx")] + m.group("loc"))
    return out


def predicate_triples(graph: Graph, iri: str, rules: dict[str, list[dict]]) -> int:
    n = sum(1 for _ in graph.triples((None, URIRef(iri), None)))
    for r in rules.get(iri, []):
        n += sum(1 for _ in graph.triples((None, URIRef(r["variant_predicate"]), None)))
    return n


def absent_predicates(graph: Graph, query: str, rules: dict[str, list[dict]]) -> list[str]:
    used = query_predicate_iris(query) & set(IRI_TO_SHORT)
    return sorted(IRI_TO_SHORT[i] for i in used if predicate_triples(graph, i, rules) == 0)


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def load_cqs(root: Path) -> list[dict]:
    with (root / BANK_CSV).open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = []
    for r in rows:
        cls = {"yes": "deterministic", "partial": "expert"}[r["ask_expressible"]]
        out.append({"cq_id": r["cq_id"], "category": r["category"], "cluster_id": r["cluster_id"], "cls": cls,
                    "query_text": (root / QUERY_DIR / f"{r['cq_id']}.rq").read_text(encoding="utf-8")})
    return sorted(out, key=lambda r: r["cq_id"])


def load_labels(root: Path, primary: dict) -> dict[tuple[str, str], dict]:
    """(cq, variant) -> {J, s_ah, s_ind}; J and A cross-checked against the per-cell join."""
    key = {r["cell_id"]: r for r in csv.DictReader((root / KEY_CSV).open(newline="", encoding="utf-8"))}
    ind = {r["cell_id"]: r for r in csv.DictReader((root / INDEP_CSV).open(newline="", encoding="utf-8"))}
    out = {}
    for (cq, v), c in primary.items():
        cid = f"primary:{v}:{cq}"
        k, i = key[cid], ind[cid]
        if int(k["J"]) != c["J"]:
            raise SystemExit(f"J disagrees for {cid}")
        out[(cq, v)] = {"J": c["J"], "s_ah": int(k["S_AH"]), "s_ind": int(i["S_label"]), "a_perCell": c["A"]}
    return out


# ---------------------------------------------------------------------------
# statistics (registered helpers reused from ask_alignment / analyze_holdout)
# ---------------------------------------------------------------------------
def kappa_block(ah, rows: list[dict], left: str, right: str, with_ci: bool = True) -> dict:
    t = aa.table_2x2((r[left], r[right]) for r in rows)
    k = aa.cohen_kappa(t["ask_true__other_1"], t["ask_true__other_0"], t["ask_false__other_1"], t["ask_false__other_0"])
    out = {"table": t, **k}
    clusters = sorted({r["cluster_id"] for r in rows})
    discord = {r["cluster_id"] for r in rows if r[left] != r[right]}
    out["clusters"] = len(clusters)
    out["discordant_clusters"] = len(discord)
    if clusters:
        up = ah.clopper_pearson_upper(len(discord), len(clusters), 0.025)
        out["cp_one_sided_97_5_upper_discordant_cluster_share"] = up
        out["cp_one_sided_97_5_lower_concordant_cluster_share"] = 1.0 - up
    if with_ci and rows:
        out["bca_kappa"] = aa.bca(ah, rows, aa.kappa_stat(left, right))
    return out


def concordance(ah, rows: list[dict], with_ci: bool = True) -> dict:
    return {
        "n_cells": len(rows),
        "oracle_true_cells": sum(r["ask"] for r in rows),
        "oracle_vs_judge_J_ge_2": kappa_block(ah, rows, "ask", "j2", with_ci),
        "oracle_vs_S_AH": kappa_block(ah, rows, "ask", "s_ah", with_ci),
        "oracle_vs_S_independent": kappa_block(ah, rows, "ask", "s_ind", with_ci),
        "baseline_S_AH_vs_S_independent": kappa_block(ah, rows, "s_ah", "s_ind", False),
        "baseline_judge_J_ge_2_vs_S_AH": kappa_block(ah, rows, "j2", "s_ah", False),
        "shares": {"j2": sum(r["j2"] for r in rows) / len(rows) if rows else None,
                   "s_ah": sum(r["s_ah"] for r in rows) / len(rows) if rows else None,
                   "s_ind": sum(r["s_ind"] for r in rows) / len(rows) if rows else None},
    }


def decide(conc_bf: dict, ne_share: float, ne_n: int, runs: int) -> dict:
    t = conc_bf["oracle_vs_S_AH"]["table"]
    n_eval = conc_bf["n_cells"]
    nonconstant = conc_bf["oracle_true_cells"] > 0 and conc_bf["oracle_true_cells"] < n_eval
    k_ah = conc_bf["oracle_vs_S_AH"]["kappa"]
    k_ind = conc_bf["oracle_vs_S_independent"]["kappa"]
    c0 = bool(nonconstant)
    c1 = ne_share <= NE_MAX
    c2 = k_ah is not None and k_ah >= KAPPA_MIN
    c3 = k_ind is not None and k_ind >= KAPPA_MIN
    if n_eval < N_MIN_EVALUABLE:
        verdict = "not_decidable (fewer than 20 evaluable B-F primary cells)"
    elif c0 and c1 and c2 and c3:
        verdict = "functional"
    elif c0 and c2 and c3:
        verdict = "partially_functional"
    else:
        verdict = "not_functional"
    return {"universe": "deterministic 18 CQs x variants B-F",
            "thresholds": {"not_evaluable_max_share": NE_MAX, "kappa_min": KAPPA_MIN, "min_evaluable_primary_cells": N_MIN_EVALUABLE},
            "evaluable_primary_cells": n_eval, "C0_nonconstant": c0,
            "C1_not_evaluable_share": ne_share, "C1_not_evaluable_runs": f"{ne_n}/{runs}", "C1_pass": c1,
            "C2_kappa_oracle_S_AH": k_ah, "C2_pass": c2,
            "C3_kappa_oracle_S_independent": k_ind, "C3_pass": c3, "verdict": verdict}


# ---------------------------------------------------------------------------
# main pipeline
# ---------------------------------------------------------------------------
def build(root: Path = ROOT, with_ci: bool = True, ah=None):
    if ah is None:
        sys.path.insert(0, str(root / "harness"))
        import analyze_holdout as ah  # noqa: PLC0415
    if ah.BOOTSTRAP_RESAMPLES != aa.BOOTSTRAP_B or ah.REGISTERED_SEED != aa.BOOTSTRAP_SEED:
        raise SystemExit("analyze_holdout bootstrap constants differ from the registered B / seed")

    pmap_rows = load_predicate_map(root)
    rules = active_rules(pmap_rows)
    cqs = load_cqs(root)
    primary = aa.load_primary_cells(root)
    labels = load_labels(root, primary)

    inputs = {name: aa.sha256_file(root / rel) for name, rel in aa.INPUT_FILES.items() if name.startswith("variant_graph")
              or name in ("bank_csv", "brick_snapshot", "per_cell", "cells_jsonl", "analyze_holdout_py")}
    inputs.update({"predicate_map_csv": aa.sha256_file(root / PRED_MAP), "key_csv": aa.sha256_file(root / KEY_CSV),
                   "independent_labels_csv": aa.sha256_file(root / INDEP_CSV), "ask_alignment_py": aa.sha256_file(HERE.parent / "ask_alignment" / "ask_alignment.py")})
    for r in cqs:
        inputs[f"query_v2_{r['cq_id']}"] = aa.sha256_text(r["query_text"])

    snapshot = Graph()
    snapshot.parse(root / aa.INPUT_FILES["brick_snapshot"], format="turtle")

    term_users: dict[str, set[str]] = defaultdict(set)
    q_terms: dict[str, list[str]] = {}
    step7_text: dict[str, str] = {}
    fired: dict[str, list[str]] = {}
    for r in cqs:
        terms = aa.query_terms(r["query_text"])
        q_terms[r["cq_id"]] = [ns + loc for ns, loc in terms]
        for ns, loc in terms:
            term_users[ns + loc].add(r["cq_id"])
        step7_text[r["cq_id"]], fired[r["cq_id"]] = rewrite_predicates(r["query_text"], rules)

    mapping_rows, outcomes, structural, map_stats, rule_fire = [], [], {}, {}, defaultdict(Counter)
    for v in VARIANTS:
        graph = Graph()
        graph.parse(root / aa.INPUT_FILES[f"variant_graph_{v}"], format="turtle")
        vocab = aa.ct_vocab_from_graph(graph)
        pred_triples = {n: sum(1 for _ in graph.triples((None, URIRef(i), None))) for n, i in STRUCT_PREDICATES.items()}
        alt_triples = {r["rule_id"]: sum(1 for _ in graph.triples((None, URIRef(r["variant_predicate"]), None)))
                       for r in pmap_rows if r["status"] == "active"}
        structural[v] = {"triples": len(graph), "ct_terms_candidate_vocabulary": len(vocab.terms),
                         "scaffold_terms_excluded": vocab.n_scaffold_excluded,
                         "query_predicate_triples": pred_triples, "rule_variant_predicate_triples": alt_triples}
        results = {}
        for iri in sorted(term_users):
            ns = next(n for n in aa.REWRITE_NAMESPACES if iri.startswith(n))
            res = aa.map_term(iri, aa.REWRITE_NAMESPACES[ns], iri[len(ns):], aa.brick_labels(snapshot, iri), vocab)
            results[iri] = res
            mapping_rows.append({
                "variant": v, "brick_term": aa.short_name(iri), "brick_iri": iri, "brick_labels": "|".join(res.labels),
                "status": res.status, "rule": res.rule, "ct_iri": res.ct_iri,
                "n_candidates_at_rule": len(res.top_candidates),
                "candidates_at_rule": "|".join(c[len(aa.CT_NS):] for c in res.top_candidates),
                "alternate_candidates": ";".join(f"{r}={'|'.join(c[len(aa.CT_NS):] for c in cs)}" for r, cs in sorted(res.alt_candidates.items())),
                "used_by_cqs": "|".join(sorted(term_users[iri]))})
        sc = Counter(r.status for r in results.values())
        map_stats[v] = {"terms": len(results), "mapped": sc["mapped"], "ambiguous": sc["ambiguous"], "unmapped": sc["unmapped"],
                        "unmapped_terms": sorted(aa.short_name(i) for i, r in results.items() if r.status == "unmapped"),
                        "ambiguous_terms": sorted(aa.short_name(i) for i, r in results.items() if r.status == "ambiguous")}
        absent_core = [n for n, c in pred_triples.items() if c == 0]
        for r in cqs:
            cq = r["cq_id"]
            before = aa.evaluate_cq(graph, r["query_text"], q_terms[cq], results, absent_core)
            after = aa.evaluate_cq(graph, step7_text[cq], q_terms[cq], results, absent_core)
            pabs = absent_predicates(graph, r["query_text"], rules)
            for rid in fired[cq]:
                rule_fire[rid][v] += 1
            outcomes.append({
                "cq_id": cq, "variant": v, "class": r["cls"], "category": r["category"], "cluster_id": r["cluster_id"],
                "has_primary_cell": (cq, v) in primary,
                "before_outcome": before["outcome"], "after_outcome": after["outcome"], "outcome": after["outcome"],
                "changed": before["outcome"] != after["outcome"],
                "predicate_map_applied": fired[cq],
                "predicate_absent": pabs if after["outcome"] == "false" else [],
                "predicates_without_triples": pabs,
                "unmapped_terms": after["unmapped_terms"], "ambiguous_terms": after["ambiguous_terms"],
                "rewritten_query_sha256_before": before["rewritten_query_sha256"],
                "rewritten_query_sha256_after": after["rewritten_query_sha256"],
                "any_candidate_outcome_before": before["any_candidate_outcome"],
                "any_candidate_outcome_after": after["any_candidate_outcome"]})

    res = analyse(outcomes, primary, labels, ah, with_ci)
    res.update({
        "schema": "ask_alignment results v2 (v1 schema + predicate_map_applied + before/after outcome)",
        "status": ("EXPLORATORY and POST HOC supplement registered in addendum 16 (tag access2026-addendum16-freeze); "
                   "feeds no gate. AH labels are AI-drafted, author-revised; the judge is gemini-3.6-flash."),
        "inputs_sha256": inputs,
        "config": {"ct_namespace": aa.CT_NS, "variants": list(VARIANTS), "rules_in_priority_order": list(aa.RULES) + ["predicate_map"],
                   "predicate_map_rules": [{k: r[k] for k in ("rule_id", "status", "query_predicate", "variant_predicate", "direction")} for r in pmap_rows],
                   "active_rewrite_rules": len([r for r in pmap_rows if r["status"] == "active"]),
                   "rewrite_namespaces": aa.REWRITE_NAMESPACES,
                   "bootstrap": {"B": aa.BOOTSTRAP_B, "seed": aa.BOOTSTRAP_SEED, "method": "BCa (analyze_holdout.cluster_bootstrap_stat, midrank)", "cluster": "cluster_id (= CQ)"},
                   "decision_constants": {"NE_MAX": NE_MAX, "KAPPA_MIN": KAPPA_MIN, "N_MIN_EVALUABLE": N_MIN_EVALUABLE}},
        "variant_graphs": structural, "mapping_summary": map_stats,
        "predicate_map_applied": {"rule_fired_on_cq_variant_pairs": {k: dict(sorted(v.items())) for k, v in sorted(rule_fire.items())},
                                  "rules_per_cq": {k: v for k, v in sorted(fired.items())}},
        "per_cq_variant": sorted(outcomes, key=lambda o: (o["cq_id"], o["variant"]))})
    mapping_rows.sort(key=lambda r: (r["variant"], r["brick_term"]))
    return res, mapping_rows


def cnt(c: Counter) -> dict:
    return {"true": c["true"], "false": c["false"], "not_evaluable": c["not_evaluable"], "total": sum(c.values())}


def analyse(outcomes, primary, labels, ah, with_ci=True) -> dict:
    counts = {}
    for cls in ("deterministic", "expert"):
        for stage in ("before_outcome", "after_outcome"):
            counts[f"{cls}__{stage}"] = {
                "overall": cnt(Counter(o[stage] for o in outcomes if o["class"] == cls)),
                "per_variant": {v: cnt(Counter(o[stage] for o in outcomes if o["class"] == cls and o["variant"] == v)) for v in VARIANTS}}
    transitions = {}
    for cls in ("deterministic", "expert"):
        tr = Counter((o["before_outcome"], o["after_outcome"]) for o in outcomes if o["class"] == cls)
        transitions[cls] = {f"{b}->{a}": n for (b, a), n in sorted(tr.items())}
    changed = [{"cq_id": o["cq_id"], "variant": o["variant"], "class": o["class"], "before": o["before_outcome"],
                "after": o["after_outcome"], "rules": o["predicate_map_applied"]} for o in outcomes if o["changed"]]

    det = [o for o in outcomes if o["class"] == "deterministic"]
    recs = []
    for o in det:
        key = (o["cq_id"], o["variant"])
        if key in primary and o["after_outcome"] != "not_evaluable":
            lab = labels[key]
            recs.append({"cluster_id": o["cluster_id"], "variant": o["variant"], "ask": int(o["after_outcome"] == "true"),
                         "j2": int(lab["J"] >= 2), "s_ah": lab["s_ah"], "s_ind": lab["s_ind"],
                         "pred_absent": bool(o["predicate_absent"])})
    bf = [r for r in recs if r["variant"] != "A"]
    a_only = [r for r in recs if r["variant"] == "A"]
    bf_det = [o for o in det if o["variant"] != "A"]
    ne_n = sum(o["after_outcome"] == "not_evaluable" for o in bf_det)
    conc = {"universe_note": ("cells = primary (CQ, variant) cells of the 18 deterministic CQs whose after-outcome is evaluable; "
                              "cluster = CQ"),
            "A_separate_row": concordance(ah, a_only, with_ci),
            "B_to_F_decision_universe": concordance(ah, bf, with_ci),
            "all_variants_pooled_descriptive": concordance(ah, recs, with_ci),
            "per_variant_no_ci": {v: concordance(ah, [r for r in recs if r["variant"] == v], False) for v in VARIANTS},
            "sensitivity_predicate_absent_excluded_B_to_F": concordance(ah, [r for r in bf if not (r["ask"] == 0 and r["pred_absent"])], with_ci)}
    decision = decide(conc["B_to_F_decision_universe"], ne_n / len(bf_det), ne_n, len(bf_det))
    # remaining unmapped / predicate-absent after step 7
    unm = Counter()
    for o in det:
        for t in o["unmapped_terms"] + o["ambiguous_terms"]:
            unm[(o["variant"] != "A", t)] += 1
    pa = Counter()
    for o in outcomes:
        if o["class"] == "deterministic":
            for p in o["predicate_absent"]:
                pa[(o["variant"] == "A", p)] += 1
    return {"ask_counts": counts, "transitions": transitions, "changed_pairs": changed, "concordance": conc, "decision": decision,
            "remaining": {"unmapped_or_ambiguous_terms_det_runs": {("A" if not k[0] else "B-F") + ":" + k[1]: n for k, n in sorted(unm.items())},
                          "predicate_absent_false_det_runs": {("A" if k[0] else "B-F") + ":" + k[1]: n for k, n in sorted(pa.items())}},
            "label_crosscheck": {"cells_with_S_AH_ne_perCellA": sum(1 for v in labels.values() if v["s_ah"] != v["a_perCell"])}}


MAPPING_COLUMNS = aa.MAPPING_COLUMNS


def comparison_md(res: dict) -> str:
    lines = ["# comparison_v2 (generated by run_oracle_v2.py; exploratory, post hoc)", ""]
    for cls in ("deterministic", "expert"):
        lines += [f"## {cls} CQs: outcome before -> after step 7 (true / false / not_evaluable)", "",
                  "| variant | before | after |", "|---|---|---|"]
        b = res["ask_counts"][f"{cls}__before_outcome"]["per_variant"]
        a = res["ask_counts"][f"{cls}__after_outcome"]["per_variant"]
        for v in VARIANTS:
            lines.append(f"| {v} | {b[v]['true']} / {b[v]['false']} / {b[v]['not_evaluable']} | {a[v]['true']} / {a[v]['false']} / {a[v]['not_evaluable']} |")
        lines.append("")
    c = res["concordance"]
    lines += ["## concordance (deterministic CQs, evaluable primary cells)", "",
              "| row | n | oracle true | kappa J>=2 | kappa S_AH | kappa S_indep | agree S_AH | agree S_indep |", "|---|--:|--:|--:|--:|--:|--:|--:|"]

    def f(x):
        return "undef" if x is None else f"{x:.3f}"
    for name in ("A_separate_row", "B_to_F_decision_universe", "all_variants_pooled_descriptive",
                 "sensitivity_predicate_absent_excluded_B_to_F"):
        r = c[name]
        lines.append(f"| {name} | {r['n_cells']} | {r['oracle_true_cells']} | {f(r['oracle_vs_judge_J_ge_2']['kappa'])} | "
                     f"{f(r['oracle_vs_S_AH']['kappa'])} | {f(r['oracle_vs_S_independent']['kappa'])} | "
                     f"{f(r['oracle_vs_S_AH'].get('percent_agreement'))} | {f(r['oracle_vs_S_independent'].get('percent_agreement'))} |")
    d = res["decision"]
    lines += ["", f"## decision: {d['verdict']}", "",
              f"C0 nonconstant {d['C0_nonconstant']}; C1 not_evaluable {d['C1_not_evaluable_runs']} = {d['C1_not_evaluable_share']:.3f} (pass {d['C1_pass']}); "
              f"C2 kappa(S_AH) {f(d['C2_kappa_oracle_S_AH'])} (pass {d['C2_pass']}); C3 kappa(S_indep) {f(d['C3_kappa_oracle_S_independent'])} (pass {d['C3_pass']})", ""]
    return "\n".join(lines) + "\n"


def write_outputs(res: dict, rows: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "mapping_v2.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MAPPING_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    res = dict(res)
    res["script_sha256"] = aa.sha256_file(Path(__file__).resolve())
    res["mapping_v2_csv_sha256"] = aa.sha256_file(out_dir / "mapping_v2.csv")
    (out_dir / "ask_results_v2.json").write_text(json.dumps(aa._round(res), indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "comparison_v2.md").write_text(comparison_md(res), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out-dir", type=Path, default=HERE)
    a = ap.parse_args(argv)
    res, rows = build(a.root)
    write_outputs(res, rows, a.out_dir)
    print(res["ask_counts"]["deterministic__after_outcome"]["overall"], res["decision"]["verdict"])
    print(f"wrote {a.out_dir}/ask_results_v2.json, mapping_v2.csv, comparison_v2.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
