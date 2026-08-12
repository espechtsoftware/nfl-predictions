#!/bin/bash
# Validate and resolve the active-only fitted-K standing-law revalidation.
# Usage: cloud_finish_active_label_usage_revalidation.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONTROL=20260812-pitclean-e80-active-label-usage-multinomial-v1
TREATMENT=20260812-pitclean-e80-selected-tabpfn-active-v2
HISTORICAL_SOURCE=20260811-pitclean-e80-k1-role12union-a12ab31
PROTOCOL="$ROOT/reports/2026-08-12-active-label-usage-revalidation-protocol.md"
CONTROL_RUN="$ROOT/reports/panel-runs/$CONTROL"
OUT="$ROOT/reports/active-label-usage-revalidation-runs/20260812-active-label-usage-revalidation-v1"
REPORT="$OUT/comparison.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
for path in "$PROTOCOL" "$CONTROL_RUN/executions.txt" \
  "$CONTROL_RUN/revalidation_manifest.txt"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_usage_revalidation.txt" ] || {
  echo "ABORT: immutable usage revalidation selection exists"; exit 2; }

bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$CONTROL" \
  check 80 2 "2023 2024 2025" season-varying-config
grep -q 'ACCEPTANCE PASSED' \
  "$ROOT/reports/panel-runs/$TREATMENT/acceptance_check.txt" || {
  echo "ABORT: finite-K active-only treatment lacks prior acceptance"; exit 2; }

mkdir -p "$OUT"
JOB=compare-active-label-usage-revalidation-v1
ARGS="scripts/compare_active_label_usage_revalidation.py,--historical-source,$HISTORICAL_SOURCE,--control,$CONTROL,--treatment,$TREATMENT,--code-sha,a12ab31"
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
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/comparison_execution.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"ACTIVE_LABEL_USAGE_REVALIDATION_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/comparison_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/comparison_raw.txt" "$REPORT" <<'PY'
import json
import sys
prefix = "ACTIVE_LABEL_USAGE_REVALIDATION_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one comparison, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: active-only usage revalidation is invalid")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: comparator execution failed"; exit 1; }

SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$CONTROL" "$TREATMENT" <<'PY'
import json
import sys
selected = json.load(open(sys.argv[1], encoding="utf-8")).get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: selected usage arm is not registered")
print(selected)
PY
)
if [ "$SELECTED" = "$CONTROL" ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$CONTROL" \
    promote 80 2 "2023 2024 2025" season-varying-config
  ALLOCATION=multinomial
  SELECTED_K=infinity
else
  ALLOCATION=dirichlet
  SELECTED_K=28.154043586960896
fi
printf '%s\n' \
  "historical_source=$HISTORICAL_SOURCE" \
  "active_cache=tabpfn_active_label_treatment_v2" \
  "allocation=$ALLOCATION" "selected_k=$SELECTED_K" \
  "selected_eval_panel=$SELECTED" "comparison_execution=$EXEC" \
  "known_treatment_before_protocol=true" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_usage_revalidation.txt"
echo "ACTIVE_LABEL_USAGE_REVALIDATION_SELECTED $SELECTED allocation=$ALLOCATION"
