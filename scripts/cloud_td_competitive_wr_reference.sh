#!/bin/bash
# Launch the frozen clean repaired-path TD competitive-WR reference.
# Usage: cloud_td_competitive_wr_reference.sh <IMAGE@sha256:...> <40-char SHA> [RUN_ID] [JOB]
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${3:-20260814-td-competitive-wr-v1}
JOB=${4:-td-competitive-wr-reference-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/td-competitive-wr-runs/$RUN_ID/reference"
PROTOCOL="$ROOT/reports/2026-08-14-td-competitive-wr-allocation-protocol.md"
PRIOR="$ROOT/reports/td-ledger-rank-coupling-runs/20260814-td-ledger-rank-coupling-v1"
G1="$ROOT/reports/g1-topology-runs/20260812-g1-archetype-topology-v3"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable competitive-WR image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full competitive-WR code SHA required"; exit 2; }
for path in "$PROTOCOL" "$PRIOR/report.json" "$PRIOR/manifest.txt" \
  "$G1/report.json" "$G1/manifest.txt" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: competitive-WR prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT" ] || { echo "ABORT: immutable competitive-WR reference exists: $OUT"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" "$G1/report.json" "$PRIOR/report.json" <<'PY'
import base64
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

active = selection(sys.argv[1])
usage = selection(sys.argv[2])
g1 = json.load(open(sys.argv[3], encoding="utf-8"))
prior = json.load(open(sys.argv[4], encoding="utf-8"))
if active.get("allocation") != "dirichlet" or usage.get("allocation") != "dirichlet":
    raise SystemExit("ABORT: competitive-WR reference requires finite-K allocation")
if active.get("selected_k") != usage.get("selected_k") or not math.isclose(
        float(active["selected_k"]), 28.154043586960896, rel_tol=0, abs_tol=0):
    raise SystemExit("ABORT: competitive-WR reference finite K differs")
if active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: competitive-WR reference cache differs")
panel = active.get("historical_source", "")
if prior.get("panel") != panel or "control" not in prior:
    raise SystemExit("ABORT: competitive-WR repaired prior differs")
schedule = {str(season): {"factors": value.get("factors", {})}
            for season, value in g1.get("position_schedule", {}).items()}
if set(schedule) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: competitive-WR schedule is incomplete")
encoded = base64.b64encode(json.dumps(
    schedule, sort_keys=True, separators=(",", ":")).encode()).decode()
print(f"panel={panel}")
print(f"selected_eval_panel={active.get('selected_eval_panel', '')}")
print(f"cache={active['cache_table']}")
print(f"k={active['selected_k']}")
print(f"schedule_b64={encoded}")
PY
)

mkdir -p "$OUT"
PRIOR_SHA=$(sha256sum "$PRIOR/report.json" | awk '{print $1}')
SCHEDULE_SHA=$(printf '%s' "${resolved[schedule_b64]}" | base64 -d | sha256sum | awk '{print $1}')
printf '%s\n' \
  "run_id=$RUN_ID" "stage=reference" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=${resolved[panel]}" "selected_eval_panel=${resolved[selected_eval_panel]}" \
  "cache_table=${resolved[cache]}" "dirichlet_k=${resolved[k]}" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "prior_report_sha256=$PRIOR_SHA" \
  "prior_manifest_sha256=$(sha256sum "$PRIOR/manifest.txt" | awk '{print $1}')" \
  "g1_report_sha256=$(sha256sum "$G1/report.json" | awk '{print $1}')" \
  "g1_manifest_sha256=$(sha256sum "$G1/manifest.txt" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "schedule_sha256=$SCHEDULE_SHA" \
  'evaluation_seasons=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'model_market_blend=0.45/0.55' 'reference_tolerance=1e-12' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
ENVS="$ENVS,TD_COMP_WR_PANEL_ID=${resolved[panel]}"
ENVS="$ENVS,TD_COMP_WR_RUN_ID=$RUN_ID,TD_COMP_WR_CODE_SHA=$CODE_SHA"
ENVS="$ENVS,TD_COMP_WR_PRIOR_REPORT_SHA256=$PRIOR_SHA"
ENVS="$ENVS,G1_PANEL_ID=${resolved[panel]},G1_CACHE_TABLE=${resolved[cache]}"
ENVS="$ENVS,G1_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=${resolved[k]}"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=${resolved[k]}"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "td-competitive-wr-reference,--panel,${resolved[panel]}" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 21600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: competitive-WR reference deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: competitive-WR reference execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TD_COMPETITIVE_WR_REFERENCE_LAUNCHED $EXEC"
