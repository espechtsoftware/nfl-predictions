"""Hermetic adversarial tests for the guarded generic scheduler release."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_legal_scheduler_release_v1 as release
from nfl_dfs.research import corpus_r6_legal_scheduler_v1 as scheduler


class _Store:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.by_uri: dict[str, dict[str, object]] = {}
        self.publishes: list[str] = []
        self.reads: list[str] = []

    @staticmethod
    def _key(identity: object) -> tuple[str, str, str, int]:
        row = dict(identity)  # type: ignore[arg-type]
        return (
            str(row["uri"]),
            str(row["generation"]),
            str(row["sha256"]),
            int(row["bytes"]),
        )

    def add(self, uri: str, raw: bytes, generation: str) -> dict[str, object]:
        identity: dict[str, object] = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.values[self._key(identity)] = raw
        self.by_uri[uri] = identity
        return identity

    def read_exact(self, identity: object) -> bytes:
        key = self._key(identity)
        self.reads.append(key[0])
        return self.values[key]

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.publishes.append(uri)
        existing = self.by_uri.get(uri)
        if existing is not None:
            if self.values[self._key(existing)] != raw:
                raise release.CorpusR6LegalSchedulerReleaseV1Error(
                    "create-once collision"
                )
            return existing
        return self.add(uri, raw, str(100 + len(self.by_uri)))


def _source() -> dict[str, object]:
    positions = (
        "QB",
        "RB",
        "RB",
        "RB",
        "WR",
        "WR",
        "WR",
        "WR",
        "TE",
        "TE",
        "DST",
    )
    players = [
        {
            "player_id": f"p{index:02d}",
            "position": position,
            "team": (
                "T00"
                if index in {4, 6}
                else ("O00" if index == 5 else f"T{index:02d}")
            ),
            "opponent": f"O{index:02d}",
            "game_id": f"G{index:02d}",
            "salary": 5_800 if position != "DST" else 3_000,
        }
        for index, position in enumerate(positions)
    ]
    body = {
        "schema_version": release.SOURCE_SCHEMA,
        "slate_id": "2025-w01",
        "batch_id": "R0-b000",
        "players": players,
        "player_scores_micro": [
            [
                10_000_000 + index * 100_000 + world * 10_000
                for world in range(3)
            ]
            for index in range(len(players))
        ],
        "ordered_world_ids": [
            {"block": "R0", "index": index} for index in range(3)
        ],
    }
    return release.add_self_hash_v1(body, "source_batch_sha256")


def _candidates() -> dict[str, object]:
    body = {
        "schema_version": release.CANDIDATE_SCHEMA,
        "slate_id": "2025-w01",
        "candidate_bank_id": "incumbents-v1",
        "incumbent_rosters": [
            [
                "p00",
                "p01",
                "p02",
                "p04",
                "p05",
                "p06",
                "p07",
                "p08",
                "p10",
            ]
        ],
    }
    return release.add_self_hash_v1(body, "incumbent_bank_sha256")


def _fixture(
    *,
    attempt_id: str = "attempt-1",
    limits: int = 10_000_000,
    proxy_id: str = scheduler.POSITION_SALARY_PROXY_ID,
) -> tuple[_Store, dict[str, object]]:
    store = _Store()
    source_raw = release.canonical_json_bytes_v1(_source())
    candidate_raw = release.canonical_json_bytes_v1(_candidates())
    source_identity = store.add("gs://fixture/source.json", source_raw, "1")
    candidate_identity = store.add(
        "gs://fixture/candidates.json", candidate_raw, "2"
    )
    profile = legal.frozen_policy_profiles()[0]
    producer = scheduler.ProducerIdentity(
        proxy_id=proxy_id,
        code_sha256="1" * 64,
        image_digest="sha256:" + "2" * 64,
    )
    dose = (
        scheduler.DEFAULT_SALARY_POSITION_DOSE
        if proxy_id == scheduler.POSITION_SALARY_PROXY_ID
        else scheduler.DEFAULT_FEASIBLE_CORE_DOSE
    )
    body = {
        "schema_version": release.CONFIGURATION_SCHEMA,
        "configuration_id": "caller-selected-research-configuration-v1",
        "run_id": "run-1",
        "slate_id": "2025-w01",
        "batch_id": "R0-b000",
        "attempt_id": attempt_id,
        "proxy_id": proxy_id,
        "source_identity": source_identity,
        "candidate_identity": candidate_identity,
        "profile_id": profile.parameter_set_id,
        "profile_payload_sha256": release.canonical_sha256_v1(
            profile.as_payload()
        ),
        "dose_sha256": dose.receipt().dose_sha256,
        "producer_identity_claim": producer.as_payload(),
        "work_limits": {field: limits for field in release.WORK_FIELDS},
        "receipt_uri": (
            "gs://fixture/"
            f"{release.GENERIC_OUTPUT_OBJECT_PREFIX}{attempt_id}/receipt.json"
        ),
        "root_uri": (
            "gs://fixture/"
            f"{release.GENERIC_OUTPUT_OBJECT_PREFIX}{attempt_id}/root.json"
        ),
        "terminal": True,
        "caller_asserted_no_outcome_reads": True,
    }
    return store, release.add_self_hash_v1(
        body, "release_configuration_sha256"
    )


def _run(
    store: _Store,
    configuration: dict[str, object],
    ledger: release.InMemoryAtomicRunLedgerV1,
) -> dict[str, object]:
    return release.build_and_publish_release_v1(
        release_configuration=configuration,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
        ledger=ledger,
    )


def _rehash_configuration(value: dict[str, object]) -> dict[str, object]:
    changed = deepcopy(value)
    changed.pop("release_configuration_sha256", None)
    changed["release_configuration_sha256"] = release.canonical_sha256_v1(
        changed
    )
    return changed


def _all_false_authority(value: object) -> None:
    status = dict(value)  # type: ignore[arg-type]
    assert status["authoritative"] is False
    assert status["promotion_authority"] is False
    assert status["adopted_configuration_bound"] is False
    assert status["durable_cas_ledger_verified"] is False
    assert status["trusted_create_once_adapter_verified"] is False
    assert status["runtime_code_image_attested"] is False
    assert status["future_fixed_trusted_adapter_required"] is True


def test_release_is_nonauthoritative_exact_reopened_and_root_last() -> None:
    store, configuration = _fixture()
    ledger = release.InMemoryAtomicRunLedgerV1()
    result = _run(store, configuration, ledger)

    assert store.publishes == [
        configuration["receipt_uri"],
        configuration["root_uri"],
    ]
    assert result["publication_exact_reopen_verified"] is True
    assert result["root"]["schema_version"] == release.ROOT_SCHEMA
    assert result["receipt"]["schema_version"] == release.RECEIPT_SCHEMA
    assert result["root"][
        "receipt_published_and_exact_reopened_before_root"
    ] is True
    _all_false_authority(result["authority_status"])
    _all_false_authority(result["root"]["authority_status"])
    _all_false_authority(result["receipt"]["authority_status"])
    assert result["receipt"]["scheduler_proxy_receipt"]["authority"][
        "authoritative"
    ] is False
    for persisted in (result["root"], result["receipt"]):
        assert persisted["promotion_eligible"] is False
        assert persisted["outcome_freedom_status"] == {
            "caller_asserted_no_outcome_reads": True,
            "caller_assertion_only": True,
            "source_lineage_attested": False,
            "outcome_free_authority": False,
            "promotion_eligible": False,
        }
        assert "no_outcome_reads" not in persisted
    # The publisher return was not trusted on sight: both objects were read by
    # their returned generation/hash/size before the call returned.
    assert store.reads[-2:] == [
        configuration["receipt_uri"],
        configuration["root_uri"],
    ]

    publish_count = len(store.publishes)
    reopened = release.reopen_release_v1(
        result["root_identity"],
        release_configuration=configuration,
        read_exact=store.read_exact,
        ledger=ledger,
    )
    assert len(store.publishes) == publish_count
    assert reopened["root"] == result["root"]
    assert reopened["receipt"] == result["receipt"]
    assert reopened["publication_performed"] is False
    assert reopened["exact_reopen_and_predecessor_replay_verified"] is True
    assert [charge["phase"] for charge in reopened["ledger_charges"]] == [
        "retained-root-read",
        "retained-receipt-read",
        "input",
        "compute",
    ]


@pytest.mark.parametrize(
    "proxy_id",
    [
        scheduler.POSITION_SALARY_PROXY_ID,
        scheduler.FEASIBLE_CORE_PROXY_ID,
    ],
)
def test_reservation_covers_all_input_and_proxy_work(proxy_id: str) -> None:
    store, configuration = _fixture(proxy_id=proxy_id)
    ledger = release.InMemoryAtomicRunLedgerV1()
    result = _run(store, configuration, ledger)
    reservation = result["receipt"]["work_reservation"]
    assert reservation["source_bytes"] == configuration["source_identity"][
        "bytes"
    ]
    assert reservation["candidate_bytes"] == configuration[
        "candidate_identity"
    ]["bytes"]
    assert reservation["player_world_cells"] == (
        release.PLAYER_WORLD_CELL_PASSES_PER_COMPUTE * 11 * 3
    )
    assert reservation["incumbent_roster_audits"] >= 1
    assert reservation["incumbent_player_audits"] >= 9
    if proxy_id == scheduler.POSITION_SALARY_PROXY_ID:
        theta_count = len(
            scheduler.DEFAULT_SALARY_POSITION_DOSE.theta_micro_per_salary_dollar
        )
        assert reservation["theta_evaluations"] == 2 * theta_count * 3
        assert reservation["theta_player_world_cells"] == 2 * theta_count * 11 * 3
        assert reservation["beam_expansions"] == 0
    else:
        dose = scheduler.DEFAULT_FEASIBLE_CORE_DOSE
        assert reservation["theta_player_world_cells"] == 0
        assert reservation["incumbent_roster_audits"] == 9
        assert reservation["incumbent_score_cells"] == 2 * 1 * 3
        assert reservation["combination_candidates"] == (
            2 * dose.max_combination_candidates * 3
        )
        assert reservation["core_candidates"] == (
            2 * dose.max_core_candidates * 3
        )
        assert reservation["beam_expansions"] == (
            2 * dose.max_state_expansions * 3
        )
        expected_witness_audits = (
            2
            * (dose.max_cores * 3 * dose.beam_width + 1)
            * 3
        )
        assert reservation["witness_roster_audits"] == expected_witness_audits
        assert reservation["witness_player_audits"] == (
            expected_witness_audits * 9
        )


def test_create_once_retry_is_byte_stable_but_every_compute_is_charged() -> None:
    store, configuration = _fixture()
    ledger = release.InMemoryAtomicRunLedgerV1()
    first = _run(store, configuration, ledger)
    first_totals = ledger.totals("run-1")
    second = _run(store, configuration, ledger)
    second_totals = ledger.totals("run-1")

    assert first["receipt"] == second["receipt"]
    assert first["root"] == second["root"]
    assert first["receipt_identity"] == second["receipt_identity"]
    assert first["root_identity"] == second["root_identity"]
    assert second_totals == {
        field: first_totals[field] * 2 for field in release.WORK_FIELDS
    }
    assert [
        charge["retry_phase_invocation_ordinal"]
        for charge in second["ledger_charges"]
    ] == [2, 2, 2, 2]
    # Mutable cumulative ledger evidence is intentionally outside persisted
    # deterministic bytes, so a legitimate retry does not collide.
    assert "ledger_charges" not in second["receipt"]


def test_distinct_attempts_share_one_cumulative_run_budget() -> None:
    store, first_configuration = _fixture(attempt_id="attempt-1")
    other_store, second_configuration = _fixture(attempt_id="attempt-2")
    store.values.update(other_store.values)
    store.by_uri.update(
        {
            uri: identity
            for uri, identity in other_store.by_uri.items()
            if uri not in store.by_uri
        }
    )
    ledger = release.InMemoryAtomicRunLedgerV1()
    first = _run(store, first_configuration, ledger)
    first_totals = ledger.totals("run-1")
    _run(store, second_configuration, ledger)
    assert ledger.totals("run-1") == {
        field: first_totals[field] * 2 for field in release.WORK_FIELDS
    }
    assert first["receipt"]["work_reservation"]["publication_write_bytes"] == 0


def test_input_budget_exhausts_before_any_read_compute_or_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, configuration = _fixture(limits=1)
    ledger = release.InMemoryAtomicRunLedgerV1()
    called = False

    def forbidden(**_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("compute must not run")

    monkeypatch.setattr(scheduler, "produce_position_salary_proxy", forbidden)
    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="budget exhausted before input",
    ):
        _run(store, configuration, ledger)
    assert called is False
    assert store.reads == []
    assert store.publishes == []


def test_compute_budget_exhausts_after_charged_reads_but_before_compute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, configuration = _fixture()
    limits = dict(configuration["work_limits"])
    limits.update(
        {
            field: 1
            for field in release.WORK_FIELDS
            if field not in {"source_bytes", "candidate_bytes"}
        }
    )
    changed = deepcopy(configuration)
    changed["work_limits"] = limits
    changed = _rehash_configuration(changed)
    ledger = release.InMemoryAtomicRunLedgerV1()
    called = False

    def forbidden(**_kwargs: object) -> object:
        nonlocal called
        called = True
        raise AssertionError("compute must not run")

    monkeypatch.setattr(scheduler, "produce_position_salary_proxy", forbidden)
    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="budget exhausted before compute",
    ):
        _run(store, changed, ledger)
    assert called is False
    assert store.reads == [
        configuration["source_identity"]["uri"],
        configuration["candidate_identity"]["uri"],
    ]
    assert store.publishes == []
    totals = ledger.totals("run-1")
    assert totals["source_bytes"] > 0
    assert totals["candidate_bytes"] > 0
    assert totals["player_world_cells"] == 0


def test_publication_budget_exhausts_before_publisher_or_reopen() -> None:
    store, configuration = _fixture()
    changed = deepcopy(configuration)
    limits = dict(changed["work_limits"])
    limits["publication_write_bytes"] = 1
    limits["publication_reopen_bytes"] = 1
    changed["work_limits"] = limits
    changed = _rehash_configuration(changed)

    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="budget exhausted before publication-receipt",
    ):
        _run(store, changed, release.InMemoryAtomicRunLedgerV1())
    assert store.publishes == []
    assert store.reads == [
        configuration["source_identity"]["uri"],
        configuration["candidate_identity"]["uri"],
    ]


def test_reopen_read_budget_is_charged_before_retained_root_access() -> None:
    store, configuration = _fixture()
    changed = deepcopy(configuration)
    limits = dict(changed["work_limits"])
    limits["retained_read_bytes"] = 1
    changed["work_limits"] = limits
    changed = _rehash_configuration(changed)
    ledger = release.InMemoryAtomicRunLedgerV1()
    result = _run(store, changed, ledger)
    reads_before = list(store.reads)

    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="budget exhausted before retained-root-read",
    ):
        release.reopen_release_v1(
            result["root_identity"],
            release_configuration=changed,
            read_exact=store.read_exact,
            ledger=ledger,
        )
    assert store.reads == reads_before


def test_generic_release_forbids_privileged_or_unsegregated_output_namespace(
) -> None:
    store, configuration = _fixture()
    changed = deepcopy(configuration)
    changed["receipt_uri"] = "gs://fixture/research/adopted/run/receipt.json"
    changed["root_uri"] = "gs://fixture/research/adopted/run/root.json"
    changed = _rehash_configuration(changed)

    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="fixed non-authoritative research namespace",
    ):
        _run(store, changed, release.InMemoryAtomicRunLedgerV1())
    assert store.reads == []
    assert store.publishes == []


def test_caller_cannot_select_authority_or_inject_a_ledger() -> None:
    store, configuration = _fixture()
    changed = deepcopy(configuration)
    changed["configuration_id"] = "caller-calls-this-adopted"
    changed["producer_identity_claim"]["code_sha256"] = "9" * 64
    changed = _rehash_configuration(changed)
    result = _run(store, changed, release.InMemoryAtomicRunLedgerV1())
    _all_false_authority(result["authority_status"])

    forged = deepcopy(configuration)
    forged["authoritative"] = True
    forged = _rehash_configuration(forged)
    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="fields differ",
    ):
        release.validate_release_configuration_v1(forged)

    class _FabricatedLedger:
        def reserve(self, **_kwargs: object) -> dict[str, object]:
            return {}

    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="fixed process-local ledger",
    ):
        release.build_and_publish_release_v1(
            release_configuration=configuration,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
            ledger=_FabricatedLedger(),  # type: ignore[arg-type]
        )


def test_fabricated_publisher_identity_and_collision_fail_before_root() -> None:
    store, configuration = _fixture()
    ledger = release.InMemoryAtomicRunLedgerV1()

    def fabricated(uri: str, raw: bytes) -> dict[str, object]:
        return {
            "uri": uri,
            "generation": "999",
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="exact read failed",
    ):
        release.build_and_publish_release_v1(
            release_configuration=configuration,
            read_exact=store.read_exact,
            publish_create_once=fabricated,
            ledger=ledger,
        )

    collision_store, collision_configuration = _fixture()
    collision_store.add(
        str(collision_configuration["receipt_uri"]), b"{}", "77"
    )
    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="create-once publication failed",
    ):
        _run(
            collision_store,
            collision_configuration,
            release.InMemoryAtomicRunLedgerV1(),
        )
    assert collision_store.publishes == [collision_configuration["receipt_uri"]]


@pytest.mark.parametrize(
    "mutate, message",
    [
        (
            lambda source: source["ordered_world_ids"].__setitem__(
                1, source["ordered_world_ids"][0]
            ),
            "world schedule",
        ),
        (
            lambda source: source["player_scores_micro"][0].__setitem__(0, 1.5),
            "signed int64",
        ),
        (
            lambda source: source["players"][1].__setitem__(
                "player_id", source["players"][0]["player_id"]
            ),
            "player ids repeat",
        ),
    ],
)
def test_coherently_rehashed_malformed_source_is_rejected(
    mutate, message: str,
) -> None:
    store, configuration = _fixture()
    source = deepcopy(_source())
    mutate(source)
    source.pop("source_batch_sha256")
    source["source_batch_sha256"] = release.canonical_sha256_v1(source)
    raw = release.canonical_json_bytes_v1(source)
    identity = store.add("gs://fixture/malformed-source.json", raw, "41")
    changed = deepcopy(configuration)
    changed["source_identity"] = identity
    changed = _rehash_configuration(changed)
    with pytest.raises(release.CorpusR6LegalSchedulerReleaseV1Error, match=message):
        _run(store, changed, release.InMemoryAtomicRunLedgerV1())


def test_exact_identity_and_retained_authority_tampering_are_rejected() -> None:
    store, configuration = _fixture()
    bad_raw = bytearray(store.read_exact(configuration["source_identity"]))
    bad_raw[-2] = ord("0") if bad_raw[-2] != ord("0") else ord("1")
    store.values[store._key(configuration["source_identity"])] = bytes(bad_raw)
    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="exact bytes differ",
    ):
        _run(store, configuration, release.InMemoryAtomicRunLedgerV1())

    store, configuration = _fixture()
    result = _run(store, configuration, release.InMemoryAtomicRunLedgerV1())
    forged_root = deepcopy(result["root"])
    forged_root["authority_status"]["authoritative"] = True
    forged_root.pop("release_root_sha256")
    forged_root["release_root_sha256"] = release.canonical_sha256_v1(forged_root)
    raw = release.canonical_json_bytes_v1(forged_root)
    forged_identity = store.add(str(configuration["root_uri"]), raw, "500")
    with pytest.raises(
        release.CorpusR6LegalSchedulerReleaseV1Error,
        match="root law differs",
    ):
        release.reopen_release_v1(
            forged_identity,
            release_configuration=configuration,
            read_exact=store.read_exact,
            ledger=release.InMemoryAtomicRunLedgerV1(),
        )
