#!/bin/bash
# Run and durably harvest the corrected K=1 CE audit in Cloud Run.
# Usage: cloud_compare_k1_ce_panel.sh <COMPARATOR_IMAGE@sha256:...> <union|fixed>
set -euo pipefail

IMG=${1:-}
MODE=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE=20260808-e80-k1-c616390
UNION=20260809-e80-k1-ceunion-c616390
FIXED=20260809-e80-k1-ce12-c616390
ROOT=$(cd "$(dirname "$0")/.." && pwd)

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable comparator image required"; exit 2 ;; esac
case "$MODE" in
  union) TREATMENT=$UNION ;;
  fixed) TREATMENT=$FIXED ;;
  *) echo "ABORT: mode must be union or fixed"; exit 2 ;;
esac
OUT="$ROOT/reports/panel-runs/$TREATMENT"
[ -d "$OUT" ] || { echo "ABORT: panel directory absent: $OUT"; exit 2; }
[ ! -s "$OUT/comparison_execution.txt" ] || {
  echo "ABORT: immutable comparison execution already recorded"; exit 2; }

JOB=compare-k1-ce-panel
ARGS="scripts/compare_k1_ce_panel.py,$TREATMENT,--source,$SOURCE,--mode,$MODE"
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
printf '%s\n' "$EXEC" > "$OUT/comparison_execution.txt"

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
  --format='json(jsonPayload)' > "$OUT/comparison_log.json"
grep -q '"disposition"' "$OUT/comparison_log.json" || {
  echo "ABORT: structured CE comparison report absent"; exit 1; }
"$ROOT/.venv/bin/python" - "$OUT/comparison_log.json" \
  "$OUT/ce_comparison.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 1 or "jsonPayload" not in rows[0]:
    raise SystemExit(f"ABORT: expected one structured report, got {len(rows)}")
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(rows[0]["jsonPayload"], fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
echo "K1 CE comparison complete: $OUT/ce_comparison.json"
