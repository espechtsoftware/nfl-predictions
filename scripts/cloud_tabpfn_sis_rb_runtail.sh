#!/bin/bash
# Launch the frozen adaptive SIS RB opponent run-tail cache pair.
# Usage: cloud_tabpfn_sis_rb_runtail.sh <GPU_IMAGE@sha256:...> <40-char SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260814-tabpfn-sis-rb-runtail-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-rb-runtail-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-14-sis-run-tail-marginal-protocol.md"
AUDIT="$ROOT/reports/2026-08-14-sis-run-tail-prerequisite-audit.md"
AUDIT_SQL="$ROOT/sql/audits/sis_run_tail_prerequisite.sql"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
SCHED="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"
TEAM_QB="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean/selected_team_qb.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable run-tail GPU image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full immutable run-tail code SHA required"; exit 2; }
for path in "$PROTOCOL" "$AUDIT" "$AUDIT_SQL" "$ACTIVE" "$SCHED" "$TEAM_QB"; do
  [ -s "$path" ] || { echo "ABORT: run-tail prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT" ] || { echo "ABORT: immutable run-tail run exists: $OUT"; exit 2; }

"$ROOT/.venv/bin/python" - "$ACTIVE" "$SCHED" "$TEAM_QB" <<'PY'
import sys
def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)
active, sched, team = map(selection, sys.argv[1:])
if active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: run-tail active-label selection differs")
if sched.get("sched_selected") != "false" or \
        sched.get("feature_contract") != "shared33" or \
        sched.get("cache_table") != active["cache_table"]:
    raise SystemExit("ABORT: run-tail SCHED selection differs")
if team.get("team_qb_selected") != "false" or \
        team.get("feature_contract") != "shared33" or \
        team.get("cache_table") != active["cache_table"]:
    raise SystemExit("ABORT: run-tail team-QB selection differs")
PY

"$ROOT/.venv/bin/python" - "$PROJECT" <<'PY'
import sys

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

project = sys.argv[1]
client = bigquery.Client(project=project)
for table in (
    "tabpfn_sis_rb_runtail_control_v1",
    "tabpfn_sis_rb_runtail_treatment_v1",
):
    identity = f"{project}.nfl_features.{table}"
    try:
        client.get_table(identity)
    except NotFound:
        continue
    raise SystemExit(f"ABORT: write-once run-tail table already exists: {table}")
PY

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "audit_sha256=$(sha256sum "$AUDIT" | awk '{print $1}')" \
  "audit_sql_sha256=$(sha256sum "$AUDIT_SQL" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "sched_selection_sha256=$(sha256sum "$SCHED" | awk '{print $1}')" \
  "team_qb_selection_sha256=$(sha256sum "$TEAM_QB" | awk '{print $1}')" \
  'adaptive_retrospective=true' 'label_law=active_only' 'feature_law=base' \
  'inherited_cache_table=tabpfn_active_label_treatment_v2' \
  'source_table=nfl_raw.sis_team_run_context_game' \
  'source_run=sis-team-run-context-tranche-2-v1' \
  'treatment_features=sis_rb_def_boom_rate_l4 sis_rb_def_bust_rate_l4' \
  'target_seasons=2022 2023 2024 2025' \
  'context=strictly earlier seasons' 'context_max=28000' \
  'random_seed=7' 'n_estimators=4' 'tabpfn_version=2.2.1' \
  'control_table=nfl_features.tabpfn_sis_rb_runtail_control_v1' \
  'treatment_table=nfl_features.tabpfn_sis_rb_runtail_treatment_v1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch_arm() {
  local arm=$1 table=$2 job="tabpfn-sis-rb-runtail-v1-$1"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" \
    --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_SIS_RB_RUNTAIL_ARM=$arm,TABPFN_OUTPUT_TABLE=$table,CODE_SHA=$CODE_SHA" \
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

launch_arm control tabpfn_sis_rb_runtail_control_v1
launch_arm treatment tabpfn_sis_rb_runtail_treatment_v1
echo "TABPFN_SIS_RB_RUNTAIL_LAUNCHED $OUT"
