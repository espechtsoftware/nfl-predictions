#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_cbwu_oi_selector_stability.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=cbwu-oi-selector-stability-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-cbwu-oi-selector-stability-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/cbwu-oi-selector-stability-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-15-cbwu-oi-selector-stability-protocol.md"
PROTOCOL_SHA=81c8d0ff7750c7781e9c9181699b3bdf397d6161c8bf6e7a91025d233236cb01
CBWU_REPORT="$ROOT/reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json"
CBWU_SHA=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33
ATLAS_DIR="$ROOT/reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1"
OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-cbwu-oi-selector-stability-v1/result.json
FREQUENCY_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-cbwu-oi-selector-stability-v1/candidate-frequencies.json.gz

IMAGE=${1:-}
CODE_SHA=${2:-}
[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: selector-stability protocol differs" >&2; exit 2; }
[ "$(sha256sum "$CBWU_REPORT" | awk '{print $1}')" = "$CBWU_SHA" ] || {
  echo "ERROR: selector-stability source report differs" >&2; exit 2; }
[ -s "$ATLAS_DIR/report.json" ] && [ -s "$ATLAS_DIR/report.sha256" ] || {
  echo "ERROR: strict ATLAS harvest must precede selector stability" >&2
  exit 3
}
(cd "$ATLAS_DIR" && sha256sum -c report.sha256 >/dev/null) || {
  echo "ERROR: harvested ATLAS report hash differs" >&2; exit 3; }
for uri in "$OUTPUT_URI" "$FREQUENCY_URI"; do
  if gcloud storage objects describe "$uri" \
      --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: frozen create-only output exists: $uri" >&2
    exit 3
  fi
done
[ ! -e "$OUT" ] || {
  echo "ERROR: selector-stability run directory exists: $OUT" >&2; exit 3; }
mkdir -p "$OUT"
ATLAS_SHA=$(awk '{print $1}' "$ATLAS_DIR/report.sha256")
printf '%s\n' \
  'version=cbwu-oi-selector-stability-v1' \
  "image=$IMAGE" "code_sha=$CODE_SHA" "output_uri=$OUTPUT_URI" \
  "frequency_uri=$FREQUENCY_URI" "protocol_sha256=$PROTOCOL_SHA" \
  "cbwu_oi_scorefree_report_sha256=$CBWU_SHA" \
  "atlas_prerequisite_report_sha256=$ATLAS_SHA" \
  'source_panels=20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1' \
  'forensic_manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'uses_realized_outcomes=false' 'candidate_or_lineup_scores_read=false' \
  'selector_tuned=false' 'historical_arm_licensed=false' \
  'production_change_licensed=false' 'slates=54' \
  'seed_slate_artifacts=270' 'full_worlds=50000' \
  'bootstrap_resamples=32' 'bootstrap_worlds=10000' > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" --region "$REGION" --image "$IMAGE" \
  --command python \
  --args scripts/run_cbwu_oi_selector_stability.py,--output-uri,"$OUTPUT_URI",--frequency-uri,"$FREQUENCY_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 6h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: selector-stability execution is missing" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
