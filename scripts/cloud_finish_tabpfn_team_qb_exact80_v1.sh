#!/bin/bash
# Validate, compare and select the PIT-clean TabPFN team-QB exact-80 arm.
# Usage: cloud_finish_tabpfn_team_qb_exact80_v1.sh <AUDIT_IMAGE@sha256:...>
set -euo pipefail

IMG=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CONTROL=20260812-pitclean-e80-selected-tabpfn-team-qb-control-v1
TREATMENT=20260812-pitclean-e80-selected-tabpfn-team-qb-treatment-v1
TIER1="$ROOT/reports/pit-tier1-runs/20260811-pit-clean-role-v2/selected_tier1.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
SCHED="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"
FINAL="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-final-served-v1-pit-clean/report.json"
CACHE="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-v1-pit-clean/validation.json"
OUT="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean"
REPORT="$OUT/comparison.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
for path in "$TIER1" "$USAGE" "$SCHED" "$FINAL" "$CACHE"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/selected_team_qb.txt" ] || {
  echo "ABORT: immutable team-QB selection exists"; exit 2; }
SOURCE=$(awk -F= '$1=="selected_panel" {print $2}' "$TIER1")
ROLE_SELECTED=$(awk -F= '$1=="role_selected" {print $2}' "$TIER1")
ALLOCATION=$(awk -F= '$1=="allocation" {print $2}' "$USAGE")
SELECTED_K=$(awk -F= '$1=="selected_k" {print $2}' "$USAGE")
LABEL_LAW=$(awk -F= '$1=="label_law" {print $2}' "$SCHED")
FEATURE_CONTRACT=$(awk -F= '$1=="feature_contract" {print $2}' "$SCHED")
INHERITED_TABLE=$(awk -F= '$1=="cache_table" {print $2}' "$SCHED")
CODE_SHA=$(awk -F= '$1=="code_sha" {print $2}' \
  "$ROOT/reports/panel-runs/$CONTROL/manifest.txt")
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: control generation code SHA is invalid"; exit 2;;
esac

read -r CONTROL_B64 TREATMENT_B64 <<< "$(
  "$ROOT/.venv/bin/python" - "$FINAL" "$CACHE" <<'PY'
import base64
import json
import sys

report = json.load(open(sys.argv[1], encoding="utf-8"))
cache = json.load(open(sys.argv[2], encoding="utf-8"))
if report.get("disposition") != "tabpfn-team-qb-final-served-passes" or \
        not report.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: team-QB final-served gate did not pass")
if cache.get("disposition") != "tabpfn-team-qb-caches-valid" or \
        not cache.get("passes") or \
        not cache.get("control_reproduction", {}).get("passes"):
    raise SystemExit("ABORT: team-QB cache validation did not pass")
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
    encoded.append(base64.b64encode(
        json.dumps(specs, sort_keys=True).encode()).decode())
print(*encoded)
PY
)"
CACHE_SHA=$(sha256sum "$CACHE" | awk '{print $1}')
FINAL_SHA=$(sha256sum "$FINAL" | awk '{print $1}')

bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$CONTROL" check 80 2 \
  "2023 2024 2025" season-varying-config
bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" check 80 2 \
  "2023 2024 2025" season-varying-config

mkdir -p "$OUT"
JOB=compare-tabpfn-team-qb-exact80-v1
ARGS="scripts/compare_tabpfn_team_qb_lineup_v1.py,--historical-source,$SOURCE,--historical-code-sha,a12ab31,--control,$CONTROL,--treatment,$TREATMENT,--code-sha,$CODE_SHA,--role-selected,$ROLE_SELECTED,--allocation,$ALLOCATION,--selected-k,$SELECTED_K,--control-schedules-b64,$CONTROL_B64,--treatment-schedules-b64,$TREATMENT_B64,--cache-validation-sha,$CACHE_SHA,--final-served-sha,$FINAL_SHA"
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
FILTER="resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\" AND textPayload:\"TABPFN_TEAM_QB_STAGE_B_V1_JSON=\""
gcloud logging read "$FILTER" --project "$PROJECT" --limit 10 --order asc \
  --format='value(textPayload)' > "$OUT/comparison_raw.txt"
"$ROOT/.venv/bin/python" - "$OUT/comparison_raw.txt" "$REPORT" <<'PY'
import json
import sys

prefix = "TABPFN_TEAM_QB_STAGE_B_V1_JSON="
payloads = [
    json.loads(line.split(prefix, 1)[1])
    for line in open(sys.argv[1], encoding="utf-8") if prefix in line]
if len(payloads) != 1:
    raise SystemExit(f"ABORT: expected one team-QB comparison, got {len(payloads)}")
report = payloads[0]
if report.get("disposition") != "valid" or report.get("failures"):
    raise SystemExit("ABORT: team-QB comparison is invalid")
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
    raise SystemExit("ABORT: team-QB selection is not registered")
print(selected)
PY
)
if [ "$SELECTED" = "$TREATMENT" ]; then
  bash "$ROOT/scripts/cloud_accept_panel.sh" "$IMG" "$TREATMENT" promote 80 2 \
    "2023 2024 2025" season-varying-config
  TEAM_QB_SELECTED=true
  CACHE_TABLE=tabpfn_team_qb_treatment_v1
  SELECTED_EVAL=$TREATMENT
else
  TEAM_QB_SELECTED=false
  CACHE_TABLE=$INHERITED_TABLE
  SELECTED_EVAL=$(awk -F= '$1=="selected_eval_panel" {print $2}' "$SCHED")
fi
printf '%s\n' \
  "historical_source=$SOURCE" "role_selected=$ROLE_SELECTED" \
  "allocation=$ALLOCATION" "selected_k=$SELECTED_K" \
  "label_law=$LABEL_LAW" "feature_contract=$FEATURE_CONTRACT" \
  "team_qb_selected=$TEAM_QB_SELECTED" "cache_table=$CACHE_TABLE" \
  "selected_eval_panel=$SELECTED_EVAL" "comparison_execution=$EXEC" \
  "cache_validation_sha256=$CACHE_SHA" \
  "final_served_report_sha256=$FINAL_SHA" \
  "comparison_sha256=$(sha256sum "$REPORT" | awk '{print $1}')" \
  > "$OUT/selected_team_qb.txt"
echo "PIT_TEAM_QB_EXACT80_SELECTED $SELECTED team_qb=$TEAM_QB_SELECTED"
