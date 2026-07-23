from datetime import date

from nfl_dfs.config import Settings, current_season


def test_current_season_rolls_over_in_march():
    assert current_season(date(2025, 2, 15)) == 2024
    assert current_season(date(2025, 3, 1)) == 2025
    assert current_season(date(2025, 11, 30)) == 2025
    assert current_season(date(2026, 1, 4)) == 2025


def test_settings_qualified_datasets():
    s = Settings()
    assert s.raw.endswith(".nfl_raw")
    assert s.features.endswith(".nfl_features")
    assert s.predictions.endswith(".nfl_predictions")
