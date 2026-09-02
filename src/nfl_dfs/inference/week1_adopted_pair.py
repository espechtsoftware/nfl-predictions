"""Immutable Week-1 authority for the entered D800 and shadow D400 books.

This module is deliberately only a contract boundary.  It does not generate,
select, publish, enter, or grade lineups.  A caller must provide two already
frozen book artifacts.  The validator binds those artifacts to the exact
adopted configurations and proves that both arms used the same pre-lock slate,
inputs, and simulation banks.

D400 is a counterfactual book, not a required prefix of D800.  Their observed
roster overlap is retained as a checked diagnostic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import re
from typing import Final

from .generation_exposure import canonical_sha256


SCHEMA_VERSION: Final = "week1-adopted-pair/v1"
PAIR_ID: Final = "2026-week1-d800-paid-d400-shadow-v1"
PAID_ARM_ID: Final = "D800_DEMAX"
SHADOW_ARM_ID: Final = "D400_DEMAX"
EXACT_ENTRIES: Final = 80
WEEK1_LOCK_UTC: Final = "2026-09-13T17:00:00+00:00"
GOVERNED_ARTIFACT_PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/"
)

_PAIR_FIELDS: Final = frozenset({
    "schema_version",
    "pair_id",
    "complete",
    "authority",
    "recipe",
    "paid",
    "shadow",
    "roster_overlap_count",
    "contract_sha256",
})
_AUTHORITY_FIELDS: Final = frozenset({
    "season",
    "week",
    "draft_group_id",
    "slate_type",
    "lock_utc",
    "frozen_at",
    "outcome_blind",
    "outcome_fields_read",
})
_RECIPE_FIELDS: Final = frozenset({
    "generation_seed",
    "selection_seed",
    "audit_seed",
    "corrected_hsim_seed",
    "incumbent_worlds",
    "corrected_hsim_worlds",
    "decision_worlds",
    "law_weighting",
    "selector_recipe",
    "tie_break",
    "construction_contract",
})
_ARM_FIELDS: Final = frozenset({
    "arm_id",
    "purpose",
    "config",
    "slate_identity",
    "input_identity",
    "player_bridge_identity",
    "generation_bank_identity",
    "selection_bank_identity",
    "audit_bank_identity",
    "hsim_bank_identity",
    "construction_identity",
    "generator_source_identity",
    "selector_source_identity",
    "hsim_source_identity",
    "book_artifact",
    "candidate_artifact",
    "exposure_ledger_artifact",
    "run_receipt_artifact",
    "candidate_ids",
    "roster_ids",
})
_CONFIG_FIELDS: Final = frozenset({"lev", "boom", "selector", "entries", "k"})
_IDENTITY_FIELDS: Final = frozenset({"id", "sha256"})
_ARTIFACT_FIELDS: Final = frozenset({
    "uri", "generation", "sha256", "bytes",
})
_SHARED_IDENTITY_FIELDS: Final = (
    "slate_identity",
    "input_identity",
    "player_bridge_identity",
    "generation_bank_identity",
    "selection_bank_identity",
    "audit_bank_identity",
    "hsim_bank_identity",
    "construction_identity",
    "generator_source_identity",
    "selector_source_identity",
    "hsim_source_identity",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ROSTER_ID = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_SOURCE_ID = re.compile(
    r"(?:nfl2-live-week|nfl2-select-expected-max|nfl2-corrected-hsim)"
    r"@[0-9a-f]{40}\Z"
)


class Week1AdoptedPairError(ValueError):
    """The Week-1 D800/D400 authority differs from its frozen contract."""


def _fail(message: str) -> None:
    raise Week1AdoptedPairError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed mapping")
    return dict(value)


def _exact_fields(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = set(value)
    if actual != expected:
        _fail(
            f"{label} fields differ: missing={sorted(expected - actual)} "
            f"unexpected={sorted(actual - expected)}"
        )


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a nonempty canonical string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return value


def _gcs_uri(value: object, *, label: str) -> str:
    uri = _text(value, label=label)
    if (
        not uri.startswith(GOVERNED_ARTIFACT_PREFIX)
        or uri.endswith("/")
        or any(token in uri for token in ("\\", "\x00", "?", "#"))
    ):
        _fail(f"{label} must use the governed Week-1 prelock prefix")
    bucket, separator, object_name = uri[5:].partition("/")
    if (
        not separator
        or not bucket
        or not object_name
        or any(part in {"", ".", ".."} for part in object_name.split("/"))
    ):
        _fail(f"{label} must name one canonical GCS object")
    if any(token in uri.lower() for token in (
        "/actual", "/outcome", "/postlock", "/post-lock",
        "/standings", "/payout", "/settlement",
    )):
        _fail(f"{label} is an outcome/post-lock carrier")
    return uri


def _positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 1:
        _fail(f"{label} must be a positive integer")
    return value


def _generation(value: object, *, label: str) -> str:
    if type(value) is not str:
        _fail(f"{label} must be a positive decimal generation")
    retained = value
    if (
        not retained.isdigit()
        or retained.startswith("0")
        or int(retained) < 1
    ):
        _fail(f"{label} must be a positive decimal generation")
    return retained


def _canonical_timestamp(value: object, *, label: str) -> str:
    text = _text(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise Week1AdoptedPairError(
            f"{label} must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{label} must be timezone-aware")
    canonical = parsed.astimezone(timezone.utc).isoformat()
    if text != canonical:
        _fail(f"{label} must use canonical UTC representation")
    return canonical


def _authority(value: object) -> dict[str, object]:
    authority = _mapping(value, label="Week-1 authority")
    _exact_fields(authority, _AUTHORITY_FIELDS, label="Week-1 authority")
    if (
        type(authority.get("season")) is not int
        or authority.get("season") != 2026
        or type(authority.get("week")) is not int
        or authority.get("week") != 1
        or authority.get("draft_group_id") != "151307"
        or authority.get("slate_type") != "sunday-main"
        or authority.get("outcome_blind") is not True
        or authority.get("outcome_fields_read") != []
    ):
        _fail("Week-1 authority differs from the frozen pre-lock boundary")
    lock_utc = _canonical_timestamp(
        authority.get("lock_utc"), label="Week-1 lock"
    )
    if lock_utc != WEEK1_LOCK_UTC:
        _fail("Week-1 lock differs")
    frozen_at = _canonical_timestamp(
        authority.get("frozen_at"), label="Week-1 freeze time"
    )
    if datetime.fromisoformat(frozen_at) >= datetime.fromisoformat(lock_utc):
        _fail("Week-1 pair was not frozen before lock")
    return {
        "season": 2026,
        "week": 1,
        "draft_group_id": "151307",
        "slate_type": "sunday-main",
        "lock_utc": lock_utc,
        "frozen_at": frozen_at,
        "outcome_blind": True,
        "outcome_fields_read": [],
    }


def _recipe(value: object) -> dict[str, object]:
    recipe = _mapping(value, label="Week-1 D800/D400 recipe")
    _exact_fields(recipe, _RECIPE_FIELDS, label="Week-1 D800/D400 recipe")
    expected: dict[str, object] = {
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
    if any(
        type(recipe.get(field)) is not type(expected_value)
        or recipe.get(field) != expected_value
        for field, expected_value in expected.items()
    ):
        _fail("Week-1 D800/D400 recipe differs from the adopted live law")
    return expected


def _identity(value: object, *, label: str) -> dict[str, object]:
    identity = _mapping(value, label=label)
    _exact_fields(identity, _IDENTITY_FIELDS, label=label)
    return {
        "id": _text(identity.get("id"), label=f"{label} id"),
        "sha256": _digest(identity.get("sha256"), label=f"{label} SHA-256"),
    }


def _artifact(value: object, *, label: str) -> dict[str, object]:
    artifact = _mapping(value, label=label)
    _exact_fields(artifact, _ARTIFACT_FIELDS, label=label)
    return {
        "uri": _gcs_uri(artifact.get("uri"), label=f"{label} URI"),
        "generation": _generation(
            artifact.get("generation"), label=f"{label} generation"
        ),
        "sha256": _digest(
            artifact.get("sha256"), label=f"{label} SHA-256"
        ),
        "bytes": _positive_int(
            artifact.get("bytes"), label=f"{label} bytes"
        ),
    }


def _roster_ids(value: object, *, label: str) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, Sequence
    ):
        _fail(f"{label} must be an ordered sequence")
    retained: list[str] = []
    for roster_id in value:
        if type(roster_id) is not str or _ROSTER_ID.fullmatch(roster_id) is None:
            _fail(f"{label} contains a noncanonical roster ID")
        retained.append(roster_id)
    if len(retained) != EXACT_ENTRIES:
        _fail(f"{label} must contain exactly {EXACT_ENTRIES} roster IDs")
    if len(set(retained)) != EXACT_ENTRIES:
        _fail(f"{label} repeats a roster ID")
    return retained


def _candidate_ids(value: object, *, label: str) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(
        value, Sequence
    ):
        _fail(f"{label} must be an ordered sequence")
    retained: list[str] = []
    for candidate_id in value:
        if (
            type(candidate_id) is not str
            or _ROSTER_ID.fullmatch(candidate_id) is None
        ):
            _fail(f"{label} contains a noncanonical candidate ID")
        retained.append(candidate_id)
    if len(retained) < EXACT_ENTRIES:
        _fail(f"{label} must contain at least {EXACT_ENTRIES} candidates")
    if len(set(retained)) != len(retained):
        _fail(f"{label} repeats a candidate ID")
    return retained


def _config(
    value: object,
    *,
    arm_id: str,
    lev: int,
    boom: int,
) -> dict[str, object]:
    config = _mapping(value, label=f"{arm_id} config")
    _exact_fields(config, _CONFIG_FIELDS, label=f"{arm_id} config")
    expected: dict[str, object] = {
        "lev": lev,
        "boom": boom,
        "selector": "dual_emax",
        "entries": EXACT_ENTRIES,
        "k": 1,
    }
    # Exact equality also rejects booleans for integer levers.
    if any(
        type(config.get(field)) is not type(expected_value)
        or config.get(field) != expected_value
        for field, expected_value in expected.items()
    ):
        _fail(f"{arm_id} config differs from the frozen {lev}/{boom} law")
    return expected


def _arm(
    value: object,
    *,
    arm_id: str,
    purpose: str,
    lev: int,
    boom: int,
) -> dict[str, object]:
    arm = _mapping(value, label=f"{arm_id} arm")
    _exact_fields(arm, _ARM_FIELDS, label=f"{arm_id} arm")
    if arm.get("arm_id") != arm_id or arm.get("purpose") != purpose:
        _fail(f"{arm_id} identity/purpose differs")
    retained: dict[str, object] = {
        "arm_id": arm_id,
        "purpose": purpose,
        "config": _config(
            arm.get("config"), arm_id=arm_id, lev=lev, boom=boom
        ),
    }
    for field in _SHARED_IDENTITY_FIELDS:
        retained[field] = _identity(
            arm.get(field), label=f"{arm_id} {field}"
        )
    expected_identity_ids = {
        "slate_identity": "2026-w01-dk-151307",
        "input_identity": "live-input-root/v1",
        "player_bridge_identity": "player-bridge/v1",
        "generation_bank_identity": "incumbent-generation-seed-2026",
        "selection_bank_identity": "incumbent-selection-seed-2076",
        "audit_bank_identity": "incumbent-audit-seed-2126",
        "hsim_bank_identity": "corrected-hsim-selection-seed-2326",
        "construction_identity": "house_qb2_bb1_floor49_v1",
    }
    if any(
        retained[field]["id"] != expected_id
        for field, expected_id in expected_identity_ids.items()
    ):
        _fail(f"{arm_id} semantic identity differs from the adopted live law")
    source_fields = (
        "generator_source_identity",
        "selector_source_identity",
        "hsim_source_identity",
    )
    source_ids = [str(retained[field]["id"]) for field in source_fields]
    if any(_SOURCE_ID.fullmatch(source_id) is None for source_id in source_ids):
        _fail(f"{arm_id} source identity is not commit-pinned")
    if len({source_id.rsplit("@", 1)[1] for source_id in source_ids}) != 1:
        _fail(f"{arm_id} source identities do not share one commit")
    retained["book_artifact"] = _artifact(
        arm.get("book_artifact"), label=f"{arm_id} book artifact"
    )
    retained["candidate_artifact"] = _artifact(
        arm.get("candidate_artifact"), label=f"{arm_id} candidate artifact"
    )
    retained["exposure_ledger_artifact"] = _artifact(
        arm.get("exposure_ledger_artifact"),
        label=f"{arm_id} exposure-ledger artifact",
    )
    retained["run_receipt_artifact"] = _artifact(
        arm.get("run_receipt_artifact"),
        label=f"{arm_id} canonical run-receipt artifact",
    )
    retained["candidate_ids"] = _candidate_ids(
        arm.get("candidate_ids"), label=f"{arm_id} candidate IDs"
    )
    retained["roster_ids"] = _roster_ids(
        arm.get("roster_ids"), label=f"{arm_id} roster IDs"
    )
    if not set(retained["roster_ids"]) <= set(retained["candidate_ids"]):
        _fail(f"{arm_id} selected book is not contained in its candidate pool")
    return retained


def _normalized_pair(value: object) -> dict[str, object]:
    pair = _mapping(value, label="Week-1 adopted pair")
    _exact_fields(pair, _PAIR_FIELDS, label="Week-1 adopted pair")
    if (
        pair.get("schema_version") != SCHEMA_VERSION
        or pair.get("pair_id") != PAIR_ID
        or pair.get("complete") is not True
    ):
        _fail("Week-1 adopted-pair schema/identity/completion differs")

    authority = _authority(pair.get("authority"))
    recipe = _recipe(pair.get("recipe"))

    paid = _arm(
        pair.get("paid"),
        arm_id=PAID_ARM_ID,
        purpose="paid",
        lev=160,
        boom=640,
    )
    shadow = _arm(
        pair.get("shadow"),
        arm_id=SHADOW_ARM_ID,
        purpose="shadow",
        lev=80,
        boom=320,
    )

    for field in _SHARED_IDENTITY_FIELDS:
        if paid[field] != shadow[field]:
            _fail(f"paid/shadow {field} differs")

    artifacts = [
        arm[field]
        for arm in (paid, shadow)
        for field in (
            "book_artifact",
            "candidate_artifact",
            "exposure_ledger_artifact",
            "run_receipt_artifact",
        )
    ]
    artifact_uris = [artifact["uri"] for artifact in artifacts]
    if len(set(artifact_uris)) != len(artifact_uris):
        _fail("paid/shadow artifact URIs alias")

    if not set(shadow["candidate_ids"]) <= set(paid["candidate_ids"]):
        _fail("D400 candidate population is not contained in D800")

    overlap = len(set(paid["roster_ids"]) & set(shadow["roster_ids"]))
    retained_overlap = pair.get("roster_overlap_count")
    if type(retained_overlap) is not int or retained_overlap != overlap:
        _fail("roster overlap diagnostic differs from exact membership")

    contract_sha256 = _digest(
        pair.get("contract_sha256"), label="adopted-pair contract SHA-256"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "pair_id": PAIR_ID,
        "complete": True,
        "authority": authority,
        "recipe": recipe,
        "paid": paid,
        "shadow": shadow,
        "roster_overlap_count": overlap,
        "contract_sha256": contract_sha256,
    }


def validate_week1_adopted_pair_v1(value: object) -> dict[str, object]:
    """Validate and normalize the immutable D800-paid/D400-shadow authority."""

    normalized = _normalized_pair(value)
    retained_hash = normalized.pop("contract_sha256")
    try:
        expected_hash = canonical_sha256(normalized)
    except Exception as exc:
        raise Week1AdoptedPairError(
            "Week-1 adopted pair is not canonical JSON"
        ) from exc
    normalized["contract_sha256"] = retained_hash
    if retained_hash != expected_hash:
        _fail("adopted-pair contract SHA-256 differs")
    return normalized


def build_week1_adopted_pair_v1(
    *, authority: object, recipe: object, paid: object, shadow: object
) -> dict[str, object]:
    """Seal two frozen arm records into the sole Week-1 adopted-pair shape."""

    paid_arm = _arm(
        paid,
        arm_id=PAID_ARM_ID,
        purpose="paid",
        lev=160,
        boom=640,
    )
    shadow_arm = _arm(
        shadow,
        arm_id=SHADOW_ARM_ID,
        purpose="shadow",
        lev=80,
        boom=320,
    )
    body: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "pair_id": PAIR_ID,
        "complete": True,
        "authority": _authority(authority),
        "recipe": _recipe(recipe),
        "paid": paid_arm,
        "shadow": shadow_arm,
        "roster_overlap_count": len(
            set(paid_arm["roster_ids"]) & set(shadow_arm["roster_ids"])
        ),
    }
    body["contract_sha256"] = canonical_sha256(body)
    return validate_week1_adopted_pair_v1(body)


__all__ = [
    "EXACT_ENTRIES",
    "GOVERNED_ARTIFACT_PREFIX",
    "PAIR_ID",
    "PAID_ARM_ID",
    "SCHEMA_VERSION",
    "SHADOW_ARM_ID",
    "WEEK1_LOCK_UTC",
    "Week1AdoptedPairError",
    "build_week1_adopted_pair_v1",
    "validate_week1_adopted_pair_v1",
]
