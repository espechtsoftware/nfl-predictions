#!/usr/bin/env python3
"""Build the bounded R6 historical graph plan and emit a compact receipt.

This operator is localhost-only.  It reads only caller-selected files, invokes
the fail-closed adapter, and writes one create-once canonical receipt.  It has
no cloud, Docker, Neo4j, outcome-query, scoring, UI, or deployment capability.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Sequence

from nfl_dfs.research import corpus_r6_historical_neo4j_slice_v1 as historical


RECEIPT_SCHEMA = "corpus-r6-historical-neo4j-slice-local-receipt/v1"


def _object(path: Path, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} could not be read as JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must be one JSON object: {path}")
    return value


def _inputs(
    *,
    staging_dir: Path,
    candidate_identity: dict[str, object],
    funnel_identity: dict[str, object],
) -> tuple[
    list[historical.ExactJsonFileV1],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    candidate_path = staging_dir / "candidate-authority-release-v2.json"
    catalog_path = (
        staging_dir / "fixed-g0-catalog-recovery-attestation-v2.json"
    )
    funnel_path = staging_dir / "no-rescore-funnel-release.json"
    candidate = _object(candidate_path, label="candidate-v2 terminal root")
    catalog = _object(catalog_path, label="catalog outer attestation")
    funnel = _object(funnel_path, label="no-rescore funnel terminal root")
    catalog_identity = candidate.get("catalog_recovery_outer_identity")
    if not isinstance(catalog_identity, dict):
        raise SystemExit("candidate-v2 root has no catalog outer identity")

    inputs = [
        historical.ExactJsonFileV1(candidate_identity, candidate_path),
        historical.ExactJsonFileV1(catalog_identity, catalog_path),
        historical.ExactJsonFileV1(funnel_identity, funnel_path),
    ]
    for row in candidate.get("non_root_publication_manifest", []):
        if not isinstance(row, dict):
            raise SystemExit("candidate publication manifest row differs")
        role = row.get("role")
        source_ordinal = row.get("source_task_ordinal")
        if role == "candidate_artifact":
            path = staging_dir / "candidate-artifacts" / f"{source_ordinal}.json"
        elif role == "exact_occurrence_lineage_sidecar":
            path = staging_dir / "lineage-sidecars" / f"{source_ordinal}.json"
        else:
            continue
        identity = row.get("identity")
        if not isinstance(identity, dict):
            raise SystemExit(f"candidate {role} identity differs")
        inputs.append(historical.ExactJsonFileV1(identity, path))
    for row in catalog.get("inner_object_manifest", []):
        if not isinstance(row, dict):
            raise SystemExit("catalog inner manifest row differs")
        if row.get("role") != "player_catalog":
            continue
        source_ordinal = row.get("source_task_ordinal")
        identity = row.get("identity")
        if not isinstance(identity, dict):
            raise SystemExit("player catalog identity differs")
        path = (
            staging_dir
            / "player-catalogs-by-slate"
            / f"{source_ordinal}.json"
        )
        inputs.append(historical.ExactJsonFileV1(identity, path))
    predecessors = funnel.get("predecessors")
    if not isinstance(predecessors, dict):
        raise SystemExit("funnel predecessors differ")
    shard_identities = predecessors.get("attribution_shard_identities")
    if not isinstance(shard_identities, list):
        raise SystemExit("funnel attribution shard identities differ")
    shard_paths = sorted((staging_dir / "attribution-shards").glob("*.json"))
    if len(shard_paths) != historical.EXPECTED_SLATE_COUNT:
        raise SystemExit("staged attribution shard file census differs")
    for identity, path in zip(shard_identities, shard_paths, strict=True):
        if not isinstance(identity, dict):
            raise SystemExit("funnel attribution shard identity differs")
        inputs.append(historical.ExactJsonFileV1(identity, path))
    if len(inputs) != historical.EXPECTED_EXACT_OBJECT_COUNT:
        raise SystemExit("local exact object input census differs")
    return inputs, candidate_identity, catalog_identity, funnel_identity


def _receipt(
    plan: historical.HistoricalNeo4jGraphPlanV1,
    *,
    candidate_identity: dict[str, object],
    catalog_identity: dict[str, object],
    funnel_identity: dict[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "evidence_class": historical.EVIDENCE_CLASS,
        "threshold_dk": historical.THRESHOLD_DK,
        "source_root_identities": {
            "candidate_v2": candidate_identity,
            "catalog_outer": catalog_identity,
            "no_rescore_funnel": funnel_identity,
        },
        "source_object_count": plan.manifest["source_object_count"],
        "source_object_manifest_sha256": plan.manifest[
            "source_object_manifest_sha256"
        ],
        "source_row_digest_manifest_sha256": plan.manifest[
            "source_row_digest_manifest_sha256"
        ],
        "reconciliation": plan.manifest["reconciliation"],
        "node_count": len(plan.nodes),
        "node_kinds": dict(sorted(Counter(
            str(row["kind"]) for row in plan.nodes
        ).items())),
        "node_rows_sha256": plan.manifest["node_rows_sha256"],
        "relationship_count": len(plan.relationships),
        "relationship_types": dict(sorted(Counter(
            str(row["relationship_type"]) for row in plan.relationships
        ).items())),
        "relationship_rows_sha256": plan.manifest[
            "relationship_rows_sha256"
        ],
        "manifest_sha256": plan.manifest["manifest_sha256"],
        "plan_sha256": plan.plan_sha256,
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "winner_nodes_included": False,
        "official_claims_included": False,
        "world_matrix_bodies_included": False,
        "neo4j_mutation_performed": False,
        "network_access_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "complete": True,
    }
    body["receipt_sha256"] = historical.canonical_sha256(body)
    return body


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--candidate-root-identity", type=Path, required=True)
    parser.add_argument("--funnel-reopen-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    staging_dir = args.staging_dir.resolve(strict=True)
    candidate_identity = _object(
        args.candidate_root_identity.resolve(strict=True),
        label="candidate root identity",
    )
    funnel_summary = _object(
        args.funnel_reopen_summary.resolve(strict=True),
        label="funnel reopen summary",
    )
    funnel_identity = funnel_summary.get("funnel_release_identity")
    if not isinstance(funnel_identity, dict):
        raise SystemExit("funnel reopen summary has no release identity")
    inputs, candidate_identity, catalog_identity, funnel_identity = _inputs(
        staging_dir=staging_dir,
        candidate_identity=candidate_identity,
        funnel_identity=funnel_identity,
    )
    plan = historical.build_historical_corpus_graph_plan_v1(
        exact_objects=inputs,
        candidate_root_identity=candidate_identity,
        catalog_outer_identity=catalog_identity,
        attribution_root_identity=funnel_identity,
    )
    receipt = _receipt(
        plan,
        candidate_identity=candidate_identity,
        catalog_identity=catalog_identity,
        funnel_identity=funnel_identity,
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as handle:
            handle.write(historical.canonical_json_bytes(receipt))
            handle.write(b"\n")
    except FileExistsError as exc:
        raise SystemExit(f"refusing to overwrite local receipt: {output}") from exc
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
