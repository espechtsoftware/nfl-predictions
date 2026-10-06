#!/usr/bin/env bash
# Fill-order replay (group vs value) on Weeks 2-4 real fields at the live Week-5 settings (ms5, QB cap 5, no term); the
# production switch a7fafd38 (--mix-fill). W4 under FP, W2-3 under our projections. Same harness as the lever screen.
set -uo pipefail
COMMIT=${1:?commit}; R=${2:?run dir}; I=$HOME/.cache/laptop-agent/rehearsal/inputs
PROD=$HOME/projects/.nfl-predictions-worktrees/rehearsal-fill-$(basename "$R")
[ -d "$PROD" ] || git -C "$HOME/projects/nfl-predictions" worktree add -q --detach "$PROD" "$COMMIT" || exit 1
CLONE=$HOME/projects/.nfl2-worktrees/week5-live-center; LAB_PY=$HOME/projects/nfl2/.venv/bin/python; PY=$HOME/projects/nfl-predictions/.venv/bin/python
PLAN=$HOME/week5-sunday/contests.json; LIVE=$HOME/moneygate/inputs/runs; W4=$HOME/projects/.nfl2-worktrees/week4-live-center/results/live/2026-w04
declare -A T70=([2]=$LIVE/20260920T155005557498Z-2dc116c [3]=$LIVE/20260927T155027472554Z-65305f5 [4]=$W4/20261004T155026918221Z-32cdb61)
declare -A LD=([2]=$LIVE [3]=$LIVE [4]=$W4); declare -A GROUP=([2]=153428 [3]=153769 [4]=154078)
declare -A AFTER=([2]=2026-09-18T05:00:00 [3]=2026-09-25T05:00:00 [4]=2026-10-03T05:00:00)
echo "== fill-order replay $(date -u +%FT%TZ): code $(git -C "$PROD" rev-parse --short HEAD), lab $(git -C "$CLONE" rev-parse --short HEAD), plan $(sha256sum "$PLAN" | cut -c1-12)"
union() { local w=$1 out=$2; shift 2; local ps=(); [ "$w" = 4 ] && ps=(--proj-source "$I/proj_fp-w4.csv")
  ( cd "$PROD" && LIVE_FLEX_LATEST=1 PYTHONPATH="$CLONE/src:$PROD/src" "$LAB_PY" scripts/union_reselect.py \
      --saturday-run auto --saturday-dose 2560/10240,1280/5120 --t70-run "${T70[$w]}" --live-dir "${LD[$w]}" --group "${GROUP[$w]}" \
      --saturday-after "${AFTER[$w]}" --entries 26 --tail-sleeve 0 --mean-max-shared 5 --min-proj 1.0 --max-per-game 4 --min-salary 49000 \
      --pmo 0 --pmo-cap-share 0.5 --main-cap-share 0.5 --main-dst-cap 0.25 --sleeve-includes-main --mean-dst-cap 0.25 --rehearsal \
      --main mix --mix-portfolio mix --mix-plan "$PLAN" --mix-layout head --mix-spares 15 --main-qb-cap-rows 5 --main-qb-cap-k 26 \
      "${ps[@]}" "$@" --out "$R/w$w-$out" ) > "$R/w$w-$out.txt" 2>&1
  echo "  union w$w $out rc $? ($(grep -c -E 'REFUSED|Traceback' "$R/w$w-$out.txt") refusal lines) $(date +%H:%M:%S)"; }
for w in 2 3 4; do union $w group --mix-fill group; union $w value --mix-fill value
  for a in group value; do mkdir -p "$R/stage-w$w-$a"
    ( cd "$PROD" && ENTER_SMALL_MAX_SHARED=5 ENTER_SMALL_OVERLAP_MAX_ENTRIES=10 PYTHONPATH="$PROD/src" "$PY" -m nfl_dfs.inference.enter_layout write "$PLAN" "$R/w$w-$a/book.csv" "$R/stage-w$w-$a" --layout head ) > "$R/stage-w$w-$a.txt" 2>&1; echo "  layout w$w $a rc $?"; done; done
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
    for a in ("group", "value"):
        d = R / f"w{w}-{a}"
        if not (d / "book.csv").exists(): continue
        fr = pd.read_parquet(d / "frame.parquet"); key = fr.dk_player_id.astype("Int64").astype(str); name = dict(zip(key, fr.display_name)); pos = dict(zip(key, fr.pos.astype(str)))
        rows = list(csv.reader(open(d / "book.csv")))[1:]; ents = json.loads((d / "book.json").read_text())["entries"][:26]; cells = [e["tag"].split("_")[1] for e in ents]
        pts = np.array([sum(W.fpts.get(MS.canon(name.get(p, "")), 0) for p in r) for r in rows], np.int64); F = np.searchsorted(others, pts, "left") / len(others)
        rm = json.loads((R / f"stage-w{w}-{a}" / "ENTER-rowmap.json").read_text()); ranks = [rm[f"{c['name']}-{c['contest_id']}"] for c in plan]
        st = big_seat_stats(F, ranks, plan); dealt = [i for rr in ranks for i in rr]; book = rows[:26]
        qbrows = {}
        for r, c in zip(book, cells):
            q = next((name.get(p) for p in r if pos.get(p) == "QB"), "?"); qbrows.setdefault(q, []).append(c)
        top = np.argsort(-pts[:26])[:3]
        out[f"w{w}-{a}"] = {"p_big1": round(st["p_big1"], 4), "e_big": round(st["e_big"], 4), "mean_entry_pct": round(float(F[dealt].mean()), 4),
            "proj_sum_mean": round(float(np.mean([e["proj_sum"] for e in ents])), 2), "best_row": round(float(pts[:26].max()) / 100, 2),
            "top3": ", ".join(f"{pts[i]/100:.1f} {cells[i]}" for i in top), "qbs": len(qbrows),
            "top_qb_shapes": "; ".join(f"{q.split()[-1]}:{''.join(sorted(v))}" for q, v in sorted(qbrows.items(), key=lambda kv: -len(kv[1]))[:4])}
df = pd.DataFrame(out).T; print("\n" + df.to_string()); (R / "score.json").write_text(json.dumps(out, indent=1) + "\n")
PYEOF
echo "== done $(date +%H:%M:%S); scratch $R; worktree $PROD"
