#!/usr/bin/env bash
set -euo pipefail

# Launch the frozen 2022-only SIS receiver-copula calibration.
# Usage: cloud_sis_receiver_copula_calibration.sh <image@sha256:...> <full-code-sha> [run-id] [job] [stage-dir]

IMAGE=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${3:-20260815-sis-receiver-copula-v1}
JOB=${4:-sis-receiver-copula-calibration-v1}
STAGE_DIR=${5:-calibration}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
[[ "$STAGE_DIR" =~ ^calibration[-a-z0-9]*$ ]] || {
  echo "ABORT: SIS calibration stage directory is invalid"; exit 2; }
OUT="$ROOT/reports/sis-receiver-copula-runs/$RUN_ID/$STAGE_DIR"
PANEL=20260811-pitclean-e80-k1-role12union-a12ab31
PARENT="$ROOT/reports/2026-08-15-sis-receiver-copula-protocol.md"
AMENDMENT="$ROOT/reports/2026-08-15-sis-receiver-copula-calibration-book-amendment.md"
PARENT_SHA=045a5a8e90bdbc95b5fdfa4ff29574f71fe03fcc69701d3c39dfc159c1395274
AMENDMENT_SHA=cb28791b593023ab6abc80becf94c901b80c095a268f154c77af15214dc6b500

case "$IMAGE" in *@sha256:*) ;; *) echo "ABORT: immutable SIS calibration image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full SIS calibration code SHA required"; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" 2>/dev/null || {
  echo "ABORT: SIS calibration code commit is unavailable"; exit 2; }
git -C "$ROOT" merge-base --is-ancestor 26e73c5 "$CODE_SHA" || {
  echo "ABORT: SIS calibration code is not descended from 26e73c5"; exit 2; }
[ "$(sha256sum "$PARENT" | awk '{print $1}')" = "$PARENT_SHA" ] || {
  echo "ABORT: SIS calibration parent protocol differs"; exit 2; }
[ "$(sha256sum "$AMENDMENT" | awk '{print $1}')" = "$AMENDMENT_SHA" ] || {
  echo "ABORT: SIS calibration amendment differs"; exit 2; }
[ ! -e "$OUT" ] || { echo "ABORT: immutable SIS calibration exists: $OUT"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "stage=calibration" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "stage_dir=$STAGE_DIR" \
  "panel=$PANEL" "parent_protocol_sha256=$PARENT_SHA" \
  "calibration_amendment_sha256=$AMENDMENT_SHA" \
  'calibration_season=2022' 'target_weeks=5 6 7 8 9 10 11 12 13 14 15 16 17 18' \
  'cache_table=tabpfn_projections_pit_v2' 'usage_law=production-multinomial' \
  'served_position_adjustment=none' 'model_market_blend=0.45/0.55' \
  'n_sims=10000' 'seed=0' 'heldout_outcomes_queried=false' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
ENVS="$ENVS,SIS_RECEIVER_COPULA_CALIBRATION_PANEL=$PANEL"
ENVS="$ENVS,SIS_RECEIVER_COPULA_CALIBRATION_RUN_ID=$RUN_ID"
ENVS="$ENVS,SIS_RECEIVER_COPULA_CALIBRATION_CODE_SHA=$CODE_SHA"
ENVS="$ENVS,SIS_RECEIVER_COPULA_REPORT_ROOT=/app"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command nfl-dfs \
  --args "sis-receiver-copula-calibration,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 --tasks 1 --parallelism 1 \
  --max-retries 0 --task-timeout 21600 --quiet >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMAGE" ] || {
  echo "ABORT: SIS calibration deployed $DEPLOYED, expected $IMAGE"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: SIS calibration execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "SIS_RECEIVER_COPULA_CALIBRATION_LAUNCHED $EXEC"
