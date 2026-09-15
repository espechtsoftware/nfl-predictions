#!/usr/bin/env bash
# Print (and, with --run, execute) the one-shot user timers for a week's Sunday builds.  The harness classifier
# refuses systemd unit writes, so the operator runs the printed lines himself (each is a transient timer that
# disappears after firing; `systemctl --user list-timers` shows them while armed).
#   scripts/arm_week_timers.sh 2            # print
#   scripts/arm_week_timers.sh 2 --run      # arm (operator)
set -euo pipefail
WEEK=${1:?week}; RUN=${2:-}
PROD=${PROD:-/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912}
SUNDAY=$(date -u -d "2026-09-13 + $(( (WEEK - 1) * 7 )) days" +%Y-%m-%d)
DRIVER=/home/erich/week${WEEK}-sunday-build.sh
cat <<EOF
# Week $WEEK Sunday $SUNDAY: 09:10 CT main build, 10:50 CT T-70 rebuild (after the 10:30 CT inactives), 09:12 CT watchers.
systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit nfl-week${WEEK}-sunday-build $DRIVER
systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit nfl-week${WEEK}-t70-build env RUN_TAG=$(date -u -d "$SUNDAY 15:50" +%Y%m%dt%H%Mz)-e7255e9 $DRIVER
systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit nfl-week${WEEK}-watchers /home/erich/week${WEEK}-sunday-watchers.sh
EOF
if [[ "$RUN" == "--run" ]]; then
  systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit "nfl-week${WEEK}-sunday-build" "$DRIVER"
  systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit "nfl-week${WEEK}-t70-build" env "RUN_TAG=$(date -u -d "$SUNDAY 15:50" +%Y%m%dt%H%Mz)-e7255e9" "$DRIVER"
  systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit "nfl-week${WEEK}-watchers" "/home/erich/week${WEEK}-sunday-watchers.sh"
  systemctl --user list-timers --all | grep -i "nfl-week${WEEK}" || true
fi
