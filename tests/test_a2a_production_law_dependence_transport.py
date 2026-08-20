from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any

from google.api_core.exceptions import NotFound, PreconditionFailed
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_a2a_production_law_dependence_remeasurement as finish  # noqa: E402


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _job(*, generation: int, code: str, image: str) -> dict[str, Any]:
    contract = finish._execution_contract(code_sha=code, image=image)
    return {
        "metadata": {
            "name": finish.JOB,
            "uid": finish.JOB_UID,
            "generation": generation,
        },
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": image,
                    "command": contract["command"],
                    "args": contract["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["env"].items()
                    ],
                    "resources": {"limits": contract["resources"]},
                }],
                "volumes": [],
                "maxRetries": 0,
                "timeoutSeconds": finish.TIMEOUT_SECONDS,
                "serviceAccountName": finish.SERVICE_ACCOUNT,
            }},
        }}},
    }


def _build(*, build_id: str, code: str, image: str) -> dict[str, Any]:
    tag = finish._image_tag(code)
    source = {"url": finish.GIT_SOURCE_URL, "revision": code}
    return {
        "id": build_id,
        "status": "SUCCESS",
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
        "substitutions": {"_IMAGE": tag, "COMMIT_SHA": code},
        "steps": finish._expected_cloud_build_steps(tag),
        "options": {"machineType": "E2_HIGHCPU_8"},
        "results": {"images": [{
            "name": tag, "digest": image.rsplit("@", 1)[1],
        }]},
        "images": [tag],
        "artifacts": {"images": [tag]},
        "timeout": "10800s",
        "serviceAccount": finish.BUILD_SERVICE_ACCOUNT,
        "logsBucket": finish.BUILD_LOGS_BUCKET,
    }


def _terminal_row(status: str = "True") -> dict[str, Any]:
    return {"status": {"conditions": [{
        "type": "Completed", "status": status,
    }]}}


def _manifest() -> dict[str, Any]:
    code = "a" * 40
    image = finish.IMAGE_REPOSITORY + "@sha256:" + "b" * 64
    return finish._build_launch_manifest(
        code_sha=code,
        image=image,
        build_id="build-12345678",
        build_metadata=_build(
            build_id="build-12345678", code=code, image=image,
        ),
        job_before=_job(generation=10, code=code, image=image),
        job_after=_job(generation=11, code=code, image=image),
        executions_before=[_terminal_row()],
        executions_after=[_terminal_row()],
        schedulers_before=[],
        schedulers_after=[],
        prefix_before=finish._absence_receipt(
            kind="result-prefix", checked_at="2026-08-20T19:00:00+00:00",
        ),
        prefix_after=finish._absence_receipt(
            kind="result-prefix", checked_at="2026-08-20T19:01:00+00:00",
        ),
        lease_before=finish._absence_receipt(
            kind="historical-outcome-lease",
            checked_at="2026-08-20T19:00:00+00:00",
        ),
        lease_after=finish._absence_receipt(
            kind="historical-outcome-lease",
            checked_at="2026-08-20T19:01:00+00:00",
        ),
        frozen_at="2026-08-20T19:02:00+00:00",
        root=ROOT,
        git_loader=lambda root, code_sha, relative: (root / relative).read_bytes(),
    )


def _execution(manifest: dict[str, Any], name: str) -> dict[str, Any]:
    contract = manifest["execution_contract"]
    return {
        "metadata": {
            "name": name,
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": finish.JOB,
                "run.googleapis.com/jobUid": finish.JOB_UID,
                "run.googleapis.com/jobGeneration": manifest["job"][
                    "generation"
                ],
            },
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "completionTime": "2026-08-20T20:00:00Z",
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": contract["image"],
                    "command": contract["command"],
                    "args": contract["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["env"].items()
                    ],
                    "resources": {"limits": contract["resources"]},
                }],
                "volumes": [],
                "maxRetries": 0,
                "timeoutSeconds": finish.TIMEOUT_SECONDS,
                "serviceAccountName": finish.SERVICE_ACCOUNT,
            }},
        },
    }


def _report(worlds: int) -> dict[str, Any]:
    return {
        "population": {"rows": 9_469, "slates": 54, "n_sims": worlds},
        "cells": {
            cell: {
                "realized_estimate": finish.decision.REALIZED_TARGETS[cell],
                "simulated_estimate": finish.decision.REALIZED_TARGETS[cell],
                "log_simulated_to_realized": 0.0,
                "cluster_ci95_low": -0.01,
                "cluster_ci95_high": 0.01,
                "equivalence_band_abs_log": (
                    finish.decision.EQUIVALENCE_BANDS[cell]
                ),
                "supported": True,
                "classification": "equivalent",
            }
            for cell in finish.decision.REGISTERED_CELLS
        },
    }


def _result(manifest: dict[str, Any]) -> dict[str, Any]:
    blocks = {
        block: _report(10_000) for block in finish.decision.REGISTERED_BLOCKS
    }
    aggregate = _report(50_000)
    judged = finish.decision.evaluate_remeasurement(blocks, aggregate)
    source_lock = json.loads((
        ROOT / finish.IMPLEMENTATION_PATHS["source_lock"]
    ).read_text())
    artifacts = [{
        "season": row["season"],
        "week": row["week"],
        "block": finish.decision.REGISTERED_BLOCKS[row["seed"]],
        "panel_run_id": row["panel_run_id"],
        "uri": row["uri"],
        "generation": str(row["generation"]),
        "sha256": row["sha256"],
        "bytes": row["bytes"],
    } for row in source_lock["artifact_receipts"]]
    mechanism = json.loads((
        ROOT / finish.IMPLEMENTATION_PATHS["mechanism_license"]
    ).read_text())
    result = {
        **judged,
        **judged["licenses"],
        "run_id": finish.RUN_ID,
        "protocol_sha256": finish.runner.PROTOCOL_SHA256,
        "code_sha": manifest["code"]["commit_sha"],
        "analysis_image": manifest["image"]["uri"],
        "static_source_hashes": finish.runner._validate_static_sources(),
        "mechanism_license": {
            "uri": finish.runner.A2A_RESULT_URI,
            "generation": finish.runner.A2A_RESULT_GENERATION,
            "sha256": finish.runner.A2A_RESULT_SHA256,
            "bytes": finish.runner.A2A_RESULT_BYTES,
            "disposition": "a2a-scorefree-mechanism-passes",
            "historical_remeasurement_licensed": True,
        },
        "control_reference": finish.runner._validate_control_reference(),
        "source_lock": {
            "uri": finish.runner.a2a_source.SOURCE_LOCK_URI,
            "generation": finish.runner.a2a_source.SOURCE_LOCK_GENERATION,
            "sha256": finish.runner.a2a_source.SOURCE_LOCK_SHA256,
            "bytes": finish.runner.a2a_source.SOURCE_LOCK_BYTES,
        },
        "source_artifacts": artifacts,
        "block_mechanics": {
            block: mechanism["block_reports"][block]["mechanics"]
            for block in finish.decision.REGISTERED_BLOCKS
        },
        "coverage_accounting": finish.decision.support_accounting(
            source_lock["catalog"]
        ),
        "outcome_query": {
            "job_id": "query-job",
            "location": "US",
            "created": "2026-08-20T20:00:00+00:00",
            "started": "2026-08-20T20:00:01+00:00",
            "ended": "2026-08-20T20:00:02+00:00",
            "total_bytes_processed": 100,
            "query_sha256": _sha(finish.runner.OUTCOME_SQL.encode()),
            "selected_fields": ["season", "week", "player_id", "actual"],
        },
        "outcome_query_issued_after_complete_source_preflight": True,
        "outcome_population": {
            "slates": 54,
            "eligible_player_rows": 9_469,
            "missing_eligible_outcomes": 0,
            "duplicate_eligible_keys": 0,
        },
    }
    assert set(result) == finish.RESULT_KEYS
    return result


def test_manifest_binds_direct_git_build_exact_job_and_all_sources() -> None:
    manifest = _manifest()
    assert manifest["job"] == {
        "name": finish.JOB,
        "uid": finish.JOB_UID,
        "prior_generation": "10",
        "prior_spec_sha256": finish._job_spec_sha256(_job(
            generation=10,
            code=manifest["code"]["commit_sha"],
            image=manifest["image"]["uri"],
        )),
        "generation": "11",
        "spec_sha256": finish._job_spec_sha256(_job(
            generation=11,
            code=manifest["code"]["commit_sha"],
            image=manifest["image"]["uri"],
        )),
        "service_account": finish.SERVICE_ACCOUNT,
        "update_mode": "reuse-only-update-existing",
        "scheduler_target_absent": True,
    }
    assert manifest["execution_contract"]["tasks"] == 1
    assert manifest["execution_contract"]["max_retries"] == 0
    assert manifest["execution_contract"]["resources"] == {
        "cpu": "8", "memory": "32Gi",
    }
    assert set(manifest["implementation"]) == set(finish.IMPLEMENTATION_PATHS)
    assert manifest["implementation"]["outcome_blind_smoke"]["sha256"] == (
        "a8d61cd8b4646af70dea6ac30c79e53b61d5c0f72be9f7c13c7f88e500531c7f"
    )
    altered = _build(
        build_id=manifest["build"]["id"],
        code=manifest["code"]["commit_sha"], image=manifest["image"]["uri"],
    )
    altered["steps"][1]["args"][-1] = "elsewhere"
    with pytest.raises(RuntimeError, match="Build/test/image gate"):
        finish._validate_build_metadata(
            altered, build_id=manifest["build"]["id"],
            code_sha=manifest["code"]["commit_sha"],
            image=manifest["image"]["uri"],
        )


def test_smoke_staging_allows_only_exact_committed_receipt(
    tmp_path: Path,
) -> None:
    out = tmp_path / "reports/a2a-production-law-dependence-runs" / finish.RUN_ID
    out.mkdir(parents=True)
    source = ROOT / finish.IMPLEMENTATION_PATHS["outcome_blind_smoke"]
    retained = source.read_bytes()
    (out / "local-outcome-blind-smoke.json").write_bytes(retained)
    finish._validate_smoke_staging(
        out, code_sha="a" * 40, root=tmp_path,
        git_loader=lambda root, code_sha, relative: retained,
    )
    (out / "unexpected.txt").write_text("no")
    with pytest.raises(RuntimeError, match="staging inventory"):
        finish._validate_smoke_staging(
            out, code_sha="a" * 40, root=tmp_path,
            git_loader=lambda root, code_sha, relative: retained,
        )


def test_preupdate_rejects_source_running_job_and_scheduler_target() -> None:
    manifest = _manifest()
    code, image = manifest["code"]["commit_sha"], manifest["image"]["uri"]
    build = _build(build_id="build-12345678", code=code, image=image)
    changed = copy.deepcopy(build)
    changed["sourceProvenance"]["resolvedGitSource"]["revision"] = "d" * 40
    with pytest.raises(RuntimeError, match="resolved Git source"):
        finish._validate_prepare_inputs(
            code_sha=code, image=image, build_id="build-12345678",
            build_metadata=changed, job_before=_job(
                generation=10, code=code, image=image,
            ), executions_before=[], schedulers_before=[], root=ROOT,
            git_loader=lambda root, code_sha, relative: (
                root / relative
            ).read_bytes(),
        )
    with pytest.raises(RuntimeError, match="not idle"):
        finish._validate_job_idle([{"status": {"conditions": []}}])
    with pytest.raises(RuntimeError, match="scheduler target"):
        finish._validate_unscheduled([{"httpTarget": {"uri": (
            "https://run.googleapis.com/v2/projects/p/locations/us-central1"
            f"/jobs/{finish.JOB}:run"
        )}}])


def test_job_and_execution_contracts_reject_inherited_state_or_retry() -> None:
    manifest = _manifest()
    code, image = manifest["code"]["commit_sha"], manifest["image"]["uri"]
    job = _job(generation=11, code=code, image=image)
    task = job["spec"]["template"]["spec"]["template"]["spec"]
    task["volumes"] = [{"name": "inherited"}]
    with pytest.raises(RuntimeError, match="executable contract"):
        finish._validate_job_spec(job, code_sha=code, image=image)

    name = finish.JOB + "-abc12"
    execution = _execution(manifest, name)
    execution["status"]["retriedCount"] = 1
    with pytest.raises(RuntimeError, match="strict terminal success"):
        finish._validate_execution(
            execution, execution=name, manifest=manifest,
        )
    execution = _execution(manifest, name)
    execution["status"]["conditions"] = []
    with pytest.raises(RuntimeError, match="strict terminal success"):
        finish._validate_execution(execution, execution=name, manifest=manifest)
    execution = _execution(manifest, name)
    execution["spec"]["template"]["spec"]["containers"][0]["image"] = (
        finish.IMAGE_REPOSITORY + "@sha256:" + "0" * 64
    )
    with pytest.raises(RuntimeError, match="execution contract"):
        finish._validate_execution(execution, execution=name, manifest=manifest)
    execution = _execution(manifest, name)
    execution["status"]["conditions"].append({
        "type": "Completed", "status": "True",
    })
    with pytest.raises(RuntimeError, match="strict terminal success"):
        finish._validate_execution(execution, execution=name, manifest=manifest)


def test_result_replay_rejects_forged_disposition_and_coverage() -> None:
    manifest = _manifest()
    result = _result(manifest)
    finish._validate_result(result, manifest=manifest)

    forged = copy.deepcopy(result)
    forged["disposition"] = "a2a-law-shape-miss-qb-wr-overshoot"
    with pytest.raises(RuntimeError, match="judgment differs"):
        finish._validate_result(forged, manifest=manifest)
    forged = copy.deepcopy(result)
    forged["coverage_accounting"]["covered_groups"] -= 1
    with pytest.raises(RuntimeError, match="coverage"):
        finish._validate_result(forged, manifest=manifest)
    forged = copy.deepcopy(result)
    forged["outcome_query"]["location"] = "EU"
    with pytest.raises(RuntimeError, match="outcome-query"):
        finish._validate_result(forged, manifest=manifest)
    forged = copy.deepcopy(result)
    forged["source_artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="source-artifact"):
        finish._validate_result(forged, manifest=manifest)
    forged = copy.deepcopy(result)
    forged["mechanism_license"]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="upstream reference"):
        finish._validate_result(forged, manifest=manifest)


class FakeBlob:
    def __init__(self, client: "FakeStorage", uri: str, generation: int | None):
        self.client = client
        self.uri = uri
        self.requested_generation = generation
        self.name = finish._gcs_parts(uri)[1]
        self.generation: int | None = None
        self.metageneration: int | None = None
        self.size: int | None = None

    def _row(self) -> dict[str, Any]:
        row = self.client.objects.get(self.uri)
        if row is None or (
            self.requested_generation is not None
            and row["generation"] != self.requested_generation
        ):
            raise NotFound("missing")
        return row

    def reload(self) -> None:
        row = self._row()
        self.generation = row["generation"]
        self.metageneration = row["metageneration"]
        self.size = len(row["raw"])
        self.client.events.append(("reload", self.uri, self.requested_generation))

    def download_as_bytes(self, if_generation_match: int | None = None) -> bytes:
        row = self._row()
        assert if_generation_match == row["generation"]
        self.reload()
        self.client.events.append(("download", self.uri, if_generation_match))
        return row["raw"]

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        if self.uri in self.client.objects:
            raise PreconditionFailed("exists")
        generation = self.client.next_generation
        self.client.next_generation += 1
        self.client.objects[self.uri] = {
            "generation": generation, "metageneration": 1, "raw": raw,
        }
        self.client.events.append(("upload", self.uri, generation))

    def delete(self, if_generation_match: int) -> None:
        row = self._row()
        assert if_generation_match == row["generation"]
        if self.client.fail_delete_once:
            self.client.fail_delete_once = False
            raise RuntimeError("synthetic crash before generation delete")
        del self.client.objects[self.uri]
        self.client.events.append(("delete", self.uri, if_generation_match))


class FakeBucket:
    def __init__(self, client: "FakeStorage", name: str):
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> FakeBlob:
        return FakeBlob(self.client, f"gs://{self.name}/{name}", generation)


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, dict[str, Any]] = {}
        self.events: list[tuple[Any, ...]] = []
        self.next_generation = 100
        self.fail_delete_once = False

    def bucket(self, name: str) -> FakeBucket:
        return FakeBucket(self, name)

    def list_blobs(self, bucket: str, prefix: str):
        self.events.append(("inventory", f"gs://{bucket}/{prefix}"))
        rows = []
        for uri, row in self.objects.items():
            if uri.startswith(f"gs://{bucket}/{prefix}"):
                blob = FakeBlob(self, uri, row["generation"])
                blob.reload()
                rows.append(blob)
        return rows

    def put(self, uri: str, raw: bytes, generation: int) -> None:
        self.objects[uri] = {
            "generation": generation, "metageneration": 1, "raw": raw,
        }


def _write(path: Path, value: Any) -> None:
    path.write_bytes(_canonical(value))


def _ledger(out: Path, name: str, files: list[str]) -> None:
    (out / name).write_text("".join(
        f"{_sha((out / file).read_bytes())}  {file}\n" for file in files
    ))


def _synthetic_launch(
    tmp_path: Path,
) -> tuple[Path, dict[str, Any], dict[str, Any], FakeStorage, str]:
    out = tmp_path / "run"
    out.mkdir()
    manifest = _manifest()
    code, image = manifest["code"]["commit_sha"], manifest["image"]["uri"]
    build = _build(build_id=manifest["build"]["id"], code=code, image=image)
    before, after = _job(generation=10, code=code, image=image), _job(
        generation=11, code=code, image=image,
    )
    values = {
        "build-metadata.json": build,
        "job-before.json": before,
        "job-after.json": after,
        "job-executions-before.json": [_terminal_row()],
        "job-executions-after.json": [_terminal_row()],
        "schedulers-before.json": [],
        "schedulers-after.json": [],
        "prefix-before.json": finish._absence_receipt(
            kind="result-prefix", checked_at="2026-08-20T19:00:00+00:00",
        ),
        "prefix-after.json": finish._absence_receipt(
            kind="result-prefix", checked_at="2026-08-20T19:01:00+00:00",
        ),
        "lease-before.json": finish._absence_receipt(
            kind="historical-outcome-lease",
            checked_at="2026-08-20T19:00:00+00:00",
        ),
        "lease-after.json": finish._absence_receipt(
            kind="historical-outcome-lease",
            checked_at="2026-08-20T19:01:00+00:00",
        ),
        "manifest.json": manifest,
    }
    for name, value in values.items():
        _write(out / name, value)
    fake = FakeStorage()
    manifest_raw = _canonical(manifest)
    fake.put(finish.MANIFEST_URI, manifest_raw, 50)
    manifest_receipt = {
        "version": "a2a-production-law-dependence-manifest-receipt-v1",
        "manifest_sha256": _sha(manifest_raw),
        "object": {
            "uri": finish.MANIFEST_URI, "generation": "50",
            "metageneration": "1", "bytes": len(manifest_raw),
            "sha256": _sha(manifest_raw), "create_only": True,
        },
    }
    _write(out / "manifest-object.json", manifest_receipt)
    _ledger(out, "prepared.sha256", sorted(finish.PREPARED_FILES))
    lease = {
        "version": "historical-outcome-active-v1",
        "run_id": finish.RUN_ID,
        "job": finish.JOB,
        "code_sha": code,
        "image": image,
        "acquired_at": "2026-08-20T19:30:00+00:00",
    }
    lease_raw = _canonical(lease)
    fake.put(finish.LEASE_URI, lease_raw, 51)
    lease_receipt = {
        "lease": lease,
        "object": {
            "uri": finish.LEASE_URI, "generation": "51",
            "sha256": _sha(lease_raw), "bytes": len(lease_raw),
            "create_only": True,
        },
    }
    _write(out / "lease-receipt.json", lease_receipt)
    finish._publish_launch_intent(out, client=fake)
    for suffix in ("launch", "launch-final"):
        _write(out / f"job-{suffix}.json", after)
        _write(out / f"job-executions-{suffix}.json", [_terminal_row()])
        _write(out / f"schedulers-{suffix}.json", [])
        _write(out / f"prefix-{suffix}.json", finish._absence_receipt(
            kind="result-prefix", checked_at="2026-08-20T19:40:00+00:00",
        ))
    execution_name = finish.JOB + "-abc12"
    (out / "executions.txt").write_text(
        f"{finish.JOB} {execution_name} {finish.RESULT_URI}\n"
    )
    _ledger(out, "launch.sha256", sorted(finish.LAUNCH_FILES))
    return out, manifest, _result(manifest), fake, execution_name


def test_finish_is_body_blind_until_terminal_and_is_locally_idempotent(
    tmp_path: Path,
) -> None:
    out, manifest, result, fake, execution_name = _synthetic_launch(tmp_path)
    result_raw = _canonical(result)
    fake.put(finish.RESULT_URI, result_raw, 52)

    def load_execution(name: str) -> dict[str, Any]:
        fake.events.append(("execution", name))
        return _execution(manifest, name)

    value = finish.finish(
        out=out, execution_loader=load_execution, client=fake,
    )
    assert value["report"]["disposition"] == result["disposition"]
    result_download = fake.events.index(("download", finish.RESULT_URI, 52))
    execution_gate = fake.events.index(("execution", execution_name))
    inventory_gate = next(
        index for index, event in enumerate(fake.events)
        if event[0] == "inventory"
    )
    assert execution_gate < inventory_gate < result_download
    assert (out / "finish.sha256").is_file()

    fake.events.clear()
    second = finish.finish(
        out=out,
        execution_loader=lambda name: (_ for _ in ()).throw(
            AssertionError("completed finish called cloud execution loader")
        ),
        client=fake,
    )
    assert second["already_complete"] is True
    assert fake.events == []


def test_finish_rejects_nonterminal_and_extra_prefix_before_body_read(
    tmp_path: Path,
) -> None:
    out, manifest, result, fake, execution_name = _synthetic_launch(tmp_path)
    fake.put(finish.RESULT_URI, _canonical(result), 52)
    nonterminal = _execution(manifest, execution_name)
    nonterminal["status"]["conditions"] = []
    fake.events.clear()
    with pytest.raises(RuntimeError, match="strict terminal success"):
        finish.finish(
            out=out, execution_loader=lambda name: nonterminal, client=fake,
        )
    assert not any(event[0] == "inventory" for event in fake.events)
    assert not any(
        event[0] == "download" and event[1] == finish.RESULT_URI
        for event in fake.events
    )

    other = tmp_path / "extra-prefix"
    other.mkdir()
    out, manifest, result, fake, execution_name = _synthetic_launch(other)
    fake.put(finish.RESULT_URI, _canonical(result), 52)
    fake.put(finish.RESULT_PREFIX + "/unexpected.json", b"{}\n", 53)
    with pytest.raises(RuntimeError, match="prefix inventory"):
        finish.finish(
            out=out,
            execution_loader=lambda name: _execution(manifest, name),
            client=fake,
        )
    assert not any(
        event[0] == "download" and event[1] == finish.RESULT_URI
        for event in fake.events
    )


def test_release_intent_resumes_after_crash_and_never_deletes_successor(
    tmp_path: Path,
) -> None:
    out, manifest, result, fake, execution_name = _synthetic_launch(tmp_path)
    fake.put(finish.RESULT_URI, _canonical(result), 52)
    finish.finish(
        out=out, execution_loader=lambda name: _execution(manifest, name),
        client=fake,
    )
    fake.fail_delete_once = True
    with pytest.raises(RuntimeError, match="synthetic crash"):
        finish.close_lease(out=out, client=fake)
    assert finish.RELEASE_INTENT_URI in fake.objects
    assert finish.LEASE_URI in fake.objects

    closed = finish.close_lease(out=out, client=fake)
    assert closed["active_lease_deleted_in_this_call"] is True
    assert finish.LEASE_URI not in fake.objects
    successor = _canonical({"run_id": "other-run"})
    fake.put(finish.LEASE_URI, successor, 99)
    fake.events.clear()
    again = finish.close_lease(out=out, client=fake)
    assert again["active_lease_deleted_in_this_call"] is False
    assert fake.objects[finish.LEASE_URI]["generation"] == 99
    assert fake.events == []


def test_partial_lease_receipt_recovers_only_exact_live_identity(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    manifest_path = tmp_path / "manifest.json"
    _write(manifest_path, manifest)
    receipt_path = tmp_path / "lease-receipt.json"
    partial = b'{"lease":'
    receipt_path.write_bytes(partial)
    lease = {
        "version": "historical-outcome-active-v1",
        "run_id": finish.RUN_ID,
        "job": finish.JOB,
        "code_sha": manifest["code"]["commit_sha"],
        "image": manifest["image"]["uri"],
        "acquired_at": "2026-08-20T19:30:00+00:00",
    }
    fake = FakeStorage()
    fake.put(finish.LEASE_URI, _canonical(lease), 51)
    recovered = finish._recover_live_lease(
        manifest_path=manifest_path, receipt_path=receipt_path, client=fake,
    )
    assert recovered["lease"] == lease
    assert receipt_path.with_name("lease-receipt.json.incomplete").read_bytes() == \
        partial
    assert json.loads(receipt_path.read_bytes()) == recovered

    foreign_path = tmp_path / "foreign-receipt.json"
    foreign_path.write_bytes(partial)
    fake.put(finish.LEASE_URI, _canonical({**lease, "run_id": "foreign"}), 52)
    with pytest.raises(RuntimeError, match="lease identity"):
        finish._recover_live_lease(
            manifest_path=manifest_path, receipt_path=foreign_path,
            client=fake,
        )
    assert foreign_path.read_bytes() == partial


def test_terminal_failure_has_crash_safe_no_retry_closure(
    tmp_path: Path,
) -> None:
    out, manifest, _result_value, fake, execution_name = _synthetic_launch(
        tmp_path,
    )
    failed = _execution(manifest, execution_name)
    failed["status"]["conditions"][0]["status"] = "False"
    failed["status"].pop("succeededCount")
    failed["status"]["failedCount"] = 1
    _write(out / "failed-execution.json", failed)

    fake.fail_delete_once = True
    with pytest.raises(RuntimeError, match="synthetic crash"):
        finish.close_failed_execution(out=out, client=fake)
    assert finish.RELEASE_INTENT_URI in fake.objects
    assert finish.LEASE_URI in fake.objects
    assert not (out / "failure-closure.sha256").exists()

    closed = finish.close_failed_execution(out=out, client=fake)
    assert closed["disposition"] == "closed-terminal-failed-no-retry"
    assert closed["possible_historical_outcome_access"] is True
    assert finish.LEASE_URI not in fake.objects
    assert any(event[0] == "inventory" for event in fake.events)
    assert not any(
        event[0] == "download" and event[1] == finish.RESULT_URI
        for event in fake.events
    )
    assert closed["intent"]["result_prefix_inventory"] == []
    assert closed["intent"]["result_body_read"] is False

    fake.events.clear()
    fake.put(finish.LEASE_URI, _canonical({"run_id": "successor"}), 99)
    again = finish.close_failed_execution(out=out, client=fake)
    assert again == closed
    assert fake.objects[finish.LEASE_URI]["generation"] == 99
    assert fake.events == []


def test_launcher_watcher_and_chain_status_keep_required_order_and_scope() -> None:
    launcher = (ROOT / (
        "scripts/cloud_a2a_production_law_dependence_remeasurement.sh"
    )).read_text()
    watcher = (ROOT / (
        "scripts/watch_a2a_production_law_dependence_queue.sh"
    )).read_text()
    status = (ROOT / "scripts/chain_status.sh").read_text()
    prepare = launcher.index("validate-prepare-inputs")
    update = launcher.index('gcloud run jobs update "$JOB"')
    launch = launcher.index("  launch)")
    intent = launcher.index("publish-launch-intent", launch)
    execute = launcher.index('gcloud run jobs execute "$JOB"', launch)
    assert prepare < update < launch < intent < execute
    assert "validate-smoke-staging" in launcher
    assert "gcloud run jobs deploy" not in launcher
    assert "gcloud run jobs create" not in launcher
    assert "gcloud run jobs delete" not in launcher
    assert "--max-retries 0" in launcher
    assert "--tasks 1 --parallelism 1 --cpu 8 --memory 32Gi" in launcher
    assert watcher.index("verify-pushed-manifest") < watcher.index(
        '"$LEASE_TOOL" acquire'
    ) < watcher.index('bash "$LAUNCHER" launch')
    assert "storage cp" not in watcher
    assert "jobs cancel" not in watcher
    assert "close-failed-execution" in watcher
    assert "A2a realized law" in status
