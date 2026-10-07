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


def _cache(arm: str, *, dry_run: bool = False) -> pd.DataFrame:
    rows = []
    for index, gsis_id in enumerate(("p1", "p2")):
        rows.append({
            "contract": shadow.CONTRACT,
            "contract_settings_sha256": shadow.contract_settings_sha256(),
            "dry_run": dry_run,
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
    for key, value in portfolio.paired_job_environment(
            shadow.COMPANION_LINEUP_CONTRACT).items():
        monkeypatch.setenv(key, value)
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
    assert "gcloud artifacts docker images describe" in deploy
    assert '--image "$IMMUTABLE_IMAGE"' in deploy
    assert 'scheduler jobs pause "$scheduler"' in deploy
    assert "live_shadow.py" in dockerfile
    assert "shadow-sis-pass-tail-paired" in jobs


# --- O-3 Amendment 1 (2026-10-05): split contract, repairs, dry runs -------------------

import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import sys  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

DISTRIBUTION_SHA256 = "7693d3709e7b60f66d638b07881851e27220a39fdb01f1e789512360798509d8"
FROZEN_LINEUP_SHA256 = "0f03a67b81324eb13f13555ac90957fce0cfbc63aebda7f1455e7491378e7555"
COMPANION_SHA256 = "5133879471760ce0c606b3a8a4562c704f06153440a11be40ddb87718216dd1b"
COMPANION = "pass-tail-v1-a1-companion"
FROZEN = "pass-tail-v1-a1-frozen-2026-08"


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_prospective_gates_o3", ROOT / "scripts" / "check_prospective_gates.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_prospective_gates_o3"] = module
    spec.loader.exec_module(module)
    return module


def _paired_env(monkeypatch, contract=COMPANION, **extra):
    monkeypatch.setenv("CODE_SHA", "abc1234")
    for key in list(portfolio.paired_job_environment(COMPANION)):
        monkeypatch.delenv(key, raising=False)
    for key, value in {**portfolio.paired_job_environment(contract), **extra}.items():
        monkeypatch.setenv(key, value)


def test_published_identities():
    """Amendment 1 cites these three hashes; any setting change moves one of them."""
    assert shadow.distribution_settings_sha256() == DISTRIBUTION_SHA256
    assert shadow.contract_settings_sha256() == DISTRIBUTION_SHA256
    assert shadow.frozen_lineup_settings_sha256() == FROZEN_LINEUP_SHA256
    assert portfolio.companion_settings_sha256() == COMPANION_SHA256
    assert shadow.frozen_lineup_settings()["distribution_settings_sha256"] == DISTRIBUTION_SHA256
    assert portfolio.companion_contract_settings()[
        "distribution_settings_sha256"] == DISTRIBUTION_SHA256


def test_distribution_contract_is_generation_independent():
    settings = shadow.distribution_settings()
    text = str(settings)
    for lever in ("N_BOOM", "N_LEV", "SERVED_POSITION_SCALES", "DIRICHLET_K"):
        assert lever not in text
    assert settings["cache"]["context_max"] == 28_000
    assert settings["treatment_extra_tabpfn_fields"] == list(shadow.FEATURES)


def test_frozen_lineup_contract_keeps_the_august_arms():
    arms = shadow.frozen_lineup_settings()["arms"]
    for arm in ("control", "treatment"):
        assert (arms[arm]["N_BOOM"], arms[arm]["N_EPISTEMIC"], arms[arm]["N_CE"]) == (
            "40", "12", "0")
        assert arms[arm]["SERVED_POSITION_SCALES"] == shadow.SCHEDULES[arm]


def test_companion_is_the_adopted_money_path_literally():
    """Values derived from production_policy; the literals pin what was published."""
    assert portfolio.companion_settings() == {
        "GEN_TOTAL_BUDGET": "172", "N_LEV": "40", "N_CE": "0", "N_EPISTEMIC": "12",
        "N_BOOM": "160", "N_GUMBEL": "0", "REPLACEMENT_SLOTS": "12",
        "BOOM_UNIQUE_FILL": "0", "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ("target_share_last,carry_share_last,snap_share_last,"
                                 "target_share_jump,carry_share_jump,snap_share_jump"),
        "CE_SEED": "1701", "BLEND_MODEL_WEIGHT": "0.45", "LIVE_SIMS": "30000",
        "GAME_SIM_MODE": "possession",
        "SERVED_POSITION_SCALES": "QB:0.970,RB:1.005,TE:0.940,WR:1.070",
        "MODEL_ENSEMBLE": "1", "MIN_LINEUP_SALARY": "49000"}
    from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
    # The grid's five seed pairs ARE the money path's registered pairs.
    assert tuple(shadow.SEEDS.values()) == ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs


def test_companion_arms_differ_only_in_the_sis_cache():
    envs = {arm: portfolio.companion_book_environment(
        arm, projection_seed=0, role_seed=7331, environ={}, bucket="b")
        for arm in ("control", "treatment")}
    differ = {k for k in envs["control"] if envs["control"][k] != envs["treatment"].get(k)}
    assert differ == {"TABPFN_MARGINAL_TABLE"}
    for arm, env in envs.items():
        assert not portfolio.companion_failures(arm, env)
        assert env["TABPFN_MARGINAL_TABLE"] == shadow.TABLES[arm]
        assert env["N_BOOM"] == "160" and env["N_LEV"] == "40"
        assert env["MULTISEED_PORTFOLIO"] == ""
    bad = {**envs["control"], "N_BOOM": "40"}
    assert "N_BOOM differs" in portfolio.companion_failures("control", bad)
    bad = {**envs["control"], "SIS_ASOE_TARGET_ALLOCATION": "1"}
    assert any("SIS_ASOE" in f for f in portfolio.companion_failures("control", bad))
    bad = {**envs["control"], "TABPFN_MARGINAL_TABLE": shadow.TREATMENT_TABLE}
    assert "TABPFN_MARGINAL_TABLE differs" in portfolio.companion_failures("control", bad)


def test_base_feature_contract_hash_matches_the_file_the_image_copies():
    data = (ROOT / "scripts/tabpfn_gen/features.txt").read_bytes()
    assert hashlib.sha256(data).hexdigest() == shadow.BASE_FEATURES_SHA256


def test_registry_equals_the_guards_for_every_job():
    """One contract per job, three places (guard, registry, update command)."""
    cpg = _checker()
    dist = cpg.GATES["sis-pass-tail-2026"]
    assert dist["require_env_by_scheduler"] == {
        "s-tabpfn-sis-pass-tail-control": shadow.job_environment("cache-control"),
        "s-tabpfn-sis-pass-tail-treatment": shadow.job_environment("cache-treatment")}
    assert dist["schedulers"] == list(dist["require_env_by_scheduler"])
    assert dist["in_season_value"] is False
    comp = cpg.GATES["sis-pass-tail-2026-companion-v1"]
    assert comp["require_env"] == portfolio.paired_job_environment(COMPANION)
    assert comp["schedulers"] == ["s-shadow-sis-pass-tail-paired"]
    assert comp["input_schedulers"] == dist["schedulers"]
    assert comp["in_season_value"] is True and comp["same_env_include_inputs"] is True
    if (ROOT / "reports").is_dir():   # the Cloud Build live lane copies no reports/ (2026-10-04); the repo and CI check it
        assert (ROOT / comp["policy_doc"]).is_file()
    for spec in (dist, comp):
        assert spec["same_env_across_jobs"] == ["CODE_SHA"]
        assert "193e1b44d2b43eed70cc9b5688b3700d2054046d" in spec["require_code_ancestors"]
        assert "72261a27f44bc8e9a876dfc5c394517fa2847f32" in spec["require_code_ancestors"]


def test_deploy_scripts_declare_the_contracts():
    jobs = (ROOT / "deploy/deploy_jobs.sh").read_text(encoding="utf-8")
    line = next(l for l in jobs.splitlines() if l.startswith("job shadow-sis-pass-tail-paired"))
    declared = line.split('"')[1]
    pairs = dict(item.split("=", 1) for item in declared.split("|"))
    assert pairs.pop("CODE_SHA") == "${CODE_SHA}"
    assert pairs == portfolio.paired_job_environment(COMPANION)
    cache = (ROOT / "deploy/deploy_sis_pass_tail_cache.sh").read_text(encoding="utf-8")
    assert "SIS_PASS_TAIL_CONTRACT=pass-tail-v1-a1,TABPFN_SIS_PASS_TAIL_LIVE_ARM=${arm}" in cache


@pytest.mark.parametrize("role", shadow.CACHE_ROLES + ("paired-frozen",))
def test_job_contract_has_no_default_and_refuses_any_one_key_drift(role):
    good = shadow.job_environment(role)
    receipt = shadow.check_job_contract(good, role)
    assert receipt["distribution_settings_sha256"] == DISTRIBUTION_SHA256
    assert receipt["dry_run"] is False
    missing = {k: v for k, v in good.items() if k != shadow.CONTRACT_ENV}
    with pytest.raises(RuntimeError, match="no default"):
        shadow.check_job_contract(missing, role)
    for key in good:
        with pytest.raises(RuntimeError, match="contradicts"):
            shadow.check_job_contract({**good, key: good[key] + "x"}, role)


def test_paired_contract_refuses_drift_strays_and_unknown_names():
    good = portfolio.paired_job_environment(COMPANION)
    receipt = portfolio.check_paired_contract(good)
    assert receipt["settings_sha256"] == COMPANION_SHA256
    for key in good:
        with pytest.raises(RuntimeError):
            portfolio.check_paired_contract({**good, key: good[key] + "x"})
    with pytest.raises(RuntimeError, match="does not declare"):
        portfolio.check_paired_contract({**good, "SELECT_LSE": "1"})
    with pytest.raises(RuntimeError, match="does not declare"):
        portfolio.check_paired_contract({"SIS_PASS_TAIL_CONTRACT": FROZEN, "N_LEV": "40"})
    with pytest.raises(RuntimeError, match="no default"):
        portfolio.check_paired_contract({})
    with pytest.raises(RuntimeError, match="requires"):
        portfolio.check_paired_contract({"SIS_PASS_TAIL_CONTRACT": "pass-tail-v1-a1"})
    frozen = portfolio.check_paired_contract({"SIS_PASS_TAIL_CONTRACT": FROZEN})
    assert frozen["settings_sha256"] == FROZEN_LINEUP_SHA256


def test_cache_arm_env_cannot_pass_as_the_other_arm():
    env = shadow.job_environment("cache-control")
    with pytest.raises(RuntimeError, match="contradicts"):
        shadow.check_job_contract(env, "cache-treatment")


@pytest.mark.parametrize("value", ["0", "true", "yes", " 1"])
def test_dry_run_flag_must_be_exact(value):
    env = {**shadow.job_environment("cache-control"), "SHADOW_DRY_RUN": value}
    with pytest.raises(RuntimeError, match="SHADOW_DRY_RUN"):
        shadow.check_job_contract(env, "cache-control")
    env["SHADOW_DRY_RUN"] = "1"
    assert shadow.check_job_contract(env, "cache-control")["dry_run"] is True


def test_frozen_lineup_generation_is_refused_live_from_week_5():
    shadow.require_live_lineup_contract(FROZEN, 2026, 4, dry_run=False)
    shadow.require_live_lineup_contract(FROZEN, 2026, 5, dry_run=True)
    shadow.require_live_lineup_contract(COMPANION, 2026, 5, dry_run=False)
    with pytest.raises(RuntimeError, match="may not produce a live"):
        shadow.require_live_lineup_contract(FROZEN, 2026, 5, dry_run=False)


def test_identities_never_share_a_prefix():
    frozen = shadow.LINEUP_IDENTITIES[FROZEN]
    companion = shadow.LINEUP_IDENTITIES[COMPANION]
    for a, b in zip(frozen, companion):
        assert not a.startswith(b) and not b.startswith(a)


def test_marginal_reads_count_fallbacks_live_and_redirect_dry(monkeypatch):
    """Reviewer ruling (f): the silent empirical fallback is counted, not changed."""
    from nfl_dfs import bq
    from nfl_dfs.backtest import replay

    original = replay.load_tabpfn_marginal_cache
    live_calls = []
    monkeypatch.setattr(replay, "load_tabpfn_marginal_cache",
                        lambda season, env=None: live_calls.append(env) or pd.DataFrame())
    with portfolio.marginal_reads(False) as receipt:
        out = replay.load_tabpfn_marginal_cache(
            2026, {"TABPFN_MARGINAL_TABLE": shadow.CONTROL_TABLE})
        assert out.empty  # behaviour unchanged: the caller still falls back
        with pytest.raises(RuntimeError, match="unexpected marginal table"):
            replay.load_tabpfn_marginal_cache(2026, {"TABPFN_MARGINAL_TABLE": ""})
    assert receipt["empty_fallbacks"] == 1
    assert receipt["tables"][shadow.CONTROL_TABLE] == {
        "reads": 1, "empty_fallbacks": 1, "rows": 0}
    monkeypatch.setattr(replay, "load_tabpfn_marginal_cache", original)
    sql = []
    monkeypatch.setattr(bq, "query_df", lambda q, params=None: sql.append(q) or _cache("control"))
    with portfolio.marginal_reads(True) as receipt:
        replay.load_tabpfn_marginal_cache(2026, {"TABPFN_MARGINAL_TABLE": shadow.CONTROL_TABLE})
    assert "tabpfn_sis_pass_tail_live_control_v1_dryrun" in sql[0]
    assert receipt["empty_fallbacks"] == 0
    assert replay.load_tabpfn_marginal_cache is original
    monkeypatch.setattr(bq, "query_df", lambda q, params=None: pd.DataFrame())
    with portfolio.marginal_reads(True):
        with pytest.raises(RuntimeError, match="is empty"):
            replay.load_tabpfn_marginal_cache(
                2026, {"TABPFN_MARGINAL_TABLE": shadow.TREATMENT_TABLE})


def _schedule(weeks=range(1, 6)) -> pd.DataFrame:
    rows = []
    for week in weeks:
        rows.append({"season": 2026, "week": week, "game_type": "REG",
                     "home_team": "AAA", "away_team": "BBB"})
    rows.append({"season": 2026, "week": 1, "game_type": "PRE",
                 "home_team": "AAA", "away_team": "CCC"})
    return pd.DataFrame(rows)


def test_source_window_requires_every_completed_team_game():
    audit = shadow.require_complete_source_window(
        _source(), _schedule(), season=2026, week=5)
    assert audit["complete"] and audit["expected_team_games"] == 8
    assert audit["source_weeks"] == [1, 2, 3, 4]
    no_w4 = _source()[lambda f: ~f.week.eq(4)]
    with pytest.raises(ValueError, match="incomplete"):
        shadow.require_complete_source_window(no_w4, _schedule(), season=2026, week=5)
    dry = shadow.require_complete_source_window(
        no_w4, _schedule(), season=2026, week=5, dry_run=True)
    assert not dry["complete"] and dry["missing"] == ["4:AAA", "4:BBB"]
    stray = pd.concat([_source(), _source().iloc[[0]].assign(team="ZZZ")])
    with pytest.raises(ValueError, match="unexpected"):
        shadow.require_complete_source_window(stray, _schedule(), season=2026, week=5)


def test_target_salary_comes_from_dk_salary_week():
    target = pd.DataFrame({"gsis_id": ["a", "b"], "season": 2026, "week": 5})
    salaries = pd.DataFrame({"gsis_id": ["a"], "season": [2026], "week": [5],
                             "salary": [6400]})
    out, audit = shadow.attach_target_salary(target, salaries)
    assert out.set_index("gsis_id").salary.to_dict()["a"] == 6400
    assert audit["rows_with_salary"] == 1 and audit["rows_without_salary"] == 1
    with pytest.raises(ValueError, match="now carry salary"):
        shadow.attach_target_salary(target.assign(salary=1), salaries)
    with pytest.raises(ValueError, match="repeats"):
        shadow.attach_target_salary(target, pd.concat([salaries, salaries]))


def test_auto_target_is_one_week_and_the_schedules_week():
    assert shadow.resolve_auto_target([(2026, 5), (2026, 5)], (2026, 5)) == (2026, 5)
    with pytest.raises(ValueError, match="exactly one"):
        shadow.resolve_auto_target([(2026, 4), (2026, 5)], (2026, 5))
    with pytest.raises(ValueError, match="differs from the schedule"):
        shadow.resolve_auto_target([(2026, 4)], (2026, 5))


def test_gpu_generator_auto_target_counts_only_the_upcoming_weeks_teams():
    """O-41 (2026-10-07): from Week 5 a team on bye carries its NEXT game in player_week_inference (Week 5: CAR / KC
    on Week 6), so the generator's distinct inference weeks are taken over the teams the schedule plays in the
    upcoming week only; the resolver itself (one week, the schedule's week) is unchanged and still fails closed."""
    generator = (ROOT / "scripts/tabpfn_sis_pass_tail_live/gen.py").read_text(encoding="utf-8")
    body = generator[generator.index("def _resolve_auto_target("):generator.index("def _checksum(")]
    assert body.index("SELECT MIN(week) AS week") < body.index("player_week_inference")   # the schedule's week first
    for needle in ("UNNEST([s.home_team, s.away_team]) AS team", "s.week=@upcoming", "i.team IN (",
                   "AND s.gameday >= CAST(CURRENT_DATE() AS STRING))",
                   'ScalarQueryParameter("upcoming", "INT64", int(upcoming))', "resolve_auto_target(\n"):
        assert needle in body, needle
    # the resolver's contract is unchanged: a bye-filtered single week passes, a stale or mixed table refuses
    assert shadow.resolve_auto_target([(2026, 5)] * 30, (2026, 5)) == (2026, 5)
    with pytest.raises(ValueError, match="exactly one"):
        shadow.resolve_auto_target([(2026, 5), (2026, 6)], (2026, 5))
    with pytest.raises(ValueError, match="differs from the schedule"):
        shadow.resolve_auto_target([(2026, 4)], (2026, 5))


def test_gpu_generator_is_wired_to_the_contract():
    generator = (ROOT / "scripts/tabpfn_sis_pass_tail_live/gen.py").read_text(
        encoding="utf-8")
    for needle in (
        'check_job_contract(os.environ, f"cache-{ARM}")',
        "require_complete_source_window(",
        "attach_target_salary(target, salaries)",
        "cache_table(ARM, dry_run=dry_run)",
        "WRITE_TRUNCATE if dry_run",
        "BASE_FEATURES_SHA256",
        'predicted["contract_settings_sha256"]',
        'predicted["dry_run"] = dry_run',
        "resolve_auto_target(",
    ):
        assert needle in generator, needle
    assert "28_000" not in generator and "RANDOM_SEED = 7" not in generator


def test_cache_pair_requires_the_contract_and_the_same_dry_run_mode():
    receipt = portfolio.cache_pair_receipt(
        _cache("control", dry_run=True), _cache("treatment", dry_run=True),
        season=2026, week=5, code_sha="abc1234", dry_run=True)
    assert receipt["control_table"] == shadow.DRY_RUN_TABLES["control"]
    with pytest.raises(ValueError, match="dry-run flag"):
        portfolio.cache_pair_receipt(
            _cache("control", dry_run=True), _cache("treatment", dry_run=True),
            season=2026, week=5, code_sha="abc1234", dry_run=False)
    other = _cache("treatment")
    other["contract_settings_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="contract differs"):
        portfolio.cache_pair_receipt(
            _cache("control"), other, season=2026, week=5, code_sha="abc1234")


def test_paired_job_refuses_without_the_contract(monkeypatch):
    _paired_env(monkeypatch)
    monkeypatch.delenv("SIS_PASS_TAIL_CONTRACT")
    with pytest.raises(RuntimeError, match="no default"):
        portfolio.run(store=object(), season=2026, week=5, draft_group_id=1)


def test_paired_job_refuses_a_policy_lever_on_the_job(monkeypatch):
    _paired_env(monkeypatch, SELECT_LSE="1")
    with pytest.raises(RuntimeError, match="does not declare"):
        portfolio.run(store=object(), season=2026, week=5, draft_group_id=1)


def test_paired_job_refuses_the_frozen_generation_live_at_week_5(monkeypatch):
    _paired_env(monkeypatch, contract=FROZEN)
    with pytest.raises(RuntimeError, match="may not produce a live"):
        portfolio.run(store=object(), season=2026, week=5, draft_group_id=1)


def _slate(now: datetime, *, started_group: bool = False) -> pd.DataFrame:
    kick = pd.Timestamp(now) + pd.Timedelta(hours=6)
    frame = pd.DataFrame({
        "dk_player_id": [1, 2, 3],
        "draft_group_id": [100, 100, 200],
        "game_start": [kick, kick, kick],
        "gsis_id": ["p1", "p2", "c"],
        "dk_position": ["QB", "WR", "RB"],
    })
    if started_group:
        frame.loc[1, ["draft_group_id", "game_start"]] = [
            999, pd.Timestamp(now) - pd.Timedelta(days=3)]
    return frame


def test_one_feature_snapshot_reads_once_and_names_its_draft_groups(monkeypatch):
    from nfl_dfs.inference import run_projections

    now = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    calls = []

    def fake(season, week, as_of=None):
        calls.append((season, week))
        return _slate(now)

    monkeypatch.setattr(run_projections, "upcoming_slate_features", fake)
    with portfolio.one_feature_snapshot({1, 2}, now) as receipt:
        first = run_projections.upcoming_slate_features(2026, 5)
        first.loc[0, "gsis_id"] = "mutated"
        second = run_projections.upcoming_slate_features(2026, 5)
        with pytest.raises(RuntimeError, match="two target weeks"):
            run_projections.upcoming_slate_features(2026, 6)
    assert calls == [(2026, 5)] and second.gsis_id.iloc[0] == "p1"
    assert receipt["reads"] == 2 and len(receipt["sha256"]) == 64
    assert receipt["pool"]["selectable_draft_groups"] == {"100": 2}
    assert receipt["pool"]["draft_groups"] == {"100": 2, "200": 1}
    assert run_projections.upcoming_slate_features is fake


def test_stale_started_draft_group_is_refused(monkeypatch):
    """O-27 class (193e1b44): a selectable row from an already-started group."""
    from nfl_dfs.inference import run_projections

    now = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(run_projections, "upcoming_slate_features",
                        lambda season, week, as_of=None: _slate(now, started_group=True))
    with portfolio.one_feature_snapshot({1, 2}, now):
        with pytest.raises(RuntimeError, match="already started"):
            run_projections.upcoming_slate_features(2026, 5)


class _Store:
    def classic_salaries(self, draft_group_id):
        return pd.DataFrame({"dk_player_id": [1, 2], "dk_draftable_id": [11, 12],
                             "salary": [5000, 6000]})


class _Blob:
    def __init__(self, sink, name):
        self.sink, self.name = sink, name

    def upload_from_string(self, payload, content_type, if_generation_match):
        assert if_generation_match == 0
        self.sink[self.name] = payload


class _Storage:
    def __init__(self):
        self.objects = {}

    def bucket(self, name):
        sink = self.objects
        return type("B", (), {"blob": lambda _self, n: _Blob(sink, f"{name}/{n}")})()


@pytest.mark.parametrize("contract,dry_run", [
    (COMPANION, False), (COMPANION, True), (FROZEN, True)])
def test_paired_grid_end_to_end_is_namespaced_by_contract_and_mode(
        monkeypatch, contract, dry_run):
    """The full run() path, offline: ten books, one feature read, labelled outputs."""
    from nfl_dfs import bq
    from nfl_dfs.backtest import replay
    from nfl_dfs.inference import live_lineups, run_projections

    _paired_env(monkeypatch, contract=contract)
    if dry_run:
        monkeypatch.setenv("SHADOW_DRY_RUN", "1")
    else:
        monkeypatch.delenv("SHADOW_DRY_RUN", raising=False)
    now = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    reads = []
    monkeypatch.setattr(run_projections, "upcoming_slate_features",
                        lambda season, week, as_of=None: reads.append(week) or _slate(now))
    queried = []

    def query_df(sql, params=None):
        queried.append(sql)
        arm = "treatment" if "treatment" in sql else "control"
        return _cache(arm, dry_run=dry_run)

    monkeypatch.setattr(bq, "query_df", query_df)
    if not dry_run:
        monkeypatch.setattr(replay, "load_tabpfn_marginal_cache",
                            lambda season, env=None: _cache("control"))
    builds = []

    def build(season, week, **kwargs):
        run_projections.upcoming_slate_features(season, week)
        replay.load_tabpfn_marginal_cache(season, kwargs["policy_env"])
        builds.append(kwargs)
        kwargs["_candidate_capture"](object())
        return [type("L", (), {"ids": [1, 2, 3, 4, 5, 6, 7, 8, 9 + i]})() for i in range(80)]

    monkeypatch.setattr(live_lineups, "build_sim_lineups", build)
    monkeypatch.setattr(portfolio, "_membership",
                        lambda lineups, mapping: [[str(i)] for i in range(80)])
    persisted = []
    monkeypatch.setattr(portfolio, "persist_recourse_world_artifact",
                        lambda capture, mapping, **kw: persisted.append(kw) or {"uri": kw["object_name"]})
    out = portfolio.run(store=_Store(), season=2026, week=5, draft_group_id=77,
                        generated_at=now, storage_client=_Storage(), bucket_name="raw")
    assert len(builds) == 10 and reads == [5]
    assert out["dry_run"] is dry_run and out["live"] is (not dry_run)
    assert out["contract"]["contract"] == contract
    assert out["contract"]["distribution_settings_sha256"] == DISTRIBUTION_SHA256
    assert out["feature_snapshot"]["reads"] == 10 and "_frame" not in out["feature_snapshot"]
    assert out["feature_snapshot"]["pool"]["selectable_draft_groups"] == {"100": 2}
    assert out["marginal_reads"]["empty_fallbacks"] == 0
    assert out["cache_coverage"]["control"]["without_cache_row"] == 0
    gcs_root, run_type, prefix = shadow.LINEUP_IDENTITIES[contract]
    if dry_run:
        gcs_root, run_type = f"{gcs_root}_dryrun", f"{run_type}_dryrun"
    assert all(p["object_name"].startswith(gcs_root + "/") for p in persisted)
    assert out["manifest_uri"].startswith(f"gs://raw/{gcs_root}/")
    want_tables = shadow.DRY_RUN_TABLES if dry_run else shadow.TABLES
    assert all(any(t + "`" in q for q in queried) for t in want_tables.values())
    for kwargs in builds:
        assert kwargs["candidate_run_type"] == run_type
        assert kwargs["panel_run_id"].startswith(("dryrun-" if dry_run else "") + prefix)
        assert kwargs["_log_ownership_shadow"] is False
        assert kwargs["policy_env"]["TABPFN_MARGINAL_TABLE"] in shadow.TABLES.values()
    book = out["books"]["R0-control"]
    if contract == COMPANION:
        assert out["contract"]["settings_sha256"] == COMPANION_SHA256
        assert book["effective_generation"]["n_boom"] == 160
        assert book["worlds"] == 30000
        assert builds[0]["n_sims"] == 30000 and builds[0]["stack"].qb_stack_min == 2
    else:
        assert out["contract"]["settings_sha256"] == FROZEN_LINEUP_SHA256
        assert book["effective_generation"]["n_boom"] == 40
        assert book["worlds"] == 10000
    assert out["disposition"].endswith("dryrun" if dry_run else "frozen")


def test_live_fallback_is_recorded_in_the_manifest(monkeypatch):
    from nfl_dfs import bq
    from nfl_dfs.backtest import replay
    from nfl_dfs.inference import live_lineups, run_projections

    _paired_env(monkeypatch)
    monkeypatch.delenv("SHADOW_DRY_RUN", raising=False)
    now = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(run_projections, "upcoming_slate_features",
                        lambda season, week, as_of=None: _slate(now))
    monkeypatch.setattr(bq, "query_df", lambda sql, params=None: _cache(
        "treatment" if "treatment" in sql else "control"))
    monkeypatch.setattr(replay, "load_tabpfn_marginal_cache",
                        lambda season, env=None: pd.DataFrame())

    def build(season, week, **kwargs):
        run_projections.upcoming_slate_features(season, week)
        replay.load_tabpfn_marginal_cache(season, kwargs["policy_env"])
        kwargs["_candidate_capture"](object())
        return []

    monkeypatch.setattr(live_lineups, "build_sim_lineups", build)
    monkeypatch.setattr(portfolio, "_membership", lambda lineups, mapping: [])
    monkeypatch.setattr(portfolio, "persist_recourse_world_artifact",
                        lambda capture, mapping, **kw: {})
    out = portfolio.run(store=_Store(), season=2026, week=5, draft_group_id=77,
                        generated_at=now, storage_client=_Storage(), bucket_name="raw")
    assert out["marginal_reads"]["empty_fallbacks"] == 10
    from nfl_dfs.research import sis_pass_tail_weekly_record as record
    assert record.select_week_manifest(
        [out], lock_utc=datetime(2026, 10, 11, 17, tzinfo=timezone.utc),
        settings_sha256=COMPANION_SHA256) is None
