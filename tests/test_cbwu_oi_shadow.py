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


# --- O-27 (2026-10-05): declared collection contracts -----------------------

FROZEN = prospective_shadow.CBWU_OI_FROZEN_V1
COMPANION = prospective_shadow.CBWU_OI_COMPANION_V1
COMPANION_SHA256 = "9849d07f0ff22a57f75d10a1e4dc909647ca86563eadc134ed6eaf2d5eff4081"
FROZEN_SHA256 = "6d68946b27ca35ace348e7ce08340b22566d806a7caebc3815ea0f989feb425e"
SEEDS = ("R0=0:7331;R1=1137260708:2690847602;R2=2875959182:1630284992;"
         "R3=253722715:3374646876;R4=1643280042:3977633467")
# The companion's derived values, written out once so a production_policy change
# shows up here as a deliberate edit (and a new published sha), never silently.
COMPANION_LITERALS = {
    "GEN_TOTAL_BUDGET": "172", "N_LEV": "40", "N_CE": "0", "N_EPISTEMIC": "12",
    "N_BOOM": "160", "N_GUMBEL": "0", "REPLACEMENT_SLOTS": "12",
    "BOOM_UNIQUE_FILL": "0", "EPISTEMIC_FAMILY": "role_draws",
    "ROLE_BELIEF_FEATURES": ("target_share_last,carry_share_last,snap_share_last,"
                             "target_share_jump,carry_share_jump,snap_share_jump"),
    "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701", "BLEND_MODEL_WEIGHT": "0.45",
    "LIVE_SIMS": "30000", "GAME_SIM_MODE": "possession",
    "SERVED_POSITION_SCALES": "QB:0.970,RB:1.005,TE:0.940,WR:1.070",
    "MODEL_ENSEMBLE": "1", "MIN_LINEUP_SALARY": "49000",
    "MULTISEED_SEED_PAIRS": SEEDS, "MULTISEED_WORLDS_PER_BLOCK": "10000",
    "MULTISEED_CANDIDATE_ENTRY_BASIS": "80", "SELECT_LSE": "0",
    "MULTISEED_PORTFOLIO": "CBWU_OI_SHADOW",
}


def _receipt(contract):
    environ = prospective_shadow.cbwu_oi_job_environment(contract)
    build, _ = prospective_shadow.cbwu_oi_environment(contract, environ)
    return prospective_shadow.check_cbwu_oi_contract(environ, build)


def test_companion_settings_are_derived_from_the_money_path_and_pinned():
    derived = prospective_shadow.cbwu_oi_companion_v1_settings()
    assert derived == COMPANION_LITERALS
    money = ADOPTED_CLASSIC_POLICY.engine_environment({})
    for key in prospective_shadow.CBWU_OI_COMPANION_V1_KEYS:
        assert derived[key] == money[key], key
    assert money["MULTISEED_PORTFOLIO"] == "CBWU"  # only the treatment law differs
    receipt = _receipt(COMPANION)
    assert receipt["contract"] == COMPANION
    assert receipt["settings"]["ENTRIES"] == "80"
    assert receipt["settings"]["TAIL_LINE"] == "194.0"
    assert receipt["settings_sha256"] == COMPANION_SHA256


def test_companion_build_is_the_money_path_with_only_the_law_swapped():
    environ = prospective_shadow.cbwu_oi_job_environment(COMPANION)
    build, control = prospective_shadow.cbwu_oi_environment(COMPANION, environ)
    money = ADOPTED_CLASSIC_POLICY.engine_environment(environ)
    changed = {k for k in set(build) | set(money) if build.get(k) != money.get(k)}
    assert changed == {"MULTISEED_PORTFOLIO", "PROSPECTIVE_SHADOW_ID"}
    assert build["MULTISEED_PORTFOLIO"] == "CBWU_OI_SHADOW"
    assert control == money


def test_frozen_settings_are_literals_not_policy_reads():
    """A later production_policy change must trip the check, not move it."""
    frozen = dict(prospective_shadow.CBWU_OI_FROZEN_SETTINGS)
    assert frozen["GEN_TOTAL_BUDGET"] == "52"
    assert (frozen["N_LEV"], frozen["N_BOOM"]) == ("160", "40")
    assert frozen["MULTISEED_SEED_PAIRS"] == SEEDS
    with pytest.raises(TypeError):
        prospective_shadow.CBWU_OI_FROZEN_SETTINGS["N_BOOM"] = "160"
    assert _receipt(FROZEN)["settings_sha256"] == FROZEN_SHA256


@pytest.mark.parametrize("declared", [None, "", "2026-cbwu-oi-v2", "companion-v1"])
def test_contract_must_be_declared_exactly(declared):
    environ = {} if declared is None else {
        prospective_shadow.CBWU_OI_CONTRACT_ENV: declared}
    build, _ = prospective_shadow.cbwu_oi_environment(COMPANION, {})
    with pytest.raises(RuntimeError, match="requires CBWU_OI_CONTRACT in"):
        prospective_shadow.check_cbwu_oi_contract(environ, build)


@pytest.mark.parametrize("contract", [FROZEN, COMPANION])
@pytest.mark.parametrize("key,value", [
    ("N_BOOM", "28"),
    ("N_LEV", "80"),
    ("GEN_TOTAL_BUDGET", "40"),
    ("MULTISEED_PORTFOLIO", "CBWU"),   # treatment law silently dropped
    ("MULTISEED_SEED_PAIRS", "R0=0:7331"),
    ("SELECT_LSE", "1"),
    ("N_CE", "12"),
])
def test_contract_refuses_any_drift_in_the_built_env(contract, key, value):
    environ = prospective_shadow.cbwu_oi_job_environment(contract)
    build, _ = prospective_shadow.cbwu_oi_environment(contract, environ)
    build[key] = value
    with pytest.raises(RuntimeError, match="contradicts its declared contract"):
        prospective_shadow.check_cbwu_oi_contract(environ, build)


@pytest.mark.parametrize("key,value", [
    ("N_BOOM", "40"),            # the frozen 160/40 allocation on a companion job
    ("N_LEV", "160"),
    ("SERVED_POSITION_SCALES", ""),
    ("MULTISEED_PORTFOLIO", None),
])
def test_companion_job_env_must_equal_the_derived_settings(key, value):
    environ = prospective_shadow.cbwu_oi_job_environment(COMPANION)
    if value is None:
        environ.pop(key)
    else:
        environ[key] = value
    build, _ = prospective_shadow.cbwu_oi_environment(COMPANION, environ)
    with pytest.raises(RuntimeError, match="job env contradicts the adopted money path"):
        prospective_shadow.check_cbwu_oi_contract(environ, build)


def test_frozen_contract_is_refused_live_from_week_5_but_not_as_a_dry_run():
    require = prospective_shadow.require_live_cbwu_oi_contract
    with pytest.raises(RuntimeError, match="may not freeze a live panel"):
        require(FROZEN, 2026, 5, dry_run=False)
    with pytest.raises(RuntimeError, match="may not freeze a live panel"):
        require(FROZEN, 2027, 1, dry_run=False)
    require(FROZEN, 2026, 5, dry_run=True)      # labelled non-live book / replay
    require(FROZEN, 2026, 4, dry_run=False)     # its own weeks stay its own
    require(COMPANION, 2026, 5, dry_run=False)


def test_contract_identities_never_overlap():
    frozen_prefix, frozen_type = prospective_shadow.CBWU_OI_IDENTITIES[FROZEN]
    comp_prefix, comp_type = prospective_shadow.CBWU_OI_IDENTITIES[COMPANION]
    assert frozen_prefix == "prospective-cbwu-oi"   # the Week-1 panel's identity
    assert not comp_prefix.startswith(frozen_prefix)
    assert not frozen_prefix.startswith(comp_prefix)
    assert frozen_type != comp_type


def test_only_the_cbwu_oi_variant_carries_a_contract():
    variants = prospective_shadow.SHADOW_VARIANTS
    assert "contract_build" in variants["cbwu_oi"]
    assert "contract_build" not in variants["archetype"]
    assert "contract_build" not in variants["cbwu_volume"]
