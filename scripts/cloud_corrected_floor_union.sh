#!/bin/bash
# Run and harvest the one frozen corrected role/no-floor candidate union.
# Usage: bash scripts/cloud_corrected_floor_union.sh <IMAGE@sha256:...> \
#   <SOURCE_PANEL> <NOFLOOR_PANEL> <INCUMBENT_PANEL> \
#   [SOURCE_TABLE] [NOFLOOR_TABLE] [INCUMBENT_TABLE]
set -euo pipefail

IMG=${1:-}
SOURCE=${2:-}
ADDON=${3:-}
INCUMBENT=${4:-}
SOURCE_TABLE=${5:-replay_candidates}
ADDON_TABLE=${6:-replay_candidates_staging}
INCUMBENT_TABLE=${7:-replay_candidates}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260810-corrected-role-nofloor-union
OUT="$ROOT/reports/floor-union-runs/$RUN_ID"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
for panel in "$SOURCE" "$ADDON" "$INCUMBENT"; do
  case "$panel" in *[!A-Za-z0-9_-]*|'') echo "ABORT: invalid panel id"; exit 2;; esac
  accept="$ROOT/reports/panel-runs/$panel/acceptance_check.txt"
  [ -s "$accept" ] && grep -q 'ACCEPTANCE PASSED' "$accept" || {
    echo "ABORT: accepted panel is not recorded: $panel"; exit 2; }
done
for table in "$SOURCE_TABLE" "$ADDON_TABLE" "$INCUMBENT_TABLE"; do
  case "$table" in replay_candidates|replay_candidates_staging) ;;
    *) echo "ABORT: invalid candidate table"; exit 2;; esac
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable floor-union execution already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'image=%s\nsource=%s\naddon=%s\nincumbent=%s\nsource_table=%s\naddon_table=%s\nincumbent_table=%s\nentries=80\n' \
  "$IMG" "$SOURCE" "$ADDON" "$INCUMBENT" "$SOURCE_TABLE" \
  "$ADDON_TABLE" "$INCUMBENT_TABLE" > "$OUT/manifest.txt"

JOB=corrected-floor-union
# gcloud's list parser rejects a repeated argument value.  The source is also
# the incumbent when no later arm has promoted, so pass the unchanged CLI
# invocation as one shell argument instead of losing that valid comparison.
CLI_ARGS="exec nfl-dfs corrected-floor-union --source-panel $SOURCE --addon-panel $ADDON --incumbent-panel $INCUMBENT --source-table $SOURCE_TABLE --addon-table $ADDON_TABLE --incumbent-table $INCUMBENT_TABLE"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command /bin/sh --args "-c,$CLI_ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 4Gi --cpu 2 \
  --max-retries 0 --task-timeout 1800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: union deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: union execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"FLOOR_UNION_CONFIRMATION_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "FLOOR_UNION_CONFIRMATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one floor-union report, got {len(payloads)}")
if not payloads[0].get("disposition"):
    raise SystemExit("ABORT: floor-union report has no disposition")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Corrected floor-union confirmation complete: $EXEC ($OUT/report.json)"
