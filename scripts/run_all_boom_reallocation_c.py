#!/usr/bin/env python3
"""Run one cell of the all-boom reallocation arm (C endpoint first).

Protocol `20260819-all-boom-reallocation-c-v1` (operator-directed): at
the incumbent per-seed candidate budget, replace the entire lev batch
with boom-family depth — CAND_MULT=0, N_BOOM=200, BOOM_UNIQUE_FILL=1 —
against the registered native pools as control. Control needs no
regeneration (the natives are pinned truth with actual scores);
treatment regenerates from the same pinned artifacts with exactly three
lever changes, role natives injected verbatim (arm-invariant).

`--smoke` runs the outcome-blind half (generation, truncation parity,
lever receipt) and uploads nothing.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path
_scripts_dir = (_Path(__file__).parent if "__file__" in globals()
                else _Path("scripts"))
_sys.path.insert(0, str(_scripts_dir.resolve()))

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_atlas_minimal_world_selection_c as base

RUN_ID = "20260819-all-boom-reallocation-c-v1"
VERSION = "all-boom-reallocation-c-v1"
PROJECT = base.PROJECT
PROTOCOL_DOC = Path("reports/2026-08-19-all-boom-reallocation-protocol.md")
PROTOCOL_SHA256 = "cb45336918ffedf33b00e44571aae7fdbeb1c0a5ed2e22cdd5ece00d4587d680"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"all-boom-reallocation-c-runs/{RUN_ID}"
)
TREATMENT_LEVERS = {
    "CAND_MULT": "0",
    "N_BOOM": "200",
    "BOOM_UNIQUE_FILL": "1",
}
MAX_SHORTFALL_PER_SEED = 5


def _treatment_env(block: int, season: int, code_sha: str) -> dict[str, str]:
    env = base._generation_env(block, season, code_sha)
    env.update(TREATMENT_LEVERS)
    return env


def _validate_lever_env_except_treatment(
    cell: dict, env: dict[str, str],
) -> None:
    """Acquisition-record parity on every key EXCEPT the three
    predeclared treatment levers, whose treatment values are asserted."""
    recorded = dict(
        item.split("=", 1)
        for item in re.split(
            r",(?=[A-Z][A-Z0-9_]*=)", str(cell["lever_env"]))
        if "=" in item
    )
    mismatched = {
        key: (value, env.get(key, ""))
        for key, value in recorded.items()
        if key not in TREATMENT_LEVERS and str(env.get(key, "")) != value
    }
    if mismatched:
        raise RuntimeError(
            "all-boom reconstructed environment differs from the "
            f"acquisition record: {sorted(mismatched)}")
    for key, value in TREATMENT_LEVERS.items():
        if str(env.get(key, "")) != value:
            raise RuntimeError(f"all-boom treatment lever differs: {key}")


def _budget_and_roles(
    batch: base.CandidateBatch,
    ordered_natives: pd.DataFrame,
    slate: pd.DataFrame,
    artifact: dict,
) -> tuple[base.CandidateBatch, int]:
    """Truncate the regenerated (non-role) pool to the native non-role
    count, then append the registered role natives verbatim.

    This arm has no reproduction obligation, and C is order-invariant, so
    roles append at the end (never truncated) with the artifact's own
    world totals as pinned inputs. Truncation is deterministic reverse
    generation order; shortfall beyond the frozen tolerance fails closed;
    a regenerated/role identity collision fails closed.
    """
    from nfl_dfs.optimizer.lineup import Lineup

    role_rows = ordered_natives[ordered_natives.tag.astype(str).eq("epi")]
    target_non_role = len(ordered_natives) - len(role_rows)
    candidates = list(batch.candidates)
    totals = list(np.asarray(batch.candidate_totals))
    truncated_from = len(candidates)
    shortfall = max(0, target_non_role - len(candidates))
    if shortfall > MAX_SHORTFALL_PER_SEED:
        raise RuntimeError(
            f"all-boom treatment short {shortfall} candidates "
            f"(tolerance {MAX_SHORTFALL_PER_SEED})")
    candidates = candidates[:target_non_role]
    totals = totals[:target_non_role]

    art_totals = np.asarray(artifact["totals"])
    record_by_id = {str(r["id"]): r for r in slate.to_dict("records")}
    existing = {base._identity(c) for c in candidates}
    all_tags = {k: tuple(v) for k, v in batch.all_tags.items()}
    for _, row in role_rows.iterrows():
        roster = [v for v in str(row["players"]).split(",") if v]
        if len(roster) != 9 or len(set(roster)) != 9:
            raise RuntimeError("all-boom role native is not nine unique ids")
        if tuple(sorted(roster)) in existing:
            raise RuntimeError(
                "all-boom regenerated candidate collides with a role native")
        missing = [p for p in roster if p not in record_by_id]
        if missing:
            raise RuntimeError(
                f"all-boom role players missing from slate: {missing}")
        index = int(row["cand_ix"])
        if not 0 <= index < len(art_totals):
            raise RuntimeError("all-boom role cand_ix outside artifact")
        lineup = Lineup(
            players=[record_by_id[p] for p in roster], tag="epi")
        candidates.append(lineup)
        totals.append(np.asarray(art_totals[index]))
        all_tags.setdefault(lineup.ids, ("epi",))
    return base.CandidateBatch(
        candidates=tuple(candidates),
        candidate_totals=np.stack(totals),
        player_ids=batch.player_ids,
        player_rows=batch.player_rows,
        row_draws=batch.row_draws,
        all_tags=all_tags,
        metadata={
            **dict(batch.metadata),
            "truncated_from": truncated_from,
            "role_appended": len(role_rows),
        },
    ), shortfall


def run(season: int, week: int, output_uri: str, smoke: bool) -> dict:
    base.validate_frozen_inputs()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not smoke and (
        not re.fullmatch(r"[0-9a-f]{40}", code_sha)
        or not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)
    ):
        raise RuntimeError(
            "all-boom needs CODE_SHA and an immutable ANALYSIS_IMAGE")
    from google.cloud import bigquery, storage
    from run_cbwu_seed_order_audit import (
        _download_artifact, _query, _upload_create_only,
    )

    grid = json.loads(base.SOURCE_GRID.read_text())
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    params = [
        bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(base.SOURCE_PANEL_IDS)),
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ]
    natives = _query(bq, base.NATIVE_SQL, params)
    snapshots = _query(bq, base.SNAPSHOT_SQL, params)

    receipt: dict[str, Any] = {
        "version": VERSION,
        "run_id": RUN_ID,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "treatment_levers": dict(TREATMENT_LEVERS),
        "smoke": bool(smoke),
        "uses_realized_outcomes": not smoke,
        "production_change_licensed": False,
        "seeds": [],
    }
    recovery_slate = (season, week) == base.RECOVERY_CELL[1:]
    blocks = [0, 1, 2, 4] if recovery_slate else list(range(5))
    if recovery_slate:
        receipt["recovery_four_seed_slate"] = True

    treatment_pools: dict[str, base.CandidateBatch] = {}
    native_frames: dict[str, pd.DataFrame] = {}
    for block in blocks:
        panel = base.SOURCE_PANEL_IDS[block]
        cell = base._grid_cell(grid, panel, season, week)
        env = _treatment_env(block, season, code_sha or "0" * 40)
        _validate_lever_env_except_treatment(cell, env)
        panel_natives = natives[
            natives.panel_run_id.astype(str).eq(panel)].copy()
        if panel_natives.empty:
            raise RuntimeError(f"all-boom natives missing for {panel}")
        snapshot = snapshots[
            snapshots.panel_run_id.astype(str).eq(panel)].copy()
        if snapshot.empty:
            raise RuntimeError(f"all-boom snapshot missing for {panel}")
        artifact, art_receipt = _download_artifact(
            gcs, str(cell["score_artifact_uri"]),
            str(cell["score_artifact_sha256"]))
        slate = base._slate_frame(
            snapshot, np.asarray(artifact["player_ids"]))
        draws = np.asarray(artifact["player_draws"], dtype=np.float64)
        ordered = panel_natives.sort_values("cand_ix", kind="stable")
        role_identities = [
            frozenset(v for v in str(row["players"]).split(",") if v)
            for _, row in ordered.iterrows()
            if str(row["tag"]) == "epi"
        ]
        generated = base._generate(
            slate, draws, env, treatment=False,
            role_identities=role_identities)
        treatment, shortfall = _budget_and_roles(
            generated, ordered, slate, artifact)
        target = len(ordered)
        boom_uniques = sum(
            1 for c in treatment.candidates if c.tag == "boom")
        receipt["seeds"].append({
            "block": block,
            "panel_run_id": panel,
            "artifact": art_receipt,
            "native_count": int(target),
            "treatment_count": int(len(treatment.candidates)),
            "shortfall": int(shortfall),
            "boom_uniques": int(boom_uniques),
            "role_injected": (
                None if (injected := treatment.metadata.get(
                    "role_injection", {}).get("count")) is None
                else int(injected)),
            "family_counts": {
                str(tag): int(count)
                for tag, count in pd.Series(
                    [c.tag for c in treatment.candidates]
                ).value_counts().items()
            },
        })
        treatment_pools[f"R{block}"] = treatment
        native_frames[f"R{block}"] = ordered

    if not smoke:
        player_actuals = _query(bq, base.PLAYER_ACTUALS_SQL, params)
        if player_actuals.id.astype(str).duplicated().any():
            raise RuntimeError("all-boom player actuals are not unique")
        actuals = {
            str(row["id"]): float(row["actual"])
            for _, row in player_actuals.iterrows()
        }
        native_actuals = _query(bq, base.NATIVE_ACTUALS_SQL, params)
        receipt["actual_parity_max_delta"] = base._actual_parity(
            native_actuals, actuals)

        def pool_c(pools) -> dict[str, Any]:
            seen: set = set()
            scores: list[float] = []
            for rosters in pools:
                for identity in rosters:
                    if identity in seen:
                        continue
                    seen.add(identity)
                    scores.append(
                        sum(actuals[p] for p in identity))
            arr = np.asarray(scores, dtype=float)
            return {
                "c_score": float(arr.max()),
                "pool_unique": int(arr.size),
                "thresholds": {
                    str(t): int((arr >= t).sum())
                    for t in (187, 194, 200, 210, 220, 230, 240)
                },
            }

        control_rosters = [
            [tuple(sorted(v for v in str(p).split(",") if v))
             for p in frame["players"]]
            for frame in native_frames.values()
        ]
        treatment_rosters = [
            [base._identity(c) for c in pool.candidates]
            for pool in treatment_pools.values()
        ]
        receipt["control"] = pool_c(control_rosters)
        receipt["treatment"] = pool_c(treatment_rosters)
        receipt["paired_delta_c"] = (
            receipt["treatment"]["c_score"] - receipt["control"]["c_score"]
        )
    # Serialize on EVERY path: the first canary died on an np.int64 that
    # only the non-smoke branch ever tried to serialize. Smoke must
    # exercise the full receipt contract; only the upload stays gated.
    payload = json.dumps(
        receipt, sort_keys=True, separators=(",", ":")).encode()
    if not smoke:
        receipt["upload"] = _upload_create_only(gcs, output_uri, payload)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", default="")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if not args.smoke and not args.output_uri.startswith(OUTPUT_PREFIX):
        raise SystemExit(
            "all-boom output URI must live under the immutable run prefix")
    receipt = run(args.season, args.week, args.output_uri, args.smoke)
    summary = {
        key: receipt.get(key)
        for key in ("run_id", "season", "week", "smoke", "paired_delta_c")
    }
    summary["seeds"] = [
        {k: seed[k] for k in
         ("block", "treatment_count", "boom_uniques", "shortfall")}
        for seed in receipt["seeds"]
    ]
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
