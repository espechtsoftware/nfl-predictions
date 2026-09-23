"""Diagnostic: are the simulator's per-player UPPER tails too thin? 2021 development slates (outside L01's 2022-24 panel).
Per slate: the production-law incumbent bank (10,000 worlds, as generation uses); per skill player projected >= 5 who
played (actual > 0 or listed active), PIT = share of his draws <= his realized DK points. Calibrated tails: 1% of players
above their simulated p99, 5% above p95, 10% above p90. Reported by position and pooled, with a binomial 95% band."""
import warnings, numpy as np, pandas as pd
warnings.filterwarnings("ignore")
from nfl2.data import slates
from nfl2.pipeline import simulate_slate, slate_frame, slate_seed
ENV = {"NFL2_ENSEMBLE": "1", "NFL2_CENTER": "mean"}
rows = []
todo = [sw for sw in slates("k1") if sw[0] == 2021]
for s, w in todo:
    fr = slate_frame(s, w)
    draws = simulate_slate(fr, n_sims=10_000, seed=slate_seed(2021, s, w), law_env=ENV)
    act = pd.to_numeric(fr.actual, errors="coerce").to_numpy(float)
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").to_numpy(float)
    pos = fr.pos.astype(str).to_numpy()
    for i in range(len(fr)):
        if pos[i] in ("QB", "RB", "WR", "TE") and proj[i] >= 5 and np.isfinite(act[i]) and act[i] != 0:
            d = draws[i]
            rows.append({"week": w, "pos": pos[i], "proj": proj[i], "act": act[i], "pit": float((d <= act[i]).mean()),
                         "p99": float(np.quantile(d, 0.99)), "p50": float(np.quantile(d, 0.5)), "mean": float(d.mean())})
    print(f"2021-W{w:02d} done ({len(rows)} player rows)", flush=True)
r = pd.DataFrame(rows)
def band(p, n): se = np.sqrt(p * (1 - p) / n); return f"{100*p:.1f}% (ideal band {100*(p-1.96*se):.1f}-{100*(p+1.96*se):.1f})"
print(f"\nplayers {len(r)} across {r.week.nunique()} slates; mean sim {r['mean'].mean():.2f} vs realized {r.act.mean():.2f}")
for label, g in [("ALL", r)] + list(r.groupby("pos")):
    n = len(g)
    print(f"  {label:4s} n={n:5d}  >p99 {100*(g.pit > 0.99).mean():5.2f}% (ideal 1; band {100*(0.01-1.96*np.sqrt(.0099/n)):.2f}-{100*(0.01+1.96*np.sqrt(.0099/n)):.2f})"
          f"  >p95 {100*(g.pit > 0.95).mean():5.2f}% (5)  >p90 {100*(g.pit > 0.90).mean():5.2f}% (10)  <p10 {100*(g.pit < 0.10).mean():5.2f}% (10)")
top = r[r.pit > 0.99]
print("\nlargest above-p99 misses (realized vs sim p99):", top.assign(gap=top.act - top.p99).nlargest(6, "gap")[["week", "pos", "proj", "p99", "act"]].round(1).to_string(index=False))
