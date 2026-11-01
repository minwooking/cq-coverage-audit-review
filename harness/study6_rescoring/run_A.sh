#!/bin/bash
# addendum 37 sub-study A on the three shared-server judges (tunnels on local ports are opened by the caller)
cd "$(dirname "$0")"  # endpoints come from S6_GLM, S6_GPTOSS, S6_QWEN35 (host:port of the local tunnel)
S6_ENDPOINT=http://$S6_GLM/v1 python3 run_study.py glm jobs_A.jsonl raw/A_glm.jsonl --studies A_nohint,A_holdout > raw/A_glm.out 2>&1 &
S6_ENDPOINT=http://$S6_GPTOSS/v1 python3 run_study.py gptoss jobs_A.jsonl raw/A_gptoss.jsonl --studies A_nohint,A_holdout > raw/A_gptoss.out 2>&1 &
S6_ENDPOINT=http://$S6_QWEN35/v1 python3 run_study.py qwen35 jobs_A.jsonl raw/A_qwen35.jsonl --studies A_hint,A_nohint,A_holdout > raw/A_qwen35.out 2>&1 &
wait
