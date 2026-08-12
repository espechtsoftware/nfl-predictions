#!/bin/bash
# Launch the frozen write-once PIT-clean canonical TabPFN cache.
# Usage: bash scripts/cloud_tabpfn_canonical_pit.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260811-tabpfn-canonical-pit-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-canonical-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-canonical-pit-clean-cache.md"
JOB=tabpfn-canonical-pit-v2
TABLE=tabpfn_projections_pit_v2

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol missing"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable canonical execution already recorded"; exit 2; }
if bq show --project_id="$PROJECT" --format=none \
    "$PROJECT:nfl_features.$TABLE" >/dev/null 2>&1; then
  echo "ABORT: write-once destination already exists: nfl_features.$TABLE"
  exit 2
fi

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "output_table=nfl_features.$TABLE" \
  'write_disposition=WRITE_EMPTY' \
  'target_seasons=2019 2021 2022 2023 2024 2025' \
  'context=all strictly earlier non-null labels, including inactive rows' \
  'context_max=28000' \
  'random_seed=7' \
  'n_estimators=4' \
  'tabpfn_version=2.2.1' \
  > "$OUT/manifest.txt"

gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" \
  --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_OUTPUT_TABLE=$TABLE,CODE_SHA=$CODE_SHA" \
  --memory 16Gi --cpu 4 --gpu 1 --gpu-type nvidia-l4 \
  --no-gpu-zonal-redundancy --max-retries 0 --task-timeout 3600 \
  --service-account "$SERVICE_ACCOUNT" >/dev/null
deployed=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$deployed" = "$IMG" ] || {
  echo "ABORT: $JOB deployed $deployed, expected $IMG"; exit 1; }
execution=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$execution" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s %s %s\n' "$JOB" "$execution" "$TABLE" \
  | tee "$OUT/execution.txt"

echo "TABPFN_CANONICAL_PIT_LAUNCHED $OUT"
