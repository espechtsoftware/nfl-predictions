#!/usr/bin/env bash
# Re-run the props-blend arm of the W4 screen with its sidecar in place; score base vs blend. Reuses the W4 screen worktree.
set -uo pipefail
R=/home/erich/rehearsals/screen-20261006T202423Z; I=$HOME/.cache/laptop-agent/rehearsal/inputs
PROD=$HOME/projects/.nfl-predictions-worktrees/rehearsal-screen-screen-20261006T202423Z
CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center; LAB_PY=$HOME/projects/nfl2/.venv/bin/python; PY=$HOME/projects/nfl-predictions/.venv/bin/python
W4=$HOME/projects/.nfl2-worktrees/week4-live-center/results/live/2026-w04; PLAN=$HOME/week5-sunday/contests.json
rm -rf "$R/blend" "$R/stage-blend"
( cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py \
    --saturday-run auto --saturday-dose 2560/10240,1280/5120 --t70-run "$W4/20261004T155026918221Z-32cdb61" --live-dir "$W4" \
    --group 154078 --saturday-after 2026-10-03T05:00:00 --entries 26 --tail-sleeve 0 --mean-max-shared 7 --min-proj 1.0 \
    --max-per-game 4 --min-salary 49000 --pmo 0 --pmo-cap-share 0.5 --main-cap-share 0.5 --main-dst-cap 0.25 \
    --sleeve-includes-main --mean-dst-cap 0.25 --rehearsal --main mix --mix-portfolio mix --mix-plan "$PLAN" --mix-layout head --mix-spares 15 \
    --main-qb-cap-rows 5 --main-qb-cap-k 26 --proj-source "$R/proj_blend-w4.csv" --out "$R/blend" ) > "$R/blend.txt" 2>&1
echo "  union blend rc $? ($(grep -c -E 'REFUSED|Traceback' "$R/blend.txt") refusal lines)"
mkdir -p "$R/stage-blend"
( cd "$PROD" && ENTER_SMALL_MAX_SHARED=5 ENTER_SMALL_OVERLAP_MAX_ENTRIES=10 PYTHONPATH="$PROD/src" "$PY" -m nfl_dfs.inference.enter_layout write "$PLAN" "$R/blend/book.csv" "$R/stage-blend" --layout head ) > "$R/stage-blend.txt" 2>&1
echo "  layout blend rc $?"
PYTHONPATH="$PROD/src" "$LAB_PY" - "$R" "$PROD" <<'PYEOF'
import csv, importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
R, PROD = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("MS", PROD / "scripts" / "moneygate_score.py"); MS = importlib.util.module_from_spec(spec); sys.modules["MS"] = MS; spec.loader.exec_module(MS)
sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/experiments")); sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/src"))
from s24_qb_game_cap import big_seat_stats
W = MS.load_week(MS.load_config(), 4); others = np.asarray(W.others_sorted("196151357"), np.int64)
plan = json.loads((Path.home() / "s24-panel/plan-week5-rev3-s24.json").read_text())["contests"]
score = json.loads((R / "score.json").read_text())
for a in ("blend",):
    fr = pd.read_parquet(R / a / "frame.parquet"); key = fr.dk_player_id.astype("Int64").astype(str)
    name = dict(zip(key, fr.display_name)); pos = dict(zip(key, fr.pos.astype(str))); game = dict(zip(key, fr.game_id.astype(str)))
    rows = list(csv.reader(open(R / a / "book.csv")))[1:]
    pts = np.array([sum(W.fpts.get(MS.canon(name.get(p, "")), 0) for p in r) for r in rows], np.int64)
    F = np.searchsorted(others, pts, "left") / len(others)
    rm = json.loads((R / f"stage-{a}" / "ENTER-rowmap.json").read_text()); ranks = [rm[f"{c['name']}-{c['contest_id']}"] for c in plan]
    st = big_seat_stats(F, ranks, plan); dealt = [i for rr in ranks for i in rr]; book = rows[:26]; cnt = pd.Series([p for r in book for p in r]).value_counts()
    score[a] = {**{k: round(v, 4) for k, v in st.items()}, "mean_entry_pct": round(float(F[dealt].mean()), 4), "mean_entry_points": round(float(pts[dealt].mean()) / 100, 2),
                "best_row_points": round(float(pts[:26].max()) / 100, 2), "rows_top1pct": int((F[:26] >= 0.99).sum()), "rows_top5pct": int((F[:26] >= 0.95).sum()),
                "distinct_players": int(len(cnt)), "players_at_cap13": int((cnt >= 13).sum()), "players_over_9": int((cnt > 9).sum()), "max_exposure": int(cnt.max()),
                "qbs": len({p for r in book for p in r if pos.get(p) == "QB"}), "games": len({game.get(p) for r in book for p in r}), "own_sum_mean": None, "rows_with_field_copy": None, "dealt_entries": len(dealt)}
    base_rows = set(frozenset(r) for r in list(csv.reader(open(R / "base" / "book.csv")))[1:][:26]); same = sum(frozenset(r) in base_rows for r in book)
    print(f"blend: {same} of 26 rows identical to base")
(R / "score.json").write_text(json.dumps(score, indent=1) + "\n")
cols = ["p_big1", "e_big", "mean_entry_pct", "mean_entry_points", "best_row_points", "rows_top5pct", "distinct_players", "players_over_9", "qbs", "games"]
print(pd.DataFrame({k: score[k] for k in ("base", "blend")}).T[cols].to_string())
PYEOF
