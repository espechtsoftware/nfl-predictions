import json
from dataclasses import asdict

import pandas as pd
import pytest

from nfl_dfs import bq
from nfl_dfs.ingest import sis_receiver_copula as history
from nfl_dfs.ingest import sis_receiver_copula_weekly as intake
from nfl_dfs.ingest.sis_pass_tail_weekly import archive_once
from nfl_dfs.ops import sis_downloads as sis

HEADER = (
    "Rank,Season,Player,Team,Week,Opp.,Pos.,Games,Cov. Snaps,Tgts,Catchable,"
    "Comp,Yds,TDs,Pass Def."
)
SIDES = (("Cardinals", "Texans", 1, "ARI"), ("Texans", "Cardinals", 2, "HOU"))


def _write_run(tmp_path, target_week=4):
    """Two synthetic W-1 artifacts (wide, slot), each one CB per side of one game."""
    week = target_week - 1
    artifacts = []
    for ordinal, (alignment, values) in enumerate(sis.RECEIVER_COPULA_ALIGNMENTS):
        path = tmp_path / sis._receiver_copula_weekly_artifact(target_week, alignment)
        lines, identities = [HEADER], []
        for side, (team, opponent, team_id, _abbr) in enumerate(SIDES):
            player = f"Corner {ordinal}{side}"
            lines.append(
                f"{side + 1},2026,{player},{team},{week},{opponent},CB,1,30,4,3,2,-1,1,1"
            )
            identities.append({
                "season": 2026, "week": week, "games": 1, "teamId": team_id,
                "team": team, "playerId": 100 + 10 * ordinal + side, "player": player,
            })
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        artifacts.append({
            "season": 2026, "week": week, "alignment": alignment,
            "artifact": path.name, "sha256": sis._sha256(path),
            "bytes": path.stat().st_size, "rows": 2,
            "headers": HEADER.split(","),
            "spec": asdict(sis.ExportSpec(
                entity="players", report="pass-defense-totals", season=2026,
                start_week=week, end_week=week, split_by_game=True,
            )),
            "submitted_scope": {
                **sis.RECEIVER_COPULA_FILTERS,
                "PassDefenseFilters.TargetLinedUp": list(values),
            },
            "identities": identities,
        })
    manifest = {
        "schema_version": 1,
        "version": sis.RECEIVER_COPULA_WEEKLY_VERSION,
        "acquisition_identity": sis._receiver_copula_weekly_identity(target_week),
        "protocol_sha256": sis.RECEIVER_COPULA_WEEKLY_PROTOCOL_SHA256,
        "retrieved_at_utc": "2026-09-30T15:00:00+00:00",
        "season": 2026, "target_week": target_week, "source_week": week,
        "api_requests_used": 2,
        "api_request_ceiling": sis.RECEIVER_COPULA_WEEKLY_API_REQUEST_CEILING,
        "artifacts": artifacts,
    }
    (tmp_path / "receiver-copula-weekly.manifest.json").write_text(json.dumps(manifest))
    result = sis.analyze_receiver_copula_weekly_acquisition(tmp_path, manifest)
    (tmp_path / "receiver-copula-weekly.result.json").write_text(json.dumps(result))
    return manifest


def _history(weeks_2026=(1, 2)):
    """Warehouse games strictly before the run: 2025 Weeks 12-18 and the given 2026 weeks."""
    rows = []
    games = [(2025, week) for week in range(12, 19)] + [(2026, week) for week in weeks_2026]
    for season, week in games:
        for alignment, _values in sis.RECEIVER_COPULA_ALIGNMENTS:
            for side, (_team, _opp, team_id, abbr) in enumerate(SIDES):
                rows.append({
                    "season": season, "week": week, "alignment": alignment,
                    "defender_player_id": 500 + side, "defender_team_id": team_id,
                    "defense": abbr, "coverage_snaps": 30.0, "targets": 4.0,
                    "completions": 2.0, "yards": 20.0, "touchdowns": 0.0,
                    "source_sha256": f"history-{season}-{week}-{alignment}",
                })
    return pd.DataFrame(rows)


def _schedule(extra=()):
    rows = []
    for week in (3, 4):
        for team, opponent in (("ARI", "HOU"), ("HOU", "ARI"), *extra):
            rows.append({"season": 2026, "week": week, "team": team, "opponent": opponent})
    return pd.DataFrame(rows)


def _warehouse(monkeypatch, *, games, schedule=None, prior=None):
    """Fake read-only BigQuery; any load or archive is recorded, never sent."""
    writes = []

    def query(sql, params=None):
        if "schedules" in sql:
            return schedule if schedule is not None else _schedule()
        if history.DEFENSE_PRIOR_TABLE in sql:
            return prior if prior is not None else pd.DataFrame()
        return games

    monkeypatch.setattr(bq, "query_df", query)
    monkeypatch.setattr(
        bq, "load_dataframe",
        lambda frame, ref, **kw: writes.append((ref, frame.copy(), kw)),
    )
    monkeypatch.setattr(
        intake, "archive_once",
        lambda root, artifacts, bucket, *, prefix: writes.append(
            ("archive", prefix, [item["artifact"] for item in artifacts])
        ) or [],
    )
    return writes


def test_weekly_protocol_carries_the_parent_prior_parameters():
    payload = json.loads(sis.RECEIVER_COPULA_WEEKLY_PROTOCOL.read_text())
    assert payload["defense_prior"]["prior_games"] == history.PRIOR_GAMES
    assert payload["defense_prior"]["minimum_prior_games"] == history.MIN_PRIOR_GAMES
    assert payload["import"]["player_keys"] == intake.PLAYER_KEYS
    assert payload["defense_prior"]["prior_keys"] == intake.PRIOR_KEYS


def test_weekly_analyzer_passes_the_two_w_minus_one_artifacts_outcome_blind(tmp_path):
    manifest = _write_run(tmp_path)
    result = sis.analyze_receiver_copula_weekly_acquisition(tmp_path, manifest)
    assert result["passes"], result["failures"]
    assert result["disposition"] == "sis-receiver-copula-weekly-acquisition-passes"
    assert (result["target_week"], result["source_week"]) == (4, 3)
    assert (result["artifact_count"], result["rows"], result["union_team_count"]) == (2, 4, 2)
    assert "numeric_totals" not in result          # rows and manifests only
    assert result["fantasy_lineup_or_contest_outcomes_read"] == []


def test_weekly_analyzer_rejects_future_weeks_the_grid_and_the_parent_protocol(tmp_path):
    manifest = _write_run(tmp_path)
    with pytest.raises(RuntimeError, match="source week"):
        sis.analyze_receiver_copula_weekly_acquisition(tmp_path, {**manifest, "source_week": 4})
    with pytest.raises(RuntimeError, match="protocol hash"):
        sis.analyze_receiver_copula_weekly_acquisition(
            tmp_path, {**manifest, "protocol_sha256": sis.RECEIVER_COPULA_PROTOCOL_SHA256})
    with pytest.raises(RuntimeError, match="identity"):
        sis.analyze_receiver_copula_weekly_acquisition(
            tmp_path, {**manifest, "acquisition_identity": sis._receiver_copula_weekly_identity(5)})
    with pytest.raises(RuntimeError, match="two W-1 artifacts"):
        sis.analyze_receiver_copula_weekly_acquisition(
            tmp_path, {**manifest, "artifacts": manifest["artifacts"][:1]})
    manifest["artifacts"][1]["submitted_scope"]["PassDefenseFilters.TargetLinedUp"] = ["2"]
    manifest["api_requests_used"] = 5
    result = sis.analyze_receiver_copula_weekly_acquisition(tmp_path, manifest)
    assert result["failures"] == [
        "2026:W03:slot:scope:PassDefenseFilters.TargetLinedUp", "request-budget:5/4",
    ]


def test_weekly_export_parses_only_week_w_minus_one(tmp_path):
    manifest = _write_run(tmp_path)
    _root, _manifest, rows = intake.read_export(tmp_path, target_week=4)
    assert len(rows) == 4 and set(rows.week) == {3} and set(rows.season) == {2026}
    assert set(rows.defense) == {"ARI", "HOU"} and rows.yards.eq(-1).all()
    assert set(rows.source_run_id) == {manifest["acquisition_identity"]}
    with pytest.raises(ValueError, match="target week differs"):
        intake.read_export(tmp_path, target_week=5)


def test_audit_only_import_computes_the_prior_and_writes_nothing(monkeypatch, tmp_path, capsys):
    _write_run(tmp_path)
    writes = _warehouse(monkeypatch, games=_history())
    audit = intake.run(tmp_path, target_week=4)
    assert writes == []
    assert audit["append_player_rows"] == 4 and audit["append_prior_rows"] == 4
    assert audit["source_week_completeness"]["complete"]
    prior = audit["prior"]
    assert prior["disposition"] == "computed" and prior["unsupported_cells"] == []
    assert (prior["source_last_season_max"], prior["source_last_week_max"]) == (2026, 3)
    assert "SIS_RECEIVER_COPULA_WEEKLY_IMPORT_JSON=" in capsys.readouterr().out


def test_write_appends_once_archives_by_hash_and_reruns_are_no_ops(monkeypatch, tmp_path):
    _write_run(tmp_path)
    writes = _warehouse(monkeypatch, games=_history())
    audit = intake.run(tmp_path, target_week=4, write=True)
    assert writes[0] == (
        "archive", "licensed/sis/receiver-copula/season=2026/week=03",
        ["2026-week03-wide-wr-cb-pass-defense-totals.csv",
         "2026-week03-slot-wr-cb-pass-defense-totals.csv"],
    )
    (player_ref, players, player_kw), (prior_ref, prior, _kw) = writes[1:]
    assert player_ref.endswith(".sis_receiver_copula_player_game")
    assert player_kw == {"write_disposition": "WRITE_APPEND"}
    assert list(players.columns) == [
        "season", "week", "alignment", "defender_player_id", "defender_team_id",
        "defender_name", "defense", "offense", "coverage_snaps", "targets",
        "completions", "yards", "touchdowns", "source_sha256", "source_run_id",
        "ingested_at",
    ]
    assert prior_ref.endswith(".sis_receiver_copula_defense_prior")
    assert set(prior.target_week) == {4} and prior.source_last_week.eq(3).all()
    assert prior.context_supported.all() and prior.source_sha256.nunique() == 1
    assert (audit["player_write_disposition"], audit["prior_write_disposition"]) == (
        "appended", "appended")

    # the identical re-run finds its own rows and appends nothing
    games = pd.concat([_history(), players[intake.GAME_COLUMNS]], ignore_index=True)
    writes = _warehouse(monkeypatch, games=games, prior=prior[[*intake.PRIOR_KEYS, "source_sha256"]])
    audit = intake.run(tmp_path, target_week=4, write=True)
    assert [entry[0] for entry in writes] == ["archive"]
    assert (audit["player_write_disposition"], audit["prior_write_disposition"]) == (
        "already-identical", "already-identical")


def test_a_different_source_hash_for_an_existing_key_fails_closed(monkeypatch, tmp_path):
    _write_run(tmp_path)
    _root, _manifest, rows = intake.read_export(tmp_path, target_week=4)
    existing = rows[intake.GAME_COLUMNS].assign(source_sha256="another-download")
    writes = _warehouse(monkeypatch, games=pd.concat([_history(), existing], ignore_index=True))
    with pytest.raises(RuntimeError, match="conflicts"):
        intake.run(tmp_path, target_week=4, write=True)
    assert writes == []


def test_the_prior_is_withheld_while_a_2026_source_week_is_missing(monkeypatch, tmp_path):
    _write_run(tmp_path)
    writes = _warehouse(monkeypatch, games=_history(weeks_2026=(2,)))
    audit = intake.run(tmp_path, target_week=4, write=True)
    assert audit["prior"] == {"disposition": "withheld", "missing_2026_source_weeks": [1]}
    assert audit["player_write_disposition"] == "appended"
    assert audit["prior_write_disposition"] == "withheld"
    assert [entry[0] for entry in writes][-1].endswith(".sis_receiver_copula_player_game")


def test_defenses_under_four_prior_games_are_recorded_not_failed():
    games = _history(weeks_2026=(1, 2, 3))
    games = games[games.season.eq(2026)]                     # three games per defense
    prior, audit = intake.defense_prior(games, _schedule(), target_week=4, run_id="run")
    assert not prior.context_supported.any() and audit["supported_rows"] == 0
    assert audit["unsupported_cells"] == [
        "ARI:wide:3", "ARI:slot:3", "HOU:wide:3", "HOU:slot:3",
    ]


def test_an_incomplete_source_week_is_recorded_and_never_appended(monkeypatch, tmp_path):
    _write_run(tmp_path)
    schedule = _schedule(extra=(("BUF", "MIA"), ("MIA", "BUF")))
    writes = _warehouse(monkeypatch, games=_history(), schedule=schedule)
    audit = intake.run(tmp_path, target_week=4)
    assert audit["source_week_completeness"] == {
        "complete": False, "scheduled_defenses": 4,
        "missing_defenses": ["BUF", "MIA"], "unscheduled_pairs": [],
    }
    with pytest.raises(RuntimeError, match="incomplete"):
        intake.run(tmp_path, target_week=4, write=True)
    assert writes == []


def test_archive_once_creates_hash_addressed_objects_and_verifies_reruns(monkeypatch, tmp_path):
    from google.api_core.exceptions import PreconditionFailed
    from google.cloud import storage

    manifest = _write_run(tmp_path)
    stored = {}

    class Blob:
        def __init__(self, name):
            self.name = name

        def upload_from_filename(self, path, content_type, if_generation_match):
            assert if_generation_match == 0 and content_type == "text/csv"
            if self.name in stored:
                raise PreconditionFailed("exists")
            stored[self.name] = open(path, "rb").read()

        def download_as_bytes(self):
            return stored[self.name]

    class Client:
        def bucket(self, name):
            return type("Bucket", (), {"blob": lambda _self, object_name: Blob(object_name)})()

    monkeypatch.setattr(storage, "Client", Client)
    prefix = "licensed/sis/receiver-copula/season=2026/week=03"
    first = archive_once(tmp_path, manifest["artifacts"], "bucket", prefix=prefix)
    item = manifest["artifacts"][0]
    assert first[0] == {
        "artifact": item["artifact"], "disposition": "created",
        "uri": f"gs://bucket/{prefix}/sha256={item['sha256']}/{item['artifact']}",
    }
    again = archive_once(tmp_path, manifest["artifacts"], "bucket", prefix=prefix)
    assert {entry["disposition"] for entry in again} == {"already-identical"}
    stored[next(iter(stored))] = b"tampered"
    with pytest.raises(RuntimeError, match="archive differs"):
        archive_once(tmp_path, manifest["artifacts"], "bucket", prefix=prefix)
