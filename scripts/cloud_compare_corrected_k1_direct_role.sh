#!/bin/bash
# Run and durably harvest the corrected direct K1+role union comparison.
# Usage: cloud_compare_corrected_k1_direct_role.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE=20260810-lockfix-e80-k1-8677d21
TREATMENT=20260810-lockfix-e80-k1-role12union-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$TREATMENT"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable comparator image required"; exit 2;; esac
[ -d "$OUT" ] || { echo "ABORT: panel directory absent: $OUT"; exit 2; }
EXEC_FILE="$OUT/comparison_execution.txt"
LOG_FILE="$OUT/comparison_log.json"
REPORT_FILE="$OUT/direct_role_comparison.json"
[ ! -s "$EXEC_FILE" ] || {
  echo "ABORT: immutable comparison execution already recorded"; exit 2; }

JOB=compare-corrected-k1-direct-role
ARGS="scripts/compare_corrected_k1_direct_role.py,$TREATMENT,--source,$SOURCE"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: comparator deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$EXEC_FILE"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  if [ "$STATE" = False ]; then
    echo "Comparator reported a mechanical failure; harvesting its report."
    break
  fi
  sleep 30
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND jsonPayload.disposition:*" \
  --project "$PROJECT" --limit 10 --order asc \
  --format='json(jsonPayload)' > "$LOG_FILE"
grep -q '"disposition"' "$LOG_FILE" || {
  echo "ABORT: structured direct-role comparison report absent"; exit 1; }
"$ROOT/.venv/bin/python" - "$LOG_FILE" "$REPORT_FILE" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 1 or "jsonPayload" not in rows[0]:
    raise SystemExit(f"ABORT: expected one structured report, got {len(rows)}")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(rows[0]["jsonPayload"], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
echo "Corrected direct-role comparison complete: $REPORT_FILE"

