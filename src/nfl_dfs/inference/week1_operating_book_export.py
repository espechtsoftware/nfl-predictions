"""Canonical UI and DraftKings-CSV projection of the Week-1 money book.

The selected roster identities come only from the exact-reopened immutable
materialization.  The live salary table contributes display labels and the
DraftKings player id, but every score-relevant field (draftable id, position,
team and salary) must match the frozen pre-lock player bridge exactly.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import csv
import hashlib
import io
from numbers import Integral
import re
from typing import Final

from .generation_exposure import canonical_sha256
from . import prospective_generation_shadow_evaluation as shadow_evaluation
from .week1_operating_book import BASE_SOURCE_ORDER
from .week1_operating_book_operator import (
    WEEK1_DRAFT_GROUP_ID,
    WEEK1_SEASON,
    WEEK1_WEEK,
)
from .week1_operating_roster_materializer import (
    validate_week1_operating_roster_materialization_v1,
)


SCHEMA_VERSION: Final = "week1-operating-book-export/v1"
DK_HEADER: Final = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class Week1OperatingBookExportError(ValueError):
    """The immutable Week-1 book cannot be projected to a legal DK CSV."""


def _fail(message: str) -> None:
    raise Week1OperatingBookExportError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered sequence")
    return list(value)


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a nonempty canonical string")
    return value


def _int(value: object, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        _fail(f"{label} must be an integer")
    return int(value)


def _dk_id(value: object, *, label: str) -> str:
    if isinstance(value, bool):
        _fail(f"{label} must be a DraftKings draftable ID")
    if isinstance(value, Integral):
        value = str(int(value))
    return _text(value, label=label)


def _salary_records(value: object) -> list[dict[str, object]]:
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict("records")
        except TypeError as exc:
            raise Week1OperatingBookExportError(
                "salary authority cannot be converted to records"
            ) from exc
    return [
        _mapping(row, label=f"salary row[{ordinal}]")
        for ordinal, row in enumerate(_sequence(value, label="salary rows"))
    ]


def _slot_order(players: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    by_position = {
        position: sorted(
            (player for player in players if player["position"] == position),
            key=lambda player: str(player["dk_draftable_id"]),
        )
        for position in _POSITIONS
    }
    counts = {position: len(rows) for position, rows in by_position.items()}
    if (
        counts["QB"] != 1
        or counts["DST"] != 1
        or counts["RB"] not in {2, 3}
        or counts["WR"] not in {3, 4}
        or counts["TE"] not in {1, 2}
        or counts["RB"] + counts["WR"] + counts["TE"] != 7
    ):
        _fail("materialized roster does not have DraftKings Classic shape")
    fixed = (
        by_position["QB"]
        + by_position["RB"][:2]
        + by_position["WR"][:3]
        + by_position["TE"][:1]
    )
    used = {str(player["dk_draftable_id"]) for player in fixed}
    flex = [
        player
        for position in ("RB", "WR", "TE")
        for player in by_position[position]
        if str(player["dk_draftable_id"]) not in used
    ]
    if len(flex) != 1:
        _fail("materialized roster does not resolve one FLEX player")
    return fixed + flex + by_position["DST"]


def _csv(lineups: Sequence[Mapping[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(DK_HEADER)
    for lineup in lineups:
        players = _sequence(lineup.get("players"), label="export lineup players")
        writer.writerow([
            f"{player['display_name']} ({player['dk_draftable_id']})"
            for player in players
        ])
    return buffer.getvalue()


def build_week1_operating_book_export_v1(
    *,
    exact_book: object,
    salary_rows: object,
) -> dict[str, object]:
    """Resolve one exact immutable K80/K100 book to display rows and CSV."""

    exact = _mapping(exact_book, label="exact Week-1 book")
    if set(exact) != {"identity", "storage_created_at", "materialization"}:
        _fail("exact Week-1 book fields differ")
    try:
        identity = shadow_evaluation.normalize_object_identity_v1(
            exact.get("identity"), label="Week-1 materialization identity"
        )
        materialization = validate_week1_operating_roster_materialization_v1(
            exact.get("materialization")
        )
    except Exception as exc:
        raise Week1OperatingBookExportError(
            "exact Week-1 materialization validation failed"
        ) from exc
    raw = shadow_evaluation.canonical_json_bytes_v1(materialization)
    if (
        identity["sha256"] != shadow_evaluation.canonical_sha256_v1(materialization)
        or identity["bytes"] != len(raw)
    ):
        _fail("materialization object identity does not bind exact bytes")
    context = _mapping(materialization.get("slate_context"), label="slate context")
    if (
        context.get("season") != WEEK1_SEASON
        or context.get("week") != WEEK1_WEEK
        or str(context.get("draft_group_id")) != WEEK1_DRAFT_GROUP_ID
    ):
        _fail("materialization is not the frozen Week-1 slate")

    bridge_rows = _sequence(
        materialization.get("player_identity_bridge"),
        label="materialized player identity bridge",
    )
    bridge = {
        str(row["dk_draftable_id"]): _mapping(row, label="player bridge row")
        for row in bridge_rows
    }
    selected_ids = {
        str(player_id)
        for lineup in materialization["selected_lineups"]
        for player_id in lineup["player_ids"]
    }
    salary_by_id: dict[str, dict[str, object]] = {}
    for ordinal, row in enumerate(_salary_records(salary_rows)):
        required = {
            "draft_group_id",
            "dk_player_id",
            "dk_draftable_id",
            "display_name",
            "position",
            "team_abbr",
            "salary",
        }
        if not required <= set(row):
            _fail(f"salary row[{ordinal}] lacks export fields")
        if str(row["draft_group_id"]) != WEEK1_DRAFT_GROUP_ID:
            continue
        dk_id = _dk_id(
            row["dk_draftable_id"], label=f"salary row[{ordinal}] draftable ID"
        )
        if dk_id not in selected_ids:
            continue
        if dk_id in salary_by_id:
            _fail("salary authority repeats a selected draftable ID")
        salary_by_id[dk_id] = row
    if set(salary_by_id) != selected_ids:
        _fail("salary authority does not exactly resolve selected draftable IDs")

    resolved_players: dict[str, dict[str, object]] = {}
    for dk_id in sorted(selected_ids):
        frozen = bridge.get(dk_id)
        live = salary_by_id[dk_id]
        if frozen is None:
            _fail("selected draftable ID is absent from the frozen player bridge")
        position = _text(live["position"], label="salary position").upper()
        if position in {"DEF", "D/ST"}:
            position = "DST"
        team = _text(live["team_abbr"], label="salary team")
        salary = _int(live["salary"], label="salary amount")
        if (
            position not in _POSITIONS
            or position != frozen["position"]
            or team != frozen["team"]
            or salary != frozen["salary"]
        ):
            _fail("live salary identity differs from the frozen player bridge")
        resolved_players[dk_id] = {
            "dk_player_id": _int(live["dk_player_id"], label="DK player ID"),
            "dk_draftable_id": dk_id,
            "display_name": _text(live["display_name"], label="display name"),
            "gsis_id": frozen["gsis_id"],
            "position": position,
            "team": team,
            "salary": salary,
        }

    exported: list[dict[str, object]] = []
    for raw_lineup in materialization["selected_lineups"]:
        lineup = _mapping(raw_lineup, label="materialized selected lineup")
        roster = [resolved_players[str(player_id)] for player_id in lineup["player_ids"]]
        players = _slot_order(roster)
        salary = sum(int(player["salary"]) for player in players)
        if salary > 50_000 or len({player["team"] for player in players}) < 2:
            _fail("materialized roster fails universal DraftKings legality")
        exported.append({
            "entry_rank": lineup["entry_rank"],
            "lineup_id": lineup["lineup_id"],
            "source_id": lineup["source_id"],
            "source_role": lineup["source_role"],
            "source_rank": lineup["source_rank"],
            "salary": salary,
            "players": players,
        })
    counts = Counter(str(lineup["source_id"]) for lineup in exported)
    source_counts = {source_id: counts[source_id] for source_id in BASE_SOURCE_ORDER}
    csv_text = _csv(exported)
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "complete": True,
        "k": materialization["k"],
        "slate_context": context,
        "materialization_identity": identity,
        "materialization_storage_created_at": exact["storage_created_at"],
        "materialization_sha256": materialization["materialization_sha256"],
        "selected_lineup_ids_sha256": materialization[
            "selected_lineup_ids_sha256"
        ],
        "source_counts": source_counts,
        "lineups": exported,
        "dk_csv": csv_text,
        "dk_csv_sha256": hashlib.sha256(csv_text.encode("utf-8")).hexdigest(),
        "cap4_used": False,
        "tier3_used": False,
        "uses_realized_outcomes": False,
        "tuning_controls_accepted": [],
    }
    body["export_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "SCHEMA_VERSION",
    "Week1OperatingBookExportError",
    "build_week1_operating_book_export_v1",
]
