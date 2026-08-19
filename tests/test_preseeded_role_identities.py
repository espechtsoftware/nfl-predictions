"""Preseeded role identities (ATLAS C freeze Amendment 4): default None is
byte-identical; a nonzero role dose rejects preseeding; a preseeded
identity blocks exactly the post-role families' duplicate, mirroring the
source run's dedup."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine

PRE_SEAM_TAGS = {"lev", "thesis", "boom", "hyper", "ce"}


def _slate(n_worlds: int = 48):
    pool, ix = [], 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5200), ("WR", 12, 4800),
                        ("TE", 6, 3600), ("DST", 4, 2800)):
        for k in range(n):
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": f"T{ix % 4}", "opp": f"T{(ix + 1) % 4}",
                "game_id": f"g{ix % 2}", "salary": sal + 111 * k,
                "proj": 8.0 + (k % 6), "actual": 9.0 + (k % 7),
                "season": 2025, "week": 3})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(np.random.default_rng(7).normal(9, 4.5,
                                                   size=(len(pool), n_worlds)))
    return slate, pool, draws


def _run(preseeded=None):
    slate, pool, draws = _slate()
    captured = {}
    engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=4, stack=None,
        objective_col="proj", n_boom_solves=4,
        policy_env={"MIN_LINEUP_SALARY": "0"},
        candidate_capture=lambda b: captured.setdefault("batch", b),
        preseeded_role_identities=preseeded)
    return captured["batch"]


def test_default_none_is_byte_identical():
    first = _run()
    second = _run(preseeded=None)
    assert [c.ids for c in first.candidates] == \
        [c.ids for c in second.candidates]


def test_preseeded_identity_blocks_post_role_duplicate():
    base = _run()
    post_seam = [c for c in base.candidates if c.tag not in PRE_SEAM_TAGS]
    assert post_seam, "fixture produced no post-seam family candidates"
    target = post_seam[0]
    blocked = _run(preseeded=[target.ids])
    identities = {c.ids for c in blocked.candidates}
    assert target.ids not in identities
    # Pre-seam families are untouched: their candidates all survive.
    for candidate in base.candidates:
        if candidate.tag in PRE_SEAM_TAGS:
            assert candidate.ids in identities


def test_preseed_requires_zero_role_dose():
    slate, pool, draws = _slate()
    with pytest.raises(ValueError, match="zero role dose"):
        engine.tail_select_lineups(
            slate, pool, draws, tail_line=95.0, n_entries=4, stack=None,
            objective_col="proj", n_boom_solves=4,
            policy_env={"MIN_LINEUP_SALARY": "0", "N_EPISTEMIC": "2",
                        "EPISTEMIC_FAMILY": "standard"},
            preseeded_role_identities=[frozenset(
                p["id"] for p in pool[:9])])


def test_preseed_rejects_malformed_identity():
    slate, pool, draws = _slate()
    with pytest.raises(ValueError, match="nine unique"):
        engine.tail_select_lineups(
            slate, pool, draws, tail_line=95.0, n_entries=4, stack=None,
            objective_col="proj", n_boom_solves=4,
            policy_env={"MIN_LINEUP_SALARY": "0"},
            preseeded_role_identities=[frozenset({"a", "b"})])
