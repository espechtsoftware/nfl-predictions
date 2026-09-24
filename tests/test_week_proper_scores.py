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


def _row(pos, proj, std, realized, played=True, p20=None, team="KC"):
    return {"position": pos, "team": team, "proj_points": proj, "proj_std": std,
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


class TestDispersion:
    """Model's stated spread against what actually happened."""

    def test_a_too_narrow_forecast_reads_above_one(self):
        """Ratio > 1 means the stated sd exceeds the realized sd."""
        rows = [_row("WR", 10.0, 8.0, v) for v in (9.0, 10.0, 11.0)] * 4
        b = wps.panel(rows, "t")["all"]
        assert b["dispersion_ratio"] > 1.0

    def test_a_too_confident_forecast_reads_below_one(self):
        rows = [_row("WR", 10.0, 1.0, v) for v in (0.0, 10.0, 25.0)] * 4
        b = wps.panel(rows, "t")["all"]
        assert b["dispersion_ratio"] < 1.0

    def test_it_reports_both_sides_not_just_the_ratio(self):
        b = wps.panel([_row("WR", 10.0, 4.0, v) for v in (5.0, 15.0)], "t")["all"]
        assert b["predicted_sd"] == pytest.approx(4.0)
        assert b["realized_sd"] == pytest.approx(wps.stdev([5.0, 15.0]))

    def test_a_single_row_has_no_realized_spread(self):
        """One observation cannot estimate dispersion; say None, not a fake number."""
        assert wps.panel([_row("WR", 10.0, 4.0, 12.0)], "t")["all"]["dispersion_ratio"] is None


class TestMedianBias:
    def test_it_is_signed_not_absolute(self):
        """Median ABSOLUTE error hides direction; the protocol needs the sign."""
        rows = [_row("WR", 10.0, 4.0, y) for y in (4.0, 5.0, 6.0)]
        b = wps.panel(rows, "t")["all"]
        assert b["median_bias"] == pytest.approx(-5.0)
        assert b["median_abs_err"] == pytest.approx(5.0)

    def test_it_resists_a_single_outlier_that_moves_the_mean(self):
        rows = [_row("WR", 10.0, 4.0, y) for y in (9.0, 10.0, 11.0, 200.0)]
        b = wps.panel(rows, "t")["all"]
        assert abs(b["median_bias"]) < 1.0 < b["mean_bias"]


class TestProjectionBuckets:
    def test_buckets_use_frozen_edges_not_quantiles(self):
        """Quantile edges would move week to week and break comparability."""
        assert wps.PROJECTION_BUCKETS[0] == (0.0, 5.0)
        assert wps.PROJECTION_BUCKETS[-1][1] == float("inf")

    def test_a_row_lands_in_the_bucket_holding_its_projection(self):
        out = wps.panel([_row("WR", 12.0, 4.0, 12.0)], "t")["projection_buckets"]["WR"]
        assert len(out) == 1 and out[0]["lo"] == 10.0 and out[0]["hi"] == 15.0

    def test_the_top_bucket_is_open_ended(self):
        out = wps.panel([_row("QB", 31.0, 8.0, 30.0)], "t")["projection_buckets"]["QB"]
        assert out[0]["lo"] == 20.0 and out[0]["hi"] is None

    def test_it_detects_bias_that_grows_with_the_projection(self):
        """The Week-2 shape: small projections fair, large ones over-projected."""
        rows = [_row("WR", 2.0, 2.0, 2.0) for _ in range(10)]
        rows += [_row("WR", 22.0, 8.0, 12.0) for _ in range(10)]
        buckets = {(b["lo"]): b for b in wps.panel(rows, "t")["projection_buckets"]["WR"]}
        assert buckets[0.0]["mean_bias"] == pytest.approx(0.0)
        assert buckets[20.0]["mean_bias"] == pytest.approx(-10.0)

    def test_reached_projection_is_the_share_at_or_above(self):
        rows = [_row("WR", 10.0, 4.0, 12.0), _row("WR", 10.0, 4.0, 8.0)]
        b = wps.panel(rows, "t")["projection_buckets"]["WR"][0]
        assert b["reached_projection"] == pytest.approx(0.5)

    def test_empty_buckets_are_omitted_not_reported_as_zero(self):
        out = wps.panel([_row("TE", 2.0, 2.0, 2.0)], "t")["projection_buckets"]["TE"]
        assert [b["lo"] for b in out] == [0.0]


class TestUnplayedGamesAreNeverScored:
    """A player with no stat line is scored 0. That is right for someone who was
    active and did nothing, and WRONG for someone whose game has not kicked off.

    On 2026-09-21 the published Week-2 panel included 36 rows from that night's
    unplayed Monday game, all scored as zeros. It moved every position's bias
    away from zero: all-skill -0.77 read as -1.00, QB -2.89 read as -3.50, and
    WR -0.44 read as -0.75, which changed a null result into an apparent one.
    """

    def test_rows_from_an_unplayed_team_are_removed_not_zeroed(self):
        rows = [_row("QB", 18.0, 6.0, None, played=False), _row("QB", 20.0, 6.0, 22.0)]
        rows[0]["team"], rows[1]["team"] = "NYG", "KC"
        out = wps.panel(rows, "t", scoreable={"KC"})
        assert out["n_unplayed_excluded"] == 1
        assert out["unplayed_teams"] == ["NYG"]
        assert out["all"]["n"] == 1
        assert out["all"]["mean_bias"] == pytest.approx(2.0)

    def test_without_the_guard_the_same_rows_drag_the_bias_down(self):
        """The bug, reproduced: scoring the unplayed row makes a positive bias negative."""
        rows = [_row("QB", 18.0, 6.0, None, played=False), _row("QB", 20.0, 6.0, 22.0)]
        rows[0]["team"], rows[1]["team"] = "NYG", "KC"
        unguarded = wps.panel(rows, "t")
        assert unguarded["all"]["n"] == 2
        assert unguarded["all"]["mean_bias"] < 0 < wps.panel(
            rows, "t", scoreable={"KC"})["all"]["mean_bias"]

    def test_a_player_who_was_active_and_scored_nothing_is_still_zeroed(self):
        """The guard must not excuse genuine zeros on teams that did play."""
        r = _row("WR", 9.0, 4.0, None, played=False)
        r["team"] = "KC"
        out = wps.panel([r], "t", scoreable={"KC"})
        assert out["n_unplayed_excluded"] == 0
        assert out["all"]["n"] == 1 and out["all"]["mean_realized"] == 0.0

    def test_no_scoreable_set_means_no_filtering(self):
        """Back-compatible: callers that pass nothing behave as before."""
        r = _row("QB", 18.0, 6.0, None, played=False)
        r["team"] = "NYG"
        out = wps.panel([r], "t")
        assert out["n_unplayed_excluded"] == 0 and out["all"]["n"] == 1

    def test_the_excluded_teams_are_reported_not_silently_dropped(self):
        rows = [_row("QB", 18.0, 6.0, None, played=False) for _ in range(3)]
        for r, t in zip(rows, ("NYG", "LA", "NYG")):
            r["team"] = t
        rows.append(_row("QB", 20.0, 6.0, 22.0)); rows[-1]["team"] = "KC"
        out = wps.panel(rows, "t", scoreable={"KC"})
        assert out["n_unplayed_excluded"] == 3
        assert out["unplayed_teams"] == ["LA", "NYG"]
