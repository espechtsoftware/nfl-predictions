"""Backup job config sanity (ops/backup.py) — offline checks only."""

from nfl_dfs.ops import backup


def test_irreplaceable_tables_covered():
    tables = {t for _, t in backup.TABLES}
    # The tables a >7-day-late discovery could not rebuild from source.
    for must in ("contest_ownership", "manual_notes", "player_watch_notes",
                 "entered_lineups", "dk_salaries_historical"):
        assert must in tables


def test_dataset_attrs_resolve():
    from nfl_dfs.config import settings

    for attr, _ in backup.TABLES:
        assert getattr(settings, attr)  # unknown attr would AttributeError


def test_cli_wired():
    from nfl_dfs import cli

    src = open(cli.__file__).read()
    assert "backup-tables" in src
