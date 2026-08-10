#!/bin/bash
# Run and harvest the preregistered true-80 K=1 CE fixed-pool reranker.
# Usage: cloud_evaluate_k1_ce_reranker.sh <IMAGE@sha256:...> <RUN_ID>
set -euo pipefail

IMG=${1:-}
RUN_ID=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/reranker-runs/$RUN_ID"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2 ;; esac
case "$RUN_ID" in 20260810-k1ce-rerank-a1-*) ;; *) echo "ABORT: invalid run id"; exit 2 ;; esac
mkdir -p "$OUT"
[ ! -s "$OUT/execution.txt" ] || {
  echo "ABORT: immutable reranker execution already recorded"; exit 2; }

JOB=evaluate-k1-ce-reranker
ARGS="scripts/evaluate_k1_ce_reranker.py,--panel,20260809-e80-k1-ce12-c616390"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: reranker image mismatch"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: reranker execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

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
  --format='json(jsonPayload)' > "$OUT/log.json"
grep -q '"disposition"' "$OUT/log.json" || {
  echo "ABORT: structured reranker report absent"; exit 1; }
"$ROOT/.venv/bin/python" - "$OUT/log.json" "$OUT/report.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
if len(rows) != 1 or "jsonPayload" not in rows[0]:
    raise SystemExit(f"ABORT: expected one report, got {len(rows)}")
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(rows[0]["jsonPayload"], fh, indent=2, sort_keys=True)
    fh.write("\n")
PY
echo "K1 CE reranker evaluation complete: $OUT/report.json"
