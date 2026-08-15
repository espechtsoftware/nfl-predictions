"""Backup job config sanity (ops/backup.py) — offline checks only."""

from types import SimpleNamespace

from nfl_dfs.ops import backup


def test_irreplaceable_tables_covered():
    tables = {t for _, t in backup.TABLES}
    # The tables a >7-day-late discovery could not rebuild from source.
    for must in ("contest_ownership", "manual_notes", "player_watch_notes",
                 "entered_lineups", "dk_salaries_historical",
                 "injury_snapshots",
                 "fantasy_points_route_share",
                 "fantasy_points_advanced_prior",
                 "fantasy_points_receiver_coverage_l4",
                 "fantasy_points_defense_coverage_l4",
                 "fantasy_points_advanced_passing_l4",
                 "fantasy_points_route_shape_l4",
                 "fantasy_points_qb_shell_l4",
                 "fantasy_points_defense_proe",
                 "fantasy_points_advanced_receiving_windows"):
        assert must in tables


def test_future_fantasy_points_tables_are_discovered():
    class FakeClient:
        def list_tables(self, _dataset):
            return [
                SimpleNamespace(
                    table_id="fantasy_points_future_adopted", table_type="TABLE"),
                SimpleNamespace(
                    table_id="fantasy_points_view", table_type="VIEW"),
                SimpleNamespace(table_id="ordinary_raw", table_type="TABLE"),
            ]

    tables = set(backup._tables_to_backup(FakeClient()))
    assert ("raw", "fantasy_points_future_adopted") in tables
    assert ("raw", "fantasy_points_view") not in tables
    assert ("raw", "ordinary_raw") not in tables


def test_actual_route_table_is_selected_by_dynamic_backup_discovery():
    class FakeClient:
        def list_tables(self, _dataset):
            return [SimpleNamespace(
                table_id="fantasy_points_route_share", table_type="TABLE")]

    tables = set(backup._tables_to_backup(FakeClient()))
    assert ("raw", "fantasy_points_route_share") in tables


def test_future_sis_tables_are_discovered():
    class FakeClient:
        def list_tables(self, _dataset):
            return [
                SimpleNamespace(table_id="sis_team_context_game", table_type="TABLE"),
                SimpleNamespace(table_id="sis_view", table_type="VIEW"),
            ]

    tables = set(backup._tables_to_backup(FakeClient()))
    assert ("raw", "sis_team_context_game") in tables
    assert ("raw", "sis_view") not in tables


def test_dataset_attrs_resolve():
    from nfl_dfs.config import settings

    for attr, _ in backup.TABLES:
        assert getattr(settings, attr)  # unknown attr would AttributeError


def test_cli_wired():
    from nfl_dfs import cli

    src = open(cli.__file__).read()
    assert "backup-tables" in src
