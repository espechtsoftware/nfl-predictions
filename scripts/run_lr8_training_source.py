#!/usr/bin/env python3
"""Create-only, outcome-blind LR8 training-source runner.

``smoke`` is exactly 2019 week 1 / R0 and is successful only after its forty
exact DK-only optima and retained CBC evidence have been published.
``full-source`` is exactly the registered 35 slates and R0/R1. The CLI is
inert unless both the environment gate and ``--execute`` are explicit. Query
extracts are canonicalized, published create-only, generation-pinned,
reopened, and byte-verified before they may enter the replay adapter. No
realized lineup label is queried here.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Final

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nfl_dfs.models import components, featureset  # noqa: E402
from nfl_dfs.research import lr8_replay_source as replay_source  # noqa: E402
from nfl_dfs.research import lr8_training_source as training  # noqa: E402
from nfl_dfs.research import residual_world_columns as rw  # noqa: E402


ENABLED_ENV: Final = "LR8_TRAINING_SOURCE_ENABLED"
RUNNER_VERSION: Final = "lr8-training-source-runner-v1"
EXTRACT_VERSION: Final = "lr8-outcome-blind-bq-extract-v1"
SMOKE_SOLVE_FREEZE_VERSION: Final = "lr8-smoke-solve-freeze-v1"
PANEL_ID: Final = training.CANONICAL_PANEL_ID
MODEL_BOOST_ROUNDS: Final = replay_source.MODEL_BOOST_ROUNDS
TABPFN_TABLE_NAME: Final = "tabpfn_projections_pit_v2"
QUANTILE_COLUMNS: Final = (
    "q01", "q05", "q10", "q20", "q30", "q40", "q50",
    "q60", "q70", "q80", "q90", "q95", "q99",
)
MODEL_LABEL_COLUMNS: Final = (
    "y_carries", "y_interceptions", "y_pass_attempts", "y_pass_tds",
    "y_pass_yards", "y_rec_tds", "y_rec_yards", "y_receptions",
    "y_rush_tds", "y_rush_yards", "y_targets",
)
PIT_META_COLUMNS: Final = (
    "season", "week", "gsis_id", "position", "team",
    "opponent", "game_id", "salary", "injury_status", "is_rookie",
    "draft_round",
)


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


PIT_FEATURE_COLUMNS: Final = _unique(tuple(featureset.NUMERIC_FEATURES))
PIT_COLUMNS: Final = _unique((
    *PIT_META_COLUMNS,
    *PIT_FEATURE_COLUMNS,
    "was_active",
    *MODEL_LABEL_COLUMNS,
))
CATALOG_COLUMNS: Final = (
    "season", "week", "id", "gsis_id", "pos", "team", "opp",
    "game_id", "salary", "mean_projection",
)
INCUMBENT_COLUMNS: Final = ("season", "week", "cand_ix", "players")
CACHE_COLUMNS: Final = ("season", "week", "gsis_id", *QUANTILE_COLUMNS)
REPLAY_ENVIRONMENT: Final = {
    "MODEL_ENSEMBLE": "1",
    "MODEL_ENSEMBLE_MIX": "0",
    "TABPFN_COMPONENTS": "0",
    "TABPFN_MARGINALS": "1",
    "TABPFN_MARGINAL_TABLE": TABPFN_TABLE_NAME,
    "DRAFT_PRIORS": "0",
    "SIS_ASOE_TARGET_ALLOCATION": "0",
    "ENSEMBLE_WORLD_MODE": "",
    "EXTRA_FEATURES": "",
    "BIGPLAY": "0",
    "SIM_WIDEN_DRAWS": "fitted",
    "EMP_MARGINALS": "1",
    "SHAPE_MIX": "1",
    "SERVED_TAIL_SCALE": "1",
    "SERVED_POSITION_SCALES": "",
    "ROOKIE_WIDEN": "",
    "SCHAAKE_DIAG": "",
}
_TABLE_ID: Final = re.compile(
    r"[a-z][a-z0-9-]{4,62}\.[A-Za-z_][A-Za-z0-9_]*\."
    r"[A-Za-z_][A-Za-z0-9_]*"
)
_ATTEMPT_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,127}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_AUTO_SOLVER = object()


class LR8SourceRunnerError(RuntimeError):
    """Fail-closed source-runner contract violation."""


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    bq_type: str
    value: object
    array: bool = False


@dataclass(frozen=True, slots=True)
class QuerySpec:
    label: str
    sql: str
    parameters: tuple[Parameter, ...]
    job_id: str
    location: str
    query_sha256: str
    parameters_sha256: str


@dataclass(frozen=True, slots=True)
class PublishedObject:
    receipt: Mapping[str, object]
    reopened_raw: bytes
    created: bool


@dataclass(frozen=True, slots=True)
class RunnerConfig:
    mode: str
    attempt_id: str
    project: str
    bucket: str
    catalog_table: str
    candidate_table: str
    pit_table: str
    tabpfn_table: str
    location: str = "US"
    evidence_root: Path | None = None
    execute: bool = False
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return (
            f"gs://{self.bucket}/research/lr8-training-source/"
            f"{self.attempt_id}"
        )


@dataclass(frozen=True, slots=True)
class FittedModelBinding:
    """The exact fitted component model object that replay must reuse."""

    model: object
    model_sha256: str


QueryExecutor = Callable[[QuerySpec], tuple[pd.DataFrame, Mapping[str, object]]]
MetadataReader = Callable[[str], Mapping[str, object]]
Publisher = Callable[[str, bytes], PublishedObject]
ModelFitter = Callable[[pd.DataFrame, int], FittedModelBinding]


def _canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LR8SourceRunnerError("value is not canonical JSON") from exc


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _strict_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LR8SourceRunnerError(f"{label} must be a lowercase SHA-256")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8SourceRunnerError(f"{label} must be an exact integer")
    result = int(value)
    if result < minimum:
        raise LR8SourceRunnerError(f"{label} must be >= {minimum}")
    return result


def _exact_catalog_salary(value: object) -> int:
    """Return an exact positive DK salary without rounding source truth.

    ``slate_player_features.salary`` is a nullable BigQuery FLOAT column, so
    the BigQuery/pandas/JSON round trip truthfully yields floating scalars such
    as ``5500.0``.  Accept those only after proving that the finite stored
    value is mathematically integral.  Fractional values are never rounded;
    booleans, strings, nulls, non-finite values, and nonpositive values remain
    fatal at the source boundary.
    """
    if isinstance(value, (bool, np.bool_)):
        raise LR8SourceRunnerError(
            "canonical catalog salary must be a finite positive exact integer"
        )
    if isinstance(value, (int, np.integer)):
        result = int(value)
    elif isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number) or not number.is_integer():
            raise LR8SourceRunnerError(
                "canonical catalog salary must be a finite positive exact integer"
            )
        result = int(number)
        if number != result:
            raise LR8SourceRunnerError(
                "canonical catalog salary must be a finite positive exact integer"
            )
    else:
        raise LR8SourceRunnerError(
            "canonical catalog salary must be a finite positive exact integer"
        )
    if result <= 0:
        raise LR8SourceRunnerError(
            "canonical catalog salary must be a finite positive exact integer"
        )
    return result


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8SourceRunnerError(f"{label} must be a canonical string")
    return value


def _table(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _TABLE_ID.fullmatch(result) is None:
        raise LR8SourceRunnerError(f"{label} is not project.dataset.table")
    return result


def _json_value(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise LR8SourceRunnerError("query output mapping keys must be strings")
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_json_value(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return None
        if not math.isfinite(number):
            raise LR8SourceRunnerError("query output contains non-finite data")
        return number
    if isinstance(value, str):
        return value
    try:
        if bool(pd.isna(value)):
            return None
    except (TypeError, ValueError):
        pass
    raise LR8SourceRunnerError(
        f"query output type is not canonical JSON: {type(value).__name__}"
    )


def _frame_rows(
    frame: pd.DataFrame,
    *,
    columns: Sequence[str],
    sort_by: Sequence[str],
    label: str,
) -> list[dict[str, object]]:
    if not isinstance(frame, pd.DataFrame) or set(frame) != set(columns):
        raise LR8SourceRunnerError(f"{label} query columns differ")
    ordered = frame.loc[:, list(columns)].sort_values(
        list(sort_by), kind="mergesort"
    )
    return [
        {column: _json_value(value) for column, value in zip(
            columns, row, strict=True
        )}
        for row in ordered.itertuples(index=False, name=None)
    ]


def _sql_columns(alias: str, columns: Sequence[str]) -> str:
    return ",\n  ".join(f"{alias}.`{column}`" for column in columns)


def catalog_sql(table: str) -> str:
    source = _table(table, label="catalog table")
    return f"""SELECT
  p.season,
  p.week,
  p.id,
  IF(UPPER(p.pos) = 'DST', CAST(NULL AS STRING), p.id) AS gsis_id,
  p.pos,
  p.team,
  p.opp,
  p.game_id,
  p.salary,
  IF(UPPER(p.pos) = 'DST', p.proj, p.mean_projection) AS mean_projection
FROM `{source}` AS p
WHERE p.panel_run_id = @panel_id
  AND FORMAT('%d-%02d', p.season, p.week) IN UNNEST(@slate_keys)
ORDER BY p.season, p.week, p.id"""


def incumbent_sql(table: str) -> str:
    source = _table(table, label="candidate table")
    return f"""SELECT
  c.season,
  c.week,
  c.cand_ix,
  SPLIT(c.players, ',') AS players
FROM `{source}` AS c
WHERE c.panel_run_id = @panel_id
  AND FORMAT('%d-%02d', c.season, c.week) IN UNNEST(@slate_keys)
ORDER BY c.season, c.week, c.cand_ix"""


def pit_panel_sql(table: str, catalog_table: str) -> str:
    source = _table(table, label="PIT panel table")
    catalog = _table(catalog_table, label="catalog table")
    feature_columns = _unique((*PIT_META_COLUMNS, *PIT_FEATURE_COLUMNS))
    prior = _sql_columns("p", feature_columns)
    target = _sql_columns("t", feature_columns)
    prior_labels = ",\n  ".join(
        ["p.`was_active`", *[f"p.`{column}`" for column in MODEL_LABEL_COLUMNS]]
    )
    target_labels = ",\n  ".join([
        "CAST(NULL AS BOOL) AS was_active",
        *[
            f"CAST(NULL AS FLOAT64) AS {column}"
            for column in MODEL_LABEL_COLUMNS
        ],
    ])
    selected = ", ".join(f"`{column}`" for column in PIT_COLUMNS)
    return f"""WITH target_skill AS (
SELECT DISTINCT c.season, c.week, c.id AS gsis_id
FROM `{catalog}` AS c
WHERE c.panel_run_id = @panel_id
  AND UPPER(c.pos) != 'DST'
  AND FORMAT('%d-%02d', c.season, c.week) IN UNNEST(@slate_keys)
), mixed AS (
SELECT
  {prior},
  {prior_labels}
FROM `{source}` AS p
WHERE p.season IN UNNEST(@training_seasons)
UNION ALL
SELECT
  {target},
  {target_labels}
FROM `{source}` AS t
JOIN target_skill AS c
  USING (season, week, gsis_id)
WHERE t.season = @target_season
  AND t.week IN UNNEST(@target_weeks)
)
SELECT {selected}
FROM mixed
ORDER BY season, week, gsis_id"""


def tabpfn_sql(table: str, catalog_table: str) -> str:
    source = _table(table, label="TabPFN table")
    catalog = _table(catalog_table, label="catalog table")
    return f"""SELECT
  {_sql_columns('q', CACHE_COLUMNS)}
FROM `{source}` AS q
JOIN `{catalog}` AS c
  ON c.panel_run_id = @panel_id
 AND c.season = q.season
 AND c.week = q.week
 AND c.id = q.gsis_id
 AND UPPER(c.pos) != 'DST'
WHERE q.season = @target_season
  AND q.week IN UNNEST(@target_weeks)
  AND FORMAT('%d-%02d', q.season, q.week) IN UNNEST(@slate_keys)
ORDER BY q.season, q.week, q.gsis_id"""


def lattice(mode: str) -> tuple[tuple[int, tuple[int, ...], tuple[str, ...]], ...]:
    if mode == "smoke":
        return ((2019, (1,), ("R0",)),)
    if mode == "full-source":
        return tuple(
            (season, training.EXPECTED_WEEKS[season], training.BLOCK_ORDER)
            for season in training.TARGET_SEASONS
        )
    raise LR8SourceRunnerError("mode must be smoke or full-source")


def _slate_keys(plan: Sequence[tuple[int, Sequence[int], Sequence[str]]]) -> tuple[str, ...]:
    return tuple(
        f"{season}-{week:02d}"
        for season, weeks, _ in plan
        for week in weeks
    )


def _parameter_payload(values: Sequence[Parameter]) -> list[dict[str, object]]:
    output = []
    for value in values:
        name = _string(value.name, label="query parameter name")
        bq_type = _string(value.bq_type, label="query parameter type")
        output.append({
            "name": name,
            "type": bq_type,
            "array": value.array,
            "value": _json_value(value.value),
        })
    if len({row["name"] for row in output}) != len(output):
        raise LR8SourceRunnerError("query parameter names repeat")
    return output


def query_spec(
    *,
    label: str,
    sql: str,
    parameters: Sequence[Parameter],
    attempt_id: str,
    location: str,
) -> QuerySpec:
    name = _string(label, label="query label")
    raw_sql = _string(sql, label="query SQL")
    payload = _parameter_payload(parameters)
    query_digest = _sha(raw_sql.encode("utf-8"))
    parameter_digest = _sha(_canonical_json(payload))
    safe_attempt = attempt_id.replace("-", "_")[:48]
    safe_label = re.sub(r"[^a-z0-9_]", "_", name.lower())[:32]
    job_id = f"lr8_{safe_attempt}_{safe_label}_{query_digest[:12]}"
    return QuerySpec(
        label=name,
        sql=raw_sql,
        parameters=tuple(parameters),
        job_id=job_id,
        location=_string(location, label="BigQuery location"),
        query_sha256=query_digest,
        parameters_sha256=parameter_digest,
    )


def _validate_job_receipt(
    value: Mapping[str, object], spec: QuerySpec,
) -> dict[str, object]:
    expected = {
        "job_id", "location", "query_sha256", "parameters_sha256",
        "created", "started", "ended", "total_bytes_processed",
        "cache_hit", "error_result",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise LR8SourceRunnerError(f"{spec.label} query job receipt fields differ")
    result = dict(value)
    if (
        result["job_id"] != spec.job_id
        or result["location"] != spec.location
        or result["query_sha256"] != spec.query_sha256
        or result["parameters_sha256"] != spec.parameters_sha256
        or result["error_result"] is not None
    ):
        raise LR8SourceRunnerError(f"{spec.label} query job receipt differs")
    for field in ("created", "started", "ended"):
        _string(result[field], label=f"query job {field}")
    _exact_int(
        result["total_bytes_processed"],
        label="query total bytes processed",
    )
    if not isinstance(result["cache_hit"], bool):
        raise LR8SourceRunnerError("query cache_hit must be a literal bool")
    return result


def _validate_table_receipt(
    value: Mapping[str, object], *, table: str,
) -> dict[str, object]:
    expected = {"table_id", "etag", "modified", "num_rows", "schema_sha256"}
    if not isinstance(value, Mapping) or set(value) != expected:
        raise LR8SourceRunnerError("BigQuery table metadata fields differ")
    result = dict(value)
    if result["table_id"] != table:
        raise LR8SourceRunnerError("BigQuery table identity differs")
    _string(result["etag"], label="BigQuery table etag")
    _string(result["modified"], label="BigQuery table modified time")
    _exact_int(result["num_rows"], label="BigQuery table rows")
    _strict_sha(result["schema_sha256"], label="BigQuery schema hash")
    return result


def _extract_bytes(
    *,
    spec: QuerySpec,
    frame: pd.DataFrame,
    job_receipt: Mapping[str, object],
    table_receipts: Sequence[Mapping[str, object]],
    columns: Sequence[str],
    sort_by: Sequence[str],
) -> bytes:
    payload = {
        "schema": EXTRACT_VERSION,
        "label": spec.label,
        "query": {
            "sql_sha256": spec.query_sha256,
            "parameters": _parameter_payload(spec.parameters),
            "parameters_sha256": spec.parameters_sha256,
            "job_receipt": _validate_job_receipt(job_receipt, spec),
        },
        "tables": [dict(value) for value in table_receipts],
        "columns": list(columns),
        "rows": _frame_rows(
            frame, columns=columns, sort_by=sort_by, label=spec.label
        ),
    }
    payload["rows_sha256"] = _sha(_canonical_json(payload["rows"]))
    return _canonical_json(payload)


def _strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LR8SourceRunnerError(f"{label} is not JSON") from exc
    if not isinstance(value, dict) or _canonical_json(value) != raw:
        raise LR8SourceRunnerError(f"{label} is not canonical JSON")
    return value


def _published(
    value: PublishedObject,
    *,
    expected_uri: str,
    expected_raw: bytes,
    require_json: bool = True,
) -> tuple[dict[str, object], dict[str, object] | None]:
    if not isinstance(value, PublishedObject) or value.reopened_raw != expected_raw:
        raise LR8SourceRunnerError("create-only object reopen bytes differ")
    try:
        receipt = training._normalized_receipt(
            value.receipt, label="create-only object receipt"
        )
    except training.LR8TrainingSourceError as exc:
        raise LR8SourceRunnerError(str(exc)) from exc
    if (
        receipt["uri"] != expected_uri
        or receipt["sha256"] != _sha(expected_raw)
        or receipt["bytes"] != len(expected_raw)
    ):
        raise LR8SourceRunnerError("create-only object receipt differs")
    reopened = (
        _strict_json(value.reopened_raw, label=expected_uri)
        if require_json else None
    )
    return receipt, reopened


def _validate_config(value: RunnerConfig) -> RunnerConfig:
    if not isinstance(value, RunnerConfig):
        raise LR8SourceRunnerError("runner config has the wrong type")
    lattice(value.mode)
    if not isinstance(value.execute, bool) or value.execute is not True:
        raise LR8SourceRunnerError("--execute is required explicitly")
    if not isinstance(value.enabled, bool) or value.enabled is not True:
        raise LR8SourceRunnerError(f"{ENABLED_ENV}=1 is required explicitly")
    if _ATTEMPT_ID.fullmatch(value.attempt_id) is None:
        raise LR8SourceRunnerError("attempt id is not canonical")
    _string(value.project, label="project")
    _string(value.bucket, label="bucket")
    for label, table in (
        ("catalog table", value.catalog_table),
        ("candidate table", value.candidate_table),
        ("PIT table", value.pit_table),
        ("TabPFN table", value.tabpfn_table),
    ):
        _table(table, label=label)
    if value.mode in ("smoke", "full-source"):
        if value.evidence_root is None:
            raise LR8SourceRunnerError(f"{value.mode} requires --evidence-root")
        root = value.evidence_root.resolve()
        if not root.is_dir() or any(root.iterdir()):
            raise LR8SourceRunnerError(
                "evidence root must be an existing empty create-only directory"
            )
    return value


def _query_requests(config: RunnerConfig) -> tuple[QuerySpec, ...]:
    plan = lattice(config.mode)
    slate_keys = _slate_keys(plan)
    common = (
        Parameter("panel_id", "STRING", PANEL_ID),
        Parameter("slate_keys", "STRING", slate_keys, array=True),
    )
    requests = [
        query_spec(
            label="canonical_catalog",
            sql=catalog_sql(config.catalog_table),
            parameters=common,
            attempt_id=config.attempt_id,
            location=config.location,
        ),
        query_spec(
            label="canonical_incumbents",
            sql=incumbent_sql(config.candidate_table),
            parameters=common,
            attempt_id=config.attempt_id,
            location=config.location,
        ),
    ]
    for season, weeks, _ in plan:
        requests.append(query_spec(
            label=f"pit_panel_{season}",
            sql=pit_panel_sql(config.pit_table, config.catalog_table),
            parameters=(
                Parameter("panel_id", "STRING", PANEL_ID),
                Parameter("slate_keys", "STRING", slate_keys, array=True),
                Parameter(
                    "training_seasons",
                    "INT64",
                    training.MODEL_TRAINING_SEASONS[season],
                    array=True,
                ),
                Parameter("target_season", "INT64", season),
                Parameter("target_weeks", "INT64", weeks, array=True),
            ),
            attempt_id=config.attempt_id,
            location=config.location,
        ))
        requests.append(query_spec(
            label=f"tabpfn_{season}",
            sql=tabpfn_sql(config.tabpfn_table, config.catalog_table),
            parameters=(
                Parameter("panel_id", "STRING", PANEL_ID),
                Parameter("slate_keys", "STRING", slate_keys, array=True),
                Parameter("target_season", "INT64", season),
                Parameter("target_weeks", "INT64", weeks, array=True),
            ),
            attempt_id=config.attempt_id,
            location=config.location,
        ))
    return tuple(requests)


def _extract_contract(label: str) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    if label == "canonical_catalog":
        return CATALOG_COLUMNS, ("season", "week", "id"), "catalog.json"
    if label == "canonical_incumbents":
        return INCUMBENT_COLUMNS, ("season", "week", "cand_ix"), "incumbents.json"
    if label.startswith("pit_panel_"):
        season = label.rsplit("_", 1)[1]
        return PIT_COLUMNS, ("season", "week", "gsis_id"), f"pit-panel-{season}.json"
    if label.startswith("tabpfn_"):
        season = label.rsplit("_", 1)[1]
        return CACHE_COLUMNS, ("season", "week", "gsis_id"), f"tabpfn-{season}.json"
    raise LR8SourceRunnerError("query extract label differs")


def _table_dependencies(config: RunnerConfig, label: str) -> tuple[str, ...]:
    if label == "canonical_catalog":
        return (config.catalog_table,)
    if label == "canonical_incumbents":
        return (config.candidate_table,)
    if label.startswith("pit_panel_"):
        return (config.pit_table, config.catalog_table)
    if label.startswith("tabpfn_"):
        return (config.tabpfn_table, config.catalog_table)
    raise LR8SourceRunnerError("query dependency label differs")


def _frame_from_extract(
    value: Mapping[str, object], *, expected_columns: Sequence[str],
) -> pd.DataFrame:
    if (
        value.get("schema") != EXTRACT_VERSION
        or value.get("columns") != list(expected_columns)
        or not isinstance(value.get("rows"), list)
        or value.get("rows_sha256")
        != _sha(_canonical_json(value.get("rows")))
    ):
        raise LR8SourceRunnerError("reopened query extract contract differs")
    return pd.DataFrame(value["rows"], columns=expected_columns)


def _catalog_inputs(
    catalog: pd.DataFrame,
    incumbents: pd.DataFrame,
    *,
    plan: Sequence[tuple[int, Sequence[int], Sequence[str]]],
    catalog_receipt: Mapping[str, object],
    incumbent_receipt: Mapping[str, object],
) -> tuple[
    tuple[training.CanonicalSlateSource, ...],
    dict[tuple[int, int], tuple[tuple[rw.PlayerSpec, ...], dict[str, float]]],
]:
    expected = {
        (season, week) for season, weeks, _ in plan for week in weeks
    }
    if catalog.empty or incumbents.empty:
        raise LR8SourceRunnerError("canonical catalog/incumbents are empty")
    observed_catalog = {
        (int(season), int(week))
        for season, week in catalog[["season", "week"]].itertuples(index=False)
    }
    observed_incumbents = {
        (int(season), int(week))
        for season, week in incumbents[["season", "week"]].itertuples(index=False)
    }
    if observed_catalog != expected or observed_incumbents != expected:
        raise LR8SourceRunnerError("canonical source slate lattice differs")
    output: list[training.CanonicalSlateSource] = []
    audited: dict[
        tuple[int, int], tuple[tuple[rw.PlayerSpec, ...], dict[str, float]]
    ] = {}
    for key in sorted(expected):
        season, week = key
        cat = catalog[(catalog.season == season) & (catalog.week == week)]
        cand = incumbents[
            (incumbents.season == season) & (incumbents.week == week)
        ]
        if cat.id.astype(str).duplicated().any():
            raise LR8SourceRunnerError("canonical catalog repeats a player id")
        players = tuple(rw.PlayerSpec.from_mapping({
            "id": row.id,
            "pos": row.pos,
            "team": row.team,
            "opp": row.opp,
            "game_id": row.game_id,
            "salary": _exact_catalog_salary(row.salary),
        }) for row in cat.itertuples(index=False))
        skill = cat.pos.astype(str).str.upper().ne("DST")
        if not cat.loc[skill, "id"].astype(str).equals(
            cat.loc[skill, "gsis_id"].astype(str)
        ):
            raise LR8SourceRunnerError("catalog skill id/gsis_id differs")
        dst = cat[~skill]
        if dst.empty or dst.mean_projection.isna().any():
            raise LR8SourceRunnerError("canonical DST mean_projection is missing")
        dst_means = {
            str(row.id): float(row.mean_projection)
            for row in dst.itertuples(index=False)
        }
        raw_identities = tuple(cand.players)
        if any(not isinstance(value, list) for value in raw_identities):
            raise LR8SourceRunnerError(
                "canonical incumbent players must be BigQuery ARRAY values"
            )
        identities = tuple(tuple(value) for value in raw_identities)
        if not identities:
            raise LR8SourceRunnerError("canonical incumbent identities are empty")
        catalog_hash = training.catalog_sha256(players)
        incumbent_hash = training.identities_sha256(identities)
        output.append(training.CanonicalSlateSource(
            season=season,
            week=week,
            panel_id=PANEL_ID,
            players=players,
            incumbent_candidates=identities,
            catalog_sha256=catalog_hash,
            incumbent_candidates_sha256=incumbent_hash,
            catalog_source_receipts=(catalog_receipt,),
            incumbent_source_receipts=(incumbent_receipt,),
            candidate_totals_loaded=False,
            outcome_fields_read=(),
        ))
        audited[key] = (players, dst_means)
    return tuple(output), audited


def _component_model_sha256(fitted: object) -> str:
    if not hasattr(fitted, "models") or not isinstance(fitted.models, Mapping):
        raise LR8SourceRunnerError("fitted component model contract differs")
    models = []
    for name in sorted(fitted.models):
        model = fitted.models[name]
        members = tuple(getattr(model, "members", (model,)))
        serialized = []
        for member in members:
            if not hasattr(member, "model_to_string"):
                raise LR8SourceRunnerError(
                    "model fit identity requires serializable LightGBM members"
                )
            serialized.append(member.model_to_string())
        models.append({"component": name, "members": serialized})
    return _sha(_canonical_json(models))


def _fit_model_binding(
    panel: pd.DataFrame, target_season: int,
) -> FittedModelBinding:
    fitted = components.train(
        panel,
        target_season=target_season,
        num_boost_round=MODEL_BOOST_ROUNDS,
    )
    return FittedModelBinding(
        model=fitted,
        model_sha256=_component_model_sha256(fitted),
    )


@contextmanager
def _bound_replay_model(
    binding: FittedModelBinding,
    *,
    target_season: int,
    expected_calls: int,
):
    """Return the hash-bound fitted object to every block's replay call."""
    if not isinstance(binding, FittedModelBinding) or binding.model is None:
        raise LR8SourceRunnerError("model fitter returned the wrong binding")
    expected_sha = _strict_sha(
        binding.model_sha256, label="model fit identity"
    )
    if _component_model_sha256(binding.model) != expected_sha:
        raise LR8SourceRunnerError("fitted model bytes differ from their identity")
    calls = 0
    previous_train = components.train

    def reuse_model(panel, *, target_season: int, num_boost_round: int):
        nonlocal calls
        if (
            target_season != int(target_season_expected)
            or num_boost_round != MODEL_BOOST_ROUNDS
        ):
            raise LR8SourceRunnerError("replay requested a different model fit")
        calls += 1
        if calls > expected_calls:
            raise LR8SourceRunnerError("replay requested too many model fits")
        return binding.model

    target_season_expected = target_season
    try:
        components.train = reuse_model
        yield
    finally:
        components.train = previous_train
    if calls != expected_calls:
        raise LR8SourceRunnerError(
            "replay did not reuse the hash-bound model for every block"
        )
    if _component_model_sha256(binding.model) != expected_sha:
        raise LR8SourceRunnerError("replay mutated the hash-bound fitted model")


@contextmanager
def _replay_scope(
    *,
    season: int,
    weeks: tuple[int, ...],
    cache: pd.DataFrame,
):
    previous_env = {key: os.environ.get(key) for key in REPLAY_ENVIRONMENT}
    previous_weeks = replay_source.EXPECTED_WEEKS
    previous_loader = replay_source.replay.load_tabpfn_marginal_cache

    def cache_loader(requested_season: int, env=None):
        if requested_season != season:
            raise LR8SourceRunnerError("TabPFN cache requested another season")
        return cache.copy(deep=True)

    try:
        for key, value in REPLAY_ENVIRONMENT.items():
            os.environ[key] = value
        replay_source.EXPECTED_WEEKS = {season: weeks}
        replay_source.replay.load_tabpfn_marginal_cache = cache_loader
        yield
    finally:
        replay_source.EXPECTED_WEEKS = previous_weeks
        replay_source.replay.load_tabpfn_marginal_cache = previous_loader
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _model_fit_input_sha(panel: pd.DataFrame, target_season: int) -> str:
    prior = panel[panel.season < target_season]
    rows = _frame_rows(
        prior,
        columns=PIT_COLUMNS,
        sort_by=("season", "week", "gsis_id"),
        label="model fit input",
    )
    return _sha(_canonical_json({"columns": list(PIT_COLUMNS), "rows": rows}))


def _validate_outcome_blind_panel(
    panel: pd.DataFrame, *, target_season: int,
) -> None:
    if not isinstance(panel, pd.DataFrame) or set(panel) != set(PIT_COLUMNS):
        raise LR8SourceRunnerError("mixed PIT panel columns differ")
    try:
        seasons = tuple(sorted({int(value) for value in panel["season"]}))
    except (TypeError, ValueError) as exc:
        raise LR8SourceRunnerError("mixed PIT panel seasons are malformed") from exc
    expected = (*training.MODEL_TRAINING_SEASONS[target_season], target_season)
    if seasons != expected:
        raise LR8SourceRunnerError("mixed PIT panel training seasons differ")
    target = panel[panel["season"] == target_season]
    if target.empty:
        raise LR8SourceRunnerError("mixed PIT target rows are empty")
    poison = ("was_active", *MODEL_LABEL_COLUMNS)
    if target.loc[:, list(poison)].notna().any(axis=None):
        raise LR8SourceRunnerError(
            "target PIT outcome/model-label placeholders must all be NULL"
        )


def _load_solver_factory():
    try:
        from nfl_dfs.research.lr8_exact_solvers import (
            make_training_world_solver,
        )
    except (ImportError, AttributeError) as exc:
        raise LR8SourceRunnerError(
            "exact LR8 solver callback is unavailable"
        ) from exc
    if not callable(make_training_world_solver):
        raise LR8SourceRunnerError("exact LR8 solver factory is not callable")
    return make_training_world_solver


def _evidence_publisher(
    *,
    evidence_root: Path,
    output_root: str,
    publish: Publisher,
):
    root = evidence_root.resolve()

    def publisher(bundle) -> Sequence[Mapping[str, object]]:
        proof = bytes(bundle.proof_bytes)
        request_sha = _strict_sha(
            bundle.request_sha256, label="solve request hash"
        )
        if _sha(proof) != _strict_sha(
            bundle.proof_sha256, label="solve proof hash"
        ):
            raise LR8SourceRunnerError("exact solve proof bytes differ")
        receipts: list[Mapping[str, object]] = []
        proof_uri = f"{output_root}/solver-evidence/{request_sha}/proof.json"
        receipts.append(_published(
            publish(proof_uri, proof),
            expected_uri=proof_uri,
            expected_raw=proof,
            require_json=False,
        )[0])
        for index, evidence in enumerate(bundle.solve_evidence):
            paths = (
                ("cbc.log", evidence.log_path, evidence.log_sha256),
                ("model.sol", evidence.solution_path, evidence.solution_sha256),
                ("model.mps", evidence.model_path, evidence.model_sha256),
                (
                    "variable-domain-manifest.json",
                    evidence.variable_domain_manifest_path,
                    evidence.variable_domain_manifest_sha256,
                ),
                ("model.mst", evidence.mip_start_path, evidence.mip_start_sha256),
            )
            for name, raw_path, expected_sha in paths:
                if raw_path is None:
                    continue
                path = Path(raw_path).resolve()
                if not path.is_file() or not path.is_relative_to(root):
                    raise LR8SourceRunnerError(
                        "retained CBC evidence is outside its create-only root"
                    )
                raw = path.read_bytes()
                if _sha(raw) != _strict_sha(
                    expected_sha, label="retained CBC artifact hash"
                ):
                    raise LR8SourceRunnerError(
                        "retained CBC evidence artifact bytes differ"
                    )
                uri = (
                    f"{output_root}/solver-evidence/{request_sha}/"
                    f"{index:02d}-{name}"
                )
                receipts.append(_published(
                    publish(uri, raw),
                    expected_uri=uri,
                    expected_raw=raw,
                    require_json=False,
                )[0])
        if not receipts:
            raise LR8SourceRunnerError("exact solve evidence receipts are empty")
        return tuple(receipts)

    return publisher


def _smoke_solve(
    canonical: training.CanonicalSlateSource,
    block: training.PITReplayBlock,
    solve_world: training.WorldSolver,
) -> training.FrozenBlockSource:
    players = tuple(sorted(
        (
            player if isinstance(player, rw.PlayerSpec)
            else rw.PlayerSpec.from_mapping(player)
            for player in canonical.players
        ),
        key=lambda row: row.player_id,
    ))
    incumbents = tuple(rw.canonical_identity(value) for value in (
        canonical.incumbent_candidates
    ))
    replay_slate = block.slates[0]
    by_id = {
        player_id: index for index, player_id in enumerate(replay_slate.player_ids)
    }
    canonical_ids = tuple(player.player_id for player in players)
    if set(by_id) != set(canonical_ids):
        raise LR8SourceRunnerError("smoke player universe differs")
    draws = np.ascontiguousarray(
        replay_slate.player_draws[[by_id[player_id] for player_id in canonical_ids]],
        dtype=np.float32,
    )
    draws.flags.writeable = False
    return training._solve_block(
        season=2019,
        week=1,
        block="R0",
        players=players,
        player_ids=canonical_ids,
        player_draws=draws,
        world_receipts=tuple(replay_slate.source_receipts),
        incumbents=incumbents,
        catalog_digest=canonical.catalog_sha256,
        incumbent_digest=canonical.incumbent_candidates_sha256,
        solve_world=solve_world,
    )


def _smoke_solve_payload(
    block: training.FrozenBlockSource,
    canonical: training.CanonicalSlateSource,
) -> dict[str, object]:
    """Serialize the complete smoke solve ledger for independent harvesting."""
    if not isinstance(block, training.FrozenBlockSource):
        raise LR8SourceRunnerError("smoke solve freeze has the wrong type")
    if not isinstance(canonical, training.CanonicalSlateSource) or (
        canonical.season,
        canonical.week,
    ) != (2019, 1):
        raise LR8SourceRunnerError("smoke canonical source identity differs")
    if block.block != "R0" or block.projection_seed != 0:
        raise LR8SourceRunnerError("smoke solve block identity differs")
    canonical_player_ids = tuple(
        player.player_id for player in sorted(
            canonical.players, key=lambda row: row.player_id
        )
    )
    if block.player_ids != canonical_player_ids:
        raise LR8SourceRunnerError("smoke solve player/catalog alignment differs")
    attempts = [{
        "block": attempt.block,
        "projection_seed": attempt.projection_seed,
        "world_index": attempt.world_index,
        "roster": list(attempt.roster),
        "objective_micro": attempt.objective_micro,
        "admitted_unique": attempt.admitted_unique,
        "request_sha256": attempt.request_sha256,
        "evidence_receipts": list(attempt.evidence_receipts),
        "evidence_manifest_sha256": attempt.evidence_manifest_sha256,
    } for attempt in block.solve_attempts]
    request_payloads = []
    for attempt in block.solve_attempts:
        scores = np.array(
            block.player_draws[:, attempt.world_index],
            dtype=np.float32,
            copy=True,
            order="C",
        )
        scores.flags.writeable = False
        request_payload = {
            "season": 2019,
            "week": 1,
            "block": block.block,
            "projection_seed": block.projection_seed,
            "world_index": attempt.world_index,
            "catalog_sha256": canonical.catalog_sha256,
            "player_scores_sha256": training.array_sha256(scores),
            "incumbent_no_goods_sha256": (
                canonical.incumbent_candidates_sha256
            ),
            "candidate_world_family": training.CANDIDATE_WORLD_FAMILY,
            "role_belief_worlds_used": False,
            "hard_domain_id": training.HARD_DOMAIN_ID,
            "former_house_rules_not_applied": list(
                training.FORMER_HOUSE_RULES_NOT_APPLIED
            ),
        }
        if training.canonical_sha256(request_payload) != attempt.request_sha256:
            raise LR8SourceRunnerError("smoke solve request preimage differs")
        request_payloads.append(request_payload)
    candidates = [
        training._candidate_freeze_payload(candidate)  # noqa: SLF001
        for candidate in block.candidates
    ]
    candidate_identities = [list(candidate.roster) for candidate in block.candidates]
    anatomy = [{
        "roster": list(candidate.roster),
        "features": training._anatomy_payload(  # noqa: SLF001
            candidate.anatomy_features
        ),
    } for candidate in block.candidates]
    legality = [{
        "roster": list(candidate.roster),
        "hard_domain_id": training.HARD_DOMAIN_ID,
        "dk_classic_legal": True,
        "former_house_rules_applied": [],
    } for candidate in block.candidates]
    checks = (
        (attempts, block.solve_attempts_sha256, "ordered solve attempts"),
        (candidate_identities, block.candidate_identities_sha256, "candidate identities"),
        (anatomy, block.anatomy_sha256, "candidate anatomy"),
        (legality, block.legality_sha256, "candidate legality"),
    )
    for value, expected, label in checks:
        if training.canonical_sha256(value) != _strict_sha(
            expected, label=f"smoke {label} hash"
        ):
            raise LR8SourceRunnerError(f"smoke {label} hash differs")
    world_order = list(block.world_order)
    if training.canonical_sha256(world_order) != _strict_sha(
        block.world_order_sha256, label="smoke world order hash"
    ):
        raise LR8SourceRunnerError("smoke world order hash differs")
    player_ids = list(block.player_ids)
    if training.player_ids_sha256(block.player_ids) != _strict_sha(
        block.player_ids_sha256, label="smoke player ids hash"
    ):
        raise LR8SourceRunnerError("smoke player ids hash differs")
    draws = np.asarray(block.player_draws)
    if training.array_sha256(draws) != _strict_sha(
        block.player_draws_sha256, label="smoke player draws hash"
    ):
        raise LR8SourceRunnerError("smoke player draws hash differs")
    if len(candidates) != training.UNIQUE_OPTIMA_PER_BLOCK:
        raise LR8SourceRunnerError("smoke unique candidate dose differs")
    return {
        "version": SMOKE_SOLVE_FREEZE_VERSION,
        "season": 2019,
        "week": 1,
        "block": block.block,
        "projection_seed": block.projection_seed,
        "source_environment_role_seed_nonoperative": (
            block.source_environment_role_seed_nonoperative
        ),
        "candidate_world_family": training.CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "hard_domain_id": training.HARD_DOMAIN_ID,
        "former_house_rules_not_applied": list(
            training.FORMER_HOUSE_RULES_NOT_APPLIED
        ),
        "player_ids": player_ids,
        "player_ids_sha256": block.player_ids_sha256,
        "player_draws": {
            "dtype": draws.dtype.str,
            "shape": list(draws.shape),
            "sha256": block.player_draws_sha256,
        },
        "world_order_law": training.WORLD_ORDER_LAW,
        "world_order": world_order,
        "world_order_sha256": block.world_order_sha256,
        "source_receipts": list(block.source_receipts),
        "catalog_sha256": canonical.catalog_sha256,
        "incumbent_candidates_sha256": canonical.incumbent_candidates_sha256,
        "ordered_request_payloads": request_payloads,
        "ordered_request_payloads_sha256": training.canonical_sha256(
            request_payloads
        ),
        "ordered_solve_attempt_count": len(attempts),
        "ordered_solve_attempts": attempts,
        "ordered_solve_attempts_sha256": block.solve_attempts_sha256,
        "unique_candidates": candidates,
        "unique_candidate_count": len(candidates),
        "candidate_identities_sha256": block.candidate_identities_sha256,
        "anatomy_sha256": block.anatomy_sha256,
        "legality_sha256": block.legality_sha256,
    }


def run_source(
    config: RunnerConfig,
    *,
    query: QueryExecutor,
    table_metadata: MetadataReader,
    publish: Publisher,
    model_fitter: ModelFitter = _fit_model_binding,
    adapter: Callable[..., training.PITReplayBlock] = (
        replay_source.materialize_baseline_replay_block
    ),
    solver_factory: object = _AUTO_SOLVER,
) -> dict[str, object]:
    """Run one source build using explicit query/storage dependencies."""
    cfg = _validate_config(config)
    plan = lattice(cfg.mode)
    if not callable(query) or not callable(table_metadata) or not callable(publish):
        raise LR8SourceRunnerError("runner dependencies must be callable")
    if solver_factory is _AUTO_SOLVER:
        solver_factory = _load_solver_factory()
    if not callable(solver_factory):
        raise LR8SourceRunnerError(
            f"{cfg.mode} requires the separate exact solver callback"
        )

    tables = (
        cfg.catalog_table, cfg.candidate_table, cfg.pit_table, cfg.tabpfn_table
    )
    before = {
        table: _validate_table_receipt(table_metadata(table), table=table)
        for table in tables
    }
    query_outputs: dict[str, tuple[pd.DataFrame, dict[str, object], QuerySpec]] = {}
    for spec in _query_requests(cfg):
        frame, job = query(spec)
        query_outputs[spec.label] = (
            frame, _validate_job_receipt(job, spec), spec
        )
    after = {
        table: _validate_table_receipt(table_metadata(table), table=table)
        for table in tables
    }
    if _canonical_json(before) != _canonical_json(after):
        raise LR8SourceRunnerError("BigQuery table metadata drifted during reads")

    extracts: dict[str, dict[str, object]] = {}
    extract_receipts: dict[str, dict[str, object]] = {}
    query_receipts: dict[str, dict[str, object]] = {}
    for label, (frame, job, spec) in query_outputs.items():
        columns, sort_by, filename = _extract_contract(label)
        dependencies = _table_dependencies(cfg, label)
        raw = _extract_bytes(
            spec=spec,
            frame=frame,
            job_receipt=job,
            table_receipts=[before[table] for table in dependencies],
            columns=columns,
            sort_by=sort_by,
        )
        uri = f"{cfg.output_root}/extracts/{filename}"
        receipt, reopened = _published(
            publish(uri, raw), expected_uri=uri, expected_raw=raw
        )
        extracts[label] = reopened
        extract_receipts[label] = receipt
        query_receipts[label] = job

    catalog = _frame_from_extract(
        extracts["canonical_catalog"], expected_columns=CATALOG_COLUMNS
    )
    incumbents = _frame_from_extract(
        extracts["canonical_incumbents"], expected_columns=INCUMBENT_COLUMNS
    )
    canonical_sources, audited = _catalog_inputs(
        catalog,
        incumbents,
        plan=plan,
        catalog_receipt=extract_receipts["canonical_catalog"],
        incumbent_receipt=extract_receipts["canonical_incumbents"],
    )

    blocks: list[training.PITReplayBlock] = []
    model_fits: dict[int, dict[str, str]] = {}
    for season, weeks, block_names in plan:
        panel_label = f"pit_panel_{season}"
        cache_label = f"tabpfn_{season}"
        panel = _frame_from_extract(
            extracts[panel_label], expected_columns=PIT_COLUMNS
        )
        _validate_outcome_blind_panel(panel, target_season=season)
        cache = _frame_from_extract(
            extracts[cache_label], expected_columns=CACHE_COLUMNS
        )
        fit_input_sha = _model_fit_input_sha(panel, season)
        with _replay_scope(season=season, weeks=tuple(weeks), cache=cache):
            binding = model_fitter(panel, season)
            if not isinstance(binding, FittedModelBinding):
                raise LR8SourceRunnerError(
                    "model fitter returned the wrong binding"
                )
            fit_sha = _strict_sha(
                binding.model_sha256, label="model fit identity"
            )
            model_fits[season] = {
                "model_fit_input_sha256": fit_input_sha,
                "model_fit_sha256": fit_sha,
            }
            audited_slates = tuple(
                replay_source.AuditedReplaySlate(
                    season=season,
                    week=week,
                    players=audited[(season, week)][0],
                    catalog_sha256=training.catalog_sha256(
                        audited[(season, week)][0]
                    ),
                    dst_mean_projection=audited[(season, week)][1],
                    replay_source_receipts=(
                        extract_receipts[panel_label],
                        extract_receipts[cache_label],
                        extract_receipts["canonical_catalog"],
                    ),
                )
                for week in weeks
            )
            with _bound_replay_model(
                binding,
                target_season=season,
                expected_calls=len(block_names),
            ):
                for block_name in block_names:
                    blocks.append(adapter(
                        panel,
                        audited_slates,
                        target_season=season,
                        block=block_name,
                        model_fit_input_sha256=fit_input_sha,
                        model_fit_sha256=fit_sha,
                        fit_source_receipts=(extract_receipts[panel_label],),
                        provenance=replay_source.ReplaySourceProvenance(),
                    ))

    if cfg.evidence_root is None:  # already rejected; type narrowing only
        raise LR8SourceRunnerError("exact solver lacks evidence root")
    evidence_root = cfg.evidence_root.resolve()
    solve_world = solver_factory(
        evidence_root=evidence_root,
        publish_evidence=_evidence_publisher(
            evidence_root=evidence_root,
            output_root=cfg.output_root,
            publish=publish,
        ),
    )
    if not callable(solve_world):
        raise LR8SourceRunnerError("exact solver factory returned non-callable")

    source_freeze_receipt = None
    smoke_solve_receipt = None
    smoke_solve = None
    if cfg.mode == "full-source":
        if solve_world is None:
            raise LR8SourceRunnerError("full-source exact solver is unavailable")
        bundle = training.build_training_source(
            canonical_sources, tuple(blocks), solve_world
        )
        freeze = training.freeze_training_source(bundle)
        freeze_raw = _canonical_json(freeze)
        freeze_uri = f"{cfg.output_root}/training-source-freeze.json"
        source_freeze_receipt = _published(
            publish(freeze_uri, freeze_raw),
            expected_uri=freeze_uri,
            expected_raw=freeze_raw,
        )[0]
    else:
        smoke_solve = _smoke_solve(canonical_sources[0], blocks[0], solve_world)
        if len(smoke_solve.candidates) != training.UNIQUE_OPTIMA_PER_BLOCK:
            raise LR8SourceRunnerError(
                "smoke did not produce exactly forty unique DK-only optima"
            )
        smoke_solve_raw = _canonical_json(_smoke_solve_payload(
            smoke_solve, canonical_sources[0]
        ))
        smoke_solve_uri = f"{cfg.output_root}/smoke-solve-freeze.json"
        smoke_solve_receipt = _published(
            publish(smoke_solve_uri, smoke_solve_raw),
            expected_uri=smoke_solve_uri,
            expected_raw=smoke_solve_raw,
        )[0]

    if cfg.mode == "smoke":
        if len(canonical_sources) != 1 or len(blocks) != 1:
            raise LR8SourceRunnerError("smoke source lattice differs")
        block = blocks[0]
        if (
            block.target_season != 2019
            or block.block != "R0"
            or block.projection_seed != 0
            or len(block.slates) != 1
            or (block.slates[0].season, block.slates[0].week) != (2019, 1)
            or block.slates[0].player_draws.shape[1]
            != training.WORLDS_PER_BLOCK
            or block.target_player_labels_read is not False
            or block.candidate_labels_read is not False
            or block.role_belief_worlds_used is not False
        ):
            raise LR8SourceRunnerError("smoke replay lattice differs")

    manifest: dict[str, object] = {
        "version": RUNNER_VERSION,
        "mode": cfg.mode,
        "attempt_id": cfg.attempt_id,
        "canonical_panel_id": PANEL_ID,
        "lattice": [{
            "season": season,
            "weeks": list(weeks),
            "blocks": list(block_names),
        } for season, weeks, block_names in plan],
        "replay_environment": REPLAY_ENVIRONMENT,
        "table_receipts": before,
        "query_job_receipts": query_receipts,
        "extract_objects": extract_receipts,
        "model_fits": {str(key): value for key, value in model_fits.items()},
        "replay_blocks": [{
            "season": block.target_season,
            "block": block.block,
            "projection_seed": block.projection_seed,
            "source_environment_role_seed_nonoperative": (
                block.source_environment_role_seed_nonoperative
            ),
            "slates": [{
                "season": slate.season,
                "week": slate.week,
                "player_ids_sha256": slate.player_ids_sha256,
                "player_draws_sha256": slate.player_draws_sha256,
                "shape": list(slate.player_draws.shape),
            } for slate in block.slates],
        } for block in blocks],
        "solver_status": (
            "exact_smoke_complete" if smoke_solve is not None
            else "exact_full_source_complete"
        ),
        "smoke_unique_candidates": (
            len(smoke_solve.candidates) if smoke_solve is not None else 0
        ),
        "training_source_freeze_object": source_freeze_receipt,
        "smoke_solve_freeze_object": smoke_solve_receipt,
        "smoke_solve_freeze": (
            {
                "block": smoke_solve.block,
                "projection_seed": smoke_solve.projection_seed,
                "player_ids_sha256": smoke_solve.player_ids_sha256,
                "player_draws_sha256": smoke_solve.player_draws_sha256,
                "world_order_sha256": smoke_solve.world_order_sha256,
                "ordered_solve_attempt_count": len(smoke_solve.solve_attempts),
                "ordered_solve_attempts_sha256": (
                    smoke_solve.solve_attempts_sha256
                ),
                "unique_candidate_count": len(smoke_solve.candidates),
                "candidate_identities_sha256": (
                    smoke_solve.candidate_identities_sha256
                ),
                "anatomy_sha256": smoke_solve.anatomy_sha256,
                "legality_sha256": smoke_solve.legality_sha256,
            }
            if smoke_solve is not None else None
        ),
        "prior_model_training_labels_queried": True,
        "prior_was_active_queried": True,
        "prior_model_training_seasons": {
            str(season): list(training.MODEL_TRAINING_SEASONS[season])
            for season, _, _ in plan
        },
        "target_model_label_placeholders_all_null": True,
        "target_was_active_placeholder_all_null": True,
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "role_belief_worlds_used": False,
        "dst_correlated_draws_used": False,
        "build_slates_used": False,
        "actual_score_queried": False,
        "candidate_totals_queried": False,
        "y_dk_points_queried": False,
        "target_realized_labels_queried": False,
        "historical_candidate_label_read_licensed": False,
        "production_change_licensed": False,
    }
    manifest["manifest_sha256"] = _sha(_canonical_json(manifest))
    manifest_raw = _canonical_json(manifest)
    name = "smoke-manifest.json" if cfg.mode == "smoke" else "full-source-manifest.json"
    manifest_uri = f"{cfg.output_root}/{name}"
    manifest_receipt = _published(
        publish(manifest_uri, manifest_raw),
        expected_uri=manifest_uri,
        expected_raw=manifest_raw,
    )[0]
    return {"manifest": manifest, "manifest_object": manifest_receipt}


def _iso(value: object, *, label: str) -> str:
    if not isinstance(value, datetime):
        raise LR8SourceRunnerError(f"{label} is not a datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _default_table_metadata(client, table_id: str) -> dict[str, object]:
    table = client.get_table(table_id)

    def field_payload(field) -> dict[str, object]:
        return {
            "name": field.name,
            "field_type": field.field_type,
            "mode": field.mode,
            "fields": [field_payload(child) for child in field.fields],
        }

    schema = [field_payload(field) for field in table.schema]
    return {
        "table_id": table_id,
        "etag": _string(table.etag, label="BigQuery table etag"),
        "modified": _iso(table.modified, label="BigQuery table modified"),
        "num_rows": _exact_int(table.num_rows, label="BigQuery table rows"),
        "schema_sha256": _sha(_canonical_json(schema)),
    }


def _default_query(client, spec: QuerySpec) -> tuple[pd.DataFrame, dict[str, object]]:
    from google.cloud import bigquery

    parameters = []
    for value in spec.parameters:
        if value.array:
            parameters.append(bigquery.ArrayQueryParameter(
                value.name, value.bq_type, list(value.value)
            ))
        else:
            parameters.append(bigquery.ScalarQueryParameter(
                value.name, value.bq_type, value.value
            ))
    config = bigquery.QueryJobConfig(query_parameters=parameters, use_query_cache=False)
    job = client.query(
        spec.sql,
        job_config=config,
        job_id=spec.job_id,
        location=spec.location,
    )
    result = job.result()
    frame = result.to_dataframe(create_bqstorage_client=False)
    receipt = {
        "job_id": job.job_id,
        "location": job.location,
        "query_sha256": spec.query_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "created": _iso(job.created, label="query created"),
        "started": _iso(job.started, label="query started"),
        "ended": _iso(job.ended, label="query ended"),
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "cache_hit": bool(job.cache_hit),
        "error_result": job.error_result,
    }
    return frame, receipt


def _gcs_parts(uri: str) -> tuple[str, str]:
    value = _string(uri, label="GCS URI")
    if not value.startswith("gs://"):
        raise LR8SourceRunnerError("object URI must use gs://")
    bucket, separator, name = value.removeprefix("gs://").partition("/")
    if not bucket or not separator or not name:
        raise LR8SourceRunnerError("object URI needs bucket and object")
    return bucket, name


def _precondition_failed(exc: Exception) -> bool:
    try:
        from google.api_core.exceptions import PreconditionFailed

        return isinstance(exc, PreconditionFailed)
    except ImportError:
        return type(exc).__name__ == "PreconditionFailed"


def _content_type(uri: str) -> str:
    lowered = uri.lower()
    if lowered.endswith(".json"):
        return "application/json"
    if lowered.endswith((".log", ".sol", ".mps", ".mst")):
        return "text/plain; charset=utf-8"
    return "application/octet-stream"


def _default_publish(storage_client, uri: str, raw: bytes) -> PublishedObject:
    bucket_name, name = _gcs_parts(uri)
    blob = storage_client.bucket(bucket_name).blob(name)
    created = True
    try:
        blob.upload_from_string(
            raw,
            content_type=_content_type(uri),
            if_generation_match=0,
        )
    except Exception as exc:
        if not _precondition_failed(exc):
            raise
        created = False
    blob.reload()
    generation = _exact_int(
        int(blob.generation), label="GCS generation", minimum=1
    )
    pinned = storage_client.bucket(bucket_name).blob(name, generation=generation)
    reopened = pinned.download_as_bytes(if_generation_match=generation)
    if reopened != raw:
        if created:
            raise LR8SourceRunnerError("create-only object reopen differs")
        raise LR8SourceRunnerError("create-only collision has different bytes")
    return PublishedObject(
        receipt={
            "uri": uri,
            "generation": str(generation),
            "sha256": _sha(reopened),
            "bytes": len(reopened),
        },
        reopened_raw=reopened,
        created=created,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("smoke", "full-source"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument(
        "--project", default=os.environ.get("GCP_PROJECT", "nfl-predictions-503414")
    )
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--catalog-table")
    parser.add_argument("--candidate-table")
    parser.add_argument("--pit-table")
    parser.add_argument("--tabpfn-table")
    parser.add_argument("--location", default="US")
    parser.add_argument("--evidence-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project = args.project
    config = RunnerConfig(
        mode=args.mode,
        attempt_id=args.attempt_id,
        project=project,
        bucket=args.bucket,
        catalog_table=(
            args.catalog_table
            or f"{project}.nfl_predictions.slate_player_features"
        ),
        candidate_table=(
            args.candidate_table
            or f"{project}.nfl_predictions.replay_candidates_staging"
        ),
        pit_table=(
            args.pit_table
            or f"{project}.nfl_features.player_week_training"
        ),
        tabpfn_table=(
            args.tabpfn_table
            or f"{project}.nfl_features.{TABPFN_TABLE_NAME}"
        ),
        location=args.location,
        evidence_root=args.evidence_root,
        execute=args.execute,
        enabled=os.environ.get(ENABLED_ENV, "0") == "1",
    )
    _validate_config(config)
    from google.cloud import bigquery, storage

    bq_client = bigquery.Client(project=project)
    storage_client = storage.Client(project=project)
    result = run_source(
        config,
        query=lambda spec: _default_query(bq_client, spec),
        table_metadata=lambda table: _default_table_metadata(bq_client, table),
        publish=lambda uri, raw: _default_publish(storage_client, uri, raw),
    )
    print(_canonical_json(result).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LR8SourceRunnerError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
