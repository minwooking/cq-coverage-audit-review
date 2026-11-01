#!/bin/bash
# addendum 37 sub-studies B/C: limited (60,000-char) view, 188 cells; usage: run_L.sh glm|gptoss  (tunnels opened by the caller)
cd "$(dirname "$0")"  # endpoints come from S6_GLM, S6_GPTOSS, S6_QWEN35 (host:port of the local tunnel)
j=$1; ep=http://$S6_GLM/v1; [ "$j" = gptoss ] && ep=http://$S6_GPTOSS/v1
S6_ENDPOINT=$ep exec python3 run_study.py $j jobs_L.jsonl raw/L_$j.jsonl --studies L_limited > raw/L_$j.out 2>&1
