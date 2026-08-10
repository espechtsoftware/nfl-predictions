"""Lagged pass-play participation proxy for evaluating paid route data.

The nflverse participation feed is season-delayed and does not identify every
route.  This module therefore never writes production features.  It asks a
narrower question: does knowing which skill players were on the field for
prior-game dropbacks improve held-out residual and 20-point-tail forecasts
over the accepted pre-lock snapshot features?
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import numpy as np
import pandas as pd

PANEL_ID = "20260809-e80-k1-ce12-c616390"
SEASONS = (2023, 2024, 2025)
HELD_OUT_SEASONS = (2024, 2025)
SKILL_POSITIONS = frozenset({"RB", "FB", "WR", "TE"})

CONTROL_NUMERIC = (
    "proj",
    "salary",
    "target_share_last",
    "target_share_jump",
    "snap_share_last",
    "snap_share_jump",
    "team_vacated_target_share",
)
PARTICIPATION_NUMERIC = (
    "pass_play_share_last",
    "pass_play_share_jump",
    "redzone_pass_play_share_last",
    "redzone_pass_play_share_jump",
)


def _split(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def build_weekly_participation(
    participation: pd.DataFrame,
    pbp: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Return player/team/week pass-play presence shares.

    Denominators use only dropbacks whose participation row has exactly eleven
    aligned offensive player IDs and positions.  This makes a malformed play
    incapable of lowering every player's share.
    """

    p_needed = {
        "nflverse_game_id", "play_id", "possession_team",
        "offense_players", "offense_positions",
    }
    b_needed = {
        "game_id", "play_id", "season", "week", "posteam",
        "qb_dropback", "yardline_100", "season_type", "play_type",
    }
    if missing := p_needed - set(participation.columns):
        raise ValueError(f"participation missing {sorted(missing)}")
    if missing := b_needed - set(pbp.columns):
        raise ValueError(f"play by play missing {sorted(missing)}")

    part = participation[list(p_needed)].copy()
    part["_ids"] = part.offense_players.map(_split)
    part["_positions"] = part.offense_positions.map(_split)
    lengths = pd.DataFrame({
        "ids": part._ids.map(len),
        "positions": part._positions.map(len),
    })
    aligned = lengths.ids.eq(lengths.positions)
    eleven = lengths.ids.eq(11)
    part["_valid_personnel"] = aligned & eleven

    plays = pbp[list(b_needed)].copy()
    plays = plays[
        plays.season_type.eq("REG")
        & pd.to_numeric(plays.qb_dropback, errors="coerce").eq(1)
        & ~plays.play_type.fillna("").eq("no_play")
    ]
    merged = part.merge(
        plays,
        left_on=["nflverse_game_id", "play_id"],
        right_on=["game_id", "play_id"],
        how="inner",
        validate="one_to_one",
    )
    merged = merged[
        merged._valid_personnel
        & merged.possession_team.eq(merged.posteam)
        & merged.posteam.notna()
    ].copy()
    if merged.empty:
        raise ValueError("no valid regular-season dropbacks joined")

    play_keys = ["season", "week", "posteam", "game_id", "play_id"]
    valid_plays = merged.drop_duplicates(play_keys)
    team = valid_plays.groupby(
        ["season", "week", "posteam"], observed=True,
    ).agg(
        team_dropbacks=("play_id", "size"),
        team_redzone_dropbacks=(
            "yardline_100",
            lambda s: int(pd.to_numeric(s, errors="coerce").le(20).sum()),
        ),
    ).reset_index()

    exploded = merged.explode(["_ids", "_positions"], ignore_index=True)
    exploded = exploded[
        exploded._ids.notna() & exploded._positions.isin(SKILL_POSITIONS)
    ].copy()
    exploded["is_redzone"] = pd.to_numeric(
        exploded.yardline_100, errors="coerce",
    ).le(20)
    player = exploded.groupby(
        ["season", "week", "posteam", "_ids"], observed=True,
    ).agg(
        player_dropbacks=("play_id", "size"),
        player_redzone_dropbacks=("is_redzone", "sum"),
    ).reset_index().rename(columns={"_ids": "gsis_id", "posteam": "team"})
    team = team.rename(columns={"posteam": "team"})
    out = player.merge(
        team, on=["season", "week", "team"], how="left",
        validate="many_to_one",
    )
    out["pass_play_share"] = out.player_dropbacks / out.team_dropbacks
    out["redzone_pass_play_share"] = np.where(
        out.team_redzone_dropbacks.gt(0),
        out.player_redzone_dropbacks / out.team_redzone_dropbacks,
        np.nan,
    )
    if not out.pass_play_share.between(0, 1).all():
        raise ValueError("pass-play participation share outside [0, 1]")
    rz = out.redzone_pass_play_share.dropna()
    if not rz.between(0, 1).all():
        raise ValueError("red-zone pass-play participation outside [0, 1]")

    audit = {
        "participation_rows": int(len(part)),
        "malformed_personnel_rows": int((~part._valid_personnel).sum()),
        "joined_valid_dropbacks": int(len(valid_plays)),
        "player_week_rows": int(len(out)),
    }
    cols = [
        "season", "week", "team", "gsis_id", "player_dropbacks",
        "team_dropbacks", "pass_play_share", "player_redzone_dropbacks",
        "team_redzone_dropbacks", "redzone_pass_play_share",
    ]
    return out[cols].sort_values(
        ["season", "week", "team", "gsis_id"],
    ).reset_index(drop=True), audit


def attach_strict_prior(
    targets: pd.DataFrame,
    weekly: pd.DataFrame,
) -> pd.DataFrame:
    """Attach the latest strictly earlier participation row and its change."""

    t_needed = {"season", "week", "gsis_id"}
    w_needed = {
        "season", "week", "gsis_id", "pass_play_share",
        "redzone_pass_play_share",
    }
    if missing := t_needed - set(targets.columns):
        raise ValueError(f"targets missing {sorted(missing)}")
    if missing := w_needed - set(weekly.columns):
        raise ValueError(f"weekly participation missing {sorted(missing)}")

    history: dict[tuple[int, str], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for (season, player), group in weekly.groupby(
        ["season", "gsis_id"], sort=False, observed=True,
    ):
        ordered = group.sort_values("week")
        history[(int(season), str(player))] = (
            ordered.week.to_numpy(dtype=int),
            ordered.pass_play_share.to_numpy(dtype=float),
            ordered.redzone_pass_play_share.to_numpy(dtype=float),
        )

    rows: list[dict[str, float | int]] = []
    for row in targets[["season", "week", "gsis_id"]].itertuples(index=False):
        values = history.get((int(row.season), str(row.gsis_id)))
        result: dict[str, float | int] = {
            "participation_source_week": -1,
            "pass_play_share_last": np.nan,
            "pass_play_share_jump": np.nan,
            "redzone_pass_play_share_last": np.nan,
            "redzone_pass_play_share_jump": np.nan,
        }
        if values is not None:
            weeks, shares, redzone = values
            position = int(np.searchsorted(weeks, int(row.week), side="left")) - 1
            if position >= 0:
                result["participation_source_week"] = int(weeks[position])
                result["pass_play_share_last"] = float(shares[position])
                result["redzone_pass_play_share_last"] = float(redzone[position])
                if position >= 1:
                    result["pass_play_share_jump"] = float(
                        shares[position] - shares[position - 1]
                    )
                    result["redzone_pass_play_share_jump"] = float(
                        redzone[position] - redzone[position - 1]
                    )
        rows.append(result)
    additions = pd.DataFrame(rows, index=targets.index)
    out = pd.concat([targets.copy(), additions], axis=1)
    leaked = out.participation_source_week.ge(out.week)
    if leaked.any():
        raise ValueError("participation join used same/future week")
    return out


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
) -> tuple[np.ndarray, np.ndarray]:
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import Pipeline

    columns = [*numeric, "pos"]
    regression = Pipeline([
        ("features", _preprocessor(numeric)),
        ("model", Ridge(alpha=10.0)),
    ])
    classifier = Pipeline([
        ("features", _preprocessor(numeric)),
        (
            "model",
            LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000),
        ),
    ])
    y_residual = train.actual.to_numpy(dtype=float) - train.proj.to_numpy(
        dtype=float,
    )
    y_tail = train.actual.ge(20).astype(int).to_numpy()
    regression.fit(train[columns], y_residual)
    classifier.fit(train[columns], y_tail)
    return (
        regression.predict(test[columns]),
        classifier.predict_proba(test[columns])[:, 1],
    )


def evaluate_proxy(rows: pd.DataFrame) -> dict:
    """Run the frozen 2024/2025 season-walk-forward comparison."""

    needed = {
        "season", "week", "gsis_id", "pos", "actual",
        *CONTROL_NUMERIC, *PARTICIPATION_NUMERIC,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"evaluation rows missing {sorted(missing)}")
    data = rows[
        rows.pos.isin(["RB", "WR", "TE"])
        & rows.actual.notna()
        & rows.proj.notna()
        & rows.pass_play_share_last.notna()
    ].copy()
    if data.empty:
        raise ValueError("no complete proxy evaluation rows")

    predictions: list[pd.DataFrame] = []
    fold_rows: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = data[data.season.lt(held_out)]
        test = data[data.season.eq(held_out)]
        if train.empty or test.empty:
            raise ValueError(f"fold {held_out} has empty train or test rows")
        fold = test[["season", "week", "gsis_id", "pos", "proj", "actual"]].copy()
        for label, numeric in (
            ("control", CONTROL_NUMERIC),
            ("treatment", CONTROL_NUMERIC + PARTICIPATION_NUMERIC),
        ):
            residual, tail = _fit_predict(train, test, numeric)
            fold[f"{label}_score"] = test.proj.to_numpy(dtype=float) + residual
            fold[f"{label}_tail"] = tail
        predictions.append(fold)
        fold_rows.append(_score_predictions(fold, label=str(held_out)))
    all_predictions = pd.concat(predictions, ignore_index=True)
    aggregate = _score_predictions(all_predictions, label="aggregate")
    gate = {
        "aggregate_mae_improves": (
            aggregate["treatment_mae"] < aggregate["control_mae"]
        ),
        "aggregate_brier_improves": (
            aggregate["treatment_brier"] < aggregate["control_brier"]
        ),
        "wr_te_brier_improves": (
            aggregate["treatment_wr_te_brier"]
            < aggregate["control_wr_te_brier"]
        ),
        "no_fold_metric_worse_over_1pct": all(
            fold["treatment_mae"] <= fold["control_mae"] * 1.01
            and fold["treatment_brier"] <= fold["control_brier"] * 1.01
            for fold in fold_rows
        ),
    }
    return {
        "panel_id": PANEL_ID,
        "folds": fold_rows,
        "aggregate": aggregate,
        "gate": gate,
        "disposition": (
            "supports-paid-route-trial" if all(gate.values())
            else "route-proxy-gate-fails"
        ),
        "calibration_deciles": _calibration_deciles(all_predictions),
    }


def _score_predictions(frame: pd.DataFrame, *, label: str) -> dict:
    from sklearn.metrics import brier_score_loss, mean_absolute_error

    truth = frame.actual.to_numpy(dtype=float)
    tail = frame.actual.ge(20).astype(int).to_numpy()
    wr_te = frame.pos.isin(["WR", "TE"]).to_numpy()
    if not wr_te.any():
        raise ValueError(f"{label} has no WR/TE rows")
    return {
        "fold": label,
        "rows": int(len(frame)),
        "tail_rate": float(tail.mean()),
        "control_mae": float(mean_absolute_error(truth, frame.control_score)),
        "treatment_mae": float(mean_absolute_error(truth, frame.treatment_score)),
        "control_brier": float(brier_score_loss(tail, frame.control_tail)),
        "treatment_brier": float(brier_score_loss(tail, frame.treatment_tail)),
        "control_wr_te_brier": float(
            brier_score_loss(tail[wr_te], frame.loc[wr_te, "control_tail"])
        ),
        "treatment_wr_te_brier": float(
            brier_score_loss(tail[wr_te], frame.loc[wr_te, "treatment_tail"])
        ),
    }


def _calibration_deciles(frame: pd.DataFrame) -> list[dict]:
    stacked: list[pd.DataFrame] = []
    for label in ("control", "treatment"):
        part = pd.DataFrame({
            "arm": label,
            "probability": frame[f"{label}_tail"].to_numpy(dtype=float),
            "actual_tail": frame.actual.ge(20).astype(int).to_numpy(),
        })
        part["decile"] = pd.qcut(
            part.probability.rank(method="first"), 10, labels=False,
            duplicates="drop",
        )
        stacked.append(part)
    joined = pd.concat(stacked, ignore_index=True)
    summary = joined.groupby(["arm", "decile"], observed=True).agg(
        rows=("actual_tail", "size"),
        mean_probability=("probability", "mean"),
        actual_rate=("actual_tail", "mean"),
    ).reset_index()
    return summary.to_dict("records")


def run(panel_id: str = PANEL_ID) -> dict:
    """Load the frozen sources, execute the diagnostic, and print JSON."""

    if panel_id != PANEL_ID:
        raise ValueError(f"proxy protocol is frozen to panel {PANEL_ID}")
    import nflreadpy as nfl

    from ..bq import query_df
    from ..config import settings

    participation = pd.concat([
        nfl.load_participation([season]).to_pandas() for season in SEASONS
    ], ignore_index=True)
    pbp = query_df(f"""
        SELECT game_id, play_id, season, week, posteam, qb_dropback,
               yardline_100, season_type, play_type
        FROM `{settings.raw}.pbp`
        WHERE season IN UNNEST(@seasons)
        """, params={"seasons": list(SEASONS)})
    snapshots = query_df(f"""
        SELECT season, week, gsis_id, pos, proj, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id
          AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN ('RB', 'WR', 'TE')
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id, "seasons": list(SEASONS)})
    weekly, audit = build_weekly_participation(participation, pbp)
    joined = attach_strict_prior(snapshots, weekly)
    report = evaluate_proxy(joined)
    report["source_audit"] = audit
    report["snapshot_rows"] = int(len(snapshots))
    report["rows_with_prior_participation"] = int(
        joined.pass_play_share_last.notna().sum()
    )
    print("PASS_PARTICIPATION_JSON=" + json.dumps(report, sort_keys=True))
    return report

