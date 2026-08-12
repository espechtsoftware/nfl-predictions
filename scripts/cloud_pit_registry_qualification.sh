#!/bin/bash
# Train the three isolated PIT-clean production/fallback registries.
# Usage: bash scripts/cloud_pit_registry_qualification.sh <IMAGE@sha256:...> a12ab31
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
PREFIX=models_pit_v2
RUN_ID=20260811-pit-clean-registry-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/pit-tier1-runs/$RUN_ID"
RECONCILIATION="$ROOT/reports/pit-repair-runs/20260811-pit-clean-v2/reconciliation.json"
CACHE_VALIDATION="$ROOT/reports/tabpfn-canonical-runs/20260811-tabpfn-canonical-pit-v2/validation.json"
PROTOCOL="$ROOT/reports/2026-08-11-pit-clean-tier1-revalidation.md"
ISO_WEEK=$(date -u +%G-W%V)

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
[ "$CODE_SHA" = a12ab31 ] || {
  echo "ABORT: Tier-1 generation is frozen to a12ab31"; exit 2; }
for path in "$RECONCILIATION" "$CACHE_VALIDATION" "$PROTOCOL"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable registry run already recorded"; exit 2; }
"$ROOT/.venv/bin/python" - "$RECONCILIATION" "$CACHE_VALIDATION" <<'PY'
import json
import sys

reconciliation = json.load(open(sys.argv[1], encoding="utf-8"))
cache = json.load(open(sys.argv[2], encoding="utf-8"))
if reconciliation.get("disposition") != "pit-repair-warehouse-reconciled" or \
        not reconciliation.get("passes"):
    raise SystemExit("ABORT: warehouse reconciliation did not pass")
if cache.get("disposition") != "tabpfn-canonical-pit-cache-valid" or \
        not cache.get("passes"):
    raise SystemExit("ABORT: canonical PIT cache validation did not pass")
PY

# A rerun into the same ISO week would overwrite an allegedly immutable
# qualification. The isolated root must be empty at launch.
EXISTING=$(gcloud storage ls \
  "gs://$PROJECT-raw/$PREFIX/**" 2>/dev/null | head -1 || true)
[ -z "$EXISTING" ] || {
  echo "ABORT: isolated registry prefix already contains objects"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "code_sha=$CODE_SHA" \
  "registry_prefix=$PREFIX" \
  "iso_week=$ISO_WEEK" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "reconciliation_sha256=$(sha256sum "$RECONCILIATION" | awk '{print $1}')" \
  "canonical_cache_validation_sha256=$(sha256sum "$CACHE_VALIDATION" | awk '{print $1}')" \
  'variants=canonical tail_k1 tail_k1_role' \
  'ensemble_sizes=3 1 1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch() {
  local suffix=$1 variant=$2 ensemble=$3 extras=$4
  local job="train-pit-v2-$suffix"
  local envs="GCP_PROJECT=$PROJECT,MODEL_REGISTRY_PREFIX=$PREFIX"
  envs="$envs,MODEL_REGISTRY_VARIANT=$variant,MODEL_ENSEMBLE=$ensemble"
  [ -z "$extras" ] || envs="$envs,EXTRA_FEATURES=$extras"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" --command nfl-dfs --args train \
    --set-env-vars "$envs" --memory 8Gi --cpu 4 --max-retries 0 \
    --task-timeout 3600 --service-account "$SERVICE_ACCOUNT" >/dev/null
  local deployed execution
  deployed=$(gcloud run jobs describe "$job" --project "$PROJECT" \
    --region "$REGION" \
    --format='value(spec.template.spec.template.spec.containers[0].image)')
  [ "$deployed" = "$IMG" ] || {
    echo "ABORT: $job deployed $deployed, expected $IMG"; exit 1; }
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [ -n "$execution" ] || { echo "ABORT: $job execution missing"; exit 1; }
  printf '%s %s %s %s\n' "$variant" "$ensemble" "$job" "$execution" \
    | tee -a "$OUT/executions.txt"
}

ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
launch k3 canonical 3 ""
launch k1 tail_k1 1 ""
launch role tail_k1_role 1 "$ROLE_FEATURES"
echo "PIT_REGISTRY_QUALIFICATION_LAUNCHED $OUT"
