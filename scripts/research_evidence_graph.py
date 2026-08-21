#!/usr/bin/env python3
"""Build, validate, and query the research evidence knowledge graph."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from nfl_dfs.research.evidence_knowledge_graph import (
    EvidenceGraphError,
    arm_rule_matrix,
    baseline_compatibility,
    build_graph,
    canonical_json_bytes,
    decision_brief,
    full_soft_removal,
    effects_for_arm,
    load_validated_graph,
    population_measurements,
    write_graph,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "reports/evidence-graph/20260821-v1/bootstrap.json"
DEFAULT_GRAPH_DIR = ROOT / "reports/evidence-graph/20260821-v1/materialized"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="materialize a create-once graph")
    build.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    build.add_argument("--output-dir", type=Path, default=DEFAULT_GRAPH_DIR)

    validate = sub.add_parser("validate", help="validate retained graph bytes")
    validate.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    validate.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    rules = sub.add_parser("arm-rules", help="show one arm's complete rule matrix")
    rules.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    rules.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    rules.add_argument("--arm", required=True)

    removed = sub.add_parser(
        "full-soft-removal", help="derive the all-house-rules-removed predicate"
    )
    removed.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    removed.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    removed.add_argument("--arm", required=True)

    effects = sub.add_parser("arm-effects", help="show retained effects for an arm")
    effects.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    effects.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    effects.add_argument("--arm", required=True)

    gaps = sub.add_parser(
        "winner-corpus-gap", help="show winner/pool/book characteristic measurements"
    )
    gaps.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    gaps.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    gaps.add_argument(
        "--population",
        action="append",
        default=[
            "population:milly-winners-2023-2025",
            "population:incumbent-candidate-structure",
            "population:incumbent-selected-structure",
        ],
    )

    compatible = sub.add_parser(
        "baseline-compatibility", help="compare two headline measurement contexts"
    )
    compatible.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    compatible.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    compatible.add_argument("--left", required=True)
    compatible.add_argument("--right", required=True)

    brief = sub.add_parser(
        "decision-brief", help="summarize completed evidence and license boundaries"
    )
    brief.add_argument("--graph-dir", type=Path, default=DEFAULT_GRAPH_DIR)
    brief.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser


def _print(value: object) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(value))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            graph = build_graph(ROOT, args.registry)
            _print(write_graph(graph, args.output_dir))
            return 0
        graph = load_validated_graph(ROOT, args.registry, args.graph_dir)
        if args.command == "validate":
            _print({
                "artifacts": len(graph.artifacts),
                "builder_sha256": graph.builder_sha256,
                "edges": len(graph.edges),
                "graph_id": graph.graph_id,
                "nodes": len(graph.nodes),
                "registry_sha256": graph.registry_sha256,
                "rule_universe_sha256": graph.rule_universe_sha256,
                "valid": True,
            })
        elif args.command == "arm-rules":
            _print({"arm_id": args.arm, "rules": arm_rule_matrix(graph, args.arm)})
        elif args.command == "full-soft-removal":
            _print(full_soft_removal(graph, args.arm))
        elif args.command == "arm-effects":
            _print(effects_for_arm(graph, args.arm))
        elif args.command == "winner-corpus-gap":
            _print({
                "measurements": population_measurements(graph, args.population),
                "populations": sorted(set(args.population)),
            })
        elif args.command == "baseline-compatibility":
            _print(baseline_compatibility(graph, args.left, args.right))
        elif args.command == "decision-brief":
            _print(decision_brief(graph))
        else:  # pragma: no cover - argparse owns the command domain
            raise AssertionError(args.command)
        return 0
    except (EvidenceGraphError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
