"""results.json, REPORT_auto.md and tables.tex from results_stage1.json / results_stage2.json (addendum 32).  AI-generated; review
before use.  Numbers are copied, never recomputed.  LLM-labeled; not human-validated beyond Stage 1."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b", "qwen": "Qwen3.8-Flash-Next"}


def ci(r, nd=3):
    if not r or r.get("est") is None:
        return "n/a"
    if r.get("lo") is None:
        return f"{r['est']:.{nd}f}"
    return f"{r['est']:.{nd}f} [{r['lo']:.{nd}f}, {r['hi']:.{nd}f}]"


def pct(r, nd=1):
    if not r or r.get("est") is None:
        return "n/a"
    if r.get("lo") is None:
        return f"{100 * r['est']:.{nd}f}%"
    return f"{100 * r['est']:.{nd}f}% [{100 * r['lo']:.{nd}f}, {100 * r['hi']:.{nd}f}]"


def load(name):
    p = HERE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def stage1_md(s1) -> list[str]:
    md = ["## Stage 1: calibration gate", "",
          f"Gate rule (PLAN 32.6): PASS iff at least one primary model passes both humans; pair passes iff n >= 30 and the lower 95% BCa bound of kappa(LLM, human) >= kappa(AH, R2) on the same cells - 0.10.",
          f"**Verdict: {'PASS' if s1['gate']['pass'] else 'FAIL'}** (passing models: {s1['gate']['passing_models'] or 'none'}; headline labeler: {s1['gate']['headline_labeler']}).", "",
          "| model | human | n cells | kappa(LLM, human) [95% CI] | kappa(AH, R2) same cells | gate ref (-0.10) | exact agreement | pass |", "|---|---|---:|---|---|---:|---|:-:|"]
    for m, b in s1["models"].items():
        if "primary" not in b:
            md.append(f"| {NAMES.get(m, m)} | - | 0 | {b.get('status', 'no labeled cells')} | | | | |")
            continue
        p = b["primary"]
        for h in ("AH", "R2"):
            v = p["vs_human"][h]
            md.append(f"| {NAMES[m]}{' (secondary)' if m == 'qwen' else ''} | {h} | {p['n_cells']} | {ci(v['kappa'])} | {ci(p['human_human_same_cells']['kappa'])} | {v['gate_ref_kappa_minus_0.10']} | {ci(v['agreement'])} | {'yes' if v['gate_pass'] else 'no'} |")
    md += ["", "### Unsupported credit pi-hat (share of cells with registered-judge J >= 2 and S = 0) on the same cells", "",
           "| model | pi-hat under LLM | under AH | under R2 | LLM - AH | LLM - R2 |", "|---|---|---|---|---|---|"]
    for m, b in s1["models"].items():
        if "primary" in b:
            q = b["primary"]["pi_hat"]
            md.append(f"| {NAMES[m]} | {pct(q['LLM'])} | {pct(q['AH'])} | {pct(q['R2'])} | {pct(q['LLM_minus_AH'])} | {pct(q['LLM_minus_R2'])} |")
    hh = s1["human_human_all188"]
    md += ["", f"All 188 cells: kappa(AH, R2) = {ci(hh['kappa'])}; pi-hat AH = {pct(hh['pi_hat_AH'])}, R2 = {pct(hh['pi_hat_R2'])}.", "",
           "### Label coverage, consistency and reliability", "",
           "| model | cells with label / attempted | undefined | context skip | share of label 1 | R25 coverage | alpha (25 slots) | valid slot share |", "|---|---:|---:|---:|---|---|---|---:|"]
    for m, b in s1["models"].items():
        if "primary" in b:
            md.append(f"| {NAMES[m]} | {b['cells_with_label']} / {b['cells_attempted']} | {b['cells_undefined']} | {b['context_skip']} | {pct(b['primary']['share_label1'])} | {pct(b['R25_coverage'])} | {ci(b['alpha_25_slots'])} | {b['parse_valid_slot_share']} |")
    md += ["", "### Agreement of the R25-consistent subset (secondary)", ""]
    for m, b in s1["models"].items():
        sub = b.get("R25_subset")
        if sub and "vs_human" in sub:
            md.append(f"- {NAMES[m]}: n = {sub['n_cells']}; kappa vs AH {ci(sub['vs_human']['AH']['kappa'])}, vs R2 {ci(sub['vs_human']['R2']['kappa'])}; human-human on the same cells {ci(sub['human_human_same_cells']['kappa'])}.")
    vc = s1["view_coverage"]
    md += ["", "### View term coverage (PLAN 32.4; target >= 90%, reported whatever it is)", "",
           f"- The retrieval view holds the expected-answer terms (anchors and >= 50% of the answer terms on one line) in {vc['view_holds_terms']} / {vc['n_cells']} cells ({100 * vc['view_holds_terms_share']:.1f}%). "
           f"The full rendering itself holds them in {vc['full_holds_terms']} / {vc['n_cells']} ({100 * vc['full_holds_terms_share']:.1f}%), which is the ceiling of any view of it under this strict single-line test; "
           f"given that the full rendering holds them, the view holds them in {vc['view_holds_given_full_holds']['k']} / {vc['view_holds_given_full_holds']['n']} ({100 * vc['view_holds_given_full_holds']['share']:.1f}%). "
           f"The subgraph views of addendum 30 held them in {vc['subgraph_view_holds_terms']} / {vc['n_cells']} ({100 * vc['subgraph_view_holds_terms_share']:.1f}%).",
           f"- Judge span located in the rendering: all pieces found in {vc['span_located']['all_pieces_found']} of {vc['span_located']['cells_with_span']} cells that had a span. Fallback used in {vc['fallback_used']} primary cells; character cap reached in {vc['cap_reached']}.",
           "- By variant (view / full / subgraph holds terms, of n): " + "; ".join(f"{v}: {x['view']}/{x['full']}/{x['subgraph']} of {x['n']}" for v, x in vc["by_variant"].items()) + ".",
           "- The anchor half of the test is true by construction wherever an anchor line exists; the informative half is the answer-term fraction.", "",
           "### Negative control (diagnostic): the 24 registered ablated controls, majority label", ""]
    for m, c in s1["controls"].items():
        md.append(f"- {NAMES[m]}: labeled S = 0 in {c['label0']} of {c['n_controls']} (S = 1: {c['label1']}, undefined: {c['undefined']}).")
    md += ["", "### Timing record (per-call latency, seconds)", ""]
    for m, l in s1["latency"].items():
        md.append(f"- {NAMES[m]}: {l}")
    return md


def stage2_md(s2) -> list[str]:
    md = ["", "## Stage 2: expanded audit", ""]
    b = s2["bank"]
    md += [f"- Bank: {b['n_questions']} questions (frozen sha256 `{b['bank_sha256']}`); eligible cells {b['n_eligible_cells']} of {b['n_cells_total']} (by variant {b['eligible_cells_by_variant']}); "
           f"**eligible clusters {b['n_eligible_clusters']}** (target >= {b['target_clusters']}: {'met' if b['target_met'] else 'NOT met; the target was not lowered'}); clusters eligible in both A and B: {b['n_clusters_eligible_in_A_and_B']}.",
           f"- Judges: {', '.join(s2['judges'])}. {s2['judge_note']}.", f"- Stage 1 gate: {'PASS' if s2['stage1_gate']['pass'] else 'FAIL'}."]
    if not s2.get("audit_run"):
        md += ["", f"**Not run as an audit: {s2['reason']}.** Judge-only descriptive scores are in `results_stage2.json`."]
        return md
    for c in s2["combinations"]:
        if "pi_hat" not in c:
            md.append(f"- {c.get('labeler')}: {c.get('note', 'not computed')}")
            continue
        g = c["gates"]
        md += ["", f"### Labeler {NAMES[c['labeler']]} x judge {NAMES[c['judge']]}{' (headline pair)' if c.get('headline') else ''}", "",
               f"- Cells {c['n_cells']} in {c['n_clusters']} clusters (label undefined {c['cells_label_undefined']}, judge invalid {c['cells_judge_invalid']}).",
               f"- pi-hat = {pct({'est': c['pi_hat']['pi_hat'], 'lo': c['pi_hat'].get('ci_lo'), 'hi': c['pi_hat'].get('ci_hi')})} (events {c['pi_hat']['events']}); two-way error counts: {c['two_way_counts']}.",
               f"- MAE(J, R_LLM), R = 0 rubric (G5 statistic): {g['G5_mae_judge_human'].get('value')}; coverage on L1*: {c['coverage_pct_L1star']}.",
               f"- A->B contrast on L1*: {c['contrasts'].get('A->B')}; MDE: {c.get('A_to_B_mde')}.",
               f"- Verbatim-span check: {c['verbatim_span_check']}.",
               "", "| gate | status | value | threshold |", "|---|---|---|---|"]
        for k, v in g.items():
            md.append(f"| {k} | {v.get('status')} | {str(v.get('value'))[:90]} | {str(v.get('threshold'))[:60]} |")
    return md


def tables(s1, s2) -> str:
    rows = []
    for m, b in s1["models"].items():
        if "primary" in b:
            for h in ("AH", "R2"):
                v = b["primary"]["vs_human"][h]
                rows.append(f"{NAMES[m]} & {h} & {b['primary']['n_cells']} & {ci(v['kappa'], 2)} & {ci(b['primary']['human_human_same_cells']['kappa'], 2)} & {'yes' if v['gate_pass'] else 'no'} \\\\")
    return "% LLM-labeled; not human-validated beyond Stage 1. Generated by s2_report.py from results_stage1.json\n" + "\n".join(rows) + "\n"


def main() -> int:
    s1, s2 = load("results_stage1.json"), load("results_stage2.json")
    if s1 is None:
        raise SystemExit("results_stage1.json missing")
    (HERE / "results.json").write_text(json.dumps({"banner": "LLM-labeled; not human-validated beyond Stage 1.", "stage1": s1, "stage2": s2},
                                                   indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    md = ["# Study 2 (addendum 32) -- automatic report", "", "> **LLM-labeled; not human-validated beyond Stage 1.** AI-generated; a person must review it. All numbers come from `results.json`, written by `analyze.py` from the raw call records; nothing was tuned after the first model call.", ""]
    md += stage1_md(s1)
    if s2:
        md += stage2_md(s2)
    else:
        md += ["", "## Stage 2", "", "Not run (no `results_stage2.json`)."]
    (HERE / "REPORT_auto.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "tables.tex").write_text(tables(s1, s2), encoding="utf-8")
    print("wrote results.json, REPORT_auto.md, tables.tex")
    return 0


if __name__ == "__main__":
    sys.exit(main())
