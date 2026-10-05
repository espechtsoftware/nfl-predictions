from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest


def test_registry_variant_keeps_canonical_labels_unchanged():
    from nfl_dfs.models import train_job

    assert train_job.registry_variant("canonical") == "canonical"
    assert train_job._component_label("targets", "canonical") == \
        "comp_targets"
    assert train_job._component_label("targets", "tail_k1") == \
        "comp_targets__tail_k1"
    assert train_job._component_version("2026-W36", "tail_k1") == \
        "pooled/components__tail_k1/2026-W36"
    with pytest.raises(ValueError, match="MODEL_REGISTRY_VARIANT"):
        train_job.registry_variant("../canonical")


def test_shadow_training_writes_only_suffixed_registry_labels(monkeypatch):
    from nfl_dfs.models import components, train_job

    panel = pd.DataFrame({"season": [2025]})
    monkeypatch.setattr(train_job, "training_panel", lambda: panel)
    monkeypatch.setattr(
        train_job.baseline, "walk_forward",
        lambda frame: SimpleNamespace(fold_reports={}),
    )
    booster = SimpleNamespace(feature_name=lambda: ["salary", "position"])
    fitted = SimpleNamespace(
        models={name: booster for name in components.COMPONENT_NAMES})
    monkeypatch.setattr(train_job.components, "train", lambda *a, **k: fitted)
    monkeypatch.setattr(train_job.registry, "model_params", lambda model: {})
    labels = []
    monkeypatch.setattr(
        train_job.registry, "save",
        lambda model, meta, root: labels.append(meta.label),
    )

    version = train_job.train_and_register(
        today=date(2026, 9, 8), variant="tail_k1")
    assert version == "pooled/components__tail_k1/2026-W37"
    assert set(labels) == {
        f"comp_{name}__tail_k1" for name in components.COMPONENT_NAMES}
    assert "comp_targets" not in labels


def test_load_shadow_models_reads_only_suffixed_labels(monkeypatch):
    from nfl_dfs.models import components, train_job

    seen = []
    monkeypatch.setattr(train_job, "_registry_root", lambda: "gs://test/models")
    monkeypatch.setattr(
        train_job.registry, "latest_iso_week",
        lambda root, scope, label: seen.append(label) or "2026-W37",
    )
    monkeypatch.setattr(
        train_job.registry, "load",
        lambda root, scope, label, week: (seen.append(label) or object(), None),
    )
    models, version = train_job.load_latest_component_models("tail_k1")
    assert version == "pooled/components__tail_k1/2026-W37"
    assert set(models.models) == set(components.COMPONENT_NAMES)
    assert seen[0] == "comp_targets__tail_k1"
    assert all(label.endswith("__tail_k1") for label in seen)


def test_registered_component_member_count_must_be_consistent():
    from nfl_dfs.models import components, train_job

    single = components.ComponentModels(models={"a": object(), "b": object()})
    assert train_job.registered_ensemble_size(single) == 1
    ensemble = lambda n: SimpleNamespace(members=[object()] * n)
    triple = components.ComponentModels(
        models={"a": ensemble(3), "b": ensemble(3)})
    assert train_job.registered_ensemble_size(triple) == 3
    mixed = components.ComponentModels(
        models={"a": ensemble(3), "b": object()})
    with pytest.raises(RuntimeError, match="mixed member counts"):
        train_job.registered_ensemble_size(mixed)


def test_sunday_main_matches_ui_largest_all_sunday_group():
    from nfl_dfs.inference.tail_shadow import sunday_main_group

    slates = pd.DataFrame([
        {"draft_group_id": 10, "game_start": "2026-09-10T00:20:00Z",
         "teams": 2, "players": 50},
        {"draft_group_id": 10, "game_start": "2026-09-13T17:00:00Z",
         "teams": 20, "players": 180},
        {"draft_group_id": 20, "game_start": "2026-09-13T17:00:00Z",
         "teams": 16, "players": 160},
        {"draft_group_id": 20, "game_start": "2026-09-13T20:25:00Z",
         "teams": 8, "players": 80},
        {"draft_group_id": 30, "game_start": "2026-09-13T20:25:00Z",
         "teams": 8, "players": 80},
    ])
    # A larger preseason Sunday must never be paired with regular Week 1.
    slates = pd.concat([slates, pd.DataFrame([{
        "draft_group_id": 40,
        "game_start": "2026-08-30T17:00:00Z",
        "teams": 30,
        "players": 300,
    }])], ignore_index=True)
    assert sunday_main_group(slates, date(2026, 9, 13)) == 20


def test_shadow_run_is_fixed_isolated_and_synchronous(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "tail_k1")
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    monkeypatch.setenv("CAND_ARTIFACT_BUCKET", "test-artifacts")
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20,
                "players": 100,
            }])

        def classic_salaries(self, gid):
            assert gid == 77
            return pd.DataFrame({
                "dk_player_id": range(100, 200),
                "salary": [5000] * 100,
            })

    captured = {}

    def fake_build(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return [object()] * 80

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build)
    result = tail_shadow.run(
        store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc),
    )
    assert result["panel_run_id"] == \
        "live-shadow-tail_k1-2026w01-20260913T153000Z"
    assert result["entries"] == 80 and result["tail_line"] == 194.0
    kwargs = captured["kwargs"]
    assert kwargs["n_entries"] == 80
    assert kwargs["model_variant"] == "tail_k1"
    assert kwargs["apply_notes"] is False
    assert kwargs["cand_log_async"] is False
    assert kwargs["cand_log_required"] is True
    assert kwargs["candidate_run_type"] == "live_shadow"
    assert kwargs["panel_run_id"] == result["panel_run_id"]
    assert kwargs["allowed_ids"] == set(range(100, 200))
    assert kwargs["belief_model_variant"] is None


def test_role_union_shadow_requires_and_passes_exact_role_contract(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    exact = {
        "ROUTE_SHARE_CONTRACT": "frozen-2026-08",
        "MODEL_REGISTRY_VARIANT": "tail_k1", "MODEL_ENSEMBLE": "1",
        "MIN_LINEUP_SALARY": "49000", "CAND_ARTIFACT_BUCKET": "artifacts",
        "GEN_TOTAL_BUDGET": "52", "N_GUMBEL": "0",
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "12", "N_EPISTEMIC": "12", "N_BOOM": "28",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": tail_shadow.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701",
    }
    for key, value in exact.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20, "players": 100,
            }])

        def classic_salaries(self, gid):
            return pd.DataFrame({
                "dk_player_id": range(100, 200), "salary": [5000] * 100})

    captured = {}

    def fake_build(*args, **kwargs):
        captured.update(kwargs)
        return [object()] * 80

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build)
    result = tail_shadow.run(
        shadow_label=tail_shadow.K1_ROLE_UNION_LABEL, store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 20, tzinfo=timezone.utc))
    assert result["panel_run_id"] == (
        "live-shadow-tail_k1_roleunion-2026w01-20260913T152000Z")
    assert result["role_model_variant"] == "tail_k1_role"
    assert captured["belief_model_variant"] == "tail_k1_role"
    assert captured["policy_env"]["N_EPISTEMIC"] == "12"
    assert captured["distribution_artifact_spec"].arm == "control"
    assert captured["model_required_features"] == ()
    assert "fp_route_share_last" in captured["model_forbidden_features"]
    assert "target_share_last" in captured["belief_required_features"]

    monkeypatch.setenv("N_EPISTEMIC", "11")
    with pytest.raises(RuntimeError, match="incorrect frozen settings"):
        tail_shadow.run(
            shadow_label=tail_shadow.K1_ROLE_UNION_LABEL, store=object())


def test_route_role_union_is_exact_isolated_treatment(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    exact = {
        "ROUTE_SHARE_CONTRACT": "frozen-2026-08",
        "MODEL_REGISTRY_VARIANT": "tail_k1_route", "MODEL_ENSEMBLE": "1",
        "MIN_LINEUP_SALARY": "49000", "CAND_ARTIFACT_BUCKET": "artifacts",
        "GEN_TOTAL_BUDGET": "52", "N_CE": "12", "N_EPISTEMIC": "12",
        "N_BOOM": "28", "N_GUMBEL": "0", "REPLACEMENT_SLOTS": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": tail_shadow.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701",
    }
    for key, value in exact.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20, "players": 100,
            }])

        def classic_salaries(self, gid):
            return pd.DataFrame({
                "dk_player_id": range(100, 200), "salary": [5000] * 100})

    captured = {}
    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups",
        lambda *args, **kwargs: captured.update(kwargs) or [object()] * 80)
    result = tail_shadow.run(
        expected_variant=tail_shadow.K1_ROUTE_VARIANT,
        shadow_label=tail_shadow.K1_ROUTE_ROLE_UNION_LABEL,
        store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 20, tzinfo=timezone.utc),
    )
    assert result["shadow_label"] == "tail_k1_route_roleunion"
    assert result["model_variant"] == "tail_k1_route"
    assert result["role_model_variant"] == "tail_k1_route_role"
    assert captured["route_source_policy"] is True
    assert captured["distribution_artifact_spec"].arm == "treatment"
    assert set(captured["model_required_features"]) == {
        "fp_route_share_last", "fp_route_share_l4",
        "fp_route_share_jump", "fp_route_cross_season"}
    assert "target_share_last" in captured["belief_required_features"]


def test_shadow_refuses_canonical_registry(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.delenv("MODEL_REGISTRY_VARIANT", raising=False)
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    with pytest.raises(RuntimeError, match="requires MODEL_REGISTRY_VARIANT=tail_k1"):
        tail_shadow.run(store=object())


def test_no_floor_shadow_has_distinct_identity_and_exact_floor(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "tail_k1")
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("CAND_ARTIFACT_BUCKET", "test-artifacts")
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20,
                "players": 100,
            }])

        def classic_salaries(self, gid):
            return pd.DataFrame({
                "dk_player_id": range(100, 200),
                "salary": [5000] * 100,
            })

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups",
        lambda *a, **k: [object()] * 80)
    result = tail_shadow.run(
        shadow_label=tail_shadow.K1_NOFLOOR_LABEL,
        store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc),
    )
    assert result["panel_run_id"] == \
        "live-shadow-tail_k1_nofloor-2026w01-20260913T153000Z"
    assert result["model_variant"] == "tail_k1"
    assert result["shadow_label"] == "tail_k1_nofloor"
    assert result["minimum_lineup_salary"] == 0


def test_no_floor_shadow_rejects_default_floor(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "tail_k1")
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    monkeypatch.delenv("MIN_LINEUP_SALARY", raising=False)
    with pytest.raises(RuntimeError, match="requires MIN_LINEUP_SALARY=0"):
        tail_shadow.run(
            shadow_label=tail_shadow.K1_NOFLOOR_LABEL, store=object())


def test_canonical_reference_shadow_has_distinct_identity(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "canonical")
    monkeypatch.setenv("MODEL_ENSEMBLE", "3")
    monkeypatch.setenv("CAND_ARTIFACT_BUCKET", "test-artifacts")
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, 1, date(2026, 9, 13)))

    class Store:
        def classic_slates(self):
            return pd.DataFrame([{
                "draft_group_id": 77,
                "game_start": "2026-09-13T17:00:00Z",
                "teams": 20,
                "players": 100,
            }])

        def classic_salaries(self, gid):
            return pd.DataFrame({
                "dk_player_id": range(100, 200),
                "salary": [5000] * 100,
            })

    captured = {}

    def fake_build(*args, **kwargs):
        captured.update(kwargs)
        return [object()] * 80

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build)
    result = tail_shadow.run(
        expected_variant=tail_shadow.K3_VARIANT,
        store=Store(),
        generated_at=datetime(2026, 9, 13, 15, 30, tzinfo=timezone.utc),
    )
    assert result["panel_run_id"] == \
        "live-shadow-tail_k3-2026w01-20260913T153000Z"
    assert result["model_variant"] == "canonical"
    assert result["shadow_label"] == "tail_k3"
    assert captured["model_variant"] == "canonical"
    assert captured["candidate_run_type"] == "live_shadow"


# --- Route Share contracts (O-2 / O-25, 2026-10-05) -------------------------

_ROUTE_INFRA = {"CAND_ARTIFACT_BUCKET": "artifacts", "GCP_PROJECT": "test"}
_CONTRACT_KEYS_TO_CLEAR = {
    "ROUTE_SHARE_CONTRACT", "SHADOW_DRY_RUN", "PROSPECTIVE_SHADOW_ID",
    "MULTISEED_PORTFOLIO", "MULTISEED_SEED_PAIRS", "N_QB_VARIANTS",
    "MAX_OVERLAP", "MIN_GAMES", "GEN_TOTAL_BUDGET", "N_LEV", "N_CE",
    "N_EPISTEMIC", "N_BOOM", "N_GUMBEL", "REPLACEMENT_SLOTS",
    "BOOM_UNIQUE_FILL", "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
    "ROLE_BELIEF_SEED", "CE_SEED", "BLEND_MODEL_WEIGHT", "LIVE_SIMS",
    "GAME_SIM_MODE", "SERVED_POSITION_SCALES", "MODEL_ENSEMBLE",
    "MIN_LINEUP_SALARY", "MODEL_REGISTRY_VARIANT",
}


class _MainSlateStore:
    def classic_slates(self):
        return pd.DataFrame([{
            "draft_group_id": 77,
            "game_start": "2026-10-11T17:00:00Z",
            "teams": 20, "players": 100,
        }])

    def classic_salaries(self, gid):
        return pd.DataFrame({
            "dk_player_id": range(100, 200), "salary": [5000] * 100})


def _arm(monkeypatch, contract: str, variant: str, week: int | None = None,
         **overrides):
    """Set exactly one arm's job env (+ overrides; None deletes a key).

    The frozen contract may run live only before 2026 Week 5, so its default
    target week is 4; companion v1 defaults to Week 5."""
    from nfl_dfs.inference import tail_shadow

    for key in _CONTRACT_KEYS_TO_CLEAR:
        monkeypatch.delenv(key, raising=False)
    env = {**_ROUTE_INFRA, "MODEL_REGISTRY_VARIANT": variant,
           **tail_shadow.route_share_job_environment(contract)}
    env.setdefault("MODEL_ENSEMBLE", "1")
    env.setdefault("MIN_LINEUP_SALARY", "49000")
    env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    if week is None:
        week = 4 if contract == "frozen-2026-08" else 5
    monkeypatch.setattr(
        tail_shadow, "upcoming_season_week",
        lambda: (2026, week, date(2026, 10, 11)))
    monkeypatch.setattr(
        "nfl_dfs.inference.route_share_shadow.require_prior_week_source",
        lambda season, week: None)


def _run_arm(monkeypatch, arm: str, dry: bool = False):
    from nfl_dfs.inference import tail_shadow

    captured = {}
    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups",
        lambda *args, **kwargs: captured.update(kwargs) or [object()] * 80)
    kwargs = (
        {"shadow_label": tail_shadow.K1_ROLE_UNION_LABEL}
        if arm == "control" else
        {"expected_variant": tail_shadow.K1_ROUTE_VARIANT,
         "shadow_label": tail_shadow.K1_ROUTE_ROLE_UNION_LABEL})
    result = tail_shadow.run(
        store=_MainSlateStore(),
        generated_at=datetime(2026, 10, 11, 15, 20, tzinfo=timezone.utc),
        **kwargs)
    return result, captured


ARM_VARIANT = {"control": "tail_k1", "treatment": "tail_k1_route"}
# Published in the gate amendment; a change to either contract changes these.
CONTRACT_SHA256 = {
    "frozen-2026-08":
        "345d3ca925564663490f20c5809be104c8171d86cd2c85990681cc874888fd91",
    "companion-v1":
        "76c3994a0d9d4bb4bc852a60569c535a8306458b5be7a2a9c254a7d851f96ee8",
}


def test_frozen_august_contract_is_kept_byte_for_byte():
    from nfl_dfs.inference import tail_shadow

    assert dict(tail_shadow.FROZEN_2026_08_SETTINGS) == {
        "GEN_TOTAL_BUDGET": "52",
        "N_CE": "12", "N_EPISTEMIC": "12", "N_BOOM": "28",
        "N_GUMBEL": "0", "REPLACEMENT_SLOTS": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": (
            "target_share_last,carry_share_last,snap_share_last,"
            "target_share_jump,carry_share_jump,snap_share_jump"),
        "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701",
    }


def test_companion_v1_is_the_adopted_money_path_generation():
    """Derived from production_policy, and pinned so a policy change is seen."""
    from nfl_dfs.inference import tail_shadow
    from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY as P

    settings = tail_shadow.companion_v1_settings()
    engine = P.engine_environment()
    assert settings == {k: engine[k] for k in tail_shadow.COMPANION_V1_KEYS}
    assert settings["GEN_TOTAL_BUDGET"] == str(P.n_role + P.n_boom)
    assert settings["N_CE"] == str(P.n_ce) == "0"
    assert settings == {
        "GEN_TOTAL_BUDGET": "172", "N_LEV": "40", "N_CE": "0",
        "N_EPISTEMIC": "12", "N_BOOM": "160", "N_GUMBEL": "0",
        "REPLACEMENT_SLOTS": "12", "BOOM_UNIQUE_FILL": "0",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": tail_shadow.ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701",
        "BLEND_MODEL_WEIGHT": "0.45", "LIVE_SIMS": "30000",
        "GAME_SIM_MODE": "possession",
        "SERVED_POSITION_SCALES": "QB:0.970,RB:1.005,TE:0.940,WR:1.070",
        "MODEL_ENSEMBLE": "1", "MIN_LINEUP_SALARY": "49000",
    }


@pytest.mark.parametrize("arm", ["control", "treatment"])
@pytest.mark.parametrize("contract", ["frozen-2026-08", "companion-v1"])
def test_each_contract_accepts_its_exact_set_and_records_it(
        monkeypatch, contract, arm):
    from nfl_dfs.inference import tail_shadow

    _arm(monkeypatch, contract, ARM_VARIANT[arm])
    result, captured = _run_arm(monkeypatch, arm)
    expected = tail_shadow.route_share_contract_settings(contract)
    assert result["route_share_contract"] == contract
    assert result["route_share_contract_settings"] == expected
    assert len(result["route_share_contract_settings_sha256"]) == 64
    assert result["dry_run"] is False and result["live"] is True
    assert result["candidate_run_type"] == "live_shadow"
    assert captured["candidate_run_type"] == "live_shadow"
    assert result["panel_run_id"].startswith("live-shadow-")
    for key, value in expected.items():
        assert captured["policy_env"][key] == value
    shadow_id = captured["policy_env"].get("PROSPECTIVE_SHADOW_ID")
    if contract == "companion-v1":
        assert shadow_id == tail_shadow.COMPANION_V1_SHADOW_ID
    else:
        # The frozen contract's recorded environment is left exactly as it was.
        assert shadow_id is None
    # Live runs do not append own_shadow either (O-27 follow-up): its readers
    # take a week's latest generation, so a shadow row would become "the" one.
    assert captured["_log_ownership_shadow"] is False


def _one_key_deviations():
    from nfl_dfs.inference import tail_shadow

    cases = []
    for contract in ("frozen-2026-08", "companion-v1"):
        for key, value in tail_shadow.route_share_contract_settings(
                contract).items():
            cases.append((contract, key, value + "9"))
            cases.append((contract, key, None))
    return cases


@pytest.mark.parametrize("contract,key,bad", _one_key_deviations())
def test_one_key_deviation_is_refused(monkeypatch, contract, key, bad):
    _arm(monkeypatch, contract, "tail_k1", **{key: bad})
    with pytest.raises(RuntimeError, match="incorrect frozen settings|requires MIN_LINEUP_SALARY|requires MODEL_ENSEMBLE"):
        _run_arm(monkeypatch, "control")


@pytest.mark.parametrize("value", [None, "", "companion-v2", "frozen"])
def test_missing_or_unknown_contract_is_refused(monkeypatch, value):
    _arm(monkeypatch, "companion-v1", "tail_k1", ROUTE_SHARE_CONTRACT=value)
    with pytest.raises(RuntimeError, match="ROUTE_SHARE_CONTRACT"):
        _run_arm(monkeypatch, "control")


def test_todays_mixed_job_env_is_refused_under_either_contract(monkeypatch):
    """The live Weeks 3-4 env: N_BOOM=160 + N_LEV=40 beside N_CE=12 / budget 52."""
    live = {"GEN_TOTAL_BUDGET": "52", "N_CE": "12", "N_BOOM": "160",
            "N_LEV": "40", "SERVED_POSITION_SCALES": None,
            "BOOM_UNIQUE_FILL": None}
    for contract in ("frozen-2026-08", "companion-v1"):
        _arm(monkeypatch, contract, "tail_k1", **live)
        with pytest.raises(RuntimeError, match="incorrect frozen settings"):
            _run_arm(monkeypatch, "control")


@pytest.mark.parametrize("override,match", [
    ({"MULTISEED_PORTFOLIO": "CBWU"}, "single-seed"),
    ({"N_QB_VARIANTS": "8"}, "contradicts the adopted money path"),
    ({"PROSPECTIVE_SHADOW_ID": "something-else"},
     "contradicts the adopted money path"),
    ({"MAX_OVERLAP": "8"}, "construction differs"),
])
def test_companion_refuses_drift_outside_its_pinned_keys(
        monkeypatch, override, match):
    _arm(monkeypatch, "companion-v1", "tail_k1", **override)
    with pytest.raises(RuntimeError, match=match):
        _run_arm(monkeypatch, "control")


@pytest.mark.parametrize("contract", ["frozen-2026-08", "companion-v1"])
def test_control_and_treatment_differ_only_by_the_route_variant(
        monkeypatch, contract):
    results, envs = {}, {}
    for arm in ("control", "treatment"):
        _arm(monkeypatch, contract, ARM_VARIANT[arm])
        results[arm], captured = _run_arm(monkeypatch, arm)
        envs[arm] = captured["policy_env"]
    differing = {
        key for key in set(envs["control"]) | set(envs["treatment"])
        if envs["control"].get(key) != envs["treatment"].get(key)}
    assert differing == {"MODEL_REGISTRY_VARIANT"}
    assert (results["control"]["route_share_contract_settings_sha256"]
            == results["treatment"]["route_share_contract_settings_sha256"])
    assert results["control"]["role_model_variant"] == "tail_k1_role"
    assert results["treatment"]["role_model_variant"] == "tail_k1_route_role"


def test_dry_run_is_isolated_from_the_graded_freeze(monkeypatch):
    _arm(monkeypatch, "companion-v1", "tail_k1_route", SHADOW_DRY_RUN="1")
    result, captured = _run_arm(monkeypatch, "treatment")
    assert result["dry_run"] is True and result["live"] is False
    assert result["panel_run_id"] == (
        "dryrun-live-shadow-tail_k1_route_roleunion-2026w05-"
        "20261011T152000Z")
    assert captured["panel_run_id"] == result["panel_run_id"]
    assert captured["distribution_artifact_spec"].panel_run_id == \
        result["panel_run_id"]
    # Graded readers select run_type = 'live_shadow' and the live-shadow-
    # panel prefix; the dry run matches neither and skips the own_shadow append.
    assert captured["candidate_run_type"] == "live_shadow_dryrun"
    assert not captured["panel_run_id"].startswith("live-shadow-")
    assert captured["_log_ownership_shadow"] is False
    from nfl_dfs.research.live_shadow_portfolios import _PANEL_ID

    assert _PANEL_ID.fullmatch(result["panel_run_id"]) is None


def test_dry_run_flag_must_be_exact(monkeypatch):
    _arm(monkeypatch, "companion-v1", "tail_k1", SHADOW_DRY_RUN="yes")
    with pytest.raises(RuntimeError, match="SHADOW_DRY_RUN"):
        _run_arm(monkeypatch, "control")


def test_contract_on_a_non_route_shadow_is_refused(monkeypatch):
    from nfl_dfs.inference import tail_shadow

    for key in _CONTRACT_KEYS_TO_CLEAR:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "tail_k1")
    monkeypatch.setenv("MODEL_ENSEMBLE", "1")
    monkeypatch.setenv("ROUTE_SHARE_CONTRACT", "companion-v1")
    with pytest.raises(RuntimeError, match="applies only to the Route Share"):
        tail_shadow.run(store=object())


def test_deploy_script_and_verifier_declare_the_companion_contract():
    """The redeploy script and the deployment verifier carry the same contract."""
    import re
    from pathlib import Path

    from nfl_dfs.inference import tail_shadow

    root = Path(__file__).resolve().parents[1]
    deploy = (root / "deploy" / "deploy_jobs.sh").read_text(encoding="utf-8")
    want = tail_shadow.route_share_job_environment("companion-v1")
    for job, variant in (("shadow-k1-roleunion", "tail_k1"),
                         ("shadow-k1-route-roleunion", "tail_k1_route")):
        line = re.search(rf'^job {job} {job} 8Gi 4 "([^"]+)"$', deploy, re.M)
        assert line, job
        env = dict(item.split("=", 1) for item in line.group(1).split("|"))
        assert env.pop("MODEL_REGISTRY_VARIANT") == variant
        assert env.pop("CAND_ARTIFACT_BUCKET") == "${PROJECT}-raw"
        assert env.pop("CODE_SHA") == "${CODE_SHA}"
        assert env == want, job


@pytest.mark.parametrize("arm", ["control", "treatment"])
@pytest.mark.parametrize("week", [5, 6, 18])
def test_frozen_contract_may_not_run_live_from_week_5(monkeypatch, arm, week):
    """Companion v1 owns the graded weeks from W5; a live frozen book is refused."""
    _arm(monkeypatch, "frozen-2026-08", ARM_VARIANT[arm], week=week)
    built = []
    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups",
        lambda *a, **k: built.append(k) or [object()] * 80)
    from nfl_dfs.inference import tail_shadow

    kwargs = (
        {"shadow_label": tail_shadow.K1_ROLE_UNION_LABEL}
        if arm == "control" else
        {"expected_variant": tail_shadow.K1_ROUTE_VARIANT,
         "shadow_label": tail_shadow.K1_ROUTE_ROLE_UNION_LABEL})
    with pytest.raises(RuntimeError, match="may not produce a live run"):
        tail_shadow.run(store=_MainSlateStore(), **kwargs)
    assert built == []  # refused before any candidate work or persistence


@pytest.mark.parametrize("arm", ["control", "treatment"])
def test_frozen_contract_from_week_5_only_as_a_flagged_dry_run(monkeypatch, arm):
    _arm(monkeypatch, "frozen-2026-08", ARM_VARIANT[arm], week=5,
         SHADOW_DRY_RUN="1")
    result, captured = _run_arm(monkeypatch, arm)
    assert result["route_share_contract"] == "frozen-2026-08"
    assert result["live"] is False and result["dry_run"] is True
    assert result["candidate_run_type"] == "live_shadow_dryrun"
    assert result["panel_run_id"].startswith("dryrun-live-shadow-")
    assert captured["candidate_run_type"] == "live_shadow_dryrun"


def test_frozen_contract_still_runs_live_before_week_5(monkeypatch):
    _arm(monkeypatch, "frozen-2026-08", "tail_k1", week=4)
    result, _ = _run_arm(monkeypatch, "control")
    assert result["live"] is True and result["week"] == 4


def test_companion_runs_live_from_week_5(monkeypatch):
    _arm(monkeypatch, "companion-v1", "tail_k1_route", week=5)
    result, _ = _run_arm(monkeypatch, "treatment")
    assert result["live"] is True
    assert result["route_share_contract"] == "companion-v1"


def test_contract_settings_sha256_is_the_published_identity():
    """Pinned for the gate amendment: canonical JSON (sorted keys, ',' ':')."""
    import hashlib
    import json

    from nfl_dfs.inference import tail_shadow

    for contract in ("frozen-2026-08", "companion-v1"):
        settings = dict(sorted(
            tail_shadow.route_share_contract_settings(contract).items()))
        digest = hashlib.sha256(json.dumps(
            settings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        receipt = tail_shadow.check_route_share_contract({
            **tail_shadow.route_share_job_environment(contract)})
        assert receipt["settings_sha256"] == digest
        assert receipt["settings_sha256"] == CONTRACT_SHA256[contract]
