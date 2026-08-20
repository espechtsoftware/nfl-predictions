from __future__ import annotations

import copy
from datetime import datetime, timezone
from hashlib import sha256
import itertools
from pathlib import Path
import sys

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_b1_authoritative_settlement as settlement  # noqa: E402


CODE_SHA = "a" * 40
MODEL_SHA = "b" * 64
LOCK = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)
FROZEN = datetime(2026, 9, 13, 16, 0, tzinfo=timezone.utc)
ATTEMPTED = datetime(2026, 9, 13, 18, 0, tzinfo=timezone.utc)
CAPTURED = datetime(2026, 9, 13, 18, 2, tzinfo=timezone.utc)
IMAGE = settlement.transport.IMAGE_REPOSITORY + "@sha256:" + "c" * 64
SNAPSHOT_ID = "2026w01-sunday-main-early"
PANELS = ["canonical", "companion"]
CANONICAL = "canonical"
PANEL_SNAPSHOT = datetime(2026, 9, 13, 15, 50, tzinfo=timezone.utc)
PANEL_CREATED = datetime(2026, 9, 13, 15, 55, tzinfo=timezone.utc)


def _rosters() -> list[str]:
    ids = [str(index) for index in range(1, 13)]
    return [
        ",".join(sorted(values))
        for values in itertools.islice(itertools.combinations(ids, 9), 80)
    ]


def _deployment() -> dict:
    return {
        "code": {"commit_sha": CODE_SHA, "image": IMAGE},
        "historical_license": {"model_artifact_sha256": MODEL_SHA},
    }


def _panel_receipt() -> dict:
    mapping = _mapping_frame().loc[:, settlement.panel_producer.PLAYER_COLUMNS]
    return {
        "season": 2026,
        "week": 1,
        "snapshot_id": SNAPSHOT_ID,
        "snapshot_at": PANEL_SNAPSHOT.isoformat(),
        "lock_at": LOCK.isoformat(),
        "code_sha": CODE_SHA,
        "model_artifact_sha256": MODEL_SHA,
        "panels": PANELS,
        "canonical_panel": CANONICAL,
        "validation": {
            "candidate_rows": 500,
            "deduplicated_rosters": 100,
            "player_rows": len(mapping),
            "player_frame_sha256": settlement.panel_producer._frame_sha(
                mapping, ("panel_run_id", "season", "week", "id")
            ),
            "panel_rows": {
                "canonical": {
                    "slate_run_id": "slate-canonical",
                    "config_hash": "d" * 64,
                },
                "companion": {
                    "slate_run_id": "slate-companion",
                    "config_hash": "e" * 64,
                },
            },
        },
    }


def _panel_object(panel: dict | None = None) -> tuple[dict, bytes]:
    panel = _panel_receipt() if panel is None else panel
    raw = settlement._canonical_json(panel)
    uri = settlement.panel_producer.canonical_receipt_uri(
        season=2026, week=1, snapshot_id=SNAPSHOT_ID
    )
    return ({
        **_identity(uri, raw, "33"),
        "created_at": PANEL_CREATED.isoformat(),
        "create_only": True,
    }, raw)


def _receipt(*, panel: dict | None = None) -> dict:
    rosters = _rosters()
    panel_object, _ = _panel_object(panel)
    return {
        "version": "b1-corpus-tail-shadow-receipt-v1",
        "policy_version": settlement.science.POLICY_VERSION,
        "season": 2026,
        "week": 1,
        "model_artifact_sha256": MODEL_SHA,
        "source_identity": {
            "snapshot_id": SNAPSHOT_ID,
            "snapshot_at": "2026-09-13T16:00:00+00:00",
            "lock_at": LOCK.isoformat(),
            "panels": PANELS,
            "canonical_panel": CANONICAL,
            "candidate_rows": 500,
            "deduplicated_rosters": 100,
            "candidate_frame_sha256": "e" * 64,
            "player_frame_sha256": "f" * 64,
            "candidate_query": {
                "job_id": "candidate-job",
                "location": "US",
                "created": "2026-09-13T15:58:00+00:00",
                "started": "2026-09-13T15:58:01+00:00",
                "ended": "2026-09-13T15:59:00+00:00",
                "total_bytes_processed": 1,
                "query_sha256": "1" * 64,
            },
            "player_query": {
                "job_id": "player-job",
                "location": "US",
                "created": "2026-09-13T15:59:01+00:00",
                "started": "2026-09-13T15:59:02+00:00",
                "ended": "2026-09-13T16:00:00+00:00",
                "total_bytes_processed": 1,
                "query_sha256": "2" * 64,
            },
            "realized_outcome_columns_read": [],
            "panel_source_receipt_object": panel_object,
        },
        "candidate_budget_control": 100,
        "candidate_budget_challenger": 100,
        "entry_budget": 80,
        "redundancy": {},
        "control_entries": [
            {"rank": rank, "roster_key": roster}
            for rank, roster in enumerate(rosters)
        ],
        "challenger_entries": [
            {
                "rank": rank,
                "roster_key": roster,
                "prelock_tail_score": 0.5,
            }
            for rank, roster in enumerate(reversed(rosters))
        ],
        "uses_realized_outcomes": False,
        "uses_winner_target_or_feature": False,
        "production_licensed": False,
        "prospective_adoption_gate_required": True,
    }


def _mapping_frame() -> pd.DataFrame:
    rows = []
    ids = sorted({item for roster in _rosters() for item in roster.split(",")})
    for panel in PANELS:
        for player_id in ids:
            is_dst = player_id == "12"
            in_union = panel == CANONICAL
            rows.append({
                "generated_at": FROZEN,
                "panel_run_id": panel,
                "slate_run_id": f"slate-{panel}",
                "code_sha": CODE_SHA,
                "config_hash": ("d" if panel == CANONICAL else "e") * 64,
                "research_eligible": False,
                "season": 2026,
                "week": 1,
                "id": player_id,
                "pos": "DST" if is_dst else "WR",
                "gsis_id": "" if is_dst else f"GSIS-{player_id}",
                "team": "A" if is_dst else "B",
                "opp": "B" if is_dst else "A",
                "game_id": "G1",
                "salary": 5000,
                "in_frozen_union": in_union,
                "authoritative_actual": (
                    float(int(player_id)) if in_union else None
                ),
                "actual_source": ((
                    "team_defense_week.dst_dk_points"
                    if is_dst else "player_week_actuals.dk_points"
                ) if in_union else None),
                "schedule_game_id": "G1" if in_union else None,
                "schedule_home_team": "A" if in_union else None,
                "schedule_away_team": "B" if in_union else None,
                "home_score": 24 if in_union else None,
                "away_score": 17 if in_union else None,
                "terminal_home_score": 24 if in_union else None,
                "terminal_away_score": 17 if in_union else None,
                "terminal_game_status": "final" if in_union else None,
                "terminal_rule": (
                    "latest_pbp_end_game" if in_union else None
                ),
            })
    return pd.DataFrame(rows).loc[:, settlement.QUERY_COLUMNS]


def _identity(uri: str, raw: bytes, generation: str) -> dict:
    return {
        "uri": uri,
        "generation": generation,
        "metageneration": "1",
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }


def _query_meta(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "location": "US",
        "created": "2026-09-13T18:01:00+00:00",
        "started": "2026-09-13T18:01:01+00:00",
        "ended": CAPTURED.isoformat(),
        "total_bytes_processed": 1,
        "query_sha256": sha256(
            settlement.authoritative_settlement_sql().encode("utf-8")
        ).hexdigest(),
    }


def _run(monkeypatch, *, frame: pd.DataFrame | None = None,
         receipt_created: datetime = FROZEN,
         now: datetime = ATTEMPTED,
         panel: dict | None = None,
         receipt: dict | None = None,
         query_meta_mutator=None,
         score_created: datetime = CAPTURED,
         events: list[str] | None = None):
    monkeypatch.setenv(settlement.ENABLED_ENV, "1")
    panel = _panel_receipt() if panel is None else panel
    receipt = _receipt(panel=panel) if receipt is None else receipt
    monkeypatch.setattr(
        settlement.transport, "_validate_deployment", lambda value: value
    )
    monkeypatch.setattr(
        settlement.transport, "_validate_runtime_environment",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        settlement.transport, "_validate_shadow_receipt",
        lambda *args, **kwargs: (_rosters(), list(reversed(_rosters()))),
    )
    monkeypatch.setattr(
        settlement.transport, "_validate_panel_source_receipt",
        lambda value, **kwargs: value,
    )
    deployment_raw = settlement._canonical_json(_deployment())
    receipt_raw = settlement._canonical_json(receipt)
    panel_object, panel_raw = _panel_object(panel)
    downloads = []

    def download(client, *, uri, generation, label):
        del client
        downloads.append((uri, generation, label))
        if events is not None:
            events.append(f"download:{label}")
        if uri == settlement.transport.DEPLOYMENT_URI:
            return _identity(uri, deployment_raw, "11"), deployment_raw, FROZEN
        if uri == settlement.transport._week_uris(1)["shadow_receipt"]:
            return _identity(uri, receipt_raw, "22"), receipt_raw, receipt_created
        assert uri == panel_object["uri"]
        return _identity(uri, panel_raw, "33"), panel_raw, PANEL_CREATED

    uploads = []

    def upload(client, *, uri, value):
        del client
        uploads.append((uri, value))
        if events is not None:
            events.append(
                "upload:attempt" if len(uploads) == 1 else "upload:scores"
            )
        stamp = ATTEMPTED if len(uploads) == 1 else score_created
        raw = settlement._canonical_json(value)
        return {
            **_identity(uri, raw, str(len(uploads))),
            "created_at": stamp.isoformat(),
            "create_only": True,
        }

    query_calls = []

    def query(client, *, sql, parameters, job_id):
        del client
        query_calls.append((sql, parameters, job_id))
        if events is not None:
            events.append("query")
        meta = _query_meta(job_id)
        if query_meta_mutator is not None:
            query_meta_mutator(meta)
        return (_mapping_frame() if frame is None else frame, meta)

    result = settlement.materialize(
        week=1,
        shadow_receipt_generation="22",
        deployment_generation="11",
        storage_client=object(),
        bigquery_client=object(),
        now=lambda: now,
        download=download,
        upload=upload,
        query=query,
    )
    return result, downloads, uploads, query_calls


def test_sql_reads_only_mapping_authoritative_actuals_and_final_scores():
    sql = settlement.authoritative_settlement_sql().lower()
    assert "slate_player_features" in sql
    assert "player_week_actuals" in sql
    assert "team_defense_week" in sql
    assert "nfl_raw.schedules" in sql
    assert "nfl_raw.pbp" in sql
    assert "terminal_game_status" in sql
    assert "end( of)? game" in sql
    assert "^end( of)? game$" in sql
    assert "game_seconds_remaining" not in sql
    assert "latest_pbp_regulation_clock_zero" not in sql
    assert "where in_frozen_union" in sql
    assert "when not m.in_frozen_union then null" in sql
    for forbidden in (
        "winner", "payout", "ownership", " insert ", " update ",
        " merge ", " delete ", "replay_candidates_staging.actual_score",
    ):
        assert forbidden not in sql


def test_default_off_precedes_every_remote_read_query_or_write(monkeypatch):
    monkeypatch.delenv(settlement.ENABLED_ENV, raising=False)
    blocked = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("disabled settlement performed remote work")
    )
    with pytest.raises(settlement.AuthoritativeSettlementError, match="required"):
        settlement.materialize(
            week=1,
            shadow_receipt_generation="22",
            deployment_generation="11",
            storage_client=object(),
            bigquery_client=object(),
            download=blocked,
            upload=blocked,
            query=blocked,
        )


def test_disabled_cli_does_not_construct_cloud_clients(monkeypatch):
    monkeypatch.delenv(settlement.ENABLED_ENV, raising=False)
    monkeypatch.setattr(
        settlement.storage, "Client",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("disabled CLI constructed a storage client")
        ),
    )
    monkeypatch.setattr(
        settlement.bigquery, "Client",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("disabled CLI constructed a BigQuery client")
        ),
    )
    with pytest.raises(settlement.AuthoritativeSettlementError, match="required"):
        settlement.main([
            "--week", "1",
            "--shadow-receipt-generation", "22",
            "--deployment-generation", "11",
        ])


def test_success_scores_exact_union_and_publishes_no_maximum(monkeypatch):
    result, downloads, uploads, query_calls = _run(monkeypatch)
    uris = settlement.transport._week_uris(1)
    assert downloads == [
        (settlement.transport.DEPLOYMENT_URI, "11", "deployment"),
        (uris["shadow_receipt"], "22", "shadow receipt"),
        (
            settlement.panel_producer.canonical_receipt_uri(
                season=2026, week=1, snapshot_id=SNAPSHOT_ID
            ),
            "33",
            "panel source receipt",
        ),
    ]
    assert [uri for uri, _ in uploads] == [
        uris["settlement_attempt"], uris["settled_scores"]
    ]
    attempt = uploads[0][1]
    artifact = uploads[1][1]
    assert attempt["shadow_receipt_object"]["generation"] == "22"
    assert attempt["panel_source_receipt_object"]["generation"] == "33"
    assert attempt["player_frame_sha256"] == _panel_receipt()["validation"][
        "player_frame_sha256"
    ]
    assert attempt["outcomes_queried_at_creation"] is False
    assert attempt["prelock_rows_mutated"] is False
    assert len(query_calls) == 1
    assert query_calls[0][2] == attempt["query_job_id"]
    assert artifact["version"] == settlement.SETTLED_VERSION
    assert artifact["labels_complete"] is True
    assert artifact["source_identity"]["source"] == settlement.SOURCE_NAME
    assert artifact["source_identity"]["source"] != (
        "replay_candidates_staging.actual_score"
    )
    assert {row["roster_key"] for row in artifact["scores"]} == set(_rosters())
    source = artifact["source_identity"]
    assert source["attempt_object"]["generation"] == "1"
    assert source["deployment_object"]["generation"] == "11"
    assert source["shadow_receipt_object"]["generation"] == "22"
    assert source["panel_source_receipt_object"]["generation"] == "33"
    assert source["query_receipt"]["job_id"] == attempt["query_job_id"]
    assert source["query_parameters"]["panels"] == PANELS
    assert len(source["query_result_sha256"]) == 64
    assert source["roster_union_sha256"] == attempt["roster_union_sha256"]
    first = artifact["scores"][0]
    assert first["actual_score"] == sum(
        int(value) for value in first["roster_key"].split(",")
    )
    assert "max" not in str(artifact).lower()
    assert result["labels_complete"] is True
    assert result["prelock_rows_mutated"] is False


def test_phase_order_is_attempt_then_query_then_score(monkeypatch):
    events: list[str] = []
    _run(monkeypatch, events=events)
    assert events[-3:] == ["upload:attempt", "query", "upload:scores"]


def test_panel_source_object_generation_is_not_caller_substitutable(monkeypatch):
    receipt = _receipt()
    receipt["source_identity"]["panel_source_receipt_object"][
        "generation"
    ] = "34"
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="generation/content"
    ):
        _run(monkeypatch, receipt=receipt)


def test_panel_source_object_rejects_non_create_once_metageneration(monkeypatch):
    receipt = _receipt()
    receipt["source_identity"]["panel_source_receipt_object"][
        "metageneration"
    ] = "2"
    with pytest.raises(
        settlement.AuthoritativeSettlementError,
        match="panel-source receipt identity",
    ):
        _run(monkeypatch, receipt=receipt)


@pytest.mark.parametrize("field", ("canonical_panel", "snapshot_id", "code_sha"))
def test_panel_source_body_must_match_shadow_and_deployment(field, monkeypatch):
    panel = _panel_receipt()
    panel[field] = "wrong"
    receipt = _receipt(panel=panel)
    with pytest.raises(
        settlement.AuthoritativeSettlementError,
        match="frozen panel source|generation-pinned panel source",
    ):
        _run(monkeypatch, panel=panel, receipt=receipt)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("location", "us-central1"),
        ("query_sha256", "0" * 64),
        ("created", "2026-09-13T17:59:59+00:00"),
        ("ended", "2026-09-13T17:59:59+00:00"),
    ),
)
def test_query_receipt_is_exact_and_post_attempt(field, value, monkeypatch):
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="query provenance"
    ):
        _run(
            monkeypatch,
            query_meta_mutator=lambda meta: meta.__setitem__(field, value),
        )


def test_score_object_cannot_claim_creation_before_query_completion(monkeypatch):
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="predates"
    ):
        _run(monkeypatch, score_created=ATTEMPTED)


def test_settled_artifact_rejects_provenance_tampering(monkeypatch):
    _, _, uploads, _ = _run(monkeypatch)
    artifact = copy.deepcopy(uploads[1][1])
    expected_source = copy.deepcopy(artifact["source_identity"])
    artifact["source_identity"]["shadow_receipt_object"]["generation"] = "99"
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="source identity"
    ):
        settlement.validate_settled_artifact(
            artifact,
            expected_rosters=set(_rosters()),
            week=1,
            lock_at=LOCK,
            expected_source_identity=expected_source,
        )


@pytest.mark.parametrize(
    "defect",
    (
        "missing-map", "null-actual", "late-map", "wrong-code",
        "eligible", "unfinished-game", "zero-clock-live-score", "duplicate-gsis",
        "swapped-gsis", "post-snapshot-map", "duplicate-map", "wrong-source",
        "bad-config", "positive-infinity", "negative-infinity", "wrong-game",
        "wrong-dst-team", "companion-outcome", "score-disagreement",
    ),
)
def test_incomplete_or_unfrozen_labels_burn_attempt_without_score_artifact(
    defect, monkeypatch
):
    frame = _mapping_frame()
    if defect == "missing-map":
        frame = frame.iloc[:-1].copy()
    elif defect == "null-actual":
        frame.loc[0, "authoritative_actual"] = None
    elif defect == "late-map":
        frame.loc[0, "generated_at"] = LOCK
    elif defect == "wrong-code":
        frame.loc[0, "code_sha"] = "f" * 40
    elif defect == "eligible":
        frame.loc[0, "research_eligible"] = True
    elif defect == "unfinished-game":
        frame.loc[0, "home_score"] = None
    elif defect == "zero-clock-live-score":
        # Populated/reconciled scores at 0:00 are still live without an
        # explicit END GAME event (for example, an accepted untimed-down penalty).
        frame.loc[0, "terminal_game_status"] = "not_final"
        frame.loc[0, "terminal_rule"] = None
    elif defect == "duplicate-gsis":
        frame.loc[1, "gsis_id"] = frame.loc[0, "gsis_id"]
    elif defect == "swapped-gsis":
        first = frame.loc[0, "gsis_id"]
        frame.loc[0, "gsis_id"] = frame.loc[1, "gsis_id"]
        frame.loc[1, "gsis_id"] = first
    elif defect == "post-snapshot-map":
        frame.loc[0, "generated_at"] = datetime(
            2026, 9, 13, 16, 30, tzinfo=timezone.utc
        )
    elif defect == "duplicate-map":
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    elif defect == "wrong-source":
        frame.loc[0, "actual_source"] = "unlicensed.actual"
    elif defect == "bad-config":
        frame.loc[0, "config_hash"] = ""
    elif defect == "positive-infinity":
        frame.loc[0, "authoritative_actual"] = float("inf")
    elif defect == "negative-infinity":
        frame.loc[0, "authoritative_actual"] = float("-inf")
    elif defect == "wrong-game":
        frame.loc[0, "schedule_game_id"] = "G2"
    elif defect == "companion-outcome":
        companion = frame.panel_run_id.eq("companion")
        frame.loc[companion, "authoritative_actual"] = 1.0
    elif defect == "score-disagreement":
        frame.loc[0, "terminal_home_score"] = 23
    else:
        dst = frame.pos.eq("DST")
        frame.loc[dst, "schedule_home_team"] = "C"
        frame.loc[dst, "schedule_away_team"] = "D"

    captured_uploads = []
    original = settlement.materialize

    def record_materialize(*args, **kwargs):
        original_upload = kwargs["upload"]

        def record_upload(*upload_args, **upload_kwargs):
            result = original_upload(*upload_args, **upload_kwargs)
            captured_uploads.append(upload_kwargs["value"])
            return result

        kwargs["upload"] = record_upload
        return original(*args, **kwargs)

    monkeypatch.setattr(settlement, "materialize", record_materialize)
    with pytest.raises(settlement.AuthoritativeSettlementError):
        _run(monkeypatch, frame=frame)
    assert len(captured_uploads) == 1
    assert captured_uploads[0]["version"] == settlement.ATTEMPT_VERSION


def test_receipt_must_be_remotely_frozen_before_lock(monkeypatch):
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="creation time differs"
    ):
        _run(monkeypatch, receipt_created=LOCK)


def test_settlement_cannot_open_attempt_before_lock(monkeypatch):
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="cannot start before lock"
    ):
        _run(monkeypatch, now=LOCK)


def test_shadow_source_requires_exact_prelock_query_binding():
    source = _receipt()["source_identity"]
    source["candidate_query"]["ended"] = source["player_query"]["ended"]
    source["player_query"]["ended"] = "2026-09-13T16:01:00+00:00"
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="query completion"
    ):
        settlement._validate_shadow_source(source)


def test_generation_download_is_fixed_and_pinned():
    raw = settlement._canonical_json({"version": "receipt"})

    class Blob:
        generation = 7
        metageneration = 1
        size = len(raw)
        time_created = FROZEN

        def reload(self):
            return None

        def download_as_bytes(self, **kwargs):
            assert kwargs == {"if_generation_match": 7}
            return raw

    class Bucket:
        def blob(self, name, generation):
            assert name == "path/object.json"
            assert generation == 7
            return Blob()

    class Client:
        def bucket(self, name):
            assert name == "bucket"
            return Bucket()

    identity, observed, created = settlement._download_generation(
        Client(),
        uri="gs://bucket/path/object.json",
        generation="7",
        label="test",
    )
    assert observed == raw
    assert identity["generation"] == "7"
    assert identity["sha256"] == sha256(raw).hexdigest()
    assert created == FROZEN


@pytest.mark.parametrize("generation", ("0", "-1", "abc", "1.0"))
def test_generation_download_rejects_nonpositive_or_noninteger_identity(
    generation,
):
    with pytest.raises(
        settlement.AuthoritativeSettlementError, match="generation differs"
    ):
        settlement._download_generation(
            object(),
            uri="gs://bucket/path/object.json",
            generation=generation,
            label="test",
        )


def test_v2_is_intentionally_not_spoofed_as_old_transport_source(monkeypatch):
    _, _, uploads, _ = _run(monkeypatch)
    artifact = uploads[1][1]
    assert artifact["version"] != "b1-corpus-tail-settled-scores-v1"
    assert artifact["source_identity"]["query_receipt"]["query_sha256"] != sha256(
        settlement.transport._settlement_sql().encode("utf-8")
    ).hexdigest()
