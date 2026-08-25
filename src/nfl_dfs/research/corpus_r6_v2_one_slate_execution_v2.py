"""Corrected exact-source one-slate execution for outcome-blind R6-v2.

This separately versioned successor leaves the frozen v1 executor intact.  It
reuses v1 only for exact reconstruction of one accepted Foundry v12 panel
member.  Matchup information enters through the corrected three-object seam:
the source export, query receipt, and accepted player catalog are each read at
their exact URI/generation/SHA-256/byte identity before the existing R6-v2
seven-law, five-fold, and distinct all-block final-fit surface is executed.

The module owns no storage client, publisher, CLI, cloud operation, outcome
reader, score, freeze, promotion, or production decision.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from typing import Final

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_matchup_source_v1 as matchup_source
from nfl_dfs.research import corpus_r6_v2_one_slate_execution as execution_v1
from nfl_dfs.research import residual_world_columns as rw


RESULT_SCHEMA: Final = "corpus-r6-v2-one-slate-execution/v2"
REQUIRED_MATCHUP_EVIDENCE_CLASS: Final = matchup_source.EVIDENCE_RETROSPECTIVE
_FALSE_RESULT_AUTHORITY_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "outcome_verdict_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)
_FALSE_MATCHUP_SOURCE_AUTHORITY_FIELDS: Final = (
    "authoritative_pit",
    "fill_authority",
    "retrieval_authority",
    "promotion_authority",
    "production_policy_authority",
)


class CorpusR6V2OneSlateExecutionV2Error(ValueError):
    """The corrected one-slate surface cannot preserve its exact bindings."""


ReadExact = Callable[[Mapping[str, object]], bytes]


def _fail(message: str) -> None:
    raise CorpusR6V2OneSlateExecutionV2Error(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _require_false_fields(
    value: Mapping[str, object],
    fields: Sequence[str],
    *,
    label: str,
) -> None:
    differing = [field for field in fields if value.get(field) is not False]
    if differing:
        _fail(f"{label} carries non-false authority fields {differing}")


def _exact_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a nonnegative exact integer")
    return value


def _accepted_source_authority(
    accepted: execution_v1.AcceptedV12SlateReconstruction,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Derive task and complete catalog authority from the accepted v12 row."""
    reconstructed = accepted.reconstructed
    provenance = _mapping(
        reconstructed.provenance, label="reconstructed candidate provenance"
    )
    provenance_slate = _mapping(
        provenance.get("slate"), label="reconstructed provenance slate"
    )
    prepared = getattr(reconstructed, "prepared", None)
    season = provenance_slate.get("season")
    week = provenance_slate.get("week")
    slate_id = provenance_slate.get("slate_id")
    if (
        type(season) is not int
        or isinstance(season, bool)
        or type(week) is not int
        or isinstance(week, bool)
        or week < 1
        or type(slate_id) is not str
        or not slate_id
        or prepared is None
        or getattr(prepared, "season", None) != season
        or getattr(prepared, "week", None) != week
        or getattr(prepared, "slate_id", None) != slate_id
    ):
        _fail("accepted v12 prepared/provenance slate binding differs")
    membership = _mapping(
        accepted.accepted_slate_membership, label="accepted slate membership"
    )
    task_binding = {
        "task_id": f"slate-{season}-w{week}",
        "slate_id": slate_id,
        "task_ordinal": _exact_int(
            membership.get("task_ordinal"), label="accepted task ordinal"
        ),
        "source_task_ordinal": _exact_int(
            membership.get("source_task_ordinal"),
            label="accepted source task ordinal",
        ),
    }
    raw_players = getattr(prepared, "players", None)
    if isinstance(raw_players, (str, bytes)) or not isinstance(
        raw_players, Sequence
    ):
        _fail("accepted v12 prepared catalog must be an ordered array")
    projection: list[dict[str, object]] = []
    for offset, player in enumerate(raw_players):
        row = {
            "id": getattr(player, "player_id", None),
            "pos": getattr(player, "position", None),
            "team": getattr(player, "team", None),
            "opp": getattr(player, "opponent", None),
            "game_id": getattr(player, "game_id", None),
            "salary": getattr(player, "salary", None),
        }
        if (
            any(type(row[field]) is not str or not row[field] for field in (
                "id", "pos", "team", "opp", "game_id"
            ))
            or type(row["salary"]) is not int
            or isinstance(row["salary"], bool)
            or row["salary"] < 0
        ):
            _fail(f"accepted v12 prepared player[{offset}] structure differs")
        projection.append(row)
    player_ids = [str(row["id"]) for row in projection]
    if (
        not projection
        or player_ids != sorted(player_ids)
        or len(player_ids) != len(set(player_ids))
    ):
        _fail("accepted v12 prepared catalog order/population differs")
    return task_binding, projection


def _exact_matchup_catalog_projection(
    *,
    identity: Mapping[str, object],
    read_exact: ReadExact,
    expected_task_id: str,
) -> list[dict[str, object]]:
    """Exact-read the source catalog and retain its science-relevant fields."""
    try:
        raw = read_exact(dict(identity))
    except matchup_source.CorpusR6MatchupSourceV1Error as exc:
        raise CorpusR6V2OneSlateExecutionV2Error(
            f"matchup player catalog exact reopen failed: {exc}"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity.get("bytes")
        or sha256(raw).hexdigest() != identity.get("sha256")
    ):
        _fail("matchup player catalog content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6V2OneSlateExecutionV2Error(
            "matchup player catalog is not canonical JSON"
        ) from exc
    body = _mapping(parsed, label="matchup player catalog")
    if matchup_source.canonical_json_bytes(body) != raw:
        _fail("matchup player catalog bytes are not canonical")
    if (
        body.get("schema_version") != matchup_source.PLAYER_CATALOG_SCHEMA
        or body.get("task_id") != expected_task_id
    ):
        _fail("matchup player catalog task differs from accepted v12 task")
    raw_players = body.get("players")
    if isinstance(raw_players, (str, bytes)) or not isinstance(
        raw_players, Sequence
    ):
        _fail("matchup player catalog players must be an ordered array")
    projection: list[dict[str, object]] = []
    fields = ("id", "pos", "team", "opp", "game_id", "salary")
    for offset, raw_player in enumerate(raw_players):
        player = _mapping(raw_player, label=f"matchup catalog player[{offset}]")
        if any(field not in player for field in fields):
            _fail(f"matchup catalog player[{offset}] structure differs")
        projection.append({field: player[field] for field in fields})
    return projection


def _validate_matchup_source_for_historical_r6(
    *,
    source_export_identity: Mapping[str, object],
    query_receipt_identity: Mapping[str, object],
    player_catalog_identity: Mapping[str, object],
    expected_slate: Mapping[str, object],
    required_evidence_class: str,
    read_exact: ReadExact,
) -> tuple[dict[str, object], runner.MatchupSourceExactReopen]:
    """Exact-reopen and construct the only runner authority accepted here."""
    if required_evidence_class != REQUIRED_MATCHUP_EVIDENCE_CLASS:
        _fail(
            "corrected historical R6-v2 requires the exact retrospective "
            "prior-period evidence floor"
        )
    if not callable(read_exact):
        _fail("exact reader is not callable")
    try:
        reopened = matchup_source.reopen_matchup_source_snapshot(
            source_export_identity=source_export_identity,
            query_receipt_identity=query_receipt_identity,
            player_catalog_identity=player_catalog_identity,
            read_exact=read_exact,
            expected_slate=expected_slate,
            required_evidence_class=required_evidence_class,
        )
    except matchup_source.CorpusR6MatchupSourceV1Error as exc:
        raise CorpusR6V2OneSlateExecutionV2Error(
            f"corrected matchup source exact reopen failed: {exc}"
        ) from exc
    if (
        reopened.get("schema_version") != matchup_source.REOPENED_SOURCE_SCHEMA
        or reopened.get("evidence_class") != REQUIRED_MATCHUP_EVIDENCE_CLASS
        or reopened.get("authoritative_for_mechanics") is not True
        or reopened.get("uses_realized_outcomes") is not False
        or reopened.get("outcome_columns_read") != []
    ):
        _fail("corrected historical matchup source policy differs")
    _require_false_fields(
        reopened,
        _FALSE_MATCHUP_SOURCE_AUTHORITY_FIELDS,
        label="corrected matchup source",
    )
    authority = runner.MatchupSourceExactReopen(
        source_export_identity=reopened["source_export_identity"],
        query_receipt_identity=reopened["query_receipt_identity"],
        player_catalog_identity=reopened["player_catalog_identity"],
        expected_slate=reopened["slate"],
        required_evidence_class=required_evidence_class,
        read_exact=read_exact,
    )
    return reopened, authority


def execute_one_slate_r6_v2(
    *,
    validated_panel_index: Mapping[str, object],
    panel_index_identity: Mapping[str, object],
    accepted_slate_membership: Mapping[str, object],
    task_acceptance_identity: Mapping[str, object],
    carrier_identity: Mapping[str, object],
    matchup_source_export_identity: Mapping[str, object],
    matchup_query_receipt_identity: Mapping[str, object],
    matchup_player_catalog_identity: Mapping[str, object],
    expected_matchup_slate: Mapping[str, object],
    read_exact: ReadExact,
    required_matchup_evidence_class: str = REQUIRED_MATCHUP_EVIDENCE_CLASS,
    minimum_supported_players: int = 2,
    minimum_completeness: float = 0.5,
    admission_m: int = runner.DEFAULT_ADMISSION_M,
    neutral_replicates: int = runner.DEFAULT_NEUTRAL_REPLICATES,
    neutral_seed_root: str = "r6-v2-neutral-v1",
    worlds_per_block: int | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Execute one accepted slate through the corrected outcome-blind surface."""
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be an exact boolean")
    if require_authoritative and (
        admission_m != runner.DEFAULT_ADMISSION_M
        or worlds_per_block is not None
    ):
        _fail("authoritative one-slate execution cannot override registered doses")
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
        raise CorpusR6V2OneSlateExecutionV2Error(str(exc)) from exc

    accepted_task_binding, accepted_catalog_projection = (
        _accepted_source_authority(accepted)
    )
    imported = accepted.imported
    reconstructed = accepted.reconstructed
    import_receipt = _mapping(
        imported.compatibility_receipt, label="v12 compatibility import"
    )
    provenance = _mapping(
        reconstructed.provenance, label="reconstructed candidate provenance"
    )
    provenance_slate = _mapping(
        provenance.get("slate"), label="reconstructed provenance slate"
    )
    accepted_expected_slate = {
        "season": provenance_slate["season"],
        "week": provenance_slate["week"],
        "slate_id": provenance_slate["slate_id"],
        "task_id": accepted_task_binding["task_id"],
    }
    if dict(_mapping(
        expected_matchup_slate, label="expected matchup slate"
    )) != accepted_expected_slate:
        _fail("caller expected matchup slate differs from accepted v12 task")
    reopened, authority = _validate_matchup_source_for_historical_r6(
        source_export_identity=matchup_source_export_identity,
        query_receipt_identity=matchup_query_receipt_identity,
        player_catalog_identity=matchup_player_catalog_identity,
        expected_slate=accepted_expected_slate,
        required_evidence_class=required_matchup_evidence_class,
        read_exact=read_exact,
    )
    if reopened["slate"].get("task_id") != accepted_task_binding["task_id"]:
        _fail("corrected matchup source task differs from accepted v12 task")
    matchup_catalog_projection = _exact_matchup_catalog_projection(
        identity=reopened["player_catalog_identity"],
        read_exact=read_exact,
        expected_task_id=str(accepted_task_binding["task_id"]),
    )
    if matchup_catalog_projection != accepted_catalog_projection:
        _fail("matchup player catalog differs from accepted v12 catalog")
    if (
        accepted.slate_id != provenance_slate.get("slate_id")
        or {
            key: reopened["slate"].get(key) for key in provenance_slate
        }
        != dict(provenance_slate)
    ):
        _fail("corrected matchup source differs from the accepted v12 slate")
    try:
        summary = runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=authority,
            minimum_supported_players=minimum_supported_players,
            minimum_completeness=minimum_completeness,
        )
        retained_surface = runner.run_retrieval_surface_v2(
            provenance=provenance,
            union_scores=reconstructed.union_scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            matchup_summary=summary,
            matchup_source=authority,
            admission_m=admission_m,
            neutral_replicates=neutral_replicates,
            neutral_seed_root=neutral_seed_root,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
        surface = runner.validate_retrieval_surface_v2(
            retained_surface,
            provenance=provenance,
            union_scores=reconstructed.union_scores,
            reconstruction_receipt=reconstructed.reconstruction_receipt,
            matchup_summary=summary,
            matchup_source=authority,
            admission_m=admission_m,
            neutral_replicates=neutral_replicates,
            neutral_seed_root=neutral_seed_root,
            worlds_per_block=worlds_per_block,
            require_authoritative=require_authoritative,
        )
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6V2OneSlateExecutionV2Error(str(exc)) from exc

    summary = dict(_mapping(summary, label="matchup summary"))
    surface = dict(_mapping(surface, label="retrieval surface"))
    source_export_identity = dict(reopened["source_export_identity"])
    query_receipt_identity = dict(reopened["query_receipt_identity"])
    player_catalog_identity = dict(reopened["player_catalog_identity"])
    export_sha = _sha(
        source_export_identity.get("sha256"),
        label="matchup source export SHA",
    )
    if (
        summary.get("uses_realized_outcomes") is not False
        or summary.get("matchup_source_snapshot_sha256") != export_sha
        or summary.get("matchup_source_schema_version")
        != matchup_source.REOPENED_SOURCE_SCHEMA
        or summary.get("player_catalog_identity") != player_catalog_identity
        or summary.get("annotation_query_receipt_identity")
        != query_receipt_identity
        or surface.get("uses_realized_outcomes") is not False
        or surface.get("promotion_authority") is not False
        or surface.get("require_authoritative") is not require_authoritative
        or surface.get("slate") != dict(provenance_slate)
    ):
        _fail("retrieval surface differs from its exact matchup/v12 authority")
    expected_dose = (
        runner.AUTHORITATIVE_DOSE
        if require_authoritative
        else runner.FIXTURE_DOSE
    )
    if surface.get("dose_authority") != expected_dose:
        _fail("retrieval surface dose authority differs")
    if require_authoritative and (
        surface.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or surface.get("admission_cap") != runner.DEFAULT_ADMISSION_M
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
    matchup_identities = {
        "source_export": source_export_identity,
        "query_receipt": query_receipt_identity,
        "player_catalog": player_catalog_identity,
    }
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
        "matchup_source_export_sha256": export_sha,
        "matchup_query_receipt_sha256": _sha(
            query_receipt_identity.get("sha256"),
            label="matchup query receipt SHA",
        ),
        "matchup_player_catalog_sha256": _sha(
            player_catalog_identity.get("sha256"),
            label="matchup player catalog SHA",
        ),
        "matchup_summary_sha256": _sha(
            summary.get("matchup_summary_sha256"),
            label="matchup summary SHA",
        ),
        "retrieval_surface_sha256": _sha(
            surface.get("retrieval_surface_sha256"),
            label="retrieval surface SHA",
        ),
    }
    body: dict[str, object] = {
        "schema_version": RESULT_SCHEMA,
        "execution_mode": (
            "corrected-retrospective-authoritative-dose-one-slate-mechanics"
            if require_authoritative
            else "corrected-retrospective-fixture-dose-one-slate-mechanics"
        ),
        "slate_id": accepted.slate_id,
        "panel_index_identity": accepted.panel_index_identity,
        "panel_index_sha256": accepted.panel_index_sha256,
        "accepted_slate_membership": accepted.accepted_slate_membership,
        "accepted_slate_membership_sha256": batch.canonical_sha256(
            accepted.accepted_slate_membership
        ),
        "accepted_task_binding": accepted_task_binding,
        "accepted_task_binding_sha256": batch.canonical_sha256(
            accepted_task_binding
        ),
        "accepted_player_catalog_structural_sha256": batch.canonical_sha256(
            accepted_catalog_projection
        ),
        "matchup_player_catalog_structural_sha256": batch.canonical_sha256(
            matchup_catalog_projection
        ),
        "task_acceptance_identity": accepted.task_acceptance_identity,
        "carrier_identity": accepted.carrier_identity,
        "later_source_freeze_identity": accepted.later_source_freeze_identity,
        "world_artifact_identities": accepted.world_artifact_identities,
        "world_artifact_identity_set_sha256": batch.canonical_sha256(
            accepted.world_artifact_identities
        ),
        "matchup_source_identities": matchup_identities,
        "matchup_source_identity_set_sha256": batch.canonical_sha256(
            matchup_identities
        ),
        "matchup_source_export_sha256": export_sha,
        "matchup_source_export_schema_version": (
            matchup_source.SOURCE_EXPORT_SCHEMA
        ),
        "matchup_source_schema_version": reopened["schema_version"],
        "matchup_evidence_class": reopened["evidence_class"],
        "required_matchup_evidence_class": required_matchup_evidence_class,
        "expected_matchup_slate": reopened["slate"],
        "matchup_source_authority": {
            "authoritative_for_mechanics": True,
            **{
                field: reopened[field]
                for field in _FALSE_MATCHUP_SOURCE_AUTHORITY_FIELDS
            },
            "uses_realized_outcomes": False,
        },
        "configuration": {
            "minimum_supported_players": minimum_supported_players,
            "minimum_completeness": float(minimum_completeness),
            "admission_m": admission_m,
            "neutral_replicates": neutral_replicates,
            "neutral_seed_root": neutral_seed_root,
            "worlds_per_block": (
                rw.WORLDS_PER_BLOCK
                if worlds_per_block is None
                else worlds_per_block
            ),
            "require_authoritative": require_authoritative,
        },
        "verification": {
            "panel_content_identity_verified": True,
            "panel_membership_binding_verified": True,
            "task_acceptance_content_identity_verified": True,
            "task_acceptance_carrier_binding_verified": True,
            "carrier_source_receipts_verified": True,
            "matchup_source_export_exact_reopen_verified": True,
            "matchup_query_receipt_exact_reopen_verified": True,
            "matchup_player_catalog_exact_reopen_verified": True,
            "matchup_player_catalog_matches_accepted_v12_verified": True,
            "matchup_task_matches_accepted_v12_verified": True,
            "matchup_source_cross_binding_verified": True,
            "full_seven_law_fold_final_surface_canonical_replay_verified": True,
            "canonical_authoritative_dose_verified": require_authoritative,
        },
        "output_hashes": output_hashes,
        "reconstruction_receipt": reconstruction_receipt,
        "matchup_summary": summary,
        "retrieval_surface": surface,
        **{field: False for field in _FALSE_RESULT_AUTHORITY_FIELDS},
    }
    body["task_result_sha256"] = batch.canonical_sha256(body)
    return body


__all__ = [
    "CorpusR6V2OneSlateExecutionV2Error",
    "REQUIRED_MATCHUP_EVIDENCE_CLASS",
    "RESULT_SCHEMA",
    "execute_one_slate_r6_v2",
]
