from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts import run_corpus_extreme_tail_one_slate_smoke_v1 as cli
from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_extreme_tail_one_slate_execution as execution
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import corpus_v12_panel_index as panel
from nfl_dfs.research import residual_world_columns as rw


TARGET_SLATE = "2023-w01"


def _hex(value: int) -> str:
    return f"{value:064x}"


class Store:
    def __init__(self) -> None:
        self.raw_by_key: dict[tuple[str, str], bytes] = {}
        self.identity_by_key: dict[tuple[str, str], dict[str, object]] = {}
        self.read_calls: list[dict[str, object]] = []

    def put_raw(
        self, uri: str, raw: bytes, *, generation: int
    ) -> dict[str, object]:
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        key = (uri, str(generation))
        self.raw_by_key[key] = raw
        self.identity_by_key[key] = identity
        return identity

    def put_json(
        self, uri: str, value: object, *, generation: int
    ) -> dict[str, object]:
        return self.put_raw(
            uri, batch.canonical_json_bytes(value), generation=generation
        )

    def read(self, identity: dict[str, object]) -> bytes:
        retained = batch.normalize_object_identity(identity, label="fake read")
        key = (str(retained["uri"]), str(retained["generation"]))
        assert retained == self.identity_by_key[key]
        self.read_calls.append(retained)
        return self.raw_by_key[key]


def _stub_identity(uri: str, seed: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(seed),
        "sha256": _hex(seed),
        "bytes": 1,
    }


def _task_carrier(
    store: Store,
    *,
    ordinal: int,
    slate_id: str,
    arms: list[dict[str, object]],
) -> dict[str, object]:
    source_identity = store.put_json(
        f"gs://fixture/source-freeze/{ordinal}.json",
        {"freeze_sha256": _hex(30_000 + ordinal)},
        generation=30_000 + ordinal,
    )
    source_receipts = {"later_source_freeze": source_identity}
    world_artifacts = {
        role: store.put_raw(
            f"gs://fixture/worlds/{ordinal}/{role}.npz",
            f"world-{ordinal}-{role}".encode(),
            generation=40_000 + ordinal * 10 + role_ordinal,
        )
        for role_ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }
    body: dict[str, object] = {
        "schema_version": batch.TASK_RESULT_SCHEMA,
        "publication_mode": batch.PUBLICATION_MODE,
        "batch_manifest_identity": _stub_identity(
            f"gs://fixture/batch/{ordinal}.json", 50_000 + ordinal
        ),
        "batch_id": f"fixture-batch-{ordinal}",
        "batch_manifest_sha256": _hex(51_000 + ordinal),
        "parameter_schema_sha256": _hex(52_000 + ordinal),
        "common_law_sha256": _hex(53_000 + ordinal),
        "task_index": ordinal if ordinal < 28 else ordinal - 28,
        "task_sha256": _hex(54_000 + ordinal),
        "slate_id": slate_id,
        "world_artifact_receipts": world_artifacts,
        "world_artifact_receipt_set_sha256": batch.canonical_sha256(
            world_artifacts
        ),
        "artifact_source_authority_task_sha256": _hex(55_000 + ordinal),
        "code_source": _stub_identity(
            f"gs://fixture/code/{ordinal}.tgz", 55_500 + ordinal
        ),
        "immutable_image": {
            "uri": "fixture/image",
            "digest": f"sha256:{_hex(55_600 + ordinal)}",
        },
        "source_receipts": source_receipts,
        "source_receipt_set_sha256": batch.canonical_sha256(
            source_receipts
        ),
        "later_source_freeze_manifest_sha256": _hex(30_000 + ordinal),
        "artifact_source_authority_completion": _stub_identity(
            f"gs://fixture/authority/{ordinal}.json", 56_000 + ordinal
        ),
        "artifact_source_authority_completion_sha256": _hex(
            57_000 + ordinal
        ),
        "effective_policy_inventory_identity": _stub_identity(
            f"gs://fixture/policy/{ordinal}.json", 58_000 + ordinal
        ),
        "effective_policy_inventory_sha256": _hex(59_000 + ordinal),
        "effective_policy_rule_universe_sha256": _hex(60_000 + ordinal),
        "effective_policy_inventory_source_set_sha256": _hex(
            61_000 + ordinal
        ),
        "effective_policy_classified_input_projection_sha256": _hex(
            62_000 + ordinal
        ),
        "world_schedule": _stub_identity(
            f"gs://fixture/schedule/{ordinal}.json", 61_500 + ordinal
        ),
        "world_seed": 62_500 + ordinal,
        "solver": {"fixture": True},
        "execution": {"fixture": True},
        "variant_results": [
            {
                "ordinal": arm_ordinal,
                "parameter_set_id": arm["parameter_set_id"],
                "parameter_set_sha256": _hex(
                    63_000 + ordinal * 10 + arm_ordinal
                ),
                "effective_policy_receipt": _stub_identity(
                    (
                        f"gs://fixture/effective/{ordinal}/"
                        f"{arm_ordinal}.json"
                    ),
                    64_000 + ordinal * 10 + arm_ordinal,
                ),
                "result_object": arm["result_identity"],
            }
            for arm_ordinal, arm in enumerate(arms)
        ],
    }
    body["task_result_sha256"] = batch.canonical_sha256(body)
    return store.put_json(
        f"gs://fixture/carrier/{ordinal}.json",
        body,
        generation=2_000 + ordinal,
    )


def _member(store: Store, ordinal: int) -> dict[str, object]:
    lane_ordinal = 0 if ordinal < 28 else 1
    task_ordinal = ordinal if lane_ordinal == 0 else ordinal - 28
    slate_id = TARGET_SLATE if ordinal == 0 else f"fixture-slate-{ordinal:02d}"
    acceptance = store.put_json(
        f"gs://fixture/acceptance/{ordinal}.json",
        {"kind": "acceptance", "ordinal": ordinal},
        generation=1_000 + ordinal,
    )
    arms = []
    for arm_ordinal, parameter_set_id in enumerate(batch.PARAMETER_SET_ORDER):
        result_identity = store.put_json(
            f"gs://fixture/arm/{ordinal}/{arm_ordinal}.json",
            {
                "kind": "arm",
                "ordinal": ordinal,
                "arm_ordinal": arm_ordinal,
            },
            generation=10_000 + ordinal * 10 + arm_ordinal,
        )
        arms.append({
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": parameter_set_id,
            "result_identity": result_identity,
        })
    carrier = (
        _task_carrier(
            store,
            ordinal=ordinal,
            slate_id=slate_id,
            arms=arms,
        )
        if ordinal in {0, 1}
        else store.put_json(
            f"gs://fixture/carrier/{ordinal}.json",
            {"kind": "carrier", "ordinal": ordinal},
            generation=2_000 + ordinal,
        )
    )
    return {
        "slate_id": slate_id,
        "lane_ordinal": lane_ordinal,
        "lane_id": "v12a" if lane_ordinal == 0 else "v12b",
        "task_ordinal": task_ordinal,
        "source_task_ordinal": ordinal,
        "source_task_authority_sha256": _hex(20_000 + ordinal),
        "task_acceptance_identity": acceptance,
        "carrier_identity": carrier,
        "arms": arms,
    }


def _panel(store: Store) -> dict[str, object]:
    accepted = [_member(store, ordinal) for ordinal in range(54)]
    source_identity = store.put_json(
        "gs://fixture/source/completion.json",
        {"kind": "source-completion"},
        generation=50_000,
    )
    body: dict[str, object] = {
        "schema_version": panel.PANEL_INDEX_SCHEMA,
        "publication_mode": panel.PUBLICATION_MODE,
        "panel_id": "v12:" + _hex(90_000),
        "artifact_source_authority_completion": source_identity,
        "artifact_source_authority_completion_sha256": _hex(90_001),
        "lane_count": 2,
        "lanes": [{"lane_ordinal": 0}, {"lane_ordinal": 1}],
        "accepted_slate_count": 54,
        "accepted_slates": accepted,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "coverage": {
            "expected_task_count": 54,
            "accepted_task_count": 54,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        },
        **{field: False for field in panel._FALSE_PANEL_FIELDS},
    }
    body["panel_index_sha256"] = batch.canonical_sha256(body)
    return body


def _publication_receipt(
    panel_body: dict[str, object], panel_identity: dict[str, object]
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": cli.PUBLICATION_RECEIPT_SCHEMA,
        "mode": "create_once",
        "panel_uri": panel_identity["uri"],
        "panel_id": panel_body["panel_id"],
        "panel_object_identity": panel_identity,
        "panel_content_sha256": panel_identity["sha256"],
        "panel_content_bytes": panel_identity["bytes"],
        "panel_index_sha256": panel_body["panel_index_sha256"],
        "lane_count": 2,
        "accepted_slate_count": 54,
        "exact_input_replay_verified": True,
        "published": True,
        **{field: False for field in cli._FALSE_PUBLICATION_FIELDS},
    }
    body["publication_receipt_sha256"] = batch.canonical_sha256(body)
    return body


def _write_receipt(path: Path, receipt: dict[str, object]) -> None:
    path.write_bytes(batch.canonical_json_bytes(receipt) + b"\n")


def _fixture(tmp_path: Path) -> tuple[
    Store,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    Path,
]:
    store = Store()
    panel_body = _panel(store)
    panel_identity = store.put_json(
        "gs://fixture/panel/index.json", panel_body, generation=77
    )
    receipt = _publication_receipt(panel_body, panel_identity)
    receipt_path = tmp_path / "panel-publication.json"
    _write_receipt(receipt_path, receipt)
    return store, panel_body, panel_identity, receipt, receipt_path


def _fraction(numerator: int, denominator: int) -> dict[str, int] | None:
    if denominator == 0:
        return None
    return {"numerator": numerator, "denominator": denominator}


@lru_cache(maxsize=None)
def _canonical_world_scope_sha256(blocks: tuple[str, ...]) -> str:
    return batch.canonical_sha256([
        {"block": block, "index": index}
        for block in blocks
        for index in range(rw.WORLDS_PER_BLOCK)
    ])


def _source_support(
    *,
    blocks: list[str],
    lineup_count: int,
    universe_kind: str,
    parameter_set_id: str | None,
) -> dict[str, object]:
    if universe_kind == "source-arm-all-block":
        assert parameter_set_id in batch.PARAMETER_SET_ORDER
        occurrence_by_arm = {
            arm: len(rw.WORLD_BLOCKS) * runner.VISITS_PER_BLOCK
            for arm in batch.PARAMETER_SET_ORDER
        }
        candidate_by_arm = {
            arm: lineup_count
            for arm in batch.PARAMETER_SET_ORDER
        }
        occurrence_by_block = {
            block: len(batch.PARAMETER_SET_ORDER) * runner.VISITS_PER_BLOCK
            for block in rw.WORLD_BLOCKS
        }
    else:
        occurrence_by_arm = {
            arm: len(blocks) * runner.VISITS_PER_BLOCK
            for arm in batch.PARAMETER_SET_ORDER
        }
        candidate_by_arm = {
            arm: lineup_count for arm in batch.PARAMETER_SET_ORDER
        }
        occurrence_by_block = {
            block: (
                len(batch.PARAMETER_SET_ORDER) * runner.VISITS_PER_BLOCK
                if block in blocks
                else 0
            )
            for block in rw.WORLD_BLOCKS
        }
    candidate_by_block = {
        block: lineup_count if block in blocks else 0
        for block in rw.WORLD_BLOCKS
    }
    total = sum(occurrence_by_block.values())
    minimum = total // lineup_count
    maximum = minimum + (total % lineup_count != 0)
    return {
        "candidate_counts_are_nonexclusive_across_arms_and_blocks": True,
        "occurrence_counts_partition_occurrences_by_arm_and_block": True,
        "candidate_count": lineup_count,
        "candidate_count_by_training_origin_block": candidate_by_block,
        "training_occurrence_count_by_block": occurrence_by_block,
        "candidate_count_by_training_source_arm": candidate_by_arm,
        "training_occurrence_count_by_source_arm": occurrence_by_arm,
        "training_origin_block_breadth_histogram": [
            {"block_count": len(blocks), "lineup_count": lineup_count}
        ],
        "training_source_arm_breadth_histogram": [
            {
                "arm_count": sum(value > 0 for value in candidate_by_arm.values()),
                "lineup_count": lineup_count,
            }
        ],
        "training_visit_occurrence_count_total": total,
        "distinct_training_arm_visit_count": total,
        "training_visit_occurrence_count_minimum": minimum,
        "training_visit_occurrence_count_maximum": maximum,
        "training_visit_occurrence_count_mean_fraction": _fraction(
            total, lineup_count
        ),
    }


def _count_evidence(
    *,
    label: str,
    threshold: float,
    operator: str,
    lineup_count: int,
    world_count: int,
    event_count: int,
    seed: int,
) -> dict[str, object]:
    return {
        "label": label,
        "threshold": threshold,
        "operator": operator,
        "event_lineup_count": event_count,
        "event_lineup_ids_sha256": _hex(seed),
        "lineup_world_event_count": event_count,
        "opportunity_world_count": event_count,
        "opportunity_world_ids_sha256": _hex(seed + 1),
        "non_opportunity_world_count": world_count - event_count,
        "opportunity_rate_fraction": _fraction(event_count, world_count),
        "summed_individual_event_rate_fraction": _fraction(
            event_count, world_count
        ),
        "mean_individual_event_rate_fraction": _fraction(
            event_count, lineup_count * world_count
        ),
        "event_union_efficiency_fraction": _fraction(
            event_count, event_count
        ),
    }


def _event_source_lineage(
    *,
    event_lineup_count: int,
    source_support: dict[str, object],
    source_training_blocks: list[str],
) -> dict[str, object]:
    candidate_by_arm = source_support[
        "candidate_count_by_training_source_arm"
    ]
    active_arms = [
        arm
        for arm in batch.PARAMETER_SET_ORDER
        if candidate_by_arm[arm] == source_support["candidate_count"]
    ]
    assert active_arms
    occurrence_total = (
        source_support["training_visit_occurrence_count_minimum"]
        * event_lineup_count
    )

    def partition(keys: list[str]) -> dict[str, int]:
        quotient, remainder = divmod(occurrence_total, len(keys))
        return {
            key: quotient + (ordinal < remainder)
            for ordinal, key in enumerate(keys)
        }

    occurrence_by_arm = partition(active_arms)
    occurrence_by_block = partition(source_training_blocks)
    return {
        "event_lineup_counts_are_nonexclusive_across_arms_and_blocks": True,
        "event_occurrence_counts_partition_occurrences_by_arm_and_block": True,
        "event_lineup_count_by_training_source_arm": {
            arm: event_lineup_count if arm in active_arms else 0
            for arm in batch.PARAMETER_SET_ORDER
        },
        "event_training_occurrence_count_by_source_arm": {
            arm: occurrence_by_arm.get(arm, 0)
            for arm in batch.PARAMETER_SET_ORDER
        },
        "event_lineup_count_by_training_origin_block": {
            block: event_lineup_count if block in source_training_blocks else 0
            for block in rw.WORLD_BLOCKS
        },
        "event_training_occurrence_count_by_origin_block": {
            block: occurrence_by_block.get(block, 0)
            for block in rw.WORLD_BLOCKS
        },
        "event_distinct_training_arm_visit_count": occurrence_total,
    }


def _opportunity_metrics(
    *,
    blocks: list[str],
    source_training_blocks: list[str],
    source_support: dict[str, object],
    lineup_count: int,
    lineup_ids_sha256: str,
    seed: int,
) -> dict[str, object]:
    opportunity_count_by_threshold = {
        "ge_220": 30,
        "ge_230": 25,
        "ge_240": 10,
        "ge_250": 5,
    }
    block_world_hashes = {
        block: _canonical_world_scope_sha256((block,))
        for block in blocks
    }
    thresholds = []
    for ordinal, (label, threshold, operator) in enumerate(census.THRESHOLDS):
        count = opportunity_count_by_threshold[label]
        event_lineup_ids_sha256 = _hex(seed + 30_000 + ordinal)
        block_rows = [
            {
                "block_id": block,
                "world_count": rw.WORLDS_PER_BLOCK,
                "world_ids_sha256": block_world_hashes[block],
                **_count_evidence(
                    label=label,
                    threshold=threshold,
                    operator=operator,
                    lineup_count=lineup_count,
                    world_count=rw.WORLDS_PER_BLOCK,
                    event_count=count,
                    seed=seed + 10_000 + ordinal * 100 + block_ordinal * 2,
                ),
            }
            for block_ordinal, block in enumerate(blocks)
        ]
        for block_row in block_rows:
            block_row["event_lineup_ids_sha256"] = event_lineup_ids_sha256
        event_total = len(blocks) * count
        aggregate = _count_evidence(
            label=label,
            threshold=threshold,
            operator=operator,
            lineup_count=lineup_count,
            world_count=len(blocks) * rw.WORLDS_PER_BLOCK,
            event_count=event_total,
            seed=seed + 20_000 + ordinal * 2,
        )
        aggregate["event_lineup_count"] = count
        aggregate["event_lineup_ids_sha256"] = event_lineup_ids_sha256
        if len(block_rows) == 1:
            aggregate["event_lineup_ids_sha256"] = block_rows[0][
                "event_lineup_ids_sha256"
            ]
            aggregate["opportunity_world_ids_sha256"] = block_rows[0][
                "opportunity_world_ids_sha256"
            ]
        thresholds.append({
            **aggregate,
            "event_score_block_breadth_histogram": [
                {"block_count": 0, "lineup_count": lineup_count - count},
                {"block_count": len(blocks), "lineup_count": count},
            ],
            "event_positive_lineup_generation_origin_block_breadth_histogram": [
                {
                    "block_count": len(source_training_blocks),
                    "lineup_count": count,
                }
            ],
            "event_source_lineage": _event_source_lineage(
                event_lineup_count=count,
                source_support=source_support,
                source_training_blocks=source_training_blocks,
            ),
            "by_block": block_rows,
        })
    body: dict[str, object] = {
        "schema_version": census.METRIC_SCHEMA,
        "blocks": blocks,
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "world_count": len(blocks) * rw.WORLDS_PER_BLOCK,
        "world_ids_sha256": _canonical_world_scope_sha256(tuple(blocks)),
        "lineup_count": lineup_count,
        "lineup_ids_sha256": lineup_ids_sha256,
        "thresholds": thresholds,
        "ordinary_unweighted_r_worlds": True,
        "uses_realized_outcomes": False,
    }
    body["opportunity_metrics_sha256"] = batch.canonical_sha256(body)
    return body


def _support_universes() -> list[dict[str, object]]:
    contracts = [
        (
            f"source-arm-all-block:{arm}",
            "source-arm-all-block",
            arm,
            None,
            list(rw.WORLD_BLOCKS),
            "any-all-block-provenance-occurrence-from-source-arm",
        )
        for arm in batch.PARAMETER_SET_ORDER
    ] + [
        (
            f"cross-arm-fold-eligible:holdout-{heldout}",
            "cross-arm-fold-eligible",
            None,
            heldout,
            [block for block in rw.WORLD_BLOCKS if block != heldout],
            (
                "cross-arm-union-with-heldout-only-origins-and-heldout-"
                "occurrences-removed-before-selection"
            ),
        )
        for heldout in rw.WORLD_BLOCKS
    ] + [
        (
            "cross-arm-all-block-union",
            "cross-arm-all-block-union",
            None,
            None,
            list(rw.WORLD_BLOCKS),
            "canonical-deduplicated-cross-arm-all-block-union",
        )
    ]
    universes: list[dict[str, object]] = []
    for ordinal, (
        universe_id,
        universe_kind,
        parameter_set_id,
        heldout_block,
        training_blocks,
        membership_law,
    ) in enumerate(contracts):
        lineup_count = 90
        lineup_ids_sha256 = _hex(62_001)
        is_fold = universe_kind == "cross-arm-fold-eligible"
        source_support = _source_support(
            blocks=training_blocks,
            lineup_count=lineup_count,
            universe_kind=universe_kind,
            parameter_set_id=parameter_set_id,
        )
        body: dict[str, object] = {
            "schema_version": census.UNIVERSE_SCHEMA,
            "universe_id": universe_id,
            "universe_kind": universe_kind,
            "parameter_set_id": parameter_set_id,
            "heldout_block": heldout_block,
            "training_blocks": training_blocks,
            "membership_law": membership_law,
            "lineup_count": lineup_count,
            "lineup_ids_sha256": lineup_ids_sha256,
            "heldout_only_excluded_lineup_count": 0,
            "fit_candidate_view_sha256": (
                _hex(65_000 + ordinal) if is_fold else None
            ),
            "selection_provenance_sha256": (
                _hex(66_000 + ordinal) if is_fold else None
            ),
            "source_support": source_support,
            "training_metrics": _opportunity_metrics(
                blocks=training_blocks,
                source_training_blocks=training_blocks,
                source_support=source_support,
                lineup_count=lineup_count,
                lineup_ids_sha256=lineup_ids_sha256,
                seed=67_000 + ordinal,
            ),
            "heldout_metrics_descriptive": (
                _opportunity_metrics(
                    blocks=[heldout_block],
                    source_training_blocks=training_blocks,
                    source_support=source_support,
                    lineup_count=lineup_count,
                    lineup_ids_sha256=lineup_ids_sha256,
                    seed=68_000 + ordinal,
                )
                if is_fold
                else None
            ),
            "uses_realized_outcomes": False,
            "analytical_authority": False,
            "promotion_authority": False,
        }
        body["universe_sha256"] = batch.canonical_sha256(body)
        universes.append(body)
    return universes


def _execution_result(
    *,
    store: Store,
    panel_body: dict[str, object],
    panel_identity: dict[str, object],
    membership: dict[str, object],
) -> dict[str, object]:
    carrier_identity = membership["carrier_identity"]
    carrier_key = (
        str(carrier_identity["uri"]), str(carrier_identity["generation"])
    )
    carrier = batch.parse_canonical_json_bytes(
        store.raw_by_key[carrier_key], label="fixture carrier"
    )
    world_artifacts = carrier["world_artifact_receipts"]
    source_identity = carrier["source_receipts"]["later_source_freeze"]
    matrix_binding: dict[str, object] = {
        "schema_version": v12_import.MATRIX_BINDING_SCHEMA,
        "slate": {"season": 2023, "week": 1, "slate_id": TARGET_SLATE},
        "candidate_provenance_sha256": _hex(62_000),
        "lineup_ids_sha256": _hex(62_001),
        "world_ids_sha256": _canonical_world_scope_sha256(
            tuple(rw.WORLD_BLOCKS)
        ),
        "shape": [90, len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK],
        "score_matrix_sha256": _hex(62_003),
        "uses_realized_outcomes": False,
    }
    matrix_binding["matrix_binding_sha256"] = batch.canonical_sha256(
        matrix_binding
    )
    reconstruction: dict[str, object] = {
        "schema_version": v12_import.RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": _hex(63_000),
        "candidate_provenance_sha256": matrix_binding[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix_binding,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": parameter_set_id,
                "candidate_score_sha256": _hex(63_100 + ordinal),
                "selected_score_sha256": _hex(63_200 + ordinal),
                "unique_count": 90,
                "selected_count": batch.SELECTED_ENTRY_BUDGET,
                "verified": True,
            }
            for ordinal, parameter_set_id in enumerate(
                batch.PARAMETER_SET_ORDER
            )
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    reconstruction["reconstruction_sha256"] = batch.canonical_sha256(
        reconstruction
    )

    universes = _support_universes()
    gate_observations = [
        {
            "heldout_block": heldout,
            "training_blocks": [
                block for block in rw.WORLD_BLOCKS if block != heldout
            ],
            "every_training_block_nonzero": True,
            "training_opportunity_world_count": 100,
            "nomination_support_passed": True,
        }
        for heldout in rw.WORLD_BLOCKS
    ]

    support: dict[str, object] = {
        "schema_version": census.CENSUS_SCHEMA,
        "census_law_id": census.CENSUS_LAW_ID,
        "slate": matrix_binding["slate"],
        "input_binding": {
            "reconstruction_sha256": reconstruction[
                "reconstruction_sha256"
            ],
            "candidate_provenance_sha256": matrix_binding[
                "candidate_provenance_sha256"
            ],
            "matrix_binding_sha256": matrix_binding[
                "matrix_binding_sha256"
            ],
            "score_matrix_sha256": matrix_binding["score_matrix_sha256"],
            "lineup_ids_sha256": matrix_binding["lineup_ids_sha256"],
            "world_ids_sha256": matrix_binding["world_ids_sha256"],
            "score_shape": matrix_binding["shape"],
        },
        "world_basis": {
            "blocks": list(rw.WORLD_BLOCKS),
            "worlds_per_block": rw.WORLDS_PER_BLOCK,
            "world_count": len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK,
            "ordinary_unweighted_r_worlds": True,
        },
        "threshold_registry": [
            {
                "threshold_id": label,
                "score": threshold,
                "operator": operator,
            }
            for label, threshold, operator in census.THRESHOLDS
        ],
        "source_arm_order": list(census.SOURCE_ARM_ORDER),
        "source_arm_order_sha256": census.SOURCE_ARM_ORDER_SHA256,
        "universe_order_law": (
            "seven-source-arms-parameter-order-then-five-heldout-blocks-"
            "then-cross-arm-all-block-union"
        ),
        "universe_count": 13,
        "universes": universes,
        "coverage_ge_230_support_gate": {
            "role": "support-observation-not-selector-or-promotion-authority",
            "requires_every_training_block_nonzero": True,
            "minimum_training_opportunity_world_count": (
                census.LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS
            ),
            "failure_role": (
                "literal-230-remains-diagnostic-use-bounded-tail-fallback"
            ),
            "fold_observations": gate_observations,
        },
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "require_authoritative": True,
        "evidence_class": "outcome-blind-simulated-instrument",
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "automatic_retry_licensed": False,
        "live_policy_access_licensed": False,
        "r6_freeze_authority": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    support["support_census_sha256"] = batch.canonical_sha256(support)
    output_hashes = {
        "compatibility_import_sha256": reconstruction[
            "compatibility_import_sha256"
        ],
        "candidate_provenance_sha256": reconstruction[
            "candidate_provenance_sha256"
        ],
        "reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "matrix_binding_sha256": matrix_binding["matrix_binding_sha256"],
        "score_matrix_sha256": matrix_binding["score_matrix_sha256"],
        "support_census_sha256": support["support_census_sha256"],
    }
    body: dict[str, object] = {
        "schema_version": execution.RESULT_SCHEMA,
        "execution_mode": "authoritative-dose-one-slate-outcome-blind-smoke",
        "slate_id": membership["slate_id"],
        "panel_index_identity": panel_identity,
        "panel_index_sha256": panel_body["panel_index_sha256"],
        "accepted_slate_membership": membership,
        "accepted_slate_membership_sha256": batch.canonical_sha256(membership),
        "task_acceptance_identity": membership["task_acceptance_identity"],
        "carrier_identity": membership["carrier_identity"],
        "later_source_freeze_identity": source_identity,
        "world_artifact_identities": world_artifacts,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            world_artifacts
        ),
        "configuration": {
            "worlds_per_block": 10_000,
            "require_authoritative": True,
        },
        "verification": {
            "panel_content_identity_verified": True,
            "panel_membership_binding_verified": True,
            "task_acceptance_content_identity_verified": True,
            "task_acceptance_carrier_binding_verified": True,
            "carrier_source_receipts_verified": True,
            "canonical_reconstruction_verified": True,
            "support_census_canonical_replay_verified": True,
            "canonical_authoritative_dose_verified": True,
        },
        "output_hashes": output_hashes,
        "reconstruction_receipt": reconstruction,
        "support_census": support,
        **{field: False for field in execution._FALSE_AUTHORITY_FIELDS},
    }
    body["one_slate_execution_sha256"] = batch.canonical_sha256(body)
    return body


def _argv(receipt_path: Path, *, output: Path | None = None) -> list[str]:
    result = [
        "--panel-publication-receipt",
        str(receipt_path),
        "--slate-id",
        TARGET_SLATE,
    ]
    if output is not None:
        result.extend(["--result-output", str(output)])
    return result


def _rehash_nested_support(result: dict[str, object]) -> None:
    support = result["support_census"]
    support.pop("support_census_sha256")
    support["support_census_sha256"] = batch.canonical_sha256(support)
    result["output_hashes"]["support_census_sha256"] = support[
        "support_census_sha256"
    ]
    result.pop("one_slate_execution_sha256")
    result["one_slate_execution_sha256"] = batch.canonical_sha256(result)


def _rehash_universe_evidence(
    result: dict[str, object],
    *,
    universe_ordinal: int,
    metrics_field: str | None = None,
) -> None:
    universe = result["support_census"]["universes"][universe_ordinal]
    if metrics_field is not None:
        metrics = universe[metrics_field]
        metrics.pop("opportunity_metrics_sha256")
        metrics["opportunity_metrics_sha256"] = batch.canonical_sha256(
            metrics
        )
    universe.pop("universe_sha256")
    universe["universe_sha256"] = batch.canonical_sha256(universe)
    _rehash_nested_support(result)


def _rehash_all_universe_evidence(result: dict[str, object]) -> None:
    for universe in result["support_census"]["universes"]:
        for metrics_field in (
            "training_metrics",
            "heldout_metrics_descriptive",
        ):
            metrics = universe[metrics_field]
            if metrics is not None:
                metrics.pop("opportunity_metrics_sha256")
                metrics["opportunity_metrics_sha256"] = (
                    batch.canonical_sha256(metrics)
                )
        universe.pop("universe_sha256")
        universe["universe_sha256"] = batch.canonical_sha256(universe)


def _rehash_reconstruction_and_support(result: dict[str, object]) -> None:
    reconstruction = result["reconstruction_receipt"]
    matrix = reconstruction["matrix_binding"]
    matrix.pop("matrix_binding_sha256")
    matrix["matrix_binding_sha256"] = batch.canonical_sha256(matrix)
    reconstruction.pop("reconstruction_sha256")
    reconstruction["reconstruction_sha256"] = batch.canonical_sha256(
        reconstruction
    )
    census_input = result["support_census"]["input_binding"]
    census_input.update({
        "reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "candidate_provenance_sha256": reconstruction[
            "candidate_provenance_sha256"
        ],
        "matrix_binding_sha256": matrix["matrix_binding_sha256"],
        "score_matrix_sha256": matrix["score_matrix_sha256"],
        "lineup_ids_sha256": matrix["lineup_ids_sha256"],
        "world_ids_sha256": matrix["world_ids_sha256"],
        "score_shape": matrix["shape"],
    })
    result["output_hashes"].update({
        "reconstruction_sha256": reconstruction["reconstruction_sha256"],
        "matrix_binding_sha256": matrix["matrix_binding_sha256"],
        "score_matrix_sha256": matrix["score_matrix_sha256"],
    })
    _rehash_nested_support(result)


def test_direct_publication_envelope_selects_and_binds_one_member(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, panel_body, panel_identity, _receipt, receipt_path = _fixture(
        tmp_path
    )
    member = panel_body["accepted_slates"][0]
    output = tmp_path / "smoke-result.json"
    observed: list[dict[str, object]] = []

    def execute(**kwargs):
        observed.append(kwargs)
        assert kwargs["validated_panel_index"] == panel_body
        assert kwargs["panel_index_identity"] == panel_identity
        assert kwargs["accepted_slate_membership"] == member
        assert kwargs["task_acceptance_identity"] == member[
            "task_acceptance_identity"
        ]
        assert kwargs["carrier_identity"] == member["carrier_identity"]
        assert kwargs["require_authoritative"] is True
        kwargs["read_exact"](member["task_acceptance_identity"])
        kwargs["read_exact"](member["carrier_identity"])
        return _execution_result(
            store=store,
            panel_body=panel_body,
            panel_identity=panel_identity,
            membership=member,
        )

    monkeypatch.setattr(
        execution, "execute_one_slate_extreme_tail_census", execute
    )
    result = cli.run(_argv(receipt_path, output=output), store=store)

    assert len(observed) == 1
    assert store.read_calls == [
        panel_identity,
        member["carrier_identity"],
        member["task_acceptance_identity"],
        member["carrier_identity"],
    ]
    assert result["slate_id"] == TARGET_SLATE
    assert output.read_bytes() == batch.canonical_json_bytes(result) + b"\n"
    assert json.loads(output.read_text()) == result


def test_gcs_store_pins_blob_and_download_generation() -> None:
    calls: list[tuple[object, ...]] = []

    class Blob:
        def download_as_bytes(
            self, *, if_generation_match: int, retry: object
        ) -> bytes:
            calls.append(("download", if_generation_match, retry))
            return b"panel"

    class Bucket:
        def blob(self, name: str, *, generation: int) -> Blob:
            calls.append(("blob", name, generation))
            return Blob()

    class Client:
        def bucket(self, name: str) -> Bucket:
            calls.append(("bucket", name))
            return Bucket()

    identity = {
        "uri": "gs://fixture-bucket/path/panel.json",
        "generation": "71",
        "sha256": sha256(b"panel").hexdigest(),
        "bytes": 5,
    }
    assert cli.GCSReadStore(Client()).read(identity) == b"panel"
    assert calls == [
        ("bucket", "fixture-bucket"),
        ("blob", "path/panel.json", 71),
        ("download", 71, None),
    ]


def test_all_bad_output_paths_fail_before_store_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _body, _identity, _receipt, receipt_path = _fixture(tmp_path)
    monkeypatch.chdir(tmp_path)
    existing = tmp_path / "existing.json"
    existing.write_text("occupied")
    directory = tmp_path / "directory"
    directory.mkdir()
    target = tmp_path / "target.json"
    target.write_text("target")
    symlink = tmp_path / "result-link.json"
    symlink.symlink_to(target)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    missing_parent = tmp_path / "missing" / "result.json"
    bad_paths = [
        Path("relative.json"),
        existing,
        directory,
        symlink,
        linked_parent / "result.json",
        missing_parent,
    ]
    for bad_path in bad_paths:
        store.read_calls.clear()
        with pytest.raises(cli.CorpusExtremeTailOneSlateSmokeCLIError):
            cli.run(_argv(receipt_path, output=bad_path), store=store)
        assert store.read_calls == []


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"{}\n\n",
        b'{"a":1,"a":1}\n',
        b'{"value":NaN}\n',
        b' {"value":1}\n',
    ],
)
def test_publication_receipt_rejects_noncanonical_duplicate_or_nonfinite_json(
    tmp_path: Path, raw: bytes
) -> None:
    path = tmp_path / "bad-publication.json"
    path.write_bytes(raw)
    store = Store()
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="newline-canonical JSON",
    ):
        cli.run(_argv(path), store=store)
    assert store.read_calls == []


@pytest.mark.parametrize(
    "field,value", [("mode", "validate_only"), ("published", False)]
)
def test_publication_receipt_requires_create_once_published_true(
    tmp_path: Path, field: str, value: object
) -> None:
    store, _body, _identity, receipt, receipt_path = _fixture(tmp_path)
    receipt[field] = value
    receipt.pop("publication_receipt_sha256")
    receipt["publication_receipt_sha256"] = batch.canonical_sha256(receipt)
    _write_receipt(receipt_path, receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="mode or authority differs",
    ):
        cli.run(_argv(receipt_path), store=store)
    assert store.read_calls == []


def test_publication_receipt_exact_keys_and_self_hash_fail_before_read(
    tmp_path: Path,
) -> None:
    store, _body, _identity, receipt, receipt_path = _fixture(tmp_path)
    receipt["unexpected"] = False
    receipt.pop("publication_receipt_sha256")
    receipt["publication_receipt_sha256"] = batch.canonical_sha256(receipt)
    _write_receipt(receipt_path, receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError, match="fields differ"
    ):
        cli.run(_argv(receipt_path), store=store)
    assert store.read_calls == []

    receipt.pop("unexpected")
    receipt["publication_receipt_sha256"] = "f" * 64
    _write_receipt(receipt_path, receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError, match="self-hash differs"
    ):
        cli.run(_argv(receipt_path), store=store)
    assert store.read_calls == []


def test_panel_content_identity_and_canonical_json_fail_closed(
    tmp_path: Path
) -> None:
    store, panel_body, panel_identity, receipt, receipt_path = _fixture(tmp_path)
    key = (str(panel_identity["uri"]), str(panel_identity["generation"]))
    store.raw_by_key[key] += b"x"
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="content differs from exact identity",
    ):
        cli.run(_argv(receipt_path), store=store)

    noncanonical = json.dumps(panel_body, indent=2).encode()
    noncanonical_identity = store.put_raw(
        "gs://fixture/panel/noncanonical.json",
        noncanonical,
        generation=78,
    )
    noncanonical_receipt = _publication_receipt(
        panel_body, noncanonical_identity
    )
    noncanonical_path = tmp_path / "noncanonical-publication.json"
    _write_receipt(noncanonical_path, noncanonical_receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="not exact canonical JSON",
    ):
        cli.run(_argv(noncanonical_path), store=store)

    canonical = batch.canonical_json_bytes(panel_body)
    duplicate = b'{"schema_version":"duplicate",' + canonical[1:]
    duplicate_identity = store.put_raw(
        "gs://fixture/panel/duplicate.json", duplicate, generation=79
    )
    duplicate_receipt = _publication_receipt(panel_body, duplicate_identity)
    duplicate_path = tmp_path / "duplicate-publication.json"
    _write_receipt(duplicate_path, duplicate_receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="not exact canonical JSON",
    ):
        cli.run(_argv(duplicate_path), store=store)

    nonfinite = canonical.replace(b'"lane_count":2', b'"lane_count":NaN')
    nonfinite_identity = store.put_raw(
        "gs://fixture/panel/nonfinite.json", nonfinite, generation=81
    )
    nonfinite_receipt = _publication_receipt(panel_body, nonfinite_identity)
    nonfinite_path = tmp_path / "nonfinite-publication.json"
    _write_receipt(nonfinite_path, nonfinite_receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="not exact canonical JSON",
    ):
        cli.run(_argv(nonfinite_path), store=store)


def test_missing_or_duplicate_explicit_slate_fails_closed(tmp_path: Path) -> None:
    store, _panel_body, _identity, _receipt, receipt_path = _fixture(tmp_path)
    argv = [
        "--panel-publication-receipt",
        str(receipt_path),
        "--slate-id",
        "missing-slate",
    ]
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="not exactly one accepted panel member",
    ):
        cli.run(argv, store=store)

    duplicate_body = _panel(store)
    duplicate_body["accepted_slates"][1]["slate_id"] = TARGET_SLATE
    duplicate_body.pop("panel_index_sha256")
    duplicate_body["panel_index_sha256"] = batch.canonical_sha256(
        duplicate_body
    )
    duplicate_identity = store.put_json(
        "gs://fixture/panel/duplicate-slate.json",
        duplicate_body,
        generation=80,
    )
    duplicate_receipt = _publication_receipt(
        duplicate_body, duplicate_identity
    )
    duplicate_path = tmp_path / "duplicate-slate-publication.json"
    _write_receipt(duplicate_path, duplicate_receipt)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="duplicate slate_id",
    ):
        cli.run(_argv(duplicate_path), store=store)


def test_existing_result_collision_never_reads_or_overwrites(
    tmp_path: Path
) -> None:
    store, _body, _identity, _receipt, receipt_path = _fixture(tmp_path)
    output = tmp_path / "result.json"
    output.write_bytes(b"do-not-overwrite")
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="collision already exists",
    ):
        cli.run(_argv(receipt_path, output=output), store=store)
    assert store.read_calls == []
    assert output.read_bytes() == b"do-not-overwrite"


def test_execution_result_nested_evidence_fails_closed(tmp_path: Path) -> None:
    store, panel_body, panel_identity, _receipt, _path = _fixture(tmp_path)
    membership = panel_body["accepted_slates"][0]
    carrier_bindings = cli._load_carrier_bindings(
        carrier_identity=membership["carrier_identity"],
        membership=membership,
        store=store,
    )
    baseline = _execution_result(
        store=store,
        panel_body=panel_body,
        panel_identity=panel_identity,
        membership=membership,
    )
    assert cli._validate_execution_result(
        baseline,
        slate_id=TARGET_SLATE,
        panel_identity=panel_identity,
        panel_body=panel_body,
        membership=membership,
        carrier_bindings=carrier_bindings,
    ) == baseline

    missing_census = deepcopy(baseline)
    missing_census["support_census"] = {}
    missing_census.pop("one_slate_execution_sha256")
    missing_census["one_slate_execution_sha256"] = batch.canonical_sha256(
        missing_census
    )
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="support census fields differ",
    ):
        cli._validate_execution_result(
            missing_census,
            slate_id=TARGET_SLATE,
            panel_identity=panel_identity,
            panel_body=panel_body,
            membership=membership,
            carrier_bindings=carrier_bindings,
        )

    outcome_licensed = deepcopy(baseline)
    support = outcome_licensed["support_census"]
    support["uses_realized_outcomes"] = True
    support.pop("support_census_sha256")
    support["support_census_sha256"] = batch.canonical_sha256(support)
    outcome_licensed["output_hashes"]["support_census_sha256"] = support[
        "support_census_sha256"
    ]
    outcome_licensed.pop("one_slate_execution_sha256")
    outcome_licensed["one_slate_execution_sha256"] = batch.canonical_sha256(
        outcome_licensed
    )
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="carries forbidden authority",
    ):
        cli._validate_execution_result(
            outcome_licensed,
            slate_id=TARGET_SLATE,
            panel_identity=panel_identity,
            panel_body=panel_body,
            membership=membership,
            carrier_bindings=carrier_bindings,
        )

    unverified = deepcopy(baseline)
    unverified["verification"][
        "support_census_canonical_replay_verified"
    ] = False
    unverified.pop("one_slate_execution_sha256")
    unverified["one_slate_execution_sha256"] = batch.canonical_sha256(
        unverified
    )
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="not authoritative-dose",
    ):
        cli._validate_execution_result(
            unverified,
            slate_id=TARGET_SLATE,
            panel_identity=panel_identity,
            panel_body=panel_body,
            membership=membership,
            carrier_bindings=carrier_bindings,
        )

    artifact_drift = deepcopy(baseline)
    artifact_drift["world_artifact_identity_set_sha256"] = _hex(99_999)
    artifact_drift.pop("one_slate_execution_sha256")
    artifact_drift["one_slate_execution_sha256"] = batch.canonical_sha256(
        artifact_drift
    )
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="source/world artifact binding differs",
    ):
        cli._validate_execution_result(
            artifact_drift,
            slate_id=TARGET_SLATE,
            panel_identity=panel_identity,
            panel_body=panel_body,
            membership=membership,
            carrier_bindings=carrier_bindings,
        )

    splice = deepcopy(baseline)
    other_carrier_identity = panel_body["accepted_slates"][1][
        "carrier_identity"
    ]
    other_carrier_key = (
        str(other_carrier_identity["uri"]),
        str(other_carrier_identity["generation"]),
    )
    other_carrier = batch.parse_canonical_json_bytes(
        store.raw_by_key[other_carrier_key], label="splice carrier"
    )
    splice["later_source_freeze_identity"] = other_carrier[
        "source_receipts"
    ]["later_source_freeze"]
    splice["world_artifact_identities"] = other_carrier[
        "world_artifact_receipts"
    ]
    splice["world_artifact_identity_set_sha256"] = batch.canonical_sha256(
        splice["world_artifact_identities"]
    )
    splice.pop("one_slate_execution_sha256")
    splice["one_slate_execution_sha256"] = batch.canonical_sha256(splice)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="source/world artifact binding differs",
    ):
        cli._validate_execution_result(
            splice,
            slate_id=TARGET_SLATE,
            panel_identity=panel_identity,
            panel_body=panel_body,
            membership=membership,
            carrier_bindings=carrier_bindings,
        )


def test_universe_order_gate_and_dose_drift_fail_after_valid_rehash(
    tmp_path: Path,
) -> None:
    store, panel_body, panel_identity, _receipt, _path = _fixture(tmp_path)
    membership = panel_body["accepted_slates"][0]
    carrier_bindings = cli._load_carrier_bindings(
        carrier_identity=membership["carrier_identity"],
        membership=membership,
        store=store,
    )
    baseline = _execution_result(
        store=store,
        panel_body=panel_body,
        panel_identity=panel_identity,
        membership=membership,
    )

    order_law_drift = deepcopy(baseline)
    order_law_drift["support_census"]["universe_order_law"] = "arbitrary"

    universe_order_drift = deepcopy(baseline)
    universes = universe_order_drift["support_census"]["universes"]
    universes[0], universes[1] = universes[1], universes[0]

    gate_drift = deepcopy(baseline)
    gate_drift["support_census"]["coverage_ge_230_support_gate"][
        "minimum_training_opportunity_world_count"
    ] = 99

    dose_drift = deepcopy(baseline)
    dose_drift["support_census"]["dose_authority"] = "arbitrary"

    for drifted in (
        order_law_drift,
        universe_order_drift,
        gate_drift,
        dose_drift,
    ):
        _rehash_nested_support(drifted)
        with pytest.raises(cli.CorpusExtremeTailOneSlateSmokeCLIError):
            cli._validate_execution_result(
                drifted,
                slate_id=TARGET_SLATE,
                panel_identity=panel_identity,
                panel_body=panel_body,
                membership=membership,
                carrier_bindings=carrier_bindings,
            )


def test_nested_producer_evidence_drift_fails_after_valid_rehash(
    tmp_path: Path,
) -> None:
    store, panel_body, panel_identity, _receipt, _path = _fixture(tmp_path)
    membership = panel_body["accepted_slates"][0]
    carrier_bindings = cli._load_carrier_bindings(
        carrier_identity=membership["carrier_identity"],
        membership=membership,
        store=store,
    )
    baseline = _execution_result(
        store=store,
        panel_body=panel_body,
        panel_identity=panel_identity,
        membership=membership,
    )

    membership_law_drift = deepcopy(baseline)
    membership_law_drift["support_census"]["universes"][0][
        "membership_law"
    ] = "arbitrary"
    _rehash_universe_evidence(
        membership_law_drift, universe_ordinal=0
    )

    empty_source_support = deepcopy(baseline)
    empty_source_support["support_census"]["universes"][0][
        "source_support"
    ] = {}
    _rehash_universe_evidence(empty_source_support, universe_ordinal=0)

    omitted_threshold_field = deepcopy(baseline)
    omitted_threshold_field["support_census"]["universes"][0][
        "training_metrics"
    ]["thresholds"][0].pop("event_lineup_count")
    _rehash_universe_evidence(
        omitted_threshold_field,
        universe_ordinal=0,
        metrics_field="training_metrics",
    )

    impossible_count = deepcopy(baseline)
    impossible_count["support_census"]["universes"][0][
        "training_metrics"
    ]["thresholds"][1]["by_block"][0][
        "opportunity_world_count"
    ] = rw.WORLDS_PER_BLOCK + 1
    _rehash_universe_evidence(
        impossible_count,
        universe_ordinal=0,
        metrics_field="training_metrics",
    )

    cases = (
        (membership_law_drift, "registered content differs"),
        (empty_source_support, "source support fields differ"),
        (omitted_threshold_field, "threshold\\[0\\] fields differ"),
        (impossible_count, "counts exceed or contradict"),
    )
    for drifted, expected_error in cases:
        with pytest.raises(
            cli.CorpusExtremeTailOneSlateSmokeCLIError,
            match=expected_error,
        ):
            cli._validate_execution_result(
                drifted,
                slate_id=TARGET_SLATE,
                panel_identity=panel_identity,
                panel_body=panel_body,
                membership=membership,
                carrier_bindings=carrier_bindings,
            )


def test_exact_lineage_and_canonical_world_hashes_reject_coherent_rehash(
    tmp_path: Path,
) -> None:
    store, panel_body, panel_identity, _receipt, _path = _fixture(tmp_path)
    membership = panel_body["accepted_slates"][0]
    carrier_bindings = cli._load_carrier_bindings(
        carrier_identity=membership["carrier_identity"],
        membership=membership,
        store=store,
    )
    baseline = _execution_result(
        store=store,
        panel_body=panel_body,
        panel_identity=panel_identity,
        membership=membership,
    )

    matrix_slate_extra = deepcopy(baseline)
    matrix_slate_extra["reconstruction_receipt"]["matrix_binding"][
        "slate"
    ]["unknown"] = False
    _rehash_reconstruction_and_support(matrix_slate_extra)

    census_slate_extra = deepcopy(baseline)
    census_slate_extra["support_census"]["slate"] = dict(
        census_slate_extra["support_census"]["slate"]
    )
    census_slate_extra["support_census"]["slate"]["unknown"] = False
    _rehash_nested_support(census_slate_extra)

    input_extra = deepcopy(baseline)
    input_extra["support_census"]["input_binding"]["unknown"] = _hex(88_001)
    _rehash_nested_support(input_extra)

    world_basis_extra = deepcopy(baseline)
    world_basis_extra["support_census"]["world_basis"]["unknown"] = False
    _rehash_nested_support(world_basis_extra)

    for drifted in (
        matrix_slate_extra,
        census_slate_extra,
        input_extra,
        world_basis_extra,
    ):
        with pytest.raises(
            cli.CorpusExtremeTailOneSlateSmokeCLIError,
            match="fields differ",
        ):
            cli._validate_execution_result(
                drifted,
                slate_id=TARGET_SLATE,
                panel_identity=panel_identity,
                panel_body=panel_body,
                membership=membership,
                carrier_bindings=carrier_bindings,
            )

    coherent_world_hash_drift = deepcopy(baseline)
    fake_block_hashes = {
        block: _hex(89_000 + ordinal)
        for ordinal, block in enumerate(rw.WORLD_BLOCKS)
    }
    scopes = {
        tuple(metric["blocks"])
        for universe in coherent_world_hash_drift["support_census"][
            "universes"
        ]
        for metric in (
            universe["training_metrics"],
            universe["heldout_metrics_descriptive"],
        )
        if metric is not None
    }
    fake_scope_hashes = {
        scope: _hex(90_000 + ordinal)
        for ordinal, scope in enumerate(sorted(scopes))
    }
    for universe in coherent_world_hash_drift["support_census"]["universes"]:
        for metric in (
            universe["training_metrics"],
            universe["heldout_metrics_descriptive"],
        ):
            if metric is None:
                continue
            scope = tuple(metric["blocks"])
            metric["world_ids_sha256"] = (
                fake_block_hashes[scope[0]]
                if len(scope) == 1
                else fake_scope_hashes[scope]
            )
            for threshold in metric["thresholds"]:
                for block_row in threshold["by_block"]:
                    block_row["world_ids_sha256"] = fake_block_hashes[
                        block_row["block_id"]
                    ]
    matrix = coherent_world_hash_drift["reconstruction_receipt"][
        "matrix_binding"
    ]
    matrix["world_ids_sha256"] = fake_scope_hashes[
        tuple(rw.WORLD_BLOCKS)
    ]
    _rehash_all_universe_evidence(coherent_world_hash_drift)
    _rehash_reconstruction_and_support(coherent_world_hash_drift)
    with pytest.raises(
        cli.CorpusExtremeTailOneSlateSmokeCLIError,
        match="canonical carrier scope",
    ):
        cli._validate_execution_result(
            coherent_world_hash_drift,
            slate_id=TARGET_SLATE,
            panel_identity=panel_identity,
            panel_body=panel_body,
            membership=membership,
            carrier_bindings=carrier_bindings,
        )


def test_full_union_marginals_and_overlap_histograms_fail_closed(
    tmp_path: Path,
) -> None:
    store, panel_body, panel_identity, _receipt, _path = _fixture(tmp_path)
    membership = panel_body["accepted_slates"][0]
    carrier_bindings = cli._load_carrier_bindings(
        carrier_identity=membership["carrier_identity"],
        membership=membership,
        store=store,
    )
    baseline = _execution_result(
        store=store,
        panel_body=panel_body,
        panel_identity=panel_identity,
        membership=membership,
    )
    first_arm, second_arm = batch.PARAMETER_SET_ORDER[:2]

    full_marginal_drift = deepcopy(baseline)
    full_support = full_marginal_drift["support_census"]["universes"][12][
        "source_support"
    ]
    full_support["candidate_count_by_training_source_arm"][first_arm] = 89
    full_support["training_source_arm_breadth_histogram"] = [
        {"arm_count": 6, "lineup_count": 1},
        {"arm_count": 7, "lineup_count": 89},
    ]
    _rehash_universe_evidence(full_marginal_drift, universe_ordinal=12)

    asymmetric_overlap = deepcopy(baseline)
    first_support = asymmetric_overlap["support_census"]["universes"][0][
        "source_support"
    ]
    first_support["candidate_count_by_training_source_arm"][second_arm] = 89
    first_support["training_source_arm_breadth_histogram"] = [
        {"arm_count": 6, "lineup_count": 1},
        {"arm_count": 7, "lineup_count": 89},
    ]
    _rehash_universe_evidence(asymmetric_overlap, universe_ordinal=0)

    symmetric_histogram_splice = deepcopy(baseline)
    for universe_ordinal, other_arm in ((0, second_arm), (1, first_arm)):
        source_support = symmetric_histogram_splice["support_census"][
            "universes"
        ][universe_ordinal]["source_support"]
        source_support["candidate_count_by_training_source_arm"][
            other_arm
        ] = 89
        source_support["training_source_arm_breadth_histogram"] = [
            {"arm_count": 6, "lineup_count": 1},
            {"arm_count": 7, "lineup_count": 89},
        ]
        _rehash_universe_evidence(
            symmetric_histogram_splice,
            universe_ordinal=universe_ordinal,
        )

    cases = (
        (full_marginal_drift, "full-union arm marginals"),
        (asymmetric_overlap, "pairwise overlap marginals are asymmetric"),
        (symmetric_histogram_splice, "arm breadth differs"),
    )
    for drifted, expected_error in cases:
        with pytest.raises(
            cli.CorpusExtremeTailOneSlateSmokeCLIError,
            match=expected_error,
        ):
            cli._validate_execution_result(
                drifted,
                slate_id=TARGET_SLATE,
                panel_identity=panel_identity,
                panel_body=panel_body,
                membership=membership,
                carrier_bindings=carrier_bindings,
            )
