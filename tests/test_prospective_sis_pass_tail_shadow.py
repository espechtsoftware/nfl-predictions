from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.inference import sis_pass_tail_shadow as shadow
from nfl_dfs.inference import sis_pass_tail_portfolio as portfolio


ROOT = Path(__file__).parents[1]


def _source() -> pd.DataFrame:
    rows = []
    for team, offset in (("AAA", 0.0), ("BBB", 0.1)):
        for week in range(1, 6):
            rows.append({
                "season": 2026,
                "week": week,
                "team": team,
                "source_run_id": f"weekly-{week}",
                "pdef_attempts": 30 + week,
                "pdef_value_attempts": 20 + week,
                "pdef_boom_rate": 0.10 + offset + week / 100,
                "pdef_bust_rate": 0.20 + offset + week / 100,
                "prush_combined_sacks": 2,
                "prush_pressures": 8 + week,
            })
    return pd.DataFrame(rows)


def test_target_context_is_strict_prior_and_uses_last_four_games():
    got = shadow.build_target_context(
        _source(), season=2026, week=5, teams=["AAA", "BBB"]
    ).set_index("team")
    assert got.sis_pass_tail_supported.all()
    assert got.sis_pass_tail_prior_games.eq(4).all()
    assert got.sis_pass_tail_source_week_end.eq(4).all()

    mutated = _source()
    mutated.loc[mutated.week.eq(5), [
        "pdef_boom_rate", "pdef_bust_rate", "prush_pressures",
    ]] = [0.99, 0.99, 999]
    after = shadow.build_target_context(
        mutated, season=2026, week=5, teams=["AAA", "BBB"]
    ).set_index("team")
    pd.testing.assert_frame_equal(got, after)


def test_target_context_requires_two_games_and_unique_source_keys():
    got = shadow.build_target_context(
        _source(), season=2026, week=2, teams=["AAA"]
    )
    assert not bool(got.sis_pass_tail_supported.iloc[0])
    assert got[list(shadow.FEATURES)].isna().all(axis=None)

    duplicate = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeats team-week"):
        shadow.build_target_context(
            duplicate, season=2026, week=5, teams=["AAA"]
        )


def test_attach_target_context_exposes_only_passing_positions():
    context = shadow.build_target_context(
        _source(), season=2026, week=5, teams=["AAA"]
    )
    players = pd.DataFrame({
        "season": [2026, 2026, 2026],
        "week": [5, 5, 5],
        "opponent": ["AAA", "AAA", "AAA"],
        "position": ["QB", "WR", "RB"],
        "gsis_id": ["q", "w", "r"],
    })
    got = shadow.attach_target_context(players, context).set_index("gsis_id")
    assert got.loc[["q", "w"], list(shadow.FEATURES)].notna().all(axis=None)
    assert got.loc["r", list(shadow.FEATURES)].isna().all()


def test_frozen_environment_pins_arm_and_registered_seeds():
    projection_seed, role_seed = shadow.SEEDS["R2"]
    env = shadow.arm_environment(
        "treatment", projection_seed=projection_seed, role_seed=role_seed
    )
    assert env["TABPFN_MARGINAL_TABLE"] == shadow.TREATMENT_TABLE
    assert env["SERVED_POSITION_SCALES"] == shadow.SCHEDULES["treatment"]
    assert env["DIRICHLET_K"] == shadow.FITTED_K
    assert not shadow.environment_failures("treatment", env)

    env["MULTISEED_PORTFOLIO"] = "CBWU"
    assert "unregistered composition lever is active" in shadow.environment_failures(
        "treatment", env
    )


def test_environment_rejects_unregistered_seed_pair():
    env = shadow.arm_environment("control", projection_seed=1, role_seed=2)
    assert "seed pair is not registered" in shadow.environment_failures(
        "control", env
    )


def test_live_cache_tables_are_explicitly_licensed(monkeypatch):
    from nfl_dfs.backtest import replay

    for table in (shadow.CONTROL_TABLE, shadow.TREATMENT_TABLE):
        assert replay._tabpfn_marginal_table({
            "TABPFN_MARGINAL_TABLE": table,
        }) == table
    with pytest.raises(ValueError, match="unlicensed"):
        replay._tabpfn_marginal_table({
            "TABPFN_MARGINAL_TABLE": "tabpfn_sis_pass_tail_live_v2",
        })


def _cache(arm: str) -> pd.DataFrame:
    rows = []
    for index, gsis_id in enumerate(("p1", "p2")):
        rows.append({
            "season": 2026,
            "week": 5,
            "gsis_id": gsis_id,
            "arm": arm,
            "mean": 10.0 + index + (0.5 if arm == "treatment" else 0),
            "q50": 9.0 + index,
            "q99": 20.0 + index + (1 if arm == "treatment" else 0),
            "protocol_version": shadow.PROTOCOL_VERSION,
            "code_sha": "abc1234",
            "training_source_checksum": "11",
            "inference_source_checksum": "22",
            "sis_source_checksum": "33",
            "sis_source_run_ids": '["weekly-4"]',
        })
    return pd.DataFrame(rows)


def test_cache_pair_requires_same_keys_and_source_identity():
    receipt = portfolio.cache_pair_receipt(
        _cache("control"), _cache("treatment"),
        season=2026, week=5, code_sha="abc1234",
    )
    assert receipt["rows_per_arm"] == 2
    assert receipt["changed_player_distribution_rows"] == 2

    treatment = _cache("treatment")
    treatment.loc[0, "sis_source_checksum"] = "other"
    with pytest.raises(ValueError, match="sis_source_checksum"):
        portfolio.cache_pair_receipt(
            _cache("control"), treatment,
            season=2026, week=5, code_sha="abc1234",
        )


def test_prospective_portfolio_is_explicit_no_run_before_week_five(monkeypatch):
    monkeypatch.setenv("CODE_SHA", "abc1234")
    result = portfolio.run(
        store=object(), season=2026, week=4, draft_group_id=1,
    )
    assert result["disposition"].endswith("not-yet-eligible")
    assert result["minimum_week"] == 5


def test_live_gpu_writer_and_deployment_are_isolated_and_append_only():
    generator = (
        ROOT / "scripts/tabpfn_sis_pass_tail_live/gen.py"
    ).read_text(encoding="utf-8")
    dockerfile = (
        ROOT / "scripts/tabpfn_sis_pass_tail_live/Dockerfile"
    ).read_text(encoding="utf-8")
    deploy = (
        ROOT / "deploy/deploy_sis_pass_tail_cache.sh"
    ).read_text(encoding="utf-8")
    jobs = (ROOT / "deploy/deploy_jobs.sh").read_text(encoding="utf-8")
    assert "WRITE_APPEND" in generator
    assert "already has {season} Week {week}" in generator
    assert "tabpfn_projections" not in generator
    assert "TABPFN_UPCOMING=auto" in deploy
    assert "--gpu 1" in deploy
    assert 'scheduler jobs pause "$scheduler"' in deploy
    assert "live_shadow.py" in dockerfile
    assert "shadow-sis-pass-tail-paired" in jobs
