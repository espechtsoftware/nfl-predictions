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


def test_v2_usage_law_requires_machine_selected_branch(monkeypatch):
    monkeypatch.setattr(diagnostic, "VERSION", "v2")
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    monkeypatch.delenv("DIRICHLET_K", raising=False)
    monkeypatch.delenv("TABPFN_ACCEPTED_USAGE_LAW", raising=False)
    monkeypatch.delenv("TABPFN_ACCEPTED_DIRICHLET_K", raising=False)
    with pytest.raises(ValueError, match="explicit accepted usage law"):
        diagnostic._accepted_usage_law()

    monkeypatch.setenv("TABPFN_ACCEPTED_USAGE_LAW", "multinomial")
    assert diagnostic._accepted_usage_law()["mode"] == "production-multinomial"

    monkeypatch.setenv("TABPFN_ACCEPTED_USAGE_LAW", "dirichlet")
    monkeypatch.setenv("TABPFN_ACCEPTED_DIRICHLET_K", "31.125")
    monkeypatch.setenv("GAME_SIM_USAGE", "dirichlet")
    monkeypatch.setenv("DIRICHLET_K", "31.125")
    assert diagnostic._accepted_usage_law()["k"] == "31.125"
    monkeypatch.setenv("DIRICHLET_K", "31.126")
    with pytest.raises(ValueError, match="differs from its accepted fitted K"):
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
    v2_runner = root / "scripts/cloud_tabpfn_active_label_final_served_v2.sh"
    v2_text = v2_runner.read_text(encoding="utf-8")
    assert "tabpfn_active_label_control_v2" in v2_text
    assert "TABPFN_ACCEPTED_USAGE_LAW" in v2_text
    assert "SELECTED_USAGE.txt" in v2_text
    assert 'decision.get("allocation")' in v2_text
    assert 'decision.get("selected_k"' in v2_text
    assert 'decision.get("historical_source")' in v2_text
    v2_finish = (
        root / "scripts/cloud_finish_tabpfn_active_label_final_served_v2.sh"
    ).read_text(encoding="utf-8")
    assert "TABPFN_ACTIVE_LABEL_FINAL_SERVED_JSON=" in v2_finish
    assert 'report.get("version") != "v2"' in v2_finish
    assert 'int(report.get("cache_rows", -1)) != 52307' in v2_finish
    assert 'manifest.get("accepted_usage_law")' in v2_finish
