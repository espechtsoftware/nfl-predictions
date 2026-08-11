#!/bin/bash
# Run and harvest the one frozen final served-path calibration diagnostic.
# Usage: bash scripts/cloud_served_tail_calibration.sh <IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-served-tail-calibration-v1
PANEL=20260810-lockfix-e80-k1-8677d21
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/served-tail-calibration-runs/$RUN_ID"
ACCEPT="$ROOT/reports/panel-runs/$PANEL/acceptance_check.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ -s "$ACCEPT" ] && grep -q 'ACCEPTANCE PASSED' "$ACCEPT" || {
  echo "ABORT: corrected K1 check-only acceptance is not recorded"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable served-tail execution already recorded"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "panel=$PANEL" \
  'held_out=2023 2024 2025' \
  'positions=RB WR TE' \
  'expected_rows=13876' \
  'model_ensemble=1' \
  'n_sims=10000' \
  'game_sim_mode=possession' \
  'game_sim_team_factors=1' \
  'sim_widen_draws=fitted' \
  'tabpfn_marginals=1' \
  'emp_marginals_fallback=1' \
  'shape_mix=1' \
  'blend_model_weight=0.45' \
  > "$OUT/manifest.txt"

JOB=served-tail-calibration
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "served-tail-calibration-diagnostic,--panel,$PANEL" \
  --set-env-vars "GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1" \
  --memory 16Gi --cpu 8 --max-retries 0 --task-timeout 7200 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: served-tail job deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: served-tail execution id missing"; exit 1; }
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
LOG_FILTER+='textPayload:"SERVED_TAIL_CALIBRATION_JSON="'
gcloud logging read "$LOG_FILTER" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "SERVED_TAIL_CALIBRATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(
        f"ABORT: expected one served-tail report, got {len(payloads)}")
if not payloads[0].get("disposition") or not payloads[0].get("gate"):
    raise SystemExit("ABORT: served-tail report is incomplete")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Served-tail calibration complete: $EXEC ($OUT/report.json)"
