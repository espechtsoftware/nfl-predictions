#!/usr/bin/env python3
"""Outcome-blind historical screen for a weakest-projection selection floor.

The panel already persists the sufficient statistics used by the production
binary coverage selector: one clear-world bit mask per candidate, P(clear), and
the simulated mean tie-break.  This script filters candidates by the weakest
non-DST served projection, reruns the exact selector on each frozen slate, and
only then reads the historical candidate labels to score the resulting books.
It is a retrospective mechanism screen, not a production recommendation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from nfl_dfs.optimizer.lineup import select_from_support  # noqa: E402


PROJECT = "nfl-predictions-503414"
DATASET = "nfl_predictions"
PANEL = "20260811-pitclean-e80-k1-role12union-a12ab31"
ENTRY_COUNT = 80
TAIL_LINE = 194.0
ARMS = {"control": None, "floor8": 8.0, "floor10": 10.0, "floor12": 12.0}
TAILS = (187, 194, 200, 210, 220, 230, 240)

CANDIDATE_SQL = f"""
SELECT season, week, cand_ix, players, selected, selected_rank, actual_score,
       p_line, sim_mean, tail_line, clear_bits, n_worlds, bitorder
FROM `{PROJECT}.{DATASET}.replay_candidates`
WHERE panel_run_id = @panel_id
  AND research_eligible = TRUE
ORDER BY season, week, cand_ix
""".strip()

FEATURE_SQL = f"""
SELECT season, week, id, pos, proj
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


def decode_mask(value: object, n_worlds: int, bitorder: str) -> np.ndarray:
    if not isinstance(value, str) or not value:
        raise RuntimeError("candidate has no persisted clear mask")
    if bitorder != "big":
        raise RuntimeError(f"unsupported persisted bit order: {bitorder!r}")
    decoded = np.unpackbits(
        np.frombuffer(bytes.fromhex(value), dtype=np.uint8), bitorder=bitorder
    )
    if len(decoded) < n_worlds:
        raise RuntimeError("persisted clear mask is shorter than n_worlds")
    return decoded[:n_worlds].astype(bool, copy=False)


def attach_floor(candidates: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    frame = candidates.copy().reset_index(drop=True)
    frame.insert(0, "row_id", np.arange(len(frame), dtype=np.int64))
    roster = (
        frame[["row_id", "season", "week", "players"]]
        .assign(player_id=lambda x: x.players.str.split(","))
        .explode("player_id", ignore_index=True)
        .drop(columns="players")
        .merge(
            features.rename(columns={"id": "player_id"}),
            on=["season", "week", "player_id"],
            how="left",
            validate="many_to_one",
        )
    )
    missing = roster[roster.proj.isna()]
    if not missing.empty:
        raise RuntimeError(f"missing projection joins: {len(missing)}")
    if roster.groupby("row_id", sort=False).size().ne(9).any():
        raise RuntimeError("candidate does not have exactly nine players")
    non_dst = roster[roster.pos.ne("DST")]
    weakest = (
        non_dst.sort_values(["row_id", "proj", "player_id"], kind="mergesort")
        .drop_duplicates("row_id", keep="first")[["row_id", "proj"]]
        .rename(columns={"proj": "weakest_proj"})
    )
    if len(weakest) != len(frame):
        raise RuntimeError("weakest projection did not resolve for every candidate")
    return frame.merge(weakest, on="row_id", validate="one_to_one")


def screen(candidates: pd.DataFrame, features: pd.DataFrame) -> dict:
    frame = attach_floor(candidates, features)
    if frame[["season", "week", "cand_ix"]].duplicated().any():
        raise RuntimeError("duplicate candidate key")
    if frame.selected.isna().any():
        raise RuntimeError("selection labels are incomplete")
    baseline_check = {"slates": 0, "set_mismatches": 0, "order_mismatches": 0}
    arm_rows: dict[str, list[dict]] = {name: [] for name in ARMS}
    total_masks_decoded = 0

    for (season, week), group in frame.groupby(["season", "week"], sort=True):
        group = group.sort_values("cand_ix").reset_index(drop=True)
        baseline_check["slates"] += 1
        n_worlds = group.n_worlds.astype(int).unique()
        bitorders = group.bitorder.astype(str).unique()
        if len(n_worlds) != 1 or len(bitorders) != 1:
            raise RuntimeError(f"mixed mask metadata in {season} week {week}")
        if not np.allclose(group.tail_line.to_numpy(dtype=float), TAIL_LINE):
            raise RuntimeError(f"persisted clear masks are not the 194 line in {season} week {week}")
        n_worlds_int = int(n_worlds[0])
        clears = np.vstack(
            [decode_mask(value, n_worlds_int, bitorders[0]) for value in group.clear_bits]
        )
        total_masks_decoded += len(group)
        p_line = clears.mean(axis=1)
        if np.max(np.abs(p_line - group.p_line.to_numpy(dtype=float))) > 1e-8:
            raise RuntimeError(f"p_line does not match clear mask in {season} week {week}")
        sim_mean = group.sim_mean.to_numpy(dtype=float)
        persisted_selected = set(np.flatnonzero(group.selected.to_numpy(dtype=bool)))
        control_ix = select_from_support(clears, p_line, sim_mean, ENTRY_COUNT)
        if len(control_ix) != ENTRY_COUNT:
            raise RuntimeError(f"control selector returned {len(control_ix)} rows in {season} week {week}")
        baseline_check["set_mismatches"] += int(set(control_ix) != persisted_selected)
        persisted_order = list(
            group.assign(_ix=np.arange(len(group)))
            .query("selected")
            .sort_values("selected_rank")
            ["_ix"]
        )
        baseline_check["order_mismatches"] += int(list(control_ix) != persisted_order)

        for arm, floor in ARMS.items():
            eligible = np.ones(len(group), dtype=bool) if floor is None else group.weakest_proj.ge(floor).to_numpy()
            candidate_count = int(eligible.sum())
            row = {
                "season": int(season),
                "week": int(week),
                "candidate_count": candidate_count,
                "floor": floor,
                "feasible": candidate_count >= ENTRY_COUNT,
                "selected_count": 0,
                "selected_indices": [],
                "selected_max": None,
                "candidate_oracle": None,
                "selected_mean": None,
            }
            if not row["feasible"]:
                arm_rows[arm].append(row)
                continue
            selected_local = select_from_support(
                clears[eligible], p_line[eligible], sim_mean[eligible], ENTRY_COUNT
            )
            eligible_ix = np.flatnonzero(eligible)
            selected_ix = eligible_ix[np.asarray(selected_local, dtype=int)]
            actual = group.actual_score.to_numpy(dtype=float)
            row.update(
                {
                    "selected_count": int(len(selected_ix)),
                    "selected_indices": [int(group.iloc[i].cand_ix) for i in selected_ix],
                    "selected_max": float(actual[selected_ix].max()),
                    "candidate_oracle": float(actual[eligible].max()),
                    "selected_mean": float(actual[selected_ix].mean()),
                    "control_overlap": int(len(set(selected_ix) & set(control_ix))),
                    "selected_floor_min": float(group.iloc[selected_ix].weakest_proj.min()),
                }
            )
            for threshold in TAILS:
                row[f"selected_ge_{threshold}"] = int(actual[selected_ix].max() >= threshold)
                row[f"oracle_ge_{threshold}"] = int(actual[eligible].max() >= threshold)
            arm_rows[arm].append(row)

    summaries = {}
    slate_diagnostics: dict[str, list[dict]] = {}
    for arm, rows in arm_rows.items():
        table = pd.DataFrame(rows)
        feasible = table[table.feasible].copy()
        slate_diagnostics[arm] = [
            {key: value for key, value in row.items() if key != "selected_indices"}
            for row in rows
        ]
        summary = {
            "arm": arm,
            "floor": ARMS[arm],
            "slates": int(len(table)),
            "feasible_slates": int(len(feasible)),
            "infeasible_slates": int((~table.feasible).sum()),
            "candidate_count_min": int(table.candidate_count.min()),
            "candidate_count_median": float(table.candidate_count.median()),
            "candidate_count_mean": float(table.candidate_count.mean()),
            "selected_share": float(ENTRY_COUNT * len(feasible) / feasible.candidate_count.sum()) if len(feasible) else None,
            "mean_selected_max": float(feasible.selected_max.mean()) if len(feasible) else None,
            "median_selected_max": float(feasible.selected_max.median()) if len(feasible) else None,
            "mean_candidate_oracle": float(feasible.candidate_oracle.mean()) if len(feasible) else None,
            "mean_selected_actual": float(feasible.selected_mean.mean()) if len(feasible) else None,
            "mean_control_overlap": float(feasible.control_overlap.mean()) if len(feasible) and arm != "control" else None,
        }
        for threshold in TAILS:
            summary[f"selected_max_ge_{threshold}"] = int(feasible[f"selected_ge_{threshold}"].sum()) if len(feasible) else None
            summary[f"candidate_oracle_ge_{threshold}"] = int(feasible[f"oracle_ge_{threshold}"].sum()) if len(feasible) else None
        summaries[arm] = summary

    return {
        "panel": PANEL,
        "candidate_rows": int(len(frame)),
        "slates": int(frame.groupby(["season", "week"]).ngroups),
        "entry_count": ENTRY_COUNT,
        "tail_line": TAIL_LINE,
        "arms": summaries,
        "slate_diagnostics": slate_diagnostics,
        "baseline_reproduction": baseline_check,
        "total_masks_decoded": total_masks_decoded,
        "selection_scope": "selection-only filter on frozen historical candidate pool; masks/p_line/sim_mean only",
        "actuals_scope": "historical panel actuals read only after selection; no current-week tables queried",
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
    result = screen(candidates, features)
    result.update(
        {
            "project": PROJECT,
            "dataset": DATASET,
            "candidate_query_sha256": hashlib.sha256(CANDIDATE_SQL.encode()).hexdigest(),
            "feature_query_sha256": hashlib.sha256(FEATURE_SQL.encode()).hexdigest(),
            "selector": "nfl_dfs.optimizer.lineup.select_from_support",
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
