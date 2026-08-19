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

import sys as _sys
from pathlib import Path as _Path
# Script-to-script imports need scripts/ on sys.path under BOTH
# invocation modes: as a file (parent dir) and as injected -c
# source (cwd-relative scripts/).
_scripts_dir = (_Path(__file__).parent if "__file__" in globals()
                else _Path("scripts"))
_sys.path.insert(0, str(_scripts_dir.resolve()))

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
    "ba2f04984cfaa96dd0e21d7488e5b575704f03cd26277c4a717c2d1d64f7405c"
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
# Amendment 3 (2026-08-18 smoke disposition): the source money-world
# panels were TRUE-80 replays — generation basis 80 entries (160 lev
# candidates at CAND_MULT=2; the coherent support census records exactly
# 160 leverage candidates per cell). The original freeze passed 40,
# silently halving the lev family (smoke #3: natives 255 vs regenerated
# 164 + injected 12). The reproduction gate remains the arbiter.
N_ENTRIES = 80
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
    # Values may contain commas (ROLE_BELIEF_FEATURES,
    # SERVED_POSITION_SCALES); split only where a new KEY= begins.
    recorded = dict(
        item.split("=", 1)
        for item in re.split(r",(?=[A-Z][A-Z0-9_]*=)", str(cell["lever_env"]))
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
    """Reconstruct the generation slate: ALL rows in artifact order with
    draw_idx = 0..n-1.

    The pinned money-world artifacts store the complete generation slate
    — skill AND DST rows, DST draws being the constant projection
    broadcast (asserted where draws are in scope). The original freeze
    assumed skill-only artifacts and failed closed on first contact with
    a real artifact (2023 W1 R0: 756 skill + 17 DST rows). Amendment
    record: reports/2026-08-18-atlas-minimal-c-smoke-disposition.md; the
    exact native-reproduction gate remains the arbiter of faithfulness.
    """
    frame = snapshot.copy()
    frame["id"] = frame["id"].astype(str)
    if frame["id"].duplicated().any():
        raise RuntimeError("ATLAS C snapshot has duplicate player ids")
    catalog = frame.set_index("id", drop=False)
    ids = [str(value) for value in player_ids]
    if len(set(ids)) != len(ids):
        raise RuntimeError("ATLAS C artifact ids repeat")
    missing = set(ids) - set(catalog.index)
    if missing:
        raise RuntimeError(
            f"ATLAS C artifact players missing from snapshot: "
            f"{sorted(missing)[:5]}"
        )
    leftover = catalog[~catalog.index.isin(ids)]
    if len(leftover):
        raise RuntimeError(
            "ATLAS C snapshot rows absent from the artifact: "
            f"{sorted(leftover['id'].astype(str))[:5]}"
        )
    slate = catalog.loc[ids].reset_index(drop=True)
    if not (slate["pos"].astype(str).str.upper() == "DST").any():
        raise RuntimeError("ATLAS C artifact carries no DST rows")
    slate["draw_idx"] = np.arange(len(slate), dtype=int)
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
    # Amendment 2 (2026-08-18 smoke disposition): the production role
    # family requires the role registry's belief slate/draws, which are
    # not reconstructible from the pinned artifacts. Role candidates are
    # arm-invariant by code (role generation never reads the boom world
    # ranking), so generation runs with the role dose at zero and the
    # registered role natives are injected verbatim afterwards
    # (_inject_role_natives). The acquisition-record env validation is
    # unchanged and still checks the FAITHFUL environment.
    run_env["N_EPISTEMIC"] = "0"
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


def _inject_role_natives(
    batch: CandidateBatch,
    natives: pd.DataFrame,
    slate: pd.DataFrame,
    artifact: dict[str, np.ndarray],
) -> CandidateBatch:
    """Splice the registered role natives into a regenerated batch.

    The role family is arm-invariant (its generation never reads the boom
    world ranking), so both arms receive the SAME registered role rosters
    at their registered cand_ix positions. Injected rows carry the
    artifact's own world totals verbatim — they are pinned inputs exactly
    like the draws — while every regenerated row must still reproduce
    independently under the unchanged exact gate. Player order follows
    the registered roster string so downstream recomputation stays
    bit-consistent. Any collision between an injected identity and a
    regenerated one fails closed (amendment record:
    reports/2026-08-18-atlas-minimal-c-smoke-disposition.md).
    """
    from nfl_dfs.optimizer.lineup import Lineup

    ordered = natives.sort_values("cand_ix", kind="stable")
    role_rows = ordered[ordered["tag"].astype(str).eq("epi")]
    if role_rows.empty:
        raise RuntimeError(
            "ATLAS C acquisition env carries a role dose but the panel "
            "registered no role natives")
    art_totals = np.asarray(artifact["totals"])
    record_by_id = {
        str(row["id"]): row for row in slate.to_dict("records")
    }
    regen_identities = {_identity(lineup) for lineup in batch.candidates}
    injected: dict[int, tuple[Lineup, np.ndarray]] = {}
    for _, row in role_rows.iterrows():
        roster = [
            value for value in str(row["players"]).split(",") if value
        ]
        if len(roster) != 9 or len(set(roster)) != 9:
            raise RuntimeError("ATLAS C role native is not nine unique ids")
        if tuple(sorted(roster)) in regen_identities:
            raise RuntimeError(
                "ATLAS C regenerated candidate collides with an injected "
                "role native; halt and disposition")
        missing = [pid for pid in roster if pid not in record_by_id]
        if missing:
            raise RuntimeError(
                f"ATLAS C role native players missing from slate: {missing}")
        index = int(row["cand_ix"])
        if not 0 <= index < len(art_totals):
            raise RuntimeError("ATLAS C role native cand_ix outside artifact")
        injected[index] = (
            Lineup(players=[record_by_id[pid] for pid in roster],
                   tag="epi"),
            art_totals[index],
        )
    native_order = ordered["cand_ix"].astype(int).tolist()
    if len(native_order) != len(batch.candidates) + len(injected):
        raise RuntimeError(
            "ATLAS C splice budget differs: natives "
            f"{len(native_order)} vs regenerated {len(batch.candidates)} "
            f"+ injected {len(injected)}")
    regen_iter = iter(zip(batch.candidates, batch.candidate_totals))
    final_candidates: list = []
    final_totals: list = []
    for index in native_order:
        if index in injected:
            lineup, totals_row = injected[index]
        else:
            lineup, totals_row = next(regen_iter)
        final_candidates.append(lineup)
        final_totals.append(np.asarray(totals_row))
    all_tags = {key: tuple(value) for key, value in batch.all_tags.items()}
    for lineup, _ in injected.values():
        all_tags.setdefault(lineup.ids, ("epi",))
    return CandidateBatch(
        candidates=tuple(final_candidates),
        candidate_totals=np.stack(final_totals),
        player_ids=batch.player_ids,
        player_rows=batch.player_rows,
        row_draws=batch.row_draws,
        all_tags=all_tags,
        metadata={
            **dict(batch.metadata),
            "role_injection": {
                "mode": "verbatim-registered-arm-invariant",
                "count": len(injected),
                "cand_ix": sorted(injected),
            },
        },
    )


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
        # DST rows must carry the constant projection broadcast the
        # source panel generated with — any variance means this is not
        # the pinned law (amendment record: smoke disposition, 2026-08-18).
        dst_mask = slate["pos"].astype(str).str.upper().eq("DST").to_numpy()
        if float(draws[dst_mask].std(axis=1).max()) != 0.0:
            raise RuntimeError("ATLAS C DST artifact rows are not constant")
        control = _inject_role_natives(
            _generate(slate, draws, env, treatment=False),
            panel_natives, slate, artifact)
        repro = _reproduction_check(control, panel_natives, artifact)
        treatment = _inject_role_natives(
            _generate(slate, draws, env, treatment=True),
            panel_natives, slate, artifact)
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
            "role_injected": control.metadata.get("role_injection", {}).get(
                "count"),
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
