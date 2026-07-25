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


def test_dotenv_loading(tmp_path, monkeypatch):
    from nfl_dfs.config import _load_dotenv

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "# comment\nMY_DOTENV_TEST=hello\nQUOTED='world'\nEXISTING=file\n")
    monkeypatch.setenv("EXISTING", "real-env")
    monkeypatch.delenv("MY_DOTENV_TEST", raising=False)
    _load_dotenv()
    import os
    assert os.environ["MY_DOTENV_TEST"] == "hello"
    assert os.environ["QUOTED"] == "world"
    assert os.environ["EXISTING"] == "real-env"  # env always wins
