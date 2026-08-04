"""Walk-forward TabPFN-v2 projection quantiles (the sim's default
marginals since Addendum 50). Runs on Cloud Run L4 (job: tabpfn-gen).

Modes:
- default: for each season in SEASONS, context = strictly-earlier panel
  rows, predict all rows -> features.tabpfn_projections (WRITE_TRUNCATE).
- TABPFN_UPCOMING="2026:1": ALSO predict the upcoming week's rows from
  player_week_inference (context = all prior TRAINING rows) and append
  them — this is what makes the lever live on Sundays. Run weekly.
"""
import os
import time

import numpy as np
import pandas as pd
import torch
from google.cloud import bigquery

PROJECT = os.environ["GCP_PROJECT"]
QS = [0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
      0.60, 0.70, 0.80, 0.90, 0.95, 0.99]
QCOLS = [f"q{int(q*100):02d}" for q in QS]
CTX_MAX = 28_000
SEASONS = [2019, 2021, 2022, 2023, 2024, 2025]

bq = bigquery.Client(project=PROJECT)
feats = open("/app/features.txt").read().split()


def prep(df):
    df = df[df.position.isin(["QB", "RB", "WR", "TE"])].copy()
    df["pos_code"] = df.position.map(
        {p: i for i, p in enumerate(["QB", "RB", "WR", "TE"])})
    for c in X_cols:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    return df


X_cols = sorted(feats) + ["pos_code"]
panel = bq.query(
    f"SELECT * FROM `{PROJECT}.nfl_features.player_week_training`"
).to_dataframe()
panel = prep(panel)
print(f"panel {len(panel):,} rows {panel.season.min()}-{panel.season.max()}",
      flush=True)

from tabpfn import TabPFNRegressor

rng = np.random.default_rng(7)


def fit_predict(tr, te):
    if len(tr) > CTX_MAX:
        tr = tr.iloc[rng.choice(len(tr), CTX_MAX, replace=False)]
    reg = TabPFNRegressor(device="cuda" if torch.cuda.is_available() else "cpu",
                          n_estimators=4, ignore_pretraining_limits=True,
                          random_state=7)
    reg.fit(tr[X_cols].to_numpy(np.float32),
            tr.y_dk_points.to_numpy(np.float32))
    qs = reg.predict(te[X_cols].to_numpy(np.float32),
                     output_type="quantiles", quantiles=QS)
    mean = reg.predict(te[X_cols].to_numpy(np.float32))
    f = te[["season", "week", "gsis_id"]].copy()
    f["mean"] = np.asarray(mean, float)
    for c, arr in zip(QCOLS, qs):
        f[c] = np.maximum(np.asarray(arr, float), 0.0)
    return f


out = []
for S in SEASONS:
    tr = panel[(panel.season < S) & panel.y_dk_points.notna()]
    te = panel[panel.season == S]
    if tr.empty or te.empty:
        print(f"skip {S}", flush=True)
        continue
    t0 = time.time()
    out.append(fit_predict(tr, te))
    print(f"season {S}: pred {len(te):,} ({time.time()-t0:.0f}s)", flush=True)

up = os.environ.get("TABPFN_UPCOMING", "")
if up:
    us, uw = (int(x) for x in up.split(":"))
    inf = bq.query(
        f"SELECT * FROM `{PROJECT}.nfl_features.player_week_inference` "
        f"WHERE season={us} AND week={uw}").to_dataframe()
    inf = prep(inf)
    tr = panel[panel.y_dk_points.notna()]
    if not inf.empty:
        t0 = time.time()
        out.append(fit_predict(tr, inf))
        print(f"upcoming {us} w{uw}: pred {len(inf):,} "
              f"({time.time()-t0:.0f}s)", flush=True)
    else:
        print(f"upcoming {us} w{uw}: no inference rows", flush=True)

allf = pd.concat(out, ignore_index=True).drop_duplicates(
    ["season", "week", "gsis_id"], keep="last")
job = bq.load_table_from_dataframe(
    allf, f"{PROJECT}.nfl_features.tabpfn_projections",
    job_config=bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE"))
job.result()
print(f"loaded {len(allf):,} rows; TABPFN_GEN_DONE", flush=True)
