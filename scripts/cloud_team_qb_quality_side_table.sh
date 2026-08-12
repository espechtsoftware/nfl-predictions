#!/bin/bash
# Build only the frozen team-QB-quality side table in an immutable image.
# Usage: cloud_team_qb_quality_side_table.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-team-qb-quality-side-table-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-team-qb-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-team-qb-quality-protocol.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable side-table execution already exists"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  'table=nfl_features.team_week_qb_quality' \
  'build_scope=017l_team_qb_quality.sql only' \
  'validation=independent strict-prior recomputation' \
  > "$OUT/manifest.txt"

JOB=build-team-qb-quality-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs --args build-team-qb-quality \
  --set-env-vars "GCP_PROJECT=$PROJECT,CODE_SHA=$CODE_SHA" \
  --memory 8Gi --cpu 4 --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: side-table job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: side-table execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TEAM_QB_QUALITY_SIDE_TABLE_LAUNCHED $EXEC"
