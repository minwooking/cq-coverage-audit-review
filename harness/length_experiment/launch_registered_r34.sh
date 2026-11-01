#!/usr/bin/env bash
# Addendum 22: rescore the rendering-length conditions (limited, subgraph; variants A-F) with the
# REGISTERED holdout judge gemini-3.6-flash, then analyse (full views reused from the holdout run).
# AI-generated: review before use.  Idempotent: re-running resumes and skips already scored cells.
# The key is read silently into HOLDOUT_JUDGE_API_KEY (never echoed, never written, never a flag).
#   background (default):  bash harness/length_experiment/launch_registered_r34.sh
#   foreground + tee:      bash harness/length_experiment/launch_registered_r34.sh --fg
#   analysis only (no key): bash harness/length_experiment/launch_registered_r34.sh --analyze-only
set -u
set +x
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACCESS="$(cd "$HERE/../.." && pwd)"
OUTDIR="$HERE/registered_r34"
LOG="$OUTDIR/run_registered_r34.log"
TAG="access2026-addendum22-freeze"
mkdir -p "$OUTDIR"
cd "$ACCESS" || exit 1

export HOLDOUT_JUDGE_ENDPOINT='https://generativelanguage.googleapis.com/v1beta/openai'
export HOLDOUT_JUDGE_MODEL='gemini-3.6-flash'
export HOLDOUT_JUDGE_EXTRA_BODY='{"google":{"thinking_config":{"thinking_level":"minimal"}}}'
unset HOLDOUT_JUDGE_EXTRA_TOP_LEVEL_FIELDS

analyze() {
  python3 "$HERE/analyze_length.py" \
    --cells "$OUTDIR/cells_registered_r34.jsonl" \
    --holdout-cells "$ACCESS/harness/real_run/cells.jsonl" \
    --compare-cells "$HERE/cells_length.jsonl" \
    --out "$OUTDIR/results_registered_r34.json" \
    --report-ko "$OUTDIR/REPORT_registered_r34_ko.md" >/dev/null \
    && echo "analysis done: $OUTDIR/results_registered_r34.json , $OUTDIR/REPORT_registered_r34_ko.md"
}

judge() {
  git -C "$ACCESS" rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
    || { echo "tag $TAG missing: addendum 22 not frozen" >&2; return 1; }
  [ -n "${HOLDOUT_JUDGE_API_KEY:-}" ] || { echo "HOLDOUT_JUDGE_API_KEY is empty" >&2; return 1; }
  for pass in 1 2; do   # pass 2 re-sends only cells that failed in pass 1 (resume)
    echo "[$(date -u +%FT%TZ)] judge pass $pass"
    python3 "$HERE/run_length_judge.py" --design registered-all --variants A,B,C,D,E,F \
      --workers 3 --confirm-addendum22-frozen
  done
  analyze
}

case "${1:-}" in
  --analyze-only) analyze; exit $? ;;
  --run) judge; exit $? ;;
  --fg|"") ;;
  *) echo "usage: $0 [--fg|--analyze-only]" >&2; exit 2 ;;
esac

read -r -s -p "Gemini API key: " HOLDOUT_JUDGE_API_KEY; echo
export HOLDOUT_JUDGE_API_KEY
[ -n "$HOLDOUT_JUDGE_API_KEY" ] || { echo "no key entered" >&2; exit 1; }

if [ "${1:-}" = "--fg" ]; then
  judge 2>&1 | tee -a "$LOG"
else
  nohup bash "${BASH_SOURCE[0]}" --run >>"$LOG" 2>&1 &
  echo "started pid $! (key stays in the environment only). progress:"
  echo "  tail -f $LOG ; cat $OUTDIR/progress.log"
fi
unset HOLDOUT_JUDGE_API_KEY
