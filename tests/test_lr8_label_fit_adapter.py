from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_label_fit_adapter as adapter
from nfl_dfs.research import lr8_training_source as source
from nfl_dfs.research import residual_world_columns as rw


def _receipt(uri: str, *, raw: bytes | None = None) -> dict[str, object]:
    body = raw if raw is not None else uri.encode("utf-8")
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(body).hexdigest(),
        "bytes": len(body),
    }


def _create_once_receipt(
    uri: str, value: dict[str, object],
) -> dict[str, object]:
    return {
        **_receipt(uri, raw=adapter.canonical_json(value) + b"\n"),
        "create_only": True,
    }


def _players() -> tuple[rw.PlayerSpec, ...]:
    base = (
        ("q-a", "QB", "A", "B", "g1", 5_000),
        ("rb-c", "RB", "C", "D", "g2", 4_000),
        ("rb-d", "RB", "D", "C", "g2", 4_000),
        ("wr-a", "WR", "A", "B", "g1", 4_000),
        ("wr-b", "WR", "B", "A", "g1", 4_000),
        ("wr-c", "WR", "C", "D", "g2", 4_000),
        ("te-b", "TE", "B", "A", "g1", 4_000),
        ("dst-d", "DST", "D", "C", "g2", 3_000),
    )
    flexible = tuple(
        (
            f"x-{index:02d}",
            "WR",
            "E" if index % 2 == 0 else "F",
            "F" if index % 2 == 0 else "E",
            "g3",
            3_000 + index,
        )
        for index in range(41)
    )
    incumbents = tuple(
        (
            f"y-{index:02d}",
            "WR",
            "G" if index % 2 == 0 else "H",
            "H" if index % 2 == 0 else "G",
            "g4",
            3_100 + index,
        )
        for index in range(40)
    )
    return tuple(sorted((rw.PlayerSpec(
        player_id=player_id,
        position=position,
        team=team,
        opponent=opponent,
        game_id=game_id,
        salary=salary,
    ) for player_id, position, team, opponent, game_id, salary in (
        *base, *flexible, *incumbents
    )), key=lambda row: row.player_id))


def _roster(prefix: str, index: int) -> tuple[str, ...]:
    return tuple(sorted((
        "q-a",
        "rb-c",
        "rb-d",
        "wr-a",
        "wr-b",
        "wr-c",
        "te-b",
        "dst-d",
        f"{prefix}-{index:02d}",
    )))


def _candidate_payload(candidate: source.FrozenCandidate) -> dict[str, object]:
    return {
        "season": candidate.season,
        "week": candidate.week,
        "roster": list(candidate.roster),
        "anatomy_features": [
            int(value) if float(value).is_integer() else float(value)
            for value in candidate.anatomy_features
        ],
        "first_source_block": candidate.first_source_block,
        "first_source_world_index": candidate.first_source_world_index,
        "source_occurrences": [list(value) for value in candidate.source_occurrences],
    }


def _block(
    *,
    season: int,
    week: int,
    block: str,
    players: tuple[rw.PlayerSpec, ...],
    roster_indexes: tuple[int, ...],
    draws: np.ndarray,
) -> source.FrozenBlockSource:
    projection_seed, role_seed = source.BLOCK_SEED_PAIRS[block]
    candidates = tuple(source.FrozenCandidate(
        season=season,
        week=week,
        roster=_roster("x", index),
        anatomy_features=lr8.lineup_anatomy(players, _roster("x", index)),
        first_source_block=block,
        first_source_world_index=solve_index,
        source_occurrences=((block, solve_index),),
    ) for solve_index, index in enumerate(roster_indexes))
    attempts = tuple(source.SolveAttempt(
        block=block,
        projection_seed=projection_seed,
        world_index=index,
        roster=candidate.roster,
        objective_micro=(index + 1) * rw.MICRO_DK_SCALE,
        admitted_unique=True,
        request_sha256=sha256(
            f"request/{season}/{week}/{block}/{index}".encode()
        ).hexdigest(),
        evidence_receipts=(_receipt(
            f"gs://test/evidence/{season}/{week}/{block}/{index}"
        ),),
        evidence_manifest_sha256=adapter.canonical_sha256([_receipt(
            f"gs://test/evidence/{season}/{week}/{block}/{index}"
        )]),
    ) for index, candidate in enumerate(candidates))
    attempt_payload = [{
        "block": row.block,
        "projection_seed": row.projection_seed,
        "world_index": row.world_index,
        "roster": list(row.roster),
        "objective_micro": row.objective_micro,
        "admitted_unique": row.admitted_unique,
        "request_sha256": row.request_sha256,
        "evidence_receipts": list(row.evidence_receipts),
        "evidence_manifest_sha256": row.evidence_manifest_sha256,
    } for row in attempts]
    candidate_payload = [list(row.roster) for row in candidates]
    anatomy_payload = [{
        "roster": list(row.roster),
        "features": _candidate_payload(row)["anatomy_features"],
    } for row in candidates]
    legality_payload = [{
        "roster": list(row.roster),
        "hard_domain_id": source.HARD_DOMAIN_ID,
        "dk_classic_legal": True,
        "former_house_rules_applied": [],
    } for row in candidates]
    ids = tuple(player.player_id for player in players)
    return source.FrozenBlockSource(
        block=block,
        projection_seed=projection_seed,
        source_environment_role_seed_nonoperative=role_seed,
        player_ids=ids,
        player_draws=draws,
        player_ids_sha256=source.player_ids_sha256(ids),
        player_draws_sha256=source.array_sha256(draws),
        world_order=tuple(range(source.WORLDS_PER_BLOCK)),
        world_order_sha256=adapter.canonical_sha256(
            list(range(source.WORLDS_PER_BLOCK))
        ),
        source_receipts=(_receipt(
            f"gs://test/worlds/{season}/{week}/{block}"
        ),),
        solve_attempts=attempts,
        solve_attempts_sha256=adapter.canonical_sha256(attempt_payload),
        candidates=candidates,
        candidate_identities_sha256=adapter.canonical_sha256(candidate_payload),
        anatomy_sha256=adapter.canonical_sha256(anatomy_payload),
        legality_sha256=adapter.canonical_sha256(legality_payload),
    )


def _merge(
    blocks: tuple[source.FrozenBlockSource, ...],
) -> tuple[source.FrozenCandidate, ...]:
    order: list[tuple[str, ...]] = []
    first: dict[tuple[str, ...], source.FrozenCandidate] = {}
    occurrences: dict[tuple[str, ...], list[tuple[str, int]]] = {}
    for block in blocks:
        for candidate in block.candidates:
            if candidate.roster not in first:
                first[candidate.roster] = candidate
                order.append(candidate.roster)
            occurrences.setdefault(candidate.roster, []).extend(
                candidate.source_occurrences
            )
    return tuple(source.FrozenCandidate(
        season=first[roster].season,
        week=first[roster].week,
        roster=roster,
        anatomy_features=first[roster].anatomy_features,
        first_source_block=first[roster].first_source_block,
        first_source_world_index=first[roster].first_source_world_index,
        source_occurrences=tuple(occurrences[roster]),
    ) for roster in order)


def _source_freeze(*, unequal_first_slate: bool = False):
    players = _players()
    draws = np.zeros(
        (len(players), source.WORLDS_PER_BLOCK), dtype=np.float32
    )
    incumbent = tuple(_roster("y", index) for index in range(40))
    slates: list[source.FrozenTrainingSlate] = []
    for slate_index, (season, week) in enumerate(source.EXPECTED_SLATE_KEYS):
        r0_indexes = tuple(range(40))
        r1_indexes = (
            tuple(range(1, 41))
            if unequal_first_slate and slate_index == 0
            else tuple(range(40))
        )
        blocks = (
            _block(
                season=season,
                week=week,
                block="R0",
                players=players,
                roster_indexes=r0_indexes,
                draws=draws,
            ),
            _block(
                season=season,
                week=week,
                block="R1",
                players=players,
                roster_indexes=r1_indexes,
                draws=draws,
            ),
        )
        pre = tuple(candidate for block in blocks for candidate in block.candidates)
        post = _merge(blocks)
        slates.append(source.FrozenTrainingSlate(
            season=season,
            week=week,
            players=players,
            incumbent_candidates=incumbent,
            catalog_sha256=source.catalog_sha256(players),
            incumbent_candidates_sha256=source.identities_sha256(incumbent),
            catalog_source_receipts=(_receipt(
                f"gs://test/catalog/{season}/{week}"
            ),),
            incumbent_source_receipts=(_receipt(
                f"gs://test/incumbent/{season}/{week}"
            ),),
            blocks=blocks,
            pre_cross_block_candidate_count=len(pre),
            pre_cross_block_sha256=adapter.canonical_sha256([
                _candidate_payload(row) for row in pre
            ]),
            post_cross_block_candidates=post,
            post_cross_block_sha256=adapter.canonical_sha256([
                _candidate_payload(row) for row in post
            ]),
            cross_block_duplicates=len(pre) - len(post),
        ))
    replay_blocks = tuple(source.PITReplayBlock(
        target_season=season,
        block=block,
        projection_seed=source.BLOCK_SEED_PAIRS[block][0],
        source_environment_role_seed_nonoperative=(
            source.BLOCK_SEED_PAIRS[block][1]
        ),
        replay_path_id=source.PIT_REPLAY_PATH_ID,
        model_training_seasons=source.MODEL_TRAINING_SEASONS[season],
        model_fit_input_sha256=sha256(f"fit-input/{season}".encode()).hexdigest(),
        model_fit_sha256=sha256(f"fit/{season}".encode()).hexdigest(),
        fit_source_receipts=(_receipt(f"gs://test/fit/{season}"),),
        slates=(),
    ) for season in source.TARGET_SEASONS for block in source.BLOCK_ORDER)
    bundle = source.TrainingSourceBundle(
        protocol_id=source.PROTOCOL_ID,
        version=source.SOURCE_VERSION,
        canonical_panel_id=source.CANONICAL_PANEL_ID,
        target_seasons=source.TARGET_SEASONS,
        slate_keys=source.EXPECTED_SLATE_KEYS,
        replay_blocks=replay_blocks,
        slates=tuple(slates),
    )
    frozen = source.freeze_training_source(bundle)
    receipt = _receipt(
        "gs://test/full/training-source-freeze.json",
        raw=adapter.canonical_json(frozen) + b"\n",
    )
    return frozen, receipt, players


def _score_map(
    frozen: dict[str, object],
    source_receipt: dict[str, object],
    players: tuple[rw.PlayerSpec, ...],
):
    rows: list[dict[str, object]] = []
    for season, week in source.EXPECTED_SLATE_KEYS:
        for player in players:
            if player.player_id in {
                "q-a", "rb-c", "rb-d", "wr-a", "wr-b", "wr-c", "te-b", "dst-d",
            }:
                score = 20 * rw.MICRO_DK_SCALE
            elif player.player_id.startswith("x-"):
                index = int(player.player_id.split("-")[1])
                score = (
                    39 if index < 19 else 40 if index == 19 else 41
                ) * rw.MICRO_DK_SCALE
            else:
                score = 0
            rows.append({
                "season": season,
                "week": week,
                "player_id": player.player_id,
                "position": player.position,
                "realized_score_micro": score,
                "actual_source": (
                    adapter.DST_ACTUAL_SOURCE
                    if player.position == "DST"
                    else adapter.SKILL_ACTUAL_SOURCE
                ),
            })
    universe = [{
        "season": season,
        "week": week,
        "player_id": player.player_id,
        "position": player.position,
    } for season, week in source.EXPECTED_SLATE_KEYS for player in players]
    lease_body = {
        "version": adapter.HISTORICAL_OUTCOME_LEASE_VERSION,
        "run_id": "20260821-lr8-label-fit-v1",
        "job": "atlas-md-prefix-r4-smoke",
        "code_sha": "1" * 40,
        "image": "us-central1-docker.pkg.dev/test/repo/image@sha256:" + "2" * 64,
        "acquired_at": "2026-08-21T00:00:00+00:00",
    }
    lease = {
        "body": lease_body,
        "object_receipt": _create_once_receipt(
            adapter.HISTORICAL_OUTCOME_LEASE_URI, lease_body
        ),
    }
    attempt = {
        "schema": adapter.LABEL_READ_ATTEMPT_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": adapter.SCORE_SUPPLIER_BOUNDARY,
        "stage": "before-authoritative-score-query",
        "training_source_manifest_sha256": frozen["manifest_sha256"],
        "training_source_object": source_receipt,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "query_identity": adapter.authoritative_query_identity(),
        "query_sha256": adapter.AUTHORITATIVE_QUERY_SHA256,
        "historical_outcome_lease": lease,
        "started_at": "2026-08-21T00:00:01+00:00",
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    output_root = f"{adapter.SCORE_OUTPUT_ROOT}/{lease_body['run_id']}"
    attempt_receipt = _create_once_receipt(
        f"{output_root}/label-read-attempt.json", attempt
    )
    catalog_keys = [{
        "season": season,
        "week": week,
        "source_kind": "dst" if player.position == "DST" else "skill",
        "source_key": (
            player.team.upper() if player.position == "DST" else player.player_id
        ),
        "player_id": player.player_id,
        "position": player.position,
    } for season, week in source.EXPECTED_SLATE_KEYS for player in players]
    score_by_player = {
        (row["season"], row["week"], row["player_id"]): row["realized_score_micro"]
        for row in rows
    }
    source_rows = sorted(({
        "season": row["season"],
        "week": row["week"],
        "source_kind": row["source_kind"],
        "source_key": row["source_key"],
        "realized_score_micro": score_by_player[
            (row["season"], row["week"], row["player_id"])
        ],
    } for row in catalog_keys), key=lambda row: (
        row["season"], row["week"], row["source_kind"], row["source_key"]
    ))
    parameters = [{
        "name": "source_snapshot_at", "type": "TIMESTAMP", "array": False,
        "value": "2026-08-21T00:00:02+00:00",
    }]
    parameters_sha = sha256(adapter.canonical_json(parameters) + b"\n").hexdigest()
    source_extract = {
        "schema": adapter.SCORE_SOURCE_EXTRACT_VERSION,
        "supplier_version": adapter.SCORE_SUPPLIER_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": adapter.SCORE_SUPPLIER_BOUNDARY,
        "training_source_manifest_sha256": frozen["manifest_sha256"],
        "training_source_object": source_receipt,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "catalog_universe_sha256": adapter.canonical_sha256(universe),
        "catalog_keys": catalog_keys,
        "catalog_keys_sha256": adapter.canonical_sha256(catalog_keys),
        "query_identity": adapter.authoritative_query_identity(),
        "query_sha256": adapter.AUTHORITATIVE_QUERY_SHA256,
        "sql_sha256": adapter.AUTHORITATIVE_SQL_SHA256,
        "parameters": parameters,
        "parameters_sha256": parameters_sha,
        "source_snapshot_at": "2026-08-21T00:00:02+00:00",
        "job_receipt": {
            "sql_sha256": adapter.AUTHORITATIVE_SQL_SHA256,
            "parameters_sha256": parameters_sha,
            "error_result": None,
        },
        "table_receipts": [{
            "table_id": "nfl-predictions-503414.nfl_features.player_week_actuals",
        }, {
            "table_id": "nfl-predictions-503414.nfl_features.team_defense_week",
        }],
        "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True,
        "label_read_attempt": attempt,
        "label_read_attempt_receipt": attempt_receipt,
        "row_fields": list(adapter.SCORE_SOURCE_ROW_FIELDS),
        "rows": source_rows,
        "rows_sha256": adapter.canonical_sha256(source_rows),
        "query_completed_at": "2026-08-21T00:00:03+00:00",
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    source_extract_receipt = _create_once_receipt(
        f"{output_root}/authoritative-score-source.json", source_extract
    )
    score_map = {
        "schema": adapter.SCORE_MAP_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": adapter.SCORE_SUPPLIER_BOUNDARY,
        "training_source_manifest_sha256": frozen["manifest_sha256"],
        "training_source_object": source_receipt,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "row_fields": list(adapter.SCORE_ROW_FIELDS),
        "score_unit": adapter.SCORE_UNIT,
        "catalog_universe_sha256": adapter.canonical_sha256(universe),
        "authoritative_source_id": adapter.AUTHORITATIVE_SOURCE_ID,
        "query_identity": adapter.authoritative_query_identity(),
        "query_sha256": adapter.AUTHORITATIVE_QUERY_SHA256,
        "score_source_receipts": ({
            key: source_extract_receipt[key]
            for key in ("uri", "generation", "sha256", "bytes")
        },),
        "score_source_extract": source_extract,
        "score_source_extract_receipt": source_extract_receipt,
        "label_read_attempt": attempt,
        "label_read_attempt_receipt": attempt_receipt,
        "rows": rows,
        "score_rows_sha256": adapter.canonical_sha256(rows),
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    receipt = _create_once_receipt(
        f"{output_root}/authoritative-score-map.json", score_map
    )
    return score_map, receipt


def _fixture(*, unequal_first_slate: bool = False):
    frozen, source_receipt, players = _source_freeze(
        unequal_first_slate=unequal_first_slate
    )
    score_map, score_receipt = _score_map(frozen, source_receipt, players)
    return frozen, source_receipt, score_map, score_receipt


def _rehash_source(frozen: dict[str, object]):
    frozen["manifest_sha256"] = adapter.canonical_sha256({
        key: value for key, value in frozen.items() if key != "manifest_sha256"
    })
    return _receipt(
        "gs://test/full/training-source-freeze.json",
        raw=adapter.canonical_json(frozen) + b"\n",
    )


def _rehash_score(score_map: dict[str, object]):
    try:
        score_map["score_rows_sha256"] = adapter.canonical_sha256(
            score_map["rows"]
        )
    except adapter.LR8LabelFitError:
        # A non-finite poison is intentionally not canonicalizable.  The
        # adapter validates row values before the external object binding.
        return _receipt(
            score_map["score_source_extract_receipt"]["uri"], raw=b"noncanonical"
        )
    run_id = score_map["label_read_attempt"]["historical_outcome_lease"]["body"][
        "run_id"
    ]
    return _create_once_receipt(
        f"{adapter.SCORE_OUTPUT_ROOT}/{run_id}/authoritative-score-map.json",
        score_map,
    )


def _rehash_extract(score_map: dict[str, object]):
    extract = score_map["score_source_extract"]
    extract["rows_sha256"] = adapter.canonical_sha256(extract["rows"])
    run_id = score_map["label_read_attempt"]["historical_outcome_lease"]["body"][
        "run_id"
    ]
    receipt = _create_once_receipt(
        f"{adapter.SCORE_OUTPUT_ROOT}/{run_id}/authoritative-score-source.json",
        extract,
    )
    score_map["score_source_extract_receipt"] = receipt
    score_map["score_source_receipts"] = ({
        key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
    },)
    return _rehash_score(score_map)


def _rehash_attempt(score_map: dict[str, object]):
    attempt = score_map["label_read_attempt"]
    run_id = attempt["historical_outcome_lease"]["body"]["run_id"]
    score_map["label_read_attempt_receipt"] = _create_once_receipt(
        f"{adapter.SCORE_OUTPUT_ROOT}/{run_id}/label-read-attempt.json", attempt
    )
    return _rehash_score(score_map)


def _rehash_fit(fit: dict[str, object]) -> None:
    fit["freeze_sha256"] = adapter.canonical_sha256({
        key: value for key, value in fit.items() if key != "freeze_sha256"
    })


@pytest.fixture(scope="module")
def exact_fixture():
    return _fixture()


def test_complete_source_labels_boundary_and_freezes_deterministically(exact_fixture):
    frozen, source_receipt, score_map, score_receipt = exact_fixture
    first = adapter.fit_and_freeze(
        training_source_freeze=frozen,
        expected_source_manifest_sha256=frozen["manifest_sha256"],
        training_source_receipt=source_receipt,
        authoritative_score_map=score_map,
        authoritative_score_map_receipt=score_receipt,
    )
    second = adapter.fit_and_freeze(
        training_source_freeze=deepcopy(frozen),
        expected_source_manifest_sha256=frozen["manifest_sha256"],
        training_source_receipt=deepcopy(source_receipt),
        authoritative_score_map=deepcopy(score_map),
        authoritative_score_map_receipt=deepcopy(score_receipt),
    )
    assert adapter.canonical_json(first) == adapter.canonical_json(second)
    assert first["labels"]["row_count"] == 35 * 40
    by_flex = {
        next(player for player in row["roster"] if player.startswith("x-")): row
        for row in first["labels"]["rows"]
        if row["season"] == 2019 and row["week"] == 1
    }
    assert by_flex["x-18"]["realized_total_micro"] == 199 * rw.MICRO_DK_SCALE
    assert by_flex["x-18"]["label_200_plus"] is False
    assert by_flex["x-19"]["realized_total_micro"] == 200 * rw.MICRO_DK_SCALE
    assert by_flex["x-19"]["label_200_plus"] is True
    assert first["fit_law"]["feature_sweep"] is False
    assert first["fit_law"]["hyperparameter_sweep"] is False
    assert first["anatomy_artifact"]["sample_weight"] == (
        "equal_total_weight_per_season_week"
    )
    assert all(value is False for value in first["licenses"].values())
    assert adapter.validate_label_fit_freeze(
        first, expected_freeze_sha256=first["freeze_sha256"]
    ) == first


def test_public_source_surface_contains_only_identity_and_anatomy(exact_fixture):
    frozen, receipt, _, _ = exact_fixture
    rows = adapter.frozen_fit_candidates(
        frozen,
        expected_manifest_sha256=frozen["manifest_sha256"],
        training_source_receipt=receipt,
    )
    assert len(rows) == 35 * 40
    assert rows[0].__slots__ == (
        "season", "week", "roster", "anatomy_features"
    )
    assert not hasattr(rows[0], "objective_micro")
    assert not hasattr(rows[0], "player_draws")


def test_source_pin_object_and_schema_drift_fail_closed(exact_fixture):
    frozen, source_receipt, score_map, score_receipt = exact_fixture
    with pytest.raises(adapter.LR8LabelFitError, match="manifest hash"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256="f" * 64,
            training_source_receipt=source_receipt,
            authoritative_score_map=score_map,
            authoritative_score_map_receipt=score_receipt,
        )
    bad_receipt = dict(source_receipt)
    bad_receipt["sha256"] = "0" * 64
    with pytest.raises(adapter.LR8LabelFitError, match="canonical object bytes"):
        adapter.frozen_fit_candidates(
            frozen,
            expected_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=bad_receipt,
        )
    drifted = deepcopy(frozen)
    drifted["b1_candidate_score"] = False
    receipt = _rehash_source(drifted)
    with pytest.raises(adapter.LR8LabelFitError, match="schema differs"):
        adapter.frozen_fit_candidates(
            drifted,
            expected_manifest_sha256=drifted["manifest_sha256"],
            training_source_receipt=receipt,
        )


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda rows: rows.pop(), "not exact"),
        (
            lambda rows: rows.append({
                **rows[-1],
                "player_id": "unknown-extra-player",
            }),
            "extra player",
        ),
        (lambda rows: rows.append(dict(rows[0])), "repeat"),
        (
            lambda rows: rows[0].__setitem__("realized_score_micro", float("nan")),
            "exact integer",
        ),
        (
            lambda rows: rows[0].__setitem__(
                "actual_source", adapter.SKILL_ACTUAL_SOURCE
            ),
            "source mapping differs",
        ),
    ],
)
def test_score_reconciliation_rejects_missing_duplicate_nonfinite_and_source(
    exact_fixture, mutator, message,
):
    frozen, source_receipt, original, _ = exact_fixture
    score_map = deepcopy(original)
    mutator(score_map["rows"])
    score_receipt = _rehash_score(score_map)
    with pytest.raises(adapter.LR8LabelFitError, match=message):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=score_map,
            authoritative_score_map_receipt=score_receipt,
        )


def test_score_object_hash_and_schema_are_exact(exact_fixture):
    frozen, source_receipt, score_map, score_receipt = exact_fixture
    stale = dict(score_receipt)
    stale["sha256"] = "0" * 64
    with pytest.raises(adapter.LR8LabelFitError, match="canonical object bytes"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=score_map,
            authoritative_score_map_receipt=stale,
        )
    poisoned = deepcopy(score_map)
    poisoned["rows"][0]["b1_probability"] = 0.9
    poisoned_receipt = _rehash_score(poisoned)
    with pytest.raises(adapter.LR8LabelFitError, match="B1 fields are forbidden"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=poisoned,
            authoritative_score_map_receipt=poisoned_receipt,
        )


def test_score_source_extract_is_transitively_replayed(exact_fixture):
    frozen, source_receipt, original, _ = exact_fixture
    changed_row = deepcopy(original)
    changed_row["score_source_extract"]["rows"][0][
        "realized_score_micro"
    ] += 1
    with pytest.raises(adapter.LR8LabelFitError, match="source extract"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=changed_row,
            authoritative_score_map_receipt=_rehash_extract(changed_row),
        )

    wrong_sql = deepcopy(original)
    wrong_sql["score_source_extract"]["sql_sha256"] = "9" * 64
    wrong_sql["score_source_extract"]["job_receipt"]["sql_sha256"] = "9" * 64
    with pytest.raises(adapter.LR8LabelFitError, match="score-source boundary"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=wrong_sql,
            authoritative_score_map_receipt=_rehash_extract(wrong_sql),
        )


def test_2023_plus_and_b1_later_period_inputs_are_forbidden(exact_fixture):
    frozen, source_receipt, original, _ = exact_fixture
    score_map = deepcopy(original)
    score_map["rows"][0]["season"] = 2023
    score_receipt = _rehash_score(score_map)
    with pytest.raises(adapter.LR8LabelFitError, match=r"2023\+"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=score_map,
            authoritative_score_map_receipt=score_receipt,
        )
    for field in ("b1_inputs_used", "later_period_inputs_used"):
        poisoned = deepcopy(original)
        poisoned[field] = True
        receipt = _rehash_score(poisoned)
        with pytest.raises(adapter.LR8LabelFitError, match=field):
            adapter.fit_and_freeze(
                training_source_freeze=frozen,
                expected_source_manifest_sha256=frozen["manifest_sha256"],
                training_source_receipt=source_receipt,
                authoritative_score_map=poisoned,
                authoritative_score_map_receipt=receipt,
            )


def test_registered_query_and_lease_protected_attempt_are_exact(exact_fixture):
    frozen, source_receipt, original, _ = exact_fixture

    wrong_query = deepcopy(original)
    wrong_query["query_sha256"] = "a" * 64
    with pytest.raises(adapter.LR8LabelFitError, match="score-map boundary"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=wrong_query,
            authoritative_score_map_receipt=_rehash_score(wrong_query),
        )

    b1_attempt = deepcopy(original)
    b1_attempt["label_read_attempt"]["b1_inputs_used"] = True
    with pytest.raises(adapter.LR8LabelFitError, match="attempt b1_inputs_used"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=b1_attempt,
            authoritative_score_map_receipt=_rehash_attempt(b1_attempt),
        )

    stale_lease = deepcopy(original)
    stale_lease["label_read_attempt"]["historical_outcome_lease"]["body"][
        "acquired_at"
    ] = "2026-08-21T00:00:00.500000+00:00"
    with pytest.raises(adapter.LR8LabelFitError, match="lease receipt"):
        adapter.fit_and_freeze(
            training_source_freeze=frozen,
            expected_source_manifest_sha256=frozen["manifest_sha256"],
            training_source_receipt=source_receipt,
            authoritative_score_map=stale_lease,
            authoritative_score_map_receipt=_rehash_attempt(stale_lease),
        )


def test_equal_slate_weighting_is_exact_when_cell_sizes_differ(monkeypatch):
    # This synthetic lattice holds most anatomy coordinates exactly constant.
    # Unequal floating weights can leave sub-epsilon variance in those
    # artificial coordinates, so isolate the weighting assertion from the
    # fixed-point range guard.  The non-mocked exact fit is exercised above.
    monkeypatch.setattr(
        lr8,
        "_quantize_anatomy_linear_law",
        lambda means, scales, coefficients, intercept: (
            (0,) * len(lr8.ANATOMY_FEATURES), 0, 0
        ),
    )
    frozen, source_receipt, score_map, score_receipt = _fixture(
        unequal_first_slate=True
    )
    fit = adapter.fit_and_freeze(
        training_source_freeze=frozen,
        expected_source_manifest_sha256=frozen["manifest_sha256"],
        training_source_receipt=source_receipt,
        authoritative_score_map=score_map,
        authoritative_score_map_receipt=score_receipt,
    )
    weighting = fit["weighting"]
    assert weighting["training_rows"] == 35 * 40 + 1
    first, second = weighting["cells"][:2]
    assert first["candidate_rows"] == 41
    assert second["candidate_rows"] == 40
    assert first["cell_total_weight_numerator"] == second[
        "cell_total_weight_numerator"
    ]
    assert first["cell_total_weight_denominator"] == second[
        "cell_total_weight_denominator"
    ] == 35
    assert first["normalized_row_weight_denominator"] == 35 * 41
    assert second["normalized_row_weight_denominator"] == 35 * 40


def test_create_once_freeze_validator_rejects_license_or_body_drift(exact_fixture):
    frozen, source_receipt, score_map, score_receipt = exact_fixture
    fit = adapter.fit_and_freeze(
        training_source_freeze=frozen,
        expected_source_manifest_sha256=frozen["manifest_sha256"],
        training_source_receipt=source_receipt,
        authoritative_score_map=score_map,
        authoritative_score_map_receipt=score_receipt,
    )
    licensed = deepcopy(fit)
    licensed["licenses"]["adoption_licensed"] = True
    licensed["freeze_sha256"] = adapter.canonical_sha256({
        key: value for key, value in licensed.items() if key != "freeze_sha256"
    })
    with pytest.raises(adapter.LR8LabelFitError, match="adoption_licensed"):
        adapter.validate_label_fit_freeze(
            licensed, expected_freeze_sha256=licensed["freeze_sha256"]
        )
    drifted = deepcopy(fit)
    drifted["labels"]["rows"][0]["realized_total_micro"] += 1
    with pytest.raises(adapter.LR8LabelFitError, match="freeze hash"):
        adapter.validate_label_fit_freeze(
            drifted, expected_freeze_sha256=fit["freeze_sha256"]
        )


def test_freeze_validator_replays_lattice_labels_totals_weighting_and_fit(exact_fixture):
    frozen, source_receipt, score_map, score_receipt = exact_fixture
    fit = adapter.fit_and_freeze(
        training_source_freeze=frozen,
        expected_source_manifest_sha256=frozen["manifest_sha256"],
        training_source_receipt=source_receipt,
        authoritative_score_map=score_map,
        authoritative_score_map_receipt=score_receipt,
    )

    later_slate = deepcopy(fit)
    later_slate["labels"]["rows"][0]["season"] = 2023
    later_slate["labels"]["rows_sha256"] = adapter.canonical_sha256(
        later_slate["labels"]["rows"]
    )
    _rehash_fit(later_slate)
    with pytest.raises(adapter.LR8LabelFitError, match="non-2019/2021"):
        adapter.validate_label_fit_freeze(
            later_slate, expected_freeze_sha256=later_slate["freeze_sha256"]
        )

    false_boundary = deepcopy(fit)
    boundary = next(
        row for row in false_boundary["labels"]["rows"]
        if row["realized_total_micro"] == lr8.ANATOMY_LABEL_MICRO
    )
    boundary["label_200_plus"] = False
    false_boundary["labels"]["positive_rows"] -= 1
    false_boundary["labels"]["rows_sha256"] = adapter.canonical_sha256(
        false_boundary["labels"]["rows"]
    )
    _rehash_fit(false_boundary)
    with pytest.raises(adapter.LR8LabelFitError, match=r">=200 label"):
        adapter.validate_label_fit_freeze(
            false_boundary,
            expected_freeze_sha256=false_boundary["freeze_sha256"],
        )

    wrong_total = deepcopy(fit)
    stable_label = next(
        row for row in wrong_total["labels"]["rows"]
        if row["realized_total_micro"] > lr8.ANATOMY_LABEL_MICRO
    )
    stable_label["realized_total_micro"] += 1
    wrong_total["labels"]["rows_sha256"] = adapter.canonical_sha256(
        wrong_total["labels"]["rows"]
    )
    _rehash_fit(wrong_total)
    with pytest.raises(adapter.LR8LabelFitError, match="does not replay"):
        adapter.validate_label_fit_freeze(
            wrong_total, expected_freeze_sha256=wrong_total["freeze_sha256"]
        )

    wrong_weight = deepcopy(fit)
    wrong_weight["weighting"]["cells"][0]["candidate_rows"] += 1
    wrong_weight["weighting"]["cells_sha256"] = adapter.canonical_sha256(
        wrong_weight["weighting"]["cells"]
    )
    _rehash_fit(wrong_weight)
    with pytest.raises(adapter.LR8LabelFitError, match="equal-slate weighting"):
        adapter.validate_label_fit_freeze(
            wrong_weight, expected_freeze_sha256=wrong_weight["freeze_sha256"]
        )

    swept = deepcopy(fit)
    swept["fit_law"]["hyperparameter_sweep"] = True
    _rehash_fit(swept)
    with pytest.raises(adapter.LR8LabelFitError, match="fixed/no-sweep"):
        adapter.validate_label_fit_freeze(
            swept, expected_freeze_sha256=swept["freeze_sha256"]
        )
