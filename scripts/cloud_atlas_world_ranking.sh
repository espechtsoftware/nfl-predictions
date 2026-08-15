#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_world_ranking.sh <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-world-ranking-scorefree-v1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-atlas-world-ranking-scorefree-v1/result.json
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/atlas-world-ranking-runs/20260815-atlas-world-ranking-scorefree-v1-repair1"

IMAGE=${1:-}
CODE_SHA=${2:-}
if [[ ! "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]]; then
  echo "ERROR: immutable image digest is required" >&2
  exit 2
fi
if [[ ! "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: full code SHA is required" >&2
  exit 2
fi
if gcloud storage objects describe "$OUTPUT_URI" \
    --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: frozen create-only output already exists: $OUTPUT_URI" >&2
  exit 3
fi
[ ! -e "$OUT" ] || {
  echo "ERROR: frozen ATLAS run directory already exists: $OUT" >&2
  exit 3
}
mkdir -p "$OUT"
printf '%s\n' \
  'version=atlas-world-ranking-scorefree-v1' \
  "image=$IMAGE" "code_sha=$CODE_SHA" "output_uri=$OUTPUT_URI" \
  'source_panels=20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1' \
  'forensic_manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'uses_realized_outcomes=false' 'slates=54' 'seed_slate_artifacts=270' \
  'worlds_per_ranking=40' > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --image "$IMAGE" \
  --command python \
  --args scripts/run_atlas_world_ranking.py,--output-uri,"$OUTPUT_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" \
  --cpu 8 \
  --memory 32Gi \
  --tasks 1 \
  --parallelism 1 \
  --max-retries 0 \
  --task-timeout 6h \
  --quiet

EXEC=$(gcloud run jobs execute "$JOB" \
  --project "$PROJECT" \
  --region "$REGION" \
  --async \
  --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ERROR: ATLAS execution identity missing" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
