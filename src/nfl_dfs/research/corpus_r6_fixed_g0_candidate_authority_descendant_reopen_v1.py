"""Deep-reopen the fixed-G0 candidate root from a durable descendant.

The published candidate-v2 root retained a catalog-recovery capability hash
whose input included the clean repository HEAD used during publication.  That
HEAD is operational context, not an immutable predecessor: resolving the same
unchanged lock chain at a later clean descendant therefore changes only that
hash and the enclosing candidate-binding self-hash.

The frozen candidate-v1 predecessor also records that replay-time HEAD in two
non-scientific leaves: the G0 source commit and the catalog terminal-lock
binding copied into all 54 slate receipts.  This adapter accepts exactly those
two leaf classes, their deterministic 112-hash cascade, and the outer recovery
capability representation drift.  It proves the transitive authority code and
selection bytes unchanged between the historical and current commits, then
performs independent complete candidate-v1 replays of both the projected
current bundle and retained historical bundle before rebuilding the exact
candidate-v2 predecessor.  It does not expose publication, outcome, scoring,
graph, or policy capability.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
import stat
from typing import Final

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v2 as release,
)
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as core_v1
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v2 as core
from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as recovery
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import (
    corpus_r6_player_catalog_fixed_g0_adapter_v1 as catalog_adapter,
)

ADAPTER_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_fixed_g0_candidate_authority_descendant_reopen_v1.py"
)

# These are the transitive authority validators that can influence the two
# replay-time HEAD representations accepted below.  They deliberately exclude
# the much broader historical panel runtime surface: ordinary v1 byte replay
# still rejects any scientific-output drift in those modules.  The descendant
# adapter itself did not exist at the historical commit and is instead
# measured by the current capture-plan successor.
REPLAY_HEAD_STABLE_IMPLEMENTATION_PATHS: Final = tuple(sorted({
    core.FROZEN_CORE_V1_MODULE_PATH,
    core.CORE_V2_MODULE_PATH,
    core.RELEASE_V2_MODULE_PATH,
    core.recovery_downstream.DOWNSTREAM_MODULE_PATH,
    recovery.RECOVERY_MODULE_PATH,
    "src/nfl_dfs/research/corpus_extreme_tail_panel_execution.py",
    "src/nfl_dfs/research/corpus_v12_panel_index.py",
    "src/nfl_dfs/research/corpus_artifact_source_authority.py",
    "src/nfl_dfs/research/corpus_parametric_batch.py",
    "src/nfl_dfs/research/lr8_later_period_source.py",
    "src/nfl_dfs/research/lr8_historical_arm.py",
    "src/nfl_dfs/research/residual_world_columns.py",
    "src/nfl_dfs/research/object_identity.py",
    core_v1.catalog_successor.MODULE_PATH,
    core_v1.catalog_adapter.FIXED_ADAPTER_MODULE_PATH,
    core_v1.catalog_adapter.FIXED_CATALOG_MODULE_PATH,
    "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py",
    "src/nfl_dfs/research/corpus_v12_import.py",
    "src/nfl_dfs/research/corpus_legal_feasibility.py",
}))

REPLAY_HEAD_STABLE_SELECTION_PATHS: Final = tuple(sorted({
    core_v1.panel_execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH,
    core_v1.panel_execution.FROZEN_G0_PUBLICATION_RECEIPT_RELATIVE_PATH,
    *core_v1.panel_execution.FROZEN_G0_LANE_RECEIPT_RELATIVE_PATHS,
    core_v1.catalog_successor.FINAL_LOCK_PATH,
    core_v1.catalog_successor.REVIEW_LOCK_PATH,
    core_v1.catalog_successor.OLD_FINAL_LOCK_PATH,
    core_v1.catalog_successor.FAILURE_REPORT_PATH,
    core_v1.catalog_successor.FOCUSED_OUTPUT_PATH,
}))

REPLAY_HEAD_STABLE_PATHS: Final = tuple(sorted({
    *REPLAY_HEAD_STABLE_IMPLEMENTATION_PATHS,
    *REPLAY_HEAD_STABLE_SELECTION_PATHS,
}))

_G0_RUNTIME_SELECTION_PATHS: Final = {
    core_v1.panel_execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH: (
        core_v1.panel_execution.FROZEN_G0_AUTHORITY_LOCK_PATH
    ),
    core_v1.panel_execution.FROZEN_G0_PUBLICATION_RECEIPT_RELATIVE_PATH: (
        core_v1.panel_execution.FROZEN_G0_PUBLICATION_RECEIPT_PATH
    ),
    **{
        relative_path: runtime_path
        for relative_path, runtime_path in zip(
            core_v1.panel_execution.FROZEN_G0_LANE_RECEIPT_RELATIVE_PATHS,
            core_v1.panel_execution.FROZEN_G0_LANE_RECEIPT_PATHS,
            strict=True,
        )
    },
}

_CATALOG_TERMINAL_BINDING_FIELDS: Final = frozenset({
    "relative_path",
    "git_commit_sha",
    "sha256",
    "bytes",
    "projection_successor_final_lock_sha256",
})


class CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(ValueError):
    """The descendant-safe exact reopener failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return deepcopy(dict(value))


def _capability_stable_projection(
    capability: recovery.PublicationCapabilityV1,
) -> dict[str, object]:
    """Return every capability-hash input except the replay-time HEAD."""

    validated = recovery.validate_resolved_authority_v1(capability)
    return {
        "implementation_commit_sha": validated.implementation_commit_sha,
        "implementation_measurements": [
            dict(row) for row in validated.implementation_measurements
        ],
        "review_lock_commit_sha": validated.review_lock_commit_sha,
        "review_lock_file": dict(validated.review_lock_file),
        "review_lock_internal_sha256": validated.review_lock_internal_sha256,
        "final_lock_commit_sha": validated.final_lock_commit_sha,
        "final_lock_file": dict(validated.final_lock_file),
        "final_lock_internal_sha256": validated.final_lock_internal_sha256,
        "review_lock_sha256": recovery.canonical_sha256(dict(validated.review_lock)),
        "final_lock_sha256": recovery.canonical_sha256(dict(validated.final_lock)),
    }


def _attempt_stable_projection(
    attempt: recovery.TrackedAttemptBindingV1,
    *,
    capability: recovery.PublicationCapabilityV1,
) -> dict[str, object]:
    """Return every tracked-attempt field except its replay-time HEAD."""

    validated = recovery.validate_tracked_attempt_binding_v1(
        attempt, capability=capability
    )
    return {
        "marker_commit_sha": validated.marker_commit_sha,
        "marker": dict(validated.marker),
        "marker_file": dict(validated.marker_file),
        "marker_internal_sha256": validated.marker_internal_sha256,
    }


def validate_replay_head_only_binding_drift_v1(
    *,
    retained_binding: Mapping[str, object],
    descendant_binding: Mapping[str, object],
    historical_capability_sha256: str,
    descendant_capability_sha256: str,
) -> dict[str, object]:
    """Prove a candidate binding differs only by replay-time capability SHA.

    The immutable retained binding is returned.  Both enclosing self-hashes
    are validated, and an exact projection is required; coherent drift in any
    other field is rejected even when the caller recomputes its self-hash.
    """

    retained = _mapping(retained_binding, label="retained candidate binding")
    descendant = _mapping(descendant_binding, label="descendant candidate binding")
    try:
        core._validate_hash(
            retained,
            field="candidate_implementation_binding_sha256",
            label="retained candidate binding",
        )
        core._validate_hash(
            descendant,
            field="candidate_implementation_binding_sha256",
            label="descendant candidate binding",
        )
        historical_sha = core._digest(
            historical_capability_sha256,
            label="historical recovery capability SHA",
        )
        descendant_sha = core._digest(
            descendant_capability_sha256,
            label="descendant recovery capability SHA",
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc
    retained_recovery = _mapping(
        retained.get("catalog_recovery_code_and_lock_binding"),
        label="retained recovery binding",
    )
    descendant_recovery = _mapping(
        descendant.get("catalog_recovery_code_and_lock_binding"),
        label="descendant recovery binding",
    )
    if (
        retained_recovery.get("capability_sha256") != historical_sha
        or descendant_recovery.get("capability_sha256") != descendant_sha
    ):
        _fail("candidate binding capability SHA differs from resolved authority")

    projected = deepcopy(retained)
    projected_recovery = _mapping(
        projected.get("catalog_recovery_code_and_lock_binding"),
        label="projected recovery binding",
    )
    projected_recovery["capability_sha256"] = descendant_sha
    projected["catalog_recovery_code_and_lock_binding"] = projected_recovery
    projected.pop("candidate_implementation_binding_sha256", None)
    projected["candidate_implementation_binding_sha256"] = source.canonical_sha256(
        projected
    )
    if projected != descendant:
        _fail("candidate binding drift exceeds replay-time capability SHA")
    return retained


def _validate_v1_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    try:
        core_v1._validate_self_hash(value, field=field, label=label)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"{label} differs before replay-HEAD projection: {exc}"
        ) from exc


def _replace_terminal_binding_head(
    value: object,
    *,
    historical_head: str,
    descendant_head: str,
    label: str,
) -> dict[str, object]:
    binding = _mapping(value, label=label)
    if set(binding) != _CATALOG_TERMINAL_BINDING_FIELDS:
        _fail(f"{label} field schema differs")
    if binding.get("git_commit_sha") != historical_head:
        _fail(f"{label} is not bound to the candidate historical HEAD")
    binding["git_commit_sha"] = descendant_head
    return binding


def _project_v1_replay_head_only_bundle(
    value: object,
    *,
    historical_head: str,
    descendant_head: str,
) -> dict[str, object]:
    """Project the two v1 replay-time HEAD leaves to a durable descendant.

    Candidate-v1 records the current HEAD twice even though both values only
    attest that immutable tracked locks were clean when replayed: once in the
    G0 ``source_commit_sha`` and once in the catalog terminal-lock binding.
    The latter is copied into all 54 slate receipts.  This function accepts
    exactly those two direct leaf changes and deterministically rebuilds only
    their dependent receipt, panel, manifest, and bundle hashes.

    The returned projection is validation-only.  The retained historical
    bundle remains the authority returned by the descendant reopener.
    """

    try:
        historical = core._commit(
            historical_head, label="candidate historical replay HEAD"
        )
        descendant = core._commit(
            descendant_head, label="candidate descendant replay HEAD"
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc

    bundle = _mapping(value, label="retained v1 candidate bundle")
    _validate_v1_self_hash(
        bundle,
        field="candidate_authority_bundle_sha256",
        label="retained v1 candidate bundle",
    )
    if (
        bundle.get("schema_version") != core_v1.AUTHORITY_BUNDLE_SCHEMA
        or bundle.get("task_count") != source.TASK_COUNT
    ):
        _fail("retained v1 candidate bundle schema/cardinality differs")
    try:
        raw_receipts = core._sequence(
            bundle.get("slate_derivation_receipts"),
            label="retained v1 slate receipts",
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc
    if len(raw_receipts) != source.TASK_COUNT:
        _fail("retained v1 slate receipt cardinality differs")

    retained_receipts: list[dict[str, object]] = []
    projected_receipts: list[dict[str, object]] = []
    retained_terminal_binding: dict[str, object] | None = None
    for ordinal, raw_receipt in enumerate(raw_receipts):
        receipt = _mapping(
            raw_receipt, label=f"retained v1 slate receipt[{ordinal}]"
        )
        _validate_v1_self_hash(
            receipt,
            field="slate_derivation_sha256",
            label=f"retained v1 slate receipt[{ordinal}]",
        )
        if (
            receipt.get("schema_version") != core_v1.SLATE_DERIVATION_SCHEMA
            or receipt.get("source_task_ordinal") != ordinal
        ):
            _fail(f"retained v1 slate receipt[{ordinal}] schema/order differs")
        terminal_binding = _mapping(
            receipt.get("catalog_terminal_final_lock_binding"),
            label=f"retained v1 slate receipt[{ordinal}] terminal binding",
        )
        if retained_terminal_binding is None:
            retained_terminal_binding = terminal_binding
        elif terminal_binding != retained_terminal_binding:
            _fail("retained v1 slate terminal bindings differ")
        projected = deepcopy(receipt)
        projected["catalog_terminal_final_lock_binding"] = (
            _replace_terminal_binding_head(
                terminal_binding,
                historical_head=historical,
                descendant_head=descendant,
                label=f"retained v1 slate receipt[{ordinal}] terminal binding",
            )
        )
        projected.pop("slate_derivation_sha256", None)
        projected["slate_derivation_sha256"] = source.canonical_sha256(projected)
        retained_receipts.append(receipt)
        projected_receipts.append(projected)
    if retained_terminal_binding is None:  # Cardinality check makes this defensive.
        _fail("retained v1 slate terminal binding is absent")

    retained_receipt_manifest_sha = source.canonical_sha256(retained_receipts)
    if (
        bundle.get("slate_derivation_manifest_sha256")
        != retained_receipt_manifest_sha
    ):
        _fail("retained v1 bundle slate receipt manifest differs")

    panel = _mapping(
        bundle.get("panel_derivation_receipt"),
        label="retained v1 panel receipt",
    )
    _validate_v1_self_hash(
        panel,
        field="panel_derivation_sha256",
        label="retained v1 panel receipt",
    )
    if (
        panel.get("schema_version") != core_v1.PANEL_DERIVATION_SCHEMA
        or panel.get("task_count") != source.TASK_COUNT
    ):
        _fail("retained v1 panel receipt schema/cardinality differs")
    if panel.get("g0_source_commit_sha") != historical:
        _fail("retained v1 panel G0 source is not the candidate historical HEAD")
    panel_terminal_binding = _mapping(
        panel.get("catalog_terminal_final_lock_binding"),
        label="retained v1 panel terminal binding",
    )
    if panel_terminal_binding != retained_terminal_binding:
        _fail("retained v1 panel/slate terminal bindings differ")
    if panel.get("slate_derivation_manifest_sha256") != retained_receipt_manifest_sha:
        _fail("retained v1 panel slate receipt manifest differs")
    try:
        panel_slates = [
            _mapping(row, label=f"retained v1 panel slate[{ordinal}]")
            for ordinal, row in enumerate(
                core._sequence(panel.get("slates"), label="retained v1 panel slates")
            )
        ]
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc
    if len(panel_slates) != source.TASK_COUNT:
        _fail("retained v1 panel slate cardinality differs")

    projected_panel_slates: list[dict[str, object]] = []
    for ordinal, row in enumerate(panel_slates):
        if (
            row.get("source_task_ordinal") != ordinal
            or row.get("slate_derivation_sha256")
            != retained_receipts[ordinal]["slate_derivation_sha256"]
        ):
            _fail(f"retained v1 panel slate[{ordinal}] receipt order differs")
        projected_row = deepcopy(row)
        projected_row["slate_derivation_sha256"] = projected_receipts[ordinal][
            "slate_derivation_sha256"
        ]
        projected_panel_slates.append(projected_row)

    projected_panel = deepcopy(panel)
    projected_panel["catalog_terminal_final_lock_binding"] = (
        _replace_terminal_binding_head(
            panel_terminal_binding,
            historical_head=historical,
            descendant_head=descendant,
            label="retained v1 panel terminal binding",
        )
    )
    projected_panel["g0_source_commit_sha"] = descendant
    projected_panel["slates"] = projected_panel_slates
    projected_receipt_manifest_sha = source.canonical_sha256(projected_receipts)
    projected_panel["slate_derivation_manifest_sha256"] = (
        projected_receipt_manifest_sha
    )
    projected_panel.pop("panel_derivation_sha256", None)
    projected_panel["panel_derivation_sha256"] = source.canonical_sha256(
        projected_panel
    )

    projected_bundle = deepcopy(bundle)
    projected_bundle["slate_derivation_receipts"] = projected_receipts
    projected_bundle["slate_derivation_manifest_sha256"] = (
        projected_receipt_manifest_sha
    )
    projected_bundle["panel_derivation_receipt"] = projected_panel
    projected_bundle.pop("candidate_authority_bundle_sha256", None)
    projected_bundle["candidate_authority_bundle_sha256"] = (
        source.canonical_sha256(projected_bundle)
    )
    return projected_bundle


def _require_transitive_replay_paths_stable(
    *,
    repository_root: Path,
    historical_head: str,
    descendant_head: str,
    git_blob: core.GitBlob,
    git_status: core.GitStatus,
) -> None:
    """Prove every HEAD-sensitive validator/selection byte stayed exact."""

    try:
        historical = core._commit(
            historical_head, label="transitive historical replay HEAD"
        )
        descendant = core._commit(
            descendant_head, label="transitive descendant replay HEAD"
        )
        status_raw = git_status(repository_root, REPLAY_HEAD_STABLE_PATHS)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"transitive replay path Git boundary failed: {exc}"
        ) from exc
    if type(status_raw) is not bytes or status_raw != b"":
        _fail("transitive replay paths must be tracked-clean at current HEAD")

    repository = Path(repository_root)
    for ordinal, relative_path in enumerate(REPLAY_HEAD_STABLE_PATHS):
        relative = Path(relative_path)
        if (
            relative.is_absolute()
            or not relative.parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            _fail(f"transitive replay path[{ordinal}] differs")
        runtime_path = _G0_RUNTIME_SELECTION_PATHS.get(
            relative_path, repository / relative
        )
        try:
            mode = runtime_path.lstat().st_mode
            historical_raw = git_blob(repository, historical, relative_path)
            descendant_raw = git_blob(repository, descendant, relative_path)
            runtime_raw = runtime_path.read_bytes()
        except Exception as exc:
            raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
                f"transitive replay path[{ordinal}] exact read failed: "
                f"{relative_path}"
            ) from exc
        if (
            stat.S_ISLNK(mode)
            or not stat.S_ISREG(mode)
            or type(historical_raw) is not bytes
            or type(descendant_raw) is not bytes
            or historical_raw != descendant_raw
            or descendant_raw != runtime_raw
        ):
            _fail(
                f"transitive replay path[{ordinal}] changed between candidate "
                f"and descendant HEAD: {relative_path}"
            )


def _historical_git_head(
    *, repository_root: Path, historical_head: str,
) -> core.GitHead:
    """Return a root-bound callback for the second, historical v1 replay."""

    expected_root = Path(repository_root).resolve()
    try:
        retained_head = core._commit(
            historical_head, label="historical v1 replay HEAD"
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc

    def callback(candidate_root: Path) -> str:
        if Path(candidate_root).resolve() != expected_root:
            _fail("historical v1 replay repository root differs")
        return retained_head

    return callback


def _require_current_head_unchanged(
    *, repository_root: Path, expected_head: str,
) -> None:
    try:
        observed = catalog_adapter.SubprocessGitRepositoryV1(
            repository_root
        ).require_current_clean_head()
        expected = core._commit(expected_head, label="expected final clean HEAD")
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate final Git boundary differs: {exc}"
        ) from exc
    if observed != expected:
        _fail("candidate clean HEAD changed during descendant replay")


def _resolve_replay_heads(
    *,
    repository_root: Path,
    bound_head: str,
) -> tuple[
    str,
    recovery.PublicationCapabilityV1,
    recovery.TrackedAttemptBindingV1,
    recovery.PublicationCapabilityV1,
    recovery.TrackedAttemptBindingV1,
]:
    """Resolve the same tracked recovery chain at original and current HEAD."""

    repository = catalog_adapter.SubprocessGitRepositoryV1(repository_root)
    try:
        current_head = repository.require_current_clean_head()
        recovery.require_git_ancestor_v1(
            repository,
            ancestor_commit_sha=bound_head,
            descendant_commit_sha=current_head,
            label="candidate-bound-head-to-current",
        )
        recovery.require_commit_reachable_from_remote_v1(
            repository, commit_sha=bound_head
        )
        recovery.require_commit_reachable_from_remote_v1(
            repository, commit_sha=current_head
        )
        historical_capability, historical_attempt = (
            recovery.resolve_tracked_attempt_binding_v1(
                repository=repository, current_head=bound_head
            )
        )
        descendant_capability, descendant_attempt = (
            recovery.resolve_tracked_attempt_binding_v1(
                repository=repository, current_head=current_head
            )
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate replay Git boundary differs: {exc}"
        ) from exc
    if (
        historical_capability.current_clean_commit_sha != bound_head
        or descendant_capability.current_clean_commit_sha != current_head
        or _capability_stable_projection(historical_capability)
        != _capability_stable_projection(descendant_capability)
        or _attempt_stable_projection(
            historical_attempt, capability=historical_capability
        )
        != _attempt_stable_projection(
            descendant_attempt, capability=descendant_capability
        )
    ):
        _fail("catalog recovery authority changed beyond its replay-time HEAD")
    return (
        current_head,
        historical_capability,
        historical_attempt,
        descendant_capability,
        descendant_attempt,
    )


def reopen_fixed_g0_candidate_authority_from_descendant_v1(
    root_identity: object,
    *,
    repository_root: Path,
    read_exact: core.ReadExact,
    git_head: core.GitHead,
    git_blob: core.GitBlob,
    git_status: core.GitStatus,
) -> release.ReopenedFixedG0CandidateAuthorityV2:
    """Deep-replay candidate-v2 while accepting only replay-HEAD hash drift."""

    retained_root_identity = release._identity(
        root_identity, label="candidate-authority v2 root identity"
    )
    prefix, run_id = release._prefix_from_root_identity(retained_root_identity)
    output_reader = release._scoped_reader(read_exact=read_exact, prefix=prefix)
    root_body, reopened_root_identity = release._exact_json(
        retained_root_identity,
        read_exact=output_reader,
        label="candidate-authority v2 terminal root",
    )
    if root_body.get("schema_version") != release.RELEASE_SCHEMA:
        _fail("candidate-authority legacy root schema rejected")
    try:
        root = release.validate_fixed_g0_candidate_authority_release_structure_v2(
            root_body
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate-authority v2 root structure differs: {exc}"
        ) from exc
    if root.get("target_uri") != reopened_root_identity["uri"]:
        _fail("candidate-authority v2 root outer identity differs")

    retained_binding = _mapping(
        root.get("catalog_recovery_candidate_binding"),
        label="retained candidate binding",
    )
    try:
        bound_head = core._commit(
            retained_binding.get("candidate_implementation_commit_sha"),
            label="candidate implementation bound head",
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            str(exc)
        ) from exc
    (
        current_head,
        historical_capability,
        _historical_attempt,
        descendant_capability,
        _descendant_attempt,
    ) = _resolve_replay_heads(repository_root=repository_root, bound_head=bound_head)
    try:
        callback_head = core._commit(
            git_head(repository_root), label="candidate callback current HEAD"
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate callback Git boundary differs: {exc}"
        ) from exc
    if callback_head != current_head:
        _fail("candidate callback and durable current HEAD differ")
    _require_transitive_replay_paths_stable(
        repository_root=repository_root,
        historical_head=bound_head,
        descendant_head=current_head,
        git_blob=git_blob,
        git_status=git_status,
    )

    try:
        authority, descendant_binding = core._open_outer_and_binding(
            repository_root=repository_root,
            catalog_recovery_outer_identity=root["catalog_recovery_outer_identity"],
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
            candidate_implementation_commit_sha=bound_head,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate outer/code exact replay failed: {exc}"
        ) from exc
    validate_replay_head_only_binding_drift_v1(
        retained_binding=retained_binding,
        descendant_binding=descendant_binding,
        historical_capability_sha256=historical_capability.capability_sha256,
        descendant_capability_sha256=descendant_capability.capability_sha256,
    )

    candidate_release_body, candidate_release_identity = release._exact_json(
        root["candidate_release_identity"],
        read_exact=output_reader,
        label="accepted candidate release",
    )
    try:
        candidate_release = source.validate_accepted_candidate_release_v1(
            candidate_release_body
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"accepted candidate release differs: {exc}"
        ) from exc
    panel, panel_identity = release._exact_json(
        root["panel_derivation_identity"],
        read_exact=output_reader,
        label="outer-bound panel receipt",
    )
    artifacts: list[dict[str, object]] = []
    sidecars: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    artifact_identities: list[dict[str, object]] = []
    sidecar_identities: list[dict[str, object]] = []
    receipt_identities: list[dict[str, object]] = []
    for ordinal, raw_descriptor in enumerate(
        release._sequence(root["objects"], label="objects")
    ):
        descriptor = release._mapping(
            raw_descriptor, label=f"object descriptor[{ordinal}]"
        )
        artifact_body, artifact_identity = release._exact_json(
            descriptor["candidate_artifact_identity"],
            read_exact=output_reader,
            label=f"candidate artifact[{ordinal}]",
        )
        artifact = source.validate_accepted_candidate_artifact_v1(artifact_body)
        sidecar, sidecar_identity = release._exact_json(
            descriptor["lineage_sidecar_identity"],
            read_exact=output_reader,
            label=f"lineage sidecar[{ordinal}]",
        )
        receipt, receipt_identity = release._exact_json(
            descriptor["slate_derivation_identity"],
            read_exact=output_reader,
            label=f"outer-bound slate receipt[{ordinal}]",
        )
        expected_descriptor = release._object_descriptor(
            prefix=prefix,
            source_task_ordinal=ordinal,
            artifact=artifact,
            artifact_identity=artifact_identity,
            sidecar=sidecar,
            sidecar_identity=sidecar_identity,
            receipt=receipt,
            receipt_identity=receipt_identity,
        )
        if source.canonical_json_bytes(descriptor) != source.canonical_json_bytes(
            expected_descriptor
        ):
            _fail(f"object descriptor[{ordinal}] body binding differs")
        artifacts.append(artifact)
        sidecars.append(sidecar)
        receipts.append(receipt)
        artifact_identities.append(artifact_identity)
        sidecar_identities.append(sidecar_identity)
        receipt_identities.append(receipt_identity)

    bundle = release._assemble_bundle(
        candidate_release=candidate_release,
        artifacts=artifacts,
        sidecars=sidecars,
        receipts=receipts,
        panel=panel,
    )
    try:
        core._require_bundle_binding(bundle, expected_binding=retained_binding)
        current_reader, require_complete_current_catalog_replay = (
            core._outer_manifest_gated_reader(
                authority=authority, read_exact=read_exact
            )
        )
        historical_reader, require_complete_historical_catalog_replay = (
            core._outer_manifest_gated_reader(
                authority=authority, read_exact=read_exact
            )
        )
        retained_v1 = core._downgrade_bundle(bundle)
        descendant_v1 = _project_v1_replay_head_only_bundle(
            retained_v1,
            historical_head=bound_head,
            descendant_head=current_head,
        )
        validated_descendant_v1 = (
            core_v1.validate_fixed_g0_candidate_authority_v1(
                descendant_v1,
                repository_root=repository_root,
                catalog_replay_receipt_identity=(
                    authority.inner_replay_receipt_identity
                ),
                read_exact=current_reader,
                git_head=git_head,
                git_blob=git_blob,
                git_status=git_status,
            )
        )
        if source.canonical_json_bytes(
            validated_descendant_v1
        ) != source.canonical_json_bytes(descendant_v1):
            _fail("candidate descendant v1 replay differs from HEAD projection")
        require_complete_current_catalog_replay()
        historical_head_callback = _historical_git_head(
            repository_root=repository_root,
            historical_head=bound_head,
        )
        validated_historical_v1 = (
            core_v1.validate_fixed_g0_candidate_authority_v1(
                retained_v1,
                repository_root=repository_root,
                catalog_replay_receipt_identity=(
                    authority.inner_replay_receipt_identity
                ),
                read_exact=historical_reader,
                git_head=historical_head_callback,
                git_blob=git_blob,
                git_status=git_status,
            )
        )
        if source.canonical_json_bytes(
            validated_historical_v1
        ) != source.canonical_json_bytes(retained_v1):
            _fail("candidate historical v1 replay differs from retained bundle")
        require_complete_historical_catalog_replay()
        validated_panel = core._mapping(
            validated_descendant_v1.get("panel_derivation_receipt"),
            label="validated v1 panel",
        )
        material_projection = {
            "slate_predecessor_bindings": [
                {"catalog_binding": receipt["catalog_binding"]}
                for receipt in core._sequence(
                    validated_descendant_v1.get("slate_derivation_receipts"),
                    label="validated v1 slate receipts",
                )
            ],
            "catalog_release_identity": validated_panel["catalog_release_identity"],
            "catalog_release_sha256": validated_panel["catalog_release_sha256"],
            "catalog_replay_receipt_identity": validated_panel[
                "catalog_replay_receipt_identity"
            ],
            "catalog_replay_receipt_sha256": validated_panel[
                "catalog_replay_receipt_sha256"
            ],
        }
        core._require_outer_manifest(authority=authority, material=material_projection)
        rebuilt_bundle = core._upgrade_bundle(
            validated_historical_v1, binding=retained_binding
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error(
            f"candidate-authority v2 predecessor replay failed: {exc}"
        ) from exc
    if source.canonical_json_bytes(rebuilt_bundle) != source.canonical_json_bytes(
        bundle
    ):
        _fail("candidate-authority v2 bundle differs from predecessor replay")

    expected_root = release._build_root(
        prefix=prefix,
        run_id=run_id,
        bundle=rebuilt_bundle,
        candidate_release_identity=candidate_release_identity,
        panel_identity=panel_identity,
        artifact_identities=artifact_identities,
        sidecar_identities=sidecar_identities,
        receipt_identities=receipt_identities,
    )
    if source.canonical_json_bytes(root) != source.canonical_json_bytes(expected_root):
        _fail("candidate-authority v2 root predecessor replay differs")
    _require_current_head_unchanged(
        repository_root=repository_root, expected_head=current_head
    )
    return release.ReopenedFixedG0CandidateAuthorityV2(
        root=root,
        root_identity=reopened_root_identity,
        authority_bundle=rebuilt_bundle,
        candidate_release=candidate_release,
        candidate_release_identity=candidate_release_identity,
    )


__all__ = [
    "ADAPTER_MODULE_PATH",
    "CorpusR6FixedG0CandidateAuthorityDescendantReopenV1Error",
    "REPLAY_HEAD_STABLE_IMPLEMENTATION_PATHS",
    "REPLAY_HEAD_STABLE_PATHS",
    "REPLAY_HEAD_STABLE_SELECTION_PATHS",
    "reopen_fixed_g0_candidate_authority_from_descendant_v1",
    "validate_replay_head_only_binding_drift_v1",
]
