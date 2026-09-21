"""Precipitation probability is carried from raw weather through the feature tables (audit ING-002, 2026-09-21)
without becoming a model feature until a point-in-time shadow supports it."""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_game_weather_carries_precip_and_snapshot_time():
    sql = (ROOT / "sql/features/020_game_weather.sql").read_text()
    assert "precip_prob" in sql and "weather_pulled_at" in sql
    assert re.search(r"ARRAY_AGG\(precip_prob ORDER BY pulled_at DESC LIMIT 1\)", sql)   # same latest-snapshot law as temp/wind
    assert "MAX(pulled_at) AS weather_pulled_at" in sql


def test_training_and_inference_tables_pass_precip_through():
    for name in ("021_player_week_training.sql", "023_player_week_inference.sql"):
        sql = (ROOT / "sql/features" / name).read_text()
        assert "w.precip_prob, w.weather_pulled_at" in sql, name


def test_precipitation_is_not_a_model_feature_yet():
    src = (ROOT / "src/nfl_dfs/models/featureset.py").read_text()
    assert "precip" not in src
    assert '"is_dome"' in src                      # the existing weather feature set is unchanged
