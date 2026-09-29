"""B6 dumb-baseline books on the live 2026 frames (read-only; one CBC solve at a time).

Usage: live_books.py <tag> [--books market,dk_ppg,served,...] [--k 36]
Tags: w1 (entered source run K90), w2 (entered D12800), w3sat, w3t70.
"""
import csv, glob, json, os, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1"); os.environ.setdefault("OMP_THREAD_LIMIT", "1")
import numpy as np, pandas as pd
from nfl2.core.lineup import optimize, StackRules

WT = "/home/erich/projects/.nfl2-worktrees"
FRAMES = {
    "w1": (WT + "/week1-live-center-e7255e9/results/live/2026-w01/20260913T160405364118Z-e7255e9", 165.5),
    "w2": (WT + "/week2-release-2dc116c/results/live/2026-w02/20260919T153008787414Z-2dc116c", 138.0),
    "w3sat": (WT + "/week3-live-center/results/live/2026-w03/20260926T153408285093Z-65305f5", 149.5),
    "w3t70": (WT + "/week3-live-center/results/live/2026-w03/20260927T155027472554Z-65305f5", 149.5),
}
OUT = os.path.dirname(os.path.abspath(__file__)) + "/out"


def load_actuals(tag):
    """name -> realized DK points. Information time: post-game (scoring only)."""
    if tag == "w1":
        d = pd.read_csv(os.path.expanduser("~/week3-sunday/postmortem/w1_actuals.csv"))
        return dict(zip(d.display_name, d.fpts)), "w1_actuals.csv (DK standings export, Week 1)"
    if tag.startswith("w3"):
        d = pd.read_csv(os.path.expanduser("~/week3-sunday/postmortem/players_actuals.csv"))
        return dict(zip(d.name_, d.fpts)), "players_actuals.csv (DK standings export, Week 3)"
    if tag == "w2":
        m = {}
        for f in sorted(glob.glob(os.path.expanduser("~/week2-sunday/ENTERED/standings/contest-standings-*.csv"))):
            d = pd.read_csv(f, encoding="utf-8-sig")
            d = d[["Player", "FPTS"]].dropna()
            for n, p in zip(d.Player, d.FPTS):
                m[str(n).strip()] = float(p)
        return m, "union of 12 Week-2 DK standings exports (Player/FPTS columns)"
    raise KeyError(tag)


def frame_players(frame, value_col, dst_col="proj", universe_col=None):
    """DK-legal pool for one objective. Rows lacking the objective value are dropped
    (a consensus optimizer never sees a player it has no number for)."""
    rows = []
    for r in frame.itertuples(index=False):
        v = getattr(r, dst_col) if r.pos == "DST" else getattr(r, value_col)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        if universe_col and r.pos != "DST" and pd.isna(getattr(r, universe_col)):
            continue
        rows.append(dict(id=r.id, name=r.name, pos=r.pos, team=r.team, opp=r.opp, game_id=r.game_id,
                         salary=int(r.salary), proj=float(v)))
    return rows


def build_book(players, k, house=False):
    banned, book, t0 = [], [], time.time()
    kw = dict(min_salary=0, env={}, punt_min=0, max_overlap=7, stack=None)
    if house:
        kw.update(min_salary=49_000, stack=StackRules(qb_stack_min=2, bring_back_min=1))
    for i in range(k):
        lu = optimize(players, banned_lineups=banned, **kw)
        if lu is None:
            break
        banned.append(lu.ids); book.append(lu)
    return book, time.time() - t0


def score(book, actual_by_name, line):
    scores, missing = [], 0
    for lu in book:
        s = 0.0
        for p in lu.players:
            a = actual_by_name.get(p["name"])
            if a is None:
                missing += 1
            else:
                s += float(a)
        scores.append(s)
    sc = np.array(scores)
    idsets = [lu.ids for lu in book]
    from collections import Counter
    cnt = Counter(p["name"] for lu in book for p in lu.players)
    ov = [len(a & b) for i, a in enumerate(idsets) for b in idsets[i + 1:]]
    return dict(n=len(sc), mean=round(float(sc.mean()), 2), median=round(float(np.median(sc)), 2), best=round(float(sc.max()), 2),
                share_cash=round(float((sc >= line).mean()), 3), share_150=round(float((sc >= 150).mean()), 3),
                share_194=round(float((sc >= 194).mean()), 3), missing_actual_slots=missing,
                proj_mean=round(float(np.mean([lu.proj for lu in book])), 2),
                distinct_players=len(cnt), mean_pairwise_overlap=round(float(np.mean(ov)), 2) if ov else None,
                core_ge50pct=[f"{n} {c}/{len(book)} act={actual_by_name.get(n)}" for n, c in cnt.most_common() if c >= len(book) / 2],
                row1=[f"{p['pos']} {p['name']} act={actual_by_name.get(p['name'])}" for p in book[0].players] if book else [],
                scores=[round(x, 2) for x in scores])


def score_book_csv(path, frame, actual_by_name, line, k=None):
    name_by_dk = dict(zip(frame.dk_player_id.astype(int), frame.name))
    rows = list(csv.reader(open(path)))[1:]
    if k:
        rows = rows[:k]
    scores, missing = [], 0
    for r in rows:
        s = 0.0
        for cell in r:
            n = name_by_dk.get(int(cell))
            a = actual_by_name.get(n) if n else None
            if a is None:
                missing += 1
            else:
                s += float(a)
        scores.append(s)
    sc = np.array(scores)
    return dict(n=len(sc), mean=round(sc.mean(), 2), median=round(float(np.median(sc)), 2), best=round(sc.max(), 2),
                share_cash=round(float((sc >= line).mean()), 3), share_150=round(float((sc >= 150).mean()), 3),
                share_194=round(float((sc >= 194).mean()), 3), missing_actual_slots=missing)


def main():
    tag = sys.argv[1]
    books = "market,dk_ppg,served".split(",")
    k = 36
    if "--books" in sys.argv:
        books = sys.argv[sys.argv.index("--books") + 1].split(",")
    if "--k" in sys.argv:
        k = int(sys.argv[sys.argv.index("--k") + 1])
    run, line = FRAMES[tag]
    frame = pd.read_parquet(run + "/frame.parquet")
    actual, asrc = load_actuals(tag)
    matched = frame.name.isin(actual).sum()
    res = dict(tag=tag, run=run, cash_line=line, k=k, frame_rows=len(frame), frame_pulled_at=str(frame.pulled_at.iloc[0]),
               actuals_source=asrc, frame_names_with_actual=int(matched),
               frame_names_without_actual=sorted(frame.name[~frame.name.isin(actual)].tolist()), books={})
    # machine book from the run dir (same scorer, for a like-for-like comparison)
    if os.path.exists(run + "/book.csv"):
        res["run_book_csv"] = score_book_csv(run + "/book.csv", frame, actual, line)
        res["run_book_csv_top36"] = score_book_csv(run + "/book.csv", frame, actual, line, k=36)
    for b in books:
        col = {"market": "market_points", "dk_ppg": "dk_ppg", "served": "proj", "model_pre": "model_points_pre",
               "served_house": "proj", "tourney_house": "proj_tourney", "served_mktpool": "proj",
               "market_house": "market_points"}[b]
        dst_col = "dk_ppg" if b == "dk_ppg" else "proj"
        pl = frame_players(frame, col, dst_col=dst_col, universe_col="market_points" if b == "served_mktpool" else None)
        book, secs = build_book(pl, k, house=b.endswith("_house"))
        sc = score(book, actual, line)
        sc.update(pool_size=len(pl), solve_seconds=round(secs, 1), value_col=col, dst_value_col=dst_col)
        res["books"][b] = sc
        print(tag, b, {kk: vv for kk, vv in sc.items() if kk != "scores"}, flush=True)
    path = f"{OUT}/{tag}.json"
    old = json.load(open(path)) if os.path.exists(path) else {}
    old.update({kk: vv for kk, vv in res.items() if kk != "books"}); old.setdefault("books", {}).update(res["books"])
    json.dump(old, open(path, "w"), indent=1)


if __name__ == "__main__":
    main()
