#!/usr/bin/env bash
# Print (and, with --run, execute) the one-shot user timers for a regular-season Sunday.  The commands use tracked
# entrypoints and pass every path explicitly; they do not depend on deleted /home/erich/week<W>-sunday-* wrappers.
#
#   scripts/arm_week_timers.sh 3             # print the Week-3 commands
#   scripts/arm_week_timers.sh 3 --run       # preflight, then arm them (operator action)
#
# The build doses are explicit environment values so a missing or stale dose file cannot silently turn the D3200 slot
# into a D800 build.  Adjust the D*_LEV/D*_BOOM variables for a tested plan before arming (lev 0 is a dose).
#
# Week-4 additions (laptop host, 2026-09-28):
#   SKIP_UNITS="d6400sat d6400"   keys of units NOT to arm (d12800sat d6400sat d6400 d3200 t70 watchers); a laptop cannot
#                                 run overlapping heavy builds without slowing the T-70 build it depends on
#   T70_MIN_PROJ_CT=10:30         the T-70 build refuses a projection batch generated before this Sunday CT time
#                                 (check_build_inputs --min-generated-at): the hourly 10:03 batch is fresh and pre-inactives
#   T70_PROJECT=1                 also arm the T-70 DK pull (T70_PULL_CT, default 10:33) and the project-slate execution
#                                 with the T-70 rules (T70_PROJECT_CT, default 10:36; ~3 min) -- operator-armed like the rest
#
# 2026-10-05 (reviewer; every paid page, every week): the Fantasy Points projection tables are captured pre-lock by
# scripts/fp_projections_capture.sh -- once at arming (--run, after every timer is armed; a failure is loud and does not
# stop the arming) and by the unit nfl-week<W>-fp-projections at FP_PROJ_CT (default 10:40 CT: after the 10:30 inactives,
# before the 10:50 T-70 build). SKIP_UNITS key: fpproj (skips both). Capture only; no build reads them.
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WEEK=${1:?usage: arm_week_timers.sh WEEK [--run]}
RUN=${2:-}
SEASON=${SEASON:-2026}
PROD=${PROD:-$(cd -- "$SCRIPT_DIR/.." && pwd)}
CLONE=${CLONE:-${NFL2_LIVE_CLONE:-/home/erich/projects/.nfl2-worktrees/week4-live-center}}
EXPECT_SHA=${EXPECT_SHA:-${NFL2_EXPECT_SHA:-e7255e98bf87297452befb61fb508ad4b368b59f}}
PROD_PY=${PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
TOOLS=${TOOLS:-$PROD/scripts}
OUT=${OUT:-/home/erich/week${WEEK}-sunday}
CONTESTS_JSON=${CONTESTS_JSON:-$OUT/contests.json}
DRIVER=${DRIVER:-$SCRIPT_DIR/run_week_build.sh}
WATCHER=${WATCHER:-$SCRIPT_DIR/run_week_watchers.sh}
INGEST_LOOP=${INGEST_LOOP:-$SCRIPT_DIR/host_ingest_dk_loop.sh}
FP_PROJ_CAPTURE=${FP_PROJ_CAPTURE:-$SCRIPT_DIR/fp_projections_capture.sh}
CODE_TAG=${RUN_SUFFIX:-${EXPECT_SHA:0:7}}
FIXTURE_SHA=e7255e98bf87297452befb61fb508ad4b368b59f
if [[ "$RUN" == "--run" && "$EXPECT_SHA" == "$FIXTURE_SHA" && "${ALLOW_FIXTURE_PIN:-0}" != "1" ]]; then
  echo "refusing to arm Week $WEEK with the compatibility fixture EXPECT_SHA=$FIXTURE_SHA; export the approved Week-3 pin (or set ALLOW_FIXTURE_PIN=1 only for a deliberate rehearsal)" >&2
  exit 2
fi
# 2026-09-29: GROUP must be explicit when arming. Without it every unit auto-detects it through the `bq` CLI, which the
# systemd --user PATH does not contain (the gcloud SDK lives in ~/google-cloud-sdk/bin): week_env failed in every unit.
if [[ "$RUN" == "--run" && -z "${GROUP:-}" ]]; then
  echo "refusing to arm Week $WEEK without GROUP (the Sunday-main draft group id, e.g. GROUP=154078)" >&2
  exit 2
fi

SUNDAY=$(date -u -d "2026-09-13 + $(( (WEEK - 1) * 7 )) days" +%Y-%m-%d)
SATURDAY=$(date -u -d "$SUNDAY - 1 day" +%Y-%m-%d)
# Timer calendars use America/Chicago.  Tags use the same instant in UTC so receipts can be compared across hosts.
tag() { local t; t=$(TZ=America/Chicago date -d "$SUNDAY $1" +%s); echo "$(date -u -d "@$t" +%Y%m%dt%H%Mz)-$2-$CODE_TAG"; }
sat() { local t; t=$(TZ=America/Chicago date -d "$SATURDAY $1" +%s); echo "$(date -u -d "@$t" +%Y%m%dt%H%Mz)-$2-$CODE_TAG"; }

D12800_LEV=${D12800_LEV:-2560}; D12800_BOOM=${D12800_BOOM:-10240}
D6400_LEV=${D6400_LEV:-1280}; D6400_BOOM=${D6400_BOOM:-5120}
D3200_LEV=${D3200_LEV:-640}; D3200_BOOM=${D3200_BOOM:-2560}
D800_LEV=${D800_LEV:-160}; D800_BOOM=${D800_BOOM:-640}

U12800="nfl-week${WEEK}-d12800-sat-build"
U6400SAT="nfl-week${WEEK}-d6400-sat-build"
U6400="nfl-week${WEEK}-d6400-build"
U3200="nfl-week${WEEK}-d3200-build"
U800="nfl-week${WEEK}-t70-build"
UW="nfl-week${WEEK}-watchers"
UI="nfl-week${WEEK}-host-dk-ingest"
UFPPROJ="nfl-week${WEEK}-fp-projections"

GCP_PROJECT=${GCP_PROJECT:-nfl-predictions-503414}
# GCP_PROJECT rides every unit: the Week-3 D12800 died in 5 s without it (systemd-run does not inherit the shell's env).
# PATH rides every unit too: systemd-run --user units get /usr/bin:/bin-style PATHs without the gcloud SDK (bq, gcloud).
BASE_ENV=(env "GCP_PROJECT=$GCP_PROJECT" "PATH=$PATH"
  "SEASON=$SEASON" "WEEK=$WEEK" "PROD=$PROD" "CLONE=$CLONE" "EXPECT_SHA=$EXPECT_SHA"
  "PROD_PY=$PROD_PY" "LAB_PY=$LAB_PY" "TOOLS=$TOOLS" "OUT=$OUT" "CONTESTS_JSON=$CONTESTS_JSON"
  "RUN_SUFFIX=$CODE_TAG")
[[ -n "${GROUP:-}" ]] && BASE_ENV+=("GROUP=$GROUP")
[[ -n "${CHOSEN_FILE:-}" ]] && BASE_ENV+=("CHOSEN_FILE=$CHOSEN_FILE")
[[ -n "${WIN_DOWNLOADS:-}" ]] && BASE_ENV+=("WIN_DOWNLOADS=$WIN_DOWNLOADS")
[[ -n "${ENTER_LAYOUT:-}" ]] && BASE_ENV+=("ENTER_LAYOUT=$ENTER_LAYOUT")
[[ -n "${ENTER_ORDER:-}" ]] && BASE_ENV+=("ENTER_ORDER=$ENTER_ORDER")
[[ -n "${LIVE_FLEX_LATEST:-}" ]] && BASE_ENV+=("LIVE_FLEX_LATEST=$LIVE_FLEX_LATEST")
[[ -n "${OWNERSHIP_SETS:-}" ]] && BASE_ENV+=("OWNERSHIP_SETS=$OWNERSHIP_SETS")
for v in ENTER_FLAG_LATE_Q_ONLY T70_ACTIVE_Q T70_VACATED_BUMP LIVE_SELECTOR TAIL_LINE LIVE_MIN_PROJ MEAN_OWN_TILT MEAN_OWN_SOURCE MEAN_DST_CAP TAIL_SLEEVE_SELECTOR CLASS_MODEL CLASS_SLEEVE_EVERY UNION_SATURDAY_RUN UNION_SAT_DOSE UNION_PMO UNION_PMO_CAP UNION_MAIN UNION_PROJ_SOURCE UNION_MIX_PORTFOLIO UNION_MIX_SPARES UNION_MAIN_CAP UNION_SLEEVE_CAP UNION_MAIN_OWN_TILT UNION_MAIN_OWN_LAG_TILT OWNERSHIP_LAG LINESTAR_DIR UNION_MAIN_OWN_PREDICTOR TABPFN_PY OWNERSHIP_LAGS OWN_TABPFN_ROWS OWN_TABPFN_ROWS_2026 ENTER_SMALL_MAX_SHARED ENTER_SMALL_OVERLAP_MAX_ENTRIES LEV_CBC_THREADS UNION_MAIN_DST_CAP UNION_MAIN_QB_CAP_ROWS UNION_SLEEVE_INCLUDES_MAIN UNION_SLEEVE_SOURCE UNION_SLEEVE_FIELD_MODE UNION_SLEEVE_MAX_PER_GAME UNION_SLEEVE_FIELD_ROWS UNION_DK_STATUS FP_MAX_AGE_HOURS \
         ENTRIES_END_CT MAX_PER_GAME MIN_LINEUP_SALARY CASH_SHADOW CASH_SHADOW_N REQUIRE_AUDIT_PASSED; do
  [[ -n "${!v:-}" ]] && BASE_ENV+=("$v=${!v}")
done
[[ -n "${ALLOW_FIXTURE_PIN:-}" ]] && BASE_ENV+=("ALLOW_FIXTURE_PIN=$ALLOW_FIXTURE_PIN")

# The selection-only shadow is approved for the Saturday D12800 build only. Keep it out of the fallback and Sunday
# rebuilds so a later, cheaper book cannot overwrite the prelock shadow record. Promotion belongs to the persistent
# watcher, which runs the after-build chain once the chosen dose is known.
SHADOW_FLAGS=()
[[ -n "${RUN_WEEK3_SHADOW:-}" ]] && SHADOW_FLAGS+=("RUN_WEEK3_SHADOW=$RUN_WEEK3_SHADOW")
[[ -n "${SHADOW_OUT:-}" ]] && SHADOW_FLAGS+=("SHADOW_OUT=$SHADOW_OUT")
[[ -n "${SHADOW_LABEL:-}" ]] && SHADOW_FLAGS+=("SHADOW_LABEL=$SHADOW_LABEL")
WATCH_FLAGS=()
[[ -n "${PROMOTE_FIRST_ENTRY:-}" ]] && WATCH_FLAGS+=("PROMOTE_FIRST_ENTRY=$PROMOTE_FIRST_ENTRY")
[[ -n "${RUN_FIRST_PROMOTION:-}" ]] && WATCH_FLAGS+=("RUN_FIRST_PROMOTION=$RUN_FIRST_PROMOTION")

L12800=("${BASE_ENV[@]}" "${SHADOW_FLAGS[@]}" "PAID_LEV=$D12800_LEV" "PAID_BOOM=$D12800_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(sat 10:30 d12800sat)" "$DRIVER")
L6400SAT=("${BASE_ENV[@]}" "PAID_LEV=$D6400_LEV" "PAID_BOOM=$D6400_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(sat 10:35 d6400sat)" "$DRIVER")
L6400=("${BASE_ENV[@]}" "PAID_LEV=$D6400_LEV" "PAID_BOOM=$D6400_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 05:30 d6400)" "$DRIVER")
# sweep item 12: the 09:10 build is the floor only until the T-70 build starts; if it finishes later its dirs are marked
# superseded (the watcher never publishes them), so a slow 09:10 union can never displace the T-70 union.
SUPERSEDE_T70=$(date -u -d "@$(TZ=America/Chicago date -d "$SUNDAY ${T70_BUILD_CT:-10:50}" +%s)" +%Y-%m-%dT%H:%M:%S)
L3200=("${BASE_ENV[@]}" "SUPERSEDE_AFTER_UTC=$SUPERSEDE_T70" "PAID_LEV=$D3200_LEV" "PAID_BOOM=$D3200_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 09:10 d3200)" "$DRIVER")
T70_GATE=()
if [[ -n "${T70_MIN_PROJ_CT:-}" ]]; then
  T70_GATE=("MIN_PROJ_GENERATED_AT=$(date -u -d "@$(TZ=America/Chicago date -d "$SUNDAY $T70_MIN_PROJ_CT" +%s)" +%Y-%m-%dT%H:%M:%S+00:00)")
fi
L800=("${BASE_ENV[@]}" "${T70_GATE[@]}" "PAID_LEV=$D800_LEV" "PAID_BOOM=$D800_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 10:50 d800)" "$DRIVER")
LW=("${BASE_ENV[@]}" "${WATCH_FLAGS[@]}" "$WATCHER")
HI=("${BASE_ENV[@]}" "$INGEST_LOOP")
FP_PROJ_CT=${FP_PROJ_CT:-10:40}
LFPPROJ=("${BASE_ENV[@]}" "$FP_PROJ_CAPTURE" sunday-prelock)
GCLOUD=${GCLOUD:-$(command -v gcloud || echo "$HOME/google-cloud-sdk/bin/gcloud")}
NFL_DFS_CLI=${NFL_DFS_CLI:-$PROD/.venv/bin/nfl-dfs}
T70_PULL_CT=${T70_PULL_CT:-10:33}; T70_PROJECT_CT=${T70_PROJECT_CT:-10:36}
UPULL="nfl-week${WEEK}-t70-pull"; UPROJ="nfl-week${WEEK}-t70-project"
LPULL=(env "GCP_PROJECT=$GCP_PROJECT" "PYTHONPATH=$PROD/src" "$NFL_DFS_CLI" ingest-dk)
LPROJ=("$GCLOUD" run jobs execute project-slate --project "$GCP_PROJECT" --region us-central1
       --update-env-vars T70_ACTIVE_Q=1,T70_VACATED_BUMP=1 --wait)
# The Sunday-early supply (operator 2026-10-01: 8 threads make the D12800 ~2 h, so it can be built on Sunday's pre-dawn
# information): EARLY_SUPPLY_CT=HH:MM arms a props pull (EARLY_PROPS_CT, default 03:45), a project-slate execution
# (EARLY_PROJECT_CT, default 04:00; no T-70 flags) and a second D12800 (UNION's 2560/10240 dose) at EARLY_SUPPLY_CT. The
# union takes the NEWEST qualifying supply (this one if it finished, else Saturday's D12800, else the D6400). No MIN_PROJ
# gate: if the refresh fails it builds on the newest projections there are, and the build log says which.
EARLY_PROPS_CT=${EARLY_PROPS_CT:-03:45}; EARLY_PROJECT_CT=${EARLY_PROJECT_CT:-04:00}
UEPROPS="nfl-week${WEEK}-early-props"; UEPROJ="nfl-week${WEEK}-early-project"; U12800SUN="nfl-week${WEEK}-d12800-sun-build"
LEPROPS=("$GCLOUD" run jobs execute ingest-props --project "$GCP_PROJECT" --region us-central1 --wait)
LEPROJ=("$GCLOUD" run jobs execute project-slate --project "$GCP_PROJECT" --region us-central1 --wait)
if [[ -n "${EARLY_SUPPLY_CT:-}" ]]; then
  L12800SUN=("${BASE_ENV[@]}" "PAID_LEV=$D12800_LEV" "PAID_BOOM=$D12800_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag "$EARLY_SUPPLY_CT" d12800sun)" "$DRIVER")
fi
SKIP_UNITS=${SKIP_UNITS:-}
for k in $SKIP_UNITS; do
  [[ " d12800sat d6400sat d6400 d3200 t70 watchers d12800sun earlyrefresh fpproj " == *" $k "* ]] || { echo "SKIP_UNITS: unknown unit key $k" >&2; exit 2; }
done
# arm KEY "DATE HH:MM" UNIT ARRAY: print the systemd-run line (or a SKIPPED comment); with --run, also execute it.
arm() {
  local key=$1 cal=$2 unit=$3; local -n cmd=$4
  if [[ " $SKIP_UNITS " == *" $key "* ]]; then echo "# SKIPPED ($key): $unit"; return 0; fi
  echo "systemd-run --user --on-calendar=\"$cal America/Chicago\" --unit=\"$unit\" ${cmd[*]}"
  if [[ "$RUN" == "--run" ]]; then systemd-run --user --on-calendar="$cal America/Chicago" --unit="$unit" "${cmd[@]}"; fi
}
CHECK_BUILD=("${BASE_ENV[@]}" "$DRIVER" --check)
CHECK_WATCH=("${BASE_ENV[@]}" "${WATCH_FLAGS[@]}" "$WATCHER" --check)
HOST_LINE="# HOST_INGEST=1 enables the tracked hourly DraftKings fallback after its --check"
if [[ "${HOST_INGEST:-0}" == "1" ]]; then
  HOST_LINE="systemd-run --user --unit=\"$UI\" ${HI[*]}"
fi

cat <<EOT
# Week $WEEK (America/Chicago), Sunday $SUNDAY; code tag $CODE_TAG
# Main book: UNION_MAIN=${UNION_MAIN:-(week_env default)}$( [[ "${UNION_MAIN:-}" == "mix" ]] && echo " PORTFOLIO=${UNION_MIX_PORTFOLIO:-UNSET (refused at arming)}"); projections: ${UNION_PROJ_SOURCE:-ours}
# Before arming: refresh build-features -> tabpfn-gen -> project-slate for ${SEASON}:${WEEK}, fill $CONTESTS_JSON,
# and create $OUT/chosen-dose.env with CHOSEN_LEV/CHOSEN_BOOM.  The watcher fails closed without that file.
#
# Refresh (operator, in this order, after the props pull):
gcloud run jobs execute build-features --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute tabpfn-gen --project nfl-predictions-503414 --region us-central1 --update-env-vars TABPFN_UPCOMING=${SEASON}:${WEEK} --wait
gcloud run jobs execute project-slate --project nfl-predictions-503414 --region us-central1 --wait
# then, when ENTER_ORDER=fewest-low, the Saturday sets file (the preflight refuses to arm without it):
PYTHONPATH=\$PROD/src \$PROD_PY \$PROD/scripts/ownership_sets.py sets --week ${WEEK} --group \${GROUP} --out \${OWNERSHIP_SETS}
# the ownership term (UNION_MAIN_OWN_TILT > 0): Saturday's lag-model file, its gate (sum >= 280), and a LineStar capture:
PYTHONPATH=\$PROD/src \$PROD_PY \$PROD/scripts/ownership_sets.py sets --season ${SEASON:-2026} --week ${WEEK} --group \${GROUP} --lag-features --out ${OUT}/ownership_lag.csv
\$PROD_PY \$PROD/scripts/check_ownership_lag.py ${OUT}/ownership_lag.csv
\$PROD_PY \$PROD/scripts/linestar_ownership_capture.py --season ${SEASON:-2026} --week ${WEEK} --out ${OUT}/linestar --label saturday
# with UNION_MAIN_OWN_PREDICTOR=tabpfn or fp (TabPFN is fp's first fallback): Saturday's lags (BigQuery) -- the Sunday unions then fit on the laptop GPU:
PYTHONPATH=\$PROD/src \$PROD_PY \$PROD/scripts/ownership_tabpfn.py lags --season ${SEASON:-2026} --week ${WEEK} --out ${OUT}/ownership_lags.csv
#
# Saturday $SATURDAY: D12800 at 10:30 CT, D6400 fallback at 10:35 CT; Sunday: D6400 05:30 CT, D3200 09:10 CT,
# D800 T-70 at 10:50 CT, persistent watchers at 09:12 CT, FP projections capture at $FP_PROJ_CT CT$( [[ "${T70_PROJECT:-0}" == 1 ]] && echo "; T-70 DK pull $T70_PULL_CT CT, T-70 project-slate $T70_PROJECT_CT CT")$( [[ -n "${T70_MIN_PROJ_CT:-}" ]] && echo "; the T-70 build needs projections generated after $T70_MIN_PROJ_CT CT").
EOT

if [[ "$RUN" == "--run" ]]; then
  echo "running build and watcher preflights before arming timers"
  "${CHECK_BUILD[@]}"
  "${CHECK_WATCH[@]}"
  if [[ "${HOST_INGEST:-0}" == "1" ]]; then
    "$INGEST_LOOP" --check
  fi
  if [[ "${UNION_MAIN_OWN_TILT:-0}" != "0" ]]; then
    # reviewer gate 4: never arm the term on a collapsed or missing lag file
    "$PROD_PY" "$PROD/scripts/check_ownership_lag.py" "${OWNERSHIP_LAG:-$OUT/ownership_lag.csv}" || exit 2
  fi
  if [[ "${UNION_MAIN_OWN_PREDICTOR:-blend}" == "tabpfn" || "${UNION_MAIN_OWN_PREDICTOR:-blend}" == "fp" ]]; then
    # the TabPFN predictor (fp's first fallback): its env, a CUDA device, the pinned rows file and Saturday's lags must all be present at arming
    TPY=${TABPFN_PY:-$HOME/.local/tabpfn311-gpu/bin/python}
    "$TPY" -c "import torch, tabpfn; assert torch.cuda.is_available(), 'no CUDA'" || { echo "TABPFN PREFLIGHT FAILED: $TPY cannot see a CUDA device or tabpfn" >&2; exit 2; }
    [[ "$(sha256sum "${OWN_TABPFN_ROWS:-$OUT/private/l23_rows.parquet}" 2>/dev/null | cut -d' ' -f1)" == 0bec4237eb4c4bc1228571e5628685b3cc26e8aaed433f8b8f2056d5062edde9 ]] \
      || { echo "TABPFN PREFLIGHT FAILED: the L23 rows file is missing or not sha 0bec4237" >&2; exit 2; }
    [[ -s "${OWNERSHIP_LAGS:-$OUT/ownership_lags.csv}" ]] || { echo "TABPFN PREFLIGHT FAILED: Saturday's lags file is missing (ownership_tabpfn.py lags)" >&2; exit 2; }
  fi
  if [[ "${UNION_MAIN_OWN_PREDICTOR:-blend}" == "fp" ]]; then
    # Fantasy Points' ownership (operator 10-02): the saved FP session must verify at arming; Sunday falls back loudly if not
    ( cd "$PROD" && PYTHONPATH="$PROD/src" "$PROD_PY" -m nfl_dfs.ops.fantasy_points_ownership verify-login >/dev/null 2>&1 ) \
      || { echo "FP PREFLIGHT FAILED: the Fantasy Points session does not verify (fantasy-points-ownership login --terminal-credentials)" >&2; exit 2; }
  fi
  if [[ -n "${EARLY_SUPPLY_CT:-}" ]]; then
    [[ -x "$GCLOUD" ]] || { echo "gcloud not executable: $GCLOUD (the Sunday-early refresh needs it)" >&2; exit 2; }
  fi
  if [[ "${T70_PROJECT:-0}" == "1" ]]; then
    [[ -x "$GCLOUD" ]] || { echo "gcloud not executable: $GCLOUD" >&2; exit 2; }
    [[ -x "$NFL_DFS_CLI" ]] || { echo "nfl-dfs CLI not executable: $NFL_DFS_CLI" >&2; exit 2; }
  fi
fi
arm d12800sat "$SATURDAY 10:30" "$U12800" L12800
arm d6400sat "$SATURDAY 10:35" "$U6400SAT" L6400SAT
arm d6400 "$SUNDAY 05:30" "$U6400" L6400
arm d3200 "$SUNDAY 09:10" "$U3200" L3200
arm t70 "$SUNDAY 10:50" "$U800" L800
arm watchers "$SUNDAY 09:12" "$UW" LW
arm fpproj "$SUNDAY $FP_PROJ_CT" "$UFPPROJ" LFPPROJ
if [[ -n "${EARLY_SUPPLY_CT:-}" ]]; then
  arm earlyrefresh "$SUNDAY $EARLY_PROPS_CT" "$UEPROPS" LEPROPS
  arm earlyrefresh "$SUNDAY $EARLY_PROJECT_CT" "$UEPROJ" LEPROJ
  arm d12800sun "$SUNDAY $EARLY_SUPPLY_CT" "$U12800SUN" L12800SUN
fi
if [[ "${T70_PROJECT:-0}" == "1" ]]; then
  arm t70pull "$SUNDAY $T70_PULL_CT" "$UPULL" LPULL
  arm t70project "$SUNDAY $T70_PROJECT_CT" "$UPROJ" LPROJ
fi
# The Saturday pre-lock snapshot of the FP projection pages, AFTER every arm() call (reviewer 10-05: a slow FP site must
# never delay arming a build whose time is near): loud on failure, never a reason to stop.
if [[ "$RUN" == "--run" && " $SKIP_UNITS " != *" fpproj "* ]]; then
  "${BASE_ENV[@]}" "$FP_PROJ_CAPTURE" saturday-arm \
    || echo "FP PROJECTIONS: the Saturday capture FAILED (line above); the timers are armed -- re-run $FP_PROJ_CAPTURE before lock"
fi
# DraftKings host fallback (provider calls; opt in explicitly with HOST_INGEST=1 after the --check):
echo "$HOST_LINE"
if [[ "$RUN" == "--run" ]]; then
  if [[ "${HOST_INGEST:-0}" == "1" ]]; then
    [[ -x "$INGEST_LOOP" ]] || { echo "host ingest loop is not executable: $INGEST_LOOP" >&2; exit 2; }
    systemd-run --user --unit="$UI" "${HI[@]}"
  fi
  systemctl --user list-timers --all | grep -i "nfl-week${WEEK}" || true
fi
