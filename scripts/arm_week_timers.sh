#!/usr/bin/env bash
# Print (and, with --run, execute) the one-shot user timers for a regular-season Sunday.  The commands use tracked
# entrypoints and pass every path explicitly; they do not depend on deleted /home/erich/week<W>-sunday-* wrappers.
#
#   scripts/arm_week_timers.sh 3             # print the Week-3 commands
#   scripts/arm_week_timers.sh 3 --run       # preflight, then arm them (operator action)
#
# The build doses are explicit environment values so a missing or stale dose file cannot silently turn the D3200 slot
# into a D800 build.  Adjust the D*_LEV/D*_BOOM variables for a tested plan before arming.
set -Eeuo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WEEK=${1:?usage: arm_week_timers.sh WEEK [--run]}
RUN=${2:-}
SEASON=${SEASON:-2026}
PROD=${PROD:-$(cd -- "$SCRIPT_DIR/.." && pwd)}
CLONE=${CLONE:-${NFL2_LIVE_CLONE:-/home/erich/projects/.nfl2-worktrees/week3-live-center}}
EXPECT_SHA=${EXPECT_SHA:-${NFL2_EXPECT_SHA:-e7255e98bf87297452befb61fb508ad4b368b59f}}
PROD_PY=${PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
TOOLS=${TOOLS:-$PROD/scripts}
OUT=${OUT:-/home/erich/week${WEEK}-sunday}
CONTESTS_JSON=${CONTESTS_JSON:-$OUT/contests.json}
DRIVER=${DRIVER:-$SCRIPT_DIR/run_week_build.sh}
WATCHER=${WATCHER:-$SCRIPT_DIR/run_week_watchers.sh}
INGEST_LOOP=${INGEST_LOOP:-$SCRIPT_DIR/host_ingest_dk_loop.sh}
CODE_TAG=${RUN_SUFFIX:-${EXPECT_SHA:0:7}}
FIXTURE_SHA=e7255e98bf87297452befb61fb508ad4b368b59f
if [[ "$RUN" == "--run" && "$EXPECT_SHA" == "$FIXTURE_SHA" && "${ALLOW_FIXTURE_PIN:-0}" != "1" ]]; then
  echo "refusing to arm Week $WEEK with the compatibility fixture EXPECT_SHA=$FIXTURE_SHA; export the approved Week-3 pin (or set ALLOW_FIXTURE_PIN=1 only for a deliberate rehearsal)" >&2
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

BASE_ENV=(env
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
L3200=("${BASE_ENV[@]}" "PAID_LEV=$D3200_LEV" "PAID_BOOM=$D3200_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 09:10 d3200)" "$DRIVER")
L800=("${BASE_ENV[@]}" "PAID_LEV=$D800_LEV" "PAID_BOOM=$D800_BOOM" SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 10:50 d800)" "$DRIVER")
LW=("${BASE_ENV[@]}" "${WATCH_FLAGS[@]}" "$WATCHER")
HI=("${BASE_ENV[@]}" "GCP_PROJECT=${GCP_PROJECT:-nfl-predictions-503414}" "$INGEST_LOOP")
CHECK_BUILD=("${BASE_ENV[@]}" "$DRIVER" --check)
CHECK_WATCH=("${BASE_ENV[@]}" "${WATCH_FLAGS[@]}" "$WATCHER" --check)
HOST_LINE="# HOST_INGEST=1 enables the tracked hourly DraftKings fallback after its --check"
if [[ "${HOST_INGEST:-0}" == "1" ]]; then
  HOST_LINE="systemd-run --user --unit=\"$UI\" ${HI[*]}"
fi

cat <<EOT
# Week $WEEK (America/Chicago), Sunday $SUNDAY; code tag $CODE_TAG
# Before arming: refresh build-features -> tabpfn-gen -> project-slate for ${SEASON}:${WEEK}, fill $CONTESTS_JSON,
# and create $OUT/chosen-dose.env with CHOSEN_LEV/CHOSEN_BOOM.  The watcher fails closed without that file.
#
# Refresh (operator, in this order, after the props pull):
gcloud run jobs execute build-features --project nfl-predictions-503414 --region us-central1 --wait
gcloud run jobs execute tabpfn-gen --project nfl-predictions-503414 --region us-central1 --update-env-vars TABPFN_UPCOMING=${SEASON}:${WEEK} --wait
gcloud run jobs execute project-slate --project nfl-predictions-503414 --region us-central1 --wait
# then, when ENTER_ORDER=fewest-low, the Saturday sets file (the preflight refuses to arm without it):
PYTHONPATH=\$PROD/src \$PROD_PY \$PROD/scripts/ownership_sets.py sets --week ${WEEK} --group \${GROUP} --out \${OWNERSHIP_SETS}
#
# Saturday $SATURDAY: D12800 at 10:30 CT, D6400 fallback at 10:35 CT; Sunday: D6400 05:30 CT, D3200 09:10 CT,
# D800 T-70 at 10:50 CT, persistent watchers at 09:12 CT.
systemd-run --user --on-calendar="$SATURDAY 10:30 America/Chicago" --unit="$U12800" ${L12800[*]}
systemd-run --user --on-calendar="$SATURDAY 10:35 America/Chicago" --unit="$U6400SAT" ${L6400SAT[*]}
systemd-run --user --on-calendar="$SUNDAY 05:30 America/Chicago" --unit="$U6400" ${L6400[*]}
systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit="$U3200" ${L3200[*]}
systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit="$U800" ${L800[*]}
systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit="$UW" ${LW[*]}
# DraftKings host fallback (provider calls; opt in explicitly with HOST_INGEST=1 after the --check):
$HOST_LINE
EOT

if [[ "$RUN" == "--run" ]]; then
  echo "running build and watcher preflights before arming timers"
  "${CHECK_BUILD[@]}"
  "${CHECK_WATCH[@]}"
  if [[ "${HOST_INGEST:-0}" == "1" ]]; then
    "$INGEST_LOOP" --check
  fi
  systemd-run --user --on-calendar="$SATURDAY 10:30 America/Chicago" --unit="$U12800" "${L12800[@]}"
  systemd-run --user --on-calendar="$SATURDAY 10:35 America/Chicago" --unit="$U6400SAT" "${L6400SAT[@]}"
  systemd-run --user --on-calendar="$SUNDAY 05:30 America/Chicago" --unit="$U6400" "${L6400[@]}"
  systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit="$U3200" "${L3200[@]}"
  systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit="$U800" "${L800[@]}"
  systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit="$UW" "${LW[@]}"
  if [[ "${HOST_INGEST:-0}" == "1" ]]; then
    [[ -x "$INGEST_LOOP" ]] || { echo "host ingest loop is not executable: $INGEST_LOOP" >&2; exit 2; }
    systemd-run --user --unit="$UI" "${HI[@]}"
  fi
  systemctl --user list-timers --all | grep -i "nfl-week${WEEK}" || true
fi
