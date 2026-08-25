from __future__ import annotations

from copy import deepcopy

import pytest

from nfl_dfs.research import corpus_retrieval_engine as engine
from nfl_dfs.research import (
    corpus_retrieval_v2_implementation_contract as implementation,
)
from nfl_dfs.research.corpus_legal_feasibility import canonical_sha256


EXPECTED_IMPLEMENTATION_SHA256 = (
    "01f62c080451f6d090da782c47474e86ae8302a1a57df698d2df16fb5dcffac7"
)
EXPECTED_STRATEGIES = [
    (
        "coverage-194-v1",
        "1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f",
    ),
    (
        "strict-200-coverage-v1",
        "9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de",
    ),
    (
        "tail-ladder-200-210-220-v1",
        "5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea",
    ),
    (
        "mean-score-v1",
        "5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6",
    ),
    (
        "expected-max-v1",
        "ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780",
    ),
    (
        "block-supported-tail-ladder-v1",
        "1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b",
    ),
    (
        "regime-robust-ladder-v1",
        "125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b",
    ),
]


def _contract() -> dict[str, object]:
    return implementation.frozen_retrieval_v2_implementation_contract_v1()


def _rehash_contract(value: dict[str, object]) -> None:
    value["implementation_contract_sha256"] = canonical_sha256(
        value["contract_identity"]
    )


def _callable_row(
    identity: dict[str, object], name: str
) -> dict[str, object]:
    matches = [
        row
        for row in identity["callable_sources"]
        if row["callable_name"] == name
    ]
    assert len(matches) == 1
    return matches[0]


def _assert_rejected(value: dict[str, object]) -> None:
    with pytest.raises(
        implementation.CorpusRetrievalV2ImplementationContractError
    ):
        implementation.validate_retrieval_v2_implementation_contract_v1(
            value
        )


def test_frozen_contract_exact_identity_and_public_strategy_order() -> None:
    value = _contract()
    identity = value["contract_identity"]
    assert value["implementation_contract_sha256"] == (
        EXPECTED_IMPLEMENTATION_SHA256
    )
    assert canonical_sha256(identity) == EXPECTED_IMPLEMENTATION_SHA256
    assert identity["implementation_id"] == (
        "dense-public-r6-v2-comparator-engine-v1"
    )
    assert [
        (row["strategy_id"], row["strategy_sha256"])
        for row in identity["strategy_registry"]
    ] == EXPECTED_STRATEGIES
    assert identity["canonical_registry_order"] == [
        strategy_id for strategy_id, _ in EXPECTED_STRATEGIES
    ]
    assert identity["packed_preweek_overlap"] == {
        "strategy_id": "coverage-194-v1",
        "public_dense_implementation_still_bound_here": True,
        "six_additionally_protected_strategy_ids": [
            strategy_id for strategy_id, _ in EXPECTED_STRATEGIES[1:]
        ],
    }


def test_contract_binds_exact_source_methods_laws_and_false_authority() -> None:
    identity = _contract()["contract_identity"]
    assert identity["source_module"] == {
        "logical_module_id": "nfl_dfs.research.corpus_retrieval_engine",
        "source_file_name": "corpus_retrieval_engine.py",
        "source_encoding": "utf-8",
        "source_bytes": 156_603,
        "whole_source_sha256": (
            "f69262c7468752ce40f0ae5ed55151046d4e9aacdad96fb1db6450188581c10a"
        ),
    }
    assert [row["method"] for row in identity["method_to_callable"]] == [
        "greedy-threshold-coverage-v1",
        "greedy-tail-ladder-v1",
        "rank-mean-score-v1",
        "greedy-expected-max-v1",
        "greedy-block-supported-ladder-v1",
        "greedy-blockmin-ladder-v1",
    ]
    laws = identity["execution_laws"]
    assert laws["entry_budget"] == laws["candidate_minimum"] == 80
    assert laws["world_blocks"] == ["R0", "R1", "R2", "R3", "R4"]
    assert laws["discovery_blocks"] == ["R0", "R1", "R2", "R3"]
    assert laws["heldout_blocks"] == ["R4"]
    assert laws["heldout_content_used_for_selection"] is False
    assert laws["primary_event"] == {"threshold": 200.0, "operator": ">"}
    assert laws["coverage_194_event"] == {
        "threshold": 194.0,
        "operator": ">=",
    }
    assert laws["ladder_rungs"] == [
        {"threshold": 200.0, "operator": ">", "weight": 1},
        {"threshold": 210.0, "operator": ">", "weight": 4},
        {"threshold": 220.0, "operator": ">", "weight": 12},
    ]
    assert laws["source_score_dtype"] == "<f4"
    assert laws["mean_and_expected_max_accumulator_dtype"] == "float64"
    assert laws["event_and_utility_count_dtype"] == "int64"
    assert identity["absolute_paths_are_diagnostic_only"] is True
    authority_fields = [
        key for key in identity if key.endswith("_authority")
    ]
    assert len(authority_fields) >= 10
    assert all(identity[key] is False for key in authority_fields)


def test_validator_allows_only_diagnostic_absolute_path_relocation() -> None:
    value = _contract()
    retained_hash = value["implementation_contract_sha256"]
    value["diagnostics"] = {
        "absolute_source_path": "/cloud/app/corpus_retrieval_engine.py",
        "absolute_python_executable_path": "/cloud/python/bin/python",
        "absolute_numpy_core_binary_path": "/cloud/python/numpy/core.so",
        "excluded_from_implementation_contract_sha256": True,
    }
    validated = (
        implementation.validate_retrieval_v2_implementation_contract_v1(
            value
        )
    )
    assert validated["implementation_contract_sha256"] == retained_hash
    assert validated["diagnostics"] != value["diagnostics"]


def test_coherent_strategy_registry_attack_fails_canonical_replay() -> None:
    value = deepcopy(_contract())
    identity = value["contract_identity"]
    strategy = identity["strategy_registry"][0]
    strategy["description"] = "coherently replaced implementation law"
    strategy["strategy_sha256"] = canonical_sha256(
        {
            key: item
            for key, item in strategy.items()
            if key != "strategy_sha256"
        }
    )
    identity["strategy_registry_sha256"] = canonical_sha256(
        identity["strategy_registry"]
    )
    pointer = identity["strategy_registry_pointers"][0]
    pointer["strategy_sha256"] = strategy["strategy_sha256"]
    identity["strategy_registry_pointers_sha256"] = canonical_sha256(
        identity["strategy_registry_pointers"]
    )
    _rehash_contract(value)
    _assert_rejected(value)


def test_coherent_method_to_callable_mapping_attack_fails() -> None:
    value = deepcopy(_contract())
    identity = value["contract_identity"]
    mapping = identity["method_to_callable"][0]
    replacement = _callable_row(identity, "_select_mean")
    mapping["callable"] = replacement["callable_name"]
    mapping["callable_source_sha256"] = replacement["source_sha256"]
    identity["method_to_callable_sha256"] = canonical_sha256(
        identity["method_to_callable"]
    )
    _rehash_contract(value)
    _assert_rejected(value)


@pytest.mark.parametrize("field,replacement", [
    ("source_bytes", 156_604),
    ("whole_source_sha256", "0" * 64),
])
def test_coherent_whole_source_identity_attacks_fail(
    field: str, replacement: object
) -> None:
    value = deepcopy(_contract())
    value["contract_identity"]["source_module"][field] = replacement
    _rehash_contract(value)
    _assert_rejected(value)


def test_coherent_selector_callable_source_attack_fails() -> None:
    value = deepcopy(_contract())
    identity = value["contract_identity"]
    callable_row = _callable_row(identity, "_select_mean")
    callable_row["source_bytes"] += 1
    callable_row["source_sha256"] = "1" * 64
    identity["callable_sources_sha256"] = canonical_sha256(
        identity["callable_sources"]
    )
    mapping = next(
        row
        for row in identity["method_to_callable"]
        if row["callable"] == "_select_mean"
    )
    mapping["callable_source_sha256"] = callable_row["source_sha256"]
    identity["method_to_callable_sha256"] = canonical_sha256(
        identity["method_to_callable"]
    )
    _rehash_contract(value)
    _assert_rejected(value)


@pytest.mark.parametrize(
    "callable_name,dispatch_hash_field",
    [
        ("_run_strategy", "strategy_dispatch_source_sha256"),
        (
            "_run_discovery_strategy",
            "heldout_safe_dispatch_source_sha256",
        ),
    ],
)
def test_coherent_dispatch_source_attacks_fail(
    callable_name: str, dispatch_hash_field: str
) -> None:
    value = deepcopy(_contract())
    identity = value["contract_identity"]
    callable_row = _callable_row(identity, callable_name)
    callable_row["source_sha256"] = "2" * 64
    identity["callable_sources_sha256"] = canonical_sha256(
        identity["callable_sources"]
    )
    identity["dispatch_sources"][dispatch_hash_field] = (
        callable_row["source_sha256"]
    )
    _rehash_contract(value)
    _assert_rejected(value)


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("python_version", "3.14.5"),
        ("python_executable_sha256", "3" * 64),
        ("numpy_version", "2.5.2"),
        ("numpy_core_binary_sha256", "4" * 64),
        ("platform_machine", "aarch64"),
        ("dtype_float64", ">f8"),
        ("numpy_cpu_features_true", ["SSE2"]),
    ],
)
def test_coherent_runtime_and_dependency_attacks_fail(
    field: str, replacement: object
) -> None:
    value = deepcopy(_contract())
    value["contract_identity"]["runtime_identity"][field] = replacement
    _rehash_contract(value)
    _assert_rejected(value)


def test_coherent_false_authority_attack_fails() -> None:
    value = deepcopy(_contract())
    value["contract_identity"]["publication_authority"] = True
    _rehash_contract(value)
    _assert_rejected(value)


def test_imported_registry_coherent_drift_fails_under_same_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current_registry, current_pointers = implementation._registry_evidence()
    changed_registry = deepcopy(current_registry)
    changed_pointers = deepcopy(current_pointers)
    strategy = changed_registry[1]
    strategy["description"] = "changed but self-consistent public registry"
    strategy["strategy_sha256"] = canonical_sha256(
        {
            key: item
            for key, item in strategy.items()
            if key != "strategy_sha256"
        }
    )
    changed_pointers[1]["strategy_sha256"] = strategy["strategy_sha256"]
    monkeypatch.setattr(
        implementation,
        "_registry_evidence",
        lambda: (changed_registry, changed_pointers),
    )
    with pytest.raises(
        implementation.CorpusRetrievalV2ImplementationContractError,
        match="source or strategy registry drifted",
    ):
        _contract()


@pytest.mark.parametrize("callable_name", ["_select_mean", "_run_strategy"])
def test_imported_callable_or_dispatch_replacement_fails_source_binding(
    monkeypatch: pytest.MonkeyPatch, callable_name: str
) -> None:
    def replacement(*args: object, **kwargs: object) -> None:
        del args, kwargs

    monkeypatch.setattr(engine, callable_name, replacement)
    with pytest.raises(
        implementation.CorpusRetrievalV2ImplementationContractError,
        match="not source-bound",
    ):
        _contract()


def test_current_source_evidence_drift_fails_under_same_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, path = implementation._source_module_evidence()
    changed_source = deepcopy(source)
    changed_source["source_bytes"] += 1
    monkeypatch.setattr(
        implementation,
        "_source_module_evidence",
        lambda: (changed_source, path),
    )
    with pytest.raises(
        implementation.CorpusRetrievalV2ImplementationContractError,
        match="source or strategy registry drifted",
    ):
        _contract()


def test_current_runtime_dependency_drift_fails_under_same_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime, paths = implementation._runtime_evidence()
    changed_runtime = deepcopy(runtime)
    changed_runtime["numpy_version"] = "2.5.2"
    monkeypatch.setattr(
        implementation,
        "_runtime_evidence",
        lambda: (changed_runtime, paths),
    )
    with pytest.raises(
        implementation.CorpusRetrievalV2ImplementationContractError,
        match="numerical runtime identity drifted",
    ):
        _contract()


def test_validator_rejects_schema_selfhash_nonfinite_and_diagnostic_attacks() -> None:
    extra = deepcopy(_contract())
    extra["extra"] = None
    _assert_rejected(extra)

    stale_hash = deepcopy(_contract())
    stale_hash["contract_identity"]["evidence_role"] = "publication"
    _assert_rejected(stale_hash)

    nonfinite = deepcopy(_contract())
    nonfinite["contract_identity"]["execution_laws"]["entry_budget"] = (
        float("nan")
    )
    _assert_rejected(nonfinite)

    diagnostic = deepcopy(_contract())
    diagnostic["diagnostics"][
        "excluded_from_implementation_contract_sha256"
    ] = False
    _assert_rejected(diagnostic)
