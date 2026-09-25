import pandas as pd, numpy as np
rng = np.random.default_rng(7)
g = pd.read_csv("games.csv")
g = g[(g.game_type=="REG") & g.total_line.notna() & g.home_score.notna()].copy()
g["resid"] = g.home_score + g.away_score - g.total_line
g["margin_resid"] = (g.home_score - g.away_score) - g.spread_line
def hhmm(t):
    try: h,m = str(t).split(":"); return int(h)*60+int(m)
    except: return np.nan
g["tmin"] = g.gametime.map(hhmm)
main = g[(g.weekday=="Sunday") & (g.tmin>=13*60) & (g.tmin<=16*60+45)].copy()

def icc_oneway(df, col, grp):
    # unbalanced one-way random-effects ICC(1)
    groups = [x[col].values for _,x in df.groupby(grp) if len(x)>=2]
    N = sum(len(x) for x in groups); a = len(groups)
    grand = np.concatenate(groups).mean()
    ssb = sum(len(x)*(x.mean()-grand)**2 for x in groups); ssw = sum(((x-x.mean())**2).sum() for x in groups)
    msb = ssb/(a-1); msw = ssw/(N-a)
    n0 = (N - sum(len(x)**2 for x in groups)/N)/(a-1)
    return (msb-msw)/(msb+(n0-1)*msw), n0, a

def perm_p(df, col, grp, stat_obs, B=2000):
    # permute residuals across weeks WITHIN season, keep week sizes
    cnt=0
    for b in range(B):
        d = df.copy()
        d[col] = d.groupby("season")[col].transform(lambda s: rng.permutation(s.values))
        if icc_oneway(d,col,grp)[0] >= stat_obs: cnt+=1
    return (cnt+1)/(B+1)

for label, df in [("all REG games 2006-2025", g[(g.season>=2006)&(g.season<=2025)]),
                  ("Sunday main-slate games 2006-2025", main[(main.season>=2006)&(main.season<=2025)]),
                  ("Sunday main-slate 2014-2025", main[(main.season>=2014)&(main.season<=2025)])]:
    df = df.assign(wk=df.season.astype(str)+"-"+df.week.astype(str))
    icc, n0, a = icc_oneway(df,"resid","wk")
    iccm, _, _ = icc_oneway(df,"margin_resid","wk")
    p = perm_p(df,"resid","wk",icc,B=1000)
    sd = df.resid.std()
    wm = df.groupby("wk").resid.agg(["mean","size","sum"])
    infl = 1+(n0-1)*icc
    print(f"\n== {label}: games={len(df)} weeks={a} avg games/week={n0:.1f}")
    print(f"  total-points residual SD per game = {sd:.2f}; mean = {df.resid.mean():+.2f}")
    print(f"  ICC(within-week) of total residual = {icc:+.4f}  (permutation p={p:.4f});  ICC of margin residual = {iccm:+.4f}")
    print(f"  => variance inflation of a {n0:.0f}-game slate SUM vs independent games: x{infl:.2f} (SD x{np.sqrt(infl):.2f})")
    print(f"  weekly slate-sum residual SD: observed {wm['sum'].std():.1f} pts vs independent-games expectation {sd*np.sqrt(wm['size']).mean():.1f}")
    # by week-of-season bucket
    df["bucket"] = pd.cut(df.week,[0,2,4,8,13,18],labels=["W1-2","W3-4","W5-8","W9-13","W14-18"])
    print("  mean residual / SD by week bucket:\n", df.groupby("bucket",observed=True).resid.agg(["mean","std","size"]).round(2).to_string())

# 2026 so far
g26 = g[(g.season==2026)]
print("\n2026 so far (all REG games with lines & scores):")
print(g26.groupby("week").resid.agg(["mean","sum","size"]).round(2))
