#!/usr/bin/env python3
"""Create one bounded historical-realized E0 aggregate artifact.

This localhost-only operator rebuilds the accepted E0 graph plan from the
same caller-selected 219 immutable objects used by the existing E0 runner,
then delegates all binding and aggregate validation to the production summary
core.  It has no Neo4j, network, cloud, scoring, UI, or deployment capability.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

from nfl_dfs.research import corpus_r6_historical_neo4j_slice_v1 as historical
from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as summary_v1

if __package__:
    from scripts import run_corpus_r6_historical_neo4j_slice_v1 as e0_runner
else:  # Direct ``python scripts/...`` execution puts scripts/ on sys.path.
    import run_corpus_r6_historical_neo4j_slice_v1 as e0_runner


RUN_RESULT_SCHEMA = "corpus-r6-historical-realized-summary-run-result/v1"


def _read_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise SystemExit(f"{label} could not be read: {path}") from exc


def _object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} is not one JSON object") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{label} is not one JSON object")
    return value


def _root_identity(receipt: dict[str, object], *, role: str) -> dict[str, object]:
    roots = receipt.get("source_root_identities")
    if not isinstance(roots, dict):
        raise SystemExit("accepted E0 receipt has no source root identities")
    identity = roots.get(role)
    if not isinstance(identity, dict):
        raise SystemExit(f"accepted E0 receipt has no {role} identity")
    return identity


def _build_summary(
    *, staging_dir: Path, accepted_e0_receipt_path: Path
) -> dict[str, object]:
    receipt_raw = _read_bytes(accepted_e0_receipt_path, label="accepted E0 receipt")
    receipt = _object(receipt_raw, label="accepted E0 receipt")
    candidate_identity = _root_identity(receipt, role="candidate_v2")
    funnel_identity = _root_identity(receipt, role="no_rescore_funnel")

    inputs, candidate_identity, catalog_identity, funnel_identity = e0_runner._inputs(
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
    funnel_raw = _read_bytes(
        staging_dir / "no-rescore-funnel-release.json",
        label="no-rescore funnel release",
    )
    return summary_v1.build_historical_realized_summary_v1(
        accepted_e0_receipt_raw=receipt_raw,
        no_rescore_funnel_raw=funnel_raw,
        e0_plan=plan,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--accepted-e0-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    staging_dir = args.staging_dir.resolve(strict=True)
    accepted_receipt = args.accepted_e0_receipt.resolve(strict=True)
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        raise SystemExit(f"refusing to overwrite summary artifact: {output}")

    summary = _build_summary(
        staging_dir=staging_dir,
        accepted_e0_receipt_path=accepted_receipt,
    )
    summary = summary_v1.validate_historical_realized_summary_v1(summary)
    raw = summary_v1.canonical_json_bytes(summary) + b"\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("xb") as handle:
            handle.write(raw)
    except FileExistsError as exc:
        raise SystemExit(f"refusing to overwrite summary artifact: {output}") from exc

    result = {
        "schema_version": RUN_RESULT_SCHEMA,
        "artifact_path": str(output),
        "artifact_bytes": len(raw),
        "artifact_file_sha256": sha256(raw).hexdigest(),
        "summary_sha256": summary["summary_sha256"],
        "source_object_count": summary["source_binding"]["source_object_count"],
        "neo4j_access_performed": False,
        "network_access_performed": False,
        "scoring_performed": False,
        "promotion_authority": False,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
