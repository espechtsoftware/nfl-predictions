#!/bin/bash
# Re-run only the repaired active-label exact-80 comparator after its original
# validator omitted three deterministic cache descendants.
# Usage: cloud_recompare_tabpfn_active_label_exact80_v2.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONTROL=20260812-pitclean-e80-selected-tabpfn-current-v2
TREATMENT=20260812-pitclean-e80-selected-tabpfn-active-v2
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
FINAL_REPORT="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v2-pit-clean/report.json"
CACHE_VALIDATION="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v2-pit-clean/validation.json"
OUT="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean"
INVALID_RAW="$OUT/comparison_raw.txt"
REPORT="$OUT/comparison.json"
AMENDMENT="$ROOT/reports/2026-08-12-active-label-comparator-invariant-repair.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
for path in "$TIER1" "$USAGE" "$FINAL_REPORT" "$CACHE_VALIDATION" \
    "$INVALID_RAW" "$AMENDMENT" \
    "$ROOT/reports/panel-runs/$CONTROL/acceptance_check.txt" \
    "$ROOT/reports/panel-runs/$TREATMENT/acceptance_check.txt"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$REPORT" ] || { echo "ABORT: immutable repaired report exists"; exit 2; }
[ ! -e "$OUT/selected_active_label.txt" ] || {
  echo "ABORT: immutable active-label selection exists"; exit 2; }
[ ! -e "$OUT/comparison_repair_execution.txt" ] || {
  echo "ABORT: repaired comparator execution already exists"; exit 2; }

"$ROOT/.venv/bin/python" - "$INVALID_RAW" <<'PY'
import json
import sys

prefix = "TABPFN_ACTIVE_LABEL_STAGE_B_V2_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line
]
if len(payloads) != 1:
    raise SystemExit("ABORT: original invalid comparator payload differs")
report = payloads[0]
expected = {
    "player snapshots differ in mismatch_rows",
    "player snapshot invariant values differ",
}
if report.get("disposition") != "invalid" or set(report.get("failures", ())) != expected:
    raise SystemExit("ABORT: original comparator did not fail only the repaired invariant")
if report.get("selected_panel") is not None or "decision" in report or \
        "weekly_maxima" in report or report.get("winner_position_contributions"):
    raise SystemExit("ABORT: original invalid comparator exposed a scoring decision")
PY

SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
ALLOCATION=$(awk -F= '$1=="allocation" {print $2}' "$USAGE")
SELECTED_K=$(awk -F= '$1=="selected_k" {print $2}' "$USAGE")
read -r CONTROL_B64 TREATMENT_B64 <<< "$("$ROOT/.venv/bin/python" - "$FINAL_REPORT" <<'PY'
import base64
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
if report.get("disposition") != "tabpfn-active-label-final-served-passes" or \
        not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: active-label final-served gate did not pass")
encoded = []
for arm in ("control", "treatment"):
    schedule = report.get(f"{arm}_schedule", {})
    specs = {}
    for season in ("2023", "2024", "2025"):
        factors = schedule.get(season, {}).get("factors", {})
        if set(factors) != {"QB", "RB", "TE", "WR"}:
            raise SystemExit(f"ABORT: {arm} {season} schedule differs")
        specs[season] = ",".join(
            f"{pos}:{float(factors[pos])!r}" for pos in ("QB", "RB", "TE", "WR"))
    encoded.append(base64.b64encode(json.dumps(specs, sort_keys=True).encode()).decode())
print(*encoded)
PY
)"
CACHE_SHA=$(sha256sum "$CACHE_VALIDATION" | awk '{print $1}')
FINAL_SHA=$(sha256sum "$FINAL_REPORT" | awk '{print $1}')

JOB=compare-tabpfn-active-label-exact80-v2-r1
ARGS="scripts/compare_tabpfn_active_label_lineup_v2.py,--historical-source,$SOURCE,--control,$CONTROL,--treatment,$TREATMENT,--code-sha,a12ab31,--role-selected,$ROLE_SELECTED,--allocation,$ALLOCATION,--selected-k,$SELECTED_K,--control-schedules-b64,$CONTROL_B64,--treatment-schedules-b64,$TREATMENT_B64,--cache-validation-sha,$CACHE_SHA,--final-served-sha,$FINAL_SHA"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command python --args "$ARGS" \
  --set-env-vars "GCP_PROJECT=$PROJECT" --memory 8Gi --cpu 2 \
  --max-retries 0 --task-timeout 3600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || { echo "ABORT: deployed image mismatch"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: comparator execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/comparison_repair_execution.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || break
  sleep 20
done
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_ACTIVE_LABEL_STAGE_B_V2_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/comparison_repair_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/comparison_repair_raw.txt" "$REPORT" <<'PY'
import json
import sys

prefix = "TABPFN_ACTIVE_LABEL_STAGE_B_V2_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line
]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one repaired comparison, got {len(payloads)}")
report = payloads[0]
expected = {
    "consensus_div", "mean_projection", "model_points_pre", "proj",
    "proj_tourney", "own_est", "proj_p10", "proj_p50", "proj_p90", "proj_std",
}
ignored = set(report.get("control_treatment_features", {}).get(
    "ignored_numeric_fields", ()))
if report.get("disposition") != "valid" or report.get("failures") or ignored != expected:
    raise SystemExit("ABORT: repaired active-label comparison is invalid")
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
[ "$STATE" = True ] || { echo "ABORT: repaired comparator execution failed"; exit 1; }

SELECTED=$("$ROOT/.venv/bin/python" - "$REPORT" "$CONTROL" "$TREATMENT" <<'PY'
import json
import sys
selected = json.load(open(sys.argv[1], encoding="utf-8")).get("selected_panel")
if selected not in {sys.argv[2], sys.argv[3]}:
    raise SystemExit("ABORT: active-label selection is not registered")
print(selected)
PY
)
if [ "$SELECTED" = "$TREATMENT" ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" promote 80 2 \
    "2023 2024 2025" season-varying-config
  LABEL_LAW=active-only
  CACHE_TABLE=tabpfn_active_label_treatment_v2
else
  LABEL_LAW=current
  CACHE_TABLE=tabpfn_projections_pit_v2
fi
printf '%s\n' \
  "historical_source=$SOURCE" "role_selected=$ROLE_SELECTED" \
  "allocation=$ALLOCATION" "selected_k=$SELECTED_K" \
  "label_law=$LABEL_LAW" "cache_table=$CACHE_TABLE" \
  "selected_eval_panel=$SELECTED" "comparison_execution=$EXEC" \
  "superseded_invalid_execution=$(head -1 "$OUT/comparison_execution.txt")" \
  "invalid_comparison_sha256=$(sha256sum "$INVALID_RAW" | awk '{print $1}')" \
  "amendment_sha256=$(sha256sum "$AMENDMENT" | awk '{print $1}')" \
  "cache_validation_sha256=$CACHE_SHA" "final_served_report_sha256=$FINAL_SHA" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_active_label.txt"
echo "PIT_ACTIVE_LABEL_EXACT80_REPAIRED_SELECTED $SELECTED label_law=$LABEL_LAW"
