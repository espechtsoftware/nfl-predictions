"""Create-once strategy-registry release from one accepted 54x7 batch.

The release is a compact, rebuildable graph authority.  It does not copy
world matrices or realized outcomes into Neo4j.  It registers the seven
request-local corpus-generation parameter sets as fill presets, the frozen
exact-80 selector as one retrieval preset, a bounded three-lineup-per-arm
structural sample, and the score-free simulated measurements already present
in each independently verified task.

The legal-feasibility selector used all R0--R4 worlds.  Consequently these
measurements are deliberately labelled ``all-worlds-descriptive``.  This
producer cannot emit a promotion decision or active pointer and never calls a
historical-outcome reader.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_strategy_registry as registry
from nfl_dfs.research import lr8_later_period_source as later_source
from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    ExactObjectStore,
    ObjectIdentity,
    _accepted_parametric_suite,
    _accepted_task0,
    object_identity,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    Neo4jLoadPlan,
    canonical_json_bytes,
    canonical_sha256,
    parse_canonical_json_bytes,
)


PUBLICATION_SCHEMA: Final = (
    "corpus-strategy-registry-release-publication/v1"
)
PUBLICATION_INTENT_SCHEMA: Final = (
    "corpus-strategy-registry-release-intent/v1"
)
VARIANT_RESULT_SCHEMA: Final = "corpus-legal-feasibility-variant-result/v2"
RUNTIME_POLICY_SCHEMA: Final = "corpus-runtime-effective-policy/v1"
LINEUP_SAMPLE_PER_ARM: Final = 3
TASK_COUNT: Final = 54
ARM_COUNT: Final = 7
MATRIX_CELL_COUNT: Final = TASK_COUNT * ARM_COUNT
WORLD_COUNT: Final = 50_000
SELECTED_COUNT: Final = 80

_SHA = re.compile(r"^[0-9a-f]{64}$")
_BUILD = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class CorpusStrategyRegistryReleaseError(RuntimeError):
    """The accepted batch cannot produce the governed registry release."""


@dataclass(frozen=True, slots=True)
class AcceptedVariantEvidence:
    parameter_set_id: str
    parameter_set_sha256: str
    effective_policy_identity: dict[str, object]
    effective_policy: dict[str, object]
    result_identity: dict[str, object]
    result: dict[str, object]


@dataclass(frozen=True, slots=True)
class AcceptedTaskEvidence:
    task_index: int
    task_acceptance_identity: dict[str, object]
    task_acceptance: dict[str, object]
    task_result_identity: dict[str, object]
    task_result: dict[str, object]
    science_terminal_identity: dict[str, object]
    science_terminal: dict[str, object]
    independent_verification_identity: dict[str, object]
    independent_verification: dict[str, object]
    variants: tuple[AcceptedVariantEvidence, ...]


@dataclass(frozen=True, slots=True)
class AcceptedBatchEvidence:
    retrieval_plan: Neo4jLoadPlan
    retrieval_terminal_identity: dict[str, object]
    batch_acceptance_identity: dict[str, object]
    batch_acceptance: dict[str, object]
    batch_completion_identity: dict[str, object]
    batch_manifest_identity: dict[str, object]
    batch_manifest: dict[str, object]
    source_freeze_identity: dict[str, object]
    source_freeze: dict[str, object]
    exact_release: dict[str, str]
    tasks: tuple[AcceptedTaskEvidence, ...]


@dataclass(frozen=True, slots=True)
class PublishedStrategyRegistryRelease:
    release_identity: ObjectIdentity
    publication_identity: ObjectIdentity
    release: dict[str, object]
    publication: dict[str, object]


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusStrategyRegistryReleaseError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise CorpusStrategyRegistryReleaseError(f"{label} keys differ")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if type(value) is not list:
        raise CorpusStrategyRegistryReleaseError(f"{label} must be an array")
    return list(value)


def _timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise CorpusStrategyRegistryReleaseError(f"{label} differs")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return object_identity(value, label=label).as_dict()
    except CorpusNeo4jTransportError as exc:
        raise CorpusStrategyRegistryReleaseError(f"{label} differs") from exc


def _identity_key(value: object) -> tuple[object, ...]:
    row = _identity(value, label="object identity")
    return tuple(row[key] for key in ("uri", "generation", "sha256", "bytes"))


def _read_json(
    storage: ExactObjectStore, value: object, *, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = object_identity(value, label=f"{label} identity")
    raw = storage.read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity.bytes
        or sha256(raw).hexdigest() != identity.sha256
    ):
        raise CorpusStrategyRegistryReleaseError(
            f"{label} exact content identity differs"
        )
    try:
        parsed = parse_canonical_json_bytes(raw, label=label)
    except Exception as exc:
        raise CorpusStrategyRegistryReleaseError(
            f"{label} is not canonical JSON"
        ) from exc
    return identity.as_dict(), _mapping(parsed, label=label)


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    digest = value.get(field)
    if (
        not isinstance(digest, str)
        or _SHA.fullmatch(digest) is None
        or digest != canonical_sha256({
            key: row for key, row in value.items() if key != field
        })
    ):
        raise CorpusStrategyRegistryReleaseError(f"{label} self-hash differs")


def _with_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    retained = dict(body)
    retained[field] = canonical_sha256(retained)
    return retained


def _outcome_firewall(value: Mapping[str, object], *, label: str) -> None:
    if (
        value.get("uses_realized_outcomes") is not False
        or value.get("outcome_columns_read") != []
        or value.get("historical_scoring_licensed") is not False
    ):
        raise CorpusStrategyRegistryReleaseError(
            f"{label} outcome firewall differs"
        )


def _prefix(value: object) -> str:
    if not isinstance(value, str) or not value.startswith("gs://"):
        raise CorpusStrategyRegistryReleaseError("output prefix differs")
    if not value.endswith("/") or "//" in value.removeprefix("gs://"):
        raise CorpusStrategyRegistryReleaseError("output prefix differs")
    bucket, separator, name = value.removeprefix("gs://").partition("/")
    if not bucket or not separator or not name:
        raise CorpusStrategyRegistryReleaseError("output prefix differs")
    return value


def _release_binding(value: object, *, label: str) -> dict[str, str]:
    row = _mapping(value, label=label)
    if (
        set(row) != {"code_commit", "image", "build_id"}
        or not isinstance(row.get("code_commit"), str)
        or _COMMIT.fullmatch(str(row["code_commit"])) is None
        or not isinstance(row.get("image"), str)
        or _IMAGE.fullmatch(str(row["image"])) is None
        or not isinstance(row.get("build_id"), str)
        or _BUILD.fullmatch(str(row["build_id"])) is None
    ):
        raise CorpusStrategyRegistryReleaseError(f"{label} differs")
    return {
        field: str(row[field])
        for field in ("code_commit", "image", "build_id")
    }


def _registry_identifier(value: object) -> str:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", value) is None
    ):
        raise CorpusStrategyRegistryReleaseError("registry ID differs")
    return value


def _accepted_input_identities(
    evidence: AcceptedBatchEvidence,
) -> list[dict[str, object]]:
    retained: dict[tuple[object, ...], dict[str, object]] = {}

    def add(value: object) -> None:
        row = _identity(value, label="accepted input identity")
        retained[_identity_key(row)] = row

    def walk(value: object) -> None:
        if isinstance(value, Mapping):
            if set(value) == {"uri", "generation", "sha256", "bytes"}:
                add(value)
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, Sequence) and not isinstance(
            value, (str, bytes)
        ):
            for child in value:
                walk(child)

    for identity in (
        evidence.retrieval_terminal_identity,
        evidence.batch_acceptance_identity,
        evidence.batch_completion_identity,
        evidence.batch_manifest_identity,
        evidence.source_freeze_identity,
    ):
        add(identity)
    for task in evidence.tasks:
        for identity in (
            task.task_acceptance_identity,
            task.task_result_identity,
            task.science_terminal_identity,
            task.independent_verification_identity,
        ):
            add(identity)
        for variant in task.variants:
            add(variant.effective_policy_identity)
            add(variant.result_identity)
    for body in (
        evidence.batch_acceptance,
        evidence.batch_manifest,
        evidence.source_freeze,
    ):
        walk(body)
    return sorted(retained.values(), key=_identity_key)


def _bucket(uri: str) -> str:
    return uri.removeprefix("gs://").split("/", 1)[0]


def _validate_variant(
    *,
    result: Mapping[str, object],
    result_identity: Mapping[str, object],
    policy: Mapping[str, object],
    policy_identity: Mapping[str, object],
    parameter_set: Mapping[str, object],
    task: Mapping[str, object],
) -> None:
    _self_hash(result, field="result_sha256", label="variant result")
    profile = _mapping(result.get("profile"), label="variant profile")
    coverage = _mapping(result.get("coverage"), label="variant coverage")
    slate = _mapping(result.get("slate"), label="variant slate")
    unique = _sequence(result.get("unique_rosters"), label="unique rosters")
    selected = _sequence(
        result.get("selected_rosters"), label="selected rosters"
    )
    unique_rows = [tuple(_sequence(row, label="unique roster")) for row in unique]
    selected_rows = [
        tuple(_sequence(row, label="selected roster")) for row in selected
    ]
    expected_values = _mapping(
        parameter_set.get("values"), label="parameter-set values"
    )
    if (
        result.get("schema") != VARIANT_RESULT_SCHEMA
        or profile.get("ordinal") != parameter_set.get("ordinal")
        or profile.get("parameter_set_id")
        != parameter_set.get("parameter_set_id")
        or profile.get("parameter_set_sha256")
        != parameter_set.get("parameter_set_sha256")
        or profile.get("parameter_values") != expected_values
        or slate != {
            "season": task["season"],
            "week": task["week"],
            "slate_id": task["slate_id"],
        }
        or coverage.get("unique_candidates") != len(unique_rows)
        or coverage.get("selected_entries") != SELECTED_COUNT
        or len(selected_rows) != SELECTED_COUNT
        or not unique_rows
        or len(unique_rows) != len(set(unique_rows))
        or len(selected_rows) != len(set(selected_rows))
        or not set(selected_rows).issubset(set(unique_rows))
        or any(len(row) != 9 or len(set(row)) != 9 for row in unique_rows)
    ):
        raise CorpusStrategyRegistryReleaseError(
            "variant result accepted-batch binding differs"
        )
    _outcome_firewall(result, label="variant result")
    parameter_payload = _mapping(
        policy.get("parameter_set"), label="runtime parameter set"
    )
    if (
        policy.get("schema") != RUNTIME_POLICY_SCHEMA
        or parameter_payload != profile
        or policy.get("uses_realized_outcomes") is not False
        or policy.get("outcome_columns_read") != []
        or policy.get("historical_scoring_licensed") is not False
        or policy.get("production_change_licensed") is not False
        or result_identity["sha256"] != sha256(
            canonical_json_bytes(result)
        ).hexdigest()
        or policy_identity["sha256"] != sha256(
            canonical_json_bytes(policy)
        ).hexdigest()
    ):
        raise CorpusStrategyRegistryReleaseError(
            "runtime policy accepted-batch binding differs"
        )


def reopen_accepted_batch_evidence(
    *,
    storage: ExactObjectStore,
    retrieval_terminal_identity: object,
    batch_acceptance_identity: object,
) -> AcceptedBatchEvidence:
    """Reopen the complete accepted lattice before deriving any registry row."""
    try:
        _, retrieval_plan = _accepted_task0(
            storage, retrieval_terminal_identity
        )
        suite, _ = _accepted_parametric_suite(
            storage=storage,
            batch_acceptance_identity_value=batch_acceptance_identity,
            retrieval_plan=retrieval_plan,
        )
    except Exception as exc:
        raise CorpusStrategyRegistryReleaseError(
            "accepted retrieval/54x7 batch evidence differs"
        ) from exc
    retained_retrieval = _identity(
        retrieval_terminal_identity, label="retrieval terminal"
    )
    acceptance_identity, acceptance = _read_json(
        storage, batch_acceptance_identity, label="batch acceptance"
    )
    completion_identity = _identity(
        acceptance.get("batch_completion"), label="batch completion"
    )
    if (
        suite.get("task_count") != TASK_COUNT
        or suite.get("parameter_set_count") != ARM_COUNT
        or suite.get("matrix_cell_count") != MATRIX_CELL_COUNT
        or suite.get("batch_acceptance") != acceptance_identity
        or suite.get("batch_completion") != completion_identity
    ):
        raise CorpusStrategyRegistryReleaseError(
            "accepted batch lattice differs"
        )

    task_rows: list[AcceptedTaskEvidence] = []
    manifest_identity: dict[str, object] | None = None
    manifest: dict[str, object] | None = None
    source_identity: dict[str, object] | None = None
    source: dict[str, object] | None = None
    exact_release: dict[str, str] | None = None
    parameter_sets: list[object] | None = None
    manifest_tasks: list[object] | None = None
    for task_index, raw_summary in enumerate(
        _sequence(suite.get("tasks"), label="accepted suite tasks")
    ):
        summary = _mapping(raw_summary, label=f"accepted task[{task_index}]")
        acceptance_id, task_acceptance = _read_json(
            storage,
            summary.get("task_acceptance"),
            label=f"task[{task_index}] acceptance",
        )
        result_id, task_result = _read_json(
            storage,
            summary.get("task_result"),
            label=f"task[{task_index}] result",
        )
        terminal_id, terminal = _read_json(
            storage,
            summary.get("science_terminal"),
            label=f"task[{task_index}] science terminal",
        )
        verification_id, verification = _read_json(
            storage,
            summary.get("independent_verification"),
            label=f"task[{task_index}] independent verification",
        )
        if manifest_identity is None:
            manifest_identity, raw_manifest = _read_json(
                storage,
                task_result.get("batch_manifest_identity"),
                label="batch manifest",
            )
            try:
                manifest = batch.validate_batch_manifest(raw_manifest)
            except Exception as exc:
                raise CorpusStrategyRegistryReleaseError(
                    "batch manifest does not replay"
                ) from exc
            parameter_sets = _sequence(
                manifest.get("parameter_sets"), label="parameter sets"
            )
            manifest_tasks = _sequence(manifest.get("tasks"), label="tasks")
            common = _mapping(manifest.get("common_law"), label="common law")
            sources = _mapping(
                common.get("source_receipts"), label="source receipts"
            )
            source_identity, raw_source = _read_json(
                storage,
                sources.get("later_source_freeze"),
                label="later source freeze",
            )
            try:
                source = later_source.validate_source_freeze(
                    raw_source,
                    expected_freeze_sha256=str(
                        common["later_source_freeze_manifest_sha256"]
                    ),
                )
            except Exception as exc:
                raise CorpusStrategyRegistryReleaseError(
                    "later source freeze does not replay"
                ) from exc
            _, code_source = _read_json(
                storage, common.get("code_source"), label="code source"
            )
            commit = code_source.get("source_commit_sha")
            build_id = code_source.get("cloud_build_id")
            image_row = _mapping(
                code_source.get("immutable_image"), label="immutable image"
            )
            image = image_row.get("uri")
            if (
                not isinstance(commit, str)
                or _COMMIT.fullmatch(commit) is None
                or not isinstance(build_id, str)
                or _BUILD.fullmatch(build_id) is None
                or not isinstance(image, str)
                or image_row != common.get("immutable_image")
                or "@sha256:" not in image
            ):
                raise CorpusStrategyRegistryReleaseError(
                    "batch code/build/image authority differs"
                )
            exact_release = {
                "code_commit": commit,
                "image": image,
                "build_id": build_id,
            }
        assert manifest_identity is not None
        assert manifest is not None
        assert parameter_sets is not None
        assert manifest_tasks is not None
        expected_task = _mapping(
            manifest_tasks[task_index], label=f"manifest task[{task_index}]"
        )
        if (
            task_result.get("batch_manifest_identity") != manifest_identity
            or task_result.get("task_index") != task_index
            or task_result.get("task_sha256") != expected_task.get("task_sha256")
            or task_result.get("slate_id") != expected_task.get("slate_id")
            or task_acceptance.get("accepted_at_utc") is None
            or task_acceptance.get("task_result") != result_id
            or task_acceptance.get("science_terminal") != terminal_id
            or task_acceptance.get("independent_verification")
            != verification_id
        ):
            raise CorpusStrategyRegistryReleaseError(
                f"accepted task[{task_index}] binding differs"
            )
        _timestamp(
            task_acceptance["accepted_at_utc"],
            label=f"task[{task_index}] acceptance timestamp",
        )
        variants: list[AcceptedVariantEvidence] = []
        for ordinal, raw_variant in enumerate(
            _sequence(task_result.get("variant_results"), label="variant results")
        ):
            variant_row = _mapping(
                raw_variant, label=f"task[{task_index}] variant[{ordinal}]"
            )
            parameter_set = _mapping(
                parameter_sets[ordinal], label=f"parameter set[{ordinal}]"
            )
            policy_id, policy = _read_json(
                storage,
                variant_row.get("effective_policy_receipt"),
                label=f"task[{task_index}] policy[{ordinal}]",
            )
            variant_id, variant = _read_json(
                storage,
                variant_row.get("result_object"),
                label=f"task[{task_index}] variant result[{ordinal}]",
            )
            _validate_variant(
                result=variant,
                result_identity=variant_id,
                policy=policy,
                policy_identity=policy_id,
                parameter_set=parameter_set,
                task=expected_task,
            )
            variants.append(AcceptedVariantEvidence(
                parameter_set_id=str(parameter_set["parameter_set_id"]),
                parameter_set_sha256=str(parameter_set["parameter_set_sha256"]),
                effective_policy_identity=policy_id,
                effective_policy=policy,
                result_identity=variant_id,
                result=variant,
            ))
        if len(variants) != ARM_COUNT:
            raise CorpusStrategyRegistryReleaseError(
                f"task[{task_index}] does not cover seven arms"
            )
        task_rows.append(AcceptedTaskEvidence(
            task_index=task_index,
            task_acceptance_identity=acceptance_id,
            task_acceptance=task_acceptance,
            task_result_identity=result_id,
            task_result=task_result,
            science_terminal_identity=terminal_id,
            science_terminal=terminal,
            independent_verification_identity=verification_id,
            independent_verification=verification,
            variants=tuple(variants),
        ))
    if (
        len(task_rows) != TASK_COUNT
        or manifest_identity is None
        or manifest is None
        or source_identity is None
        or source is None
        or exact_release is None
    ):
        raise CorpusStrategyRegistryReleaseError(
            "accepted batch evidence is incomplete"
        )
    return AcceptedBatchEvidence(
        retrieval_plan=retrieval_plan,
        retrieval_terminal_identity=retained_retrieval,
        batch_acceptance_identity=acceptance_identity,
        batch_acceptance=acceptance,
        batch_completion_identity=completion_identity,
        batch_manifest_identity=manifest_identity,
        batch_manifest=manifest,
        source_freeze_identity=source_identity,
        source_freeze=source,
        exact_release=exact_release,
        tasks=tuple(task_rows),
    )


def _typed_parameters(values: Mapping[str, object]) -> list[dict[str, object]]:
    rows = []
    for name, value in sorted(values.items()):
        if type(value) is bool:
            kind = "boolean"
        elif type(value) is int:
            kind = "integer"
        elif type(value) is float:
            kind = "number"
        elif isinstance(value, str):
            kind = "string"
        else:
            kind = "json"
        rows.append({"name": name, "type": kind, "value": value})
    return rows


def _graph_identifier(value: object, *, label: str) -> str:
    """Translate a source identifier into the registry's stable ID alphabet.

    The frozen DK catalogs use values such as ``DST_ATL`` and ``CHI|GB``.
    Registry logical identifiers are deliberately lowercase and do not admit
    the pipe separator, so the structural projection must canonicalize those
    values before it builds player/game relationships.
    """
    if not isinstance(value, str) or not value:
        raise CorpusStrategyRegistryReleaseError(f"{label} differs")
    retained = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-._")
    if (
        not retained
        or len(retained) > 128
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", retained) is None
    ):
        raise CorpusStrategyRegistryReleaseError(
            f"{label} cannot be represented in the graph"
        )
    return retained


def _publish_json(
    storage: ExactObjectStore,
    *,
    uri: str,
    value: Mapping[str, object],
) -> dict[str, object]:
    raw = canonical_json_bytes(value)
    identity = storage.publish_create_once(uri, raw)
    reopened = storage.read_exact(identity)
    if reopened != raw:
        raise CorpusStrategyRegistryReleaseError(
            "create-once registry object did not reopen exactly"
        )
    return identity.as_dict()


def _preset(
    *, kind: str, preset_id: str, parameters: list[dict[str, object]],
    description: str,
) -> dict[str, object]:
    schema, field = (
        (registry.FILL_PRESET_SCHEMA, "fill_preset_sha256")
        if kind == "fill"
        else (registry.RETRIEVAL_PRESET_SCHEMA, "retrieval_preset_sha256")
    )
    return _with_hash({
        "schema_version": schema,
        "publication_mode": "create_once",
        "preset_id": preset_id,
        "version": 1,
        "parameters": parameters,
        "description": description,
        "deprecated": False,
        "research_only": True,
        "production_policy_authority": False,
    }, field=field)


def _lineup_id(roster: Sequence[object]) -> str:
    return "lineup-" + canonical_sha256(list(roster))


def _structure(
    *, task_index: int, slate: Mapping[str, object], lineups: Sequence[Sequence[str]],
) -> dict[str, object]:
    catalog = [
        _mapping(row, label="source catalog row")
        for row in _sequence(slate.get("catalog"), label="source catalog")
    ]
    player_id_by_source = {
        str(row["id"]): _graph_identifier(
            row["id"], label="source player ID"
        )
        for row in catalog
    }
    if len(set(player_id_by_source.values())) != len(player_id_by_source):
        raise CorpusStrategyRegistryReleaseError(
            "source player IDs alias after graph canonicalization"
        )
    players = [{
        "player_id": player_id_by_source[str(row["id"])],
        "display_name": str(row["id"]),
        "team": _graph_identifier(row["team"], label="source team"),
        "positions": [str(row["pos"])],
    } for row in catalog]
    player_by_id = {
        player_id_by_source[str(row["id"])]: row for row in catalog
    }
    game_id_by_source = {
        str(row["game_id"]): _graph_identifier(
            row["game_id"], label="source game ID"
        )
        for row in catalog
    }
    if len(set(game_id_by_source.values())) != len(game_id_by_source):
        raise CorpusStrategyRegistryReleaseError(
            "source game IDs alias after graph canonicalization"
        )
    team_pairs: dict[str, set[str]] = {}
    for row in catalog:
        game_id = game_id_by_source[str(row["game_id"])]
        team_pairs.setdefault(game_id, set()).update(
            (
                _graph_identifier(row["team"], label="source team"),
                _graph_identifier(row["opp"], label="source opponent"),
            )
        )
    games = []
    teams = []
    for game_id, raw_teams in sorted(team_pairs.items()):
        retained_teams = sorted(raw_teams)
        if len(retained_teams) != 2:
            raise CorpusStrategyRegistryReleaseError(
                f"source game {game_id} does not bind exactly two teams"
            )
        first, second = retained_teams
        games.append({
            "game_id": game_id,
            "home_team": first,
            "away_team": second,
        })
        teams.extend((
            {"team": first, "game_id": game_id, "opponent": second},
            {"team": second, "game_id": game_id, "opponent": first},
        ))
    lineup_rows = []
    normalized_lineups = set()
    for row in lineups:
        try:
            normalized_lineups.add(tuple(
                player_id_by_source[str(player)] for player in row
            ))
        except KeyError as exc:
            raise CorpusStrategyRegistryReleaseError(
                "bounded lineup sample contains an unknown source player"
            ) from exc
    for roster in sorted(normalized_lineups, key=_lineup_id):
        if len(roster) != 9 or not set(roster).issubset(player_by_id):
            raise CorpusStrategyRegistryReleaseError(
                "bounded lineup sample differs from the source catalog"
            )
        lineup_rows.append({
            "lineup_id": _lineup_id(roster),
            "player_ids": list(roster),
            "salary": sum(int(player_by_id[player]["salary"]) for player in roster),
            "source": "generated",
        })
    body = {
        "schema_version": registry.STRUCTURE_SCHEMA,
        "publication_mode": "create_once",
        "task_index": task_index,
        "slate_id": slate["slate_id"],
        "games": games,
        "teams": sorted(teams, key=lambda row: str(row["team"])),
        "players": players,
        "lineups": lineup_rows,
    }
    return _with_hash(body, field="slate_structure_sha256")


def _artifact_pointer(
    role: str, identity: Mapping[str, object], *, matrix: bool,
) -> dict[str, object]:
    return {
        "role": role,
        "format": "retained-object-pointer-v1",
        "object_identity": dict(identity),
        "contains_world_matrix": matrix,
        "contains_raw_outcomes": False,
    }


def _metrics(
    *,
    verification: Mapping[str, object],
    ordinal: int,
    baseline: Mapping[str, object] | None,
) -> list[dict[str, object]]:
    endpoints = _sequence(
        verification.get("score_free_endpoint_summaries"),
        label="endpoint summaries",
    )
    coverages = _sequence(
        verification.get("score_matrix_coverage_summaries"),
        label="coverage summaries",
    )
    outside_rows = _sequence(
        verification.get("outside_incumbent_law_summaries"),
        label="outside-law summaries",
    )
    endpoint = _mapping(endpoints[ordinal], label="endpoint summary")
    coverage = _mapping(coverages[ordinal], label="coverage summary")
    outside = _mapping(outside_rows[ordinal], label="outside-law summary")
    values = (
        (
            "generated-unique-roster-count",
            coverage.get("generated_unique_roster_count"),
            "lineups", "descriptive", 1,
        ),
        (
            "outside-incumbent-law-unique-count",
            outside.get("outside_incumbent_law_unique_count"),
            "lineups", "descriptive", 1,
        ),
        (
            "simulated-candidate-ceiling",
            endpoint.get("simulated_candidate_ceiling_c"),
            "fantasy-points", "maximize", WORLD_COUNT,
        ),
        (
            "simulated-conversion-gap",
            endpoint.get("simulated_conversion_gap_c_minus_s"),
            "fantasy-points", "minimize", WORLD_COUNT,
        ),
        (
            "simulated-exact80-maximum",
            endpoint.get("simulated_exact80_maximum_s"),
            "fantasy-points", "maximize", WORLD_COUNT,
        ),
    )
    rows = []
    for metric_id, value, unit, direction, sample_count in values:
        if type(value) not in {int, float} or isinstance(value, bool):
            raise CorpusStrategyRegistryReleaseError(
                f"accepted simulated metric {metric_id} differs"
            )
        rows.append({
            "metric_id": metric_id,
            "name": metric_id,
            "value": value,
            "unit": unit,
            "direction": direction,
            "scope": "all-worlds-descriptive",
            "sample_count": sample_count,
            "paired_key": "r0-r4-world-id",
            "baseline_experiment_run": (
                None if baseline is None else dict(baseline)
            ),
        })
    return rows


def _evidence_binding(
    *,
    evidence_id: str,
    experiment_id: str,
    role: str,
    task_index: int,
    slate_id: str,
    exact_release: Mapping[str, str],
    dependencies: Sequence[Mapping[str, object]],
    metrics_sha256: str | None,
    created_at_utc: str,
) -> dict[str, object]:
    return _with_hash({
        "schema_version": registry.RETROSPECTIVE_EVIDENCE_BINDING_SCHEMA,
        "publication_mode": "create_once",
        "derivation_mode": "retrospective-pointer-binding",
        "evidence_id": evidence_id,
        "experiment_id": experiment_id,
        "evidence_role": role,
        "task_index": task_index,
        "slate_id": slate_id,
        "exact_release": dict(exact_release),
        "dependencies": sorted(
            (dict(row) for row in dependencies), key=_identity_key
        ),
        "accepted": True,
        "complete": True,
        "computed_metrics_sha256": metrics_sha256,
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
        "created_at_utc": created_at_utc,
    }, field="evidence_binding_sha256")


def _publish_validated_strategy_registry_release(
    *,
    storage: ExactObjectStore,
    evidence: AcceptedBatchEvidence,
    registry_id: str,
    output_prefix: str,
    created_at_utc: str,
    producer_release: Mapping[str, object],
) -> PublishedStrategyRegistryRelease:
    """Publish the bounded release and its transitive create-once receipt."""
    prefix = _prefix(output_prefix)
    retained_registry_id = _registry_identifier(registry_id)
    timestamp = _timestamp(created_at_utc, label="release timestamp")
    source_execution_release = _release_binding(
        evidence.exact_release, label="source execution release"
    )
    retained_producer_release = _release_binding(
        producer_release, label="registry producer release"
    )
    if (
        len(evidence.tasks) != TASK_COUNT
        or evidence.batch_manifest.get("parameter_sets") is None
        or evidence.source_freeze.get("slates") is None
    ):
        raise CorpusStrategyRegistryReleaseError(
            "accepted evidence does not cover 54x7"
        )
    input_identities = _accepted_input_identities(evidence)
    output_bucket = _bucket(prefix)
    if output_bucket in {
        _bucket(str(row["uri"])) for row in input_identities
    }:
        raise CorpusStrategyRegistryReleaseError(
            "registry output must use a bucket dedicated away from all inputs"
        )
    intent_body = {
        "schema_version": PUBLICATION_INTENT_SCHEMA,
        "publication_mode": "create_once",
        "registry_id": retained_registry_id,
        "output_prefix": prefix,
        "retrieval_terminal": evidence.retrieval_terminal_identity,
        "batch_acceptance": evidence.batch_acceptance_identity,
        "batch_completion": evidence.batch_completion_identity,
        "batch_manifest": evidence.batch_manifest_identity,
        "source_freeze": evidence.source_freeze_identity,
        "accepted_input_objects": input_identities,
        "accepted_input_identity_set_sha256": canonical_sha256(
            input_identities
        ),
        "source_execution_release": source_execution_release,
        "producer_release": retained_producer_release,
        "task_count": TASK_COUNT,
        "fill_preset_count": ARM_COUNT,
        "experiment_count": MATRIX_CELL_COUNT,
        "heldout_split_registered": False,
        "selection_informed_by_heldout": False,
        "selection_informed_by_evaluation_worlds": True,
        "metric_scope": "all-worlds-descriptive",
        "realized_namespace_reserved": True,
        "uses_realized_outcomes": False,
        "automatic_promotion": False,
        "production_policy_authority": False,
        "created_at_utc": timestamp,
    }
    intent = _with_hash(
        intent_body, field="publication_intent_sha256"
    )
    intent_identity = _publish_json(
        storage, uri=f"{prefix}publication-intent.json", value=intent
    )
    parameter_sets = [
        _mapping(row, label="parameter set")
        for row in _sequence(
            evidence.batch_manifest["parameter_sets"], label="parameter sets"
        )
    ]
    if len(parameter_sets) != ARM_COUNT:
        raise CorpusStrategyRegistryReleaseError("seven fill presets are required")

    fill_identities: list[dict[str, object]] = []
    fill_by_id: dict[str, tuple[dict[str, object], list[dict[str, object]]]] = {}
    for row in parameter_sets:
        preset_id = "fill-" + str(row["parameter_set_id"])
        parameters = _typed_parameters(
            _mapping(row["values"], label="fill parameter values")
        )
        body = _preset(
            kind="fill",
            preset_id=preset_id,
            parameters=parameters,
            description=(
                "Accepted request-local legal-feasibility generation arm; "
                "research only."
            ),
        )
        identity = _publish_json(
            storage,
            uri=f"{prefix}presets/fill/{preset_id}/v1.json",
            value=body,
        )
        fill_identities.append(identity)
        fill_by_id[str(row["parameter_set_id"])] = (identity, parameters)

    common = _mapping(
        evidence.batch_manifest["common_law"], label="common law"
    )
    retrieval_parameters = _typed_parameters({
        "cbwu-authority": common["cbwu"],
        "exact-80-authority": common["exact_80"],
        "line-194-authority": common["line_194"],
        "selected-entry-budget": _mapping(
            common["solve_budget"], label="solve budget"
        )["selected_entry_budget"],
        "selector-authority": common["selector"],
    })
    retrieval_body = _preset(
        kind="retrieval",
        preset_id="retrieval-exact80-line194",
        parameters=retrieval_parameters,
        description=(
            "Frozen exact-80 line-194 selector used by the accepted 54x7 "
            "score-free suite."
        ),
    )
    retrieval_identity = _publish_json(
        storage,
        uri=f"{prefix}presets/retrieval/retrieval-exact80-line194/v1.json",
        value=retrieval_body,
    )

    source_slates = [
        _mapping(row, label="source slate")
        for row in _sequence(evidence.source_freeze["slates"], label="source slates")
    ]
    if len(source_slates) != TASK_COUNT:
        raise CorpusStrategyRegistryReleaseError("source slate lattice differs")
    structure_identities: list[dict[str, object]] = []
    snapshot_identities: list[dict[str, object]] = []
    experiment_identities: list[dict[str, object]] = []
    metric_identities: list[dict[str, object]] = []
    sampled_lineup_count = 0

    for expected_task_index, task in enumerate(evidence.tasks):
        source_slate = source_slates[task.task_index]
        if (
            source_slate.get("slate_id") != task.task_result.get("slate_id")
            or task.task_index != expected_task_index
        ):
            raise CorpusStrategyRegistryReleaseError(
                "accepted task/source slate order differs"
            )
        samples_by_arm: dict[str, list[list[str]]] = {}
        all_samples: list[list[str]] = []
        for variant in task.variants:
            selected = [
                [str(player) for player in _sequence(row, label="selected roster")]
                for row in _sequence(
                    variant.result["selected_rosters"], label="selected rosters"
                )
            ]
            sample = selected[:LINEUP_SAMPLE_PER_ARM]
            samples_by_arm[variant.parameter_set_id] = sample
            all_samples.extend(sample)
        structure = _structure(
            task_index=task.task_index,
            slate=source_slate,
            lineups=all_samples,
        )
        structure_identity = _publish_json(
            storage,
            uri=f"{prefix}slates/task-{task.task_index:04d}/structure.json",
            value=structure,
        )
        structure_identities.append(structure_identity)
        sampled_lineup_count += len(structure["lineups"])

        task_manifest = _mapping(
            _sequence(evidence.batch_manifest["tasks"], label="manifest tasks")[
                task.task_index
            ],
            label="manifest task",
        )
        world_identities = _mapping(
            task_manifest["world_artifact_receipts"], label="world receipts"
        )
        matrix_identities = sorted(
            (_identity(row, label="world matrix") for row in world_identities.values()),
            key=_identity_key,
        )
        baseline_experiment: dict[str, object] | None = None
        for ordinal, variant in enumerate(task.variants):
            fill_identity, fill_parameters = fill_by_id[variant.parameter_set_id]
            artifact_rows = [
                *(
                    _artifact_pointer(
                        f"world-{role.removeprefix('world_artifact_')}",
                        _identity(raw, label="world artifact"),
                        matrix=True,
                    )
                    for role, raw in sorted(world_identities.items())
                ),
                _artifact_pointer(
                    "accepted-task", task.task_acceptance_identity, matrix=False,
                ),
                _artifact_pointer(
                    "effective-policy", variant.effective_policy_identity,
                    matrix=False,
                ),
                _artifact_pointer(
                    "independent-verification",
                    task.independent_verification_identity,
                    matrix=False,
                ),
                _artifact_pointer(
                    "science-terminal", task.science_terminal_identity,
                    matrix=False,
                ),
                _artifact_pointer(
                    "task-result", task.task_result_identity, matrix=False,
                ),
                _artifact_pointer(
                    "variant-result", variant.result_identity, matrix=False,
                ),
            ]
            artifact_rows.sort(key=lambda row: str(row["role"]))
            snapshot_id = (
                f"snapshot-task-{task.task_index:04d}-{variant.parameter_set_id}"
            )
            lineup_ids = sorted(
                _lineup_id([
                    _graph_identifier(player, label="selected roster player ID")
                    for player in row
                ])
                for row in samples_by_arm[variant.parameter_set_id]
            )
            snapshot = _with_hash({
                "schema_version": registry.SNAPSHOT_SCHEMA,
                "publication_mode": "create_once",
                "snapshot_id": snapshot_id,
                "task_index": task.task_index,
                "slate_id": source_slate["slate_id"],
                "season": source_slate["season"],
                "week": source_slate["week"],
                "source_snapshot_manifest": evidence.source_freeze_identity,
                "producing_fill_preset": fill_identity,
                "slate_structure": structure_identity,
                "artifact_pointers": artifact_rows,
                "lineup_ids": lineup_ids,
                "created_at_utc": str(evidence.batch_manifest["created_at_utc"]),
            }, field="corpus_snapshot_sha256")
            snapshot_identity = _publish_json(
                storage,
                uri=(
                    f"{prefix}slates/task-{task.task_index:04d}/"
                    f"{variant.parameter_set_id}/snapshot.json"
                ),
                value=snapshot,
            )
            snapshot_identities.append(snapshot_identity)

            experiment_id = (
                f"experiment-task-{task.task_index:04d}-"
                f"{variant.parameter_set_id}"
            )
            base = (
                f"{prefix}experiments/task-{task.task_index:04d}/"
                f"{variant.parameter_set_id}/"
            )
            effective = _with_hash({
                "schema_version": (
                    registry.RETROSPECTIVE_EFFECTIVE_PARAMETERS_SCHEMA
                ),
                "publication_mode": "create_once",
                "derivation_mode": "retrospective-pointer-binding",
                "experiment_id": experiment_id,
                "fill_preset": fill_identity,
                "retrieval_preset": retrieval_identity,
                "fill_parameters": fill_parameters,
                "retrieval_parameters": retrieval_parameters,
                "source_effective_policy": (
                    variant.effective_policy_identity
                ),
                "uses_realized_outcomes": False,
                "historical_outcome_read_authority": False,
                "outcome_namespace_read": False,
                "outcome_columns_read": [],
            }, field="effective_parameters_sha256")
            effective_id = _publish_json(
                storage, uri=f"{base}effective-parameters.json", value=effective
            )
            gate = _with_hash({
                "schema_version": registry.RETROSPECTIVE_REGISTRATION_SCHEMA,
                "publication_mode": "create_once",
                "gate_id": f"gate-{experiment_id}",
                "experiment_id": experiment_id,
                "task_index": task.task_index,
                "slate_id": source_slate["slate_id"],
                "fill_preset": fill_identity,
                "retrieval_preset": retrieval_identity,
                "corpus_snapshot": snapshot_identity,
                "matrix_artifacts": matrix_identities,
                "effective_parameters": effective_id,
                "exact_release": source_execution_release,
                "derivation_manifest": intent_identity,
                "batch_manifest": evidence.batch_manifest_identity,
                "task_acceptance": task.task_acceptance_identity,
                "task_result": task.task_result_identity,
                "science_terminal": task.science_terminal_identity,
                "independent_verification": (
                    task.independent_verification_identity
                ),
                "variant_result": variant.result_identity,
                "effective_policy": variant.effective_policy_identity,
                "task_sha256": task.task_result["task_sha256"],
                "parameter_set_sha256": variant.parameter_set_sha256,
                "registered_before_execution": False,
                "batch_law_frozen_before_execution": True,
                "retrospective_binding": True,
                "uses_realized_outcomes": False,
                "historical_outcome_read_authority": False,
                "outcome_namespace_read": False,
                "outcome_columns_read": [],
                "created_at_utc": timestamp,
            }, field="retrospective_registration_sha256")
            gate_id = _publish_json(
                storage, uri=f"{base}pre-execution-gate.json", value=gate
            )
            evidence_time = timestamp
            accepted_execution = _evidence_binding(
                evidence_id=f"accepted-execution-{experiment_id}",
                experiment_id=experiment_id,
                role="accepted-execution",
                task_index=task.task_index,
                slate_id=str(source_slate["slate_id"]),
                exact_release=source_execution_release,
                dependencies=[
                    gate_id, effective_id, task.task_acceptance_identity,
                    task.science_terminal_identity,
                ],
                metrics_sha256=None,
                created_at_utc=evidence_time,
            )
            accepted_execution_id = _publish_json(
                storage,
                uri=f"{base}accepted-execution.json",
                value=accepted_execution,
            )
            accepted_result = _evidence_binding(
                evidence_id=f"accepted-result-{experiment_id}",
                experiment_id=experiment_id,
                role="accepted-result",
                task_index=task.task_index,
                slate_id=str(source_slate["slate_id"]),
                exact_release=source_execution_release,
                dependencies=[
                    accepted_execution_id, effective_id,
                    task.task_result_identity, variant.result_identity,
                ],
                metrics_sha256=None,
                created_at_utc=evidence_time,
            )
            accepted_result_id = _publish_json(
                storage, uri=f"{base}accepted-result.json", value=accepted_result
            )
            independent = _evidence_binding(
                evidence_id=f"independent-verification-{experiment_id}",
                experiment_id=experiment_id,
                role="independent-verification",
                task_index=task.task_index,
                slate_id=str(source_slate["slate_id"]),
                exact_release=source_execution_release,
                dependencies=[
                    accepted_result_id, effective_id,
                    task.independent_verification_identity,
                ],
                metrics_sha256=None,
                created_at_utc=evidence_time,
            )
            independent_id = _publish_json(
                storage,
                uri=f"{base}independent-verification.json",
                value=independent,
            )
            selection = _evidence_binding(
                evidence_id=f"selection-evidence-{experiment_id}",
                experiment_id=experiment_id,
                role="selection-evidence",
                task_index=task.task_index,
                slate_id=str(source_slate["slate_id"]),
                exact_release=source_execution_release,
                dependencies=[
                    accepted_result_id, independent_id, effective_id,
                    variant.result_identity,
                ],
                metrics_sha256=None,
                created_at_utc=evidence_time,
            )
            selection_id = _publish_json(
                storage, uri=f"{base}selection-evidence.json", value=selection
            )
            metric_rows = _metrics(
                verification=task.independent_verification,
                ordinal=ordinal,
                baseline=baseline_experiment,
            )
            metric_computation = _evidence_binding(
                evidence_id=f"metric-computation-{experiment_id}",
                experiment_id=experiment_id,
                role="metric-computation",
                task_index=task.task_index,
                slate_id=str(source_slate["slate_id"]),
                exact_release=source_execution_release,
                dependencies=[
                    accepted_result_id, independent_id, effective_id,
                    selection_id, task.independent_verification_identity,
                ],
                metrics_sha256=canonical_sha256(metric_rows),
                created_at_utc=evidence_time,
            )
            metric_computation_id = _publish_json(
                storage,
                uri=f"{base}metric-computation.json",
                value=metric_computation,
            )
            authority = {
                "pre_execution_gate": gate_id,
                "accepted_execution": accepted_execution_id,
                "accepted_result": accepted_result_id,
                "independent_verification": independent_id,
                "effective_parameters": effective_id,
                "selection_evidence": selection_id,
                "metric_computation": metric_computation_id,
            }
            metric_set = _with_hash({
                "schema_version": registry.METRIC_SET_SCHEMA,
                "publication_mode": "create_once",
                "experiment_id": experiment_id,
                "metrics": metric_rows,
                "paired_design": {
                    "required": baseline_experiment is not None,
                    "comparison_axis": (
                        "none" if baseline_experiment is None else "fill"
                    ),
                    "same_snapshot": False,
                    "same_worlds": True,
                    "paired_key": "r0-r4-world-id",
                },
                "heldout_design": {
                    "heldout_split_registered": False,
                    "selection_informed_by_heldout": False,
                    "selection_informed_by_evaluation_worlds": True,
                },
                **authority,
                "uses_realized_outcomes": False,
                "historical_outcome_read_authority": False,
                "outcome_namespace_read": False,
                "outcome_columns_read": [],
            }, field="metric_set_sha256")
            metric_set_id = _publish_json(
                storage, uri=f"{base}metric-set.json", value=metric_set
            )
            metric_identities.append(metric_set_id)
            experiment = _with_hash({
                "schema_version": registry.EXPERIMENT_SCHEMA,
                "publication_mode": "create_once",
                "experiment_id": experiment_id,
                "task_index": task.task_index,
                "slate_id": source_slate["slate_id"],
                "fill_preset": fill_identity,
                "retrieval_preset": retrieval_identity,
                "corpus_snapshot": snapshot_identity,
                "exact_release": source_execution_release,
                "matrix_artifacts": matrix_identities,
                "metric_set": metric_set_id,
                **authority,
                "status": "complete-accepted",
                "uses_realized_outcomes": False,
                "historical_outcome_read_authority": False,
                "outcome_namespace_read": False,
                "outcome_columns_read": [],
                "automatic_promotion": False,
                "application_config_mutation": False,
                "production_policy_authority": False,
            }, field="experiment_run_sha256")
            experiment_identity = _publish_json(
                storage, uri=f"{base}experiment.json", value=experiment
            )
            experiment_identities.append(experiment_identity)
            if ordinal == 0:
                baseline_experiment = experiment_identity

    release_body = {
        "schema_version": registry.RELEASE_SCHEMA,
        "publication_mode": "create_once",
        "registry_id": retained_registry_id,
        "output_prefix": prefix,
        "fill_presets": sorted(fill_identities, key=_identity_key),
        "retrieval_presets": [retrieval_identity],
        "corpus_snapshots": sorted(snapshot_identities, key=_identity_key),
        "slate_structures": sorted(structure_identities, key=_identity_key),
        "experiment_runs": sorted(experiment_identities, key=_identity_key),
        "metric_sets": sorted(metric_identities, key=_identity_key),
        "promotion_decisions": [],
        "active_strategy_pointers": [],
        "winner_import_requested": False,
        "winner_import_authority": None,
        "winner_evidence": None,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
        "created_at_utc": timestamp,
    }
    release = _with_hash(release_body, field="registry_release_sha256")
    release_identity = ObjectIdentity(**_publish_json(
        storage, uri=f"{prefix}release.json", value=release
    ))
    try:
        prepared = registry.prepare_strategy_registry_plan(
            parent_plan=evidence.retrieval_plan,
            storage=storage,
            release_identity=release_identity.as_dict(),
        )
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusStrategyRegistryReleaseError(
            "published registry release does not replay exactly"
        ) from exc
    registry_nodes = [
        row for row in prepared.plan.nodes
        if row["workstream_namespace"] == registry.REGISTRY_NAMESPACE
    ]
    registry_node_ids = {str(row["id"]) for row in registry_nodes}
    registry_relationship_count = sum(
        str(row["from_id"]) in registry_node_ids
        or str(row["to_id"]) in registry_node_ids
        for row in prepared.plan.relationships
    )
    publication_body = {
        "schema_version": PUBLICATION_SCHEMA,
        "publication_mode": "create_once",
        "publication_intent": intent_identity,
        "registry_release": release_identity.as_dict(),
        "retrieval_terminal": evidence.retrieval_terminal_identity,
        "batch_acceptance": evidence.batch_acceptance_identity,
        "batch_completion": evidence.batch_completion_identity,
        "batch_manifest": evidence.batch_manifest_identity,
        "source_freeze": evidence.source_freeze_identity,
        "source_execution_release": source_execution_release,
        "producer_release": retained_producer_release,
        "registry_plan_sha256": prepared.plan.plan_sha256,
        "registry_node_count": len(registry_nodes),
        "registry_relationship_count": registry_relationship_count,
        "task_count": TASK_COUNT,
        "fill_preset_count": ARM_COUNT,
        "retrieval_preset_count": 1,
        "experiment_count": MATRIX_CELL_COUNT,
        "metric_set_count": MATRIX_CELL_COUNT,
        "lineup_sample_per_arm": LINEUP_SAMPLE_PER_ARM,
        "sampled_unique_lineup_count": sampled_lineup_count,
        "heldout_split_registered": False,
        "selection_informed_by_heldout": False,
        "selection_informed_by_evaluation_worlds": True,
        "metric_scope": "all-worlds-descriptive",
        "registration_mode": "retrospective-pointer-binding",
        "new_gate_claimed_pre_execution": False,
        "source_inputs_frozen_before_execution": True,
        "promotion_decision_count": 0,
        "active_strategy_pointer_count": 0,
        "winner_imported": False,
        "realized_namespace_reserved": True,
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
        "created_at_utc": timestamp,
    }
    publication = _with_hash(
        publication_body, field="publication_receipt_sha256"
    )
    publication_identity = ObjectIdentity(**_publish_json(
        storage,
        uri=f"{prefix}publication-receipt.json",
        value=publication,
    ))
    return PublishedStrategyRegistryRelease(
        release_identity=release_identity,
        publication_identity=publication_identity,
        release=release,
        publication=publication,
    )


def publish_strategy_registry_release(
    *,
    storage: ExactObjectStore,
    retrieval_terminal_identity: object,
    batch_acceptance_identity: object,
    registry_id: str,
    output_prefix: str,
    created_at_utc: str,
    producer_release: Mapping[str, object],
) -> PublishedStrategyRegistryRelease:
    """Reopen exact accepted identities, then publish the derived release.

    Accepting only the two governed root identities keeps arbitrary callers
    from constructing an ``AcceptedBatchEvidence`` dataclass and bypassing
    the 54x7 acceptance, outcome-firewall, and independent-verification
    replay performed by :func:`reopen_accepted_batch_evidence`.
    """
    evidence = reopen_accepted_batch_evidence(
        storage=storage,
        retrieval_terminal_identity=retrieval_terminal_identity,
        batch_acceptance_identity=batch_acceptance_identity,
    )
    return _publish_validated_strategy_registry_release(
        storage=storage,
        evidence=evidence,
        registry_id=registry_id,
        output_prefix=output_prefix,
        created_at_utc=created_at_utc,
        producer_release=producer_release,
    )


__all__ = [
    "ARM_COUNT",
    "AcceptedBatchEvidence",
    "AcceptedTaskEvidence",
    "AcceptedVariantEvidence",
    "CorpusStrategyRegistryReleaseError",
    "LINEUP_SAMPLE_PER_ARM",
    "MATRIX_CELL_COUNT",
    "PUBLICATION_INTENT_SCHEMA",
    "PUBLICATION_SCHEMA",
    "PublishedStrategyRegistryRelease",
    "TASK_COUNT",
    "publish_strategy_registry_release",
    "reopen_accepted_batch_evidence",
]
