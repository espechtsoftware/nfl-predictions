"""Terminal-first realized grading for novel R6 roster experiments.

Population-crossed and hard230 deliberately create rosters outside the frozen
full-union lineup-ID registry.  This module therefore scores their roster
members directly from the immutable player-outcome snapshot.  It does not use
the full-union lineup lookup.

The outcome object is inaccessible until one create-last experiment root, its
manifest, all 54 task results, and (for hard230) every terminal process receipt
have been exact-opened and validated.  Each distinct roster is then summed
once per slate and every population/book metric is projected from that lookup.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_process_v1 as hard_process,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as hard_successor,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as hard_cloud,
)
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as outcomes
from nfl_dfs.research import corpus_r6_population_crossed_cloud_v1 as population_cloud
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT


TERMINAL_ROOT_SCHEMA: Final = "corpus-r6-novel-roster-terminal-root/v1"
REALIZED_GRADE_SCHEMA: Final = "corpus-r6-novel-roster-realized-grade/v1"
SLATE_GRADE_SCHEMA: Final = "corpus-r6-novel-roster-realized-slate-grade/v1"
AGGREGATE_CELL_SCHEMA: Final = (
    "corpus-r6-novel-roster-realized-aggregate-cell/v1"
)

POPULATION_CROSSED_ADAPTER: Final = "population-crossed-v1"
HARD230_ADAPTER: Final = "hard230-v1"
ADAPTER_IDS: Final = (POPULATION_CROSSED_ADAPTER, HARD230_ADAPTER)
SOURCE_SLATE_COUNT: Final = 54
THRESHOLDS_DK: Final = (200, 210, 220, 230)
MAXIMUM_ROOT_BYTES: Final = 8_000_000
MAXIMUM_OUTCOME_SNAPSHOT_BYTES: Final = 64_000_000
MAXIMUM_REALIZED_GRADE_BYTES: Final = 256_000_000
FIXED_GCP_PROJECT: Final = "nfl-predictions-503414"
FIXED_STORAGE_ENDPOINT: Final = "https://storage.googleapis.com"

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]

_SNAPSHOT_FIELDS: Final = frozenset({
    "schema_version", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "panel_freeze_identity",
    "panel_freeze_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "realized_source_identity",
    "realized_source_sha256", "score_unit", "micro_dk_per_point",
    "row_count", "row_keys_sha256", "rows_sha256", "rows",
    "exact_union_coverage", "lineup_scoring_performed",
    "full_field_standings_included", "payout_ladder_included",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "outcome_snapshot_sha256",
})
_SNAPSHOT_ROW_FIELDS: Final = frozenset({
    "source_ordinal", "season", "week", "slate_id", "player_id",
    "realized_score_micro",
})


class CorpusR6NovelRosterRealizedGraderV1Error(ValueError):
    """A terminal experiment or direct-roster realized grade failed closed."""


@dataclass(frozen=True, slots=True)
class _OpenedTerminal:
    adapter_id: str
    task_manifest: Mapping[str, object]
    task_manifest_identity: Mapping[str, object]
    task_manifest_sha256: str
    task_results: tuple[Mapping[str, object], ...]
    task_result_descriptors: tuple[Mapping[str, object], ...]
    slates: tuple[Mapping[str, object], ...]
    later_source_identity: Mapping[str, object]


def _fail(message: str) -> None:
    raise CorpusR6NovelRosterRealizedGraderV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty exact string")
    return value


def _integer(value: object, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc


def _bind_json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = canonical_sha256_v1(body)
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    if (
        type(retained) is not str
        or len(retained) != 64
        or retained
        != canonical_sha256_v1({key: row for key, row in value.items() if key != field})
    ):
        _fail(f"{label} self-hash differs")


def _exact_read_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc
    body = _mapping(value, label=label)
    _bind_json_identity(body, identity, label=label)
    return body, identity


def _publish_json_create_once(
    *,
    uri: str,
    value: Mapping[str, object],
    maximum_bytes: int,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    if type(uri) is not str or not uri.startswith("gs://") or uri.endswith("/"):
        _fail(f"{label} URI must name one exact GCS object")
    raw = canonical_json_bytes_v1(value)
    if not raw or len(raw) > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(published, label=f"published {label}")
    if (
        identity["uri"] != uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} publisher identity differs")
    reopened, reopened_identity = _exact_read_json(
        identity,
        read_exact=read_exact,
        label=f"published {label}",
        maximum_bytes=maximum_bytes,
    )
    if reopened_identity != identity or canonical_json_bytes_v1(reopened) != raw:
        _fail(f"{label} exact reopen differs")
    return identity


def _roster(value: object, *, label: str) -> tuple[str, ...]:
    roster = tuple(
        _string(player_id, label=f"{label} player")
        for player_id in _sequence(value, label=label)
    )
    if len(roster) != 9 or len(set(roster)) != 9:
        _fail(f"{label} must contain exactly nine distinct player IDs")
    return roster


def _lineups(
    rows_value: object, *, label: str, hard230_identity_law: bool = False,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_rosters: set[tuple[str, ...]] = set()
    for ordinal, raw in enumerate(_sequence(rows_value, label=label)):
        row = _mapping(raw, label=f"{label}[{ordinal}]")
        lineup_id = _string(row.get("lineup_id"), label=f"{label} lineup ID")
        roster = _roster(row.get("roster_player_ids"), label=f"{label} roster")
        if lineup_id in seen_ids or roster in seen_rosters:
            _fail(f"{label} repeats a lineup ID or roster")
        roster_sha = canonical_sha256_v1(list(roster))
        if hard230_identity_law and (
            row.get("roster_sha256") != roster_sha
            or lineup_id != f"lineup-v1-{roster_sha}"
            or type(row.get("first_occurrence_ordinal")) is not int
            or int(row["first_occurrence_ordinal"]) < 0
        ):
            _fail(f"{label} hard230 lineup identity differs")
        seen_ids.add(lineup_id)
        seen_rosters.add(roster)
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster),
            "roster_sha256": roster_sha,
        })
    if not rows:
        _fail(f"{label} must contain at least one lineup")
    return rows


def _normalize_population_crossed_slate(
    result: Mapping[str, object],
) -> dict[str, object]:
    populations: list[dict[str, object]] = []
    books: list[dict[str, object]] = []
    for fold in result["fold_results"]:
        fold_ordinal = int(fold["fold_ordinal"])
        heldout_block = str(fold["heldout_block"])
        for profile in fold["profile_results"]:
            profile_id = str(profile["profile_id"])
            population_id = f"fold-{heldout_block}/profile-{profile_id}"
            lineups = _lineups(
                profile["sampled_candidate_rows"],
                label=f"{population_id} sampled candidates",
            )
            lineup_ids = [str(row["lineup_id"]) for row in lineups]
            if profile.get("sampled_lineup_ids") != lineup_ids:
                _fail("population-crossed sampled IDs/rosters differ")
            populations.append({
                "population_id": population_id,
                "dimensions": {
                    "fold_ordinal": fold_ordinal,
                    "heldout_block": heldout_block,
                    "profile_id": profile_id,
                },
                "lineups": lineups,
            })
            population_ids = set(lineup_ids)
            for descriptor in profile["evaluation_book_descriptors"]:
                family = str(descriptor["selector_family"])
                selector_ordinal = int(descriptor["selector_ordinal"])
                selector_id = str(descriptor["selector_id"])
                for prefix in descriptor["prefixes"]:
                    selected = [str(value) for value in prefix["selected_lineup_ids"]]
                    entry_budget = int(prefix["entry_budget"])
                    if (
                        len(selected) != entry_budget
                        or len(set(selected)) != entry_budget
                        or not set(selected) <= population_ids
                    ):
                        _fail("population-crossed selected book differs")
                    coordinate = {
                        "adapter_id": POPULATION_CROSSED_ADAPTER,
                        "metric_kind": "selected-book",
                        "heldout_block": heldout_block,
                        "profile_id": profile_id,
                        "selector_family": family,
                        "selector_ordinal": selector_ordinal,
                        "selector_id": selector_id,
                        "entry_budget": entry_budget,
                    }
                    books.append({
                        "coordinate": coordinate,
                        "coordinate_sha256": canonical_sha256_v1(coordinate),
                        "population_id": population_id,
                        "selected_lineup_ids": selected,
                    })
    if len({row["population_id"] for row in populations}) != len(populations):
        _fail("population-crossed population coordinates repeat")
    if len({row["coordinate_sha256"] for row in books}) != len(books):
        _fail("population-crossed metric coordinates repeat")
    later_identities = {
        canonical_json_bytes_v1(
            profile["evaluator_recipe"]["later_source_identity"]
        ): _identity(
            profile["evaluator_recipe"]["later_source_identity"],
            label="population-crossed later-source identity",
        )
        for fold in result["fold_results"]
        for profile in fold["profile_results"]
    }
    if len(later_identities) != 1:
        _fail("population-crossed later-source identities differ")
    return {
        "source_ordinal": int(result["source_ordinal"]),
        "slate_id": str(result["slate_id"]),
        "populations": populations,
        "books": books,
        "later_source_identity": next(iter(later_identities.values())),
    }


def _validate_hard230_population(
    value: object, *, expected_population_id: str, label: str,
) -> dict[str, object]:
    population = _mapping(value, label=label)
    lineups = _lineups(
        population.get("population_rosters"),
        label=f"{label} rosters",
        hard230_identity_law=True,
    )
    if (
        population.get("population_id") != expected_population_id
        or population.get("population_lineup_count") != len(lineups)
        or population.get("population_rosters_sha256")
        != canonical_sha256_v1(population.get("population_rosters"))
        or population.get("uses_heldout_scores") is not False
        or population.get("uses_realized_outcomes") is not False
    ):
        _fail(f"{label} population authority differs")
    return {
        "population_id": expected_population_id,
        "lineups": lineups,
    }


def _normalize_hard230_slate(
    *, task_result: Mapping[str, object], process_receipt: Mapping[str, object],
) -> dict[str, object]:
    scientific = _mapping(
        process_receipt.get("scientific_receipt"), label="hard230 scientific receipt"
    )
    target = _integer(
        scientific.get("target_retained_count"),
        label="hard230 target retained count",
        minimum=1,
    )
    if task_result.get("p0_target_count") != target:
        _fail("hard230 task/P0 target count differs")
    specs = (
        (
            hard_successor.CONTROL_POPULATION_ID,
            "score_blind_control_population",
            "score_blind_control_population_count",
            "score_blind_control_population_sha256",
        ),
        (
            hard_successor.CHALLENGER_POPULATION_ID,
            "hard230_challenger_population",
            "hard230_challenger_population_count",
            "hard230_challenger_population_sha256",
        ),
    )
    populations: list[dict[str, object]] = []
    for population_id, receipt_field, count_field, hash_field in specs:
        normalized = _validate_hard230_population(
            scientific.get(receipt_field),
            expected_population_id=population_id,
            label=f"hard230 {population_id}",
        )
        source_population = scientific[receipt_field]
        if (
            task_result.get(count_field) != source_population["population_lineup_count"]
            or task_result.get(hash_field) != source_population["population_rosters_sha256"]
        ):
            _fail("hard230 task/population summary differs")
        normalized["dimensions"] = {
            "population_id": population_id,
            "entry_budget": target,
        }
        populations.append(normalized)
    return {
        "source_ordinal": int(task_result["task_index"]),
        "slate_id": str(task_result["slate_id"]),
        "populations": populations,
        "books": [],
    }


def _descriptor(
    *, source_ordinal: int, slate_id: str, identity: Mapping[str, object],
    result_sha256: str,
) -> dict[str, object]:
    return {
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "task_result_identity": dict(identity),
        "task_result_sha256": result_sha256,
    }


def _open_population_crossed_terminal(
    *, task_manifest_identity: object, task_result_identities: object,
    read_exact: ReadExact,
) -> _OpenedTerminal:
    manifest_body, manifest_identity = _exact_read_json(
        task_manifest_identity,
        read_exact=read_exact,
        label="population-crossed task manifest",
        maximum_bytes=population_cloud.MAXIMUM_TASK_MANIFEST_BYTES,
    )
    try:
        manifest = population_cloud.validate_task_manifest_v1(manifest_body)
    except population_cloud.CorpusR6PopulationCrossedCloudV1Error as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc
    identities = [
        _identity(value, label=f"population-crossed task result[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(task_result_identities, label="task-result identities")
        )
    ]
    if len(identities) != SOURCE_SLATE_COUNT:
        _fail("population-crossed terminal requires exactly 54 task results")
    results: list[dict[str, object]] = []
    descriptors: list[dict[str, object]] = []
    slates: list[dict[str, object]] = []
    for ordinal, (identity, binding) in enumerate(
        zip(identities, manifest["task_bindings"], strict=True)
    ):
        body, retained_identity = _exact_read_json(
            identity,
            read_exact=read_exact,
            label=f"population-crossed task result[{ordinal}]",
            maximum_bytes=population_cloud.MAXIMUM_SLATE_RESULT_BYTES,
        )
        try:
            result = population_cloud.validate_slate_result_v1(body)
        except population_cloud.CorpusR6PopulationCrossedCloudV1Error as exc:
            raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc
        if (
            retained_identity["uri"] != binding["result_uri"]
            or result.get("source_ordinal") != ordinal
            or result.get("slate_id") != binding["slate_id"]
            or result.get("task_request_sha256") != binding["request_sha256"]
            or result.get("task_binding_sha256") != binding["task_binding_sha256"]
        ):
            _fail("population-crossed manifest/result binding differs")
        normalized = _normalize_population_crossed_slate(result)
        results.append(result)
        slates.append(normalized)
        descriptors.append(_descriptor(
            source_ordinal=ordinal,
            slate_id=str(result["slate_id"]),
            identity=retained_identity,
            result_sha256=str(result["slate_result_sha256"]),
        ))
    later_identities = {
        canonical_json_bytes_v1(slate["later_source_identity"]): slate[
            "later_source_identity"
        ]
        for slate in slates
    }
    if len(later_identities) != 1:
        _fail("population-crossed panel later-source identities differ")
    return _OpenedTerminal(
        adapter_id=POPULATION_CROSSED_ADAPTER,
        task_manifest=manifest,
        task_manifest_identity=manifest_identity,
        task_manifest_sha256=str(manifest["task_manifest_sha256"]),
        task_results=tuple(results),
        task_result_descriptors=tuple(descriptors),
        slates=tuple(slates),
        later_source_identity=next(iter(later_identities.values())),
    )


def _open_hard230_terminal(
    *, task_manifest_identity: object, task_result_identities: object,
    read_exact: ReadExact,
) -> _OpenedTerminal:
    manifest_body, manifest_identity = _exact_read_json(
        task_manifest_identity,
        read_exact=read_exact,
        label="hard230 task manifest",
        maximum_bytes=hard_cloud.MAXIMUM_MANIFEST_BYTES,
    )
    run_identity = _identity(
        manifest_body.get("run_authorization_identity"),
        label="hard230 run authorization",
    )
    run_body, retained_run_identity = _exact_read_json(
        run_identity,
        read_exact=read_exact,
        label="hard230 run authorization",
        maximum_bytes=hard_cloud.MAXIMUM_AUTHORITY_BYTES,
    )
    try:
        authorization = hard_cloud.validate_run_authorization_v1(run_body)
        manifest = hard_cloud.validate_task_manifest_v1(
            manifest_body, run_authorization=authorization
        )
    except hard_cloud.Hard230R6CloudEntrypointV1Error as exc:
        raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc
    if retained_run_identity != manifest["run_authorization_identity"]:
        _fail("hard230 manifest/run-authorization identity differs")
    identities = [
        _identity(value, label=f"hard230 task result[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(task_result_identities, label="task-result identities")
        )
    ]
    if len(identities) != SOURCE_SLATE_COUNT:
        _fail("hard230 terminal requires exactly 54 task results")
    results: list[dict[str, object]] = []
    descriptors: list[dict[str, object]] = []
    slates: list[dict[str, object]] = []
    for ordinal, (identity, task_row) in enumerate(
        zip(identities, manifest["task_rows"], strict=True)
    ):
        body, retained_identity = _exact_read_json(
            identity,
            read_exact=read_exact,
            label=f"hard230 task result[{ordinal}]",
            maximum_bytes=hard_cloud.MAXIMUM_TASK_RESULT_BYTES,
        )
        try:
            result = hard_cloud.validate_task_result_v1(body)
        except hard_cloud.Hard230R6CloudEntrypointV1Error as exc:
            raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc
        expected_result_uri = f"{task_row['task_output_prefix']}task-result.json"
        if (
            retained_identity["uri"] != expected_result_uri
            or result.get("task_index") != ordinal
            or result.get("slate_id") != task_row["slate_id"]
            or result.get("task_manifest_identity") != manifest_identity
            or result.get("task_manifest_sha256") != manifest["task_manifest_sha256"]
            or result.get("complete") is not True
        ):
            _fail("hard230 manifest/result binding differs")
        process_body, process_identity = _exact_read_json(
            result["process_receipt_identity"],
            read_exact=read_exact,
            label=f"hard230 process receipt[{ordinal}]",
            maximum_bytes=hard_process.MAX_ROOT_BYTES,
        )
        try:
            process_receipt = hard_process.validate_process_receipt_v1(process_body)
        except hard_process.Hard230PopulationProcessV1Error as exc:
            raise CorpusR6NovelRosterRealizedGraderV1Error(str(exc)) from exc
        if (
            process_identity != result["process_receipt_identity"]
            or process_receipt.get("process_receipt_sha256")
            != result["process_receipt_sha256"]
            or process_receipt.get("task_index") != ordinal
            or process_receipt.get("slate_id") != task_row["slate_id"]
            or process_receipt.get("create_once_exact_reopen_completed") is not True
        ):
            _fail("hard230 task/process terminal binding differs")
        normalized = _normalize_hard230_slate(
            task_result=result, process_receipt=process_receipt
        )
        results.append(result)
        slates.append(normalized)
        descriptors.append(_descriptor(
            source_ordinal=ordinal,
            slate_id=str(result["slate_id"]),
            identity=retained_identity,
            result_sha256=str(result["task_result_sha256"]),
        ))
    later_source_identity = _identity(
        manifest["later_source_freeze_identity"],
        label="hard230 later-source identity",
    )
    return _OpenedTerminal(
        adapter_id=HARD230_ADAPTER,
        task_manifest=manifest,
        task_manifest_identity=manifest_identity,
        task_manifest_sha256=str(manifest["task_manifest_sha256"]),
        task_results=tuple(results),
        task_result_descriptors=tuple(descriptors),
        slates=tuple(slates),
        later_source_identity=later_source_identity,
    )


_ADAPTER_REGISTRY: Final = {
    POPULATION_CROSSED_ADAPTER: _open_population_crossed_terminal,
    HARD230_ADAPTER: _open_hard230_terminal,
}


def _open_terminal_sources(
    *, adapter_id: str, task_manifest_identity: object,
    task_result_identities: object, read_exact: ReadExact,
) -> _OpenedTerminal:
    adapter = _ADAPTER_REGISTRY.get(adapter_id)
    if adapter is None:
        _fail(f"unknown novel-roster adapter: {adapter_id!r}")
    return adapter(
        task_manifest_identity=task_manifest_identity,
        task_result_identities=task_result_identities,
        read_exact=read_exact,
    )


def build_terminal_experiment_root_v1(
    *, adapter_id: str, task_manifest_identity: object,
    task_manifest_sha256: str, task_result_descriptors: object,
) -> dict[str, object]:
    """Build the pure create-last root after all adapter validation succeeds."""
    if adapter_id not in ADAPTER_IDS:
        _fail("terminal root adapter differs")
    manifest_identity = _identity(
        task_manifest_identity, label="terminal task manifest"
    )
    retained_manifest_sha = _digest(
        task_manifest_sha256, label="terminal task-manifest SHA-256"
    )
    descriptors: list[dict[str, object]] = []
    seen_slates: set[str] = set()
    seen_identities: set[bytes] = set()
    for ordinal, raw in enumerate(
        _sequence(task_result_descriptors, label="terminal task results")
    ):
        row = _mapping(raw, label=f"terminal task result[{ordinal}]")
        if set(row) != {
            "source_ordinal", "slate_id", "task_result_identity",
            "task_result_sha256",
        }:
            _fail("terminal task-result descriptor fields differ")
        slate_id = _string(row.get("slate_id"), label="terminal slate ID")
        identity = _identity(
            row.get("task_result_identity"), label="terminal task-result identity"
        )
        result_sha = _digest(
            row.get("task_result_sha256"), label="terminal task-result SHA-256"
        )
        identity_key = canonical_json_bytes_v1(identity)
        if (
            row.get("source_ordinal") != ordinal
            or slate_id in seen_slates
            or identity_key in seen_identities
        ):
            _fail("terminal task-result order, identity, or SHA differs")
        seen_slates.add(slate_id)
        seen_identities.add(identity_key)
        descriptors.append(_descriptor(
            source_ordinal=ordinal,
            slate_id=slate_id,
            identity=identity,
            result_sha256=result_sha,
        ))
    if len(descriptors) != SOURCE_SLATE_COUNT:
        _fail("terminal root requires exactly 54 validated task results")
    body = {
        "schema_version": TERMINAL_ROOT_SCHEMA,
        "adapter_id": adapter_id,
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": retained_manifest_sha,
        "source_slate_count": SOURCE_SLATE_COUNT,
        "task_results": descriptors,
        "task_results_sha256": canonical_sha256_v1(descriptors),
        "complete": True,
        "all_task_results_exact_opened": True,
        "all_task_results_adapter_validated": True,
        "root_built_after_all_task_results": True,
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="terminal_experiment_root_sha256")


def validate_terminal_experiment_root_v1(value: object) -> dict[str, object]:
    root = _mapping(value, label="novel-roster terminal root")
    expected_fields = {
        "schema_version", "adapter_id", "task_manifest_identity",
        "task_manifest_sha256", "source_slate_count", "task_results",
        "task_results_sha256", "complete", "all_task_results_exact_opened",
        "all_task_results_adapter_validated", "root_built_after_all_task_results",
        "uses_realized_outcomes", "historical_scoring_performed",
        "decision_authority", "terminal_experiment_root_sha256",
    }
    if set(root) != expected_fields:
        _fail("novel-roster terminal root fields differ")
    _self_hash(
        root, field="terminal_experiment_root_sha256",
        label="novel-roster terminal root",
    )
    expected = build_terminal_experiment_root_v1(
        adapter_id=str(root.get("adapter_id", "")),
        task_manifest_identity=root.get("task_manifest_identity"),
        task_manifest_sha256=str(root.get("task_manifest_sha256", "")),
        task_result_descriptors=root.get("task_results"),
    )
    if (
        canonical_json_bytes_v1(root) != canonical_json_bytes_v1(expected)
        or root.get("source_slate_count") != SOURCE_SLATE_COUNT
        or root.get("complete") is not True
        or root.get("all_task_results_exact_opened") is not True
        or root.get("all_task_results_adapter_validated") is not True
        or root.get("root_built_after_all_task_results") is not True
        or root.get("uses_realized_outcomes") is not False
        or root.get("historical_scoring_performed") is not False
        or root.get("decision_authority") is not False
    ):
        _fail("novel-roster terminal root law differs")
    return expected


def publish_terminal_experiment_root_v1(
    *, adapter_id: str, task_manifest_identity: object,
    task_result_identities: object, target_uri: str, read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate all 54 score-free results, then publish one root create-once."""
    opened = _open_terminal_sources(
        adapter_id=adapter_id,
        task_manifest_identity=task_manifest_identity,
        task_result_identities=task_result_identities,
        read_exact=read_exact,
    )
    root = build_terminal_experiment_root_v1(
        adapter_id=adapter_id,
        task_manifest_identity=opened.task_manifest_identity,
        task_manifest_sha256=opened.task_manifest_sha256,
        task_result_descriptors=opened.task_result_descriptors,
    )
    identity = _publish_json_create_once(
        uri=target_uri,
        value=root,
        maximum_bytes=MAXIMUM_ROOT_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="novel-roster terminal root",
    )
    return root, identity


def reopen_terminal_experiment_v1(
    *, terminal_root_identity: object, read_terminal_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], _OpenedTerminal]:
    """Prove the create-last root and every score-free predecessor."""
    root_body, root_identity = _exact_read_json(
        terminal_root_identity,
        read_exact=read_terminal_exact,
        label="novel-roster terminal root",
        maximum_bytes=MAXIMUM_ROOT_BYTES,
    )
    root = validate_terminal_experiment_root_v1(root_body)
    opened = _open_terminal_sources(
        adapter_id=str(root["adapter_id"]),
        task_manifest_identity=root["task_manifest_identity"],
        task_result_identities=[
            row["task_result_identity"] for row in root["task_results"]
        ],
        read_exact=read_terminal_exact,
    )
    if (
        opened.task_manifest_identity != root["task_manifest_identity"]
        or opened.task_manifest_sha256 != root["task_manifest_sha256"]
        or list(opened.task_result_descriptors) != root["task_results"]
        or len(opened.slates) != SOURCE_SLATE_COUNT
    ):
        _fail("terminal root exact predecessor replay differs")
    return root, root_identity, opened


def _open_outcome_snapshot_surface(
    *, outcome_snapshot_identity: object, read_outcome_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[tuple[int, str], int],
    dict[int, tuple[int, int, str]],
]:
    snapshot, identity = _exact_read_json(
        outcome_snapshot_identity,
        read_exact=read_outcome_exact,
        label="realized player-outcome snapshot",
        maximum_bytes=MAXIMUM_OUTCOME_SNAPSHOT_BYTES,
    )
    if set(snapshot) != _SNAPSHOT_FIELDS:
        _fail("outcome snapshot fields differ")
    _self_hash(snapshot, field="outcome_snapshot_sha256", label="outcome snapshot")
    for field in (
        "outcome_key_projection_identity", "panel_freeze_identity",
        "later_source_freeze_identity", "realized_source_identity",
    ):
        _identity(snapshot.get(field), label=f"outcome snapshot {field}")
    for field in (
        "outcome_key_projection_sha256", "panel_freeze_sha256",
        "later_source_freeze_sha256", "realized_source_sha256",
    ):
        _digest(snapshot.get(field), label=f"outcome snapshot {field}")
    rows = [
        _mapping(raw, label=f"outcome snapshot row[{ordinal}]")
        for ordinal, raw in enumerate(_sequence(snapshot.get("rows"), label="snapshot rows"))
    ]
    score_map: dict[tuple[int, str], int] = {}
    slate_keys: dict[int, tuple[int, int, str]] = {}
    row_keys: list[dict[str, object]] = []
    for ordinal, row in enumerate(rows):
        if set(row) != _SNAPSHOT_ROW_FIELDS:
            _fail(f"outcome snapshot row[{ordinal}] fields differ")
        source_ordinal = _integer(
            row.get("source_ordinal"), label="snapshot source ordinal", minimum=0
        )
        if source_ordinal >= SOURCE_SLATE_COUNT:
            _fail("snapshot source ordinal lies outside the 54-slate panel")
        season = _integer(row.get("season"), label="snapshot season", minimum=2000)
        week = _integer(row.get("week"), label="snapshot week", minimum=1)
        slate_id = _string(row.get("slate_id"), label="snapshot slate ID")
        player_id = _string(row.get("player_id"), label="snapshot player ID")
        score = _integer(row.get("realized_score_micro"), label="snapshot score")
        key = (source_ordinal, player_id)
        slate_key = (season, week, slate_id)
        if key in score_map or (
            source_ordinal in slate_keys and slate_keys[source_ordinal] != slate_key
        ):
            _fail("outcome snapshot repeats or splits one player/slate key")
        score_map[key] = score
        slate_keys[source_ordinal] = slate_key
        row_keys.append({key_name: row[key_name] for key_name in (
            "source_ordinal", "season", "week", "slate_id", "player_id"
        )})
    if (
        snapshot.get("schema_version") != outcomes.OUTCOME_SNAPSHOT_SCHEMA
        or snapshot.get("score_unit") != "micro_dk"
        or snapshot.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or snapshot.get("row_count") != len(rows)
        or snapshot.get("row_keys_sha256") != canonical_sha256_v1(row_keys)
        or snapshot.get("rows_sha256") != canonical_sha256_v1(rows)
        or set(slate_keys) != set(range(SOURCE_SLATE_COUNT))
        or snapshot.get("exact_union_coverage") is not True
        or snapshot.get("lineup_scoring_performed") is not False
        or snapshot.get("full_field_standings_included") is not False
        or snapshot.get("payout_ladder_included") is not False
        or snapshot.get("graph_mutation_licensed") is not False
        or snapshot.get("production_change_licensed") is not False
        or snapshot.get("decision_authority") is not False
    ):
        _fail("outcome snapshot fixed law differs")
    return snapshot, identity, score_map, slate_keys


def _rational(numerator: int, denominator: int, *, unit: str) -> dict[str, object]:
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        _fail("exact rational inputs differ")
    return {"numerator": numerator, "denominator": denominator, "unit": unit}


def _threshold_metrics(
    *, population_scores: Sequence[int], selected_scores: Sequence[int] | None,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for threshold in THRESHOLDS_DK:
        threshold_micro = threshold * MICRO_DK_PER_POINT
        population_hits = sum(score >= threshold_micro for score in population_scores)
        selected_hits = (
            None
            if selected_scores is None
            else sum(score >= threshold_micro for score in selected_scores)
        )
        rows.append({
            "threshold_dk": threshold,
            "threshold_micro": threshold_micro,
            "operator": ">=",
            "population_lineup_hit_count": population_hits,
            "population_produced_at_least_one_hit": population_hits > 0,
            "selected_lineup_hit_count": selected_hits,
            "selected_produced_at_least_one_hit": (
                None if selected_hits is None else selected_hits > 0
            ),
        })
    return rows


def _score_normalized_slates(
    *, slates: Sequence[Mapping[str, object]], player_scores: Mapping[tuple[int, str], int],
) -> list[dict[str, object]]:
    grades: list[dict[str, object]] = []
    for expected_ordinal, raw_slate in enumerate(slates):
        slate = _mapping(raw_slate, label=f"normalized slate[{expected_ordinal}]")
        source_ordinal = int(slate["source_ordinal"])
        slate_id = str(slate["slate_id"])
        if source_ordinal != expected_ordinal:
            _fail("normalized slate ordinals differ")
        populations = {
            str(population["population_id"]): population
            for population in slate["populations"]
        }
        if len(populations) != len(slate["populations"]):
            _fail("normalized population IDs repeat")
        roster_by_id: dict[str, tuple[str, ...]] = {}
        for population in populations.values():
            for lineup in population["lineups"]:
                lineup_id = str(lineup["lineup_id"])
                roster = tuple(str(value) for value in lineup["roster_player_ids"])
                prior = roster_by_id.setdefault(lineup_id, roster)
                if prior != roster:
                    _fail("one lineup ID maps to multiple rosters")
        roster_score_cache: dict[tuple[str, ...], int] = {}
        for roster in sorted(set(roster_by_id.values())):
            try:
                roster_score_cache[roster] = sum(
                    int(player_scores[(source_ordinal, player_id)])
                    for player_id in roster
                )
            except KeyError as exc:
                missing = exc.args[0]
                _fail(
                    f"outcome snapshot lacks novel-roster player key {missing!r}"
                )
        lineup_scores = {
            lineup_id: roster_score_cache[roster]
            for lineup_id, roster in roster_by_id.items()
        }
        score_rows = [{
            "lineup_id": lineup_id,
            "roster_sha256": canonical_sha256_v1(list(roster_by_id[lineup_id])),
            "realized_score_micro": lineup_scores[lineup_id],
        } for lineup_id in sorted(lineup_scores)]
        books_by_population: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for book in slate["books"]:
            books_by_population[str(book["population_id"])].append(book)
        metrics: list[dict[str, object]] = []
        for population_id, population in populations.items():
            population_ids = [str(row["lineup_id"]) for row in population["lineups"]]
            population_values = [lineup_scores[lineup_id] for lineup_id in population_ids]
            ceiling = max(population_values)
            population_max_ids = [
                lineup_id for lineup_id in population_ids
                if lineup_scores[lineup_id] == ceiling
            ]
            books = books_by_population.get(population_id, [])
            if not books:
                dimensions = dict(population.get("dimensions", {}))
                coordinate = {
                    "adapter_id": HARD230_ADAPTER,
                    "metric_kind": "population-only",
                    **dimensions,
                }
                metrics.append({
                    "coordinate": coordinate,
                    "coordinate_sha256": canonical_sha256_v1(coordinate),
                    "population_id": population_id,
                    "entry_budget": int(dimensions["entry_budget"]),
                    "population_lineup_count": len(population_ids),
                    "selected_lineup_count": None,
                    "population_ceiling_micro": ceiling,
                    "population_ceiling_lineup_ids": population_max_ids,
                    "selected_weekly_maximum_micro": None,
                    "weekly_maximum_micro": ceiling,
                    "population_ceiling_converted": None,
                    "population_ceiling_regret_micro": None,
                    "thresholds": _threshold_metrics(
                        population_scores=population_values,
                        selected_scores=None,
                    ),
                })
                continue
            for book in books:
                selected_ids = [str(value) for value in book["selected_lineup_ids"]]
                if not selected_ids or not set(selected_ids) <= set(population_ids):
                    _fail("normalized selected book lies outside its population")
                selected_values = [lineup_scores[lineup_id] for lineup_id in selected_ids]
                selected_maximum = max(selected_values)
                metrics.append({
                    "coordinate": dict(book["coordinate"]),
                    "coordinate_sha256": str(book["coordinate_sha256"]),
                    "population_id": population_id,
                    "entry_budget": int(book["coordinate"]["entry_budget"]),
                    "population_lineup_count": len(population_ids),
                    "selected_lineup_count": len(selected_ids),
                    "population_ceiling_micro": ceiling,
                    "population_ceiling_lineup_ids": population_max_ids,
                    "selected_weekly_maximum_micro": selected_maximum,
                    "weekly_maximum_micro": selected_maximum,
                    "population_ceiling_converted": selected_maximum == ceiling,
                    "population_ceiling_regret_micro": ceiling - selected_maximum,
                    "thresholds": _threshold_metrics(
                        population_scores=population_values,
                        selected_scores=selected_values,
                    ),
                })
        metrics.sort(key=lambda row: str(row["coordinate_sha256"]))
        body = {
            "schema_version": SLATE_GRADE_SCHEMA,
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "unique_lineup_id_count": len(roster_by_id),
            "unique_roster_count": len(roster_score_cache),
            "roster_sum_operation_count": len(roster_score_cache),
            "lineup_score_rows": score_rows,
            "lineup_score_rows_sha256": canonical_sha256_v1(score_rows),
            "metric_count": len(metrics),
            "metrics": metrics,
            "metrics_sha256": canonical_sha256_v1(metrics),
            "every_distinct_roster_scored_once": True,
            "all_metrics_projected_from_score_lookup": True,
            "complete": True,
        }
        grades.append(_with_hash(body, field="slate_grade_sha256"))
    return grades


def _aggregate_cells(slate_grades: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[tuple[int, str, Mapping[str, object]]]] = defaultdict(list)
    for slate in slate_grades:
        for metric in slate["metrics"]:
            grouped[str(metric["coordinate_sha256"])].append((
                int(slate["source_ordinal"]), str(slate["slate_id"]), metric
            ))
    cells: list[dict[str, object]] = []
    for coordinate_sha in sorted(grouped):
        rows = sorted(grouped[coordinate_sha], key=lambda value: value[0])
        if [row[0] for row in rows] != list(range(SOURCE_SLATE_COUNT)):
            _fail("one aggregate metric coordinate lacks exact 54-slate coverage")
        coordinate = dict(rows[0][2]["coordinate"])
        if any(
            row[2]["coordinate"] != coordinate
            or row[2]["coordinate_sha256"] != coordinate_sha
            for row in rows
        ):
            _fail("aggregate metric coordinate differs across slates")
        weekly_maxima = [int(row[2]["weekly_maximum_micro"]) for row in rows]
        ceilings = [int(row[2]["population_ceiling_micro"]) for row in rows]
        selected_available = rows[0][2]["selected_weekly_maximum_micro"] is not None
        if any(
            (row[2]["selected_weekly_maximum_micro"] is not None)
            != selected_available
            for row in rows
        ):
            _fail("selection availability differs within one aggregate cell")
        threshold_rows: list[dict[str, object]] = []
        for threshold_index, threshold in enumerate(THRESHOLDS_DK):
            source_rows = [row[2]["thresholds"][threshold_index] for row in rows]
            population_lineup_hits = sum(
                int(row["population_lineup_hit_count"]) for row in source_rows
            )
            selected_lineup_hits = (
                None
                if not selected_available
                else sum(int(row["selected_lineup_hit_count"]) for row in source_rows)
            )
            threshold_rows.append({
                "threshold_dk": threshold,
                "threshold_micro": threshold * MICRO_DK_PER_POINT,
                "operator": ">=",
                "population_lineup_hit_count": population_lineup_hits,
                "population_slates_with_at_least_one_hit": sum(
                    bool(row["population_produced_at_least_one_hit"])
                    for row in source_rows
                ),
                "selected_lineup_hit_count": selected_lineup_hits,
                "selected_slates_with_at_least_one_hit": (
                    None
                    if not selected_available
                    else sum(
                        bool(row["selected_produced_at_least_one_hit"])
                        for row in source_rows
                    )
                ),
            })
        slate_rows = [{
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "entry_budget": metric["entry_budget"],
            "population_lineup_count": metric["population_lineup_count"],
            "selected_lineup_count": metric["selected_lineup_count"],
            "population_ceiling_micro": metric["population_ceiling_micro"],
            "selected_weekly_maximum_micro": metric[
                "selected_weekly_maximum_micro"
            ],
            "weekly_maximum_micro": metric["weekly_maximum_micro"],
            "population_ceiling_converted": metric[
                "population_ceiling_converted"
            ],
            "population_ceiling_regret_micro": metric[
                "population_ceiling_regret_micro"
            ],
        } for source_ordinal, slate_id, metric in rows]
        body = {
            "schema_version": AGGREGATE_CELL_SCHEMA,
            "coordinate": coordinate,
            "coordinate_sha256": coordinate_sha,
            "source_slate_count": SOURCE_SLATE_COUNT,
            "slate_rows": slate_rows,
            "slate_rows_sha256": canonical_sha256_v1(slate_rows),
            "mean_weekly_maximum_micro": _rational(
                sum(weekly_maxima), SOURCE_SLATE_COUNT, unit="micro_dk"
            ),
            "mean_population_ceiling_micro": _rational(
                sum(ceilings), SOURCE_SLATE_COUNT, unit="micro_dk"
            ),
            "thresholds": threshold_rows,
            "selection_conversion_available": selected_available,
            "population_ceiling_conversion_count": (
                None
                if not selected_available
                else sum(bool(row[2]["population_ceiling_converted"]) for row in rows)
            ),
            "population_ceiling_conversion_fraction": (
                None
                if not selected_available
                else _rational(
                    sum(bool(row[2]["population_ceiling_converted"]) for row in rows),
                    SOURCE_SLATE_COUNT,
                    unit="slates",
                )
            ),
            "mean_population_ceiling_regret_micro": (
                None
                if not selected_available
                else _rational(
                    sum(int(row[2]["population_ceiling_regret_micro"]) for row in rows),
                    SOURCE_SLATE_COUNT,
                    unit="micro_dk",
                )
            ),
            "complete": True,
        }
        cells.append(_with_hash(body, field="aggregate_cell_sha256"))
    if not cells:
        _fail("realized grade contains no aggregate metric cells")
    return cells


def grade_novel_roster_experiment_realized_v1(
    *, terminal_root_identity: object, outcome_snapshot_identity: object,
    read_terminal_exact: ReadExact, read_outcome_exact: ReadExact,
) -> dict[str, object]:
    """Prove terminality, then exact-open outcomes and grade novel rosters."""
    # This call and every adapter predecessor read must finish before the first
    # invocation of the separately injected outcome reader below.
    root, root_identity, opened = reopen_terminal_experiment_v1(
        terminal_root_identity=terminal_root_identity,
        read_terminal_exact=read_terminal_exact,
    )
    snapshot, snapshot_identity, player_scores, slate_keys = (
        _open_outcome_snapshot_surface(
            outcome_snapshot_identity=outcome_snapshot_identity,
            read_outcome_exact=read_outcome_exact,
        )
    )
    if snapshot.get("later_source_freeze_identity") != opened.later_source_identity:
        _fail("terminal experiment/outcome later-source identity differs")
    for source_ordinal, slate in enumerate(opened.slates):
        if slate_keys[source_ordinal][2] != slate["slate_id"]:
            _fail("terminal experiment/outcome slate identity differs")
    slate_grades = _score_normalized_slates(
        slates=opened.slates, player_scores=player_scores
    )
    aggregates = _aggregate_cells(slate_grades)
    body = {
        "schema_version": REALIZED_GRADE_SCHEMA,
        "adapter_id": opened.adapter_id,
        "terminal_root_identity": root_identity,
        "terminal_root_sha256": root["terminal_experiment_root_sha256"],
        "task_manifest_identity": opened.task_manifest_identity,
        "task_manifest_sha256": opened.task_manifest_sha256,
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "later_source_freeze_identity": opened.later_source_identity,
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "threshold_registry": [{
            "threshold_dk": threshold,
            "threshold_micro": threshold * MICRO_DK_PER_POINT,
            "operator": ">=",
        } for threshold in THRESHOLDS_DK],
        "source_slate_count": SOURCE_SLATE_COUNT,
        "slate_grade_count": len(slate_grades),
        "slate_grades": slate_grades,
        "slate_grades_sha256": canonical_sha256_v1(slate_grades),
        "aggregate_cell_count": len(aggregates),
        "aggregate_cells": aggregates,
        "aggregate_cells_sha256": canonical_sha256_v1(aggregates),
        "roster_sum_operation_count": sum(
            int(row["roster_sum_operation_count"]) for row in slate_grades
        ),
        "every_distinct_roster_scored_once_per_slate": True,
        "terminal_before_first_outcome_read": True,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "decision_authority": False,
        "complete": True,
    }
    return _with_hash(body, field="realized_grade_sha256")


def grade_and_publish_novel_roster_experiment_realized_v1(
    *, terminal_root_identity: object, outcome_snapshot_identity: object,
    target_uri: str, read_terminal_exact: ReadExact,
    read_outcome_exact: ReadExact, publish_create_once: PublishCreateOnce,
) -> tuple[dict[str, object], dict[str, object]]:
    """Grade only after terminal replay, then publish the scorecard create-once."""
    grade = grade_novel_roster_experiment_realized_v1(
        terminal_root_identity=terminal_root_identity,
        outcome_snapshot_identity=outcome_snapshot_identity,
        read_terminal_exact=read_terminal_exact,
        read_outcome_exact=read_outcome_exact,
    )
    identity = _publish_json_create_once(
        uri=target_uri,
        value=grade,
        maximum_bytes=MAXIMUM_REALIZED_GRADE_BYTES,
        publish_create_once=publish_create_once,
        read_exact=read_terminal_exact,
        label="novel-roster realized scorecard",
    )
    return grade, identity


__all__ = [
    "ADAPTER_IDS",
    "AGGREGATE_CELL_SCHEMA",
    "CorpusR6NovelRosterRealizedGraderV1Error",
    "FIXED_GCP_PROJECT",
    "FIXED_STORAGE_ENDPOINT",
    "HARD230_ADAPTER",
    "POPULATION_CROSSED_ADAPTER",
    "REALIZED_GRADE_SCHEMA",
    "SLATE_GRADE_SCHEMA",
    "SOURCE_SLATE_COUNT",
    "TERMINAL_ROOT_SCHEMA",
    "THRESHOLDS_DK",
    "build_terminal_experiment_root_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "grade_novel_roster_experiment_realized_v1",
    "grade_and_publish_novel_roster_experiment_realized_v1",
    "publish_terminal_experiment_root_v1",
    "reopen_terminal_experiment_v1",
    "validate_terminal_experiment_root_v1",
]
