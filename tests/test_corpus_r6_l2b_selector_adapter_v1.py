from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as projection_contract,
)
from nfl_dfs.research import corpus_r6_l2b_selector_adapter_v1 as adapter
from scripts import run_corpus_r6_l2b_selector_adapter_v1 as cli


def _identity(uri: str, label: str) -> dict[str, object]:
    raw = label.encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _value_identity(uri: str, value: object) -> dict[str, object]:
    raw = adapter.canonical_json_bytes_v1(value)
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _candidates(
    count: int = 150, *, duplicate_second_roster: bool = False,
) -> list[dict[str, object]]:
    arms = sorted(
        profile_id for _, profile_id, _ in projection_contract.PROFILE_IDENTITIES
    )
    rows = []
    for index in range(count):
        roster_index = 0 if duplicate_second_roster and index == 1 else index
        rows.append({
            "lineup_id": f"lineup-{index:03d}",
            "roster_player_ids": [
                f"p-{roster_index:03d}-{slot}" for slot in range(9)
            ],
            "training_origin_blocks": ["R1", "R2", "R3", "R4"],
            "training_source_arms": arms,
            "training_occurrence_counts_by_block": {
                block: 1 for block in ("R1", "R2", "R3", "R4")
            },
            "training_source_arms_by_block": {
                block: arms for block in ("R1", "R2", "R3", "R4")
            },
            "training_occurrence_count": 4,
        })
    return rows


def _projection(
    fold_ordinal: int,
    *,
    candidates: list[dict[str, object]],
    later_source_identity: dict[str, object],
) -> dict[str, object]:
    heldout = projection_contract.WORLD_BLOCKS[fold_ordinal]
    training = [
        block for block in projection_contract.WORLD_BLOCKS if block != heldout
    ]
    arms = sorted(
        profile_id for _, profile_id, _ in projection_contract.PROFILE_IDENTITIES
    )
    normalized = []
    for source in candidates:
        row = deepcopy(source)
        row["training_origin_blocks"] = list(training)
        row["training_occurrence_counts_by_block"] = {
            block: 1 for block in training
        }
        row["training_source_arms_by_block"] = {
            block: arms for block in training
        }
        normalized.append(row)
    lineup_ids = [row["lineup_id"] for row in normalized]
    rosters = [row["roster_player_ids"] for row in normalized]
    body = {
        "schema_version": projection_contract.PROJECTION_SCHEMA,
        "contract_id": projection_contract.CONTRACT_ID,
        "slate_id": "2023-w01",
        "fit_scope_id": f"holdout-{heldout}",
        "source_task_result_identity": _identity(
            "gs://fixture/source-task.json", "source-task"
        ),
        "task_result_payload_sha256": "1" * 64,
        "later_source_identity": later_source_identity,
        "world_artifact_identities": {
            f"world_artifact_{block.lower()}": _identity(
                f"gs://fixture/{block}.npz", block
            )
            for block in projection_contract.WORLD_BLOCKS
        },
        "fit_candidate_view_sha256": f"{fold_ordinal + 2:x}" * 64,
        "selection_provenance_sha256": f"{fold_ordinal + 3:x}" * 64,
        "training_blocks": training,
        "heldout_block": heldout,
        "training_world_columns_sha256": (
            projection_contract.canonical_world_columns_sha256_v1(training)
        ),
        "candidates": normalized,
        "candidate_lineup_order_sha256": (
            projection_contract.canonical_sha256_v1(lineup_ids)
        ),
        "candidate_rosters_sha256": (
            projection_contract.canonical_sha256_v1(rosters)
        ),
        "candidate_rows_sha256": (
            projection_contract.canonical_sha256_v1(normalized)
        ),
        "expected_training_score_matrix_sha256": "a" * 64,
        "expected_training_score_shape": [len(normalized), 40_000],
        "policy": dict(projection_contract.POLICY_CLAIMS),
    }
    body["projection_sha256"] = projection_contract.canonical_sha256_v1(body)
    return body


def _bundle() -> dict[str, object]:
    candidates = _candidates()
    later_source_identity = _identity("gs://fixture/later.json", "later")
    return projection_contract.build_projection_bundle_v1(
        source_ordinal=0,
        fold_projections=[
            _projection(
                fold,
                candidates=candidates,
                later_source_identity=later_source_identity,
            )
            for fold in range(5)
        ],
    )


def _manifest(bundle: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    prefix = adapter.OUTPUT_NAMESPACE + "l2b-selector-fixture/"
    later_identity = bundle["fold_projections"][0]["later_source_identity"]
    rows = []
    for index, (season, week) in enumerate(adapter.l2b_panel.EXPECTED_SLATES):
        slate_id = f"{season}-w{week:02d}"
        rows.append({
            "source_ordinal": index,
            "slate_id": slate_id,
            "projection_bundle_identity": _identity(
                f"gs://fixture/projection-{index:02d}.json", f"projection-{index}"
            ),
            "projection_bundle_sha256": (
                bundle["projection_bundle_sha256"] if index == 0 else f"{index:064x}"
            ),
            "unique_roster_count_by_fold": [150] * 5,
            "selector_candidate_count_by_fold": [150] * 5,
            "l2b_task_result_identity": _identity(
                f"gs://fixture/l2b-task-{index:02d}.json", f"l2b-{index}"
            ),
            "l2b_task_result_sha256": f"{index + 1:064x}",
            "result_uri": (
                f"{prefix}{adapter.FULL54_SCOPE}/selector-results/"
                f"{index:02d}-{slate_id}.json"
            ),
        })
    body = {
        "schema_version": adapter.TASK_MANIFEST_SCHEMA,
        "contract_id": adapter.CONTRACT_ID,
        "adapter_id": adapter.ADAPTER_ID,
        "l2b_panel_root_identity": _identity(
            "gs://fixture/l2b-panel-root.json", "panel-root"
        ),
        "l2b_panel_root_sha256": "b" * 64,
        "l2b_task_manifest_identity": _identity(
            "gs://fixture/l2b-task-manifest.json", "l2b-manifest"
        ),
        "l2b_task_manifest_sha256": "c" * 64,
        "control_projection_receipt_identity": _identity(
            "gs://fixture/control-projection-receipt.json", "control-receipt"
        ),
        "control_projection_receipt_sha256": "d" * 64,
        "control_projection_manifest_identity": _identity(
            "gs://fixture/control-projection-manifest.json", "control-manifest"
        ),
        "control_projection_manifest_sha256": "e" * 64,
        "control_design_identity": _identity(
            "gs://fixture/control-design.json", "control-design"
        ),
        "control_design_sha256": "f" * 64,
        "control_topology_identity": _identity(
            "gs://fixture/control-topology.json", "control-topology"
        ),
        "control_topology_sha256": "1" * 64,
        "terminal_build_receipt_identity": _identity(
            "gs://fixture/build.json", "build"
        ),
        "terminal_build_receipt_sha256": "2" * 64,
        "terminal_build_id": "11111111-1111-1111-1111-111111111111",
        "source_commit_sha": "3" * 40,
        "immutable_image_digest": "sha256:" + "4" * 64,
        "immutable_image_uri": "fixture/image@sha256:" + "4" * 64,
        "reused_job_name": adapter.REUSED_JOB_NAME,
        "reused_job_uid": adapter.REUSED_JOB_UID,
        "execution_scope": adapter.FULL54_SCOPE,
        "execution_task_count": 54,
        "task0_smoke_receipt_identity": _identity(
            "gs://fixture/task0-smoke.json", "task0-smoke"
        ),
        "task0_smoke_receipt_sha256": "5" * 64,
        "later_source_freeze_identity": later_identity,
        "task_count": adapter.TASK_COUNT,
        "task_rows": rows,
        "fraction_registry": [
            dict(row) for row in adapter.l2b_panel.FRACTION_REGISTRY
        ],
        "world_blocks": list(adapter.WORLD_BLOCKS),
        "worlds_per_block": adapter.WORLDS_PER_BLOCK,
        "selector_lattice": dict(adapter.SELECTOR_LATTICE),
        "candidate_population_law": adapter.SELECTOR_CANDIDATE_VIEW_LAW,
        "output_prefix": prefix,
        "terminal_root_uri": f"{prefix}terminal-selector-root.json",
        **adapter._FALSE_POLICY,
    }
    manifest = adapter._with_hash(body, field="task_manifest_sha256")
    return manifest, _identity(
        f"{prefix}selector-task-manifest-{adapter.FULL54_SCOPE}.json",
        "manifest",
    )


def _task0_manifest(
    bundle: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    manifest, _ = _manifest(bundle)
    manifest.pop("task_manifest_sha256")
    manifest["execution_scope"] = adapter.TASK0_SCOPE
    manifest["execution_task_count"] = 1
    manifest["task0_smoke_receipt_identity"] = None
    manifest["task0_smoke_receipt_sha256"] = None
    for row in manifest["task_rows"]:
        row["result_uri"] = (
            f"{manifest['output_prefix']}{adapter.TASK0_SCOPE}/selector-results/"
            f"{row['source_ordinal']:02d}-{row['slate_id']}.json"
        )
    manifest = adapter._with_hash(manifest, field="task_manifest_sha256")
    identity = _identity(
        f"{manifest['output_prefix']}selector-task-manifest-"
        f"{adapter.TASK0_SCOPE}.json",
        "task0-manifest",
    )
    return manifest, identity


def _task0_launch_and_status() -> tuple[dict[str, object], dict[str, object]]:
    execution_name = f"{adapter.REUSED_JOB_NAME}-fixture"
    launch = adapter.l2b_operator.build_launch_result_v1(
        execution_name=execution_name, scope=adapter.TASK0_SCOPE
    )
    status = adapter.l2b_operator._with_hash({
        "schema_version": adapter.l2b_operator.STATUS_SCHEMA,
        "scope": adapter.TASK0_SCOPE,
        "project_id": adapter.l2b_operator.PROJECT,
        "location": adapter.l2b_operator.REGION,
        "job_name": adapter.REUSED_JOB_NAME,
        "job_uid": adapter.REUSED_JOB_UID,
        "execution_name": execution_name,
        "execution_uid": "execution-uid",
        "execution_generation": "1",
        "expected_task_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "terminal_state": "SUCCEEDED",
        "logs_read": False,
        "scientific_outputs_read": False,
        "outcomes_read": False,
    }, field="status_sha256")
    return launch, status


def _task0_smoke_receipt(
    manifest: dict[str, object], manifest_identity: dict[str, object],
) -> dict[str, object]:
    launch, status = _task0_launch_and_status()
    result_identity = _identity(
        str(manifest["task_rows"][0]["result_uri"]), "task0-result"
    )
    return adapter._with_hash({
        "schema_version": adapter.TASK0_SMOKE_SCHEMA,
        "adapter_id": adapter.ADAPTER_ID,
        "execution_scope": adapter.TASK0_SCOPE,
        "task0_manifest_identity": manifest_identity,
        "task0_manifest_sha256": manifest["task_manifest_sha256"],
        "l2b_panel_root_identity": manifest["l2b_panel_root_identity"],
        "control_projection_receipt_identity": manifest[
            "control_projection_receipt_identity"
        ],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "reused_job_uid": manifest["reused_job_uid"],
        "task0_launch_result": launch,
        "task0_execution_status": status,
        "task_result_identity": result_identity,
        "task_result_sha256": "6" * 64,
        "uses_realized_outcomes": False,
        "complete": True,
    }, field="smoke_receipt_sha256")


def _prefix(
    lineup_ids: list[str], size: int, *, label: str
) -> dict[str, object]:
    selected = lineup_ids[:size]
    rosters = [[f"p-{index:03d}-{slot}" for slot in range(9)] for index in range(size)]
    body = {
        "prefix_size": size,
        "selected_lineup_ids": selected,
        "selected_lineup_ids_sha256": adapter.canonical_sha256_v1(selected),
        "selected_rosters_sha256": adapter.canonical_sha256_v1(rosters),
    }
    body["prefix_sha256"] = adapter.canonical_sha256_v1({
        **body, "fixture": label
    })
    return body


def _selector_fakes(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    def grouped(**kwargs):
        events.append("grouped")
        ids = list(kwargs["sampled_lineup_ids"])
        selectors = []
        for ordinal in range(3):
            selectors.append({
                "ordinal": ordinal,
                "preset_id": f"preset-{ordinal}",
                "selector_result_sha256": f"{ordinal + 1:064x}",
                "prefixes": [
                    _prefix(ids, size, label=f"g-{ordinal}-{size}")
                    for size in adapter.successor.PREFIX_SIZES
                ],
            })
        return {
            "schema_version": adapter.successor.RESULT_SCHEMA,
            "selector_count": 3,
            "selectors": selectors,
            "result_sha256": "1" * 64,
        }

    def ranked(**kwargs):
        events.append("ranked")
        ids = list(kwargs["sampled_lineup_ids"])
        selectors = []
        for ordinal in range(3):
            selectors.append({
                "ordinal": ordinal,
                "preset_id": f"preset-{ordinal}",
                "selector_result_sha256": f"{ordinal + 4:064x}",
                "entry_books": [
                    _prefix(ids, size, label=f"r-{ordinal}-{size}")
                    for size in adapter.rank150.ENTRY_BUDGETS
                ],
            })
        return {
            "schema_version": adapter.rank150.RESULT_SCHEMA,
            "selector_count": 3,
            "ranking_depth": 150,
            "selectors": selectors,
            "result_sha256": "2" * 64,
        }

    def dpp(**kwargs):
        events.append("dpp")
        ids = list(kwargs["sampled_lineup_ids"])
        return {
            "schema_version": adapter.diversity.RESULT_SCHEMA,
            "entry_budget": 150,
            "strategy_contract": {"strategy_id": "dpp-v1"},
            "prefixes": [
                _prefix(ids, size, label=f"d-{size}")
                for size in adapter.diversity.PREFIX_SIZES
            ],
            "result_sha256": "3" * 64,
        }

    def tail_diversity(**kwargs):
        events.append("tail-diversity")
        ids = list(kwargs["sampled_lineup_ids"])
        strategy_ids = [
            *[
                f"tail-ladder-roster-overlap-cap-{gamma}-v1"
                for gamma in adapter.diversity_challengers.OVERLAP_CAPS
            ],
            "tail-ladder-evil-twin-strict-200-v1",
        ]
        selectors = []
        for ordinal, strategy_id in enumerate(strategy_ids):
            books = []
            for size in adapter.diversity_challengers.ENTRY_BUDGETS:
                prefix = _prefix(ids, size, label=f"t-{ordinal}-{size}")
                books.append({
                    "entry_budget": size,
                    "selected_lineup_ids": prefix["selected_lineup_ids"],
                    "selected_lineup_ids_sha256": prefix[
                        "selected_lineup_ids_sha256"
                    ],
                    "selected_rosters_sha256": prefix[
                        "selected_rosters_sha256"
                    ],
                    "book_sha256": prefix["prefix_sha256"],
                })
            selectors.append({
                "ordinal": ordinal,
                "strategy_id": strategy_id,
                "selector_result_sha256": f"{ordinal + 8:064x}",
                "entry_books": books,
            })
        return {
            "schema_version": adapter.diversity_challengers.RESULT_SCHEMA,
            "selector_count": 4,
            "selectors": selectors,
            "result_sha256": "4" * 64,
        }

    monkeypatch.setattr(
        adapter.successor, "run_grouped_native_selectors_v1", grouped
    )
    monkeypatch.setattr(
        adapter.rank150, "run_exact_rank150_continuation_v1", ranked
    )
    monkeypatch.setattr(
        adapter.diversity, "run_effective_independent_shots_selector_v1", dpp
    )
    monkeypatch.setattr(
        adapter.diversity_challengers,
        "run_diversity_challengers_v1",
        tail_diversity,
    )
    monkeypatch.setattr(
        adapter.successor, "validate_grouped_native_selector_result_v1",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        adapter.rank150, "validate_exact_rank150_continuation_v1",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        adapter.diversity, "validate_effective_independent_shots_result_v1",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        adapter.diversity_challengers,
        "validate_diversity_challengers_v1",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        adapter, "_validate_persisted_selector_shapes_v1", lambda **_kwargs: None
    )


def test_fixed_union_is_cross_scored_for_both_l2b_fractions_and_all_budgets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle()
    manifest, manifest_identity = _manifest(bundle)
    monkeypatch.setattr(adapter, "WORLDS_PER_BLOCK", 8)
    manifest["worlds_per_block"] = 8
    manifest.pop("task_manifest_sha256")
    manifest = adapter._with_hash(manifest, field="task_manifest_sha256")
    events: list[str] = []
    _selector_fakes(monkeypatch, events)

    def cross_score(*, projection, world, **_kwargs):
        events.append(f"cross-{world.block}")
        result = np.zeros((len(projection["candidates"]), 8), dtype=np.float64)
        result.flags.writeable = False
        return result

    monkeypatch.setattr(adapter, "_cross_score_projection_block_v1", cross_score)
    players = (SimpleNamespace(player_id="unused"),)
    worlds = {
        fraction_id: {
            block: SimpleNamespace(block=block) for block in adapter.WORLD_BLOCKS
        }
        for fraction_id in adapter.FRACTION_IDS
    }
    result = adapter.build_slate_result_v1(
        source_ordinal=0,
        manifest=manifest,
        manifest_identity=manifest_identity,
        projection_bundle=bundle,
        players=players,
        worlds_by_fraction=worlds,
    )

    assert result["normalized_population_count"] == 5
    assert result["normalized_book_count"] == 2 * 5 * 30
    coordinates = [row["coordinate"] for row in result["normalized_books"]]
    assert {row["fraction_id"] for row in coordinates} == set(
        adapter.FRACTION_IDS
    )
    assert {row["entry_budget"] for row in coordinates} == {
        4, 14, 80, 100, 150
    }
    tail_coordinates = [
        row for row in coordinates
        if row["selector_family"] == adapter.SELECTOR_FAMILIES[3]
    ]
    assert len(tail_coordinates) == 2 * 5 * 3 * 3
    assert {row["entry_budget"] for row in tail_coordinates} == {80, 100, 150}
    assert {row["selector_id"] for row in tail_coordinates} == set(
        adapter.SELECTOR_LATTICE[
            "tail_ladder_diversity_active_strategy_ids"
        ]
    )
    assert adapter.TAIL_DIVERSITY_FOLLOWUP_STRATEGY_ID not in {
        row["selector_id"] for row in tail_coordinates
    }
    assert all(
        fold["candidate_rows"] == bundle["fold_projections"][index]["candidates"]
        for index, fold in enumerate(result["fold_results"])
    )
    first_population = result["normalized_populations"][0]
    assert len(first_population["lineups"]) == 150
    assert len({
        tuple(row["roster_player_ids"]) for row in first_population["lineups"]
    }) == 150
    # Every fraction/fold performs only four training cross-scores followed by
    # the selectors.  No held-out cross-score or digest is computed at all.
    for offset in range(0, len(events), 8):
        chunk = events[offset:offset + 8]
        assert chunk[4:8] == [
            "grouped", "ranked", "dpp", "tail-diversity"
        ]

    # This is the same normalized surface used by terminal reopen.  Requiring
    # exact 54-slate coordinate coverage here proves every new 80/100/150 cell
    # reaches the shared direct-roster scorer and aggregate topology.
    normalized = adapter._normalized_slate_v1(result)
    slates = tuple({
        **normalized,
        "source_ordinal": index,
        "slate_id": f"{season}-w{week:02d}",
    } for index, (season, week) in enumerate(adapter.l2b_panel.EXPECTED_SLATES))
    gradeable = adapter.grader.validate_external_normalized_terminal_v1(
        adapter_id=adapter.ADAPTER_ID, slates=slates
    )
    player_ids = {
        player_id
        for population in normalized["populations"]
        for lineup in population["lineups"]
        for player_id in lineup["roster_player_ids"]
    }
    player_scores = {
        (source_ordinal, player_id): 1
        for source_ordinal in range(adapter.TASK_COUNT)
        for player_id in player_ids
    }
    slate_grades = adapter.grader.score_normalized_slates_v1(
        slates=gradeable, player_scores=player_scores
    )
    aggregate = adapter.grader.aggregate_normalized_slate_grades_v1(
        slate_grades
    )
    assert len(aggregate) == 2 * 5 * 30
    assert sum(
        row["coordinate"]["selector_family"] == adapter.SELECTOR_FAMILIES[3]
        for row in aggregate
    ) == 2 * 5 * 3 * 3


def test_real_selector_results_pass_their_exact_pure_replay_validators(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = _candidates(150)
    projection = _projection(
        0,
        candidates=candidates,
        later_source_identity=_identity("gs://fixture/later.json", "later"),
    )
    monkeypatch.setattr(adapter, "WORLDS_PER_BLOCK", 8)
    def cross_score(*, candidate_rows=None, projection, **_kwargs):
        count = len(candidate_rows or projection["candidates"])
        matrix = np.arange(count * 8, dtype=np.float64).reshape(count, 8)
        matrix = np.ascontiguousarray((matrix % 251) + 1.0)
        matrix.flags.writeable = False
        return matrix
    monkeypatch.setattr(adapter, "_cross_score_projection_block_v1", cross_score)
    result = adapter._run_selectors_v1(
        fraction_id=adapter.FRACTION_IDS[0],
        heldout_block="R0",
        projection=projection,
        players=(SimpleNamespace(player_id="unused"),),
        worlds={block: SimpleNamespace(block=block) for block in adapter.WORLD_BLOCKS},
    )
    assert result["heldout_cross_score_executed"] is False
    assert "heldout_score_matrix_sha256" not in result
    assert result["book_count"] == adapter.BOOK_COUNT_PER_FRACTION_FOLD
    # The three incumbent selector payloads are embedded byte-for-byte; only
    # new registered challenger fields and book coordinates extend the result.
    one_block = np.ascontiguousarray(
        (np.arange(150 * 8, dtype=np.float64).reshape(150, 8) % 251) + 1.0
    )
    training = np.ascontiguousarray(
        np.concatenate([one_block] * 4, axis=1), dtype=np.float64
    )
    kwargs = {
        "sampled_lineup_ids": [row["lineup_id"] for row in candidates],
        "training_score_matrix": training,
        "candidate_rows": candidates,
        "training_blocks": projection["training_blocks"],
        "worlds_per_block": 8,
    }
    presets = adapter.successor.frozen_native_preset_registry_v1()
    expected_grouped = adapter.successor.run_grouped_native_selectors_v1(
        **kwargs, preset_registry=presets
    )
    expected_ranked = adapter.rank150.run_exact_rank150_continuation_v1(
        **kwargs, preset_registry=presets
    )
    expected_dpp = adapter.diversity.run_effective_independent_shots_selector_v1(
        **kwargs
    )
    assert adapter.canonical_json_bytes_v1(result["grouped_result"]) == (
        adapter.canonical_json_bytes_v1(expected_grouped)
    )
    assert adapter.canonical_json_bytes_v1(result["rank150_result"]) == (
        adapter.canonical_json_bytes_v1(expected_ranked)
    )
    assert adapter.canonical_json_bytes_v1(result["dpp_result"]) == (
        adapter.canonical_json_bytes_v1(expected_dpp)
    )


def test_infeasible_gamma_fails_closed_before_any_fraction_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = _candidates(150)
    shared = [f"shared-{slot}" for slot in range(6)]
    for index, row in enumerate(candidates):
        row["roster_player_ids"] = sorted([
            *shared,
            *[f"unique-{index:03d}-{slot}" for slot in range(3)],
        ])
    projection = _projection(
        0,
        candidates=candidates,
        later_source_identity=_identity("gs://fixture/later.json", "later"),
    )
    monkeypatch.setattr(adapter, "WORLDS_PER_BLOCK", 8)
    monkeypatch.setattr(
        adapter,
        "_cross_score_projection_block_v1",
        lambda *, candidate_rows, **_kwargs: np.zeros(
            (len(candidate_rows), 8), dtype=np.float64
        ),
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="frozen selector execution failed",
    ) as exc_info:
        adapter._run_selectors_v1(
            fraction_id=adapter.FRACTION_IDS[0],
            heldout_block="R0",
            projection=projection,
            players=(SimpleNamespace(player_id="unused"),),
            worlds={
                block: SimpleNamespace(block=block)
                for block in adapter.WORLD_BLOCKS
            },
        )
    assert isinstance(
        exc_info.value.__cause__, adapter.CorpusR6L2BSelectorAdapterV1Error
    )
    assert "lacks exact rank-150" in str(exc_info.value.__cause__)


def test_gamma3_partial_is_followup_while_three_active_arms_stay_exact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = _candidates(150)
    shared = [f"shared-{slot}" for slot in range(4)]
    for index, row in enumerate(candidates):
        row["roster_player_ids"] = sorted([
            *shared,
            *[f"unique-{index:03d}-{slot}" for slot in range(5)],
        ])
    projection = _projection(
        0,
        candidates=candidates,
        later_source_identity=_identity("gs://fixture/later.json", "later"),
    )
    monkeypatch.setattr(adapter, "WORLDS_PER_BLOCK", 8)
    monkeypatch.setattr(
        adapter,
        "_cross_score_projection_block_v1",
        lambda *, candidate_rows, **_kwargs: np.zeros(
            (len(candidate_rows), 8), dtype=np.float64
        ),
    )
    result = adapter._run_selectors_v1(
        fraction_id=adapter.FRACTION_IDS[0],
        heldout_block="R0",
        projection=projection,
        players=(SimpleNamespace(player_id="unused"),),
        worlds={
            block: SimpleNamespace(block=block)
            for block in adapter.WORLD_BLOCKS
        },
    )
    selectors = result["tail_diversity_result"]["selectors"]
    assert selectors[0]["strategy_id"] == (
        adapter.TAIL_DIVERSITY_FOLLOWUP_STRATEGY_ID
    )
    assert selectors[0]["status"] == "infeasible-before-exact-80"
    assert all(
        selector["status"] == "exact-rank-150"
        for selector in selectors[1:]
    )
    assert result["book_count"] == adapter.BOOK_COUNT_PER_FRACTION_FOLD
    assert adapter.TAIL_DIVERSITY_FOLLOWUP_STRATEGY_ID not in {
        book["coordinate"]["selector_id"] for book in result["books"]
    }


def test_rehashed_overlap_cap_violation_is_rejected_independently() -> None:
    candidates = _candidates(150)
    lineup_ids = [row["lineup_id"] for row in candidates]
    scores = np.zeros((150, 32), dtype=np.float64)
    result = adapter.diversity_challengers.run_diversity_challengers_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=["R1", "R2", "R3", "R4"],
        worlds_per_block=8,
    )
    tampered_candidates = deepcopy(candidates)
    first_id, second_id = result["selectors"][0]["ranked_lineup_ids"][:2]
    by_id = {row["lineup_id"]: row for row in tampered_candidates}
    first = list(by_id[first_id]["roster_player_ids"])
    second = list(by_id[second_id]["roster_player_ids"])
    by_id[second_id]["roster_player_ids"] = sorted([*first[:4], *second[4:]])
    roster_by_id = {
        row["lineup_id"]: row["roster_player_ids"]
        for row in tampered_candidates
    }
    tampered = deepcopy(result)
    for selector in tampered["selectors"]:
        for book in selector["entry_books"]:
            book["selected_rosters_sha256"] = adapter.canonical_sha256_v1([
                roster_by_id[lineup_id]
                for lineup_id in book["selected_lineup_ids"]
            ])
            book.pop("book_sha256")
            book["book_sha256"] = adapter.canonical_sha256_v1(book)
        selector["entry_book_sha256s"] = [
            book["book_sha256"] for book in selector["entry_books"]
        ]
        selector.pop("selector_result_sha256")
        selector["selector_result_sha256"] = adapter.canonical_sha256_v1(
            selector
        )
    tampered["selector_result_sha256s"] = [
        selector["selector_result_sha256"]
        for selector in tampered["selectors"]
    ]
    tampered.pop("result_sha256")
    tampered["result_sha256"] = adapter.canonical_sha256_v1(tampered)

    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="selected roster violates cap",
    ):
        adapter._validate_exact_tail_diversity_shapes_v1(
            challengers=tampered, candidate_rows=tampered_candidates
        )


def test_slate_result_rejects_any_added_realized_or_score_value_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle()
    manifest, manifest_identity = _manifest(bundle)
    monkeypatch.setattr(adapter, "WORLDS_PER_BLOCK", 8)
    manifest["worlds_per_block"] = 8
    manifest.pop("task_manifest_sha256")
    manifest = adapter._with_hash(manifest, field="task_manifest_sha256")
    _selector_fakes(monkeypatch, [])
    monkeypatch.setattr(
        adapter,
        "_cross_score_projection_block_v1",
        lambda *, projection, **_kwargs: np.zeros(
            (len(projection["candidates"]), 8), dtype=np.float64
        ),
    )
    result = adapter.build_slate_result_v1(
        source_ordinal=0,
        manifest=manifest,
        manifest_identity=manifest_identity,
        projection_bundle=bundle,
        players=(SimpleNamespace(player_id="unused"),),
        worlds_by_fraction={
            fraction_id: {
                block: SimpleNamespace(block=block)
                for block in adapter.WORLD_BLOCKS
            }
            for fraction_id in adapter.FRACTION_IDS
        },
    )
    tampered = dict(result)
    tampered.pop("slate_result_sha256")
    tampered["realized_scores"] = []
    tampered = adapter._with_hash(tampered, field="slate_result_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="slate-result fields differ",
    ):
        adapter.validate_slate_result_v1(tampered, projection_bundle=bundle)

    def rehash(row: dict[str, object], field: str) -> None:
        row.pop(field, None)
        row[field] = adapter.canonical_sha256_v1(row)

    nested = deepcopy(result)
    nested["fold_results"][0]["outcome_hint"] = None
    rehash(nested["fold_results"][0], "fold_result_sha256")
    nested["fold_result_sha256s"][0] = nested["fold_results"][0][
        "fold_result_sha256"
    ]
    rehash(nested, "slate_result_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error, match="fold binding"
    ):
        adapter.validate_slate_result_v1(nested, projection_bundle=bundle)

    nested = deepcopy(result)
    fraction = nested["fold_results"][0]["fraction_results"][0]
    fraction["realized_hint"] = []
    rehash(fraction, "fraction_result_sha256")
    fold = nested["fold_results"][0]
    fold["fraction_result_sha256s"][0] = fraction["fraction_result_sha256"]
    rehash(fold, "fold_result_sha256")
    nested["fold_result_sha256s"][0] = fold["fold_result_sha256"]
    rehash(nested, "slate_result_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error, match="fraction-result law"
    ):
        adapter.validate_slate_result_v1(nested, projection_bundle=bundle)

    nested = deepcopy(result)
    fraction = nested["fold_results"][0]["fraction_results"][0]
    book = fraction["books"][0]
    book["score_hint"] = 0
    rehash(book, "book_descriptor_sha256")
    fraction["books_sha256"] = adapter.canonical_sha256_v1(fraction["books"])
    rehash(fraction, "fraction_result_sha256")
    fold = nested["fold_results"][0]
    fold["fraction_result_sha256s"][0] = fraction["fraction_result_sha256"]
    rehash(fold, "fold_result_sha256")
    nested["fold_result_sha256s"][0] = fold["fold_result_sha256"]
    rehash(nested, "slate_result_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="exact selector prefixes",
    ):
        adapter.validate_slate_result_v1(nested, projection_bundle=bundle)

    # A fully rehashed book still cannot substitute another valid candidate
    # for the lineup selected by its exact persisted selector prefix.
    nested = deepcopy(result)
    fraction = nested["fold_results"][0]["fraction_results"][0]
    book = fraction["books"][0]
    replacement = nested["fold_results"][0]["candidate_lineup_ids"][-1]
    book["selected_lineup_ids"][-1] = replacement
    book["selected_lineup_ids_sha256"] = adapter.canonical_sha256_v1(
        book["selected_lineup_ids"]
    )
    rehash(book, "book_descriptor_sha256")
    fraction["books_sha256"] = adapter.canonical_sha256_v1(fraction["books"])
    rehash(fraction, "fraction_result_sha256")
    fold = nested["fold_results"][0]
    fold["fraction_result_sha256s"][0] = fraction["fraction_result_sha256"]
    rehash(fold, "fold_result_sha256")
    nested["fold_result_sha256s"][0] = fold["fold_result_sha256"]
    nested_book = nested["normalized_books"][0]
    nested_book["selected_lineup_ids"][-1] = replacement
    nested["normalized_books_sha256"] = adapter.canonical_sha256_v1(
        nested["normalized_books"]
    )
    rehash(nested, "slate_result_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="exact selector prefixes",
    ):
        adapter.validate_slate_result_v1(nested, projection_bundle=bundle)


def test_realized_reader_is_unreachable_until_terminal_replay_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def terminal(**_kwargs):
        calls.append("terminal")
        raise adapter.CorpusR6L2BSelectorAdapterV1Error("terminal replay failed")

    def outcome(**_kwargs):
        calls.append("outcome")
        raise AssertionError("outcome reader must remain unreachable")

    monkeypatch.setattr(adapter, "reopen_generic_grader_terminal_v1", terminal)
    monkeypatch.setattr(adapter.grader, "open_outcome_snapshot_surface_v1", outcome)
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="terminal replay failed",
    ):
        adapter.grade_l2b_selector_experiment_realized_v1(
            terminal_root_identity=_identity("gs://fixture/root.json", "root"),
            outcome_snapshot_identity=_identity(
                "gs://fixture/outcome.json", "outcome"
            ),
            read_terminal_exact=lambda _identity: b"",
            read_outcome_exact=lambda _identity: b"",
        )
    assert calls == ["terminal"]


def test_realized_adapter_reuses_common_slate_and_aggregate_grader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    later_identity = _identity("gs://fixture/later.json", "later")
    root_identity = _identity("gs://fixture/root.json", "root")
    manifest_identity = _identity("gs://fixture/manifest.json", "manifest")
    slates = tuple({
        "source_ordinal": index,
        "slate_id": f"{season}-w{week:02d}",
        "populations": [],
        "books": [],
        "later_source_identity": later_identity,
    } for index, (season, week) in enumerate(adapter.l2b_panel.EXPECTED_SLATES))
    opened = adapter.L2BGenericGraderTerminalV1(
        adapter_id=adapter.ADAPTER_ID,
        task_manifest={"task_manifest_sha256": "a" * 64},
        task_manifest_identity=manifest_identity,
        task_manifest_sha256="a" * 64,
        task_result_descriptors=tuple(),
        slates=slates,
        later_source_identity=later_identity,
        terminal_root={"terminal_root_sha256": "b" * 64},
        terminal_root_identity=root_identity,
    )

    def terminal(**_kwargs):
        calls.append("terminal")
        return opened

    def outcome(**_kwargs):
        calls.append("outcome")
        slate_keys = {
            index: (season, week, f"{season}-w{week:02d}")
            for index, (season, week) in enumerate(
                adapter.l2b_panel.EXPECTED_SLATES
            )
        }
        return (
            {
                "later_source_freeze_identity": later_identity,
                "outcome_snapshot_sha256": "c" * 64,
            },
            _identity("gs://fixture/outcome.json", "outcome"),
            {},
            slate_keys,
        )

    def score(*, slates, player_scores):
        calls.append("score")
        assert len(slates) == 54
        assert player_scores == {}
        return [{"roster_sum_operation_count": 1} for _ in slates]

    def aggregate(slate_grades):
        calls.append("aggregate")
        assert len(slate_grades) == 54
        return [{"complete": True}]

    monkeypatch.setattr(adapter, "reopen_generic_grader_terminal_v1", terminal)
    monkeypatch.setattr(
        adapter.grader, "validate_external_normalized_terminal_v1",
        lambda *, slates, **_kwargs: tuple(slates),
    )
    monkeypatch.setattr(adapter.grader, "open_outcome_snapshot_surface_v1", outcome)
    monkeypatch.setattr(adapter.grader, "score_normalized_slates_v1", score)
    monkeypatch.setattr(
        adapter.grader, "aggregate_normalized_slate_grades_v1", aggregate
    )
    grade = adapter.grade_l2b_selector_experiment_realized_v1(
        terminal_root_identity=root_identity,
        outcome_snapshot_identity=_identity(
            "gs://fixture/outcome.json", "outcome"
        ),
        read_terminal_exact=lambda _identity: b"",
        read_outcome_exact=lambda _identity: b"",
    )
    assert calls == ["terminal", "outcome", "score", "aggregate"]
    assert grade["adapter_id"] == adapter.ADAPTER_ID
    assert grade["source_slate_count"] == 54
    assert grade["roster_sum_operation_count"] == 54
    assert grade["terminal_before_first_outcome_read"] is True


def test_terminal_root_declares_generic_grader_surface_and_no_decision_authority() -> None:
    descriptors = []
    for index, (season, week) in enumerate(adapter.l2b_panel.EXPECTED_SLATES):
        descriptors.append({
            "source_ordinal": index,
            "slate_id": f"{season}-w{week:02d}",
            "task_result_identity": _identity(
                f"gs://fixture/result-{index:02d}.json", f"result-{index}"
            ),
            "task_result_sha256": f"{index + 1:064x}",
        })
    body = {
        "schema_version": adapter.TERMINAL_ROOT_SCHEMA,
        "contract_id": adapter.CONTRACT_ID,
        "adapter_id": adapter.ADAPTER_ID,
        "task_manifest_identity": _identity(
            "gs://fixture/manifest.json", "manifest"
        ),
        "task_manifest_sha256": "a" * 64,
        "control_projection_receipt_identity": _identity(
            "gs://fixture/control-receipt.json", "control-receipt"
        ),
        "control_projection_receipt_sha256": "c" * 64,
        "terminal_build_receipt_identity": _identity(
            "gs://fixture/build.json", "build"
        ),
        "terminal_build_receipt_sha256": "d" * 64,
        "source_commit_sha": "1" * 40,
        "immutable_image_digest": "sha256:" + "2" * 64,
        "immutable_image_uri": "fixture/image@sha256:" + "2" * 64,
        "reused_job_name": adapter.REUSED_JOB_NAME,
        "reused_job_uid": adapter.REUSED_JOB_UID,
        "execution_scope": adapter.FULL54_SCOPE,
        "l2b_panel_root_identity": _identity(
            "gs://fixture/panel.json", "panel"
        ),
        "l2b_panel_root_sha256": "b" * 64,
        "later_source_freeze_identity": _identity(
            "gs://fixture/later.json", "later"
        ),
        "source_slate_count": 54,
        "task_results": descriptors,
        "task_results_sha256": adapter.canonical_sha256_v1(descriptors),
        "fraction_registry": [
            dict(row) for row in adapter.l2b_panel.FRACTION_REGISTRY
        ],
        "selector_lattice": dict(adapter.SELECTOR_LATTICE),
        "generic_grader_adapter": {
            "adapter_id": adapter.ADAPTER_ID,
            "boundary": adapter.NORMALIZED_GRADER_BOUNDARY,
            "gradeability_validator": (
                "corpus_r6_novel_roster_realized_grader_v1."
                "validate_external_normalized_terminal_v1"
            ),
            "normalized_surface": "novel-roster-populations-and-books-v1",
            "realized_grade_schema": adapter.grader.REALIZED_GRADE_SCHEMA,
        },
        "all_task_results_exact_opened": True,
        "root_built_after_all_task_results": True,
        "terminal_before_first_outcome_read": True,
        "complete": True,
        **adapter._FALSE_POLICY,
    }
    root = adapter.validate_terminal_root_v1(
        adapter._with_hash(body, field="terminal_root_sha256")
    )
    assert root["generic_grader_adapter"]["adapter_id"] == adapter.ADAPTER_ID
    assert root["decision_authority"] is False
    assert root["uses_realized_outcomes"] is False


def test_task_cli_delegates_one_exact_manifest_and_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}

    def execute(**kwargs):
        observed.update(kwargs)
        return adapter.L2BSelectorTaskExecutionV1(
            result={
                "source_ordinal": 7,
                "slate_id": "2023-w08",
                "slate_result_sha256": "a" * 64,
            },
            result_identity=_identity("gs://fixture/result.json", "result"),
        )

    monkeypatch.setattr(adapter, "execute_selector_task_v1", execute)
    store = SimpleNamespace(read_exact=object(), publish_create_once=object())
    manifest_identity = _identity("gs://fixture/manifest.json", "manifest")
    result = cli.execute_task_from_request_v1(
        {"manifest_identity": manifest_identity, "task_index": 7}, store=store
    )
    assert observed["manifest_identity"] == manifest_identity
    assert observed["task_index"] == 7
    assert result["source_ordinal"] == 7
    assert result["uses_realized_outcomes"] is False


def test_dispatcher_binds_task0_scope_code_image_job_and_no_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = SimpleNamespace(read_exact=object(), publish_create_once=object())
    with pytest.raises(
        cli.RunCorpusR6L2BSelectorAdapterV1Error, match="default-off"
    ):
        cli.dispatch_task_from_environment_v1(store=store)
    monkeypatch.setenv(cli.ENABLE_ENV, "1")
    monkeypatch.setenv(
        cli.MANIFEST_IDENTITY_ENV,
        adapter.canonical_json_bytes_v1(
            _identity("gs://fixture/manifest.json", "manifest")
        ).decode("utf-8"),
    )
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "0")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "1")
    monkeypatch.setenv("CLOUD_RUN_TASK_ATTEMPT", "0")
    manifest_identity = _identity("gs://fixture/manifest.json", "manifest")
    manifest = {
        "execution_scope": adapter.TASK0_SCOPE,
        "execution_task_count": 1,
        "source_commit_sha": "1" * 40,
        "immutable_image_digest": "sha256:" + "2" * 64,
        "immutable_image_uri": "fixture/image@sha256:" + "2" * 64,
        "reused_job_uid": adapter.REUSED_JOB_UID,
    }
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    with pytest.raises(
        cli.RunCorpusR6L2BSelectorAdapterV1Error,
        match="code/image/job/scope",
    ):
        cli.dispatch_task_from_environment_v1(store=store)
    monkeypatch.setenv(cli.EXECUTION_SCOPE_ENV, adapter.TASK0_SCOPE)
    monkeypatch.setenv(cli.SOURCE_COMMIT_ENV, manifest["source_commit_sha"])
    monkeypatch.setenv(cli.IMAGE_DIGEST_ENV, manifest["immutable_image_digest"])
    monkeypatch.setenv(cli.REUSED_JOB_UID_ENV, adapter.REUSED_JOB_UID)
    monkeypatch.setattr(
        cli, "execute_task_from_request_v1",
        lambda request, **_kwargs: {"source_ordinal": request["task_index"]},
    )
    assert cli.dispatch_task_from_environment_v1(store=store) == {
        "source_ordinal": 0
    }
    manifest["execution_scope"] = adapter.FULL54_SCOPE
    manifest["execution_task_count"] = 54
    monkeypatch.setenv(cli.EXECUTION_SCOPE_ENV, adapter.FULL54_SCOPE)
    monkeypatch.setenv("CLOUD_RUN_TASK_INDEX", "53")
    monkeypatch.setenv("CLOUD_RUN_TASK_COUNT", "54")
    assert cli.dispatch_task_from_environment_v1(store=store) == {
        "source_ordinal": 53
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_commit_sha", "A" * 40, "fixed law"),
        ("immutable_image_digest", "tag-only", "fixed law"),
        ("immutable_image_uri", "fixture/image:mutable", "fixed law"),
        ("reused_job_uid", "00000000-0000-0000-0000-000000000000", "fixed law"),
        ("execution_scope", "all", "fixed law"),
        ("terminal_build_receipt_sha256", "A" * 64, "lowercase SHA"),
    ],
)
def test_manifest_rejects_code_build_image_job_and_scope_drift(
    field: str, value: object, message: str,
) -> None:
    manifest, _ = _manifest(_bundle())
    manifest.pop("task_manifest_sha256")
    manifest[field] = value
    if field == "execution_scope":
        manifest["execution_task_count"] = 54
    tampered = adapter._with_hash(manifest, field="task_manifest_sha256")
    with pytest.raises(adapter.CorpusR6L2BSelectorAdapterV1Error, match=message):
        adapter.validate_selector_manifest_v1(tampered)


def test_full54_manifest_requires_task0_smoke_and_accepts_authority_sample_below_250(
) -> None:
    manifest, _ = _manifest(_bundle())
    manifest.pop("task_manifest_sha256")
    manifest["task_rows"][0]["unique_roster_count_by_fold"] = [300] * 5
    manifest["task_rows"][0]["selector_candidate_count_by_fold"] = [175] * 5
    retained = adapter.validate_selector_manifest_v1(
        adapter._with_hash(manifest, field="task_manifest_sha256")
    )
    assert retained["task_rows"][0]["selector_candidate_count_by_fold"] == [175] * 5

    manifest = dict(retained)
    manifest.pop("task_manifest_sha256")
    manifest["task0_smoke_receipt_identity"] = None
    manifest["task0_smoke_receipt_sha256"] = None
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error, match="fixed law"
    ):
        adapter.validate_selector_manifest_v1(
            adapter._with_hash(manifest, field="task_manifest_sha256")
        )


def test_selector_lattice_survives_canonical_json_round_trip() -> None:
    manifest, _ = _manifest(_bundle())
    manifest.pop("task_manifest_sha256")
    # Reproduce the production failure class: an in-memory contract may carry
    # tuples even though canonical JSON necessarily reopens them as lists.
    lattice = dict(manifest["selector_lattice"])
    for field in (
        "grouped_native_entry_budgets",
        "exact_rank150_entry_budgets",
        "dpp_entry_budgets",
        "tail_ladder_diversity_entry_budgets",
        "tail_ladder_diversity_active_strategy_ids",
        "tail_ladder_diversity_followup_strategy_ids",
    ):
        lattice[field] = tuple(lattice[field])
    activation_gate = dict(lattice["tail_ladder_diversity_activation_gate"])
    activation_gate["required_entry_budgets"] = tuple(
        activation_gate["required_entry_budgets"]
    )
    lattice["tail_ladder_diversity_activation_gate"] = activation_gate
    manifest["selector_lattice"] = lattice
    in_memory = adapter._with_hash(manifest, field="task_manifest_sha256")
    assert adapter.validate_selector_manifest_v1(in_memory) == in_memory

    raw = adapter.canonical_json_bytes_v1(in_memory)
    reopened = adapter.batch.parse_canonical_json_bytes(
        raw, label="selector manifest round trip"
    )
    retained = adapter.validate_selector_manifest_v1(reopened)
    assert retained["selector_lattice"] == adapter._selector_lattice_v1()
    assert adapter.canonical_json_bytes_v1(retained) == raw


def test_unpinned_archived_law_cannot_become_full54_law() -> None:
    manifest, _ = _manifest(_bundle())
    manifest.pop("task_manifest_sha256")
    manifest["selector_lattice"] = dict(adapter._ARCHIVED_TASK0_LATTICE)
    tampered = adapter._with_hash(manifest, field="task_manifest_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="fixed law",
    ):
        adapter.validate_selector_manifest_v1(tampered)


def test_current_full54_law_has_exactly_300_aggregate_cells() -> None:
    lattice = adapter._selector_lattice_v1()
    assert lattice["selector_count_per_fraction_fold"] == 10
    assert lattice["book_count_per_fraction_fold"] == 30
    assert 2 * 5 * lattice["book_count_per_fraction_fold"] == 300


def test_l2b_is_explicitly_registered_with_generic_grader() -> None:
    assert adapter.ADAPTER_ID == adapter.grader.L2B_SELECTOR_ADAPTER
    assert adapter.ADAPTER_ID in adapter.grader.ADAPTER_IDS
    assert adapter.ADAPTER_ID in adapter.grader._ADAPTER_REGISTRY


def test_prepare_rejects_any_control_fold_below_150_unique_rosters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invalid_bundle = projection_contract.build_projection_bundle_v1(
        source_ordinal=0,
        fold_projections=[
            _projection(
                fold,
                candidates=_candidates(150, duplicate_second_roster=True),
                later_source_identity=_identity("gs://fixture/later.json", "later"),
            )
            for fold in range(5)
        ],
    )
    panel_tasks = [{
        "slate_id": f"{season}-w{week:02d}",
        "task_result_identity": _identity(
            f"gs://fixture/l2b-{index}.json", f"l2b-{index}"
        ),
        "task_result_sha256": f"{index + 1:064x}",
    } for index, (season, week) in enumerate(adapter.l2b_panel.EXPECTED_SLATES)]
    later_identity = _identity("gs://fixture/later.json", "later")
    monkeypatch.setattr(
        adapter.l2b_panel, "_read_terminal_build_receipt",
        lambda *args, **kwargs: (
            {
                "build_id": "11111111-1111-1111-1111-111111111111",
                "image_tag": "fixture/image:build-tag",
            },
            _identity("gs://fixture/build.json", "build"),
        ),
    )
    monkeypatch.setattr(
        adapter, "_open_panel_root_v1",
        lambda **kwargs: (
            {"task_results": panel_tasks, "panel_root_sha256": "a" * 64,
             "manifest_identity": _identity("gs://fixture/l2b-manifest.json", "lm"),
             "manifest_sha256": "b" * 64},
            _identity("gs://fixture/panel.json", "panel"),
            {"later_source_freeze_identity": later_identity},
            _identity("gs://fixture/l2b-manifest.json", "lm"),
        ),
    )
    projection_identities = [
        _identity(f"gs://fixture/projection-{index}.json", f"p-{index}")
        for index in range(54)
    ]
    monkeypatch.setattr(
        adapter, "_open_control_projection_authority_v1",
        lambda **kwargs: (
            {"layer_execution_receipt_sha256": "c" * 64},
            _identity("gs://fixture/control-receipt.json", "cr"),
            {"task_manifest_sha256": "d" * 64,
             "design_identity": _identity("gs://fixture/design.json", "design"),
             "topology_identity": _identity("gs://fixture/topology.json", "topology"),
             "topology_sha256": "e" * 64},
            _identity("gs://fixture/control-manifest.json", "cm"),
            {"design_sha256": "f" * 64, "topology": {}},
            projection_identities,
        ),
    )
    monkeypatch.setattr(
        adapter, "_open_projection_bundle_v1",
        lambda identity, **kwargs: (invalid_bundle, dict(identity)),
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error, match="unique-roster depth"
    ):
        adapter.prepare_selector_manifest_v1(
            l2b_panel_root_identity=_identity("gs://fixture/panel.json", "panel"),
            control_projection_receipt_identity=_identity(
                "gs://fixture/control-receipt.json", "cr"
            ),
            terminal_build_receipt_identity=_identity(
                "gs://fixture/build.json", "build"
            ),
            source_commit_sha="1" * 40,
            immutable_image_digest="sha256:" + "2" * 64,
            reused_job_name=adapter.REUSED_JOB_NAME,
            reused_job_uid=adapter.REUSED_JOB_UID,
            execution_scope=adapter.TASK0_SCOPE,
            task0_smoke_receipt_identity=None,
            output_prefix=adapter.OUTPUT_NAMESPACE + "prepare-fail/",
            read_exact=lambda identity: b"",
            publish_create_once=lambda uri, raw: pytest.fail("must not publish"),
        )


def test_control_projection_source_requires_full_layer_receipt_authority_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_identity = _identity("gs://fixture/control-receipt.json", "receipt")
    manifest_identity = _identity("gs://fixture/control-manifest.json", "manifest")
    def exact(_identity_value, *, label, **_kwargs):
        if label == "control projection layer receipt":
            return {}, receipt_identity
        if label == "control projection task manifest":
            return {}, manifest_identity
        raise AssertionError("design must remain unreachable")
    monkeypatch.setattr(adapter, "_exact_read_json", exact)
    monkeypatch.setattr(
        adapter.control_runtime, "validate_layer_execution_receipt_v1",
        lambda value: {"manifest_identity": manifest_identity},
    )
    monkeypatch.setattr(
        adapter.control_runtime, "validate_task_manifest_v1", lambda value: {}
    )
    def reject(*args, **kwargs):
        raise ValueError("terminal evidence differs")
    monkeypatch.setattr(
        adapter.control_runtime,
        "validate_layer_execution_receipt_authority_v1",
        reject,
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="exact authority replay failed",
    ):
        adapter._open_control_projection_authority_v1(
            receipt_identity=receipt_identity, read_exact=lambda identity: b""
        )


def test_duplicate_roster_is_removed_before_exact_budget_selection() -> None:
    candidates = _candidates(151, duplicate_second_roster=True)
    unique = adapter._unique_roster_candidates_v1(candidates)
    assert len(unique) == 150
    assert [row["lineup_id"] for row in unique[:2]] == [
        "lineup-000", "lineup-002"
    ]
    assert len({tuple(row["roster_player_ids"]) for row in unique}) == 150


def test_nested_selector_and_result_extras_fail_closed() -> None:
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="persisted selector result fields differ",
    ):
        adapter._validate_persisted_selector_shapes_v1(
            grouped={"result_sha256": "a" * 64, "realized_scores": []},
            ranked={},
            dpp={},
            challengers={},
            candidate_rows=[],
        )


def test_gradeability_failure_precedes_first_outcome_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    later_identity = _identity("gs://fixture/later.json", "later")
    opened = adapter.L2BGenericGraderTerminalV1(
        adapter_id=adapter.ADAPTER_ID,
        task_manifest={},
        task_manifest_identity=_identity("gs://fixture/manifest.json", "manifest"),
        task_manifest_sha256="a" * 64,
        task_result_descriptors=tuple(),
        slates=tuple(),
        later_source_identity=later_identity,
        terminal_root={"terminal_root_sha256": "b" * 64},
        terminal_root_identity=_identity("gs://fixture/root.json", "root"),
    )
    monkeypatch.setattr(
        adapter, "reopen_generic_grader_terminal_v1", lambda **kwargs: opened
    )
    def invalid(**kwargs):
        calls.append("gradeability")
        raise adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error(
            "coordinate coverage differs"
        )
    def outcome(**kwargs):
        calls.append("outcome")
        raise AssertionError("outcome must remain unreachable")
    monkeypatch.setattr(
        adapter.grader, "validate_external_normalized_terminal_v1", invalid
    )
    monkeypatch.setattr(
        adapter.grader, "open_outcome_snapshot_surface_v1", outcome
    )
    with pytest.raises(
        adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="coordinate coverage",
    ):
        adapter.grade_l2b_selector_experiment_realized_v1(
            terminal_root_identity=opened.terminal_root_identity,
            outcome_snapshot_identity=_identity("gs://fixture/outcome.json", "outcome"),
            read_terminal_exact=lambda identity: b"",
            read_outcome_exact=lambda identity: b"",
        )
    assert calls == ["gradeability"]


def test_public_gradeability_boundary_rejects_roster_alias_and_coordinate_gap() -> None:
    later = _identity("gs://fixture/later.json", "later")
    coordinate = {
        "adapter_id": adapter.ADAPTER_ID,
        "metric_kind": "selected-book",
        "entry_budget": 1,
    }
    coordinate_sha = adapter.canonical_sha256_v1(coordinate)
    slates = []
    for index, (season, week) in enumerate(adapter.l2b_panel.EXPECTED_SLATES):
        roster = [f"p-{slot}" for slot in range(9)]
        slates.append({
            "source_ordinal": index,
            "slate_id": f"{season}-w{week:02d}",
            "populations": [{
                "population_id": "population",
                "dimensions": {"entry_budget": 1},
                "lineups": [{
                    "lineup_id": "lineup-a",
                    "roster_player_ids": roster,
                    "roster_sha256": adapter.canonical_sha256_v1(roster),
                }],
            }],
            "books": [{
                "coordinate": coordinate,
                "coordinate_sha256": coordinate_sha,
                "population_id": "population",
                "selected_lineup_ids": ["lineup-a"],
            }],
            "later_source_identity": later,
        })
    validated = adapter.grader.validate_external_normalized_terminal_v1(
        adapter_id=adapter.ADAPTER_ID, slates=slates
    )
    assert len(validated) == 54

    alias = deepcopy(slates)
    alias[0]["populations"][0]["lineups"].append({
        "lineup_id": "lineup-b",
        "roster_player_ids": list(
            alias[0]["populations"][0]["lineups"][0]["roster_player_ids"]
        ),
        "roster_sha256": alias[0]["populations"][0]["lineups"][0][
            "roster_sha256"
        ],
    })
    with pytest.raises(
        adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="repeats a lineup ID or roster",
    ):
        adapter.grader.validate_external_normalized_terminal_v1(
            adapter_id=adapter.ADAPTER_ID, slates=alias
        )

    gap = deepcopy(slates)
    gap[-1]["books"] = []
    with pytest.raises(
        adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="no selected books",
    ):
        adapter.grader.validate_external_normalized_terminal_v1(
            adapter_id=adapter.ADAPTER_ID, slates=gap
        )


@pytest.mark.parametrize(
    ("scope", "count"),
    [(adapter.TASK0_SCOPE, 1), (adapter.FULL54_SCOPE, 54)],
)
def test_operator_configuration_exactly_binds_both_execution_scopes(
    scope: str, count: int,
) -> None:
    manifest, identity = _manifest(_bundle())
    manifest.pop("task_manifest_sha256")
    manifest["execution_scope"] = scope
    manifest["execution_task_count"] = count
    if scope == adapter.TASK0_SCOPE:
        manifest["task0_smoke_receipt_identity"] = None
        manifest["task0_smoke_receipt_sha256"] = None
    for row in manifest["task_rows"]:
        row["result_uri"] = (
            f"{manifest['output_prefix']}{scope}/selector-results/"
            f"{row['source_ordinal']:02d}-{row['slate_id']}.json"
        )
    manifest = adapter._with_hash(manifest, field="task_manifest_sha256")
    config = cli.build_job_configuration_v1(
        manifest=manifest, manifest_identity=identity
    )
    assert config["task_count"] == count
    assert config["parallelism"] == count
    assert config["max_retries"] == 0
    assert config["environment"][cli.EXECUTION_SCOPE_ENV] == scope
    assert config["environment"][cli.SOURCE_COMMIT_ENV] == manifest[
        "source_commit_sha"
    ]
    assert config["environment"][cli.REUSED_JOB_UID_ENV] == adapter.REUSED_JOB_UID
    assert config["image_digest"] == manifest["immutable_image_digest"]
    assert config["image_uri"] == manifest["immutable_image_uri"]
    assert config["gcloud_update_flags"]["--image"] == manifest[
        "immutable_image_uri"
    ]


def test_operator_collect_cannot_resolve_results_before_terminal_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, identity = _manifest(_bundle())
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **kwargs: (manifest, identity),
    )
    launch = cli.panel_operator.build_launch_result_v1(
        execution_name=f"{adapter.REUSED_JOB_NAME}-fixture",
        scope=adapter.FULL54_SCOPE,
    )
    monkeypatch.setattr(
        cli, "status_operator_v1",
        lambda **kwargs: {
            "scope": adapter.FULL54_SCOPE,
            "job_uid": adapter.REUSED_JOB_UID,
            "expected_task_count": 54,
            "succeeded_count": 1,
            "failed_count": 0,
            "cancelled_count": 0,
            "terminal_state": "ACTIVE",
            "scientific_outputs_read": False,
            "outcomes_read": False,
        },
    )
    class Store:
        read_exact = object()
        def open_known(self, *args, **kwargs):
            raise AssertionError("scientific result must remain unreachable")
    with pytest.raises(
        cli.RunCorpusR6L2BSelectorAdapterV1Error,
        match="before terminal success",
    ):
        cli.collect_operator_v1(
            manifest_identity=identity,
            launch=launch,
            store=Store(),
            runner=object(),
        )


def test_registered_generic_opener_rejects_task0_manifest_as_full54(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _task0_manifest(_bundle())
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    identities = [
        _identity(str(row["result_uri"]), f"result-{index}")
        for index, row in enumerate(manifest["task_rows"])
    ]
    with pytest.raises(
        adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="full54 execution scope",
    ):
        adapter.grader._open_l2b_selector_terminal(
            task_manifest_identity=manifest_identity,
            task_result_identities=identities,
            read_exact=lambda _identity_value: pytest.fail(
                "task0 manifest must fail before task results open"
            ),
        )


def test_registered_generic_opener_rejects_copied_result_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _manifest(_bundle())
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    identities = [
        _identity(str(row["result_uri"]), f"result-{index}")
        for index, row in enumerate(manifest["task_rows"])
    ]
    identities[1] = dict(identities[0])
    with pytest.raises(
        adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="54 unique task/result identities",
    ):
        adapter.grader._open_l2b_selector_terminal(
            task_manifest_identity=manifest_identity,
            task_result_identities=identities,
            read_exact=lambda _identity_value: pytest.fail(
                "copied identities must fail before task results open"
            ),
        )


def test_registered_generic_opener_rejects_noncanonical_result_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _manifest(_bundle())
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    monkeypatch.setattr(
        adapter, "_open_panel_root_v1",
        lambda **_kwargs: ({}, {}, {}, {}),
    )
    monkeypatch.setattr(
        adapter, "_open_projection_bundle_v1",
        lambda identity, **_kwargs: ({}, dict(identity)),
    )
    monkeypatch.setattr(
        adapter, "_open_l2b_task_worlds_v1", lambda **_kwargs: {}
    )
    monkeypatch.setattr(
        adapter, "_exact_replay_persisted_slate_v1", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        adapter, "_scoring_players_v1", lambda **_kwargs: tuple()
    )
    monkeypatch.setattr(
        adapter,
        "validate_slate_result_v1",
        lambda _body, **_kwargs: {
            "source_ordinal": 0,
            "slate_id": manifest["task_rows"][0]["slate_id"],
            "task_manifest_identity": manifest_identity,
            "task_manifest_sha256": manifest["task_manifest_sha256"],
            "slate_result_sha256": "a" * 64,
        },
    )
    identities = [
        _identity(
            (
                "gs://fixture/copied-result.json"
                if index == 0 else str(row["result_uri"])
            ),
            f"result-{index}",
        )
        for index, row in enumerate(manifest["task_rows"])
    ]
    later_identity = manifest["later_source_freeze_identity"]

    def exact(identity_value, **kwargs):
        if kwargs.get("label") == "registered L2b later-source freeze":
            return {}, dict(later_identity)
        return {}, dict(identity_value)

    monkeypatch.setattr(adapter, "_exact_read_json", exact)
    with pytest.raises(
        adapter.grader.CorpusR6NovelRosterRealizedGraderV1Error,
        match="task-result binding differs",
    ):
        adapter.grader._open_l2b_selector_terminal(
            task_manifest_identity=manifest_identity,
            task_result_identities=identities,
            read_exact=lambda _identity_value: b"",
        )


def test_manifest_opener_rejects_copied_publication_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _ = _manifest(_bundle())
    copied_identity = _identity("gs://fixture/copied-manifest.json", "copy")
    monkeypatch.setattr(
        adapter,
        "_exact_read_json",
        lambda *_args, **_kwargs: (manifest, copied_identity),
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="manifest publication URI differs",
    ):
        adapter._open_selector_manifest_v1(
            manifest_identity=copied_identity,
            read_exact=lambda _identity_value: b"",
        )


def test_full54_manifest_reopens_with_exact_archived_smoke_and_new_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _bundle()
    manifest, _ = _manifest(bundle)
    old_task0, old_task0_identity = _task0_manifest(bundle)
    smoke = _task0_smoke_receipt(old_task0, old_task0_identity)
    smoke.pop("smoke_receipt_sha256")
    smoke["l2b_panel_root_identity"] = manifest["l2b_panel_root_identity"]
    smoke["control_projection_receipt_identity"] = manifest[
        "control_projection_receipt_identity"
    ]
    smoke = adapter._with_hash(smoke, field="smoke_receipt_sha256")
    smoke_identity = _value_identity(
        f"{manifest['output_prefix']}task0-selector-smoke-receipt.json", smoke
    )
    monkeypatch.setattr(adapter, "_ARCHIVED_TASK0_SMOKE_IDENTITY", smoke_identity)

    new_build = {
        "build_id": "11111111-1111-1111-1111-111111111111",
        "image_tag": "fixture/image:new-current",
    }
    manifest.pop("task_manifest_sha256")
    manifest["terminal_build_receipt_sha256"] = adapter.canonical_sha256_v1(
        new_build
    )
    manifest["terminal_build_id"] = new_build["build_id"]
    manifest["immutable_image_uri"] = (
        "fixture/image@" + str(manifest["immutable_image_digest"])
    )
    manifest["task0_smoke_receipt_identity"] = smoke_identity
    manifest["task0_smoke_receipt_sha256"] = smoke["smoke_receipt_sha256"]
    manifest = adapter._with_hash(manifest, field="task_manifest_sha256")
    manifest_identity = _value_identity(
        f"{manifest['output_prefix']}selector-task-manifest-full54.json", manifest
    )

    def exact(identity_value, **_kwargs):
        if identity_value == manifest_identity:
            return manifest, manifest_identity
        if identity_value == smoke_identity:
            return smoke, smoke_identity
        raise AssertionError("unexpected exact open")

    monkeypatch.setattr(adapter, "_exact_read_json", exact)
    monkeypatch.setattr(
        adapter.l2b_panel, "_read_terminal_build_receipt",
        lambda *_args, **_kwargs: (
            new_build, manifest["terminal_build_receipt_identity"]
        ),
    )
    projection_identities = [
        row["projection_bundle_identity"] for row in manifest["task_rows"]
    ]
    monkeypatch.setattr(
        adapter, "_open_control_projection_authority_v1",
        lambda **_kwargs: (
            {"layer_execution_receipt_sha256": manifest[
                "control_projection_receipt_sha256"
            ]},
            manifest["control_projection_receipt_identity"],
            {
                "task_manifest_sha256": manifest[
                    "control_projection_manifest_sha256"
                ],
                "design_identity": manifest["control_design_identity"],
                "topology_identity": manifest["control_topology_identity"],
                "topology_sha256": manifest["control_topology_sha256"],
            },
            manifest["control_projection_manifest_identity"],
            {"design_sha256": manifest["control_design_sha256"], "topology": {}},
            projection_identities,
        ),
    )
    monkeypatch.setattr(
        adapter, "_open_projection_bundle_v1",
        lambda identity, **_kwargs: (bundle, dict(identity)),
    )
    observed: dict[str, object] = {}
    monkeypatch.setattr(
        adapter, "_replay_task0_smoke_authority_v1",
        lambda **kwargs: observed.update(kwargs) or smoke,
    )

    retained, retained_identity = adapter._open_selector_manifest_v1(
        manifest_identity=manifest_identity,
        read_exact=lambda _identity_value: b"",
    )
    assert retained == manifest
    assert retained_identity == manifest_identity
    assert observed["smoke_receipt_identity"] == smoke_identity
    assert observed["expected_terminal_build_receipt_identity"] == manifest[
        "terminal_build_receipt_identity"
    ]


def test_terminal_opener_rejects_custom_root_publication_uri(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _manifest(_bundle())
    root = {
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
    }
    copied_root_identity = _identity("gs://fixture/copied-root.json", "copy")
    monkeypatch.setattr(
        adapter,
        "_exact_read_json",
        lambda *_args, **_kwargs: (root, copied_root_identity),
    )
    monkeypatch.setattr(adapter, "validate_terminal_root_v1", lambda _value: root)
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="terminal root/manifest binding differs",
    ):
        adapter.reopen_generic_grader_terminal_v1(
            terminal_root_identity=copied_root_identity,
            read_exact=lambda _identity_value: b"",
        )


def test_terminal_opener_rejects_descriptor_result_uri_outside_manifest_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _manifest(_bundle())
    descriptors = [
        {
            "source_ordinal": index,
            "slate_id": row["slate_id"],
            "task_result_identity": _identity(
                (
                    "gs://fixture/copied-terminal-result.json"
                    if index == 0 else str(row["result_uri"])
                ),
                f"terminal-result-{index}",
            ),
            "task_result_sha256": f"{index + 1:064x}",
        }
        for index, row in enumerate(manifest["task_rows"])
    ]
    root = {
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "l2b_panel_root_identity": manifest["l2b_panel_root_identity"],
        "l2b_panel_root_sha256": manifest["l2b_panel_root_sha256"],
        "later_source_freeze_identity": manifest["later_source_freeze_identity"],
        "control_projection_receipt_identity": manifest[
            "control_projection_receipt_identity"
        ],
        "control_projection_receipt_sha256": manifest[
            "control_projection_receipt_sha256"
        ],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "terminal_build_receipt_sha256": manifest[
            "terminal_build_receipt_sha256"
        ],
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image_digest": manifest["immutable_image_digest"],
        "immutable_image_uri": manifest["immutable_image_uri"],
        "reused_job_name": manifest["reused_job_name"],
        "reused_job_uid": manifest["reused_job_uid"],
        "execution_scope": manifest["execution_scope"],
        "task_results": descriptors,
    }
    root_identity = _identity(manifest["terminal_root_uri"], "terminal-root")
    monkeypatch.setattr(adapter, "validate_terminal_root_v1", lambda _value: root)
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    monkeypatch.setattr(
        adapter,
        "_open_panel_root_v1",
        lambda **_kwargs: (
            {"panel_root_sha256": manifest["l2b_panel_root_sha256"]},
            manifest["l2b_panel_root_identity"],
            {"task_manifest_sha256": manifest["l2b_task_manifest_sha256"]},
            manifest["l2b_task_manifest_identity"],
        ),
    )
    monkeypatch.setattr(
        adapter, "_open_projection_bundle_v1",
        lambda identity, **_kwargs: ({}, dict(identity)),
    )
    monkeypatch.setattr(
        adapter,
        "validate_slate_result_v1",
        lambda _body, **_kwargs: {
            "source_ordinal": 0,
            "slate_id": manifest["task_rows"][0]["slate_id"],
            "slate_result_sha256": descriptors[0]["task_result_sha256"],
        },
    )
    monkeypatch.setattr(
        adapter, "_open_l2b_task_worlds_v1", lambda **_kwargs: {}
    )
    monkeypatch.setattr(
        adapter, "_exact_replay_persisted_slate_v1", lambda **_kwargs: None
    )
    monkeypatch.setattr(
        adapter, "_scoring_players_v1", lambda **_kwargs: tuple()
    )

    def exact(identity_value, **kwargs):
        label = kwargs.get("label")
        if label == "L2b selector terminal root":
            return root, root_identity
        if label == "L2b terminal later-source freeze":
            return {}, dict(manifest["later_source_freeze_identity"])
        return {}, dict(identity_value)

    monkeypatch.setattr(adapter, "_exact_read_json", exact)
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="terminal task-result replay differs",
    ):
        adapter.reopen_generic_grader_terminal_v1(
            terminal_root_identity=root_identity,
            read_exact=lambda _identity_value: b"",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("task0_manifest_identity", None, "identity"),
        ("task_result_identity", None, "identity"),
        ("task_result_sha256", "garbage", "SHA"),
    ],
)
def test_task0_smoke_rejects_null_identity_and_garbage_digest(
    field: str, value: object, message: str,
) -> None:
    manifest, manifest_identity = _task0_manifest(_bundle())
    receipt = _task0_smoke_receipt(manifest, manifest_identity)
    receipt.pop("smoke_receipt_sha256")
    receipt[field] = value
    receipt = adapter._with_hash(receipt, field="smoke_receipt_sha256")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error, match=message
    ):
        adapter._validate_task0_smoke_receipt_shape_v1(receipt)


def test_task0_smoke_cannot_gate_a_different_output_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _task0_manifest(_bundle())
    receipt = _task0_smoke_receipt(manifest, manifest_identity)
    smoke_identity = _value_identity(
        f"{manifest['output_prefix']}task0-selector-smoke-receipt.json",
        receipt,
    )
    different = dict(manifest)
    different["output_prefix"] = adapter.OUTPUT_NAMESPACE + "different-run/"
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (different, manifest_identity),
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="task0 smoke/full54 manifest authority differs",
    ):
        adapter._replay_task0_smoke_authority_v1(
            smoke_receipt=receipt,
            smoke_receipt_identity=smoke_identity,
            expected_l2b_panel_root_identity=manifest["l2b_panel_root_identity"],
            expected_control_projection_receipt_identity=manifest[
                "control_projection_receipt_identity"
            ],
            expected_terminal_build_receipt_identity=manifest[
                "terminal_build_receipt_identity"
            ],
            expected_source_commit_sha=manifest["source_commit_sha"],
            expected_immutable_image_digest=manifest["immutable_image_digest"],
            expected_reused_job_uid=manifest["reused_job_uid"],
            expected_output_prefix=manifest["output_prefix"],
            read_exact=lambda _identity_value: b"",
        )


def test_exact_archived_smoke_can_gate_different_current_build_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _ = _task0_manifest(_bundle())
    manifest.pop("task_manifest_sha256")
    manifest["selector_lattice"] = dict(adapter._ARCHIVED_TASK0_LATTICE)
    manifest = adapter._with_hash(manifest, field="task_manifest_sha256")
    manifest_identity = _value_identity(
        f"{manifest['output_prefix']}selector-task-manifest-task0.json",
        manifest,
    )
    result = {
        "slate_result_sha256": "6" * 64,
        "task_manifest_identity": manifest_identity,
        "task_manifest_sha256": manifest["task_manifest_sha256"],
        "selector_lattice": dict(adapter._ARCHIVED_TASK0_LATTICE),
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "uses_realized_outcomes": False,
    }
    result_identity = _value_identity(
        str(manifest["task_rows"][0]["result_uri"]), result
    )
    receipt = _task0_smoke_receipt(manifest, manifest_identity)
    receipt.pop("smoke_receipt_sha256")
    receipt["task_result_identity"] = result_identity
    receipt["task_result_sha256"] = result["slate_result_sha256"]
    receipt = adapter._with_hash(receipt, field="smoke_receipt_sha256")
    smoke_identity = _value_identity(
        f"{manifest['output_prefix']}task0-selector-smoke-receipt.json", receipt
    )
    monkeypatch.setattr(adapter, "_ARCHIVED_TASK0_SMOKE_IDENTITY", smoke_identity)
    monkeypatch.setattr(adapter, "_ARCHIVED_TASK0_MANIFEST_IDENTITY", manifest_identity)
    monkeypatch.setattr(adapter, "_ARCHIVED_TASK0_RESULT_IDENTITY", result_identity)
    monkeypatch.setattr(
        adapter, "_ARCHIVED_TASK0_MANIFEST_SELF_HASH",
        manifest["task_manifest_sha256"],
    )
    monkeypatch.setattr(
        adapter, "_ARCHIVED_TASK0_RESULT_SELF_HASH", result["slate_result_sha256"]
    )
    monkeypatch.setattr(
        adapter, "_ARCHIVED_TASK0_SOURCE_COMMIT_SHA", manifest["source_commit_sha"]
    )
    monkeypatch.setattr(
        adapter, "_ARCHIVED_TASK0_IMAGE_DIGEST", manifest["immutable_image_digest"]
    )
    monkeypatch.setattr(
        adapter, "_ARCHIVED_TASK0_BUILD_IDENTITY",
        manifest["terminal_build_receipt_identity"],
    )

    def exact(identity_value, **_kwargs):
        if identity_value == manifest_identity:
            return manifest, manifest_identity
        if identity_value == result_identity:
            return result, result_identity
        raise AssertionError("unexpected exact open")

    monkeypatch.setattr(adapter, "_exact_read_json", exact)
    retained = adapter._replay_task0_smoke_authority_v1(
        smoke_receipt=receipt,
        smoke_receipt_identity=smoke_identity,
        expected_l2b_panel_root_identity=manifest["l2b_panel_root_identity"],
        expected_control_projection_receipt_identity=manifest[
            "control_projection_receipt_identity"
        ],
        expected_terminal_build_receipt_identity=_identity(
            "gs://fixture/new-build.json", "new-build"
        ),
        expected_source_commit_sha="a" * 40,
        expected_immutable_image_digest="sha256:" + "b" * 64,
        expected_reused_job_uid=manifest["reused_job_uid"],
        expected_output_prefix=manifest["output_prefix"],
        read_exact=lambda _identity_value: b"",
    )
    assert retained == receipt


def test_prepare_routes_exact_archived_smoke_to_different_current_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _task0_manifest(_bundle())
    receipt = _task0_smoke_receipt(manifest, manifest_identity)
    smoke_identity = _value_identity(
        f"{manifest['output_prefix']}task0-selector-smoke-receipt.json", receipt
    )
    monkeypatch.setattr(adapter, "_ARCHIVED_TASK0_SMOKE_IDENTITY", smoke_identity)
    monkeypatch.setattr(
        adapter, "_exact_read_json",
        lambda *_args, **_kwargs: (receipt, smoke_identity),
    )
    observed: dict[str, object] = {}

    def replay(**kwargs):
        observed.update(kwargs)
        return receipt

    monkeypatch.setattr(adapter, "_replay_task0_smoke_authority_v1", replay)

    class ReachedNewBuild(Exception):
        pass

    monkeypatch.setattr(
        adapter.l2b_panel,
        "_read_terminal_build_receipt",
        lambda *args, **kwargs: (_ for _ in ()).throw(ReachedNewBuild()),
    )
    new_build = _identity("gs://fixture/new-build.json", "new-build")
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="terminal build receipt replay failed",
    ):
        adapter.prepare_selector_manifest_v1(
            l2b_panel_root_identity=manifest["l2b_panel_root_identity"],
            control_projection_receipt_identity=manifest[
                "control_projection_receipt_identity"
            ],
            terminal_build_receipt_identity=new_build,
            source_commit_sha="a" * 40,
            immutable_image_digest="sha256:" + "b" * 64,
            reused_job_name=adapter.REUSED_JOB_NAME,
            reused_job_uid=adapter.REUSED_JOB_UID,
            execution_scope=adapter.FULL54_SCOPE,
            task0_smoke_receipt_identity=smoke_identity,
            output_prefix=manifest["output_prefix"],
            read_exact=lambda _identity_value: b"",
            publish_create_once=lambda *_args: pytest.fail("must not publish"),
        )
    assert observed["expected_terminal_build_receipt_identity"] == new_build
    assert observed["expected_source_commit_sha"] == "a" * 40
    assert observed["expected_immutable_image_digest"] == "sha256:" + "b" * 64


def test_task0_manifest_cannot_execute_task_index_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, manifest_identity = _task0_manifest(_bundle())
    monkeypatch.setattr(
        adapter, "_open_selector_manifest_v1",
        lambda **_kwargs: (manifest, manifest_identity),
    )
    with pytest.raises(
        adapter.CorpusR6L2BSelectorAdapterV1Error,
        match="task index differs from execution scope",
    ):
        adapter.execute_selector_task_v1(
            manifest_identity=manifest_identity,
            task_index=1,
            read_exact=lambda _identity_value: pytest.fail(
                "out-of-scope task must fail before panel open"
            ),
            publish_create_once=lambda _uri, _raw: pytest.fail(
                "out-of-scope task must never publish"
            ),
        )
