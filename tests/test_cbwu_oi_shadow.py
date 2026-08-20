"""CBWU-OI prospective shadow wiring: policy env, variant table, dispatch.

Spec: reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md (frozen before
first collection). These tests pin the two-key env delta, the variant
registry, and that production paths remain untouched.
"""

import pytest

from nfl_dfs.inference import prospective_shadow
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY


def test_cbwu_oi_shadow_env_changes_exactly_two_keys():
    money = ADOPTED_CLASSIC_POLICY.engine_environment({})
    shadow = ADOPTED_CLASSIC_POLICY.cbwu_oi_shadow_environment({})
    assert shadow["MULTISEED_PORTFOLIO"] == "CBWU_OI_SHADOW"
    assert shadow["PROSPECTIVE_SHADOW_ID"] == "2026-cbwu-oi-v1"
    changed = {
        key for key in set(money) | set(shadow)
        if money.get(key) != shadow.get(key)
    }
    assert changed == {"MULTISEED_PORTFOLIO", "PROSPECTIVE_SHADOW_ID"}


def test_production_engine_environment_is_untouched():
    env = ADOPTED_CLASSIC_POLICY.engine_environment({})
    assert env["MULTISEED_PORTFOLIO"] == "CBWU"
    assert "PROSPECTIVE_SHADOW_ID" not in env


def test_variant_registry_has_every_shadow():
    """Pins the registry: a new shadow variant must be added here
    deliberately, never by accident."""
    assert set(prospective_shadow.SHADOW_VARIANTS) == {
        "archetype", "cbwu_oi", "cbwu_volume",
    }
    spec = prospective_shadow.SHADOW_VARIANTS["cbwu_oi"]
    assert spec["env_method"] == "cbwu_oi_shadow_environment"
    assert spec["panel_prefix"] == "prospective-cbwu-oi"
    assert spec["candidate_run_type"] == "prospective_cbwu_oi_shadow"
    volume = prospective_shadow.SHADOW_VARIANTS["cbwu_volume"]
    assert volume["env_method"] == "cbwu_volume_shadow_environment"
    assert volume["panel_prefix"] == "prospective-cbwu-volume"
    assert volume["candidate_run_type"] == "prospective_cbwu_volume_shadow"
    # Every named env method must exist on the adopted policy.
    for variant in prospective_shadow.SHADOW_VARIANTS.values():
        assert hasattr(ADOPTED_CLASSIC_POLICY, variant["env_method"])


def test_unknown_variant_fails_closed():
    with pytest.raises(ValueError, match="unknown prospective shadow"):
        prospective_shadow.run_paired_prospective_shadow(variant="bogus")


def test_dispatch_accepts_oi_portfolio_and_control_capture():
    import inspect

    from nfl_dfs.inference import live_lineups

    source = inspect.getsource(live_lineups)
    assert '"CBWU_OI_SHADOW"' in source
    guard = source.split("paired control capture requires", 1)[0]
    assert "CBWU_OI_SHADOW" in guard.rsplit("multiseed_portfolios", 1)[1]


def test_archetype_defaults_unchanged():
    spec = prospective_shadow.SHADOW_VARIANTS["archetype"]
    assert spec["panel_prefix"] == "prospective-archetype"
    assert spec["candidate_run_type"] == "prospective_archetype_shadow"
    import inspect

    signature = inspect.signature(
        prospective_shadow.run_paired_prospective_shadow)
    assert signature.parameters["variant"].default == "archetype"
