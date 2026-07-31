"""SQL_DIR must resolve to a real directory containing the feature SQL.

Regression guard for the 2026-07-31 incident: the checkout-relative path
resolved to a nonexistent directory inside the container, so every
scheduled build-features run died on FileNotFoundError for weeks."""

from nfl_dfs.bq import SQL_DIR


def test_sql_dir_exists_with_feature_sql():
    assert SQL_DIR.is_dir()
    assert list((SQL_DIR / "features").glob("*.sql"))
    assert list((SQL_DIR / "raw").glob("*.sql"))
