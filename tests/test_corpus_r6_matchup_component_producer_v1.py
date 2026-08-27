from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import combinations, product
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import pytest

from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


PRODUCER_NAMESPACE = "gs://fixture-bucket/r6-producer-v1/"
CANDIDATE_NAMESPACE = "gs://fixture-bucket/r6-candidates-v1/"
CATALOG_NAMESPACE = "gs://fixture-bucket/r6-catalog-v1/"
UPSTREAM_NAMESPACE = "gs://fixture-bucket/r6-upstream-v1/"


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity_for_raw(
    *, raw: bytes, uri: str, generation_label: str,
) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(int(_digest(generation_label)[:15], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_body(
    body: object, *, uri: str, generation_label: str,
) -> dict[str, object]:
    return _identity_for_raw(
        raw=source.canonical_json_bytes(body),
        uri=uri,
        generation_label=generation_label,
    )


def _opaque_identity(label: str) -> dict[str, object]:
    raw = source.canonical_json_bytes({"fixture": label})
    return _identity_for_raw(
        raw=raw,
        uri=f"gs://fixture-bucket/opaque/{label}.json",
        generation_label=label,
    )


def _lookup(uri: str, digest: str, size: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(int(_digest(f"generation:{uri}")[:15], 16) + 1),
        "sha256": digest,
        "bytes": size,
    }


def _code(label: str, *, module_path: str) -> dict[str, str]:
    return {
        "source_commit_sha": _digest(f"commit:{label}")[:40],
        "module_path": module_path,
        "module_sha256": _digest(f"module:{label}"),
    }


def _policy(*, catalog: bool = False) -> dict[str, object]:
    fields = (
        catalog_v1.FALSE_AUTHORITY_FIELDS
        if catalog else source.FALSE_AUTHORITY_FIELDS
    )
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in fields},
    }


def _rehash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = deepcopy(dict(value))
    result.pop(field, None)
    result[field] = source.canonical_sha256(result)
    return result


def _sunday(season: int, week: int) -> datetime:
    september_first = datetime(season, 9, 1)
    first_sunday = september_first + timedelta(
        days=(6 - september_first.weekday()) % 7
    )
    return first_sunday + timedelta(weeks=week - 1)


def _schedule_row(season: int, week: int) -> dict[str, object]:
    gameday = _sunday(season, week)
    local = datetime.combine(
        gameday.date(),
        datetime.strptime("13:00", "%H:%M").time(),
        tzinfo=ZoneInfo("America/New_York"),
    )
    return {
        "away_team": "BBB",
        "game_id": f"schedule-{season}-w{week:02d}",
        "game_type": "REG",
        "gameday": gameday.strftime("%Y-%m-%d"),
        "gametime": "13:00",
        "home_team": "AAA",
        "kickoff_time_utc": local.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "season": season,
        "week": week,
    }


def _retime_schedule(
    row: Mapping[str, object], *, gameday: str, gametime: str = "13:00",
) -> dict[str, object]:
    result = dict(row)
    local = datetime.combine(
        datetime.strptime(gameday, "%Y-%m-%d").date(),
        datetime.strptime(gametime, "%H:%M").time(),
        tzinfo=ZoneInfo("America/New_York"),
    )
    result["gameday"] = gameday
    result["gametime"] = gametime
    result["kickoff_time_utc"] = local.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return result


PLAYERS: tuple[tuple[str, str], ...] = (
    ("p01", "QB"),
    ("p02", "QB"),
    ("p03", "RB"),
    ("p04", "RB"),
    ("p05", "RB"),
    ("p06", "RB"),
    ("p07", "RB"),
    ("p08", "WR"),
    ("p09", "WR"),
    ("p10", "WR"),
    ("p11", "WR"),
    ("p12", "WR"),
    ("p13", "WR"),
    ("p14", "WR"),
    ("p15", "WR"),
    ("p16", "TE"),
    ("p17", "TE"),
    ("p18", "TE"),
    ("p19", "DST"),
    ("p20", "DST"),
)


def _catalog(ordinal: int) -> dict[str, object]:
    slate = catalog_v1.expected_slate_for_source_task(ordinal)
    lane = catalog_v1.expected_lane_for_source_task(ordinal)
    players = [
        {
            "id": player_id,
            "pos": position,
            "team": "BBB" if position == "DST" else "AAA",
            "opp": "AAA" if position == "DST" else "BBB",
            "game_id": f"opaque-{slate['season']}-w{slate['week']:02d}",
            "salary": 6500 - index * 200,
        }
        for index, (player_id, position) in enumerate(PLAYERS, start=1)
    ]
    player_ids = [str(player["id"]) for player in players]
    body: dict[str, object] = {
        "schema_version": catalog_v1.PLAYER_CATALOG_SCHEMA,
        "task_id": catalog_v1.task_id_for_source_task(ordinal),
        "slate": slate,
        "task_ordinal": lane["task_ordinal"],
        "source_task_ordinal": ordinal,
        "universe_scope": catalog_v1.UNIVERSE_SCOPE,
        "authority_boundary": catalog_v1.AUTHORITY_BOUNDARY,
        "source_authority": _opaque_identity(f"catalog-authority-{ordinal:02d}"),
        "players": players,
        "player_count": len(players),
        "ordered_player_ids_sha256": source.canonical_sha256(player_ids),
        "source_catalog_sha256": source.canonical_sha256(players),
        **_policy(catalog=True),
    }
    return _rehash(body, "player_catalog_sha256")


def _catalog_panel() -> dict[str, Any]:
    catalogs = [_catalog(ordinal) for ordinal in range(source.TASK_COUNT)]
    entries: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for ordinal, catalog in enumerate(catalogs):
        slate_id = str(catalog["slate"]["slate_id"])
        prefix = f"{CATALOG_NAMESPACE}tasks/{ordinal:04d}-{slate_id}/"
        identity = _identity_for_body(
            catalog,
            uri=f"{prefix}player-catalog.json",
            generation_label=f"catalog-{ordinal:02d}",
        )
        identities.append(identity)
        lane = catalog_v1.expected_lane_for_source_task(ordinal)
        entries.append({
            "source_task_ordinal": ordinal,
            "task_id": catalog["task_id"],
            "slate": catalog["slate"],
            "lane_id": lane["lane_id"],
            "lane_ordinal": lane["lane_ordinal"],
            "task_ordinal": lane["task_ordinal"],
            "accepted_slate_membership_sha256": _digest(
                f"membership-{ordinal}"
            ),
            "source_task_authority_sha256": _digest(
                f"source-authority-{ordinal}"
            ),
            "catalog_identity": identity,
            "derivation_receipt_identity": _identity_for_body(
                {"fixture": f"catalog-derivation-{ordinal:02d}"},
                uri=f"{prefix}catalog-derivation-receipt.json",
                generation_label=f"catalog-derivation-{ordinal:02d}",
            ),
            "source_catalog_sha256": catalog["source_catalog_sha256"],
            "player_count": catalog["player_count"],
            "ordered_player_ids_sha256": catalog[
                "ordered_player_ids_sha256"
            ],
        })
    body: dict[str, object] = {
        "schema_version": catalog_v1.RELEASE_SCHEMA,
        "release_id": "r6-catalog-producer-fixture-v1",
        "publication_mode": "create_once",
        "universe_scope": catalog_v1.UNIVERSE_SCOPE,
        "authority_boundary": catalog_v1.AUTHORITY_BOUNDARY,
        "catalog_namespace": CATALOG_NAMESPACE,
        "tracked_root_binding": {
            "g0_authority_lock_schema": catalog_v1.G0_AUTHORITY_LOCK_SCHEMA,
            "g0_authority_lock_relative_path": "reports/fixed-g0.json",
            "g0_authority_lock_file_sha256": _digest("g0-file"),
            "g0_authority_lock_sha256": _digest("g0-internal"),
            "source_commit_sha": _digest("g0-commit")[:40],
            "panel_object_identity": _opaque_identity("g0-panel"),
            "panel_index_sha256": _digest("g0-panel-index"),
            "accepted_slate_count": source.TASK_COUNT,
        },
        "later_source_freeze_identity": _opaque_identity("later-source"),
        "later_source_freeze_manifest_sha256": _digest("later-source-body"),
        "artifact_source_authority_completion_identity": _opaque_identity(
            "source-completion"
        ),
        "artifact_source_authority_completion_sha256": _digest(
            "source-completion-body"
        ),
        "derivation_code_identity": _code(
            "catalog-adapter",
            module_path=(
                "src/nfl_dfs/research/"
                "corpus_r6_player_catalog_fixed_g0_adapter_v1.py"
            ),
        ),
        "task_count": source.TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": source.canonical_sha256(entries),
        **_policy(catalog=True),
    }
    release = _rehash(body, "release_sha256")
    release_identity = _identity_for_body(
        release,
        uri=f"{CATALOG_NAMESPACE}catalog-release.json",
        generation_label="catalog-release",
    )
    return {
        "catalogs": catalogs,
        "catalog_identities": identities,
        "release": release,
        "release_identity": release_identity,
    }


def _fixed_g0_replay(catalog_panel: Mapping[str, Any]) -> dict[str, Any]:
    release = catalog_panel["release"]
    body: dict[str, object] = {
        "schema_version": producer.FIXED_G0_REPLAY_SCHEMA,
        "replay_id": "fixed-g0-r6-player-catalog-projection-v1",
        "replay_scope": (
            "accepted-panel-index-projection-rooted-in-frozen-g0-evidence"
        ),
        "pin_set_sha256": _digest("fixed-g0-pin-set"),
        "tracked_root_binding": release["tracked_root_binding"],
        "official_publication_receipt_file": {
            "relative_path": "reports/fixed-g0-publication.json",
            "sha256": _digest("fixed-g0-publication-file"),
            "bytes": 100,
        },
        "official_publication_receipt_sha256": _digest(
            "fixed-g0-publication-receipt"
        ),
        "adapter_review_binding": {
            "relative_path": "reports/fixed-g0-adapter-review.json",
            "sha256": _digest("fixed-g0-adapter-review"),
            "bytes": 100,
        },
        "lane_terminal_identities": [
            _opaque_identity("lane-a-terminal"),
            _opaque_identity("lane-b-terminal"),
        ],
        "lane_completion_identities": [
            _opaque_identity("lane-a-completion"),
            _opaque_identity("lane-b-completion"),
        ],
        "later_source_freeze_identity": release[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_manifest_sha256": release[
            "later_source_freeze_manifest_sha256"
        ],
        "artifact_source_authority_completion_identity": release[
            "artifact_source_authority_completion_identity"
        ],
        "artifact_source_authority_completion_sha256": release[
            "artifact_source_authority_completion_sha256"
        ],
        "derivation_code_identity": release["derivation_code_identity"],
        "catalog_namespace": release["catalog_namespace"],
        "catalog_release_identity": catalog_panel["release_identity"],
        "catalog_release_sha256": release["release_sha256"],
        "task_count": source.TASK_COUNT,
        "task_acceptance_body_count": source.TASK_COUNT,
        "task_acceptance_body_manifest_sha256": _digest(
            "fixed-g0-task-acceptances"
        ),
        "carrier_body_count": source.TASK_COUNT,
        "carrier_body_manifest_sha256": _digest("fixed-g0-carriers"),
        "member_binding_manifest_sha256": _digest("fixed-g0-members"),
        "source_catalog_binding_manifest_sha256": _digest(
            "fixed-g0-source-catalogs"
        ),
        "completion_binding_manifest_sha256": _digest(
            "fixed-g0-completions"
        ),
        "structural_catalog_manifest_sha256": _digest(
            "fixed-g0-structural-catalogs"
        ),
        "catalog_identity_manifest_sha256": source.canonical_sha256([
            entry["catalog_identity"] for entry in release["entries"]
        ]),
        "accepted_panel_index_projection_only": True,
        "fresh_task_or_arm_body_revalidation_performed": True,
        "task_acceptance_bodies_reopened": True,
        "carrier_bodies_reopened": True,
        "source_completion_artifact_bodies_reopened": False,
        "world_matrix_bodies_reopened": False,
        "result_object_bodies_reopened": False,
        "execution_manifest_pin_required": True,
        "self_authorizing": False,
        **_policy(catalog=True),
        "analytical_authority": False,
        "automatic_retry_licensed": False,
    }
    receipt = _rehash(body, "replay_receipt_sha256")
    identity = _identity_for_body(
        receipt,
        uri=f"{CATALOG_NAMESPACE}fixed-g0-replay-receipt.json",
        generation_label="fixed-g0-replay",
    )
    return {"receipt": receipt, "identity": identity}


def _weekly_rows(schedule_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for game in schedule_rows:
        for index, (player_id, position) in enumerate(
            (item for item in PLAYERS if item[1] != "DST"), start=1
        ):
            rows.append({
                "air_yards_share": 0.05 * index,
                "carries": 12 + index if position == "RB" else 0,
                "fumbles_lost_total": 0,
                "opponent_team": "BBB",
                "passing_interceptions": 1 if position == "QB" else 0,
                "passing_tds": 2 if position == "QB" else 0,
                "passing_yards": 260 if position == "QB" else 0,
                "player_id": player_id,
                "position": position,
                "receiving_tds": 1 if position in {"RB", "WR", "TE"} else 0,
                "receiving_yards": 35 + index * 4,
                "receptions": 3 + index % 3,
                "rushing_tds": 1 if position == "RB" else 0,
                "rushing_yards": 45 + index if position == "RB" else 0,
                "season": game["season"],
                "target_share": 0.05 + index * 0.02,
                "targets": 4 + index,
                "team": "AAA",
                "week": game["week"],
            })
    return rows


def _legacy_depth_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    position_rank: dict[str, int] = {}
    for season in (2022, 2023, 2024):
        for week in range(1, 19):
            position_rank.clear()
            for index, (player_id, position) in enumerate(
                (item for item in PLAYERS if item[1] != "DST"), start=1
            ):
                position_rank[position] = position_rank.get(position, 0) + 1
                rows.append({
                    "club_code": "AAA",
                    "depth_position": position,
                    "depth_team": position_rank[position],
                    "formation": "Offense",
                    "gsis_id": player_id,
                    "jersey_number": index,
                    "position": position,
                    "season": season,
                    "week": week,
                })
    return rows


def _snapshot_depth_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for week in range(1, 19):
        position_rank: dict[str, int] = {}
        snapshot_day = (_sunday(2025, week) - timedelta(days=1)).date()
        for player_id, position in PLAYERS:
            if position == "DST":
                continue
            position_rank[position] = position_rank.get(position, 0) + 1
            rows.append({
                "dt": snapshot_day.strftime("%Y-%m-%d"),
                "gsis_id": player_id,
                "pos_abb": position,
                "pos_rank": position_rank[position],
                "team": "AAA",
            })
    return rows


def _pfr_slices(
    schedule_rows: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    pressure: list[dict[str, object]] = []
    secondary: list[dict[str, object]] = []
    positions: list[dict[str, object]] = []
    for game in schedule_rows:
        pressure.append({
            "def_pressures": 8,
            "def_sacks": 2,
            "def_times_blitzed": 12,
            "def_times_hurried": 4,
            "game_id": game["game_id"],
            "pfr_player_id": "d01",
            "season": game["season"],
            "team": "BBB",
            "week": game["week"],
        })
        for index, defender in enumerate(("d01", "d02"), start=1):
            secondary.append({
                "def_completions_allowed": 3 + index,
                "def_targets": 5 + index,
                "def_yards_allowed": 45 + index * 5,
                "game_id": game["game_id"],
                "pfr_player_id": defender,
                "season": game["season"],
                "team": "BBB",
                "week": game["week"],
            })
            positions.append({
                "defense_snaps": 55 + index,
                "game_id": game["game_id"],
                "pfr_player_id": defender,
                "position": "CB",
                "season": game["season"],
                "team": "BBB",
                "week": game["week"],
            })
    return {
        "pfr-pass-rush": pressure,
        "pfr-secondary": secondary,
        "pfr-snap-positions": positions,
    }


def _fp_slices() -> dict[str, list[dict[str, object]]]:
    routes: list[dict[str, object]] = []
    alignments: list[dict[str, object]] = []
    shells: list[dict[str, object]] = []
    defense_shells: list[dict[str, object]] = []
    skill = [item for item in PLAYERS if item[1] in {"RB", "WR", "TE"}]
    receivers = [item for item in PLAYERS if item[1] in {"WR", "TE"}]
    for season in range(2022, 2026):
        for week in range(1, 19):
            for index, (player_id, _) in enumerate(skill, start=1):
                routes.append({
                    "gsis_id": player_id,
                    "route_share": 0.10 + index * 0.04,
                    "season": season,
                    "source_sha256": _digest(f"route-{season}-{week}"),
                    "week": week,
                })
            if week >= 5:
                for index, (player_id, _) in enumerate(receivers, start=1):
                    alignments.append({
                        "alignment_supported": True,
                        "gsis_id": player_id,
                        "player_wide_share": 0.20 + index * 0.05,
                        "season": season,
                        "source_sha256": _digest(
                            f"alignment-{season}-{week}-{player_id}"
                        ),
                        "split_duplicate": False,
                        "target_week": week,
                    })
        for index, (player_id, _) in enumerate(receivers, start=1):
            shells.append({
                "gsis_id": player_id,
                "man_fprr": 1.5 + index * 0.1,
                "season": season,
                "source_sha256": _digest(f"shell-{season}-{player_id}"),
                "split_duplicate": False,
                "zone_fprr": 1.1 + index * 0.05,
            })
        defense_shells.append({
            "def_man_rate": 0.55,
            "season": season,
            "source_sha256": _digest(f"def-shell-{season}"),
            "team": "BBB",
        })
    return {
        "fp-route-share": routes,
        "fp-alignment": alignments,
        "fp-receiver-shell": shells,
        "fp-defense-shell": defense_shells,
    }


def _sis_slices(
    schedule_rows: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    defender: list[dict[str, object]] = []
    run: list[dict[str, object]] = []
    for game in schedule_rows:
        for alignment in ("wide", "slot"):
            for index, defender_id in enumerate(("d01", "d02"), start=1):
                defender.append({
                    "alignment": alignment,
                    "completions": 3 + index,
                    "coverage_snaps": 28 + index,
                    "defense": "BBB",
                    "defender_name": f"Defender {index}",
                    "defender_player_id": defender_id,
                    "season": game["season"],
                    "targets": 5 + index,
                    "touchdowns": 0,
                    "week": game["week"],
                    "yards": 45 + index * 4,
                })
        run.append({
            "rdef_attempts": 25,
            "rdef_boom_rate": 0.12,
            "rdef_bust_rate": 0.18,
            "rdef_epa_per_attempt": -0.04,
            "rdef_stuffs": 4,
            "rdef_yards_after_contact": 70,
            "season": game["season"],
            "team": "BBB",
            "week": game["week"],
        })
    return {"sis-defender-alignment": defender, "sis-run-context": run}


def _upstream() -> dict[str, Any]:
    schedule_rows = [
        _schedule_row(season, week)
        for season in range(2022, 2026)
        for week in range(1, 19)
    ]
    rows_by_slice: dict[str, list[dict[str, object]]] = {
        "schedule-games": schedule_rows,
        "weekly-player-stats": _weekly_rows(schedule_rows),
        "legacy-depth": _legacy_depth_rows(),
        "snapshot-depth": _snapshot_depth_rows(),
        **_pfr_slices(schedule_rows),
        **_fp_slices(),
        **_sis_slices(schedule_rows),
    }
    registry = source.frozen_upstream_pack_registry_v1()
    pack_rows: list[dict[str, object]] = []
    packs: list[dict[str, object]] = []
    for registry_entry in registry["packs"]:
        pack_id = str(registry_entry["pack_id"])
        slices = [
            {
                "slice_kind": schema["slice_kind"],
                "rows": rows_by_slice[str(schema["slice_kind"])],
            }
            for schema in registry_entry["positive_row_schemas"]
        ]
        rows_object = source.build_upstream_pack_rows_v1(
            pack_id=pack_id, slices=slices
        )
        pack_rows.append(rows_object)
        rows_identity = _identity_for_body(
            rows_object,
            uri=f"{UPSTREAM_NAMESPACE}packs/{pack_id}/rows.json",
            generation_label=f"upstream-rows-{pack_id}",
        )
        warehouse = registry_entry["provenance_kind"] == "warehouse-query-receipt"
        packs.append({
            "pack_id": pack_id,
            "source_kind": registry_entry["source_kind"],
            "provenance_kind": registry_entry["provenance_kind"],
            "positive_row_schemas": registry_entry["positive_row_schemas"],
            "positive_row_schema_manifest_sha256": registry_entry[
                "positive_row_schema_manifest_sha256"
            ],
            "exact_rows_identity": rows_identity,
            "row_count": rows_object["row_count"],
            "rows_sha256": rows_object["rows_sha256"],
            "source_period_min": registry_entry["source_period_min"],
            "source_period_max": registry_entry["source_period_max"],
            "warehouse_query_receipt_identity": (
                _opaque_identity(f"query-{pack_id}") if warehouse else None
            ),
            "frozen_artifact_manifest_identities": (
                [] if warehouse else [_opaque_identity(f"manifest-{pack_id}")]
            ),
            "projection_code_identity": _code(
                f"projection-{pack_id}",
                module_path="src/nfl_dfs/research/source_projection_v1.py",
            ),
        })
    release = source.build_upstream_release_v1(
        release_id="r6-upstream-producer-fixture-v1",
        namespace=UPSTREAM_NAMESPACE,
        fixed_source_root_identity=_opaque_identity("fixed-upstream-root"),
        packs=packs,
        pack_row_objects=pack_rows,
    )
    return {
        "release": release,
        "release_identity": _identity_for_body(
            release,
            uri=f"{UPSTREAM_NAMESPACE}upstream-release.json",
            generation_label="upstream-release",
        ),
        "pack_rows": pack_rows,
    }


def _candidate_rosters() -> list[dict[str, object]]:
    by_position = {
        position: [player_id for player_id, pos in PLAYERS if pos == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    lineups = [
        [qb, *rbs, *wrs, *tes, dst]
        for qb, rbs, wrs, tes, dst in product(
            by_position["QB"],
            combinations(by_position["RB"], 2),
            combinations(by_position["WR"], 3),
            combinations(by_position["TE"], 2),
            by_position["DST"],
        )
    ][:source.ENTRY_BUDGET]
    assert len(lineups) == source.ENTRY_BUDGET
    return [
        {
            "source_task_ordinal": ordinal,
            "rows": [
                {
                    "candidate_id": f"candidate-{ordinal:02d}-{index:03d}",
                    "player_ids": player_ids,
                }
                for index, player_ids in enumerate(lineups)
            ],
        }
        for ordinal in range(source.TASK_COUNT)
    ]


def _candidate_panel(catalog_panel: Mapping[str, Any]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for task in _candidate_rosters():
        ordinal = int(task["source_task_ordinal"])
        catalog = catalog_panel["catalogs"][ordinal]
        artifact = source.build_accepted_candidate_artifact_v1(
            source_task_ordinal=ordinal,
            rows=task["rows"],
        )
        artifact_identity = _identity_for_body(
            artifact,
            uri=(
                f"{CANDIDATE_NAMESPACE}source-task-{ordinal:02d}-"
                f"{catalog['slate']['slate_id']}/accepted-candidates.json"
            ),
            generation_label=f"accepted-candidates-{ordinal:02d}",
        )
        entry: dict[str, object] = {
            "source_task_ordinal": ordinal,
            "task_id": catalog["task_id"],
            "slate": catalog["slate"],
            "catalog_identity": catalog_panel["catalog_identities"][ordinal],
            "candidate_artifact": artifact,
            "candidate_artifact_identity": artifact_identity,
            "candidate_count": artifact["candidate_count"],
            "ordered_candidate_ids_sha256": artifact[
                "ordered_candidate_ids_sha256"
            ],
        }
        entry["accepted_candidate_release_entry_sha256"] = (
            source.canonical_sha256(entry)
        )
        entries.append(entry)
    release = source.build_accepted_candidate_release_v1(
        release_id="r6-accepted-candidates-v1",
        namespace=CANDIDATE_NAMESPACE,
        source_candidate_panel_identity=_opaque_identity(
            "accepted-v12-candidate-panel"
        ),
        entries=entries,
    )
    return {
        "release": release,
        "identity": _identity_for_body(
            release,
            uri=f"{CANDIDATE_NAMESPACE}accepted-candidate-release.json",
            generation_label="accepted-candidate-release",
        ),
    }


@pytest.fixture(scope="module")
def full_fixture() -> dict[str, Any]:
    catalogs = _catalog_panel()
    replay = _fixed_g0_replay(catalogs)
    upstream = _upstream()
    candidates = _candidate_panel(catalogs)
    return {
        "catalogs": catalogs,
        "replay": replay,
        "upstream": upstream,
        "candidates": candidates,
        "producer_code_identity": _code(
            "component-producer",
            module_path=source.PRODUCER_MODULE_PATH,
        ),
    }


def _produce(fixture: Mapping[str, Any]) -> dict[str, object]:
    return producer.produce_all_54_component_panel_v1(
        producer_id="r6-matchup-component-producer-v1",
        producer_release_id="r6-matchup-producer-release-v1",
        producer_namespace=PRODUCER_NAMESPACE,
        fixed_g0_replay_receipt=fixture["replay"]["receipt"],
        fixed_g0_replay_receipt_identity=fixture["replay"]["identity"],
        catalog_release=fixture["catalogs"]["release"],
        catalog_release_identity=fixture["catalogs"]["release_identity"],
        structural_catalogs=fixture["catalogs"]["catalogs"],
        accepted_candidate_release=fixture["candidates"]["release"],
        accepted_candidate_release_identity=fixture["candidates"]["identity"],
        upstream_source_release=fixture["upstream"]["release"],
        upstream_source_release_identity=fixture["upstream"]["release_identity"],
        upstream_pack_row_objects=fixture["upstream"]["pack_rows"],
        producer_code_identity=fixture["producer_code_identity"],
        identity_lookup=_lookup,
    )


def test_full_54_producer_emits_body_bound_bundles_and_support(
    full_fixture: Mapping[str, Any],
) -> None:
    result = _produce(full_fixture)
    assert result["task_count"] == source.TASK_COUNT
    assert [entry["source_task_ordinal"] for entry in result["entries"]] == list(
        range(source.TASK_COUNT)
    )
    assert result["all_54_support_census"]["all_slates_passed"] is True
    assert result["producer_release"]["task_count"] == source.TASK_COUNT
    family_registry = source.frozen_family_registry_v1()
    assert producer.FAMILY_COMPONENTS == source.family_components_v1()
    assert result["family_registry"] == family_registry
    assert result["producer_release"]["family_registry"] == family_registry
    assert result["input_bundle_identity_manifest_sha256"] == (
        source.canonical_sha256(result["input_bundle_identities"])
    )
    assert result["producer_receipt_identity_manifest_sha256"] == (
        source.canonical_sha256(result["producer_receipt_identities"])
    )
    assert all(
        entry["support_preflight_passed"] is True
        and entry["qualifying_candidate_count"] >= source.ENTRY_BUDGET
        for entry in result["entries"]
    )
    for bundle, receipt in zip(
        result["input_bundles"], result["producer_receipts"], strict=True
    ):
        assert receipt["input_bundle_identity"]["sha256"] == sha256(
            source.canonical_json_bytes(bundle)
        ).hexdigest()
        assert bundle["family_registry_sha256"] == family_registry[
            "family_registry_sha256"
        ]
        assert receipt["family_registry_sha256"] == family_registry[
            "family_registry_sha256"
        ]
        lock = str(bundle["lock_time_utc"])
        for source_slice in bundle["source_slices"]:
            period = next(
                role["source_periods"][source_slice["period_ordinal"]]
                for role in bundle["role_entries"]
                if role["role"] == source_slice["role"]
            )
            kickoffs = source_slice["row_event_kickoff_times_utc"]
            assert len(kickoffs) == source_slice["row_count"]
            assert source_slice["row_event_kickoff_manifest_sha256"] == (
                source.canonical_sha256(kickoffs)
            )
            if period["period_kind"] == "prior-game-window" and (
                source_slice["slice_kind"] in {
                    "schedule-games", "weekly-player-stats", "fp-route-share",
                    "pfr-pass-rush", "pfr-secondary", "pfr-snap-positions",
                    "sis-defender-alignment", "sis-run-context",
                }
            ):
                assert all(value is not None and value < lock for value in kickoffs)
        for annotation in bundle["annotation_rows"]:
            for component, supported in annotation["component_support"].items():
                reason = annotation["component_missingness_reasons"][component]
                assert (reason is None) is supported
        proof = receipt["target_or_later_deletion_proof"]
        assert proof["target_or_later_deletion_invariant"] is True
        assert proof["full_input_row_count"] - proof[
            "deleted_input_row_count"
        ] == proof["deleted_row_count"]
    for field in source.FALSE_AUTHORITY_FIELDS:
        assert result[field] is False


def test_actual_weekly_sis_and_pfr_target_rows_are_deleted(
    full_fixture: Mapping[str, Any],
) -> None:
    result = _produce(full_fixture)
    for receipt in result["producer_receipts"]:
        proof = receipt["target_or_later_deletion_proof"]
        assert proof["deleted_row_counts_by_pack"][source.WEEKLY_STATS_PACK] > 0
        assert proof["deleted_row_counts_by_pack"][source.SIS_PACK] > 0
        assert proof["deleted_row_counts_by_pack"][source.PFR_DEFENSE_PACK] > 0
        assert proof["full_input_sha256"] != proof["deleted_input_sha256"]
        assert proof["full_output_sha256"] == proof["deleted_output_sha256"]


def test_pack_body_drift_fails_before_any_receipt(
    full_fixture: Mapping[str, Any],
) -> None:
    changed = deepcopy(full_fixture)
    changed["upstream"]["pack_rows"][1]["slices"][0]["rows"][0][
        "passing_yards"
    ] = 999
    with pytest.raises((
        source.CorpusR6MatchupSourceV2Error,
        producer.CorpusR6MatchupComponentProducerV1Error,
    )):
        _produce(changed)


def test_fixed_g0_catalog_release_body_drift_fails(
    full_fixture: Mapping[str, Any],
) -> None:
    changed = deepcopy(full_fixture)
    changed["catalogs"]["release"]["entries"][0]["player_count"] += 1
    with pytest.raises((
        source.CorpusR6MatchupSourceV2Error,
        producer.CorpusR6MatchupComponentProducerV1Error,
        catalog_v1.CorpusR6PlayerCatalogV1Error,
    )):
        _produce(changed)


def test_fixed_g0_replay_requires_the_complete_adapter_receipt(
    full_fixture: Mapping[str, Any],
) -> None:
    changed = deepcopy(full_fixture)
    receipt = changed["replay"]["receipt"]
    del receipt["carrier_body_manifest_sha256"]
    receipt = _rehash(receipt, "replay_receipt_sha256")
    changed["replay"]["receipt"] = receipt
    changed["replay"]["identity"] = _identity_for_body(
        receipt,
        uri=f"{CATALOG_NAMESPACE}fixed-g0-replay-receipt.json",
        generation_label="fixed-g0-replay-incomplete",
    )
    with pytest.raises(producer.CorpusR6MatchupComponentProducerV1Error):
        _produce(changed)


def test_pfr_game_id_must_match_exact_schedule(
    full_fixture: Mapping[str, Any],
) -> None:
    slices = producer._pack_slices(full_fixture["upstream"]["pack_rows"])
    slices["pfr-pass-rush"][0]["game_id"] = "wrong-game"
    with pytest.raises(producer.CorpusR6MatchupComponentProducerV1Error):
        producer._derive_semantic_slate(
            catalog=full_fixture["catalogs"]["catalogs"][0],
            slices=slices,
        )


def test_candidate_release_reorder_or_body_drift_fails(
    full_fixture: Mapping[str, Any],
) -> None:
    reordered = deepcopy(full_fixture)
    entries = reordered["candidates"]["release"]["entries"]
    entries[0], entries[1] = (
        entries[1],
        entries[0],
    )
    with pytest.raises((
        source.CorpusR6MatchupSourceV2Error,
        producer.CorpusR6MatchupComponentProducerV1Error,
    )):
        _produce(reordered)


def test_coherently_rehashed_duplicate_candidate_roster_fails(
    full_fixture: Mapping[str, Any],
) -> None:
    changed = deepcopy(full_fixture)
    release = changed["candidates"]["release"]
    entry = release["entries"][0]
    artifact = entry["candidate_artifact"]
    duplicate_ids = list(artifact["rows"][0]["player_ids"])
    artifact["rows"][1]["player_ids"] = duplicate_ids
    artifact["rows"][1]["roster_sha256"] = source.canonical_sha256(
        duplicate_ids
    )
    artifact["candidate_row_manifest_sha256"] = source.canonical_sha256(
        artifact["rows"]
    )
    artifact = _rehash(artifact, "candidate_artifact_sha256")
    entry["candidate_artifact"] = artifact
    entry["candidate_artifact_identity"] = _identity_for_body(
        artifact,
        uri=entry["candidate_artifact_identity"]["uri"],
        generation_label="duplicate-candidate-roster",
    )
    release["entries"][0] = _rehash(
        entry, "accepted_candidate_release_entry_sha256"
    )
    release["entry_manifest_sha256"] = source.canonical_sha256(
        release["entries"]
    )
    release = _rehash(release, "accepted_candidate_release_sha256")
    changed["candidates"]["release"] = release
    changed["candidates"]["identity"] = _identity_for_body(
        release,
        uri=f"{CANDIDATE_NAMESPACE}accepted-candidate-release.json",
        generation_label="duplicate-candidate-release",
    )
    with pytest.raises(producer.CorpusR6MatchupComponentProducerV1Error):
        _produce(changed)


def test_identity_lookup_cannot_substitute_generation_or_body(
    full_fixture: Mapping[str, Any],
) -> None:
    def wrong_lookup(uri: str, digest: str, size: int) -> Mapping[str, object]:
        result = _lookup(uri, digest, size)
        result["sha256"] = _digest("coherent-substitution-attempt")
        return result

    fixture = full_fixture
    with pytest.raises(producer.CorpusR6MatchupComponentProducerV1Error):
        producer.produce_all_54_component_panel_v1(
            producer_id="r6-matchup-component-producer-v1",
            producer_release_id="r6-matchup-producer-release-v1",
            producer_namespace=PRODUCER_NAMESPACE,
            fixed_g0_replay_receipt=fixture["replay"]["receipt"],
            fixed_g0_replay_receipt_identity=fixture["replay"]["identity"],
            catalog_release=fixture["catalogs"]["release"],
            catalog_release_identity=fixture["catalogs"]["release_identity"],
            structural_catalogs=fixture["catalogs"]["catalogs"],
            accepted_candidate_release=fixture["candidates"]["release"],
            accepted_candidate_release_identity=fixture["candidates"]["identity"],
            upstream_source_release=fixture["upstream"]["release"],
            upstream_source_release_identity=fixture["upstream"]["release_identity"],
            upstream_pack_row_objects=fixture["upstream"]["pack_rows"],
            producer_code_identity=fixture["producer_code_identity"],
            identity_lookup=wrong_lookup,
        )


def test_role_windows_retain_last_one_and_last_four_sensitivity_ranks() -> None:
    def candidate(
        player_id: str,
        values: list[float],
    ) -> dict[str, object]:
        history = [
            {
                "target_share": value,
                "air_yards_share": value,
                "_key": (2024 if index < 3 else 2025, 16 + index),
            }
            for index, value in enumerate(values)
        ]
        routes = [
            {"route_share": value, "_key": row["_key"]}
            for value, row in zip(values, history, strict=True)
        ]
        return {
            "player_id": player_id,
            "team": "AAA",
            "position": "WR",
            "depth_rank": None,
            "salary": 5000,
            "components": producer._role_components(
                family="receiver",
                history=history,
                route_history=routes,
                depth_rank=None,
            ),
        }

    ranked = producer._rank_role_group([
        candidate("recent", [0.0, 0.0, 0.0, 1.0]),
        candidate("stable", [0.6, 0.6, 0.6, 0.2]),
    ], family="receiver")
    recent = ranked["recent"]
    assert recent["role_component_values"]["target_share_last_one"] == 1.0
    assert recent["role_component_values"]["target_share_last_four"] == 0.25
    assert recent["role_component_observed_game_counts"] == {
        "target_share_last_one": 1,
        "route_share_last_one": 1,
        "air_yards_share_last_one": 1,
        "target_share_last_four": 4,
        "route_share_last_four": 4,
        "air_yards_share_last_four": 4,
    }
    assert recent["role_window_sensitivity"]["last_one"]["role_rank"] == 1
    assert recent["role_window_sensitivity"]["last_four"]["role_rank"] == 2
    assert ranked["stable"]["role_window_sensitivity"]["last_four"][
        "role_rank"
    ] == 1


def test_role_windows_require_complete_aligned_observation_counts() -> None:
    history = [
        {"target_share": value, "air_yards_share": value, "_key": (2023, week)}
        for week, value in enumerate((0.1, None, 0.3, 0.4), start=1)
    ]
    routes = [
        {"route_share": value, "_key": (2023, week)}
        for week, value in enumerate((0.1, 0.2, 0.3), start=1)
    ]
    values = producer._role_components(
        family="receiver",
        history=history,
        route_history=routes,
        depth_rank=1,
    )
    assert values["target_share_last_one"] == 0.4
    assert values["target_share_last_one_observed_game_count"] == 1
    assert values["target_share_last_four"] is None
    assert values["target_share_last_four_observed_game_count"] == 3
    assert values["route_share_last_four"] is None
    assert values["route_share_last_four_observed_game_count"] == 3


def test_null_dk_fields_never_become_supported_zero() -> None:
    receiving = {"receptions": 0, "receiving_yards": 0, "receiving_tds": 0}
    rushing = {"rushing_yards": 0, "rushing_tds": 0}
    quarterback = {
        "passing_yards": 0,
        "passing_tds": 0,
        "passing_interceptions": 0,
        "rushing_yards": 0,
        "rushing_tds": 0,
        "fumbles_lost_total": 0,
    }
    assert producer._receiving_dk(receiving) == 0.0
    assert producer._rushing_dk(rushing) == 0.0
    assert producer._qb_dk(quarterback) == 0.0
    receiving["receiving_yards"] = None
    rushing["rushing_yards"] = None
    quarterback["passing_yards"] = None
    assert producer._receiving_dk(receiving) is None
    assert producer._rushing_dk(rushing) is None
    assert producer._qb_dk(quarterback) is None


def test_role_concession_requires_four_complete_observed_role_games() -> None:
    schedule_rows = [
        *(_schedule_row(2022, week) for week in range(15, 19)),
        _schedule_row(2023, 1),
    ]
    schedule_games, _ = producer._schedule_indexes(schedule_rows)
    prior_keys = [(2022, week) for week in range(15, 19)]
    weekly_rows = [
        {
            "_key": key,
            "opponent_team": "BBB",
            "player_id": "source-wr1",
            "receptions": 4,
            "receiving_yards": 50,
            "receiving_tds": 0,
            "rushing_yards": 0,
            "rushing_tds": 0,
        }
        for key in prior_keys
    ]
    source_roles = {
        ("source-wr1", season, week): {
            "role_supported": True,
            "role_label": "WR1",
        }
        for season, week in prior_keys
    }
    kwargs = {
        "catalog": {
            "slate": {"season": 2023, "week": 1},
            "players": [{"id": "target-wr", "pos": "WR", "opp": "BBB"}],
        },
        "target_roles": {"target-wr": {"role_label": "WR1"}},
        "source_roles": source_roles,
        "schedule_games": schedule_games,
        "lock_time": next(
            game["_kickoff"] for game in schedule_games
            if game["_key"] == (2023, 1)
        ),
    }
    incomplete = deepcopy(weekly_rows)
    incomplete[0]["receiving_yards"] = None
    result = producer._role_concession_components(
        weekly_rows=incomplete, **kwargs
    )["target-wr"]
    assert result["role_concession"] is None
    assert result["role_concession_observed_game_count"] == 3

    complete = producer._role_concession_components(
        weekly_rows=weekly_rows, **kwargs
    )["target-wr"]
    assert complete["role_concession"] == 9.0
    assert complete["role_concession_observed_game_count"] == 4


def test_missing_weekly_sis_and_pfr_rows_remain_null_with_coverage_counts(
    full_fixture: Mapping[str, Any],
) -> None:
    slices = producer._pack_slices(full_fixture["upstream"]["pack_rows"])
    for row in slices["weekly-player-stats"]:
        if row["season"] == 2022 and row["position"] == "QB":
            row["passing_yards"] = None
    for row in slices["sis-run-context"]:
        if row["season"] == 2022:
            row["rdef_attempts"] = None
    for row in slices["pfr-pass-rush"]:
        if row["season"] == 2022:
            row["def_pressures"] = None
    for row in slices["pfr-secondary"]:
        if row["season"] == 2022:
            row["def_yards_allowed"] = None
    semantic = producer._derive_semantic_slate(
        catalog=full_fixture["catalogs"]["catalogs"][0],
        slices=slices,
    )
    qb_rows = [
        row for row in semantic["annotation_rows"] if row["family"] == "qb"
    ]
    assert qb_rows
    for row in qb_rows:
        assert row["raw_component_values"] == {
            "qb_concession": None,
            "pressure_inverted": None,
            "secondary": None,
        }
        assert row["component_observed_game_counts"] == {
            "qb_concession": 0,
            "pressure_inverted": 0,
            "secondary": 0,
        }


def test_every_schedule_kickoff_is_derived_not_trusted() -> None:
    changed = _schedule_row(2022, 1)
    changed["kickoff_time_utc"] = "2022-09-04T00:00:00Z"
    with pytest.raises(producer.CorpusR6MatchupComponentProducerV1Error):
        producer._schedule_indexes([changed])


def test_percentile_ties_and_singleton_denominators_are_deterministic() -> None:
    assert producer._percentiles({"a": 4.0}) == {"a": 0.0}
    assert producer._percentiles({"a": 1.0, "b": 1.0, "c": 2.0}) == {
        "a": 0.0, "b": 0.0, "c": 1.0,
    }


def test_et_kickoff_derivation_crosses_dst_and_year_boundary() -> None:
    summer = _schedule_row(2023, 1)
    winter = _schedule_row(2023, 18)
    summer["gameday"] = "2023-09-10"
    summer["gametime"] = "13:00"
    summer["kickoff_time_utc"] = "2023-09-10T17:00:00Z"
    winter["gameday"] = "2024-01-07"
    winter["gametime"] = "13:00"
    winter["kickoff_time_utc"] = "2024-01-07T18:00:00Z"
    games, _ = producer._schedule_indexes([summer, winter])
    assert [game["kickoff_time_utc"] for game in games] == [
        "2023-09-10T17:00:00Z", "2024-01-07T18:00:00Z",
    ]


def test_captured_prior_windows_exclude_ninth_and_seventh_games(
    full_fixture: Mapping[str, Any],
) -> None:
    catalog = full_fixture["catalogs"]["catalogs"][0]
    slices = producer._pack_slices(full_fixture["upstream"]["pack_rows"])
    semantic = producer._derive_semantic_slate(catalog=catalog, slices=slices)
    definitions = {
        entry["role"]: entry
        for entry in source.frozen_role_registry_v2()["roles"]
    }
    eight_requirement = next(
        requirement for requirement in definitions["qb-concession"][
            "period_requirements"
        ] if requirement["period_rule"] == "prior-eight-games"
    )
    six_requirement = next(
        requirement for requirement in definitions["qb-secondary"][
            "period_requirements"
        ] if requirement["period_rule"] == "prior-six-games"
    )
    eight = producer._select_period_rows(
        role="qb-concession", requirement=eight_requirement,
        semantic=semantic, catalog=catalog, slices=slices,
    )
    six = producer._select_period_rows(
        role="qb-secondary", requirement=six_requirement,
        semantic=semantic, catalog=catalog, slices=slices,
    )
    assert {(row["season"], row["week"]) for row in eight} == {
        (2022, week) for week in range(11, 19)
    }
    assert {(row["season"], row["week"]) for row in six} == {
        (2022, week) for week in range(13, 19)
    }
    assert all(row["week"] != 10 for row in eight)
    assert all(row["week"] != 12 for row in six)


def test_team_context_uses_documented_weighted_denominators() -> None:
    schedule_rows = [
        *(_schedule_row(2022, week) for week in range(15, 19)),
        _schedule_row(2023, 1),
    ]
    games, by_team = producer._schedule_indexes(schedule_rows)
    prior = [game for game in games if game["_key"][0] == 2022]
    sis = [{
        "season": 2022, "week": game["week"], "team": "BBB",
        "rdef_attempts": attempts, "rdef_epa_per_attempt": epa,
    } for game, attempts, epa in zip(
        prior, (10, 20, 30, 40), (1.0, 2.0, 3.0, 4.0), strict=True
    )]
    pressure = [{
        "season": 2022, "week": game["week"], "team": "BBB",
        "game_id": game["game_id"], "pfr_player_id": "edge",
        "def_pressures": value, "def_sacks": 0,
    } for game, value in zip(prior, (1, 2, 3, 4), strict=True)]
    positions = [{
        "season": 2022, "week": game["week"], "team": "BBB",
        "game_id": game["game_id"], "pfr_player_id": "db", "position": "CB",
    } for game in prior]
    secondary = [{
        "season": 2022, "week": game["week"], "team": "BBB",
        "game_id": game["game_id"], "pfr_player_id": "db",
        "def_yards_allowed": yards, "def_targets": targets,
    } for game, yards, targets in zip(
        prior, (10, 20, 30, 40), (1, 2, 3, 4), strict=True
    )]
    result = producer._team_context_components(
        catalog={
            "slate": {"season": 2023, "week": 1},
            "players": [{"id": "qb", "pos": "QB", "opp": "BBB"}],
        },
        weekly_rows=[], sis_run_rows=sis, pfr_pressure_rows=pressure,
        pfr_secondary_rows=secondary, pfr_position_rows=positions,
        schedule_games=games, schedule_by_team=by_team,
        lock_time=next(game["_kickoff"] for game in games if game["_key"] == (2023, 1)),
    )["qb"]
    assert result["run_context"] == 3.0
    assert result["pressure_inverted"] == -2.5
    assert result["secondary"] == 10.0
    assert result["run_context_observed_game_count"] == 4
    assert result["secondary_observed_game_count"] == 4


def test_prior_horizons_follow_exact_kickoff_including_week18_to_week1() -> None:
    transition_rows = [
        *(_schedule_row(2022, week) for week in range(11, 19)),
        _schedule_row(2023, 1),
    ]
    transition_games, _ = producer._schedule_indexes(transition_rows)
    target_lock = next(
        game["_kickoff"]
        for game in transition_games if game["_key"] == (2023, 1)
    )
    transition = producer._prior_defense_games(
        defense="BBB",
        schedule_games=transition_games,
        lock_time=target_lock,
        count=8,
    )
    assert [game["_key"] for game in transition] == [
        (2022, week) for week in range(11, 19)
    ]
    assert all(game["_kickoff"] < target_lock for game in transition)

    reordered_rows = [_schedule_row(2024, week) for week in range(1, 11)]
    reordered_rows[0] = _retime_schedule(
        reordered_rows[0], gameday="2024-10-28"
    )
    reordered_games, _ = producer._schedule_indexes(reordered_rows)
    reordered_lock = next(
        game["_kickoff"]
        for game in reordered_games if game["_key"] == (2024, 10)
    )
    reordered = producer._prior_defense_games(
        defense="BBB",
        schedule_games=reordered_games,
        lock_time=reordered_lock,
        count=8,
    )
    assert [game["_key"] for game in reordered] == [
        (2024, 3), (2024, 4), (2024, 5), (2024, 6),
        (2024, 7), (2024, 8), (2024, 9), (2024, 1),
    ]


def test_role_history_period_uses_exact_kickoff_not_week_label() -> None:
    schedule_rows = [_schedule_row(2024, week) for week in range(1, 16)]
    schedule_rows[0] = _retime_schedule(
        schedule_rows[0], gameday="2024-12-02"
    )
    games, _ = producer._schedule_indexes(schedule_rows)
    target = next(game for game in games if game["_key"] == (2024, 15))
    slices = {
        "schedule-games": schedule_rows,
        "weekly-player-stats": [
            {
                "season": 2024,
                "week": week,
                "player_id": "history-wr",
                "position": "WR",
                "team": "AAA",
                "opponent_team": "BBB",
            }
            for week in range(1, 15)
        ],
        "fp-route-share": [
            {
                "season": 2024,
                "week": week,
                "gsis_id": "history-wr",
                "route_share": 0.5,
            }
            for week in range(1, 15)
        ],
    }
    catalog = {
        "slate": {"season": 2024, "week": 15},
        "players": [
            {"id": "history-wr", "pos": "WR", "opp": "BBB"},
        ],
    }
    semantic = {
        "lock_time_utc": target["kickoff_time_utc"],
        "target_games": [
            {
                key: target[key]
                for key in (
                    "away_team", "game_id", "game_type", "gameday",
                    "gametime", "home_team", "kickoff_time_utc", "season",
                    "week",
                )
            }
        ],
    }
    role = next(
        definition
        for definition in source.frozen_role_registry_v2()["roles"]
        if definition["role"] == "receiver-role-concession"
    )
    requirements = {
        requirement["slice_kind"]: requirement
        for requirement in role["period_requirements"]
        if requirement["slice_kind"] in {
            "weekly-player-stats", "fp-route-share",
        }
    }
    expected = {(2024, week) for week in range(4, 15)} | {(2024, 1)}
    for slice_kind in ("weekly-player-stats", "fp-route-share"):
        selected = producer._select_period_rows(
            role="receiver-role-concession",
            requirement=requirements[slice_kind],
            semantic=semantic,
            catalog=catalog,
            slices=slices,
        )
        assert {(row["season"], row["week"]) for row in selected} == expected
        assert all(row["week"] not in {2, 3} for row in selected)
        event_times = producer._row_event_kickoffs(
            slice_kind=slice_kind,
            rows=selected,
            slices=slices,
            semantic=semantic,
        )
        assert len(event_times) == len(selected)
        by_week = {
            int(row["week"]): event_time
            for row, event_time in zip(selected, event_times, strict=True)
        }
        assert by_week[1] > by_week[14]


@pytest.mark.parametrize("position", ["WR", "RB"])
def test_source_game_postgame_participant_cannot_change_pregame_role_peers(
    position: str,
) -> None:
    schedule_rows = [_schedule_row(2023, week) for week in range(1, 7)]
    games, by_team = producer._schedule_indexes(schedule_rows)
    lock = next(game["_kickoff"] for game in games if game["_key"] == (2023, 6))

    def weekly(player_id: str, week: int, value: float) -> dict[str, object]:
        row: dict[str, object] = {
            "season": 2023, "week": week, "player_id": player_id,
            "position": position, "team": "AAA", "opponent_team": "BBB",
            "target_share": value,
        }
        if position == "WR":
            row["air_yards_share"] = value
        else:
            row["carries"] = value * 10.0
        return row

    raw_weekly = [
        weekly(player_id, week, value)
        for week, value in enumerate((0.2, 0.3, 0.4, 0.5), start=1)
        for player_id in ("pregame-a", "pregame-b")
    ] + [
        weekly("pregame-a", 5, 0.9),
        weekly("pregame-b", 5, 0.1),
    ]
    raw_routes = [
        {"season": 2023, "week": week, "gsis_id": player_id,
         "route_share": value}
        for week, value in enumerate((0.2, 0.3, 0.4, 0.5), start=1)
        for player_id in ("pregame-a", "pregame-b")
    ]
    depth = [
        {"season": 2023, "week": 5, "club_code": "AAA",
         "formation": "Offense", "position": position, "gsis_id": player_id,
         "depth_team": rank}
        for rank, player_id in enumerate(("pregame-a", "pregame-b"), start=1)
    ]

    def labels(rows: list[dict[str, object]]) -> dict[
        tuple[str, int, int], dict[str, object]
    ]:
        normalized = producer._valid_weekly_rows(
            rows, schedule_by_team=by_team, before_lock=lock
        )
        routes = producer._route_rows_by_player(
            raw_routes, weekly_rows=normalized, before_lock=lock
        )
        return producer._source_role_labels(
            weekly_rows=normalized,
            route_rows_by_player=routes,
            schedule_by_team=by_team,
            legacy_depth_rows=depth,
            snapshot_depth_rows=[],
        )

    baseline = labels(raw_weekly)
    contaminated = labels([
        *raw_weekly, weekly("postgame-surprise", 5, 1.0)
    ])
    assert contaminated[("pregame-a", 2023, 5)] == baseline[
        ("pregame-a", 2023, 5)
    ]
    assert contaminated[("pregame-b", 2023, 5)] == baseline[
        ("pregame-b", 2023, 5)
    ]
    assert ("postgame-surprise", 2023, 5) not in contaminated


def test_sis_defender_views_freeze_shrink_top_two_and_trade_isolation() -> None:
    schedule_rows: list[dict[str, object]] = []
    for week in range(15, 19):
        target_defense_game = _schedule_row(2022, week)
        schedule_rows.append(target_defense_game)
        league_game = dict(target_defense_game)
        league_game["home_team"] = "CCC"
        league_game["away_team"] = "DDD"
        league_game["game_id"] = f"league-{week}"
        schedule_rows.append(league_game)
    schedule_rows.append(_schedule_row(2023, 1))
    games, by_team = producer._schedule_indexes(schedule_rows)
    lock = next(game["_kickoff"] for game in games if game["_key"] == (2023, 1))

    rows: list[dict[str, object]] = []
    for week in range(15, 19):
        for defender_id, snaps, targets, completions, yards in (
            ("def-a", 10, 2, 1, 10),
            ("def-b", 5, 2, 1, 30),
            ("def-c", 5, 2, 1, 70),
        ):
            rows.append({
                "season": 2022, "week": week, "alignment": "wide",
                "defense": "BBB", "defender_player_id": defender_id,
                "coverage_snaps": snaps, "targets": targets,
                "completions": completions, "yards": yards,
                "touchdowns": 0,
            })
        rows.append({
            "season": 2022, "week": week, "alignment": "wide",
            "defense": "CCC", "defender_player_id": "league-def",
            "coverage_snaps": 10, "targets": 10, "completions": 1,
            "yards": 0, "touchdowns": 0,
        })
    old_team_trade_row = {
        "season": 2022, "week": 15, "alignment": "wide",
        "defense": "CCC", "defender_player_id": "def-a",
        "coverage_snaps": 999, "targets": 100, "completions": 100,
        "yards": 1000, "touchdowns": 20,
    }

    kwargs = {
        "defense": "BBB", "schedule_games": games,
        "schedule_by_team": by_team, "lock_time": lock,
    }
    unit, top_two = producer._sis_defender_views(
        sis_rows=[*rows, old_team_trade_row], **kwargs
    )
    assert (unit, top_two) == producer._sis_defender_views(
        sis_rows=rows, **kwargs
    )
    league_prior = 60.0 / 64.0
    rate_a = (8.0 + 16.0 * league_prior) / 24.0
    rate_b = (16.0 + 16.0 * league_prior) / 24.0
    rate_c = (32.0 + 16.0 * league_prior) / 24.0
    assert unit["wide"] == pytest.approx(
        (40.0 * rate_a + 20.0 * rate_b + 20.0 * rate_c) / 80.0
    )
    assert top_two["wide"] == pytest.approx(
        (40.0 * rate_a + 20.0 * rate_b) / 60.0
    )
