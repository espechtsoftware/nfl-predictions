"""Ordinal-only mechanics adapter for the terminal matchup-source v1 release.

This successor is intentionally separate from
``corpus_r6_v2_analysis_release``.  The predecessor is frozen to the legacy
simple matchup snapshot and can only terminate ``complete-source-blocked``;
changing its source interpretation in place would make its old receipts
ambiguous.

The public consumer added below accepts one generation-pinned terminal source
release and one source-task ordinal.  It does not accept caller-supplied
member identities, source rows, matchup summaries, or admissions.  The source
release module exact-reopens and validates the selected member before these
private helpers project its already-validated annotation rows into the
existing seven-law R6-v2 runner.

This adapter does not prove that the accepted-candidate release came from the
fixed-G0 candidate-authority root and therefore is not the final authoritative
consumer.  The candidate-rooted v2 consumer is the only successor eligible
for that role; this module remains a bounded offline mechanics baseline and a
shared implementation surface.

No function in this module owns a cloud client, publisher, warehouse reader,
realized-outcome reader, scorer, graph mutation, promotion, or production
decision.  Every returned authority flag is false.  The retained runner
surface is independently regenerated and byte-compared in the same call so a
caller cannot substitute a coherently rehashed fold, admission, or book.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as source_release
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution_v1
from nfl_dfs.research import corpus_r6_v2_one_slate_execution_v2 as execution_v2
from nfl_dfs.research import residual_world_columns as rw


RESULT_SCHEMA: Final = (
    "corpus-r6-v2-matchup-source-release-consumer-result/v1"
)
SOURCE_PROJECTION_SCHEMA: Final = (
    "corpus-r6-v2-matchup-source-release-runner-projection/v1"
)
REQUIRED_SOURCE_EVIDENCE_CLASS: Final = (
    "retrospective-prior-period-reconstruction"
)
_ELIGIBLE_FAMILY_BY_POSITION: Final = {
    "QB": "qb",
    "RB": "rb",
    "WR": "receiver",
    "TE": "receiver",
}
_FALSE_AUTHORITY_FIELDS: Final = (
    "analytical_authority",
    "automatic_retry_licensed",
    "corpus_fill_licensed",
    "corpus_retrieval_licensed",
    "decision_authority",
    "fill_authority",
    "graph_authority",
    "graph_mutation_licensed",
    "historical_scoring_authority",
    "historical_scoring_licensed",
    "live_policy_access_licensed",
    "live_strategy_authority",
    "outcome_authority",
    "outcome_verdict_authority",
    "production_authority",
    "production_change_licensed",
    "production_policy_authority",
    "promotion_authority",
    "r6_freeze_authority",
    "retrieval_authority",
    "scoring_authority",
    "source_execution_authority",
    "source_publication_authority",
)
_FORBIDDEN_OUTCOME_FIELDS: Final = frozenset({
    "actual_points",
    "actual_score",
    "contest_finish",
    "contest_place",
    "contest_rank",
    "contest_score",
    "entry_rank",
    "lineup_actual",
    "lineup_points",
    "lineup_score",
    "outcome_reader",
    "payout",
    "realized_outcome",
    "realized_points",
    "realized_reader",
    "realized_score",
    "score_reader",
    "winner",
    "winning_score",
})


class CorpusR6V2MatchupSourceReleaseConsumerV1Error(ValueError):
    """The source-v2 member cannot be bound to one R6-v2 slate."""


ReadExact = Callable[[Mapping[str, object]], bytes]


@dataclass(frozen=True)
class _ValidatedSourceProjection:
    """Private projection constructed only after exact source-release reopen."""

    source_release_identity: dict[str, object]
    source_member: dict[str, object]
    source_export_identity: dict[str, object]
    capture_receipt_identity: dict[str, object]
    catalog_identity: dict[str, object]
    source_export_schema: str
    slate: dict[str, object]
    structural_catalog: list[dict[str, object]]
    annotation_rows: list[dict[str, object]]


def _fail(message: str) -> None:
    raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


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
        raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(str(exc)) from exc


def _exact_ordinal(value: object, *, label: str) -> int:
    if type(value) is not int or not 0 <= value < 54:
        _fail(f"{label} must be an exact integer in [0,54)")
    return value


def _reject_outcome_carriers(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if normalized in _FORBIDDEN_OUTCOME_FIELDS or (
                "realized" in normalized
                and normalized != "uses_realized_outcomes"
            ):
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "outcome_columns_read" and nested != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            if normalized == "uses_realized_outcomes" and nested is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            _reject_outcome_carriers(nested, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, nested in enumerate(value):
            _reject_outcome_carriers(nested, label=f"{label}[{ordinal}]")


def _accepted_task_and_catalog(
    accepted: execution_v1.AcceptedV12SlateReconstruction,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Reuse the approved six-field accepted-v12 authority derivation."""
    try:
        task, catalog = execution_v2._accepted_source_authority(accepted)
    except execution_v2.CorpusR6V2OneSlateExecutionV2Error as exc:
        raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(str(exc)) from exc
    return dict(task), [dict(row) for row in catalog]


def _normalize_source_projection(
    *,
    source_release_identity: object,
    source_member: object,
    source_export_identity: object,
    capture_receipt_identity: object,
    catalog_identity: object,
    source_export_schema: object,
    slate: object,
    structural_catalog: object,
    annotation_rows: object,
) -> _ValidatedSourceProjection:
    """Normalize values returned by the exact source-release reopener.

    This helper is private by design.  It is not a source authority boundary;
    the public entry point must call the terminal source-release exact
    reopener first and may pass only its returned bodies here.
    """
    root_identity = _identity(
        source_release_identity, label="matchup source release root"
    )
    member = _mapping(source_member, label="matchup source release member")
    export_identity = _identity(
        source_export_identity, label="matchup source export"
    )
    receipt_identity = _identity(
        capture_receipt_identity, label="matchup capture receipt"
    )
    retained_catalog_identity = _identity(
        catalog_identity, label="matchup structural catalog"
    )
    if type(source_export_schema) is not str or not source_export_schema:
        _fail("matchup source export schema must be nonempty")
    normalized_slate = _mapping(slate, label="matchup source slate")
    catalog_rows = [
        _mapping(row, label=f"matchup structural catalog[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(structural_catalog, label="matchup structural catalog")
        )
    ]
    annotations = [
        _mapping(row, label=f"matchup annotation[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(annotation_rows, label="matchup annotations")
        )
    ]
    if not catalog_rows or not annotations:
        _fail("matchup source projection cannot be empty")
    return _ValidatedSourceProjection(
        source_release_identity=root_identity,
        source_member=member,
        source_export_identity=export_identity,
        capture_receipt_identity=receipt_identity,
        catalog_identity=retained_catalog_identity,
        source_export_schema=source_export_schema,
        slate=normalized_slate,
        structural_catalog=catalog_rows,
        annotation_rows=annotations,
    )


def _runner_rows_from_projection(
    projection: _ValidatedSourceProjection,
    *,
    accepted_catalog: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Derive the exact minimal row surface used by the frozen runner."""
    catalog = [dict(row) for row in accepted_catalog]
    if projection.structural_catalog != catalog:
        _fail("source-v2 structural catalog differs from accepted v12 catalog")
    expected_skill = {
        str(row["id"]): {
            "gsis_id": str(row["id"]),
            "family": _ELIGIBLE_FAMILY_BY_POSITION[str(row["pos"])],
            "position": str(row["pos"]),
        }
        for row in catalog
        if str(row.get("pos")) in _ELIGIBLE_FAMILY_BY_POSITION
    }
    by_id: dict[str, dict[str, object]] = {}
    for ordinal, row in enumerate(projection.annotation_rows):
        player_id = row.get("gsis_id")
        if type(player_id) is not str or not player_id or player_id in by_id:
            _fail(f"matchup annotation[{ordinal}] player identity differs")
        if player_id not in expected_skill:
            _fail("matchup annotations contain a player outside accepted catalog")
        expected = expected_skill[player_id]
        depth = row.get("qb_depth1")
        edge = row.get("matchup_edge_score")
        present = edge is not None
        component_count = row.get("matchup_component_count")
        if (
            row.get("family") != expected["family"]
            or row.get("position") != expected["position"]
            or row.get("annotation_row_present") is not present
            or (
                expected["family"] == "qb"
                and depth is not None
                and type(depth) is not bool
            )
            or (expected["family"] != "qb" and depth is not None)
            or type(component_count) is not int
            or component_count < 0
            or (
                edge is not None
                and (
                    isinstance(edge, bool)
                    or not isinstance(edge, (int, float))
                    or not math.isfinite(float(edge))
                    or not 0.0 <= float(edge) <= 1.0
                )
            )
            or (edge is None) is not (component_count < 2)
        ):
            _fail(f"matchup annotation[{ordinal}] runner semantics differ")
        by_id[player_id] = {
            **expected,
            "qb_depth1": depth,
            "matchup_edge_score": None if edge is None else float(edge),
        }
    if set(by_id) != set(expected_skill):
        missing = sorted(set(expected_skill) - set(by_id))
        extra = sorted(set(by_id) - set(expected_skill))
        _fail(
            "matchup annotation population differs from accepted catalog: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    return [by_id[player_id] for player_id in sorted(by_id)]


def _build_matchup_summary(
    *,
    provenance: Mapping[str, object],
    projection: _ValidatedSourceProjection,
    accepted_catalog: Sequence[Mapping[str, object]],
    minimum_supported_players: int,
    minimum_completeness: float,
) -> dict[str, object]:
    rows = _runner_rows_from_projection(
        projection, accepted_catalog=accepted_catalog
    )
    runner_source = {
        "schema_version": projection.source_export_schema,
        "source_export_identity": projection.source_export_identity,
        "query_receipt_identity": projection.capture_receipt_identity,
        "player_catalog_identity": projection.catalog_identity,
        "rows": rows,
    }
    try:
        return runner._build_matchup_lineup_summaries_from_reopened(
            provenance=provenance,
            source=runner_source,
            minimum_supported_players=minimum_supported_players,
            minimum_completeness=minimum_completeness,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(str(exc)) from exc


def _build_retrieval_surface(
    *,
    provenance: Mapping[str, object],
    union_scores: np.ndarray,
    reconstruction_receipt: Mapping[str, object],
    matchup_summary: Mapping[str, object],
    admission_m: int,
    neutral_replicates: int,
    neutral_seed_root: str,
    worlds_per_block: int | None,
    require_authoritative: bool,
) -> dict[str, object]:
    """Run the unchanged R6-v2 laws from an already source-validated summary."""
    try:
        reconstruction_sha = runner._validate_reconstruction_input(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
        )
        summary_sha = _sha(
            matchup_summary.get("matchup_summary_sha256"),
            label="matchup summary SHA",
        )
        folds = [
            runner._run_fit_scope_impl(
                provenance=provenance,
                union_scores=union_scores,
                reconstruction_receipt=reconstruction_receipt,
                matchup_summary=matchup_summary,
                matchup_source=None,
                heldout_block=heldout,
                admission_m=admission_m,
                neutral_replicates=neutral_replicates,
                neutral_seed_root=neutral_seed_root,
                worlds_per_block=worlds_per_block,
                require_authoritative=require_authoritative,
                validated_reconstruction_sha256=reconstruction_sha,
                validated_matchup_summary_sha256=summary_sha,
            )
            for heldout in rw.WORLD_BLOCKS
        ]
        final_fit = runner._run_fit_scope_impl(
            provenance=provenance,
            union_scores=union_scores,
            reconstruction_receipt=reconstruction_receipt,
            matchup_summary=matchup_summary,
            matchup_source=None,
            heldout_block=None,
            admission_m=admission_m,
            neutral_replicates=neutral_replicates,
            neutral_seed_root=neutral_seed_root,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
            validated_reconstruction_sha256=reconstruction_sha,
            validated_matchup_summary_sha256=summary_sha,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(str(exc)) from exc
    body: dict[str, object] = {
        "schema_version": runner.RUNNER_SCHEMA,
        "slate": provenance["slate"],
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "reconstruction_sha256": reconstruction_sha,
        "matchup_summary_sha256": summary_sha,
        "matchup_source_snapshot_sha256": matchup_summary[
            "matchup_source_snapshot_sha256"
        ],
        "folds": folds,
        "final_fit": final_fit,
        "fold_count": len(folds),
        "books_per_scope": 14 + neutral_replicates,
        "cross_fit_book_count": len(folds) * (14 + neutral_replicates),
        "final_fit_book_count": 14 + neutral_replicates,
        "neutral_replicate_count": neutral_replicates,
        "worlds_per_block": final_fit["worlds_per_block"],
        "admission_cap": admission_m,
        "dose_authority": final_fit["dose_authority"],
        "require_authoritative": require_authoritative,
        "neutral_replicate_freeze_requires_outcome_blind_runtime_benchmark": True,
        "final_fit_is_distinct_all-block-refit": True,
        "uses_realized_outcomes": False,
        "evidence_tier": "outcome-blind-simulated-analysis",
        "promotion_authority": False,
    }
    body["retrieval_surface_sha256"] = batch.canonical_sha256(body)
    return body


def _validate_retrieval_surface(
    value: Mapping[str, object],
    **inputs: object,
) -> dict[str, object]:
    rebuilt = _build_retrieval_surface(**inputs)  # type: ignore[arg-type]
    if batch.canonical_json_bytes(value) != batch.canonical_json_bytes(rebuilt):
        _fail("source-v2 retrieval surface canonical replay differs")
    return rebuilt


def _source_projection_from_exact_reopen(
    reopened: Mapping[str, object],
    *,
    expected_ordinal: int,
    expected_task: Mapping[str, object],
    accepted_catalog: Sequence[Mapping[str, object]],
    expected_release_schema: str = source_release.MATCHUP_SOURCE_RELEASE_SCHEMA,
    expected_reopened_fields: frozenset[str] | None = None,
) -> _ValidatedSourceProjection:
    item = _mapping(reopened, label="exact-reopened matchup source member")
    _reject_outcome_carriers(item, label="exact-reopened matchup source member")
    required = expected_reopened_fields or frozenset({
        "release_identity",
        "release",
        "member",
        "producer_release",
        "producer_release_entry",
        "structural_catalog",
        "candidate_artifact",
        "producer_receipt",
        "input_bundle",
        "source_export",
        "capture_receipt",
        "operator_result",
        "structural_players",
        "annotation_rows",
    })
    if set(item) != required:
        _fail("exact source-release reopener result fields differ")
    release = _mapping(item["release"], label="matchup source release")
    member = _mapping(item["member"], label="matchup source member")
    source_export = _mapping(
        item["source_export"], label="matchup source export"
    )
    capture = _mapping(
        item["capture_receipt"], label="matchup capture receipt"
    )
    catalog = _mapping(
        item["structural_catalog"], label="matchup structural catalog"
    )
    ordinal = _exact_ordinal(
        member.get("source_task_ordinal"), label="source member ordinal"
    )
    accepted_slate = {
        key: expected_task[key] for key in ("season", "week", "slate_id")
        if key in expected_task
    }
    # The approved accepted-task helper retains task/slate IDs and ordinals;
    # season/week come from the reconstructed provenance and are checked by
    # the public entry before this projection is built.
    if (
        ordinal != expected_ordinal
        or source_export.get("source_task_ordinal") != ordinal
        or capture.get("source_task_ordinal") != ordinal
        or member.get("task_id") != expected_task.get("task_id")
        or member.get("slate_id", member.get("slate", {}).get("slate_id"))
        != expected_task.get("slate_id")
        or source_export.get("evidence_class")
        != REQUIRED_SOURCE_EVIDENCE_CLASS
        or source_export.get("authoritative_pit") is not False
        or source_export.get("uses_realized_outcomes") is not False
        or source_export.get("outcome_columns_read") != []
        or source_export.get("schema_version")
        != source_release.MATCHUP_SOURCE_EXPORT_SCHEMA
        or release.get("schema_version") != expected_release_schema
    ):
        _fail("source-v2 release member differs from accepted R6 task")
    source_slate = _mapping(source_export.get("slate"), label="source export slate")
    if accepted_slate and any(
        source_slate.get(key) != value for key, value in accepted_slate.items()
    ):
        _fail("source-v2 export slate differs from accepted R6 slate")
    if (
        catalog.get("source_task_ordinal") != ordinal
        or catalog.get("task_id") != expected_task.get("task_id")
        or catalog.get("slate") != source_slate
        or catalog.get("players") != item["structural_players"]
        or member.get("catalog_identity") != source_export.get("catalog_identity")
        or source_export.get("annotation_rows") != item["annotation_rows"]
        or source_export.get("annotation_rows_sha256")
        != batch.canonical_sha256(item["annotation_rows"])
        or member.get("source_export_identity")
        != capture.get("source_export_identity")
        or member.get("source_export_sha256")
        != source_export.get("matchup_source_export_sha256")
        or member.get("capture_receipt_sha256")
        != capture.get("matchup_capture_receipt_sha256")
    ):
        _fail("source-v2 catalog/export/capture cross-binding differs")
    projection = _normalize_source_projection(
        source_release_identity=item["release_identity"],
        source_member=member,
        source_export_identity=member["source_export_identity"],
        capture_receipt_identity=member["capture_receipt_identity"],
        catalog_identity=member["catalog_identity"],
        source_export_schema=source_export["schema_version"],
        slate=source_slate,
        structural_catalog=item["structural_players"],
        annotation_rows=item["annotation_rows"],
    )
    # Reassert the exact accepted catalog here, before the runner ever sees a
    # row.  This detects an alternate same-slate population even if every
    # source-v2 object is internally coherent.
    _runner_rows_from_projection(
        projection, accepted_catalog=accepted_catalog
    )
    return projection


def execute_r6_v2_matchup_source_release_ordinal_v1(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    matchup_source_release_identity: Mapping[str, object],
    source_task_ordinal: int,
    read_exact: ReadExact,
    minimum_supported_players: int = 2,
    minimum_completeness: float = 0.5,
    admission_m: int = runner.DEFAULT_ADMISSION_M,
    neutral_replicates: int = runner.DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Exact-open one source-v2 ordinal and run the complete R6-v2 surface."""
    ordinal = _exact_ordinal(source_task_ordinal, label="source task ordinal")
    if not callable(read_exact):
        _fail("exact reader is not callable")
    normalized_source_release_identity = _identity(
        matchup_source_release_identity,
        label="matchup source release root",
    )
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if require_authoritative and (
        admission_m != runner.DEFAULT_ADMISSION_M or worlds_per_block is not None
    ):
        _fail("authoritative source-v2 execution cannot override registered doses")
    try:
        accepted = execution_v1.reconstruct_one_accepted_v12_slate(
            validated_panel_index=validated_panel_index,
            panel_index_identity=panel_index_identity,
            accepted_slate_membership=accepted_slate_membership,
            task_acceptance_identity=task_acceptance_identity,
            carrier_identity=carrier_identity,
            read_exact=read_exact,
            require_authoritative=require_authoritative,
        )
    except execution_v1.CorpusR6V2OneSlateExecutionError as exc:
        raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(str(exc)) from exc
    accepted_task, accepted_catalog = _accepted_task_and_catalog(accepted)
    reconstructed = accepted.reconstructed
    provenance = _mapping(
        reconstructed.provenance, label="accepted candidate provenance"
    )
    reconstruction_receipt = _mapping(
        reconstructed.reconstruction_receipt, label="reconstruction receipt"
    )
    provenance_slate = _mapping(
        provenance.get("slate"), label="accepted provenance slate"
    )
    accepted_expected_task = {
        **accepted_task,
        "season": provenance_slate.get("season"),
        "week": provenance_slate.get("week"),
    }
    if (
        accepted_task.get("source_task_ordinal") != ordinal
        or accepted_task.get("slate_id") != provenance_slate.get("slate_id")
        or accepted.slate_id != provenance_slate.get("slate_id")
    ):
        _fail("requested source ordinal differs from accepted panel membership")
    try:
        reopened = source_release.reopen_matchup_source_release_ordinal_v1(
            release_identity=normalized_source_release_identity,
            source_task_ordinal=ordinal,
            read_exact=read_exact,
        )
    except source_release.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6V2MatchupSourceReleaseConsumerV1Error(str(exc)) from exc
    projection = _source_projection_from_exact_reopen(
        reopened,
        expected_ordinal=ordinal,
        expected_task=accepted_expected_task,
        accepted_catalog=accepted_catalog,
    )
    if projection.source_release_identity != normalized_source_release_identity:
        _fail("exact source-release reopener returned a different root identity")
    summary = _build_matchup_summary(
        provenance=provenance,
        projection=projection,
        accepted_catalog=accepted_catalog,
        minimum_supported_players=minimum_supported_players,
        minimum_completeness=minimum_completeness,
    )
    surface_inputs = {
        "provenance": provenance,
        "union_scores": reconstructed.union_scores,
        "reconstruction_receipt": reconstructed.reconstruction_receipt,
        "matchup_summary": summary,
        "admission_m": admission_m,
        "neutral_replicates": neutral_replicates,
        "neutral_seed_root": neutral_seed_root,
        "worlds_per_block": worlds_per_block,
        "require_authoritative": require_authoritative,
    }
    retained_surface = _build_retrieval_surface(**surface_inputs)
    surface = _validate_retrieval_surface(retained_surface, **surface_inputs)
    release = _mapping(reopened["release"], label="matchup source release")
    member = _mapping(reopened["member"], label="matchup source member")
    source_projection = {
        "schema_version": SOURCE_PROJECTION_SCHEMA,
        "source_task_ordinal": ordinal,
        "slate": projection.slate,
        "source_release_identity": projection.source_release_identity,
        "source_release_sha256": release["matchup_source_release_sha256"],
        "source_member_sha256": member["matchup_source_member_sha256"],
        "source_export_identity": projection.source_export_identity,
        "source_export_sha256": member["source_export_sha256"],
        "capture_receipt_identity": projection.capture_receipt_identity,
        "capture_receipt_sha256": member["capture_receipt_sha256"],
        "catalog_identity": projection.catalog_identity,
        "candidate_artifact_identity": _identity(
            member["candidate_artifact_identity"], label="candidate artifact"
        ),
        "producer_receipt_identity": _identity(
            member["producer_receipt_identity"], label="producer receipt"
        ),
        "input_bundle_identity": _identity(
            member["input_bundle_identity"], label="component input bundle"
        ),
        "operator_result_identity": _identity(
            member["operator_result_identity"], label="source operator result"
        ),
        "operator_result_sha256": _sha(
            member["operator_result_sha256"], label="source operator result SHA"
        ),
        "accepted_catalog_structural_sha256": batch.canonical_sha256(
            accepted_catalog
        ),
        "annotation_rows_sha256": reopened["source_export"][
            "annotation_rows_sha256"
        ],
        "matchup_evidence_class": REQUIRED_SOURCE_EVIDENCE_CLASS,
        "uses_realized_outcomes": False,
    }
    source_projection["source_projection_sha256"] = batch.canonical_sha256(
        source_projection
    )
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "execution_mode": (
            "source-v2-release-authoritative-dose-one-slate-mechanics"
            if require_authoritative
            else "source-v2-release-fixture-dose-one-slate-mechanics"
        ),
        "slate_id": accepted.slate_id,
        "source_task_ordinal": ordinal,
        "panel_index_identity": accepted.panel_index_identity,
        "panel_index_sha256": accepted.panel_index_sha256,
        "accepted_slate_membership": accepted.accepted_slate_membership,
        "accepted_slate_membership_sha256": batch.canonical_sha256(
            accepted.accepted_slate_membership
        ),
        "accepted_task_binding": accepted_task,
        "accepted_task_binding_sha256": batch.canonical_sha256(accepted_task),
        "task_acceptance_identity": accepted.task_acceptance_identity,
        "carrier_identity": accepted.carrier_identity,
        "later_source_freeze_identity": accepted.later_source_freeze_identity,
        "world_artifact_identities": accepted.world_artifact_identities,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            accepted.world_artifact_identities
        ),
        "matchup_source_projection": source_projection,
        "configuration": {
            "minimum_supported_players": minimum_supported_players,
            "minimum_completeness": float(minimum_completeness),
            "admission_m": admission_m,
            "neutral_replicates": neutral_replicates,
            "neutral_seed_root": neutral_seed_root,
            "worlds_per_block": (
                rw.WORLDS_PER_BLOCK if worlds_per_block is None else worlds_per_block
            ),
            "require_authoritative": require_authoritative,
        },
        "verification": {
            "source_release_root_exact_reopened": True,
            "source_member_selected_only_by_ordinal": True,
            "source_member_mechanics_predecessor_replay_verified": True,
            "candidate_authority_root_verified": False,
            "source_catalog_matches_accepted_v12_verified": True,
            "source_task_matches_accepted_v12_verified": True,
            "full_seven_law_fold_final_surface_canonical_replay_verified": True,
            "canonical_authoritative_dose_verified": require_authoritative,
        },
        "output_hashes": {
            "candidate_provenance_sha256": provenance[
                "candidate_provenance_sha256"
            ],
            "reconstruction_sha256": reconstruction_receipt[
                "reconstruction_sha256"
            ],
            "matchup_summary_sha256": summary["matchup_summary_sha256"],
            "retrieval_surface_sha256": surface["retrieval_surface_sha256"],
            "source_projection_sha256": source_projection[
                "source_projection_sha256"
            ],
        },
        "reconstruction_receipt": reconstruction_receipt,
        "matchup_summary": summary,
        "retrieval_surface": surface,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["task_result_sha256"] = batch.canonical_sha256(body)
    return body


def validate_r6_v2_matchup_source_release_ordinal_result_v1(
    value: Mapping[str, object],
    **inputs: object,
) -> dict[str, object]:
    """Exact-reopen and independently regenerate one retained result."""
    rebuilt = execute_r6_v2_matchup_source_release_ordinal_v1(
        **inputs  # type: ignore[arg-type]
    )
    if batch.canonical_json_bytes(value) != batch.canonical_json_bytes(rebuilt):
        _fail("source-v2 one-slate consumer result canonical replay differs")
    return rebuilt


__all__ = [
    "CorpusR6V2MatchupSourceReleaseConsumerV1Error",
    "REQUIRED_SOURCE_EVIDENCE_CLASS",
    "RESULT_SCHEMA",
    "SOURCE_PROJECTION_SCHEMA",
    "execute_r6_v2_matchup_source_release_ordinal_v1",
    "validate_r6_v2_matchup_source_release_ordinal_result_v1",
]
