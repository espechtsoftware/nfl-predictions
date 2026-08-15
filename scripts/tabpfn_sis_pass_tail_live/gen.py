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
    FEATURES as ARM_FEATURES,
    PROTOCOL_VERSION,
    TABLES,
    attach_target_context,
    build_target_context,
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
POSITIONS = ("QB", "RB", "WR", "TE")
QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
             0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
QUANTILE_COLUMNS = tuple(f"q{int(value * 100):02d}" for value in QUANTILES)
CONTEXT_MAX = 28_000
RANDOM_SEED = 7
N_ESTIMATORS = 4


def _validate_environment() -> tuple[int, int]:
    if ARM not in TABLES:
        raise ValueError(f"unknown live SIS pass-tail arm {ARM!r}")
    if OUTPUT_TABLE != TABLES[ARM]:
        raise ValueError(
            f"arm {ARM} requires TABPFN_OUTPUT_TABLE={TABLES[ARM]}"
        )
    if not re.fullmatch(r"[0-9a-f]{7,40}", CODE_SHA):
        raise ValueError("CODE_SHA must be an immutable Git commit identity")
    if TARGET == "auto":
        season, week = -1, -1
    else:
        if not re.fullmatch(r"\d{4}:\d{1,2}", TARGET):
            raise ValueError("TABPFN_UPCOMING must be season:week")
        season, week = (int(value) for value in TARGET.split(":"))
        if season != 2026 or not 1 <= week <= 18:
            raise ValueError("live SIS pass-tail v1 is frozen to 2026 Weeks 1-18")
    forbidden = (
        "EXTRA_FEATURES", "DROP_FEATURES", "TABPFN_COMPONENTS",
        "TABPFN_SEASONS", "TABPFN_WRITE",
    )
    if active := [name for name in forbidden if os.environ.get(name, "").strip()]:
        raise ValueError(f"live SIS pass-tail cache has forbidden envs: {active}")
    return season, week


def _resolve_auto_target(client: bigquery.Client) -> tuple[int, int]:
    rows = client.query(f"""
        SELECT DISTINCT CAST(season AS INT64) season, CAST(week AS INT64) week
        FROM `{PROJECT}.nfl_features.player_week_inference`
        WHERE season=2026
    """).to_dataframe()
    if len(rows) != 1:
        raise ValueError(
            "automatic live SIS pass-tail target requires exactly one 2026 "
            "inference season/week"
        )
    season, week = (int(value) for value in rows.iloc[0])
    if not 1 <= week <= 18:
        raise ValueError("automatic live SIS pass-tail target week is invalid")
    return season, week


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
    season, week = _validate_environment()
    client = bigquery.Client(project=PROJECT)
    if (season, week) == (-1, -1):
        season, week = _resolve_auto_target(client)
    training_table = f"{PROJECT}.nfl_features.player_week_training"
    inference_table = f"{PROJECT}.nfl_features.player_week_inference"
    sis_table = f"{PROJECT}.nfl_raw.sis_team_context_game"
    destination = f"{PROJECT}.nfl_features.{OUTPUT_TABLE}"
    base_bytes = Path("/app/features_control.txt").read_bytes()
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

    try:
        client.get_table(destination)
    except NotFound:
        pass
    else:
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
    client.load_table_from_dataframe(
        predicted,
        destination,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
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
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
