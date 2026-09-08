"""Immutable Week-1 A5 entry and settlement evidence contracts.

This module is deliberately outside the scoring and entry paths.  It binds the
already-frozen A5 allocation to one immutable pre-lock contest manifest per
contest, exact accepted DraftKings entries, a four-contest acceptance root,
and a post-settlement result receipt.  It performs no network, Cloud Storage,
warehouse, or DraftKings mutation.

The v3 manifest fixes an ambiguity in ``dk-contest-manifest/v2``: advertised
capacity and the current pre-lock entry count are different facts, while final
field size is knowable only after settlement.  The three values therefore
never share a field or overwrite one another.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference.week1_a5_allocation import (
    ALLOCATION_ID,
    validate_week1_a5_allocation_v1,
)

PRELOCK_SCHEMA: Final = "dk-contest-manifest/v3"
ACCEPTANCE_SCHEMA: Final = "week1-a5-entry-acceptance/v1"
ACCEPTANCE_ROOT_SCHEMA: Final = "week1-a5-entry-acceptance-root/v1"
SETTLEMENT_SCHEMA: Final = "dk-contest-settlement/v1"
BOOK_BINDING_SCHEMA: Final = "week1-a5-contest-book-binding/v1"

EXPECTED_ROLE_ENTRIES: Final = {
    "milly-5": 57,
    "large-20max-3": 20,
    "championship-qualifier-18": 3,
    "championship-qualifier-5": 10,
}
EXPECTED_POLICIES: Final = ("P_MIX", "P_CTRL", "D400_DEMAX", "D800_WEMAX")
SHADOW_POLICIES: Final = ("P_CTRL", "D400_DEMAX", "D800_WEMAX")
EXPECTED_SLATE_ID: Final = "dk-151307"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_LINEUP = re.compile(r"lineup-v1-[0-9a-f]{64}\Z")
_IDENTITY_FIELDS = frozenset({"uri", "generation", "sha256", "bytes"})
_PRELOCK_CARRIER_TOKENS = (
    "/actual",
    "/outcome",
    "/postlock",
    "/post-lock",
    "/standings",
    "/payout",
    "/settlement",
)
_CENT_MICRO = 10_000


class Week1A5CaptureContractError(ValueError):
    """A Week-1 A5 evidence artifact violated its fail-closed contract."""


def _fail(message: str) -> None:
    raise Week1A5CaptureContractError(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact(
    value: Mapping[str, object], fields: set[str] | frozenset[str], *, label: str
) -> None:
    if set(value) != set(fields):
        _fail(
            f"{label} fields differ: missing={sorted(set(fields) - set(value))} "
            f"unexpected={sorted(set(value) - set(fields))}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _lineup(value: object, *, label: str) -> str:
    if type(value) is not str or _LINEUP.fullmatch(value) is None:
        _fail(f"{label} must be a canonical lineup ID")
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise Week1A5CaptureContractError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        _fail(f"{label} must include a UTC offset")
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _identity(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact(row, _IDENTITY_FIELDS, label=label)
    uri = _string(row.get("uri"), label=f"{label}.uri")
    if (
        not uri.startswith("gs://")
        or uri.endswith("/")
        or "/" not in uri[5:]
        or "#" in uri
    ):
        _fail(f"{label}.uri must name one generation-free gs:// object")
    generation = row.get("generation")
    if (
        type(generation) not in {str, int}
        or not str(generation).isdigit()
        or int(generation) < 1
    ):
        _fail(f"{label}.generation must identify one immutable generation")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": _sha(row.get("sha256"), label=f"{label}.sha256"),
        "bytes": _integer(row.get("bytes"), label=f"{label}.bytes", minimum=1),
    }


def _prelock_identity(value: object, *, label: str) -> dict[str, object]:
    identity = _identity(value, label=label)
    if any(token in str(identity["uri"]).lower() for token in _PRELOCK_CARRIER_TOKENS):
        _fail(f"{label}.uri is an outcome/post-lock carrier")
    return identity


def _source(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact(row, {"identity", "captured_at"}, label=label)
    captured_at, _ = _timestamp(row.get("captured_at"), label=f"{label}.captured_at")
    return {
        "identity": _prelock_identity(row.get("identity"), label=f"{label}.identity"),
        "captured_at": captured_at,
    }


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> dict[str, object]:
    body = dict(value)
    retained = _sha(body.pop(field, None), label=f"{label}.{field}")
    if retained != canonical_sha256(body):
        _fail(f"{label} {field} differs")
    body[field] = retained
    return body


def _finish(body: dict[str, object], *, field: str) -> dict[str, object]:
    body[field] = canonical_sha256(body)
    return body


def _correction(value: object, *, label: str, hash_field: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact(row, {"revision", hash_field, "reason"}, label=label)
    revision = _integer(row.get("revision"), label=f"{label}.revision")
    predecessor = row.get(hash_field)
    reason = _string(row.get("reason"), label=f"{label}.reason")
    if revision == 0:
        if predecessor is not None or reason != "initial":
            _fail(f"{label} revision 0 must be initial with no predecessor")
    else:
        predecessor = _sha(predecessor, label=f"{label}.{hash_field}")
        if reason == "initial":
            _fail(f"{label} correction must state a non-initial reason")
    return {"revision": revision, hash_field: predecessor, "reason": reason}


def _allocation(value: object) -> dict[str, object]:
    try:
        return validate_week1_a5_allocation_v1(value)
    except Exception as exc:
        raise Week1A5CaptureContractError("A5 allocation root is invalid") from exc


def _contest_for_role(allocation: Mapping[str, object], role: str) -> dict[str, object]:
    if role not in EXPECTED_ROLE_ENTRIES:
        _fail("contest_role is not in the frozen A5 allocation")
    matches = [dict(row) for row in allocation["contests"] if row["role"] == role]
    if len(matches) != 1:
        _fail("A5 allocation does not contain one exact contest role")
    return matches[0]


def _normalize_payout_ladder(
    value: object, *, capacity: int
) -> tuple[list[dict[str, object]], dict[int, int]]:
    raw_rows = _sequence(value, label="payout_ladder")
    rows: list[dict[str, object]] = []
    for ordinal, raw in enumerate(raw_rows):
        row = _mapping(raw, label=f"payout_ladder[{ordinal}]")
        _exact(
            row,
            {"rank_start", "rank_end", "payout_micro", "award_label"},
            label=f"payout_ladder[{ordinal}]",
        )
        start = _integer(row.get("rank_start"), label="payout rank_start", minimum=1)
        end = _integer(row.get("rank_end"), label="payout rank_end", minimum=start)
        if end > capacity:
            _fail("payout ladder rank exceeds advertised field capacity")
        rows.append(
            {
                "rank_start": start,
                "rank_end": end,
                "payout_micro": _integer(row.get("payout_micro"), label="payout_micro"),
                "award_label": _string(row.get("award_label"), label="award_label"),
            }
        )
    rows.sort(key=lambda row: (int(row["rank_start"]), int(row["rank_end"])))
    if not rows or rows[0]["rank_start"] != 1:
        _fail("payout ladder must begin at rank 1")
    by_rank: dict[int, int] = {}
    prior_end = 0
    prior_payout: int | None = None
    for row in rows:
        start, end, payout = (
            int(row["rank_start"]),
            int(row["rank_end"]),
            int(row["payout_micro"]),
        )
        if start != prior_end + 1:
            _fail("payout ladder contains a gap or overlap")
        if prior_payout is not None and payout > prior_payout:
            _fail("payout ladder must be nonincreasing")
        by_rank.update({rank: payout for rank in range(start, end + 1)})
        prior_end, prior_payout = end, payout
    return rows, by_rank


def _int_ids(value: object, *, label: str) -> list[int]:
    ids = [
        _integer(item, label=label, minimum=1) for item in _sequence(value, label=label)
    ]
    if len(ids) != 9 or len(set(ids)) != 9:
        _fail(f"{label} must contain nine unique IDs")
    return ids


def _draftable_ids(value: object, *, label: str) -> list[int]:
    ids = [
        _integer(item, label=label, minimum=1) for item in _sequence(value, label=label)
    ]
    if len(ids) != 9 or len(set(ids)) != 9:
        _fail(f"{label} must contain nine unique DraftKings IDs")
    return ids


def _book_entry(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact(
        row,
        {
            "lineup_rank",
            "lineup_id",
            "roster_sha256",
            "internal_player_ids",
            "slot_dk_draftable_ids",
        },
        label=label,
    )
    internal = sorted(
        _int_ids(row.get("internal_player_ids"), label=f"{label}.internal_player_ids")
    )
    roster_sha = _sha(row.get("roster_sha256"), label=f"{label}.roster_sha256")
    if roster_sha != canonical_sha256(sorted(internal)):
        _fail(f"{label}.roster_sha256 differs from internal_player_ids")
    return {
        "lineup_rank": _integer(
            row.get("lineup_rank"), label=f"{label}.lineup_rank", minimum=1
        ),
        "lineup_id": _lineup(row.get("lineup_id"), label=f"{label}.lineup_id"),
        "roster_sha256": roster_sha,
        "internal_player_ids": internal,
        "slot_dk_draftable_ids": _draftable_ids(
            row.get("slot_dk_draftable_ids"), label=f"{label}.slot_dk_draftable_ids"
        ),
    }


def _book_binding(
    value: object, *, label: str, expected_count: int
) -> dict[str, object]:
    row = _mapping(value, label=label)
    base_fields = {
        "schema_version",
        "policy",
        "purpose",
        "artifact_identity",
        "entries",
    }
    if set(row) not in {
        frozenset(base_fields),
        frozenset(base_fields | {"entries_sha256"}),
    }:
        _fail(f"{label} fields differ")
    if row.get("schema_version") != BOOK_BINDING_SCHEMA:
        _fail(f"{label} schema differs")
    policy = _string(row.get("policy"), label=f"{label}.policy")
    if policy not in EXPECTED_POLICIES:
        _fail(f"{label}.policy is not a frozen A5 policy")
    purpose = _string(row.get("purpose"), label=f"{label}.purpose")
    if purpose != ("paid" if policy == "P_MIX" else "shadow"):
        _fail(f"{label}.purpose differs from A5")
    entries = [
        _book_entry(item, label=f"{label}.entries[{i}]")
        for i, item in enumerate(
            _sequence(row.get("entries"), label=f"{label}.entries")
        )
    ]
    if len(entries) != expected_count:
        _fail(f"{label} must bind exact contest K={expected_count}")
    if [item["lineup_rank"] for item in entries] != list(range(1, expected_count + 1)):
        _fail(f"{label} lineup ranks must be exact 1..K")
    if (
        len({item["lineup_id"] for item in entries}) != expected_count
        or len({item["roster_sha256"] for item in entries}) != expected_count
    ):
        _fail(f"{label} contains duplicate lineups or rosters")
    entries_sha256 = canonical_sha256(entries)
    if "entries_sha256" in row and row.get("entries_sha256") != entries_sha256:
        _fail(f"{label}.entries_sha256 differs")
    return {
        "schema_version": BOOK_BINDING_SCHEMA,
        "policy": policy,
        "purpose": purpose,
        "artifact_identity": _prelock_identity(
            row.get("artifact_identity"), label=f"{label}.artifact_identity"
        ),
        "entries": entries,
        "entries_sha256": entries_sha256,
    }


def _manifest_core(value: object, *, allocation: object) -> dict[str, object]:
    a5 = _allocation(allocation)
    manifest = _mapping(value, label="pre-lock manifest")
    manifest = _self_hash(manifest, field="manifest_sha256", label="pre-lock manifest")
    _exact(
        manifest,
        {
            "schema_version",
            "complete",
            "manifest_frozen_at",
            "contest",
            "payout_ladder",
            "source_identities",
            "a5_binding",
            "correction_lineage",
            "outcome_fields_read",
            "manifest_sha256",
        },
        label="pre-lock manifest",
    )
    if (
        manifest.get("schema_version") != PRELOCK_SCHEMA
        or manifest.get("complete") is not True
    ):
        _fail("pre-lock manifest schema or completeness differs")
    if manifest.get("outcome_fields_read") != []:
        _fail("pre-lock manifest cannot read outcomes")
    frozen_text, frozen_at = _timestamp(
        manifest.get("manifest_frozen_at"), label="manifest_frozen_at"
    )
    contest = _mapping(manifest.get("contest"), label="contest")
    _exact(
        contest,
        {
            "season",
            "week",
            "contest_id",
            "contest_name",
            "contest_role",
            "draft_group_id",
            "slate_id",
            "roster_format",
            "advertised_field_capacity",
            "entries_observed_at_freeze",
            "entries_observed_at",
            "entry_fee_micro",
            "entry_limit",
            "lock_at",
            "late_swap",
            "payout_ladder_underfill_policy",
        },
        label="contest",
    )
    role = _string(contest.get("contest_role"), label="contest_role")
    expected = _contest_for_role(a5, role)
    lock_text, lock_at = _timestamp(contest.get("lock_at"), label="lock_at")
    observed_text, observed_at = _timestamp(
        contest.get("entries_observed_at"), label="entries_observed_at"
    )
    if frozen_at >= lock_at or observed_at > frozen_at:
        _fail(
            "pre-lock manifest and current-entry observation must precede lock in order"
        )
    capacity = _integer(
        contest.get("advertised_field_capacity"),
        label="advertised_field_capacity",
        minimum=1,
    )
    current = _integer(
        contest.get("entries_observed_at_freeze"), label="entries_observed_at_freeze"
    )
    if current > capacity:
        _fail("current pre-lock entries exceed advertised capacity")
    late_swap = _mapping(contest.get("late_swap"), label="late_swap")
    _exact(late_swap, {"enabled", "policy", "state_at_freeze"}, label="late_swap")
    if (
        type(late_swap.get("enabled")) is not bool
        or late_swap.get("state_at_freeze") != "prelock"
    ):
        _fail("late_swap must be an explicit pre-lock fact")
    underfill_policy = _string(
        contest.get("payout_ladder_underfill_policy"),
        label="payout_ladder_underfill_policy",
    )
    if underfill_policy not in {
        "prelock-applicable-ranks-only",
        "official-settlement-ladder",
    }:
        _fail("payout ladder underfill policy differs")
    exact_facts = {
        "season": a5["season"],
        "week": a5["week"],
        "contest_id": expected["contest_id"],
        "contest_name": expected["contest_name"],
        "contest_role": role,
        "draft_group_id": expected["draft_group_id"],
        "entry_fee_micro": expected["entry_fee_micro"],
        "entry_limit": expected["entry_limit"],
        "advertised_field_capacity": expected["field_cap"],
    }
    actual_facts = {name: contest.get(name) for name in exact_facts}
    if actual_facts != exact_facts or contest.get("roster_format") != "classic":
        _fail("manifest contest identity differs from the frozen A5 allocation")
    _, expected_lock = _timestamp(expected["lock_utc"], label="A5 lock_utc")
    if lock_at != expected_lock:
        _fail("manifest lock differs from the frozen A5 allocation")
    payout, _ = _normalize_payout_ladder(
        manifest.get("payout_ladder"), capacity=capacity
    )
    sources = _mapping(manifest.get("source_identities"), label="source_identities")
    if set(sources) != {
        "contest_metadata",
        "payout_ladder",
        "late_swap",
        "current_entries",
    }:
        _fail("pre-lock source identity set differs")
    normalized_sources = {
        name: _source(sources[name], label=f"source_identities.{name}")
        for name in sorted(sources)
    }
    for name, source in normalized_sources.items():
        _, captured = _timestamp(source["captured_at"], label=f"{name}.captured_at")
        if captured > frozen_at:
            _fail(f"{name} was captured after manifest freeze")
    if normalized_sources["current_entries"]["captured_at"] != observed_text:
        _fail("current-entry source timestamp differs from entries_observed_at")
    binding = _mapping(manifest.get("a5_binding"), label="a5_binding")
    _exact(
        binding,
        {
            "allocation_id",
            "allocation_sha256",
            "allocation_identity",
            "contest_role",
            "planned_entries",
            "paid_policy",
            "shadow_policies",
            "paid_entry_edges",
            "shadow_entry_edges",
            "book_bindings",
        },
        label="a5_binding",
    )
    allocation_identity = _prelock_identity(
        binding.get("allocation_identity"), label="allocation_identity"
    )
    if (
        binding.get("allocation_id") != ALLOCATION_ID
        or binding.get("allocation_sha256") != a5["allocation_sha256"]
        or allocation_identity["sha256"] != a5["allocation_sha256"]
        or binding.get("contest_role") != role
        or binding.get("planned_entries") != EXPECTED_ROLE_ENTRIES[role]
        or binding.get("paid_policy") != "P_MIX"
        or binding.get("shadow_policies") != list(SHADOW_POLICIES)
    ):
        _fail("manifest A5 allocation-root binding differs")
    contest_id = expected["contest_id"]
    paid_edges = [
        dict(row) for row in a5["paid_entry_edges"] if row["contest_id"] == contest_id
    ]
    shadow_edges = [
        dict(row) for row in a5["shadow_entry_edges"] if row["contest_id"] == contest_id
    ]
    if (
        binding.get("paid_entry_edges") != paid_edges
        or binding.get("shadow_entry_edges") != shadow_edges
    ):
        _fail("manifest A5 contest edge slice differs")
    k = EXPECTED_ROLE_ENTRIES[role]
    books = [
        _book_binding(item, label=f"book_bindings[{i}]", expected_count=k)
        for i, item in enumerate(
            _sequence(binding.get("book_bindings"), label="book_bindings")
        )
    ]
    by_policy = {str(row["policy"]): row for row in books}
    if len(books) != 4 or set(by_policy) != set(EXPECTED_POLICIES):
        _fail("manifest must bind exactly the paid book and three A5 shadow books")
    expected_ids: dict[str, list[str]] = {
        "P_MIX": [str(row["lineup_id"]) for row in paid_edges]
    }
    for policy in SHADOW_POLICIES:
        expected_ids[policy] = [
            str(row["lineup_id"]) for row in shadow_edges if row["book_id"] == policy
        ]
    for policy, book in by_policy.items():
        if [str(row["lineup_id"]) for row in book["entries"]] != expected_ids[policy]:
            _fail(f"{policy} book differs from its exact A5 edge slice")
    correction = _correction(
        manifest.get("correction_lineage"),
        label="manifest correction_lineage",
        hash_field="supersedes_manifest_sha256",
    )
    normalized = {
        "schema_version": PRELOCK_SCHEMA,
        "complete": True,
        "manifest_frozen_at": frozen_text,
        "contest": {
            "season": a5["season"],
            "week": a5["week"],
            "contest_id": expected["contest_id"],
            "contest_name": expected["contest_name"],
            "contest_role": role,
            "draft_group_id": expected["draft_group_id"],
            "slate_id": _string(contest.get("slate_id"), label="slate_id"),
            "roster_format": "classic",
            "advertised_field_capacity": capacity,
            "entries_observed_at_freeze": current,
            "entries_observed_at": observed_text,
            "entry_fee_micro": expected["entry_fee_micro"],
            "entry_limit": expected["entry_limit"],
            "lock_at": lock_text,
            "late_swap": {
                "enabled": late_swap["enabled"],
                "policy": _string(late_swap.get("policy"), label="late_swap.policy"),
                "state_at_freeze": "prelock",
            },
            "payout_ladder_underfill_policy": underfill_policy,
        },
        "payout_ladder": payout,
        "source_identities": normalized_sources,
        "a5_binding": {
            "allocation_id": ALLOCATION_ID,
            "allocation_sha256": a5["allocation_sha256"],
            "allocation_identity": allocation_identity,
            "contest_role": role,
            "planned_entries": k,
            "paid_policy": "P_MIX",
            "shadow_policies": list(SHADOW_POLICIES),
            "paid_entry_edges": paid_edges,
            "shadow_entry_edges": shadow_edges,
            "book_bindings": [by_policy[name] for name in EXPECTED_POLICIES],
        },
        "correction_lineage": correction,
        "outcome_fields_read": [],
        "manifest_sha256": manifest["manifest_sha256"],
    }
    if normalized != manifest:
        _fail("pre-lock manifest does not exactly replay its canonical semantics")
    if normalized["contest"]["slate_id"] != EXPECTED_SLATE_ID:
        _fail("manifest slate ID differs from the frozen Week-1 draft group")
    return normalized


def build_week1_prelock_manifest_v3(
    *,
    allocation: object,
    allocation_identity: object,
    contest_role: str,
    slate_id: str,
    advertised_field_capacity: int,
    entries_observed_at_freeze: int,
    entries_observed_at: str,
    manifest_frozen_at: str,
    late_swap: object,
    payout_ladder_underfill_policy: str,
    payout_ladder: object,
    source_identities: object,
    book_bindings: object,
    correction_lineage: object,
) -> dict[str, object]:
    """Build one immutable pre-lock manifest; no final field-size field exists."""
    a5 = _allocation(allocation)
    contest = _contest_for_role(a5, contest_role)
    if slate_id != EXPECTED_SLATE_ID:
        _fail("slate_id differs from the frozen Week-1 draft group")
    paid_edges = [
        dict(row)
        for row in a5["paid_entry_edges"]
        if row["contest_id"] == contest["contest_id"]
    ]
    shadow_edges = [
        dict(row)
        for row in a5["shadow_entry_edges"]
        if row["contest_id"] == contest["contest_id"]
    ]
    frozen_text, _ = _timestamp(manifest_frozen_at, label="manifest_frozen_at")
    observed_text, _ = _timestamp(entries_observed_at, label="entries_observed_at")
    capacity = _integer(
        advertised_field_capacity, label="advertised_field_capacity", minimum=1
    )
    normalized_payout, _ = _normalize_payout_ladder(payout_ladder, capacity=capacity)
    raw_sources = _mapping(source_identities, label="source_identities")
    normalized_sources = {
        name: _source(raw_sources[name], label=f"source_identities.{name}")
        for name in sorted(raw_sources)
    }
    raw_late_swap = _mapping(late_swap, label="late_swap")
    normalized_late_swap = {
        "enabled": raw_late_swap.get("enabled"),
        "policy": _string(raw_late_swap.get("policy"), label="late_swap.policy"),
        "state_at_freeze": raw_late_swap.get("state_at_freeze"),
    }
    k = EXPECTED_ROLE_ENTRIES[contest_role]
    normalized_books = [
        _book_binding(item, label=f"book_bindings[{i}]", expected_count=k)
        for i, item in enumerate(_sequence(book_bindings, label="book_bindings"))
    ]
    by_policy = {str(item["policy"]): item for item in normalized_books}
    if len(normalized_books) != 4 or set(by_policy) != set(EXPECTED_POLICIES):
        _fail("book_bindings must contain the four exact A5 policies")
    normalized_allocation_identity = _prelock_identity(
        allocation_identity, label="allocation_identity"
    )
    normalized_correction = _correction(
        correction_lineage,
        label="manifest correction_lineage",
        hash_field="supersedes_manifest_sha256",
    )
    lock_text, _ = _timestamp(contest["lock_utc"], label="A5 lock_utc")
    body: dict[str, object] = {
        "schema_version": PRELOCK_SCHEMA,
        "complete": True,
        "manifest_frozen_at": frozen_text,
        "contest": {
            "season": a5["season"],
            "week": a5["week"],
            "contest_id": contest["contest_id"],
            "contest_name": contest["contest_name"],
            "contest_role": contest_role,
            "draft_group_id": contest["draft_group_id"],
            "slate_id": slate_id,
            "roster_format": "classic",
            "advertised_field_capacity": capacity,
            "entries_observed_at_freeze": entries_observed_at_freeze,
            "entries_observed_at": observed_text,
            "entry_fee_micro": contest["entry_fee_micro"],
            "entry_limit": contest["entry_limit"],
            "lock_at": lock_text,
            "late_swap": normalized_late_swap,
            "payout_ladder_underfill_policy": payout_ladder_underfill_policy,
        },
        "payout_ladder": normalized_payout,
        "source_identities": normalized_sources,
        "a5_binding": {
            "allocation_id": ALLOCATION_ID,
            "allocation_sha256": a5["allocation_sha256"],
            "allocation_identity": normalized_allocation_identity,
            "contest_role": contest_role,
            "planned_entries": EXPECTED_ROLE_ENTRIES[contest_role],
            "paid_policy": "P_MIX",
            "shadow_policies": list(SHADOW_POLICIES),
            "paid_entry_edges": paid_edges,
            "shadow_entry_edges": shadow_edges,
            "book_bindings": [by_policy[name] for name in EXPECTED_POLICIES],
        },
        "correction_lineage": normalized_correction,
        "outcome_fields_read": [],
    }
    return _manifest_core(_finish(body, field="manifest_sha256"), allocation=a5)


def validate_week1_prelock_manifest_v3(
    value: object, *, allocation: object
) -> dict[str, object]:
    return _manifest_core(value, allocation=allocation)


def _manifest_identity(
    value: object, manifest: Mapping[str, object], *, label: str
) -> dict[str, object]:
    identity = _prelock_identity(value, label=label)
    if identity["sha256"] != manifest["manifest_sha256"]:
        _fail(f"{label} does not bind the exact manifest")
    return identity


def _acceptance_core(
    value: object, *, manifest: object, allocation: object
) -> dict[str, object]:
    a5 = _allocation(allocation)
    man = _manifest_core(manifest, allocation=a5)
    receipt = _self_hash(
        _mapping(value, label="entry acceptance"),
        field="acceptance_sha256",
        label="entry acceptance",
    )
    _exact(
        receipt,
        {
            "schema_version",
            "complete",
            "accepted_at",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "planned_entries",
            "allocation_sha256",
            "allocation_identity",
            "manifest_sha256",
            "manifest_identity",
            "prepared_capture_identity",
            "filled_upload_identity",
            "acceptance_evidence_identity",
            "acceptance_evidence_rows_sha256",
            "ordinal_bridge",
            "entries",
            "outcome_fields_read",
            "acceptance_sha256",
        },
        label="entry acceptance",
    )
    contest = man["contest"]
    role, k = str(contest["contest_role"]), int(man["a5_binding"]["planned_entries"])
    accepted_text, accepted_at = _timestamp(
        receipt.get("accepted_at"), label="accepted_at"
    )
    _, lock_at = _timestamp(contest["lock_at"], label="lock_at")
    if accepted_at >= lock_at:
        _fail("entry acceptance evidence must be frozen before lock")
    allocation_identity = _prelock_identity(
        receipt.get("allocation_identity"), label="allocation_identity"
    )
    manifest_identity = _manifest_identity(
        receipt.get("manifest_identity"), man, label="manifest_identity"
    )
    if (
        receipt.get("schema_version") != ACCEPTANCE_SCHEMA
        or receipt.get("complete") is not True
        or receipt.get("contest_role") != role
        or receipt.get("contest_id") != contest["contest_id"]
        or receipt.get("draft_group_id") != contest["draft_group_id"]
        or receipt.get("planned_entries") != k
        or receipt.get("allocation_sha256") != a5["allocation_sha256"]
        or allocation_identity["sha256"] != a5["allocation_sha256"]
        or receipt.get("manifest_sha256") != man["manifest_sha256"]
        or receipt.get("outcome_fields_read") != []
    ):
        _fail("entry acceptance root, contest, or pre-lock boundary differs")
    prepared_identity = _prelock_identity(
        receipt.get("prepared_capture_identity"), label="prepared_capture_identity"
    )
    upload_identity = _prelock_identity(
        receipt.get("filled_upload_identity"), label="filled_upload_identity"
    )
    evidence_identity = _prelock_identity(
        receipt.get("acceptance_evidence_identity"),
        label="acceptance_evidence_identity",
    )
    evidence_rows_sha = _sha(
        receipt.get("acceptance_evidence_rows_sha256"),
        label="acceptance_evidence_rows_sha256",
    )
    bridge = _mapping(receipt.get("ordinal_bridge"), label="ordinal_bridge")
    _exact(
        bridge,
        {
            "prepared_export_base",
            "a5_entry_base",
            "prepared_book_base",
            "a5_lineup_rank_base",
            "rule",
        },
        label="ordinal_bridge",
    )
    expected_bridge = {
        "prepared_export_base": 0,
        "a5_entry_base": 1,
        "prepared_book_base": 0,
        "a5_lineup_rank_base": 1,
        "rule": "a5_entry_index=export_ordinal+1;a5_lineup_rank=paid_input_book_ordinal+1",
    }
    if bridge != expected_bridge:
        _fail("the explicit 0-to-1 ordinal bridge differs")
    rows: list[dict[str, object]] = []
    for ordinal, raw in enumerate(_sequence(receipt.get("entries"), label="entries")):
        row = _mapping(raw, label=f"entries[{ordinal}]")
        _exact(
            row,
            {
                "entry_id",
                "a5_entry_index",
                "a5_lineup_rank",
                "lineup_id",
                "roster_sha256",
                "internal_player_ids",
                "slot_dk_draftable_ids",
            },
            label=f"entries[{ordinal}]",
        )
        entry_id = _string(row.get("entry_id"), label="entry_id")
        if not entry_id.isdigit():
            _fail("DraftKings Entry ID must be numeric")
        internal = _int_ids(row.get("internal_player_ids"), label="internal_player_ids")
        roster_sha = _sha(row.get("roster_sha256"), label="roster_sha256")
        if roster_sha != canonical_sha256(sorted(internal)):
            _fail("accepted roster SHA differs from its exact internal player IDs")
        rows.append(
            {
                "entry_id": entry_id,
                "a5_entry_index": _integer(
                    row.get("a5_entry_index"), label="a5_entry_index", minimum=1
                ),
                "a5_lineup_rank": _integer(
                    row.get("a5_lineup_rank"), label="a5_lineup_rank", minimum=1
                ),
                "lineup_id": _lineup(row.get("lineup_id"), label="lineup_id"),
                "roster_sha256": roster_sha,
                "internal_player_ids": internal,
                "slot_dk_draftable_ids": _draftable_ids(
                    row.get("slot_dk_draftable_ids"), label="slot_dk_draftable_ids"
                ),
            }
        )
    if len(rows) != k or [row["a5_entry_index"] for row in rows] != list(
        range(1, k + 1)
    ):
        _fail("accepted entries must cover exact A5 entry indices 1..K")
    if (
        len({row["entry_id"] for row in rows}) != k
        or len({row["lineup_id"] for row in rows}) != k
    ):
        _fail("accepted entries contain a duplicate Entry ID or lineup")
    replay_evidence_rows = [
        {
            "entry_id": row["entry_id"],
            "contest_id": contest["contest_id"],
            "draft_group_id": contest["draft_group_id"],
            "slot_dk_draftable_ids": row["slot_dk_draftable_ids"],
            "status": "accepted",
        }
        for row in sorted(rows, key=lambda item: str(item["entry_id"]))
    ]
    if evidence_rows_sha != canonical_sha256(replay_evidence_rows):
        _fail("acceptance evidence row projection SHA differs")
    paid_book = next(
        row for row in man["a5_binding"]["book_bindings"] if row["policy"] == "P_MIX"
    )
    expected_by_rank = {int(row["lineup_rank"]): row for row in paid_book["entries"]}
    paid_edges = {
        int(row["entry_index"]): row for row in man["a5_binding"]["paid_entry_edges"]
    }
    for row in rows:
        edge = paid_edges[int(row["a5_entry_index"])]
        expected_entry = expected_by_rank[int(row["a5_lineup_rank"])]
        if edge["lineup_rank"] != row["a5_lineup_rank"] or any(
            row[field] != expected_entry[field]
            for field in (
                "lineup_id",
                "roster_sha256",
                "internal_player_ids",
                "slot_dk_draftable_ids",
            )
        ):
            _fail("accepted Entry ID/roster differs from its A5 edge and paid book")
    normalized = {
        "schema_version": ACCEPTANCE_SCHEMA,
        "complete": True,
        "accepted_at": accepted_text,
        "contest_role": role,
        "contest_id": contest["contest_id"],
        "draft_group_id": contest["draft_group_id"],
        "planned_entries": k,
        "allocation_sha256": a5["allocation_sha256"],
        "allocation_identity": allocation_identity,
        "manifest_sha256": man["manifest_sha256"],
        "manifest_identity": manifest_identity,
        "prepared_capture_identity": prepared_identity,
        "filled_upload_identity": upload_identity,
        "acceptance_evidence_identity": evidence_identity,
        "acceptance_evidence_rows_sha256": evidence_rows_sha,
        "ordinal_bridge": expected_bridge,
        "entries": rows,
        "outcome_fields_read": [],
        "acceptance_sha256": receipt["acceptance_sha256"],
    }
    if normalized != receipt:
        _fail("entry acceptance does not replay exact canonical semantics")
    return normalized


def build_week1_entry_acceptance_v1(
    *,
    manifest: object,
    manifest_identity: object,
    allocation: object,
    allocation_identity: object,
    prepared_capture: object,
    prepared_capture_identity: object,
    filled_upload_identity: object,
    acceptance_evidence_rows: object,
    acceptance_evidence_identity: object,
    accepted_at: str,
) -> dict[str, object]:
    """Bind prepared CSV rows to accepted DK Entry IDs and the exact A5 edge."""
    a5 = _allocation(allocation)
    man = _manifest_core(manifest, allocation=a5)
    contest, binding = man["contest"], man["a5_binding"]
    k = int(binding["planned_entries"])
    prepared = _mapping(prepared_capture, label="prepared_capture")
    required_prepared = {
        "schema_version",
        "contest_id",
        "draft_group_id",
        "salary_catalog_sha256",
        "csv_sha256",
        "csv_bytes",
        "paid_export_receipt_sha256",
        "entries",
        "uses_realized_outcomes",
        "post_lock_data_read",
    }
    _exact(prepared, required_prepared, label="prepared_capture")
    if (
        prepared.get("schema_version") != "paid-entry-capture/v1"
        or prepared.get("contest_id") != contest["contest_id"]
        or prepared.get("draft_group_id") != contest["draft_group_id"]
        or prepared.get("uses_realized_outcomes") is not False
        or prepared.get("post_lock_data_read") is not False
    ):
        _fail("prepared entry capture contest or no-outcome boundary differs")
    prepared_identity = _prelock_identity(
        prepared_capture_identity, label="prepared_capture_identity"
    )
    if prepared_identity["sha256"] != canonical_sha256(prepared):
        _fail("prepared capture identity differs from exact prepared payload")
    upload_identity = _prelock_identity(
        filled_upload_identity, label="filled_upload_identity"
    )
    if upload_identity["sha256"] != prepared.get("csv_sha256") or upload_identity[
        "bytes"
    ] != prepared.get("csv_bytes"):
        _fail("filled upload identity differs from prepared CSV")
    prepared_rows = [
        _mapping(row, label=f"prepared.entries[{i}]")
        for i, row in enumerate(
            _sequence(prepared.get("entries"), label="prepared.entries")
        )
    ]
    if len(prepared_rows) != k:
        _fail("prepared capture does not contain exact contest K")
    evidence_rows = [
        _mapping(row, label=f"acceptance_evidence[{i}]")
        for i, row in enumerate(
            _sequence(acceptance_evidence_rows, label="acceptance_evidence_rows")
        )
    ]
    by_entry: dict[str, dict[str, object]] = {}
    for i, row in enumerate(evidence_rows):
        _exact(
            row,
            {
                "entry_id",
                "contest_id",
                "draft_group_id",
                "slot_dk_draftable_ids",
                "status",
            },
            label=f"acceptance_evidence[{i}]",
        )
        entry_id = _string(row.get("entry_id"), label="acceptance entry_id")
        if (
            row.get("contest_id") != contest["contest_id"]
            or row.get("draft_group_id") != contest["draft_group_id"]
            or row.get("status") != "accepted"
        ):
            _fail("acceptance evidence contest, draft group, or status differs")
        if entry_id in by_entry:
            _fail("acceptance evidence repeats a DraftKings Entry ID")
        by_entry[entry_id] = {
            **row,
            "slot_dk_draftable_ids": _draftable_ids(
                row.get("slot_dk_draftable_ids"), label="acceptance slot IDs"
            ),
        }
    if len(by_entry) != k:
        _fail("acceptance evidence does not contain exact contest K")
    paid_book = next(
        row for row in binding["book_bindings"] if row["policy"] == "P_MIX"
    )
    book_by_rank = {int(row["lineup_rank"]): row for row in paid_book["entries"]}
    output: list[dict[str, object]] = []
    for raw in sorted(
        prepared_rows, key=lambda row: int(row.get("export_ordinal", -1))
    ):
        _exact(
            raw,
            {
                "export_ordinal",
                "entry_id",
                "internal_player_ids",
                "dk_draftable_ids",
                "paid_input_book_ordinal",
                "slot_dk_draftable_ids",
            },
            label="prepared entry",
        )
        export_ordinal = _integer(raw.get("export_ordinal"), label="export_ordinal")
        book_ordinal = _integer(
            raw.get("paid_input_book_ordinal"), label="paid_input_book_ordinal"
        )
        entry_id = _string(raw.get("entry_id"), label="prepared entry_id")
        a5_index, rank = export_ordinal + 1, book_ordinal + 1
        if a5_index > k or rank > k or entry_id not in by_entry:
            _fail("prepared ordinal or Entry ID falls outside exact A5 acceptance")
        expected = book_by_rank[rank]
        internal = sorted(
            _int_ids(
                raw.get("internal_player_ids"), label="prepared internal_player_ids"
            )
        )
        slot_ids = _draftable_ids(
            raw.get("slot_dk_draftable_ids"), label="prepared slot_dk_draftable_ids"
        )
        if (
            raw.get("dk_draftable_ids") != sorted(slot_ids)
            or internal != sorted(expected["internal_player_ids"])
            or slot_ids != expected["slot_dk_draftable_ids"]
            or by_entry[entry_id]["slot_dk_draftable_ids"] != slot_ids
        ):
            _fail("prepared or accepted DK roster differs from the frozen paid book")
        output.append(
            {
                "entry_id": entry_id,
                "a5_entry_index": a5_index,
                "a5_lineup_rank": rank,
                "lineup_id": expected["lineup_id"],
                "roster_sha256": expected["roster_sha256"],
                "internal_player_ids": list(expected["internal_player_ids"]),
                "slot_dk_draftable_ids": slot_ids,
            }
        )
    accepted_text, _ = _timestamp(accepted_at, label="accepted_at")
    normalized_manifest_identity = _manifest_identity(
        manifest_identity, man, label="manifest_identity"
    )
    normalized_allocation_identity = _prelock_identity(
        allocation_identity, label="allocation_identity"
    )
    if normalized_allocation_identity["sha256"] != a5["allocation_sha256"]:
        _fail("allocation identity differs from exact A5 root")
    normalized_evidence_identity = _prelock_identity(
        acceptance_evidence_identity, label="acceptance_evidence_identity"
    )
    normalized_evidence_rows = [
        {
            "entry_id": entry_id,
            "contest_id": contest["contest_id"],
            "draft_group_id": contest["draft_group_id"],
            "slot_dk_draftable_ids": by_entry[entry_id]["slot_dk_draftable_ids"],
            "status": "accepted",
        }
        for entry_id in sorted(by_entry)
    ]
    body: dict[str, object] = {
        "schema_version": ACCEPTANCE_SCHEMA,
        "complete": True,
        "accepted_at": accepted_text,
        "contest_role": contest["contest_role"],
        "contest_id": contest["contest_id"],
        "draft_group_id": contest["draft_group_id"],
        "planned_entries": k,
        "allocation_sha256": a5["allocation_sha256"],
        "allocation_identity": normalized_allocation_identity,
        "manifest_sha256": man["manifest_sha256"],
        "manifest_identity": normalized_manifest_identity,
        "prepared_capture_identity": prepared_identity,
        "filled_upload_identity": upload_identity,
        "acceptance_evidence_identity": normalized_evidence_identity,
        "acceptance_evidence_rows_sha256": canonical_sha256(normalized_evidence_rows),
        "ordinal_bridge": {
            "prepared_export_base": 0,
            "a5_entry_base": 1,
            "prepared_book_base": 0,
            "a5_lineup_rank_base": 1,
            "rule": "a5_entry_index=export_ordinal+1;a5_lineup_rank=paid_input_book_ordinal+1",
        },
        "entries": output,
        "outcome_fields_read": [],
    }
    return _acceptance_core(
        _finish(body, field="acceptance_sha256"), manifest=man, allocation=a5
    )


def validate_week1_entry_acceptance_v1(
    value: object, *, manifest: object, allocation: object
) -> dict[str, object]:
    return _acceptance_core(value, manifest=manifest, allocation=allocation)


def build_week1_acceptance_root_v1(
    *,
    allocation: object,
    allocation_identity: object,
    manifests_by_role: Mapping[str, object],
    receipts_by_role: Mapping[str, object],
    receipt_identities_by_role: Mapping[str, object],
    frozen_at: str,
) -> dict[str, object]:
    a5 = _allocation(allocation)
    if (
        set(manifests_by_role) != set(EXPECTED_ROLE_ENTRIES)
        or set(receipts_by_role) != set(EXPECTED_ROLE_ENTRIES)
        or set(receipt_identities_by_role) != set(EXPECTED_ROLE_ENTRIES)
    ):
        _fail("four-contest acceptance root requires all exact A5 roles")
    rows: list[dict[str, object]] = []
    entry_ids: set[str] = set()
    for role in EXPECTED_ROLE_ENTRIES:
        manifest = _manifest_core(manifests_by_role[role], allocation=a5)
        receipt = _acceptance_core(
            receipts_by_role[role], manifest=manifest, allocation=a5
        )
        identity = _prelock_identity(
            receipt_identities_by_role[role], label=f"{role}.acceptance_identity"
        )
        if identity["sha256"] != receipt["acceptance_sha256"]:
            _fail("acceptance receipt identity differs")
        ids = {str(row["entry_id"]) for row in receipt["entries"]}
        if entry_ids & ids:
            _fail("DraftKings Entry IDs repeat across contests")
        entry_ids |= ids
        rows.append(
            {
                "contest_role": role,
                "contest_id": manifest["contest"]["contest_id"],
                "draft_group_id": manifest["contest"]["draft_group_id"],
                "planned_entries": EXPECTED_ROLE_ENTRIES[role],
                "manifest_sha256": manifest["manifest_sha256"],
                "acceptance_sha256": receipt["acceptance_sha256"],
                "acceptance_identity": identity,
            }
        )
    total = sum(int(row["planned_entries"]) for row in rows)
    if total != 90 or len(entry_ids) != 90:
        _fail("four-contest acceptance root is not complete at 90 paid entries")
    allocation_id = _prelock_identity(allocation_identity, label="allocation_identity")
    if allocation_id["sha256"] != a5["allocation_sha256"]:
        _fail("acceptance root allocation identity differs")
    frozen_text, frozen_dt = _timestamp(frozen_at, label="frozen_at")
    _, lock_dt = _timestamp(a5["lock_utc"], label="A5 lock_utc")
    if frozen_dt >= lock_dt:
        _fail("acceptance root must freeze before slate lock")
    if any(
        _timestamp(receipts_by_role[role]["accepted_at"], label="accepted_at")[1]
        > frozen_dt
        for role in EXPECTED_ROLE_ENTRIES
    ):
        _fail("acceptance root cannot predate a bound acceptance receipt")
    body: dict[str, object] = {
        "schema_version": ACCEPTANCE_ROOT_SCHEMA,
        "complete": True,
        "frozen_at": frozen_text,
        "allocation_id": ALLOCATION_ID,
        "allocation_sha256": a5["allocation_sha256"],
        "allocation_identity": allocation_id,
        "required_contests": rows,
        "accepted_entry_count": 90,
        "accepted_entry_ids_sha256": canonical_sha256(sorted(entry_ids)),
        "outcome_fields_read": [],
    }
    return _finish(body, field="acceptance_root_sha256")


def validate_week1_acceptance_root_v1(
    value: object,
    *,
    allocation: object,
    manifests_by_role: Mapping[str, object],
    receipts_by_role: Mapping[str, object],
) -> dict[str, object]:
    root = _self_hash(
        _mapping(value, label="acceptance root"),
        field="acceptance_root_sha256",
        label="acceptance root",
    )
    _exact(
        root,
        {
            "schema_version",
            "complete",
            "frozen_at",
            "allocation_id",
            "allocation_sha256",
            "allocation_identity",
            "required_contests",
            "accepted_entry_count",
            "accepted_entry_ids_sha256",
            "outcome_fields_read",
            "acceptance_root_sha256",
        },
        label="acceptance root",
    )
    if (
        root.get("schema_version") != ACCEPTANCE_ROOT_SCHEMA
        or root.get("complete") is not True
        or root.get("outcome_fields_read") != []
    ):
        _fail("acceptance root schema, completeness, or no-outcome boundary differs")
    identities: dict[str, object] = {}
    for row in _sequence(root.get("required_contests"), label="required_contests"):
        item = _mapping(row, label="required_contest")
        _exact(
            item,
            {
                "contest_role",
                "contest_id",
                "draft_group_id",
                "planned_entries",
                "manifest_sha256",
                "acceptance_sha256",
                "acceptance_identity",
            },
            label="required_contest",
        )
        role = _string(item.get("contest_role"), label="required_contest role")
        if role in identities:
            _fail("acceptance root repeats a contest role")
        identities[role] = item.get("acceptance_identity")
    replay = build_week1_acceptance_root_v1(
        allocation=allocation,
        allocation_identity=root["allocation_identity"],
        manifests_by_role=manifests_by_role,
        receipts_by_role=receipts_by_role,
        receipt_identities_by_role=identities,
        frozen_at=str(root["frozen_at"]),
    )
    if replay != root:
        _fail("acceptance root does not exactly replay")
    return root


def _standings_rows(
    value: object, *, observed_final_field_size: int
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for i, raw in enumerate(_sequence(value, label="standings_rows")):
        row = _mapping(raw, label=f"standings_rows[{i}]")
        _exact(
            row,
            {"entry_id", "rank", "points_micropoints", "payout_micro"},
            label=f"standings_rows[{i}]",
        )
        entry_id = _string(row.get("entry_id"), label="standings entry_id")
        if not entry_id.isdigit():
            _fail("standings Entry ID must be numeric")
        rows.append(
            {
                "entry_id": entry_id,
                "rank": _integer(row.get("rank"), label="standings rank", minimum=1),
                "points_micropoints": _integer(
                    row.get("points_micropoints"), label="points_micropoints"
                ),
                "payout_micro": _integer(row.get("payout_micro"), label="payout_micro"),
            }
        )
    if len(rows) != observed_final_field_size:
        _fail("normalized standings row count differs from observed final field size")
    if len({row["entry_id"] for row in rows}) != len(rows):
        _fail("normalized standings repeat an Entry ID")
    ordered = sorted(
        rows, key=lambda row: (-int(row["points_micropoints"]), str(row["entry_id"]))
    )
    offset = 0
    while offset < len(ordered):
        points = int(ordered[offset]["points_micropoints"])
        end = offset + 1
        while end < len(ordered) and int(ordered[end]["points_micropoints"]) == points:
            end += 1
        expected_rank = offset + 1
        if any(row["rank"] != expected_rank for row in ordered[offset:end]):
            _fail("standings ranks do not match competition ranking by points")
        offset = end
    return rows


def build_week1_settlement_v1(
    *,
    manifest: object,
    manifest_identity: object,
    allocation: object,
    allocation_identity: object,
    acceptance_root: object,
    acceptance_root_identity: object,
    manifests_by_role: Mapping[str, object],
    receipts_by_role: Mapping[str, object],
    standings_source_identity: object,
    normalized_standings_identity: object,
    standings_rows: object,
    observed_final_field_size: int,
    captured_at: str,
    confirm_settled: bool,
    confirm_full_field: bool,
    correction_lineage: object,
) -> dict[str, object]:
    """Build an outcome-bearing receipt without changing any pre-lock artifact."""
    a5 = _allocation(allocation)
    man = _manifest_core(manifest, allocation=a5)
    root = validate_week1_acceptance_root_v1(
        acceptance_root,
        allocation=a5,
        manifests_by_role=manifests_by_role,
        receipts_by_role=receipts_by_role,
    )
    if confirm_settled is not True or confirm_full_field is not True:
        _fail("settlement requires explicit settled and complete-field confirmations")
    final_size = _integer(
        observed_final_field_size, label="observed_final_field_size", minimum=1
    )
    capacity = int(man["contest"]["advertised_field_capacity"])
    if final_size > capacity:
        _fail("observed final field size exceeds advertised capacity")
    captured_text, captured = _timestamp(captured_at, label="captured_at")
    _, lock_at = _timestamp(man["contest"]["lock_at"], label="lock_at")
    if captured <= lock_at:
        _fail("settlement capture must occur after slate lock")
    rows = _standings_rows(standings_rows, observed_final_field_size=final_size)
    normalized_identity = _identity(
        normalized_standings_identity, label="normalized_standings_identity"
    )
    if normalized_identity["sha256"] != canonical_sha256(rows):
        _fail("normalized standings identity differs from exact normalized rows")
    _, payout_by_rank = _normalize_payout_ladder(
        man["payout_ladder"], capacity=capacity
    )
    policy = man["contest"]["payout_ladder_underfill_policy"]
    if final_size < capacity and policy == "official-settlement-ladder":
        _fail(
            "underfilled official-settlement-ladder contest requires a successor schema with its final ladder"
        )
    groups: dict[int, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        groups[int(row["points_micropoints"])].append(row)
    maximum_residual = Decimal(0)
    for points, tied in groups.items():
        rank, tie_size = int(tied[0]["rank"]), len(tied)
        scheduled = sum(
            payout_by_rank.get(position, 0)
            for position in range(rank, min(final_size, rank + tie_size - 1) + 1)
        )
        expected_each = Decimal(scheduled) / Decimal(tie_size)
        actual = {int(row["payout_micro"]) for row in tied}
        if len(actual) != 1:
            _fail(f"tied entries disagree on payout at score {points}")
        residual = abs(Decimal(next(iter(actual))) - expected_each)
        maximum_residual = max(maximum_residual, residual)
        if residual > _CENT_MICRO:
            _fail("tie-split payout does not reconcile")
    scheduled_applicable = sum(
        payout_by_rank.get(rank, 0) for rank in range(1, final_size + 1)
    )
    observed_payout = sum(int(row["payout_micro"]) for row in rows)
    if abs(observed_payout - scheduled_applicable) > final_size * _CENT_MICRO:
        _fail("observed payouts do not reconcile over applicable occupied ranks")
    role = str(man["contest"]["contest_role"])
    accepted = _acceptance_core(receipts_by_role[role], manifest=man, allocation=a5)
    field_entry_ids = {str(row["entry_id"]) for row in rows}
    accepted_ids = {str(row["entry_id"]) for row in accepted["entries"]}
    if not accepted_ids.issubset(field_entry_ids):
        _fail("one or more accepted paid Entry IDs are absent from final standings")
    manifest_id = _manifest_identity(manifest_identity, man, label="manifest_identity")
    allocation_id = _prelock_identity(allocation_identity, label="allocation_identity")
    root_id = _prelock_identity(
        acceptance_root_identity, label="acceptance_root_identity"
    )
    if (
        allocation_id["sha256"] != a5["allocation_sha256"]
        or root_id["sha256"] != root["acceptance_root_sha256"]
    ):
        _fail("settlement allocation or acceptance-root identity differs")
    body: dict[str, object] = {
        "schema_version": SETTLEMENT_SCHEMA,
        "complete": True,
        "captured_at": captured_text,
        "contest_role": role,
        "contest_id": man["contest"]["contest_id"],
        "draft_group_id": man["contest"]["draft_group_id"],
        "manifest_sha256": man["manifest_sha256"],
        "manifest_identity": manifest_id,
        "allocation_sha256": a5["allocation_sha256"],
        "allocation_identity": allocation_id,
        "acceptance_root_sha256": root["acceptance_root_sha256"],
        "acceptance_root_identity": root_id,
        "advertised_field_capacity": capacity,
        "observed_final_field_size": final_size,
        "underfilled_vs_advertised": final_size < capacity,
        "settled_confirmed": True,
        "full_field_confirmed": True,
        "standings_source_identity": _identity(
            standings_source_identity, label="standings_source_identity"
        ),
        "normalized_standings_identity": normalized_identity,
        "normalized_standings_rows_sha256": canonical_sha256(rows),
        "applicable_payout_reconciliation": {
            "underfill_policy": policy,
            "applicable_rank_count": final_size,
            "scheduled_applicable_prize_pool_micro": scheduled_applicable,
            "observed_prize_pool_micro": observed_payout,
            "maximum_tie_rounding_residual_micro": int(maximum_residual),
            "reconciled": True,
        },
        "accepted_entries_reconciled": len(accepted_ids),
        "correction_lineage": _correction(
            correction_lineage,
            label="settlement correction_lineage",
            hash_field="supersedes_settlement_sha256",
        ),
        "outcome_fields_read": [
            "observed_final_field_size",
            "rank",
            "points_micropoints",
            "payout_micro",
        ],
    }
    return _finish(body, field="settlement_sha256")


def validate_week1_settlement_v1(
    value: object,
    *,
    manifest: object,
    allocation: object,
    acceptance_root: object,
    manifests_by_role: Mapping[str, object],
    receipts_by_role: Mapping[str, object],
    standings_rows: object,
) -> dict[str, object]:
    """Replay a settlement against separately reopened normalized standings."""
    settlement = _self_hash(
        _mapping(value, label="settlement"),
        field="settlement_sha256",
        label="settlement",
    )
    _exact(
        settlement,
        {
            "schema_version",
            "complete",
            "captured_at",
            "contest_role",
            "contest_id",
            "draft_group_id",
            "manifest_sha256",
            "manifest_identity",
            "allocation_sha256",
            "allocation_identity",
            "acceptance_root_sha256",
            "acceptance_root_identity",
            "advertised_field_capacity",
            "observed_final_field_size",
            "underfilled_vs_advertised",
            "settled_confirmed",
            "full_field_confirmed",
            "standings_source_identity",
            "normalized_standings_identity",
            "normalized_standings_rows_sha256",
            "applicable_payout_reconciliation",
            "accepted_entries_reconciled",
            "correction_lineage",
            "outcome_fields_read",
            "settlement_sha256",
        },
        label="settlement",
    )
    if (
        settlement.get("schema_version") != SETTLEMENT_SCHEMA
        or settlement.get("complete") is not True
    ):
        _fail("settlement schema or completeness differs")
    replay = build_week1_settlement_v1(
        manifest=manifest,
        manifest_identity=settlement["manifest_identity"],
        allocation=allocation,
        allocation_identity=settlement["allocation_identity"],
        acceptance_root=acceptance_root,
        acceptance_root_identity=settlement["acceptance_root_identity"],
        manifests_by_role=manifests_by_role,
        receipts_by_role=receipts_by_role,
        standings_source_identity=settlement["standings_source_identity"],
        normalized_standings_identity=settlement["normalized_standings_identity"],
        standings_rows=standings_rows,
        observed_final_field_size=int(settlement["observed_final_field_size"]),
        captured_at=str(settlement["captured_at"]),
        confirm_settled=settlement["settled_confirmed"] is True,
        confirm_full_field=settlement["full_field_confirmed"] is True,
        correction_lineage=settlement["correction_lineage"],
    )
    if replay != settlement:
        _fail("settlement does not exactly replay against normalized standings")
    return settlement


__all__ = [
    "ACCEPTANCE_ROOT_SCHEMA",
    "ACCEPTANCE_SCHEMA",
    "BOOK_BINDING_SCHEMA",
    "EXPECTED_ROLE_ENTRIES",
    "EXPECTED_SLATE_ID",
    "PRELOCK_SCHEMA",
    "SETTLEMENT_SCHEMA",
    "Week1A5CaptureContractError",
    "build_week1_acceptance_root_v1",
    "build_week1_entry_acceptance_v1",
    "build_week1_prelock_manifest_v3",
    "build_week1_settlement_v1",
    "validate_week1_acceptance_root_v1",
    "validate_week1_entry_acceptance_v1",
    "validate_week1_prelock_manifest_v3",
    "validate_week1_settlement_v1",
]
