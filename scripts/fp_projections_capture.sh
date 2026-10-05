#!/usr/bin/env bash
# Capture Fantasy Points' projection tables (dfs, weekly, rankings-weekly, rankings-ros) for $WEEK: CAPTURE ONLY, nothing
# in the build reads them (reviewer 2026-10-05; the operator's every-paid-page rule). FP serves the current week only,
# so a missed capture is lost for good: a failure prints one loud line and exits 1 (a failed unit).
#
# Wednesday is covered by `nfl-weekly-data run` (its fp-projections pages). This wrapper is the pre-lock pair: once at
# Saturday's arming (arm_week_timers.sh --run) and the Sunday unit before the T-70 build, so a pre-lock snapshot exists.
#
# Every Fantasy Points browser use on the host takes FP_PROFILE_LOCK: Chromium allows one process per profile, and the
# T-70 build's ownership capture (sunday_build_host.sh) takes the same lock, so neither can break the other.
#
#   WEEK=5 PROD=... PROD_PY=... scripts/fp_projections_capture.sh LABEL
set -uo pipefail
: "${WEEK:?set WEEK}" "${PROD:?set PROD}" "${PROD_PY:?set PROD_PY}"
LABEL=${1:-manual}
LOCK=${FP_PROFILE_LOCK:-$HOME/.cache/nfl-dfs/fantasy-points-profile.lock}
# logs stay out of the week's OUT directory (O-24: only build inputs live there)
LOGDIR=${FP_PROJ_LOG_DIR:-$HOME/.cache/nfl-dfs/fp-projections}
mkdir -p "$(dirname "$LOCK")" "$LOGDIR"
LOG="$LOGDIR/week${WEEK}-${LABEL}-$(date -u +%Y%m%dT%H%M%SZ).log"
if ( cd "$PROD" && PYTHONPATH="$PROD/src" flock -w "${FP_LOCK_WAIT_S:-600}" "$LOCK" \
       timeout "${FP_PROJ_TIMEOUT_S:-600}" "$PROD_PY" -m nfl_dfs.ops.fantasy_points_projections collect --week "$WEEK" ) \
     > "$LOG" 2>&1; then
  echo "FP PROJECTIONS CAPTURED for Week $WEEK ($LABEL); log $LOG"
else
  rc=$?
  why=$(grep -h '^ERROR' "$LOG" | tail -1)
  echo "FP PROJECTIONS CAPTURE FAILED for Week $WEEK ($LABEL, exit $rc): ${why:-see the log}; log $LOG" >&2
  exit 1
fi
