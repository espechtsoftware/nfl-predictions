#!/usr/bin/env python3
"""Publish the outcome-blind registry release from an accepted 54x7 batch."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
import os
from pathlib import Path
import sys

from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    GoogleCloudObjectStore,
    ObjectIdentity,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    CorpusRetrievalNeo4jError,
    canonical_json_bytes,
    parse_canonical_json_bytes,
)
from nfl_dfs.research.corpus_strategy_registry_release import (
    CorpusStrategyRegistryReleaseError,
    publish_strategy_registry_release_with_preflight,
)


ENABLE_ENV = "CORPUS_STRATEGY_REGISTRY_RELEASE_ENABLED"


def _identity(args: argparse.Namespace, prefix: str) -> ObjectIdentity:
    return ObjectIdentity(
        uri=getattr(args, f"{prefix}_uri"),
        generation=getattr(args, f"{prefix}_generation"),
        sha256=getattr(args, f"{prefix}_sha256"),
        bytes=getattr(args, f"{prefix}_bytes"),
    )


def _add_identity(parser: argparse.ArgumentParser, prefix: str) -> None:
    option = prefix.replace("_", "-")
    parser.add_argument(f"--{option}-uri", required=True)
    parser.add_argument(f"--{option}-generation", required=True)
    parser.add_argument(f"--{option}-sha256", required=True)
    parser.add_argument(f"--{option}-bytes", type=int, required=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("parked", help="default-off command; constructs no client")
    publish = sub.add_parser(
        "publish", help="reopen exact accepted evidence and publish once"
    )
    publish.add_argument("--project")
    _add_identity(publish, "retrieval_terminal")
    _add_identity(publish, "batch_acceptance")
    publish.add_argument("--registry-id", required=True)
    publish.add_argument("--output-prefix", required=True)
    publish.add_argument("--created-at-utc", required=True)
    publish.add_argument("--producer-code-commit", required=True)
    publish.add_argument("--producer-image", required=True)
    publish.add_argument("--producer-build-id", required=True)
    publish.add_argument(
        "--named-scenario-definition",
        action="append",
        type=Path,
        default=[],
        help=(
            "canonical, self-hashed additive named-scenario manifest; "
            "repeat for multiple definitions"
        ),
    )
    publish.add_argument("--execute", action="store_true")
    return parser


def _load_named_definition(path: Path) -> Mapping[str, object]:
    try:
        raw = path.read_bytes()
        parsed = parse_canonical_json_bytes(
            raw, label=f"named scenario definition {path}"
        )
    except (CorpusRetrievalNeo4jError, OSError) as exc:
        raise CorpusStrategyRegistryReleaseError(
            f"named scenario definition {path} differs"
        ) from exc
    if not isinstance(parsed, Mapping):
        raise CorpusStrategyRegistryReleaseError(
            f"named scenario definition {path} must be an object"
        )
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "parked":
            result = {
                "schema_version": "corpus-strategy-registry-release-parked/v1",
                "default_off": True,
                "cloud_client_constructed": False,
                "accepted_batch_read": False,
                "graph_contacted": False,
                "uses_realized_outcomes": False,
            }
        else:
            if args.execute is not True or os.environ.get(ENABLE_ENV) != "1":
                raise CorpusStrategyRegistryReleaseError(
                    f"publication requires literal --execute and {ENABLE_ENV}=1"
                )
            producer_release = {
                "code_commit": args.producer_code_commit,
                "image": args.producer_image,
                "build_id": args.producer_build_id,
            }
            if (
                os.environ.get("CODE_SHA", "")
                != producer_release["code_commit"]
                or os.environ.get("CORPUS_NEO4J_IMAGE", "")
                != producer_release["image"]
                or os.environ.get("CORPUS_NEO4J_BUILD_ID", "")
                != producer_release["build_id"]
            ):
                raise CorpusStrategyRegistryReleaseError(
                    "producer code/image/build environment differs"
                )
            storage = GoogleCloudObjectStore(project=args.project)
            named_definitions = [
                _load_named_definition(path)
                for path in args.named_scenario_definition
            ]
            published = publish_strategy_registry_release_with_preflight(
                storage=storage,
                retrieval_terminal_identity=_identity(
                    args, "retrieval_terminal"
                ),
                batch_acceptance_identity=_identity(
                    args, "batch_acceptance"
                ),
                registry_id=args.registry_id,
                output_prefix=args.output_prefix,
                created_at_utc=args.created_at_utc,
                producer_release=producer_release,
                named_scenario_definitions=named_definitions,
            )
            result = {
                "schema_version": "corpus-strategy-registry-release-published/v1",
                "registry_release": published.release_identity.as_dict(),
                "publication_receipt": published.publication_identity.as_dict(),
                "publication_intent": published.publication[
                    "publication_intent"
                ],
                "registry_id": published.release["registry_id"],
                "experiment_count": published.publication["experiment_count"],
                "metric_scope": published.publication["metric_scope"],
                "realized_namespace_reserved": True,
                "uses_realized_outcomes": False,
                "graph_contacted": False,
            }
            if named_definitions:
                result.update({
                    "named_scenario_definition_count": published.publication[
                        "named_scenario_definition_count"
                    ],
                    "accepted_scenario_evidence_count": published.publication[
                        "accepted_scenario_evidence_count"
                    ],
                    "named_heldout_metrics_descriptive_only": True,
                    "named_ranker_input_authority": False,
                })
        sys.stdout.buffer.write(canonical_json_bytes(result) + b"\n")
        return 0
    except (
        CorpusNeo4jTransportError,
        CorpusStrategyRegistryReleaseError,
        OSError,
        ValueError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
