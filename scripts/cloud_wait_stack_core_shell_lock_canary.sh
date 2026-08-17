#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-production-lock-v1
OUT="$ROOT/reports/stack-core-shell-lock-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
VALIDATOR="$ROOT/scripts/validate_stack_core_shell_lock_canary.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: lock canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 1 ] || {
  echo "ABORT: lock canary must precede the other 53 cells" >&2; exit 2; }
[ ! -e "$OUT/canary-completion.txt" ] && \
  [ ! -e "$OUT/canary-execution-metadata.json" ] && \
  [ ! -e "$OUT/canary-object-metadata.json" ] || {
  echo "ABORT: immutable lock canary receipt already exists" >&2; exit 3; }
read -r SEASON WEEK JOB EXEC URI < "$EXECUTIONS"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && \
  [ "$JOB" = stack-shell-lock-s2023-w1-v1 ] || {
  echo "ABORT: lock canary identity differs" >&2; exit 2; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  printf '%s STACK_CORE_SHELL_LOCK_CANARY execution=%s state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EXEC" "$STATE"
  [ "$STATE" != Unknown ] && break
  sleep 60
done
LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: lock canary job has an extra execution" >&2; exit 2; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json \
  > "$OUT/canary-execution-metadata.pending.json"
OBJECT_ARG=()
if gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
    > "$OUT/canary-object-metadata.pending.json" 2>/dev/null; then
  OBJECT_ARG=(--object "$OUT/canary-object-metadata.pending.json")
else
  rm -f "$OUT/canary-object-metadata.pending.json"
fi
set +e
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$VALIDATOR" \
  --manifest "$MANIFEST" --ledger "$EXECUTIONS" \
  --metadata "$OUT/canary-execution-metadata.pending.json" \
  "${OBJECT_ARG[@]}" --validator "$VALIDATOR" \
  --completion "$OUT/canary-completion.pending.txt"
RC=$?
set -e
mv "$OUT/canary-execution-metadata.pending.json" \
  "$OUT/canary-execution-metadata.json"
if [ -e "$OUT/canary-object-metadata.pending.json" ]; then
  mv "$OUT/canary-object-metadata.pending.json" \
    "$OUT/canary-object-metadata.json"
fi
mv "$OUT/canary-completion.pending.txt" "$OUT/canary-completion.txt"
sha256sum "$OUT/canary-execution-metadata.json" \
  "$OUT/canary-completion.txt" > "$OUT/canary.sha256"
if [ -e "$OUT/canary-object-metadata.json" ]; then
  sha256sum "$OUT/canary-object-metadata.json" >> "$OUT/canary.sha256"
fi
[ "$RC" -eq 0 ] || exit "$RC"
echo "STACK_CORE_SHELL_LOCK_REAL_PATH_CANARY_PASSED $EXEC"
