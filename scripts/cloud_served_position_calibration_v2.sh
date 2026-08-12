#!/bin/bash
# Launch the repaired score-free served-position calibration after Tier 1.
# Usage: cloud_served_position_calibration_v2.sh <DIAGNOSTIC_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-served-position-calibration-v2-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/served-position-calibration-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-12-pit-clean-served-position-calibration.md"
SELECTION="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
CACHE_VALIDATION="$ROOT/reports/tabpfn-canonical-runs/20260811-tabpfn-canonical-pit-v2/validation.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable diagnostic image required"; exit 2;; esac
case "$CODE_SHA" in [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;; *) echo "ABORT: code SHA required"; exit 2;; esac
for path in "$PROTOCOL" "$SELECTION" "$CACHE_VALIDATION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || { echo "ABORT: immutable execution exists"; exit 2; }
BASE=$(awk -F= '$1=="selected_base" {print $2}' "$SELECTION")
PANEL=$(awk -F= '$1=="selected_panel" {print $2}' "$SELECTION")
case "$BASE" in k3) ENSEMBLE=3 ;; k1) ENSEMBLE=1 ;; *) echo "ABORT: invalid base"; exit 2;; esac
case "$PANEL" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid selected panel"; exit 2;; esac

"$ROOT/.venv/bin/python" - "$CACHE_VALIDATION" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "tabpfn-canonical-pit-cache-valid" or not report.get("passes"):
    raise SystemExit("ABORT: canonical PIT cache is invalid")
PY
COUNT=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
  "SELECT COUNT(DISTINCT CONCAT(CAST(season AS STRING), '-', CAST(week AS STRING))) AS n
   FROM \`$PROJECT.nfl_predictions.replay_candidates\`
   WHERE panel_run_id='$PANEL' AND research_eligible AND code_sha='a12ab31'" \
  | tail -1 | tr -d '[:space:]')
[ "$COUNT" = 107 ] || { echo "ABORT: selected panel has $COUNT accepted slates"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "selected_base=$BASE" "panel=$PANEL" "model_ensemble=$ENSEMBLE" \
  'tabpfn_marginal_table=tabpfn_projections_pit_v2' \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "tier1_selection_sha256=$(sha256sum "$SELECTION" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE_VALIDATION" | awk '{print $1}')" \
  'calibration_seasons=2019 2021 2022' 'evaluation_seasons=2023 2024 2025' \
  'position_factor_grid=0.750:0.005:1.500' 'n_sims=10000' 'seed=0' \
  > "$OUT/manifest.txt"
JOB=served-position-calibration-pit-v2
ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=$ENSEMBLE,SERVED_POSITION_CALIBRATION_PIT_V2=1,TABPFN_MARGINAL_TABLE=tabpfn_projections_pit_v2"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "served-position-calibration-diagnostic,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 --max-retries 0 \
  --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: deployed image mismatch"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "PIT_POSITION_CALIBRATION_LAUNCHED $EXEC"
