import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nfl_dfs.ops.fantasy_points_downloads import (
    EXPECTED_CATALOG,
    REPORTS,
    ExportSpec,
    _assert_values_response_scope,
    _game_count_from_rendered_row,
    _reuse_download_prefix,
    _validate_download_scope,
    artifact_name,
    compact_weeks,
    expand_plan,
    load_plan,
    parse_weeks,
    select_target_week,
)


class _Response:
    status = 200

    def __init__(self, payload):
        self.request = SimpleNamespace(post_data=json.dumps(payload))

    def json(self):
        return {"content": {}, "errors": []}


def test_parse_weeks_accepts_ranges_lists_and_mixtures():
    assert parse_weeks("1-4") == (1, 2, 3, 4)
    assert parse_weeks("1,3-5") == (1, 3, 4, 5)
    assert parse_weeks([4, 2, 2]) == (2, 4)


@pytest.mark.parametrize("bad", ["", "5-2", "0", "23", {"week": 1}])
def test_parse_weeks_rejects_unsafe_windows(bad):
    with pytest.raises(ValueError):
        parse_weeks(bad)


def test_expand_plan_is_deterministic_and_names_point_in_time_filters():
    plan = {
        "schema_version": 1,
        "reports": [
            {
                "report": "advanced-receiving",
                "seasons": [2024, 2025],
                "week_windows": ["1-4", "1,3-5"],
            }
        ],
    }
    specs = expand_plan(plan)
    assert len(specs) == 4
    assert specs[0].include_group_headers is True
    assert artifact_name(specs[-1]) == (
        "advanced-receiving__season-2025__weeks-01_03-05.csv"
    )
    assert compact_weeks((1, 2, 3, 4, 7)) == "01-04_07"


def test_load_checked_in_window_plan():
    root = Path(__file__).resolve().parents[1]
    payload, specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "advanced-receiving-window-check.json"
    )
    assert payload["name"] == "advanced-receiving-window-semantics-v1"
    assert [spec.weeks for spec in specs] == [(1, 2, 3, 4), (5, 6, 7, 8)]
    assert all(spec.season == 2025 for spec in specs)


def test_load_checked_in_coverage_matrix_window_plan():
    root = Path(__file__).resolve().parents[1]
    payload, specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "coverage-matrix-window-check.json"
    )
    assert payload["name"] == "coverage-matrix-window-semantics-v1"
    assert [spec.weeks for spec in specs] == [(1, 2, 3, 4), (5, 6, 7, 8)]
    assert all(spec.context == "Defense" for spec in specs)

    _, offense_specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "coverage-matrix-offense-window-check.json"
    )
    assert [spec.weeks for spec in offense_specs] == [
        (1, 2, 3, 4),
        (5, 6, 7, 8),
    ]
    assert all(spec.context == "Offense" for spec in offense_specs)


def test_load_checked_in_high_priority_window_plan():
    root = Path(__file__).resolve().parents[1]
    payload, specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "high-priority-window-check.json"
    )
    assert payload["name"] == "high-priority-window-semantics-v1"
    assert len(specs) == 16
    assert all(max(spec.weeks) - min(spec.weeks) == 3 for spec in specs)


def test_catalog_guard_covers_every_live_menu_report():
    assert len(EXPECTED_CATALOG) == 28
    assert len(REPORTS) == 25
    assert set(EXPECTED_CATALOG) - {
        definition.property for definition in REPORTS.values()
    } == {"qbCoverageMatchup", "wrCoverageMatchup", "lineMatchups"}


def test_load_checked_in_remaining_catalog_window_plan():
    root = Path(__file__).resolve().parents[1]
    payload, specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "remaining-catalog-window-check.json"
    )
    assert payload["name"] == "remaining-catalog-window-semantics-v1"
    assert len(specs) == 18
    assert len({spec.report for spec in specs}) == 9
    assert all(spec.context == "Player" for spec in specs)


def test_load_checked_in_same_season_coverage_plan():
    root = Path(__file__).resolve().parents[1]
    payload, specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "same-season-coverage-last-four-v1.json"
    )
    assert payload["name"] == "same-season-coverage-last-four-v1"
    assert len(specs) == 3 * 4 * 14
    assert {spec.definition.key for spec in specs} == {
        "receiving-man-vs-zone",
        "receiving-separation-by-coverage",
        "coverage-matrix",
    }
    assert all(spec.target_week in range(5, 19) for spec in specs)
    assert all(
        spec.weeks == tuple(range(spec.target_week - 4, spec.target_week))
        for spec in specs
    )


def test_load_checked_in_same_season_route_shape_plan():
    root = Path(__file__).resolve().parents[1]
    payload, specs = load_plan(
        root
        / "automation"
        / "fantasy_points"
        / "plans"
        / "same-season-route-shape-last-four-v1.json"
    )
    assert payload["name"] == "same-season-route-shape-last-four-v1"
    assert len(specs) == 56
    assert {spec.report for spec in specs} == {
        "receiving-separation-by-breaks"
    }
    assert all(spec.target_week in range(5, 19) for spec in specs)
    assert all(
        spec.weeks == tuple(range(spec.target_week - 4, spec.target_week))
        for spec in specs
    )


def test_plan_rejects_duplicate_export():
    plan = {
        "schema_version": 1,
        "reports": [
            {
                "report": "route-share",
                "seasons": [2025],
                "week_windows": ["1-4", [1, 2, 3, 4]],
            }
        ],
    }
    with pytest.raises(ValueError, match="duplicate export"):
        expand_plan(plan)


def test_generated_prior_windows_enforce_target_week_boundary():
    plan = {
        "schema_version": 1,
        "reports": [
            {
                "report": "advanced-receiving",
                "seasons": [2025],
                "target_weeks": "5-7",
                "source_window": "last-four-prior",
                "context": "Player",
            }
        ],
    }
    specs = expand_plan(plan)
    assert [(spec.target_week, spec.weeks) for spec in specs] == [
        (5, (1, 2, 3, 4)),
        (6, (2, 3, 4, 5)),
        (7, (3, 4, 5, 6)),
    ]
    assert artifact_name(specs[0]) == (
        "advanced-receiving__season-2025__weeks-01-04"
        "__target-week-05__context-player.csv"
    )


def test_previous_week_plan_and_runtime_target_selection():
    plan = {
        "schema_version": 1,
        "reports": [{
            "report": "route-share",
            "seasons": [2026],
            "target_weeks": "2-4",
            "source_window": "previous-week",
        }],
    }
    specs = expand_plan(plan)
    assert [(spec.target_week, spec.weeks) for spec in specs] == [
        (2, (1,)), (3, (2,)), (4, (3,)),
    ]
    selected = select_target_week(specs, 3)
    assert len(selected) == 1
    assert selected[0].weeks == (2,)
    with pytest.raises(ValueError, match="declares no exports"):
        select_target_week(specs, 5)


def test_generated_window_rejects_target_week_one():
    plan = {
        "schema_version": 1,
        "reports": [
            {
                "report": "route-share",
                "seasons": [2025],
                "target_weeks": [1],
                "source_window": "cumulative-prior",
            }
        ],
    }
    with pytest.raises(ValueError, match="target week"):
        expand_plan(plan)


def test_apply_response_must_carry_exact_season_and_weeks():
    spec = ExportSpec(
        "receiving-man-vs-zone", 2022, (1, 2, 3, 4), True, "Player", 5)
    response = _Response({
        "context": {
            "weeks": {"REG": [1, 2, 3, 4]},
            "filterMatch": {"game.season": {"eq": 2022}},
        },
    })
    _assert_values_response_scope(response, spec)
    response.request.post_data = json.dumps({
        "context": {
            "weeks": {"REG": [1, 2, 3, 4]},
            "filterMatch": {"game.season": {"eq": 2025}},
        },
    })
    with pytest.raises(RuntimeError, match="scope differs"):
        _assert_values_response_scope(response, spec)


def test_download_scope_rejects_stale_full_season_csv(tmp_path):
    spec = ExportSpec(
        "receiving-man-vs-zone", 2022, (1, 2, 3, 4), True, "Player", 5)
    path = tmp_path / "window.csv"
    path.write_text(
        "Player Details,,,,,,Overall\n"
        "Rank,Name,Team,POS,G,Season,RTE\n"
        "1,Receiver,NYJ,WR,4,2022,100\n"
    )
    _validate_download_scope(path, spec)
    path.write_text(
        "Player Details,,,,,,Overall\n"
        "Rank,Name,Team,POS,G,Season,RTE\n"
        "1,Receiver,NYJ,WR,17,2025,600\n"
    )
    with pytest.raises(RuntimeError, match="contains seasons"):
        _validate_download_scope(path, spec)


def test_rendered_game_count_supports_player_and_team_rows():
    assert _game_count_from_rendered_row(
        ["1", "Receiver", "NYJ", "WR", "4", "100"]
    ) == 4
    assert _game_count_from_rendered_row(
        ["1", "Baltimore Ravens", "4", "195", "28.7%"]
    ) == 4
    assert _game_count_from_rendered_row(
        ["Rank", "Name", "G", "DB"]
    ) is None
    assert _game_count_from_rendered_row(
        ["175", "166", "121", "72.9%", "1119"]
    ) is None
    assert _game_count_from_rendered_row(
        ["1", "Buffalo Bills", "QB", "4", "143"]
    ) == 4


def test_reuse_prefix_revalidates_and_copies_download(tmp_path):
    prior = tmp_path / "prior"
    destination = tmp_path / "next"
    prior.mkdir()
    destination.mkdir()
    spec = ExportSpec(
        "receiving-man-vs-zone", 2022, (1, 2, 3, 4), True, "Player", 5)
    name = artifact_name(spec)
    source = prior / name
    source.write_text(
        "Player Details,,,,,,Overall\n"
        "Rank,Name,Team,POS,G,Season,RTE\n"
        "1,Receiver,NYJ,WR,4,2022,100\n"
    )
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "run_id": "prior-run",
        "plan_sha256": "plan-hash",
        "exports": [{
            "status": "downloaded",
            "report": spec.report,
            "season": spec.season,
            "weeks": list(spec.weeks),
            "include_group_headers": spec.include_group_headers,
            "context": spec.context,
            "target_week": spec.target_week,
            "path": name,
            "bytes": source.stat().st_size,
            "csv_rows_including_headers": 3,
            "max_csv_columns": 7,
            "sha256": digest,
        }],
    }
    (prior / "manifest.json").write_text(json.dumps(manifest))
    reused, run_id = _reuse_download_prefix(
        prior, destination, [spec], plan_sha256="plan-hash")
    assert run_id == "prior-run"
    assert reused[0]["reused_from_run_id"] == "prior-run"
    assert (destination / name).read_bytes() == source.read_bytes()

    source.write_text(source.read_text() + "2,Other,NYJ,WR,4,2022,90\n")
    with pytest.raises(ValueError, match="hash differs"):
        _reuse_download_prefix(
            prior, destination, [spec], plan_sha256="plan-hash")
