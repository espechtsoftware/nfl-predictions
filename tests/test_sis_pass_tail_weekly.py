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


def test_week5_backfill_accepts_team_context_rows_identical_by_content():
    """O-3: W1-3 were first loaded by the weekly team-context pull (other files, other
    hashes). The Week-5 re-fetch of the same values is identical by CONTENT."""
    keys = ["season", "week", "team"]
    hashes = ["source_sha256_pass_defense_totals"]
    content = ["pdef_attempts", "pdef_boom_rate", "team_id"]
    rows = pd.DataFrame([
        {"season": 2026, "week": 1, "team": "ARI", "pdef_attempts": 31.0,
         "pdef_boom_rate": 0.125, "team_id": 1,
         "source_sha256_pass_defense_totals": "pass-tail-file"},
        {"season": 2026, "week": 4, "team": "ARI", "pdef_attempts": 28.0,
         "pdef_boom_rate": 0.2, "team_id": 1,
         "source_sha256_pass_defense_totals": "pass-tail-file"},
    ])
    existing = rows.iloc[[0]].copy()
    existing["source_sha256_pass_defense_totals"] = "team-context-file"
    existing["pdef_attempts"] = 31  # INT64 in the warehouse, float in the CSV parse
    audit: dict = {}
    novel = intake._novel_or_identical(
        rows, existing, keys=keys, hash_columns=hashes,
        content_columns=content, audit=audit)
    assert novel[keys].to_dict("records") == [{"season": 2026, "week": 4, "team": "ARI"}]
    assert audit == {"content_identical_rows": 1, "differing_columns": {}, "revisions": []}
    # A vendor revision of any value still fails closed, naming the column.
    revised = existing.copy()
    revised["pdef_boom_rate"] = 0.126
    with pytest.raises(RuntimeError, match="pdef_boom_rate"):
        intake._novel_or_identical(
            rows, revised, keys=keys, hash_columns=hashes, content_columns=content)
    # NULL on one side only is a difference, NULL on both is not.
    one_null = existing.copy()
    one_null["pdef_boom_rate"] = None
    with pytest.raises(RuntimeError, match="conflicts"):
        intake._novel_or_identical(
            rows, one_null, keys=keys, hash_columns=hashes, content_columns=content)
    both_null_rows = rows.copy()
    both_null_rows.loc[0, "pdef_boom_rate"] = None
    assert len(intake._novel_or_identical(
        both_null_rows, one_null, keys=keys, hash_columns=hashes,
        content_columns=content)) == 1


def test_run_compares_team_context_by_content(monkeypatch, tmp_path):
    """run() asks the warehouse for the content columns and reports the identity."""
    context = pd.DataFrame([{
        "season": 2026, "week": 1, "team": "ARI", "pdef_attempts": 31.0,
        "source_sha256_pass_defense_totals": "a",
        "source_sha256_pass_defense_value": "b",
        "source_sha256_pass_rush_totals": "c",
        "source_run_id": "new", "team_name": "Cardinals",
    }])
    attempts = pd.DataFrame([{
        "season": 2026, "week": 1, "defense": "ARI", "alignment": "wide",
        "source_sha256": "w", "attempts": 10, "offense": "LA", "team_id": 1,
    }])
    manifest = {"source_week_start": 1, "source_week_end": 4,
                "acquisition_identity": "id"}
    monkeypatch.setattr(intake, "_load_manifest", lambda d, target_week: (tmp_path, manifest))
    monkeypatch.setattr(intake, "_read_team_context", lambda root, m: context)
    monkeypatch.setattr(intake, "_read_alignment_attempts", lambda root, m: attempts)
    seen = []

    def query_df(sql, params=None):
        seen.append(sql)
        if "sis_team_context_game" in sql:
            old = context.copy()
            old["source_sha256_pass_defense_totals"] = "old-file"
            return old.drop(columns=["source_run_id"])
        return pd.DataFrame(columns=["season", "week", "defense", "alignment",
                                     "source_sha256", "offense", "team_id", "attempts"])

    from nfl_dfs import bq
    monkeypatch.setattr(bq, "query_df", query_df)
    audit = intake.run(tmp_path, target_week=5, write=False)
    assert "pdef_attempts" in seen[0] and "team_name" in seen[0]
    assert "source_run_id" not in audit["context_content_columns"]
    assert audit["append_context_rows"] == 0
    assert audit["context_rows_identical_by_content"] == 1


def test_vendor_revision_keeps_first_seen_and_is_reported():
    """Reviewer ruling (d): first seen wins, never fail-closed, every value logged."""
    keys = ["season", "week", "team"]
    rows = pd.DataFrame([
        {"season": 2026, "week": 1, "team": "ARI", "pdef_boom_rate": 0.126,
         "pdef_attempts": 31, "h": "new"},
        {"season": 2026, "week": 4, "team": "ARI", "pdef_boom_rate": 0.2,
         "pdef_attempts": 28, "h": "new"},
    ])
    existing = rows.iloc[[0]].assign(pdef_boom_rate=0.125, h="old")
    audit: dict = {}
    novel = intake._novel_or_identical(
        rows, existing, keys=keys, hash_columns=["h"],
        content_columns=["pdef_boom_rate", "pdef_attempts"], audit=audit,
        keep_first_seen=True)
    # The revised W1 row is NOT appended (the first-seen row stays); W4 is new.
    assert novel.week.tolist() == [4]
    assert audit["revisions"] == [{
        "season": 2026, "week": 1, "team": "ARI", "column": "pdef_boom_rate",
        "first_seen_value": "0.125", "refetched_value": "0.126"}]


def test_run_logs_revisions_and_appends_only_new_keys(monkeypatch, tmp_path):
    context = pd.DataFrame([
        {"season": 2026, "week": w, "team": "ARI", "pdef_attempts": 31.0 + w,
         "source_sha256_pass_defense_totals": "a",
         "source_sha256_pass_defense_value": "b",
         "source_sha256_pass_rush_totals": "c", "source_run_id": "new"}
        for w in (1, 4)])
    attempts = pd.DataFrame([{
        "season": 2026, "week": 1, "defense": "ARI", "alignment": "wide",
        "source_sha256": "w", "attempts": 10, "offense": "LA", "team_id": 1}])
    manifest = {"source_week_start": 1, "source_week_end": 4,
                "acquisition_identity": "refetch-run"}
    monkeypatch.setattr(intake, "_load_manifest", lambda d, target_week: (tmp_path, manifest))
    monkeypatch.setattr(intake, "_read_team_context", lambda root, m: context)
    monkeypatch.setattr(intake, "_read_alignment_attempts", lambda root, m: attempts)
    monkeypatch.setattr(intake, "_archive", lambda root, m, bucket: [])

    def query_df(sql, params=None):
        if "sis_team_context_game" in sql:
            old = context.iloc[[0]].copy()
            old["pdef_attempts"] = 30.0          # a revised first-seen W1 value
            old["source_sha256_pass_defense_totals"] = "team-context-file"
            return old.drop(columns=["source_run_id"])
        return attempts.assign(attempts=9, source_sha256="old")  # revised attempts

    loads = []
    from nfl_dfs import bq
    monkeypatch.setattr(bq, "query_df", query_df)
    monkeypatch.setattr(bq, "load_dataframe",
                        lambda frame, table, write_disposition: loads.append((table, frame)))
    audit = intake.run(tmp_path, target_week=5, write=True)
    assert audit["append_context_rows"] == 1 and audit["append_attempt_rows"] == 0
    assert audit["deficiency_row_required"] is True and audit["first_seen_kept"] is True
    tables = [t for t, _ in loads]
    assert any(t.endswith(".sis_vendor_revision_log") for t in tables)
    log = next(f for t, f in loads if t.endswith(".sis_vendor_revision_log"))
    assert sorted(log.column_name) == ["attempts", "pdef_attempts"]
    appended = next(f for t, f in loads if t.endswith(".sis_team_context_game"))
    assert appended.week.tolist() == [4]
