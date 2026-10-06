#!/usr/bin/env bash
# W4 fixed-book screen of one-setting construction levers under FP (outside review 2026-10-06, operator: "do the replay").
# Modelled on ~/.cache/laptop-agent/rehearsal/b_w4_term_replay.sh (the tilt replay): the ARMED Week-5 settings at K 26
# (MIX + FP source + QB cap 5/26 + Rev3 head, tilt 0) built by production's union_reselect on W4's real T-70 inputs, once
# per arm, then enter_layout (Rev3 head) and the score on W4's REAL Millionaire field (ties lose; big_seat_stats per Rev3
# contest). One week, the chalk-bust week: a screen for "not worse", never evidence of a gain. Touches nothing armed.
#   bash screen_w4_levers.sh <production commit> <run dir>
set -uo pipefail
COMMIT=${1:?production commit}; R=${2:?run dir}; mkdir -p "$R"
I=$HOME/.cache/laptop-agent/rehearsal/inputs
PROD=$HOME/projects/.nfl-predictions-worktrees/rehearsal-screen-$(basename "$R")
git -C "$HOME/projects/nfl-predictions" worktree add -q --detach "$PROD" "$COMMIT" || exit 1
CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center; LAB_PY=$HOME/projects/nfl2/.venv/bin/python; PY=$HOME/projects/nfl-predictions/.venv/bin/python
W4=$HOME/projects/.nfl2-worktrees/week4-live-center/results/live/2026-w04
OWN=$HOME/week4-sunday/ownership_fp-20261004t1550z-d800-32cdb61.csv
PLAN=$HOME/week5-sunday/contests.json
echo "== W4 lever screen $(date -u +%FT%TZ): code $(git -C "$PROD" rev-parse --short HEAD), lab $(git -C "$CLONE" rev-parse --short HEAD), plan $(sha256sum "$PLAN" | cut -c1-12), fp $(sha256sum "$I/proj_fp-w4.csv" | cut -c1-12)"
# the FP + props blend file: 0.5 FP + 0.5 market_points where the frame holds a REAL prop number (not the dk_ppg fallback), else FP
"$LAB_PY" - "$I/proj_fp-w4.csv" "$W4/20261004T155026918221Z-32cdb61/frame.parquet" "$R/proj_blend-w4.csv" <<'PY'
import sys, pandas as pd, numpy as np
fp = pd.read_csv(sys.argv[1]); fr = pd.read_parquet(sys.argv[2])
mp = pd.to_numeric(fr.market_points, errors="coerce"); dk = pd.to_numeric(fr.dk_ppg, errors="coerce")
real = mp.notna() & ((mp - dk).abs() >= 0.01)
m = dict(zip(fr.loc[real, "dk_draftable_id"].astype("Int64").astype(str), mp[real]))
b = fp.copy(); key = b.dk_draftable_id.astype("Int64").astype(str); props = key.map(m)
b["fp"] = np.where(props.notna(), 0.5 * b.fp + 0.5 * props, b.fp)
b.to_csv(sys.argv[3], index=False); print(f"  blend file: {int(props.notna().sum())} of {len(b)} players blended with a real prop number")
PY
union() {  # $1 out name, rest: extra args (a repeated option takes the LAST value)
  local out=$1; shift
  ( cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py \
      --saturday-run auto --saturday-dose 2560/10240,1280/5120 --t70-run "$W4/20261004T155026918221Z-32cdb61" --live-dir "$W4" \
      --group 154078 --saturday-after 2026-10-03T05:00:00 --entries 26 --tail-sleeve 0 --mean-max-shared 7 --min-proj 1.0 \
      --max-per-game 4 --min-salary 49000 --pmo 0 --pmo-cap-share 0.5 --main-cap-share 0.5 --main-dst-cap 0.25 \
      --sleeve-includes-main --mean-dst-cap 0.25 --rehearsal \
      --main mix --mix-portfolio mix --mix-plan "$PLAN" --mix-layout head --mix-spares 15 \
      --main-qb-cap-rows 5 --main-qb-cap-k 26 --proj-source "$I/proj_fp-w4.csv" "$@" --out "$R/$out" ) > "$R/$out.txt" 2>&1
  echo "  union $out rc $? ($(grep -c -E 'REFUSED|Traceback' "$R/$out.txt") refusal lines) $(date +%H:%M:%S)"
}
union base
union ms6   --mean-max-shared 6
union ms5   --mean-max-shared 5
union qb4   --main-qb-cap-rows 4 --main-qb-cap-k 26
union qb3   --main-qb-cap-rows 3 --main-qb-cap-k 26
union mpg3  --max-per-game 3
union cap35 --main-cap-share 0.35
union blend --proj-source "$R/proj_blend-w4.csv"
union ms5qb4 --mean-max-shared 5 --main-qb-cap-rows 4 --main-qb-cap-k 26
ARMS="base ms6 ms5 qb4 qb3 mpg3 cap35 blend ms5qb4"
for a in $ARMS; do
  [ -f "$R/$a/book.csv" ] || { echo "  layout $a SKIPPED (no book)"; continue; }
  mkdir -p "$R/stage-$a"
  ( cd "$PROD" && ENTER_SMALL_MAX_SHARED=5 ENTER_SMALL_OVERLAP_MAX_ENTRIES=10 PYTHONPATH="$PROD/src" "$PY" -m nfl_dfs.inference.enter_layout write "$PLAN" "$R/$a/book.csv" "$R/stage-$a" --layout head ) > "$R/stage-$a.txt" 2>&1
  echo "  layout $a rc $?"
done
PYTHONPATH="$PROD/src" "$LAB_PY" - "$R" "$PROD" "$OWN" $ARMS <<'PYEOF'
import csv, importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
R, PROD, OWN = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); ARMS = sys.argv[4:]
spec = importlib.util.spec_from_file_location("MS", PROD / "scripts" / "moneygate_score.py"); MS = importlib.util.module_from_spec(spec); sys.modules["MS"] = MS; spec.loader.exec_module(MS)
sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/experiments")); sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/src"))
from s24_qb_game_cap import big_seat_stats
W = MS.load_week(MS.load_config(), 4)
MILLY = "196151357"
others = np.asarray(W.others_sorted(MILLY), np.int64)            # the real W4 Milly field without any entry of ours
plan = json.loads((Path.home() / "s24-panel/plan-week5-rev3-s24.json").read_text())["contests"]
own = pd.read_csv(OWN); own_col = next((c for c in own.columns if "own" in c.lower() and c != "name"), None)
own_by_id = dict(zip(own.iloc[:, 0].astype(str), pd.to_numeric(own[own_col], errors="coerce"))) if own_col else {}
# the field's rosters, if the loader keeps them (exact copies per row)
field_keys = None
for attr in ("entries", "field", "lineups", "rows"):
    obj = getattr(W, attr, None)
    if isinstance(obj, pd.DataFrame) and "players_key" in obj.columns:
        f = obj[obj.contest_id.astype(str) == MILLY] if "contest_id" in obj.columns else obj
        field_keys = f.players_key.astype(str).value_counts().to_dict(); break
out = {}
for a in ARMS:
    if not (R / a / "book.csv").exists(): continue
    fr = pd.read_parquet(R / a / "frame.parquet")
    name = dict(zip(fr.dk_player_id.astype("Int64").astype(str), fr.display_name)); pos = dict(zip(fr.dk_player_id.astype("Int64").astype(str), fr.pos.astype(str)))
    game = dict(zip(fr.dk_player_id.astype("Int64").astype(str), fr.game_id.astype(str)))
    rows = list(csv.reader(open(R / a / "book.csv")))[1:]
    pts = np.array([sum(W.fpts.get(MS.canon(name.get(p, "")), 0) for p in r) for r in rows], np.int64)
    F = np.searchsorted(others, pts, "left") / len(others)                # share of the field each row BEATS (ties lose)
    rm = json.loads((R / f"stage-{a}" / "ENTER-rowmap.json").read_text())
    ranks = [rm[f"{c['name']}-{c['contest_id']}"] for c in plan]
    st = big_seat_stats(F, ranks, plan)
    dealt = [i for rr in ranks for i in rr]
    book = rows[:26]
    cnt = pd.Series([p for r in book for p in r]).value_counts()
    qbs = {p for r in book for p in r if pos.get(p) == "QB"}; games = {game.get(p) for r in book for p in r}
    own_sum = [sum(own_by_id.get(p, 0) or 0 for p in r) for r in book] if own_by_id else None
    copies = None
    if field_keys is not None:
        keys = ["|".join(sorted(MS.canon(name.get(p, "")) for p in r)) for r in book]
        copies = sum(field_keys.get(k, 0) > 0 for k in keys)
    out[a] = {**{k: round(v, 4) for k, v in st.items()}, "mean_entry_pct": round(float(F[dealt].mean()), 4),
              "mean_entry_points": round(float(pts[dealt].mean()) / 100, 2), "best_row_points": round(float(pts[:26].max()) / 100, 2),
              "rows_top1pct": int((F[:26] >= 0.99).sum()), "rows_top5pct": int((F[:26] >= 0.95).sum()),
              "distinct_players": int(len(cnt)), "players_at_cap13": int((cnt >= 13).sum()), "players_over_9": int((cnt > 9).sum()),
              "max_exposure": int(cnt.max()), "qbs": len(qbs), "games": len(games),
              "own_sum_mean": round(float(np.mean(own_sum)), 1) if own_sum else None, "rows_with_field_copy": copies, "dealt_entries": len(dealt)}
cols = ["p_big1", "e_big", "mean_entry_pct", "mean_entry_points", "best_row_points", "rows_top1pct", "rows_top5pct", "distinct_players", "players_at_cap13", "players_over_9", "max_exposure", "qbs", "games", "own_sum_mean", "rows_with_field_copy"]
print("\n" + pd.DataFrame(out).T[cols].to_string())
(R / "score.json").write_text(json.dumps(out, indent=1) + "\n")
PYEOF
echo "== done $(date +%H:%M:%S); scratch $R; worktree $PROD"
