import pytest

from nfl_dfs.ops import sis_downloads as sis


def test_default_profile_is_outside_repository(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    profile = tmp_path / "nfl-dfs" / "sis-playwright"
    assert sis.default_profile_dir() == profile
    assert sis.default_storage_state_path(profile) == (
        tmp_path / "nfl-dfs" / "sis-playwright-storage-state.json"
    )


def test_authenticated_url_requires_protected_sis_host():
    assert sis._authenticated_url("https://pro.sisdatahub.com/NFL/Leaders/Players")
    assert not sis._authenticated_url(
        "https://auth.sportsinfosolutions.com/Account/Login"
    )
    assert not sis._authenticated_url("https://store.sportsinfosolutions.com/Purchase")


def test_cli_help_exits_cleanly():
    with pytest.raises(SystemExit) as exc_info:
        sis.main(["--help"])
    assert exc_info.value.code == 0


def test_catalog_covers_high_priority_value_and_denominator_views():
    expected = {
        "passing-totals", "passing-value",
        "receiving-totals", "receiving-value",
        "pass-defense-totals", "pass-defense-value",
        "pass-rush-totals", "pass-rush-value",
        "run-defense-totals", "run-defense-value",
        "blocking-totals", "blocking-value",
    }
    assert expected <= set(sis.REPORTS)
    assert sis.REPORTS["pass-defense-value"].subtype == 9.3
    assert sis.REPORTS["returning-totals"].priority == 3


def test_export_spec_validation_and_name():
    spec = sis.ExportSpec(
        entity="players", report="receiving-value", season=2025,
        start_week=1, end_week=4, split_by_game=True, team_id=7,
    )
    assert sis.artifact_name(spec) == (
        "players__receiving-value__season-2025__weeks-01-04"
        "__team-7__game.csv"
    )
    with pytest.raises(ValueError, match="week range"):
        sis.validate_spec(sis.ExportSpec(
            entity="players", report="receiving-value", season=2025,
            start_week=4, end_week=3,
        ))


class _Request:
    def __init__(self, post_data):
        self.post_data = post_data


class _Response:
    def __init__(self, post_data, data, status=200):
        self.url = "https://api.sisdatahub.com/api/v1/nfl/players/query"
        self.request = _Request(post_data)
        self.status = status
        self._data = data

    def json(self):
        return {"data": self._data}


def test_response_scope_and_row_cap_fail_closed():
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-totals", season=2025,
        start_week=1, end_week=1, team_id=2,
    )
    post = (
        "MetricGroup=9&TimeFilters.SeasonFrom=2025&"
        "TimeFilters.SeasonTo=2025&TimeFilters.StartWeek=1&"
        "TimeFilters.EndWeek=1&TimeFilters.ByGame=1&GameFilters.Team=2"
    )
    response = _Response(post, [{
        "season": 2025, "week": 1, "games": 1, "teamId": 2,
    }])
    assert sis._response_matches_spec(response, spec)
    assert sis._assert_api_scope(response, spec, row_cap=200) == 1
    capped = _Response(post, response._data * 200)
    with pytest.raises(sis.RowCapError, match="paid row cap"):
        sis._assert_api_scope(capped, spec, row_cap=200)


def test_csv_scope_validation(tmp_path):
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-totals", season=2025,
        start_week=1, end_week=2,
    )
    path = tmp_path / "sis.csv"
    path.write_text(
        "Rank,Season,Week,Opp.,Games,Player\n"
        "1,2025,1,ATL,1,A\n2,2025,2,BUF,1,B\n",
        encoding="utf-8",
    )
    sis._validate_csv_scope(path, spec, expected_rows=2)
    with pytest.raises(RuntimeError, match="API returned"):
        sis._validate_csv_scope(path, spec, expected_rows=3)


def test_value_csv_can_omit_games_when_api_proved_game_grain(tmp_path):
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-value", season=2025,
        start_week=1, end_week=1, team_id=1,
    )
    path = tmp_path / "sis-value.csv"
    path.write_text(
        "Rank,Season,Week,Opp.,Player,Points Saved\n"
        "[object Object],2025,1,ATL,A,0.5\n",
        encoding="utf-8",
    )
    sis._validate_csv_scope(path, spec, expected_rows=1)


def test_load_plan_expands_seasons_windows_and_enforces_budget(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(
        """{
          "schema_version": 1,
          "max_exports": 4,
          "max_api_requests": 20,
          "exports": [{
            "entity": "teams",
            "seasons": [2024, 2025],
            "week_windows": [[1, 6]],
            "reports": ["pass-defense-totals", "pass-defense-value"]
          }]
        }""",
        encoding="utf-8",
    )
    specs = sis.load_plan(plan)
    assert len(specs) == 4
    assert {spec.season for spec in specs} == {2024, 2025}
    assert sis.plan_request_ceiling(plan) == 20
    plan.write_text(plan.read_text().replace('"max_exports": 4', '"max_exports": 3'))
    with pytest.raises(ValueError, match="above max_exports"):
        sis.load_plan(plan)
