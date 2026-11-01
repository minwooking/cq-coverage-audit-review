"""Generate REPORT_auto.md and tables.tex from results.json (study 9). AI-generated; review before reuse."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results.json").read_text())


def f(x, nd=2):
    if x is None:
        return "-"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def tex(s):
    return str(s).replace("&", r"\&").replace("_", r"\_").replace("%", r"\%")


rows = []
md = ["# Study 9 -- schema-anchored and internal-consistency SHACL shapes (auto-generated)", "",
      "> AI-generated; review before relying on it. Prereg addendum 39 (`PLAN.md`), post hoc, no model call. "
      "Verdict rule (fixed in advance): pass = focus nodes > 0 and violations = 0; focus nodes = 0 -> not applicable (vacuous). "
      "Second domain and development corpus: numbers only.", ""]

md += ["## 1. Shape counts", "",
       "| Domain | official full set: node shapes / property shapes / minCount>=1 / sh:class / sh:datatype / nodeKind | required pairs |",
       "|---|---|---|"]
for d, dom in R["domains"].items():
    fs = dom.get("official_full_shape_set")
    if fs:
        md.append(f"| {d} | {fs['node_shapes']} / {fs['property_shapes']} / {fs['minCount_ge1']} / {fs['sh_class']} / {fs['sh_datatype']} / {fs['sh_nodeKind']} | {dom['official_required_pairs']} |")
    else:
        md.append(f"| {d} | no official ontology | - |")
md += ["", "Per-variant shape sets (official: only classes the variant references; internal: from the variant's own declarations):", "",
       "| Domain | Var | official: refs (R1/R2) / node / prop / minCount>=1 / class / datatype | internal: node / prop / class / datatype / nodeKind / minCount>=1 |",
       "|---|---|---|---|"]
for d, dom in R["domains"].items():
    for v, rec in dom["variants"].items():
        if rec.get("missing"):
            continue
        o = rec["official"].get("shape_counts")
        i = rec["internal"]["shape_counts"]
        os_ = (f"{o['referenced_by_level'].get('R1', 0)}/{o['referenced_by_level'].get('R2', 0)} / {o['node_shapes']} / {o['property_shapes']} / {o['minCount_ge1']} / {o['sh_class']} / {o['sh_datatype']}") if o else "-"
        md.append(f"| {d} | {v} | {os_} | {i['node_shapes']} / {i['property_shapes']} / {i['sh_class']} / {i['sh_datatype']} / {i['sh_nodeKind']} / {i['minCount_ge1']} |")

md += ["", "## 2. Per variant: official shapes (L1 strict, headline) and internal-consistency shapes", "",
       "| Domain | Var | triples | official L1: focus / viol / per 1k / verdict | internal: focus / viol / per 1k / verdict | official L2 (punning sens.): focus / viol / verdict |",
       "|---|---|---|---|---|---|"]
for d, dom in R["domains"].items():
    for v, rec in dom["variants"].items():
        if rec.get("missing"):
            continue
        o = rec["official"]
        i = rec["internal"]
        if "L1" in o:
            l1 = o["L1"]
            l2 = o["L2_punning_sensitivity"]
            os_ = f"{f(l1.get('focus_nodes'))} / {f(l1.get('violations'))} / {f(l1.get('violations_per_1000_triples'))} / {l1['verdict']}"
            o2 = f"{f(l2.get('focus_nodes'))} / {f(l2.get('violations'))} / {l2['verdict']}"
            of, ov, ovd = l1.get("focus_nodes"), l1.get("violations"), l1["verdict"]
        else:
            os_, o2, of, ov, ovd = "no official ontology", "-", None, None, "--"
        is_ = f"{f(i.get('focus_nodes'))} / {f(i.get('violations'))} / {f(i.get('violations_per_1000_triples'))} / {i['verdict']}"
        md.append(f"| {d} | {v} | {rec['triples']} | {os_} | {is_} | {o2} |")
        rows.append((d, v, of, ov, i.get("focus_nodes"), i.get("violations"), ovd, i["verdict"]))

md += ["", "## 3. Top violated constraints (top 5 per variant; public domains with path and shape, others component only)", ""]
for d, dom in R["domains"].items():
    for v, rec in dom["variants"].items():
        if rec.get("missing"):
            continue
        for lab, blk in (("official L1", rec["official"].get("L1")), ("internal", rec["internal"])):
            if not blk or not blk.get("top_constraints"):
                continue
            md.append(f"* **{d} {v} {lab}**: " + "; ".join(
                f"{t['component'].replace('ConstraintComponent', '')}" + (f" `{t['path'].split('/')[-1].split('#')[-1]}`" if t.get("path", "-") != "-" else (" (node-level/domain)" if lab == "internal" and t["component"].startswith("Class") and "path" in t else "")) + f" x{t['n']}"
                for t in blk["top_constraints"]))
md += ["", "## 4. Internal-consistency violations by kind", ""]
for d, dom in R["domains"].items():
    for v, rec in dom["variants"].items():
        k = rec.get("internal", {}).get("violations_by_kind") if not rec.get("missing") else None
        if k:
            md.append(f"* {d} {v}: " + ", ".join(f"{a} {b}" for a, b in sorted(k.items(), key=lambda x: -x[1])))
md += ["", "## 5. Step 2 -- stage-C artefact (C-F with internal violations)", ""]
for d, dom in R["domains"].items():
    for v, rec in dom["variants"].items():
        if rec.get("missing"):
            continue
        so = rec["internal"].get("step2_offenders")
        if not so:
            continue
        md.append(f"* **{d} {v}**: {so['properties_with_violation']} of {so['declared_properties']} declared properties carry >=1 violation "
                  f"({f(100 * so['share_declared_properties_with_violation'], 1)}%); top 10 carry {f(100 * (so['share_violations_on_top10'] or 0), 1)}% of attributed violations.")
        for t in so.get("top_properties", [])[:5]:
            md.append(f"    * `{t['property']}` domain {t['declared_domain']} range {t['declared_range']}: {t['triples']} triples, {t['subjects']} subjects, "
                      f"violations {t['violations']}, share of subjects typed as declared domain {f(t['share_subjects_typed_declared_domain'])}, "
                      f"actual subject classes {[(c['class'], c['n']) for c in t['top_subject_classes']]}")
md += ["", "## 6. Reading notes (checked against the data)", "",
       "* Official shapes, L1: under B-F the pipeline's instances carry `ct:` classes, so no node is an instance of an official class: focus nodes = 0 in Brick, DCAT and SOSA/SSN for every variant B-F (and for Brick/SOSA A, whose official classes are declared, not instantiated) -> **not applicable (vacuous)**, not valid. Variant A of DCAT has instances of official classes and fails (missing dct:title / dct:description / dcat:accessURL).",
       "* PROV E and F pass the official shapes with 153 focus nodes; these are the `prov:Entity` chunk nodes (152) and one `prov:Activity` that the pipeline's own PROV stage emits (checked by listing the shapes with focus nodes), i.e. the provenance annotation layer, not the domain concepts. C, D (no PROV stage) are vacuous. PROV A passes on 5 focus nodes.",
       "* L2 (concepts typed by label as instances of official classes) is a sensitivity, not a validation: it makes the shapes applicable and then shows violations dominated by missing required properties (minCount) on label-typed concept nodes, which are class-concepts and not instances.",
       "* Internal consistency (set b) is non-vacuous in every variant that declares domain/range (A, C-F) and fails in every one of them; B declares none (vacuous). Violations are typed-but-wrong (`wrong_typed`), i.e. the declared domain/range is the most frequent class, not the class of all subjects/objects; A (baseline) violations are mostly untyped subjects/objects.",
       "* Counts: violations are counted per (focus node, constraint, value); a node-level domain violation is one result per declared property the node is a subject of."]
(HERE / "REPORT_auto.md").write_text("\n".join(md) + "\n")

t = [r"% study 9 (addendum 39): focus nodes / violations; official = schema-anchored shapes (L1 strict), internal = pipeline's own domain/range",
     r"\begin{tabular}{llrrrrll}", r"\hline",
     r"Domain & Var & $F_{\mathrm{off}}$ & $V_{\mathrm{off}}$ & $F_{\mathrm{int}}$ & $V_{\mathrm{int}}$ & Official & Internal \\ \hline"]
short = {"NA (vacuous)": "NA", "pass": "pass", "fail": "fail", "error": "err", "--": "--"}
for d, v, of, ov, inf, iv, ovd, ivd in rows:
    t.append(f"{tex(d)} & {tex(v)} & {f(of)} & {f(ov)} & {f(inf)} & {f(iv)} & {short.get(ovd, ovd)} & {short.get(ivd, ivd)} \\\\")
t += [r"\hline", r"\end{tabular}"]
(HERE / "tables.tex").write_text("\n".join(t) + "\n")
print("ok")
