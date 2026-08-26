"""Outcome-blind structural freeze for the 54-slate R6 full-union lane.

The fast lane produces one deterministic 48-book result for each accepted
Foundry-v12 slate.  This module turns those results into a compact immutable
chain:

``execution manifest -> 54 task results -> 54 slate leaves -> panel root``.

Full task results retain the selected rosters.  Leaves and the root carry only
content identities and compact hashes, so later grading can exact-open each
result and score the all-block candidate union once without duplicating about
one gigabyte of JSON.  Every 4/14/80 prefix is nevertheless frozen explicitly
by its first-N payload hash.

This module is deliberately pure.  It accepts exact-read callbacks, owns no
storage or warehouse client, has no object-listing operation, and cannot read
realized outcomes.  The root is a structural outcome-blind freeze, not an
independent second replay of the simulated selector.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import corpus_v12_panel_index as panel_index
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


MANIFEST_SCHEMA: Final = "corpus-r6-full-union-freeze-manifest/v1"
TASK_RESULT_OBJECT_SCHEMA: Final = lane.EXECUTION_SCHEMA
TASK_RESULT_ENVELOPE_SCHEMA: Final = "corpus-r6-full-union-task-result-envelope/v1"
RUNTIME_EXECUTION_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-full-union-runtime-execution-evidence/v1"
)
SLATE_FREEZE_SCHEMA: Final = "corpus-r6-full-union-slate-freeze/v1"
SCOPE_DESCRIPTOR_SCHEMA: Final = "corpus-r6-full-union-scope-descriptor/v1"
BOOK_DESCRIPTOR_SCHEMA: Final = "corpus-r6-full-union-book-descriptor/v1"
PREFIX_DESCRIPTOR_SCHEMA: Final = "corpus-r6-full-union-prefix-descriptor/v1"
UNION_DESCRIPTOR_SCHEMA: Final = "corpus-r6-full-union-population-descriptor/v1"
PANEL_FREEZE_SCHEMA: Final = "corpus-r6-full-union-panel-freeze/v1"
PUBLICATION_MODE: Final = "create_once"
AUTHORITATIVE_SLATE_COUNT: Final = panel_index.V12_SOURCE_TASK_COUNT
SCOPE_COUNT: Final = lane.SCOPE_COUNT
BOOKS_PER_SCOPE: Final = lane.BOOKS_PER_SCOPE
BOOKS_PER_SLATE: Final = lane.BOOKS_PER_SLATE
PREFIXES_PER_BOOK: Final = len(lane.PREFIX_SIZES)
PREFIXES_PER_SLATE: Final = BOOKS_PER_SLATE * PREFIXES_PER_BOOK
PANEL_SCOPE_COUNT: Final = AUTHORITATIVE_SLATE_COUNT * SCOPE_COUNT
PANEL_BOOK_COUNT: Final = AUTHORITATIVE_SLATE_COUNT * BOOKS_PER_SLATE
PANEL_PREFIX_COUNT: Final = AUTHORITATIVE_SLATE_COUNT * PREFIXES_PER_SLATE
FIT_SCOPE_IDS: Final = tuple(
    [*(f"holdout-{block}" for block in rw.WORLD_BLOCKS), "all-block-final-fit"]
)
EXPECTED_WORLD_ROLES: Final = tuple(
    f"world_artifact_{block.lower()}" for block in rw.WORLD_BLOCKS
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
_SLATE_ID = re.compile(r"^20[0-9]{2}-w(?:0[1-9]|1[0-8])$")

_FALSE_FIELDS: Final = (
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
_PANEL_FALSE_FIELDS: Final = tuple(
    field for field in _FALSE_FIELDS if field != "r6_freeze_authority"
)
_RESULT_VERIFICATION_FIELDS: Final = frozenset({
    "panel_exact_reopen_verified",
    "accepted_membership_binding_verified",
    "task_acceptance_exact_reopen_verified",
    "carrier_exact_reopen_verified",
    "world_artifact_exact_reopen_verified",
    "all_seven_arm_score_hashes_verified",
    "complete_cross_arm_union_reconstructed",
    "all_48_books_materialized",
    "matchup_source_not_read",
    "realized_outcomes_not_read",
})
_RESULT_FIELDS: Final = frozenset({
    "schema_version", "slate_id", "panel_index_identity",
    "panel_index_sha256", "accepted_slate_membership",
    "accepted_slate_membership_sha256", "task_acceptance_identity",
    "carrier_identity", "later_source_freeze_identity",
    "world_artifact_identities", "world_artifact_identity_set_sha256",
    "compatibility_import_sha256", "candidate_provenance_sha256",
    "reconstruction_sha256", "full_union_surface",
    "full_union_surface_sha256", "verification", "task_result_sha256",
    *_FALSE_FIELDS,
})
_TASK_RESULT_ENVELOPE_FIELDS: Final = frozenset({
    "schema_version", "publication_mode", "target_uri", "manifest_identity",
    "execution_manifest_sha256", "source_ordinal", "slate_id",
    "panel_member_sha256", "source_commit_sha", "immutable_image",
    "runtime_execution_evidence",
    "task_result", "task_result_sha256", "task_result_payload_sha256",
    "structural_freeze_only", "independent_second_selector_replay",
    "task_result_envelope_sha256", *_FALSE_FIELDS,
})
_RUNTIME_EXECUTION_EVIDENCE_FIELDS: Final = frozenset({
    "schema_version", "cloud_project_id", "cloud_project_number",
    "cloud_region", "cloud_job", "cloud_execution", "cloud_execution_uid",
    "cloud_job_uid", "cloud_job_generation", "execution_resource_version",
    "source_ordinal", "task_index", "task_attempt", "task_count",
    "parallelism", "max_retries", "task_timeout_seconds", "immutable_image",
    "service_account", "cpu", "memory", "container_command",
    "container_args", "execution_spec_keys", "execution_template_keys",
    "task_spec_keys",
    "container_keys", "configured_environment", "secret_env_count",
    "volume_count", "volume_mount_count", "network_attachment_count",
    "authenticated_execution_api_read",
    "runtime_execution_evidence_sha256",
})
_RUNTIME_JOBS: Final = frozenset({
    "atlas-minimal-c-s2023-w1-v1",
    "atlas-cbc-32g-full-2023-w8-v1",
})
_RUNTIME_JOB_UIDS: Final = {
    "atlas-minimal-c-s2023-w1-v1": "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2",
    "atlas-cbc-32g-full-2023-w8-v1": "1f4bcf0a-2300-4afa-9fc1-9981844c8275",
}
_RUNTIME_PROJECT_ID: Final = "nfl-predictions-503414"
_RUNTIME_PROJECT_NUMBER: Final = "817589974517"
_RUNTIME_SERVICE_ACCOUNT: Final = (
    "817589974517-compute@developer.gserviceaccount.com"
)
_RUNTIME_REGION: Final = "us-central1"
_RUNTIME_TIMEOUT_SECONDS: Final = 7_200
_RUNTIME_EXECUTION_SPEC_KEYSETS: Final = frozenset({
    frozenset({"parallelism", "taskCount", "template"}),
})
_RUNTIME_EXECUTION_TEMPLATE_KEYSETS: Final = frozenset({
    frozenset({"spec"}),
})
_RUNTIME_TASK_SPEC_KEYSETS: Final = frozenset({
    frozenset({"containers", "maxRetries", "serviceAccountName", "timeoutSeconds"}),
    frozenset({
        "containers", "maxRetries", "serviceAccountName", "timeoutSeconds",
        "volumes",
    }),
})
_RUNTIME_CONTAINER_KEYSETS: Final = frozenset({
    frozenset({"args", "command", "env", "image", "resources"}),
    frozenset({
        "args", "command", "env", "image", "resources", "volumeMounts",
    }),
})
_SURFACE_FIELDS: Final = frozenset({
    "schema_version", "slate", "candidate_provenance_sha256",
    "reconstruction_sha256", "strategy_registry", "strategy_registry_sha256",
    "scope_count", "books_per_scope", "book_count", "prefix_sizes", "scopes",
    "rotated_simulated_fold_count", "final_fit_is_distinct_all_block_refit",
    "full_union_only", "matchup_source_read", "uses_realized_outcomes",
    "evidence_tier", "promotion_authority", "full_union_surface_sha256",
})
_SCOPE_FIELDS: Final = frozenset({
    "schema_version", "fit_scope_id", "reconstruction_sha256",
    "training_blocks", "heldout_block", "worlds_per_block", "dose_authority",
    "require_authoritative", "candidate_view", "admission", "admission_mode",
    "matchup_source_read", "matchup_admission_read", "neutral_control_read",
    "strategy_registry", "strategy_count", "book_count", "books",
    "uses_realized_outcomes", "promotion_authority", "fit_scope_sha256",
})
_CANDIDATE_VIEW_FIELDS: Final = frozenset({
    "schema_version", "slate", "fit_scope_id", "training_blocks",
    "heldout_block", "eligible_candidates", "excluded_candidates_audit",
    "eligible_count", "excluded_count", "dose_authority",
    "selection_inputs_exclude_heldout_occurrences", "uses_realized_outcomes",
    "fit_candidate_view_sha256", "selection_provenance_sha256",
})
_ELIGIBLE_FIELDS: Final = frozenset({
    "lineup_id", "roster_player_ids", "training_origin_blocks",
    "training_source_arms", "training_occurrence_counts_by_block",
    "training_source_arms_by_block", "training_occurrence_count",
})
_EXCLUDED_FIELDS: Final = frozenset({
    "lineup_id", "reason_code", "heldout_origin_present",
})
_ADMISSION_FIELDS: Final = frozenset({
    "schema_version", "admission_id", "fit_scope_id",
    "selection_provenance_sha256", "admitted_lineup_ids", "admitted_count",
    "excluded_eligible_candidates", "dose_authority", "admission_inputs",
    "uses_simulated_scores", "uses_matchup_values", "uses_realized_outcomes",
    "admission_sha256",
})
_BOOK_FIELDS: Final = frozenset({
    "schema_version", "book_id", "fit_scope_id", "reconstruction_sha256",
    "training_blocks", "heldout_block", "admission_id", "admission_sha256",
    "strategy_id", "strategy_sha256", "strategy_application_scope",
    "input_lineup_ids_sha256", "training_score_matrix_sha256",
    "training_score_shape", "worlds_per_block", "dose_authority",
    "selected_local_indices", "selected_global_indices", "selected_lineup_ids",
    "selected_rosters", "entry_count", "marginal_trace", "training_metrics",
    "redundancy_diagnostics", "heldout_metrics_descriptive",
    "threshold_semantics", "uses_realized_outcomes", "promotion_authority",
    "book_sha256",
})
_REGISTERED_OPEN_BOOK_MAPPING_SCHEMAS: Final = frozenset({
    frozenset({"aggregate", "by_block"}),
    frozenset({
        "expected_book_max", "lineup_count", "maximum_book_score",
        "world_count", "worlds_ge_194", "worlds_gt_200", "worlds_gt_210",
        "worlds_gt_220",
    }),
    frozenset({
        "block_id", "expected_book_max", "lineup_count", "maximum_book_score",
        "world_count", "worlds_ge_194", "worlds_gt_200", "worlds_gt_210",
        "worlds_gt_220",
    }),
    frozenset({
        "schema_version", "selected_rosters_sha256",
        "selected_score_matrix_sha256", "distinct_player_count",
        "maximum_player_exposure_count", "player_exposure_count_histogram",
        "lineup_pair_count", "shared_player_count_histogram",
        "simulated_outcome_event_redundancy", "pairwise_score_correlation",
        "correlation_replay_source", "uses_realized_outcomes",
        "redundancy_diagnostics_sha256",
    }),
    frozenset({
        "schema_version", "representation", "selection_law", "pair_sample_cap",
        "pair_population_count", "sampled_pair_count", "defined_pair_count",
        "constant-series-pair-count", "minimum", "maximum", "mean", "rows",
        "pairwise_correlation_sha256", "full_pairwise_materialized",
        "uses_realized_outcomes",
    }),
    frozenset({"defined", "left_lineup_id", "pearson_correlation", "right_lineup_id"}),
    frozenset({"lineup_count", "player_count"}),
    frozenset({"lineup_pair_count", "shared_player_count"}),
    frozenset({
        "book_covered_world_count", "label", "operator",
        "redundant_event_count_beyond_first_book_cover", "redundant_event_fraction",
        "selected_lineup_event_count_maximum", "selected_lineup_event_count_mean",
        "selected_lineup_event_count_minimum", "selected_lineup_event_count_sum",
        "threshold",
    }),
    frozenset({"label", "operator", "threshold"}),
    frozenset({
        "admitted_lineup_index", "base_trace", "block_contributions",
        "global_lineup_index", "lineup_id", "objective_after",
        "objective_before", "objective_gain", "objective_law", "selection_rank",
        "threshold_contributions", "tie_break_values",
    }),
    frozenset({
        "discovery_mean_score", "discovery_primary_event_count", "lineup_id",
        "lineup_index", "marginal_utility", "selection_rank",
    }),
    frozenset({
        "block_utilities_added", "block_utilities_after", "block_utilities_before",
        "discovery_mean_score", "discovery_primary_event_count",
        "leximin_profile_after", "lineup_id", "lineup_index", "marginal_utility",
        "selection_rank",
    }),
    frozenset({
        "individual_selector_event_count", "selector_event_definition",
        "stable_lineup_id", "training_mean_score",
    }),
    frozenset({"operator", "threshold"}),
    frozenset({"block_id", "objective_after", "objective_before", "objective_gain"}),
    frozenset({"new_world_count", "operator", "threshold", "weight", "weighted_utility"}),
    frozenset({
        "new_world_count", "operator", "support_factor", "threshold", "weight",
        "weighted_utility",
    }),
    frozenset({
        "label", "new_book_world_count", "operator", "threshold",
    }),
    frozenset({
        "label", "objective_contribution", "operator",
        "selected_lineup_event_count", "threshold",
    }),
    frozenset({"block_utilities", "leximin_profile"}),
    frozenset({"block_utility_delta", "marginal_utility_sum"}),
})

ReadExact = Callable[[Mapping[str, object]], bytes]


class CorpusR6FullUnionPanelFreezeV1Error(ValueError):
    """The full-union freeze cannot preserve its exact structural chain."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionPanelFreezeV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str] | set[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} field set differs")


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionPanelFreezeV1Error(str(exc)) from exc


def _identity_key(value: object, *, label: str) -> tuple[str, str, str, int]:
    item = _identity(value, label=label)
    return (
        str(item["uri"]), str(item["generation"]),
        str(item["sha256"]), int(item["bytes"]),
    )


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    digest = _sha(value.get(field), label=f"{label}.{field}")
    if batch.canonical_sha256({k: v for k, v in value.items() if k != field}) != digest:
        _fail(f"{label} self-hash differs")
    return digest


def _false_fields(value: Mapping[str, object], *, label: str) -> None:
    if any(value.get(field) is not False for field in _FALSE_FIELDS):
        _fail(f"{label} carries forbidden outcome or decision authority")


def _reject_nested_result_or_authority(
    value: object,
    *,
    label: str,
    allow_outcome_key_projection_inputs_frozen: bool = False,
) -> None:
    """Reject any unregistered realized/contest/authority field at any depth."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string key")
            if key == "outcome_key_projection_inputs_frozen":
                if not allow_outcome_key_projection_inputs_frozen or item is not True:
                    _fail(
                        f"{label}.{key} must be the top-level boolean true flag"
                    )
            if key == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.{key} must be false")
            if key in _FALSE_FIELDS and item is not False:
                _fail(f"{label}.{key} must be false")
            if key == "realized_outcomes_not_read" and item is not True:
                _fail(f"{label}.{key} must be true")
            if (
                "outcome" in key
                and key not in {
                    "uses_realized_outcomes",
                    "realized_outcomes_not_read",
                    "outcome_key_projection_inputs_frozen",
                }
                and not key.startswith("simulated_outcome")
            ):
                _fail(f"{label} contains an unregistered outcome field")
            if (
                "realized" in key
                and key not in {"uses_realized_outcomes", "realized_outcomes_not_read"}
            ):
                _fail(f"{label} contains an unregistered realized-result field")
            if any(token in key for token in ("actual", "contest", "payout", "points")):
                _fail(f"{label} contains an unregistered result field")
            if (
                "authority" in key
                and key not in {*_FALSE_FIELDS, "dose_authority"}
                and not key.endswith("_authority_sha256")
            ):
                _fail(f"{label} contains an unregistered authority field")
            _reject_nested_result_or_authority(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_nested_result_or_authority(item, label=f"{label}[{ordinal}]")


def _validate_registered_open_book_payload(value: object, *, label: str) -> None:
    """Exact-schema the intentionally nested diagnostics and selector traces."""
    if isinstance(value, Mapping):
        keys = frozenset(value)
        if keys not in _REGISTERED_OPEN_BOOK_MAPPING_SCHEMAS:
            _fail(f"{label} contains an unregistered nested mapping schema")
        for key, item in value.items():
            _validate_registered_open_book_payload(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _validate_registered_open_book_payload(item, label=f"{label}[{ordinal}]")
    elif value is not None and type(value) not in {str, int, float, bool}:
        _fail(f"{label} contains an unregistered nested value type")


def _exact_read_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionPanelFreezeV1Error(str(exc)) from exc
    return _mapping(value, label=label), identity


def _bind_identity_to_body(
    identity_value: object, body: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = batch.canonical_json_bytes(dict(body))
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail(f"{label} body differs from its outer content identity")
    return identity


def _fixed_panel_identity() -> dict[str, object]:
    return _identity(adapter.FIXED_PANEL_IDENTITY, label="fixed panel identity")


def _fixed_later_source_identity() -> dict[str, object]:
    try:
        pins = adapter._normalize_pins(adapter.FIXED_PINS)
    except Exception as exc:  # pragma: no cover - static production constant
        raise CorpusR6FullUnionPanelFreezeV1Error(
            "fixed later-source pins are unavailable"
        ) from exc
    return _identity(pins["later_source_identity"], label="fixed later source")


def validate_fixed_panel_v1(value: object) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Validate the exact complete fixed-G0 panel projection."""
    item = _mapping(value, label="fixed G0 panel")
    _self_hash(item, field="panel_index_sha256", label="fixed G0 panel")
    members = [
        _mapping(member, label=f"panel member[{ordinal}]")
        for ordinal, member in enumerate(
            _sequence(item.get("accepted_slates"), label="panel members")
        )
    ]
    coverage = _mapping(item.get("coverage"), label="panel coverage")
    if (
        item.get("schema_version") != panel_index.PANEL_INDEX_SCHEMA
        or item.get("publication_mode") != panel_index.PUBLICATION_MODE
        or item.get("panel_id") != adapter.FIXED_PANEL_ID
        or item.get("panel_index_sha256") != adapter.FIXED_PANEL_INDEX_SHA256
        or item.get("lane_count") != 2
        or item.get("accepted_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or len(members) != AUTHORITATIVE_SLATE_COUNT
        or item.get("exclusions") != []
        or item.get("failures") != []
        or item.get("missing_tasks") != []
        or coverage != {
            "expected_task_count": AUTHORITATIVE_SLATE_COUNT,
            "accepted_task_count": AUTHORITATIVE_SLATE_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        }
        or any(item.get(field) is not False for field in _PANEL_FALSE_FIELDS)
    ):
        _fail("fixed G0 panel identity, coverage, or authority differs")
    seen_slates: set[str] = set()
    seen_acceptances: set[tuple[str, str, str, int]] = set()
    seen_carriers: set[tuple[str, str, str, int]] = set()
    seen_arms: set[tuple[str, str, str, int]] = set()
    for source_ordinal, member in enumerate(members):
        slate_id = member.get("slate_id")
        expected_lane = 0 if source_ordinal < 28 else 1
        expected_task = source_ordinal if expected_lane == 0 else source_ordinal - 28
        arms = _sequence(member.get("arms"), label=f"panel member[{source_ordinal}] arms")
        if (
            type(slate_id) is not str
            or _SLATE_ID.fullmatch(slate_id) is None
            or slate_id in seen_slates
            or member.get("source_task_ordinal") != source_ordinal
            or member.get("lane_ordinal") != expected_lane
            or member.get("lane_id") != ("v12a" if expected_lane == 0 else "v12b")
            or member.get("task_ordinal") != expected_task
            or len(arms) != len(batch.PARAMETER_SET_ORDER)
            or _SHA256.fullmatch(str(member.get("source_task_authority_sha256"))) is None
        ):
            _fail(f"panel member[{source_ordinal}] order or identity differs")
        seen_slates.add(slate_id)
        acceptance_key = _identity_key(
            member.get("task_acceptance_identity"),
            label=f"panel member[{source_ordinal}] acceptance",
        )
        carrier_key = _identity_key(
            member.get("carrier_identity"),
            label=f"panel member[{source_ordinal}] carrier",
        )
        if acceptance_key in seen_acceptances or carrier_key in seen_carriers:
            _fail("panel acceptance or carrier identity repeats")
        seen_acceptances.add(acceptance_key)
        seen_carriers.add(carrier_key)
        for arm_ordinal, raw_arm in enumerate(arms):
            arm = _mapping(raw_arm, label=f"panel member[{source_ordinal}] arm[{arm_ordinal}]")
            if (
                arm.get("arm_ordinal") != arm_ordinal
                or arm.get("parameter_set_id") != batch.PARAMETER_SET_ORDER[arm_ordinal]
            ):
                _fail("panel arm order differs")
            arm_key = _identity_key(arm.get("result_identity"), label="panel arm result")
            if arm_key in seen_arms:
                _fail("panel arm result identity repeats")
            seen_arms.add(arm_key)
    return item, members


def reopen_fixed_panel_v1(
    panel_identity: object, *, read_exact: ReadExact,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    identity = _identity(panel_identity, label="panel index identity")
    if identity != _fixed_panel_identity():
        _fail("panel identity differs from accepted fixed G0")
    panel, reopened_identity = _exact_read_json(
        identity, read_exact=read_exact, label="fixed G0 panel"
    )
    normalized, members = validate_fixed_panel_v1(panel)
    return normalized, members, reopened_identity


def _output_prefix(value: object) -> str:
    if type(value) is not str or not value.startswith("gs://") or not value.endswith("/"):
        _fail("output prefix must be an explicit GCS prefix ending in /")
    retained = value.removeprefix("gs://")
    if (
        not retained
        or retained.startswith("/")
        or "//" in retained
        or any(part in {"", ".", ".."} for part in retained.split("/" )[:-1])
    ):
        _fail("output prefix differs")
    return value


def _commit(value: object) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail("source commit must be one exact lowercase 40-hex SHA")
    return value


def _immutable_image(value: object) -> str:
    if type(value) is not str or _IMAGE.fullmatch(value) is None:
        _fail("immutable image must be digest-pinned")
    return value


def _source_member_descriptors(
    members: Sequence[Mapping[str, object]], *, output_prefix: str,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    uris: set[str] = set()
    for source_ordinal, raw_member in enumerate(members):
        member = _mapping(raw_member, label=f"panel member[{source_ordinal}]")
        slate_id = str(member["slate_id"])
        prefix = f"{output_prefix}slates/{source_ordinal:02d}-{slate_id}/"
        task_result_uri = f"{prefix}task-result.json"
        slate_freeze_uri = f"{prefix}slate-freeze.json"
        if task_result_uri in uris or slate_freeze_uri in uris:
            _fail("source-member output URI repeats")
        uris.update((task_result_uri, slate_freeze_uri))
        rows.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "panel_member_sha256": batch.canonical_sha256(member),
            "task_acceptance_identity": _identity(
                member["task_acceptance_identity"],
                label=f"source member[{source_ordinal}] acceptance",
            ),
            "carrier_identity": _identity(
                member["carrier_identity"],
                label=f"source member[{source_ordinal}] carrier",
            ),
            "task_result_uri": task_result_uri,
            "slate_freeze_uri": slate_freeze_uri,
        })
    return rows


def build_execution_manifest_v1(
    *,
    panel_index_identity: object,
    exact_panel_index: Mapping[str, object],
    source_commit_sha: str,
    immutable_image: str,
    output_prefix: str,
) -> dict[str, object]:
    """Build the one immutable execution manifest for all 54 slate workers."""
    panel, members = validate_fixed_panel_v1(exact_panel_index)
    panel_identity = _bind_identity_to_body(
        panel_index_identity, panel, label="fixed G0 panel"
    )
    if panel_identity != _fixed_panel_identity():
        _fail("manifest panel identity differs from accepted fixed G0")
    commit = _commit(source_commit_sha)
    image = _immutable_image(immutable_image)
    prefix = _output_prefix(output_prefix)
    strategies = lane.frozen_full_union_strategies_v1()
    source_members = _source_member_descriptors(members, output_prefix=prefix)
    body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "manifest_id": "r6-full-union:" + batch.canonical_sha256({
            "panel_index_identity": panel_identity,
            "source_commit_sha": commit,
            "immutable_image": image,
            "output_prefix": prefix,
        }),
        "source_commit_sha": commit,
        "immutable_image": image,
        "output_prefix": prefix,
        "target_uri": f"{prefix}execution-manifest.json",
        "panel_index_identity": panel_identity,
        "panel_index_sha256": panel["panel_index_sha256"],
        "accepted_slates_sha256": batch.canonical_sha256(members),
        "later_source_freeze_identity": _fixed_later_source_identity(),
        "strategy_registry": strategies,
        "strategy_registry_sha256": batch.canonical_sha256(strategies),
        "execution_lattice": {
            "source_slate_count": AUTHORITATIVE_SLATE_COUNT,
            "scope_count_per_slate": SCOPE_COUNT,
            "books_per_scope": BOOKS_PER_SCOPE,
            "books_per_slate": BOOKS_PER_SLATE,
            "prefix_sizes": list(lane.PREFIX_SIZES),
            "prefixes_per_book": PREFIXES_PER_BOOK,
            "prefixes_per_slate": PREFIXES_PER_SLATE,
            "entry_budget": lane.ENTRY_BUDGET,
            "world_blocks": list(rw.WORLD_BLOCKS),
            "worlds_per_block": rw.WORLDS_PER_BLOCK,
            "world_count_per_slate": len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK,
            "fit_scope_ids": list(FIT_SCOPE_IDS),
            "full_union_only": True,
            "prefix_law": "first-n-of-one-immutable-rank-80",
        },
        "source_member_count": len(source_members),
        "source_members": source_members,
        "source_members_sha256": batch.canonical_sha256(source_members),
        "panel_freeze_uri": f"{prefix}panel-freeze.json",
        "structural_freeze_only": True,
        "independent_second_selector_replay": False,
        **{field: False for field in _FALSE_FIELDS},
    }
    return _with_hash(body, field="execution_manifest_sha256")


def validate_execution_manifest_v1(
    value: object, *, exact_panel_index: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="execution manifest")
    _self_hash(item, field="execution_manifest_sha256", label="execution manifest")
    _false_fields(item, label="execution manifest")
    _reject_nested_result_or_authority(item, label="execution manifest")
    expected = build_execution_manifest_v1(
        panel_index_identity=item.get("panel_index_identity"),
        exact_panel_index=exact_panel_index,
        source_commit_sha=str(item.get("source_commit_sha")),
        immutable_image=str(item.get("immutable_image")),
        output_prefix=str(item.get("output_prefix")),
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("execution manifest canonical replay differs")
    return expected


def reopen_execution_manifest_v1(
    manifest_identity: object, *, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
    manifest, retained_identity = _exact_read_json(
        manifest_identity, read_exact=read_exact, label="execution manifest"
    )
    panel, members, _ = reopen_fixed_panel_v1(
        manifest.get("panel_index_identity"), read_exact=read_exact
    )
    validated = validate_execution_manifest_v1(
        manifest, exact_panel_index=panel
    )
    _bind_identity_to_body(retained_identity, validated, label="execution manifest")
    if retained_identity["uri"] != validated["target_uri"]:
        _fail("execution manifest outer URI differs from its designated target")
    return validated, panel, members, retained_identity


def _validate_candidate_view_and_admission(
    *,
    candidate_view_value: object,
    admission_value: object,
    expected_slate: Mapping[str, object],
    fit_scope_id: str,
    training_blocks: Sequence[str],
    heldout_block: str | None,
) -> tuple[dict[str, object], dict[str, object], list[str], dict[str, list[str]]]:
    candidate_view = _mapping(candidate_view_value, label="fold candidate view")
    admission = _mapping(admission_value, label="full-union admission")
    _exact_keys(candidate_view, _CANDIDATE_VIEW_FIELDS, label="fold candidate view")
    _exact_keys(admission, _ADMISSION_FIELDS, label="full-union admission")
    _self_hash(
        candidate_view,
        field="fit_candidate_view_sha256",
        label="fold candidate view",
    )
    _self_hash(admission, field="admission_sha256", label="full-union admission")
    eligible_rows = _sequence(
        candidate_view.get("eligible_candidates"), label="eligible candidates"
    )
    excluded_rows = _sequence(
        candidate_view.get("excluded_candidates_audit"), label="excluded candidates"
    )
    eligible_ids: list[str] = []
    roster_by_id: dict[str, list[str]] = {}
    for ordinal, raw_row in enumerate(eligible_rows):
        row = _mapping(raw_row, label=f"eligible candidate[{ordinal}]")
        _exact_keys(row, _ELIGIBLE_FIELDS, label=f"eligible candidate[{ordinal}]")
        lineup_id = row.get("lineup_id")
        roster = _sequence(row.get("roster_player_ids"), label="eligible roster")
        origin_blocks = _sequence(
            row.get("training_origin_blocks"), label="eligible origin blocks"
        )
        occurrence_counts = _mapping(
            row.get("training_occurrence_counts_by_block"),
            label="eligible occurrence counts",
        )
        arms_by_block = _mapping(
            row.get("training_source_arms_by_block"),
            label="eligible source arms by block",
        )
        source_arms = _sequence(
            row.get("training_source_arms"), label="eligible source arms"
        )
        if (
            type(lineup_id) is not str
            or not lineup_id
            or lineup_id in roster_by_id
            or len(roster) != rw.ROSTER_SIZE
            or roster != sorted(roster)
            or len(set(roster)) != rw.ROSTER_SIZE
            or any(type(player_id) is not str or not player_id for player_id in roster)
            or canonical_lineup_id(expected_slate, roster) != lineup_id
            or set(occurrence_counts) != set(training_blocks)
            or set(arms_by_block) != set(training_blocks)
            or any(type(count) is not int or count < 0 for count in occurrence_counts.values())
            or origin_blocks
            != [block for block in training_blocks if occurrence_counts.get(block)]
            or source_arms != sorted(set(source_arms))
            or any(arm not in batch.PARAMETER_SET_ORDER for arm in source_arms)
            or row.get("training_occurrence_count")
            != sum(int(count) for count in occurrence_counts.values())
        ):
            _fail("eligible full-union candidate differs")
        for block, raw_arms in arms_by_block.items():
            block_arms = _sequence(raw_arms, label=f"eligible source arms {block}")
            if (
                block_arms != sorted(set(block_arms))
                or any(arm not in batch.PARAMETER_SET_ORDER for arm in block_arms)
                or (int(occurrence_counts[block]) == 0) != (block_arms == [])
            ):
                _fail("eligible block source-arm evidence differs")
        eligible_ids.append(lineup_id)
        roster_by_id[lineup_id] = [str(player_id) for player_id in roster]
    for ordinal, raw_row in enumerate(excluded_rows):
        row = _mapping(raw_row, label=f"excluded candidate[{ordinal}]")
        _exact_keys(row, _EXCLUDED_FIELDS, label=f"excluded candidate[{ordinal}]")
        if (
            type(row.get("lineup_id")) is not str
            or row.get("reason_code") != "heldout-only-origin"
            or heldout_block is None
            or row.get("heldout_origin_present") is not True
        ):
            _fail("excluded candidate audit differs")
    selection_projection = {
        "schema_version": "corpus-fold-selection-provenance/v2",
        "slate": dict(expected_slate),
        "fit_scope_id": fit_scope_id,
        "training_blocks": list(training_blocks),
        "eligible_candidates": eligible_rows,
        "dose_authority": runner.AUTHORITATIVE_DOSE,
        "uses_realized_outcomes": False,
    }
    admitted_ids = _sequence(
        admission.get("admitted_lineup_ids"), label="admitted lineup IDs"
    )
    if (
        candidate_view.get("schema_version") != "corpus-fold-candidate-view/v2"
        or candidate_view.get("slate") != dict(expected_slate)
        or candidate_view.get("fit_scope_id") != fit_scope_id
        or candidate_view.get("training_blocks") != list(training_blocks)
        or candidate_view.get("heldout_block") != heldout_block
        or candidate_view.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or candidate_view.get("selection_inputs_exclude_heldout_occurrences") is not True
        or candidate_view.get("uses_realized_outcomes") is not False
        or eligible_ids != sorted(set(eligible_ids))
        or len(eligible_ids) < lane.ENTRY_BUDGET
        or candidate_view.get("eligible_count") != len(eligible_ids)
        or candidate_view.get("excluded_count") != len(excluded_rows)
        or candidate_view.get("selection_provenance_sha256")
        != batch.canonical_sha256(selection_projection)
        or admission.get("schema_version") != runner.ADMISSION_SCHEMA
        or admission.get("admission_id") != runner.FULL_UNION_ADMISSION_ID
        or admission.get("fit_scope_id") != fit_scope_id
        or admission.get("selection_provenance_sha256")
        != candidate_view.get("selection_provenance_sha256")
        or admission.get("admission_inputs")
        != "fold-local-provenance-and-stable-lineup-id-only"
        or admitted_ids != eligible_ids
        or admission.get("admitted_count") != len(eligible_ids)
        or admission.get("excluded_eligible_candidates") != []
        or admission.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or admission.get("uses_simulated_scores") is not False
        or admission.get("uses_matchup_values") is not False
        or admission.get("uses_realized_outcomes") is not False
    ):
        _fail("complete fold-eligible union admission differs")
    try:
        runner._validate_admission_partition(admission, eligible_ids=eligible_ids)
    except runner.CorpusBatchRetrievalV2Error as exc:
        raise CorpusR6FullUnionPanelFreezeV1Error(str(exc)) from exc
    return candidate_view, admission, eligible_ids, roster_by_id


def _validate_book_v1(
    value: object,
    *,
    strategy: Mapping[str, object],
    expected_slate: Mapping[str, object],
    heldout_block: str | None,
    training_blocks: Sequence[str],
    fit_scope_id: str,
    reconstruction_sha256: str,
    admission: Mapping[str, object],
    admitted_ids: Sequence[str],
    roster_by_id: Mapping[str, Sequence[str]],
    global_index_by_id: Mapping[str, int],
    seen_book_ids: set[str],
) -> dict[str, object]:
    book = _mapping(value, label="full-union book")
    _exact_keys(book, _BOOK_FIELDS, label="full-union book")
    _self_hash(book, field="book_sha256", label="full-union book")
    lineup_ids = _sequence(book.get("selected_lineup_ids"), label="selected IDs")
    rosters = _sequence(book.get("selected_rosters"), label="selected rosters")
    selected_local = _sequence(
        book.get("selected_local_indices"), label="selected local indices"
    )
    selected_global = _sequence(
        book.get("selected_global_indices"), label="selected global indices"
    )
    traces = _sequence(book.get("marginal_trace"), label="marginal trace")
    book_id = book.get("book_id")
    expected_scope_law = (
        "explicit-all-five-block-final-fit"
        if heldout_block is None
        else "explicit-rotated-training-blocks"
    )
    if (
        type(book_id) is not str
        or not book_id
        or book_id in seen_book_ids
        or book.get("schema_version") != runner.BOOK_SCHEMA
        or book.get("fit_scope_id") != fit_scope_id
        or book.get("reconstruction_sha256") != reconstruction_sha256
        or book.get("training_blocks") != list(training_blocks)
        or book.get("heldout_block") != heldout_block
        or book.get("strategy_id") != strategy.get("strategy_id")
        or book.get("strategy_sha256") != strategy.get("strategy_sha256")
        or book.get("strategy_application_scope") != expected_scope_law
        or book.get("admission_id") != admission.get("admission_id")
        or book.get("admission_sha256") != admission.get("admission_sha256")
        or book.get("input_lineup_ids_sha256")
        != batch.canonical_sha256(list(admitted_ids))
        or book.get("training_score_shape")
        != [len(admitted_ids), len(training_blocks) * rw.WORLDS_PER_BLOCK]
        or _SHA256.fullmatch(str(book.get("training_score_matrix_sha256"))) is None
        or book.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or book.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or book.get("entry_count") != lane.ENTRY_BUDGET
        or len(lineup_ids) != lane.ENTRY_BUDGET
        or len(set(lineup_ids)) != lane.ENTRY_BUDGET
        or len(rosters) != lane.ENTRY_BUDGET
        or len(selected_local) != lane.ENTRY_BUDGET
        or len(set(selected_local)) != lane.ENTRY_BUDGET
        or len(selected_global) != lane.ENTRY_BUDGET
        or len(set(selected_global)) != lane.ENTRY_BUDGET
        or len(traces) != lane.ENTRY_BUDGET
        or any(type(index) is not int or not 0 <= index < len(admitted_ids) for index in selected_local)
        or lineup_ids != [admitted_ids[int(index)] for index in selected_local]
        or any(lineup_id not in global_index_by_id for lineup_id in lineup_ids)
        or selected_global != [global_index_by_id[str(lineup_id)] for lineup_id in lineup_ids]
        or book.get("uses_realized_outcomes") is not False
        or book.get("promotion_authority") is not False
    ):
        _fail("full-union exact-80 book differs")
    for field in (
        "training_metrics", "redundancy_diagnostics", "threshold_semantics",
        "marginal_trace",
    ):
        _validate_registered_open_book_payload(
            book.get(field), label=f"full-union book.{field}"
        )
    if book.get("heldout_metrics_descriptive") is not None:
        _validate_registered_open_book_payload(
            book.get("heldout_metrics_descriptive"),
            label="full-union book.heldout_metrics_descriptive",
        )
    redundancy = _mapping(
        book.get("redundancy_diagnostics"), label="redundancy diagnostics"
    )
    _self_hash(
        redundancy,
        field="redundancy_diagnostics_sha256",
        label="redundancy diagnostics",
    )
    pairwise = _mapping(
        redundancy.get("pairwise_score_correlation"),
        label="pairwise score correlation",
    )
    _self_hash(
        pairwise,
        field="pairwise_correlation_sha256",
        label="pairwise score correlation",
    )
    if (
        redundancy.get("schema_version")
        != "corpus-book-redundancy-diagnostics/v1"
        or redundancy.get("selected_rosters_sha256")
        != batch.canonical_sha256(rosters)
        or _SHA256.fullmatch(
            str(redundancy.get("selected_score_matrix_sha256"))
        ) is None
        or redundancy.get("correlation_replay_source")
        != "bound-selected-score-matrix"
        or redundancy.get("uses_realized_outcomes") is not False
        or pairwise.get("schema_version")
        != "corpus-bounded-pairwise-score-correlation/v1"
        or pairwise.get("uses_realized_outcomes") is not False
    ):
        _fail("book redundancy diagnostic binding differs")
    _reject_nested_result_or_authority(book, label="full-union book")
    for rank, (lineup_id, raw_roster, raw_trace) in enumerate(
        zip(lineup_ids, rosters, traces, strict=True)
    ):
        roster = _sequence(raw_roster, label=f"selected roster[{rank}]")
        trace = _mapping(raw_trace, label=f"marginal trace[{rank}]")
        if (
            len(roster) != rw.ROSTER_SIZE
            or roster != sorted(roster)
            or len(set(roster)) != rw.ROSTER_SIZE
            or any(type(player_id) is not str or not player_id for player_id in roster)
            or canonical_lineup_id(expected_slate, roster) != lineup_id
            or roster != list(roster_by_id[str(lineup_id)])
            or trace.get("selection_rank") != rank
            or trace.get("lineup_id") != lineup_id
            or trace.get("global_lineup_index") != selected_global[rank]
            or trace.get("admitted_lineup_index") != selected_local[rank]
        ):
            _fail("selected book rank/roster/trace alignment differs")
    seen_book_ids.add(str(book_id))
    return book


def validate_task_result_v1(
    value: object,
    *,
    panel_index_identity: object,
    panel_index_sha256: str,
    panel_member: Mapping[str, object],
) -> dict[str, object]:
    """Deep structural validation generalized from the passing task-0 smoke."""
    result = _mapping(value, label="full-union task result")
    _exact_keys(result, _RESULT_FIELDS, label="full-union task result")
    _self_hash(result, field="task_result_sha256", label="full-union task result")
    _false_fields(result, label="full-union task result")
    _reject_nested_result_or_authority(result, label="full-union task result")
    member = _mapping(panel_member, label="panel member")
    slate_id = member.get("slate_id")
    membership = _mapping(
        result.get("accepted_slate_membership"), label="result membership"
    )
    worlds = _mapping(
        result.get("world_artifact_identities"), label="result world identities"
    )
    verification = _mapping(result.get("verification"), label="result verification")
    if (
        result.get("schema_version") != TASK_RESULT_OBJECT_SCHEMA
        or result.get("slate_id") != slate_id
        or _identity(result.get("panel_index_identity"), label="result panel")
        != _identity(panel_index_identity, label="expected result panel")
        or result.get("panel_index_sha256") != panel_index_sha256
        or batch.canonical_json_bytes(membership) != batch.canonical_json_bytes(member)
        or result.get("accepted_slate_membership_sha256")
        != batch.canonical_sha256(member)
        or _identity(result.get("task_acceptance_identity"), label="result acceptance")
        != _identity(member.get("task_acceptance_identity"), label="member acceptance")
        or _identity(result.get("carrier_identity"), label="result carrier")
        != _identity(member.get("carrier_identity"), label="member carrier")
        or _identity(result.get("later_source_freeze_identity"), label="later source")
        != _fixed_later_source_identity()
        or set(worlds) != set(EXPECTED_WORLD_ROLES)
        or {
            role: _identity(identity, label=f"result world {role}")
            for role, identity in worlds.items()
        } != worlds
        or result.get("world_artifact_identity_set_sha256")
        != batch.canonical_sha256(worlds)
        or set(verification) != set(_RESULT_VERIFICATION_FIELDS)
        or any(flag is not True for flag in verification.values())
    ):
        _fail("task-result lineage or verification differs")
    for field in (
        "compatibility_import_sha256", "candidate_provenance_sha256",
        "reconstruction_sha256", "full_union_surface_sha256",
    ):
        _sha(result.get(field), label=f"task result {field}")

    surface = _mapping(result.get("full_union_surface"), label="full-union surface")
    _exact_keys(surface, _SURFACE_FIELDS, label="full-union surface")
    surface_sha = _self_hash(
        surface, field="full_union_surface_sha256", label="full-union surface"
    )
    strategies = lane.frozen_full_union_strategies_v1()
    scopes = _sequence(surface.get("scopes"), label="full-union scopes")
    slate = _mapping(surface.get("slate"), label="surface slate")
    if (
        result.get("full_union_surface_sha256") != surface_sha
        or surface.get("schema_version") != lane.SURFACE_SCHEMA
        or slate.get("slate_id") != slate_id
        or surface.get("candidate_provenance_sha256")
        != result.get("candidate_provenance_sha256")
        or surface.get("reconstruction_sha256") != result.get("reconstruction_sha256")
        or surface.get("strategy_registry") != strategies
        or surface.get("strategy_registry_sha256") != batch.canonical_sha256(strategies)
        or surface.get("scope_count") != SCOPE_COUNT
        or surface.get("books_per_scope") != BOOKS_PER_SCOPE
        or surface.get("book_count") != BOOKS_PER_SLATE
        or surface.get("prefix_sizes") != list(lane.PREFIX_SIZES)
        or len(scopes) != SCOPE_COUNT
        or surface.get("rotated_simulated_fold_count") != len(rw.WORLD_BLOCKS)
        or surface.get("final_fit_is_distinct_all_block_refit") is not True
        or surface.get("full_union_only") is not True
        or surface.get("matchup_source_read") is not False
        or surface.get("uses_realized_outcomes") is not False
        or surface.get("promotion_authority") is not False
    ):
        _fail("full-union surface lattice differs")

    final_scope = _mapping(scopes[-1], label="all-block final scope")
    final_view, final_admission, final_ids, final_rosters = (
        _validate_candidate_view_and_admission(
            candidate_view_value=final_scope.get("candidate_view"),
            admission_value=final_scope.get("admission"),
            expected_slate=slate,
            fit_scope_id=FIT_SCOPE_IDS[-1],
            training_blocks=list(rw.WORLD_BLOCKS),
            heldout_block=None,
        )
    )
    if final_view.get("excluded_count") != 0 or final_admission.get("admitted_count") != len(final_ids):
        _fail("all-block union population is incomplete")
    global_index_by_id = {lineup_id: index for index, lineup_id in enumerate(final_ids)}

    seen_book_ids: set[str] = set()
    expected_holdouts: list[str | None] = [*rw.WORLD_BLOCKS, None]
    for scope_ordinal, raw_scope in enumerate(scopes):
        scope = _mapping(raw_scope, label=f"full-union scope[{scope_ordinal}]")
        _exact_keys(scope, _SCOPE_FIELDS, label=f"scope[{scope_ordinal}]")
        _self_hash(scope, field="fit_scope_sha256", label=f"scope[{scope_ordinal}]")
        heldout = expected_holdouts[scope_ordinal]
        training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
        fit_scope_id = FIT_SCOPE_IDS[scope_ordinal]
        candidate_view, admission, admitted_ids, roster_by_id = (
            _validate_candidate_view_and_admission(
                candidate_view_value=scope.get("candidate_view"),
                admission_value=scope.get("admission"),
                expected_slate=slate,
                fit_scope_id=fit_scope_id,
                training_blocks=training_blocks,
                heldout_block=heldout,
            )
        )
        books = _sequence(scope.get("books"), label="scope books")
        if (
            scope.get("schema_version") != lane.SCOPE_SCHEMA
            or scope.get("fit_scope_id") != fit_scope_id
            or scope.get("heldout_block") != heldout
            or scope.get("training_blocks") != training_blocks
            or scope.get("reconstruction_sha256") != result.get("reconstruction_sha256")
            or scope.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
            or scope.get("dose_authority") != runner.AUTHORITATIVE_DOSE
            or scope.get("require_authoritative") is not True
            or scope.get("admission_mode") != "complete-fold-eligible-cross-arm-union"
            or scope.get("strategy_registry") != strategies
            or scope.get("strategy_count") != lane.STRATEGY_COUNT
            or scope.get("book_count") != BOOKS_PER_SCOPE
            or len(books) != BOOKS_PER_SCOPE
            or scope.get("matchup_source_read") is not False
            or scope.get("matchup_admission_read") is not False
            or scope.get("neutral_control_read") is not False
            or scope.get("uses_realized_outcomes") is not False
            or scope.get("promotion_authority") is not False
            or not set(admitted_ids).issubset(global_index_by_id)
            or any(final_rosters[lineup_id] != roster_by_id[lineup_id] for lineup_id in admitted_ids)
        ):
            _fail("full-union scope differs")
        for strategy, raw_book in zip(strategies, books, strict=True):
            _validate_book_v1(
                raw_book,
                strategy=strategy,
                expected_slate=slate,
                heldout_block=heldout,
                training_blocks=training_blocks,
                fit_scope_id=fit_scope_id,
                reconstruction_sha256=str(result["reconstruction_sha256"]),
                admission=admission,
                admitted_ids=admitted_ids,
                roster_by_id=roster_by_id,
                global_index_by_id=global_index_by_id,
                seen_book_ids=seen_book_ids,
            )
    if len(seen_book_ids) != BOOKS_PER_SLATE:
        _fail("full-union task result does not contain 48 unique books")
    return result


def _one_runtime_argument(args: Sequence[str], flag: str) -> str:
    positions = [index for index, value in enumerate(args) if value == flag]
    if len(positions) != 1 or positions[0] + 1 >= len(args):
        _fail(f"runtime execution must carry one {flag} value")
    value = args[positions[0] + 1]
    if not value or value.startswith("--"):
        _fail(f"runtime execution {flag} value differs")
    return value


def validate_runtime_execution_evidence_v1(
    value: object,
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    source_ordinal: int,
) -> dict[str, object]:
    """Validate authenticated evidence for the worker's actual execution spec."""
    evidence = _mapping(value, label="runtime execution evidence")
    _exact_keys(
        evidence,
        _RUNTIME_EXECUTION_EVIDENCE_FIELDS,
        label="runtime execution evidence",
    )
    _self_hash(
        evidence,
        field="runtime_execution_evidence_sha256",
        label="runtime execution evidence",
    )
    manifest_id = _identity(manifest_identity, label="manifest identity")
    args = _sequence(
        evidence.get("container_args"), label="runtime container args"
    )
    command = _sequence(
        evidence.get("container_command"), label="runtime container command"
    )
    execution_spec_keys = _sequence(
        evidence.get("execution_spec_keys"), label="execution spec keys"
    )
    execution_template_keys = _sequence(
        evidence.get("execution_template_keys"),
        label="execution template keys",
    )
    task_spec_keys = _sequence(
        evidence.get("task_spec_keys"), label="task spec keys"
    )
    container_keys = _sequence(
        evidence.get("container_keys"), label="container keys"
    )
    configured_environment = _mapping(
        evidence.get("configured_environment"),
        label="runtime configured environment",
    )
    if any(
        type(value) is not str
        for value in [
            *args, *command, *execution_spec_keys, *execution_template_keys,
            *task_spec_keys, *container_keys,
        ]
    ):
        _fail("runtime container command or args differ")
    job = evidence.get("cloud_job")
    execution = evidence.get("cloud_execution")
    task_index = evidence.get("task_index")
    task_attempt = evidence.get("task_attempt")
    task_count = evidence.get("task_count")
    parallelism = evidence.get("parallelism")
    if (
        evidence.get("schema_version") != RUNTIME_EXECUTION_EVIDENCE_SCHEMA
        or evidence.get("cloud_project_id") != _RUNTIME_PROJECT_ID
        or evidence.get("cloud_project_number") != _RUNTIME_PROJECT_NUMBER
        or evidence.get("cloud_region") != _RUNTIME_REGION
        or job not in _RUNTIME_JOBS
        or type(execution) is not str
        or not execution.startswith(f"{job}-")
        or any(
            type(evidence.get(field)) is not str or not evidence.get(field)
            for field in (
                "cloud_execution_uid", "cloud_job_generation",
                "execution_resource_version",
            )
        )
        or evidence.get("cloud_job_uid") != _RUNTIME_JOB_UIDS.get(str(job))
        or not str(evidence.get("cloud_job_generation")).isdigit()
        or evidence.get("source_ordinal") != source_ordinal
        or type(task_index) is not int
        or type(task_attempt) is not int
        or type(task_count) is not int
        or type(parallelism) is not int
        or not 0 <= task_index < task_count
        or task_attempt != 0
        or not 1 <= parallelism <= task_count
        or evidence.get("max_retries") != 0
        or evidence.get("task_timeout_seconds") != _RUNTIME_TIMEOUT_SECONDS
        or evidence.get("immutable_image") != manifest.get("immutable_image")
        or evidence.get("service_account") != _RUNTIME_SERVICE_ACCOUNT
        or evidence.get("cpu") != "4"
        or evidence.get("memory") != "16Gi"
        or command != ["python"]
        or not args
        or args[0] != "scripts/run_corpus_r6_full_union_panel_freeze_v1.py"
        or args.count("run-slate") != 1
        or args.count("--execute") != 1
        or frozenset(execution_spec_keys) not in _RUNTIME_EXECUTION_SPEC_KEYSETS
        or execution_spec_keys != sorted(execution_spec_keys)
        or frozenset(execution_template_keys)
        not in _RUNTIME_EXECUTION_TEMPLATE_KEYSETS
        or execution_template_keys != sorted(execution_template_keys)
        or frozenset(task_spec_keys) not in _RUNTIME_TASK_SPEC_KEYSETS
        or task_spec_keys != sorted(task_spec_keys)
        or frozenset(container_keys) not in _RUNTIME_CONTAINER_KEYSETS
        or container_keys != sorted(container_keys)
        or configured_environment != {
            "R6_FULL_UNION_PANEL_FREEZE_PRODUCTION_ENABLED": "1",
            "R6_FULL_UNION_PANEL_FREEZE_RUNTIME_IMAGE": manifest.get(
                "immutable_image"
            ),
        }
        or evidence.get("secret_env_count") != 0
        or evidence.get("volume_count") != 0
        or evidence.get("volume_mount_count") != 0
        or evidence.get("network_attachment_count") != 0
        or evidence.get("authenticated_execution_api_read") is not True
    ):
        _fail("runtime execution provenance, resources, or retry law differs")
    if (
        _one_runtime_argument(args, "--project")
        != evidence["cloud_project_id"]
        or _one_runtime_argument(args, "--manifest-uri") != manifest_id["uri"]
        or _one_runtime_argument(args, "--manifest-generation")
        != manifest_id["generation"]
        or _one_runtime_argument(args, "--manifest-sha256")
        != manifest_id["sha256"]
        or int(_one_runtime_argument(args, "--manifest-bytes"))
        != manifest_id["bytes"]
        or _one_runtime_argument(args, "--expected-source-commit-sha")
        != manifest.get("source_commit_sha")
        or _one_runtime_argument(args, "--expected-immutable-image")
        != manifest.get("immutable_image")
        or int(_one_runtime_argument(args, "--expected-project-number"))
        != int(evidence["cloud_project_number"])
        or _one_runtime_argument(args, "--expected-region")
        != evidence["cloud_region"]
    ):
        _fail("runtime execution arguments differ from the immutable manifest")
    explicit_count = args.count("--source-ordinal")
    offset_count = args.count("--source-offset")
    if explicit_count == 1 and offset_count == 0:
        if (
            int(_one_runtime_argument(args, "--source-ordinal"))
            != source_ordinal
            or task_index != 0
            or task_count != 1
        ):
            _fail("explicit source-ordinal execution mapping differs")
    elif explicit_count == 0 and offset_count == 1:
        if (
            int(_one_runtime_argument(args, "--source-offset")) + task_index
            != source_ordinal
        ):
            _fail("task-index source-offset execution mapping differs")
    else:
        _fail("runtime execution source mapping differs")
    return evidence


def _build_task_result_envelope_from_open(
    *,
    manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    panel_members: Sequence[Mapping[str, object]],
    source_ordinal: int,
    runtime_execution_evidence: Mapping[str, object],
    task_result: Mapping[str, object],
) -> dict[str, object]:
    """Bind one validated scientific result to its immutable execution manifest."""
    if (
        type(source_ordinal) is not int
        or not 0 <= source_ordinal < AUTHORITATIVE_SLATE_COUNT
    ):
        _fail("task-result envelope source ordinal must be in 0..53")
    source_members = _sequence(
        manifest.get("source_members"), label="manifest source members"
    )
    source_member = _mapping(
        source_members[source_ordinal], label="manifest source member"
    )
    panel_member = _mapping(
        panel_members[source_ordinal], label="panel member"
    )
    if (
        source_member.get("source_ordinal") != source_ordinal
        or source_member.get("slate_id") != panel_member.get("slate_id")
        or source_member.get("panel_member_sha256")
        != batch.canonical_sha256(panel_member)
    ):
        _fail("task-result envelope source-member binding differs")
    result = validate_task_result_v1(
        task_result,
        panel_index_identity=manifest["panel_index_identity"],
        panel_index_sha256=str(panel["panel_index_sha256"]),
        panel_member=panel_member,
    )
    runtime_evidence = validate_runtime_execution_evidence_v1(
        runtime_execution_evidence,
        manifest_identity=manifest_identity,
        manifest=manifest,
        source_ordinal=source_ordinal,
    )
    body: dict[str, object] = {
        "schema_version": TASK_RESULT_ENVELOPE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": source_member["task_result_uri"],
        "manifest_identity": dict(manifest_identity),
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_ordinal": source_ordinal,
        "slate_id": panel_member["slate_id"],
        "panel_member_sha256": batch.canonical_sha256(panel_member),
        "source_commit_sha": manifest["source_commit_sha"],
        "immutable_image": manifest["immutable_image"],
        "runtime_execution_evidence": runtime_evidence,
        "task_result": result,
        "task_result_sha256": result["task_result_sha256"],
        "task_result_payload_sha256": batch.canonical_sha256(result),
        "structural_freeze_only": True,
        "independent_second_selector_replay": False,
        **{field: False for field in _FALSE_FIELDS},
    }
    return _with_hash(body, field="task_result_envelope_sha256")


def build_task_result_envelope_v1(
    *,
    manifest_identity: object,
    source_ordinal: int,
    runtime_execution_evidence: Mapping[str, object],
    task_result: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build the create-once manifest-bound envelope for one task result."""
    manifest, panel, members, retained_manifest_identity = (
        reopen_execution_manifest_v1(manifest_identity, read_exact=read_exact)
    )
    return _build_task_result_envelope_from_open(
        manifest_identity=retained_manifest_identity,
        manifest=manifest,
        panel=panel,
        panel_members=members,
        source_ordinal=source_ordinal,
        runtime_execution_evidence=runtime_execution_evidence,
        task_result=task_result,
    )


def validate_task_result_envelope_v1(
    value: object,
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    panel_members: Sequence[Mapping[str, object]],
    source_ordinal: int,
) -> dict[str, object]:
    """Exact-replay a task-result envelope from its manifest and result body."""
    envelope = _mapping(value, label="task-result envelope")
    _exact_keys(
        envelope,
        _TASK_RESULT_ENVELOPE_FIELDS,
        label="task-result envelope",
    )
    _self_hash(
        envelope,
        field="task_result_envelope_sha256",
        label="task-result envelope",
    )
    _false_fields(envelope, label="task-result envelope")
    _reject_nested_result_or_authority(envelope, label="task-result envelope")
    expected = _build_task_result_envelope_from_open(
        manifest_identity=_identity(manifest_identity, label="manifest identity"),
        manifest=manifest,
        panel=panel,
        panel_members=panel_members,
        source_ordinal=source_ordinal,
        runtime_execution_evidence=_mapping(
            envelope.get("runtime_execution_evidence"),
            label="runtime execution evidence",
        ),
        task_result=_mapping(
            envelope.get("task_result"), label="enveloped task result"
        ),
    )
    if batch.canonical_json_bytes(envelope) != batch.canonical_json_bytes(expected):
        _fail("task-result envelope canonical replay differs")
    return expected


def reopen_task_result_envelope_v1(
    task_result_identity: object, *, read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    list[dict[str, object]], dict[str, object], dict[str, object]
]:
    """Exact-open one envelope, its manifest, and its scientific result."""
    envelope, retained_identity = _exact_read_json(
        task_result_identity, read_exact=read_exact, label="task-result envelope"
    )
    source_ordinal = envelope.get("source_ordinal")
    if type(source_ordinal) is not int:
        _fail("task-result envelope source ordinal differs")
    manifest, panel, members, manifest_identity = reopen_execution_manifest_v1(
        envelope.get("manifest_identity"), read_exact=read_exact
    )
    validated = validate_task_result_envelope_v1(
        envelope,
        manifest_identity=manifest_identity,
        manifest=manifest,
        panel=panel,
        panel_members=members,
        source_ordinal=source_ordinal,
    )
    _bind_identity_to_body(
        retained_identity, validated, label="task-result envelope"
    )
    if retained_identity["uri"] != validated["target_uri"]:
        _fail("task-result envelope outer URI differs from its designated target")
    return (
        validated,
        manifest,
        panel,
        members,
        _mapping(validated["task_result"], label="enveloped task result"),
        retained_identity,
    )


def _prefix_descriptors(book: Mapping[str, object]) -> list[dict[str, object]]:
    selected_ids = _sequence(book.get("selected_lineup_ids"), label="rank-80 IDs")
    selected_rosters = _sequence(book.get("selected_rosters"), label="rank-80 rosters")
    rank_payload = {
        "selected_lineup_ids": selected_ids,
        "selected_rosters": selected_rosters,
    }
    rank_sha = batch.canonical_sha256(rank_payload)
    descriptors: list[dict[str, object]] = []
    for size in lane.PREFIX_SIZES:
        ids = selected_ids[:size]
        rosters = selected_rosters[:size]
        body = {
            "schema_version": PREFIX_DESCRIPTOR_SCHEMA,
            "entry_count": size,
            "prefix_of_rank_80": True,
            "rank_80_payload_sha256": rank_sha,
            "prefix_payload_sha256": batch.canonical_sha256({
                "selected_lineup_ids": ids,
                "selected_rosters": rosters,
            }),
            "selected_lineup_ids_sha256": batch.canonical_sha256(ids),
            "selected_rosters_sha256": batch.canonical_sha256(rosters),
        }
        descriptors.append(_with_hash(body, field="prefix_descriptor_sha256"))
    return descriptors


def _derive_descriptors(
    task_result: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    surface = _mapping(task_result["full_union_surface"], label="full-union surface")
    scopes = _sequence(surface["scopes"], label="full-union scopes")
    strategies = _sequence(surface["strategy_registry"], label="strategy registry")
    final_scope = _mapping(scopes[-1], label="all-block final scope")
    final_view = _mapping(final_scope["candidate_view"], label="all-block candidate view")
    final_admission = _mapping(final_scope["admission"], label="all-block admission")
    candidate_rows = [
        _mapping(row, label=f"all-block candidate[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(final_view["eligible_candidates"], label="all-block candidates")
        )
    ]
    population = [
        {
            "lineup_id": row["lineup_id"],
            "roster_player_ids": row["roster_player_ids"],
        }
        for row in candidate_rows
    ]
    candidate_ids = [row["lineup_id"] for row in population]
    candidate_rosters = [row["roster_player_ids"] for row in population]
    union_descriptor = _with_hash({
        "schema_version": UNION_DESCRIPTOR_SCHEMA,
        "fit_scope_id": FIT_SCOPE_IDS[-1],
        "fit_scope_sha256": final_scope["fit_scope_sha256"],
        "fit_candidate_view_sha256": final_view["fit_candidate_view_sha256"],
        "selection_provenance_sha256": final_view["selection_provenance_sha256"],
        "admission_id": final_admission["admission_id"],
        "admission_sha256": final_admission["admission_sha256"],
        "lineup_count": len(population),
        "ordered_lineup_ids_sha256": batch.canonical_sha256(candidate_ids),
        "ordered_rosters_sha256": batch.canonical_sha256(candidate_rosters),
        "ordered_population_sha256": batch.canonical_sha256(population),
        "eligible_equals_admitted": True,
        "excluded_count": 0,
    }, field="population_descriptor_sha256")

    scope_descriptors: list[dict[str, object]] = []
    book_descriptors: list[dict[str, object]] = []
    global_book_ordinal = 0
    for scope_ordinal, raw_scope in enumerate(scopes):
        scope = _mapping(raw_scope, label=f"scope[{scope_ordinal}]")
        view = _mapping(scope["candidate_view"], label="scope candidate view")
        admission = _mapping(scope["admission"], label="scope admission")
        books = _sequence(scope["books"], label="scope books")
        scope_descriptor = _with_hash({
            "schema_version": SCOPE_DESCRIPTOR_SCHEMA,
            "scope_ordinal": scope_ordinal,
            "fit_scope_id": scope["fit_scope_id"],
            "heldout_block": scope["heldout_block"],
            "fit_scope_sha256": scope["fit_scope_sha256"],
            "fit_candidate_view_sha256": view["fit_candidate_view_sha256"],
            "selection_provenance_sha256": view["selection_provenance_sha256"],
            "admission_id": admission["admission_id"],
            "admission_sha256": admission["admission_sha256"],
            "eligible_count": view["eligible_count"],
            "admitted_count": admission["admitted_count"],
            "book_count": len(books),
        }, field="scope_descriptor_sha256")
        scope_descriptors.append(scope_descriptor)
        for scope_book_ordinal, (raw_book, raw_strategy) in enumerate(
            zip(books, strategies, strict=True)
        ):
            book = _mapping(raw_book, label="full-union book")
            strategy = _mapping(raw_strategy, label="strategy")
            rank_payload = {
                "selected_lineup_ids": book["selected_lineup_ids"],
                "selected_rosters": book["selected_rosters"],
            }
            prefixes = _prefix_descriptors(book)
            descriptor = _with_hash({
                "schema_version": BOOK_DESCRIPTOR_SCHEMA,
                "global_book_ordinal": global_book_ordinal,
                "scope_ordinal": scope_ordinal,
                "scope_book_ordinal": scope_book_ordinal,
                "fit_scope_id": scope["fit_scope_id"],
                "heldout_block": scope["heldout_block"],
                "book_id": book["book_id"],
                "book_sha256": book["book_sha256"],
                "admission_id": book["admission_id"],
                "admission_sha256": book["admission_sha256"],
                "strategy_ordinal": strategy["ordinal"],
                "strategy_id": strategy["strategy_id"],
                "strategy_sha256": strategy["strategy_sha256"],
                "entry_count": book["entry_count"],
                "rank_80_payload_sha256": batch.canonical_sha256(rank_payload),
                "selected_lineup_ids_sha256": batch.canonical_sha256(
                    book["selected_lineup_ids"]
                ),
                "selected_rosters_sha256": batch.canonical_sha256(
                    book["selected_rosters"]
                ),
                "prefix_count": len(prefixes),
                "prefixes": prefixes,
            }, field="book_descriptor_sha256")
            book_descriptors.append(descriptor)
            global_book_ordinal += 1
    if (
        len(scope_descriptors) != SCOPE_COUNT
        or len(book_descriptors) != BOOKS_PER_SLATE
        or sum(int(row["prefix_count"]) for row in book_descriptors)
        != PREFIXES_PER_SLATE
    ):
        _fail("derived descriptor census differs")
    return union_descriptor, scope_descriptors, book_descriptors


def _build_slate_freeze_from_open(
    *,
    manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    panel_members: Sequence[Mapping[str, object]],
    source_ordinal: int,
    task_result_identity: Mapping[str, object],
    task_result_envelope: Mapping[str, object],
) -> dict[str, object]:
    if type(source_ordinal) is not int or not 0 <= source_ordinal < AUTHORITATIVE_SLATE_COUNT:
        _fail("source ordinal must be one exact integer in 0..53")
    source_members = _sequence(manifest.get("source_members"), label="manifest source members")
    source_member = _mapping(source_members[source_ordinal], label="manifest source member")
    panel_member = _mapping(panel_members[source_ordinal], label="panel member")
    if (
        source_member.get("source_ordinal") != source_ordinal
        or source_member.get("slate_id") != panel_member.get("slate_id")
        or source_member.get("panel_member_sha256") != batch.canonical_sha256(panel_member)
        or task_result_identity.get("uri") != source_member.get("task_result_uri")
    ):
        _fail("slate freeze source-member binding differs")
    envelope = validate_task_result_envelope_v1(
        task_result_envelope,
        manifest_identity=manifest_identity,
        manifest=manifest,
        panel=panel,
        panel_members=panel_members,
        source_ordinal=source_ordinal,
    )
    result = _mapping(envelope["task_result"], label="enveloped task result")
    result_identity = _bind_identity_to_body(
        task_result_identity, envelope, label="task-result envelope"
    )
    union_descriptor, scope_descriptors, book_descriptors = _derive_descriptors(result)
    body: dict[str, object] = {
        "schema_version": SLATE_FREEZE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": source_member["slate_freeze_uri"],
        "manifest_identity": dict(manifest_identity),
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "source_ordinal": source_ordinal,
        "slate_id": panel_member["slate_id"],
        "panel_index_identity": manifest["panel_index_identity"],
        "panel_index_sha256": panel["panel_index_sha256"],
        "panel_member_sha256": batch.canonical_sha256(panel_member),
        "task_acceptance_identity": result["task_acceptance_identity"],
        "carrier_identity": result["carrier_identity"],
        "task_result_identity": result_identity,
        "task_result_envelope_sha256": envelope[
            "task_result_envelope_sha256"
        ],
        "runtime_execution_evidence_sha256": _mapping(
            envelope["runtime_execution_evidence"],
            label="runtime execution evidence",
        )["runtime_execution_evidence_sha256"],
        "task_result_sha256": result["task_result_sha256"],
        "later_source_freeze_identity": result["later_source_freeze_identity"],
        "world_artifact_identity_set_sha256": result[
            "world_artifact_identity_set_sha256"
        ],
        "compatibility_import_sha256": result["compatibility_import_sha256"],
        "candidate_provenance_sha256": result["candidate_provenance_sha256"],
        "reconstruction_sha256": result["reconstruction_sha256"],
        "full_union_surface_sha256": result["full_union_surface_sha256"],
        "strategy_registry_sha256": manifest["strategy_registry_sha256"],
        "scope_count": len(scope_descriptors),
        "scope_descriptors": scope_descriptors,
        "all_block_union": union_descriptor,
        "book_count": len(book_descriptors),
        "book_descriptors": book_descriptors,
        "prefix_sizes": list(lane.PREFIX_SIZES),
        "prefix_count": sum(
            int(descriptor["prefix_count"]) for descriptor in book_descriptors
        ),
        "complete": True,
        "structural_freeze_only": True,
        "independent_second_selector_replay": False,
        **{field: False for field in _FALSE_FIELDS},
    }
    return _with_hash(body, field="slate_freeze_sha256")


def build_slate_freeze_v1(
    *,
    manifest_identity: object,
    source_ordinal: int,
    task_result_identity: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open a task result and derive its compact immutable leaf."""
    manifest, panel, members, retained_manifest_identity = (
        reopen_execution_manifest_v1(manifest_identity, read_exact=read_exact)
    )
    task_result_envelope, retained_result_identity = _exact_read_json(
        task_result_identity, read_exact=read_exact, label="task-result envelope"
    )
    return _build_slate_freeze_from_open(
        manifest_identity=retained_manifest_identity,
        manifest=manifest,
        panel=panel,
        panel_members=members,
        source_ordinal=source_ordinal,
        task_result_identity=retained_result_identity,
        task_result_envelope=task_result_envelope,
    )


def validate_slate_freeze_structure_v1(
    value: object,
    *,
    manifest_identity: object,
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    panel_members: Sequence[Mapping[str, object]],
    task_result_identity: object,
    task_result_envelope: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="slate freeze")
    _self_hash(item, field="slate_freeze_sha256", label="slate freeze")
    _false_fields(item, label="slate freeze")
    _reject_nested_result_or_authority(item, label="slate freeze")
    source_ordinal = item.get("source_ordinal")
    if type(source_ordinal) is not int:
        _fail("slate freeze source ordinal differs")
    expected = _build_slate_freeze_from_open(
        manifest_identity=_identity(manifest_identity, label="manifest identity"),
        manifest=manifest,
        panel=panel,
        panel_members=panel_members,
        source_ordinal=source_ordinal,
        task_result_identity=_identity(task_result_identity, label="task result identity"),
        task_result_envelope=task_result_envelope,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("slate freeze canonical replay differs")
    return expected


def reopen_slate_freeze_v1(
    slate_freeze_identity: object, *, read_exact: ReadExact,
) -> tuple[
    dict[str, object], dict[str, object], dict[str, object],
    list[dict[str, object]], dict[str, object], dict[str, object]
]:
    leaf, retained_leaf_identity = _exact_read_json(
        slate_freeze_identity, read_exact=read_exact, label="slate freeze"
    )
    manifest, panel, members, manifest_identity = reopen_execution_manifest_v1(
        leaf.get("manifest_identity"), read_exact=read_exact
    )
    envelope, result_identity = _exact_read_json(
        leaf.get("task_result_identity"),
        read_exact=read_exact,
        label="task-result envelope",
    )
    validated = validate_slate_freeze_structure_v1(
        leaf,
        manifest_identity=manifest_identity,
        manifest=manifest,
        panel=panel,
        panel_members=members,
        task_result_identity=result_identity,
        task_result_envelope=envelope,
    )
    _bind_identity_to_body(retained_leaf_identity, validated, label="slate freeze")
    if retained_leaf_identity["uri"] != validated["target_uri"]:
        _fail("slate-freeze outer URI differs from its designated target")
    result = _mapping(envelope["task_result"], label="enveloped task result")
    return validated, manifest, panel, members, result, retained_leaf_identity


def build_panel_freeze_v1(
    *,
    manifest_identity: object,
    ordered_slate_freeze_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open all 54 leaves/results and derive the root last."""
    manifest, panel, members, retained_manifest_identity = (
        reopen_execution_manifest_v1(manifest_identity, read_exact=read_exact)
    )
    raw_identities = _sequence(
        ordered_slate_freeze_identities, label="ordered slate-freeze identities"
    )
    if len(raw_identities) != AUTHORITATIVE_SLATE_COUNT:
        _fail("panel freeze requires exactly 54 ordered slate leaves")
    rows: list[dict[str, object]] = []
    seen_leaf_identities: set[tuple[str, str, str, int]] = set()
    seen_result_identities: set[tuple[str, str, str, int]] = set()
    seen_leaf_uris: set[str] = set()
    seen_result_uris: set[str] = set()
    union_lineup_count = 0
    for source_ordinal, raw_identity in enumerate(raw_identities):
        leaf, leaf_manifest, leaf_panel, leaf_members, result, leaf_identity = (
            reopen_slate_freeze_v1(raw_identity, read_exact=read_exact)
        )
        if (
            leaf.get("source_ordinal") != source_ordinal
            or leaf.get("slate_id") != members[source_ordinal].get("slate_id")
            or leaf.get("manifest_identity") != retained_manifest_identity
            or leaf_manifest.get("execution_manifest_sha256")
            != manifest.get("execution_manifest_sha256")
            or leaf_panel.get("panel_index_sha256") != panel.get("panel_index_sha256")
            or batch.canonical_sha256(leaf_members[source_ordinal])
            != batch.canonical_sha256(members[source_ordinal])
            or leaf.get("later_source_freeze_identity")
            != manifest.get("later_source_freeze_identity")
            or leaf.get("strategy_registry_sha256")
            != manifest.get("strategy_registry_sha256")
            or leaf.get("scope_count") != SCOPE_COUNT
            or leaf.get("book_count") != BOOKS_PER_SLATE
            or leaf.get("prefix_count") != PREFIXES_PER_SLATE
            or leaf.get("complete") is not True
        ):
            _fail(f"slate leaf[{source_ordinal}] root binding differs")
        leaf_key = _identity_key(leaf_identity, label="slate-freeze identity")
        result_identity = _identity(
            leaf.get("task_result_identity"), label="task-result identity"
        )
        result_key = _identity_key(result_identity, label="task-result identity")
        if (
            leaf_key in seen_leaf_identities
            or result_key in seen_result_identities
            or str(leaf_identity["uri"]) in seen_leaf_uris
            or str(result_identity["uri"]) in seen_result_uris
        ):
            _fail("slate leaf or task-result object repeats across source ordinals")
        seen_leaf_identities.add(leaf_key)
        seen_result_identities.add(result_key)
        seen_leaf_uris.add(str(leaf_identity["uri"]))
        seen_result_uris.add(str(result_identity["uri"]))
        union_descriptor = _mapping(
            leaf.get("all_block_union"), label="all-block union descriptor"
        )
        union_count = union_descriptor.get("lineup_count")
        if type(union_count) is not int or union_count < lane.ENTRY_BUDGET:
            _fail("all-block union lineup count differs")
        union_lineup_count += union_count
        row = _with_hash({
            "source_ordinal": source_ordinal,
            "slate_id": leaf["slate_id"],
            "panel_member_sha256": leaf["panel_member_sha256"],
            "slate_freeze_identity": leaf_identity,
            "slate_freeze_sha256": leaf["slate_freeze_sha256"],
            "task_result_identity": result_identity,
            "task_result_envelope_sha256": leaf[
                "task_result_envelope_sha256"
            ],
            "runtime_execution_evidence_sha256": leaf[
                "runtime_execution_evidence_sha256"
            ],
            "task_result_sha256": result["task_result_sha256"],
            "full_union_surface_sha256": leaf["full_union_surface_sha256"],
            "population_descriptor_sha256": union_descriptor[
                "population_descriptor_sha256"
            ],
            "union_lineup_count": union_count,
            "scope_count": leaf["scope_count"],
            "book_count": leaf["book_count"],
            "prefix_count": leaf["prefix_count"],
        }, field="panel_slate_descriptor_sha256")
        rows.append(row)
    if (
        [row["source_ordinal"] for row in rows]
        != list(range(AUTHORITATIVE_SLATE_COUNT))
        or [row["slate_id"] for row in rows]
        != [member["slate_id"] for member in members]
        or sum(int(row["scope_count"]) for row in rows) != PANEL_SCOPE_COUNT
        or sum(int(row["book_count"]) for row in rows) != PANEL_BOOK_COUNT
        or sum(int(row["prefix_count"]) for row in rows) != PANEL_PREFIX_COUNT
    ):
        _fail("panel root census differs")
    body: dict[str, object] = {
        "schema_version": PANEL_FREEZE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": manifest["panel_freeze_uri"],
        "manifest_identity": retained_manifest_identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "panel_index_identity": manifest["panel_index_identity"],
        "panel_index_sha256": panel["panel_index_sha256"],
        "accepted_slates_sha256": manifest["accepted_slates_sha256"],
        "later_source_freeze_identity": manifest["later_source_freeze_identity"],
        "strategy_registry": manifest["strategy_registry"],
        "strategy_registry_sha256": manifest["strategy_registry_sha256"],
        "fit_scope_ids": list(FIT_SCOPE_IDS),
        "prefix_sizes": list(lane.PREFIX_SIZES),
        "source_slate_count": len(rows),
        "slate_freezes": rows,
        "slate_freezes_sha256": batch.canonical_sha256(rows),
        "union_lineup_count": union_lineup_count,
        "scope_count": PANEL_SCOPE_COUNT,
        "rank_80_book_count": PANEL_BOOK_COUNT,
        "prefix_count": PANEL_PREFIX_COUNT,
        "prefix_roster_occurrence_counts": {
            str(size): AUTHORITATIVE_SLATE_COUNT * BOOKS_PER_SLATE * size
            for size in lane.PREFIX_SIZES
        },
        "complete": True,
        "structural_freeze_only": True,
        "independent_second_selector_replay": False,
        "outcome_key_projection_inputs_frozen": True,
        **{field: False for field in _FALSE_FIELDS},
    }
    return _with_hash(body, field="panel_freeze_sha256")


def validate_panel_freeze_structure_v1(
    value: object, *, read_exact: ReadExact,
) -> dict[str, object]:
    item = _mapping(value, label="panel freeze")
    _self_hash(item, field="panel_freeze_sha256", label="panel freeze")
    _false_fields(item, label="panel freeze")
    _reject_nested_result_or_authority(
        item,
        label="panel freeze",
        allow_outcome_key_projection_inputs_frozen=True,
    )
    rows = _sequence(item.get("slate_freezes"), label="panel slate descriptors")
    identities = [
        _identity(
            _mapping(row, label=f"panel slate descriptor[{ordinal}]").get(
                "slate_freeze_identity"
            ),
            label=f"slate-freeze identity[{ordinal}]",
        )
        for ordinal, row in enumerate(rows)
    ]
    expected = build_panel_freeze_v1(
        manifest_identity=item.get("manifest_identity"),
        ordered_slate_freeze_identities=identities,
        read_exact=read_exact,
    )
    if batch.canonical_json_bytes(item) != batch.canonical_json_bytes(expected):
        _fail("panel freeze canonical replay differs")
    return expected


def reopen_panel_freeze_v1(
    panel_freeze_identity: object, *, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    root, retained_identity = _exact_read_json(
        panel_freeze_identity, read_exact=read_exact, label="panel freeze"
    )
    validated = validate_panel_freeze_structure_v1(root, read_exact=read_exact)
    _bind_identity_to_body(retained_identity, validated, label="panel freeze")
    if retained_identity["uri"] != validated["target_uri"]:
        _fail("panel-freeze outer URI differs from its designated target")
    return validated, retained_identity


__all__ = [
    "AUTHORITATIVE_SLATE_COUNT",
    "BOOKS_PER_SLATE",
    "CorpusR6FullUnionPanelFreezeV1Error",
    "MANIFEST_SCHEMA",
    "PANEL_BOOK_COUNT",
    "PANEL_FREEZE_SCHEMA",
    "PANEL_PREFIX_COUNT",
    "PREFIX_DESCRIPTOR_SCHEMA",
    "RUNTIME_EXECUTION_EVIDENCE_SCHEMA",
    "SLATE_FREEZE_SCHEMA",
    "TASK_RESULT_ENVELOPE_SCHEMA",
    "build_execution_manifest_v1",
    "build_panel_freeze_v1",
    "build_slate_freeze_v1",
    "build_task_result_envelope_v1",
    "reopen_execution_manifest_v1",
    "reopen_fixed_panel_v1",
    "reopen_panel_freeze_v1",
    "reopen_slate_freeze_v1",
    "reopen_task_result_envelope_v1",
    "validate_execution_manifest_v1",
    "validate_fixed_panel_v1",
    "validate_panel_freeze_structure_v1",
    "validate_runtime_execution_evidence_v1",
    "validate_slate_freeze_structure_v1",
    "validate_task_result_envelope_v1",
    "validate_task_result_v1",
]
