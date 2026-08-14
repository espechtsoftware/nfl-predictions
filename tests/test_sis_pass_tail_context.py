import pandas as pd
import pytest

from nfl_dfs.analysis import sis_pass_tail_context as sis


def _source():
    return pd.DataFrame([
        {
            "season": 2025, "week": week, "team": "A",
            "pdef_attempts": 20 + week,
            "pdef_value_attempts": 10 * week,
            "pdef_boom_rate": 0.1 * week,
            "pdef_bust_rate": 0.05 * week,
            "prush_combined_sacks": week,
            "prush_pressures": 2 * week,
        }
        for week in range(1, 5)
    ])


def test_strict_prior_rates_are_volume_weighted():
    context = sis.build_strict_prior_context(_source())
    row = context.loc[context.week.eq(3)].iloc[0]
    assert row.sis_pass_def_boom_rate_l4 == pytest.approx(1.0 / 6.0)
    assert row.sis_pass_def_bust_rate_l4 == pytest.approx(1.0 / 12.0)
    assert row.sis_pass_rush_pressure_rate_l4 == pytest.approx(6 / 46)
    assert row.sis_pass_tail_source_week_end == 2
    assert row.sis_pass_tail_supported


def test_target_week_mutation_cannot_change_target_context():
    source = _source()
    before = sis.build_strict_prior_context(source)
    source.loc[source.week.eq(3), "pdef_boom_rate"] = 0.99
    after = sis.build_strict_prior_context(source)
    columns = [*sis.FEATURES, "sis_pass_tail_source_week_end"]
    pd.testing.assert_series_equal(
        before.loc[before.week.eq(3), columns].iloc[0],
        after.loc[after.week.eq(3), columns].iloc[0],
    )


def test_rejects_invalid_rate_and_duplicate_keys():
    source = _source()
    source.loc[0, "pdef_boom_rate"] = 1.1
    with pytest.raises(ValueError, match="outside"):
        sis.build_strict_prior_context(source)
    with pytest.raises(ValueError, match="repeats"):
        sis.build_strict_prior_context(pd.concat([_source(), _source().iloc[[0]]]))


def test_attachment_and_audit_are_outcome_free():
    context = sis.build_strict_prior_context(_source())
    panel = pd.DataFrame([
        {
            "season": 2025, "week": week, "gsis_id": f"p{week}",
            "position": "WR", "opp": "A", "was_active": True,
            "epa_per_dropback_allowed_l6": 0.01 * week,
            "opp_pressure_rate_l6": 0.02 * week,
        }
        for week in range(1, 5)
    ])
    attached = sis.attach_context(panel, context)
    report = sis.audit_attached(attached)
    assert report["outcomes_read"] is False
    assert report["supported_rows"] == 2
    assert report["supported_by_position"] == {"WR": 2}
    assert set(report["redundancy"]) == {
        "boom_vs_existing_pdef_epa",
        "bust_vs_existing_pdef_epa",
        "pressure_vs_existing_pressure",
        "boom_vs_bust",
    }
