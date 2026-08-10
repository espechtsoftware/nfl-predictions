#!/bin/bash
# Run and durably harvest the frozen lagged-NGS receiver-tail gate.
# Usage: bash scripts/cloud_ngs_receiver_tail.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260810-ngs-receiver-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/ngs-receiver-runs/$RUN_ID"
ACCEPT="$ROOT/reports/panel-runs/$PANEL/acceptance_check.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$ACCEPT" ] && grep -q 'ACCEPTANCE PASSED' "$ACCEPT" || {
  echo "ABORT: corrected K1 check-only acceptance is not recorded"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable NGS execution already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'run_id=%s\nimage=%s\npanel=%s\nhistory_seasons=2016-2025\nheld_out=2024 2025\n' \
  "$RUN_ID" "$IMG" "$PANEL" > "$OUT/manifest.txt"

JOB=ngs-receiver-tail-diagnostic
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "ngs-receiver-tail-diagnostic,--panel,$PANEL" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 4Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: NGS diagnostic deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: NGS execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"NGS_RECEIVER_TAIL_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "NGS_RECEIVER_TAIL_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one NGS report, got {len(payloads)}")
if not payloads[0].get("disposition"):
    raise SystemExit("ABORT: NGS report has no disposition")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "NGS receiver-tail diagnostic complete: $EXEC ($OUT/report.json)"
