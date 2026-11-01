#!/usr/bin/env python3
"""Addendum 37 gateway probe: list models, then ONE call for gpt-5.6-luna with the smallest A_nohint job.  AI-generated; review before use."""
import json, os, sys, urllib.request, urllib.error, importlib.util
from pathlib import Path
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sg", HERE.parent / "study5_judge_panel" / "score_gateway.py")
sys.path.insert(0, str(HERE.parent / "study5_judge_panel"))
sg = importlib.util.module_from_spec(spec); spec.loader.exec_module(sg)
jobs = [json.loads(l) for l in open(HERE / "jobs_A.jsonl")]
job = min((j for j in jobs if j["study"] == "A_nohint"), key=lambda j: len(j["user"]))
lst = sg.http("/models", None, 20)
ids = [m.get("id") for m in (lst["payload"] or {}).get("data", [])] if lst["status"] == 200 else []
res = {"models_status": lst["status"], "luna_listed": "gpt-5.6-luna" in ids}
if res["luna_listed"]:
    for omit in (False, True):
        r = sg.http("/chat/completions", sg.body_for("gpt-5.6-luna", job, 1024, omit), 300)
        res.update(http_status=r["status"], omit_temperature=omit, err=r["text"][:150] if r["status"] != 200 else "")
        if r["status"] == 200:
            ch = r["payload"]["choices"][0]
            j, ev, ok, note, _ = sg.sj.parse_reply(ch["message"].get("content"))
            res.update(parsed_ok=ok, J=j)
            break
        if not (r["status"] == 400 and "temperature" in r["text"].lower()):
            break
(HERE / "probe_gateway.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res))
