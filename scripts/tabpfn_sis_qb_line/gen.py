"""Generate the frozen strict-prior SIS QB line-context TabPFN cache pair."""

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

if os.environ.get("TABPFN_SIS_RB_RUNTAIL_ARM", "").strip():
    from sis_rb_runtail import (
        SIS_RB_RUNTAIL_FEATURES,
        SIS_SOURCE_RUN,
        SOURCE_HASH_COLUMNS,
        active_rb_coverage as active_coverage,
        attach_sis_rb_runtail as attach_features,
        build_strict_prior_sis_rb_runtail as build_strict_prior,
        feature_contract,
    )
    ARM_FEATURES = SIS_RB_RUNTAIL_FEATURES
    EXPERIMENT = "sis-rb-runtail"
    ARM_ENV = "TABPFN_SIS_RB_RUNTAIL_ARM"
    OUTPUT_PREFIX = "TABPFN_SIS_RB_RUNTAIL_JSON="
    COVERAGE_KEY = "active_rb_coverage"
    SUPPORT_STEM = "sis_rb_runtail"
    SIS_TABLE = "sis_team_run_context_game"
    TABLES = {
        "control": "tabpfn_sis_rb_runtail_control_v1",
        "treatment": "tabpfn_sis_rb_runtail_treatment_v1",
    }
elif os.environ.get("TABPFN_SIS_PASS_TAIL_ARM", "").strip():
    from sis_pass_tail import (
        SIS_PASS_TAIL_FEATURES,
        SIS_SOURCE_RUN,
        active_pass_tail_coverage as active_coverage,
        attach_sis_pass_tail as attach_features,
        build_strict_prior_sis_pass_tail as build_strict_prior,
        feature_contract,
    )
    ARM_FEATURES = SIS_PASS_TAIL_FEATURES
    SOURCE_HASH_COLUMNS = ()
    EXPERIMENT = "sis-pass-tail"
    ARM_ENV = "TABPFN_SIS_PASS_TAIL_ARM"
    OUTPUT_PREFIX = "TABPFN_SIS_PASS_TAIL_JSON="
    COVERAGE_KEY = "active_pass_tail_coverage"
    SUPPORT_STEM = "sis_pass_tail"
    SIS_TABLE = "sis_team_context_game"
    TABLES = {
        "control": "tabpfn_sis_pass_tail_control_v1",
        "treatment": "tabpfn_sis_pass_tail_treatment_v1",
    }
elif os.environ.get("TABPFN_SIS_RB_RDEF_ARM", "").strip():
    from sis_rb_rdef import (
        SIS_RB_FEATURE,
        SIS_SOURCE_RUN,
        SOURCE_HASH_COLUMNS,
        active_rb_coverage as active_coverage,
        attach_sis_rb_rdef as attach_features,
        build_strict_prior_sis_rb_rdef as build_strict_prior,
        feature_contract,
    )
    ARM_FEATURES = (SIS_RB_FEATURE,)
    EXPERIMENT = "sis-rb-rdef"
    ARM_ENV = "TABPFN_SIS_RB_RDEF_ARM"
    OUTPUT_PREFIX = "TABPFN_SIS_RB_RDEF_JSON="
    COVERAGE_KEY = "active_rb_coverage"
    SUPPORT_STEM = "sis_rb"
    SIS_TABLE = "sis_team_run_context_game"
    TABLES = {
        "control": "tabpfn_sis_rb_rdef_control_v1",
        "treatment": "tabpfn_sis_rb_rdef_treatment_v1",
    }
else:
    from sis_qb_line import (
        SIS_QB_FEATURES,
        SIS_SOURCE_RUN,
        active_qb_coverage as active_coverage,
        attach_sis_qb_line as attach_features,
        build_strict_prior_sis_qb_line as build_strict_prior,
        feature_contract,
    )
    ARM_FEATURES = SIS_QB_FEATURES
    SOURCE_HASH_COLUMNS = ()
    EXPERIMENT = "sis-qb-line"
    ARM_ENV = "TABPFN_SIS_QB_LINE_ARM"
    OUTPUT_PREFIX = "TABPFN_SIS_QB_LINE_JSON="
    COVERAGE_KEY = "active_qb_coverage"
    SUPPORT_STEM = "sis_qb"
    SIS_TABLE = "sis_team_context_game"
    TABLES = {
        "control": "tabpfn_sis_qb_line_control_v1",
        "treatment": "tabpfn_sis_qb_line_treatment_v1",
    }


PROJECT = os.environ["GCP_PROJECT"]
ARM = os.environ[ARM_ENV].strip()
OUTPUT_TABLE = os.environ["TABPFN_OUTPUT_TABLE"].strip()
CODE_SHA = os.environ.get("CODE_SHA", "").strip()

ARMS = ("control", "treatment")
TARGET_SEASONS = (2022, 2023, 2024, 2025)
POSITIONS = ("QB", "RB", "WR", "TE")
QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
             0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
QUANTILE_COLUMNS = tuple(f"q{int(value * 100):02d}" for value in QUANTILES)
CONTEXT_MAX = 28_000
RANDOM_SEED = 7
N_ESTIMATORS = 4


def _validate_environment() -> None:
    if ARM not in ARMS:
        raise ValueError(f"unknown {ARM_ENV}={ARM!r}")
    if OUTPUT_TABLE != TABLES[ARM]:
        raise ValueError(f"arm {ARM} requires TABPFN_OUTPUT_TABLE={TABLES[ARM]}")
    if not re.fullmatch(r"[0-9a-f]{7,40}", CODE_SHA):
        raise ValueError("CODE_SHA must be an immutable Git commit identity")
    other_arm_envs = [
        name for name in (
            "TABPFN_SIS_RB_RUNTAIL_ARM", "TABPFN_SIS_PASS_TAIL_ARM",
            "TABPFN_SIS_RB_RDEF_ARM", "TABPFN_SIS_QB_LINE_ARM",
        )
        if name != ARM_ENV and os.environ.get(name, "").strip()
    ]
    if other_arm_envs:
        raise ValueError(
            f"{EXPERIMENT} cache has competing arm envs: {other_arm_envs}")
    forbidden = (
        "EXTRA_FEATURES", "DROP_FEATURES", "TABPFN_COMPONENTS",
        "TABPFN_UPCOMING", "TABPFN_SEASONS", "TABPFN_WRITE",
    )
    active = [name for name in forbidden if os.environ.get(name, "").strip()]
    if active:
        raise ValueError(f"{EXPERIMENT} cache has forbidden envs: {active}")


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
        f"context_{SUPPORT_STEM}_supported": int(
            context[list(ARM_FEATURES)].notna().all(axis=1).sum()),
        "target_rows": int(len(test)),
        f"target_{SUPPORT_STEM}_supported": int(
            test[list(ARM_FEATURES)].notna().all(axis=1).sum()),
    }


def main() -> None:
    _validate_environment()
    base_path = Path("/app/features_control.txt")
    base_bytes = base_path.read_bytes()
    features = feature_contract(base_bytes.decode("utf-8").split(), ARM)
    feature_text = "\n".join(features) + "\n"
    feature_sha = hashlib.sha256(feature_text.encode()).hexdigest()
    x_columns = [*features, "pos_code"]

    client = bigquery.Client(project=PROJECT)
    source_table = f"{PROJECT}.nfl_features.player_week_training"
    sis_table = f"{PROJECT}.nfl_raw.{SIS_TABLE}"
    source_meta = client.get_table(source_table)
    sis_meta = client.get_table(sis_table)
    panel = client.query(f"SELECT * FROM `{source_table}`").to_dataframe()
    sis = client.query(f"SELECT * FROM `{sis_table}`").to_dataframe()
    source_rows = len(panel)
    strict_prior = build_strict_prior(sis)
    panel = attach_features(panel, strict_prior)
    if len(panel) != source_rows:
        raise ValueError(f"{EXPERIMENT} join changed training-panel row count")
    required = {
        "season", "week", "gsis_id", "position", "was_active",
        "y_dk_points", *ARM_FEATURES, *features,
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
    sis_schema = json.dumps(
        [(field.name, field.field_type, field.mode)
         for field in sis_meta.schema], separators=(",", ":"))

    active_only = True
    rng = np.random.default_rng(RANDOM_SEED)
    frames: list[pd.DataFrame] = []
    folds: dict[str, dict] = {}
    for season in TARGET_SEASONS:
        train = panel[(panel.season < season) & panel.y_dk_points.notna()].copy()
        unfiltered_inactive = int((~train.was_active.astype(bool)).sum())
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
            raise ValueError(f"active-only {EXPERIMENT} context retained inactive labels")
        frames.append(predicted)
        folds[str(season)] = audit
        print(
            f"{ARM}/active_only/base season {season}: "
            f"context={audit['sampled_context_rows']:,} "
            f"target={audit['target_rows']:,} "
            f"elapsed={audit['elapsed_seconds']:.0f}s", flush=True)

    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError(f"{EXPERIMENT} cache target keys are not unique")
    combined["arm"] = ARM
    combined["label_law"] = "active_only"
    combined["feature_law"] = "base"
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
        "disposition": f"tabpfn-{EXPERIMENT}-cache-generated",
        "arm": ARM,
        "label_law": "active_only",
        "feature_law": "base",
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
        COVERAGE_KEY: active_coverage(panel),
        "training_source": {
            "table": source_table,
            "last_modified": source_meta.modified.isoformat(),
            "schema_sha256": hashlib.sha256(source_schema.encode()).hexdigest(),
            "content_checksum": checksum(source_table),
            "rows": int(source_rows),
            "active_rows": int(panel.was_active.astype(bool).sum()),
        },
        "sis_source": {
            "table": sis_table,
            "last_modified": sis_meta.modified.isoformat(),
            "schema_sha256": hashlib.sha256(sis_schema.encode()).hexdigest(),
            "content_checksum": checksum(sis_table),
            "rows": int(len(sis)),
            "source_run_ids": sorted(sis.source_run_id.dropna().unique().tolist()),
            "expected_source_run": SIS_SOURCE_RUN,
            "source_hash_identities": {
                column: sorted(sis[column].dropna().astype(str).unique().tolist())
                for column in SOURCE_HASH_COLUMNS
            },
        },
        "folds": folds,
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
