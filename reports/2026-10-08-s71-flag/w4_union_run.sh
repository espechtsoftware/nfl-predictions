#!/usr/bin/env bash
# study 71 W4 validation: one union run on the Week-4 inputs with the Week-5 arming (mix, rr, ms4, QB cap 5, FP, cheap +2 block)
set -uo pipefail
PROD=$1; OUT=$2; shift 2
W4=$HOME/projects/.nfl2-worktrees/week4-live-center/results/live/2026-w04; T70=$W4/20261004T155026918221Z-32cdb61
CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center; LAB_PY=$HOME/projects/nfl2/.venv/bin/python; I=$HOME/.cache/laptop-agent/rehearsal/inputs
CHEAP=$HOME/rehearsals/outside-twblocks-20261008T213239Z/cheap2-w4.csv
cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py \
  --saturday-run auto --saturday-dose 2560/10240,1280/5120 --t70-run "$T70" --live-dir "$W4" --group 154078 \
  --saturday-after 2026-10-03T05:00:00 --entries 26 --tail-sleeve 0 --mean-max-shared 4 --min-proj 1.0 --max-per-game 4 --min-salary 49000 \
  --pmo 0 --pmo-cap-share 0.5 --main-cap-share 0.5 --main-dst-cap 0.25 --sleeve-includes-main --mean-dst-cap 0.25 --rehearsal \
  --main mix --mix-portfolio mix --mix-plan $HOME/week5-sunday/contests.json --mix-layout head --mix-spares 15 --mix-fill rr \
  --main-qb-cap-rows 5 --main-qb-cap-k 26 --proj-source $I/proj_fp-w4.csv \
  --term-block-rows 8 --term-block-source $CHEAP --term-block-tilt 0.20 --term-block-cap-points 2.0 "$@" --out "$OUT"
