"""Seal builder for schema-1 live-matchup runs: latest valid pre-kickoff member per report, archive re-read."""
import hashlib
import json

import pandas as pd
import pytest

from nfl_dfs.ops import fantasy_points_matchup_seal as seal_mod

KICKOFF = pd.Timestamp("2026-09-18T00:15:00+00:00")
PAIRS = {("BUF", "MIA"), ("MIA", "BUF")}


def _run(root, stamp, records, *, kickoff=KICKOFF, pairs=PAIRS, schema=1):
    run_dir = root / f"{stamp}__{seal_mod.CAPTURE_ID}__week-02"
    run_dir.mkdir(parents=True)
    reports = []
    for key, retrieved, passes, archived, body in records:
        path = run_dir / f"{key}.csv"
        path.write_text(body)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reports.append({
            "key": key, "status": "captured", "retrieved_at_utc": retrieved,
            "source_url": f"https://data.fantasypoints.com/nfl/tools/player/{key}", "path": path.name,
            "bytes": path.stat().st_size, "source_rows": 2, "source_seasons": [2026], "source_regime": "active",
            "sha256": digest, "schedule_gate": {"passes": passes, "observed_pairs": 2},
            **({"archive_uri": f"gs://bucket/week=02/sha256={digest}/{key}.csv"} if archived else {}),
        })
    (run_dir / "manifest.json").write_text(json.dumps({
        "schema_version": schema, "capture_id": seal_mod.CAPTURE_ID, "target_season": 2026, "target_week": 2,
        "first_kickoff_utc": kickoff.isoformat(), "expected_schedule_pairs": [list(p) for p in sorted(pairs)],
        "reports": reports}))
    return run_dir


def _lookup(uri):
    return uri.split("sha256=")[1].split("/")[0], "1758130000000000"


def test_latest_valid_pre_kickoff_member_per_report(tmp_path):
    early, late, after = "2026-09-17T10:00:00+00:00", "2026-09-17T17:30:00+00:00", "2026-09-18T01:00:00+00:00"
    _run(tmp_path, "20260917T100000Z", [(k, early, True, True, f"{k} early") for k in seal_mod.REPORTS])
    _run(tmp_path, "20260917T172902Z", [
        ("line-matchups", late, True, True, "line late"),
        ("qb-coverage-matchup", late, False, False, "qb gate failed"),       # gate failed: never admitted
        ("wr-coverage-matchup", late, True, False, "wr not archived"),       # not archived: never admitted
    ])
    _run(tmp_path, "20260918T010000Z", [(k, after, True, True, f"{k} after") for k in seal_mod.REPORTS])
    seal = seal_mod.build_seal(tmp_path, week=2, kickoff=KICKOFF, expected=PAIRS, archive_lookup=_lookup)
    chosen = {m["report"]: m["source_run_id"][:16] for m in seal["members"]}
    assert chosen == {"line-matchups": "20260917T172902Z", "qb-coverage-matchup": "20260917T100000Z",
                      "wr-coverage-matchup": "20260917T100000Z"}
    assert all(m["archive_generation"] == "1758130000000000" for m in seal["members"])
    reasons = " | ".join(seal["excluded_records"])
    assert "schedule gate failed" in reasons and "not archived" in reasons and "after first kickoff" in reasons
    assert seal["status"] == seal_mod.SEAL_STATUS and seal["integrity"]["all_members_source_regime_identical"]


def test_changed_file_and_foreign_schedule_are_excluded(tmp_path):
    good = "2026-09-17T12:00:00+00:00"
    run = _run(tmp_path, "20260917T120000Z", [(k, good, True, True, k) for k in seal_mod.REPORTS])
    (run / "line-matchups.csv").write_text("tampered")
    _run(tmp_path, "20260917T130000Z", [(k, good, True, True, k) for k in seal_mod.REPORTS],
         pairs={("NE", "NYJ"), ("NYJ", "NE")})
    with pytest.raises(ValueError, match=r"no valid pre-kickoff capture for \['line-matchups'\]"):
        seal_mod.build_seal(tmp_path, week=2, kickoff=KICKOFF, expected=PAIRS, archive_lookup=_lookup)


def test_archive_bytes_must_match_the_captured_file(tmp_path):
    _run(tmp_path, "20260917T120000Z", [(k, "2026-09-17T12:00:00+00:00", True, True, k) for k in seal_mod.REPORTS])
    with pytest.raises(ValueError, match="bytes differ"):
        seal_mod.build_seal(tmp_path, week=2, kickoff=KICKOFF, expected=PAIRS,
                            archive_lookup=lambda uri: ("0" * 64, "1"))


def test_schema_2_runs_are_left_to_the_run_dir_path(tmp_path):
    _run(tmp_path, "20260917T120000Z", [(k, "2026-09-17T12:00:00+00:00", True, True, k) for k in seal_mod.REPORTS],
         schema=2)
    found, excluded = seal_mod.candidates(tmp_path, week=2, kickoff=KICKOFF, expected=PAIRS)
    assert not any(found.values()) and "schema 2" in excluded[0]


def test_the_staging_loader_accepts_the_built_seal(tmp_path):
    """End to end: vendor-shaped schema-1 files -> build_seal -> the loader's own validate_seal re-derives them."""
    import os

    from nfl_dfs.ingest import fantasy_points_matchups_weekly as loader
    from nfl_dfs.ops import fantasy_points_matchups as matchups
    from tests.fp_matchup_fixtures import _write_grouped, directional_pairs, export_rows_for, schedule_frame

    schedule = schedule_frame()
    kickoff, expected = matchups.first_kickoff_utc(schedule), matchups.expected_schedule_pairs(schedule)
    retrieved = kickoff - pd.Timedelta(days=2)
    run_dir = tmp_path / f"20260917T172902Z__{seal_mod.CAPTURE_ID}__week-02"
    run_dir.mkdir()
    reports = []
    for key in seal_mod.REPORTS:
        path = run_dir / f"{key}.csv"
        _write_grouped(path, key, export_rows_for(key, directional_pairs(schedule)))
        os.utime(path, (retrieved.timestamp(), retrieved.timestamp()))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reports.append({"key": key, "retrieved_at_utc": retrieved.isoformat(), "path": path.name,
                        "bytes": path.stat().st_size, "sha256": digest, "source_regime": "active",
                        "schedule_gate": {"passes": True, "observed_pairs": len(expected)},
                        "archive_uri": loader.expected_archive_uri(digest, path.name, 2)})
    (run_dir / "manifest.json").write_text(json.dumps({
        "schema_version": 1, "capture_id": seal_mod.CAPTURE_ID, "target_season": 2026, "target_week": 2,
        "first_kickoff_utc": kickoff.isoformat(), "expected_schedule_pairs": [list(p) for p in sorted(expected)],
        "reports": reports}))
    seal = seal_mod.build_seal(tmp_path, week=2, kickoff=kickoff, expected=expected,
                               archive_lookup=lambda uri: (uri.split("sha256=")[1].split("/")[0], "7"))
    seal_path = tmp_path / "seal.json"
    seal_path.write_text(json.dumps(seal))
    capture, artifacts = loader.validate_seal(seal_path, target_week=2, output_root=tmp_path,
                                              kickoff=kickoff, expected=expected)
    assert set(artifacts) == set(seal_mod.REPORTS) and capture["input_kind"] == "seal"
