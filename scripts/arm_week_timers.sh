#!/usr/bin/env bash
# Print (and, with --run, execute) the one-shot user timers for a week's Sunday builds.  The harness classifier
# refuses systemd unit writes, so the operator runs the printed lines himself (each is a transient timer that
# disappears after firing; `systemctl --user list-timers` shows them while armed).
#   scripts/arm_week_timers.sh 2            # print
#   scripts/arm_week_timers.sh 2 --run      # arm (operator)
#
# Week-2 dose plan (operator decision 2026-09-16, recorded in HANDOFF.md): four builds, each its own run tag and
# run dir, the operator picks the book on Sunday morning from whatever completed:
#   01:30 CT  D12800 (lev 2560 / boom 10240), ≈ 6.5–8 h   -> candidate if Friday's PREREG-099 read favours it
#   05:30 CT  D6400  (lev 1280 / boom 5120),  ≈ 2.5–3 h   -> the intended entry
#   09:10 CT  D3200  (lev 640 / boom 2560),   ≈ 1 h       -> fallback (the two-cohort-proven dose; week<W>-dose.env)
#   10:50 CT  D800   (lev 160 / boom 640),    ≈ 15 min    -> T-70 fresh-salary fallback after the 10:30 CT inactives
# The 10:30 CT inactives are applied to the chosen book by the scratch-swap tools, not by rebuilding.
set -euo pipefail
WEEK=${1:?week}; RUN=${2:-}
PROD=${PROD:-/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912}
SUNDAY=$(date -u -d "2026-09-13 + $(( (WEEK - 1) * 7 )) days" +%Y-%m-%d)
DRIVER=/home/erich/week${WEEK}-sunday-build.sh
tag() { echo "$(date -u -d "$SUNDAY $1" +%Y%m%dt%H%Mz)-$2-e7255e9"; }   # $1 UTC time of the CT slot, $2 label
U12800="nfl-week${WEEK}-d12800-build"; U6400="nfl-week${WEEK}-d6400-build"; U3200="nfl-week${WEEK}-sunday-build"; U800="nfl-week${WEEK}-t70-build"; UW="nfl-week${WEEK}-watchers"
L12800=(env PAID_LEV=2560 PAID_BOOM=10240 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 06:30 d12800)" "$DRIVER")
L6400=(env PAID_LEV=1280 PAID_BOOM=5120 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 10:30 d6400)" "$DRIVER")
L3200=(env SKIP_PAIR=1 "RUN_TAG=$(tag 14:10 d3200)" "$DRIVER")
L800=(env PAID_LEV=160 PAID_BOOM=640 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 15:50 d800)" "$DRIVER")
cat <<EOT
# Week $WEEK Sunday $SUNDAY (America/Chicago): 01:30 D12800, 05:30 D6400, 09:10 D3200 (dose file), 10:50 D800 T-70, 09:12 watchers.
systemd-run --user --on-calendar="$SUNDAY 01:30 America/Chicago" --unit $U12800 ${L12800[*]}
systemd-run --user --on-calendar="$SUNDAY 05:30 America/Chicago" --unit $U6400 ${L6400[*]}
systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit $U3200 ${L3200[*]}
systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit $U800 ${L800[*]}
systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit $UW /home/erich/week${WEEK}-sunday-watchers.sh
EOT
if [[ "$RUN" == "--run" ]]; then
  systemd-run --user --on-calendar="$SUNDAY 01:30 America/Chicago" --unit "$U12800" "${L12800[@]}"
  systemd-run --user --on-calendar="$SUNDAY 05:30 America/Chicago" --unit "$U6400" "${L6400[@]}"
  systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit "$U3200" "${L3200[@]}"
  systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit "$U800" "${L800[@]}"
  systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit "$UW" "/home/erich/week${WEEK}-sunday-watchers.sh"
  systemctl --user list-timers --all | grep -i "nfl-week${WEEK}" || true
fi
