"""Pool-level test of the learned lineup score: can it replace/augment expected-max selection over the WHOLE candidate corpus?
Training: the 216 opened D800_DEMAX books (2021-2024), season held out (LOSO), features WITHOUT greedy rank.
Test corpus: PREREG-083 Neo4j pools (2023, 2024; 36 slates x 2 arms; 200 candidates per slate-arm with realized scores; the
DEMAX K80 book marked). Rules at K=30/80: DEMAX (control), LEARNED_POOL (top-K of the 200 by learned score), RESORT (DEMAX-80 re-sorted
by learned, K=30), BLEND_Q99 (z learned + z sim_q99 over the pool), BLEND_P200 (z learned + z p200), UNION (DEMAX K/2 + learned-pool K/2).
Metric: realized max of the chosen K per slate-arm; delta vs DEMAX; wins/losses; per season."""
import importlib.util, json, pathlib, sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/erich/week1-sunday/tools")
from learned_order_live import COLS, lineup_features_vec, ridge
from nfl2.pipeline import slate_frame
OUT = pathlib.Path("/home/erich/week1-sunday/pool-level")

def feats_for(df, key_cols):
    feats = {}
    for (s, w), g in df.groupby(["season", "week"]):
        fr = slate_frame(int(s), int(w)); fr = fr.set_index(fr.id.astype(str)); num = {c: pd.to_numeric(fr.get(c), errors="coerce") for c in COLS}
        pos = fr.pos.astype(str); team = fr.team.astype(str); game = fr.game_id.astype(str)
        lus = [[p for p in row.players.split(",") if p in fr.index] for _, row in g.iterrows()]
        Fg = lineup_features_vec(lus, fr, num, np.zeros(len(g))); Fg.index = g.index; feats[(s, w)] = Fg
        print("features", s, w, len(g), file=sys.stderr)
    return pd.concat(feats.values()).loc[df.index].drop(columns=["greedy_rank"]).fillna(0.0)

books_path = OUT / "books216_features.parquet"
if not books_path.exists():
    spec = importlib.util.spec_from_file_location("r", "/home/erich/projects/.nfl2-worktrees/live-center-production-20260912/scripts/prereg094_report.py")
    r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
    books, meta = r._load(["114b940r1-20260913T042316Z", "114b941r1-20260913T042615Z", "114b942r1-20260913T053219Z"])
    d = pd.DataFrame(books["D800_DEMAX"]); d["rank"] = pd.to_numeric(d["rank"]); d["actual"] = pd.to_numeric(d["actual"]); d["season"] = d.season.astype(int); d["week"] = d.week.astype(int)
    d = d.join(feats_for(d, None)); d.to_parquet(books_path)
B = pd.read_parquet(books_path); fcols = [c for c in B.columns if c.startswith(("sum_", "min_", "max_")) or c in ("games", "max_game", "teams", "max_team", "qb_mates", "n_rb", "n_te")]
pool_path = OUT / "prereg083_pool_features.parquet"
if not pool_path.exists():
    P = pd.read_parquet(OUT / "prereg083_candidates.parquet"); P = P.join(feats_for(P, None)); P.to_parquet(pool_path)
P = pd.read_parquet(pool_path)
z = lambda g: (g - g.mean()) / (g.std() + 1e-9)
import itertools
def greedy_div(g, col, K, cap):
    chosen, sets = [], []
    for i, pl in zip(g.sort_values(col, ascending=False).index, g.sort_values(col, ascending=False).players):
        st = set(pl.split(","))
        if all(len(st & c) <= cap for c in sets): chosen.append(i); sets.append(st)
        if len(chosen) == K: break
    return g.loc[chosen]
def conc(df):
    sets = [set(p.split(",")) for p in df.players]; ov = [len(a & b) for a, b in itertools.combinations(sets, 2)]
    return float(np.mean(ov)) if ov else 0.0
res = []
for T in (2023, 2024):
    tr = B[B.season != T]; key = ["season", "week", "bank"]
    Z = tr.groupby(key)[fcols].transform(z).fillna(0.0); y = tr.groupby(key)["actual"].transform(z).to_numpy(); w = ridge(Z.to_numpy(), y)
    te = P[P.season == T].copy(); pkey = ["season", "week", "arm"]
    te["learned"] = (te.groupby(pkey)[fcols].transform(z).fillna(0.0).to_numpy() @ w[:-1])
    te["z_learned"] = te.groupby(pkey)["learned"].transform(z); te["z_q99"] = te.groupby(pkey)["sim_q99"].transform(z); te["z_p200"] = te.groupby(pkey)["p200"].transform(z)
    te["blend_q99"] = te.z_learned + te.z_q99; te["blend_p200"] = te.z_learned + te.z_p200
    for (s, wk, arm), g in te.groupby(pkey):
        sel = g[g.selected].sort_values("selected_rank"); pool_sorted = g.sort_values("learned", ascending=False)
        row = {"season": s, "week": wk, "arm": arm, "pool_oracle": g.actual.max(), "pool_ge200": int((g.actual >= 200).sum()), "sel_ge200": int((sel.actual >= 200).sum())}
        for K in (30, 80):
            demax = sel.head(K); row[f"DEMAX_{K}"] = demax.actual.max()
            row[f"LEARNED_POOL_{K}"] = pool_sorted.head(K).actual.max()
            row[f"RESORT_{K}"] = sel.sort_values("learned", ascending=False).head(K).actual.max()
            row[f"BLEND_Q99_{K}"] = g.sort_values("blend_q99", ascending=False).head(K).actual.max()
            row[f"BLEND_P200_{K}"] = g.sort_values("blend_p200", ascending=False).head(K).actual.max()
            u = pd.concat([demax.head(K // 2), pool_sorted]).drop_duplicates("players").head(K); row[f"UNION_{K}"] = u.actual.max()
            row[f"Q99_{K}"] = g.sort_values("sim_q99", ascending=False).head(K).actual.max()
            for cap in (4, 5, 6):
                row[f"LEARNED_DIV{cap}_{K}"] = greedy_div(g, "learned", K, cap).actual.max(); row[f"BLEND_DIV{cap}_{K}"] = greedy_div(g, "blend_q99", K, cap).actual.max()
            row[f"conc_DEMAX_{K}"] = conc(demax); row[f"conc_LEARNED_POOL_{K}"] = conc(pool_sorted.head(K)); row[f"conc_LEARNED_DIV5_{K}"] = conc(greedy_div(g, "learned", K, 5)); row[f"conc_BLEND_DIV5_{K}"] = conc(greedy_div(g, "blend_q99", K, 5))
            row[f"LEARNED_POOL_{K}_overlap_demax"] = len(set(pool_sorted.head(K).players) & set(demax.players))
        res.append(row)
    coef = pd.Series(w[:-1], index=fcols).sort_values(); print(f"\n## held-out {T}: coefficients (top -/+)\n", coef.head(6).round(3).to_dict(), "\n", coef.tail(8).round(3).to_dict())
R = pd.DataFrame(res); R.to_csv(OUT / "pool_level_results.csv", index=False)
rules = ["LEARNED_POOL", "LEARNED_DIV4", "LEARNED_DIV5", "LEARNED_DIV6", "BLEND_Q99", "BLEND_DIV4", "BLEND_DIV5", "BLEND_DIV6", "UNION", "RESORT", "Q99"]
lines = []
for K in (30, 80):
    lines.append(f"\n### K={K}  (72 slate-arms; realized max of the chosen K; delta vs DEMAX)")
    lines.append("| rule | mean DEMAX | mean rule | delta | wins | losses | 2023 delta | 2024 delta | ctrl delta | trt delta |"); lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for ru in rules:
        d_ = R[f"{ru}_{K}"] - R[f"DEMAX_{K}"]
        lines.append(f"| {ru} | {R[f'DEMAX_{K}'].mean():.2f} | {R[f'{ru}_{K}'].mean():.2f} | {d_.mean():+.2f} | {(d_>0).mean():.2f} | {(d_<0).mean():.2f} | {d_[R.season==2023].mean():+.2f} | {d_[R.season==2024].mean():+.2f} | {d_[R.arm=='control'].mean():+.2f} | {d_[R.arm=='treatment'].mean():+.2f} |")
    lines.append(f"\nmean overlap of LEARNED_POOL top-{K} with the DEMAX top-{K}: {R[f'LEARNED_POOL_{K}_overlap_demax'].mean():.1f}")
for K in (30, 80): lines.append(f"mean pairwise overlap K={K}: DEMAX {R[f'conc_DEMAX_{K}'].mean():.2f}, LEARNED_POOL {R[f'conc_LEARNED_POOL_{K}'].mean():.2f}, LEARNED_DIV5 {R[f'conc_LEARNED_DIV5_{K}'].mean():.2f}, BLEND_DIV5 {R[f'conc_BLEND_DIV5_{K}'].mean():.2f}")
lines.append(f"\npool oracle mean {R.pool_oracle.mean():.2f}; pool 200+ lineups per slate-arm {R.pool_ge200.mean():.2f}; in DEMAX-80 {R.sel_ge200.mean():.2f}")
for K in (30, 80):
    for ru in ["DEMAX"] + rules:
        lines.append(f"K={K} {ru}: slate-arms with max>=200: {int((R[f'{ru}_{K}']>=200).sum())}, >=194: {int((R[f'{ru}_{K}']>=194).sum())}")
print("\n".join(lines)); (OUT / "pool_level_results.md").write_text("\n".join(lines) + "\n")
