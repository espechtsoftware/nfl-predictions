#!/usr/bin/env bash
# Print (and, with --run, execute) the one-shot user timers for a week's Sunday builds.  The harness classifier
# refuses systemd unit writes, so the operator runs the printed lines himself (each is a transient timer that
# disappears after firing; `systemctl --user list-timers` shows them while armed).
#   scripts/arm_week_timers.sh 2            # print
#   scripts/arm_week_timers.sh 2 --run      # arm (operator)
#
# Week-2 dose plan (operator decisions 2026-09-16, recorded in HANDOFF.md and the operating handoff §4.1): five builds,
# each its own run tag and run dir; the operator picks the book on Sunday morning from whatever completed.
# The long builds run SATURDAY MORNING after the operator triggers the production refresh at ~09:45 CT -- AFTER the
# 09:30 CT props pull, because below 30 % prop coverage the projection blend falls back to DK points-per-game, which at
# week <= 3 is simply last week's score (defect 27; check the project-slate log says 'market blend source: props') (measured
# D12800 rehearsal on the Week-2 group: 58,602 s = 16.3 h with the lab bank sharing the machine; the slot leaves a
# 20 % margin to 04:00 CT Sunday even at that pace)
# (`gcloud run jobs execute build-features ... --wait` then `project-slate`), so a failure leaves the whole night:
#   Sat 10:30 CT  D12800 (lev 2560 / boom 10240; delivers 12,560 — one boom solve per simulated world, 10,000 worlds), 12–16 h -> THE INTENDED ENTRY (operator 2026-09-17; done 20:30 CT Sat – 02:30 CT Sun)
#   Sat 10:35 CT  D6400  (lev 1280 / boom 5120),  2 h 08  -> first fallback, on Saturday's refresh
#   Sun 05:30 CT  D6400  (same),                  2 h 08  -> fallback on the Sunday-morning refresh
#   Sun 09:10 CT  D3200  (lev 640 / boom 2560),   51 min  -> fallback (the two-cohort-proven dose; week<W>-dose.env)
#   Sun 10:50 CT  D800   (lev 160 / boom 640),    4 min   -> T-70 fresh-salary fallback after the 10:30 CT inactives
# The 10:30 CT inactives are applied to the chosen book by the scratch-swap tools, not by rebuilding.  The
# PREREG-099 host bank finishes Friday (amendment 4); if it is somehow still running, stop it before Saturday 10:00 CT so the cores are free (it resumes after Sunday).
# The after-build watcher enters only the CHOSEN dose (/home/erich/week<W>-chosen-dose.env: 2560/10240).
set -euo pipefail
WEEK=${1:?week}; RUN=${2:-}
PROD=${PROD:-/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912}
SUNDAY=$(date -u -d "2026-09-13 + $(( (WEEK - 1) * 7 )) days" +%Y-%m-%d)
SATURDAY=$(date -u -d "$SUNDAY - 1 day" +%Y-%m-%d)
DRIVER=/home/erich/week${WEEK}-sunday-build.sh
# Release pin (2026-09-19): the run-tag suffix and every unit's environment follow EXPECT_SHA/CLONE when they are
# exported.  systemd-run does NOT inherit the invoking shell's environment into the transient service, so the pins
# must be carried in the command itself -- for the WATCHERS too, or they resolve the old LIVE_DIR while the builds
# write to the new one.  Unset => the e7255e9 default and byte-identical output to the unpatched script.
REL_SHA=${EXPECT_SHA:-e7255e98bf87297452befb61fb508ad4b368b59f}; REL_SUFFIX=${REL_SHA:0:7}
REL_ENV=()
[[ -n "${CLONE:-}" ]] && REL_ENV+=("CLONE=$CLONE")
[[ -n "${EXPECT_SHA:-}" ]] && REL_ENV+=("EXPECT_SHA=$EXPECT_SHA")
REL_PRE=(); [[ ${#REL_ENV[@]} -gt 0 ]] && REL_PRE=(env "${REL_ENV[@]}")
tag() { echo "$(date -u -d "$SUNDAY $1" +%Y%m%dt%H%Mz)-$2-$REL_SUFFIX"; }   # $1 UTC time of the CT slot, $2 label
sat() { echo "$(date -u -d "$SATURDAY $1" +%Y%m%dt%H%Mz)-$2-$REL_SUFFIX"; }  # Saturday slots, UTC time (CT + 5 h in September)
U12800="nfl-week${WEEK}-d12800-sat-build"; U6400SAT="nfl-week${WEEK}-d6400-sat-build"; U6400="nfl-week${WEEK}-d6400-build"; U3200="nfl-week${WEEK}-sunday-build"; U800="nfl-week${WEEK}-t70-build"; UW="nfl-week${WEEK}-watchers"
L12800=(env ${REL_ENV[@]+"${REL_ENV[@]}"} PAID_LEV=2560 PAID_BOOM=10240 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(sat 15:30 d12800sat)" "$DRIVER")
L6400SAT=(env ${REL_ENV[@]+"${REL_ENV[@]}"} PAID_LEV=1280 PAID_BOOM=5120 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(sat 15:35 d6400sat)" "$DRIVER")
L6400=(env ${REL_ENV[@]+"${REL_ENV[@]}"} PAID_LEV=1280 PAID_BOOM=5120 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 10:30 d6400)" "$DRIVER")
L3200=(env ${REL_ENV[@]+"${REL_ENV[@]}"} SKIP_PAIR=1 "RUN_TAG=$(tag 14:10 d3200)" "$DRIVER")
L800=(env ${REL_ENV[@]+"${REL_ENV[@]}"} PAID_LEV=160 PAID_BOOM=640 SKIP_PAIR=1 DOSE_FILE=/dev/null "RUN_TAG=$(tag 15:50 d800)" "$DRIVER")
LW=(${REL_PRE[@]+"${REL_PRE[@]}"} "/home/erich/week${WEEK}-sunday-watchers.sh")   # watchers need the same pins
cat <<EOT
# Week $WEEK (America/Chicago): Sat $SATURDAY 09:45 operator refresh (three gcloud lines, AFTER the 09:30 props pull), 10:30 D12800 (THE ENTRY), 10:35 D6400 fallback;
# Sun $SUNDAY 05:30 D6400, 09:10 D3200 (dose file), 10:50 D800 T-70, 09:12 watchers.
# refresh (operator, in this order): gcloud run jobs execute build-features --project nfl-predictions-503414 --region us-central1 --wait ; gcloud run jobs execute tabpfn-gen --project nfl-predictions-503414 --region us-central1 --update-env-vars TABPFN_UPCOMING=2026:2 --wait ; gcloud run jobs execute project-slate --project nfl-predictions-503414 --region us-central1 --wait
systemd-run --user --on-calendar="$SATURDAY 10:30 America/Chicago" --unit $U12800 ${L12800[*]}
systemd-run --user --on-calendar="$SATURDAY 10:35 America/Chicago" --unit $U6400SAT ${L6400SAT[*]}
systemd-run --user --on-calendar="$SUNDAY 05:30 America/Chicago" --unit $U6400 ${L6400[*]}
systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit $U3200 ${L3200[*]}
systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit $U800 ${L800[*]}
systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit $UW ${LW[*]}
EOT
if [[ "$RUN" == "--run" ]]; then
  systemd-run --user --on-calendar="$SATURDAY 10:30 America/Chicago" --unit "$U12800" "${L12800[@]}"
  systemd-run --user --on-calendar="$SATURDAY 10:35 America/Chicago" --unit "$U6400SAT" "${L6400SAT[@]}"
  systemd-run --user --on-calendar="$SUNDAY 05:30 America/Chicago" --unit "$U6400" "${L6400[@]}"
  systemd-run --user --on-calendar="$SUNDAY 09:10 America/Chicago" --unit "$U3200" "${L3200[@]}"
  systemd-run --user --on-calendar="$SUNDAY 10:50 America/Chicago" --unit "$U800" "${L800[@]}"
  systemd-run --user --on-calendar="$SUNDAY 09:12 America/Chicago" --unit "$UW" "${LW[@]}"
  systemctl --user list-timers --all | grep -i "nfl-week${WEEK}" || true
fi
