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
    assert retained["ce"] == 12, f"CE trimmed to {retained.get('ce')}"
    assert retained["boom"] == 28
    assert dropped.get("ce", 0) == 0 and dropped["lev"] == 20


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
