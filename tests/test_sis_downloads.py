import json
from dataclasses import asdict

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
        "runs-to-gap-totals", "runs-to-gap-value",
        "adjusted-blown-blocks",
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

    def header_value(self, _name):
        return "application/json"


def test_response_scope_and_row_cap_fail_closed():
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-totals", season=2025,
        start_week=1, end_week=1, team_id=2,
    )
    post = (
        "MetricGroup=9&MetricGroupSubType=9.1&TimeFilters.SeasonFrom=2025&"
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


def test_response_scope_rejects_wrong_report_subtype():
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-value", season=2025,
        start_week=1, end_week=1,
    )
    wrong = _Response(
        "MetricGroup=9&MetricGroupSubType=9.1&TimeFilters.SeasonFrom=2025&"
        "TimeFilters.SeasonTo=2025&TimeFilters.StartWeek=1&"
        "TimeFilters.EndWeek=1&TimeFilters.ByGame=1",
        [{"season": 2025, "week": 1, "games": 1}],
    )
    assert not sis._response_matches_spec(wrong, spec)


def test_non_json_api_response_has_audit_error():
    response = _Response("", [], status=429)
    with pytest.raises(RuntimeError, match="HTTP 429"):
        sis._api_rows(response, "submitted")


def test_csv_scope_validation(tmp_path):
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-totals", season=2025,
        start_week=1, end_week=2,
    )
    path = tmp_path / "sis.csv"
    path.write_text(
        "Rank,Season,Week,Opp.,Games,Player,Catchable,Pass Def.\n"
        "1,2025,1,ATL,1,A,2,1\n2,2025,2,BUF,1,B,3,1\n",
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
        "Rank,Season,Week,Opp.,Player,Points Saved,PS Per Play,Boom%,Bust%\n"
        "[object Object],2025,1,ATL,A,0.5,0.1,10%,5%\n",
        encoding="utf-8",
    )
    sis._validate_csv_scope(path, spec, expected_rows=1)


def test_value_csv_rejects_stale_totals_view(tmp_path):
    spec = sis.ExportSpec(
        entity="teams", report="passing-value", season=2025,
        start_week=1, end_week=1,
    )
    path = tmp_path / "stale.csv"
    path.write_text(
        "Rank,Season,Team,Week,Opp.,Games,Dropbacks,Gross Yds\n"
        "1,2025,ARI,1,DET,1,30,250\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="view differs"):
        sis._validate_csv_scope(path, spec, expected_rows=1)


def test_alignment_sample_analysis_uses_only_frozen_volume_columns(tmp_path):
    artifacts = []
    rows = {
        "left": [(101, "Alpha WR", "WR", 1), (102, "Beta WR", "WR", 3)],
        "slot": [(101, "Alpha WR", "WR", 3), (102, "Beta WR", "WR", 15)],
        "right": [(101, "Alpha WR", "WR", 16), (102, "Beta WR", "WR", 2)],
        "lcb": [(201, "Corner A", "CB", 18), (202, "Corner B", "CB", 2)],
        "rcb": [(201, "Corner A", "CB", 1), (202, "Corner B", "CB", 2)],
        "scb": [(201, "Corner A", "CB", 1), (202, "Corner B", "CB", 16)],
    }
    for family, filter_name, filter_values, slice_name in sis.ALIGNMENT_SAMPLE_SLICES:
        path = tmp_path / sis._alignment_sample_artifact(slice_name)
        volume = "Routes" if family == "receiving" else "Cov. Snaps"
        path.write_text(
            f"Rank,Season,Player,Team,Week,Opp.,Pos.,Games,{volume}\n" +
            "".join(
                f"1,2025,{name},T,1,O,{position},1,{value}\n"
                for _pid, name, position, value in rows[slice_name]
            ), encoding="utf-8")
        artifacts.append({
            "family": family, "filter_name": filter_name,
            "filter_values": list(filter_values), "slice": slice_name,
            "artifact": path.name, "sha256": sis._sha256(path),
            "identities": [
                {"playerId": pid, "player": name}
                for pid, name, _position, _value in rows[slice_name]
            ],
        })
    result = sis.analyze_alignment_feasibility_sample(tmp_path, {
        "api_requests_used": 12, "artifacts": artifacts})
    assert result["passes"]
    assert result["receiver"]["player"] == "Alpha WR"
    assert result["receiver"]["shares"]["right"] == pytest.approx(0.8)
    assert result["best_alignment_overlap"] == pytest.approx(0.73)
    assert result["outcome_columns_read"] == []


def test_blocking_csv_can_call_season_year(tmp_path):
    spec = sis.ExportSpec(
        entity="teams", report="blocking-totals", season=2019,
        start_week=1, end_week=1,
    )
    path = tmp_path / "sis-blocking.csv"
    path.write_text(
        "Rank,Year,Team,Week,Opp.,Games,Snaps,PassSnap,RushSnap\n"
        "1,2019,ARI,1,DET,1,60,40,20\n", encoding="utf-8")
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


class _Route:
    def __init__(self):
        self.action = None

    def continue_(self):
        self.action = "continue"

    def abort(self, reason):
        self.action = reason


def test_api_request_budget_blocks_before_overage():
    budget = sis.APIRequestBudget(ceiling=2)
    first, second, third = _Route(), _Route(), _Route()
    budget.route(first)
    budget.route(second)
    budget.route(third)
    assert first.action == second.action == "continue"
    assert third.action == "blockedbyclient"
    assert budget.used == 2


def test_submit_only_budget_does_not_count_incidental_refreshes():
    budget = sis.APIRequestBudget(ceiling=2)
    guarded = sis.SubmitOnlyAPIRequestBudget(budget)
    incidental, submit = _Route(), _Route()
    guarded.route(incidental)
    assert incidental.action == "blockedbyclient"
    assert budget.used == 0
    guarded.armed = True
    guarded.route(submit)
    assert submit.action == "continue"
    assert budget.used == 1


def test_api_request_budget_persists_across_processes(tmp_path):
    state_path = tmp_path / "state.json"
    budget = sis.APIRequestBudget(
        ceiling=5, state_path=state_path, plan_sha256="abc")
    budget.route(_Route())
    payload = json.loads(state_path.read_text())
    assert payload["used"] == 1
    assert payload["ceiling"] == 5
    assert payload["plan_sha256"] == "abc"


def test_alignment_sampler_loads_existing_request_count():
    source = sis.run_alignment_feasibility_sample.__code__
    assert "used" in source.co_varnames


def test_alignment_sample_slices_are_exact_six_call_repair():
    assert len(sis.ALIGNMENT_SAMPLE_SLICES) == 6
    assert sis.ALIGNMENT_SAMPLE_SLICES[1] == (
        "receiving", "ReceivingFilters.RecAlignment", ("2", "5"), "slot")


def test_team_pass_defense_schema_slices_are_frozen_and_bounded():
    assert sis.TEAM_PASS_DEFENSE_PROFILE_REPORTS == (
        "pass-defense-totals", "pass-defense-value")
    assert sis.TEAM_PASS_DEFENSE_PROFILE_SLICES == (
        ("wide-man", ("2",), ("0", "1", "5")),
        ("wide-zone", ("2",), ("2", "3", "4", "6")),
        ("slot-man", ("3",), ("0", "1", "5")),
        ("slot-zone", ("3",), ("2", "3", "4", "6")),
    )
    assert len(sis.TEAM_PASS_DEFENSE_PROFILE_REPORTS) * len(
        sis.TEAM_PASS_DEFENSE_PROFILE_SLICES
    ) == 8


def test_asoe_acquisition_grid_is_frozen_and_subcap():
    assert sis.ASOE_SEASONS == (2022, 2023, 2024, 2025)
    assert sis.ASOE_WINDOWS == ((1, 6), (7, 12), (13, 17))
    assert sis.ASOE_ALIGNMENTS == (("wide", ("2",)), ("slot", ("3",)))
    assert set(sis.ASOE_ALL_SCHEMES) == {"0", "1", "2", "3", "4", "5", "6"}
    assert len(sis.ASOE_SEASONS) * len(sis.ASOE_WINDOWS) * len(
        sis.ASOE_ALIGNMENTS
    ) == 24
    assert max(end - start + 1 for start, end in sis.ASOE_WINDOWS) * 32 < 200
    assert sis._asoe_artifact(2025, 13, 17, "slot") == (
        "2025-weeks13-17-team-pass-defense__slot__pass-defense-totals.csv"
    )


def test_asoe_acquisition_analyzer_reads_attempts_not_performance(tmp_path):
    artifacts = []
    for season in sis.ASOE_SEASONS:
        for start, end in sis.ASOE_WINDOWS:
            for alignment, values in sis.ASOE_ALIGNMENTS:
                path = tmp_path / sis._asoe_artifact(
                    season, start, end, alignment)
                path.write_text(
                    "Rank,Season,Team,Week,Opp.,Games,Att,Catchable,Pass Def.\n"
                    + "\n".join(
                        f"1,{season},T{team}," + str(start)
                        + ",O,1,2,1,0"
                        for team in range(1, 33)
                    )
                    + "\n",
                    encoding="utf-8",
                )
                filters = {
                    "PassDefenseFilters.TargetLinedUp": list(values),
                    "PassDefenseFilters.Schemes": list(sis.ASOE_ALL_SCHEMES),
                    "PassDefenseFilters.ReceiverPos": ["4"],
                    "PassDefenseFilters.MinTargets": ["0"],
                    "PassDefenseFilters.MinAttempts": ["0"],
                }
                artifacts.append({
                    "season": season,
                    "start_week": start,
                    "end_week": end,
                    "alignment": alignment,
                    "artifact": path.name,
                    "sha256": sis._sha256(path),
                    "rows": 32,
                    "headers": [
                        "Rank", "Season", "Team", "Week", "Opp.",
                        "Games", "Att", "Catchable", "Pass Def.",
                    ],
                    "submitted_scope": filters,
                    "identities": [{
                        "season": season,
                        "week": start,
                        "games": 1,
                        "teamId": team,
                        "team": f"T{team}",
                        "opp": "O",
                    } for team in range(1, 33)],
                })
    result = sis.analyze_team_pass_defense_asoe_acquisition(tmp_path, {
        "api_requests_used": 24,
        "api_request_ceiling": 26,
        "artifacts": artifacts,
    })
    assert result["passes"]
    assert result["artifact_count"] == 24
    assert result["attempts"] == 24 * 32 * 2
    assert result["opportunity_columns_read"] == ["Att"]
    assert result["performance_values_read"] == []


class _SubtypeParent:
    def __init__(self):
        self.class_name = ""


class _SubtypeControl:
    def __init__(self, page):
        self.page = page
        self.parent = _SubtypeParent()

    def wait_for(self, **_kwargs):
        return None

    def get_attribute(self, name):
        return str(self.page.definition.subtype) if name == "value" else None

    def evaluate(self, script, *args):
        if "parentElement.className" in script:
            return self.parent.class_name
        if "element.click()" in script:
            self.page.incidental_refreshes += 1
            self.parent.class_name = "active"
            return None
        raise AssertionError(script)


class _HiddenSubtype:
    def __init__(self, page):
        self.page = page

    def evaluate(self, _script, value):
        self.page.hidden_subtype = value
        return True

    def input_value(self):
        return self.page.hidden_subtype


class _MainTab:
    def __init__(self, page):
        self.page = page

    def wait_for(self, **_kwargs):
        return None

    def get_attribute(self, name):
        return str(self.page.definition.metric_group) if name == "value" else None


class _HiddenGroup:
    def __init__(self, page):
        self.page = page

    def evaluate(self, _script, value):
        self.page.hidden_group = value
        return True


class _SubtypePage:
    def __init__(self, definition):
        self.definition = definition
        self.hidden_group = "1"
        self.hidden_subtype = "1"
        self.incidental_refreshes = 0
        self.main = _MainTab(self)
        self.subtype = _SubtypeControl(self)
        self.hidden_group_control = _HiddenGroup(self)
        self.hidden_subtype_control = _HiddenSubtype(self)

    def locator(self, selector):
        return {
            f"#{self.definition.main_tab}": self.main,
            f"#{self.definition.subtab}": self.subtype,
            "#MetricGroup": self.hidden_group_control,
            "#MetricGroupSubType": self.hidden_subtype_control,
        }[selector]


def test_report_activation_sets_hidden_scope_and_visible_active_tab():
    definition = sis.REPORTS["pass-defense-value"]
    page = _SubtypePage(definition)
    sis._activate_report_view_without_refresh(page, definition)
    assert page.hidden_group == "9"
    assert page.hidden_subtype == "9.3"
    assert page.subtype.parent.class_name == "active"
    # The helper deliberately triggers the site's refresh handler; the live
    # sampler route remains disarmed and blocks that unmetered request.
    assert page.incidental_refreshes == 1


def _defense_profile_fixture(tmp_path, *, team_count=32, mismatched=False):
    artifacts = []
    for report in sis.TEAM_PASS_DEFENSE_PROFILE_REPORTS:
        for slice_name, alignment, schemes in sis.TEAM_PASS_DEFENSE_PROFILE_SLICES:
            path = tmp_path / sis._team_pass_defense_artifact(report, slice_name)
            if report == "pass-defense-totals":
                header = (
                    "Rank,Season,Team,Week,Opp.,Games,Cov. Snaps,Tgts,"
                    "Catchable,Pass Def.\n"
                )
            else:
                header = (
                    "Rank,Season,Team,Week,Opp.,Points Saved,PS Per Play,"
                    "Boom%,Bust%\n"
                )
            path.write_text(header + "\n".join(
                f"1,2025,T{team_id},1,O,1,1,1,1,1"
                if report == "pass-defense-totals"
                else f"1,2025,T{team_id},1,O,0.0,0.0,0%,0%"
                for team_id in range(
                    1, team_count + 1 - (
                        1 if mismatched and report == "pass-defense-value"
                        and slice_name == "wide-man" else 0
                    )
                )
            ) + "\n", encoding="utf-8")
            ids = list(range(
                1, team_count + 1 - (
                    1 if mismatched and report == "pass-defense-value"
                    and slice_name == "wide-man" else 0
                )
            ))
            artifacts.append({
                "report": report,
                "slice": slice_name,
                "artifact": path.name,
                "sha256": sis._sha256(path),
                "rows": len(ids),
                "headers": header.strip().split(","),
                "submitted_scope": {
                    "PassDefenseFilters.TargetLinedUp": list(alignment),
                    "PassDefenseFilters.Schemes": list(schemes),
                    "PassDefenseFilters.ReceiverPos": ["4"],
                    "PassDefenseFilters.MinTargets": ["0"],
                    "PassDefenseFilters.MinAttempts": ["0"],
                },
                "identities": [{
                    "season": 2025, "week": 1, "games": 1,
                    "teamId": team_id, "team": f"T{team_id}", "opp": "O",
                } for team_id in ids],
            })
    return {
        "api_requests_used": 8,
        "api_request_ceiling": 10,
        "artifacts": artifacts,
    }


def test_team_pass_defense_schema_analysis_reads_only_schema_and_identity(tmp_path):
    result = sis.analyze_team_pass_defense_schema_sample(
        tmp_path, _defense_profile_fixture(tmp_path)
    )
    assert result["passes"]
    assert result["disposition"] == "sis-team-pass-defense-schema-passes"
    assert result["union_team_count"] == 32
    assert set(result["slice_team_counts"].values()) == {32}
    assert result["outcome_values_read"] == []


def test_team_pass_defense_schema_rejects_mismatched_views(tmp_path):
    result = sis.analyze_team_pass_defense_schema_sample(
        tmp_path, _defense_profile_fixture(tmp_path, mismatched=True)
    )
    assert not result["passes"]
    assert "wide-man:totals-value-team-mismatch" in result["failures"]


def test_team_pass_defense_schema_rejects_missing_teams_and_cap(tmp_path):
    manifest = _defense_profile_fixture(tmp_path, team_count=31)
    manifest["artifacts"][0]["rows"] = 200
    result = sis.analyze_team_pass_defense_schema_sample(tmp_path, manifest)
    assert not result["passes"]
    assert "union-team-count:31" in result["failures"]
    assert any(failure.endswith(":row-cap") for failure in result["failures"])


def test_identity_rows_retain_ids_and_scope_without_metrics():
    response = _Response("", [{
        "season": 2025, "week": 1, "games": 1, "playerId": 77,
        "playerTeamId": 3, "teamId": 4, "player": "A", "team": "B",
        "opp": "C", "pointsSaved": 2.5,
    }])
    assert sis._identity_rows(response) == [{
        "games": 1, "opp": "C", "player": "A", "playerId": 77,
        "playerTeamId": 3, "season": 2025, "team": "B", "teamId": 4,
        "week": 1,
    }]


def test_verified_existing_is_resumable_and_fails_on_hash_drift(tmp_path):
    spec = sis.ExportSpec(
        entity="players", report="pass-defense-value", season=2025,
        start_week=1, end_week=1, team_id=1,
    )
    artifact = tmp_path / sis.artifact_name(spec)
    artifact.write_text(
        "Rank,Season,Week,Opp.,Player,Points Saved,PS Per Play,Boom%,Bust%\n"
        "[object Object],2025,1,ATL,A,0.5,0.1,10%,5%\n",
        encoding="utf-8")
    manifest = sis._manifest_path(tmp_path, artifact.name)
    manifest.write_text(json.dumps({
        "spec": asdict(spec), "sha256": sis._sha256(artifact), "rows": 1,
    }), encoding="utf-8")
    assert sis._verified_existing(tmp_path, spec)
    artifact.write_text(artifact.read_text() + "corrupt\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="hash differs"):
        sis._verified_existing(tmp_path, spec)


def test_run_plan_refuses_existing_artifact_without_budget_state(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({
        "schema_version": 1, "max_exports": 1, "max_api_requests": 10,
        "exports": [{
            "entity": "players", "season": 2025, "start_week": 1,
            "end_week": 1, "reports": ["pass-defense-value"],
        }],
    }), encoding="utf-8")
    spec = sis.load_plan(plan)[0]
    output = tmp_path / "output"
    output.mkdir()
    (output / sis.artifact_name(spec)).write_text("partial history")
    with pytest.raises(RuntimeError, match="request state is missing"):
        sis.run_plan(tmp_path / "profile", 1, output, plan)
