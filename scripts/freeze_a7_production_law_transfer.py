#!/usr/bin/env python3
"""Create the immutable execution freeze for the conditional A7 transfer.

This command is score-free.  Its first gate is the exact final positive A7
closure; only after that local validation may it construct a storage client,
generation-pin the smoke/support objects, or create the freeze object.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from google.cloud import storage


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from nfl_dfs.research import a7_production_law_transfer as science  # noqa: E402

import run_a7_production_law_transfer as runner  # noqa: E402
from run_cbwu_seed_order_audit import _upload_create_only  # noqa: E402


def build_manifest(
    *,
    predecessor: Mapping[str, Any],
    code_sha: str,
    image: str,
    candidate_query_sha256: str,
    player_query_sha256: str,
    smoke_object: Mapping[str, Any],
    support_object: Mapping[str, Any],
) -> dict[str, Any]:
    """Build and replay-validate the exact fail-closed freeze body."""
    manifest = {
        "version": runner.FREEZE_MANIFEST_VERSION,
        "status": "frozen-for-one-scorefree-transfer",
        "run_id": runner.RUN_ID,
        "protocol_id": science.PROTOCOL_ID,
        "protocol_sha256": runner.PROTOCOL_SHA256,
        "code_sha": code_sha,
        "image": image,
        "predecessor_license": dict(predecessor),
        "frozen_law": runner.FROZEN_LAW,
        "implementation_sha256": runner._implementation_receipts(),
        "source_query_sha256": {
            "candidates": candidate_query_sha256,
            "players": player_query_sha256,
        },
        "preflights": {
            "smoke": dict(smoke_object),
            "support": dict(support_object),
        },
        "support_passed": True,
        "full_execution_licensed": True,
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "historical_outcome_lease_acquired": False,
        "production_mutated": False,
        "shadow_deployment_licensed": False,
        "licenses": science.licenses(),
    }
    runner._validate_freeze_manifest(
        manifest,
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        candidate_query_sha256=candidate_query_sha256,
        player_query_sha256=player_query_sha256,
    )
    return manifest


def freeze(
    *,
    output_uri: str,
    code_sha: str,
    image: str,
    candidate_query_sha256: str,
    player_query_sha256: str,
    smoke_generation: str,
    smoke_sha256: str,
    smoke_bytes: int | None,
    support_generation: str,
    support_sha256: str,
    support_bytes: int | None,
    a7_out: Path = runner.A7_OUT,
) -> dict[str, Any]:
    if output_uri != runner.FREEZE_MANIFEST_URI:
        raise RuntimeError("A7 production-law freeze output URI differs")

    # Load-bearing order: no storage client, object read, or create-only write
    # may precede this exact final predecessor validation.
    predecessor = runner.validate_a7_positive_license(a7_out)
    runner._validate_protocol()
    runner.validate_scorefree_queries()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ) is None or any(
        re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in (candidate_query_sha256, player_query_sha256)
    ):
        raise RuntimeError("A7 production-law freeze execution identity differs")

    smoke_identity = runner._object_identity(
        uri=runner.SMOKE_OUTPUT_URI,
        generation=smoke_generation,
        digest=smoke_sha256,
        byte_count=smoke_bytes,
    )
    support_identity = runner._object_identity(
        uri=runner.SUPPORT_OUTPUT_URI,
        generation=support_generation,
        digest=support_sha256,
        byte_count=support_bytes,
    )

    gcs = storage.Client(project=runner.PROJECT)
    _smoke, smoke_object = runner._load_pinned_preflight(
        gcs,
        smoke_identity,
        uri=runner.SMOKE_OUTPUT_URI,
        mode="real-artifact-smoke",
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        expected_candidate_sha256=candidate_query_sha256,
        expected_player_sha256=player_query_sha256,
        expected_preflight_receipts={},
    )
    _support, support_object = runner._load_pinned_preflight(
        gcs,
        support_identity,
        uri=runner.SUPPORT_OUTPUT_URI,
        mode="support-census",
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        expected_candidate_sha256=candidate_query_sha256,
        expected_player_sha256=player_query_sha256,
        expected_preflight_receipts={"smoke": smoke_object},
    )
    manifest = build_manifest(
        predecessor=predecessor,
        code_sha=code_sha,
        image=image,
        candidate_query_sha256=candidate_query_sha256,
        player_query_sha256=player_query_sha256,
        smoke_object=smoke_object,
        support_object=support_object,
    )
    payload = runner._canonical_json(manifest)
    uploaded = _upload_create_only(gcs, output_uri, payload)
    replay, replay_object = runner._a7_download_json_object_pinned(
        gcs,
        {
            key: uploaded[key]
            for key in ("uri", "generation", "sha256", "bytes")
        },
    )
    if replay != manifest or replay_object != {
        "uri": uploaded["uri"],
        "generation": uploaded["generation"],
        "sha256": uploaded["sha256"],
        "bytes": uploaded["bytes"],
        "metageneration": "1",
    }:
        raise RuntimeError("A7 production-law freeze changed after creation")
    return {"manifest": manifest, "object": replay_object}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--candidate-query-sha256", required=True)
    parser.add_argument("--player-query-sha256", required=True)
    parser.add_argument("--smoke-generation", required=True)
    parser.add_argument("--smoke-sha256", required=True)
    parser.add_argument("--smoke-bytes", type=int)
    parser.add_argument("--support-generation", required=True)
    parser.add_argument("--support-sha256", required=True)
    parser.add_argument("--support-bytes", type=int)
    parser.add_argument("--a7-output-dir", type=Path, default=runner.A7_OUT)
    args = parser.parse_args()
    result = freeze(
        output_uri=args.output_uri,
        code_sha=args.code_sha,
        image=args.image,
        candidate_query_sha256=args.candidate_query_sha256,
        player_query_sha256=args.player_query_sha256,
        smoke_generation=args.smoke_generation,
        smoke_sha256=args.smoke_sha256,
        smoke_bytes=args.smoke_bytes,
        support_generation=args.support_generation,
        support_sha256=args.support_sha256,
        support_bytes=args.support_bytes,
        a7_out=args.a7_output_dir,
    )
    print(json.dumps(result["object"], sort_keys=True))


if __name__ == "__main__":
    main()
