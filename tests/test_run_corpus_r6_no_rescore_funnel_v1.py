"""Hermetic transport tests for the guarded R6 no-rescore funnel CLI."""

from __future__ import annotations

from argparse import Namespace
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

from scripts import run_corpus_r6_no_rescore_funnel_v1 as cli


class _NotFound(Exception):
    code = 404


class _PreconditionFailed(Exception):
    code = 412


class _FakeBlob:
    def __init__(
        self, store: "_FakeClient", key: str, generation: int | None,
    ) -> None:
        self._store = store
        self._key = key
        self._requested_generation = generation
        self.generation: int | None = None

    def _resolve(self) -> int:
        generation = self._requested_generation
        if generation is None:
            generation = self._store.current.get(self._key)
        if (
            generation is None
            or (self._key, generation) not in self._store.versions
        ):
            raise _NotFound(self._key)
        return generation

    def reload(self, if_generation_match: int | None = None) -> None:
        generation = self._resolve()
        if if_generation_match is not None and generation != if_generation_match:
            raise _PreconditionFailed(self._key)
        self.generation = generation

    def download_as_bytes(self, if_generation_match: int | None = None) -> bytes:
        generation = self._resolve()
        if if_generation_match is not None and generation != if_generation_match:
            raise _PreconditionFailed(self._key)
        return self._store.versions[(self._key, generation)]

    def upload_from_string(
        self,
        raw: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        self._store.upload_calls += 1
        behavior = (
            self._store.behaviors.pop(0)
            if self._store.behaviors else "success"
        )
        if self._key in self._store.current:
            raise _PreconditionFailed(self._key)
        if behavior == "fail":
            raise RuntimeError("transport failed before create")
        self._store.force(self._key, raw)
        if behavior == "ambiguous-success":
            raise RuntimeError("transport failed after create")


class _FakeBucket:
    def __init__(self, store: "_FakeClient", name: str) -> None:
        self._store = store
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self._store, f"{self._name}/{name}", generation)


class _FakeClient:
    def __init__(self, *behaviors: str) -> None:
        self.behaviors = list(behaviors)
        self.versions: dict[tuple[str, int], bytes] = {}
        self.current: dict[str, int] = {}
        self.next_generation = 100
        self.upload_calls = 0

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def force(self, key: str, raw: bytes) -> int:
        self.next_generation += 1
        generation = self.next_generation
        self.versions[(key, generation)] = bytes(raw)
        self.current[key] = generation
        return generation


def _key(uri: str) -> str:
    bucket, name = uri[5:].split("/", 1)
    return f"{bucket}/{name}"


def _identity(uri: str, raw: bytes, generation: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def test_generation_pinned_reader_does_not_follow_latest() -> None:
    uri = "gs://fixture/path/value.json"
    client = _FakeClient()
    first = b'{"version":1}'
    second = b'{"version":2}'
    first_generation = client.force(_key(uri), first)
    client.force(_key(uri), second)
    store = cli.GenerationPinnedGCSV1(client)

    assert store.read_exact(_identity(uri, first, first_generation)) == first

    for field, value in (
        ("sha256", "0" * 64),
        ("bytes", len(first) + 1),
        ("generation", str(first_generation + 99)),
    ):
        changed = _identity(uri, first, first_generation)
        changed[field] = value
        with pytest.raises(cli.RunCorpusR6NoRescoreFunnelV1Error):
            store.read_exact(changed)


def test_create_once_retries_only_identical_bytes_while_absent() -> None:
    client = _FakeClient("fail", "success")
    store = cli.GenerationPinnedGCSV1(client)
    uri = "gs://fixture/path/release.json"
    raw = b'{"complete":true}'

    identity = store.publish_create_once(uri, raw)

    assert client.upload_calls == 2
    assert store.read_exact(identity) == raw


def test_create_once_recovers_ambiguous_success_without_retry() -> None:
    client = _FakeClient("ambiguous-success")
    store = cli.GenerationPinnedGCSV1(client)
    raw = b'{"complete":true}'

    identity = store.publish_create_once("gs://fixture/path/release.json", raw)

    assert client.upload_calls == 1
    assert identity["sha256"] == sha256(raw).hexdigest()


def test_create_once_rejects_different_existing_bytes() -> None:
    client = _FakeClient()
    uri = "gs://fixture/path/release.json"
    client.force(_key(uri), b'{"complete":false}')
    store = cli.GenerationPinnedGCSV1(client)

    with pytest.raises(
        cli.RunCorpusR6NoRescoreFunnelV1Error,
        match="existing create-once object differs",
    ):
        store.publish_create_once(uri, b'{"complete":true}')

    assert client.upload_calls == 1


def test_create_once_accepts_only_an_identical_existing_object() -> None:
    client = _FakeClient()
    uri = "gs://fixture/path/release.json"
    raw = b'{"complete":true}'
    generation = client.force(_key(uri), raw)
    store = cli.GenerationPinnedGCSV1(client)

    identity = store.publish_create_once(uri, raw)

    assert identity == _identity(uri, raw, generation)
    assert client.upload_calls == 1


def test_create_once_fails_after_bounded_absent_attempts() -> None:
    client = _FakeClient(*(["fail"] * cli.CREATE_ONCE_ATTEMPTS))
    store = cli.GenerationPinnedGCSV1(client)

    with pytest.raises(
        cli.RunCorpusR6NoRescoreFunnelV1Error,
        match="absent after bounded attempts",
    ):
        store.publish_create_once(
            "gs://fixture/path/release.json", b'{"complete":true}'
        )

    assert client.upload_calls == cli.CREATE_ONCE_ATTEMPTS


def test_adopted_attribution_identity_and_output_namespace_are_fixed() -> None:
    args = Namespace(
        attribution_root_uri=cli.ATTRIBUTION_ROOT_IDENTITY["uri"],
        attribution_root_generation=cli.ATTRIBUTION_ROOT_IDENTITY["generation"],
        attribution_root_sha256=cli.ATTRIBUTION_ROOT_IDENTITY["sha256"],
        attribution_root_bytes=cli.ATTRIBUTION_ROOT_IDENTITY["bytes"],
    )
    assert cli._attribution_identity(args) == cli.ATTRIBUTION_ROOT_IDENTITY

    args.attribution_root_generation = "1"
    with pytest.raises(
        cli.RunCorpusR6NoRescoreFunnelV1Error,
        match="adopted terminal release",
    ):
        cli._attribution_identity(args)

    governed = cli._root_uri("20260827-r6-no-rescore-funnel-v1")
    assert cli._validate_root_uri(governed) == governed
    with pytest.raises(
        cli.RunCorpusR6NoRescoreFunnelV1Error,
        match="governed namespace",
    ):
        cli._validate_root_uri("gs://mirror/release.json")


def test_winner_authority_file_is_exactly_pinned(tmp_path: Path) -> None:
    authority_path = Path(
        "reports/r6-no-rescore-funnel-runs/"
        "20260827-r6-no-rescore-funnel-v1/winner-registry-authority.json"
    )
    retained = cli._authority(authority_path)
    assert retained["terminal"] is True

    changed = tmp_path / "winner-registry-authority.json"
    changed.write_bytes(authority_path.read_bytes() + b" ")
    with pytest.raises(
        cli.RunCorpusR6NoRescoreFunnelV1Error,
        match="authority must be canonical",
    ):
        cli._authority(changed)


def _common_cli_args() -> list[str]:
    return [
        "--execute",
        "--attribution-root-uri", str(cli.ATTRIBUTION_ROOT_IDENTITY["uri"]),
        "--attribution-root-generation",
        str(cli.ATTRIBUTION_ROOT_IDENTITY["generation"]),
        "--attribution-root-sha256",
        str(cli.ATTRIBUTION_ROOT_IDENTITY["sha256"]),
        "--attribution-root-bytes", str(cli.ATTRIBUTION_ROOT_IDENTITY["bytes"]),
    ]


def test_parser_supports_conventional_subcommand_first_order() -> None:
    publish = cli._parser().parse_args([
        "publish", *_common_cli_args(),
        "--output-run-id", "20260827-r6-no-rescore-funnel-v1",
    ])
    assert publish.command == "publish"
    assert publish.execute is True

    reopen = cli._parser().parse_args([
        "reopen", *_common_cli_args(),
        "--funnel-root-uri", cli._root_uri(
            "20260827-r6-no-rescore-funnel-v1"
        ),
        "--funnel-root-generation", "1",
        "--funnel-root-sha256", "4" * 64,
        "--funnel-root-bytes", "1",
    ])
    assert reopen.command == "reopen"
    assert reopen.execute is True


def test_main_rejects_missing_double_execution_gate_before_cloud_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(cli.ENABLED_ENV, raising=False)
    args = [
        "run_corpus_r6_no_rescore_funnel_v1.py", "publish",
        *[value for value in _common_cli_args() if value != "--execute"],
        "--output-run-id", "20260827-r6-no-rescore-funnel-v1",
    ]
    monkeypatch.setattr(sys, "argv", args)

    with pytest.raises(
        cli.RunCorpusR6NoRescoreFunnelV1Error,
        match="execution requires",
    ):
        cli.main()


def test_main_publish_and_reopen_orchestration_is_guarded_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from google.cloud import storage

    client = _FakeClient()
    winner = deepcopy(cli.funnel.ADOPTED_WINNER_REGISTRY_IDENTITY)
    release = {
        "funnel_release_sha256": "2" * 64,
        "source_slate_count": 54,
        "population_result": {"lineup_count": 199_244},
        "winner_target_census": {"included_slate_count": 51},
        "predecessors": {
            "attribution_release_root_identity": deepcopy(
                cli.ATTRIBUTION_ROOT_IDENTITY
            ),
            "winner_registry_identity": winner,
            "winner_registry_authority": {
                "winner_registry_authority_sha256": (
                    cli.funnel.ADOPTED_WINNER_REGISTRY_AUTHORITY_SHA256
                ),
            },
        },
    }
    calls: list[str] = []

    def build(**_kwargs: object) -> dict[str, object]:
        calls.append("build")
        return deepcopy(release)

    def reopen(identity: object, **_kwargs: object):
        calls.append("reopen")
        return deepcopy(release), dict(identity)  # type: ignore[arg-type]

    monkeypatch.setattr(storage, "Client", lambda *, project: client)
    monkeypatch.setattr(cli.funnel, "build_no_rescore_funnel_release_v1", build)
    monkeypatch.setattr(cli.funnel, "reopen_no_rescore_funnel_release_v1", reopen)
    monkeypatch.setenv(cli.ENABLED_ENV, "1")
    run_id = "20260827-r6-no-rescore-funnel-v1"
    monkeypatch.setattr(sys, "argv", [
        "run_corpus_r6_no_rescore_funnel_v1.py", "publish",
        *_common_cli_args(), "--output-run-id", run_id,
    ])

    cli.main()

    published = json.loads(capsys.readouterr().out)
    assert published["command"] == "publish"
    assert calls == ["build", "reopen"]
    root_identity = published["funnel_release_identity"]

    calls.clear()
    monkeypatch.setattr(sys, "argv", [
        "run_corpus_r6_no_rescore_funnel_v1.py", "reopen",
        *_common_cli_args(),
        "--funnel-root-uri", root_identity["uri"],
        "--funnel-root-generation", root_identity["generation"],
        "--funnel-root-sha256", root_identity["sha256"],
        "--funnel-root-bytes", str(root_identity["bytes"]),
    ])

    cli.main()

    reopened = json.loads(capsys.readouterr().out)
    assert reopened["command"] == "reopen"
    assert reopened["funnel_release_identity"] == root_identity
    assert calls == ["reopen"]


def test_summary_retains_both_predecessor_authorities() -> None:
    attribution = deepcopy(cli.ATTRIBUTION_ROOT_IDENTITY)
    winner = {
        "uri": "gs://fixture/winner.json",
        "generation": "1",
        "sha256": "1" * 64,
        "bytes": 1,
    }
    release = {
        "funnel_release_sha256": "2" * 64,
        "source_slate_count": 54,
        "population_result": {"lineup_count": 199_244},
        "winner_target_census": {"included_slate_count": 51},
        "predecessors": {
            "attribution_release_root_identity": attribution,
            "winner_registry_identity": winner,
            "winner_registry_authority": {
                "winner_registry_authority_sha256": "3" * 64,
            },
        },
    }
    identity = {
        "uri": cli._root_uri("20260827-r6-no-rescore-funnel-v1"),
        "generation": "1",
        "sha256": "4" * 64,
        "bytes": 1,
    }

    summary = cli._summary(
        command="reopen", release_value=release, identity=identity
    )

    assert summary["attribution_release_root_identity"] == attribution
    assert summary["winner_registry_identity"] == winner
    assert summary["winner_registry_authority_sha256"] == "3" * 64
    assert summary["lineup_rescore_performed"] is False
    assert summary["outcome_source_read"] is False
