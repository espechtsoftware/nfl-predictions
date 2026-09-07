"""Canonical-game successor for paid DraftKings NFL Classic books.

Version 2 remains frozen for compatibility.  This successor keeps its exact-K,
fresh-salary, active-status, and upload-byte checks, then independently joins
the current salary slate to the current projection batch and the authoritative
NFL schedule.  Final game semantics are recomputed from that joined catalog;
``opp`` and ``game_id`` values carried by a selected lineup are claims to
verify, never the source of truth.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

import pandas as pd

from .game_identity import (
    CANONICAL_GAME_POLICY_ID,
    audit_classic_roster_semantics,
    canonical_game_identities,
    canonical_game_key,
    normalize_team,
)
from .lineup import Lineup
from .paid_classic_book_v2 import (
    PAID_CLASSIC_BOUNDARY_ID as PAID_CLASSIC_BOUNDARY_ID_V2,
)
from .paid_classic_book_v2 import (
    PaidClassicCatalog,
    PaidClassicExport,
    assert_exact_unique_classic_book_v2,
    build_paid_classic_catalog_v2,
    fill_paid_entries_csv_v2,
    paid_entry_count_v2,
    to_paid_dk_csv_v2,
    validate_paid_classic_book_v2,
)

PAID_CLASSIC_BOUNDARY_ID: Final = "paid-classic-book-boundary-v3-canonical-game"
PAID_CLASSIC_GAME_CATALOG_SCHEMA: Final = (
    "paid-classic-authoritative-game-catalog/v3"
)
PAID_CLASSIC_PROJECTION_DERIVATION_ID: Final = (
    "certified-coherent-batch-centered-simulation/v1"
)
PAID_CLASSIC_SOURCE_COMMIT_ENV: Final = "IMAGE_SOURCE_COMMIT_SHA"
PAID_CLASSIC_IMAGE_DIGEST_ENV: Final = "IMAGE_DIGEST"
PAID_CLASSIC_IMAGE_URI_ENV: Final = "IMAGE_URI"
PAID_CLASSIC_BUILD_ID_ENV: Final = "PAID_V3_CLOUD_BUILD_ID"
PAID_CLASSIC_REVISION_ENV: Final = "K_REVISION"
_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
_COMMIT_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_BUILD_ID_RE: Final = re.compile(
    r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$"
)
_IMAGE_URI_RE: Final = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_REVISION_RE: Final = re.compile(r"^[a-z][a-z0-9-]{0,62}$")
_ENGINE_RECEIPT_SCHEMA: Final = "paid-classic-engine-transformation/v2"
_PROJECTION_AUTHORITY_SCHEMA: Final = "paid-classic-projection-authority/v2"
_ENGINE_RECEIPT_ISSUER: Final = object()


@dataclass(frozen=True)
class PaidClassicCatalogV3:
    """Fresh DK salary identity joined to projection and schedule facts."""

    draft_group_id: int
    season: int
    week: int
    salary_catalog: PaidClassicCatalog
    by_player_id: Mapping[int, Mapping[str, Any]]
    sha256: str
    rows: int
    projection_generated_at: str
    projection_batch_sha256: str
    projection_distribution_columns: tuple[str, ...]
    projection_derivation_id: str
    schedule_sha256: str
    schedule_games: int
    validated_at: str
    slate_lock_at: str
    source_commit_sha: str
    immutable_image_digest: str
    cloud_build_id: str
    immutable_image_uri: str
    running_revision: str
    runtime_deployment_identity_sha256: str


@dataclass(frozen=True)
class PaidClassicProjectionAuthorityV3:
    """Opaque, catalog-derived authority passed into the lineup engine.

    This object contains no caller-supplied transformation claim.  The engine
    consumes it before execution and emits a separate sealed receipt only
    after it has produced the selected book.
    """

    payload_json: str

    def as_dict(self) -> dict[str, object]:
        return json.loads(self.payload_json)


class PaidClassicEngineReceiptV3:
    """Engine-issued immutable evidence for a completed transformation."""

    __slots__ = ("_payload_json",)

    def __init__(self, payload: Mapping[str, object], *, _issuer: object) -> None:
        if _issuer is not _ENGINE_RECEIPT_ISSUER:
            raise TypeError("paid-v3 engine receipts can only be issued by the engine")
        self._payload_json = json.dumps(
            dict(payload), sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, allow_nan=False,
        )

    def as_dict(self) -> dict[str, object]:
        return json.loads(self._payload_json)

    def __deepcopy__(self, memo):
        return self


def _fail(message: str) -> None:
    raise ValueError(f"{PAID_CLASSIC_BOUNDARY_ID}: {message}")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_paid_classic_runtime_identity_v3(
    source_commit_sha: object,
    immutable_image_digest: object,
) -> tuple[str, str]:
    """Validate the immutable release coordinates required at money time."""

    commit = str(source_commit_sha or "").strip()
    digest = str(immutable_image_digest or "").strip()
    if _COMMIT_RE.fullmatch(commit) is None:
        _fail("source commit must be the full 40-character commit SHA")
    if _DIGEST_RE.fullmatch(digest) is None:
        _fail("image digest must be an immutable sha256 digest")
    return commit, digest


def validate_paid_classic_deployment_identity_v3(
    *,
    source_commit_sha: object,
    immutable_image_digest: object,
    cloud_build_id: object,
    immutable_image_uri: object,
    running_revision: object,
) -> dict[str, str]:
    """Validate the runtime half of a provider-attested deployment."""

    commit, digest = validate_paid_classic_runtime_identity_v3(
        source_commit_sha, immutable_image_digest
    )
    build_id = str(cloud_build_id or "").strip()
    image_uri = str(immutable_image_uri or "").strip()
    revision = str(running_revision or "").strip()
    if _BUILD_ID_RE.fullmatch(build_id) is None:
        _fail("Cloud Build ID must be a full provider build identity")
    if _IMAGE_URI_RE.fullmatch(image_uri) is None or image_uri.rsplit(
        "@", 1
    )[1] != digest:
        _fail("runtime image URI must be immutable and match IMAGE_DIGEST")
    if _REVISION_RE.fullmatch(revision) is None:
        _fail("running Cloud Run revision is missing or malformed")
    body = {
        "source_commit_sha": commit,
        "immutable_image_digest": digest,
        "cloud_build_id": build_id,
        "immutable_image_uri": image_uri,
        "running_revision": revision,
    }
    body["runtime_deployment_identity_sha256"] = _canonical_sha256(body)
    return body


def _integer(value: Any, *, label: str, positive: bool = True) -> int:
    if isinstance(value, bool):
        _fail(f"{label} must be an integer")
    try:
        parsed = int(value)
        exact = float(value) == float(parsed)
    except (TypeError, ValueError, OverflowError):
        _fail(f"{label} must be an integer")
    if not exact:
        _fail(f"{label} must be an integer")
    if positive and parsed <= 0:
        _fail(f"{label} must be positive")
    return parsed


def _text(value: Any, *, label: str) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        _fail(f"{label} is missing")
    parsed = str(value).strip()
    if not parsed or parsed.upper() in {"NAN", "NONE", "NULL"}:
        _fail(f"{label} is missing")
    return parsed


def _timestamp(value: Any, *, label: str) -> pd.Timestamp:
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError, OverflowError):
        _fail(f"{label} must be a timezone-aware timestamp")
    if pd.isna(parsed) or parsed.tzinfo is None:
        _fail(f"{label} must be a timezone-aware timestamp")
    return parsed.tz_convert("UTC")


def _position(value: Any, *, label: str) -> str:
    position = _text(value, label=label).upper()
    if position in {"DEF", "D/ST"}:
        position = "DST"
    if position not in _POSITIONS:
        _fail(f"{label} has unsupported position {position!r}")
    return position


def _translate_v2_error(exc: ValueError) -> None:
    message = str(exc)
    prefix = f"{PAID_CLASSIC_BOUNDARY_ID_V2}: "
    _fail(message.removeprefix(prefix))


def build_paid_classic_catalog_v3(
    salary_rows: pd.DataFrame,
    projection_rows: pd.DataFrame,
    schedule_rows: pd.DataFrame,
    *,
    draft_group_id: int,
    season: int,
    week: int,
    source_commit_sha: str,
    immutable_image_digest: str,
    cloud_build_id: str,
    immutable_image_uri: str,
    running_revision: str,
    validated_at: datetime | pd.Timestamp | None = None,
) -> PaidClassicCatalogV3:
    """Build a fail-closed salary/projection/schedule authority join.

    Salary rows provide current slate eligibility and upload IDs.  Projection
    rows provide the pre-lock player-to-team/opponent relation.  Schedule rows
    independently authenticate that relation and provide the provider game ID.
    Canonical team aliases are applied only while comparing these authorities;
    every raw source value remains represented in the catalog identity.
    """

    gid = _integer(draft_group_id, label="draft_group_id")
    target_season = _integer(season, label="season")
    target_week = _integer(week, label="week")
    deployment = validate_paid_classic_deployment_identity_v3(
        source_commit_sha=source_commit_sha,
        immutable_image_digest=immutable_image_digest,
        cloud_build_id=cloud_build_id,
        immutable_image_uri=immutable_image_uri,
        running_revision=running_revision,
    )
    source_commit = deployment["source_commit_sha"]
    image_digest = deployment["immutable_image_digest"]
    if validated_at is None:
        _fail("validated_at is required")
    validation_time = _timestamp(validated_at, label="validated_at")
    try:
        salary_catalog = build_paid_classic_catalog_v2(
            salary_rows,
            draft_group_id=gid,
            validated_at=validated_at,
        )
    except ValueError as exc:
        _translate_v2_error(exc)

    salary_records = salary_rows.to_dict("records")
    target_salary_records = [
        row for row in salary_records
        if _integer(row.get("draft_group_id"), label="salary draft_group_id")
        == gid
    ]
    if not target_salary_records or any(
        "game_start" not in row for row in target_salary_records
    ):
        _fail("salary authority lacks a slate-lock timestamp")
    salary_game_starts = [
        _timestamp(row.get("game_start"), label="salary game_start")
        for row in target_salary_records
    ]
    slate_lock = min(salary_game_starts)
    if validation_time >= slate_lock:
        _fail("validation timestamp reaches or follows slate lock")

    if not isinstance(projection_rows, pd.DataFrame) or projection_rows.empty:
        _fail("projection authority is empty")
    projection_required = {
        "generated_at",
        "season",
        "week",
        "dk_player_id",
        "position",
        "team",
        "opponent",
        "proj_points",
    }
    missing = projection_required - set(projection_rows.columns)
    if missing:
        _fail("projection authority is missing " + ", ".join(sorted(missing)))
    distribution_columns = ("proj_p50", "proj_p90", "proj_std")
    present_distribution_columns = tuple(
        column for column in distribution_columns
        if column in projection_rows.columns
    )
    if present_distribution_columns not in ((), distribution_columns):
        _fail(
            "projection authority must provide proj_p50, proj_p90, and "
            "proj_std together"
        )

    projections: dict[int, dict[str, Any]] = {}
    projection_batch_identity: list[dict[str, Any]] = []
    projection_batch_values: set[int] = set()
    for ordinal, row in enumerate(projection_rows.to_dict("records"), start=1):
        row_season = _integer(
            row.get("season"), label=f"projection row {ordinal} season"
        )
        row_week = _integer(row.get("week"), label=f"projection row {ordinal} week")
        if row_season != target_season or row_week != target_week:
            _fail(
                f"projection row {ordinal} is for {row_season}-W{row_week}, "
                f"not {target_season}-W{target_week}"
            )
        player_id = _integer(
            row.get("dk_player_id"),
            label=f"projection row {ordinal} dk_player_id",
        )
        if player_id in projections:
            _fail("projection authority has duplicate player IDs")
        try:
            team = normalize_team(
                row.get("team"), label=f"projection row {ordinal} team"
            )
            opponent = normalize_team(
                row.get("opponent"),
                label=f"projection row {ordinal} opponent",
            )
            game_key = canonical_game_key(team, opponent)
        except ValueError as exc:
            _fail(f"projection row {ordinal} has invalid game facts: {exc}")
        generated_at = _timestamp(
            row.get("generated_at"),
            label=f"projection row {ordinal} generated_at",
        )
        projection_batch_values.add(int(generated_at.value))
        try:
            projection_points = float(row.get("proj_points"))
        except (TypeError, ValueError, OverflowError):
            _fail(f"projection row {ordinal} proj_points is invalid")
        if not math.isfinite(projection_points):
            _fail(f"projection row {ordinal} proj_points is invalid")
        distribution: dict[str, float] = {}
        for column in present_distribution_columns:
            try:
                value = float(row.get(column))
            except (TypeError, ValueError, OverflowError):
                _fail(f"projection row {ordinal} {column} is invalid")
            if not math.isfinite(value):
                _fail(f"projection row {ordinal} {column} is invalid")
            if column == "proj_std" and value <= 0:
                _fail(f"projection row {ordinal} proj_std must be positive")
            distribution[column] = value
        if distribution and distribution["proj_p50"] > distribution["proj_p90"]:
            _fail(f"projection row {ordinal} has proj_p50 above proj_p90")
        projections[player_id] = {
            "player_id": player_id,
            "position": _position(
                row.get("position"), label=f"projection row {ordinal} position"
            ),
            "team": team,
            "opponent": opponent,
            "canonical_game_key": game_key,
            "generated_at": generated_at,
            "projection": projection_points,
            **distribution,
            "raw_team": _text(
                row.get("team"), label=f"projection row {ordinal} team"
            ),
            "raw_opponent": _text(
                row.get("opponent"),
                label=f"projection row {ordinal} opponent",
            ),
        }
        projection_batch_identity.append(
            {
                "dk_player_id": player_id,
                "generated_at": generated_at.isoformat(),
                "season": row_season,
                "week": row_week,
                "position": projections[player_id]["position"],
                "team": team,
                "opponent": opponent,
                "proj_points": projection_points,
                **distribution,
            }
        )

    if len(projection_batch_values) != 1:
        _fail("projection authority mixes generated_at batches")
    projection_batch_time = pd.Timestamp(
        next(iter(projection_batch_values)), unit="ns", tz="UTC"
    )
    if projection_batch_time > validation_time:
        _fail("projection batch is later than validation time")
    if projection_batch_time >= slate_lock:
        _fail("projection batch reaches or follows slate lock")
    projection_batch_identity.sort(key=lambda row: int(row["dk_player_id"]))
    projection_batch_sha256 = _canonical_sha256(projection_batch_identity)

    if not isinstance(schedule_rows, pd.DataFrame) or schedule_rows.empty:
        _fail("schedule authority is empty")
    schedule_required = {
        "game_id",
        "season",
        "week",
        "home_team",
        "away_team",
    }
    missing = schedule_required - set(schedule_rows.columns)
    if missing:
        _fail("schedule authority is missing " + ", ".join(sorted(missing)))

    schedule_by_key: dict[str, dict[str, Any]] = {}
    schedule_ids: set[str] = set()
    for ordinal, row in enumerate(schedule_rows.to_dict("records"), start=1):
        row_season = _integer(
            row.get("season"), label=f"schedule row {ordinal} season"
        )
        row_week = _integer(row.get("week"), label=f"schedule row {ordinal} week")
        if row_season != target_season or row_week != target_week:
            _fail(
                f"schedule row {ordinal} is for {row_season}-W{row_week}, "
                f"not {target_season}-W{target_week}"
            )
        if "game_type" in row and _text(
            row.get("game_type"), label=f"schedule row {ordinal} game_type"
        ).upper() != "REG":
            _fail(f"schedule row {ordinal} is not a regular-season game")
        raw_game_id = _text(
            row.get("game_id"), label=f"schedule row {ordinal} game_id"
        )
        try:
            home = normalize_team(
                row.get("home_team"), label=f"schedule row {ordinal} home_team"
            )
            away = normalize_team(
                row.get("away_team"), label=f"schedule row {ordinal} away_team"
            )
            game_key = canonical_game_key(home, away)
        except ValueError as exc:
            _fail(f"schedule row {ordinal} has invalid game facts: {exc}")
        if game_key in schedule_by_key:
            _fail(f"schedule authority has duplicate canonical game {game_key}")
        if raw_game_id in schedule_ids:
            _fail(f"schedule authority has duplicate game_id {raw_game_id}")
        schedule_ids.add(raw_game_id)
        schedule_by_key[game_key] = {
            "canonical_game_key": game_key,
            "schedule_game_id": raw_game_id,
            "home_team": home,
            "away_team": away,
            "raw_home_team": _text(
                row.get("home_team"),
                label=f"schedule row {ordinal} home_team",
            ),
            "raw_away_team": _text(
                row.get("away_team"),
                label=f"schedule row {ordinal} away_team",
            ),
        }

    joined: list[dict[str, Any]] = []
    generated_at_values: set[int] = set()
    for player_id, salary in salary_catalog.by_player_id.items():
        projection = projections.get(int(player_id))
        if projection is None:
            continue
        try:
            salary_team = normalize_team(
                salary["team"], label=f"salary player {player_id} team"
            )
        except ValueError as exc:
            _fail(f"salary player {player_id} has invalid team: {exc}")
        if salary_team != projection["team"]:
            _fail(
                f"player {player_id} salary/projection teams disagree after aliases"
            )
        if str(salary["pos"]) != projection["position"]:
            _fail(f"player {player_id} salary/projection positions disagree")
        schedule = schedule_by_key.get(str(projection["canonical_game_key"]))
        if schedule is None:
            _fail(f"player {player_id} projection game is absent from the schedule")
        generated_at = projection["generated_at"]
        generated_at_values.add(int(generated_at.value))
        joined.append(
            {
                "player_id": int(player_id),
                "draftable_id": int(salary["draftable_id"]),
                "name": str(salary["name"]),
                "pos": str(salary["pos"]),
                "salary": int(salary["salary"]),
                "status": str(salary["status"]),
                "salary_team": str(salary["team"]),
                "projection_team_raw": str(projection["raw_team"]),
                "projection_opponent_raw": str(projection["raw_opponent"]),
                "team": str(projection["team"]),
                "opponent": str(projection["opponent"]),
                "canonical_game_key": str(projection["canonical_game_key"]),
                "schedule_game_id": str(schedule["schedule_game_id"]),
                "projection": float(projection["projection"]),
                **{
                    column: float(projection[column])
                    for column in present_distribution_columns
                },
            }
        )

    if not joined:
        _fail("salary and projection authorities have no joined players")
    if len(generated_at_values) != 1:
        _fail("joined projection authority mixes generated_at batches")
    # Detect a team being assigned different opponents before any selected
    # roster can exploit an internally contradictory catalog.
    try:
        canonical_game_identities(
            [
                {
                    "id": row["player_id"],
                    "team": row["team"],
                    "opp": row["opponent"],
                    "game_id": row["schedule_game_id"],
                }
                for row in joined
            ]
        )
    except ValueError as exc:
        _fail(f"joined game authority is ambiguous: {exc}")

    joined.sort(key=lambda row: row["player_id"])
    schedule_identity = [schedule_by_key[key] for key in sorted(schedule_by_key)]
    schedule_sha256 = _canonical_sha256(schedule_identity)
    projection_generated_at = pd.Timestamp(
        next(iter(generated_at_values)), unit="ns", tz="UTC"
    ).isoformat()
    identity = {
        "schema_version": PAID_CLASSIC_GAME_CATALOG_SCHEMA,
        "canonical_game_policy_id": CANONICAL_GAME_POLICY_ID,
        "draft_group_id": gid,
        "season": target_season,
        "week": target_week,
        "salary_catalog_sha256": salary_catalog.sha256,
        "projection_generated_at": projection_generated_at,
        "projection_batch_sha256": projection_batch_sha256,
        "projection_distribution_columns": list(
            present_distribution_columns
        ),
        "projection_derivation_id": PAID_CLASSIC_PROJECTION_DERIVATION_ID,
        "source_commit_sha": source_commit,
        "immutable_image_digest": image_digest,
        "cloud_build_id": deployment["cloud_build_id"],
        "immutable_image_uri": deployment["immutable_image_uri"],
        "running_revision": deployment["running_revision"],
        "runtime_deployment_identity_sha256": deployment[
            "runtime_deployment_identity_sha256"
        ],
        "validated_at": validation_time.isoformat(),
        "slate_lock_at": slate_lock.isoformat(),
        "schedule_sha256": schedule_sha256,
        "players": joined,
    }
    return PaidClassicCatalogV3(
        draft_group_id=gid,
        season=target_season,
        week=target_week,
        salary_catalog=salary_catalog,
        by_player_id={int(row["player_id"]): row for row in joined},
        sha256=_canonical_sha256(identity),
        rows=len(joined),
        projection_generated_at=projection_generated_at,
        projection_batch_sha256=projection_batch_sha256,
        projection_distribution_columns=present_distribution_columns,
        projection_derivation_id=PAID_CLASSIC_PROJECTION_DERIVATION_ID,
        schedule_sha256=schedule_sha256,
        schedule_games=len(schedule_identity),
        validated_at=validation_time.isoformat(),
        slate_lock_at=slate_lock.isoformat(),
        source_commit_sha=source_commit,
        immutable_image_digest=image_digest,
        cloud_build_id=deployment["cloud_build_id"],
        immutable_image_uri=deployment["immutable_image_uri"],
        running_revision=deployment["running_revision"],
        runtime_deployment_identity_sha256=deployment[
            "runtime_deployment_identity_sha256"
        ],
    )


def _claimed_opponent(player: Mapping[str, Any], *, label: str) -> str:
    values = []
    for field in ("opp", "opponent"):
        if player.get(field) is not None:
            try:
                values.append(normalize_team(player[field], label=f"{label} {field}"))
            except ValueError as exc:
                _fail(f"{label} has invalid {field}: {exc}")
    if not values:
        _fail(f"{label} opponent claim is missing")
    if len(set(values)) != 1:
        _fail(f"{label} opp and opponent claims disagree")
    return values[0]


def _claimed_game_matches_authority(token: Any, source: Mapping[str, Any]) -> bool:
    claimed = _text(token, label="lineup game_id claim")
    if claimed == str(source["schedule_game_id"]):
        return True
    if claimed == str(source["canonical_game_key"]):
        return True
    for separator in ("@", "|"):
        parts = claimed.split(separator)
        if len(parts) != 2:
            continue
        try:
            return canonical_game_key(parts[0], parts[1]) == source[
                "canonical_game_key"
            ]
        except ValueError:
            return False
    return False


def paid_classic_projection_authority_v3(
    catalog: PaidClassicCatalogV3,
) -> PaidClassicProjectionAuthorityV3:
    """Create the catalog-only token accepted by paid simulation.

    In particular, callers cannot put seeds, world counts, model claims, or
    objectives into this token.  Those facts are observed and sealed by the
    engine after execution.
    """

    body: dict[str, object] = {
        "schema_version": _PROJECTION_AUTHORITY_SCHEMA,
        "authoritative_game_catalog_sha256": catalog.sha256,
        "projection_batch_sha256": catalog.projection_batch_sha256,
        "projection_generated_at": catalog.projection_generated_at,
        "projection_derivation_id": catalog.projection_derivation_id,
        "source_commit_sha": catalog.source_commit_sha,
        "immutable_image_digest": catalog.immutable_image_digest,
        "cloud_build_id": catalog.cloud_build_id,
        "immutable_image_uri": catalog.immutable_image_uri,
        "running_revision": catalog.running_revision,
        "runtime_deployment_identity_sha256": (
            catalog.runtime_deployment_identity_sha256
        ),
    }
    body["authority_sha256"] = _canonical_sha256(body)
    return PaidClassicProjectionAuthorityV3(
        json.dumps(body, sort_keys=True, separators=(",", ":"))
    )


def paid_classic_projection_derivation_receipt_v3(
    catalog: PaidClassicCatalogV3,
    *,
    transformation: Mapping[str, object] | None = None,
) -> PaidClassicProjectionAuthorityV3:
    """Compatibility name for the pre-execution authority token.

    The old API accepted a caller-authored transformation mapping.  That was
    not evidence of what the engine ran, so paid-v3 now rejects it.
    """

    if transformation is not None:
        _fail("caller-supplied transformation receipts are forbidden")
    return paid_classic_projection_authority_v3(catalog)


def _selected_projection_objectives(
    lineups: Sequence[Lineup],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for lineup in lineups:
        objectives: list[dict[str, object]] = []
        for player in lineup.players:
            player_id = _integer(
                player.get("id"), label="selected objective player ID"
            )
            try:
                objective = float(player.get("proj"))
            except (TypeError, ValueError, OverflowError):
                _fail("selected projection objective is invalid")
            if not math.isfinite(objective):
                _fail("selected projection objective is invalid")
            objectives.append({
                "player_id": player_id,
                "objective": objective,
            })
        objectives.sort(key=lambda row: int(row["player_id"]))
        lineup_key = _canonical_sha256([
            int(row["player_id"]) for row in objectives
        ])
        rows.append({
            "lineup_sha256": lineup_key,
            "objectives": objectives,
        })
    rows.sort(key=lambda row: str(row["lineup_sha256"]))
    return rows


def _validate_engine_model_artifact(
    value: object, *, label: str,
) -> str:
    """Reopen the engine's exact in-memory model fingerprint."""

    if not isinstance(value, Mapping):
        _fail(f"engine receipt {label} model artifact is invalid")
    artifact = dict(value)
    claimed = artifact.pop("artifact_sha256", None)
    if (
        artifact.get("schema_version")
        != "loaded-component-model-artifacts/v1"
        or not str(artifact.get("model_version", ""))
        or not isinstance(artifact.get("components"), list)
        or not artifact["components"]
        or claimed != _canonical_sha256(artifact)
    ):
        _fail(f"engine receipt {label} model artifact is invalid")
    names: list[str] = []
    for row in artifact["components"]:
        if not isinstance(row, Mapping):
            _fail(f"engine receipt {label} model component is invalid")
        if set(row) != {"component", "member_count", "member_sha256"}:
            _fail(f"engine receipt {label} model component schema differs")
        name = str(row.get("component", ""))
        members = row.get("member_sha256")
        count = row.get("member_count")
        if (
            not name
            or type(count) is not int
            or count <= 0
            or not isinstance(members, list)
            or len(members) != count
            or any(_DIGEST_RE.fullmatch("sha256:" + str(item)) is None
                   for item in members)
        ):
            _fail(f"engine receipt {label} model component is invalid")
        names.append(name)
    if names != sorted(set(names)):
        _fail(f"engine receipt {label} model components are not canonical")
    return str(artifact["model_version"])


def _validate_engine_feature_snapshot(
    value: object, *, label: str,
) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "sha256", "rows", "columns",
    }:
        _fail(f"engine receipt {label} feature snapshot is invalid")
    columns = value.get("columns")
    if (
        _DIGEST_RE.fullmatch("sha256:" + str(value.get("sha256", ""))) is None
        or type(value.get("rows")) is not int
        or int(value["rows"]) <= 0
        or not isinstance(columns, list)
        or not columns
        or any(not isinstance(column, str) or not column for column in columns)
        or columns != sorted(set(columns))
    ):
        _fail(f"engine receipt {label} feature snapshot is invalid")


def _validate_component_notes(value: object, *, label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "state", "before_sha256", "effective_sha256", "changed",
    }:
        _fail(f"engine receipt {label} component-notes state is invalid")
    before = str(value.get("before_sha256", ""))
    effective = str(value.get("effective_sha256", ""))
    if (
        value.get("state") not in {"enabled", "disabled"}
        or _DIGEST_RE.fullmatch("sha256:" + before) is None
        or _DIGEST_RE.fullmatch("sha256:" + effective) is None
        or type(value.get("changed")) is not bool
        or value["changed"] != (before != effective)
        or (value["state"] == "disabled" and value["changed"] is not False)
    ):
        _fail(f"engine receipt {label} component-notes state is invalid")


def _validate_preference_state(value: object, *, label: str) -> None:
    if not isinstance(value, Mapping):
        _fail(f"engine receipt {label} preference state is invalid")
    state = value.get("state")
    expected_keys = {
        "state", "source_rows_sha256", "applied_ban_player_ids",
        "applied_boost_player_ids",
    }
    if set(value) != expected_keys or state not in {"enabled", "disabled"}:
        _fail(f"engine receipt {label} preference state is invalid")
    source_hash = value.get("source_rows_sha256")
    if state == "enabled":
        if _DIGEST_RE.fullmatch("sha256:" + str(source_hash or "")) is None:
            _fail(f"engine receipt {label} preference source is invalid")
    elif source_hash is not None:
        _fail(f"engine receipt {label} preference source is invalid")
    for field in ("applied_ban_player_ids", "applied_boost_player_ids"):
        rows = value.get(field)
        if (
            not isinstance(rows, list)
            or any(type(item) is not int or item <= 0 for item in rows)
            or rows != sorted(set(rows))
        ):
            _fail(f"engine receipt {label} {field} is invalid")
    if state == "disabled" and any(
        value[field]
        for field in ("applied_ban_player_ids", "applied_boost_player_ids")
    ):
        _fail(f"engine receipt {label} disabled preferences changed players")


def _reopen_construction_policy(value: object):
    from .construction_presets import ConstructionPreset

    if not isinstance(value, Mapping):
        _fail("engine transformation receipt lacks construction_policy")
    raw = dict(value)
    try:
        from .lineup import StackRules

        stack = raw.get("stack")
        if not isinstance(stack, Mapping):
            raise TypeError("stack")
        preset = ConstructionPreset(
            preset_id=str(raw.get("base_preset_id", "")),
            stack=StackRules(**dict(stack)),
            min_salary=raw.get("min_salary"),
            min_games=raw.get("min_games"),
            punt_min=raw.get("punt_min"),
            punt_max_salary=raw.get("punt_max_salary"),
            punt_strict=raw.get("punt_strict"),
            value2_min=raw.get("value2_min"),
            value2_max=raw.get("value2_max"),
            own_barbell=raw.get("own_barbell"),
            own_barbell_low=raw.get("own_barbell_low"),
            own_barbell_high=raw.get("own_barbell_high"),
            own_barbell_nlow=raw.get("own_barbell_nlow"),
            own_barbell_nhigh=raw.get("own_barbell_nhigh"),
            max_per_game=raw.get("max_per_game"),
            min_lowown=raw.get("min_lowown"),
            max_overlap=raw.get("max_overlap"),
        )
    except (TypeError, ValueError):
        _fail("engine construction policy is invalid")
    if raw != preset.receipt():
        _fail("engine construction policy receipt is invalid")
    return preset


def _issue_paid_classic_engine_receipt_v3(
    authority: PaidClassicProjectionAuthorityV3,
    *,
    mode: str,
    lineups: Sequence[Lineup],
    seed_pairs: Sequence[Mapping[str, object]],
    worlds_per_block: int,
    selection_world_count: int,
    model_artifacts: Mapping[str, object],
    feature_snapshots: Mapping[str, object],
    notes_preferences: Mapping[str, object],
    locks: Sequence[int],
    bans: Sequence[int],
    theses: Sequence[Mapping[str, object]],
    construction_policy: Mapping[str, object],
    request_inputs: Mapping[str, object],
    policy_environment: Mapping[str, object],
) -> PaidClassicEngineReceiptV3:
    """Seal facts observed by the engine after a selected book exists."""

    if not isinstance(authority, PaidClassicProjectionAuthorityV3):
        _fail("paid engine requires a typed projection authority")
    if mode not in {"simulation", "milp"}:
        _fail("paid engine transformation mode is unsupported")
    objective_rows = _selected_projection_objectives(lineups)
    if not lineups or any(len(lineup.players) != 9 for lineup in lineups):
        _fail("paid engine cannot seal an empty or malformed selected book")
    body: dict[str, object] = {
        "schema_version": _ENGINE_RECEIPT_SCHEMA,
        "issuer": "nfl-dfs-paid-classic-engine-v3",
        "issued_after_execution": True,
        "mode": mode,
        "projection_authority": authority.as_dict(),
        "seed_pairs": [dict(row) for row in seed_pairs],
        "worlds_per_block": int(worlds_per_block),
        "selection_world_count": int(selection_world_count),
        "model_artifacts": dict(model_artifacts),
        "feature_snapshots": dict(feature_snapshots),
        "notes_preferences": dict(notes_preferences),
        "locks": sorted({int(value) for value in locks}),
        "bans": sorted({int(value) for value in bans}),
        "theses": [dict(row) for row in theses],
        "construction_policy": dict(construction_policy),
        "request_inputs": dict(request_inputs),
        "policy_environment": dict(sorted(policy_environment.items())),
        "selected_entries": len(lineups),
        "selected_projection_objectives_sha256": _canonical_sha256(
            objective_rows
        ),
    }
    body["receipt_sha256"] = _canonical_sha256(body)
    return PaidClassicEngineReceiptV3(body, _issuer=_ENGINE_RECEIPT_ISSUER)


def _validate_paid_classic_engine_receipt_v3(
    receipt: PaidClassicEngineReceiptV3,
    *,
    catalog: PaidClassicCatalogV3,
    lineups: Sequence[Lineup],
) -> dict[str, object]:
    if not isinstance(receipt, PaidClassicEngineReceiptV3):
        _fail("projection transformation receipt was not engine-produced")
    body = receipt.as_dict()
    expected_keys = {
        "schema_version", "issuer", "issued_after_execution", "mode",
        "projection_authority", "seed_pairs", "worlds_per_block",
        "selection_world_count", "model_artifacts", "feature_snapshots",
        "notes_preferences", "locks", "bans", "theses",
        "construction_policy", "request_inputs", "policy_environment",
        "selected_entries", "selected_projection_objectives_sha256",
        "receipt_sha256",
    }
    if set(body) != expected_keys:
        _fail("engine transformation receipt schema differs")
    claimed_hash = body.pop("receipt_sha256", None)
    if claimed_hash != _canonical_sha256(body):
        _fail("engine transformation receipt hash is invalid")
    body["receipt_sha256"] = claimed_hash
    expected_authority = paid_classic_projection_authority_v3(catalog).as_dict()
    if body.get("projection_authority") != expected_authority:
        _fail("engine transformation receipt names another projection authority")
    if (
        body.get("schema_version") != _ENGINE_RECEIPT_SCHEMA
        or body.get("issuer") != "nfl-dfs-paid-classic-engine-v3"
        or body.get("issued_after_execution") is not True
    ):
        _fail("engine transformation receipt identity is invalid")
    mode = body.get("mode")
    if mode == "simulation":
        from ..inference.production_policy import ADOPTED_CLASSIC_POLICY

        expected_pairs = [
            {
                "label": f"R{index}",
                "projection_seed": int(pair[0]),
                "role_seed": int(pair[1]),
            }
            for index, pair in enumerate(
                ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs
            )
        ]
        expected_worlds = int(
            ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block
        )
        if body.get("seed_pairs") != expected_pairs:
            _fail("engine receipt does not bind the exact five production seeds")
        if body.get("worlds_per_block") != expected_worlds:
            _fail("engine receipt does not bind 10,000 worlds per block")
        if body.get("selection_world_count") != (
            len(expected_pairs) * expected_worlds
        ):
            _fail("engine receipt does not bind 50,000 selection worlds")
        labels = {row["label"] for row in expected_pairs}
        for field in ("model_artifacts", "feature_snapshots"):
            value = body.get(field)
            if not isinstance(value, Mapping) or set(value) != labels:
                _fail(f"engine receipt {field} do not cover exact seed blocks")
        artifact_bodies: dict[str, list[dict[str, object]]] = {
            "projection": [], "role": [],
        }
        for label, artifacts in body["model_artifacts"].items():
            if not isinstance(artifacts, Mapping) or set(artifacts) != {
                "projection", "role",
            }:
                _fail(f"engine receipt model artifact for {label} is invalid")
            for family, expected_variant in (
                ("projection", ADOPTED_CLASSIC_POLICY.model_variant),
                ("role", ADOPTED_CLASSIC_POLICY.role_model_variant),
            ):
                version = _validate_engine_model_artifact(
                    artifacts.get(family), label=f"{label} {family}"
                )
                if not version.startswith(
                    f"pooled/components__{expected_variant}/"
                ):
                    _fail(
                        f"engine receipt {label} {family} model version differs"
                    )
                artifact_bodies[family].append(dict(artifacts[family]))
        if any(
            len({_canonical_sha256(row) for row in rows}) != 1
            for rows in artifact_bodies.values()
        ):
            _fail("engine receipt mixes model artifacts across seed blocks")
        feature_snapshot_hashes: set[str] = set()
        for label, snapshots in body["feature_snapshots"].items():
            if not isinstance(snapshots, Mapping) or set(snapshots) != {
                "projection", "role",
            }:
                _fail(f"engine receipt feature snapshot for {label} is invalid")
            for family in ("projection", "role"):
                _validate_engine_feature_snapshot(
                    snapshots.get(family), label=f"{label} {family}"
                )
                feature_snapshot_hashes.add(
                    _canonical_sha256(snapshots[family])
                )
        if len(feature_snapshot_hashes) != 1:
            _fail("engine receipt mixes feature snapshots across seed blocks")
        notes = body.get("notes_preferences")
        if not isinstance(notes, Mapping) or set(notes) != labels:
            _fail("engine receipt notes/preferences do not cover exact seed blocks")
        for label, note_state in notes.items():
            if not isinstance(note_state, Mapping) or set(note_state) != {
                "projection_component_notes", "role_component_notes",
                "preferences",
            }:
                _fail(f"engine receipt notes/preferences for {label} is invalid")
            _validate_component_notes(
                note_state["projection_component_notes"],
                label=f"{label} projection",
            )
            _validate_component_notes(
                note_state["role_component_notes"], label=f"{label} role"
            )
            _validate_preference_state(
                note_state["preferences"], label=str(label)
            )
    elif mode == "milp":
        if (
            body.get("seed_pairs") != []
            or body.get("worlds_per_block") != 0
            or body.get("selection_world_count") != 0
            or body.get("model_artifacts") != {}
        ):
            _fail("MILP receipt falsely claims simulation worlds")
        snapshots = body.get("feature_snapshots")
        notes = body.get("notes_preferences")
        if (
            not isinstance(snapshots, Mapping)
            or set(snapshots) != {"effective_optimizer_pool"}
        ):
            _fail("MILP receipt effective optimizer pool is invalid")
        pool_snapshot = snapshots["effective_optimizer_pool"]
        if (
            not isinstance(pool_snapshot, Mapping)
            or set(pool_snapshot) != {"sha256", "rows"}
            or _DIGEST_RE.fullmatch(
                "sha256:" + str(pool_snapshot.get("sha256", ""))
            ) is None
            or type(pool_snapshot.get("rows")) is not int
            or int(pool_snapshot["rows"]) <= 0
        ):
            _fail("MILP receipt effective optimizer pool is invalid")
        if (
            not isinstance(notes, Mapping)
            or set(notes) != {"state", "effective_optimizer_pool_sha256"}
            or notes.get("state") not in {"enabled", "disabled"}
            or notes.get("effective_optimizer_pool_sha256")
            != pool_snapshot["sha256"]
        ):
            _fail("MILP receipt notes state is invalid")
    else:
        _fail("engine transformation receipt mode is unsupported")
    for field in ("construction_policy", "request_inputs", "policy_environment"):
        if not isinstance(body.get(field), Mapping):
            _fail(f"engine transformation receipt lacks {field}")
    if not isinstance(body.get("locks"), list) or not isinstance(
        body.get("bans"), list
    ) or not isinstance(body.get("theses"), list):
        _fail("engine transformation receipt lacks request constraints")
    locks = body["locks"]
    bans = body["bans"]
    if (
        any(type(item) is not int or item <= 0 for item in locks + bans)
        or locks != sorted(set(locks))
        or bans != sorted(set(bans))
        or set(locks) & set(bans)
        or not set(locks + bans) <= set(catalog.by_player_id)
    ):
        _fail("engine transformation request locks/bans are invalid")
    if any(
        not set(locks) <= {int(player["id"]) for player in lineup.players}
        or set(bans) & {int(player["id"]) for player in lineup.players}
        for lineup in lineups
    ):
        _fail("engine transformation request locks/bans differ from the book")

    theses = body["theses"]
    for thesis in theses:
        if not isinstance(thesis, Mapping) or set(thesis) != {"players", "min"}:
            _fail("engine transformation thesis schema differs")
        players = thesis.get("players")
        minimum = thesis.get("min")
        if (
            not isinstance(players, list)
            or not players
            or any(type(item) is not int or item <= 0 for item in players)
            or len(players) != len(set(players))
            or not set(players) <= set(catalog.by_player_id)
            or type(minimum) is not int
            or not 0 < minimum <= len(lineups)
        ):
            _fail("engine transformation thesis is invalid")
        combo = set(players)
        if sum(
            combo <= {int(player["id"]) for player in lineup.players}
            for lineup in lineups
        ) < minimum:
            _fail("engine transformation thesis differs from the book")

    construction = _reopen_construction_policy(body["construction_policy"])
    request = body["request_inputs"]
    base_request_keys = {
        "season", "week", "draft_group_id", "n_entries",
        "contest_max_entries", "objective", "field_size",
        "requested_tail_line", "requested_leverage_scale",
        "construction_preset_id", "tail_line", "leverage_scale",
        "apply_notes",
    }
    simulation_request_keys = base_request_keys | {
        "allowed_player_count", "allowed_player_ids_sha256",
        "salary_override_count", "salary_overrides_sha256",
    }
    expected_request_keys = (
        simulation_request_keys if mode == "simulation" else base_request_keys
    )
    if set(request) != expected_request_keys:
        _fail("engine transformation request schema differs")
    if (
        request.get("season") != catalog.season
        or request.get("week") != catalog.week
        or request.get("draft_group_id") != catalog.draft_group_id
        or request.get("n_entries") != len(lineups)
        or request.get("construction_preset_id") != construction.preset_id
    ):
        _fail("engine transformation request context differs")
    objective = request.get("objective")
    supported_objectives = {"proj_points"} | set(
        catalog.projection_distribution_columns
    )
    if objective not in supported_objectives:
        _fail("engine transformation request objective is unsupported")
    if mode == "simulation" and objective != "proj_points":
        _fail("engine simulation objective is unsupported")
    apply_notes = request.get("apply_notes")
    if type(apply_notes) is not bool:
        _fail("engine transformation request apply_notes is invalid")
    contest_max_entries = request.get("contest_max_entries")
    requested_leverage = request.get("requested_leverage_scale")
    requested_tail = request.get("requested_tail_line")
    field_size = request.get("field_size")
    if (
        type(contest_max_entries) is not int
        or not 1 <= contest_max_entries <= 150
        or isinstance(requested_leverage, bool)
        or not isinstance(requested_leverage, (int, float))
        or not math.isfinite(float(requested_leverage))
        or not 0.0 <= float(requested_leverage) <= 2.0
        or (
            field_size is not None
            and (type(field_size) is not int or field_size < 100)
        )
        or (
            requested_tail is not None
            and (
                isinstance(requested_tail, bool)
                or not isinstance(requested_tail, (int, float))
                or not math.isfinite(float(requested_tail))
                or not 100.0 <= float(requested_tail) <= 300.0
            )
        )
    ):
        _fail("engine transformation request inputs are invalid")
    from ..inference.production_policy import (
        ADOPTED_CLASSIC_POLICY,
        contest_entry_policy,
    )

    try:
        entry_policy = contest_entry_policy(
            contest_max_entries,
            len(lineups),
            float(requested_leverage),
        )
    except (TypeError, ValueError) as exc:
        _fail(f"engine transformation contest entry policy is invalid: {exc}")
    expected_tail = (
        float(requested_tail)
        if requested_tail is not None
        else float(ADOPTED_CLASSIC_POLICY.tail_line)
    )
    if (
        request.get("tail_line") != expected_tail
        or request.get("leverage_scale")
        != float(entry_policy["effective_leverage_scale"])
    ):
        _fail("engine transformation effective request inputs differ")
    if mode == "simulation":
        allowed_ids = sorted(catalog.by_player_id)
        salary_items = sorted(
            (int(player_id), int(row["salary"]))
            for player_id, row in catalog.by_player_id.items()
        )
        if (
            request.get("allowed_player_count") != len(allowed_ids)
            or request.get("allowed_player_ids_sha256")
            != _canonical_sha256(allowed_ids)
            or request.get("salary_override_count") != len(salary_items)
            or request.get("salary_overrides_sha256")
            != _canonical_sha256(salary_items)
        ):
            _fail("engine transformation request slate inputs differ")
        expected_component_state = "enabled" if apply_notes else "disabled"
        notes_differ = any(
            state[component]["state"] != expected_component_state
            for state in body["notes_preferences"].values()
            for component in (
                "projection_component_notes", "role_component_notes",
            )
        )
        preferences_differ = any(
            (
                state["preferences"]["state"] == "disabled"
                if apply_notes
                else state["preferences"]["state"] != "disabled"
            )
            for state in body["notes_preferences"].values()
        )
        if notes_differ or preferences_differ:
            _fail("engine notes/preferences differ from apply_notes request")
        from ..inference.production_policy import POLICY_ENV_PASSTHROUGH

        supplied_environment = dict(body["policy_environment"])
        base = {
            key: str(supplied_environment[key])
            for key in POLICY_ENV_PASSTHROUGH
            if key in supplied_environment
        }
        expected_environment = ADOPTED_CLASSIC_POLICY.engine_environment(
            base, construction_preset=construction
        )
        if supplied_environment != expected_environment:
            _fail("engine transformation policy environment differs")
    else:
        if body["notes_preferences"]["state"] != (
            "enabled" if apply_notes else "disabled"
        ):
            _fail("MILP notes state differs from apply_notes request")
        if dict(body["policy_environment"]) != construction.optimizer_environment():
            _fail("MILP transformation policy environment differs")
    objective_rows = _selected_projection_objectives(lineups)
    if (
        body.get("selected_entries") != len(lineups)
        or body.get("selected_projection_objectives_sha256")
        != _canonical_sha256(objective_rows)
    ):
        _fail("engine receipt selected objectives differ from the book")
    return body


def _reopen_paid_classic_book_v3(
    lineups: Sequence[Lineup],
    *,
    expected_entries: int,
    catalog: PaidClassicCatalogV3,
) -> tuple[list[Lineup], list[dict[str, object]], dict[str, Any]]:
    try:
        assert_exact_unique_classic_book_v2(
            lineups, expected_entries=expected_entries
        )
    except ValueError as exc:
        _translate_v2_error(exc)

    authoritative_lineups: list[Lineup] = []
    semantic_audits: list[dict[str, object]] = []
    projection_objectives: list[list[dict[str, object]]] = []
    bound_derivations: dict[
        str, dict[str, object] | PaidClassicEngineReceiptV3
    ] = {}
    deterministic_derivation: dict[str, object] = {
        "schema_version": "paid-classic-deterministic-projection/v2",
        "mode": "deterministic-exact",
        "projection_authority": paid_classic_projection_authority_v3(
            catalog
        ).as_dict(),
    }
    deterministic_derivation["receipt_sha256"] = _canonical_sha256(
        deterministic_derivation
    )
    for lineup_ordinal, lineup in enumerate(lineups, start=1):
        authoritative_players: list[dict[str, Any]] = []
        audit_players: list[dict[str, Any]] = []
        transformed_projection = False
        for player_ordinal, player in enumerate(lineup.players, start=1):
            if not isinstance(player, Mapping):
                _fail(
                    f"lineup {lineup_ordinal} player {player_ordinal} "
                    "is not a mapping"
                )
            label = f"lineup {lineup_ordinal} player {player_ordinal}"
            player_id = _integer(player.get("id"), label=f"{label} ID")
            source = catalog.by_player_id.get(player_id)
            if source is None:
                _fail(
                    f"lineup {lineup_ordinal} player {player_id} is absent "
                    "from the authoritative joined catalog"
                )
            draftable_id = _integer(
                player.get("dk_id"), label=f"{label} draftable ID"
            )
            if draftable_id != source["draftable_id"]:
                _fail(f"{label} has a stale draftable ID")
            if _position(player.get("pos"), label=f"{label} position") != source[
                "pos"
            ]:
                _fail(f"{label} position differs from the joined catalog")
            try:
                claimed_team = normalize_team(player.get("team"), label=f"{label} team")
            except ValueError as exc:
                _fail(f"{label} has an invalid team claim: {exc}")
            if claimed_team != source["team"]:
                _fail(f"{label} team differs from the joined catalog")
            if _integer(player.get("salary"), label=f"{label} salary") != source[
                "salary"
            ]:
                _fail(f"{label} salary differs from the joined catalog")
            _text(player.get("name"), label=f"{label} name")
            claimed_opponent = _claimed_opponent(player, label=label)
            if claimed_opponent != source["opponent"]:
                _fail(f"{label} opponent differs from the joined catalog")
            if not _claimed_game_matches_authority(player.get("game_id"), source):
                _fail(f"{label} game_id differs from the joined catalog")
            try:
                projection = float(player.get("proj"))
            except (TypeError, ValueError, OverflowError):
                _fail(f"{label} projection is invalid")
            if not math.isfinite(projection):
                _fail(f"{label} projection is invalid")
            if not math.isclose(
                projection,
                float(source["projection"]),
                rel_tol=0.0,
                abs_tol=1e-9,
            ):
                transformed_projection = True
            authoritative = dict(player)
            authoritative.update(
                {
                    "id": player_id,
                    "dk_id": int(source["draftable_id"]),
                    "name": str(source["name"]),
                    "pos": str(source["pos"]),
                    # V2 validates the raw current DK salary team.  Alias
                    # equivalence was already proven against projection and
                    # schedule authority above.
                    "team": str(source["salary_team"]),
                    "opp": str(source["opponent"]),
                    "game_id": str(source["schedule_game_id"]),
                    "salary": int(source["salary"]),
                    "proj": projection,
                }
            )
            authoritative_players.append(authoritative)
            audit_players.append(
                {
                    "id": player_id,
                    "pos": str(source["pos"]),
                    "team": str(source["team"]),
                    "opp": str(source["opponent"]),
                    "game_id": str(source["schedule_game_id"]),
                    "salary": int(source["salary"]),
                }
            )
        derivation = getattr(lineup, "paid_projection_derivation_receipt", None)
        if derivation is None:
            if transformed_projection:
                _fail(
                    f"lineup {lineup_ordinal} transformed projections are not "
                    "bound to the certified coherent batch"
                )
            normalized_derivation: (
                dict[str, object] | PaidClassicEngineReceiptV3
            ) = dict(deterministic_derivation)
        else:
            if not isinstance(derivation, PaidClassicEngineReceiptV3):
                _fail(
                    f"lineup {lineup_ordinal} projection transformation "
                    "receipt was not engine-produced"
                )
            normalized_derivation = derivation
        normalized_body = (
            normalized_derivation.as_dict()
            if isinstance(normalized_derivation, PaidClassicEngineReceiptV3)
            else normalized_derivation
        )
        bound_derivations[
            _canonical_sha256(normalized_body)
        ] = normalized_derivation
        authoritative_lineup = Lineup(
            players=authoritative_players,
            tag=lineup.tag,
        )
        authoritative_lineups.append(authoritative_lineup)
        projection_objectives.append(
            [
                {"player_id": int(player["id"]), "objective": float(player["proj"])}
                for player in authoritative_players
            ]
        )
        try:
            semantic_audits.append(audit_classic_roster_semantics(audit_players))
        except ValueError as exc:
            _fail(
                f"lineup {lineup_ordinal} fails authoritative semantic "
                f"legality: {exc}"
            )

    if len(bound_derivations) > 1:
        _fail("selected lineups mix projection transformations")
    selected_derivation = (
        next(iter(bound_derivations.values()))
        if bound_derivations
        else deterministic_derivation
    )
    projection_derivation_receipt = (
        _validate_paid_classic_engine_receipt_v3(
            selected_derivation,
            catalog=catalog,
            lineups=authoritative_lineups,
        )
        if isinstance(selected_derivation, PaidClassicEngineReceiptV3)
        else dict(selected_derivation)
    )

    try:
        v2_receipt = validate_paid_classic_book_v2(
            authoritative_lineups,
            expected_entries=expected_entries,
            catalog=catalog.salary_catalog,
        )
    except ValueError as exc:
        _translate_v2_error(exc)

    v2_receipt_sha256 = str(v2_receipt.pop("receipt_sha256"))
    body = dict(v2_receipt)
    body.update(
        {
            "boundary_id": PAID_CLASSIC_BOUNDARY_ID,
            "v2_compatibility_boundary_id": PAID_CLASSIC_BOUNDARY_ID_V2,
            "v2_compatibility_receipt_sha256": v2_receipt_sha256,
            "authoritative_game_catalog_schema": (
                PAID_CLASSIC_GAME_CATALOG_SCHEMA
            ),
            "authoritative_game_catalog_sha256": catalog.sha256,
            "authoritative_game_catalog_rows": catalog.rows,
            "projection_generated_at": catalog.projection_generated_at,
            "projection_batch_sha256": catalog.projection_batch_sha256,
            "projection_derivation_id": catalog.projection_derivation_id,
            "projection_derivation_receipt": projection_derivation_receipt,
            "projection_derivation_receipt_sha256": _canonical_sha256(
                projection_derivation_receipt
            ),
            "selected_projection_objectives_sha256": _canonical_sha256(
                projection_objectives
            ),
            "source_commit_sha": catalog.source_commit_sha,
            "immutable_image_digest": catalog.immutable_image_digest,
            "cloud_build_id": catalog.cloud_build_id,
            "immutable_image_uri": catalog.immutable_image_uri,
            "running_revision": catalog.running_revision,
            "runtime_deployment_identity_sha256": (
                catalog.runtime_deployment_identity_sha256
            ),
            "validated_at": catalog.validated_at,
            "slate_lock_at": catalog.slate_lock_at,
            "schedule_catalog_sha256": catalog.schedule_sha256,
            "schedule_game_count": catalog.schedule_games,
            "canonical_game_policy_id": CANONICAL_GAME_POLICY_ID,
            "semantic_roster_audits": semantic_audits,
            "semantic_roster_audits_sha256": _canonical_sha256(
                semantic_audits
            ),
            "game_claims_match_authority": True,
            "authoritative_game_facts": True,
            "semantic_draftkings_legal": True,
        }
    )
    body["receipt_sha256"] = _canonical_sha256(body)
    return authoritative_lineups, semantic_audits, body


def validate_paid_classic_book_v3(
    lineups: Sequence[Lineup],
    *,
    expected_entries: int,
    catalog: PaidClassicCatalogV3,
) -> dict[str, Any]:
    """Validate the selected book against independent joined authorities."""

    return _reopen_paid_classic_book_v3(
        lineups,
        expected_entries=expected_entries,
        catalog=catalog,
    )[2]


def to_paid_dk_csv_v3(
    lineups: Sequence[Lineup],
    *,
    expected_entries: int,
    catalog: PaidClassicCatalogV3,
) -> PaidClassicExport:
    """Serialize authoritative names/IDs after the v3 terminal audit."""

    authoritative, _, receipt = _reopen_paid_classic_book_v3(
        lineups,
        expected_entries=expected_entries,
        catalog=catalog,
    )
    try:
        base = to_paid_dk_csv_v2(
            authoritative,
            expected_entries=expected_entries,
            catalog=catalog.salary_catalog,
        )
    except ValueError as exc:
        _translate_v2_error(exc)
    export_receipt = dict(receipt)
    for field in ("export_kind", "csv_sha256", "csv_bytes"):
        export_receipt[field] = base.receipt[field]
    export_receipt["export_receipt_sha256"] = _canonical_sha256(export_receipt)
    return PaidClassicExport(csv_text=base.csv_text, receipt=export_receipt)


def paid_entry_count_v3(entries_csv: str, *, contest_id: str | None) -> int:
    """Retain v2's exact, unambiguous paid-target selection semantics."""

    try:
        return paid_entry_count_v2(entries_csv, contest_id=contest_id)
    except ValueError as exc:
        _translate_v2_error(exc)


def fill_paid_entries_csv_v3(
    entries_csv: str,
    lineups: Sequence[Lineup],
    *,
    catalog: PaidClassicCatalogV3,
    contest_id: str | None,
    prepared_entry_capture: (Callable[[Mapping[str, Any]], None] | None) = None,
) -> PaidClassicExport:
    """Fill DKEntries one-to-one after the authoritative v3 game audit."""

    authoritative, _, receipt = _reopen_paid_classic_book_v3(
        lineups,
        expected_entries=paid_entry_count_v3(entries_csv, contest_id=contest_id),
        catalog=catalog,
    )
    v2_captures: list[Mapping[str, Any]] = []
    try:
        base = fill_paid_entries_csv_v2(
            entries_csv,
            authoritative,
            catalog=catalog.salary_catalog,
            contest_id=contest_id,
            prepared_entry_capture=(
                v2_captures.append if prepared_entry_capture is not None else None
            ),
        )
    except ValueError as exc:
        _translate_v2_error(exc)
    export_receipt = dict(receipt)
    for field in (
        "export_kind",
        "csv_sha256",
        "csv_bytes",
        "targeted_entries",
        "contest_id",
        "entry_id_order_sha256",
    ):
        export_receipt[field] = base.receipt[field]
    export_receipt["export_receipt_sha256"] = _canonical_sha256(export_receipt)
    if prepared_entry_capture is not None:
        if len(v2_captures) != 1:
            _fail("v2 compatibility fill emitted the wrong capture count")
        capture = dict(v2_captures[0])
        capture.update(
            {
                "schema_version": "paid-entry-capture/v2-canonical-game",
                "authoritative_game_catalog_sha256": catalog.sha256,
                "projection_batch_sha256": catalog.projection_batch_sha256,
                "projection_derivation_id": catalog.projection_derivation_id,
                "source_commit_sha": catalog.source_commit_sha,
                "immutable_image_digest": catalog.immutable_image_digest,
                "canonical_game_policy_id": CANONICAL_GAME_POLICY_ID,
                "paid_export_receipt_sha256": export_receipt[
                    "export_receipt_sha256"
                ],
            }
        )
        prepared_entry_capture(capture)
    return PaidClassicExport(csv_text=base.csv_text, receipt=export_receipt)


__all__ = [
    "PAID_CLASSIC_BOUNDARY_ID",
    "PAID_CLASSIC_BUILD_ID_ENV",
    "PAID_CLASSIC_GAME_CATALOG_SCHEMA",
    "PAID_CLASSIC_IMAGE_DIGEST_ENV",
    "PAID_CLASSIC_IMAGE_URI_ENV",
    "PAID_CLASSIC_PROJECTION_DERIVATION_ID",
    "PAID_CLASSIC_REVISION_ENV",
    "PAID_CLASSIC_SOURCE_COMMIT_ENV",
    "PaidClassicCatalogV3",
    "PaidClassicEngineReceiptV3",
    "PaidClassicProjectionAuthorityV3",
    "build_paid_classic_catalog_v3",
    "fill_paid_entries_csv_v3",
    "paid_classic_projection_authority_v3",
    "paid_classic_projection_derivation_receipt_v3",
    "paid_entry_count_v3",
    "to_paid_dk_csv_v3",
    "validate_paid_classic_book_v3",
    "validate_paid_classic_deployment_identity_v3",
    "validate_paid_classic_runtime_identity_v3",
]
