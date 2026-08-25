"""Pure accepted-slate orchestration for the extreme-tail support census.

The caller exact-reads one member of the complete Foundry v12 panel through
the shared compatibility reconstruction seam, builds the outcome-blind support
census, and replays it byte-for-byte.  It owns no CLI, storage client,
publisher, outcome reader, graph mutation, retry, or promotion authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as accepted
from nfl_dfs.research import residual_world_columns as rw


RESULT_SCHEMA: Final = "corpus-extreme-tail-one-slate-execution/v1"
_FALSE_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)


class CorpusExtremeTailOneSlateExecutionError(ValueError):
    """The accepted-slate census cannot run without weakening its bindings."""


def _fail(message: str) -> None:
    raise CorpusExtremeTailOneSlateExecutionError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _world_id(value: object, *, label: str) -> dict[str, object]:
    if isinstance(value, Mapping):
        block = value.get("block")
        index = value.get("index")
    else:
        block = getattr(value, "block", None)
        index = getattr(value, "index", None)
    if block not in rw.WORLD_BLOCKS or type(index) is not int or index < 0:
        _fail(f"{label} is not a canonical R-world identity")
    return {"block": str(block), "index": index}


def execute_one_slate_extreme_tail_census(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    read_exact: accepted.ReadExact,
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Reconstruct and replay one exact outcome-blind support census."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if require_authoritative and worlds_per_block is not None:
        _fail("authoritative one-slate census cannot override registered doses")
    try:
        reconstructed_slate = accepted.reconstruct_one_accepted_v12_slate(
            validated_panel_index=validated_panel_index,
            panel_index_identity=panel_index_identity,
            accepted_slate_membership=accepted_slate_membership,
            task_acceptance_identity=task_acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=read_exact,
            require_authoritative=require_authoritative,
        )
    except accepted.CorpusR6V2OneSlateExecutionError as exc:
        raise CorpusExtremeTailOneSlateExecutionError(str(exc)) from exc

    reconstructed = reconstructed_slate.reconstructed
    raw_world_ids = _sequence(
        getattr(reconstructed.prepared, "world_ids", None),
        label="reconstructed world IDs",
    )
    world_ids = [
        _world_id(value, label=f"reconstructed world ID[{ordinal}]")
        for ordinal, value in enumerate(raw_world_ids)
    ]
    try:
        support_census = census.build_extreme_tail_support_census(
            provenance=reconstructed.provenance,
            union_scores=reconstructed.union_scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            world_ids=world_ids,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
        replayed = census.validate_extreme_tail_support_census(
            support_census,
            provenance=reconstructed.provenance,
            union_scores=reconstructed.union_scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            world_ids=world_ids,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except census.CorpusExtremeTailCensusError as exc:
        raise CorpusExtremeTailOneSlateExecutionError(str(exc)) from exc

    import_receipt = _mapping(
        reconstructed_slate.imported.compatibility_receipt,
        label="v12 compatibility import",
    )
    provenance = _mapping(
        reconstructed.provenance, label="reconstructed provenance"
    )
    reconstruction_receipt = _mapping(
        reconstructed.reconstruction_receipt,
        label="reconstruction receipt",
    )
    matrix_binding = _mapping(
        reconstruction_receipt.get("matrix_binding"),
        label="reconstruction matrix binding",
    )
    retained_census = _mapping(replayed, label="replayed support census")
    census_input = _mapping(
        retained_census.get("input_binding"), label="census input binding"
    )
    world_basis = _mapping(
        retained_census.get("world_basis"), label="census world basis"
    )
    expected_worlds_per_block = (
        rw.WORLDS_PER_BLOCK
        if worlds_per_block is None
        else worlds_per_block
    )
    if (
        retained_census.get("schema_version") != census.CENSUS_SCHEMA
        or retained_census.get("slate", {}).get("slate_id")
        != reconstructed_slate.slate_id
        or retained_census.get("require_authoritative")
        is not require_authoritative
        or retained_census.get("uses_realized_outcomes") is not False
        or retained_census.get("promotion_authority") is not False
        or world_basis.get("worlds_per_block") != expected_worlds_per_block
        or census_input.get("reconstruction_sha256")
        != reconstruction_receipt.get("reconstruction_sha256")
        or census_input.get("candidate_provenance_sha256")
        != provenance.get("candidate_provenance_sha256")
        or census_input.get("matrix_binding_sha256")
        != matrix_binding.get("matrix_binding_sha256")
    ):
        _fail("replayed support census differs from accepted reconstruction")

    output_hashes = {
        "compatibility_import_sha256": _sha(
            import_receipt.get("compatibility_import_sha256"),
            label="compatibility import SHA",
        ),
        "candidate_provenance_sha256": _sha(
            provenance.get("candidate_provenance_sha256"),
            label="candidate provenance SHA",
        ),
        "reconstruction_sha256": _sha(
            reconstruction_receipt.get("reconstruction_sha256"),
            label="reconstruction SHA",
        ),
        "matrix_binding_sha256": _sha(
            matrix_binding.get("matrix_binding_sha256"),
            label="matrix binding SHA",
        ),
        "score_matrix_sha256": _sha(
            matrix_binding.get("score_matrix_sha256"),
            label="score matrix SHA",
        ),
        "support_census_sha256": _sha(
            retained_census.get("support_census_sha256"),
            label="support census SHA",
        ),
    }
    membership = dict(reconstructed_slate.accepted_slate_membership)
    world_artifacts = dict(reconstructed_slate.world_artifact_identities)
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "execution_mode": (
            "authoritative-dose-one-slate-outcome-blind-smoke"
            if require_authoritative
            else "non-authoritative-fixture-smoke"
        ),
        "slate_id": reconstructed_slate.slate_id,
        "panel_index_identity": reconstructed_slate.panel_index_identity,
        "panel_index_sha256": reconstructed_slate.panel_index_sha256,
        "accepted_slate_membership": membership,
        "accepted_slate_membership_sha256": batch.canonical_sha256(membership),
        "task_acceptance_identity": (
            reconstructed_slate.task_acceptance_identity
        ),
        "carrier_identity": reconstructed_slate.carrier_identity,
        "later_source_freeze_identity": (
            reconstructed_slate.later_source_freeze_identity
        ),
        "world_artifact_identities": world_artifacts,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            world_artifacts
        ),
        "configuration": {
            "worlds_per_block": expected_worlds_per_block,
            "require_authoritative": require_authoritative,
        },
        "verification": {
            "panel_content_identity_verified": True,
            "panel_membership_binding_verified": True,
            "task_acceptance_content_identity_verified": True,
            "task_acceptance_carrier_binding_verified": True,
            "carrier_source_receipts_verified": True,
            "canonical_reconstruction_verified": True,
            "support_census_canonical_replay_verified": True,
            "canonical_authoritative_dose_verified": require_authoritative,
        },
        "output_hashes": output_hashes,
        "reconstruction_receipt": dict(reconstruction_receipt),
        "support_census": dict(retained_census),
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["one_slate_execution_sha256"] = batch.canonical_sha256(body)
    return body


__all__ = [
    "CorpusExtremeTailOneSlateExecutionError",
    "RESULT_SCHEMA",
    "execute_one_slate_extreme_tail_census",
]
