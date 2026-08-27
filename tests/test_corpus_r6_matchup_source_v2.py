from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import pytest

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


NAMESPACE = "gs://fixture-bucket/r6-matchup-v2/"
CATALOG_NAMESPACE = "gs://fixture-bucket/r6-catalog-v1/"
CANDIDATE_NAMESPACE = "gs://fixture-bucket/r6-candidates-v1/"
UPSTREAM_NAMESPACE = "gs://fixture-bucket/r6-upstream-v1/"


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(
    label: str,
    *,
    raw: bytes | None = None,
    uri: str | None = None,
    generation_offset: int = 0,
) -> dict[str, object]:
    digest = _digest(label) if raw is None else sha256(raw).hexdigest()
    return {
        "uri": uri or f"gs://fixture-bucket/objects/{label}.json",
        "generation": str(int(digest[:12], 16) + 1 + generation_offset),
        "sha256": digest,
        "bytes": 100 + len(label) if raw is None else len(raw),
    }


def _identity_for_body(
    label: str,
    body: Mapping[str, object],
    *,
    uri: str | None = None,
    generation_offset: int = 0,
) -> dict[str, object]:
    return _identity(
        label,
        raw=source.canonical_json_bytes(body),
        uri=uri,
        generation_offset=generation_offset,
    )


def _code(
    label: str,
    *,
    module_path: str = source.PRODUCER_MODULE_PATH,
) -> dict[str, str]:
    return {
        "source_commit_sha": _digest(f"commit-{label}")[:40],
        "module_path": module_path,
        "module_sha256": _digest(f"module-{label}"),
    }


def _rehash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = deepcopy(dict(value))
    result.pop(field, None)
    result[field] = source.canonical_sha256(result)
    return result


def _catalog_policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in catalog_v1.FALSE_AUTHORITY_FIELDS},
    }


def _schedule_row(ordinal: int) -> dict[str, object]:
    slate = catalog_v1.expected_slate_for_source_task(ordinal)
    september_first = datetime(int(slate["season"]), 9, 1)
    first_sunday = september_first + timedelta(
        days=(6 - september_first.weekday()) % 7
    )
    gameday = first_sunday + timedelta(weeks=int(slate["week"]) - 1)
    local = datetime.combine(
        gameday.date(),
        datetime.strptime("13:00", "%H:%M").time(),
        tzinfo=ZoneInfo("America/New_York"),
    )
    return {
        "away_team": "BBB",
        "game_id": f"schedule-{ordinal:02d}",
        "game_type": "REG",
        "gameday": gameday.strftime("%Y-%m-%d"),
        "gametime": "13:00",
        "home_team": "AAA",
        "kickoff_time_utc": local.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "season": int(slate["season"]),
        "week": int(slate["week"]),
    }


def _players(ordinal: int) -> list[dict[str, object]]:
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "DST"]
    rows: list[dict[str, object]] = []
    for offset, position in enumerate(positions, start=1):
        team = "BBB" if position == "DST" else "AAA"
        rows.append({
            "id": f"p{ordinal:02d}-{offset:02d}",
            "pos": position,
            "team": team,
            "opp": "AAA" if team == "BBB" else "BBB",
            "game_id": f"opaque-catalog-game-{ordinal:02d}",
            "salary": 8000 - offset * 250,
        })
    return rows


def _catalog(ordinal: int) -> dict[str, object]:
    slate = catalog_v1.expected_slate_for_source_task(ordinal)
    lane = catalog_v1.expected_lane_for_source_task(ordinal)
    players = _players(ordinal)
    player_ids = [str(player["id"]) for player in players]
    body: dict[str, object] = {
        "schema_version": catalog_v1.PLAYER_CATALOG_SCHEMA,
        "task_id": catalog_v1.task_id_for_source_task(ordinal),
        "slate": slate,
        "task_ordinal": lane["task_ordinal"],
        "source_task_ordinal": ordinal,
        "universe_scope": catalog_v1.UNIVERSE_SCOPE,
        "authority_boundary": catalog_v1.AUTHORITY_BOUNDARY,
        "source_authority": _identity(f"catalog-authority-{ordinal:02d}"),
        "players": players,
        "player_count": len(players),
        "ordered_player_ids_sha256": source.canonical_sha256(player_ids),
        "source_catalog_sha256": source.canonical_sha256(players),
        **_catalog_policy(),
    }
    return _rehash(body, "player_catalog_sha256")


def _catalog_release() -> dict[str, Any]:
    catalogs = [_catalog(ordinal) for ordinal in range(source.TASK_COUNT)]
    catalog_ids: list[dict[str, object]] = []
    entries: list[dict[str, object]] = []
    for ordinal, catalog in enumerate(catalogs):
        slate_id = str(catalog["slate"]["slate_id"])
        prefix = f"{CATALOG_NAMESPACE}tasks/{ordinal:04d}-{slate_id}/"
        catalog_identity = _identity_for_body(
            f"catalog-{ordinal:02d}",
            catalog,
            uri=f"{prefix}player-catalog.json",
        )
        catalog_ids.append(catalog_identity)
        lane = catalog_v1.expected_lane_for_source_task(ordinal)
        entries.append({
            "source_task_ordinal": ordinal,
            "task_id": catalog["task_id"],
            "slate": catalog["slate"],
            "lane_id": lane["lane_id"],
            "lane_ordinal": lane["lane_ordinal"],
            "task_ordinal": lane["task_ordinal"],
            "accepted_slate_membership_sha256": _digest(
                f"accepted-membership-{ordinal}"
            ),
            "source_task_authority_sha256": _digest(
                f"source-task-authority-{ordinal}"
            ),
            "catalog_identity": catalog_identity,
            "derivation_receipt_identity": _identity(
                f"catalog-derivation-{ordinal:02d}",
                uri=f"{prefix}catalog-derivation-receipt.json",
            ),
            "source_catalog_sha256": catalog["source_catalog_sha256"],
            "player_count": catalog["player_count"],
            "ordered_player_ids_sha256": catalog[
                "ordered_player_ids_sha256"
            ],
        })
    source_identity = _identity("catalog-later-source")
    completion_identity = _identity("catalog-completion")
    body: dict[str, object] = {
        "schema_version": catalog_v1.RELEASE_SCHEMA,
        "release_id": "r6-catalog-fixture-v1",
        "publication_mode": "create_once",
        "universe_scope": catalog_v1.UNIVERSE_SCOPE,
        "authority_boundary": catalog_v1.AUTHORITY_BOUNDARY,
        "catalog_namespace": CATALOG_NAMESPACE,
        "tracked_root_binding": {
            "g0_authority_lock_schema": catalog_v1.G0_AUTHORITY_LOCK_SCHEMA,
            "g0_authority_lock_relative_path": "reports/fixed-g0.json",
            "g0_authority_lock_file_sha256": _digest("g0-lock-file"),
            "g0_authority_lock_sha256": _digest("g0-lock-internal"),
            "source_commit_sha": _digest("catalog-source-commit")[:40],
            "panel_object_identity": _identity("catalog-panel"),
            "panel_index_sha256": _digest("catalog-panel-index"),
            "accepted_slate_count": source.TASK_COUNT,
        },
        "later_source_freeze_identity": source_identity,
        "later_source_freeze_manifest_sha256": _digest(
            "catalog-later-source-internal"
        ),
        "artifact_source_authority_completion_identity": completion_identity,
        "artifact_source_authority_completion_sha256": _digest(
            "catalog-completion-internal"
        ),
        "derivation_code_identity": _code(
            "catalog-derivation",
            module_path=(
                "src/nfl_dfs/research/"
                "corpus_r6_player_catalog_fixed_g0_adapter_v1.py"
            ),
        ),
        "task_count": source.TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": source.canonical_sha256(entries),
        **_catalog_policy(),
    }
    release = _rehash(body, "release_sha256")
    return {
        "catalogs": catalogs,
        "catalog_identities": catalog_ids,
        "release": release,
        "release_identity": _identity_for_body(
            "catalog-release",
            release,
            uri=f"{CATALOG_NAMESPACE}catalog-release.json",
        ),
    }


def _positive_row(slice_kind: str, fields: list[str]) -> dict[str, object]:
    return {
        field: (
            2022 if field == "season"
            else 1 if field in {"week", "target_week"}
            else f"{slice_kind}-{field}"
        )
        for field in fields
    }


def _upstream() -> dict[str, Any]:
    registry = source.frozen_upstream_pack_registry_v1()
    pack_rows: list[dict[str, object]] = []
    packs: list[dict[str, object]] = []
    for entry in registry["packs"]:
        pack_id = str(entry["pack_id"])
        slices: list[dict[str, object]] = []
        for schema in entry["positive_row_schemas"]:
            slice_kind = str(schema["slice_kind"])
            fields = [str(field) for field in schema["row_fields"]]
            rows = (
                [_schedule_row(ordinal) for ordinal in range(source.TASK_COUNT)]
                if slice_kind == "schedule-games"
                else [_positive_row(slice_kind, fields)]
            )
            slices.append({"slice_kind": slice_kind, "rows": rows})
        rows_object = source.build_upstream_pack_rows_v1(
            pack_id=pack_id, slices=slices
        )
        pack_rows.append(rows_object)
        rows_identity = _identity_for_body(
            f"upstream-rows-{pack_id}",
            rows_object,
            uri=f"{UPSTREAM_NAMESPACE}packs/{pack_id}/rows.json",
        )
        if entry["provenance_kind"] == "warehouse-query-receipt":
            query_identity: dict[str, object] | None = _identity(
                f"query-receipt-{pack_id}"
            )
            artifact_identities: list[dict[str, object]] = []
        else:
            query_identity = None
            artifact_identities = [_identity(f"artifact-manifest-{pack_id}")]
        packs.append({
            "pack_id": pack_id,
            "source_kind": entry["source_kind"],
            "provenance_kind": entry["provenance_kind"],
            "positive_row_schemas": entry["positive_row_schemas"],
            "positive_row_schema_manifest_sha256": entry[
                "positive_row_schema_manifest_sha256"
            ],
            "exact_rows_identity": rows_identity,
            "row_count": rows_object["row_count"],
            "rows_sha256": rows_object["rows_sha256"],
            "source_period_min": entry["source_period_min"],
            "source_period_max": entry["source_period_max"],
            "warehouse_query_receipt_identity": query_identity,
            "frozen_artifact_manifest_identities": artifact_identities,
            "projection_code_identity": _code(
                f"projection-{pack_id}",
                module_path="src/nfl_dfs/research/source_projection.py",
            ),
        })
    root = _identity("fixed-upstream-source-root")
    release = source.build_upstream_release_v1(
        release_id="r6-upstream-fixture-v1",
        namespace=UPSTREAM_NAMESPACE,
        fixed_source_root_identity=root,
        packs=packs,
        pack_row_objects=pack_rows,
    )
    return {
        "release": release,
        "release_identity": _identity_for_body(
            "upstream-release",
            release,
            uri=f"{UPSTREAM_NAMESPACE}upstream-release.json",
        ),
        "root": root,
        "pack_rows": pack_rows,
    }


def _candidate_release(catalog_panel: Mapping[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, object]] = []
    candidate_ids: list[list[str]] = []
    for ordinal, catalog in enumerate(catalog_panel["catalogs"]):
        ids = [f"candidate-{ordinal:02d}-{index:03d}" for index in range(100)]
        candidate_ids.append(ids)
        roster_ids = [str(player["id"]) for player in catalog["players"]]
        artifact = source.build_accepted_candidate_artifact_v1(
            source_task_ordinal=ordinal,
            rows=[{"candidate_id": value, "player_ids": roster_ids} for value in ids],
        )
        artifact_identity = _identity_for_body(
            f"candidate-artifact-{ordinal:02d}",
            artifact,
            uri=(
                f"{CANDIDATE_NAMESPACE}source-task-{ordinal:02d}-"
                f"{catalog['slate']['slate_id']}/accepted-candidates.json"
            ),
        )
        entry: dict[str, object] = {
            "source_task_ordinal": ordinal,
            "task_id": catalog["task_id"],
            "slate": catalog["slate"],
            "catalog_identity": catalog_panel["catalog_identities"][ordinal],
            "candidate_artifact": artifact,
            "candidate_artifact_identity": artifact_identity,
            "candidate_count": len(ids),
            "ordered_candidate_ids_sha256": source.canonical_sha256(ids),
        }
        entry["accepted_candidate_release_entry_sha256"] = (
            source.canonical_sha256(entry)
        )
        entries.append(entry)
    release = source.build_accepted_candidate_release_v1(
        release_id="accepted-v12-candidates-fixture-v1",
        namespace=CANDIDATE_NAMESPACE,
        source_candidate_panel_identity=_identity("accepted-v12-panel"),
        entries=entries,
    )
    return {
        "release": release,
        "release_identity": _identity_for_body(
            "accepted-candidate-release",
            release,
            uri=f"{CANDIDATE_NAMESPACE}accepted-candidate-release.json",
        ),
        "candidate_ids": candidate_ids,
    }


def _period_bounds(
    rule: str, season: int, week: int,
) -> tuple[str, dict[str, object] | None, dict[str, object] | None]:
    target = {"season": season, "week": week}
    if rule == "target-slate":
        return "target-slate", target, target
    if rule == "legacy-depth":
        return ("prelock-snapshot", target, target) if season <= 2024 else (
            "unavailable", None, None
        )
    if rule == "snapshot-depth":
        return ("prelock-snapshot", target, target) if season == 2025 else (
            "unavailable", None, None
        )
    if rule == "alignment-w4":
        if week <= 4:
            return "unavailable", None, None
        return (
            "alignment-window",
            {"season": season, "week": week - 4},
            {"season": season, "week": week - 1},
        )
    if rule == "prior-season-n-minus-one":
        prior = {"season": season - 1, "week": None}
        return "prior-season-full", prior, prior
    if week == 1:
        return (
            "prior-game-window",
            {"season": season - 1, "week": 1},
            {"season": season - 1, "week": 18},
        )
    return (
        "prior-game-window",
        {"season": season - 1, "week": 1},
        {"season": season, "week": week - 1},
    )


def _role_periods(
    ordinal: int,
    definition: Mapping[str, object],
    upstream: Mapping[str, Any],
    schedule_row: Mapping[str, object],
    schedule_identity: Mapping[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    slate = catalog_v1.expected_slate_for_source_task(ordinal)
    packs = {str(pack["pack_id"]): pack for pack in upstream["release"]["packs"]}
    result: list[dict[str, object]] = []
    source_slices: list[dict[str, object]] = []
    for period_ordinal, requirement in enumerate(definition["period_requirements"]):
        rule = str(requirement["period_rule"])
        kind, minimum, maximum = _period_bounds(
            rule, int(slate["season"]), int(slate["week"])
        )
        pack = packs[str(requirement["pack_id"])]
        is_target_schedule = (
            requirement["pack_id"] == source.SCHEDULE_PACK
            and requirement["slice_kind"] == "schedule-games"
            and rule == "target-slate"
        )
        label = (
            f"slice-{ordinal:02d}-{definition['ordinal']}-{period_ordinal}"
        )
        slice_uri = (
            f"{NAMESPACE}source-task-{ordinal:02d}-{slate['slate_id']}/"
            f"producer/slices/{int(definition['ordinal']):02d}-"
            f"{period_ordinal:02d}-{requirement['slice_kind']}.json"
        )
        selected_rows = (
            [dict(schedule_row)]
            if is_target_schedule
            else []
            if kind == "unavailable"
            else [{"fixture_slice": label}]
        )
        game_event_slices = {
            "schedule-games", "weekly-player-stats", "fp-route-share",
            "pfr-pass-rush", "pfr-secondary", "pfr-snap-positions",
            "sis-defender-alignment", "sis-run-context",
        }
        event_kickoffs = (
            [str(schedule_row["kickoff_time_utc"])]
            if is_target_schedule
            else ["2022-01-01T18:00:00Z"] * len(selected_rows)
            if kind == "prior-game-window"
            and requirement["slice_kind"] in game_event_slices
            else [None] * len(selected_rows)
        )
        slice_identity = (
            dict(schedule_identity)
            if is_target_schedule
            and int(definition["ordinal"]) == 0
            and period_ordinal == 0
            else _identity(
                label,
                raw=source.canonical_json_bytes(selected_rows),
                uri=slice_uri,
            )
        )
        period = source.build_historical_source_period_v1(
            pack_id=str(requirement["pack_id"]),
            slice_kind=str(requirement["slice_kind"]),
            period_kind=kind,
            source_period_min=minimum,
            source_period_max=maximum,
            upstream_pack_rows_identity=pack["exact_rows_identity"],
            exact_slice_identity=slice_identity,
            slice_row_count=len(selected_rows),
            slice_rows_sha256=str(slice_identity["sha256"]),
            row_event_kickoff_times_utc=event_kickoffs,
        )
        result.append(period)
        source_slices.append({
            "role": str(definition["role"]),
            "period_ordinal": period_ordinal,
            "pack_id": requirement["pack_id"],
            "slice_kind": requirement["slice_kind"],
            "rows": selected_rows,
            "row_count": len(selected_rows),
            "rows_sha256": source.canonical_sha256(selected_rows),
            "row_event_kickoff_times_utc": event_kickoffs,
            "row_event_kickoff_manifest_sha256": source.canonical_sha256(
                event_kickoffs
            ),
            "exact_slice_identity": slice_identity,
            "historical_source_period_sha256": period[
                "historical_source_period_sha256"
            ],
        })
    return result, source_slices


def _missingness(**updates: int) -> dict[str, int]:
    result = {
        "identity_unresolved": 0,
        "insufficient_history": 0,
        "other_registered": 0,
        "source_unavailable": 0,
        "unknown_depth": 0,
    }
    result.update(updates)
    return result


def _role_entries(
    ordinal: int,
    catalog: Mapping[str, object],
    upstream: Mapping[str, Any],
    schedule_row: Mapping[str, object],
    schedule_identity: Mapping[str, object],
    *,
    unknown_qb_depth: bool,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    populations = {
        "qb": sum(player["pos"] == "QB" for player in catalog["players"]),
        "rb": sum(player["pos"] == "RB" for player in catalog["players"]),
        "receiver": sum(
            player["pos"] in {"WR", "TE"} for player in catalog["players"]
        ),
    }
    week = int(catalog["slate"]["week"])
    entries: list[dict[str, object]] = []
    row_objects: list[dict[str, object]] = []
    source_slices: list[dict[str, object]] = []
    for definition in source.frozen_role_registry_v2()["roles"]:
        role = str(definition["role"])
        if role == "schedule-spine":
            expected, supported, missingness = 1, 1, _missingness()
        elif role == "qb-depth-evidence":
            expected = populations["qb"]
            supported = 0 if unknown_qb_depth else expected
            missingness = _missingness(
                unknown_depth=expected if unknown_qb_depth else 0
            )
        else:
            expected = populations[str(definition["family"])]
            if week <= 4 and role in {
                "receiver-alignment-vulnerability",
                "receiver-defender-workload-quality",
            }:
                supported, missingness = 0, _missingness(
                    source_unavailable=expected
                )
            else:
                supported, missingness = expected, _missingness()
        if definition["population_role"] == "component":
            family = str(definition["family"])
            component = str(definition["component"])
            player_ids = sorted(
                str(player["id"]) for player in catalog["players"]
                if (
                    (family == "qb" and player["pos"] == "QB")
                    or (family == "rb" and player["pos"] == "RB")
                    or (family == "receiver" and player["pos"] in {"WR", "TE"})
                )
            )
            retained_rows = [{
                "gsis_id": player_id,
                "component": component,
                "raw_value": 1.0 if supported else None,
                "percentile": 0.0 if supported else None,
                "supported": bool(supported),
                "observed_game_count": None,
                "missingness_reason": None if supported else "source_unavailable",
            } for player_id in player_ids]
        else:
            retained_rows = [
                {"cell_id": f"{ordinal:02d}-{role}-{offset:03d}"}
                for offset in range(expected)
            ]
        retained_rows_sha256 = source.canonical_sha256(retained_rows)
        row_objects.append({
            "role": role,
            "rows": retained_rows,
            "row_count": len(retained_rows),
            "rows_sha256": retained_rows_sha256,
        })
        periods, role_slices = _role_periods(
            ordinal,
            definition,
            upstream,
            schedule_row,
            schedule_identity,
        )
        source_slices.extend(role_slices)
        entries.append(source.build_role_entry_v1(
            role=role,
            source_periods=periods,
            expected_population_count=expected,
            retained_row_count=expected,
            retained_rows_sha256=retained_rows_sha256,
            supported_cell_count=supported,
            missingness_counts=missingness,
        ))
    return entries, row_objects, source_slices


def _bundle_policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _input_bundle(
    *,
    producer_id: str,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    candidate_release_identity: Mapping[str, object],
    upstream_release_identity: Mapping[str, object],
    target_spine: Mapping[str, object],
    role_entries: list[dict[str, object]],
    role_row_objects: list[dict[str, object]],
    source_slices: list[dict[str, object]],
    qb_depth_census: Mapping[str, object],
    admission_support_census: Mapping[str, object],
) -> dict[str, object]:
    role_by_component = {
        str(entry["component"]): (entry, row_object)
        for entry, row_object in zip(
            role_entries, role_row_objects, strict=True
        )
        if entry["population_role"] == "component"
    }
    component_sets = source.family_components_v1()
    annotations = []
    depth_by_id = {
        str(row["player_id"]): row["qb_depth1"]
        for row in qb_depth_census["rows"]
    }
    for player in sorted(
        (player for player in catalog["players"] if player["pos"] != "DST"),
        key=lambda player: str(player["id"]),
    ):
        family = "qb" if player["pos"] == "QB" else (
            "rb" if player["pos"] == "RB" else "receiver"
        )
        components = component_sets[family]
        component_rows = {
            component: next(
                row for row in role_by_component[component][1]["rows"]
                if row["gsis_id"] == player["id"]
            )
            for component in components
        }
        supported_values = [
            float(component_rows[component]["percentile"])
            for component in components
            if component_rows[component]["supported"] is True
        ]
        edge = (
            sum(supported_values) / len(supported_values)
            if len(supported_values) >= 2 else None
        )
        qb_depth = depth_by_id.get(str(player["id"])) if family == "qb" else None
        annotations.append({
            "gsis_id": str(player["id"]),
            "family": family,
            "position": player["pos"],
            "qb_depth1": qb_depth,
            "qb_depth_evidence_class": (
                source.EVIDENCE_CLASS if family == "qb" and qb_depth is not None
                else "unknown" if family == "qb" else None
            ),
            "raw_component_values": {
                component: component_rows[component]["raw_value"]
                for component in components
            },
            "component_observed_game_counts": {
                component: None for component in components
            },
            "component_values": {
                component: component_rows[component]["percentile"]
                for component in components
            },
            "component_support": {
                component: component_rows[component]["supported"]
                for component in components
            },
            "component_missingness_reasons": {
                component: component_rows[component]["missingness_reason"]
                for component in components
            },
            "matchup_component_count": len(supported_values),
            "matchup_edge_score": edge,
            "annotation_row_present": edge is not None,
            "component_source_bounds": {
                component: [{
                    "period_kind": period["period_kind"],
                    "source_period_min": period["source_period_min"],
                    "source_period_max": period["source_period_max"],
                    "minimum_source_event_time_utc": period[
                        "minimum_source_event_time_utc"
                    ],
                    "maximum_source_event_time_utc": period[
                        "maximum_source_event_time_utc"
                    ],
                    "row_event_kickoff_manifest_sha256": period[
                        "row_event_kickoff_manifest_sha256"
                    ],
                    "exact_slice_identity": period["exact_slice_identity"],
                    "historical_source_period_sha256": period[
                        "historical_source_period_sha256"
                    ],
                } for period in role_by_component[component][0]["source_periods"]]
                for component in components
            },
        })
    semantic = {
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "lock_time_utc": target_spine["lock_time_utc"],
        "target_games": target_spine["games"],
        "target_roles": {},
        "qb_depth_census": dict(qb_depth_census),
        "annotation_rows": annotations,
        "annotation_rows_sha256": source.canonical_sha256(annotations),
        "raw_component_manifest_sha256": _digest("synthetic-components"),
    }
    body: dict[str, object] = {
        "schema_version": source.PRODUCER_INPUT_BUNDLE_SCHEMA,
        "producer_id": producer_id,
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "lock_time_utc": target_spine["lock_time_utc"],
        "catalog_identity": dict(catalog_identity),
        "catalog_release_identity": dict(catalog_release_identity),
        "catalog_replay_receipt_identity": dict(
            catalog_replay_receipt_identity
        ),
        "accepted_candidate_release_identity": dict(
            candidate_release_identity
        ),
        "upstream_source_release_identity": dict(upstream_release_identity),
        "family_registry": source.frozen_family_registry_v1(),
        "family_registry_sha256": source.frozen_family_registry_v1()[
            "family_registry_sha256"
        ],
        "semantic_output": semantic,
        "semantic_output_sha256": source.canonical_sha256(semantic),
        "target_spine": dict(target_spine),
        "target_spine_sha256": target_spine["target_spine_sha256"],
        "source_slices": source_slices,
        "source_slice_manifest_sha256": source.canonical_sha256(source_slices),
        "role_entries": role_entries,
        "role_entry_manifest_sha256": source.canonical_sha256(role_entries),
        "role_row_objects": role_row_objects,
        "role_row_manifest_sha256": source.canonical_sha256(role_row_objects),
        "annotation_rows": annotations,
        "annotation_row_count": len(annotations),
        "annotation_rows_sha256": source.canonical_sha256(annotations),
        "qb_depth_census": dict(qb_depth_census),
        "admission_support_census": dict(admission_support_census),
        **_bundle_policy(),
    }
    return _rehash(body, "input_bundle_sha256")


def _admission(
    ordinal: int,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    candidate_panel: Mapping[str, Any],
    *,
    passing: bool,
) -> dict[str, object]:
    binding = source.build_candidate_support_binding_v1(
        source_task_ordinal=ordinal,
        catalog_identity=catalog_identity,
        accepted_candidate_release=candidate_panel["release"],
        accepted_candidate_release_identity=candidate_panel["release_identity"],
    )
    qb_id = next(str(player["id"]) for player in catalog["players"] if player["pos"] == "QB")
    rows = [{
        "candidate_id": candidate_id,
        "qb_player_id": qb_id,
        "qb_depth_true": passing,
        "supported_matchup_player_count": 8,
        "annotation_completeness": 1.0,
    } for candidate_id in candidate_panel["candidate_ids"][ordinal]]
    support = source.build_candidate_support_rows_v1(
        candidate_support_binding=binding,
        structural_catalog=catalog,
        accepted_candidate_release=candidate_panel["release"],
        accepted_candidate_release_identity=candidate_panel["release_identity"],
        rows=rows,
    )
    return source.build_admission_support_census_v1(
        candidate_support_binding=binding,
        structural_catalog=catalog,
        accepted_candidate_release=candidate_panel["release"],
        accepted_candidate_release_identity=candidate_panel["release_identity"],
        candidate_support_rows=rows,
        candidate_support_rows_identity=_identity_for_body(
            f"candidate-support-{ordinal:02d}-{'pass' if passing else 'fail'}",
            support,
            uri=(
                f"{NAMESPACE}source-task-{ordinal:02d}-"
                f"{catalog['slate']['slate_id']}/producer/"
                "candidate-support-rows.json"
            ),
        ),
    )


def _receipt_fixture(
    ordinal: int,
    *,
    catalog_panel: Mapping[str, Any],
    candidate_panel: Mapping[str, Any],
    upstream: Mapping[str, Any],
    producer_code_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    unknown_qb_depth: bool = False,
) -> dict[str, Any]:
    catalog = catalog_panel["catalogs"][ordinal]
    catalog_identity = catalog_panel["catalog_identities"][ordinal]
    schedule_row = _schedule_row(ordinal)
    schedule_identity = _identity(
        f"target-schedule-{ordinal:02d}",
        raw=source.canonical_json_bytes([schedule_row]),
        uri=(
            f"{NAMESPACE}source-task-{ordinal:02d}-"
            f"{catalog['slate']['slate_id']}/producer/"
            "slices/00-00-schedule-games.json"
        ),
    )
    target_spine = source.build_target_spine_v1(
        structural_catalog=catalog,
        catalog_identity=catalog_identity,
        upstream_source_release=upstream["release"],
        upstream_pack_row_objects=upstream["pack_rows"],
        schedule_slice_identity=schedule_identity,
        games=[schedule_row],
    )
    qb_id = next(str(player["id"]) for player in catalog["players"] if player["pos"] == "QB")
    qb_status = None if unknown_qb_depth else True
    depth_rows = [{"player_id": qb_id, "qb_depth1": qb_status}]
    depth_census = {
        "catalog_qb_count": 1,
        "rows": depth_rows,
        "row_manifest_sha256": source.canonical_sha256(depth_rows),
        "depth_true_count": 0 if unknown_qb_depth else 1,
        "depth_false_count": 0,
        "depth_unknown_count": 1 if unknown_qb_depth else 0,
        "qb_depth_complete": not unknown_qb_depth,
    }
    role_entries, role_row_objects, source_slices = _role_entries(
        ordinal,
        catalog,
        upstream,
        schedule_row,
        schedule_identity,
        unknown_qb_depth=unknown_qb_depth,
    )
    admission = _admission(
        ordinal,
        catalog,
        catalog_identity,
        candidate_panel,
        passing=not unknown_qb_depth,
    )
    bundle = _input_bundle(
        producer_id="r6-producer-v1",
        catalog=catalog,
        catalog_identity=catalog_identity,
        catalog_release_identity=catalog_panel["release_identity"],
        catalog_replay_receipt_identity=catalog_replay_receipt_identity,
        candidate_release_identity=candidate_panel["release_identity"],
        upstream_release_identity=upstream["release_identity"],
        target_spine=target_spine,
        role_entries=role_entries,
        role_row_objects=role_row_objects,
        source_slices=source_slices,
        qb_depth_census=depth_census,
        admission_support_census=admission,
    )
    input_identity = _identity_for_body(
        f"input-bundle-{ordinal:02d}",
        bundle,
        uri=(
            f"{NAMESPACE}source-task-{ordinal:02d}-"
            f"{catalog['slate']['slate_id']}/producer/"
            "component-input-bundle.json"
        ),
    )
    deletion = source.build_target_or_later_deletion_proof_v1(
        source_task_ordinal=ordinal,
        target_period={
            "season": catalog["slate"]["season"],
            "week": catalog["slate"]["week"],
        },
        full_input_sha256=_digest(f"full-input-{ordinal}"),
        deleted_input_sha256=_digest(f"deleted-input-{ordinal}"),
        full_input_row_count=20,
        deleted_input_row_count=8,
        deleted_row_count=12,
        deleted_rows_sha256=_digest(f"deleted-rows-{ordinal}"),
        deleted_row_counts_by_pack={
            source.WEEKLY_STATS_PACK: 4,
            source.PFR_DEFENSE_PACK: 4,
            source.SIS_PACK: 4,
        },
        deleted_row_counts_by_slice={
            "weekly-player-stats": 4,
            "pfr-pass-rush": 1,
            "pfr-secondary": 2,
            "pfr-snap-positions": 1,
            "sis-defender-alignment": 2,
            "sis-run-context": 2,
        },
        full_output_sha256=str(input_identity["sha256"]),
        deleted_output_sha256=str(input_identity["sha256"]),
    )
    receipt = source.build_component_producer_receipt_v1(
        producer_id="r6-producer-v1",
        structural_catalog=catalog,
        catalog_identity=catalog_identity,
        catalog_release=catalog_panel["release"],
        catalog_release_identity=catalog_panel["release_identity"],
        catalog_replay_receipt_identity=catalog_replay_receipt_identity,
        accepted_candidate_release=candidate_panel["release"],
        accepted_candidate_release_identity=candidate_panel["release_identity"],
        upstream_source_release=upstream["release"],
        upstream_pack_row_objects=upstream["pack_rows"],
        upstream_source_release_identity=upstream["release_identity"],
        producer_code_identity=producer_code_identity,
        target_spine=target_spine,
        role_entries=role_entries,
        annotation_row_count=8,
        annotation_rows_sha256=bundle["annotation_rows_sha256"],
        input_bundle=bundle,
        input_bundle_identity=input_identity,
        target_or_later_deletion_proof=deletion,
        qb_depth_census=depth_census,
        admission_support_census=admission,
    )
    return {
        "catalog": catalog,
        "receipt": receipt,
        "input_bundle": bundle,
        "receipt_identity": _identity_for_body(
            f"producer-receipt-{ordinal:02d}",
            receipt,
            uri=(
                f"{NAMESPACE}source-task-{ordinal:02d}-"
                f"{catalog['slate']['slate_id']}/producer/"
                "component-producer-receipt.json"
            ),
        ),
    }


def _panel(*, failed_ordinal: int | None = None) -> dict[str, Any]:
    catalog_panel = _catalog_release()
    candidate_panel = _candidate_release(catalog_panel)
    upstream = _upstream()
    code = _code("producer-v1")
    catalog_replay_receipt_identity = _identity(
        "fixed-g0-catalog-replay-receipt"
    )
    fixtures = [
        _receipt_fixture(
            ordinal,
            catalog_panel=catalog_panel,
            candidate_panel=candidate_panel,
            upstream=upstream,
            producer_code_identity=code,
            catalog_replay_receipt_identity=(
                catalog_replay_receipt_identity
            ),
            unknown_qb_depth=ordinal == failed_ordinal,
        )
        for ordinal in range(source.TASK_COUNT)
    ]
    return {
        "catalog_panel": catalog_panel,
        "candidate_panel": candidate_panel,
        "upstream": upstream,
        "producer_code_identity": code,
        "catalog_replay_receipt_identity": catalog_replay_receipt_identity,
        "fixtures": fixtures,
        "catalogs": [fixture["catalog"] for fixture in fixtures],
        "receipts": [fixture["receipt"] for fixture in fixtures],
        "input_bundles": [fixture["input_bundle"] for fixture in fixtures],
        "receipt_identities": [
            fixture["receipt_identity"] for fixture in fixtures
        ],
    }


def _build_release(panel: Mapping[str, Any]) -> dict[str, object]:
    return source.build_producer_release_v1(
        release_id="r6-producer-release-fixture-v1",
        namespace=NAMESPACE,
        catalog_release=panel["catalog_panel"]["release"],
        catalog_release_identity=panel["catalog_panel"]["release_identity"],
        catalog_replay_receipt_identity=panel[
            "catalog_replay_receipt_identity"
        ],
        accepted_candidate_release=panel["candidate_panel"]["release"],
        accepted_candidate_release_identity=panel["candidate_panel"]["release_identity"],
        upstream_source_release=panel["upstream"]["release"],
        upstream_pack_row_objects=panel["upstream"]["pack_rows"],
        upstream_source_release_identity=panel["upstream"]["release_identity"],
        producer_code_identity=panel["producer_code_identity"],
        producer_receipts=panel["receipts"],
        producer_receipt_identities=panel["receipt_identities"],
        input_bundles=panel["input_bundles"],
        structural_catalogs=panel["catalogs"],
    )


def test_exact_registries_and_corrected_semantic_laws() -> None:
    families = source.frozen_family_registry_v1()
    assert families["registry_id"] == (
        "r6-matchup-fixed-three-family-ten-component-v1"
    )
    assert families["family_count"] == 3
    assert families["component_count"] == 10
    assert source.family_components_v1() == {
        "receiver": (
            "role_concession", "alignment_vulnerability",
            "defender_workload_quality", "shell_fit",
        ),
        "rb": ("rushing_concession", "receiving_concession", "run_context"),
        "qb": ("qb_concession", "pressure_inverted", "secondary"),
    }
    roles = source.frozen_role_registry_v2()
    assert roles["role_count"] == 12
    assert roles["component_role_count"] == 10
    components = [
        entry["component"]
        for entry in roles["roles"]
        if entry["population_role"] == "component"
    ]
    assert len(components) == len(set(components)) == 10
    assert roles["family_registry_sha256"] == families[
        "family_registry_sha256"
    ]
    laws = source.frozen_semantic_registry_v2()["laws"]
    assert laws["fp_shell_source_season"] == "target-season-minus-one-both-sides"
    assert laws["fp_alignment_weeks_1_through_4"] == "unavailable-not-zero"
    assert laws["sis_alignment_horizon"] == "common-prior-eight-target-defense-games"
    assert laws["sis_top_two_aggregation"] == "coverage-workload-weighted"
    assert laws["sis_shrink_targets"] == 16.0
    assert laws["sis_defender_rate_formula"] == (
        "(defender-dk-allowed+16.0*league-alignment-dk-per-target)/"
        "(defender-targets+16.0)"
    )
    assert laws["traded_defender_isolation"] == "target-defense-team-rows-only"
    assert laws["qb_secondary_minimum_prior_games"] == 4
    assert "postgame-participation-never-defines-peers" in laws[
        "source_game_role_peer_population"
    ]
    assert source.PRODUCER_MODULE_PATH.endswith(
        "corpus_r6_matchup_component_producer_v1.py"
    )


def test_positive_pack_rows_reject_extra_outcome_field() -> None:
    registry = source.frozen_upstream_pack_registry_v1()
    definition = registry["packs"][0]
    schema = definition["positive_row_schemas"][0]
    row = _schedule_row(0)
    row["contest_score"] = 250.0
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.build_upstream_pack_rows_v1(
            pack_id=str(definition["pack_id"]),
            slices=[{"slice_kind": schema["slice_kind"], "rows": [row]}],
        )


def test_upstream_release_requires_exact_positive_row_body() -> None:
    upstream = _upstream()
    drift = deepcopy(upstream["pack_rows"])
    drift[0]["slices"][0]["rows"][0]["home_team"] = "ZZZ"
    drift[0]["slices"][0]["rows_sha256"] = source.canonical_sha256(
        drift[0]["slices"][0]["rows"]
    )
    drift[0]["slices"][0]["row_count"] = len(
        drift[0]["slices"][0]["rows"]
    )
    drift[0]["slice_manifest_sha256"] = source.canonical_sha256(
        drift[0]["slices"]
    )
    drift[0]["rows_sha256"] = source.canonical_sha256(
        [row for item in drift[0]["slices"] for row in item["rows"]]
    )
    drift[0] = _rehash(drift[0], "pack_rows_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_upstream_release_v1(
            upstream["release"], pack_row_objects=drift
        )


def test_legacy_catalog_and_fake_historical_timestamps_fail() -> None:
    catalog = _catalog(0)
    catalog["players"][0]["name"] = "forbidden"
    catalog["source_catalog_sha256"] = source.canonical_sha256(catalog["players"])
    catalog = _rehash(catalog, "player_catalog_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_structural_catalog_v2(catalog)

    upstream = _upstream()
    definition = source.frozen_role_registry_v2()["roles"][2]
    schedule_row = _schedule_row(0)
    schedule_identity = _identity(
        "unused-target-schedule",
        raw=source.canonical_json_bytes([schedule_row]),
    )
    periods, _ = _role_periods(
        0, definition, upstream, schedule_row, schedule_identity
    )
    period = periods[1]
    period["maximum_source_event_time_utc"] = "2023-01-01T00:00:00Z"
    period = _rehash(period, "historical_source_period_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_historical_source_period_v1(
            period,
            role=str(definition["role"]),
            period_ordinal=1,
            slate=catalog_v1.expected_slate_for_source_task(0),
            upstream_source_release=upstream["release"],
            upstream_pack_row_objects=upstream["pack_rows"],
        )


def test_target_spine_uses_unordered_pair_not_opaque_catalog_game_id() -> None:
    catalog_panel = _catalog_release()
    upstream = _upstream()
    catalog = catalog_panel["catalogs"][0]
    game = _schedule_row(0)
    identity = _identity(
        "target-schedule-pair",
        raw=source.canonical_json_bytes([game]),
    )
    spine = source.build_target_spine_v1(
        structural_catalog=catalog,
        catalog_identity=catalog_panel["catalog_identities"][0],
        upstream_source_release=upstream["release"],
        upstream_pack_row_objects=upstream["pack_rows"],
        schedule_slice_identity=identity,
        games=[game],
    )
    assert game["game_id"] != catalog["players"][0]["game_id"]
    assert spine["canonical_game_keys"] == ["AAA|BBB"]

    swapped = deepcopy(game)
    swapped["away_team"] = "CCC"
    swapped_identity = _identity(
        "target-schedule-swapped",
        raw=source.canonical_json_bytes([swapped]),
    )
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.build_target_spine_v1(
            structural_catalog=catalog,
            catalog_identity=catalog_panel["catalog_identities"][0],
            upstream_source_release=upstream["release"],
            upstream_pack_row_objects=upstream["pack_rows"],
            schedule_slice_identity=swapped_identity,
            games=[swapped],
        )


def test_target_spine_rejects_fake_kickoff_and_unfrozen_schedule_row() -> None:
    catalog_panel = _catalog_release()
    upstream = _upstream()
    game = _schedule_row(0)
    game["kickoff_time_utc"] = "2023-09-03T00:00:00Z"
    identity = _identity(
        "fake-kickoff", raw=source.canonical_json_bytes([game])
    )
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.build_target_spine_v1(
            structural_catalog=catalog_panel["catalogs"][0],
            catalog_identity=catalog_panel["catalog_identities"][0],
            upstream_source_release=upstream["release"],
            upstream_pack_row_objects=upstream["pack_rows"],
            schedule_slice_identity=identity,
            games=[game],
        )


def test_candidate_release_exact_binds_rosters_and_catalog() -> None:
    catalogs = _catalog_release()
    candidates = _candidate_release(catalogs)
    assert source.validate_accepted_candidate_release_v1(
        candidates["release"]
    ) == candidates["release"]
    swapped = deepcopy(candidates["release"])
    swapped["entries"][0]["candidate_artifact_identity"] = swapped["entries"][1][
        "candidate_artifact_identity"
    ]
    swapped["entries"][0]["accepted_candidate_release_entry_sha256"] = (
        source.canonical_sha256({
            key: value
            for key, value in swapped["entries"][0].items()
            if key != "accepted_candidate_release_entry_sha256"
        })
    )
    swapped["entry_manifest_sha256"] = source.canonical_sha256(swapped["entries"])
    swapped = _rehash(swapped, "accepted_candidate_release_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_accepted_candidate_release_v1(swapped)


def test_support_census_computes_true_intersection_not_marginal_minimum() -> None:
    catalogs = _catalog_release()
    candidates = _candidate_release(catalogs)
    catalog = catalogs["catalogs"][0]
    binding = source.build_candidate_support_binding_v1(
        source_task_ordinal=0,
        catalog_identity=catalogs["catalog_identities"][0],
        accepted_candidate_release=candidates["release"],
        accepted_candidate_release_identity=candidates["release_identity"],
    )
    qb_id = str(catalog["players"][0]["id"])
    rows = []
    for index, candidate_id in enumerate(candidates["candidate_ids"][0]):
        rows.append({
            "candidate_id": candidate_id,
            "qb_player_id": qb_id,
            "qb_depth_true": index < 80,
            "supported_matchup_player_count": 8,
            "annotation_completeness": 1.0 if index >= 20 else 0.0,
        })
    support = source.build_candidate_support_rows_v1(
        candidate_support_binding=binding,
        structural_catalog=catalog,
        accepted_candidate_release=candidates["release"],
        accepted_candidate_release_identity=candidates["release_identity"],
        rows=rows,
    )
    census = source.build_admission_support_census_v1(
        candidate_support_binding=binding,
        structural_catalog=catalog,
        accepted_candidate_release=candidates["release"],
        accepted_candidate_release_identity=candidates["release_identity"],
        candidate_support_rows=rows,
        candidate_support_rows_identity=_identity_for_body(
            "intersection-support", support
        ),
    )
    assert census["qb_depth_true_candidate_count"] == 80
    assert census["completeness_distribution"]["ge_half"] == 80
    assert census["qualifying_candidate_count"] == 60
    assert census["entry_budget_satisfied"] is False


def test_all_false_depth_cannot_be_claimed_true_by_candidate_rows() -> None:
    panel = _panel(failed_ordinal=0)
    receipt = deepcopy(panel["receipts"][0])
    rows = receipt["admission_support_census"]["candidate_support_rows"]["rows"]
    for row in rows:
        row["qb_depth_true"] = True
    support = source.build_candidate_support_rows_v1(
        candidate_support_binding=receipt["admission_support_census"][
            "candidate_support_binding"
        ],
        structural_catalog=panel["catalogs"][0],
        accepted_candidate_release=panel["candidate_panel"]["release"],
        accepted_candidate_release_identity=panel["candidate_panel"]["release_identity"],
        rows=rows,
    )
    receipt["admission_support_census"] = source.build_admission_support_census_v1(
        candidate_support_binding=receipt["admission_support_census"][
            "candidate_support_binding"
        ],
        structural_catalog=panel["catalogs"][0],
        accepted_candidate_release=panel["candidate_panel"]["release"],
        accepted_candidate_release_identity=panel["candidate_panel"]["release_identity"],
        candidate_support_rows=rows,
        candidate_support_rows_identity=_identity_for_body(
            "dishonest-qb-support", support
        ),
    )
    receipt = _rehash(receipt, "producer_receipt_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            receipt,
            structural_catalog=panel["catalogs"][0],
            catalog_release=panel["catalog_panel"]["release"],
            accepted_candidate_release=panel["candidate_panel"]["release"],
            upstream_source_release=panel["upstream"]["release"],
            upstream_pack_row_objects=panel["upstream"]["pack_rows"],
            input_bundle=panel["input_bundles"][0],
        )


def test_deletion_proof_must_bind_exact_input_bundle_output() -> None:
    panel = _panel()
    receipt = deepcopy(panel["receipts"][0])
    receipt["target_or_later_deletion_proof"] = (
        source.build_target_or_later_deletion_proof_v1(
            source_task_ordinal=0,
            target_period={"season": 2023, "week": 1},
            full_input_sha256=_digest("full-input-drift"),
            deleted_input_sha256=_digest("deleted-input-drift"),
            full_input_row_count=12,
            deleted_input_row_count=6,
            deleted_row_count=6,
            deleted_rows_sha256=_digest("deleted-rows-drift"),
            deleted_row_counts_by_pack={
                source.WEEKLY_STATS_PACK: 1,
                source.PFR_DEFENSE_PACK: 3,
                source.SIS_PACK: 2,
            },
            deleted_row_counts_by_slice={
                "weekly-player-stats": 1,
                "pfr-pass-rush": 1,
                "pfr-secondary": 1,
                "pfr-snap-positions": 1,
                "sis-defender-alignment": 1,
                "sis-run-context": 1,
            },
            full_output_sha256=_digest("unrelated-output"),
            deleted_output_sha256=_digest("unrelated-output"),
        )
    )
    receipt = _rehash(receipt, "producer_receipt_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            receipt,
            structural_catalog=panel["catalogs"][0],
            catalog_release=panel["catalog_panel"]["release"],
            accepted_candidate_release=panel["candidate_panel"]["release"],
            upstream_source_release=panel["upstream"]["release"],
            upstream_pack_row_objects=panel["upstream"]["pack_rows"],
            input_bundle=panel["input_bundles"][0],
        )


def test_receipt_authority_claim_fails_even_when_rehashed() -> None:
    panel = _panel()
    claimed = deepcopy(panel["receipts"][0])
    claimed["scoring_authority"] = True
    claimed = _rehash(claimed, "producer_receipt_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            claimed,
            structural_catalog=panel["catalogs"][0],
            catalog_release=panel["catalog_panel"]["release"],
            accepted_candidate_release=panel["candidate_panel"]["release"],
            upstream_source_release=panel["upstream"]["release"],
            upstream_pack_row_objects=panel["upstream"]["pack_rows"],
            input_bundle=panel["input_bundles"][0],
        )


def _receipt_rebound_to_bundle(
    receipt: Mapping[str, object],
    bundle: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    bundle_identity = _identity_for_body(label, bundle)
    changed = deepcopy(dict(receipt))
    changed["input_bundle_identity"] = bundle_identity
    changed["input_bundle_sha256"] = bundle_identity["sha256"]
    proof = deepcopy(changed["target_or_later_deletion_proof"])
    proof["full_output_sha256"] = bundle_identity["sha256"]
    proof["deleted_output_sha256"] = bundle_identity["sha256"]
    changed["target_or_later_deletion_proof"] = _rehash(
        proof, "deletion_proof_sha256"
    )
    return _rehash(changed, "producer_receipt_sha256")


def test_receipt_exact_binds_bundle_producer_and_source_slice_bodies() -> None:
    panel = _panel()
    producer_drift = deepcopy(panel["input_bundles"][0])
    producer_drift["producer_id"] = "alternate-producer"
    producer_drift = _rehash(producer_drift, "input_bundle_sha256")
    producer_receipt = _receipt_rebound_to_bundle(
        panel["receipts"][0], producer_drift, label="producer-drift-bundle"
    )
    common = {
        "structural_catalog": panel["catalogs"][0],
        "catalog_release": panel["catalog_panel"]["release"],
        "accepted_candidate_release": panel["candidate_panel"]["release"],
        "upstream_source_release": panel["upstream"]["release"],
        "upstream_pack_row_objects": panel["upstream"]["pack_rows"],
    }
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            producer_receipt,
            input_bundle=producer_drift,
            **common,
        )

    slice_drift = deepcopy(panel["input_bundles"][0])
    first_slice = slice_drift["source_slices"][0]
    first_slice["rows"] = []
    first_slice["row_count"] = 0
    first_slice["rows_sha256"] = source.canonical_sha256([])
    first_slice["exact_slice_identity"] = _identity(
        "empty-source-slice", raw=source.canonical_json_bytes([])
    )
    slice_drift["source_slice_manifest_sha256"] = source.canonical_sha256(
        slice_drift["source_slices"]
    )
    slice_drift = _rehash(slice_drift, "input_bundle_sha256")
    slice_receipt = _receipt_rebound_to_bundle(
        panel["receipts"][0], slice_drift, label="slice-drift-bundle"
    )
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            slice_receipt,
            input_bundle=slice_drift,
            **common,
        )

    outcome_drift = deepcopy(panel["input_bundles"][0])
    outcome_drift["annotation_rows"][0]["realized_score"] = 250.0
    outcome_drift["annotation_rows_sha256"] = source.canonical_sha256(
        outcome_drift["annotation_rows"]
    )
    outcome_drift = _rehash(outcome_drift, "input_bundle_sha256")
    outcome_receipt = _receipt_rebound_to_bundle(
        panel["receipts"][0], outcome_drift, label="outcome-drift-bundle"
    )
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            outcome_receipt,
            input_bundle=outcome_drift,
            **common,
        )

    annotation_drift = deepcopy(panel["input_bundles"][0])
    annotation_drift["annotation_rows"][0]["matchup_edge_score"] = 0.99
    annotation_drift["semantic_output"]["annotation_rows"] = deepcopy(
        annotation_drift["annotation_rows"]
    )
    annotation_sha = source.canonical_sha256(annotation_drift["annotation_rows"])
    annotation_drift["annotation_rows_sha256"] = annotation_sha
    annotation_drift["semantic_output"]["annotation_rows_sha256"] = annotation_sha
    annotation_drift["semantic_output_sha256"] = source.canonical_sha256(
        annotation_drift["semantic_output"]
    )
    annotation_drift = _rehash(annotation_drift, "input_bundle_sha256")
    annotation_receipt = _receipt_rebound_to_bundle(
        panel["receipts"][0], annotation_drift, label="annotation-drift-bundle"
    )
    annotation_receipt["annotation_rows_sha256"] = annotation_sha
    annotation_receipt = _rehash(
        annotation_receipt, "producer_receipt_sha256"
    )
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            annotation_receipt,
            input_bundle=annotation_drift,
            **common,
        )

    reason_drift = deepcopy(panel["input_bundles"][0])
    first_annotation = reason_drift["annotation_rows"][0]
    first_component = next(iter(first_annotation["component_support"]))
    first_annotation["component_missingness_reasons"][first_component] = (
        "other_registered"
    )
    reason_drift["semantic_output"]["annotation_rows"] = deepcopy(
        reason_drift["annotation_rows"]
    )
    reason_sha = source.canonical_sha256(reason_drift["annotation_rows"])
    reason_drift["annotation_rows_sha256"] = reason_sha
    reason_drift["semantic_output"]["annotation_rows_sha256"] = reason_sha
    reason_drift["semantic_output_sha256"] = source.canonical_sha256(
        reason_drift["semantic_output"]
    )
    reason_drift = _rehash(reason_drift, "input_bundle_sha256")
    reason_receipt = _receipt_rebound_to_bundle(
        panel["receipts"][0], reason_drift, label="reason-drift-bundle"
    )
    reason_receipt["annotation_rows_sha256"] = reason_sha
    reason_receipt = _rehash(reason_receipt, "producer_receipt_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            reason_receipt,
            input_bundle=reason_drift,
            **common,
        )


def test_complete_ordered_54_release_and_support_census() -> None:
    panel = _panel()
    release = _build_release(panel)
    assert release["task_count"] == source.TASK_COUNT
    assert release["family_registry"] == source.frozen_family_registry_v1()
    assert all(
        receipt["family_registry_sha256"]
        == release["family_registry_sha256"]
        for receipt in panel["receipts"]
    )
    assert [entry["source_task_ordinal"] for entry in release["entries"]] == list(
        range(source.TASK_COUNT)
    )
    assert release["all_54_support_census"]["all_slates_passed"] is True
    assert source.validate_producer_release_v1(
        release,
        catalog_release=panel["catalog_panel"]["release"],
        accepted_candidate_release=panel["candidate_panel"]["release"],
        upstream_source_release=panel["upstream"]["release"],
        upstream_pack_row_objects=panel["upstream"]["pack_rows"],
        producer_receipts=panel["receipts"],
        input_bundles=panel["input_bundles"],
        structural_catalogs=panel["catalogs"],
        expected_catalog_release_identity=panel["catalog_panel"]["release_identity"],
        expected_catalog_replay_receipt_identity=panel[
            "catalog_replay_receipt_identity"
        ],
        expected_candidate_release_identity=panel["candidate_panel"]["release_identity"],
        expected_upstream_source_release_identity=panel["upstream"]["release_identity"],
        expected_producer_code_identity=panel["producer_code_identity"],
        expected_namespace=NAMESPACE,
    ) == release
    for field in source.FALSE_AUTHORITY_FIELDS:
        assert release[field] is False


def test_failed_support_preflight_blocks_54_release() -> None:
    panel = _panel(failed_ordinal=0)
    assert panel["receipts"][0]["support_preflight_passed"] is False
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        _build_release(panel)


def test_reordered_release_and_alternate_roots_fail_closed() -> None:
    panel = _panel()
    release = _build_release(panel)
    reordered = deepcopy(release)
    reordered["entries"][0], reordered["entries"][1] = (
        reordered["entries"][1], reordered["entries"][0]
    )
    reordered["entry_manifest_sha256"] = source.canonical_sha256(
        reordered["entries"]
    )
    reordered = _rehash(reordered, "producer_release_sha256")
    common = {
        "catalog_release": panel["catalog_panel"]["release"],
        "accepted_candidate_release": panel["candidate_panel"]["release"],
        "upstream_source_release": panel["upstream"]["release"],
        "upstream_pack_row_objects": panel["upstream"]["pack_rows"],
        "producer_receipts": panel["receipts"],
        "input_bundles": panel["input_bundles"],
        "structural_catalogs": panel["catalogs"],
        "expected_catalog_release_identity": panel["catalog_panel"]["release_identity"],
        "expected_catalog_replay_receipt_identity": panel[
            "catalog_replay_receipt_identity"
        ],
        "expected_candidate_release_identity": panel["candidate_panel"]["release_identity"],
        "expected_upstream_source_release_identity": panel["upstream"]["release_identity"],
        "expected_producer_code_identity": panel["producer_code_identity"],
        "expected_namespace": NAMESPACE,
    }
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_producer_release_v1(reordered, **common)
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_producer_release_v1(
            release,
            **{
                **common,
                "expected_candidate_release_identity": _identity_for_body(
                    "alternate-candidate-generation",
                    panel["candidate_panel"]["release"],
                    uri=f"{CANDIDATE_NAMESPACE}accepted-candidate-release.json",
                    generation_offset=1,
                ),
            },
        )


def test_catalog_release_entry_cannot_be_invented_or_swapped() -> None:
    panel = _panel()
    receipt = panel["receipts"][0]
    catalog_release = deepcopy(panel["catalog_panel"]["release"])
    catalog_release["entries"][0]["catalog_identity"] = catalog_release[
        "entries"
    ][1]["catalog_identity"]
    catalog_release["entry_manifest_sha256"] = source.canonical_sha256(
        catalog_release["entries"]
    )
    catalog_release = _rehash(catalog_release, "release_sha256")
    with pytest.raises(source.CorpusR6MatchupSourceV2Error):
        source.validate_component_producer_receipt_v1(
            receipt,
            structural_catalog=panel["catalogs"][0],
            catalog_release=catalog_release,
            accepted_candidate_release=panel["candidate_panel"]["release"],
            upstream_source_release=panel["upstream"]["release"],
            upstream_pack_row_objects=panel["upstream"]["pack_rows"],
            input_bundle=panel["input_bundles"][0],
        )
