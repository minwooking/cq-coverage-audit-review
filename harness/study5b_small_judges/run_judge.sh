#!/bin/bash
# usage: run_judge.sh <judge> ; env P5_ENDPOINT, P5_KEY_FILE set by the caller (never committed)
J=$1; cd "$(dirname "$0")"; PY=<repo>/.venv/bin/python; S5=../study5_judge_panel
$PY score_ladder.py $J $S5/jobs_ab.jsonl raw/ab_$J.jsonl --workers 4 --max-model-len 131072 >> raw/ab_$J.nohup 2>&1
$PY score_ladder.py $J $S5/jobs_f.jsonl raw/f_$J.jsonl --workers 4 --max-model-len 131072 >> raw/f_$J.nohup 2>&1
echo DONE $J >> raw/done_$J.txt
