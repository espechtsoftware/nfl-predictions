"""Per player: whom the winners had that our best rule-built lineup did not, and why the build did not take him (operator
10-07: "which players were you unable to get? have you analyzed each of those players and seen why we're not getting them?").
For each week: the winner's nine vs our best built lineup's nine; for each winner's player: in the T-70 frame? eligible?
the projection we played and his rank among his position by projection, salary, pre-lock projected ownership (W3/W4), realized
ownership, actual points, residual; and at his slot, the player the build took instead. Usage: missing_players.py OUT_DIR"""
import importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
MS = WSS.MS; RUN = Path("/home/erich/rehearsals/winners-strategy-20261006"); out = Path(sys.argv[1]); out.mkdir(exist_ok=True, parents=True)
def best_lineup_names(w):
    rec = json.loads((RUN / f"week{w}.json").read_text()); layers = [e for e in rec["layers"] if e.get("enum")]
    b = max(layers, key=lambda e: e["enum"]["best_actual"]); return b["layer"], [s.rsplit(" $", 1)[0].rsplit(" ", 2)[0] for s in b["enum"]["best_lineup"]], b["enum"]["best_actual"]
lines = []
def P(s=""): print(s, flush=True); lines.append(s)
for w in (1, 2, 3, 4):
    W, fr, f = WSS.load_week(w); N = len(f); fr = fr.copy()
    fr["proj_rank_pos"] = fr.groupby("pos").proj.rank(ascending=False, method="min")
    fr["val"] = fr.proj / fr.salary * 1000; fr["val_rank_pos"] = fr.groupby("pos").val.rank(ascending=False, method="min")
    raw = pd.read_parquet(Path(WSS.CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id"); raw["id"] = raw.dk_player_id.astype("Int64").astype(str); raw = raw.set_index("id")
    for c in ("injury_status", "depth_rank", "snap_share_l4", "target_share_l4", "carries_l4", "implied_team_total", "practice_status"):
        fr[c] = fr.id.map(raw[c]) if c in raw.columns else np.nan
    win = f.sort_values("rank").iloc[0]; wnames = win.names; wix = win.ix
    layer, bnames, bact = best_lineup_names(w); bidx = [fr.index[fr.display_name == n][0] for n in bnames if (fr.display_name == n).any()]
    bset = set(fr.fname.iloc[bidx]); wset = set(wnames)
    wproj = sum(fr.proj.iloc[i] for i in wix if i >= 0); bproj = float(fr.proj.iloc[bidx].sum())
    P(f"\n=== WEEK {w}: winner {win.points/100:.2f}; projected sum of the winner's lineup (the projection we played, {fr.proj_source.iloc[0]}): {wproj:.1f} | our best built ({layer}): {bact:.1f} actual, projected {bproj:.1f}; shared players {len(wset & bset)} of 9 ===")
    P(f"{'winner player':24s} {'pos':4s} {'team':4s} {'sal':>5s} {'proj':>5s} {'rk@pos':>6s} {'val_rk':>6s} {'pown':>5s} {'rown':>5s} {'actual':>6s} {'resid':>6s}  {'in ours':7s}  {'status / depth / snap_l4 / tgt_sh_l4 / carries_l4 / team_tot'}")
    for n, i in sorted(zip(wnames, wix), key=lambda t: (fr.pos.iloc[t[1]] if t[1] >= 0 else "zz", -(fr.actual.iloc[t[1]] if t[1] >= 0 else 0))):
        if i < 0:
            P(f"{n:24s} ---- NOT IN THE T-70 FRAME (the build could not pick him) ----"); continue
        r = fr.iloc[i]; pown = f"{r.pown:.1f}" if pd.notna(r.pown) else "  -"
        facts = f"{r.status_s}/{r.injury_status} d{r.depth_rank} snap {r.snap_share_l4:.2f} tgt {r.target_share_l4:.2f} car {r.carries_l4:.0f} tot {r.implied_team_total:.1f}" if pd.notna(r.snap_share_l4) else f"{r.status_s}"
        P(f"{r.display_name:24s} {r.pos:4s} {r.team:4s} {int(r.salary):5d} {r.proj:5.1f} {int(r.proj_rank_pos):6d} {int(r.val_rank_pos):6d} {pown:>5s} {r.rown:5.1f} {r.actual:6.1f} {r.actual - r.proj:+6.1f}  {'yes' if r.fname in bset else 'NO':7s}  {facts}")
    P(f"--- the players our best built lineup took instead (not in the winner's):")
    for i in bidx:
        r = fr.iloc[i]
        if r.fname in wset: continue
        pown = f"{r.pown:.1f}" if pd.notna(r.pown) else "  -"
        P(f"{r.display_name:24s} {r.pos:4s} {r.team:4s} {int(r.salary):5d} {r.proj:5.1f} {int(r.proj_rank_pos):6d} {int(r.val_rank_pos):6d} {pown:>5s} {r.rown:5.1f} {r.actual:6.1f} {r.actual - r.proj:+6.1f}")
    miss = [i for n, i in zip(wnames, wix) if i >= 0 and fr.fname.iloc[i] not in bset]
    gap_proj = sum(fr.proj.iloc[bidx]) - sum(fr.proj.iloc[i] for i in wix if i >= 0)
    P(f"--- summary W{w}: the winner's lineup projects {gap_proj:+.1f} points BELOW our best built under the same projection; the {len(miss)} players we missed scored {sum(fr.actual.iloc[i] for i in miss):.1f} actual on {sum(fr.proj.iloc[i] for i in miss):.1f} projected (+{sum(fr.actual.iloc[i] - fr.proj.iloc[i] for i in miss):.1f} over projection)")
(out / "missing_players.txt").write_text("\n".join(lines) + "\n")
