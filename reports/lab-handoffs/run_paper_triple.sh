#!/usr/bin/env bash
# Chalk-core PAPER triple for the live week (production HANDOFF c72753c9). Runs on the LAPTOP, never uploads, never
# enters. Three D3200 builds, one at a time (one heavy process), same seed, in a scratch clone at the sleeve commit:
#   (a) control   (b) --chalk-sleeve-low-max 1 --chalk-sleeve-chalk-k 15   (c) --chalk-sleeve-low-max 2 --chalk-sleeve-chalk-k 15
# (c) IS L02's SLEEVE_L2 (operator 155ff97b asks for it as a Week-3 paper arm): L02 froze share 0.25, <= 2 LOW, top-15 by
# pred_own, salary >= 49,500, lev 640 + boom 2,560, max-per-game 4 at this same sleeve commit; the receipt check pins each one.
# all with --max-per-game 4 --entries 198 --selector dual_emax, no --emit-a5-sidecars (paper path).
#
#   bash run_paper_triple.sh <sets file> [group=153769] [week=3] [entries=198]
#
# Preconditions (checked): before lock; the sets file exists and its receipt is readable; production's Week-3 projections
# exist (live_week refuses otherwise). Each run's receipt is checked: arm.max_per_game == 4 and, for (b)/(c),
# arm.chalk_sleeve.low_max matches and its book_shape exists. Outputs and logs in $TRIPLE_DIR (durable, not /tmp).
set -uo pipefail
SETS=${1:?sets file}; GROUP=${2:-153769}; WEEK=${3:-3}; ENTRIES=${4:-198}
SHA=0f03b782f30c4c17f0c54439ddbac0acc35013b7
LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
T=${TRIPLE_DIR:-$HOME/.cache/laptop-agent/paper-triple-w$(printf %02d "$WEEK")}; mkdir -p "$T"
exec > >(tee -a "$T/triple.log") 2>&1
echo "=== paper triple $(date -u +%FT%TZ) week $WEEK group $GROUP entries $ENTRIES sets $SETS sleeve commit $SHA"
[[ -s "$SETS" ]] || { echo "FAIL: sets file $SETS missing or empty"; exit 1; }
S="$T/nfl2-$SHA"
if [[ ! -d "$S/.git" ]]; then git clone -q /home/erich/projects/nfl2 "$S" && git -C "$S" checkout -q "$SHA" || { echo "FAIL: clone"; exit 1; }; fi
[[ "$(git -C "$S" rev-parse HEAD)" == "$SHA" && -z "$(git -C "$S" status --porcelain)" ]] || { echo "FAIL: scratch clone not clean at $SHA"; exit 1; }
fail=0
run() {  # $1 label, rest = extra args; an arm already recorded in run_dirs.txt (it passed its check) is not rebuilt
  local label=$1; shift
  if [[ -f "$T/run_dirs.txt" ]] && grep -q "^$label " "$T/run_dirs.txt"; then echo "--- ($label) already built: $(grep "^$label " "$T/run_dirs.txt" | cut -d' ' -f2)"; return; fi
  echo "--- ($label) $(date -u +%T) extra: $*"
  local before; before=$(ls -d "$S/results/live/2026-w$(printf %02d "$WEEK")"/*/ 2>/dev/null | sort | tail -1)
  ( cd "$S" && NFL2_LIVE_CENTER=production PYTHONPATH="$S/src" OMP_NUM_THREADS=1 "$LAB_PY" scripts/live_week.py \
      --season 2026 --week "$WEEK" --group "$GROUP" --selector dual_emax --lev 640 --boom 2560 --sims 10000 --k 1 \
      --seed 2026 --entries "$ENTRIES" --max-per-game 4 "$@" > "$T/$label.out" 2> "$T/$label.err" ) \
    || { echo "FAIL ($label): live_week exited non-zero; tail:"; tail -5 "$T/$label.err"; fail=1; return; }
  local run; run=$(ls -d "$S/results/live/2026-w$(printf %02d "$WEEK")"/*/ | sort | tail -1); run=${run%/}
  [[ "$run/" != "$before" ]] || { echo "FAIL ($label): no new run dir"; fail=1; return; }
  echo "$label $run" >> "$T/run_dirs.txt"
  "$LAB_PY" - "$run" "$label" <<'PY' || fail=1
import json, sys
run, label = sys.argv[1], sys.argv[2]
r = json.load(open(f"{run}/receipt.json")); arm = r["config"]["arm"]; ok = arm.get("max_per_game") == 4
cs = arm.get("chalk_sleeve")
if label == "a_control":
    ok &= cs is None
else:
    want = 1 if label.startswith("b") else 2
    ok &= bool(cs) and cs.get("low_max") == want and "book_shape" in cs and cs.get("chalk_rule") == "top-15 by pred_own"
    ok &= cs.get("share") == 0.25 and cs.get("min_salary") == 49_500 and cs.get("of_boom") == 2560 and cs.get("solves") == 640
    print(f"  sleeve: {cs.get('solves')} solves, book shape {cs.get('book_shape')}")
print(f"  {label}: {run}  max_per_game={arm.get('max_per_game')}  written={r.get('written')}  -> {'OK' if ok else 'FAIL'}")
sys.exit(0 if ok else 1)
PY
}
run a_control
run b_low1 --chalk-sleeve-sets "$SETS" --chalk-sleeve-low-max 1 --chalk-sleeve-chalk-k 15
run c_low2 --chalk-sleeve-sets "$SETS" --chalk-sleeve-low-max 2 --chalk-sleeve-chalk-k 15
echo "=== paper triple $([[ $fail == 0 ]] && echo DONE || echo FAILED); run dirs in $T/run_dirs.txt"
exit $fail
