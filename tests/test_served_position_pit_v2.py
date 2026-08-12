from pathlib import Path


def test_position_v2_runner_derives_selected_base_panel_and_pit_cache():
    root = Path(__file__).parents[1]
    launch = (root / "scripts/cloud_served_position_calibration_v2.sh").read_text(
        encoding="utf-8"
    )
    finish = (
        root / "scripts/cloud_finish_served_position_calibration_v2.sh"
    ).read_text(encoding="utf-8")
    assert "selected_tier1.txt" in launch
    assert 'k3) ENSEMBLE=3' in launch
    assert 'k1) ENSEMBLE=1' in launch
    assert "TABPFN_MARGINAL_TABLE=tabpfn_projections_pit_v2" in launch
    assert "SERVED_POSITION_CALIBRATION_PIT_V2=1" in launch
    assert "107" in launch
    assert '"version": "v2"' in finish
    assert '"tabpfn_table": "tabpfn_projections_pit_v2"' in finish
