from pathlib import Path


def test_pit_registry_qualification_is_isolated_and_fail_closed():
    root = Path(__file__).parents[1]
    launch = (root / "scripts/cloud_pit_registry_qualification.sh").read_text(
        encoding="utf-8"
    )
    finish = (
        root / "scripts/cloud_finish_pit_registry_qualification.sh"
    ).read_text(encoding="utf-8")
    validator = (
        root / "scripts/validate_pit_registry_qualification.py"
    ).read_text(encoding="utf-8")

    assert "MODEL_REGISTRY_PREFIX=$PREFIX" in launch
    assert "PREFIX=models_pit_v2" in launch
    assert "canonical 3" in launch
    assert "tail_k1 1" in launch
    assert "tail_k1_role 1" in launch
    assert "canonical PIT cache validation did not pass" in launch
    assert "isolated registry prefix already contains objects" in launch
    assert "status.conditions[0].status" in finish
    assert "role_adds_exact_registered_features" in validator
    assert "k3_k1_feature_contract_equal" in validator
    assert "generation" in validator
    assert "md5_hash" in validator
