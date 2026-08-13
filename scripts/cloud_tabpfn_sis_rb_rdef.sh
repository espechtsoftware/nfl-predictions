#!/bin/bash
# Launch the frozen active-only SIS RB opponent run-defense cache pair.
# Usage: cloud_tabpfn_sis_rb_rdef.sh <GPU_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260813-tabpfn-sis-rb-rdef-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-rb-rdef-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-sis-rb-run-defense-protocol.md"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
SCHED="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"
TEAM_QB="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean/selected_team_qb.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable GPU image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$ACTIVE" "$SCHED" "$TEAM_QB"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable SIS RB executions already recorded"; exit 2; }

"$ROOT/.venv/bin/python" - "$ACTIVE" "$SCHED" "$TEAM_QB" <<'PY'
import sys
def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)
active, sched, team = map(selection, sys.argv[1:])
if active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: active-label terminal selection differs")
if sched.get("sched_selected") != "false" or \
        sched.get("feature_contract") != "shared33" or \
        sched.get("cache_table") != active["cache_table"]:
    raise SystemExit("ABORT: SCHED terminal selection differs")
if team.get("team_qb_selected") != "false" or \
        team.get("feature_contract") != "shared33" or \
        team.get("cache_table") != active["cache_table"]:
    raise SystemExit("ABORT: team-QB terminal selection differs")
PY

for table in tabpfn_sis_rb_rdef_control_v1 tabpfn_sis_rb_rdef_treatment_v1; do
  if bq show --project_id "$PROJECT" "$PROJECT:nfl_features.$table" \
      >/dev/null 2>&1; then
    echo "ABORT: write-once SIS RB table already exists: $table"
    exit 2
  fi
done

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "sched_selection_sha256=$(sha256sum "$SCHED" | awk '{print $1}')" \
  "team_qb_selection_sha256=$(sha256sum "$TEAM_QB" | awk '{print $1}')" \
  'label_law=active_only' 'feature_law=base' \
  'inherited_cache_table=tabpfn_active_label_treatment_v2' \
  'source_table=nfl_raw.sis_team_run_context_game' \
  'source_run=sis-team-run-context-tranche-2-v1' \
  'treatment_feature=sis_rb_def_ps_per_play_l4' \
  'target_seasons=2022 2023 2024 2025' \
  'context=strictly earlier seasons' 'context_max=28000' \
  'random_seed=7' 'n_estimators=4' 'tabpfn_version=2.2.1' \
  'control_table=nfl_features.tabpfn_sis_rb_rdef_control_v1' \
  'treatment_table=nfl_features.tabpfn_sis_rb_rdef_treatment_v1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch_arm() {
  local arm=$1 table=$2 job="tabpfn-sis-rb-rdef-v2-$1"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" \
    --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_SIS_RB_RDEF_ARM=$arm,TABPFN_OUTPUT_TABLE=$table,CODE_SHA=$CODE_SHA" \
    --memory 16Gi --cpu 4 --gpu 1 --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy --max-retries 0 --task-timeout 3600 \
    --service-account "$SERVICE_ACCOUNT" >/dev/null
  local deployed execution
  deployed=$(gcloud run jobs describe "$job" --project "$PROJECT" \
    --region "$REGION" \
    --format='value(spec.template.spec.template.spec.containers[0].image)')
  [ "$deployed" = "$IMG" ] || {
    echo "ABORT: $job deployed $deployed, expected $IMG"; exit 1; }
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [ -n "$execution" ] || { echo "ABORT: $arm execution id missing"; exit 1; }
  printf '%s %s %s %s\n' "$arm" "$job" "$execution" "$table" \
    | tee -a "$OUT/executions.txt"
}

launch_arm control tabpfn_sis_rb_rdef_control_v1
launch_arm treatment tabpfn_sis_rb_rdef_treatment_v1
echo "TABPFN_SIS_RB_RDEF_LAUNCHED $OUT"
