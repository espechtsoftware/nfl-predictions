from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from nfl_dfs.bq import render_sql
from nfl_dfs.features import build as feature_build

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_receiver_matchup_features.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "build_receiver_matchup_features", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_research_sql_renders_without_unresolved_placeholders():
    for name in (
        "017l_receiver_week_role_pit.sql",
        "017m_defense_receiver_role_concession_pit.sql",
    ):
        rendered = render_sql(ROOT / "sql" / "research" / name)
        assert "${" not in rendered
        assert "CREATE OR REPLACE TABLE" in rendered
        # Strictly-prior windows are the PIT law: every window must end at
        # 1 PRECEDING and never touch the current row.
        assert "AND 1 PRECEDING" in rendered
        assert "CURRENT ROW" not in rendered


def test_research_sql_stays_out_of_the_production_build_glob():
    production = {
        path.name
        for path in sorted(
            (feature_build.SQL_DIR / "features").glob("*.sql")
        )
    }
    assert "017l_receiver_week_role_pit.sql" not in production
    assert "017m_defense_receiver_role_concession_pit.sql" not in production
    research = ROOT / "sql" / "research"
    assert (research / "017l_receiver_week_role_pit.sql").is_file()
    assert (research / "017m_defense_receiver_role_concession_pit.sql").is_file()


def test_runner_is_default_off_and_render_is_offline(monkeypatch, capsys):
    module = _load_runner()
    monkeypatch.delenv(module.ENABLE_ENV, raising=False)
    assert module.main(["execute", "--execute"]) == 2
    assert module.main(["execute"]) == 2
    monkeypatch.setenv(module.ENABLE_ENV, "1")
    assert module.main(["execute"]) == 2
    assert module.main(["render"]) == 0
    out = capsys.readouterr().out
    assert '"bigquery_contacted": false' in out


def test_validation_queries_cover_both_tables_and_pit_law():
    module = _load_runner()
    checks = dict(module.VALIDATION_QUERIES)
    assert "role-pit-strictly-prior" in checks
    assert "concession-strictly-prior" in checks
    for template in checks.values():
        assert "violations" in template
    assert any(
        "receiver_week_role_pit" in template for template in checks.values()
    )
    assert any(
        "defense_receiver_role_concession_pit" in template
        for template in checks.values()
    )
