"""Adopted generation budget (2026-08-06 CE adoption).

CE was live in production ONLY through Cloud Run env vars while the
code defaulted to CE-off, so any redeploy without those vars silently
reverted generation to boom-only — invisible to both the test suite
and the config manifest. These tests pin the resolver's rules so the
adopted configuration is a code fact.
"""
from nfl_dfs.backtest.engine import (DEFAULT_N_BOOM, DEFAULT_N_CE,
                                     GEN_TOTAL_BUDGET,
                                     resolve_generation_budget)


def test_no_env_is_exactly_12_ce_28_boom_40_total():
    ce, epi, boom = resolve_generation_budget(env={})
    assert (ce, epi, boom) == (12, 0, 28)
    assert ce + epi + boom == GEN_TOTAL_BUDGET == 40
    assert (DEFAULT_N_CE, DEFAULT_N_BOOM) == (12, 28)


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
    defaulting to 28 AND then subtracting CE, giving 16."""
    _, _, boom = resolve_generation_budget(env={})
    assert boom == 28, f"double-subtracted to {boom}"


def test_ce_off_experiment_restores_full_boom_budget():
    ce, epi, boom = resolve_generation_budget(env={"N_CE": "0"})
    assert (ce, boom) == (0, 40)


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
    bad = effective_generation_config(env={"N_CE": "0"})
    assert not bad["matches_adopted_default"]
    assert bad["overrides"] == {"N_CE": "0"} and bad["n_boom"] == 40


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
    assert (cfg["n_ce"], cfg["n_boom"]) == (12, 28)


def test_ce_seed_changes_the_sampled_worlds():
    import numpy as np

    from nfl_dfs.research.ce_worlds import sample_knobs

    a = sample_knobs(np.random.default_rng(1701), 8)
    b = sample_knobs(np.random.default_rng(424242), 8)
    same = sample_knobs(np.random.default_rng(1701), 8)
    assert np.allclose(a, same), "same seed must reproduce"
    assert not np.allclose(a, b), "different seed must explore elsewhere"


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
