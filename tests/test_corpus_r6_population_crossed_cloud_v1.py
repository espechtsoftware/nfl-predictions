from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_authority_v1 as population_authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as population_runtime,
)
from nfl_dfs.research import corpus_r6_population_crossed_cloud_v1 as cloud
from nfl_dfs.research import (
    corpus_r6_population_crossed_scoring_v1 as crossed,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import residual_world_columns as rw


def _identity(uri: str, value: object, generation: int = 1) -> dict[str, object]:
    raw = population_authority.canonical_bytes_v1(value)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _manifest_fixture(monkeypatch: pytest.MonkeyPatch):
    population_bindings = []
    result_bodies: list[dict[str, object]] = []
    result_identities: list[dict[str, object]] = []
    objects: dict[tuple[str, str], bytes] = {}
    for source in range(cloud.TASK_COUNT):
        profile_uris = {
            profile_id: (
                f"gs://fixture/population/slates/{source:02d}/"
                f"{profile_id}/lineups.json"
            )
            for profile_id in profiles.PROFILE_ORDER
        }
        generation_request_sha = sha256(f"request-{source}".encode()).hexdigest()
        population_request = {
            "request_sha256": generation_request_sha,
            "projection_bundle_identity": {
                "uri": f"gs://fixture/projections/{source:02d}.json",
                "generation": str(source + 1),
                "sha256": sha256(f"projection-{source}".encode()).hexdigest(),
                "bytes": len(f"projection-{source}".encode()),
            },
            "expected_outputs": {
                "profile_lineup_uris": profile_uris,
                "task_result_uri": (
                    f"gs://fixture/population/slates/{source:02d}/task-result.json"
                ),
            },
        }
        population_bindings.append({
            "task_binding_sha256": sha256(f"binding-{source}".encode()).hexdigest(),
            "request": population_request,
        })
        profile_results = []
        for profile_ordinal, profile_id in enumerate(profiles.PROFILE_ORDER):
            lineup_body = {"profile": profile_id, "source": source}
            lineup_identity = _identity(
                profile_uris[profile_id],
                lineup_body,
                generation=10_000 + source * 3 + profile_ordinal,
            )
            profile_results.append({
                "profile_id": profile_id,
                "lineups_identity": lineup_identity,
                "unique_lineup_count": 250,
            })
        result_body = {
            "task_index": source,
            "source_ordinal": source,
            "request_sha256": generation_request_sha,
            "source_authority": {
                "slate_id": f"2023-w{source + 1:02d}",
            },
            "profile_results": profile_results,
        }
        result_body["task_result_sha256"] = population_authority.canonical_sha256_v1(
            result_body
        )
        result_identity = _identity(
            population_request["expected_outputs"]["task_result_uri"],
            result_body,
            generation=20_000 + source,
        )
        raw = population_authority.canonical_bytes_v1(result_body)
        objects[(result_identity["uri"], result_identity["generation"])] = raw
        result_bodies.append(result_body)
        result_identities.append(result_identity)

    population_manifest = {
        "task_manifest_sha256": "a" * 64,
        "task_bindings": population_bindings,
    }
    population_identity = _identity(
        "gs://fixture/population/task-manifest.json",
        population_manifest,
        generation=999,
    )
    objects[(population_identity["uri"], population_identity["generation"])] = (
        population_authority.canonical_bytes_v1(population_manifest)
    )

    monkeypatch.setattr(
        population_authority,
        "validate_task_manifest_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        population_runtime,
        "validate_task_result_v1",
        lambda value: dict(value),
    )

    def _read_exact(identity):
        return objects[(str(identity["uri"]), str(identity["generation"]))]

    manifest = cloud.build_task_manifest_v1(
        population_task_manifest_identity=population_identity,
        population_task_result_identities=result_identities,
        output_prefix=(
            current_contract.OUTPUT_NAMESPACE
            + "population-crossed/fixture-v1/"
        ),
        code_commit="b" * 40,
        image_digest="sha256:" + "c" * 64,
        reused_job_name="atlas-cbc-32g-full-2023-w8-v1",
        read_exact=_read_exact,
    )
    return manifest, population_identity, result_bodies, result_identities


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = population_authority.canonical_sha256_v1({
        key: row for key, row in value.items() if key != field
    })


def test_thin_manifest_binds_54_completed_population_tasks_and_one_reused_job(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest, population_identity, _bodies, result_identities = _manifest_fixture(
        monkeypatch
    )
    assert manifest["task_count"] == 54
    assert manifest["population_task_manifest_identity"] == population_identity
    assert manifest["population_task_result_identities"] == result_identities
    assert manifest["fold_count_per_slate"] == 5
    assert manifest["profile_count_per_fold"] == 3
    assert manifest["selectors_per_profile_fold"] == 7
    assert manifest["selector_cells_per_slate"] == 105
    assert manifest["one_reused_job_for_all_slates"] is True
    assert manifest["per_profile_or_parameter_deploy_allowed"] is False
    assert manifest["policy"]["uses_realized_outcomes"] is False
    assert len(manifest["task_bindings"]) == 54
    for source, binding in enumerate(manifest["task_bindings"]):
        request = binding["request"]
        assert request["task_index"] == source
        assert request["population_task_result_identity"] == result_identities[source]
        assert tuple(request["profile_lineup_identities"]) == profiles.PROFILE_ORDER
        assert binding["result_uri"].endswith(
            f"slates/{source:02d}/selection-result.json"
        )
    assert cloud.validate_task_manifest_v1(deepcopy(manifest)) == manifest

    raw = population_authority.canonical_bytes_v1(manifest)
    identity = _identity(
        "gs://fixture/population-crossed/task-manifest.json", manifest, generation=77
    )
    job = cloud.build_cloud_run_job_configuration_v1(
        task_manifest=manifest, task_manifest_identity=identity
    )
    assert len(raw) == identity["bytes"]
    assert job["reused_job_name"] == "atlas-cbc-32g-full-2023-w8-v1"
    assert job["task_count"] == job["parallelism"] == 54
    assert job["max_retries"] == 0
    assert job["new_job_creation_allowed"] is False
    assert job["per_profile_or_parameter_deploy_allowed"] is False


def test_manifest_rejects_rehashed_profile_shortfall_before_cloud_compute(
    monkeypatch: pytest.MonkeyPatch,
):
    manifest, *_ = _manifest_fixture(monkeypatch)
    poisoned = deepcopy(manifest)
    binding = poisoned["task_bindings"][0]
    request = binding["request"]
    request["profile_unique_lineup_counts"][profiles.PROFILE_ORDER[-1]] = 149
    _rehash(request, "request_sha256")
    binding["request_sha256"] = request["request_sha256"]
    _rehash(binding, "task_binding_sha256")
    poisoned["task_binding_sha256s"][0] = binding["task_binding_sha256"]
    _rehash(poisoned, "task_manifest_sha256")
    with pytest.raises(
        cloud.CorpusR6PopulationCrossedCloudV1Error,
        match="fixed authority differs",
    ):
        cloud.validate_task_manifest_v1(poisoned)


def _object_identity(label: str) -> dict[str, object]:
    raw = label.encode()
    return {
        "uri": f"gs://fixture/{label}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _task_request() -> dict[str, object]:
    profile_identities = {
        profile_id: _object_identity(f"{profile_id}-lineups")
        for profile_id in profiles.PROFILE_ORDER
    }
    body = {
        "schema": cloud.TASK_REQUEST_SCHEMA,
        "task_index": 0,
        "source_ordinal": 0,
        "population_task_manifest_identity": _object_identity("population-manifest"),
        "population_task_manifest_sha256": "1" * 64,
        "population_task_binding_sha256": "2" * 64,
        "population_generation_request_sha256": "3" * 64,
        "population_task_result_identity": _object_identity("population-result"),
        "population_task_result_sha256": "4" * 64,
        "projection_bundle_identity": _object_identity("projection"),
        "profile_lineup_identities": profile_identities,
        "profile_lineup_identities_sha256": population_authority.canonical_sha256_v1(
            profile_identities
        ),
        "profile_unique_lineup_counts": {
            profile_id: 250 for profile_id in profiles.PROFILE_ORDER
        },
        "profile_order": list(profiles.PROFILE_ORDER),
        "fold_order": list(rw.WORLD_BLOCKS),
        "expected_result_uri": (
            current_contract.OUTPUT_NAMESPACE
            + "population-crossed/fixture-v1/slates/00/selection-result.json"
        ),
        "code_commit": "5" * 40,
        "image_digest": "sha256:" + "6" * 64,
        "reused_job_name": "atlas-cbc-32g-full-2023-w8-v1",
        "policy": dict(cloud._POLICY),
    }
    return {**body, "request_sha256": population_authority.canonical_sha256_v1(body)}


def _prefix(ids: tuple[str, ...], size: int) -> dict[str, object]:
    selected = list(ids[:size])
    body = {
        "prefix_size": size,
        "selected_lineup_ids": selected,
        "selected_lineup_ids_sha256": population_authority.canonical_sha256_v1(
            selected
        ),
        "selected_rosters_sha256": sha256(
            f"rosters-{ids[0]}-{size}".encode()
        ).hexdigest(),
    }
    return {**body, "prefix_sha256": population_authority.canonical_sha256_v1(body)}


def _selector_result(profile_id: str, ids: tuple[str, ...]) -> dict[str, object]:
    grouped_selectors = [
        {
            "ordinal": ordinal,
            "preset_id": f"grouped-{ordinal}",
            "selector_result_sha256": f"{ordinal + 1}" * 64,
            "prefixes": [_prefix(ids, size) for size in successor.PREFIX_SIZES],
        }
        for ordinal in range(3)
    ]
    grouped = {
        "schema_version": successor.RESULT_SCHEMA,
        "selector_count": 3,
        "selectors": grouped_selectors,
        "result_sha256": "a" * 64,
    }
    ranked_selectors = [
        {
            "ordinal": ordinal,
            "preset_id": f"rank150-{ordinal}",
            "selector_result_sha256": f"{ordinal + 4}" * 64,
            "entry_books": [_prefix(ids, size) for size in rank150.ENTRY_BUDGETS],
        }
        for ordinal in range(3)
    ]
    ranked = {
        "schema_version": rank150.RESULT_SCHEMA,
        "selector_count": 3,
        "selectors": ranked_selectors,
        "ranking_depth": rank150.RANKING_DEPTH,
        "result_sha256": "b" * 64,
    }
    dpp = {
        "schema_version": diversity.RESULT_SCHEMA,
        "strategy_contract": {"strategy_id": "dpp-fixture"},
        "entry_budget": diversity.ENTRY_BUDGET,
        "prefixes": [_prefix(ids, size) for size in diversity.PREFIX_SIZES],
        "result_sha256": "c" * 64,
    }
    body = {
        "schema": crossed.SELECTOR_RESULT_SCHEMA,
        "profile_id": profile_id,
        "source_arm_id": profile_id,
        "heldout_block_label_only": "R4",
        "selection_binding": {},
        "selection_binding_sha256": "d" * 64,
        "grouped_result": grouped,
        "grouped_result_sha256": grouped["result_sha256"],
        "rank150_result": ranked,
        "rank150_result_sha256": ranked["result_sha256"],
        "dpp_result": dpp,
        "dpp_result_sha256": dpp["result_sha256"],
        "selector_input_source_arm_registry": [profile_id],
        "heldout_score_columns_present": False,
        "heldout_matrix_or_digest_read": False,
        "realized_outcomes_read": False,
    }
    return {
        **body,
        "selector_result_sha256": population_authority.canonical_sha256_v1(body),
    }


def _fold_inputs(profile_id: str, heldout: str):
    ids = tuple(
        f"{profiles.PROFILE_ORDER.index(profile_id):02d}{heldout}lineup-{index:03d}"
        for index in range(150)
    )
    candidate = tuple({
        "lineup_id": lineup_id,
        "roster_player_ids": [f"p{index}-{slot}" for slot in range(9)],
    } for index, lineup_id in enumerate(ids))
    selection_body = {
        "fixture": f"selection-{profile_id}-{heldout}",
    }
    selection_binding = {
        **selection_body,
        "selection_binding_sha256": population_authority.canonical_sha256_v1(
            selection_body
        ),
    }
    evaluation_body = {
        "fixture": f"evaluation-{profile_id}-{heldout}",
    }
    evaluation_binding = {
        **evaluation_body,
        "evaluation_binding_sha256": population_authority.canonical_sha256_v1(
            evaluation_body
        ),
    }
    fit = np.zeros((150, 4), dtype=np.float64)
    heldout_scores = np.zeros((150, 1), dtype=np.float64)
    fit.flags.writeable = False
    heldout_scores.flags.writeable = False
    return crossed.PopulationCrossedFoldInputsV1(
        selection=crossed.PopulationCrossedSelectionInputsV1(
            profile_id=profile_id,
            heldout_block_label_only=heldout,
            training_blocks=tuple(
                block for block in rw.WORLD_BLOCKS if block != heldout
            ),
            worlds_per_block=1,
            sampled_lineup_ids=ids,
            candidate_rows=candidate,
            training_score_matrix=fit,
            binding=selection_binding,
        ),
        evaluation=crossed.PopulationCrossedEvaluationInputsV1(
            profile_id=profile_id,
            heldout_block=heldout,
            worlds_per_block=1,
            sampled_lineup_ids=ids,
            roster_player_ids=tuple(
                tuple(row["roster_player_ids"]) for row in candidate
            ),
            heldout_score_matrix=heldout_scores,
            binding=evaluation_binding,
        ),
    )


def _fold_plan(heldout: str) -> dict[str, object]:
    profile_rows = []
    for profile_id in profiles.PROFILE_ORDER:
        inputs = _fold_inputs(profile_id, heldout)
        sampled = list(inputs.selection.sampled_lineup_ids)
        candidates = list(inputs.selection.candidate_rows)
        profile_rows.append({
            "profile_id": profile_id,
            "profile_plan_sha256": sha256(
                f"plan-{profile_id}-{heldout}".encode()
            ).hexdigest(),
            "sampled_lineup_count": len(sampled),
            "sampled_lineup_ids": sampled,
            "sampled_lineup_ids_sha256": population_authority.canonical_sha256_v1(
                sampled
            ),
            "sampled_candidate_rows": candidates,
            "sampled_candidate_rows_sha256": population_authority.canonical_sha256_v1(
                candidates
            ),
        })
    return {
        "plan_sha256": sha256(f"plan-{heldout}".encode()).hexdigest(),
        "common_count": 150,
        "profiles": profile_rows,
    }


def test_slate_task_runs_all_five_by_three_crosses_and_emits_evaluator_recipes(
    monkeypatch: pytest.MonkeyPatch,
):
    plans: list[str] = []
    materialized: list[tuple[str, str]] = []
    selector_calls: list[tuple[str, str]] = []

    def _plan(**kwargs):
        heldout = str(kwargs["heldout_block"])
        plans.append(heldout)
        return _fold_plan(heldout)

    def _materialize(*, plan, prepared, profile_id):
        heldout = next(
            block for block in rw.WORLD_BLOCKS
            if plan["plan_sha256"] == sha256(f"plan-{block}".encode()).hexdigest()
        )
        materialized.append((heldout, profile_id))
        return _fold_inputs(profile_id, heldout)

    def _select(value):
        selector_calls.append((value.heldout_block_label_only, value.profile_id))
        return _selector_result(value.profile_id, value.sampled_lineup_ids)

    monkeypatch.setattr(crossed, "build_population_crossed_fold_plan_v1", _plan)
    monkeypatch.setattr(
        crossed, "materialize_population_crossed_profile_fold_v1", _materialize
    )
    monkeypatch.setattr(crossed, "run_population_crossed_selectors_v1", _select)

    request = _task_request()
    source = {
        "slate_id": "2023-w01",
        "source_authority_sha256": "7" * 64,
        "later_source_identity": _object_identity("later"),
        "world_artifact_identities": {
            f"world_artifact_{block.casefold()}": _object_identity(block)
            for block in rw.WORLD_BLOCKS
        },
    }
    result = cloud.build_slate_result_v1(
        request=request,
        task_binding_sha256="8" * 64,
        prepared=object(),
        profile_lineups_by_id={profile_id: {} for profile_id in profiles.PROFILE_ORDER},
        source=source,
    )
    assert plans == list(rw.WORLD_BLOCKS)
    assert materialized == selector_calls
    assert len(materialized) == 15
    assert result["profile_fold_count"] == 15
    assert result["selector_cell_count"] == 105
    assert result["heldout_score_values_persisted"] is False
    assert result["realized_outcomes_read"] is False
    for heldout, fold in zip(rw.WORLD_BLOCKS, result["fold_results"], strict=True):
        assert fold["heldout_block"] == heldout
        for profile_id, row in zip(
            profiles.PROFILE_ORDER, fold["profile_results"], strict=True
        ):
            assert row["source_arm_id"] == profile_id
            assert row["selector_cell_count"] == 7
            assert len(row["evaluation_book_descriptors"]) == 7
            assert sorted({
                budget
                for descriptor in row["evaluation_book_descriptors"]
                for budget in descriptor["entry_budgets"]
            }) == [4, 14, 80, 100, 150]
            assert row["evaluator_recipe"]["heldout_block"] == heldout
            assert row["evaluator_recipe"]["heldout_score_values_persisted"] is False
            assert row["selector_result"]["heldout_matrix_or_digest_read"] is False
    assert cloud.validate_slate_result_v1(deepcopy(result)) == result

    replay_inputs = cloud.reconstruct_profile_fold_for_evaluation_v1(
        slate_result=result,
        prepared=object(),
        profile_lineups_by_id={profile_id: {} for profile_id in profiles.PROFILE_ORDER},
        heldout_block="R3",
        profile_id=profiles.PROFILE_ORDER[1],
    )
    assert replay_inputs.evaluation.heldout_block == "R3"
    assert replay_inputs.selection.profile_id == profiles.PROFILE_ORDER[1]


def _load_cli_module():
    path = Path("scripts/run_corpus_r6_population_crossed_cloud_v1.py")
    spec = importlib.util.spec_from_file_location("population_crossed_cli", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatcher_command_and_ambient_structure_guards_fail_closed():
    cli = _load_cli_module()
    command = b"\0".join(value.encode() for value in cloud.DISPATCHER_COMMAND) + b"\0"
    assert cli.observed_dispatcher_command_v1(command) == list(
        cloud.DISPATCHER_COMMAND
    )

    class _NoStore:
        def read_exact(self, _identity):
            raise AssertionError("store must not be reached")

    with pytest.raises(
        cli.RunCorpusR6PopulationCrossedCloudV1Error,
        match="ambient inherited structure keys",
    ):
        cli.execute_environment_task_v1(
            {
                cloud.ENABLE_ENV: "1",
                "CLOUD_RUN_TASK_INDEX": "0",
                next(iter(profiles.STRUCTURE_ENV_KEYS)): "1",
            },
            store=_NoStore(),
            observed_command=list(cloud.DISPATCHER_COMMAND),
        )


def test_task_completion_is_compact_and_binds_the_published_slate_result():
    body = {
        "schema": cloud.TASK_COMPLETION_SCHEMA,
        "task_index": 7,
        "source_ordinal": 7,
        "slate_id": "2023-w08",
        "task_manifest_identity": _object_identity("crossed-manifest"),
        "task_binding_sha256": "a" * 64,
        "slate_result_identity": _object_identity("crossed-slate-result"),
        "slate_result_sha256": "b" * 64,
        "fold_count": 5,
        "profile_fold_count": 15,
        "selector_cell_count": 105,
        "heldout_score_values_persisted": False,
        "realized_outcomes_read": False,
    }
    completion = {
        **body,
        "task_completion_sha256": population_authority.canonical_sha256_v1(body),
    }
    assert cloud.validate_task_completion_v1(completion) == completion
    poisoned = deepcopy(completion)
    poisoned["heldout_score_values_persisted"] = True
    _rehash(poisoned, "task_completion_sha256")
    with pytest.raises(
        cloud.CorpusR6PopulationCrossedCloudV1Error,
        match="completion authority differs",
    ):
        cloud.validate_task_completion_v1(poisoned)
