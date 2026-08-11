#!/bin/bash
# Run and harvest the one frozen independently calibrated Route Share audit.
# Usage: bash scripts/cloud_route_final_served_calibration.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-route-final-served-calibration-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/route-final-served-calibration-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-route-share-final-served-recalibration.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol is missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable Route recalibration execution already recorded"; exit 2; }

SOURCE_CHECK=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv --quiet "
SELECT COUNT(*) AS n_rows,
       COUNT(DISTINCT source_sha256) AS source_hashes,
       COUNT(DISTINCT gsis_id) AS resolved_players
FROM \`$PROJECT.nfl_raw.fantasy_points_route_share\`
WHERE resolution_status = 'resolved'
" | tail -n 1)
[ "$SOURCE_CHECK" = "26881,4,1029" ] || {
  echo "ABORT: imported Route source contract differs: $SOURCE_CHECK"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "panel=$PANEL" \
  'calibration_fold=2022' \
  'evaluation_folds=2023 2024 2025' \
  'positions=QB RB WR TE' \
  'primary_positions=RB WR TE' \
  'position_factor_grid=0.750:0.005:1.500' \
  'fit_objective=equal-season-q90-q95-q99-normalized-pinball' \
  'n_sims=10000' \
  'seed=0' \
  'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

JOB=route-final-served-calibration
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "route-final-served-calibration-diagnostic,--panel,$PANEL" \
  --set-env-vars "GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1" \
  --memory 16Gi --cpu 8 --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: Route recalibration deployed $DEPLOYED, expected $IMG"; exit 1; }

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
LOG_FILTER+='textPayload:"ROUTE_FINAL_SERVED_CALIBRATION_JSON="'
gcloud logging read "$LOG_FILTER" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "ROUTE_FINAL_SERVED_CALIBRATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(
        f"ABORT: expected one Route recalibration report, got {len(payloads)}")
report = payloads[0]
if not report.get("disposition") or not report.get("gate"):
    raise SystemExit("ABORT: Route recalibration report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Route final-served calibration complete: $EXEC ($OUT/report.json)"
