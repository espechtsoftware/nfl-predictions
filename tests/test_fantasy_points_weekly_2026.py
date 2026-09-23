"""2026 weekly Fantasy Points last-four families: frozen plans, strict single-target manifests, the historical parser
applied to one 2026 window, append-once and the completeness guard (offline; synthetic exports)."""
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_qb_shell as qb_shell
from nfl_dfs.ingest import fantasy_points_weekly_2026 as weekly
from nfl_dfs.ingest.fantasy_points_coverage import TEAM_NAMES
from nfl_dfs.ops import fantasy_points_downloads as fp

PLANS = Path(__file__).resolve().parents[1] / "automation" / "fantasy_points" / "plans"
SNAPSHOTS = pd.DataFrame([
    {"season": 2026, "gsis_id": "wr1", "name": "Wide One", "pos": "WR", "team": "HOU"},
    {"season": 2026, "gsis_id": "te1", "name": "Tight One", "pos": "TE", "team": "HOU"},
    {"season": 2026, "gsis_id": "qb1", "name": "Quarter Back", "pos": "QB", "team": "HOU"},
])


def _grouped(path, header, rows):
    groups, names = zip(*header)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(groups)
        writer.writerow(names)
        writer.writerows(rows)


def _player_cols(extra):
    return [("Player Details", "Rank"), ("", "Name"), ("", "Team"), ("", "POS"), ("", "G"), ("", "Season"), *extra]


def _write(path, report, context, weeks):
    ident = lambda i, name, pos: [i, name, "HST", pos, min(4, len(weeks)), 2026]
    if report == "advanced-passing":
        feats = list(__import__("nfl_dfs.ingest.fantasy_points_same_season_passing", fromlist=["x"]).FEATURE_SPECS)
        extra = [("Passing", "DB"), ("Scrambles", "SCRM"), *[(f.split("::")[0], f.split("::")[1]) for f in feats]]
        _grouped(path, _player_cols(extra), [ident(1, "Quarter Back", "QB") + [150, 6] + ["10"] * len(feats)])
    elif report == "receiving-separation-by-breaks":
        extra = [("Overall", "RTE"), ("Horizontally Breaking", "RTE"), ("Vertically Breaking", "RTE"),
                 ("Static", "RTE"), ("Shallow/Underneath", "RTE"), ("Backfield", "RTE")]
        _grouped(path, _player_cols(extra), [ident(1, "Wide One", "WR") + [100, 30, 30, 20, 20, ""],
                                             ident(2, "Tight One", "TE") + [60, 10, 20, 20, 10, ""]])
    elif report == "receiving-man-vs-zone":
        extra = [(g, m) for g in ("Overall", "Man", "Zone") for m in ("RTE", "TPRR", "YPRR", "FP/RR")]
        _grouped(path, _player_cols(extra), [ident(1, "Wide One", "WR") + ["100", "0.2", "2.1", "0.5"] * 3])
    elif report == "receiving-separation-by-coverage":
        extra = [(g, m) for g in ("Overall", "Man", "Zone") for m in ("RTE", "SEP SCORE")]
        _grouped(path, _player_cols(extra), [ident(1, "Wide One", "WR") + ["100", "0.6"] * 3])
    elif report == "advanced-receiving":
        specs = list(__import__("nfl_dfs.ingest.fantasy_points_advanced_receiving_support",
                                fromlist=["x"]).METRIC_SPECS)
        extra = [("Receiving", "RTE"), *[(s.split("::")[0], s.split("::")[1]) for s in specs]]
        row = [1, "Wide One", "HST", "WR", min(len(weeks), 4), 2026, 120] + ["0.2"] * len(specs)
        _grouped(path, _player_cols(extra), [row])
    elif report == "coverage-matrix":
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Team"] + [""] * 21)
            writer.writerow(qb_shell._HEADER)
            for rank, name in enumerate(sorted(TEAM_NAMES)[:32], start=1):
                writer.writerow([rank, name, 4, 2026, "", name, 150, 30, 0.4, 70, 0.3, 50, 0.35, 50, 0.36,
                                 1, 20, 15, 5, 30, 20, 9])
    else:
        raise AssertionError(report)


def _run_dir(tmp_path, family, target_week, *, mutate=None):
    root = tmp_path / f"{family.key}-{target_week}"
    root.mkdir()
    now = datetime(2026, 10, 7, 15, tzinfo=UTC).isoformat()
    exports = []
    for w in family.windows:
        if target_week < w.first_target_week:
            continue
        weeks = weekly._weeks(w.kind, target_week)
        path = root / f"{w.report}-{w.context}-{w.kind}.csv"
        _write(path, w.report, w.context, weeks)
        rows = list(csv.reader(path.open()))
        exports.append({
            "status": "downloaded", "report": w.report, "season": 2026, "weeks": weeks,
            "include_group_headers": True, "context": w.context, "target_week": target_week,
            "retrieved_at_utc": now, "source_url": f"https://data.fantasypoints.com/nfl/tools/player/{w.report}",
            "path": path.name, "bytes": path.stat().st_size, "csv_rows_including_headers": len(rows),
            "max_csv_columns": max(map(len, rows)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    manifest = {"schema_version": 1, "status": "complete", "run_id": f"20261007T150000Z__{family.plan_name}",
                "plan_sha256": family.plan_sha256, "selected_target_week": target_week,
                "started_at_utc": now, "finished_at_utc": now, "exports": exports}
    if mutate:
        mutate(manifest)
    (root / "manifest.json").write_text(json.dumps(manifest))
    return root


@pytest.mark.parametrize("key", sorted(weekly.FAMILIES))
def test_frozen_plans_match_tracked_files_and_declare_the_family_windows(key):
    family = weekly.FAMILIES[key]
    path = PLANS / f"{family.plan_name}.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == family.plan_sha256
    _, specs = fp.load_plan(path)
    assert {s.season for s in specs} == {2026}
    for week in range(family.first_target_week, 19):
        declared = {(s.report, s.context, s.weeks) for s in fp.select_target_week(specs, week)}
        wanted = {(w.report, w.context, tuple(weekly._weeks(w.kind, week)))
                  for w in family.windows if week >= w.first_target_week}
        assert declared == wanted
        assert all(max(weeks) == week - 1 for _, _, weeks in declared)      # strictly prior


@pytest.mark.parametrize("key", ["advanced-passing", "route-shape", "coverage", "advanced-receiving"])
def test_one_2026_window_parses_through_the_historical_reader(tmp_path, key):
    family = weekly.FAMILIES[key]
    root = _run_dir(tmp_path, family, 6)
    manifest, artifacts = weekly.validate_manifest(family, root, target_week=6)
    tables = weekly.parse(family, manifest, artifacts, SNAPSHOTS, target_week=6)
    assert set(tables) == {t.name for t in family.tables}
    for table in family.tables:
        rows = tables[table.name]
        assert len(rows) and rows.season.eq(2026).all() and rows.target_week.eq(6).all()
        assert rows.source_week_end.eq(5).all()                              # W-1, never W
        assert not rows.duplicated(list(table.keys)).any()
        assert set(table.hash_columns) <= set(rows.columns)
        if "gsis_id" in rows:
            assert rows.gsis_id.notna().all()                                # resolved against 2026 rosters


def test_advanced_receiving_starts_cumulative_at_week_5_and_adds_last_four_at_6(tmp_path):
    family = weekly.FAMILIES["advanced-receiving"]
    for week, kinds in ((5, {"cumulative"}), (6, {"cumulative", "last_four"})):
        root = _run_dir(tmp_path, family, week)
        manifest, artifacts = weekly.validate_manifest(family, root, target_week=week)
        rows = weekly.parse(family, manifest, artifacts, SNAPSHOTS, target_week=week)[family.tables[0].name]
        assert set(rows.window_type) == kinds


def test_qb_shell_joins_the_same_weeks_coverage_defense_matrix(tmp_path):
    shell, cov = weekly.FAMILIES["qb-shell"], weekly.FAMILIES["coverage"]
    m1, a1 = weekly.validate_manifest(shell, _run_dir(tmp_path, shell, 7), target_week=7)
    m2, a2 = weekly.validate_manifest(cov, _run_dir(tmp_path, cov, 7), target_week=7)
    with pytest.raises(ValueError, match="coverage run"):
        weekly.parse(shell, m1, a1, SNAPSHOTS, target_week=7)
    rows = weekly.parse(shell, m1, a1, SNAPSHOTS, target_week=7, coverage_manifest=m2,
                        coverage_artifacts=a2)[qb_shell.TABLE]
    assert len(rows) == 32 and rows.source_week_end.eq(6).all()
    assert rows.source_run_id.eq(m1["run_id"] + "|" + m2["run_id"]).all()


@pytest.mark.parametrize("mutate, match", [
    (lambda m: m.update(plan_sha256="0" * 64), "frozen plan hash"),
    (lambda m: m["exports"][0].update(weeks=[3, 4, 5, 6]), "unexpected or repeated"),
    (lambda m: m["exports"].pop(), "exports; expected"),
    (lambda m: m["exports"][0].update(season=2025), "season"),
    (lambda m: m.update(selected_target_week=7), "target week differs"),
    (lambda m: m.update(status="failed"), "not complete"),
])
def test_manifest_is_fail_closed(tmp_path, mutate, match):
    family = weekly.FAMILIES["coverage"]
    root = _run_dir(tmp_path, family, 6, mutate=mutate)
    with pytest.raises(ValueError, match=match):
        weekly.validate_manifest(family, root, target_week=6)


def test_changed_bytes_fail_closed(tmp_path):
    family = weekly.FAMILIES["route-shape"]
    root = _run_dir(tmp_path, family, 6)
    next(root.glob("*.csv")).write_text("tampered\n")
    with pytest.raises(ValueError, match="missing or changed"):
        weekly.validate_manifest(family, root, target_week=6)


def test_append_once_is_idempotent_and_conflicts_on_a_changed_hash():
    table = weekly.FAMILIES["coverage"].tables[0]
    rows = pd.DataFrame([{"season": 2026, "target_week": 6, "normalized_name": "wide one", "pos": "WR",
                          "man_zone_source_sha256": "a", "separation_source_sha256": "b"}])
    assert len(weekly.novel_or_identical(rows, rows.iloc[0:0], table)) == 1
    assert weekly.novel_or_identical(rows, rows.copy(), table).empty
    changed = rows.copy(); changed["separation_source_sha256"] = "other"
    with pytest.raises(RuntimeError, match="conflicts"):
        weekly.novel_or_identical(rows, changed, table)


def test_completeness_guard():
    table = weekly.FAMILIES["advanced-passing"].tables[0]
    weekly.check_completeness(table, 40, None)          # first 2026 target week: nothing to compare
    weekly.check_completeness(table, 40, 45)
    with pytest.raises(ValueError, match="re-download"):
        weekly.check_completeness(table, 30, 45)
    with pytest.raises(ValueError, match="no rows"):
        weekly.check_completeness(table, 0, None)
