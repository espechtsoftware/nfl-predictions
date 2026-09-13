"""Historical late-swap experiment (descriptive, hypothesis-generating; 2026-09-13 evening).
For every dev slate, take the PREREG-096 DEMAX K80 book (bank 960) and split each lineup into early (13:00 ET) and late
(16:00+ ET) players by the nflverse schedule.  With the EARLY players' realized points known (E), re-choose the late slots
(same position, salary within the lineup's room) from late-game players to maximise P(E + late >= 220) under the
pre-lock simulator (selection-bank draws, 2000 worlds), then score the swapped lineup with the late players' REALIZED
points.  Compares the book's best-of-K under: static (as entered), late-swap-220, late-swap-chalk (max projection),
late-swap-ceiling (max q95).  Also: anatomy of the realized perfect lineups (players >= 30, stack size, salary)."""
import json, sys, time, itertools, pathlib, numpy as np, pandas as pd, pulp
sys.path.insert(0, "/home/erich/projects/.nfl2-worktrees/prereg096-fast-20260913/scripts")
from prereg096_report import load
from nfl2.pipeline import simulate_slate, slate_frame, slate_seed
from google.cloud import bigquery
ENV = {"NFL2_ENSEMBLE": "1", "NFL2_CENTER": "mean"}; OUT = pathlib.Path("/home/erich/week1-sunday/audit"); SKILL = ("QB", "RB", "WR", "TE")
sched = bigquery.Client(project="nfl-predictions-503414").query("SELECT game_id, gametime FROM `nfl-predictions-503414.nfl_raw.schedules` WHERE season BETWEEN 2021 AND 2024").result().to_dataframe()
late_game = {g: (str(t) >= "15:00") for g, t in zip(sched.game_id, sched.gametime)}
metas, cands, names = load("116b960r1-20260913T140230Z")

def perfect_anatomy(fr):
    fr = fr[fr.pos.isin(SKILL + ("DST",))].reset_index(drop=True); pts = pd.to_numeric(fr.actual, errors="coerce").fillna(0.0).to_numpy(); sal = pd.to_numeric(fr.salary, errors="coerce").fillna(99999).to_numpy(); pos = fr.pos.astype(str).to_numpy()
    prob = pulp.LpProblem("p", pulp.LpMaximize); x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(fr))]; prob += pulp.lpSum(x[i] * pts[i] for i in range(len(fr))); prob += pulp.lpSum(x) == 9; prob += pulp.lpSum(x[i] * sal[i] for i in range(len(fr))) <= 50000
    for p, lo, hi in (("QB", 1, 1), ("RB", 2, 3), ("WR", 3, 4), ("TE", 1, 2), ("DST", 1, 1)): prob += pulp.lpSum(x[i] for i in range(len(fr)) if pos[i] == p) >= lo; prob += pulp.lpSum(x[i] for i in range(len(fr)) if pos[i] == p) <= hi
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=20)); sel = [i for i in range(len(fr)) if x[i].value() > 0.5]; q = fr.iloc[sel]
    qb_team = q[q.pos == "QB"].team.iloc[0]; stack = int(((q.team == qb_team) & q.pos.isin(("WR", "TE", "RB"))).sum())
    return {"score": float(pts[sel].sum()), "pts_sorted": sorted([round(float(v), 1) for v in pts[sel]], reverse=True), "n_ge30": int((pts[sel] >= 30).sum()), "n_ge25": int((pts[sel] >= 25).sum()), "n_ge20": int((pts[sel] >= 20).sum()), "stack": stack, "salary": int(sal[sel].sum()), "games": int(q.game_id.nunique()), "max_game": int(q.game_id.value_counts().max()), "late_players": int(sum(late_game.get(g, False) for g in q.game_id))}

results = {"anatomy": {}, "late_swap": {}}; t0 = time.time()
for key, table in cands.items():
    s, w = map(int, key.split("-w")); fr = slate_frame(s, w); results["anatomy"][key] = perfect_anatomy(fr)
    fri = fr.set_index(fr.id.astype(str)); pos = fri.pos.astype(str); team = fri.team.astype(str); sal = pd.to_numeric(fri.salary, errors="coerce").fillna(99999); act = pd.to_numeric(fri.actual, errors="coerce").fillna(0.0)
    is_late = fri.game_id.astype(str).map(lambda g: late_game.get(g, False)); proj = pd.to_numeric(fri.get("mean_projection"), errors="coerce").fillna(0.0)
    draws = simulate_slate(fr, n_sims=2000, seed=slate_seed(1010, s, w), law_env=ENV); D = pd.DataFrame(draws, index=fr.id.astype(str))
    q95 = D.quantile(0.95, axis=1); q90 = D.quantile(0.90, axis=1)
    t = pd.DataFrame(table); book = t[t.demax_rank.notna()].sort_values("demax_rank"); rows = []
    for rank, players in zip(book.demax_rank, book.players):
        ids = [p for p in players.split(",") if p in fri.index]; early = [p for p in ids if not is_late[p]]; late = [p for p in ids if is_late[p]]
        E = float(act[early].sum()); static_total = float(act[ids].sum()); res = {"rank": int(rank), "E": E, "n_late": len(late), "static": static_total}
        if not late: rows.append({**res, "swap220": static_total, "chalk": static_total, "ceiling": static_total}); continue
        room = 50000 - float(sal[ids].sum()); need = 220.0 - E
        cand_lists = []
        for p in late:   # same-position late-game replacements (incl. keeping p), top 10 by q90 plus the incumbent
            pool = fri[(is_late) & (pos == pos[p]) & (~fri.index.isin([x for x in ids if x != p]))]
            top = list(q90[pool.index].sort_values(ascending=False).index[:10]); cand_lists.append(list(dict.fromkeys([p] + top)))
        # coordinate ascent over the late slots (2 passes): per slot, try every same-position late candidate that fits the
        # remaining salary room, holding the other slots fixed; three objectives evaluated separately from the same start
        Dm = D.to_numpy(dtype=np.float32); ix = {pid: i for i, pid in enumerate(D.index)}; sal_v = sal.reindex(D.index).to_numpy(float)
        proj_v = proj.reindex(D.index).to_numpy(float); q95_v = q95.reindex(D.index).to_numpy(float); act_v = act.reindex(D.index).to_numpy(float)
        slot_cands = [[ix[c] for c in cl] for cl in cand_lists]; start = [ix[p] for p in late]; base_sal = float(sal[late].sum())
        def objective(kind, chosen):
            v = Dm[chosen].sum(axis=0)
            return float((v >= need).mean()) if kind == "swap220" else (float(proj_v[chosen].sum()) if kind == "chalk" else float(q95_v[chosen].sum()))
        for kind in ("swap220", "chalk", "ceiling"):
            chosen = list(start)
            for _ in range(2):
                for j in range(len(chosen)):
                    best_c, best_v = chosen[j], objective(kind, chosen)
                    for c in slot_cands[j]:
                        if c in chosen and c != chosen[j]: continue
                        trial = list(chosen); trial[j] = c
                        if sal_v[trial].sum() - base_sal > room + 1e-6: continue
                        v = objective(kind, trial)
                        if v > best_v + 1e-12: best_c, best_v = c, v
                    chosen[j] = best_c
            res[kind] = E + float(act_v[chosen].sum())
        rows.append(res)
    b = pd.DataFrame(rows); results["late_swap"][key] = {K: {c: float(b.head(K)[c].max()) for c in ("static", "swap220", "chalk", "ceiling")} for K in (30, 80)}
    results["late_swap"][key]["alive_E_ge_120"] = int((b.E >= 120).sum()); results["late_swap"][key]["mean_n_late"] = float(b.n_late.mean())
    print(f"{key}: K30 static {b.head(30).static.max():.1f} swap220 {b.head(30).swap220.max():.1f} chalk {b.head(30).chalk.max():.1f} ceiling {b.head(30).ceiling.max():.1f} | K80 static {b.static.max():.1f} swap220 {b.swap220.max():.1f} | perfect {results['anatomy'][key]['score']:.1f} n30 {results['anatomy'][key]['n_ge30']} stack {results['anatomy'][key]['stack']} ({time.time()-t0:.0f}s)", flush=True)
    (OUT / "late_swap_history.json").write_text(json.dumps(results, indent=1))
ls = results["late_swap"]; an = pd.DataFrame(results["anatomy"]).T
lines = ["# Late swap, historically (descriptive) and the anatomy of perfect lineups", ""]
for K in (30, 80):
    for c in ("static", "swap220", "chalk", "ceiling"):
        vals = np.array([v[str(K)][c] if str(K) in v else v[K][c] for v in ls.values()]); lines.append(f"K={K} {c:8s}: mean best-of-book {vals.mean():.2f} | slates >=200: {(vals>=200).sum()} | >=220: {(vals>=220).sum()} | >=230: {(vals>=230).sum()}")
lines += ["", f"perfect lineups (n={len(an)}): mean {an.score.mean():.1f}; players >=30 pts: mean {an.n_ge30.mean():.2f}; >=25: {an.n_ge25.mean():.2f}; >=20: {an.n_ge20.mean():.2f}; QB stack size mean {an['stack'].mean():.2f}; salary used mean {an.salary.mean():.0f}; games {an.games.mean():.2f}; max per game {an.max_game.mean():.2f}; late-game players {an.late_players.mean():.2f} of 9"]
(OUT / "late_swap_history.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines)); print("DONE")
