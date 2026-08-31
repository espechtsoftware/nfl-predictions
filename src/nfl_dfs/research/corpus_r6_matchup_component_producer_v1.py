"""Deterministic, offline component producer for the historical R6-v2 source.

The producer consumes exact bodies and content identities supplied by an
outer capture layer.  It never constructs a warehouse or cloud client,
lists a bucket, reads Git, imports a result/scoring module, or reads a
realized lineup/contest outcome.  The original offline path injects an
identity lookup that receives only ``(uri, sha256, bytes)``.  A separate,
explicit capture path may instead inject a create-once materializer that
receives ``(uri, canonical_bytes)``; every returned identity is immediately
exact-reopened before it can become a parent-object dependency.  The module
still owns no storage client and grants no publication or downstream
authority.

The central contamination check is an actual reducer replay.  For every
slate, the same reducer runs once over the complete seven-pack input and once
after physically deleting every target-or-later weekly-stat, SIS, and PFR
row.  Catalog population, roles, components, percentiles, support, and final
annotation rows must be byte-identical before a source-v2 deletion proof or
producer receipt can be built.

All returned objects are evidence candidates only.  They carry no source,
publication, scoring, fill, retrieval, promotion, production, graph, or
decision authority.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timezone
from hashlib import sha256
import math
import re
from typing import Final
from zoneinfo import ZoneInfo

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


PRODUCER_INPUT_BUNDLE_SCHEMA: Final = source.PRODUCER_INPUT_BUNDLE_SCHEMA
OFFLINE_PANEL_RESULT_SCHEMA: Final = (
    "corpus-r6-matchup-offline-component-panel/v1"
)
ONE_TASK_RESULT_SCHEMA: Final = (
    "corpus-r6-matchup-component-one-task-result/v1"
)
FIXED_G0_REPLAY_SCHEMA: Final = (
    "corpus-r6-player-catalog-fixed-g0-replay/v1"
)
FIXED_G0_REPLAY_FALSE_FIELDS: Final = (
    *catalog_v1.FALSE_AUTHORITY_FIELDS,
    "analytical_authority",
    "automatic_retry_licensed",
)
FIXED_G0_REPLAY_FIELDS: Final = frozenset({
    "schema_version",
    "replay_id",
    "replay_scope",
    "pin_set_sha256",
    "tracked_root_binding",
    "official_publication_receipt_file",
    "official_publication_receipt_sha256",
    "adapter_review_binding",
    "lane_terminal_identities",
    "lane_completion_identities",
    "later_source_freeze_identity",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion_identity",
    "artifact_source_authority_completion_sha256",
    "derivation_code_identity",
    "catalog_namespace",
    "catalog_release_identity",
    "catalog_release_sha256",
    "task_count",
    "task_acceptance_body_count",
    "task_acceptance_body_manifest_sha256",
    "carrier_body_count",
    "carrier_body_manifest_sha256",
    "member_binding_manifest_sha256",
    "source_catalog_binding_manifest_sha256",
    "completion_binding_manifest_sha256",
    "structural_catalog_manifest_sha256",
    "catalog_identity_manifest_sha256",
    "accepted_panel_index_projection_only",
    "fresh_task_or_arm_body_revalidation_performed",
    "task_acceptance_bodies_reopened",
    "carrier_bodies_reopened",
    "source_completion_artifact_bodies_reopened",
    "world_matrix_bodies_reopened",
    "result_object_bodies_reopened",
    "execution_manifest_pin_required",
    "self_authorizing",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *FIXED_G0_REPLAY_FALSE_FIELDS,
    "replay_receipt_sha256",
})
PRODUCER_MODULE_PATH: Final = source.PRODUCER_MODULE_PATH

FAMILY_COMPONENTS: Final = source.family_components_v1()
POSITION_FAMILY: Final = source.position_family_v1()
MINIMUM_PRIOR_GAMES: Final = 4
SIS_SHRINK_TARGETS: Final = source.SIS_SHRINK_TARGETS

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_OUTCOME_KEYS: Final = frozenset({
    "actual_score",
    "actual_points",
    "contest_finish",
    "contest_place",
    "contest_rank",
    "contest_score",
    "entry_rank",
    "lineup_actual",
    "lineup_points",
    "lineup_score",
    "payout",
    "realized_outcome",
    "realized_points",
    "realized_score",
    "winner",
    "winning_score",
})
_ALLOWED_OUTCOME_POLICY_KEYS: Final = frozenset({
    "outcome_columns_read",
    "uses_realized_outcomes",
})


class CorpusR6MatchupComponentProducerV1Error(ValueError):
    """The injected source or deterministic producer replay is invalid."""


IdentityLookup = Callable[[str, str, int], Mapping[str, object]]
BodyMaterializer = Callable[[str, bytes], Mapping[str, object]]
ExactReader = Callable[[Mapping[str, object]], bytes]


def _fail(message: str) -> None:
    raise CorpusR6MatchupComponentProducerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _identifier(value: object, *, label: str) -> str:
    text = _text(value, label=label)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(f"{label} must be a canonical identifier")
    return text


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        _fail(f"{label} must be a finite number")
    return float(value)


def _number_or_none(value: object, *, label: str) -> float | None:
    if value is None:
        return None
    return _number(value, label=label)


def _bool_or_none(value: object, *, label: str) -> bool | None:
    if value is None:
        return None
    if type(value) is not bool:
        _fail(f"{label} must be true, false, or null")
    return value


def _key(value: Mapping[str, object], *, label: str) -> tuple[int, int]:
    season = _integer(value.get("season"), label=f"{label}.season", minimum=2000)
    week = _integer(value.get("week"), label=f"{label}.week", minimum=1)
    if week > 18:
        _fail(f"{label}.week must be <= 18")
    return season, week


def _parse_utc(value: object, *, label: str) -> datetime:
    text = _text(value, label=label)
    if _UTC.fullmatch(text) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusR6MatchupComponentProducerV1Error(
            f"{label} is not a valid timestamp"
        ) from exc


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _reject_outcome_fields(value: object, *, label: str) -> None:
    """Reject outcome-bearing carrier fields recursively.

    Historical player-game box-score columns registered in the positive pack
    schema are legitimate prior-period inputs.  This guard rejects only
    contest/lineup outcome carriers and non-false outcome policy claims; the
    exact pack schemas perform the stronger positive-boundary check.
    """
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if normalized in _FORBIDDEN_OUTCOME_KEYS:
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "outcome_columns_read" and item != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            if normalized == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            if (
                "realized" in normalized
                and normalized not in _ALLOWED_OUTCOME_POLICY_KEYS
            ):
                _fail(f"{label} contains forbidden realized field {key!r}")
            _reject_outcome_fields(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_outcome_fields(item, label=f"{label}[{ordinal}]")


def _identity_for_body(
    *,
    body: object,
    uri: str,
    identity_lookup: IdentityLookup | None,
    body_materializer: BodyMaterializer | None = None,
    read_exact: ExactReader | None = None,
    label: str,
) -> dict[str, object]:
    raw = source.canonical_json_bytes(body)
    digest = sha256(raw).hexdigest()
    if (identity_lookup is None) == (body_materializer is None):
        _fail(
            f"{label} requires exactly one identity lookup or body materializer"
        )
    if body_materializer is not None:
        if read_exact is None:
            _fail(f"{label} materialization requires an exact reader")
        try:
            supplied = body_materializer(uri, raw)
        except Exception as exc:
            raise CorpusR6MatchupComponentProducerV1Error(
                f"{label} create-once materialization failed"
            ) from exc
    else:
        assert identity_lookup is not None
        supplied = identity_lookup(uri, digest, len(raw))
    identity = source.normalize_object_identity_v2(supplied, label=label)
    if (
        identity["uri"] != uri
        or identity["sha256"] != digest
        or identity["bytes"] != len(raw)
    ):
        _fail(f"{label} differs from its exact body request")
    if body_materializer is not None:
        assert read_exact is not None
        try:
            reopened = read_exact(identity)
        except Exception as exc:
            raise CorpusR6MatchupComponentProducerV1Error(
                f"{label} exact reopen failed"
            ) from exc
        if type(reopened) is not bytes or reopened != raw:
            _fail(f"{label} exact-reopened bytes differ")
    return identity


def _bind_body(
    body: object, identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = source.normalize_object_identity_v2(identity, label=label)
    raw = source.canonical_json_bytes(body)
    if (
        normalized["sha256"] != sha256(raw).hexdigest()
        or normalized["bytes"] != len(raw)
    ):
        _fail(f"{label} differs from its exact body")
    return normalized


def _validate_fixed_g0_replay(
    *,
    replay_receipt: Mapping[str, object],
    replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    receipt = _mapping(replay_receipt, label="fixed-G0 replay receipt")
    _exact_keys(
        receipt,
        FIXED_G0_REPLAY_FIELDS,
        label="fixed-G0 replay receipt",
    )
    _reject_outcome_fields(receipt, label="fixed-G0 replay receipt")
    receipt_identity = _bind_body(
        receipt,
        replay_receipt_identity,
        label="fixed-G0 replay receipt identity",
    )
    release_identity = source.normalize_object_identity_v2(
        catalog_release_identity, label="fixed-G0 catalog release identity"
    )
    retained = receipt.get("replay_receipt_sha256")
    if type(retained) is not str or _SHA256.fullmatch(retained) is None:
        _fail("fixed-G0 replay receipt self-hash is invalid")
    replay_body = dict(receipt)
    del replay_body["replay_receipt_sha256"]
    try:
        release = catalog_v1.validate_release_v1(catalog_release)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupComponentProducerV1Error(str(exc)) from exc
    _bind_body(
        release,
        release_identity,
        label="fixed-G0 catalog release identity",
    )
    lane_terminal_identities = [
        source.normalize_object_identity_v2(
            value, label=f"fixed-G0 lane terminal[{ordinal}]"
        )
        for ordinal, value in enumerate(
            _sequence(
                receipt.get("lane_terminal_identities"),
                label="fixed-G0 lane terminal identities",
            )
        )
    ]
    lane_completion_identities = [
        source.normalize_object_identity_v2(
            value, label=f"fixed-G0 lane completion[{ordinal}]"
        )
        for ordinal, value in enumerate(
            _sequence(
                receipt.get("lane_completion_identities"),
                label="fixed-G0 lane completion identities",
            )
        )
    ]
    digest_fields = (
        "pin_set_sha256",
        "official_publication_receipt_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion_sha256",
        "task_acceptance_body_manifest_sha256",
        "carrier_body_manifest_sha256",
        "member_binding_manifest_sha256",
        "source_catalog_binding_manifest_sha256",
        "completion_binding_manifest_sha256",
        "structural_catalog_manifest_sha256",
        "catalog_identity_manifest_sha256",
    )
    if any(
        type(receipt.get(field)) is not str
        or _SHA256.fullmatch(str(receipt.get(field))) is None
        for field in digest_fields
    ):
        _fail("fixed-G0 replay receipt contains an invalid manifest digest")
    expected_catalog_identity_manifest = source.canonical_sha256([
        _mapping(entry, label="fixed-G0 catalog release entry")[
            "catalog_identity"
        ]
        for entry in _sequence(
            release.get("entries"), label="fixed-G0 catalog release entries"
        )
    ])
    if (
        source.canonical_sha256(replay_body) != retained
        or receipt.get("schema_version") != FIXED_G0_REPLAY_SCHEMA
        or receipt.get("replay_id")
        != "fixed-g0-r6-player-catalog-projection-v1"
        or receipt.get("replay_scope")
        != "accepted-panel-index-projection-rooted-in-frozen-g0-evidence"
        or receipt.get("catalog_namespace") != release.get("catalog_namespace")
        or receipt.get("catalog_release_identity") != release_identity
        or receipt.get("catalog_release_sha256") != release.get("release_sha256")
        or receipt.get("tracked_root_binding")
        != release.get("tracked_root_binding")
        or receipt.get("later_source_freeze_identity")
        != release.get("later_source_freeze_identity")
        or receipt.get("later_source_freeze_manifest_sha256")
        != release.get("later_source_freeze_manifest_sha256")
        or receipt.get("artifact_source_authority_completion_identity")
        != release.get("artifact_source_authority_completion_identity")
        or receipt.get("artifact_source_authority_completion_sha256")
        != release.get("artifact_source_authority_completion_sha256")
        or receipt.get("derivation_code_identity")
        != release.get("derivation_code_identity")
        or receipt.get("catalog_identity_manifest_sha256")
        != expected_catalog_identity_manifest
        or receipt.get("task_count") != source.TASK_COUNT
        or receipt.get("task_acceptance_body_count") != source.TASK_COUNT
        or receipt.get("carrier_body_count") != source.TASK_COUNT
        or receipt.get("accepted_panel_index_projection_only") is not True
        or receipt.get("fresh_task_or_arm_body_revalidation_performed") is not True
        or receipt.get("task_acceptance_bodies_reopened") is not True
        or receipt.get("carrier_bodies_reopened") is not True
        or receipt.get("source_completion_artifact_bodies_reopened") is not False
        or receipt.get("world_matrix_bodies_reopened") is not False
        or receipt.get("result_object_bodies_reopened") is not False
        or receipt.get("execution_manifest_pin_required") is not True
        or receipt.get("self_authorizing") is not False
        or receipt.get("outcome_columns_read") != []
        or receipt.get("uses_realized_outcomes") is not False
        or len(lane_terminal_identities) != 2
        or len(lane_completion_identities) != 2
        or len({identity["uri"] for identity in lane_terminal_identities}) != 2
        or len({identity["uri"] for identity in lane_completion_identities}) != 2
    ):
        _fail("fixed-G0 replay receipt differs from the exact adapter replay")
    for field in FIXED_G0_REPLAY_FALSE_FIELDS:
        if receipt.get(field) is not False:
            _fail("fixed-G0 replay receipt claims downstream authority")
    expected_uri = f"{release.get('catalog_namespace')}fixed-g0-replay-receipt.json"
    if receipt_identity["uri"] != expected_uri:
        _fail("fixed-G0 replay receipt URI differs from catalog namespace")
    return receipt, receipt_identity


def _percentiles(values: Mapping[str, float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values.values())
    denominator = len(ordered) - 1
    if denominator == 0:
        return {key: 0.0 for key in values}
    return {
        key: sum(other < value for other in ordered) / denominator
        for key, value in values.items()
    }


def _average(values: Sequence[float | None]) -> float | None:
    retained = [float(value) for value in values if value is not None]
    return None if not retained else sum(retained) / len(retained)


def _last_complete_average(
    rows: Sequence[Mapping[str, object]], field: str, count: int,
) -> tuple[float | None, int]:
    values = [
        _number_or_none(row.get(field), label=f"history.{field}")
        for row in rows[-count:]
    ]
    observed = sum(value is not None for value in values)
    if len(values) != count or observed != count:
        return None, observed
    return _average(values), observed


def _family(position: object) -> str | None:
    return POSITION_FAMILY.get(str(position))


def _depth_rank_number(value: object) -> int | None:
    if value is None:
        return None
    if type(value) is int:
        return value if value >= 1 else None
    if type(value) is float and value.is_integer():
        integer = int(value)
        return integer if integer >= 1 else None
    if type(value) is str and value.strip().isdigit():
        integer = int(value.strip())
        return integer if integer >= 1 else None
    return None


def _snapshot_date(value: object) -> date | None:
    if type(value) is not str or not value:
        return None
    candidate = value[:10]
    try:
        return datetime.strptime(candidate, "%Y-%m-%d").date()
    except ValueError:
        return None


def _schedule_indexes(
    schedule_rows: Sequence[Mapping[str, object]],
) -> tuple[
    list[dict[str, object]],
    dict[tuple[int, int, str], dict[str, object]],
]:
    games: list[dict[str, object]] = []
    by_team: dict[tuple[int, int, str], dict[str, object]] = {}
    seen_games: set[str] = set()
    for ordinal, raw in enumerate(schedule_rows):
        row = _mapping(raw, label=f"schedule row[{ordinal}]")
        key = _key(row, label=f"schedule row[{ordinal}]")
        if row.get("game_type") != "REG":
            _fail("schedule pack contains a non-regular-season game")
        game_id = _text(row.get("game_id"), label="schedule game ID")
        if game_id in seen_games:
            _fail("schedule pack repeats a regular-season game ID")
        seen_games.add(game_id)
        home = _text(row.get("home_team"), label="schedule home team")
        away = _text(row.get("away_team"), label="schedule away team")
        if home == away:
            _fail("schedule pack contains a self-opponent game")
        gameday = _text(row.get("gameday"), label="schedule gameday")
        gametime = _text(row.get("gametime"), label="schedule gametime")
        try:
            game_date = datetime.strptime(gameday, "%Y-%m-%d").date()
            local_time = datetime.strptime(gametime, "%H:%M").time()
            derived_kickoff = datetime.combine(
                game_date,
                local_time,
                tzinfo=ZoneInfo("America/New_York"),
            ).astimezone(timezone.utc)
        except ValueError as exc:
            raise CorpusR6MatchupComponentProducerV1Error(
                "schedule game date/time is invalid"
            ) from exc
        kickoff = _parse_utc(
            row.get("kickoff_time_utc"), label="schedule kickoff"
        )
        if kickoff != derived_kickoff:
            _fail("schedule kickoff differs from gameday/gametime")
        normalized = dict(row)
        normalized["_key"] = key
        normalized["_kickoff"] = kickoff
        games.append(normalized)
        for team in (home, away):
            index_key = (key[0], key[1], team)
            if index_key in by_team:
                _fail("schedule pack repeats a team/week regular-season game")
            by_team[index_key] = normalized
    games.sort(key=lambda row: (row["_kickoff"], str(row["game_id"])))
    return games, by_team


def _opponent_for_game(game: Mapping[str, object], team: str) -> str:
    if game["home_team"] == team:
        return str(game["away_team"])
    if game["away_team"] == team:
        return str(game["home_team"])
    _fail("schedule game does not contain the requested team")


def _valid_weekly_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    schedule_by_team: Mapping[tuple[int, int, str], Mapping[str, object]],
    before_lock: datetime,
) -> list[dict[str, object]]:
    retained: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"weekly row[{ordinal}]")
        key = _key(row, label=f"weekly row[{ordinal}]")
        player_id = _text(row.get("player_id"), label="weekly player ID")
        team = _text(row.get("team"), label="weekly team")
        opponent = _text(row.get("opponent_team"), label="weekly opponent")
        game = schedule_by_team.get((key[0], key[1], team))
        if game is None or game["_kickoff"] >= before_lock:
            continue
        if _opponent_for_game(game, team) != opponent:
            _fail("weekly row opponent differs from the exact schedule")
        identity = (key, player_id, str(row.get("position")), team)
        if identity in seen:
            _fail("weekly pack repeats a player/team/week/position row")
        seen.add(identity)
        normalized = dict(row)
        normalized["_key"] = key
        normalized["_kickoff"] = game["_kickoff"]
        normalized["_kickoff_time_utc"] = game["kickoff_time_utc"]
        retained.append(normalized)
    retained.sort(
        key=lambda row: (
            row["_kickoff"], str(row["team"]), str(row["position"]),
            str(row["player_id"]),
        )
    )
    return retained


def _route_rows_by_player(
    rows: Sequence[Mapping[str, object]],
    *,
    weekly_rows: Sequence[Mapping[str, object]],
    before_lock: datetime,
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen: set[tuple[str, tuple[int, int]]] = set()
    weekly_kickoffs: dict[tuple[str, tuple[int, int]], datetime] = {}
    for weekly in weekly_rows:
        identity = (str(weekly["player_id"]), weekly["_key"])
        kickoff = weekly["_kickoff"]
        if identity in weekly_kickoffs and weekly_kickoffs[identity] != kickoff:
            _fail("weekly history gives one player/week multiple kickoffs")
        weekly_kickoffs[identity] = kickoff
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"FP route row[{ordinal}]")
        key = _key(row, label=f"FP route row[{ordinal}]")
        player_id = _text(row.get("gsis_id"), label="FP route player ID")
        kickoff = weekly_kickoffs.get((player_id, key))
        if kickoff is None or kickoff >= before_lock:
            continue
        identity = (player_id, key)
        if identity in seen:
            _fail("FP route pack repeats a player/week row")
        seen.add(identity)
        value = _number_or_none(row.get("route_share"), label="FP route share")
        if value is not None and not 0.0 <= value <= 1.0:
            _fail("FP route share must be within [0,1]")
        normalized = dict(row)
        normalized["_key"] = key
        normalized["_kickoff"] = kickoff
        normalized["_kickoff_time_utc"] = kickoff.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        result[player_id].append(normalized)
    for player_rows in result.values():
        player_rows.sort(key=lambda row: row["_kickoff"])
    return dict(result)


def _legacy_depth_rank(
    rows: Sequence[Mapping[str, object]],
    *,
    player_id: str,
    team: str,
    position: str,
    key: tuple[int, int],
) -> int | None:
    ranks: list[int] = []
    for raw in rows:
        row = _mapping(raw, label="legacy depth row")
        if (
            row.get("gsis_id") != player_id
            or row.get("club_code") != team
            or row.get("season") != key[0]
            or row.get("week") != key[1]
            or row.get("formation") != "Offense"
            or row.get("position") != position
        ):
            continue
        rank = _depth_rank_number(row.get("depth_team"))
        if rank is not None:
            ranks.append(rank)
    return min(ranks) if ranks else None


def _snapshot_depth_rank(
    rows: Sequence[Mapping[str, object]],
    *,
    player_id: str,
    team: str,
    position: str,
    game_day: date,
) -> int | None:
    candidates: list[tuple[date, int]] = []
    for raw in rows:
        row = _mapping(raw, label="snapshot depth row")
        if (
            row.get("gsis_id") != player_id
            or row.get("team") != team
            or row.get("pos_abb") != position
        ):
            continue
        snapshot_day = _snapshot_date(row.get("dt"))
        rank = _depth_rank_number(row.get("pos_rank"))
        if snapshot_day is not None and snapshot_day < game_day and rank is not None:
            candidates.append((snapshot_day, rank))
    if not candidates:
        return None
    latest = max(day for day, _ in candidates)
    return min(rank for day, rank in candidates if day == latest)


def _depth_rank(
    *,
    player_id: str,
    team: str,
    position: str,
    key: tuple[int, int],
    game_day: date,
    legacy_depth_rows: Sequence[Mapping[str, object]],
    snapshot_depth_rows: Sequence[Mapping[str, object]],
) -> int | None:
    if key[0] <= 2024:
        return _legacy_depth_rank(
            legacy_depth_rows,
            player_id=player_id,
            team=team,
            position=position,
            key=key,
        )
    return _snapshot_depth_rank(
        snapshot_depth_rows,
        player_id=player_id,
        team=team,
        position=position,
        game_day=game_day,
    )


def _role_components(
    *,
    family: str,
    history: Sequence[Mapping[str, object]],
    route_history: Sequence[Mapping[str, object]],
    depth_rank: int | None,
) -> dict[str, object]:
    fields = (
        ("target_share", "target_share"),
        ("route_share", "route_share"),
        ("air_yards_share", "air_yards_share"),
    ) if family == "receiver" else (
        ("carry_share", "_carry_share"),
        ("target_share", "target_share"),
        ("route_share", "route_share"),
    ) if family == "rb" else ()
    if not fields:
        _fail("role components requested for an unsupported family")
    result: dict[str, object] = {}
    for window_name, count in (("last_one", 1), ("last_four", 4)):
        for component, field in fields:
            rows = route_history if component == "route_share" else history
            value, observed = _last_complete_average(rows, field, count)
            result[f"{component}_{window_name}"] = value
            result[f"{component}_{window_name}_observed_game_count"] = observed
    result["depth"] = None if depth_rank is None else -float(depth_rank)
    return result


def _role_label(*, family: str, position: str, rank: int) -> str:
    if family == "rb":
        return "RB1" if rank == 1 else "RB2" if rank == 2 else "RB3+"
    if position == "WR":
        return "WR1" if rank == 1 else "WR2" if rank == 2 else "WR3+"
    return "TE1" if rank == 1 else "TE2+"


def _rank_role_group(
    players: Sequence[Mapping[str, object]], *, family: str,
) -> dict[str, dict[str, object]]:
    if not players:
        return {}
    base_components = (
        ("target_share", "route_share", "air_yards_share")
        if family == "receiver"
        else ("carry_share", "target_share", "route_share")
    )
    component_names = tuple(
        f"{component}_{window}"
        for window in ("last_one", "last_four")
        for component in base_components
    ) + ("depth",)
    percentiles: dict[str, dict[str, float]] = {}
    for component in component_names:
        values = {
            str(player["player_id"]): float(player["components"][component])
            for player in players
            if player["components"][component] is not None
        }
        percentiles[component] = _percentiles(values)
    result: dict[str, dict[str, object]] = {}
    for player in players:
        player_id = str(player["player_id"])
        available = {
            component: percentiles[component][player_id]
            for component in component_names
            if player_id in percentiles[component]
        }
        component_count = len(available)
        supported = component_count >= 2 and len(players) >= 2
        result[player_id] = {
            "role_supported": supported,
            "role_component_count": component_count,
            "role_consensus_score": (
                None if not available else sum(available.values()) / len(available)
            ),
            "role_label": None,
            "role_rank": None,
            "role_component_values": dict(player["components"]),
            "role_component_observed_game_counts": {
                component: player["components"].get(
                    f"{component}_observed_game_count"
                )
                for component in component_names if component != "depth"
            },
            "role_component_percentiles": available,
            "role_window_sensitivity": {},
            "depth_rank": player.get("depth_rank"),
            "salary": player.get("salary"),
        }
    supported_ids = [
        str(player["player_id"])
        for player in players
        if result[str(player["player_id"])]["role_supported"] is True
    ]
    supported_ids.sort(key=lambda player_id: (
        -float(result[player_id]["role_consensus_score"]),
        (
            10**9
            if result[player_id]["depth_rank"] is None
            else int(result[player_id]["depth_rank"])
        ),
        -(
            0
            if result[player_id]["salary"] is None
            else int(result[player_id]["salary"])
        ),
        player_id,
    ))
    position_by_id = {
        str(player["player_id"]): str(player["position"])
        for player in players
    }
    for rank, player_id in enumerate(supported_ids, start=1):
        position = position_by_id[player_id]
        result[player_id]["role_rank"] = rank
        result[player_id]["role_label"] = _role_label(
            family=family, position=position, rank=rank
        )

    for window in ("last_one", "last_four"):
        window_components = tuple(
            f"{component}_{window}" for component in base_components
        ) + ("depth",)
        for player in players:
            player_id = str(player["player_id"])
            raw_values = {
                component.removesuffix(f"_{window}"): player["components"][
                    component
                ]
                for component in window_components
            }
            ranked_values = {
                component.removesuffix(f"_{window}"): percentiles[component][
                    player_id
                ]
                for component in window_components
                if player_id in percentiles[component]
            }
            component_count = len(ranked_values)
            supported = component_count >= 2 and len(players) >= 2
            result[player_id]["role_window_sensitivity"][window] = {
                "role_supported": supported,
                "role_component_count": component_count,
                "role_consensus_score": (
                    None if not ranked_values
                    else sum(ranked_values.values()) / len(ranked_values)
                ),
                "role_rank": None,
                "role_label": None,
                "component_values": raw_values,
                "component_observed_game_counts": {
                    component.removesuffix(f"_{window}"): player[
                        "components"
                    ].get(f"{component}_observed_game_count")
                    for component in window_components if component != "depth"
                },
                "component_percentiles": ranked_values,
            }
        window_supported = [
            str(player["player_id"])
            for player in players
            if result[str(player["player_id"])]["role_window_sensitivity"][
                window
            ]["role_supported"] is True
        ]
        window_supported.sort(key=lambda player_id: (
            -float(result[player_id]["role_window_sensitivity"][window][
                "role_consensus_score"
            ]),
            (
                10**9
                if result[player_id]["depth_rank"] is None
                else int(result[player_id]["depth_rank"])
            ),
            -(0 if result[player_id]["salary"] is None
              else int(result[player_id]["salary"])),
            player_id,
        ))
        for rank, player_id in enumerate(window_supported, start=1):
            sensitivity = result[player_id]["role_window_sensitivity"][window]
            sensitivity["role_rank"] = rank
            sensitivity["role_label"] = _role_label(
                family=family,
                position=position_by_id[player_id],
                rank=rank,
            )
    return result


def _carry_shares(
    weekly_rows: Sequence[Mapping[str, object]],
) -> dict[tuple[tuple[int, int], str, str], float | None]:
    totals: dict[tuple[tuple[int, int], str], float] = defaultdict(float)
    carries: dict[tuple[tuple[int, int], str, str], float | None] = {}
    incomplete: set[tuple[tuple[int, int], str]] = set()
    for row in weekly_rows:
        if row.get("position") != "RB":
            continue
        key = row["_key"]
        team = str(row["team"])
        player_id = str(row["player_id"])
        value = _number_or_none(row.get("carries"), label="weekly carries")
        if value is None or value < 0:
            incomplete.add((key, team))
            carries[(key, team, player_id)] = None
            continue
        totals[(key, team)] += value
        carries[(key, team, player_id)] = value
    result: dict[tuple[tuple[int, int], str, str], float | None] = {}
    for identity, value in carries.items():
        denominator = totals[(identity[0], identity[1])]
        result[identity] = (
            None
            if (identity[0], identity[1]) in incomplete
            or denominator <= 0
            or value is None
            else value / denominator
        )
    return result


def _source_role_labels(
    *,
    weekly_rows: Sequence[Mapping[str, object]],
    route_rows_by_player: Mapping[str, Sequence[Mapping[str, object]]],
    schedule_by_team: Mapping[tuple[int, int, str], Mapping[str, object]],
    legacy_depth_rows: Sequence[Mapping[str, object]],
    snapshot_depth_rows: Sequence[Mapping[str, object]],
) -> dict[tuple[str, int, int], dict[str, object]]:
    """Assign source-game roles from evidence that existed before kickoff.

    A completed source-game row may identify a game that needs a concession
    label, but it never defines that game's peer population.  Exact pregame
    depth is the population spine when available.  Otherwise the fallback
    population is players whose latest strictly-prior opportunity row places
    them on the source team and who also have strictly-prior route evidence.
    """
    carry_share = _carry_shares(weekly_rows)
    normalized_weekly: list[dict[str, object]] = []
    source_games: dict[str, Mapping[str, object]] = {}
    for raw in weekly_rows:
        row = dict(raw)
        row["_carry_share"] = carry_share.get(
            (row["_key"], str(row["team"]), str(row["player_id"]))
        )
        normalized_weekly.append(row)
        game = schedule_by_team.get(
            (row["_key"][0], row["_key"][1], str(row["team"]))
        )
        if game is not None:
            source_games[str(game["game_id"])] = game

    def depth_peers(
        *,
        team: str,
        positions: frozenset[str],
        key: tuple[int, int],
        game_day: date,
    ) -> list[tuple[str, str, int]]:
        candidates: dict[tuple[str, str], int] = {}
        if key[0] <= 2024:
            for raw in legacy_depth_rows:
                row = _mapping(raw, label="source-game legacy depth row")
                position = str(row.get("position"))
                if (
                    row.get("club_code") != team
                    or row.get("season") != key[0]
                    or row.get("week") != key[1]
                    or row.get("formation") != "Offense"
                    or position not in positions
                ):
                    continue
                player_id = str(row.get("gsis_id", ""))
                rank = _depth_rank_number(row.get("depth_team"))
                if not player_id or rank is None:
                    continue
                identity = (player_id, position)
                candidates[identity] = min(rank, candidates.get(identity, rank))
        else:
            latest: dict[tuple[str, str], tuple[date, int]] = {}
            for raw in snapshot_depth_rows:
                row = _mapping(raw, label="source-game snapshot depth row")
                position = str(row.get("pos_abb"))
                if row.get("team") != team or position not in positions:
                    continue
                player_id = str(row.get("gsis_id", ""))
                snapshot_day = _snapshot_date(row.get("dt"))
                rank = _depth_rank_number(row.get("pos_rank"))
                if (
                    not player_id
                    or snapshot_day is None
                    or snapshot_day >= game_day
                    or rank is None
                ):
                    continue
                identity = (player_id, position)
                retained = latest.get(identity)
                if retained is None or snapshot_day > retained[0]:
                    latest[identity] = (snapshot_day, rank)
                elif snapshot_day == retained[0]:
                    latest[identity] = (snapshot_day, min(rank, retained[1]))
            candidates = {
                identity: retained[1] for identity, retained in latest.items()
            }
        return sorted(
            (
                (player_id, position, rank)
                for (player_id, position), rank in candidates.items()
            ),
            key=lambda value: (value[1], value[2], value[0]),
        )

    result: dict[tuple[str, int, int], dict[str, object]] = {}
    ordered_games = sorted(
        source_games.values(),
        key=lambda game: (game["_kickoff"], str(game["game_id"])),
    )
    for game in ordered_games:
        key = game["_key"]
        kickoff = game["_kickoff"]
        game_day = datetime.strptime(str(game["gameday"]), "%Y-%m-%d").date()
        for team in sorted((str(game["home_team"]), str(game["away_team"]))):
            for position_group, positions in (
                ("RB", frozenset({"RB"})),
                ("WR", frozenset({"WR"})),
                ("TE", frozenset({"TE"})),
            ):
                peers = depth_peers(
                    team=team,
                    positions=positions,
                    key=key,
                    game_day=game_day,
                )
                if not peers:
                    fallback: list[tuple[str, str, int]] = []
                    for player_id in sorted({
                        str(row["player_id"]) for row in normalized_weekly
                    }):
                        history = [
                            row for row in normalized_weekly
                            if str(row["player_id"]) == player_id
                            and row["_kickoff"] < kickoff
                        ]
                        routes = [
                            row for row in route_rows_by_player.get(player_id, ())
                            if row["_kickoff"] < kickoff
                        ]
                        if not history or not routes:
                            continue
                        latest = history[-1]
                        position = str(latest["position"])
                        if str(latest["team"]) == team and position in positions:
                            fallback.append((player_id, position, 10**9))
                    peers = fallback
                candidates: list[dict[str, object]] = []
                for player_id, position, depth_rank in peers:
                    history = [
                        row for row in normalized_weekly
                        if str(row["player_id"]) == player_id
                        and row["_kickoff"] < kickoff
                    ]
                    routes = [
                        row for row in route_rows_by_player.get(player_id, ())
                        if row["_kickoff"] < kickoff
                    ]
                    depth = None if depth_rank == 10**9 else depth_rank
                    family = "rb" if position_group == "RB" else "receiver"
                    candidates.append({
                        "player_id": player_id,
                        "team": team,
                        "position": position,
                        "depth_rank": depth,
                        "salary": None,
                        "components": _role_components(
                            family=family,
                            history=history,
                            route_history=routes,
                            depth_rank=depth,
                        ),
                    })
                family = "rb" if position_group == "RB" else "receiver"
                for player_id, role in _rank_role_group(
                    candidates, family=family
                ).items():
                    result[(player_id, key[0], key[1])] = role
    return result


def _target_roles(
    *,
    catalog: Mapping[str, object],
    target_games: Sequence[Mapping[str, object]],
    weekly_rows: Sequence[Mapping[str, object]],
    route_rows_by_player: Mapping[str, Sequence[Mapping[str, object]]],
    legacy_depth_rows: Sequence[Mapping[str, object]],
    snapshot_depth_rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    target_key = (
        int(catalog["slate"]["season"]), int(catalog["slate"]["week"])
    )
    game_by_team: dict[str, Mapping[str, object]] = {}
    for game in target_games:
        game_by_team[str(game["home_team"])] = game
        game_by_team[str(game["away_team"])] = game
    histories: dict[str, list[dict[str, object]]] = defaultdict(list)
    carry_share = _carry_shares(weekly_rows)
    for raw in weekly_rows:
        row = dict(raw)
        row["_carry_share"] = carry_share.get(
            (row["_key"], str(row["team"]), str(row["player_id"]))
        )
        histories[str(row["player_id"])].append(row)
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for player in catalog["players"]:
        position = str(player["pos"])
        family = _family(position)
        if family not in {"receiver", "rb"}:
            continue
        player_id = str(player["id"])
        team = str(player["team"])
        game = game_by_team.get(team)
        if game is None:
            _fail("catalog skill player has no exact target schedule game")
        game_day = datetime.strptime(
            str(game["gameday"]), "%Y-%m-%d"
        ).date()
        depth = _depth_rank(
            player_id=player_id,
            team=team,
            position=position,
            key=target_key,
            game_day=game_day,
            legacy_depth_rows=legacy_depth_rows,
            snapshot_depth_rows=snapshot_depth_rows,
        )
        routes = [
            row for row in route_rows_by_player.get(player_id, ())
            if row["_kickoff"] < _parse_utc(
                game["kickoff_time_utc"], label="target role kickoff"
            )
        ]
        groups[(team, "RB" if family == "rb" else position)].append({
            "player_id": player_id,
            "team": team,
            "position": position,
            "depth_rank": depth,
            "salary": int(player["salary"]),
            "components": _role_components(
                family=family,
                history=histories.get(player_id, ()),
                route_history=routes,
                depth_rank=depth,
            ),
        })
    result: dict[str, dict[str, object]] = {}
    for (_, position_group), candidates in sorted(groups.items()):
        family = "rb" if position_group == "RB" else "receiver"
        result.update(_rank_role_group(candidates, family=family))
    return result


def _target_games(
    *,
    catalog: Mapping[str, object],
    schedule_games: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    season = int(catalog["slate"]["season"])
    week = int(catalog["slate"]["week"])
    expected_pairs = {
        tuple(sorted((str(player["team"]), str(player["opp"]))))
        for player in catalog["players"]
    }
    matched: dict[tuple[str, str], dict[str, object]] = {}
    for raw in schedule_games:
        if raw["_key"] != (season, week):
            continue
        pair = tuple(sorted((str(raw["home_team"]), str(raw["away_team"]))))
        if pair not in expected_pairs:
            continue
        if pair in matched:
            _fail("schedule pack repeats a catalog target team pair")
        matched[pair] = {
            key: raw[key]
            for key in (
                "away_team", "game_id", "game_type", "gameday", "gametime",
                "home_team", "kickoff_time_utc", "season", "week",
            )
        }
    if set(matched) != expected_pairs:
        _fail("schedule pack does not cover the exact catalog game set")
    return sorted(matched.values(), key=lambda row: str(row["game_id"]))


def _prior_defense_games(
    *,
    defense: str,
    schedule_games: Sequence[Mapping[str, object]],
    lock_time: datetime,
    count: int,
) -> list[dict[str, object]]:
    rows = [
        row for row in schedule_games
        if row["_kickoff"] < lock_time
        and defense in {str(row["home_team"]), str(row["away_team"])}
    ]
    rows.sort(key=lambda row: (row["_kickoff"], str(row["game_id"])))
    return rows[-count:]


def _receiving_dk(row: Mapping[str, object]) -> float | None:
    receptions = _number_or_none(row.get("receptions"), label="receptions")
    yards = _number_or_none(
        row.get("receiving_yards"), label="receiving yards"
    )
    touchdowns = _number_or_none(
        row.get("receiving_tds"), label="receiving touchdowns"
    )
    if receptions is None or yards is None or touchdowns is None:
        return None
    return receptions + 0.1 * yards + 6.0 * touchdowns + (3.0 if yards >= 100 else 0.0)


def _rushing_dk(row: Mapping[str, object]) -> float | None:
    yards = _number_or_none(row.get("rushing_yards"), label="rushing yards")
    touchdowns = _number_or_none(
        row.get("rushing_tds"), label="rushing touchdowns"
    )
    if yards is None or touchdowns is None:
        return None
    return 0.1 * yards + 6.0 * touchdowns + (3.0 if yards >= 100 else 0.0)


def _qb_dk(row: Mapping[str, object]) -> float | None:
    pass_yards = _number_or_none(
        row.get("passing_yards"), label="passing yards"
    )
    pass_tds = _number_or_none(
        row.get("passing_tds"), label="passing touchdowns"
    )
    interceptions = _number_or_none(
        row.get("passing_interceptions"), label="passing interceptions"
    )
    rush_yards = _number_or_none(
        row.get("rushing_yards"), label="QB rushing yards"
    )
    rush_tds = _number_or_none(
        row.get("rushing_tds"), label="QB rushing touchdowns"
    )
    fumbles = _number_or_none(
        row.get("fumbles_lost_total"), label="lost fumbles"
    )
    if any(value is None for value in (
        pass_yards, pass_tds, interceptions, rush_yards, rush_tds, fumbles,
    )):
        return None
    assert pass_yards is not None
    assert pass_tds is not None
    assert interceptions is not None
    assert rush_yards is not None
    assert rush_tds is not None
    assert fumbles is not None
    return (
        0.04 * pass_yards
        + 4.0 * pass_tds
        - interceptions
        + (3.0 if pass_yards >= 300 else 0.0)
        + 0.1 * rush_yards
        + 6.0 * rush_tds
        + (3.0 if rush_yards >= 100 else 0.0)
        - fumbles
    )


def _role_concession_components(
    *,
    catalog: Mapping[str, object],
    target_roles: Mapping[str, Mapping[str, object]],
    source_roles: Mapping[tuple[str, int, int], Mapping[str, object]],
    weekly_rows: Sequence[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
    lock_time: datetime,
) -> dict[str, dict[str, float | None]]:
    by_defense_key: dict[
        tuple[str, tuple[int, int]], list[Mapping[str, object]]
    ] = defaultdict(list)
    for row in weekly_rows:
        by_defense_key[(str(row["opponent_team"]), row["_key"])].append(row)
    result: dict[str, dict[str, float | None]] = {}
    for player in catalog["players"]:
        player_id = str(player["id"])
        family = _family(player["pos"])
        if family not in {"receiver", "rb"}:
            continue
        role = target_roles.get(player_id)
        label = None if role is None else role.get("role_label")
        defense = str(player["opp"])
        games = _prior_defense_games(
            defense=defense,
            schedule_games=schedule_games,
            lock_time=lock_time,
            count=8,
        )
        receiving_games: list[float] = []
        rushing_games: list[float] = []
        if label is not None:
            for game in games:
                key = game["_key"]
                matching_rows: list[Mapping[str, object]] = []
                for row in by_defense_key.get((defense, key), ()):
                    source_role = source_roles.get(
                        (str(row["player_id"]), key[0], key[1])
                    )
                    if (
                        source_role is None
                        or source_role.get("role_supported") is not True
                        or source_role.get("role_label") != label
                    ):
                        continue
                    matching_rows.append(row)
                if not matching_rows:
                    continue
                receiving_values = [_receiving_dk(row) for row in matching_rows]
                if all(value is not None for value in receiving_values):
                    receiving_games.append(sum(
                        float(value) for value in receiving_values
                        if value is not None
                    ))
                if family == "rb":
                    rushing_values = [_rushing_dk(row) for row in matching_rows]
                    if all(value is not None for value in rushing_values):
                        rushing_games.append(sum(
                            float(value) for value in rushing_values
                            if value is not None
                        ))
        receiving_supported = (
            label is not None
            and len(receiving_games) >= MINIMUM_PRIOR_GAMES
        )
        rushing_supported = (
            label is not None
            and len(rushing_games) >= MINIMUM_PRIOR_GAMES
        )
        result[player_id] = {
            "role_concession": (
                sum(receiving_games) / len(receiving_games)
                if receiving_supported and family == "receiver"
                else None
            ),
            "rushing_concession": (
                sum(rushing_games) / len(rushing_games)
                if rushing_supported and family == "rb"
                else None
            ),
            "receiving_concession": (
                sum(receiving_games) / len(receiving_games)
                if receiving_supported and family == "rb"
                else None
            ),
            "role_concession_observed_game_count": (
                len(receiving_games) if family == "receiver" else None
            ),
            "rushing_concession_observed_game_count": (
                len(rushing_games) if family == "rb" else None
            ),
            "receiving_concession_observed_game_count": (
                len(receiving_games) if family == "rb" else None
            ),
        }
    return result


def _alignment_rows_for_target(
    rows: Sequence[Mapping[str, object]], *, target_key: tuple[int, int],
) -> dict[str, float]:
    if target_key[1] <= 4:
        return {}
    result: dict[str, float] = {}
    for raw in rows:
        row = _mapping(raw, label="FP alignment row")
        if (
            row.get("season") != target_key[0]
            or row.get("target_week") != target_key[1]
            or row.get("alignment_supported") is not True
            or row.get("split_duplicate") is not False
        ):
            continue
        player_id = _text(row.get("gsis_id"), label="FP alignment player ID")
        if player_id in result:
            _fail("FP alignment pack repeats a supported target player")
        share = _number(row.get("player_wide_share"), label="FP wide share")
        if not 0.0 <= share <= 1.0:
            _fail("FP wide share must be within [0,1]")
        result[player_id] = share
    return result


def _sis_defender_views(
    *,
    defense: str,
    sis_rows: Sequence[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
    schedule_by_team: Mapping[tuple[int, int, str], Mapping[str, object]],
    lock_time: datetime,
) -> tuple[dict[str, float], dict[str, float]]:
    horizon = _prior_defense_games(
        defense=defense,
        schedule_games=schedule_games,
        lock_time=lock_time,
        count=8,
    )
    horizon_keys = {game["_key"] for game in horizon}
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    league: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
    eligible_rows: list[dict[str, object]] = []
    for raw in sis_rows:
        row = _mapping(raw, label="SIS defender row")
        key = _key(row, label="SIS defender row")
        alignment = str(row.get("alignment", "")).strip().lower()
        if alignment not in {"wide", "slot"}:
            continue
        row_defense = _text(row.get("defense"), label="SIS defense")
        game = schedule_by_team.get((key[0], key[1], row_defense))
        if game is None or game["_kickoff"] >= lock_time:
            continue
        if key not in horizon_keys:
            continue
        completions = _number_or_none(
            row.get("completions"), label="SIS completions"
        )
        yards = _number_or_none(row.get("yards"), label="SIS yards")
        touchdowns = _number_or_none(
            row.get("touchdowns"), label="SIS touchdowns"
        )
        targets = _number_or_none(row.get("targets"), label="SIS targets")
        snaps = _number_or_none(
            row.get("coverage_snaps"), label="SIS coverage snaps"
        )
        if None in {completions, yards, touchdowns, targets, snaps}:
            continue
        if min(completions, yards, touchdowns, targets, snaps) < 0:
            _fail("SIS defender counts must be nonnegative")
        eligible_rows.append({
            "key": key,
            "alignment": alignment,
            "defense": row_defense,
            "defender_id": _text(
                row.get("defender_player_id"), label="SIS defender ID"
            ),
            "completions": completions,
            "yards": yards,
            "touchdowns": touchdowns,
            "targets": targets,
            "snaps": snaps,
        })

    target_defender_ids = {
        str(row["defender_id"])
        for row in eligible_rows if row["defense"] == defense
    }
    for row in eligible_rows:
        alignment = str(row["alignment"])
        row_defense = str(row["defense"])
        defender_id = str(row["defender_id"])
        # A target-defense player's rows for a former team are excluded from
        # both its workload and the shrink prior for this target-defense view.
        if defender_id in target_defender_ids and row_defense != defense:
            continue
        completions = float(row["completions"])
        yards = float(row["yards"])
        touchdowns = float(row["touchdowns"])
        targets = float(row["targets"])
        snaps = float(row["snaps"])
        dk = completions + 0.1 * yards + 6.0 * touchdowns
        prior_dk, prior_targets = league[alignment]
        league[alignment] = (prior_dk + dk, prior_targets + targets)
        if row_defense != defense:
            continue
        aggregate = grouped.setdefault((alignment, defender_id), {
            "games": set(), "snaps": 0.0, "targets": 0.0, "dk": 0.0,
        })
        aggregate["games"].add(row["key"])
        aggregate["snaps"] += snaps
        aggregate["targets"] += targets
        aggregate["dk"] += dk

    unit: dict[str, float] = {}
    top_two: dict[str, float] = {}
    for alignment in ("wide", "slot"):
        league_dk, league_targets = league.get(alignment, (0.0, 0.0))
        if league_targets <= 0:
            continue
        prior_rate = league_dk / league_targets
        supported: list[tuple[str, float, float]] = []
        for (row_alignment, defender_id), aggregate in grouped.items():
            if row_alignment != alignment:
                continue
            games = aggregate["games"]
            snaps = float(aggregate["snaps"])
            targets = float(aggregate["targets"])
            if len(games) < MINIMUM_PRIOR_GAMES or snaps <= 0:
                continue
            rate = (
                float(aggregate["dk"]) + SIS_SHRINK_TARGETS * prior_rate
            ) / (targets + SIS_SHRINK_TARGETS)
            supported.append((defender_id, snaps, rate))
        total_snaps = sum(item[1] for item in supported)
        if total_snaps <= 0:
            continue
        unit[alignment] = sum(
            snaps * rate for _, snaps, rate in supported
        ) / total_snaps
        ranked = sorted(supported, key=lambda item: (-item[1], item[0]))[:2]
        ranked_snaps = sum(item[1] for item in ranked)
        if ranked_snaps > 0:
            top_two[alignment] = sum(
                snaps * rate for _, snaps, rate in ranked
            ) / ranked_snaps
    return unit, top_two


def _receiver_nonrole_components(
    *,
    catalog: Mapping[str, object],
    alignment_rows: Sequence[Mapping[str, object]],
    shell_receiver_rows: Sequence[Mapping[str, object]],
    shell_defense_rows: Sequence[Mapping[str, object]],
    sis_defender_rows: Sequence[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
    schedule_by_team: Mapping[tuple[int, int, str], Mapping[str, object]],
    lock_time: datetime,
) -> dict[str, dict[str, float | None]]:
    target_key = (
        int(catalog["slate"]["season"]), int(catalog["slate"]["week"])
    )
    alignments = _alignment_rows_for_target(
        alignment_rows, target_key=target_key
    )
    defenses = {
        str(player["opp"])
        for player in catalog["players"] if player["pos"] in {"WR", "TE"}
    }
    defender_views = {
        defense: _sis_defender_views(
            defense=defense,
            sis_rows=sis_defender_rows,
            schedule_games=schedule_games,
            schedule_by_team=schedule_by_team,
            lock_time=lock_time,
        )
        for defense in defenses
    }
    prior_season = target_key[0] - 1
    receiver_shell: dict[str, tuple[float, float]] = {}
    for raw in shell_receiver_rows:
        row = _mapping(raw, label="FP receiver shell row")
        if (
            row.get("season") != prior_season
            or row.get("split_duplicate") is not False
        ):
            continue
        player_id = _text(row.get("gsis_id"), label="FP shell player ID")
        if player_id in receiver_shell:
            _fail("FP receiver shell pack repeats a prior-season player")
        man = _number_or_none(row.get("man_fprr"), label="FP man FPRR")
        zone = _number_or_none(row.get("zone_fprr"), label="FP zone FPRR")
        if man is not None and zone is not None:
            receiver_shell[player_id] = (man, zone)
    defense_shell: dict[str, float] = {}
    for raw in shell_defense_rows:
        row = _mapping(raw, label="FP defense shell row")
        if row.get("season") != prior_season:
            continue
        team = _text(row.get("team"), label="FP defense shell team")
        if team in defense_shell:
            _fail("FP defense shell pack repeats a prior-season team")
        rate = _number_or_none(row.get("def_man_rate"), label="FP man rate")
        if rate is not None:
            defense_shell[team] = rate
    league_man_rate = (
        None
        if not defense_shell
        else sum(defense_shell.values()) / len(defense_shell)
    )
    result: dict[str, dict[str, float | None]] = {}
    for player in catalog["players"]:
        if player["pos"] not in {"WR", "TE"}:
            continue
        player_id = str(player["id"])
        defense = str(player["opp"])
        wide_share = alignments.get(player_id)
        unit, top_two = defender_views.get(defense, ({}, {}))
        alignment_value = None
        workload_value = None
        if wide_share is not None:
            wide = unit.get("wide")
            slot = unit.get("slot")
            if wide is not None and slot is not None:
                alignment_value = wide_share * wide + (1.0 - wide_share) * slot
            dominant = "wide" if wide_share >= 0.5 else "slot"
            workload_value = top_two.get(dominant)
        shell_value = None
        player_shell = receiver_shell.get(player_id)
        defense_rate = defense_shell.get(defense)
        if (
            player_shell is not None
            and defense_rate is not None
            and league_man_rate is not None
        ):
            shell_value = (
                player_shell[0] - player_shell[1]
            ) * (defense_rate - league_man_rate)
        result[player_id] = {
            "alignment_vulnerability": alignment_value,
            "defender_workload_quality": workload_value,
            "shell_fit": shell_value,
        }
    return result


def _team_context_components(
    *,
    catalog: Mapping[str, object],
    weekly_rows: Sequence[Mapping[str, object]],
    sis_run_rows: Sequence[Mapping[str, object]],
    pfr_pressure_rows: Sequence[Mapping[str, object]],
    pfr_secondary_rows: Sequence[Mapping[str, object]],
    pfr_position_rows: Sequence[Mapping[str, object]],
    schedule_games: Sequence[Mapping[str, object]],
    schedule_by_team: Mapping[tuple[int, int, str], Mapping[str, object]],
    lock_time: datetime,
) -> dict[str, dict[str, float | None]]:
    defenses = {
        str(player["opp"])
        for player in catalog["players"]
        if player["pos"] in {"QB", "RB"}
    }
    weekly_by_defense: dict[
        tuple[str, tuple[int, int]], list[Mapping[str, object]]
    ] = defaultdict(list)
    for row in weekly_rows:
        weekly_by_defense[(str(row["opponent_team"]), row["_key"])].append(row)

    run_by_defense_key: dict[tuple[str, tuple[int, int]], Mapping[str, object]] = {}
    for raw in sis_run_rows:
        row = _mapping(raw, label="SIS run-context row")
        key = _key(row, label="SIS run-context row")
        team = _text(row.get("team"), label="SIS run-context team")
        game = schedule_by_team.get((key[0], key[1], team))
        if game is None or game["_kickoff"] >= lock_time:
            continue
        identity = (team, key)
        if identity in run_by_defense_key:
            _fail("SIS run-context pack repeats a defense/week")
        run_by_defense_key[identity] = row

    pressure_accumulators: dict[
        tuple[str, tuple[int, int]], dict[str, object]
    ] = {}
    for raw in pfr_pressure_rows:
        row = _mapping(raw, label="PFR pressure row")
        key = _key(row, label="PFR pressure row")
        team = _text(row.get("team"), label="PFR pressure team")
        game = schedule_by_team.get((key[0], key[1], team))
        if game is None or game["_kickoff"] >= lock_time:
            continue
        if row.get("game_id") != game["game_id"]:
            _fail("PFR pressure row game ID differs from exact schedule")
        pressures = _number_or_none(
            row.get("def_pressures"), label="PFR pressures"
        )
        sacks = _number_or_none(row.get("def_sacks"), label="PFR sacks")
        state = pressure_accumulators.setdefault((team, key), {
            "row_count": 0,
            "complete": True,
            "pressures": 0.0,
            "sacks": 0.0,
        })
        state["row_count"] = int(state["row_count"]) + 1
        if pressures is None or sacks is None:
            state["complete"] = False
        else:
            state["pressures"] = float(state["pressures"]) + pressures
            state["sacks"] = float(state["sacks"]) + sacks
    pressure_by_defense_key = {
        identity: (float(state["pressures"]), float(state["sacks"]))
        for identity, state in pressure_accumulators.items()
        if int(state["row_count"]) > 0 and state["complete"] is True
    }

    positions: dict[tuple[str, str, str], str] = {}
    for raw in pfr_position_rows:
        row = _mapping(raw, label="PFR position row")
        key = _key(row, label="PFR position row")
        team = _text(row.get("team"), label="PFR position team")
        game = schedule_by_team.get((key[0], key[1], team))
        if game is None or game["_kickoff"] >= lock_time:
            continue
        if row.get("game_id") != game["game_id"]:
            _fail("PFR position row game ID differs from exact schedule")
        identity = (
            str(row.get("game_id")), team,
            str(row.get("pfr_player_id")),
        )
        position = _text(row.get("position"), label="PFR position")
        if identity in positions and positions[identity] != position:
            _fail("PFR position pack conflicts for a defender/game")
        positions[identity] = position
    secondary_accumulators: dict[
        tuple[str, tuple[int, int]], dict[str, object]
    ] = {}
    db_positions = {"CB", "DB", "S", "FS", "SS"}
    for raw in pfr_secondary_rows:
        row = _mapping(raw, label="PFR secondary row")
        key = _key(row, label="PFR secondary row")
        team = _text(row.get("team"), label="PFR secondary team")
        game = schedule_by_team.get((key[0], key[1], team))
        if game is None or game["_kickoff"] >= lock_time:
            continue
        if row.get("game_id") != game["game_id"]:
            _fail("PFR secondary row game ID differs from exact schedule")
        identity = (
            str(row.get("game_id")), team, str(row.get("pfr_player_id")),
        )
        if positions.get(identity) not in db_positions:
            continue
        yards = _number_or_none(
            row.get("def_yards_allowed"), label="PFR yards allowed"
        )
        targets = _number_or_none(
            row.get("def_targets"), label="PFR targets"
        )
        state = secondary_accumulators.setdefault((team, key), {
            "row_count": 0,
            "complete": True,
            "yards": 0.0,
            "targets": 0.0,
        })
        state["row_count"] = int(state["row_count"]) + 1
        if yards is None or targets is None:
            state["complete"] = False
        else:
            state["yards"] = float(state["yards"]) + yards
            state["targets"] = float(state["targets"]) + targets
    secondary_by_defense_key = {
        identity: (float(state["yards"]), float(state["targets"]))
        for identity, state in secondary_accumulators.items()
        if int(state["row_count"]) > 0 and state["complete"] is True
    }

    by_defense: dict[str, dict[str, float | None]] = {}
    for defense in defenses:
        games8 = _prior_defense_games(
            defense=defense,
            schedule_games=schedule_games,
            lock_time=lock_time,
            count=8,
        )
        keys8 = [game["_key"] for game in games8]
        qb_games: list[float] = []
        for key in keys8:
            qb_rows = [
                row
                for row in weekly_by_defense.get((defense, key), ())
                if row.get("position") == "QB"
            ]
            qb_values = [_qb_dk(row) for row in qb_rows]
            if qb_rows and all(value is not None for value in qb_values):
                qb_games.append(sum(
                    float(value) for value in qb_values if value is not None
                ))
        qb_value = (
            sum(qb_games) / len(qb_games)
            if len(qb_games) >= MINIMUM_PRIOR_GAMES else None
        )
        run_rows: list[tuple[float, float]] = []
        for key in keys8:
            row = run_by_defense_key.get((defense, key))
            if row is None:
                continue
            attempts_value = _number_or_none(
                row.get("rdef_attempts"), label="SIS run attempts"
            )
            epa_value = _number_or_none(
                row.get("rdef_epa_per_attempt"), label="SIS run EPA"
            )
            if attempts_value is None or epa_value is None or attempts_value < 0:
                continue
            run_rows.append((attempts_value, epa_value))
        attempts = sum(row[0] for row in run_rows)
        run_epa_total = sum(row[0] * row[1] for row in run_rows)
        run_value = (
            run_epa_total / attempts
            if len(run_rows) >= MINIMUM_PRIOR_GAMES and attempts > 0 else None
        )
        pressure_games = [
            pressure_by_defense_key[(defense, key)]
            for key in keys8 if (defense, key) in pressure_by_defense_key
        ]
        pressure_value = (
            -sum(row[0] for row in pressure_games) / len(pressure_games)
            if len(pressure_games) >= MINIMUM_PRIOR_GAMES else None
        )
        games6 = games8[-6:]
        secondary_games = [
            secondary_by_defense_key[(defense, game["_key"])]
            for game in games6
            if (defense, game["_key"]) in secondary_by_defense_key
        ]
        secondary_yards = sum(row[0] for row in secondary_games)
        secondary_targets = sum(row[1] for row in secondary_games)
        secondary_value = (
            secondary_yards / secondary_targets
            if len(secondary_games) >= MINIMUM_PRIOR_GAMES
            and secondary_targets > 0 else None
        )
        by_defense[defense] = {
            "run_context": run_value,
            "qb_concession": qb_value,
            "pressure_inverted": pressure_value,
            "secondary": secondary_value,
            "run_context_observed_game_count": len(run_rows),
            "qb_concession_observed_game_count": len(qb_games),
            "pressure_inverted_observed_game_count": len(pressure_games),
            "secondary_observed_game_count": len(secondary_games),
        }
    result: dict[str, dict[str, float | None]] = {}
    for player in catalog["players"]:
        family = _family(player["pos"])
        if family not in {"qb", "rb"}:
            continue
        result[str(player["id"])] = dict(by_defense.get(str(player["opp"]), {}))
    return result


def _qb_depth_census(
    *,
    catalog: Mapping[str, object],
    target_games: Sequence[Mapping[str, object]],
    legacy_depth_rows: Sequence[Mapping[str, object]],
    snapshot_depth_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    key = (int(catalog["slate"]["season"]), int(catalog["slate"]["week"]))
    game_by_team: dict[str, Mapping[str, object]] = {}
    for game in target_games:
        game_by_team[str(game["home_team"])] = game
        game_by_team[str(game["away_team"])] = game
    rows: list[dict[str, object]] = []
    for player in catalog["players"]:
        if player["pos"] != "QB":
            continue
        game = game_by_team.get(str(player["team"]))
        if game is None:
            _fail("catalog QB lacks a target schedule game")
        game_day = datetime.strptime(str(game["gameday"]), "%Y-%m-%d").date()
        rank = _depth_rank(
            player_id=str(player["id"]),
            team=str(player["team"]),
            position="QB",
            key=key,
            game_day=game_day,
            legacy_depth_rows=legacy_depth_rows,
            snapshot_depth_rows=snapshot_depth_rows,
        )
        rows.append({
            "player_id": str(player["id"]),
            "qb_depth1": None if rank is None else rank == 1,
        })
    rows.sort(key=lambda row: str(row["player_id"]))
    true_count = sum(row["qb_depth1"] is True for row in rows)
    false_count = sum(row["qb_depth1"] is False for row in rows)
    unknown_count = sum(row["qb_depth1"] is None for row in rows)
    return {
        "catalog_qb_count": len(rows),
        "rows": rows,
        "row_manifest_sha256": source.canonical_sha256(rows),
        "depth_true_count": true_count,
        "depth_false_count": false_count,
        "depth_unknown_count": unknown_count,
        "qb_depth_complete": unknown_count == 0,
    }


def _pack_slices(
    pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    seen_packs: list[str] = []
    for ordinal, raw in enumerate(pack_row_objects):
        pack = source.validate_upstream_pack_rows_v1(raw)
        pack_id = str(pack["pack_id"])
        seen_packs.append(pack_id)
        for slice_value in pack["slices"]:
            slice_entry = _mapping(slice_value, label="upstream slice")
            slice_kind = str(slice_entry["slice_kind"])
            if slice_kind in result:
                _fail("seven-pack input repeats a semantic slice kind")
            result[slice_kind] = [dict(row) for row in slice_entry["rows"]]
    if tuple(seen_packs) != source.PACK_IDS:
        _fail("upstream pack bodies differ from the fixed seven-pack order")
    return result


def _component_percentiles(
    *,
    catalog: Mapping[str, object],
    raw_by_player: Mapping[str, Mapping[str, float | None]],
) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {
        str(player["id"]): {
            component: None for component in FAMILY_COMPONENTS[family]
        }
        for player in catalog["players"]
        if (family := _family(player["pos"])) is not None
    }
    for family, components in FAMILY_COMPONENTS.items():
        family_ids = [
            str(player["id"])
            for player in catalog["players"] if _family(player["pos"]) == family
        ]
        for component in components:
            values = {
                player_id: float(raw_by_player[player_id][component])
                for player_id in family_ids
                if raw_by_player.get(player_id, {}).get(component) is not None
            }
            ranked = _percentiles(values)
            for player_id, value in ranked.items():
                result[player_id][component] = value
    return result


def _semantic_annotations(
    *,
    catalog: Mapping[str, object],
    qb_depth_census: Mapping[str, object],
    raw_by_player: Mapping[str, Mapping[str, float | None]],
    observed_game_counts_by_player: Mapping[
        str, Mapping[str, int | None]
    ],
) -> list[dict[str, object]]:
    percentiles = _component_percentiles(
        catalog=catalog, raw_by_player=raw_by_player
    )
    depth = {
        str(row["player_id"]): row["qb_depth1"]
        for row in qb_depth_census["rows"]
    }
    rows: list[dict[str, object]] = []
    target_week = int(catalog["slate"]["week"])
    for player in catalog["players"]:
        family = _family(player["pos"])
        if family is None:
            continue
        player_id = str(player["id"])
        values = dict(percentiles[player_id])
        support = {
            component: values[component] is not None
            for component in FAMILY_COMPONENTS[family]
        }
        missingness_reasons = {
            component: (
                None
                if support[component]
                else "source_unavailable"
                if target_week <= 4 and component in {
                    "alignment_vulnerability",
                    "defender_workload_quality",
                }
                else "insufficient_history"
            )
            for component in FAMILY_COMPONENTS[family]
        }
        retained = [
            float(values[component])
            for component in FAMILY_COMPONENTS[family]
            if support[component]
        ]
        edge = (
            sum(retained) / len(retained)
            if len(retained) >= 2 else None
        )
        qb_depth = depth.get(player_id) if family == "qb" else None
        rows.append({
            "gsis_id": player_id,
            "family": family,
            "position": str(player["pos"]),
            "qb_depth1": qb_depth,
            "qb_depth_evidence_class": (
                source.EVIDENCE_CLASS if family == "qb" and qb_depth is not None
                else "unknown" if family == "qb" else None
            ),
            "raw_component_values": {
                component: raw_by_player[player_id][component]
                for component in FAMILY_COMPONENTS[family]
            },
            "component_observed_game_counts": {
                component: observed_game_counts_by_player.get(
                    player_id, {}
                ).get(component)
                for component in FAMILY_COMPONENTS[family]
            },
            "component_values": values,
            "component_support": support,
            "component_missingness_reasons": missingness_reasons,
            "matchup_component_count": len(retained),
            "matchup_edge_score": edge,
            "annotation_row_present": edge is not None,
        })
    rows.sort(key=lambda row: str(row["gsis_id"]))
    return rows


def _derive_semantic_slate(
    *,
    catalog: Mapping[str, object],
    slices: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    schedule_games, schedule_by_team = _schedule_indexes(
        slices["schedule-games"]
    )
    target_games = _target_games(catalog=catalog, schedule_games=schedule_games)
    lock_time = min(
        _parse_utc(game["kickoff_time_utc"], label="target kickoff")
        for game in target_games
    )
    target_key = (
        int(catalog["slate"]["season"]), int(catalog["slate"]["week"])
    )
    weekly_rows = _valid_weekly_rows(
        slices["weekly-player-stats"],
        schedule_by_team=schedule_by_team,
        before_lock=lock_time,
    )
    route_rows = _route_rows_by_player(
        slices["fp-route-share"],
        weekly_rows=weekly_rows,
        before_lock=lock_time,
    )
    source_roles = _source_role_labels(
        weekly_rows=weekly_rows,
        route_rows_by_player=route_rows,
        schedule_by_team=schedule_by_team,
        legacy_depth_rows=slices["legacy-depth"],
        snapshot_depth_rows=slices["snapshot-depth"],
    )
    target_roles = _target_roles(
        catalog=catalog,
        target_games=target_games,
        weekly_rows=weekly_rows,
        route_rows_by_player=route_rows,
        legacy_depth_rows=slices["legacy-depth"],
        snapshot_depth_rows=slices["snapshot-depth"],
    )
    qb_depth = _qb_depth_census(
        catalog=catalog,
        target_games=target_games,
        legacy_depth_rows=slices["legacy-depth"],
        snapshot_depth_rows=slices["snapshot-depth"],
    )
    concession = _role_concession_components(
        catalog=catalog,
        target_roles=target_roles,
        source_roles=source_roles,
        weekly_rows=weekly_rows,
        schedule_games=schedule_games,
        lock_time=lock_time,
    )
    receiver = _receiver_nonrole_components(
        catalog=catalog,
        alignment_rows=slices["fp-alignment"],
        shell_receiver_rows=slices["fp-receiver-shell"],
        shell_defense_rows=slices["fp-defense-shell"],
        sis_defender_rows=slices["sis-defender-alignment"],
        schedule_games=schedule_games,
        schedule_by_team=schedule_by_team,
        lock_time=lock_time,
    )
    team_context = _team_context_components(
        catalog=catalog,
        weekly_rows=weekly_rows,
        sis_run_rows=slices["sis-run-context"],
        pfr_pressure_rows=slices["pfr-pass-rush"],
        pfr_secondary_rows=slices["pfr-secondary"],
        pfr_position_rows=slices["pfr-snap-positions"],
        schedule_games=schedule_games,
        schedule_by_team=schedule_by_team,
        lock_time=lock_time,
    )
    raw_by_player: dict[str, dict[str, float | None]] = {}
    observed_game_counts_by_player: dict[
        str, dict[str, int | None]
    ] = {}
    for player in catalog["players"]:
        family = _family(player["pos"])
        if family is None:
            continue
        player_id = str(player["id"])
        values = {component: None for component in FAMILY_COMPONENTS[family]}
        if family == "receiver":
            values["role_concession"] = concession[player_id]["role_concession"]
            values.update(receiver[player_id])
            observed_game_counts_by_player[player_id] = {
                "role_concession": concession[player_id][
                    "role_concession_observed_game_count"
                ],
                "alignment_vulnerability": None,
                "defender_workload_quality": None,
                "shell_fit": None,
            }
        elif family == "rb":
            values["rushing_concession"] = concession[player_id][
                "rushing_concession"
            ]
            values["receiving_concession"] = concession[player_id][
                "receiving_concession"
            ]
            values["run_context"] = team_context[player_id].get("run_context")
            observed_game_counts_by_player[player_id] = {
                "rushing_concession": concession[player_id][
                    "rushing_concession_observed_game_count"
                ],
                "receiving_concession": concession[player_id][
                    "receiving_concession_observed_game_count"
                ],
                "run_context": team_context[player_id].get(
                    "run_context_observed_game_count"
                ),
            }
        else:
            for component in FAMILY_COMPONENTS["qb"]:
                values[component] = team_context[player_id].get(component)
            observed_game_counts_by_player[player_id] = {
                component: team_context[player_id].get(
                    f"{component}_observed_game_count"
                )
                for component in FAMILY_COMPONENTS["qb"]
            }
        raw_by_player[player_id] = values
    annotations = _semantic_annotations(
        catalog=catalog,
        qb_depth_census=qb_depth,
        raw_by_player=raw_by_player,
        observed_game_counts_by_player=observed_game_counts_by_player,
    )
    return {
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "lock_time_utc": lock_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_games": target_games,
        "target_roles": {
            player_id: target_roles[player_id] for player_id in sorted(target_roles)
        },
        "qb_depth_census": qb_depth,
        "annotation_rows": annotations,
        "annotation_rows_sha256": source.canonical_sha256(annotations),
        "raw_component_manifest_sha256": source.canonical_sha256(
            raw_by_player
        ),
    }


def _target_or_later_key(
    row: Mapping[str, object], *, target_key: tuple[int, int],
) -> bool:
    return _key(row, label="deletion row") >= target_key


def _delete_target_or_later(
    *,
    pack_row_objects: Sequence[Mapping[str, object]],
    target_key: tuple[int, int],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    deletable_packs = {
        source.WEEKLY_STATS_PACK,
        source.SIS_PACK,
        source.PFR_DEFENSE_PACK,
    }
    rebuilt: list[dict[str, object]] = []
    deleted: list[dict[str, object]] = []
    for pack_value in pack_row_objects:
        pack = source.validate_upstream_pack_rows_v1(pack_value)
        pack_id = str(pack["pack_id"])
        slices: list[dict[str, object]] = []
        for slice_value in pack["slices"]:
            slice_entry = _mapping(slice_value, label="deletion pack slice")
            slice_kind = str(slice_entry["slice_kind"])
            kept_rows: list[dict[str, object]] = []
            for row_value in slice_entry["rows"]:
                row = _mapping(row_value, label="deletion pack row")
                if pack_id in deletable_packs and _target_or_later_key(
                    row, target_key=target_key
                ):
                    deleted.append({
                        "pack_id": pack_id,
                        "slice_kind": slice_kind,
                        "row": row,
                    })
                else:
                    kept_rows.append(row)
            # The source-v2 positive pack builder requires a positive row in
            # every slice.  The reducer itself accepts an empty deleted slice,
            # so retain a canonical internal body rather than pretending it is
            # a publishable upstream release.
            slices.append({"slice_kind": slice_kind, "rows": kept_rows})
        rebuilt.append({"pack_id": pack_id, "slices": slices})
    deleted.sort(key=source.canonical_json_bytes)
    return rebuilt, deleted


def _slices_from_deleted_body(
    deleted_body: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for pack_value in deleted_body:
        pack = _mapping(pack_value, label="deleted pack")
        for slice_value in _sequence(pack["slices"], label="deleted slices"):
            slice_entry = _mapping(slice_value, label="deleted slice")
            result[str(slice_entry["slice_kind"])] = [
                _mapping(row, label="deleted slice row")
                for row in _sequence(slice_entry["rows"], label="deleted rows")
            ]
    return result


def _plain_pack_bodies(
    pack_row_objects: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Project the seven validated packs into the shape used by deletion."""
    result: list[dict[str, object]] = []
    for pack_value in pack_row_objects:
        pack = source.validate_upstream_pack_rows_v1(pack_value)
        result.append({
            "pack_id": str(pack["pack_id"]),
            "slices": [
                {
                    "slice_kind": str(slice_entry["slice_kind"]),
                    "rows": [dict(row) for row in slice_entry["rows"]],
                }
                for slice_entry in pack["slices"]
            ],
        })
    if tuple(str(pack["pack_id"]) for pack in result) != source.PACK_IDS:
        _fail("plain deletion inputs differ from the seven-pack order")
    return result


def _pack_body_row_count(values: Sequence[Mapping[str, object]]) -> int:
    return sum(
        len(_sequence(slice_entry["rows"], label="pack-body rows"))
        for pack in values
        for slice_entry in _sequence(pack["slices"], label="pack-body slices")
    )


def _deletion_replay(
    *,
    catalog: Mapping[str, object],
    pack_row_objects: Sequence[Mapping[str, object]],
    full_slices: Mapping[str, Sequence[Mapping[str, object]]],
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    dict[str, object],
]:
    target_key = (
        int(catalog["slate"]["season"]), int(catalog["slate"]["week"])
    )
    full_semantic = _derive_semantic_slate(catalog=catalog, slices=full_slices)
    deleted_body, deleted_rows = _delete_target_or_later(
        pack_row_objects=pack_row_objects, target_key=target_key
    )
    if not deleted_rows:
        _fail("actual deletion replay found no target-or-later source rows")
    deleted_semantic = _derive_semantic_slate(
        catalog=catalog, slices=_slices_from_deleted_body(deleted_body)
    )
    if source.canonical_json_bytes(full_semantic) != source.canonical_json_bytes(
        deleted_semantic
    ):
        _fail("target-or-later deletion changes the actual producer output")
    full_inputs = _plain_pack_bodies(pack_row_objects)
    full_count = _pack_body_row_count(full_inputs)
    deleted_count = _pack_body_row_count(deleted_body)
    by_pack = {pack_id: 0 for pack_id in source.DELETION_PACK_IDS}
    by_slice = {slice_kind: 0 for slice_kind in source.DELETION_SLICE_KINDS}
    for row in deleted_rows:
        pack_id = str(row["pack_id"])
        slice_kind = str(row["slice_kind"])
        if pack_id not in by_pack or slice_kind not in by_slice:
            _fail("deletion replay removed a row outside the fixed deletion set")
        by_pack[pack_id] += 1
        by_slice[slice_kind] += 1
    if full_count - deleted_count != len(deleted_rows):
        _fail("physical deletion replay row accounting differs")
    evidence = {
        "full_input_sha256": source.canonical_sha256(full_inputs),
        "deleted_input_sha256": source.canonical_sha256(deleted_body),
        "full_input_row_count": full_count,
        "deleted_input_row_count": deleted_count,
        "deleted_row_count": len(deleted_rows),
        "deleted_rows_sha256": source.canonical_sha256(deleted_rows),
        "deleted_row_counts_by_pack": by_pack,
        "deleted_row_counts_by_slice": by_slice,
        "semantic_output_sha256": source.canonical_sha256(full_semantic),
    }
    return full_semantic, deleted_semantic, deleted_body, evidence


def _previous_period(target_key: tuple[int, int]) -> dict[str, object]:
    if target_key[1] > 1:
        return {"season": target_key[0], "week": target_key[1] - 1}
    return {"season": target_key[0] - 1, "week": 18}


def _period_shape(
    *,
    rule: str,
    target_key: tuple[int, int],
    selected_rows: Sequence[Mapping[str, object]],
) -> tuple[str, dict[str, object] | None, dict[str, object] | None]:
    target = {"season": target_key[0], "week": target_key[1]}
    if rule == "target-slate":
        return "target-slate", target, target
    if rule == "legacy-depth":
        return (
            ("prelock-snapshot", target, target)
            if target_key[0] <= 2024 else ("unavailable", None, None)
        )
    if rule == "snapshot-depth":
        return (
            ("prelock-snapshot", target, target)
            if target_key[0] == 2025 else ("unavailable", None, None)
        )
    if rule == "alignment-w4":
        if target_key[1] <= 4:
            return "unavailable", None, None
        return (
            "alignment-window",
            {"season": target_key[0], "week": target_key[1] - 4},
            {"season": target_key[0], "week": target_key[1] - 1},
        )
    if rule == "prior-season-n-minus-one":
        prior = {"season": target_key[0] - 1, "week": None}
        return "prior-season-full", prior, prior
    if rule in {
        "prior-regular-game-window",
        "prior-eight-common-defense-games",
        "prior-eight-games",
        "prior-six-games",
    }:
        keys = sorted({
            _key(row, label="period row")
            for row in selected_rows
            if "season" in row and "week" in row
        })
        if not keys:
            previous = _previous_period(target_key)
            return "prior-game-window", previous, previous
        return (
            "prior-game-window",
            {"season": keys[0][0], "week": keys[0][1]},
            {"season": keys[-1][0], "week": keys[-1][1]},
        )
    _fail(f"unknown role period rule {rule!r}")


def _select_period_rows(
    *,
    role: str,
    requirement: Mapping[str, object],
    semantic: Mapping[str, object],
    catalog: Mapping[str, object],
    slices: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    slice_kind = str(requirement["slice_kind"])
    rule = str(requirement["period_rule"])
    target_key = (
        int(catalog["slate"]["season"]), int(catalog["slate"]["week"])
    )
    schedule_games, schedule_by_team = _schedule_indexes(
        slices["schedule-games"]
    )
    lock_time = _parse_utc(
        semantic["lock_time_utc"], label="period target lock"
    )
    raw_rows = [dict(row) for row in slices[slice_kind]]
    if rule == "target-slate":
        rows = [dict(row) for row in semantic["target_games"]]
    elif rule == "legacy-depth":
        if target_key[0] > 2024:
            rows = []
        else:
            player_ids = {
                str(player["id"]) for player in catalog["players"]
                if _family(player["pos"]) is not None
            }
            rows = [
                row for row in raw_rows
                if row.get("season") == target_key[0]
                and row.get("week") == target_key[1]
                and row.get("gsis_id") in player_ids
            ]
    elif rule == "snapshot-depth":
        if target_key[0] != 2025:
            rows = []
        else:
            player_team = {
                str(player["id"]): str(player["team"])
                for player in catalog["players"] if _family(player["pos"]) is not None
            }
            game_day_by_team: dict[str, date] = {}
            for game in semantic["target_games"]:
                game_day = datetime.strptime(
                    str(game["gameday"]), "%Y-%m-%d"
                ).date()
                game_day_by_team[str(game["home_team"])] = game_day
                game_day_by_team[str(game["away_team"])] = game_day
            rows = [
                row for row in raw_rows
                if row.get("gsis_id") in player_team
                and row.get("team") == player_team[str(row.get("gsis_id"))]
                and _snapshot_date(row.get("dt")) is not None
                and _snapshot_date(row.get("dt"))
                < game_day_by_team[str(row.get("team"))]
            ]
    elif rule == "alignment-w4":
        rows = [] if target_key[1] <= 4 else [
            row for row in raw_rows
            if row.get("season") == target_key[0]
            and row.get("target_week") == target_key[1]
        ]
    elif rule == "prior-season-n-minus-one":
        rows = [
            row for row in raw_rows if row.get("season") == target_key[0] - 1
        ]
    else:
        family = next(
            str(definition["family"])
            for definition in source.frozen_role_registry_v2()["roles"]
            if definition["role"] == role
        )
        defenses = {
            str(player["opp"])
            for player in catalog["players"]
            if _family(player["pos"]) == family
        }
        schedule_rows = [
            row for row in schedule_games if row["_kickoff"] < lock_time
        ]
        limit = 6 if rule == "prior-six-games" or role == "qb-secondary" else 8
        selected_games: list[dict[str, object]] = []
        for defense in sorted(defenses):
            defense_games = [
                row for row in schedule_rows
                if defense in {str(row["home_team"]), str(row["away_team"])}
            ]
            defense_games.sort(
                key=lambda row: (row["_kickoff"], str(row["game_id"]))
            )
            selected_games.extend(defense_games[-limit:])
        selected_game_ids = {
            str(row["game_id"]) for row in selected_games
        }
        selected_game_keys = {
            _key(row, label="selected period game") for row in selected_games
        }
        role_history_required = role in {
            "receiver-role-concession",
            "rb-rushing-concession",
            "rb-receiving-concession",
        }
        target_player_ids = {
            str(player["id"])
            for player in catalog["players"]
            if role_history_required and _family(player["pos"]) == family
        }
        cutoff_kickoffs_by_player: dict[str, set[datetime]] = defaultdict(set)
        for row in (
            slices["weekly-player-stats"] if role_history_required else ()
        ):
            if "season" not in row or "week" not in row:
                continue
            row_key = _key(row, label="role source row")
            row_team = str(row.get("team"))
            game = schedule_by_team.get((row_key[0], row_key[1], row_team))
            if (
                game is not None
                and str(game["game_id"]) in selected_game_ids
                and str(row.get("opponent_team")) in defenses
            ):
                cutoff_kickoffs_by_player[str(row["player_id"])].add(
                    game["_kickoff"]
                )
        for player_id in target_player_ids:
            cutoff_kickoffs_by_player[player_id].add(lock_time)

        weekly_event: dict[tuple[str, tuple[int, int]], datetime] = {}
        for row in slices["weekly-player-stats"]:
            if "season" not in row or "week" not in row:
                continue
            row_key = _key(row, label="period weekly kickoff")
            game = schedule_by_team.get(
                (row_key[0], row_key[1], str(row.get("team")))
            )
            if game is not None:
                weekly_event[(str(row.get("player_id")), row_key)] = game[
                    "_kickoff"
                ]

        def last_four_identities(
            candidates: Sequence[Mapping[str, object]],
            *, id_field: str,
        ) -> set[bytes]:
            retained: set[bytes] = set()
            for player_id, cutoff_kickoffs in cutoff_kickoffs_by_player.items():
                player_rows: list[tuple[datetime, Mapping[str, object]]] = []
                for row in candidates:
                    if (
                        str(row.get(id_field)) != player_id
                        or "season" not in row
                        or "week" not in row
                    ):
                        continue
                    row_key = _key(row, label="role history")
                    kickoff = weekly_event.get((player_id, row_key))
                    if kickoff is not None:
                        player_rows.append((kickoff, row))
                player_rows.sort(
                    key=lambda value: (
                        value[0], source.canonical_json_bytes(value[1])
                    )
                )
                for cutoff in cutoff_kickoffs:
                    earlier = [row for kickoff, row in player_rows if kickoff < cutoff]
                    retained.update(
                        source.canonical_json_bytes(row) for row in earlier[-4:]
                    )
            return retained

        weekly_history = last_four_identities(
            slices["weekly-player-stats"], id_field="player_id"
        )
        route_history = last_four_identities(
            slices["fp-route-share"], id_field="gsis_id"
        )
        if slice_kind == "schedule-games":
            history_keys = {
                _key(row, label="weekly history row")
                for row in slices["weekly-player-stats"]
                if source.canonical_json_bytes(row) in weekly_history
            }
            rows = [
                {key: value for key, value in row.items() if not key.startswith("_")}
                for row in schedule_rows
                if (
                    str(row["game_id"]) in selected_game_ids
                    and bool(
                        {str(row["home_team"]), str(row["away_team"])} & defenses
                    )
                )
                or _key(row, label="period history schedule row") in history_keys
            ]
        elif slice_kind == "weekly-player-stats":
            rows = [
                row for row in raw_rows
                if source.canonical_json_bytes(row) in weekly_history
                or (
                    "season" in row and "week" in row
                    and _key(row, label="prior weekly row") in selected_game_keys
                    and str(row.get("opponent_team")) in defenses
                )
            ]
        elif slice_kind == "fp-route-share":
            rows = [
                row for row in raw_rows
                if source.canonical_json_bytes(row) in route_history
            ]
        else:
            rows = []
            for row in raw_rows:
                if "season" not in row or "week" not in row:
                    continue
                row_key = _key(row, label="prior period row")
                if row_key not in selected_game_keys:
                    continue
                row_team = (
                    str(row.get("defense"))
                    if slice_kind == "sis-defender-alignment"
                    else str(row.get("team"))
                )
                row_game = schedule_by_team.get(
                    (row_key[0], row_key[1], row_team)
                )
                if row_game is None or row_game["_kickoff"] >= lock_time:
                    continue
                if (
                    str(row.get("opponent_team")) in defenses
                    or str(row.get("defense")) in defenses
                    or str(row.get("team")) in defenses
                    or slice_kind == "sis-defender-alignment"
                ):
                    rows.append(row)
    if rule == "target-slate":
        rows.sort(key=lambda row: str(row["game_id"]))
    else:
        rows.sort(key=source.canonical_json_bytes)
    if len(rows) != len({source.canonical_json_bytes(row) for row in rows}):
        _fail("derived role period repeats an exact source row")
    return rows


def _row_event_kickoffs(
    *,
    slice_kind: str,
    rows: Sequence[Mapping[str, object]],
    slices: Mapping[str, Sequence[Mapping[str, object]]],
    semantic: Mapping[str, object],
) -> list[str | None]:
    """Derive one exact schedule kickoff (or explicit null) per source row."""
    games, by_team = _schedule_indexes(slices["schedule-games"])
    by_game_id = {str(game["game_id"]): game for game in games}
    target_by_team: dict[str, Mapping[str, object]] = {}
    for game_value in semantic["target_games"]:
        game = by_game_id[str(game_value["game_id"])]
        target_by_team[str(game["home_team"])] = game
        target_by_team[str(game["away_team"])] = game
    weekly_team: dict[tuple[str, tuple[int, int]], str] = {}
    for raw in slices["weekly-player-stats"]:
        row = _mapping(raw, label="event-binding weekly row")
        if "season" not in row or "week" not in row:
            continue
        identity = (
            str(row.get("player_id")),
            _key(row, label="event-binding weekly row"),
        )
        team = str(row.get("team"))
        if identity in weekly_team and weekly_team[identity] != team:
            _fail("event binding sees one player/week on multiple teams")
        weekly_team[identity] = team

    result: list[str | None] = []
    for raw in rows:
        row = _mapping(raw, label=f"{slice_kind} event-binding row")
        game: Mapping[str, object] | None = None
        if slice_kind == "schedule-games":
            game = by_game_id.get(str(row.get("game_id")))
        elif slice_kind in {
            "weekly-player-stats", "pfr-pass-rush", "pfr-secondary",
            "pfr-snap-positions", "sis-run-context",
        }:
            key = _key(row, label=f"{slice_kind} event-binding row")
            game = by_team.get((key[0], key[1], str(row.get("team"))))
        elif slice_kind == "sis-defender-alignment":
            key = _key(row, label="SIS defender event-binding row")
            game = by_team.get((key[0], key[1], str(row.get("defense"))))
        elif slice_kind == "legacy-depth":
            key = _key(row, label="legacy depth event-binding row")
            game = by_team.get((key[0], key[1], str(row.get("club_code"))))
        elif slice_kind == "snapshot-depth":
            game = target_by_team.get(str(row.get("team")))
        elif slice_kind == "fp-route-share":
            key = _key(row, label="FP route event-binding row")
            team = weekly_team.get((str(row.get("gsis_id")), key))
            if team is not None:
                game = by_team.get((key[0], key[1], team))
        result.append(None if game is None else str(game["kickoff_time_utc"]))
    return result


def _role_and_slice_artifacts(
    *,
    producer_namespace: str,
    catalog: Mapping[str, object],
    semantic: Mapping[str, object],
    slices: Mapping[str, Sequence[Mapping[str, object]]],
    upstream_source_release: Mapping[str, object],
    identity_lookup: IdentityLookup | None,
    body_materializer: BodyMaterializer | None = None,
    read_exact: ExactReader | None = None,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    ordinal = int(catalog["source_task_ordinal"])
    slate_id = str(catalog["slate"]["slate_id"])
    prefix = (
        f"{producer_namespace}source-task-{ordinal:02d}-{slate_id}/producer/"
    )
    target_key = (
        int(catalog["slate"]["season"]), int(catalog["slate"]["week"])
    )
    pack_by_id = {
        str(pack["pack_id"]): pack for pack in upstream_source_release["packs"]
    }
    source_slices: list[dict[str, object]] = []
    role_entries: list[dict[str, object]] = []
    role_row_objects: list[dict[str, object]] = []
    annotation_by_id = {
        str(row["gsis_id"]): dict(row) for row in semantic["annotation_rows"]
    }
    component_bounds: dict[str, list[dict[str, object]]] = {}
    populations = {
        family: sum(_family(player["pos"]) == family for player in catalog["players"])
        for family in FAMILY_COMPONENTS
    }
    for definition_value in source.frozen_role_registry_v2()["roles"]:
        definition = _mapping(definition_value, label="role definition")
        role = str(definition["role"])
        periods: list[dict[str, object]] = []
        for period_ordinal, requirement_value in enumerate(
            definition["period_requirements"]
        ):
            requirement = _mapping(
                requirement_value, label="role period requirement"
            )
            selected = _select_period_rows(
                role=role,
                requirement=requirement,
                semantic=semantic,
                catalog=catalog,
                slices=slices,
            )
            slice_uri = (
                f"{prefix}slices/{int(definition['ordinal']):02d}-"
                f"{period_ordinal:02d}-{requirement['slice_kind']}.json"
            )
            slice_identity = _identity_for_body(
                body=selected,
                uri=slice_uri,
                identity_lookup=identity_lookup,
                body_materializer=body_materializer,
                read_exact=read_exact,
                label=f"{role} period {period_ordinal} identity",
            )
            period_kind, period_min, period_max = _period_shape(
                rule=str(requirement["period_rule"]),
                target_key=target_key,
                selected_rows=selected,
            )
            event_kickoffs = _row_event_kickoffs(
                slice_kind=str(requirement["slice_kind"]),
                rows=selected,
                slices=slices,
                semantic=semantic,
            )
            period = source.build_historical_source_period_v1(
                pack_id=str(requirement["pack_id"]),
                slice_kind=str(requirement["slice_kind"]),
                period_kind=period_kind,
                source_period_min=period_min,
                source_period_max=period_max,
                upstream_pack_rows_identity=pack_by_id[
                    str(requirement["pack_id"])
                ]["exact_rows_identity"],
                exact_slice_identity=slice_identity,
                slice_row_count=len(selected),
                slice_rows_sha256=str(slice_identity["sha256"]),
                row_event_kickoff_times_utc=event_kickoffs,
            )
            periods.append(period)
            source_slices.append({
                "role": role,
                "period_ordinal": period_ordinal,
                "pack_id": requirement["pack_id"],
                "slice_kind": requirement["slice_kind"],
                "rows": selected,
                "row_count": len(selected),
                "rows_sha256": source.canonical_sha256(selected),
                "row_event_kickoff_times_utc": event_kickoffs,
                "row_event_kickoff_manifest_sha256": source.canonical_sha256(
                    event_kickoffs
                ),
                "exact_slice_identity": slice_identity,
                "historical_source_period_sha256": period[
                    "historical_source_period_sha256"
                ],
            })
        if definition["population_role"] == "component":
            family = str(definition["family"])
            component = str(definition["component"])
            retained_rows = []
            for player in catalog["players"]:
                if _family(player["pos"]) != family:
                    continue
                annotation = annotation_by_id[str(player["id"])]
                raw_value = annotation["raw_component_values"][component]
                percentile = annotation["component_values"][component]
                supported = percentile is not None
                retained_rows.append({
                    "gsis_id": str(player["id"]),
                    "component": component,
                    "raw_value": raw_value,
                    "percentile": percentile,
                    "supported": supported,
                    "observed_game_count": annotation[
                        "component_observed_game_counts"
                    ][component],
                    "missingness_reason": (
                        annotation["component_missingness_reasons"][component]
                    ),
                })
            retained_rows.sort(key=lambda row: str(row["gsis_id"]))
            expected = populations[family]
            supported_count = sum(row["supported"] is True for row in retained_rows)
            source_unavailable = sum(
                row["missingness_reason"] == "source_unavailable"
                for row in retained_rows
            )
            missingness = {
                "identity_unresolved": 0,
                "insufficient_history": expected - supported_count - source_unavailable,
                "other_registered": 0,
                "source_unavailable": source_unavailable,
                "unknown_depth": 0,
            }
            component_bounds[component] = [{
                "period_kind": period["period_kind"],
                "source_period_min": period["source_period_min"],
                "source_period_max": period["source_period_max"],
                "minimum_source_event_time_utc": period[
                    "minimum_source_event_time_utc"
                ],
                "maximum_source_event_time_utc": period[
                    "maximum_source_event_time_utc"
                ],
                "row_event_kickoff_manifest_sha256": period[
                    "row_event_kickoff_manifest_sha256"
                ],
                "exact_slice_identity": period["exact_slice_identity"],
                "historical_source_period_sha256": period[
                    "historical_source_period_sha256"
                ],
            } for period in periods]
        elif role == "schedule-spine":
            retained_rows = [{
                "game_id": str(game["game_id"]),
                "canonical_game_key": "|".join(sorted((
                    str(game["home_team"]), str(game["away_team"]),
                ))),
                "kickoff_time_utc": str(game["kickoff_time_utc"]),
            } for game in semantic["target_games"]]
            expected = len(retained_rows)
            supported_count = expected
            missingness = {
                "identity_unresolved": 0, "insufficient_history": 0,
                "other_registered": 0, "source_unavailable": 0,
                "unknown_depth": 0,
            }
        else:
            retained_rows = [dict(row) for row in semantic["qb_depth_census"]["rows"]]
            expected = len(retained_rows)
            supported_count = sum(row["qb_depth1"] is not None for row in retained_rows)
            missingness = {
                "identity_unresolved": 0, "insufficient_history": 0,
                "other_registered": 0, "source_unavailable": 0,
                "unknown_depth": expected - supported_count,
            }
        row_object = {
            "role": role,
            "rows": retained_rows,
            "row_count": len(retained_rows),
            "rows_sha256": source.canonical_sha256(retained_rows),
        }
        role_row_objects.append(row_object)
        role_entries.append(source.build_role_entry_v1(
            role=role,
            source_periods=periods,
            expected_population_count=expected,
            retained_rows_sha256=row_object["rows_sha256"],
            retained_row_count=len(retained_rows),
            supported_cell_count=supported_count,
            missingness_counts=missingness,
        ))
    final_annotations: list[dict[str, object]] = []
    for row_value in semantic["annotation_rows"]:
        row = dict(row_value)
        row["component_source_bounds"] = {
            component: component_bounds[component]
            for component in FAMILY_COMPONENTS[str(row["family"])]
        }
        final_annotations.append(row)
    return role_entries, role_row_objects, source_slices, final_annotations


def _namespace(value: object, *, label: str) -> str:
    text = _text(value, label=label)
    if (
        not text.startswith("gs://")
        or not text.endswith("/")
        or ".." in text
        or "//" in text[5:]
    ):
        _fail(f"{label} must be a canonical GCS prefix")
    return text


def _admission_support(
    *,
    producer_namespace: str,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    annotation_rows: Sequence[Mapping[str, object]],
    qb_depth_census: Mapping[str, object],
    identity_lookup: IdentityLookup | None,
    body_materializer: BodyMaterializer | None = None,
    read_exact: ExactReader | None = None,
) -> dict[str, object]:
    ordinal = int(catalog["source_task_ordinal"])
    binding = source.build_candidate_support_binding_v1(
        source_task_ordinal=ordinal,
        catalog_identity=catalog_identity,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
    )
    candidate_artifact = accepted_candidate_release["entries"][ordinal][
        "candidate_artifact"
    ]
    annotation_by_id = {
        str(row["gsis_id"]): row for row in annotation_rows
    }
    depth_by_id = {
        str(row["player_id"]): row["qb_depth1"]
        for row in qb_depth_census["rows"]
    }
    positions = {
        str(player["id"]): str(player["pos"])
        for player in catalog["players"]
    }
    rows: list[dict[str, object]] = []
    for candidate in candidate_artifact["rows"]:
        player_ids = [str(value) for value in candidate["player_ids"]]
        skill_ids = [
            player_id for player_id in player_ids
            if positions[player_id] in POSITION_FAMILY
        ]
        qb_ids = [
            player_id for player_id in skill_ids if positions[player_id] == "QB"
        ]
        if len(skill_ids) != 8 or len(qb_ids) != 1:
            _fail("candidate support roster shape differs from eight skill players")
        supported = sum(
            annotation_by_id[player_id]["matchup_edge_score"] is not None
            for player_id in skill_ids
        )
        rows.append({
            "candidate_id": str(candidate["candidate_id"]),
            "qb_player_id": qb_ids[0],
            "qb_depth_true": depth_by_id[qb_ids[0]] is True,
            "supported_matchup_player_count": supported,
            "annotation_completeness": supported / len(skill_ids),
        })
    support_object = source.build_candidate_support_rows_v1(
        candidate_support_binding=binding,
        structural_catalog=catalog,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        rows=rows,
    )
    slate_id = str(catalog["slate"]["slate_id"])
    identity = _identity_for_body(
        body=support_object,
        uri=(
            f"{producer_namespace}source-task-{ordinal:02d}-{slate_id}/"
            "producer/candidate-support-rows.json"
        ),
        identity_lookup=identity_lookup,
        body_materializer=body_materializer,
        read_exact=read_exact,
        label=f"candidate support rows {ordinal}",
    )
    return source.build_admission_support_census_v1(
        candidate_support_binding=binding,
        structural_catalog=catalog,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        candidate_support_rows=rows,
        candidate_support_rows_identity=identity,
    )


def _derive_component_bundle_candidate(
    *,
    producer_id: str,
    producer_namespace: str,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    upstream_source_release_identity: Mapping[str, object],
    semantic: Mapping[str, object],
    slices: Mapping[str, Sequence[Mapping[str, object]]],
    identity_lookup: IdentityLookup | None,
    body_materializer: BodyMaterializer | None = None,
    read_exact: ExactReader | None = None,
) -> dict[str, object]:
    """Run every post-reducer derivation for one exact input body."""
    ordinal = int(catalog["source_task_ordinal"])
    slate_id = str(catalog["slate"]["slate_id"])
    schedule_slice_uri = (
        f"{producer_namespace}source-task-{ordinal:02d}-{slate_id}/producer/"
        "slices/00-00-schedule-games.json"
    )
    schedule_identity = _identity_for_body(
        body=semantic["target_games"],
        uri=schedule_slice_uri,
        identity_lookup=identity_lookup,
        body_materializer=body_materializer,
        read_exact=read_exact,
        label=f"schedule-spine slice {ordinal}",
    )
    target_spine = source.build_target_spine_v1(
        structural_catalog=catalog,
        catalog_identity=catalog_identity,
        upstream_source_release=upstream_source_release,
        upstream_pack_row_objects=upstream_pack_row_objects,
        schedule_slice_identity=schedule_identity,
        games=semantic["target_games"],
    )
    role_entries, role_rows, source_slices, annotations = (
        _role_and_slice_artifacts(
            producer_namespace=producer_namespace,
            catalog=catalog,
            semantic=semantic,
            slices=slices,
            upstream_source_release=upstream_source_release,
            identity_lookup=identity_lookup,
            body_materializer=body_materializer,
            read_exact=read_exact,
        )
    )
    bounded_semantic = dict(semantic)
    bounded_semantic["annotation_rows"] = annotations
    bounded_semantic["annotation_rows_sha256"] = source.canonical_sha256(
        annotations
    )
    admission = _admission_support(
        producer_namespace=producer_namespace,
        catalog=catalog,
        catalog_identity=catalog_identity,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        annotation_rows=annotations,
        qb_depth_census=semantic["qb_depth_census"],
        identity_lookup=identity_lookup,
        body_materializer=body_materializer,
        read_exact=read_exact,
    )
    bundle = build_component_input_bundle_v1(
        producer_id=producer_id,
        catalog=catalog,
        catalog_identity=catalog_identity,
        catalog_release_identity=catalog_release_identity,
        catalog_replay_receipt_identity=catalog_replay_receipt_identity,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        upstream_source_release_identity=upstream_source_release_identity,
        semantic_output=bounded_semantic,
        target_spine=target_spine,
        source_slices=source_slices,
        role_entries=role_entries,
        role_row_objects=role_rows,
        annotation_rows=annotations,
        qb_depth_census=semantic["qb_depth_census"],
        admission_support_census=admission,
    )
    validate_component_input_bundle_v1(bundle, expected_catalog=catalog)
    return {
        "target_spine": target_spine,
        "role_entries": role_entries,
        "role_row_objects": role_rows,
        "source_slices": source_slices,
        "annotation_rows": annotations,
        "qb_depth_census": semantic["qb_depth_census"],
        "admission_support_census": admission,
        "input_bundle": bundle,
    }


def _with_self_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    if field in body:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(body)
    result[field] = source.canonical_sha256(result)
    return result


def build_component_input_bundle_v1(
    *,
    producer_id: str,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    semantic_output: Mapping[str, object],
    target_spine: Mapping[str, object],
    source_slices: Sequence[Mapping[str, object]],
    role_entries: Sequence[Mapping[str, object]],
    role_row_objects: Sequence[Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    qb_depth_census: Mapping[str, object],
    admission_support_census: Mapping[str, object],
) -> dict[str, object]:
    """Build the exact, embedded per-slate producer bundle candidate."""
    annotation_list = [dict(row) for row in annotation_rows]
    role_list = [dict(row) for row in role_entries]
    role_rows = [dict(row) for row in role_row_objects]
    slice_list = [dict(row) for row in source_slices]
    semantic = dict(semantic_output)
    body: dict[str, object] = {
        "schema_version": PRODUCER_INPUT_BUNDLE_SCHEMA,
        "producer_id": _identifier(producer_id, label="producer ID"),
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "lock_time_utc": target_spine["lock_time_utc"],
        "catalog_identity": source.normalize_object_identity_v2(
            catalog_identity, label="bundle catalog"
        ),
        "catalog_release_identity": source.normalize_object_identity_v2(
            catalog_release_identity, label="bundle catalog release"
        ),
        "catalog_replay_receipt_identity": source.normalize_object_identity_v2(
            catalog_replay_receipt_identity, label="bundle catalog replay"
        ),
        "accepted_candidate_release_identity": source.normalize_object_identity_v2(
            accepted_candidate_release_identity,
            label="bundle accepted candidate release",
        ),
        "upstream_source_release_identity": source.normalize_object_identity_v2(
            upstream_source_release_identity, label="bundle upstream release"
        ),
        "family_registry": source.frozen_family_registry_v1(),
        "family_registry_sha256": source.frozen_family_registry_v1()[
            "family_registry_sha256"
        ],
        "semantic_output": semantic,
        "semantic_output_sha256": source.canonical_sha256(semantic),
        "target_spine": dict(target_spine),
        "target_spine_sha256": target_spine["target_spine_sha256"],
        "source_slices": slice_list,
        "source_slice_manifest_sha256": source.canonical_sha256(slice_list),
        "role_entries": role_list,
        "role_entry_manifest_sha256": source.canonical_sha256(role_list),
        "role_row_objects": role_rows,
        "role_row_manifest_sha256": source.canonical_sha256(role_rows),
        "annotation_rows": annotation_list,
        "annotation_row_count": len(annotation_list),
        "annotation_rows_sha256": source.canonical_sha256(annotation_list),
        "qb_depth_census": dict(qb_depth_census),
        "admission_support_census": dict(admission_support_census),
        **_policy(),
    }
    return _with_self_hash(body, field="input_bundle_sha256")


def validate_component_input_bundle_v1(
    value: object,
    *,
    expected_catalog: Mapping[str, object],
    expected_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="component input bundle")
    _exact_keys(
        item,
        frozenset({
            "schema_version", "producer_id", "source_task_ordinal",
            "task_id", "slate", "lock_time_utc", "catalog_identity",
            "catalog_release_identity", "catalog_replay_receipt_identity",
            "accepted_candidate_release_identity",
            "upstream_source_release_identity", "family_registry",
            "family_registry_sha256", "semantic_output",
            "semantic_output_sha256", "target_spine",
            "target_spine_sha256", "source_slices",
            "source_slice_manifest_sha256", "role_entries",
            "role_entry_manifest_sha256", "role_row_objects",
            "role_row_manifest_sha256", "annotation_rows",
            "annotation_row_count", "annotation_rows_sha256",
            "qb_depth_census", "admission_support_census",
            "outcome_columns_read", "uses_realized_outcomes",
            *source.FALSE_AUTHORITY_FIELDS, "input_bundle_sha256",
        }),
        label="component input bundle",
    )
    _reject_outcome_fields(item, label="component input bundle")
    retained = item.get("input_bundle_sha256")
    if type(retained) is not str or _SHA256.fullmatch(retained) is None:
        _fail("component input bundle self-hash is invalid")
    body = dict(item)
    del body["input_bundle_sha256"]
    if source.canonical_sha256(body) != retained:
        _fail("component input bundle self-hash differs")
    if item.get("schema_version") != PRODUCER_INPUT_BUNDLE_SCHEMA:
        _fail("component input bundle schema differs")
    _identifier(item.get("producer_id"), label="bundle producer ID")
    catalog = source.validate_structural_catalog_v2(expected_catalog)
    expected_ids = sorted(
        str(player["id"])
        for player in catalog["players"] if _family(player["pos"]) is not None
    )
    annotations = _sequence(item.get("annotation_rows"), label="bundle annotations")
    family_registry = source.validate_family_registry_v1(
        item.get("family_registry")
    )
    semantic = _mapping(item.get("semantic_output"), label="bundle semantic output")
    _exact_keys(
        semantic,
        frozenset({
            "source_task_ordinal", "task_id", "slate", "lock_time_utc",
            "target_games", "target_roles", "qb_depth_census",
            "annotation_rows", "annotation_rows_sha256",
            "raw_component_manifest_sha256",
        }),
        label="bundle semantic output",
    )
    source_slices = _sequence(item.get("source_slices"), label="bundle source slices")
    role_entries = _sequence(item.get("role_entries"), label="bundle roles")
    role_rows = _sequence(item.get("role_row_objects"), label="bundle role rows")
    if (
        item.get("source_task_ordinal") != catalog["source_task_ordinal"]
        or item.get("task_id") != catalog["task_id"]
        or item.get("slate") != catalog["slate"]
        or item.get("annotation_row_count") != len(expected_ids)
        or item.get("family_registry_sha256")
        != family_registry["family_registry_sha256"]
        or [str(_mapping(row, label="annotation row").get("gsis_id")) for row in annotations]
        != expected_ids
        or item.get("annotation_rows_sha256")
        != source.canonical_sha256(annotations)
        or item.get("semantic_output_sha256")
        != source.canonical_sha256(semantic)
        or semantic.get("source_task_ordinal")
        != catalog["source_task_ordinal"]
        or semantic.get("task_id") != catalog["task_id"]
        or semantic.get("slate") != catalog["slate"]
        or semantic.get("lock_time_utc") != item.get("lock_time_utc")
        or semantic.get("target_games")
        != _mapping(item.get("target_spine"), label="bundle target spine").get(
            "games"
        )
        or semantic.get("qb_depth_census") != item.get("qb_depth_census")
        or semantic.get("annotation_rows") != annotations
        or semantic.get("annotation_rows_sha256")
        != source.canonical_sha256(annotations)
        or item.get("target_spine_sha256")
        != _mapping(item.get("target_spine"), label="bundle target spine").get(
            "target_spine_sha256"
        )
        or item.get("source_slice_manifest_sha256")
        != source.canonical_sha256(source_slices)
        or item.get("role_entry_manifest_sha256")
        != source.canonical_sha256(role_entries)
        or item.get("role_row_manifest_sha256")
        != source.canonical_sha256(role_rows)
    ):
        _fail("component input bundle task/universe manifests differ")
    if len(role_entries) != source.ROLE_COUNT or len(role_rows) != source.ROLE_COUNT:
        _fail("component input bundle requires exactly 12 role bodies")
    for ordinal, (entry_value, row_object_value) in enumerate(
        zip(role_entries, role_rows, strict=True)
    ):
        entry = _mapping(entry_value, label=f"bundle role[{ordinal}]")
        row_object = _mapping(
            row_object_value, label=f"bundle role rows[{ordinal}]"
        )
        rows = _sequence(row_object.get("rows"), label="bundle retained rows")
        if (
            set(row_object) != {"role", "rows", "row_count", "rows_sha256"}
            or row_object.get("role") != entry.get("role")
            or row_object.get("row_count") != len(rows)
            or row_object.get("rows_sha256") != source.canonical_sha256(rows)
            or row_object.get("rows_sha256") != entry.get("retained_rows_sha256")
        ):
            _fail("component input bundle role-row binding differs")
    normalized_annotations = source._normalize_annotation_rows_v1(
        annotations,
        catalog=catalog,
        role_entries=role_entries,
        role_row_objects=role_rows,
        qb_depth_census=_mapping(
            item.get("qb_depth_census"), label="bundle QB depth census"
        ),
    )
    if annotations != normalized_annotations:
        _fail("component input bundle annotations differ from canonical replay")
    expected_source_periods = [
        (str(entry["role"]), period_ordinal, period)
        for entry in role_entries
        for period_ordinal, period in enumerate(
            _sequence(entry["source_periods"], label="bundle role periods")
        )
    ]
    if len(source_slices) != len(expected_source_periods):
        _fail("component input source slices differ from role periods")
    slice_fields = {
        "role", "period_ordinal", "pack_id", "slice_kind", "rows",
        "row_count", "rows_sha256", "row_event_kickoff_times_utc",
        "row_event_kickoff_manifest_sha256", "exact_slice_identity",
        "historical_source_period_sha256",
    }
    for ordinal, (slice_value, expected) in enumerate(
        zip(source_slices, expected_source_periods, strict=True)
    ):
        role, period_ordinal, period_value = expected
        period = _mapping(
            period_value, label=f"bundle role period[{ordinal}]"
        )
        slice_entry = _mapping(
            slice_value, label=f"bundle source slice[{ordinal}]"
        )
        rows = _sequence(slice_entry.get("rows"), label="bundle source rows")
        event_kickoffs = _sequence(
            slice_entry.get("row_event_kickoff_times_utc"),
            label="bundle source row event kickoffs",
        )
        normalized_event_kickoffs = [
            None
            if value is None
            else _parse_utc(value, label="bundle source event kickoff").strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            for value in event_kickoffs
        ]
        identity = source.normalize_object_identity_v2(
            slice_entry.get("exact_slice_identity"),
            label=f"bundle source slice[{ordinal}] identity",
        )
        if (
            set(slice_entry) != slice_fields
            or slice_entry.get("role") != role
            or slice_entry.get("period_ordinal") != period_ordinal
            or slice_entry.get("pack_id") != period.get("pack_id")
            or slice_entry.get("slice_kind") != period.get("slice_kind")
            or slice_entry.get("row_count") != len(rows)
            or slice_entry.get("row_count") != period.get("slice_row_count")
            or slice_entry.get("rows_sha256") != source.canonical_sha256(rows)
            or slice_entry.get("rows_sha256")
            != period.get("slice_rows_sha256")
            or len(event_kickoffs) != len(rows)
            or normalized_event_kickoffs
            != period.get("row_event_kickoff_times_utc")
            or slice_entry.get("row_event_kickoff_manifest_sha256")
            != source.canonical_sha256(normalized_event_kickoffs)
            or slice_entry.get("row_event_kickoff_manifest_sha256")
            != period.get("row_event_kickoff_manifest_sha256")
            or identity != period.get("exact_slice_identity")
            or identity["sha256"] != source.canonical_sha256(rows)
            or identity["bytes"] != len(source.canonical_json_bytes(rows))
            or slice_entry.get("historical_source_period_sha256")
            != period.get("historical_source_period_sha256")
        ):
            _fail("component input bundle source slice differs from role period")
        if period.get("period_kind") == "prior-game-window" and (
            slice_entry.get("slice_kind") in {
                "schedule-games", "weekly-player-stats", "fp-route-share",
                "pfr-pass-rush", "pfr-secondary", "pfr-snap-positions",
                "sis-defender-alignment", "sis-run-context",
            }
            and (
                any(value is None for value in normalized_event_kickoffs)
                or any(
                    _parse_utc(value, label="prior-game event kickoff")
                    >= _parse_utc(item.get("lock_time_utc"), label="bundle lock")
                    for value in normalized_event_kickoffs
                    if value is not None
                )
            )
        ):
            _fail("prior-game source rows must exact-bind kickoffs before lock")
        if (
            period.get("period_kind") == "target-slate"
            and slice_entry.get("slice_kind") == "schedule-games"
            and (
                not normalized_event_kickoffs
                or any(value is None for value in normalized_event_kickoffs)
                or any(
                    _parse_utc(value, label="target schedule event kickoff")
                    < _parse_utc(item.get("lock_time_utc"), label="bundle lock")
                    for value in normalized_event_kickoffs
                    if value is not None
                )
                or item.get("lock_time_utc") not in normalized_event_kickoffs
            )
        ):
            _fail("target schedule rows must exact-bind kickoffs at/after lock")
    for field in source.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("component input bundle claims downstream authority")
    if item.get("outcome_columns_read") != [] or item.get(
        "uses_realized_outcomes"
    ) is not False:
        _fail("component input bundle reads outcomes")
    if expected_identity is not None:
        _bind_body(item, expected_identity, label="component input bundle identity")
    return item


def _validated_catalog_panel(
    *,
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    try:
        release = catalog_v1.validate_release_v1(catalog_release)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupComponentProducerV1Error(str(exc)) from exc
    release_identity = _bind_body(
        release,
        catalog_release_identity,
        label="catalog release identity",
    )
    if release_identity["uri"] != (
        f"{release['catalog_namespace']}catalog-release.json"
    ):
        _fail("catalog release URI differs from its namespace")
    raw_catalogs = _sequence(
        structural_catalogs, label="structural catalog panel"
    )
    if len(raw_catalogs) != source.TASK_COUNT:
        _fail("structural catalog panel requires exactly 54 catalogs")
    catalogs: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for ordinal, raw in enumerate(raw_catalogs):
        catalog = source.validate_structural_catalog_v2(raw)
        entry = _mapping(
            release["entries"][ordinal], label=f"catalog release entry[{ordinal}]"
        )
        identity = _bind_body(
            catalog,
            entry["catalog_identity"],
            label=f"structural catalog identity[{ordinal}]",
        )
        expected_lane = catalog_v1.expected_lane_for_source_task(ordinal)
        if (
            catalog["source_task_ordinal"] != ordinal
            or entry["source_task_ordinal"] != ordinal
            or entry["task_id"] != catalog["task_id"]
            or entry["slate"] != catalog["slate"]
            or entry["task_ordinal"] != catalog["task_ordinal"]
            or any(entry[field] != value for field, value in expected_lane.items())
            or entry["source_catalog_sha256"]
            != catalog["source_catalog_sha256"]
            or entry["player_count"] != catalog["player_count"]
            or entry["ordered_player_ids_sha256"]
            != catalog["ordered_player_ids_sha256"]
        ):
            _fail("structural catalog panel differs from its fixed-G0 release")
        catalogs.append(catalog)
        identities.append(identity)
    return release, release_identity, catalogs, identities


def _validate_candidate_panel_against_catalogs(
    *,
    candidate_release: Mapping[str, object],
    candidate_namespace: str,
    catalogs: Sequence[Mapping[str, object]],
    catalog_identities: Sequence[Mapping[str, object]],
) -> None:
    entries = _sequence(
        candidate_release["entries"], label="accepted candidate entries"
    )
    if len(entries) != source.TASK_COUNT:
        _fail("accepted candidate release requires exactly 54 entries")
    for ordinal, entry_value in enumerate(entries):
        entry = _mapping(
            entry_value, label=f"accepted candidate entry[{ordinal}]"
        )
        catalog = catalogs[ordinal]
        artifact = _mapping(
            entry["candidate_artifact"],
            label=f"accepted candidate artifact[{ordinal}]",
        )
        artifact_identity = source.normalize_object_identity_v2(
            entry["candidate_artifact_identity"],
            label=f"accepted candidate artifact identity[{ordinal}]",
        )
        expected_uri = (
            f"{candidate_namespace}source-task-{ordinal:02d}-"
            f"{catalog['slate']['slate_id']}/accepted-candidates.json"
        )
        if (
            entry["catalog_identity"] != catalog_identities[ordinal]
            or artifact_identity["uri"] != expected_uri
        ):
            _fail("accepted candidate entry differs from its catalog/capture law")
        positions = {
            str(player["id"]): str(player["pos"])
            for player in catalog["players"]
        }
        salaries = {
            str(player["id"]): int(player["salary"])
            for player in catalog["players"]
        }
        roster_hashes: set[str] = set()
        for row_value in _sequence(
            artifact["rows"], label=f"accepted candidate rows[{ordinal}]"
        ):
            row = _mapping(row_value, label="accepted candidate row")
            player_ids = [
                str(value)
                for value in _sequence(
                    row["player_ids"], label="accepted candidate player IDs"
                )
            ]
            roster_hash = source.canonical_sha256(sorted(player_ids))
            if roster_hash in roster_hashes:
                _fail("accepted candidate artifact repeats a player roster")
            roster_hashes.add(roster_hash)
            if any(player_id not in positions for player_id in player_ids):
                _fail("accepted candidate contains a non-catalog player")
            roster_positions = [positions[player_id] for player_id in player_ids]
            if (
                len(player_ids) != 9
                or len(player_ids) != len(set(player_ids))
                or sum(position == "QB" for position in roster_positions) != 1
                or sum(
                    position in POSITION_FAMILY for position in roster_positions
                ) != 8
                or sum(position == "DST" for position in roster_positions) != 1
                or not 2 <= sum(
                    position == "RB" for position in roster_positions
                ) <= 3
                or not 3 <= sum(
                    position == "WR" for position in roster_positions
                ) <= 4
                or not 1 <= sum(
                    position == "TE" for position in roster_positions
                ) <= 2
                or sum(salaries[player_id] for player_id in player_ids) > 50_000
            ):
                _fail("accepted candidate roster shape differs from DK classic")


def produce_all_54_component_panel_v1(
    *,
    producer_id: str,
    producer_release_id: str,
    producer_namespace: str,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_code_identity: Mapping[str, object],
    identity_lookup: IdentityLookup | None = None,
    body_materializer: BodyMaterializer | None = None,
    read_exact: ExactReader | None = None,
) -> dict[str, object]:
    """Produce and cross-validate all 54 outcome-blind component bundles.

    Exactly one identity mode is admitted.  The original offline
    ``identity_lookup`` receives only URI/hash/size.  The explicit capture
    ``body_materializer`` receives URI/canonical bytes and requires
    ``read_exact``; every leaf, bundle, receipt, and the root-last producer
    release is byte-reopened before use or return.  A capture layer owns the
    storage implementation and create-once collision law.

    The accepted candidate release is an injected, body-bound predecessor;
    this reducer never mints accepted-v12 rosters from caller-shaped rows.
    """
    if (identity_lookup is None) == (body_materializer is None):
        _fail(
            "component panel requires exactly one identity lookup or "
            "body materializer"
        )
    if body_materializer is not None and read_exact is None:
        _fail("component panel materialization requires an exact reader")
    if body_materializer is None and read_exact is not None:
        _fail("hash-only component production cannot accept an exact reader")
    normalized_producer_id = _identifier(producer_id, label="producer ID")
    producer_prefix = _namespace(
        producer_namespace, label="producer namespace"
    )
    candidate_release = source.validate_accepted_candidate_release_v1(
        accepted_candidate_release
    )
    candidate_release_identity = _bind_body(
        candidate_release,
        accepted_candidate_release_identity,
        label="accepted candidate release identity",
    )
    candidate_prefix = _namespace(
        candidate_release["namespace"], label="candidate namespace"
    )
    if candidate_release_identity["uri"] != (
        f"{candidate_prefix}accepted-candidate-release.json"
    ):
        _fail("accepted candidate release URI differs from its namespace")
    if (
        producer_prefix == candidate_prefix
        or producer_prefix.startswith(candidate_prefix)
        or candidate_prefix.startswith(producer_prefix)
    ):
        _fail("producer and candidate namespaces must be disjoint")
    release, release_identity, catalogs, catalog_identities = (
        _validated_catalog_panel(
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            structural_catalogs=structural_catalogs,
        )
    )
    replay_receipt, replay_identity = _validate_fixed_g0_replay(
        replay_receipt=fixed_g0_replay_receipt,
        replay_receipt_identity=fixed_g0_replay_receipt_identity,
        catalog_release=release,
        catalog_release_identity=release_identity,
    )
    _validate_candidate_panel_against_catalogs(
        candidate_release=candidate_release,
        candidate_namespace=candidate_prefix,
        catalogs=catalogs,
        catalog_identities=catalog_identities,
    )
    upstream = source.validate_upstream_release_v1(
        upstream_source_release,
        pack_row_objects=upstream_pack_row_objects,
    )
    upstream_identity = _bind_body(
        upstream,
        upstream_source_release_identity,
        label="upstream source release identity",
    )
    if upstream_identity["uri"] != (
        f"{upstream['namespace']}upstream-release.json"
    ):
        _fail("upstream source release URI differs from its namespace")
    code = source.normalize_code_identity_v2(
        producer_code_identity,
        expected_module_path=PRODUCER_MODULE_PATH,
        label="component producer code",
    )
    full_slices = _pack_slices(upstream_pack_row_objects)
    bundles: list[dict[str, object]] = []
    bundle_identities: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []
    for ordinal, catalog in enumerate(catalogs):
        full_semantic, deleted_semantic, deleted_body, deletion = (
            _deletion_replay(
                catalog=catalog,
                pack_row_objects=upstream_pack_row_objects,
                full_slices=full_slices,
            )
        )
        full_artifacts = _derive_component_bundle_candidate(
            producer_id=normalized_producer_id,
            producer_namespace=producer_prefix,
            catalog=catalog,
            catalog_identity=catalog_identities[ordinal],
            catalog_release_identity=release_identity,
            catalog_replay_receipt_identity=replay_identity,
            accepted_candidate_release=candidate_release,
            accepted_candidate_release_identity=candidate_release_identity,
            upstream_source_release=upstream,
            upstream_pack_row_objects=upstream_pack_row_objects,
            upstream_source_release_identity=upstream_identity,
            semantic=full_semantic,
            slices=full_slices,
            identity_lookup=identity_lookup,
            body_materializer=body_materializer,
            read_exact=read_exact,
        )
        deleted_artifacts = _derive_component_bundle_candidate(
            producer_id=normalized_producer_id,
            producer_namespace=producer_prefix,
            catalog=catalog,
            catalog_identity=catalog_identities[ordinal],
            catalog_release_identity=release_identity,
            catalog_replay_receipt_identity=replay_identity,
            accepted_candidate_release=candidate_release,
            accepted_candidate_release_identity=candidate_release_identity,
            upstream_source_release=upstream,
            upstream_pack_row_objects=upstream_pack_row_objects,
            upstream_source_release_identity=upstream_identity,
            semantic=deleted_semantic,
            slices=_slices_from_deleted_body(deleted_body),
            identity_lookup=identity_lookup,
            body_materializer=body_materializer,
            read_exact=read_exact,
        )
        bundle = full_artifacts["input_bundle"]
        deleted_bundle = deleted_artifacts["input_bundle"]
        if source.canonical_json_bytes(bundle) != source.canonical_json_bytes(
            deleted_bundle
        ):
            _fail("target-or-later deletion changes the complete producer bundle")
        slate_id = str(catalog["slate"]["slate_id"])
        bundle_uri = (
            f"{producer_prefix}source-task-{ordinal:02d}-{slate_id}/"
            "producer/component-input-bundle.json"
        )
        bundle_identity = _identity_for_body(
            body=bundle,
            uri=bundle_uri,
            identity_lookup=identity_lookup,
            body_materializer=body_materializer,
            read_exact=read_exact,
            label=f"component input bundle {ordinal}",
        )
        validate_component_input_bundle_v1(
            bundle,
            expected_catalog=catalog,
            expected_identity=bundle_identity,
        )
        deletion_proof = source.build_target_or_later_deletion_proof_v1(
            source_task_ordinal=ordinal,
            target_period={
                "season": catalog["slate"]["season"],
                "week": catalog["slate"]["week"],
            },
            full_input_sha256=deletion["full_input_sha256"],
            deleted_input_sha256=deletion["deleted_input_sha256"],
            full_input_row_count=deletion["full_input_row_count"],
            deleted_input_row_count=deletion["deleted_input_row_count"],
            deleted_row_count=deletion["deleted_row_count"],
            deleted_rows_sha256=deletion["deleted_rows_sha256"],
            deleted_row_counts_by_pack=deletion[
                "deleted_row_counts_by_pack"
            ],
            deleted_row_counts_by_slice=deletion[
                "deleted_row_counts_by_slice"
            ],
            full_output_sha256=bundle_identity["sha256"],
            deleted_output_sha256=bundle_identity["sha256"],
        )
        receipt = source.build_component_producer_receipt_v1(
            producer_id=normalized_producer_id,
            structural_catalog=catalog,
            catalog_identity=catalog_identities[ordinal],
            catalog_release=release,
            catalog_release_identity=release_identity,
            catalog_replay_receipt_identity=replay_identity,
            accepted_candidate_release=candidate_release,
            accepted_candidate_release_identity=candidate_release_identity,
            upstream_source_release=upstream,
            upstream_pack_row_objects=upstream_pack_row_objects,
            upstream_source_release_identity=upstream_identity,
            producer_code_identity=code,
            target_spine=full_artifacts["target_spine"],
            role_entries=full_artifacts["role_entries"],
            annotation_row_count=len(full_artifacts["annotation_rows"]),
            annotation_rows_sha256=source.canonical_sha256(
                full_artifacts["annotation_rows"]
            ),
            input_bundle=bundle,
            input_bundle_identity=bundle_identity,
            target_or_later_deletion_proof=deletion_proof,
            qb_depth_census=full_artifacts["qb_depth_census"],
            admission_support_census=full_artifacts[
                "admission_support_census"
            ],
        )
        receipt_uri = (
            f"{producer_prefix}source-task-{ordinal:02d}-{slate_id}/"
            "producer/component-producer-receipt.json"
        )
        receipt_identity = _identity_for_body(
            body=receipt,
            uri=receipt_uri,
            identity_lookup=identity_lookup,
            body_materializer=body_materializer,
            read_exact=read_exact,
            label=f"component producer receipt {ordinal}",
        )
        source.validate_component_producer_receipt_v1(
            receipt,
            structural_catalog=catalog,
            catalog_release=release,
            accepted_candidate_release=candidate_release,
            upstream_source_release=upstream,
            upstream_pack_row_objects=upstream_pack_row_objects,
            input_bundle=bundle,
            expected_catalog_release_identity=release_identity,
            expected_catalog_replay_receipt_identity=replay_identity,
            expected_candidate_release_identity=candidate_release_identity,
            expected_upstream_source_release_identity=upstream_identity,
            expected_producer_code_identity=code,
        )
        bundles.append(bundle)
        bundle_identities.append(bundle_identity)
        receipts.append(receipt)
        receipt_identities.append(receipt_identity)
        entries.append({
            "source_task_ordinal": ordinal,
            "slate": catalog["slate"],
            "catalog_identity": catalog_identities[ordinal],
            "input_bundle_identity": bundle_identity,
            "producer_receipt_identity": receipt_identity,
            "support_preflight_passed": receipt["support_preflight_passed"],
            "qualifying_candidate_count": receipt[
                "admission_support_census"
            ]["qualifying_candidate_count"],
            "deletion_proof_sha256": deletion_proof["deletion_proof_sha256"],
        })
    support_census = source.build_all_54_support_census_v1(receipts)
    producer_release = source.build_producer_release_v1(
        release_id=producer_release_id,
        namespace=producer_prefix,
        catalog_release=release,
        catalog_release_identity=release_identity,
        catalog_replay_receipt_identity=replay_identity,
        accepted_candidate_release=candidate_release,
        accepted_candidate_release_identity=candidate_release_identity,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
        upstream_source_release_identity=upstream_identity,
        producer_code_identity=code,
        producer_receipts=receipts,
        producer_receipt_identities=receipt_identities,
        input_bundles=bundles,
        structural_catalogs=catalogs,
    )
    producer_release_identity = _identity_for_body(
        body=producer_release,
        uri=f"{producer_prefix}producer-release.json",
        identity_lookup=identity_lookup,
        body_materializer=body_materializer,
        read_exact=read_exact,
        label="component producer release identity",
    )
    source.validate_producer_release_v1(
        producer_release,
        catalog_release=release,
        accepted_candidate_release=candidate_release,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
        producer_receipts=receipts,
        input_bundles=bundles,
        structural_catalogs=catalogs,
        expected_catalog_release_identity=release_identity,
        expected_catalog_replay_receipt_identity=replay_identity,
        expected_candidate_release_identity=candidate_release_identity,
        expected_upstream_source_release_identity=upstream_identity,
        expected_producer_code_identity=code,
        expected_namespace=producer_prefix,
    )
    body: dict[str, object] = {
        "schema_version": OFFLINE_PANEL_RESULT_SCHEMA,
        "producer_id": normalized_producer_id,
        "producer_namespace": producer_prefix,
        "fixed_g0_replay_receipt": replay_receipt,
        "fixed_g0_replay_receipt_identity": replay_identity,
        "catalog_release_identity": release_identity,
        "accepted_candidate_release": candidate_release,
        "accepted_candidate_release_identity": candidate_release_identity,
        "upstream_source_release_identity": upstream_identity,
        "producer_code_identity": code,
        "family_registry": source.frozen_family_registry_v1(),
        "family_registry_sha256": source.frozen_family_registry_v1()[
            "family_registry_sha256"
        ],
        "task_count": source.TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": source.canonical_sha256(entries),
        "input_bundles": bundles,
        "input_bundle_identities": bundle_identities,
        "input_bundle_identity_manifest_sha256": source.canonical_sha256(
            bundle_identities
        ),
        "producer_receipts": receipts,
        "producer_receipt_identities": receipt_identities,
        "producer_receipt_identity_manifest_sha256": source.canonical_sha256(
            receipt_identities
        ),
        "all_54_support_census": support_census,
        "all_54_support_census_sha256": support_census[
            "all_54_support_census_sha256"
        ],
        "producer_release": producer_release,
        "producer_release_identity": producer_release_identity,
        **_policy(),
    }
    return _with_self_hash(body, field="offline_panel_result_sha256")


def produce_one_component_task_v1(
    *,
    source_task_ordinal: int,
    producer_id: str,
    producer_namespace: str,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_code_identity: Mapping[str, object],
    body_materializer: BodyMaterializer,
    read_exact: ExactReader,
) -> dict[str, object]:
    """Materialize exactly one component bundle and receipt.

    This is the bounded task-0 gate for the complete producer.  It validates
    the same 54-slate candidate/catalog predecessor lattice as the full
    producer but executes the semantic and deletion reducers for only the
    requested ordinal.  The returned bundle and receipt use the exact same
    builders, validators, URIs, and create-once/exact-reopen path as the full
    panel.  No producer-release root is minted here; the task-0 controller
    binds these two leaves in its own explicitly non-authoritative one-task
    root before exercising the source operator.
    """
    if type(source_task_ordinal) is not int or not (
        0 <= source_task_ordinal < source.TASK_COUNT
    ):
        _fail("one-task component ordinal must be in 0..53")
    if not callable(body_materializer) or not callable(read_exact):
        _fail("one-task component requires materializer and exact reader")
    normalized_producer_id = _identifier(producer_id, label="producer ID")
    producer_prefix = _namespace(
        producer_namespace, label="producer namespace"
    )
    candidate_release = source.validate_accepted_candidate_release_v1(
        accepted_candidate_release
    )
    candidate_release_identity = _bind_body(
        candidate_release,
        accepted_candidate_release_identity,
        label="accepted candidate release identity",
    )
    candidate_prefix = _namespace(
        candidate_release["namespace"], label="candidate namespace"
    )
    if candidate_release_identity["uri"] != (
        f"{candidate_prefix}accepted-candidate-release.json"
    ):
        _fail("accepted candidate release URI differs from its namespace")
    if (
        producer_prefix == candidate_prefix
        or producer_prefix.startswith(candidate_prefix)
        or candidate_prefix.startswith(producer_prefix)
    ):
        _fail("producer and candidate namespaces must be disjoint")
    release, release_identity, catalogs, catalog_identities = (
        _validated_catalog_panel(
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            structural_catalogs=structural_catalogs,
        )
    )
    replay_receipt, replay_identity = _validate_fixed_g0_replay(
        replay_receipt=fixed_g0_replay_receipt,
        replay_receipt_identity=fixed_g0_replay_receipt_identity,
        catalog_release=release,
        catalog_release_identity=release_identity,
    )
    _validate_candidate_panel_against_catalogs(
        candidate_release=candidate_release,
        candidate_namespace=candidate_prefix,
        catalogs=catalogs,
        catalog_identities=catalog_identities,
    )
    upstream = source.validate_upstream_release_v1(
        upstream_source_release,
        pack_row_objects=upstream_pack_row_objects,
    )
    upstream_identity = _bind_body(
        upstream,
        upstream_source_release_identity,
        label="upstream source release identity",
    )
    if upstream_identity["uri"] != f"{upstream['namespace']}upstream-release.json":
        _fail("upstream source release URI differs from its namespace")
    code = source.normalize_code_identity_v2(
        producer_code_identity,
        expected_module_path=PRODUCER_MODULE_PATH,
        label="component producer code",
    )
    ordinal = source_task_ordinal
    catalog = catalogs[ordinal]
    full_slices = _pack_slices(upstream_pack_row_objects)
    full_semantic, deleted_semantic, deleted_body, deletion = _deletion_replay(
        catalog=catalog,
        pack_row_objects=upstream_pack_row_objects,
        full_slices=full_slices,
    )
    full_artifacts = _derive_component_bundle_candidate(
        producer_id=normalized_producer_id,
        producer_namespace=producer_prefix,
        catalog=catalog,
        catalog_identity=catalog_identities[ordinal],
        catalog_release_identity=release_identity,
        catalog_replay_receipt_identity=replay_identity,
        accepted_candidate_release=candidate_release,
        accepted_candidate_release_identity=candidate_release_identity,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
        upstream_source_release_identity=upstream_identity,
        semantic=full_semantic,
        slices=full_slices,
        identity_lookup=None,
        body_materializer=body_materializer,
        read_exact=read_exact,
    )
    deleted_artifacts = _derive_component_bundle_candidate(
        producer_id=normalized_producer_id,
        producer_namespace=producer_prefix,
        catalog=catalog,
        catalog_identity=catalog_identities[ordinal],
        catalog_release_identity=release_identity,
        catalog_replay_receipt_identity=replay_identity,
        accepted_candidate_release=candidate_release,
        accepted_candidate_release_identity=candidate_release_identity,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
        upstream_source_release_identity=upstream_identity,
        semantic=deleted_semantic,
        slices=_slices_from_deleted_body(deleted_body),
        identity_lookup=None,
        body_materializer=body_materializer,
        read_exact=read_exact,
    )
    bundle = full_artifacts["input_bundle"]
    deleted_bundle = deleted_artifacts["input_bundle"]
    if source.canonical_json_bytes(bundle) != source.canonical_json_bytes(
        deleted_bundle
    ):
        _fail("target-or-later deletion changes the complete producer bundle")
    slate_id = str(catalog["slate"]["slate_id"])
    bundle_uri = (
        f"{producer_prefix}source-task-{ordinal:02d}-{slate_id}/"
        "producer/component-input-bundle.json"
    )
    bundle_identity = _identity_for_body(
        body=bundle,
        uri=bundle_uri,
        identity_lookup=None,
        body_materializer=body_materializer,
        read_exact=read_exact,
        label=f"component input bundle {ordinal}",
    )
    validate_component_input_bundle_v1(
        bundle,
        expected_catalog=catalog,
        expected_identity=bundle_identity,
    )
    deletion_proof = source.build_target_or_later_deletion_proof_v1(
        source_task_ordinal=ordinal,
        target_period={
            "season": catalog["slate"]["season"],
            "week": catalog["slate"]["week"],
        },
        full_input_sha256=deletion["full_input_sha256"],
        deleted_input_sha256=deletion["deleted_input_sha256"],
        full_input_row_count=deletion["full_input_row_count"],
        deleted_input_row_count=deletion["deleted_input_row_count"],
        deleted_row_count=deletion["deleted_row_count"],
        deleted_rows_sha256=deletion["deleted_rows_sha256"],
        deleted_row_counts_by_pack=deletion["deleted_row_counts_by_pack"],
        deleted_row_counts_by_slice=deletion["deleted_row_counts_by_slice"],
        full_output_sha256=bundle_identity["sha256"],
        deleted_output_sha256=bundle_identity["sha256"],
    )
    receipt = source.build_component_producer_receipt_v1(
        producer_id=normalized_producer_id,
        structural_catalog=catalog,
        catalog_identity=catalog_identities[ordinal],
        catalog_release=release,
        catalog_release_identity=release_identity,
        catalog_replay_receipt_identity=replay_identity,
        accepted_candidate_release=candidate_release,
        accepted_candidate_release_identity=candidate_release_identity,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
        upstream_source_release_identity=upstream_identity,
        producer_code_identity=code,
        target_spine=full_artifacts["target_spine"],
        role_entries=full_artifacts["role_entries"],
        annotation_row_count=len(full_artifacts["annotation_rows"]),
        annotation_rows_sha256=source.canonical_sha256(
            full_artifacts["annotation_rows"]
        ),
        input_bundle=bundle,
        input_bundle_identity=bundle_identity,
        target_or_later_deletion_proof=deletion_proof,
        qb_depth_census=full_artifacts["qb_depth_census"],
        admission_support_census=full_artifacts["admission_support_census"],
    )
    receipt_uri = (
        f"{producer_prefix}source-task-{ordinal:02d}-{slate_id}/"
        "producer/component-producer-receipt.json"
    )
    receipt_identity = _identity_for_body(
        body=receipt,
        uri=receipt_uri,
        identity_lookup=None,
        body_materializer=body_materializer,
        read_exact=read_exact,
        label=f"component producer receipt {ordinal}",
    )
    source.validate_component_producer_receipt_v1(
        receipt,
        structural_catalog=catalog,
        catalog_release=release,
        accepted_candidate_release=candidate_release,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
        input_bundle=bundle,
        expected_catalog_release_identity=release_identity,
        expected_catalog_replay_receipt_identity=replay_identity,
        expected_candidate_release_identity=candidate_release_identity,
        expected_upstream_source_release_identity=upstream_identity,
        expected_producer_code_identity=code,
    )
    body: dict[str, object] = {
        "schema_version": ONE_TASK_RESULT_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "producer_id": normalized_producer_id,
        "producer_namespace": producer_prefix,
        "fixed_g0_replay_receipt_identity": replay_identity,
        "catalog_release_identity": release_identity,
        "catalog_identity": catalog_identities[ordinal],
        "accepted_candidate_release_identity": candidate_release_identity,
        "upstream_source_release_identity": upstream_identity,
        "producer_code_identity": code,
        "input_bundle": bundle,
        "input_bundle_identity": bundle_identity,
        "producer_receipt": receipt,
        "producer_receipt_identity": receipt_identity,
        "target_or_later_deletion_proof": deletion_proof,
        "support_preflight_passed": receipt["support_preflight_passed"],
        **_policy(),
    }
    return _with_self_hash(body, field="one_task_result_sha256")


__all__ = [
    "CorpusR6MatchupComponentProducerV1Error",
    "FIXED_G0_REPLAY_SCHEMA",
    "ONE_TASK_RESULT_SCHEMA",
    "OFFLINE_PANEL_RESULT_SCHEMA",
    "PRODUCER_INPUT_BUNDLE_SCHEMA",
    "build_component_input_bundle_v1",
    "produce_all_54_component_panel_v1",
    "produce_one_component_task_v1",
    "validate_component_input_bundle_v1",
]
