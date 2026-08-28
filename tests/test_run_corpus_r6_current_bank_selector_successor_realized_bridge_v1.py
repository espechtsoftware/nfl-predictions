"""Focused operational tests for the successor realized publisher CLI."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_realized_bridge_v1 as bridge,
)


SCRIPT = Path(
    "scripts/run_corpus_r6_current_bank_selector_successor_realized_bridge_v1.py"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "selector_successor_realized_publisher_test", SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(uri: str, raw: bytes, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _report(
    terminal_identity: dict[str, object], outcome_identity: dict[str, object],
) -> dict[str, object]:
    body = {
        "schema_version": bridge.BRIDGE_SCHEMA,
        "mode": bridge.MODE_ONE_SLATE_SMOKE,
        "terminal_aggregate_identity": terminal_identity,
        "outcome_authority_identity": outcome_identity,
        "scored_slate_count": 1,
        "finalist_count": 4,
    }
    body["realized_bridge_sha256"] = bridge.canonical_sha256_v1(body)
    return body


class _UnusedReader:
    def read_exact(self, _: object) -> bytes:
        raise AssertionError("stubbed pure bridge must own the reader calls")


class _Publisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.calls.append((uri, raw))
        return _identity(uri, raw, "9")


def _argv(
    terminal_identity: dict[str, object], outcome_identity: dict[str, object],
    output_uri: str,
) -> list[str]:
    values = ["publish", "--mode", bridge.MODE_ONE_SLATE_SMOKE]
    for stem, identity in (
        ("terminal-aggregate", terminal_identity),
        ("outcome-authority", outcome_identity),
    ):
        values.extend([
            f"--{stem}-uri", str(identity["uri"]),
            f"--{stem}-generation", str(identity["generation"]),
            f"--{stem}-sha256", str(identity["sha256"]),
            f"--{stem}-bytes", str(identity["bytes"]),
        ])
    values.extend(["--output-uri", output_uri])
    return values


def test_injected_cli_publishes_once_and_returns_compact_identity_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    terminal = _identity(
        f"{contract.OUTPUT_NAMESPACE}fixture/evaluations/terminal-aggregate.json",
        b"terminal",
    )
    outcome = _identity(
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        "r6-full-union/attribution-release.json",
        b"outcome",
    )
    report = _report(terminal, outcome)
    observed: dict[str, object] = {}

    def build(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return report

    monkeypatch.setattr(module.bridge, "build_successor_realized_bridge_v1", build)
    publisher = _Publisher()
    output_uri = (
        f"{contract.OUTPUT_NAMESPACE}fixture/realized/{bridge.OUTPUT_FILENAME}"
    )
    result = module.run_with_transports_v1(
        _argv(terminal, outcome, output_uri),
        terminal_reader=_UnusedReader(),
        outcome_reader=_UnusedReader(),
        publisher=publisher,
    )
    assert observed["terminal_aggregate_identity"] == terminal
    assert observed["outcome_authority_identity"] == outcome
    assert observed["mode"] == bridge.MODE_ONE_SLATE_SMOKE
    assert len(publisher.calls) == 1
    assert publisher.calls[0][0] == output_uri
    assert publisher.calls[0][1] == bridge.canonical_json_bytes_v1(report)
    assert result["schema_version"] == bridge.PUBLICATION_ENVELOPE_SCHEMA
    assert result["realized_bridge_identity"]["uri"] == output_uri
    assert "finalist_results" not in result


class PreconditionFailed(Exception):
    pass


class _Blob:
    def __init__(self, objects: dict[str, tuple[str, bytes]], name: str) -> None:
        self.objects = objects
        self.name = name
        self.generation: str | None = None

    def upload_from_string(self, raw: bytes, **_: object) -> None:
        if self.name in self.objects:
            raise PreconditionFailed
        self.objects[self.name] = ("17", raw)
        self.generation = "17"

    def reload(self, **_: object) -> None:
        self.generation = self.objects[self.name][0]

    def download_as_bytes(self, **_: object) -> bytes:
        return self.objects[self.name][1]


class _Bucket:
    def __init__(self, objects: dict[str, tuple[str, bytes]]) -> None:
        self.objects = objects

    def blob(self, name: str, generation: object = None) -> _Blob:
        blob = _Blob(self.objects, name)
        if generation is not None:
            blob.generation = str(generation)
        return blob


class _Client:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[str, bytes]] = {}

    def bucket(self, _: str) -> _Bucket:
        return _Bucket(self.objects)


def test_create_once_writer_accepts_only_equal_byte_retry() -> None:
    module = _module()
    uri = f"{contract.OUTPUT_NAMESPACE}run/realized/{bridge.OUTPUT_FILENAME}"
    client = _Client()
    writer = module.CreateOnceGCSWriterV1(client, output_uri=uri)
    raw = b'{"complete":true}'
    first = writer.publish_create_once(uri, raw)
    second = writer.publish_create_once(uri, raw)
    assert first == second
    assert writer.call_count == 2
    with pytest.raises(
        module.RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
        match="collision bytes differ",
    ):
        writer.publish_create_once(uri, b'{"complete":false}')


def test_cloud_entry_registration_and_namespace_are_fixed() -> None:
    registration = bridge.cloud_entrypoint_registration_v1()
    assert registration["entrypoint_relative_path"] == str(SCRIPT)
    assert registration["command"] == list(bridge.ENTRYPOINT_COMMAND)
    assert registration["publication_mode"] == "create-once-exact-reopen"
    assert registration["lineup_rescore_performed"] is False
    assert registration["decision_authority"] is False
    module = _module()
    terminal = _identity(
        f"{contract.OUTPUT_NAMESPACE}successor/evaluations/terminal-aggregate.json",
        b"terminal",
    )
    assert module._namespace_for_terminal_graph(terminal) == (
        contract.OUTPUT_NAMESPACE
    )
    assert (
        f"{contract.OUTPUT_NAMESPACE}source-control/projections/source-000.json"
        .startswith(module._namespace_for_terminal_graph(terminal))
    )
    with pytest.raises(
        module.RunCorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
        match="fixed successor realized namespace",
    ):
        module._safe_output_uri(
            f"gs://other-bucket/run/{bridge.OUTPUT_FILENAME}"
        )
