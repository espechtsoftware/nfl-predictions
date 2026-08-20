from __future__ import annotations

import copy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
from typing import Any

from google.api_core.exceptions import NotFound
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = str(ROOT / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import finish_b1_corpus_tail_model as finish  # noqa: E402


def _canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _job(*, generation: int, code: str, image: str) -> dict[str, Any]:
    contract = finish._static_job_contract(code_sha=code, image=image)
    return {
        "metadata": {
            "name": finish.JOB, "uid": finish.JOB_UID,
            "generation": generation,
        },
        "spec": {"template": {"spec": {
            "taskCount": 1, "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": image, "command": contract["command"],
                    "args": contract["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["env"].items()
                    ],
                    "resources": {"limits": contract["resources"]},
                }],
                "volumes": [], "maxRetries": 0,
                "timeoutSeconds": finish.TIMEOUT_SECONDS,
                "serviceAccountName": finish.SERVICE_ACCOUNT,
            }},
        }}},
    }


def _build(*, build_id: str, code: str, image: str) -> dict[str, Any]:
    tag = finish._image_tag(code)
    source = {"url": finish.GIT_SOURCE_URL, "revision": code}
    return {
        "id": build_id, "status": "SUCCESS",
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
        "substitutions": {"_IMAGE": tag, "COMMIT_SHA": code},
        "steps": finish._expected_cloud_build_steps(tag),
        "results": {"images": [{
            "name": tag, "digest": image.rsplit("@", 1)[1],
        }]},
        "images": [tag], "artifacts": {"images": [tag]},
        "timeout": "10800s", "serviceAccount": finish.BUILD_SERVICE_ACCOUNT,
        "logsBucket": finish.BUILD_LOGS_BUCKET,
    }


def _small_manifest() -> dict[str, Any]:
    code = "a" * 40
    image = finish.IMAGE_REPOSITORY + "@sha256:" + "b" * 64
    job = _job(generation=12, code=code, image=image)
    return {
        "code": {"commit_sha": code}, "image": {"uri": image},
        "job": {
            "name": finish.JOB, "uid": finish.JOB_UID,
            "generation": "12", "spec_sha256": finish._job_spec_sha256(job),
        },
    }


def _lease(manifest: dict[str, Any]) -> dict[str, Any]:
    body = {
        "version": "historical-outcome-active-v1", "run_id": finish.RUN_ID,
        "job": finish.JOB, "code_sha": manifest["code"]["commit_sha"],
        "image": manifest["image"]["uri"],
        "acquired_at": "2026-08-20T20:00:00+00:00",
    }
    raw = _canonical(body)
    return {
        "lease": body,
        "object": {
            "uri": finish.LEASE_URI, "generation": "91",
            "sha256": sha256(raw).hexdigest(), "bytes": len(raw),
            "create_only": True,
        },
    }


def _attempt(lease: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "b1-corpus-tail-historical-attempt-v1",
        "run_id": finish.RUN_ID, "protocol_sha256": finish.PROTOCOL_SHA256,
        "started_at": "2026-08-20T20:01:00+00:00", "lease": lease,
        "b1_protocol_sha256": finish.runner.B1_PROTOCOL_SHA256,
        "b1_report_sha256": finish.runner.B1_REPORT_SHA256,
        "b1_runner_sha256": finish.runner.B1_RUNNER_SHA256,
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False, "production_licensed": False,
    }


def _metric() -> dict[str, Any]:
    return {
        "rows": finish.runner.EXPECTED_DEDUP_ROWS,
        "slates": finish.runner.EXPECTED_SLATES,
        "prevalence_ge200": 0.10, "prevalence_ge210": 0.04,
        "average_precision_ge200": 0.30,
        "p_line_average_precision_ge200": 0.20,
        "average_precision_ge210": 0.12,
        "p_line_average_precision_ge210": 0.08,
        "brier_ge200": 0.07, "fold_prevalence_brier_ge200": 0.09,
        "spearman_tail_score_vs_actual": 0.20,
        "mean_predicted_ge200": 0.11,
    }


def _book(mean: float, counts: tuple[int, int, int, int, int, int, int]) -> dict[str, Any]:
    return {
        "slates": 54, "mean_weekly_max": mean,
        "median_weekly_max": mean - 1, "maximum": mean + 30,
        "threshold_counts": dict(zip(
            ("187", "194", "200", "210", "220", "230", "240"), counts,
            strict=True,
        )),
    }


def _redundancy(candidate_budget: int) -> dict[str, Any]:
    return {
        "candidate_budget": candidate_budget, "entry_budget": 80,
        "max_shared_players_first_pass": 7,
        "overlap_rejections_before_fill": 2, "deterministic_backfills": 0,
    }


def _report(
    manifest: dict[str, Any], lease: dict[str, Any],
    attempt_meta: dict[str, Any],
) -> dict[str, Any]:
    slates = []
    for index in range(54):
        season = 2023 + index // 18
        week = index % 18 + 1
        budget = 200 + index
        slates.append({
            "season": season, "week": week,
            "candidate_budget_control": budget,
            "candidate_budget_challenger": budget,
            "entries_control": 80, "entries_challenger": 80,
            "challenger_control_overlap": 42,
            "challenger_redundancy": _redundancy(budget),
            "naive_redundancy": _redundancy(budget),
        })
    books = {
        "control": _book(190.0, (40, 30, 20, 10, 5, 2, 1)),
        "challenger": _book(195.0, (41, 30, 21, 10, 5, 2, 1)),
        "naive_p_line": _book(188.0, (38, 28, 18, 9, 4, 2, 1)),
    }
    selection = {
        "equal_candidate_and_entry_budgets": True,
        "mean_weekly_max_improves": True,
        "ge200_count_improves": True,
        "ge210_count_noninferior": True,
        "ge194_count_protected": True,
    }
    prediction = {
        "ge200_pr_beats_prevalence": True,
        "ge200_pr_beats_p_line": True,
        "ge210_pr_beats_prevalence": True,
        "positive_brier_skill_vs_fold_prevalence": True,
    }
    return {
        "version": "b1-corpus-tail-historical-evaluation-v1",
        "population": {
            "deduplicated_rosters": finish.runner.EXPECTED_DEDUP_ROWS,
            "slates": finish.runner.EXPECTED_SLATES,
            "seasons": [2023, 2024, 2025],
            "canonical_candidate_rows": 13_770,
        },
        "model": {
            "version": finish.science.MODEL_VERSION,
            "feature_columns": list(finish.science.FEATURE_COLUMNS),
            "target": "actual_score_ge_200", "winner_fields_used": [],
            "hyperparameter_grid": [],
        },
        "loso": _metric(), "walk_forward_companion": _metric(),
        "exact80": {"books": books, "slates": slates, "selection_gates": selection},
        "historical_gates": {**prediction, **selection},
        "historical_pass": True,
        "licenses": {
            "write_2026_shadow_artifact": True, "run_2026_shadow": True,
            "production": False, "historical_retune": False,
        },
        "uses_winner_target_or_feature": False, "uses_realized_outcomes": True,
        "source_lock": {
            "executed_at": "2026-08-20T20:03:00+00:00",
            "protocol_sha256": finish.PROTOCOL_SHA256,
            "candidate_frame_sha256": "c" * 64,
            "player_frame_sha256": "d" * 64,
            "b1_protocol_sha256": finish.runner.B1_PROTOCOL_SHA256,
            "b1_report_sha256": finish.runner.B1_REPORT_SHA256,
            "b1_runner_sha256": finish.runner.B1_RUNNER_SHA256,
            "historical_lease": lease["object"],
            "historical_attempt": {**attempt_meta, "create_only": True},
            "candidate_query": {
                "job_id": "candidate-query", "location": "US",
                "created": "2026-08-20T20:01:01+00:00",
                "started": "2026-08-20T20:01:02+00:00",
                "ended": "2026-08-20T20:02:00+00:00",
                "total_bytes_processed": 123,
                "query_sha256": sha256(finish.runner._candidate_sql(
                    outcomes=True, one_slate=False,
                ).encode()).hexdigest(),
            },
            "player_query": {
                "job_id": "player-query", "location": "US",
                "created": "2026-08-20T20:01:01+00:00",
                "started": "2026-08-20T20:01:02+00:00",
                "ended": "2026-08-20T20:01:30+00:00",
                "total_bytes_processed": 45,
                "query_sha256": sha256(finish.runner._player_sql(
                    one_slate=False,
                ).encode()).hexdigest(),
            },
            "realized_outcome_columns_read": ["actual_score"],
        },
        "model_artifact_sha256": "e" * 64,
        "model_file_sha256": "f" * 64,
    }


def _execution(
    manifest: dict[str, Any], *, intent_generation: str,
    status: str = "True", name: str | None = None,
) -> dict[str, Any]:
    name = name or finish.JOB + "-abc12"
    contract = finish._execution_contract(
        manifest=manifest, intent_generation=intent_generation,
    )
    succeeded = 1 if status == "True" else 0
    failed = 0 if status == "True" else 1
    return {
        "metadata": {
            "name": name, "generation": 1,
            "labels": {
                "run.googleapis.com/job": finish.JOB,
                "run.googleapis.com/jobUid": finish.JOB_UID,
                "run.googleapis.com/jobGeneration": manifest["job"]["generation"],
            },
        },
        "status": {
            "observedGeneration": 1,
            "conditions": [{"type": "Completed", "status": status}],
            "succeededCount": succeeded, "failedCount": failed,
            "completionTime": "2026-08-20T22:00:00Z",
        },
        "spec": {
            "taskCount": 1, "parallelism": 1,
            "template": {"spec": {
                "containers": [{
                    "image": contract["image"], "command": contract["command"],
                    "args": contract["args"],
                    "env": [
                        {"name": key, "value": value}
                        for key, value in contract["env"].items()
                    ],
                    "resources": {"limits": contract["resources"]},
                }],
                "volumes": [], "maxRetries": 0,
                "timeoutSeconds": finish.TIMEOUT_SECONDS,
                "serviceAccountName": finish.SERVICE_ACCOUNT,
            }},
        },
    }


def test_strict_json_rejects_duplicates_and_nonfinite() -> None:
    with pytest.raises(RuntimeError, match="strict JSON"):
        finish._strict_json_bytes(b'{"a":1,"a":2}', label="fixture")
    with pytest.raises(RuntimeError, match="strict JSON"):
        finish._strict_json_bytes(b'{"a":NaN}', label="fixture")


def test_build_requires_direct_git_successful_tests_and_exact_digest() -> None:
    code = "a" * 40
    image = finish.IMAGE_REPOSITORY + "@sha256:" + "b" * 64
    build = _build(build_id="build-12345678", code=code, image=image)
    assert finish._validate_build_metadata(
        build, build_id="build-12345678", code_sha=code, image=image,
    ) == finish._image_tag(code)
    poisoned = copy.deepcopy(build)
    poisoned["steps"][0]["status"] = "FAILURE"
    with pytest.raises(RuntimeError, match="test/image gate"):
        finish._validate_build_metadata(
            poisoned, build_id="build-12345678", code_sha=code, image=image,
        )


def test_reused_job_is_update_only_inert_and_zero_retry() -> None:
    code = "a" * 40
    image = finish.IMAGE_REPOSITORY + "@sha256:" + "b" * 64
    job = _job(generation=12, code=code, image=image)
    assert finish._validate_job_spec(job, code_sha=code, image=image)[1] == "12"
    inherited = copy.deepcopy(job)
    inherited["spec"]["template"]["spec"]["template"]["spec"]["maxRetries"] = 1
    with pytest.raises(RuntimeError, match="executable contract"):
        finish._validate_job_spec(inherited, code_sha=code, image=image)
    scheduled = [{"httpTarget": {"uri": "https://run.googleapis.com/v2/projects/x/locations/y/jobs/" + finish.JOB + ":run"}}]
    with pytest.raises(RuntimeError, match="scheduler"):
        finish._validate_unscheduled(scheduled)


def test_a2a_terminal_must_be_exact_no_retry_closure_in_source(tmp_path: Path) -> None:
    out = tmp_path / finish.A2A_OUT.relative_to(ROOT)
    out.mkdir(parents=True)
    body = {
        "version": "a2a-production-law-dependence-lease-release-v1",
        "run_id": finish.A2A_RUN_ID,
        "intent": {"disposition": "a2a-law-shape-passes"},
        "active_lease_generation": "88",
        "active_lease_exact_generation_closed": True,
        "release_complete": True, "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    raw = _canonical(body)
    (out / "lease-release.json").write_bytes(raw)
    (out / "lease-release.sha256").write_text(
        f"{sha256(raw).hexdigest()}  lease-release.json\n", encoding="utf-8",
    )
    observed = finish._a2a_terminal(
        root=tmp_path, code_sha="a" * 40,
        git_loader=lambda root, code, relative: (root / relative).read_bytes(),
    )
    assert observed["terminal_kind"] == "success"
    body["historical_retry_licensed"] = True
    (out / "lease-release.json").write_bytes(_canonical(body))
    with pytest.raises(RuntimeError, match="terminal closure"):
        finish._a2a_terminal(root=tmp_path)


def test_smoke_staging_is_exact_committed_inventory(tmp_path: Path) -> None:
    out = tmp_path / "reports/b1-corpus-tail-runs" / finish.RUN_ID
    out.mkdir(parents=True)
    source = ROOT / "reports/b1-corpus-tail-runs" / finish.RUN_ID
    for name in finish.SMOKE_FILES:
        shutil.copyfile(source / name, out / name)
    finish._validate_smoke_staging(
        out, code_sha="a" * 40, root=tmp_path,
        git_loader=lambda root, code, relative: (root / relative).read_bytes(),
    )
    (out / "extra.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="inventory"):
        finish._validate_smoke_staging(
            out, code_sha="a" * 40, root=tmp_path,
            git_loader=lambda root, code, relative: (root / relative).read_bytes(),
        )


def test_independent_report_replay_rejects_forged_gate_and_license() -> None:
    manifest = _small_manifest()
    lease = _lease(manifest)
    attempt = _attempt(lease)
    attempt_raw = _canonical(attempt)
    attempt_meta = {
        "uri": finish.ATTEMPT_URI, "generation": "92", "metageneration": "1",
        "bytes": len(attempt_raw), "sha256": sha256(attempt_raw).hexdigest(),
    }
    report = _report(manifest, lease, attempt_meta)
    assert finish._validate_report(
        report, manifest=manifest, lease_receipt=lease, attempt=attempt,
        attempt_metadata=attempt_meta,
    )["historical_pass"] is True
    forged = copy.deepcopy(report)
    forged["historical_gates"]["ge200_pr_beats_p_line"] = False
    with pytest.raises(RuntimeError, match="independent replay"):
        finish._validate_report(
            forged, manifest=manifest, lease_receipt=lease, attempt=attempt,
            attempt_metadata=attempt_meta,
        )
    forged = copy.deepcopy(report)
    forged["licenses"]["production"] = True
    with pytest.raises(RuntimeError, match="license truth table"):
        finish._validate_report(
            forged, manifest=manifest, lease_receipt=lease, attempt=attempt,
            attempt_metadata=attempt_meta,
        )


def test_portable_model_is_hash_replayed_and_never_production_licensed() -> None:
    manifest = _small_manifest()
    lease = _lease(manifest)
    attempt_raw = _canonical(_attempt(lease))
    attempt_meta = {
        "uri": finish.ATTEMPT_URI, "generation": "92", "metageneration": "1",
        "bytes": len(attempt_raw), "sha256": sha256(attempt_raw).hexdigest(),
    }
    report = _report(manifest, lease, attempt_meta)
    width = len(finish.science.FEATURE_COLUMNS)
    model = {
        "version": finish.science.MODEL_VERSION,
        "target": "actual_score_ge_200", "target_threshold": 200.0,
        "feature_columns": list(finish.science.FEATURE_COLUMNS),
        "impute_medians": [0.0] * width, "standardize_means": [0.0] * width,
        "standardize_scales": [1.0] * width, "coefficients": [0.1] * width,
        "intercept": -1.0, "training_rows": finish.runner.EXPECTED_DEDUP_ROWS,
        "training_slates": finish.runner.EXPECTED_SLATES,
        "training_seasons": [2023, 2024, 2025],
        "training_prevalence_ge200": 0.1,
        "fixed_estimator": {
            "type": "sklearn.linear_model.LogisticRegression", "C": 1.0,
            "solver": "lbfgs", "penalty": "l2", "class_weight": None,
            "max_iter": 2000,
            "sample_weight": "each season-week has equal total weight",
        },
        "winner_fields_used": [], "production_licensed": False,
        "prospective_shadow_only": True, "historical_gate_passed": True,
        "historical_gate_scope": "LOSO-2023-2025-B1-union",
        "protocol_sha256": finish.PROTOCOL_SHA256,
        "historical_run_id": finish.RUN_ID,
        "historical_source_rows": finish.runner.EXPECTED_SOURCE_ROWS,
        "historical_deduplicated_rosters": finish.runner.EXPECTED_DEDUP_ROWS,
    }
    model["artifact_sha256"] = finish.science.artifact_sha256(model)
    report["model_artifact_sha256"] = model["artifact_sha256"]
    assert finish._validate_model(model, report=report)["production_licensed"] is False
    model["coefficients"][0] = 0.2
    with pytest.raises(RuntimeError, match="artifact identity"):
        finish._validate_model(model, report=report)


def test_execution_contract_is_one_task_and_rejects_retry() -> None:
    manifest = _small_manifest()
    execution = _execution(manifest, intent_generation="93")
    finish._validate_execution_terminal(
        execution, execution=finish.JOB + "-abc12", manifest=manifest,
        intent_generation="93", completed_status="True",
    )
    retried = copy.deepcopy(execution)
    retried["status"]["retriedCount"] = 1
    with pytest.raises(RuntimeError, match="strict terminal"):
        finish._validate_execution_terminal(
            retried, execution=finish.JOB + "-abc12", manifest=manifest,
            intent_generation="93", completed_status="True",
        )


def test_finish_does_not_inventory_or_open_body_before_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _small_manifest()
    lease = _lease(manifest)
    monkeypatch.setattr(
        finish, "_validate_launch_local",
        lambda out: (manifest, {"object": {}}, lease, finish.JOB + "-abc12", "93"),
    )
    monkeypatch.setattr(finish, "_load_live_manifest", lambda *args, **kwargs: {})
    monkeypatch.setattr(finish, "_load_live_lease", lambda *args, **kwargs: (None, lease))
    monkeypatch.setattr(finish, "_load_live_launch_intent", lambda *args, **kwargs: ({}, {}))
    opened = {"inventory": False}

    def inventory(client: Any) -> list[dict[str, Any]]:
        opened["inventory"] = True
        return []

    monkeypatch.setattr(finish, "_prefix_inventory", inventory)
    running = _execution(manifest, intent_generation="93")
    running["status"]["conditions"] = []
    with pytest.raises(RuntimeError, match="strict terminal"):
        finish.finish(
            out=Path("unused"), execution_loader=lambda name: running,
            client=object(),
        )
    assert opened["inventory"] is False


def test_generation_delete_never_selects_a_successor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = _small_manifest()
    lease = _lease(manifest)
    monkeypatch.setattr(
        finish, "_load_live_lease",
        lambda client, receipt, manifest: (_ for _ in ()).throw(NotFound("gone")),
    )
    assert finish._delete_intended_lease(
        object(), lease=lease, manifest=manifest,
    ) is False


def test_launcher_watcher_encode_reuse_only_serial_order_and_no_retry() -> None:
    launcher = (ROOT / "scripts/cloud_b1_corpus_tail_model.sh").read_text()
    watcher = (ROOT / "scripts/watch_b1_corpus_tail_queue.sh").read_text()
    assert "gcloud run jobs update" in launcher
    assert "gcloud run jobs deploy" not in launcher
    assert "gcloud run jobs delete" not in launcher
    assert "--tasks 1" in launcher and "--max-retries 0" in launcher
    assert launcher.index("capture-empty-prefix --output \"$OUT/prefix-launch-final.json\"") \
        < launcher.index("gcloud run jobs execute")
    assert "execute-frozen,--launch-intent-generation" in launcher
    assert watcher.index("validate-a2a-terminal --code-sha") \
        < watcher.index("bash \"$LAUNCHER\" prepare")
    assert watcher.index("conditions") < watcher.index("\"$FINISHER\" finish")
    assert "launch is ambiguous; no retry" in watcher
    assert "deploy_jobs.sh" not in launcher + watcher
    assert "B1_CORPUS_TAIL_OUTCOME" in watcher
