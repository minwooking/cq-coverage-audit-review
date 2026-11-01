#!/bin/bash
# Build the six pipeline variants (A-F) for one holdout domain, parameterised by
# paper/access2026/domains/<domain>.toml.
#
#   build_domain.sh <domain>              # DRY RUN (default): prints every command, runs nothing
#   build_domain.sh <domain> --execute    # runs them; needs an LLM endpoint (CHUNKTOGRAPH_LLM_*)
#
# The default is a dry run on purpose: the real run calls an LLM for hours. Review this script and
# the printed commands before using --execute (AI-generated tooling; test before relying on it).
# Brick's historical resume script (build_rest.sh) is untouched; this one is the domain-generic form
# of the same step list (README.md "Reproduction").
set -euo pipefail

DOMAIN="${1:-}"
MODE="${2:-}"
if [ -z "$DOMAIN" ] || { [ -n "$MODE" ] && [ "$MODE" != "--execute" ]; }; then
  echo "usage: $0 <domain> [--execute]" >&2; exit 2
fi
EXECUTE=0; [ "$MODE" = "--execute" ] && EXECUTE=1

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
cd "$REPO"
PY="${PYTHON:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY=python3

cfg () { "$PY" paper/access2026/harness/domains.py get "$DOMAIN" "$1"; }
IN="$(cfg corpus.path)"
W="$(cfg variants.work_dir)"
CQ="$(cfg variants.cq_json)"
OUT="$(cfg variants.dir)"
BUILDER="$(cfg corpus.builder)"

# Pipeline-side CQs only. Never the holdout bank (it would leak scored questions into construction).
case "$CQ" in *bank*) echo "refusing: variants.cq_json points at a CQ bank ($CQ)" >&2; exit 1;; esac

# The endpoint has no default: set CHUNKTOGRAPH_LLM_BASE_URL to your OpenAI-compatible server (a dry run
# prints "<unset>" and runs nothing; --execute refuses to start without it). The other defaults match the
# registered local setup; override via the environment.
export CHUNKTOGRAPH_LLM_BASE_URL="${CHUNKTOGRAPH_LLM_BASE_URL:-}"
if [ $EXECUTE = 1 ] && [ -z "$CHUNKTOGRAPH_LLM_BASE_URL" ]; then
  echo "set CHUNKTOGRAPH_LLM_BASE_URL to the OpenAI-compatible endpoint (for example http://HOST:PORT/v1)" >&2; exit 2
fi
export CHUNKTOGRAPH_LLM_MODEL="${CHUNKTOGRAPH_LLM_MODEL:-qwen-next-flash}"
export CHUNKTOGRAPH_LLM_API_KEY="${CHUNKTOGRAPH_LLM_API_KEY:-dummy}"
export CHUNKTOGRAPH_LLM_TIMEOUT="${CHUNKTOGRAPH_LLM_TIMEOUT:-900}"
export PYTHONMALLOC=malloc

echo "domain          : $DOMAIN"
echo "mode            : $([ $EXECUTE = 1 ] && echo EXECUTE || echo 'DRY RUN (nothing is executed)')"
echo "corpus          : $IN   (exists: $([ -e "$IN" ] && echo yes || echo NO))"
echo "work dir        : $W"
echo "package dir     : $OUT"
echo "pipeline CQs    : $CQ"
echo "LLM endpoint    : ${CHUNKTOGRAPH_LLM_BASE_URL:-<unset>}  model=$CHUNKTOGRAPH_LLM_MODEL  (key not printed)"
echo

run () {
  if [ $EXECUTE = 1 ]; then
    echo "+ $*"; "$@"
  else
    echo "[dry-run] $*"
  fi
}

if [ $EXECUTE = 1 ]; then
  [ -e "$IN" ] || { echo "missing corpus $IN; build it first (harness/$BUILDER.py)" >&2; exit 1; }
  mkdir -p "$W"
fi

run uv run chunktograph extract   --input "$IN" --output-dir "$W" --granularity leaf
run uv run chunktograph triples   --input "$IN" --output-dir "$W" --granularity leaf
run uv run chunktograph build     --input "$IN" --output-dir "$W" --granularity leaf
run uv run chunktograph split     --output-dir "$W"
run uv run chunktograph build-a   --input "$IN" --output-dir "$W" --granularity leaf
run uv run chunktograph build-c   --output-dir "$W" --cq "$CQ"
run uv run chunktograph refine-d  --output-dir "$W"
run uv run chunktograph build-d   --output-dir "$W" --cq "$CQ"
run uv run chunktograph select-standards --output-dir "$W" --cq "$CQ"
run uv run chunktograph build-e   --output-dir "$W" --cq "$CQ"
run uv run chunktograph build-f   --output-dir "$W" --cq "$CQ"
if [ "$DOMAIN" = "brick" ]; then
  run "$PY" paper/access2026/harness/variants/package_variants.py --domain "$DOMAIN"
else
  # Non-Brick packaging needs the model and host stated explicitly (no Brick provenance text is reused).
  run "$PY" paper/access2026/harness/variants/package_variants.py --domain "$DOMAIN" \
      --model "$CHUNKTOGRAPH_LLM_MODEL" --endpoint-host "$(echo "$CHUNKTOGRAPH_LLM_BASE_URL" | sed -E 's#^[a-z]+://([^/:]+).*#\1#')"
fi
echo
echo "done ($([ $EXECUTE = 1 ] && echo executed || echo 'dry run only'))"
