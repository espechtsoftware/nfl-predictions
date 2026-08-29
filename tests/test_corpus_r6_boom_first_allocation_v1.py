from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from itertools import combinations, islice

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.research import corpus_r6_boom_first_allocation_v1 as subject


def _identity(marker: str = "a") -> dict[str, object]:
    return {
        "uri": "gs://fixture/source.json",
        "generation": "7",
        "sha256": marker * 64,
        "bytes": 123,
    }


_MANIFEST_IDENTITY = _identity("8")
_MANIFEST_SHA256 = "9" * 64
_TERMINAL_BUILD_IDENTITY = _identity("7")
_EXECUTION_ID = "boom-first-fixture-execution"
_JOB_NAME = "boom-first-fixture-job"
_JOB_UID = "boom-first-fixture-job-uid"
_SERVICE_ACCOUNT = "boom-first-fixture@example.iam.gserviceaccount.com"
_PROJECT_ID = "nfl-predictions-503414"
_REGION = "us-central1"
_TASK0_SMOKE_SHA256 = "6" * 64
_LAUNCH_CLAIM_IDENTITY = _identity("3")
_LAUNCH_RECEIPT_IDENTITY = _identity("2")
_LAUNCH_RECEIPT_SHA256 = "1" * 64


def _runtime_identity(ordinal: int = 0) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": subject.RUNTIME_AUTHORITY_SCHEMA,
        "execution_mode": "provider-task",
        "source_ordinal": ordinal,
        "task_count": subject.TASK_COUNT,
        "task_attempt": 0,
        "execution_id": _EXECUTION_ID,
        "job_name": _JOB_NAME,
        "reused_job_uid": _JOB_UID,
        "service_account": _SERVICE_ACCOUNT,
        "project_id": _PROJECT_ID,
        "region": _REGION,
        "manifest_identity": dict(_MANIFEST_IDENTITY),
        "manifest_sha256": _MANIFEST_SHA256,
        "terminal_build_receipt_identity": dict(_TERMINAL_BUILD_IDENTITY),
        "code_commit": "5" * 40,
        "image_digest": "sha256:" + "4" * 64,
        "immutable_image_uri": (
            "us-central1-docker.pkg.dev/fixture/repo/image@sha256:" + "4" * 64
        ),
        "task0_smoke_sha256": _TASK0_SMOKE_SHA256,
        "observed_command": [
            "/usr/local/bin/python3.11", "-I",
            "/app/scripts/run_corpus_r6_boom_first_allocation_v1.py",
            "task", "--execute",
        ],
        "authority_source": (
            "reserved-cloud-run-metadata-and-exact-process-command"
        ),
        "generation_and_selection_wall_seconds": 3.0,
    }
    return {
        **body,
        "runtime_authority_sha256": subject.canonical_sha256_v1(body),
    }


def _provider_terminal_execution() -> dict[str, object]:
    job = {
        "job_name": _JOB_NAME,
        "job_uid": _JOB_UID,
        "service_account": _SERVICE_ACCOUNT,
        "project_id": _PROJECT_ID,
        "region": _REGION,
        "task_count": subject.TASK_COUNT,
        "container_environment": {
            subject.TASK0_SMOKE_ENVIRONMENT: _TASK0_SMOKE_SHA256,
        },
        "provider_observed": True,
    }
    body: dict[str, object] = {
        "schema_version": subject.PROVIDER_TERMINAL_SCHEMA,
        "manifest_identity": dict(_MANIFEST_IDENTITY),
        "manifest_sha256": _MANIFEST_SHA256,
        "launch_claim_identity": dict(_LAUNCH_CLAIM_IDENTITY),
        "launch_receipt_identity": dict(_LAUNCH_RECEIPT_IDENTITY),
        "launch_receipt_sha256": _LAUNCH_RECEIPT_SHA256,
        "execution_id": _EXECUTION_ID,
        "job_name": _JOB_NAME,
        "job_uid": _JOB_UID,
        "service_account": _SERVICE_ACCOUNT,
        "project_id": _PROJECT_ID,
        "region": _REGION,
        "task_count": subject.TASK_COUNT,
        "succeeded_count": subject.TASK_COUNT,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "terminal": True,
        "provider_observed": True,
        "job_observation": job,
        "job_observation_sha256": subject.canonical_sha256_v1(job),
    }
    return {
        **body,
        "provider_terminal_execution_sha256": subject.canonical_sha256_v1(body),
    }


def _rehash_provider_terminal(value: dict[str, object]) -> None:
    value["job_observation_sha256"] = subject.canonical_sha256_v1(
        value["job_observation"]
    )
    body = {
        key: child for key, child in value.items()
        if key != "provider_terminal_execution_sha256"
    }
    value["provider_terminal_execution_sha256"] = (
        subject.canonical_sha256_v1(body)
    )


def _rehash_task_result(value: dict[str, object]) -> None:
    body = {
        key: child for key, child in value.items()
        if key != "task_result_sha256"
    }
    value["task_result_sha256"] = subject.canonical_sha256_v1(body)


def _player_rows(panel: str, season: int, week: int, count: int = 20):
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"]
    rows = []
    for index in range(count):
        player_id = f"p{index:03d}"
        position = positions[index % len(positions)]
        rows.append({
            "panel_run_id": panel,
            "season": season,
            "week": week,
            "id": player_id,
            "gsis_id": player_id if position != "DST" else None,
            "name": player_id,
            "pos": position,
            "team": f"T{index % 6}",
            "opp": f"T{(index + 1) % 6}",
            "game_id": f"g{index % 3}",
            "salary": 3000 + index * 50,
            "proj": 10.0 + index,
            "proj_tourney": 9.5 + index,
            "own_est": 0.01 * index,
            "consensus_div": None,
            "market_points": None,
            "model_points_pre": None,
            "mean_projection": 10.0 + index,
            "proj_p10": 2.0 + index,
            "proj_p50": 10.0 + index,
            "proj_p90": 20.0 + index,
            "proj_std": 4.0,
        })
    return rows


def _snapshot(ordinal: int = 0):
    season, week = subject.SLATE_KEYS[ordinal]
    slate_id = subject.expected_slate_id_v1(ordinal)
    artifacts = []
    player_rows = {}
    candidate_rows = {}
    for index, block in enumerate(subject.BLOCK_ORDER):
        is_exact_repair = (season, week, block) == subject.REPAIR_KEY
        artifact = {
            "block": block,
            "bytes": (
                subject.REPAIR_ARTIFACT_BYTES
                if is_exact_repair else 1000 + index
            ),
            "candidate_rows": (
                subject.REPAIR_CANDIDATE_ROWS if is_exact_repair else 1
            ),
            "generation": (
                subject.REPAIR_ARTIFACT_GENERATION
                if is_exact_repair else str(10 + index)
            ),
            "panel_run_id": subject.SOURCE_PANELS[index],
            "season": season,
            "sha256": (
                subject.REPAIR_ARTIFACT_SHA256
                if is_exact_repair else str(index + 1) * 64
            ),
            "updated": "2026-08-21T00:00:00+00:00",
            "uri": (
                subject.REPAIR_WORLD_ARTIFACT_URI
                if is_exact_repair else f"gs://fixture/{block}.npz"
            ),
            "week": week,
        }
        artifacts.append(artifact)
        panel = subject.candidate_source_panel_v1(season, week, block)
        players = _player_rows(panel, season, week)
        player_rows[block] = players
        candidate_rows[block] = [
            {
                "panel_run_id": panel,
                "season": season,
                "week": week,
                "cand_ix": candidate_index,
                "tag": "lev",
                "player_ids": [row["id"] for row in players[:9]],
                "score_artifact_uri": (
                    subject.REPAIR_CANDIDATE_ARTIFACT_URI
                    if is_exact_repair else artifact["uri"]
                ),
                "score_artifact_sha256": artifact["sha256"],
            }
            for candidate_index in range(int(artifact["candidate_rows"]))
        ]
    later_slate = {
        "season": season,
        "week": week,
        "slate_id": slate_id,
        "artifact_receipts": artifacts,
    }
    return subject.build_generation_snapshot_v1(
        source_ordinal=ordinal,
        later_source_identity=_identity("a"),
        later_source_freeze_sha256="b" * 64,
        later_slate=later_slate,
        player_rows_by_block=player_rows,
        candidate_rows_by_block=candidate_rows,
        query_receipts={
            "player_query": {"sql_sha256": "c" * 64},
            "candidate_query": {"sql_sha256": "d" * 64},
            "postlock_columns_selected": [],
        },
    )


def _records(count: int = 22):
    rows = []
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"]
    for index in range(count):
        rows.append({
            "id": f"p{index:03d}",
            "pos": positions[index % len(positions)],
            "team": f"T{index % 6}",
            "opp": f"T{(index + 1) % 6}",
            "game_id": f"g{index % 3}",
            "salary": 3000 + 50 * index,
            "proj": 10.0 + index,
            "proj_tourney": 10.0 + index,
        })
    return rows


def _candidate_batch(
    *, arm: str, count: int, worlds: int, block_index: int,
) -> CandidateBatch:
    rows = _records()
    player_ids = tuple(row["id"] for row in rows)
    rng = np.random.default_rng(100 + block_index)
    draws = rng.normal(15.0, 4.0, size=(len(rows), worlds)).astype(np.float32)
    roster_ids = list(islice(combinations(player_ids, 9), count))
    lineups = tuple(
        Lineup(
            [rows[player_ids.index(player_id)] for player_id in roster],
            tag="lev",
        )
        for roster in roster_ids
    )
    totals = np.stack([
        draws[[player_ids.index(player_id) for player_id in roster]].sum(axis=0)
        for roster in roster_ids
    ])
    lev, boom = (160, 40) if arm == "control" else (40, 160)
    boom_unique = min(boom, 10)
    allocation = {
        "leverage_requested": lev,
        "leverage_unique": min(lev, count),
        "leverage_solve_attempts": lev,
        "leverage_solver_errors": 0,
        "leverage_infeasible": 0,
        "leverage_successful": lev,
        "boom_requested": boom,
        "boom_attempted": boom,
        "boom_successful": boom,
        "boom_solver_errors": 0,
        "boom_infeasible": 0,
        "boom_duplicates": boom - boom_unique,
        "boom_failures": 0,
        "boom_unique_added": boom_unique,
        "boom_unique_fill": False,
        "ce_requested": 0,
        "role_or_epistemic_requested": 12,
        "gumbel_requested": 0,
        "core_requested": 200,
        "total_requested_with_replacement_families": 212,
        "unique_candidates_after_all_families": count,
    }
    role_rosters = [
        sorted(str(value) for value in lineup.ids)
        for lineup in lineups[:subject.ROLE_DOSE]
    ]
    role_totals = np.ascontiguousarray(totals[:subject.ROLE_DOSE])
    role_injection = {
        "mode": "verbatim-registered-arm-invariant-natural-dedup-multitag-v1",
        "requested_count": subject.ROLE_DOSE,
        "represented_count": subject.ROLE_DOSE,
        "unique_added_count": subject.ROLE_DOSE,
        "already_present_count": 0,
        "requested_candidate_rosters_sha256": (
            subject.canonical_sha256_v1(role_rosters)
        ),
        "requested_candidate_totals_sha256": sha256(
            role_totals.tobytes()
        ).hexdigest(),
        "unique_added_candidate_rosters_sha256": (
            subject.canonical_sha256_v1(role_rosters)
        ),
        "collision_candidate_rosters_sha256": subject.canonical_sha256_v1([]),
        "natural_unique_deduplication": True,
        "collision_family_multitagged": True,
    }
    return CandidateBatch(
        candidates=lineups,
        candidate_totals=totals,
        player_ids=player_ids,
        player_rows=tuple(rows),
        row_draws=draws,
        all_tags={
            lineup.ids: (
                ("lev", "epi") if index < subject.ROLE_DOSE else ("lev",)
            )
            for index, lineup in enumerate(lineups)
        },
        metadata={
            "generation_allocation": allocation,
            "generation_timing_seconds": {
                "leverage": 1.0,
                "primary_boom": 2.0,
                "all_generation_through_candidate_matrix": 3.0,
            },
            "construction_preset_receipt": subject.construction_preset_v1()[
                "named_construction_preset"
            ],
            "role_injection": role_injection,
            **({
                "control_reproduction": {
                    "mode": "bq-identities-and-artifact-totals",
                    "generated_candidates": count,
                    "artifact_candidates": count,
                    "registered_candidates": count,
                    "max_total_delta": 0.0,
                }
            } if arm == "control" else {}),
        },
    )


def test_generation_snapshot_binds_repaired_r3_and_proj_tourney():
    snapshot = _snapshot(36)
    retained = subject.validate_generation_snapshot_v1(snapshot)
    r3 = retained["seeds"][3]
    assert retained["slate_id"] == "2025-w01"
    assert r3["candidate_source_panel_id"] == subject.REPAIR_PANEL
    assert r3["world_source_panel_id"] == subject.SOURCE_PANELS[3]
    assert r3["repair_substitution"] is True
    assert r3["artifact_receipt"]["uri"] == subject.REPAIR_WORLD_ARTIFACT_URI
    assert r3["candidate_rows"][0]["score_artifact_uri"] == (
        subject.REPAIR_CANDIDATE_ARTIFACT_URI
    )
    assert (
        r3["artifact_receipt"]["sha256"]
        == r3["candidate_rows"][0]["score_artifact_sha256"]
        == subject.REPAIR_ARTIFACT_SHA256
    )
    assert len(r3["candidate_rows"]) == subject.REPAIR_CANDIDATE_ROWS
    assert r3["player_rows"][0]["proj_tourney"] == 9.5
    assert retained["uses_realized_outcomes"] is False


@pytest.mark.parametrize(
    "mutation",
    ("candidate_uri", "both_uris", "shared_sha", "row_count", "panel", "slate"),
)
def test_generation_snapshot_rejects_any_neighbor_of_exact_repair_alias(
    mutation,
):
    broken = deepcopy(_snapshot(36))
    r3 = broken["seeds"][3]
    if mutation == "candidate_uri":
        r3["candidate_rows"][0]["score_artifact_uri"] = (
            subject.REPAIR_CANDIDATE_ARTIFACT_URI + ".other"
        )
    elif mutation == "both_uris":
        r3["artifact_receipt"]["uri"] = "gs://fixture/other.npz"
        for row in r3["candidate_rows"]:
            row["score_artifact_uri"] = "gs://fixture/other.npz"
    elif mutation == "shared_sha":
        r3["artifact_receipt"]["sha256"] = "f" * 64
        for row in r3["candidate_rows"]:
            row["score_artifact_sha256"] = "f" * 64
    elif mutation == "row_count":
        r3["artifact_receipt"]["candidate_rows"] -= 1
        r3["candidate_rows"].pop()
    elif mutation == "panel":
        r3["candidate_source_panel_id"] = subject.SOURCE_PANELS[3]
        r3["repair_substitution"] = False
        for row in r3["player_rows"]:
            row["panel_run_id"] = subject.SOURCE_PANELS[3]
        for row in r3["candidate_rows"]:
            row["panel_run_id"] = subject.SOURCE_PANELS[3]
    else:
        broken["week"] = 2
        broken["slate_id"] = "2025-w02"
    r3["player_rows_sha256"] = subject.canonical_sha256_v1(
        r3["player_rows"]
    )
    r3["candidate_rows_sha256"] = subject.canonical_sha256_v1(
        r3["candidate_rows"]
    )
    body = {
        key: value for key, value in broken.items()
        if key != "generation_snapshot_sha256"
    }
    broken["generation_snapshot_sha256"] = subject.canonical_sha256_v1(body)

    with pytest.raises(subject.CorpusR6BoomFirstAllocationV1Error):
        subject.validate_generation_snapshot_v1(broken)


def test_generation_snapshot_rejects_missing_objective():
    snapshot = _snapshot()
    broken = deepcopy(snapshot)
    del broken["seeds"][0]["player_rows"][0]["proj_tourney"]
    body = {k: v for k, v in broken.items() if k != "generation_snapshot_sha256"}
    broken["generation_snapshot_sha256"] = subject.canonical_sha256_v1(body)
    with pytest.raises(subject.CorpusR6BoomFirstAllocationV1Error):
        subject.validate_generation_snapshot_v1(broken)


def test_generation_snapshot_rejects_candidate_artifact_uri_mismatch():
    broken = deepcopy(_snapshot())
    seed = broken["seeds"][0]
    seed["candidate_rows"][0]["score_artifact_uri"] = (
        "gs://fixture/not-the-bound-world-artifact.npz"
    )
    seed["candidate_rows_sha256"] = subject.canonical_sha256_v1(
        seed["candidate_rows"]
    )
    body = {
        key: value for key, value in broken.items()
        if key != "generation_snapshot_sha256"
    }
    broken["generation_snapshot_sha256"] = subject.canonical_sha256_v1(body)

    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="candidate coordinate/artifact differs",
    ):
        subject.validate_generation_snapshot_v1(broken)


def test_generation_snapshot_rejects_score_bearing_query_receipt():
    ordinal = 0
    season, week = subject.SLATE_KEYS[ordinal]
    base = _snapshot(ordinal)
    seeds = base["seeds"]
    with pytest.raises(subject.CorpusR6BoomFirstAllocationV1Error):
        subject.build_generation_snapshot_v1(
            source_ordinal=ordinal,
            later_source_identity=_identity(),
            later_source_freeze_sha256="b" * 64,
            later_slate={
                "season": season, "week": week,
                "slate_id": subject.expected_slate_id_v1(ordinal),
                "artifact_receipts": [row["artifact_receipt"] for row in seeds],
            },
            player_rows_by_block={row["block"]: row["player_rows"] for row in seeds},
            candidate_rows_by_block={
                row["block"]: row["candidate_rows"] for row in seeds
            },
            query_receipts={"selected_columns": ["actual_score"]},
        )


def test_role12_injection_occurs_at_core_boundary_and_preserves_totals():
    rows = _records(24)
    player_ids = tuple(row["id"] for row in rows)
    draws = np.arange(len(rows) * 4, dtype=np.float32).reshape(len(rows), 4)
    all_rosters = list(combinations(player_ids, 9))
    generated_rosters = all_rosters[:5]
    role_rosters = all_rosters[20:32]
    generated = tuple(
        Lineup([rows[player_ids.index(pid)] for pid in roster])
        for roster in generated_rosters
    )
    generated_totals = np.stack([
        draws[[player_ids.index(pid) for pid in roster]].sum(axis=0)
        for roster in generated_rosters
    ])
    artifact_totals = np.stack([
        draws[[player_ids.index(pid) for pid in roster]].sum(axis=0)
        for roster in role_rosters
    ])
    batch = CandidateBatch(
        candidates=generated,
        candidate_totals=generated_totals,
        player_ids=player_ids,
        player_rows=tuple(rows),
        row_draws=draws,
        all_tags={lineup.ids: ("lev",) for lineup in generated},
        metadata={
            "generation_allocation": {
                "leverage_unique": 3,
                "boom_unique_added": 2,
                "role_or_epistemic_requested": 0,
                "core_requested": 200,
            }
        },
    )
    natives = pd.DataFrame([{
        "cand_ix": index, "tag": "epi", "player_ids": list(roster),
    } for index, roster in enumerate(role_rosters)])
    result = subject.inject_frozen_role12_v1(
        batch, native_rows=natives, slate=pd.DataFrame(rows),
        artifact_totals=artifact_totals,
    )
    assert len(result.candidates) == 17
    assert [lineup.tag for lineup in result.candidates[5:17]] == ["epi"] * 12
    assert result.metadata["generation_allocation"][
        "total_requested_with_replacement_families"
    ] == 212
    role = result.metadata["role_injection"]
    assert role["requested_count"] == role["represented_count"] == 12
    assert role["unique_added_count"] == 12
    assert role["already_present_count"] == 0
    assert role["natural_unique_deduplication"] is True


def test_role12_collision_is_naturally_deduped_and_multitagged():
    rows = _records(24)
    player_ids = tuple(row["id"] for row in rows)
    draws = np.arange(len(rows) * 4, dtype=np.float32).reshape(len(rows), 4)
    all_rosters = list(islice(combinations(player_ids, 9), 40))
    generated_rosters = all_rosters[:5]
    collision_roster = generated_rosters[0]
    role_rosters = [collision_roster, *all_rosters[20:31]]
    generated = tuple(
        Lineup(
            [rows[player_ids.index(pid)] for pid in roster],
            tag="lev",
        )
        for roster in generated_rosters
    )
    generated_totals = np.stack([
        draws[[player_ids.index(pid) for pid in roster]].sum(axis=0)
        for roster in generated_rosters
    ])
    artifact_totals = np.stack([
        draws[[player_ids.index(pid) for pid in roster]].sum(axis=0)
        for roster in role_rosters
    ])
    batch = CandidateBatch(
        candidates=generated,
        candidate_totals=generated_totals,
        player_ids=player_ids,
        player_rows=tuple(rows),
        row_draws=draws,
        all_tags={lineup.ids: ("lev",) for lineup in generated},
        metadata={
            "generation_allocation": {
                "leverage_unique": 3,
                "boom_unique_added": 2,
                "role_or_epistemic_requested": 0,
                "core_requested": 200,
            }
        },
    )
    natives = pd.DataFrame([{
        "cand_ix": index, "tag": "epi", "player_ids": list(roster),
    } for index, roster in enumerate(role_rosters)])

    result = subject.inject_frozen_role12_v1(
        batch,
        native_rows=natives,
        slate=pd.DataFrame(rows),
        artifact_totals=artifact_totals,
    )

    collision_key = frozenset(collision_roster)
    assert len(result.candidates) == 16
    assert len({lineup.ids for lineup in result.candidates}) == 16
    assert result.all_tags[collision_key] == ("lev", "epi")
    assert sum("epi" in tags for tags in result.all_tags.values()) == 12
    role = result.metadata["role_injection"]
    assert role["requested_count"] == role["represented_count"] == 12
    assert role["unique_added_count"] == 11
    assert role["already_present_count"] == 1
    assert role["natural_unique_deduplication"] is True
    assert role["collision_family_multitagged"] is True
    assert role["collision_candidate_rosters_sha256"] == (
        subject.canonical_sha256_v1([sorted(collision_roster)])
    )


def test_native_book_rejects_actual_construction_receipt_mismatch():
    batch = _candidate_batch(arm="control", count=90, worlds=4, block_index=0)
    batch.metadata["construction_preset_receipt"] = {"preset_id": "not-adopted"}

    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="actual construction preset receipt differs",
    ):
        subject._batch_receipt(batch, arm="control", block="R0")


def test_native_book_rejects_generation_timing_inconsistency():
    batch = _candidate_batch(arm="control", count=90, worlds=4, block_index=0)
    batch.metadata["generation_timing_seconds"][
        "all_generation_through_candidate_matrix"
    ] = 2.5

    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="generation timing order differs",
    ):
        subject._batch_receipt(batch, arm="control", block="R0")


def test_task_result_allows_unequal_unique_pools_and_selects_exact80(monkeypatch):
    monkeypatch.setattr(subject, "WORLDS_PER_BLOCK", 4)
    controls = {
        block: _candidate_batch(
            arm="control", count=90, worlds=4, block_index=index
        )
        for index, block in enumerate(subject.BLOCK_ORDER)
    }
    treatments = {
        block: _candidate_batch(
            arm="treatment", count=85, worlds=4, block_index=index
        )
        for index, block in enumerate(subject.BLOCK_ORDER)
    }
    result = subject.build_task_result_v1(
        snapshot=_snapshot(),
        books_by_arm={"control": controls, "treatment": treatments},
        runtime_identity=_runtime_identity(),
    )
    retained = subject.validate_task_result_v1(result)
    assert retained["arm_science"]["control"]["combined_candidate_count"] == 90
    assert retained["arm_science"]["treatment"]["combined_candidate_count"] == 85
    assert [len(row["selected_lineup_ids"]) for row in retained[
        "normalized_slate"
    ]["books"]] == [80, 80]
    assert retained["equal_unique_population_required"] is False


def test_task_result_rejects_deep_rehashed_normalized_surface_tamper(monkeypatch):
    monkeypatch.setattr(subject, "WORLDS_PER_BLOCK", 4)
    controls = {
        block: _candidate_batch(
            arm="control", count=90, worlds=4, block_index=index
        )
        for index, block in enumerate(subject.BLOCK_ORDER)
    }
    treatments = {
        block: _candidate_batch(
            arm="treatment", count=85, worlds=4, block_index=index
        )
        for index, block in enumerate(subject.BLOCK_ORDER)
    }
    result = subject.build_task_result_v1(
        snapshot=_snapshot(),
        books_by_arm={"control": controls, "treatment": treatments},
        runtime_identity=_runtime_identity(),
    )
    broken = deepcopy(result)
    lineup = broken["normalized_slate"]["populations"][0]["lineups"][0]
    old_lineup_id = lineup["lineup_id"]
    tampered_roster = sorted([
        *lineup["roster_player_ids"][1:], "tampered-player",
    ])
    tampered_roster_sha = subject.canonical_sha256_v1(tampered_roster)
    lineup["roster_player_ids"] = tampered_roster
    lineup["roster_sha256"] = tampered_roster_sha
    lineup["lineup_id"] = f"roster-{tampered_roster_sha}"
    for book in broken["normalized_slate"]["books"]:
        book["selected_lineup_ids"] = [
            lineup["lineup_id"] if value == old_lineup_id else value
            for value in book["selected_lineup_ids"]
        ]
    broken["normalized_slate_sha256"] = subject.canonical_sha256_v1(
        broken["normalized_slate"]
    )
    _rehash_task_result(broken)

    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="normalized exact-80 book differs",
    ):
        subject.validate_task_result_v1(broken)


def test_provider_terminal_rejects_non54_and_fixed_binding_tamper():
    valid = _provider_terminal_execution()
    assert subject.validate_provider_terminal_execution_v1(valid) == valid

    non54 = deepcopy(valid)
    non54["succeeded_count"] = subject.TASK_COUNT - 1
    _rehash_provider_terminal(non54)
    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="not exact 54/54 terminal",
    ):
        subject.validate_provider_terminal_execution_v1(non54)

    mismatched_job = deepcopy(valid)
    mismatched_job["job_observation"]["job_uid"] = "different-fixed-job-uid"
    _rehash_provider_terminal(mismatched_job)
    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="not exact 54/54 terminal",
    ):
        subject.validate_provider_terminal_execution_v1(mismatched_job)


def test_exact54_terminal_replays_every_score_free_task(monkeypatch):
    monkeypatch.setattr(subject, "WORLDS_PER_BLOCK", 4)
    controls = {
        block: _candidate_batch(
            arm="control", count=90, worlds=4, block_index=index
        )
        for index, block in enumerate(subject.BLOCK_ORDER)
    }
    treatments = {
        block: _candidate_batch(
            arm="treatment", count=85, worlds=4, block_index=index
        )
        for index, block in enumerate(subject.BLOCK_ORDER)
    }
    template = subject.build_task_result_v1(
        snapshot=_snapshot(),
        books_by_arm={"control": controls, "treatment": treatments},
        runtime_identity=_runtime_identity(),
    )
    results = []
    identities = []
    for ordinal, (season, week) in enumerate(subject.SLATE_KEYS):
        result = deepcopy(template)
        slate_id = subject.expected_slate_id_v1(ordinal)
        result.update({
            "source_ordinal": ordinal,
            "season": season,
            "week": week,
            "slate_id": slate_id,
        })
        result["normalized_slate"]["source_ordinal"] = ordinal
        result["normalized_slate"]["slate_id"] = slate_id
        result["normalized_slate_sha256"] = subject.canonical_sha256_v1(
            result["normalized_slate"]
        )
        result["runtime_identity"] = _runtime_identity(ordinal)
        _rehash_task_result(result)
        raw = subject.canonical_json_bytes_v1(result)
        results.append(result)
        identities.append({
            "uri": f"gs://fixture/tasks/{ordinal}.json",
            "generation": str(ordinal + 1),
            "sha256": subject.canonical_sha256_v1(result),
            "bytes": len(raw),
        })
    mismatched_provider = _provider_terminal_execution()
    mismatched_provider["job_uid"] = "different-fixed-job-uid"
    mismatched_provider["job_observation"]["job_uid"] = (
        "different-fixed-job-uid"
    )
    _rehash_provider_terminal(mismatched_provider)
    assert subject.validate_provider_terminal_execution_v1(
        mismatched_provider
    ) == mismatched_provider
    with pytest.raises(
        subject.CorpusR6BoomFirstAllocationV1Error,
        match="terminal task result/provider authority differs",
    ):
        subject.build_terminal_v1(
            task_results=results,
            task_result_identities=identities,
            manifest_identity=_MANIFEST_IDENTITY,
            manifest_sha256=_MANIFEST_SHA256,
            provider_terminal_execution=mismatched_provider,
        )
    terminal = subject.build_terminal_v1(
        task_results=results,
        task_result_identities=identities,
        manifest_identity=_MANIFEST_IDENTITY,
        manifest_sha256=_MANIFEST_SHA256,
        provider_terminal_execution=_provider_terminal_execution(),
    )
    retained = subject.validate_terminal_v1(terminal)
    assert retained["source_slate_count"] == 54
    assert len(retained["task_results"]) == 54
    assert len(retained["normalized_slates"]) == 54
    assert retained["selection_completed_before_first_outcome_read"] is True


def test_construction_preset_excludes_only_allocation_keys():
    preset = subject.construction_preset_v1()
    assert preset["stack_rules"] == {
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
        "qb_stack_max": None,
        "bring_back_max": None,
        "require_rb_vs_dst": False,
        "require_two_rb_same_team": False,
    }
    assert preset["named_construction_preset"]["construction_id"] == (
        "pre-rewrite-atlas-incumbent-composite-v1"
    )
    assert preset["named_construction_preset"]["schema_version"] == (
        "boom-first-incumbent-composite-construction/v1"
    )
    assert preset["minimum_games"] == 2
    assert preset["maximum_overlap"] == (
        "family-specific-see-named-construction-receipt"
    )
    assert preset["named_construction_preset"]["family_specific_overlap_law"] == {
        "leverage_repeated_solve": {
            "configured_max_overlap": 7,
            "banned_lineup_scope": "all-prior-leverage-rosters",
            "natural_roster_dedup": True,
        },
        "primary_boom_single_world_solve": {
            "configured_max_overlap": 8,
            "banned_lineup_scope": "none",
            "solver_overlap_bound_effective": False,
            "natural_roster_dedup": True,
        },
        "qb_variants_repeated_solve": {
            "configured_max_overlap": 6,
            "banned_lineup_scope": "prior-rosters-for-same-qb",
            "natural_roster_dedup": True,
        },
        "game_stack_repeated_solve": {
            "configured_max_overlap": 7,
            "banned_lineup_scope": "prior-rosters-for-same-game",
            "natural_roster_dedup": True,
        },
        "dark_game_single_solve": {
            "configured_max_overlap": 8,
            "banned_lineup_scope": "none",
            "solver_overlap_bound_effective": False,
            "natural_roster_dedup": True,
        },
        "registered_role12": {
            "solver_overlap_bound": None,
            "mode": "verbatim-natural-unique-dedup-multitag",
        },
    }
    assert preset["named_construction_preset"]["minimum_games_law"] == {
        "effective_minimum": 2,
        "source": "optimizer.lineup.MIN_GAMES-module-constant",
        "compatibility_environment_value": "2",
        "environment_value_consumed_by_pre_rewrite_optimizer": False,
    }
    assert preset["named_construction_preset"][
        "optimizer_environment_semantics"
    ] == (
        "historical-helper-compatibility-input-not-universal-effective-"
        "solver-kwargs"
    )
    assert preset["selector"] == "CBWU"
    assert preset["entry_budget"] == 80
    assert preset["allocation_environment_keys_excluded"] == [
        "GEN_TOTAL_BUDGET", "N_BOOM", "N_LEV", "PROSPECTIVE_SHADOW_ID",
    ]
    assert preset["construction_preset_sha256"] == subject.canonical_sha256_v1({
        key: value for key, value in preset.items()
        if key != "construction_preset_sha256"
    })


def test_arm_environments_change_only_the_registered_allocation():
    environments = subject.arm_environments_v1(
        {"CODE_SHA": "1" * 40, "CAND_LOG_TABLE": ""},
        code_sha="1" * 40,
    )
    control = environments["control"]
    treatment = environments["treatment"]
    changed = {
        key for key in set(control) | set(treatment)
        if control.get(key) != treatment.get(key)
    }
    assert changed == {
        "GEN_TOTAL_BUDGET", "N_BOOM", "N_LEV", "PROSPECTIVE_SHADOW_ID",
    }
    assert (control["N_LEV"], control["N_BOOM"]) == ("160", "40")
    assert (treatment["N_LEV"], treatment["N_BOOM"]) == ("40", "160")
    assert control["BOOM_UNIQUE_FILL"] == treatment["BOOM_UNIQUE_FILL"] == "0"


def test_boom_contract_needs_no_construction_preset_rewrite(monkeypatch):
    class LegacyPolicy:
        policy_id = "classic-k1-role12-boom40-poscal-cbwu-v4"
        source_panel = "legacy-panel"
        model_variant = "tail_k1"
        model_ensemble = 1
        multiseed_candidate_entry_basis = 80
        multiseed_worlds_per_block = 10_000
        multiseed_seed_pairs = ((0, 7331),)

        def engine_environment(self, base=None):
            return {
                **dict(base or {}),
                "MODEL_REGISTRY_VARIANT": "tail_k1",
                "MIN_LINEUP_SALARY": "49000",
                "PUNT_MIN": "0",
                "PUNT_MAX": "4000",
                "MAX_PER_GAME": "0",
                "GEN_TOTAL_BUDGET": "52",
                "N_BOOM": "40",
            }

        def boom_first_control_environment(self, base=None):
            return {
                **self.engine_environment(base),
                "N_LEV": "160", "BOOM_UNIQUE_FILL": "0",
                "PROSPECTIVE_SHADOW_ID": "control",
            }

        def boom_first_shadow_environment(self, base=None):
            return {
                **self.engine_environment(base),
                "GEN_TOTAL_BUDGET": "172", "N_LEV": "40",
                "N_BOOM": "160", "BOOM_UNIQUE_FILL": "0",
                "PROSPECTIVE_SHADOW_ID": "treatment",
            }

    legacy = LegacyPolicy()
    assert not hasattr(legacy, "construction_preset")
    monkeypatch.setattr(subject, "ADOPTED_CLASSIC_POLICY", legacy)
    monkeypatch.setattr(
        subject.paired, "_validated_arm_environments", lambda code_sha: {}
    )
    receipt = subject.construction_preset_v1()["named_construction_preset"]
    assert receipt["construction_id"] == (
        "pre-rewrite-atlas-incumbent-composite-v1"
    )
    environments = subject.arm_environments_v1(
        {"CODE_SHA": "1" * 40}, code_sha="1" * 40
    )
    assert environments["control"]["MIN_GAMES"] == "2"
    assert environments["treatment"]["STACK_QB_MIN"] == "2"
