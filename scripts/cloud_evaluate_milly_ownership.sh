#!/bin/bash
# Run and durably harvest the preregistered Milly ownership diagnostic.
# Usage: cloud_evaluate_milly_ownership.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
PANEL=20260808-e80-k1-c616390
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/ownership-runs/20260809-milly-k1-c616390"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2 ;; esac
[ ! -s "$OUT/execution.txt" ] || {
  echo "ABORT: immutable ownership execution already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'image=%s\nsource_panel=%s\nfolds=2023,2024,2025\n' \
  "$IMG" "$PANEL" > "$OUT/manifest.txt"

JOB=evaluate-milly-ownership
ARGS="scripts/evaluate_milly_ownership.py,--panel,$PANEL"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: evaluator deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: ownership execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  if [ "$STATE" = False ]; then
    echo "ABORT: ownership diagnostic failed: $EXEC"
    exit 1
  fi
  sleep 30
done
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND jsonPayload.disposition:*" \
  --project "$PROJECT" --limit 10 --order asc \
  --format='json(jsonPayload)' > "$OUT/report_log.json"
grep -q '"disposition"' "$OUT/report_log.json" || {
  echo "ABORT: structured ownership report absent"; exit 1; }
"$ROOT/.venv/bin/python" - "$OUT/report_log.json" "$OUT/report.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 1 or "jsonPayload" not in rows[0]:
    raise SystemExit(f"ABORT: expected one structured report, got {len(rows)}")
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(rows[0]["jsonPayload"], fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
echo "Milly ownership diagnostic complete: $OUT/report.json"
