"""Point-in-time leakage assertions.

The #1 way DFS backtests lie is a rolling feature that includes the current
week. These checks recompute key rolling features from the source tables
using strictly-prior weeks and assert they match what the build produced.
Any mismatch means a window definition regressed — fail the build.

`trailing_mean_excluding_current` is the pure-pandas reference
implementation; it is unit-tested on synthetic data and reused by the
SQL-vs-reference comparison.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class LeakageError(AssertionError):
    """A feature saw data from its own week or later."""


def trailing_mean_excluding_current(
    df: pd.DataFrame,
    value_col: str,
    window: int | None = None,
    group_cols: tuple[str, ...] = ("gsis_id", "season"),
    order_col: str = "week",
) -> pd.Series:
    """Reference rolling mean over the trailing `window` rows (all prior rows
    when window is None), strictly excluding the current row. Mirrors the SQL
    `ROWS BETWEEN n PRECEDING AND 1 PRECEDING` window."""
    df = df.sort_values(list(group_cols) + [order_col])

    def _roll(s: pd.Series) -> pd.Series:
        shifted = s.shift(1)
        if window is None:
            return shifted.expanding().mean()
        return shifted.rolling(window, min_periods=1).mean()

    return df.groupby(list(group_cols), sort=False)[value_col].transform(_roll)


def assert_no_leakage(
    built: pd.DataFrame,
    source: pd.DataFrame,
    feature_col: str,
    source_col: str,
    window: int | None,
    atol: float = 1e-6,
    min_coverage: float = 0.95,
) -> None:
    """Compare a built rolling feature against the reference recomputation.

    `built` needs [gsis_id, season, week, feature_col]; `source` needs
    [gsis_id, season, week, source_col] at per-game grain.
    """
    ref = source[["gsis_id", "season", "week", source_col]].copy()
    ref["expected"] = trailing_mean_excluding_current(ref, source_col, window=window)
    merged = built.merge(ref[["gsis_id", "season", "week", "expected"]],
                         on=["gsis_id", "season", "week"], how="inner")
    if merged.empty:
        raise LeakageError(f"No overlapping rows to check for {feature_col}")

    both = merged.dropna(subset=[feature_col, "expected"])
    n_checked = len(both)
    if n_checked == 0:
        raise LeakageError(f"{feature_col}: no non-null rows to compare")
    mismatch = ~np.isclose(both[feature_col], both["expected"], atol=atol)
    rate = 1 - mismatch.mean()
    if rate < min_coverage:
        bad = both[mismatch].head(5)[["gsis_id", "season", "week", feature_col, "expected"]]
        raise LeakageError(
            f"{feature_col}: only {rate:.1%} of {n_checked} rows match the "
            f"point-in-time reference (need >= {min_coverage:.0%}). "
            f"A rolling window is probably including the current week.\n"
            f"Examples:\n{bad.to_string(index=False)}"
        )
    log.info("%s: %d rows checked, %.2f%% match", feature_col, n_checked, 100 * rate)


def assert_first_game_features_null(built: pd.DataFrame, feature_cols: list[str]) -> None:
    """A player's first tracked game has no prior data: every rolling feature
    must be null there. A value means the window saw the current week."""
    first = built[built["games_played_prior"] == 0]
    for col in feature_cols:
        if col not in first.columns:
            continue
        leaked = first[first[col].notna()]
        if not leaked.empty:
            raise LeakageError(
                f"{col} is non-null on {len(leaked)} first-game rows; "
                f"rolling window includes the current week."
            )


# SQL-side checks used in production against BigQuery ------------------------

CHECKED_FEATURES = [
    # (built feature col, source table, source col, window)
    ("target_share_l4", "rz_receiving", "target_share", 4),
    ("rz20_targets_l4", "rz_receiving", "rz20_targets", 4),
    ("carry_share_l4", "rz_rushing", "carry_share", 4),
    ("target_share_std", "rz_receiving", "target_share", None),
]

SAMPLE_SQL = """
SELECT gsis_id, season, week, {cols}
FROM `{table}`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0  -- deterministic 5% player sample
"""


def run_leakage_checks() -> None:
    from ..bq import query_df
    from ..config import settings

    built_cols = sorted({f for f, *_ in CHECKED_FEATURES} | {"games_played_prior"})
    built = query_df(
        SAMPLE_SQL.format(cols=", ".join(built_cols),
                          table=f"{settings.features}.player_week_usage")
    )
    for feature_col, source_table, source_col, window in CHECKED_FEATURES:
        source = query_df(
            SAMPLE_SQL.format(cols=source_col,
                              table=f"{settings.features}.{source_table}")
        )
        assert_no_leakage(built, source, feature_col, source_col, window)
    assert_first_game_features_null(built, [f for f, *_ in CHECKED_FEATURES])

    # Training-table sanity: labels exist, features don't correlate perfectly
    # with same-week labels (a 1.0 correlation is a copied column).
    tr = query_df(
        f"""SELECT target_share_l4, y_targets, dk_points_l4, y_dk_points
            FROM `{settings.features}.player_week_training`
            WHERE RAND() < 0.05"""
    )
    for feat, label in (("target_share_l4", "y_targets"), ("dk_points_l4", "y_dk_points")):
        sub = tr[[feat, label]].dropna()
        if len(sub) > 100 and abs(sub[feat].corr(sub[label])) > 0.98:
            raise LeakageError(f"{feat} correlates {sub[feat].corr(sub[label]):.3f} "
                               f"with same-week {label}; that's a leak, not a feature.")
    log.info("All leakage checks passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_leakage_checks()
