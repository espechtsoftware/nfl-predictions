#!/usr/bin/env python3
"""Create one immutable B1 score artifact from authoritative settled data.

This is a default-off replacement scaffold for the invalid assumption that
live pre-lock candidate rows later label themselves.  It never updates those
rows.  Instead it generation-pins the frozen shadow receipt, opens a
create-only settlement attempt, maps the receipt's exact DK roster union
through the persisted pre-lock player catalog, and reads only the canonical
player/DST actual tables after every represented game is final.

The emitted v2 document preserves the existing B1 adoption document shape,
but truthfully identifies its new source.  The existing shared B1 validators
must explicitly license this version/source/query hash before deployment.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence

import pandas as pd
from google.api_core.exceptions import PreconditionFailed
from google.cloud import bigquery, storage


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_b1_corpus_tail_shadow_transport as transport  # noqa: E402
import run_b1_corpus_tail_panel_producer as panel_producer  # noqa: E402
from nfl_dfs.research import b1_corpus_tail as science  # noqa: E402


PROJECT = transport.PROJECT
SEASON = transport.SEASON
WEEKS = transport.WEEKS
ENABLED_ENV = "B1_AUTHORITATIVE_SETTLEMENT_ENABLED"
SETTLED_VERSION = "b1-corpus-tail-authoritative-settled-scores-v2"
ATTEMPT_VERSION = "b1-corpus-tail-authoritative-settlement-attempt-v2"
SOURCE_NAME = (
    "nfl_features.player_week_actuals+team_defense_week"
    ":via:nfl_predictions.slate_player_features"
    ":finality:nfl_raw.schedules+nfl_raw.pbp"
)

_GENERATION = re.compile(r"[1-9][0-9]*")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")

QUERY_COLUMNS = (*panel_producer.PLAYER_COLUMNS,
    "in_frozen_union", "authoritative_actual", "actual_source",
    "schedule_game_id", "schedule_home_team", "schedule_away_team",
    "home_score", "away_score", "terminal_home_score",
    "terminal_away_score", "terminal_game_status", "terminal_rule",
)


class AuthoritativeSettlementError(RuntimeError):
    """The post-settlement materializer failed a frozen boundary."""


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _strict_json(raw: bytes, *, label: str) -> Any:
    def reject_constant(value: str) -> None:
        raise AuthoritativeSettlementError(
            f"{label} contains non-finite JSON: {value}"
        )

    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuthoritativeSettlementError(
                    f"{label} repeats JSON key {key}"
                )
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate,
        )
    except AuthoritativeSettlementError:
        raise
    except Exception as exc:
        raise AuthoritativeSettlementError(f"{label} is not strict JSON") from exc


def _utc(value: object, *, label: str) -> datetime:
    if isinstance(value, pd.Timestamp):
        parsed = value.to_pydatetime()
    elif isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuthoritativeSettlementError(
                f"{label} is not ISO-8601"
            ) from exc
    else:
        raise AuthoritativeSettlementError(f"{label} timestamp is absent")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AuthoritativeSettlementError(
            f"{label} timestamp is not timezone-aware"
        )
    return parsed.astimezone(timezone.utc)


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://") or "/" not in uri[5:]:
        raise AuthoritativeSettlementError("GCS object URI differs")
    bucket, name = uri[5:].split("/", 1)
    if not bucket or not name:
        raise AuthoritativeSettlementError("GCS object URI differs")
    return bucket, name


def _download_generation(
    client: storage.Client,
    *,
    uri: str,
    generation: str,
    label: str,
) -> tuple[dict[str, Any], bytes, datetime]:
    """Read exactly one caller-named generation at one code-fixed URI."""
    if _GENERATION.fullmatch(str(generation)) is None:
        raise AuthoritativeSettlementError(f"{label} generation differs")
    bucket_name, name = _gcs_parts(uri)
    expected_generation = int(generation)
    blob = client.bucket(bucket_name).blob(name, generation=expected_generation)
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=expected_generation)
    identity = {
        "uri": uri,
        "generation": str(blob.generation or ""),
        "metageneration": str(blob.metageneration or ""),
        "bytes": int(blob.size or 0),
        "sha256": sha256(raw).hexdigest(),
    }
    if (
        identity["generation"] != str(expected_generation)
        or identity["metageneration"] != "1"
        or identity["bytes"] != len(raw)
        or _HEX64.fullmatch(identity["sha256"]) is None
    ):
        raise AuthoritativeSettlementError(f"{label} object identity differs")
    created_at = _utc(blob.time_created, label=f"{label} object creation")
    return identity, raw, created_at


def _upload_create_once(
    client: storage.Client,
    *,
    uri: str,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Create and byte-verify one exact GCS generation."""
    raw = _canonical_json(dict(value))
    bucket_name, name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(name)
    try:
        blob.upload_from_string(
            raw,
            content_type="application/json",
            if_generation_match=0,
        )
    except PreconditionFailed as exc:
        raise AuthoritativeSettlementError(
            f"create-only settlement object already exists: {uri}"
        ) from exc
    try:
        generation = int(blob.generation or 0)
    except (TypeError, ValueError) as exc:
        raise AuthoritativeSettlementError(
            "create-only settlement upload lacks a generation"
        ) from exc
    if generation <= 0:
        raise AuthoritativeSettlementError(
            "create-only settlement upload lacks a generation"
        )
    pinned = client.bucket(bucket_name).blob(name, generation=generation)
    pinned.reload()
    observed = pinned.download_as_bytes(if_generation_match=generation)
    identity = {
        "uri": uri,
        "generation": str(pinned.generation or ""),
        "metageneration": str(pinned.metageneration or ""),
        "bytes": int(pinned.size or 0),
        "sha256": sha256(observed).hexdigest(),
        "created_at": _utc(
            pinned.time_created, label="settlement object creation"
        ).isoformat(),
        "create_only": True,
    }
    if (
        observed != raw
        or identity["generation"] != str(generation)
        or identity["metageneration"] != "1"
        or identity["bytes"] != len(raw)
    ):
        raise AuthoritativeSettlementError(
            "create-only settlement object bytes differ"
        )
    return identity


def authoritative_settlement_sql() -> str:
    sql = f"""
WITH frozen_mapping AS (
  SELECT {', '.join(panel_producer.PLAYER_COLUMNS)}
  FROM `{panel_producer.PLAYER_TABLE}`
  WHERE panel_run_id IN UNNEST(@panels)
    AND season = @season
    AND week = @week
),
tagged_mapping AS (
  SELECT m.*,
         (m.panel_run_id = @canonical_panel
           AND CAST(m.id AS STRING) IN UNNEST(@dk_player_ids))
           AS in_frozen_union
  FROM frozen_mapping m
),
represented_games AS (
  SELECT DISTINCT CAST(game_id AS STRING) AS game_id
  FROM tagged_mapping
  WHERE in_frozen_union
),
skill_actual AS (
  SELECT CAST(gsis_id AS STRING) AS gsis_id, dk_points
  FROM `{PROJECT}.nfl_features.player_week_actuals`
  WHERE season = @season AND week = @week
    AND CAST(gsis_id AS STRING) IN (
      SELECT DISTINCT CAST(gsis_id AS STRING)
      FROM tagged_mapping
      WHERE in_frozen_union AND UPPER(CAST(pos AS STRING)) != 'DST'
    )
),
dst_actual AS (
  SELECT UPPER(CAST(team AS STRING)) AS team, dst_dk_points
  FROM `{PROJECT}.nfl_features.team_defense_week`
  WHERE season = @season AND week = @week
    AND UPPER(CAST(team AS STRING)) IN (
      SELECT DISTINCT UPPER(CAST(team AS STRING))
      FROM tagged_mapping
      WHERE in_frozen_union AND UPPER(CAST(pos AS STRING)) = 'DST'
    )
),
latest_pbp AS (
  SELECT CAST(game_id AS STRING) AS game_id,
         ARRAY_AGG(
           STRUCT(play_id, total_home_score, total_away_score, `desc`)
           ORDER BY play_id DESC LIMIT 1
         )[OFFSET(0)] AS terminal
  FROM `{PROJECT}.nfl_raw.pbp`
  WHERE season = @season AND week = @week
    AND CAST(game_id AS STRING) IN (SELECT game_id FROM represented_games)
  GROUP BY game_id
),
settled_games AS (
  SELECT CAST(s.game_id AS STRING) AS game_id,
         UPPER(CAST(s.home_team AS STRING)) AS home_team,
         UPPER(CAST(s.away_team AS STRING)) AS away_team,
         s.home_score,
         s.away_score,
         p.terminal.total_home_score AS terminal_home_score,
         p.terminal.total_away_score AS terminal_away_score,
         CASE
           WHEN REGEXP_CONTAINS(
             TRIM(LOWER(COALESCE(p.terminal.`desc`, ''))),
             r'^end( of)? game$'
           ) THEN 'final'
           ELSE 'not_final'
         END AS terminal_game_status,
         CASE
           WHEN REGEXP_CONTAINS(
             TRIM(LOWER(COALESCE(p.terminal.`desc`, ''))),
             r'^end( of)? game$'
           ) THEN 'latest_pbp_end_game'
           ELSE NULL
         END AS terminal_rule
  FROM `{PROJECT}.nfl_raw.schedules`
    AS s
  LEFT JOIN latest_pbp p ON CAST(s.game_id AS STRING) = p.game_id
  WHERE s.season = @season AND s.week = @week AND s.game_type = 'REG'
    AND CAST(s.game_id AS STRING) IN (SELECT game_id FROM represented_games)
)
SELECT {', '.join(f'm.{column}' for column in panel_producer.PLAYER_COLUMNS)},
       m.in_frozen_union,
       CASE WHEN NOT m.in_frozen_union THEN NULL
            WHEN UPPER(CAST(m.pos AS STRING)) = 'DST'
            THEN d.dst_dk_points ELSE a.dk_points END
         AS authoritative_actual,
       CASE WHEN NOT m.in_frozen_union THEN NULL
            WHEN UPPER(CAST(m.pos AS STRING)) = 'DST'
            THEN 'team_defense_week.dst_dk_points'
            ELSE 'player_week_actuals.dk_points' END AS actual_source,
       g.game_id AS schedule_game_id,
       g.home_team AS schedule_home_team,
       g.away_team AS schedule_away_team,
       g.home_score, g.away_score,
       g.terminal_home_score, g.terminal_away_score,
       g.terminal_game_status, g.terminal_rule
FROM tagged_mapping m
LEFT JOIN skill_actual a
  ON m.in_frozen_union
  AND UPPER(CAST(m.pos AS STRING)) != 'DST'
  AND a.gsis_id = CAST(m.gsis_id AS STRING)
LEFT JOIN dst_actual d
  ON m.in_frozen_union
  AND UPPER(CAST(m.pos AS STRING)) = 'DST'
  AND d.team = UPPER(CAST(m.team AS STRING))
LEFT JOIN settled_games g
  ON m.in_frozen_union AND g.game_id = CAST(m.game_id AS STRING)
ORDER BY m.panel_run_id, m.season, m.week, m.id
"""
    lowered = sql.lower()
    for forbidden in ("winner", "payout", "ownership"):
        if forbidden in lowered:
            raise AssertionError(f"settlement SQL contains forbidden {forbidden}")
    if "replay_candidates_staging.actual_score" in lowered:
        raise AssertionError("settlement SQL retained the invalid mutable-label source")
    return sql


def _query(
    client: bigquery.Client,
    *,
    sql: str,
    parameters: Sequence[bigquery.QueryParameter],
    job_id: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    job = client.query(
        sql,
        job_id=job_id,
        job_config=bigquery.QueryJobConfig(query_parameters=list(parameters)),
    )
    frame = job.result().to_dataframe(create_bqstorage_client=False)
    return frame, {
        "job_id": str(job.job_id),
        "location": str(job.location or ""),
        "created": job.created.isoformat() if job.created else None,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "query_sha256": sha256(sql.encode("utf-8")).hexdigest(),
    }


def _receipt_rosters(
    receipt: Mapping[str, Any],
    *,
    week: int,
    deployment: Mapping[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    try:
        control, challenger = transport._validate_shadow_receipt(
            receipt, week=week, deployment=deployment
        )
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "generation-pinned shadow receipt does not validate"
        ) from exc
    canonical: list[str] = []
    for roster in sorted(set(control) | set(challenger)):
        try:
            normalized = ",".join(science.canonical_roster(roster))
        except Exception as exc:
            raise AuthoritativeSettlementError(
                "shadow receipt roster identity differs"
            ) from exc
        if roster != normalized:
            raise AuthoritativeSettlementError(
                "shadow receipt roster identity is noncanonical"
            )
        canonical.append(normalized)
    if not canonical:
        raise AuthoritativeSettlementError("shadow receipt roster union is empty")
    return control, challenger, canonical


def _validate_shadow_source(source: object) -> tuple[datetime, datetime, str]:
    expected_keys = {
        "snapshot_id", "snapshot_at", "lock_at", "panels",
        "canonical_panel", "candidate_rows", "deduplicated_rosters",
        "candidate_frame_sha256", "player_frame_sha256", "candidate_query",
        "player_query", "realized_outcome_columns_read",
        "panel_source_receipt_object",
    }
    if not isinstance(source, Mapping) or set(source) != expected_keys:
        raise AuthoritativeSettlementError("shadow source identity schema differs")
    snapshot_at = _utc(source["snapshot_at"], label="shadow snapshot")
    lock_at = _utc(source["lock_at"], label="contest lock")
    panels = source["panels"]
    canonical_panel = source["canonical_panel"]
    if (
        snapshot_at >= lock_at
        or not isinstance(source["snapshot_id"], str)
        or not source["snapshot_id"].strip()
        or not isinstance(panels, list)
        or panels != sorted(set(panels))
        or not panels
        or not isinstance(canonical_panel, str)
        or canonical_panel not in panels
        or type(source["candidate_rows"]) is not int
        or source["candidate_rows"] <= 0
        or type(source["deduplicated_rosters"]) is not int
        or source["deduplicated_rosters"] <= 0
        or _HEX64.fullmatch(str(source["candidate_frame_sha256"])) is None
        or _HEX64.fullmatch(str(source["player_frame_sha256"])) is None
        or source["realized_outcome_columns_read"] != []
    ):
        raise AuthoritativeSettlementError("shadow source identity differs")
    try:
        transport._panel_source_object_identity(
            source["panel_source_receipt_object"]
        )
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "shadow panel-source receipt identity differs"
        ) from exc
    ended: list[datetime] = []
    expected_query_keys = {
        "job_id", "location", "created", "started", "ended",
        "total_bytes_processed", "query_sha256",
    }
    for label in ("candidate_query", "player_query"):
        query = source[label]
        if not isinstance(query, Mapping) or set(query) != expected_query_keys:
            raise AuthoritativeSettlementError("shadow source query schema differs")
        created = _utc(query["created"], label=f"{label} creation")
        started = _utc(query["started"], label=f"{label} start")
        completed = _utc(query["ended"], label=f"{label} completion")
        if (
            not isinstance(query["job_id"], str)
            or not query["job_id"]
            or type(query["total_bytes_processed"]) is not int
            or query["total_bytes_processed"] < 0
            or _HEX64.fullmatch(str(query["query_sha256"])) is None
            or not created <= started <= completed < lock_at
        ):
            raise AuthoritativeSettlementError("shadow source query differs")
        ended.append(completed)
    if max(ended) != snapshot_at:
        raise AuthoritativeSettlementError(
            "shadow snapshot does not equal its query completion"
        )
    return snapshot_at, lock_at, canonical_panel


def _load_panel_source_receipt(
    client: storage.Client,
    *,
    week: int,
    shadow_source: Mapping[str, Any],
    deployment: Mapping[str, Any],
    deployment_object: Mapping[str, Any],
    download: Callable[..., tuple[dict[str, Any], bytes, datetime]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generation-read and validate the sole pre-lock panel source receipt."""
    embedded = shadow_source["panel_source_receipt_object"]
    try:
        checked = transport._panel_source_object_identity(embedded)
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "panel-source receipt object does not validate"
        ) from exc
    expected_uri = panel_producer.canonical_receipt_uri(
        season=SEASON,
        week=week,
        snapshot_id=str(shadow_source["snapshot_id"]),
    )
    if checked["uri"] != expected_uri:
        raise AuthoritativeSettlementError("panel-source receipt URI differs")
    observed, raw, created_at = download(
        client,
        uri=expected_uri,
        generation=str(checked["generation"]),
        label="panel source receipt",
    )
    observed_create_once = {
        **observed,
        "created_at": created_at.isoformat(),
        "create_only": True,
    }
    if observed_create_once != checked:
        raise AuthoritativeSettlementError(
            "panel-source receipt generation/content identity changed"
        )
    receipt = _strict_json(raw, label="panel source receipt")
    if not isinstance(receipt, dict) or raw != _canonical_json(receipt):
        raise AuthoritativeSettlementError("panel source receipt is not canonical")
    current_deployment = {**deployment_object, "create_only": True}
    try:
        receipt = transport._validate_panel_source_receipt(
            receipt,
            receipt_object=checked,
            deployment=deployment,
            deployment_object=current_deployment,
        )
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "generation-pinned panel source receipt does not validate"
        ) from exc

    validation = receipt["validation"]
    shadow_snapshot = _utc(shadow_source["snapshot_at"], label="shadow snapshot")
    source_snapshot = _utc(receipt["snapshot_at"], label="panel source snapshot")
    source_lock = _utc(receipt["lock_at"], label="panel source lock")
    if (
        receipt["season"] != SEASON
        or receipt["week"] != week
        or receipt["code_sha"] != deployment["code"]["commit_sha"]
        or receipt.get("model_artifact_sha256")
        != deployment["historical_license"]["model_artifact_sha256"]
        or receipt["snapshot_id"] != shadow_source["snapshot_id"]
        or receipt["lock_at"] != shadow_source["lock_at"]
        or receipt["panels"] != shadow_source["panels"]
        or receipt["canonical_panel"] != shadow_source["canonical_panel"]
        or validation["candidate_rows"] != shadow_source["candidate_rows"]
        or validation["deduplicated_rosters"]
        != shadow_source["deduplicated_rosters"]
        or source_snapshot > shadow_snapshot
        or shadow_snapshot >= source_lock
    ):
        raise AuthoritativeSettlementError(
            "shadow receipt diverges from its frozen panel source"
        )
    return receipt, checked


def _validate_query_receipt(
    meta: Mapping[str, Any],
    *,
    expected_job_id: str,
    expected_query_sha: str,
    lock_at: datetime,
    attempt_created_at: datetime,
) -> dict[str, Any]:
    expected_keys = {
        "job_id", "location", "created", "started", "ended",
        "total_bytes_processed", "query_sha256",
    }
    if not isinstance(meta, Mapping) or set(meta) != expected_keys:
        raise AuthoritativeSettlementError(
            "authoritative actual query receipt schema differs"
        )
    created = _utc(meta.get("created"), label="actual query creation")
    started = _utc(meta.get("started"), label="actual query start")
    ended = _utc(meta.get("ended"), label="actual query completion")
    if (
        meta.get("job_id") != expected_job_id
        or meta.get("location") != "US"
        or meta.get("query_sha256") != expected_query_sha
        or type(meta.get("total_bytes_processed")) is not int
        or int(meta["total_bytes_processed"]) < 0
        or not attempt_created_at <= created <= started <= ended
        or ended <= lock_at
    ):
        raise AuthoritativeSettlementError(
            "authoritative actual query provenance differs"
        )
    return {
        **dict(meta),
        "created": created.isoformat(),
        "started": started.isoformat(),
        "ended": ended.isoformat(),
    }


def score_exact_union(
    frame: pd.DataFrame,
    *,
    rosters: Sequence[str],
    season: int,
    week: int,
    panels: Sequence[str],
    canonical_panel: str,
    code_sha: str,
    lock_at: datetime,
    expected_player_rows: int,
    expected_player_frame_sha256: str,
    expected_slate_run_id: str,
    expected_config_hash: str,
) -> list[dict[str, Any]]:
    """Validate complete authoritative labels and score only frozen rosters."""
    if (
        type(season) is not int
        or season != SEASON
        or type(week) is not int
        or week not in WEEKS
        or not isinstance(panels, Sequence)
        or list(panels) != sorted(set(panels))
        or not panels
        or not isinstance(canonical_panel, str)
        or canonical_panel not in panels
        or type(expected_player_rows) is not int
        or expected_player_rows <= 0
        or _HEX64.fullmatch(expected_player_frame_sha256) is None
        or not isinstance(expected_slate_run_id, str)
        or not expected_slate_run_id
        or not isinstance(expected_config_hash, str)
        or not expected_config_hash
    ):
        raise AuthoritativeSettlementError("settlement slate/panel boundary differs")
    if frame.empty or set(frame) != set(QUERY_COLUMNS):
        raise AuthoritativeSettlementError("authoritative mapping/result schema differs")
    frame = frame.copy()
    mapping = frame.loc[:, panel_producer.PLAYER_COLUMNS].copy()
    if (
        len(mapping) != expected_player_rows
        or panel_producer._frame_sha(
            mapping, ("panel_run_id", "season", "week", "id")
        ) != expected_player_frame_sha256
    ):
        raise AuthoritativeSettlementError(
            "persisted player mapping differs from the frozen producer frame"
        )
    if (
        mapping.duplicated(["panel_run_id", "season", "week", "id"]).any()
        or set(mapping.panel_run_id.astype(str)) != set(panels)
        or mapping.id.isna().any()
        or not mapping.code_sha.astype(str).eq(code_sha).all()
    ):
        raise AuthoritativeSettlementError("frozen player mapping identity differs")
    generated = mapping.generated_at.map(
        lambda value: _utc(value, label="mapping generated_at")
    )
    if any(value >= lock_at for value in generated):
        raise AuthoritativeSettlementError("DK-to-player mapping was not frozen pre-lock")
    eligible = mapping.research_eligible
    if (
        eligible.isna().any()
        or not pd.api.types.is_bool_dtype(eligible.dtype)
        or eligible.any()
    ):
        raise AuthoritativeSettlementError(
            "pre-lock player mapping eligibility differs"
        )

    expected_ids = {
        player_id
        for roster in rosters
        for player_id in roster.split(",")
    }
    expected_marker = (
        frame.panel_run_id.astype(str).eq(canonical_panel)
        & frame.id.astype(str).isin(expected_ids)
    )
    marker = frame.in_frozen_union
    if (
        marker.isna().any()
        or not pd.api.types.is_bool_dtype(marker.dtype)
        or not marker.eq(expected_marker).all()
    ):
        raise AuthoritativeSettlementError(
            "authoritative query union marker differs"
        )
    outcome_columns = [
        column for column in QUERY_COLUMNS
        if column not in {*panel_producer.PLAYER_COLUMNS, "in_frozen_union"}
    ]
    if frame.loc[~marker, outcome_columns].notna().any().any():
        raise AuthoritativeSettlementError(
            "authoritative query read outcomes outside the frozen roster union"
        )
    scoring = frame.loc[marker].copy()
    scoring["dk_player_id"] = scoring.id.astype(str)
    if (
        scoring.empty
        or scoring.dk_player_id.duplicated().any()
        or set(scoring.dk_player_id) != expected_ids
    ):
        raise AuthoritativeSettlementError(
            "authoritative mapping does not exactly cover the frozen union"
        )
    if (
        not scoring.config_hash.astype(str).eq(expected_config_hash).all()
        or not scoring.slate_run_id.astype(str).eq(expected_slate_run_id).all()
    ):
        raise AuthoritativeSettlementError("mapping code/config/slate identity differs")
    positions = scoring.pos.astype(str).str.upper()
    if not set(positions) <= {"QB", "RB", "WR", "TE", "DST"}:
        raise AuthoritativeSettlementError("mapping position differs")
    skill = positions.ne("DST")
    if (
        scoring.loc[skill, "gsis_id"].isna().any()
        or scoring.loc[skill, "gsis_id"].astype(str).str.strip().eq("").any()
        or scoring.loc[skill, "gsis_id"].astype(str).duplicated().any()
        or scoring.loc[~skill, "team"].isna().any()
        or scoring.loc[~skill, "team"].astype(str).str.strip().eq("").any()
        or scoring.loc[~skill, "team"].astype(str).duplicated().any()
    ):
        raise AuthoritativeSettlementError("DK-to-GSIS/DST mapping is incomplete")
    expected_sources = pd.Series(
        [
            "player_week_actuals.dk_points" if is_skill
            else "team_defense_week.dst_dk_points"
            for is_skill in skill
        ],
        index=scoring.index,
    )
    if not scoring.actual_source.astype(str).eq(expected_sources).all():
        raise AuthoritativeSettlementError("authoritative actual source differs")
    actual = pd.to_numeric(
        scoring.authoritative_actual, errors="raise"
    ).astype(float)
    if actual.isna().any() or not actual.map(math.isfinite).all():
        raise AuthoritativeSettlementError("authoritative labels are incomplete")
    if (
        scoring.schedule_game_id.isna().any()
        or scoring.schedule_game_id.astype(str).str.strip().eq("").any()
        or not scoring.terminal_game_status.astype(str).eq("final").all()
        or scoring.terminal_rule.isna().any()
        or not set(scoring.terminal_rule.astype(str)) <= {
            "latest_pbp_end_game",
        }
    ):
        raise AuthoritativeSettlementError(
            "one or more represented games lack terminal PBP proof"
        )
    schedule_home = scoring.schedule_home_team.astype(str).str.upper()
    schedule_away = scoring.schedule_away_team.astype(str).str.upper()
    if (
        scoring.schedule_home_team.isna().any()
        or scoring.schedule_away_team.isna().any()
        or scoring.schedule_game_id.astype(str).ne(
            scoring.game_id.astype(str)
        ).any()
        or not (
            scoring.loc[~skill, "team"].astype(str).str.upper().eq(
                schedule_home.loc[~skill]
            )
            | scoring.loc[~skill, "team"].astype(str).str.upper().eq(
                schedule_away.loc[~skill]
            )
        ).all()
    ):
        raise AuthoritativeSettlementError("settlement schedule identity differs")
    numeric_scores: dict[str, pd.Series] = {}
    for column in (
        "home_score", "away_score", "terminal_home_score",
        "terminal_away_score",
    ):
        values = pd.to_numeric(scoring[column], errors="raise").astype(float)
        if (
            values.isna().any()
            or not values.map(math.isfinite).all()
            or values.lt(0).any()
            or values.mod(1.0).ne(0.0).any()
        ):
            raise AuthoritativeSettlementError(
                "one or more represented games are not final"
            )
        numeric_scores[column] = values
    if (
        not numeric_scores["home_score"].eq(
            numeric_scores["terminal_home_score"]
        ).all()
        or not numeric_scores["away_score"].eq(
            numeric_scores["terminal_away_score"]
        ).all()
    ):
        raise AuthoritativeSettlementError(
            "schedule and terminal PBP scores disagree"
        )
    lookup = dict(zip(scoring.dk_player_id, actual, strict=True))
    scores: list[dict[str, Any]] = []
    for roster in sorted(rosters):
        ids = roster.split(",")
        if len(ids) != 9 or len(set(ids)) != 9:
            raise AuthoritativeSettlementError("frozen roster identity differs")
        try:
            score = float(sum(lookup[player_id] for player_id in ids))
        except KeyError as exc:
            raise AuthoritativeSettlementError(
                "frozen roster lacks an authoritative label"
            ) from exc
        if not math.isfinite(score):
            raise AuthoritativeSettlementError("frozen roster score is non-finite")
        scores.append({"roster_key": roster, "actual_score": score})
    return scores


def validate_settled_artifact(
    value: object,
    *,
    expected_rosters: set[str],
    week: int,
    lock_at: datetime,
    expected_source_identity: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "season", "week", "labels_complete", "source_identity",
        "scores",
    }:
        raise AuthoritativeSettlementError("settled-score schema differs")
    if (
        value["version"] != SETTLED_VERSION
        or type(value["season"]) is not int
        or value["season"] != SEASON
        or type(value["week"]) is not int
        or value["week"] != week
        or value["labels_complete"] is not True
    ):
        raise AuthoritativeSettlementError("settled-score boundary differs")
    source = value["source_identity"]
    query_sha = sha256(authoritative_settlement_sql().encode("utf-8")).hexdigest()
    source_keys = {
        "source", "attempt_object", "deployment_object",
        "shadow_receipt_object", "panel_source_receipt_object",
        "snapshot_id", "lock_at", "canonical_panel", "panels",
        "player_rows", "player_frame_sha256", "roster_union_sha256",
        "query_parameters", "query_parameters_sha256",
        "query_result_sha256", "query_receipt", "captured_at",
    }
    if (
        not isinstance(source, dict)
        or set(source) != source_keys
        or source != dict(expected_source_identity)
        or source["source"] != SOURCE_NAME
        or source["lock_at"] != lock_at.isoformat()
        or not isinstance(source["snapshot_id"], str)
        or not source["snapshot_id"]
        or not isinstance(source["canonical_panel"], str)
        or not isinstance(source["panels"], list)
        or source["panels"] != sorted(set(source["panels"]))
        or source["canonical_panel"] not in source["panels"]
        or type(source["player_rows"]) is not int
        or source["player_rows"] <= 0
        or _HEX64.fullmatch(str(source["player_frame_sha256"])) is None
        or _HEX64.fullmatch(str(source["roster_union_sha256"])) is None
        or _HEX64.fullmatch(str(source["query_parameters_sha256"])) is None
        or _HEX64.fullmatch(str(source["query_result_sha256"])) is None
        or not isinstance(source["query_parameters"], dict)
        or sha256(_canonical_json(source["query_parameters"])).hexdigest()
        != source["query_parameters_sha256"]
    ):
        raise AuthoritativeSettlementError("settled-score source identity differs")
    for label, identity in (
        ("settlement attempt", source["attempt_object"]),
        ("deployment", source["deployment_object"]),
        ("shadow receipt", source["shadow_receipt_object"]),
        ("panel source receipt", source["panel_source_receipt_object"]),
    ):
        try:
            transport._panel_source_object_identity(identity)
        except Exception as exc:
            raise AuthoritativeSettlementError(
                f"settled-score {label} identity differs"
            ) from exc
    uris = transport._week_uris(week)
    expected_panel_uri = panel_producer.canonical_receipt_uri(
        season=SEASON, week=week, snapshot_id=source["snapshot_id"]
    )
    if (
        source["attempt_object"]["uri"] != uris["settlement_attempt"]
        or source["deployment_object"]["uri"] != transport.DEPLOYMENT_URI
        or source["shadow_receipt_object"]["uri"] != uris["shadow_receipt"]
        or source["panel_source_receipt_object"]["uri"] != expected_panel_uri
    ):
        raise AuthoritativeSettlementError(
            "settled-score frozen input URI differs"
        )
    attempt_created = _utc(
        source["attempt_object"]["created_at"],
        label="settlement attempt creation",
    )
    shadow_created = _utc(
        source["shadow_receipt_object"]["created_at"],
        label="shadow receipt creation",
    )
    panel_created = _utc(
        source["panel_source_receipt_object"]["created_at"],
        label="panel source receipt creation",
    )
    expected_parameters = {
        "canonical_panel": source["canonical_panel"],
        "panels": source["panels"],
        "season": SEASON,
        "week": week,
        "dk_player_ids": sorted({
            player_id
            for roster in expected_rosters
            for player_id in roster.split(",")
        }),
    }
    expected_roster_sha = sha256(_canonical_json({
        "rosters": sorted(expected_rosters)
    })).hexdigest()
    expected_job_id = (
        f"b1_authoritative_settle_{SEASON}_w{week:02d}_"
        f"{source['shadow_receipt_object']['sha256']}"
    )
    if (
        source["query_parameters"] != expected_parameters
        or source["roster_union_sha256"] != expected_roster_sha
        or not panel_created <= shadow_created < lock_at < attempt_created
    ):
        raise AuthoritativeSettlementError(
            "settled-score frozen chronology/parameter identity differs"
        )
    query_receipt = source["query_receipt"]
    normalized_query = _validate_query_receipt(
        query_receipt,
        expected_job_id=expected_job_id,
        expected_query_sha=query_sha,
        lock_at=lock_at,
        attempt_created_at=attempt_created,
    )
    captured = _utc(source["captured_at"], label="settled capture")
    if (
        normalized_query != query_receipt
        or captured.isoformat() != normalized_query["ended"]
        or captured <= lock_at
    ):
        raise AuthoritativeSettlementError("settled-score query identity differs")
    rows = value["scores"]
    if not isinstance(rows, list):
        raise AuthoritativeSettlementError("settled scores are absent")
    observed: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"roster_key", "actual_score"}:
            raise AuthoritativeSettlementError("settled-score row schema differs")
        key = row["roster_key"]
        score = row["actual_score"]
        if (
            not isinstance(key, str)
            or key in observed
            or isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
        ):
            raise AuthoritativeSettlementError("settled-score row differs")
        observed[key] = float(score)
    if set(observed) != expected_rosters:
        raise AuthoritativeSettlementError(
            "settled scores do not exactly cover the frozen union"
        )
    return value


def materialize(
    *,
    week: int,
    shadow_receipt_generation: str,
    deployment_generation: str,
    storage_client: storage.Client,
    bigquery_client: bigquery.Client,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    download: Callable[..., tuple[dict[str, Any], bytes, datetime]] = _download_generation,
    upload: Callable[..., dict[str, Any]] = _upload_create_once,
    query: Callable[..., tuple[pd.DataFrame, dict[str, Any]]] = _query,
) -> dict[str, Any]:
    """Materialize one exact post-settlement score union, without mutation."""
    if os.environ.get(ENABLED_ENV, "0") != "1":
        raise AuthoritativeSettlementError(f"{ENABLED_ENV}=1 is required explicitly")
    if type(week) is not int or week not in WEEKS:
        raise AuthoritativeSettlementError("settlement week must be 2026 Week 1-6")
    if _GENERATION.fullmatch(str(shadow_receipt_generation)) is None:
        raise AuthoritativeSettlementError("shadow receipt generation differs")
    if _GENERATION.fullmatch(str(deployment_generation)) is None:
        raise AuthoritativeSettlementError("deployment generation differs")

    deployment_object, deployment_raw, deployment_created_at = download(
        storage_client,
        uri=transport.DEPLOYMENT_URI,
        generation=deployment_generation,
        label="deployment",
    )
    deployment = _strict_json(deployment_raw, label="deployment")
    if deployment_raw != _canonical_json(deployment):
        raise AuthoritativeSettlementError("deployment is not canonical")
    try:
        deployment = transport._validate_deployment(deployment)
        transport._validate_runtime_environment(deployment, freeze=False)
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "settlement runtime deployment does not validate"
        ) from exc
    code_sha = str(deployment["code"]["commit_sha"])
    if _HEX40.fullmatch(code_sha) is None:
        raise AuthoritativeSettlementError("settlement code SHA differs")

    uris = transport._week_uris(week)
    receipt_object, receipt_raw, receipt_created_at = download(
        storage_client,
        uri=uris["shadow_receipt"],
        generation=shadow_receipt_generation,
        label="shadow receipt",
    )
    receipt = _strict_json(receipt_raw, label="shadow receipt")
    if receipt_raw != _canonical_json(receipt):
        raise AuthoritativeSettlementError("shadow receipt is not canonical")
    control, challenger, rosters = _receipt_rosters(
        receipt, week=week, deployment=deployment
    )
    source = receipt.get("source_identity")
    snapshot_at, lock_at, _ = _validate_shadow_source(source)
    if not snapshot_at <= receipt_created_at < lock_at:
        raise AuthoritativeSettlementError(
            "generation-pinned shadow receipt creation time differs"
        )
    if not isinstance(source, Mapping):
        raise AuthoritativeSettlementError("shadow source identity is absent")
    panel_receipt, panel_receipt_object = _load_panel_source_receipt(
        storage_client,
        week=week,
        shadow_source=source,
        deployment=deployment,
        deployment_object=deployment_object,
        download=download,
    )
    validation = panel_receipt["validation"]
    panels = list(panel_receipt["panels"])
    canonical_panel = str(panel_receipt["canonical_panel"])
    canonical_mapping = validation["panel_rows"][canonical_panel]
    lock_at = _utc(panel_receipt["lock_at"], label="panel source lock")
    settlement_started = _utc(now(), label="settlement start")
    if settlement_started <= lock_at:
        raise AuthoritativeSettlementError("settlement cannot start before lock")

    expected_ids = sorted({
        player_id for roster in rosters for player_id in roster.split(",")
    })
    roster_union_sha = sha256(
        _canonical_json({"rosters": rosters})
    ).hexdigest()
    sql = authoritative_settlement_sql()
    query_sha = sha256(sql.encode("utf-8")).hexdigest()
    query_parameters = {
        "canonical_panel": canonical_panel,
        "panels": panels,
        "season": SEASON,
        "week": week,
        "dk_player_ids": expected_ids,
    }
    query_parameters_sha = sha256(
        _canonical_json(query_parameters)
    ).hexdigest()
    expected_job_id = (
        f"b1_authoritative_settle_{SEASON}_w{week:02d}_"
        f"{receipt_object['sha256']}"
    )
    attempt = {
        "version": ATTEMPT_VERSION,
        "season": SEASON,
        "week": week,
        "deployment_object": {
            **deployment_object,
            "created_at": deployment_created_at.isoformat(),
            "create_only": True,
        },
        "shadow_receipt_object": {
            **receipt_object,
            "created_at": receipt_created_at.isoformat(),
            "create_only": True,
        },
        "panel_source_receipt_object": panel_receipt_object,
        "snapshot_id": panel_receipt["snapshot_id"],
        "lock_at": lock_at.isoformat(),
        "canonical_panel": canonical_panel,
        "panels": panels,
        "player_rows": validation["player_rows"],
        "player_frame_sha256": validation["player_frame_sha256"],
        "control_entries": len(control),
        "challenger_entries": len(challenger),
        "roster_union_count": len(rosters),
        "roster_union_sha256": roster_union_sha,
        "source": SOURCE_NAME,
        "query_job_id": expected_job_id,
        "query_sha256": query_sha,
        "query_parameters": query_parameters,
        "query_parameters_sha256": query_parameters_sha,
        "output_uri": uris["settled_scores"],
        "outcomes_queried_at_creation": False,
        "prelock_rows_mutated": False,
        "retry_licensed": False,
        "production_licensed": False,
    }
    attempt_object = upload(
        storage_client,
        uri=uris["settlement_attempt"],
        value=attempt,
    )
    try:
        attempt_object = transport._panel_source_object_identity(
            attempt_object, uri=uris["settlement_attempt"]
        )
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "create-only settlement attempt identity differs"
        ) from exc
    attempt_created_at = _utc(
        attempt_object.get("created_at"), label="settlement attempt creation"
    )
    if attempt_created_at <= lock_at:
        raise AuthoritativeSettlementError(
            "settlement attempt was not created after lock"
        )

    frame, query_meta = query(
        bigquery_client,
        sql=sql,
        parameters=[
            bigquery.ScalarQueryParameter(
                "canonical_panel", "STRING", canonical_panel
            ),
            bigquery.ArrayQueryParameter("panels", "STRING", panels),
            bigquery.ScalarQueryParameter("season", "INT64", SEASON),
            bigquery.ScalarQueryParameter("week", "INT64", week),
            bigquery.ArrayQueryParameter("dk_player_ids", "STRING", expected_ids),
        ],
        job_id=expected_job_id,
    )
    query_receipt = _validate_query_receipt(
        query_meta,
        expected_job_id=expected_job_id,
        expected_query_sha=query_sha,
        lock_at=lock_at,
        attempt_created_at=attempt_created_at,
    )
    captured_at = _utc(
        query_receipt["ended"], label="actual query completion"
    )
    scores = score_exact_union(
        frame,
        rosters=rosters,
        season=SEASON,
        week=week,
        panels=panels,
        canonical_panel=canonical_panel,
        code_sha=code_sha,
        lock_at=lock_at,
        expected_player_rows=validation["player_rows"],
        expected_player_frame_sha256=validation["player_frame_sha256"],
        expected_slate_run_id=canonical_mapping["slate_run_id"],
        expected_config_hash=canonical_mapping["config_hash"],
    )
    query_result_sha = panel_producer._frame_sha(
        frame, ("panel_run_id", "season", "week", "id")
    )
    source_identity = {
        "source": SOURCE_NAME,
        "attempt_object": attempt_object,
        "deployment_object": attempt["deployment_object"],
        "shadow_receipt_object": attempt["shadow_receipt_object"],
        "panel_source_receipt_object": panel_receipt_object,
        "snapshot_id": panel_receipt["snapshot_id"],
        "lock_at": lock_at.isoformat(),
        "canonical_panel": canonical_panel,
        "panels": panels,
        "player_rows": validation["player_rows"],
        "player_frame_sha256": validation["player_frame_sha256"],
        "roster_union_sha256": roster_union_sha,
        "query_parameters": query_parameters,
        "query_parameters_sha256": query_parameters_sha,
        "query_result_sha256": query_result_sha,
        "query_receipt": query_receipt,
        "captured_at": captured_at.isoformat(),
    }
    artifact = {
        "version": SETTLED_VERSION,
        "season": SEASON,
        "week": week,
        "labels_complete": True,
        "source_identity": source_identity,
        "scores": scores,
    }
    validate_settled_artifact(
        artifact,
        expected_rosters=set(rosters),
        week=week,
        lock_at=lock_at,
        expected_source_identity=source_identity,
    )
    scores_object = upload(
        storage_client,
        uri=uris["settled_scores"],
        value=artifact,
    )
    try:
        scores_object = transport._panel_source_object_identity(
            scores_object, uri=uris["settled_scores"]
        )
    except Exception as exc:
        raise AuthoritativeSettlementError(
            "create-only settled-score identity differs"
        ) from exc
    if _utc(
        scores_object.get("created_at"), label="score artifact creation"
    ) < captured_at:
        raise AuthoritativeSettlementError(
            "settled-score artifact predates its authoritative query"
        )
    return {
        "version": "b1-corpus-tail-authoritative-settlement-publication-v2",
        "season": SEASON,
        "week": week,
        "attempt_object": attempt_object,
        "scores_object": scores_object,
        "labels_complete": True,
        "roster_union_count": len(rosters),
        "prelock_rows_mutated": False,
        "production_licensed": False,
    }


def _args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", type=int, required=True, choices=WEEKS)
    parser.add_argument("--shadow-receipt-generation", required=True)
    parser.add_argument("--deployment-generation", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _args(argv)
    if os.environ.get(ENABLED_ENV, "0") != "1":
        raise AuthoritativeSettlementError(
            f"{ENABLED_ENV}=1 is required explicitly"
        )
    result = materialize(
        week=args.week,
        shadow_receipt_generation=args.shadow_receipt_generation,
        deployment_generation=args.deployment_generation,
        storage_client=storage.Client(project=PROJECT),
        bigquery_client=bigquery.Client(project=PROJECT),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
