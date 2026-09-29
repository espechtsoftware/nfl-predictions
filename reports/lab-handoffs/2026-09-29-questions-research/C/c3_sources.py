"""C3: pre-lock ownership sources vs the realized Millionaire top-15, 36 lab slates (2023-24) and 2026 W1.
Sources: LAG (walk-forward lag model, inputs weeks W-1..W-3, available Tuesday), LINESTAR (vendor projected ownership
from the L15 cache; capture time UNKNOWN, not provably pre-lock), BLEND_PCT (mean of the two where LineStar covers),
ORACLE = realized (post-settlement). 2026 W1: own_shadow naive / booster (generated 2026-09-10 16:57Z, Thursday) and
naive_ownership(frame) at build time, vs realized Millionaire ownership (sum of slots)."""
import sys, json, re, numpy as np, pandas as pd
W = "/home/erich/projects/.nfl2-worktrees/prereg-l15-20260929"; sys.path.insert(0, f"{W}/experiments")
from l15_linestar_ownership import linestar_slate, norm, slates
S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/72305fd0-5efb-4d88-a744-a668e10ec3e9/scratchpad/q/C"
CACHE = "/home/erich/.cache/linestar-l15"
SKILL = ["QB","RB","WR","TE"]; POSK = {"QB":3,"RB":5,"WR":5,"TE":3}
pmap = {tuple(v): int(k) for k, v in json.load(open(f"{CACHE}/pmap.json")).items()}
rows = []
for season, week in slates():
    lag = pd.read_csv(f"{W}/results/l05_sets/lag/{season}-w{week:02d}.csv"); orc = pd.read_csv(f"{W}/results/l05_sets/oracle/{season}-w{week:02d}.csv")
    bl = pd.read_csv(f"{W}/results/l15_sets/blend_pct/{season}-w{week:02d}.csv")
    ls = linestar_slate(json.load(open(f"{CACHE}/p{pmap[(season, week)]}.json")))
    for d in (lag, orc, bl): d["key"] = d.display_name.map(norm); d["pos"] = d.pos.astype(str).str.upper()
    j = (orc[["key","pos","salary","proj","pred_own"]].rename(columns={"pred_own":"actual"})
         .merge(lag[["key","pos","pred_own"]].rename(columns={"pred_own":"lag"}), on=["key","pos"], how="left")
         .merge(bl[["key","pos","pred_own"]].rename(columns={"pred_own":"blend"}), on=["key","pos"], how="left")
         .merge(ls, on=["key","pos"], how="left")).drop_duplicates(["key","pos"])
    j["proj_rank_own"] = j.proj  # our projection as a "chalk predictor" for comparison
    j["value"] = j.proj / (j.salary/1000)
    sk = j[j.pos.isin(SKILL)].copy()
    r = {"season": season, "week": week, "n": len(sk), "ls_cov": sk.own_proj.notna().mean(), "sum_actual": sk.actual.sum()}
    for k in (5, 10, 15):
        top = set(sk.nlargest(k, "actual").index)
        for src in ("lag", "blend", "own_proj", "proj", "value"):
            r[f"{src}_top{k}"] = len(top & set(sk.dropna(subset=[src]).nlargest(k, src).index))
    # per-position top-k hits at k = QB3 RB5 WR5 TE3, for lag/blend/linestar
    for p, k in POSK.items():
        dp = sk[sk.pos == p]; top = set(dp.nlargest(k, "actual").index)
        for src in ("lag", "blend", "own_proj"):
            r[f"{src}_{p}"] = len(top & set(dp.dropna(subset=[src]).nlargest(k, src).index))
    # calibration of level at the top: predicted % of the realized top-15 vs realized
    t15 = sk.nlargest(15, "actual")
    r["top15_actual_mean"] = t15.actual.mean(); r["top15_lag_mean"] = t15.lag.mean(); r["top15_blend_mean"] = t15.blend.mean(); r["top15_ls_mean"] = t15.own_proj.mean()
    rows.append(r)
R = pd.DataFrame(rows); R.to_csv(f"{S}/c3_per_slate.csv", index=False)
print("=== C3: 36 lab slates (2023-24), skill players in the oracle (realized Millionaire) file; hits = overlap with the realized top-k ===")
print(f"players per slate {R.n.mean():.0f}; LineStar covers {R.ls_cov.mean():.1%} of them (its top-k is taken among covered players only)")
for k in (5, 10, 15):
    print(f"top-{k}: " + "  ".join(f"{s}: {R[f'{s}_top{k}'].mean():.2f}/{k} ({R[f'{s}_top{k}'].mean()/k:.0%})" for s in ("lag","blend","own_proj","proj","value")))
print("by season, top-15:"); print(R.groupby("season")[[f"{s}_top15" for s in ("lag","blend","own_proj","proj","value")]].mean().round(2).to_string())
print("per position hits (k: QB3 RB5 WR5 TE3):")
for p, k in POSK.items():
    print(f"  {p}: " + "  ".join(f"{s} {R[f'{s}_{p}'].mean():.2f}/{k}" for s in ("lag","blend","own_proj")))
print(f"level at the realized top-15: realized {R.top15_actual_mean.mean():.1f}% | lag {R.top15_lag_mean.mean():.1f}% | blend {R.top15_blend_mean.mean():.1f}% | LineStar {R.top15_ls_mean.mean():.1f}%")
pb = (R.blend_top15 > R.lag_top15).sum(); pl = (R.blend_top15 < R.lag_top15).sum()
print(f"paired blend vs lag at top-15: blend better {pb}, worse {pl}, tie {36-pb-pl}")

# ---------- 2026 W1 ----------
print("\n=== 2026 W1: own_shadow (naive = production fade input; booster) generated 2026-09-10 16:57Z vs REALIZED Millionaire ownership; naive_ownership(frame) at the T-70 build ===")
os_ = pd.read_csv(f"{S}/own_shadow_2026w1.csv"); os_ = os_[os_.generated_at == os_.generated_at.max()].copy(); os_["key"] = os_.name.map(norm)
om = pd.read_csv(f"{S}/own_2026_milly.csv"); om["key"] = om.display_name.map(norm)
sys.path.insert(0, "/home/erich/projects/nfl-predictions/src")
from nfl_dfs.backtest.field import naive_ownership
frames = {1:"/home/erich/week1-sunday/composite-20260913t1550z-t70-e7255e9/frame.parquet", 2:"/home/erich/week2-sunday/vetted-20260920t1410z-d3200-2dc116c/frame.parquet", 3:"/home/erich/week3-sunday/composite-20260927t1550z-d800-65305f5/frame.parquet"}
for w, p in frames.items():
    f = pd.read_parquet(p); f["key"] = f.name.map(norm)
    try:
        f["naive_frame"] = np.asarray(naive_ownership(f))
    except Exception as e:
        print("naive_ownership failed", e); f["naive_frame"] = np.nan
    f["value"] = f.proj / (f.salary/1000)
    d = om[om.week == w][["key","own"]].merge(f[["key","pos","proj","value","naive_frame","salary"]], on="key", how="left")
    if w == 1:
        d = d.merge(os_[["key","pred_own","booster_own"]], on="key", how="left")
    sk = d[d.pos.isin(SKILL)]
    srcs = ["proj","value","naive_frame"] + (["pred_own","booster_own"] if w == 1 else [])
    out = {}
    for k in (5, 10, 15):
        top = set(sk.nlargest(k, "own").index)
        out[k] = {s: len(top & set(sk.dropna(subset=[s]).nlargest(k, s).index)) for s in srcs}
    print(f"W{w}: skill players with realized ownership {len(sk)}; hits: " + "; ".join(f"top-{k} " + ", ".join(f"{s} {v}" for s, v in out[k].items()) for k in (5,10,15)))
    for s in srcs:
        m = sk.dropna(subset=[s]); print(f"   Spearman(realized own, {s}) = {m.own.rank().corr(m[s].rank()):+.3f} (n {len(m)})")
