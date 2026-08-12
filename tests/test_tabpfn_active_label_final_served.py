from pathlib import Path

import pytest

from nfl_dfs.analysis import tabpfn_active_label_final_served as diagnostic


def test_accepted_usage_law_is_exact(monkeypatch):
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    monkeypatch.delenv("DIRICHLET_K", raising=False)
    assert diagnostic._accepted_usage_law()["mode"] == "production-multinomial"

    monkeypatch.setenv("GAME_SIM_USAGE", "dirichlet")
    monkeypatch.setenv("DIRICHLET_K", diagnostic.FITTED_K_TEXT)
    assert diagnostic._accepted_usage_law() == {
        "mode": "data-fitted-dirichlet",
        "game_sim_usage": "dirichlet",
        "k": diagnostic.FITTED_K_TEXT,
    }
    monkeypatch.setenv("DIRICHLET_K", "28.2469")
    with pytest.raises(ValueError, match="exact frozen fitted K"):
        diagnostic._accepted_usage_law()


def test_inactive_usage_rejects_stray_k(monkeypatch):
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    monkeypatch.setenv("DIRICHLET_K", diagnostic.FITTED_K_TEXT)
    with pytest.raises(ValueError, match="while fitted-K usage is inactive"):
        diagnostic._accepted_usage_law()


def test_cache_environment_is_licensed_and_restored(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "original")
    with diagnostic._cache_environment(diagnostic.CONTROL_TABLE):
        assert diagnostic.os.environ["TABPFN_MARGINAL_TABLE"] == diagnostic.CONTROL_TABLE
    assert diagnostic.os.environ["TABPFN_MARGINAL_TABLE"] == "original"
    with pytest.raises(ValueError, match="unlicensed active-label cache"):
        with diagnostic._cache_environment("tabpfn_projections"):
            pass


def test_cli_and_cloud_runner_are_packaged():
    root = Path(__file__).resolve().parents[1]
    cli = (root / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    runner = root / "scripts/cloud_tabpfn_active_label_final_served.sh"
    assert "tabpfn-active-label-final-served" in cli
    assert runner.is_file()
    text = runner.read_text(encoding="utf-8")
    assert "20260811-tabpfn-active-label-final-served-v1" in text
    assert "usage_dirichlet_exact80_comparison.json" in text
