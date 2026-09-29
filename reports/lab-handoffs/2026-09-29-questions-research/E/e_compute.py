"""THEME E compute: persisted pre-lock score banks (players x worlds) vs realized DK points, 2026 W1-3.
Read-only; single-threaded; no simulation (only reads persisted banks + one column permutation for an independence
counterfactual). Realized points: nfl_raw.contest_ownership fpts (DK's own scoring, Millionaire contest per week);
players absent from the ownership file score 0 (they were not in the contest player pool or did not play).
Realized game points: nfl_raw.schedules."""
import os, sys, json
os.environ["OMP_NUM_THREADS"] = "1"; os.environ["OPENBLAS_NUM_THREADS"] = "1"; os.environ["MKL_NUM_THREADS"] = "1"
import numpy as np, pandas as pd
sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
from nfl_dfs.bq import query_df

RUNS = {
 "W1 D800 (09-13 14:10Z, K80, the entered-size build; sel dual_emax)": ("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01/20260913T141023019886Z-e7255e9", 1, "193028206"),
 "W2 D12800 ENTERED (09-19 15:30Z Saturday build, K97; week2-release-2dc116c)": ("/home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/results/live/2026-w02/20260919T153008787414Z-2dc116c", 2, "195648007"),
 "W1 D800 (09-13 16:04Z, ~1h pre-lock; sel dual_emax)": ("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w01/20260913T160405364118Z-e7255e9", 1, "193028206"),
 "W2 D12800 (09-16 16:53Z Saturday-style build; entered pool)": ("/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9/results/live/2026-w02/20260916T165251953256Z-e7255e9", 2, "195648007"),
 "W3 D12800 Saturday (09-26 15:34Z)": ("/home/erich/projects/.nfl2-worktrees/week3-live-center/results/live/2026-w03/20260926T153408285093Z-65305f5", 3, "195905122"),
 "W3 D800 T-70 (09-27 15:50Z)": ("/home/erich/projects/.nfl2-worktrees/week3-live-center/results/live/2026-w03/20260927T155027472554Z-65305f5", 3, "195905122"),
}
LINES = (150, 170, 194, 200, 210)
BANKS = ("incumbent_player_scores.npy", "corrected_hsim_player_scores.npy")
rng = np.random.default_rng(20260929)
out = {}

sched = query_df("""SELECT game_id, week, home_score, away_score, total_line FROM `nfl-predictions-503414.nfl_raw.schedules`
                    WHERE season=2026 AND week<=3 AND game_type='REG'""")
sched["pts"] = sched.home_score + sched.away_score
sched = sched.set_index("game_id")

def lineup_stats(idx_lists, bank, realized, chunk=1500):
    """Stream candidate totals (cands x worlds) through the bank without holding the matrix."""
    n = len(idx_lists); W = bank.shape[1]
    sim_mean = np.empty(n); sim_sd = np.empty(n); pit = np.empty(n); p99 = np.empty(n); p95 = np.empty(n)
    above = {L: np.zeros(n) for L in LINES}
    world_sum = np.zeros(W); world_max = np.full(W, -np.inf)
    for s in range(0, n, chunk):
        ids = idx_lists[s:s+chunk]
        T = np.stack([bank[i].sum(axis=0) for i in ids])            # chunk x worlds
        sim_mean[s:s+chunk] = T.mean(1); sim_sd[s:s+chunk] = T.std(1)
        r = realized[s:s+chunk][:, None]
        pit[s:s+chunk] = (T <= r).mean(1)
        q = np.quantile(T, [0.95, 0.99], axis=1); p95[s:s+chunk] = q[0]; p99[s:s+chunk] = q[1]
        for L in LINES: above[L][s:s+chunk] = (T >= L).mean(1)
        world_sum += T.sum(0); world_max = np.maximum(world_max, T.max(0))
    return dict(sim_mean=sim_mean, sim_sd=sim_sd, pit=pit, p95=p95, p99=p99, above=above,
                world_mean=world_sum / n, world_max=world_max)

ONLY = sys.argv[1:]
for label, (d, week, contest) in RUNS.items():
    if ONLY and not any(o in label for o in ONLY): continue
    fr = pd.read_parquet(d + "/frame.parquet").reset_index(drop=True)
    c = pd.read_parquet(d + "/candidates.parquet").reset_index(drop=True)
    fr["id"] = fr.id.astype(str)
    own = query_df(f"""SELECT display_name, MAX(fpts) f, MAX(pct_drafted) own FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                       WHERE season=2026 AND week={week} AND contest_id='{contest}' GROUP BY 1""")
    lut = dict(zip(own.display_name.astype(str), own.f.astype(float)))
    fr["realized"] = fr.display_name.astype(str).map(lut)
    matched = fr.realized.notna()
    fr["realized"] = fr.realized.fillna(0.0)
    row = {s: k for k, s in enumerate(fr.id)}
    idx_lists = [[row[p] for p in ps.split(",")] for ps in c.players.astype(str)]
    proj = fr.mean_projection.to_numpy(float); real = fr.realized.to_numpy(float)
    realized_lineup = np.array([real[i].sum() for i in idx_lists]); proj_lineup = np.array([proj[i].sum() for i in idx_lists])
    res = {"run_dir": d, "n_players": int(len(fr)), "n_players_matched_to_dk_file": int(matched.sum()),
           "n_cands": int(len(c)), "tags": c.tag.value_counts().to_dict()}
    # --- player level (E2): served projection vs realized, exposure-weighted and by position
    expo = np.zeros(len(fr))
    for i in idx_lists: expo[i] += 1
    res["player_level"] = {
        "all_frame_players": {"proj_sum": round(float(proj.sum()), 1), "real_sum": round(float(real.sum()), 1), "ratio": round(float(real.sum() / proj.sum()), 3)},
        "exposure_weighted_pool": {"proj": round(float((expo * proj).sum() / expo.sum() * 9), 2), "real": round(float((expo * real).sum() / expo.sum() * 9), 2)},
        "by_pos_exposure_weighted": {p: {"proj": round(float((expo * proj)[fr.pos == p].sum() / max(1e-9, expo[fr.pos == p].sum())), 2),
                                         "real": round(float((expo * real)[fr.pos == p].sum() / max(1e-9, expo[fr.pos == p].sum())), 2),
                                         "slots": int(expo[fr.pos == p].sum())} for p in ("QB", "RB", "WR", "TE", "DST")},
        "top50_by_projection": {"proj": round(float(np.sort(proj)[-50:].sum()), 1), "real": round(float(real[np.argsort(proj)[-50:]].sum()), 1)},
    }
    # --- market total for the slate's games vs realized points (E2)
    g = fr.drop_duplicates("game_id")[["game_id", "game_total"]].set_index("game_id")
    g = g.join(sched[["pts", "total_line"]], how="left")
    res["market_level"] = {"games": int(len(g)), "sum_market_total": round(float(g.game_total.sum()), 1),
                           "sum_realized_points": round(float(g.pts.sum()), 1), "ratio": round(float(g.pts.sum() / g.game_total.sum()), 3),
                           "per_game_corr_market_vs_pts": round(float(np.corrcoef(g.game_total, g.pts)[0, 1]), 3)}
    # --- lineup level per bank (E2/E3)
    for b in BANKS:
        bank = np.load(d + "/" + b, mmap_mode="r")
        assert bank.shape[0] == len(fr)
        st = lineup_stats(idx_lists, np.asarray(bank), realized_lineup)
        book = c.book_rank.notna().to_numpy()
        wm = st["world_mean"]; rp = realized_lineup.mean()
        def block(mask):
            m = mask
            return {"n": int(m.sum()), "sim_mean": round(float(st["sim_mean"][m].mean()), 2), "proj_sum_mean": round(float(proj_lineup[m].mean()), 2),
                    "realized_mean": round(float(realized_lineup[m].mean()), 2), "realized_sd": round(float(realized_lineup[m].std()), 2),
                    "sim_sd_within_lineup": round(float(st["sim_sd"][m].mean()), 2), "mean_pit": round(float(st["pit"][m].mean()), 3),
                    "share_real_above_p99": round(float((realized_lineup[m] > st["p99"][m]).mean()), 4),
                    "share_real_above_p95": round(float((realized_lineup[m] > st["p95"][m]).mean()), 4),
                    "sim_vs_real_P_ge": {str(L): [round(float(st["above"][L][m].mean()), 5), round(float((realized_lineup[m] >= L).mean()), 5)] for L in LINES},
                    "realized_max": round(float(realized_lineup[m].max()), 1),
                    "corr_sim_mean_realized": round(float(np.corrcoef(st["sim_mean"][m], realized_lineup[m])[0, 1]), 3) if m.sum() > 2 else None}
        res[b] = {"pool": block(np.ones(len(c), bool)), "book(dual_emax, as built)": block(book),
                  "level": {"realized_pool_mean_world_rank": round(float((wm <= rp).mean()), 4), "sim_world_mean_sd": round(float(wm.std()), 2),
                            "world_pool_max_mean": round(float(st["world_max"].mean()), 2), "world_pool_max_p99": round(float(np.quantile(st["world_max"], .99)), 2),
                            "realized_pool_max": round(float(realized_lineup.max()), 1),
                            "share_worlds_pool_max_ge_200": round(float((st["world_max"] >= 200).mean()), 4)}}
        # --- dependence card in the bank (E4): cross-team skill sums per game; WR1-WR2, QB-WR1 same team
        skill = fr.pos.isin(["QB", "RB", "WR", "TE"]).to_numpy()
        xs = []; wr = []; qbwr = []; teamsum = {}
        for gid, sub in fr[skill].groupby("game_id"):
            teams = sub.team.unique()
            if len(teams) != 2: continue
            a = np.asarray(bank[sub.index[sub.team == teams[0]]]).sum(0); bb = np.asarray(bank[sub.index[sub.team == teams[1]]]).sum(0)
            xs.append(np.corrcoef(a, bb)[0, 1]); teamsum[teams[0]] = a; teamsum[teams[1]] = bb
        for t, sub in fr[skill].groupby("team"):
            w = sub[sub.pos == "WR"].sort_values("salary", ascending=False)
            q = sub[sub.pos == "QB"].sort_values("mean_projection", ascending=False)
            if len(w) >= 2: wr.append(np.corrcoef(np.asarray(bank[w.index[0]]), np.asarray(bank[w.index[1]]))[0, 1])
            if len(w) >= 1 and len(q) >= 1: qbwr.append(np.corrcoef(np.asarray(bank[q.index[0]]), np.asarray(bank[w.index[0]]))[0, 1])
        # independence counterfactual: permute each player's worlds independently (destroys all dependence, keeps marginals)
        sh = np.asarray(bank).copy()
        for i in range(sh.shape[0]): sh[i] = sh[i][rng.permutation(sh.shape[1])]
        st0 = lineup_stats(idx_lists, sh, realized_lineup)
        res[b]["dependence"] = {"cross_team_skill_sum_corr_mean": round(float(np.mean(xs)), 3), "cross_team_n_games": len(xs),
                                "WR1_WR2_same_team_corr_mean": round(float(np.mean(wr)), 3), "QB_WR1_corr_mean": round(float(np.mean(qbwr)), 3),
                                "independence_shuffle": {"pool_sim_mean": [round(float(st["sim_mean"].mean()), 3), round(float(st0["sim_mean"].mean()), 3)],
                                                         "pool_within_lineup_sd": [round(float(st["sim_sd"].mean()), 2), round(float(st0["sim_sd"].mean()), 2)],
                                                         "P_ge_200_pool": [round(float(st["above"][200].mean()), 5), round(float(st0["above"][200].mean()), 5)],
                                                         "P_ge_210_pool": [round(float(st["above"][210].mean()), 5), round(float(st0["above"][210].mean()), 5)],
                                                         "P_ge_150_pool": [round(float(st["above"][150].mean()), 4), round(float(st0["above"][150].mean()), 4)],
                                                         "world_pool_max_mean": [round(float(st["world_max"].mean()), 2), round(float(st0["world_max"].mean()), 2)],
                                                         "sim_world_mean_sd(level)": [round(float(st["world_mean"].std()), 2), round(float(st0["world_mean"].std()), 2)],
                                                         "realized_pool_mean_world_rank": [round(float((st["world_mean"] <= rp).mean()), 4), round(float((st0["world_mean"] <= rp).mean()), 4)]}}
        del sh
    out[label] = res
    print(label, json.dumps(res, indent=1)[:200], flush=True)
prev = {}
try: prev = json.load(open(os.path.dirname(__file__) + "/e_results.json"))
except Exception: pass
prev.update(out); json.dump(prev, open(os.path.dirname(__file__) + "/e_results.json", "w"), indent=1)
print("DONE")
