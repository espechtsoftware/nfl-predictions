#!/bin/bash
# Run and harvest the one frozen outcome-blind usage concentration audit.
# Usage: bash scripts/cloud_usage_dirichlet_calibration.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-data-fitted-usage-k-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/usage-dirichlet-calibration-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-data-fitted-dirichlet-usage.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol is missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable usage calibration execution already recorded"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  'calibration_seasons=2021 2022' \
  'evaluation_seasons=2023 2024 2025' \
  'k_bounds=5:500' \
  'optimizer_x_tolerance=0.000001' \
  'minimum_observed_total=15' \
  'minimum_opportunity_coverage=0.95' \
  'model_ensemble=1' \
  'num_boost_round=400' \
  'extra_features=' \
  > "$OUT/manifest.txt"

JOB=usage-dirichlet-calibration
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args usage-dirichlet-calibration-diagnostic \
  --set-env-vars "GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1" \
  --memory 16Gi --cpu 8 --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: usage calibration deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

LOG_FILTER="resource.type=\"cloud_run_job\" AND "
LOG_FILTER+="labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND "
LOG_FILTER+='textPayload:"USAGE_DIRICHLET_CALIBRATION_JSON="'
gcloud logging read "$LOG_FILTER" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "USAGE_DIRICHLET_CALIBRATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(
        f"ABORT: expected one usage calibration report, got {len(payloads)}")
report = payloads[0]
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: usage calibration report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Usage concentration calibration complete: $EXEC ($OUT/report.json)"
