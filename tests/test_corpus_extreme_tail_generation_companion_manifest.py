from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Callable

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_factorial_manifest as factorial
from nfl_dfs.research import corpus_extreme_tail_generation_additions as additions
from nfl_dfs.research import (
    corpus_extreme_tail_generation_companion_manifest as companion,
)
from nfl_dfs.research import corpus_parametric_batch as batch


COMMIT = "a" * 40
DIGEST = "sha256:" + "b" * 64
IMAGE = {
    "uri": f"us-central1-docker.pkg.dev/example/research/generation@{DIGEST}",
    "digest": DIGEST,
}
OUTPUT_PREFIX = "gs://fixture-bucket/research/factorial/run-001/"
CATALOG_ID = "fixture-factorial-source-catalog-v1"
CATALOG_URI = "gs://fixture-bucket/research/factorial/source-catalog-v1.json"
SHADOW_IDENTITY = {
    "uri": "gs://fixture-bucket/prospective/2026-cbwu-oi-v1.json",
    "generation": "820260818",
    "sha256": "c" * 64,
    "bytes": 20_026,
}
MATRIX_DERIVATION_IMPLEMENTATION_SHA256 = "e" * 64


def _identity(label: str, ordinal: int) -> dict[str, object]:
    payload = f"{label}:{ordinal}".encode()
    return {
        "uri": f"gs://fixture-bucket/objects/{label}-{ordinal:05d}.json",
        "generation": str(10_000 + ordinal),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _source_members() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    source_ordinal = 0
    world_ordinal = 10_000
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            blocks = (
                ("R0", "R1", "R2", "R4")
                if (season, week) == (2025, 1)
                else ("R0", "R1", "R2", "R3", "R4")
            )
            rows.append({
                "source_ordinal": source_ordinal,
                "slate_id": f"{season}-w{week:02d}",
                "season": season,
                "week": week,
                "reconstruction_source_identity": _identity(
                    "reconstruction", source_ordinal
                ),
                "ordinary_r_blocks": [
                    {
                        "block_id": block_id,
                        "world_count": 10_000,
                        "world_identity": _identity("world", world_ordinal + index),
                    }
                    for index, block_id in enumerate(blocks)
                ],
            })
            world_ordinal += 5
            source_ordinal += 1
    return rows


def _bundle(
    sources: list[dict[str, object]] | None = None,
    *,
    catalog_generation: str = "9001",
) -> dict[str, object]:
    members = _source_members() if sources is None else sources
    catalog = factorial.build_extreme_tail_factorial_source_catalog_v1(
        catalog_id=CATALOG_ID, source_members=members
    )
    identity = batch.object_identity_for_json(
        catalog, uri=CATALOG_URI, generation=catalog_generation
    )
    p0 = factorial.frozen_extreme_tail_factorial_p0_environment_v1()
    p0_hash = batch.canonical_sha256(p0)
    core = factorial.build_extreme_tail_factorial_execution_manifest_v1(
        source_catalog=catalog,
        source_catalog_identity=identity,
        p0_generation_environment=p0,
        p0_generation_environment_sha256=p0_hash,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
    )
    return {
        "source_catalog": catalog,
        "source_catalog_identity": identity,
        "p0_generation_environment": p0,
        "p0_generation_environment_sha256": p0_hash,
        "factorial_manifest": core,
    }


def _build(bundle: dict[str, object] | None = None) -> dict[str, object]:
    inputs = _bundle() if bundle is None else bundle
    return companion.build_extreme_tail_generation_companion_manifest_v1(
        **inputs,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
        prospective_k20_oi_shadow_identity=SHADOW_IDENTITY,
    )


def _validate(
    value: object, bundle: dict[str, object] | None = None
) -> dict[str, object]:
    inputs = _bundle() if bundle is None else bundle
    return companion.validate_extreme_tail_generation_companion_manifest_v1(
        value,
        **inputs,
        source_commit_sha=COMMIT,
        immutable_image=IMAGE,
        output_prefix=OUTPUT_PREFIX,
        prospective_k20_oi_shadow_identity=SHADOW_IDENTITY,
    )


def _rehash(value: dict[str, object]) -> dict[str, object]:
    retained = deepcopy(value)
    retained.pop("generation_companion_manifest_sha256", None)
    retained["generation_companion_manifest_sha256"] = batch.canonical_sha256(
        retained
    )
    return retained


def _rehash_public(value: dict[str, object], field: str) -> dict[str, object]:
    retained = deepcopy(value)
    retained.pop(field, None)
    retained[field] = batch.canonical_sha256(retained)
    return retained


def _control_players() -> list[dict[str, object]]:
    rows = [
        {
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": game_id,
            "salary": 5500,
        }
        for player_id, position, team, opponent, game_id in (
            ("a-qb", "QB", "A", "B", "g1"),
            ("a-rb", "RB", "A", "B", "g1"),
            ("a-wr1", "WR", "A", "B", "g1"),
            ("a-wr2", "WR", "A", "B", "g1"),
            ("a-wr3", "WR", "A", "B", "g1"),
            ("b-rb", "RB", "B", "A", "g1"),
            ("b-wr1", "WR", "B", "A", "g1"),
            ("b-wr2", "WR", "B", "A", "g1"),
            ("c-dst", "DST", "C", "D", "g2"),
            ("c-te", "TE", "C", "D", "g2"),
            ("c-wr1", "WR", "C", "D", "g2"),
            ("c-wr2", "WR", "C", "D", "g2"),
        )
    ]
    return sorted(rows, key=lambda row: str(row["id"]))


def _control_roster(seed: int) -> list[str]:
    return sorted([
        "a-qb",
        "a-rb",
        "a-wr1",
        ("a-wr2", "a-wr3")[seed % 2],
        "b-rb",
        ("b-wr1", "b-wr2")[(seed // 2) % 2],
        "c-dst",
        "c-te",
        ("c-wr1", "c-wr2")[(seed // 4) % 2],
    ])


def _roster_sha256(roster: list[str]) -> str:
    return batch.canonical_sha256({
        "schema_version": "canonical-dk-roster-identity/v1",
        "player_ids": roster,
    })


def _proof(
    *, proof_id: str, proof_kind: str, input_body: object, output_body: object
) -> dict[str, object]:
    return {
        "proof_id": proof_id,
        "proof_kind": proof_kind,
        "implementation_sha256": MATRIX_DERIVATION_IMPLEMENTATION_SHA256,
        "input_sha256": batch.canonical_sha256(input_body),
        "output_sha256": batch.canonical_sha256(output_body),
        "proof_object_identity": _identity(f"proof-{proof_id}", 200),
    }


def _hard_control_inputs() -> dict[str, object]:
    occurrences: list[dict[str, object]] = []
    rows = (
        ("optimal", "lineup-a", _control_roster(0)),
        ("optimal", "lineup-b", _control_roster(0)),
        ("infeasible", None, None),
        ("optimal", "lineup-a", _control_roster(1)),
    )
    for ordinal, (status, lineup_id, roster) in enumerate(rows):
        optimal = status == "optimal"
        occurrences.append({
            "occurrence_ordinal": ordinal,
            "solver_status": status,
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "roster_sha256": _roster_sha256(roster) if roster is not None else None,
            "legality_passed": True if optimal else None,
            "solver_proof_identity": _identity("hard-solver-proof", ordinal),
            "legality_proof_identity": (
                _identity("hard-legality-proof", ordinal) if optimal else None
            ),
        })
    stream = companion.build_hard230_control_stream_manifest_v1(
        stream_id="fixture-complete-hard-stream",
        candidate_origin_id="R0",
        fit_scope_id="holdout-R4",
        generator_configuration_sha256="7" * 64,
        solver_implementation_sha256="8" * 64,
        target_retained_count=2,
        source_stream_world_count=5,
        execution_mode="test-fixture",
        termination_reason="paired-target-reached",
        exhaustion_proof_identity=None,
        occurrences=occurrences,
    )
    return {
        "slate_id": "2023-w01",
        "candidate_origin_id": "R0",
        "fit_scope_id": "holdout-R4",
        "heldout_block_id": "R4",
        "training_block_ids": ["R0", "R1", "R2", "R3"],
        "source_member_sha256": "3" * 64,
        "score_block_ids": ["R0", "R1", "R2", "R3"],
        "score_block_identities_sha256": "4" * 64,
        "player_registry_sha256": "5" * 64,
        "player_score_matrix_sha256": "6" * 64,
        "ordered_generator_stream_manifest": stream,
        "ordered_generator_stream_manifest_identity": (
            batch.object_identity_for_json(
                stream,
                uri="gs://fixture-bucket/objects/hard-stream-manifest.json",
                generation="22001",
            )
        ),
        "generator_configuration_sha256": "7" * 64,
        "solver_implementation_sha256": "8" * 64,
        "paired_target_identity": _identity("p0-target", 0),
        "target_retained_count": 2,
        "source_stream_world_count": 5,
        "execution_mode": "test-fixture",
        "occurrences": occurrences,
    }


def _discovery_control_inputs() -> dict[str, object]:
    players = _control_players()
    matrix = np.zeros((len(players), 25), dtype="<i8")
    for block_ordinal in range(5):
        start = block_ordinal * 5
        matrix[0, start:start + 5] = [5_000, 9_000, 9_000, 1_000, 0]
    member_sha = batch.canonical_sha256({"member": "control-fixture"})
    source = {
        "member_id": "control-source-member",
        "slate_id": "2023-w01",
        "member_sha256": member_sha,
        "object_identity": {
            "uri": "gs://fixture-bucket/objects/control-source.json",
            "generation": "12001",
            "sha256": member_sha,
            "bytes": 100,
        },
    }
    blocks = [
        {
            "block_id": block_id,
            "world_count": 5,
            "source_member_sha256": member_sha,
            "object_identity": _identity("control-block", ordinal + 20),
        }
        for ordinal, block_id in enumerate(("R0", "R1", "R2", "R3", "R4"))
    ]
    matrix_hash = additions.canonical_score_matrix_sha256_v1(matrix)
    artifact = _identity("control-matrix", 30)
    matrix_id = "control-all-five-ordinary-r-matrix"
    derivation_input = {
        "matrix_id": matrix_id,
        "score_unit": "milli-DraftKings-points",
        "matrix_shape": [len(players), 25],
        "artifact_identity": artifact,
        "source_member_sha256": member_sha,
        "score_block_identities_sha256": batch.canonical_sha256(blocks),
        "player_registry_sha256": batch.canonical_sha256(players),
    }
    matrix_identity = {
        **derivation_input,
        "canonical_score_matrix_sha256": matrix_hash,
        "derivation_proof_identity": _proof(
            proof_id="derive-control-matrix",
            proof_kind="score-matrix-derivation-v1",
            input_body=derivation_input,
            output_body={"canonical_score_matrix_sha256": matrix_hash},
        ),
    }
    solve_results: list[dict[str, object]] = []
    position = 0
    for block_id in ("R0", "R1", "R2", "R3"):
        for world_index in (1, 2):
            if position == 0:
                lineup_id, roster = "shared-lineup", _control_roster(0)
            elif position == 1:
                lineup_id, roster = "distinct-id", _control_roster(0)
            elif position == 2:
                lineup_id, roster = "shared-lineup", _control_roster(1)
            else:
                lineup_id, roster = f"lineup-{position}", _control_roster(position - 1)
            solve_results.append({
                "schedule_position": position,
                "block_id": block_id,
                "world_index": world_index,
                "solver_status": "optimal",
                "lineup_id": lineup_id,
                "roster_player_ids": roster,
                "roster_sha256": _roster_sha256(roster),
                "legality_passed": True,
                "solver_proof_identity": _identity("visit-solver-proof", position),
                "legality_proof_identity": _identity(
                    "visit-legality-proof", position
                ),
            })
            position += 1
    return {
        "slate_id": "2023-w01",
        "fit_scope_id": "holdout-R4",
        "heldout_block_id": "R4",
        "training_block_ids": ["R0", "R1", "R2", "R3"],
        "source_member_identity": source,
        "ordinary_r_block_identities": blocks,
        "player_registry": players,
        "ordinary_r_player_score_matrix": matrix,
        "ordinary_r_score_matrix_identity": matrix_identity,
        "worlds_per_block": 5,
        "visits_per_block": 2,
        "solver_implementation_sha256": "c" * 64,
        "solve_results": solve_results,
        "execution_mode": "test-fixture",
    }


def test_manifest_binds_current_protocol_census_and_unchanged_core() -> None:
    inputs = _bundle()
    original_core_bytes = batch.canonical_json_bytes(inputs["factorial_manifest"])
    value = _build(inputs)

    assert value["schema_version"] == (
        "foundry-extreme-tail-generation-companion-manifest/v1"
    )
    assert value["protocol_document"] == (
        "reports/2026-08-25-pre-week1-historical-experiment-matrix.md"
    )
    assert value["protocol_sha256"] == (
        "b7d6c8f4f0ed2f6db667933717f5446545a06f1f2cda2c8ecd56ca26b45d34bc"
    )
    assert value["census_document"] == (
        "reports/2026-08-25-complete-pre-week1-foundry-strategy-census.md"
    )
    assert value["census_sha256"] == (
        "bb05e1ec5fa7a7d836282b41a2ed864aa7828a939257e674cf0625511862950f"
    )
    core = inputs["factorial_manifest"]
    assert value["core_factorial_manifest_id"] == core["manifest_id"]
    assert value["core_factorial_manifest_sha256"] == core[
        "execution_manifest_sha256"
    ]
    assert value["core_protocol_sha256"] == (
        "4cd61f51617322bcafb3e2a867332ed4e35484073aa47c3d9891339fd493f338"
    )
    assert batch.canonical_json_bytes(inputs["factorial_manifest"]) == (
        original_core_bytes
    )


def test_exact_53_slate_source_lineage_and_output_uris_are_derived() -> None:
    value = _build()
    slates = value["factorial_slates"]
    assert len(slates) == 53
    assert [row["factorial_slate_ordinal"] for row in slates] == list(range(53))
    assert [row["source_ordinal"] for row in slates] == [
        ordinal for ordinal in range(54) if ordinal != 36
    ]
    assert slates[35]["slate_id"] == "2024-w18"
    assert slates[36]["slate_id"] == "2025-w02"
    assert "2025-w01" not in {row["slate_id"] for row in slates}
    assert value["source_catalog_identity"] == _bundle()[
        "source_catalog_identity"
    ]
    assert value["factorial_slates_sha256"] == batch.canonical_sha256(slates)

    uris: list[str] = []
    for ordinal, row in enumerate(slates):
        assert row["source_lineage_sha256"] == batch.canonical_sha256(
            row["source_lineage"]
        )
        assert [
            block["block_id"] for block in row["source_lineage"]["ordinary_r_blocks"]
        ] == ["R0", "R1", "R2", "R3", "R4"]
        assert {
            block["world_count"]
            for block in row["source_lineage"]["ordinary_r_blocks"]
        } == {10_000}
        prefix = (
            OUTPUT_PREFIX
            + f"generation-companion-v1/slates/{ordinal:02d}-{row['slate_id']}/"
        )
        assert row["companion_output_uris"]["player_ordinary_r_matrix_uri"] == (
            prefix + "ordinary-r-player-matrix-v1.npz"
        )
        assert row["companion_output_uris"]["selector_books_uri"] == (
            prefix + "stage-b-selector-books-v1.json"
        )
        uris.extend(row["companion_output_uris"].values())
    assert len(uris) == 53 * 12
    assert len(set(uris)) == len(uris)


def test_prospective_k20_oi_shadow_is_generation_content_and_bytes_bound() -> None:
    value = _build()
    binding = value["prospective_k20_oi_shadow_binding"]
    assert binding["shadow_id"] == "2026-cbwu-oi-v1"
    assert binding["treatment_entry_budget"] == 20
    assert binding["shadow_manifest_identity"] == SHADOW_IDENTITY
    assert binding["identity_dimensions"] == [
        "uri", "generation", "sha256", "bytes"
    ]
    assert binding["historical_companion_may_modify_or_replace_shadow"] is False
    assert binding["historical_k20_factorial_is_a_separate_identity"] is True
    assert value["prospective_k20_oi_shadow_binding_sha256"] == binding[
        "prospective_k20_oi_shadow_binding_sha256"
    ]


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("uri", "gs://fixture-bucket/prospective/spliced-shadow.json"),
        ("generation", "820260819"),
        ("sha256", "d" * 64),
        ("bytes", 20_027),
    ],
)
def test_prospective_shadow_identity_drift_fails_replay(
    field: str, replacement: object
) -> None:
    retained = _build()
    changed = deepcopy(SHADOW_IDENTITY)
    changed[field] = replacement
    inputs = _bundle()
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        companion.validate_extreme_tail_generation_companion_manifest_v1(
            retained,
            **inputs,
            source_commit_sha=COMMIT,
            immutable_image=IMAGE,
            output_prefix=OUTPUT_PREFIX,
            prospective_k20_oi_shadow_identity=changed,
        )


def test_public_generation_contracts_are_literal_and_stably_ordered() -> None:
    value = _build()
    registry = value["generation_registry"]
    assert [row["generation_ordinal"] for row in registry] == [0, 1]
    assert [row["strategy_id"] for row in registry] == [
        "hard-230-generate-replenish-v1",
        "game-regime-stratified-tail-discovery-v1",
    ]
    assert [row["strategy_sha256"] for row in registry] == [
        "524aa7cb737f325cafccda857ce68ac8f5801967f2d157aa06de85fd057da594",
        "4389ad29e21340fee2bef6e2e76bb5cb773a39f78e580bb7c77acd8fcde41f30",
    ]
    assert [row["implementation_sha256"] for row in registry] == [
        "2700a83440e05056c99d429e0f910074c492fac10e55a860891964f4ae6b3da1",
        "3e0a849e9cf57ad8edbdd903f1e0e06d785f19832ac1c1fd39d935224f634bd2",
    ]
    assert [row["public_contract_sha256"] for row in registry] == [
        "8454f3993c320d5f0b9689a37f25a42b06e56d6ec6eb7fbd3b680e9f77954ec1",
        "94eeba2d806516c4ce22c5ef3480dd343a440618395bad93cec009a2303ebf3c",
    ]
    assert registry[0]["public_contract"] == (
        additions.frozen_hard230_generation_replenishment_contract_v1()
    )
    assert registry[1]["public_contract"] == (
        additions.frozen_game_regime_tail_discovery_contract_v1()
    )
    assert value["generation_registry_sha256"] == (
        "a698cc9c717974155e5ab417e1f8b2284b185be512a7b8d3bffe85c439927913"
    )
    for row in registry:
        assert row["candidate_origin_mask_id"] == "K5"
        assert row["standalone_evidence_role"] == (
            "diagnostic-nonpublication-only"
        )
        for field in companion._PUBLIC_FALSE_AUTHORITY_FIELDS:  # noqa: SLF001
            assert row["public_contract"][field] is False


def test_paired_controls_are_exact_source_composition_and_budget_matches() -> None:
    value = _build()
    controls = value["paired_control_registry"]
    assert value["paired_control_registry_sha256"] == (
        "725f59b66c2336799bb243f61505e59e434e0937146c638f8edd7609f8a7e871"
    )
    assert [row["control_id"] for row in controls] == [
        "hard-230-score-blind-stream-prefix-control-v1",
        "incumbent-equal-visit-control-v1",
    ]
    hard = controls[0]["control_contract"]
    assert hard["control_population_id"] == "P0-incumbent-native"
    assert hard["admission_reads_simulated_score_or_value"] is False
    assert hard["target_law"] == (
        "exact-registered-p0-native-retained-count-for-slate-origin-fit-scope"
    )
    assert hard["stream_pairing_law"] == (
        "same-generation-pinned-complete-ordered-generator-stream-source-"
        "scope-public-contract-derived-effective-ceiling-and-termination"
    )
    discovery = controls[1]["control_contract"]
    assert discovery["schedule_law"] == (
        "existing-incumbent-top-total-world-schedule-v1"
    )
    assert discovery["budget_law"] == "exact-same-scope-visit-and-solve-count"
    assert discovery["uses_atlas_world_ranking"] is False
    assert discovery["uses_realized_outcomes"] is False
    assert discovery["unique_yield_is_reported_not_force-matched"] is True
    for row in controls:
        assert row["implementation_sha256"] == (
            "f55f43ac4f8594ac3d3f8400b21aae863f27f3739aa0578bfac162aa5b90c5b7"
        )
        assert row["control_contract_sha256"] == batch.canonical_sha256(
            row["control_contract"]
        )


def test_paired_control_implementation_is_literal_and_publicly_replayable() -> None:
    implementation = companion.frozen_generation_companion_control_implementation_v1()
    assert implementation["implementation_id"] == (
        "canonical-score-blind-prefix-and-equal-visit-controls-v1"
    )
    assert implementation["implementation_sha256"] == (
        "f55f43ac4f8594ac3d3f8400b21aae863f27f3739aa0578bfac162aa5b90c5b7"
    )
    assert implementation["hard230_builder"] == (
        "build_hard230_score_blind_control_receipt_v1"
    )
    assert implementation["discovery_builder"] == (
        "build_incumbent_equal_visit_control_receipt_v1"
    )
    value = _build()
    assert value["control_implementation_contract"] == implementation
    assert value["control_implementation_sha256"] == implementation[
        "implementation_sha256"
    ]


def test_hard_control_receipt_replays_score_blind_prefix_and_duplicate_law() -> None:
    inputs = _hard_control_inputs()
    first = companion.build_hard230_score_blind_control_receipt_v1(**inputs)
    second = companion.build_hard230_score_blind_control_receipt_v1(
        **deepcopy(inputs)
    )
    assert first == second
    assert [row["lineup_id"] for row in first["retained_rosters"]] == [
        "lineup-a", "lineup-a"
    ]
    assert first["retained_rosters"][0]["roster_sha256"] != (
        first["retained_rosters"][1]["roster_sha256"]
    )
    assert first["occurrences"][0]["roster_sha256"] == (
        first["occurrences"][1]["roster_sha256"]
    )
    assert first["retained_count"] == 2
    assert first["consumed_occurrence_count"] == 4
    assert first["shortfall_count"] == 0
    assert first["completion_status"] == "complete"
    assert first["score_or_value_read"] is False
    assert companion.validate_hard230_score_blind_control_receipt_v1(
        deepcopy(first), **inputs
    ) == first
    for occurrence in first["occurrences"]:
        assert not any("score" in key or "value" in key for key in occurrence)


def test_hard_control_receipt_rejects_stream_scope_and_score_field_splices() -> None:
    inputs = _hard_control_inputs()
    receipt = companion.build_hard230_score_blind_control_receipt_v1(**inputs)

    changed_inputs = deepcopy(inputs)
    changed_inputs["ordered_generator_stream_manifest_identity"][
        "generation"
    ] = "99999"
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        companion.validate_hard230_score_blind_control_receipt_v1(
            receipt, **changed_inputs
        )

    with_score = deepcopy(inputs)
    with_score["occurrences"][0]["simulated_score"] = 231.0
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="fields differ",
    ):
        companion.build_hard230_score_blind_control_receipt_v1(**with_score)

    early_prefix = deepcopy(inputs)
    early_prefix["occurrences"] = early_prefix["occurrences"][:4]
    early_stream = companion.build_hard230_control_stream_manifest_v1(
        stream_id="fixture-complete-hard-stream",
        candidate_origin_id="R0",
        fit_scope_id="holdout-R4",
        generator_configuration_sha256="7" * 64,
        solver_implementation_sha256="8" * 64,
        target_retained_count=2,
        source_stream_world_count=5,
        execution_mode="test-fixture",
        termination_reason="paired-target-reached",
        exhaustion_proof_identity=None,
        occurrences=early_prefix["occurrences"],
    )
    early_prefix["ordered_generator_stream_manifest"] = early_stream
    early_prefix["ordered_generator_stream_manifest_identity"] = (
        batch.object_identity_for_json(
            early_stream,
            uri="gs://fixture-bucket/objects/hard-stream-prefix.json",
            generation="22002",
        )
    )
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        companion.validate_hard230_score_blind_control_receipt_v1(
            receipt, **early_prefix
        )


def test_hard_control_under_target_requires_exact_effective_ceiling() -> None:
    inputs = _hard_control_inputs()
    inputs["occurrences"] = inputs["occurrences"][:3]
    stream = companion.build_hard230_control_stream_manifest_v1(
        stream_id="fixture-ceiling-hard-stream",
        candidate_origin_id="R0",
        fit_scope_id="holdout-R4",
        generator_configuration_sha256="7" * 64,
        solver_implementation_sha256="8" * 64,
        target_retained_count=2,
        source_stream_world_count=3,
        execution_mode="test-fixture",
        termination_reason="effective-ceiling-reached",
        exhaustion_proof_identity=None,
        occurrences=inputs["occurrences"],
    )
    inputs["source_stream_world_count"] = 3
    inputs["ordered_generator_stream_manifest"] = stream
    inputs["ordered_generator_stream_manifest_identity"] = (
        batch.object_identity_for_json(
            stream,
            uri="gs://fixture-bucket/objects/ceiling-hard-stream.json",
            generation="22003",
        )
    )
    receipt = companion.build_hard230_score_blind_control_receipt_v1(**inputs)
    assert receipt["retained_count"] == 1
    assert receipt["shortfall_count"] == 1
    assert receipt["completion_status"] == (
        "mechanical-infeasibility-effective-ceiling-reached"
    )
    assert receipt["execution_mode"] == "test-fixture"
    assert receipt["computed_solver_call_ceiling"] == 200
    assert receipt["effective_solver_call_ceiling"] == 3


def test_hard_control_rejects_coherent_lowered_release_ceiling() -> None:
    inputs = _hard_control_inputs()
    release_stream = companion.build_hard230_control_stream_manifest_v1(
        stream_id="fixture-complete-hard-stream",
        candidate_origin_id="R0",
        fit_scope_id="holdout-R4",
        generator_configuration_sha256="7" * 64,
        solver_implementation_sha256="8" * 64,
        target_retained_count=2,
        source_stream_world_count=10_000,
        execution_mode="release",
        termination_reason="paired-target-reached",
        exhaustion_proof_identity=None,
        occurrences=inputs["occurrences"],
    )
    assert release_stream["minimum_solver_call_ceiling"] == 200
    assert release_stream["solver_calls_per_target"] == 20
    assert release_stream["maximum_solver_call_ceiling"] == 10_000
    assert release_stream["computed_solver_call_ceiling"] == 200
    assert release_stream["effective_solver_call_ceiling"] == 200

    forged_stream = deepcopy(release_stream)
    forged_stream["effective_solver_call_ceiling"] = 5
    inputs["execution_mode"] = "release"
    inputs["source_stream_world_count"] = 10_000
    inputs["ordered_generator_stream_manifest"] = forged_stream
    inputs["ordered_generator_stream_manifest_identity"] = (
        batch.object_identity_for_json(
            forged_stream,
            uri="gs://fixture-bucket/objects/forged-lowered-release-stream.json",
            generation="22004",
        )
    )
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="complete ordered generator stream manifest differs",
    ):
        companion.build_hard230_score_blind_control_receipt_v1(**inputs)

    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="exactly 10,000 source-stream worlds",
    ):
        companion.build_hard230_control_stream_manifest_v1(
            stream_id="fixture-escalated-to-release",
            candidate_origin_id="R0",
            fit_scope_id="holdout-R4",
            generator_configuration_sha256="7" * 64,
            solver_implementation_sha256="8" * 64,
            target_retained_count=2,
            source_stream_world_count=5,
            execution_mode="release",
            termination_reason="paired-target-reached",
            exhaustion_proof_identity=None,
            occurrences=_hard_control_inputs()["occurrences"],
        )


def test_hard_control_rejects_coherently_rehashed_early_exhaustion() -> None:
    inputs = _hard_control_inputs()
    inputs["occurrences"] = inputs["occurrences"][:3]
    normalized = companion._normalize_hard_control_occurrences(  # noqa: SLF001
        inputs["occurrences"]
    )
    proof_content = {
        "stream_id": "fixture-complete-hard-stream",
        "next_stream_position": 3,
        "additional_occurrence_exists": False,
    }
    proof_identity = batch.object_identity_for_json(
        proof_content,
        uri="gs://fixture-bucket/objects/forged-exhaustion-proof.json",
        generation="22005",
    )
    forged_stream = deepcopy(inputs["ordered_generator_stream_manifest"])
    forged_stream["occurrence_count"] = 3
    forged_stream["stream_positions"] = [0, 1, 2]
    forged_stream["occurrence_membership_sha256"] = batch.canonical_sha256(
        normalized
    )
    forged_stream["termination_reason"] = "generator-exhausted-before-ceiling"
    forged_stream["generator_exhausted"] = True
    forged_stream["exhaustion_proof_identity"] = {
        "proof_content": proof_content,
        "proof_content_identity": proof_identity,
    }
    inputs["ordered_generator_stream_manifest"] = forged_stream
    inputs["ordered_generator_stream_manifest_identity"] = (
        batch.object_identity_for_json(
            forged_stream,
            uri="gs://fixture-bucket/objects/forged-truncated-stream.json",
            generation="22006",
        )
    )
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="unsupported by the public v1 contiguous-world-stream law",
    ):
        companion.build_hard230_score_blind_control_receipt_v1(**inputs)


def test_discovery_control_derives_exact_equal_visit_schedule_and_unique_yield() -> None:
    inputs = _discovery_control_inputs()
    receipt = companion.build_incumbent_equal_visit_control_receipt_v1(**inputs)
    assert [
        (row["block_id"], row["world_index"])
        for row in receipt["visit_schedule"]
    ] == [
        (block_id, world_index)
        for block_id in ("R0", "R1", "R2", "R3")
        for world_index in (1, 2)
    ]
    assert receipt["visit_count"] == receipt["solve_count"] == 8
    assert receipt["unique_yield_count"] == 7
    assert receipt["duplicate_optimal_count"] == 1
    assert receipt["ordinary_r_matrix_encoding"] == (
        "row-major-little-endian-int64-milli-dk/v1"
    )
    assert receipt["ordinary_r_score_matrix_identity"]["matrix_shape"] == [12, 25]
    assert [row["lineup_id"] for row in receipt["unique_rosters"][:2]] == [
        "shared-lineup", "shared-lineup"
    ]
    assert receipt["solve_results"][0]["roster_sha256"] == (
        receipt["solve_results"][1]["roster_sha256"]
    )
    assert receipt["uses_heldout_scores"] is False
    assert receipt["uses_atlas_or_realized_values"] is False
    assert receipt["execution_mode"] == "test-fixture"
    assert companion.validate_incumbent_equal_visit_control_receipt_v1(
        deepcopy(receipt), **inputs
    ) == receipt


def test_discovery_control_rejects_small_width_in_release_mode() -> None:
    inputs = _discovery_control_inputs()
    inputs["execution_mode"] = "release"
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="exactly 10,000 worlds per block",
    ):
        companion.build_incumbent_equal_visit_control_receipt_v1(**inputs)


def test_discovery_control_rejects_matrix_source_schedule_and_atlas_splices() -> None:
    inputs = _discovery_control_inputs()
    receipt = companion.build_incumbent_equal_visit_control_receipt_v1(**inputs)

    changed_matrix = deepcopy(inputs)
    changed_matrix["ordinary_r_player_score_matrix"][0, 0] += 1
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="shared all-five",
    ):
        companion.validate_incumbent_equal_visit_control_receipt_v1(
            receipt, **changed_matrix
        )

    changed_source = deepcopy(inputs)
    changed_source["source_member_identity"]["member_sha256"] = "d" * 64
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="shared all-five",
    ):
        companion.validate_incumbent_equal_visit_control_receipt_v1(
            receipt, **changed_source
        )

    converted_matrix = deepcopy(inputs)
    converted_matrix["ordinary_r_player_score_matrix"] = np.ascontiguousarray(
        converted_matrix["ordinary_r_player_score_matrix"].astype("<f8")
    )
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="little-endian int64 milli-DK law",
    ):
        companion.build_incumbent_equal_visit_control_receipt_v1(
            **converted_matrix
        )

    identity_splice = deepcopy(inputs)
    identity_splice["ordinary_r_score_matrix_identity"][
        "canonical_score_matrix_sha256"
    ] = "f" * 64
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="shared all-five",
    ):
        companion.build_incumbent_equal_visit_control_receipt_v1(
            **identity_splice
        )

    changed_schedule = deepcopy(inputs)
    changed_schedule["solve_results"][0]["world_index"] = 0
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="derived visit schedule",
    ):
        companion.build_incumbent_equal_visit_control_receipt_v1(
            **changed_schedule
        )

    with_atlas = deepcopy(inputs)
    with_atlas["solve_results"][0]["atlas_score"] = 300.0
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="fields differ",
    ):
        companion.build_incumbent_equal_visit_control_receipt_v1(**with_atlas)


def test_ordinary_r_and_cross_fit_laws_never_use_heldout_generation_inputs() -> None:
    value = _build()
    matrix = value["ordinary_r_matrix_law"]
    assert matrix["evaluation_blocks"] == ["R0", "R1", "R2", "R3", "R4"]
    assert matrix["worlds_per_block"] == 10_000
    assert matrix["world_count_per_slate"] == 50_000
    assert matrix["ordinary_unweighted_r_worlds"] is True
    assert matrix["candidate_generation_shared_across_r194_and_t230"] is True
    assert matrix["score_each_companion_union_roster_once"] is True
    assert matrix["heldout_or_realized_generation_input_forbidden"] is True
    assert matrix["tail_biased_frequency_is_not_target_probability"] is True
    assert matrix["ordinary_r_matrix_law_sha256"] == (
        "e5034012a3009defa19629c39f6b7a8ecdce6f4b902b859614099fdc7329b9da"
    )

    cross_fit = value["generation_cross_fit_law"]
    assert cross_fit["candidate_origin_mask_id"] == "K5"
    assert cross_fit["hard230_fold_origin_receipt_count_per_slate"] == 20
    assert cross_fit["hard230_final_fit_origin_receipt_count_per_slate"] == 5
    assert cross_fit["hard230_total_receipt_count_per_slate"] == 25
    assert cross_fit["discovery_fold_schedule_count_per_slate"] == 5
    for fold in cross_fit["folds"]:
        heldout = fold["heldout_block_id"]
        assert heldout not in fold["training_block_ids"]
        assert heldout not in fold["hard230_eligible_candidate_origin_ids"]
        assert all(
            heldout not in blocks
            for blocks in fold["hard230_permitted_score_block_ids_by_origin"].values()
        )
    assert cross_fit["discovery_final_population_law"] == (
        "canonical-roster-union-of-all-five-cross-fit-schedule-populations"
    )
    assert cross_fit[
        "additional_unregistered_discovery_final_schedule_forbidden"
    ] is True


def test_retrieval_dependencies_bind_exact_full_r194_and_t230_contract_rows() -> None:
    value = _build()
    rows = value["retrieval_dependency_registry"]
    assert [row["retrieval_id"] for row in rows] == [
        "coverage-194-v1",
        "frozen-census-support-switch-ge-230/v1",
    ]
    assert [row["strategy_contract_sha256"] for row in rows] == [
        "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f",
        "e44525130cdd119d441178da9f2a003876f63d328b44f1730b48064ef61d56ab",
    ]
    assert [row["implementation_contract_sha256"] for row in rows] == [
        "bc54abd13c4a5ecd5966dcc5e1b78afb06028850865517bde754507ccc40e94f",
        "73f53f8b3e7b8d9ec6c661de16e5c171917526858bc1a358a555fcc78085bd30",
    ]
    assert value["retrieval_dependency_registry_sha256"] == (
        "93fa6b8f643c46a4dc26580140ff184ce34588b6c0c505e9c321ec379b550318"
    )
    core_catalog = _bundle()["factorial_manifest"]["retrieval_contract"][
        "catalog"
    ]
    assert rows[0]["core_retrieval_row"] == core_catalog[0]
    assert rows[1]["core_retrieval_row"] == core_catalog[5]


def test_stage_b_catalog_is_exact_two_matched_four_cell_surfaces() -> None:
    value = _build()
    rows = value["stage_b_catalog_registry"]
    assert len(rows) == 8
    assert [row["catalog_entry_ordinal"] for row in rows] == list(range(8))
    for start in (0, 4):
        surface = rows[start:start + 4]
        assert [row["stage_b_cell"] for row in surface] == ["A", "B", "C", "D"]
        assert [row["generation_arm"] for row in surface] == [
            "control",
            "challenger",
            "control",
            "challenger",
        ]
        assert [row["retrieval_id"] for row in surface] == [
            "coverage-194-v1",
            "coverage-194-v1",
            "frozen-census-support-switch-ge-230/v1",
            "frozen-census-support-switch-ge-230/v1",
        ]
        assert {tuple(row["entry_budgets"]) for row in surface} == {(4, 14, 80)}
        assert all(row["candidate_origin_mask_id"] == "K5" for row in surface)
        assert all(
            row["candidate_population_shared_between_retrieval_columns"]
            for row in surface
        )
        assert all(row["simulated_effect_screening_forbidden"] for row in surface)
        assert all(row["pre_grade_inclusion_required"] for row in surface)
    assert rows[0]["population_id"] == rows[2]["population_id"]
    assert rows[1]["population_id"] == rows[3]["population_id"]
    assert rows[4]["population_id"] == rows[6]["population_id"]
    assert rows[5]["population_id"] == rows[7]["population_id"]
    assert [row["counts_as_new_rank"] for row in rows] == [
        False, True, False, True, True, True, True, True
    ]
    assert rows[0]["core_factorial_cell_id"] == "H01-P0-K5-R194"
    assert rows[2]["core_factorial_cell_id"] == "H02-P0-K5-T230"
    assert rows[0]["core_factorial_cell"] == _bundle()["factorial_manifest"][
        "factorial_cell_registry"
    ][0]
    assert rows[2]["core_factorial_cell"] == _bundle()["factorial_manifest"][
        "factorial_cell_registry"
    ][1]
    assert all(
        rows[index]["catalog_entry_kind"] == "core-factorial-reference"
        for index in (0, 2)
    )
    assert all(
        rows[index]["core_factorial_cell_id"] is None
        for index in (1, 3, 4, 5, 6, 7)
    )
    assert value["stage_b_catalog_registry_sha256"] == (
        "b1c46dfb4f4a20989ebcd90453c8401d402272ee37f24dd963cca317287329e0"
    )


def test_aggregate_pre_grade_catalog_is_mandatory_but_not_final_authority() -> None:
    value = _build()
    catalog = value["aggregate_pre_grade_catalog_contract"]
    assert catalog["registered_fragment_count"] == 2
    assert [row["fragment_id"] for row in catalog["registered_fragments"]] == [
        "frozen-53-slate-factorial-core-v1",
        "generation-additions-stage-b-v1",
    ]
    assert catalog["registered_fragments"][1]["registry_row_count"] == 8
    assert catalog["registered_fragments"][1]["new_registry_row_count"] == 6
    assert catalog["registered_fragments"][1]["core_reference_row_count"] == 2
    assert catalog["core_factorial_registry_remains_exactly_18_rows"] is True
    assert catalog["core_eight_primary_cells_remain_byte_unchanged"] is True
    assert catalog["generation_companion_stage_b_entry_count_per_slate"] == 8
    assert catalog["generation_companion_new_rank_count_if_all-feasible"] == 318
    assert catalog["generation_companion_new_exact_book_count_if_all-feasible"] == 954
    assert catalog["core_reused_rank_count"] == 106
    assert catalog["core_reused_exact_book_count"] == 318
    assert catalog["total_referenced_rank_count"] == 424
    assert catalog["total_referenced_exact_book_count"] == 1272
    assert catalog["feasible_entry_requires_all_exact_books"] is True
    assert catalog[
        "mechanically_infeasible_entry_requires_bound_receipt"
    ] is True
    assert catalog["simulated_effect_screening_before_inclusion_forbidden"] is True
    assert catalog["other_complete_census_companion_fragments_still_required"]
    assert catalog["this_companion_is_not_the_final_complete_census_catalog"]
    assert catalog["this_contract_opens_outcome_access"] is False
    assert catalog["this_instance_opens_outcome_access"] is False
    assert catalog["catalog_status"] == (
        "outcome-blind-registration-incomplete-until-all-census-fragments-join"
    )
    assert catalog["aggregate_pre_grade_catalog_contract_sha256"] == (
        batch.canonical_sha256({
            key: item
            for key, item in catalog.items()
            if key != "aggregate_pre_grade_catalog_contract_sha256"
        })
    )


def test_manifest_is_deterministic_self_hashed_and_exactly_replayed() -> None:
    inputs = _bundle()
    first = _build(inputs)
    second = _build(deepcopy(inputs))
    assert batch.canonical_json_bytes(first) == batch.canonical_json_bytes(second)
    assert first["generation_companion_manifest_sha256"] == batch.canonical_sha256({
        key: item
        for key, item in first.items()
        if key != "generation_companion_manifest_sha256"
    })
    assert _validate(deepcopy(first), inputs) == first


def test_self_hash_unknown_field_and_coherent_top_level_rehash_fail_closed() -> None:
    inputs = _bundle()
    value = _build(inputs)

    damaged = deepcopy(value)
    damaged["ranking_depth"] = 79
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="self-hash differs",
    ):
        _validate(damaged, inputs)

    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        _validate(_rehash(damaged), inputs)

    unknown = deepcopy(value)
    unknown["latest_generation_alias"] = True
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="fields differ",
    ):
        _validate(_rehash(unknown), inputs)


@pytest.mark.parametrize("field", companion._FALSE_AUTHORITY_FIELDS)  # noqa: SLF001
def test_every_false_authority_is_fail_closed(field: str) -> None:
    inputs = _bundle()
    value = _build(inputs)
    assert value[field] is False
    changed = deepcopy(value)
    changed[field] = True
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="must be false",
    ):
        _validate(_rehash(changed), inputs)


@pytest.mark.parametrize(
    "path, replacement",
    [
        (("factorial_slates", 0, "source_lineage", "source_member_sha256"), "f" * 64),
        (("factorial_slates", 0, "companion_output_uris", "selector_books_uri"), "gs://splice/books.json"),
        (("ordinary_r_matrix_law", "ordinary_unweighted_r_worlds"), False),
        (("generation_cross_fit_law", "realized_outcomes_forbidden"), False),
        (("paired_control_registry", 0, "control_contract", "admission_reads_simulated_score_or_value"), True),
        (("paired_control_registry", 1, "control_contract", "uses_atlas_world_ranking"), True),
        (("stage_b_catalog_registry", 1, "retrieval_id"), "mean-score-v1"),
        (("aggregate_pre_grade_catalog_contract", "this_instance_opens_outcome_access"), True),
    ],
)
def test_coherent_nested_lineage_control_matrix_and_catalog_splices_fail(
    path: tuple[object, ...], replacement: object
) -> None:
    inputs = _bundle()
    changed = deepcopy(_build(inputs))
    target: object = changed
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        _validate(_rehash(changed), inputs)


def test_missing_stage_b_entry_cannot_be_rehashed_away() -> None:
    inputs = _bundle()
    changed = deepcopy(_build(inputs))
    changed["stage_b_catalog_registry"].pop()
    changed["stage_b_catalog_registry_sha256"] = batch.canonical_sha256(
        changed["stage_b_catalog_registry"]
    )
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        _validate(_rehash(changed), inputs)


@pytest.mark.parametrize("contract_name", ["hard", "discovery"])
@pytest.mark.parametrize("drift_kind", ["strategy", "implementation", "authority"])
def test_same_id_coherent_public_contract_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch, contract_name: str, drift_kind: str
) -> None:
    inputs = _bundle()
    if contract_name == "hard":
        contract = additions.frozen_hard230_generation_replenishment_contract_v1()
        helper = "frozen_hard230_generation_replenishment_contract_v1"
        self_field = "hard230_contract_sha256"
        if drift_kind == "strategy":
            contract["strategy_body"]["retention_threshold_milli_dk"] = 229_000
            new_hash = batch.canonical_sha256(contract["strategy_body"])
            contract["strategy_sha256"] = new_hash
        elif drift_kind == "implementation":
            contract["implementation_body"]["matrix_hash_row_chunk_size"] = 64
            new_hash = batch.canonical_sha256(contract["implementation_body"])
            contract["implementation_sha256"] = new_hash
        else:
            contract["publication_authority"] = True
    else:
        contract = additions.frozen_game_regime_tail_discovery_contract_v1()
        helper = "frozen_game_regime_tail_discovery_contract_v1"
        self_field = "discovery_contract_sha256"
        if drift_kind == "strategy":
            contract["strategy_body"]["spike_ratio"] = [3, 1]
            new_hash = batch.canonical_sha256(contract["strategy_body"])
            contract["strategy_sha256"] = new_hash
        elif drift_kind == "implementation":
            contract["implementation_body"]["world_aggregate_chunk_size"] = 512
            new_hash = batch.canonical_sha256(contract["implementation_body"])
            contract["implementation_sha256"] = new_hash
        else:
            contract["publication_authority"] = True
    contract = _rehash_public(contract, self_field)
    monkeypatch.setattr(additions, helper, lambda: deepcopy(contract))
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="public strategy/implementation contract drifted",
    ):
        _build(inputs)


@pytest.mark.parametrize(
    "helper, expected_match",
    [
        ("_hard230_control_body", "hard_control"),
        ("_discovery_control_body", "discovery_control"),
        ("_ordinary_r_matrix_law", "ordinary_r"),
        ("_generation_cross_fit_law", "cross_fit"),
        ("_aggregate_pre_grade_law", "aggregate"),
    ],
)
def test_local_literal_contract_drift_cannot_self_author(
    monkeypatch: pytest.MonkeyPatch, helper: str, expected_match: str
) -> None:
    inputs = _bundle()
    original: Callable[[], dict[str, object]] = getattr(companion, helper)

    def changed() -> dict[str, object]:
        body = deepcopy(original())
        if helper == "_hard230_control_body":
            body["target_law"] = "caller-selected-count"
        elif helper == "_discovery_control_body":
            body["budget_law"] = "approximately-equal"
        elif helper == "_ordinary_r_matrix_law":
            body["ordinary_unweighted_r_worlds"] = False
            body["ordinary_r_matrix_law_sha256"] = batch.canonical_sha256({
                key: item
                for key, item in body.items()
                if key != "ordinary_r_matrix_law_sha256"
            })
        elif helper == "_generation_cross_fit_law":
            body["realized_outcomes_forbidden"] = False
            body["generation_cross_fit_law_sha256"] = batch.canonical_sha256({
                key: item
                for key, item in body.items()
                if key != "generation_cross_fit_law_sha256"
            })
        else:
            body["this_contract_opens_outcome_access"] = True
            body["aggregate_pre_grade_law_sha256"] = batch.canonical_sha256({
                key: item
                for key, item in body.items()
                if key != "aggregate_pre_grade_law_sha256"
            })
        return body

    monkeypatch.setattr(companion, helper, changed)
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match=expected_match,
    ):
        _build(inputs)


def test_same_id_paired_control_implementation_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = companion._control_implementation_body  # noqa: SLF001

    def changed() -> dict[str, object]:
        body = deepcopy(original())
        body["implementation_id"] = companion.CONTROL_IMPLEMENTATION_ID
        body["discovery_matrix_hash_row_chunk_size"] = 64
        return body

    monkeypatch.setattr(companion, "_control_implementation_body", changed)
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="literal paired-control implementation hash differs",
    ):
        _build()


def test_core_retrieval_contract_same_id_drift_is_rejected_before_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _bundle()
    original = factorial._retrieval_contract  # noqa: SLF001

    def changed() -> dict[str, object]:
        contract = deepcopy(original())
        contract["catalog"][0]["strategy_contract"]["parameters"]["threshold"] = (
            195.0
        )
        strategy = contract["catalog"][0]["strategy_contract"]
        strategy.pop("strategy_sha256")
        strategy_hash = batch.canonical_sha256(strategy)
        strategy["strategy_sha256"] = strategy_hash
        contract["catalog"][0]["strategy_contract_sha256"] = strategy_hash
        contract["catalog_sha256"] = batch.canonical_sha256(contract["catalog"])
        contract.pop("retrieval_contract_sha256")
        contract["retrieval_contract_sha256"] = batch.canonical_sha256(contract)
        return contract

    monkeypatch.setattr(factorial, "_retrieval_contract", changed)
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="core factorial manifest or authoritative source replay differs",
    ):
        _build(inputs)


def test_source_catalog_and_core_manifest_splice_fails_canonical_replay() -> None:
    original_inputs = _bundle()
    retained = _build(original_inputs)
    changed_sources = _source_members()
    changed_sources[0]["ordinary_r_blocks"][0]["world_identity"] = _identity(
        "replacement-world", 777
    )
    changed_inputs = _bundle(changed_sources, catalog_generation="9002")
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="canonical replay",
    ):
        _validate(retained, changed_inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("PROTOCOL_SHA256", "1" * 64),
        ("CENSUS_SHA256", "2" * 64),
        ("HARD230_CONTROL_ID", "hard-230-latest-control"),
        ("DISCOVERY_CONTROL_ID", "discovery-latest-control"),
        ("CONTROL_IMPLEMENTATION_ID", "latest-control-implementation"),
        ("PROSPECTIVE_K20_OI_SHADOW_ID", "latest-shadow"),
    ],
)
def test_protocol_and_stable_id_constant_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    inputs = _bundle()
    monkeypatch.setattr(companion, field, value)
    with pytest.raises(
        companion.CorpusExtremeTailGenerationCompanionManifestError,
        match="frozen 18-row core factorial dependency differs",
    ):
        _build(inputs)


def test_no_manifest_level_outcome_publication_or_production_authority() -> None:
    value = _build()
    for field in companion._FALSE_AUTHORITY_FIELDS:  # noqa: SLF001
        assert value[field] is False
    assert value["aggregate_pre_grade_catalog_contract"][
        "this_contract_grants_publication_or_promotion_authority"
    ] is False
    assert value["aggregate_pre_grade_catalog_contract"][
        "separate_final_grade_manifest_required"
    ] is True
    assert value["source_lineage_contract"]["uses_realized_outcomes"] is False
