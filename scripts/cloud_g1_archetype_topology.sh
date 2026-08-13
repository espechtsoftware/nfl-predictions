#!/bin/bash
# Launch the sole frozen G1 walk-forward archetype topology diagnostic.
# Usage: cloud_g1_archetype_topology.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-g1-archetype-topology-v3
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/g1-topology-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-12-g1-walk-forward-archetype-topology-protocol.md"
G0="$ROOT/reports/g0-dependence-runs/20260812-g0-final-served-dependence-v2"
SELECTED="$ROOT/reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean/selected_team_qb.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
SCHED="$ROOT/reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable G1 image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable G1 code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$G0/report.json" "$G0/manifest.txt" \
  "$G0/cache_preflight.json" "$SELECTED" "$USAGE" "$ACTIVE" "$SCHED"; do
  [ -s "$path" ] || { echo "ABORT: G1 prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable G1 execution already recorded"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$SELECTED" "$USAGE" "$G0/report.json" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(
        line.rstrip("\n").split("=", 1)
        for line in open(path, encoding="utf-8") if "=" in line)

selected = selection(sys.argv[1])
usage = selection(sys.argv[2])
report = json.load(open(sys.argv[3], encoding="utf-8"))
if report.get("disposition") != "dependence-premise-miss" or \
        not report.get("g1_licensed") or \
        not report.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: G1 lacks a valid G0 license")
panel = selected.get("historical_source", "")
cache = selected.get("cache_table", "")
if report.get("panel") != panel or report.get("cache_table") != cache:
    raise SystemExit("ABORT: G1 terminal selection differs from G0")
schedule = report.get("position_schedule", {})
compact = {
    str(season): {"factors": value.get("factors", {})}
    for season, value in schedule.items()
}
if set(compact) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: G1 selected served schedule is incomplete")
allocation = usage.get("allocation", "")
k = usage.get("selected_k", "")
if allocation == "multinomial" and k == "infinity":
    accepted_usage, accepted_k = "multinomial", "-"
elif allocation == "dirichlet":
    try:
        valid = math.isfinite(float(k)) and float(k) > 0
    except ValueError:
        valid = False
    if not valid:
        raise SystemExit("ABORT: G1 fitted K is invalid")
    accepted_usage, accepted_k = "dirichlet", k
else:
    raise SystemExit("ABORT: G1 selected usage law is invalid")
encode = lambda value: base64.b64encode(
    json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).decode()
print(f"panel={panel}")
print(f"cache={cache}")
print(f"selected_eval_panel={selected.get('selected_eval_panel', '')}")
print(f"schedule_b64={encode(compact)}")
print(f"g0_reference_b64={encode(report)}")
print(f"accepted_usage={accepted_usage}")
print(f"accepted_k={accepted_k}")
PY
)

mkdir -p "$OUT"
cp "$G0/cache_preflight.json" "$OUT/cache_preflight.json"
SCHEDULE_SHA=$(printf '%s' "${resolved[schedule_b64]}" | base64 -d | sha256sum | awk '{print $1}')
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=${resolved[panel]}" "cache_table=${resolved[cache]}" \
  "selected_eval_panel=${resolved[selected_eval_panel]}" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "g0_report_sha256=$(sha256sum "$G0/report.json" | awk '{print $1}')" \
  "g0_manifest_sha256=$(sha256sum "$G0/manifest.txt" | awk '{print $1}')" \
  "g0_cache_preflight_sha256=$(sha256sum "$G0/cache_preflight.json" | awk '{print $1}')" \
  "terminal_selection_sha256=$(sha256sum "$SELECTED" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "sched_selection_sha256=$(sha256sum "$SCHED" | awk '{print $1}')" \
  "schedule_sha256=$SCHEDULE_SHA" \
  "accepted_usage_law=${resolved[accepted_usage]}" \
  "dirichlet_k=${resolved[accepted_k]}" \
  'evaluation_seasons=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'bootstrap_replicates=2000' 'bootstrap_seed=1702' \
  'archetype_min_games=16' 'archetype_components=4' 'archetype_seed=0' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,G1_PANEL_ID=${resolved[panel]}"
ENVS="$ENVS,G1_CACHE_TABLE=${resolved[cache]}"
ENVS="$ENVS,G1_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,G1_G0_REFERENCE_B64=${resolved[g0_reference_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=${resolved[accepted_usage]}"
if [ "${resolved[accepted_usage]}" = dirichlet ]; then
  ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=${resolved[accepted_k]}"
  ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=${resolved[accepted_k]}"
fi
JOB=g1-archetype-topology-v3
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "g1-archetype-topology,--panel,${resolved[panel]}" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: G1 job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: G1 execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "G1_ARCHETYPE_TOPOLOGY_LAUNCHED $EXEC"
