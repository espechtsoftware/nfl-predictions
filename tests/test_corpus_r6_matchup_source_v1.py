"""Adversarial tests for the pure corrected R6 matchup-source seam."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_r6_matchup_source_v1 as source


def _raw(value: object) -> bytes:
    return source.canonical_json_bytes(value)


def _hashed(body: dict[str, object], field: str) -> dict[str, object]:
    result = deepcopy(body)
    result[field] = source.canonical_sha256(result)
    return result


def _identity(uri: str, raw: bytes, generation: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _ExactStore:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.next_generation = 1000

    def seed(self, uri: str, raw: bytes, *, generation: str = "900") -> dict[str, object]:
        identity = _identity(uri, raw, generation)
        self.objects[uri] = {"identity": identity, "raw": raw}
        return deepcopy(identity)

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.objects:
            raise source.CorpusR6MatchupSourceV1Error(
                "create-once collision"
            )
        identity = _identity(uri, raw, str(self.next_generation))
        self.next_generation += 1
        self.objects[uri] = {"identity": identity, "raw": raw}
        return deepcopy(identity)

    def read_exact(self, identity: dict[str, object]) -> bytes:
        uri = str(identity["uri"])
        retained = self.objects.get(uri)
        if retained is None or retained["identity"] != identity:
            raise source.CorpusR6MatchupSourceV1Error(
                "exact identity/generation differs"
            )
        return retained["raw"]

    def body(self, identity: dict[str, object]) -> dict[str, object]:
        return json.loads(self.objects[str(identity["uri"])]["raw"])

    def replace(
        self,
        identity: dict[str, object],
        body_or_raw: dict[str, object] | bytes,
        *,
        generation: str | None = None,
    ) -> dict[str, object]:
        raw = body_or_raw if isinstance(body_or_raw, bytes) else _raw(body_or_raw)
        uri = str(identity["uri"])
        replacement = _identity(
            uri,
            raw,
            generation or str(int(str(identity["generation"])) + 100),
        )
        self.objects[uri] = {"identity": replacement, "raw": raw}
        return deepcopy(replacement)


def _family_definition(
    family_id: str, roles: list[str]
) -> dict[str, object]:
    schemas = {
        role: source.build_source_role_schema_v1(
            role=role,
            row_fields=sorted({
                "role",
                "source_season",
                "source_week",
                "source_event_time_utc",
                "observed_at_utc",
                "target_season",
                "target_week",
                "target_slate_id",
                "target_task_id",
                "gsis_id",
                "family",
                "team",
                "opponent",
                "game_id",
                "component",
                "component_value",
                "component_supported",
                "missing_reason_code",
            }),
            source_period_kind=(
                "prior-season-full"
                if "fantasy-points" in role and "shell" in role
                else "prior-game-window"
            ),
            population_role="component",
        )
        for role in roles
    }
    return _hashed({
        "schema_version": source.FAMILY_DEFINITION_SCHEMA,
        "family_id": family_id,
        "version": 2,
        "provisional": True,
        "source_roles": roles,
        "fields": [
            {
                "name": "component_a",
                "field_type": "percentile",
                "nullable": True,
                "description": "first score-free component percentile",
            },
            {
                "name": "component_b",
                "field_type": "percentile",
                "nullable": True,
                "description": "second score-free component percentile",
            },
        ],
        "missing_reason_codes": ["source-absent"],
        "description": "versioned corrected prior-period family fixture",
        "source_role_schemas": schemas,
        "component_source_roles": {
            "component_a": sorted(roles[::2]),
            "component_b": sorted(roles[1::2] or roles),
        },
    }, "family_definition_sha256")


def _catalog(*, task_id: str = "slate-2023-w5") -> dict[str, object]:
    players = [
        {
            "id": "00-001",
            "name": "Quarterback",
            "pos": "QB",
            "team": "AAA",
            "opp": "BBB",
            "game_id": "AAA|BBB",
            "salary": 6000,
            "proj": 20.0,
        },
        {
            "id": "00-002",
            "name": "Running Back",
            "pos": "RB",
            "team": "AAA",
            "opp": "BBB",
            "game_id": "AAA|BBB",
            "salary": 6500,
            "proj": 17.0,
        },
        {
            "id": "00-003",
            "name": "Wide Receiver",
            "pos": "WR",
            "team": "AAA",
            "opp": "BBB",
            "game_id": "AAA|BBB",
            "salary": 7000,
            "proj": 18.0,
        },
        {
            "id": "00-004",
            "name": "Tight End",
            "pos": "TE",
            "team": "BBB",
            "opp": "AAA",
            "game_id": "AAA|BBB",
            "salary": 4000,
            "proj": 10.0,
        },
        {
            "id": "DST_AAA",
            "name": "AAA DST",
            "pos": "DST",
            "team": "AAA",
            "opp": "BBB",
            "game_id": "AAA|BBB",
            "salary": 3000,
            "proj": 7.0,
        },
    ]
    return _hashed({
        "schema_version": source.PLAYER_CATALOG_SCHEMA,
        "task_id": task_id,
        "source_authority": {
            "uri": "gs://fixture/catalog-authority.json",
            "generation": "800",
            "sha256": "a" * 64,
            "bytes": 1,
        },
        "players": players,
    }, "player_catalog_sha256")


def _fixture() -> dict[str, Any]:
    slate = {
        "season": 2023,
        "week": 5,
        "slate_id": "2023-w05-main",
        "task_id": "slate-2023-w5",
    }
    families = {
        "qb": _family_definition(
            "qb-matchup", ["qb-prior-context"]
        ),
        "rb": _family_definition(
            "rb-matchup", ["rb-prior-context"]
        ),
        "receiver": _family_definition(
            "receiver-matchup",
            [
                "receiver-role-components",
                "defense-role-concessions",
                "fantasy-points-receiver-shell",
                "fantasy-points-defense-shell",
            ],
        ),
    }
    component_roles = [
        role
        for family in source.ELIGIBLE_FAMILIES
        for role in families[family]["source_roles"]
    ]
    schemas_by_role = {
        role: families[family]["source_role_schemas"][role]
        for family in source.ELIGIBLE_FAMILIES
        for role in families[family]["source_roles"]
    }
    infrastructure_schemas = source.infrastructure_source_role_schemas_v1()
    schemas_by_role.update(infrastructure_schemas)
    target_players = {
        "00-001": {
            "family": "qb", "team": "AAA", "opponent": "BBB",
            "game_id": "AAA|BBB",
        },
        "00-002": {
            "family": "rb", "team": "AAA", "opponent": "BBB",
            "game_id": "AAA|BBB",
        },
        "00-003": {
            "family": "receiver", "team": "AAA", "opponent": "BBB",
            "game_id": "AAA|BBB",
        },
        "00-004": {
            "family": "receiver", "team": "BBB", "opponent": "AAA",
            "game_id": "AAA|BBB",
        },
    }
    extracts: list[dict[str, object]] = []
    for role in component_roles:
        is_shell = role in {
            "fantasy-points-receiver-shell",
            "fantasy-points-defense-shell",
        }
        family = next(
            family
            for family in source.ELIGIBLE_FAMILIES
            if role in families[family]["source_roles"]
        )
        components = sorted(
            component
            for component, roles in families[family][
                "component_source_roles"
            ].items()
            if role in roles
        )
        rows = []
        for player_id, context in target_players.items():
            if context["family"] != family:
                continue
            for component in components:
                supported = player_id != "00-004"
                rows.append({
                    "role": role,
                    "source_season": 2022 if is_shell else 2023,
                    "source_week": None if is_shell else 4,
                    "source_event_time_utc": (
                        "2023-02-12T23:00:00Z"
                        if is_shell
                        else "2023-10-02T03:30:00Z"
                    ),
                    "observed_at_utc": "2026-08-24T10:00:00Z",
                    "target_season": 2023,
                    "target_week": 5,
                    "target_slate_id": "2023-w05-main",
                    "target_task_id": "slate-2023-w5",
                    "gsis_id": player_id,
                    "family": family,
                    "team": context["team"],
                    "opponent": context["opponent"],
                    "game_id": context["game_id"],
                    "component": component,
                    "component_value": (
                        0.6 if component == "component_a" else 0.7
                    ) if supported else None,
                    "component_supported": supported,
                    "missing_reason_code": (
                        None if supported else "source-absent"
                    ),
                })
        rows.sort(key=lambda row: (row["gsis_id"], row["component"]))
        rows_sha = source.canonical_sha256(rows)
        extracts.append({
            "role": role,
            "relation_or_object": (
                "bq://fixture_project.fixture_dataset."
                f"{role.replace('-', '_')}"
            ),
            "source_identity_or_extract_sha256": rows_sha,
            "source_role_schema_sha256": schemas_by_role[role][
                "source_role_schema_sha256"
            ],
            "rows": rows,
            "rows_sha256": rows_sha,
            "row_count": len(rows),
            "source_period_kind": (
                "prior-season-full" if is_shell else "prior-game-window"
            ),
            "source_season_week_min": {
                "season": 2022 if is_shell else 2023,
                "week": None if is_shell else 4,
            },
            "source_season_week_max": {
                "season": 2022 if is_shell else 2023,
                "week": None if is_shell else 4,
            },
            "maximum_source_event_time_utc": (
                "2023-02-12T23:00:00Z"
                if is_shell
                else "2023-10-02T03:30:00Z"
            ),
            "observed_at_utc": "2026-08-24T10:00:00Z",
            "observed_at_basis": "historical-source-period-only",
            "evidence_class": source.EVIDENCE_RETROSPECTIVE,
            "missingness_reason": None,
        })
    schedule_rows = [
        {
            "role": source.SCHEDULE_SOURCE_ROLE,
            "source_season": 2023,
            "source_week": 5,
            "source_event_time_utc": "2023-09-01T12:00:00Z",
            "observed_at_utc": "2026-08-24T10:00:00Z",
            "season": 2023,
            "week": 5,
            "slate_id": "2023-w05-main",
            "task_id": "slate-2023-w5",
            "game_id": "AAA|BBB",
            "team": team,
            "opponent": opponent,
            "kickoff_time_utc": "2023-10-08T17:00:00Z",
            "lock_time_utc": "2023-10-08T17:00:00Z",
        }
        for team, opponent in (("AAA", "BBB"), ("BBB", "AAA"))
    ]
    depth_rows = [{
        "role": source.QB_DEPTH_SOURCE_ROLE,
        "source_season": 2023,
        "source_week": 5,
        "source_event_time_utc": "2023-10-08T16:00:00Z",
        "observed_at_utc": "2026-08-24T10:00:00Z",
        "season": 2023,
        "week": 5,
        "slate_id": "2023-w05-main",
        "task_id": "slate-2023-w5",
        "gsis_id": "00-001",
        "team": "AAA",
        "game_id": "AAA|BBB",
        "depth1": True,
        "missingness_reason": None,
    }]
    for role, rows, event_time in (
        (
            source.SCHEDULE_SOURCE_ROLE,
            schedule_rows,
            "2023-09-01T12:00:00Z",
        ),
        (
            source.QB_DEPTH_SOURCE_ROLE,
            depth_rows,
            "2023-10-08T16:00:00Z",
        ),
    ):
        rows_sha = source.canonical_sha256(rows)
        extracts.append({
            "role": role,
            "relation_or_object": (
                "bq://fixture_project.fixture_dataset."
                f"{role.replace('-', '_')}"
            ),
            "source_identity_or_extract_sha256": rows_sha,
            "source_role_schema_sha256": schemas_by_role[role][
                "source_role_schema_sha256"
            ],
            "rows": rows,
            "rows_sha256": rows_sha,
            "row_count": len(rows),
            "source_period_kind": "prelock-snapshot",
            "source_season_week_min": {"season": 2023, "week": 5},
            "source_season_week_max": {"season": 2023, "week": 5},
            "maximum_source_event_time_utc": event_time,
            "observed_at_utc": "2026-08-24T10:00:00Z",
            "observed_at_basis": "historical-source-period-only",
            "evidence_class": source.EVIDENCE_RETROSPECTIVE,
            "missingness_reason": None,
        })
    extract_by_role = {str(item["role"]): item for item in extracts}

    def annotation(
        player_id: str,
        family: str,
        position: str,
        *,
        depth: bool | None = None,
    ) -> dict[str, object]:
        values: dict[str, object] = {}
        support: dict[str, bool] = {}
        bounds: dict[str, object] = {}
        missing_reasons: dict[str, list[str]] = {}
        for component, roles in sorted(
            families[family]["component_source_roles"].items()
        ):
            component_extracts = [extract_by_role[role] for role in roles]
            cells = [
                row
                for extract in component_extracts
                for row in extract["rows"]
                if row["gsis_id"] == player_id
                and row["component"] == component
            ]
            supported_values = [
                float(row["component_value"])
                for row in cells
                if row["component_supported"] is True
            ]
            supported = bool(supported_values)
            support[component] = supported
            values[component] = (
                round(sum(supported_values) / len(supported_values), 12)
                if supported
                else None
            )
            missing_reasons[component] = (
                []
                if supported
                else sorted({
                    str(row["missing_reason_code"])
                    for row in cells
                    if row["missing_reason_code"] is not None
                })
            )
            periods_min = [
                extract["source_season_week_min"]
                for extract in component_extracts
                if extract["source_season_week_min"] is not None
            ]
            periods_max = [
                extract["source_season_week_max"]
                for extract in component_extracts
                if extract["source_season_week_max"] is not None
            ]
            bounds[component] = {
                "source_roles": list(roles),
                "source_season_week_min": min(
                    periods_min,
                    key=lambda period: (
                        period["season"],
                        -1 if period["week"] is None else period["week"],
                    ),
                ),
                "source_season_week_max": max(
                    periods_max,
                    key=lambda period: (
                        period["season"],
                        -1 if period["week"] is None else period["week"],
                    ),
                ),
                "maximum_source_event_time_utc": max(
                    str(extract["maximum_source_event_time_utc"])
                    for extract in component_extracts
                ),
                "evidence_class": min(
                    (str(extract["evidence_class"]) for extract in component_extracts),
                    key=source.EVIDENCE_CLASSES.index,
                ),
            }
        supported_component_values = [
            float(value)
            for component, value in values.items()
            if support[component]
        ]
        return {
            "gsis_id": player_id,
            "family": family,
            "position": position,
            "qb_depth1": depth,
            "qb_depth_evidence_class": (
                source.EVIDENCE_RETROSPECTIVE
                if family == "qb"
                else "not-applicable"
            ),
            "component_values": values,
            "component_support": support,
            "component_source_bounds": bounds,
            "component_missing_reason_codes": missing_reasons,
            "matchup_component_count": len(supported_component_values),
            "matchup_edge_score": (
                round(
                    sum(supported_component_values)
                    / len(supported_component_values),
                    12,
                )
                if len(supported_component_values) >= 2
                else None
            ),
        }

    annotations = [
        annotation(
            "00-001", "qb", "QB", depth=True
        ),
        annotation(
            "00-002", "rb", "RB"
        ),
        annotation(
            "00-003",
            "receiver",
            "WR",
        ),
        # 00-004 is deliberately absent: the export must materialize it.
    ]
    relations = [{
        "role": str(extract["role"]),
        "table_or_object": str(extract["relation_or_object"]),
        "schema_sha256": str(extract["source_role_schema_sha256"]),
        "etag_or_generation": f"etag-{ordinal}",
        "modified_or_created_at_utc": "2026-08-24T10:00:00Z",
        "exact_extract_sha256": str(extract["rows_sha256"]),
        "row_count": int(extract["row_count"]),
    } for ordinal, extract in enumerate(extracts)]
    relations.sort(key=lambda row: str(row["role"]))
    metadata = {
        "created_at_utc": "2026-08-25T12:05:00Z",
        "query_parameters": {
            "season": 2023,
            "week": 5,
            "slate_id": "2023-w05-main",
            "task_id": "slate-2023-w5",
            "lock_time_utc": "2023-10-08T17:00:00Z",
            "source_roles": sorted(str(extract["role"]) for extract in extracts),
        },
        "query_snapshot_at_utc": "2026-08-25T11:59:00Z",
        "query_job": {
            "project": "fixture-project",
            "location": "US",
            "job_id": "r6_matchup_source_fixture",
            "created": "2026-08-25T12:00:00Z",
            "started": "2026-08-25T12:01:00Z",
            "ended": "2026-08-25T12:02:00Z",
            "cache_hit": False,
            "error_result": None,
            "total_bytes_processed": 1234,
        },
        "source_relations": relations,
        "player_catalog_evidence": {
            "maximum_source_event_time_utc": "2023-10-08T16:00:00Z",
            "observed_at_utc": "2026-08-24T09:00:00Z",
            "observed_at_basis": "historical-source-period-only",
            "evidence_class": source.EVIDENCE_RETROSPECTIVE,
        },
    }
    return {
        "catalog": _catalog(),
        "slate": slate,
        "lock_time_utc": "2023-10-08T17:00:00Z",
        "families": families,
        "extracts": extracts,
        "annotations": annotations,
        "metadata": metadata,
        "rendered_sql_raw": source.build_rendered_sql_v1(relations),
        "code_identity": {
            "schema_version": "r6-matchup-source-code/v1",
            "source_commit": "b" * 40,
            "uses_realized_outcomes": False,
        },
    }


def _extract(fixture: Mapping[str, Any], role: str) -> dict[str, Any]:
    return next(
        extract
        for extract in fixture["extracts"]
        if extract["role"] == role
    )


def _relation(fixture: Mapping[str, Any], role: str) -> dict[str, Any]:
    return next(
        relation
        for relation in fixture["metadata"]["source_relations"]
        if relation["role"] == role
    )


def _rehash_extract(fixture: Mapping[str, Any], role: str) -> None:
    extract = _extract(fixture, role)
    digest = source.canonical_sha256(extract["rows"])
    extract["rows_sha256"] = digest
    extract["source_identity_or_extract_sha256"] = digest
    extract["row_count"] = len(extract["rows"])
    relation = _relation(fixture, role)
    relation["exact_extract_sha256"] = digest
    relation["row_count"] = len(extract["rows"])


def _rehash_family(fixture: Mapping[str, Any], family: str) -> None:
    definition = fixture["families"][family]
    fixture["families"][family] = _hashed(
        {
            key: value
            for key, value in definition.items()
            if key != "family_definition_sha256"
        },
        "family_definition_sha256",
    )


def _rehash_role_schema(
    fixture: Mapping[str, Any], family: str, role: str
) -> None:
    schema = fixture["families"][family]["source_role_schemas"][role]
    rebuilt = _hashed(
        {
            key: value
            for key, value in schema.items()
            if key != "source_role_schema_sha256"
        },
        "source_role_schema_sha256",
    )
    fixture["families"][family]["source_role_schemas"][role] = rebuilt
    _extract(fixture, role)["source_role_schema_sha256"] = rebuilt[
        "source_role_schema_sha256"
    ]
    _relation(fixture, role)["schema_sha256"] = rebuilt[
        "source_role_schema_sha256"
    ]
    _rehash_family(fixture, family)


def _make_extract_unavailable(
    fixture: Mapping[str, Any], role: str
) -> None:
    extract = _extract(fixture, role)
    extract.update({
        "rows": [],
        "source_period_kind": "unavailable",
        "source_season_week_min": None,
        "source_season_week_max": None,
        "maximum_source_event_time_utc": None,
        "observed_at_utc": None,
        "observed_at_basis": "unknown",
        "evidence_class": source.EVIDENCE_RETROSPECTIVE,
        "missingness_reason": "source-absent",
    })
    _rehash_extract(fixture, role)


def _rewrite_annotation_bounds(fixture: Mapping[str, Any]) -> None:
    for annotation in fixture["annotations"]:
        family = annotation["family"]
        component_roles = fixture["families"][family][
            "component_source_roles"
        ]
        for component, roles in component_roles.items():
            extracts = [_extract(fixture, role) for role in roles]
            periods_min = [
                extract["source_season_week_min"]
                for extract in extracts
                if extract["source_season_week_min"] is not None
            ]
            periods_max = [
                extract["source_season_week_max"]
                for extract in extracts
                if extract["source_season_week_max"] is not None
            ]
            maximum_events = [
                extract["maximum_source_event_time_utc"]
                for extract in extracts
                if extract["maximum_source_event_time_utc"] is not None
            ]
            annotation["component_source_bounds"][component] = {
                "source_roles": list(roles),
                "source_season_week_min": min(
                    periods_min,
                    key=lambda period: (
                        period["season"],
                        -1 if period["week"] is None else period["week"],
                    ),
                    default=None,
                ),
                "source_season_week_max": max(
                    periods_max,
                    key=lambda period: (
                        period["season"],
                        -1 if period["week"] is None else period["week"],
                    ),
                    default=None,
                ),
                "maximum_source_event_time_utc": max(
                    maximum_events, default=None
                ),
                "evidence_class": min(
                    (extract["evidence_class"] for extract in extracts),
                    key=source.EVIDENCE_CLASSES.index,
                ),
            }


def _retarget_to_2025_with_unknown_qb_depth(
    fixture: dict[str, Any],
) -> None:
    fixture["catalog"] = _catalog(task_id="slate-2025-w5")
    fixture["slate"] = {
        "season": 2025,
        "week": 5,
        "slate_id": "2025-w05-main",
        "task_id": "slate-2025-w5",
    }
    fixture["lock_time_utc"] = "2025-10-05T17:00:00Z"
    for extract in fixture["extracts"]:
        role = str(extract["role"])
        for row in extract["rows"]:
            if role not in source.INFRASTRUCTURE_SOURCE_ROLES:
                row.update({
                    "target_season": 2025,
                    "target_week": 5,
                    "target_slate_id": "2025-w05-main",
                    "target_task_id": "slate-2025-w5",
                })
            if extract["source_period_kind"] == "prior-season-full":
                row["source_season"] = 2024
                row["source_week"] = None
                row["source_event_time_utc"] = "2025-02-09T23:00:00Z"
            elif role not in source.INFRASTRUCTURE_SOURCE_ROLES:
                row["source_season"] = 2025
                row["source_week"] = 4
                row["source_event_time_utc"] = "2025-09-29T03:30:00Z"
            elif role == source.SCHEDULE_SOURCE_ROLE:
                row.update({
                    "source_season": 2025,
                    "source_week": 5,
                    "source_event_time_utc": "2025-09-01T12:00:00Z",
                    "season": 2025,
                    "week": 5,
                    "slate_id": "2025-w05-main",
                    "task_id": "slate-2025-w5",
                    "kickoff_time_utc": "2025-10-05T17:00:00Z",
                    "lock_time_utc": "2025-10-05T17:00:00Z",
                })
            else:
                row.update({
                    "source_season": 2025,
                    "source_week": 5,
                    "source_event_time_utc": "2025-10-05T16:00:00Z",
                    "season": 2025,
                    "week": 5,
                    "slate_id": "2025-w05-main",
                    "task_id": "slate-2025-w5",
                    "depth1": None,
                    "missingness_reason": "historical-depth-unavailable",
                })
        periods = [
            {
                "season": row["source_season"],
                "week": row["source_week"],
            }
            for row in extract["rows"]
        ]
        extract["source_season_week_min"] = min(
            periods,
            key=lambda period: (
                period["season"],
                -1 if period["week"] is None else period["week"],
            ),
        )
        extract["source_season_week_max"] = max(
            periods,
            key=lambda period: (
                period["season"],
                -1 if period["week"] is None else period["week"],
            ),
        )
        extract["maximum_source_event_time_utc"] = max(
            row["source_event_time_utc"] for row in extract["rows"]
        )
        _rehash_extract(fixture, role)
    fixture["metadata"]["query_parameters"] = {
        "season": 2025,
        "week": 5,
        "slate_id": "2025-w05-main",
        "task_id": "slate-2025-w5",
        "lock_time_utc": "2025-10-05T17:00:00Z",
        "source_roles": sorted(
            str(extract["role"]) for extract in fixture["extracts"]
        ),
    }
    fixture["metadata"]["player_catalog_evidence"][
        "maximum_source_event_time_utc"
    ] = "2025-10-05T16:00:00Z"
    fixture["annotations"][0]["qb_depth1"] = None
    fixture["annotations"][0]["qb_depth_evidence_class"] = "unknown"
    _rewrite_annotation_bounds(fixture)


def _capture(
    fixture: dict[str, Any] | None = None,
    *,
    store: _ExactStore | None = None,
    prefix: str = "gs://fixture/r6-corrected",
) -> tuple[_ExactStore, dict[str, Any], dict[str, Mapping[str, object]]]:
    fixture = deepcopy(fixture or _fixture())
    store = store or _ExactStore()
    catalog_raw = _raw(fixture["catalog"])
    catalog_uri = "gs://fixture/player-catalog.json"
    if catalog_uri in store.objects:
        catalog_identity = deepcopy(store.objects[catalog_uri]["identity"])
    else:
        catalog_identity = store.seed(catalog_uri, catalog_raw)
    identities = source.capture_matchup_source_v1(
        slate=fixture["slate"],
        lock_time_utc=fixture["lock_time_utc"],
        player_catalog_identity=catalog_identity,
        player_catalog_raw=catalog_raw,
        rendered_sql_raw=fixture["rendered_sql_raw"],
        query_job_receipt=fixture["metadata"],
        component_extracts=fixture["extracts"],
        annotation_rows=fixture["annotations"],
        family_definition_identities=fixture["families"],
        code_identity=fixture["code_identity"],
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
        output_prefix=prefix,
    )
    fixture["catalog_identity"] = catalog_identity
    return store, fixture, identities


def _reopen(
    store: _ExactStore,
    fixture: dict[str, Any],
    identities: dict[str, Mapping[str, object]],
    *,
    required_evidence_class: str = source.EVIDENCE_RETROSPECTIVE,
) -> dict[str, object]:
    return source.reopen_matchup_source_snapshot(
        source_export_identity=identities["source_export_identity"],
        query_receipt_identity=identities["query_receipt_identity"],
        player_catalog_identity=fixture["catalog_identity"],
        read_exact=store.read_exact,
        expected_slate=fixture["slate"],
        required_evidence_class=required_evidence_class,
    )


def test_capture_and_exact_reopen_are_catalog_complete_and_null_preserving() -> None:
    store, fixture, identities = _capture()
    snapshot = _reopen(store, fixture, identities)

    assert snapshot["schema_version"] == source.REOPENED_SOURCE_SCHEMA
    assert snapshot["evidence_class"] == source.EVIDENCE_RETROSPECTIVE
    assert snapshot["authoritative_pit"] is False
    assert snapshot["uses_realized_outcomes"] is False
    assert snapshot["qb_depth_unknown_policy"] == (
        source.QB_DEPTH_UNKNOWN_POLICY
    )
    assert snapshot["eligible_player_count"] == 4
    assert [row["gsis_id"] for row in snapshot["rows"]] == [
        "00-001", "00-002", "00-003", "00-004"
    ]
    missing = snapshot["rows"][-1]
    assert missing["annotation_row_present"] is False
    assert missing["component_values"] == {
        "component_a": None,
        "component_b": None,
    }
    assert missing["component_missing_reason_codes"] == {
        "component_a": ["source-absent"],
        "component_b": ["source-absent"],
    }
    assert missing["matchup_edge_score"] is None
    assert snapshot["target_spine_replay"]["population_authority"] == (
        "accepted-player-catalog"
    )
    assert snapshot["component_value_replay"][
        "target_week_deletion_invariant"
    ] is True
    deletion_proof = snapshot["component_value_replay"][
        "target_week_deletion_proof"
    ]
    assert deletion_proof["probe_source_systems"] == [
        "weekly_stats", "sis", "pfr"
    ]
    assert deletion_proof["probe_row_count"] == 12
    assert deletion_proof["full_input_sha256"] != deletion_proof[
        "deleted_input_sha256"
    ]
    assert deletion_proof["full_reduction_sha256"] == deletion_proof[
        "deleted_reduction_sha256"
    ]
    receipt = store.body(dict(identities["query_receipt_identity"]))
    assert receipt["rendered_sql_template_sha256"] == (
        source.RENDERED_SQL_TEMPLATE_SHA256
    )
    shell_extracts = {
        row["role"]: row
        for row in snapshot["source_extracts"]
        if row["source_period_kind"] == "prior-season-full"
    }
    assert set(shell_extracts) == {
        "fantasy-points-receiver-shell",
        "fantasy-points-defense-shell",
    }
    assert {
        row["source_season_week_min"]["season"]
        for row in shell_extracts.values()
    } == {2022}
    assert set(source.INFRASTRUCTURE_SOURCE_ROLES) <= {
        row["role"] for row in snapshot["source_extracts"]
    }


@pytest.mark.parametrize(
    "drift",
    ["unavailable", "relabelled", "target-task", "opponent"],
)
def test_schedule_spine_is_standalone_and_exactly_slate_bound(
    drift: str,
) -> None:
    fixture = _fixture()
    schedule = _extract(fixture, source.SCHEDULE_SOURCE_ROLE)
    if drift == "unavailable":
        _make_extract_unavailable(fixture, source.SCHEDULE_SOURCE_ROLE)
        expected = "standalone schedule spine is unavailable"
    elif drift == "relabelled":
        schedule["role"] = "schedule-spine-relabelled"
        for row in schedule["rows"]:
            row["role"] = "schedule-spine-relabelled"
        expected = "role differs from frozen dictionaries"
    elif drift == "target-task":
        schedule["rows"][0]["task_id"] = "different-task"
        _rehash_extract(fixture, source.SCHEDULE_SOURCE_ROLE)
        expected = "does not bind the target slate"
    else:
        schedule["rows"][0]["opponent"] = "CCC"
        _rehash_extract(fixture, source.SCHEDULE_SOURCE_ROLE)
        expected = "not reciprocal|differs for catalog player"
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match=expected,
    ):
        _capture(fixture)


def test_schedule_and_catalog_team_opponent_game_context_must_match() -> None:
    fixture = _fixture()
    fixture["catalog"]["players"][0]["opp"] = "CCC"
    fixture["catalog"] = _hashed(
        {
            key: value
            for key, value in fixture["catalog"].items()
            if key != "player_catalog_sha256"
        },
        "player_catalog_sha256",
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="schedule spine differs for catalog player",
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    ("drift", "expected"),
    [
        ("wrapper-period", "row-derived temporal fields drift"),
        ("target-period-row", "prior-game source reaches the target period"),
        ("row-role", "retained row role differs"),
        ("wrapper-observation", "row-derived temporal fields drift"),
    ],
)
def test_retained_rows_derive_period_role_and_observation_laws(
    drift: str, expected: str
) -> None:
    fixture = _fixture()
    role = "qb-prior-context"
    extract = _extract(fixture, role)
    if drift == "wrapper-period":
        extract["source_season_week_max"] = {"season": 2023, "week": 3}
    elif drift == "target-period-row":
        for row in extract["rows"]:
            row["source_week"] = 5
        extract["source_season_week_min"] = {"season": 2023, "week": 5}
        extract["source_season_week_max"] = {"season": 2023, "week": 5}
        _rehash_extract(fixture, role)
    elif drift == "row-role":
        extract["rows"][0]["role"] = "rb-prior-context"
        _rehash_extract(fixture, role)
    else:
        extract["observed_at_utc"] = "2026-08-24T10:00:01Z"
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match=expected,
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("uri", "gs://fixture/other-export.json"),
        ("generation", "999999"),
        ("sha256", "f" * 64),
        ("bytes", 1),
    ],
)
def test_exact_reopen_rejects_identity_and_generation_drift(
    field: str, replacement: object
) -> None:
    store, fixture, identities = _capture()
    drifted = deepcopy(identities)
    drifted["source_export_identity"] = dict(
        drifted["source_export_identity"]
    )
    drifted["source_export_identity"][field] = replacement
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="identity|content",
    ):
        _reopen(store, fixture, drifted)


def test_exact_reopen_rejects_content_and_self_hash_drift() -> None:
    store, fixture, identities = _capture()
    source_identity = dict(identities["source_export_identity"])
    store.objects[str(source_identity["uri"])]["raw"] += b"\n"
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error, match="content identity"
    ):
        _reopen(store, fixture, identities)

    store, fixture, identities = _capture()
    source_identity = dict(identities["source_export_identity"])
    export = store.body(source_identity)
    export["rows"][0]["matchup_edge_score"] = 0.66
    # Update the outer object identity but deliberately retain the stale
    # semantic self-hash. Exact content identity alone is not enough.
    identities["source_export_identity"] = store.replace(
        source_identity, export
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error, match="self-hash"
    ):
        _reopen(store, fixture, identities)


def test_query_receipt_cannot_misbind_export_or_catalog() -> None:
    store, fixture, identities = _capture()
    receipt_identity = dict(identities["query_receipt_identity"])
    receipt = store.body(receipt_identity)
    receipt["source_export_identity"]["generation"] = "777777"
    receipt = _hashed(
        {
            key: value
            for key, value in receipt.items()
            if key != "matchup_query_receipt_sha256"
        },
        "matchup_query_receipt_sha256",
    )
    identities["query_receipt_identity"] = store.replace(
        receipt_identity, receipt
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="different source export",
    ):
        _reopen(store, fixture, identities)


def test_source_export_self_consistent_missing_player_still_fails() -> None:
    store, fixture, identities = _capture()
    source_identity = dict(identities["source_export_identity"])
    export = store.body(source_identity)
    export["rows"] = export["rows"][:-1]
    export["rows_sha256"] = source.canonical_sha256(export["rows"])
    export = _hashed(
        {
            key: value
            for key, value in export.items()
            if key != "matchup_source_export_sha256"
        },
        "matchup_source_export_sha256",
    )
    identities["source_export_identity"] = store.replace(
        source_identity, export
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="completeness|canonical replay",
    ):
        _reopen(store, fixture, identities)


def test_source_export_self_consistent_duplicate_or_extra_player_fails() -> None:
    for mode in ("duplicate", "extra"):
        store, fixture, identities = _capture()
        source_identity = dict(identities["source_export_identity"])
        export = store.body(source_identity)
        if mode == "duplicate":
            export["rows"].append(deepcopy(export["rows"][0]))
        else:
            extra = deepcopy(export["rows"][0])
            extra["gsis_id"] = "00-999"
            export["rows"].append(extra)
        export["rows_sha256"] = source.canonical_sha256(export["rows"])
        export = _hashed(
            {
                key: value
                for key, value in export.items()
                if key != "matchup_source_export_sha256"
            },
            "matchup_source_export_sha256",
        )
        identities["source_export_identity"] = store.replace(
            source_identity, export
        )
        with pytest.raises(source.CorpusR6MatchupSourceV1Error):
            _reopen(store, fixture, identities)


def test_same_target_year_full_season_source_is_rejected() -> None:
    fixture = _fixture()
    for extract in fixture["extracts"]:
        if extract["source_period_kind"] == "prior-season-full":
            for row in extract["rows"]:
                row["source_season"] = 2023
            extract["source_season_week_min"]["season"] = 2023
            extract["source_season_week_max"]["season"] = 2023
            _rehash_extract(fixture, str(extract["role"]))
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="same-target-season",
    ):
        _capture(fixture)


def test_source_event_and_observation_time_drift_fail_closed() -> None:
    fixture = _fixture()
    role = str(fixture["extracts"][0]["role"])
    fixture["extracts"][0]["rows"][0][
        "source_event_time_utc"
    ] = fixture["lock_time_utc"]
    fixture["extracts"][0][
        "maximum_source_event_time_utc"
    ] = fixture["lock_time_utc"]
    _rehash_extract(fixture, role)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="retained row reaches or follows lock",
    ):
        _capture(fixture)

    fixture = _fixture()
    fixture["extracts"][0][
        "evidence_class"
    ] = source.EVIDENCE_CONTEMPORANEOUS
    fixture["extracts"][0]["observed_at_basis"] = "vendor-retrieved-at"
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="evidence class is not row-derived",
    ):
        _capture(fixture)


def test_receipt_time_drift_and_evidence_upgrade_fail_closed() -> None:
    store, fixture, identities = _capture()
    receipt_identity = dict(identities["query_receipt_identity"])
    receipt = store.body(receipt_identity)
    receipt["lock_time_utc"] = "2023-10-08T16:59:59Z"
    receipt = _hashed(
        {
            key: value
            for key, value in receipt.items()
            if key != "matchup_query_receipt_sha256"
        },
        "matchup_query_receipt_sha256",
    )
    identities["query_receipt_identity"] = store.replace(
        receipt_identity, receipt
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error, match="time binding"
    ):
        _reopen(store, fixture, identities)

    store, fixture, identities = _capture()
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="below the required minimum",
    ):
        _reopen(
            store,
            fixture,
            identities,
            required_evidence_class=source.EVIDENCE_CONTEMPORANEOUS,
        )


def test_source_role_and_relation_hash_drift_fail_closed() -> None:
    fixture = _fixture()
    fixture["extracts"][0]["role"] = fixture["extracts"][1]["role"]
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="role differs|frozen schema differs",
    ):
        _capture(fixture)

    fixture = _fixture()
    fixture["metadata"]["source_relations"][0]["etag_or_generation"] = None
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="generation must be a nonempty string",
    ):
        _capture(fixture)

    fixture = _fixture()
    fixture["metadata"]["source_relations"][0][
        "exact_extract_sha256"
    ] = "f" * 64
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="does not bind its extract",
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    ("drift", "expected"),
    [
        ("extract-schema-hash", "frozen schema differs"),
        ("retained-row-schema", "retained row schema differs"),
        ("relation-schema-hash", "does not bind its extract"),
        (
            "schema-self-hash",
            "source role schema definition differs|source schema identity differs",
        ),
        ("swapped-role-schema", "frozen schema differs"),
    ],
)
def test_source_role_schemas_are_frozen_and_exact(
    drift: str, expected: str
) -> None:
    fixture = _fixture()
    role = "fantasy-points-receiver-shell"
    extract = _extract(fixture, role)
    if drift == "extract-schema-hash":
        extract["source_role_schema_sha256"] = "f" * 64
    elif drift == "retained-row-schema":
        extract["rows"][0]["extra_context"] = "drift"
        _rehash_extract(fixture, role)
    elif drift == "relation-schema-hash":
        _relation(fixture, role)["schema_sha256"] = "f" * 64
    elif drift == "schema-self-hash":
        fixture["families"]["receiver"]["source_role_schemas"][role][
            "row_fields"
        ].append("extra_context")
        fixture["families"]["receiver"]["source_role_schemas"][role][
            "row_fields"
        ].sort()
        _rehash_family(fixture, "receiver")
    else:
        other = "fantasy-points-defense-shell"
        extract["source_role_schema_sha256"] = fixture["families"][
            "receiver"
        ]["source_role_schemas"][other]["source_role_schema_sha256"]
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match=expected,
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    ("parameter", "replacement"),
    [
        ("season", 2024),
        ("week", 4),
        ("slate_id", "other-slate"),
        ("task_id", "other-task"),
        ("lock_time_utc", "2023-10-08T16:59:59Z"),
        ("source_roles", ["qb-prior-context"]),
    ],
)
def test_capture_query_parameters_exactly_bind_the_slate_and_roles(
    parameter: str, replacement: object
) -> None:
    fixture = _fixture()
    fixture["metadata"]["query_parameters"][parameter] = replacement
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="query parameters do not exactly bind",
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    ("parameter", "replacement"),
    [
        ("season", 2024),
        ("week", 4),
        ("slate_id", "other-slate"),
        ("task_id", "other-task"),
        ("lock_time_utc", "2023-10-08T16:59:59Z"),
        ("source_roles", ["qb-prior-context"]),
    ],
)
def test_exact_reopen_rederives_query_parameters(
    parameter: str, replacement: object
) -> None:
    store, fixture, identities = _capture()
    receipt_identity = dict(identities["query_receipt_identity"])
    receipt = store.body(receipt_identity)
    receipt["query_parameters"][parameter] = replacement
    receipt = _hashed(
        {
            key: value
            for key, value in receipt.items()
            if key != "matchup_query_receipt_sha256"
        },
        "matchup_query_receipt_sha256",
    )
    identities["query_receipt_identity"] = store.replace(
        receipt_identity, receipt
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="query receipt parameters differ",
    ):
        _reopen(store, fixture, identities)


def test_component_bound_and_edge_range_drift_fail_closed() -> None:
    fixture = _fixture()
    fixture["annotations"][0]["component_source_bounds"]["component_a"][
        "source_roles"
    ] = ["rb-prior-context"]
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="component roles differ from family|family dictionary",
    ):
        _capture(fixture)

    fixture = _fixture()
    fixture["annotations"][0]["matchup_edge_score"] = 1.01
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error, match="edge differs"
    ):
        _capture(fixture)


def test_component_values_and_frozen_edge_are_replayed_from_source_rows() -> None:
    fixture = _fixture()
    role = "qb-prior-context"
    row = next(
        row
        for row in _extract(fixture, role)["rows"]
        if row["component"] == "component_a"
    )
    row["component_value"] = 0.61
    _rehash_extract(fixture, role)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="not source-replayed",
    ):
        _capture(fixture)

    fixture = _fixture()
    fixture["annotations"][0]["matchup_edge_score"] = 0.64
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="frozen component mean",
    ):
        _capture(fixture)


def test_available_component_extracts_exactly_cover_target_spine_cells() -> None:
    fixture = _fixture()
    role = "receiver-role-components"
    _extract(fixture, role)["rows"].pop()
    _rehash_extract(fixture, role)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="exactly cover the target spine",
    ):
        _capture(fixture)


def test_supported_annotation_cannot_survive_unavailable_declared_source() -> None:
    fixture = _fixture()
    _make_extract_unavailable(fixture, "qb-prior-context")
    _rewrite_annotation_bounds(fixture)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="not source-replayed",
    ):
        _capture(fixture)


def test_player_component_missing_reason_codes_are_exactly_replayed() -> None:
    fixture = _fixture()
    fixture["annotations"][0]["component_missing_reason_codes"][
        "component_a"
    ] = ["source-absent"]
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="not source-replayed",
    ):
        _capture(fixture)


def test_partial_component_support_preserves_missing_role_reason() -> None:
    fixture = _fixture()
    _make_extract_unavailable(
        fixture, "fantasy-points-receiver-shell"
    )
    _rewrite_annotation_bounds(fixture)
    for annotation in fixture["annotations"]:
        if annotation["family"] == "receiver":
            annotation["component_missing_reason_codes"]["component_a"] = [
                "source-absent"
            ]
    store, captured, identities = _capture(fixture)
    snapshot = _reopen(store, captured, identities)
    receiver = next(
        row for row in snapshot["rows"] if row["gsis_id"] == "00-003"
    )
    assert receiver["component_support"]["component_a"] is True
    assert receiver["component_values"]["component_a"] == 0.6
    assert receiver["component_missing_reason_codes"]["component_a"] == [
        "source-absent"
    ]


@pytest.mark.parametrize(
    ("drift", "expected"),
    [
        ("target-week", "target replay differs"),
        ("target-task", "target replay differs"),
        ("population-row", "exactly cover the target spine"),
    ],
)
def test_target_week_population_deletion_invariance_is_row_replayed(
    drift: str, expected: str
) -> None:
    fixture = _fixture()
    role = "rb-prior-context"
    extract = _extract(fixture, role)
    if drift == "target-week":
        extract["rows"][0]["target_week"] = 4
    elif drift == "target-task":
        extract["rows"][0]["target_task_id"] = "postgame-participants"
    else:
        extract["rows"].pop()
    _rehash_extract(fixture, role)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match=expected,
    ):
        _capture(fixture)


def test_self_consistent_target_spine_claim_cannot_replace_derived_replay() -> None:
    store, fixture, identities = _capture()
    export_identity = dict(identities["source_export_identity"])
    export = store.body(export_identity)
    export["target_spine_replay"]["population_authority"] = "caller-asserted"
    export["target_spine_replay"] = _hashed(
        {
            key: value
            for key, value in export["target_spine_replay"].items()
            if key != "target_spine_sha256"
        },
        "target_spine_sha256",
    )
    export = _hashed(
        {
            key: value
            for key, value in export.items()
            if key != "matchup_source_export_sha256"
        },
        "matchup_source_export_sha256",
    )
    identities["source_export_identity"] = store.replace(
        export_identity, export
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="target-spine replay differs",
    ):
        _reopen(store, fixture, identities)


@pytest.mark.parametrize(
    ("drift", "expected"),
    [
        ("unavailable", "QB depth evidence source is unavailable"),
        ("duplicate", r"QB depth row\[1\] differs"),
        ("annotation", "QB depth is not evidence-bound"),
        ("null-without-reason", r"QB depth row\[0\] differs"),
        ("catalog-context", r"QB depth row\[0\] differs"),
    ],
)
def test_qb_depth_is_separately_bound_and_cannot_be_asserted(
    drift: str, expected: str
) -> None:
    fixture = _fixture()
    depth = _extract(fixture, source.QB_DEPTH_SOURCE_ROLE)
    if drift == "unavailable":
        _make_extract_unavailable(fixture, source.QB_DEPTH_SOURCE_ROLE)
    elif drift == "duplicate":
        depth["rows"].append(deepcopy(depth["rows"][0]))
        _rehash_extract(fixture, source.QB_DEPTH_SOURCE_ROLE)
    elif drift == "annotation":
        fixture["annotations"][0]["qb_depth1"] = False
    elif drift == "null-without-reason":
        depth["rows"][0]["depth1"] = None
        _rehash_extract(fixture, source.QB_DEPTH_SOURCE_ROLE)
    else:
        depth["rows"][0]["team"] = "BBB"
        _rehash_extract(fixture, source.QB_DEPTH_SOURCE_ROLE)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match=expected,
    ):
        _capture(fixture)


def test_2025_unknown_qb_depth_is_explicitly_fail_closed() -> None:
    fixture = _fixture()
    _retarget_to_2025_with_unknown_qb_depth(fixture)
    store, captured, identities = _capture(fixture)
    snapshot = _reopen(store, captured, identities)
    qb_row = next(row for row in snapshot["rows"] if row["family"] == "qb")

    assert snapshot["slate"]["season"] == 2025
    assert snapshot["qb_depth_unknown_policy"] == (
        "exclude-qb-from-matchup-admission"
    )
    assert qb_row["qb_depth1"] is None
    assert qb_row["qb_depth_evidence_class"] == "unknown"


@pytest.mark.parametrize("drift", ["missing", "extra", "renamed"])
def test_annotation_components_exactly_match_frozen_family_fields(
    drift: str,
) -> None:
    fixture = _fixture()
    annotation = fixture["annotations"][2]
    if drift == "missing":
        del annotation["component_values"]["component_b"]
    elif drift == "extra":
        annotation["component_values"]["component_c"] = 0.5
        annotation["component_support"]["component_c"] = True
        annotation["component_source_bounds"]["component_c"] = deepcopy(
            annotation["component_source_bounds"]["component_a"]
        )
    else:
        for field in (
            "component_values",
            "component_support",
            "component_source_bounds",
        ):
            annotation[field]["renamed_component"] = annotation[field].pop(
                "component_a"
            )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="component dictionaries differ",
    ):
        _capture(fixture)


def test_family_field_and_component_role_drift_reaches_annotations() -> None:
    fixture = _fixture()
    receiver = fixture["families"]["receiver"]
    receiver["fields"].append({
        "name": "component_c",
        "field_type": "percentile",
        "nullable": True,
        "description": "new unbound component",
    })
    receiver["component_source_roles"]["component_c"] = [
        "receiver-role-components"
    ]
    _rehash_family(fixture, "receiver")
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match=(
            "component dictionaries differ|"
            "component rows do not exactly cover the target spine"
        ),
    ):
        _capture(fixture)

    fixture = _fixture()
    fixture["families"]["receiver"]["component_source_roles"][
        "component_a"
    ] = ["defense-role-concessions"]
    _rehash_family(fixture, "receiver")
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="component roles differ from family|not all component-bound",
    ):
        _capture(fixture)


@pytest.mark.parametrize("carrier", ["source-row", "sql"])
def test_outcome_fields_and_017s_path_are_rejected(carrier: str) -> None:
    fixture = _fixture()
    if carrier == "source-row":
        fixture["extracts"][0]["rows"][0]["actual_score"] = 201.0
        rows = fixture["extracts"][0]["rows"]
        digest = source.canonical_sha256(rows)
        fixture["extracts"][0]["rows_sha256"] = digest
        fixture["extracts"][0]["source_identity_or_extract_sha256"] = digest
        fixture["metadata"]["source_relations"][0][
            "exact_extract_sha256"
        ] = digest
    else:
        fixture["rendered_sql_raw"] = (
            b"SELECT actual_score FROM 017s_lineup_matchup_evidence"
        )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="outcome field|forbidden outcome path",
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    "forbidden_name",
    [
        "winner_membership",
        "field_rank",
        "field_percentile",
        "final_score",
        "post_lock_timestamp",
        "after_kickoff_time",
        "contest_winner_flag",
        "lineup_score",
        "dk_points",
        "tournament_rank",
        "post_slate_timestamp",
    ],
)
@pytest.mark.parametrize("carrier", ["coherently-hashed-source", "sql"])
def test_semantically_equivalent_outcome_and_post_lock_paths_fail_closed(
    forbidden_name: str, carrier: str
) -> None:
    fixture = _fixture()
    if carrier == "coherently-hashed-source":
        family = "qb"
        role = "qb-prior-context"
        schema = fixture["families"][family]["source_role_schemas"][role]
        schema["row_fields"].append(forbidden_name)
        schema["row_fields"].sort()
        for row in _extract(fixture, role)["rows"]:
            row[forbidden_name] = 1
        _rehash_extract(fixture, role)
        _rehash_role_schema(fixture, family, role)
    else:
        fixture["rendered_sql_raw"] = (
            b"WITH target AS (SELECT @season AS season, @week AS week, "
            b"@slate_id AS slate_id, @task_id AS task_id, "
            b"@lock_time_utc AS lock_time_utc, "
            b"@source_roles AS source_roles) SELECT "
            + forbidden_name.encode("utf-8")
            + b" FROM target"
        )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="forbidden outcome|post-lock semantics|post-lock field",
    ):
        _capture(fixture)


@pytest.mark.parametrize(
    "sql",
    [
        b"SELECT 1",
        (
            b"WITH target AS (SELECT @season, @week, @slate_id, @task_id, "
            b"@lock_time_utc, @source_roles, @field_rank) SELECT 1 FROM target"
        ),
        (
            b"WITH target AS (SELECT @season, @week, @slate_id, @task_id, "
            b"@lock_time_utc, @source_roles) SELECT 1 FROM target; DELETE x"
        ),
    ],
)
def test_rendered_sql_requires_exact_parameters_and_one_read_only_query(
    sql: bytes,
) -> None:
    fixture = _fixture()
    fixture["rendered_sql_raw"] = sql
    with pytest.raises(source.CorpusR6MatchupSourceV1Error):
        _capture(fixture)


def test_rendered_sql_relations_are_exactly_bound_to_receipt_relations() -> None:
    fixture = _fixture()
    substituted_relations = deepcopy(
        fixture["metadata"]["source_relations"]
    )
    substituted_relations[0]["table_or_object"] = (
        "bq://fixture_project.fixture_dataset.weekly_stats"
    )
    fixture["rendered_sql_raw"] = source.build_rendered_sql_v1(
        substituted_relations
    )
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="frozen exact relation-bound template|referenced relations differ",
    ):
        _capture(fixture)


def test_relation_metadata_cannot_hide_an_outcome_relation_alias() -> None:
    fixture = _fixture()
    role = str(fixture["extracts"][0]["role"])
    relation = "bq://fixture_project.fixture_dataset.lineup_score"
    _extract(fixture, role)["relation_or_object"] = relation
    _relation(fixture, role)["table_or_object"] = relation
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error,
        match="forbidden outcome/post-lock semantics",
    ):
        _capture(fixture)


def test_module_has_no_outcome_or_score_imports() -> None:
    module_path = Path(source.__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert all(
        token not in imported.lower()
        for imported in imports
        for token in ("outcome", "actual", "score")
    )


def test_create_once_collision_does_not_overwrite() -> None:
    store, _, _ = _capture()
    retained = deepcopy(store.objects)
    with pytest.raises(
        source.CorpusR6MatchupSourceV1Error, match="create-once collision"
    ):
        _capture(store=store)
    assert store.objects == retained
