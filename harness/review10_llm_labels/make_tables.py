#!/usr/bin/env python3
"""LaTeX rows for a later appendix table of addendum 30, written from results.json.  AI-generated; review before use.

Writes tables.tex (a tabular body, no preamble).  `--check` compares the file on disk with what results.json would give
(exit 1 on a difference).  Numbers are copied, never recomputed.  The manuscript sources are not edited by this script.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b", "qwen": "Qwen3.8-Flash-Next$^{\\dagger}$"}


def ci(r, nd=2):
    if not r or r.get("est") is None:
        return "--"
    if r.get("lo") is None:
        return f"{r['est']:.{nd}f}"
    return f"{r['est']:.{nd}f} [{r['lo']:.{nd}f}, {r['hi']:.{nd}f}]"


def pc(r):
    if not r or r.get("est") is None:
        return "--"
    return f"{100 * r['est']:.1f}"


def rows(res: dict) -> str:
    out = []
    hdr = ("Model & rule & cons./eval. (cov.\\ \\%) & $\\kappa$(LLM, AH) & $\\kappa$(LLM, R2) & $\\kappa$(AH, R2), same cells & "
           "$\\hat\\pi$ LLM / AH / R2 (\\%) \\\\")
    out.append(hdr)
    out.append("\\midrule")
    for m, blk in res["models"].items():
        if blk.get("status") != "analysed":
            continue
        s = blk["S_final"]
        for rn, label in (("R25", "$\\geq 23/25$"), ("R25U", "25/25")):
            r = s[rn]
            ag = r["agreement"]
            cons = f"{r['n_consistent']}/{r['n_evaluated']} ({pc(r['coverage'])})"
            if "vs_human" in ag:
                vh = ag["vs_human"]
                ph = ag["pi_hat"]
                out.append(f"{NAMES[m]} & {label} & {cons} & {ci(vh['AH']['kappa'])} & {ci(vh['R2']['kappa'])} & "
                           f"{ci(ag['human_human_same_cells']['kappa'])} & {pc(ph['LLM'])} / {pc(ph['AH'])} / {pc(ph['R2'])} \\\\")
            else:
                out.append(f"{NAMES[m]} & {label} & {cons} & -- & -- & -- & -- \\\\")
        u = s["unfiltered_majority25"]["agreement"]
        out.append(f"{NAMES[m]} & majority of 25, no filter & {s['unfiltered_majority25']['n_cells_with_label']}/{blk['n_cells_evaluated']} & "
                   f"{ci(u['vs_human']['AH']['kappa'])} & {ci(u['vs_human']['R2']['kappa'])} & "
                   f"{ci(u['human_human_same_cells']['kappa'])} & {pc(u['pi_hat']['LLM'])} / {pc(u['pi_hat']['AH'])} / {pc(u['pi_hat']['R2'])} \\\\")
    for name, label in (("RX_primary", "consensus, both primary"), ("RX_all", "consensus, $\\geq 2$ of 3")):
        c = res.get("cross_model", {}).get(name, {})
        if "coverage" in c and "agreement" in c and "vs_human" in c["agreement"]:
            ag = c["agreement"]
            vh, ph = ag["vs_human"], ag["pi_hat"]
            out.append(f"{'+'.join(NAMES[m].split('$')[0] for m in c['models'])} & {label} & {c['n_consensus']}/{c['n_denominator']} ({pc(c['coverage'])}) & "
                       f"{ci(vh['AH']['kappa'])} & {ci(vh['R2']['kappa'])} & {ci(ag['human_human_same_cells']['kappa'])} & "
                       f"{pc(ph['LLM'])} / {pc(ph['AH'])} / {pc(ph['R2'])} \\\\")
    return "\n".join(out) + "\n"


def main(argv) -> int:
    res = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    body = rows(res)
    path = HERE / "tables.tex"
    if "--check" in argv:
        same = path.exists() and path.read_text(encoding="utf-8") == body
        print("tables.tex up to date" if same else "tables.tex DIFFERS from results.json")
        return 0 if same else 1
    path.write_text(body, encoding="utf-8")
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
