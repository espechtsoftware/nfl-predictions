from __future__ import annotations

import hashlib
import json

import pytest

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference import prospective_generation_shadow_evaluation as shadow
from nfl_dfs.inference import week1_adopted_pair as adopted
from nfl_dfs.inference import week1_adopted_pair_operator as operator


LOCK_AT = adopted.WEEK1_LOCK_UTC
FROZEN_AT = "2026-09-02T03:00:00+00:00"
SOURCE_CREATED = "2026-09-02T02:00:00+00:00"
OUTPUT_CREATED = "2026-09-02T04:00:00+00:00"
PREFIX = adopted.GOVERNED_ARTIFACT_PREFIX
PAID_URI = f"{PREFIX}D800_DEMAX/book.json"
SHADOW_URI = f"{PREFIX}D400_DEMAX/book.json"
MANIFEST_URI = f"{PREFIX}adopted-pair.json"
POSITIONS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "RB", "DST")
TEAMS = ("AAA", "AAA", "AAA", "BBB", "BBB", "BBB", "CCC", "CCC", "CCC")


class FakeStore:
    def __init__(self, *, publish_created_at: str = OUTPUT_CREATED) -> None:
        self.publish_created_at = publish_created_at
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.next_generation = 1
        self.read_count_by_uri: dict[str, int] = {}
        self.forge_reopen_uri: str | None = None

    def seed_raw(
        self, *, uri: str, raw: bytes, created_at: str = SOURCE_CREATED
    ) -> dict[str, object]:
        generation = str(self.next_generation)
        self.next_generation += 1
        self.objects[(uri, generation)] = (raw, created_at)
        return {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def seed_json(
        self, *, uri: str, value: dict[str, object], created_at: str
    ) -> dict[str, object]:
        return self.seed_raw(
            uri=uri,
            raw=shadow.canonical_json_bytes_v1(value),
            created_at=created_at,
        )

    def publish_create_once(
        self, *, uri: str, raw: bytes, content_type: str
    ) -> dict[str, object]:
        assert content_type == "application/json"
        if any(existing_uri == uri for existing_uri, _generation in self.objects):
            raise operator.Week1AdoptedPairOperatorError(
                f"create-once collision at {uri}"
            )
        generation = str(self.next_generation)
        self.next_generation += 1
        self.objects[(uri, generation)] = (raw, self.publish_created_at)
        return {
            "identity": {
                "uri": uri,
                "generation": generation,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            },
            "created_at": self.publish_created_at,
        }

    def read_exact(self, *, identity: dict[str, object]) -> dict[str, object]:
        uri = str(identity["uri"])
        generation = str(identity["generation"])
        raw, created_at = self.objects[(uri, generation)]
        self.read_count_by_uri[uri] = self.read_count_by_uri.get(uri, 0) + 1
        if self.forge_reopen_uri == uri:
            raw += b" "
        return {
            "identity": dict(identity),
            "created_at": created_at,
            "raw": raw,
        }


def _identity(label: str) -> dict[str, object]:
    return {
        "id": label,
        "sha256": hashlib.sha256(label.encode("ascii")).hexdigest(),
    }


def _player_id(roster: int, slot: int) -> str:
    return f"p{roster:04d}-{slot:02d}"


def _player_bridge() -> list[dict[str, object]]:
    rows = [
        {
            "player_id": _player_id(roster, slot),
            "position": POSITIONS[slot],
            "team": TEAMS[slot],
            "salary": 5_000,
        }
        for roster in range(150)
        for slot in range(9)
    ]
    return sorted(rows, key=lambda row: str(row["player_id"]))


def _lineup(roster: int) -> dict[str, object]:
    player_ids = sorted(_player_id(roster, slot) for slot in range(9))
    return {
        "lineup_id": f"lineup-v1-{canonical_sha256(player_ids)}",
        "player_ids": player_ids,
        "slots": [
            {
                "slot": slot_name,
                "player_id": _player_id(roster, slot),
            }
            for slot, slot_name in enumerate(operator.DK_SLOT_ORDER)
        ],
        # Deliberately below the house $49k floor: DK legality is the only
        # universal validation performed by the operator.
        "salary": 45_000,
    }


def _lineup_id(roster: int) -> str:
    return str(_lineup(roster)["lineup_id"])


def _candidate_id(ordinal: int) -> str:
    if ordinal < 150:
        return _lineup_id(ordinal)
    return f"lineup-v1-{hashlib.sha256(f'candidate-{ordinal}'.encode()).hexdigest()}"


def _books() -> tuple[dict[str, object], dict[str, object]]:
    bridge = _player_bridge()
    bridge_identity = {
        "id": "player-bridge/v1",
        "sha256": canonical_sha256(bridge),
    }
    paid = operator.build_week1_adopted_book_v1(
        arm_id=adopted.PAID_ARM_ID,
        player_bridge_identity=bridge_identity,
        player_bridge=bridge,
        lineups=[_lineup(index) for index in range(80)],
    )
    shadow_book = operator.build_week1_adopted_book_v1(
        arm_id=adopted.SHADOW_ARM_ID,
        player_bridge_identity=bridge_identity,
        player_bridge=bridge,
        lineups=[_lineup(index) for index in range(70, 150)],
    )
    return paid, shadow_book


def _authority() -> dict[str, object]:
    return {
        "season": 2026,
        "week": 1,
        "draft_group_id": "151307",
        "slate_type": "sunday-main",
        "lock_utc": LOCK_AT,
        "frozen_at": FROZEN_AT,
        "outcome_blind": True,
        "outcome_fields_read": [],
    }


def _recipe() -> dict[str, object]:
    return {
        "generation_seed": 2026,
        "selection_seed": 2076,
        "audit_seed": 2126,
        "corrected_hsim_seed": 2326,
        "incumbent_worlds": 10_000,
        "corrected_hsim_worlds": 10_000,
        "decision_worlds": 20_000,
        "law_weighting": "equal-column-mass",
        "selector_recipe": "greedy-expected-weekly-max-v1",
        "tie_break": "first-in-candidate-order-v1",
        "construction_contract": "house_qb2_bb1_floor49_v1",
    }


def _arm_metadata(
    store: FakeStore, *, arm_id: str, purpose: str, lev: int, boom: int
) -> dict[str, object]:
    commit = "a" * 40
    candidate_count = 800 if purpose == "paid" else 400
    candidate_artifact = store.seed_raw(
        uri=f"{PREFIX}{arm_id}/candidates.parquet",
        raw=f"non-json candidate bytes for {arm_id}".encode("ascii"),
    )
    ledger_artifact = store.seed_raw(
        uri=f"{PREFIX}{arm_id}/exposure-ledger.json",
        raw=f'{{ "arm": "{arm_id}", "spacing": "retained" }}'.encode(),
    )
    run_receipt_artifact = store.seed_raw(
        uri=f"{PREFIX}{arm_id}/run-receipt.json",
        raw=f'{{"arm":"{arm_id}","canonical":true}}'.encode(),
    )
    return {
        "arm_id": arm_id,
        "purpose": purpose,
        "config": {
            "lev": lev,
            "boom": boom,
            "selector": "dual_emax",
            "entries": 80,
            "k": 1,
        },
        "slate_identity": _identity("2026-w01-dk-151307"),
        "input_identity": _identity("live-input-root/v1"),
        "player_bridge_identity": {
            "id": "player-bridge/v1",
            "sha256": canonical_sha256(_player_bridge()),
        },
        "generation_bank_identity": _identity(
            "incumbent-generation-seed-2026"
        ),
        "selection_bank_identity": _identity(
            "incumbent-selection-seed-2076"
        ),
        "audit_bank_identity": _identity("incumbent-audit-seed-2126"),
        "hsim_bank_identity": _identity(
            "corrected-hsim-selection-seed-2326"
        ),
        "construction_identity": _identity("house_qb2_bb1_floor49_v1"),
        "generator_source_identity": _identity(
            f"nfl2-live-week@{commit}"
        ),
        "selector_source_identity": _identity(
            f"nfl2-select-expected-max@{commit}"
        ),
        "hsim_source_identity": _identity(f"nfl2-corrected-hsim@{commit}"),
        "candidate_artifact": candidate_artifact,
        "exposure_ledger_artifact": ledger_artifact,
        "run_receipt_artifact": run_receipt_artifact,
        "candidate_ids": [
            _candidate_id(index) for index in range(candidate_count)
        ],
    }


def _arrange() -> tuple[
    FakeStore,
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    store = FakeStore()
    paid_metadata = _arm_metadata(
        store,
        arm_id=adopted.PAID_ARM_ID,
        purpose="paid",
        lev=160,
        boom=640,
    )
    shadow_metadata = _arm_metadata(
        store,
        arm_id=adopted.SHADOW_ARM_ID,
        purpose="shadow",
        lev=80,
        boom=320,
    )
    paid_book, shadow_book = _books()
    return store, paid_metadata, shadow_metadata, paid_book, shadow_book


def _publish(
    store: FakeStore,
    paid_metadata: dict[str, object],
    shadow_metadata: dict[str, object],
    paid_book: dict[str, object],
    shadow_book: dict[str, object],
) -> dict[str, object]:
    return operator.publish_week1_adopted_pair_v1(
        store=store,
        authority=_authority(),
        recipe=_recipe(),
        paid_arm_metadata=paid_metadata,
        shadow_arm_metadata=shadow_metadata,
        paid_book=paid_book,
        shadow_book=shadow_book,
        paid_book_uri=PAID_URI,
        shadow_book_uri=SHADOW_URI,
        manifest_uri=MANIFEST_URI,
        observed_at="2026-09-02T03:30:00+00:00",
    )


def _rehash_book(book: dict[str, object]) -> None:
    body = dict(book)
    body.pop("book_sha256", None)
    book["book_sha256"] = canonical_sha256(body)


def test_book_payload_is_exact_k80_dk_legal_and_house_law_free() -> None:
    paid, _shadow = _books()
    validated = operator.validate_week1_adopted_book_v1(paid)

    assert len(validated["lineups"]) == 80
    assert len(set(validated["roster_ids"])) == 80
    assert validated["slot_order"] == list(operator.DK_SLOT_ORDER)
    assert {row["salary"] for row in validated["lineups"]} == {45_000}
    assert all(
        row["player_ids"] == sorted(row["player_ids"])
        for row in validated["lineups"]
    )
    assert {row["team"] for row in validated["player_bridge"]} == {
        "AAA",
        "BBB",
        "CCC",
    }


@pytest.mark.parametrize(
    "mutation",
    (
        "wrong-slot",
        "duplicate-player",
        "salary",
        "lineup-id",
        "short-book",
        "team-limit",
        "outcome-field",
        "unknown-field",
    ),
)
def test_book_payload_fails_closed_on_semantic_or_schema_drift(
    mutation: str,
) -> None:
    paid, _shadow = _books()
    if mutation == "wrong-slot":
        paid["lineups"][0]["slots"][0]["player_id"] = paid["lineups"][0][
            "slots"
        ][1]["player_id"]
    elif mutation == "duplicate-player":
        paid["lineups"][0]["player_ids"][-1] = paid["lineups"][0][
            "player_ids"
        ][0]
    elif mutation == "salary":
        paid["lineups"][0]["salary"] = 50_001
    elif mutation == "lineup-id":
        paid["lineups"][0]["lineup_id"] = "lineup-v1-" + "f" * 64
    elif mutation == "short-book":
        paid["lineups"].pop()
        paid["roster_ids"].pop()
        paid["roster_ids_sha256"] = canonical_sha256(paid["roster_ids"])
    elif mutation == "team-limit":
        first_lineup_ids = set(paid["lineups"][0]["player_ids"])
        for bridge_row in paid["player_bridge"]:
            if bridge_row["player_id"] in first_lineup_ids:
                bridge_row["team"] = "AAA"
        paid["player_bridge_identity"]["sha256"] = canonical_sha256(
            paid["player_bridge"]
        )
    elif mutation == "outcome-field":
        paid["lineups"][0]["diagnostic"] = {"actual_score": 250.0}
    else:
        paid["lineups"][0]["projection"] = 175.0
    _rehash_book(paid)

    with pytest.raises(operator.Week1AdoptedPairOperatorError):
        operator.validate_week1_adopted_book_v1(paid)


def test_publisher_create_once_uploads_and_independently_reopens_everything() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    receipt = _publish(
        store, paid_metadata, shadow_metadata, paid_book, shadow_book
    )

    assert receipt["complete"] is True
    assert receipt["independent_exact_reopen"] is True
    assert receipt["paid_book_identity"]["uri"] == PAID_URI
    assert receipt["shadow_book_identity"]["uri"] == SHADOW_URI
    assert receipt["manifest_identity"]["uri"] == MANIFEST_URI
    assert operator.validate_week1_adopted_pair_publication_v1(receipt) == receipt
    assert store.read_count_by_uri[PAID_URI] == 1
    assert store.read_count_by_uri[SHADOW_URI] == 1
    assert store.read_count_by_uri[MANIFEST_URI] == 1
    for metadata in (paid_metadata, shadow_metadata):
        assert store.read_count_by_uri[
            metadata["candidate_artifact"]["uri"]
        ] == 2
        assert store.read_count_by_uri[
            metadata["exposure_ledger_artifact"]["uri"]
        ] == 2
        assert store.read_count_by_uri[
            metadata["run_receipt_artifact"]["uri"]
        ] == 2

    reopened = operator.read_week1_adopted_pair_v1(
        store=store, manifest_identity=receipt["manifest_identity"]
    )
    assert reopened["manifest"]["paid"]["roster_ids"] == paid_book[
        "roster_ids"
    ]
    assert reopened["manifest"]["shadow"]["roster_ids"] == shadow_book[
        "roster_ids"
    ]
    assert reopened["manifest"]["roster_overlap_count"] == 10


@pytest.mark.parametrize(
    ("field", "created_at", "message"),
    (
        (
            "manifest_storage_created_at",
            LOCK_AT,
            "created at/after lock",
        ),
        (
            "manifest_storage_created_at",
            "2026-09-02T03:59:59+00:00",
            "manifest predates",
        ),
    ),
)
def test_publication_receipt_rejects_impossible_storage_timing(
    field: str, created_at: str, message: str
) -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    receipt = _publish(
        store, paid_metadata, shadow_metadata, paid_book, shadow_book
    )
    receipt[field] = created_at
    receipt.pop("publication_sha256")
    receipt["publication_sha256"] = canonical_sha256(receipt)

    with pytest.raises(operator.Week1AdoptedPairOperatorError, match=message):
        operator.validate_week1_adopted_pair_publication_v1(receipt)


def test_source_identity_drift_fails_before_any_publication() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    paid_metadata["candidate_artifact"]["sha256"] = "f" * 64

    with pytest.raises(
        operator.Week1AdoptedPairOperatorError, match="exact reopen failed"
    ):
        _publish(store, paid_metadata, shadow_metadata, paid_book, shadow_book)
    assert not any(
        uri in {PAID_URI, SHADOW_URI, MANIFEST_URI}
        for uri, _generation in store.objects
    )


def test_source_created_after_declared_freeze_fails_before_publication() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    source = paid_metadata["run_receipt_artifact"]
    key = (str(source["uri"]), str(source["generation"]))
    raw, _created = store.objects[key]
    store.objects[key] = (raw, "2026-09-02T03:00:01+00:00")

    with pytest.raises(
        operator.Week1AdoptedPairOperatorError, match="exact reopen failed"
    ):
        _publish(store, paid_metadata, shadow_metadata, paid_book, shadow_book)
    assert not any(
        uri in {PAID_URI, SHADOW_URI, MANIFEST_URI}
        for uri, _generation in store.objects
    )


def test_candidate_membership_drift_fails_before_any_publication() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    paid_metadata["candidate_ids"].remove(paid_book["roster_ids"][0])

    with pytest.raises(
        operator.Week1AdoptedPairOperatorError,
        match="contract preflight failed",
    ):
        _publish(store, paid_metadata, shadow_metadata, paid_book, shadow_book)
    assert not any(
        uri in {PAID_URI, SHADOW_URI, MANIFEST_URI}
        for uri, _generation in store.objects
    )


def test_target_source_alias_and_outcome_carrier_fail_before_publication() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    with pytest.raises(operator.Week1AdoptedPairOperatorError, match="aliases"):
        operator.publish_week1_adopted_pair_v1(
            store=store,
            authority=_authority(),
            recipe=_recipe(),
            paid_arm_metadata=paid_metadata,
            shadow_arm_metadata=shadow_metadata,
            paid_book=paid_book,
            shadow_book=shadow_book,
            paid_book_uri=paid_metadata["candidate_artifact"]["uri"],
            shadow_book_uri=SHADOW_URI,
            manifest_uri=MANIFEST_URI,
            observed_at="2026-09-02T03:30:00+00:00",
        )

    with pytest.raises(operator.Week1AdoptedPairOperatorError):
        operator.publish_week1_adopted_pair_v1(
            store=store,
            authority=_authority(),
            recipe=_recipe(),
            paid_arm_metadata=paid_metadata,
            shadow_arm_metadata=shadow_metadata,
            paid_book=paid_book,
            shadow_book=shadow_book,
            paid_book_uri=f"{PREFIX}outcomes/paid-book.json",
            shadow_book_uri=SHADOW_URI,
            manifest_uri=MANIFEST_URI,
            observed_at="2026-09-02T03:30:00+00:00",
        )
    assert not any(
        uri in {PAID_URI, SHADOW_URI, MANIFEST_URI}
        for uri, _generation in store.objects
    )


def test_at_lock_preflight_and_create_once_collision_fail_closed() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    with pytest.raises(operator.Week1AdoptedPairOperatorError, match="at or after"):
        operator.publish_week1_adopted_pair_v1(
            store=store,
            authority=_authority(),
            recipe=_recipe(),
            paid_arm_metadata=paid_metadata,
            shadow_arm_metadata=shadow_metadata,
            paid_book=paid_book,
            shadow_book=shadow_book,
            paid_book_uri=PAID_URI,
            shadow_book_uri=SHADOW_URI,
            manifest_uri=MANIFEST_URI,
            observed_at=LOCK_AT,
        )
    assert not any(
        uri in {PAID_URI, SHADOW_URI, MANIFEST_URI}
        for uri, _generation in store.objects
    )

    _publish(store, paid_metadata, shadow_metadata, paid_book, shadow_book)
    retained = next(
        raw for (uri, _generation), (raw, _created) in store.objects.items()
        if uri == PAID_URI
    )
    with pytest.raises(operator.Week1AdoptedPairOperatorError, match="collision"):
        _publish(store, paid_metadata, shadow_metadata, paid_book, shadow_book)
    assert next(
        raw for (uri, _generation), (raw, _created) in store.objects.items()
        if uri == PAID_URI
    ) == retained


def test_forged_independent_book_reopen_fails_after_create_once_upload() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    store.forge_reopen_uri = PAID_URI
    with pytest.raises(
        operator.Week1AdoptedPairOperatorError, match="exact reopen failed"
    ):
        _publish(store, paid_metadata, shadow_metadata, paid_book, shadow_book)


def test_reader_rejects_manifest_membership_not_present_in_exact_book() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    receipt = _publish(
        store, paid_metadata, shadow_metadata, paid_book, shadow_book
    )
    original_identity = receipt["manifest_identity"]
    raw, _created = store.objects[
        (str(original_identity["uri"]), str(original_identity["generation"]))
    ]
    manifest = json.loads(raw)
    manifest["paid"]["roster_ids"][0] = paid_metadata["candidate_ids"][200]
    manifest["roster_overlap_count"] = len(
        set(manifest["paid"]["roster_ids"])
        & set(manifest["shadow"]["roster_ids"])
    )
    manifest.pop("contract_sha256")
    manifest["contract_sha256"] = canonical_sha256(manifest)
    forged_identity = store.seed_json(
        uri=f"{PREFIX}forged-adopted-pair.json",
        value=manifest,
        created_at=OUTPUT_CREATED,
    )

    with pytest.raises(
        operator.Week1AdoptedPairOperatorError,
        match="membership/bridge differs",
    ):
        operator.read_week1_adopted_pair_v1(
            store=store, manifest_identity=forged_identity
        )


def test_reader_reopens_candidate_and_ledger_sources_on_every_read() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    receipt = _publish(
        store, paid_metadata, shadow_metadata, paid_book, shadow_book
    )
    store.forge_reopen_uri = paid_metadata["exposure_ledger_artifact"]["uri"]

    with pytest.raises(
        operator.Week1AdoptedPairOperatorError, match="exact reopen failed"
    ):
        operator.read_week1_adopted_pair_v1(
            store=store, manifest_identity=receipt["manifest_identity"]
        )


def test_reader_rejects_manifest_that_predates_a_bound_book() -> None:
    store, paid_metadata, shadow_metadata, paid_book, shadow_book = _arrange()
    receipt = _publish(
        store, paid_metadata, shadow_metadata, paid_book, shadow_book
    )
    manifest_identity = receipt["manifest_identity"]
    key = (
        str(manifest_identity["uri"]),
        str(manifest_identity["generation"]),
    )
    raw, _created_at = store.objects[key]
    store.objects[key] = (raw, "2026-09-02T03:59:59+00:00")

    with pytest.raises(
        operator.Week1AdoptedPairOperatorError, match="predates a bound book"
    ):
        operator.read_week1_adopted_pair_v1(
            store=store, manifest_identity=manifest_identity
        )
