"""Pull the historical selection/sorting test bed into the CURRENT directory (outside the repo).

    cd $TESTBED && python pull_testbed.py

- `cands.parquet`: every candidate of replay panel 20260811-pitclean-e80-k1-a12ab31 (107 slates, 2019 and
  2021-25, ~240 candidates each) with its simulated summary, selection flag/rank and realized score.
- `spf_full.parquet`: the same panel's player frame (pre-lock projections, salary, market, p90).
- `npz/`: the per-slate candidate x 10,000-world score matrices the panel archived (~0.9 GB). These are the
  GENERATION worlds, so expected-max read on them is slightly optimistic for boom lineups.
- `p90_2026.csv` (written to $WIN): served p90 for the 2026 W1/W2 last pre-lock projections, used by
  sleeve_reach.py's ownership model.
"""
import os
import subprocess
from pathlib import Path

from google.cloud import bigquery

P = "nfl-predictions-503414"
PANEL = "20260811-pitclean-e80-k1-a12ab31"
here = Path.cwd()
if Path(__file__).resolve().parents[2] in here.resolve().parents or here.resolve() == Path(__file__).resolve().parent:
    raise SystemExit("run from a data directory outside the repo")
c = bigquery.Client(project=P)
c.query(f"""SELECT season, week, cand_ix, tag, all_tags, selected, selected_rank, salary, p_line, sim_mean, sim_sd,
       sim_q50, sim_q90, sim_q99, actual_score, actual_rank, players, score_artifact_uri
       FROM `{P}.nfl_predictions.replay_candidates` WHERE panel_run_id = "{PANEL}" """).to_dataframe().to_parquet("cands.parquet")
c.query(f"""SELECT season, week, id, gsis_id, name, pos, team, opp, salary, proj, mean_projection, market_points,
       model_points_pre, proj_p90, own_est, actual, implied_team_total
       FROM `{P}.nfl_predictions.slate_player_features` WHERE panel_run_id = "{PANEL}" """).to_dataframe().to_parquet("spf_full.parquet")
(here / "npz").mkdir(exist_ok=True)
subprocess.run(["gcloud", "storage", "cp", f"gs://{P}-raw/cand_scores/{PANEL}/*.npz", "npz/"], check=True)
win = Path(os.environ["WIN"])
c.query(f"""SELECT week, display_name, proj_p90 FROM `{P}.nfl_predictions.player_projections`
       WHERE season = 2026 AND (
         (week = 1 AND generated_at BETWEEN TIMESTAMP("2026-09-13 16:03:00") AND TIMESTAMP("2026-09-13 16:05:00"))
      OR (week = 2 AND generated_at BETWEEN TIMESTAMP("2026-09-20 16:02:00") AND TIMESTAMP("2026-09-20 16:03:00")))"""
        ).to_dataframe().to_csv(win / "p90_2026.csv", index=False)
print("test bed pulled")
