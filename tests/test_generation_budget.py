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
