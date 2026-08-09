"""Analyze 40/80-entry frozen portfolios and high scores left unselected.

Examples:
  python scripts/analyze_tail_portfolios.py PANEL
  python scripts/analyze_tail_portfolios.py PANEL --staging

The script prints a full, predeclared grid: entry counts 40/80 and selection
lines 187/194/200. It does not pick whichever objective happened to win.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.tail_portfolio import (  # noqa: E402
    evaluate_portfolio,
    evaluate_hybrid_portfolio,
    evaluate_ranked_portfolio,
    high_unselected_candidates,
    missed_oracles,
    portfolio_summary,
    refine_one_swap,
    season_summary,
    select_slate,
    swap_frontier,
)


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _load(panel: str, staging: bool) -> pd.DataFrame:
    table = "replay_candidates_staging" if staging else "replay_candidates"
    eligibility = "" if staging else "AND research_eligible"
    return query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, players, selected,
               selected_rank, salary, p_line, sim_mean, sim_sd, sim_q50,
               sim_q90, sim_q99, sim_rank_p_line, actual_score, actual_rank,
               n_worlds, clear_bits_187, clear_bits_194, clear_bits_200
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _load_features(panel: str, staging: bool) -> pd.DataFrame:
    eligibility = "" if staging else "AND research_eligible"
    return query_df(f"""
        SELECT season, week, id, name, pos, team, salary, actual, proj,
               mean_projection, model_points_pre, market_points
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _fmt_summary(report: dict) -> str:
    fields = [
        f"N={report['entry_count']}",
        f"select={report['select_line']:g}",
        *(f">={line} {report[f'ge_{line}']}" for line in
          (187, 194, 200, 210, 220, 230, 240)),
        f"mean-max {report['mean_weekly_max']:.2f}",
        f"q90 {report['q90_weekly_max']:.2f}",
        f"regret {report['mean_regret']:.2f}",
    ]
    return " | ".join(fields)


def _print_misses(rows: pd.DataFrame, threshold: float) -> None:
    if rows.empty:
        print("  none")
        return
    columns = [
        "season", "week", "selected_best", "oracle", "regret",
        "oracle_tag", "oracle_p_line_rank", "oracle_sim_mean_rank",
        "oracle_sim_q99_rank", "oracle_clear_worlds",
        "oracle_new_worlds_after_portfolio",
        "best_oracle_swap_coverage_delta", "nonnegative_oracle_swaps",
        "roster_overlap", "closest_selected_support_jaccard",
        "closest_selected_roster_overlap", "selected_support_superset_count",
        "n_candidates",
    ]
    print(rows[columns].to_string(index=False, float_format=lambda x: f"{x:.2f}"))


def _print_roster_contrasts(misses: pd.DataFrame, candidates: pd.DataFrame,
                            features: pd.DataFrame) -> None:
    """Explain which realized player swaps created each missed winner."""
    if misses.empty:
        print("  none")
        return
    candidate_lookup = candidates.set_index(["season", "week", "cand_ix"])
    feature_lookup = {
        (int(season), int(week)): group.drop_duplicates("id").set_index("id")
        for (season, week), group in features.groupby(["season", "week"])
    }
    for miss in misses.itertuples(index=False):
        key = (int(miss.season), int(miss.week))
        oracle = candidate_lookup.loc[
            (*key, int(miss.oracle_cand_ix))]
        selected = candidate_lookup.loc[
            (*key, int(miss.selected_best_cand_ix))]
        oracle_ids = set(str(oracle.players).split(","))
        selected_ids = set(str(selected.players).split(","))
        frame = feature_lookup[key]
        details = []
        for side, ids in (("oracle_only", oracle_ids - selected_ids),
                          ("selected_only", selected_ids - oracle_ids)):
            for player_id in ids:
                player = frame.loc[player_id]
                expected = (player.proj if str(player.pos).upper() == "DST"
                            else player.mean_projection)
                details.append({
                    "side": side,
                    "id": player_id,
                    "name": player.get("name", player_id),
                    "pos": player.pos,
                    "team": player.team,
                    "salary": int(player.salary),
                    "expected": float(expected),
                    "actual": float(player.actual),
                    "surprise": float(player.actual - expected),
                })
        detail = pd.DataFrame(details).sort_values(
            ["side", "actual"], ascending=[True, False])
        slate_candidates = candidates[
            candidates.season.eq(key[0]) & candidates.week.eq(key[1])]
        ordered, support, picked = select_slate(
            slate_candidates, int(miss.entry_count), float(miss.select_line))
        best_delta, free_swaps = swap_frontier(support, picked)
        oracle_pos = int(np.flatnonzero(
            ordered.cand_ix.to_numpy() == int(miss.oracle_cand_ix))[0])
        selected_mask = np.zeros(len(ordered), dtype=bool)
        selected_mask[picked] = True
        free_mask = (best_delta >= 0) & ~selected_mask
        free_candidates = int(np.count_nonzero(free_mask))
        selected_support = support[picked]
        world_counts = selected_support.sum(axis=0)
        unique_worlds = (
            selected_support & (world_counts == 1)).sum(axis=1)
        zero_unique = int(np.count_nonzero(unique_worlds == 0))

        def frontier_rank(column: str) -> int:
            values = pd.to_numeric(ordered[column], errors="coerce").to_numpy()
            target = values[oracle_pos]
            return int(np.count_nonzero(values[free_mask] > target)) + 1

        actual_values = ordered.actual_score.to_numpy(dtype=float)
        frontier_high = int(np.count_nonzero(
            free_mask & (actual_values >= 200.0)))
        print(f"  {key[0]} week {key[1]}: selected {miss.selected_best:.2f}, "
              f"oracle {miss.oracle:.2f}, overlap {miss.roster_overlap}/9")
        print(f"    closest simulated substitute cand="
              f"{int(miss.closest_selected_cand_ix)} scored "
              f"{miss.closest_selected_actual:.2f}; support Jaccard="
              f"{miss.closest_selected_support_jaccard:.3f}, roster overlap="
              f"{int(miss.closest_selected_roster_overlap)}/9; selected "
              f"support supersets={int(miss.selected_support_superset_count)}")
        print(f"    oracle best swap delta={best_delta[oracle_pos]:+d}; "
              f"non-worsening drops={free_swaps[oracle_pos]}; "
              f"all unselected candidates with a free swap="
              f"{free_candidates}/{int((~selected_mask).sum())}")
        print(f"    final selected book covers {int((world_counts > 0).sum())}/"
              f"{support.shape[1]} worlds; {zero_unique}/{len(picked)} "
              f"selected entries own zero unique worlds")
        if free_mask[oracle_pos]:
            print(f"    oracle rank inside {free_candidates}-candidate free "
                  f"frontier: p_line {frontier_rank('p_line')}, "
                  f"mean {frontier_rank('sim_mean')}, "
                  f"q99 {frontier_rank('sim_q99')}; "
                  f"realized >=200 candidates on frontier={frontier_high}")
        refined, refinement_trace = refine_one_swap(
            support,
            ordered.p_line.to_numpy(dtype=float),
            ordered.sim_mean.to_numpy(dtype=float),
            picked,
        )
        refined_coverage = int(np.any(support[refined], axis=0).sum())
        refined_best = float(ordered.actual_score.iloc[refined].max())
        print(f"    pre-lock lexicographic one-swap refinement: "
              f"{len(refinement_trace)} swaps, coverage "
              f"{int((world_counts > 0).sum())}->{refined_coverage}, "
              f"oracle selected={oracle_pos in set(refined.tolist())}, "
              f"realized best={refined_best:.2f}")
        print(detail.to_string(
            index=False, float_format=lambda x: f"{x:.2f}"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("panel_run_id")
    ap.add_argument("--staging", action="store_true")
    ap.add_argument("--entry-counts", nargs="+", type=int, default=[40, 80])
    ap.add_argument("--select-lines", nargs="+", type=float,
                    default=[187.0, 194.0, 200.0])
    ap.add_argument("--top-unselected", type=int, default=20)
    ap.add_argument(
        "--top-unselected-oracles", type=int, default=20,
        help="show weekly pool maxima omitted from the submitted book")
    ap.add_argument(
        "--ranked-diagnostics", action="store_true",
        help="compare coverage selection with top marginal-ranking books")
    args = ap.parse_args()

    candidates = _load(args.panel_run_id, args.staging)
    if candidates.empty:
        print(f"no candidate rows for {args.panel_run_id}", file=sys.stderr)
        return 1
    slates = candidates.groupby(["season", "week"]).ngroups
    print(f"panel={args.panel_run_id} staging={args.staging} "
          f"candidates={len(candidates):,} slates={slates}")
    features: pd.DataFrame | None = None

    results: dict[tuple[int, float], tuple[pd.DataFrame, pd.DataFrame]] = {}
    print("\nFULL FROZEN GRID")
    for entries in args.entry_counts:
        for line in args.select_lines:
            slate_rows, membership = evaluate_portfolio(
                candidates, entry_count=entries, select_line=line)
            results[(entries, line)] = (slate_rows, membership)
            print(_fmt_summary(portfolio_summary(slate_rows)))

    # Prove the frozen analysis reproduces the panel's persisted portfolio at
    # its actual entry count before interpreting counterfactual sizes. Older
    # panels persisted 40; the production-faithful experiment persists 80.
    persisted_counts = candidates.groupby(
        ["season", "week"]).selected.sum().unique()
    if len(persisted_counts) != 1:
        print("panel has inconsistent persisted entry counts", file=sys.stderr)
        return 2
    persisted_entries = int(persisted_counts[0])
    if (persisted_entries, 194.0) in results:
        _, membership = results[(persisted_entries, 194.0)]
        persisted = candidates[["season", "week", "cand_ix", "selected"]]
        joined = persisted.merge(
            membership, on=["season", "week", "cand_ix"],
            validate="one_to_one")
        mismatches = int(
            (joined.selected != joined.portfolio_selected).sum())
        print(f"\n{persisted_entries}-entry production-selection "
              f"mismatches: {mismatches}")
        if mismatches:
            return 2

    for entries in args.entry_counts:
        key = (entries, 194.0)
        if key not in results:
            continue
        slate_rows, membership = results[key]
        print(f"\nN={entries}, SELECT=194 — BY SEASON")
        print(season_summary(slate_rows).to_string(
            index=False, float_format=lambda x: f"{x:.2f}"))
        unselected_oracles = slate_rows[~slate_rows.oracle_selected].sort_values(
            ["regret", "oracle"], ascending=False)
        print(f"\nN={entries} UNSELECTED WEEKLY POOL MAXIMA")
        if unselected_oracles.empty:
            print("  none")
        else:
            oracle_200 = unselected_oracles.oracle.ge(200)
            selected_200 = unselected_oracles.selected_best.ge(200)
            free_swap = unselected_oracles[
                "best_oracle_swap_coverage_delta"].ge(0)
            print(
                f"{len(unselected_oracles)}/{len(slate_rows)} weekly pool "
                f"maxima unselected; median regret "
                f"{unselected_oracles.regret.median():.2f}; "
                f"max regret {unselected_oracles.regret.max():.2f}; "
                f"oracle >=200 in "
                f"{int(oracle_200.sum())} weeks, "
                f"including {int((oracle_200 & selected_200).sum())} "
                f"where the selected book already cleared 200; "
                f"non-worsening one-swap exists for "
                f"{int(free_swap.sum())}/{len(unselected_oracles)} oracles "
                f"and {int((free_swap & oracle_200).sum())}/"
                f"{int(oracle_200.sum())} scoring >=200")
            oracle_columns = [
                "season", "week", "selected_best", "oracle", "regret",
                "oracle_tag", "oracle_p_line_rank", "oracle_sim_mean_rank",
                "oracle_sim_q99_rank", "best_oracle_swap_coverage_delta",
                "roster_overlap",
            ]
            if args.top_unselected_oracles:
                print(unselected_oracles[oracle_columns].head(
                    args.top_unselected_oracles).to_string(
                        index=False, float_format=lambda x: f"{x:.2f}"))
        for threshold in (194.0, 200.0):
            print(f"\nN={entries} RECOVERABLE >={threshold:g} WEEKS")
            _print_misses(missed_oracles(slate_rows, threshold), threshold)

        print(f"\nN={entries} TOP REALIZED >=200 CANDIDATES NOT SELECTED")
        high = high_unselected_candidates(
            candidates, membership, threshold=200.0)
        columns = [
            "season", "week", "cand_ix", "actual_score", "tag", "salary",
            "p_line", "p_line_rank", "sim_mean", "sim_mean_rank",
            "sim_q99", "sim_q99_rank", "players",
        ]
        if high.empty:
            print("  none")
        else:
            if args.top_unselected:
                print(high[columns].head(args.top_unselected).to_string(
                    index=False, float_format=lambda x: f"{x:.3f}"))
            print(f"unselected >=200 candidates: {len(high)} across "
                  f"{high.groupby(['season', 'week']).ngroups} slates")
            high = high.merge(
                slate_rows[["season", "week", "selected_best"]],
                on=["season", "week"], validate="many_to_one")
            high["consequential"] = high.selected_best < 200.0
            print("by generator (candidates / slates / consequential):")
            by_tag = high.groupby("tag").apply(
                lambda g: pd.Series({
                    "candidates": len(g),
                    "slates": g.groupby(["season", "week"]).ngroups,
                    "consequential": int(g.consequential.sum()),
                    "median_p_line_rank": float(g.p_line_rank.median()),
                }), include_groups=False).reset_index()
            print(by_tag.to_string(
                index=False, float_format=lambda x: f"{x:.1f}"))

        misses_200 = missed_oracles(slate_rows, 200.0)
        print(f"\nN={entries} MISSED >=200 ROSTER CONTRASTS")
        if not misses_200.empty and features is None:
            features = _load_features(args.panel_run_id, args.staging)
        _print_roster_contrasts(
            misses_200, candidates,
            features if features is not None else pd.DataFrame())

        if args.ranked_diagnostics:
            print(f"\nN={entries} OUTCOME-BLIND RANKED-BOOK DIAGNOSTICS")
            coverage_slates, _ = results[(entries, 194.0)]
            coverage_misses = missed_oracles(coverage_slates, 200.0)
            oracle_keys = set(zip(
                coverage_misses.season.astype(int),
                coverage_misses.week.astype(int),
                coverage_misses.oracle_cand_ix.astype(int)))
            for rank_column in ("p_line", "sim_mean", "sim_q99"):
                ranked_slates, ranked_membership = evaluate_ranked_portfolio(
                    candidates, entries, rank_column)
                summary = portfolio_summary(ranked_slates)
                print(f"top-{rank_column}: {_fmt_summary(summary)}")
                membership_lookup = ranked_membership.set_index(
                    ["season", "week", "cand_ix"]).portfolio_selected
                recovered = sorted(
                    (season, week) for season, week, cand_ix in oracle_keys
                    if bool(membership_lookup.loc[(season, week, cand_ix)]))
                print(f"  production >=200 misses included: "
                      f"{len(recovered)}/{len(oracle_keys)} {recovered}")
                for coverage_entries in (
                        entries, 3 * entries // 4, entries // 2,
                        entries // 4):
                    ranked_entries = entries - coverage_entries
                    if not ranked_entries:
                        continue
                    hybrid_slates, hybrid_membership = (
                        evaluate_hybrid_portfolio(
                            candidates, coverage_entries, ranked_entries,
                            rank_column))
                    hybrid_summary = portfolio_summary(hybrid_slates)
                    hybrid_lookup = hybrid_membership.set_index(
                        ["season", "week", "cand_ix"]).portfolio_selected
                    hybrid_recovered = sorted(
                        (season, week)
                        for season, week, cand_ix in oracle_keys
                        if bool(hybrid_lookup.loc[
                            (season, week, cand_ix)]))
                    print(
                        f"  coverage/rank {coverage_entries}/"
                        f"{ranked_entries}: {_fmt_summary(hybrid_summary)}; "
                        f"misses {len(hybrid_recovered)}/"
                        f"{len(oracle_keys)} {hybrid_recovered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
