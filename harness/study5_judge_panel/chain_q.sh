#!/bin/bash
# wait for the first pass of a judge to exit, then resume over the full job list (extra cells) and the F cells
J=$1; PID=$2; EP=$3
cd "$(dirname "$0")"; B=<repo>
tail --pid=$PID -f /dev/null
P5_ENDPOINT=$EP $B/.venv/bin/python score_panel.py $J jobs_ab.jsonl raw/ab_$J.jsonl --workers 3 >> raw/ab_$J.nohup 2>&1
P5_ENDPOINT=$EP $B/.venv/bin/python score_panel.py $J jobs_f.jsonl raw/f_$J.jsonl --workers 3 > raw/f_$J.nohup 2>&1
echo CHAIN_DONE $J
