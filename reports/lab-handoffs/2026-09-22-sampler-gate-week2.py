"""PREREG-098 sampler gate, re-run on the real 2026 Week-2 Millionaire field (external review §6.5; delegated by
production e67103d7). Report only; nothing adopts. Frozen v4 settings (stack 0.70, salary floor band 48,500-50,000,
6 IPF rounds, 200,000 lineups, seed 98); criteria exactly as PREREG-098 §Gate(a): per-world top-100 and top-1,000
cutoff correlation > 0.95 across 10,000 worlds; top-1,000 mean |diff| < 3; realized top-1,000 / cash cutoffs within
5 points of the real field's; ownership error sum < 0.5. Worlds: the Week-2 Saturday run's incumbent bank (the
selector's), frame rows aligned. Cutoffs sit at FRACS of an 832,342-entry reference field, so field size cancels."""
import sys, time, numpy as np, pandas as pd
sys.path.insert(0, sys.argv[1])            # nfl2 experiments dir at 7e8126b (sampler + world_cutoffs)
from prereg098_field_sampler import sample_field, world_cutoffs
from nfl_dfs.bq import query_df
D = "/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/results/live/2026-w02/20260919T151024628419Z-2dc116c"
REF = 832_342; FRACS = {"top100": 100 / REF, "top1000": 1000 / REF, "cash": 173_275 / REF}
fr = pd.read_parquet(f"{D}/frame.parquet").reset_index(drop=True); M = np.load(f"{D}/incumbent_player_scores.npy").astype(np.float32)
assert M.shape[0] == len(fr)
T = "`nfl-predictions-503414.nfl_raw.contest_entries`"; MID = "195648007"
# ownership is one row per (player, roster slot): SUM over slots (a WR has a WR row and a FLEX row)
own = query_df(f"""SELECT display_name, SUM(pct_drafted) o, MAX(fpts) f FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                   WHERE season=2026 AND week=2 AND contest_id='{MID}' GROUP BY 1""")
name2row = {n: i for i, n in enumerate(fr.display_name.astype(str))}
target = {str(fr.id[name2row[n]]): float(o) / 100.0 for n, o in zip(own.display_name, own.o) if n in name2row}
print(f"ownership mass: real {own.o.sum()/100:.2f}, matched into the frame {sum(target.values()):.2f} "
      f"({sum(1 for n in own.display_name if n not in name2row)} owned players not in the frame)")
real = query_df(f"SELECT points, players_key FROM {T} WHERE season=2026 AND week=2 AND contest_id='{MID}'")
rows = [[name2row.get(p) for p in k.split("|")] for k in real.players_key]
ok = np.array([len(r) == 9 and all(x is not None for x in r) for r in rows])
RF = np.array([r for r, g in zip(rows, ok) if g], dtype=np.int32)
print(f"real field {len(real)} lineups; scorable in the frame's worlds {len(RF)} ({100*ok.mean():.1f}%)")
import prereg098_field_sampler as PS; _orig = PS.np.random.default_rng
t0 = time.time(); SF, rec = sample_field(fr, target, 200_000, seed=98); print(f"sampled 200,000 in {time.time()-t0:.0f}s; ownership error {rec['final_abs_ownership_error_sum']}; stack rate {rec['stack_rate']:.2f}; mean salary {rec['mean_salary']:.0f}")
def ranks(n): return np.array([max(1, int(round(FRACS[k] * n))) for k in ("top100", "top1000", "cash")])
t0 = time.time(); cr = world_cutoffs(RF, M, ranks(len(RF))); cs = world_cutoffs(SF, M, ranks(len(SF))); print(f"cutoffs in {time.time()-t0:.0f}s")
res = {}
for j, k in enumerate(("top100", "top1000", "cash")):
    res[k] = (float(np.corrcoef(cr[:, j], cs[:, j])[0, 1]), float(np.abs(cr[:, j] - cs[:, j]).mean()), float((cs[:, j] - cr[:, j]).mean()))
    print(f"  {k:8s} corr {res[k][0]:.3f}  mean |diff| {res[k][1]:.2f}  mean signed (sampled - real) {res[k][2]:+.2f}")
pts = dict(zip(own.display_name.astype(str), own.f.astype(float)))
fpts = np.array([pts.get(n, 0.0) for n in fr.display_name.astype(str)])
real_sorted = np.sort(real.points.to_numpy(float))[::-1]; samp_sorted = np.sort(fpts[SF].sum(axis=1))[::-1]
rr, rs = ranks(len(real)), ranks(len(SF))
real_cut = {k: float(real_sorted[r - 1]) for k, r in zip(("top100", "top1000", "cash"), rr)}
samp_cut = {k: float(samp_sorted[r - 1]) for k, r in zip(("top100", "top1000", "cash"), rs)}
print(f"  realized cutoffs, sampled vs real: top-1,000 {samp_cut['top1000']:.1f} vs {real_cut['top1000']:.1f}; cash {samp_cut['cash']:.1f} vs {real_cut['cash']:.1f}; top-100 {samp_cut['top100']:.1f} vs {real_cut['top100']:.1f}")
crit = {"corr top-100 > 0.95": res["top100"][0] > 0.95, "corr top-1,000 > 0.95": res["top1000"][0] > 0.95,
        "top-1,000 mean |diff| < 3": res["top1000"][1] < 3,
        "realized top-1,000 within 5": abs(samp_cut["top1000"] - real_cut["top1000"]) <= 5,
        "realized cash within 5": abs(samp_cut["cash"] - real_cut["cash"]) <= 5,
        "ownership error < 0.5": rec["final_abs_ownership_error_sum"] < 0.5}
for k, v in crit.items(): print(f"  {'PASS' if v else 'FAIL'}  {k}")
print("GATE (Week 2):", "PASS" if all(crit.values()) else "FAIL")
