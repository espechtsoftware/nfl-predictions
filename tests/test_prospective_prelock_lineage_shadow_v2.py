from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import combinations, islice

import numpy as np
import pandas as pd
import pytest
from google.api_core.exceptions import NotFound, PreconditionFailed

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.config import settings
from nfl_dfs.inference import prospective_prelock_lineage_shadow_v2 as shadow_v2
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books
from nfl_dfs.inference.prelock_candidate_lineage_v1 import canonical_sha256
from nfl_dfs.inference.prelock_lineage_runtime_v2 import SEED_LABELS
from nfl_dfs.inference.prelock_model_artifact_authority_v1 import (
    MODEL_ARTIFACT_MANIFEST_SCHEMA,
)
from nfl_dfs.inference.prospective_prelock_lineage_shadow_v2 import (
    OBJECT_NAMES,
    GcsClosedObjectStore,
    ProspectivePrelockLineageShadowV2Error,
    build_execution_receipt_v1,
    run_prelock_lineage_shadow_v2,
)
from nfl_dfs.models.components import COMPONENT_NAMES
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries

LOCK = datetime(2026, 9, 13, 17, 0, tzinfo=UTC)
RUN_ID = "week1-lineage-publication-001"
PREFIX = f"prelock-lineage-v1/2026/week-01/{RUN_ID}"
MODEL_WEEK = "2026-W36"


@pytest.fixture(autouse=True)
def _clean_source_fixture(monkeypatch) -> None:
    monkeypatch.setattr(
        shadow_v2,
        "_validate_runtime_source_binding_v1",
        lambda *args, **kwargs: "git-global-clean-checkout",
    )


def _model_manifest() -> dict[str, object]:
    model_sets = []
    for purpose, variant in (
        ("candidate-projection", "tail_k1"),
        ("role-belief", "tail_k1_role"),
    ):
        components = []
        for component in COMPONENT_NAMES:
            label = f"comp_{component}__{variant}"
            artifacts = []
            for ordinal, name in enumerate(("meta.json", "model.txt")):
                payload = f"{variant}/{component}/{name}".encode()
                artifacts.append(
                    {
                        "name": name,
                        "identity": {
                            "uri": (
                                f"gs://{settings.gcs_bucket}/"
                                f"{settings.model_registry_prefix}/pooled/"
                                f"{label}/{MODEL_WEEK}/{name}"
                            ),
                            "generation": str(1_000 + len(model_sets) * 100 + ordinal),
                            "sha256": __import__("hashlib").sha256(payload).hexdigest(),
                            "bytes": len(payload),
                            "time_created_utc": "2026-09-13T15:00:00.500000Z",
                        },
                    }
                )
            components.append(
                {
                    "component": component,
                    "registry_label": label,
                    "artifacts": artifacts,
                }
            )
        model_sets.append(
            {
                "purpose": purpose,
                "variant": variant,
                "iso_week": MODEL_WEEK,
                "model_version": f"pooled/components__{variant}/{MODEL_WEEK}",
                "components": components,
            }
        )
    body: dict[str, object] = {
        "schema_version": MODEL_ARTIFACT_MANIFEST_SCHEMA,
        "bucket": settings.gcs_bucket,
        "registry_prefix": settings.model_registry_prefix,
        "scope": "pooled",
        "expected_member_count": 1,
        "model_sets": model_sets,
        "frozen_before_generation": True,
        "provider_generations_required_unchanged_after_generation": True,
        "read_only": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["manifest_sha256"] = canonical_sha256(body)
    return body


class _ModelAuthority:
    def __init__(self) -> None:
        self.freeze_calls = 0
        self.reopen_calls = 0
        self.manifest = _model_manifest()

    def freeze(self, **kwargs):
        self.freeze_calls += 1
        assert kwargs["purpose_variants"] == {
            "candidate-projection": "tail_k1",
            "role-belief": "tail_k1_role",
        }
        assert kwargs["expected_member_count"] == 1
        assert kwargs["must_precede"] == LOCK
        return self.manifest

    def reopen_exact(self, manifest):
        self.reopen_calls += 1
        assert manifest == self.manifest
        return self.manifest


class _SalaryStore:
    def __init__(self) -> None:
        self.calls = 0
        self.frame = pd.DataFrame(
            [
                {
                    "pulled_at": pd.Timestamp("2026-09-13T12:00:00Z"),
                    "draft_group_id": 123,
                    "dk_player_id": player_id,
                    "dk_draftable_id": 10_000 + player_id,
                    "display_name": f"P{player_id}",
                    "team_abbr": f"T{player_id % 6}",
                    "position": "WR",
                    "salary": 5_000,
                    "game_start": pd.Timestamp(LOCK),
                    "status": "None",
                }
                for player_id in range(30)
            ]
        )

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        self.calls += 1
        if self.calls > 1:
            raise AssertionError("salary authority was read more than once")
        assert draft_group_id == 123
        return self.frame.copy(deep=True)


class _ClosedStore:
    def __init__(self, *, fail_after: str | None = None) -> None:
        self.bucket_name = settings.gcs_bucket
        self.prefix = PREFIX
        self.allowed_names = frozenset(OBJECT_NAMES.values())
        self.objects: dict[str, tuple[bytes, dict[str, object]]] = {}
        self.create_attempts: list[str] = []
        self._generation = 100
        self._created = datetime(2026, 9, 13, 16, 30, 0, 500_000, tzinfo=UTC)
        self.fail_after = fail_after
        self._failed = False

    def try_reopen(self, object_name: str):
        return self.objects.get(object_name)

    def create_or_reopen(
        self,
        object_name: str,
        payload: bytes,
        *,
        content_type: str,
        must_precede: datetime,
    ) -> dict[str, object]:
        del content_type
        assert object_name in self.allowed_names
        assert must_precede == LOCK
        self.create_attempts.append(object_name)
        existing = self.objects.get(object_name)
        if existing is not None:
            if existing[0] != payload:
                raise ProspectivePrelockLineageShadowV2Error("create-once bytes differ")
            return dict(existing[1])
        self._generation += 1
        identity = {
            "uri": f"gs://{self.bucket_name}/{self.prefix}/{object_name}",
            "generation": str(self._generation),
            "sha256": __import__("hashlib").sha256(payload).hexdigest(),
            "bytes": len(payload),
            "time_created_utc": self._created.isoformat(
                timespec="microseconds"
            ).replace("+00:00", "Z"),
        }
        self._created += timedelta(microseconds=100_000)
        self.objects[object_name] = (bytes(payload), identity)
        if object_name == self.fail_after and not self._failed:
            self._failed = True
            raise RuntimeError(f"simulated lost response after {object_name}")
        return dict(identity)

    def reopen_exact(self, object_name: str, identity):
        payload, observed = self.objects[object_name]
        if observed != dict(identity):
            raise ProspectivePrelockLineageShadowV2Error(
                "exact provider identity differs"
            )
        return payload


def _player(player_id: int) -> dict[str, object]:
    return {
        "id": player_id,
        "name": f"P{player_id}",
        "pos": "WR",
        "team": f"T{player_id % 6}",
        "opp": f"T{(player_id + 1) % 6}",
        "game_id": f"G{player_id % 3}",
        "salary": 5_000,
        "proj": 20.0,
    }


def _native_books() -> dict[str, CandidateBatch]:
    player_ids = tuple(range(30))
    player_rows = tuple(_player(player_id) for player_id in player_ids)
    roster_grid = list(islice(combinations(player_ids, 9), 180))
    books: dict[str, CandidateBatch] = {}
    for seed_index, label in enumerate(SEED_LABELS):
        rosters = roster_grid[seed_index * 20 : seed_index * 20 + 80]
        rng = np.random.default_rng(8_000 + seed_index)
        draws = rng.normal(20.0, 7.0, size=(len(player_ids), 5)).astype(np.float32)
        candidates = tuple(
            Lineup([player_rows[player_id] for player_id in roster], tag="boom")
            for roster in rosters
        )
        totals = np.stack(
            [draws[list(lineup.ids)].sum(axis=0) for lineup in candidates]
        ).astype(np.float32)
        ledger = SolveExposureLedger(source_label=label)
        for ordinal, roster in enumerate(rosters):
            ledger.record(
                family="boom",
                requested_ordinal=ordinal,
                world_id=ordinal,
                status="new",
                roster_ids=roster,
            )
        books[label] = CandidateBatch(
            candidates=candidates,
            candidate_totals=totals,
            player_ids=player_ids,
            player_rows=player_rows,
            row_draws=draws,
            all_tags={lineup.ids: ("boom",) for lineup in candidates},
            metadata={
                "generation_exposure_ledger": ledger.finalize(
                    expected_requests_by_family={"boom": 80}
                ),
                "model_version": f"pooled/components__tail_k1/{MODEL_WEEK}",
                "role_model_version": (f"pooled/components__tail_k1_role/{MODEL_WEEK}"),
                "candidate_input_receipt": {
                    "sha256": "1" * 64,
                    "rows": 30,
                    "columns": ["id"],
                },
                "role_candidate_input_receipt": {
                    "sha256": "2" * 64,
                    "rows": 30,
                    "columns": ["id"],
                },
            },
        )
    return books


class _Build:
    def __init__(self) -> None:
        self.calls = 0
        self.kwargs: dict[str, object] = {}
        self.model_authority = _ModelAuthority()

    def __call__(self, season: int, week: int, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        assert (season, week) == (2026, 1)
        books = _native_books()
        transform = kwargs["_native_candidate_transform"]
        for label in SEED_LABELS:
            assert transform(label, books[label]) is books[label]
        combined = combine_cbwu_books(books, SEED_LABELS, expected_worlds_per_book=5)
        kwargs["_candidate_capture"](combined)
        selected = select_tail_entries(
            combined.candidate_totals,
            kwargs["n_entries"],
            kwargs["tail_line"],
            env=kwargs["policy_env"],
        )
        return [combined.candidates[index] for index in selected]


@pytest.fixture(scope="module")
def execution_receipt() -> dict[str, object]:
    return build_execution_receipt_v1(
        image_digest="sha256:" + "a" * 64,
        source_commit="b" * 40,
    )


def _run(
    salary_store: _SalaryStore,
    object_store: _ClosedStore,
    builder: _Build,
    execution_receipt: dict[str, object],
    *,
    now: datetime,
):
    return run_prelock_lineage_shadow_v2(
        store=salary_store,
        object_store=object_store,
        run_id=RUN_ID,
        season=2026,
        week=1,
        draft_group_id=123,
        expected_lock_at=LOCK,
        execution_receipt=execution_receipt,
        model_artifact_authority=builder.model_authority,
        now_factory=lambda: now,
        build_lineups_fn=builder,
    )


def test_subsecond_provider_time_root_last_and_real_clock_resume(
    execution_receipt,
) -> None:
    salary_store = _SalaryStore()
    object_store = _ClosedStore()
    builder = _Build()

    first = _run(
        salary_store,
        object_store,
        builder,
        execution_receipt,
        now=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
    )
    assert first["complete"] is True
    assert first["generation_performed"] is True
    assert first["returned_book_parity_observed"] is True
    assert set(object_store.objects) == set(OBJECT_NAMES.values())
    assert object_store.create_attempts[-1] == OBJECT_NAMES["final-manifest"]
    assert salary_store.calls == 1
    assert builder.calls == 1
    assert builder.model_authority.freeze_calls == 1
    assert builder.model_authority.reopen_calls == 1
    assert builder.kwargs["_log_ownership_shadow"] is False
    assert builder.kwargs["cand_log_table"] == ""

    second = _run(
        salary_store,
        object_store,
        builder,
        execution_receipt,
        now=datetime(2026, 9, 13, 16, 45, 37, tzinfo=UTC),
    )
    assert second["complete"] is True
    assert second["resumed"] is True
    assert second["generation_performed"] is False
    assert second["final_manifest"] == first["final_manifest"]
    assert salary_store.calls == 1
    assert builder.calls == 1
    assert builder.model_authority.freeze_calls == 1
    assert builder.model_authority.reopen_calls == 1

    final_bytes = object_store.objects[OBJECT_NAMES["final-manifest"]][0]
    final = __import__("json").loads(final_bytes)
    assert final["projection_created_at_utc"] == "2026-09-13T16:30:01Z"
    assert final["root_is_fifth_object"] is True
    assert final["predecessor_object_count"] == 4


@pytest.mark.parametrize("failed_name", list(OBJECT_NAMES.values()))
def test_retry_after_every_publication_boundary_never_regenerates(
    failed_name: str, execution_receipt
) -> None:
    salary_store = _SalaryStore()
    object_store = _ClosedStore(fail_after=failed_name)
    builder = _Build()

    with pytest.raises(RuntimeError, match="simulated lost response"):
        _run(
            salary_store,
            object_store,
            builder,
            execution_receipt,
            now=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        )
    assert OBJECT_NAMES["capture-authority"] in object_store.objects
    assert builder.calls == 1
    assert salary_store.calls == 1
    assert builder.model_authority.freeze_calls == 1
    assert builder.model_authority.reopen_calls == 1

    completed = _run(
        salary_store,
        object_store,
        builder,
        execution_receipt,
        now=datetime(2026, 9, 13, 16, 50, 59, tzinfo=UTC),
    )
    assert completed["complete"] is True
    assert completed["generation_performed"] is False
    assert builder.calls == 1
    assert salary_store.calls == 1
    assert builder.model_authority.freeze_calls == 1
    assert builder.model_authority.reopen_calls == 1
    assert set(object_store.objects) == set(OBJECT_NAMES.values())


def test_partial_resume_rejects_changed_runtime_provenance_before_writing(
    monkeypatch,
    execution_receipt,
) -> None:
    modes = iter(
        (
            "git-global-clean-checkout",
            "immutable-image-embedded-revision",
        )
    )
    source_gate_calls = 0

    def changed_source_gate(*args, **kwargs):
        nonlocal source_gate_calls
        del args, kwargs
        source_gate_calls += 1
        return next(modes)

    monkeypatch.setattr(
        shadow_v2,
        "_validate_runtime_source_binding_v1",
        changed_source_gate,
    )
    salary_store = _SalaryStore()
    object_store = _ClosedStore(fail_after=OBJECT_NAMES["capture-authority"])
    builder = _Build()

    with pytest.raises(RuntimeError, match="simulated lost response"):
        _run(
            salary_store,
            object_store,
            builder,
            execution_receipt,
            now=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        )
    attempts = list(object_store.create_attempts)
    assert attempts == [OBJECT_NAMES["capture-authority"]]

    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="retry runtime provenance differs",
    ):
        _run(
            salary_store,
            object_store,
            builder,
            execution_receipt,
            now=datetime(2026, 9, 13, 16, 45, tzinfo=UTC),
        )

    assert source_gate_calls == 2
    assert object_store.create_attempts == attempts
    assert set(object_store.objects) == {OBJECT_NAMES["capture-authority"]}
    assert builder.calls == 1


def test_partial_resume_rejects_changed_image_receipt_before_writing(
    execution_receipt,
) -> None:
    salary_store = _SalaryStore()
    object_store = _ClosedStore(fail_after=OBJECT_NAMES["capture-authority"])
    builder = _Build()

    with pytest.raises(RuntimeError, match="simulated lost response"):
        _run(
            salary_store,
            object_store,
            builder,
            execution_receipt,
            now=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        )
    attempts = list(object_store.create_attempts)
    changed_receipt = build_execution_receipt_v1(
        image_digest="sha256:" + "c" * 64,
        source_commit=str(execution_receipt["source_commit"]),
    )

    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="retry execution receipt differs",
    ):
        _run(
            salary_store,
            object_store,
            builder,
            changed_receipt,
            now=datetime(2026, 9, 13, 16, 45, tzinfo=UTC),
        )

    assert object_store.create_attempts == attempts
    assert set(object_store.objects) == {OBJECT_NAMES["capture-authority"]}
    assert builder.calls == 1


def test_complete_root_can_be_reopened_after_lock_without_writes(
    execution_receipt,
) -> None:
    salary_store = _SalaryStore()
    object_store = _ClosedStore()
    builder = _Build()
    first = _run(
        salary_store,
        object_store,
        builder,
        execution_receipt,
        now=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
    )
    attempts = list(object_store.create_attempts)

    reopened = _run(
        salary_store,
        object_store,
        builder,
        execution_receipt,
        now=datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert reopened["final_manifest_sha256"] == first["final_manifest_sha256"]
    assert object_store.create_attempts == attempts
    assert salary_store.calls == 1
    assert builder.calls == 1


def test_closed_store_boundary_rejects_arbitrary_bucket(execution_receipt) -> None:
    salary_store = _SalaryStore()
    object_store = _ClosedStore()
    object_store.bucket_name = "operator-chosen-bucket"

    with pytest.raises(ProspectivePrelockLineageShadowV2Error, match="fixed bucket"):
        _run(
            salary_store,
            object_store,
            _Build(),
            execution_receipt,
            now=datetime(2026, 9, 13, 16, 0, tzinfo=UTC),
        )


def test_execution_receipt_is_bound_to_image_solver_and_compute(
    execution_receipt,
) -> None:
    assert execution_receipt["image_digest"] == "sha256:" + "a" * 64
    assert execution_receipt["image_reference_is_digest"] is True
    assert execution_receipt["provider_execution_identity_verified"] is False
    assert execution_receipt["provider_resource_envelope_verified"] is False
    assert execution_receipt["execution_authority"] is False
    assert len(execution_receipt["solver"]["binary_sha256"]) == 64
    assert execution_receipt["compute_envelope"]["cpu_count"] >= 1
    assert execution_receipt["compute_envelope"]["memory_bytes"] >= 1
    assert execution_receipt["receipt_sha256"] == canonical_sha256(
        {
            key: value
            for key, value in execution_receipt.items()
            if key != "receipt_sha256"
        }
    )

    zero_cpu = deepcopy(execution_receipt)
    zero_cpu["compute_envelope"]["cpu_count"] = 0
    zero_cpu["receipt_sha256"] = canonical_sha256(
        {key: value for key, value in zero_cpu.items() if key != "receipt_sha256"}
    )
    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="compute identity is incomplete",
    ):
        shadow_v2.validate_execution_receipt_v1(zero_cpu)


class _GcsBlob:
    def __init__(self, bucket: _GcsBucket, name: str) -> None:
        self._bucket = bucket
        self.name = name
        self.generation: int | None = None
        self.time_created: datetime | None = None
        self.upload_preconditions: list[int] = []
        self.download_preconditions: list[int] = []

    def reload(self) -> None:
        record = self._bucket.objects.get(self.name)
        if record is None:
            raise NotFound("absent")
        self.generation = int(record[1])
        self.time_created = record[2]

    def upload_from_string(
        self,
        payload: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        del content_type
        self.upload_preconditions.append(if_generation_match)
        if if_generation_match != 0:
            raise AssertionError("write was not create-only")
        if self.name in self._bucket.objects:
            raise PreconditionFailed("simulated create race")
        self._bucket.next_generation += 1
        self._bucket.objects[self.name] = (
            bytes(payload),
            self._bucket.next_generation,
            datetime(2026, 9, 13, 16, 30, 0, 500_000, tzinfo=UTC),
        )

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        self.download_preconditions.append(if_generation_match)
        record = self._bucket.objects[self.name]
        if int(record[1]) != if_generation_match:
            raise PreconditionFailed("generation moved")
        return bytes(record[0])


class _GcsBucket:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, int, datetime]] = {}
        self.next_generation = 900
        self.blobs: dict[str, _GcsBlob] = {}

    def blob(self, name: str) -> _GcsBlob:
        return self.blobs.setdefault(name, _GcsBlob(self, name))


class _GcsClient:
    def __init__(self) -> None:
        self.bucket_object = _GcsBucket()

    def bucket(self, name: str) -> _GcsBucket:
        assert name == settings.gcs_bucket
        return self.bucket_object


def test_gcs_create_race_reopens_exact_generation_and_rejects_other_bytes() -> None:
    client = _GcsClient()
    store = GcsClosedObjectStore(client, prefix=PREFIX)
    object_name = OBJECT_NAMES["selector-matrix"]
    provider_name = f"{PREFIX}/{object_name}"
    payload = b"immutable selector matrix"
    client.bucket_object.objects[provider_name] = (
        payload,
        777,
        datetime(2026, 9, 13, 16, 30, 0, 500_000, tzinfo=UTC),
    )

    identity = store.create_or_reopen(
        object_name,
        payload,
        content_type="application/octet-stream",
        must_precede=LOCK,
    )
    blob = client.bucket_object.blobs[provider_name]
    assert blob.upload_preconditions == [0]
    assert blob.download_preconditions == [777]
    assert identity["generation"] == "777"
    assert identity["time_created_utc"].endswith(".500000Z")

    with pytest.raises(
        ProspectivePrelockLineageShadowV2Error,
        match="different bytes",
    ):
        store.create_or_reopen(
            object_name,
            b"different matrix",
            content_type="application/octet-stream",
            must_precede=LOCK,
        )
