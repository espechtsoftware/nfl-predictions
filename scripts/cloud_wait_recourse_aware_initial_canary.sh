#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-recourse-aware-initial-book-scorefree-v1
OUT="$ROOT/reports/recourse-aware-initial-book-runs/$RUN_ID"
PREFIX="gs://nfl-predictions-503414-raw/research/recourse-aware-initial-book-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
VALIDATOR="$ROOT/scripts/validate_recourse_aware_initial_canary.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] && [ -s "$VALIDATOR" ] || {
  echo "ABORT: recourse-aware canary launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 1 ] || {
  echo "ABORT: recourse-aware canary must precede the other 53 cells" >&2; exit 2; }
[ ! -e "$OUT/canary-completion.json" ] && \
  [ ! -e "$OUT/canary-execution-metadata.json" ] && \
  [ ! -e "$OUT/canary-object-metadata.json" ] && \
  [ ! -e "$OUT/canary-shard.json" ] || {
  echo "ABORT: immutable recourse-aware canary receipt exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC URI < "$EXECUTIONS"
[ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && \
  [ "$JOB" = recourse-initial-s2023-w1-v1 ] && \
  [ "$URI" = "$PREFIX/slate-2023-1.json" ] || {
  echo "ABORT: recourse-aware canary identity differs" >&2; exit 2; }

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  printf '%s RECOURSE_INITIAL_CANARY_STATUS execution=%s state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$EXEC" "$STATE"
  [ "$STATE" != Unknown ] && break
  sleep 60
done

LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: recourse-aware canary job has an extra execution" >&2; exit 2; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$OUT/canary-execution-metadata.pending.json"

if [ "$STATE" != True ]; then
  OBJECT_PRESENT=false
  if gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
      > "$OUT/canary-object-metadata.pending.json" 2>/dev/null; then
    OBJECT_PRESENT=true
  else
    rm -f "$OUT/canary-object-metadata.pending.json"
  fi
  "$ROOT/.venv/bin/python" - "$OUT/canary-execution-metadata.pending.json" \
    "$OUT/canary-completion.pending.json" "$EXEC" "$OBJECT_PRESENT" <<'PY'
from hashlib import sha256
import json, pathlib, sys
metadata_path, output_path = map(pathlib.Path, sys.argv[1:3])
metadata=json.loads(metadata_path.read_text())
status=metadata.get("status",{})
done=[row for row in status.get("conditions",[]) if row.get("type")=="Completed"]
if metadata.get("metadata",{}).get("name")!=sys.argv[3] or len(done)!=1 or done[0].get("status")!="False" or not status.get("completionTime"):
 raise SystemExit("ABORT: recourse-aware failed canary metadata differs")
payload={"version":"recourse-aware-initial-book-canary-validation-v1","status":False,"disposition":"actual-final-path-canary-terminal-failure","run_id":"20260817-recourse-aware-initial-book-scorefree-v1","cell":"2023-1","execution":sys.argv[3],"object_present":sys.argv[4]=="true","execution_metadata_sha256":sha256(metadata_path.read_bytes()).hexdigest(),"remaining_cells_released":False,"outcome_fields_inspected":False,"effect_fields_inspected":False}
output_path.write_text(json.dumps(payload,sort_keys=True,separators=(",",":"))+"\n")
PY
  mv "$OUT/canary-execution-metadata.pending.json" \
    "$OUT/canary-execution-metadata.json"
  [ ! -e "$OUT/canary-object-metadata.pending.json" ] || mv \
    "$OUT/canary-object-metadata.pending.json" \
    "$OUT/canary-object-metadata.json"
  mv "$OUT/canary-completion.pending.json" "$OUT/canary-completion.json"
  sha256sum "$OUT"/canary-*.json > "$OUT/canary.sha256"
  echo "RECOURSE_INITIAL_ACTUAL_CANARY_TERMINAL_FAILURE $EXEC" >&2
  exit 10
fi

INVENTORY=$(mktemp)
trap 'rm -f "$INVENTORY"' EXIT
gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
  > "$INVENTORY" 2>/dev/null || true
[ "$(sed '/^[[:space:]]*$/d' "$INVENTORY")" = "$URI" ] || {
  echo "ABORT: recourse-aware canary object inventory differs" >&2; exit 2; }
gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
  > "$OUT/canary-object-metadata.pending.json"
gcloud storage cp "$URI" "$OUT/canary-shard.pending.json" \
  --project "$PROJECT" >/dev/null
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" "$VALIDATOR" \
  --manifest "$MANIFEST" --execution-ledger "$EXECUTIONS" \
  --execution-metadata "$OUT/canary-execution-metadata.pending.json" \
  --object-metadata "$OUT/canary-object-metadata.pending.json" \
  --shard "$OUT/canary-shard.pending.json" \
  --output "$OUT/canary-completion.pending.json"

mv "$OUT/canary-execution-metadata.pending.json" \
  "$OUT/canary-execution-metadata.json"
mv "$OUT/canary-object-metadata.pending.json" \
  "$OUT/canary-object-metadata.json"
mv "$OUT/canary-shard.pending.json" "$OUT/canary-shard.json"
mv "$OUT/canary-completion.pending.json" "$OUT/canary-completion.json"
sha256sum "$OUT"/canary-*.json > "$OUT/canary.sha256"
trap - EXIT
rm -f "$INVENTORY"
echo "RECOURSE_INITIAL_ACTUAL_CANARY_PASSED $EXEC"
