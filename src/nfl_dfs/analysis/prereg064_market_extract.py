"""Build the PREREG-064 bookmaker market extract at the common DFS lock.

The transformation is deliberately dataframe-only. The executable wrapper
owns BigQuery reads and immutable publication; keeping the scientific
transformation here makes the strict-lock, name-resolution, and price-pairing
contracts testable without cloud access.
"""

from __future__ import annotations

from datetime import time
from typing import Any

import numpy as np
import pandas as pd

from nfl_dfs.models.blend import (
    american_to_prob,
    devig_two_way,
    prop_line_to_mean,
)
from nfl_dfs.models.prop_market import latest_pre_main_lock
from nfl_dfs.names import initial_key, match_map, norm_name, resolve


SCHEMA_VERSION = "prereg064_common_lock_market_extract_v1"
CONVERSION_LAW_VERSION = "prop_market_common_lock_v1"
STANDARD_MARKETS = frozenset(
    {
        "player_pass_yds",
        "player_pass_tds",
        "player_rush_yds",
        "player_reception_yds",
        "player_receptions",
        "player_anytime_td",
    }
)
ALT_MARKETS = frozenset(
    {
        "player_pass_yds_alternate",
        "player_rush_yds_alternate",
        "player_reception_yds_alternate",
        "player_receptions_alternate",
    }
)
SUPPORTED_MARKETS = STANDARD_MARKETS | ALT_MARKETS

ACTUAL_COLUMN = {
    "player_pass_yds": "y_pass_yards",
    "player_pass_tds": "y_pass_tds",
    "player_rush_yds": "y_rush_yards",
    "player_reception_yds": "y_rec_yards",
    "player_receptions": "y_receptions",
    "player_pass_yds_alternate": "y_pass_yards",
    "player_rush_yds_alternate": "y_rush_yards",
    "player_reception_yds_alternate": "y_rec_yards",
    "player_receptions_alternate": "y_receptions",
}


def common_main_locks(schedules: pd.DataFrame) -> pd.DataFrame:
    """Return the earliest domestic Sunday-main kickoff by season/week."""

    needed = {
        "season", "week", "gameday", "gametime", "game_type", "weekday",
    }
    if missing := needed - set(schedules.columns):
        raise ValueError(f"schedules missing {sorted(missing)}")
    slate = schedules[
        schedules.game_type.eq("REG") & schedules.weekday.eq("Sunday")
    ].copy()
    parsed_time = pd.to_datetime(
        slate.gametime.astype(str), format="%H:%M", errors="coerce",
    ).dt.time
    main = parsed_time.map(
        lambda value: (
            value is not pd.NaT
            and pd.notna(value)
            and time(13, 0) <= value < time(19, 0)
        )
    )
    slate = slate[main].copy()
    local = pd.to_datetime(
        slate.gameday.astype(str) + " " + slate.gametime.astype(str),
        errors="coerce",
    ).dt.tz_localize(
        "America/New_York", ambiguous="NaT", nonexistent="shift_forward",
    ).dt.tz_convert("UTC")
    slate["common_lock_utc"] = local
    return (
        slate.dropna(subset="common_lock_utc")
        .groupby(["season", "week"], observed=True).common_lock_utc.min()
        .reset_index()
        .sort_values(["season", "week"], kind="stable")
        .reset_index(drop=True)
    )


def _resolve_props_to_slate(
    props: pd.DataFrame,
    snapshot: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    needed = {"season", "week", "player"}
    if missing := needed - set(props.columns):
        raise ValueError(f"props missing {sorted(missing)}")
    snapshot_needed = {"season", "week", "name", "gsis_id"}
    if missing := snapshot_needed - set(snapshot.columns):
        raise ValueError(f"snapshot missing {sorted(missing)}")

    resolved_parts: list[pd.DataFrame] = []
    match_counts = {"exact": 0, "initial": 0, "unmapped": 0}
    for (season, week), lines in props.groupby(
        ["season", "week"], observed=True, sort=True,
    ):
        candidates = snapshot[
            snapshot.season.eq(season) & snapshot.week.eq(week)
        ][["name", "gsis_id"]].dropna().drop_duplicates()
        reference = dict(zip(candidates.name.astype(str), candidates.gsis_id))
        lookup = match_map(reference)
        exact_keys = {norm_name(name) for name in reference}
        part = lines.copy()
        part["gsis_id"] = part.player.map(lambda value: resolve(value, lookup))

        def method(value: object, gsis_id: object) -> str:
            if pd.isna(gsis_id):
                return "unmapped"
            if norm_name(str(value)) in exact_keys:
                return "exact"
            if initial_key(str(value)) in lookup:
                return "initial"
            return "unmapped"

        part["identity_resolution_method"] = [
            method(name, gsis_id)
            for name, gsis_id in zip(part.player, part.gsis_id)
        ]
        counts = part.identity_resolution_method.value_counts()
        for key in match_counts:
            match_counts[key] += int(counts.get(key, 0))
        resolved_parts.append(part)
    resolved = (
        pd.concat(resolved_parts, ignore_index=True)
        if resolved_parts else props.assign(
            gsis_id=pd.Series(dtype="object"),
            identity_resolution_method=pd.Series(dtype="object"),
        )
    )
    audit = {
        "prop_rows_after_common_lock": int(len(resolved)),
        "mapped_prop_rows": int(resolved.gsis_id.notna().sum()),
        "unmapped_prop_rows": int(resolved.gsis_id.isna().sum()),
        "mapping_method_rows": match_counts,
        "distinct_source_names": int(resolved.player.nunique()),
        "distinct_unmapped_source_names": int(
            resolved.loc[resolved.gsis_id.isna(), "player"].nunique()
        ),
    }
    return resolved, audit


def _pair_prices(lines: pd.DataFrame) -> pd.DataFrame:
    """Collapse outcome-side rows to one bookmaker/player/market/line row."""

    index = [
        "season", "week", "slate_id", "common_lock_utc", "gsis_id",
        "identity_resolution_method", "player", "bookmaker", "market",
        "point", "event_id", "commence_time", "home_team", "away_team",
    ]
    frame = lines.copy()
    # Pandas groupby/pivot drops null keys; anytime TD has no point.
    frame["_point_key"] = pd.to_numeric(frame.point, errors="coerce").fillna(
        -9_999_999.0
    )
    index[index.index("point")] = "_point_key"
    sides = frame[index].drop_duplicates().copy()
    for outcome, prefix in (("Over", "over"), ("Under", "under"), ("Yes", "yes")):
        values = (
            frame[frame.outcome_name.eq(outcome)]
            .groupby(index, observed=True, dropna=False)[["price", "snapshot_ts"]]
            .first()
            .rename(columns={
                "price": f"{prefix}_price",
                "snapshot_ts": f"{prefix}_snapshot_ts",
            })
            .reset_index()
        )
        sides = sides.merge(values, on=index, how="left", validate="one_to_one")
    sides = sides.rename(columns={"_point_key": "line"})
    for column in (
        "over_price", "under_price", "yes_price", "over_snapshot_ts",
        "under_snapshot_ts", "yes_snapshot_ts",
    ):
        if column not in sides:
            sides[column] = np.nan if column.endswith("price") else pd.NaT
    sides["line"] = sides.line.mask(sides.line.eq(-9_999_999.0))
    for column in ("over_snapshot_ts", "under_snapshot_ts", "yes_snapshot_ts"):
        sides[column] = pd.to_datetime(sides[column], utc=True, errors="coerce")
    sides["snapshot_ts"] = sides[
        ["over_snapshot_ts", "under_snapshot_ts", "yes_snapshot_ts"]
    ].max(axis=1)
    sides["over_price"] = sides.over_price.where(
        sides.over_price.notna(), sides.yes_price,
    )
    sides["snapshot_horizon"] = "latest_pre_common_lock"
    sides["hours_before_common_lock"] = (
        sides.common_lock_utc - sides.snapshot_ts
    ).dt.total_seconds() / 3600.0
    sides["alt_ladder_flag"] = sides.market.isin(ALT_MARKETS)
    return sides.drop(columns=["yes_price"])


def _add_derived_forecasts(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["devig_over_probability"] = np.nan
    result["forecast_stat_mean"] = np.nan
    result["forecast_dk_component_points"] = np.nan
    for idx, row in result.iterrows():
        if row.market == "player_anytime_td":
            if pd.isna(row.over_price):
                continue
            p = float(np.clip(american_to_prob(row.over_price) / 1.15, 0.01, 0.95))
            mean = float(-np.log1p(-p))
            result.at[idx, "devig_over_probability"] = p
            result.at[idx, "forecast_stat_mean"] = mean
            result.at[idx, "forecast_dk_component_points"] = 6.0 * mean
            continue
        if pd.isna(row.line) or pd.isna(row.over_price) or pd.isna(row.under_price):
            continue
        p_over, _ = devig_two_way(
            american_to_prob(row.over_price), american_to_prob(row.under_price),
        )
        distribution = (
            "poisson"
            if row.market in {"player_receptions", "player_pass_tds"}
            else "normal"
        )
        try:
            mean = float(prop_line_to_mean(float(row.line), p_over, distribution))
        except (TypeError, ValueError):
            continue
        points_per_unit = {
            "player_pass_yds": 0.04,
            "player_rush_yds": 0.1,
            "player_reception_yds": 0.1,
            "player_receptions": 1.0,
            "player_pass_tds": 4.0,
        }.get(str(row.market).replace("_alternate", ""), np.nan)
        result.at[idx, "devig_over_probability"] = float(p_over)
        result.at[idx, "forecast_stat_mean"] = mean
        result.at[idx, "forecast_dk_component_points"] = mean * points_per_unit
    result["conversion_law_version"] = CONVERSION_LAW_VERSION
    return result


def build_market_extract(
    props: pd.DataFrame,
    schedules: pd.DataFrame,
    snapshot: pd.DataFrame,
    actuals: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Create the outcome-bearing 092 market table and an audit receipt."""

    props = props[props.market.isin(SUPPORTED_MARKETS)].copy()
    prelock, cutoff_audit = latest_pre_main_lock(props, schedules)
    locks = common_main_locks(schedules)
    prelock = prelock.merge(
        locks, on=["season", "week"], how="inner", validate="many_to_one",
    )
    prelock["snapshot_ts"] = pd.to_datetime(
        prelock.snapshot_ts, utc=True, errors="coerce",
    )
    if not prelock.snapshot_ts.lt(prelock.common_lock_utc).all():
        raise ValueError("common-lock extract contains a non-prelock row")
    prelock["slate_id"] = prelock.apply(
        lambda row: f"{int(row.season)}-w{int(row.week):02d}-dk-sunday-main",
        axis=1,
    )
    resolved, mapping_audit = _resolve_props_to_slate(prelock, snapshot)
    mapped = resolved[resolved.gsis_id.notna()].copy()
    paired = _add_derived_forecasts(_pair_prices(mapped))

    snap_columns = {
        "name": "player_name",
        "pos": "position",
        "opp": "opponent",
        "actual": "actual_dk_points",
        "mean_projection": "incumbent_projection",
        "market_points": "incumbent_market_points",
    }
    snap_needed = {
        "season", "week", "gsis_id", "name", "pos", "team", "opp",
        "game_id", "salary", "actual", "mean_projection",
        "model_points_pre", "market_points",
    }
    if missing := snap_needed - set(snapshot.columns):
        raise ValueError(f"snapshot missing {sorted(missing)}")
    # DST rows intentionally share a synthetic gsis_id; player props never
    # target DST and the contract is player-grain.
    meta = snapshot[snapshot.pos.ne("DST")][list(snap_needed)].rename(
        columns=snap_columns
    )
    if meta.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("snapshot player-week keys are not unique")
    paired = paired.merge(
        meta,
        on=["season", "week", "gsis_id"],
        how="inner",
        validate="many_to_one",
    )

    actual_columns = [
        "season", "week", "gsis_id", "was_active", "y_targets",
        "y_receptions", "y_rec_yards", "y_rec_tds", "y_carries",
        "y_rush_yards", "y_rush_tds", "y_pass_attempts", "y_pass_yards",
        "y_pass_tds", "y_interceptions", "y_dk_points",
    ]
    if missing := set(actual_columns) - set(actuals.columns):
        raise ValueError(f"actuals missing {sorted(missing)}")
    labels = actuals[actual_columns].copy()
    if labels.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("actual player-week keys are not unique")
    paired = paired.merge(
        labels,
        on=["season", "week", "gsis_id"],
        how="left",
        validate="many_to_one",
    )
    paired["actual_market_value"] = np.nan
    for market, column in ACTUAL_COLUMN.items():
        use = paired.market.eq(market)
        paired.loc[use, "actual_market_value"] = paired.loc[use, column]
    anytime = paired.market.eq("player_anytime_td")
    paired.loc[anytime, "actual_market_value"] = (
        paired.loc[anytime, "y_rec_tds"].fillna(0)
        + paired.loc[anytime, "y_rush_tds"].fillna(0)
    )
    paired["schema_version"] = SCHEMA_VERSION
    paired["contains_realized_outcomes"] = True

    sort_columns = [
        "season", "week", "gsis_id", "bookmaker", "market", "line",
        "snapshot_ts",
    ]
    paired = paired.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    if not paired.snapshot_ts.lt(paired.common_lock_utc).all():
        raise ValueError("paired extract contains a non-prelock row")
    delta = (
        pd.to_numeric(paired.actual_dk_points, errors="coerce")
        - pd.to_numeric(paired.y_dk_points, errors="coerce")
    ).abs()
    audit = {
        "schema_version": SCHEMA_VERSION,
        "cutoff": cutoff_audit,
        "mapping": mapping_audit,
        "output_rows": int(len(paired)),
        "seasons": sorted(int(value) for value in paired.season.unique()),
        "slates": int(paired[["season", "week"]].drop_duplicates().shape[0]),
        "players": int(paired.gsis_id.nunique()),
        "player_weeks": int(
            paired[["season", "week", "gsis_id"]].drop_duplicates().shape[0]
        ),
        "bookmakers": sorted(paired.bookmaker.dropna().astype(str).unique()),
        "markets": sorted(paired.market.dropna().astype(str).unique()),
        "alternate_ladder_rows": int(paired.alt_ladder_flag.sum()),
        "strictly_prelock": bool(
            paired.snapshot_ts.lt(paired.common_lock_utc).all()
        ),
        "actual_dk_points_vs_training": {
            "compared_rows": int(delta.notna().sum()),
            "different_rows_gt_1e_8": int(delta.gt(1e-8).sum()),
            "max_absolute_difference": (
                float(delta.max()) if delta.notna().any() else None
            ),
        },
    }
    return paired, audit
