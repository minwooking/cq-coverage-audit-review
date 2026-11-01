# PROGRESS (addendum 35) -- one line per stage; times UTC
- 2026-10-20 plan committed (d3a3267). dcat: bank frozen + tag (916711c); ssn: bank frozen + tag (4d02755).
- dcat: corpus 426 chunks; extractor stages extract/triples/build/split done (B ready), build-a running sequentially (146 sections, ~3/min); ETA A ready ~09:55, judge ~+1h.
- ssn: build started in parallel with dcat build-a (domain order of judging unchanged: dcat first).
- dcat: A/B built (A: 1877 triples, B: 4271), judged by glm and gptoss (162 calls each, 0 invalid); results in results.json (not yet committed). ssn build-a running.
- ssn: A (2057 triples) / B (5922) built, judged by glm (249 calls, 0 invalid) and gptoss (249, 1 invalid: B/CQS32 repeat 1, malformed JSON at T=0 on retry, not imputed); done 09:20. prov: bank frozen (a5e7680), build running, ETA judges ~09:30.
- prov: A (2398) / B (6015) built, judged (231 calls each, 0 invalid) 09:25; results.json/REPORT_auto.md/tables.tex written for all three. F not built (needs pipeline-side CQs; not planned). Tunnels closed at end.
