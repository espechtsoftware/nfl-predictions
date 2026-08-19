#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_production_law_dependence_remeasurement.sh <image@sha256:...> <code-sha> <build-id> <lease-receipt-sha256>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-production-law-dependence-remeasurement-v1
OUT="$ROOT/reports/production-law-dependence-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/production-law-dependence-runs/$RUN_ID
LOCK_ID=20260817-production-law-dependence-source-lock-v1
LOCK="$ROOT/reports/production-law-dependence-runs/$LOCK_ID"
LOCK_PREFIX=gs://nfl-predictions-503414-raw/research/production-law-dependence-runs/$LOCK_ID
COHERENT="$ROOT/reports/coherent-market-state-historical-score-runs/20260817-coherent-market-state-historical-score-v1"
PROTOCOL="$ROOT/reports/2026-08-17-production-law-dependence-remeasurement-protocol.md"
PROTOCOL_SHA=0ab5850416d856537b47bedaf23b3fdce827dcf2f99e35f589520a123b63919f
AMENDMENT="$ROOT/reports/2026-08-17-production-law-dependence-source-population-amendment.md"
AMENDMENT_SHA=16123cf7d96fb84a278fb29a86c99c1df56c8811a84ef69aa899a12305b25a3e
RUNNER="$ROOT/scripts/run_production_law_dependence_remeasurement.py"
FINISHER="$ROOT/scripts/cloud_finish_production_law_dependence_remeasurement.sh"
LEASE_TOOL="$ROOT/scripts/historical_outcome_lease.py"
LEASE_RECEIPT="$OUT/lease-receipt.json"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}
LEASE_SHA=${4:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || exit 2
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || exit 2
[[ "$LEASE_SHA" =~ ^[0-9a-f]{64}$ ]] || exit 2
[ -s "$LEASE_RECEIPT" ] && [ "$(sha256sum "$LEASE_RECEIPT" | awk '{print $1}')" = "$LEASE_SHA" ] || {
  echo "ERROR: production-law dependence historical lease differs" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || exit 2
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-17-production-law-dependence-remeasurement-protocol.md \
  reports/2026-08-17-production-law-dependence-source-population-amendment.md \
  src/nfl_dfs/analysis/production_law_dependence.py \
  src/nfl_dfs/analysis/final_served_dependence.py \
  scripts/run_production_law_dependence_source_lock.py \
  scripts/run_production_law_dependence_remeasurement.py \
  scripts/historical_outcome_lease.py \
  scripts/cloud_production_law_dependence_remeasurement.sh \
  scripts/cloud_finish_production_law_dependence_remeasurement.sh; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: production-law dependence built source differs: $RELATIVE" >&2; exit 2; }
done
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || exit 2
[ "$(sha256sum "$AMENDMENT" | awk '{print $1}')" = "$AMENDMENT_SHA" ] || exit 2
for NAME in source-lock.json object-metadata.json completion.txt; do
  [ -s "$LOCK/$NAME" ] || {
    echo "ERROR: production-law dependence source lock lacks $NAME" >&2; exit 2; }
done
for NAME in report.json execution.json object-metadata.json completion.txt; do
  [ -s "$COHERENT/$NAME" ] || {
    echo "ERROR: production-law dependence awaits coherent historical closure" >&2; exit 2; }
done

LOCK_GENERATION=$($ROOT/.venv/bin/python -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' \
  "$LOCK/object-metadata.json")
LOCK_SHA=$(sha256sum "$LOCK/source-lock.json" | awk '{print $1}')
"$ROOT/.venv/bin/python" - "$LOCK/completion.txt" "$COHERENT/report.json" \
  "$COHERENT/completion.txt" "$LEASE_RECEIPT" <<'PY'
import json, sys
lock = dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[1]) if "=" in line)
coherent = json.load(open(sys.argv[2], encoding="utf-8"))
completion = dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[3]) if "=" in line)
lease = json.load(open(sys.argv[4], encoding="utf-8"))
if lock.get("disposition") != "valid-production-law-source-lock" or \
        lock.get("uses_realized_outcomes") != "false" or \
        coherent.get("run_id") != "20260817-coherent-market-state-historical-score-v1" or \
        coherent.get("uses_realized_outcomes") is not True or \
        completion.get("uses_realized_outcomes") != "true" or \
        lease.get("lease", {}).get("run_id") != \
        "20260817-production-law-dependence-remeasurement-v1" or \
        lease.get("lease", {}).get("job") != "production-law-dependence-v1":
    raise SystemExit("ERROR: production-law dependence queue/lease differs")
PY

[ ! -e "$OUT/manifest.txt" ] || {
  echo "ERROR: immutable production-law dependence outcome run exists" >&2; exit 3; }
if gcloud storage objects describe "$PREFIX/report.json" --project "$PROJECT" \
    >/dev/null 2>&1; then
  echo "ERROR: immutable production-law dependence report exists" >&2; exit 3
fi
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json,sys
b=json.load(open(sys.argv[1],encoding="utf-8")); image,code=sys.argv[2:]
tag=f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:production-law-dependence-{code[:7]}"
steps={row.get("id"):row.get("status") for row in b.get("steps",[])}
if b.get("status")!="SUCCESS" or b.get("substitutions",{}).get("_IMAGE")!=tag or \
 not any(row.get("digest")==image.rsplit("@",1)[1] and row.get("name")==tag for row in b.get("results",{}).get("images",[])) or \
 steps.get("full-test-suite")!="SUCCESS" or steps.get("smoke-atlas-mvp-runner")!="SUCCESS":
 raise SystemExit("ERROR: production-law dependence validation build differs")
PY

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "source_population_amendment_sha256=$AMENDMENT_SHA" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  "lease_tool_sha256=$(sha256sum "$LEASE_TOOL" | awk '{print $1}')" \
  "lease_receipt_sha256=$LEASE_SHA" \
  "source_lock_uri=$LOCK_PREFIX/source-lock.json" \
  "source_lock_generation=$LOCK_GENERATION" "source_lock_sha256=$LOCK_SHA" \
  "coherent_report_sha256=$(sha256sum "$COHERENT/report.json" | awk '{print $1}')" \
  "coherent_completion_sha256=$(sha256sum "$COHERENT/completion.txt" | awk '{print $1}')" \
  'uses_realized_outcomes=true' 'candidate_or_lineup_scores_read=false' \
  'production_change_licensed=false' 'blocks=5' 'worlds_per_block=10000' \
  'aggregate_worlds=50000' 'candidate_rows=68199' \
  'candidate_union_rows=10729' 'eligible_rows=9469' \
  'slates=54' 'cpu=8' 'memory=32Gi' \
  'timeout_seconds=14400' 'max_retries=0' > "$OUT/manifest.txt"

JOB=production-law-dependence-v1
URI="$PREFIX/report.json"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --service-account "$SERVICE_ACCOUNT" \
  --command python \
  --args scripts/run_production_law_dependence_remeasurement.py,--source-lock-uri,"$LOCK_PREFIX/source-lock.json",--source-lock-generation,"$LOCK_GENERATION",--source-lock-sha256,"$LOCK_SHA",--output-uri,"$URI" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --cpu 8 --memory 32Gi --task-timeout 14400s --max-retries 0 \
  --quiet >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(metadata.name)')
[[ "$EXEC" == "$JOB-"* ]] || exit 2
printf '%s %s %s\n' "$JOB" "$EXEC" "$URI" > "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" > "$OUT/manifest.sha256"
sha256sum "$OUT/execution.txt" > "$OUT/execution.sha256"
echo "PRODUCTION_LAW_DEPENDENCE_REMEASUREMENT_LAUNCHED $EXEC"
