"""Materialize the four Week-1 A5 books from the reviewed live candidate pool.

This module is deliberately storage- and entry-free.  It converts the lab's
active Week-1 frame, candidate rows, and ordered selector outputs into the
strict capture-v3 salary catalog, player bridge, and exact-K80 book shapes.
All builders finish by invoking the capture contract validators.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

import pandas as pd

from ..ingest import week1_a5_capture_contracts as capture
from .generation_exposure import canonical_sha256

_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
_FLEX: Final = frozenset({"RB", "WR", "TE"})


class Week1A5BookMaterializerError(ValueError):
    """The live candidate data cannot form the governed A5 book artifacts."""


def _fail(message: str) -> None:
    raise Week1A5BookMaterializerError(message)


def _status(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    retained = str(value).strip().upper()
    if retained in {"", "NONE", "NAN", "<NA>"}:
        return ""
    return retained


def _frame_facts(frame: pd.DataFrame) -> dict[str, dict[str, object]]:
    required = {
        "id",
        "dk_player_id",
        "dk_draftable_id",
        "display_name",
        "team",
        "pos",
        "salary",
        "status",
        "roster_status",
    }
    if frame.empty or required - set(frame.columns):
        _fail("live frame is empty or lacks A5 player authority fields")
    facts: dict[str, dict[str, object]] = {}
    paid_ids: set[int] = set()
    draftable_ids: set[int] = set()
    display_names: set[str] = set()
    for ordinal, raw in enumerate(frame.to_dict("records")):
        internal_id = str(raw["id"])
        position = str(raw["pos"]).upper()
        try:
            paid_id = int(raw["dk_player_id"])
            draftable_id = int(raw["dk_draftable_id"])
            salary = int(raw["salary"])
        except (TypeError, ValueError) as exc:
            raise Week1A5BookMaterializerError(
                f"live frame row {ordinal} has a nonnumeric DK fact"
            ) from exc
        name = str(raw["display_name"]).strip()
        team = str(raw["team"]).strip().upper()
        status = _status(raw["status"])
        roster_status = _status(raw["roster_status"])
        # The live frame deliberately retains DK-inactive players long enough
        # for cascade redistribution, then removes them before simulation.
        # The capture catalog begins at that final playable boundary.
        if status in {"O", "OUT", "IR"}:
            continue
        if (
            not internal_id
            or internal_id in facts
            or paid_id < 1
            or paid_id in paid_ids
            or draftable_id < 1
            or draftable_id in draftable_ids
            or not name
            or name in display_names
            or not team
            or position not in _POSITIONS
            or salary < 1
            or salary > capture.SALARY_CAP
            or (position != "DST" and roster_status != "ACT")
        ):
            _fail(f"live frame row {ordinal} violates the active A5 catalog")
        paid_ids.add(paid_id)
        draftable_ids.add(draftable_id)
        display_names.add(name)
        facts[internal_id] = {
            "internal_player_id": internal_id,
            "dk_player_id": paid_id,
            "dk_draftable_id": draftable_id,
            "display_name": name,
            "team": team,
            "position": position,
            "salary": salary,
            "status": status,
        }
    return facts


def _pulled_at(frame: pd.DataFrame) -> str:
    if "pulled_at" not in frame.columns:
        _fail("live frame lacks its DraftKings pull time")
    pulled = pd.to_datetime(frame["pulled_at"], utc=True, errors="coerce")
    if pulled.isna().any() or pulled.nunique() != 1:
        _fail("live frame does not bind one canonical DraftKings pull time")
    return pulled.iloc[0].to_pydatetime().isoformat()


def build_week1_paid_salary_catalog_v1(
    frame: pd.DataFrame,
) -> dict[str, object]:
    """Build the active, one-to-one DraftKings catalog used by all four books."""

    facts = _frame_facts(frame)
    players = [
        {
            "player_id": fact["dk_player_id"],
            "draftable_id": fact["dk_draftable_id"],
            "name": fact["display_name"],
            "team": fact["team"],
            "pos": fact["position"],
            "salary": fact["salary"],
            "status": fact["status"],
        }
        for fact in sorted(facts.values(), key=lambda item: int(item["dk_player_id"]))
    ]
    pulled_at = _pulled_at(frame)
    paid_catalog_sha256 = canonical_sha256(
        {
            "draft_group_id": int(capture.EXPECTED_DRAFT_GROUP_ID),
            "pulled_at": pulled_at,
            "players": players,
        }
    )
    artifact = capture.seal_semantic_artifact(
        {
            "schema_version": capture.SALARY_CATALOG_SCHEMA,
            "slate_id": capture.EXPECTED_SLATE_ID,
            "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
            "pulled_at": pulled_at,
            "players": players,
            "paid_catalog_sha256": paid_catalog_sha256,
        }
    )
    return capture.validate_week1_paid_salary_catalog_v1(artifact)


def build_week1_player_bridge_v1(
    frame: pd.DataFrame,
    *,
    salary_catalog: Mapping[str, object],
    salary_catalog_ref: Mapping[str, object],
) -> dict[str, object]:
    """Build complete internal/DK player and draftable mappings."""

    catalog = capture.validate_week1_paid_salary_catalog_v1(salary_catalog)
    facts = _frame_facts(frame)
    players = [dict(facts[player_id]) for player_id in sorted(facts)]
    artifact = capture.seal_semantic_artifact(
        {
            "schema_version": capture.PLAYER_BRIDGE_SCHEMA,
            "slate_id": capture.EXPECTED_SLATE_ID,
            "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
            "salary_cap": capture.SALARY_CAP,
            "salary_catalog": dict(salary_catalog_ref),
            "paid_catalog_sha256": catalog["paid_catalog_sha256"],
            "players": players,
        }
    )
    return capture.validate_week1_player_bridge_v1(
        artifact,
        catalog=catalog,
        salary_catalog_ref=salary_catalog_ref,
    )


def _roster(raw: object, *, label: str) -> list[str]:
    if type(raw) is not str:
        _fail(f"{label} must be a comma-delimited internal roster")
    players = raw.split(",")
    if len(players) != 9 or len(set(players)) != 9 or players != sorted(players):
        _fail(f"{label} must contain nine unique sorted players")
    return players


def _candidate_rosters(
    candidates: pd.DataFrame,
) -> tuple[list[str], dict[str, list[str]], list[list[str]]]:
    if candidates.empty or "players" not in candidates.columns:
        _fail("candidate table is empty or lacks player membership")
    ids: list[str] = []
    by_id: dict[str, list[str]] = {}
    rosters: list[list[str]] = []
    for ordinal, raw in enumerate(candidates["players"].tolist()):
        roster = _roster(raw, label=f"candidate {ordinal}")
        lineup_id = f"lineup-v1-{canonical_sha256(roster)}"
        if lineup_id in by_id:
            _fail("candidate table repeats a lineup identity")
        ids.append(lineup_id)
        by_id[lineup_id] = roster
        rosters.append(roster)
    return ids, by_id, rosters


def _canonical_slots(
    roster: Sequence[str], facts: Mapping[str, Mapping[str, object]]
) -> list[str]:
    by_position: dict[str, list[str]] = {position: [] for position in _POSITIONS}
    for player_id in roster:
        try:
            position = str(facts[player_id]["position"])
        except KeyError as exc:
            raise Week1A5BookMaterializerError(
                "candidate roster leaves the exact player bridge"
            ) from exc
        by_position[position].append(player_id)
    for players in by_position.values():
        players.sort()
    if (
        len(by_position["QB"]) != 1
        or len(by_position["RB"]) < 2
        or len(by_position["WR"]) < 3
        or len(by_position["TE"]) < 1
        or len(by_position["DST"]) != 1
    ):
        _fail("candidate roster cannot fill the NFL Classic slots")
    fixed = (
        by_position["QB"]
        + by_position["RB"][:2]
        + by_position["WR"][:3]
        + by_position["TE"][:1]
    )
    remaining = sorted(set(roster) - set(fixed) - set(by_position["DST"]))
    if len(remaining) != 1 or str(facts[remaining[0]]["position"]) not in _FLEX:
        _fail("candidate roster does not have exactly one eligible FLEX")
    return fixed + remaining + by_position["DST"]


def lineups_from_ordered_candidate_ids_v1(
    *,
    frame: pd.DataFrame,
    candidates: pd.DataFrame,
    ordered_lineup_ids: Sequence[str],
) -> list[dict[str, object]]:
    """Recover exact slot assignments for one ordered candidate-book prefix."""

    facts = _frame_facts(frame)
    _ids, by_id, _rosters = _candidate_rosters(candidates)
    retained_ids = [str(value) for value in ordered_lineup_ids]
    if (
        len(retained_ids) != capture.EXPECTED_BOOK_SIZE
        or len(set(retained_ids)) != capture.EXPECTED_BOOK_SIZE
    ):
        _fail("ordered candidate book must contain exact unique K80")
    lineups: list[dict[str, object]] = []
    for lineup_id in retained_ids:
        try:
            roster = by_id[lineup_id]
        except KeyError as exc:
            raise Week1A5BookMaterializerError(
                "ordered book references a lineup outside the candidate table"
            ) from exc
        slots = _canonical_slots(roster, facts)
        lineups.append(
            {
                "lineup_id": lineup_id,
                "player_ids": roster,
                "slots": [
                    {"slot": slot, "player_id": player_id}
                    for slot, player_id in zip(
                        capture.CLASSIC_SLOTS, slots, strict=True
                    )
                ],
                "salary": sum(int(facts[player_id]["salary"]) for player_id in roster),
            }
        )
    return lineups


def lineups_from_ranked_csv_v1(
    *,
    frame: pd.DataFrame,
    candidates: pd.DataFrame,
    csv_rows: Sequence[Sequence[object]],
    rank_column: str,
) -> list[dict[str, object]]:
    """Bind a live selector rank column to the emitted DK-player CSV order."""

    if rank_column not in candidates.columns:
        _fail(f"candidate table lacks {rank_column}")
    facts = _frame_facts(frame)
    candidate_ids, _by_id, rosters = _candidate_rosters(candidates)
    selected: dict[int, int] = {}
    for ordinal, raw_rank in enumerate(candidates[rank_column].tolist()):
        if pd.isna(raw_rank):
            continue
        rank = int(raw_rank)
        if float(raw_rank) != rank or rank in selected:
            _fail(f"{rank_column} is noncanonical or repeated")
        selected[rank] = ordinal
    if set(selected) != set(range(1, capture.EXPECTED_BOOK_SIZE + 1)):
        _fail(f"{rank_column} does not contain exact ranks 1..80")
    rows = [list(row) for row in csv_rows]
    if len(rows) != capture.EXPECTED_BOOK_SIZE or any(len(row) != 9 for row in rows):
        _fail("ranked CSV must be exact K80 by nine slots")
    by_dk_player = {int(fact["dk_player_id"]): player_id for player_id, fact in facts.items()}
    lineups: list[dict[str, object]] = []
    for rank, raw_slots in enumerate(rows, start=1):
        try:
            slots = [by_dk_player[int(value)] for value in raw_slots]
        except (KeyError, TypeError, ValueError) as exc:
            raise Week1A5BookMaterializerError(
                f"ranked CSV row {rank} leaves the exact player bridge"
            ) from exc
        roster = rosters[selected[rank]]
        if len(set(slots)) != 9 or set(slots) != set(roster):
            _fail(f"ranked CSV row {rank} differs from selected candidate membership")
        for slot, player_id in zip(capture.CLASSIC_SLOTS, slots, strict=True):
            position = str(facts[player_id]["position"])
            if (slot == "FLEX" and position not in _FLEX) or (
                slot != "FLEX" and position != slot
            ):
                _fail(f"ranked CSV row {rank} has an ineligible {slot}")
        lineups.append(
            {
                "lineup_id": candidate_ids[selected[rank]],
                "player_ids": roster,
                "slots": [
                    {"slot": slot, "player_id": player_id}
                    for slot, player_id in zip(capture.CLASSIC_SLOTS, slots, strict=True)
                ],
                "salary": sum(int(facts[player_id]["salary"]) for player_id in roster),
            }
        )
    return lineups


def build_week1_book_materialization_v2(
    *,
    policy: str,
    lineups: Sequence[Mapping[str, object]],
    bridge: Mapping[str, object],
    player_bridge_ref: Mapping[str, object],
) -> dict[str, object]:
    """Convert one ordered K80 lineup book into the capture-v3 book contract."""

    if policy not in capture.EXPECTED_POLICIES:
        _fail("book policy is outside the exact A5 decision")
    bridge_by_internal = {
        str(player["internal_player_id"]): player
        for player in bridge.get("players", [])
        if isinstance(player, Mapping)
    }
    entries: list[dict[str, object]] = []
    for rank, lineup in enumerate(lineups, start=1):
        player_ids = [str(value) for value in lineup.get("player_ids", [])]
        slots = list(lineup.get("slots", []))
        if (
            len(player_ids) != 9
            or len(set(player_ids)) != 9
            or player_ids != sorted(player_ids)
            or len(slots) != 9
        ):
            _fail(f"{policy} lineup {rank} has invalid membership or slots")
        slot_ids: list[int] = []
        for ordinal, (slot, expected_slot) in enumerate(
            zip(slots, capture.CLASSIC_SLOTS, strict=True)
        ):
            if not isinstance(slot, Mapping) or slot.get("slot") != expected_slot:
                _fail(f"{policy} lineup {rank} slot {ordinal} differs")
            player_id = str(slot.get("player_id"))
            try:
                slot_ids.append(int(bridge_by_internal[player_id]["dk_draftable_id"]))
            except KeyError as exc:
                raise Week1A5BookMaterializerError(
                    f"{policy} lineup {rank} leaves the exact bridge"
                ) from exc
        if set(str(slot.get("player_id")) for slot in slots) != set(player_ids):
            _fail(f"{policy} lineup {rank} slot membership differs")
        roster_sha256 = canonical_sha256(sorted(player_ids))
        lineup_id = f"lineup-v1-{roster_sha256}"
        if lineup.get("lineup_id") != lineup_id:
            _fail(f"{policy} lineup {rank} ID differs from membership")
        team_counts = Counter(
            str(bridge_by_internal[player_id]["team"]) for player_id in player_ids
        )
        if len(team_counts) < 2 or max(team_counts.values()) > capture.MAX_FROM_TEAM:
            _fail(f"{policy} lineup {rank} violates the A5 team constraint")
        entries.append(
            {
                "lineup_rank": rank,
                "lineup_id": lineup_id,
                "roster_sha256": roster_sha256,
                "internal_player_ids": player_ids,
                "slot_dk_draftable_ids": slot_ids,
                "salary": int(lineup.get("salary", 0)),
            }
        )
    artifact = capture.seal_semantic_artifact(
        {
            "schema_version": capture.BOOK_SCHEMA,
            "policy": policy,
            "purpose": "paid" if policy == "P_MIX" else "shadow",
            "slate_id": capture.EXPECTED_SLATE_ID,
            "draft_group_id": capture.EXPECTED_DRAFT_GROUP_ID,
            "player_bridge": dict(player_bridge_ref),
            "entries": entries,
        }
    )
    return capture.validate_week1_book_materialization_v2(
        artifact, bridge=bridge
    )


__all__ = [
    "Week1A5BookMaterializerError",
    "build_week1_book_materialization_v2",
    "build_week1_paid_salary_catalog_v1",
    "build_week1_player_bridge_v1",
    "lineups_from_ordered_candidate_ids_v1",
    "lineups_from_ranked_csv_v1",
]
