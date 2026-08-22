"""Bounded, outcome-blind analysis of accepted simulated ``score > 200`` evidence.

The analyzer deliberately consumes the sparse strict-event sidecar rather than
the full lineup-by-world score matrix.  It cannot read realized contest
outcomes, generate worlds, admit lineups to a live corpus, or change a selector.
All input objects are generation/SHA/byte pinned by the accepted retrieval task
result and snapshot manifest.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from itertools import combinations
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_retrieval_engine as engine


ANALYSIS_SCHEMA: Final = "corpus-gt200-phenotype-analysis/v1"
ANNOTATION_SCHEMA: Final = "corpus-gt200-context-annotations/v1"
PHENOTYPE_PRESET_ID: Final = "simulated-gt200-phenotype-v1"
DEFAULT_MAX_ASSOCIATION_ROWS: Final = 25_000
DEFAULT_MAX_REDUNDANCY_ROWS: Final = 2_000
DEFAULT_MAX_TOP_WORLDS: Final = 100

ObjectReader = Callable[[Mapping[str, object]], bytes]


class CorpusGt200AnalysisError(ValueError):
    """An exact-evidence or bounded-analysis contract was violated."""


def _fail(message: str) -> None:
    raise CorpusGt200AnalysisError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        _fail(f"{label} must be an array")
    return value


def _exact_raw(
    identity: Mapping[str, object], reader: ObjectReader, *, label: str,
) -> bytes:
    try:
        expected = engine.normalize_object_identity(identity, label=label)
    except engine.CorpusRetrievalError as exc:
        raise CorpusGt200AnalysisError(str(exc)) from exc
    raw = reader(expected)
    if type(raw) is not bytes:
        _fail(f"{label} reader must return bytes")
    if len(raw) != expected["bytes"] or sha256(raw).hexdigest() != expected["sha256"]:
        _fail(f"{label} content identity differs")
    return raw


def _parse(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = engine.parse_canonical_json_bytes(raw, label=label)
    except engine.CorpusRetrievalError as exc:
        raise CorpusGt200AnalysisError(str(exc)) from exc
    return dict(_mapping(value, label=label))


def _self_hash(value: Mapping[str, object], field: str, *, label: str) -> None:
    retained = value.get(field)
    if not isinstance(retained, str):
        _fail(f"{label}.{field} is absent")
    replay = dict(value)
    replay.pop(field)
    if engine.canonical_sha256(replay) != retained:
        _fail(f"{label} self hash differs")


def _receipt_map(task_result: Mapping[str, object]) -> dict[tuple[str, str], dict[str, object]]:
    result: dict[tuple[str, str], dict[str, object]] = {}
    for raw in _sequence(task_result.get("sidecars"), label="task result sidecars"):
        row = dict(_mapping(raw, label="sidecar receipt"))
        role = row.get("role")
        strategy = row.get("strategy_id")
        if not isinstance(role, str) or not isinstance(strategy, str):
            _fail("sidecar receipt role/strategy differs")
        key = (role, strategy)
        if key in result:
            _fail("sidecar receipt keys repeat")
        _mapping(row.get("object_identity"), label="sidecar object identity")
        result[key] = row
    return result


def _event_scope(block_id: str) -> str:
    return "discovery-r0-r3" if block_id in engine.DISCOVERY_BLOCKS else "evaluation-r4"


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator == 0.0 else numerator / denominator


def _scope_stats(
    *, support: set[int], event_counts: np.ndarray, lineup_count: int,
    world_count: int, global_event_count: int,
) -> dict[str, object]:
    support_count = len(support)
    feature_events = int(event_counts[list(support)].sum()) if support else 0
    cohort_count = sum(1 for index in support if int(event_counts[index]) > 0)
    exposure = support_count * world_count
    global_exposure = lineup_count * world_count
    event_rate = feature_events / exposure if exposure else 0.0
    global_rate = global_event_count / global_exposure if global_exposure else 0.0
    outside_support = lineup_count - support_count
    outside_events = global_event_count - feature_events
    outside_exposure = outside_support * world_count
    outside_rate = outside_events / outside_exposure if outside_exposure else 0.0
    return {
        "full_corpus_lineup_count": lineup_count,
        "reference_lineup_count": support_count,
        "high_score_cohort_lineup_count": cohort_count,
        "lineup_world_exposure": exposure,
        "strict_gt_200_event_count": feature_events,
        "event_rate": event_rate,
        "full_corpus_event_rate": global_rate,
        "exposure_normalized_lift": _ratio(event_rate, global_rate),
        "unexposed_event_rate": outside_rate,
        "risk_ratio_vs_unexposed": _ratio(event_rate, outside_rate),
        "risk_difference_vs_unexposed": event_rate - outside_rate,
    }


def _annotation_contract(value: object, *, task_id: str) -> dict[str, object]:
    if value is None:
        return {
            "schema_version": ANNOTATION_SCHEMA,
            "task_id": task_id,
            "world_law": {},
            "pit_vendor_annotations": [],
            "player_features": [],
            "game_features": [],
            "world_features": [],
        }
    item = dict(_mapping(value, label="context annotations"))
    allowed = {
        "schema_version", "task_id", "world_law", "pit_vendor_annotations",
        "player_features", "game_features", "world_features",
    }
    if set(item) != allowed:
        _fail("context annotation fields differ")
    if item["schema_version"] != ANNOTATION_SCHEMA or item["task_id"] != task_id:
        _fail("context annotation schema/task differs")
    for field in ("pit_vendor_annotations", "player_features", "game_features", "world_features"):
        _sequence(item[field], label=f"context annotations {field}")
    _mapping(item["world_law"], label="context annotations world_law")
    # Context is intentionally carried verbatim and is never an input to an
    # event score, association statistic, selector membership, or rank.
    return item


def _optional_feature_maps(
    annotations: Mapping[str, object], *, player_ids: set[str], game_ids: set[str],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]], dict[tuple[str, int], dict[str, object]]]:
    players: dict[str, dict[str, object]] = {}
    for raw in _sequence(annotations["player_features"], label="player features"):
        row = dict(_mapping(raw, label="player feature"))
        player_id = row.get("player_id")
        if not isinstance(player_id, str) or player_id not in player_ids or player_id in players:
            _fail("player feature identity is unknown or repeated")
        players[player_id] = row
    games: dict[str, dict[str, object]] = {}
    for raw in _sequence(annotations["game_features"], label="game features"):
        row = dict(_mapping(raw, label="game feature"))
        game_id = row.get("game_id")
        if not isinstance(game_id, str) or game_id not in game_ids or game_id in games:
            _fail("game feature identity is unknown or repeated")
        games[game_id] = row
    worlds: dict[tuple[str, int], dict[str, object]] = {}
    for raw in _sequence(annotations["world_features"], label="world features"):
        row = dict(_mapping(raw, label="world feature"))
        block_id, world_index = row.get("block_id"), row.get("world_index")
        if block_id not in engine.WORLD_BLOCKS or type(world_index) is not int:
            _fail("world feature coordinate differs")
        if not 0 <= world_index < engine.WORLDS_PER_BLOCK:
            _fail("world feature coordinate is out of range")
        key = (str(block_id), world_index)
        if key in worlds:
            _fail("world feature coordinates repeat")
        worlds[key] = row
    return players, games, worlds


def _association_row(
    *, category: str, key: str, components: Sequence[str], support: set[int],
    event_counts: Mapping[str, np.ndarray], global_events: Mapping[str, int],
    lineup_count: int, selectors: Mapping[str, set[int]],
) -> dict[str, object]:
    scopes = {
        scope: _scope_stats(
            support=support,
            event_counts=event_counts[scope],
            lineup_count=lineup_count,
            world_count=(
                40_000 if scope == "discovery-r0-r3"
                else 10_000 if scope == "evaluation-r4" else 50_000
            ),
            global_event_count=global_events[scope],
        )
        for scope in ("discovery-r0-r3", "evaluation-r4", "all-r0-r4-descriptive")
    }
    corpus_exposure = len(support) / lineup_count
    selector_membership: dict[str, object] = {}
    for strategy_id, selected in sorted(selectors.items()):
        selected_support = len(support & selected)
        selector_exposure = selected_support / len(selected) if selected else 0.0
        selector_membership[strategy_id] = {
            "selected_lineup_count": len(selected),
            "selected_support_lineup_count": selected_support,
            "selected_exposure": selector_exposure,
            "corpus_exposure": corpus_exposure,
            "exposure_lift_vs_corpus": _ratio(selector_exposure, corpus_exposure),
        }
    return {
        "association_id": f"association:{category}:{sha256(key.encode()).hexdigest()}",
        "category": category,
        "key": key,
        "components": list(components),
        "support_lineup_indices": sorted(support),
        "selector_membership": selector_membership,
        "scopes": scopes,
    }


def _graph_node(identifier: str, kind: str, properties: Mapping[str, object]) -> dict[str, object]:
    return {"id": identifier, "kind": kind, "properties": dict(properties)}


def _graph_edge(
    source: str, relationship: str, target: str, properties: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "from": source,
        "type": relationship,
        "to": target,
        "properties": {} if properties is None else dict(properties),
    }


def build_gt200_analysis(
    *,
    task_result_raw: bytes,
    task_result_identity: Mapping[str, object],
    read_object: ObjectReader,
    analysis_id: str,
    created_at_utc: str,
    context_annotations: object = None,
    max_association_rows: int = DEFAULT_MAX_ASSOCIATION_ROWS,
    max_redundancy_rows: int = DEFAULT_MAX_REDUNDANCY_ROWS,
    max_top_worlds: int = DEFAULT_MAX_TOP_WORLDS,
) -> dict[str, object]:
    """Build a canonical, Neo4j-ready projection without the full score matrix."""
    if not analysis_id or not isinstance(analysis_id, str):
        _fail("analysis_id must be nonempty")
    try:
        engine._timestamp(created_at_utc, label="created_at_utc")
    except engine.CorpusRetrievalError as exc:
        raise CorpusGt200AnalysisError(str(exc)) from exc
    for value, label in (
        (max_association_rows, "max_association_rows"),
        (max_redundancy_rows, "max_redundancy_rows"),
        (max_top_worlds, "max_top_worlds"),
    ):
        if type(value) is not int or value < 1:
            _fail(f"{label} must be positive")

    expected_task_identity = engine.normalize_object_identity(
        task_result_identity, label="task result identity"
    )
    if (
        len(task_result_raw) != expected_task_identity["bytes"]
        or sha256(task_result_raw).hexdigest() != expected_task_identity["sha256"]
    ):
        _fail("task result content identity differs")
    task_result = _parse(task_result_raw, label="task result")
    if task_result.get("schema_version") != engine.TASK_RESULT_SCHEMA:
        _fail("task result schema differs")
    _self_hash(task_result, "task_result_sha256", label="task result")
    licenses = _mapping(task_result.get("licenses"), label="task result licenses")
    if licenses.get("analytics_authority") is not True:
        _fail("task result lacks analytics authority")
    if licenses.get("historical_outcome_read_authority") is not False:
        _fail("task result historical-outcome license differs")
    coverage = _mapping(task_result.get("coverage"), label="task result coverage")
    if coverage.get("every_unique_lineup_scored_in_every_world") is not True:
        _fail("task result does not cover every lineup/world")
    task_id = task_result.get("task_id")
    if not isinstance(task_id, str):
        _fail("task result task_id differs")

    snapshot_identity = engine.normalize_object_identity(
        _mapping(task_result.get("snapshot_manifest_identity"), label="snapshot identity"),
        label="snapshot identity",
    )
    snapshot_raw = _exact_raw(snapshot_identity, read_object, label="snapshot manifest")
    snapshot_value = _parse(snapshot_raw, label="snapshot manifest")
    try:
        snapshot = engine.validate_snapshot_manifest(snapshot_value)
    except engine.CorpusRetrievalError as exc:
        raise CorpusGt200AnalysisError(str(exc)) from exc
    snapshot_tasks = [
        row for row in snapshot["tasks"] if row.get("task_id") == task_id
    ]
    if len(snapshot_tasks) != 1:
        _fail("snapshot task binding differs")
    snapshot_task = snapshot_tasks[0]
    blocks = snapshot_task["world_blocks"]
    if [row["block_id"] for row in blocks] != list(engine.WORLD_BLOCKS):
        _fail("world block law differs")

    player_identity = engine.normalize_object_identity(
        snapshot_task["player_catalog_object"], label="player catalog identity"
    )
    player_raw = _exact_raw(player_identity, read_object, label="player catalog")
    player_value = _parse(player_raw, label="player catalog")
    try:
        player_catalog = engine.validate_player_catalog_object(player_value)
    except engine.CorpusRetrievalError as exc:
        raise CorpusGt200AnalysisError(str(exc)) from exc
    if player_catalog["task_id"] != task_id:
        _fail("player catalog task binding differs")
    player_by_id = {str(row["id"]): dict(row) for row in player_catalog["players"]}

    receipts = _receipt_map(task_result)
    required_keys = [("unique-lineups", ""), ("strict-gt-200-events", "")]
    if any(key not in receipts for key in required_keys):
        _fail("required compact sidecar receipt is absent")
    lineup_receipt = receipts[("unique-lineups", "")]
    lineup_raw = _exact_raw(
        _mapping(lineup_receipt["object_identity"], label="lineup identity"),
        read_object, label="unique lineups",
    )
    lineup_table = _parse(lineup_raw, label="unique lineups")
    if lineup_table.get("schema_version") != engine.LINEUP_TABLE_SCHEMA:
        _fail("unique lineup schema differs")
    _self_hash(lineup_table, "lineup_table_sha256", label="unique lineups")
    if lineup_table.get("task_id") != task_id or lineup_table.get("roster_size") != 9:
        _fail("unique lineup task/roster contract differs")
    lineups = [dict(_mapping(row, label="lineup")) for row in _sequence(lineup_table["lineups"], label="lineups")]
    lineup_count = len(lineups)
    if lineup_table.get("lineup_count") != lineup_count or coverage.get("unique_lineup_count") != lineup_count:
        _fail("unique lineup count differs")
    lineup_ids: list[str] = []
    roster_sets: list[set[str]] = []
    for expected_index, lineup in enumerate(lineups):
        lineup_id = lineup.get("lineup_id")
        roster = list(_sequence(lineup.get("roster_player_ids"), label="roster player IDs"))
        if (
            lineup.get("lineup_index") != expected_index
            or not isinstance(lineup_id, str)
            or len(roster) != 9
            or len(set(roster)) != 9
            or any(not isinstance(value, str) or value not in player_by_id for value in roster)
        ):
            _fail("unique lineup indexing/roster differs")
        lineup_ids.append(lineup_id)
        roster_sets.append(set(roster))
    if len(set(lineup_ids)) != lineup_count:
        _fail("lineup IDs repeat")

    event_receipt = receipts[("strict-gt-200-events", "")]
    event_raw = _exact_raw(
        _mapping(event_receipt["object_identity"], label="strict event identity"),
        read_object, label="strict events",
    )
    try:
        arrays, descriptors = engine._load_npz_arrays(
            event_raw,
            expected=(
                ("lineup_index", "<i4", (None,)),
                ("block_index", "|u1", (None,)),
                ("world_index", "<i4", (None,)),
                ("score", "<f4", (None,)),
            ),
            label="strict events",
            require_canonical=True,
        )
    except engine.CorpusRetrievalError as exc:
        raise CorpusGt200AnalysisError(str(exc)) from exc
    lengths = {len(value) for value in arrays.values()}
    if len(lengths) != 1:
        _fail("strict event array lengths differ")
    event_count = lengths.pop()
    lineup_ix = arrays["lineup_index"]
    block_ix = arrays["block_index"]
    world_ix = arrays["world_index"]
    scores = arrays["score"]
    if (
        event_count == 0
        or np.any(lineup_ix < 0)
        or np.any(lineup_ix >= lineup_count)
        or np.any(block_ix >= len(engine.WORLD_BLOCKS))
        or np.any(world_ix < 0)
        or np.any(world_ix >= engine.WORLDS_PER_BLOCK)
        or np.any(scores <= engine.PRIMARY_EVENT_THRESHOLD)
    ):
        _fail("strict event values differ")
    observed_order = np.lexsort((lineup_ix, world_ix, block_ix))
    if not np.array_equal(observed_order, np.arange(event_count)):
        _fail("strict events are not in canonical coordinate order")
    coordinates = np.stack((block_ix.astype(np.int64), world_ix, lineup_ix), axis=1)
    if event_count > 1 and np.any(np.all(coordinates[1:] == coordinates[:-1], axis=1)):
        _fail("strict event coordinates repeat")
    semantic = _mapping(event_receipt.get("semantic"), label="strict event semantic")
    if semantic.get("arrays") != descriptors:
        _fail("strict event array descriptors differ")
    expected_summary = _mapping(task_result.get("primary_event_summary"), label="primary event summary")
    if expected_summary.get("event_count") != event_count:
        _fail("strict event count differs from task result")

    annotations = _annotation_contract(context_annotations, task_id=task_id)
    player_features, game_features, world_features = _optional_feature_maps(
        annotations,
        player_ids=set(player_by_id),
        game_ids={str(row["game_id"]) for row in player_by_id.values()},
    )

    strategy_results = _sequence(task_result.get("strategy_results"), label="strategy results")
    selectors: dict[str, set[int]] = {}
    selection_ranks: dict[str, dict[int, int]] = {}
    for raw_result in strategy_results:
        result = _mapping(raw_result, label="strategy result")
        strategy_id = result.get("strategy_id")
        if not isinstance(strategy_id, str):
            _fail("strategy ID differs")
        receipt = receipts.get(("strategy-selection", strategy_id))
        if receipt is None or result.get("selection_object") != receipt.get("object_identity"):
            _fail("strategy selection receipt binding differs")
        selection_raw = _exact_raw(
            _mapping(receipt["object_identity"], label="selection identity"),
            read_object, label=f"selection {strategy_id}",
        )
        selection = _parse(selection_raw, label=f"selection {strategy_id}")
        if selection.get("schema_version") != engine.SELECTION_SCHEMA:
            _fail("selection schema differs")
        _self_hash(selection, "selection_sha256", label=f"selection {strategy_id}")
        selected = list(_sequence(selection.get("selected_lineup_indices"), label="selected lineup indices"))
        selected_ids = list(_sequence(selection.get("selected_lineup_ids"), label="selected lineup IDs"))
        if (
            selected != result.get("selected_lineup_indices")
            or len(selected) != len(set(selected))
            or any(type(value) is not int or not 0 <= value < lineup_count for value in selected)
            or selected_ids != [lineup_ids[value] for value in selected]
        ):
            _fail("selection lineup binding differs")
        selectors[strategy_id] = set(selected)
        selection_ranks[strategy_id] = {index: rank for rank, index in enumerate(selected)}

    scope_event_counts = {
        "discovery-r0-r3": np.zeros(lineup_count, dtype=np.int64),
        "evaluation-r4": np.zeros(lineup_count, dtype=np.int64),
        "all-r0-r4-descriptive": np.zeros(lineup_count, dtype=np.int64),
    }
    lineup_block_counts = np.zeros((lineup_count, len(engine.WORLD_BLOCKS)), dtype=np.int64)
    event_worlds: list[set[int]] = [set() for _ in range(lineup_count)]
    world_rows: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
    event_rows: list[dict[str, object]] = []
    for index, block, world, score in zip(lineup_ix, block_ix, world_ix, scores, strict=True):
        lineup_index, block_index, world_index = int(index), int(block), int(world)
        block_id = engine.WORLD_BLOCKS[block_index]
        scope = _event_scope(block_id)
        scope_event_counts[scope][lineup_index] += 1
        scope_event_counts["all-r0-r4-descriptive"][lineup_index] += 1
        lineup_block_counts[lineup_index, block_index] += 1
        event_worlds[lineup_index].add(block_index * engine.WORLDS_PER_BLOCK + world_index)
        world_rows[(block_index, world_index)].append((lineup_index, float(score)))
        world_annotation = world_features.get((block_id, world_index), {})
        event_rows.append({
            "event_id": f"event:{task_id}:{block_id}:{world_index}:{lineup_index}",
            "lineup_index": lineup_index,
            "lineup_id": lineup_ids[lineup_index],
            "block_id": block_id,
            "partition": scope,
            "world_index": world_index,
            "seed": world_annotation.get("seed"),
            "score": float(score),
            "outcome_semantics": "simulated-world-score",
        })
    global_events = {key: int(value.sum()) for key, value in scope_event_counts.items()}

    association_support: dict[tuple[str, str, tuple[str, ...]], set[int]] = defaultdict(set)
    phenotype_tokens_by_lineup: list[list[str]] = []
    easy_coverage_annotated_ids = {
        player_id for player_id, row in player_features.items()
        if "easy_coverage" in row
    }
    easy_coverage_state_by_lineup: list[bool | None] = []
    easy_coverage_count_by_lineup: list[int | None] = []
    easy_coverage_lineups = 0
    easy_coverage_complete_lineups = 0
    for lineup_index, (lineup, roster) in enumerate(zip(lineups, roster_sets, strict=True)):
        ordered_roster = sorted(roster)
        positions = {player_id: str(player_by_id[player_id]["pos"]) for player_id in roster}
        teams = Counter(str(player_by_id[player_id]["team"]) for player_id in roster)
        games = Counter(str(player_by_id[player_id]["game_id"]) for player_id in roster)
        for first, second in combinations(ordered_roster, 2):
            key = "|".join((first, second))
            association_support[("player-pair", key, (first, second))].add(lineup_index)
        position_pairs = {
            tuple(sorted((positions[first], positions[second])))
            for first, second in combinations(ordered_roster, 2)
        }
        for pair in position_pairs:
            association_support[("position-pair", "|".join(pair), pair)].add(lineup_index)
        for team, count in teams.items():
            if count >= 2:
                components = (team, str(count))
                association_support[("team-stack", f"{team}|{count}", components)].add(lineup_index)
        for game, count in games.items():
            if count >= 2:
                components = (game, str(count))
                association_support[("game-stack", f"{game}|{count}", components)].add(lineup_index)

        memberships = _sequence(lineup.get("source_memberships"), label="source memberships")
        tags = sorted({
            str(tag)
            for membership in memberships
            for tag in _sequence(_mapping(membership, label="source membership").get("all_tags"), label="membership tags")
        })
        for tag in tags:
            association_support[("generator-tag", tag, (tag,))].add(lineup_index)
        features = _mapping(lineup.get("features"), label="lineup features")
        stack_key = (
            f"qb_stack={features.get('qb_stack_teammates')}|"
            f"bring_back={features.get('bring_back_players')}|"
            f"max_game={features.get('max_players_same_game')}"
        )
        association_support[("stack-topology", stack_key, (stack_key,))].add(lineup_index)
        receiver_players = [
            player_id for player_id in roster
            if str(player_by_id[player_id]["pos"]) in {"WR", "TE"}
        ]
        easy_coverage_complete = bool(receiver_players) and all(
            player_id in easy_coverage_annotated_ids for player_id in receiver_players
        )
        easy_players = [
            player_id for player_id in receiver_players
            if player_features.get(player_id, {}).get("easy_coverage") is True
        ]
        easy_coverage_state = bool(easy_players) if easy_coverage_complete else None
        easy_coverage_state_by_lineup.append(easy_coverage_state)
        easy_coverage_count_by_lineup.append(
            len(easy_players) if easy_coverage_complete else None
        )
        if easy_coverage_complete:
            easy_coverage_complete_lineups += 1
        if easy_coverage_state is True:
            easy_coverage_lineups += 1
        phenotype_tokens = [f"tag={tag}" for tag in tags]
        phenotype_tokens.extend((
            f"qb_stack={features.get('qb_stack_teammates')}",
            f"bring_back={features.get('bring_back_players')}",
            f"max_game={features.get('max_players_same_game')}",
        ))
        if easy_coverage_state is not None:
            phenotype_tokens.append(f"easy_coverage={easy_coverage_state}")
        phenotype_tokens = sorted(phenotype_tokens)
        phenotype_tokens_by_lineup.append(phenotype_tokens)
        phenotype_key = "|".join(phenotype_tokens)
        association_support[("phenotype-combination", phenotype_key, tuple(phenotype_tokens))].add(lineup_index)

    associations = [
        _association_row(
            category=category,
            key=key,
            components=components,
            support=support,
            event_counts=scope_event_counts,
            global_events=global_events,
            lineup_count=lineup_count,
            selectors=selectors,
        )
        for (category, key, components), support in association_support.items()
    ]
    associations.sort(key=lambda row: (
        -int(row["scopes"]["discovery-r0-r3"]["strict_gt_200_event_count"]),
        -int(row["scopes"]["discovery-r0-r3"]["reference_lineup_count"]),
        str(row["category"]), str(row["key"]),
    ))
    association_universe_count = len(associations)
    associations = associations[:max_association_rows]

    origin_support: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for lineup_index, lineup in enumerate(lineups):
        for raw_membership in _sequence(lineup["source_memberships"], label="source memberships"):
            membership = _mapping(raw_membership, label="source membership")
            key = (str(membership["block_id"]), str(membership["panel_id"]), str(membership["tag"]))
            origin_support[key].add(lineup_index)
    origins = []
    for (block_id, panel_id, tag), support in sorted(origin_support.items()):
        origin_key = f"{block_id}|{panel_id}|{tag}"
        row = _association_row(
            category="candidate-origin", key=origin_key,
            components=(block_id, panel_id, tag), support=support,
            event_counts=scope_event_counts, global_events=global_events,
            lineup_count=lineup_count, selectors=selectors,
        )
        row.update({"block_id": block_id, "panel_id": panel_id, "tag": tag})
        origins.append(row)

    block_summaries: list[dict[str, object]] = []
    top_world_rows: list[dict[str, object]] = []
    all_world_nodes: list[dict[str, object]] = []
    for block_index, block_id in enumerate(engine.WORLD_BLOCKS):
        counts = [
            (world, rows) for (block, world), rows in world_rows.items()
            if block == block_index
        ]
        counts.sort(key=lambda item: (-len(item[1]), item[0]))
        block_events = sum(len(rows) for _, rows in counts)
        shares = [len(rows) / block_events for _, rows in counts] if block_events else []
        block_summaries.append({
            "block_id": block_id,
            "ordinal": block_index,
            "partition": _event_scope(block_id),
            "world_count": engine.WORLDS_PER_BLOCK,
            "worlds_with_event": len(counts),
            "strict_gt_200_event_count": block_events,
            "share_of_all_events": block_events / event_count,
            "event_world_hhi": sum(value * value for value in shares),
            "top_1_world_event_share": sum(shares[:1]),
            "top_10_world_event_share": sum(shares[:10]),
        })
        for world, rows in counts:
            all_world_nodes.append({
                "world_id": f"sim-world:{task_id}:{block_id}:{world}",
                "block_id": block_id,
                "partition": _event_scope(block_id),
                "world_index": world,
                "seed": world_features.get((block_id, world), {}).get("seed"),
                "strict_gt_200_lineup_count": len(rows),
                "max_score": max(score for _, score in rows),
                "mean_score": sum(score for _, score in rows) / len(rows),
            })
        for world, rows in counts[:max_top_worlds]:
            top_world_rows.append({
                "block_id": block_id,
                "partition": _event_scope(block_id),
                "world_index": world,
                "seed": world_features.get((block_id, world), {}).get("seed"),
                "strict_gt_200_lineup_count": len(rows),
                "max_score": max(score for _, score in rows),
                "mean_score": sum(score for _, score in rows) / len(rows),
            })

    redundancy_distribution: Counter[int] = Counter()
    redundancy_rows: list[dict[str, object]] = []
    for first, second in combinations(range(lineup_count), 2):
        shared = len(roster_sets[first] & roster_sets[second])
        redundancy_distribution[shared] += 1
        event_intersection = len(event_worlds[first] & event_worlds[second])
        event_union = len(event_worlds[first] | event_worlds[second])
        redundancy_rows.append({
            "lineup_indices": [first, second],
            "lineup_ids": [lineup_ids[first], lineup_ids[second]],
            "shared_player_count": shared,
            "roster_jaccard": shared / (18 - shared),
            "simulated_gt200_world_intersection": event_intersection,
            "simulated_gt200_world_union": event_union,
            "simulated_gt200_world_jaccard": (
                event_intersection / event_union if event_union else 0.0
            ),
            "shared_selectors": sorted(
                strategy for strategy, selected in selectors.items()
                if first in selected and second in selected
            ),
        })
    redundancy_rows.sort(key=lambda row: (
        -int(row["shared_player_count"]),
        -float(row["simulated_gt200_world_jaccard"]),
        row["lineup_ids"],
    ))
    redundancy_universe_count = len(redundancy_rows)
    redundancy_rows = redundancy_rows[:max_redundancy_rows]

    lineup_rows: list[dict[str, object]] = []
    for index, lineup in enumerate(lineups):
        selector_rows = [
            {"strategy_id": strategy, "selection_rank": ranks[index]}
            for strategy, ranks in sorted(selection_ranks.items()) if index in ranks
        ]
        features = dict(_mapping(lineup["features"], label="lineup features"))
        roster = sorted(roster_sets[index])
        ownership_values = [player_features[player].get("ownership_projection") for player in roster if "ownership_projection" in player_features.get(player, {})]
        leverage_values = [player_features[player].get("leverage_projection") for player in roster if "leverage_projection" in player_features.get(player, {})]
        lineup_rows.append({
            "lineup_index": index,
            "lineup_id": lineup_ids[index],
            "roster_player_ids": roster,
            "source_memberships": lineup["source_memberships"],
            "generator_tags": lineup["tags"],
            "features": features,
            "phenotype_tokens": phenotype_tokens_by_lineup[index],
            "optional_features": {
                "easy_coverage_player_count": easy_coverage_count_by_lineup[index],
                "ownership_projection_sum": sum(float(value) for value in ownership_values) if len(ownership_values) == len(roster) else None,
                "leverage_projection_sum": sum(float(value) for value in leverage_values) if len(leverage_values) == len(roster) else None,
                "game_environment_annotations": [game_features[game] for game in features.get("games", []) if game in game_features],
            },
            "selector_memberships": selector_rows,
            "simulated_gt200": {
                scope: {
                    "event_count": int(values[index]),
                    "event_rate": int(values[index]) / (
                        40_000 if scope == "discovery-r0-r3" else 10_000 if scope == "evaluation-r4" else 50_000
                    ),
                }
                for scope, values in scope_event_counts.items()
            },
            "event_count_by_block": {
                block: int(lineup_block_counts[index, ordinal])
                for ordinal, block in enumerate(engine.WORLD_BLOCKS)
            },
        })

    analysis_node_id = f"gt200-analysis:{analysis_id}"
    graph_nodes = [_graph_node(analysis_node_id, "CorpusGt200Analysis", {
        "analysis_id": analysis_id, "task_id": task_id,
        "outcome_semantics": "simulated-world-scores-only",
    })]
    graph_edges: list[dict[str, object]] = []
    for player_id, player in sorted(player_by_id.items()):
        graph_nodes.append(_graph_node(f"player:{task_id}:{player_id}", "Player", player))
    for row in lineup_rows:
        node_id = f"candidate:{task_id}:{row['lineup_id']}"
        graph_nodes.append(_graph_node(node_id, "LineupCandidate", {
            key: value for key, value in row.items() if key != "roster_player_ids"
        }))
        graph_edges.append(_graph_edge(analysis_node_id, "HAS_LINEUP", node_id))
        for player_id in row["roster_player_ids"]:
            graph_edges.append(_graph_edge(node_id, "ROSTERS", f"player:{task_id}:{player_id}"))
    for strategy_id, ranks in sorted(selection_ranks.items()):
        strategy_node = f"strategy:{task_id}:{strategy_id}"
        graph_nodes.append(_graph_node(strategy_node, "RetrievalStrategy", {"strategy_id": strategy_id}))
        graph_edges.append(_graph_edge(analysis_node_id, "HAS_SELECTOR", strategy_node))
        for lineup_index, rank in sorted(ranks.items(), key=lambda item: item[1]):
            graph_edges.append(_graph_edge(
                strategy_node, "SELECTED",
                f"candidate:{task_id}:{lineup_ids[lineup_index]}",
                {"selection_rank": rank},
            ))
    for block in block_summaries:
        block_node = f"sim-block:{task_id}:{block['block_id']}"
        graph_nodes.append(_graph_node(block_node, "SimulatedWorldBlock", block))
        graph_edges.append(_graph_edge(analysis_node_id, "HAS_SIMULATED_BLOCK", block_node))
    for world in all_world_nodes:
        graph_nodes.append(_graph_node(world["world_id"], "SimulatedWorld", world))
        graph_edges.append(_graph_edge(
            f"sim-block:{task_id}:{world['block_id']}", "HAS_WORLD", world["world_id"]
        ))
    for event in event_rows:
        graph_edges.append(_graph_edge(
            f"candidate:{task_id}:{event['lineup_id']}", "SIMULATED_GT200_IN",
            f"sim-world:{task_id}:{event['block_id']}:{event['world_index']}",
            {"event_id": event["event_id"], "score": event["score"], "partition": event["partition"]},
        ))
    for association in associations:
        association_id = association["association_id"]
        graph_nodes.append(_graph_node(association_id, "PhenotypeAssociation", {
            key: value for key, value in association.items() if key != "support_lineup_indices"
        }))
        graph_edges.append(_graph_edge(analysis_node_id, "HAS_ASSOCIATION", association_id))
        for lineup_index in association["support_lineup_indices"]:
            graph_edges.append(_graph_edge(
                association_id, "SUPPORTED_BY",
                f"candidate:{task_id}:{lineup_ids[lineup_index]}",
            ))
    for row in redundancy_rows:
        first, second = row["lineup_indices"]
        graph_edges.append(_graph_edge(
            f"candidate:{task_id}:{lineup_ids[first]}", "ROSTER_OVERLAP",
            f"candidate:{task_id}:{lineup_ids[second]}",
            {key: value for key, value in row.items() if key not in {"lineup_indices", "lineup_ids"}},
        ))

    availability = {
        "generator_family_tags": {"available": True, "lineup_coverage": lineup_count},
        "salary_and_projection": {"available": True, "lineup_coverage": lineup_count},
        "player_pairs_and_stack_topology": {"available": True, "lineup_coverage": lineup_count},
        "simulated_world_block_origin": {"available": True, "event_coverage": event_count},
        "simulated_world_seed": {"available": bool(world_features), "annotated_world_count": len(world_features)},
        "easy_coverage": {
            "available": bool(easy_coverage_annotated_ids),
            "annotated_player_count": len(easy_coverage_annotated_ids),
            "complete_lineup_count": easy_coverage_complete_lineups,
            "lineups_with_easy_coverage": (
                easy_coverage_lineups if easy_coverage_complete_lineups else None
            ),
        },
        "ownership_projection": {
            "available": any("ownership_projection" in row for row in player_features.values()),
            "annotated_player_count": sum("ownership_projection" in row for row in player_features.values()),
        },
        "leverage_projection": {
            "available": any("leverage_projection" in row for row in player_features.values()),
            "annotated_player_count": sum("leverage_projection" in row for row in player_features.values()),
        },
        "game_environment": {"available": bool(game_features), "annotated_game_count": len(game_features)},
        "realized_contest_outcomes": {"available": False, "reason": "not licensed or read"},
    }

    body: dict[str, object] = {
        "schema_version": ANALYSIS_SCHEMA,
        "analysis_id": analysis_id,
        "created_at_utc": created_at_utc,
        "task_id": task_id,
        "evidence": {
            "task_result_identity": expected_task_identity,
            "snapshot_manifest_identity": snapshot_identity,
            "player_catalog_identity": player_identity,
            "unique_lineups_identity": lineup_receipt["object_identity"],
            "strict_gt_200_events_identity": event_receipt["object_identity"],
            "selection_identities": {
                strategy: receipts[("strategy-selection", strategy)]["object_identity"]
                for strategy in sorted(selectors)
            },
            "full_score_matrix_read": False,
        },
        "outcome_semantics": {
            "score_source": "retained-simulated-world-matrices",
            "primary_event": {"operator": ">", "threshold": 200.0, "unit": "dk_points_float32"},
            "discovery_partition": list(engine.DISCOVERY_BLOCKS),
            "evaluation_partition": list(engine.HELDOUT_BLOCKS),
            "evaluation_use": "descriptive-only; excluded from preset ranking inputs",
            "realized_contest_outcomes_read": False,
            "winner_roi_or_profit_claims_licensed": False,
            "causal_claims_licensed": False,
        },
        "world_provenance": {
            "receipt_bound_blocks": [
                {
                    "block_id": row["block_id"], "panel_id": row["panel_id"],
                    "artifact_object": row["artifact_object"],
                }
                for row in blocks
            ],
            "declared_context_annotations": annotations["world_law"],
            "pit_vendor_annotations": annotations["pit_vendor_annotations"],
            "annotation_semantics": "optional context only; not score input replay and not causal evidence",
        },
        "phenotype_preset": {
            "preset_id": PHENOTYPE_PRESET_ID,
            "population_admission_view": {
                "allowed_inputs": ["pre-lock generator tags", "roster composition", "PIT annotations when available"],
                "forbidden_inputs": ["simulated event counts", "R4 evaluation", "realized outcomes"],
                "rows": "lineups",
            },
            "retrieval_filter_ranker_view": {
                "allowed_inputs": ["R0--R3 simulated strict >200 counts", "exposure-normalized lift", "selector membership", "roster redundancy"],
                "forbidden_inputs": ["R4 evaluation", "realized outcomes"],
                "rows": "associations.scopes.discovery-r0-r3",
                "default_rank_keys": ["strict_gt_200_event_count desc", "reference_lineup_count desc", "category asc", "key asc"],
            },
            "evaluation_view": {"rows": "associations.scopes.evaluation-r4", "ranker_input": False},
        },
        "availability": availability,
        "optional_join_contract": {
            "schema_version": ANNOTATION_SCHEMA,
            "keys": {
                "player_features": ["task_id", "player_id"],
                "game_features": ["task_id", "game_id"],
                "world_features": ["task_id", "block_id", "world_index"],
            },
            "easy_coverage_definition": "pre-lock receiver alignment/coverage traits crossed with opponent prior-window coverage map",
            "required_guards": ["point-in-time source identity", "pre-lock availability", "no target outcome fields", "coverage diagnostics"],
        },
        "summary": {
            "lineup_count": lineup_count,
            "simulated_world_count": 50_000,
            "strict_gt_200_event_count": event_count,
            "lineups_with_event": sum(bool(worlds) for worlds in event_worlds),
            "association_universe_count": association_universe_count,
            "association_retained_count": len(associations),
            "redundancy_pair_universe_count": redundancy_universe_count,
            "redundancy_pair_retained_count": len(redundancy_rows),
        },
        "lineups": lineup_rows,
        "simulated_gt200_events": event_rows,
        "associations": associations,
        "candidate_origins": origins,
        "world_block_concentration": block_summaries,
        "top_worlds_by_block": top_world_rows,
        "roster_redundancy": {
            "overlap_pair_count_by_shared_players": {
                str(key): value for key, value in sorted(redundancy_distribution.items())
            },
            "score_correlation_computed": False,
            "score_correlation_reason": "full score matrix intentionally not read",
            "top_pairs": redundancy_rows,
        },
        "neo4j_projection": {
            "dedicated_analytical_graph_only": True,
            "node_count": len(graph_nodes),
            "edge_count": len(graph_edges),
            "nodes": sorted(graph_nodes, key=lambda row: str(row["id"])),
            "edges": sorted(graph_edges, key=lambda row: (
                str(row["from"]), str(row["type"]), str(row["to"]),
                engine.canonical_sha256(row["properties"]),
            )),
        },
        "licenses": {
            "analytics_authority": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }
    body["analysis_sha256"] = engine.canonical_sha256(body)
    return body


__all__ = [
    "ANALYSIS_SCHEMA",
    "ANNOTATION_SCHEMA",
    "CorpusGt200AnalysisError",
    "build_gt200_analysis",
]
