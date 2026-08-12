#!/bin/bash
# Run and durably harvest a frozen PIT-clean Tier-1 comparison.
# Usage: cloud_compare_pit_tier1.sh <IMAGE@sha256:...> <SOURCE> <TREATMENT> ensemble|direct-role a12ab31
set -euo pipefail

IMG=${1:-}
SOURCE=${2:-}
TREATMENT=${3:-}
MECHANISM=${4:-}
CODE_SHA=${5:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$TREATMENT"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$SOURCE$TREATMENT" in *[!A-Za-z0-9_-]*) echo "ABORT: invalid panel id"; exit 2;; esac
case "$MECHANISM" in ensemble|direct-role) ;; *) echo "ABORT: invalid mechanism"; exit 2;; esac
[ "$CODE_SHA" = a12ab31 ] || { echo "ABORT: frozen code is a12ab31"; exit 2; }
[ -d "$OUT" ] || { echo "ABORT: treatment directory missing"; exit 2; }
[ ! -e "$OUT/pit_tier1_comparison_execution.txt" ] || {
  echo "ABORT: immutable comparison already recorded"; exit 2; }

JOB="compare-pit-tier1-${MECHANISM}"
ARGS="scripts/compare_pit_tier1.py,$SOURCE,$TREATMENT,--mechanism,$MECHANISM,--code-sha,$CODE_SHA"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: comparator deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/pit_tier1_comparison_execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done
FILTER="resource.type=\"cloud_run_job\" AND "
FILTER+="labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND "
FILTER+='textPayload:"PIT_TIER1_JSON="'
gcloud logging read "$FILTER" --project "$PROJECT" --limit 5 --order asc \
  --format='value(textPayload)' > "$OUT/pit_tier1_comparison_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/pit_tier1_comparison_raw.txt" \
    "$OUT/pit_tier1_comparison.json" <<'PY'
import json
import sys

prefix = "PIT_TIER1_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one comparison report, got {len(payloads)}")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
if payloads[0].get("disposition") != "valid" or payloads[0].get("failures"):
    raise SystemExit("ABORT: Tier-1 comparison is mechanically invalid")
PY
[ "$STATE" = True ] || { echo "ABORT: comparator execution failed"; exit 1; }
echo "PIT_TIER1_COMPARISON_COMPLETE $OUT/pit_tier1_comparison.json"
