"""Pair support: which players are individually admitted but never joined.

Calibrated on Week 2 of 2026. The Millionaire winner's roster shared 35 of its 36
pairs with the 12,555-candidate pool; the one absent pair was Kittle + Schultz,
two tight ends ranked 8th and 6th of 95 by our own projection. The generator
built 1,735 two-TE lineups but only 380 distinct TE pairs, so an 8th-ranked TE
never met a 6th-ranked one. This measures that from the pool alone, before any
outcome exists.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "pool_pair_support.py"
_spec = importlib.util.spec_from_file_location("pool_pair_support", _SRC)
pps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pps)

INFO = {f"te{i}": ("TE", 15.0 - i) for i in range(5)}
INFO.update({f"wr{i}": ("WR", 20.0 - i) for i in range(5)})


class TestPairSupport:
    def test_it_counts_distinct_pairs_not_occurrences(self):
        rosters = [["te0", "te1", "wr0"]] * 10
        s = pps.pair_support(rosters, INFO, "TE")
        assert s["distinct_pairs"] == 1
        assert s["repetition_factor"] == pytest.approx(10.0)

    def test_the_denominator_is_achievable_not_theoretical(self):
        """A pool of N two-TE lineups can hold at most N distinct pairs, however
        many exist in principle. Using the theoretical count understates coverage
        whenever the shape is rare — which is exactly the TE case."""
        rosters = [["te0", "te1", "wr0"], ["te2", "te3", "wr0"]]
        s = pps.pair_support(rosters, INFO, "TE")
        assert s["lineups_with_two_or_more"] == 2
        assert s["achievable_pairs"] == 2
        assert s["share_of_achievable"] == pytest.approx(1.0)
        assert s["share_of_possible"] < 1.0

    def test_a_position_never_doubled_reports_no_pairs(self):
        """QB appears once per lineup, so it has no pair space at all."""
        info = dict(INFO, qb0=("QB", 20.0), qb1=("QB", 19.0))
        s = pps.pair_support([["qb0", "te0", "wr0"]], info, "QB")
        assert s["distinct_pairs"] == 0 and s["share_of_achievable"] is None

    def test_players_are_counted_even_when_unpaired(self):
        s = pps.pair_support([["te0", "wr0", "wr1"]], INFO, "TE")
        assert s["players_used"] == 1 and s["distinct_pairs"] == 0

    def test_pair_order_does_not_create_duplicates(self):
        rosters = [["te1", "te0"], ["te0", "te1"]]
        assert pps.pair_support(rosters, INFO, "TE")["distinct_pairs"] == 1


class TestPartnerCoverage:
    def test_coverage_is_a_share_of_peers_not_a_raw_count(self):
        """Raw counts are incomparable across positions: in Week 2 the top WRs
        met 90-127 peers and the top TEs 19-52, purely because WR slots are more
        numerous. As a share the gap is the real signal."""
        rosters = [["te0", "te1"], ["te0", "te2"]]
        s = pps.pair_support(rosters, INFO, "TE")
        rows = {r["player"]: r for r in pps.under_paired(s, INFO, top=5)}
        assert rows["te0"]["distinct_partners"] == 2
        assert rows["te0"]["partner_coverage"] == pytest.approx(2 / 2)
        assert rows["te1"]["partner_coverage"] == pytest.approx(1 / 2)

    def test_a_widely_paired_player_reaches_full_coverage(self):
        rosters = [["te0", f"te{i}"] for i in range(1, 5)]
        s = pps.pair_support(rosters, INFO, "TE")
        rows = {r["player"]: r for r in pps.under_paired(s, INFO, top=5)}
        assert rows["te0"]["partner_coverage"] == pytest.approx(1.0)

    def test_rows_come_back_in_projection_order(self):
        rosters = [["te0", "te1"], ["te2", "te3"]]
        s = pps.pair_support(rosters, INFO, "TE")
        rows = pps.under_paired(s, INFO, top=4)
        assert [r["projection_rank"] for r in rows] == [1, 2, 3, 4]
        assert rows[0]["projection"] >= rows[-1]["projection"]

    def test_the_week2_blind_spot_shape_is_flagged(self):
        """A well-projected player meeting few peers is the thing to surface."""
        rosters = [["te0", "te1"]] * 50 + [["te0", "te2"]] * 50 + [["te3", "te4"]]
        s = pps.pair_support(rosters, INFO, "TE")
        rows = {r["player"]: r for r in pps.under_paired(s, INFO, top=5)}
        assert rows["te3"]["partner_coverage"] < 0.5
        assert rows["te0"]["partner_coverage"] > rows["te3"]["partner_coverage"]


class TestItRefusesBadInput:
    def test_a_pool_without_names_is_rejected(self, tmp_path):
        p = tmp_path / "pool.csv"
        p.write_text("cand\n1\n")
        with pytest.raises(SystemExit) as e:
            pps.main(["--pool", str(p), "--season", "2026", "--week", "2"])
        assert "names" in str(e.value)
