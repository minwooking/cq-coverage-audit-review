#!/bin/bash
# Addendum 36 Step 2: build variants C, D, E, F for one domain on top of the domain's existing B-side work directory
# (copied from harness/study4_domains/<d>/work into <d>/work), with the pipeline's own commands (the C-F steps of
# harness/variants/build_domain.sh).  AI-generated; review before reuse.  Resumable: re-run until every step is OK.
#   CHUNKTOGRAPH_LLM_BASE_URL=<OpenAI-compatible endpoint ending in /v1> [S4_CONCURRENCY=3] ./build_f.sh <domain>
# Endpoint from the environment only; key = the pipeline's default unless CHUNKTOGRAPH_LLM_API_KEY is set.
# CQ file = the one the Brick build used (PLAN 36.5); the frozen banks are never given to construction.
set -u
D="${1:?usage: build_f.sh <domain>}"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO="$(cd -- "$HERE/../../../.." && pwd)"
cd "$REPO" || exit 1
: "${CHUNKTOGRAPH_LLM_BASE_URL:?set CHUNKTOGRAPH_LLM_BASE_URL}"
export CHUNKTOGRAPH_LLM_MODEL="${CHUNKTOGRAPH_LLM_MODEL:-Qwen/Qwen3-Next-80B-A3B-Instruct-FP8}"
export CHUNKTOGRAPH_LLM_TIMEOUT="${CHUNKTOGRAPH_LLM_TIMEOUT:-900}"
export S4_USAGE_LOG="$HERE/$D/build_f_usage.jsonl"
export PYTHONMALLOC=malloc
CQ="eval/competency_questions.json"
case "$CQ" in *bank*) echo "refusing: CQ file is a bank" >&2; exit 1;; esac
W="$HERE/$D/work"
LOG="$W/build_f.log"
PY="$REPO/.venv/bin/python"
echo "=== build C-F start $(date -u +%FT%TZ) HEAD=$(git rev-parse --short HEAD) model=$CHUNKTOGRAPH_LLM_MODEL conc=${S4_CONCURRENCY:-8} ===" >> "$LOG"
step () {
  local name="$1"; shift
  echo "[$(date -u +%H:%M:%S)] START $name" >> "$LOG"
  if "$PY" "$HERE/../study4_domains/run_pipeline.py" "$@" >> "$LOG" 2>&1; then
    echo "[$(date -u +%H:%M:%S)] OK    $name" >> "$LOG"
  else
    echo "[$(date -u +%H:%M:%S)] FAIL  $name" >> "$LOG"; exit 1
  fi
}
step build-c          build-c          --output-dir "$W" --cq "$CQ"
step refine-d         refine-d         --output-dir "$W"
step build-d          build-d          --output-dir "$W" --cq "$CQ"
step select-standards select-standards --output-dir "$W" --cq "$CQ"
step build-e          build-e          --output-dir "$W" --cq "$CQ"
step build-f          build-f          --output-dir "$W" --cq "$CQ"
echo "=== build C-F done $(date -u +%FT%TZ) ===" >> "$LOG"
ls -1 "$W"/ontology_F.ttl >> "$LOG" 2>&1
