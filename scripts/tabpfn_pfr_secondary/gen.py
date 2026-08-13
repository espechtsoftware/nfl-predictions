"""Generate the frozen TabPFN PFR secondary-feature ablation caches."""

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


PROJECT = os.environ["GCP_PROJECT"]
ARM = os.environ["TABPFN_PFR_SECONDARY_ARM"].strip()
OUTPUT_TABLE = os.environ["TABPFN_OUTPUT_TABLE"].strip()
CODE_SHA = os.environ.get("CODE_SHA", "").strip()

RATE_FEATURES = (
    "cb_ypt_allowed_l6",
    "cb_comp_rate_allowed_l6",
    "db_ypt_allowed_l6",
)
TOP_CB_FEATURE = "top_cb_out"
ARM_DROPS = {
    "control": (),
    "drop_rates": RATE_FEATURES,
    "drop_top_cb": (TOP_CB_FEATURE,),
    "drop_all": (*RATE_FEATURES, TOP_CB_FEATURE),
}
TABLES = {
    arm: f"tabpfn_pfr_secondary_{arm}_v1" for arm in ARM_DROPS
}
TARGET_SEASONS = (2022, 2023, 2024, 2025)
POSITIONS = ("QB", "RB", "WR", "TE")
QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
             0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
QUANTILE_COLUMNS = tuple(f"q{int(value * 100):02d}" for value in QUANTILES)
CONTEXT_MAX = 28_000
RANDOM_SEED = 7
N_ESTIMATORS = 4
OUTPUT_PREFIX = "TABPFN_PFR_SECONDARY_JSON="


def _validate_environment() -> None:
    if ARM not in ARM_DROPS:
        raise ValueError(f"unknown TABPFN_PFR_SECONDARY_ARM={ARM!r}")
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
        raise ValueError(f"PFR secondary cache has forbidden envs: {active}")


def _feature_contract(path: Path, arm: str) -> tuple[list[str], str]:
    raw = path.read_bytes()
    listed = raw.decode("utf-8").split()
    if len(listed) != len(set(listed)):
        raise ValueError("control TabPFN feature contract contains duplicates")
    required = {*RATE_FEATURES, TOP_CB_FEATURE}
    if not required.issubset(listed):
        raise ValueError("control contract lacks a frozen PFR secondary feature")
    dropped = set(ARM_DROPS[arm])
    retained_in_source_order = [name for name in listed if name not in dropped]
    # The inherited control file intentionally has no terminal newline. Keep
    # that exact byte convention so CONTROL's hash equals the accepted v2
    # cache while treatment hashes represent only the declared subtraction.
    canonical = "\n".join(retained_in_source_order)
    feature_sha = hashlib.sha256(canonical.encode()).hexdigest()
    if arm == "control" and feature_sha != hashlib.sha256(raw).hexdigest():
        raise ValueError("control feature contract did not preserve inherited bytes")
    return sorted(retained_in_source_order), feature_sha


def _prepare(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    frame = frame[frame.position.isin(POSITIONS)].copy()
    frame["pos_code"] = frame.position.map(
        {position: index for index, position in enumerate(POSITIONS)})
    for column in (*features, "pos_code"):
        if column not in frame.columns:
            raise ValueError(f"training panel lacks {column}")
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
        "target_rows": int(len(test)),
    }


def main() -> None:
    _validate_environment()
    features, feature_sha = _feature_contract(
        Path("/app/features_control.txt"), ARM)
    x_columns = [*features, "pos_code"]
    client = bigquery.Client(project=PROJECT)
    source_table = f"{PROJECT}.nfl_features.player_week_training"
    source_meta = client.get_table(source_table)
    panel = client.query(f"SELECT * FROM `{source_table}`").to_dataframe()
    required = {
        "season", "week", "gsis_id", "position", "was_active",
        "y_dk_points", *features,
    }
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    panel = _prepare(panel, features)
    if panel.empty or panel.was_active.isna().any():
        raise ValueError("training panel activity provenance is incomplete")
    source_checksum = int(client.query(f"""
        SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
        FROM `{source_table}` t
    """).to_dataframe().iloc[0]["checksum"])
    schema_text = json.dumps(
        [(field.name, field.field_type, field.mode)
         for field in source_meta.schema], separators=(",", ":"))
    source_schema_sha = hashlib.sha256(schema_text.encode()).hexdigest()

    rng = np.random.default_rng(RANDOM_SEED)
    frames: list[pd.DataFrame] = []
    folds: dict[str, dict] = {}
    for season in TARGET_SEASONS:
        train = panel[
            (panel.season < season)
            & panel.y_dk_points.notna()
            & panel.was_active.astype(bool)
        ].copy()
        test = panel[panel.season == season].copy()
        if train.empty or test.empty:
            raise ValueError(f"empty context or target for {season}")
        started = time.time()
        predicted, audit = _fit_predict(train, test, x_columns, rng)
        audit["elapsed_seconds"] = float(time.time() - started)
        if audit["sampled_inactive_rows"]:
            raise ValueError("active-only context retained an inactive label")
        frames.append(predicted)
        folds[str(season)] = audit
        print(
            f"{ARM} season {season}: context={audit['sampled_context_rows']:,} "
            f"target={audit['target_rows']:,} "
            f"elapsed={audit['elapsed_seconds']:.0f}s", flush=True)

    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("PFR secondary cache target keys are not unique")
    combined["arm"] = ARM
    combined["label_law"] = "active_only"
    combined["feature_law"] = ARM
    combined["dropped_features"] = ",".join(ARM_DROPS[ARM])
    combined["feature_contract_sha256"] = feature_sha
    combined["code_sha"] = CODE_SHA
    destination = f"{PROJECT}.nfl_features.{OUTPUT_TABLE}"
    client.load_table_from_dataframe(
        combined, destination,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_EMPTY),
    ).result()
    report = {
        "disposition": "tabpfn-pfr-secondary-cache-generated",
        "arm": ARM,
        "label_law": "active_only",
        "feature_law": ARM,
        "dropped_features": list(ARM_DROPS[ARM]),
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
        "training_source": {
            "table": source_table,
            "last_modified": source_meta.modified.isoformat(),
            "schema_sha256": source_schema_sha,
            "content_checksum": source_checksum,
            "rows": int(len(panel)),
            "active_rows": int(panel.was_active.astype(bool).sum()),
        },
        "folds": folds,
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
