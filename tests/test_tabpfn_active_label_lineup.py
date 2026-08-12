from pathlib import Path

import pandas as pd

from nfl_dfs.research import tabpfn_active_label_lineup as lineup


def _book(kind: str, code: str = "new") -> pd.DataFrame:
    rows = []
    table = lineup.CONTROL_TABLE if kind == "control" \
        else lineup.TREATMENT_TABLE
    schedules = lineup.CONTROL_POSITION_SPECS if kind == "control" \
        else lineup.TREATMENT_POSITION_SPECS
    for season in lineup.EVALUATION_SEASONS:
        values = {
            **lineup._frozen_common_levers(),
            "TABPFN_MARGINAL_TABLE": table,
            "SERVED_POSITION_SCALES": schedules[season],
        }
        rows.append({
            "season": season,
            "code_sha": code,
            "config_hash": f"config-{kind}-{season}",
            "seeds": "same-seeds",
            "lever_env": ",".join(
                f"{key}={value}" for key, value in sorted(values.items())),
        })
    return pd.DataFrame(rows)


def _features() -> dict:
    return {
        "left_rows": 100,
        "right_rows": 100,
        "left_only_rows": 0,
        "right_only_rows": 0,
        "mismatch_rows": 0,
        "max_numeric_abs_delta": 0.0,
        "ignored_numeric_fields": list(lineup.DISTRIBUTION_DERIVED_FEATURES),
    }


def _candidates(*, changed: bool = True) -> dict:
    return {
        "paired_slates": 54,
        "common_rows": 100,
        "left_only_rows": 2 if changed else 0,
        "right_only_rows": 3 if changed else 0,
        "common_actual_mismatch": 0,
        "common_sim_mean_mismatch": 5 if changed else 0,
    }


def test_mechanism_accepts_only_frozen_cache_and_schedule_changes():
    assert lineup.mechanism_failures(
        _book("control"),
        _book("treatment"),
        _features(),
        _candidates(),
        experiment_code_sha="new",
    ) == []


def test_mechanism_rejects_wrong_schedule_and_usage_change():
    treatment = _book("treatment")
    treatment.loc[treatment.season.eq(2024), "lever_env"] = (
        treatment.loc[treatment.season.eq(2024), "lever_env"].iloc[0]
        .replace(lineup.TREATMENT_POSITION_SPECS[2024],
                 "QB:1.000,RB:1.000,TE:1.000,WR:1.000")
        + ",GAME_SIM_USAGE=dirichlet,DIRICHLET_K=28")
    failures = lineup.mechanism_failures(
        _book("control"), treatment, _features(), _candidates(),
        experiment_code_sha="new")
    assert "treatment 2024 position schedule differs" in failures
    assert "treatment 2024 usage is not production default" in failures
    assert "treatment 2024 unexpectedly persists DIRICHLET_K" in failures


def test_mechanism_rejects_unregistered_output_exclusion_and_noop():
    features = _features()
    features["ignored_numeric_fields"].remove("proj_std")
    failures = lineup.mechanism_failures(
        _book("control"), _book("treatment"), features,
        _candidates(changed=False), experiment_code_sha="new")
    assert any("registered outputs" in failure for failure in failures)
    assert "active-label treatment did not reach candidate scoring" in failures


def test_active_label_exact80_scripts_and_protocol_are_packaged():
    root = Path(__file__).resolve().parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY scripts/compare_tabpfn_active_label_lineup.py " \
        "./scripts/compare_tabpfn_active_label_lineup.py" in dockerfile
    protocol = (root /
                "reports/2026-08-11-tabpfn-active-label-exact80-protocol.md")
    text = protocol.read_text(encoding="utf-8")
    assert lineup.FINAL_SERVED_REPORT_SHA256 in text
    assert lineup.CONTROL_PANEL in text and lineup.TREATMENT_PANEL in text
    for name in (
        "prop_lock_tabpfn_active_label_exact80.sh",
        "cloud_accept_tabpfn_active_label_exact80.sh",
        "cloud_compare_tabpfn_active_label_exact80.sh",
    ):
        assert (root / "scripts" / name).is_file()


def test_shared_panel_runner_and_acceptance_support_frozen_season_configs():
    root = Path(__file__).resolve().parents[1]
    baseline = (root / "scripts/baseline_panel.sh").read_text(encoding="utf-8")
    accept = (root / "scripts/cloud_accept_panel.sh").read_text(
        encoding="utf-8")
    harvest = (root / "scripts/harvest_accept.py").read_text(encoding="utf-8")
    assert 'KEY="PANEL_ARM_ENV_$1"' in baseline
    assert "season-varying-config" in accept
    assert "--allow-season-varying-config" in harvest
