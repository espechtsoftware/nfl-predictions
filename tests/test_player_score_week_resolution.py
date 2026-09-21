"""The composite ordering must never score a book against another week's data.

Regression cover for the defect found 2026-09-21: every Week-2 composite ordering
run scored Week-2 lineups against the LAST WEEK-1 projection batch and Week-1
props, because `player_score.py --week` defaulted to 1 and the Sunday caller
omitted the flag. The projection join is by player, not by week, so it succeeded
silently: the receipt's coverage block read a healthy 134 of 149 and nothing in
the output said the data was a week old. 80% of the ordering weight was stale.

Each test below breaks the property it claims.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "scripts" / "player_score.py"
_spec = importlib.util.spec_from_file_location("player_score", _SRC)
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)


def _run(tmp_path, **receipt):
    d = tmp_path / "run"
    d.mkdir(exist_ok=True)
    if receipt is not None:
        (d / "receipt.json").write_text(json.dumps(receipt))
    return d


class TestTheDefectItself:
    def test_week_is_taken_from_the_run_not_a_default(self, tmp_path):
        """The exact failure: a Week-2 run must resolve to week 2, with no flag."""
        assert ps.resolve_season_week(_run(tmp_path, season=2026, week=2)) == (2026, 2)

    def test_a_week_three_run_resolves_to_three(self, tmp_path):
        assert ps.resolve_season_week(_run(tmp_path, season=2026, week=3)) == (2026, 3)

    def test_no_argparse_default_can_supply_a_week(self):
        """A default on --week is what caused the incident. It must stay absent."""
        src = _SRC.read_text()
        for flag in ("--season", "--week"):
            m = re.search(rf'add_argument\("{flag}"[^)]*\)', src)
            assert m, f"{flag} not found"
            assert "default=None" in m.group(0), (
                f"{flag} has a non-None default; a defaulted slate silently scored "
                f"Week 2 against Week 1 on 2026-09-20")

    def test_no_flag_value_can_reach_a_query(self):
        """The queries must bind the resolved values, never the raw flags."""
        src = _SRC.read_text()
        # Passing the flags INTO resolve_season_week is correct; binding them into a
        # query is the defect. Check the bindings, which is where the week is chosen.
        for call in re.findall(r'ScalarQueryParameter\("[sw]", "INT64", (\w+(?:\.\w+)?)\)', src):
            assert call in ("season", "week"), f"query binds {call}, not the resolved slate"


class TestFlagsMayOnlyConfirm:
    def test_an_agreeing_flag_is_accepted(self, tmp_path):
        r = _run(tmp_path, season=2026, week=2)
        assert ps.resolve_season_week(r, 2026, 2) == (2026, 2)

    def test_a_contradicting_week_is_refused(self, tmp_path):
        """The caller and the run disagreeing is exactly the incident's shape."""
        r = _run(tmp_path, season=2026, week=2)
        with pytest.raises(ps.ScopeError) as e:
            ps.resolve_season_week(r, 2026, 1)
        assert "disagrees" in str(e.value) and "week" in str(e.value)

    def test_a_contradicting_season_is_refused(self, tmp_path):
        r = _run(tmp_path, season=2026, week=2)
        with pytest.raises(ps.ScopeError) as e:
            ps.resolve_season_week(r, 2025, 2)
        assert "disagrees" in str(e.value)

    def test_a_flag_cannot_override_the_run(self, tmp_path):
        """If a flag could win, a wrong caller would still score the wrong week."""
        r = _run(tmp_path, season=2026, week=3)
        with pytest.raises(ps.ScopeError):
            ps.resolve_season_week(r, 2026, 1)


class TestFailsClosed:
    def test_a_missing_receipt_stops_the_run(self, tmp_path):
        d = tmp_path / "bare"
        d.mkdir()
        with pytest.raises(ps.ScopeError) as e:
            ps.resolve_season_week(d)
        assert "missing" in str(e.value)

    def test_a_receipt_without_a_week_stops_the_run(self, tmp_path):
        with pytest.raises(ps.ScopeError) as e:
            ps.resolve_season_week(_run(tmp_path, season=2026))
        assert "season and week" in str(e.value)

    def test_an_unreadable_receipt_stops_the_run(self, tmp_path):
        d = tmp_path / "bad"
        d.mkdir()
        (d / "receipt.json").write_text("{not json")
        with pytest.raises(ps.ScopeError) as e:
            ps.resolve_season_week(d)
        assert "cannot read" in str(e.value)

    def test_an_empty_projection_batch_is_refused(self):
        """Scoring against zero rows must stop, not produce an all-NaN ordering."""
        src = _SRC.read_text()
        assert "prod.empty" in src and "refusing to score a book against nothing" in src


class TestTheReceiptShowsItsWork:
    def test_the_receipt_records_the_slate_it_scored(self):
        """The incident was invisible because the output never named the week."""
        src = _SRC.read_text()
        for field in ('"season": season', '"week": week', '"week_source"'):
            assert field in src, f"composite receipt does not record {field}"


class TestTheCallerPassesTheSlate:
    def test_sunday_build_host_passes_season_and_week(self):
        """The Sunday driver omitted these while the adjacent vetting call had them."""
        line = next(l for l in (ROOT / "scripts" / "sunday_build_host.sh").read_text().splitlines()
                    if "player_score.py" in l)
        assert '--season "$SEASON"' in line and '--week "$WEEK"' in line, line


class TestAWeek1BatchCannotReachAWeek2Book:
    """The regression the lab asked for on 2026-09-21:

    "Add a regression test that supplies a Week 1 projection batch to a Week 2
    run and asserts a nonzero failure before book.csv is emitted."

    `verify_slice` checks the RETURNED ROWS, not the query text, so a wrong slice
    cannot reach the book however it arrives -- a bad flag, an edited query, or a
    table whose own columns disagree.
    """

    @staticmethod
    def _frame(season, week, n=3):
        pd = pytest.importorskip("pandas")
        return pd.DataFrame({"gsis_id": [f"00-{i:07d}" for i in range(n)],
                             "proj_points": [10.0] * n, "season": [season] * n,
                             "week": [week] * n})

    def test_a_week1_projection_batch_is_refused_by_a_week2_run(self):
        with pytest.raises(ps.ScopeError) as e:
            ps.verify_slice(self._frame(2026, 1), 2026, 2, "projection batch")
        msg = str(e.value)
        assert "week [1]" in msg and "week 2" in msg
        assert "refusing to score the book against another slate" in msg

    def test_the_matching_batch_passes(self):
        ps.verify_slice(self._frame(2026, 2), 2026, 2, "projection batch")

    def test_a_wrong_season_is_refused(self):
        with pytest.raises(ps.ScopeError) as e:
            ps.verify_slice(self._frame(2025, 2), 2026, 2, "projection batch")
        assert "season [2025]" in str(e.value)

    def test_a_batch_mixing_two_weeks_is_refused(self):
        """A partial substitution must fail as loudly as a total one."""
        pd = pytest.importorskip("pandas")
        mixed = pd.concat([self._frame(2026, 1, 2), self._frame(2026, 2, 2)])
        with pytest.raises(ps.ScopeError) as e:
            ps.verify_slice(mixed, 2026, 2, "projection batch")
        assert "week [1, 2]" in str(e.value)

    def test_a_frame_without_the_slice_columns_is_refused(self):
        """Unverifiable is not the same as fine."""
        pd = pytest.importorskip("pandas")
        with pytest.raises(ps.ScopeError) as e:
            ps.verify_slice(pd.DataFrame({"gsis_id": ["x"]}), 2026, 2, "projection batch")
        assert "cannot verify its identity" in str(e.value)

    def test_prop_lines_are_verified_too_not_just_projections(self):
        """25% of the composite weight came from props, which were also stale."""
        src = _SRC.read_text()
        assert 'verify_slice(L, season, week, "prop lines")' in src

    def test_the_check_runs_before_any_book_is_written(self):
        """A check after the emit would document the defect, not prevent it.

        Uses line numbers, and counts only writes to the OUTPUT dir. The input
        book is read from the run dir early, which is fine and is not a write.
        """
        lines = _SRC.read_text().splitlines()
        checks = [i for i, l in enumerate(lines) if "verify_slice(" in l and "def " not in l]
        writes = [i for i, l in enumerate(lines)
                  if any(m in l for m in ('out / "book.csv"', "to_csv(out /", "(out /"))
                  and "print(" not in l]
        assert checks and writes
        assert max(checks) < min(writes), (
            f"identity checks at lines {[c + 1 for c in checks]} but an output artifact "
            f"is written at line {min(writes) + 1}")

    def test_the_receipt_carries_both_batch_identities(self):
        """The lab asked for projection and prop batch identity in the receipt."""
        src = _SRC.read_text()
        for field in ('"target_identity"', '"projection_batch"', '"prop_batch"'):
            assert field in src, f"receipt does not record {field}"
