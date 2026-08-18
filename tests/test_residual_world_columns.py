from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
from functools import lru_cache
from itertools import combinations
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.residual_world_run_context import (
    CBC_SHA256,
    build_residual_run_context,
)


@lru_cache(maxsize=1)
def _run_context():
    """Synthetic exact context; it never attests or licenses a real run."""
    return build_residual_run_context(
        code_commit="1" * 40,
        code_archive_sha256="2" * 64,
        source_file_lock_sha256="3" * 64,
        source_data_lock_sha256="4" * 64,
        image_sha256="5" * 64,
        python_version="3.14.4",
        cbc_sha256=CBC_SHA256,
    )


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows: list[rw.PlayerSpec] = []

    def add(player_id: str, position: str, team: str, opponent: str, game: str):
        rows.append(rw.PlayerSpec(
            player_id, position, team, opponent, game,
            5_000 + (len(rows) % 6) * 200,
        ))

    add("AQB", "QB", "A", "B", "g1")
    add("BQB", "QB", "B", "A", "g1")
    for player_id, team, opponent, game in (
        ("ARB1", "A", "B", "g1"),
        ("ARB2", "A", "B", "g1"),
        ("BRB", "B", "A", "g1"),
        ("CRB", "C", "D", "g2"),
        ("DRB", "D", "C", "g2"),
    ):
        add(player_id, "RB", team, opponent, game)
    for player_id, team, opponent, game in (
        ("AWR1", "A", "B", "g1"),
        ("AWR2", "A", "B", "g1"),
        ("BWR1", "B", "A", "g1"),
        ("BWR2", "B", "A", "g1"),
        ("CWR", "C", "D", "g2"),
        ("DWR", "D", "C", "g2"),
    ):
        add(player_id, "WR", team, opponent, game)
    for player_id, team, opponent, game in (
        ("ATE", "A", "B", "g1"),
        ("BTE", "B", "A", "g1"),
        ("CTE", "C", "D", "g2"),
        ("DTE", "D", "C", "g2"),
    ):
        add(player_id, "TE", team, opponent, game)
    add("ADST", "DST", "A", "B", "g1")
    add("CDST", "DST", "C", "D", "g2")
    return tuple(rows)


def _independent_legal(players: tuple[rw.PlayerSpec, ...], roster: tuple[str, ...]) -> bool:
    by_id = {player.player_id: player for player in players}
    if len(roster) != 9 or len(set(roster)) != 9 or not set(roster) <= set(by_id):
        return False
    chosen = [by_id[player_id] for player_id in roster]
    count = {
        position: sum(player.position == position for player in chosen)
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    if not (
        count["QB"] == count["DST"] == 1
        and 2 <= count["RB"] <= 3
        and 3 <= count["WR"] <= 4
        and 1 <= count["TE"] <= 2
    ):
        return False
    salary = sum(player.salary for player in chosen)
    if not 49_000 <= salary <= 50_000:
        return False
    if max(sum(player.team == team for player in chosen) for team in {
        player.team for player in chosen
    }) > 8:
        return False
    if len({player.game_id for player in chosen}) < 2:
        return False
    qb = next(player for player in chosen if player.position == "QB")
    if sum(
        player.team == qb.team and player.position in {"WR", "TE"}
        for player in chosen
    ) < 2:
        return False
    if not any(
        player.team == qb.opponent and player.position in {"RB", "WR", "TE"}
        for player in chosen
    ):
        return False
    dst = next(player for player in chosen if player.position == "DST")
    if any(
        player.position == "RB" and player.team == dst.opponent
        for player in chosen
    ):
        return False
    rb_teams = [player.team for player in chosen if player.position == "RB"]
    return len(rb_teams) == len(set(rb_teams))


@lru_cache(maxsize=1)
def _legal_rosters() -> tuple[tuple[str, ...], ...]:
    players = _players()
    return tuple(
        tuple(sorted(player.player_id for player in chosen))
        for chosen in combinations(players, 9)
        if _independent_legal(
            players, tuple(player.player_id for player in chosen)
        )
    )


def _score_matrix() -> np.ndarray:
    # Four integer-micro worlds with deliberately different player orderings.
    rng = np.random.default_rng(17_081_701)
    return rng.integers(
        8_000_000, 36_000_001, size=(len(_players()), 4), dtype=np.int64
    )


def _brute_pricing(
    scores: np.ndarray,
    book_maxima: np.ndarray,
    forbidden: set[tuple[str, ...]] = frozenset(),
):
    players = _players()
    row = {player.player_id: index for index, player in enumerate(players)}
    ranks = {
        player_id: index + 1 for index, player_id in enumerate(sorted(row))
    }
    candidates = []
    for roster in _legal_rosters():
        if roster in forbidden:
            continue
        total = scores[[row[player_id] for player_id in roster]].sum(
            axis=0, dtype=np.int64
        )
        counts = tuple(int(np.count_nonzero(
            (book_maxima < threshold) & (total >= threshold)
        )) for threshold in rw.TAIL_THRESHOLDS_MICRO)
        gain = sum(int(value) for value in np.maximum(total - book_maxima, 0))
        objective = (*counts, gain)
        rank_sum = sum(ranks[player_id] for player_id in roster)
        candidates.append((objective, -rank_sum, roster, total))
    best_objective = max(value[0] for value in candidates)
    objective_ties = [value for value in candidates if value[0] == best_objective]
    best_rank = max(value[1] for value in objective_ties)
    rank_ties = [value for value in objective_ties if value[1] == best_rank]
    # Canonical incidence prefers the smallest id at the first difference,
    # which is the lexicographically smallest sorted nine-id tuple.
    return min(rank_ties, key=lambda value: value[2]), len(rank_ties)


def _identity(suffix: str) -> tuple[str, ...]:
    return tuple(f"{suffix}-{index}" for index in range(9))


def _pricing_result(
    roster: tuple[str, ...], counts: tuple[int, ...], *, admissible: bool,
) -> rw.PricingResult:
    return rw.PricingResult(
        roster=roster,
        scores_micro=(0,),
        marginal_threshold_counts=counts,
        residuals_micro=(0,),
        residual_gain_micro=0,
        objective_vector=(*counts, 0),
        indicators_by_threshold=tuple((int(value > 0),) for value in counts),
        rank_sum=1,
        rank_sum_ambiguous=False,
        admissible=admissible,
        sequential_optima=(*counts, 0),
    )


def test_frozen_constants_and_fold_contract_are_immutable_values():
    assert rw.PROTOCOL_ID == "20260817-residual-world-column-generation-scorefree-v1"
    assert rw.TAIL_THRESHOLDS_DK == (240, 230, 220, 210, 200, 194, 187)
    assert rw.TAIL_THRESHOLDS_MICRO == tuple(
        value * 1_000_000 for value in rw.TAIL_THRESHOLDS_DK
    )
    assert rw.K_MAX == 8
    assert rw.WORLD_BLOCKS == ("R0", "R1", "R2", "R3", "R4")
    assert rw.WORLDS_PER_BLOCK == 10_000
    assert rw.CBC_WARM_START is True
    assert rw.CBC_AUXILIARY_CUTS is False
    assert rw.CBC_INTEGER_TOLERANCE == Decimal("1e-12")
    assert rw.CBC_INTEGER_TOLERANCE_OPTION == "1e-12"
    assert rw.PROTOCOL_AMENDMENT_ID == (
        "20260817-residual-world-exact-solver-selector-v1"
    )
    assert rw.PROTOCOL_AMENDMENT_SHA256 == (
        "18155f674c60383a51583f9a08916680dd3917665dbfaf064ede1330f2b3671f"
    )
    assert rw.SCORE_RADIX == 100
    assert (rw.ENTRY_COUNT, rw.CONTROL_TAIL_LINE_DK) == (80, 194)
    assert (rw.FOLD_RESERVOIR_SIZE, rw.FOLD_ACTIVE_SIZE) == (96, 66)
    assert (
        rw.SHADOW_RESERVOIR_SIZE,
        rw.SHADOW_ACTIVE_SIZE,
        rw.SHADOW_RESERVOIR_PER_BLOCK,
        rw.SHADOW_ACTIVE_PER_BLOCK,
    ) == (100, 70, 20, 14)
    assert rw.FOLD_SPECS == (
        rw.FoldSpec("A", ("R0", "R2", "R4"), ("R1", "R3"), 32, 22),
        rw.FoldSpec("B", ("R1", "R3"), ("R0", "R2", "R4"), 48, 33),
    )


def test_world_player_and_integer_inputs_fail_closed_without_coercion():
    assert rw.WorldId("R4", 9_999) == rw.WorldId("R4", np.int64(9_999))
    for block, index in (("R5", 0), ("R0", -1), ("R0", 10_000)):
        with pytest.raises(rw.ResidualWorldError, match="outside"):
            rw.WorldId(block, index)
    for index in (1.0, True):
        with pytest.raises(rw.ResidualWorldError, match="must be an integer"):
            rw.WorldId("R0", index)

    row = {
        "id": "p", "pos": "RB", "team": "A", "opp": "B",
        "game_id": "g", "salary": 5_500,
    }
    assert rw.PlayerSpec.from_mapping(row).salary == 5_500
    for salary in (5_500.9, True):
        with pytest.raises(rw.ResidualWorldError, match="must be an integer"):
            rw.PlayerSpec.from_mapping({**row, "salary": salary})
    with pytest.raises(rw.ResidualWorldError, match="lineup player id"):
        rw.canonical_identity(tuple(range(9)))
    with pytest.raises(rw.ResidualWorldError, match="roster sequence"):
        rw.canonical_identity("123456789")
    with pytest.raises(rw.ResidualWorldError, match="tail threshold"):
        rw.utility_from_maxima([1], thresholds_micro=(1.0,))
    with pytest.raises(rw.ResidualWorldError, match="signed int64"):
        rw.utility_from_maxima(np.asarray([2**63], dtype=np.uint64))


def test_research_constraint_builder_matches_independent_exhaustive_domain():
    players = _players()
    model = rw.build_legal_lineup_model(players)
    model_legal = set()
    for chosen in combinations(players, 9):
        chosen_ids = {player.player_id for player in chosen}
        for player_id, variable in model.decision.items():
            variable.varValue = float(player_id in chosen_ids)
        if all(constraint.valid(0.0) for constraint in model.problem.constraints()):
            model_legal.add(tuple(sorted(chosen_ids)))
    assert model_legal == set(_legal_rosters())
    assert model_legal
    for roster in model_legal:
        assert rw.audit_legal_identity(players, roster) == roster


def test_residual_builder_calls_shared_constraints_with_exact_frozen_policy(
    monkeypatch,
):
    calls = []
    original = rw.add_classic_lineup_constraints

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(rw, "add_classic_lineup_constraints", spy)
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("MAX_PER_GAME", "1")
    forbidden = (_legal_rosters()[0],)
    rw.build_legal_lineup_model(_players(), forbidden_rosters=forbidden)
    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs == {
        "budget": 50_000,
        "locks": None,
        "bans": None,
        "banned_lineups": [frozenset(forbidden[0])],
        "stack": rw.StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        ),
        "max_overlap": 8,
        "punt_max_salary": None,
        "punt_min": 0,
        "game_lock": None,
        "min_salary": 49_000,
        "max_salary": None,
        "max_per_game": 0,
        "env": {},
    }

    one_game = tuple(
        rw.PlayerSpec(
            player.player_id,
            player.position,
            player.team,
            player.opponent,
            "one-game",
            player.salary,
        )
        for player in _players()
    )
    with pytest.raises(rw.ResidualWorldError, match="at least two"):
        rw.build_legal_lineup_model(one_game)


def test_exact_legal_bounds_equal_brute_force_and_are_row_order_invariant():
    players = _players()
    scores = _score_matrix()
    row = {player.player_id: index for index, player in enumerate(players)}
    brute = np.asarray([
        scores[[row[player_id] for player_id in roster]].sum(axis=0)
        for roster in _legal_rosters()
    ], dtype=np.int64)
    bounds = rw.solve_legal_bounds(players, scores)
    assert len(bounds.solve_evidence) == 4 * scores.shape[1]
    for evidence in bounds.solve_evidence:
        assert evidence.objective == int(evidence.objective)
        assert evidence.wall_seconds < evidence.max_seconds
        assert rw.Path(evidence.log_path).is_file()
        assert rw._sha256_file(rw.Path(evidence.log_path)) == evidence.log_sha256
    assert bounds.lower_micro == tuple(int(value) for value in brute.min(axis=0))
    assert bounds.upper_micro == tuple(int(value) for value in brute.max(axis=0))
    for world, roster in enumerate(bounds.lower_rosters):
        assert rw.audit_legal_identity(players, roster) == roster
        assert int(scores[[row[value] for value in roster], world].sum()) == (
            bounds.lower_micro[world]
        )
    for world, roster in enumerate(bounds.upper_rosters):
        assert rw.audit_legal_identity(players, roster) == roster
        assert int(scores[[row[value] for value in roster], world].sum()) == (
            bounds.upper_micro[world]
        )

    reverse = tuple(reversed(players))
    reversed_bounds = rw.solve_legal_bounds(reverse, scores[::-1])
    assert reversed_bounds.lower_micro == bounds.lower_micro
    assert reversed_bounds.upper_micro == bounds.upper_micro


def test_exact_pricing_matches_brute_force_all_tiers_positive_part_and_identity():
    players = _players()
    scores = _score_matrix()
    bounds = rw.solve_legal_bounds(players, scores)
    book = np.array([218, 205, 192, 181], dtype=np.int64) * 1_000_000
    brute, tie_count = _brute_pricing(scores, book)
    result = rw.solve_residual_pricing(
        players,
        scores,
        book,
        bounds.lower_micro,
        bounds.upper_micro,
    )
    objective, negative_rank, roster, totals = brute
    expected_indicators = tuple(tuple(int(
        book[world] < threshold <= totals[world]
    ) for world in range(len(book))) for threshold in rw.TAIL_THRESHOLDS_MICRO)
    assert result.roster == roster
    assert result.objective_vector == objective
    assert result.marginal_threshold_counts == objective[:-1]
    assert result.residual_gain_micro == objective[-1]
    assert result.residuals_micro == tuple(
        int(value) for value in np.maximum(totals - book, 0)
    )
    assert result.indicators_by_threshold == expected_indicators
    assert result.rank_sum == -negative_rank
    assert result.rank_sum_ambiguous is (tie_count > 1)
    assert result.admissible is any(objective[:-1])
    assert result.solve_evidence
    assert all(
        evidence.wall_seconds < evidence.max_seconds
        and rw.Path(evidence.solution_path).is_file()
        for evidence in result.solve_evidence
    )
    assert all(
        not any(
            line.split()[:1] == ["**"]
            for line in rw.Path(evidence.solution_path).read_text().splitlines()
        )
        for evidence in result.solve_evidence
    )
    for evidence in result.solve_evidence:
        if evidence.warm_start:
            assert evidence.mip_start_values is not None
            assert evidence.mip_start_variable_count == len(
                evidence.mip_start_values
            )
            assert evidence.mip_start_values_sha256 == rw._canonical_json_sha256([
                [name, value] for name, value in evidence.mip_start_values
            ])

    reverse = tuple(reversed(players))
    reversed_result = rw.solve_residual_pricing(
        reverse,
        scores[::-1],
        book,
        bounds.lower_micro,
        bounds.upper_micro,
    )
    assert reversed_result == result


def test_positive_part_pricing_matches_brute_force_in_all_three_bound_cases():
    players = _players()
    scores = _score_matrix()[:, :3]
    bounds = rw.solve_legal_bounds(players, scores)
    # A legal selected-book maximum must itself lie in [L,H].  Exercise the
    # reachable H==m structural zero, m==L, and L<m<H cases here; the three
    # algebraic helper branches (including defensive L>m) are tested below.
    roster_rows = {
        player.player_id: index for index, player in enumerate(players)
    }
    legal_third_scores = sorted({
        int(scores[[roster_rows[player_id] for player_id in roster], 2].sum())
        for roster in _legal_rosters()
    })
    book = np.asarray([
        bounds.upper_micro[0],
        bounds.lower_micro[1],
        legal_third_scores[len(legal_third_scores) // 2],
    ], dtype=np.int64)
    brute, _ = _brute_pricing(scores, book)
    result = rw.solve_residual_pricing(
        players, scores, book, bounds.lower_micro, bounds.upper_micro,
    )
    assert result.roster == brute[2]
    assert result.objective_vector == brute[0]
    assert result.residuals_micro == tuple(
        int(value) for value in np.maximum(brute[3] - book, 0)
    )
    assert result.residuals_micro[0] == 0
    assert result.residuals_micro[1] > 0


@pytest.mark.parametrize(
    ("lower", "upper", "maximum", "score", "expected", "has_binary"),
    (
        (10, 20, 20, 15, 0, False),       # H<=m
        (21, 30, 20, 24, 4, False),       # L>m
        (10, 30, 20, 19, 0, True),        # L<=m<H, nonpositive
        (10, 30, 20, 20, 0, True),        # exact boundary
        (10, 30, 20, 21, 1, True),        # strictly positive
    ),
)
def test_positive_part_graph_has_all_exact_algebraic_branches(
    lower, upper, maximum, score, expected, has_binary,
):
    problem = rw.pulp.LpProblem("positive_part_unit", rw.pulp.LpMaximize)
    score_variable = rw.pulp.LpVariable(
        "score", lowBound=score, upBound=score, cat="Integer",
    )
    problem += score_variable == score
    residual, positive = rw._add_exact_positive_part(
        problem,
        score_variable,
        lower,
        upper,
        maximum,
        name="unit",
    )
    assert (positive is not None) is has_binary
    if has_binary:
        problem.setObjective(residual)
        problem.solve(rw.pulp.PULP_CBC_CMD(msg=0))
        assert rw.pulp.LpStatus[problem.status] == "Optimal"
    else:
        score_variable.varValue = score
    assert rw._integer_value(residual) == expected
    if positive is not None:
        assert rw._integer_value(positive) == int(score > maximum)


def test_tail_indicator_skip_cases_are_exact_at_legal_book_boundaries():
    players = _players()
    threshold = 220_000_000
    scores = np.full((len(players), 4), 24_000_000, dtype=np.int64)
    for index, player in enumerate(players):
        if player.position == "DST":
            scores[index] += np.asarray(
                [4_000_000, 3_999_999, 4_000_000, 3_999_999],
                dtype=np.int64,
            )
    # Pricing receives active worlds, so retain one genuinely nonconstant
    # registered-tail world while the first four isolate the structural skip
    # branches m>=T and H<T.
    scores = np.column_stack((scores, _score_matrix()[:, 0]))
    bounds = rw.solve_legal_bounds(players, scores)
    book = np.asarray(
        [threshold, threshold - 1, threshold, threshold - 1, 219_000_000],
        dtype=np.int64,
    )
    result = rw.solve_residual_pricing(
        players,
        scores,
        book,
        bounds.lower_micro,
        bounds.upper_micro,
        thresholds_micro=(threshold,),
    )
    assert result.scores_micro[:4] == (
        threshold, threshold - 1, threshold, threshold - 1,
    )
    assert result.indicators_by_threshold[0][:4] == (0, 0, 0, 0)


@pytest.mark.parametrize(("score", "threshold", "expected"), (
    (219, 220, 0),
    (220, 220, 1),
    (221, 220, 1),
))
def test_binary_tail_indicator_is_iff_at_t_minus_one_t_and_t_plus_one(
    score, threshold, expected,
):
    problem = rw.pulp.LpProblem("binary_tail_unit", rw.pulp.LpMaximize)
    source = rw.pulp.LpVariable("source", cat="Binary")
    problem += source == 1
    number = rw._binary_weighted_sum(
        problem, ((source, score),), upper_bound=score, name="unit_score",
    )
    indicator = rw._binary_ge_indicator(
        problem, number, threshold, name="unit_tail",
    )
    problem.setObjective(indicator)
    problem.solve(rw.pulp.PULP_CBC_CMD(msg=0))
    assert rw.pulp.LpStatus[problem.status] == "Optimal"
    assert rw._binary_value(number) == score
    assert rw._integer_value(indicator) == expected


def test_rank_sum_ambiguity_uses_exact_canonical_incidence_fallback():
    players = _players()
    scores = np.full((len(players), 1), 25_000_000, dtype=np.int64)
    # Make the 230 tier genuinely nonconstant (the runner only prices active
    # queue worlds) while retaining a small, known rank-tied optimum face.
    aqb_row = next(
        index for index, player in enumerate(players)
        if player.player_id == "AQB"
    )
    scores[aqb_row, 0] += 10_000_000
    bounds = rw.solve_legal_bounds(players, scores)
    ranks = {
        player_id: index + 1 for index, player_id in enumerate(sorted(
            player.player_id for player in players
        ))
    }
    grouped: dict[int, list[tuple[str, ...]]] = defaultdict(list)
    for roster in _legal_rosters():
        if "AQB" not in roster:
            continue
        grouped[sum(ranks[player_id] for player_id in roster)].append(roster)
    ambiguous_rank = min(rank for rank, values in grouped.items() if len(values) > 1)
    forbidden = tuple(
        roster for rank, values in grouped.items() if rank < ambiguous_rank
        for roster in values
    )
    assert len(forbidden) == 1
    result = rw.solve_residual_pricing(
        players,
        scores,
        [225_000_000],
        bounds.lower_micro,
        bounds.upper_micro,
        control_rosters=forbidden,
    )
    assert result.rank_sum_ambiguous is True
    assert result.rank_sum == ambiguous_rank
    assert result.roster == min(grouped[ambiguous_rank])
    incidence = tuple(
        evidence for evidence in result.solve_evidence
        if evidence.solve_label.startswith("canonical incidence chunk")
    )
    assert incidence
    assert len(incidence) <= (len(players) + 3) // 4
    assert all(0 <= evidence.objective <= 15 for evidence in incidence)
    assert all(
        not any(
            line.split()[:1] == ["**"]
            for line in rw.Path(evidence.solution_path).read_text().splitlines()
        )
        for evidence in incidence
    )
    residual_upper = bounds.upper_micro[0] - 225_000_000
    coefficient_width = max(
        max(abs(int(value)) for value in scores[:, 0]), 225_000_000
    )
    residual_width = max(
        1, residual_upper.bit_length(), coefficient_width.bit_length()
    )
    mask = rw._residual_chunk_solver_mask(
        result.residual_gain_micro,
        residual_upper,
        bit_width=residual_width,
    )
    residual_labels = {
        evidence.solve_label for evidence in result.solve_evidence
        if "residual_gain chunk" in evidence.solve_label
    }
    assert residual_labels == {
        f"pricing tier residual_gain chunk {index:02d}"
        for index, needs_solver in enumerate(mask) if needs_solver
    }
    assert any(not needs_solver for needs_solver in mask)
    reversed_result = rw.solve_residual_pricing(
        tuple(reversed(players)),
        scores[::-1],
        [225_000_000],
        bounds.lower_micro,
        bounds.upper_micro,
        control_rosters=forbidden,
    )
    assert reversed_result == result


def test_no_good_cut_returns_exact_brute_force_next_identity():
    players = _players()
    scores = _score_matrix()
    bounds = rw.solve_legal_bounds(players, scores)
    book = np.array([218, 205, 192, 181], dtype=np.int64) * 1_000_000
    first, _ = _brute_pricing(scores, book)
    second, _ = _brute_pricing(scores, book, {first[2]})
    result = rw.solve_residual_pricing(
        players,
        scores,
        book,
        bounds.lower_micro,
        bounds.upper_micro,
        control_rosters=[first[2]],
    )
    assert result.roster == second[2]
    assert result.objective_vector == second[0]
    assert result.roster != first[2]


def test_no_good_list_is_complete_across_controls_and_previous_columns():
    rosters = _legal_rosters()
    controls = rosters[:2]
    previous = rosters[2:4]
    assert rw.complete_no_good_rosters(controls, previous) == (
        *controls, *previous,
    )
    with pytest.raises(rw.ResidualWorldError, match="duplicates an original"):
        rw.complete_no_good_rosters(controls, [controls[0]])
    with pytest.raises(rw.ResidualWorldError, match="previous generated"):
        rw.complete_no_good_rosters(controls, [previous[0], previous[0]])


def test_pricing_rejects_book_maximum_outside_exact_legal_bounds():
    players = _players()
    scores = _score_matrix()[:, :1]
    bounds = rw.solve_legal_bounds(players, scores)
    for book in (bounds.lower_micro[0] - 1, bounds.upper_micro[0] + 1):
        with pytest.raises(rw.ResidualWorldError, match="outside its exact"):
            rw.solve_residual_pricing(
                players,
                scores,
                [book],
                bounds.lower_micro,
                bounds.upper_micro,
            )


def _cbc_evidence_problem():
    model = rw.build_legal_lineup_model(_players(), name="evidence_fixture")
    expression = rw.pulp.lpSum(
        (index + 1) * model.decision[player.player_id]
        for index, player in enumerate(model.players)
    )
    model.problem.sense = rw.pulp.LpMaximize
    model.problem.setObjective(expression)
    return model.problem


@pytest.mark.parametrize(
    "poison",
    (
        "gap_terminal",
        "warning",
        "nonzero_gap_command",
        "objective_mismatch",
        "wall_at_limit",
    ),
)
def test_cbc_evidence_parser_rejects_nonexact_or_mutated_proofs(poison):
    problem = _cbc_evidence_problem()
    solver = rw.make_cbc_solver(120, False)
    problem.solve(solver)
    log_path = rw.Path(solver.evidence_directory / "cbc.log")
    solution_path = solver.artifact_paths["sol"]
    if poison == "gap_terminal":
        text = log_path.read_text().replace(
            "Result - Optimal solution found",
            "Result - Optimal solution found (within gap tolerance)",
        )
        log_path.write_text(text)
    elif poison == "warning":
        log_path.write_text(log_path.read_text() + "\nCbc9999W poison warning\n")
    elif poison == "nonzero_gap_command":
        log_path.write_text(
            log_path.read_text().replace("-ratio 0.0", "-ratio 0.5")
        )
    elif poison == "objective_mismatch":
        lines = solution_path.read_text().splitlines()
        value = rw.Decimal(lines[0].rsplit(" ", 1)[1])
        lines[0] = f"Optimal - objective value {value + 1}"
        solution_path.write_text("\n".join(lines) + "\n")
    elif poison == "wall_at_limit":
        log_path.write_text(
            rw.re.sub(
                r"^Time \(Wallclock seconds\):\s+[^\n]+$",
                "Time (Wallclock seconds):       120.00",
                log_path.read_text(),
                count=1,
                flags=rw.re.MULTILINE,
            )
        )
    with pytest.raises(rw.SolverFailure):
        rw._parse_cbc_evidence(problem, solver, "poison")


def test_cbc_evidence_is_unique_and_bare_solver_cannot_license_result():
    problem = _cbc_evidence_problem()
    solver = rw.make_cbc_solver(120, False)
    evidence = rw._solve(problem, solver, "golden exact solve")
    assert evidence.objective == rw._integer_value(problem.objective)
    assert evidence.integer_tolerance == Decimal("1e-12")
    assert "-integerTolerance 1e-12" in evidence.command_line
    assert rw._sha256_file(rw.Path(evidence.model_path)) == evidence.model_sha256
    with pytest.raises(rw.SolverFailure, match="reused"):
        rw._parse_cbc_evidence(problem, solver, "reuse")
    with pytest.raises(rw.SolverFailure, match="lacks retained"):
        rw._solve(
            _cbc_evidence_problem(),
            rw.pulp.PULP_CBC_CMD(msg=0),
            "bare solver",
        )


def test_warm_cbc_evidence_binds_every_normalized_mip_start_value():
    problem = _cbc_evidence_problem()
    cold_evidence = rw._solve(
        problem, rw.make_cbc_solver(120, False), "cold seed"
    )
    expected = tuple(
        (variable.name, int(round(float(variable.value()))))
        for variable in problem.variables()
    )
    warm_solver = rw.make_cbc_solver(120, True)
    warm_solver.optionsDict["cuts"] = False
    warm_solver.cuts_exact = False
    warm_solver.disable_preprocess()
    evidence = rw._solve(problem, warm_solver, "warm exact solve")
    assert evidence.mip_start_values == expected
    assert evidence.mip_start_variable_count == len(expected)
    assert evidence.mip_start_values_sha256 == rw._canonical_json_sha256([
        [name, value] for name, value in expected
    ])
    assert evidence.predecessor_assignment_sha256 == (
        cold_evidence.canonical_assignment_sha256
    )
    assert evidence.mip_start_reconstructed_objective == cold_evidence.objective
    assert evidence.mip_start_path is not None
    renamed_sha, count = rw._validate_mip_start_body(
        rw.Path(evidence.mip_start_path).read_text(encoding="utf-8"),
        [value for _, value in expected],
    )
    assert renamed_sha == evidence.mip_start_renamed_values_sha256
    assert count == evidence.mip_start_variable_count
    rw.validate_cbc_solve_evidence(evidence)

    assert evidence.mip_start_values is not None
    poisoned_values = list(evidence.mip_start_values)
    name, value = poisoned_values[0]
    poisoned_values[0] = (name, 1 - value)
    with pytest.raises(rw.SolverFailure, match="MIP-start"):
        rw.validate_cbc_solve_evidence(replace(
            evidence, mip_start_values=tuple(poisoned_values)
        ))


def test_warm_solve_rejects_forged_predecessor_and_infeasible_new_auxiliary():
    problem = _cbc_evidence_problem()
    rw._solve(problem, rw.make_cbc_solver(120, False), "cold predecessor")
    original = tuple(problem._residual_proven_assignment)
    name, value = original[0]
    problem._residual_proven_assignment = (
        (name, 1 - value), *original[1:]
    )
    with pytest.raises(rw.SolverFailure, match="predecessor assignment differs"):
        rw._solve(
            problem,
            rw.make_cbc_solver(120, True),
            "forged predecessor",
        )

    problem._residual_proven_assignment = original
    auxiliary = rw.pulp.LpVariable("new_auxiliary", 0, 1, cat="Binary")
    problem += auxiliary == 0, "new_auxiliary_must_be_zero"
    auxiliary.setInitialValue(1)
    with pytest.raises(rw.SolverFailure, match="MIP start violates a current PuLP row"):
        rw._solve(
            problem,
            rw.make_cbc_solver(120, True),
            "infeasible expanded predecessor",
        )


def test_warm_solve_requires_all_three_predecessor_attributes():
    problem = _cbc_evidence_problem()
    rw._solve(problem, rw.make_cbc_solver(120, False), "complete predecessor")
    for attribute in (
        "_residual_proven_assignment",
        "_residual_proven_assignment_sha256",
        "_residual_proven_evidence",
    ):
        value = getattr(problem, attribute)
        delattr(problem, attribute)
        with pytest.raises(rw.SolverFailure, match="predecessor lacks"):
            rw._solve(
                problem,
                rw.make_cbc_solver(120, True),
                f"missing predecessor {attribute}",
            )
        setattr(problem, attribute, value)


def test_ordered_audit_rejects_alternate_feasible_warm_start(tmp_path):
    root = tmp_path / "ordered-predecessor"
    root.mkdir()
    problem = _cbc_evidence_problem()
    cold = rw._solve(
        problem,
        rw.make_cbc_solver(120, False, evidence_root=root),
        "ordered cold predecessor",
    )
    warm_solver = rw.make_cbc_solver(120, True, evidence_root=root)
    warm_solver.optionsDict["cuts"] = False
    warm_solver.cuts_exact = False
    warm_solver.disable_preprocess()
    warm = rw._solve(problem, warm_solver, "ordered warm successor")
    rw._validate_ordered_warm_predecessor(cold, warm)

    assert warm.mip_start_values is not None
    player_for_variable = {
        f"x_{index:04d}": player.player_id
        for index, player in enumerate(sorted(
            _players(), key=lambda player: player.player_id
        ))
    }
    prior_roster = frozenset(
        player_for_variable[name]
        for name, value in rw._scientific_assignment_from_evidence(cold)
        if value == 1
    )
    alternate_roster = next(
        roster for roster in _legal_rosters()
        if frozenset(roster) != prior_roster
    )
    alternate_values = tuple(
        (name, int(player_for_variable[name] in alternate_roster))
        for name, _ in warm.mip_start_values
    )
    parsed = rw._parse_exact_mps(rw.Path(warm.model_path))
    alternate_objective = rw._validate_assignment_against_mps(
        parsed,
        warm.variable_domain_manifest,
        dict(alternate_values),
    )
    mip_path = rw.Path(warm.mip_start_path)
    mip_text = "\n".join((
        "Stopped on time - objective value 0",
        *(
            f"{index} X{index:07d} {value} 0"
            for index, (_, value) in enumerate(alternate_values)
        ),
        "",
    ))
    mip_path.write_text(mip_text, encoding="utf-8")
    renamed_sha, count = rw._validate_mip_start_body(
        mip_text, [value for _, value in alternate_values]
    )
    poisoned = replace(
        warm,
        mip_start_sha256=rw._sha256_file(mip_path),
        mip_start_values_sha256=rw._canonical_json_sha256([
            [name, value] for name, value in alternate_values
        ]),
        mip_start_renamed_values_sha256=renamed_sha,
        mip_start_variable_count=count,
        mip_start_reconstructed_objective=alternate_objective,
        mip_start_values=alternate_values,
    )
    # The poison is a coherent, complete, current-MPS-feasible retained start
    # with the genuine predecessor digest.  Only the ordered chain audit can
    # prove that it is not the predecessor assignment actually licensed.
    rw.validate_cbc_solve_evidence(poisoned)
    with pytest.raises(rw.SolverFailure, match="prior canonical assignment"):
        rw._validate_ordered_warm_predecessor(cold, poisoned)


def test_retained_evidence_reparses_command_and_complete_solution(tmp_path):
    problem = _cbc_evidence_problem()
    root = tmp_path / "evidence"
    root.mkdir()
    evidence = rw._solve(
        problem,
        rw.make_cbc_solver(120, False, evidence_root=root),
        "retained exact solve",
    )
    rw.validate_cbc_solve_evidence(evidence)
    for poison in (
        replace(evidence, cuts=None),
        replace(evidence, preprocess_off=True),
        replace(evidence, max_seconds=121),
        replace(evidence, random_seed=evidence.random_seed + 1),
        replace(evidence, threads=2),
        replace(evidence, time_mode="cpu"),
        replace(evidence, absolute_gap=Decimal("1")),
        replace(evidence, integer_tolerance=Decimal("1e-7")),
    ):
        with pytest.raises(rw.SolverFailure):
            rw.validate_cbc_solve_evidence(poison)

    alias_parent = tmp_path / "evidence-parent-alias"
    alias_parent.symlink_to(tmp_path, target_is_directory=True)
    aliased_root = alias_parent / root.name
    aliased_directory = aliased_root / rw.Path(
        evidence.evidence_directory
    ).name
    aliased = replace(
        evidence,
        evidence_directory=str(aliased_directory),
        log_path=str(aliased_directory / rw.Path(evidence.log_path).name),
        solution_path=str(
            aliased_directory / rw.Path(evidence.solution_path).name
        ),
        model_path=str(aliased_directory / rw.Path(evidence.model_path).name),
        variable_domain_manifest_path=str(
            aliased_directory
            / rw.Path(evidence.variable_domain_manifest_path).name
        ),
    )
    with pytest.raises(rw.SolverFailure, match="ancestor"):
        rw.validate_cbc_solve_evidence(aliased)
    with pytest.raises(rw.SolverFailure, match="ancestor"):
        rw.make_cbc_solver(120, False, evidence_root=aliased_root)

    solution_path = rw.Path(evidence.solution_path)
    solution = solution_path.read_text()
    solution_path.write_text(solution.splitlines()[0] + "\n")
    truncated = replace(
        evidence, solution_sha256=rw._sha256_file(solution_path)
    )
    with pytest.raises(rw.SolverFailure, match="solution body"):
        rw.validate_cbc_solve_evidence(truncated)


def test_integer_token_decode_boundary_is_literal_complete_and_signed(tmp_path):
    root = tmp_path / "integer-decode"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        "integer decode boundary",
    )
    solution_path = rw.Path(evidence.solution_path)
    model_path = rw.Path(evidence.model_path)
    original = solution_path.read_text()
    model = rw._parse_exact_mps(model_path)
    target = 1 + len(model.rows)
    lines = original.splitlines()
    fields = lines[target].split()
    canonical = int(Decimal(fields[2]))
    direction = Decimal(1) if canonical == 0 else Decimal(-1)

    def mutated_solution(delta: Decimal) -> str:
        changed = original.splitlines()
        values = changed[target].split()
        values[2] = str(Decimal(canonical) + direction * delta)
        changed[target] = " ".join(values)
        return "\n".join(changed) + "\n"

    at_boundary = mutated_solution(rw.CBC_INTEGER_DECODE_EPS)
    (
        objective,
        assignment_sha,
        affected_count,
        maximum_residual,
        decode_rows,
        sense,
    ) = rw._validate_solution_body(
        at_boundary, model_path, evidence.variable_domain_manifest
    )
    assert objective == evidence.objective
    assert assignment_sha == evidence.canonical_assignment_sha256
    assert affected_count == 1
    assert maximum_residual == rw.CBC_INTEGER_DECODE_EPS
    assert len(decode_rows) == len(evidence.variable_domain_manifest)
    assert decode_rows[0][0] == "X0000000"
    assert Decimal(decode_rows[0][3]) == direction * rw.CBC_INTEGER_DECODE_EPS
    assert sum(Decimal(row[3]) != 0 for row in decode_rows) == 1
    assert sense == evidence.problem_sense

    solution_path.write_text(at_boundary)
    boundary_receipt = replace(
        evidence,
        solution_sha256=rw._sha256_file(solution_path),
        canonical_assignment_sha256=assignment_sha,
        integer_decode_affected_count=affected_count,
        integer_decode_max_residual=maximum_residual,
        integer_decode_rows=decode_rows,
    )
    rw.validate_cbc_solve_evidence(boundary_receipt)

    above = rw.CBC_INTEGER_DECODE_EPS + Decimal("1e-12")
    with pytest.raises(rw.SolverFailure, match="decode epsilon"):
        rw._validate_solution_body(
            mutated_solution(above),
            model_path,
            evidence.variable_domain_manifest,
        )
    changed = original.splitlines()
    values = changed[target].split()
    values[2] = "0.9999999995"
    changed[target] = " ".join(values)
    with pytest.raises(rw.SolverFailure, match="decode epsilon"):
        rw._validate_solution_body(
            "\n".join(changed) + "\n",
            model_path,
            evidence.variable_domain_manifest,
        )


@pytest.mark.parametrize(
    "mutation",
    ("category", "bounds", "duplicate_scientific", "missing", "reordered"),
)
def test_variable_domain_manifest_poison_fails_closed(tmp_path, mutation):
    root = tmp_path / f"manifest-{mutation}"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        f"manifest poison {mutation}",
    )
    manifest = list(evidence.variable_domain_manifest)
    if mutation == "category":
        renamed, scientific, domain, lower, upper = manifest[0]
        assert domain == "binary"
        manifest[0] = (renamed, scientific, "integer", lower, upper)
    elif mutation == "bounds":
        renamed, scientific, domain, lower, upper = manifest[0]
        manifest[0] = (renamed, scientific, domain, lower, upper + 1)
    elif mutation == "duplicate_scientific":
        renamed, _, domain, lower, upper = manifest[1]
        manifest[1] = (renamed, manifest[0][1], domain, lower, upper)
    elif mutation == "missing":
        manifest.pop()
    else:
        manifest[0], manifest[1] = manifest[1], manifest[0]
    with pytest.raises(rw.SolverFailure, match="manifest|category|bounds"):
        rw._validate_solution_body(
            rw.Path(evidence.solution_path).read_text(),
            rw.Path(evidence.model_path),
            tuple(manifest),
        )


def test_strict_mps_parser_preserves_pinned_bound_and_category_semantics(
    tmp_path,
):
    problem = rw.pulp.LpProblem("strict_mps_profile", rw.pulp.LpMaximize)
    bounded = rw.pulp.LpVariable(
        "bounded_integer", lowBound=2, upBound=3, cat="Integer"
    )
    upper_only = rw.pulp.LpVariable(
        "upper_only_integer", lowBound=None, upBound=4, cat="Integer"
    )
    lower_only = rw.pulp.LpVariable(
        "lower_only_integer", lowBound=0, upBound=None, cat="Integer"
    )
    fixed = rw.pulp.LpVariable(
        "fixed_continuous", lowBound=7, upBound=7, cat="Continuous"
    )
    implied = rw.pulp.LpVariable(
        "implied_integer", lowBound=1, upBound=5, cat="Continuous"
    )
    rw._register_implied_integer(problem, implied)
    # Registration is not evidence by itself: the frozen proof profile now
    # requires an exact acyclic equality circuit from already-integral
    # columns.  This fixture intentionally supplies that proof.
    problem += implied == bounded
    problem += bounded + upper_only + lower_only + fixed + implied <= 20
    problem.setObjective(bounded + upper_only + lower_only + fixed + implied)
    model_path = tmp_path / "profile.mps"
    problem.writeMPS(str(model_path), rename=1)
    parsed = rw._parse_exact_mps(model_path)
    manifest = rw._variable_domain_manifest(problem)
    by_scientific = {
        scientific: (renamed, domain, lower, upper)
        for renamed, scientific, domain, lower, upper in manifest
    }
    for scientific, expected in {
        "bounded_integer": ("integer", 2, 3),
        "upper_only_integer": ("integer", None, 4),
        "lower_only_integer": ("integer", 0, None),
        "fixed_continuous": ("fixed_integer", 7, 7),
        "implied_integer": ("implied_integer", 1, 5),
    }.items():
        renamed, domain, lower, upper = by_scientific[scientific]
        assert (domain, lower, upper) == expected
        assert parsed.bounds[renamed] == (lower, upper)
        assert parsed.column_categories[renamed] == (
            domain if domain == "integer" else "continuous"
        )


def test_residual_problem_clone_preserves_implied_registry_without_aliasing():
    problem = rw.pulp.LpProblem("clone_metadata", rw.pulp.LpMaximize)
    selected = rw.pulp.LpVariable("selected", cat="Binary")
    implied = rw.pulp.LpVariable(
        "implied", lowBound=0, upBound=1, cat="Continuous"
    )
    rw._register_implied_integer(problem, implied)
    problem += implied == selected, "implied_definition"
    problem.setObjective(implied)

    # This is the exact PuLP defect the audited wrapper closes.
    raw_clone = problem.deepcopy()
    assert getattr(raw_clone, "_residual_implied_integer_names", None) is None

    clone = rw._clone_residual_problem(problem)
    source_registry = problem._residual_implied_integer_names
    clone_registry = clone._residual_implied_integer_names
    assert clone_registry == frozenset({"implied"})
    assert isinstance(clone_registry, frozenset)
    assert clone_registry is not source_registry
    source_registry.add("later_source_only_mutation")
    assert clone._residual_implied_integer_names == frozenset({"implied"})
    assert rw._variable_domain_manifest(clone)


@pytest.mark.parametrize(
    "poison",
    (
        "truncated_log",
        "duplicate_terminal",
        "duplicate_objective",
        "stopped_solution",
        "gap_solution",
        "upper_bound",
        "partial_search",
        "nonzero_model_errors",
        "nonfinite_time",
        "bare_inf",
        "malformed_inf_diagnostic",
        "infinity_marker",
        "wrong_seed_command",
        "starred_row",
        "starred_column",
        "fractional_integer",
        "bound_violation",
        "mps_duplicate_coefficient",
        "mps_zero_coefficient",
        "mps_unknown_row",
        "mps_unbalanced_marker",
        "mps_duplicate_rhs",
        "mps_missing_rhs",
        "mps_duplicate_bound",
        "mps_unsupported_bound",
        "mps_noncontiguous_row",
        "mps_wrong_sense",
        "mps_oversized_coefficient",
        "mps_oversized_activity",
    ),
)
def test_retained_evidence_poison_records_fail_closed(tmp_path, poison):
    problem = _cbc_evidence_problem()
    root = tmp_path / poison
    root.mkdir()
    evidence = rw._solve(
        problem,
        rw.make_cbc_solver(120, False, evidence_root=root),
        f"poison {poison}",
    )
    log_path = rw.Path(evidence.log_path)
    solution_path = rw.Path(evidence.solution_path)
    model_path = rw.Path(evidence.model_path)
    log = log_path.read_text()
    solution = solution_path.read_text()
    model = model_path.read_text()
    command_line = evidence.command_line
    if poison == "truncated_log":
        log = "Welcome to the CBC MILP Solver\n"
    elif poison == "duplicate_terminal":
        log += "\nResult - Optimal solution found\n"
    elif poison == "duplicate_objective":
        log += f"\nObjective value: {evidence.objective}\n"
    elif poison == "stopped_solution":
        solution = solution.replace(
            "Optimal - objective value", "Stopped on time - objective value", 1
        )
    elif poison == "gap_solution":
        solution = solution.replace(
            "Optimal - objective value",
            "Optimal (within gap tolerance) - objective value",
            1,
        )
    elif poison == "upper_bound":
        log += "\nUpper bound: 999\nGap: 0.1\n"
    elif poison == "partial_search":
        log += "\nPartial search - incumbent only\n"
    elif poison == "nonzero_model_errors":
        log = log.replace("MODEL read with 0 errors", "MODEL read with 1 errors")
    elif poison == "nonfinite_time":
        log = rw.re.sub(
            r"^Time \(Wallclock seconds\):\s+[^\n]+$",
            "Time (Wallclock seconds): nan",
            log,
            count=1,
            flags=rw.re.MULTILINE,
        )
    elif poison == "bare_inf":
        log += "\nPoison diagnostic inf\n"
    elif poison == "malformed_inf_diagnostic":
        log += "\nClp0006I 0 Obj 1 Primal inf not-a-number (1)\n"
    elif poison == "infinity_marker":
        log += "\nPoison diagnostic infinity\n"
    elif poison == "wrong_seed_command":
        log = log.replace("-randomSeed 170817", "-randomSeed 170818", 1)
        command_line = command_line.replace(
            "-randomSeed 170817", "-randomSeed 170818", 1
        )
    elif poison.startswith("mps_"):
        lines = model.splitlines()
        columns = lines.index("COLUMNS")
        rhs = lines.index("RHS")
        bounds = lines.index("BOUNDS")
        first_column = next(
            index for index in range(columns + 1, rhs)
            if lines[index].split()[0] != "MARK"
        )
        first_rhs = rhs + 1
        first_bound = bounds + 1
        if poison == "mps_duplicate_coefficient":
            lines.insert(first_column + 1, lines[first_column])
        elif poison == "mps_zero_coefficient":
            fields = lines[first_column].split()
            fields[2] = "0.000000000000e+00"
            lines[first_column] = "    " + "  ".join(fields)
        elif poison == "mps_unknown_row":
            fields = lines[first_column].split()
            fields[1] = "C9999999"
            lines[first_column] = "    " + "  ".join(fields)
        elif poison == "mps_unbalanced_marker":
            marker = next(
                index for index in range(columns + 1, rhs)
                if "'INTEND'" in lines[index]
            )
            lines.pop(marker)
        elif poison == "mps_duplicate_rhs":
            lines.insert(first_rhs + 1, lines[first_rhs])
        elif poison == "mps_missing_rhs":
            lines.pop(first_rhs)
        elif poison == "mps_duplicate_bound":
            lines.insert(first_bound + 1, lines[first_bound])
        elif poison == "mps_unsupported_bound":
            fields = lines[first_bound].split()
            lines[first_bound] = (
                f" LI BND       {fields[2]}   0.000000000000e+00"
            )
        elif poison == "mps_noncontiguous_row":
            rows = lines.index("ROWS")
            fields = lines[rows + 2].split()
            fields[1] = "C0000001"
            lines[rows + 2] = " " + "  ".join(fields)
        elif poison == "mps_wrong_sense":
            lines[0] = "*SENSE:Minimize"
        elif poison == "mps_oversized_coefficient":
            fields = lines[first_column].split()
            fields[2] = str(rw.CBC_EXACT_INTEGER_MAX + 1)
            lines[first_column] = "    " + "  ".join(fields)
        else:
            by_row = defaultdict(list)
            for index in range(columns + 1, rhs):
                fields = lines[index].split()
                if fields[0] != "MARK":
                    by_row[fields[1]].append(index)
            first, second = next(
                indices[:2] for indices in by_row.values()
                if len(indices) >= 2
            )
            for index in (first, second):
                fields = lines[index].split()
                fields[2] = str(1 << 52)
                lines[index] = "    " + "  ".join(fields)
        model = "\n".join(lines) + "\n"
    elif poison in {"starred_row", "starred_column"}:
        lines = solution.splitlines()
        target = 1 if poison == "starred_row" else len(lines) - 1
        lines[target] = f"** {lines[target]}"
        solution = "\n".join(lines) + "\n"
    else:
        lines = solution.splitlines()
        target = next(
            index for index, line in enumerate(lines[1:], 1)
            if line.split()[1].startswith("X")
        )
        fields = lines[target].split()
        fields[2] = "0.5" if poison == "fractional_integer" else "2"
        lines[target] = " ".join(fields)
        solution = "\n".join(lines) + "\n"
    log_path.write_text(log)
    solution_path.write_text(solution)
    model_path.write_text(model)
    poisoned = replace(
        evidence,
        command_line=command_line,
        log_sha256=rw._sha256_file(log_path),
        solution_sha256=rw._sha256_file(solution_path),
        model_sha256=rw._sha256_file(model_path),
    )
    with pytest.raises(rw.SolverFailure):
        rw.validate_cbc_solve_evidence(poisoned)


def test_retained_evidence_allows_nonlicensing_row_display_drift(tmp_path):
    root = tmp_path / "row-display-drift"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        "row display drift",
    )
    solution_path = rw.Path(evidence.solution_path)
    lines = solution_path.read_text().splitlines()
    fields = lines[1].split()
    fields[2] = str(Decimal(fields[2]) + Decimal("1.23456789"))
    lines[1] = " ".join(fields)
    solution_path.write_text("\n".join(lines) + "\n")
    drifted = replace(
        evidence,
        solution_sha256=rw._sha256_file(solution_path),
    )
    # Printed row activities are retained, hashed, ordered, unique and finite,
    # but exact feasibility is licensed only by the canonical assignment/MPS.
    rw.validate_cbc_solve_evidence(drifted)


def test_finite_cbc_primal_dual_infeasibility_diagnostics_are_not_nonfinite(
    tmp_path,
):
    problem = _cbc_evidence_problem()
    root = tmp_path / "finite-inf-diagnostic"
    root.mkdir()
    evidence = rw._solve(
        problem,
        rw.make_cbc_solver(120, False, evidence_root=root),
        "finite diagnostic exact solve",
    )
    log_path = rw.Path(evidence.log_path)
    log_path.write_text(
        log_path.read_text()
        + "\nClp0006I 0 Obj 159.751 Primal inf 0.041309618 (1)\n"
        + "0  Obj 68 Primal inf 2.6426869e-10 (1) "
        + "Dual inf 1.2475957e+17 (2)\n"
    )
    rw.validate_cbc_solve_evidence(replace(
        evidence, log_sha256=rw._sha256_file(log_path)
    ))


def test_retained_validation_rehashes_the_cbc_binary_without_cache(tmp_path):
    problem = _cbc_evidence_problem()
    root = tmp_path / "binary-rehash-evidence"
    root.mkdir()
    evidence = rw._solve(
        problem,
        rw.make_cbc_solver(120, False, evidence_root=root),
        "binary rehash exact solve",
    )
    copied_binary = tmp_path / "cbc-copy"
    shutil.copyfile(evidence.cbc_path, copied_binary)
    log_path = rw.Path(evidence.log_path)
    command_tokens = rw.shlex.split(evidence.command_line)
    command_tokens[0] = str(copied_binary)
    copied_command = rw.shlex.join(command_tokens)
    log_path.write_text(
        log_path.read_text().replace(
            evidence.command_line, copied_command, 1
        )
    )
    relocated = replace(
        evidence,
        cbc_path=str(copied_binary),
        cbc_sha256=rw._sha256_file(copied_binary),
        command_line=copied_command,
        log_sha256=rw._sha256_file(log_path),
    )
    rw.validate_cbc_solve_evidence(relocated)
    with copied_binary.open("ab") as destination:
        destination.write(b"\0")
    with pytest.raises(rw.SolverFailure, match="binary identity"):
        rw.validate_cbc_solve_evidence(relocated)


def test_final_evidence_inventory_rehashes_every_prior_step(tmp_path):
    root = tmp_path / "final-inventory"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        "final inventory exact solve",
    )
    steps = (SimpleNamespace(
        pricing=SimpleNamespace(solve_evidence=(evidence,))
    ),)
    rw._audit_evidence_root_inventory(root, steps)
    log_path = rw.Path(evidence.log_path)
    log_path.write_text(log_path.read_text() + "\npost-step mutation\n")
    with pytest.raises(rw.SolverFailure, match="log hash changed"):
        rw._audit_evidence_root_inventory(root, steps)


def test_final_evidence_inventory_rejects_outside_directory_symlink(tmp_path):
    root = tmp_path / "symlink-inventory"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        "symlink inventory exact solve",
    )
    steps = (SimpleNamespace(
        pricing=SimpleNamespace(solve_evidence=(evidence,))
    ),)
    directory = rw.Path(evidence.evidence_directory)
    outside = tmp_path / "outside-solve"
    directory.rename(outside)
    directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(
        (rw.ResidualWorldError, rw.SolverFailure), match="symlink|escaped"
    ):
        rw._audit_evidence_root_inventory(root, steps)


def test_retained_evidence_rejects_outside_artifact_symlink(tmp_path):
    root = tmp_path / "artifact-symlink-inventory"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        "artifact symlink exact solve",
    )
    log_path = rw.Path(evidence.log_path)
    outside_log = tmp_path / "outside-cbc.log"
    log_path.rename(outside_log)
    log_path.symlink_to(outside_log)
    with pytest.raises(rw.SolverFailure, match="reused or misplaced"):
        rw.validate_cbc_solve_evidence(evidence)


def test_final_inventory_rejects_extra_symlink_to_expected_artifact(tmp_path):
    root = tmp_path / "extra-artifact-symlink"
    root.mkdir()
    evidence = rw._solve(
        _cbc_evidence_problem(),
        rw.make_cbc_solver(120, False, evidence_root=root),
        "extra artifact symlink exact solve",
    )
    steps = (SimpleNamespace(
        pricing=SimpleNamespace(solve_evidence=(evidence,))
    ),)
    duplicate = rw.Path(evidence.evidence_directory) / "duplicate-log-link"
    duplicate.symlink_to(rw.Path(evidence.log_path))
    with pytest.raises(rw.ResidualWorldError, match="inventory changed"):
        rw._audit_evidence_root_inventory(root, steps)


def test_pricing_evidence_is_semantically_bound_to_inputs_and_run_root(tmp_path):
    players = _players()
    scores = _score_matrix()
    bounds = rw.solve_legal_bounds(players, scores)
    book = np.array([218, 205, 192, 181], dtype=np.int64) * 1_000_000
    root = tmp_path / "pricing"
    root.mkdir()
    result = rw.solve_residual_pricing(
        players,
        scores,
        book,
        bounds.lower_micro,
        bounds.upper_micro,
        solver_factory=lambda seconds, warm: rw.make_cbc_solver(
            seconds, warm, evidence_root=root
        ),
    )
    rw._audit_pricing_result(
        result,
        players,
        scores,
        book,
        bounds.lower_micro,
        bounds.upper_micro,
        (),
        root,
    )
    with pytest.raises(rw.ResidualWorldError, match="input binding"):
        rw._audit_pricing_result(
            replace(result, pricing_input_sha256="0" * 64),
            players, scores, book, bounds.lower_micro, bounds.upper_micro,
            (), root,
        )
    with pytest.raises(rw.ResidualWorldError, match="ambiguity"):
        rw._audit_pricing_result(
            replace(
                result,
                rank_sum_ambiguous=not result.rank_sum_ambiguous,
            ),
            players, scores, book, bounds.lower_micro, bounds.upper_micro,
            (), root,
        )
    with pytest.raises(rw.ResidualWorldError, match="evidence"):
        rw._audit_pricing_result(
            replace(result, solve_evidence=result.solve_evidence[:1]),
            players, scores, book, bounds.lower_micro, bounds.upper_micro,
            (), root,
        )
    with pytest.raises(rw.ResidualWorldError, match="semantic law"):
        rw._audit_pricing_result(
            replace(result, solve_evidence=tuple(reversed(result.solve_evidence))),
            players, scores, book, bounds.lower_micro, bounds.upper_micro,
            (), root,
        )


@pytest.mark.parametrize(
    "unregistered_mode", ("time", "nodes", "solutions", "relative_gap")
)
def test_cbc_coordinator_rejects_limit_and_nonzero_gap_modes(unregistered_mode):
    problem = _cbc_evidence_problem()
    solver = rw.make_cbc_solver(120, False)
    if unregistered_mode == "time":
        solver.timeLimit = 0.001
    elif unregistered_mode == "nodes":
        solver.options.append("maxNodes 0")
    elif unregistered_mode == "solutions":
        solver.options.append("maxSolutions 1")
    else:
        solver.optionsDict["gapRel"] = 0.5
    with pytest.raises(rw.SolverFailure):
        rw._solve(problem, solver, f"reject {unregistered_mode}")


def test_micro_conversion_and_raw_parity_obey_nine_rounding_bound():
    raw = np.asarray([
        [10.1234564, 12.7654321],
        *[[2.0000004 + index, 3.0000004 + index] for index in range(8)],
        [1.0, 1.0],
    ], dtype=np.float32)
    micro = rw.to_micro_dk(raw)
    error = rw.validate_raw_micro_parity(raw, micro, range(9))
    assert error <= rw.RAW_MICRO_MAX_ERROR_DK
    poisoned = micro.copy()
    poisoned[0, 0] += 10
    with pytest.raises(rw.ResidualWorldError, match="canonical float32"):
        rw.validate_raw_micro_parity(raw, poisoned, range(9))
    cancelled = micro.copy()
    cancelled[0, 0] += 10
    cancelled[1, 0] -= 10
    with pytest.raises(rw.ResidualWorldError, match="canonical float32"):
        rw.validate_raw_micro_parity(raw, cancelled, range(9))
    unchosen = micro.copy()
    unchosen[9, 0] += 1
    with pytest.raises(rw.ResidualWorldError, match="canonical float32"):
        rw.validate_raw_micro_parity(raw, unchosen, range(9))


def test_position_shape_bound_matches_manual_best_classic_pattern():
    positions = [
        "QB", "QB", "RB", "RB", "RB", "WR", "WR", "WR", "WR",
        "TE", "TE", "DST", "DST",
    ]
    scores = np.asarray([
        [20], [10], [9], [8], [1], [7], [6], [5], [4], [3], [2], [4], [1],
    ], dtype=np.int64)
    assert rw.position_shape_upper_bounds_micro(scores, positions).tolist() == [66]


def test_reservoir_cycle_uses_all_tiers_deterministically_and_fails_closed():
    worlds = tuple(rw.WorldId("R0", index) for index in range(5))
    chosen = rw.select_cyclic_threshold_worlds(
        worlds,
        [29, 19, 9, 0, 0],
        [31, 30, 25, 15, 5],
        4,
        thresholds_micro=(30, 20, 10),
    )
    assert [value.world_id.index for value in chosen] == [0, 1, 2, 3]
    assert [value.queue_threshold_micro for value in chosen] == [30, 20, 10, 10]
    with pytest.raises(rw.InsufficientResidualWorldSupport, match="1 of 3"):
        rw.select_cyclic_threshold_worlds(
            worlds[:3], [29, 25, 25], [31, 26, 26], 3,
            thresholds_micro=(30,),
        )


def test_reservoir_ties_use_world_id_and_block_quotas_are_exact():
    worlds = (
        rw.WorldId("R0", 2), rw.WorldId("R0", 0), rw.WorldId("R0", 1),
        rw.WorldId("R2", 1), rw.WorldId("R2", 0),
    )
    selected = rw.select_block_stratified_worlds(
        worlds,
        [19] * 5,
        [21] * 5,
        (("R0", 2), ("R2", 1)),
        thresholds_micro=(20,),
    )
    assert [value.world_id for value in selected] == [
        rw.WorldId("R0", 0), rw.WorldId("R0", 1), rw.WorldId("R2", 0),
    ]


def _brute_pruning_steps(identities, scores, protected, steps):
    remaining = list(range(len(identities)))
    result = []
    for dose in range(1, steps + 1):
        before = rw.tail_utility(scores[remaining])
        choices = []
        for index in remaining:
            if identities[index] in protected:
                continue
            retained = [value for value in remaining if value != index]
            utility = rw.tail_utility(scores[retained])
            choices.append((utility.vector, identities[index], index))
        _, identity, index = max(choices)
        remaining.remove(index)
        result.append((dose, identity, before, rw.tail_utility(scores[remaining])))
    return tuple(result)


def test_reverse_greedy_pruning_matches_brute_force_and_lex_greatest_tie():
    identities = tuple(_identity(value) for value in ("a", "b", "c", "d"))
    scores = np.asarray([
        [0, 0, 0],
        [250, 0, 0],
        [0, 240, 0],
        [0, 0, 230],
    ], dtype=np.int64) * 1_000_000
    expected = _brute_pruning_steps(identities, scores, {identities[0]}, 2)
    result = rw.reverse_greedy_pruning_order(
        identities, scores, [identities[0]], steps=2,
    )
    assert result.removal_order == tuple(value[1] for value in expected)
    assert tuple(
        (step.dose, step.removed_identity, step.utility_before, step.utility_after)
        for step in result.steps
    ) == expected
    assert all(
        step.utility_after.vector <= step.utility_before.vector
        for step in result.steps
    )
    assert any(
        step.utility_after.vector < step.utility_before.vector
        for step in result.steps
    )

    tied = np.full((4, 2), 200_000_000, dtype=np.int64)
    tie_result = rw.reverse_greedy_pruning_order(
        identities, tied, [identities[0]], steps=1,
    )
    assert tie_result.removal_order == (identities[-1],)


def test_matched_budget_pool_is_exact_and_blocks_control_resurrection():
    control = tuple(_identity(value) for value in ("a", "b", "c", "d"))
    generated = (_identity("x"), _identity("y"))
    pruning = rw.reverse_greedy_pruning_order(
        control,
        np.asarray([[1], [2], [3], [4]], dtype=np.int64),
        [control[0]],
        steps=2,
        thresholds_micro=(1,),
    )
    treatment = rw.matched_budget_treatment_pool(
        control, pruning, generated,
    )
    assert treatment == tuple(
        value for value in control if value not in pruning.removal_order
    ) + generated
    assert len(treatment) == len(control)
    with pytest.raises(rw.ResidualWorldError, match="generated dose exceeds"):
        rw.matched_budget_treatment_pool(control, pruning, (*generated, _identity("z")))
    with pytest.raises(rw.ResidualWorldError, match="resurrects"):
        rw.matched_budget_treatment_pool(control, pruning, [control[2]])


def test_protected_book_must_reproduce_in_exact_order_at_every_dose():
    book = tuple(_identity(f"book-{index:02d}") for index in range(80))
    rw.verify_protected_book_reproduction(book, [book] * 8)
    changed = [book] * 8
    changed[1] = tuple(reversed(book))
    with pytest.raises(rw.ResidualWorldError, match="dose 2"):
        rw.verify_protected_book_reproduction(book, changed)
    with pytest.raises(rw.ResidualWorldError, match="8 doses"):
        rw.verify_protected_book_reproduction(book, [book] * 7)


def test_adaptive_sequence_stops_at_first_null_and_never_calls_later_step():
    positive = _pricing_result(_identity("a"), (0, 0, 0, 1, 0, 0, 0), admissible=True)
    null = _pricing_result(_identity("b"), (0,) * 7, admissible=False)
    calls = []

    def price(iteration, previous):
        calls.append((iteration, previous))
        if iteration == 1:
            return positive
        if iteration == 2:
            return null
        raise AssertionError("pricing continued after its first null")

    result = rw.run_adaptive_column_sequence(price)
    assert result.columns == (positive.roster,)
    assert result.stopped_on_first_null is True
    assert result.null_iteration == 2
    assert calls == [(1, ()), (2, (positive.roster,))]


def test_adaptive_sequence_retains_all_eight_positive_columns():
    def price(iteration, previous):
        assert len(previous) == iteration - 1
        return _pricing_result(
            _identity(str(iteration)),
            (0, 0, 0, 1, 0, 0, 0),
            admissible=True,
        )

    result = rw.run_adaptive_column_sequence(price)
    assert len(result.columns) == 8
    assert len(result.steps) == 8
    assert result.stopped_on_first_null is False
    assert result.null_iteration is None


@lru_cache(maxsize=1)
def _dose_data():
    players = _players()
    rosters = _legal_rosters()
    peak_player = "BRB"
    column_player = "DTE"
    neither = tuple(
        roster for roster in rosters
        if peak_player not in roster and column_player not in roster
    )
    peak_only = tuple(
        roster for roster in rosters
        if peak_player in roster and column_player not in roster
    )
    column_only = tuple(
        roster for roster in rosters
        if peak_player not in roster and column_player in roster
    )
    both = tuple(
        roster for roster in rosters
        if peak_player in roster and column_player in roster
    )
    controls = (peak_only[0], *neither[:87])
    worlds = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    raw = np.full((len(players), len(worlds)), 20, dtype=np.float32)
    row = {player.player_id: index for index, player in enumerate(players)}
    raw[row[peak_player]] = 30
    # 70 makes generated q-only rosters score 230 and legal p+q rosters 240.
    # Keeping H=240 leaves a 240 queue after a 230 roster enters the book, so
    # the next attempted pricing solve can be a genuine null rather than a
    # terminal active-support failure.
    raw[row[column_player]] = 70
    micro = rw.to_micro_dk(raw)
    selector, control_micro = rw._cross_score_rosters(
        players, raw, micro, controls
    )
    return (
        players, worlds, raw, micro, controls,
        tuple((f"control:{index:03d}",) for index in range(len(controls))),
        selector, control_micro, neither, column_only, both,
    )


def _dummy_cbc_evidence(label: str) -> rw.CbcSolveEvidence:
    return rw.CbcSolveEvidence(
        solve_label=label,
        evidence_directory="/not-used",
        log_path="/not-used/log",
        solution_path="/not-used/sol",
        model_path="/not-used/mps",
        variable_domain_manifest_path="/not-used/variable-domain-manifest.json",
        mip_start_path=None,
        log_sha256="0" * 64,
        solution_sha256="1" * 64,
        model_sha256="2" * 64,
        mip_start_sha256=None,
        mip_start_values_sha256=None,
        mip_start_renamed_values_sha256=None,
        predecessor_assignment_sha256=None,
        mip_start_reconstructed_objective=None,
        mip_start_variable_count=0,
        mip_start_values=None,
        cbc_path="/not-used/cbc",
        cbc_sha256="3" * 64,
        cbc_version="test",
        pulp_version=rw.pulp.__version__,
        command_line="test",
        pulp_status=rw.pulp.LpStatusOptimal,
        pulp_solution_status=rw.pulp.LpSolutionOptimal,
        objective=0,
        problem_sense=rw.pulp.LpMaximize,
        enumerated_nodes=0,
        total_iterations=0,
        cpu_seconds=Decimal(0),
        wall_seconds=Decimal(0),
        max_seconds=rw.BOUND_TIME_LIMIT_SECONDS,
        warm_start=False,
        cuts=False,
        preprocess_off=False,
        random_seed=rw.CBC_RANDOM_SEED,
        random_cbc_seed=rw.CBC_RANDOM_SEED,
        threads=1,
        time_mode="elapsed",
        relative_gap=Decimal(0),
        absolute_gap=Decimal(0),
        primal_tolerance=Decimal("1e-9"),
        integer_tolerance=Decimal("1e-12"),
        variable_domain_manifest_sha256="4" * 64,
        canonical_assignment_sha256="5" * 64,
        integer_decode_affected_count=0,
        integer_decode_max_residual=Decimal(0),
        variable_domain_manifest=(("X0000000", "dummy", "binary", 0, 1),),
        integer_decode_rows=(("X0000000", "0", 0, "0"),),
    )


def test_bound_evidence_is_tuple_copied_and_source_tags_reject_strings():
    evidence = _dummy_cbc_evidence("immutable")
    lower = [evidence, evidence]
    upper = [evidence, evidence]
    roster = _legal_rosters()[0]
    bound = rw.WorldLegalBound(
        rw.WorldId("R0", 0), 1, 2, roster, roster, lower, upper
    )
    lower.clear()
    upper.clear()
    assert bound.lower_evidence == (evidence, evidence)
    assert bound.upper_evidence == (evidence, evidence)
    with pytest.raises(rw.ResidualWorldError, match="nested"):
        rw._source_tags("control:000", 1)
    with pytest.raises(rw.ResidualWorldError, match="row must be a sequence"):
        rw._source_tags(("control:000",), 1)


def _prepare_dose_fixture(monkeypatch):
    (
        players, worlds, raw, micro, controls, tags, selector,
        control_micro, neither, column_only, both,
    ) = _dose_data()
    selector_calls = []

    def first_eighty(values, entries, line, env):
        selector_calls.append((values.shape, entries, line, dict(env)))
        return list(range(80))

    monkeypatch.setattr(rw, "select_tail_entries", first_eighty)
    monkeypatch.setattr(rw, "_validate_bound_receipts", lambda *args: None)
    spec = rw._fold_spec("A")
    construction = np.asarray([
        index for index, world in enumerate(worlds)
        if world.block in spec.construction_blocks
    ], dtype=int)
    maxima = control_micro[:80, construction].max(axis=0)
    relaxed = rw.position_shape_upper_bounds_micro(
        micro[:, construction], [player.position for player in players]
    )
    selections = rw.select_block_stratified_worlds(
        tuple(worlds[index] for index in construction),
        maxima,
        relaxed,
        tuple((block, 32) for block in spec.construction_blocks),
    )
    dummy = _dummy_cbc_evidence("dummy")
    bounds = tuple(
        rw.WorldLegalBound(
            selection.world_id,
            180_000_000,
            240_000_000,
            neither[0],
            both[0],
            (dummy, dummy),
            (dummy, dummy),
        )
        for selection in selections
    )
    prepared = rw.prepare_fold_reservoir(
        "A", players, worlds, raw, controls, tags,
        selector, control_micro, bounds,
        run_context=_run_context(),
    )
    assert prepared.control_score_parity.selector_thresholds_sha256 == (
        prepared.control_score_parity.float64_thresholds_sha256
    ) == prepared.control_score_parity.micro_thresholds_sha256
    assert prepared.control_score_parity.max_raw_micro_error_hex == "0x0.0p+0"
    assert prepared.control_score_parity_sha256 == (
        prepared.control_score_parity.sha256
    )
    assert selector_calls == [((88, 30_000), 80, 194.0, {"SELECT_LSE": "0"})]
    selector_calls.clear()
    return (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, column_only, selector_calls,
    )


def _fake_pricer(roster_sequence, calls):
    sequence = iter(roster_sequence)

    def price(
        players, scores, maxima, lower, upper, *,
        control_rosters, previous_columns, solver_factory, **kwargs,
    ):
        roster = next(sequence)
        rows = {player.player_id: index for index, player in enumerate(players)}
        totals = scores[[rows[player_id] for player_id in roster]].sum(
            axis=0, dtype=np.int64
        )
        maxima_array = np.asarray(maxima, dtype=np.int64)
        indicators = tuple(tuple(int(
            int(maxima_array[world]) < threshold <= int(totals[world])
        ) for world in range(len(totals))) for threshold in rw.TAIL_THRESHOLDS_MICRO)
        counts = tuple(sum(values) for values in indicators)
        residuals = np.maximum(totals - maxima_array, 0).astype(np.int64)
        gain = sum(int(value) for value in residuals)
        cuts = rw.complete_no_good_rosters(control_rosters, previous_columns)
        rank = {
            player_id: index + 1
            for index, player_id in enumerate(sorted(rows))
        }
        calls.append((tuple(control_rosters), tuple(previous_columns), maxima_array.copy()))
        return rw.PricingResult(
            roster=roster,
            scores_micro=tuple(int(value) for value in totals),
            marginal_threshold_counts=counts,
            residuals_micro=tuple(int(value) for value in residuals),
            residual_gain_micro=gain,
            objective_vector=(*counts, gain),
            indicators_by_threshold=indicators,
            rank_sum=sum(rank[player_id] for player_id in roster),
            rank_sum_ambiguous=False,
            admissible=any(counts),
            sequential_optima=(*counts, gain),
            ambiguity_distance=0,
            rank_first_roster=roster,
            pricing_input_sha256=rw._pricing_input_sha256(
                players,
                scores,
                maxima_array,
                np.asarray(lower, dtype=np.int64),
                np.asarray(upper, dtype=np.int64),
                rw.TAIL_THRESHOLDS_MICRO,
                cuts,
            ),
            no_good_rosters=cuts,
            solve_evidence=(),
        )

    return price


@pytest.mark.parametrize(
    ("mode", "expected_columns", "expected_null", "expected_calls"),
    (
        ("null", 0, 1, 9),
        ("two_then_null", 2, 3, 11),
        ("all_eight", 8, None, 17),
        ("falling", 1, 2, 10),
    ),
)
def test_hardwired_fold_dose_state_machine_and_complete_coupling(
    monkeypatch, tmp_path, mode, expected_columns, expected_null, expected_calls,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, column_only, selector_calls,
    ) = _prepare_dose_fixture(monkeypatch)
    treatment_calls = 0
    selector_outputs: dict[str, tuple[int, ...]] = {}

    def scripted_selector(values, entries, line, env):
        nonlocal treatment_calls
        selector_calls.append((values.shape, entries, line, dict(env)))
        assert values.dtype == np.float32
        assert values.shape[1] == 30_000
        key = rw._array_sha256(values)
        if key in selector_outputs:
            return list(selector_outputs[key])
        if len(selector_calls) > 9:
            treatment_calls += 1
            if mode == "two_then_null" and treatment_calls == 2:
                selected = (*range(79), 87)
                selector_outputs[key] = selected
                return list(selected)
            if mode == "falling" and treatment_calls == 1:
                selected = tuple(range(1, 81))
                selector_outputs[key] = selected
                return list(selected)
        selected = tuple(range(80))
        selector_outputs[key] = selected
        return list(selected)

    monkeypatch.setattr(rw, "select_tail_entries", scripted_selector)
    monkeypatch.setattr(
        rw, "_audit_pricing_evidence_semantics", lambda *args: None
    )
    if mode == "null":
        sequence = (neither[87],)
    elif mode == "two_then_null":
        sequence = (*column_only[:3],)
    elif mode == "all_eight":
        sequence = column_only[:8]
    else:
        sequence = (column_only[0], neither[87])
    pricing_calls = []
    monkeypatch.setattr(rw, "solve_residual_pricing", _fake_pricer(
        sequence, pricing_calls
    ))
    result = rw.run_fold_doses(
        prepared,
        players,
        worlds,
        raw,
        controls,
        tags,
        selector,
        control_micro,
        evidence_root=tmp_path / f"evidence-{mode}",
    )
    assert len(result.generated_columns) == expected_columns
    assert result.null_iteration == expected_null
    assert result.stopped_on_first_null is (expected_null is not None)
    assert result.selector_call_count == expected_calls
    assert len(pricing_calls) == expected_columns + int(expected_null is not None)
    assert [len(previous) for _, previous, _ in pricing_calls] == list(
        range(len(pricing_calls))
    )
    assert all(control == controls for control, _, _ in pricing_calls)
    for index, step in enumerate(result.steps):
        assert step.complete_no_goods == (
            *controls, *result.generated_columns[:index]
        )
        assert len(step.active_selections) == 66
    assert result.generated_selector_totals.shape == (
        expected_columns, 50_000
    )
    assert result.generated_micro_totals.shape == (expected_columns, 50_000)
    assert result.generated_selector_totals.dtype == np.float32
    assert result.generated_micro_totals.dtype == np.int64
    assert not result.generated_selector_totals.flags.writeable
    assert not result.treatment_selector_totals.flags.writeable
    assert rw.fold_dose_scientific_payload(result)["prepared_fold_sha256"] == (
        rw.prepared_fold_sha256(prepared)
    )
    if mode == "falling":
        assert set(pricing_calls[0][2]) == {190_000_000}
        assert set(pricing_calls[1][2]) == {180_000_000}


def test_active_world_selection_is_independently_rejected_when_poisoned(
    monkeypatch, tmp_path,
):
    (
        prepared, players, worlds, raw, controls, tags, selector,
        control_micro, neither, _, _,
    ) = _prepare_dose_fixture(monkeypatch)
    original = rw.select_block_stratified_worlds

    def poisoned(*args, **kwargs):
        result = original(*args, **kwargs)
        quotas = args[3]
        if quotas and quotas[0][1] == 22:
            return (*result[:-1], result[0])
        return result

    monkeypatch.setattr(rw, "select_block_stratified_worlds", poisoned)
    monkeypatch.setattr(
        rw, "solve_residual_pricing", _fake_pricer((neither[87],), [])
    )
    with pytest.raises(rw.ResidualWorldError, match="independent deterministic"):
        rw.run_fold_doses(
            prepared, players, worlds, raw, controls, tags,
            selector, control_micro,
            evidence_root=tmp_path / "poisoned-active",
        )
