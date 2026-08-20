#!/usr/bin/env python3
"""Create the immutable A7 freeze manifest from strict preflight evidence.

This command is outcome-blind. It generation-pins the durable job claim,
science receipts, and terminal execution receipts; independently reconstructs
the clean source archive; and creates exactly one freeze manifest.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

from google.cloud import storage


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "scripts", ROOT / "src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import finish_a7_select_ladder as transport  # noqa: E402
import run_a7_select_ladder as a7  # noqa: E402


OPERATOR_APPROVAL_BASIS = (
    "user-authorized-proof-before-adoption-implementation-2026-08-20"
)
OBJECT_KEYS = frozenset({
    "uri", "generation", "metageneration", "bytes", "sha256",
})


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n"
    ).encode("utf-8")


def _identity(
    uri: str, generation: str, digest: str, byte_count: int,
) -> dict[str, Any]:
    value = {
        "uri": str(uri),
        "generation": str(generation),
        "metageneration": "1",
        "sha256": str(digest),
        "bytes": int(byte_count),
    }
    if (
        not str(uri).startswith("gs://")
        or re.fullmatch(r"[1-9][0-9]*", value["generation"]) is None
        or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
        or value["bytes"] <= 0
    ):
        raise RuntimeError("A7 immutable object identity differs")
    return value


def _git_archive_sha256(code_sha: str) -> str:
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None:
        raise RuntimeError("A7 clean archive commit differs")
    raw = subprocess.run(
        ["git", "-C", str(ROOT), "archive", "--format=tar", code_sha],
        check=True, capture_output=True,
    ).stdout
    if not raw:
        raise RuntimeError("A7 clean archive is empty")
    return sha256(raw).hexdigest()


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True, capture_output=True,
    ).stdout


def _validate_object_identity(
    value: object, *, uri: str, label: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != OBJECT_KEYS:
        raise RuntimeError(f"A7 {label} object fields differ")
    if value.get("uri") != uri:
        raise RuntimeError(f"A7 {label} object URI differs")
    transport._metadata_block(value, uri=uri, label=label)
    return dict(value)


def _validate_common_preflight_identity(
    smoke: Mapping[str, Any], support: Mapping[str, Any],
) -> tuple[str, str]:
    shared = (
        "code_sha", "image", "protocol_sha256", "local_source_receipts",
        "implementation_receipts", "query_content_receipts",
        "frozen_choices",
    )
    if any(smoke.get(key) != support.get(key) for key in shared):
        raise RuntimeError("A7 preflight receipts do not share frozen inputs")
    code_sha = str(smoke.get("code_sha", ""))
    image = str(smoke.get("image", ""))
    a7.validate_execution_identity(code_sha, image)
    return code_sha, image


def build_manifest(
    *,
    smoke: dict[str, Any],
    support: dict[str, Any],
    smoke_object: dict[str, Any],
    support_object: dict[str, Any],
    smoke_terminal: dict[str, Any],
    support_terminal: dict[str, Any],
    smoke_terminal_object: dict[str, Any],
    support_terminal_object: dict[str, Any],
    job_claim: dict[str, Any],
    a3_logical_release_sha256: str,
    archive_sha256: str,
) -> dict[str, Any]:
    """Construct and independently validate the exact freeze-manifest body."""
    code_sha, image = _validate_common_preflight_identity(smoke, support)
    actual_archive_sha256 = _git_archive_sha256(code_sha)
    if archive_sha256 != actual_archive_sha256:
        raise RuntimeError("A7 clean archive digest differs")
    a7._validate_smoke_source_identity(code_sha)

    for relative in a7.FREEZE_IMPLEMENTATION_PATHS.values():
        current = (ROOT / relative).read_bytes()
        committed = _git_blob(ROOT, code_sha, str(relative))
        if current != committed:
            raise RuntimeError(f"A7 freeze source differs from commit: {relative}")

    local_source_receipts = a7.verify_local_sha256({
        "protocol": (a7.PROTOCOL_PATH, a7.PROTOCOL_SHA256),
        "source_report": (a7.SOURCE_REPORT_PATH, a7.SOURCE_REPORT_SHA256),
        "baseline": (a7.BASELINE_PATH, a7.BASELINE_SHA256),
        "baseline_vector": (
            a7.BASELINE_VECTOR_PATH, a7.BASELINE_VECTOR_SHA256,
        ),
    })
    implementation_sha256 = a7._freeze_implementation_receipts()
    _, source_map, _ = a7._source_report()
    source_artifacts = a7._locked_source_artifacts(source_map)
    source_lock_sha256 = sha256(json.dumps(
        source_artifacts, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    if support.get("source_artifacts_sha256") != source_lock_sha256:
        raise RuntimeError("A7 support source-artifact lock differs")

    claim_body = job_claim.get("claim") if isinstance(job_claim, dict) else None
    if not isinstance(claim_body, dict):
        raise RuntimeError("A7 durable job claim differs")
    claim = transport._validate_job_claim_receipt(
        job_claim, code_sha=code_sha, image=image,
        protocol_sha256=a7.PROTOCOL_SHA256,
        a3_logical_release_sha256=a3_logical_release_sha256,
    )
    smoke_object = _validate_object_identity(
        smoke_object, uri=a7.SMOKE_RECEIPT_URI, label="smoke preflight",
    )
    support_object = _validate_object_identity(
        support_object, uri=a7.SUPPORT_RECEIPT_URI, label="support preflight",
    )
    smoke_terminal_object = _validate_object_identity(
        smoke_terminal_object, uri=a7.SMOKE_TERMINAL_URI,
        label="smoke terminal",
    )
    support_terminal_object = _validate_object_identity(
        support_terminal_object, uri=a7.SUPPORT_TERMINAL_URI,
        label="support terminal",
    )
    claim_metadata = {
        key: value for key, value in claim["object"].items()
        if key != "create_only"
    }
    smoke_inventory = [
        claim_metadata, smoke_object, smoke_terminal_object,
    ]
    support_inventory = [
        *smoke_inventory, support_object, support_terminal_object,
    ]

    manifest = {
        "version": a7.FREEZE_MANIFEST_VERSION,
        "status": "frozen-for-one-historical-look",
        "run_id": a7.RUN_ID,
        "protocol_id": a7.PROTOCOL_ID,
        "protocol": {
            "path": str(a7.PROTOCOL_PATH), "sha256": a7.PROTOCOL_SHA256,
        },
        "code": {
            "commit_sha": code_sha,
            "archive_sha256": actual_archive_sha256,
        },
        "image": {"uri": image},
        "operator_approved": True,
        "operator_approval_basis": OPERATOR_APPROVAL_BASIS,
        "operator_approvals": a7.OPERATOR_APPROVALS,
        "frozen_law": a7.FROZEN_CHOICES,
        "implementation_sha256": implementation_sha256,
        "local_source_receipts": local_source_receipts,
        "query_content_receipts": smoke["query_content_receipts"],
        "source_report": {
            "path": str(a7.SOURCE_REPORT_PATH),
            "sha256": a7.SOURCE_REPORT_SHA256,
        },
        "baseline": {
            "path": str(a7.BASELINE_PATH), "sha256": a7.BASELINE_SHA256,
        },
        "baseline_vector": {
            "path": str(a7.BASELINE_VECTOR_PATH),
            "sha256": a7.BASELINE_VECTOR_SHA256,
        },
        "source_artifacts": source_artifacts,
        "source_artifact_lock_sha256": source_lock_sha256,
        "preflights": {
            "smoke": {
                "science": smoke_object,
                "terminal": smoke_terminal_object,
            },
            "support": {
                "science": support_object,
                "terminal": support_terminal_object,
            },
        },
        "job_claim": claim,
        "prefix_inventory_sha256": {
            "claimed": transport._inventory_sha256([claim_metadata]),
            "smoke-complete": transport._inventory_sha256(smoke_inventory),
            "support-complete": transport._inventory_sha256(
                support_inventory,
            ),
        },
        "historical_looks": 1,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "production_law_scorefree_transfer_licensed": False,
        "prospective_shadow_licensed": False,
    }
    if set(manifest) != transport.FREEZE_MANIFEST_KEYS:
        raise RuntimeError("A7 freeze manifest field population differs")

    a7._validate_preflight_receipt(
        smoke, mode="real-artifact-smoke", manifest=manifest,
    )
    a7._validate_preflight_receipt(
        support, mode="support-census", manifest=manifest,
    )
    if support.get("support", {}).get("passes") is not True:
        raise RuntimeError("A7 support census is unsupported; freeze is forbidden")
    validated_smoke_terminal = transport._validate_preflight_terminal_receipt(
        smoke_terminal, mode="real-artifact-smoke",
        science_object=smoke_object, claim=claim, code_sha=code_sha,
        image=image, protocol_sha256=a7.PROTOCOL_SHA256,
        a3_logical_release_sha256=a3_logical_release_sha256,
    )
    validated_support_terminal = transport._validate_preflight_terminal_receipt(
        support_terminal, mode="support-census",
        science_object=support_object, claim=claim, code_sha=code_sha,
        image=image, protocol_sha256=a7.PROTOCOL_SHA256,
        a3_logical_release_sha256=a3_logical_release_sha256,
        prior_science_object=smoke_object,
        prior_terminal_object=smoke_terminal_object,
    )
    if validated_support_terminal.get("support_passed") is not True:
        raise RuntimeError("A7 unsupported terminal receipt forbids freeze")
    if any(
        terminal["execution"].get("job_uid") != claim["claim"].get("job_uid")
        for terminal in (validated_smoke_terminal, validated_support_terminal)
    ):
        raise RuntimeError("A7 preflight terminal job identity differs")
    smoke_execution = validated_smoke_terminal["execution"]
    support_execution = validated_support_terminal["execution"]
    if (
        smoke_execution["prior_job_generation"]
        != claim["claim"]["job_generation"]
        or smoke_execution["prior_job_spec_sha256"]
        != claim["claim"]["job_spec_sha256"]
        or support_execution["prior_job_generation"]
        != smoke_execution["job_generation"]
        or support_execution["prior_job_spec_sha256"]
        != smoke_execution["job_spec_sha256"]
    ):
        raise RuntimeError("A7 preflight job-generation chain differs")

    transport._validate_freeze_manifest(
        manifest, expected_code_sha=code_sha, expected_image=image, root=ROOT,
        git_source_loader=_git_blob,
    )
    _canonical_json(manifest)
    return manifest


def _download(
    client: storage.Client, *, uri: str, generation: str, digest: str,
    byte_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    return a7._download_json_object_pinned(
        client, _identity(uri, generation, digest, byte_count),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    for label in (
        "job-claim", "smoke", "smoke-terminal", "support",
        "support-terminal",
    ):
        parser.add_argument(f"--{label}-uri", required=True)
        parser.add_argument(f"--{label}-generation", required=True)
        parser.add_argument(f"--{label}-sha256", required=True)
        parser.add_argument(f"--{label}-bytes", required=True, type=int)
    parser.add_argument("--a3-logical-release", required=True, type=Path)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--archive-sha256", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    expected_uris = {
        "job_claim": a7.JOB_CLAIM_URI,
        "smoke": a7.SMOKE_RECEIPT_URI,
        "smoke_terminal": a7.SMOKE_TERMINAL_URI,
        "support": a7.SUPPORT_RECEIPT_URI,
        "support_terminal": a7.SUPPORT_TERMINAL_URI,
    }
    supplied_uris = {
        "job_claim": args.job_claim_uri,
        "smoke": args.smoke_uri,
        "smoke_terminal": args.smoke_terminal_uri,
        "support": args.support_uri,
        "support_terminal": args.support_terminal_uri,
    }
    if supplied_uris != expected_uris or args.output_uri != a7.FREEZE_MANIFEST_URI:
        raise RuntimeError("A7 immutable preflight/freeze URI differs")

    client = storage.Client(project=a7.PROJECT)
    loaded: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for label in expected_uris:
        loaded[label] = _download(
            client, uri=getattr(args, f"{label}_uri"),
            generation=getattr(args, f"{label}_generation"),
            digest=getattr(args, f"{label}_sha256"),
            byte_count=getattr(args, f"{label}_bytes"),
        )

    release = transport._validate_a3_release(args.a3_logical_release)
    release_sha256 = sha256(args.a3_logical_release.read_bytes()).hexdigest()
    raw_claim, claim_object = loaded["job_claim"]
    job_claim = {
        "claim": raw_claim,
        "object": {**claim_object, "create_only": True},
    }
    manifest = build_manifest(
        smoke=loaded["smoke"][0],
        support=loaded["support"][0],
        smoke_object=loaded["smoke"][1],
        support_object=loaded["support"][1],
        smoke_terminal=loaded["smoke_terminal"][0],
        support_terminal=loaded["support_terminal"][0],
        smoke_terminal_object=loaded["smoke_terminal"][1],
        support_terminal_object=loaded["support_terminal"][1],
        job_claim=job_claim,
        a3_logical_release_sha256=release_sha256,
        archive_sha256=args.archive_sha256,
    )
    if release.get("next_run_id") != manifest["run_id"]:
        raise RuntimeError("A7 A3 release does not name the frozen run")
    payload = _canonical_json(manifest)
    uploaded = a7._upload_create_only(client, args.output_uri, payload)
    reopened, reopened_object = a7._download_json_object_pinned(
        client, {
            "uri": args.output_uri,
            "generation": uploaded["generation"],
            "sha256": uploaded["sha256"],
            "bytes": uploaded["bytes"],
            "metageneration": "1",
        },
    )
    if reopened != manifest:
        raise RuntimeError("A7 freeze manifest changed after create-only upload")
    print(json.dumps({
        "manifest": manifest,
        "object": reopened_object,
        "payload_sha256": sha256(payload).hexdigest(),
    }, sort_keys=True, separators=(",", ":"), allow_nan=False))


if __name__ == "__main__":
    main()
