#!/bin/bash
# Validate, compare and mechanically select the PIT-clean fitted-usage arm.
# Usage: cloud_finish_usage_dirichlet_exact80_v2.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONTROL=20260812-pitclean-e80-selected-usage-control-v2
TREATMENT=20260812-pitclean-e80-selected-usage-fitted-v2
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
POSITION="$ROOT/reports/served-position-calibration-runs/20260812-served-position-stage-b-v2-pit-clean/selected_position.txt"
FIT_REPORT="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-data-fitted-usage-k-v2-pit-clean/report.json"
OUT="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean"
REPORT="$OUT/comparison.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
for path in "$TIER1" "$POSITION" "$FIT_REPORT"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_usage.txt" ] || { echo "ABORT: immutable usage selection exists"; exit 2; }
BASE=$(awk -F= '$1=="selected_base" {print $2}' "$TIER1")
HISTORICAL_SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
POSITION_SELECTED=$(awk -F= '$1=="position_selected" {print $2}' "$POSITION")
POSITION_SPEC=$(awk -F= '$1=="served_position_scales" {print $2}' "$POSITION")
if [ "$POSITION_SELECTED" = true ]; then
  EVALUATION_SOURCE=$(awk -F= '$1=="selected_eval_panel" {print $2}' "$POSITION")
else
  EVALUATION_SOURCE=$HISTORICAL_SOURCE
fi
FITTED_K=$("$ROOT/.venv/bin/python" - "$FIT_REPORT" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "data-fitted-usage-concentration-passes" or not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: repaired fitted-K diagnostic did not pass")
print(repr(float(report["fit"]["selected_k"])))
PY
)
POSITION_B64=$(printf '%s' "$POSITION_SPEC" | base64 -w0)

bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$CONTROL" check 80 2 "2023 2024 2025"
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" check 80 2 "2023 2024 2025"

mkdir -p "$OUT"
JOB=compare-usage-dirichlet-exact80-v2
ARGS="scripts/compare_usage_dirichlet_lineup_v2.py,--historical-source,$HISTORICAL_SOURCE,--evaluation-source,$EVALUATION_SOURCE,--control,$CONTROL,--treatment,$TREATMENT,--code-sha,a12ab31,--fitted-k,$FITTED_K,--base,$BASE,--role-selected,$ROLE_SELECTED,--position-spec-b64,$POSITION_B64"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: deployed image mismatch"; exit 1; }
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
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"USAGE_DIRICHLET_STAGE_B_V2_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/comparison_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/comparison_raw.txt" "$REPORT" <<'PY'
import json
import sys
prefix = "USAGE_DIRICHLET_STAGE_B_V2_JSON="
payloads = [json.loads(line.split(prefix, 1)[1]) for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one usage comparison, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: repaired usage comparison is invalid")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: comparator execution failed"; exit 1; }

SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$CONTROL" "$TREATMENT" <<'PY'
import json
import sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
selected = report.get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: usage selection is not a registered panel")
print(selected)
PY
)
if [ "$SELECTED" = "$TREATMENT" ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" promote 80 2 "2023 2024 2025"
  ALLOCATION=dirichlet
  SELECTED_K=$FITTED_K
else
  ALLOCATION=multinomial
  SELECTED_K=infinity
fi
printf '%s\n' \
  "selected_base=$BASE" "historical_source=$HISTORICAL_SOURCE" \
  "evaluation_source=$EVALUATION_SOURCE" "role_selected=$ROLE_SELECTED" \
  "position_selected=$POSITION_SELECTED" "served_position_scales=$POSITION_SPEC" \
  "allocation=$ALLOCATION" "selected_k=$SELECTED_K" \
  "selected_eval_panel=$SELECTED" "comparison_execution=$EXEC" \
  "fit_report_sha256=$(sha256sum "$FIT_REPORT" | awk '{print $1}')" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_usage.txt"
echo "PIT_USAGE_EXACT80_SELECTED $SELECTED allocation=$ALLOCATION k=$SELECTED_K"
