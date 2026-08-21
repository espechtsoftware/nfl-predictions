from __future__ import annotations

from dataclasses import replace
from itertools import combinations

import numpy as np
import pulp
import pytest

from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.lr8_historical_arm import (
    ANATOMY_FEATURES,
    ANATOMY_FEATURE_ABS_UPPER,
    ANATOMY_LINEAR_SCALE,
    BOOK_MAX_CAP_MICRO,
    EVALUATION_SEASONS,
    FOLD_WEIGHT,
    K_MAX_PER_FOLD,
    MARGINAL_THRESHOLDS_MICRO,
    TRAINING_CELLS,
    AnatomyTrainingRow,
    FrozenBookCell,
    LR8Error,
    LaterPeriodScoreRow,
    audit_dk_classic_identity,
    build_dk_classic_model,
    canonical_sha256,
    clipped_marginal_utility,
    deployment_fold,
    evaluate_frozen_later_period_once,
    fit_soft_anatomy_law,
    lineup_anatomy,
    mechanics_payload,
    operative_anatomy_linear_units,
    run_lr8_mechanics,
    validate_prelock_timestamp,
    validate_soft_anatomy_artifact,
)


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows: list[rw.PlayerSpec] = []

    def add(player_id: str, pos: str, team: str, opp: str, game: str) -> None:
        rows.append(rw.PlayerSpec(player_id, pos, team, opp, game, 5_000))

    add("AQB", "QB", "A", "B", "g1")
    add("CQB", "QB", "C", "D", "g2")
    for player_id, team, opp, game in (
        ("ARB1", "A", "B", "g1"),
        ("ARB2", "A", "B", "g1"),
        ("BRB", "B", "A", "g1"),
        ("CRB", "C", "D", "g2"),
        ("DRB", "D", "C", "g2"),
        ("ERB", "E", "F", "g3"),
        ("FRB", "F", "E", "g3"),
    ):
        add(player_id, "RB", team, opp, game)
    for player_id, team, opp, game in (
        ("AWR1", "A", "B", "g1"),
        ("AWR2", "A", "B", "g1"),
        ("BWR", "B", "A", "g1"),
        ("CWR", "C", "D", "g2"),
        ("DWR", "D", "C", "g2"),
        ("EWR", "E", "F", "g3"),
        ("FWR1", "F", "E", "g3"),
        ("FWR2", "F", "E", "g3"),
    ):
        add(player_id, "WR", team, opp, game)
    for player_id, team, opp, game in (
        ("ATE", "A", "B", "g1"),
        ("BTE", "B", "A", "g1"),
        ("CTE", "C", "D", "g2"),
        ("DTE", "D", "C", "g2"),
        ("ETE", "E", "F", "g3"),
    ):
        add(player_id, "TE", team, opp, game)
    for player_id, team, opp, game in (
        ("ADST", "A", "B", "g1"),
        ("BDST", "B", "A", "g1"),
        ("CDST", "C", "D", "g2"),
        ("EDST", "E", "F", "g3"),
    ):
        add(player_id, "DST", team, opp, game)
    return tuple(rows)


def _all_legal_rosters() -> tuple[tuple[str, ...], ...]:
    players = _players()
    by_position = {
        position: [player.player_id for player in players if player.position == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    # One fixed legal FLEX shape: 3 RB, 3 WR, 1 TE, plus QB and DST.
    for qb in by_position["QB"]:
        for rbs in combinations(by_position["RB"], 3):
            for wrs in combinations(by_position["WR"], 3):
                for te in by_position["TE"]:
                    for dst in by_position["DST"]:
                        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
                        try:
                            audit_dk_classic_identity(players, roster)
                        except LR8Error:
                            continue
                        result.append(roster)
                        if len(result) == 1_500:
                            return tuple(result)
    return tuple(result)


def _artifact() -> dict[str, object]:
    rows = []
    for season, week in TRAINING_CELLS:
        index = len(rows) + 1
        features = tuple(
            float(((index + column) % 7) + index * (column + 1) / 10)
            for column in range(len(ANATOMY_FEATURES))
        )
        rows.append(AnatomyTrainingRow(
            season=season,
            week=week,
            features=features,
            realized_total_micro=(190 if index % 2 else 205) * 1_000_000,
        ))
    return fit_soft_anatomy_law(rows)


def _mechanics_fixture():
    players = _players()
    worlds = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(2)
    )
    # Later catalog rows are much stronger.  Select the bottom 88 legal
    # rosters as the incumbent and reserve the best roster as the proposal.
    raw = np.empty((len(players), len(worlds)), dtype=np.float32)
    for player_index in range(len(players)):
        for world_index in range(len(worlds)):
            raw[player_index, world_index] = np.float32(
                7.0 + 0.8 * player_index + 0.05 * world_index
            )
    rosters = _all_legal_rosters()
    player_row = {player.player_id: index for index, player in enumerate(players)}
    means = []
    for roster in rosters:
        indices = [player_row[player_id] for player_id in roster]
        means.append(float(raw[indices].sum(axis=0).mean()))
    order = np.argsort(np.asarray(means), kind="stable")
    controls = tuple(rosters[int(index)] for index in order[:88])
    proposal = rosters[int(order[-1])]
    assert proposal not in controls
    return players, worlds, raw, controls, proposal


def _house_rule_violator() -> tuple[str, ...]:
    # $45k, naked AQB, no B skill bring-back, two A RBs, and those A RBs
    # oppose BDST.  It is nevertheless DK Classic legal.
    return tuple(sorted((
        "AQB", "ARB1", "ARB2", "CWR", "DWR", "EWR", "FWR1", "CTE", "BDST",
    )))


def test_dk_only_legality_accepts_every_named_house_rule_relaxation():
    players = _players()
    roster = _house_rule_violator()
    assert audit_dk_classic_identity(players, roster) == roster
    anatomy = dict(zip(ANATOMY_FEATURES, lineup_anatomy(players, roster), strict=True))
    assert anatomy["salary_used"] == 45_000
    assert anatomy["qb_wrte_partners"] == 0
    assert anatomy["bring_back_skill_players"] == 0
    assert anatomy["rb_against_dst_count"] == 2
    assert anatomy["same_team_rb_pairs"] == 1

    model = build_dk_classic_model(players)
    model.problem.setObjective(pulp.lpSum(model.decision[player_id] for player_id in roster))
    assert model.problem.solve(pulp.PULP_CBC_CMD(msg=False)) == pulp.LpStatusOptimal
    solved = tuple(sorted(
        player_id for player_id, variable in model.decision.items()
        if variable.value() and variable.value() > 0.5
    ))
    assert solved == roster


def test_dk_only_legality_still_rejects_cap_and_position_violations():
    players = _players()
    roster = _house_rule_violator()
    expensive = tuple(
        replace(player, salary=11_000) if player.player_id == "AQB" else player
        for player in players
    )
    with pytest.raises(LR8Error, match="salary cap"):
        audit_dk_classic_identity(expensive, roster)
    malformed = tuple(value for value in roster if value != "AQB") + ("CQB",)
    malformed = tuple(sorted((*malformed[:-1], "CQB")))
    # Swap a WR for the second QB so the identity is still nine unique ids.
    malformed = tuple(sorted((set(roster) - {"CWR"}) | {"CQB"}))
    with pytest.raises(LR8Error, match="position shape"):
        audit_dk_classic_identity(players, malformed)


def test_soft_anatomy_fit_is_exactly_2019_and_2021_and_hash_bound():
    artifact = _artifact()
    assert validate_soft_anatomy_artifact(artifact) == artifact
    assert artifact["training_seasons"] == [2019, 2021]
    assert artifact["training_cells"] == 35
    assert artifact["b1_inputs_used"] is False
    assert artifact["a2a_inputs_used"] is False
    assert artifact["operative_linear_scale"] == ANATOMY_LINEAR_SCALE
    assert artifact["operative_rounding"] == "decimal-round-half-even-v1"
    assert artifact["sigmoid_probability_operative"] is False
    assert artifact["operative_worst_case_abs_units"] <= rw.CBC_EXACT_INTEGER_MAX
    assert ANATOMY_FEATURE_ABS_UPPER[5] == 6
    features = lineup_anatomy(_players(), _house_rule_violator())
    expected_tier = int(artifact["operative_intercept_units"]) + sum(
        int(weight) * int(value)
        for weight, value in zip(
            artifact["operative_raw_weight_units"], features, strict=True
        )
    )
    assert operative_anatomy_linear_units(artifact, features) == expected_tier
    poisoned = dict(artifact, training_seasons=[2019, 2020, 2021])
    with pytest.raises(LR8Error, match="law differs"):
        validate_soft_anatomy_artifact(poisoned)
    wrong_rows = [
        AnatomyTrainingRow(2019, 1, (1.0,) * len(ANATOMY_FEATURES), 190_000_000),
        AnatomyTrainingRow(2020, 1, (2.0,) * len(ANATOMY_FEATURES), 205_000_000),
        AnatomyTrainingRow(2021, 1, (3.0,) * len(ANATOMY_FEATURES), 190_000_000),
    ]
    with pytest.raises(LR8Error, match="exactly seasons 2019 and 2021"):
        fit_soft_anatomy_law(wrong_rows)


def test_soft_anatomy_standardization_gives_each_season_week_equal_weight():
    rows = [
        AnatomyTrainingRow(
            season,
            week,
            (float(index),) * len(ANATOMY_FEATURES),
            (205_000_000 if index % 2 else 190_000_000),
        )
        for index, (season, week) in enumerate(TRAINING_CELLS)
    ]
    # Duplicating the zero-valued first cell would lower an unweighted mean,
    # but cannot change equal-cell standardization.
    rows.append(AnatomyTrainingRow(
        2019, 1, (0.0,) * len(ANATOMY_FEATURES), 205_000_000
    ))
    artifact = fit_soft_anatomy_law(rows)
    assert artifact["standardize_means"] == pytest.approx(
        [17.0] * len(ANATOMY_FEATURES)
    )
    assert artifact["standardize_scales"] == pytest.approx(
        [np.sqrt(102.0)] * len(ANATOMY_FEATURES)
    )
    assert artifact["sample_weight"] == "equal_total_weight_per_season_week"


def _rehash_artifact(artifact: dict[str, object]) -> dict[str, object]:
    artifact["artifact_sha256"] = canonical_sha256({
        key: value for key, value in artifact.items()
        if key != "artifact_sha256"
    })
    return artifact


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda artifact: artifact["standardize_means"].__setitem__(0, True),
            "finite non-bool JSON number",
        ),
        (
            lambda artifact: artifact.update(intercept="0.0"),
            "finite non-bool JSON number",
        ),
        (
            lambda artifact: artifact.update(intercept=10 ** 1_000),
            "finite non-bool JSON number",
        ),
        (
            lambda artifact: artifact.update(c=True),
            "finite non-bool JSON number",
        ),
        (
            lambda artifact: artifact.update(max_iter=2000.0),
            "exact non-bool JSON integer",
        ),
        (
            lambda artifact: artifact.update(training_cells=35.0),
            "exact non-bool JSON integer",
        ),
        (
            lambda artifact: artifact.update(training_positive_rows=35),
            "training lattice differs",
        ),
        (
            lambda artifact: artifact["operative_raw_weight_units"].__setitem__(
                0, artifact["operative_raw_weight_units"][0] + 1
            ),
            "fixed-point law differs",
        ),
        (
            lambda artifact: artifact.update(
                operative_worst_case_abs_units=(
                    artifact["operative_worst_case_abs_units"] + 1
                )
            ),
            "fixed-point law differs",
        ),
    ],
)
def test_soft_anatomy_artifact_numeric_types_and_counts_fail_closed(
    mutate, message,
):
    artifact = _artifact()
    mutate(artifact)
    _rehash_artifact(artifact)
    with pytest.raises(LR8Error, match=message):
        validate_soft_anatomy_artifact(artifact)


def test_soft_anatomy_fit_requires_the_exact_35_cell_training_lattice():
    rows = []
    for index, (season, week) in enumerate(TRAINING_CELLS[:-1]):
        rows.append(AnatomyTrainingRow(
            season,
            week,
            (float(index),) * len(ANATOMY_FEATURES),
            (205_000_000 if index % 2 else 190_000_000),
        ))
    with pytest.raises(LR8Error, match="exact 2019 Weeks 1..17"):
        fit_soft_anatomy_law(rows)


def test_marginal_utility_caps_every_score_and_pruning_tie_at_210():
    maxima = np.asarray([205, 220], dtype=np.int64) * 1_000_000
    candidate = np.asarray([260, 300], dtype=np.int64) * 1_000_000
    counts, residuals, gain, objective = clipped_marginal_utility(candidate, maxima)
    assert counts == (1, 0, 0, 0)
    assert residuals == (5_000_000, 0)
    assert gain == 5_000_000
    assert objective == (*counts, gain)

    uncapped = rw.utility_from_maxima(
        np.asarray([300_000_000], dtype=np.int64),
        thresholds_micro=MARGINAL_THRESHOLDS_MICRO,
    )
    capped = rw.utility_from_maxima(
        np.asarray([300_000_000], dtype=np.int64),
        thresholds_micro=MARGINAL_THRESHOLDS_MICRO,
        sum_max_cap_micro=BOOK_MAX_CAP_MICRO,
    )
    assert uncapped.sum_max_micro == 300_000_000
    assert capped.sum_max_micro == 210_000_000


def test_two_folds_each_get_k8_budget_and_stop_at_their_own_first_null():
    players, worlds, raw, controls, proposal = _mechanics_fixture()
    calls = {"A": [], "B": []}

    def make_pricer(fold):
        def price(request):
            calls[fold].append(request)
            assert request.fold_name == fold
            assert {world.block for world in request.world_ids} == set(
                request.construction_blocks
            )
            assert not ({world.block for world in request.world_ids} & set(
                next(spec for spec in rw.FOLD_SPECS if spec.name == fold).evaluation_blocks
            ))
            assert request.player_scores_micro.flags.writeable is False
            assert request.book_maxima_micro.flags.writeable is False
            assert request.portfolio_improvement_required is True
            assert request.anatomy_linear_scale == ANATOMY_LINEAR_SCALE
            return proposal if request.iteration == 1 else None
        return price

    result = run_lr8_mechanics(
        season=2023,
        week=1,
        slate_id="synthetic-2023-w1",
        players=players,
        world_ids=worlds,
        raw_player_draws=raw,
        incumbent_candidates=controls,
        anatomy_artifact=_artifact(),
        pricing_steps={"A": make_pricer("A"), "B": make_pricer("B")},
    )
    assert len(result.folds) == 2
    for fold in result.folds:
        assert fold.fold_weight == FOLD_WEIGHT
        assert fold.candidate_budget == 88
        assert len(fold.control_book) == len(fold.treatment_book) == 80
        assert len(fold.control_candidates) == len(fold.treatment_candidates) == 88
        assert fold.generated_columns == (proposal,)
        assert fold.pruning.removal_order[0] not in fold.control_book
        assert fold.stopped_on_first_null is True
        assert fold.null_iteration == 2
        assert fold.steps[0].admitted is True
        assert fold.steps[0].anatomy_tier_units is not None
        assert fold.steps[0].objective_vector == (
            *fold.steps[0].threshold_counts,
            fold.steps[0].anatomy_tier_units,
            fold.steps[0].clipped_residual_gain_micro,
        )
        assert fold.steps[1].null is True
    assert [request.iteration for request in calls["A"]] == [1, 2]
    assert [request.iteration for request in calls["B"]] == [1, 2]
    payload = mechanics_payload(result)
    assert payload["k_max_per_fold"] == K_MAX_PER_FOLD
    assert payload["k_max_combined"] is None
    assert payload["folds"][0]["fold_weight"] == 0.5
    assert payload["folds"][1]["fold_weight"] == 0.5
    assert payload["pricing_objective_order"] == [
        "g_210", "g_200", "g_194", "g_187",
        "soft_anatomy_linear_predictor_units",
        "clipped_book_max_gain_micro",
    ]
    assert result.deployment_fold == "A"
    assert result.control_deployment_book == result.folds[0].control_book
    assert result.treatment_deployment_book == result.folds[0].treatment_book
    assert payload["deployment_fold_rule"] == "odd_week_A_even_week_B"
    assert payload["hard_constraints"] == "dk_nfl_classic_only"
    assert payload["pricing_optimality_proven"] is False
    assert payload["production_change_licensed"] is False


def test_null_at_first_iteration_never_calls_a_later_pricing_step():
    players, worlds, raw, controls, _ = _mechanics_fixture()
    calls = []

    def null(request):
        calls.append((request.fold_name, request.iteration))
        if request.iteration != 1:
            raise AssertionError("pricing continued after first null")
        return None

    result = run_lr8_mechanics(
        season=2025,
        week=18,
        slate_id="synthetic-null",
        players=players,
        world_ids=worlds,
        raw_player_draws=raw,
        incumbent_candidates=controls,
        anatomy_artifact=_artifact(),
        pricing_steps={"A": null, "B": null},
    )
    assert calls == [("A", 1), ("B", 1)]
    assert all(not fold.generated_columns for fold in result.folds)
    assert all(fold.control_book == fold.treatment_book for fold in result.folds)


def _roster(prefix: str, index: int) -> tuple[str, ...]:
    return tuple(f"{prefix}-{index:02d}-{slot}" for slot in range(9))


def _later_period_fixture():
    control = tuple(_roster("c", index) for index in range(80))
    treatment = (*control[:-1], _roster("t", 0))
    control_candidates = (
        *control, *(_roster("cx", index) for index in range(8))
    )
    treatment_candidates = (
        *treatment, *(_roster("tx", index) for index in range(8))
    )
    cells = []
    score_rows = []
    for season in EVALUATION_SEASONS:
        for week in range(1, 19):
            for fold in ("A", "B"):
                cells.append(FrozenBookCell(
                    season=season,
                    week=week,
                    fold_name=fold,
                    candidate_budget_control=88,
                    candidate_budget_treatment=88,
                    control_candidates=control_candidates,
                    treatment_candidates=treatment_candidates,
                    control_book=control,
                    treatment_book=treatment,
                    freeze_sha256="a" * 64,
                ))
            for roster in sorted(
                set((*control_candidates, *treatment_candidates))
            ):
                score_rows.append(LaterPeriodScoreRow(
                    season=season,
                    week=week,
                    roster=roster,
                    realized_total_micro=(205 if roster == _roster("t", 0) else 190)
                    * 1_000_000,
                ))
    attempt = {
        "uri": "gs://synthetic/lr8/attempt.json",
        "generation": "123",
        "sha256": "b" * 64,
        "bytes": 123,
        "create_once": True,
        "stage": "lr8-2023-2025-later-period-score-read",
        "historical_outcome_lease_generation": "456",
    }
    return cells, score_rows, attempt


def test_mocked_later_period_evaluator_uses_one_deployable_book_and_passes():
    cells, scores, attempt = _later_period_fixture()
    report = evaluate_frozen_later_period_once(
        cells, scores, attempt_identity=attempt
    )
    assert report["historical_pass"] is True
    assert report["primary_deployment_rule"] == "odd_week_A_even_week_B"
    assert report["primary_deployable_books_per_slate"] == 1
    assert report["fold_weights"] == {"A": 0.5, "B": 0.5}
    primary = report["primary_deployment"]
    assert primary["slates"] == 54
    assert primary["control_mean_candidate_ceiling_dk"] == 190.0
    assert primary["treatment_mean_candidate_ceiling_dk"] == 205.0
    assert primary["control_mean_selected_max_dk"] == 190.0
    assert primary["treatment_mean_selected_max_dk"] == 205.0
    assert primary["treatment_mean_candidate_to_selected_gap_dk"] == 0.0
    assert primary["threshold_counts"]["200"] == {
        "control_slates": 0,
        "treatment_slates": 54,
    }
    assert report["equal_fold_diagnostics"]["license_bearing"] is False
    assert report["equal_fold_diagnostics"]["threshold_counts"]["200"] == {
        "control_equal_fold_weighted_slates": 0.0,
        "treatment_equal_fold_weighted_slates": 54.0,
    }
    primary_rows = [
        row for row in report["per_fold_cell"]
        if row["is_primary_deployment_book"]
    ]
    assert len(primary_rows) == 54
    assert all(
        row["fold_name"] == ("A" if row["week"] % 2 else "B")
        for row in primary_rows
    )
    assert all(report["gates"].values())
    assert report["one_later_period_score_read"] is True
    assert report["prospective_2026_weeks_1_6_confirmation_licensed"] is True
    assert report["production_change_licensed"] is False
    assert report["report_sha256"] == canonical_sha256({
        key: value for key, value in report.items() if key != "report_sha256"
    })


def test_later_period_evaluator_rejects_extra_rows_and_non_create_once_attempt():
    cells, scores, attempt = _later_period_fixture()
    scores.append(LaterPeriodScoreRow(
        2023, 1, _roster("extra", 0), 200_000_000
    ))
    with pytest.raises(LR8Error, match="exact frozen-candidate union"):
        evaluate_frozen_later_period_once(cells, scores, attempt_identity=attempt)
    cells, scores, attempt = _later_period_fixture()
    attempt["create_once"] = False
    with pytest.raises(LR8Error, match="attempt identity differs"):
        evaluate_frozen_later_period_once(cells, scores, attempt_identity=attempt)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("generation", "0"),
        ("generation", "01"),
        ("historical_outcome_lease_generation", "0"),
        ("historical_outcome_lease_generation", "0456"),
    ],
)
def test_later_period_attempt_requires_positive_canonical_generations(
    field, value,
):
    cells, scores, attempt = _later_period_fixture()
    attempt[field] = value
    with pytest.raises(LR8Error, match="attempt identity differs"):
        evaluate_frozen_later_period_once(cells, scores, attempt_identity=attempt)


def test_later_period_tiny_selection_lift_cannot_pass_path_to_200_gate():
    cells, scores, attempt = _later_period_fixture()
    scores = [
        replace(row, realized_total_micro=201_000_000)
        if row.roster == _roster("t", 0) else row
        for row in scores
    ]
    report = evaluate_frozen_later_period_once(
        cells, scores, attempt_identity=attempt
    )
    assert report["gates"]["primary_mean_selected_max_strictly_improves"] is True
    assert report["gates"]["primary_selected_max_200_strictly_improves"] is True
    assert report["gates"][
        "primary_treatment_mean_candidate_ceiling_at_least_205"
    ] is False
    assert report["historical_pass"] is False


def test_deployment_fold_is_frozen_before_outcomes():
    assert deployment_fold(2023, 1) == "A"
    assert deployment_fold(2023, 2) == "B"
    assert deployment_fold(2026, 17) == "A"


def test_prelock_guard_requires_strict_utc_order():
    validate_prelock_timestamp("2026-09-13T16:00:00Z", "2026-09-13T17:00:00Z")
    with pytest.raises(LR8Error, match="strictly pre-lock"):
        validate_prelock_timestamp("2026-09-13T18:00:00Z", "2026-09-13T17:00:00Z")
    with pytest.raises(LR8Error, match="ISO-8601"):
        validate_prelock_timestamp("not-a-time", "2026-09-13T17:00:00Z")
