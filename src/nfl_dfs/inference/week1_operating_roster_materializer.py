"""Materialize the frozen Week-1 operating book into exact DK rosters.

This module is a pure, score-blind boundary.  It accepts either the complete
create-once terminal prelock envelope or the validated suite authority plus
the three decoded source-arm artifacts.  It delegates lineup selection to
``week1_operating_book_suite_adapter`` and only resolves the selected lineup
identities to their canonical nine-player roster identities.

There is deliberately no storage, application-route, contest-entry, cap-4,
Tier-3, or realized-outcome behavior here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

from .generation_exposure import canonical_sha256
from . import prospective_generation_shadow_evaluation as shadow_evaluation
from .week1_operating_book import BASE_SOURCE_ORDER
from .week1_operating_book_suite_adapter import (
    Week1OperatingBookSuiteAdapterError,
    build_week1_operating_book_from_suite_authority_v1,
    validate_week1_operating_book_suite_envelope_v1,
)


SCHEMA_VERSION: Final = "week1-operating-roster-materialization/v1"
MATERIALIZER_ID: Final = "2026-week1-score-blind-roster-materializer-v1"
TERMINAL_AUTHORITY_MODE: Final = "terminal-prelock-envelope"
DECODED_AUTHORITY_MODE: Final = "suite-decoded-arm-artifacts"
SOURCE_BOOK_SIZE: Final = 80

_LINEUP_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_DECODED_FIELDS = {
    "metadata",
    "generated_at",
    "player_ids",
    "player_draws",
    "candidate_rosters",
    "sha256",
}
_CONTEXT_FIELDS = (
    "season",
    "week",
    "draft_group_id",
    "run_id",
    "code_sha",
    "slate_lock_at",
)
_PLAYER_BRIDGE_FIELDS = {
    "internal_player_id",
    "dk_draftable_id",
    "gsis_id",
    "position",
    "team",
    "dst_team",
    "salary",
}
_OUTCOME_CARRIER_FIELDS = frozenset({
    "actual",
    "actual_score",
    "actual_points",
    "actual_ownership",
    "contest_rank",
    "final_score",
    "outcome",
    "outcomes",
    "payout",
    "realized_points",
    "realized_score",
    "roi",
})


class Week1OperatingRosterMaterializerError(ValueError):
    """The prelock authority cannot support one exact roster book."""


def _fail(message: str) -> None:
    raise Week1OperatingRosterMaterializerError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed mapping")
    return value


def _sequence(value: object, *, label: str) -> list[object]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, Sequence
    ):
        _fail(f"{label} must be an ordered sequence")
    return list(value)


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _canonical_player_id(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a nonempty canonical string")
    return value


def _canonical_roster(value: object, *, label: str) -> tuple[str, ...]:
    raw = _sequence(value, label=label)
    roster = tuple(
        _canonical_player_id(player_id, label=f"{label} player ID")
        for player_id in raw
    )
    if len(roster) != 9 or len(set(roster)) != 9 or list(roster) != sorted(roster):
        _fail(f"{label} must contain nine unique, sorted player IDs")
    return roster


def _lineup_id(roster: Sequence[str]) -> str:
    return f"lineup-v1-{canonical_sha256(list(roster))}"


def _forbidden_metadata_paths(value: object, *, path: str = "metadata") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in _OUTCOME_CARRIER_FIELDS:
                found.append(child)
            found.extend(_forbidden_metadata_paths(nested, path=child))
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            found.extend(
                _forbidden_metadata_paths(nested, path=f"{path}[{index}]")
            )
    return found


def _slate_context(suite: Mapping[str, object]) -> dict[str, object]:
    manifest = _mapping(suite.get("manifest"), label="suite manifest")
    context = {field: manifest.get(field) for field in _CONTEXT_FIELDS}
    if any(value is None for value in context.values()):
        _fail("suite manifest lacks the complete slate context")
    if context["slate_lock_at"] != suite.get("slate_lock_at"):
        _fail("suite slate-lock context differs")
    return context


def _player_identity_bridge(
    suite: Mapping[str, object],
) -> list[dict[str, object]]:
    """Retain the frozen DK/roster bridge needed to export the exact book."""

    raw_rows = _sequence(
        suite.get("player_identity_bridge"),
        label="suite player identity bridge",
    )
    rows: list[dict[str, object]] = []
    internal_ids: set[str] = set()
    dk_ids: set[str] = set()
    for ordinal, raw_row in enumerate(raw_rows):
        row = _mapping(raw_row, label=f"suite player bridge[{ordinal}]")
        if set(row) != _PLAYER_BRIDGE_FIELDS:
            _fail("suite player identity bridge fields differ")
        internal_id = _canonical_player_id(
            row.get("internal_player_id"),
            label=f"suite bridge internal player ID {ordinal}",
        )
        dk_id = _canonical_player_id(
            row.get("dk_draftable_id"),
            label=f"suite bridge DK draftable ID {ordinal}",
        )
        position = _canonical_player_id(
            row.get("position"), label=f"suite bridge position {ordinal}"
        )
        team = _canonical_player_id(
            row.get("team"), label=f"suite bridge team {ordinal}"
        )
        salary = row.get("salary")
        gsis_id = row.get("gsis_id")
        dst_team = row.get("dst_team")
        if (
            position not in {"QB", "RB", "WR", "TE", "DST"}
            or type(salary) is not int
            or salary <= 0
            or internal_id in internal_ids
            or dk_id in dk_ids
        ):
            _fail("suite player identity bridge row differs")
        if position == "DST":
            if gsis_id is not None or dst_team != team:
                _fail("suite DST identity bridge differs")
        elif (
            type(gsis_id) is not str
            or not gsis_id
            or gsis_id.strip() != gsis_id
            or dst_team is not None
        ):
            _fail("suite skill-player identity bridge differs")
        internal_ids.add(internal_id)
        dk_ids.add(dk_id)
        rows.append({
            "internal_player_id": internal_id,
            "dk_draftable_id": dk_id,
            "gsis_id": gsis_id,
            "position": position,
            "team": team,
            "dst_team": dst_team,
            "salary": salary,
        })
    if not rows:
        _fail("suite player identity bridge is empty")
    return rows


def _suite_membership_rosters(
    suite: Mapping[str, object],
) -> dict[str, tuple[tuple[str, ...], ...]]:
    manifest = _mapping(suite.get("manifest"), label="suite manifest")
    prelock = _mapping(
        manifest.get("prelock_receipt"), label="suite prelock receipt"
    )
    memberships = _mapping(
        prelock.get("memberships"), label="suite prelock memberships"
    )
    k80 = _mapping(memberships.get("80"), label="suite K80 memberships")
    authority_lineup_ids = _mapping(
        suite.get("membership_lineup_ids_by_arm"),
        label="suite membership lineup IDs",
    )
    retained: dict[str, tuple[tuple[str, ...], ...]] = {}
    for source_id in BASE_SOURCE_ORDER:
        raw_rosters = _sequence(
            k80.get(source_id), label=f"{source_id} K80 membership rosters"
        )
        if len(raw_rosters) != SOURCE_BOOK_SIZE:
            _fail(f"{source_id} membership roster book is not exact-80")
        rosters = tuple(
            _canonical_roster(
                raw_roster, label=f"{source_id} membership roster[{ordinal}]"
            )
            for ordinal, raw_roster in enumerate(raw_rosters)
        )
        lineup_ids = [_lineup_id(roster) for roster in rosters]
        expected_ids = _sequence(
            authority_lineup_ids.get(source_id),
            label=f"{source_id} suite membership lineup IDs",
        )
        if lineup_ids != expected_ids or len(set(lineup_ids)) != len(lineup_ids):
            _fail(f"{source_id} membership roster/lineup binding differs")
        retained[source_id] = rosters
    return retained


def _world_artifact_sha256(
    suite: Mapping[str, object], *, source_id: str
) -> str:
    identities = _mapping(
        suite.get("world_artifact_identities"),
        label="suite world-artifact identities",
    )
    identity = _mapping(
        identities.get(source_id), label=f"{source_id} world-artifact identity"
    )
    return _digest(
        identity.get("sha256"), label=f"{source_id} world-artifact SHA-256"
    )


def _terminal_arm_freeze_sha256s(
    root: Mapping[str, object], *, suite: Mapping[str, object]
) -> dict[str, str]:
    raw_arms = _sequence(root.get("arms"), label="terminal root arms")
    arms: dict[str, Mapping[str, object]] = {}
    for raw_arm in raw_arms:
        arm = _mapping(raw_arm, label="terminal root arm")
        arm_id = arm.get("arm_id")
        if type(arm_id) is not str or arm_id in arms:
            _fail("terminal root arm registry differs")
        arms[arm_id] = arm
    if set(arms) != set(shadow_evaluation.ARM_ORDER):
        _fail("terminal root arm registry is incomplete")

    memberships = _mapping(
        suite.get("membership_lineup_ids_by_arm"),
        label="suite membership lineup IDs",
    )
    retained: dict[str, str] = {}
    for source_id in BASE_SOURCE_ORDER:
        arm = arms[source_id]
        artifacts = _mapping(
            arm.get("artifacts"), label=f"{source_id} arm artifacts"
        )
        world = _mapping(
            artifacts.get("world"), label=f"{source_id} arm world artifact"
        )
        world_identity = _mapping(
            world.get("identity"), label=f"{source_id} arm world identity"
        )
        if (
            arm.get("book_lineup_ids") != memberships[source_id]
            or arm.get("uses_realized_outcomes") is not False
            or arm.get("uses_post_lock_data") is not False
            or world_identity.get("sha256")
            != _world_artifact_sha256(suite, source_id=source_id)
        ):
            _fail(f"{source_id} terminal arm binding differs")
        retained[source_id] = _digest(
            arm.get("arm_freeze_sha256"),
            label=f"{source_id} arm-freeze SHA-256",
        )
    return retained


def _decoded_source_rosters(
    suite: Mapping[str, object],
    decoded_arm_artifacts: object,
    *,
    membership_rosters: Mapping[str, Sequence[Sequence[str]]],
) -> tuple[
    dict[str, dict[str, tuple[str, ...]]],
    dict[str, str],
    dict[str, str],
]:
    decoded_grid = _mapping(
        decoded_arm_artifacts, label="decoded source-arm artifacts"
    )
    if set(decoded_grid) != set(BASE_SOURCE_ORDER):
        _fail("decoded source-arm artifact registry differs")
    manifest = _mapping(suite.get("manifest"), label="suite manifest")
    prelock = _mapping(
        manifest.get("prelock_receipt"), label="suite prelock receipt"
    )
    arm_receipts = _mapping(
        prelock.get("arm_receipts"), label="suite arm receipts"
    )
    context = _slate_context(suite)
    membership_ids = _mapping(
        suite.get("membership_lineup_ids_by_arm"),
        label="suite membership lineup IDs",
    )

    roster_maps: dict[str, dict[str, tuple[str, ...]]] = {}
    decoded_sha256s: dict[str, str] = {}
    candidate_roster_sha256s: dict[str, str] = {}
    for source_id in BASE_SOURCE_ORDER:
        decoded = _mapping(
            decoded_grid[source_id], label=f"decoded {source_id} artifact"
        )
        if set(decoded) != _DECODED_FIELDS:
            _fail(f"decoded {source_id} artifact fields differ")
        decoded_sha = _digest(
            decoded.get("sha256"),
            label=f"decoded {source_id} artifact SHA-256",
        )
        if decoded_sha != _world_artifact_sha256(suite, source_id=source_id):
            _fail(f"decoded {source_id} artifact differs from suite authority")

        metadata = _mapping(
            decoded.get("metadata"), label=f"decoded {source_id} metadata"
        )
        forbidden = _forbidden_metadata_paths(metadata)
        if forbidden:
            _fail(
                f"decoded {source_id} metadata contains outcome carriers: "
                + ", ".join(forbidden)
            )
        decoded_context = _mapping(
            metadata.get("context"), label=f"decoded {source_id} context"
        )
        batch_metadata = _mapping(
            metadata.get("candidate_batch_metadata"),
            label=f"decoded {source_id} candidate-batch metadata",
        )
        if (
            metadata.get("artifact_version")
            != "prospective-recourse-worlds-v1"
            or metadata.get("uses_post_decision_outcomes") is not False
            or batch_metadata.get("uses_realized_outcomes", False) is not False
            or batch_metadata.get("post_lock_data_read", False) is not False
            or decoded_context.get("arm") != source_id
            or any(
                decoded_context.get(field) != context[field]
                for field in _CONTEXT_FIELDS
            )
        ):
            _fail(f"decoded {source_id} score-blind context differs")

        player_ids = tuple(
            _canonical_player_id(value, label=f"decoded {source_id} player ID")
            for value in _sequence(
                decoded.get("player_ids"),
                label=f"decoded {source_id} player IDs",
            )
        )
        if not player_ids or len(set(player_ids)) != len(player_ids):
            _fail(f"decoded {source_id} player universe differs")
        draws_shape = tuple(getattr(decoded.get("player_draws"), "shape", ()))
        if draws_shape != (len(player_ids), 50_000):
            _fail(f"decoded {source_id} player-world shape differs")
        player_universe = set(player_ids)

        raw_rosters = _sequence(
            decoded.get("candidate_rosters"),
            label=f"decoded {source_id} candidate rosters",
        )
        rosters = [
            _canonical_roster(
                raw_roster,
                label=f"decoded {source_id} candidate roster[{ordinal}]",
            )
            for ordinal, raw_roster in enumerate(raw_rosters)
        ]
        if any(not set(roster) <= player_universe for roster in rosters):
            _fail(f"decoded {source_id} candidate escapes its player universe")
        lineup_ids = [_lineup_id(roster) for roster in rosters]
        if len(set(lineup_ids)) != len(lineup_ids):
            _fail(f"decoded {source_id} candidate pool repeats")
        arm_receipt = _mapping(
            arm_receipts.get(source_id), label=f"suite {source_id} arm receipt"
        )
        candidate_rosters_sha256 = canonical_sha256(
            [list(roster) for roster in rosters]
        )
        if (
            arm_receipt.get("candidate_count") != len(rosters)
            or arm_receipt.get("candidate_order_sha256")
            != candidate_rosters_sha256
        ):
            _fail(f"decoded {source_id} candidate-order binding differs")

        roster_by_id = dict(zip(lineup_ids, rosters, strict=True))
        expected_membership_ids = _sequence(
            membership_ids.get(source_id),
            label=f"suite {source_id} membership lineup IDs",
        )
        expected_membership_rosters = membership_rosters[source_id]
        for lineup_id, expected_roster in zip(
            expected_membership_ids,
            expected_membership_rosters,
            strict=True,
        ):
            if roster_by_id.get(str(lineup_id)) != tuple(expected_roster):
                _fail(f"decoded {source_id} membership roster binding differs")

        roster_maps[source_id] = roster_by_id
        decoded_sha256s[source_id] = decoded_sha
        candidate_roster_sha256s[source_id] = candidate_rosters_sha256
    return roster_maps, decoded_sha256s, candidate_roster_sha256s


def _terminal_authority(
    value: object,
) -> tuple[
    Mapping[str, object],
    Mapping[str, object],
    dict[str, object],
]:
    try:
        root = shadow_evaluation.validate_terminal_prelock_root_v1(value)
    except Exception as exc:
        raise Week1OperatingRosterMaterializerError(
            "terminal prelock root validation failed"
        ) from exc
    envelope = _mapping(value, label="terminal prelock envelope")
    suite = _mapping(root.get("suite_authority"), label="root suite authority")
    if root.get("suite_authority_sha256") != suite.get("suite_authority_sha256"):
        _fail("terminal root suite binding differs")
    try:
        object_identity = shadow_evaluation.normalize_object_identity_v1(
            envelope.get("identity"), label="terminal prelock root identity"
        )
    except Exception as exc:
        raise Week1OperatingRosterMaterializerError(
            "terminal prelock root object identity differs"
        ) from exc
    root_binding = {
        "terminal_prelock_root_sha256": _digest(
            root.get("terminal_prelock_root_sha256"),
            label="terminal prelock root SHA-256",
        ),
        "terminal_prelock_envelope_sha256": _digest(
            envelope.get("terminal_prelock_envelope_sha256"),
            label="terminal prelock envelope SHA-256",
        ),
        "terminal_prelock_object_identity": object_identity,
    }
    return root, suite, root_binding


def _materialization_source_bindings(
    *,
    suite: Mapping[str, object],
    membership_rosters: Mapping[str, Sequence[Sequence[str]]],
    selected: Sequence[Mapping[str, object]],
    arm_freeze_sha256s: Mapping[str, str] | None,
    decoded_artifact_sha256s: Mapping[str, str] | None,
    candidate_roster_sha256s: Mapping[str, str] | None,
) -> list[dict[str, object]]:
    memberships = _mapping(
        suite.get("membership_lineup_ids_by_arm"),
        label="suite membership lineup IDs",
    )
    bindings: list[dict[str, object]] = []
    for source_id in BASE_SOURCE_ORDER:
        source_selected = [
            row for row in selected if row["source_id"] == source_id
        ]
        source_rosters = [list(roster) for roster in membership_rosters[source_id]]
        bindings.append({
            "source_id": source_id,
            "world_artifact_sha256": _world_artifact_sha256(
                suite, source_id=source_id
            ),
            "arm_freeze_sha256": (
                None
                if arm_freeze_sha256s is None
                else arm_freeze_sha256s[source_id]
            ),
            "decoded_artifact_sha256": (
                None
                if decoded_artifact_sha256s is None
                else decoded_artifact_sha256s[source_id]
            ),
            "candidate_rosters_sha256": (
                None
                if candidate_roster_sha256s is None
                else candidate_roster_sha256s[source_id]
            ),
            "membership_lineup_count": SOURCE_BOOK_SIZE,
            "ordered_membership_lineup_ids_sha256": canonical_sha256(
                list(memberships[source_id])
            ),
            "ordered_membership_rosters_sha256": canonical_sha256(
                source_rosters
            ),
            "selected_lineup_count": len(source_selected),
            "selected_lineup_ids_sha256": canonical_sha256([
                row["lineup_id"] for row in source_selected
            ]),
            "selected_rosters_sha256": canonical_sha256([
                row["player_ids"] for row in source_selected
            ]),
        })
    return bindings


def _source_membership_books(
    *,
    suite: Mapping[str, object],
    membership_rosters: Mapping[str, Sequence[Sequence[str]]],
) -> list[dict[str, object]]:
    membership_ids = _mapping(
        suite.get("membership_lineup_ids_by_arm"),
        label="suite membership lineup IDs",
    )
    books: list[dict[str, object]] = []
    for source_id in BASE_SOURCE_ORDER:
        lineup_ids = list(membership_ids[source_id])
        rosters = [list(roster) for roster in membership_rosters[source_id]]
        books.append({
            "source_id": source_id,
            "lineup_ids": lineup_ids,
            "rosters": rosters,
            "lineup_ids_sha256": canonical_sha256(lineup_ids),
            "rosters_sha256": canonical_sha256(rosters),
        })
    return books


def validate_week1_operating_roster_materialization_v1(
    value: object,
) -> dict[str, object]:
    """Reopen the self-hashed roster materialization without source I/O."""

    materialization = dict(
        _mapping(value, label="Week-1 roster materialization")
    )
    fields = {
        "schema_version",
        "materializer_id",
        "complete",
        "authority_mode",
        "k",
        "slate_context",
        "slate_context_sha256",
        "suite_authority_schema_version",
        "suite_authority_sha256",
        "player_identity_bridge",
        "player_identity_bridge_sha256",
        "terminal_root_binding",
        "adapter_envelope",
        "adapter_envelope_sha256",
        "source_membership_books",
        "source_membership_books_sha256",
        "source_arm_bindings",
        "source_arm_bindings_sha256",
        "selected_lineups",
        "selected_lineup_ids_sha256",
        "selected_rosters_sha256",
        "cap4_used",
        "tier3_used",
        "uses_realized_outcomes",
        "outcome_fields",
        "materialization_sha256",
    }
    if set(materialization) != fields:
        _fail("Week-1 roster materialization fields differ")
    retained_hash = _digest(
        materialization.get("materialization_sha256"),
        label="roster materialization SHA-256",
    )
    unhashed = dict(materialization)
    unhashed.pop("materialization_sha256")
    if retained_hash != canonical_sha256(unhashed):
        _fail("Week-1 roster materialization hash differs")

    mode = materialization.get("authority_mode")
    if (
        materialization.get("schema_version") != SCHEMA_VERSION
        or materialization.get("materializer_id") != MATERIALIZER_ID
        or materialization.get("complete") is not True
        or mode not in {TERMINAL_AUTHORITY_MODE, DECODED_AUTHORITY_MODE}
        or materialization.get("suite_authority_schema_version")
        != shadow_evaluation.SUITE_AUTHORITY_SCHEMA
        or materialization.get("cap4_used") is not False
        or materialization.get("tier3_used") is not False
        or materialization.get("uses_realized_outcomes") is not False
        or materialization.get("outcome_fields") != []
    ):
        _fail("Week-1 roster materialization fixed law differs")
    suite_sha = _digest(
        materialization.get("suite_authority_sha256"),
        label="bound suite authority SHA-256",
    )
    context = _mapping(
        materialization.get("slate_context"), label="slate context"
    )
    if set(context) != set(_CONTEXT_FIELDS) or any(
        value is None for value in context.values()
    ):
        _fail("materialized slate context differs")
    if materialization.get("slate_context_sha256") != canonical_sha256(context):
        _fail("materialized slate-context hash differs")

    player_bridge = _sequence(
        materialization.get("player_identity_bridge"),
        label="materialized player identity bridge",
    )
    if materialization.get(
        "player_identity_bridge_sha256"
    ) != canonical_sha256(player_bridge):
        _fail("materialized player identity-bridge hash differs")
    normalized_player_bridge = _player_identity_bridge({
        "player_identity_bridge": player_bridge
    })
    player_bridge_by_dk_id = {
        str(row["dk_draftable_id"]): row for row in normalized_player_bridge
    }

    adapter = validate_week1_operating_book_suite_envelope_v1(
        materialization.get("adapter_envelope")
    )
    if (
        materialization.get("adapter_envelope_sha256")
        != adapter["envelope_sha256"]
        or adapter["suite_authority_sha256"] != suite_sha
        or materialization.get("k") != adapter["k"]
        or adapter["cap4_used"] is not False
        or adapter["tier3_used"] is not False
        or adapter["uses_realized_outcomes"] is not False
    ):
        _fail("roster materialization adapter binding differs")

    raw_membership_books = _sequence(
        materialization.get("source_membership_books"),
        label="source membership books",
    )
    if materialization.get(
        "source_membership_books_sha256"
    ) != canonical_sha256(raw_membership_books):
        _fail("source membership-book hash differs")
    if len(raw_membership_books) != len(BASE_SOURCE_ORDER):
        _fail("source membership-book count differs")
    adapter_book_bindings = {
        row["source_id"]: row
        for row in _sequence(
            adapter.get("source_book_bindings"),
            label="adapter source-book bindings",
        )
    }
    membership_roster_by_id: dict[
        str, dict[str, tuple[str, ...]]
    ] = {}
    normalized_membership_books: dict[str, dict[str, object]] = {}
    for source_id, raw_book in zip(
        BASE_SOURCE_ORDER, raw_membership_books, strict=True
    ):
        book = _mapping(raw_book, label=f"{source_id} membership book")
        if set(book) != {
            "source_id",
            "lineup_ids",
            "rosters",
            "lineup_ids_sha256",
            "rosters_sha256",
        }:
            _fail("source membership-book fields differ")
        raw_lineup_ids = _sequence(
            book.get("lineup_ids"),
            label=f"{source_id} membership lineup IDs",
        )
        raw_rosters = _sequence(
            book.get("rosters"), label=f"{source_id} membership rosters"
        )
        if (
            book.get("source_id") != source_id
            or len(raw_lineup_ids) != SOURCE_BOOK_SIZE
            or len(raw_rosters) != SOURCE_BOOK_SIZE
        ):
            _fail(f"{source_id} membership book is not exact-80")
        rosters = [
            _canonical_roster(
                raw_roster,
                label=f"{source_id} membership roster[{ordinal}]",
            )
            for ordinal, raw_roster in enumerate(raw_rosters)
        ]
        if any(
            player_id not in player_bridge_by_dk_id
            for roster in rosters
            for player_id in roster
        ):
            _fail(f"{source_id} membership roster escapes the player bridge")
        recomputed_lineup_ids = [_lineup_id(roster) for roster in rosters]
        if any(
            type(lineup_id) is not str
            or _LINEUP_ID.fullmatch(lineup_id) is None
            for lineup_id in raw_lineup_ids
        ) or (
            recomputed_lineup_ids != raw_lineup_ids
            or len(set(recomputed_lineup_ids)) != SOURCE_BOOK_SIZE
            or book.get("lineup_ids_sha256")
            != canonical_sha256(recomputed_lineup_ids)
            or book.get("rosters_sha256")
            != canonical_sha256([list(roster) for roster in rosters])
        ):
            _fail(f"{source_id} membership roster/lineup binding differs")
        adapter_book = adapter_book_bindings.get(source_id)
        if (
            adapter_book is None
            or adapter_book.get("lineup_count") != SOURCE_BOOK_SIZE
            or adapter_book.get("ordered_lineup_ids_sha256")
            != canonical_sha256(recomputed_lineup_ids)
        ):
            _fail(f"{source_id} membership book differs from adapter")
        membership_roster_by_id[source_id] = dict(
            zip(recomputed_lineup_ids, rosters, strict=True)
        )
        normalized_membership_books[source_id] = {
            "lineup_ids_sha256": canonical_sha256(recomputed_lineup_ids),
            "rosters_sha256": canonical_sha256(
                [list(roster) for roster in rosters]
            ),
        }

    root_binding = materialization.get("terminal_root_binding")
    if mode == TERMINAL_AUTHORITY_MODE:
        binding = _mapping(root_binding, label="terminal root binding")
        if set(binding) != {
            "terminal_prelock_root_sha256",
            "terminal_prelock_envelope_sha256",
            "terminal_prelock_object_identity",
        }:
            _fail("terminal root binding fields differ")
        _digest(
            binding.get("terminal_prelock_root_sha256"),
            label="bound terminal root SHA-256",
        )
        _digest(
            binding.get("terminal_prelock_envelope_sha256"),
            label="bound terminal envelope SHA-256",
        )
        try:
            shadow_evaluation.normalize_object_identity_v1(
                binding.get("terminal_prelock_object_identity"),
                label="bound terminal root object identity",
            )
        except Exception as exc:
            raise Week1OperatingRosterMaterializerError(
                "bound terminal root object identity differs"
            ) from exc
    elif root_binding is not None:
        _fail("suite-decoded materialization unexpectedly binds a root")

    selected = _sequence(
        materialization.get("selected_lineups"), label="selected lineups"
    )
    k = materialization.get("k")
    if type(k) is not int or k not in (80, 100) or len(selected) != k:
        _fail("materialized selected-lineup count differs")
    adapter_selected = _sequence(
        _mapping(
            adapter.get("compositor_receipt"), label="compositor receipt"
        ).get("entered_lineups"),
        label="compositor entered lineups",
    )
    normalized_selected: list[dict[str, object]] = []
    lineup_ids: list[str] = []
    roster_keys: list[tuple[str, ...]] = []
    for ordinal, (raw_row, raw_adapter_row) in enumerate(
        zip(selected, adapter_selected, strict=True), start=1
    ):
        row = dict(_mapping(raw_row, label=f"selected lineup[{ordinal}]"))
        adapter_row = _mapping(
            raw_adapter_row, label=f"compositor entered lineup[{ordinal}]"
        )
        if set(row) != {
            "entry_rank",
            "lineup_id",
            "source_id",
            "source_role",
            "source_rank",
            "player_ids",
            "roster_sha256",
        }:
            _fail("selected lineup fields differ")
        lineup_id = row.get("lineup_id")
        roster = _canonical_roster(
            row.get("player_ids"), label=f"selected lineup[{ordinal}] roster"
        )
        roster_sha = _digest(
            row.get("roster_sha256"),
            label=f"selected lineup[{ordinal}] roster SHA-256",
        )
        if (
            type(lineup_id) is not str
            or _LINEUP_ID.fullmatch(lineup_id) is None
            or row.get("entry_rank") != ordinal
            or roster_sha != canonical_sha256(list(roster))
            or lineup_id != f"lineup-v1-{roster_sha}"
            or membership_roster_by_id.get(str(row.get("source_id")), {}).get(
                lineup_id
            )
            != roster
            or any(
                row.get(field) != adapter_row.get(field)
                for field in (
                    "entry_rank",
                    "lineup_id",
                    "source_id",
                    "source_role",
                    "source_rank",
                )
            )
        ):
            _fail("selected lineup identity or adapter binding differs")
        lineup_ids.append(lineup_id)
        roster_keys.append(roster)
        normalized_selected.append({**row, "player_ids": list(roster)})
    if len(set(lineup_ids)) != k or len(set(roster_keys)) != k:
        _fail("materialized selected lineups are not globally unique")
    if (
        materialization.get("selected_lineup_ids_sha256")
        != canonical_sha256(lineup_ids)
        or materialization.get("selected_rosters_sha256")
        != canonical_sha256([list(roster) for roster in roster_keys])
    ):
        _fail("materialized selected-lineup hashes differ")

    raw_bindings = _sequence(
        materialization.get("source_arm_bindings"),
        label="source-arm bindings",
    )
    if materialization.get("source_arm_bindings_sha256") != canonical_sha256(
        raw_bindings
    ):
        _fail("source-arm binding hash differs")
    adapter_bindings = adapter_book_bindings
    if len(raw_bindings) != len(BASE_SOURCE_ORDER):
        _fail("source-arm binding count differs")
    for source_id, raw_binding in zip(
        BASE_SOURCE_ORDER, raw_bindings, strict=True
    ):
        binding = _mapping(raw_binding, label=f"{source_id} source binding")
        if set(binding) != {
            "source_id",
            "world_artifact_sha256",
            "arm_freeze_sha256",
            "decoded_artifact_sha256",
            "candidate_rosters_sha256",
            "membership_lineup_count",
            "ordered_membership_lineup_ids_sha256",
            "ordered_membership_rosters_sha256",
            "selected_lineup_count",
            "selected_lineup_ids_sha256",
            "selected_rosters_sha256",
        }:
            _fail("source-arm binding fields differ")
        _digest(
            binding.get("world_artifact_sha256"),
            label=f"{source_id} world-artifact SHA-256",
        )
        _digest(
            binding.get("ordered_membership_rosters_sha256"),
            label=f"{source_id} membership-roster SHA-256",
        )
        if mode == TERMINAL_AUTHORITY_MODE:
            _digest(
                binding.get("arm_freeze_sha256"),
                label=f"{source_id} arm-freeze SHA-256",
            )
            if (
                binding.get("decoded_artifact_sha256") is not None
                or binding.get("candidate_rosters_sha256") is not None
            ):
                _fail("terminal source binding unexpectedly binds decoded data")
        else:
            decoded_sha = _digest(
                binding.get("decoded_artifact_sha256"),
                label=f"{source_id} decoded-artifact SHA-256",
            )
            _digest(
                binding.get("candidate_rosters_sha256"),
                label=f"{source_id} candidate-roster SHA-256",
            )
            if (
                binding.get("arm_freeze_sha256") is not None
                or decoded_sha != binding.get("world_artifact_sha256")
            ):
                _fail("decoded source binding differs")

        source_rows = [
            row for row in normalized_selected if row["source_id"] == source_id
        ]
        adapter_binding = adapter_bindings.get(source_id)
        if (
            binding.get("source_id") != source_id
            or binding.get("membership_lineup_count") != SOURCE_BOOK_SIZE
            or adapter_binding is None
            or binding.get("ordered_membership_lineup_ids_sha256")
            != normalized_membership_books[source_id]["lineup_ids_sha256"]
            or binding.get("ordered_membership_lineup_ids_sha256")
            != adapter_binding["ordered_lineup_ids_sha256"]
            or binding.get("ordered_membership_rosters_sha256")
            != normalized_membership_books[source_id]["rosters_sha256"]
            or binding.get("selected_lineup_count") != len(source_rows)
            or binding.get("selected_lineup_ids_sha256")
            != canonical_sha256([row["lineup_id"] for row in source_rows])
            or binding.get("selected_rosters_sha256")
            != canonical_sha256([row["player_ids"] for row in source_rows])
        ):
            _fail(f"{source_id} source-selection binding differs")
    return materialization


def build_week1_operating_roster_materialization_v1(
    *,
    k: int,
    terminal_prelock_root: object | None = None,
    suite_authority: object | None = None,
    decoded_arm_artifacts: object | None = None,
) -> dict[str, object]:
    """Build an exact K80/K100 roster book from one score-blind authority.

    Exactly one input mode is allowed:

    * ``terminal_prelock_root`` is the complete create-once terminal envelope;
      its validated suite manifest supplies the exact membership rosters.
    * ``suite_authority`` and ``decoded_arm_artifacts`` provide the validated
      suite plus exactly the core/all-boom/BX60 decoder outputs.
    """

    terminal_mode = terminal_prelock_root is not None
    decoded_mode = suite_authority is not None or decoded_arm_artifacts is not None
    if terminal_mode == decoded_mode:
        _fail("provide exactly one terminal or suite-decoded authority mode")

    root_binding: dict[str, object] | None
    arm_freeze_sha256s: dict[str, str] | None
    decoded_artifact_sha256s: dict[str, str] | None
    candidate_roster_sha256s: dict[str, str] | None
    if terminal_mode:
        root, suite, root_binding = _terminal_authority(terminal_prelock_root)
        authority_mode = TERMINAL_AUTHORITY_MODE
        membership_rosters = _suite_membership_rosters(suite)
        roster_maps = {
            source_id: {
                _lineup_id(roster): roster
                for roster in membership_rosters[source_id]
            }
            for source_id in BASE_SOURCE_ORDER
        }
        arm_freeze_sha256s = _terminal_arm_freeze_sha256s(
            root, suite=suite
        )
        decoded_artifact_sha256s = None
        candidate_roster_sha256s = None
        context = _slate_context(suite)
        if (
            root.get("season") != context["season"]
            or root.get("week") != context["week"]
            or root.get("lock_at") != context["slate_lock_at"]
        ):
            _fail("terminal root slate context differs from suite")
    else:
        if suite_authority is None or decoded_arm_artifacts is None:
            _fail("suite-decoded mode requires both authority and artifacts")
        try:
            suite = shadow_evaluation.validate_suite_authority_v1(
                suite_authority
            )
        except Exception as exc:
            raise Week1OperatingRosterMaterializerError(
                "suite authority validation failed"
            ) from exc
        suite = _mapping(suite, label="validated suite authority")
        authority_mode = DECODED_AUTHORITY_MODE
        root_binding = None
        arm_freeze_sha256s = None
        membership_rosters = _suite_membership_rosters(suite)
        (
            roster_maps,
            decoded_artifact_sha256s,
            candidate_roster_sha256s,
        ) = _decoded_source_rosters(
            suite,
            decoded_arm_artifacts,
            membership_rosters=membership_rosters,
        )
        context = _slate_context(suite)

    try:
        adapter = build_week1_operating_book_from_suite_authority_v1(
            suite, k=k
        )
    except Week1OperatingBookSuiteAdapterError as exc:
        raise Week1OperatingRosterMaterializerError(
            "Week-1 suite adapter rejected the authority"
        ) from exc
    receipt = _mapping(
        adapter.get("compositor_receipt"), label="compositor receipt"
    )
    entered = _sequence(
        receipt.get("entered_lineups"), label="compositor entered lineups"
    )
    selected: list[dict[str, object]] = []
    for raw_row in entered:
        row = _mapping(raw_row, label="compositor entered lineup")
        source_id = row.get("source_id")
        lineup_id = row.get("lineup_id")
        if source_id not in roster_maps or type(lineup_id) is not str:
            _fail("compositor selected an unknown source or lineup")
        roster = roster_maps[source_id].get(lineup_id)
        if roster is None:
            _fail(f"{source_id} selected lineup lacks a bound exact roster")
        roster_sha = canonical_sha256(list(roster))
        if lineup_id != f"lineup-v1-{roster_sha}":
            _fail("selected lineup ID differs from its canonical roster")
        selected.append({
            "entry_rank": row["entry_rank"],
            "lineup_id": lineup_id,
            "source_id": source_id,
            "source_role": row["source_role"],
            "source_rank": row["source_rank"],
            "player_ids": list(roster),
            "roster_sha256": roster_sha,
        })
    lineup_ids = [str(row["lineup_id"]) for row in selected]
    roster_keys = [tuple(row["player_ids"]) for row in selected]
    if len(set(lineup_ids)) != len(selected) or len(set(roster_keys)) != len(selected):
        _fail("selected roster materialization is not globally unique")

    source_bindings = _materialization_source_bindings(
        suite=suite,
        membership_rosters=membership_rosters,
        selected=selected,
        arm_freeze_sha256s=arm_freeze_sha256s,
        decoded_artifact_sha256s=decoded_artifact_sha256s,
        candidate_roster_sha256s=candidate_roster_sha256s,
    )
    membership_books = _source_membership_books(
        suite=suite, membership_rosters=membership_rosters
    )
    player_bridge = _player_identity_bridge(suite)
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "materializer_id": MATERIALIZER_ID,
        "complete": True,
        "authority_mode": authority_mode,
        "k": k,
        "slate_context": context,
        "slate_context_sha256": canonical_sha256(context),
        "suite_authority_schema_version": suite["schema_version"],
        "suite_authority_sha256": suite["suite_authority_sha256"],
        "player_identity_bridge": player_bridge,
        "player_identity_bridge_sha256": canonical_sha256(player_bridge),
        "terminal_root_binding": root_binding,
        "adapter_envelope": adapter,
        "adapter_envelope_sha256": adapter["envelope_sha256"],
        "source_membership_books": membership_books,
        "source_membership_books_sha256": canonical_sha256(membership_books),
        "source_arm_bindings": source_bindings,
        "source_arm_bindings_sha256": canonical_sha256(source_bindings),
        "selected_lineups": selected,
        "selected_lineup_ids_sha256": canonical_sha256(lineup_ids),
        "selected_rosters_sha256": canonical_sha256(
            [list(roster) for roster in roster_keys]
        ),
        "cap4_used": False,
        "tier3_used": False,
        "uses_realized_outcomes": False,
        "outcome_fields": [],
    }
    body["materialization_sha256"] = canonical_sha256(body)
    return validate_week1_operating_roster_materialization_v1(body)


__all__ = [
    "DECODED_AUTHORITY_MODE",
    "MATERIALIZER_ID",
    "SCHEMA_VERSION",
    "TERMINAL_AUTHORITY_MODE",
    "Week1OperatingRosterMaterializerError",
    "build_week1_operating_roster_materialization_v1",
    "validate_week1_operating_roster_materialization_v1",
]
