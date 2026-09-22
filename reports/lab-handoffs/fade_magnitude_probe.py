import numpy as np, pandas as pd
from nfl_dfs.backtest.field import naive_ownership
from nfl_dfs.bq import query_df

df = query_df("""
  SELECT display_name, position AS pos, salary, proj_points AS proj
  FROM `nfl-predictions-503414.nfl_predictions.player_projections`
  WHERE season=2026 AND week=2
  QUALIFY generated_at = MAX(generated_at) OVER ()
""")
df = df[df.pos.isin(["QB","RB","WR","TE","DST"])].reset_index(drop=True)
own = naive_ownership(df)
fade = 25.0 * own
df["own"], df["fade"] = own, fade
print(f"slate rows: {len(df)}")
print("\nper-position group sizes and fade magnitude (penalty = 25 * own_est):")
g = df.groupby("pos").agg(n=("fade","size"), mean_fade=("fade","mean"),
                          median_fade=("fade","median"), max_fade=("fade","max"))
print(g.round(3).to_string())
print(f"\nwhole-slate: mean fade {fade.mean():.3f}  median {np.median(fade):.3f}  max {fade.max():.3f}")
print(f"fade as % of mean projection: {100*fade.mean()/df.proj.mean():.2f}%")
print("\nlargest fades (who the lever actually moves):")
print(df.nlargest(8, "fade")[["display_name","pos","salary","proj","own","fade"]].round(3).to_string(index=False))
