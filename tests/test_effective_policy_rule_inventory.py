"""Static, fail-closed checks for the independent policy-rule inventory."""

from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

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
    SOURCE_SET_ID,
    V6_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V6_FROZEN_SOURCE_SHA256,
    V6_SOURCE_SET_ID,
    V7_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V7_FROZEN_SOURCE_SHA256,
    V7_SOURCE_SET_ID,
    V8_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V8_FROZEN_SOURCE_SHA256,
    V8_SOURCE_SET_ID,
    V9_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V9_FROZEN_SOURCE_SHA256,
    V9_SOURCE_SET_ID,
    V10_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V10_FROZEN_SOURCE_SHA256,
    V10_SOURCE_SET_ID,
    V12_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V12_FROZEN_SOURCE_SHA256,
    V12_SOURCE_SET_ID,
    V13_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V13_FROZEN_SOURCE_SHA256,
    V13_SOURCE_SET_ID,
    V14_CLASSIFIED_INPUT_PROJECTION_SHA256,
    V14_FROZEN_SOURCE_SHA256,
    V14_SOURCE_SET_ID,
    canonical_json_bytes,
    canonical_sha256,
    generate_effective_policy_rule_inventory,
    generate_effective_policy_rule_inventory_v7,
    generate_effective_policy_rule_inventory_v8,
    generate_effective_policy_rule_inventory_v9,
    generate_effective_policy_rule_inventory_v10,
    generate_effective_policy_rule_inventory_v12,
    generate_effective_policy_rule_inventory_v13,
    generate_effective_policy_rule_inventory_v14,
    validate_effective_policy_rule_inventory,
)


ROOT = Path(__file__).resolve().parents[1]
V5_SOURCE_COMMIT = "def26c98ee88b4e874f516494fd57a76f62326f0"


def _policy_semantics(inventory: dict[str, object]) -> dict[str, object]:
    rule_fields = (
        "baseline_state",
        "classification",
        "default_dose",
        "id",
        "normalized_paths",
        "optional",
        "parametric_field",
        "stage",
    )
    return {
        "effective_policy": inventory["effective_policy"],
        "legal_feasibility_parameters": inventory[
            "legal_feasibility_parameters"
        ],
        "rules": [
            {field: row[field] for field in rule_fields}
            for row in inventory["rules"]
        ],
    }


def test_cloudbuild_full_suite_imports_the_pinned_source_tree():
    source = (ROOT / "cloudbuild.yaml").read_text(encoding="utf-8")
    assert "PYTHONPATH=src pytest" in source
    assert "PYTHONPATH=. pytest" not in source


@pytest.fixture(scope="module")
def inventory() -> dict[str, object]:
    return generate_effective_policy_rule_inventory_v14(ROOT)


def test_v14_is_explicit_and_v5_to_v13_literals_remain_frozen(inventory) -> None:
    assert SOURCE_SET_ID == (
        "adopted-classic-policy-20260830-week1-boom-first-v5"
    )
    assert CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "29956b03e2b3c19e0c938ae8043a15d1bcc2942ea731aea2337f5db4889f1989"
    )
    assert FROZEN_SOURCE_SHA256["src/nfl_dfs/app/main.py"] == (
        "1a64ce27b01b819351f2f55bd398f2fe0a086b0ee84f5677cbd097f9d102a87b"
    )
    assert FROZEN_SOURCE_SHA256["src/nfl_dfs/optimizer/lineup.py"] == (
        "efb1e4a203da81d8677deb138e3487a399975177ca8ec42d98a093155b14be7f"
    )
    assert V6_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/live_lineups.py"] == (
        "b37e9c5056bebe021e1dfa07ac574e929434419f996292d627cbb927200f689e"
    )
    assert V6_SOURCE_SET_ID == (
        "adopted-classic-policy-20260902-week1-boom-first-selector-lineage-v6"
    )
    assert V6_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "d3ad2c67c3e57e6199c83a3e4de8c3c6ef07fde44a4c289d1f85464f9c52a779"
    )
    assert V7_SOURCE_SET_ID == (
        "adopted-classic-policy-20260910-week1-licensed-asof-v7"
    )
    assert V7_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "e9b8779f0dacb530311b321d9e761d132b95ad2b40d0a64e776e10eab01599a2"
    )
    assert V7_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/live_lineups.py"] == (
        "95ccc439badad13714432fabb7396a16177bb92674bbcdaed2dc7e71fb2e6864"
    )
    assert V7_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/run_projections.py"] == (
        "24a49e904d0859d52b3e85eb259247aec8f68a6d19aca11d739740b3572738c4"
    )
    assert V8_SOURCE_SET_ID == (
        "adopted-classic-policy-20260921-week3-market-source-v8"
    )
    assert V8_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "3135cf8718fc58e800774fb1714690ec18b88069ef7ecde673e2be72250c816a"
    )
    assert V8_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/run_projections.py"] == (
        "7bf2785e2ca8d951aaf25d17378f7ae89c407dbdfb7a288df0777bac1381cf7e"
    )
    assert V9_SOURCE_SET_ID == (
        "adopted-classic-policy-20260922-week3-qb-availability-gate-v9"
    )
    assert V9_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "4635ad55efc75a43f43e33ce7959d64ea0be8ed1a3e3c75971f617893957a606"
    )
    assert V9_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/run_projections.py"] == (
        "49abc54fd67be65298a7af40c646e50b9dae8fa053d58f26e34682f510778daa"
    )
    assert V10_SOURCE_SET_ID == (
        "adopted-classic-policy-20260922-week3-questionable-haircut-v10"
    )
    assert V10_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "7ba8976639b9970e6a69d1ffe2870fdb622cafb40d4973351996fb5a1ff78eb1"
    )
    assert V10_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/run_projections.py"] == (
        "c4502523b3fde52b41974ebbc639e4958afa387e5415fead0d8e3e72e7965f71"
    )
    assert V12_SOURCE_SET_ID == (
        "adopted-classic-policy-20260923-week3-q-primary-backup-scale-v12"
    )
    assert V12_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "8b69934e51ab1ab41e58c7c34dbfbf8296a9f2205d830317066cb00dadbcc543"
    )
    assert V12_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/run_projections.py"] == (
        "fa0c67fbad19466fb06e9101f1b417b393bf55a82a4940f499f840aca2f67656"
    )
    assert V13_SOURCE_SET_ID == (
        "adopted-classic-policy-20260923-week3-returning-teammate-v13"
    )
    assert V13_CLASSIFIED_INPUT_PROJECTION_SHA256 == (
        "402ec72f4e341a6e31a15a741ead75c5479ed829f2b93538b3cb2a20753d5061"
    )
    assert V13_FROZEN_SOURCE_SHA256["src/nfl_dfs/inference/live_lineups.py"] == (
        "7290c0797ed83c73b514db6b9d2de0f8aed3ca47925768cdbd276a9377a61e48"
    )
    assert V14_SOURCE_SET_ID == (
        "adopted-classic-policy-20260923-week3-thin-line-market-v14"
    )
    assert inventory["source_set_id"] == V14_SOURCE_SET_ID
    assert inventory["classified_input_projection_sha256"] == (
        V14_CLASSIFIED_INPUT_PROJECTION_SHA256
    )
    with pytest.raises(
        EffectivePolicyInventoryError,
        match=r"frozen source SHA-256 differs: src/nfl_dfs/app/main.py",
    ):
        generate_effective_policy_rule_inventory(ROOT)


def test_archived_v5_validates_and_has_same_policy_semantics(
    inventory: dict[str, object], tmp_path: Path
) -> None:
    try:
        archive_raw = subprocess.check_output(
            ["git", "archive", V5_SOURCE_COMMIT], cwd=ROOT
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("exact v5 Git source archive is unavailable")
    with tarfile.open(fileobj=BytesIO(archive_raw)) as archive:
        archive.extractall(tmp_path, filter="data")

    script = """
import json
from pathlib import Path
from nfl_dfs.research.effective_policy_rule_inventory import (
    canonical_sha256,
    generate_effective_policy_rule_inventory,
    validate_effective_policy_rule_inventory,
)
root = Path.cwd()
inventory = generate_effective_policy_rule_inventory(root)
validate_effective_policy_rule_inventory(inventory, root)
fields = (
    "baseline_state", "classification", "default_dose", "id",
    "normalized_paths", "optional", "parametric_field", "stage",
)
semantics = {
    "effective_policy": inventory["effective_policy"],
    "legal_feasibility_parameters": inventory["legal_feasibility_parameters"],
    "rules": [{field: row[field] for field in fields} for row in inventory["rules"]],
}
print(json.dumps({
    "inventory_sha256": inventory["inventory_sha256"],
    "policy_semantics_sha256": canonical_sha256(semantics),
    "projection_sha256": inventory["classified_input_projection_sha256"],
    "source_set_id": inventory["source_set_id"],
    "source_set_sha256": inventory["source_set_sha256"],
}, sort_keys=True))
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(tmp_path / "src")
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    archived = json.loads(completed.stdout)
    assert archived == {
        "inventory_sha256": (
            "2bf2eebd4bf17500f5fa09ecadbc6b76ddf14410678a4e26ebda34811e728ffa"
        ),
        "policy_semantics_sha256": canonical_sha256(
            _policy_semantics(inventory)
        ),
        "projection_sha256": CLASSIFIED_INPUT_PROJECTION_SHA256,
        "source_set_id": SOURCE_SET_ID,
        "source_set_sha256": (
            "926b776a2f233e3a32db1395b9e592eac2013334abd192421558dfa87239039f"
        ),
    }


def test_cross_label_rehash_cannot_turn_v14_into_v5(inventory) -> None:
    relabeled = deepcopy(inventory)
    relabeled["source_set_id"] = SOURCE_SET_ID
    relabeled["inventory_sha256"] = canonical_sha256({
        key: value
        for key, value in relabeled.items()
        if key != "inventory_sha256"
    })

    with pytest.raises(
        EffectivePolicyInventoryError,
        match=r"frozen source SHA-256 differs: src/nfl_dfs/app/main.py",
    ):
        validate_effective_policy_rule_inventory(relabeled, ROOT)


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
        assert all(locator["path"] in V14_FROZEN_SOURCE_SHA256
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
    assert roles["scripts/publish_week1_operating_book.py"] == (
        "week1_exact_publication_operator_command"
    )
    assert roles["src/nfl_dfs/research/final_forensic.py"] == (
        "independent_dk_only_validator"
    )
    assert roles["src/nfl_dfs/research/lr8_historical_arm.py"] == (
        "independent_five_rule_relaxation_with_legacy_min_games"
    )
    assert roles["src/nfl_dfs/inference/run_projections.py"] == (
        "live_projection_and_market_blend_enforcement"
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
    assert rules["rule:leverage-family"]["default_dose"] == {
        "solve_attempts": 40,
        "fallback_candidate_multiple": 2,
        "fallback_generation_entry_basis": 80,
    }
    assert rules["rule:boom-family"]["default_dose"] == {
        "solve_attempts": 160,
        "unique_fill": False,
    }
    assert rules["rule:boom-unique-fill"]["default_dose"] is False


def test_effective_policy_and_ambient_boundary_are_bound(inventory):
    effective = inventory["effective_policy"]
    assert effective["policy_id"] == (
        "classic-k1-role12-lev40-boom160-poscal-cbwu-v5"
    )
    assert effective["engine_environment_sha256"] == canonical_sha256(
        effective["engine_environment"]
    )
    env = effective["engine_environment"]
    assert len(env) == 75
    assert env["MIN_LINEUP_SALARY"] == "49000"
    assert env["MULTISEED_PORTFOLIO"] == "CBWU"
    assert env["SELECT_LADDER"] == ""
    assert (env["N_LEV"], env["N_BOOM"], env["N_EPISTEMIC"]) == (
        "40", "160", "12",
    )
    assert env["GEN_TOTAL_BUDGET"] == "172"
    assert env["BOOM_UNIQUE_FILL"] == "0"
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
        V14_CLASSIFIED_INPUT_PROJECTION_SHA256
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
        assert all(
            site["source_sha256"]
            == V14_FROZEN_SOURCE_SHA256[site["path"]]
                   for site in row["direct_read_sites"])
        if row["ambient_process_requirement"] == "absent":
            assert key in projection["ambient_process_keys_requiring_absence"]

    for key, value in (("N_LEV", "40"), ("BOOM_UNIQUE_FILL", "0")):
        row = inputs[key]
        assert row["classification"] == "frozen_mechanism_input"
        assert row["baseline_effective_policy"] == {
            "state": "present", "value": value,
        }
        assert row["request_mapping_requirement"] == {
            "state": "present", "value": value,
        }
    assert "PROP_MARKET_REQUIRED" not in inputs
    for key in (
        "WEEK1_OPERATING_BOOK_URI",
        "WEEK1_OPERATING_BOOK_GENERATION",
        "WEEK1_OPERATING_BOOK_SHA256",
        "WEEK1_OPERATING_BOOK_BYTES",
    ):
        assert inputs[key]["classification"] == "infrastructure_only"
        assert {
            site["path"] for site in inputs[key]["direct_read_sites"]
        } == {"src/nfl_dfs/app/week1_operating_book_api.py"}

    live_projection_sites = [
        site
        for row in inputs.values()
        for site in row["direct_read_sites"]
        if site["path"] == "src/nfl_dfs/inference/run_projections.py"
    ]
    assert len(live_projection_sites) == 1
    assert live_projection_sites[0]["classification"] == (
        "frozen_mechanism_input"
    )


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
    for relative in V14_FROZEN_SOURCE_SHA256:
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
        generate_effective_policy_rule_inventory_v14(tmp_path)


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
        generate_effective_policy_rule_inventory_v14(ROOT)

    monkeypatch.setattr(
        inventory_module,
        "FORBIDDEN_AMBIENT_INPUT_KEYS",
        inventory_module.FORBIDDEN_AMBIENT_INPUT_KEYS | {key},
    )
    with pytest.raises(
        EffectivePolicyInventoryError,
        match="classified runtime-input projection SHA-256 differs",
    ):
        generate_effective_policy_rule_inventory_v14(ROOT)


def test_inventory_source_has_no_graph_bootstrap_dependency():
    source = (
        ROOT / "src/nfl_dfs/research/effective_policy_rule_inventory.py"
    ).read_text(encoding="utf-8")
    assert "from .evidence_knowledge_graph import" not in source
    assert "bootstrap.json" not in source
    assert "reports/evidence-graph" not in source
