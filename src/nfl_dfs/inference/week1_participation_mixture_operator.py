"""Create-once publication boundary for the Week-1 P_CTRL/P_MIX decision.

The historical participation result changes selection beliefs, not candidate
generation.  This operator therefore starts by exact-reopening the adopted
D800/D400 pair, proves that the live selection used the exact D800 candidate
order and that P_CTRL reproduces the adopted D800 book, then publishes the
outcome-blind snapshot, map, selection, and deterministic rehearsal.  The
terminal root is written last and every source/component is independently
reopened by generation.

Any failure leaves P_CTRL as the paid fallback.  This module does not enter a
contest, read a result, or publish post-lock data.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Final

from . import week1_adopted_pair_operator as pair_operator
from . import week1_participation_mixture as pmix
from .generation_exposure import canonical_sha256
from .prospective_generation_shadow_operator import (
    _assert_created_before,
    _prelock_uri,
    _publish_json,
    _read_json,
    _read_raw,
    _timestamp,
)

PACKAGE_SCHEMA_VERSION: Final = "week1-participation-package/v1"
PUBLICATION_SCHEMA_VERSION: Final = "week1-participation-publication/v1"
PACKAGE_PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/participation/"
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IMPLEMENTATION_ID = re.compile(
    r"nfl-predictions-week1-pmix@[0-9a-f]{40}\Z"
)
_IDENTITY_FIELDS: Final = frozenset({"uri", "generation", "sha256", "bytes"})
_SOURCE_IDENTITY_FIELDS: Final = frozenset({"id", "sha256"})
_PACKAGE_FIELDS: Final = frozenset({
    "schema_version",
    "complete",
    "season",
    "week",
    "draft_group_id",
    "lock_utc",
    "adopted_pair_manifest_identity",
    "adopted_pair_contract_sha256",
    "history_source_identity",
    "raw_snapshot_identity",
    "snapshot_identity",
    "map_identity",
    "selection_identity",
    "rehearsal_identity",
    "implementation_identity",
    "candidate_count",
    "candidate_ids_sha256",
    "candidate_rosters_sha256",
    "paid_policy",
    "fallback_policy",
    "a5_prefixes",
    "outcome_fields_read",
    "package_sha256",
})
_PUBLICATION_FIELDS: Final = frozenset({
    "schema_version",
    "complete",
    "package_identity",
    "snapshot_identity",
    "map_identity",
    "selection_identity",
    "rehearsal_identity",
    "independent_exact_reopen",
    "publication_sha256",
})


class Week1ParticipationMixtureOperatorError(RuntimeError):
    """The live P_MIX publication or exact reopen failed closed."""


def _fail(message: str) -> None:
    raise Week1ParticipationMixtureOperatorError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    identity = _mapping(value, label=label)
    if set(identity) != _IDENTITY_FIELDS:
        _fail(f"{label} identity fields differ")
    try:
        uri = _prelock_uri(identity.get("uri"), label=label)
    except Exception as exc:
        raise Week1ParticipationMixtureOperatorError(
            f"{label} URI is not a pre-lock GCS object"
        ) from exc
    generation = identity.get("generation")
    if type(generation) not in {str, int}:
        _fail(f"{label} generation must be a positive decimal")
    generation_text = str(generation)
    if not generation_text.isdigit() or int(generation_text) < 1:
        _fail(f"{label} generation must be a positive decimal")
    byte_count = identity.get("bytes")
    if type(byte_count) is not int or byte_count < 1:
        _fail(f"{label} byte count must be positive")
    return {
        "uri": uri,
        "generation": generation_text,
        "sha256": _digest(identity.get("sha256"), label=f"{label} SHA-256"),
        "bytes": byte_count,
    }


def _implementation_identity(value: object) -> dict[str, object]:
    identity = _mapping(value, label="P_MIX implementation identity")
    if set(identity) != _SOURCE_IDENTITY_FIELDS:
        _fail("P_MIX implementation identity fields differ")
    source_id = identity.get("id")
    if type(source_id) is not str or _IMPLEMENTATION_ID.fullmatch(source_id) is None:
        _fail("P_MIX implementation ID must bind one full Git commit")
    return {
        "id": source_id,
        "sha256": _digest(
            identity.get("sha256"), label="P_MIX implementation SHA-256"
        ),
    }


def _component_uris(*, run_id: str) -> dict[str, str]:
    if (
        type(run_id) is not str
        or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", run_id)
    ):
        _fail("P_MIX run ID must be a canonical lowercase token")
    root = f"{PACKAGE_PREFIX}{run_id}/"
    return {
        "snapshot": f"{root}snapshot.json",
        "map": f"{root}participation-map.json",
        "selection": f"{root}selection.json",
        "rehearsal": f"{root}rehearsal.json",
        "package": f"{root}package.json",
    }


def _validate_package(value: object) -> dict[str, object]:
    package = _mapping(value, label="Week-1 participation package")
    if set(package) != _PACKAGE_FIELDS:
        _fail("Week-1 participation package fields differ")
    retained_hash = package.pop("package_sha256", None)
    _digest(retained_hash, label="participation package SHA-256")
    if retained_hash != canonical_sha256(package):
        _fail("participation package SHA-256 differs")
    if (
        package.get("schema_version") != PACKAGE_SCHEMA_VERSION
        or package.get("complete") is not True
        or package.get("season") != pmix.SEASON
        or package.get("week") != pmix.WEEK
        or package.get("draft_group_id") != pmix.DRAFT_GROUP_ID
        or package.get("lock_utc") != pmix.LOCK_UTC
        or package.get("candidate_count") != 800
        or package.get("paid_policy") != "P_MIX"
        or package.get("fallback_policy") != "P_CTRL"
        or package.get("a5_prefixes") != list(pmix.A5_PREFIXES)
        or package.get("outcome_fields_read") != []
    ):
        _fail("Week-1 participation package fixed boundary differs")
    for field in (
        "adopted_pair_contract_sha256",
        "candidate_ids_sha256",
        "candidate_rosters_sha256",
    ):
        _digest(package.get(field), label=field)
    for field in (
        "adopted_pair_manifest_identity",
        "history_source_identity",
        "raw_snapshot_identity",
        "snapshot_identity",
        "map_identity",
        "selection_identity",
        "rehearsal_identity",
    ):
        package[field] = _identity(package.get(field), label=field)
    package["implementation_identity"] = _implementation_identity(
        package.get("implementation_identity")
    )
    uris = [
        package[field]["uri"]
        for field in (
            "snapshot_identity", "map_identity", "selection_identity",
            "rehearsal_identity",
        )
    ]
    if len(set(uris)) != 4 or any(not uri.startswith(PACKAGE_PREFIX) for uri in uris):
        _fail("P_MIX component URIs alias or leave the governed prefix")
    package["package_sha256"] = retained_hash
    return package


def validate_week1_participation_package_v1(
    value: object,
) -> dict[str, object]:
    """Validate the self-contained terminal package contract."""

    return _validate_package(value)


def _read_components(
    *, store: pair_operator.ImmutableObjectStore, package: Mapping[str, object]
) -> dict[str, object]:
    components: dict[str, object] = {}
    created: list[datetime] = []
    for name in ("snapshot", "map", "selection", "rehearsal"):
        receipt = _read_json(
            store,
            identity=package[f"{name}_identity"],
            label=f"P_MIX {name}",
        )
        _assert_created_before(receipt, pmix.LOCK_UTC, label=f"P_MIX {name}")
        created.append(_timestamp(receipt["created_at"], label=f"P_MIX {name}"))
        components[name] = receipt["value"]
    components["created_at"] = created
    return components


def read_week1_participation_package_v1(
    *,
    store: pair_operator.ImmutableObjectStore,
    package_identity: Mapping[str, object],
) -> dict[str, object]:
    """Generation-exact reopen of the terminal root and every dependency."""

    expected_identity = _identity(package_identity, label="P_MIX package")
    try:
        root_receipt = _read_json(
            store, identity=expected_identity, label="P_MIX package"
        )
        _assert_created_before(root_receipt, pmix.LOCK_UTC, label="P_MIX package")
        package = _validate_package(root_receipt["value"])
        pair = pair_operator.read_week1_adopted_pair_v1(
            store=store,
            manifest_identity=package["adopted_pair_manifest_identity"],
        )
        components = _read_components(store=store, package=package)
        root_created = _timestamp(root_receipt["created_at"], label="P_MIX package")
        if any(created > root_created for created in components.pop("created_at")):
            _fail("P_MIX terminal package predates a component")
        snapshot_rows = components["snapshot"].get("rows")
        if not isinstance(snapshot_rows, list):
            _fail("P_MIX snapshot rows are absent")
        player_ids = [
            row.get("player_id") for row in snapshot_rows if isinstance(row, Mapping)
        ]
        snapshot = pmix.validate_prelock_snapshot_v1(
            components["snapshot"], player_ids=player_ids
        )
        participation_map = pmix.validate_participation_map_v1(components["map"])
        selection = pmix.validate_participation_selection_v1(
            components["selection"]
        )
        rehearsal = pmix.validate_participation_rehearsal_v1(
            components["rehearsal"]
        )
        raw_snapshot = _read_raw(
            store,
            identity=package["raw_snapshot_identity"],
            label="P_MIX raw snapshot source",
        )
        history = _read_raw(
            store,
            identity=package["history_source_identity"],
            label="P_MIX participation-history source",
        )
        _assert_created_before(raw_snapshot, pmix.LOCK_UTC, label="raw snapshot")
        _assert_created_before(history, pmix.LOCK_UTC, label="participation history")
    except Week1ParticipationMixtureOperatorError:
        raise
    except Exception as exc:
        raise Week1ParticipationMixtureOperatorError(
            "P_MIX package exact reopen failed"
        ) from exc

    manifest = pair["manifest"]
    paid_book = pair["paid_book"]
    paid_candidates = manifest["paid"]["candidate_ids"]
    links_match = (
        package["adopted_pair_contract_sha256"] == manifest["contract_sha256"]
        and package["candidate_ids_sha256"] == canonical_sha256(paid_candidates)
        and package["candidate_ids_sha256"] == selection["candidate_ids_sha256"]
        and package["candidate_rosters_sha256"]
        == selection["candidate_rosters_sha256"]
        and package["raw_snapshot_identity"] == snapshot["raw_artifact"]
        and package["history_source_identity"]["sha256"]
        == participation_map["source_artifact_sha256"]
        and package["snapshot_identity"]["sha256"]
        == canonical_sha256(components["snapshot"])
        and package["map_identity"]["sha256"]
        == canonical_sha256(components["map"])
        and package["selection_identity"]["sha256"]
        == canonical_sha256(components["selection"])
        and package["rehearsal_identity"]["sha256"]
        == canonical_sha256(components["rehearsal"])
        and selection["snapshot_sha256"] == snapshot["snapshot_sha256"]
        and selection["participation_map_sha256"] == participation_map["map_sha256"]
        and rehearsal["selection_receipt_sha256"]
        == selection["selection_receipt_sha256"]
        and rehearsal["snapshot_sha256"] == snapshot["snapshot_sha256"]
        and rehearsal["participation_map_sha256"]
        == participation_map["map_sha256"]
        and selection["P_CTRL"]["ordered_lineup_ids"] == paid_book["roster_ids"]
    )
    if not links_match:
        _fail("P_MIX package dependency or P_CTRL/adopted-book link differs")
    return {
        "package_identity": root_receipt["identity"],
        "package_storage_created_at": root_receipt["created_at"],
        "package": package,
        "adopted_pair": pair,
        "snapshot": snapshot,
        "participation_map": participation_map,
        "selection": selection,
        "rehearsal": rehearsal,
    }


def validate_week1_participation_publication_v1(value: object) -> dict[str, object]:
    """Validate the compact result of a root-last P_MIX publication."""

    receipt = _mapping(value, label="P_MIX publication receipt")
    if set(receipt) != _PUBLICATION_FIELDS:
        _fail("P_MIX publication receipt fields differ")
    retained_hash = receipt.pop("publication_sha256", None)
    _digest(retained_hash, label="P_MIX publication SHA-256")
    if retained_hash != canonical_sha256(receipt):
        _fail("P_MIX publication SHA-256 differs")
    if (
        receipt.get("schema_version") != PUBLICATION_SCHEMA_VERSION
        or receipt.get("complete") is not True
        or receipt.get("independent_exact_reopen") is not True
    ):
        _fail("P_MIX publication fixed claims differ")
    for field in (
        "package_identity", "snapshot_identity", "map_identity",
        "selection_identity", "rehearsal_identity",
    ):
        receipt[field] = _identity(receipt.get(field), label=field)
    receipt["publication_sha256"] = retained_hash
    return receipt


def publish_week1_participation_package_v1(
    *,
    store: pair_operator.ImmutableObjectStore,
    adopted_pair_manifest_identity: Mapping[str, object],
    history_source_identity: Mapping[str, object],
    selection_inputs: Mapping[str, object],
    implementation_identity: Mapping[str, object],
    run_id: str,
    observed_at: str,
) -> dict[str, object]:
    """Build, create-once publish, and independently reopen one live package."""

    uris = _component_uris(run_id=run_id)
    observed = _timestamp(observed_at, label="P_MIX publication observed-at")
    if observed >= _timestamp(pmix.LOCK_UTC, label="Week-1 lock"):
        _fail("P_MIX publication observed-at is at/after lock")
    source_identity = _identity(
        history_source_identity, label="participation-history source"
    )
    implementation = _implementation_identity(implementation_identity)
    try:
        pair = pair_operator.read_week1_adopted_pair_v1(
            store=store,
            manifest_identity=adopted_pair_manifest_identity,
        )
        selection = pmix.build_participation_selection_v1(**selection_inputs)
        rehearsal = pmix.certify_participation_replay_v1(**selection_inputs)
        snapshot = pmix.validate_prelock_snapshot_v1(
            selection_inputs["snapshot"], player_ids=selection_inputs["player_ids"]
        )
        participation_map = pmix.validate_participation_map_v1(
            selection_inputs["participation_map"]
        )
        history = _read_raw(
            store, identity=source_identity, label="participation-history source"
        )
        raw_snapshot = _read_raw(
            store, identity=snapshot["raw_artifact"], label="raw snapshot source"
        )
        _assert_created_before(history, pmix.LOCK_UTC, label="participation history")
        _assert_created_before(raw_snapshot, pmix.LOCK_UTC, label="raw snapshot")
    except Week1ParticipationMixtureOperatorError:
        raise
    except Exception as exc:
        raise Week1ParticipationMixtureOperatorError(
            "P_MIX semantic/source preflight failed"
        ) from exc

    manifest = pair["manifest"]
    paid_candidates = manifest["paid"]["candidate_ids"]
    supplied_candidates = list(selection_inputs.get("lineup_ids", []))
    if len(supplied_candidates) != 800 or supplied_candidates != paid_candidates:
        _fail("P_MIX candidate order differs from the adopted D800 authority")
    if selection["P_CTRL"]["ordered_lineup_ids"] != pair["paid_book"]["roster_ids"]:
        _fail("P_CTRL does not exactly reproduce the adopted D800 paid book")
    if participation_map["source_artifact_sha256"] != source_identity["sha256"]:
        _fail("participation map does not bind the reopened history source")
    if raw_snapshot["identity"] != snapshot["raw_artifact"]:
        _fail("snapshot does not bind the reopened raw provider object")

    try:
        publications = {
            "snapshot": _publish_json(
                store, uri=uris["snapshot"], value=snapshot,
                label="P_MIX snapshot", must_precede=pmix.LOCK_UTC,
            ),
            "map": _publish_json(
                store, uri=uris["map"], value=participation_map,
                label="P_MIX map", must_precede=pmix.LOCK_UTC,
            ),
            "selection": _publish_json(
                store, uri=uris["selection"], value=selection,
                label="P_MIX selection", must_precede=pmix.LOCK_UTC,
            ),
            "rehearsal": _publish_json(
                store, uri=uris["rehearsal"], value=rehearsal,
                label="P_MIX rehearsal", must_precede=pmix.LOCK_UTC,
            ),
        }
        body: dict[str, object] = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "complete": True,
            "season": pmix.SEASON,
            "week": pmix.WEEK,
            "draft_group_id": pmix.DRAFT_GROUP_ID,
            "lock_utc": pmix.LOCK_UTC,
            "adopted_pair_manifest_identity": pair["manifest_identity"],
            "adopted_pair_contract_sha256": manifest["contract_sha256"],
            "history_source_identity": source_identity,
            "raw_snapshot_identity": snapshot["raw_artifact"],
            **{
                f"{name}_identity": publications[name]["identity"]
                for name in ("snapshot", "map", "selection", "rehearsal")
            },
            "implementation_identity": implementation,
            "candidate_count": 800,
            "candidate_ids_sha256": selection["candidate_ids_sha256"],
            "candidate_rosters_sha256": selection["candidate_rosters_sha256"],
            "paid_policy": "P_MIX",
            "fallback_policy": "P_CTRL",
            "a5_prefixes": list(pmix.A5_PREFIXES),
            "outcome_fields_read": [],
        }
        body["package_sha256"] = canonical_sha256(body)
        root = _publish_json(
            store, uri=uris["package"], value=_validate_package(body),
            label="P_MIX terminal package", must_precede=pmix.LOCK_UTC,
        )
        reopened = read_week1_participation_package_v1(
            store=store, package_identity=root["identity"]
        )
    except Week1ParticipationMixtureOperatorError:
        raise
    except Exception as exc:
        raise Week1ParticipationMixtureOperatorError(
            "P_MIX create-once publication/exact reopen failed"
        ) from exc
    if reopened["package"] != body:
        _fail("P_MIX independently reopened terminal package differs")

    result: dict[str, object] = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "complete": True,
        "package_identity": root["identity"],
        **{
            f"{name}_identity": publications[name]["identity"]
            for name in ("snapshot", "map", "selection", "rehearsal")
        },
        "independent_exact_reopen": True,
    }
    result["publication_sha256"] = canonical_sha256(result)
    return validate_week1_participation_publication_v1(result)


__all__ = [
    "PACKAGE_PREFIX",
    "PACKAGE_SCHEMA_VERSION",
    "PUBLICATION_SCHEMA_VERSION",
    "Week1ParticipationMixtureOperatorError",
    "publish_week1_participation_package_v1",
    "read_week1_participation_package_v1",
    "validate_week1_participation_package_v1",
    "validate_week1_participation_publication_v1",
]
