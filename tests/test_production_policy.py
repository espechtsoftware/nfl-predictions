from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY


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
