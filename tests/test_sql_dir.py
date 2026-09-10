"""SQL_DIR must resolve to a real directory containing the feature SQL.

Regression guard for the 2026-07-31 incident: the checkout-relative path
resolved to a nonexistent directory inside the container, so every
scheduled build-features run died on FileNotFoundError for weeks."""

from nfl_dfs.bq import SQL_DIR


def test_sql_dir_exists_with_feature_sql():
    assert SQL_DIR.is_dir()
    assert list((SQL_DIR / "features").glob("*.sql"))
    assert list((SQL_DIR / "raw").glob("*.sql"))


def test_ownership_shadow_schema_keeps_both_predictions_numeric():
    sql = (SQL_DIR / "predictions" / "002_own_shadow.sql").read_text()

    assert "pred_own FLOAT64" in sql
    assert "booster_own FLOAT64" in sql
    assert "PARTITION BY DATE(generated_at)" in sql
    assert "CLUSTER BY season, week" in sql
