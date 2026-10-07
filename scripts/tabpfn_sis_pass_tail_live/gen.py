"""Generate one prospective target-week SIS pass-tail TabPFN cache arm."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from tabpfn import TabPFNRegressor

from live_shadow import (
    BASE_FEATURES_SHA256,
    CACHE_SETTINGS,
    CONTRACT,
    PROTOCOL_VERSION,
    TABLES,
    attach_target_context,
    attach_target_salary,
    build_target_context,
    cache_table,
    check_job_contract,
    require_complete_source_window,
    resolve_auto_target,
)
from sis_pass_tail import (
    attach_sis_pass_tail,
    build_strict_prior_sis_pass_tail,
    feature_contract,
)


PROJECT = os.environ["GCP_PROJECT"]
ARM = os.environ["TABPFN_SIS_PASS_TAIL_LIVE_ARM"].strip()
OUTPUT_TABLE = os.environ["TABPFN_OUTPUT_TABLE"].strip()
TARGET = os.environ.get("TABPFN_UPCOMING", "auto").strip().lower() or "auto"
CODE_SHA = os.environ.get("CODE_SHA", "").strip().lower()
OUTPUT_PREFIX = "TABPFN_SIS_PASS_TAIL_LIVE_JSON="
# Settings come from the declared contract (live_shadow.CACHE_SETTINGS).
POSITIONS = tuple(CACHE_SETTINGS["positions"])
QUANTILES = tuple(CACHE_SETTINGS["quantiles"])
QUANTILE_COLUMNS = tuple(f"q{int(value * 100):02d}" for value in QUANTILES)
CONTEXT_MAX = int(CACHE_SETTINGS["context_max"])
RANDOM_SEED = int(CACHE_SETTINGS["random_seed"])
N_ESTIMATORS = int(CACHE_SETTINGS["n_estimators"])


def _validate_environment() -> tuple[dict, int, int]:
    if ARM not in TABLES:
        raise ValueError(f"unknown live SIS pass-tail arm {ARM!r}")
    # The declared contract first: arm, live table name, target rule, no default.
    receipt = check_job_contract(os.environ, f"cache-{ARM}")
    if OUTPUT_TABLE != TABLES[ARM]:
        raise ValueError(
            f"arm {ARM} requires TABPFN_OUTPUT_TABLE={TABLES[ARM]}"
        )
    if not re.fullmatch(r"[0-9a-f]{7,40}", CODE_SHA):
        raise ValueError("CODE_SHA must be an immutable Git commit identity")
    if TARGET != "auto":
        raise ValueError(f"contract {CONTRACT} requires TABPFN_UPCOMING=auto")
    forbidden = (
        "EXTRA_FEATURES", "DROP_FEATURES", "TABPFN_COMPONENTS",
        "TABPFN_SEASONS", "TABPFN_WRITE",
    )
    if active := [name for name in forbidden if os.environ.get(name, "").strip()]:
        raise ValueError(f"live SIS pass-tail cache has forbidden envs: {active}")
    return receipt, -1, -1


def _schedule(client: bigquery.Client, season: int) -> pd.DataFrame:
    return client.query(f"""
        SELECT season, week, game_type, gameday, home_team, away_team
        FROM `{PROJECT}.nfl_raw.schedules`
        WHERE season=@season AND game_type='REG'
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("season", "INT64", season),
    ])).to_dataframe()


def _resolve_auto_target(client: bigquery.Client) -> tuple[int, int]:
    # The paired job resolves its target from the schedule (tail_shadow's
    # upcoming_season_week); the cache must name the same week.
    upcoming = client.query(f"""
        SELECT MIN(week) AS week FROM `{PROJECT}.nfl_raw.schedules`
        WHERE season=2026 AND game_type='REG'
          AND gameday >= CAST(CURRENT_DATE() AS STRING)
    """).to_dataframe().iloc[0].week
    if pd.isna(upcoming):
        raise ValueError("no upcoming 2026 regular-season week in schedules")
    # Bye weeks (2026-10-07, O-41): player_week_inference holds each team's
    # NEXT game, so a team on bye in the upcoming week carries the week after
    # it (Week 5: CAR / KC on Week 6). Only the teams that play the upcoming
    # week name the inference week; a stale table (a playing team still on an
    # earlier week) still fails closed in resolve_auto_target.
    rows = client.query(f"""
        SELECT DISTINCT CAST(i.season AS INT64) season, CAST(i.week AS INT64) week
        FROM `{PROJECT}.nfl_features.player_week_inference` i
        WHERE i.season=2026 AND i.team IN (
          SELECT team FROM `{PROJECT}.nfl_raw.schedules` s,
            UNNEST([s.home_team, s.away_team]) AS team
          WHERE s.season=2026 AND s.game_type='REG' AND s.week=@upcoming)
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("upcoming", "INT64", int(upcoming)),
    ])).to_dataframe()
    return resolve_auto_target(
        zip(rows.season, rows.week), (2026, int(upcoming)))


def _checksum(client: bigquery.Client, table: str, where: str = "") -> int:
    value = client.query(f"""
        SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
        FROM `{table}` t {where}
    """).to_dataframe().iloc[0]["checksum"]
    return int(value or 0)


def _prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    frame = frame[frame.position.isin(POSITIONS)].copy()
    frame["pos_code"] = frame.position.map(
        {position: index for index, position in enumerate(POSITIONS)}
    )
    required = {*features, "pos_code"}
    if missing := required - set(frame.columns):
        raise ValueError(f"live SIS pass-tail panel lacks {sorted(missing)}")
    for column in required:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(
            "float64"
        )
    return frame


def _predict(
    train: pd.DataFrame, target: pd.DataFrame, x_columns: list[str],
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED)
    if len(train) > CONTEXT_MAX:
        train = train.iloc[rng.choice(len(train), CONTEXT_MAX, replace=False)]
    estimator = TabPFNRegressor(
        device="cuda" if torch.cuda.is_available() else "cpu",
        n_estimators=N_ESTIMATORS,
        ignore_pretraining_limits=True,
        random_state=RANDOM_SEED,
    )
    estimator.fit(
        train[x_columns].to_numpy(np.float32),
        train.y_dk_points.to_numpy(np.float32),
    )
    quantiles = estimator.predict(
        target[x_columns].to_numpy(np.float32),
        output_type="quantiles",
        quantiles=list(QUANTILES),
    )
    mean = estimator.predict(target[x_columns].to_numpy(np.float32))
    output = target[[
        "season", "week", "gsis_id", "sis_pass_tail_source_week_end",
        "sis_pass_tail_prior_games", "sis_pass_tail_supported",
    ]].copy()
    output["mean"] = np.asarray(mean, dtype=float)
    for column, values in zip(QUANTILE_COLUMNS, quantiles):
        output[column] = np.maximum(np.asarray(values, dtype=float), 0.0)
    values = output[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("live SIS pass-tail TabPFN produced non-finite values")
    if np.any(np.diff(output[list(QUANTILE_COLUMNS)].to_numpy(float), axis=1)
              < -1e-8):
        raise ValueError("live SIS pass-tail TabPFN produced unordered quantiles")
    return output


def main() -> None:
    contract, season, week = _validate_environment()
    dry_run = bool(contract["dry_run"])
    client = bigquery.Client(project=PROJECT)
    if (season, week) == (-1, -1):
        season, week = _resolve_auto_target(client)
    training_table = f"{PROJECT}.nfl_features.player_week_training"
    inference_table = f"{PROJECT}.nfl_features.player_week_inference"
    salary_table = f"{PROJECT}.nfl_features.dk_salary_week"
    sis_table = f"{PROJECT}.nfl_raw.sis_team_context_game"
    # A dry run writes only its own namespace, which no graded reader selects.
    destination = f"{PROJECT}.nfl_features.{cache_table(ARM, dry_run=dry_run)}"
    base_bytes = Path("/app/features_control.txt").read_bytes()
    if hashlib.sha256(base_bytes).hexdigest() != BASE_FEATURES_SHA256:
        raise ValueError("baseline feature contract differs from the declared contract")
    features = feature_contract(base_bytes.decode("utf-8").split(), ARM)
    feature_text = "\n".join(features) + "\n"
    feature_sha = hashlib.sha256(feature_text.encode()).hexdigest()
    x_columns = [*features, "pos_code"]

    panel = client.query(f"SELECT * FROM `{training_table}`").to_dataframe()
    target = client.query(f"""
        SELECT * FROM `{inference_table}`
        WHERE season=@season AND week=@week
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ])).to_dataframe()
    sis = client.query(f"SELECT * FROM `{sis_table}`").to_dataframe()
    if target.empty:
        raise ValueError(f"live inference table has no {season} Week {week} rows")
    if target.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("live inference target repeats player keys")
    source_window = require_complete_source_window(
        sis, _schedule(client, season), season=season, week=week,
        dry_run=dry_run,
    )
    salaries = client.query(f"""
        SELECT gsis_id, season, week, salary FROM `{salary_table}`
        WHERE season=@season AND week=@week
    """, job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ])).to_dataframe()
    target, salary_audit = attach_target_salary(target, salaries)

    historical = build_strict_prior_sis_pass_tail(
        sis[pd.to_numeric(sis.season, errors="coerce").lt(season)].copy()
    )
    panel = attach_sis_pass_tail(panel, historical)
    target_context = build_target_context(
        sis,
        season=season,
        week=week,
        teams=target.opponent.dropna().astype(str),
    )
    if not target_context.sis_pass_tail_supported.all():
        missing = target_context.loc[
            ~target_context.sis_pass_tail_supported, "team"
        ].astype(str).tolist()
        raise ValueError(
            "live SIS pass-tail target lacks two-game support for "
            + ",".join(missing)
        )
    target = attach_target_context(target, target_context)
    panel = _prepare(panel, features)
    target = _prepare(target, features)
    train = panel[
        panel.y_dk_points.notna()
        & panel.was_active.fillna(False).astype(bool)
        & panel.season.lt(season)
    ].copy()
    if train.empty or target.empty:
        raise ValueError("live SIS pass-tail has empty context or target")
    predicted = _predict(train, target, x_columns)
    if predicted.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("live SIS pass-tail output repeats target keys")

    exists = True
    try:
        client.get_table(destination)
    except NotFound:
        exists = False
    if exists and not dry_run:
        count = int(client.query(f"""
            SELECT COUNT(*) AS n FROM `{destination}`
            WHERE season=@season AND week=@week
        """, job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("season", "INT64", season),
            bigquery.ScalarQueryParameter("week", "INT64", week),
        ])).to_dataframe().iloc[0].n)
        if count:
            raise ValueError(
                f"live SIS pass-tail cache already has {season} Week {week}"
            )

    training_checksum = _checksum(client, training_table)
    inference_checksum = _checksum(
        client, inference_table,
        f"WHERE season={season} AND week={week}",
    )
    sis_checksum = _checksum(
        client, sis_table,
        f"WHERE season={season} AND week < {week}",
    )
    generated_at = datetime.now(timezone.utc)
    source_run_ids = json.dumps(
        sorted(sis.loc[
            sis.season.eq(season) & sis.week.lt(week), "source_run_id"
        ].dropna().astype(str).unique().tolist()),
        separators=(",", ":"),
    )
    predicted["arm"] = ARM
    predicted["protocol_version"] = PROTOCOL_VERSION
    predicted["code_sha"] = CODE_SHA
    predicted["generated_at"] = generated_at
    predicted["feature_contract_sha256"] = feature_sha
    predicted["training_source_checksum"] = training_checksum
    predicted["inference_source_checksum"] = inference_checksum
    predicted["sis_source_checksum"] = sis_checksum
    predicted["sis_source_run_ids"] = source_run_ids
    predicted["contract"] = CONTRACT
    predicted["contract_settings_sha256"] = contract["settings_sha256"]
    predicted["dry_run"] = dry_run
    # Live: append-only, one previously absent week. Dry run: its own table,
    # replaced on every dry run (it holds only the latest one).
    client.load_table_from_dataframe(
        predicted,
        destination,
        job_config=bigquery.LoadJobConfig(
            write_disposition=(
                bigquery.WriteDisposition.WRITE_TRUNCATE if dry_run
                else bigquery.WriteDisposition.WRITE_APPEND
            ),
        ),
    ).result()
    report = {
        "disposition": "prospective-sis-pass-tail-cache-generated",
        "protocol_version": PROTOCOL_VERSION,
        "arm": ARM,
        "season": season,
        "week": week,
        "code_sha": CODE_SHA,
        "output_table": destination,
        "output_rows": int(len(predicted)),
        "feature_columns": features,
        "feature_contract_sha256": feature_sha,
        "active_context_only": True,
        "context_rows": int(len(train)),
        "context_max": CONTEXT_MAX,
        "random_seed": RANDOM_SEED,
        "n_estimators": N_ESTIMATORS,
        "training_source_checksum": training_checksum,
        "inference_source_checksum": inference_checksum,
        "sis_source_checksum": sis_checksum,
        "sis_source_run_ids": json.loads(source_run_ids),
        "target_source_week_end": sorted(
            int(value) for value in target_context[
                "sis_pass_tail_source_week_end"
            ].dropna().unique()
        ),
        "generated_at": generated_at.isoformat(),
        "target_resolution": TARGET,
        "contract": CONTRACT,
        "contract_settings_sha256": contract["settings_sha256"],
        "dry_run": dry_run,
        "live": not dry_run,
        "source_window": source_window,
        "target_salary": salary_audit,
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
