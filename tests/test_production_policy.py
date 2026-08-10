from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY


def test_adopted_policy_is_the_promoted_true80_k1_ce_book():
    p = ADOPTED_CLASSIC_POLICY
    assert p.policy_id == "classic-k1-ce12-role12-boom28-v2"
    assert p.source_panel == "20260810-e80-k1-ce12-roleunion-c616390"
    assert (p.model_variant, p.model_ensemble) == ("tail_k1", 1)
    assert p.role_model_variant == "tail_k1_role"
    assert (p.default_entries, p.tail_line) == (80, 194.0)
    assert (p.n_ce, p.n_role, p.n_boom, p.min_lineup_salary) == (
        12, 12, 28, 49_000)
    assert p.blend_model_weight == 0.45


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
    assert dirty["MODEL_ENSEMBLE"] == "3"
    assert env["GCP_PROJECT"] == "keep-me"
    assert env["MODEL_ENSEMBLE"] == "1"
    assert (env["N_CE"], env["N_EPISTEMIC"], env["N_BOOM"]) == (
        "12", "12", "28")
    assert env["EPISTEMIC_FAMILY"] == "role_draws"
    assert env["ROLE_BELIEF_SEED"] == "7331"
    assert env["SELECT_LSE"] == "0"
    assert env["MIN_LINEUP_SALARY"] == "49000"
    assert env["N_GUMBEL"] == "0"
    assert env["GEN_POOL_CAP"] == "0"

    fallback = ADOPTED_CLASSIC_POLICY.fallback_environment(dirty)
    assert (fallback["N_CE"], fallback["N_EPISTEMIC"],
            fallback["N_BOOM"]) == ("12", "0", "28")
    assert fallback["EPISTEMIC_FAMILY"] == "standard"
