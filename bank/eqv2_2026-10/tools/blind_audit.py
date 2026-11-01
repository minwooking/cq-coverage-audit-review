#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C2.)
"""Blind audit for the eqv2 drafting tools (addendum 47, 47.3).

B1 (static): AST scan of the tools in this directory.  Every string constant and
   os.path/join/Path concatenation is checked against blind_patterns.json.  The two
   POST-FREEZE tools eligibility.py and views.py are exempted BY NAME (they run only
   after the freeze, where touching those paths is the assigned job) -- the exemption is
   stated in the report, exactly as planned.
B2 (runtime): every blind_open_log_*.jsonl in logs/ contains zero forbidden paths.
B3 (transcript scan, framework only at C2): scan the tool-call arguments in the session
   transcripts that RAN the drafting tools, for forbidden patterns -- counts only, no
   content.  The target sessions are given as --session paths (not known at C2 time; a
   missing target reports "not verifiable", B1+B2 then stand alone).

The report always carries verbatim: "B1-B2 cannot prove what a human or agent saw."
The drafting session's frame design itself had read access to renderings; that limit is
stated, not excluded (47.3).

Usage:
    python3 blind_audit.py --static                     # B1 only, C2 gate
    python3 blind_audit.py --logs logs/ --out BLIND_AUDIT_b1.md [--session P ...]
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import common
from common import install_blind_hooks

HERE = common.TOOLS
# The two POST-FREEZE scripts (built later, run only after the bank freeze) are exempt
# from the static scan by design; the exemption is stated in the report (addendum 47, 47.3).
EXEMPT_BY_NAME = ("eligibility.py", "views.py")
LIMIT_SENTENCE = ("B1-B2 cannot prove what a human or agent saw. The session that designed "
                  "the frame had read access to the renderings and graphs, and recomputed "
                  "their hashes; that access is stated, not excluded (addendum 47, 47.3).")
# A string constant counts as a PATH reference (B1 violation) when it names a forbidden
# path (contains a separator).  Prose (docstrings, comments as strings) and exact matches
# of the shared blind_patterns.json list (the tool's own configuration) or the exemption
# file names are reported as informational, not violations.
def _severity(value: str, pattern: str, patterns: list[str]) -> str:
    """Classify one string constant that contains the pattern somewhere.
    exempt-listed -- the documented exemption file names;
    pattern-config -- the exact forbidden pattern string (the shared config's own strings);
    path-reference -- the pattern occurs glued to a path separator, i.e. a real path;
    prose-mention -- the word only appears inside ordinary text."""
    if value in EXEMPT_BY_NAME:
        return "exempt-listed"
    if value == pattern:
        return "pattern-config"
    i = 0
    while True:
        i = value.find(pattern, i)
        if i < 0:
            return "prose-mention"
        before = value[i - 1] if i else ""
        after = value[i + len(pattern)] if i + len(pattern) < len(value) else ""
        if before in "/\\" or after in "/\\":
            return "path-reference"
        i += len(pattern)


def scan_tool_static(path: Path, patterns: list[str]) -> list[dict]:
    """Violations: forbidden patterns glued to path separators, and any path-building
    call whose string parts mention a pattern. Everything else is informational."""
    hits: list[dict] = []
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for pat in patterns:
                if pat in node.value:
                    sev = _severity(node.value, pat, patterns)
                    hits.append({"line": node.lineno, "kind": "string-constant",
                                 "severity": "violation" if sev == "path-reference" else sev,
                                 "pattern": pat, "snippet": node.value[:60]})
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name in {"join", "Path", "fspath", "open", "read_text", "read_bytes"}:
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        for pat in patterns:
                            if pat in sub.value:
                                sev = _severity(sub.value, pat, patterns)
                                hits.append({"line": node.lineno, "kind": "path-join",
                                             "severity": "violation" if sev == "path-reference" else sev,
                                             "pattern": pat, "snippet": sub.value[:60]})
    return hits


def audit_static(tools_dir: Path) -> dict:
    patterns = json.loads((tools_dir / "blind_patterns.json").read_text(encoding="utf-8"))["patterns"]
    report: dict[str, list] = {}
    for f in sorted(tools_dir.glob("*.py")):
        if f.name in EXEMPT_BY_NAME:
            report[f.name] = [{"severity": "exempt",
                               "note": "exempt by name (runs only after the bank freeze)"}]
            continue
        report[f.name] = scan_tool_static(f, patterns)
    return report


def audit_runtime_logs(log_dir: Path) -> dict:
    patterns = json.loads((HERE / "blind_patterns.json").read_text(encoding="utf-8"))["patterns"]
    per: dict[str, int] = {}
    total_bad = 0
    for p in sorted(log_dir.glob("blind_open_log_*.jsonl")) if log_dir.exists() else []:
        bad = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if common.forbidden_hit(rec.get("path", "")):  # None: plain + boundary lists
                bad += 1
        per[p.name] = bad
        total_bad += bad
    return {"per_log": per, "total_forbidden_opens": total_bad}


def audit_transcripts(session_paths: list[Path]) -> dict:
    """B3: counts only. Each transcript (jsonl of a session) is scanned for forbidden
    patterns inside the tool-call *arguments* of Read/Grep/Glob/Bash-family calls; only
    the counts are returned -- content is never kept or copied."""
    patterns = json.loads((HERE / "blind_patterns.json").read_text(encoding="utf-8"))["patterns"]
    out: dict[str, dict] = {}
    for p in session_paths:
        if not p.exists():
            out[str(p.name)] = {"status": "not verifiable (transcript not found)"}
            continue
        counts = {pat: 0 for pat in patterns}
        n_calls = 0
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # walk only tool_use/tool_result blocks; count forbidden hits in their input
            stack = [rec]
            while stack:
                cur = stack.pop()
                if isinstance(cur, dict):
                    if cur.get("type") in {"tool_use", "tool-call", "toolCall"} and isinstance(cur.get("input"), dict):
                        n_calls += 1
                        blob = json.dumps(cur["input"])
                        for pat in patterns:
                            counts[pat] += blob.count(pat)
                    else:
                        stack.extend(cur.values())
                elif isinstance(cur, list):
                    stack.extend(cur)
        out[p.name] = {"status": "scanned", "tool_calls": n_calls,
                       "forbidden_pattern_counts": {k: v for k, v in counts.items() if v},
                       "total_forbidden_hits": sum(counts.values())}
    return out


def write_report(out_path: Path, static: dict, runtime: dict, transcripts: dict) -> None:
    lines = ["# BLIND AUDIT (eqv2)", "", "Plan-based, exploratory; addendum 47. AI-generated draft -- review before reliance.", "",
             "## B1 static AST scan of the tools", ""]
    ok_b1 = True
    for fname, hits in static.items():
        viol = [h for h in hits if isinstance(h, dict) and h.get("severity") == "violation"]
        info = [h for h in hits if isinstance(h, dict) and h.get("severity") != "violation"]
        if viol:
            ok_b1 = False
        lines.append(f"- `{fname}`: " + ("**" + str(len(viol)) + " violation(s)**" if viol else "clean")
                     + (f" ({len(info)} informational)" if info else ""))
        for h in viol:
            lines.append(f"    - line {h['line']} ({h['kind']}): pattern `{h['pattern']}` -- `{h['snippet']}`")
        for h in info:
            lines.append(f"    - line {h['line']} ({h['severity']}): pattern `{h['pattern']}`")
    lines += ["", "## B2 runtime open-log scan", ""]
    for name, bad in runtime["per_log"].items():
        lines.append(f"- `{name}`: {bad} forbidden open(s)")
    if not runtime["per_log"]:
        lines.append("- (no logs present yet)")
    ok_b2 = runtime["total_forbidden_opens"] == 0
    lines += ["", f"total forbidden opens: **{runtime['total_forbidden_opens']}**", "",
              "## B3 transcript scan", ""]
    if not transcripts:
        lines.append("- not run at C2; the target sessions are given by path when the drafting has happened")
    for name, d in transcripts.items():
        lines.append(f"- `{name}`: {d['status']}" + (f", tool calls {d['tool_calls']}, forbidden hits {d['total_forbidden_hits']}"
                                                     if d.get("status") == "scanned" else ""))
    if not transcripts:
        b3 = "NOT RUN"
    elif all(d.get("status") == "scanned" and d.get("total_forbidden_hits", 0) == 0 for d in transcripts.values()):
        b3 = "PASS"
    else:
        b3 = "CHECK"
    lines += ["", "## Limitations (verbatim)", "", LIMIT_SENTENCE, "",
              "## Verdict", "", f"B1 {'PASS' if ok_b1 else 'FAIL'}, "
              f"B2 {'PASS' if ok_b2 else 'FAIL'}, B3 {b3}", ""]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--static", action="store_true", help="run B1 only (C2 gate)")
    ap.add_argument("--logs", default=str(common.LOG_DIR))
    ap.add_argument("--out", default=None, help="report md path (default BLIND_AUDIT_b1.md)")
    ap.add_argument("--session", action="append", default=[], help="transcript path(s) for B3")
    ap.add_argument("--no-hook", action="store_true")
    args = ap.parse_args(argv)
    if not args.no_hook:
        install_blind_hooks("blind_open_log_b1.jsonl")
    static = audit_static(HERE)
    n = sum(1 for hits in static.values() for h in hits if isinstance(h, dict) and h.get("severity") == "violation")
    if args.static:
        print(json.dumps({"b1_violations": n,
                          "informational_mentions": sum(1 for hits in static.values() for h in hits
                                                        if isinstance(h, dict) and h.get("severity") != "violation"),
                          "files": {k: sum(1 for h in v if isinstance(h, dict) and h.get("severity") == "violation")
                                    for k, v in static.items()}}, ensure_ascii=False))
        return 1 if n else 0
    runtime = audit_runtime_logs(Path(args.logs))
    transcripts = audit_transcripts([Path(s) for s in args.session])
    out = Path(args.out or (common.BANK / "BLIND_AUDIT_b1.md"))
    write_report(out, static, runtime, transcripts)
    print(json.dumps({"b1_hits": n, "b2_forbidden_opens": runtime["total_forbidden_opens"],
                      "b3": {k: v["status"] for k, v in transcripts.items()}}, ensure_ascii=False))
    return 0 if (n == 0 and runtime["total_forbidden_opens"] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
