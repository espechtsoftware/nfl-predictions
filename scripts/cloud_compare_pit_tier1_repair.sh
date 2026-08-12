#!/bin/bash
# Packaging-only repair for the first PIT Tier-1 comparator attempt.
# Usage: cloud_compare_pit_tier1_repair.sh <REPAIRED_AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
SOURCE=20260811-pitclean-e80-k3-a12ab31
TREATMENT=20260811-pitclean-e80-k1-a12ab31
OUT="$ROOT/reports/panel-runs/$TREATMENT"
FAILED=compare-pit-tier1-ensemble-x8nkn
FAILED_FILE="$OUT/pit_tier1_comparison_execution.txt"
REPAIR_FILE="$OUT/pit_tier1_comparison_repair_execution.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable repaired audit image required"; exit 2;; esac
[ "$(head -1 "$FAILED_FILE")" = "$FAILED" ] || {
  echo "ABORT: failed execution identity differs"; exit 2; }
[ ! -e "$OUT/pit_tier1_comparison.json" ] || { echo "ABORT: comparison report exists"; exit 2; }
[ ! -e "$REPAIR_FILE" ] || { echo "ABORT: repair execution exists"; exit 2; }
STATE=$(gcloud run jobs executions describe "$FAILED" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = False ] || { echo "ABORT: first attempt is not failed"; exit 2; }
LOGS=$(gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$FAILED\"" \
  --project "$PROJECT" --limit 100 --format='value(textPayload)')
case "$LOGS" in *"can't open file '/app/scripts/compare_pit_tier1.py'"*) ;; \
  *) echo "ABORT: first failure is not the registered packaging defect"; exit 2;; esac

JOB=compare-pit-tier1-ensemble-repair
ARGS="scripts/compare_pit_tier1.py,$SOURCE,$TREATMENT,--mechanism,ensemble,--code-sha,a12ab31"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: repaired image mismatch"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: repair execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$REPAIR_FILE"

while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"PIT_TIER1_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 5 --order asc \
  --format='value(textPayload)' > "$OUT/pit_tier1_comparison_repair_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/pit_tier1_comparison_repair_raw.txt" \
    "$OUT/pit_tier1_comparison.json" <<'PY'
import json
import sys

prefix = "PIT_TIER1_JSON="
payloads = [json.loads(line.split(prefix, 1)[1]) for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one repaired comparison, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: repaired comparison is mechanically invalid")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: repaired comparator failed"; exit 1; }
echo "PIT_TIER1_COMPARISON_REPAIRED $EXEC"
