#!/bin/bash
# Compare and harvest the K=1 Milly ownership fade arm.
# Usage: cloud_compare_k1_milly_ownership_panel.sh <IMAGE@sha256:...> <TREATMENT>
set -euo pipefail

IMG=${1:-}
TREATMENT=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SOURCE=20260808-e80-k1-c616390
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$TREATMENT"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2 ;; esac
case "$TREATMENT" in
  20260809-e80-k1-millyown-*) ;;
  *) echo "ABORT: invalid ownership treatment panel"; exit 2 ;;
esac
[ -d "$OUT" ] || { echo "ABORT: treatment directory absent"; exit 2; }
[ ! -s "$OUT/comparison_execution.txt" ] || {
  echo "ABORT: immutable comparison already recorded"; exit 2; }

JOB=compare-k1-milly-ownership
ARGS="scripts/compare_k1_milly_ownership_panel.py,$TREATMENT,--source,$SOURCE"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: comparator image mismatch"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/comparison_execution.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" = False ] && break
  sleep 30
done
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND jsonPayload.disposition:*" \
  --project "$PROJECT" --limit 10 --order asc \
  --format='json(jsonPayload)' > "$OUT/comparison_log.json"
grep -q '"disposition"' "$OUT/comparison_log.json" || {
  echo "ABORT: structured comparison report absent"; exit 1; }
"$ROOT/.venv/bin/python" - "$OUT/comparison_log.json" \
  "$OUT/ownership_comparison.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 1 or "jsonPayload" not in rows[0]:
    raise SystemExit(f"ABORT: expected one report, got {len(rows)}")
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(rows[0]["jsonPayload"], fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
echo "K1 Milly ownership comparison complete: $OUT/ownership_comparison.json"
