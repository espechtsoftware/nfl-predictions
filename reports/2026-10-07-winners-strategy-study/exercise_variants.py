"""The winners' exercise, rerun with what the factor analysis found (operator 10-07: "run any experiment that comes out of
these findings"). Same rules per week as the ladder's best layer (W1 environment, W2 environment, W3 salary, W4 ownership);
same targets (first lineup in the real top 1% / top 100 / within 10 of the winner; best within the budget).
  --mode bonus : projection-ordered enumeration on projection + the COMBINED pre-lock factor bonus (matchup, vacated
                 opportunity, market disagreement; weights fixed before any run, see make_factor_files.py), plus the
                 winner-gap diagnostic (max objective - the winner's lineup objective, with and without the bonus)
  --mode boom  : one lineup per simulated world (the archived incumbent_player_scores of that week's T-70 run, worlds
                 in production's order: descending world total), solved under the same rules; duplicates skipped
Usage: exercise_variants.py RUN_DIR OUT_DIR --mode bonus|boom [--weeks 1,2,3,4] [--n 500]"""
import argparse, importlib.util, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, pulp
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
LAYER = {1: "environment", 2: "environment", 3: "salary", 4: "ownership"}
ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("out"); ap.add_argument("--mode", required=True); ap.add_argument("--weeks", default="1,2,3,4"); ap.add_argument("--n", type=int, default=500)
a = ap.parse_args(); RUN, OUT = Path(a.run), Path(a.out); OUT.mkdir(parents=True, exist_ok=True)
log = open(OUT / f"log-{a.mode}.txt", "a")
def P(s): print(s, flush=True); log.write(s + "\n"); log.flush()
def bonus_for(w, fr):
    from google.cloud import bigquery
    BQ = bigquery.Client()
    al = BQ.query("""WITH a AS (SELECT x.season, x.week, x.team, r.position, x.dk_points FROM `nfl_features.player_week_actuals` x
      JOIN `nfl_features.player_week_role` r ON r.gsis_id = x.gsis_id AND r.season = x.season AND r.week = x.week
      WHERE x.season IN (2025, 2026) AND r.position IN ('QB', 'RB', 'WR', 'TE'))
      SELECT a.season, a.week, s.opponent def, a.position, SUM(a.dk_points) pts FROM a JOIN `nfl_features.schedule_long` s ON s.season = a.season AND s.week = a.week AND s.team = a.team
      WHERE s.game_type = 'REG' GROUP BY 1, 2, 3, 4""").to_dataframe()
    p25 = al[al.season == 2025].groupby(["def", "position"]).pts.mean(); cur = al[(al.season == 2026) & (al.week < w)].groupby(["def", "position"]).pts.agg(["sum", "count"])
    mm = pd.DataFrame({"p25": p25}).join(cur, how="outer").fillna({"sum": 0, "count": 0}); prior = mm.p25.fillna(mm.p25.groupby(level=1).transform("mean"))
    allowed = ((6 * prior + mm["sum"]) / (6 + mm["count"])).to_dict()
    raw = pd.read_parquet(Path(WSS.CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id"); raw["id"] = raw.dk_player_id.astype("Int64").astype(str); raw = raw.set_index("id")
    mr = pd.Series([allowed.get((o, p), np.nan) for o, p in zip(fr.opp.astype(str), fr.pos.astype(str))], index=fr.index)
    sk = fr.pos.isin(["QB", "RB", "WR", "TE"])
    z = mr[sk].groupby(fr.pos[sk]).transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    b_m = pd.Series(0.0, index=fr.index); b_m[sk] = np.clip(z.fillna(0), 0, 2)
    vt = pd.to_numeric(fr.id.map(raw.team_vacated_target_share), errors="coerce").fillna(0); vc = pd.to_numeric(fr.id.map(raw.team_vacated_carry_share), errors="coerce").fillna(0)
    b_v = pd.Series(np.where(fr.pos == "RB", vc, np.where(fr.pos.isin(["WR", "TE"]), vt, 0.0)), index=fr.index).clip(0) * 10; b_v = b_v.clip(0, 3)
    mk = pd.to_numeric(fr.id.map(raw.market_points), errors="coerce") - fr.proj
    b_k = (0.5 * mk.fillna(0)).clip(0, 2).where(sk, 0.0)
    return (b_m + b_v + b_k).clip(0, 3)
for w in [int(x) for x in a.weeks.split(",")]:
    t0 = time.time(); W, fr, f = WSS.load_week(w); winner = float(f.points.max()) / 100; N = len(f); pts = np.sort(f.points.values)
    lines = {"top100": float(pts[-100]) / 100, "top1pct": float(pts[int(0.99 * N)]) / 100, "hit": winner - WSS.WITHIN}
    rec = json.loads((RUN / f"week{w}.json").read_text()); rules = next(e["rules"] for e in rec["layers"] if e["layer"] == LAYER[w])
    win_ix = [i for i in f.sort_values("rank").iloc[0].ix]
    P(f"== W{w} mode {a.mode}: rules {rules}; winner {winner:.1f}; lines within10 {lines['hit']:.1f} top100 {lines['top100']:.1f} top1% {lines['top1pct']:.1f}")
    fr0 = fr.copy(); first = {k: None for k in lines}; best = (-1, None); seen = set(); built = 0
    if a.mode == "bonus":
        b = bonus_for(w, fr0); fr = fr0.assign(proj=fr0.proj + b)
        # the winner-gap diagnostic (unconstrained and under the rules), with and without the bonus
        for lbl, frx in (("projection", fr0), ("projection+bonus", fr)):
            for rl, rr in (("no rules", {}), ("week rules", rules)):
                m, x, ids = WSS.make_model(frx, rr, "proj"); L = WSS.solve(m, x, ids)
                top = float(frx.proj.iloc[L].sum()) if L else float("nan"); wv = float(frx.proj.iloc[[i for i in win_ix if i >= 0]].sum())
                P(f"   gap [{lbl:16s} | {rl:10s}]: best lineup objective {top:.1f}, the winner's lineup {wv:.1f}, gap {top - wv:+.1f}")
        P(f"   bonus on the winner's players: " + ", ".join(f"{fr0.display_name.iloc[i]} +{b.iloc[i]:.1f}" for i in win_ix if i >= 0) + f" | mean bonus over skill players {b[fr0.pos.isin(['QB','RB','WR','TE'])].mean():.2f}")
        m, x, ids = WSS.make_model(fr, rules, "proj")
        for n in range(1, a.n + 1):
            L = WSS.solve(m, x, ids)
            if L is None: P(f"   exhausted at {n}"); break
            m += pulp.lpSum(x[i] for i in L) <= 7; built += 1; act = float(fr0.actual.iloc[L].sum())
            if act > best[0]: best = (act, L)
            for k, line in lines.items():
                if first[k] is None and act >= line: first[k] = n
            if n % 100 == 0: P(f"   n={n} best {best[0]:.1f} first {first} {time.time()-t0:.0f}s")
    else:
        worlds = np.load(Path(WSS.CFG["weeks"][str(w)]["t70_run"]) / "incumbent_player_scores.npy", mmap_mode="r")
        assert worlds.shape[0] == len(fr0), (worlds.shape, len(fr0))
        order = np.argsort(-np.asarray(worlds).sum(axis=0))
        for n, k in enumerate(order[: a.n], start=1):
            frk = fr0.assign(proj=np.asarray(worlds[:, k], dtype=float))
            m, x, ids = WSS.make_model(frk, rules, "proj"); L = WSS.solve(m, x, ids)
            if L is None: continue
            key = tuple(sorted(L))
            if key in seen: continue
            seen.add(key); built += 1; act = float(fr0.actual.iloc[L].sum())
            if act > best[0]: best = (act, L)
            for kk, line in lines.items():
                if first[kk] is None and act >= line: first[kk] = built
            if n % 100 == 0: P(f"   worlds={n} distinct lineups {built} best {best[0]:.1f} first {first} {time.time()-t0:.0f}s")
    desc = [f"{fr0.display_name.iloc[i]} {fr0.pos.iloc[i]} {fr0.team.iloc[i]} {fr0.actual.iloc[i]:.1f}" for i in best[1]] if best[1] else None
    res = {"week": w, "mode": a.mode, "rules": rules, "winner": winner, "lines": lines, "built": built, "first": first, "best": round(best[0], 2), "best_lineup": desc, "secs": round(time.time() - t0)}
    P(f"   RESULT W{w} {a.mode}: built {built}; first top-1% {first['top1pct']}, top-100 {first['top100']}, within-10 {first['hit']}; best {best[0]:.1f}: {desc}")
    (OUT / f"{a.mode}-w{w}.json").write_text(json.dumps(res, indent=1))
