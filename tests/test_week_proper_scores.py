"""Scoring-function tests for scripts/week_proper_scores.py.

Each test breaks the property it claims: a passing assertion here must fail if
the corresponding line of the reader is wrong, so none of these merely restate
the implementation.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "week_proper_scores.py"
_spec = importlib.util.spec_from_file_location("week_proper_scores", _SRC)
wps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wps)


def _row(pos, proj, std, realized, played=True, p20=None):
    return {"position": pos, "proj_points": proj, "proj_std": std,
            "proj_p10": proj - 1.2816 * std, "proj_p50": proj,
            "proj_p90": proj + 1.2816 * std, "p_20_plus": p20,
            "realized": realized, "played": played}


class TestCRPS:
    def test_is_mae_when_the_forecast_is_nearly_deterministic(self):
        """As sigma -> 0 a Gaussian CRPS collapses to |y - mu|."""
        assert wps.crps_gauss(10.0, 1e-6, 14.0) == pytest.approx(4.0, abs=1e-3)

    def test_rewards_the_sharper_of_two_unbiased_forecasts(self):
        """Same centre, same outcome: the tighter distribution must score lower."""
        assert wps.crps_gauss(10.0, 2.0, 10.0) < wps.crps_gauss(10.0, 6.0, 10.0)

    def test_penalises_a_confident_wrong_forecast(self):
        """A sharp forecast that misses must score worse than a vague one."""
        assert wps.crps_gauss(10.0, 1.0, 25.0) > wps.crps_gauss(10.0, 8.0, 25.0)

    def test_is_undefined_for_a_zero_variance_stand_in(self):
        """Zero-variance rows have no predictive distribution to score."""
        assert wps.crps_gauss(0.0, 0.0, 0.0) is None
        assert wps.crps_gauss(0.0, None, 0.0) is None


class TestPinball:
    def test_upper_quantile_penalises_under_prediction_more(self):
        """At q = 0.9 missing low must cost more than missing high by the same gap."""
        assert wps.pinball(0.90, 10.0, 15.0) > wps.pinball(0.90, 20.0, 15.0)

    def test_lower_quantile_penalises_over_prediction_more(self):
        assert wps.pinball(0.10, 20.0, 15.0) > wps.pinball(0.10, 10.0, 15.0)

    def test_is_zero_only_on_an_exact_hit(self):
        assert wps.pinball(0.90, 12.0, 12.0) == 0.0
        assert wps.pinball(0.90, 12.0, 12.5) > 0.0


class TestMedian:
    def test_averages_the_middle_pair_on_an_even_count(self):
        assert wps.median([4.0, 1.0, 3.0, 2.0]) == pytest.approx(2.5)

    def test_takes_the_middle_on_an_odd_count(self):
        assert wps.median([5.0, 1.0, 3.0]) == pytest.approx(3.0)


class TestPanelPopulations:
    def test_excludes_dst_and_zero_variance_rows_from_scoring(self):
        rows = [_row("WR", 10.0, 4.0, 12.0), _row("QB", 0.0, 0.0, 0.0),
                {"position": "DST", "proj_points": 6.0, "proj_std": 3.0,
                 "proj_p10": 2.0, "proj_p50": 6.0, "proj_p90": 10.0,
                 "p_20_plus": None, "realized": 8.0, "played": True}]
        out = wps.panel(rows, "t")
        assert out["n_skill"] == 1, "only the WR is a scorable forecast"
        assert out["n_dst"] == 1 and out["n_degenerate"] == 1

    def test_a_zero_variance_stand_in_cannot_flatter_the_score(self):
        """Adding a 0-projected/0-scored row must not change any scored metric."""
        real = [_row("WR", 10.0, 4.0, 3.0), _row("WR", 8.0, 3.0, 19.0)]
        padded = real + [_row("QB", 0.0, 0.0, 0.0, played=False)]
        assert wps.panel(padded, "t")["all"] == wps.panel(real, "t")["all"]

    def test_a_missing_stat_line_scores_zero_not_null(self):
        out = wps.panel([_row("RB", 9.0, 3.0, None, played=False)], "t")
        assert out["all"]["mean_realized"] == 0.0
        assert out["all"]["mean_bias"] == pytest.approx(-9.0)

    def test_bias_sign_is_realized_minus_projected(self):
        """Over-projection must read negative, or every bias in the record flips."""
        assert wps.panel([_row("WR", 12.0, 4.0, 5.0)], "t")["all"]["mean_bias"] < 0
        assert wps.panel([_row("WR", 5.0, 4.0, 12.0)], "t")["all"]["mean_bias"] > 0

    def test_played_only_block_drops_the_absent(self):
        rows = [_row("WR", 10.0, 4.0, 14.0), _row("WR", 10.0, 4.0, None, played=False)]
        out = wps.panel(rows, "t")
        assert out["all"]["n"] == 2 and out["played_only"]["n"] == 1
        assert out["played_only"]["mean_bias"] == pytest.approx(4.0)

    def test_coverage_counts_strictly_below_the_quantile(self):
        """A row exactly at p90 is not below it -- the negative-p10 finding
        in the Week-2 record depends on this boundary being strict."""
        r = _row("WR", 10.0, 4.0, 0.0)
        r["proj_p10"] = 0.0
        assert wps.panel([r], "t")["all"]["cov_p10"] == 0.0

    def test_bias_se_shrinks_as_the_sample_grows(self):
        few = [_row("WR", 10.0, 4.0, v) for v in (2.0, 18.0)]
        many = [_row("WR", 10.0, 4.0, v) for v in (2.0, 18.0) * 25]
        assert wps.panel(many, "t")["all"]["bias_se"] < wps.panel(few, "t")["all"]["bias_se"]
        assert wps.panel(many, "t")["all"]["mean_bias"] == pytest.approx(
            wps.panel(few, "t")["all"]["mean_bias"])


class TestCalibrationBuckets:
    def test_detects_an_overstated_top_bucket(self):
        """25 rows stating 80% that never happen must show realized 0."""
        rows = [_row("WR", 9.0, 5.0, 3.0, p20=0.80) for _ in range(25)]
        rows += [_row("WR", 3.0, 2.0, 1.0, p20=0.01) for _ in range(25)]
        buckets = wps.panel(rows, "t")["p20_calibration"]
        top = max(buckets, key=lambda b: b["mean_p20"])
        assert top["mean_p20"] == pytest.approx(0.80)
        assert top["realized_rate"] == 0.0

    def test_a_well_calibrated_bucket_reads_back_its_stated_rate(self):
        # Interleaved: the sort is stable, so ties keep input order and every
        # bucket gets the same hit/miss mix. Grouping them would make the
        # bucket boundaries, not the calibration, decide the answer.
        rows = []
        for _ in range(25):
            rows.append(_row("WR", 15.0, 6.0, 25.0, p20=0.50))
            rows.append(_row("WR", 15.0, 6.0, 5.0, p20=0.50))
        for b in wps.panel(rows, "t")["p20_calibration"]:
            assert b["realized_rate"] == pytest.approx(0.50)

    def test_too_few_rows_says_so_instead_of_returning_nothing(self):
        """Silence would read as 'well calibrated'; the reader must name the gap."""
        rows = [_row("WR", 9.0, 5.0, 3.0, p20=0.4) for _ in range(10)]
        out = wps.panel(rows, "t")
        assert out["p20_calibration"] == []
        assert "10 of 10 scored rows carry p_20_plus" in out["p20_calibration_note"]

    def test_every_row_lands_in_a_bucket_when_the_count_divides(self):
        rows = [_row("WR", 9.0, 5.0, 3.0, p20=i / 100) for i in range(50)]
        buckets = wps.panel(rows, "t")["p20_calibration"]
        assert len(buckets) == 5
        assert sum(b["n"] for b in buckets) == 50
