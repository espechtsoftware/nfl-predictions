#!/usr/bin/env bash
set -euo pipefail

# Acquire five exact production-multinomial player-world blocks after ATLAS.
# Usage: cloud_atlas_money_worlds.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-atlas-current-money-worlds-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/atlas-money-world-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-15-atlas-current-money-transfer-protocol.md"
PROTOCOL_SHA=e575243db55f88ae3295d12c034c7921787b0a1de8d3ca5bef8c332395103eea
ATLAS_REPORT="$ROOT/reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1/report.json"
POLICY_SHA=b0aef9d0bec9d3fa1fdefeed237991c6e6089a967473973c0fd909a2daf563bb
IMAGE=${1:-}
CODE_SHA=${2:-}

[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: ATLAS money-transfer protocol differs" >&2; exit 2; }
[ -s "$ATLAS_REPORT" ] || {
  echo "ERROR: strict Phase S ATLAS harvest must complete first" >&2; exit 2; }
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS money-world run directory exists" >&2; exit 3; }

ACTUAL_POLICY_SHA=$("$ROOT/.venv/bin/python" - <<'PY'
from nfl_dfs.research.atlas_money_transfer import canonical_policy_receipt
print(canonical_policy_receipt()["engine_environment_sha256"])
PY
)
[ "$ACTUAL_POLICY_SHA" = "$POLICY_SHA" ] || {
  echo "ERROR: adopted money-policy environment differs" >&2; exit 2; }

for BLOCK in 0 1 2 3 4; do
  PANEL="20260815-atlas-money-worlds-r${BLOCK}-v1"
  EXISTING=$(bq query --project_id="$PROJECT" --use_legacy_sql=false \
    --format=csv \
    "SELECT COUNT(*) AS n FROM \`$PROJECT.nfl_predictions.replay_candidates_staging\` WHERE panel_run_id='$PANEL'" \
    | tail -1 | tr -d '[:space:]')
  [ "${EXISTING:-0}" = 0 ] || {
    echo "ERROR: create-only source panel $PANEL already has $EXISTING rows" >&2
    exit 3
  }
done

mkdir -p "$OUT/environment-receipts"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "policy_environment_sha256=$POLICY_SHA" \
  'source_panels=20260815-atlas-money-worlds-r0-v1,20260815-atlas-money-worlds-r1-v1,20260815-atlas-money-worlds-r2-v1,20260815-atlas-money-worlds-r3-v1,20260815-atlas-money-worlds-r4-v1' \
  'replicates=R0 R1 R2 R3 R4' 'seasons=2023 2024 2025' \
  'slates=54' 'seed_slate_artifacts=270' 'worlds_per_artifact=10000' \
  'uses_realized_outcomes=false' 'usage_allocation=production-multinomial' \
  'game_sim_usage=' 'dirichlet_k=' 'sis_asoe=' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

for BLOCK in 0 1 2 3 4; do
  PANEL="20260815-atlas-money-worlds-r${BLOCK}-v1"
  for SEASON in 2023 2024 2025; do
    RECEIPT="$OUT/environment-receipts/r${BLOCK}-${SEASON}.json"
    "$ROOT/.venv/bin/python" "$ROOT/scripts/atlas_money_world_env.py" \
      --block "$BLOCK" --season "$SEASON" --code-sha "$CODE_SHA" \
      --project "$PROJECT" --format json > "$RECEIPT"
    ENVS=$("$ROOT/.venv/bin/python" "$ROOT/scripts/atlas_money_world_env.py" \
      --block "$BLOCK" --season "$SEASON" --code-sha "$CODE_SHA" \
      --project "$PROJECT" --format gcloud)
    JOB="replay-atlasmoney-r${BLOCK}-${SEASON}"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --command nfl-dfs \
      --args "replay,--season,$SEASON,--contest,gpp,--entries,80" \
      --set-env-vars "^|^$ENVS" --service-account "$SERVICE_ACCOUNT" \
      --memory 16Gi --cpu 4 --tasks 1 --parallelism 1 --max-retries 0 \
      --task-timeout 4h --quiet
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [ -n "$EXEC" ] || {
      echo "ERROR: ATLAS money-world execution identity is missing" >&2
      exit 1
    }
    GOT=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
      --region "$REGION" \
      --format='value(spec.template.spec.containers[0].image)')
    [ "$GOT" = "$IMAGE" ] || {
      echo "ERROR: $EXEC image differs from manifest" >&2; exit 1; }
    printf '%s %s %s %s %s\n' \
      "$BLOCK" "$SEASON" "$PANEL" "$JOB" "$EXEC" \
      | tee -a "$OUT/executions.txt"
  done
done

echo "ATLAS_MONEY_WORLDS_LAUNCHED $RUN_ID"
