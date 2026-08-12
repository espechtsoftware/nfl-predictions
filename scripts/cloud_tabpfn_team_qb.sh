#!/bin/bash
# Launch the frozen team-QB cache pair after terminal SCHED selection.
# Usage: cloud_tabpfn_team_qb.sh <GPU_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260812-tabpfn-team-qb-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-team-qb-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-team-qb-quality-protocol.md"
SCHED_SELECTION="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"
SIDE_REPORT="$ROOT/reports/tabpfn-team-qb-runs/20260812-team-qb-quality-side-table-v1/report.json"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable GPU image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$SCHED_SELECTION" "$SIDE_REPORT"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable team-QB executions already recorded"; exit 2; }

read -r LABEL_LAW FEATURE_LAW INHERITED_TABLE <<< "$(
  "$ROOT/.venv/bin/python" - "$SCHED_SELECTION" "$SIDE_REPORT" <<'PY'
import json
import sys

selected = dict(
    line.rstrip("\n").split("=", 1)
    for line in open(sys.argv[1], encoding="utf-8") if "=" in line)
side = json.load(open(sys.argv[2], encoding="utf-8"))
if side.get("disposition") != "team-qb-quality-side-table-valid":
    raise SystemExit("ABORT: team-QB side table did not validate")
label = {"current": "current", "active-only": "active_only"}.get(
    selected.get("label_law"))
feature = {"shared33": "base", "sched35": "sched"}.get(
    selected.get("feature_contract"))
table = selected.get("cache_table", "")
allowed = {
    "tabpfn_projections_pit_v2",
    "tabpfn_active_label_treatment_v2",
    "tabpfn_sched_treatment_v1",
}
if label is None or feature is None or table not in allowed:
    raise SystemExit("ABORT: terminal SCHED inheritance is invalid")
if feature == "sched" and table != "tabpfn_sched_treatment_v1":
    raise SystemExit("ABORT: SCHED feature law lacks treatment cache")
print(label, feature, table)
PY
)"

for table in tabpfn_team_qb_control_v1 tabpfn_team_qb_treatment_v1; do
  if bq show --project_id "$PROJECT" "$PROJECT:nfl_features.$table" \
      >/dev/null 2>&1; then
    echo "ABORT: write-once team-QB table already exists: $table"
    exit 2
  fi
done

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "sched_selection=$SCHED_SELECTION" \
  "sched_selection_sha256=$(sha256sum "$SCHED_SELECTION" | awk '{print $1}')" \
  "side_table_report=$SIDE_REPORT" \
  "side_table_report_sha256=$(sha256sum "$SIDE_REPORT" | awk '{print $1}')" \
  "label_law=$LABEL_LAW" "feature_law=$FEATURE_LAW" \
  "inherited_cache_table=$INHERITED_TABLE" \
  'target_seasons=2022 2023 2024 2025' \
  'context=strictly earlier seasons' 'context_max=28000' \
  'random_seed=7' 'n_estimators=4' 'tabpfn_version=2.2.1' \
  'control_table=nfl_features.tabpfn_team_qb_control_v1' \
  'treatment_table=nfl_features.tabpfn_team_qb_treatment_v1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch_arm() {
  local arm=$1
  local table=$2
  local job="tabpfn-team-qb-v1-$arm"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" \
    --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_TEAM_QB_ARM=$arm,TABPFN_TEAM_QB_LABEL_LAW=$LABEL_LAW,TABPFN_TEAM_QB_FEATURE_LAW=$FEATURE_LAW,TABPFN_OUTPUT_TABLE=$table,CODE_SHA=$CODE_SHA" \
    --memory 16Gi --cpu 4 --gpu 1 --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy --max-retries 0 --task-timeout 3600 \
    --service-account "$SERVICE_ACCOUNT" >/dev/null
  local deployed
  deployed=$(gcloud run jobs describe "$job" --project "$PROJECT" \
    --region "$REGION" \
    --format='value(spec.template.spec.template.spec.containers[0].image)')
  [ "$deployed" = "$IMG" ] || {
    echo "ABORT: $job deployed $deployed, expected $IMG"; exit 1; }
  local execution
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [ -n "$execution" ] || { echo "ABORT: $arm execution id missing"; exit 1; }
  printf '%s %s %s %s\n' "$arm" "$job" "$execution" "$table" \
    | tee -a "$OUT/executions.txt"
}

launch_arm control tabpfn_team_qb_control_v1
launch_arm treatment tabpfn_team_qb_treatment_v1
echo "TABPFN_TEAM_QB_LAUNCHED $OUT"
