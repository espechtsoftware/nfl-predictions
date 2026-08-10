"""Frozen alternate-prop tail-disagreement mechanism diagnostic.

This module is deliberately diagnostic-only.  It never mutates model
features, candidates, or production policy.  A passing report licenses the
single candidate-union experiment preregistered in
reports/2026-08-10-market-tail-disagreement-experiment.md.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import numpy as np
import pandas as pd

from ..inference.market_implied import ALT_MARKETS, market_quantiles
from ..names import norm_name

PANEL_ID = "20260809-e80-k1-ce12-c616390"
SEASONS = (2024, 2025)
TRAIN_SEASON = 2024
TEST_SEASON = 2025

PRIMARY_MARKET = {
    "QB": "player_pass_yds_alternate",
    "RB": "player_rush_yds_alternate",
    "WR": "player_reception_yds_alternate",
    "TE": "player_reception_yds_alternate",
}
CONTROL_NUMERIC = (
    "mean_projection",
    "salary",
    "production_upside",
)
TREATMENT_NUMERIC = CONTROL_NUMERIC + ("tail_edge",)


def component_points(position: object, yards: object) -> np.ndarray:
    """Convert a primary yardage component to its monotone DK score."""

    pos = np.asarray(position, dtype=str)
    value = np.asarray(yards, dtype=float)
    passing = pos == "QB"
    rate = np.where(passing, 0.04, 0.10)
    bonus_line = np.where(passing, 300.0, 100.0)
    return rate * value + 3.0 * (value >= bonus_line)


def _normalized_feature_ids(features: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    frame = features.copy()
    frame["norm"] = frame["name"].map(
        lambda value: norm_name(value) if pd.notna(value) else ""
    )
    frame = frame[frame.norm.ne("")].copy()
    identity = frame.groupby(
        ["season", "week", "norm"], observed=True,
    ).gsis_id.nunique()
    ambiguous = identity[identity.gt(1)].reset_index()[
        ["season", "week", "norm"]
    ]
    if not ambiguous.empty:
        frame = frame.merge(
            ambiguous.assign(_ambiguous=True),
            on=["season", "week", "norm"], how="left",
        )
        frame = frame[frame._ambiguous.isna()].drop(columns="_ambiguous")
    return frame, int(len(ambiguous))


def attach_market_tail_edges(
    features: pd.DataFrame,
    props: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Attach frozen common-lock primary-market disagreement features."""

    f_needed = {
        "season", "week", "gsis_id", "name", "pos", "salary",
        "mean_projection", "proj_p50", "proj_p90",
    }
    p_needed = {
        "season", "week", "event_id", "commence_time", "snapshot_ts",
        "market", "player", "point", "outcome_name", "price",
    }
    if missing := f_needed - set(features.columns):
        raise ValueError(f"features missing {sorted(missing)}")
    if missing := p_needed - set(props.columns):
        raise ValueError(f"props missing {sorted(missing)}")

    frame, ambiguous_count = _normalized_feature_ids(features)
    if frame.empty:
        raise ValueError("no unambiguous feature identities")
    if frame.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("feature rows are not unique by player/slate")

    lines = props.copy()
    lines = lines[
        lines.market.isin(ALT_MARKETS)
        & lines.point.notna()
        & lines.price.notna()
    ].copy()
    lines["norm"] = lines.player.map(
        lambda value: norm_name(value) if pd.notna(value) else ""
    )
    lines["snapshot"] = pd.to_datetime(
        lines.snapshot_ts, utc=True, errors="coerce",
    )
    lines["commence"] = pd.to_datetime(
        lines.commence_time, utc=True, errors="coerce",
    )
    lines = lines[
        lines.norm.ne("") & lines.snapshot.notna() & lines.commence.notna()
    ].copy()

    valid_ids = frame[["season", "week", "norm"]].drop_duplicates()
    matched = lines.merge(
        valid_ids, on=["season", "week", "norm"], how="inner",
        validate="many_to_one",
    )
    if matched.empty:
        raise ValueError("no alternate props match the accepted snapshots")
    cutoffs = matched.groupby(
        ["season", "week"], observed=True,
    ).commence.min().rename("common_slate_lock").reset_index()
    matched = matched.merge(
        cutoffs, on=["season", "week"], how="inner",
        validate="many_to_one",
    )
    matched = matched[matched.snapshot.lt(matched.common_slate_lock)].copy()
    if matched.empty:
        raise ValueError("no matched alternate props precede common slate lock")
    matched = matched.sort_values(
        ["season", "week", "market", "norm", "point", "outcome_name",
         "snapshot"], kind="stable",
    ).drop_duplicates(
        ["season", "week", "market", "norm", "point", "outcome_name"],
        keep="last",
    )

    ladder_input = matched[
        ["season", "week", "market", "norm", "point", "outcome_name",
         "price"]
    ].rename(columns={"norm": "player"})
    quantiles = market_quantiles(ladder_input)
    if quantiles.empty:
        raise ValueError("no valid three-point alternate ladders")
    quantiles = quantiles.rename(columns={"player": "norm"})

    frame["market"] = frame.pos.map(PRIMARY_MARKET)
    out = frame.merge(
        quantiles,
        on=["season", "week", "market", "norm"],
        how="left", validate="one_to_one",
    )
    out["production_upside"] = (
        pd.to_numeric(out.proj_p90, errors="coerce")
        - pd.to_numeric(out.proj_p50, errors="coerce")
    ).clip(lower=0.0)
    out["market_upside"] = (
        component_points(out.pos, out.q90)
        - component_points(out.pos, out.q50)
    )
    out["raw_tail_edge"] = out.production_upside - out.market_upside
    covered = out.raw_tail_edge.notna()
    centers = out.loc[covered].groupby(
        ["season", "week", "pos"], observed=True,
    ).raw_tail_edge.transform("median")
    out["tail_edge"] = np.nan
    out.loc[covered, "tail_edge"] = out.loc[
        covered, "raw_tail_edge"
    ] - centers

    season_rows: list[dict] = []
    for season in SEASONS:
        season_frame = out[out.season.eq(season)]
        by_slate = season_frame.assign(
            _covered=season_frame.tail_edge.notna(),
        ).groupby(["season", "week"], observed=True)._covered.sum()
        season_rows.append({
            "season": season,
            "snapshot_rows": int(len(season_frame)),
            "slates": int(season_frame[["season", "week"]]
                          .drop_duplicates().shape[0]),
            "covered_rows": int(season_frame.tail_edge.notna().sum()),
            "covered_slates": int((by_slate > 0).sum()),
            "minimum_covered_rows_per_slate": (
                int(by_slate.min()) if not by_slate.empty else 0
            ),
            "mean_covered_rows_per_slate": (
                float(by_slate.mean()) if not by_slate.empty else 0.0
            ),
            "maximum_covered_rows_per_slate": (
                int(by_slate.max()) if not by_slate.empty else 0
            ),
        })
    audit = {
        "ambiguous_snapshot_names_dropped": ambiguous_count,
        "matched_prop_rows_before_ladder_collapse": int(len(matched)),
        "valid_ladders": int(len(quantiles)),
        "cutoffs": [
            {
                "season": int(row.season),
                "week": int(row.week),
                "common_slate_lock": row.common_slate_lock.isoformat(),
            }
            for row in cutoffs.sort_values(["season", "week"]).itertuples()
            if int(row.season) in SEASONS
        ],
        "seasons": season_rows,
    }
    return out, audit


def _preprocessor(numeric: Iterable[str]):
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    return ColumnTransformer([
        (
            "numeric",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]),
            list(numeric),
        ),
        (
            "position",
            Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ]),
            ["pos"],
        ),
    ])


def _fit_predict(
    train: pd.DataFrame,
    test: pd.DataFrame,
    numeric: tuple[str, ...],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import Pipeline

    columns = [*numeric, "pos"]
    regression = Pipeline([
        ("features", _preprocessor(numeric)),
        ("model", Ridge(alpha=10.0)),
    ])
    classifiers = {
        threshold: Pipeline([
            ("features", _preprocessor(numeric)),
            (
                "model",
                LogisticRegression(
                    C=0.1, solver="lbfgs", max_iter=2000,
                ),
            ),
        ])
        for threshold in (20, 30)
    }
    residual = train.actual.to_numpy(dtype=float) - train.mean_projection.to_numpy(
        dtype=float,
    )
    regression.fit(train[columns], residual)
    tail_predictions: dict[int, np.ndarray] = {}
    for threshold, classifier in classifiers.items():
        target = train.actual.ge(threshold).astype(int).to_numpy()
        if np.unique(target).size != 2:
            raise ValueError(f"training target >= {threshold} has one class")
        classifier.fit(train[columns], target)
        tail_predictions[threshold] = classifier.predict_proba(
            test[columns],
        )[:, 1]
    return (
        regression.predict(test[columns]),
        tail_predictions[20],
        tail_predictions[30],
    )


def _metrics(frame: pd.DataFrame, mask: np.ndarray | None = None) -> dict:
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    if mask is None:
        mask = np.ones(len(frame), dtype=bool)
    part = frame.loc[mask]
    if part.empty:
        raise ValueError("metric slice is empty")
    truth = part.actual.to_numpy(dtype=float)
    result = {"rows": int(len(part))}
    for arm in ("control", "treatment"):
        result[f"{arm}_mae"] = float(mean_absolute_error(
            truth, part[f"{arm}_score"],
        ))
        for threshold in (20, 30):
            result[f"{arm}_brier{threshold}"] = float(brier_score_loss(
                part.actual.ge(threshold).astype(int),
                part[f"{arm}_tail{threshold}"],
            ))
    result["tail20_rate"] = float(part.actual.ge(20).mean())
    result["tail30_rate"] = float(part.actual.ge(30).mean())
    return result


def _tail_calibration(frame: pd.DataFrame, threshold: int) -> list[dict]:
    rows: list[pd.DataFrame] = []
    for arm in ("control", "treatment"):
        part = pd.DataFrame({
            "arm": arm,
            "probability": frame[f"{arm}_tail{threshold}"].to_numpy(
                dtype=float,
            ),
            "actual_tail": frame.actual.ge(threshold).astype(int).to_numpy(),
        })
        part["decile"] = pd.qcut(
            part.probability.rank(method="first"), 10,
            labels=False, duplicates="drop",
        )
        rows.append(part)
    joined = pd.concat(rows, ignore_index=True)
    summary = joined.groupby(["arm", "decile"], observed=True).agg(
        rows=("actual_tail", "size"),
        mean_probability=("probability", "mean"),
        actual_rate=("actual_tail", "mean"),
    ).reset_index()
    return summary.to_dict("records")


def _separation(rows: pd.DataFrame) -> list[dict]:
    reports: list[dict] = []
    for season in (*SEASONS, "aggregate"):
        part = rows if season == "aggregate" else rows[rows.season.eq(season)]
        extremes: list[pd.DataFrame] = []
        for _position, group in part.groupby("pos", observed=True):
            ranked = group.tail_edge.rank(method="average", pct=True)
            selected = group[ranked.le(0.20) | ranked.gt(0.80)].copy()
            selected["edge_group"] = np.where(
                ranked.loc[selected.index].gt(0.80), "top", "bottom",
            )
            extremes.append(selected)
        joined = pd.concat(extremes, ignore_index=True)
        joined["residual"] = joined.actual - joined.mean_projection
        means = joined.groupby("edge_group", observed=True).residual.mean()
        reports.append({
            "season": season,
            "top_rows": int(joined.edge_group.eq("top").sum()),
            "bottom_rows": int(joined.edge_group.eq("bottom").sum()),
            "top_mean_residual": float(means.get("top", np.nan)),
            "bottom_mean_residual": float(means.get("bottom", np.nan)),
            "top_minus_bottom_residual": float(
                means.get("top", np.nan) - means.get("bottom", np.nan)
            ),
        })
    return reports


def evaluate_disagreement(rows: pd.DataFrame, source_audit: dict) -> dict:
    """Execute the frozen 2024-to-2025 player-level mechanism gate."""

    needed = {
        "season", "week", "gsis_id", "pos", "actual", "mean_projection",
        "salary", "production_upside", "tail_edge",
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"evaluation rows missing {sorted(missing)}")
    data = rows[
        rows.season.isin(SEASONS)
        & rows.pos.isin(PRIMARY_MARKET)
        & rows.actual.notna()
        & rows.mean_projection.notna()
        & rows.production_upside.notna()
        & rows.tail_edge.notna()
    ].copy()
    if data.empty:
        raise ValueError("no complete covered evaluation rows")
    train = data[data.season.eq(TRAIN_SEASON)]
    test = data[data.season.eq(TEST_SEASON)]
    if train.empty or test.empty:
        raise ValueError("2024 train or 2025 test rows are empty")

    predictions = test[
        ["season", "week", "gsis_id", "pos", "actual", "mean_projection"]
    ].copy()
    for arm, numeric in (
        ("control", CONTROL_NUMERIC),
        ("treatment", TREATMENT_NUMERIC),
    ):
        residual, tail20, tail30 = _fit_predict(train, test, numeric)
        predictions[f"{arm}_score"] = (
            test.mean_projection.to_numpy(dtype=float) + residual
        )
        predictions[f"{arm}_tail20"] = tail20
        predictions[f"{arm}_tail30"] = tail30

    overall = _metrics(predictions)
    wr_te = _metrics(predictions, predictions.pos.isin(["WR", "TE"]).to_numpy())
    by_position = {
        pos: _metrics(predictions, predictions.pos.eq(pos).to_numpy())
        for pos in sorted(predictions.pos.unique())
    }
    separation = _separation(data)
    separation_by_season = {
        str(row["season"]): row["top_minus_bottom_residual"]
        for row in separation
    }
    season_audit = {
        int(row["season"]): row for row in source_audit.get("seasons", [])
    }
    coverage_passes = all(
        season_audit.get(season, {}).get("slates") == 18
        and season_audit.get(season, {}).get("covered_slates") == 18
        and season_audit.get(season, {}).get("covered_rows", 0) >= 1500
        and season_audit.get(season, {}).get(
            "minimum_covered_rows_per_slate", 0,
        ) >= 30
        for season in SEASONS
    )
    gate = {
        "coverage_passes": bool(coverage_passes),
        "positive_separation_2024": bool(
            separation_by_season.get("2024", np.nan) > 0
        ),
        "positive_separation_2025": bool(
            separation_by_season.get("2025", np.nan) > 0
        ),
        "positive_separation_aggregate": bool(
            separation_by_season.get("aggregate", np.nan) > 0
        ),
        "heldout_brier30_improves": bool(
            overall["treatment_brier30"] < overall["control_brier30"]
        ),
        "heldout_mae_not_worse_over_1pct": bool(
            overall["treatment_mae"] <= overall["control_mae"] * 1.01
        ),
        "heldout_brier20_not_worse_over_1pct": bool(
            overall["treatment_brier20"] <= overall["control_brier20"] * 1.01
        ),
        "heldout_wr_te_brier30_not_worse_over_1pct": bool(
            wr_te["treatment_brier30"] <= wr_te["control_brier30"] * 1.01
        ),
    }
    return {
        "panel_id": PANEL_ID,
        "train_season": TRAIN_SEASON,
        "test_season": TEST_SEASON,
        "training_rows": int(len(train)),
        "heldout_rows": int(len(test)),
        "source_audit": source_audit,
        "separation": separation,
        "heldout_overall": overall,
        "heldout_wr_te": wr_te,
        "heldout_by_position": by_position,
        "calibration20": _tail_calibration(predictions, 20),
        "calibration30": _tail_calibration(predictions, 30),
        "gate": gate,
        "disposition": (
            "licenses-market-tail-union" if all(gate.values())
            else "market-tail-mechanism-gate-fails"
        ),
    }


def run(panel_id: str = PANEL_ID) -> dict:
    """Load frozen warehouse inputs, run once, and print machine JSON."""

    if panel_id != PANEL_ID:
        raise ValueError(f"market-tail protocol is frozen to panel {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    features = query_df(f"""
        SELECT season, week, gsis_id, name, pos, salary,
               mean_projection, proj_p50, proj_p90, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id
          AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN ('QB', 'RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id, "seasons": list(SEASONS)})
    props = query_df(f"""
        SELECT season, week, event_id, commence_time, snapshot_ts,
               market, player, point, outcome_name, price
        FROM `{settings.raw}.prop_lines`
        WHERE season IN UNNEST(@seasons)
          AND bookmaker = 'draftkings'
          AND market IN UNNEST(@markets)
          AND point IS NOT NULL
        """, params={
            "seasons": list(SEASONS),
            "markets": list(ALT_MARKETS),
        })
    joined, audit = attach_market_tail_edges(features, props)
    report = evaluate_disagreement(joined, audit)
    print("MARKET_TAIL_DIAGNOSTIC_JSON=" + json.dumps(report, sort_keys=True))
    return report

