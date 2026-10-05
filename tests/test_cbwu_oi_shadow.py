"""CBWU-OI prospective shadow wiring: policy env, variant table, dispatch.

Spec: reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md (frozen before
first collection). These tests pin the two-key env delta from the frozen
pre-adoption control, the variant registry, and that production paths remain
untouched.
"""

import pytest

from nfl_dfs.inference import prospective_shadow
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY


def test_cbwu_oi_shadow_retains_frozen_pre_adoption_population():
    money = ADOPTED_CLASSIC_POLICY.engine_environment({})
    control = ADOPTED_CLASSIC_POLICY.incumbent_control_environment({})
    shadow = ADOPTED_CLASSIC_POLICY.cbwu_oi_shadow_environment({})
    assert shadow["MULTISEED_PORTFOLIO"] == "CBWU_OI_SHADOW"
    assert shadow["PROSPECTIVE_SHADOW_ID"] == "2026-cbwu-oi-v1"
    changed = {
        key for key in set(control) | set(shadow)
        if control.get(key) != shadow.get(key)
    }
    assert changed == {"MULTISEED_PORTFOLIO", "PROSPECTIVE_SHADOW_ID"}
    assert (shadow["N_LEV"], shadow["N_BOOM"]) == ("160", "40")
    assert (money["N_LEV"], money["N_BOOM"]) == ("40", "160")


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


# --- O-27 (2026-10-05): declared, frozen collection contract ----------------

def _shadow_env():
    policy = ADOPTED_CLASSIC_POLICY
    env = policy.cbwu_oi_shadow_environment({})
    env.update(policy.construction_preset().optimizer_environment())
    return env


DECLARED = {prospective_shadow.CBWU_OI_CONTRACT_ENV: "2026-cbwu-oi-v1"}


def test_frozen_contract_is_what_the_policy_builds_today():
    """The frozen literals equal what production_policy derives for the shadow.

    If this fails, production_policy changed something the 2026-08-18 spec
    froze; the fix is an amendment to the spec, never an edit of the literals.
    """
    receipt = prospective_shadow.check_cbwu_oi_contract(DECLARED, _shadow_env())
    assert receipt["contract"] == "2026-cbwu-oi-v1"
    assert receipt["settings"]["N_LEV"] == "160"
    assert receipt["settings"]["N_BOOM"] == "40"
    assert receipt["settings"]["MULTISEED_PORTFOLIO"] == "CBWU_OI_SHADOW"
    assert receipt["settings"]["ENTRIES"] == "80"
    assert receipt["settings"]["TAIL_LINE"] == "194.0"
    assert len(receipt["settings_sha256"]) == 64


def test_frozen_settings_are_literals_not_policy_reads():
    """A later production_policy change must trip the check, not move it."""
    frozen = dict(prospective_shadow.CBWU_OI_FROZEN_SETTINGS)
    assert frozen["GEN_TOTAL_BUDGET"] == "52"
    assert frozen["MULTISEED_SEED_PAIRS"].startswith("R0=0:7331;R1=1137260708:")
    with pytest.raises(TypeError):
        prospective_shadow.CBWU_OI_FROZEN_SETTINGS["N_BOOM"] = "160"


@pytest.mark.parametrize("declared", [None, "", "2026-cbwu-oi-v2", "companion-v1"])
def test_contract_must_be_declared_exactly(declared):
    environ = {} if declared is None else {
        prospective_shadow.CBWU_OI_CONTRACT_ENV: declared}
    with pytest.raises(RuntimeError, match="requires CBWU_OI_CONTRACT"):
        prospective_shadow.check_cbwu_oi_contract(environ, _shadow_env())


@pytest.mark.parametrize("key,value", [
    ("N_BOOM", "160"),                 # the money path's boom-first allocation
    ("N_LEV", "40"),
    ("GEN_TOTAL_BUDGET", "172"),
    ("MULTISEED_PORTFOLIO", "CBWU"),   # treatment law silently dropped
    ("MULTISEED_SEED_PAIRS", "R0=0:7331"),
    ("SELECT_LSE", "1"),
    ("N_CE", "12"),
])
def test_contract_refuses_any_drift_from_the_frozen_comparison(key, value):
    env = _shadow_env()
    env[key] = value
    with pytest.raises(RuntimeError, match="contradicts its frozen contract"):
        prospective_shadow.check_cbwu_oi_contract(DECLARED, env)


def test_only_the_cbwu_oi_variant_carries_the_contract():
    variants = prospective_shadow.SHADOW_VARIANTS
    assert variants["cbwu_oi"]["contract_check"] is (
        prospective_shadow.check_cbwu_oi_contract)
    assert "contract_check" not in variants["archetype"]
    assert "contract_check" not in variants["cbwu_volume"]
