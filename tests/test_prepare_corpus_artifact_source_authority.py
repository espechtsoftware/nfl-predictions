from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

from nfl_dfs.research import corpus_artifact_source_authority as authority
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_parametric_batch import TASK_WORLD_SOURCE_ROLES


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_corpus_artifact_source_authority.py"
SALARY_SQL = (
    ROOT
    / "reports"
    / "corpus-parametric-runs"
    / "20260821-corpus-artifact-source-authority-v1"
    / "governance"
    / "salary-player-id-query.sql"
)


@pytest.fixture()
def module() -> ModuleType:
    name = "prepare_corpus_artifact_source_authority_under_test"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    imported = importlib.util.module_from_spec(spec)
    sys.modules[name] = imported
    spec.loader.exec_module(imported)
    return imported


def _base_source_lock(
    module: ModuleType, *, synthetic_artifacts: bool = False,
) -> tuple[bytes, dict[str, object]]:
    receipts: list[dict[str, object]] = []
    for season, week in later.EXPECTED_SLATE_KEYS:
        for seed, _block in enumerate(rw.WORLD_BLOCKS):
            artifact_raw = (
                f"npz-{len(receipts):03d}-{TASK_WORLD_SOURCE_ROLES[seed]}"
            ).encode("ascii")
            artifact_sha = (
                sha256(artifact_raw).hexdigest()
                if synthetic_artifacts
                else sha256(f"{season}-{week}-{seed}".encode("ascii")).hexdigest()
            )
            if (season, week, rw.WORLD_BLOCKS[seed]) == later.REPAIRED_R3_KEY:
                artifact_sha = later.REPAIRED_R3_SHA256
            receipts.append({
                "bytes": len(artifact_raw) if synthetic_artifacts else 11 + seed,
                "candidate_rows": 1,
                "generation": str(100_000 + len(receipts)),
                "panel_run_id": later.SOURCE_PANELS[seed],
                "season": season,
                "seed": seed,
                "sha256": artifact_sha,
                "updated": "2026-08-21T00:00:00+00:00",
                "uri": (
                    "gs://retained-source/"
                    f"{season}/w{week:02d}/{rw.WORLD_BLOCKS[seed]}.npz"
                ),
                "week": week,
            })
    value = {
        "version": later.BASE_SOURCE_VERSION,
        "run_id": later.BASE_SOURCE_RUN_ID,
        "source_panels": list(later.SOURCE_PANELS),
        "slates": len(later.EXPECTED_SLATE_KEYS),
        "artifact_count": len(receipts),
        "artifact_receipts": receipts,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "uses_realized_outcomes": False,
    }
    raw = module.canonical_json_bytes(value)
    identity = {
        "uri": later.BASE_SOURCE_URI,
        "generation": later.BASE_SOURCE_GENERATION,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return raw, identity


def _plan(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, object], bytes, dict[str, object]]:
    repaired_ordinal = later.EXPECTED_ARTIFACT_KEYS.index(later.REPAIRED_R3_KEY)
    repaired_role = TASK_WORLD_SOURCE_ROLES[repaired_ordinal % 5]
    repaired_raw = f"npz-{repaired_ordinal:03d}-{repaired_role}".encode("ascii")
    monkeypatch.setattr(
        later, "REPAIRED_R3_SHA256", sha256(repaired_raw).hexdigest()
    )
    base_raw, base_identity = _base_source_lock(
        module, synthetic_artifacts=True
    )
    monkeypatch.setattr(module, "BASE_SOURCE_OBJECT", base_identity)
    plan = module.build_execution_plan(
        run_id="20260821-artifact-source-test-v1",
        registered_at="2026-08-21T00:00:00+00:00",
        source_snapshot_at="2026-08-21T01:00:00+00:00",
        output_prefix=(
            "gs://dedicated-corpus-authority/"
            "20260821-artifact-source-test-v1/"
        ),
        code_sha="a" * 40,
        image=f"image@sha256:{'b' * 64}",
        job="reused-parked-job",
        base_source_lock_bytes=base_raw,
    )
    return plan, base_raw, base_identity


def _execution_intent(
    module: ModuleType,
    *,
    plan: Mapping[str, object],
    plan_identity: Mapping[str, object],
) -> tuple[dict[str, object], bytes, dict[str, object]]:
    delivery_prefix = str(plan_identity["uri"]).removesuffix(
        "input/publication-plan.json"
    )
    contract_identity = {
        "uri": f"{delivery_prefix}governance/transport-contract.json",
        "generation": "54",
        "sha256": "c" * 64,
        "bytes": 100,
    }
    job = {
        "name": plan["runtime_identity"]["job"],
        "uid": "source-job-uid",
        "generation": "5",
        "observed_generation": "5",
        "spec_sha256": "d" * 64,
    }
    worker_args = module._cloud_worker_base_args(plan_identity)
    body = {
        "schema_version": module.LAUNCH_LEDGER_SCHEMA,
        "created_at_utc": "2026-08-21T00:00:00+00:00",
        "transport_contract": contract_identity,
        "plan_object": dict(plan_identity),
        "run_id": plan["run_id"],
        "job": job,
        "execution_names_before": ["source-prior-execution"],
        "worker_args": worker_args,
        "worker_args_sha256": module.canonical_sha256(worker_args),
        "launch_authority_consumed": True,
        "execution_intent": True,
        "intent_nonce": module.canonical_sha256({
            "transport_contract": contract_identity,
            "plan_object": dict(plan_identity),
            "job": job,
            "run_id": plan["run_id"],
        }),
        "one_execution": True,
        "max_retries": 0,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
    }
    intent = module._self_hash(body, field="launch_ledger_sha256")
    raw = module.canonical_json_bytes(intent)
    identity = module._identity_for_raw(
        f"{delivery_prefix}governance/launch-ledger.json", "56", raw
    )
    return intent, raw, identity


def _query_rows(role: str) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for season, week in later.EXPECTED_SLATE_KEYS:
        player_id = f"player-{season}-{week:02d}"
        if role == "r0_candidates":
            rows.append({
                "panel_run_id": later.R0_PANEL,
                "season": season,
                "week": week,
                "cand_ix": 0,
                "players": [player_id],
                "score_artifact_uri": (
                    f"gs://candidate-scores/{season}/w{week:02d}.npz"
                ),
                "score_artifact_sha256": sha256(
                    f"score-{season}-{week}".encode("ascii")
                ).hexdigest(),
            })
        elif role == "artifact_catalog":
            rows.append({
                "season": season,
                "week": week,
                "id": player_id,
                "pos": "QB",
                "team": "AAA",
                "opp": "BBB",
                "game_id": f"{season}_{week}_AAA_BBB",
                "salary": 5000,
            })
        elif role == "salary_player_ids":
            rows.append({"season": season, "week": week, "id": player_id})
        else:
            raise AssertionError(role)
    return tuple(rows)


def _query_receipt(query_identity: Mapping[str, object]) -> dict[str, object]:
    return {
        "job_id": query_identity["job_id"],
        "location": query_identity["location"],
        "sql_sha256": query_identity["sql_sha256"],
        "parameters_sha256": query_identity["parameters_sha256"],
        "created": "2026-08-21T00:00:01+00:00",
        "started": "2026-08-21T00:00:02+00:00",
        "ended": "2026-08-21T00:00:03+00:00",
        "total_bytes_processed": 1,
        "cache_hit": False,
        "error_result": None,
    }


def _fake_source_freeze() -> tuple[dict[str, object], dict[tuple[str, str], bytes]]:
    objects: dict[tuple[str, str], bytes] = {}
    slates: list[dict[str, object]] = []
    for task_index, (season, week) in enumerate(later.EXPECTED_SLATE_KEYS):
        receipts: list[dict[str, object]] = []
        for role, block in zip(
            TASK_WORLD_SOURCE_ROLES, rw.WORLD_BLOCKS, strict=True
        ):
            ordinal = task_index * 5 + len(receipts)
            raw = f"npz-{ordinal:03d}-{role}".encode("ascii")
            uri = (
                "gs://retained-source/"
                f"{season}/w{week:02d}/{block}.npz"
            )
            generation = str(100_000 + ordinal)
            receipt = {
                "block": block,
                "uri": uri,
                "generation": generation,
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
            receipts.append(receipt)
            objects[(uri, generation)] = raw
        slates.append({
            "season": season,
            "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "artifact_receipts": receipts,
        })
    return {
        "slates": slates,
        "freeze_sha256": "c" * 64,
    }, objects


class _FakeStorage:
    def __init__(
        self,
        module: ModuleType,
        initial: Mapping[tuple[str, str], bytes],
        events: list[str],
    ) -> None:
        self.module = module
        self.objects = dict(initial)
        self.events = events
        self.next_generation = 900_000

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = self.module.normalize_object_identity(
            identity, label="fake read"
        )
        uri = str(normalized["uri"])
        generation = str(normalized["generation"])
        self.events.append(f"read:{uri}")
        raw = self.objects[(uri, generation)]
        self.module._bind_raw(raw, normalized, label="fake read")
        return raw

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if any(existing_uri == uri for existing_uri, _ in self.objects):
            raise self.module.CorpusArtifactSourcePreparationError(
                "fake create-only collision"
            )
        generation = str(self.next_generation)
        self.next_generation += 1
        identity = self.module._identity_for_raw(uri, generation, raw)
        self.objects[(uri, generation)] = raw
        self.events.append(f"publish:{uri}")
        return identity

    def require_absent(self, uris: Sequence[str]) -> None:
        self.events.append("require_absent")
        if any(existing_uri in set(uris) for existing_uri, _ in self.objects):
            raise self.module.CorpusArtifactSourcePreparationError(
                "partial source-authority namespace exists"
            )


class _FakeQueries:
    def __init__(
        self, module: ModuleType, events: list[str], *, reused: bool = False,
    ) -> None:
        self.module = module
        self.events = events
        self.reused = reused

    def require_unused_job_ids(self, job_ids: Sequence[str]) -> None:
        self.events.append("require_unused_job_ids")
        assert len(job_ids) == 3 and len(set(job_ids)) == 3
        if self.reused:
            raise self.module.CorpusArtifactSourcePreparationError(
                "predeclared query job ID already exists"
            )

    def run_query(
        self,
        *,
        sql: str,
        query_identity: Mapping[str, object],
        parameters: Sequence[Mapping[str, object]],
    ) -> object:
        job_id = str(query_identity["job_id"])
        if job_id.endswith("-r0-candidates"):
            role = "r0_candidates"
            assert sql == later.CANDIDATE_SQL
        elif job_id.endswith("-full-catalog"):
            role = "artifact_catalog"
            assert sql == later.CATALOG_SQL
        elif job_id.endswith("-salary-player-ids"):
            role = "salary_player_ids"
            assert sha256(sql.encode("utf-8")).hexdigest() == (
                self.module.SALARY_SQL_SHA256
            )
        else:
            raise AssertionError(job_id)
        assert sum(
            row["name"] == "source_snapshot_at" for row in parameters
        ) == 1
        self.events.append(f"query:{role}")
        return self.module.QueryOutcome(
            rows=_query_rows(role),
            receipt=_query_receipt(query_identity),
        )


def test_fixed_source_and_salary_query_boundaries(module: ModuleType) -> None:
    assert module.BASE_SOURCE_OBJECT == {
        "uri": later.BASE_SOURCE_URI,
        "generation": "1786950155692968",
        "sha256": (
            "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c"
        ),
        "bytes": 1_341_911,
    }
    raw = SALARY_SQL.read_bytes()
    assert sha256(raw).hexdigest() == module.SALARY_SQL_SHA256
    lowered = raw.decode("utf-8").lower()
    assert (
        "`nfl-predictions-503414.nfl_predictions.slate_player_features`"
        in lowered
    )
    assert "for system_time as of @source_snapshot_at" in lowered
    assert "select distinct season, week, id" in lowered
    assert not any(
        fragment in lowered for fragment in module._FORBIDDEN_OUTCOME_FRAGMENTS
    )
    source_text = SCRIPT.read_text(encoding="utf-8")
    assert "list_blobs" not in source_text
    assert "later.build_source_freeze(" in source_text
    assert "authority.verify_artifact_supported_source_authority(" in source_text


def test_plan_is_client_free_and_binds_full_lattice(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, base_raw, identity = _plan(module, monkeypatch)
    source, receipts = module.validate_base_source_lock_bytes(
        base_raw, identity=identity
    )
    assert source["slates"] == 54
    assert len(receipts) == 270
    assert tuple(row["block"] for row in receipts[:5]) == rw.WORLD_BLOCKS
    assert plan["artifact_count"] == 270
    assert plan["artifact_list_allowed"] is False
    assert plan["publication_object_count"] == 9
    assert plan["registration"]["salary_universe_query"][
        "selected_columns"
    ] == ["id", "season", "week"]
    assert len({
        plan["registration"]["source_queries"]["r0_candidates"]["job_id"],
        plan["registration"]["source_queries"]["artifact_catalog"]["job_id"],
        plan["registration"]["salary_universe_query"]["job_id"],
    }) == 3


def test_default_off_gate_precedes_factories_and_plan_read(
    module: ModuleType,
) -> None:
    called: list[str] = []
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="literal --execute",
    ):
        module.execute_authority(
            plan={},
            execute=False,
            environ={module.ENABLE_ENV: "1"},
            storage_factory=lambda: called.append("storage"),
            query_factory=lambda: called.append("query"),
        )
    assert called == []
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match=f"{module.ENABLE_ENV}=1",
    ):
        module.main([
            "execute", "--plan", "/definitely/absent/plan.json", "--execute"
        ])
    assert called == []


def test_base_source_fails_closed_on_outcomes_and_noncanonical_bytes(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw, _identity = _base_source_lock(module)
    value = json.loads(raw)
    value["actual_outcomes_queried"] = True
    bad_raw = module.canonical_json_bytes(value)
    bad_identity = {
        "uri": later.BASE_SOURCE_URI,
        "generation": later.BASE_SOURCE_GENERATION,
        "sha256": sha256(bad_raw).hexdigest(),
        "bytes": len(bad_raw),
    }
    monkeypatch.setattr(module, "BASE_SOURCE_OBJECT", bad_identity)
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="54xR0-R4 lattice differs",
    ):
        module.validate_base_source_lock_bytes(bad_raw)

    newline_raw = raw + b"\n\n"
    newline_identity = {
        "uri": later.BASE_SOURCE_URI,
        "generation": later.BASE_SOURCE_GENERATION,
        "sha256": sha256(newline_raw).hexdigest(),
        "bytes": len(newline_raw),
    }
    monkeypatch.setattr(module, "BASE_SOURCE_OBJECT", newline_identity)
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="not canonical JSON",
    ):
        module.validate_base_source_lock_bytes(newline_raw)


def test_query_capture_binds_exact_job_rows_digest_and_slates(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, _raw, _identity = _plan(module, monkeypatch)
    query_identity = plan["registration"]["salary_universe_query"]
    capture = module.build_query_capture(
        role="salary_player_ids",
        query_identity=query_identity,
        query_outcome=module.QueryOutcome(
            rows=_query_rows("salary_player_ids"),
            receipt=_query_receipt(query_identity),
        ),
        registered_at=str(plan["registered_at"]),
    )
    assert capture["row_count"] == 54
    assert capture["rows_sha256"] == module.canonical_sha256(capture["rows"])
    assert capture["query_receipt"]["job_id"] == query_identity["job_id"]

    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="exact 54 slates",
    ):
        module.normalize_query_rows(
            "salary_player_ids", _query_rows("salary_player_ids")[:-1]
        )
    outcome_row = dict(_query_rows("salary_player_ids")[0])
    outcome_row["actual_points"] = 1
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="fields differ|outcome field",
    ):
        module.normalize_query_rows("salary_player_ids", [outcome_row])
    wrong_receipt = _query_receipt(query_identity)
    wrong_receipt["job_id"] = "different-job-id"
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="differs from pre-query registration",
    ):
        module.build_query_capture(
            role="salary_player_ids",
            query_identity=query_identity,
            query_outcome=module.QueryOutcome(
                rows=_query_rows("salary_player_ids"),
                receipt=wrong_receipt,
            ),
            registered_at=str(plan["registered_at"]),
        )


def test_execute_registers_before_queries_streams_270_and_publishes_terminal(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, base_raw, base_identity = _plan(module, monkeypatch)
    source_freeze, artifact_objects = _fake_source_freeze()
    events: list[str] = []
    initial = {
        (str(base_identity["uri"]), str(base_identity["generation"])): base_raw,
        **artifact_objects,
    }
    storage = _FakeStorage(module, initial, events)
    build_calls: list[Mapping[str, object]] = []

    def fake_build_source_freeze(**kwargs: object) -> Mapping[str, object]:
        build_calls.append(kwargs)
        assert len(kwargs["r0_candidate_rows"]) == 54
        assert len(kwargs["full_catalog_rows"]) == 54
        return source_freeze

    verified: list[object] = []

    def fake_verify(**kwargs: object) -> bytes:
        iterator = kwargs["artifact_bodies"]
        assert iter(iterator) is iterator
        for ordinal in range(270):
            record = next(iterator)
            task_index, role_index = divmod(ordinal, 5)
            assert type(record) is authority.RetainedArtifactBody
            assert record.task_index == task_index
            assert record.role == TASK_WORLD_SOURCE_ROLES[role_index]
            assert record.raw == artifact_objects[
                (str(record.identity["uri"]), str(record.identity["generation"]))
            ]
        with pytest.raises(StopIteration):
            next(iterator)
        verified.append(kwargs)
        return module.canonical_json_bytes({"completion_sha256": "d" * 64})

    monkeypatch.setattr(later, "build_source_freeze", fake_build_source_freeze)
    monkeypatch.setattr(
        authority, "verify_artifact_supported_source_authority", fake_verify
    )
    monkeypatch.setattr(
        authority,
        "validate_completion_bytes",
        lambda raw: module.parse_canonical_json_bytes(
            raw, label="fake pure completion"
        ),
    )

    result = module.execute_authority(
        plan=plan,
        execute=True,
        environ={module.ENABLE_ENV: "1"},
        storage_factory=lambda: (events.append("storage_factory") or storage),
        query_factory=lambda: (
            events.append("query_factory") or _FakeQueries(module, events)
        ),
    )

    registration_publish = next(
        index for index, event in enumerate(events)
        if event.endswith("governance/source-registration.json")
        and event.startswith("publish:")
    )
    registration_reopen = next(
        index for index, event in enumerate(events)
        if event.endswith("governance/source-registration.json")
        and event.startswith("read:")
    )
    query_factory = events.index("query_factory")
    first_query = events.index("query:r0_candidates")
    assert registration_publish < registration_reopen < query_factory < first_query
    artifact_reads = [
        event for event in events if event.startswith("read:gs://retained-source/")
    ]
    assert len(artifact_reads) == 270
    assert artifact_reads[0].endswith("/R0.npz")
    assert artifact_reads[-1].endswith("/R4.npz")
    assert len(build_calls) == len(verified) == 1
    assert result["artifact_count"] == 270
    assert result["artifact_streamed_one_at_a_time"] is True
    assert result["final_object_count"] == 9
    assert result["source_authority_completion_sha256"] == "d" * 64
    assert sum(event.startswith("publish:") for event in events) == 9
    assert events.index("require_absent") < registration_publish
    publication_raw = storage.read(result["publication_completion"])
    terminal = module.validate_publication_completion_bytes(publication_raw)
    assert terminal["task_count"] == 54
    assert terminal["artifact_count"] == 270
    assert terminal["artifact_list_used"] is False
    assert len(terminal["inventory_before_publication"]) == 8

    damaged = dict(terminal)
    damaged.pop("publication_completion_sha256")
    damaged["artifact_list_used"] = True
    damaged = module._self_hash(
        damaged, field="publication_completion_sha256"
    )
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="authority differs",
    ):
        module.validate_publication_completion_bytes(
            module.canonical_json_bytes(damaged)
        )


def test_partial_namespace_and_reused_query_ids_fail_closed(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, base_raw, base_identity = _plan(module, monkeypatch)
    events: list[str] = []
    prefix_claim_uri = str(plan["publication_uris"]["prefix_claim"])
    partial = b"partial"
    initial = {
        (str(base_identity["uri"]), str(base_identity["generation"])): base_raw,
        (prefix_claim_uri, "88"): partial,
    }
    storage = _FakeStorage(module, initial, events)
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="partial source-authority namespace",
    ):
        module.execute_authority(
            plan=plan,
            execute=True,
            environ={module.ENABLE_ENV: "1"},
            storage_factory=lambda: storage,
            query_factory=lambda: (_ for _ in ()).throw(
                AssertionError("query client must not be constructed")
            ),
        )
    assert not any(event.startswith("publish:") for event in events)

    events = []
    storage = _FakeStorage(
        module,
        {(str(base_identity["uri"]), str(base_identity["generation"])): base_raw},
        events,
    )
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="already exists",
    ):
        module.execute_authority(
            plan=plan,
            execute=True,
            environ={module.ENABLE_ENV: "1"},
            storage_factory=lambda: storage,
            query_factory=lambda: (
                events.append("query_factory")
                or _FakeQueries(module, events, reused=True)
            ),
        )
    assert any(
        event.endswith("governance/source-registration.json")
        and event.startswith("publish:")
        for event in events
    )
    assert "require_unused_job_ids" in events
    assert not any(event.startswith("query:") for event in events)


def test_registration_reopen_failure_prevents_query_client(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, base_raw, base_identity = _plan(module, monkeypatch)
    events: list[str] = []

    class TamperedStorage(_FakeStorage):
        def read(self, identity: Mapping[str, object]) -> bytes:
            raw = super().read(identity)
            if str(identity["uri"]).endswith("source-registration.json"):
                return raw + b"tampered"
            return raw

    storage = TamperedStorage(
        module,
        {(str(base_identity["uri"]), str(base_identity["generation"])): base_raw},
        events,
    )
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="traced GET body bytes differ",
    ):
        module.execute_authority(
            plan=plan,
            execute=True,
            environ={module.ENABLE_ENV: "1"},
            storage_factory=lambda: storage,
            query_factory=lambda: (_ for _ in ()).throw(
                AssertionError("query client must not be constructed")
            ),
        )


def test_validate_only_and_parked_construct_no_clients(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    raw, identity = _base_source_lock(module)
    monkeypatch.setattr(module, "BASE_SOURCE_OBJECT", identity)
    monkeypatch.setattr(
        module,
        "GCSStorage",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("GCS client")),
    )
    monkeypatch.setattr(
        module,
        "BigQueryBoundary",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("BQ client")),
    )
    source_path = tmp_path / "source-lock.json"
    source_path.write_bytes(raw)
    assert module.main(["parked"]) == 0
    assert module.main([
        "dry-run",
        "--run-id", "20260821-artifact-source-test-v1",
        "--registered-at-utc", "2026-08-21T00:00:00+00:00",
        "--source-snapshot-at", "2026-08-21T01:00:00+00:00",
        "--output-prefix",
        "gs://dedicated-corpus-authority/20260821-artifact-source-test-v1/",
        "--code-sha", "a" * 40,
        "--image", f"image@sha256:{'b' * 64}",
        "--job", "reused-parked-job",
        "--base-source-lock-file", str(source_path),
    ]) == 0
    output = capsys.readouterr().out
    assert "client_constructed=false" in output
    assert module.PLAN_SCHEMA in output


def test_cloud_worker_gate_precedes_clients_and_binds_task_runtime(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(module.ENABLE_ENV, "1")
    for key in (
        "CLOUD_RUN_TASK_INDEX", "CLOUD_RUN_TASK_COUNT",
        "CLOUD_RUN_TASK_ATTEMPT", "CLOUD_RUN_EXECUTION",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        module,
        "GCSStorage",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("GCS client must not be constructed")
        ),
    )
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="task/execution runtime binding",
    ):
        module.main([
            "cloud-worker",
            "--plan-uri", "gs://delivery/run/plan.json",
            "--plan-generation", "1",
            "--plan-sha256", "a" * 64,
            "--plan-bytes", "1",
            "--intent-uri", "gs://delivery/run/governance/launch-ledger.json",
            "--intent-generation", "2",
            "--intent-sha256", "b" * 64,
            "--intent-bytes", "1",
            "--execute",
        ])


def test_cloud_worker_generation_get_reuses_storage_and_rejects_substitution(
    module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, _base_raw, _base_identity = _plan(module, monkeypatch)
    plan_raw = module.canonical_json_bytes(plan)
    plan_uri = (
        "gs://dedicated-delivery/source-run/input/publication-plan.json"
    )
    identity = module._identity_for_raw(plan_uri, "55", plan_raw)
    _intent, intent_raw, intent_identity = _execution_intent(
        module, plan=plan, plan_identity=identity
    )
    events: list[str] = []

    class PlanStorage:
        def __init__(self, bodies: Mapping[tuple[str, str], bytes]) -> None:
            self.bodies = dict(bodies)

        def read(self, retained: Mapping[str, object]) -> bytes:
            events.append("generation_get")
            raw = self.bodies[(str(retained["uri"]), str(retained["generation"]))]
            module._bind_raw(raw, retained, label="delivered input")
            return raw

        def require_absent(self, _uris: Sequence[str]) -> None:
            raise AssertionError("execute_authority is replaced")

        def publish(self, _uri: str, _raw: bytes) -> Mapping[str, object]:
            raise AssertionError("execute_authority is replaced")

        def list(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("worker must not LIST")

    storage = PlanStorage({
        (str(identity["uri"]), str(identity["generation"])): plan_raw,
        (
            str(intent_identity["uri"]),
            str(intent_identity["generation"]),
        ): intent_raw,
    })
    executed: list[object] = []

    def fake_execute(**kwargs: object) -> dict[str, object]:
        executed.append(kwargs["plan"])
        traced = kwargs["storage_factory"]()
        assert traced._storage is storage
        return {"schema": "fake-source-result/v1"}

    monkeypatch.setattr(module, "execute_authority", fake_execute)
    runtime = {
        module.ENABLE_ENV: "1",
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_EXECUTION": "source-execution-abc",
        "CLOUD_RUN_JOB": plan["runtime_identity"]["job"],
        module.IMAGE_ENV: plan["runtime_identity"]["image"],
        module.CODE_ENV: plan["runtime_identity"]["code_sha"],
    }
    result = module.execute_cloud_worker(
        plan_identity=identity,
        intent_identity=intent_identity,
        execute=True,
        environ=runtime,
        storage_factory=lambda: (events.append("storage_factory") or storage),
        query_factory=lambda: (_ for _ in ()).throw(
            AssertionError("query factory is deferred to execute_authority")
        ),
    )
    assert events == ["storage_factory", "generation_get", "generation_get"]
    assert executed == [plan]
    assert result["delivered_plan_object"] == identity

    substituted = bytearray(plan_raw)
    substituted[-2] = ord("0") if substituted[-2] != ord("0") else ord("1")
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="bytes differ",
    ):
        module.execute_cloud_worker(
            plan_identity=identity,
            intent_identity=intent_identity,
            execute=True,
            environ=runtime,
            storage_factory=lambda: PlanStorage({
                (str(identity["uri"]), str(identity["generation"])): bytes(substituted),
                (
                    str(intent_identity["uri"]),
                    str(intent_identity["generation"]),
                ): intent_raw,
            }),
            query_factory=lambda: None,
        )

    inside_identity = module._identity_for_raw(
        str(plan["output_prefix"]) + "plan.json", "56", plan_raw
    )
    with pytest.raises(
        module.CorpusArtifactSourcePreparationError,
        match="outside the nine-object",
    ):
        module.execute_cloud_worker(
            plan_identity=inside_identity,
            intent_identity=intent_identity,
            execute=True,
            environ=runtime,
            storage_factory=lambda: PlanStorage({
                (
                    str(inside_identity["uri"]),
                    str(inside_identity["generation"]),
                ): plan_raw,
                (
                    str(intent_identity["uri"]),
                    str(intent_identity["generation"]),
                ): intent_raw,
            }),
            query_factory=lambda: None,
        )
