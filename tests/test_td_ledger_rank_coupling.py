from __future__ import annotations

import copy

import numpy as np

from nfl_dfs.analysis import td_ledger_rank_coupling as coupling


def test_rank_coupling_preserves_exact_marginals_and_uses_source_order():
    control = np.asarray([
        [3.0, 1.0, 4.0, 2.0],
        [10.0, 40.0, 20.0, 30.0],
    ], dtype=np.float32)
    source = np.asarray([
        [100.0, 400.0, 200.0, 300.0],
        [0.4, 0.1, 0.3, 0.2],
    ])

    treatment = coupling.rank_couple_marginals(control, source)

    assert np.array_equal(np.sort(treatment, axis=1), np.sort(control, axis=1))
    assert treatment[0].tolist() == [1.0, 4.0, 2.0, 3.0]
    assert treatment[1].tolist() == [40.0, 10.0, 30.0, 20.0]


def test_rank_coupling_ties_are_stable_and_reproducible():
    control = np.asarray([[4.0, 1.0, 3.0, 2.0]])
    source = np.asarray([[0.0, 0.0, 1.0, 1.0]])
    first = coupling.rank_couple_marginals(control, source)
    second = coupling.rank_couple_marginals(control, source.copy())
    assert np.array_equal(first, second)
    assert first.tolist() == [[1.0, 2.0, 3.0, 4.0]]


def test_rank_coupling_disposition_names_do_not_reuse_prior_result():
    prior = {
        "disposition": "td-ledger-dependence-gate-passes",
        "exact80_licensed": True,
        "gate": {"passes": True},
    }
    result = coupling._remap_decision(copy.deepcopy(prior))
    assert result["disposition"] == "td-ledger-rank-coupling-gate-passes"
    assert result["exact80_licensed"]
