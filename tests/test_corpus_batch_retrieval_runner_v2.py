from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

import numpy as np
import pytest

from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_r6_matchup_source_v1 as corrected_source
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    canonical_sha256,
)
from nfl_dfs.research.corpus_parametric_batch import PARAMETER_SET_ORDER
from nfl_dfs.research.corpus_v12_import import (
    MATRIX_BINDING_SCHEMA,
    PROVENANCE_SCHEMA,
    RECONSTRUCTION_SCHEMA,
    canonical_lineup_id,
)
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner


SLATE = {"season": 2023, "week": 1, "slate_id": "2023-w01"}


def _roster(index: int) -> list[str]:
    return sorted(f"player-{index:03d}-{slot}" for slot in range(9))


def _provenance(count: int = 90) -> dict[str, object]:
    rows = []
    for index in range(count):
        roster = _roster(index)
        lineup_id = canonical_lineup_id(SLATE, roster)
        block = "R4" if index == count - 1 else rw.WORLD_BLOCKS[index % 4]
        arm_ordinal = index % len(PARAMETER_SET_ORDER)
        occurrences = [{
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": PARAMETER_SET_ORDER[arm_ordinal],
            "visit_ordinal": index,
            "block_id": block,
            "objective_world_index": index % 2,
        }]
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "origin_blocks": [block],
            "source_arms": [PARAMETER_SET_ORDER[arm_ordinal]],
            "occurrence_counts_by_block": {
                value: int(value == block) for value in rw.WORLD_BLOCKS
            },
            "source_arms_by_block": {
                value: (
                    [PARAMETER_SET_ORDER[arm_ordinal]] if value == block else []
                )
                for value in rw.WORLD_BLOCKS
            },
            "occurrence_count": 1,
            "occurrences": occurrences,
        })
    rows.sort(key=lambda row: row["lineup_id"])
    body: dict[str, object] = {
        "schema_version": PROVENANCE_SCHEMA,
        "slate": dict(SLATE),
        "visit_schedule_sha256": "a" * 64,
        "visits_per_block": 2,
        "arm_count": 7,
        "visit_occurrence_count": count,
        "candidate_count": count,
        "lineup_order_law": "ascending-stable-per-slate-lineup-id",
        "candidates": rows,
        "uses_realized_outcomes": False,
    }
    body["candidate_provenance_sha256"] = canonical_sha256(body)
    return body


def _matchup_rows(provenance: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for ordinal, candidate in enumerate(provenance["candidates"]):
        for player_offset, player_id in enumerate(
            candidate["roster_player_ids"][:8]
        ):
            rows.append({
                "gsis_id": player_id,
                "family": (
                    "qb" if player_offset == 0
                    else "rb" if player_offset in {1, 2}
                    else "receiver"
                ),
                "matchup_edge_score": round(
                    (ordinal + player_offset / 10)
                    / (len(provenance["candidates"]) + 1),
                    12,
                ),
            })
    return rows


def _eligible_players(provenance: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for candidate in provenance["candidates"]:
        for player_offset, player_id in enumerate(
            candidate["roster_player_ids"][:8]
        ):
            if player_offset == 0:
                family, position, depth = "qb", "QB", True
            elif player_offset in {1, 2}:
                family, position, depth = "rb", "RB", None
            else:
                family, position, depth = "receiver", "WR", None
            rows.append({
                "gsis_id": player_id,
                "family": family,
                "position": position,
                "qb_depth1": depth,
            })
    return rows


def _object_identity(name: str) -> dict[str, object]:
    raw = name.encode()
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _ExactMatchupStore:
    """Generation-aware in-memory object store used by the runner boundary."""

    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.next_generation = 1000

    @staticmethod
    def _identity(uri: str, raw: bytes, generation: str) -> dict[str, object]:
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def seed(self, uri: str, raw: bytes) -> dict[str, object]:
        identity = self._identity(uri, raw, "900")
        self.objects[uri] = {"identity": identity, "raw": raw}
        return deepcopy(identity)

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.objects:
            raise corrected_source.CorpusR6MatchupSourceV1Error(
                "create-once collision"
            )
        identity = self._identity(uri, raw, str(self.next_generation))
        self.next_generation += 1
        self.objects[uri] = {"identity": identity, "raw": raw}
        return deepcopy(identity)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        retained = self.objects.get(str(identity["uri"]))
        if retained is None or retained["identity"] != identity:
            raise corrected_source.CorpusR6MatchupSourceV1Error(
                "exact identity/generation differs"
            )
        return bytes(retained["raw"])


_MATCHUP_AUTHORITY_CACHE: dict[str, runner.MatchupSourceExactReopen] = {}


def _self_hashed(
    body: dict[str, object], field: str
) -> dict[str, object]:
    result = deepcopy(body)
    result[field] = corrected_source.canonical_sha256(result)
    return result


def _family_definition(family: str, role: str) -> dict[str, object]:
    row_fields = sorted({
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
    })
    role_schema = corrected_source.build_source_role_schema_v1(
        role=role,
        row_fields=row_fields,
        source_period_kind="prior-season-full",
        population_role="component",
    )
    return _self_hashed({
        "schema_version": corrected_source.FAMILY_DEFINITION_SCHEMA,
        "family_id": f"{family}-matchup",
        "version": 2,
        "provisional": True,
        "source_roles": [role],
        "fields": [
            {
                "name": component,
                "field_type": "percentile",
                "nullable": True,
                "description": f"outcome-blind fixture {component}",
            }
            for component in ("component_a", "component_b")
        ],
        "missing_reason_codes": ["source-absent"],
        "description": "exact-reopen runner fixture",
        "source_role_schemas": {role: role_schema},
        "component_source_roles": {
            "component_a": [role],
            "component_b": [role],
        },
    }, "family_definition_sha256")


def _source_extract(
    *,
    role: str,
    schema_sha256: str,
    rows: list[dict[str, object]],
    period_kind: str,
    period: dict[str, object],
    maximum_event: str,
) -> dict[str, object]:
    rows_sha = corrected_source.canonical_sha256(rows)
    return {
        "role": role,
        "relation_or_object": (
            "bq://fixture_project.fixture_dataset."
            f"{role.replace('-', '_')}"
        ),
        "source_identity_or_extract_sha256": rows_sha,
        "source_role_schema_sha256": schema_sha256,
        "rows": rows,
        "rows_sha256": rows_sha,
        "row_count": len(rows),
        "source_period_kind": period_kind,
        "source_season_week_min": period,
        "source_season_week_max": period,
        "maximum_source_event_time_utc": maximum_event,
        "observed_at_utc": "2026-08-25T11:58:00Z",
        "observed_at_basis": "historical-source-period-only",
        "evidence_class": corrected_source.EVIDENCE_RETROSPECTIVE,
        "missingness_reason": None,
    }


def _capture_matchup_source(
    provenance: dict[str, object],
    *,
    rows: list[dict[str, object]] | None = None,
    eligible_players: list[dict[str, object]] | None = None,
) -> tuple[runner.MatchupSourceExactReopen, _ExactMatchupStore]:
    """Capture, create-once publish, and prepare an exact runner reopen."""
    eligible = deepcopy(
        _eligible_players(provenance)
        if eligible_players is None else eligible_players
    )
    eligible.sort(key=lambda row: str(row["gsis_id"]))
    eligible_by_id = {
        str(row["gsis_id"]): dict(row) for row in eligible
    }
    supplied = {
        str(row["gsis_id"]): dict(row)
        for row in (_matchup_rows(provenance) if rows is None else rows)
    }
    task_slate = {**SLATE, "task_id": "fixture-task"}
    lock_time = "2023-09-10T17:00:00Z"

    families = {
        family: _family_definition(family, f"{family}-prior-context")
        for family in corrected_source.ELIGIBLE_FAMILIES
    }
    extracts: list[dict[str, object]] = []
    annotations: list[dict[str, object]] = []
    for family in corrected_source.ELIGIBLE_FAMILIES:
        role = f"{family}-prior-context"
        component_rows: list[dict[str, object]] = []
        for player in eligible:
            if player["family"] != family:
                continue
            player_id = str(player["gsis_id"])
            supplied_row = supplied.get(player_id)
            edge = (
                None
                if supplied_row is None
                else supplied_row["matchup_edge_score"]
            )
            supported = edge is not None
            for component in ("component_a", "component_b"):
                component_rows.append({
                    "role": role,
                    "source_season": 2022,
                    "source_week": None,
                    "source_event_time_utc": "2023-02-12T23:00:00Z",
                    "observed_at_utc": "2026-08-25T11:58:00Z",
                    "target_season": SLATE["season"],
                    "target_week": SLATE["week"],
                    "target_slate_id": SLATE["slate_id"],
                    "target_task_id": task_slate["task_id"],
                    "gsis_id": player_id,
                    "family": family,
                    "team": "AAA",
                    "opponent": "BBB",
                    "game_id": "AAA|BBB",
                    "component": component,
                    "component_value": None if edge is None else float(edge),
                    "component_supported": supported,
                    "missing_reason_code": (
                        None if supported else "source-absent"
                    ),
                })
            if not supported:
                continue
            bound = {
                "source_roles": [role],
                "source_season_week_min": {"season": 2022, "week": None},
                "source_season_week_max": {"season": 2022, "week": None},
                "maximum_source_event_time_utc": "2023-02-12T23:00:00Z",
                "evidence_class": corrected_source.EVIDENCE_RETROSPECTIVE,
            }
            depth = player["qb_depth1"]
            annotations.append({
                "gsis_id": player_id,
                "family": family,
                "position": player["position"],
                "qb_depth1": depth,
                "qb_depth_evidence_class": (
                    corrected_source.EVIDENCE_RETROSPECTIVE
                    if family == "qb" and depth is not None
                    else "unknown"
                    if family == "qb"
                    else "not-applicable"
                ),
                "component_values": {
                    "component_a": float(edge),
                    "component_b": float(edge),
                },
                "component_support": {
                    "component_a": True,
                    "component_b": True,
                },
                "component_source_bounds": {
                    "component_a": bound,
                    "component_b": bound,
                },
                "component_missing_reason_codes": {
                    "component_a": [],
                    "component_b": [],
                },
                "matchup_component_count": 2,
                "matchup_edge_score": float(edge),
            })
        component_rows.sort(
            key=lambda row: (str(row["gsis_id"]), str(row["component"]))
        )
        extracts.append(_source_extract(
            role=role,
            schema_sha256=str(
                families[family]["source_role_schemas"][role][
                    "source_role_schema_sha256"
                ]
            ),
            rows=component_rows,
            period_kind="prior-season-full",
            period={"season": 2022, "week": None},
            maximum_event="2023-02-12T23:00:00Z",
        ))
    annotations.sort(key=lambda row: str(row["gsis_id"]))

    schedule_schema = corrected_source.infrastructure_source_role_schemas_v1()[
        corrected_source.SCHEDULE_SOURCE_ROLE
    ]
    schedule_rows = [
        {
            "role": corrected_source.SCHEDULE_SOURCE_ROLE,
            "source_season": 2023,
            "source_week": 1,
            "source_event_time_utc": "2023-09-01T12:00:00Z",
            "observed_at_utc": "2026-08-25T11:58:00Z",
            "season": 2023,
            "week": 1,
            "slate_id": SLATE["slate_id"],
            "task_id": task_slate["task_id"],
            "game_id": "AAA|BBB",
            "team": team,
            "opponent": opponent,
            "kickoff_time_utc": lock_time,
            "lock_time_utc": lock_time,
        }
        for team, opponent in (("AAA", "BBB"), ("BBB", "AAA"))
    ]
    extracts.append(_source_extract(
        role=corrected_source.SCHEDULE_SOURCE_ROLE,
        schema_sha256=str(schedule_schema["source_role_schema_sha256"]),
        rows=schedule_rows,
        period_kind="prelock-snapshot",
        period={"season": 2023, "week": 1},
        maximum_event="2023-09-01T12:00:00Z",
    ))
    depth_schema = corrected_source.infrastructure_source_role_schemas_v1()[
        corrected_source.QB_DEPTH_SOURCE_ROLE
    ]
    depth_rows = []
    for player in eligible:
        if player["family"] != "qb":
            continue
        depth = player["qb_depth1"]
        depth_rows.append({
            "role": corrected_source.QB_DEPTH_SOURCE_ROLE,
            "source_season": 2023,
            "source_week": 1,
            "source_event_time_utc": "2023-09-10T16:00:00Z",
            "observed_at_utc": "2026-08-25T11:58:00Z",
            "season": 2023,
            "week": 1,
            "slate_id": SLATE["slate_id"],
            "task_id": task_slate["task_id"],
            "gsis_id": player["gsis_id"],
            "team": "AAA",
            "game_id": "AAA|BBB",
            "depth1": depth,
            "missingness_reason": None if depth is not None else "source-absent",
        })
    depth_rows.sort(key=lambda row: str(row["gsis_id"]))
    extracts.append(_source_extract(
        role=corrected_source.QB_DEPTH_SOURCE_ROLE,
        schema_sha256=str(depth_schema["source_role_schema_sha256"]),
        rows=depth_rows,
        period_kind="prelock-snapshot",
        period={"season": 2023, "week": 1},
        maximum_event="2023-09-10T16:00:00Z",
    ))
    extracts.sort(key=lambda row: str(row["role"]))

    all_roster_ids = sorted({
        str(player_id)
        for candidate in provenance["candidates"]
        for player_id in candidate["roster_player_ids"]
    })
    catalog_players = []
    for player_id in all_roster_ids:
        eligible_player = eligible_by_id.get(player_id)
        position = (
            str(eligible_player["position"])
            if eligible_player is not None
            else "DST"
        )
        is_dst = position == "DST"
        catalog_players.append({
            "id": player_id,
            "name": player_id,
            "pos": position,
            "team": "BBB" if is_dst else "AAA",
            "opp": "AAA" if is_dst else "BBB",
            "game_id": "AAA|BBB",
            "salary": 3000 if is_dst else 6000,
            "proj": 7.0 if is_dst else 15.0,
        })
    catalog = _self_hashed({
        "schema_version": corrected_source.PLAYER_CATALOG_SCHEMA,
        "task_id": task_slate["task_id"],
        "source_authority": _object_identity("catalog-authority"),
        "players": catalog_players,
    }, "player_catalog_sha256")
    catalog_raw = corrected_source.canonical_json_bytes(catalog)
    store = _ExactMatchupStore()
    catalog_identity = store.seed(
        "gs://fixture/r6-runner/player-catalog.json", catalog_raw
    )
    relations = [
        {
            "role": str(extract["role"]),
            "table_or_object": str(extract["relation_or_object"]),
            "schema_sha256": str(extract["source_role_schema_sha256"]),
            "etag_or_generation": f"etag-{ordinal}",
            "modified_or_created_at_utc": "2026-08-25T11:58:00Z",
            "exact_extract_sha256": str(extract["rows_sha256"]),
            "row_count": int(extract["row_count"]),
        }
        for ordinal, extract in enumerate(extracts)
    ]
    identities = corrected_source.capture_matchup_source_v1(
        slate=task_slate,
        lock_time_utc=lock_time,
        player_catalog_identity=catalog_identity,
        player_catalog_raw=catalog_raw,
        rendered_sql_raw=corrected_source.build_rendered_sql_v1(relations),
        query_job_receipt={
            "created_at_utc": "2026-08-25T12:05:00Z",
            "query_parameters": {
                "season": 2023,
                "week": 1,
                "slate_id": SLATE["slate_id"],
                "task_id": task_slate["task_id"],
                "lock_time_utc": lock_time,
                "source_roles": sorted(
                    str(extract["role"]) for extract in extracts
                ),
            },
            "query_snapshot_at_utc": "2026-08-25T11:59:00Z",
            "query_job": {
                "project": "fixture-project",
                "location": "US",
                "job_id": "r6_runner_exact_reopen_fixture",
                "created": "2026-08-25T12:00:00Z",
                "started": "2026-08-25T12:01:00Z",
                "ended": "2026-08-25T12:02:00Z",
                "cache_hit": False,
                "error_result": None,
                "total_bytes_processed": 1234,
            },
            "source_relations": relations,
            "player_catalog_evidence": {
                "maximum_source_event_time_utc": "2023-09-10T16:00:00Z",
                "observed_at_utc": "2026-08-25T11:58:00Z",
                "observed_at_basis": "historical-source-period-only",
                "evidence_class": corrected_source.EVIDENCE_RETROSPECTIVE,
            },
        },
        component_extracts=extracts,
        annotation_rows=annotations,
        family_definition_identities=families,
        code_identity={
            "schema_version": "r6-matchup-source-code/v1",
            "source_commit": "b" * 40,
            "uses_realized_outcomes": False,
        },
        publish_create_once=store.publish_create_once,
        read_exact=store.read_exact,
        output_prefix="gs://fixture/r6-runner/corrected-source",
    )
    authority = runner.MatchupSourceExactReopen(
        source_export_identity=identities["source_export_identity"],
        query_receipt_identity=identities["query_receipt_identity"],
        player_catalog_identity=catalog_identity,
        expected_slate=task_slate,
        required_evidence_class=corrected_source.EVIDENCE_RETROSPECTIVE,
        read_exact=store.read_exact,
    )
    # Prove the fixture itself takes the same exact reopen used by the runner.
    corrected_source.reopen_matchup_source_snapshot(
        source_export_identity=authority.source_export_identity,
        query_receipt_identity=authority.query_receipt_identity,
        player_catalog_identity=authority.player_catalog_identity,
        read_exact=authority.read_exact,
        expected_slate=authority.expected_slate,
        required_evidence_class=authority.required_evidence_class,
    )
    return authority, store


def _matchup_source(
    provenance: dict[str, object],
    *,
    rows: list[dict[str, object]] | None = None,
    eligible_players: list[dict[str, object]] | None = None,
) -> runner.MatchupSourceExactReopen:
    effective_rows = (
        _matchup_rows(provenance) if rows is None else deepcopy(rows)
    )
    effective_eligible = (
        _eligible_players(provenance)
        if eligible_players is None
        else deepcopy(eligible_players)
    )
    cache_key = corrected_source.canonical_sha256({
        "slate": provenance["slate"],
        "rosters": [
            candidate["roster_player_ids"]
            for candidate in provenance["candidates"]
        ],
        "rows": effective_rows,
        "eligible_players": effective_eligible,
    })
    cached = _MATCHUP_AUTHORITY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    authority, _ = _capture_matchup_source(
        provenance,
        rows=effective_rows,
        eligible_players=effective_eligible,
    )
    _MATCHUP_AUTHORITY_CACHE[cache_key] = authority
    return authority


def _scores(provenance: dict[str, object]) -> np.ndarray:
    count = len(provenance["candidates"])
    row = np.arange(count, dtype=np.float64)[:, None]
    column = np.arange(10, dtype=np.float64)[None, :]
    scores = np.ascontiguousarray(180.0 + (row % 31) + column * 0.75)
    # The heldout-only candidate would dominate if origin filtering failed.
    r4_only_index = next(
        index for index, candidate in enumerate(provenance["candidates"])
        if candidate["origin_blocks"] == ["R4"]
    )
    scores[r4_only_index] = 400.0 + column
    return scores


def _reconstruction(
    provenance: dict[str, object], scores: np.ndarray
) -> dict[str, object]:
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    matrix: dict[str, object] = {
        "schema_version": MATRIX_BINDING_SCHEMA,
        "slate": dict(SLATE),
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "lineup_ids_sha256": canonical_sha256(lineup_ids),
        "world_ids_sha256": "9" * 64,
        "shape": list(scores.shape),
        "score_matrix_sha256": _score_matrix_sha256(scores),
        "uses_realized_outcomes": False,
    }
    matrix["matrix_binding_sha256"] = canonical_sha256(matrix)
    receipt: dict[str, object] = {
        "schema_version": RECONSTRUCTION_SCHEMA,
        "compatibility_import_sha256": "8" * 64,
        "candidate_provenance_sha256": provenance[
            "candidate_provenance_sha256"
        ],
        "matrix_binding": matrix,
        "verified_arm_score_hashes": [
            {
                "ordinal": ordinal,
                "parameter_set_id": arm_id,
                "candidate_score_sha256": f"{ordinal + 1:x}" * 64,
                "selected_score_sha256": f"{ordinal + 8:x}" * 64,
                "unique_count": len(lineup_ids),
                "selected_count": 80,
                "verified": True,
            }
            for ordinal, arm_id in enumerate(PARAMETER_SET_ORDER)
        ],
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    receipt["reconstruction_sha256"] = canonical_sha256(receipt)
    return receipt


def _summary(provenance: dict[str, object]) -> dict[str, object]:
    return runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=_matchup_source(provenance),
        minimum_supported_players=2,
        minimum_completeness=1.0,
    )


def _book_projection(scope: dict[str, object]) -> list[dict[str, object]]:
    return [{
        "book_id": book["book_id"],
        "selected_lineup_ids": book["selected_lineup_ids"],
        "marginal_trace": book["marginal_trace"],
        "training_metrics": book["training_metrics"],
    } for book in scope["books"]]


def test_all_seven_laws_run_for_union_and_matchup_with_exact_traces(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    scope = runner.run_fit_scope(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=2,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert scope["book_count"] == 16
    assert scope["dose_authority"] == runner.FIXTURE_DOSE
    assert scope["require_authoritative"] is False
    assert scope["worlds_per_block"] == 2
    ids_by_admission = {}
    for book in scope["books"]:
        ids_by_admission.setdefault(book["admission_id"], set()).add(
            book["strategy_id"]
        )
        assert book["entry_count"] == 80
        assert len(set(book["selected_lineup_ids"])) == 80
        assert len(book["marginal_trace"]) == 80
        diagnostics = book["redundancy_diagnostics"]
        assert diagnostics["lineup_pair_count"] == 3160
        assert sum(
            row["lineup_pair_count"]
            for row in diagnostics["shared_player_count_histogram"]
        ) == 3160
        assert len(diagnostics["simulated_outcome_event_redundancy"]) == 4
        assert diagnostics["uses_realized_outcomes"] is False
        correlation = diagnostics["pairwise_score_correlation"]
        assert correlation["pair_population_count"] == 3160
        assert correlation["sampled_pair_count"] == 32
        assert len(correlation["rows"]) == 32
        assert correlation["full_pairwise_materialized"] is False
        assert correlation["uses_realized_outcomes"] is False
        assert all(
            "objective_before" in row
            and "objective_gain" in row
            and "objective_after" in row
            and "global_lineup_index" in row
            and "block_contributions" in row
            for row in book["marginal_trace"]
        )
    expected = {
        strategy["strategy_id"]
        for strategy in retrieval.frozen_retrieval_strategies_v2(80)
    }
    fixture_full = f"{runner.FIXTURE_ID_PREFIX}{runner.FULL_UNION_ADMISSION_ID}"
    fixture_matchup = f"{runner.FIXTURE_ID_PREFIX}matchup-top-80-supported-v2"
    assert ids_by_admission[fixture_full] == expected
    assert ids_by_admission[fixture_matchup] == expected
    neutral_ids = [
        admission["admission_id"]
        for admission in scope["admissions"]
        if admission["admission_id"].startswith(
            f"{runner.FIXTURE_ID_PREFIX}neutral-"
        )
    ]
    assert len(neutral_ids) == 2
    assert all(ids_by_admission[value] == {runner.PRIMARY_STRATEGY_ID} for value in neutral_ids)
    heldout_only = next(
        row["lineup_id"] for row in provenance["candidates"]
        if row["origin_blocks"] == ["R4"]
    )
    assert all(
        heldout_only not in book["selected_lineup_ids"] for book in scope["books"]
    )
    assert runner.validate_fit_scope(
        scope,
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=2,
        worlds_per_block=2,
        require_authoritative=False,
    ) == scope


def test_heldout_scores_and_occurrences_cannot_change_fold_selection(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    summary = _summary(provenance)
    baseline = runner.run_fit_scope(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=summary,
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )

    poisoned_scores = scores.copy()
    poisoned_scores[:, 8:10] = np.arange(len(scores))[:, None] * 10_000.0
    poisoned = runner.run_fit_scope(
        provenance=provenance,
        union_scores=poisoned_scores,
        reconstruction_receipt=_reconstruction(provenance, poisoned_scores),
        matchup_summary=summary,
        matchup_source=_matchup_source(provenance),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert _book_projection(poisoned) == _book_projection(baseline)
    assert any(
        left["heldout_metrics_descriptive"]
        != right["heldout_metrics_descriptive"]
        for left, right in zip(poisoned["books"], baseline["books"], strict=True)
    )

    changed = deepcopy(provenance)
    candidate = next(
        row for row in changed["candidates"] if row["origin_blocks"] != ["R4"]
    )
    candidate["occurrences"].append({
        "arm_ordinal": 6,
        "parameter_set_id": PARAMETER_SET_ORDER[6],
        "visit_ordinal": 999,
        "block_id": "R4",
        "objective_world_index": 1,
    })
    candidate["origin_blocks"] = [
        block for block in rw.WORLD_BLOCKS
        if block in {*candidate["origin_blocks"], "R4"}
    ]
    candidate["source_arms"] = sorted({
        *candidate["source_arms"], PARAMETER_SET_ORDER[6]
    })
    candidate["occurrence_counts_by_block"]["R4"] += 1
    candidate["source_arms_by_block"]["R4"] = sorted({
        *candidate["source_arms_by_block"]["R4"], PARAMETER_SET_ORDER[6]
    })
    candidate["occurrence_count"] += 1
    changed["visit_occurrence_count"] += 1
    changed.pop("candidate_provenance_sha256")
    changed["candidate_provenance_sha256"] = canonical_sha256(changed)
    changed_scope = runner.run_fit_scope(
        provenance=changed,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(changed, scores),
        matchup_summary=summary,
        matchup_source=_matchup_source(changed),
        heldout_block="R4",
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert changed_scope["candidate_view"]["selection_provenance_sha256"] == (
        baseline["candidate_view"]["selection_provenance_sha256"]
    )
    assert _book_projection(changed_scope) == _book_projection(baseline)


def test_neutral_is_order_independent_and_exactly_composition_matched() -> None:
    candidate_ids = [f"lineup:{index:064x}" for index in range(12)]
    strata = {
        lineup_id: {"cell": index % 3}
        for index, lineup_id in enumerate(candidate_ids)
    }
    targets = candidate_ids[:6]
    first = runner.build_score_blind_neutral_admission(
        candidate_ids=candidate_ids,
        target_ids=targets,
        strata_by_id=strata,
        slate=SLATE,
        fit_scope_id="holdout-R4",
        seed_root="fixture-seed",
        replicate_index=0,
        selection_provenance_sha256="c" * 64,
        target_admission_sha256="e" * 64,
        dose_authority=runner.FIXTURE_DOSE,
    )
    replay = runner.build_score_blind_neutral_admission(
        candidate_ids=list(reversed(candidate_ids)),
        target_ids=list(reversed(targets)),
        strata_by_id=strata,
        slate=SLATE,
        fit_scope_id="holdout-R4",
        seed_root="fixture-seed",
        replicate_index=0,
        selection_provenance_sha256="c" * 64,
        target_admission_sha256="e" * 64,
        dose_authority=runner.FIXTURE_DOSE,
    )
    assert first == replay
    target_counts = Counter(strata[value]["cell"] for value in targets)
    admitted_counts = Counter(
        strata[value]["cell"] for value in first["admitted_lineup_ids"]
    )
    assert admitted_counts == target_counts
    assert first["admitted_count"] == len(targets)
    assert first["uses_simulated_scores"] is False
    assert first["uses_matchup_values"] is False
    excluded_ids = [
        row["lineup_id"] for row in first["excluded_eligible_candidates"]
    ]
    assert excluded_ids == sorted(set(candidate_ids) - set(first["admitted_lineup_ids"]))
    assert all(
        row["reason_code"] == "neutral-not-sampled"
        for row in first["excluded_eligible_candidates"]
    )
    assert first["excluded_eligible_candidate_count"] == 6
    assert first["excluded_eligible_lineup_ids_sha256"] == canonical_sha256(
        excluded_ids
    )
    runner._validate_admission_partition(first, eligible_ids=candidate_ids)

    tampered = deepcopy(first)
    tampered["excluded_eligible_candidates"].pop()
    tampered["admission_sha256"] = canonical_sha256({
        key: value for key, value in tampered.items() if key != "admission_sha256"
    })
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="partition does not replay",
    ):
        runner._validate_admission_partition(tampered, eligible_ids=candidate_ids)


def test_matchup_preserves_zero_missing_and_qb_starter_semantics() -> None:
    provenance = _provenance(count=3)
    first = provenance["candidates"][0]
    second = provenance["candidates"][1]
    rows = [
        {
            "gsis_id": first["roster_player_ids"][3],
            "family": "receiver",
            "matchup_edge_score": 0.0,
        },
        {
            "gsis_id": first["roster_player_ids"][4],
            "family": "receiver",
            "matchup_edge_score": None,
        },
        {
            "gsis_id": second["roster_player_ids"][0],
            "family": "qb",
            "matchup_edge_score": 1.0,
        },
    ]
    eligible = _eligible_players(provenance)
    second_qb = second["roster_player_ids"][0]
    for player in eligible:
        if player["gsis_id"] == second_qb:
            player["qb_depth1"] = False
    summary = runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=_matchup_source(
            provenance, rows=rows, eligible_players=eligible
        ),
        minimum_supported_players=1,
        minimum_completeness=0.1,
    )
    by_id = {row["lineup_id"]: row for row in summary["lineups"]}
    first_row = by_id[first["lineup_id"]]
    assert first_row["matchup_edge_mean"] == 0.0
    assert first_row["eligible_player_count"] == 8
    assert first_row["supported_player_count"] == 1
    assert first_row["qualifies_for_matchup_admission"] is True
    second_row = by_id[second["lineup_id"]]
    assert second_row["eligible_player_count"] == 7
    assert second_row["matchup_edge_mean"] is None
    assert second_row["qb_depth1_eligible"] is False
    assert second_row["qualifies_for_matchup_admission"] is False
    assert summary["qb_gate"] == "require-qb_depth1-is-literal-true"


def test_unknown_qb_depth_cannot_silently_pass_matchup_admission() -> None:
    provenance = _provenance(count=3)
    first = provenance["candidates"][0]
    eligible = _eligible_players(provenance)
    first_qb = first["roster_player_ids"][0]
    for player in eligible:
        if player["gsis_id"] == first_qb:
            player["qb_depth1"] = None
    summary = runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=_matchup_source(
            provenance,
            rows=_matchup_rows(provenance),
            eligible_players=eligible,
        ),
        minimum_supported_players=1,
        minimum_completeness=0.0,
    )
    row = next(
        row
        for row in summary["lineups"]
        if row["lineup_id"] == first["lineup_id"]
    )
    assert row["qb_depth1_eligible"] is False
    assert row["qualifies_for_matchup_admission"] is False
    assert row["eligible_player_count"] == 7


def test_final_fit_uses_all_blocks_and_includes_heldout_only_origin(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    final_fit = runner.run_fit_scope(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        heldout_block=None,
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert final_fit["training_blocks"] == list(rw.WORLD_BLOCKS)
    assert final_fit["heldout_block"] is None
    assert final_fit["candidate_view"]["excluded_count"] == 0
    r4_only = next(
        row["lineup_id"] for row in provenance["candidates"]
        if row["origin_blocks"] == ["R4"]
    )
    assert r4_only in {
        row["lineup_id"]
        for row in final_fit["candidate_view"]["eligible_candidates"]
    }
    assert all(book["heldout_metrics_descriptive"] is None for book in final_fit["books"])


def test_complete_surface_rotates_all_five_blocks_then_refits_all_blocks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance(count=120)
    scores = _scores(provenance)
    surface = runner.run_retrieval_surface_v2(
        provenance=provenance,
        union_scores=scores,
        reconstruction_receipt=_reconstruction(provenance, scores),
        matchup_summary=_summary(provenance),
        matchup_source=_matchup_source(provenance),
        admission_m=80,
        neutral_replicates=1,
        worlds_per_block=2,
        require_authoritative=False,
    )
    assert [fold["heldout_block"] for fold in surface["folds"]] == list(
        rw.WORLD_BLOCKS
    )
    assert all(fold["book_count"] == 15 for fold in surface["folds"])
    assert surface["cross_fit_book_count"] == 75
    assert surface["final_fit_book_count"] == 15
    assert surface["final_fit"]["training_blocks"] == list(rw.WORLD_BLOCKS)
    assert surface["final_fit"]["fit_scope_id"] == "all-block-final-fit"
    assert surface["uses_realized_outcomes"] is False
    assert surface["dose_authority"] == runner.FIXTURE_DOSE
    assert all(
        admission["admission_id"].startswith(runner.FIXTURE_ID_PREFIX)
        for scope in [*surface["folds"], surface["final_fit"]]
        for admission in scope["admissions"]
    )


def test_authoritative_surface_rejects_fixture_doses_before_dispatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="authoritative R6-v2 requires top-200 admission",
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            matchup_summary=_summary(provenance),
            matchup_source=_matchup_source(provenance),
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
        )


def test_threshold_boundaries_are_ge_194_then_strict_above_tail_lines() -> None:
    summary = runner._score_summary(np.asarray(
        [[194.0, 200.0, 210.0, 220.0]], dtype=np.float64
    ))
    assert summary["worlds_ge_194"] == 4
    assert summary["worlds_gt_200"] == 2
    assert summary["worlds_gt_210"] == 1
    assert summary["worlds_gt_220"] == 0


def test_bounded_pairwise_correlation_is_identity_order_independent() -> None:
    lineup_ids = [f"lineup:{index:064x}" for index in range(5)]
    scores = np.asarray([
        [1.0, 2.0, 3.0, 4.0],
        [4.0, 3.0, 2.0, 1.0],
        [2.0, 4.0, 6.0, 8.0],
        [7.0, 7.0, 7.0, 7.0],
        [1.0, 4.0, 2.0, 9.0],
    ], dtype=np.float64)
    first = runner._bounded_pairwise_score_correlation(
        scores, lineup_ids=lineup_ids
    )
    replay = runner._bounded_pairwise_score_correlation(
        scores[::-1], lineup_ids=list(reversed(lineup_ids))
    )
    assert replay == first
    assert first["pair_population_count"] == 10
    assert first["sampled_pair_count"] == 10
    assert first["full_pairwise_materialized"] is True
    assert first["constant-series-pair-count"] == 4


def test_sparse_matchup_support_fails_closed_before_selector_dispatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    eligible_r4_fold = [
        row for row in provenance["candidates"]
        if row["origin_blocks"] != ["R4"]
    ]
    supported_ids = {
        player
        for candidate in eligible_r4_fold[:79]
        for player in candidate["roster_player_ids"][:8]
    }
    rows = [
        row for row in _matchup_rows(provenance)
        if row["gsis_id"] in supported_ids
    ]
    sparse_source = _matchup_source(provenance, rows=rows)
    sparse = runner.build_matchup_lineup_summaries(
        provenance=provenance,
        matchup_source=sparse_source,
        minimum_supported_players=2,
        minimum_completeness=1.0,
    )
    scores = _scores(provenance)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="fewer qualifying candidates",
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            matchup_summary=sparse,
            matchup_source=sparse_source,
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_registry_deletion_fails_the_seven_law_compatibility_gate(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    frozen = retrieval.frozen_retrieval_strategies_v2(80)
    monkeypatch.setattr(
        retrieval,
        "frozen_retrieval_strategies_v2",
        lambda entry_budget: frozen[:-1],
    )
    scores = _scores(provenance)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error, match="seven-law retrieval registry"
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=_reconstruction(provenance, scores),
            matchup_summary=_summary(provenance),
            matchup_source=_matchup_source(provenance),
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_registry_reordering_fails_the_canonical_ordinal_gate(monkeypatch) -> None:
    frozen = retrieval.frozen_retrieval_strategies_v2(80)
    monkeypatch.setattr(
        retrieval,
        "frozen_retrieval_strategies_v2",
        lambda entry_budget: list(reversed(frozen)),
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="registry order/ordinal differs",
    ):
        runner._validate_strategy_registry()


def test_registry_duplicate_identity_fails_even_with_a_valid_self_hash(
    monkeypatch,
) -> None:
    frozen = deepcopy(retrieval.frozen_retrieval_strategies_v2(80))
    duplicate = deepcopy(frozen[5])
    duplicate["ordinal"] = 6
    duplicate["strategy_sha256"] = canonical_sha256({
        key: value for key, value in duplicate.items()
        if key != "strategy_sha256"
    })
    frozen[6] = duplicate
    monkeypatch.setattr(
        retrieval,
        "frozen_retrieval_strategies_v2",
        lambda entry_budget: frozen,
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="identities are not unique/canonical",
    ):
        runner._validate_strategy_registry()


def test_expected_max_dispatch_is_byte_semantic_with_the_frozen_v1_law() -> None:
    provenance = _provenance()
    scores = _scores(provenance)
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    strategy = retrieval.frozen_retrieval_strategies_v2(80)[4]
    legacy_selected, legacy_trace = retrieval._run_strategy(
        strategy,
        discovery_scores=scores,
        lineup_ids=lineup_ids,
    )
    selected, trace = runner._run_strategy_v2(
        strategy,
        training_scores=scores,
        lineup_ids=lineup_ids,
    )
    assert selected == legacy_selected
    assert trace == legacy_trace


def test_blockmin_trace_publishes_and_replays_the_leximin_vector(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    lineup_ids = [row["lineup_id"] for row in provenance["candidates"]]
    strategy = retrieval.frozen_retrieval_strategies_v2(80)[6]
    selected, base_trace = runner._run_strategy_v2(
        strategy,
        training_scores=scores,
        lineup_ids=lineup_ids,
    )
    trace = runner._trace_evidence(
        strategy=strategy,
        scores=scores,
        lineup_ids=lineup_ids,
        selected=selected,
        base_trace=base_trace,
        blocks=rw.WORLD_BLOCKS,
        worlds_per_block=2,
    )
    for row in trace:
        assert row["objective_law"] == (
            "leximin-ascending-per-block-weighted-coverage"
        )
        assert row["objective_before"]["block_utilities"] == row[
            "base_trace"
        ]["block_utilities_before"]
        assert row["objective_gain"]["block_utility_delta"] == row[
            "base_trace"
        ]["block_utilities_added"]
        assert row["objective_after"]["block_utilities"] == row[
            "base_trace"
        ]["block_utilities_after"]
        assert row["objective_after"]["leximin_profile"] == sorted(
            row["objective_after"]["block_utilities"]
        )


def test_matchup_source_rejects_post_lock_and_tampered_evidence() -> None:
    provenance = _provenance(count=3)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="not point-in-time",
    ):
        runner.build_matchup_source_snapshot(
            slate=SLATE,
            lock_time_utc="2023-09-10T17:00:00Z",
            maximum_source_time_utc="2023-09-10T17:00:00.001Z",
            eligible_players=_eligible_players(provenance),
            annotation_rows=_matchup_rows(provenance),
            player_catalog_identity=_object_identity("player-catalog"),
            annotation_query_receipt_identity=_object_identity("query-receipt"),
        )
    legacy_source = runner.build_matchup_source_snapshot(
        slate=SLATE,
        lock_time_utc="2023-09-10T17:00:00Z",
        maximum_source_time_utc="2023-09-10T16:59:59Z",
        eligible_players=_eligible_players(provenance),
        annotation_rows=_matchup_rows(provenance),
        player_catalog_identity=_object_identity("player-catalog"),
        annotation_query_receipt_identity=_object_identity("query-receipt"),
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="legacy caller-asserted matchup source",
    ):
        runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=legacy_source,
        )

    authority = _matchup_source(provenance)
    source = corrected_source.reopen_matchup_source_snapshot(
        source_export_identity=authority.source_export_identity,
        query_receipt_identity=authority.query_receipt_identity,
        player_catalog_identity=authority.player_catalog_identity,
        read_exact=authority.read_exact,
        expected_slate=authority.expected_slate,
        required_evidence_class=authority.required_evidence_class,
    )
    tampered = deepcopy(source)
    tampered["rows"][0]["matchup_edge_score"] = 999.0
    with pytest.raises(
        corrected_source.CorpusR6MatchupSourceV1Error,
        match="component value|frozen edge|row population",
    ):
        corrected_source.validate_reopened_matchup_source_snapshot(tampered)


def test_non_boolean_qb_depth_is_rejected() -> None:
    provenance = _provenance(count=3)
    eligible = _eligible_players(provenance)
    eligible[0]["qb_depth1"] = 1
    with pytest.raises(
        corrected_source.CorpusR6MatchupSourceV1Error,
        match="QB depth row",
    ):
        _matchup_source(
            provenance, eligible_players=eligible
        )


def test_coherent_reopened_projection_forgery_cannot_cross_runner_boundary() -> None:
    """Rehashing every replay checked below cannot replace an exact reopen."""
    provenance = _provenance(count=3)
    authority = _matchup_source(provenance)
    reopened = corrected_source.reopen_matchup_source_snapshot(
        source_export_identity=authority.source_export_identity,
        query_receipt_identity=authority.query_receipt_identity,
        player_catalog_identity=authority.player_catalog_identity,
        read_exact=authority.read_exact,
        expected_slate=authority.expected_slate,
        required_evidence_class=authority.required_evidence_class,
    )
    forged = deepcopy(reopened)
    forged_row = forged["rows"][0]
    replacement = round(float(forged_row["matchup_edge_score"]) + 0.001, 12)
    forged_row["component_values"] = {
        component: replacement
        for component in forged_row["component_values"]
    }
    forged_row["matchup_edge_score"] = replacement
    rows_sha = corrected_source.canonical_sha256(forged["rows"])
    forged["rows_sha256"] = rows_sha
    replay = forged["component_value_replay"]
    replay["normalized_rows_sha256"] = rows_sha
    deletion = replay["target_week_deletion_proof"]
    deletion["reduction_output"]["percentile_rows_sha256"] = rows_sha
    reduction_sha = corrected_source.canonical_sha256(
        deletion["reduction_output"]
    )
    deletion["full_reduction_sha256"] = reduction_sha
    deletion["deleted_reduction_sha256"] = reduction_sha
    deletion["target_week_deletion_proof_sha256"] = (
        corrected_source.canonical_sha256({
            key: value
            for key, value in deletion.items()
            if key != "target_week_deletion_proof_sha256"
        })
    )
    replay["component_value_replay_sha256"] = (
        corrected_source.canonical_sha256({
            key: value
            for key, value in replay.items()
            if key != "component_value_replay_sha256"
        })
    )

    # This is the exact prior weakness: all retained identities are unchanged
    # and the pure projection/replay validator sees a coherent replacement.
    assert (
        corrected_source.validate_reopened_matchup_source_snapshot(forged)[
            "source_export_identity"
        ]
        == reopened["source_export_identity"]
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="exact-generation reopen authority",
    ):
        runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=forged,
        )


def test_exact_reader_rejects_coherent_export_rehash_under_retained_identity() -> None:
    """A dishonest reader cannot substitute rehashed rows for exact bytes."""
    provenance = _provenance(count=3)
    authority = _matchup_source(provenance)
    source_raw = authority.read_exact(authority.source_export_identity)
    forged_export = json.loads(source_raw)
    forged_row = forged_export["rows"][0]
    replacement = round(float(forged_row["matchup_edge_score"]) + 0.001, 12)
    forged_row["component_values"] = {
        component: replacement
        for component in forged_row["component_values"]
    }
    forged_row["matchup_edge_score"] = replacement
    rows_sha = corrected_source.canonical_sha256(forged_export["rows"])
    forged_export["rows_sha256"] = rows_sha
    replay = forged_export["component_value_replay"]
    replay["normalized_rows_sha256"] = rows_sha
    deletion = replay["target_week_deletion_proof"]
    deletion["reduction_output"]["percentile_rows_sha256"] = rows_sha
    reduction_sha = corrected_source.canonical_sha256(
        deletion["reduction_output"]
    )
    deletion["full_reduction_sha256"] = reduction_sha
    deletion["deleted_reduction_sha256"] = reduction_sha
    deletion["target_week_deletion_proof_sha256"] = (
        corrected_source.canonical_sha256({
            key: value
            for key, value in deletion.items()
            if key != "target_week_deletion_proof_sha256"
        })
    )
    replay["component_value_replay_sha256"] = (
        corrected_source.canonical_sha256({
            key: value
            for key, value in replay.items()
            if key != "component_value_replay_sha256"
        })
    )
    forged_export["matchup_source_export_sha256"] = (
        corrected_source.canonical_sha256({
            key: value
            for key, value in forged_export.items()
            if key != "matchup_source_export_sha256"
        })
    )
    forged_raw = corrected_source.canonical_json_bytes(forged_export)
    assert sha256(forged_raw).hexdigest() != authority.source_export_identity[
        "sha256"
    ]

    def forged_reader(identity: Mapping[str, object]) -> bytes:
        if identity == authority.source_export_identity:
            return forged_raw
        return authority.read_exact(identity)

    forged_authority = runner.MatchupSourceExactReopen(
        source_export_identity=authority.source_export_identity,
        query_receipt_identity=authority.query_receipt_identity,
        player_catalog_identity=authority.player_catalog_identity,
        expected_slate=authority.expected_slate,
        required_evidence_class=authority.required_evidence_class,
        read_exact=forged_reader,
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="exact reopen failed.*content identity differs",
    ):
        runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=forged_authority,
        )


def test_matchup_summary_must_replay_from_its_bound_source() -> None:
    provenance = _provenance(count=3)
    summary = _summary(provenance)
    different_rows = deepcopy(_matchup_rows(provenance))
    different_rows[0]["matchup_edge_score"] = min(
        1.0, float(different_rows[0]["matchup_edge_score"]) + 0.01
    )
    different_source = _matchup_source(provenance, rows=different_rows)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="source binding differs",
    ):
        runner.validate_matchup_lineup_summaries(
            summary,
            provenance=provenance,
            matchup_source=different_source,
        )


def test_matchup_catalog_missing_a_skill_player_fails_closed() -> None:
    provenance = _provenance(count=3)
    eligible = _eligible_players(provenance)[1:]
    rows = [
        row for row in _matchup_rows(provenance)
        if row["gsis_id"] != _eligible_players(provenance)[0]["gsis_id"]
    ]
    source = _matchup_source(
        provenance,
        rows=rows,
        eligible_players=eligible,
    )
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="does not cover exactly eight skill players",
    ):
        runner.build_matchup_lineup_summaries(
            provenance=provenance,
            matchup_source=source,
            minimum_supported_players=1,
            minimum_completeness=0.1,
        )


def test_reconstruction_mismatch_fails_before_selector_dispatch(
    monkeypatch,
) -> None:
    monkeypatch.setattr(retrieval, "WORLDS_PER_BLOCK", 2)
    provenance = _provenance()
    scores = _scores(provenance)
    receipt = _reconstruction(provenance, scores)
    receipt["matrix_binding"]["score_matrix_sha256"] = "0" * 64
    receipt["matrix_binding"]["matrix_binding_sha256"] = canonical_sha256({
        key: value
        for key, value in receipt["matrix_binding"].items()
        if key != "matrix_binding_sha256"
    })
    receipt["reconstruction_sha256"] = canonical_sha256({
        key: value
        for key, value in receipt.items()
        if key != "reconstruction_sha256"
    })

    def selector_must_not_run(*args, **kwargs):
        raise AssertionError("selector dispatched before reconstruction validation")

    monkeypatch.setattr(runner, "_run_strategy_v2", selector_must_not_run)
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match="matrix binding differs",
    ):
        runner.run_fit_scope(
            provenance=provenance,
            union_scores=scores,
            reconstruction_receipt=receipt,
            matchup_summary=_summary(provenance),
            matchup_source=_matchup_source(provenance),
            heldout_block="R4",
            admission_m=80,
            neutral_replicates=1,
            worlds_per_block=2,
            require_authoritative=False,
        )


def test_candidate_provenance_rejects_hidden_outcome_fields() -> None:
    provenance = _provenance()
    provenance["candidates"][0]["actual_points"] = 250.0
    provenance["candidate_provenance_sha256"] = canonical_sha256({
        key: value
        for key, value in provenance.items()
        if key != "candidate_provenance_sha256"
    })
    with pytest.raises(
        runner.CorpusBatchRetrievalV2Error,
        match=r"candidate\[0\] fields differ",
    ):
        runner.build_fit_candidate_view(provenance, heldout_block="R4")
