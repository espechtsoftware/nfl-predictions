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


def test_ownership_shadow_schema_names_its_writer_nullable():
    """2026-10-05: rows carry writer/run_type; both NULLABLE (legacy rows read NULL),
    in the same order the writer builds its frame."""
    import re

    from nfl_dfs.inference.own_shadow import ownership_shadow_frame
    import pandas as pd

    sql = (SQL_DIR / "predictions" / "002_own_shadow.sql").read_text()
    body = sql[sql.index("(") + 1:sql.index("\n)")]
    columns = [m.group(1) for m in re.finditer(r"^\s+([a-z_]+) [A-Z0-9]+,?$", body, re.M)]
    assert "writer STRING" in sql and "run_type STRING" in sql
    assert "NOT NULL" not in sql and "REQUIRED" not in sql
    frame = pd.DataFrame({"gsis_id": ["a"], "name": ["A"], "pos": ["QB"],
                          "salary": [5000]})
    rows = ownership_shadow_frame(frame, [0.1], "naive", 2026, 5, booster_own=None,
                                  writer="w", run_type=None,
                                  generated_at=pd.Timestamp("2026-10-11", tz="UTC"))
    assert list(rows.columns) == columns
