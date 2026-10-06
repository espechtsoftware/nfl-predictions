#!/usr/bin/env bash
# Weeks 1-3 fixed-book screen of the STRUCTURAL levers under OUR served projections (no FP before W4), same machinery as
# the W4 screen: the armed Week-5 settings at K 26 (MIX + QB cap 5/26 + Rev3 head, tilt 0) built by production's
# union_reselect on each week's real T-70 inputs (the settlement copies under ~/moneygate/inputs/runs), one union per arm,
# enter_layout (Rev3 head), scored on that week's REAL Millionaire field (ties lose; big_seat_stats per Rev3 contest).
# The generic levers were not fitted to W1-4, so these are fair weeks for them; the projections are the older ones.
#   bash screen_w123_levers.sh <production commit> <run dir>
set -uo pipefail
COMMIT=${1:?production commit}; R=${2:?run dir}; mkdir -p "$R"
PROD=$HOME/projects/.nfl-predictions-worktrees/rehearsal-screen-$(basename "$R")
[ -d "$PROD" ] || git -C "$HOME/projects/nfl-predictions" worktree add -q --detach "$PROD" "$COMMIT" || exit 1
CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center; LAB_PY=$HOME/projects/nfl2/.venv/bin/python; PY=$HOME/projects/nfl-predictions/.venv/bin/python
LIVE=$HOME/moneygate/inputs/runs; PLAN=$HOME/week5-sunday/contests.json
declare -A T70=([1]=20260913T160405364118Z-e7255e9 [2]=20260920T155005557498Z-2dc116c [3]=20260927T155027472554Z-65305f5)
declare -A GROUP=([1]=151307 [2]=153428 [3]=153769)
declare -A AFTER=([1]=2026-09-11T05:00:00 [2]=2026-09-18T05:00:00 [3]=2026-09-25T05:00:00)
declare -A DOSE=([1]=80/320 [2]=2560/10240,1280/5120 [3]=2560/10240,1280/5120)
echo "== W1-3 lever screen $(date -u +%FT%TZ): code $(git -C "$PROD" rev-parse --short HEAD), lab $(git -C "$CLONE" rev-parse --short HEAD), plan $(sha256sum "$PLAN" | cut -c1-12)"
union() {  # $1 week, $2 out name, rest: extra args
  local w=$1 out=$2; shift 2
  ( cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py \
      --saturday-run auto --saturday-dose "${DOSE[$w]}" --t70-run "$LIVE/${T70[$w]}" --live-dir "$LIVE" \
      --group "${GROUP[$w]}" --saturday-after "${AFTER[$w]}" --entries 26 --tail-sleeve 0 --mean-max-shared 7 --min-proj 1.0 \
      --max-per-game 4 --min-salary 49000 --pmo 0 --pmo-cap-share 0.5 --main-cap-share 0.5 --main-dst-cap 0.25 \
      --sleeve-includes-main --mean-dst-cap 0.25 --rehearsal \
      --main mix --mix-portfolio mix --mix-plan "$PLAN" --mix-layout head --mix-spares 15 \
      --main-qb-cap-rows 5 --main-qb-cap-k 26 "$@" --out "$R/w$w-$out" ) > "$R/w$w-$out.txt" 2>&1
  echo "  union w$w $out rc $? ($(grep -c -E 'REFUSED|Traceback' "$R/w$w-$out.txt") refusal lines) $(date +%H:%M:%S)"
}
ARMS="base ms6 ms5 qb4 qb3 mpg3 cap35 ms5qb4"
for w in 1 2 3; do
  union $w base
  union $w ms6   --mean-max-shared 6
  union $w ms5   --mean-max-shared 5
  union $w qb4   --main-qb-cap-rows 4 --main-qb-cap-k 26
  union $w qb3   --main-qb-cap-rows 3 --main-qb-cap-k 26
  union $w mpg3  --max-per-game 3
  union $w cap35 --main-cap-share 0.35
  union $w ms5qb4 --mean-max-shared 5 --main-qb-cap-rows 4 --main-qb-cap-k 26
  for a in $ARMS; do
    [ -f "$R/w$w-$a/book.csv" ] || { echo "  layout w$w $a SKIPPED (no book)"; continue; }
    mkdir -p "$R/stage-w$w-$a"
    ( cd "$PROD" && ENTER_SMALL_MAX_SHARED=5 ENTER_SMALL_OVERLAP_MAX_ENTRIES=10 PYTHONPATH="$PROD/src" "$PY" -m nfl_dfs.inference.enter_layout write "$PLAN" "$R/w$w-$a/book.csv" "$R/stage-w$w-$a" --layout head ) > "$R/stage-w$w-$a.txt" 2>&1
    echo "  layout w$w $a rc $?"
  done
done
PYTHONPATH="$PROD/src" "$LAB_PY" - "$R" "$PROD" $ARMS <<'PYEOF'
import csv, importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
R, PROD = Path(sys.argv[1]), Path(sys.argv[2]); ARMS = sys.argv[3:]
spec = importlib.util.spec_from_file_location("MS", PROD / "scripts" / "moneygate_score.py"); MS = importlib.util.module_from_spec(spec); sys.modules["MS"] = MS; spec.loader.exec_module(MS)
sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/experiments")); sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/src"))
from s24_qb_game_cap import big_seat_stats
cfg = MS.load_config(); plan = json.loads((Path.home() / "s24-panel/plan-week5-rev3-s24.json").read_text())["contests"]
out = {}
for w in (1, 2, 3):
    W = MS.load_week(cfg, w); milly = MS.milly_cid(W); others = np.asarray(W.others_sorted(milly), np.int64)
    for a in ARMS:
        d = R / f"w{w}-{a}"
        if not (d / "book.csv").exists(): continue
        fr = pd.read_parquet(d / "frame.parquet")
        key = fr.dk_player_id.astype("Int64").astype(str)
        name = dict(zip(key, fr.display_name)); pos = dict(zip(key, fr.pos.astype(str))); game = dict(zip(key, fr.game_id.astype(str)))
        rows = list(csv.reader(open(d / "book.csv")))[1:]
        pts = np.array([sum(W.fpts.get(MS.canon(name.get(p, "")), 0) for p in r) for r in rows], np.int64)
        F = np.searchsorted(others, pts, "left") / len(others)
        rm = json.loads((R / f"stage-w{w}-{a}" / "ENTER-rowmap.json").read_text())
        ranks = [rm[f"{c['name']}-{c['contest_id']}"] for c in plan]
        st = big_seat_stats(F, ranks, plan); dealt = [i for rr in ranks for i in rr]
        book = rows[:26]; cnt = pd.Series([p for r in book for p in r]).value_counts()
        out[f"w{w}-{a}"] = {**{k: round(v, 4) for k, v in st.items()}, "mean_entry_pct": round(float(F[dealt].mean()), 4),
            "best_row_points": round(float(pts[:26].max()) / 100, 2), "rows_top1pct": int((F[:26] >= 0.99).sum()),
            "distinct_players": int(len(cnt)), "players_over_9": int((cnt > 9).sum()), "max_exposure": int(cnt.max()),
            "qbs": len({p for r in book for p in r if pos.get(p) == "QB"}), "games": len({game.get(p) for r in book for p in r})}
cols = ["p_big1", "e_big", "mean_entry_pct", "best_row_points", "rows_top1pct", "distinct_players", "players_over_9", "max_exposure", "qbs", "games"]
print("\n" + pd.DataFrame(out).T[cols].to_string())
(R / "score.json").write_text(json.dumps(out, indent=1) + "\n")
PYEOF
echo "== done $(date +%H:%M:%S); scratch $R; worktree $PROD"
