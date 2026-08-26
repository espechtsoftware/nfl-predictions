from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
from typing import Any

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog


OUTPUT_PREFIX = "gs://fixture-bucket/r6-player-catalog-v1/"
RELEASE_ID = "r6-player-catalog-release-fixture-v1"
MODULE_PATH = "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py"


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(label: str, ordinal: int, raw: bytes | None = None) -> dict[str, object]:
    body = raw if raw is not None else f"{label}:{ordinal}".encode("utf-8")
    return {
        "uri": f"gs://fixture-bucket/authority/{label}-{ordinal:04d}.json",
        "generation": str(10_000 + ordinal),
        "sha256": sha256(body).hexdigest(),
        "bytes": len(body),
    }


def _root(label: str = "official") -> dict[str, object]:
    return {
        "g0_authority_lock_schema": catalog.G0_AUTHORITY_LOCK_SCHEMA,
        "g0_authority_lock_relative_path": (
            "reports/corpus-parametric-runs/fixture/g0-authority-lock-v1.json"
        ),
        "g0_authority_lock_file_sha256": _digest(f"{label}:root-file"),
        "g0_authority_lock_sha256": _digest(f"{label}:root-internal"),
        "source_commit_sha": "a" * 40 if label == "official" else "b" * 40,
        "panel_object_identity": _identity(f"{label}-panel", 0),
        "panel_index_sha256": _digest(f"{label}:panel-index"),
        "accepted_slate_count": catalog.TASK_COUNT,
    }


CODE_IDENTITY = {
    "source_commit_sha": "c" * 40,
    "module_path": MODULE_PATH,
    "module_sha256": _digest("catalog-module"),
}
SOURCE_IDENTITY = _identity("later-source-freeze", 0)
SOURCE_MANIFEST_SHA = _digest("later-source-internal-manifest")
COMPLETION_IDENTITY = _identity("artifact-source-completion", 0)
COMPLETION_INTERNAL_SHA = _digest("artifact-source-internal-completion")


def _players(source_ordinal: int) -> list[dict[str, object]]:
    return [
        {
            "id": f"00-{source_ordinal:07d}-a",
            "pos": "WR",
            "team": "AAA",
            "opp": "BBB",
            "game_id": f"AAA|BBB|{source_ordinal:02d}",
            "salary": 5_000 + source_ordinal,
        },
        {
            "id": f"00-{source_ordinal:07d}-b",
            "pos": "DST",
            "team": "BBB",
            "opp": "AAA",
            "game_id": f"AAA|BBB|{source_ordinal:02d}",
            "salary": 3_000 + source_ordinal,
        },
    ]


def _member(source_ordinal: int) -> dict[str, object]:
    lane_id = "v12a" if source_ordinal < 28 else "v12b"
    task_ordinal = source_ordinal if lane_id == "v12a" else source_ordinal - 28
    slate = catalog.expected_slate_for_source_task(source_ordinal)
    return {
        "lane_id": lane_id,
        "lane_ordinal": 0 if lane_id == "v12a" else 1,
        "task_ordinal": task_ordinal,
        "source_task_ordinal": source_ordinal,
        "task_id": catalog.task_id_for_source_task(source_ordinal),
        "slate_id": slate["slate_id"],
        "accepted_slate_membership_sha256": _digest(
            f"membership:{source_ordinal}"
        ),
        "task_acceptance_identity": _identity("task-acceptance", source_ordinal),
        "carrier_identity": _identity("task-carrier", source_ordinal),
        "source_task_authority_sha256": _digest(
            f"source-task-authority:{source_ordinal}"
        ),
    }


def _source(
    source_ordinal: int,
    players: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    retained_players = list(players if players is not None else _players(source_ordinal))
    player_ids = [str(player["id"]) for player in retained_players]
    return {
        "later_source_freeze_identity": SOURCE_IDENTITY,
        "later_source_freeze_manifest_sha256": SOURCE_MANIFEST_SHA,
        "source_task_ordinal": source_ordinal,
        "slate": catalog.expected_slate_for_source_task(source_ordinal),
        "catalog_sha256": catalog.canonical_sha256(retained_players),
        "catalog_player_count": len(retained_players),
        "catalog_player_ids_sha256": catalog.canonical_sha256(player_ids),
    }


def _completion(
    source_ordinal: int,
    *,
    member: Mapping[str, object] | None = None,
    source: Mapping[str, object] | None = None,
) -> dict[str, object]:
    retained_member = dict(member if member is not None else _member(source_ordinal))
    retained_source = dict(source if source is not None else _source(source_ordinal))
    return {
        "artifact_source_authority_completion_identity": COMPLETION_IDENTITY,
        "artifact_source_authority_completion_sha256": COMPLETION_INTERNAL_SHA,
        "later_source_freeze_identity": retained_source[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_manifest_sha256": retained_source[
            "later_source_freeze_manifest_sha256"
        ],
        "source_task_ordinal": source_ordinal,
        "slate": retained_source["slate"],
        "universe_scope": catalog.UNIVERSE_SCOPE,
        "task_source_authority_sha256": retained_member[
            "source_task_authority_sha256"
        ],
        "catalog_sha256": retained_source["catalog_sha256"],
        "catalog_player_count": retained_source["catalog_player_count"],
        "catalog_player_ids_sha256": retained_source[
            "catalog_player_ids_sha256"
        ],
    }


def _derivation(
    source_ordinal: int,
    *,
    root: Mapping[str, object] | None = None,
    players: Sequence[Mapping[str, object]] | None = None,
    member: Mapping[str, object] | None = None,
    source: Mapping[str, object] | None = None,
    completion: Mapping[str, object] | None = None,
    code_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    retained_players = list(players if players is not None else _players(source_ordinal))
    retained_member = dict(member if member is not None else _member(source_ordinal))
    retained_source = dict(
        source if source is not None else _source(source_ordinal, retained_players)
    )
    retained_completion = dict(
        completion
        if completion is not None
        else _completion(
            source_ordinal,
            member=retained_member,
            source=retained_source,
        )
    )
    return catalog.build_derivation_receipt_v1(
        tracked_root_binding=root if root is not None else _root(),
        accepted_member_binding=retained_member,
        source_catalog_binding=retained_source,
        artifact_source_completion_binding=retained_completion,
        structural_players=retained_players,
        derivation_code_identity=(
            code_identity if code_identity is not None else CODE_IDENTITY
        ),
    )


def _rehash(body: Mapping[str, object], field: str) -> dict[str, object]:
    retained = deepcopy(dict(body))
    retained.pop(field, None)
    retained[field] = catalog.canonical_sha256(retained)
    return retained


class MemoryStore:
    """Generation-aware exact reader plus strict create-once fixture publisher."""

    def __init__(self) -> None:
        self.next_generation = 100_000
        self.by_key: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, dict[str, object]] = {}

    def put_body(self, uri: str, body: Mapping[str, object]) -> dict[str, object]:
        raw = catalog.canonical_json_bytes(body)
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.by_key[(uri, str(identity["generation"]))] = raw
        self.current[uri] = deepcopy(identity)
        return deepcopy(identity)

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if uri in self.current:
            retained = deepcopy(self.current[uri])
            retained_raw = self.read_exact(retained)
            if retained_raw == raw:
                return retained
            raise catalog.CorpusR6PlayerCatalogV1Error(
                "different-byte create-once collision"
            )
        parsed = batch.parse_canonical_json_bytes(raw, label="fixture object")
        assert isinstance(parsed, Mapping)
        return self.put_body(uri, parsed)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        normalized = catalog.normalize_object_identity(
            identity, label="fixture exact-read identity"
        )
        key = (str(normalized["uri"]), str(normalized["generation"]))
        raw = self.by_key.get(key)
        if raw is None:
            raise catalog.CorpusR6PlayerCatalogV1Error("fixture object is absent")
        current_identity = {
            "uri": normalized["uri"],
            "generation": normalized["generation"],
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if current_identity != normalized:
            raise catalog.CorpusR6PlayerCatalogV1Error(
                "fixture exact identity differs"
            )
        return bytes(raw)


def _publish_one(
    store: MemoryStore,
    source_ordinal: int,
    *,
    output_prefix: str = OUTPUT_PREFIX,
    root: Mapping[str, object] | None = None,
    players: Sequence[Mapping[str, object]] | None = None,
    member: Mapping[str, object] | None = None,
    source: Mapping[str, object] | None = None,
    completion: Mapping[str, object] | None = None,
    code_identity: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    retained_players = list(players if players is not None else _players(source_ordinal))
    retained_member = dict(member if member is not None else _member(source_ordinal))
    retained_source = dict(
        source if source is not None else _source(source_ordinal, retained_players)
    )
    retained_completion = dict(
        completion
        if completion is not None
        else _completion(
            source_ordinal,
            member=retained_member,
            source=retained_source,
        )
    )
    derivation = _derivation(
        source_ordinal,
        root=root,
        players=retained_players,
        member=retained_member,
        source=retained_source,
        completion=retained_completion,
        code_identity=code_identity,
    )
    identities = catalog.publish_catalog_pair_create_once_v1(
        output_prefix=output_prefix,
        derivation_receipt=derivation,
        structural_players=retained_players,
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
    )
    return {
        "players": retained_players,
        "member": retained_member,
        "source": retained_source,
        "completion": retained_completion,
        "derivation": derivation,
        **identities,
    }


def _publish_lattice(
    *,
    root: Mapping[str, object] | None = None,
    output_prefix: str = OUTPUT_PREFIX,
    code_identity: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    store = MemoryStore()
    retained_root = dict(root if root is not None else _root())
    rows = [
        _publish_one(
            store,
            source_ordinal,
            output_prefix=output_prefix,
            root=retained_root,
            code_identity=code_identity,
        )
        for source_ordinal in range(catalog.TASK_COUNT)
    ]
    return {
        "store": store,
        "root": retained_root,
        "members": [row["member"] for row in rows],
        "sources": [row["source"] for row in rows],
        "completions": [row["completion"] for row in rows],
        "catalog_identities": [row["player_catalog_identity"] for row in rows],
        "rows": rows,
    }


@pytest.mark.parametrize(
    ("source_ordinal", "season", "week"),
    [
        (0, 2023, 1),
        (17, 2023, 18),
        (18, 2024, 1),
        (35, 2024, 18),
        (36, 2025, 1),
        (53, 2025, 18),
    ],
)
def test_frozen_source_task_lattice(
    source_ordinal: int, season: int, week: int
) -> None:
    assert catalog.expected_slate_for_source_task(source_ordinal) == {
        "season": season,
        "week": week,
        "slate_id": f"{season}-w{week:02d}",
    }
    assert catalog.task_id_for_source_task(source_ordinal) == (
        f"slate-{season}-w{week}"
    )


@pytest.mark.parametrize(
    ("source_ordinal", "lane_id", "task_ordinal"),
    [
        (27, "v12a", 27),
        (28, "v12b", 0),
        (53, "v12b", 25),
    ],
)
def test_frozen_member_lane_boundary(
    source_ordinal: int, lane_id: str, task_ordinal: int
) -> None:
    member = catalog.normalize_member_binding(_member(source_ordinal))
    assert member["lane_id"] == lane_id
    assert member["task_ordinal"] == task_ordinal


@pytest.mark.parametrize(
    ("source_ordinal", "lane_id", "lane_ordinal", "task_ordinal"),
    [
        (0, "v12b", 1, 0),
        (0, "v12a", 0, 1),
        (28, "v12a", 0, 0),
    ],
)
def test_member_rejects_valid_but_wrong_frozen_lane_projection(
    source_ordinal: int,
    lane_id: str,
    lane_ordinal: int,
    task_ordinal: int,
) -> None:
    member = _member(source_ordinal)
    member.update({
        "lane_id": lane_id,
        "lane_ordinal": lane_ordinal,
        "task_ordinal": task_ordinal,
    })
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="lane/task differs from its source ordinal",
    ):
        catalog.normalize_member_binding(member)


def test_builds_exact_six_field_derivation_and_catalog() -> None:
    store = MemoryStore()
    published = _publish_one(store, 0)
    reopened = catalog.reopen_player_catalog_v1(
        player_catalog_identity=published["player_catalog_identity"],
        expected_tracked_root_binding=_root(),
        expected_member_binding=published["member"],
        expected_source_catalog_binding=published["source"],
        expected_completion_binding=published["completion"],
        expected_derivation_code_identity=CODE_IDENTITY,
        read_exact=store.read_exact,
    )
    body = reopened["player_catalog"]
    assert body["schema_version"] == catalog.PLAYER_CATALOG_SCHEMA
    assert body["source_task_ordinal"] == 0
    assert body["player_count"] == 2
    assert all(tuple(player) == catalog.PLAYER_FIELD_ORDER for player in body["players"])
    assert body["outcome_columns_read"] == []
    assert body["uses_realized_outcomes"] is False
    assert body["authority_boundary"] == catalog.AUTHORITY_BOUNDARY
    assert all(body[field] is False for field in catalog.FALSE_AUTHORITY_FIELDS)


@pytest.mark.parametrize("extra_field", ["name", "proj"])
def test_structural_catalog_rejects_legacy_non_science_fields(
    extra_field: str,
) -> None:
    players = _players(0)
    players[0][extra_field] = "name" if extra_field == "name" else 20.0
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="fields differ"
    ):
        catalog.normalize_structural_players(players)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("pos", "wr", "position/team context"),
        ("team", "BBB", "position/team context"),
        ("salary", True, "exact integer"),
        ("salary", -1, "exact integer"),
        ("game_id", "", "nonempty canonical string"),
    ],
)
def test_structural_catalog_rejects_malformed_rows(
    field: str, replacement: object, message: str
) -> None:
    players = _players(0)
    players[0][field] = replacement
    with pytest.raises(catalog.CorpusR6PlayerCatalogV1Error, match=message):
        catalog.normalize_structural_players(players)


def test_structural_catalog_rejects_reorder_and_duplicate() -> None:
    players = _players(0)
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="unique, and ID-sorted"
    ):
        catalog.normalize_structural_players(list(reversed(players)))
    duplicated = [players[0], deepcopy(players[0])]
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="unique, and ID-sorted"
    ):
        catalog.normalize_structural_players(duplicated)


@pytest.mark.parametrize(
    "mutation",
    [
        "source-task",
        "catalog-sha",
        "player-count",
        "later-source",
    ],
)
def test_derivation_rejects_member_source_completion_misbinding(
    mutation: str,
) -> None:
    member = _member(0)
    source = _source(0)
    completion = _completion(0, member=member, source=source)
    if mutation == "source-task":
        completion["task_source_authority_sha256"] = _digest("substitute-task")
    elif mutation == "catalog-sha":
        completion["catalog_sha256"] = _digest("substitute-catalog")
    elif mutation == "player-count":
        completion["catalog_player_count"] = 99
    elif mutation == "later-source":
        completion["later_source_freeze_identity"] = _identity(
            "alternate-source", 0
        )
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="authority chain differs"
    ):
        _derivation(
            0,
            member=member,
            source=source,
            completion=completion,
        )


def test_derivation_rejects_expected_coherent_alternate_root() -> None:
    derivation = _derivation(0, root=_root("alternate"))
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="expected tracked root"
    ):
        catalog.validate_derivation_receipt_v1(
            derivation, expected_tracked_root_binding=_root()
        )


def test_create_once_catalog_pair_resumes_identically_and_rejects_drift() -> None:
    store = MemoryStore()
    published = _publish_one(store, 0)
    resumed = catalog.publish_catalog_pair_create_once_v1(
        output_prefix=OUTPUT_PREFIX,
        derivation_receipt=published["derivation"],
        structural_players=published["players"],
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
    )
    assert resumed["derivation_receipt_identity"] == published[
        "derivation_receipt_identity"
    ]
    assert resumed["player_catalog_identity"] == published[
        "player_catalog_identity"
    ]
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="create-once publication failed",
    ):
        catalog.publish_catalog_pair_create_once_v1(
            output_prefix=OUTPUT_PREFIX,
            derivation_receipt=_derivation(0, root=_root("alternate")),
            structural_players=published["players"],
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )


def test_create_once_catalog_pair_resumes_after_receipt_only() -> None:
    store = MemoryStore()
    derivation = _derivation(0)
    receipt_uri = (
        f"{OUTPUT_PREFIX}tasks/0000-2023-w01/"
        "catalog-derivation-receipt.json"
    )
    receipt_identity = store.publish_create_once(
        receipt_uri, catalog.canonical_json_bytes(derivation)
    )
    resumed = catalog.publish_catalog_pair_create_once_v1(
        output_prefix=OUTPUT_PREFIX,
        derivation_receipt=derivation,
        structural_players=_players(0),
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
    )
    assert resumed["derivation_receipt_identity"] == receipt_identity
    assert resumed["player_catalog_identity"]["uri"].endswith(
        "/player-catalog.json"
    )


def test_catalog_pair_preflight_and_authority_boundary_fail_before_write() -> None:
    store = MemoryStore()
    players = _players(0)
    derivation = _derivation(0, players=players)
    changed_players = deepcopy(players)
    changed_players[0]["salary"] += 1
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="pair preflight differs"
    ):
        catalog.publish_catalog_pair_create_once_v1(
            output_prefix=OUTPUT_PREFIX,
            derivation_receipt=derivation,
            structural_players=changed_players,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
        )
    assert store.current == {}
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="requires a separately pinned fixed-G0 replay manifest",
    ):
        catalog.publish_catalog_pair_create_once_v1(
            output_prefix=OUTPUT_PREFIX,
            derivation_receipt=derivation,
            structural_players=players,
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
            request_authoritative_publication=True,
        )
    assert store.current == {}


@pytest.mark.parametrize("field", ["uri", "generation", "sha256", "bytes"])
def test_exact_reader_rejects_catalog_identity_drift(field: str) -> None:
    store = MemoryStore()
    published = _publish_one(store, 0)
    identity = deepcopy(published["player_catalog_identity"])
    replacements: dict[str, object] = {
        "uri": "gs://fixture-bucket/r6-player-catalog-v1/other.json",
        "generation": "999999",
        "sha256": "f" * 64,
        "bytes": int(identity["bytes"]) + 1,
    }
    identity[field] = replacements[field]
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="exact read failed"
    ):
        catalog.reopen_player_catalog_v1(
            player_catalog_identity=identity,
            expected_tracked_root_binding=_root(),
            expected_member_binding=published["member"],
            expected_source_catalog_binding=published["source"],
            expected_completion_binding=published["completion"],
            expected_derivation_code_identity=CODE_IDENTITY,
            read_exact=store.read_exact,
        )


def test_build_and_exact_reopen_complete_54_task_release() -> None:
    fixture = _publish_lattice()
    store: MemoryStore = fixture["store"]
    release = catalog.build_release_v1(
        release_id=RELEASE_ID,
        catalog_namespace=OUTPUT_PREFIX,
        expected_tracked_root_binding=fixture["root"],
        expected_member_bindings=fixture["members"],
        expected_source_catalog_bindings=fixture["sources"],
        expected_completion_bindings=fixture["completions"],
        expected_derivation_code_identity=CODE_IDENTITY,
        player_catalog_identities=fixture["catalog_identities"],
        read_exact=store.read_exact,
    )
    assert release["authority_boundary"] == catalog.AUTHORITY_BOUNDARY
    assert release["r6_source_authority"] is False
    assert release["publication_authority"] is False
    assert release["task_count"] == catalog.TASK_COUNT
    assert [entry["source_task_ordinal"] for entry in release["entries"]] == list(
        range(catalog.TASK_COUNT)
    )
    release_identity = store.put_body(f"{OUTPUT_PREFIX}catalog-release.json", release)
    reopened = catalog.reopen_release_v1(
        release_identity=release_identity,
        expected_catalog_namespace=OUTPUT_PREFIX,
        expected_tracked_root_binding=fixture["root"],
        expected_member_bindings=fixture["members"],
        expected_source_catalog_bindings=fixture["sources"],
        expected_completion_bindings=fixture["completions"],
        expected_derivation_code_identity=CODE_IDENTITY,
        read_exact=store.read_exact,
    )
    assert reopened["release"] == release


@pytest.mark.parametrize("variant", ["missing", "extra"])
def test_release_requires_exactly_54_catalog_identities(variant: str) -> None:
    fixture = _publish_lattice()
    identities = list(fixture["catalog_identities"])
    identities = identities[:-1] if variant == "missing" else identities + [identities[0]]
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="exactly 54 ordered"
    ):
        catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace=OUTPUT_PREFIX,
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=fixture["members"],
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=identities,
            read_exact=fixture["store"].read_exact,
        )


def test_release_rejects_reordered_catalog_members() -> None:
    fixture = _publish_lattice()
    identities = list(fixture["catalog_identities"])
    identities[0], identities[1] = identities[1], identities[0]
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="expected accepted member"
    ):
        catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace=OUTPUT_PREFIX,
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=fixture["members"],
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=identities,
            read_exact=fixture["store"].read_exact,
        )


def test_release_rejects_coherent_54_way_lane_task_permutation() -> None:
    fixture = _publish_lattice()
    members = deepcopy(fixture["members"])
    lane_projections = [
        {
            "lane_id": member["lane_id"],
            "lane_ordinal": member["lane_ordinal"],
            "task_ordinal": member["task_ordinal"],
        }
        for member in members
    ]
    for source_ordinal, member in enumerate(members):
        member.update(lane_projections[(source_ordinal + 1) % catalog.TASK_COUNT])
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="lane/task differs from its source ordinal",
    ):
        catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace=OUTPUT_PREFIX,
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=members,
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=fixture["catalog_identities"],
            read_exact=fixture["store"].read_exact,
        )


def test_release_rejects_semantic_authority_uri_reuse() -> None:
    fixture = _publish_lattice()
    members = deepcopy(fixture["members"])
    members[1]["task_acceptance_identity"] = deepcopy(
        members[0]["task_acceptance_identity"]
    )
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="authority object URI is reused",
    ):
        catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace=OUTPUT_PREFIX,
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=members,
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=fixture["catalog_identities"],
            read_exact=fixture["store"].read_exact,
        )


def test_coherently_rehashed_catalog_mutation_cannot_replace_derivation() -> None:
    store = MemoryStore()
    published = _publish_one(store, 0)
    reopened = catalog.reopen_player_catalog_v1(
        player_catalog_identity=published["player_catalog_identity"],
        expected_tracked_root_binding=_root(),
        expected_member_binding=published["member"],
        expected_source_catalog_binding=published["source"],
        expected_completion_binding=published["completion"],
        expected_derivation_code_identity=CODE_IDENTITY,
        read_exact=store.read_exact,
    )
    mutated = deepcopy(reopened["player_catalog"])
    mutated["players"][0]["salary"] += 100
    mutated["source_catalog_sha256"] = catalog.canonical_sha256(mutated["players"])
    mutated = _rehash(mutated, "player_catalog_sha256")
    mutated_identity = store.put_body(
        f"{OUTPUT_PREFIX}coherent-mutated-catalog.json", mutated
    )
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="differs from its exact derivation receipt",
    ):
        catalog.reopen_player_catalog_v1(
            player_catalog_identity=mutated_identity,
            expected_tracked_root_binding=_root(),
            expected_member_binding=published["member"],
            expected_source_catalog_binding=published["source"],
            expected_completion_binding=published["completion"],
            expected_derivation_code_identity=CODE_IDENTITY,
            read_exact=store.read_exact,
        )


def test_coherent_alternate_member_and_completion_fail_expected_member() -> None:
    store = MemoryStore()
    original_member = _member(0)
    original_source = _source(0)
    original_completion = _completion(
        0, member=original_member, source=original_source
    )
    alternate_member = deepcopy(original_member)
    alternate_member["source_task_authority_sha256"] = _digest(
        "coherent-alternate-task-authority"
    )
    alternate_completion = _completion(
        0, member=alternate_member, source=original_source
    )
    published = _publish_one(
        store,
        0,
        output_prefix="gs://fixture-bucket/alternate-member/",
        member=alternate_member,
        source=original_source,
        completion=alternate_completion,
    )
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="expected accepted member"
    ):
        catalog.reopen_player_catalog_v1(
            player_catalog_identity=published["player_catalog_identity"],
            expected_tracked_root_binding=_root(),
            expected_member_binding=original_member,
            expected_source_catalog_binding=original_source,
            expected_completion_binding=original_completion,
            expected_derivation_code_identity=CODE_IDENTITY,
            read_exact=store.read_exact,
        )


def test_fully_coherent_alternate_root_release_fails_pinned_root() -> None:
    alternate = _publish_lattice(
        root=_root("alternate"),
        output_prefix="gs://fixture-bucket/alternate-root/",
    )
    store: MemoryStore = alternate["store"]
    release = catalog.build_release_v1(
        release_id="r6-alternate-root-release-v1",
        catalog_namespace="gs://fixture-bucket/alternate-root/",
        expected_tracked_root_binding=alternate["root"],
        expected_member_bindings=alternate["members"],
        expected_source_catalog_bindings=alternate["sources"],
        expected_completion_bindings=alternate["completions"],
        expected_derivation_code_identity=CODE_IDENTITY,
        player_catalog_identities=alternate["catalog_identities"],
        read_exact=store.read_exact,
    )
    assert release["authority_boundary"] == catalog.AUTHORITY_BOUNDARY
    assert release["r6_source_authority"] is False
    release_identity = store.put_body(
        "gs://fixture-bucket/alternate-root/catalog-release.json", release
    )
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="expected tracked root"
    ):
        catalog.reopen_release_v1(
            release_identity=release_identity,
            expected_catalog_namespace="gs://fixture-bucket/alternate-root/",
            expected_tracked_root_binding=_root(),
            expected_member_bindings=alternate["members"],
            expected_source_catalog_bindings=alternate["sources"],
            expected_completion_bindings=alternate["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            read_exact=store.read_exact,
        )
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="requires a separately pinned fixed-G0 replay manifest",
    ):
        catalog.publish_release_create_once_v1(
            output_prefix="gs://fixture-bucket/alternate-root/",
            release_id="r6-alternate-root-release-v1",
            expected_tracked_root_binding=alternate["root"],
            expected_member_bindings=alternate["members"],
            expected_source_catalog_bindings=alternate["sources"],
            expected_completion_bindings=alternate["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=alternate["catalog_identities"],
            publish_create_once=store.publish_create_once,
            read_exact=store.read_exact,
            request_authoritative_publication=True,
        )


@pytest.mark.parametrize(
    ("object_kind", "hash_field"),
    [
        ("derivation", "derivation_sha256"),
        ("catalog", "player_catalog_sha256"),
        ("release", "release_sha256"),
    ],
)
def test_every_schema_rejects_nonfalse_downstream_authority(
    object_kind: str, hash_field: str
) -> None:
    if object_kind == "derivation":
        body = _derivation(0)
        validator = catalog.validate_derivation_receipt_v1
    elif object_kind == "catalog":
        store = MemoryStore()
        published = _publish_one(store, 0)
        body = catalog.reopen_player_catalog_v1(
            player_catalog_identity=published["player_catalog_identity"],
            expected_tracked_root_binding=_root(),
            expected_member_binding=published["member"],
            expected_source_catalog_binding=published["source"],
            expected_completion_binding=published["completion"],
            expected_derivation_code_identity=CODE_IDENTITY,
            read_exact=store.read_exact,
        )["player_catalog"]
        validator = catalog.validate_player_catalog_v1
    else:
        fixture = _publish_lattice()
        body = catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace=OUTPUT_PREFIX,
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=fixture["members"],
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=fixture["catalog_identities"],
            read_exact=fixture["store"].read_exact,
        )
        validator = catalog.validate_release_v1
    poisoned = deepcopy(body)
    poisoned["promotion_authority"] = True
    poisoned = _rehash(poisoned, hash_field)
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="non-false downstream"
    ):
        validator(poisoned)


def test_release_rejects_relocated_byte_identical_children() -> None:
    fixture = _publish_lattice()
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="child URI differs from its fixed namespace",
    ):
        catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace="gs://fixture-bucket/relocated-release/",
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=fixture["members"],
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=fixture["catalog_identities"],
            read_exact=fixture["store"].read_exact,
        )


def test_release_rejects_coherent_54_task_alternate_code_identity() -> None:
    alternate_code = {
        "source_commit_sha": "d" * 40,
        "module_path": MODULE_PATH,
        "module_sha256": _digest("alternate-catalog-module"),
    }
    fixture = _publish_lattice(code_identity=alternate_code)
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="expected code identity",
    ):
        catalog.build_release_v1(
            release_id=RELEASE_ID,
            catalog_namespace=OUTPUT_PREFIX,
            expected_tracked_root_binding=fixture["root"],
            expected_member_bindings=fixture["members"],
            expected_source_catalog_bindings=fixture["sources"],
            expected_completion_bindings=fixture["completions"],
            expected_derivation_code_identity=CODE_IDENTITY,
            player_catalog_identities=fixture["catalog_identities"],
            read_exact=fixture["store"].read_exact,
        )


def test_nonempty_outcome_columns_fail_even_with_coherent_self_hash() -> None:
    derivation = _derivation(0)
    poisoned = deepcopy(derivation)
    poisoned["outcome_columns_read"] = ["actual_score"]
    poisoned = _rehash(poisoned, "derivation_sha256")
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="outcome_columns_read must be empty",
    ):
        catalog.validate_derivation_receipt_v1(poisoned)


def test_release_validator_rejects_coherently_reordered_entries() -> None:
    fixture = _publish_lattice()
    release = catalog.build_release_v1(
        release_id=RELEASE_ID,
        catalog_namespace=OUTPUT_PREFIX,
        expected_tracked_root_binding=fixture["root"],
        expected_member_bindings=fixture["members"],
        expected_source_catalog_bindings=fixture["sources"],
        expected_completion_bindings=fixture["completions"],
        expected_derivation_code_identity=CODE_IDENTITY,
        player_catalog_identities=fixture["catalog_identities"],
        read_exact=fixture["store"].read_exact,
    )
    poisoned = deepcopy(release)
    poisoned["entries"][0], poisoned["entries"][1] = (
        poisoned["entries"][1],
        poisoned["entries"][0],
    )
    poisoned["entry_manifest_sha256"] = catalog.canonical_sha256(
        poisoned["entries"]
    )
    poisoned = _rehash(poisoned, "release_sha256")
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error, match="source-task order differs"
    ):
        catalog.validate_release_v1(poisoned)


def test_release_validator_rejects_coherently_mutated_task_id() -> None:
    fixture = _publish_lattice()
    release = catalog.build_release_v1(
        release_id=RELEASE_ID,
        catalog_namespace=OUTPUT_PREFIX,
        expected_tracked_root_binding=fixture["root"],
        expected_member_bindings=fixture["members"],
        expected_source_catalog_bindings=fixture["sources"],
        expected_completion_bindings=fixture["completions"],
        expected_derivation_code_identity=CODE_IDENTITY,
        player_catalog_identities=fixture["catalog_identities"],
        read_exact=fixture["store"].read_exact,
    )
    poisoned = deepcopy(release)
    poisoned["entries"][0]["task_id"] = poisoned["entries"][1]["task_id"]
    poisoned["entry_manifest_sha256"] = catalog.canonical_sha256(
        poisoned["entries"]
    )
    poisoned = _rehash(poisoned, "release_sha256")
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="task ID differs from its source ordinal",
    ):
        catalog.validate_release_v1(poisoned)


def test_release_create_once_resumes_identically_and_rejects_drift() -> None:
    fixture = _publish_lattice()
    store: MemoryStore = fixture["store"]
    kwargs = {
        "output_prefix": OUTPUT_PREFIX,
        "release_id": RELEASE_ID,
        "expected_tracked_root_binding": fixture["root"],
        "expected_member_bindings": fixture["members"],
        "expected_source_catalog_bindings": fixture["sources"],
        "expected_completion_bindings": fixture["completions"],
        "expected_derivation_code_identity": CODE_IDENTITY,
        "player_catalog_identities": fixture["catalog_identities"],
        "publish_create_once": store.publish_create_once,
        "read_exact": store.read_exact,
    }
    identity = catalog.publish_release_create_once_v1(**kwargs)
    assert identity["uri"] == f"{OUTPUT_PREFIX}catalog-release.json"
    assert catalog.publish_release_create_once_v1(**kwargs) == identity
    drifted_kwargs = {**kwargs, "release_id": "drifted-release-v1"}
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="create-once publication failed",
    ):
        catalog.publish_release_create_once_v1(**drifted_kwargs)
    with pytest.raises(
        catalog.CorpusR6PlayerCatalogV1Error,
        match="requires a separately pinned fixed-G0 replay manifest",
    ):
        catalog.publish_release_create_once_v1(
            **kwargs, request_authoritative_publication=True
        )
