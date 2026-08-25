"""Frozen, outcome-blind execution manifest for the 54-slate T230 panel.

This module is intentionally a pure contract seam.  It validates the already
published Foundry v12 panel projection, binds that exact generation-pinned
object to the frozen T230 science, and derives one immutable output pair for
each accepted source ordinal.  It owns no object-store client, outcome reader,
selector execution, publisher, retry path, graph writer, or decision authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_support_switch as support
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_v12_panel_index as panel
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    VISITS_PER_BLOCK as LEGAL_VISITS_PER_BLOCK,
)


PANEL_EXECUTION_MANIFEST_SCHEMA: Final = (
    "foundry-t230-panel-execution-manifest/v1"
)
PUBLICATION_MODE: Final = "create_once"
RANKING_PREFIX_LAW: Final = "exact-prefix-of-one-deterministic-rank-80"
RESULT_FILENAME: Final = "foundry-t230-slate-analysis-v1.json"
ACCEPTANCE_FILENAME: Final = "foundry-t230-slate-acceptance-v1.json"

# These are protocol literals, not aliases for sibling-module constants.
# Every imported dependency is checked against them before a manifest can be
# built so coherent dependency drift cannot redefine the frozen experiment.
AUTHORITATIVE_SLATE_COUNT: Final = 54
SOURCE_ARM_ORDER: Final = (
    "incumbent",
    "remove-salary-floor",
    "remove-qb-stack",
    "remove-bring-back",
    "allow-rb-vs-dst",
    "allow-two-rb",
    "remove-all-five-shared-constraints",
)
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
VISITS_PER_BLOCK: Final = 200
DOSE_SHAPE: Final = (7, 5, 200)
TOTAL_VISIT_COUNT: Final = 7_000
FOLD_MINIMUM_OPPORTUNITY_WORLDS: Final = 100
FINAL_MINIMUM_OPPORTUNITY_WORLDS: Final = 125
SUPPORT_NUMERATOR: Final = 4
SUPPORT_DENOMINATOR: Final = 5
AUTHORITATIVE_FOLD_GATE_COUNT: Final = 270
AUTHORITATIVE_FINAL_GATE_COUNT: Final = 54
FOLD_PASS_MINIMUM: Final = 216
FINAL_PASS_MINIMUM: Final = 44
_FROZEN_LANE_LATTICE: Final = (
    {
        "lane_ordinal": 0,
        "lane_id": "v12a",
        "batch_mode": "lane-a-28-task",
        "task_count": 28,
        "source_task_offset": 0,
    },
    {
        "lane_ordinal": 1,
        "lane_id": "v12b",
        "batch_mode": "lane-b-26-task",
        "task_count": 26,
        "source_task_offset": 28,
    },
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_CANONICAL_SLATE_ID: Final = re.compile(r"[a-z0-9][a-z0-9._-]*")

_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)
_FALSE_PANEL_AUTHORITY_FIELDS: Final = tuple(
    field for field in _FALSE_AUTHORITY_FIELDS if field != "r6_freeze_authority"
)
_PANEL_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "panel_id",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "lane_count",
    "lanes",
    "accepted_slate_count",
    "accepted_slates",
    "exclusions",
    "failures",
    "missing_tasks",
    "coverage",
    *_FALSE_PANEL_AUTHORITY_FIELDS,
    "panel_index_sha256",
})
_PANEL_MEMBER_KEYS: Final = frozenset({
    "slate_id",
    "lane_ordinal",
    "lane_id",
    "task_ordinal",
    "source_task_ordinal",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "arms",
})
_PANEL_ARM_KEYS: Final = frozenset({
    "arm_ordinal",
    "parameter_set_id",
    "result_identity",
})
_PANEL_LANE_KEYS: Final = frozenset({
    "lane_ordinal",
    "lane_id",
    "terminal_receipt_identity",
    "batch_completion_identity",
    "batch_id",
    "batch_mode",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "source_task_offset",
    "expected_task_count",
    "accepted_task_count",
    "accepted_task_ordinals",
    "task_acceptance_identities_sha256",
    "carrier_identities_sha256",
    "complete",
})
_PANEL_COVERAGE_KEYS: Final = frozenset({
    "expected_task_count",
    "accepted_task_count",
    "excluded_task_count",
    "failed_task_count",
    "missing_task_count",
    "complete",
})
_SOURCE_MEMBER_KEYS: Final = frozenset({
    "source_ordinal",
    "slate_id",
    "panel_member_sha256",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "result_uri",
    "acceptance_uri",
})
_MANIFEST_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "manifest_id",
    "panel_object_identity",
    "panel_id",
    "panel_index_sha256",
    "panel_accepted_slates_sha256",
    "source_member_count",
    "source_members",
    "source_members_sha256",
    "source_arm_order",
    "source_arm_order_sha256",
    "ordinary_r_world_contract",
    "authoritative_generation_dose",
    "t230_retrieval_contract",
    "support_contract",
    "source_commit_sha",
    "immutable_image",
    "output_prefix",
    *_FALSE_AUTHORITY_FIELDS,
    "execution_manifest_sha256",
})


class CorpusExtremeTailPanelReleaseError(ValueError):
    """The T230 execution manifest cannot be frozen without exact replay."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailPanelReleaseError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _canonical_slate_id(value: object, *, label: str) -> str:
    if type(value) is not str or _CANONICAL_SLATE_ID.fullmatch(value) is None:
        _fail(f"{label} must be a canonical slate id")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailPanelReleaseError(
            f"{label} is not a generation-pinned object identity"
        ) from exc


def _identity_key(value: Mapping[str, object]) -> tuple[str, str, str, int]:
    return (
        str(value["uri"]),
        str(value["generation"]),
        str(value["sha256"]),
        int(value["bytes"]),
    )


def _image(value: object) -> dict[str, str]:
    try:
        return batch.normalize_image_identity(value, label="immutable image")
    except Exception as exc:
        raise CorpusExtremeTailPanelReleaseError(
            "immutable image must be digest-pinned"
        ) from exc


def _output_prefix(value: object) -> str:
    if type(value) is not str or not value.startswith("gs://"):
        _fail("output prefix must be a GCS prefix")
    tail = value.removeprefix("gs://")
    bucket_name, separator, object_name = tail.partition("/")
    if (
        not bucket_name
        or not separator
        or not object_name
        or not value.endswith("/")
        or "//" in object_name
        or "\\" in value
        or any(character.isspace() for character in value)
        or any(character in value for character in "?#")
    ):
        _fail("output prefix is not canonical")
    segments = object_name.split("/")[:-1]
    if not segments or any(segment in {"", ".", ".."} for segment in segments):
        _fail("output prefix is not canonical")
    return value


def _false_authorities(
    value: Mapping[str, object],
    *,
    label: str,
    fields: Sequence[str] = _FALSE_AUTHORITY_FIELDS,
) -> None:
    for field in fields:
        if value.get(field) is not False:
            _fail(f"{label}.{field} must be false")


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = _sha256(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _validate_frozen_dependency_constants() -> None:
    """Require sibling contracts to retain every literal protocol dimension."""
    imported_lanes = tuple(panel.V12_LANE_LATTICE)
    if (
        SOURCE_ARM_ORDER
        != (
            "incumbent",
            "remove-salary-floor",
            "remove-qb-stack",
            "remove-bring-back",
            "allow-rb-vs-dst",
            "allow-two-rb",
            "remove-all-five-shared-constraints",
        )
        or WORLD_BLOCKS != ("R0", "R1", "R2", "R3", "R4")
        or WORLDS_PER_BLOCK != 10_000
        or VISITS_PER_BLOCK != 200
        or DOSE_SHAPE != (7, 5, 200)
        or TOTAL_VISIT_COUNT != 7_000
        or DOSE_SHAPE
        != (len(SOURCE_ARM_ORDER), len(WORLD_BLOCKS), VISITS_PER_BLOCK)
        or TOTAL_VISIT_COUNT
        != len(SOURCE_ARM_ORDER) * len(WORLD_BLOCKS) * VISITS_PER_BLOCK
        or (
            FOLD_MINIMUM_OPPORTUNITY_WORLDS,
            FINAL_MINIMUM_OPPORTUNITY_WORLDS,
            SUPPORT_NUMERATOR,
            SUPPORT_DENOMINATOR,
            AUTHORITATIVE_SLATE_COUNT,
            AUTHORITATIVE_FOLD_GATE_COUNT,
            AUTHORITATIVE_FINAL_GATE_COUNT,
            FOLD_PASS_MINIMUM,
            FINAL_PASS_MINIMUM,
        )
        != (100, 125, 4, 5, 54, 270, 54, 216, 44)
        or sum(int(row["task_count"]) for row in _FROZEN_LANE_LATTICE)
        != AUTHORITATIVE_SLATE_COUNT
        or tuple(batch.PARAMETER_SET_ORDER) != SOURCE_ARM_ORDER
        or tuple(census.SOURCE_ARM_ORDER) != SOURCE_ARM_ORDER
        or census.SOURCE_ARM_ORDER_SHA256
        != batch.canonical_sha256(list(SOURCE_ARM_ORDER))
        or tuple(rw.WORLD_BLOCKS) != WORLD_BLOCKS
        or rw.WORLDS_PER_BLOCK != WORLDS_PER_BLOCK
        or batch.WORLDS_PER_BLOCK != WORLDS_PER_BLOCK
        or retrieval.WORLDS_PER_BLOCK != WORLDS_PER_BLOCK
        or LEGAL_VISITS_PER_BLOCK != VISITS_PER_BLOCK
        or census.VISITS_PER_BLOCK != VISITS_PER_BLOCK
        or batch.SOLVE_ATTEMPTS_PER_BLOCK != VISITS_PER_BLOCK
        or panel.V12_SOURCE_TASK_COUNT != AUTHORITATIVE_SLATE_COUNT
        or len(imported_lanes) != len(_FROZEN_LANE_LATTICE)
        or imported_lanes != _FROZEN_LANE_LATTICE
        or support.FOLD_MINIMUM_OPPORTUNITY_WORLDS
        != FOLD_MINIMUM_OPPORTUNITY_WORLDS
        or support.FINAL_MINIMUM_OPPORTUNITY_WORLDS
        != FINAL_MINIMUM_OPPORTUNITY_WORLDS
        or support.GENERAL_SUPPORT_NUMERATOR != SUPPORT_NUMERATOR
        or support.GENERAL_SUPPORT_DENOMINATOR != SUPPORT_DENOMINATOR
        or support.AUTHORITATIVE_SLATE_COUNT != AUTHORITATIVE_SLATE_COUNT
        or support.AUTHORITATIVE_FOLD_GATE_COUNT
        != AUTHORITATIVE_FOLD_GATE_COUNT
        or support.AUTHORITATIVE_FINAL_GATE_COUNT
        != AUTHORITATIVE_FINAL_GATE_COUNT
    ):
        _fail("frozen dependency constants drifted from the T230 protocol")


def _validate_panel_members(
    value: object,
) -> list[dict[str, object]]:
    rows = _sequence(value, label="panel accepted slates")
    if len(rows) != AUTHORITATIVE_SLATE_COUNT:
        _fail("panel must contain exactly 54 accepted slates")
    normalized: list[dict[str, object]] = []
    slate_ids: set[str] = set()
    source_authorities: set[str] = set()
    object_identities: set[tuple[str, str, str, int]] = set()
    for source_ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"panel member[{source_ordinal}]")
        _exact_keys(
            row, _PANEL_MEMBER_KEYS, label=f"panel member[{source_ordinal}]"
        )
        slate_id = _canonical_slate_id(
            row.get("slate_id"), label=f"panel member[{source_ordinal}].slate_id"
        )
        if slate_id in slate_ids:
            _fail("panel slate ids repeat")
        slate_ids.add(slate_id)
        if row.get("source_task_ordinal") != source_ordinal:
            _fail("panel source ordinals are not exactly 0..53")
        first_lane_count = int(_FROZEN_LANE_LATTICE[0]["task_count"])
        if source_ordinal < first_lane_count:
            expected_lane = (0, "v12a", source_ordinal)
        else:
            expected_lane = (
                1,
                "v12b",
                source_ordinal - first_lane_count,
            )
        if (
            row.get("lane_ordinal"),
            row.get("lane_id"),
            row.get("task_ordinal"),
        ) != expected_lane:
            _fail("panel member differs from the frozen two-lane lattice")
        source_authority = _sha256(
            row.get("source_task_authority_sha256"),
            label=f"panel member[{source_ordinal}] source authority",
        )
        if source_authority in source_authorities:
            _fail("panel source-task authority hashes repeat")
        source_authorities.add(source_authority)
        task_acceptance = _identity(
            row.get("task_acceptance_identity"),
            label=f"panel member[{source_ordinal}] task acceptance",
        )
        carrier = _identity(
            row.get("carrier_identity"),
            label=f"panel member[{source_ordinal}] carrier",
        )
        for retained in (task_acceptance, carrier):
            key = _identity_key(retained)
            if key in object_identities:
                _fail("panel accepted object identities repeat")
            object_identities.add(key)
        raw_arms = _sequence(
            row.get("arms"), label=f"panel member[{source_ordinal}] arms"
        )
        if len(raw_arms) != len(batch.PARAMETER_SET_ORDER):
            _fail("panel member must bind exactly seven source arms")
        arms: list[dict[str, object]] = []
        for arm_ordinal, raw_arm in enumerate(raw_arms):
            arm = _mapping(
                raw_arm,
                label=f"panel member[{source_ordinal}] arm[{arm_ordinal}]",
            )
            _exact_keys(
                arm,
                _PANEL_ARM_KEYS,
                label=f"panel member[{source_ordinal}] arm[{arm_ordinal}]",
            )
            if (
                arm.get("arm_ordinal") != arm_ordinal
                or arm.get("parameter_set_id")
                != batch.PARAMETER_SET_ORDER[arm_ordinal]
            ):
                _fail("panel source-arm identity or order differs")
            result_identity = _identity(
                arm.get("result_identity"),
                label=(
                    f"panel member[{source_ordinal}] arm[{arm_ordinal}] result"
                ),
            )
            result_key = _identity_key(result_identity)
            if result_key in object_identities:
                _fail("panel accepted object identities repeat")
            object_identities.add(result_key)
            arms.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
                "result_identity": result_identity,
            })
        normalized.append({
            "slate_id": slate_id,
            "lane_ordinal": expected_lane[0],
            "lane_id": expected_lane[1],
            "task_ordinal": expected_lane[2],
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": source_authority,
            "task_acceptance_identity": task_acceptance,
            "carrier_identity": carrier,
            "arms": arms,
        })
    if batch.canonical_json_bytes(normalized) != batch.canonical_json_bytes(rows):
        _fail("panel accepted slate representation differs")
    return normalized


def _validate_panel_lanes(
    value: object,
    *,
    members: Sequence[Mapping[str, object]],
    source_completion: Mapping[str, object],
    source_completion_sha256: str,
) -> list[dict[str, object]]:
    raw_lanes = _sequence(value, label="panel lanes")
    if len(raw_lanes) != len(_FROZEN_LANE_LATTICE):
        _fail("panel must contain the frozen two-lane lattice")
    terminal_identities: list[dict[str, object]] = []
    observed_objects: set[tuple[str, str, str, int]] = set()
    for lane_ordinal, raw_lane in enumerate(raw_lanes):
        lane = _mapping(raw_lane, label=f"panel lane[{lane_ordinal}]")
        _exact_keys(lane, _PANEL_LANE_KEYS, label=f"panel lane[{lane_ordinal}]")
        law = _FROZEN_LANE_LATTICE[lane_ordinal]
        expected_members = [
            row for row in members if row["lane_ordinal"] == lane_ordinal
        ]
        if (
            len(expected_members) != law["task_count"]
            or lane.get("lane_ordinal") != lane_ordinal
            or lane.get("lane_id") != law["lane_id"]
            or lane.get("batch_mode") != law["batch_mode"]
            or lane.get("source_task_offset") != law["source_task_offset"]
            or lane.get("expected_task_count") != law["task_count"]
            or lane.get("accepted_task_count") != law["task_count"]
            or lane.get("accepted_task_ordinals")
            != list(range(int(law["task_count"])))
            or lane.get("complete") is not True
            or lane.get("artifact_source_authority_completion")
            != source_completion
            or lane.get("artifact_source_authority_completion_sha256")
            != source_completion_sha256
        ):
            _fail("panel lane differs from the frozen complete lattice")
        batch_id = lane.get("batch_id")
        if type(batch_id) is not str or not batch_id or batch_id.strip() != batch_id:
            _fail("panel lane batch id is not canonical")
        terminal = _identity(
            lane.get("terminal_receipt_identity"),
            label=f"panel lane[{lane_ordinal}] terminal receipt",
        )
        completion = _identity(
            lane.get("batch_completion_identity"),
            label=f"panel lane[{lane_ordinal}] batch completion",
        )
        for retained in (terminal, completion):
            key = _identity_key(retained)
            if key in observed_objects:
                _fail("panel lane authority object identities repeat")
            observed_objects.add(key)
        if lane.get("task_acceptance_identities_sha256") != (
            batch.canonical_sha256([
                row["task_acceptance_identity"] for row in expected_members
            ])
        ):
            _fail("panel lane task-acceptance list hash differs")
        if lane.get("carrier_identities_sha256") != batch.canonical_sha256([
            row["carrier_identity"] for row in expected_members
        ]):
            _fail("panel lane carrier list hash differs")
        terminal_identities.append(terminal)
    return terminal_identities


def _validated_panel(
    value: object, *, panel_index_identity: Mapping[str, object]
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
]:
    item = dict(_mapping(value, label="published v12 panel index"))
    _exact_keys(item, _PANEL_KEYS, label="published v12 panel index")
    _false_authorities(
        item,
        label="published v12 panel index",
        fields=_FALSE_PANEL_AUTHORITY_FIELDS,
    )
    _validate_self_hash(
        item, field="panel_index_sha256", label="published v12 panel index"
    )
    identity = _identity(panel_index_identity, label="published panel object")
    try:
        batch.validate_json_identity(
            item, identity, label="published panel object identity"
        )
    except Exception as exc:
        raise CorpusExtremeTailPanelReleaseError(
            "published panel bytes differ from the generation-pinned identity"
        ) from exc
    if (
        item.get("schema_version") != panel.PANEL_INDEX_SCHEMA
        or item.get("publication_mode") != panel.PUBLICATION_MODE
        or item.get("lane_count") != len(_FROZEN_LANE_LATTICE)
        or item.get("accepted_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or item.get("exclusions") != []
        or item.get("failures") != []
        or item.get("missing_tasks") != []
    ):
        _fail("published panel is not the complete accepted v12 panel")
    source_completion = _identity(
        item.get("artifact_source_authority_completion"),
        label="panel source-authority completion",
    )
    source_completion_sha256 = _sha256(
        item.get("artifact_source_authority_completion_sha256"),
        label="panel source-authority completion SHA-256",
    )
    members = _validate_panel_members(item.get("accepted_slates"))
    terminals = _validate_panel_lanes(
        item.get("lanes"),
        members=members,
        source_completion=source_completion,
        source_completion_sha256=source_completion_sha256,
    )
    coverage = _mapping(item.get("coverage"), label="panel coverage")
    _exact_keys(coverage, _PANEL_COVERAGE_KEYS, label="panel coverage")
    if coverage != {
        "expected_task_count": AUTHORITATIVE_SLATE_COUNT,
        "accepted_task_count": AUTHORITATIVE_SLATE_COUNT,
        "excluded_task_count": 0,
        "failed_task_count": 0,
        "missing_task_count": 0,
        "complete": True,
    }:
        _fail("published panel coverage is not exactly complete")
    expected_panel_id = f"v12:{batch.canonical_sha256(terminals)}"
    if item.get("panel_id") != expected_panel_id:
        _fail("published panel id differs from its ordered terminal lanes")
    return item, identity, members


def _frozen_science_contracts() -> tuple[
    list[str],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    source_arms = list(SOURCE_ARM_ORDER)
    if (
        batch.canonical_sha256(source_arms)
        != census.SOURCE_ARM_ORDER_SHA256
        or tuple(suite.ENTRY_BUDGETS) != (4, 14, 80)
        or suite.RANKING_DEPTH != 80
    ):
        _fail("frozen source, world, dose, or budget constants drifted")
    implementation = suite.frozen_selector_implementation_contract_v1()
    implementation_hash = _sha256(
        implementation.get("selector_implementation_sha256"),
        label="selector implementation SHA-256",
    )
    _validate_self_hash(
        implementation,
        field="selector_implementation_sha256",
        label="selector implementation contract",
    )
    strategies = suite.frozen_extreme_tail_strategies_v1()
    expected_strategy_ids = (
        "coverage-ge-230-v1",
        "bounded-tail-ladder-ge-210-250-v1",
        "block-robust-bounded-tail-ge-210-250-v1",
        "individual-ge-230-rank-v1",
    )
    if len(strategies) != len(expected_strategy_ids):
        _fail("frozen T230 strategy count differs")
    for ordinal, (strategy, strategy_id) in enumerate(
        zip(strategies, expected_strategy_ids, strict=True)
    ):
        if (
            strategy.get("ordinal") != ordinal
            or strategy.get("strategy_id") != strategy_id
            or strategy.get("entry_budgets") != list(suite.ENTRY_BUDGETS)
            or strategy.get("ranking_depth") != suite.RANKING_DEPTH
            or strategy.get("selector_implementation_sha256")
            != implementation_hash
        ):
            _fail("frozen T230 strategy registry differs")
        _validate_self_hash(
            strategy, field="strategy_sha256", label=f"strategy[{ordinal}]"
        )
    strategy_hashes = {
        str(strategy["strategy_id"]): str(strategy["strategy_sha256"])
        for strategy in strategies
    }
    world_contract = {
        "world_blocks": list(WORLD_BLOCKS),
        "world_blocks_sha256": batch.canonical_sha256(list(WORLD_BLOCKS)),
        "worlds_per_block": WORLDS_PER_BLOCK,
        "score_world_count": len(WORLD_BLOCKS) * WORLDS_PER_BLOCK,
        "world_order_law": "five-complete-block-major-ordinary-r-worlds",
        "ordinary_unweighted_r_worlds": True,
    }
    world_contract["world_contract_sha256"] = batch.canonical_sha256(
        world_contract
    )
    dose = {
        "source_arm_count": len(source_arms),
        "world_block_count": len(WORLD_BLOCKS),
        "visits_per_block": VISITS_PER_BLOCK,
        "visits_per_arm": len(WORLD_BLOCKS) * VISITS_PER_BLOCK,
        "total_visit_count": TOTAL_VISIT_COUNT,
        "dose_shape": list(DOSE_SHAPE),
        "dose_law": "every-source-arm-times-every-r-block-times-200-visits",
        "require_exact_authoritative_dose": True,
    }
    dose["generation_dose_sha256"] = batch.canonical_sha256(dose)
    retrieval_contract = {
        "suite_schema_version": suite.SUITE_SCHEMA,
        "suite_law_id": suite.SUITE_LAW_ID,
        "full_union_admission_law": suite.FULL_UNION_ADMISSION_LAW,
        "strategy_registry": strategies,
        "strategy_registry_sha256": batch.canonical_sha256(strategies),
        "strategy_sha256_by_id": strategy_hashes,
        "selector_implementation_contract": implementation,
        "selector_implementation_id": implementation["implementation_id"],
        "selector_implementation_sha256": implementation_hash,
        "entry_budgets": list(suite.ENTRY_BUDGETS),
        "ranking_depth": suite.RANKING_DEPTH,
        "ranking_prefix_law": RANKING_PREFIX_LAW,
        "fold_count_per_slate": len(WORLD_BLOCKS),
        "final_fit_is_distinct_all_block_refit": True,
    }
    retrieval_contract["retrieval_contract_sha256"] = batch.canonical_sha256(
        retrieval_contract
    )
    literal_hash = strategy_hashes[support.LITERAL_COVERAGE_STRATEGY_ID]
    fallback_hash = strategy_hashes[support.FALLBACK_STRATEGY_ID]
    fold_gate_total = (
        AUTHORITATIVE_SLATE_COUNT * len(WORLD_BLOCKS)
    )
    final_gate_total = AUTHORITATIVE_SLATE_COUNT
    fold_pass_minimum = (
        fold_gate_total * SUPPORT_NUMERATOR
        + SUPPORT_DENOMINATOR
        - 1
    ) // SUPPORT_DENOMINATOR
    final_pass_minimum = (
        final_gate_total * SUPPORT_NUMERATOR
        + SUPPORT_DENOMINATOR
        - 1
    ) // SUPPORT_DENOMINATOR
    if (
        fold_gate_total != AUTHORITATIVE_FOLD_GATE_COUNT
        or final_gate_total != AUTHORITATIVE_FINAL_GATE_COUNT
        or fold_pass_minimum != FOLD_PASS_MINIMUM
        or final_pass_minimum != FINAL_PASS_MINIMUM
    ):
        _fail("frozen authoritative panel support boundaries drifted")
    support_contract = {
        "policy_schema_version": support.POLICY_SCHEMA,
        "policy_law_id": support.POLICY_LAW_ID,
        "literal_threshold": {
            "threshold_id": "ge_230",
            "score": 230.0,
            "operator": ">=",
        },
        "fold_support": {
            "training_block_count": len(WORLD_BLOCKS) - 1,
            "requires_every_training_block_nonzero": True,
            "minimum_opportunity_world_count": FOLD_MINIMUM_OPPORTUNITY_WORLDS,
        },
        "final_support": {
            "training_block_count": len(WORLD_BLOCKS),
            "requires_every_training_block_nonzero": True,
            "minimum_opportunity_world_count": FINAL_MINIMUM_OPPORTUNITY_WORLDS,
        },
        "support_switch": {
            "passed_strategy_id": support.LITERAL_COVERAGE_STRATEGY_ID,
            "passed_strategy_sha256": literal_hash,
            "failed_strategy_id": support.FALLBACK_STRATEGY_ID,
            "failed_strategy_sha256": fallback_hash,
            "selection_law": (
                "support-pass-selects-literal-coverage-otherwise-selects-"
                "block-robust-ladder"
            ),
            "projects_only_already_frozen_raw_suite_books": True,
        },
        "panel_support": {
            "summary_law_id": support.PANEL_SUMMARY_LAW_ID,
            "authoritative_slate_count": AUTHORITATIVE_SLATE_COUNT,
            "numerator": SUPPORT_NUMERATOR,
            "denominator": SUPPORT_DENOMINATOR,
            "comparison_operator": ">=",
            "integer_cross_products_only": True,
            "fold_gate_total": fold_gate_total,
            "fold_pass_minimum": fold_pass_minimum,
            "final_gate_total": final_gate_total,
            "final_pass_minimum": final_pass_minimum,
            "general_support_requires_both_boundaries": True,
        },
    }
    support_contract["support_contract_sha256"] = batch.canonical_sha256(
        support_contract
    )
    return (
        source_arms,
        world_contract,
        dose,
        retrieval_contract,
        support_contract,
    )


def _source_members(
    panel_members: Sequence[Mapping[str, object]], *, output_prefix: str
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    output_uris: set[str] = set()
    for source_ordinal, member in enumerate(panel_members):
        slate_id = str(member["slate_id"])
        member_prefix = f"{output_prefix}slates/{source_ordinal:02d}-{slate_id}/"
        result_uri = member_prefix + RESULT_FILENAME
        acceptance_uri = member_prefix + ACCEPTANCE_FILENAME
        if result_uri in output_uris or acceptance_uri in output_uris:
            _fail("deterministic T230 output URIs repeat")
        output_uris.update((result_uri, acceptance_uri))
        row = {
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "panel_member_sha256": batch.canonical_sha256(member),
            "source_task_authority_sha256": member[
                "source_task_authority_sha256"
            ],
            "task_acceptance_identity": member["task_acceptance_identity"],
            "carrier_identity": member["carrier_identity"],
            "result_uri": result_uri,
            "acceptance_uri": acceptance_uri,
        }
        _exact_keys(row, _SOURCE_MEMBER_KEYS, label="T230 source member")
        rows.append(row)
    return rows


def build_t230_panel_execution_manifest_v1(
    *,
    panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
) -> dict[str, object]:
    """Build one deterministic manifest over the exact published v12 panel."""
    _validate_frozen_dependency_constants()
    retained_panel, panel_identity, panel_members = _validated_panel(
        panel_index, panel_index_identity=panel_index_identity
    )
    if (
        type(source_commit_sha) is not str
        or _COMMIT.fullmatch(source_commit_sha) is None
    ):
        _fail("source commit must be one lowercase 40-character Git SHA")
    retained_image = _image(immutable_image)
    retained_prefix = _output_prefix(output_prefix)
    (
        source_arms,
        world_contract,
        dose,
        retrieval_contract,
        support_contract,
    ) = _frozen_science_contracts()
    members = _source_members(panel_members, output_prefix=retained_prefix)
    panel_support = _mapping(
        support_contract.get("panel_support"),
        label="frozen panel support contract",
    )
    if (
        len(panel_members) != AUTHORITATIVE_SLATE_COUNT
        or len(members) != AUTHORITATIVE_SLATE_COUNT
        or panel_support.get("authoritative_slate_count") != len(members)
        or panel_support.get("final_gate_total") != len(members)
        or panel_support.get("fold_gate_total")
        != len(members) * len(WORLD_BLOCKS)
    ):
        _fail("source member count differs from frozen panel support counts")
    manifest_id_seed = {
        "schema_version": PANEL_EXECUTION_MANIFEST_SCHEMA,
        "panel_object_identity": panel_identity,
        "panel_index_sha256": retained_panel["panel_index_sha256"],
        "source_members_sha256": batch.canonical_sha256(members),
        "source_commit_sha": source_commit_sha,
        "immutable_image": retained_image,
        "output_prefix": retained_prefix,
    }
    body: dict[str, object] = {
        "schema_version": PANEL_EXECUTION_MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_id": (
            "foundry-t230:" + batch.canonical_sha256(manifest_id_seed)
        ),
        "panel_object_identity": panel_identity,
        "panel_id": retained_panel["panel_id"],
        "panel_index_sha256": retained_panel["panel_index_sha256"],
        "panel_accepted_slates_sha256": batch.canonical_sha256(panel_members),
        "source_member_count": AUTHORITATIVE_SLATE_COUNT,
        "source_members": members,
        "source_members_sha256": batch.canonical_sha256(members),
        "source_arm_order": source_arms,
        "source_arm_order_sha256": batch.canonical_sha256(source_arms),
        "ordinary_r_world_contract": world_contract,
        "authoritative_generation_dose": dose,
        "t230_retrieval_contract": retrieval_contract,
        "support_contract": support_contract,
        "source_commit_sha": source_commit_sha,
        "immutable_image": retained_image,
        "output_prefix": retained_prefix,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["execution_manifest_sha256"] = batch.canonical_sha256(body)
    return body


def validate_t230_panel_execution_manifest_v1(
    value: object,
    *,
    panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    source_commit_sha: str,
    immutable_image: Mapping[str, object],
    output_prefix: str,
) -> dict[str, object]:
    """Validate the manifest and replay it from all frozen preparation inputs."""
    item = dict(_mapping(value, label="T230 panel execution manifest"))
    _exact_keys(item, _MANIFEST_KEYS, label="T230 panel execution manifest")
    if (
        item.get("schema_version") != PANEL_EXECUTION_MANIFEST_SCHEMA
        or item.get("publication_mode") != PUBLICATION_MODE
    ):
        _fail("T230 panel execution manifest schema or publication mode differs")
    _false_authorities(item, label="T230 panel execution manifest")
    _validate_self_hash(
        item,
        field="execution_manifest_sha256",
        label="T230 panel execution manifest",
    )
    expected = build_t230_panel_execution_manifest_v1(
        panel_index=panel_index,
        panel_index_identity=panel_index_identity,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("T230 panel execution manifest differs from frozen-input replay")
    return expected


__all__ = [
    "ACCEPTANCE_FILENAME",
    "CorpusExtremeTailPanelReleaseError",
    "PANEL_EXECUTION_MANIFEST_SCHEMA",
    "PUBLICATION_MODE",
    "RANKING_PREFIX_LAW",
    "RESULT_FILENAME",
    "build_t230_panel_execution_manifest_v1",
    "validate_t230_panel_execution_manifest_v1",
]
