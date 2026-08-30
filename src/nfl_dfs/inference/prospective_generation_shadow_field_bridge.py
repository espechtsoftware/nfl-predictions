"""Post-settlement contest-field bridge for generation shadows.

The prelock generation suite deliberately knows nothing about contest results.
This module is the narrow post-settlement seam that binds a complete DraftKings
standings capture to the *exact* lineup memberships already sealed by the
terminal prelock root.

There are two stages:

Before stage one, the independent scorer publishes the exact content returned
by ``build_independent_realized_score_source_payload_v1``.  Its immutable
identity is required even when contest-field evidence is unavailable.

``prepare_contest_field_bridge_v1``
    Validates the terminal root first, then the settled field, payout ladder,
    player identity map and point-in-time participant-strength rows.  It emits
    canonical component payloads ready for create-once publication.  If a
    required authority is absent, it returns an explicit raw-score-only bridge
    and cannot be used for contest-EV claims.

``bind_contest_field_bridge_v1``
    Verifies content identities for every prepared component and emits the
    evaluator-ready capture and lineup rows.  No external write is performed
    here; publication and generation-pinned reopen remain operator work.

An unentered shadow lineup receives a hypothetical competition rank against
the complete field, but it never receives invented contest facts: its entered
flag is false, matching entry list is empty, duplicate count is zero and
actual split payout is inapplicable/zero.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Final

import pandas as pd

from .generation_exposure import canonical_json_bytes, canonical_sha256
from ..research.object_identity import content_identity


PREPARATION_SCHEMA: Final = "prospective-generation-shadow-field-preparation/v1"
BRIDGE_SCHEMA: Final = "prospective-generation-shadow-field-bridge/v1"
MEMBERSHIP_SCHEMA: Final = "prospective-generation-shadow-memberships/v1"
FIELD_ROSTERS_SCHEMA: Final = "prospective-generation-shadow-field-rosters/v1"
FIELD_OWNERSHIP_SCHEMA: Final = "prospective-generation-shadow-field-ownership/v1"
PAYOUT_TABLE_SCHEMA: Final = "prospective-generation-shadow-payout-table/v1"
PARTICIPANT_STRENGTH_SCHEMA: Final = (
    "prospective-generation-shadow-participant-strength/v1"
)
PLAYER_IDENTITY_SCHEMA: Final = "prospective-generation-shadow-player-identity/v1"
ENTRY_MAPPING_SCHEMA: Final = "prospective-generation-shadow-entry-mapping/v1"
REALIZED_SCORE_SOURCE_SCHEMA: Final = (
    "prospective-generation-shadow-independent-lineup-scores/v1"
)
PROBABILITY_SCALE: Final = 1_000_000

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_LINEUP_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_COMPONENT_NAMES: Final = (
    "payout_table",
    "field_rosters",
    "field_ownership",
    "participant_strength",
    "player_identity",
    "shadow_entry_mapping",
)


class ProspectiveContestFieldBridgeError(ValueError):
    """A claimed contest-field bridge violated the post-settlement contract."""


def _fail(message: str) -> None:
    raise ProspectiveContestFieldBridgeError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be a mapping")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, Sequence
    ):
        _fail(f"{label} must be a sequence")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value.strip():
        _fail(f"{label} must be a nonempty string")
    return value.strip()


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _timestamp(value: object, *, label: str) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif type(value) is str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ProspectiveContestFieldBridgeError(
                f"{label} must be an ISO-8601 timestamp"
            ) from exc
    else:
        _fail(f"{label} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None:
        _fail(f"{label} must include a UTC offset")
    return parsed.astimezone(timezone.utc).isoformat()


def _self_hashed(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    retained = dict(body)
    if field in retained:
        _fail(f"{field} already exists")
    retained[field] = canonical_sha256(retained)
    return retained


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    digest = value.get(field)
    if type(digest) is not str or _HEX64.fullmatch(digest) is None:
        _fail(f"{label} self-hash differs")
    body = {key: child for key, child in value.items() if key != field}
    if canonical_sha256(body) != digest:
        _fail(f"{label} self-hash differs")


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    try:
        uri, generation, digest, size = content_identity(item)
    except (KeyError, TypeError, ValueError) as exc:
        raise ProspectiveContestFieldBridgeError(
            f"{label} is not a content identity"
        ) from exc
    if not str(uri).startswith("gs://"):
        _fail(f"{label} must be a GCS object identity")
    return {
        "uri": str(uri),
        "generation": str(generation),
        "sha256": str(digest),
        "bytes": int(size),
    }


def _identity_for_payload(
    value: object, payload: Mapping[str, object], *, label: str
) -> dict[str, object]:
    identity = _identity(value, label=label)
    raw = canonical_json_bytes(payload)
    if identity["sha256"] != canonical_sha256(payload) or identity["bytes"] != len(raw):
        _fail(f"{label} does not bind the canonical component payload")
    return identity


def _money_micro(value: object, *, label: str) -> int:
    if value is None or pd.isna(value):
        _fail(f"{label} is missing")
    try:
        retained = (Decimal(str(value)) * PROBABILITY_SCALE).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    except (InvalidOperation, ValueError) as exc:
        raise ProspectiveContestFieldBridgeError(
            f"{label} is not finite money"
        ) from exc
    result = int(retained)
    if result < 0:
        _fail(f"{label} must be nonnegative")
    return result


def _score_micro(value: object, *, label: str) -> int:
    if value is None or pd.isna(value):
        _fail(f"{label} is missing")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ProspectiveContestFieldBridgeError(
            f"{label} is not a finite score"
        ) from exc
    if not number.is_finite():
        _fail(f"{label} is not a finite score")
    return int((number * PROBABILITY_SCALE).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    ))


def _lineup_id(player_ids: Sequence[str]) -> str:
    roster = sorted(player_ids)
    if len(roster) != 9 or len(set(roster)) != 9 or any(not value for value in roster):
        _fail("a mapped field roster is not nine unique player IDs")
    return f"lineup-v1-{canonical_sha256(roster)}"


def _project_terminal_prelock_root(
    terminal_prelock_root: Mapping[str, object],
) -> dict[str, object]:
    """Validate the terminal first and project every frozen membership.

    The import is intentionally local: the evaluation contract can import this
    adapter later without creating a module cycle.
    """

    from . import prospective_generation_shadow_evaluation as evaluation

    root = evaluation.validate_terminal_prelock_root_v1(terminal_prelock_root)
    envelope = _mapping(terminal_prelock_root, label="terminal prelock envelope")
    terminal_identity = _identity(
        envelope.get("identity"), label="terminal prelock root identity"
    )
    groups: list[dict[str, object]] = []
    membership_by_lineup: defaultdict[str, list[str]] = defaultdict(list)
    for raw_arm in root["arms"]:
        arm = _mapping(raw_arm, label="terminal arm")
        arm_id = _string(arm.get("arm_id"), label="arm ID")
        candidates = [
            _string(value, label=f"{arm_id} candidate lineup ID")
            for value in _sequence(
                arm.get("candidate_lineup_ids"),
                label=f"{arm_id} candidate lineup IDs",
            )
        ]
        book = [
            _string(value, label=f"{arm_id} incumbent book lineup ID")
            for value in _sequence(
                arm.get("book_lineup_ids"), label=f"{arm_id} incumbent book"
            )
        ]
        group_rows = [
            (f"arm:{arm_id}:candidate-pool", candidates),
            (f"arm:{arm_id}:incumbent-retrieval", book),
        ]
        interaction = arm.get("retrieval_interaction")
        if interaction is not None:
            cell = _mapping(interaction, label=f"{arm_id} retrieval interaction")
            cap_book = [
                _string(value, label=f"{arm_id} cap-4 lineup ID")
                for value in _sequence(
                    cell.get("book_lineup_ids"), label=f"{arm_id} cap-4 book"
                )
            ]
            group_rows.append((f"arm:{arm_id}:cap4-prefix-then-fill", cap_book))
        for group_id, lineup_ids in group_rows:
            if not lineup_ids or len(set(lineup_ids)) != len(lineup_ids):
                _fail(f"{group_id} is empty or repeats a lineup")
            for lineup_id in lineup_ids:
                if _LINEUP_ID.fullmatch(lineup_id) is None:
                    _fail(f"{group_id} contains a noncanonical lineup ID")
                membership_by_lineup[lineup_id].append(group_id)
            groups.append({
                "membership_id": group_id,
                "lineup_count": len(lineup_ids),
                "lineup_ids": lineup_ids,
                "lineup_ids_sha256": canonical_sha256(lineup_ids),
            })
    lineup_rows = [{
        "lineup_id": lineup_id,
        "membership_ids": sorted(membership_by_lineup[lineup_id]),
    } for lineup_id in sorted(membership_by_lineup)]
    body: dict[str, object] = {
        "schema_version": MEMBERSHIP_SCHEMA,
        "season": int(root["season"]),
        "week": int(root["week"]),
        "slate_id": str(root["slate_id"]),
        "lock_at": str(root["lock_at"]),
        "terminal_prelock_root_identity": terminal_identity,
        "terminal_prelock_root_sha256": str(
            root["terminal_prelock_root_sha256"]
        ),
        "membership_groups": groups,
        "membership_groups_sha256": canonical_sha256(groups),
        "lineup_memberships": lineup_rows,
        "lineup_memberships_sha256": canonical_sha256(lineup_rows),
        "required_lineup_count": len(lineup_rows),
    }
    return _self_hashed(body, field="membership_projection_sha256")


def _normalize_realized_scores(
    value: Mapping[str, int], projection: Mapping[str, object]
) -> list[dict[str, object]]:
    required = {
        str(row["lineup_id"])
        for row in projection["lineup_memberships"]  # type: ignore[index]
    }
    if set(value) != required:
        missing = sorted(required - set(value))
        unexpected = sorted(set(value) - required)
        _fail(
            "realized-score registry does not exactly cover frozen lineups: "
            f"missing={missing[:3]} unexpected={unexpected[:3]}"
        )
    rows = []
    for lineup_id in sorted(required):
        score = value[lineup_id]
        if type(score) is not int:
            _fail(f"{lineup_id} realized score must be integer micro-points")
        rows.append({"lineup_id": lineup_id, "realized_score_micro": score})
    return rows


def _realized_score_source_payload(
    *,
    projection: Mapping[str, object],
    captured_at: str,
    score_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": REALIZED_SCORE_SOURCE_SCHEMA,
        "season": projection["season"],
        "week": projection["week"],
        "slate_id": projection["slate_id"],
        "captured_at": captured_at,
        "producer_class": "independent-realized-lineup-score-source",
        "independent_from_generation": True,
        "terminal_prelock_root_binding_present": False,
        "lineup_count": len(score_rows),
        "lineup_rows": list(score_rows),
        "lineup_rows_sha256": canonical_sha256(score_rows),
    }


def build_independent_realized_score_source_payload_v1(
    *,
    terminal_prelock_root: Mapping[str, object],
    captured_at: datetime | str,
    realized_score_micro_by_lineup_id: Mapping[str, int],
) -> dict[str, object]:
    """Build the exact content an independent scorer must publish.

    The content carries lineup identities and scores but no arm, treatment or
    terminal-root identity.  Publish these canonical bytes create-once, obtain
    their generation-pinned identity, and pass that identity to
    :func:`prepare_contest_field_bridge_v1`.
    """

    projection = _project_terminal_prelock_root(terminal_prelock_root)
    captured = _timestamp(captured_at, label="realized-score captured-at")
    if datetime.fromisoformat(captured) <= datetime.fromisoformat(
        str(projection["lock_at"])
    ):
        _fail("realized-score source was not produced after slate lock")
    score_rows = _normalize_realized_scores(
        realized_score_micro_by_lineup_id, projection
    )
    return _realized_score_source_payload(
        projection=projection, captured_at=captured, score_rows=score_rows
    )


def _raw_score_bridge(
    *,
    projection: Mapping[str, object],
    captured_at: str,
    score_rows: Sequence[Mapping[str, object]],
    realized_score_source_identity: Mapping[str, object],
    deficiencies: Sequence[str],
) -> dict[str, object]:
    normalized_deficiencies = sorted(set(deficiencies))
    if not normalized_deficiencies:
        _fail("raw-score-only bridge requires at least one deficiency")
    body: dict[str, object] = {
        "schema_version": BRIDGE_SCHEMA,
        "season": projection["season"],
        "week": projection["week"],
        "slate_id": projection["slate_id"],
        "captured_at": captured_at,
        "terminal_prelock_root_identity": projection[
            "terminal_prelock_root_identity"
        ],
        "terminal_prelock_root_sha256": projection[
            "terminal_prelock_root_sha256"
        ],
        "membership_projection_sha256": projection[
            "membership_projection_sha256"
        ],
        "realized_score_source_identity": dict(
            realized_score_source_identity
        ),
        "status": "raw-score-only-no-contest-ev",
        "evidence_scope": "raw-score-only-no-contest-ev",
        "complete_contest_field_capture": False,
        "complete_field_rank_claim_allowed": False,
        "contest_ev_claim_allowed": False,
        "allocation_recommendation_allowed": False,
        "deficiencies": normalized_deficiencies,
        "component_identities": None,
        "evaluator_contest_field_capture": None,
        "evaluator_lineup_rows": list(score_rows),
        "entered_shadow_lineup_count": None,
        "not_entered_shadow_lineup_count": None,
        "uses_realized_outcomes": True,
    }
    return _self_hashed(body, field="field_bridge_sha256")


def _missing_inputs(**values: object) -> list[str]:
    missing = []
    for name, value in values.items():
        if value is None or (
            isinstance(value, Sequence)
            and not isinstance(value, (str, bytes, bytearray))
            and len(value) == 0
        ):
            missing.append(f"{name}_missing")
    return missing


def _capture_contract(
    *,
    projection: Mapping[str, object],
    capture_manifest: Mapping[str, object],
    validated_capture: Mapping[str, object],
    capture_source_identity: Mapping[str, object],
) -> tuple[str, int, str, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    manifest = _mapping(capture_manifest, label="DK field capture manifest")
    contest = _mapping(manifest.get("contest"), label="captured contest")
    validation = _mapping(
        manifest.get("validation"), label="capture validation receipt"
    )
    source = _mapping(manifest.get("source"), label="capture source")
    if (
        manifest.get("status") != "applied"
        or manifest.get("capture_version") != "dk-full-field-v1"
        or manifest.get("evidence_timing") != "post_settlement"
        or validation.get("operator_confirmed_settled") is not True
        or validation.get("operator_confirmed_full_field") is not True
        or validation.get("operator_confirmed_contest_metadata") is not True
        or validation.get("settled_points_complete") is not True
        or validation.get("entry_ids_unique") is not True
        or validation.get("competition_ranks_reproduced") is not True
        or validation.get("ownership_reproduced_from_entries") is not True
    ):
        _fail("DK field capture is not applied, settled and operator-confirmed")
    if (
        contest.get("season") != projection["season"]
        or contest.get("week") != projection["week"]
        or contest.get("roster_format") != "classic"
    ):
        _fail("DK field capture does not match the frozen Classic slate")
    contest_id = _string(contest.get("contest_id"), label="contest ID")
    contest_name = _string(contest.get("contest_name"), label="contest name")
    expected = _integer(
        contest.get("expected_entries"), label="contest field size", minimum=2
    )
    if contest.get("observed_entries") != expected:
        _fail("capture manifest does not contain the entire contest field")
    captured = _mapping(validated_capture, label="validated capture")
    entries = captured.get("entries")
    ownership = captured.get("ownership")
    if not isinstance(entries, pd.DataFrame) or not isinstance(ownership, pd.DataFrame):
        _fail("validated capture lacks entry/ownership frames")
    if len(entries) != expected or entries.empty or ownership.empty:
        _fail("validated capture does not reproduce the entire contest field")
    if (
        captured.get("roster_format") != "classic"
        or captured.get("source_sha256") != source.get("sha256")
        or captured.get("source_bytes") != source.get("bytes")
    ):
        _fail("validated capture/source identity differs from its manifest")
    source_identity = _identity(
        capture_source_identity, label="captured full-field source identity"
    )
    if (
        source_identity["uri"] != source.get("uri")
        or source_identity["sha256"] != source.get("sha256")
        or source_identity["bytes"] != source.get("bytes")
    ):
        _fail("captured full-field source identity differs from its manifest")
    return (
        contest_id,
        expected,
        contest_name,
        entries.copy(),
        ownership.copy(),
        source_identity,
    )


def _normalize_player_identity(
    rows: Sequence[Mapping[str, object]],
    entries: pd.DataFrame,
    ownership: pd.DataFrame,
    *,
    season: int,
    week: int,
    slate_id: str,
) -> tuple[dict[str, str], dict[str, object]]:
    names: set[str] = set()
    for raw in entries["lineup_slots_json"]:
        import json

        slots = json.loads(str(raw))
        names.update(_string(row["player"], label="field player name") for row in slots)
    names.update(
        _string(value, label="ownership player name")
        for value in ownership["display_name"].tolist()
    )
    mapping: dict[str, str] = {}
    normalized_rows = []
    for raw in rows:
        row = _mapping(raw, label="player identity row")
        if set(row) != {"display_name", "player_id"}:
            _fail("player identity row fields differ")
        name = _string(row.get("display_name"), label="player display name")
        player_id = _string(row.get("player_id"), label=f"{name} player ID")
        if name in mapping:
            _fail("player identity mapping repeats a display name")
        mapping[name] = player_id
        normalized_rows.append({"display_name": name, "player_id": player_id})
    if set(mapping) != names:
        _fail("player identity mapping does not exactly cover the captured field")
    normalized_rows.sort(key=lambda row: (row["display_name"], row["player_id"]))
    payload: dict[str, object] = {
        "schema_version": PLAYER_IDENTITY_SCHEMA,
        "season": season,
        "week": week,
        "slate_id": slate_id,
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
        "rows_sha256": canonical_sha256(normalized_rows),
    }
    return mapping, payload


def _normalize_payout_table(
    rows: Sequence[Mapping[str, object]], *, contest_id: str, field_size: int
) -> tuple[list[dict[str, object]], dict[int, int], dict[str, object]]:
    normalized = []
    for raw in rows:
        row = _mapping(raw, label="payout-table row")
        if set(row) != {"rank_start", "rank_end", "payout_micro", "award_label"}:
            _fail("payout-table row fields differ")
        start = _integer(row.get("rank_start"), label="payout rank start", minimum=1)
        end = _integer(row.get("rank_end"), label="payout rank end", minimum=start)
        payout = _integer(row.get("payout_micro"), label="payout amount")
        label = _string(row.get("award_label"), label="payout award label")
        if end > field_size:
            _fail("payout-table rank exceeds the contest field")
        normalized.append({
            "rank_start": start,
            "rank_end": end,
            "payout_micro": payout,
            "award_label": label,
        })
    normalized.sort(key=lambda row: (int(row["rank_start"]), int(row["rank_end"])))
    if not normalized or normalized[0]["rank_start"] != 1:
        _fail("payout table must begin at rank 1")
    previous_end = 0
    previous_payout: int | None = None
    payout_by_rank: dict[int, int] = {}
    for row in normalized:
        start, end, payout = (
            int(row["rank_start"]), int(row["rank_end"]), int(row["payout_micro"])
        )
        if start != previous_end + 1:
            _fail("payout table contains a gap or overlap")
        if previous_payout is not None and payout > previous_payout:
            _fail("payout table is not nonincreasing by rank")
        for rank in range(start, end + 1):
            payout_by_rank[rank] = payout
        previous_end = end
        previous_payout = payout
    payload: dict[str, object] = {
        "schema_version": PAYOUT_TABLE_SCHEMA,
        "contest_id": contest_id,
        "field_size": field_size,
        "paid_through_rank": previous_end,
        "row_count": len(normalized),
        "rows": normalized,
        "rows_sha256": canonical_sha256(normalized),
    }
    return normalized, payout_by_rank, payload


def _normalize_participant_strength(
    rows: Sequence[Mapping[str, object]],
    entries: pd.DataFrame,
    *,
    contest_id: str,
    lock_at: str,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    expected_entry_ids = set(entries["entry_id"].astype(str))
    normalized = []
    by_entry: dict[str, dict[str, object]] = {}
    participant_values: dict[str, tuple[int, str]] = {}
    lock = datetime.fromisoformat(lock_at)
    for raw in rows:
        row = _mapping(raw, label="participant-strength row")
        if set(row) != {
            "entry_id", "participant_id", "strength_percentile_ppm", "as_of_at"
        }:
            _fail("participant-strength row fields differ")
        entry_id = _string(row.get("entry_id"), label="participant entry ID")
        participant_id = _string(
            row.get("participant_id"), label=f"{entry_id} participant ID"
        )
        strength = _integer(
            row.get("strength_percentile_ppm"),
            label=f"{entry_id} participant strength",
        )
        if strength > PROBABILITY_SCALE:
            _fail("participant strength percentile exceeds one")
        as_of = _timestamp(row.get("as_of_at"), label="participant-strength as-of")
        if datetime.fromisoformat(as_of) >= lock:
            _fail("participant strength is not point-in-time before slate lock")
        if entry_id in by_entry:
            _fail("participant-strength rows repeat an entry")
        key = (strength, as_of)
        if participant_id in participant_values and participant_values[participant_id] != key:
            _fail("one participant has inconsistent strength rows")
        participant_values[participant_id] = key
        normalized_row = {
            "entry_id": entry_id,
            "participant_id": participant_id,
            "strength_percentile_ppm": strength,
            "as_of_at": as_of,
        }
        by_entry[entry_id] = normalized_row
        normalized.append(normalized_row)
    if set(by_entry) != expected_entry_ids:
        _fail("participant-strength rows do not exactly cover contest entries")
    normalized.sort(key=lambda row: str(row["entry_id"]))
    payload: dict[str, object] = {
        "schema_version": PARTICIPANT_STRENGTH_SCHEMA,
        "contest_id": contest_id,
        "entry_count": len(normalized),
        "participant_count": len(participant_values),
        "point_in_time_before_lock": True,
        "rows": normalized,
        "rows_sha256": canonical_sha256(normalized),
    }
    return by_entry, payload


def _field_components(
    *,
    projection: Mapping[str, object],
    contest_id: str,
    contest_name: str,
    field_size: int,
    entry_fee_micro: int,
    entries: pd.DataFrame,
    ownership: pd.DataFrame,
    payout_table_rows: Sequence[Mapping[str, object]],
    participant_strength_rows: Sequence[Mapping[str, object]],
    player_identity_rows: Sequence[Mapping[str, object]],
    score_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, dict[str, object]], list[str]]:
    player_by_name, player_payload = _normalize_player_identity(
        player_identity_rows,
        entries,
        ownership,
        season=int(projection["season"]),
        week=int(projection["week"]),
        slate_id=str(projection["slate_id"]),
    )
    _, payout_by_rank, payout_payload = _normalize_payout_table(
        payout_table_rows, contest_id=contest_id, field_size=field_size
    )
    participant_by_entry, participant_payload = _normalize_participant_strength(
        participant_strength_rows,
        entries,
        contest_id=contest_id,
        lock_at=str(projection["lock_at"]),
    )

    import json

    field_rows: list[dict[str, object]] = []
    for ordinal, (_, raw) in enumerate(entries.iterrows()):
        entry_id = _string(raw.get("entry_id"), label=f"entry[{ordinal}] ID")
        slots = json.loads(str(raw.get("lineup_slots_json")))
        player_ids = sorted(player_by_name[
            _string(slot["player"], label=f"{entry_id} player")
        ] for slot in slots)
        lineup_id = _lineup_id(player_ids)
        field_rows.append({
            "entry_id": entry_id,
            "participant_id": participant_by_entry[entry_id]["participant_id"],
            "lineup_id": lineup_id,
            "player_ids": player_ids,
            "rank": int(raw.get("rank")),
            "realized_score_micro": _score_micro(
                raw.get("points"), label=f"{entry_id} points"
            ),
            "actual_split_payout_micro": _money_micro(
                raw.get("payout"), label=f"{entry_id} actual payout"
            ),
        })
    if len(field_rows) != field_size:
        _fail("normalized field roster count differs")
    entry_ids = [str(row["entry_id"]) for row in field_rows]
    if len(set(entry_ids)) != field_size:
        _fail("normalized field repeats an entry ID")
    score_counts = Counter(int(row["realized_score_micro"]) for row in field_rows)
    expected_rank_by_score: dict[int, int] = {}
    n_better = 0
    for score in sorted(score_counts, reverse=True):
        expected_rank_by_score[score] = n_better + 1
        n_better += score_counts[score]
    by_score: defaultdict[int, list[dict[str, object]]] = defaultdict(list)
    for row in field_rows:
        by_score[int(row["realized_score_micro"])].append(row)
    payout_deficiencies: list[str] = []
    for score, tied in by_score.items():
        rank = expected_rank_by_score[score]
        if any(int(row["rank"]) != rank for row in tied):
            _fail("captured ranks do not reproduce competition rank")
        tie_size = len(tied)
        prize_total = sum(
            payout_by_rank.get(position, 0)
            for position in range(rank, rank + tie_size)
        )
        # DraftKings displays cents; permit only the unavoidable cent-rounding
        # residue when a tie split is not integral in micro-dollars.
        expected_each = Decimal(prize_total) / Decimal(tie_size)
        actuals = {int(row["actual_split_payout_micro"]) for row in tied}
        if len(actuals) != 1 or abs(Decimal(next(iter(actuals))) - expected_each) > 10_000:
            payout_deficiencies.append(
                f"split_payout_not_reconciled_at_rank_{rank}"
            )
    duplicate_counts = Counter(str(row["lineup_id"]) for row in field_rows)
    for row in field_rows:
        row["duplicate_count"] = duplicate_counts[str(row["lineup_id"])]
    field_rows.sort(key=lambda row: str(row["entry_id"]))
    rosters_payload: dict[str, object] = {
        "schema_version": FIELD_ROSTERS_SCHEMA,
        "season": projection["season"],
        "week": projection["week"],
        "slate_id": projection["slate_id"],
        "contest_id": contest_id,
        "contest_name": contest_name,
        "field_size": field_size,
        "entry_fee_micro": entry_fee_micro,
        "entry_count": len(field_rows),
        "entries": field_rows,
        "entries_sha256": canonical_sha256(field_rows),
        "complete": True,
    }

    appearances: Counter[str] = Counter()
    for row in field_rows:
        appearances.update(str(value) for value in row["player_ids"])
    ownership_rows = []
    for player_id, count in sorted(appearances.items()):
        ppm = int((Decimal(count) * PROBABILITY_SCALE / Decimal(field_size)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        ))
        ownership_rows.append({
            "player_id": player_id,
            "appearance_count": count,
            "field_size": field_size,
            "ownership_ppm": ppm,
        })
    ownership_payload: dict[str, object] = {
        "schema_version": FIELD_OWNERSHIP_SCHEMA,
        "contest_id": contest_id,
        "field_size": field_size,
        "roster_slots_per_entry": 9,
        "appearance_count": sum(appearances.values()),
        "rows": ownership_rows,
        "rows_sha256": canonical_sha256(ownership_rows),
        "derived_from_complete_field": True,
    }

    field_by_lineup: defaultdict[str, list[dict[str, object]]] = defaultdict(list)
    for row in field_rows:
        field_by_lineup[str(row["lineup_id"])].append(row)
    score_by_lineup = {
        str(row["lineup_id"]): int(row["realized_score_micro"])
        for row in score_rows
    }
    membership_by_lineup = {
        str(row["lineup_id"]): list(row["membership_ids"])
        for row in projection["lineup_memberships"]  # type: ignore[index]
    }
    mapping_rows: list[dict[str, object]] = []
    for lineup_id in sorted(membership_by_lineup):
        score = score_by_lineup[lineup_id]
        matches = sorted(
            field_by_lineup.get(lineup_id, []), key=lambda row: str(row["entry_id"])
        )
        entered = bool(matches)
        if entered:
            if any(int(row["realized_score_micro"]) != score for row in matches):
                _fail("entered shadow lineup score differs from captured field")
            ranks = {int(row["rank"]) for row in matches}
            payouts = {int(row["actual_split_payout_micro"]) for row in matches}
            if len(ranks) != 1 or len(payouts) != 1:
                _fail("matching entries disagree on rank or split payout")
            counterfactual_rank = next(iter(ranks))
            payout = next(iter(payouts))
            actual_rank: int | None = counterfactual_rank
        else:
            counterfactual_rank = 1 + sum(
                int(row["realized_score_micro"]) > score for row in field_rows
            )
            payout = 0
            actual_rank = None
        # A lineup below every real entry has counterfactual insertion rank
        # N+1. Keep the actual-field percentile scale (rank 1 -> one, rank N
        # -> zero) and clamp that insertion-only endpoint to zero.
        counterfactual_percentile = max(
            0,
            (field_size - counterfactual_rank) * PROBABILITY_SCALE
            // (field_size - 1),
        )
        actual_percentile = counterfactual_percentile if entered else None
        mapping_rows.append({
            "lineup_id": lineup_id,
            "membership_ids": membership_by_lineup[lineup_id],
            "realized_score_micro": score,
            "entered_in_contest": entered,
            "matching_entry_ids": [str(row["entry_id"]) for row in matches],
            "actual_field_rank": actual_rank,
            "actual_field_percentile_ppm": actual_percentile,
            "counterfactual_field_rank": counterfactual_rank,
            "counterfactual_field_percentile_ppm": counterfactual_percentile,
            "duplicates": len(matches),
            "actual_split_payout_micro": payout,
            "actual_split_payout_applicable": entered,
            "aggregate_matching_entry_payout_micro": sum(
                int(row["actual_split_payout_micro"]) for row in matches
            ),
        })
    mapping_payload: dict[str, object] = {
        "schema_version": ENTRY_MAPPING_SCHEMA,
        "contest_id": contest_id,
        "field_size": field_size,
        "terminal_prelock_root_identity": projection[
            "terminal_prelock_root_identity"
        ],
        "terminal_prelock_root_sha256": projection[
            "terminal_prelock_root_sha256"
        ],
        "membership_projection_sha256": projection[
            "membership_projection_sha256"
        ],
        "mapped_lineup_count": len(mapping_rows),
        "entered_lineup_count": sum(
            bool(row["entered_in_contest"]) for row in mapping_rows
        ),
        "not_entered_lineup_count": sum(
            not bool(row["entered_in_contest"]) for row in mapping_rows
        ),
        "rows": mapping_rows,
        "rows_sha256": canonical_sha256(mapping_rows),
        "complete_mapping": True,
    }
    components = {
        "payout_table": payout_payload,
        "field_rosters": rosters_payload,
        "field_ownership": ownership_payload,
        "participant_strength": participant_payload,
        "player_identity": player_payload,
        "shadow_entry_mapping": mapping_payload,
    }
    return components, sorted(set(payout_deficiencies))


def prepare_contest_field_bridge_v1(
    *,
    terminal_prelock_root: Mapping[str, object],
    captured_at: datetime | str,
    realized_score_micro_by_lineup_id: Mapping[str, int],
    realized_score_source_identity: Mapping[str, object],
    capture_manifest: Mapping[str, object] | None = None,
    validated_capture: Mapping[str, object] | None = None,
    capture_source_identity: Mapping[str, object] | None = None,
    entry_fee_micro: int | None = None,
    payout_table_rows: Sequence[Mapping[str, object]] | None = None,
    participant_strength_rows: Sequence[Mapping[str, object]] | None = None,
    player_identity_rows: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Prepare canonical post-settlement field components or fail to raw-only.

    Missing evidence is a scientific deficiency, not an excuse to synthesize
    contest utility.  Structurally inconsistent supplied evidence raises.
    """

    projection = _project_terminal_prelock_root(terminal_prelock_root)
    captured = _timestamp(captured_at, label="field bridge captured-at")
    if datetime.fromisoformat(captured) <= datetime.fromisoformat(
        str(projection["lock_at"])
    ):
        _fail("contest-field bridge was not produced after slate lock")
    scores = _normalize_realized_scores(
        realized_score_micro_by_lineup_id, projection
    )
    score_source_payload = _realized_score_source_payload(
        projection=projection, captured_at=captured, score_rows=scores
    )
    score_source_identity = _identity_for_payload(
        realized_score_source_identity,
        score_source_payload,
        label="independent realized-score source identity",
    )
    if content_identity(score_source_identity) == content_identity(
        projection["terminal_prelock_root_identity"]  # type: ignore[arg-type]
    ):
        _fail("realized-score source is not independent of the prelock root")
    missing = _missing_inputs(
        full_field_capture=(
            capture_manifest if capture_manifest is not None and validated_capture is not None
            else None
        ),
        capture_source_identity=capture_source_identity,
        entry_fee=entry_fee_micro,
        payout_table=payout_table_rows,
        participant_strength=participant_strength_rows,
        player_identity=player_identity_rows,
    )
    if missing:
        return _raw_score_bridge(
            projection=projection,
            captured_at=captured,
            score_rows=scores,
            realized_score_source_identity=score_source_identity,
            deficiencies=missing,
        )
    assert capture_manifest is not None
    assert validated_capture is not None
    assert capture_source_identity is not None
    assert entry_fee_micro is not None
    assert payout_table_rows is not None
    assert participant_strength_rows is not None
    assert player_identity_rows is not None
    capture_status = _mapping(
        capture_manifest, label="DK field capture manifest"
    )
    capture_validation = _mapping(
        capture_status.get("validation"), label="capture validation receipt"
    )
    if (
        capture_status.get("status") != "applied"
        or capture_status.get("evidence_timing") != "post_settlement"
        or capture_validation.get("operator_confirmed_settled") is not True
        or capture_validation.get("operator_confirmed_full_field") is not True
        or capture_validation.get("operator_confirmed_contest_metadata") is not True
    ):
        return _raw_score_bridge(
            projection=projection,
            captured_at=captured,
            score_rows=scores,
            realized_score_source_identity=score_source_identity,
            deficiencies=["full_field_capture_not_applied_or_confirmed"],
        )
    capture_frames = _mapping(validated_capture, label="validated capture")
    capture_entries = capture_frames.get("entries")
    if (
        not isinstance(capture_entries, pd.DataFrame)
        or "payout" not in capture_entries
        or capture_entries["payout"].isna().any()
    ):
        return _raw_score_bridge(
            projection=projection,
            captured_at=captured,
            score_rows=scores,
            realized_score_source_identity=score_source_identity,
            deficiencies=["actual_split_payout_missing"],
        )
    entry_fee = _integer(entry_fee_micro, label="contest entry fee", minimum=1)
    (
        contest_id,
        field_size,
        contest_name,
        entries,
        ownership,
        source_identity,
    ) = _capture_contract(
        projection=projection,
        capture_manifest=capture_manifest,
        validated_capture=validated_capture,
        capture_source_identity=capture_source_identity,
    )
    components, deficiencies = _field_components(
        projection=projection,
        contest_id=contest_id,
        contest_name=contest_name,
        field_size=field_size,
        entry_fee_micro=entry_fee,
        entries=entries,
        ownership=ownership,
        payout_table_rows=payout_table_rows,
        participant_strength_rows=participant_strength_rows,
        player_identity_rows=player_identity_rows,
        score_rows=scores,
    )
    if deficiencies:
        return _raw_score_bridge(
            projection=projection,
            captured_at=captured,
            score_rows=scores,
            realized_score_source_identity=score_source_identity,
            deficiencies=deficiencies,
        )
    body: dict[str, object] = {
        "schema_version": PREPARATION_SCHEMA,
        "season": projection["season"],
        "week": projection["week"],
        "slate_id": projection["slate_id"],
        "captured_at": captured,
        "terminal_prelock_root_identity": projection[
            "terminal_prelock_root_identity"
        ],
        "terminal_prelock_root_sha256": projection[
            "terminal_prelock_root_sha256"
        ],
        "membership_projection": projection,
        "membership_projection_sha256": projection[
            "membership_projection_sha256"
        ],
        "contest_id": contest_id,
        "contest_name": contest_name,
        "field_size": field_size,
        "entry_fee_micro": entry_fee,
        "capture_source_identity": source_identity,
        "realized_score_source_identity": score_source_identity,
        "realized_score_source_payload_sha256": canonical_sha256(
            score_source_payload
        ),
        "component_payloads": components,
        "component_payload_sha256_by_name": {
            name: canonical_sha256(components[name]) for name in _COMPONENT_NAMES
        },
        "status": "ready-for-create-once-component-binding",
        "evidence_scope": "raw-score-only-until-components-are-bound",
        "complete_contest_field_capture": False,
        "complete_field_rank_claim_allowed": False,
        "contest_ev_claim_allowed": False,
        "allocation_recommendation_allowed": False,
        "uses_realized_outcomes": True,
    }
    return _self_hashed(body, field="field_preparation_sha256")


def bind_contest_field_bridge_v1(
    *,
    preparation: Mapping[str, object],
    component_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Bind all prepared components to create-once content identities."""

    prepared = _mapping(preparation, label="field preparation")
    _validate_self_hash(
        prepared, field="field_preparation_sha256", label="field preparation"
    )
    if (
        prepared.get("schema_version") != PREPARATION_SCHEMA
        or prepared.get("status") != "ready-for-create-once-component-binding"
        or prepared.get("complete_contest_field_capture") is not False
        or prepared.get("complete_field_rank_claim_allowed") is not False
        or prepared.get("contest_ev_claim_allowed") is not False
    ):
        _fail("field preparation is not ready for binding")
    payloads = _mapping(prepared.get("component_payloads"), label="field components")
    if set(payloads) != set(_COMPONENT_NAMES) or set(component_identities) != set(
        _COMPONENT_NAMES
    ):
        _fail("field component identity registry differs")
    identities = {
        name: _identity_for_payload(
            component_identities[name],
            _mapping(payloads[name], label=f"{name} payload"),
            label=f"{name} identity",
        )
        for name in _COMPONENT_NAMES
    }
    identity_keys = {content_identity(value) for value in identities.values()}
    if len(identity_keys) != len(_COMPONENT_NAMES):
        _fail("field component authority identity is reused")
    capture_identity = _identity(
        prepared.get("capture_source_identity"), label="capture source identity"
    )
    score_source_identity = _identity(
        prepared.get("realized_score_source_identity"),
        label="independent realized-score source identity",
    )
    if (
        content_identity(score_source_identity) in identity_keys
        or content_identity(score_source_identity)
        == content_identity(capture_identity)
    ):
        _fail("independent realized-score source identity is reused")
    if content_identity(capture_identity) in identity_keys:
        _fail("full-field source identity is reused as a derived component")
    mapping_payload = _mapping(
        payloads["shadow_entry_mapping"], label="shadow-entry mapping payload"
    )
    mapping_rows = _sequence(
        mapping_payload.get("rows"), label="shadow-entry mapping rows"
    )
    evaluator_rows = []
    for raw in mapping_rows:
        row = _mapping(raw, label="shadow-entry mapping row")
        evaluator_rows.append({
            "lineup_id": row["lineup_id"],
            "realized_score_micro": row["realized_score_micro"],
            "actual_field_rank": row["actual_field_rank"],
            "actual_field_percentile_ppm": row[
                "actual_field_percentile_ppm"
            ],
            "counterfactual_field_rank": row[
                "counterfactual_field_rank"
            ],
            "counterfactual_field_percentile_ppm": row[
                "counterfactual_field_percentile_ppm"
            ],
            "duplicates": row["duplicates"],
            "split_payout_micro": row["actual_split_payout_micro"],
            "entered_in_contest": row["entered_in_contest"],
            "matching_entry_ids": row["matching_entry_ids"],
            "actual_split_payout_applicable": row[
                "actual_split_payout_applicable"
            ],
        })
    entered = int(mapping_payload["entered_lineup_count"])
    not_entered = int(mapping_payload["not_entered_lineup_count"])
    contest_ev_allowed = not_entered == 0 and entered == len(evaluator_rows)
    evidence_scope = (
        "raw-score-complete-field-ranks-and-entered-contest-ev"
        if contest_ev_allowed
        else "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
    )
    evaluator_capture = {
        "contest_id": prepared["contest_id"],
        "field_size": prepared["field_size"],
        "entry_fee_micro": prepared["entry_fee_micro"],
        "payout_table_identity": identities["payout_table"],
        "field_rosters_identity": identities["field_rosters"],
        "field_ownership_identity": identities["field_ownership"],
        "participant_strength_identity": identities["participant_strength"],
        "shadow_entry_mapping_identity": identities["shadow_entry_mapping"],
        "complete": True,
        "status": "complete-contest-field-capture",
        "evidence_scope": evidence_scope,
        "complete_field_rank_claim_allowed": True,
        "contest_ev_claim_allowed": contest_ev_allowed,
        "allocation_recommendation_allowed": False,
    }
    body: dict[str, object] = {
        "schema_version": BRIDGE_SCHEMA,
        "season": prepared["season"],
        "week": prepared["week"],
        "slate_id": prepared["slate_id"],
        "captured_at": prepared["captured_at"],
        "terminal_prelock_root_identity": prepared[
            "terminal_prelock_root_identity"
        ],
        "terminal_prelock_root_sha256": prepared[
            "terminal_prelock_root_sha256"
        ],
        "membership_projection_sha256": prepared[
            "membership_projection_sha256"
        ],
        "status": "complete-contest-field-capture",
        "evidence_scope": evidence_scope,
        "complete_contest_field_capture": True,
        "complete_field_rank_claim_allowed": True,
        "contest_ev_claim_allowed": contest_ev_allowed,
        "allocation_recommendation_allowed": False,
        "deficiencies": [],
        "capture_source_identity": capture_identity,
        "realized_score_source_identity": score_source_identity,
        "component_identities": identities,
        "component_payload_sha256_by_name": prepared[
            "component_payload_sha256_by_name"
        ],
        "evaluator_contest_field_capture": evaluator_capture,
        "evaluator_lineup_rows": evaluator_rows,
        "evaluator_lineup_rows_sha256": canonical_sha256(evaluator_rows),
        "entered_shadow_lineup_count": entered,
        "not_entered_shadow_lineup_count": not_entered,
        "every_frozen_lineup_mapped_entered_or_not_entered": True,
        "actual_payout_never_imputed_for_unentered_lineup": True,
        "uses_realized_outcomes": True,
    }
    return _self_hashed(body, field="field_bridge_sha256")


def validate_contest_field_bridge_v1(value: object) -> dict[str, object]:
    """Validate the complete or explicit raw-score-only bridge receipt."""

    bridge = _mapping(value, label="contest-field bridge")
    _validate_self_hash(bridge, field="field_bridge_sha256", label="field bridge")
    if bridge.get("schema_version") != BRIDGE_SCHEMA:
        _fail("field bridge schema differs")
    _timestamp(bridge.get("captured_at"), label="field bridge captured-at")
    _identity(
        bridge.get("terminal_prelock_root_identity"),
        label="terminal prelock root identity",
    )
    score_source_identity = _identity(
        bridge.get("realized_score_source_identity"),
        label="independent realized-score source identity",
    )
    if score_source_identity == _identity(
        bridge.get("terminal_prelock_root_identity"),
        label="terminal prelock root identity",
    ):
        _fail("realized-score source is not independent of the prelock root")
    scores = _sequence(
        bridge.get("evaluator_lineup_rows"), label="evaluator lineup rows"
    )
    if not scores:
        _fail("field bridge contains no lineup rows")
    lineup_ids = []
    for raw in scores:
        row = _mapping(raw, label="evaluator lineup row")
        lineup_id = _string(row.get("lineup_id"), label="lineup ID")
        if _LINEUP_ID.fullmatch(lineup_id) is None:
            _fail("field bridge contains a noncanonical lineup ID")
        lineup_ids.append(lineup_id)
        if type(row.get("realized_score_micro")) is not int:
            _fail("field bridge realized score is not integer micro-points")
    if lineup_ids != sorted(lineup_ids) or len(set(lineup_ids)) != len(lineup_ids):
        _fail("field bridge lineup rows are reordered or duplicated")
    score_rows = [{
        "lineup_id": row["lineup_id"],
        "realized_score_micro": row["realized_score_micro"],
    } for row in scores]
    score_source_payload = _realized_score_source_payload(
        projection={
            "season": bridge.get("season"),
            "week": bridge.get("week"),
            "slate_id": bridge.get("slate_id"),
        },
        captured_at=str(bridge["captured_at"]),
        score_rows=score_rows,
    )
    _identity_for_payload(
        score_source_identity,
        score_source_payload,
        label="independent realized-score source identity",
    )
    complete = bridge.get("complete_contest_field_capture")
    if complete is False:
        expected_raw_fields = {
            "schema_version", "season", "week", "slate_id", "captured_at",
            "terminal_prelock_root_identity", "terminal_prelock_root_sha256",
            "membership_projection_sha256", "realized_score_source_identity",
            "status", "evidence_scope", "complete_contest_field_capture",
            "complete_field_rank_claim_allowed",
            "contest_ev_claim_allowed", "allocation_recommendation_allowed",
            "deficiencies", "component_identities",
            "evaluator_contest_field_capture", "evaluator_lineup_rows",
            "entered_shadow_lineup_count", "not_entered_shadow_lineup_count",
            "uses_realized_outcomes", "field_bridge_sha256",
        }
        if (
            set(bridge) != expected_raw_fields
            or bridge.get("status") != "raw-score-only-no-contest-ev"
            or bridge.get("evidence_scope") != "raw-score-only-no-contest-ev"
            or bridge.get("complete_field_rank_claim_allowed") is not False
            or bridge.get("contest_ev_claim_allowed") is not False
            or bridge.get("allocation_recommendation_allowed") is not False
            or bridge.get("evaluator_contest_field_capture") is not None
            or bridge.get("component_identities") is not None
            or not bridge.get("deficiencies")
            or bridge.get("uses_realized_outcomes") is not True
            or any(set(_mapping(row, label="raw score row")) != {
                "lineup_id", "realized_score_micro"
            } for row in scores)
        ):
            _fail("raw-score-only bridge overclaims contest evidence")
        return bridge
    if complete is not True:
        _fail("field bridge completeness is not explicit")
    expected_complete_fields = {
        "schema_version", "season", "week", "slate_id", "captured_at",
        "terminal_prelock_root_identity", "terminal_prelock_root_sha256",
        "membership_projection_sha256", "status", "evidence_scope",
        "complete_contest_field_capture", "complete_field_rank_claim_allowed",
        "contest_ev_claim_allowed",
        "allocation_recommendation_allowed", "deficiencies",
        "capture_source_identity", "realized_score_source_identity",
        "component_identities", "component_payload_sha256_by_name",
        "evaluator_contest_field_capture", "evaluator_lineup_rows",
        "evaluator_lineup_rows_sha256", "entered_shadow_lineup_count",
        "not_entered_shadow_lineup_count",
        "every_frozen_lineup_mapped_entered_or_not_entered",
        "actual_payout_never_imputed_for_unentered_lineup",
        "uses_realized_outcomes", "field_bridge_sha256",
    }
    if set(bridge) != expected_complete_fields:
        _fail("complete field bridge fields differ")
    expected_row_fields = {
        "lineup_id", "realized_score_micro", "actual_field_rank",
        "actual_field_percentile_ppm", "counterfactual_field_rank",
        "counterfactual_field_percentile_ppm", "duplicates",
        "split_payout_micro",
        "entered_in_contest", "matching_entry_ids",
        "actual_split_payout_applicable",
    }
    evaluator_capture = _mapping(
        bridge.get("evaluator_contest_field_capture"),
        label="evaluator field capture",
    )
    field_size = _integer(
        evaluator_capture.get("field_size"),
        label="field size",
        minimum=2,
    )
    entered_count = 0
    for raw in scores:
        row = _mapping(raw, label="complete evaluator lineup row")
        if set(row) != expected_row_fields:
            _fail("complete evaluator lineup row fields differ")
        entered = row.get("entered_in_contest")
        applicable = row.get("actual_split_payout_applicable")
        matches = _sequence(row.get("matching_entry_ids"), label="matching entries")
        duplicates = _integer(row.get("duplicates"), label="duplicates")
        counterfactual_rank = _integer(
            row.get("counterfactual_field_rank"),
            label="counterfactual field rank",
            minimum=1,
        )
        counterfactual_percentile = _integer(
            row.get("counterfactual_field_percentile_ppm"),
            label="counterfactual field percentile",
        )
        if counterfactual_rank > field_size + 1 or counterfactual_percentile != max(
            0,
            (field_size - counterfactual_rank) * PROBABILITY_SCALE
            // (field_size - 1),
        ):
            _fail("counterfactual field rank/percentile differs")
        if type(entered) is not bool or type(applicable) is not bool:
            _fail("entered/payout applicability must be boolean")
        if entered:
            entered_count += 1
            actual_rank = _integer(
                row.get("actual_field_rank"), label="actual field rank", minimum=1
            )
            actual_percentile = _integer(
                row.get("actual_field_percentile_ppm"),
                label="actual field percentile",
            )
            if (
                not applicable
                or duplicates < 1
                or len(matches) != duplicates
                or actual_rank != counterfactual_rank
                or actual_percentile != counterfactual_percentile
            ):
                _fail("entered lineup mapping is incomplete")
        elif (
            applicable
            or duplicates != 0
            or matches
            or row.get("split_payout_micro") != 0
            or row.get("actual_field_rank") is not None
            or row.get("actual_field_percentile_ppm") is not None
        ):
            _fail("unentered lineup was assigned contest facts")
    if (
        bridge.get("status") != "complete-contest-field-capture"
        or bridge.get("evidence_scope") != (
            "raw-score-complete-field-ranks-and-entered-contest-ev"
            if entered_count == len(scores)
            else "raw-score-and-complete-field-ranks-no-counterfactual-contest-ev"
        )
        or bridge.get("complete_field_rank_claim_allowed") is not True
        or bridge.get("contest_ev_claim_allowed") is not (
            entered_count == len(scores)
        )
        or bridge.get("allocation_recommendation_allowed") is not False
        or bridge.get("deficiencies") != []
        or bridge.get("entered_shadow_lineup_count") != entered_count
        or bridge.get("not_entered_shadow_lineup_count")
        != len(scores) - entered_count
        or bridge.get("every_frozen_lineup_mapped_entered_or_not_entered") is not True
        or bridge.get("actual_payout_never_imputed_for_unentered_lineup") is not True
        or bridge.get("uses_realized_outcomes") is not True
        or bridge.get("evaluator_lineup_rows_sha256") != canonical_sha256(scores)
    ):
        _fail("complete field bridge fixed law differs")
    component_identities = _mapping(
        bridge.get("component_identities"), label="component identities"
    )
    if set(component_identities) != set(_COMPONENT_NAMES):
        _fail("complete field bridge component registry differs")
    keys = {
        content_identity(_identity(value, label=f"{name} identity"))
        for name, value in component_identities.items()
    }
    if len(keys) != len(_COMPONENT_NAMES):
        _fail("complete field bridge reuses a component identity")
    capture_source_identity = _identity(
        bridge.get("capture_source_identity"), label="capture source identity"
    )
    if (
        content_identity(capture_source_identity) in keys
        or content_identity(score_source_identity) in keys
        or content_identity(capture_source_identity)
        == content_identity(score_source_identity)
    ):
        _fail("complete field bridge reuses an outcome authority identity")
    identity_fields = {
        "payout_table_identity": "payout_table",
        "field_rosters_identity": "field_rosters",
        "field_ownership_identity": "field_ownership",
        "participant_strength_identity": "participant_strength",
        "shadow_entry_mapping_identity": "shadow_entry_mapping",
    }
    expected_capture_fields = {
        "contest_id", "field_size", "entry_fee_micro", *identity_fields,
        "complete", "status", "evidence_scope", "contest_ev_claim_allowed",
        "complete_field_rank_claim_allowed",
        "allocation_recommendation_allowed",
    }
    if (
        set(evaluator_capture) != expected_capture_fields
        or evaluator_capture.get("complete") is not True
        or evaluator_capture.get("status") != "complete-contest-field-capture"
        or evaluator_capture.get("evidence_scope")
        != bridge.get("evidence_scope")
        or evaluator_capture.get("complete_field_rank_claim_allowed") is not True
        or evaluator_capture.get("contest_ev_claim_allowed") is not (
            entered_count == len(scores)
        )
        or evaluator_capture.get("allocation_recommendation_allowed") is not False
    ):
        _fail("evaluator contest-field capture differs")
    for field, component in identity_fields.items():
        if _identity(
            evaluator_capture.get(field), label=f"evaluator {field}"
        ) != _identity(
            component_identities[component], label=f"component {component}"
        ):
            _fail("evaluator contest-field identity projection differs")
    component_hashes = _mapping(
        bridge.get("component_payload_sha256_by_name"),
        label="component payload hashes",
    )
    if set(component_hashes) != set(_COMPONENT_NAMES) or any(
        type(value) is not str or _HEX64.fullmatch(value) is None
        for value in component_hashes.values()
    ) or any(
        component_hashes[name]
        != _identity(component_identities[name], label=f"{name} identity")[
            "sha256"
        ]
        for name in _COMPONENT_NAMES
    ):
        _fail("component payload hash registry differs")
    return bridge


__all__ = [
    "BRIDGE_SCHEMA",
    "PREPARATION_SCHEMA",
    "ProspectiveContestFieldBridgeError",
    "build_independent_realized_score_source_payload_v1",
    "bind_contest_field_bridge_v1",
    "prepare_contest_field_bridge_v1",
    "validate_contest_field_bridge_v1",
]
