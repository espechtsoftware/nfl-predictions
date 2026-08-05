"""Normalized candidate data model (emerging-technologies plan §4.2,
2026-08-05): candidate_run / candidate_lineup / candidate_player DDL
plus the shim off the current engine candidate log.

WHY: the CAND_LOG_TABLE rows written by `backtest/engine.py` carry the
whole lineup as a comma-separated player string — fine for eyeballing,
useless for the reranker, GFlowNet reward joins, or per-player
exposure queries. The primary representation must be three normalized
tables keyed by (run_id, candidate_id) with a CANONICAL sorted
player-set hash so identical rosters from different generators (or
different runs) join in O(1). DDL follows the `sql/` convention:
`${predictions}` is substituted by `bq.run_sql_file`.

Offline by design: `normalize_cand_log` is a pure DataFrame transform;
no BQ calls here.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Iterable

import pandas as pd

log = logging.getLogger(__name__)

CANDIDATE_RUN_DDL = """
CREATE TABLE IF NOT EXISTS `${predictions}.candidate_run` (
  generated_at TIMESTAMP,
  run_id STRING,                -- RunContext.run_id
  parent_run_id STRING,         -- comparator/source run, if any
  run_type STRING,              -- replay | live_shadow | live_build | ...
  code_sha STRING,
  code_dirty BOOL,
  config_hash STRING,           -- stable hash of effective config
  manifest_hash STRING,         -- shipping-defaults manifest (plan 3.5)
  season INT64, week INT64, slate_id INT64,
  draft_group_id INT64, contest_id STRING,
  generator_config STRING,      -- JSON: generator settings
  generator_versions STRING,    -- JSON: generator name -> version
  n_candidates INT64,
  n_entries INT64,
  n_sims INT64,
  tail_line FLOAT64,
  n_locks INT64, n_bans INT64, n_theses INT64,
  locks STRING, bans STRING, theses STRING, notes STRING,  -- JSON
  build_kind STRING,            -- canonical | experimental | user_custom
  minutes_to_lock FLOAT64,      -- lock-relative timing at generation
  research_eligible BOOL        -- pre-lock, canonical, complete data
)
PARTITION BY DATE(generated_at)
CLUSTER BY season, week;
"""

CANDIDATE_LINEUP_DDL = """
CREATE TABLE IF NOT EXISTS `${predictions}.candidate_lineup` (
  generated_at TIMESTAMP,
  run_id STRING,
  candidate_id STRING,          -- stable within run: "<run_id>:<ix>"
  source_generator STRING,      -- tag of the arm that produced it
  source_tags STRING,           -- JSON list when several generators agree
  player_set_hash STRING,       -- sha256 of sorted player ids (canonical)
  salary INT64,
  proj_score FLOAT64,           -- sum of point projections
  sim_mean FLOAT64, sim_std FLOAT64,
  sim_q10 FLOAT64, sim_q50 FLOAT64, sim_q90 FLOAT64, sim_q99 FLOAT64,
  p_tail FLOAT64,               -- P(total >= tail_line) under the sim
  world_support INT64,          -- sims where this lineup clears the line
  weighted_world_support FLOAT64,
  stack_pattern STRING,         -- e.g. QB+2+bring-back
  bring_back BOOL,
  game_concentration FLOAT64,
  salary_left INT64,
  own_sum FLOAT64,              -- projected ownership features
  dup_risk FLOAT64,
  corr_score FLOAT64,
  selected BOOL,
  selected_rank INT64,          -- -1 when not selected
  actual_score FLOAT64,         -- populated only after results land
  actual_rank INT64,
  actual_tail BOOL
)
PARTITION BY DATE(generated_at)
CLUSTER BY run_id;
"""

CANDIDATE_PLAYER_DDL = """
CREATE TABLE IF NOT EXISTS `${predictions}.candidate_player` (
  generated_at TIMESTAMP,
  run_id STRING,
  candidate_id STRING,
  player_id STRING,             -- gsis_id (or dk id string pre-mapping)
  dk_player_id INT64,
  display_name STRING,
  position STRING, team STRING, opponent STRING, game_id STRING,
  salary INT64,
  roster_slot STRING,           -- QB/RB/WR/TE/FLEX/DST
  proj FLOAT64,                 -- pre-lock projection
  proj_q10 FLOAT64, proj_q50 FLOAT64, proj_q90 FLOAT64,
  own FLOAT64,                  -- pre-lock projected ownership
  role STRING,                  -- WR1/WR2/RB1/... from the role model
  evidence_flags STRING,        -- JSON: punt_boom, low_own, notes, ...
  model_version STRING,         -- per-player marginal/model version
  data_version STRING
)
PARTITION BY DATE(generated_at)
CLUSTER BY run_id;
"""

ALL_DDL = (CANDIDATE_RUN_DDL, CANDIDATE_LINEUP_DDL, CANDIDATE_PLAYER_DDL)


def player_set_hash(ids: Iterable) -> str:
    """Canonical lineup identity: sha256 over SORTED player ids, so the
    same roster hashes identically regardless of slot order or which
    generator emitted it."""
    canon = ",".join(sorted(str(i) for i in ids))
    return hashlib.sha256(canon.encode()).hexdigest()


def normalize_cand_log(rows: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Convert current engine CAND_LOG_TABLE rows (one row per
    candidate, `players` a comma-separated id string — see
    backtest/engine.py) into the normalized three-table form.

    Returns {"candidate_run", "candidate_lineup", "candidate_player"}
    DataFrames. Fields the flat log never carried (quantiles beyond
    q99, ownership features, actuals) are left absent — the normalized
    writers populate them; this shim exists so history is queryable in
    the new shape.
    """
    df = pd.DataFrame(rows)
    required = {"run_id", "cand_ix", "players"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"cand log rows missing columns: {sorted(missing)}")

    run_rows, lineup_rows, player_rows = [], [], []
    for run_id, grp in df.groupby("run_id", sort=False):
        first = grp.iloc[0]

        def _get(col, default=None):
            return first[col] if col in grp.columns else default

        run_rows.append({
            "generated_at": _get("generated_at"),
            "run_id": run_id,
            "run_type": "replay",
            "season": _get("season"),
            "week": _get("week"),
            "n_candidates": int(len(grp)),
            "n_entries": _get("n_entries"),
            "n_sims": _get("n_sims"),
            "tail_line": _get("tail_line"),
            "n_locks": _get("n_locks"),
            "n_theses": _get("n_theses"),
            "build_kind": "canonical",
        })
        for r in grp.itertuples():
            candidate_id = f"{run_id}:{int(r.cand_ix):05d}"
            ids = [s for s in str(r.players).split(",") if s]
            lineup_rows.append({
                "generated_at": getattr(r, "generated_at", None),
                "run_id": run_id,
                "candidate_id": candidate_id,
                "source_generator": getattr(r, "tag", None),
                "player_set_hash": player_set_hash(ids),
                "salary": getattr(r, "salary", None),
                "sim_mean": getattr(r, "sim_mean", None),
                "sim_q99": getattr(r, "sim_q99", None),
                "p_tail": getattr(r, "p_line", None),
                "selected": bool(getattr(r, "selected", False)),
                "selected_rank": getattr(r, "selected_rank", -1),
            })
            for pid in ids:
                player_rows.append({
                    "generated_at": getattr(r, "generated_at", None),
                    "run_id": run_id,
                    "candidate_id": candidate_id,
                    "player_id": pid,
                })
    out = {
        "candidate_run": pd.DataFrame(run_rows),
        "candidate_lineup": pd.DataFrame(lineup_rows),
        "candidate_player": pd.DataFrame(player_rows),
    }
    log.info("normalized cand log: %d runs, %d lineups, %d player rows",
             len(run_rows), len(lineup_rows), len(player_rows))
    return out
