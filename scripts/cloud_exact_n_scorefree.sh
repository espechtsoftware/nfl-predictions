#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_exact_n_scorefree.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=exact-n-scorefree-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-exact-n-scorefree-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/exact-n-scorefree-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-15-exact-n-scorefree-protocol.md"
PROTOCOL_SHA=4918cdf96675a2b7608c5688e80fb826b61c443e9beb6bbb210f34a5b6319c11
AMENDMENT="$ROOT/reports/2026-08-15-exact-n-order-invariant-source-amendment.md"
AMENDMENT_SHA=934af9c612fe5399bbe2c6aa0061d258c2fd4691785ac678cb8f5d6d633203ce
CBWU_REPORT="$ROOT/reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json"
CBWU_SHA=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33
ATLAS_DIR="$ROOT/reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1"
OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-n-scorefree-v1/result.json

IMAGE=${1:-}
CODE_SHA=${2:-}
[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: exact-N protocol differs" >&2; exit 2; }
[ "$(sha256sum "$AMENDMENT" | awk '{print $1}')" = "$AMENDMENT_SHA" ] || {
  echo "ERROR: exact-N source amendment differs" >&2; exit 2; }
[ "$(sha256sum "$CBWU_REPORT" | awk '{print $1}')" = "$CBWU_SHA" ] || {
  echo "ERROR: exact-N CBWU-OI source report differs" >&2; exit 2; }
[ -s "$ATLAS_DIR/report.json" ] && [ -s "$ATLAS_DIR/report.sha256" ] || {
  echo "ERROR: strict ATLAS harvest must precede exact-N" >&2; exit 3; }
(cd "$ATLAS_DIR" && sha256sum -c report.sha256 >/dev/null) || {
  echo "ERROR: harvested ATLAS report hash differs" >&2; exit 3; }
if gcloud storage objects describe "$OUTPUT_URI" \
    --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: frozen create-only output exists: $OUTPUT_URI" >&2
  exit 3
fi
[ ! -e "$OUT" ] || {
  echo "ERROR: exact-N run directory exists: $OUT" >&2; exit 3; }
mkdir -p "$OUT"
ATLAS_SHA=$(awk '{print $1}' "$ATLAS_DIR/report.sha256")
printf '%s\n' \
  'version=exact-n-scorefree-v1' \
  "image=$IMAGE" "code_sha=$CODE_SHA" "output_uri=$OUTPUT_URI" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "source_amendment_sha256=$AMENDMENT_SHA" \
  "cbwu_oi_scorefree_report_sha256=$CBWU_SHA" \
  "atlas_prerequisite_report_sha256=$ATLAS_SHA" \
  'source_panels=20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1' \
  'forensic_manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'uses_realized_outcomes=false' 'candidate_or_lineup_scores_read=false' \
  'selector_tuned=false' 'historical_arm_licensed=false' \
  'production_change_licensed=false' 'slates=54' \
  'seed_slate_artifacts=270' 'full_worlds=50000' \
  'cardinalities=1,3,20,40' 'n80_parity=true' > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" --region "$REGION" --image "$IMAGE" \
  --command python \
  --args scripts/run_exact_n_scorefree.py,--output-uri,"$OUTPUT_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 16Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 4h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: exact-N execution is missing" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
