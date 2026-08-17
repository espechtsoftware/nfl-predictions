"""Outcome-viewed correction and characterization of the forensic P-C gap.

The frozen repair4 forensic run accidentally solved H/P with QB+1 and no
bring-back while the candidate generator used QB+2 plus one bring-back.  This
module never changes or promotes a historical policy.  It recomputes the
descriptive bounds under the actual production construction contract and
characterizes how the corrected P roster differs from the generated pool.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .final_forensic import (
    TAILS,
    _solve_oracle,
    audit_roster,
    canonical_game_id,
    decompose_slate,
    recourse_ceiling_slate,
)


PROTOCOL_ID = "20260815-post-forensic-exact-stack-construction-v1"
SCOPE = "phase-s-cbwu-54"
QB_STACK_MIN = 2
BRING_BACK_MIN = 1


def _require(frame: pd.DataFrame, required: set[str], label: str) -> None:
    if missing := required - set(frame.columns):
        raise ValueError(f"{label} lacks columns {sorted(missing)}")


def _roster(value: object) -> tuple[str, ...]:
    players = tuple(item for item in str(value).split(",") if item)
    if len(players) != 9 or len(set(players)) != 9:
        raise ValueError("construction addendum encountered a malformed roster")
    return players


def _summary(values: Sequence[float]) -> dict[str, float | int | None]:
    array = np.asarray(list(values), dtype=float)
    finite = array[np.isfinite(array)]
    if not len(finite):
        return {"n": 0, "mean": None, "median": None, "minimum": None,
                "maximum": None}
    return {
        "n": int(len(finite)),
        "mean": float(finite.mean()),
        "median": float(np.median(finite)),
        "minimum": float(finite.min()),
        "maximum": float(finite.max()),
    }


def _shape(players: pd.DataFrame, roster: Sequence[str]) -> dict[str, float]:
    by_id = players.set_index("id", drop=False)
    chosen = by_id.loc[list(map(str, roster))]
    qbs = chosen[chosen.pos.eq("QB")]
    if len(qbs) != 1:
        raise ValueError("construction shape requires one quarterback")
    qb = qbs.iloc[0]
    games = [
        canonical_game_id(team, opponent)
        for team, opponent in zip(chosen.team, chosen.opp, strict=True)
    ]
    out: dict[str, float] = {
        "salary": float(chosen.salary.sum()),
        "distinct_games": float(len(set(games))),
        "largest_team_block": float(chosen.team.value_counts().max()),
        "qb_stack_size": float((
            chosen.team.eq(str(qb.team))
            & chosen.pos.isin(("WR", "TE"))
        ).sum()),
        "bring_back_count": float((
            chosen.team.eq(str(qb.opp))
            & chosen.pos.isin(("RB", "WR", "TE"))
        ).sum()),
    }
    for position in ("QB", "RB", "WR", "TE", "DST"):
        out[f"{position.lower()}_salary"] = float(
            chosen.loc[chosen.pos.eq(position), "salary"].sum()
        )
    if "actual_ownership" in chosen:
        ownership = pd.to_numeric(chosen.actual_ownership, errors="coerce")
        out["actual_ownership_sum"] = (
            float(ownership.sum()) if ownership.notna().all() else np.nan
        )
    return out


def _standard_player_slate(rows: pd.DataFrame) -> pd.DataFrame:
    frame = rows.copy()
    frame["id"] = frame.id.astype(str)
    frame["pos"] = frame.pos.astype(str).str.upper().replace({"DEF": "DST"})
    frame["team"] = frame.team.astype(str)
    frame["opp"] = frame.opp.astype(str)
    frame["salary"] = pd.to_numeric(frame.salary, errors="raise").astype(int)
    frame["actual"] = pd.to_numeric(frame.actual, errors="raise").astype(float)
    return frame


def analyze_exact_stack_construction(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    published_oracles: pd.DataFrame,
    *,
    expected_slates: int = 54,
    expected_entries: int = 80,
) -> dict[str, Any]:
    """Recompute exact production H/P and characterize the corrected gap.

    Inputs must be the immutable repair4 warehouse projection of the CBWU
    scope.  Historical outcomes are used, so every output is descriptive and
    prospective-hypothesis-only.
    """
    key = {"season", "week"}
    _require(
        players,
        key | {"id", "pos", "team", "opp", "game_id", "salary", "actual"},
        "construction players",
    )
    _require(
        candidates,
        key | {"players", "actual_score", "selected", "selected_rank"},
        "construction candidates",
    )
    _require(
        published_oracles,
        key | {"layer", "players", "actual_score"},
        "published oracles",
    )
    player_keys = set(map(tuple, players[["season", "week"]].astype(int).drop_duplicates().to_numpy()))
    candidate_keys = set(map(tuple, candidates[["season", "week"]].astype(int).drop_duplicates().to_numpy()))
    oracle_keys = set(map(tuple, published_oracles[["season", "week"]].astype(int).drop_duplicates().to_numpy()))
    if player_keys != candidate_keys or player_keys != oracle_keys:
        raise ValueError("construction addendum slate populations differ")
    if len(player_keys) != int(expected_slates):
        raise ValueError(
            f"construction addendum has {len(player_keys)} slates; "
            f"expected {int(expected_slates)}"
        )

    records: list[dict[str, Any]] = []
    for season, week in sorted(player_keys):
        pframe = _standard_player_slate(players[
            players.season.eq(season) & players.week.eq(week)
        ].copy())
        cframe = candidates[
            candidates.season.eq(season) & candidates.week.eq(week)
        ].copy().sort_values("candidate_index" if "candidate_index" in candidates else "players",
                            kind="stable")
        oframe = published_oracles[
            published_oracles.season.eq(season)
            & published_oracles.week.eq(week)
        ].copy()
        if set(oframe.layer.astype(str)) != {
            "H_no_salary_floor", "H", "P", "C", "S"
        }:
            raise ValueError("published oracle layer set differs")
        exact = decompose_slate(
            pframe,
            cframe,
            expected_entries=expected_entries,
            min_salary=49_000,
            qb_stack_min=QB_STACK_MIN,
            bring_back_min=BRING_BACK_MIN,
        )
        support_counts = Counter(
            player for value in cframe.players for player in _roster(value)
        )
        support = set(support_counts)
        published = {
            str(row.layer): row for row in oframe.itertuples(index=False)
        }
        old_p_ids = _roster(published["P"].players)
        old_p_audit = audit_roster(
            pframe,
            old_p_ids,
            min_salary=49_000,
            qb_stack_min=QB_STACK_MIN,
            bring_back_min=BRING_BACK_MIN,
        )
        loose = _solve_oracle(
            pframe,
            support,
            min_salary=49_000,
            qb_stack_min=1,
            bring_back_min=0,
        )
        if (
            not np.isclose(
                loose["actual_score"], float(published["P"].actual_score),
                rtol=0.0, atol=1e-6,
            )
            or set(loose["players"]) != set(old_p_ids)
        ):
            raise ValueError("published loose P oracle does not reproduce")
        qb2_only = _solve_oracle(
            pframe, support, min_salary=49_000,
            qb_stack_min=2, bring_back_min=0,
        )
        bringback_only = _solve_oracle(
            pframe, support, min_salary=49_000,
            qb_stack_min=1, bring_back_min=1,
        )
        exact_p_ids = tuple(map(str, exact["P"]["players"]))
        candidate_rosters = [_roster(value) for value in cframe.players]
        overlaps = np.asarray([
            len(set(exact_p_ids) & set(roster)) for roster in candidate_rosters
        ], dtype=int)
        closest_overlap = int(overlaps.max())
        closest_indices = np.flatnonzero(overlaps == closest_overlap)
        closest = cframe.iloc[int(closest_indices[0])]
        pshape = _shape(pframe, exact_p_ids)
        candidate_shapes = pd.DataFrame([
            _shape(pframe, roster) for roster in candidate_rosters
        ])
        shape_contrast = {}
        for field, value in pshape.items():
            pool_values = pd.to_numeric(candidate_shapes[field], errors="coerce")
            finite = pool_values[np.isfinite(pool_values)]
            shape_contrast[field] = {
                "p_oracle": float(value) if np.isfinite(value) else None,
                "candidate_mean": float(finite.mean()) if len(finite) else None,
                "candidate_median": float(finite.median()) if len(finite) else None,
                "p_within_pool_percentile": (
                    float((finite <= value).mean())
                    if len(finite) and np.isfinite(value) else None
                ),
            }
        appearances = [int(support_counts[player]) for player in exact_p_ids]
        recourse = recourse_ceiling_slate(
            pframe,
            cframe,
            expected_entries=expected_entries,
            compute_liveness=False,
            qb_stack_min=QB_STACK_MIN,
            bring_back_min=BRING_BACK_MIN,
        )
        if recourse["status"] != "computed_perfect_information_upper_bound":
            raise ValueError("corrected recourse ceiling is not identifiable")
        selected = cframe[
            cframe.selected.fillna(False).astype(bool)
        ].copy()
        selected["_roster"] = selected.players.map(_roster)
        selected["_key"] = selected._roster.map(lambda ids: ",".join(sorted(ids)))
        srow = selected.sort_values(
            ["actual_score", "_key"],
            ascending=[False, True],
            kind="stable",
        ).iloc[0]
        source_rank = int(recourse["source_selected_rank"])
        source_row = selected[
            pd.to_numeric(selected.selected_rank, errors="raise").astype(int).eq(
                source_rank
            )
        ]
        if len(source_row) != 1:
            raise ValueError("corrected recourse source rank does not resolve")
        source_ids = tuple(source_row.iloc[0]._roster)
        final_ids = tuple(map(str, recourse["final_roster"]["players"]))

        def distance(left: Sequence[str], right: Sequence[str]) -> int:
            return int(9 - len(set(left) & set(right)))

        record = {
            "season": int(season),
            "week": int(week),
            "published_loose_p": float(loose["actual_score"]),
            "exact_h_dk_legal": float(
                exact["H_DK_legal"]["actual_score"]
            ),
            "exact_h_strategy": float(exact["H_strategy"]["actual_score"]),
            "exact_h_no_salary_floor": float(
                exact["H_no_salary_floor"]["actual_score"]
            ),
            "exact_h": float(exact["H"]["actual_score"]),
            "exact_p": float(exact["P"]["actual_score"]),
            "c": float(exact["C"]["actual_score"]),
            "s": float(exact["S"]["actual_score"]),
            "gaps": dict(exact["gaps"]),
            "dk_legal_strategy": {
                "dk_legal_roster": list(exact["H_DK_legal"]["players"]),
                "strategy_roster": list(exact["H_strategy"]["players"]),
                "roster_changed": bool(
                    exact["H_DK_legal"]["players"]
                    != exact["H_strategy"]["players"]
                ),
                "realized_score_cost": float(
                    exact["strategy_gaps"]["combined_strategy_constraints"]
                ),
                "non_salary_strategy_constraints_cost": float(
                    exact["strategy_gaps"][
                        "non_salary_strategy_constraints"
                    ]
                ),
                "salary_floor_cost": float(
                    exact["strategy_gaps"]["salary_floor"]
                ),
            },
            "published_p_violates_qb2": any(
                "same-team WR/TE" in failure for failure in old_p_audit["failures"]
            ),
            "published_p_violates_bring_back": any(
                "opponent bring-backs" in failure for failure in old_p_audit["failures"]
            ),
            "constraint_scores": {
                "qb1_bringback0": float(loose["actual_score"]),
                "qb2_bringback0": float(qb2_only["actual_score"]),
                "qb1_bringback1": float(bringback_only["actual_score"]),
                "qb2_bringback1": float(exact["P"]["actual_score"]),
            },
            "minimum_swaps_to_p": int(9 - closest_overlap),
            "closest_candidate_count": int(len(closest_indices)),
            "closest_candidate_score": float(closest.actual_score),
            "p_player_appearances": appearances,
            "p_players_appearing_fewer_than_five": int(sum(
                value < 5 for value in appearances
            )),
            "corrected_recourse": {
                "incumbent_selected_best": float(
                    recourse["incumbent_selected_best"]
                ),
                "perfect_information_ceiling": float(
                    recourse["perfect_information_recourse_ceiling"]
                ),
                "ceiling_gain": float(recourse["ceiling_gain"]),
                "source_selected_rank": source_rank,
                "source_roster": sorted(source_ids),
                "final_roster": sorted(final_ids),
                "p_distance_from_selected_best": distance(
                    exact_p_ids, tuple(srow._roster)
                ),
                "p_distance_from_recourse_source": distance(
                    exact_p_ids, source_ids
                ),
                "p_distance_from_recourse_final": distance(
                    exact_p_ids, final_ids
                ),
            },
            "shape_contrast": shape_contrast,
            "salary_floor_realized_score_cost": float(
                exact["salary_floor_policy"]["realized_score_cost"]
            ),
            "salary_floor_newly_reached_thresholds": list(
                exact["salary_floor_policy"]["newly_reached_thresholds"]
            ),
            "thresholds": exact["thresholds"],
        }
        records.append(record)

    layers = (
        "exact_h_dk_legal", "exact_h_no_salary_floor",
        "exact_h_strategy", "exact_h", "exact_p", "c", "s",
    )
    tail_counts = {
        layer: {
            str(tail): int(sum(record[layer] >= tail for record in records))
            for tail in TAILS
        }
        for layer in layers
    }
    published_p_tail = {
        str(tail): int(sum(record["published_loose_p"] >= tail for record in records))
        for tail in TAILS
    }
    first_failed = {
        str(tail): dict(Counter(
            record["thresholds"][str(tail)]["first_failed_layer"]
            for record in records
        ))
        for tail in TAILS
    }
    first_failed_extended = {
        str(tail): dict(Counter(
            record["thresholds"][str(tail)]["first_failed_layer_extended"]
            for record in records
        ))
        for tail in TAILS
    }
    constraint_names = (
        "qb1_bringback0", "qb2_bringback0",
        "qb1_bringback1", "qb2_bringback1",
    )
    constraint_scores = {
        name: _summary(record["constraint_scores"][name] for record in records)
        for name in constraint_names
    }
    constraint_tail_counts = {
        name: {
            str(tail): int(sum(
                record["constraint_scores"][name] >= tail for record in records
            ))
            for tail in TAILS
        }
        for name in constraint_names
    }
    shape_fields = tuple(records[0]["shape_contrast"])
    shape_summary = {
        field: {
            "p_oracle": _summary(
                record["shape_contrast"][field]["p_oracle"]
                for record in records
                if record["shape_contrast"][field]["p_oracle"] is not None
            ),
            "candidate_slate_mean": _summary(
                record["shape_contrast"][field]["candidate_mean"]
                for record in records
                if record["shape_contrast"][field]["candidate_mean"] is not None
            ),
            "p_within_pool_percentile": _summary(
                record["shape_contrast"][field]["p_within_pool_percentile"]
                for record in records
                if record["shape_contrast"][field]["p_within_pool_percentile"] is not None
            ),
        }
        for field in shape_fields
    }
    recourse_rows = [record["corrected_recourse"] for record in records]
    recourse_summary = {
        "incumbent_selected_best": _summary(
            row["incumbent_selected_best"] for row in recourse_rows
        ),
        "perfect_information_ceiling": _summary(
            row["perfect_information_ceiling"] for row in recourse_rows
        ),
        "ceiling_gain": _summary(row["ceiling_gain"] for row in recourse_rows),
        "improved_slates": int(sum(row["ceiling_gain"] > 1e-6 for row in recourse_rows)),
        "tail_counts": {
            "incumbent": {
                str(tail): int(sum(
                    row["incumbent_selected_best"] >= tail
                    for row in recourse_rows
                ))
                for tail in TAILS
            },
            "perfect_information": {
                str(tail): int(sum(
                    row["perfect_information_ceiling"] >= tail
                    for row in recourse_rows
                ))
                for tail in TAILS
            },
            "newly_reached": {
                str(tail): int(sum(
                    row["incumbent_selected_best"] < tail
                    <= row["perfect_information_ceiling"]
                    for row in recourse_rows
                ))
                for tail in TAILS
            },
        },
        "p_distance": {
            "selected_best": _summary(
                row["p_distance_from_selected_best"] for row in recourse_rows
            ),
            "recourse_source": _summary(
                row["p_distance_from_recourse_source"] for row in recourse_rows
            ),
            "recourse_final": _summary(
                row["p_distance_from_recourse_final"] for row in recourse_rows
            ),
            "final_closer_than_source_slates": int(sum(
                row["p_distance_from_recourse_final"]
                < row["p_distance_from_recourse_source"]
                for row in recourse_rows
            )),
            "final_closer_than_selected_best_slates": int(sum(
                row["p_distance_from_recourse_final"]
                < row["p_distance_from_selected_best"]
                for row in recourse_rows
            )),
        },
        "warning": (
            "This still uses realized late outcomes and is a descriptive upper "
            "bound, not an executable policy estimate."
        ),
    }
    return {
        "protocol_id": PROTOCOL_ID,
        "scope": SCOPE,
        "uses_realized_outcomes": True,
        "use_restriction": (
            "Descriptive correction and prospective hypothesis generation only; "
            "not a historical arm, adoption scorecard or production promotion."
        ),
        "production_stack_contract": {
            "qb_stack_min": QB_STACK_MIN,
            "bring_back_min": BRING_BACK_MIN,
        },
        "expected_entries": int(expected_entries),
        "slates": len(records),
        "published_scope_defect": {
            "published_qb_stack_min": 1,
            "published_bring_back_min": 0,
            "p_violates_qb2": int(sum(
                record["published_p_violates_qb2"] for record in records
            )),
            "p_violates_bring_back": int(sum(
                record["published_p_violates_bring_back"] for record in records
            )),
            "p_violates_either": int(sum(
                record["published_p_violates_qb2"]
                or record["published_p_violates_bring_back"]
                for record in records
            )),
        },
        "corrected_gap_points": {
            "player_support": _summary(record["gaps"]["player_support"] for record in records),
            "construction": _summary(record["gaps"]["construction"] for record in records),
            "selection": _summary(record["gaps"]["selection"] for record in records),
        },
        "dk_legal_strategy_decomposition": {
            "core_layer_order": [
                "H_DK_legal", "H_strategy", "P", "C", "S",
            ],
            "strategy_attribution_order": [
                "H_DK_legal", "H_no_salary_floor", "H_strategy",
            ],
            "legacy_alias": {"H": "H_strategy"},
            "realized_score_cost": _summary(
                record["dk_legal_strategy"]["realized_score_cost"]
                for record in records
            ),
            "non_salary_strategy_constraints_cost": _summary(
                record["dk_legal_strategy"][
                    "non_salary_strategy_constraints_cost"
                ]
                for record in records
            ),
            "salary_floor_cost": _summary(
                record["dk_legal_strategy"]["salary_floor_cost"]
                for record in records
            ),
            "changed_roster_slates": int(sum(
                record["dk_legal_strategy"]["roster_changed"]
                for record in records
            )),
            "tail_counts": {
                "H_DK_legal": tail_counts["exact_h_dk_legal"],
                "H_strategy": tail_counts["exact_h_strategy"],
            },
            "first_failed_layer_counts": first_failed_extended,
            "draftkings_legality": {
                "minimum_salary": 0,
                "maximum_salary": 50_000,
                "maximum_players_per_team": 8,
                "minimum_games": 2,
                "qb_stack_min": 0,
                "bring_back_min": 0,
                "forbid_two_rb_same_team": False,
                "forbid_rb_vs_dst": False,
            },
            "use_restriction": (
                "Outcome-viewed hindsight description only. The gap cannot "
                "promote a strategy relaxation or alter H/P/C/S verdicts."
            ),
        },
        "corrected_salary_floor_policy": {
            "realized_score_cost": _summary(
                record["salary_floor_realized_score_cost"]
                for record in records
            ),
            "positive_cost_slates": int(sum(
                record["salary_floor_realized_score_cost"] > 1e-6
                for record in records
            )),
            "newly_reached_threshold_slates": {
                str(tail): int(sum(
                    tail in record["salary_floor_newly_reached_thresholds"]
                    for record in records
                ))
                for tail in TAILS
            },
        },
        "tail_counts": tail_counts,
        "published_loose_p_tail_counts": published_p_tail,
        "corrected_first_failed_layer_counts": first_failed,
        "extended_first_failed_layer_counts": first_failed_extended,
        "constraint_attribution": {
            "score_summaries": constraint_scores,
            "tail_counts": constraint_tail_counts,
            "warning": (
                "Constraint cells are outcome-viewed oracles; differences size "
                "the forensic definition error and cannot promote stack changes."
            ),
        },
        "swap_distance": {
            "minimum_player_swaps_to_exact_p": _summary(
                record["minimum_swaps_to_p"] for record in records
            ),
            "slates_by_swaps": dict(sorted(Counter(
                record["minimum_swaps_to_p"] for record in records
            ).items())),
            "closest_candidate_score": _summary(
                record["closest_candidate_score"] for record in records
            ),
        },
        "p_player_representation": {
            "appearance_count": _summary(
                value for record in records for value in record["p_player_appearances"]
            ),
            "players_in_p": int(sum(len(record["p_player_appearances"]) for record in records)),
            "players_in_p_appearing_fewer_than_five_candidates": int(sum(
                record["p_players_appearing_fewer_than_five"] for record in records
            )),
        },
        "structural_contrast": shape_summary,
        "corrected_perfect_information_recourse": recourse_summary,
        "records": records,
    }


__all__ = [
    "BRING_BACK_MIN",
    "PROTOCOL_ID",
    "QB_STACK_MIN",
    "SCOPE",
    "analyze_exact_stack_construction",
]
