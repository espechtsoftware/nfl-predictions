"""Static, fail-closed checks for the independent policy-rule inventory."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from nfl_dfs.research import effective_policy_rule_inventory as inventory_module
from nfl_dfs.research.effective_policy_rule_inventory import (
    CLASSIFIED_INPUT_KEY_COUNT,
    CLASSIFIED_INPUT_PROJECTION_SHA256,
    DIRECT_INPUT_READ_SITE_COUNT,
    EffectivePolicyInventoryError,
    FORBIDDEN_AMBIENT_INPUT_KEYS,
    FROZEN_SOURCE_SHA256,
    INPUT_CLASSIFICATIONS,
    PARAMETRIC_FIELDS,
    SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
    generate_effective_policy_rule_inventory,
    validate_effective_policy_rule_inventory,
)


ROOT = Path(__file__).resolve().parents[1]


def test_cloudbuild_full_suite_imports_the_pinned_source_tree():
    source = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "PYTHONPATH=src pytest" in source
    assert "PYTHONPATH=. pytest" not in source


@pytest.fixture(scope="module")
def inventory() -> dict[str, object]:
    return generate_effective_policy_rule_inventory(ROOT)


def _rules(inventory: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["id"]: row for row in inventory["rules"]}


def _inputs(inventory: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        row["input_key"]: row
        for row in inventory["classified_input_projection"]["inputs"]
    }


def test_inventory_is_canonical_source_generated_and_replayable(inventory):
    assert inventory["schema"] == SCHEMA
    assert inventory["complete_for_scope"] is True
    assert inventory["scope"]["runtime_receipt_required"] is True
    assert inventory["inventory_sha256"] == canonical_sha256({
        key: value for key, value in inventory.items()
        if key != "inventory_sha256"
    })
    assert validate_effective_policy_rule_inventory(inventory, ROOT) == inventory
    assert json.loads(canonical_json_bytes(inventory)) == inventory


def test_every_rule_has_a_separate_typed_dose_path_and_source(inventory):
    rules = inventory["rules"]
    assert inventory["rule_count"] == len(rules)
    assert len({row["id"] for row in rules}) == len(rules)
    assert [row["id"] for row in rules] == sorted(row["id"] for row in rules)

    for row in rules:
        assert row["baseline_state"] in {"active", "inactive"}
        assert row["classification"] in {
            "admission_recipe",
            "dk_hard",
            "generation_recipe",
            "house_soft",
            "selector",
            "simulation_law",
        }
        assert row["stage"] in {
            "admission", "generation", "selection", "simulation",
        }
        assert row["normalized_paths"] == sorted(set(row["normalized_paths"]))
        assert row["source_locators"]
        assert row["source_locator_sha256"] == canonical_sha256(
            row["source_locators"]
        )
        assert all(locator["path"] in FROZEN_SOURCE_SHA256
                   for locator in row["source_locators"])


def test_exact_five_active_soft_constraints_and_domains(inventory):
    surface = inventory["legal_feasibility_parameters"]
    assert [row["field"] for row in surface] == sorted(PARAMETRIC_FIELDS)
    assert len(surface) == 5

    rules = _rules(inventory)
    for row in surface:
        rule = rules[row["rule_id"]]
        expected_rule, expected_baseline, expected_allowed = PARAMETRIC_FIELDS[
            row["field"]
        ]
        assert row["rule_id"] == expected_rule
        assert row["baseline"] == expected_baseline
        assert type(row["baseline"]) is type(expected_baseline)
        assert row["allowed_values"] == list(expected_allowed)
        assert rule["classification"] == "house_soft"
        assert rule["stage"] == "generation"
        assert rule["baseline_state"] == "active"
        assert rule["normalized_paths"] == ["generation:all"]
        assert rule["default_dose"] == expected_baseline
        assert type(rule["default_dose"]) is type(expected_baseline)

    assert {
        row["parametric_field"] for row in rules.values()
        if row["parametric_field"] is not None
    } == set(PARAMETRIC_FIELDS)


def test_soft_rules_are_proven_by_enforcer_and_independent_consumers(inventory):
    rules = _rules(inventory)
    expected_paths = {
        "src/nfl_dfs/optimizer/lineup.py",
        "src/nfl_dfs/research/final_forensic.py",
        "src/nfl_dfs/research/lr8_historical_arm.py",
    }
    for _, (rule_id, _, _) in PARAMETRIC_FIELDS.items():
        paths = {row["path"] for row in rules[rule_id]["source_locators"]}
        assert expected_paths <= paths

    roles = {row["path"]: row["role"] for row in inventory["source_identities"]}
    assert roles["src/nfl_dfs/research/final_forensic.py"] == (
        "independent_dk_only_validator"
    )
    assert roles["src/nfl_dfs/research/lr8_historical_arm.py"] == (
        "independent_five_rule_relaxation_with_legacy_min_games"
    )


def test_every_optional_shared_constraint_is_an_individual_rule(inventory):
    rules = _rules(inventory)
    optional_ids = {
        row["id"] for row in rules.values() if row["optional"] is True
    }
    assert {
        "rule:bring-back-maximum",
        "rule:interaction-floor",
        "rule:max-per-game-cap",
        "rule:maximum-salary",
        "rule:min-low-ownership",
        "rule:objective-floor",
        "rule:ownership-barbell-high",
        "rule:ownership-barbell-low",
        "rule:player-bans",
        "rule:player-locks",
        "rule:punt-minimum",
        "rule:qb-stack-maximum",
        "rule:require-rb-vs-dst",
        "rule:require-two-rb-same-team",
        "rule:value-two-minimum",
    } <= optional_ids
    assert rules["rule:ownership-barbell-low"]["id"] != (
        rules["rule:ownership-barbell-high"]["id"]
    )


def test_active_generation_admission_simulation_and_selector_are_explicit(inventory):
    rules = _rules(inventory)
    active = {
        row["id"] for row in rules.values() if row["baseline_state"] == "active"
    }
    assert {
        "rule:boom-family",
        "rule:cbwu-cross-seed-admission",
        "rule:dark-game-family",
        "rule:first-producer-dedup-order",
        "rule:game-stack-family",
        "rule:leverage-family",
        "rule:qb-variant-family",
        "rule:role-family",
        "rule:selector-line194",
        "rule:simulation-fitted-widen",
        "rule:simulation-game-mode",
        "rule:simulation-served-position-scales",
        "rule:simulation-team-factors",
    } <= active
    assert rules["rule:candidate-budget-truncation"]["baseline_state"] == (
        "inactive"
    )
    assert rules["rule:max-per-game-cap"]["default_dose"] == 0
    assert rules["rule:selector-ladder"]["baseline_state"] == "inactive"


def test_effective_policy_and_ambient_boundary_are_bound(inventory):
    effective = inventory["effective_policy"]
    assert effective["policy_id"] == "classic-k1-role12-boom40-poscal-cbwu-v4"
    assert effective["engine_environment_sha256"] == canonical_sha256(
        effective["engine_environment"]
    )
    assert effective["engine_environment"]["MIN_LINEUP_SALARY"] == "49000"
    assert effective["engine_environment"]["MULTISEED_PORTFOLIO"] == "CBWU"
    assert effective["engine_environment"]["SELECT_LADDER"] == ""
    assert inventory["forbidden_ambient_process_keys"] == sorted(
        FORBIDDEN_AMBIENT_INPUT_KEYS
    )


def test_runtime_input_projection_is_an_exact_classified_partition(inventory):
    projection = inventory["classified_input_projection"]
    inputs = _inputs(inventory)
    assert projection["input_count"] == CLASSIFIED_INPUT_KEY_COUNT == len(inputs)
    assert projection["direct_input_read_site_count"] == (
        DIRECT_INPUT_READ_SITE_COUNT
    )
    assert inventory["classified_input_projection_sha256"] == (
        CLASSIFIED_INPUT_PROJECTION_SHA256
    )
    assert inventory["classified_input_projection_sha256"] == canonical_sha256(
        projection
    )
    assert set(projection["classification_counts"]) == set(
        INPUT_CLASSIFICATIONS
    )
    assert sum(projection["classification_counts"].values()) == len(inputs)
    assert set(row["classification"] for row in inputs.values()) == set(
        INPUT_CLASSIFICATIONS
    )

    for key, row in inputs.items():
        assert row["direct_read_site_count"] == len(row["direct_read_sites"])
        assert row["direct_read_sites_sha256"] == canonical_sha256(
            row["direct_read_sites"]
        )
        assert all(site["classification"] == row["classification"]
                   for site in row["direct_read_sites"])
        assert all(site["source_sha256"] == FROZEN_SOURCE_SHA256[site["path"]]
                   for site in row["direct_read_sites"])
        if row["ambient_process_requirement"] == "absent":
            assert key in projection["ambient_process_keys_requiring_absence"]


def test_stack_globals_and_engine_replay_game_sim_reads_are_visible(inventory):
    inputs = _inputs(inventory)
    for key, field, baseline in (
        ("STACK_QB_MIN", "qb_stack_min", 2),
        ("STACK_BRING_BACK", "bring_back_min", 1),
        ("FORBID_RB_DST", "forbid_rb_vs_dst", True),
        ("MIN_LINEUP_SALARY", "min_lineup_salary", 49_000),
    ):
        row = inputs[key]
        assert row["classification"] == "typed_parametric_rule"
        assert row["parametric_field"] == field
        assert row["baseline_dose"] == baseline
        assert type(row["baseline_dose"]) is type(baseline)

    expected_sources = {
        "ALT_CEIL": "src/nfl_dfs/backtest/replay.py",
        "DIRICHLET_K": "src/nfl_dfs/models/game_sim.py",
        "SCRIPT_FEEDBACK": "src/nfl_dfs/models/game_sim.py",
    }
    for key, path in expected_sources.items():
        sites = inputs[key]["direct_read_sites"]
        assert any(
            site["path"] == path
            and "ambient_process" in site["receiver_provenance"]
            for site in sites
        )
    cand_sites = inputs["CAND_MULT"]["direct_read_sites"]
    assert any(
        site["path"] == "src/nfl_dfs/backtest/engine.py"
        and "request_mapping" in site["receiver_provenance"]
        for site in cand_sites
    )
    assert not any(
        site["path"] == "src/nfl_dfs/backtest/engine.py"
        and "ambient_process" in site["receiver_provenance"]
        for site in cand_sites
    )
    assert inputs["ALT_CEIL"]["classification"] == "forbidden_ambient"
    assert inputs["DIRICHLET_K"]["classification"] == "forbidden_ambient"


def test_active_role_and_multiseed_doses_are_not_hidden_in_policy_hash(inventory):
    rules = _rules(inventory)
    inputs = _inputs(inventory)
    role = rules["rule:role-family"]["default_dose"]
    assert role == {
        "family": "role_draws",
        "feature_spec": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"
        ),
        "features": [
            "target_share_last", "carry_share_last", "snap_share_last",
            "target_share_jump", "carry_share_jump", "snap_share_jump",
        ],
        "seed": 7331,
        "solve_slots": 12,
    }
    admission = rules["rule:cbwu-cross-seed-admission"]["default_dose"]
    assert admission["seed_pairs"] == [
        {"label": "R0", "projection_seed": 0, "role_seed": 7331},
        {"label": "R1", "projection_seed": 1137260708,
         "role_seed": 2690847602},
        {"label": "R2", "projection_seed": 2875959182,
         "role_seed": 1630284992},
        {"label": "R3", "projection_seed": 253722715,
         "role_seed": 3374646876},
        {"label": "R4", "projection_seed": 1643280042,
         "role_seed": 3977633467},
    ]
    for key in (
        "MULTISEED_SEED_PAIRS", "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED",
    ):
        assert inputs[key]["classification"] == "frozen_mechanism_input"
        assert inputs[key]["baseline_effective_policy"]["state"] == "present"


def test_source_hash_drift_fails_before_policy_import(tmp_path: Path):
    for relative in FROZEN_SOURCE_SHA256:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    poisoned = tmp_path / "src/nfl_dfs/optimizer/lineup.py"
    poisoned.write_bytes(poisoned.read_bytes() + b"\n# drift\n")

    with pytest.raises(
        EffectivePolicyInventoryError,
        match=r"frozen source SHA-256 differs: src/nfl_dfs/optimizer/lineup.py",
    ):
        generate_effective_policy_rule_inventory(tmp_path)


def test_retained_inventory_value_and_type_poison_fail_closed(inventory):
    value_poison = deepcopy(inventory)
    value_poison["effective_policy"]["engine_environment"][
        "MIN_LINEUP_SALARY"
    ] = "0"
    with pytest.raises(
        EffectivePolicyInventoryError,
        match="retained effective-policy inventory differs",
    ):
        validate_effective_policy_rule_inventory(value_poison, ROOT)

    type_poison = deepcopy(inventory)
    rule = next(
        row for row in type_poison["rules"]
        if row["id"] == "rule:salary-floor-49000"
    )
    rule["default_dose"] = 49_000.0
    with pytest.raises(
        EffectivePolicyInventoryError,
        match="retained effective-policy inventory differs",
    ):
        validate_effective_policy_rule_inventory(type_poison, ROOT)


def test_omitted_and_reclassified_input_projection_poison_fail_closed(inventory):
    omitted = deepcopy(inventory)
    inputs = omitted["classified_input_projection"]["inputs"]
    inputs[:] = [row for row in inputs if row["input_key"] != "ROLE_BELIEF_SEED"]
    with pytest.raises(
        EffectivePolicyInventoryError,
        match="retained effective-policy inventory differs",
    ):
        validate_effective_policy_rule_inventory(omitted, ROOT)

    reclassified = deepcopy(inventory)
    next(
        row for row in reclassified["classified_input_projection"]["inputs"]
        if row["input_key"] == "ROLE_BELIEF_SEED"
    )["classification"] = "infrastructure_only"
    with pytest.raises(
        EffectivePolicyInventoryError,
        match="retained effective-policy inventory differs",
    ):
        validate_effective_policy_rule_inventory(reclassified, ROOT)


def test_source_classifier_omission_and_reclassification_fail_closed(monkeypatch):
    key = "ROLE_BELIEF_SEED"
    monkeypatch.setattr(
        inventory_module,
        "FROZEN_MECHANISM_INPUT_KEYS",
        inventory_module.FROZEN_MECHANISM_INPUT_KEYS - {key},
    )
    with pytest.raises(
        EffectivePolicyInventoryError,
        match=r"input classification partition differs; unclassified=.*ROLE_BELIEF_SEED",
    ):
        generate_effective_policy_rule_inventory(ROOT)

    monkeypatch.setattr(
        inventory_module,
        "FORBIDDEN_AMBIENT_INPUT_KEYS",
        inventory_module.FORBIDDEN_AMBIENT_INPUT_KEYS | {key},
    )
    with pytest.raises(
        EffectivePolicyInventoryError,
        match="classified runtime-input projection SHA-256 differs",
    ):
        generate_effective_policy_rule_inventory(ROOT)


def test_inventory_source_has_no_graph_bootstrap_dependency():
    source = (
        ROOT / "src/nfl_dfs/research/effective_policy_rule_inventory.py"
    ).read_text(encoding="utf-8")
    assert "from .evidence_knowledge_graph import" not in source
    assert "bootstrap.json" not in source
    assert "reports/evidence-graph" not in source
