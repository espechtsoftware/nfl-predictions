"""Focused adversarial tests for the corrected R6 source operator."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import runpy
from typing import Any

import pytest

from nfl_dfs.research import corpus_r6_matchup_source_operator_v1 as operator
from nfl_dfs.research import corpus_r6_matchup_source_v1 as source


_SOURCE_TEST_NAMESPACE = runpy.run_path(
    str(Path(__file__).with_name("test_corpus_r6_matchup_source_v1.py"))
)
_source_fixture = _SOURCE_TEST_NAMESPACE["_fixture"]
_CLI_NAMESPACE = runpy.run_path(
    str(
        Path(__file__).parents[1]
        / "scripts"
        / "run_corpus_r6_matchup_source_operator_v1.py"
    )
)


def _identity(uri: str, raw: bytes, generation: str = "900") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _rehash(body: dict[str, object], field: str) -> None:
    body[field] = source.canonical_sha256({
        key: value for key, value in body.items() if key != field
    })


def _code_identity(families: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    artifacts = [
        {
            "role": role,
            "path": f"src/nfl_dfs/research/{role.replace('-', '_')}.py",
            "sha256": f"{ordinal + 1:x}" * 64,
            "bytes": 1000 + ordinal,
        }
        for ordinal, role in enumerate((
            "family-definition-producer",
            "matchup-source-contract",
            "matchup-source-operator",
            "source-extract-producer",
        ))
    ]
    return operator.build_code_identity_v1(
        repository_commit="b" * 40,
        artifacts=artifacts,
        family_definition_identities=families,
    )


def _bundle_fixture() -> dict[str, Any]:
    fixture = _source_fixture()
    fixture["metadata"]["query_job"]["project"] = "fixture_project"

    catalog_authority_raw = source.canonical_json_bytes({
        "schema_version": "accepted-v12-catalog-authority-fixture/v1",
        "task_id": fixture["slate"]["task_id"],
        "uses_realized_outcomes": False,
    })
    catalog_authority_identity = _identity(
        "gs://fixture-authority/catalog-authority.json",
        catalog_authority_raw,
        "800",
    )
    fixture["catalog"]["source_authority"] = catalog_authority_identity
    _rehash(fixture["catalog"], "player_catalog_sha256")
    catalog_raw = source.canonical_json_bytes(fixture["catalog"])
    catalog_identity = _identity(
        "gs://fixture-authority/catalogs/slate-2023-w5.json",
        catalog_raw,
        "801",
    )

    task_binding = {
        **fixture["slate"],
        "task_ordinal": 5,
        "source_task_ordinal": 17,
    }
    accepted_raw = source.canonical_json_bytes({
        "schema_version": "accepted-v12-reconstruction-fixture/v1",
        "task_binding": task_binding,
        "uses_realized_outcomes": False,
    })
    accepted_identity = _identity(
        "gs://fixture-authority/accepted-v12/slate-2023-w5.json",
        accepted_raw,
        "802",
    )
    code_identity = _code_identity(fixture["families"])
    bundle = operator.build_input_bundle_v1(
        accepted_v12_reconstruction_identity=accepted_identity,
        task_binding=task_binding,
        slate=fixture["slate"],
        lock_time_utc=fixture["lock_time_utc"],
        player_catalog_identity=catalog_identity,
        player_catalog_raw=fixture["catalog"],
        rendered_sql_raw=fixture["rendered_sql_raw"],
        query_job_receipt=fixture["metadata"],
        component_extracts=fixture["extracts"],
        annotation_rows=fixture["annotations"],
        family_definition_identities=fixture["families"],
        code_identity=code_identity,
        output_prefix="gs://fixture-output/r6/matchup/2023-w05-main",
    )
    bundle_raw = source.canonical_json_bytes(bundle)
    bundle_identity = _identity(
        "gs://fixture-authority/bundles/slate-2023-w5.json",
        bundle_raw,
        "803",
    )
    authority = operator._build_capture_authority_fixture_v1(
        input_bundle=bundle,
        input_bundle_identity=bundle_identity,
        allowed_project="fixture_project",
        allowed_bucket="fixture-output",
        allowed_output_prefix=str(bundle["output_prefix"]),
    )
    authority_raw = source.canonical_json_bytes(authority)
    authority_identity = _identity(
        "gs://fixture-authority/capture-authorities/slate-2023-w5.json",
        authority_raw,
        "804",
    )
    return {
        "fixture": fixture,
        "bundle": bundle,
        "bundle_raw": bundle_raw,
        "bundle_identity": bundle_identity,
        "catalog_raw": catalog_raw,
        "catalog_identity": catalog_identity,
        "catalog_authority_raw": catalog_authority_raw,
        "catalog_authority_identity": catalog_authority_identity,
        "accepted_raw": accepted_raw,
        "accepted_identity": accepted_identity,
        "authority": authority,
        "authority_raw": authority_raw,
        "authority_identity": authority_identity,
    }


def _coherent_fixture_store(
    case: Mapping[str, Any],
) -> operator.MemoryExactObjectStore:
    store = operator.MemoryExactObjectStore()
    for identity_key, raw_key in (
        ("accepted_identity", "accepted_raw"),
        ("catalog_authority_identity", "catalog_authority_raw"),
        ("catalog_identity", "catalog_raw"),
        ("bundle_identity", "bundle_raw"),
        ("authority_identity", "authority_raw"),
    ):
        store.seed_exact(case[identity_key], case[raw_key])
    return store


def _run_execute_blocked(
    case: Mapping[str, Any],
    *,
    raw: bytes | None = None,
) -> dict[str, object]:
    return operator.run_matchup_source_operator_v1(
        input_bundle_raw=case["bundle_raw"] if raw is None else raw,
        validate_only=False,
    )


def _rehash_bundle(bundle: dict[str, object]) -> bytes:
    _rehash(bundle, "input_bundle_sha256")
    return source.canonical_json_bytes(bundle)


def test_validate_only_replays_semantics_but_has_no_trusted_authority() -> None:
    case = _bundle_fixture()

    result = operator.run_matchup_source_operator_v1(
        input_bundle_raw=case["bundle_raw"],
        validate_only=True,
    )
    assert result["operator_result_identity"] is None
    receipt = operator.validate_operator_result_receipt_v1(result["receipt"])
    assert receipt["mode"] == operator.VALIDATE_ONLY_MODE
    assert receipt["semantic_capture_replay_validated"] is True
    assert receipt["published"] is False
    assert receipt["capture_mechanics_authority"] is False
    assert receipt["capture_authority_identity"] is None
    assert receipt["input_bundle_identity"] is None
    assert receipt["source_export_identity"] is None
    assert receipt["query_receipt_identity"] is None
    assert all(
        receipt[field] is False
        for field in (
            "capture_authority_exact_reopen_validated",
            "input_bundle_exact_reopen_validated",
            "accepted_v12_reconstruction_exact_reopen_validated",
            "catalog_exact_reopen_validated",
            "catalog_source_authority_exact_reopen_validated",
        )
    )


def test_authority_minting_names_are_absent_from_public_surface() -> None:
    former_public_names = {
        "CAPTURE_AUTHORITY_SCHEMA",
        "build_capture_authority_v1",
        "validate_capture_authority_v1",
    }
    assert former_public_names.isdisjoint(operator.__all__)
    assert all(not hasattr(operator, name) for name in former_public_names)


def test_execute_is_unconditionally_blocked_pending_frozen_catalog() -> None:
    case = _bundle_fixture()
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="frozen 54-entry authority catalog unavailable",
    ):
        operator.run_matchup_source_operator_v1(
            input_bundle_raw=case["bundle_raw"],
            validate_only=False,
        )


def test_fully_coherent_caller_selected_authority_chain_cannot_execute() -> None:
    case = _bundle_fixture()
    # Prove the entire caller-created bundle/catalog/accepted/carrier set is
    # internally coherent. It still cannot become the missing pinned
    # 54-member authority root.
    operator._validate_capture_authority_v1(case["authority"])
    _coherent_fixture_store(case)
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="frozen 54-entry authority catalog unavailable",
    ):
        operator.run_matchup_source_operator_v1(
            input_bundle_raw=case["bundle_raw"],
            validate_only=False,
        )


def test_self_hashed_execute_receipt_is_rejected_pending_frozen_catalog() -> None:
    case = _bundle_fixture()
    result = operator.run_matchup_source_operator_v1(
        input_bundle_raw=case["bundle_raw"], validate_only=True
    )
    receipt = deepcopy(result["receipt"])
    receipt["mode"] = operator.EXECUTE_MODE
    _rehash(receipt, "operator_result_sha256")
    assert receipt["operator_result_sha256"] == source.canonical_sha256({
        key: value
        for key, value in receipt.items()
        if key != "operator_result_sha256"
    })
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="frozen 54-entry authority catalog unavailable",
    ):
        operator.validate_operator_result_receipt_v1(receipt)


def test_noncanonical_input_bundle_bytes_are_rejected() -> None:
    case = _bundle_fixture()
    noncanonical = json.dumps(case["bundle"], indent=2).encode("utf-8")
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="canonical representation",
    ):
        operator.parse_input_bundle_v1(noncanonical)


def test_huge_json_integer_is_a_controlled_rejection() -> None:
    raw = b'{"value":' + (b"9" * 5000) + b"}"
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="not canonical JSON",
    ):
        operator.parse_input_bundle_v1(raw)


def test_unhashable_result_mode_is_a_controlled_rejection() -> None:
    case = _bundle_fixture()
    result = operator.run_matchup_source_operator_v1(
        input_bundle_raw=case["bundle_raw"], validate_only=True
    )
    receipt = deepcopy(result["receipt"])
    receipt["mode"] = []
    _rehash(receipt, "operator_result_sha256")
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="operator result policy differs",
    ):
        operator.validate_operator_result_receipt_v1(receipt)


def test_arbitrary_code_identity_fields_are_rejected_by_positive_schema() -> None:
    case = _bundle_fixture()
    bundle = deepcopy(case["bundle"])
    bundle["code_identity"]["unregistered_claim"] = True
    _rehash(bundle["code_identity"], "code_identity_sha256")
    raw = _rehash_bundle(bundle)
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="code identity fields differ",
    ):
        operator.parse_input_bundle_v1(raw)


def test_explicit_input_authority_or_outcome_policy_cannot_be_enabled() -> None:
    case = _bundle_fixture()
    for field, value in (
        ("capture_mechanics_authority", True),
        ("outcome_columns_read", ["points"]),
        ("scoring_authority", True),
    ):
        bundle = deepcopy(case["bundle"])
        bundle[field] = value
        raw = _rehash_bundle(bundle)
        with pytest.raises(
            operator.CorpusR6MatchupSourceOperatorV1Error,
            match="authority|outcome|cannot grant",
        ):
            operator.parse_input_bundle_v1(raw)


def test_unbounded_annotation_input_fails_before_source_capture() -> None:
    case = _bundle_fixture()
    bundle = deepcopy(case["bundle"])
    bundle["annotation_rows"] = [
        {} for _ in range(operator.MAX_ANNOTATION_ROWS + 1)
    ]
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="annotation rows exceed",
    ):
        operator.parse_input_bundle_v1(_rehash_bundle(bundle))


def test_generation_digit_bound_fails_before_gcs_client_use() -> None:
    client = _FakeGCSClient()
    store = operator.GenerationPinnedGCSStore(client)
    bad = {
        "uri": "gs://fixture-output/r6/object.json",
        "generation": "9" * (operator.MAX_GENERATION_DIGITS + 1),
        "sha256": "a" * 64,
        "bytes": 1,
    }
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="bounded positive generation",
    ):
        store.read_exact(bad)
    assert client.events == []


def _coherent_bundle_substitution(
    case: Mapping[str, Any], kind: str,
) -> bytes:
    bundle = deepcopy(case["bundle"])
    if kind == "catalog":
        bundle["player_catalog_raw"]["players"][0]["salary"] += 100
        _rehash(bundle["player_catalog_raw"], "player_catalog_sha256")
        catalog_raw = source.canonical_json_bytes(bundle["player_catalog_raw"])
        bundle["player_catalog_identity"]["sha256"] = sha256(catalog_raw).hexdigest()
        bundle["player_catalog_identity"]["bytes"] = len(catalog_raw)
    elif kind == "catalog-source-authority":
        bundle["player_catalog_raw"]["source_authority"]["generation"] = "899"
        _rehash(bundle["player_catalog_raw"], "player_catalog_sha256")
        catalog_raw = source.canonical_json_bytes(bundle["player_catalog_raw"])
        bundle["player_catalog_identity"]["sha256"] = sha256(catalog_raw).hexdigest()
        bundle["player_catalog_identity"]["bytes"] = len(catalog_raw)
    elif kind == "accepted-reconstruction":
        bundle["accepted_v12_reconstruction_identity"]["generation"] = "899"
    elif kind == "task-ordinal":
        bundle["task_binding"]["task_ordinal"] = 6
    elif kind == "source-ordinal":
        bundle["task_binding"]["source_task_ordinal"] = 18
    elif kind == "query-job":
        bundle["query_job_receipt"]["query_job"]["job_id"] = "substituted_job"
    elif kind == "relation":
        bundle["query_job_receipt"]["source_relations"][0][
            "etag_or_generation"
        ] = "substituted-etag"
    elif kind == "code":
        bundle["code_identity"]["artifacts"][0]["sha256"] = "f" * 64
        _rehash(bundle["code_identity"], "code_identity_sha256")
    elif kind == "output":
        bundle["output_prefix"] = (
            "gs://fixture-output/r6/matchup/2023-w05-main-substituted"
        )
    else:  # pragma: no cover - test helper guard
        raise AssertionError(kind)
    return _rehash_bundle(bundle)


@pytest.mark.parametrize(
    "kind",
    [
        "catalog",
        "catalog-source-authority",
        "accepted-reconstruction",
        "task-ordinal",
        "source-ordinal",
        "query-job",
        "relation",
        "code",
        "output",
    ],
)
def test_coherently_rehashed_bundle_substitutions_cannot_enable_execute(
    kind: str,
) -> None:
    case = _bundle_fixture()
    substituted_raw = _coherent_bundle_substitution(case, kind)
    # Every substitution retains the bundle's own internal self-hash and
    # schema. None can substitute for the unavailable pinned catalog root.
    operator.parse_input_bundle_v1(substituted_raw)
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="frozen 54-entry authority catalog unavailable",
    ):
        _run_execute_blocked(case, raw=substituted_raw)


class _FakeBlob:
    def __init__(
        self,
        client: "_FakeGCSClient",
        bucket: str,
        name: str,
        generation: int | None,
    ) -> None:
        self.client = client
        self.bucket = bucket
        self.name = name
        self.generation: int | str | None = generation
        self.size: int | None = None

    @property
    def key(self) -> tuple[str, str]:
        return self.bucket, self.name

    def upload_from_string(
        self,
        raw: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        self.client.events.append((
            "upload", self.key, content_type, if_generation_match
        ))
        if if_generation_match != 0 or self.key in self.client.objects:
            raise RuntimeError("precondition")
        generation = self.client.next_generation
        self.client.next_generation += 1
        self.client.objects[self.key] = (generation, raw)
        self.generation = generation

    def reload(self, *, if_generation_match: int) -> None:
        self.client.events.append(("reload", self.key, if_generation_match))
        retained = self.client.objects.get(self.key)
        if retained is None or retained[0] != if_generation_match:
            raise RuntimeError("generation drift")
        self.generation = retained[0]
        self.size = (
            self.client.metadata_size_override
            if self.client.metadata_size_override is not None
            else len(retained[1])
        )

    def download_as_bytes(
        self, *, if_generation_match: int, start: int, end: int
    ) -> bytes:
        self.client.events.append(
            ("download", self.key, if_generation_match, start, end)
        )
        retained = self.client.objects.get(self.key)
        if retained is None or retained[0] != if_generation_match:
            raise RuntimeError("generation drift")
        raw = retained[1]
        if self.client.corrupt_download:
            return (b"0" if raw[:1] != b"0" else b"1") + raw[1:]
        return raw[start : end + 1]


class _FakeBucket:
    def __init__(self, client: "_FakeGCSClient", name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        self.client.events.append(("blob", (self.name, name), generation))
        return _FakeBlob(self.client, self.name, name, generation)


class _FakeGCSClient:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[int, bytes]] = {}
        self.next_generation = 1000
        self.corrupt_download = False
        self.metadata_size_override: int | None = None
        self.events: list[tuple[object, ...]] = []

    def bucket(self, name: str) -> _FakeBucket:
        self.events.append(("bucket", name))
        return _FakeBucket(self, name)

    def seed(self, identity: Mapping[str, object], raw: bytes) -> None:
        uri = str(identity["uri"])
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects[(bucket, name)] = (int(str(identity["generation"])), raw)


def _coherent_fixture_fake_gcs(case: Mapping[str, Any]) -> _FakeGCSClient:
    client = _FakeGCSClient()
    for identity_key, raw_key in (
        ("accepted_identity", "accepted_raw"),
        ("catalog_authority_identity", "catalog_authority_raw"),
        ("catalog_identity", "catalog_raw"),
        ("bundle_identity", "bundle_raw"),
        ("authority_identity", "authority_raw"),
    ):
        client.seed(case[identity_key], case[raw_key])
    return client


def test_gcs_adapter_uses_create_precondition_and_only_pinned_reopens() -> None:
    client = _FakeGCSClient()
    store = operator.GenerationPinnedGCSStore(client)
    raw = b'{"outcome_blind":true}'

    identity = store.publish_create_once(
        "gs://fixture-output/r6/operator-object.json", raw
    )

    assert store.read_exact(identity) == raw
    upload_events = [event for event in client.events if event[0] == "upload"]
    reload_events = [event for event in client.events if event[0] == "reload"]
    download_events = [event for event in client.events if event[0] == "download"]
    assert upload_events == [(
        "upload",
        ("fixture-output", "r6/operator-object.json"),
        "application/json",
        0,
    )]
    assert reload_events and all(event[2] == 1000 for event in reload_events)
    assert download_events and all(event[2] == 1000 for event in download_events)
    assert not any(event[0] in {"list", "iam", "latest"} for event in client.events)

    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="create-once GCS publication failed",
    ):
        store.publish_create_once(
            "gs://fixture-output/r6/operator-object.json", raw
        )


def test_gcs_adapter_rejects_generation_matched_hash_drift() -> None:
    client = _FakeGCSClient()
    store = operator.GenerationPinnedGCSStore(client)
    raw = b'{"outcome_blind":true}'
    identity = store.publish_create_once(
        "gs://fixture-output/r6/drift.json", raw
    )
    client.corrupt_download = True
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="content identity differs",
    ):
        store.read_exact(identity)


def test_gcs_adapter_rejects_oversize_metadata_before_download() -> None:
    client = _FakeGCSClient()
    raw = b"x"
    identity = _identity("gs://fixture-output/r6/oversize.json", raw, "1000")
    client.seed(identity, raw)
    client.metadata_size_override = operator.MAX_EXTERNAL_OBJECT_BYTES + 1
    store = operator.GenerationPinnedGCSStore(client)
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="generation-pinned GCS read failed",
    ):
        store.read_exact(identity)
    assert not any(event[0] == "download" for event in client.events)


def test_cli_validate_only_uses_secure_local_read_and_no_client(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = _bundle_fixture()
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_bytes(case["bundle_raw"])
    status = _CLI_NAMESPACE["main"](
        ["--bundle", str(bundle_path), "--validate-only"],
    )

    assert status == 0
    result = json.loads(capsys.readouterr().out)
    assert result["receipt"]["capture_mechanics_authority"] is False


def test_cli_execute_is_honestly_fail_closed_without_frozen_catalog(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = _bundle_fixture()
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_bytes(case["bundle_raw"])

    status = _CLI_NAMESPACE["main"](
        ["--bundle", str(bundle_path), "--execute"],
    )

    assert status == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "frozen 54-entry authority catalog unavailable" in captured.err


def test_cli_no_follow_reader_rejects_symlink(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    case = _bundle_fixture()
    target = tmp_path / "bundle-target.json"
    link = tmp_path / "bundle-link.json"
    target.write_bytes(case["bundle_raw"])
    link.symlink_to(target)

    status = _CLI_NAMESPACE["main"](
        ["--bundle", str(link), "--validate-only"]
    )

    assert status == 2
    assert "could not be read safely" in capsys.readouterr().err


def test_cli_bounded_fd_reader_detects_in_read_metadata_change(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "changing.json"
    path.write_bytes(b'{"a":1}')
    original_read = os.read
    changed = False

    def drifting_read(descriptor: int, size: int) -> bytes:
        nonlocal changed
        raw = original_read(descriptor, size)
        if raw and not changed:
            before = path.stat()
            os.utime(
                path,
                ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000),
            )
            changed = True
        return raw

    monkeypatch.setattr(os, "read", drifting_read)
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV1Error,
        match="changed during",
    ):
        _CLI_NAMESPACE["_read_bounded_regular_file"](
            path,
            maximum_bytes=1024,
            label="changing fixture",
        )
