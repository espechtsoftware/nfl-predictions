#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_exact_p_generator_census_source1.sh <preflight-2023|full> <image@sha256:...> <full-code-sha> <identity-generation> <identity-sha256>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-exact-p-generator-constraint-census-v1-source1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
IDENTITY_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-corrected-identities-v1/result.json
PARENT_PROTOCOL="$ROOT/reports/2026-08-15-exact-p-generator-constraint-census-protocol.md"
PARENT_SHA=bca1db394240359edd80db4767cafbe8d39d1a6769ba6a60e2b35ded18c0056e
REPAIR_PROTOCOL="$ROOT/reports/2026-08-15-exact-p-corrected-identity-source-repair.md"
REPAIR_SHA=e1cb1cd1a131bd0884da499048b23de3295d2f42079a615f4d40b8af7b9b3bab

MODE=${1:-}
IMAGE=${2:-}
CODE_SHA=${3:-}
IDENTITY_GENERATION=${4:-}
IDENTITY_SHA256=${5:-}
case "$MODE" in
  preflight-2023)
    JOB=exact-p-generator-census-preflight
    STAGE=preflight-2023
    OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-generator-constraint-census-v1/preflight-2023.json
    ;;
  full)
    JOB=exact-p-generator-constraint-census-v1
    STAGE=full-source1
    OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-generator-constraint-census-v1/result.json
    PREFLIGHT="$ROOT/reports/exact-p-generator-census-runs/$RUN_ID/preflight-2023/report.json"
    [ -s "$PREFLIGHT" ] || {
      echo "ERROR: strict exact-P census plumbing preflight is absent" >&2; exit 2; }
    "$ROOT/.venv/bin/python" - "$PREFLIGHT" "$IDENTITY_GENERATION" "$IDENTITY_SHA256" <<'PY'
import json
import sys

r = json.load(open(sys.argv[1], encoding="utf-8"))
s = r.get("corrected_identity_source", {})
if (
    r.get("mode") != "preflight-2023"
    or r.get("slates") != 18
    or r.get("scientific_result_licensed") is not False
    or str(s.get("generation")) != sys.argv[2]
    or s.get("sha256") != sys.argv[3]
):
    raise SystemExit("ERROR: exact-P census plumbing preflight differs")
PY
    ;;
  *) echo "ERROR: mode must be preflight-2023 or full" >&2; exit 2 ;;
esac
[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[[ "$IDENTITY_GENERATION" =~ ^[1-9][0-9]*$ ]] || {
  echo "ERROR: identity generation is required" >&2; exit 2; }
[[ "$IDENTITY_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR: identity SHA-256 is required" >&2; exit 2; }
[ "$(sha256sum "$PARENT_PROTOCOL" | awk '{print $1}')" = "$PARENT_SHA" ] || {
  echo "ERROR: exact-P parent protocol differs" >&2; exit 2; }
[ "$(sha256sum "$REPAIR_PROTOCOL" | awk '{print $1}')" = "$REPAIR_SHA" ] || {
  echo "ERROR: exact-P source repair protocol differs" >&2; exit 2; }
IDENTITY_LOCAL="$ROOT/reports/exact-p-corrected-identity-runs/20260815-exact-p-corrected-identities-v1/full"
[ -s "$IDENTITY_LOCAL/report.json" ] && [ -s "$IDENTITY_LOCAL/report.sha256" ] && [ -s "$IDENTITY_LOCAL/generation.txt" ] || {
  echo "ERROR: strict full corrected-identity harvest is absent" >&2; exit 2; }
[ "$(awk '{print $1}' "$IDENTITY_LOCAL/report.sha256")" = "$IDENTITY_SHA256" ] || {
  echo "ERROR: identity SHA differs from strict harvest" >&2; exit 2; }
[ "$(tr -d '[:space:]' < "$IDENTITY_LOCAL/generation.txt")" = "$IDENTITY_GENERATION" ] || {
  echo "ERROR: identity generation differs from strict harvest" >&2; exit 2; }
if gcloud storage objects describe "$OUTPUT_URI" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: create-only exact-P census output exists: $OUTPUT_URI" >&2; exit 3
fi
OUT="$ROOT/reports/exact-p-generator-census-runs/$RUN_ID/$STAGE"
[ ! -e "$OUT" ] || {
  echo "ERROR: exact-P census source1 run directory exists: $OUT" >&2; exit 3; }
mkdir -p "$OUT"
printf '%s\n' \
  'version=exact-p-generator-census-source1-v1' \
  "mode=$MODE" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_uri=$OUTPUT_URI" "identity_uri=$IDENTITY_URI" \
  "identity_generation=$IDENTITY_GENERATION" \
  "identity_sha256=$IDENTITY_SHA256" \
  "protocol_sha256=$PARENT_SHA" "repair_protocol_sha256=$REPAIR_SHA" \
  'manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'uses_candidate_or_lineup_scores=false' > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" --region "$REGION" --image "$IMAGE" \
  --command python \
  --args scripts/run_exact_p_generator_constraint_census.py,--mode,"$MODE",--output-uri,"$OUTPUT_URI",--identity-uri,"$IDENTITY_URI",--identity-generation,"$IDENTITY_GENERATION",--identity-sha256,"$IDENTITY_SHA256" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 2h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ERROR: exact-P census source1 execution missing" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
