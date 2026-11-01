#!/usr/bin/env python3
"""LaTeX rows of the paper's tables for addenda 30 and 31, written from results.json and results_adjudication.json.
AI-generated; review before use.  Numbers are copied, never recomputed.  The manuscript sources are not edited by this script.

Writes (tabular bodies, no preamble; the header row is the first line, then \\midrule):
  tables_appendix.tex        Appendix A table (Tier 1, compact: point estimates of the primary rule, the majority and the consensus)
  tables_supp_tier1.tex      supplement: Tier 1 in full (the rows of tables.tex with short model names, intervals included)
  tables_supp_personas.tex   supplement: persona-level detail of Tier 1
  tables_supp_reliability.tex  supplement: reliability side by side (per model; LLM-LLM pairs)
  tables_supp_adjudication.tex supplement: the objective adjudication (addendum 31)
  tables_supp_tiers.tex      supplement: tiers without a human reference (aggregates; the second domain is aggregate only)
`--check` compares the files on disk with what the JSON files give and checks that every row occurs verbatim in main.tex or
supplement.tex (exit 1 on a difference or a missing row).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parents[1]
SHORT = {"glm": "GLM", "gptoss": "gpt-oss", "qwen": "Qwen$^{\\dagger}$"}
LONG = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b", "qwen": "Qwen3.8-Flash-Next$^{\\dagger}$"}
TIER_NAMES = {"2a": "2a, remaining holdout cells (36 questions)", "2b": "2b, natural-documentation cells", "3a": "3a, holdout paraphrases",
              "3b": "3b, holdout extra questions", "3c": "3c, development bank", "3d": "3d, second domain (aggregate only)",
              "3e": "3e, unfrozen expansion draft"}


def _f(x, nd):
    t = f"{x:.{nd}f}"
    if t.startswith("-"):
        return t[1:] if float(t) == 0 else f"${t}$"      # no negative zero; a minus sign in math mode
    return t


def ci(r, nd=2):
    if not r or r.get("est") is None:
        return "--"
    if r.get("lo") is None:
        return _f(r["est"], nd)
    return f"{_f(r['est'], nd)} [{_f(r['lo'], nd)}, {_f(r['hi'], nd)}]"


def pc(r, nd=1):
    if not r or r.get("est") is None:
        return "--"
    return f"{100 * r['est']:.{nd}f}"


def pcci(r, nd=1):
    if not r or r.get("est") is None:
        return "--"
    if r.get("lo") is None:
        return f"{100 * r['est']:.{nd}f}"
    return f"{100 * r['est']:.{nd}f} [{100 * r['lo']:.{nd}f}, {100 * r['hi']:.{nd}f}]"


def gshare(x):
    """adjudication group share: k/n (share %) or --"""
    if not x or x.get("n", 0) == 0:
        return "--"
    s = f"{x['k']}/{x['n']}"
    if x.get("share") is not None:
        s += f" ({100 * x['share']:.0f}\\%)"
    return s


def gshare_ci(x):
    if not x or x.get("n", 0) == 0:
        return "--"
    s = gshare(x)
    c = x.get("ci")
    if c and c.get("lo") is not None:
        s = f"{x['k']}/{x['n']} ({100 * x['share']:.0f}\\%; {100 * c['lo']:.0f}--{100 * c['hi']:.0f})"
    return s


# ---------------------------------------------------------------- Tier 1: full table (supplement) and compact table (appendix)
def tier1_rows(res: dict) -> str:
    """The rows of tables.tex with short model names (supplement; intervals included)."""
    out = ["Model & Rule & Cons./eval. (cov.\\ \\%) & $\\kappa$(LLM, AH) & $\\kappa$(LLM, R2) & $\\kappa$(AH, R2), same cells & "
           "$\\hat\\pi$ LLM / AH / R2 (\\%) \\\\", "\\midrule"]
    for m, blk in res["models"].items():
        if blk.get("status") != "analysed":
            continue
        s = blk["S_final"]
        for rn, label in (("R25", "$\\geq 23/25$"), ("R25U", "25/25")):
            r = s[rn]
            ag = r["agreement"]
            cons = f"{r['n_consistent']}/{r['n_evaluated']} ({pc(r['coverage'])})"
            if "vs_human" in ag:
                vh, ph = ag["vs_human"], ag["pi_hat"]
                out.append(f"{SHORT[m]} & {label} & {cons} & {ci(vh['AH']['kappa'])} & {ci(vh['R2']['kappa'])} & "
                           f"{ci(ag['human_human_same_cells']['kappa'])} & {pc(ph['LLM'])} / {pc(ph['AH'])} / {pc(ph['R2'])} \\\\")
            else:
                out.append(f"{SHORT[m]} & {label} & {cons} & -- & -- & -- & -- \\\\")
        u = s["unfiltered_majority25"]["agreement"]
        out.append(f"{SHORT[m]} & majority of 25 & {s['unfiltered_majority25']['n_cells_with_label']}/{blk['n_cells_evaluated']} & "
                   f"{ci(u['vs_human']['AH']['kappa'])} & {ci(u['vs_human']['R2']['kappa'])} & {ci(u['human_human_same_cells']['kappa'])} & "
                   f"{pc(u['pi_hat']['LLM'])} / {pc(u['pi_hat']['AH'])} / {pc(u['pi_hat']['R2'])} \\\\")
    for name, mname, label in (("RX_primary", "GLM + gpt-oss", "consensus, both"), ("RX_all", "all three", "consensus, $\\geq 2$ of 3")):
        c = res.get("cross_model", {}).get(name, {})
        if "coverage" in c and "agreement" in c and "vs_human" in c["agreement"]:
            ag = c["agreement"]
            vh, ph = ag["vs_human"], ag["pi_hat"]
            out.append(f"{mname} & {label} & {c['n_consensus']}/{c['n_denominator']} ({pc(c['coverage'])}) & {ci(vh['AH']['kappa'])} & "
                       f"{ci(vh['R2']['kappa'])} & {ci(ag['human_human_same_cells']['kappa'])} & {pc(ph['LLM'])} / {pc(ph['AH'])} / {pc(ph['R2'])} \\\\")
    return "\n".join(out) + "\n"


def appendix_rows(res: dict) -> str:
    """Compact Appendix A table: point estimates (no intervals) of the primary rule and the unfiltered majority per model, and the three-model consensus;
    the intervals are in the supplement (tier1_rows)."""
    out = ["Model, rule & Cons./eval. & $\\kappa$ AH & $\\kappa$ R2 & $\\kappa$ AH--R2 & $\\hat\\pi$ L/AH/R2 \\\\", "\\midrule"]

    def pi(ph):
        return f"{100 * ph['LLM']['est']:.0f}/{100 * ph['AH']['est']:.0f}/{100 * ph['R2']['est']:.0f}"

    for m, blk in res["models"].items():
        if blk.get("status") != "analysed":
            continue
        s = blk["S_final"]
        r = s["R25"]
        ag = r["agreement"]
        vh = ag["vs_human"]
        out.append(f"{SHORT[m]}, $\\geq 23/25$ & {r['n_consistent']}/{r['n_evaluated']} & {_f(vh['AH']['kappa']['est'], 2)} & {_f(vh['R2']['kappa']['est'], 2)} & "
                   f"{_f(ag['human_human_same_cells']['kappa']['est'], 2)} & {pi(ag['pi_hat'])} \\\\")
        u = s["unfiltered_majority25"]["agreement"]
        out.append(f"{SHORT[m]}, majority & {s['unfiltered_majority25']['n_cells_with_label']}/{blk['n_cells_evaluated']} & {_f(u['vs_human']['AH']['kappa']['est'], 2)} & "
                   f"{_f(u['vs_human']['R2']['kappa']['est'], 2)} & {_f(u['human_human_same_cells']['kappa']['est'], 2)} & {pi(u['pi_hat'])} \\\\")

    c = res["cross_model"]["RX_all"]
    ag = c["agreement"]
    out.append(f"All three, $\\geq 2$ & {c['n_consensus']}/{c['n_denominator']} & {_f(ag['vs_human']['AH']['kappa']['est'], 2)} & {_f(ag['vs_human']['R2']['kappa']['est'], 2)} & "
               f"{_f(ag['human_human_same_cells']['kappa']['est'], 2)} & {pi(ag['pi_hat'])} \\\\")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- supplement: personas
def personas_rows(res: dict) -> str:
    out = ["Model & Persona & Cells & $S{=}1$ (\\%) & $\\kappa$(AH) & $\\kappa$(R2) & $\\hat\\pi$ (\\%) & $\\alpha$, five seeds \\\\", "\\midrule"]
    for m, blk in res["models"].items():
        if blk.get("status") != "analysed":
            continue
        s = blk["S_final"]
        for p, v in s["personas"].items():
            out.append(f"{LONG[m]} & {p} & {v['n_cells_with_label']} & {pc(v['S1_share'])} & {ci(v['kappa_AH'])} & {ci(v['kappa_R2'])} & "
                       f"{pc(v['pi_hat'])} & {ci(s['alpha_seeds_per_persona'][p], 3)} \\\\")
        u = s["unfiltered_majority25"]
        out.append(f"{LONG[m]} & all 25 labels & {u['n_cells_with_label']} & {pc(u['agreement']['S1_share']['LLM'])} & "
                   f"{ci(u['agreement']['vs_human']['AH']['kappa'])} & {ci(u['agreement']['vs_human']['R2']['kappa'])} & "
                   f"{pc(u['agreement']['pi_hat']['LLM'])} & {ci(s['alpha_all_25_slots'], 3)} \\\\")
        if m != list(res["models"])[-1]:
            out.append("\\midrule")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- supplement: reliability side by side
def reliability_rows(adj: dict) -> str:
    r = adj["reliability"]
    out = ["Model & Cons./eval. & Label 1 among cons.\\ (\\%) & $\\kappa$(AH, R2), same cells & $\\kappa$(LLM, AH) & $\\kappa$(LLM, R2) & "
           "$\\alpha$, 25 labels & $\\alpha$ per persona \\\\", "\\midrule"]
    for m, pm in r["per_model"].items():
        al = [v["est"] for v in pm["alpha_seeds_per_persona"].values()]
        out.append(f"{LONG[m]} & {pm['n_consistent']}/{pm['n_evaluated']} & {pc(pm['S1_share_of_consistent_labels'])} & "
                   f"{ci(r['human_human']['per_model_consistent_cells'][m]['kappa'])} & {ci(pm['kappa_with_AH_on_consistent'])} & "
                   f"{ci(pm['kappa_with_R2_on_consistent'])} & {ci(pm['alpha_all_25_slots'])} & {min(al):.2f}--{max(al):.2f} \\\\")
    return "\n".join(out) + "\n"


def llmpairs_rows(adj: dict) -> str:
    r = adj["reliability"]["llm_llm_kappa"]
    out = ["Pair & Labels & Cells & $\\kappa$ & Agreement \\\\", "\\midrule"]
    nm = {"glm": "GLM", "gptoss": "gpt-oss", "qwen": "Qwen"}
    for pair, blk in r.items():
        a, b = pair.split("|")
        for key, lab in (("consistent_labels", "both consistent"), ("unfiltered_majority_of_25", "majority of 25")):
            e = blk[key]
            out.append(f"{nm[a]}, {nm[b]} & {lab} & {e['n_cells']} & {ci(e.get('kappa'))} & {ci(e.get('agreement'))} \\\\")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- supplement: adjudication
def adjudication_rows(adj: dict) -> str:
    out = ["Model & Human & Cons. & $D_{10}{+}D_{01}$ & $T_H$ on $D$ & $T_H$ on Ag11 & $T_H$ on Ag00 & $T_{\\mathrm{view}}$ on $D$ & "
           "Human right on $D$ & Reading \\\\", "\\midrule"]
    for k, v in adj["pairs"].items():
        m, h = k.split("|")
        g = v["groups"]
        out.append(f"{SHORT[m]} & {h} & {v['n_consistent']} & {v['counts']['D10']}+{v['counts']['D01']} & {gshare_ci(g['D']['T_H'])} & "
                   f"{gshare(g['Ag11']['T_H']) if g['Ag11']['n'] else '--'} & {gshare(g['Ag00']['T_H']) if g['Ag00']['n'] else '--'} & "
                   f"{gshare_ci(g['D']['T_view'])} & {gshare_ci(v['verdict_on_D']['human_right'])} & {adj['reading'][k]['reading']} \\\\")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- supplement: tiers without a human reference
def tiers_rows(res: dict) -> str:
    out = ["Tier and model & Cells (eval.) & R25 consistent (cov.\\ \\%) & Label 1 / 0 & 25/25 & $S{=}1$ of majority (\\%) \\\\", "\\midrule"]
    first = True
    for t, blk in res["extra"].items():
        if not first:
            out.append("\\midrule")
        first = False
        out.append(f"\\multicolumn{{6}}{{@{{}}l}}{{Tier {TIER_NAMES[t]}, {blk['n_cells']} cells}} \\\\")
        for m, mb in blk["models"].items():
            o = mb["overall"]
            r25 = o["R25"]
            out.append(f"\\quad {SHORT[m]} & {o['n_evaluated']}/{o['n_cells']} & {r25['n_consistent']} ({pc(r25['coverage'])}) & "
                       f"{r25['n_label1']} / {r25['n_label0']} & {o['R25U']['n_consistent']} & {pc(o['unfiltered_majority25']['S1_share'])} \\\\")
        c = blk.get("cross_model_primary")
        if c and "n_consensus" in c:
            out.append(f"\\quad GLM + gpt-oss, consensus & {c['n_denominator']} & {c['n_consensus']} ({pc(c['coverage'])}) & -- & -- & -- \\\\")
    return "\n".join(out) + "\n"


TABLES = {"tables_appendix.tex": ("res", appendix_rows), "tables_supp_tier1.tex": ("res", tier1_rows), "tables_supp_personas.tex": ("res", personas_rows),
          "tables_supp_reliability.tex": ("adj", reliability_rows), "tables_supp_llmpairs.tex": ("adj", llmpairs_rows),
          "tables_supp_adjudication.tex": ("adj", adjudication_rows), "tables_supp_tiers.tex": ("res", tiers_rows)}


def strip_comments(t: str) -> str:
    t = "\n".join(l for l in t.split("\n") if not l.lstrip().startswith("%"))
    return re.sub(r"(^|[^\\])%.*", r"\1", t, flags=re.M)


def main(argv) -> int:
    res = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    adj = json.loads((HERE / "results_adjudication.json").read_text(encoding="utf-8"))
    src = {"res": res, "adj": adj}
    check = "--check" in argv
    main_src = strip_comments((ACCESS / "main.tex").read_text(encoding="utf-8"))
    supp_src = strip_comments((ACCESS / "supplement.tex").read_text(encoding="utf-8"))
    bad = 0
    for name, (key, fn) in TABLES.items():
        body = fn(src[key])
        path = HERE / name
        if check:
            same = path.exists() and path.read_text(encoding="utf-8") == body
            haystack = main_src if name == "tables_appendix.tex" else supp_src
            missing = [row for row in body.split("\n") if row.strip() and row not in haystack]
            print(f"{name}: {'up to date' if same else 'DIFFERS from the JSON'}; rows missing from the manuscript source: {len(missing)}")
            for row in missing[:5]:
                print("   missing:", row[:120])
            bad += (not same) + len(missing)
        else:
            path.write_text(body, encoding="utf-8")
            print(f"wrote {name} ({len(body.splitlines())} lines)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
