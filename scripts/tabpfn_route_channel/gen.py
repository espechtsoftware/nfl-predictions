"""Generate the frozen current-stack Route marginal-channel cache pair."""

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
ARM = os.environ["TABPFN_ROUTE_CHANNEL_ARM"].strip()
OUTPUT_TABLE = os.environ["TABPFN_OUTPUT_TABLE"].strip()
CODE_SHA = os.environ.get("CODE_SHA", "").strip()

ARMS = {"control": False, "marginal": True}
TABLES = {
    "control": "tabpfn_route_channel_control_v1",
    "marginal": "tabpfn_route_channel_marginal_v1",
}
ROUTE_FEATURES = (
    "fp_route_share_last",
    "fp_route_share_l4",
    "fp_route_share_jump",
    "fp_route_cross_season",
)
TARGET_SEASONS = (2022, 2023, 2024, 2025)
POSITIONS = ("QB", "RB", "WR", "TE")
QUANTILES = (0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
             0.60, 0.70, 0.80, 0.90, 0.95, 0.99)
QUANTILE_COLUMNS = tuple(f"q{int(value * 100):02d}" for value in QUANTILES)
CONTEXT_MAX = 28_000
RANDOM_SEED = 7
N_ESTIMATORS = 4
EXPECTED_BASE_FEATURE_SHA = (
    "52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83"
)
EXPECTED_SOURCE_ROWS = 102_927
EXPECTED_SOURCE_CHECKSUM = 1_904_430_067_081_090_565
OUTPUT_PREFIX = "TABPFN_ROUTE_CHANNEL_JSON="


def _validate_environment() -> None:
    if ARM not in ARMS:
        raise ValueError(f"unknown TABPFN_ROUTE_CHANNEL_ARM={ARM!r}")
    if OUTPUT_TABLE != TABLES.get(ARM):
        raise ValueError(f"arm {ARM} requires TABPFN_OUTPUT_TABLE={TABLES.get(ARM)}")
    if not re.fullmatch(r"[0-9a-f]{7,40}", CODE_SHA):
        raise ValueError("CODE_SHA must be an immutable Git commit identity")
    forbidden = (
        "EXTRA_FEATURES", "DROP_FEATURES", "TABPFN_ACTIVE_LABEL_ARM",
        "TABPFN_COMPONENTS", "TABPFN_UPCOMING", "TABPFN_SEASONS",
        "TABPFN_WRITE",
    )
    active = [name for name in forbidden if os.environ.get(name, "").strip()]
    if active:
        raise ValueError(f"Route-channel cache has forbidden envs: {active}")


def _feature_contract() -> tuple[list[str], str, str]:
    path = Path("/app/features.txt")
    base_bytes = path.read_bytes()
    base_sha = hashlib.sha256(base_bytes).hexdigest()
    if base_sha != EXPECTED_BASE_FEATURE_SHA:
        raise ValueError("Route-channel baseline feature contract differs")
    baseline = path.read_text(encoding="utf-8").split()
    if len(baseline) != len(set(baseline)):
        raise ValueError("baseline TabPFN feature contract contains duplicates")
    effective = [*baseline, *(ROUTE_FEATURES if ARMS[ARM] else ())]
    if len(effective) != len(set(effective)):
        raise ValueError("Route-channel effective feature contract repeats fields")
    effective_bytes = (
        base_bytes if not ARMS[ARM]
        else base_bytes + b"\n" + "\n".join(ROUTE_FEATURES).encode("utf-8")
    )
    return sorted(effective), base_sha, hashlib.sha256(effective_bytes).hexdigest()


def _prepare(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    frame = frame[frame.position.isin(POSITIONS)].copy()
    frame["pos_code"] = frame.position.map(
        {position: index for index, position in enumerate(POSITIONS)})
    for column in (*feature_columns, "pos_code"):
        if column not in frame.columns:
            frame[column] = np.nan
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
    matrix = output[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
    if not np.isfinite(matrix).all():
        raise ValueError("TabPFN produced non-finite predictions")
    if np.any(np.diff(output[list(QUANTILE_COLUMNS)].to_numpy(float), axis=1) < -1e-8):
        raise ValueError("TabPFN produced unordered quantiles")
    audit = {
        "eligible_context_rows": int(eligible_rows),
        "sampled_context_rows": int(len(context)),
        "sampled_active_rows": int(context.was_active.fillna(False).sum()),
        "sampled_inactive_rows": int((~context.was_active.fillna(False)).sum()),
        "route_context_rows": int(
            context.fp_route_share_last.notna().sum()
            if "fp_route_share_last" in context else 0
        ),
        "route_target_rows": int(
            test.fp_route_share_last.notna().sum()
            if "fp_route_share_last" in test else 0
        ),
        "target_rows": int(len(test)),
    }
    return output, audit


def main() -> None:
    _validate_environment()
    feature_columns, base_feature_sha, feature_sha = _feature_contract()
    x_columns = [*feature_columns, "pos_code"]
    client = bigquery.Client(project=PROJECT)
    source_table = f"{PROJECT}.nfl_features.player_week_training"
    source_meta = client.get_table(source_table)
    panel = client.query(f"SELECT * FROM `{source_table}`").to_dataframe()
    required = {
        "season", "week", "gsis_id", "position", "was_active",
        "y_dk_points", *ROUTE_FEATURES,
    }
    if missing := required - set(panel.columns):
        raise ValueError(f"training panel lacks {sorted(missing)}")
    raw_rows = len(panel)
    source_checksum = int(client.query(f"""
        SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
        FROM `{source_table}` t
    """).to_dataframe().iloc[0]["checksum"])
    if raw_rows != EXPECTED_SOURCE_ROWS or source_checksum != EXPECTED_SOURCE_CHECKSUM:
        raise ValueError("Route-channel source snapshot differs from frozen source")
    schema_text = json.dumps(
        [(field.name, field.field_type, field.mode) for field in source_meta.schema],
        separators=(",", ":"),
    )
    source_schema_sha = hashlib.sha256(schema_text.encode()).hexdigest()
    panel = _prepare(panel, feature_columns)
    if panel.empty or panel.was_active.isna().any():
        raise ValueError("training panel activity provenance is incomplete")

    rng = np.random.default_rng(RANDOM_SEED)
    frames: list[pd.DataFrame] = []
    folds: dict[str, dict] = {}
    for season in TARGET_SEASONS:
        train = panel[
            (panel.season < season) & panel.y_dk_points.notna()
            & panel.was_active.astype(bool)
        ].copy()
        test = panel[panel.season == season].copy()
        if train.empty or test.empty:
            raise ValueError(f"empty context or target for {season}")
        started = time.time()
        predicted, audit = _fit_predict(train, test, x_columns, rng)
        audit["elapsed_seconds"] = float(time.time() - started)
        if audit["sampled_inactive_rows"] != 0:
            raise ValueError("Route-channel context retained an inactive label")
        frames.append(predicted)
        folds[str(season)] = audit
        print(
            f"{ARM} season {season}: context={audit['sampled_context_rows']:,} "
            f"route={audit['route_context_rows']:,} target={audit['target_rows']:,} "
            f"elapsed={audit['elapsed_seconds']:.0f}s",
            flush=True,
        )

    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("Route-channel cache target keys are not unique")
    combined["arm"] = ARM
    combined["active_context_only"] = True
    combined["route_marginal"] = ARMS[ARM]
    combined["base_feature_contract_sha256"] = base_feature_sha
    combined["feature_contract_sha256"] = feature_sha
    combined["code_sha"] = CODE_SHA
    destination = f"{PROJECT}.nfl_features.{OUTPUT_TABLE}"
    client.load_table_from_dataframe(
        combined,
        destination,
        job_config=bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_EMPTY,
        ),
    ).result()
    report = {
        "disposition": "tabpfn-route-channel-cache-generated",
        "arm": ARM,
        "active_context_only": True,
        "route_marginal": ARMS[ARM],
        "route_features": list(ROUTE_FEATURES),
        "code_sha": CODE_SHA,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "feature_columns": feature_columns,
        "base_feature_contract_sha256": base_feature_sha,
        "feature_contract_sha256": feature_sha,
        "target_seasons": list(TARGET_SEASONS),
        "quantiles": list(QUANTILES),
        "context_max": CONTEXT_MAX,
        "random_seed": RANDOM_SEED,
        "n_estimators": N_ESTIMATORS,
        "output_table": destination,
        "output_rows": int(len(combined)),
        "unique_keys": int(
            combined[["season", "week", "gsis_id"]].drop_duplicates().shape[0]
        ),
        "training_source": {
            "table": source_table,
            "last_modified": source_meta.modified.isoformat(),
            "schema_sha256": source_schema_sha,
            "content_checksum": source_checksum,
            "rows": raw_rows,
            "active_rows": int(panel.was_active.astype(bool).sum()),
            "inactive_zero_labels_by_season": {
                str(int(season)): int((
                    panel.season.eq(season)
                    & ~panel.was_active.astype(bool)
                    & panel.y_dk_points.eq(0)
                ).sum())
                for season in TARGET_SEASONS
            },
        },
        "folds": folds,
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
