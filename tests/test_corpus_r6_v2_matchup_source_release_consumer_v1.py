from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
import pytest

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source_v2
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as source_release
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_candidate_authority_v2 as source_release_v2,
)
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_authority_consumer_v2 as consumer_v2,
)
from nfl_dfs.research import corpus_r6_v2_matchup_source_release_consumer_v1 as consumer
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution_v1
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import _score_matrix_sha256


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}
TASK_ID = "slate-2023-w1"


def _identity(name: str) -> dict[str, object]:
    raw = name.encode("utf-8")
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _json_identity(body: object, name: str) -> dict[str, object]:
    raw = batch.canonical_json_bytes(body)
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "2",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _accepted_fixture() -> tuple[
    execution_v1.AcceptedV12SlateReconstruction,
    list[dict[str, object]],
]:
    candidate_count = 101
    positions = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST")
    candidates: list[dict[str, object]] = []
    catalog: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    for candidate_ordinal in range(candidate_count):
        roster: list[str] = []
        for slot, position in enumerate(positions):
            player_id = f"p-{candidate_ordinal:03d}-{slot}"
            roster.append(player_id)
            is_dst = position == "DST"
            catalog.append({
                "id": player_id,
                "pos": position,
                "team": "BBB" if is_dst else "AAA",
                "opp": "AAA" if is_dst else "BBB",
                "game_id": "AAA|BBB",
                "salary": 3000 if is_dst else 5800,
            })
            if is_dst:
                continue
            family = (
                "qb" if position == "QB"
                else "rb" if position == "RB"
                else "receiver"
            )
            edge = round(
                (candidate_ordinal * 8 + slot + 1) / (candidate_count * 8 + 1),
                12,
            )
            annotations.append({
                "gsis_id": player_id,
                "family": family,
                "position": position,
                "qb_depth1": True if position == "QB" else None,
                "matchup_component_count": 2,
                "matchup_edge_score": edge,
                "annotation_row_present": True,
            })
        block = rw.WORLD_BLOCKS[candidate_ordinal % len(rw.WORLD_BLOCKS)]
        arm_ordinal = candidate_ordinal % len(batch.PARAMETER_SET_ORDER)
        arm_id = batch.PARAMETER_SET_ORDER[arm_ordinal]
        occurrence = {
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": arm_id,
            "visit_ordinal": candidate_ordinal,
            "block_id": block,
            "objective_world_index": candidate_ordinal % 2,
        }
        candidates.append({
            "lineup_id": v12_import.canonical_lineup_id(SLATE, roster),
            "roster_player_ids": roster,
            "origin_blocks": [block],
            "source_arms": [arm_id],
            "occurrence_counts_by_block": {
                value: int(value == block) for value in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                value: [arm_id] if value == block else []
                for value in rw.WORLD_BLOCKS
            },
            "occurrence_count": 1,
            "occurrences": [occurrence],
        })
    candidates.sort(key=lambda row: str(row["lineup_id"]))
    catalog.sort(key=lambda row: str(row["id"]))
    annotations.sort(key=lambda row: str(row["gsis_id"]))
    provenance: dict[str, object] = {
        "schema_version": v12_import.PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": "a" * 64,
        "visits_per_block": 2,
        "arm_count": len(batch.PARAMETER_SET_ORDER),
        "visit_occurrence_count": candidate_count,
        "candidate_count": candidate_count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": candidates,
        "uses_realized_outcomes": False,
    }
    provenance["candidate_provenance_sha256"] = batch.canonical_sha256(
        provenance
    )
    row = np.arange(candidate_count, dtype=np.float64)[:, None]
    column = np.arange(10, dtype=np.float64)[None, :]
    scores = np.ascontiguousarray(175.0 + (row % 29) + column * 0.5)
    lineup_ids = [str(candidate["lineup_id"]) for candidate in candidates]
    matrix_binding: dict[str, object] = {
        "schema_version": v12_import.MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": batch.canonical_sha256(lineup_ids),
        "world_ids_sha256": "9" * 64,
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    matrix_binding["matrix_binding_sha256"] = batch.canonical_sha256(
        matrix_binding
    )
    reconstruction: dict[str, object] = {
        "schema_version": v12_import.RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": "1" * 64,
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix_binding,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": arm_id,
                "candidate_score_sha256": f"{ordinal + 1:x}" * 64,
                "selected_score_sha256": f"{ordinal + 8:x}" * 64,
                "unique_count": candidate_count,
                "selected_count": 80,
                "verified": True,
            }
            for ordinal, arm_id in enumerate(batch.PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    reconstruction["reconstruction_sha256"] = batch.canonical_sha256(
        reconstruction
    )
    accepted = execution_v1.AcceptedV12SlateReconstruction(
        slate_id=str(SLATE["slate_id"]),
        panel_index_identity=_identity("panel"),
        panel_index_sha256="b" * 64,
        accepted_slate_membership={
            "slate_id": SLATE["slate_id"],
            "task_ordinal": 0,
            "source_task_ordinal": 0,
        },
        task_acceptance_identity=_identity("task-acceptance"),
        carrier_identity=_identity("carrier"),
        later_source_freeze_identity=_identity("later-source"),
        world_artifact_identities={
            role: _identity(f"world-{role}")
            for role in batch.TASK_WORLD_SOURCE_ROLES
        },
        imported=SimpleNamespace(
            compatibility_receipt={"compatibility_import_sha256": "1" * 64}
        ),
        reconstructed=SimpleNamespace(
            prepared=SimpleNamespace(
                season=SLATE["season"],
                week=SLATE["week"],
                slate_id=SLATE["slate_id"],
                players=tuple(
                    SimpleNamespace(
                        player_id=row["id"],
                        position=row["pos"],
                        team=row["team"],
                        opponent=row["opp"],
                        game_id=row["game_id"],
                        salary=row["salary"],
                    )
                    for row in catalog
                ),
            ),
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=reconstruction,
        ),
    )
    return accepted, annotations


def _reopened_fixture(
    accepted: execution_v1.AcceptedV12SlateReconstruction,
    annotations: list[dict[str, object]],
) -> dict[str, object]:
    accepted_task, accepted_catalog = consumer._accepted_task_and_catalog(accepted)
    root_identity = _identity("source-release")
    export_identity = _identity("source-export")
    capture_identity = _identity("capture-receipt")
    catalog_identity = _identity("catalog")
    candidate_identity = _identity("candidates")
    producer_receipt_identity = _identity("producer-receipt")
    input_bundle_identity = _identity("input-bundle")
    operator_result_identity = _identity("operator-result")
    member = {
        "source_task_ordinal": 0,
        "task_id": accepted_task["task_id"],
        "slate": dict(SLATE),
        "catalog_identity": catalog_identity,
        "candidate_artifact_identity": candidate_identity,
        "producer_receipt_identity": producer_receipt_identity,
        "input_bundle_identity": input_bundle_identity,
        "source_export_identity": export_identity,
        "capture_receipt_identity": capture_identity,
        "operator_result_identity": operator_result_identity,
        "source_export_sha256": "c" * 64,
        "capture_receipt_sha256": "d" * 64,
        "operator_result_sha256": "a" * 64,
        "matchup_source_member_sha256": "e" * 64,
    }
    source_export = {
        "schema_version": source_release.MATCHUP_SOURCE_EXPORT_SCHEMA,
        "source_task_ordinal": 0,
        "task_id": accepted_task["task_id"],
        "slate": dict(SLATE),
        "evidence_class": consumer.REQUIRED_SOURCE_EVIDENCE_CLASS,
        "authoritative_pit": False,
        "catalog_identity": catalog_identity,
        "annotation_rows": annotations,
        "annotation_rows_sha256": batch.canonical_sha256(annotations),
        "matchup_source_export_sha256": "c" * 64,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    capture_receipt = {
        "source_task_ordinal": 0,
        "source_export_identity": export_identity,
        "matchup_capture_receipt_sha256": "d" * 64,
    }
    catalog = {
        "source_task_ordinal": 0,
        "task_id": accepted_task["task_id"],
        "slate": dict(SLATE),
        "players": accepted_catalog,
    }
    return {
        "release_identity": root_identity,
        "release": {
            "schema_version": source_release.MATCHUP_SOURCE_RELEASE_SCHEMA,
            "matchup_source_release_sha256": "f" * 64,
        },
        "member": member,
        "producer_release": {},
        "producer_release_entry": {},
        "structural_catalog": catalog,
        "candidate_artifact": {},
        "producer_receipt": {},
        "input_bundle": {},
        "source_export": source_export,
        "capture_receipt": capture_receipt,
        "operator_result": {},
        "structural_players": accepted_catalog,
        "annotation_rows": annotations,
    }


def _candidate_rooted_reopened_fixture(
    accepted: execution_v1.AcceptedV12SlateReconstruction,
    annotations: list[dict[str, object]],
) -> dict[str, object]:
    reopened = _reopened_fixture(accepted, annotations)
    provenance = dict(accepted.reconstructed.provenance)
    artifact = source_v2.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=[{
            "candidate_id": candidate["lineup_id"],
            "player_ids": candidate["roster_player_ids"],
        } for candidate in provenance["candidates"]],
    )
    artifact_identity = _json_identity(artifact, "authorized-candidates")
    root_identity = _identity("fixed-g0-candidate-authority-root")
    candidate_release_identity = _identity("accepted-candidate-release")
    root_sha = "4" * 64
    release_sha = "5" * 64
    member = reopened["member"]
    member.update({
        "schema_version": (
            source_release_v2.MATCHUP_SOURCE_MEMBER_CANDIDATE_AUTHORITY_SCHEMA
        ),
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_release_identity,
        "accepted_candidate_release_sha256": release_sha,
        "candidate_artifact_identity": artifact_identity,
        "candidate_artifact_sha256": artifact["candidate_artifact_sha256"],
        "candidate_count": artifact["candidate_count"],
        "ordered_candidate_ids_sha256": artifact[
            "ordered_candidate_ids_sha256"
        ],
        "candidate_root_full_predecessor_replay_verified": True,
        "selected_artifact_exact_reopened": True,
        "selected_artifact_matches_source_member": True,
        "base_matchup_source_member_sha256": member[
            "matchup_source_member_sha256"
        ],
        "matchup_source_member_candidate_authority_sha256": "6" * 64,
    })
    release = reopened["release"]
    release.update({
        "schema_version": (
            source_release_v2.MATCHUP_SOURCE_RELEASE_CANDIDATE_AUTHORITY_SCHEMA
        ),
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_release_identity,
        "accepted_candidate_release_sha256": release_sha,
        "candidate_root_full_predecessor_replay_verified": True,
        "base_matchup_source_release_sha256": release[
            "matchup_source_release_sha256"
        ],
        "matchup_source_release_candidate_authority_sha256": "7" * 64,
    })
    reopened["candidate_artifact"] = artifact
    reopened["candidate_authority_binding"] = {
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_release_identity,
        "accepted_candidate_release_sha256": release_sha,
        "candidate_artifact_identity": artifact_identity,
        "candidate_artifact_sha256": artifact["candidate_artifact_sha256"],
        "candidate_count": artifact["candidate_count"],
        "ordered_candidate_ids_sha256": artifact[
            "ordered_candidate_ids_sha256"
        ],
        "candidate_root_full_predecessor_replay_verified": True,
        "selected_artifact_exact_reopened": True,
        "selected_artifact_matches_source_member": True,
    }
    return reopened


def _execute_kwargs(root_identity: Mapping[str, object]) -> dict[str, object]:
    return {
        "validated_panel_index": {"fixture": True},
        "panel_index_identity": _identity("input-panel"),
        "accepted_slate_membership": {
            "slate_id": SLATE["slate_id"],
            "task_ordinal": 0,
            "source_task_ordinal": 0,
        },
        "task_acceptance_identity": _identity("input-acceptance"),
        "carrier_identity": _identity("input-carrier"),
        "matchup_source_release_identity": dict(root_identity),
        "source_task_ordinal": 0,
        "read_exact": lambda identity: b"unused",
        "admission_m": 80,
        "neutral_replicates": 1,
        "worlds_per_block": 2,
        "require_authoritative": False,
    }


def _install_exact_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    accepted: execution_v1.AcceptedV12SlateReconstruction,
    reopened: Mapping[str, object],
) -> list[tuple[dict[str, object], int]]:
    calls: list[tuple[dict[str, object], int]] = []
    monkeypatch.setattr(
        execution_v1,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: accepted,
    )

    def reopen(**kwargs: object) -> dict[str, object]:
        calls.append((dict(kwargs["release_identity"]), int(
            kwargs["source_task_ordinal"]
        )))
        return deepcopy(dict(reopened))

    monkeypatch.setattr(
        source_release, "reopen_matchup_source_release_ordinal_v1", reopen
    )
    return calls


def _install_candidate_rooted_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    accepted: execution_v1.AcceptedV12SlateReconstruction,
    reopened: Mapping[str, object],
) -> list[tuple[dict[str, object], int]]:
    calls: list[tuple[dict[str, object], int]] = []
    monkeypatch.setattr(
        execution_v1,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: accepted,
    )

    def reopen(**kwargs: object) -> dict[str, object]:
        calls.append((dict(kwargs["release_identity"]), int(
            kwargs["source_task_ordinal"]
        )))
        return deepcopy(dict(reopened))

    monkeypatch.setattr(
        source_release_v2,
        "reopen_matchup_source_release_candidate_authority_ordinal_v2",
        reopen,
    )
    return calls


def _candidate_rooted_execute_kwargs(
    root_identity: Mapping[str, object],
) -> dict[str, object]:
    return {
        **_execute_kwargs(root_identity),
        "repository_root": Path("/fixture/repository"),
        "git_head": lambda _root: "a" * 40,
        "git_blob": lambda _root, _commit, _path: b"fixture",
        "git_status": lambda _root, _paths: b"",
    }


def _replace_candidate_authority_artifact(
    reopened: dict[str, object],
    artifact: Mapping[str, object],
) -> None:
    retained = deepcopy(dict(artifact))
    artifact_identity = _json_identity(retained, "alternate-authorized-candidates")
    root_identity = _identity("alternate-fixed-g0-candidate-authority-root")
    candidate_release_identity = _identity("alternate-accepted-candidate-release")
    root_sha = "8" * 64
    release_sha = "9" * 64
    reopened["candidate_artifact"] = retained
    binding = reopened["candidate_authority_binding"]
    member = reopened["member"]
    release = reopened["release"]
    for value in (binding, member, release):
        value["candidate_authority_root_identity"] = root_identity
        value["candidate_authority_root_sha256"] = root_sha
        value["accepted_candidate_release_identity"] = candidate_release_identity
        value["accepted_candidate_release_sha256"] = release_sha
    for value in (binding, member):
        value["candidate_artifact_identity"] = artifact_identity
        value["candidate_artifact_sha256"] = retained[
            "candidate_artifact_sha256"
        ]
        value["candidate_count"] = retained["candidate_count"]
        value["ordered_candidate_ids_sha256"] = retained[
            "ordered_candidate_ids_sha256"
        ]


def test_real_small_dose_one_slate_runs_complete_seven_law_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _reopened_fixture(accepted, annotations)
    calls = _install_exact_stubs(
        monkeypatch, accepted=accepted, reopened=reopened
    )
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    result = consumer.execute_r6_v2_matchup_source_release_ordinal_v1(
        **_execute_kwargs(reopened["release_identity"])
    )

    assert calls == [(reopened["release_identity"], 0)]
    assert result["schema_version"] == consumer.RESULT_SCHEMA
    assert result["source_task_ordinal"] == 0
    assert result["uses_realized_outcomes"] is False
    assert all(result[field] is False for field in consumer._FALSE_AUTHORITY_FIELDS)
    surface = result["retrieval_surface"]
    assert surface["fold_count"] == 5
    assert surface["books_per_scope"] == 15
    assert surface["cross_fit_book_count"] == 75
    assert surface["final_fit_book_count"] == 15
    assert [scope["heldout_block"] for scope in surface["folds"]] == list(
        rw.WORLD_BLOCKS
    )
    assert all(scope["book_count"] == 15 for scope in surface["folds"])
    assert surface["final_fit"]["book_count"] == 15
    assert result["verification"][
        "full_seven_law_fold_final_surface_canonical_replay_verified"
    ] is True


def test_requested_ordinal_must_equal_accepted_panel_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _reopened_fixture(accepted, annotations)
    _install_exact_stubs(monkeypatch, accepted=accepted, reopened=reopened)
    kwargs = _execute_kwargs(reopened["release_identity"])
    kwargs["source_task_ordinal"] = 1
    with pytest.raises(
        consumer.CorpusR6V2MatchupSourceReleaseConsumerV1Error,
        match="requested source ordinal differs",
    ):
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1(**kwargs)


def test_exact_reopener_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, _ = _accepted_fixture()
    monkeypatch.setattr(
        execution_v1,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: accepted,
    )

    def unavailable(**kwargs: object) -> dict[str, object]:
        raise source_release.CorpusR6MatchupSourceReleaseV1Error(
            "selected matchup source export exact reopen failed"
        )

    monkeypatch.setattr(
        source_release, "reopen_matchup_source_release_ordinal_v1", unavailable
    )
    with pytest.raises(
        consumer.CorpusR6V2MatchupSourceReleaseConsumerV1Error,
        match="exact reopen failed",
    ):
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1(
            **_execute_kwargs(_identity("missing-source-release"))
        )


def test_exact_reopener_cannot_substitute_a_different_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _reopened_fixture(accepted, annotations)
    requested_root = deepcopy(reopened["release_identity"])
    reopened["release_identity"] = _identity("alternate-source-release")
    _install_exact_stubs(monkeypatch, accepted=accepted, reopened=reopened)
    with pytest.raises(
        consumer.CorpusR6V2MatchupSourceReleaseConsumerV1Error,
        match="different root identity",
    ):
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1(
            **_execute_kwargs(requested_root)
        )


def test_coherent_same_slate_catalog_substitution_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _reopened_fixture(accepted, annotations)
    drifted = deepcopy(reopened)
    drifted["structural_players"][0]["salary"] += 100
    drifted["structural_catalog"]["players"][0]["salary"] += 100
    _install_exact_stubs(monkeypatch, accepted=accepted, reopened=drifted)
    with pytest.raises(
        consumer.CorpusR6V2MatchupSourceReleaseConsumerV1Error,
        match="structural catalog differs",
    ):
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1(
            **_execute_kwargs(reopened["release_identity"])
        )


def test_annotation_presence_must_match_runner_edge_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _reopened_fixture(accepted, annotations)
    poisoned = deepcopy(reopened)
    poisoned["annotation_rows"][0]["annotation_row_present"] = False
    poisoned["source_export"]["annotation_rows"][0][
        "annotation_row_present"
    ] = False
    poisoned["source_export"]["annotation_rows_sha256"] = batch.canonical_sha256(
        poisoned["source_export"]["annotation_rows"]
    )
    _install_exact_stubs(monkeypatch, accepted=accepted, reopened=poisoned)
    with pytest.raises(
        consumer.CorpusR6V2MatchupSourceReleaseConsumerV1Error,
        match="runner semantics differ",
    ):
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1(
            **_execute_kwargs(reopened["release_identity"])
        )


def test_public_consumer_has_no_caller_selected_member_or_annotation_inputs() -> None:
    parameters = set(inspect.signature(
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1
    ).parameters)
    assert not parameters & {
        "source_member",
        "source_export_identity",
        "capture_receipt_identity",
        "catalog_identity",
        "annotation_rows",
        "matchup_summary",
        "admitted_lineup_ids",
        "outcome_source_identity",
        "outcome_reader",
        "realized_reader",
        "actual_scores",
        "realized_scores",
        "score_reader",
        "score_lineups",
    }


def test_nested_realized_or_outcome_carrier_is_rejected_before_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _reopened_fixture(accepted, annotations)
    poisoned = deepcopy(reopened)
    poisoned["source_export"]["nested_evidence"] = {
        "realized_score": 240.0,
    }
    _install_exact_stubs(monkeypatch, accepted=accepted, reopened=poisoned)

    def forbidden_surface(**kwargs: object) -> dict[str, object]:
        raise AssertionError("runner must not receive outcome-carrier source")

    monkeypatch.setattr(consumer, "_build_retrieval_surface", forbidden_surface)
    with pytest.raises(
        consumer.CorpusR6V2MatchupSourceReleaseConsumerV1Error,
        match="forbidden outcome field 'realized_score'",
    ):
        consumer.execute_r6_v2_matchup_source_release_ordinal_v1(
            **_execute_kwargs(reopened["release_identity"])
        )


def test_candidate_rooted_v2_runs_full_one_slate_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _candidate_rooted_reopened_fixture(accepted, annotations)
    calls = _install_candidate_rooted_stubs(
        monkeypatch, accepted=accepted, reopened=reopened
    )
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    result = consumer_v2.execute_r6_v2_matchup_candidate_authority_ordinal_v2(
        **_candidate_rooted_execute_kwargs(reopened["release_identity"])
    )

    assert calls == [(reopened["release_identity"], 0)]
    assert result["schema_version"] == consumer_v2.RESULT_SCHEMA
    assert result["uses_realized_outcomes"] is False
    assert all(result[field] is False for field in consumer._FALSE_AUTHORITY_FIELDS)
    projection = result["matchup_source_projection"]
    candidate_binding = projection["candidate_authority_binding"]
    union_binding = projection["candidate_population_scored_union_binding"]
    assert candidate_binding[
        "candidate_root_full_predecessor_replay_verified"
    ] is True
    assert union_binding["candidate_ids_exact_order_verified"] is True
    assert union_binding["candidate_rosters_exact_order_verified"] is True
    assert result["retrieval_surface"]["cross_fit_book_count"] == 75
    assert result["retrieval_surface"]["final_fit_book_count"] == 15
    assert result["verification"][
        "authorized_candidate_order_matches_scored_matrix_verified"
    ] is True


def test_candidate_rooted_v2_rejects_coherent_alternate_authority_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _candidate_rooted_reopened_fixture(accepted, annotations)
    original = reopened["candidate_artifact"]
    alternate = source_v2.build_accepted_candidate_artifact_v1(
        source_task_ordinal=0,
        rows=[{
            "candidate_id": row["candidate_id"],
            "player_ids": row["player_ids"],
        } for row in reversed(original["rows"])],
    )
    _replace_candidate_authority_artifact(reopened, alternate)
    _install_candidate_rooted_stubs(
        monkeypatch, accepted=accepted, reopened=reopened
    )

    def forbidden_surface(**kwargs: object) -> dict[str, object]:
        raise AssertionError("retrieval runner must not see an alternate union")

    monkeypatch.setattr(consumer, "_build_retrieval_surface", forbidden_surface)
    with pytest.raises(
        consumer_v2.CorpusR6V2MatchupCandidateAuthorityConsumerV2Error,
        match=r"authorized candidate row\[0\] differs",
    ):
        consumer_v2.execute_r6_v2_matchup_candidate_authority_ordinal_v2(
            **_candidate_rooted_execute_kwargs(reopened["release_identity"])
        )


def test_candidate_rooted_v2_rejects_binding_substitution_before_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _candidate_rooted_reopened_fixture(accepted, annotations)
    reopened["candidate_authority_binding"]["candidate_artifact_sha256"] = (
        "0" * 64
    )
    _install_candidate_rooted_stubs(
        monkeypatch, accepted=accepted, reopened=reopened
    )

    def forbidden_surface(**kwargs: object) -> dict[str, object]:
        raise AssertionError("retrieval runner must not see a substituted binding")

    monkeypatch.setattr(consumer, "_build_retrieval_surface", forbidden_surface)
    with pytest.raises(
        consumer_v2.CorpusR6V2MatchupCandidateAuthorityConsumerV2Error,
        match="candidate authority differs",
    ):
        consumer_v2.execute_r6_v2_matchup_candidate_authority_ordinal_v2(
            **_candidate_rooted_execute_kwargs(reopened["release_identity"])
        )


def test_candidate_rooted_v2_rejects_nested_outcome_carrier_before_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, annotations = _accepted_fixture()
    reopened = _candidate_rooted_reopened_fixture(accepted, annotations)
    reopened["candidate_authority_binding"]["nested"] = {
        "realized_reader": "forbidden",
    }
    _install_candidate_rooted_stubs(
        monkeypatch, accepted=accepted, reopened=reopened
    )

    def forbidden_surface(**kwargs: object) -> dict[str, object]:
        raise AssertionError("retrieval runner must not see outcomes")

    monkeypatch.setattr(consumer, "_build_retrieval_surface", forbidden_surface)
    with pytest.raises(
        consumer_v2.CorpusR6V2MatchupCandidateAuthorityConsumerV2Error,
        match="forbidden outcome field 'realized_reader'",
    ):
        consumer_v2.execute_r6_v2_matchup_candidate_authority_ordinal_v2(
            **_candidate_rooted_execute_kwargs(reopened["release_identity"])
        )


def test_candidate_rooted_v2_public_api_has_no_candidate_or_outcome_injection() -> None:
    parameters = set(inspect.signature(
        consumer_v2.execute_r6_v2_matchup_candidate_authority_ordinal_v2
    ).parameters)
    assert "matchup_source_release_identity" in parameters
    assert "source_task_ordinal" in parameters
    assert not parameters & {
        "candidate_authority_root_identity",
        "accepted_candidate_release",
        "accepted_candidate_release_identity",
        "candidate_artifact",
        "candidate_artifact_identity",
        "annotation_rows",
        "matchup_summary",
        "admitted_lineup_ids",
        "outcome_reader",
        "realized_reader",
        "actual_scores",
        "realized_scores",
        "score_reader",
    }


def test_candidate_rooted_v2_reopener_failure_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    accepted, _ = _accepted_fixture()
    monkeypatch.setattr(
        execution_v1,
        "reconstruct_one_accepted_v12_slate",
        lambda **kwargs: accepted,
    )

    def unavailable(**kwargs: object) -> dict[str, object]:
        raise source_release_v2.CorpusR6MatchupSourceReleaseCandidateAuthorityV2Error(
            "candidate authority root exact reopen failed"
        )

    monkeypatch.setattr(
        source_release_v2,
        "reopen_matchup_source_release_candidate_authority_ordinal_v2",
        unavailable,
    )
    with pytest.raises(
        consumer_v2.CorpusR6V2MatchupCandidateAuthorityConsumerV2Error,
        match="candidate authority root exact reopen failed",
    ):
        consumer_v2.execute_r6_v2_matchup_candidate_authority_ordinal_v2(
            **_candidate_rooted_execute_kwargs(_identity("missing-v2-root"))
        )
