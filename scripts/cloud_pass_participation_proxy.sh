#!/bin/bash
# Run and durably harvest the frozen pass-participation purchase gate.
# Usage: bash scripts/cloud_pass_participation_proxy.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260810-pass-participation-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/pass-participation-runs/$RUN_ID"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable proxy execution already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'run_id=%s\nimage=%s\npanel=%s\nseasons=2023 2024 2025\n' \
  "$RUN_ID" "$IMG" "20260809-e80-k1-ce12-c616390" > "$OUT/manifest.txt"

JOB=pass-participation-proxy
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "pass-participation-proxy,--panel,20260809-e80-k1-ce12-c616390" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 4Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: proxy deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: proxy execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"PASS_PARTICIPATION_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "PASS_PARTICIPATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one proxy report, got {len(payloads)}")
if not payloads[0].get("disposition"):
    raise SystemExit("ABORT: proxy report has no disposition")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Pass-participation proxy complete: $EXEC ($OUT/report.json)"
