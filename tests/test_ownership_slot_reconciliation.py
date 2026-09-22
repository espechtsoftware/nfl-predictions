"""DK's %Drafted summary is keyed by (player, roster position) and omits rows held by
very few entries. Reconciling per PLAYER conflated that omission with a genuine
disagreement about a share, and every tolerance the module accumulated existed to
absorb the former -- which left it unable to fail closed on the latter.

Measured on all twelve settled Week-2 exports (2026-09-22): at slot granularity every
listed share is within 0.005 of the lineup-derived value -- there are no real
per-player mismatches at all -- and the whole summed-mass shortfall is the mass of the
rows DK omitted.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import ownership_import as oi

# Two entries differing only in where "Swing Man" sits: RB in one, FLEX in the other.
# That is the shape DK actually writes, and the shape a per-player check cannot see.
LINEUP_RB = ("QB Quarter Back RB Swing Man RB Runner Two WR Wide One WR Wide Two "
             "WR Wide Three TE Tight End FLEX Flex Player DST Defense")
LINEUP_FLEX = ("QB Quarter Back RB Runner One RB Runner Two WR Wide One WR Wide Two "
               "WR Wide Three TE Tight End FLEX Swing Man DST Defense")


def _summary(field: int):
    """Every key's true share, at DK's two-decimal printing precision."""
    one = 100.0 / field
    both, once = 2 * one, one
    return [("Quarter Back", "QB", both), ("Runner Two", "RB", both),
            ("Wide One", "WR", both), ("Wide Two", "WR", both),
            ("Wide Three", "WR", both), ("Tight End", "TE", both),
            ("Defense", "DST", both), ("Swing Man", "RB", once),
            ("Swing Man", "FLEX", once), ("Runner One", "RB", once),
            ("Flex Player", "FLEX", once)]


def _write(path: Path, *, field: int = 100, summary=None) -> Path:
    """Two filled lineups padded to `field` with blank-lineup entries, which is how DK
    reports a field whose denominator exceeds the number of submitted rosters."""
    summary = _summary(field) if summary is None else summary
    n_blank = field - 2
    n = max(2 + n_blank, len(summary))
    pad = lambda xs: list(xs) + [None] * (n - len(xs))  # noqa: E731
    data = {
        "Rank": pad(["1", "2"] + [str(i) for i in range(3, 3 + n_blank)]),
        "EntryId": pad([f"{i:04d}" for i in range(1, 3 + n_blank)]),
        "EntryName": pad([f"e{i}" for i in range(1, 3 + n_blank)]),
        "TimeRemaining": pad(["0"] * (2 + n_blank)),
        "Points": pad(["200.5", "190.0"] + ["0"] * n_blank),
        "Lineup": pad([LINEUP_RB, LINEUP_FLEX] + [None] * n_blank),
        "Player": pad([s[0] for s in summary]),
        "Roster Position": pad([s[1] for s in summary]),
        "%Drafted": pad([f"{s[2]:.2f}%" for s in summary]),
        "FPTS": pad(["20.0"] * len(summary)),
        "Winnings": pad(["$100", "$0"] + ["$0"] * n_blank),
    }
    pd.DataFrame(data).to_csv(path, index=False)
    return path


def test_a_complete_summary_reconciles_with_nothing_omitted(tmp_path):
    result = oi.validate_full_field_capture(_write(tmp_path / "s.csv"), expected_entries=100)
    rec = result["slot_reconciliation"]
    assert rec["slot_rows_omitted_by_dk"] == 0
    assert rec["omitted_mass"] == 0
    assert rec["mass_residual"] == pytest.approx(0.0, abs=1e-6)


def test_two_decimal_printing_is_accepted_and_actually_measured(tmp_path):
    """A field of 3 makes every true share a repeating decimal, so DK's printed value
    legitimately sits ~0.0033 off. It must pass, and the receipt must show a NON-ZERO
    deviation -- otherwise this test would pass against a check that measures nothing."""
    result = oi.validate_full_field_capture(_write(tmp_path / "s.csv", field=3), expected_entries=3)
    dev = result["slot_reconciliation"]["max_listed_deviation"]
    assert 0.0 < dev <= oi.DK_PRINTED_PRECISION


def test_an_omitted_slot_row_is_counted_and_priced_not_silently_tolerated(tmp_path):
    """DK drops Swing Man's FLEX row. The capture still passes -- DK's own truncation is
    not our error -- but the receipt now says exactly what was dropped and what it was
    worth, instead of the gap disappearing into a mass tolerance."""
    summary = [s for s in _summary(100) if s[:2] != ("Swing Man", "FLEX")]
    result = oi.validate_full_field_capture(
        _write(tmp_path / "s.csv", summary=summary), expected_entries=100)
    rec = result["slot_reconciliation"]
    assert rec["slot_rows_omitted_by_dk"] == 1
    assert rec["omitted_mass"] == pytest.approx(1.0)
    assert rec["mass_residual"] == pytest.approx(0.0, abs=1e-6)
    assert "Swing Man/FLEX" in rec["omitted_examples"][0]


def test_a_contradicted_share_the_old_tolerance_allowed_now_fails_closed(tmp_path):
    """THE REGRESSION THIS FIXES. Before 2026-09-22 a share below 5% could disagree with
    the lineups by up to two entries' worth and be logged as 'minor'. Here DK claims
    Swing Man at 3% of a 100-entry field where one of the two lineups holds him, so the
    truth is 1%: a tripled share, inside the old allowance (gap 2.0 <= 2 x one entry),
    and inside the old mass tolerance of 6.0. It is now a hard failure."""
    summary = [(p, s, 3.0) if (p, s) == ("Swing Man", "RB") else (p, s, v)
               for p, s, v in _summary(100)]
    with pytest.raises(oi.CaptureValidationError) as exc:
        oi.validate_full_field_capture(_write(tmp_path / "s.csv", summary=summary),
                                       expected_entries=100)
    assert exc.value.result_class == "ownership_mismatch"
    assert "Swing Man/RB" in str(exc.value)


def test_a_share_claimed_for_a_slot_nobody_rostered_fails(tmp_path):
    summary = _summary(100) + [("Never Played", "TE", 12.0)]
    with pytest.raises(oi.CaptureValidationError, match="never rostered"):
        oi.validate_full_field_capture(_write(tmp_path / "s.csv", summary=summary),
                                       expected_entries=100)


def test_a_repeated_player_slot_row_fails_rather_than_double_counting(tmp_path):
    """A duplicated summary block would otherwise inflate the mass and still reconcile."""
    summary = _summary(100) + [("Swing Man", "RB", 1.0)]
    with pytest.raises(oi.CaptureValidationError, match="repeats"):
        oi.validate_full_field_capture(_write(tmp_path / "s.csv", summary=summary),
                                       expected_entries=100)
