#!/usr/bin/env python3
"""Prepare dedicated Neo4j deployment and generation-pinned load manifests."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    GoogleCloudObjectStore,
    build_deployment_manifest,
    object_identity,
    prepare_load_manifest,
    publish_manifest,
    require_execute_gate,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    canonical_json_bytes,
    parse_canonical_json_bytes,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    deployment = sub.add_parser(
        "deployment", help="build a secret-free dedicated deployment manifest"
    )
    deployment.add_argument("--deployment-id", required=True)
    deployment.add_argument("--provider", required=True)
    deployment.add_argument("--provider-resource-id", required=True)
    deployment.add_argument("--endpoint-host", required=True)
    deployment.add_argument("--database", required=True)
    deployment.add_argument("--server-version", required=True)
    deployment.add_argument("--server-edition", required=True)
    for role in ("bootstrap", "writer", "reader"):
        deployment.add_argument(
            f"--{role}-username-secret-version", required=True
        )
        deployment.add_argument(
            f"--{role}-password-secret-version", required=True
        )
    deployment.add_argument("--created-at-utc", required=True)
    deployment.add_argument("--output", type=Path, required=True)
    deployment.add_argument("--project")
    deployment.add_argument("--publish-uri")
    deployment.add_argument("--execute", action="store_true")

    load = sub.add_parser(
        "load-manifest",
        help="traverse exact accepted GCS evidence and build a graph load manifest",
    )
    load.add_argument("--project")
    load.add_argument("--deployment-identity", type=Path, required=True)
    load.add_argument("--retrieval-terminal-identity", type=Path, required=True)
    load.add_argument("--parametric-batch-acceptance-identity", type=Path)
    load.add_argument("--strategy-registry-release-identity", type=Path, required=True)
    load.add_argument("--output-prefix", required=True)
    load.add_argument("--code-commit", required=True)
    load.add_argument("--image", required=True)
    load.add_argument("--created-at-utc", required=True)
    load.add_argument("--output", type=Path, required=True)
    load.add_argument(
        "--publish-uri",
        help=(
            "optional create-once GCS manifest URI; requires literal --execute "
            "and CORPUS_NEO4J_MANIFEST_PUBLICATION_ENABLED=1"
        ),
    )
    load.add_argument("--execute", action="store_true")
    return parser


def _read_identity(path: Path, *, label: str) -> dict[str, object]:
    value = parse_canonical_json_bytes(path.read_bytes(), label=label)
    identity = object_identity(value, label=label)
    return identity.as_dict()


def _write_exclusive(path: Path, raw: bytes) -> None:
    if os.path.lexists(path):
        raise CorpusNeo4jTransportError(
            f"output already exists and will not be overwritten: {path}"
        )
    if not path.parent.is_dir():
        raise CorpusNeo4jTransportError("output parent directory does not exist")
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise CorpusNeo4jTransportError(
            f"output already exists and will not be overwritten: {path}"
        ) from exc


def _deployment(args: argparse.Namespace) -> dict[str, object]:
    if args.publish_uri:
        require_execute_gate(
            execute=args.execute,
            environ=os.environ,
            publication_only=True,
        )
    elif args.execute:
        raise CorpusNeo4jTransportError(
            "--execute is accepted only with --publish-uri"
        )
    principal_versions = {
        role: {
            "username": getattr(args, f"{role}_username_secret_version"),
            "password": getattr(args, f"{role}_password_secret_version"),
        }
        for role in ("bootstrap", "writer", "reader")
    }
    manifest = build_deployment_manifest(
        deployment_id=args.deployment_id,
        provider=args.provider,
        provider_resource_id=args.provider_resource_id,
        endpoint_host=args.endpoint_host,
        database=args.database,
        server_version=args.server_version,
        server_edition=args.server_edition,
        principal_secret_versions=principal_versions,
        created_at_utc=args.created_at_utc,
    )
    raw = canonical_json_bytes(manifest)
    _write_exclusive(args.output, raw)
    publication = None
    if args.publish_uri:
        storage = GoogleCloudObjectStore(project=args.project)
        publication = storage.publish_create_once(
            args.publish_uri, raw
        ).as_dict()
    return {
        "schema_version": "corpus-neo4j-deployment-prepared/v2",
        "output": str(args.output),
        "deployment_id": manifest["deployment_id"],
        "deployment_manifest_sha256": manifest["deployment_manifest_sha256"],
        "publication_identity": publication,
        "cloud_client_constructed": publication is not None,
        "graph_contacted": False,
    }


def _load_manifest(args: argparse.Namespace) -> dict[str, object]:
    if args.publish_uri:
        require_execute_gate(
            execute=args.execute,
            environ=os.environ,
            publication_only=True,
        )
        expected_uri = f"{args.output_prefix}governance/load-manifest.json"
        if args.publish_uri != expected_uri:
            raise CorpusNeo4jTransportError(
                "publish URI must be the canonical output-prefix manifest URI"
            )
    elif args.execute:
        raise CorpusNeo4jTransportError(
            "--execute is accepted only with --publish-uri"
        )
    storage = GoogleCloudObjectStore(project=args.project)
    batch_identity = (
        None
        if args.parametric_batch_acceptance_identity is None
        else _read_identity(
            args.parametric_batch_acceptance_identity,
            label="parametric batch acceptance identity",
        )
    )
    manifest, bundle = prepare_load_manifest(
        storage=storage,
        deployment_manifest_identity=_read_identity(
            args.deployment_identity, label="deployment manifest identity"
        ),
        retrieval_terminal_identity=_read_identity(
            args.retrieval_terminal_identity, label="retrieval terminal identity"
        ),
        parametric_batch_acceptance_identity=batch_identity,
        strategy_registry_release_identity=_read_identity(
            args.strategy_registry_release_identity,
            label="strategy registry release identity",
        ),
        output_prefix=args.output_prefix,
        code_commit=args.code_commit,
        image=args.image,
        created_at_utc=args.created_at_utc,
    )
    raw = canonical_json_bytes(manifest)
    _write_exclusive(args.output, raw)
    publication = None
    if args.publish_uri:
        publication = publish_manifest(
            storage=storage, uri=args.publish_uri, manifest=manifest
        ).as_dict()
    return {
        "schema_version": "corpus-neo4j-load-manifest-prepared/v2",
        "output": str(args.output),
        "publication_identity": publication,
        "load_manifest_sha256": manifest["load_manifest_sha256"],
        "retrieval_plan_sha256": bundle.retrieval_plan.plan_sha256,
        "parametric_task_count": len(bundle.parametric_plans),
        "strategy_registry_plan_sha256": (
            bundle.strategy_registry_bundle.plan.plan_sha256
        ),
        "worker_object_access_mode": "generation-pinned-exact-get-no-list",
        "graph_contacted": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "deployment":
            result = _deployment(args)
        elif args.command == "load-manifest":
            result = _load_manifest(args)
        else:  # pragma: no cover - argparse owns the command domain
            raise AssertionError(args.command)
        sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
        return 0
    except (CorpusNeo4jTransportError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
