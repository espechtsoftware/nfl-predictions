import pytest

from nfl_dfs.inference.production_policy import (
    ADOPTED_CLASSIC_POLICY,
    contest_entry_policy,
)


@pytest.mark.parametrize(
    ("limit", "entries", "profile", "cap"),
    [
        (1, 1, "single-entry-individual-tail", 0.70),
        (3, 3, "three-max-self-sufficient-tail", 0.80),
        (20, 20, "compact-max-tail-coverage", 0.90),
        (150, 80, "large-max-tail-coverage", 1.00),
    ],
)
def test_contest_entry_policy_profiles(limit, entries, profile, cap):
    result = contest_entry_policy(limit, entries, 1.25)
    assert result["profile"] == profile
    assert result["effective_leverage_scale"] == cap
    assert result["selection"] == (
        "first-N-adopted-CBWU-tail-coverage-order")
    assert result["candidate_entry_basis"] == 80
    assert result["tail_line_changed"] is False
    assert "pending separate low-max validation" in result["evidence"]


@pytest.mark.parametrize("limit,entries", [(1, 2), (20, 21), (150, 81)])
def test_contest_entry_policy_rejects_book_beyond_limit(limit, entries):
    with pytest.raises(ValueError, match="requested entries"):
        contest_entry_policy(limit, entries, 1.0)


def test_adopted_policy_is_the_promoted_true80_position_calibrated_book():
    p = ADOPTED_CLASSIC_POLICY
    assert p.policy_id == "classic-k1-role12-boom40-poscal-cbwu-v4"
    assert p.source_panel == (
        "20260813-multiseed-candidate-world-v1")
    assert (p.model_variant, p.model_ensemble) == ("tail_k1", 1)
    assert p.role_model_variant == "tail_k1_role"
    assert (p.default_entries, p.tail_line) == (80, 194.0)
    assert (p.n_ce, p.n_role, p.n_boom, p.min_lineup_salary) == (
        0, 12, 40, 49_000)
    assert p.blend_model_weight == 0.45
    assert p.served_position_scales == (
        "QB:0.970,RB:1.005,TE:0.940,WR:1.070")
    assert p.multiseed_portfolio == "CBWU"
    assert len(p.multiseed_seed_pairs) == 5
    assert p.multiseed_worlds_per_block == 10_000


def test_policy_overwrites_research_levers_without_mutating_base():
    dirty = {
        "GCP_PROJECT": "keep-me",
        "MODEL_ENSEMBLE": "3",
        "N_CE": "0",
        "N_BOOM": "40",
        "SELECT_LSE": "0.2",
        "MIN_LINEUP_SALARY": "0",
        "N_GUMBEL": "20",
        "GEN_POOL_CAP": "99",
    }
    env = ADOPTED_CLASSIC_POLICY.engine_environment(dirty)
    assert env["TABPFN_MARGINAL_TABLE"] == ""
    assert dirty["MODEL_ENSEMBLE"] == "3"
    assert env["GCP_PROJECT"] == "keep-me"
    assert env["MODEL_ENSEMBLE"] == "1"
    assert (env["N_CE"], env["N_EPISTEMIC"], env["N_BOOM"]) == (
        "0", "12", "40")
    assert env["EPISTEMIC_FAMILY"] == "role_draws"
    assert env["ROLE_BELIEF_SEED"] == "7331"
    assert env["SELECT_LSE"] == "0"
    assert env["MIN_LINEUP_SALARY"] == "49000"
    assert env["N_GUMBEL"] == "0"
    assert env["GEN_POOL_CAP"] == "0"
    assert env["SERVED_POSITION_SCALES"] == (
        "QB:0.970,RB:1.005,TE:0.940,WR:1.070")
    assert env["MULTISEED_PORTFOLIO"] == "CBWU"
    assert env["MULTISEED_WORLDS_PER_BLOCK"] == "10000"
    assert env["MULTISEED_CANDIDATE_ENTRY_BASIS"] == "80"
    assert env["MULTISEED_SEED_PAIRS"].startswith("R0=0:7331;R1=")

    fallback = ADOPTED_CLASSIC_POLICY.fallback_environment(dirty)
    assert (fallback["N_CE"], fallback["N_EPISTEMIC"],
            fallback["N_BOOM"]) == ("12", "0", "28")
    assert fallback["EPISTEMIC_FAMILY"] == "standard"
    assert fallback["SERVED_POSITION_SCALES"] == ""
    assert fallback["MULTISEED_PORTFOLIO"] == ""

    shadow = ADOPTED_CLASSIC_POLICY.archetype_shadow_environment(dirty)
    assert shadow["MULTISEED_PORTFOLIO"] == "CBWU_ARCHETYPE_SHADOW"
    assert shadow["ARCHETYPE_ALLOCATION_VERSION"] == (
        "prospective-archetype-allocation-v1"
    )
    assert shadow["ARCHETYPE_TAIL_LINE"] == "194.0"
    assert shadow["PROSPECTIVE_SHADOW_ID"] == "2026-archetype-cbwu-v1"
    assert shadow["MULTISEED_SEED_PAIRS"] == env["MULTISEED_SEED_PAIRS"]
    assert shadow["N_EPISTEMIC"] == env["N_EPISTEMIC"]

    latent = ADOPTED_CLASSIC_POLICY.latent_role_shadow_environment(dirty)
    assert latent["MULTISEED_PORTFOLIO"] == "CBWU_LATENT_ROLE_SHADOW"
    assert latent["EPISTEMIC_FAMILY"] == "latent_role_states"
    assert latent["ROLE_BELIEF_FEATURES"] == ""
    assert latent["PROSPECTIVE_LATENT_ROLE_VERSION"] == (
        "prospective-latent-role-state-v1"
    )
    assert latent["PROSPECTIVE_SHADOW_ID"] == "2026-latent-role-cbwu-v1"
    assert latent["MULTISEED_SEED_PAIRS"] == env["MULTISEED_SEED_PAIRS"]
    assert (latent["N_EPISTEMIC"], latent["N_BOOM"]) == ("12", "40")


def test_public_identity_exposes_fixed_budget_five_by_five_contract():
    identity = ADOPTED_CLASSIC_POLICY.public_identity(entries=40)
    portfolio = identity["candidate_world_portfolio"]
    assert portfolio == {
        "arm": "CBWU",
        "candidate_searches": 5,
        "fixed_candidate_budget": True,
        "candidate_entry_basis": 80,
        "world_blocks": 5,
        "worlds_per_block": 10_000,
        "selection_worlds": 50_000,
        "fail_closed": True,
    }
    assert identity["entries"] == 40
    assert identity["simulation_law"] == {
        "game_mode": "possession",
        "team_factors": True,
        "usage_allocation": "production-multinomial",
        "game_sim_usage_env": "",
        "dirichlet_k": None,
        "td_ledger": False,
    }
