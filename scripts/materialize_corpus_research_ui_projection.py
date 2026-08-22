#!/usr/bin/env python3
"""Materialize the receipt-bound corpus research UI projection."""

from __future__ import annotations

import argparse
import os
import sys

from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    GoogleCloudObjectStore,
    ObjectIdentity,
    open_bound_backend,
    require_execute_gate,
    validate_load_manifest,
)
from nfl_dfs.research.corpus_research_ui_bridge import (
    CorpusResearchUIBridgeError,
    materialize_ui_projection,
)
from nfl_dfs.research.corpus_retrieval_neo4j import canonical_json_bytes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parked", help="default-off command; constructs no clients")
    run = sub.add_parser(
        "materialize", help="run the exact six-query reader catalog once"
    )
    run.add_argument("--project")
    run.add_argument("--manifest-uri", required=True)
    run.add_argument("--manifest-generation", required=True)
    run.add_argument("--manifest-sha256", required=True)
    run.add_argument("--manifest-bytes", type=int, required=True)
    run.add_argument("--generated-at-utc", required=True)
    run.add_argument("--execute", action="store_true")
    return parser


def _manifest_identity(args: argparse.Namespace) -> ObjectIdentity:
    return ObjectIdentity(
        uri=args.manifest_uri,
        generation=args.manifest_generation,
        sha256=args.manifest_sha256,
        bytes=args.manifest_bytes,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "parked":
            result = {
                "schema_version": "corpus-research-ui-bridge-parked/v1",
                "default_off": True,
                "cloud_client_constructed": False,
                "neo4j_contacted": False,
                "graph_mutation": False,
            }
        else:
            require_execute_gate(execute=args.execute, environ=os.environ)
            storage = GoogleCloudObjectStore(project=args.project)
            bundle = validate_load_manifest(
                storage=storage,
                manifest_identity=_manifest_identity(args),
            )
            release = bundle.manifest["release"]
            if (
                os.environ.get("CODE_SHA", "") != release["code_commit"]
                or os.environ.get("CORPUS_NEO4J_IMAGE", "")
                != release["image"]
            ):
                raise CorpusResearchUIBridgeError(
                    "runtime code/image differs from the governed load manifest"
                )
            graph = open_bound_backend(
                deployment=bundle.deployment,
                role="reader",
                environ=os.environ,
            )
            try:
                published = materialize_ui_projection(
                    storage=storage,
                    graph=graph,
                    bundle=bundle,
                    generated_at_utc=args.generated_at_utc,
                )
            finally:
                graph.close()
            result = {
                "schema_version": "corpus-research-ui-bridge-complete/v1",
                "ui_projection": published.projection_identity.as_dict(),
                "bridge_receipt": published.receipt_identity.as_dict(),
                "registry_id": published.receipt["registry_id"],
                "combined_row_count": published.receipt["combined_row_count"],
                "read_only": True,
                "graph_mutation": False,
                "realized_namespace_reserved": True,
            }
        sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
        return 0
    except (
        CorpusNeo4jTransportError,
        CorpusResearchUIBridgeError,
        OSError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
