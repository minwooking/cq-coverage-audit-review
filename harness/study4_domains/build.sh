#!/bin/bash
# Addendum 35: build variants A and B for one domain with the pipeline's own commands (same sequence as
# harness/variants/build_domain.sh restricted to A and B).  AI-generated; review before reuse.  Resumable: re-run until all steps are OK.
#   CHUNKTOGRAPH_LLM_BASE_URL=<OpenAI-compatible endpoint ending in /v1> [S4_CONCURRENCY=4] ./build.sh <domain>
# The endpoint is read from the environment only; the key is the pipeline's own default unless CHUNKTOGRAPH_LLM_API_KEY is set.
set -u
D="${1:?usage: build.sh <domain>}"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO="$(cd -- "$HERE/../../../.." && pwd)"
cd "$REPO" || exit 1
: "${CHUNKTOGRAPH_LLM_BASE_URL:?set CHUNKTOGRAPH_LLM_BASE_URL}"
export CHUNKTOGRAPH_LLM_MODEL="${CHUNKTOGRAPH_LLM_MODEL:-Qwen/Qwen3-Next-80B-A3B-Instruct-FP8}"
export CHUNKTOGRAPH_LLM_TIMEOUT="${CHUNKTOGRAPH_LLM_TIMEOUT:-900}"
export S4_USAGE_LOG="$HERE/$D/build_usage.jsonl"
export PYTHONMALLOC=malloc
IN="$HERE/$D/corpus/corpus.json"
W="$HERE/$D/work"
LOG="$HERE/$D/work/build.log"
PY="$REPO/.venv/bin/python"
mkdir -p "$W"
echo "=== build A/B start $(date -u +%FT%TZ) HEAD=$(git rev-parse --short HEAD) model=$CHUNKTOGRAPH_LLM_MODEL conc=${S4_CONCURRENCY:-8} ===" >> "$LOG"
step () {
  local name="$1"; shift
  echo "[$(date -u +%H:%M:%S)] START $name" >> "$LOG"
  if "$PY" "$HERE/run_pipeline.py" "$@" >> "$LOG" 2>&1; then
    echo "[$(date -u +%H:%M:%S)] OK    $name" >> "$LOG"
  else
    echo "[$(date -u +%H:%M:%S)] FAIL  $name" >> "$LOG"; exit 1
  fi
}
step extract  extract  --input "$IN" --output-dir "$W" --granularity leaf
step triples  triples  --input "$IN" --output-dir "$W" --granularity leaf
step build    build    --input "$IN" --output-dir "$W" --granularity leaf
step split    split    --output-dir "$W"
step build-a  build-a  --input "$IN" --output-dir "$W" --granularity leaf
echo "=== build A/B done $(date -u +%FT%TZ) ===" >> "$LOG"
ls -1 "$W"/ontology_A.ttl "$W"/ontology_B.ttl >> "$LOG" 2>&1
