"""The in-season SIS loader must not write rows the table cannot be joined on.

Regression cover for the 2026-09-19 load, which wrote 32 Week-1 rows carrying
every vendor column but none of the six the loader derives -- team, opp,
opp_team_id, game_key, source_run_id, ingested_at. 73 of 79 columns were
populated, so nothing looked wrong. But `team` is the natural join key, so a
consumer joining on it silently drops the week, and one aggregating without a
team filter double-counts it. A later corrected load appended 32 more rows,
leaving 64 for 32 teams.

Each test breaks the property it claims.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "scripts" / "sis_load_inseason_week.py"
_spec = importlib.util.spec_from_file_location("sis_load_inseason_week", _SRC)
sis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sis)


def _frame(pairs=(("Bills", "Lions", 4), ("Lions", "Bills", 11)), season=2026, week=1):
    return pd.DataFrame([{"season": season, "week": week, "team_name": t,
                          "opp_name": o, "team_id": i, "pdef_attempts": 30.0}
                         for t, o, i in pairs])


class TestTheDerivedColumnsExist:
    def test_all_six_are_added(self):
        out = sis.derive_canonical_columns(_frame())
        for column in sis.CANONICAL_COLUMNS:
            assert column in out.columns, column
            assert out[column].notna().all(), f"{column} is null"

    def test_team_codes_come_from_the_frozen_map(self):
        """Importing the map rather than copying it stops the two from drifting."""
        from nfl_dfs.ingest.sis_team_context import TEAM_ABBREVIATIONS
        out = sis.derive_canonical_columns(_frame())
        assert list(out.team) == [TEAM_ABBREVIATIONS["Bills"], TEAM_ABBREVIATIONS["Lions"]]
        assert list(out.opp) == [TEAM_ABBREVIATIONS["Lions"], TEAM_ABBREVIATIONS["Bills"]]

    def test_both_sides_of_a_game_share_one_key(self):
        out = sis.derive_canonical_columns(_frame())
        assert out.game_key.nunique() == 1

    def test_the_key_is_order_independent_and_carries_the_week(self):
        out = sis.derive_canonical_columns(_frame(week=7))
        key = out.game_key.iloc[0]
        assert key.startswith("2026-07-")
        assert key == out.game_key.iloc[1]

    def test_the_opponent_id_is_the_opponents_own_id(self):
        out = sis.derive_canonical_columns(_frame())
        assert list(out.opp_team_id) == [11, 4]


class TestItRefusesBadFrames:
    def test_a_lone_row_is_refused(self):
        """A single team with no opponent row cannot resolve the opponent's id."""
        with pytest.raises(ValueError, match="opponent IDs missing"):
            sis.derive_canonical_columns(_frame((("Bills", "Lions", 4),)))

    def test_a_one_sided_game_among_complete_ones_is_refused(self):
        """Half a game passes a row count and would corrupt every paired read.

        All names resolve here, so this reaches the both-sides check rather than
        failing earlier on an unknown opponent.
        """
        with pytest.raises(ValueError, match="both sides"):
            sis.derive_canonical_columns(_frame(
                (("Bills", "Lions", 4), ("Lions", "Bills", 11), ("Jets", "Bills", 20))))

    def test_a_repeated_team_week_is_refused(self):
        with pytest.raises(ValueError, match="repeats a canonical team-week"):
            sis.derive_canonical_columns(_frame(
                (("Bills", "Lions", 4), ("Bills", "Lions", 4),
                 ("Lions", "Bills", 11), ("Lions", "Bills", 11))))

    def test_an_unknown_team_name_is_refused(self):
        with pytest.raises(ValueError, match="abbreviations missing"):
            sis.derive_canonical_columns(_frame(
                (("Notateam", "Lions", 4), ("Lions", "Notateam", 11))))

    def test_one_name_mapping_to_two_ids_is_refused(self):
        with pytest.raises(ValueError, match="multiple IDs"):
            sis.derive_canonical_columns(_frame(
                (("Bills", "Lions", 4), ("Lions", "Bills", 11),
                 ("Bills", "Jets", 99), ("Jets", "Bills", 20))))


class TestTheWriteGuard:
    def test_the_loader_checks_the_canonical_columns_before_writing(self):
        src = _SRC.read_text()
        guard = src.index("REFUSING: frame is missing loader-derived columns")
        write = src.index("bq.load_dataframe")
        assert guard < write, "the column guard must run before the write"

    def test_the_loader_checks_it_covers_the_destination_table(self):
        """The real lesson: a partial write looks exactly like a successful one."""
        src = _SRC.read_text()
        assert "INFORMATION_SCHEMA.COLUMNS" in src
        assert src.index("uncovered") < src.index("bq.load_dataframe")

    def test_the_existing_season_week_guard_is_still_there(self):
        src = _SRC.read_text()
        assert "already holds" in src and src.index("already holds") < src.index("bq.load_dataframe")

    def test_build_returns_a_frame_that_is_ready_to_write(self):
        """derive must be inside build, or a caller can skip it."""
        src = _SRC.read_text()
        assert "return derive_canonical_columns(base)" in src
