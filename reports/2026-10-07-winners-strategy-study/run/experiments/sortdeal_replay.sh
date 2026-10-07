#!/usr/bin/env bash
# The TD deal, W2-4 re-deal (reports/2026-10-07-td-deal-harm-screen.md, frozen c9028505 before any number): the LIVE books of a
# bonus-blocks replay run re-dealt by (a) DEAL_TD, the lineup's summed market td_prob (td_value_block_file.py's column at the
# Saturday 10:00 CT cut; every rostered player with a price, QB included; DST / unpriced 0), and (b) DEAL_PROJ (control), the
# lineup's proj_sum; highest first, ties keeping the book order; the spares untouched. Each deal through production's head
# layout (Rev3) and scored as the block replays (big_seat_stats). No new builds.
#   bash td_deal_replay.sh <bonus-blocks run dir> <input dir with tdup-w*.csv>
set -uo pipefail
R=${1:?bonus-blocks run dir}; IN=${2:?input dir}
PROD=$(ls -d "$HOME"/projects/.nfl-predictions-worktrees/rehearsal-outside-cblocks-"$(basename "$R" | sed 's/^outside-cblocks-//')" 2>/dev/null) || true
[[ -d "$PROD" ]] || { echo "no production worktree for $R"; exit 2; }
PLAN=$HOME/week5-sunday/contests.json; PY=$HOME/projects/nfl-predictions/.venv/bin/python; LAB_PY=$HOME/projects/nfl2/.venv/bin/python
echo "== sort-key re-deal (cheap count, market minus projection): run $R, code $(git -C "$PROD" rev-parse --short HEAD)"
for w in 2 3 4; do
  for a in cheapdeal mktdeal projdeal; do
    D=$R/w$w-$a; rm -rf "$D"; mkdir -p "$D"
    "$PY" - "$R/w$w-live" "$D" "-" "$a" <<'PYEOF' || { echo "  re-deal w$w $a FAILED"; continue; }
import csv, json, shutil, sys
from pathlib import Path
import pandas as pd
src, dst, tdf, arm = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4]
rows = list(csv.reader(open(src / "book.csv"))); header, body = rows[0], rows[1:]
book, spares = body[:26], body[26:]
bj = json.loads((src / "book.json").read_text()); ents = bj["entries"]
fr0 = pd.read_parquet(src / "frame.parquet"); nm = dict(zip(fr0.dk_player_id.astype("Int64").astype(str), fr0.display_name.astype(str)))
assert len(ents) >= 26 and all(sorted(map(str, e["players"])) == sorted(nm.get(p, p) for p in r) for e, r in zip(ents[:26], book)), "book.json / book.csv disagree"
ids = fr0.dk_player_id.astype("Int64").astype(str)
cheap = dict(zip(ids, ((fr0.salary < 4000) & (fr0.pos.astype(str) != "DST")).astype(float)))
mk = pd.to_numeric(fr0.market_points, errors="coerce"); pj = pd.to_numeric(fr0.mean_projection, errors="coerce"); dk = pd.to_numeric(fr0.dk_ppg, errors="coerce")
mkt = dict(zip(ids, (mk - pj).where(mk.notna() & ((mk - dk).abs() >= 0.01)).fillna(0.0)))
if arm == "cheapdeal": key = [sum(cheap.get(p, 0.0) for p in r) for r in book]
elif arm == "mktdeal": key = [sum(mkt.get(p, 0.0) for p in r) for r in book]
else: key = [float(e["proj_sum"]) for e in ents[:26]]
order = sorted(range(26), key=lambda i: (-key[i], i))
with open(dst / "book.csv", "w", newline="") as h:
    wr = csv.writer(h); wr.writerow(header); wr.writerows([book[i] for i in order] + spares)
bj["entries"] = [ents[i] for i in order] + ents[26:]
(dst / "book.json").write_text(json.dumps(bj, indent=1) + "\n")
shutil.copy2(src / "frame.parquet", dst / "frame.parquet")
(dst / "deal.json").write_text(json.dumps({"arm": arm, "order": order, "key": [round(k, 4) for k in key], "moved": sum(o != i for i, o in enumerate(order))}) + "\n")
print(f"  re-deal {src.name} -> {dst.name}: {sum(o != i for i, o in enumerate(order))} of 26 positions moved; key range {min(key):.2f}-{max(key):.2f}")
PYEOF
    mkdir -p "$R/stage-w$w-$a"
    ( cd "$PROD" && ENTER_SMALL_MAX_SHARED=5 ENTER_SMALL_OVERLAP_MAX_ENTRIES=10 PYTHONPATH="$PROD/src" "$PY" -m nfl_dfs.inference.enter_layout write "$PLAN" "$D/book.csv" "$R/stage-w$w-$a" --layout head ) > "$R/stage-w$w-$a.txt" 2>&1; echo "  layout w$w $a rc $?"
  done
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
    for a in ("live", "cheapdeal", "mktdeal", "projdeal"):
        d = R / f"w{w}-{a}"
        if not (d / "book.csv").exists(): continue
        fr = pd.read_parquet(d / "frame.parquet"); key = fr.dk_player_id.astype("Int64").astype(str); name = dict(zip(key, fr.display_name))
        rows = list(csv.reader(open(d / "book.csv")))[1:]
        pts = np.array([sum(W.fpts.get(MS.canon(name.get(p, "")), 0) for p in r) for r in rows], np.int64); F = np.searchsorted(others, pts, "left") / len(others)
        rm = json.loads((R / f"stage-w{w}-{a}" / "ENTER-rowmap.json").read_text()); ranks = [rm[f"{c['name']}-{c['contest_id']}"] for c in plan]
        st = big_seat_stats(F, ranks, plan); dealt = [i for rr in ranks for i in rr]
        out[f"w{w}-{a}"] = {"p_big1": round(st["p_big1"], 4), "e_big": round(st["e_big"], 4), "mean_entry_pct": round(float(F[dealt].mean()), 4),
                            "best_row": round(float(pts[:26].max()) / 100, 2), "rows_top1pct": int((F[:26] >= 0.99).sum())}
df = pd.DataFrame(out).T; print("\n" + df.to_string())
for a in ("cheapdeal", "mktdeal", "projdeal"):
    below = sum(out[f"w{w}-{a}"]["p_big1"] < out[f"w{w}-live"]["p_big1"] for w in (2, 3, 4) if f"w{w}-{a}" in out)
    ratio = sum(out[f"w{w}-{a}"]["e_big"] for w in (2, 3, 4)) / max(sum(out[f"w{w}-live"]["e_big"] for w in (2, 3, 4)), 1e-12)
    print(f"{a}: P(>=1 big) below LIVE in {below} of 3 weeks; pooled e_big ratio {ratio:.3f}" + "")
(R / "sort_deal_score.json").write_text(json.dumps(out, indent=1) + "\n")
PYEOF
echo "== done $(date +%H:%M:%S)"
