from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.config import settings
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books
from nfl_dfs.inference.prelock_candidate_lineage_v1 import (
    canonical_json_bytes,
    canonical_sha256,
)
from nfl_dfs.inference.prelock_input_boundary_v1 import (
    ALLOWED_BIGQUERY_TABLE_URIS,
    BIGQUERY_BOUNDARY_SCHEMA,
    build_prelock_input_read_manifest_v1,
)
from nfl_dfs.inference.prelock_lineage_runtime_v2 import (
    EFFECTIVE_POLICY_SCHEMA,
    EFFECTIVE_POLICY_SOURCE_SET_ID,
    EXECUTION_RECEIPT_SCHEMA,
    LINEAGE_ADAPTER_MANIFEST_SCHEMA,
    SEED_LABELS,
    PrelockLineageRuntimeV2Error,
    build_capture_authority_v2,
    build_salary_snapshot_v2,
    build_sidecar_from_capture_v2,
    canonical_selector_matrix_bytes,
    selected_roster_order,
    validate_capture_authority_v2,
)
from nfl_dfs.inference.prelock_lineage_settlement_v2 import (
    SOURCE_ROLES,
    PrelockLineageSettlementV2Error,
    build_candidate_score_document_v2,
    build_descriptive_outcome_binding_v2,
    build_first_loss_settlement_v2,
    build_individual_rescue_v2,
    build_opportunity_document_v2,
)
from nfl_dfs.inference.prelock_model_artifact_authority_v1 import (
    MODEL_ARTIFACT_MANIFEST_SCHEMA,
)
from nfl_dfs.models.components import COMPONENT_NAMES
from nfl_dfs.optimizer.lineup import Lineup

MODEL_WEEK = "2026-W36"


def _player(player_id: int) -> dict[str, object]:
    return {
        "id": player_id,
        "name": f"P{player_id}",
        "pos": "WR",
        "team": f"T{player_id % 4}",
        "opp": f"T{(player_id + 1) % 4}",
        "game_id": f"G{player_id % 2}",
        "salary": 5_000,
        "proj": 20.0,
    }


def _roster_ids(player_ids: tuple[int, ...], start: int) -> list[int]:
    return [player_ids[(start + offset) % len(player_ids)] for offset in range(9)]


def _five_books() -> dict[str, CandidateBatch]:
    player_ids = tuple(range(30))
    player_rows = tuple(_player(player_id) for player_id in player_ids)
    books: dict[str, CandidateBatch] = {}
    for seed_index, label in enumerate(SEED_LABELS):
        rng = np.random.default_rng(700 + seed_index)
        draws = rng.normal(20, 6, size=(len(player_ids), 11)).astype(np.float32)
        starts = [seed_index * 2 + offset for offset in range(4)]
        rosters = [_roster_ids(player_ids, start) for start in starts]
        candidates = tuple(
            Lineup([player_rows[player_id] for player_id in roster], tag="boom")
            for roster in rosters
        )
        totals = np.stack(
            [draws[list(lineup.ids)].sum(axis=0) for lineup in candidates]
        ).astype(np.float32)
        ledger = SolveExposureLedger(source_label=label)
        for ordinal, roster in enumerate(rosters):
            ledger.record(
                family="boom",
                requested_ordinal=ordinal,
                world_id=ordinal,
                status="new",
                roster_ids=roster,
            )
        # One generated roster is intentionally excluded from the native
        # batch, proving native-union -> pool-cap loss is represented.
        ledger.record(
            family="boom",
            requested_ordinal=len(rosters),
            world_id=len(rosters),
            status="new",
            roster_ids=_roster_ids(player_ids, 20 + seed_index),
        )
        books[label] = CandidateBatch(
            candidates=candidates,
            candidate_totals=totals,
            player_ids=player_ids,
            player_rows=player_rows,
            row_draws=draws,
            all_tags={lineup.ids: ("boom",) for lineup in candidates},
            metadata={
                "generation_exposure_ledger": ledger.finalize(
                    expected_requests_by_family={"boom": len(rosters) + 1}
                ),
                "model_version": f"pooled/components__tail_k1/{MODEL_WEEK}",
                "role_model_version": (f"pooled/components__tail_k1_role/{MODEL_WEEK}"),
                "candidate_input_receipt": {
                    "sha256": "1" * 64,
                    "rows": len(player_ids),
                    "columns": ["id"],
                },
                "role_candidate_input_receipt": {
                    "sha256": "2" * 64,
                    "rows": len(player_ids),
                    "columns": ["id"],
                },
            },
        )
    return books


def _salary_snapshot() -> dict[str, object]:
    rows = pd.DataFrame(
        [
            {
                "pulled_at": pd.Timestamp("2026-09-13T12:00:00Z"),
                "draft_group_id": 123,
                "dk_player_id": player_id,
                "dk_draftable_id": 10_000 + player_id,
                "display_name": f"P{player_id}",
                "team_abbr": f"T{player_id % 4}",
                "position": "WR",
                "salary": 5_000,
                "game_start": pd.Timestamp("2026-09-13T17:00:00Z"),
                "status": "None",
            }
            for player_id in range(30)
        ]
    )
    return build_salary_snapshot_v2(
        rows,
        draft_group_id=123,
        source_table_uri="bq://nfl-dfs-prod.nfl_raw.dk_salaries",
    )


def test_salary_pull_at_exact_lock_is_not_prelock() -> None:
    rows = pd.DataFrame(
        [
            {
                "pulled_at": pd.Timestamp("2026-09-13T17:00:00Z"),
                "draft_group_id": 123,
                "dk_player_id": 1,
                "dk_draftable_id": 10_001,
                "display_name": "P1",
                "team_abbr": "T1",
                "position": "WR",
                "salary": 5_000,
                "game_start": pd.Timestamp("2026-09-13T17:00:00Z"),
                "status": "None",
            }
        ]
    )

    with pytest.raises(PrelockLineageRuntimeV2Error, match="demonstrably pre-lock"):
        build_salary_snapshot_v2(
            rows,
            draft_group_id=123,
            source_table_uri="bq://nfl-dfs-prod.nfl_raw.dk_salaries",
        )


def _environment() -> dict[str, str]:
    return {
        "MULTISEED_PORTFOLIO": "CBWU",
        "SELECT_OBJ": "",
        "SELECT_LSE": "0",
        "SELECT_LADDER": "",
        "M4_QBLOCK": "0",
        "MAX_QBS": "0",
        "PEAK_SLICE": "0",
        "PROSPECTIVE_GENERATION_EXPOSURE": "1",
        "MULTISEED_CANDIDATE_ENTRY_BASIS": "2",
    }


def _model_artifacts() -> dict[str, object]:
    model_sets = []
    for purpose, variant in (
        ("candidate-projection", "tail_k1"),
        ("role-belief", "tail_k1_role"),
    ):
        components = []
        for component in COMPONENT_NAMES:
            label = f"comp_{component}__{variant}"
            artifacts = []
            for ordinal, name in enumerate(("meta.json", "model.txt")):
                payload = f"{variant}/{component}/{name}".encode()
                artifacts.append(
                    {
                        "name": name,
                        "identity": {
                            "uri": (
                                f"gs://{settings.gcs_bucket}/"
                                f"{settings.model_registry_prefix}/pooled/"
                                f"{label}/{MODEL_WEEK}/{name}"
                            ),
                            "generation": str(2_000 + ordinal),
                            "sha256": sha256(payload).hexdigest(),
                            "bytes": len(payload),
                            "time_created_utc": "2026-09-13T15:00:00.500000Z",
                        },
                    }
                )
            components.append(
                {
                    "component": component,
                    "registry_label": label,
                    "artifacts": artifacts,
                }
            )
        model_sets.append(
            {
                "purpose": purpose,
                "variant": variant,
                "iso_week": MODEL_WEEK,
                "model_version": f"pooled/components__{variant}/{MODEL_WEEK}",
                "components": components,
            }
        )
    body: dict[str, object] = {
        "schema_version": MODEL_ARTIFACT_MANIFEST_SCHEMA,
        "bucket": settings.gcs_bucket,
        "registry_prefix": settings.model_registry_prefix,
        "scope": "pooled",
        "expected_member_count": 1,
        "model_sets": model_sets,
        "frozen_before_generation": True,
        "provider_generations_required_unchanged_after_generation": True,
        "read_only": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["manifest_sha256"] = canonical_sha256(body)
    return body


def _authorities() -> tuple[dict[str, object], ...]:
    environment = _environment()
    base_environment = dict(environment)
    assert base_environment.pop("PROSPECTIVE_GENERATION_EXPOSURE") == "1"
    source_identities = [
        {
            "path": "src/nfl_dfs/optimizer/lineup.py",
            "role": "legality_and_soft_rule_enforcement",
            "sha256": "1" * 64,
            "bytes": 10,
        }
    ]
    policy: dict[str, object] = {
        "classified_input_projection": [],
        "classified_input_projection_sha256": "2" * 64,
        "complete_for_scope": True,
        "effective_policy": {
            "engine_environment": base_environment,
            "engine_environment_sha256": canonical_sha256(base_environment),
            "policy_id": "fixture-policy",
            "public_identity_sha256": "3" * 64,
        },
        "forbidden_ambient_process_keys": [],
        "legal_feasibility_parameters": {},
        "rule_count": 0,
        "rule_universe_sha256": "4" * 64,
        "rules": [],
        "schema": EFFECTIVE_POLICY_SCHEMA,
        "scope": {},
        "source_identities": source_identities,
        "source_set_id": EFFECTIVE_POLICY_SOURCE_SET_ID,
        "source_set_sha256": sha256(
            canonical_json_bytes(source_identities) + b"\n"
        ).hexdigest(),
    }
    policy["inventory_sha256"] = sha256(
        canonical_json_bytes(policy) + b"\n"
    ).hexdigest()
    adapter: dict[str, object] = {
        "schema_version": LINEAGE_ADAPTER_MANIFEST_SCHEMA,
        "files": [
            {
                "path": "src/nfl_dfs/inference/prelock_lineage_runtime_v2.py",
                "sha256": "5" * 64,
                "bytes": 10,
            }
        ],
        "effective_policy_inventory_required": "v6",
        "transitive_scoring_surface_claimed_here": False,
    }
    adapter["manifest_sha256"] = canonical_sha256(adapter)
    execution: dict[str, object] = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "image_digest": "sha256:" + "6" * 64,
        "source_commit": "7" * 40,
        "image_reference_is_digest": True,
        "provider_execution_identity_verified": False,
        "provider_resource_envelope_verified": False,
        "execution_authority": False,
        "solver": {
            "name": "cbc",
            "pulp_version": "3.0.0",
            "binary_sha256": "8" * 64,
            "binary_bytes": 10,
        },
        "compute_envelope": {
            "architecture": "x86_64",
            "operating_system": "Linux",
            "python_version": "3.14",
            "numpy_version": "2.0",
            "cpu_count": 1,
            "memory_bytes": 1,
        },
    }
    execution["receipt_sha256"] = canonical_sha256(execution)
    models = _model_artifacts()
    method = canonical_sha256(
        {
            "effective_policy_inventory_sha256": policy["inventory_sha256"],
            "lineage_adapter_manifest_sha256": adapter["manifest_sha256"],
            "execution_receipt_sha256": execution["receipt_sha256"],
            "model_artifact_manifest_sha256": models["manifest_sha256"],
        }
    )
    return policy, adapter, execution, models, method


def _input_read_manifest() -> dict[str, object]:
    boundary = {
        "schema_version": BIGQUERY_BOUNDARY_SCHEMA,
        "allowed_table_uris": sorted(ALLOWED_BIGQUERY_TABLE_URIS),
        "select_or_with_only": True,
        "bigquery_write_methods_exposed": False,
        "scoped_query_only_client": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    return build_prelock_input_read_manifest_v1(
        salary_boundary=boundary,
        generation_boundary=boundary,
    )


def _capture() -> tuple[dict[str, object], CandidateBatch]:
    books = _five_books()
    combined = combine_cbwu_books(
        books,
        SEED_LABELS,
        expected_worlds_per_book=11,
    )
    policy, adapter, execution, models, method = _authorities()
    capture = build_capture_authority_v2(
        run={
            "run_id": "week1-lineage-001",
            "run_type": "prospective-lineage-shadow-v2",
            "season": 2026,
            "week": 1,
            "slate_id": "dk-123",
            "draft_group_id": 123,
            "contest_id": None,
            "slate_lock_at_utc": "2026-09-13T17:00:00Z",
            "capture_started_at_utc": "2026-09-13T16:00:00Z",
            "policy_id": "policy-v1",
            "code_sha256": method,
        },
        native_batches=books,
        effective_batch=combined,
        salary_snapshot=_salary_snapshot(),
        policy_environment=_environment(),
        effective_policy_inventory=policy,
        lineage_adapter_manifest=adapter,
        execution_receipt=execution,
        model_artifact_manifest=models,
        model_artifacts_exact_reopened_after_generation=True,
        input_read_boundary=_input_read_manifest(),
        source_binding_mode="git-global-clean-checkout",
        selector_id="greedy-tail-coverage",
        retrieval_preset_id="incumbent-cbwu-coverage-194-k80",
        tail_line=194.0,
        entry_budget=2,
    )
    return capture, combined


def test_real_r0_r4_union_cbwu_typed_selector_seals_v1_sidecar() -> None:
    capture, combined = _capture()
    payload = canonical_json_bytes(capture)
    identity = {
        "uri": "gs://nfl-dfs-prod-raw/prelock-lineage-v1/run/input.json",
        "generation": "101",
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    sidecar = build_sidecar_from_capture_v2(
        capture=capture,
        capture_identity=identity,
        frozen_at_utc="2026-09-13T16:00:01Z",
    )

    assert sidecar["schema_version"] == "prelock-candidate-lineage-sidecar/v1"
    assert sidecar["counts"]["effective_candidate_count"] == len(combined.candidates)
    assert sidecar["counts"]["raw_selected_count"] == 2
    assert {row["stage_id"] for row in sidecar["admission_decisions"]} == {
        "native-union",
        "effective-candidates",
    }
    stage_zero = [
        row for row in sidecar["admission_decisions"] if row["stage_ordinal"] == 0
    ]
    assert any(row["reason"] == "DROPPED_POOL_CAP" for row in stage_zero)
    assert any(
        row["disposition"] == "DUPLICATE_CROSS_SEED"
        for row in sidecar["dedupe_decisions"]
    )
    assert selected_roster_order(capture) == [
        sorted(str(value) for value in combined.candidates[index].ids)
        for index in capture["effective_candidates"]["final_selected_indices"]
    ]
    assert canonical_selector_matrix_bytes(
        capture["effective_candidates"]["selector_matrix_archive"]
    ) == np.ascontiguousarray(combined.candidate_totals).tobytes(order="C")


def test_feature_snapshot_is_allowlist_not_an_outcome_denylist() -> None:
    books = _five_books()
    bad_rows = [dict(row) for row in books["R0"].player_rows]
    for row in bad_rows:
        row["actual_rank"] = 1
    bad = replace(books["R0"], player_rows=tuple(bad_rows))
    books["R0"] = bad
    combined = combine_cbwu_books(books, SEED_LABELS, expected_worlds_per_book=11)
    policy, adapter, execution, models, method = _authorities()

    with pytest.raises(PrelockLineageRuntimeV2Error, match="outside the allowlist"):
        build_capture_authority_v2(
            run={
                "run_id": "week1-lineage-002",
                "run_type": "prospective-lineage-shadow-v2",
                "season": 2026,
                "week": 1,
                "slate_id": "dk-123",
                "draft_group_id": 123,
                "contest_id": None,
                "slate_lock_at_utc": "2026-09-13T17:00:00Z",
                "capture_started_at_utc": "2026-09-13T16:00:00Z",
                "policy_id": "policy-v1",
                "code_sha256": method,
            },
            native_batches=books,
            effective_batch=combined,
            salary_snapshot=_salary_snapshot(),
            policy_environment=_environment(),
            effective_policy_inventory=policy,
            lineage_adapter_manifest=adapter,
            execution_receipt=execution,
            model_artifact_manifest=models,
            model_artifacts_exact_reopened_after_generation=True,
            input_read_boundary=_input_read_manifest(),
            source_binding_mode="git-global-clean-checkout",
            selector_id="greedy-tail-coverage",
            retrieval_preset_id="incumbent-cbwu-coverage-194-k80",
            tail_line=194.0,
            entry_budget=2,
        )


def test_capture_reopen_rejects_matrix_tamper() -> None:
    capture, _ = _capture()
    capture["effective_candidates"]["selector_matrix_archive"]["archive_base64"] = (
        "AAAA"
    )
    capture["capture_sha256"] = sha256(b"wrong").hexdigest()

    with pytest.raises(PrelockLineageRuntimeV2Error):
        validate_capture_authority_v2(capture)


def _sidecar(capture: dict[str, object]) -> dict[str, object]:
    payload = canonical_json_bytes(capture)
    return build_sidecar_from_capture_v2(
        capture=capture,
        capture_identity={
            "uri": "gs://nfl-dfs-prod-raw/prelock-lineage-v1/input.json",
            "generation": "101",
            "sha256": sha256(payload).hexdigest(),
            "bytes": len(payload),
        },
        frozen_at_utc="2026-09-13T16:00:01Z",
    )


def _provider_identity(
    payload: bytes,
    generation: int,
    *,
    created_at_utc: str = "2026-09-13T18:00:00.500000Z",
) -> dict[str, object]:
    return {
        "uri": f"gs://nfl-dfs-prod-raw/postlock/source-{generation}",
        "generation": str(generation),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "time_created_utc": created_at_utc,
    }


def _outcome_binding(
    sidecar: dict[str, object],
    score_rows: list[dict[str, object]],
    *,
    created_at_utc: str = "2026-09-13T18:00:00.500000Z",
) -> dict[str, object]:
    candidate_document = build_candidate_score_document_v2(
        slate_id="dk-123", rows=score_rows
    )
    roster_by_id = {row["roster_id"]: row for row in sidecar["roster_identities"]}
    strategy = sorted(
        sidecar["strategy_decisions"],
        key=lambda row: int(row["candidate_ordinal"]),
    )
    selected = next(row for row in strategy if row["decision"] == "SELECTED")
    omitted = next(row for row in strategy if row["decision"] == "NOT_SELECTED")
    rejected = next(
        row
        for row in sidecar["admission_decisions"]
        if row["disposition"] == "REJECTED" and row["stage_id"] == "native-union"
    )
    opportunity_document = build_opportunity_document_v2(
        slate_id="dk-123",
        rows=[
            {
                "opportunity_id": "final",
                "internal_player_ids": roster_by_id[selected["roster_id"]][
                    "internal_player_ids"
                ],
                "realized_score_milli": 180_000,
            },
            {
                "opportunity_id": "not-selected",
                "internal_player_ids": roster_by_id[omitted["roster_id"]][
                    "internal_player_ids"
                ],
                "realized_score_milli": 210_000,
            },
            {
                "opportunity_id": "not-admitted",
                "internal_player_ids": roster_by_id[rejected["roster_id"]][
                    "internal_player_ids"
                ],
                "realized_score_milli": 220_000,
            },
            {
                "opportunity_id": "not-produced",
                "internal_player_ids": [f"unknown-{index}" for index in range(9)],
                "realized_score_milli": 230_000,
            },
        ],
    )
    payloads = {
        "candidate-scores": canonical_json_bytes(candidate_document),
        "opportunity-rosters": canonical_json_bytes(opportunity_document),
        "complete-standings": b"complete standings bytes",
        "entries-field-bridge": b"entry field bridge bytes",
        "standings-access-receipt": b"access receipt bytes",
        "winner-score": b"winner score source bytes",
        "winner-registry-v2": b"winner registry v2 bytes",
    }
    assert set(payloads) == set(SOURCE_ROLES)
    identities = {
        role: _provider_identity(
            payload,
            200 + index,
            created_at_utc=created_at_utc,
        )
        for index, (role, payload) in enumerate(payloads.items())
    }
    return build_descriptive_outcome_binding_v2(
        season=2026,
        week=1,
        slate_id="dk-123",
        lock_at_utc="2026-09-13T17:00:00+00:00",
        settled_at_utc="2026-09-13T20:00:00+00:00",
        candidate_score_document=candidate_document,
        opportunity_document=opportunity_document,
        winner_score_milli=200_000,
        source_payloads=payloads,
        source_identities=identities,
    )


def test_outcome_source_at_exact_lock_is_not_postlock() -> None:
    capture, _ = _capture()
    sidecar = _sidecar(capture)
    rows = [
        {
            "candidate_instance_id": row["candidate_instance_id"],
            "roster_id": row["roster_id"],
            "realized_score_milli": 180_000,
        }
        for row in sidecar["strategy_decisions"]
    ]

    with pytest.raises(
        PrelockLineageSettlementV2Error,
        match="outside post-lock settlement",
    ):
        _outcome_binding(
            sidecar,
            rows,
            created_at_utc="2026-09-13T17:00:00Z",
        )


def test_keyed_rescue_is_permutation_invariant_and_source_bound() -> None:
    capture, _ = _capture()
    sidecar = _sidecar(capture)
    strategy = sorted(
        sidecar["strategy_decisions"],
        key=lambda row: int(row["candidate_ordinal"]),
    )
    scores = [
        {
            "candidate_instance_id": row["candidate_instance_id"],
            "roster_id": row["roster_id"],
            "realized_score_milli": 180_000 + 10_000 * ordinal,
        }
        for ordinal, row in enumerate(strategy)
    ]
    binding = _outcome_binding(sidecar, scores)
    matrix = canonical_selector_matrix_bytes(
        capture["effective_candidates"]["selector_matrix_archive"]
    )
    rescue = build_individual_rescue_v2(
        capture=capture,
        sidecar=sidecar,
        selector_matrix_bytes=matrix,
        outcome_binding=binding,
    )
    permuted_binding = _outcome_binding(sidecar, list(reversed(scores)))
    permuted = build_individual_rescue_v2(
        capture=capture,
        sidecar=sidecar,
        selector_matrix_bytes=matrix,
        outcome_binding=permuted_binding,
    )

    assert permuted == rescue
    assert rescue["candidate_scores_joined_by_position"] is False
    assert rescue["candidate_scores_complete_one_to_one_join"] is True
    assert rescue["sum_is_jointly_achievable"] is False
    assert rescue["settlement_authority"] is False
    assert binding["accepted_winner_registry_v2_verified"] is False
    assert set(binding["source_identities"]) == set(SOURCE_ROLES)


def test_keyed_rescue_rejects_capture_and_sidecar_from_different_roots() -> None:
    capture, _ = _capture()
    other_capture = deepcopy(capture)
    other_capture["run"]["run_id"] = "week1-lineage-other-root"
    other_capture.pop("capture_sha256")
    other_capture["capture_sha256"] = canonical_sha256(other_capture)
    sidecar = _sidecar(other_capture)
    rows = [
        {
            "candidate_instance_id": row["candidate_instance_id"],
            "roster_id": row["roster_id"],
            "realized_score_milli": 180_000,
        }
        for row in sidecar["strategy_decisions"]
    ]
    matrix = canonical_selector_matrix_bytes(
        capture["effective_candidates"]["selector_matrix_archive"]
    )

    with pytest.raises(
        PrelockLineageSettlementV2Error,
        match="cannot reproduce|do not share one exact pre-lock root",
    ):
        build_individual_rescue_v2(
            capture=capture,
            sidecar=sidecar,
            selector_matrix_bytes=matrix,
            outcome_binding=_outcome_binding(sidecar, rows),
        )


def test_keyed_rescue_rejects_wrong_selector_matrix_before_calculation() -> None:
    capture, _ = _capture()
    sidecar = _sidecar(capture)
    rows = [
        {
            "candidate_instance_id": row["candidate_instance_id"],
            "roster_id": row["roster_id"],
            "realized_score_milli": 180_000,
        }
        for row in sidecar["strategy_decisions"]
    ]
    matrix = bytearray(
        canonical_selector_matrix_bytes(
            capture["effective_candidates"]["selector_matrix_archive"]
        )
    )
    matrix[0] ^= 1

    with pytest.raises(
        PrelockLineageSettlementV2Error,
        match="selector matrix differs from frozen bytes",
    ):
        build_individual_rescue_v2(
            capture=capture,
            sidecar=sidecar,
            selector_matrix_bytes=bytes(matrix),
            outcome_binding=_outcome_binding(sidecar, rows),
        )


def test_keyed_rescue_rejects_missing_extra_and_duplicate_rows() -> None:
    capture, _ = _capture()
    sidecar = _sidecar(capture)
    strategy = sidecar["strategy_decisions"]
    rows = [
        {
            "candidate_instance_id": row["candidate_instance_id"],
            "roster_id": row["roster_id"],
            "realized_score_milli": 180_000,
        }
        for row in strategy
    ]
    matrix = canonical_selector_matrix_bytes(
        capture["effective_candidates"]["selector_matrix_archive"]
    )
    missing = _outcome_binding(sidecar, rows[:-1])
    with pytest.raises(PrelockLineageSettlementV2Error, match="not one-to-one"):
        build_individual_rescue_v2(
            capture=capture,
            sidecar=sidecar,
            selector_matrix_bytes=matrix,
            outcome_binding=missing,
        )
    with pytest.raises(PrelockLineageSettlementV2Error, match="duplicate join keys"):
        build_candidate_score_document_v2(slate_id="dk-123", rows=[*rows, rows[0]])


def test_first_loss_uses_source_bound_opportunity_universe() -> None:
    capture, _ = _capture()
    sidecar = _sidecar(capture)
    scores = [
        {
            "candidate_instance_id": row["candidate_instance_id"],
            "roster_id": row["roster_id"],
            "realized_score_milli": 180_000,
        }
        for row in sidecar["strategy_decisions"]
    ]
    settlement = build_first_loss_settlement_v2(
        sidecar=sidecar,
        outcome_binding=_outcome_binding(sidecar, scores),
    )

    assert {row["first_observed_state"] for row in settlement["rows"]} == {
        "FINAL_BOOK",
        "ELIGIBLE_NOT_SELECTED",
        "NOT_ADMITTED",
        "NOT_PRODUCED_IN_OBSERVED_REQUEST_UNIVERSE",
    }
    assert settlement["causal_first_loss_claim"] is False
    assert settlement["settlement_authority"] is False
