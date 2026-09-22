#!/usr/bin/env bash
# Week-3 blocker watch: rosters and props, the two things gating project-slate.
#
# Offered as a TRACKED replacement for the host-local hourly check described in
# reports/2026-09-22-production-accepts-the-saturday-deadline.md. Not wired into
# deploy/systemd/ -- that is production's call. Read-only: it queries BigQuery
# and prints, and starts nothing.
#
#   watch:  bash reports/lab-handoffs/week3_blocker_watch.sh 2026 3
#
# Exit 0 always; this is a reporter, not a gate.
set -uo pipefail
SEASON="${1:-2026}"; WEEK="${2:-3}"
PROJECT="${GCP_PROJECT:-nfl-predictions-503414}"
q() { timeout 120 bq --project_id="$PROJECT" --format=csv query --use_legacy_sql=false --quiet "$1" 2>/dev/null | tail -1; }

STAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
ROSTERS="$(q "SELECT COUNT(DISTINCT gsis_id) FROM \`${PROJECT}.nfl_raw.rosters_weekly\` WHERE season=${SEASON} AND week=${WEEK}")"
PROPS="$(q "SELECT COUNT(*) FROM \`${PROJECT}.nfl_raw.prop_lines\` WHERE season=${SEASON} AND week=${WEEK}")"
case "$ROSTERS" in ''|*[!0-9]*) ROSTERS=0 ;; esac
case "$PROPS"   in ''|*[!0-9]*) PROPS=0 ;; esac

echo "${STAMP} week3-blocker-watch season=${SEASON} week=${WEEK} rosters=${ROSTERS} props=${PROPS}"

if [ "$ROSTERS" -gt 0 ]; then
  echo "  ROSTERS PRESENT -> project-slate's roster guard can clear; re-run it and report the outcome."
else
  echo "  rosters absent -> project-slate stops at the roster guard (expected until Thursday)."
fi

if [ "$PROPS" -gt 0 ]; then
  echo "  PROPS PRESENT -> run prop_match_preflight.py NOW. An unmatched name stops project-slate"
  echo "  entirely and the operator decision has to happen that evening, not Sunday."
else
  echo "  props absent -> MarketMatchError is NOT testable; every raise in resolve_live_market"
  echo "  is gated on feed_present. Expected until Saturday (W1 landed 09-13, W2 09-20)."
  echo "  TRAP: a project-slate run in this state SUCCEEDS and writes a 100%-model batch."
  echo "  A 100% model-only batch is NOT a good batch -- check_market_monitor fails it on"
  echo "  props-share (0% < 30%), but nothing in the projection path objects."
fi
