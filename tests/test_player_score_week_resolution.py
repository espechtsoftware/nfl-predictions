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
        with pytest.raises(SystemExit) as e:
            ps.resolve_season_week(r, 2026, 1)
        assert "contradicts" in str(e.value) and "week" in str(e.value)

    def test_a_contradicting_season_is_refused(self, tmp_path):
        r = _run(tmp_path, season=2026, week=2)
        with pytest.raises(SystemExit) as e:
            ps.resolve_season_week(r, 2025, 2)
        assert "contradicts" in str(e.value)

    def test_a_flag_cannot_override_the_run(self, tmp_path):
        """If a flag could win, a wrong caller would still score the wrong week."""
        r = _run(tmp_path, season=2026, week=3)
        with pytest.raises(SystemExit):
            ps.resolve_season_week(r, 2026, 1)


class TestFailsClosed:
    def test_a_missing_receipt_stops_the_run(self, tmp_path):
        d = tmp_path / "bare"
        d.mkdir()
        with pytest.raises(SystemExit) as e:
            ps.resolve_season_week(d)
        assert "missing" in str(e.value)

    def test_a_receipt_without_a_week_stops_the_run(self, tmp_path):
        with pytest.raises(SystemExit) as e:
            ps.resolve_season_week(_run(tmp_path, season=2026))
        assert "season and week" in str(e.value)

    def test_an_unreadable_receipt_stops_the_run(self, tmp_path):
        d = tmp_path / "bad"
        d.mkdir()
        (d / "receipt.json").write_text("{not json")
        with pytest.raises(SystemExit) as e:
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
