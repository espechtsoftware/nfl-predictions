#!/usr/bin/env bash
# The operator's BONUS BLOCKS, exact Week-5 form (10-07: the matchup bonus "this week", and "I would like to test the under
# $7000 player idea before this week - not as paper"): W2-4 fixed-book replay on the real fields, the live Week-5 book
# (ms4 + round-robin, QB cap 5, no ownership term, Rev3 K 26) vs the same build with 8 of 26 rows on projection +
# min(0.20 x pred_own, 2.0) from (a) matchup_block_file.py, (b) td_value_block_file.py (the outside reviewer's make_tdup_files.py formula:
# RB/WR/TE under $7,000, clip(z of the anytime-TD probability's residual on salary within position, 0, 2)), (c) both summed
# (the block's 2.0 cap applies to the sum). IN-SAMPLE weeks (both ideas came from W1-4 / W2-4). Scoring as the prior-top
# block replay (big_seat_stats on the Rev3 plan).
#   bash bonus_blocks_replay.sh <production commit with --term-block-rows> <dir holding tdup-w*.csv and mtd-w*.csv>
set -uo pipefail
COMMIT=${1:?commit}; IN=${2:?input dir}; TS=$(date -u +%Y%m%dT%H%M%SZ); R=$HOME/rehearsals/outside-cblocks-$TS; mkdir -p "$R"
I=$HOME/.cache/laptop-agent/rehearsal/inputs
PROD=$HOME/projects/.nfl-predictions-worktrees/rehearsal-outside-cblocks-$TS; echo "$PROD" >> /tmp/claude-1000/-home-erich-projects-nfl-predictions/5b45848a-b7d8-4455-85c7-aaa433f36ba3/scratchpad/my_worktrees.txt
git -C "$HOME/projects/nfl-predictions" fetch -q origin && git -C "$HOME/projects/nfl-predictions" worktree add -q --detach "$PROD" "$COMMIT" || exit 1
for w in 2 3 4; do for f in cheap2 cheap4; do cp "$IN/$f-w$w.csv" "$R/$f-w$w.csv"; done; done   # the production writers at eac78311 (Saturday 10:00 CT props cut)
CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center; LAB_PY=$HOME/projects/nfl2/.venv/bin/python; PY=$HOME/projects/nfl-predictions/.venv/bin/python
PLAN=$HOME/week5-sunday/contests.json; LIVE=$HOME/moneygate/inputs/runs; W4=$HOME/projects/.nfl2-worktrees/week4-live-center/results/live/2026-w04
declare -A T70=([2]=$LIVE/20260920T155005557498Z-2dc116c [3]=$LIVE/20260927T155027472554Z-65305f5 [4]=$W4/20261004T155026918221Z-32cdb61)
declare -A LD=([2]=$LIVE [3]=$LIVE [4]=$W4); declare -A GROUP=([2]=153428 [3]=153769 [4]=154078)
declare -A AFTER=([2]=2026-09-18T05:00:00 [3]=2026-09-25T05:00:00 [4]=2026-10-03T05:00:00)
echo "== bonus-blocks replay $TS: code $(git -C "$PROD" rev-parse --short HEAD), lab $(git -C "$CLONE" rev-parse --short HEAD), files $(sha256sum "$R"/{cheap2,cheap4}-w{2,3,4}.csv | cut -c1-8 | tr '\n' ' ')"
union() { local w=$1 out=$2; shift 2; local ps=(); [ "$w" = 4 ] && ps=(--proj-source "$I/proj_fp-w4.csv")
  ( cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py \
      --saturday-run auto --saturday-dose 2560/10240,1280/5120 --t70-run "${T70[$w]}" --live-dir "${LD[$w]}" --group "${GROUP[$w]}" \
      --saturday-after "${AFTER[$w]}" --entries 26 --tail-sleeve 0 --mean-max-shared 4 --min-proj 1.0 --max-per-game 4 --min-salary 49000 \
      --pmo 0 --pmo-cap-share 0.5 --main-cap-share 0.5 --main-dst-cap 0.25 --sleeve-includes-main --mean-dst-cap 0.25 --rehearsal \
      --main mix --mix-portfolio mix --mix-plan "$PLAN" --mix-layout head --mix-spares 15 --mix-fill rr --main-qb-cap-rows 5 --main-qb-cap-k 26 \
      "${ps[@]}" "$@" --out "$R/w$w-$out" ) > "$R/w$w-$out.txt" 2>&1
  echo "  union w$w $out rc $? ($(grep -c -E 'REFUSED|Traceback|NOT APPLIED' "$R/w$w-$out.txt") refusal lines; $(grep -h 'TERM BLOCK' "$R/w$w-$out.txt" | head -1 | cut -c1-120)) $(date +%H:%M:%S)"; }
for w in 2 3 4; do
  union $w live
  union $w cblock2 --term-block-rows 8 --term-block-source "$R/cheap2-w$w.csv" --term-block-tilt 0.20 --term-block-cap-points 2.0
  union $w cblock4 --term-block-rows 8 --term-block-source "$R/cheap4-w$w.csv" --term-block-tilt 0.20 --term-block-cap-points 4.0
  for a in live cblock2 cblock4; do mkdir -p "$R/stage-w$w-$a"; [ -f "$R/w$w-$a/book.csv" ] || { echo "  layout w$w $a SKIPPED"; continue; }
    ( cd "$PROD" && ENTER_SMALL_MAX_SHARED=5 ENTER_SMALL_OVERLAP_MAX_ENTRIES=10 PYTHONPATH="$PROD/src" "$PY" -m nfl_dfs.inference.enter_layout write "$PLAN" "$R/w$w-$a/book.csv" "$R/stage-w$w-$a" --layout head ) > "$R/stage-w$w-$a.txt" 2>&1; echo "  layout w$w $a rc $?"; done
done
PYTHONPATH="$PROD/src" "$LAB_PY" - "$R" "$PROD" <<'PYEOF'
import csv, importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
R, PROD = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("MS", PROD / "scripts" / "moneygate_score.py"); MS = importlib.util.module_from_spec(spec); sys.modules["MS"] = MS; spec.loader.exec_module(MS)
sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/experiments")); sys.path.insert(0, str(Path.home() / "projects/.nfl2-worktrees/s30-census-check/src"))
from s24_qb_game_cap import big_seat_stats
cfg = MS.load_config(); plan = json.loads((Path.home() / "s24-panel/plan-week5-rev3-s24.json").read_text())["contests"]; out = {}
for w in (2, 3, 4):
    W = MS.load_week(cfg, w); others = np.asarray(W.others_sorted(MS.milly_cid(W)), np.int64)
    SRCF = {"cblock2": "cheap2", "cblock4": "cheap4"}
    for a in ("live", "cblock2", "cblock4"):
        d = R / f"w{w}-{a}"
        if not (d / "book.csv").exists(): continue
        fr = pd.read_parquet(d / "frame.parquet"); key = fr.dk_player_id.astype("Int64").astype(str); name = dict(zip(key, fr.display_name))
        rows = list(csv.reader(open(d / "book.csv")))[1:]; ents = json.loads((d / "book.json").read_text())["entries"][:26]
        pts = np.array([sum(W.fpts.get(MS.canon(name.get(p, "")), 0) for p in r) for r in rows], np.int64); F = np.searchsorted(others, pts, "left") / len(others)
        rm = json.loads((R / f"stage-w{w}-{a}" / "ENTER-rowmap.json").read_text()); ranks = [rm[f"{c['name']}-{c['contest_id']}"] for c in plan]
        st = big_seat_stats(F, ranks, plan); dealt = [i for rr in ranks for i in rr]; book = rows[:26]
        rec = {"p_big1": round(st["p_big1"], 4), "e_big": round(st["e_big"], 4), "mean_entry_pct": round(float(F[dealt].mean()), 4),
               "proj_sum_mean": round(float(np.mean([e["proj_sum"] for e in ents])), 2), "best_row": round(float(pts[:26].max()) / 100, 2),
               "rows_top1pct": int((F[:26] >= 0.99).sum()), "distinct_players": len({p for r in book for p in r})}
        if a != "live":
            pt = pd.read_csv(R / f"{SRCF[a]}-w{w}.csv", dtype={"dk_player_id": str}); top5 = set(pt[pt.dk_player_id.isin(set(key))].sort_values("pred_own", ascending=False).head(5).dk_player_id)
            rc = json.loads((d / "receipt.json").read_text())["config"]["union"]["mix"]["mix"]
            blocks = rc["term"]["blocks"]; T = [i for i, b in enumerate(blocks) if b == "T"]; L = [i for i, b in enumerate(blocks) if b == "L"]
            base = set(frozenset(r) for r in list(csv.reader(open(R / f"w{w}-live" / "book.csv")))[1:][:26])
            rec.update({"term_positions": T, "term_rows_mean_pct": round(float(F[T].mean()), 4), "live_block_mean_pct": round(float(F[L].mean()), 4),
                        "term_rows_best": round(float(pts[T].max()) / 100, 2), "term_rows_with_a_top5_bonus_player": int(sum(bool(set(book[i]) & top5) for i in T)),
                        "top5_bonus_players": [name.get(p, p) for p in top5], "rows_same_as_live": sum(frozenset(r) in base for r in book),
                        "term_source": {k: rc["term_source"].get(k) for k in ("source_sha256", "coverage_projected_5", "players_with_a_term", "players_capped", "cap_points")}})
        out[f"w{w}-{a}"] = rec
df = pd.DataFrame({k: {x: v for x, v in r.items() if not isinstance(v, (list, dict))} for k, r in out.items()}).T; print("\n" + df.to_string())
for k, r in out.items():
    if "term_positions" in r: print(k, "term positions", r["term_positions"], "top-5 bonus players", r["top5_bonus_players"], "source", r["term_source"])
(R / "score.json").write_text(json.dumps(out, indent=1) + "\n")
PYEOF
echo "== done $(date +%H:%M:%S); scratch $R; worktree $PROD"
