#!/bin/bash
# Run and harvest the one frozen summary/served-position calibration audit.
# Usage: bash scripts/cloud_served_position_calibration.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-served-position-calibration-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/served-position-calibration-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-served-position-calibration-refit.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol is missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable position-calibration execution already recorded"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "panel=$PANEL" \
  'calibration_seasons=2019 2021 2022' \
  'evaluation_seasons=2023 2024 2025' \
  'positions=QB RB WR TE' \
  'summary_refit=fit_widen_factors unchanged default grid' \
  'position_factor_grid=0.750:0.005:1.500' \
  'position_fit_objective=equal-season-q90-q95-q99-normalized-pinball' \
  'n_sims=10000' \
  'seed=0' \
  'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

JOB=served-position-calibration
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "served-position-calibration-diagnostic,--panel,$PANEL" \
  --set-env-vars "GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1" \
  --memory 16Gi --cpu 8 --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: position-calibration job deployed $DEPLOYED, expected $IMG"; exit 1; }

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
LOG_FILTER+='textPayload:"SERVED_POSITION_CALIBRATION_JSON="'
gcloud logging read "$LOG_FILTER" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "SERVED_POSITION_CALIBRATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(
        f"ABORT: expected one position-calibration report, got {len(payloads)}")
if not payloads[0].get("disposition") or not payloads[0].get("r2_final_served_fit"):
    raise SystemExit("ABORT: position-calibration report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Served-position calibration complete: $EXEC ($OUT/report.json)"
