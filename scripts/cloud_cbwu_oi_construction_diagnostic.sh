#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_cbwu_oi_construction_diagnostic.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=cbwu-oi-construction-diagnostic-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-cbwu-oi-construction-diagnostic-v1
OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-cbwu-oi-construction-diagnostic-v1/result.json
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/cbwu-oi-construction-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-15-cbwu-oi-construction-diagnostic-protocol.md"
PROTOCOL_SHA=3b458263b165b380e6adf1efdf6ed08fb423c91d6988b5741aa32b11beafe1ec
CBWU_REPORT="$ROOT/reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json"
CBWU_SHA=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33
IDENTITY_DIR="$ROOT/reports/exact-p-corrected-identity-runs/20260815-exact-p-corrected-identities-v1/full"
IDENTITY_GENERATION=1786831245271593
IDENTITY_SHA=ff456093841266cba1b0293dd56b0e2d5089588a61518568706900617eff6ad1

IMAGE=${1:-}
CODE_SHA=${2:-}
[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: CBWU-OI construction protocol differs" >&2; exit 2; }
[ "$(sha256sum "$CBWU_REPORT" | awk '{print $1}')" = "$CBWU_SHA" ] || {
  echo "ERROR: CBWU-OI score-free source report differs" >&2; exit 2; }
[ -s "$IDENTITY_DIR/report.sha256" ] && \
    [ -s "$IDENTITY_DIR/generation.txt" ] || {
  echo "ERROR: exact-P corrected identity receipt is absent" >&2; exit 2; }
[ "$(awk '{print $1}' "$IDENTITY_DIR/report.sha256")" = "$IDENTITY_SHA" ] || {
  echo "ERROR: exact-P corrected identity SHA differs" >&2; exit 2; }
[ "$(tr -d '[:space:]' < "$IDENTITY_DIR/generation.txt")" = \
    "$IDENTITY_GENERATION" ] || {
  echo "ERROR: exact-P corrected identity generation differs" >&2; exit 2; }
if gcloud storage objects describe "$OUTPUT_URI" \
    --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: frozen create-only output already exists: $OUTPUT_URI" >&2
  exit 3
fi
[ ! -e "$OUT" ] || {
  echo "ERROR: frozen CBWU-OI construction run exists: $OUT" >&2; exit 3; }
mkdir -p "$OUT"
printf '%s\n' \
  'version=cbwu-oi-construction-diagnostic-v1' \
  "image=$IMAGE" "code_sha=$CODE_SHA" "output_uri=$OUTPUT_URI" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "cbwu_oi_scorefree_report_sha256=$CBWU_SHA" \
  "identity_generation=$IDENTITY_GENERATION" \
  "identity_sha256=$IDENTITY_SHA" \
  'source_panels=20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1' \
  'forensic_manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'uses_realized_candidate_scores=true' \
  'scores_cbwu_oi_selected_80=false' \
  'historical_arm_licensed=false' \
  'production_change_licensed=false' \
  'slates=54' 'seed_slate_artifacts=270' \
  'candidate_budget=canonical-r0-fixed-and-equal' > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" --region "$REGION" --image "$IMAGE" \
  --command python \
  --args scripts/run_cbwu_oi_construction_diagnostic.py,--output-uri,"$OUTPUT_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 6h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: CBWU-OI construction execution is missing" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
