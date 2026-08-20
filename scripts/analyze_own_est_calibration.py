#!/usr/bin/env python3
"""own_est calibration gate (queue A4 entry gate).

The winner anatomy measured the winners' shape in REALIZED ownership
(chalk core plus a median of four sub-10% pieces). Generation can only
constrain PREDICTED ownership (`own_est`, point-in-time by construction).
So before the ownership-template arm can be frozen, one question must be
answered: does own_est separate the ownership classes the template
depends on, on the same slates the template targets?

This audit joins the point-in-time `own_est` from the registered slate
snapshots against the realized Millionaire ownership already in
`nfl_raw.contest_ownership`, on the winner slates, and reports rank
correlation plus the confusion between predicted and realized ownership
classes (<10%, 10-20%, >=20%).

Descriptive and score-free: no lineup score, no realized fantasy points,
no simulated total is read, so it needs no historical-outcome lease and
runs safely alongside an in-flight scored arm. It licenses nothing; it
only decides whether the A4 arm is worth freezing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_atlas_minimal_world_selection_c as base  # noqa: E402

from nfl_dfs.analysis.winner_anatomy import (  # noqa: E402
    WinnerAnatomyError,
    same_team_code,
)
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.research.real_winner_overlap import (  # noqa: E402
    _TEAM_NICKNAMES,
    _name_matches,
    _name_tokens,
)

PROTOCOL_ID = "20260820-own-est-calibration-gate-v1"
SNAP_SQL = """
SELECT DISTINCT season, week, id, name, pos, team, own_est
FROM `nfl-predictions-503414.nfl_predictions.slate_player_features`
WHERE panel_run_id IN UNNEST(@panels)
"""
OWN_SQL = """
SELECT season, week, display_name, roster_position, pct_drafted
FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
WHERE contest_name LIKE '%Millionaire%'
  AND season BETWEEN 2023 AND 2025
"""
# Class edges in PERCENT. The template needs the low class (leverage
# pieces) and the high class (chalk core) to be distinguishable.
LOW_EDGE = 10.0
HIGH_EDGE = 20.0


def _match_realized(row: pd.Series, slate_own: pd.DataFrame) -> float | None:
    """Same frozen matching rule as the winner anatomy census."""
    pos = str(row.pos).upper()
    if pos == "DST":
        rows = slate_own[slate_own.roster_position.astype(str).eq("DST")]
        for entry in rows.itertuples(index=False):
            nickname = "".join(_name_tokens(entry.display_name))
            code = _TEAM_NICKNAMES.get(nickname)
            if code is not None and same_team_code(code, str(row.team)):
                return float(entry.pct_drafted)
        return None
    rows = slate_own[slate_own.roster_position.astype(str).eq(pos)]
    if rows.empty:
        return None
    names = rows.display_name.astype(str)
    exact = rows[names.str.strip().str.lower().eq(
        str(row["name"]).strip().lower())]
    if len(exact) == 1:
        return float(exact.iloc[0].pct_drafted)
    fuzzy = rows[[_name_matches(row["name"], value) for value in names]]
    if len(fuzzy) == 1:
        return float(fuzzy.iloc[0].pct_drafted)
    return None


def _classify(pct: float) -> str:
    if pct < LOW_EDGE:
        return "low"
    if pct < HIGH_EDGE:
        return "mid"
    return "high"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    snaps = query_df(SNAP_SQL, params={"panels": list(base.SOURCE_PANEL_IDS)})
    if snaps.empty:
        raise WinnerAnatomyError("no slate snapshots found")
    realized = query_df(OWN_SQL)
    snaps["own_est_pct"] = snaps.own_est.astype(float) * 100.0

    paired = []
    for (season, week), slate in snaps.groupby(["season", "week"]):
        slate_own = realized[
            realized.season.astype(int).eq(int(season))
            & realized.week.astype(int).eq(int(week))]
        if slate_own.empty:
            continue
        for _, row in slate.iterrows():
            actual = _match_realized(row, slate_own)
            if actual is None:
                continue
            paired.append({
                "season": int(season), "week": int(week),
                "id": str(row["id"]), "pos": str(row["pos"]),
                "pred": float(row["own_est_pct"]),
                "actual": float(actual),
            })
    if not paired:
        raise WinnerAnatomyError("no predicted/realized ownership pairs")
    frame = pd.DataFrame(paired)
    frame["pred_class"] = frame.pred.map(_classify)
    frame["actual_class"] = frame.actual.map(_classify)

    spearman = float(frame.pred.corr(frame.actual, method="spearman"))
    pearson = float(frame.pred.corr(frame.actual))
    confusion = (
        frame.groupby(["pred_class", "actual_class"]).size().unstack(
            fill_value=0).reindex(index=["low", "mid", "high"],
                                  columns=["low", "mid", "high"],
                                  fill_value=0)
    )
    # The two questions the template actually depends on.
    pred_low = frame[frame.pred_class.eq("low")]
    pred_high = frame[frame.pred_class.eq("high")]
    precision_low = (
        float(pred_low.actual_class.eq("low").mean()) if len(pred_low) else None)
    precision_high = (
        float(pred_high.actual_class.eq("high").mean())
        if len(pred_high) else None)
    per_slate_rho = (
        frame.groupby(["season", "week"])
        .apply(lambda g: g.pred.corr(g.actual, method="spearman"),
               include_groups=False)
        .dropna()
    )

    report = {
        "protocol_id": PROTOCOL_ID,
        "n_pairs": int(len(frame)),
        "n_slates": int(frame.groupby(["season", "week"]).ngroups),
        "spearman_overall": spearman,
        "pearson_overall": pearson,
        "per_slate_spearman_median": float(per_slate_rho.median()),
        "per_slate_spearman_min": float(per_slate_rho.min()),
        "per_slate_spearman_q25": float(per_slate_rho.quantile(0.25)),
        "class_edges_pct": {"low": LOW_EDGE, "high": HIGH_EDGE},
        "confusion_pred_by_actual": {
            str(pred): {str(act): int(confusion.loc[pred, act])
                        for act in confusion.columns}
            for pred in confusion.index
        },
        "precision_predicted_low": precision_low,
        "precision_predicted_high": precision_high,
        "mean_pred_pct": float(frame.pred.mean()),
        "mean_actual_pct": float(frame.actual.mean()),
        "uses_realized_outcomes": False,
        "reads_realized_ownership": True,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    print(
        "OWN_EST_CALIBRATION_COMPLETE",
        f"pairs={report['n_pairs']}",
        f"spearman={spearman:.3f}",
        f"prec_low={precision_low}",
        f"prec_high={precision_high}",
        f"sha256={hashlib.sha256(payload).hexdigest()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
