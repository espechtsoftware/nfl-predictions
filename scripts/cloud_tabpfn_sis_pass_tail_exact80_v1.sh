#!/bin/bash
# Launch the frozen conditional SIS pass-tail five-seed exact-80 comparison.
# Usage: cloud_tabpfn_sis_pass_tail_exact80_v1.sh <GEN_IMAGE@sha256:...> <GEN_CODE_SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
IMG=${1:-}
CODE_SHA=${2:-}
FROZEN_IMG=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:018f0def471ba3f0a304cafb77e301c35e43d51658798f64a9ec85c95751d358
FROZEN_CODE=f92ce05
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260814-sis-pass-tail-exact80-v1
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/$RUN_ID"
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1"
PHASE_S_REPORT="$PHASE_S/report.json"
PHASE_S_MANIFEST="$PHASE_S/manifest.txt"
CACHE="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-v1/validation.json"
FINAL="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-final-served-v1/report.json"
PROTOCOL="$ROOT/reports/2026-08-13-sis-pass-tail-marginal-protocol.md"
ADDENDUM="$ROOT/reports/2026-08-14-sis-pass-tail-exact80-addendum.md"
MAX_IN_FLIGHT=${SIS_PASS_TAIL_MAX_IN_FLIGHT:-10}

[ "$IMG" = "$FROZEN_IMG" ] || { echo "ABORT: generation image differs from frozen digest"; exit 2; }
[ "$CODE_SHA" = "$FROZEN_CODE" ] || { echo "ABORT: generation code differs from frozen commit"; exit 2; }
for path in "$PHASE_S_REPORT" "$PHASE_S_MANIFEST" "$CACHE" "$FINAL" "$PROTOCOL" "$ADDENDUM"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/manifest.txt" ] || { echo "ABORT: immutable pass-tail panel already launched"; exit 2; }
case "$MAX_IN_FLIGHT" in
  ''|*[!0-9]*) echo "ABORT: SIS_PASS_TAIL_MAX_IN_FLIGHT must be an integer"; exit 2 ;;
esac
[ "$MAX_IN_FLIGHT" -ge 1 ] && [ "$MAX_IN_FLIGHT" -le 10 ] || {
  echo "ABORT: pass-tail in-flight cap must be between 1 and 10"; exit 2; }

PHASE_S_ARM=$("$ROOT/.venv/bin/python" - "$PHASE_S_REPORT" "$PHASE_S_MANIFEST" "$CACHE" "$FINAL" <<'PY'
import json
import math
import sys

phase, manifest_path, cache_path, final_path = sys.argv[1:]
r = json.load(open(phase, encoding="utf-8"))
m = dict(line.rstrip("\n").split("=", 1)
         for line in open(manifest_path, encoding="utf-8") if "=" in line)
c = json.load(open(cache_path, encoding="utf-8"))
f = json.load(open(final_path, encoding="utf-8"))
if not r.get("mechanical_passes") or r.get("failures"):
    raise SystemExit("ABORT: Phase S mechanical audit did not pass")
arm = r.get("result", {}).get("decision", {}).get("selected_arm")
if arm not in {"control", "treatment"}:
    raise SystemExit("ABORT: Phase S selected arm is not registered")
if m.get("selected_control_arm") != "k":
    raise SystemExit("ABORT: Phase S did not inherit finite K")
if c.get("disposition") != "tabpfn-sis-pass-tail-caches-valid" or \
        not c.get("passes") or not c.get("control_reproduction", {}).get("passes"):
    raise SystemExit("ABORT: pass-tail cache validation did not pass")
if f.get("disposition") != "tabpfn-sis-pass-tail-final-served-passes" or \
        not f.get("gate", {}).get("passes"):
    raise SystemExit("ABORT: pass-tail final-served gate did not pass")
if f.get("cache_tables") != {
        "control": "tabpfn_sis_pass_tail_control_v1",
        "treatment": "tabpfn_sis_pass_tail_treatment_v1"}:
    raise SystemExit("ABORT: pass-tail cache identities differ")
if f.get("common_usage_law", {}).get("k") != "28.154043586960896":
    raise SystemExit("ABORT: pass-tail calibration usage law differs")
if not math.isfinite(float(f.get("maximum_mean_delta", float("nan")))) or \
        abs(float(f["maximum_mean_delta"])) > 1e-10:
    raise SystemExit("ABORT: pass-tail mean-preservation gate differs")
expected = {
    "control": {
        "2023": {"QB": .76, "RB": .83, "TE": .99, "WR": 1.05},
        "2024": {"QB": .81, "RB": .88, "TE": .97, "WR": 1.07},
        "2025": {"QB": .85, "RB": .895, "TE": .96, "WR": 1.04}},
    "treatment": {
        "2023": {"QB": .975, "RB": .99, "TE": .975, "WR": 1.04},
        "2024": {"QB": .92, "RB": .97, "TE": .95, "WR": 1.055},
        "2025": {"QB": .92, "RB": .965, "TE": .945, "WR": 1.04}},
}
for name, seasons in expected.items():
    got = f.get(f"{name}_schedule", {})
    for season, factors in seasons.items():
        if got.get(season, {}).get("factors") != factors:
            raise SystemExit(f"ABORT: {name} {season} schedule differs")
print(arm)
PY
)

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "generation_image=$IMG" "generation_code_sha=$CODE_SHA" \
  "phase_s_arm=$PHASE_S_ARM" \
  "phase_s_report_sha256=$(sha256sum "$PHASE_S_REPORT" | awk '{print $1}')" \
  "phase_s_manifest_sha256=$(sha256sum "$PHASE_S_MANIFEST" | awk '{print $1}')" \
  "cache_validation_sha256=$(sha256sum "$CACHE" | awk '{print $1}')" \
  "final_served_report_sha256=$(sha256sum "$FINAL" | awk '{print $1}')" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "addendum_sha256=$(sha256sum "$ADDENDUM" | awk '{print $1}')" \
  'arms=control treatment' 'replicates=R0 R1 R2 R3 R4' \
  'seasons=2023 2024 2025' 'n_entries=80' 'n_sims=10000' \
  'dirichlet_k=28.154043586960896' 'tail_order=240 230 220 210 200 194 187' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"
: > "$OUT/preflight.txt"

ROLE_FEATURES=target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump
seed_pair() {
  case "$1" in
    0) printf '%s %s' 0 7331 ;;
    1) printf '%s %s' 1137260708 2690847602 ;;
    2) printf '%s %s' 2875959182 1630284992 ;;
    3) printf '%s %s' 253722715 3374646876 ;;
    4) printf '%s %s' 1643280042 3977633467 ;;
    *) return 2 ;;
  esac
}
position_spec() {
  case "$1:$2" in
    control:2023) printf '%s' 'QB:0.76,RB:0.83,TE:0.99,WR:1.05' ;;
    control:2024) printf '%s' 'QB:0.81,RB:0.88,TE:0.97,WR:1.07' ;;
    control:2025) printf '%s' 'QB:0.85,RB:0.895,TE:0.96,WR:1.04' ;;
    treatment:2023) printf '%s' 'QB:0.975,RB:0.99,TE:0.975,WR:1.04' ;;
    treatment:2024) printf '%s' 'QB:0.92,RB:0.97,TE:0.95,WR:1.055' ;;
    treatment:2025) printf '%s' 'QB:0.92,RB:0.965,TE:0.945,WR:1.04' ;;
    *) return 2 ;;
  esac
}
table_spec() {
  [ "$1" = control ] && printf '%s' tabpfn_sis_pass_tail_control_v1 || \
    printf '%s' tabpfn_sis_pass_tail_treatment_v1
}
common_env() {
  local ARM=$1 REP=$2 SEASON=$3 BASE_SEED ROLE_SEED SPEC TABLE ENVS
  read -r BASE_SEED ROLE_SEED <<< "$(seed_pair "$REP")"
  SPEC=$(position_spec "$ARM" "$SEASON")
  TABLE=$(table_spec "$ARM")
  ENVS="GCP_PROJECT=$PROJECT|GAME_SIM_MODE=possession|MODEL_ENSEMBLE=1"
  ENVS="$ENVS|TABPFN_MARGINALS=1|TABPFN_MARGINAL_TABLE=$TABLE"
  ENVS="$ENVS|EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_FEATURES=$ROLE_FEATURES"
  ENVS="$ENVS|ROLE_BELIEF_SEED=$ROLE_SEED|REPLAY_PROJECTION_SEED=$BASE_SEED|REPLACEMENT_SLOTS=12"
  ENVS="$ENVS|N_CE=0|N_EPISTEMIC=12|N_GUMBEL=0|N_BOOM=40|SERVED_POSITION_SCALES=$SPEC"
  ENVS="$ENVS|GAME_SIM_USAGE=dirichlet|DIRICHLET_K=28.154043586960896"
  if [ "$PHASE_S_ARM" = treatment ]; then
    ENVS="$ENVS|SIS_ASOE_TARGET_ALLOCATION=1|SIS_ASOE_BETA=0.07771181538347656"
  fi
  printf '%s' "$ENVS"
}

# Fail before allocating compute if any registered destination is nonempty.
for ARM in control treatment; do
  for REP in 0 1 2 3 4; do
    PANEL="20260814-sis-pass-tail-${ARM}-r${REP}-v1"
    for TABLE in replay_candidates_staging slate_player_features; do
      N=$(bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
        "SELECT COUNT(*) n FROM \`$PROJECT.nfl_predictions.$TABLE\` WHERE panel_run_id='$PANEL'" \
        | tail -1 | tr -d '[:space:]')
      [ "${N:-0}" = 0 ] || { echo "ABORT: $PANEL already has $N $TABLE rows"; exit 2; }
    done
    N=$({ gcloud storage ls "gs://${PROJECT}-raw/cand_scores/${PANEL}/*.npz" 2>/dev/null || true; } | wc -l)
    [ "$N" -eq 0 ] || { echo "ABORT: $PANEL already has $N artifacts"; exit 2; }
  done
done

# Exercise the more complex treatment cache and the conditionally inherited
# allocation branch for one week before releasing the 30 registered cells.
SMOKE_JOB=replay-sis-pass-tail-e80-smoke
SMOKE_ENVS="$(common_env treatment 0 2024)|CODE_SHA=$CODE_SHA"
SMOKE_ENVS="$SMOKE_ENVS|REPLAY_LINEUPS_TABLE=$PROJECT.nfl_features.replay_lineups_sis_pass_tail_e80_smoke"
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "replay,--season,2024,--contest,gpp,--entries,80,--field-size,500,--max-weeks,1" \
  --set-env-vars "^|^$SMOKE_ENVS" --memory 32Gi --cpu 8 --max-retries 0 \
  --task-timeout 14400 >/dev/null
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$SMOKE_EXEC" ] || { echo "ABORT: pass-tail smoke execution missing"; exit 1; }
printf '%s %s\n' "$SMOKE_JOB" "$SMOKE_EXEC" > "$OUT/preflight.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$SMOKE_EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || { echo "ABORT: pass-tail smoke failed"; exit 1; }
  sleep 30
done

ACTIVE_EXECUTIONS=()
wait_for_capacity() {
  local execution state
  local still_active=()
  while true; do
    still_active=()
    for execution in "${ACTIVE_EXECUTIONS[@]}"; do
      state=$(gcloud run jobs executions describe "$execution" \
        --project "$PROJECT" --region "$REGION" \
        --format='value(status.conditions[0].status)')
      case "$state" in
        True) ;;
        False) echo "ABORT: $execution failed during release" >&2; exit 1 ;;
        *) still_active+=("$execution") ;;
      esac
    done
    ACTIVE_EXECUTIONS=("${still_active[@]}")
    [ "${#ACTIVE_EXECUTIONS[@]}" -lt "$MAX_IN_FLIGHT" ] && return
    sleep 60
  done
}

for ARM in control treatment; do
  for REP in 0 1 2 3 4; do
    PANEL="20260814-sis-pass-tail-${ARM}-r${REP}-v1"
    for SEASON in 2023 2024 2025; do
      wait_for_capacity
      FAMILY="sispt${ARM:0:1}${REP}"
      JOB="replay-${FAMILY}-${SEASON}"
      ENVS="$(common_env "$ARM" "$REP" "$SEASON")"
      ENVS="$ENVS|PANEL_RUN_ID=$PANEL|CODE_SHA=$CODE_SHA"
      ENVS="$ENVS|CAND_LOG_TABLE=$PROJECT.nfl_predictions.replay_candidates_staging"
      ENVS="$ENVS|CAND_FEATURE_TABLE=$PROJECT.nfl_predictions.slate_player_features"
      ENVS="$ENVS|CAND_ARTIFACT_BUCKET=${PROJECT}-raw|CAND_ARTIFACT_PLAYER_WORLDS=1"
      ENVS="$ENVS|REPLAY_LINEUPS_TABLE=$PROJECT.nfl_features.replay_lineups_${FAMILY}_${SEASON}"
      gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
        --image "$IMG" --command nfl-dfs \
        --args "replay,--season,$SEASON,--contest,gpp,--entries,80" \
        --set-env-vars "^|^$ENVS" --memory 32Gi --cpu 8 --max-retries 0 \
        --task-timeout 14400 >/dev/null
      EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
        --region "$REGION" --async --format='value(metadata.name)')
      [ -n "$EXEC" ] || { echo "ABORT: no execution for $JOB"; exit 1; }
      gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
        --region "$REGION" --format=json \
        | "$ROOT/.venv/bin/python" "$ROOT/scripts/verify_tabpfn_sis_pass_tail_exact80_execution.py" \
          --arm "$ARM" --replicate "$REP" --season "$SEASON" \
          --panel "$PANEL" --job "$JOB" --execution "$EXEC" \
          --image "$IMG" --code-sha "$CODE_SHA" --phase-s-arm "$PHASE_S_ARM" \
          --allow-nonterminal
      printf '%s %s %s %s %s %s\n' \
        "$ARM" "$REP" "$SEASON" "$PANEL" "$JOB" "$EXEC" | tee -a "$OUT/executions.txt"
      ACTIVE_EXECUTIONS+=("$EXEC")
    done
  done
done
echo "TABPFN_SIS_PASS_TAIL_EXACT80_V1_LAUNCHED $RUN_ID phase_s_arm=$PHASE_S_ARM"
