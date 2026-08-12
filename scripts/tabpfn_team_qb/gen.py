"""Generate the frozen strict-prior team-QB-quality TabPFN cache pair."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from google.cloud import bigquery
from tabpfn import TabPFNRegressor

from team_qb import (
    TEAM_QB_FEATURE,
    broadcast_team_qb_quality,
    feature_contract,
    feature_coverage,
    qb_ngs_support,
)


PROJECT = os.environ["GCP_PROJECT"]
ARM = os.environ["TABPFN_TEAM_QB_ARM"].strip()
LABEL_LAW = os.environ["TABPFN_TEAM_QB_LABEL_LAW"].strip()
FEATURE_LAW = os.environ["TABPFN_TEAM_QB_FEATURE_LAW"].strip()
OUTPUT_TABLE = os.environ["TABPFN_OUTPUT_TABLE"].strip()
CODE_SHA = os.environ.get("CODE_SHA", "").strip()

ARMS = ("control", "treatment")
LABEL_LAWS = {"current": False, "active_only": True}
FEATURE_LAWS = ("base", "sched")
TABLES = {
    "control": "tabpfn_team_qb_control_v1",
    "treatment": "tabpfn_team_qb_treatment_v1",
}
TARGET_SEASONS = (2022, 2023, 2024, 2025)
CANONICAL_WARMUP_SEASONS = (2019, 2021)
POSITIONS = ("QB", "RB", "WR", "TE")
QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
             0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
QUANTILE_COLUMNS = tuple(f"q{int(value * 100):02d}" for value in QUANTILES)
CONTEXT_MAX = 28_000
RANDOM_SEED = 7
N_ESTIMATORS = 4
OUTPUT_PREFIX = "TABPFN_TEAM_QB_JSON="


def _validate_environment() -> None:
    if ARM not in ARMS:
        raise ValueError(f"unknown TABPFN_TEAM_QB_ARM={ARM!r}")
    if LABEL_LAW not in LABEL_LAWS:
        raise ValueError(f"unknown TABPFN_TEAM_QB_LABEL_LAW={LABEL_LAW!r}")
    if FEATURE_LAW not in FEATURE_LAWS:
        raise ValueError(f"unknown TABPFN_TEAM_QB_FEATURE_LAW={FEATURE_LAW!r}")
    if OUTPUT_TABLE != TABLES[ARM]:
        raise ValueError(f"arm {ARM} requires TABPFN_OUTPUT_TABLE={TABLES[ARM]}")
    if not re.fullmatch(r"[0-9a-f]{7,40}", CODE_SHA):
        raise ValueError("CODE_SHA must be an immutable Git commit identity")
    forbidden = (
        "EXTRA_FEATURES", "DROP_FEATURES", "TABPFN_COMPONENTS",
        "TABPFN_UPCOMING", "TABPFN_SEASONS", "TABPFN_WRITE",
    )
    active = [name for name in forbidden if os.environ.get(name, "").strip()]
    if active:
        raise ValueError(f"team-QB cache has forbidden envs: {active}")


def _prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    frame = frame[frame.position.isin(POSITIONS)].copy()
    frame["pos_code"] = frame.position.map(
        {position: index for index, position in enumerate(POSITIONS)})
    for column in (*features, "pos_code"):
        frame[column] = pd.to_numeric(
            frame[column], errors="coerce").astype("float64")
    return frame


def _fit_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    x_columns: list[str],
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, dict]:
    eligible_rows = len(train)
    if eligible_rows > CONTEXT_MAX:
        indices = rng.choice(eligible_rows, CONTEXT_MAX, replace=False)
        train = train.iloc[indices]
    context = train.reset_index(drop=True)
    estimator = TabPFNRegressor(
        device="cuda" if torch.cuda.is_available() else "cpu",
        n_estimators=N_ESTIMATORS,
        ignore_pretraining_limits=True,
        random_state=RANDOM_SEED,
    )
    estimator.fit(
        context[x_columns].to_numpy(np.float32),
        context.y_dk_points.to_numpy(np.float32),
    )
    predicted_quantiles = estimator.predict(
        test[x_columns].to_numpy(np.float32),
        output_type="quantiles",
        quantiles=list(QUANTILES),
    )
    predicted_mean = estimator.predict(test[x_columns].to_numpy(np.float32))
    output = test[["season", "week", "gsis_id"]].copy()
    output["mean"] = np.asarray(predicted_mean, dtype=float)
    for column, values in zip(QUANTILE_COLUMNS, predicted_quantiles):
        output[column] = np.maximum(np.asarray(values, dtype=float), 0.0)
    values = output[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("TabPFN produced non-finite predictions")
    if np.any(np.diff(output[list(QUANTILE_COLUMNS)].to_numpy(float), axis=1)
              < -1e-8):
        raise ValueError("TabPFN produced unordered quantiles")
    return output, {
        "eligible_context_rows": int(eligible_rows),
        "sampled_context_rows": int(len(context)),
        "sampled_active_rows": int(context.was_active.fillna(False).sum()),
        "sampled_inactive_rows": int((~context.was_active.fillna(False)).sum()),
        "context_team_qb_supported": int(
            context[TEAM_QB_FEATURE].notna().sum()),
        "target_rows": int(len(test)),
        "target_team_qb_supported": int(test[TEAM_QB_FEATURE].notna().sum()),
    }


def _advance_inherited_rng(panel: pd.DataFrame, rng: np.random.Generator) -> dict:
    """Match the current-label canonical generator's pre-2022 RNG state."""
    audit = {}
    if LABEL_LAW != "current":
        return audit
    for season in CANONICAL_WARMUP_SEASONS:
        train = panel[(panel.season < season) & panel.y_dk_points.notna()]
        if train.empty or panel[panel.season.eq(season)].empty:
            raise ValueError(f"canonical RNG warm-up lacks season {season}")
        sampled = len(train)
        if len(train) > CONTEXT_MAX:
            rng.choice(len(train), CONTEXT_MAX, replace=False)
            sampled = CONTEXT_MAX
        audit[str(season)] = {
            "eligible_context_rows": int(len(train)),
            "sampled_context_rows": int(sampled),
        }
    return audit


def main() -> None:
    _validate_environment()
    base_path = Path("/app/features_control.txt")
    base_bytes = base_path.read_bytes()
    features = feature_contract(
        base_bytes.decode("utf-8").split(), FEATURE_LAW, ARM)
    feature_text = "\n".join(features) + "\n"
    feature_sha = hashlib.sha256(feature_text.encode()).hexdigest()
    x_columns = [*features, "pos_code"]

    client = bigquery.Client(project=PROJECT)
    source_table = f"{PROJECT}.nfl_features.player_week_training"
    quality_table = f"{PROJECT}.nfl_features.team_week_qb_quality"
    source_meta = client.get_table(source_table)
    quality_meta = client.get_table(quality_table)
    panel = client.query(f"SELECT * FROM `{source_table}`").to_dataframe()
    quality = client.query(f"SELECT * FROM `{quality_table}`").to_dataframe()
    source_rows = len(panel)
    panel = broadcast_team_qb_quality(panel, quality)
    if len(panel) != source_rows:
        raise ValueError("team-QB join changed training-panel row count")
    required = {
        "season", "week", "gsis_id", "position", "was_active",
        "y_dk_points", "qb_cpoe_l6", *features,
    }
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    panel = _prepare(panel, features)
    if panel.empty or panel.was_active.isna().any():
        raise ValueError("training panel activity provenance is incomplete")

    def checksum(table: str) -> int:
        value = client.query(f"""
            SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
            FROM `{table}` t
        """).to_dataframe().iloc[0]["checksum"]
        return int(value)

    source_schema = json.dumps(
        [(field.name, field.field_type, field.mode)
         for field in source_meta.schema], separators=(",", ":"))
    quality_schema = json.dumps(
        [(field.name, field.field_type, field.mode)
         for field in quality_meta.schema], separators=(",", ":"))

    active_only = LABEL_LAWS[LABEL_LAW]
    rng = np.random.default_rng(RANDOM_SEED)
    inherited_rng_warmup = _advance_inherited_rng(panel, rng)
    frames: list[pd.DataFrame] = []
    folds: dict[str, dict] = {}
    for season in TARGET_SEASONS:
        train = panel[(panel.season < season) & panel.y_dk_points.notna()].copy()
        unfiltered_inactive = int((~train.was_active.astype(bool)).sum())
        if active_only:
            train = train[train.was_active.astype(bool)].copy()
        test = panel[panel.season.eq(season)].copy()
        if train.empty or test.empty:
            raise ValueError(f"empty context or target for {season}")
        started = time.time()
        predicted, audit = _fit_predict(train, test, x_columns, rng)
        audit.update({
            "unfiltered_inactive_labels": unfiltered_inactive,
            "elapsed_seconds": float(time.time() - started),
        })
        if active_only and audit["sampled_inactive_rows"]:
            raise ValueError("active-only team-QB context retained inactive labels")
        frames.append(predicted)
        folds[str(season)] = audit
        print(
            f"{ARM}/{LABEL_LAW}/{FEATURE_LAW} season {season}: "
            f"context={audit['sampled_context_rows']:,} "
            f"target={audit['target_rows']:,} "
            f"elapsed={audit['elapsed_seconds']:.0f}s", flush=True)

    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("team-QB cache target keys are not unique")
    combined["arm"] = ARM
    combined["label_law"] = LABEL_LAW
    combined["feature_law"] = FEATURE_LAW
    combined["active_context_only"] = active_only
    combined["feature_contract_sha256"] = feature_sha
    combined["code_sha"] = CODE_SHA
    destination = f"{PROJECT}.nfl_features.{OUTPUT_TABLE}"
    client.load_table_from_dataframe(
        combined, destination,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_EMPTY),
    ).result()
    report = {
        "disposition": "tabpfn-team-qb-cache-generated",
        "arm": ARM,
        "label_law": LABEL_LAW,
        "feature_law": FEATURE_LAW,
        "active_context_only": active_only,
        "code_sha": CODE_SHA,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "feature_columns": features,
        "feature_contract_sha256": feature_sha,
        "target_seasons": list(TARGET_SEASONS),
        "quantiles": list(QUANTILES),
        "context_max": CONTEXT_MAX,
        "random_seed": RANDOM_SEED,
        "n_estimators": N_ESTIMATORS,
        "output_table": destination,
        "output_rows": int(len(combined)),
        "unique_keys": int(combined[[
            "season", "week", "gsis_id"
        ]].drop_duplicates().shape[0]),
        "team_qb_coverage": feature_coverage(panel),
        "existing_qb_cpoe_support": qb_ngs_support(panel),
        "training_source": {
            "table": source_table,
            "last_modified": source_meta.modified.isoformat(),
            "schema_sha256": hashlib.sha256(source_schema.encode()).hexdigest(),
            "content_checksum": checksum(source_table),
            "rows": int(source_rows),
            "active_rows": int(panel.was_active.astype(bool).sum()),
        },
        "team_qb_source": {
            "table": quality_table,
            "last_modified": quality_meta.modified.isoformat(),
            "schema_sha256": hashlib.sha256(quality_schema.encode()).hexdigest(),
            "content_checksum": checksum(quality_table),
            "rows": int(len(quality)),
        },
        "folds": folds,
        "inherited_rng_warmup": inherited_rng_warmup,
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
