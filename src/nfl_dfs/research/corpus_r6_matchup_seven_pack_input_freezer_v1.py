"""Local freezer for the terminal-bound seven-pack capture request.

The normalized FP/SIS snapshot is the only paid-pack input.  This module does
not accept reconstructed rows, shards, or loose manifest identities.  It
freezes one candidate-authority-v2 root identity and one normalized-snapshot
terminal identity into the guarded seven-pack request; task-0 and publication
must independently deep-reopen the terminal before deriving its manifests.
"""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_operator_v1 as operator
from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


FREEZE_SPEC_SCHEMA: Final = "corpus-r6-matchup-seven-pack-input-freeze-spec/v2"
REQUEST_IDENTITY_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-local-request-identity/v2"
)
FREEZE_RECEIPT_SCHEMA: Final = "corpus-r6-matchup-seven-pack-input-freeze/v2"
FREEZE_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SEVEN_PACK_INPUT_FREEZE"
ENABLE_VALUE: Final = "1"


class CorpusR6MatchupSevenPackInputFreezerV1Error(ValueError):
    """The local seven-pack request freeze failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSevenPackInputFreezerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def freeze_seven_pack_inputs_v1(*, spec_value: object) -> dict[str, object]:
    """Freeze a request without reading or publishing any external object."""

    spec = _mapping(spec_value, label="seven-pack freeze spec")
    if set(spec) != {
        "schema_version", "run_id", "candidate_authority_v2_root_identity",
        "normalized_snapshot_terminal_identity",
    }:
        _fail("seven-pack freeze spec fields differ")
    if spec.get("schema_version") != FREEZE_SPEC_SCHEMA:
        _fail("seven-pack freeze spec schema differs")
    try:
        request = operator.build_capture_request_v1(
            run_id=spec["run_id"],
            candidate_authority_v2_root_identity=spec[
                "candidate_authority_v2_root_identity"
            ],
            normalized_snapshot_terminal_identity=spec[
                "normalized_snapshot_terminal_identity"
            ],
        )
    except (
        operator.CorpusR6MatchupSevenPackCaptureOperatorV1Error,
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
    ) as exc:
        raise CorpusR6MatchupSevenPackInputFreezerV1Error(str(exc)) from exc
    request_raw = source.canonical_json_bytes(request)
    request_identity_body: dict[str, object] = {
        "schema_version": REQUEST_IDENTITY_SCHEMA,
        "relative_path": "seven-pack-request.json",
        "sha256": sha256(request_raw).hexdigest(),
        "bytes": len(request_raw),
        "capture_request_sha256": request["capture_request_sha256"],
        "candidate_authority_v2_root_identity": request[
            "candidate_authority_v2_root_identity"
        ],
        "normalized_snapshot_terminal_identity": request[
            "normalized_snapshot_terminal_identity"
        ],
        "artifact_manifest_identities_accepted_from_caller": False,
        "normalized_snapshot_deep_reopen_required": True,
        "local_only": True,
        "cloud_generation_assigned": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    request_identity_body["request_identity_sha256"] = source.canonical_sha256(
        request_identity_body
    )
    files: dict[str, bytes] = {
        "seven-pack-request.json": request_raw,
        "seven-pack-request.identity.json": source.canonical_json_bytes(
            request_identity_body
        ),
    }
    output_manifest = [
        {"relative_path": path, "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}
        for path, raw in sorted(files.items())
    ]
    receipt: dict[str, object] = {
        "schema_version": FREEZE_RECEIPT_SCHEMA,
        "run_id": request["run_id"],
        "candidate_authority_v2_root_identity": request[
            "candidate_authority_v2_root_identity"
        ],
        "normalized_snapshot_terminal_identity": request[
            "normalized_snapshot_terminal_identity"
        ],
        "warehouse_query_pack_ids": list(capture.WAREHOUSE_PACK_IDS),
        "artifact_pack_ids": list(capture.ARTIFACT_PACK_IDS),
        "capture_request_sha256": request["capture_request_sha256"],
        "request_identity_sha256": request_identity_body[
            "request_identity_sha256"
        ],
        "output_file_manifest": output_manifest,
        "output_file_manifest_sha256": source.canonical_sha256(output_manifest),
        "output_file_count_excluding_receipt": len(output_manifest),
        "artifact_manifest_identities_accepted_from_caller": False,
        "normalized_snapshot_deep_reopen_required": True,
        "cloud_object_existence_verified": False,
        "external_read_count": 0,
        "cloud_write_count": 0,
        "outcome_body_read_count": 0,
        "world_body_read_count": 0,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "complete": True,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    receipt["freeze_receipt_sha256"] = source.canonical_sha256(receipt)
    files["freeze-receipt.json"] = source.canonical_json_bytes(receipt)
    return {"receipt": receipt, "files": files}


__all__ = [
    "ENABLE_VALUE",
    "FREEZE_ENABLE_ENV",
    "FREEZE_RECEIPT_SCHEMA",
    "FREEZE_SPEC_SCHEMA",
    "REQUEST_IDENTITY_SCHEMA",
    "CorpusR6MatchupSevenPackInputFreezerV1Error",
    "freeze_seven_pack_inputs_v1",
]
