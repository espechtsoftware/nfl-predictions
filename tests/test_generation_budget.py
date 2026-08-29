"""Adopted boom-only generation budget.

The independent CE confirmation did not improve the primary score metric,
so production defaults to 0 CE / 40 boom. These tests pin that decision in
code and retain CE as an explicit research override only.
"""
import pytest

from nfl_dfs.backtest.engine import (DEFAULT_N_BOOM, DEFAULT_N_CE,
                                     GEN_TOTAL_BUDGET,
                                     resolve_generation_budget,
                                     resolve_leverage_solves)


def test_no_env_is_exactly_0_ce_40_boom_40_total():
    ce, epi, boom = resolve_generation_budget(env={})
    assert (ce, epi, boom) == (0, 0, 40)
    assert ce + epi + boom == GEN_TOTAL_BUDGET == 40
    assert (DEFAULT_N_CE, DEFAULT_N_BOOM) == (0, 40)


def test_explicit_ce_without_boom_keeps_total_at_40():
    ce, epi, boom = resolve_generation_budget(env={"N_CE": "20"})
    assert (ce, boom) == (20, 20) and ce + epi + boom == 40


def test_epistemic_also_draws_from_the_same_budget():
    ce, epi, boom = resolve_generation_budget(
        env={"N_CE": "8", "N_EPISTEMIC": "16"})
    assert (ce, epi, boom) == (8, 16, 16)
    assert ce + epi + boom == 40


def test_explicit_boom_is_an_override():
    ce, epi, boom = resolve_generation_budget(
        env={"N_CE": "12", "N_BOOM": "40"})
    assert (ce, boom) == (12, 40)          # verbatim, not 28
    ce, epi, boom = resolve_generation_budget(env={"N_BOOM": "0"})
    assert boom == 0


def test_no_double_subtraction_regression():
    """The bug a naive signature default would have caused: boom
    defaulting to a partial boom budget and then subtracting CE again."""
    _, _, boom = resolve_generation_budget(env={})
    assert boom == 40, f"double-subtracted to {boom}"


def test_ce_off_experiment_restores_full_boom_budget():
    ce, epi, boom = resolve_generation_budget(env={"N_CE": "0"})
    assert (ce, boom) == (0, 40)


def test_exact_leverage_override_expresses_boom_first_allocation():
    assert resolve_leverage_solves(2, 80, env={}) == 160
    assert resolve_leverage_solves(2, 80, env={"N_LEV": ""}) == 160
    assert resolve_leverage_solves(2, 80, env={"N_LEV": "40"}) == 40
    assert resolve_leverage_solves(0, 80, env={"N_LEV": "0"}) == 0


@pytest.mark.parametrize("value", ["-1", "01", " 40", "40.0", 40])
def test_exact_leverage_override_rejects_noncanonical_values(value):
    with pytest.raises(ValueError, match="N_LEV"):
        resolve_leverage_solves(2, 80, env={"N_LEV": value})


# --- bounds validation ---------------------------------------------------

def test_budget_is_clamped_when_ce_plus_epi_exceeds_total():
    """N_CE=50 previously produced 50 CE / 0 boom while still claiming a
    40-slot budget — a stated fixed total that wasn't fixed."""
    ce, epi, boom = resolve_generation_budget(env={"N_CE": "50"})
    assert ce + epi + boom == 40 and boom == 0
    ce, epi, boom = resolve_generation_budget(
        env={"N_CE": "30", "N_EPISTEMIC": "30"})
    assert ce + epi + boom == 40, (ce, epi, boom)
    # an EXPLICIT N_BOOM is still an override, not clamped
    ce, epi, boom = resolve_generation_budget(
        env={"N_CE": "30", "N_BOOM": "40"})
    assert (ce, boom) == (30, 40)


# --- effective-config visibility ----------------------------------------

def test_effective_config_flags_a_deployment_override():
    from nfl_dfs.backtest.engine import effective_generation_config

    ok = effective_generation_config(env={})
    assert ok["matches_adopted_default"] and ok["overrides"] == {}
    bad = effective_generation_config(env={"N_CE": "12", "N_BOOM": "28"})
    assert not bad["matches_adopted_default"]
    assert bad["overrides"] == {"N_CE": "12", "N_BOOM": "28"}
    assert bad["n_boom"] == 28
    boom_first = effective_generation_config(
        env={"N_LEV": "40", "N_BOOM": "160"}
    )
    assert boom_first["n_lev_override"] == 40
    assert boom_first["n_boom"] == 160
    assert boom_first["overrides"] == {"N_BOOM": "160", "N_LEV": "40"}
    assert not boom_first["matches_adopted_default"]
    # A research EPI override must not masquerade as the adopted budget.
    assert not effective_generation_config(
        env={"N_EPISTEMIC": "1", "N_BOOM": "40"})["matches_adopted_default"]
    assert not effective_generation_config(
        env={"N_GUMBEL": "20"})["matches_adopted_default"]
    role = effective_generation_config(env={
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": "target_share_last",
        "ROLE_BELIEF_SEED": "91",
    })
    # The generation counts remain baseline, but the research mechanism is
    # still surfaced for the deployment verifier to reject.
    assert not role["matches_adopted_default"]
    assert role["epistemic_family"] == "role_draws"
    assert role["role_belief_seed"] == 91
    assert role["overrides"]["ROLE_BELIEF_FEATURES"] == "target_share_last"
    td_rank = effective_generation_config(
        env={"TD_LEDGER_RANK_COUPLING": "1"})
    assert not td_rank["matches_adopted_default"]
    assert td_rank["overrides"] == {"TD_LEDGER_RANK_COUPLING": "1"}
    for key in ("OPEN_BOOM_SOLVES", "SINGLE_STACK_BOOM_SOLVES"):
        inactive = effective_generation_config(env={key: "0"})
        assert inactive["matches_adopted_default"]
        assert inactive["overrides"] == {key: "0"}
        active = effective_generation_config(env={key: "1"})
        assert not active["matches_adopted_default"]
        assert active["overrides"] == {key: "1"}


# --- fair pool-size control ---------------------------------------------

class _Lu:
    def __init__(self, tag, i):
        self.tag = tag
        self.i = i


def test_pool_cap_does_not_preferentially_drop_the_batch_under_test():
    """Tail truncation would discard CE, which is generated LAST — the
    exact candidates the experiment is measuring."""
    from nfl_dfs.backtest.engine import trim_pool_to_cap

    cands = ([_Lu("lev", i) for i in range(60)]
             + [_Lu("boom", i) for i in range(28)]
             + [_Lu("ce", i) for i in range(12)])       # appended last
    quotas = {"lev": 40, "boom": 28, "ce": 12}
    kept, retained, dropped = trim_pool_to_cap(cands, 80, quotas)
    assert len(kept) == 80
    # the essential property: the arm under test is untouched
    assert retained["ce"] == 12, f"CE trimmed to {retained.get('ce')}"
    assert dropped.get("ce", 0) == 0
    # drops are shared ROUND-ROBIN across the incumbent tags (the
    # earlier largest-surplus-first rule put all 20 on lev, which the
    # 2026-08-06 review flagged as an unbalanced baseline change)
    assert dropped["lev"] == 10 and dropped["boom"] == 10


def test_pool_cap_is_a_noop_below_the_cap():
    from nfl_dfs.backtest.engine import trim_pool_to_cap

    cands = [_Lu("ce", i) for i in range(5)]
    kept, retained, dropped = trim_pool_to_cap(cands, 50, {"ce": 12})
    assert len(kept) == 5 and dropped == {}


def test_pool_cap_trims_protected_only_as_a_last_resort():
    from nfl_dfs.backtest.engine import trim_pool_to_cap

    cands = [_Lu("boom", i) for i in range(28)] + [_Lu("ce", i)
                                                   for i in range(12)]
    kept, retained, dropped = trim_pool_to_cap(cands, 30, {"boom": 28,
                                                           "ce": 12})
    assert len(kept) == 30
    assert sum(retained.values()) == 30


# --- CE seed independence (2026-08-06 review) ----------------------------

def test_ce_seed_is_configurable_and_recorded():
    """The world search was pinned to a literal 1701, so an
    'independent seed' rerun would have re-drawn the SAME elite worlds
    and proved nothing."""
    from nfl_dfs.backtest.engine import effective_generation_config

    assert effective_generation_config(env={})["ce_seed"] == 1701
    cfg = effective_generation_config(env={"CE_SEED": "424242"})
    assert cfg["ce_seed"] == 424242
    assert cfg["overrides"]["CE_SEED"] == "424242"
    # a seed change must not disturb the budget
    assert (cfg["n_ce"], cfg["n_boom"]) == (0, 40)


def test_replay_projection_seed_is_visible_and_marks_research_override():
    from nfl_dfs.backtest.engine import effective_generation_config

    assert effective_generation_config(env={})["replay_projection_seed"] == 0
    cfg = effective_generation_config(
        env={"REPLAY_PROJECTION_SEED": "1137260708"})
    assert cfg["replay_projection_seed"] == 1137260708
    assert cfg["overrides"]["REPLAY_PROJECTION_SEED"] == "1137260708"
    assert not cfg["matches_adopted_default"]


def test_ce_seed_changes_the_sampled_worlds():
    import numpy as np

    from nfl_dfs.research.ce_worlds import sample_knobs

    a = sample_knobs(np.random.default_rng(1701), 8)
    b = sample_knobs(np.random.default_rng(424242), 8)
    same = sample_knobs(np.random.default_rng(1701), 8)
    assert np.allclose(a, same), "same seed must reproduce"
    assert not np.allclose(a, b), "different seed must explore elsewhere"


def test_gumbel_seed_is_configurable_reproducible_and_recorded():
    import numpy as np

    from nfl_dfs.backtest.engine import (_gumbel_rng,
                                         effective_generation_config)

    assert effective_generation_config(env={})["gumbel_seed"] == 4700
    cfg = effective_generation_config(env={"GUMBEL_SEED": "20260807"})
    assert cfg["gumbel_seed"] == 20260807
    assert cfg["overrides"]["GUMBEL_SEED"] == "20260807"
    a = _gumbel_rng({"GUMBEL_SEED": "20260807"}).gumbel(size=12)
    same = _gumbel_rng({"GUMBEL_SEED": "20260807"}).gumbel(size=12)
    b = _gumbel_rng({"GUMBEL_SEED": "20260808"}).gumbel(size=12)
    assert np.allclose(a, same)
    assert not np.allclose(a, b)


def test_hierarchical_gumbel_has_frozen_game_and_team_correlation():
    import numpy as np

    from nfl_dfs.backtest.engine import _gumbel_perturbations

    pool = [
        {"id": "a1", "game_id": "g1", "team": "A"},
        {"id": "a2", "game_id": "g1", "team": "A"},
        {"id": "b1", "game_id": "g1", "team": "B"},
        {"id": "c1", "game_id": "g2", "team": "C"},
    ]
    rng = np.random.default_rng(91)
    draws = np.stack([_gumbel_perturbations(
        pool, rng, 2.0, "hierarchical") for _ in range(5000)])
    corr = np.corrcoef(draws, rowvar=False)
    # Equal component variances imply approximately 2/3 correlation within
    # team, 1/3 across opponents, and zero across games.
    assert 0.58 < corr[0, 1] < 0.75
    assert 0.23 < corr[0, 2] < 0.43
    assert abs(corr[0, 3]) < 0.08
    assert corr[0, 1] > corr[0, 2] > corr[0, 3]


def test_unknown_gumbel_mode_fails_loudly():
    import numpy as np
    import pytest

    from nfl_dfs.backtest.engine import _gumbel_perturbations

    with pytest.raises(ValueError, match="GUMBEL_MODE"):
        _gumbel_perturbations([], np.random.default_rng(1), 2.0, "typo")


# --- trim fairness across ALL generator tags -----------------------------

def test_trim_round_robins_across_untested_tags():
    """Tags without a quota entry (game, dark, thesis...) must not be
    silently fully trim-eligible while others are spared."""
    from nfl_dfs.backtest.engine import trim_pool_to_cap

    cands = ([_Lu("lev", i) for i in range(40)]
             + [_Lu("boom", i) for i in range(28)]
             + [_Lu("game", i) for i in range(10)]
             + [_Lu("dark", i) for i in range(10)]
             + [_Lu("ce", i) for i in range(12)])
    kept, retained, dropped = trim_pool_to_cap(
        cands, 90, {"ce": 12, "epi": 0})
    assert len(kept) == 90
    assert retained["ce"] == 12 and "ce" not in dropped
    # the 10 drops are shared round-robin, not taken from one batch
    assert len(dropped) >= 3, f"trim concentrated: {dropped}"
    assert max(dropped.values()) <= 4, f"unbalanced trim: {dropped}"


def test_degenerate_trim_is_round_robin_not_index_order():
    """When protected alone exceeds the cap, drops must spread across
    tags rather than removing the latest-generated (CE) entries."""
    from nfl_dfs.backtest.engine import trim_pool_to_cap

    cands = [_Lu("epi", i) for i in range(10)] + [_Lu("ce", i)
                                                  for i in range(10)]
    kept, retained, dropped = trim_pool_to_cap(
        cands, 14, {"ce": 10, "epi": 10})
    assert len(kept) == 14
    assert dropped.get("ce", 0) == 3 and dropped.get("epi", 0) == 3, dropped


# --- per-slate cap manifest (2026-08-06 review) --------------------------

def test_per_slate_cap_map_beats_a_scalar_cap():
    """A single cap cannot equalize paired pools: realized counts vary
    ~157-174 per slate, so one number leaves some control slates under
    it and cuts some treatment slates and not others."""
    from nfl_dfs.backtest.engine import pool_cap_for_slate

    m = '{"2025-3": 161, "2025-4": 168}'
    assert pool_cap_for_slate(2025, 3, env={"GEN_POOL_CAP_MAP": m}) == 161
    assert pool_cap_for_slate(2025, 4, env={"GEN_POOL_CAP_MAP": m}) == 168
    # a slate missing from the manifest is left UNCAPPED (and warned),
    # never silently capped at some other slate's number
    assert pool_cap_for_slate(2025, 9, env={"GEN_POOL_CAP_MAP": m}) == 0
    # scalar remains available for exploratory (non-paired) use
    assert pool_cap_for_slate(2025, 3, env={"GEN_POOL_CAP": "160"}) == 160
    # a corrupt manifest falls back rather than crashing a panel
    assert pool_cap_for_slate(
        2025, 3, env={"GEN_POOL_CAP_MAP": "{oops", "GEN_POOL_CAP": "155"}) == 155


def test_paired_protection_keeps_equal_replacement_slots():
    """Treatment protects 12 CE; the control must protect 12 boom, or
    the cap retains the novel arm more aggressively than the incumbent
    it displaces."""
    from nfl_dfs.backtest.engine import REPLACEMENT_SLOTS, trim_pool_to_cap

    assert REPLACEMENT_SLOTS == 12
    treat = ([_Lu("lev", i) for i in range(60)]
             + [_Lu("boom", i) for i in range(28)]
             + [_Lu("ce", i) for i in range(12)])
    ctrl = ([_Lu("lev", i) for i in range(60)]
            + [_Lu("boom", i) for i in range(40)])
    _, rt, _ = trim_pool_to_cap(treat, 80, {"ce": 12, "epi": 0},
                                protect=("ce", "epi"))
    _, rc, _ = trim_pool_to_cap(ctrl, 80, {"boom": REPLACEMENT_SLOTS},
                                protect=("boom",))
    assert rt["ce"] == 12          # treatment keeps its replacement slots
    assert rc["boom"] >= 12        # control keeps an equal number


def test_gumbel_treatment_and_control_protect_equal_replacement_slots():
    from nfl_dfs.backtest.engine import trim_pool_to_cap

    treat = ([_Lu("lev", i) for i in range(60)]
             + [_Lu("boom", i) for i in range(20)]
             + [_Lu("gumbel", i) for i in range(20)])
    ctrl = ([_Lu("lev", i) for i in range(60)]
            + [_Lu("boom", i) for i in range(40)])
    _, rt, _ = trim_pool_to_cap(treat, 80, {"gumbel": 20},
                                protect=("gumbel",))
    _, rc, _ = trim_pool_to_cap(ctrl, 80, {"boom": 20},
                                protect=("boom",))
    assert rt["gumbel"] == 20
    assert rc["boom"] >= 20
