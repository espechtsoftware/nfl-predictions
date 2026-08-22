#!/usr/bin/env python3
"""Govern one reuse-only Cloud Run execution for corpus realized grading."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from nfl_dfs.research import corpus_realized_cloud_transport as transport


def _add_config(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=transport.PROJECT)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--job-uid", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--batch-acceptance-uri", required=True)
    parser.add_argument("--batch-acceptance-generation", required=True)
    parser.add_argument("--batch-acceptance-sha256", required=True)
    parser.add_argument("--batch-acceptance-bytes", type=int, required=True)


def _add_execute(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute", action="store_true")


def _add_census(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--job-file", type=Path, required=True)
    parser.add_argument("--executions-file", type=Path, required=True)
    parser.add_argument("--schedulers-file", type=Path, required=True)
    parser.add_argument("--all-regions-complete", action="store_true")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parked", help="default-off no-client parked command")

    build = sub.add_parser("validate-build")
    _add_config(build)
    build.add_argument("--build-metadata-file", type=Path, required=True)

    preflight = sub.add_parser("validate-reuse-preflight")
    preflight.add_argument("--job", required=True)
    preflight.add_argument("--job-uid", required=True)
    _add_census(preflight)

    parked = sub.add_parser("validate-parked-job")
    _add_config(parked)
    parked.add_argument("--job-file", type=Path, required=True)

    acquire = sub.add_parser("acquire-lease")
    _add_config(acquire)
    acquire.add_argument("--acquired-at-utc", required=True)
    _add_execute(acquire)

    prepare = sub.add_parser("prepare-launch")
    _add_config(prepare)
    _add_census(prepare)
    prepare.add_argument("--build-metadata-file", type=Path, required=True)
    prepare.add_argument("--created-at-utc", required=True)
    prepare.add_argument("--query-observed-at-utc", required=True)
    _add_execute(prepare)

    confirm = sub.add_parser("confirm-query-unused")
    _add_config(confirm)
    confirm.add_argument("--created-at-utc", required=True)
    confirm.add_argument("--query-observed-at-utc", required=True)
    _add_execute(confirm)

    bind = sub.add_parser("bind-execution")
    _add_config(bind)
    _add_census(bind)
    bind.add_argument("--execution-file", type=Path, required=True)
    bind.add_argument("--created-at-utc", required=True)
    _add_execute(bind)

    finish = sub.add_parser("finish-execution")
    _add_config(finish)
    _add_census(finish)
    finish.add_argument("--execution-file", type=Path, required=True)
    finish.add_argument("--created-at-utc", required=True)
    _add_execute(finish)

    release = sub.add_parser("release-lease")
    _add_config(release)
    release.add_argument("--created-at-utc", required=True)
    _add_execute(release)

    abandon = sub.add_parser("abandon-lease")
    _add_config(abandon)
    abandon.add_argument("--created-at-utc", required=True)
    abandon.add_argument("--reason", required=True)
    _add_execute(abandon)
    return parser


def _config(args: argparse.Namespace) -> transport.RunConfig:
    if args.project != transport.PROJECT:
        raise transport.CorpusRealizedCloudTransportError(
            "realized transport project differs"
        )
    return transport.validate_run_config(transport.RunConfig(
        run_id=args.run_id,
        build_id=args.build_id,
        code_sha=args.code_sha,
        image=args.image,
        job_name=args.job,
        job_uid=args.job_uid,
        service_account=args.service_account,
        batch_acceptance=transport.ObjectIdentity(
            uri=args.batch_acceptance_uri,
            generation=args.batch_acceptance_generation,
            sha256=args.batch_acceptance_sha256,
            bytes=args.batch_acceptance_bytes,
        ),
    ))


def _external_json(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise transport.CorpusRealizedCloudTransportError(
            f"{label} file is absent or unsafe"
        )
    try:
        return json.loads(path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise transport.CorpusRealizedCloudTransportError(
            f"{label} is not JSON"
        ) from exc


def _store(args: argparse.Namespace) -> transport.GoogleCloudObjectStore:
    return transport.GoogleCloudObjectStore(
        execute=args.execute,
        environ=os.environ,
        project=args.project,
    )


def _census(args: argparse.Namespace) -> tuple[object, object, object]:
    return (
        _external_json(args.job_file, label="job census"),
        _external_json(args.executions_file, label="execution census"),
        _external_json(args.schedulers_file, label="scheduler census"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "parked":
        result: object = {
            "status": "CORPUS_REALIZED_CLOUD_TRANSPORT_PARKED",
            "cloud_client_created": False,
            "uses_realized_outcomes": False,
            "automatic_retry_licensed": False,
        }
    elif args.command == "validate-build":
        result = transport.validate_build_metadata(
            _external_json(args.build_metadata_file, label="build metadata"),
            config=_config(args),
        )
    elif args.command == "validate-reuse-preflight":
        job, executions, schedulers = _census(args)
        result = transport.validate_reuse_preflight(
            job=job,
            executions=executions,
            schedulers=schedulers,
            job_name=args.job,
            job_uid=args.job_uid,
            all_regions_complete=args.all_regions_complete,
        )
    elif args.command == "validate-parked-job":
        result = transport.validate_parked_job(
            _external_json(args.job_file, label="parked job"),
            config=_config(args),
        )
    elif args.command == "acquire-lease":
        result = transport.acquire_historical_lease(
            storage=_store(args),
            config=_config(args),
            acquired_at_utc=args.acquired_at_utc,
        )
    elif args.command == "prepare-launch":
        config = _config(args)
        job, executions, schedulers = _census(args)
        transport.require_execute_gate(execute=args.execute, environ=os.environ)
        proof = transport.GoogleBigQueryJobInspector().prove_unused(
            config=config,
            observed_at_utc=args.query_observed_at_utc,
        )
        result = transport.prepare_launch(
            storage=_store(args),
            config=config,
            build_metadata=_external_json(
                args.build_metadata_file, label="build metadata"
            ),
            parked_job=job,
            executions=executions,
            schedulers=schedulers,
            all_regions_complete=args.all_regions_complete,
            unused_proof=proof,
            created_at_utc=args.created_at_utc,
        )
    elif args.command == "confirm-query-unused":
        config = _config(args)
        transport.require_execute_gate(execute=args.execute, environ=os.environ)
        proof = transport.GoogleBigQueryJobInspector().prove_unused(
            config=config,
            observed_at_utc=args.query_observed_at_utc,
        )
        result = transport.confirm_query_unused(
            storage=_store(args),
            config=config,
            unused_proof=proof,
            created_at_utc=args.created_at_utc,
        )
    elif args.command == "bind-execution":
        job, executions, schedulers = _census(args)
        result = transport.bind_execution(
            storage=_store(args),
            config=_config(args),
            execution=_external_json(
                args.execution_file, label="execution metadata"
            ),
            parked_job=job,
            executions=executions,
            schedulers=schedulers,
            all_regions_complete=args.all_regions_complete,
            created_at_utc=args.created_at_utc,
        )
    elif args.command == "finish-execution":
        job, executions, schedulers = _census(args)
        result = transport.finish_execution(
            storage=_store(args),
            config=_config(args),
            execution=_external_json(
                args.execution_file, label="execution metadata"
            ),
            parked_job=job,
            executions=executions,
            schedulers=schedulers,
            all_regions_complete=args.all_regions_complete,
            created_at_utc=args.created_at_utc,
        )
    elif args.command == "release-lease":
        result = transport.release_historical_lease(
            storage=_store(args),
            config=_config(args),
            created_at_utc=args.created_at_utc,
        )
    else:
        result = transport.abandon_historical_lease(
            storage=_store(args),
            config=_config(args),
            reason=args.reason,
            created_at_utc=args.created_at_utc,
        )
    print(transport.canonical_json_bytes(result).decode(), end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except transport.CorpusRealizedCloudTransportError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
