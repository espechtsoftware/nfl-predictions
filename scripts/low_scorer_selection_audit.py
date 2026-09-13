"""Low-scoring selected players: what did the model believe at lock, and why were they in the book?
Descriptive, hypothesis-generation only (opened PREREG-094 D800_DEMAX control books, 72 slates x 3 banks).
For every player in every selected K80 lineup: realized DK points, pre-lock projection/tail/salary/usage/depth/
practice/injury fields from the slate frame, the lineup's family (lev/boom) and the lineup's realized outcome.
Low scorer = realized < 40% of projection AND < 8 points (or 0 points / inactive)."""
import importlib.util, numpy as np, pandas as pd
from nfl2.pipeline import slate_frame
spec = importlib.util.spec_from_file_location("r", "/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/scripts/prereg094_report.py")
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
books, meta = r._load(["114b940r1-20260913T042316Z", "114b941r1-20260913T042615Z", "114b942r1-20260913T053219Z"])
d = pd.DataFrame(books["D800_DEMAX"]); d["rank"] = pd.to_numeric(d["rank"]); d["actual"] = pd.to_numeric(d["actual"])
FEATS = ["mean_projection", "proj_p90", "proj_p10", "proj_std", "salary", "pos", "own_est", "depth_rank", "snap_share_l4", "target_share_l4", "carry_share_l4",
         "dk_points_l4", "dk_points_std", "practice_level", "injury_status", "games_played_prior", "is_cold_start", "was_active", "implied_team_total", "spread", "proj_tourney", "market_points", "name", "team"]
rows = []
for (s, w), g in d.groupby(["season", "week"]):
    fr = slate_frame(int(s), int(w)).set_index(fr_id := "id") if False else slate_frame(int(s), int(w))
    fr = fr.set_index(fr.id.astype(str)); pool_ids = set(fr.index)
    for row in g.itertuples():
        pl = row.players.split(",")
        for p in pl:
            if p not in pool_ids: continue
            f = fr.loc[p]; rec = {"season": int(s), "week": int(w), "bank": int(row.bank), "rank": int(row.rank), "lineup_actual": float(row.actual), "tag": row.tag, "pid": p}
            for c in FEATS: rec[c] = f.get(c, np.nan)
            rec["player_actual"] = float(f.get("actual", np.nan)); rows.append(rec)
P = pd.DataFrame(rows); P["mean_projection"] = pd.to_numeric(P.mean_projection, errors="coerce"); P["salary"] = pd.to_numeric(P.salary, errors="coerce")
P["ratio"] = P.player_actual / P.mean_projection.clip(lower=0.5)
P["low"] = (P.player_actual < 8) & (P.ratio < 0.4)
P["zero"] = P.player_actual <= 0
skill = P[P.pos.isin(["QB", "RB", "WR", "TE"])].copy()
def cat(rw):
    if rw.player_actual <= 0 and (str(rw.was_active) == "False" or rw.was_active is False): return "inactive/DNP (0 pts)"
    if rw.player_actual <= 0: return "active but 0 pts"
    if pd.notna(rw.depth_rank) and rw.depth_rank >= 2 and rw.pos in ("RB", "WR", "TE"): return "thin role (depth>=2)"
    if pd.notna(rw.proj_std) and pd.notna(rw.mean_projection) and rw.mean_projection > 0 and rw.proj_std / rw.mean_projection > 0.9: return "volatile boom bet (std/mean>0.9)"
    if pd.notna(rw.salary) and rw.salary >= 7000: return "star bust (salary>=7k)"
    return "other bust"
skill["category"] = skill.apply(cat, axis=1)
lines = []
lines.append(f"# Low-scoring selected players — what the model believed at lock (opened PREREG-094 D800 books; descriptive)\n")
lines.append(f"Selected lineup-player rows: {len(P):,} ({len(skill):,} skill) across {d.groupby(['season','week','bank']).ngroups} slate-banks; low scorer = < 8 pts and < 40% of projection.\n")
lo = skill[skill.low]
lines.append(f"## 1. Prevalence\n- low-scoring skill players: {len(lo):,} of {len(skill):,} ({len(lo)/len(skill):.1%}); zero-point: {int(skill.zero.sum()):,} ({skill.zero.mean():.1%})")
lines.append(f"- lineups with ≥1 low scorer: {skill.groupby(['season','week','bank','rank']).low.any().mean():.1%}; with ≥1 zero-point player: {skill.groupby(['season','week','bank','rank']).zero.any().mean():.1%}\n")
lines.append("## 2. Categories of low scorers (share of low-scoring skill players)\n")
c = lo.category.value_counts(); lines.append("| category | n | share | mean projection | mean salary | mean own_est |\n|---|---:|---:|---:|---:|---:|")
for k, v in c.items():
    sub = lo[lo.category == k]; lines.append(f"| {k} | {v} | {v/len(lo):.1%} | {sub.mean_projection.mean():.1f} | {sub.salary.mean():.0f} | {pd.to_numeric(sub.own_est, errors='coerce').mean():.3f} |")
lines.append("\n## 3. What the model believed: low scorers vs the rest of the selected players (skill)\n")
def summ(x):
    return {"n": len(x), "projection": x.mean_projection.mean(), "p90": pd.to_numeric(x.proj_p90, errors="coerce").mean(), "std/mean": (pd.to_numeric(x.proj_std, errors="coerce") / x.mean_projection.clip(lower=0.5)).mean(),
            "salary": x.salary.mean(), "depth>=2": (pd.to_numeric(x.depth_rank, errors="coerce") >= 2).mean(), "snap_l4": pd.to_numeric(x.snap_share_l4, errors="coerce").mean(),
            "dk_l4": pd.to_numeric(x.dk_points_l4, errors="coerce").mean(), "cold_start": pd.to_numeric(x.is_cold_start, errors="coerce").fillna(0).astype(float).mean(), "own_est": pd.to_numeric(x.own_est, errors="coerce").mean(),
            "practice<full": (pd.to_numeric(x.practice_level, errors="coerce") < 1).mean(), "lev_family": (x.tag == "lev").mean()}
S = pd.DataFrame({"low scorers": summ(lo), "other selected": summ(skill[~skill.low]), "selected 20+ pts": summ(skill[skill.player_actual >= 20])})
S = S.round(3); lines.append("| metric | " + " | ".join(S.columns) + " |\n|---|" + "---|" * len(S.columns))
for k, rw in S.iterrows(): lines.append(f"| {k} | " + " | ".join(str(v) for v in rw.values) + " |")
lines.append("\n## 4. By position and by salary tier (low-scorer rate among selected skill players)\n")
lines.append("| position | selected | low rate | zero rate |\n|---|---:|---:|---:|")
for pos, x in skill.groupby("pos"): lines.append(f"| {pos} | {len(x)} | {x.low.mean():.1%} | {x.zero.mean():.1%} |")
skill["tier"] = pd.cut(skill.salary, [0, 3999, 5499, 6999, 20000], labels=["<4k", "4-5.5k", "5.5-7k", ">=7k"])
lines.append("\n| salary tier | selected | low rate | zero rate | mean actual |\n|---|---:|---:|---:|---:|")
for t, x in skill.groupby("tier", observed=True): lines.append(f"| {t} | {len(x)} | {x.low.mean():.1%} | {x.zero.mean():.1%} | {x.player_actual.mean():.1f} |")
lines.append("\n## 5. Cost to the lineup and to the weekly max\n")
L = skill.groupby(["season", "week", "bank", "rank"]).agg(lineup_actual=("lineup_actual", "first"), n_low=("low", "sum"), n_zero=("zero", "sum"), proj_sum=("mean_projection", "sum")).reset_index()
lines.append(f"- lineups by number of low scorers: {L.n_low.value_counts().sort_index().to_dict()}; mean lineup score with 0 / 1 / 2+ low scorers: "
             f"{L[L.n_low==0].lineup_actual.mean():.1f} / {L[L.n_low==1].lineup_actual.mean():.1f} / {L[L.n_low>=2].lineup_actual.mean():.1f}")
best = L.sort_values("lineup_actual", ascending=False).groupby(["season", "week", "bank"]).head(1)
lines.append(f"- the slate-bank's BEST lineup carried a low scorer {best.n_low.gt(0).mean():.1%} of the time (zero-point player {best.n_zero.gt(0).mean():.1%}); books' best lineups average {best.lineup_actual.mean():.1f}")
zero_lu = L[L.n_zero > 0]; lines.append(f"- lineups with a zero-point player: {len(zero_lu)} of {len(L)} ({len(zero_lu)/len(L):.1%}); their mean score {zero_lu.lineup_actual.mean():.1f} vs {L[L.n_zero==0].lineup_actual.mean():.1f}")
lines.append("\n## 6. The most frequently selected low scorers (player-weeks appearing in many lineups)\n")
top = lo.groupby(["season", "week", "name", "pos", "team"]).agg(lineups=("rank", "size"), banks=("bank", "nunique"), projection=("mean_projection", "first"), salary=("salary", "first"), actual=("player_actual", "first"), category=("category", "first")).reset_index().sort_values("lineups", ascending=False).head(15)
lines.append("| season | week | player | pos | team | lineups (of 240) | projection | salary | actual | category |\n|---|---|---|---|---|---:|---:|---:|---:|---|")
for x in top.itertuples(): lines.append(f"| {x.season} | {x.week} | {x.name} | {x.pos} | {x.team} | {x.lineups} | {x.projection:.1f} | {x.salary:.0f} | {x.actual:.1f} | {x.category} |")
out = "/home/erich/week1-sunday/low-scorer-selection-audit.md"; open(out, "w").write("\n".join(lines) + "\n"); print(out); print("\n".join(lines[:40]))
