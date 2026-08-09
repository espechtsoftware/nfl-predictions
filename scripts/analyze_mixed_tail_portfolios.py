"""Score a preregistered 80-entry allocation across K=1 and K=3 books.

Each model selects against its own immutable simulated-world support. The
realized weekly maximum is then scored across the fixed union; actual outcomes
never affect portfolio membership. See the protocol in
reports/2026-08-08-80-entry-tail-audit.md.

Example after the K=3 source is promoted and K=1 remains in staging:
  python scripts/analyze_mixed_tail_portfolios.py K1_PANEL K3_PANEL
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.research.tail_portfolio import (  # noqa: E402
    combine_slate_portfolios,
    evaluate_portfolio,
    portfolio_summary,
    season_summary,
)

ALLOCATIONS = ((0, 80), (20, 60), (40, 40), (60, 20), (80, 0))
SELECT_LINE = 194.0


def _panel_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid panel id {value!r}")
    return value


def _load(panel: str, staging: bool) -> pd.DataFrame:
    table = "replay_candidates_staging" if staging else "replay_candidates"
    eligibility = "" if staging else "AND research_eligible"
    return query_df(f"""
        SELECT season, week, cand_ix, tag, players, selected, p_line,
               sim_mean, sim_q99, actual_score, n_worlds,
               clear_bits_187, clear_bits_194, clear_bits_200
        FROM `{settings.predictions}.{table}`
        WHERE panel_run_id = '{_panel_id(panel)}' {eligibility}
        """)


def _fmt(report: dict, k1: int, k3: int, duplicate_report: dict) -> str:
    tail = " | ".join(
        f">={line} {report[f'ge_{line}']}"
        for line in (187, 194, 200, 210, 220, 230, 240))
    return (
        f"K1/K3={k1}/{k3} | {tail} | "
        f"mean-max {report['mean_weekly_max']:.2f} | "
        f"oracle>=200 {report['oracle_ge_200']} | "
        f"cross-book duplicates {duplicate_report['total']} "
        f"({duplicate_report['slates']} slates; max "
        f"{duplicate_report['max_per_slate']})"
    )


def _selected_rosters(candidates: pd.DataFrame,
                      membership: pd.DataFrame) -> pd.DataFrame:
    keys = ["season", "week", "cand_ix"]
    joined = candidates[keys + ["players"]].merge(
        membership, on=keys, validate="one_to_one")
    return joined.loc[joined.portfolio_selected,
                      ["season", "week", "players"]]


def _duplicates(k1_candidates: pd.DataFrame, k1_membership: pd.DataFrame | None,
                k3_candidates: pd.DataFrame, k3_membership: pd.DataFrame | None
                ) -> dict:
    if k1_membership is None or k3_membership is None:
        return {"total": 0, "slates": 0, "max_per_slate": 0,
                "by_slate": pd.DataFrame()}
    left = _selected_rosters(k1_candidates, k1_membership)
    right = _selected_rosters(k3_candidates, k3_membership)
    overlap = left.merge(
        right, on=["season", "week", "players"], validate="one_to_one")
    if overlap.empty:
        by_slate = pd.DataFrame(columns=["season", "week", "duplicates"])
    else:
        by_slate = overlap.groupby(["season", "week"]).size().rename(
            "duplicates").reset_index()
    return {
        "total": int(len(overlap)),
        "slates": int(len(by_slate)),
        "max_per_slate": int(by_slate.duplicates.max())
        if len(by_slate) else 0,
        "by_slate": by_slate,
    }


def _verify_persisted(candidates: pd.DataFrame,
                      membership: pd.DataFrame, label: str) -> None:
    keys = ["season", "week", "cand_ix"]
    joined = candidates[keys + ["selected"]].merge(
        membership, on=keys, validate="one_to_one")
    mismatches = int(
        (joined.selected != joined.portfolio_selected).sum())
    print(f"{label} 80-entry production-selection mismatches: {mismatches}")
    if mismatches:
        raise ValueError(f"{label} frozen selector does not reproduce production")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("k1_panel")
    ap.add_argument("k3_panel")
    ap.add_argument("--k1-promoted", action="store_true",
                    help="read K=1 from the promoted table instead of staging")
    ap.add_argument("--k3-staging", action="store_true",
                    help="read K=3 from staging instead of the promoted table")
    args = ap.parse_args()

    k1 = _load(args.k1_panel, staging=not args.k1_promoted)
    k3 = _load(args.k3_panel, staging=args.k3_staging)
    if k1.empty or k3.empty:
        print("one or both candidate panels are empty", file=sys.stderr)
        return 1
    print(f"K1={args.k1_panel}: {len(k1):,} candidates; "
          f"K3={args.k3_panel}: {len(k3):,} candidates")

    counts = sorted({n for allocation in ALLOCATIONS for n in allocation if n})
    evaluated: dict[str, dict[int, tuple[pd.DataFrame, pd.DataFrame]]] = {
        "k1": {}, "k3": {}}
    for label, candidates in (("k1", k1), ("k3", k3)):
        for entries in counts:
            evaluated[label][entries] = evaluate_portfolio(
                candidates, entry_count=entries, select_line=SELECT_LINE)
    _verify_persisted(k1, evaluated["k1"][80][1], "K=1")
    _verify_persisted(k3, evaluated["k3"][80][1], "K=3")

    mixed: dict[tuple[int, int], pd.DataFrame] = {}
    summaries: dict[tuple[int, int], dict] = {}
    duplicates: dict[tuple[int, int], dict] = {}
    print("\nPREREGISTERED K1/K3 ALLOCATION GRID")
    for k1_entries, k3_entries in ALLOCATIONS:
        k1_slates, k1_members = (evaluated["k1"][k1_entries]
                                  if k1_entries else (pd.DataFrame(), None))
        k3_slates, k3_members = (evaluated["k3"][k3_entries]
                                  if k3_entries else (pd.DataFrame(), None))
        slates = combine_slate_portfolios(
            k1_slates, k3_slates, k1_entries, k3_entries)
        duplicate_report = _duplicates(
            k1, k1_members, k3, k3_members)
        report = portfolio_summary(slates)
        mixed[(k1_entries, k3_entries)] = slates
        summaries[(k1_entries, k3_entries)] = report
        duplicates[(k1_entries, k3_entries)] = duplicate_report
        print(_fmt(report, k1_entries, k3_entries, duplicate_report))

    # The stronger endpoint is defined on the primary >=200 objective, with
    # >=210, >=194, and mean weekly maximum as frozen tiebreakers.
    endpoints = ((0, 80), (80, 0))
    incumbent = max(endpoints, key=lambda allocation: (
        summaries[allocation]["ge_200"], summaries[allocation]["ge_210"],
        summaries[allocation]["ge_194"],
        summaries[allocation]["mean_weekly_max"]))
    primary = (40, 40)
    incumbent_report = summaries[incumbent]
    primary_report = summaries[primary]

    inc_season = season_summary(mixed[incumbent], thresholds=(194.0, 200.0))
    mix_season = season_summary(mixed[primary], thresholds=(194.0, 200.0))
    seasons = inc_season.merge(
        mix_season, on=["season", "slates"], suffixes=("_inc", "_mix"),
        validate="one_to_one")
    seasons["delta_ge_200"] = seasons.ge_200_mix - seasons.ge_200_inc
    positive = int(seasons.delta_ge_200.gt(0).sum())
    negative = int(seasons.delta_ge_200.lt(0).sum())

    checks = {
        "aggregate_ge_200_lift_at_least_2":
            primary_report["ge_200"] - incumbent_report["ge_200"] >= 2,
        "positive_seasons_at_least_4": positive >= 4,
        "negative_seasons_at_most_1": negative <= 1,
        "aggregate_ge_194_not_worse":
            primary_report["ge_194"] >= incumbent_report["ge_194"],
        "aggregate_ge_210_not_worse":
            primary_report["ge_210"] >= incumbent_report["ge_210"],
        "pool_oracle_ge_200_not_worse":
            primary_report["oracle_ge_200"]
            >= incumbent_report["oracle_ge_200"],
        "mean_weekly_max_regression_at_most_2":
            primary_report["mean_weekly_max"]
            >= incumbent_report["mean_weekly_max"] - 2.0,
    }

    print(f"\nPRIMARY 40/40 GATE VS STRONGER ENDPOINT K1/K3="
          f"{incumbent[0]}/{incumbent[1]}")
    print(seasons[["season", "ge_194_inc", "ge_194_mix", "ge_200_inc",
                   "ge_200_mix", "delta_ge_200"]].to_string(index=False))
    for name, passed in checks.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    print(f"VERDICT: {'PASS' if all(checks.values()) else 'FAIL'}")

    dup = duplicates[primary]["by_slate"]
    if len(dup):
        print("\n40/40 CROSS-BOOK DUPLICATES BY SLATE")
        print(dup.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
