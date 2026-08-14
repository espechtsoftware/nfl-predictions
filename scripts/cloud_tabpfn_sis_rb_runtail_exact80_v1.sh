#!/bin/bash
# Launch the frozen conditional SIS RB run-tail five-seed exact-80 comparison.
# Usage: cloud_tabpfn_sis_rb_runtail_exact80_v1.sh <IMAGE@sha256:...> <40-char SHA>
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
IMG=${1:-}
CODE_SHA=${2:-}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260814-sis-runtail-exact80-v1
OUT="$ROOT/reports/tabpfn-sis-rb-runtail-runs/$RUN_ID"
CACHE="$ROOT/reports/tabpfn-sis-rb-runtail-runs/20260814-tabpfn-sis-rb-runtail-v1/validation.json"
FINAL="$ROOT/reports/tabpfn-sis-rb-runtail-runs/20260814-tabpfn-sis-rb-runtail-final-served-v1/report.json"
PROTOCOL="$ROOT/reports/2026-08-14-sis-run-tail-marginal-protocol.md"
ADDENDUM="$ROOT/reports/2026-08-14-sis-run-tail-exact80-addendum.md"
MAX_IN_FLIGHT=${SIS_RB_RUNTAIL_MAX_IN_FLIGHT:-10}

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable generation image required"; exit 2;; esac
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full immutable generation code SHA required"; exit 2; }
for path in "$CACHE" "$FINAL" "$PROTOCOL" "$ADDENDUM"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT" ] || { echo "ABORT: immutable run-tail panel already exists"; exit 2; }
case "$MAX_IN_FLIGHT" in
  ''|*[!0-9]*) echo "ABORT: SIS_RB_RUNTAIL_MAX_IN_FLIGHT must be an integer"; exit 2 ;;
esac
[ "$MAX_IN_FLIGHT" -ge 1 ] && [ "$MAX_IN_FLIGHT" -le 10 ] || {
  echo "ABORT: run-tail in-flight cap must be between 1 and 10"; exit 2; }

mapfile -t SCHEDULE_JSON < <(
  "$ROOT/.venv/bin/python" - "$CACHE" "$FINAL" <<'PY'
import json
import math
import sys

cache = json.load(open(sys.argv[1], encoding="utf-8"))
final = json.load(open(sys.argv[2], encoding="utf-8"))
if cache.get("disposition") != "tabpfn-sis-rb-runtail-caches-valid" or \
        not cache.get("passes") or \
        not cache.get("control_reproduction", {}).get("passes") or \
        cache.get("adaptive_retrospective") is not True:
    raise SystemExit("ABORT: run-tail cache validation did not pass")
gate = final.get("gate", {})
if final.get("disposition") != "tabpfn-sis-rb-runtail-final-served-passes" or \
        not gate.get("passes") or \
        not gate.get("equal_q95_q99_mean_ratio_below_1") or \
        not gate.get("maximum_mean_delta_at_most_1e_10"):
    raise SystemExit("ABORT: run-tail final-served gate did not pass")
if final.get("adaptive_retrospective") is not True or \
        final.get("label_law") != "active_only" or \
        final.get("feature_law") != "base" or \
        final.get("primary_population") != "active RB":
    raise SystemExit("ABORT: run-tail final-served law differs")
if final.get("cache_tables") != {
        "control": "tabpfn_sis_rb_runtail_control_v1",
        "treatment": "tabpfn_sis_rb_runtail_treatment_v1"}:
    raise SystemExit("ABORT: run-tail cache identities differ")
usage = final.get("common_usage_law", {})
if usage.get("game_sim_usage") != "dirichlet" or \
        usage.get("k") != "28.154043586960896":
    raise SystemExit("ABORT: run-tail usage law differs")
mean_deltas = final.get("maximum_mean_delta", {})
if set(mean_deltas) != {"control", "treatment"} or any(
        not math.isfinite(float(mean_deltas[name])) or
        abs(float(mean_deltas[name])) > 1e-10
        for name in ("control", "treatment")):
    raise SystemExit("ABORT: run-tail mean preservation differs")
simulation = final.get("simulation", {})
required_simulation = {
    "n_sims": 10000, "seed": 0, "model_ensemble": 1,
    "game_sim_mode": "possession", "blend_model_weight": 0.45,
    "position_factor_grid": "0.750:0.005:1.500",
}
if any(simulation.get(key) != value for key, value in required_simulation.items()):
    raise SystemExit("ABORT: run-tail simulation contract differs")

def schedules(name):
    source = final.get(f"{name}_schedule", {})
    if set(source) != {"2023", "2024", "2025"}:
        raise SystemExit(f"ABORT: {name} schedule seasons differ")
    output = {}
    for season in (2023, 2024, 2025):
        row = source[str(season)]
        calibration = row.get("calibration_seasons")
        if not calibration or any(int(value) >= season for value in calibration):
            raise SystemExit(f"ABORT: {name} {season} schedule violates PIT")
        factors = row.get("factors", {})
        if set(factors) != {"QB", "RB", "TE", "WR"}:
            raise SystemExit(f"ABORT: {name} {season} factor keys differ")
        values = [float(factors[position]) for position in ("QB", "RB", "TE", "WR")]
        if any(not math.isfinite(value) or value < .75 or value > 1.5
               for value in values):
            raise SystemExit(f"ABORT: {name} {season} factors outside grid")
        output[str(season)] = ",".join(
            f"{position}:{value:g}"
            for position, value in zip(("QB", "RB", "TE", "WR"), values)
        )
    return output

print(json.dumps(schedules("control"), separators=(",", ":"), sort_keys=True))
print(json.dumps(schedules("treatment"), separators=(",", ":"), sort_keys=True))
PY
)
[ "${#SCHEDULE_JSON[@]}" = 2 ] || { echo "ABORT: schedule serialization failed"; exit 2; }
CONTROL_SCHEDULES_JSON=${SCHEDULE_JSON[0]}
TREATMENT_SCHEDULES_JSON=${SCHEDULE_JSON[1]}

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "generation_image=$IMG" "generation_code_sha=$CODE_SHA" \
  "cache_validation_sha256=$(sha256sum "$CACHE" | awk '{print $1}')" \
  "final_served_report_sha256=$(sha256sum "$FINAL" | awk '{print $1}')" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "addendum_sha256=$(sha256sum "$ADDENDUM" | awk '{print $1}')" \
  "control_schedules_json=$CONTROL_SCHEDULES_JSON" \
  "treatment_schedules_json=$TREATMENT_SCHEDULES_JSON" \
  'adaptive_retrospective=true' 'arms=control treatment' \
  'replicates=R0 R1 R2 R3 R4' 'seasons=2023 2024 2025' \
  'n_entries=80' 'n_sims=10000' 'dirichlet_k=28.154043586960896' \
  'tail_order=240 230 220 210 200 194 187' > "$OUT/manifest.txt"
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
  "$ROOT/.venv/bin/python" - "$1" "$2" "$CONTROL_SCHEDULES_JSON" \
    "$TREATMENT_SCHEDULES_JSON" <<'PY'
import json
import sys
arm, season = sys.argv[1:3]
source = json.loads(sys.argv[3] if arm == "control" else sys.argv[4])
print(source[season], end="")
PY
}
table_spec() {
  [ "$1" = control ] && printf '%s' tabpfn_sis_rb_runtail_control_v1 || \
    printf '%s' tabpfn_sis_rb_runtail_treatment_v1
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
  printf '%s' "$ENVS"
}

# Fail before allocating compute if any registered destination is nonempty.
for ARM in control treatment; do
  for REP in 0 1 2 3 4; do
    PANEL="20260814-sis-runtail-${ARM}-r${REP}-v1"
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

# Exercise the treatment cache and its exact served schedule before release.
SMOKE_JOB=replay-sis-runtail-e80-smoke
SMOKE_ENVS="$(common_env treatment 0 2024)|CODE_SHA=$CODE_SHA"
SMOKE_ENVS="$SMOKE_ENVS|REPLAY_LINEUPS_TABLE=$PROJECT.nfl_features.replay_lineups_sis_runtail_e80_smoke"
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "replay,--season,2024,--contest,gpp,--entries,80,--field-size,500,--max-weeks,1" \
  --set-env-vars "^|^$SMOKE_ENVS" --memory 32Gi --cpu 8 --max-retries 0 \
  --task-timeout 14400 >/dev/null
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$SMOKE_EXEC" ] || { echo "ABORT: run-tail smoke execution missing"; exit 1; }
printf '%s %s\n' "$SMOKE_JOB" "$SMOKE_EXEC" > "$OUT/preflight.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$SMOKE_EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = True ] && break
  [ "$STATE" != False ] || { echo "ABORT: run-tail smoke failed"; exit 1; }
  sleep 30
done

ACTIVE_EXECUTIONS=()
checkpoint_execution_ledger() {
  local count ledger_rel
  ledger_rel=${OUT#"$ROOT"/}
  count=$(wc -l < "$OUT/executions.txt" | tr -d '[:space:]')
  git -C "$ROOT" add -- "$ledger_rel"
  git -C "$ROOT" commit --only \
    -m "Checkpoint run-tail at $count released cells" -- "$ledger_rel"
  git -C "$ROOT" push origin HEAD
}
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
    PANEL="20260814-sis-runtail-${ARM}-r${REP}-v1"
    for SEASON in 2023 2024 2025; do
      wait_for_capacity
      FAMILY="sisrt${ARM:0:1}${REP}"
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
        | "$ROOT/.venv/bin/python" "$ROOT/scripts/verify_tabpfn_sis_rb_runtail_exact80_execution.py" \
          --arm "$ARM" --replicate "$REP" --season "$SEASON" \
          --panel "$PANEL" --job "$JOB" --execution "$EXEC" \
          --image "$IMG" --code-sha "$CODE_SHA" \
          --control-schedules-json "$CONTROL_SCHEDULES_JSON" \
          --treatment-schedules-json "$TREATMENT_SCHEDULES_JSON" \
          --allow-nonterminal
      printf '%s %s %s %s %s %s\n' \
        "$ARM" "$REP" "$SEASON" "$PANEL" "$JOB" "$EXEC" | tee -a "$OUT/executions.txt"
      checkpoint_execution_ledger
      ACTIVE_EXECUTIONS+=("$EXEC")
    done
  done
done
echo "TABPFN_SIS_RB_RUNTAIL_EXACT80_V1_LAUNCHED $RUN_ID"
