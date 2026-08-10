#!/bin/bash
# Run and harvest the one frozen corrected-history extreme-selector test.
# Usage: bash scripts/cloud_corrected_extreme_selector.sh \
#   <IMAGE@sha256:...> <PANEL_RUN_ID> [replay_candidates|replay_candidates_staging]
set -euo pipefail

IMG=${1:-}
PANEL=${2:-}
TABLE=${3:-replay_candidates}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/selector-runs/$PANEL"
ACCEPT="$ROOT/reports/panel-runs/$PANEL/acceptance_check.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$PANEL" in *[!A-Za-z0-9_-]*|'') echo "ABORT: invalid panel id"; exit 2;; esac
case "$TABLE" in replay_candidates|replay_candidates_staging) ;;
  *) echo "ABORT: invalid candidate table"; exit 2;; esac
[ -s "$ACCEPT" ] && grep -q 'ACCEPTANCE PASSED' "$ACCEPT" || {
  echo "ABORT: accepted source panel is not recorded"; exit 2; }
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable selector execution already recorded"; exit 2; }
mkdir -p "$OUT"
printf 'image=%s\npanel=%s\ntable=%s\nselector=220-210-200-lex\nentries=80\n' \
  "$IMG" "$PANEL" "$TABLE" > "$OUT/manifest.txt"

JOB=corrected-extreme-selector
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "corrected-extreme-selector,--panel,$PANEL,--table,$TABLE" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 2Gi --cpu 1 \
  --max-retries 0 --task-timeout 1800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: selector deployed $DEPLOYED, expected $IMG"; exit 1; }

EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: selector execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done

gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"EXTREME_SELECTOR_CONFIRMATION_JSON=\"" \
  --project "$PROJECT" --limit 10 --order asc --format='value(textPayload)' \
  > "$OUT/raw_log.txt"
"$ROOT/.venv/bin/python" - "$OUT/raw_log.txt" "$OUT/report.json" <<'PY'
import json
import sys

prefix = "EXTREME_SELECTOR_CONFIRMATION_JSON="
payloads = []
for line in open(sys.argv[1], encoding="utf-8"):
    if prefix in line:
        payloads.append(json.loads(line.split(prefix, 1)[1]))
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one selector report, got {len(payloads)}")
if not payloads[0].get("disposition"):
    raise SystemExit("ABORT: selector report has no disposition")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(payloads[0], handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

[ "$STATE" = True ] || { echo "ABORT: $EXEC failed"; exit 1; }
echo "Corrected extreme-selector confirmation complete: $EXEC ($OUT/report.json)"
