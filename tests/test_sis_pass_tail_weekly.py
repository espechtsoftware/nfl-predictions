import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.ingest import sis_pass_tail_weekly as intake
from nfl_dfs.ingest.sis_team_context import SCHEMAS
from nfl_dfs.ops import sis_downloads as sis


def _row(header, team, opponent, rank):
    values = []
    for column in header:
        if column == "Rank":
            values.append(rank)
        elif column in {"Season", "Year"}:
            values.append(2026)
        elif column == "Team":
            values.append(team)
        elif column == "Week":
            values.append(1)
        elif column == "Opp.":
            values.append(opponent)
        elif column == "Games":
            values.append(1)
        elif column in {"Boom%", "Bust%", "Positive%"}:
            values.append("10%")
        else:
            values.append(10)
    return values


def _write_run(tmp_path):
    artifacts = []
    views = (
        ("pass-defense-totals", "all"),
        ("pass-defense-value", "all"),
        ("pass-rush-totals", "all"),
        ("pass-defense-totals", "wide"),
        ("pass-defense-totals", "slot"),
    )
    identities = [
        {"season": 2026, "week": 1, "games": 1, "teamId": 1,
         "team": "Cardinals", "opp": "Texans"},
        {"season": 2026, "week": 1, "games": 1, "teamId": 2,
         "team": "Texans", "opp": "Cardinals"},
    ]
    for report, slice_name in views:
        name = sis._pass_tail_weekly_artifact(5, 1, 4, report, slice_name)
        path = tmp_path / name
        header = SCHEMAS[report][0]
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerow(_row(header, "Cardinals", "Texans", 1))
            writer.writerow(_row(header, "Texans", "Cardinals", 2))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        filters = {}
        submitted = {}
        if slice_name in {"wide", "slot"}:
            filters = {
                "PassDefenseFilters.TargetLinedUp": list(
                    dict(sis.ASOE_ALIGNMENTS)[slice_name]
                ),
                "PassDefenseFilters.Schemes": list(sis.ASOE_ALL_SCHEMES),
                "PassDefenseFilters.ReceiverPos": ["4"],
                "PassDefenseFilters.MinTargets": ["0"],
                "PassDefenseFilters.MinAttempts": ["1"],
            }
            submitted = dict(filters)
        item = {
            "report": report,
            "slice": slice_name,
            "artifact": name,
            "sha256": digest,
            "bytes": path.stat().st_size,
            "rows": 2,
            "headers": list(header),
            "spec": asdict(sis.ExportSpec(
                entity="teams", report=report, season=2026,
                start_week=1, end_week=4, split_by_game=True,
            )),
            "filters": filters,
            "submitted_scope": submitted,
            "identities": identities,
        }
        artifacts.append(item)
        path.with_suffix(".manifest.json").write_text(json.dumps(item))
    protocol = (
        Path(__file__).resolve().parents[1]
        / "reports/2026-08-15-prospective-sis-pass-tail-finite-k-protocol.md"
    )
    protocol_hash = sis._sha256(protocol)
    identity = hashlib.sha256(
        (
            protocol_hash + f"|{sis.PASS_TAIL_WEEKLY_VERSION}|2026|5|1|4"
        ).encode()
    ).hexdigest()
    manifest = {
        "schema_version": 1,
        "version": sis.PASS_TAIL_WEEKLY_VERSION,
        "acquisition_identity": identity,
        "protocol_sha256": protocol_hash,
        "retrieved_at_utc": "2026-09-30T15:00:00+00:00",
        "season": 2026,
        "target_week": 5,
        "source_week_start": 1,
        "source_week_end": 4,
        "api_requests_used": 5,
        "api_request_ceiling": sis.PASS_TAIL_WEEKLY_API_REQUEST_CEILING,
        "artifacts": artifacts,
    }
    (tmp_path / "pass-tail-weekly.manifest.json").write_text(
        json.dumps(manifest)
    )
    result = sis._analyze_pass_tail_weekly_manifest(tmp_path, manifest)
    (tmp_path / "pass-tail-weekly.result.json").write_text(json.dumps(result))
    return manifest


def test_weekly_sis_intake_reproduces_context_and_attempts(tmp_path):
    _write_run(tmp_path)
    context, attempts, audit = intake.read_exports(tmp_path, target_week=5)
    assert audit["source_week_end"] == 4
    assert len(context) == 2
    assert set(context.team) == {"ARI", "HOU"}
    assert context.pdef_boom_rate.eq(0.1).all()
    assert context.prush_pressures.eq(10).all()
    assert len(attempts) == 4
    assert set(attempts.alignment) == {"wide", "slot"}
    assert attempts.week.lt(5).all()


def test_weekly_sis_manifest_rejects_a_future_source_window(tmp_path):
    manifest = _write_run(tmp_path)
    manifest["source_week_end"] = 5
    with pytest.raises(RuntimeError, match="source window"):
        sis._analyze_pass_tail_weekly_manifest(tmp_path, manifest)


def test_weekly_sis_append_rejects_changed_provenance():
    rows = pd.DataFrame([{
        "season": 2026, "week": 1, "team": "ARI",
        "source_sha256_pass_defense_totals": "one",
    }])
    existing = rows.copy()
    assert intake._novel_or_identical(
        rows, existing, keys=["season", "week", "team"],
        hash_columns=["source_sha256_pass_defense_totals"],
    ).empty
    existing["source_sha256_pass_defense_totals"] = "two"
    with pytest.raises(RuntimeError, match="conflicts"):
        intake._novel_or_identical(
            rows, existing, keys=["season", "week", "team"],
            hash_columns=["source_sha256_pass_defense_totals"],
        )
