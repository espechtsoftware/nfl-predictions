"""Pure one-slate orchestration for an outcome-blind R6-v2 mechanics smoke.

This module owns no CLI, storage client, publisher, cloud operation, outcome
reader, or promotion decision.  It exact-reads one already-validated combined
panel member and every reconstruction input reachable from that member's
accepted carrier, then delegates scientific validation and computation to the
v12 importer and R6-v2 runner.

The currently available matchup export may be retrospective rather than a
proved point-in-time-at-lock source.  Such an input is explicitly classified
as mechanics-only and can never grant R6 freeze or promotion authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Final

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw


RESULT_SCHEMA: Final = "corpus-r6-v2-one-slate-execution/v1"
FIXTURE_PANEL_SCHEMA: Final = "foundry-v12-combined-panel-index-fixture/v1"
FIXTURE_PUBLICATION_MODE: Final = "fixture-only"
MATCHUP_EVIDENCE_PIT: Final = "validated-pit-at-lock"
MATCHUP_EVIDENCE_RETROSPECTIVE: Final = "non-pit-retrospective-mechanics-only"
MATCHUP_EVIDENCE_CLASSES: Final = (
    MATCHUP_EVIDENCE_PIT,
    MATCHUP_EVIDENCE_RETROSPECTIVE,
)
_FALSE_PANEL_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_FALSE_RESULT_AUTHORITY_FIELDS: Final = (
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


class CorpusR6V2OneSlateExecutionError(ValueError):
    """One-slate execution cannot proceed without weakening its bindings."""


ReadExact = Callable[[Mapping[str, object]], bytes]


@dataclass(frozen=True)
class AcceptedV12SlateReconstruction:
    """Exact accepted-slate bindings plus the canonical v12 reconstruction."""

    slate_id: str
    panel_index_identity: Mapping[str, object]
    panel_index_sha256: str
    accepted_slate_membership: Mapping[str, object]
    task_acceptance_identity: Mapping[str, object]
    carrier_identity: Mapping[str, object]
    later_source_freeze_identity: Mapping[str, object]
    world_artifact_identities: Mapping[str, Mapping[str, object]]
    imported: v12_import.V12ImportedTask
    reconstructed: v12_import.V12ReconstructedTask


@dataclass(frozen=True)
class _ResolvedAcceptedV12Slate:
    slate_id: str
    panel_index_identity: Mapping[str, object]
    panel_index_sha256: str
    accepted_slate_membership: Mapping[str, object]
    task_acceptance_identity: Mapping[str, object]
    carrier_identity: Mapping[str, object]
    later_source_freeze_identity: Mapping[str, object]
    world_artifact_identities: Mapping[str, Mapping[str, object]]
    source_freeze: Mapping[str, object]
    artifact_bodies: Mapping[str, bytes]
    read_exact: ReadExact
    require_authoritative: bool


def _fail(message: str) -> None:
    raise CorpusR6V2OneSlateExecutionError(message)


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


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6V2OneSlateExecutionError(str(exc)) from exc


def _parse_json(raw: bytes, *, label: str) -> dict[str, object]:
    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        body: dict[str, object] = {}
        for key, value in rows:
            if key in body:
                _fail(f"{label} contains duplicate key {key!r}")
            body[key] = value
        return body

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6V2OneSlateExecutionError(
            f"{label} is not valid JSON"
        ) from exc
    return dict(_mapping(parsed, label=label))


def _exact_read_raw(
    value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], bytes]:
    identity = _identity(value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} content differs from its exact identity")
    return identity, raw


def _exact_read_body(
    value: object,
    expected_body: Mapping[str, object],
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity, raw = _exact_read_raw(value, read_exact=read_exact, label=label)
    parsed = _parse_json(raw, label=label)
    if batch.canonical_json_bytes(parsed) != batch.canonical_json_bytes(
        dict(expected_body)
    ):
        _fail(f"{label} body differs from its exact-read identity")
    return identity, parsed


def _validate_self_hash(
    body: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _sha(body.get(field), label=f"{label}.{field}")
    remainder = {key: body[key] for key in body if key != field}
    if batch.canonical_sha256(remainder) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _validate_panel_and_membership(
    *,
    panel: Mapping[str, object],
    membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    require_authoritative: bool,
) -> tuple[str, dict[str, object], dict[str, object]]:
    schema = panel.get("schema_version")
    if schema not in {panel_index.PANEL_INDEX_SCHEMA, FIXTURE_PANEL_SCHEMA}:
        _fail("combined panel schema is not registered for one-slate execution")
    _validate_self_hash(panel, field="panel_index_sha256", label="combined panel")
    if any(panel.get(field) is not False for field in _FALSE_PANEL_AUTHORITY_FIELDS):
        _fail("combined panel carries forbidden outcome or decision authority")
    raw_slates = _sequence(panel.get("accepted_slates"), label="accepted slates")
    accepted_slates = [
        dict(_mapping(value, label=f"accepted slate[{offset}]"))
        for offset, value in enumerate(raw_slates)
    ]
    if panel.get("accepted_slate_count") != len(accepted_slates):
        _fail("combined panel accepted-slate count differs")
    target = dict(_mapping(membership, label="accepted slate membership"))
    target_bytes = batch.canonical_json_bytes(target)
    matches = [
        row for row in accepted_slates
        if batch.canonical_json_bytes(row) == target_bytes
    ]
    if len(matches) != 1:
        _fail("accepted slate membership is not exactly one combined-panel row")
    retained = matches[0]
    slate_id = retained.get("slate_id")
    if type(slate_id) is not str or not slate_id:
        _fail("accepted slate membership lacks a slate_id")
    retained_acceptance = _identity(
        retained.get("task_acceptance_identity"),
        label="membership task acceptance",
    )
    retained_carrier = _identity(
        retained.get("carrier_identity"), label="membership task carrier"
    )
    if (
        retained_acceptance
        != _identity(task_acceptance_identity, label="task acceptance input")
        or retained_carrier != _identity(carrier_identity, label="carrier input")
    ):
        _fail("task acceptance/carrier identities differ from panel membership")
    if require_authoritative:
        coverage = _mapping(panel.get("coverage"), label="combined panel coverage")
        if (
            schema != panel_index.PANEL_INDEX_SCHEMA
            or panel.get("publication_mode") != panel_index.PUBLICATION_MODE
            or panel.get("accepted_slate_count") != panel_index.V12_SOURCE_TASK_COUNT
            or len(accepted_slates) != panel_index.V12_SOURCE_TASK_COUNT
            or panel.get("exclusions") != []
            or panel.get("failures") != []
            or panel.get("missing_tasks") != []
            or coverage.get("expected_task_count")
            != panel_index.V12_SOURCE_TASK_COUNT
            or coverage.get("accepted_task_count")
            != panel_index.V12_SOURCE_TASK_COUNT
            or coverage.get("excluded_task_count") != 0
            or coverage.get("failed_task_count") != 0
            or coverage.get("missing_task_count") != 0
            or coverage.get("complete") is not True
        ):
            _fail(
                "authoritative execution requires complete accepted v12 "
                "panel membership"
            )
        for field in (
            "lane_ordinal",
            "task_ordinal",
            "source_task_ordinal",
        ):
            if type(retained.get(field)) is not int or int(retained[field]) < 0:
                _fail(f"authoritative membership {field} differs")
        arms = _sequence(retained.get("arms"), label="authoritative membership arms")
        if len(arms) != len(batch.PARAMETER_SET_ORDER):
            _fail("authoritative membership does not bind seven arm results")
    elif (
        schema == FIXTURE_PANEL_SCHEMA
        and panel.get("publication_mode") != FIXTURE_PUBLICATION_MODE
    ):
        _fail("fixture panel publication mode differs")
    return str(slate_id), retained_acceptance, retained_carrier


def _carrier_reconstruction_inputs(
    *,
    carrier_identity: Mapping[str, object],
    membership: Mapping[str, object],
    read_exact: ReadExact,
    require_authoritative: bool,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, dict[str, object]],
    dict[str, object],
    dict[str, bytes],
]:
    normalized_carrier, carrier_raw = _exact_read_raw(
        carrier_identity, read_exact=read_exact, label="accepted task carrier"
    )
    carrier = _parse_json(carrier_raw, label="accepted task carrier")
    if (
        carrier.get("slate_id") != membership.get("slate_id")
        or carrier.get("task_index") != membership.get("task_ordinal")
    ):
        _fail("accepted carrier slate/task differs from panel membership")
    if require_authoritative and (
        carrier.get("schema_version") != batch.TASK_RESULT_SCHEMA
        or carrier.get("publication_mode") != panel_index.PUBLICATION_MODE
    ):
        _fail("authoritative carrier schema/publication mode differs")
    raw_sources = _mapping(carrier.get("source_receipts"), label="carrier sources")
    if set(raw_sources) != set(batch.SOURCE_RECEIPT_ROLES):
        _fail("carrier source receipt roles differ")
    sources = {
        role: _identity(raw_sources[role], label=f"carrier source {role}")
        for role in batch.SOURCE_RECEIPT_ROLES
    }
    if carrier.get("source_receipt_set_sha256") != batch.canonical_sha256(sources):
        _fail("carrier source receipt set hash differs")
    raw_worlds = _mapping(
        carrier.get("world_artifact_receipts"), label="carrier world artifacts"
    )
    if set(raw_worlds) != set(batch.TASK_WORLD_SOURCE_ROLES):
        _fail("carrier world artifact roles differ")
    world_identities = {
        role: _identity(raw_worlds[role], label=f"carrier world artifact {role}")
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    if (
        len({str(value["uri"]) for value in world_identities.values()})
        != len(world_identities)
        or carrier.get("world_artifact_receipt_set_sha256")
        != batch.canonical_sha256(world_identities)
    ):
        _fail("carrier world artifact identities/hash differ")
    source_identity, source_raw = _exact_read_raw(
        sources["later_source_freeze"],
        read_exact=read_exact,
        label="later source freeze",
    )
    source_freeze = _parse_json(source_raw, label="later source freeze")
    if (
        source_freeze.get("freeze_sha256")
        != carrier.get("later_source_freeze_manifest_sha256")
    ):
        _fail("later source freeze internal hash differs from accepted carrier")
    artifact_bodies: dict[str, bytes] = {}
    for block, role in zip(
        rw.WORLD_BLOCKS, batch.TASK_WORLD_SOURCE_ROLES, strict=True
    ):
        _, raw = _exact_read_raw(
            world_identities[role],
            read_exact=read_exact,
            label=f"world artifact {block}",
        )
        artifact_bodies[block] = raw
    return (
        normalized_carrier,
        source_identity,
        world_identities,
        source_freeze,
        artifact_bodies,
    )


def _resolve_one_accepted_v12_slate(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    read_exact: ReadExact,
    require_authoritative: bool,
) -> _ResolvedAcceptedV12Slate:
    """Exact-read the accepted membership and its reconstruction inputs."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    panel_body = dict(_mapping(validated_panel_index, label="validated panel"))
    normalized_panel_identity, exact_panel = _exact_read_body(
        panel_index_identity,
        panel_body,
        read_exact=read_exact,
        label="combined v12 panel index",
    )
    membership = dict(
        _mapping(accepted_slate_membership, label="accepted slate membership")
    )
    slate_id, normalized_acceptance, normalized_carrier = (
        _validate_panel_and_membership(
            panel=exact_panel,
            membership=membership,
            task_acceptance_identity=task_acceptance_identity,
            carrier_identity=carrier_identity,
            require_authoritative=require_authoritative,
        )
    )
    _exact_read_raw(
        normalized_acceptance,
        read_exact=read_exact,
        label="task acceptance receipt",
    )
    (
        exact_carrier_identity,
        source_freeze_identity,
        world_artifact_identities,
        source_freeze,
        artifact_bodies,
    ) = _carrier_reconstruction_inputs(
        carrier_identity=normalized_carrier,
        membership=membership,
        read_exact=read_exact,
        require_authoritative=require_authoritative,
    )
    if exact_carrier_identity != normalized_carrier:
        _fail("exact-read carrier identity differs from panel membership")
    return _ResolvedAcceptedV12Slate(
        slate_id=slate_id,
        panel_index_identity=normalized_panel_identity,
        panel_index_sha256=_sha(
            exact_panel.get("panel_index_sha256"), label="panel index SHA"
        ),
        accepted_slate_membership=membership,
        task_acceptance_identity=normalized_acceptance,
        carrier_identity=normalized_carrier,
        later_source_freeze_identity=source_freeze_identity,
        world_artifact_identities=world_artifact_identities,
        source_freeze=source_freeze,
        artifact_bodies=artifact_bodies,
        read_exact=read_exact,
        require_authoritative=require_authoritative,
    )


def _finish_one_accepted_v12_slate_reconstruction(
    resolved: _ResolvedAcceptedV12Slate,
) -> AcceptedV12SlateReconstruction:
    """Replay the accepted task and verify its canonical union reconstruction."""
    try:
        imported = v12_import.reopen_v12_task(
            acceptance_receipt_identity=resolved.task_acceptance_identity,
            carrier_identity=resolved.carrier_identity,
            read_exact=resolved.read_exact,
            require_authoritative=resolved.require_authoritative,
        )
        reconstructed = v12_import.reconstruct_v12_task(
            imported,
            source_freeze=resolved.source_freeze,
            artifact_bodies=resolved.artifact_bodies,
        )
    except v12_import.CorpusV12ImportError as exc:
        raise CorpusR6V2OneSlateExecutionError(str(exc)) from exc
    import_receipt = _mapping(
        imported.compatibility_receipt, label="v12 compatibility import"
    )
    if (
        import_receipt.get("acceptance_receipt_identity")
        != resolved.task_acceptance_identity
        or import_receipt.get("carrier_identity") != resolved.carrier_identity
        or import_receipt.get("slate", {}).get("slate_id") != resolved.slate_id
    ):
        _fail("v12 compatibility import differs from panel membership")
    if resolved.require_authoritative and (
        import_receipt.get("authoritative_task_acceptance_verified") is not True
        or import_receipt.get("accepted_task_result_binding_verified") is not True
        or import_receipt.get("accepted_task_index")
        != resolved.accepted_slate_membership.get("task_ordinal")
    ):
        _fail("authoritative task acceptance was not preserved by v12 import")
    provenance = _mapping(reconstructed.provenance, label="reconstructed provenance")
    if provenance.get("slate", {}).get("slate_id") != resolved.slate_id:
        _fail("reconstructed slate differs from panel membership")
    reconstruction_receipt = _mapping(
        reconstructed.reconstruction_receipt,
        label="reconstruction receipt",
    )
    if (
        reconstruction_receipt.get("uses_realized_outcomes") is not False
        or reconstruction_receipt.get("promotion_authority") is not False
    ):
        _fail("reconstruction receipt carries forbidden authority")
    return AcceptedV12SlateReconstruction(
        slate_id=resolved.slate_id,
        panel_index_identity=resolved.panel_index_identity,
        panel_index_sha256=resolved.panel_index_sha256,
        accepted_slate_membership=resolved.accepted_slate_membership,
        task_acceptance_identity=resolved.task_acceptance_identity,
        carrier_identity=resolved.carrier_identity,
        later_source_freeze_identity=resolved.later_source_freeze_identity,
        world_artifact_identities=resolved.world_artifact_identities,
        imported=imported,
        reconstructed=reconstructed,
    )


def reconstruct_one_accepted_v12_slate(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    read_exact: ReadExact,
    require_authoritative: bool = True,
) -> AcceptedV12SlateReconstruction:
    """Exact-read and reconstruct one outcome-blind accepted v12 panel member."""
    resolved = _resolve_one_accepted_v12_slate(
        validated_panel_index=validated_panel_index,
        panel_index_identity=panel_index_identity,
        accepted_slate_membership=accepted_slate_membership,
        task_acceptance_identity=task_acceptance_identity,
        carrier_identity=carrier_identity,
        read_exact=read_exact,
        require_authoritative=require_authoritative,
    )
    return _finish_one_accepted_v12_slate_reconstruction(resolved)


def execute_one_slate_r6_v2(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    validated_matchup_source_snapshot: Mapping[str, object],
    matchup_source_snapshot_identity: Mapping[str, object],
    read_exact: ReadExact,
    matchup_evidence_class: str = MATCHUP_EVIDENCE_RETROSPECTIVE,
    minimum_supported_players: int = 2,
    minimum_completeness: float = 0.5,
    admission_m: int = runner.DEFAULT_ADMISSION_M,
    neutral_replicates: int = runner.DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Execute and retain one exact outcome-blind R6-v2 slate surface."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if matchup_evidence_class not in MATCHUP_EVIDENCE_CLASSES:
        _fail("matchup evidence class differs")
    if require_authoritative and (
        admission_m != runner.DEFAULT_ADMISSION_M
        or worlds_per_block is not None
    ):
        _fail("authoritative one-slate execution cannot override registered doses")
    resolved = _resolve_one_accepted_v12_slate(
        validated_panel_index=validated_panel_index,
        panel_index_identity=panel_index_identity,
        accepted_slate_membership=accepted_slate_membership,
        task_acceptance_identity=task_acceptance_identity,
        carrier_identity=carrier_identity,
        read_exact=read_exact,
        require_authoritative=require_authoritative,
    )
    matchup_body = dict(_mapping(
        validated_matchup_source_snapshot,
        label="validated matchup source snapshot",
    ))
    normalized_matchup_identity, exact_matchup_body = _exact_read_body(
        matchup_source_snapshot_identity,
        matchup_body,
        read_exact=read_exact,
        label="matchup source snapshot",
    )
    try:
        matchup_source = runner.validate_matchup_source_snapshot(
            exact_matchup_body
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6V2OneSlateExecutionError(str(exc)) from exc
    accepted = _finish_one_accepted_v12_slate_reconstruction(resolved)
    imported = accepted.imported
    reconstructed = accepted.reconstructed
    slate_id = accepted.slate_id
    membership = accepted.accepted_slate_membership
    normalized_acceptance = accepted.task_acceptance_identity
    normalized_carrier = accepted.carrier_identity
    source_freeze_identity = accepted.later_source_freeze_identity
    world_artifact_identities = accepted.world_artifact_identities
    import_receipt = _mapping(
        imported.compatibility_receipt, label="v12 compatibility import"
    )
    provenance = _mapping(reconstructed.provenance, label="reconstructed provenance")
    try:
        matchup_summary = runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=matchup_source,
            minimum_supported_players=minimum_supported_players,
            minimum_completeness=minimum_completeness,
        )
        retrieval_surface = runner.run_retrieval_surface_v2(
            provenance=provenance,
            union_scores=reconstructed.union_scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            matchup_summary=matchup_summary,
            matchup_source=matchup_source,
            admission_m=admission_m,
            neutral_replicates=neutral_replicates,
            neutral_seed_root=neutral_seed_root,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6V2OneSlateExecutionError(str(exc)) from exc
    expected_dose = (
        runner.AUTHORITATIVE_DOSE
        if require_authoritative
        else runner.FIXTURE_DOSE
    )
    if (
        matchup_summary.get("uses_realized_outcomes") is not False
        or retrieval_surface.get("uses_realized_outcomes") is not False
        or retrieval_surface.get("promotion_authority") is not False
        or retrieval_surface.get("dose_authority") != expected_dose
        or retrieval_surface.get("require_authoritative")
        is not require_authoritative
        or retrieval_surface.get("slate", {}).get("slate_id") != slate_id
    ):
        _fail("retrieval surface outcome/dose/slate authority differs")
    if require_authoritative and (
        retrieval_surface.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or retrieval_surface.get("admission_cap") != runner.DEFAULT_ADMISSION_M
    ):
        _fail("retrieval surface did not preserve authoritative production doses")
    reconstruction_receipt = dict(_mapping(
        reconstructed.reconstruction_receipt,
        label="reconstruction receipt",
    ))
    if (
        reconstruction_receipt.get("uses_realized_outcomes") is not False
        or reconstruction_receipt.get("promotion_authority") is not False
    ):
        _fail("reconstruction receipt carries forbidden authority")
    matchup_summary = dict(_mapping(matchup_summary, label="matchup summary"))
    retrieval_surface = dict(_mapping(
        retrieval_surface, label="retrieval surface"
    ))
    matchup_is_mechanics_only = (
        matchup_evidence_class == MATCHUP_EVIDENCE_RETROSPECTIVE
    )
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
        "matchup_summary_sha256": _sha(
            matchup_summary.get("matchup_summary_sha256"),
            label="matchup summary SHA",
        ),
        "retrieval_surface_sha256": _sha(
            retrieval_surface.get("retrieval_surface_sha256"),
            label="retrieval surface SHA",
        ),
    }
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "execution_mode": (
            "authoritative-dose-one-slate-mechanics-smoke"
            if require_authoritative
            else "non-authoritative-fixture-mechanics"
        ),
        "slate_id": slate_id,
        "panel_index_identity": accepted.panel_index_identity,
        "panel_index_sha256": accepted.panel_index_sha256,
        "accepted_slate_membership": membership,
        "accepted_slate_membership_sha256": batch.canonical_sha256(membership),
        "task_acceptance_identity": normalized_acceptance,
        "carrier_identity": normalized_carrier,
        "later_source_freeze_identity": source_freeze_identity,
        "world_artifact_identities": world_artifact_identities,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            world_artifact_identities
        ),
        "matchup_source_snapshot_identity": normalized_matchup_identity,
        "matchup_source_snapshot_sha256": _sha(
            matchup_source.get("matchup_source_snapshot_sha256"),
            label="matchup source snapshot SHA",
        ),
        "matchup_evidence_class": matchup_evidence_class,
        "matchup_mechanics_only": matchup_is_mechanics_only,
        "configuration": {
            "minimum_supported_players": minimum_supported_players,
            "minimum_completeness": float(minimum_completeness),
            "admission_m": admission_m,
            "neutral_replicates": neutral_replicates,
            "neutral_seed_root": neutral_seed_root,
            "worlds_per_block": (
                rw.WORLDS_PER_BLOCK
                if worlds_per_block is None else worlds_per_block
            ),
            "require_authoritative": require_authoritative,
        },
        "verification": {
            "panel_content_identity_verified": True,
            "panel_membership_binding_verified": True,
            "task_acceptance_content_identity_verified": True,
            "task_acceptance_carrier_binding_verified": True,
            "carrier_source_receipts_verified": True,
            "matchup_snapshot_content_identity_verified": True,
            "canonical_authoritative_dose_verified": require_authoritative,
        },
        "output_hashes": output_hashes,
        "reconstruction_receipt": reconstruction_receipt,
        "matchup_summary": matchup_summary,
        "retrieval_surface": retrieval_surface,
        **{field: False for field in _FALSE_RESULT_AUTHORITY_FIELDS},
    }
    body["task_result_sha256"] = batch.canonical_sha256(body)
    return body


__all__ = [
    "AcceptedV12SlateReconstruction",
    "CorpusR6V2OneSlateExecutionError",
    "FIXTURE_PANEL_SCHEMA",
    "FIXTURE_PUBLICATION_MODE",
    "MATCHUP_EVIDENCE_CLASSES",
    "MATCHUP_EVIDENCE_PIT",
    "MATCHUP_EVIDENCE_RETROSPECTIVE",
    "RESULT_SCHEMA",
    "execute_one_slate_r6_v2",
    "reconstruct_one_accepted_v12_slate",
]
