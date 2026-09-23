"""Mechanics smoke (outcome-blind in the sense that matters: no lineup is scored). Stand-in sets from W2 real ownership."""
import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from nfl2.pipeline import generate_candidates
from nfl2 import chalk_sleeve as CS
from nfl_dfs.bq import query_df
D = "/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/results/live/2026-w02/20260919T151024628419Z-2dc116c"
fr = pd.read_parquet(f"{D}/frame.parquet").reset_index(drop=True); draws = np.load(f"{D}/incumbent_player_scores.npy").astype(np.float64)
own = query_df("""SELECT display_name, SUM(pct_drafted) o FROM (SELECT * FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
   WHERE season=2026 AND week=2 AND contest_id='195648007' QUALIFY ROW_NUMBER() OVER (PARTITION BY contest_id, display_name, roster_position ORDER BY imported_at DESC)=1) GROUP BY 1""")
o = dict(zip(own.display_name, own.o))
sk = fr[fr.pos.isin(["QB", "RB", "WR", "TE"])].copy(); sk["pred_own"] = sk.display_name.map(o).fillna(0.0)
top = set(sk.nlargest(5, "pred_own").gsis_id)
sk["set"] = np.where(sk.gsis_id.isin(top), "CHALK", np.where(sk.pred_own < 5, "LOW", "MID"))
f = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/61456d60-2e09-4b53-abdc-8381ee667509/scratchpad/w2_sets_standin.csv"
sk[["gsis_id", "set", "pred_own"]].to_csv(f, index=False)
NB = 120
spec, meta = CS.sleeve_spec(fr, f, n_boom=NB, share=0.25, low_max=1)
print("sleeve receipt:", meta["receipt"])
l0, l1 = [], []
c0 = generate_candidates(fr, draws, n_lev=10, n_boom=NB, ledger=l0)
c1 = generate_candidates(fr, draws, n_lev=10, n_boom=NB, ledger=l1, boom_sleeve=spec)
b0 = [r for r in l0 if r["family"] == "boom"]; b1 = [r for r in l1 if r["family"] in ("boom", CS.TAG)]
pos = set(spec["positions"])
same = sum(1 for i, (a, b) in enumerate(zip(b0, b1)) if i not in pos and a["lineup"] == b["lineup"])
print(f"non-sleeve boom visits identical to the no-sleeve run: {same}/{NB - len(pos)}; lev identical: {[r['lineup'] for r in l0[:10]] == [r['lineup'] for r in l1[:10]]}")
print("sleeve visits tagged:", sum(1 for i, r in enumerate(b1) if r["family"] == CS.TAG), "of", len(pos), "| statuses", pd.Series([r["status"] for r in b1 if r["family"] == CS.TAG]).value_counts().to_dict())
sl = [lu for lu in c1 if lu.tag == CS.TAG]
viol = [lu for lu in sl if sum(str(p["id"]) in meta["low_ids"] for p in lu.players) > 1 or not any(str(p["id"]) in meta["chalk_ids"] for p in lu.players) or sum(p["salary"] for p in lu.players) < 49_500]
print(f"sleeve lineups {len(sl)}, constraint violations {len(viol)}")
print("pool shape (sleeve run):", CS.shape_receipt(c1, meta["low_ids"], meta["chalk_ids"]))
print("pool shape (control):   ", CS.shape_receipt(c0, meta["low_ids"], meta["chalk_ids"]))
