from __future__ import annotations

import json
from hashlib import sha256

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.research import corpus_r6_boom_first_allocation_v1 as science
from scripts import run_corpus_r6_boom_first_allocation_v1 as subject


def _identity(uri: str, marker: str, size: int = 123):
    return {
        "uri": uri,
        "generation": "7",
        "sha256": marker * 64,
        "bytes": size,
    }


def _build_receipt(code: str = "b" * 40, digest: str = "sha256:" + "c" * 64):
    return {
        "build_id": "12345678-1234-1234-1234-123456789abc",
        "finish_time": "2026-08-29T12:05:00+00:00",
        "image_digest": digest,
        "image_tag": (
            "us-central1-docker.pkg.dev/nfl-predictions-503414/"
            "nfl-dfs/nfl-dfs:fixture"
        ),
        "project_id": subject.FIXED_PROJECT,
        "region": subject.FIXED_REGION,
        "source_commit": code,
        "start_time": "2026-08-29T12:00:00+00:00",
        "status": "SUCCESS",
    }


def _source_provenance(execution_mode, *, code="b" * 40):
    return subject._build_source_provenance_v1(
        execution_mode=execution_mode,
        observed_source_commit=code,
        embedded_build_source_commit=(
            code if execution_mode == "manifest-smoke" else None
        ),
    )


def _preflight_receipt(source_identity, *, code: str = "b" * 40):
    body = {
        "schema_version": subject.PREFLIGHT_SMOKE_SCHEMA,
        "execution_mode": "preflight-smoke",
        "later_source_identity": source_identity,
        "later_source_freeze_sha256": "e" * 64,
        "code_commit": code,
        "manifest_identity": None,
        "manifest_sha256": None,
        "terminal_build_receipt_identity": None,
        "image_digest": None,
        "immutable_image_uri": None,
        "source_ordinal": 0,
        "slate_id": science.expected_slate_id_v1(0),
        "generation_snapshot_identity": None,
        "generation_snapshot_sha256": "1" * 64,
        "query_receipts_sha256": "2" * 64,
        "task_result_sha256": "3" * 64,
        "runtime_authority_sha256": "4" * 64,
        "normalized_slate_sha256": "5" * 64,
        "source_provenance": _source_provenance(
            "preflight-smoke", code=code
        ),
        "arm_science_sha256": "6" * 64,
        "control_reproductions_sha256": "7" * 64,
        "control_reproduction_count": 5,
        "all_five_control_books_reproduced": True,
        "selected_book_counts": {"control": 80, "treatment": 80},
        "both_arms_exact_80": True,
        "publication_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }
    return subject._with_hash(body, field="smoke_sha256")


class _FakeProvider:
    def describe_build(self, build_id):
        return {"id": build_id}


def _manifest():
    prefix = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-boom-first-allocation/fixture/"
    )
    descriptors = []
    for ordinal in range(science.TASK_COUNT):
        slate_id = science.expected_slate_id_v1(ordinal)
        uri = f"{prefix}inputs/{ordinal:02d}-{slate_id}.json"
        identity = _identity(uri, format((ordinal % 15) + 1, "x"))
        descriptors.append({
            "source_ordinal": ordinal,
            "slate_id": slate_id,
            "snapshot_identity": identity,
            "generation_snapshot_sha256": "f" * 64,
        })
    preflight_provenance = _source_provenance("preflight-smoke")
    return subject.build_manifest_v1(
        later_source_identity=_identity("gs://fixture/later-source.json", "a"),
        later_source_freeze_sha256="e" * 64,
        terminal_build_receipt=_build_receipt(),
        terminal_build_receipt_identity=_identity(
            "gs://fixture/terminal-build-receipt.json", "9"
        ),
        code_commit="b" * 40,
        image_digest="sha256:" + "c" * 64,
        immutable_image_uri="us-central1-docker.pkg.dev/p/r/i@sha256:" + "c" * 64,
        output_prefix=prefix,
        snapshot_descriptors=descriptors,
        preflight_smoke_sha256="7" * 64,
        preflight_scoped_source_sha256=preflight_provenance[
            "scoped_source_sha256"
        ],
    )


def _value_identity(uri, value, *, generation="1"):
    raw = science.canonical_json_bytes_v1(value)
    return {
        "uri": uri, "generation": generation,
        "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
    }


def _manifest_smoke_receipt(manifest, manifest_identity):
    binding = manifest["task_bindings"][0]
    body = {
        "schema_version": subject.MANIFEST_SMOKE_SCHEMA,
        "execution_mode": "manifest-smoke",
        "later_source_identity": manifest["later_source_identity"],
        "later_source_freeze_sha256": manifest[
            "later_source_freeze_sha256"
        ],
        "code_commit": manifest["code_commit"],
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "terminal_build_receipt_identity": manifest[
            "terminal_build_receipt_identity"
        ],
        "image_digest": manifest["image_digest"],
        "immutable_image_uri": manifest["immutable_image_uri"],
        "source_ordinal": 0,
        "slate_id": science.expected_slate_id_v1(0),
        "generation_snapshot_identity": binding["snapshot_identity"],
        "generation_snapshot_sha256": binding["generation_snapshot_sha256"],
        "query_receipts_sha256": "2" * 64,
        "task_result_sha256": "3" * 64,
        "runtime_authority_sha256": "4" * 64,
        "normalized_slate_sha256": "5" * 64,
        "source_provenance": _source_provenance("manifest-smoke"),
        "arm_science_sha256": "6" * 64,
        "control_reproductions_sha256": "7" * 64,
        "control_reproduction_count": 5,
        "all_five_control_books_reproduced": True,
        "selected_book_counts": {"control": 80, "treatment": 80},
        "both_arms_exact_80": True,
        "publication_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
    }
    return subject._with_hash(body, field="smoke_sha256")


def _launch_authorities(manifest, manifest_identity, smoke, *, execution_id):
    observation = subject.expected_provider_job_observation_v1(
        manifest=manifest, manifest_identity=manifest_identity,
        smoke_receipt=smoke,
    )
    claim = subject._build_launch_claim_v1(
        manifest=manifest, manifest_identity=manifest_identity,
        smoke_receipt=smoke, job_observation=observation,
    )
    claim_identity = _value_identity(
        subject._launch_claim_uri(manifest["output_prefix"]), claim
    )
    receipt = subject._build_launch_receipt_v1(
        claim=claim, claim_identity=claim_identity, execution_id=execution_id,
    )
    receipt_identity = _value_identity(
        subject._launch_receipt_uri(manifest["output_prefix"]), receipt
    )
    return claim, claim_identity, receipt, receipt_identity


def _catalog_completion(*, snapshot_identity, lease_identity, run_id="catalog-run-v1"):
    placeholder = _identity("gs://fixture/object.json", "8")
    body = {
        "schema_version": subject.CATALOG_OUTCOME_COMPLETION_SCHEMA,
        "run_id": run_id,
        "outcome_key_projection_identity": placeholder,
        "registered_request_identity": placeholder,
        "query_evidence_identity": placeholder,
        "realized_source_identity": placeholder,
        "outcome_snapshot_identity": snapshot_identity,
        "historical_outcome_lease_identity": lease_identity,
        "source_snapshot_at": "2026-08-26T23:58:47.451523+00:00",
        "source_slate_count": 54,
        "outcome_key_count": 29_605,
        "delta_query_key_count": 15_358,
        "one_historical_outcome_read": True,
        "one_exact_query_job": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "lineup_scoring_performed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
        "complete": True,
    }
    return subject._with_hash(body, field="completion_sha256")


def _lease_raw(run_id="catalog-run-v1"):
    body = {
        "version": "historical-outcome-active-v1",
        "run_id": run_id,
        "job": "atlas-minimal-c-s2023-w1-v1",
        "code_sha": "a" * 40,
        "image": "sha256:" + "b" * 64,
        "acquired_at": "2026-08-29T12:00:00+00:00",
    }
    return science.canonical_json_bytes_v1(body) + b"\n"


class _FakeStore:
    def __init__(self):
        self.objects = {}
        self.open_known_calls = []
        self.publish_calls = []

    def seed(self, uri, value):
        raw = science.canonical_json_bytes_v1(value)
        return self.seed_raw(uri, raw)

    def seed_raw(self, uri, raw, *, generation="1"):
        identity = {
            "uri": uri, "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return identity

    def read_exact(self, identity):
        raw, retained = self.objects[identity["uri"]]
        assert retained == identity
        return raw

    def open_known(self, uri, maximum_bytes):
        self.open_known_calls.append(uri)
        raw, identity = self.objects[uri]
        assert len(raw) <= maximum_bytes
        return raw, identity

    def publish_create_once(self, uri, raw):
        self.publish_calls.append(uri)
        if uri in self.objects:
            existing, identity = self.objects[uri]
            assert existing == raw
            return identity
        identity = {
            "uri": uri, "generation": "1", "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return identity

    def claim_launch_once(self, uri, raw):
        if uri in self.objects:
            raise subject.RunCorpusR6BoomFirstAllocationV1Error(
                "boom-first launch claim already exists"
            )
        identity = {
            "uri": uri, "generation": "1", "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[uri] = (raw, identity)
        return identity


class _FakeQueryJob:
    def __init__(self, frame, job_id):
        self._frame = frame
        self.job_id = job_id
        self.location = "US"
        self.total_bytes_processed = 1234
        self.cache_hit = False
        self.error_result = None

    def result(self):
        return self

    def to_dataframe(self):
        return self._frame.copy()


class _FakeBQ:
    def __init__(self, players, candidates):
        self.players = players
        self.candidates = candidates
        self.job_ids = []

    def query(self, sql, *, job_config, location, job_id):
        assert job_config.query_parameters
        assert location == "US"
        self.job_ids.append(job_id)
        frame = self.players if "proj_tourney" in sql else self.candidates
        return _FakeQueryJob(frame, job_id)


def _prepare_fixture_frames():
    player_rows = []
    candidate_rows = []
    slates = []
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST", "WR"]
    for ordinal, (season, week) in enumerate(science.SLATE_KEYS):
        artifacts = []
        for index, block in enumerate(science.BLOCK_ORDER):
            marker = format(index + 1, "x")
            artifacts.append({
                "block": block,
                "bytes": 1000 + ordinal * 5 + index,
                "candidate_rows": 1,
                "generation": str(ordinal * 5 + index + 1),
                "panel_run_id": science.SOURCE_PANELS[index],
                "season": season,
                "sha256": marker * 64,
                "updated": "2026-08-21T00:00:00+00:00",
                "uri": f"gs://fixture/worlds/{ordinal}-{block}.npz",
                "week": week,
            })
            panel = science.candidate_source_panel_v1(season, week, block)
            roster = []
            for player_index, position in enumerate(positions):
                player_id = f"{season}-{week}-{player_index}"
                roster.append(player_id)
                player_rows.append({
                    "panel_run_id": panel, "season": season, "week": week,
                    "id": player_id, "gsis_id": player_id, "name": player_id,
                    "pos": position, "team": f"T{player_index % 3}",
                    "opp": f"T{(player_index + 1) % 3}",
                    "game_id": f"g{player_index % 2}",
                    "salary": 3000 + player_index * 100,
                    "proj": 10.0 + player_index,
                    "proj_tourney": 9.0 + player_index,
                    "own_est": 0.01 * player_index,
                    "consensus_div": None, "market_points": None,
                    "model_points_pre": None,
                    "mean_projection": 10.0 + player_index,
                    "proj_p10": 1.0, "proj_p50": 10.0,
                    "proj_p90": 20.0, "proj_std": 4.0,
                })
            candidate_rows.append({
                "panel_run_id": panel, "season": season, "week": week,
                "cand_ix": 0, "tag": "lev", "players": ",".join(roster),
                "score_artifact_uri": f"gs://fixture/worlds/{ordinal}-{block}.npz",
                "score_artifact_sha256": marker * 64,
            })
        slates.append({
            "season": season, "week": week,
            "slate_id": science.expected_slate_id_v1(ordinal),
            "artifact_receipts": artifacts,
        })
    return pd.DataFrame(player_rows), pd.DataFrame(candidate_rows), slates


def test_manifest_records_exact_54_task_launch_and_construction_preset():
    manifest = subject.validate_manifest_v1(_manifest())
    assert manifest["task_count"] == 54
    assert manifest["launch_shape"] == {
        "project": "nfl-predictions-503414",
        "region": "us-central1",
        "reused_job_name": subject.FIXED_REUSED_JOB_NAME,
        "reused_job_uid": subject.FIXED_REUSED_JOB_UID,
        "service_account": subject.FIXED_SERVICE_ACCOUNT,
        "tasks": 54,
        "parallelism": 54,
        "cpu": "8",
        "memory": "32Gi",
        "timeout_seconds": 21600,
        "max_retries": 0,
        "command": list(subject.EXPECTED_TASK_COMMAND),
        "manifest_identity_environment": subject.MANIFEST_IDENTITY_ENV,
        "task0_smoke_sha256_environment": subject.TASK0_SMOKE_SHA_ENV,
        "new_job_creation_allowed": False,
    }
    assert manifest["construction_preset"] == science.construction_preset_v1()
    assert manifest["generation_snapshot_law"] == {
        "source_table": subject.PLAYER_TABLE,
        "capture_time": "prepare-command",
        "create_once_per_slate": True,
        "objective_field": "proj_tourney",
        "exact_control_roster_and_world_total_reproduction_required_per_seed": True,
        "postlock_columns_selected": [],
    }
    assert manifest["control_allocation"] == {
        "leverage": 160, "boom": 40, "role": 12,
    }
    assert manifest["treatment_allocation"] == {
        "leverage": 40, "boom": 160, "role": 12,
    }


def test_prepare_freezes_54_snapshots_with_distinct_internal_and_object_hashes(
    monkeypatch,
):
    players, candidates, slates = _prepare_fixture_frames()
    store = _FakeStore()
    source = {"freeze_sha256": "e" * 64, "slates": slates}
    source_identity = store.seed("gs://fixture/later-source.json", source)
    build_identity = store.seed(
        "gs://fixture/terminal-build-receipt.json", _build_receipt()
    )
    monkeypatch.setattr(
        subject.later_source, "validate_source_freeze",
        lambda value, expected_freeze_sha256: value,
    )
    monkeypatch.setattr(
        subject.transport, "_validate_provider_build_attestation_v1",
        lambda **kwargs: None,
    )
    prefix = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "corpus-r6-boom-first-allocation/prepare-fixture/"
    )
    bq = _FakeBQ(players, candidates)
    result = subject.prepare_from_request_v1({
        "later_source_identity": source_identity,
        "terminal_build_receipt_identity": build_identity,
        "preflight_smoke_receipt": _preflight_receipt(source_identity),
        "code_commit": "b" * 40,
        "image_digest": "sha256:" + "c" * 64,
        "immutable_image_uri": "us-central1-docker.pkg.dev/p/r/i@sha256:" + "c" * 64,
        "output_prefix": prefix,
    }, store=store, bq_client=bq, provider=_FakeProvider())
    assert result["generation_snapshot_count"] == 54
    assert len(bq.job_ids) == 2
    manifest_raw, _ = store.objects[result["manifest_identity"]["uri"]]
    manifest = subject.validate_manifest_v1(json.loads(manifest_raw))
    first = manifest["task_bindings"][0]
    assert first["generation_snapshot_sha256"] != first[
        "snapshot_identity"
    ]["sha256"]
    assert manifest["task_bindings"][36]["slate_id"] == "2025-w01"


def test_preflight_rejects_unobserved_caller_commit_before_any_source_read():
    class Provider:
        def current_source_commit(self):
            return "c" * 40

    class NoReadStore:
        def read_exact(self, identity):  # pragma: no cover - must not run
            raise AssertionError("source read occurred before commit authority")

    class NoQuery:
        def query(self, *args, **kwargs):  # pragma: no cover - must not run
            raise AssertionError("query occurred before commit authority")

    with pytest.raises(
        subject.RunCorpusR6BoomFirstAllocationV1Error,
        match="preflight smoke code commit differs",
    ):
        subject.preflight_smoke_from_request_v1({
            "later_source_identity": _identity("gs://fixture/source.json", "a"),
            "code_commit": "b" * 40,
        }, store=NoReadStore(), bq_client=NoQuery(), provider=Provider())


def test_generation_passes_named_incumbent_construction_explicitly(monkeypatch):
    captured = {}
    batch = CandidateBatch(
        candidates=tuple(), candidate_totals=np.empty((0, 1)),
        player_ids=("p1",), player_rows=({"id": "p1"},),
        row_draws=np.zeros((1, 1)), all_tags={}, metadata={},
    )

    def fake_tail(*args, **kwargs):
        captured["stack"] = args[5]
        captured["environment"] = kwargs["policy_env"]
        kwargs["candidate_capture"](batch)
        return [object()]

    monkeypatch.setattr(subject.atlas, "tail_select_lineups", fake_tail)
    receipt = science.construction_preset_v1()["named_construction_preset"]
    environment = dict(receipt["optimizer_environment"])
    environment.update({
        "GEN_TOTAL_BUDGET": "200",
        "N_LEV": "160",
        "N_BOOM": "40",
        "PROSPECTIVE_SHADOW_ID": "boom-first-allocation-control-k1-v1",
        "BOOM_UNIQUE_FILL": "0",
    })
    result = subject._generate_with_frozen_construction_v1(
        pd.DataFrame([{"id": "p1"}]), np.zeros((1, 1)), environment,
        role_identities=[],
    )
    assert result.candidates == batch.candidates
    assert captured["stack"].qb_stack_min == 2
    assert captured["stack"].bring_back_min == 1
    assert captured["stack"].forbid_rb_vs_dst is True
    assert captured["stack"].forbid_two_rb_same_team is True
    assert result.metadata["construction_preset_receipt"] == receipt
    assert captured["environment"]["N_EPISTEMIC"] == "0"


def test_manifest_rejects_any_non_54_snapshot_lattice():
    manifest = _manifest()
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    body["task_bindings"] = body["task_bindings"][:-1]
    body["task_bindings_sha256"] = subject._hash(body["task_bindings"])
    broken = {**body, "manifest_sha256": subject._hash(body)}
    with pytest.raises(subject.RunCorpusR6BoomFirstAllocationV1Error):
        subject.validate_manifest_v1(broken)


def test_job_configuration_binds_reused_uid_service_account_build_and_smoke():
    manifest = _manifest()
    manifest_identity = _value_identity(manifest["manifest_uri"], manifest)
    smoke = _manifest_smoke_receipt(manifest, manifest_identity)
    configuration = subject.build_job_configuration_v1(
        manifest=manifest, manifest_identity=manifest_identity,
        smoke_receipt=smoke,
    )
    assert configuration["reused_job_name"] == subject.FIXED_REUSED_JOB_NAME
    assert configuration["reused_job_uid"] == subject.FIXED_REUSED_JOB_UID
    assert configuration["service_account"] == subject.FIXED_SERVICE_ACCOUNT
    assert configuration["terminal_build_receipt_identity"] == manifest[
        "terminal_build_receipt_identity"
    ]
    assert configuration["container_environment"][
        subject.TASK0_SMOKE_SHA_ENV
    ] == smoke["smoke_sha256"]
    assert configuration["new_job_creation_allowed"] is False


def test_launch_has_one_provider_call_and_requires_manifest_smoke(monkeypatch):
    manifest = _manifest()
    manifest_identity = _value_identity(manifest["manifest_uri"], manifest)
    smoke = _manifest_smoke_receipt(manifest, manifest_identity)
    observation = subject.expected_provider_job_observation_v1(
        manifest=manifest, manifest_identity=manifest_identity,
        smoke_receipt=smoke,
    )

    class Provider:
        launch_count = 0

        def describe_job(self, job_name):
            assert job_name == subject.FIXED_REUSED_JOB_NAME
            return observation

        def launch_existing_job(self, job_name):
            self.launch_count += 1
            return "boom-first-execution-abc"

    provider = Provider()
    store = _FakeStore()
    monkeypatch.setattr(
        subject, "_open_manifest",
        lambda value, store: (manifest, manifest_identity),
    )
    result = subject.launch_existing_job_v1(
        manifest_identity=manifest_identity, smoke_receipt=smoke,
        store=store, provider=provider,
    )
    assert provider.launch_count == 1
    assert result["provider_launch_call_count"] == 1
    assert result["execution_id"] == "boom-first-execution-abc"
    assert result["launch_claim_identity"]["uri"] == (
        subject._launch_claim_uri(manifest["output_prefix"])
    )
    assert result["launch_receipt_identity"]["uri"] == (
        subject._launch_receipt_uri(manifest["output_prefix"])
    )
    with pytest.raises(
        subject.RunCorpusR6BoomFirstAllocationV1Error,
        match="launch claim already exists",
    ):
        subject.launch_existing_job_v1(
            manifest_identity=manifest_identity, smoke_receipt=smoke,
            store=store, provider=provider,
        )
    assert provider.launch_count == 1
    broken = dict(smoke)
    broken["smoke_sha256"] = "0" * 64
    with pytest.raises(subject.RunCorpusR6BoomFirstAllocationV1Error):
        subject.launch_existing_job_v1(
            manifest_identity=manifest_identity, smoke_receipt=broken,
            store=store, provider=provider,
        )
    assert provider.launch_count == 1


def test_provider_terminal_rejects_any_non_exact_54_status():
    manifest = _manifest()
    manifest_identity = _value_identity(manifest["manifest_uri"], manifest)
    smoke = _manifest_smoke_receipt(manifest, manifest_identity)
    observation = subject.expected_provider_job_observation_v1(
        manifest=manifest, manifest_identity=manifest_identity,
        smoke_receipt=smoke,
    )
    _claim, _claim_identity, launch_receipt, launch_receipt_identity = (
        _launch_authorities(
            manifest, manifest_identity, smoke,
            execution_id="boom-first-execution-abc",
        )
    )
    raw = {
        "execution_id": "boom-first-execution-abc",
        "job_name": subject.FIXED_REUSED_JOB_NAME,
        "job_uid": subject.FIXED_REUSED_JOB_UID,
        "service_account": subject.FIXED_SERVICE_ACCOUNT,
        "project_id": subject.FIXED_PROJECT,
        "region": subject.FIXED_REGION,
        "task_count": 54,
        "succeeded_count": 54,
        "failed_count": 0,
        "cancelled_count": 0,
        "running_count": 0,
        "terminal": True,
        "provider_observed": True,
        "job_observation": observation,
    }
    proof = subject.build_provider_terminal_execution_v1(
        raw, manifest=manifest, manifest_identity=manifest_identity,
        smoke_receipt=smoke, launch_receipt=launch_receipt,
        launch_receipt_identity=launch_receipt_identity,
    )
    assert proof["succeeded_count"] == 54
    broken = dict(raw)
    broken["succeeded_count"] = 53
    with pytest.raises(subject.RunCorpusR6BoomFirstAllocationV1Error):
        subject.build_provider_terminal_execution_v1(
            broken, manifest=manifest, manifest_identity=manifest_identity,
            smoke_receipt=smoke, launch_receipt=launch_receipt,
            launch_receipt_identity=launch_receipt_identity,
        )


def test_terminal_reopen_exact_opens_persisted_launch_authority_before_tasks(
    monkeypatch,
):
    manifest = _manifest()
    manifest_identity = _value_identity(manifest["manifest_uri"], manifest)
    smoke = _manifest_smoke_receipt(manifest, manifest_identity)
    claim, claim_identity, receipt, receipt_identity = _launch_authorities(
        manifest, manifest_identity, smoke,
        execution_id="boom-first-execution-abc",
    )
    store = _FakeStore()
    assert store.seed(claim_identity["uri"], claim) == claim_identity
    assert store.seed(receipt_identity["uri"], receipt) == receipt_identity
    forged_receipt_identity = store.seed(
        manifest["output_prefix"] + "authorities/forged-launch-receipt.json",
        receipt,
    )
    provider_proof = {
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "launch_claim_identity": claim_identity,
        "launch_receipt_identity": forged_receipt_identity,
        "launch_receipt_sha256": receipt["launch_receipt_sha256"],
        "execution_id": "boom-first-execution-abc",
        "job_name": subject.FIXED_REUSED_JOB_NAME,
        "job_uid": subject.FIXED_REUSED_JOB_UID,
        "service_account": subject.FIXED_SERVICE_ACCOUNT,
        "project_id": subject.FIXED_PROJECT,
        "region": subject.FIXED_REGION,
    }
    terminal = {
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "provider_terminal_execution": provider_proof,
        "execution_id": "boom-first-execution-abc",
        "task0_smoke_sha256": smoke["smoke_sha256"],
        "task_results": [],
    }
    terminal_identity = store.seed(manifest["terminal_uri"], terminal)
    monkeypatch.setattr(
        subject.science, "validate_terminal_v1", lambda value: value,
    )
    monkeypatch.setattr(
        subject.science, "validate_provider_terminal_execution_v1",
        lambda value: value,
    )
    monkeypatch.setattr(
        subject, "_open_manifest",
        lambda value, store: (manifest, manifest_identity),
    )
    task_reads = []
    monkeypatch.setattr(
        subject, "_open_bound_task_result_v1",
        lambda **kwargs: task_reads.append(True),
    )
    with pytest.raises(
        subject.RunCorpusR6BoomFirstAllocationV1Error,
        match="launch receipt URI differs",
    ):
        subject._reopen_terminal_and_tasks(terminal_identity, store=store)
    assert task_reads == []


def test_manifest_smoke_runs_task0_without_publication(monkeypatch):
    manifest = _manifest()
    manifest_identity = _value_identity(manifest["manifest_uri"], manifest)
    smoke = _manifest_smoke_receipt(manifest, manifest_identity)
    binding = manifest["task_bindings"][0]
    frozen = {
        "source_ordinal": 0,
        "generation_snapshot_sha256": binding["generation_snapshot_sha256"],
        "later_source_identity": manifest["later_source_identity"],
    }
    store = _FakeStore()
    monkeypatch.setenv(subject.BUILD_SOURCE_COMMIT_ENV, manifest["code_commit"])
    monkeypatch.setattr(
        subject, "_open_manifest",
        lambda value, store: (manifest, manifest_identity),
    )
    monkeypatch.setattr(
        subject, "_read_json",
        lambda *args, **kwargs: (frozen, binding["snapshot_identity"]),
    )
    monkeypatch.setattr(
        subject.science, "validate_generation_snapshot_v1", lambda value: value,
    )
    monkeypatch.setattr(
        subject, "_run_score_blind_task_v1", lambda **kwargs: {"task": True},
    )
    monkeypatch.setattr(
        subject, "_smoke_receipt_from_result_v1", lambda **kwargs: smoke,
    )
    retained = subject.smoke_from_request_v1(
        {"manifest_identity": manifest_identity}, store=store
    )
    assert retained == smoke
    assert store.publish_calls == []


def test_manifest_smoke_rejects_wrong_embedded_commit_before_task(monkeypatch):
    manifest = _manifest()
    manifest_identity = _value_identity(manifest["manifest_uri"], manifest)
    task_calls = []
    monkeypatch.setattr(
        subject, "_open_manifest",
        lambda value, store: (manifest, manifest_identity),
    )
    monkeypatch.setenv(subject.BUILD_SOURCE_COMMIT_ENV, "d" * 40)
    monkeypatch.setattr(
        subject, "_run_score_blind_task_v1",
        lambda **kwargs: task_calls.append(True),
    )
    with pytest.raises(
        subject.RunCorpusR6BoomFirstAllocationV1Error,
        match="embedded source commit differs",
    ):
        subject.smoke_from_request_v1(
            {"manifest_identity": manifest_identity}, store=object()
        )
    assert task_calls == []


def test_live_catalog_lease_requires_exact_newline_aware_generation():
    store = _FakeStore()
    raw = _lease_raw()
    identity = store.seed_raw(subject.HISTORICAL_OUTCOME_LEASE_URI, raw)
    body, retained = subject._open_live_outcome_lease_v1(
        expected_identity=identity, catalog_run_id="catalog-run-v1", store=store
    )
    assert retained == identity
    assert body["version"] == "historical-outcome-active-v1"
    store.seed_raw(subject.HISTORICAL_OUTCOME_LEASE_URI, raw[:-1])
    with pytest.raises(subject.RunCorpusR6BoomFirstAllocationV1Error):
        subject._open_live_outcome_lease_v1(
            expected_identity=store.objects[
                subject.HISTORICAL_OUTCOME_LEASE_URI
            ][1],
            catalog_run_id="catalog-run-v1", store=store,
        )


def test_catalog_completion_mismatch_prevents_first_outcome_read(monkeypatch):
    manifest = _manifest()
    terminal = {
        "terminal_sha256": "1" * 64,
        "later_source_identity": manifest["later_source_identity"],
        "normalized_slates": [],
    }
    terminal_identity = _identity("gs://fixture/terminal.json", "1")
    requested_snapshot = _identity("gs://fixture/outcome.json", "2")
    wrong_snapshot = _identity("gs://fixture/wrong-outcome.json", "3")
    lease_identity = _identity(subject.HISTORICAL_OUTCOME_LEASE_URI, "4")
    completion = _catalog_completion(
        snapshot_identity=wrong_snapshot, lease_identity=lease_identity
    )
    store = _FakeStore()
    completion_uri = (
        f"{subject.CATALOG_OUTCOME_ROOT}/{completion['run_id']}/completion.json"
    )
    completion_identity = store.seed(completion_uri, completion)
    monkeypatch.setattr(
        subject, "_reopen_terminal_and_tasks",
        lambda value, store: (terminal, terminal_identity, manifest),
    )
    outcome_reads = []
    monkeypatch.setattr(
        subject.grader, "open_outcome_snapshot_surface_v1",
        lambda **kwargs: outcome_reads.append(True),
    )
    with pytest.raises(subject.RunCorpusR6BoomFirstAllocationV1Error):
        subject.grade_from_request_v1({
            "terminal_identity": terminal_identity,
            "outcome_snapshot_identity": requested_snapshot,
            "catalog_outcome_completion_identity": completion_identity,
            "historical_outcome_lease_identity": lease_identity,
        }, store=store)
    assert outcome_reads == []
    assert store.publish_calls == []


def test_lease_mutation_after_scoring_blocks_grade_publication(monkeypatch):
    manifest = _manifest()
    normalized = [{"slate_id": science.expected_slate_id_v1(i)}
                  for i in range(science.TASK_COUNT)]
    terminal = {
        "terminal_sha256": "1" * 64,
        "later_source_identity": manifest["later_source_identity"],
        "normalized_slates": normalized,
    }
    terminal_identity = _identity("gs://fixture/terminal.json", "1")
    snapshot_identity = _identity("gs://fixture/outcome.json", "2")
    first_raw = _lease_raw()

    class MutatingStore(_FakeStore):
        lease_reads = 0

        def open_known(self, uri, maximum_bytes):
            if uri != subject.HISTORICAL_OUTCOME_LEASE_URI:
                return super().open_known(uri, maximum_bytes)
            self.lease_reads += 1
            raw, identity = self.objects[uri]
            if self.lease_reads == 1:
                return raw, identity
            changed = _lease_raw("catalog-run-v1").replace(
                b"12:00:00", b"12:00:01"
            )
            return changed, {
                **identity, "generation": "2",
                "sha256": sha256(changed).hexdigest(), "bytes": len(changed),
            }

    store = MutatingStore()
    lease_identity = store.seed_raw(
        subject.HISTORICAL_OUTCOME_LEASE_URI, first_raw
    )
    completion = _catalog_completion(
        snapshot_identity=snapshot_identity, lease_identity=lease_identity
    )
    completion_uri = (
        f"{subject.CATALOG_OUTCOME_ROOT}/{completion['run_id']}/completion.json"
    )
    completion_identity = store.seed(completion_uri, completion)
    monkeypatch.setattr(
        subject, "_reopen_terminal_and_tasks",
        lambda value, store: (terminal, terminal_identity, manifest),
    )
    slate_keys = {
        ordinal: (*science.SLATE_KEYS[ordinal], science.expected_slate_id_v1(ordinal))
        for ordinal in range(science.TASK_COUNT)
    }
    monkeypatch.setattr(
        subject.grader, "open_outcome_snapshot_surface_v1",
        lambda **kwargs: ({
            "later_source_freeze_identity": manifest["later_source_identity"],
            "outcome_snapshot_sha256": "9" * 64,
        }, snapshot_identity, {}, slate_keys),
    )
    monkeypatch.setattr(
        subject.grader, "score_normalized_slates_v1", lambda **kwargs: []
    )
    monkeypatch.setattr(
        subject.grader, "aggregate_normalized_slate_grades_v1",
        lambda value: [],
    )
    monkeypatch.setattr(
        subject, "_paired_allocation_summary_v1",
        lambda value: {"paired_summary_sha256": "8" * 64},
    )
    with pytest.raises(subject.RunCorpusR6BoomFirstAllocationV1Error):
        subject.grade_from_request_v1({
            "terminal_identity": terminal_identity,
            "outcome_snapshot_identity": snapshot_identity,
            "catalog_outcome_completion_identity": completion_identity,
            "historical_outcome_lease_identity": lease_identity,
        }, store=store)
    assert store.lease_reads == 2
    assert store.publish_calls == []


def test_cli_is_default_off_before_constructing_cloud_clients(tmp_path, monkeypatch):
    request = tmp_path / "request.json"
    request.write_bytes(json.dumps(
        {"manifest_identity": _identity("gs://fixture/manifest.json", "d")},
        sort_keys=True, separators=(",", ":"),
    ).encode())
    monkeypatch.delenv(subject.SELECTION_ENABLE_ENV, raising=False)
    with pytest.raises(
        subject.RunCorpusR6BoomFirstAllocationV1Error,
        match="requires --execute",
    ):
        subject.main(["collect", "--request", str(request)])


def test_grade_has_a_distinct_enable_gate(tmp_path, monkeypatch):
    request = tmp_path / "request.json"
    request.write_bytes(b"{}")
    monkeypatch.setenv(
        subject.SELECTION_ENABLE_ENV, subject.SELECTION_ENABLE_VALUE
    )
    monkeypatch.delenv(subject.GRADE_ENABLE_ENV, raising=False)
    with pytest.raises(
        subject.RunCorpusR6BoomFirstAllocationV1Error,
        match=subject.GRADE_ENABLE_ENV,
    ):
        subject.main([
            "grade", "--request", str(request.resolve()), "--execute",
        ])


def test_grade_summary_exposes_primary_delta_seasons_and_thresholds():
    grades = []
    for ordinal in range(science.TASK_COUNT):
        metrics = []
        for arm, score in (("control", 176_000_000), ("treatment", 182_000_000)):
            metrics.append({
                "coordinate": {
                    "adapter_id": science.ADAPTER_ID,
                    "arm": arm,
                },
                "selected_weekly_maximum_micro": score + ordinal,
                "population_ceiling_micro": score + 10_000_000 + ordinal,
                "population_ceiling_regret_micro": 10_000_000,
                "thresholds": [{
                    "threshold_dk": threshold,
                    "selected_produced_at_least_one_hit": score >= threshold * 1_000_000,
                    "population_produced_at_least_one_hit": (
                        score + 10_000_000 >= threshold * 1_000_000
                    ),
                } for threshold in (194, 200, 210, 220, 230)],
            })
        grades.append({"metrics": metrics})
    summary = subject._paired_allocation_summary_v1(grades)
    all_54 = summary["aggregates"][0]
    assert all_54["label"] == "all-54"
    assert all_54["paired_mean_delta_micro"] == {
        "numerator": 6_000_000 * 54,
        "denominator": 54,
    }
    assert all_54["treatment_win_count"] == 54
    assert [row["label"] for row in summary["aggregates"]] == [
        "all-54", "2023", "2024", "2025",
    ]
    assert summary["primary_coordinate"] == {
        "model_ensemble": 1, "entry_budget": 80, "tail_line": 194.0,
    }
