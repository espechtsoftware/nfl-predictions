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
_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})


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
    schedule_sha256: str
    schedule_games: int
    validated_at: str
    slate_lock_at: str


def _fail(message: str) -> None:
    raise ValueError(f"{PAID_CLASSIC_BOUNDARY_ID}: {message}")


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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

    projections: dict[int, dict[str, Any]] = {}
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
            "raw_team": _text(
                row.get("team"), label=f"projection row {ordinal} team"
            ),
            "raw_opponent": _text(
                row.get("opponent"),
                label=f"projection row {ordinal} opponent",
            ),
        }

    if len(projection_batch_values) != 1:
        _fail("projection authority mixes generated_at batches")
    projection_batch_time = pd.Timestamp(
        next(iter(projection_batch_values)), unit="ns", tz="UTC"
    )
    if projection_batch_time > validation_time:
        _fail("projection batch is later than validation time")
    if projection_batch_time >= slate_lock:
        _fail("projection batch reaches or follows slate lock")

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
        schedule_sha256=schedule_sha256,
        schedule_games=len(schedule_identity),
        validated_at=validation_time.isoformat(),
        slate_lock_at=slate_lock.isoformat(),
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
    for lineup_ordinal, lineup in enumerate(lineups, start=1):
        authoritative_players: list[dict[str, Any]] = []
        audit_players: list[dict[str, Any]] = []
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
        authoritative_lineup = Lineup(
            players=authoritative_players,
            tag=lineup.tag,
        )
        authoritative_lineups.append(authoritative_lineup)
        try:
            semantic_audits.append(audit_classic_roster_semantics(audit_players))
        except ValueError as exc:
            _fail(
                f"lineup {lineup_ordinal} fails authoritative semantic "
                f"legality: {exc}"
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
    "PAID_CLASSIC_GAME_CATALOG_SCHEMA",
    "PaidClassicCatalogV3",
    "build_paid_classic_catalog_v3",
    "fill_paid_entries_csv_v3",
    "paid_entry_count_v3",
    "to_paid_dk_csv_v3",
    "validate_paid_classic_book_v3",
]
