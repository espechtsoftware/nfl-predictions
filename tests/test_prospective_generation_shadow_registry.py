from __future__ import annotations

from types import MappingProxyType

import pytest

from nfl_dfs.inference import prospective_generation_shadow_registry as registry


def test_frozen_registry_validates_and_is_immutable() -> None:
    document = registry.validate_registry(registry.FROZEN_REGISTRY)
    assert document == registry.registry_document()
    assert document["registry_sha256"] == registry.REGISTRY_SHA256
    assert isinstance(registry.FROZEN_REGISTRY, MappingProxyType)
    with pytest.raises(TypeError):
        registry.FROZEN_REGISTRY["registry_id"] = "changed"  # type: ignore[index]


def test_exact_arms_and_allocations_include_losers() -> None:
    arms = {item["arm_id"]: item for item in registry.registry_document()["arms"]}
    assert list(arms) == [
        "incumbent-160-40",
        "boom-first-40-160",
        "cross-law-40-100-60",
        "boom-dose-40-360",
        "ceiling-all-boom-0-200",
    ]
    assert arms["incumbent-160-40"]["allocation_per_block"] == {
        "leverage": 160, "base_boom": 40, "cross_law_boom": 0, "role": 12
    }
    assert arms["boom-first-40-160"]["allocation_per_block"] == {
        "leverage": 40, "base_boom": 160, "cross_law_boom": 0, "role": 12
    }
    assert arms["cross-law-40-100-60"]["allocation_per_block"] == {
        "leverage": 40, "base_boom": 100, "cross_law_boom": 60, "role": 12
    }
    assert arms["boom-dose-40-360"]["resource_class"] == (
        "400-core-solves-per-block-unequal-resource"
    )
    assert arms["ceiling-all-boom-0-200"]["passed_historical_nomination"] is False
    assert all(arm["status"] == "required" for arm in arms.values())
    assert all(arm["required_before_week1"] is True for arm in arms.values())
    assert [arm["scientific_status"] for arm in arms.values()] == [
        "control", "primary", "exploratory", "unequal-resource", "unpassed",
    ]
    assert arms["boom-first-40-160"]["decision_role"] == (
        "primary-efficacy-challenger"
    )
    assert all(
        arms[arm_id]["decision_role"] == "diagnostic-only"
        for arm_id in (
            "cross-law-40-100-60",
            "boom-dose-40-360",
            "ceiling-all-boom-0-200",
        )
    )


def test_exact_k_coverage_prefixes_and_thresholds() -> None:
    protocol = registry.registry_document()["shared_protocol"]
    assert protocol["operational_k"] == 80
    assert protocol["prefixes"] == [20, 40, 80]
    assert protocol["coverage_threshold"] == 194
    assert protocol["tail_thresholds"] == [194, 200, 210, 220, 230, 240]
    assert protocol["generation_blocks_per_slate"] == 5
    assert protocol["retrieval_crossing"]["adds_candidate_solves"] is False


def test_only_legality_is_universal_but_shadows_retain_incumbent_rules() -> None:
    scope = registry.registry_document()["scope"]
    assert scope["universal_construction_law"] == "draftkings-legality-only"
    assert scope["shadow_construction_preset"] == "incumbent-gpp-construction"


def test_decision_horizons_are_frozen() -> None:
    rules = registry.registry_document()["decision_rules"]
    assert rules["interim_horizon_weeks"] == 8
    assert rules["interim_scope"] == (
        "integrity-and-severe-harm-only-no-efficacy-promotion"
    )
    assert rules["eight_week_efficacy_decision_forbidden"] is True
    assert rules["structural_horizon"] == "full-regular-season"
    assert rules["no_midstream_dose_order_selector_tuning"] is True
    assert rules["all_five_arms_required_before_week1"] is True
    assert rules["arm_omission_allowed"] is False
    roles = rules["contrast_decision_roles"]
    assert roles["boom-first-40-160"][
        "primary_efficacy_rule_satisfaction_allowed"
    ] is True
    assert all(
        role["decision_role"] == "diagnostic-only"
        and role["promotion_equivalent_efficacy_allowed"] is False
        for arm_id, role in roles.items()
        if arm_id != "boom-first-40-160"
    )
    retrieval = registry.registry_document()["shared_protocol"][
        "retrieval_crossing"
    ]
    assert retrieval["decision_role"] == "key-secondary-mechanism"
    assert retrieval["primary_efficacy_rule_satisfaction_allowed"] is False
    safety = rules["week8_safety_contract"]
    assert safety["receipt_weeks"] == list(range(1, 9))
    assert len(safety["expected_arm_ids"]) == 5
    assert len(safety["expected_book_ids"]) == 7
    assert safety["expected_block_labels"] == ["R0", "R1", "R2", "R3", "R4"]
    assert safety["expected_prefix_sizes"] == [20, 40, 80]
    assert all(
        threshold == 0
        for name, threshold in safety["thresholds"].items()
        if name.startswith("maximum_")
        and name != "maximum_player_book_exposure_bps"
    )
    assert safety["thresholds"]["maximum_player_book_exposure_bps"] == 9_000
    assert safety["missing_receipt_status"] == "not_evaluated"
    assert safety["efficacy_or_promotion_allowed"] is False


def test_structural_synthesis_freezes_exact_history_and_2027_fallback() -> None:
    synthesis = registry.registry_document()["decision_rules"][
        "structural_synthesis_contract"
    ]
    identity = synthesis["historical_evidence_identity"]
    metrics = synthesis["historical_metrics"]
    assert identity == {
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-boom-first-allocation/"
            "20260829-boom-first-68873f42-git-v1/full-54/"
            "descriptive-realized-grade.json"
        ),
        "generation": 1_788_045_886_595_896,
        "sha256": (
            "3d92cd0ba1466b52a0bfa883e1c51efddbabf474800ba4516340cc4eb0bff23c"
        ),
        "bytes": 4_002_644,
    }
    assert synthesis["historical_internal_grade_sha256"] == (
        "eaba50ff60c12552c188a162de9858316967f2dc8d8ba8a430a9b14818a522a4"
    )
    assert (
        metrics["challenger_selected_score_sum_micro"]
        - metrics["control_selected_score_sum_micro"]
        == metrics["selected_paired_delta_sum_micro"]
        == 67_800_000
    )
    assert (
        metrics["challenger_pool_oracle_sum_micro"]
        - metrics["control_pool_oracle_sum_micro"]
        == metrics["pool_oracle_paired_delta_sum_micro"]
        == 182_340_000
    )
    assert (
        metrics["challenger_selector_regret_sum_micro"]
        - metrics["control_selector_regret_sum_micro"]
        == metrics["selector_regret_paired_delta_sum_micro"]
        == 114_540_000
    )
    assert synthesis["fallback_disposition"] == (
        "continue-unchanged-accrual-into-2027"
    )
    assert synthesis["automatic_adoption_allowed"] is False
    assert synthesis["historical_and_prospective_gain_summing_allowed"] is False


def test_exact_tested_implementation_exclusions_are_narrow() -> None:
    document = registry.registry_document()
    closed = document["exact_tested_implementation_exclusions"]
    assert len(closed) == 17
    assert (
        "historical-gamma-4-first-result-on-boom-first-population-not-live-authority"
        in closed
    )
    assert "analog-copulas" in closed
    assert set(document["explicit_nonclosures"]) == {
        "gflownet-generators",
        "sequential-monte-carlo-generators",
        "mode-balancing-generators",
        "model-parliament-with-genuinely-disagreeing-candidate-laws",
        "underlying-dependence-deficiency",
    }


def test_findings_and_non_additivity_are_explicit() -> None:
    findings = registry.registry_document()["findings_and_laws"]
    assert findings["market_blend"]["historical_drop_cost_at_k100"] == -2.2
    assert findings["house_rules"]["historical_equal-solve_effect"] == 3.6
    assert findings["calibration"]["leverage_roster_tail_overstatement"] == 2.8
    assert findings["cross_seed"]["required_test"] == "crossed-fit-seed-by-world-seed"
    assert findings["population_by_cap"]["never_add-to-boom-first-gain"] is True
    assert findings["contest_capture"]["capture_is_mandatory"] is True
    assert "split-payouts" in findings["contest_capture"]["required_fields"]
    assert findings["non_additivity"]["historical_gains_must_not_be_summed"] is True


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("shared_protocol", "operational_k"), 100),
        (("arms", 1, "allocation_per_block", "base_boom"), 159),
        (("decision_rules", "interim_horizon_weeks"), 7),
        ((
            "decision_rules", "structural_synthesis_contract",
            "historical_evidence_identity", "generation",
        ), 1_788_045_886_595_895),
        (("findings_and_laws", "non_additivity", "historical_gains_must_not_be_summed"), False),
    ],
)
def test_tampering_is_rejected(path: tuple[object, ...], replacement: object) -> None:
    document = registry.registry_document()
    target: object = document
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]
    with pytest.raises(registry.ShadowRegistryError):
        registry.validate_registry(document)


def test_rehashing_tampered_document_still_fails() -> None:
    document = registry.registry_document()
    document["shared_protocol"]["coverage_threshold"] = 200
    payload = dict(document)
    payload.pop("registry_sha256")
    document["registry_sha256"] = registry.canonical_sha256(payload)
    with pytest.raises(registry.ShadowRegistryError):
        registry.validate_registry(document)


def test_returned_documents_do_not_mutate_authority() -> None:
    first = registry.registry_document()
    first["arms"].clear()
    assert len(registry.registry_document()["arms"]) == 5
