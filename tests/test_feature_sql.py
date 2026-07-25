"""Offline guards on the feature SQL files themselves.

The BigQuery build can't run in tests, but two invariants are checkable from
the files alone: every file renders with no unresolved ${placeholders}, and
every rolling window in a model-input table ends strictly before the current
row (the point-in-time rule; see CLAUDE.md and features/leakage.py).
"""

import re

import pytest

from nfl_dfs.bq import SQL_DIR, render_sql

FEATURE_SQL = sorted((SQL_DIR / "features").glob("*.sql"))

# Dashboard-only tables (README: "never a model input") may legitimately
# window through CURRENT ROW. Everything else must not.
CURRENT_ROW_OK = {"022_defense_points_against.sql"}


def test_feature_sql_discovered():
    assert len(FEATURE_SQL) >= 17


def test_coverage_table_present_and_ordered_before_training():
    """build.py executes in sorted order; the coverage table must be built
    before the training/inference tables that join it."""
    names = [p.name for p in FEATURE_SQL]
    cov = names.index("017a_defense_week_coverage.sql")
    assert cov < names.index("021_player_week_training.sql")
    assert cov < names.index("023_player_week_inference.sql")


@pytest.mark.parametrize("path", FEATURE_SQL, ids=lambda p: p.name)
def test_renders_without_unresolved_placeholders(path):
    sql = render_sql(path, prior_k=4)
    assert "${" not in sql


@pytest.mark.parametrize("path", FEATURE_SQL, ids=lambda p: p.name)
def test_model_input_windows_exclude_current_row(path):
    if path.name in CURRENT_ROW_OK:
        pytest.skip("dashboard table, windows through CURRENT ROW by design")
    for clause in re.findall(r"ROWS BETWEEN[^)]+", path.read_text()):
        assert clause.rstrip().endswith("1 PRECEDING"), (
            f"{path.name}: rolling window does not end at 1 PRECEDING: {clause!r}"
        )
