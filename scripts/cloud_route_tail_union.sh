#!/bin/bash
# Run and harvest the one frozen paid Route Share candidate union.
# Usage: bash scripts/cloud_route_tail_union.sh <IMAGE@sha256:...> \
#   <SOURCE_PANEL> <TREATMENT_PANEL> [SOURCE_TABLE] [TREATMENT_TABLE]
set -euo pipefail

IMG=${1:-}
SOURCE=${2:-}
TREATMENT=${3:-}
SOURCE_TABLE=${4:-replay_candidates}
TREATMENT_TABLE=${5:-replay_candidates_staging}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260810-fp-route-tail-union-v1
OUT="$ROOT/reports/route-tail-union-runs/$RUN_ID"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
for panel in "$SOURCE" "$TREATMENT"; do
  case "$panel" in *[!A-Za-z0-9_-]*|'') echo "ABORT: invalid panel id"; exit 2;; esac
  accept="$ROOT/reports/panel-runs/$panel/acceptance_check.txt"
  [ -s "$accept" ] && grep -q 'ACCEPTANCE PASSED' "$accept" || {
    echo "ABORT: check-only acceptance is not recorded: $panel"; exit 2; }
done
for table in "$SOURCE_TABLE" "$TREATMENT_TABLE"; do
  case "$table" in replay_candidates|replay_candidates_staging) ;;
    *) echo "ABORT: invalid candidate table"; exit 2;; esac
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable Route union execution already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'image=%s\nsource=%s\ntreatment=%s\nsource_table=%s\ntreatment_table=%s\nentries=80\nroute_candidates=12\ntreated_seasons=2024 2025\n' \
  "$IMG" "$SOURCE" "$TREATMENT" "$SOURCE_TABLE" "$TREATMENT_TABLE" \
  > "$OUT/manifest.txt"

JOB=fantasy-points-route-tail-union
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "route-tail-union,--source-panel,$SOURCE,--treatment-panel,$TREATMENT,--source-table,$SOURCE_TABLE,--treatment-table,$TREATMENT_TABLE" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 4Gi --cpu 2 \
  --max-retries 0 --task-timeout 1800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: Route union deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: Route union execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"ROUTE_TAIL_UNION_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "ROUTE_TAIL_UNION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one Route union report, got {len(payloads)}")
if not payloads[0].get("disposition"):
    raise SystemExit("ABORT: Route union report has no disposition")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Route tail-union confirmation complete: $EXEC ($OUT/report.json)"
