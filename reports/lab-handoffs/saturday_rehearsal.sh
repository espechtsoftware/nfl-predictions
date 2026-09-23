#!/usr/bin/env bash
# Saturday rehearsal for the live week, ONE command, outcome-blind, nothing uploaded, nothing entered.
# Run on the build host AFTER the Saturday props pull and the project-slate refresh, BEFORE Sunday's build:
#
#   bash reports/lab-handoffs/saturday_rehearsal.sh 3            # week; draft group auto-detected by week_env
#   bash reports/lab-handoffs/saturday_rehearsal.sh 3 153769     # explicit draft group
#
# It sources scripts/week_env.sh, so it uses exactly Sunday's CLONE / EXPECT_SHA / MAX_PER_GAME / BOOK_ENTRIES / GROUP.
#   0. identity:  the pinned clone is clean and at EXPECT_SHA (the same gate the Sunday build enforces).
#   1. availability dry run on the deployed production code: designations, who each mechanism touches, and the
#      project-slate log lines Sunday must show (reports/lab-handoffs/week3_availability_dry_run.py).
#   2. a SMALL paid-path build (lev 128 + boom 512, the Sunday flags incl. --emit-a5-sidecars and the cap) in a SCRATCH
#      clone at EXPECT_SHA -- never the pinned clone, whose results dir the Sunday scripts read -- then fail-closed
#      checks: receipt config.arm.max_per_game and a5_sidecars.arm_max_per_game equal MAX_PER_GAME, the book holds
#      BOOK_ENTRIES distinct rosters, and no candidate exceeds the cap in any game (QB and DST counted).
#   3. the paper cash-shadow build from that rehearsal run dir (reports/lab-handoffs/cash_shadow_paper.py), which also
#      proves the pre-lock guard and the receipt.
# Exit status is non-zero if any step fails; each step's output is in $REHEARSAL_DIR/rehearsal.log.
set -uo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd); PROD_ROOT=$(cd -- "$HERE/../.." && pwd)
# shellcheck source=/dev/null
source "$PROD_ROOT/scripts/week_env.sh"; week_env "${1:?week}" "${2:-}" || exit 2
R=${REHEARSAL_DIR:-$HOME/week${WEEK}-rehearsal}; mkdir -p "$R"
exec > >(tee -a "$R/rehearsal.log") 2>&1
echo "=== Saturday rehearsal $(date -u +%FT%TZ): season $SEASON week $WEEK group $GROUP; EXPECT_SHA $EXPECT_SHA; MAX_PER_GAME $MAX_PER_GAME; BOOK_ENTRIES $BOOK_ENTRIES"
fail=0; bad() { echo "FAIL: $*"; fail=1; }

echo "--- 0. pinned clone identity"
head=$(git -C "$CLONE" rev-parse HEAD 2>/dev/null); dirty=$(git -C "$CLONE" status --porcelain 2>/dev/null | wc -l)
[[ "$head" == "$EXPECT_SHA" ]] || bad "clone $CLONE HEAD $head != EXPECT_SHA $EXPECT_SHA"
[[ "$dirty" == 0 ]] || bad "clone $CLONE is dirty ($dirty paths)"
echo "clone HEAD $head, dirty paths $dirty"

echo "--- 1. availability dry run (deployed production code)"
PYTHONPATH="$PROD/src" "$PROD_PY" "$HERE/week3_availability_dry_run.py" --season "$SEASON" --week "$WEEK" || bad "availability dry run"

echo "--- 2. small paid-path build with the cap, scratch clone at EXPECT_SHA"
S="$R/nfl2-scratch"; rm -rf "$S"
git clone -q "$(git -C "$CLONE" rev-parse --path-format=absolute --git-common-dir)" "$S" && git -C "$S" checkout -q "$EXPECT_SHA" \
  || bad "scratch clone at $EXPECT_SHA"
MPG=(); [[ "${MAX_PER_GAME:-0}" != "0" ]] && MPG=(--max-per-game "$MAX_PER_GAME")
( cd "$S" && NFL2_LIVE_CENTER=production PYTHONPATH="$S/src" OMP_NUM_THREADS=1 "$LAB_PY" scripts/live_week.py \
    --season "$SEASON" --week "$WEEK" --group "$GROUP" --selector dual_emax --lev 128 --boom 512 --sims 10000 --k 1 \
    --seed 2026 --entries "$BOOK_ENTRIES" --emit-a5-sidecars "${MPG[@]}" > "$R/build.out" 2> "$R/build.err" ) \
  || { bad "live_week.py exited non-zero (see $R/build.err)"; tail -5 "$R/build.err"; }
RUN=$(ls -d "$S/results/live/$WEEKDIR"/*/ 2>/dev/null | sort | tail -1); RUN=${RUN%/}
echo "rehearsal run dir: ${RUN:-<none>}"
if [[ -n "$RUN" && -f "$RUN/receipt.json" ]]; then
  "$LAB_PY" - "$RUN" "${MAX_PER_GAME:-0}" "$BOOK_ENTRIES" <<'PY' || bad "receipt / book / cap checks"
import json, sys
from collections import Counter
import pandas as pd
run, want, k = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
r = json.load(open(f"{run}/receipt.json")); ok = True
arm = (r.get("config", {}).get("arm") or {}).get("max_per_game"); side = (r.get("a5_sidecars") or {}).get("arm_max_per_game")
exp = None if want == 0 else want
print(f"receipt config.arm.max_per_game={arm}  a5_sidecars.arm_max_per_game={side}  expected={exp}")
ok &= arm == exp and side == exp
book = pd.read_csv(f"{run}/book.csv"); n = len(book.drop_duplicates())
print(f"book rows {len(book)}, distinct {n}, expected {k}"); ok &= len(book) == k and n == k
fr = pd.read_parquet(f"{run}/frame.parquet"); game = dict(zip(fr.id.astype(str), fr.game_id.astype(str)))
c = pd.read_parquet(f"{run}/candidates.parquet")
mx = Counter(max(Counter(game[p] for p in s.split(",")).values()) for s in c.players.astype(str))
print(f"candidates {len(c)}; max players from one game: {dict(sorted(mx.items()))}")
if want: ok &= max(mx) <= want
print("PASS" if ok else "FAIL"); sys.exit(0 if ok else 1)
PY
else
  bad "no rehearsal run dir / receipt"
fi

echo "--- 3. paper cash-shadow build from the rehearsal run dir"
if [[ -n "${RUN:-}" ]]; then
  PYTHONPATH="$S/src:$PROD/src" "$LAB_PY" "$HERE/cash_shadow_paper.py" build "$RUN" "$R/cash-shadow-rehearsal" \
    | grep -E '"kind"|"n"|mean_proj|lock_utc' || bad "cash shadow build"
fi

echo "=== rehearsal $([[ $fail == 0 ]] && echo PASSED || echo FAILED); log $R/rehearsal.log"
exit $fail
