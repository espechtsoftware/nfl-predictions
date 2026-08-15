from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.recourse_worlds import (
    RECOURSE_WORLD_ARTIFACT_VERSION,
    decode_recourse_world_artifact,
    derive_remaining_worlds,
    encode_recourse_world_artifact,
    load_recourse_world_artifact,
    persist_recourse_world_artifact,
    propose_recourse_from_artifact,
)
from nfl_dfs.inference import prospective_shadow
from nfl_dfs.inference.prospective_shadow import paired_shadow_receipt
from nfl_dfs.optimizer.lineup import Lineup


def _fixture():
    specs = []
    for pos, count in (("QB", 3), ("RB", 5), ("WR", 7), ("TE", 3), ("DST", 3)):
        for number in range(1, count + 1):
            specs.append((f"{pos}{number}", pos))
    rows = []
    for internal_id, (dk_id, pos) in enumerate(specs):
        rows.append({
            "id": internal_id,
            "name": dk_id,
            "pos": pos,
            "team": f"T{internal_id % 8}",
            "opp": f"T{(internal_id + 1) % 8}",
            "game_id": f"G{internal_id % 4}",
            "salary": 5_000,
            "proj": 10.0,
        })
    by_dk = {row["name"]: row for row in rows}
    entries = {
        "E1": ["QB1", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "WR4", "DST1"],
        "E2": ["QB2", "RB3", "RB4", "WR5", "WR6", "WR7", "TE2", "RB5", "DST2"],
    }
    boom = ["QB3", "RB1", "RB3", "WR1", "WR5", "WR6", "TE3", "WR2", "DST3"]
    roster_names = [*entries.values(), boom]
    lineups = tuple(Lineup([by_dk[name] for name in roster]) for roster in roster_names)
    worlds = np.ones((len(rows), 100), dtype=np.float32)
    qb3_row = next(row["id"] for row in rows if row["name"] == "QB3")
    worlds[qb3_row] = 250.0
    totals = np.stack([
        worlds[[player["id"] for player in lineup.players]].sum(axis=0)
        for lineup in lineups
    ])
    batch = CandidateBatch(
        candidates=lineups,
        candidate_totals=totals,
        player_ids=tuple(row["id"] for row in rows),
        player_rows=tuple(rows),
        row_draws=worlds,
        all_tags={lineup.ids: ("test",) for lineup in lineups},
        metadata={"portfolio": "CBWU", "world_blocks": 5},
    )
    mapping = {row["id"]: row["name"] for row in rows}
    catalog = pd.DataFrame([{
        "dk_id": row["name"],
        "pos": row["pos"],
        "salary": row["salary"],
        "kickoff": "2026-09-13T17:00:00Z",
    } for row in rows])
    empty_status = pd.DataFrame(
        columns=["dk_id", "points_to_date", "game_status", "available_at"]
    )
    return batch, mapping, catalog, entries, empty_status


def test_recourse_artifact_round_trip_and_proposal():
    batch, mapping, catalog, entries, status = _fixture()
    payload, receipt = encode_recourse_world_artifact(
        batch, mapping, generated_at="2026-09-13T12:00:00Z"
    )
    assert receipt["artifact_version"] == RECOURSE_WORLD_ARTIFACT_VERSION
    artifact = decode_recourse_world_artifact(payload, receipt["sha256"])
    result = propose_recourse_from_artifact(
        artifact,
        entries,
        catalog,
        status,
        as_of="2026-09-13T16:00:00Z",
    )
    assert result["changed_entries"] == 1
    assert result["final_book_objective"] > result["initial_book_objective"]
    assert result["world_adapter_receipt"]["artifact_sha256"] == receipt["sha256"]
    assert result["uses_post_decision_outcomes"] is False


def test_recourse_artifact_checksum_and_locked_status_fail_closed():
    batch, mapping, catalog, _, status = _fixture()
    payload, receipt = encode_recourse_world_artifact(
        batch, mapping, generated_at="2026-09-13T12:00:00Z"
    )
    with pytest.raises(ValueError, match="sha256 differs"):
        decode_recourse_world_artifact(payload, "0" * 64)
    artifact = decode_recourse_world_artifact(payload, receipt["sha256"])
    catalog.loc[catalog.dk_id.eq("QB1"), "kickoff"] = "2026-09-13T15:00:00Z"
    with pytest.raises(ValueError, match="missing locked player QB1"):
        derive_remaining_worlds(
            artifact, catalog, status, as_of="2026-09-13T16:00:00Z"
        )


def test_recourse_artifact_rejects_outcome_metadata():
    batch, mapping, _, _, _ = _fixture()
    batch.metadata["nested"] = {"actual_score": 200.0}
    with pytest.raises(ValueError, match="outcome fields"):
        encode_recourse_world_artifact(
            batch, mapping, generated_at="2026-09-13T12:00:00Z"
        )


def test_final_player_is_fixed_and_has_zero_remaining_score():
    batch, mapping, catalog, _, _ = _fixture()
    payload, receipt = encode_recourse_world_artifact(
        batch, mapping, generated_at="2026-09-13T12:00:00Z"
    )
    artifact = decode_recourse_world_artifact(payload, receipt["sha256"])
    catalog.loc[catalog.dk_id.eq("QB1"), "kickoff"] = "2026-09-13T15:00:00Z"
    status = pd.DataFrame([{
        "dk_id": "QB1",
        "points_to_date": 22.5,
        "game_status": "final",
        "available_at": "2026-09-13T15:59:00Z",
    }])
    remaining, points, adapter = derive_remaining_worlds(
        artifact, catalog, status, as_of="2026-09-13T16:00:00Z"
    )
    assert remaining["QB1"].eq(0).all()
    assert points.set_index("dk_id").loc["QB1", "points_to_date"] == 22.5
    assert adapter["status_counts"]["final"] == 1
    assert adapter["uses_post_decision_outcomes"] is False
    status["actual_score"] = status.points_to_date
    with pytest.raises(ValueError, match="game status contains outcome fields"):
        derive_remaining_worlds(
            artifact, catalog, status, as_of="2026-09-13T16:00:00Z"
        )


def test_recourse_artifact_persistence_is_create_only_and_checksum_bound():
    batch, mapping, _, _, _ = _fixture()

    class Blob:
        data = None
        upload_args = None

        def upload_from_string(self, data, **kwargs):
            self.data = data
            self.upload_args = kwargs

        def download_as_bytes(self):
            return self.data

    blob = Blob()

    class Bucket:
        def blob(self, name):
            assert name == "recourse/2026/w1/control.npz"
            return blob

    class Client:
        def bucket(self, name):
            assert name == "raw-bucket"
            return Bucket()

    receipt = persist_recourse_world_artifact(
        batch,
        mapping,
        generated_at="2026-09-13T12:00:00Z",
        bucket_name="raw-bucket",
        object_name="recourse/2026/w1/control.npz",
        storage_client=Client(),
    )
    assert blob.upload_args["if_generation_match"] == 0
    assert receipt["create_only"] is True
    artifact = load_recourse_world_artifact(
        receipt["uri"], receipt["sha256"], storage_client=Client()
    )
    assert artifact["sha256"] == receipt["sha256"]


def test_paired_shadow_uses_identical_worlds_and_freezes_memberships():
    batch, mapping, _, _, _ = _fixture()
    control_lineups, receipt = paired_shadow_receipt(
        batch,
        batch,
        list(batch.candidates[:2]),
        mapping,
        n_entries=2,
    )
    assert len(control_lineups) == 2
    assert receipt["player_worlds_identical"] is True
    assert receipt["candidate_budget_identical"] is True
    assert receipt["memberships"]["2"]["treatment"]
    assert receipt["uses_post_lock_outcomes"] is False
    assert receipt["production_enabled"] is False

    altered = CandidateBatch(
        candidates=batch.candidates,
        candidate_totals=batch.candidate_totals,
        player_ids=batch.player_ids,
        player_rows=batch.player_rows,
        row_draws=batch.row_draws + 1,
        all_tags=batch.all_tags,
        metadata=batch.metadata,
    )
    with pytest.raises(ValueError, match="player worlds differ"):
        paired_shadow_receipt(
            batch,
            altered,
            list(altered.candidates[:2]),
            mapping,
            n_entries=2,
        )


def test_paired_shadow_runner_persists_both_arms_and_manifest(monkeypatch):
    batch, mapping, _, _, _ = _fixture()
    salaries = pd.DataFrame([{
        "dk_player_id": player_id,
        "dk_draftable_id": int(10_000 + player_id),
        "salary": 5_000,
    } for player_id in batch.player_ids])

    class Store:
        def classic_salaries(self, draft_group_id):
            assert draft_group_id == 9001
            return salaries

    def fake_build(*args, **kwargs):
        kwargs["_control_candidate_capture"](batch)
        kwargs["_candidate_capture"](batch)
        return list(batch.candidates[:2])

    monkeypatch.setattr(
        "nfl_dfs.inference.live_lineups.build_sim_lineups", fake_build
    )
    monkeypatch.setattr(
        prospective_shadow,
        "paired_shadow_receipt",
        lambda *args, **kwargs: (list(batch.candidates[:2]), {
            "shadow_version": "prospective-archetype-paired-shadow-v1",
            "memberships": {"80": {"control": [], "treatment": []}},
            "uses_post_lock_outcomes": False,
            "production_enabled": False,
        }),
    )
    persisted = []

    def persist(*args, object_name, context, **kwargs):
        persisted.append((object_name, context))
        return {
            "uri": f"gs://raw/{object_name}",
            "sha256": str(len(persisted)) * 64,
        }

    monkeypatch.setattr(
        prospective_shadow, "persist_recourse_world_artifact", persist
    )
    monkeypatch.setenv("CODE_SHA", "abcdef123456")

    uploaded = {}

    class Blob:
        def upload_from_string(self, payload, **kwargs):
            assert kwargs["if_generation_match"] == 0
            assert json.loads(payload)["draft_group_id"] == 9001
            uploaded["payload"] = bytes(payload)

    class Bucket:
        def blob(self, name):
            assert name.endswith("/manifest.json")
            return Blob()

    class Client:
        def bucket(self, name):
            assert name == "raw"
            return Bucket()

    result = prospective_shadow.run_paired_prospective_shadow(
        store=Store(),
        season=2026,
        week=1,
        draft_group_id=9001,
        generated_at=pd.Timestamp("2026-09-13T12:00:00Z").to_pydatetime(),
        storage_client=Client(),
        bucket_name="raw",
    )
    assert [context["arm"] for _, context in persisted] == [
        "control", "treatment",
    ]
    assert result["manifest_create_only"] is True
    assert len(result["manifest_sha256"]) == 64
    assert result["manifest_bytes"] > 0
    assert hashlib.sha256(uploaded["payload"]).hexdigest() == (
        result["manifest_sha256"]
    )
    assert result["code_sha"] == "abcdef123456"
    assert result["draft_group_id"] == 9001


def test_paired_shadow_runner_rejects_missing_code_sha(monkeypatch):
    monkeypatch.delenv("CODE_SHA", raising=False)
    with pytest.raises(ValueError, match="requires CODE_SHA"):
        prospective_shadow.run_paired_prospective_shadow(
            store=object(),
            season=2026,
            week=1,
            draft_group_id=9001,
            generated_at=pd.Timestamp("2026-09-13T12:00:00Z").to_pydatetime(),
            bucket_name="raw",
        )


def test_prospective_shadow_cli_and_deployment_are_registered():
    root = Path(prospective_shadow.__file__).resolve().parents[3]
    cli = (root / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    deploy = (root / "deploy/deploy_jobs.sh").read_text(encoding="utf-8")
    resume = (
        root / "scripts/resume_2026_production_schedulers.py"
    ).read_text(encoding="utf-8")
    assert "shadow-archetype-paired" in cli
    assert "job shadow-archetype-paired" in deploy
    assert "s-shadow-archetype-paired-early" in deploy
    assert "s-shadow-archetype-paired-late" in deploy
    assert "s-shadow-archetype-paired-early" in resume
