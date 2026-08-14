#!/bin/bash
# Harvest and mechanically validate the frozen Route C/M GPU caches.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-tabpfn-route-channel-i1-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-route-channel-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: Route-channel manifest/executions missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable Route-channel validation already exists"; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 2 ] || {
  echo "ABORT: Route-channel needs exactly two executions"; exit 2; }
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' "$MANIFEST")
IMG=$(awk -F= '$1=="image" {print $2}' "$MANIFEST")
PRIOR=$(awk -F= '$1=="incumbent_validation" {print $2}' "$MANIFEST")

while read -r arm job execution table; do
  description=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" --format=json)
  state=$(printf '%s' "$description" | "$ROOT/.venv/bin/python" -c \
    'import json,sys; d=json.load(sys.stdin); print(next((c.get("status","") for c in d.get("status",{}).get("conditions",[]) if c.get("type")=="Completed"),""))')
  [ "$state" = True ] || {
    echo "ABORT: $arm execution $execution is not successful ($state)"; exit 1; }
  deployed=$(printf '%s' "$description" | "$ROOT/.venv/bin/python" -c \
    'import json,sys; print(json.load(sys.stdin)["spec"]["template"]["spec"]["containers"][0]["image"])')
  [ "$deployed" = "$IMG" ] || {
    echo "ABORT: $arm execution image differs"; exit 1; }
  filter="resource.type=\"cloud_run_job\" AND "
  filter+="labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND "
  filter+='textPayload:"TABPFN_ROUTE_CHANNEL_JSON="'
  gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
    --order asc --format='value(textPayload)' > "$OUT/${arm}_raw_log.txt"
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_route_channel_i1.py" \
  --control-log "$OUT/control_raw_log.txt" \
  --marginal-log "$OUT/marginal_raw_log.txt" \
  --incumbent-validation "$PRIOR" --code-sha "$CODE_SHA" \
  --output "$OUT/validation.json"

echo "TABPFN_ROUTE_CHANNEL_CACHE_COMPLETE $OUT/validation.json"
