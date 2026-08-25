from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_core_v1_catalog_materializer as materializer


ROOT = Path(__file__).resolve().parents[1]


def _load_cli():
    path = ROOT / "scripts/run_core_v1_catalog_cloud.py"
    spec = importlib.util.spec_from_file_location(
        "run_core_v1_catalog_cloud_test", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


class _FakeBlob:
    def __init__(
        self,
        client: "_FakeGCSClient",
        bucket: str,
        name: str,
        generation: int | None,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self.name = name
        self.generation = generation

    @property
    def _key(self) -> tuple[str, str]:
        return self._bucket, self.name

    def _current_generation(self) -> int:
        versions = self._client.objects.get(self._key, {})
        if not versions:
            raise RuntimeError("not found")
        return max(versions)

    def reload(self, *, if_generation_match: int | None = None) -> None:
        generation = (
            self._current_generation()
            if self.generation is None
            else int(self.generation)
        )
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition failed")
        if generation not in self._client.objects.get(self._key, {}):
            raise RuntimeError("generation not found")
        self.generation = generation
        self._client.reload_generations.append(generation)

    def download_as_bytes(
        self, *, if_generation_match: int | None = None,
    ) -> bytes:
        if self.generation is None:
            raise AssertionError("download was not generation-pinned")
        generation = int(self.generation)
        if if_generation_match != generation:
            raise AssertionError("download generation precondition differs")
        self._client.download_generations.append(generation)
        return self._client.objects[self._key][generation]

    def upload_from_string(
        self,
        raw: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        if self._client.objects.get(self._key):
            raise RuntimeError("precondition failed")
        generation = self._client.next_generation
        self._client.next_generation += 1
        self._client.objects[self._key] = {generation: raw}
        self.generation = generation


class _FakeBucket:
    def __init__(self, client: "_FakeGCSClient", name: str) -> None:
        self._client = client
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self._client, self._name, name, generation)


class _FakeGCSClient:
    """Deliberately has no list_blobs method."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.next_generation = 100
        self.reload_generations: list[int] = []
        self.download_generations: list[int] = []

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def seed(self, uri: str, raw: bytes, *, generation: int) -> dict[str, object]:
        bucket, name = uri.removeprefix("gs://").split("/", 1)
        self.objects.setdefault((bucket, name), {})[generation] = raw
        return {
            "uri": uri,
            "generation": str(generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }


def _pin_args(stem: str, *, uri: str = "gs://fixture-bucket/input.json") -> list[str]:
    option = stem.replace("_", "-")
    return [
        f"--{option}-uri",
        uri,
        f"--{option}-generation",
        "1",
        f"--{option}-sha256",
        "0" * 64,
        f"--{option}-bytes",
        "1",
    ]


def _assert_receipt(captured: str, *, schema: str) -> dict[str, object]:
    assert captured.count("\n") == 0
    value = json.loads(captured)
    assert value["schema_version"] == schema
    retained = value.pop("cli_receipt_sha256")
    assert retained == materializer.canonical_sha256(value)
    value["cli_receipt_sha256"] = retained
    return value


def _identity(uri: str, generation: int) -> dict[str, object]:
    raw = f"{uri}:{generation}".encode()
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_generation_pinned_exact_reader_checks_generation_and_bytes() -> None:
    client = _FakeGCSClient()
    raw = b'{"exact":true}'
    identity = client.seed(
        "gs://fixture-bucket/exact.json", raw, generation=17
    )
    store = cli.GenerationPinnedGCS(client)

    assert store.read_exact(identity) == raw
    assert client.reload_generations == [17]
    assert client.download_generations == [17]

    forged = dict(identity)
    forged["sha256"] = "f" * 64
    with pytest.raises(cli.CoreV1CatalogCloudError, match="object differs"):
        store.read_exact(forged)


def test_create_once_recovers_current_generation_without_bucket_listing() -> None:
    client = _FakeGCSClient()
    store = cli.GenerationPinnedGCS(client)
    uri = "gs://fixture-bucket/output/catalog.json"
    raw = b'{"catalog":true}'

    created = store.publish_create_once(uri, raw)
    recovered = store.publish_create_once(uri, raw)

    assert created.created is True
    assert recovered.created is False
    assert recovered.identity == created.identity
    assert store.read_exact(recovered.identity) == raw
    with pytest.raises(
        cli.CoreV1CatalogCloudError,
        match="existing Core v1 create-once object differs",
    ):
        store.publish_create_once(uri, b'{"catalog":false}')


def test_cli_is_default_off_before_any_storage_access(capsys) -> None:
    argv = ["reopen", *_pin_args("root")]

    with pytest.raises(
        cli.CoreV1CatalogCloudError,
        match="required explicitly",
    ):
        cli.main(argv, environ={}, storage_client=object())

    assert capsys.readouterr().out == ""


def test_smoke_cli_emits_only_a_compact_self_hashed_receipt(
    monkeypatch, capsys
) -> None:
    source_identity = _identity("gs://fixture-bucket/panel.json", 1)
    t230_identity = _identity("gs://fixture-bucket/t230.json", 2)
    report = {
        "source_ordinal": 0,
        "slate": {"season": 2023, "week": 1, "slate_id": "2023-w01"},
        "source_panel_identity": source_identity,
        "t230_result_identity": t230_identity,
        "t230_slate_result_sha256": "1" * 64,
        "slate_catalog_sha256": "2" * 64,
        "structural_counts": {"union_lineup_count": 80},
        "structural_hashes": {"union_population_sha256": "3" * 64},
        "slate_catalog": {"must_not_reach_stdout": True},
    }
    monkeypatch.setattr(
        cli.core_cloud,
        "build_core_v1_slate_smoke_projection",
        lambda **_kwargs: report,
    )
    argv = [
        "slate-smoke",
        "--execute",
        "--source-ordinal",
        "0",
        *_pin_args("source_panel"),
        *_pin_args("t230_result"),
    ]

    assert cli.main(
        argv,
        environ={cli.ENABLED_ENV: "1"},
        storage_client=object(),
    ) == 0

    receipt = _assert_receipt(
        capsys.readouterr().out, schema=cli.SMOKE_RECEIPT_SCHEMA
    )
    assert "slate_catalog" not in receipt
    assert receipt["outcome_fields_read"] == []
    assert receipt["science_recomputation_performed"] is False


def test_materialize_and_reopen_cli_receipts_retain_catalog_authority(
    monkeypatch, capsys
) -> None:
    catalog_identity = _identity(
        "gs://fixture-bucket/core/catalog.json", 20
    )
    root_identity = _identity(
        "gs://fixture-bucket/core/catalog-root.json", 21
    )
    root = {
        "catalog_identity": catalog_identity,
        "sharded_catalog_root_sha256": "4" * 64,
        "catalog_sha256": "5" * 64,
        "shard_count": 54,
        "shard_descriptors_sha256": "6" * 64,
        "materialization_metrics": {
            "peak_logical_catalog_bytes_materialized": 123,
            "union_roster_membership_count": 4_320,
        },
    }
    logical_catalog = {
        "catalog_sha256": "5" * 64,
        "source_slate_count": 54,
        "book_cell_count": 1_944,
        "contrast_cell_count": 7_290,
        "slates": [
            {"union_population": {"lineup_count": 80}}
            for _ in range(54)
        ],
    }
    published = materializer.PublishedShardedCoreV1Catalog(
        root=root,
        root_identity=root_identity,
        catalog_identity=catalog_identity,
        shard_identities=tuple(),
        logical_catalog=logical_catalog,
        catalog_created=True,
        created_shard_count=54,
        recovered_shard_count=0,
        root_created=True,
    )
    reopened = materializer.ReopenedShardedCoreV1Catalog(
        root=root,
        root_identity=root_identity,
        catalog_identity=catalog_identity,
        shard_identities=tuple(),
        logical_catalog=logical_catalog,
    )
    monkeypatch.setattr(
        cli.core_cloud,
        "materialize_sharded_core_v1_catalog",
        lambda **_kwargs: published,
    )
    materialize_argv = [
        "materialize",
        "--execute",
        "--catalog-id",
        "core-v1-fixture",
        "--output-prefix",
        "gs://fixture-bucket/core/",
        "--max-logical-catalog-bytes",
        "1000",
        *_pin_args("source_panel"),
        *_pin_args("t230_panel_release"),
    ]
    assert cli.main(
        materialize_argv,
        environ={cli.ENABLED_ENV: "1"},
        storage_client=object(),
    ) == 0
    receipt = _assert_receipt(
        capsys.readouterr().out,
        schema=cli.MATERIALIZE_RECEIPT_SCHEMA,
    )
    assert receipt["catalog_identity"] == catalog_identity
    assert receipt["catalog_created"] is True

    monkeypatch.setattr(
        cli.core_cloud,
        "reopen_sharded_core_v1_catalog_authority",
        lambda **_kwargs: reopened,
    )
    reopen_argv = ["reopen", "--execute", *_pin_args("root")]
    assert cli.main(
        reopen_argv,
        environ={cli.ENABLED_ENV: "1"},
        storage_client=object(),
    ) == 0
    receipt = _assert_receipt(
        capsys.readouterr().out, schema=cli.REOPEN_RECEIPT_SCHEMA
    )
    assert receipt["catalog_identity"] == catalog_identity
    assert receipt["root_identity"] == root_identity
    assert receipt["union_roster_membership_count"] == 54 * 80
