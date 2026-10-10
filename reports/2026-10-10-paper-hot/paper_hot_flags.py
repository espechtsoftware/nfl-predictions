"""The hot-flag file for study 38's MIXT_QA0_HOT1 paper arm (amendment 6y; the operator 10-10, relaying the researcher: "a HOT1
paper arm in study 38 would let Week 5's real results arbitrate at no cost to the book"). Format agreed with the lab reviewer
10-10 before building. Study 109's HOT1 flag = study 65's frozen last_game() at x 2.0 (nfl2 experiments/s65_tailtilt.py l.113-125):
a skill player's LAST regular-season game this season before week W; his up to 4 REG games just before it, crossing into last
season; hot = 1 iff prior_n >= 2 and last_pts >= 2.0 x max(prior_mean, 5.0).

    python paper_hot_flags.py --frame <a slate frame.parquet with dk_player_id, id or gsis_id, pos, display_name> \
        --season 2026 --week 5 --out <snapshot>/paper-hot-w05.csv

Rows: every QB / RB / WR / TE of the frame with a REG game this season before week W (nfl_features.player_week_actuals,
has_stat_line, DraftKings classic dk_points; season W's weeks < W and last season's weeks 1-18). prior_mean is 0.0 when
prior_n is 0 (finite by contract; such a row is never hot)."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

X, FLOOR, MIN_PRIOR, PRIOR_GAMES = 2.0, 5.0, 2, 4
SKILL = ("QB", "RB", "WR", "TE")
SOURCE = "nfl_features.player_week_actuals (has_stat_line; REG weeks; dk_points = DraftKings classic)"


def dk(v) -> str:
    return str(v).strip().removesuffix(".0")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=Path, required=True); ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True); ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    fr = pd.read_parquet(a.frame)
    gid = "gsis_id" if "gsis_id" in fr.columns else "id"
    name = "display_name" if "display_name" in fr.columns else "name"
    fr = fr[fr.pos.astype(str).isin(SKILL) & fr["dk_player_id"].notna() & fr[gid].notna()].copy()
    fr["dkid"] = fr["dk_player_id"].map(dk); fr["gsis"] = fr[gid].astype(str)
    fr = fr.drop_duplicates(["dkid", "gsis"])
    if fr.dkid.duplicated().any() or fr.gsis.duplicated().any():
        raise SystemExit(f"{a.frame}: a dk_player_id or gsis id maps to two players")
    q = """SELECT gsis_id, season, week, dk_points FROM `nfl_features.player_week_actuals`
           WHERE gsis_id IN UNNEST(@ids) AND has_stat_line
             AND ((season = @s AND week < @w) OR (season = @s - 1 AND week <= 18))"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("ids", "STRING", fr.gsis.tolist()),
                                                    bigquery.ScalarQueryParameter("s", "INT64", a.season),
                                                    bigquery.ScalarQueryParameter("w", "INT64", a.week)])
    w = bigquery.Client(project="nfl-predictions-503414").query(q, job_config=cfg).to_dataframe()
    rows = []
    by = {g: h.sort_values(["season", "week"]) for g, h in w.groupby("gsis_id")}
    for r in fr.itertuples():
        h = by.get(r.gsis)
        if h is None or int(h.season.iloc[-1]) != a.season:
            continue                                            # no REG game this season before week W: not in the file
        pts = h.dk_points.astype(float).tolist()
        last, prior = pts[-1], pts[:-1][-PRIOR_GAMES:]
        pm = float(sum(prior) / len(prior)) if prior else 0.0
        hot = int(len(prior) >= MIN_PRIOR and last >= X * max(pm, FLOOR))
        rows.append({"dk_player_id": r.dkid, "gsis_id": r.gsis, "name": str(getattr(r, name)), "pos": str(r.pos),
                     "last_week": int(h.week.iloc[-1]), "last_pts": round(last, 4), "prior_mean": round(pm, 4),
                     "prior_n": len(prior), "hot": hot})
    out = pd.DataFrame(rows, columns=["dk_player_id", "gsis_id", "name", "pos", "last_week", "last_pts", "prior_mean", "prior_n", "hot"])
    # the reader's own checks, before writing: finite numbers, unique ids, skill only, hot agrees with its numbers
    assert out.dk_player_id.is_unique and out.gsis_id.is_unique and out.pos.isin(SKILL).all()
    assert all(math.isfinite(v) for c in ("last_pts", "prior_mean") for v in out[c])
    re = ((out.prior_n >= MIN_PRIOR) & (out.last_pts >= X * out.prior_mean.clip(lower=FLOOR))).astype(int)
    assert (re == out.hot).all()
    meta = {"what": "hot flags (study 109's HOT1)", "x": X, "floor": FLOOR, "min_prior": MIN_PRIOR, "prior_games": PRIOR_GAMES,
            "season": a.season, "week": a.week, "source": SOURCE, "points": "DK points",
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "frame": str(a.frame)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as f:
        f.write("# " + json.dumps(meta) + "\n")
        out.to_csv(f, index=False)
    print(f"{a.out}: {len(out)} skill players with a REG game this season before W{a.week}; hot {int(out.hot.sum())} "
          f"(QB {int(out[out.pos == 'QB'].hot.sum())}, RB {int(out[out.pos == 'RB'].hot.sum())}, WR {int(out[out.pos == 'WR'].hot.sum())}, "
          f"TE {int(out[out.pos == 'TE'].hot.sum())}); prior_n < 2: {int((out.prior_n < 2).sum())}")


if __name__ == "__main__":
    main()
