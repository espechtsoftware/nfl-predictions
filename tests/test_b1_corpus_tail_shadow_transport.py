from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "b1_corpus_tail_shadow_transport",
    ROOT / "scripts/run_b1_corpus_tail_shadow_transport.py",
)
assert SPEC and SPEC.loader
shadow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(shadow)


def _object(uri: str, token: str = "a") -> dict[str, Any]:
    return {
        "uri": uri,
        "generation": "11",
        "metageneration": "1",
        "bytes": 101,
        "sha256": token * 64,
    }


def _license() -> dict[str, Any]:
    return {
        "version": "b1-corpus-tail-shadow-historical-license-v1",
        "transport_id": shadow.TRANSPORT_ID,
        "historical_run_id": shadow.RUN_ID,
        "protocol_sha256": shadow.historical.PROTOCOL_SHA256,
        "evidence_commit": "a" * 40,
        "remote_ref": "origin/main",
        "historical_code_commit": "b" * 40,
        "historical_image": shadow.IMAGE_REPOSITORY + "@sha256:" + "c" * 64,
        "historical_report_object": _object(shadow.historical.REPORT_URI, "d"),
        "historical_model_object": _object(shadow.historical.MODEL_URI, "e"),
        "model_artifact_sha256": "f" * 64,
        "historical_gate_passed": True,
        "shadow_licensed": True,
        "historical_retry_licensed": False,
        "historical_lease_generation_closed": "17",
        "historical_lease_exact_generation_closed": True,
        "prospective_season": 2026,
        "prospective_weeks": list(range(1, 7)),
        "shadow_enabled_default": False,
        "production_licensed": False,
    }


def _job(
    *,
    generation: int,
    name: str,
    uid: str,
    code: str,
    image: str,
    inert: bool,
) -> dict[str, Any]:
    container: dict[str, Any] = {
        "image": image,
        "command": ["python"],
        "args": [shadow.SCRIPT_PATH, "--help"],
        "env": [
            {"name": "ANALYSIS_IMAGE", "value": image},
            {"name": "CODE_SHA", "value": code},
            {"name": "CORPUS_TAIL_SHADOW_ENABLED", "value": "0"},
        ],
        "resources": {"limits": {"cpu": shadow.CPU, "memory": shadow.MEMORY}},
    }
    task = {
        "containers": [container],
        "volumes": [],
        "maxRetries": 0,
        "timeoutSeconds": shadow.TIMEOUT_SECONDS,
        "serviceAccountName": shadow.SERVICE_ACCOUNT,
    }
    if not inert:
        task["containers"][0]["args"] = ["old-command"]
    return {
        "metadata": {"name": name, "uid": uid, "generation": generation},
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": task},
            "volumes": [],
        }}},
    }


def _build(*, build_id: str, code: str, image: str) -> dict[str, Any]:
    source = {"url": shadow.historical.GIT_SOURCE_URL, "revision": code}
    tag = shadow.IMAGE_REPOSITORY + ":b1-shadow-" + code[:7]
    return {
        "id": build_id,
        "status": "SUCCESS",
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
        "substitutions": {"_IMAGE": tag},
        "steps": [
            {"id": "full-test-suite", "status": "SUCCESS"},
            {"id": "build-image", "status": "SUCCESS"},
            {"id": "smoke-atlas-mvp-runner", "status": "SUCCESS"},
        ],
        "results": {"images": [{
            "name": tag, "digest": image.rsplit("@", 1)[1],
        }]},
        "timeout": "10800s",
        "serviceAccount": shadow.historical.BUILD_SERVICE_ACCOUNT,
        "logsBucket": shadow.historical.BUILD_LOGS_BUCKET,
    }


def _deployment() -> dict[str, Any]:
    license_doc = _license()
    code = "1" * 40
    image = shadow.IMAGE_REPOSITORY + "@sha256:" + "2" * 64
    job_name = "legacy-idle-shadow-lane"
    job_uid = "uid-123"
    return shadow.build_deployment_manifest(
        license_document=license_doc,
        license_sha256=sha256(shadow._canonical_json(license_doc)).hexdigest(),
        code_sha=code,
        image=image,
        build_id="build-12345678",
        build_metadata=_build(build_id="build-12345678", code=code, image=image),
        job_name=job_name,
        job_uid=job_uid,
        job_before=_job(
            generation=7, name=job_name, uid=job_uid, code=code,
            image=image, inert=False,
        ),
        job_after=_job(
            generation=8, name=job_name, uid=job_uid, code=code,
            image=image, inert=True,
        ),
        executions_before=[],
        executions_after=[],
        schedulers_before=[],
        schedulers_after=[],
    )


def _receipt(*, week: int = 1) -> dict[str, Any]:
    def roster(prefix: str, rank: int) -> str:
        return ",".join(f"{prefix}{rank:02d}-{slot}" for slot in range(9))

    return {
        "version": "b1-corpus-tail-shadow-receipt-v1",
        "policy_version": shadow.science.POLICY_VERSION,
        "season": 2026,
        "week": week,
        "model_artifact_sha256": "f" * 64,
        "source_identity": {
            "snapshot_id": f"2026-w{week:02d}",
            "snapshot_at": "2026-09-01T15:00:00+00:00",
            "lock_at": "2026-09-01T17:00:00+00:00",
            "panels": ["canonical"],
            "canonical_panel": "canonical",
            "candidate_query": {"ended": "2026-09-01T14:59:00+00:00"},
            "player_query": {"ended": "2026-09-01T15:00:00+00:00"},
            "realized_outcome_columns_read": [],
        },
        "candidate_budget_control": 255,
        "candidate_budget_challenger": 255,
        "entry_budget": 80,
        "redundancy": {},
        "control_entries": [
            {"rank": rank, "roster_key": roster("c", rank)}
            for rank in range(80)
        ],
        "challenger_entries": [
            {
                "rank": rank,
                "roster_key": roster("t", rank),
                "prelock_tail_score": 0.5,
            }
            for rank in range(80)
        ],
        "uses_realized_outcomes": False,
        "uses_winner_target_or_feature": False,
        "production_licensed": False,
        "prospective_adoption_gate_required": True,
    }


def _execution(
    deployment: dict[str, Any],
    *,
    phase: str,
    week: int | None = None,
    generation: str | None = None,
) -> dict[str, Any]:
    env = dict(deployment["default_environment"])
    if phase == "freeze":
        env["CORPUS_TAIL_SHADOW_ENABLED"] = "1"
    task = {
        "containers": [{
            "image": deployment["code"]["image"],
            "command": ["python"],
            "args": shadow._phase_args(
                phase=phase, week=week, intent_generation=generation
            ),
            "env": [
                {"name": key, "value": value} for key, value in env.items()
            ],
            "resources": {
                "limits": {"cpu": shadow.CPU, "memory": shadow.MEMORY}
            },
        }],
        "volumes": [],
        "maxRetries": 0,
        "timeoutSeconds": shadow.TIMEOUT_SECONDS,
        "serviceAccountName": shadow.SERVICE_ACCOUNT,
    }
    job = deployment["job"]
    return {
        "metadata": {
            "name": job["name"] + "-abc12",
            "generation": 1,
            "labels": {
                "run.googleapis.com/job": job["name"],
                "run.googleapis.com/jobUid": job["uid"],
                "run.googleapis.com/jobGeneration": job["generation"],
            },
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
            "completionTime": "2026-09-01T22:00:00Z",
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": task},
        },
    }


def test_deployment_is_reuse_only_default_off_and_historical_pass_bound() -> None:
    deployment = _deployment()
    assert deployment["default_environment"]["CORPUS_TAIL_SHADOW_ENABLED"] == "0"
    assert deployment["weekly_execution_override"] == {
        "CORPUS_TAIL_SHADOW_ENABLED": "1", "required": True,
    }
    assert deployment["job"]["update_mode"] == "reuse-only-update-existing"
    assert deployment["job"]["max_retries"] == 0
    assert deployment["historical_license"]["historical_gate_passed"] is True
    assert deployment["production_licensed"] is False


@pytest.mark.parametrize("commit_key", ["COMMIT_SHA", "_CODE_SHA"])
def test_build_accepts_omitted_commit_substitution_but_rejects_wrong_declared(
    commit_key: str,
) -> None:
    code = "1" * 40
    image = shadow.IMAGE_REPOSITORY + "@sha256:" + "2" * 64
    build = _build(build_id="build-12345678", code=code, image=image)
    shadow._validate_build(
        build, build_id="build-12345678", code_sha=code, image=image,
    )
    build["substitutions"][commit_key] = "3" * 40
    with pytest.raises(shadow.ShadowTransportError, match="substitutions"):
        shadow._validate_build(
            build, build_id="build-12345678", code_sha=code, image=image,
        )


@pytest.mark.parametrize("mutation", ["missing", "reordered", "extra"])
def test_build_rejects_nonexact_three_step_contract(mutation: str) -> None:
    code = "1" * 40
    image = shadow.IMAGE_REPOSITORY + "@sha256:" + "2" * 64
    build = _build(build_id="build-12345678", code=code, image=image)
    if mutation == "missing":
        build["steps"] = build["steps"][:-1]
    elif mutation == "reordered":
        build["steps"][1], build["steps"][2] = (
            build["steps"][2], build["steps"][1],
        )
    else:
        build["steps"].append({"id": "unexpected", "status": "SUCCESS"})
    with pytest.raises(shadow.ShadowTransportError, match="build"):
        shadow._validate_build(
            build, build_id="build-12345678", code_sha=code, image=image,
        )


def test_deployment_rejects_false_or_unclosed_historical_license() -> None:
    license_doc = _license()
    license_doc["historical_gate_passed"] = False
    with pytest.raises(shadow.ShadowTransportError, match="license boundary"):
        shadow._validate_historical_license_document(license_doc)
    license_doc = _license()
    license_doc["historical_lease_exact_generation_closed"] = False
    with pytest.raises(shadow.ShadowTransportError, match="license boundary"):
        shadow._validate_historical_license_document(license_doc)


def test_week_intent_is_exact_2026_weeks_one_through_six() -> None:
    deployment = _deployment()
    raw = shadow._canonical_json(deployment)
    deployment_object = {
        **_object(shadow.DEPLOYMENT_URI, sha256(raw).hexdigest()[0]),
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
        "create_only": True,
    }
    intent = shadow.build_week_intent(
        deployment=deployment,
        deployment_object=deployment_object,
        week=1,
        lock_at="2026-09-13T17:00:00Z",
        snapshot_id="snapshot-2026-w01",
        panels=["companion", "canonical"],
        canonical_panel="canonical",
    )
    assert intent["season"] == 2026 and intent["week"] == 1
    assert intent["panels"] == ["canonical", "companion"]
    assert intent["outcomes_allowed"] is False
    with pytest.raises(shadow.ShadowTransportError, match="Weeks 1--6"):
        shadow.build_week_intent(
            deployment=deployment,
            deployment_object=deployment_object,
            week=7,
            lock_at="2026-10-25T17:00:00Z",
            snapshot_id="x",
            panels=["canonical"],
            canonical_panel="canonical",
        )
    with pytest.raises(shadow.ShadowTransportError, match="repeat"):
        shadow.build_week_intent(
            deployment=deployment,
            deployment_object=deployment_object,
            week=1,
            lock_at="2026-09-13T17:00:00Z",
            snapshot_id="x",
            panels=["canonical", "canonical"],
            canonical_panel="canonical",
        )


def test_create_once_local_artifact_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "receipt.json"
    digest = shadow._write_create_once(target, {"a": 1})
    assert digest == sha256(target.read_bytes()).hexdigest()
    original = target.read_bytes()
    with pytest.raises(FileExistsError):
        shadow._write_create_once(target, {"a": 1})
    assert target.read_bytes() == original
    assert target.with_suffix(".json.sha256").is_file()


def test_pushed_bundle_requires_byte_identity_and_ancestry(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "t@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    artifact = tmp_path / "artifact.json"
    artifact.write_text('{"ok":true}\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "artifact.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "evidence"], check=True)
    commit = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    shadow._verify_pushed_bundle(
        root=tmp_path, commit=commit, remote_ref="HEAD", paths={artifact}
    )
    artifact.write_text('{"ok":false}\n', encoding="utf-8")
    with pytest.raises(shadow.ShadowTransportError, match="differs"):
        shadow._verify_pushed_bundle(
            root=tmp_path, commit=commit, remote_ref="HEAD", paths={artifact}
        )


def test_shadow_receipt_requires_exact80_equal_budget_and_prelock() -> None:
    deployment = _deployment()
    receipt = _receipt()
    control, challenger = shadow._validate_shadow_receipt(
        receipt, week=1, deployment=deployment
    )
    assert len(control) == len(challenger) == 80
    poisoned = json.loads(json.dumps(receipt))
    poisoned["candidate_budget_challenger"] = 256
    with pytest.raises(shadow.ShadowTransportError, match="boundary"):
        shadow._validate_shadow_receipt(poisoned, week=1, deployment=deployment)
    poisoned = json.loads(json.dumps(receipt))
    poisoned["source_identity"]["snapshot_at"] = poisoned["source_identity"]["lock_at"]
    with pytest.raises(shadow.ShadowTransportError, match="outcome-blind/pre-lock"):
        shadow._validate_shadow_receipt(poisoned, week=1, deployment=deployment)


def test_settlement_query_derives_exact_union_and_rejects_incomplete_labels() -> None:
    receipt = _receipt()
    expected = {
        row["roster_key"] for row in receipt["control_entries"]
    } | {row["roster_key"] for row in receipt["challenger_entries"]}
    rows = []
    for index, key in enumerate(sorted(expected)):
        rows.append({
            "cand_ix": index,
            "players": key.split(","),
            "actual_score": 180.0 + index / 10,
            "labels_complete": True,
        })

    class Result:
        def to_dataframe(self, **kwargs: Any) -> pd.DataFrame:
            return pd.DataFrame(rows)

    class Job:
        job_id = "settled-job"
        ended = datetime(2026, 9, 14, tzinfo=timezone.utc)

        def result(self) -> Result:
            return Result()

    class Client:
        def query(self, *args: Any, **kwargs: Any) -> Job:
            return Job()

    settled = shadow._query_settled_scores(
        Client(), week=1, canonical_panel="canonical",
        expected_rosters=expected, receipt_sha256="a" * 64,
    )
    assert settled["labels_complete"] is True
    assert {row["roster_key"] for row in settled["scores"]} == expected
    rows[0]["labels_complete"] = False
    with pytest.raises(shadow.ShadowTransportError, match="complete"):
        shadow._query_settled_scores(
            Client(), week=1, canonical_panel="canonical",
            expected_rosters=expected, receipt_sha256="a" * 64,
        )


def test_execution_contract_is_strict_no_retry_and_phase_specific() -> None:
    deployment = _deployment()
    execution = _execution(
        deployment, phase="freeze", week=1, generation="19"
    )
    shadow.validate_execution_terminal(
        execution, deployment=deployment, phase="freeze", week=1,
        intent_generation="19",
    )
    execution["status"]["retriedCount"] = 1
    with pytest.raises(shadow.ShadowTransportError, match="strict terminal"):
        shadow.validate_execution_terminal(
            execution, deployment=deployment, phase="freeze", week=1,
            intent_generation="19",
        )


def test_harvest_body_firewall_runs_before_storage_access(tmp_path: Path) -> None:
    deployment = _deployment()
    execution = _execution(
        deployment, phase="freeze", week=1, generation="19"
    )
    execution["status"]["conditions"] = []

    class BombStorage:
        def bucket(self, name: str) -> Any:
            raise AssertionError("result storage opened before strict terminal")

    with pytest.raises(shadow.ShadowTransportError, match="strict terminal"):
        shadow.harvest_phase(
            deployment=deployment,
            execution=execution,
            phase="freeze",
            week=1,
            intent_generation="19",
            out=tmp_path / "harvest",
            storage_client=BombStorage(),
        )


def test_adoption_result_cannot_auto_mutate_production() -> None:
    value = {
        "version": "b1-corpus-tail-six-week-adoption-v1",
        "season": 2026,
        "weeks": list(range(1, 7)),
        "control": {},
        "challenger": {},
        "paired": {},
        "gates": {},
        "prospective_gate_passed": True,
        "production_review_licensed": True,
        "automatic_production_mutation": False,
        "winner_fields_used": [],
    }
    assert shadow._validate_adoption_result(value)[
        "automatic_production_mutation"
    ] is False
    value["automatic_production_mutation"] = True
    with pytest.raises(shadow.ShadowTransportError, match="boundary"):
        shadow._validate_adoption_result(value)


def test_launcher_is_reuse_only_default_off_and_exact_six_week_grade() -> None:
    text = (ROOT / "scripts/cloud_b1_corpus_tail_shadow.sh").read_text()
    assert "gcloud run jobs update" in text
    assert "gcloud run jobs create" not in text
    assert "gcloud run jobs delete" not in text
    assert "deploy_jobs.sh" not in text
    assert "--max-retries 0" in text
    assert "CORPUS_TAIL_SHADOW_ENABLED=0" in text
    assert "--update-env-vars CORPUS_TAIL_SHADOW_ENABLED=1" in text
    assert "for WEEK in 1 2 3 4 5 6" in text
    assert "validate-historical-license" in text
    assert "commit_and_push_before_launch=true" in text


def test_transport_delegates_science_to_frozen_runner() -> None:
    text = (ROOT / "scripts/run_b1_corpus_tail_shadow_transport.py").read_text()
    assert "runner_main(argv)" in text
    assert "runner._materialize_adoption_grades" in text
    assert "science.evaluate_six_week_adoption" in text
    assert "LogisticRegression" not in text
    assert "select_exact80(" not in text
