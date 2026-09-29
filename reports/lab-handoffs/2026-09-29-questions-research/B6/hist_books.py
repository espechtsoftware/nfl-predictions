"""B6 dumb-baseline books on 12 historical development slates (2023-24, every third of the 36).
Read-only; one CBC solve at a time. Scores on the snapshot's `actual` column (post-game, nflverse).
dk_ppg is not in the historical snapshot: `dk_points_l4` (trailing-4-week DK points, point-in-time) stands in.
"""
import json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OMP_THREAD_LIMIT", "1")
import numpy as np, pandas as pd
from nfl2 import data, pipeline
from nfl2.core.lineup import optimize, StackRules

OUT = os.path.dirname(os.path.abspath(__file__)) + "/out"
K = 36


def players_for(frame, col, dst_col="proj", universe_col=None):
    rows = []
    for r in frame.itertuples(index=False):
        v = getattr(r, dst_col) if r.pos == "DST" else getattr(r, col)
        if v is None or pd.isna(v):
            continue
        if universe_col and r.pos != "DST" and pd.isna(getattr(r, universe_col)):
            continue
        rows.append(dict(id=r.id, name=r.name, pos=r.pos, team=r.team, opp=r.opp, game_id=r.game_id,
                         salary=int(r.salary), proj=float(v), actual=float(r.actual) if pd.notna(r.actual) else 0.0))
    return rows


def build(players, house=False):
    kw = dict(min_salary=0, env={}, punt_min=0, max_overlap=7, stack=None)
    if house:
        kw.update(min_salary=49_000, stack=StackRules(qb_stack_min=2, bring_back_min=1))
    banned, book = [], []
    for _ in range(K):
        lu = optimize(players, banned_lineups=banned, **kw)
        if lu is None:
            break
        banned.append(lu.ids); book.append(lu)
    return book


def summarize(scores):
    sc = np.array(scores)
    if len(sc) == 0:
        return dict(n=0, mean=None, best=None, share_150=None, share_194=None, note="infeasible: objective column empty for this slate")
    return dict(n=len(sc), mean=round(float(sc.mean()), 2), best=round(float(sc.max()), 2),
                share_150=round(float((sc >= 150).mean()), 3), share_194=round(float((sc >= 194).mean()), 3))


def main():
    all_slates = [s for s in data.slates("k1") if s[0] in (2023, 2024)]
    assert len(all_slates) == 36, len(all_slates)
    chosen = all_slates[::3]
    books = sys.argv[1].split(",") if len(sys.argv) > 1 else ["market", "dk_l4", "served", "served_house"]
    path = f"{OUT}/hist.json"
    res = json.load(open(path)) if os.path.exists(path) else {}
    for season, week in chosen:
        key = f"{season}-w{week:02d}"
        fr = pipeline.slate_frame(season, week)
        fr = data.dev_only(fr)
        entry = res.setdefault(key, {})
        entry.update(rows=len(fr), market_rows=int(fr.market_points.notna().sum()), l4_rows=int(fr.dk_points_l4.notna().sum()),
                     actual_rows=int(fr.actual.notna().sum()))
        for b in books:
            if b in entry:
                continue
            col = {"market": "market_points", "dk_l4": "dk_points_l4", "served": "proj", "served_house": "proj",
                   "served_mktpool": "proj", "served_mean": "mean_projection", "served_mean_house": "mean_projection",
                   "model_pre": "model_points_pre"}[b]
            pl = players_for(fr, col, universe_col="market_points" if b == "served_mktpool" else None)
            t0 = time.time()
            book = build(pl, house=b.endswith("_house"))
            scores = [sum(p["actual"] for p in lu.players) for lu in book]
            zero_slots = sum(1 for lu in book for p in lu.players if p["actual"] == 0.0)
            s = summarize(scores); s["zero_actual_slots"] = zero_slots; s.update(pool=len(pl), secs=round(time.time() - t0, 1), scores=[round(x, 2) for x in scores])
            entry[b] = s
            print(key, b, {k: v for k, v in s.items() if k != "scores"}, flush=True)
            json.dump(res, open(path, "w"), indent=1)


if __name__ == "__main__":
    main()
