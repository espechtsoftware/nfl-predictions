"""Focused operational tests for the recourse realized publisher CLI."""

from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path

import pytest

from nfl_dfs.research import (
    corpus_r6_recourse_aware_initial_realized_bridge_v1 as bridge,
)
from nfl_dfs.research import corpus_r6_score_sprint_scorecard_v1 as scorecard


SCRIPT = Path(
    "scripts/run_corpus_r6_recourse_aware_initial_realized_bridge_v1.py"
)


def _module():
    spec = importlib.util.spec_from_file_location(
        "recourse_initial_realized_publisher_test", SCRIPT,
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
    scorefree_identity: dict[str, object], outcome_identity: dict[str, object],
) -> dict[str, object]:
    diagnostic = {
        "control_arm_result_sha256": "a" * 64,
        "treatment_arm_result_sha256": "b" * 64,
        "rotated_fit_paired_diagnostic_sha256": "c" * 64,
    }
    body = {
        "schema_version": bridge.BRIDGE_SCHEMA,
        "mode": bridge.MODE_ONE_SLATE_SMOKE,
        "scorefree_terminal_identity": scorefree_identity,
        "scorefree_report_identity": scorefree_identity,
        "outcome_authority_identity": outcome_identity,
        "scored_slate_count": 1,
        "rotated_fit_paired_diagnostic": diagnostic,
        "scorecard_eligible": False,
        "all_block_54_week_benchmark_comparable": False,
        "ranking_beside_all_block_54_week_benchmark_forbidden": True,
    }
    body["realized_bridge_sha256"] = bridge.canonical_sha256_v1(body)
    return body


class _UnusedReader:
    def read_exact(self, _: object) -> bytes:
        raise AssertionError("stubbed pure bridge must own reader calls")


class _Publisher:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.calls.append((uri, raw))
        return _identity(uri, raw, "9")


def _argv(
    scorefree_identity: dict[str, object],
    outcome_identity: dict[str, object],
    output_uri: str,
) -> list[str]:
    values = ["publish", "--mode", bridge.MODE_ONE_SLATE_SMOKE]
    for stem, identity in (
        ("scorefree-terminal", scorefree_identity),
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


def test_injected_cli_publishes_once_and_returns_compact_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    scorefree = _identity(bridge.SCOREFREE_TERMINAL_URI, b"scorefree")
    outcome = dict(bridge.OUTCOME_AUTHORITY_IDENTITY)
    report = _report(scorefree, outcome)
    observed: dict[str, object] = {}

    def build(**kwargs: object) -> dict[str, object]:
        observed.update(kwargs)
        return report

    monkeypatch.setattr(
        module.bridge,
        "build_recourse_aware_initial_realized_bridge_v1",
        build,
    )
    publisher = _Publisher()
    output_uri = (
        f"{bridge.OUTPUT_NAMESPACE}fixture/{bridge.SMOKE_OUTPUT_FILENAME}"
    )
    result = module.run_with_transports_v1(
        _argv(scorefree, outcome, output_uri),
        scorefree_reader=_UnusedReader(),
        outcome_reader=_UnusedReader(),
        publisher=publisher,
    )
    assert observed["scorefree_terminal_identity"] == scorefree
    assert observed["outcome_authority_identity"] == outcome
    assert observed["mode"] == bridge.MODE_ONE_SLATE_SMOKE
    assert len(publisher.calls) == 1
    assert publisher.calls[0] == (
        output_uri, bridge.canonical_json_bytes_v1(report),
    )
    assert result["schema_version"] == bridge.PUBLICATION_ENVELOPE_SCHEMA
    assert result["realized_bridge_identity"]["uri"] == output_uri
    assert "rotated_fit_paired_diagnostic" not in result
    assert result["scorecard_eligible"] is False


class PreconditionFailed(Exception):
    pass


class _Blob:
    def __init__(self, client: "_Client", name: str) -> None:
        self.client = client
        self.objects = client.objects
        self.name = name
        self.generation: str | None = None

    def upload_from_string(self, raw: bytes, **kwargs: object) -> None:
        self.client.calls.append(("upload", self.name, kwargs))
        if self.name in self.objects:
            raise PreconditionFailed
        self.objects[self.name] = ("17", raw)
        self.generation = "17"

    def reload(self, **kwargs: object) -> None:
        self.client.calls.append(("reload", self.name, kwargs))
        self.generation = self.objects[self.name][0]

    def download_as_bytes(self, **kwargs: object) -> bytes:
        self.client.calls.append(("download", self.name, kwargs))
        return self.objects[self.name][1]


class _Bucket:
    def __init__(self, client: "_Client") -> None:
        self.client = client

    def blob(self, name: str, generation: object = None) -> _Blob:
        blob = _Blob(self.client, name)
        if generation is not None:
            blob.generation = str(generation)
        return blob


class _Client:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[str, bytes]] = {}
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def bucket(self, _: str) -> _Bucket:
        return _Bucket(self)


def test_create_once_writer_accepts_only_equal_byte_retry() -> None:
    module = _module()
    uri = f"{bridge.OUTPUT_NAMESPACE}run/{bridge.SMOKE_OUTPUT_FILENAME}"
    client = _Client()
    retry = object()
    writer = module.CreateOnceGCSWriterV1(
        client,
        output_uri=uri,
        mode=bridge.MODE_ONE_SLATE_SMOKE,
        conditional_retry=retry,
    )
    raw = b'{"complete":true}'
    first = writer.publish_create_once(uri, raw)
    second = writer.publish_create_once(uri, raw)
    assert first == second
    assert writer.call_count == 2
    upload_calls = [kwargs for action, _, kwargs in client.calls if action == "upload"]
    reload_calls = [kwargs for action, _, kwargs in client.calls if action == "reload"]
    download_calls = [kwargs for action, _, kwargs in client.calls if action == "download"]
    assert upload_calls and all(call["timeout"] >= 900 for call in upload_calls)
    assert all(call["if_generation_match"] == 0 for call in upload_calls)
    assert all(call["retry"] is retry for call in upload_calls)
    assert reload_calls and all(call["timeout"] >= 900 for call in reload_calls)
    assert all(call["retry"] is retry for call in reload_calls)
    assert download_calls and all(call["timeout"] >= 900 for call in download_calls)
    assert all(call["retry"] is retry for call in download_calls)
    assert all(type(call["if_generation_match"]) is int for call in download_calls)
    with pytest.raises(
        module.RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="collision bytes differ",
    ):
        writer.publish_create_once(uri, b'{"complete":false}')


def test_registration_and_input_output_namespaces_are_fixed() -> None:
    registration = bridge.cloud_entrypoint_registration_v1()
    assert registration["entrypoint_relative_path"] == str(SCRIPT)
    assert registration["command"] == list(bridge.ENTRYPOINT_COMMAND)
    assert registration["realized_bridge_protocol_sha256"] == (
        bridge.REALIZED_PROTOCOL_SHA256
    )
    assert registration["publication_mode"] == "create-once-exact-reopen"
    assert registration["reachable_union_scored"] is False
    assert registration["lineup_rescore_performed"] is False
    assert registration["uses_realized_outcomes"] is True
    assert registration["persisted_realized_attribution_read"] is True
    assert registration["raw_outcome_source_queried"] is False
    assert registration["scorecard_eligible"] is False
    module = _module()
    scorefree = _identity(bridge.SCOREFREE_TERMINAL_URI, b"scorefree")
    assert module._scorefree_prefix(scorefree) == (
        bridge.SCOREFREE_TERMINAL_URI.removesuffix("terminal-root.json")
    )
    assert module._outcome_prefix(bridge.OUTCOME_AUTHORITY_IDENTITY) == (
        str(bridge.OUTCOME_AUTHORITY_IDENTITY["uri"]).removesuffix(
            "attribution-release.json"
        )
    )
    with pytest.raises(
        module.RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="fixed recourse realized namespace",
    ):
        module._safe_output_uri(
            f"gs://other-bucket/run/{bridge.SMOKE_OUTPUT_FILENAME}",
            mode=bridge.MODE_ONE_SLATE_SMOKE,
        )
    assert module._safe_output_uri(
        f"{bridge.OUTPUT_NAMESPACE}run/{bridge.FULL_OUTPUT_FILENAME}",
        mode=bridge.MODE_FULL_PANEL,
    ).endswith(bridge.FULL_OUTPUT_FILENAME)
    with pytest.raises(
        module.RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="fixed recourse realized namespace",
    ):
        module._safe_output_uri(
            f"{bridge.OUTPUT_NAMESPACE}run/{bridge.FULL_OUTPUT_FILENAME}",
            mode=bridge.MODE_ONE_SLATE_SMOKE,
        )
    wrong_outcome = dict(bridge.OUTCOME_AUTHORITY_IDENTITY)
    wrong_outcome["generation"] = "1"
    with pytest.raises(
        module.RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="frozen attribution release",
    ):
        module._outcome_prefix(wrong_outcome)


def test_local_preregistration_protocol_is_exact() -> None:
    module = _module()
    module._validate_local_protocol_v1()


def test_reader_rejects_prefix_escape_and_environment_gate_is_preclient() -> None:
    module = _module()
    reader = module.GenerationExactGCSReaderV1(
        _Client(),
        allowed_prefix="gs://allowed/prefix/",
        label="fixture",
        conditional_retry=object(),
    )
    escaped = _identity("gs://other/prefix/value.json", b"value")
    with pytest.raises(
        module.RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="escapes its exact prefix",
    ):
        reader.read_exact(escaped)
    with pytest.raises(
        module.RunCorpusR6RecourseAwareInitialRealizedBridgeV1Error,
        match="redirect/credential environment",
    ):
        module._preclient_environment_gate_v1({"HTTPS_PROXY": "proxy"})


def test_generation_exact_reader_uses_bounded_conditional_retry() -> None:
    module = _module()
    client = _Client()
    retry = object()
    raw = b"fixture"
    identity = _identity("gs://allowed/prefix/value.json", raw, "23")
    client.objects["prefix/value.json"] = ("23", raw)
    reader = module.GenerationExactGCSReaderV1(
        client,
        allowed_prefix="gs://allowed/prefix/",
        label="fixture",
        conditional_retry=retry,
    )
    assert reader.read_exact(identity) == raw
    action, _, kwargs = client.calls[-1]
    assert action == "download"
    assert kwargs["if_generation_match"] == 23
    assert kwargs["timeout"] >= 900
    assert kwargs["retry"] is retry


def test_scorecard_rejects_rotated_fit_diagnostic(tmp_path: Path) -> None:
    identity = _identity(bridge.SCOREFREE_TERMINAL_URI, b"scorefree")
    report = _report(identity, dict(bridge.OUTCOME_AUTHORITY_IDENTITY))
    path = tmp_path / bridge.FULL_OUTPUT_FILENAME
    path.write_bytes(bridge.canonical_json_bytes_v1(report))
    with pytest.raises(
        scorecard.CorpusR6ScoreSprintScorecardV1Error,
        match="unsupported local score artifact schema",
    ):
        scorecard.build_scorecard_v1([
            scorecard.ScorecardInputV1(label="recourse-rotated-fit", path=path),
        ])
