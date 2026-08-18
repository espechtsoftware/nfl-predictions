#!/usr/bin/env python3
"""Run one cell of the frozen minimal ATLAS world-selection C test.

Protocol `20260818-atlas-minimal-world-selection-c-v1` (Part B of the
disposition document); implementation freeze
`reports/2026-08-18-atlas-minimal-c-implementation-freeze.md`.

Per slate: for each of the five money-worlds seed panels, reconstruct the
exact generation slate from the panel's immutable snapshot, rerun the
production generator twice from the panel's pinned world artifact — control
(incumbent boom ranking) and treatment (`ATLAS_BOOM_WORLD_RANKING=1`) —
prove the control arm reproduces the registered natives exactly, and only
then read outcomes to report candidate `C`, exact-80 `S` and the diversity
context for both arms.

`--smoke` runs the outcome-blind half only (reconstruction, generation,
reproduction gate) and uploads nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd

from nfl_dfs.backtest.engine import CandidateBatch, tail_select_lineups
from nfl_dfs.backtest.payout import gpp
from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books
from nfl_dfs.optimizer.lineup import StackRules, select_tail_entries
from nfl_dfs.research.atlas_money_transfer import (
    SEED_PAIRS,
    acquisition_environment,
    panel_id,
)

RUN_ID = "20260818-atlas-minimal-world-selection-c-v1"
VERSION = "atlas-minimal-world-selection-c-v1"
PROJECT = "nfl-predictions-503414"
FREEZE_DOC = Path("reports/2026-08-18-atlas-minimal-c-implementation-freeze.md")
FREEZE_DOC_SHA256 = (
    "4fdb514333e5c7c073fd6c1dd0710290af0155d5da510b5f97a090fd0acfd4fb"
)
SOURCE_GRID = Path(
    "reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/"
    "source-grid.json"
)
SOURCE_GRID_SHA256 = (
    "9a18458c63f0155b72f3847c705fbd0bdde9b64c923a5b63cc4a1f42bfe3445b"
)
SOURCE_PANEL_IDS = tuple(panel_id(block) for block in range(5))
CAND_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
SNAPSHOT_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"atlas-minimal-world-selection-c-runs/{RUN_ID}"
)
# Registered support census (counts only, 2026-08-18): candidates per panel.
EXPECTED_PANEL_CANDIDATES = {
    SOURCE_PANEL_IDS[0]: 13633,
    SOURCE_PANEL_IDS[1]: 13649,
    SOURCE_PANEL_IDS[2]: 13642,
    SOURCE_PANEL_IDS[3]: 13395,
    SOURCE_PANEL_IDS[4]: 13632,
}
# r3/2025-W1 was never registered (artifact-only recovery in the transfer;
# no snapshot, no natives), so faithful regeneration is impossible for that
# seed. That slate runs BOTH arms on the same four seeds — parity holds.
RECOVERY_CELL = (SOURCE_PANEL_IDS[3], 2025, 1)
TAIL_LINE = 194.0
N_ENTRIES = 40
WORLDS_PER_ARTIFACT = 10_000
# Infrastructure destinations blanked at generation (outside the lever set).
BLANKED_ENV = (
    "CAND_LOG_TABLE", "CAND_FEATURE_TABLE", "REPLAY_LINEUPS_TABLE",
    "CAND_ARTIFACT_BUCKET",
)

NATIVE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, players,
       score_artifact_uri, score_artifact_sha256
FROM `{CAND_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND season = @season AND week = @week
ORDER BY panel_run_id, cand_ix
"""
SNAPSHOT_SQL = f"""
SELECT panel_run_id, season, week, id, gsis_id, name, pos, team, opp,
       game_id, salary, proj, proj_tourney, own_est, consensus_div,
       market_points, model_points_pre, mean_projection, proj_p10,
       proj_p50, proj_p90, proj_std
FROM `{SNAPSHOT_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND season = @season AND week = @week
ORDER BY panel_run_id, id
"""
# Outcome reads happen only after every validity gate, never in smoke.
NATIVE_ACTUALS_SQL = f"""
SELECT panel_run_id, cand_ix, players, actual_score
FROM `{CAND_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND season = @season AND week = @week
ORDER BY panel_run_id, cand_ix
"""
PLAYER_ACTUALS_SQL = f"""
SELECT DISTINCT id, actual
FROM `{SNAPSHOT_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND season = @season AND week = @week
"""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_frozen_inputs() -> None:
    for path, digest in ((FREEZE_DOC, FREEZE_DOC_SHA256),
                         (SOURCE_GRID, SOURCE_GRID_SHA256)):
        if not path.is_file() or _sha256_file(path) != digest:
            raise RuntimeError(f"ATLAS C frozen input differs: {path}")


def _grid_cell(grid: list[dict], panel: str, season: int, week: int) -> dict:
    rows = [
        cell for cell in grid
        if cell["panel_run_id"] == panel
        and int(cell["season"]) == season and int(cell["week"]) == week
    ]
    if len(rows) != 1:
        raise RuntimeError(
            f"ATLAS C source grid names {len(rows)} cells for "
            f"{panel}/{season}-{week}"
        )
    return rows[0]


def _validate_lever_env(cell: dict, env: dict[str, str]) -> None:
    """The reconstructed environment must match the acquisition record."""
    recorded = dict(
        item.split("=", 1) for item in str(cell["lever_env"]).split(",")
        if "=" in item
    )
    mismatched = {
        key: (value, env.get(key, ""))
        for key, value in recorded.items()
        if str(env.get(key, "")) != value
    }
    if mismatched:
        raise RuntimeError(
            "ATLAS C reconstructed environment differs from the "
            f"acquisition record: {sorted(mismatched)}"
        )


def _generation_env(block: int, season: int, code_sha: str) -> dict[str, str]:
    env = acquisition_environment(
        block=block, season=season, code_sha=code_sha, project=PROJECT,
    )
    for key in BLANKED_ENV:
        env[key] = ""
    return env


def _slate_frame(
    snapshot: pd.DataFrame, player_ids: np.ndarray,
) -> pd.DataFrame:
    """Reconstruct the generation slate: skill rows in artifact order
    (draw_idx = 0..n-1) followed by DST rows sorted by team (draw_idx=-1)."""
    frame = snapshot.copy()
    frame["id"] = frame["id"].astype(str)
    if frame["id"].duplicated().any():
        raise RuntimeError("ATLAS C snapshot has duplicate player ids")
    catalog = frame.set_index("id", drop=False)
    ids = [str(value) for value in player_ids]
    missing = set(ids) - set(catalog.index)
    if missing:
        raise RuntimeError(
            f"ATLAS C artifact players missing from snapshot: "
            f"{sorted(missing)[:5]}"
        )
    skill = catalog.loc[ids].reset_index(drop=True)
    if (skill["pos"].astype(str).str.upper() == "DST").any():
        raise RuntimeError("ATLAS C artifact rows include DST players")
    skill["draw_idx"] = np.arange(len(skill), dtype=int)
    dst = catalog[~catalog.index.isin(ids)].copy()
    if not (dst["pos"].astype(str).str.upper() == "DST").all():
        raise RuntimeError(
            "ATLAS C non-artifact snapshot rows are not all DST"
        )
    dst = dst.sort_values("team").reset_index(drop=True)
    dst["draw_idx"] = -1
    slate = pd.concat([skill, dst], ignore_index=True)
    return slate


def _identity(lineup) -> tuple[str, ...]:
    return tuple(sorted(str(value) for value in lineup.ids))


def _generate(
    slate: pd.DataFrame,
    draws: np.ndarray,
    env: dict[str, str],
    treatment: bool,
) -> CandidateBatch:
    run_env = dict(env)
    if treatment:
        run_env["ATLAS_BOOM_WORLD_RANKING"] = "1"
    captured: list[CandidateBatch] = []
    stack = StackRules(
        qb_stack_min=int(run_env.get("STACK_QB_MIN", "2")),
        bring_back_min=int(run_env.get("STACK_BRING_BACK", "1")),
        forbid_rb_vs_dst=run_env.get("FORBID_RB_DST", "1") != "0",
    )
    pool = slate.to_dict("records")
    previous = {
        key: os.environ.get(key)
        for key in set(run_env) | {"ATLAS_BOOM_WORLD_RANKING"}
    }
    os.environ.update(run_env)
    os.environ.pop("ATLAS_BOOM_WORLD_RANKING", None)
    if treatment:
        os.environ["ATLAS_BOOM_WORLD_RANKING"] = "1"
    try:
        lineups = tail_select_lineups(
            slate, pool, draws, TAIL_LINE, N_ENTRIES, stack,
            "proj_tourney",
            candidate_multiple=int(run_env.get("CAND_MULT", "2")),
            n_boom_solves=int(run_env.get("N_BOOM", "40")),
            n_game_stacks=int(run_env.get("N_GAMESTACK", "4")),
            contest=gpp(),
            sharp_fraction=0.0,
            cand_log_table=None,
            policy_env=run_env,
            candidate_capture=captured.append,
        )
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    if len(captured) != 1:
        raise RuntimeError(
            f"ATLAS C generation captured {len(captured)} batches"
        )
    if not lineups:
        raise RuntimeError("ATLAS C generation selected no lineups")
    return captured[0]


def _native_identities(rows: pd.DataFrame) -> list[tuple[str, ...]]:
    identities = []
    for raw in rows.sort_values("cand_ix", kind="stable")["players"]:
        values = list(raw) if not isinstance(raw, str) else [
            value for value in raw.split(",") if value
        ]
        identities.append(tuple(sorted(str(value) for value in values)))
    return identities


def _reproduction_check(
    batch: CandidateBatch,
    natives: pd.DataFrame,
    artifact: dict[str, np.ndarray],
) -> dict[str, Any]:
    generated = [_identity(lineup) for lineup in batch.candidates]
    result: dict[str, Any] = {
        "generated_candidates": len(generated),
        "mode": "bq-identities-and-artifact-totals",
    }
    artifact_n = int(np.asarray(artifact["cand_ix"]).shape[0])
    result["artifact_candidates"] = artifact_n
    if len(generated) != artifact_n:
        raise RuntimeError(
            f"ATLAS C control budget differs: generated {len(generated)} "
            f"vs artifact {artifact_n}"
        )
    totals = np.asarray(batch.candidate_totals, dtype=np.float64)
    artifact_totals = np.asarray(artifact["totals"], dtype=np.float64)
    if totals.shape != artifact_totals.shape:
        raise RuntimeError(
            f"ATLAS C control totals shape differs: {totals.shape} "
            f"vs {artifact_totals.shape}"
        )
    max_delta = float(np.abs(totals - artifact_totals).max())
    result["max_total_delta"] = max_delta
    if max_delta > 1e-6:
        raise RuntimeError(
            f"ATLAS C control world totals differ from the artifact "
            f"(max delta {max_delta})"
        )
    expected = _native_identities(natives)
    result["registered_candidates"] = len(expected)
    if generated != expected:
        first = next(
            (ix for ix, pair in enumerate(zip(generated, expected))
             if pair[0] != pair[1]),
            min(len(generated), len(expected)),
        )
        raise RuntimeError(
            "ATLAS C control does not reproduce the registered "
            f"natives (first divergence at candidate {first})"
        )
    return result


def _actual_parity(
    natives: pd.DataFrame, actuals: dict[str, float],
) -> float:
    worst = 0.0
    for _, row in natives.iterrows():
        values = list(row["players"]) if not isinstance(row["players"], str) \
            else [value for value in row["players"].split(",") if value]
        rebuilt = sum(actuals[str(value)] for value in values)
        worst = max(worst, abs(rebuilt - float(row["actual_score"])))
    if worst > 1e-9:
        raise RuntimeError(
            f"ATLAS C actual-score parity failed (max delta {worst})"
        )
    return worst


def _pool_diversity(batches: dict[str, CandidateBatch]) -> dict[str, Any]:
    from itertools import combinations

    pairs: set = set()
    cores: set = set()
    games: dict[tuple[str, ...], set] = {}
    identities: set = set()
    for batch in batches.values():
        for lineup in batch.candidates:
            identity = _identity(lineup)
            identities.add(identity)
            pairs.update(combinations(identity, 2))
            players = list(lineup.players)
            qb = next(
                row for row in players
                if str(row["pos"]).upper() == "QB"
            )
            teammates = sorted(
                str(row["id"]) for row in players
                if str(row["team"]) == str(qb["team"])
                and str(row["pos"]).upper() in {"RB", "WR", "TE"}
            )
            cores.update(
                (str(qb["id"]), *pair)
                for pair in combinations(teammates, 2)
            )
            counts: dict[str, int] = {}
            for row in players:
                counts[str(row["game_id"])] = counts.get(
                    str(row["game_id"]), 0) + 1
            dominant = max(counts.values())
            games.setdefault(identity, set()).add(dominant)
    dominant_counts = [max(values) for values in games.values()]
    return {
        "unique_candidates": len(identities),
        "pair_reach": len(pairs),
        "stack_core_reach": len(cores),
        "dominant_game_mean": float(np.mean(dominant_counts)),
    }


def _score_books(
    batches: dict[str, CandidateBatch],
    actuals: dict[str, float],
) -> dict[str, Any]:
    pool_scores: list[float] = []
    seen: set = set()
    for batch in batches.values():
        for lineup in batch.candidates:
            identity = _identity(lineup)
            if identity in seen:
                continue
            seen.add(identity)
            pool_scores.append(
                sum(actuals[player] for player in identity)
            )
    scores = np.asarray(pool_scores, dtype=float)
    combined = combine_cbwu_books(
        batches, tuple(batches),
        expected_worlds_per_book=WORLDS_PER_ARTIFACT,
    )
    picked = select_tail_entries(
        combined.candidate_totals, 80, TAIL_LINE, env={"SELECT_LSE": "0"},
    )
    selected_scores = np.asarray([
        sum(actuals[player]
            for player in _identity(combined.candidates[index]))
        for index in picked
    ], dtype=float)
    if len(selected_scores) != 80:
        raise RuntimeError(
            f"ATLAS C exact-80 selection returned {len(selected_scores)}"
        )
    return {
        "c_score": float(scores.max()),
        "pool_unique": int(scores.size),
        "pool_mean": float(scores.mean()),
        "s_score": float(selected_scores.max()),
        "selected_mean": float(selected_scores.mean()),
        "thresholds": {
            str(line): int((scores >= line).sum())
            for line in (187, 194, 200, 210, 220, 230, 240)
        },
    }


def run(season: int, week: int, output_uri: str, smoke: bool) -> dict:
    validate_frozen_inputs()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not smoke and (
        not re.fullmatch(r"[0-9a-f]{40}", code_sha)
        or not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image)
    ):
        raise RuntimeError(
            "ATLAS C needs CODE_SHA and an immutable ANALYSIS_IMAGE"
        )
    from google.cloud import bigquery, storage

    from run_cbwu_seed_order_audit import (
        _download_artifact, _query, _upload_create_only,
    )

    grid = json.loads(SOURCE_GRID.read_text())
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    params = [
        bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(SOURCE_PANEL_IDS)),
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ]
    natives = _query(bq, NATIVE_SQL, params)
    snapshots = _query(bq, SNAPSHOT_SQL, params)

    receipt: dict[str, Any] = {
        "version": VERSION,
        "run_id": RUN_ID,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "image": image,
        "freeze_doc_sha256": FREEZE_DOC_SHA256,
        "source_grid_sha256": SOURCE_GRID_SHA256,
        "smoke": bool(smoke),
        "uses_realized_outcomes": not smoke,
        "production_change_licensed": False,
        "seeds": [],
    }
    control_batches: dict[str, CandidateBatch] = {}
    treatment_batches: dict[str, CandidateBatch] = {}
    recovery_slate = (season, week) == RECOVERY_CELL[1:]
    blocks = [0, 1, 2, 4] if recovery_slate else list(range(5))
    if recovery_slate:
        receipt["recovery_four_seed_slate"] = True
    for block in blocks:
        panel = SOURCE_PANEL_IDS[block]
        cell = _grid_cell(grid, panel, season, week)
        env = _generation_env(block, season, code_sha or "0" * 40)
        _validate_lever_env(cell, env)
        panel_natives = natives[
            natives.panel_run_id.astype(str).eq(panel)
        ].copy()
        if panel_natives.empty:
            raise RuntimeError(
                f"ATLAS C registered natives missing for {panel}"
            )
        snapshot = snapshots[
            snapshots.panel_run_id.astype(str).eq(panel)
        ].copy()
        if snapshot.empty:
            raise RuntimeError(f"ATLAS C snapshot missing for {panel}")
        artifact, art_receipt = _download_artifact(
            gcs, str(cell["score_artifact_uri"]),
            str(cell["score_artifact_sha256"]),
        )
        slate = _slate_frame(snapshot, np.asarray(artifact["player_ids"]))
        draws = np.asarray(artifact["player_draws"], dtype=np.float64)
        if draws.shape != (
            int((slate["draw_idx"] >= 0).sum()), WORLDS_PER_ARTIFACT,
        ):
            raise RuntimeError(
                f"ATLAS C artifact draw shape differs: {draws.shape}"
            )
        control = _generate(slate, draws, env, treatment=False)
        repro = _reproduction_check(control, panel_natives, artifact)
        treatment = _generate(slate, draws, env, treatment=True)
        if len(treatment.candidates) != len(control.candidates):
            raise RuntimeError(
                "ATLAS C arm budgets differ: control "
                f"{len(control.candidates)} vs treatment "
                f"{len(treatment.candidates)}"
            )
        control_batches[f"R{block}"] = control
        treatment_batches[f"R{block}"] = treatment
        receipt["seeds"].append({
            "block": block,
            "panel_run_id": panel,
            "projection_seed": SEED_PAIRS[block][0],
            "artifact": art_receipt,
            "reproduction": repro,
            "treatment_candidates": len(treatment.candidates),
        })

    receipt["control_diversity"] = _pool_diversity(control_batches)
    receipt["treatment_diversity"] = _pool_diversity(treatment_batches)
    if not smoke:
        # Outcome boundary: every validity gate above has passed for every
        # seed before either outcome query executes.
        native_actuals = _query(bq, NATIVE_ACTUALS_SQL, params)
        player_actuals = _query(bq, PLAYER_ACTUALS_SQL, params)
        if player_actuals.id.astype(str).duplicated().any():
            raise RuntimeError("ATLAS C player actuals are not unique")
        actuals = {
            str(row["id"]): float(row["actual"])
            for _, row in player_actuals.iterrows()
        }
        receipt["actual_parity_max_delta"] = _actual_parity(
            native_actuals, actuals,
        )
        receipt["control"] = _score_books(control_batches, actuals)
        receipt["treatment"] = _score_books(treatment_batches, actuals)
        receipt["paired_delta_c"] = (
            receipt["treatment"]["c_score"] - receipt["control"]["c_score"]
        )
        payload = json.dumps(
            receipt, sort_keys=True, separators=(",", ":"),
        ).encode()
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
            "ATLAS C output URI must live under the immutable run prefix"
        )
    receipt = run(args.season, args.week, args.output_uri, args.smoke)
    summary = {
        key: receipt.get(key)
        for key in (
            "run_id", "season", "week", "smoke", "paired_delta_c",
        )
    }
    summary["reproduction"] = [
        seed["reproduction"]["mode"] for seed in receipt["seeds"]
    ]
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
