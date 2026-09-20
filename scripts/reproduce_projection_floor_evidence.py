#!/usr/bin/env python3
"""Independently reproduce the projection-floor evidence tables.

This is deliberately a small, standalone reader rather than a call through
the panel-comparison helpers.  It reads one frozen historical panel, joins the
candidate roster IDs to the same-panel player snapshots, and writes the two
weakest-player tables used in the projection-floor proposal.  It never reads
the current-week tables and never writes BigQuery data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery


PROJECT = "nfl-predictions-503414"
DATASET = "nfl_predictions"
PANEL = "20260811-pitclean-e80-k1-role12union-a12ab31"
BUCKETS = ["min < 6", "min 6-8", "min 8-10", "min 10-12", "all >= 12"]

CANDIDATE_SQL = f"""
SELECT season, week, cand_ix, players, selected, actual_score, salary
FROM `{PROJECT}.{DATASET}.replay_candidates`
WHERE panel_run_id = @panel_id
  AND research_eligible = TRUE
ORDER BY season, week, cand_ix
""".strip()

FEATURE_SQL = f"""
SELECT season, week, id, name, pos, salary AS player_salary, proj, actual
FROM `{PROJECT}.{DATASET}.slate_player_features`
WHERE panel_run_id = @panel_id
  AND research_eligible = TRUE
ORDER BY season, week, id
""".strip()


def query_df(client: bigquery.Client, sql: str, panel: str) -> pd.DataFrame:
    config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("panel_id", "STRING", panel)]
    )
    return client.query(sql, job_config=config, location="US").result().to_dataframe(
        create_bqstorage_client=False
    )


def _json_number(value: object) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def reproduce(candidates: pd.DataFrame, features: pd.DataFrame) -> dict:
    candidates = candidates.copy().reset_index(drop=True)
    candidates.insert(0, "row_id", np.arange(len(candidates), dtype=np.int64))
    if candidates.empty or features.empty:
        raise RuntimeError("candidate or feature query returned no rows")
    if candidates[["season", "week", "cand_ix"]].duplicated().any():
        raise RuntimeError("duplicate candidate key")
    if features[["season", "week", "id"]].duplicated().any():
        raise RuntimeError("duplicate feature key")

    roster = (
        candidates[["row_id", "season", "week", "players"]]
        .assign(player_id=lambda frame: frame.players.str.split(","))
        .explode("player_id", ignore_index=True)
        .drop(columns="players")
    )
    roster = roster.merge(
        features.rename(columns={"id": "player_id"}),
        on=["season", "week", "player_id"],
        how="left",
        validate="many_to_one",
    )
    missing = roster[roster.proj.isna()]
    if not missing.empty:
        sample = missing[["season", "week", "player_id"]].head(5).to_dict("records")
        raise RuntimeError(f"missing roster feature joins: {len(missing)}; sample={sample}")
    if not roster.groupby("row_id", sort=False).size().eq(9).all():
        raise RuntimeError("candidate roster does not have exactly nine joined players")

    non_dst = roster[roster.pos.ne("DST")].copy()
    weakest = (
        non_dst.sort_values(["row_id", "proj", "player_id"], kind="mergesort")
        .drop_duplicates("row_id", keep="first")
        [["row_id", "player_id", "name", "pos", "player_salary", "proj", "actual"]]
        .rename(
            columns={
                "player_id": "weakest_id",
                "name": "weakest_name",
                "pos": "weakest_pos",
                "player_salary": "weakest_salary",
                "proj": "weakest_proj",
                "actual": "weakest_actual",
            }
        )
    )
    sub12 = (
        non_dst.assign(sub12=non_dst.proj.lt(12))
        .groupby("row_id", as_index=False)
        .agg(sub12=("sub12", "sum"), non_dst_players=("proj", "size"))
    )
    frame = candidates.merge(weakest, on="row_id", validate="one_to_one").merge(
        sub12, on="row_id", validate="one_to_one"
    )
    frame["bucket"] = pd.cut(
        frame.weakest_proj,
        bins=[-np.inf, 6, 8, 10, 12, np.inf],
        right=False,
        labels=BUCKETS,
    )
    if frame.bucket.isna().any():
        raise RuntimeError("weakest projections did not bucket")
    frame["slate_max"] = frame.groupby(["season", "week"]).actual_score.transform("max")
    frame["actual_rank"] = frame.groupby(["season", "week"]).actual_score.rank(
        method="min", ascending=False
    )
    slate_sizes = frame.groupby(["season", "week"]).actual_score.transform("size")
    ascending_rank = frame.groupby(["season", "week"]).actual_score.rank(
        method="average", ascending=True
    )
    frame["within_slate_pctile"] = (ascending_rank - 1) / (slate_sizes - 1)

    rows = []
    weakest_rows = []
    for bucket in BUCKETS:
        group = frame[frame.bucket.eq(bucket)]
        if group.empty:
            raise RuntimeError(f"empty bucket: {bucket}")
        winners = group[group.actual_score.eq(group.slate_max)][["season", "week"]].drop_duplicates()
        rows.append(
            {
                "bucket": bucket,
                "n": int(len(group)),
                "pool_share": float(len(group) / len(frame)),
                "sub12_players_per_lineup": float(group.sub12.mean()),
                "mean_actual": float(group.actual_score.mean()),
                "within_slate_pctile": float(group.within_slate_pctile.mean()),
                "p_ge_187": float(group.actual_score.ge(187).mean()),
                "p_ge_194": float(group.actual_score.ge(194).mean()),
                "p_ge_200": float(group.actual_score.ge(200).mean()),
                "slate_winners": int(len(winners)),
                "top10_of_slate_rate": float(group.actual_rank.le(10).mean()),
                "selected_share": float(group.selected.astype(bool).mean()),
            }
        )
        weakest_rows.append(
            {
                "bucket": bucket,
                "lineups": int(len(group)),
                "avg_weakest_salary": float(group.weakest_salary.mean()),
                "avg_weakest_proj": float(group.weakest_proj.mean()),
                "avg_weakest_actual": float(group.weakest_actual.mean()),
                "p_weakest_actual_ge_10": float(group.weakest_actual.ge(10).mean()),
                "p_weakest_actual_ge_15": float(group.weakest_actual.ge(15).mean()),
                "p_weakest_actual_ge_20": float(group.weakest_actual.ge(20).mean()),
                "p_weakest_actual_le_2": float(group.weakest_actual.le(2).mean()),
            }
        )

    return {
        "panel": PANEL,
        "candidate_rows": int(len(candidates)),
        "feature_rows": int(len(features)),
        "slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
        "selected_rows": int(candidates.selected.astype(bool).sum()),
        "roster_rows": int(len(roster)),
        "missing_roster_feature_rows": 0,
        "bucket_table": rows,
        "weakest_player_table": weakest_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--panel", default=PANEL)
    args = parser.parse_args()
    if args.panel != PANEL:
        raise SystemExit(f"refusing non-frozen panel: {args.panel}")
    client = bigquery.Client(project=PROJECT, location="US")
    candidates = query_df(client, CANDIDATE_SQL, args.panel)
    features = query_df(client, FEATURE_SQL, args.panel)
    result = reproduce(candidates, features)
    result.update(
        {
            "project": PROJECT,
            "dataset": DATASET,
            "candidate_query_sha256": hashlib.sha256(CANDIDATE_SQL.encode()).hexdigest(),
            "feature_query_sha256": hashlib.sha256(FEATURE_SQL.encode()).hexdigest(),
            "actuals_scope": "historical panel actuals only; no current-week tables queried",
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
