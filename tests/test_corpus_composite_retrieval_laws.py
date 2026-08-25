from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import corpus_composite_retrieval_laws as composite
from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as t230
from nfl_dfs.research.corpus_legal_feasibility import (
    canonical_json_bytes,
    canonical_sha256,
)


WIDTH = 6


def _ids(count: int = 100) -> list[str]:
    return [f"lineup-{index:03d}" for index in range(count)]


def _scores(count: int = 100) -> np.ndarray:
    values = np.full(
        (count, len(composite.WORLD_BLOCKS) * WIDTH),
        180.0,
        dtype=np.float64,
    )
    for index in range(count):
        for block in range(len(composite.WORLD_BLOCKS)):
            start = block * WIDTH
            values[index, start + index % WIDTH] = 210.0 + (index % 5) * 10.0
            values[index, start + (index * 3 + 1) % WIDTH] = 231.0
    return np.ascontiguousarray(values)


class _ExactStore:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.next_generation = 100
        self.source_artifacts: dict[str, dict[str, object]] = {}
        self.source_binding: dict[str, object] = {}
        self.producers: dict[str, dict[str, object]] = {}

    def put_raw(
        self, name: str, raw: bytes, *, generation: int | None = None
    ) -> dict[str, object]:
        if generation is None:
            self.next_generation += 1
            generation = self.next_generation
        uri = f"gs://fixture/{name}"
        identity = {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        key = (uri, str(generation))
        assert key not in self.objects
        self.objects[key] = raw
        return identity

    def put_json(
        self, name: str, body: dict[str, object], *, generation: int | None = None
    ) -> dict[str, object]:
        return self.put_raw(name, canonical_json_bytes(body), generation=generation)

    def read(self, identity: Mapping[str, object]) -> bytes:
        return self.objects[(str(identity["uri"]), str(identity["generation"]))]

    def json(self, identity: Mapping[str, object]) -> dict[str, object]:
        return composite._parse_canonical_json(
            self.read(identity), label="fixture object"
        )

    def vector(
        self, identity: Mapping[str, object]
    ) -> tuple[dict[str, object], np.ndarray]:
        raw = self.read(identity)
        metadata_raw, separator, payload = raw.partition(b"\0")
        assert separator == b"\0"
        metadata = composite._parse_canonical_json(
            metadata_raw, label="fixture vector metadata"
        )
        return metadata, np.frombuffer(payload, dtype="<f8").copy()


def _store(inputs: Mapping[str, object]) -> _ExactStore:
    store = inputs["read_exact"].__self__
    assert isinstance(store, _ExactStore)
    return store


def _object(
    name: str, digit: str, *, generation: int = 101
) -> dict[str, object]:
    return {
        "uri": f"gs://upstream-outcomes/{name}",
        "generation": str(generation),
        "sha256": digit * 64,
        "bytes": 1000 + generation,
    }


def _source_authority(
    ids: list[str], scores: np.ndarray, store: _ExactStore
) -> tuple[dict[str, object], dict[str, object]]:
    lineup_hash = canonical_sha256(ids)
    matrix_body = {
        "schema_version": composite.SOURCE_MATRIX_SCHEMA,
        "matrix_id": "ordinary-r0-r4-matrix-v1",
        "lineup_ids_sha256": lineup_hash,
        "full_score_matrix_sha256": composite._matrix_sha256(scores, lineup_hash),
        "full_score_shape": list(scores.shape),
        "dtype": "float64-le",
        "column_order": "R0-R1-R2-R3-R4-block-major-world-index",
        "world_block_registry": list(composite.WORLD_BLOCKS),
        "worlds_per_block": WIDTH,
    }
    matrix_identity = store.put_raw(
        "scores.bin",
        composite._matrix_artifact_payload_bytes(matrix_body, scores),
        generation=202,
    )
    mask_body = {
        "schema_version": composite.SOURCE_MASK_SCHEMA,
        "candidate_mask_id": "accepted-candidate-mask-v1",
        "selected_lineup_ids": ids,
        "lineup_ids_sha256": lineup_hash,
        "candidate_count": len(ids),
        "candidate_mask_sha256": canonical_sha256({
            "schema_version": "canonical-composite-candidate-mask-content/v1",
            "selected_lineup_ids": ids,
        }),
    }
    mask_identity = store.put_json("mask.json", mask_body, generation=203)
    occurrences = [
        {"lineup_id": lineup_id, "occurrence_count": index % 3}
        for index, lineup_id in enumerate(ids)
    ]
    occurrence_body = {
        "schema_version": composite.SOURCE_OCCURRENCE_SCHEMA,
        "occurrence_artifact_id": "accepted-occurrence-lineage-v1",
        "lineup_occurrences": occurrences,
        "lineup_ids_sha256": lineup_hash,
        "occurrence_lineage_sha256": canonical_sha256({
            "schema_version": "canonical-composite-occurrence-content/v1",
            "lineup_occurrences": occurrences,
        }),
    }
    occurrence_identity = store.put_json(
        "occurrences.json", occurrence_body, generation=204
    )
    member_body = {
        "schema_version": composite.SOURCE_MEMBER_SCHEMA,
        "member_id": "2023-w01",
        "member_ordinal": 0,
        "slate_id": "2023-w01",
        "lineup_ids_sha256": lineup_hash,
        "score_matrix_artifact_identity": matrix_identity,
        "candidate_mask_artifact_identity": mask_identity,
        "occurrence_artifact_identity": occurrence_identity,
    }
    member_identity = store.put_json("member.json", member_body, generation=205)
    manifest_body = {
        "schema_version": composite.SOURCE_MANIFEST_SCHEMA,
        "manifest_id": "accepted-five-block-manifest-v1",
        "member_count": 1,
        "member_receipt_identities": [member_identity],
    }
    manifest_identity = store.put_json(
        "manifest.json", manifest_body, generation=206
    )
    lock = composite.build_fixture_composite_authority_lock_v1(
        source_manifest_receipt_identity=manifest_identity,
        source_member_receipt_identity=member_identity,
    )
    lock_identity = store.put_json("source-authority-lock.json", lock, generation=207)
    replayed_lock, _identity = composite._replay_composite_authority_lock(
        lock_identity,
        read_exact=store.read,
        execution_mode="fixture",
    )
    source, _pointers = composite._replay_authoritative_source_artifacts(
        replayed_lock,
        read_exact=store.read,
        lineup_ids=ids,
        full_scores=scores,
        worlds_per_block=WIDTH,
    )
    store.source_artifacts = {
        "matrix": matrix_identity,
        "mask": mask_identity,
        "occurrence": occurrence_identity,
        "member": member_identity,
        "manifest": manifest_identity,
        "source_lock": lock_identity,
    }
    store.source_binding = source
    return source, lock_identity


def _base(*, scores: np.ndarray | None = None) -> dict[str, object]:
    ids = _ids()
    retained_scores = _scores() if scores is None else scores
    store = _ExactStore()
    _source, lock_identity = _source_authority(ids, retained_scores, store)
    substrate = composite.build_canonical_substrate_receipt_v1(
        lineup_ids=ids,
        full_scores=retained_scores,
        worlds_per_block=WIDTH,
        execution_mode="fixture",
        authority_lock_identity=lock_identity,
        read_exact=store.read,
    )
    return {
        "lineup_ids": ids,
        "full_scores": retained_scores,
        "worlds_per_block": WIDTH,
        "execution_mode": "fixture",
        "authority_lock_identity": lock_identity,
        "substrate_receipt": substrate,
        "read_exact": store.read,
    }


def _producer_contract(source: str) -> dict[str, str]:
    digits = {
        "simulated_tail_support": ("1", "2", "3", "4"),
        "realized_tail_posterior": ("5", "6", "7", "8"),
        "winner_topology_support": ("9", "a", "b", "c"),
        "novelty_residual_support": ("d", "e", "f", "0"),
    }[source]
    return {
        "producer_id": f"{source}-producer",
        "producer_version": "v1",
        "producer_implementation_sha256": digits[0] * 64,
        "producer_executable_sha256": digits[1] * 64,
        "fit_callable_sha256": digits[2] * 64,
        "predict_callable_sha256": digits[3] * 64,
    }


def _vector_artifact_identity(
    *,
    base: dict[str, object],
    source: str,
    contract: dict[str, str],
    values: np.ndarray,
    role: str,
    fold_id: str | None,
    generation: int,
    training_outcome_member_binding_sha256: str | None = None,
    heldout_outcome_member_binding_sha256: str | None = None,
    heldout_member_ids_sha256: str | None = None,
) -> dict[str, object]:
    store = _store(base)
    lineup_hash = canonical_sha256(base["lineup_ids"])
    metadata = {
        "schema_version": composite.VECTOR_ARTIFACT_SCHEMA,
        "source": source,
        "artifact_role": role,
        "fold_id": fold_id,
        "lineup_ids_sha256": lineup_hash,
        "substrate_receipt_sha256": base["substrate_receipt"][
            "substrate_receipt_sha256"
        ],
        "producer_contract_sha256": canonical_sha256(contract),
        "training_outcome_member_binding_sha256": (
            training_outcome_member_binding_sha256
        ),
        "heldout_outcome_member_binding_sha256": (
            heldout_outcome_member_binding_sha256
        ),
        "heldout_member_ids_sha256": heldout_member_ids_sha256,
        "vector_length": len(base["lineup_ids"]),
        "vector_sha256": composite._vector_sha256(values, lineup_hash),
    }
    payload = composite._vector_artifact_payload_bytes(metadata, values)
    name = f"{source}-{fold_id or 'static'}.bin"
    return store.put_raw(name, payload, generation=generation)


def _outcome_registry() -> list[dict[str, object]]:
    return [
        {
            "member_id": f"season-{season}",
            "outcome_object_identity": _object(
                f"actuals-{season}.parquet", str(index + 1), generation=300 + index
            ),
        }
        for index, season in enumerate((2022, 2023, 2024, 2025))
    ]


def _outer_folds(source: str, count: int = 100) -> list[dict[str, object]]:
    index = np.arange(count, dtype=np.float64)
    if source == "realized_tail_posterior":
        left = index / count
        right = (index[::-1] + 3.0) / count
    else:
        left = ((index * 17) % count) / count
        right = ((index * 31 + 7) % count) / count
    return [
        {
            "fold_id": "outer-0",
            "heldout_member_ids": ["season-2022", "season-2023"],
            "prediction_values": np.ascontiguousarray(left),
        },
        {
            "fold_id": "outer-1",
            "heldout_member_ids": ["season-2024", "season-2025"],
            "prediction_values": np.ascontiguousarray(right),
        },
    ]


def _support_inputs(
    base: dict[str, object], *, equal: bool = False
) -> dict[str, object]:
    ids = base["lineup_ids"]
    store = _store(base)
    count = len(ids)
    index = np.arange(count, dtype=np.float64)
    pins: dict[str, dict[str, object]] = {}
    details: dict[str, dict[str, object]] = {}
    for source_ordinal, source in enumerate(composite.SUPPORT_SOURCE_ORDER):
        contract = _producer_contract(source)
        contract_identity = store.put_json(
            f"{source}-contract.json", contract,
            generation=350 + source_ordinal,
        )
        if source in composite.OUTCOME_AWARE_SUPPORT_SOURCES:
            folds = _outer_folds(source, count)
            if equal:
                for fold in folds:
                    fold["prediction_values"] = np.ones(count, dtype=np.float64)
            registry = _outcome_registry()
            registry_identity = store.put_json(
                f"{source}-outcome-registry.json",
                {
                    "schema_version": "outer-crossfit-outcome-member-registry/v1",
                    "outcome_members": registry,
                },
                generation=370 + source_ordinal,
            )
            registry_by_member = {row["member_id"]: row for row in registry}
            registry_ids = [row["member_id"] for row in registry]
            prediction_identities = []
            outer_inputs = []
            for fold_ordinal, fold in enumerate(folds):
                heldout_binding = canonical_sha256([
                    registry_by_member[member]
                    for member in fold["heldout_member_ids"]
                ])
                artifact_identity = _vector_artifact_identity(
                    base=base,
                    source=source,
                    contract=contract,
                    values=fold["prediction_values"],
                    role="outer-fold-prediction",
                    fold_id=fold["fold_id"],
                    generation=400 + source_ordinal * 10 + fold_ordinal,
                    training_outcome_member_binding_sha256=canonical_sha256([
                        registry_by_member[member]
                        for member in registry_ids
                        if member not in set(fold["heldout_member_ids"])
                    ]),
                    heldout_outcome_member_binding_sha256=heldout_binding,
                    heldout_member_ids_sha256=canonical_sha256(
                        fold["heldout_member_ids"]
                    ),
                )
                prediction_identities.append(artifact_identity)
                outer_inputs.append({
                    "fold_id": fold["fold_id"],
                    "heldout_member_ids": fold["heldout_member_ids"],
                    "prediction_artifact_identity": artifact_identity,
                })
            receipt = composite.build_outer_crossfit_support_producer_receipt_v1(
                source=source,
                lineup_ids=ids,
                substrate_receipt=base["substrate_receipt"],
                producer_contract_identity=contract_identity,
                outcome_member_registry_identity=registry_identity,
                outer_fold_inputs=outer_inputs,
                read_exact=store.read,
            )
            receipt_identity = store.put_json(
                f"{source}-producer-receipt.json",
                receipt,
                generation=500 + source_ordinal,
            )
            details[source] = {
                "producer_receipt_identity": receipt_identity,
                "producer_contract_identity": contract_identity,
                "outcome_member_registry_identity": registry_identity,
                "prediction_artifact_identities": prediction_identities,
            }
        else:
            values = (
                np.ones(count, dtype=np.float64)
                if equal
                else (
                    np.ascontiguousarray(index)
                    if source == "simulated_tail_support"
                    else np.ascontiguousarray((index * 13) % count)
                )
            )
            vector_identity = _vector_artifact_identity(
                base=base,
                source=source,
                contract=contract,
                values=values,
                role="static-support-vector",
                fold_id=None,
                generation=400 + source_ordinal * 10,
            )
            receipt = composite.build_static_support_producer_receipt_v1(
                source=source,
                vector_artifact_identity=vector_identity,
                lineup_ids=ids,
                substrate_receipt=base["substrate_receipt"],
                producer_contract_identity=contract_identity,
                read_exact=store.read,
            )
            receipt_identity = store.put_json(
                f"{source}-producer-receipt.json",
                receipt,
                generation=500 + source_ordinal,
            )
            details[source] = {
                "producer_receipt_identity": receipt_identity,
                "producer_contract_identity": contract_identity,
                "vector_artifact_identity": vector_identity,
            }
        pins[source] = deepcopy(receipt_identity)
    store.producers = details
    lock = composite.build_fixture_producer_authority_lock_v1(
        source_authority_lock_identity=base["authority_lock_identity"],
        substrate_receipt_sha256=base["substrate_receipt"][
            "substrate_receipt_sha256"
        ],
        producer_receipt_identities=pins,
    )
    return store.put_json("producer-authority-lock.json", lock, generation=550)


def _hybrid_inputs(
    *, equal: bool = False, scores: np.ndarray | None = None
) -> dict[str, object]:
    base = _base(scores=scores)
    producer_lock_identity = _support_inputs(base, equal=equal)
    return {
        **base,
        "heldout_block": "R4",
        "producer_authority_lock_identity": producer_lock_identity,
    }


def _upstream_receipts(base: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        strategy_id: composite.build_upstream_selector_result_receipt_v1(
            strategy_id=strategy_id,
            lineup_ids=base["lineup_ids"],
            full_scores=base["full_scores"],
            heldout_block="R4",
            worlds_per_block=WIDTH,
            execution_mode="fixture",
            authority_lock_identity=base["authority_lock_identity"],
            substrate_receipt=base["substrate_receipt"],
            read_exact=base["read_exact"],
        )
        for strategy_id in composite.ENSEMBLE_SOURCE_ORDER
    }


def _ensemble_inputs() -> dict[str, object]:
    base = _base()
    return {
        **base,
        "heldout_block": "R4",
        "upstream_selector_receipts": _upstream_receipts(base),
    }


def _rehash(value: dict[str, object], field: str) -> None:
    value[field] = canonical_sha256({
        key: item for key, item in value.items() if key != field
    })


def _rehash_outer(receipt: dict[str, object]) -> None:
    for fold in receipt["outer_folds"]:
        _rehash(fold, "outer_fold_sha256")
    receipt["outer_folds_sha256"] = canonical_sha256(receipt["outer_folds"])
    _rehash(receipt, "producer_receipt_sha256")


def _rehash_upstream(receipt: dict[str, object]) -> None:
    fit = receipt["fit_scope_binding"]
    _rehash(fit, "fit_scope_binding_sha256")
    receipt["fit_scope_binding_sha256"] = fit["fit_scope_binding_sha256"]
    receipt["selected_lineup_ids_sha256"] = canonical_sha256(
        receipt["selected_lineup_ids"]
    )
    receipt["selection_trace_sha256"] = canonical_sha256(
        receipt["selection_trace"]
    )
    for book in receipt["books"]:
        budget = book["entry_budget"]
        book["selected_lineup_ids"] = receipt["selected_lineup_ids"][:budget]
        book["selected_lineup_ids_sha256"] = canonical_sha256(
            book["selected_lineup_ids"]
        )
        _rehash(book, "book_sha256")
    _rehash(receipt, "upstream_result_sha256")


def _publish_vector(
    store: _ExactStore,
    name: str,
    metadata: dict[str, object],
    values: np.ndarray,
    *,
    generation: int,
) -> dict[str, object]:
    metadata["vector_sha256"] = composite._vector_sha256(
        values, str(metadata["lineup_ids_sha256"])
    )
    return store.put_raw(
        name,
        composite._vector_artifact_payload_bytes(metadata, values),
        generation=generation,
    )


def test_literal_hashes_bind_executable_sources_and_public_dependencies() -> None:
    implementation = composite.frozen_composite_retrieval_implementation_v1()
    assert implementation["implementation_sha256"] == (
        "d2d30be6df6732b40d32bdb99cb11cd5f70b9c7725c43bf261825c3ac6827e3a"
    )
    assert implementation["local_executable_callables"]
    assert implementation["external_executable_callables"]
    assert implementation["dependency_module_executable_identities"]
    assert implementation["contract_constant_registry"][
        "producer_authority_lock_schema"
    ] == composite.PRODUCER_AUTHORITY_LOCK_SCHEMA
    local_names = {
        row["logical_name"] for row in implementation["local_executable_callables"]
    }
    assert {
        "_validated_full_matrix",
        "_read_exact_bytes",
        "_replay_composite_authority_lock",
        "_replay_producer_authority_lock",
        "_replay_matrix_artifact",
        "_source_binding",
        "validate_canonical_substrate_receipt_v1",
        "_outer_fold_inputs",
        "_aggregate_outer_predictions",
        "_fit_view",
        "_public_strategy_contracts",
        "_books",
        "_support_vectors_from_replayed_producers",
        "validate_static_support_producer_receipt_v1",
        "validate_outer_crossfit_support_producer_receipt_v1",
        "validate_upstream_selector_result_receipt_v1",
        "_guard_literal_contracts",
        "_module_executable_identity",
    }.issubset(local_names)
    registry = composite.frozen_composite_retrieval_registry_v1()
    assert [row["strategy_sha256"] for row in registry] == [
        "02c0279c7e13d6437ecfbb3a8027bca6db796feca6ddfd9e91e203db5779b8cd",
        "ec52a2e34ad09a7ba7b49a4515c76a2dabb85c50e90b62c79e53eb432d261500",
    ]
    assert registry[0]["set_objective_sha256"] == (
        composite.FROZEN_SET_OBJECTIVE_SHA256
    )
    assert registry[1]["selector_source_identities"] == (
        composite.ENSEMBLE_SOURCE_IDENTITIES
    )


def test_substrate_replays_all_five_blocks_and_fixture_release_gate() -> None:
    base = _base()
    store = _store(base)
    receipt = base["substrate_receipt"]
    assert receipt["world_block_registry"] == ["R0", "R1", "R2", "R3", "R4"]
    assert receipt["column_order"] == "R0-R1-R2-R3-R4-block-major-world-index"
    assert receipt["fixture_only_not_release_authority"] is True
    fit = receipt["upstream_all_block_fit_scope"]
    assert fit["training_blocks"] == ["R0", "R1", "R2", "R3", "R4"]
    assert fit["source_manifest_identity"] == store.source_binding[
        "source_manifest_identity"
    ]
    assert fit["source_member_identity"] == store.source_binding[
        "source_member_identity"
    ]
    assert composite.validate_canonical_substrate_receipt_v1(
        receipt,
        lineup_ids=base["lineup_ids"],
        full_scores=base["full_scores"],
        worlds_per_block=WIDTH,
        execution_mode="fixture",
        authority_lock_identity=base["authority_lock_identity"],
        read_exact=store.read,
    ) == receipt
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="release mode requires exact production",
    ):
        composite.build_canonical_substrate_receipt_v1(
            lineup_ids=base["lineup_ids"],
            full_scores=base["full_scores"],
            worlds_per_block=WIDTH,
            execution_mode="release",
            authority_lock_identity=base["authority_lock_identity"],
            read_exact=store.read,
        )


def test_hybrid_replays_outer_folds_raw_t230_and_exact_prefixes() -> None:
    inputs = _hybrid_inputs()
    receipt = composite.build_hybrid_support_retrieval_v1(**inputs)
    assert receipt["training_blocks"] == ["R0", "R1", "R2", "R3"]
    assert receipt["heldout_block"] == "R4"
    assert receipt["set_objective_rungs"] == [
        {"threshold": 210.0, "operator": ">=", "weight": 1},
        {"threshold": 220.0, "operator": ">=", "weight": 2},
        {"threshold": 230.0, "operator": ">=", "weight": 4},
        {"threshold": 240.0, "operator": ">=", "weight": 8},
        {"threshold": 250.0, "operator": ">=", "weight": 16},
    ]
    assert len(receipt["selected_lineup_ids"]) == 80
    assert len(set(receipt["selected_lineup_ids"])) == 80
    assert receipt[
        "consumes_historically_outcome_derived_outer_crossfit_evidence"
    ] is True
    assert receipt["uses_no_raw_or_current_heldout_outcomes"] is True
    store = _store(inputs)
    for source in composite.OUTCOME_AWARE_SUPPORT_SOURCES:
        producer = store.json(
            store.producers[source]["producer_receipt_identity"]
        )
        assert producer["outer_fold_count"] == 2
        for fold in producer["outer_folds"]:
            assert set(fold["training_member_ids"]).isdisjoint(
                fold["heldout_member_ids"]
            )
            assert sorted(
                fold["training_member_ids"] + fold["heldout_member_ids"]
            ) == ["season-2022", "season-2023", "season-2024", "season-2025"]
    for book in receipt["books"]:
        budget = book["entry_budget"]
        assert book["selected_lineup_ids"] == receipt["selected_lineup_ids"][:budget]
    assert composite.validate_hybrid_support_retrieval_v1(
        receipt, **inputs
    ) == receipt


def test_hybrid_complete_sleeve_overlap_supplements_exactly_to_80() -> None:
    scores = np.full_like(_scores(), 230.0)
    inputs = _hybrid_inputs(equal=True, scores=scores)
    receipt = composite.build_hybrid_support_retrieval_v1(**inputs)
    assert all(
        row["selected_lineup_ids"] == inputs["lineup_ids"][:20]
        for row in receipt["sleeves"]
    )
    assert receipt["supplement_lineup_ids"] == inputs["lineup_ids"][20:80]
    assert receipt["shortlist_lineup_ids"] == inputs["lineup_ids"][:80]
    assert receipt["selected_lineup_ids"] == inputs["lineup_ids"][:80]


def test_hybrid_missing_producer_fails_without_renormalization() -> None:
    inputs = _hybrid_inputs()
    store = _store(inputs)
    lock = store.json(inputs["producer_authority_lock_identity"])
    lock["producer_receipt_identities"].pop("winner_topology_support")
    _rehash(lock, "producer_authority_lock_sha256")
    altered_identity = store.put_json(
        "producer-authority-lock-missing.json", lock, generation=9000
    )
    with pytest.raises(composite.CorpusCompositeRetrievalError, match="exactly four"):
        composite.build_hybrid_support_retrieval_v1(**{
            **inputs,
            "producer_authority_lock_identity": altered_identity,
        })


def test_coherently_rehashed_outer_fold_training_leak_fails_replay() -> None:
    inputs = _hybrid_inputs()
    store = _store(inputs)
    detail = store.producers["realized_tail_posterior"]
    receipt = store.json(detail["producer_receipt_identity"])
    receipt["outer_folds"][0]["training_member_ids"].append("season-2022")
    receipt["outer_folds"][0]["training_member_ids"].sort()
    _rehash_outer(receipt)
    altered_receipt_identity = store.put_json(
        "realized-tail-training-leak-receipt.json", receipt, generation=9001
    )
    producer_lock = store.json(inputs["producer_authority_lock_identity"])
    producer_pins = deepcopy(producer_lock["producer_receipt_identities"])
    producer_pins["realized_tail_posterior"] = altered_receipt_identity
    altered_lock = composite.build_fixture_producer_authority_lock_v1(
        source_authority_lock_identity=inputs["authority_lock_identity"],
        substrate_receipt_sha256=inputs["substrate_receipt"][
            "substrate_receipt_sha256"
        ],
        producer_receipt_identities=producer_pins,
    )
    altered_lock_identity = store.put_json(
        "producer-authority-lock-training-leak.json", altered_lock, generation=9002
    )
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="outer-crossfit producer receipt replay differs",
    ):
        composite.build_hybrid_support_retrieval_v1(**{
            **inputs,
            "producer_authority_lock_identity": altered_lock_identity,
        })


def test_coherent_leaked_vector_and_newly_built_receipt_cannot_mint_release_lock() -> None:
    inputs = _hybrid_inputs()
    store = _store(inputs)
    source = "winner_topology_support"
    detail = store.producers[source]
    original = store.json(detail["producer_receipt_identity"])
    prediction_identities = list(detail["prediction_artifact_identities"])
    metadata, values = store.vector(prediction_identities[0])
    values[0] += 10_000.0
    prediction_identities[0] = _publish_vector(
        store, "coherent-leaked-vector.bin", metadata, values, generation=9010
    )
    by_fold = {
        str(store.vector(identity)[0]["fold_id"]): identity
        for identity in prediction_identities
    }
    rebuilt = composite.build_outer_crossfit_support_producer_receipt_v1(
        source=source,
        lineup_ids=inputs["lineup_ids"],
        substrate_receipt=inputs["substrate_receipt"],
        producer_contract_identity=original["producer_contract_identity"],
        outcome_member_registry_identity=original[
            "outcome_member_registry_identity"
        ],
        outer_fold_inputs=[
            {
                "fold_id": fold["fold_id"],
                "heldout_member_ids": fold["heldout_member_ids"],
                "prediction_artifact_identity": by_fold[fold["fold_id"]],
            }
            for fold in original["outer_folds"]
        ],
        read_exact=store.read,
    )
    rebuilt_identity = store.put_json(
        "winner-topology-rebuilt-receipt.json", rebuilt, generation=9011
    )
    pins = deepcopy(
        store.json(inputs["producer_authority_lock_identity"])[
            "producer_receipt_identities"
        ]
    )
    pins[source] = rebuilt_identity
    forged_release_lock = composite._producer_authority_lock_body(
        authority_mode="release",
        source_authority_lock_identity=inputs["authority_lock_identity"],
        substrate_receipt_sha256=inputs["substrate_receipt"][
            "substrate_receipt_sha256"
        ],
        producer_receipt_identities=pins,
    )
    forged_lock_identity = store.put_json(
        "forged-release-producer-lock.json", forged_release_lock, generation=9012
    )
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="no reviewed release producer authority lock identity is frozen",
    ):
        composite._replay_producer_authority_lock(
            forged_lock_identity,
            source_authority_lock_identity=inputs["authority_lock_identity"],
            substrate_receipt_sha256=inputs["substrate_receipt"][
                "substrate_receipt_sha256"
            ],
            read_exact=store.read,
            execution_mode="release",
        )


def test_coherent_outcome_lineage_and_new_receipt_cannot_mint_release_lock() -> None:
    inputs = _hybrid_inputs()
    store = _store(inputs)
    source = "realized_tail_posterior"
    detail = store.producers[source]
    original = store.json(detail["producer_receipt_identity"])
    registry = deepcopy(original["outcome_member_registry"])
    registry[0]["outcome_object_identity"]["generation"] = "9999"
    registry_identity = store.put_json(
        "drifted-outcome-registry.json",
        {
            "schema_version": "outer-crossfit-outcome-member-registry/v1",
            "outcome_members": registry,
        },
        generation=9020,
    )
    by_member = {row["member_id"]: row for row in registry}
    member_ids = [row["member_id"] for row in registry]
    outer_inputs = []
    for ordinal, fold in enumerate(original["outer_folds"]):
        heldout = fold["heldout_member_ids"]
        metadata, values = store.vector(
            detail["prediction_artifact_identities"][ordinal]
        )
        metadata[
            "training_outcome_member_binding_sha256"
        ] = canonical_sha256([
            by_member[member]
            for member in member_ids
            if member not in set(heldout)
        ])
        metadata["heldout_outcome_member_binding_sha256"] = canonical_sha256([
            by_member[member] for member in heldout
        ])
        artifact_identity = _publish_vector(
            store,
            f"drifted-outcome-vector-{ordinal}.bin",
            metadata,
            values,
            generation=9021 + ordinal,
        )
        outer_inputs.append({
            "fold_id": fold["fold_id"],
            "heldout_member_ids": heldout,
            "prediction_artifact_identity": artifact_identity,
        })
    rebuilt = composite.build_outer_crossfit_support_producer_receipt_v1(
        source=source,
        lineup_ids=inputs["lineup_ids"],
        substrate_receipt=inputs["substrate_receipt"],
        producer_contract_identity=original["producer_contract_identity"],
        outcome_member_registry_identity=registry_identity,
        outer_fold_inputs=outer_inputs,
        read_exact=store.read,
    )
    rebuilt_identity = store.put_json(
        "realized-tail-drifted-lineage-receipt.json", rebuilt, generation=9024
    )
    pins = deepcopy(
        store.json(inputs["producer_authority_lock_identity"])[
            "producer_receipt_identities"
        ]
    )
    pins[source] = rebuilt_identity
    forged_release_lock = composite._producer_authority_lock_body(
        authority_mode="release",
        source_authority_lock_identity=inputs["authority_lock_identity"],
        substrate_receipt_sha256=inputs["substrate_receipt"][
            "substrate_receipt_sha256"
        ],
        producer_receipt_identities=pins,
    )
    forged_lock_identity = store.put_json(
        "forged-outcome-release-lock.json", forged_release_lock, generation=9025
    )
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="no reviewed release producer authority lock identity is frozen",
    ):
        composite._replay_producer_authority_lock(
            forged_lock_identity,
            source_authority_lock_identity=inputs["authority_lock_identity"],
            substrate_receipt_sha256=inputs["substrate_receipt"][
                "substrate_receipt_sha256"
            ],
            read_exact=store.read,
            execution_mode="release",
        )


def test_coherent_rebuilt_source_binding_cannot_mint_release_lock() -> None:
    inputs = _hybrid_inputs()
    store = _store(inputs)
    member = store.json(store.source_artifacts["member"])
    member["slate_id"] = "2023-w02"
    member_identity = store.put_json(
        "rebuilt-member.json", member, generation=9030
    )
    manifest = store.json(store.source_artifacts["manifest"])
    manifest["member_receipt_identities"] = [member_identity]
    manifest_identity = store.put_json(
        "rebuilt-manifest.json", manifest, generation=9031
    )
    forged_release_lock = composite._authority_lock_body(
        authority_mode="release",
        source_manifest_receipt_identity=manifest_identity,
        source_member_receipt_identity=member_identity,
    )
    forged_lock_identity = store.put_json(
        "forged-release-source-lock.json", forged_release_lock, generation=9032
    )
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="no reviewed release authority lock identity is frozen",
    ):
        composite._replay_composite_authority_lock(
            forged_lock_identity,
            read_exact=store.read,
            execution_mode="release",
        )


def test_ensemble_replays_four_exact_public_results_and_prefixes() -> None:
    inputs = _ensemble_inputs()
    receipt = composite.build_fixed_selector_ensemble_v1(**inputs)
    assert [row["strategy_id"] for row in receipt["upstream_result_pointers"]] == list(
        composite.ENSEMBLE_SOURCE_ORDER
    )
    assert all(
        row["replay_tier"] == "exact-public-executable-replay"
        for row in receipt["upstream_result_pointers"]
        if row["strategy_id"] != "block-robust-bounded-tail-ge-210-250-v1"
    )
    block = receipt["upstream_result_pointers"][2]
    assert block["replay_tier"] == "fixture-reference-replay-not-release-authority"
    assert receipt["missing_source_law"] == "fail-closed-no-weight-renormalization"
    assert len(receipt["selected_lineup_ids"]) == 80
    for book in receipt["books"]:
        budget = book["entry_budget"]
        assert book["selected_lineup_ids"] == receipt["selected_lineup_ids"][:budget]
    assert composite.validate_fixed_selector_ensemble_v1(
        receipt, **inputs
    ) == receipt


def test_ensemble_missing_receipt_fails_without_renormalization() -> None:
    inputs = _ensemble_inputs()
    receipts = deepcopy(inputs["upstream_selector_receipts"])
    receipts.pop("coverage-ge-230-v1")
    with pytest.raises(composite.CorpusCompositeRetrievalError, match="all four"):
        composite.build_fixed_selector_ensemble_v1(
            **{**inputs, "upstream_selector_receipts": receipts}
        )


def test_coherently_rehashed_arbitrary_upstream_rank_fails_exact_replay() -> None:
    inputs = _ensemble_inputs()
    receipts = deepcopy(inputs["upstream_selector_receipts"])
    receipt = receipts["coverage-ge-230-v1"]
    receipt["selected_lineup_ids"][0], receipt["selected_lineup_ids"][1] = (
        receipt["selected_lineup_ids"][1],
        receipt["selected_lineup_ids"][0],
    )
    receipt["selection_trace"][0], receipt["selection_trace"][1] = (
        receipt["selection_trace"][1],
        receipt["selection_trace"][0],
    )
    receipt["selection_trace"][0]["selection_rank"] = 0
    receipt["selection_trace"][1]["selection_rank"] = 1
    _rehash_upstream(receipt)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="upstream selector result receipt replay differs",
    ):
        composite.build_fixed_selector_ensemble_v1(
            **{**inputs, "upstream_selector_receipts": receipts}
        )


def test_same_strategy_id_with_drifted_hash_fails_exact_replay() -> None:
    inputs = _ensemble_inputs()
    receipts = deepcopy(inputs["upstream_selector_receipts"])
    receipt = receipts["bounded-tail-ladder-ge-210-250-v1"]
    receipt["strategy_sha256"] = "0" * 64
    receipt["implementation_sha256"] = "1" * 64
    _rehash_upstream(receipt)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="upstream selector result receipt replay differs",
    ):
        composite.build_fixed_selector_ensemble_v1(
            **{**inputs, "upstream_selector_receipts": receipts}
        )


def test_coherently_rehashed_upstream_fit_scope_leak_fails_replay() -> None:
    inputs = _ensemble_inputs()
    receipts = deepcopy(inputs["upstream_selector_receipts"])
    receipt = receipts["convex-excess-expected-max-ge-200-v1"]
    receipt["fit_scope_binding"]["training_blocks"].append("R4")
    _rehash_upstream(receipt)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="upstream selector result receipt replay differs",
    ):
        composite.build_fixed_selector_ensemble_v1(
            **{**inputs, "upstream_selector_receipts": receipts}
        )


def test_borda_exact_equalities_use_final_lineup_id_tie() -> None:
    ids = _ids()
    common = ids[:80]
    ranks = {}
    for offset, source in enumerate(composite.ENSEMBLE_SOURCE_ORDER):
        rotation = offset * 20
        ranks[source] = common[rotation:] + common[:rotation]
    selected, trace = composite._borda_rank(lineup_ids=ids, ranks=ranks)
    assert selected[:4] == [ids[0], ids[20], ids[40], ids[60]]
    assert len({row["borda_points"] for row in trace[:4]}) == 1
    assert all(row["source_rank_presence_count"] == 4 for row in trace)


def _drifted_borda(*args: object, **kwargs: object) -> tuple[list[str], list[dict]]:
    return [], []


def _drifted_security_helper(*args: object, **kwargs: object) -> object:
    return None


@pytest.mark.parametrize(
    "callable_name",
    [
        "_validated_full_matrix",
        "_source_binding",
        "validate_outer_crossfit_support_producer_receipt_v1",
        "_public_strategy_contracts",
    ],
)
def test_security_critical_transitive_drift_fails_implementation_identity(
    monkeypatch, callable_name: str
) -> None:
    monkeypatch.setattr(composite, callable_name, _drifted_security_helper)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="executable implementation identity drifted",
    ):
        composite.frozen_composite_retrieval_registry_v1()


def test_local_executable_drift_fails_implementation_identity(monkeypatch) -> None:
    monkeypatch.setattr(composite, "_borda_rank", _drifted_borda)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="executable implementation identity drifted",
    ):
        composite.frozen_composite_retrieval_registry_v1()


def _drifted_ladder(*args: object, **kwargs: object) -> tuple[list[int], list[dict]]:
    return [], []


def test_upstream_executable_drift_fails_implementation_identity(monkeypatch) -> None:
    monkeypatch.setattr(t230, "_select_ladder_packed", _drifted_ladder)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="executable implementation identity drifted",
    ):
        composite.frozen_composite_retrieval_registry_v1()


def test_canonical_dependency_alias_drift_fails_implementation_identity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(composite, "canonical_sha256", _drifted_security_helper)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="executable implementation identity drifted",
    ):
        composite.frozen_composite_retrieval_registry_v1()


def test_upstream_transitive_helper_drift_fails_implementation_identity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(t230, "_packed_fresh_counts", _drifted_security_helper)
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="executable implementation identity drifted",
    ):
        composite.frozen_composite_retrieval_registry_v1()


def test_security_critical_constant_drift_fails_implementation_identity(
    monkeypatch,
) -> None:
    monkeypatch.setattr(composite, "VECTOR_ARTIFACT_SCHEMA", "drifted-vector/v999")
    with pytest.raises(
        composite.CorpusCompositeRetrievalError,
        match="executable implementation identity drifted",
    ):
        composite.frozen_composite_retrieval_registry_v1()
