"""Render results.json -> REPORT_auto.md and tables.tex (study 8). No model calls."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results.json").read_text())
ORDER = ["development", "Brick holdout", "DCAT", "SOSA/SSN", "PROV", "second domain (counts only)"]


def pct(x, d=0):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def tex(s):
    return str(s).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def n(d, k):
    return (d or {}).get(k, 0)


# ------------------------------------------------------------------ step 1
def step1_rows():
    rows = []
    for dn in ORDER:
        d = R["domains"].get(dn)
        if not d:
            continue
        for v, x in d["variants"].items():
            e = x.get("external_shacl")
            if not e:
                continue
            for sname, r in e.items():
                rows.append((dn, sname, v, r))
    return rows


def step1_md():
    L = ["## Step 1 - external SHACL validation", ""]
    L.append("Focus nodes = distinct nodes of the pipeline graph that a shape's target selects (class targets follow rdfs:subClassOf over graph + official ontology). "
             "`constraint` = shapes that carry at least one constraint component (rule-only shapes, e.g. Brick's inference rules, are counted separately). "
             "Results whose focus node belongs to the official ontology itself (pulled in as `ont_graph`) are not counted (column `ign`).")
    L += ["", "| Domain | shapes graph | V | conforms | viol | warn | ign | targeted shapes (constraint) | shapes with focus (constraint) | focus nodes (constraint) | top violated |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for dn, sname, v, r in step1_rows():
        sc = r["scope"]
        if "error" in r:
            L.append(f"| {dn} | {sname} | {v} | error | | | | {sc['targeted_shapes']} ({sc['constraint_shapes_targeted']}) | {sc['shapes_with_focus_nodes']} ({sc['constraint_shapes_with_focus_nodes']}) | {sc['distinct_focus_nodes']} ({sc['constraint_distinct_focus_nodes']}) | {r['error'][:90]} |")
            continue
        top = "; ".join(f"{t['component'].replace('ConstraintComponent', '')} {t['path'].split('/')[-1].split('#')[-1]} x{t['n']}" for t in r["top_constraints"][:2]) or "-"
        L.append(f"| {dn} | {sname} | {v} | {'yes' if r['conforms_data_nodes_only'] else 'no'} | {r['violations']} | {r['warnings']} | {r['results_on_official_ontology_nodes_ignored']} | "
                 f"{sc['targeted_shapes']} ({sc['constraint_shapes_targeted']}) | {sc['shapes_with_focus_nodes']} ({sc['constraint_shapes_with_focus_nodes']}) | {sc['distinct_focus_nodes']} ({sc['constraint_distinct_focus_nodes']}) | {top} |")
    L += ["", "### Are the official shapes non-vacuous? (constraints in the shapes graph itself)", "",
          "| Domain | shapes graph | node shapes | property shapes | minCount 0 | minCount >= 1 | sh:class | sh:datatype | sh:nodeKind | explicit targets | implicit class targets |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if d and d.get("external_shapes"):
            for sname, s in d["external_shapes"].items():
                L.append(f"| {dn} | {sname} | {s['node_shapes']} | {s['property_shapes_with_path']} | {s['minCount_0']} | {s['minCount_ge1']} | {s['class_constraints']} | {s['datatype']} | {s['nodeKind']} | {s['shapes_with_explicit_target']} | {s['shapes_with_implicit_class_target']} |")
    L += ["", "### No official shapes graph", ""]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if d and not d.get("external_shapes"):
            extra = d.get("official_ontology_sh_terms")
            L.append(f"* {dn}: none used" + (f"; `sh:` terms in the official ontology files: {sum(extra.values())}" if extra else "") + ".")
    L += ["", "### The paper's own `shapes_F.ttl` (auto-generated from the graph itself)", "",
          "| Domain | property constraints with minCount 0 | with minCount >= 1 | nodeKind | datatype | sh:class | node shapes | F conforms (own shapes) |", "|---|---|---|---|---|---|---|---|"]
    for dn in ORDER:
        d = R["domains"].get(dn)
        o = d and d["variants"].get("F", {}).get("own_shapes")
        if o:
            L.append(f"| {dn} | {o['minCount_0']} | {o['minCount_ge1']} | {o['nodeKind']} | {o['datatype']} | {o['class_constraints']} | {o['node_shapes']} | {o['F_conforms']} |")
    return L


def step1_tex():
    T = [r"\begin{tabular}{llcrrrr}", r"\hline", r"Domain & shapes & V & conf. & viol. & shapes w/ focus & focus nodes \\", r"\hline"]
    for dn, sname, v, r in step1_rows():
        sc = r["scope"]
        short = sname.replace(" (release shapes)", "").replace("DCAT-AP 3.0.1 ", "")
        if "error" in r:
            T.append(f"{tex(dn)} & {tex(short)} & {v} & err & - & {sc['constraint_shapes_with_focus_nodes']} & {sc['constraint_distinct_focus_nodes']} \\\\")
        else:
            T.append(f"{tex(dn)} & {tex(short)} & {v} & {'yes' if r['conforms_data_nodes_only'] else 'no'} & {r['violations']} & {sc['constraint_shapes_with_focus_nodes']} & {sc['constraint_distinct_focus_nodes']} \\\\")
    T += [r"\hline", r"\end{tabular}"]
    return T


# ------------------------------------------------------------------ step 2
def cat_str(c, keys=("exact", "subclass", "broader", "mismatch", "noncomparable", "official_undeclared", "not_declared")):
    return "/".join(str(c.get(k, 0)) for k in keys)


def step2_md():
    L = ["## Step 2 - domain/range quality against official ontologies", "",
         "Mapped = pipeline property mapped to an official property (levels: alignment file, exact IRI, local name; `ambig` = more than one local-name hit, not mapped). "
         "Declared-level categories (domain | range) are exact / subclass / broader / mismatch / non-comparable (generic pipeline class) / official undeclared / not declared, counted over mapped properties only. "
         "Usage = triples of mapped properties whose subject/object resolves by label to an official class; `comp` = compatible share among resolved ends, `res` = share of ends that resolve.", ""]
    L += ["| Domain | V | classes | props typed | dom+rng declared | mapped (align/IRI/name) | ambig | unmapped | domain e/s/b/m/nc/ou/nd | range e/s/b/m/nc/ou/nd | usage subj comp (res) | usage obj comp |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if not d or d["counts_only"] or not d.get("official_ontology"):
            continue
        for v, x in d["variants"].items():
            s = x["step2"]
            lv = s["mapping_levels"]
            L.append(f"| {dn} | {v} | {s['classes_declared']} | {s['properties_typed']} | {s['props_with_domain']}/{s['props_with_range']} | {s['n_mapped']} ({n(lv,'alignment')}/{n(lv,'exact_iri')}/{n(lv,'localname')}) | {n(lv,'ambiguous')} | {n(lv,'unmapped')+n(lv,'aligned_nondomain')} | "
                     f"{cat_str(s['declared_domain'])} | {cat_str(s['declared_range'])} | {pct(s['usage_subject_compatible_share'])} ({pct(s['usage_subject_resolvable_share'])}) | {pct(s['usage_object_compatible_share'])} |")
    L += ["", "Stem-extended mapping (post-plan sensitivity, labelled): number of mapped properties and declared-level exact+subclass share of mapped with a declared domain.", "",
          "| Domain | V | mapped (plan) | mapped (stem) | domain exact+subclass / comparable (stem) |", "|---|---|---|---|---|"]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if not d or d["counts_only"] or not d.get("official_ontology"):
            continue
        for v, x in d["variants"].items():
            st = x.get("step2_stem_sensitivity")
            if not st:
                continue
            dd = st["declared_domain"]
            comp = sum(dd.get(k, 0) for k in ("exact", "subclass", "broader", "mismatch"))
            L.append(f"| {dn} | {v} | {x['step2']['n_mapped']} | {st['n_mapped']} | {dd.get('exact',0)+dd.get('subclass',0)} / {comp} |")
    L += ["", "### Most-frequent-class artifact (all domains; second domain counts only)", "",
          "| Domain | V | classes declared | classes used as entity type | distinct declared domains | domain = most frequent declared domain | range = most frequent declared range | domain = most frequent entity class | most frequent class share of typed entities |", "|---|---|---|---|---|---|---|---|---|"]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if not d:
            continue
        for v, x in d["variants"].items():
            s = x["step2"]
            L.append(f"| {dn} | {v} | {s['classes_declared']} | {s['classes_used_as_entity_type']} | {s['distinct_declared_domains']} | {pct(s['share_domain_is_most_frequent_declared_domain'])} | {pct(s['share_range_is_most_frequent_declared_range'])} | {pct(s['share_domain_is_most_frequent_entity_class'])} | {pct(s['most_frequent_entity_class_share_of_typed_entities'])} |")
    L += ["", "### Official ontologies used", ""]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if d and d.get("official_ontology"):
            o = d["official_ontology"]
            L.append(f"* {dn}: {o['classes']} classes, {o['properties']} properties; official domain declared for {o['props_with_official_domain']}, range for {o['props_with_official_range']}.")
    return L


def step2_tex():
    T = [r"\begin{tabular}{llrrrrr}", r"\hline", r"Domain & V & mapped & dom. exact+sub/comparable & usage subj. comp. & classes & dom.=most freq. \\", r"\hline"]
    for dn in ORDER:
        d = R["domains"].get(dn)
        if not d or d["counts_only"]:
            continue
        for v, x in d["variants"].items():
            s = x["step2"]
            if "n_mapped" in s:
                dd = s["declared_domain"]
                comp = sum(dd.get(k, 0) for k in ("exact", "subclass", "broader", "mismatch"))
                T.append(f"{tex(dn)} & {v} & {s['n_mapped']} & {dd.get('exact',0)+dd.get('subclass',0)}/{comp} & {tex(pct(s['usage_subject_compatible_share']))} & {s['classes_declared']} & {tex(pct(s['share_domain_is_most_frequent_declared_domain']))} \\\\")
            else:
                T.append(f"{tex(dn)} & {v} & - & - & - & {s['classes_declared']} & {tex(pct(s['share_domain_is_most_frequent_declared_domain']))} \\\\")
    T += [r"\hline", r"\end{tabular}"]
    return T


# ------------------------------------------------------------------ step 3
def step3_rows():
    for dn in ORDER:
        d = R["domains"].get(dn)
        if not d:
            continue
        for v in ("E", "F"):
            x = d["variants"].get(v)
            if x and "step3" in x:
                yield dn, v, x["step3"]


def step3_md():
    L = ["## Step 3 - provenance coverage", "",
         "Concepts = `skos:Concept` subjects. Chunk share = chunks referenced by a `prov:wasDerivedFrom` link / all atomic chunks of that build. Triples = all triples except `prov:` and `dct:source`; share = triples whose subject is a concept with at least one link. "
         "Spot check (variant E, seed 20260913, 30 links): strict = the concept's label (or its domain-word-dropped form) occurs in the chunk text after normalisation; loose = all non-stop tokens occur in any order.", "",
         "| Domain | V | concepts | with prov | chunks ref. / total | links per linked concept (mean / median / max) | triples with prov subject | spot strict | spot loose |", "|---|---|---|---|---|---|---|---|---|"]
    for dn, v, t in step3_rows():
        sc = t.get("spot_check")
        L.append(f"| {dn} | {v} | {t['concepts']} | {t['concepts_with_prov']} ({pct(t['share_concepts_with_prov'])}) | {t['chunks_referenced']}/{t['chunks_total']} ({pct(t['share_chunks_referenced'])}) | "
                 f"{t['links_per_linked_concept_mean']:.2f} / {t['links_per_linked_concept_median']} / {t['links_per_linked_concept_max']} | {pct(t['share_triples_subject_has_prov'])} | "
                 f"{(str(sc['strict_contained']) + '/' + str(sc['sampled']) + ' (' + pct(sc['strict_share']) + ')') if sc else '-'} | {(str(sc['loose_contained']) + '/' + str(sc['sampled']) + ' (' + pct(sc['loose_share']) + ')') if sc else '-'} |")
    L += ["", "Second domain: no E/F variant, no PROV links; nothing reported (counts only)."]
    return L


def step3_tex():
    T = [r"\begin{tabular}{llrrrrr}", r"\hline", r"Domain & V & concepts w/ prov & chunks ref. & links/concept & triples w/ prov & spot strict \\", r"\hline"]
    for dn, v, t in step3_rows():
        sc = t.get("spot_check")
        T.append(f"{tex(dn)} & {v} & {tex(pct(t['share_concepts_with_prov']))} & {tex(pct(t['share_chunks_referenced']))} & {t['links_per_linked_concept_mean']:.2f} & {tex(pct(t['share_triples_subject_has_prov']))} & {tex(pct(sc['strict_share'])) if sc else '-'} \\\\")
    T += [r"\hline", r"\end{tabular}"]
    return T


def main():
    L = ["# Study 8 - independent structural-quality measurements (auto-generated)", "",
         "AI-generated; review before reliance. Post hoc, exploratory (prereg addendum 38 = `PLAN.md`). No model calls. No threshold or decision is attached to any number. "
         f"Generated {R['generated_utc']}; seed {R['seed']}. Second domain: counts only.", ""]
    L += ["External files (URL, sha256): " + "; ".join(f"{f['file']} `{f['sha256'][:12]}`" for f in R["external_fetch_log"]), ""]
    L += step1_md() + [""] + step2_md() + [""] + step3_md()
    (HERE / "REPORT_auto.md").write_text("\n".join(L) + "\n")
    T = ["% study 8 tables (auto-generated)", "% Table 1: external SHACL", *step1_tex(), "", "% Table 2: domain/range", *step2_tex(), "", "% Table 3: provenance", *step3_tex()]
    (HERE / "tables.tex").write_text("\n".join(T) + "\n")
    print("ok")


if __name__ == "__main__":
    main()
