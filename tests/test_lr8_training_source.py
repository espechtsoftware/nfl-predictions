from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from itertools import combinations, product

import numpy as np
import pytest

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_training_source as source
from nfl_dfs.research import residual_world_columns as rw


def _receipt(uri: str) -> dict[str, object]:
    object_name = uri.removeprefix("mock://").lstrip("/")
    gcs_uri = f"gs://lr8-test/{object_name}"
    raw = gcs_uri.encode("utf-8")
    return {
        "uri": gcs_uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _players() -> tuple[dict[str, object], ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-a", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"),
        ("wr-a1", "WR", "A", "B", "g1"),
        ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-d", "TE", "D", "C", "g2"),
        ("dst-a", "DST", "A", "B", "g1"),
        ("dst-c", "DST", "C", "D", "g2"),
    )
    return tuple({
        "id": player_id,
        "pos": position,
        "team": team,
        "opp": opponent,
        "game_id": game,
        "salary": 5_000,
    } for player_id, position, team, opponent, game in rows)


def _legal_rosters(
    players: tuple[dict[str, object], ...], count: int,
) -> tuple[tuple[str, ...], ...]:
    by_position: dict[str, list[str]] = {}
    for row in players:
        by_position.setdefault(str(row["pos"]), []).append(str(row["id"]))
    specs = tuple(rw.PlayerSpec.from_mapping(row) for row in players)
    output: list[tuple[str, ...]] = []
    for qb, rbs, wrs, te, dst in product(
        by_position["QB"],
        combinations(by_position["RB"], 2),
        combinations(by_position["WR"], 4),
        by_position["TE"],
        by_position["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            lr8.audit_dk_classic_identity(specs, roster)
        except lr8.LR8Error:
            continue
        if roster not in output:
            output.append(roster)
        if len(output) == count:
            return tuple(output)
    raise AssertionError("synthetic catalog cannot form enough legal rosters")


def _small_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(source, "TARGET_SEASONS", (2019,))
    monkeypatch.setattr(source, "EXPECTED_WEEKS", {2019: (1,)})
    monkeypatch.setattr(source, "EXPECTED_SLATE_KEYS", ((2019, 1),))
    monkeypatch.setattr(source, "EXPECTED_SLATES", 1)
    monkeypatch.setattr(source, "WORLDS_PER_BLOCK", 96)


def _solve_response(
    request: source.WorldSolveRequest,
    roster: tuple[str, ...],
) -> source.ExactWorldOptimum:
    by_id = {
        player.player_id: index
        for index, player in enumerate(request.players)
    }
    objective = int(np.rint(
        request.player_scores[[by_id[player] for player in roster]].astype(
            np.float64
        ) * rw.MICRO_DK_SCALE
    ).astype(np.int64).sum(dtype=np.int64))
    return source.ExactWorldOptimum(
        roster=roster,
        request_sha256=request.request_sha256,
        objective_micro=objective,
        evidence_receipts=(_receipt(
            f"mock://solve/{request.block}/{request.world_index}"
        ),),
        exact_optimal=True,
        canonical_roster_tiebreak=True,
        dk_classic_only=True,
        incumbent_no_goods_enforced=True,
    )


def _fixture(monkeypatch: pytest.MonkeyPatch):
    _small_contract(monkeypatch)
    players = _players()
    rosters = _legal_rosters(players, 41)
    incumbent = (rosters[0],)
    candidates = rosters[1:]
    catalog_digest = source.catalog_sha256(players)
    incumbent_digest = source.identities_sha256(incumbent)
    canonical = source.CanonicalSlateSource(
        season=2019,
        week=1,
        panel_id=source.CANONICAL_PANEL_ID,
        players=players,
        incumbent_candidates=incumbent,
        catalog_sha256=catalog_digest,
        incumbent_candidates_sha256=incumbent_digest,
        catalog_source_receipts=(_receipt("mock://catalog/2019/1"),),
        incumbent_source_receipts=(_receipt("mock://incumbent/2019/1"),),
    )

    ids = tuple(str(row["id"]) for row in reversed(players))
    # Every row has the same strict descending total, so the registered
    # world order is exactly 0..95 and its index tie-break is unexercised.
    vector = np.arange(96, 0, -1, dtype=np.float32)
    draws = np.stack([
        vector + np.float32(index / 1000)
        for index in range(len(ids))
    ]).astype(np.float32)
    slate = source.ReplaySlateWorlds(
        season=2019,
        week=1,
        player_ids=ids,
        player_draws=draws,
        player_ids_sha256=source.player_ids_sha256(ids),
        player_draws_sha256=source.array_sha256(draws),
        source_receipts=(_receipt("mock://worlds/2019/1"),),
    )
    blocks = tuple(source.PITReplayBlock(
        target_season=2019,
        block=block,
        projection_seed=seeds[0],
        source_environment_role_seed_nonoperative=seeds[1],
        replay_path_id=source.PIT_REPLAY_PATH_ID,
        model_training_seasons=(2015, 2016, 2017, 2018),
        model_fit_input_sha256="1" * 64,
        model_fit_sha256="2" * 64,
        fit_source_receipts=(_receipt("mock://fit/2019"),),
        slates=(replace(
            slate,
            source_receipts=(_receipt(f"mock://worlds/2019/1/{block}"),),
        ),),
    ) for block, seeds in source.BLOCK_SEED_PAIRS.items())

    requests: list[source.WorldSolveRequest] = []

    def solve(request: source.WorldSolveRequest) -> source.ExactWorldOptimum:
        requests.append(request)
        assert request.player_scores.flags.writeable is False
        assert request.incumbent_no_goods == incumbent
        assert request.candidate_world_family == "baseline_player_draws"
        assert request.role_belief_worlds_used is False
        assert not hasattr(request, "role_seed")
        # World 1 deliberately repeats world 0. Forty unique rows therefore
        # require exactly 41 visits; the dose itself remains forty.
        candidate_index = 0 if request.world_index <= 1 else request.world_index - 1
        roster = candidates[candidate_index]
        return _solve_response(request, roster)

    return canonical, blocks, solve, requests


def test_scientific_constants_are_exact():
    assert source.TARGET_SEASONS == (2019, 2021)
    assert source.MODEL_TRAINING_SEASONS == {
        2019: (2015, 2016, 2017, 2018),
        2021: (2015, 2016, 2017, 2018, 2019, 2020),
    }
    assert source.EXPECTED_WEEKS == {
        2019: tuple(range(1, 18)),
        2021: tuple(range(1, 19)),
    }
    assert len(source.EXPECTED_SLATE_KEYS) == source.EXPECTED_SLATES == 35
    assert source.BLOCK_SEED_PAIRS == {
        "R0": (0, 7331),
        "R1": (1137260708, 2690847602),
    }
    assert source.WORLDS_PER_BLOCK == 10_000
    assert source.CANDIDATE_WORLD_FAMILY == "baseline_player_draws"
    assert source.ROLE_SEED_USAGE == "canonical_source_environment_receipt_only"
    assert source.UNIQUE_OPTIMA_PER_BLOCK == 40
    assert source.MAX_SOLVE_ATTEMPTS_PER_BLOCK == 80
    assert source.PRE_CROSS_BLOCK_CANDIDATES == 80
    assert "include_actual=False" in source.PIT_REPLAY_PATH_ID


def test_build_and_freeze_exact_budget_without_labels(monkeypatch):
    canonical, blocks, solve, requests = _fixture(monkeypatch)
    bundle = source.build_training_source((canonical,), blocks, solve)
    assert len(requests) == 82
    slate = bundle.slates[0]
    assert [len(block.candidates) for block in slate.blocks] == [40, 40]
    assert [len(block.solve_attempts) for block in slate.blocks] == [41, 41]
    assert slate.pre_cross_block_candidate_count == 80
    # R0 and R1 intentionally produce the same fresh candidates. Cross-block
    # dedup happens after both fixed forty-row doses and does not trigger fill.
    assert len(slate.post_cross_block_candidates) == 40
    assert slate.cross_block_duplicates == 40
    assert all(
        candidate.roster not in slate.incumbent_candidates
        for candidate in slate.post_cross_block_candidates
    )
    assert all(
        candidate.source_occurrences[0][0] == "R0"
        and candidate.source_occurrences[1][0] == "R1"
        for candidate in slate.post_cross_block_candidates
    )

    manifest = source.freeze_training_source(bundle)
    assert source.validate_frozen_training_source(
        manifest,
        expected_manifest_sha256=manifest["manifest_sha256"],
    ) == manifest
    assert manifest["post_dedup_candidate_rows"] == 40
    assert manifest["pre_cross_block_candidates_per_slate"] == 80
    assert manifest["target_player_labels_read"] is False
    assert manifest["candidate_labels_read"] is False
    assert manifest["candidate_world_family"] == "baseline_player_draws"
    assert manifest["role_belief_worlds_used"] is False
    assert manifest["role_seed_usage"] == (
        "canonical_source_environment_receipt_only"
    )
    assert manifest["blocks"][0][
        "source_environment_role_seed_nonoperative"
    ] == 7331
    assert manifest["old_law_candidate_totals_loaded"] is False
    assert manifest["bigquery_outcome_query_present"] is False
    assert manifest["historical_label_read_licensed"] is False
    block_manifest = manifest["slates"][0]["blocks"][0]
    assert block_manifest["unique_candidate_count"] == 40
    assert block_manifest["solve_attempt_count"] == 41
    assert len(block_manifest["ordered_solve_attempts"]) == 41
    assert block_manifest["ordered_solve_attempts_sha256"] == (
        slate.blocks[0].solve_attempts_sha256
    )
    assert "pre_cross_block_candidates" not in manifest["slates"][0]
    assert len(source.frozen_anatomy_candidates(bundle)) == 40


def test_catalog_rejects_target_actual_field(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    poisoned = dict(canonical.players[0])
    poisoned["actual"] = 99.0
    bad = replace(canonical, players=(poisoned, *canonical.players[1:]))
    with pytest.raises(source.LR8TrainingSourceError, match="forbidden=.*actual"):
        source.build_training_source((bad,), blocks, solve)


@pytest.mark.parametrize("field", [
    "candidate_totals_loaded",
    "target_player_labels_read",
    "candidate_labels_read",
    "role_belief_worlds_used",
    "b1_inputs_used",
    "a2a_inputs_used",
    "later_period_inputs_used",
])
def test_source_firewalls_fail_closed(monkeypatch, field):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    if field == "candidate_totals_loaded":
        canonical = replace(canonical, candidate_totals_loaded=True)
    else:
        blocks = (replace(blocks[0], **{field: True}), blocks[1])
    with pytest.raises(source.LR8TrainingSourceError, match=field):
        source.build_training_source((canonical,), blocks, solve)


def test_replay_slate_rejects_any_target_outcome_field(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    poisoned = replace(
        blocks[0].slates[0], target_outcome_fields_read=("y_dk_points",)
    )
    bad = (replace(blocks[0], slates=(poisoned,)), blocks[1])
    with pytest.raises(source.LR8TrainingSourceError, match="target outcome"):
        source.build_training_source((canonical,), bad, solve)


def test_role_seed_cannot_silently_become_a_candidate_world(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    role_worlds = (
        replace(blocks[0], role_belief_worlds_used=True),
        blocks[1],
    )
    with pytest.raises(source.LR8TrainingSourceError, match="role_belief"):
        source.build_training_source((canonical,), role_worlds, solve)

    wrong_family = (
        replace(blocks[0], candidate_world_family="role_belief_player_draws"),
        blocks[1],
    )
    with pytest.raises(source.LR8TrainingSourceError, match="world family"):
        source.build_training_source((canonical,), wrong_family, solve)


@pytest.mark.parametrize("generation", ["0", "01", "-1", "1.0"])
def test_source_receipt_requires_canonical_positive_generation(
    monkeypatch, generation,
):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    receipt = dict(canonical.catalog_source_receipts[0])
    receipt["generation"] = generation
    bad = replace(canonical, catalog_source_receipts=(receipt,))
    with pytest.raises(source.LR8TrainingSourceError, match="exact positive"):
        source.build_training_source((bad,), blocks, solve)


@pytest.mark.parametrize("size", [True, 1.5, "1", 0])
def test_source_receipt_requires_exact_positive_integer_bytes(
    monkeypatch, size,
):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    receipt = dict(canonical.catalog_source_receipts[0])
    receipt["bytes"] = size
    bad = replace(canonical, catalog_source_receipts=(receipt,))
    with pytest.raises(source.LR8TrainingSourceError, match="exact positive"):
        source.build_training_source((bad,), blocks, solve)


@pytest.mark.parametrize("uri", ["mock://object", "gs://", "gs://bucket"])
def test_source_receipt_requires_nonempty_gcs_object(monkeypatch, uri):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    receipt = dict(canonical.catalog_source_receipts[0])
    receipt["uri"] = uri
    bad = replace(canonical, catalog_source_receipts=(receipt,))
    with pytest.raises(source.LR8TrainingSourceError, match="GCS identity"):
        source.build_training_source((bad,), blocks, solve)


def test_model_fit_must_be_strictly_before_target_and_shared(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    missing_prior = (
        replace(blocks[0], model_training_seasons=(2016, 2017, 2018)),
        blocks[1],
    )
    with pytest.raises(source.LR8TrainingSourceError, match="training seasons differ"):
        source.build_training_source((canonical,), missing_prior, solve)

    mismatched = (
        blocks[0],
        replace(blocks[1], model_fit_sha256="3" * 64),
    )
    with pytest.raises(source.LR8TrainingSourceError, match="same target-season"):
        source.build_training_source((canonical,), mismatched, solve)


def test_r0_r1_fit_source_receipts_must_match(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    drifted = (
        blocks[0],
        replace(
            blocks[1],
            fit_source_receipts=(_receipt("mock://fit/2019-drift"),),
        ),
    )
    with pytest.raises(source.LR8TrainingSourceError, match="receipts differ"):
        source.build_training_source((canonical,), drifted, solve)


def test_replay_path_and_seed_pairs_are_frozen(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    wrong_path = (replace(blocks[0], replay_path_id="unsafe"), blocks[1])
    with pytest.raises(source.LR8TrainingSourceError, match="score-free seam"):
        source.build_training_source((canonical,), wrong_path, solve)

    wrong_seed = (replace(blocks[0], projection_seed=1), blocks[1])
    with pytest.raises(source.LR8TrainingSourceError, match="seed pair"):
        source.build_training_source((canonical,), wrong_seed, solve)


def test_world_solver_cannot_apply_house_law(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)

    def poisoned(request):
        return replace(solve(request), house_rules_applied=("salary_floor",))

    with pytest.raises(source.LR8TrainingSourceError, match="former house rule"):
        source.build_training_source((canonical,), blocks, poisoned)


def test_world_solver_objective_and_request_are_replayed(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)

    def wrong_objective(request):
        solved = solve(request)
        return replace(solved, objective_micro=solved.objective_micro + 1)

    with pytest.raises(source.LR8TrainingSourceError, match="objective"):
        source.build_training_source((canonical,), blocks, wrong_objective)

    def stale(request):
        return replace(solve(request), request_sha256="f" * 64)

    with pytest.raises(source.LR8TrainingSourceError, match="stale"):
        source.build_training_source((canonical,), blocks, stale)


def test_world_player_universe_and_hashes_are_exact(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    slate = blocks[0].slates[0]
    missing_ids = slate.player_ids[:-1]
    missing_draws = slate.player_draws[:-1]
    poisoned = replace(
        slate,
        player_ids=missing_ids,
        player_draws=missing_draws,
        player_ids_sha256=source.player_ids_sha256(missing_ids),
        player_draws_sha256=source.array_sha256(missing_draws),
    )
    bad = (replace(blocks[0], slates=(poisoned,)), blocks[1])
    with pytest.raises(source.LR8TrainingSourceError, match="universe differs"):
        source.build_training_source((canonical,), bad, solve)

    wrong_hash = replace(slate, player_draws_sha256="0" * 64)
    bad_hash = (replace(blocks[0], slates=(wrong_hash,)), blocks[1])
    with pytest.raises(source.LR8TrainingSourceError, match="draws hash differs"):
        source.build_training_source((canonical,), bad_hash, solve)


def test_manifest_tamper_fails(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    manifest = source.freeze_training_source(
        source.build_training_source((canonical,), blocks, solve)
    )
    tampered = dict(manifest)
    tampered["candidate_labels_read"] = True
    with pytest.raises(source.LR8TrainingSourceError, match="manifest hash"):
        source.validate_frozen_training_source(
            tampered,
            expected_manifest_sha256=manifest["manifest_sha256"],
        )


def test_wrong_external_manifest_pin_fails(monkeypatch):
    canonical, blocks, solve, _ = _fixture(monkeypatch)
    manifest = source.freeze_training_source(
        source.build_training_source((canonical,), blocks, solve)
    )
    with pytest.raises(source.LR8TrainingSourceError, match="manifest hash"):
        source.validate_frozen_training_source(
            manifest,
            expected_manifest_sha256="f" * 64,
        )


def test_attempt_81_cannot_fill_the_fixed_dose(monkeypatch):
    canonical, blocks, _, _ = _fixture(monkeypatch)
    candidates = _legal_rosters(canonical.players, 41)[1:]
    visited: list[int] = []

    def solve(request):
        visited.append(request.world_index)
        if request.world_index < 39:
            roster = candidates[request.world_index]
        elif request.world_index < 80:
            roster = candidates[0]
        else:  # This would be the fortieth unique row, but is forbidden.
            roster = candidates[39]
        return _solve_response(request, roster)

    with pytest.raises(source.LR8TrainingSourceError, match="in 80 ordered solves"):
        source.build_training_source((canonical,), blocks, solve)
    assert visited == list(range(80))
    assert 80 not in visited


def test_fewer_than_40_unique_within_80_fails(monkeypatch):
    canonical, blocks, _, _ = _fixture(monkeypatch)
    candidate = _legal_rosters(canonical.players, 2)[1]
    visited: list[int] = []

    def solve(request):
        visited.append(request.world_index)
        return _solve_response(request, candidate)

    with pytest.raises(source.LR8TrainingSourceError, match="fewer than forty"):
        source.build_training_source((canonical,), blocks, solve)
    assert len(visited) == source.MAX_SOLVE_ATTEMPTS_PER_BLOCK


def test_world_order_has_explicit_index_tiebreak(monkeypatch):
    _small_contract(monkeypatch)
    draws = np.ones((3, 96), dtype=np.float32)
    assert source.deterministic_world_order(draws) == tuple(range(96))
