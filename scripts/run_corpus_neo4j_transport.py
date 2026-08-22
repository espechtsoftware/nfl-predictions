#!/usr/bin/env python3
"""Run the default-off governed transport for the dedicated corpus graph."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    GoogleCloudObjectStore,
    ObjectIdentity,
    bind_launch_execution,
    bootstrap_schema,
    consume_launch_intent,
    finish_launch_execution,
    finish_suite,
    load_parametric_suite,
    load_plan,
    load_strategy_registry,
    open_bound_backend,
    query_smoke,
    query_strategy_registry,
    recover_plan_receipt,
    recover_strategy_registry_receipt,
    require_execute_gate,
    validate_build_metadata,
    validate_parked_job,
    validate_reuse_preflight,
    validate_load_manifest,
)
from nfl_dfs.research.corpus_retrieval_neo4j import canonical_json_bytes


def _add_manifest_identity(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest-uri", required=True)
    parser.add_argument("--manifest-generation", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--manifest-bytes", type=int, required=True)
    parser.add_argument("--project")


def _add_execute(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true")


def _add_operation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--operation",
        choices=(
            "bootstrap-schema", "load-task0", "load-parametric-task",
            "load-suite", "recover-task0-receipt",
            "recover-parametric-receipt", "finish-suite", "query-smoke",
            "load-strategy-registry", "recover-strategy-registry-receipt",
            "query-strategy-registry",
        ),
        required=True,
    )
    parser.add_argument("--task-index", type=int)
    parser.add_argument("--require-complete-suite", action="store_true")


def _add_frozen_job(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--job-file", type=Path, required=True)
    parser.add_argument("--job-name", required=True)
    parser.add_argument("--job-uid", required=True)


def _add_census(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--executions-file", type=Path, required=True)
    parser.add_argument("--schedulers-file", type=Path, required=True)
    parser.add_argument("--all-regions-complete", action="store_true")


def _add_parked_contract(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--image", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument(
        "--role", choices=("bootstrap", "writer", "reader"), required=True
    )
    parser.add_argument("--uri", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--provider-resource-id", required=True)
    parser.add_argument("--username-secret-version", required=True)
    parser.add_argument("--password-secret-version", required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parked", help="default-off no-client command")

    build = sub.add_parser(
        "validate-build", help="validate direct-Git image provenance and graph smokes"
    )
    build.add_argument("--build-metadata-file", type=Path, required=True)
    build.add_argument("--build-id", required=True)
    build.add_argument("--code-sha", required=True)
    build.add_argument("--image", required=True)

    preflight = sub.add_parser(
        "validate-reuse-preflight",
        help="bind the externally frozen idle/unscheduled attachment-free job",
    )
    _add_frozen_job(preflight)
    _add_census(preflight)

    parked_job = sub.add_parser(
        "validate-parked-job", help="validate the exact post-configure parked spec"
    )
    _add_frozen_job(parked_job)
    _add_parked_contract(parked_job)

    consume = sub.add_parser(
        "consume-launch", help="publish one stable create-once launch intent"
    )
    _add_manifest_identity(consume)
    _add_operation(consume)
    _add_frozen_job(consume)
    _add_census(consume)
    _add_parked_contract(consume)
    consume.add_argument("--created-at-utc", required=True)
    _add_execute(consume)

    bind = sub.add_parser(
        "bind-execution", help="bind the sole post-intent execution name"
    )
    _add_manifest_identity(bind)
    _add_operation(bind)
    _add_frozen_job(bind)
    _add_census(bind)
    bind.add_argument("--created-at-utc", required=True)
    _add_execute(bind)

    terminal = sub.add_parser(
        "finish-execution",
        help="accept strict terminal success after exact operation receipts",
    )
    _add_manifest_identity(terminal)
    _add_operation(terminal)
    terminal.add_argument("--execution-file", type=Path, required=True)
    terminal.add_argument("--created-at-utc", required=True)
    _add_execute(terminal)

    validate = sub.add_parser(
        "validate", help="generation-pin and rebuild every manifest input"
    )
    _add_manifest_identity(validate)

    bootstrap = sub.add_parser(
        "bootstrap-schema", help="bootstrap only an initially empty dedicated database"
    )
    _add_manifest_identity(bootstrap)
    _add_execute(bootstrap)

    retrieval = sub.add_parser("load-task0", help="load accepted retrieval task 0")
    _add_manifest_identity(retrieval)
    _add_execute(retrieval)

    parametric = sub.add_parser(
        "load-parametric-task", help="load one accepted task from the complete suite"
    )
    _add_manifest_identity(parametric)
    parametric.add_argument("--task-index", type=int, required=True)
    _add_execute(parametric)

    suite = sub.add_parser(
        "load-suite", help="serially load all 54 accepted parametric tasks"
    )
    _add_manifest_identity(suite)
    _add_execute(suite)

    recover_retrieval = sub.add_parser(
        "recover-task0-receipt",
        help="read-only recovery after an ambiguous task-0 receipt publication",
    )
    _add_manifest_identity(recover_retrieval)
    _add_execute(recover_retrieval)

    recover_parametric = sub.add_parser(
        "recover-parametric-receipt",
        help="read-only recovery after an ambiguous parametric receipt publication",
    )
    _add_manifest_identity(recover_parametric)
    recover_parametric.add_argument("--task-index", type=int, required=True)
    _add_execute(recover_parametric)

    registry_load = sub.add_parser(
        "load-strategy-registry",
        help="load the generation-pinned outcome-blind strategy registry",
    )
    _add_manifest_identity(registry_load)
    _add_execute(registry_load)

    registry_recover = sub.add_parser(
        "recover-strategy-registry-receipt",
        help="read-only recovery of the exact strategy-registry load receipt",
    )
    _add_manifest_identity(registry_recover)
    _add_execute(registry_recover)

    registry_query = sub.add_parser(
        "query-strategy-registry",
        help="run the bounded read-only strategy-registry query catalog",
    )
    _add_manifest_identity(registry_query)
    _add_execute(registry_query)

    finish = sub.add_parser(
        "finish-suite", help="publish terminal only after exact 54-task graph census"
    )
    _add_manifest_identity(finish)
    _add_execute(finish)

    smoke = sub.add_parser("query-smoke", help="run the bounded read-only query smoke")
    _add_manifest_identity(smoke)
    smoke.add_argument("--require-complete-suite", action="store_true")
    _add_execute(smoke)
    return parser


def _identity(args: argparse.Namespace) -> ObjectIdentity:
    return ObjectIdentity(
        uri=args.manifest_uri,
        generation=args.manifest_generation,
        sha256=args.manifest_sha256,
        bytes=args.manifest_bytes,
    )


def _external_json(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise CorpusNeo4jTransportError(f"{label} file is absent or unsafe")
    try:
        return json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusNeo4jTransportError(f"{label} is not JSON") from exc


def _parked_contract(args: argparse.Namespace) -> dict[str, str]:
    return {
        "image": args.image,
        "code_sha": args.code_sha,
        "build_id": args.build_id,
        "service_account": args.service_account,
        "uri": args.uri,
        "database": args.database,
        "provider_resource_id": args.provider_resource_id,
        "username_secret_version": args.username_secret_version,
        "password_secret_version": args.password_secret_version,
    }


def _governance_bundle(
    args: argparse.Namespace,
) -> tuple[GoogleCloudObjectStore, object]:
    require_execute_gate(execute=args.execute, environ=os.environ)
    storage = GoogleCloudObjectStore(project=args.project)
    bundle = validate_load_manifest(storage=storage, manifest_identity=_identity(args))
    _release_gate(bundle)
    return storage, bundle


def _release_gate(bundle: object) -> None:
    manifest = bundle.manifest
    release = manifest["release"]
    code_sha = os.environ.get("CODE_SHA", "")
    image = os.environ.get("CORPUS_NEO4J_IMAGE", "")
    if code_sha != release["code_commit"] or image != release["image"]:
        raise CorpusNeo4jTransportError(
            "runtime code/image differs from the immutable load manifest"
        )


def _live(
    args: argparse.Namespace, *, role: str, action: object,
) -> dict[str, object]:
    require_execute_gate(execute=args.execute, environ=os.environ)
    storage = GoogleCloudObjectStore(project=args.project)
    bundle = validate_load_manifest(storage=storage, manifest_identity=_identity(args))
    _release_gate(bundle)
    backend = open_bound_backend(
        deployment=bundle.deployment, role=role, environ=os.environ
    )
    try:
        return dict(action(storage, backend, bundle))
    finally:
        backend.close()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "parked":
            result = {
                "schema_version": "corpus-neo4j-transport-parked/v1",
                "default_off": True,
                "gcs_client_constructed": False,
                "neo4j_driver_imported": False,
                "neo4j_contacted": False,
                "graph_mutation": False,
            }
        elif args.command == "validate-build":
            result = validate_build_metadata(
                _external_json(args.build_metadata_file, label="build metadata"),
                build_id=args.build_id,
                code_sha=args.code_sha,
                image=args.image,
            )
        elif args.command == "validate-reuse-preflight":
            result = validate_reuse_preflight(
                job=_external_json(args.job_file, label="reused job"),
                executions=_external_json(
                    args.executions_file, label="execution census"
                ),
                schedulers=_external_json(
                    args.schedulers_file, label="scheduler census"
                ),
                expected_job_name=args.job_name,
                expected_job_uid=args.job_uid,
                all_regions_complete=args.all_regions_complete,
            )
        elif args.command == "validate-parked-job":
            result = validate_parked_job(
                job=_external_json(args.job_file, label="parked job"),
                expected_job_name=args.job_name,
                expected_job_uid=args.job_uid,
                role=args.role,
                **_parked_contract(args),
            )
        elif args.command == "consume-launch":
            storage, bundle = _governance_bundle(args)
            result = consume_launch_intent(
                storage=storage,
                bundle=bundle,
                operation=args.operation,
                task_index=args.task_index,
                require_complete_suite=args.require_complete_suite,
                project=args.project,
                job=_external_json(args.job_file, label="parked job"),
                executions=_external_json(
                    args.executions_file, label="execution census"
                ),
                schedulers=_external_json(
                    args.schedulers_file, label="scheduler census"
                ),
                expected_job_name=args.job_name,
                expected_job_uid=args.job_uid,
                all_regions_complete=args.all_regions_complete,
                parked_job_contract={
                    **_parked_contract(args),
                    "role": args.role,
                },
                created_at_utc=args.created_at_utc,
            )
        elif args.command == "bind-execution":
            storage, bundle = _governance_bundle(args)
            result = bind_launch_execution(
                storage=storage,
                bundle=bundle,
                operation=args.operation,
                task_index=args.task_index,
                require_complete_suite=args.require_complete_suite,
                job=_external_json(args.job_file, label="parked job"),
                executions=_external_json(
                    args.executions_file, label="execution census"
                ),
                schedulers=_external_json(
                    args.schedulers_file, label="scheduler census"
                ),
                expected_job_name=args.job_name,
                expected_job_uid=args.job_uid,
                all_regions_complete=args.all_regions_complete,
                created_at_utc=args.created_at_utc,
            )
        elif args.command == "finish-execution":
            storage, bundle = _governance_bundle(args)
            result = finish_launch_execution(
                storage=storage,
                bundle=bundle,
                operation=args.operation,
                task_index=args.task_index,
                require_complete_suite=args.require_complete_suite,
                execution=_external_json(
                    args.execution_file, label="terminal execution"
                ),
                created_at_utc=args.created_at_utc,
            )
        elif args.command == "validate":
            storage = GoogleCloudObjectStore(project=args.project)
            bundle = validate_load_manifest(
                storage=storage, manifest_identity=_identity(args)
            )
            result = {
                "schema_version": "corpus-neo4j-transport-validated/v2",
                "load_manifest_sha256": bundle.manifest["load_manifest_sha256"],
                "retrieval_plan_sha256": bundle.retrieval_plan.plan_sha256,
                "parametric_task_count": len(bundle.parametric_plans),
                "strategy_registry_plan_sha256": (
                    bundle.strategy_registry_bundle.plan.plan_sha256
                ),
                "generation_pinned_exact_get": True,
                "worker_list_calls": 0,
                "neo4j_contacted": False,
            }
        elif args.command == "bootstrap-schema":
            result = _live(
                args,
                role="bootstrap",
                action=lambda storage, graph, bundle: bootstrap_schema(
                    storage=storage, graph=graph, bundle=bundle
                ),
            )
        elif args.command == "load-task0":
            result = _live(
                args,
                role="writer",
                action=lambda storage, graph, bundle: load_plan(
                    storage=storage, graph=graph, bundle=bundle, task_index=None
                ),
            )
        elif args.command == "load-parametric-task":
            if not 0 <= args.task_index < 54:
                raise CorpusNeo4jTransportError("task index must be in 0..53")
            result = _live(
                args,
                role="writer",
                action=lambda storage, graph, bundle: load_plan(
                    storage=storage,
                    graph=graph,
                    bundle=bundle,
                    task_index=args.task_index,
                ),
            )
        elif args.command == "load-suite":
            result = _live(
                args,
                role="writer",
                action=lambda storage, graph, bundle: load_parametric_suite(
                    storage=storage, graph=graph, bundle=bundle
                ),
            )
        elif args.command == "recover-task0-receipt":
            result = _live(
                args,
                role="reader",
                action=lambda storage, graph, bundle: recover_plan_receipt(
                    storage=storage, graph=graph, bundle=bundle, task_index=None
                ),
            )
        elif args.command == "recover-parametric-receipt":
            if not 0 <= args.task_index < 54:
                raise CorpusNeo4jTransportError("task index must be in 0..53")
            result = _live(
                args,
                role="reader",
                action=lambda storage, graph, bundle: recover_plan_receipt(
                    storage=storage,
                    graph=graph,
                    bundle=bundle,
                    task_index=args.task_index,
                ),
            )
        elif args.command == "load-strategy-registry":
            result = _live(
                args,
                role="writer",
                action=lambda storage, graph, bundle: load_strategy_registry(
                    storage=storage, graph=graph, bundle=bundle
                ),
            )
        elif args.command == "recover-strategy-registry-receipt":
            result = _live(
                args,
                role="reader",
                action=lambda storage, graph, bundle: (
                    recover_strategy_registry_receipt(
                        storage=storage, graph=graph, bundle=bundle
                    )
                ),
            )
        elif args.command == "query-strategy-registry":
            result = _live(
                args,
                role="reader",
                action=lambda storage, graph, bundle: query_strategy_registry(
                    storage=storage, graph=graph, bundle=bundle
                ),
            )
        elif args.command == "finish-suite":
            result = _live(
                args,
                role="reader",
                action=lambda storage, graph, bundle: finish_suite(
                    storage=storage, graph=graph, bundle=bundle
                ),
            )
        elif args.command == "query-smoke":
            result = _live(
                args,
                role="reader",
                action=lambda storage, graph, bundle: query_smoke(
                    storage=storage,
                    graph=graph,
                    bundle=bundle,
                    require_complete_suite=args.require_complete_suite,
                ),
            )
        else:  # pragma: no cover - argparse owns the command domain
            raise AssertionError(args.command)
        sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
        return 0
    except (CorpusNeo4jTransportError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
