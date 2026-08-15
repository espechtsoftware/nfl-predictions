#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_exact_p_corrected_identity_source.sh <preflight-2023|full> <image@sha256:...> <full-code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260815-exact-p-corrected-identities-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROTOCOL="$ROOT/reports/2026-08-15-exact-p-corrected-identity-source-repair.md"
PROTOCOL_SHA=e1cb1cd1a131bd0884da499048b23de3295d2f42079a615f4d40b8af7b9b3bab

MODE=${1:-}
IMAGE=${2:-}
CODE_SHA=${3:-}
case "$MODE" in
  preflight-2023)
    JOB=exact-p-corrected-ids-preflight
    STAGE=preflight-2023
    OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-corrected-identities-v1/preflight-2023.json
    ;;
  full)
    JOB=exact-p-corrected-identities-v1
    STAGE=full
    OUTPUT_URI=gs://nfl-predictions-503414-raw/research/final-forensic-runs/20260814-final-preseason-forensic-v1/post-forensic-addenda/20260815-exact-p-corrected-identities-v1/result.json
    PREFLIGHT="$ROOT/reports/exact-p-corrected-identity-runs/$RUN_ID/preflight-2023/report.json"
    [ -s "$PREFLIGHT" ] || {
      echo "ERROR: strict 2023 corrected-identity preflight is absent" >&2; exit 2; }
    "$ROOT/.venv/bin/python" - "$PREFLIGHT" <<'PY'
import json, sys
r=json.load(open(sys.argv[1], encoding="utf-8"))
if r.get("mode") != "preflight-2023" or r.get("slates") != 18 or \
        r.get("scientific_result_licensed") is not False or \
        r.get("identities_persisted") is not False:
    raise SystemExit("ERROR: strict 2023 corrected-identity preflight differs")
PY
    ;;
  *) echo "ERROR: mode must be preflight-2023 or full" >&2; exit 2 ;;
esac
[[ "$IMAGE" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable image digest is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full code SHA is required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ERROR: corrected-identity repair protocol differs" >&2; exit 2; }
if gcloud storage objects describe "$OUTPUT_URI" \
    --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: create-only corrected-identity output exists: $OUTPUT_URI" >&2
  exit 3
fi
OUT="$ROOT/reports/exact-p-corrected-identity-runs/$RUN_ID/$STAGE"
[ ! -e "$OUT" ] || {
  echo "ERROR: corrected-identity run directory exists: $OUT" >&2; exit 3; }
mkdir -p "$OUT"
printf '%s\n' \
  'version=exact-p-corrected-identities-v1' \
  "mode=$MODE" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_uri=$OUTPUT_URI" "repair_protocol_sha256=$PROTOCOL_SHA" \
  'manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'exact_stack_parent_generation=1786794534795445' \
  'exact_stack_parent_sha256=1d9e6b1f8d4e6174ae4aa717acf62fe657f0f3fbfd9271289a36b4a58664e7f3' \
  'scientific_result_licensed=false' > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" \
  --project "$PROJECT" --region "$REGION" --image "$IMAGE" \
  --command python \
  --args scripts/run_exact_p_corrected_identity_source.py,--mode,"$MODE",--output-uri,"$OUTPUT_URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 2h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ERROR: corrected-identity execution missing" >&2; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "$EXEC"
