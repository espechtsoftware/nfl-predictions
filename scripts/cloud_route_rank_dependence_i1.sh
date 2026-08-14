#!/bin/bash
# Launch the frozen current-stack Route component/rank dependence screen.
# Usage: cloud_route_rank_dependence_i1.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-route-rank-dependence-i1-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/route-rank-dependence-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-14-route-channel-i1-protocol.md"
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/report.json"
G0="$ROOT/reports/g0-dependence-runs/20260812-g0-final-served-dependence-v2/report.json"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$PHASE_S" "$G0" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable Route rank execution already recorded"; exit 2; }

read -r PANEL DIRICHLET_K PHASE_S_ARM SCHEDULE_B64 <<< "$(
  "$ROOT/.venv/bin/python" - "$PHASE_S" "$G0" "$ACTIVE" "$USAGE" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

phase = json.load(open(sys.argv[1], encoding="utf-8"))
g0 = json.load(open(sys.argv[2], encoding="utf-8"))
active = selection(sys.argv[3])
usage = selection(sys.argv[4])
if not phase.get("mechanical_passes") or phase.get("failures"):
    raise SystemExit("ABORT: Phase S mechanical audit did not pass")
phase_arm = phase.get("result", {}).get("decision", {}).get("selected_arm")
if phase_arm not in {"control", "treatment"}:
    raise SystemExit("ABORT: Phase S decision is incomplete")
if not g0.get("invariants", {}).get("passes") or \
        g0.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: accepted G0 terminal contract differs")
schedule = g0.get("position_schedule", {})
if set(schedule) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: accepted G0 position schedule differs")
panel = active.get("historical_source", "")
if panel != "20260811-pitclean-e80-k1-role12union-a12ab31" or \
        active.get("label_law") != "active-only" or \
        active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: active-label selection differs")
if usage.get("allocation") != "dirichlet":
    raise SystemExit("ABORT: accepted usage law is not finite Dirichlet")
value = usage.get("selected_k", "")
try:
    numeric = float(value)
except ValueError as exc:
    raise SystemExit("ABORT: fitted K is not numeric") from exc
if not math.isfinite(numeric) or numeric <= 0:
    raise SystemExit("ABORT: fitted K is invalid")
payload = json.dumps(schedule, separators=(",", ":"), sort_keys=True).encode()
encoded = base64.b64encode(payload).decode().rstrip("=")
print(panel, value, phase_arm, encoded)
PY
)"

SOURCE=$(
  bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
    'SELECT COUNT(*) AS n, BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum FROM `nfl-predictions-503414.nfl_features.player_week_training` t' \
    | tail -1 | tr -d '[:space:]'
)
[ "$SOURCE" = "102927,1904430067081090565" ] || {
  echo "ABORT: Route rank source snapshot differs: $SOURCE"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" "panel=$PANEL" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "phase_s_report_sha256=$(sha256sum "$PHASE_S" | awk '{print $1}')" \
  "g0_reference_sha256=$(sha256sum "$G0" | awk '{print $1}')" \
  "active_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  'cache_table=nfl_features.tabpfn_active_label_treatment_v2' \
  'source_rows=102927' 'source_checksum=1904430067081090565' \
  'component_difference=fp_route_share_last fp_route_share_l4 fp_route_share_jump fp_route_cross_season' \
  "dirichlet_k=$DIRICHLET_K" "phase_s_arm=$PHASE_S_ARM" \
  'evaluation_folds=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'sorted_marginal_tolerance=1e-10' \
  'loss_families=g0-multiplicity g0-role-pair g1-primary-broad joint-q90-brier variogram-p0.5' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,ROUTE_RANK_I1_PANEL_ID=$PANEL"
ENVS="$ENVS,ROUTE_RANK_I1_POSITION_SCHEDULE_B64=$SCHEDULE_B64"
ENVS="$ENVS,TABPFN_ROUTE_PHASE_S_ARM=$PHASE_S_ARM"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
if [ "$PHASE_S_ARM" = treatment ]; then
  ENVS="$ENVS,SIS_ASOE_TARGET_ALLOCATION=1,SIS_ASOE_BETA=0.07771181538347656"
fi
JOB=route-rank-dependence-i1-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "route-rank-dependence-i1,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 14400 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: Route rank gate deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: Route rank execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "ROUTE_RANK_DEPENDENCE_I1_LAUNCHED $EXEC"
