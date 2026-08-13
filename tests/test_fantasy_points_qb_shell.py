import hashlib
import json

import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_qb_shell as diagnostic
from nfl_dfs.ingest import fantasy_points_qb_shell as shell_import


def _shell(team, **overrides):
    row = {
        "season": 2025,
        "target_week": 9,
        "source_week_start": 5,
        "source_week_end": 8,
        "team": team,
        "offense_source_run_id": "run__same-season-qb-shell-fit-last-four-v1",
        "defense_source_run_id": "run__same-season-coverage-last-four-v1",
        "off_dropbacks": 100,
        "def_dropbacks": 100,
    }
    for side in ("off", "def"):
        row.update({
            f"{side}_man_rate": 0.25,
            f"{side}_man_fpdb": 0.60 if side == "off" else 0.30,
            f"{side}_zone_rate": 0.75,
            f"{side}_zone_fpdb": 0.20 if side == "off" else 0.30,
            f"{side}_one_high_rate": 0.40,
            f"{side}_one_high_fpdb": 0.50 if side == "off" else 0.30,
            f"{side}_two_high_rate": 0.60,
            f"{side}_two_high_fpdb": 0.25 if side == "off" else 0.30,
        })
    row.update(overrides)
    return row


def test_qb_shell_fit_is_team_opponent_specific_and_strictly_prior():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "team": "ARI", "opp": "NO", "pos": "QB",
    }])
    offense = _shell("ARI")
    defense = _shell(
        "NO", def_man_rate=0.75, def_zone_rate=0.25,
        def_one_high_rate=0.80, def_two_high_rate=0.20)
    row = diagnostic.attach_qb_shell_fit(
        targets, pd.DataFrame([offense, defense])).iloc[0]
    assert row.fp_qb_shell_supported
    assert row.fp_qb_shell_mz_grade == pytest.approx(2 / 3)
    assert row.fp_qb_shell_mof_grade == pytest.approx(2 / 7)
    assert row.source_team == "ARI"
    assert row.source_opp == "NO"


def test_qb_shell_fit_rejects_same_week_source():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "team": "ARI", "opp": "NO", "pos": "QB",
    }])
    with pytest.raises(ValueError, match="PIT/team/opponent"):
        diagnostic.attach_qb_shell_fit(
            targets,
            pd.DataFrame([_shell("ARI", source_week_end=9), _shell("NO")]),
        )


def test_qb_shell_gate_is_aggregate_tail_first():
    aggregate = {"control_brier_30": 0.04, "treatment_brier_30": 0.039}
    coverage = {2023: 0.70, 2024: 0.80, 2025: 0.75}
    assert diagnostic.shell_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.69
    assert not diagnostic.shell_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.80
    aggregate["treatment_brier_30"] = 0.041
    assert not diagnostic.shell_gate(aggregate, coverage)["passes"]


def test_qb_shell_manifest_requires_complete_strict_prior_grid(tmp_path):
    payload = b"a,b\n1,2\n"
    digest = hashlib.sha256(payload).hexdigest()
    exports = []
    for season in shell_import.SEASONS:
        for target_week in shell_import.TARGET_WEEKS:
            name = f"coverage-matrix-{season}-{target_week}.csv"
            (tmp_path / name).write_bytes(payload)
            exports.append({
                "status": "downloaded",
                "report": "coverage-matrix",
                "season": season,
                "weeks": list(range(target_week - 4, target_week)),
                "include_group_headers": True,
                "context": "Offense",
                "target_week": target_week,
                "path": name,
                "bytes": len(payload),
                "csv_rows_including_headers": 2,
                "max_csv_columns": 2,
                "sha256": digest,
            })
    manifest = {
        "schema_version": 1,
        "run_id": "run__same-season-qb-shell-fit-last-four-v1",
        "exports": exports,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    _, keyed = shell_import.validate_manifest(tmp_path)
    assert len(keyed) == 56
    exports[0]["context"] = "Defense"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="wrong report context"):
        shell_import.validate_manifest(tmp_path)
