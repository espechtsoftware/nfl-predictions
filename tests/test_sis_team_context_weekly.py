import pandas as pd
import pytest
from nfl_dfs.ingest.sis_team_context_weekly import KEY, coverage, plan_append


def _frame():
    return pd.DataFrame({
        "season": [2026] * 4, "week": [1, 1, 2, 2], "team": ["DET", "NO", "BUF", "DET"], "opp": ["NO", "DET", "DET", "BUF"],
        "game_key": ["2026-01-DET-NO", "2026-01-DET-NO", "2026-02-BUF-DET", "2026-02-BUF-DET"], "x": [1.0, 2.0, 3.0, 4.0],
    })


def test_plan_append_skips_existing_team_weeks_and_names_them():
    to_append, skipped = plan_append(_frame(), {(2026, 1, "DET"), (2026, 1, "NO")})
    assert to_append.week.tolist() == [2, 2] and skipped == [(2026, 1, "DET"), (2026, 1, "NO")]
    to_append, skipped = plan_append(_frame(), set())
    assert len(to_append) == 4 and skipped == []


def test_coverage_reports_partial_weeks():
    f = _frame().iloc[:3]                      # Week 2 has only one side of BUF-DET (SIS charting still posting)
    c = coverage(f)
    assert c["2026-01"] == {"rows": 2, "games": 1, "games_with_both_sides": 1, "games_one_side": 0}
    assert c["2026-02"] == {"rows": 1, "games": 1, "games_with_both_sides": 0, "games_one_side": 1}
    assert KEY == ("season", "week", "team")


def _synthetic_run(tmp_path):
    """The tracked Week-3 plan's eleven artifacts as synthetic bytes, each with its own manifest (no vendor data)."""
    import hashlib
    import json
    from pathlib import Path

    from nfl_dfs.ingest import sis_team_context_weekly as weekly
    from nfl_dfs.ops.sis_downloads import artifact_name, load_plan

    plan = Path(__file__).resolve().parents[1] / "automation" / "sis" / "plans" / "team-context-2026-w03.json"
    specs = load_plan(plan)
    for spec in specs:
        path = tmp_path / artifact_name(spec)
        path.write_text(f"synthetic,{spec.report}\n1,2\n")
        manifest = {"artifact": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        path.with_suffix(".manifest.json").write_text(json.dumps(manifest))
    return weekly, plan, specs


class _Bucket:
    def __init__(self, store):
        self.store = store

    def blob(self, name):
        from google.api_core.exceptions import PreconditionFailed
        store = self.store

        class Blob:
            def upload_from_filename(self, filename, content_type, if_generation_match):
                assert content_type == "text/csv" and if_generation_match == 0
                if name in store:
                    raise PreconditionFailed("exists")
                store[name] = open(filename, "rb").read()

            def download_as_bytes(self):
                return store[name]

        return Blob()


class _Client:
    def __init__(self, store):
        self.store = store

    def bucket(self, _name):
        return _Bucket(self.store)


def _fake_gcs(monkeypatch, store):
    from google.cloud import storage

    monkeypatch.setattr(storage, "Client", lambda *a, **k: _Client(store))


def test_team_context_csvs_are_archived_by_content_hash_once(tmp_path, monkeypatch):
    """Production's order C (2026-09-28): every planned CSV reaches GCS under the pass-tail's hash-addressed pattern."""
    weekly, plan, specs = _synthetic_run(tmp_path)
    store = {}
    _fake_gcs(monkeypatch, store)
    first = weekly.archive(tmp_path, specs, "bucket")
    assert len(first) == len(store) == 11 and {item["disposition"] for item in first} == {"created"}
    name = next(iter(store))
    assert name.startswith("licensed/sis/team-context/season=2026/source_weeks=03-03/sha256=") and name.endswith(".csv")
    assert {item["disposition"] for item in weekly.archive(tmp_path, specs, "bucket")} == {"already-identical"}
    store[name] = b"different bytes"
    with pytest.raises(RuntimeError, match="archive differs"):
        weekly.archive(tmp_path, specs, "bucket")


def test_a_changed_artifact_is_never_archived(tmp_path, monkeypatch):
    weekly, plan, specs = _synthetic_run(tmp_path)
    store = {}
    _fake_gcs(monkeypatch, store)
    from nfl_dfs.ops.sis_downloads import artifact_name

    (tmp_path / artifact_name(specs[0])).write_text("tampered\n")
    with pytest.raises(ValueError, match="differs from its manifest"):
        weekly.archive(tmp_path, specs, "bucket")
    assert store == {}


def test_only_a_write_run_archives(tmp_path, monkeypatch):
    weekly, plan, specs = _synthetic_run(tmp_path)
    calls = []
    monkeypatch.setattr(weekly, "archive", lambda root, planned, bucket: calls.append(len(planned)) or ["ok"])
    monkeypatch.setattr(weekly, "_merge_family", lambda *a, **k: None)      # no warehouse access in this test
    assert "archive" not in weekly.run(tmp_path, plan, write=False)
    assert weekly.run(tmp_path, plan, write=True)["archive"] == ["ok"] and calls == [11]
