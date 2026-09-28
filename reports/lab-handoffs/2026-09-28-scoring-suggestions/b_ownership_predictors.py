"""LineStar projected ownership vs realized Millionaire ownership, within-slate Spearman by season (run from the
directory holding ls_main.parquet from the 09-25 scripts)."""
import pandas as pd, numpy as np
from scipy import stats
df = pd.read_parquet("ls_main.parquet")
sk = df[df.pos.isin(["QB", "RB", "WR", "TE"])]
for s, g in df.groupby("season"):
    a = [stats.spearmanr(x.own_proj, x.own_act)[0] for _, x in g.groupby("week") if len(x) > 50]
    b = [stats.spearmanr(x.own_proj, x.own_act)[0] for _, x in sk[sk.season == s].groupby("week") if len(x) > 50]
    print(f"{s}: all {np.mean(a):.3f} skill {np.mean(b):.3f} (n {len(a)})")
print("lag model walk-forward (HANDOFF 2026-09-23): 2023 0.751 / 2024 0.768 / 2025 0.767")
