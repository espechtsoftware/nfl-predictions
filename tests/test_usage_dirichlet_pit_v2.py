from pathlib import Path


def test_pit_usage_runner_binds_repaired_table_and_waits_for_tier1():
    root = Path(__file__).parents[1]
    launch = (root / "scripts/cloud_usage_dirichlet_calibration_v2.sh").read_text(
        encoding="utf-8"
    )
    finish = (
        root / "scripts/cloud_finish_usage_dirichlet_calibration_v2.sh"
    ).read_text(encoding="utf-8")
    assert "selected_tier1.txt" in launch
    assert "pit-repair-warehouse-reconciled" in launch
    assert "BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t)))" in launch
    assert "1904430067081090565" in launch
    assert "MODEL_ENSEMBLE=1" in launch
    assert "USAGE_DIRICHLET_CALIBRATION_JSON=" in finish
