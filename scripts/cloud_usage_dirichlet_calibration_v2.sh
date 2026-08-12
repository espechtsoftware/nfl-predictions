#!/bin/bash
# Refit the frozen usage-concentration diagnostic on the reconciled PIT table.
# Usage: cloud_usage_dirichlet_calibration_v2.sh <GENERATION_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-data-fitted-usage-k-v2-pit-clean
FROZEN_DIGEST=sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/usage-dirichlet-calibration-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-data-fitted-dirichlet-usage.md"
RECONCILIATION="$ROOT/reports/pit-repair-runs/20260811-pit-clean-v2/reconciliation.json"
TIER1_SELECTION="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"

case "$IMG" in *@"$FROZEN_DIGEST") ;; *) echo "ABORT: wrong generation digest"; exit 2;; esac
for path in "$PROTOCOL" "$RECONCILIATION" "$TIER1_SELECTION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable PIT-clean usage calibration already recorded"; exit 2; }

# Bind the diagnostic to the exact reconciled table, not merely to whatever
# table happens to have the production name when the job starts.
"$ROOT/.venv/bin/python" - "$RECONCILIATION" <<'PY'
import json
import sys

from google.cloud import bigquery

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "pit-repair-warehouse-reconciled" or not report.get("passes"):
    raise SystemExit("ABORT: PIT reconciliation did not pass")
expected = report["tables"]["player_week_training"]["after"]
row = bigquery.Client(project="nfl-predictions-503414").query("""
    SELECT COUNT(*) AS row_count,
           COUNT(DISTINCT TO_JSON_STRING(STRUCT(gsis_id, season, week))) AS key_count,
           BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
    FROM `nfl-predictions-503414.nfl_features.player_week_training` t
""").to_dataframe().iloc[0]
actual = {
    "rows": int(row.row_count),
    "keys": int(row.key_count),
    "checksum": int(row.checksum),
}
if actual != expected:
    raise SystemExit(f"ABORT: repaired training table drifted: {actual} != {expected}")
PY

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  'code_sha=a12ab31' \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "reconciliation_sha256=$(sha256sum "$RECONCILIATION" | awk '{print $1}')" \
  "tier1_selection_sha256=$(sha256sum "$TIER1_SELECTION" | awk '{print $1}')" \
  'training_rows=102927' \
  'training_keys=102927' \
  'training_checksum=1904430067081090565' \
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

JOB=usage-dirichlet-calibration-pit-v2
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
echo "PIT_USAGE_CALIBRATION_LAUNCHED $EXEC"
