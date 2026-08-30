from __future__ import annotations

import json

import pytest

from scripts import run_corpus_r6_construction_allocation_grade_v1 as subject


CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/fixture/repo/image@sha256:" + "b" * 64


class _Store:
    def read_exact(self, identity):
        raise AssertionError(f"unexpected read: {identity}")

    def publish_create_once(self, uri, raw):
        raise AssertionError(f"unexpected publish: {uri} {raw!r}")


class _Lease:
    def __init__(self, *, store):
        self.store = store


def _write(tmp_path, name, value):
    path = (tmp_path / name).resolve()
    path.write_bytes(subject._canonical(value))
    return path


def _env(*, cloud: bool = False):
    result = {
        subject.ENABLE_ENV: subject.ENABLE_VALUE,
        subject.CODE_SHA_ENV: CODE_SHA,
        subject.IMAGE_ENV: IMAGE,
    }
    if cloud:
        result.update({
            "CLOUD_RUN_JOB": "fixture-grade-job",
            "CLOUD_RUN_TASK_INDEX": "0",
            "CLOUD_RUN_TASK_COUNT": "1",
            "CLOUD_RUN_TASK_ATTEMPT": "0",
        })
    return result


def test_default_off_rejects_before_prepare_callback(tmp_path, monkeypatch) -> None:
    request = {
        "schema_version": subject.PREPARE_REQUEST_SCHEMA,
        "run_id": "fixture-grade-run-v1",
        "grade_id": "fixture-grade-v1",
        "frozen_at": "2026-08-30T12:00:00Z",
        "code_sha": CODE_SHA,
        "immutable_image": IMAGE,
        "output_prefix": "gs://fixture/grades",
        "selection_terminal_envelope": {},
        "outcome_authority_identity": {},
    }
    path = _write(tmp_path, "prepare.json", request)
    called = []
    monkeypatch.setattr(
        subject.operator, "prepare_grade_manifest_v1",
        lambda **kwargs: called.append(kwargs),
    )
    with pytest.raises(
        subject.ConstructionAllocationGradeRunnerV1Error,
        match="literal --execute",
    ):
        subject.main(
            ["prepare", "--request", str(path)],
            environ={}, store=_Store(),
        )
    assert called == []


def test_prepare_delegates_outcome_blind_manifest_freeze(
    tmp_path, monkeypatch, capsys,
) -> None:
    request = {
        "schema_version": subject.PREPARE_REQUEST_SCHEMA,
        "run_id": "fixture-grade-run-v1",
        "grade_id": "fixture-grade-v1",
        "frozen_at": "2026-08-30T12:00:00Z",
        "code_sha": CODE_SHA,
        "immutable_image": IMAGE,
        "output_prefix": "gs://fixture/grades",
        "selection_terminal_envelope": {"fixture": "selection"},
        "outcome_authority_identity": {"fixture": "outcome"},
    }
    path = _write(tmp_path, "prepare.json", request)
    seen = {}

    def prepare(**kwargs):
        seen.update(kwargs)
        return {
            "schema_version": "fixture-prepared/v1",
            "outcome_authority_opened": False,
            "uses_realized_outcomes": False,
            "complete": True,
        }

    monkeypatch.setattr(subject.operator, "prepare_grade_manifest_v1", prepare)
    result = subject.main(
        ["prepare", "--request", str(path), "--execute"],
        environ=_env(), store=_Store(),
    )
    assert result["outcome_authority_opened"] is False
    assert seen["run_id"] == "fixture-grade-run-v1"
    assert seen["immutable_image"] == IMAGE
    assert json.loads(capsys.readouterr().out)["complete"] is True


def test_grade_requires_first_attempt_cloud_envelope_and_delegates(
    tmp_path, monkeypatch,
) -> None:
    manifest_identity = {
        "uri": "gs://fixture/grade-manifest.json",
        "generation": "17",
        "sha256": "c" * 64,
        "bytes": 100,
    }
    request = {
        "schema_version": subject.GRADE_REQUEST_SCHEMA,
        "manifest_identity": manifest_identity,
    }
    path = _write(tmp_path, "grade.json", request)
    manifest = {
        "code_sha": CODE_SHA,
        "immutable_image": IMAGE,
        "output_prefix": "gs://fixture/grades/fixture-grade-run-v1",
    }
    monkeypatch.setattr(
        subject.operator, "open_grade_manifest_v1",
        lambda *args, **kwargs: (manifest, manifest_identity),
    )
    seen = {}

    def publish(**kwargs):
        seen.update(kwargs)
        return {
            "schema_version": "fixture-published/v1",
            "historical_outcome_lease_released": False,
            "complete": True,
        }

    monkeypatch.setattr(subject.operator, "publish_grade_v1", publish)
    result = subject.main(
        ["grade", "--request", str(path), "--execute"],
        environ=_env(cloud=True), store=_Store(), lease_verifier_factory=_Lease,
    )
    assert result["historical_outcome_lease_released"] is False
    assert isinstance(seen["verify_live_lease"], _Lease)

    bad = _env(cloud=True)
    bad["CLOUD_RUN_TASK_ATTEMPT"] = "1"
    with pytest.raises(
        subject.ConstructionAllocationGradeRunnerV1Error,
        match="first-attempt Cloud Run task",
    ):
        subject.main(
            ["grade", "--request", str(path), "--execute"],
            environ=bad, store=_Store(), lease_verifier_factory=_Lease,
        )


def test_reopen_delegates_to_verify_only_catalog_lease_path(
    tmp_path, monkeypatch,
) -> None:
    manifest_identity = {
        "uri": "gs://fixture/grade-manifest.json",
        "generation": "17",
        "sha256": "c" * 64,
        "bytes": 100,
    }
    terminal_identity = {
        "uri": "gs://fixture/grade-terminal.json",
        "generation": "18",
        "sha256": "d" * 64,
        "bytes": 100,
        "create_once": True,
    }
    envelope = {
        "manifest_identity": manifest_identity,
        "terminal_identity": terminal_identity,
    }
    request = {
        "schema_version": subject.REOPEN_REQUEST_SCHEMA,
        "terminal_envelope": envelope,
        "code_sha": CODE_SHA,
        "immutable_image": IMAGE,
    }
    path = _write(tmp_path, "reopen.json", request)
    manifest = {"code_sha": CODE_SHA, "immutable_image": IMAGE}
    monkeypatch.setattr(
        subject.operator, "open_grade_manifest_v1",
        lambda *args, **kwargs: (manifest, manifest_identity),
    )
    lease_identity = {
        "uri": subject.operator.HISTORICAL_OUTCOME_LEASE_URI,
        "generation": "19",
        "sha256": "e" * 64,
        "bytes": 100,
    }
    seen = {}

    def reopen(*args, **kwargs):
        seen["args"] = args
        seen.update(kwargs)
        return {
            "historical_outcome_lease_identity": lease_identity,
            "complete": True,
        }

    monkeypatch.setattr(subject.operator, "reopen_grade_terminal_v1", reopen)
    result = subject.main(
        ["reopen", "--request", str(path), "--execute"],
        environ=_env(cloud=True), store=_Store(),
        lease_verifier_factory=_Lease,
    )
    assert result["historical_outcome_lease_identity"] == lease_identity
    assert result["historical_outcome_lease_released"] is False
    assert result["lease_release_owner"] == "external-launcher-watcher"
    assert isinstance(seen["verify_live_lease"], _Lease)


def test_request_must_be_absolute_and_canonical(tmp_path) -> None:
    relative = tmp_path / "request.json"
    relative.write_text("{\n  \"schema_version\": \"x\"\n}\n", encoding="utf-8")
    with pytest.raises(
        subject.ConstructionAllocationGradeRunnerV1Error,
        match="absolute|canonical",
    ):
        subject.main(
            ["prepare", "--request", str(relative.relative_to(tmp_path.parent))],
            environ=_env(), store=_Store(),
        )


def test_live_catalog_lease_verifier_is_named_read_only_and_rejects_forgery() -> None:
    body = {
        "version": "historical-outcome-active-v1",
        "run_id": "fixture-catalog-outcomes-v1",
        "job": "fixture-catalog-job",
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-30T12:00:00+00:00",
    }
    raw = subject._canonical(body, newline=True)
    identity = {
        "uri": subject.operator.HISTORICAL_OUTCOME_LEASE_URI,
        "generation": "1787987508020795",
        "sha256": subject.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }

    class KnownStore:
        def __init__(self):
            self.calls = []

        def open_known(self, uri, maximum_bytes):
            self.calls.append((uri, maximum_bytes))
            return raw, identity

    store = KnownStore()
    verifier = subject.GCSLiveHistoricalOutcomeLeaseVerifierV1(store=store)
    receipt = verifier(
        expected_identity=identity,
        catalog_run_id="fixture-catalog-outcomes-v1",
    )
    assert receipt == {"body": body, "object_receipt": identity}
    assert store.calls == [(
        subject.operator.HISTORICAL_OUTCOME_LEASE_URI,
        verifier.MAXIMUM_LEASE_BYTES,
    )]
    assert not hasattr(verifier, "acquire")
    assert not hasattr(verifier, "release")
    assert not hasattr(verifier, "delete")

    with pytest.raises(
        subject.ConstructionAllocationGradeRunnerV1Error,
        match="current live generation",
    ):
        verifier(
            expected_identity={**identity, "generation": "forged-generation"},
            catalog_run_id="fixture-catalog-outcomes-v1",
        )
