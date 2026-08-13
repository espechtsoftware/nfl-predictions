#!/bin/bash
# Launch the sole frozen score-free current-incumbent TD-ledger gate.
# Usage: cloud_td_ledger_final_served.sh <AUDIT_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-td-ledger-final-served-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/td-ledger-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-13-td-ledger-final-served-protocol.md"
G0="$ROOT/reports/g0-dependence-runs/20260812-g0-final-served-dependence-v2"
G1="$ROOT/reports/g1-topology-runs/20260812-g1-archetype-topology-v3"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable TD-ledger image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable TD-ledger code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$G0/report.json" "$G0/manifest.txt" \
  "$G1/report.json" "$G1/manifest.txt" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: TD-ledger prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/execution.txt" ] || {
  echo "ABORT: immutable TD-ledger execution already recorded"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" "$G0/report.json" "$G1/report.json" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

active = selection(sys.argv[1])
usage = selection(sys.argv[2])
g0 = json.load(open(sys.argv[3], encoding="utf-8"))
g1 = json.load(open(sys.argv[4], encoding="utf-8"))
if g1.get("disposition") != "stable-qb-hub-confirmed" or \
        not g1.get("g2_licensed") or not g1.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: TD-ledger lacks the valid G1 premise")
if active.get("allocation") != "dirichlet" or usage.get("allocation") != "dirichlet":
    raise SystemExit("ABORT: TD-ledger requires accepted finite-K allocation")
if active.get("selected_k") != usage.get("selected_k"):
    raise SystemExit("ABORT: TD-ledger selected finite K differs")
if not math.isclose(float(active["selected_k"]), 28.154043586960896,
                    rel_tol=0, abs_tol=0):
    raise SystemExit("ABORT: TD-ledger finite K differs from frozen value")
if active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: TD-ledger active cache differs")
panel = active.get("historical_source", "")
selected_eval = active.get("selected_eval_panel", "")
if g0.get("panel") != panel or g1.get("panel") != panel:
    raise SystemExit("ABORT: TD-ledger G0/G1 panel identity differs")
if g0.get("cache_table") != active.get("cache_table") or \
        g1.get("cache_table") != active.get("cache_table"):
    raise SystemExit("ABORT: TD-ledger G0/G1 cache identity differs")
schedule = {str(season): {"factors": value.get("factors", {})}
            for season, value in g1.get("position_schedule", {}).items()}
if set(schedule) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: TD-ledger position schedule is incomplete")
encoded = base64.b64encode(json.dumps(
    schedule, sort_keys=True, separators=(",", ":")).encode()).decode()
print(f"panel={panel}")
print(f"selected_eval_panel={selected_eval}")
print(f"cache={active['cache_table']}")
print(f"k={active['selected_k']}")
print(f"schedule_b64={encoded}")
PY
)

mkdir -p "$OUT"
G0_SHA=$(sha256sum "$G0/report.json" | awk '{print $1}')
G1_SHA=$(sha256sum "$G1/report.json" | awk '{print $1}')
SCHEDULE_SHA=$(printf '%s' "${resolved[schedule_b64]}" | base64 -d | sha256sum | awk '{print $1}')
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=${resolved[panel]}" "selected_eval_panel=${resolved[selected_eval_panel]}" \
  "cache_table=${resolved[cache]}" "dirichlet_k=${resolved[k]}" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "g0_report_sha256=$G0_SHA" \
  "g0_manifest_sha256=$(sha256sum "$G0/manifest.txt" | awk '{print $1}')" \
  "g1_report_sha256=$G1_SHA" \
  "g1_manifest_sha256=$(sha256sum "$G1/manifest.txt" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "schedule_sha256=$SCHEDULE_SHA" \
  'evaluation_seasons=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'bootstrap_replicates=2000' 'bootstrap_seed=1703' \
  'treatment=TD_LEDGER=1' 'td_alloc_k=null' \
  'material_regression_tolerance=log(1.05)' \
  > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
ENVS="$ENVS,TD_LEDGER_PANEL_ID=${resolved[panel]}"
ENVS="$ENVS,TD_LEDGER_G0_REPORT_SHA256=$G0_SHA,TD_LEDGER_G1_REPORT_SHA256=$G1_SHA"
ENVS="$ENVS,G1_PANEL_ID=${resolved[panel]},G1_CACHE_TABLE=${resolved[cache]}"
ENVS="$ENVS,G1_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=${resolved[k]}"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=${resolved[k]}"
JOB=td-ledger-final-served-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "td-ledger-final-served,--panel,${resolved[panel]}" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 21600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: TD-ledger job deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: TD-ledger execution id missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TD_LEDGER_FINAL_SERVED_LAUNCHED $EXEC"
