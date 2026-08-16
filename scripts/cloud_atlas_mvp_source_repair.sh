#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-mvp-source-repair-r3-2025-v1
PANEL=20260816-atlas-mvp-repair-r3-2025-v1
JOB=replay-atlas-mvp-repair-r3-2025
OUT="$ROOT/reports/atlas-mvp-source-repair-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-source-repair-protocol.md"
PROTOCOL_SHA=a18c0f59cfccfccd073bdf5d9d24a0a8ad8015320421d40eb0fccc6a1a18d461
SOURCE_RECEIPT="$ROOT/reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/environment-receipts/r3-2025.json"
SOURCE_EXECUTION="$ROOT/reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/execution-metadata/replay-atlasmoney-r3-2025-htrch.json"
SOURCE_EXECUTION_SHA=60173988c785b88253052e40d73cfe396f9947c44f84f4bfe279be781db07ca9
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ad4604d86f1b1f7938136650f3d3940c9f1d6edd6a3427d618e6f943822602c8

[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS MVP source-repair protocol differs" >&2; exit 2; }
[ "$(sha256sum "$SOURCE_EXECUTION" | awk '{print $1}')" = "$SOURCE_EXECUTION_SHA" ] || {
  echo "ERROR: ATLAS MVP source execution receipt differs" >&2; exit 2; }
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS MVP repair run directory exists" >&2; exit 3; }
EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
  --format=csv \
  "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL'" \
  | tail -1 | tr -d '[:space:]')
[ "${EXISTING:-0}" = 0 ] || {
  echo "ERROR: create-only repair panel already has $EXISTING rows" >&2; exit 3; }
if bq show --project_id="$PROJECT" --format=none \
    nfl-predictions-503414:nfl_features.replay_lineups_atlas_mvp_repair_r3_2025 \
    >/dev/null 2>&1; then
  echo "ERROR: create-only repair lineup table already exists" >&2
  exit 3
fi

mkdir -p "$OUT"
"$ROOT/.venv/bin/python" "$ROOT/scripts/atlas_mvp_source_repair_env.py" \
  --source-receipt "$SOURCE_RECEIPT" --format json \
  > "$OUT/environment-receipt.json"
ENVS=$("$ROOT/.venv/bin/python" "$ROOT/scripts/atlas_mvp_source_repair_env.py" \
  --source-receipt "$SOURCE_RECEIPT" --format gcloud)
printf '%s\n' \
  "run_id=$RUN_ID" "panel=$PANEL" "job=$JOB" "image=$IMAGE" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "source_execution_sha256=$SOURCE_EXECUTION_SHA" \
  'source_execution=replay-atlasmoney-r3-2025-htrch' \
  'uses_realized_outcomes=false' \
  'permitted_environment_changes=PANEL_RUN_ID,REPLAY_LINEUPS_TABLE' \
  > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command nfl-dfs \
  --args "replay,--season,2025,--contest,gpp,--entries,80" \
  --set-env-vars "^|^$ENVS" --service-account "$SERVICE_ACCOUNT" \
  --memory 16Gi --cpu 4 --tasks 1 --parallelism 1 --max-retries 0 \
  --task-timeout 4h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS MVP repair execution identity is missing" >&2; exit 1; }
GOT=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(spec.template.spec.containers[0].image)')
[ "$GOT" = "$IMAGE" ] || {
  echo "ERROR: ATLAS MVP repair execution image differs" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "ATLAS_MVP_SOURCE_REPAIR_LAUNCHED $EXEC"
