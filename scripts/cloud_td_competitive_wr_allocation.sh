#!/bin/bash
# Launch the sole frozen score-free competitive-WR allocation after reference pass.
# Usage: cloud_td_competitive_wr_allocation.sh <IMAGE@sha256:...> <40-char SHA> [RUN_ID] [JOB]
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=${3:-20260814-td-competitive-wr-v1}
JOB=${4:-td-competitive-wr-allocation-v1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BASE="$ROOT/reports/td-competitive-wr-runs/$RUN_ID"
OUT="$BASE/treatment"
REFERENCE="$BASE/reference"
PROTOCOL="$ROOT/reports/2026-08-14-td-competitive-wr-allocation-protocol.md"
G1="$ROOT/reports/g1-topology-runs/20260812-g1-archetype-topology-v3"
ACTIVE="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"
USAGE="$ROOT/reports/usage-dirichlet-calibration-runs/20260812-usage-exact80-v2-pit-clean/selected_usage.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable competitive-WR image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full competitive-WR code SHA required"; exit 2; }
for path in "$PROTOCOL" "$REFERENCE/report.json" "$REFERENCE/manifest.txt" \
  "$G1/report.json" "$G1/manifest.txt" "$ACTIVE" "$USAGE"; do
  [ -s "$path" ] || { echo "ABORT: competitive-WR prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT" ] || { echo "ABORT: immutable competitive-WR treatment exists: $OUT"; exit 2; }

declare -A resolved
while IFS='=' read -r key value; do resolved[$key]=$value; done < <(
  "$ROOT/.venv/bin/python" - "$ACTIVE" "$USAGE" "$G1/report.json" \
    "$REFERENCE/report.json" "$REFERENCE/manifest.txt" <<'PY'
import base64
import hashlib
import json
import math
import sys

def selection(path):
    return dict(line.rstrip("\n").split("=", 1)
                for line in open(path, encoding="utf-8") if "=" in line)

active = selection(sys.argv[1])
usage = selection(sys.argv[2])
g1 = json.load(open(sys.argv[3], encoding="utf-8"))
reference = json.load(open(sys.argv[4], encoding="utf-8"))
reference_bytes = open(sys.argv[4], "rb").read()
reference_manifest = selection(sys.argv[5])
if reference.get("disposition") != "td-competitive-wr-reference-passes" or \
        not reference.get("treatment_licensed") or \
        not reference.get("invariants", {}).get("passes"):
    raise SystemExit("ABORT: competitive-WR reference does not license treatment")
if active.get("allocation") != "dirichlet" or usage.get("allocation") != "dirichlet":
    raise SystemExit("ABORT: competitive-WR treatment requires finite-K allocation")
if active.get("selected_k") != usage.get("selected_k") or not math.isclose(
        float(active["selected_k"]), 28.154043586960896, rel_tol=0, abs_tol=0):
    raise SystemExit("ABORT: competitive-WR treatment finite K differs")
if active.get("cache_table") != "tabpfn_active_label_treatment_v2":
    raise SystemExit("ABORT: competitive-WR treatment cache differs")
panel = active.get("historical_source", "")
if reference.get("panel") != panel or reference_manifest.get("panel") != panel:
    raise SystemExit("ABORT: competitive-WR reference panel differs")
if reference.get("run_identity") != {
        "run_id": reference_manifest.get("run_id"),
        "code_sha": reference_manifest.get("code_sha"),
}:
    raise SystemExit("ABORT: competitive-WR reference run/code identity differs")
score_sha = reference.get("score_sha256", "")
if len(score_sha) != 64 or any(
        value not in "0123456789abcdef" for value in score_sha):
    raise SystemExit("ABORT: competitive-WR reference score fingerprint differs")
if reference_manifest.get("cache_table") != active.get("cache_table") or \
        reference_manifest.get("dirichlet_k") != active.get("selected_k"):
    raise SystemExit("ABORT: competitive-WR reference runtime differs")
schedule = {str(season): {"factors": value.get("factors", {})}
            for season, value in g1.get("position_schedule", {}).items()}
if set(schedule) != {"2023", "2024", "2025"}:
    raise SystemExit("ABORT: competitive-WR schedule is incomplete")
payload = json.dumps(schedule, sort_keys=True, separators=(",", ":")).encode()
if hashlib.sha256(payload).hexdigest() != reference_manifest.get("schedule_sha256"):
    raise SystemExit("ABORT: competitive-WR reference schedule differs")
print(f"panel={panel}")
print(f"selected_eval_panel={active.get('selected_eval_panel', '')}")
print(f"cache={active['cache_table']}")
print(f"k={active['selected_k']}")
print(f"schedule_b64={base64.b64encode(payload).decode()}")
print(f"reference_run_id={reference['run_identity']['run_id']}")
print(f"reference_code_sha={reference['run_identity']['code_sha']}")
attestation = {
    "version": reference["version"],
    "panel": reference["panel"],
    "disposition": reference["disposition"],
    "treatment_licensed": reference["treatment_licensed"],
    "run_identity": reference["run_identity"],
    "report_sha256": hashlib.sha256(reference_bytes).hexdigest(),
    "score_sha256": score_sha,
}
attestation_bytes = json.dumps(
    attestation, sort_keys=True, separators=(",", ":"),
).encode()
print(f"reference_score_sha256={score_sha}")
print(f"reference_attestation_b64={base64.b64encode(attestation_bytes).decode()}")
print(f"reference_attestation_sha256={hashlib.sha256(attestation_bytes).hexdigest()}")
PY
)

mkdir -p "$OUT"
REFERENCE_SHA=$(sha256sum "$REFERENCE/report.json" | awk '{print $1}')
SCHEDULE_SHA=$(printf '%s' "${resolved[schedule_b64]}" | base64 -d | sha256sum | awk '{print $1}')
printf '%s\n' \
  "run_id=$RUN_ID" "stage=treatment" "image=$IMG" "code_sha=$CODE_SHA" \
  "panel=${resolved[panel]}" "selected_eval_panel=${resolved[selected_eval_panel]}" \
  "cache_table=${resolved[cache]}" "dirichlet_k=${resolved[k]}" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "reference_report_sha256=$REFERENCE_SHA" \
  "reference_manifest_sha256=$(sha256sum "$REFERENCE/manifest.txt" | awk '{print $1}')" \
  "reference_run_id=${resolved[reference_run_id]}" \
  "reference_code_sha=${resolved[reference_code_sha]}" \
  "reference_score_sha256=${resolved[reference_score_sha256]}" \
  "reference_attestation_sha256=${resolved[reference_attestation_sha256]}" \
  "g1_report_sha256=$(sha256sum "$G1/report.json" | awk '{print $1}')" \
  "g1_manifest_sha256=$(sha256sum "$G1/manifest.txt" | awk '{print $1}')" \
  "active_label_selection_sha256=$(sha256sum "$ACTIVE" | awk '{print $1}')" \
  "usage_selection_sha256=$(sha256sum "$USAGE" | awk '{print $1}')" \
  "schedule_sha256=$SCHEDULE_SHA" \
  'evaluation_seasons=2023 2024 2025' 'n_sims=10000' 'seed=0' \
  'bootstrap_replicates=2000' 'bootstrap_seed=1703' \
  'rank_source=TD_LEDGER=1' 'td_alloc_k=null' \
  'changed_positions=WR' \
  'priority=qb_control_percentile+(wr_td_percentile-team_wr_mean_percentile)' \
  'coefficients=1.0,1.0' 'reference_tolerance=1e-12' > "$OUT/manifest.txt"

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1"
ENVS="$ENVS,TD_COMP_WR_PANEL_ID=${resolved[panel]}"
ENVS="$ENVS,TD_COMP_WR_REFERENCE_REPORT_SHA256=$REFERENCE_SHA"
ENVS="$ENVS,TD_COMP_WR_REFERENCE_RUN_ID=${resolved[reference_run_id]}"
ENVS="$ENVS,TD_COMP_WR_REFERENCE_CODE_SHA=${resolved[reference_code_sha]}"
ENVS="$ENVS,TD_COMP_WR_REFERENCE_ATTESTATION_B64=${resolved[reference_attestation_b64]}"
ENVS="$ENVS,TD_COMP_WR_REFERENCE_ATTESTATION_SHA256=${resolved[reference_attestation_sha256]}"
ENVS="$ENVS,G1_PANEL_ID=${resolved[panel]},G1_CACHE_TABLE=${resolved[cache]}"
ENVS="$ENVS,G1_POSITION_SCHEDULE_B64=${resolved[schedule_b64]}"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=${resolved[k]}"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=${resolved[k]}"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "td-competitive-wr-allocation,--panel,${resolved[panel]}" \
  --set-env-vars "$ENVS" --memory 32Gi --cpu 8 \
  --max-retries 0 --task-timeout 21600 >/dev/null
DEPLOYED=$(gcloud run jobs describe "$JOB" --project "$PROJECT" --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$DEPLOYED" = "$IMG" ] || {
  echo "ABORT: competitive-WR treatment deployed $DEPLOYED, expected $IMG"; exit 1; }
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[ -n "$EXEC" ] || { echo "ABORT: competitive-WR treatment execution missing"; exit 1; }
printf '%s\n' "$EXEC" > "$OUT/execution.txt"
echo "TD_COMPETITIVE_WR_ALLOCATION_LAUNCHED $EXEC"
