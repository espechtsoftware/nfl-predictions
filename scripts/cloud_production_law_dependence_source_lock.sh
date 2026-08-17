#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_production_law_dependence_source_lock.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-production-law-dependence-source-lock-v1
OUT="$ROOT/reports/production-law-dependence-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/production-law-dependence-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-17-production-law-dependence-remeasurement-protocol.md"
PROTOCOL_SHA=0ab5850416d856537b47bedaf23b3fdce827dcf2f99e35f589520a123b63919f
RUNNER="$ROOT/scripts/run_production_law_dependence_source_lock.py"
FINISHER="$ROOT/scripts/cloud_finish_production_law_dependence_source_lock.sh"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable production-law dependence image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full production-law dependence source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful production-law dependence build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || exit 2
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-17-production-law-dependence-remeasurement-protocol.md \
  src/nfl_dfs/analysis/production_law_dependence.py \
  src/nfl_dfs/analysis/final_served_dependence.py \
  scripts/run_production_law_dependence_source_lock.py \
  scripts/run_production_law_dependence_remeasurement.py \
  scripts/cloud_production_law_dependence_source_lock.sh \
  scripts/cloud_finish_production_law_dependence_source_lock.sh; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: production-law dependence built source differs: $RELATIVE" >&2
    exit 2
  }
done
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || exit 2

[ ! -e "$OUT" ] || {
  echo "ERROR: immutable production-law dependence source-lock run exists" >&2; exit 3; }
if gcloud storage objects describe "$PREFIX/source-lock.json" --project "$PROJECT" \
    >/dev/null 2>&1; then
  echo "ERROR: immutable production-law dependence source lock exists" >&2
  exit 3
fi
mkdir -p "$OUT"
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code = sys.argv[2:]
digest = image.rsplit("@", 1)[1]
tag = f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:production-law-dependence-{code[:7]}"
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag or \
        not any(row.get("digest") == digest and row.get("name") == tag
                for row in b.get("results", {}).get("images", [])) or \
        steps.get("full-test-suite") != "SUCCESS" or \
        steps.get("smoke-atlas-mvp-runner") != "SUCCESS":
    raise SystemExit("ERROR: production-law dependence validation build differs")
PY

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  'uses_realized_outcomes=false' 'actual_outcomes_queried=false' \
  'candidate_or_lineup_scores_read=false' 'production_change_licensed=false' \
  'artifacts=270' 'slates=54' 'cpu=2' 'memory=4Gi' \
  'timeout_seconds=3600' 'max_retries=0' > "$OUT/manifest.txt"

JOB=production-law-dep-source-lock-v1
URI="$PREFIX/source-lock.json"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --service-account "$SERVICE_ACCOUNT" \
  --command python \
  --args scripts/run_production_law_dependence_source_lock.py,--output-uri,"$URI" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --cpu 2 --memory 4Gi --task-timeout 3600s --max-retries 0 \
  --quiet >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(metadata.name)')
[[ "$EXEC" == "$JOB-"* ]] || {
  echo "ERROR: production-law dependence source-lock execution missing" >&2; exit 2; }
printf '%s %s %s\n' "$JOB" "$EXEC" "$URI" > "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" > "$OUT/manifest.sha256"
sha256sum "$OUT/execution.txt" > "$OUT/execution.sha256"
echo "PRODUCTION_LAW_DEPENDENCE_SOURCE_LOCK_LAUNCHED $EXEC"
