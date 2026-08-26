#!/usr/bin/env python3
"""Prepare, execute, inspect, and finish the 54-slate R6 full-union freeze."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import os
import sys
import time
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_release_v1 as release
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research.corpus_neo4j_transport import GoogleCloudObjectStore


PRODUCTION_ENABLE_ENV: Final = "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED"
RUNTIME_IMAGE_ENV: Final = "R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE"
COMMANDS: Final = ("prepare", "run-slate", "status", "finish-panel")


class CorpusR6FullUnionPanelFreezeCLIError(RuntimeError):
    """The CLI cannot proceed without weakening its production binding."""


def _add_identity(parser: argparse.ArgumentParser, prefix: str) -> None:
    parser.add_argument(f"--{prefix}-uri", required=True)
    parser.add_argument(f"--{prefix}-generation", required=True)
    parser.add_argument(f"--{prefix}-sha256", required=True)
    parser.add_argument(f"--{prefix}-bytes", required=True, type=int)


def _identity(args: argparse.Namespace, prefix: str) -> dict[str, object]:
    stem = prefix.replace("-", "_")
    return {
        "uri": getattr(args, f"{stem}_uri"),
        "generation": getattr(args, f"{stem}_generation"),
        "sha256": getattr(args, f"{stem}_sha256"),
        "bytes": getattr(args, f"{stem}_bytes"),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--execute", action="store_true")
    _add_identity(prepare, "panel")
    prepare.add_argument("--source-commit-sha", required=True)
    prepare.add_argument("--immutable-image", required=True)
    prepare.add_argument("--output-prefix", required=True)

    run_slate = subparsers.add_parser("run-slate")
    run_slate.add_argument("--execute", action="store_true")
    _add_identity(run_slate, "manifest")
    run_slate.add_argument("--source-ordinal", type=int)
    run_slate.add_argument("--source-offset", type=int, default=0)
    run_slate.add_argument("--expected-source-commit-sha", required=True)
    run_slate.add_argument("--expected-immutable-image", required=True)
    run_slate.add_argument("--expected-project-number", required=True)
    run_slate.add_argument("--expected-region", required=True)

    status = subparsers.add_parser("status")
    _add_identity(status, "manifest")

    finish = subparsers.add_parser("finish-panel")
    finish.add_argument("--execute", action="store_true")
    _add_identity(finish, "manifest")
    finish.add_argument("--expected-source-commit-sha", required=True)
    finish.add_argument("--expected-immutable-image", required=True)
    return parser


def _require_production_gate(args: argparse.Namespace) -> None:
    if args.command == "status":
        return
    if args.execute is not True:
        raise CorpusR6FullUnionPanelFreezeCLIError("--execute is required")
    if os.environ.get(PRODUCTION_ENABLE_ENV) != "1":
        raise CorpusR6FullUnionPanelFreezeCLIError(
            f"production publication requires {PRODUCTION_ENABLE_ENV}=1"
        )


def _clean_head() -> str:
    repository = adapter.SubprocessGitRepositoryV1()
    try:
        return str(repository.require_current_clean_head())
    except Exception as exc:
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "production execution requires the exact clean repository head"
        ) from exc


def _require_runtime_binding(args: argparse.Namespace) -> str | None:
    if args.command == "status":
        return None
    head = _clean_head()
    expected_commit = (
        args.source_commit_sha
        if args.command == "prepare"
        else args.expected_source_commit_sha
    )
    if head != expected_commit:
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "clean repository head differs from expected source commit"
        )
    expected_image = (
        args.immutable_image
        if args.command == "prepare"
        else args.expected_immutable_image
    )
    if args.command in {"run-slate", "finish-panel"}:
        if os.environ.get(RUNTIME_IMAGE_ENV) != expected_image:
            raise CorpusR6FullUnionPanelFreezeCLIError(
                f"runtime image binding requires exact {RUNTIME_IMAGE_ENV}"
            )
    return head


def _source_ordinal(args: argparse.Namespace) -> int:
    if args.source_ordinal is not None:
        if args.source_offset != 0:
            raise CorpusR6FullUnionPanelFreezeCLIError(
                "explicit source ordinal cannot also use a source offset"
            )
        return int(args.source_ordinal)
    raw_index = os.environ.get("CLOUD_RUN_TASK_INDEX")
    if raw_index is None or not raw_index.isdigit():
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "run-slate requires --source-ordinal or CLOUD_RUN_TASK_INDEX"
        )
    return int(args.source_offset) + int(raw_index)


def _runtime_task_environment() -> dict[str, object]:
    raw = {
        "cloud_job": os.environ.get("CLOUD_RUN_JOB"),
        "cloud_execution": os.environ.get("CLOUD_RUN_EXECUTION"),
        "task_index": os.environ.get("CLOUD_RUN_TASK_INDEX"),
        "task_attempt": os.environ.get("CLOUD_RUN_TASK_ATTEMPT"),
        "task_count": os.environ.get("CLOUD_RUN_TASK_COUNT"),
    }
    if (
        any(type(raw[field]) is not str or not raw[field] for field in raw)
        or not str(raw["task_index"]).isdigit()
        or not str(raw["task_attempt"]).isdigit()
        or not str(raw["task_count"]).isdigit()
    ):
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "run-slate requires the complete Cloud Run task environment"
        )
    task_index = int(str(raw["task_index"]))
    task_attempt = int(str(raw["task_attempt"]))
    task_count = int(str(raw["task_count"]))
    if task_attempt != 0 or not 0 <= task_index < task_count:
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "automatic retry or Cloud Run task census differs"
        )
    return {
        "cloud_job": str(raw["cloud_job"]),
        "cloud_execution": str(raw["cloud_execution"]),
        "task_index": task_index,
        "task_attempt": task_attempt,
        "task_count": task_count,
    }


def _nonempty_attachment_count(value: object, *, keyed: bool = False) -> int:
    """Count nonempty network/VPC/Cloud SQL/tag attachment fields."""
    if isinstance(value, Mapping):
        count = 0
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "").replace("_", "")
            attachment_key = any(
                token in normalized for token in ("network", "vpc", "cloudsql", "tag")
            )
            count += _nonempty_attachment_count(
                item, keyed=keyed or attachment_key
            )
        return count
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return sum(_nonempty_attachment_count(item, keyed=keyed) for item in value)
    return int(keyed and value not in {None, "", False})


def _project_runtime_execution_response(
    *,
    execution: Mapping[str, object],
    args: argparse.Namespace,
    source_ordinal: int,
    task: Mapping[str, object],
) -> dict[str, object]:
    """Project and close the authenticated Cloud Run execution surface."""
    metadata = dict(execution.get("metadata", {}))
    annotations = dict(metadata.get("annotations", {}))
    labels = dict(metadata.get("labels", {}))
    spec = dict(execution.get("spec", {}))
    execution_template = dict(spec.get("template", {}))
    task_spec = dict(execution_template.get("spec", {}))
    containers = list(task_spec.get("containers", []))
    if len(containers) != 1 or not isinstance(containers[0], Mapping):
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "Cloud Run execution container census differs"
        )
    container = dict(containers[0])
    limits = dict(dict(container.get("resources", {})).get("limits", {}))
    environment_rows = list(container.get("env", []))
    configured_environment: dict[str, str] = {}
    secret_env_count = 0
    for raw_row in environment_rows:
        if not isinstance(raw_row, Mapping):
            secret_env_count += 1
            continue
        row = dict(raw_row)
        if set(row) != {"name", "value"}:
            secret_env_count += 1
            continue
        name = row.get("name")
        value = row.get("value")
        if type(name) is not str or type(value) is not str or name in configured_environment:
            secret_env_count += 1
            continue
        configured_environment[name] = value
    volume_rows = list(task_spec.get("volumes", []))
    volume_mount_rows = list(container.get("volumeMounts", []))
    network_attachment_count = _nonempty_attachment_count(annotations)
    for key, value in task_spec.items():
        normalized = str(key).lower().replace("-", "").replace("_", "")
        if any(token in normalized for token in ("network", "vpc", "cloudsql", "tag")):
            network_attachment_count += _nonempty_attachment_count(
                value, keyed=True
            )
    observed_execution = str(metadata.get("name", "")).rsplit("/", 1)[-1]
    timeout = str(task_spec.get("timeoutSeconds", "")).removesuffix("s")
    expected_environment = {
        PRODUCTION_ENABLE_ENV: "1",
        RUNTIME_IMAGE_ENV: str(args.expected_immutable_image),
    }
    job_uids = {
        "atlas-minimal-c-s2023-w1-v1": (
            "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
        ),
        "atlas-cbc-32g-full-2023-w8-v1": (
            "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
        ),
    }
    if (
        args.project != "nfl-predictions-503414"
        or str(args.expected_project_number) != "817589974517"
        or args.expected_region != "us-central1"
        or observed_execution != task["cloud_execution"]
        or str(metadata.get("namespace")) != str(args.expected_project_number)
        or labels.get("run.googleapis.com/job") != task["cloud_job"]
        or labels.get("run.googleapis.com/jobUid")
        != job_uids.get(str(task["cloud_job"]))
        or int(spec.get("taskCount", -1)) != task["task_count"]
        or container.get("image") != args.expected_immutable_image
        or not timeout.isdigit()
        or frozenset(spec) != frozenset({"parallelism", "taskCount", "template"})
        or frozenset(execution_template) != frozenset({"spec"})
        or frozenset(task_spec) not in {
            frozenset({
                "containers", "maxRetries", "serviceAccountName", "timeoutSeconds"
            }),
            frozenset({
                "containers", "maxRetries", "serviceAccountName", "timeoutSeconds",
                "volumes",
            }),
        }
        or frozenset(container) not in {
            frozenset({"args", "command", "env", "image", "resources"}),
            frozenset({
                "args", "command", "env", "image", "resources", "volumeMounts"
            }),
        }
        or task_spec.get("serviceAccountName")
        != "817589974517-compute@developer.gserviceaccount.com"
        or configured_environment != expected_environment
        or secret_env_count != 0
        or volume_rows != []
        or volume_mount_rows != []
        or network_attachment_count != 0
    ):
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "Cloud Run execution authority surface differs"
        )
    evidence: dict[str, object] = {
        "schema_version": freeze.RUNTIME_EXECUTION_EVIDENCE_SCHEMA,
        "cloud_project_id": args.project,
        "cloud_project_number": str(args.expected_project_number),
        "cloud_region": args.expected_region,
        "cloud_job": task["cloud_job"],
        "cloud_execution": task["cloud_execution"],
        "cloud_execution_uid": str(metadata.get("uid", "")),
        "cloud_job_uid": str(labels.get("run.googleapis.com/jobUid", "")),
        "cloud_job_generation": str(
            labels.get("run.googleapis.com/jobGeneration", "")
        ),
        "execution_resource_version": str(metadata.get("resourceVersion", "")),
        "source_ordinal": source_ordinal,
        "task_index": task["task_index"],
        "task_attempt": task["task_attempt"],
        "task_count": task["task_count"],
        "parallelism": int(spec.get("parallelism", -1)),
        "max_retries": int(task_spec.get("maxRetries", -1)),
        "task_timeout_seconds": int(timeout),
        "immutable_image": str(container.get("image", "")),
        "service_account": str(task_spec.get("serviceAccountName", "")),
        "cpu": str(limits.get("cpu", "")),
        "memory": str(limits.get("memory", "")),
        "container_command": list(container.get("command", [])),
        "container_args": list(container.get("args", [])),
        "execution_spec_keys": sorted(spec),
        "execution_template_keys": sorted(execution_template),
        "task_spec_keys": sorted(task_spec),
        "container_keys": sorted(container),
        "configured_environment": configured_environment,
        "secret_env_count": secret_env_count,
        "volume_count": len(volume_rows),
        "volume_mount_count": len(volume_mount_rows),
        "network_attachment_count": network_attachment_count,
        "authenticated_execution_api_read": True,
    }
    evidence["runtime_execution_evidence_sha256"] = batch.canonical_sha256(
        evidence
    )
    return evidence


def _authenticated_runtime_execution_evidence(
    *, args: argparse.Namespace, source_ordinal: int,
) -> dict[str, object]:
    """Read this exact execution from the authenticated Cloud Run API."""
    task = _runtime_task_environment()
    if type(args.project) is not str or not args.project:
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "run-slate requires one explicit cloud project"
        )
    if (
        not str(args.expected_project_number).isdigit()
        or args.expected_region != "us-central1"
    ):
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "Cloud Run project number or region differs"
        )
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        session = AuthorizedSession(credentials)
        url = (
            f"https://{args.expected_region}-run.googleapis.com/apis/"
            "run.googleapis.com/v1/namespaces/"
            f"{args.expected_project_number}/executions/"
            f"{task['cloud_execution']}"
        )
        response = None
        for attempt in range(3):
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                break
            if attempt < 2 and response.status_code in {404, 429, 500, 503}:
                time.sleep(1)
                continue
            response.raise_for_status()
        if response is None or response.status_code != 200:
            raise RuntimeError("execution API did not return the exact resource")
        execution = response.json()
    except Exception as exc:
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "authenticated Cloud Run execution evidence is unavailable"
        ) from exc
    if not isinstance(execution, Mapping):
        raise CorpusR6FullUnionPanelFreezeCLIError(
            "Cloud Run execution response differs"
        )
    return _project_runtime_execution_response(
        execution=execution,
        args=args,
        source_ordinal=source_ordinal,
        task=task,
    )


def run(
    argv: Sequence[str], *, storage: object,
    runtime_evidence_probe: Callable[..., Mapping[str, object]] = (
        _authenticated_runtime_execution_evidence
    ),
) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    _require_production_gate(args)
    head = _require_runtime_binding(args)
    if args.command == "prepare":
        return release.prepare_release_v1(
            storage=storage,
            panel_index_identity=_identity(args, "panel"),
            source_commit_sha=str(head),
            immutable_image=args.immutable_image,
            output_prefix=args.output_prefix,
        )
    if args.command == "run-slate":
        source_ordinal = _source_ordinal(args)
        runtime_execution_evidence = dict(runtime_evidence_probe(
            args=args, source_ordinal=source_ordinal
        ))
        return release.run_slate_release_v1(
            storage=storage,
            manifest_identity=_identity(args, "manifest"),
            source_ordinal=source_ordinal,
            runtime_source_commit_sha=str(head),
            runtime_immutable_image=args.expected_immutable_image,
            runtime_execution_evidence=runtime_execution_evidence,
        )
    if args.command == "status":
        return release.panel_status_v1(
            storage=storage,
            manifest_identity=_identity(args, "manifest"),
        )
    if args.command == "finish-panel":
        return release.finish_release_v1(
            storage=storage,
            manifest_identity=_identity(args, "manifest"),
        )
    raise CorpusR6FullUnionPanelFreezeCLIError(
        f"unregistered command {args.command!r}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    retained = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(retained)
    _require_production_gate(args)
    _require_runtime_binding(args)
    storage = GoogleCloudObjectStore(project=args.project)
    result = run(retained, storage=storage)
    sys.stdout.buffer.write(batch.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
