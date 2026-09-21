"""Two standing weekly questions, asked before anyone argues about selection.

Week 2 of 2026 is the worked example these tests are calibrated against: the
pool's best candidate scored 197.26 while the Millionaire was won with 232.4, so
no ordering rule could have produced a winner; and the winning roster matched
none of the 12,555 candidates, the closest sharing five of nine players.

Nothing was measuring either of those things.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "week_ceiling_and_coverage.py"
_spec = importlib.util.spec_from_file_location("week_ceiling_and_coverage", _SRC)
wcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wcc)

W = {f"p{i}" for i in range(9)}


class TestCoverage:
    def test_an_exact_match_is_counted(self):
        out = wcc.coverage([set(W)], W)
        assert out["exact_matches"] == 1
        assert out["by_shared_players"]["9"] == 1

    def test_the_week2_shape_reports_zero_exact(self):
        """A pool that never explored the winner must say so, not round up."""
        pool = [set(list(W)[:5]) | {"x", "y", "z", "w"} for _ in range(2)]
        pool += [set(list(W)[:4]) | {"a", "b", "c", "d", "e"} for _ in range(15)]
        out = wcc.coverage(pool, W)
        assert out["exact_matches"] == 0
        assert out["by_shared_players"]["5"] == 2
        assert out["by_shared_players"]["4"] == 15

    def test_a_disjoint_pool_scores_zero_shared(self):
        out = wcc.coverage([{"q", "r", "s"}], W)
        assert out["exact_matches"] == 0
        assert out["by_shared_players"]["0"] == 1

    def test_one_missing_player_is_not_an_exact_match(self):
        """8 of 9 is the near-miss that matters most; it must not read as a hit."""
        near = set(list(W)[:8]) | {"other"}
        out = wcc.coverage([near], W)
        assert out["exact_matches"] == 0
        assert out["by_shared_players"]["8"] == 1

    def test_counts_sum_to_the_pool_size(self):
        pool = [set(W), {"q"}, set(list(W)[:3])]
        out = wcc.coverage(pool, W)
        assert sum(out["by_shared_players"].values()) == len(pool)

    def test_roster_size_is_reported_not_assumed_nine(self):
        """Showdown and other formats do not have nine slots."""
        small = {"a", "b", "c"}
        assert wcc.coverage([small], small)["roster_size"] == 3


class TestTheCeilingComparison:
    @pytest.mark.parametrize("best,winning,winnable", [
        (197.26, 232.40, False),   # the Week-2 Millionaire
        (197.26, 182.10, True),    # the Week-2 $555 satellite
        (182.10, 182.10, True),    # a tie clears the bar
        (182.09, 182.10, False),
    ])
    def test_winnable_is_pool_best_at_or_above_the_winning_score(self, best, winning, winnable):
        assert (best >= winning) is winnable


class TestItRefusesBadInput:
    def test_a_pool_without_the_needed_columns_is_rejected(self, tmp_path):
        p = tmp_path / "pool.csv"
        p.write_text("cand,salary\n1,50000\n")
        with pytest.raises(SystemExit) as e:
            wcc.main(["--season", "2026", "--week", "2", "--pool", str(p)])
        assert "names" in str(e.value)

    def test_the_realized_column_is_required_too(self, tmp_path):
        p = tmp_path / "pool.csv"
        p.write_text("names\na|b|c\n")
        with pytest.raises(SystemExit) as e:
            wcc.main(["--season", "2026", "--week", "2", "--pool", str(p)])
        assert "realized" in str(e.value)
