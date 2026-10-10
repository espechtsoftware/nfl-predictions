"""The frozen reader for the DK opponent-rank accuracy read (study list rows 8 / 106; prereg
reports/2026-10-10-prereg-oprk-accuracy-w05.md). ONE WEEK, DESCRIPTIVE, DECIDES NOTHING.

For the week's main slate (group 154468 for 2026 W5), every QB / RB / WR / TE with a pre-lock DK opponent rank (OPRK: the last
nfl_raw.dk_draftable_attributes capture strictly before --lock-utc, attr_id -2, sort_value 1 = the toughest defense, 32 = the easiest),
Fantasy Points' projection (the last fantasy_points_dfs_projections capture strictly before --lock-utc, slate --group) and a realized
DK score (nfl_raw.contest_ownership fpts for the week, max over contests per name): residual = realized - FP projection.
Prints, per position: n players, Spearman(OPRK, residual) and Spearman(our adjusted DvP, residual) (our DvP = the opponent's
<pos>_fp_allowed_adj_l6 from nfl_features.player_week_inference, higher = easier), each with a 95% bootstrap interval resampling
GAMES (team-game clusters), B 2,000, seed 20261010; and the 20+ / 30+ point rates by OPRK band (1-11 tough, 12-21 mid, 22-32 easy).
Players projected under 3 by FP are excluded (role players add noise, not signal). A positive Spearman = DK's easier matchups
beat FP's projection.

    python reports/2026-10-10-oprk/oprk_accuracy_reader.py --season 2026 --week 5 --group 154468 --lock-utc 2026-10-11T17:00:00Z
"""
from __future__ import annotations

import argparse
import re

import numpy as np
import pandas as pd
from google.cloud import bigquery

SEED, B, MIN_FP = 20261010, 2000, 3.0
canon = lambda s: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower()))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 5:
        return float("nan")
    ra, rb = pd.Series(a).rank().to_numpy(), pd.Series(b).rank().to_numpy()
    return float(np.corrcoef(ra, rb)[0, 1])


def boot(d: pd.DataFrame, x: str, rng) -> tuple[float, float, float]:
    d = d.dropna(subset=[x, "resid"])
    pt = spearman(d[x].to_numpy(), d.resid.to_numpy())
    games = d.game.unique(); idx = {g: d.index[d.game == g] for g in games}
    vals = []
    for _ in range(B):
        take = rng.choice(games, len(games), replace=True)
        s = d.loc[np.concatenate([idx[g] for g in take])]
        vals.append(spearman(s[x].to_numpy(), s.resid.to_numpy()))
    vals = np.array([v for v in vals if np.isfinite(v)])
    return pt, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--group", type=int, required=True); ap.add_argument("--lock-utc", required=True)
    a = ap.parse_args()
    bq = bigquery.Client(project="nfl-predictions-503414")
    P = [bigquery.ScalarQueryParameter("g", "INT64", a.group), bigquery.ScalarQueryParameter("lock", "TIMESTAMP", a.lock_utc),
         bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week),
         bigquery.ScalarQueryParameter("gs", "STRING", str(a.group))]
    q = lambda sql: bq.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=P)).to_dataframe()
    ok = q("""SELECT CAST(dk_player_id AS STRING) id, display_name, team_abbr team, position pos, sort_value oprk, pulled_at
              FROM `nfl_raw.dk_draftable_attributes` WHERE draft_group_id = @g AND attr_id = -2 AND pulled_at =
              (SELECT MAX(pulled_at) FROM `nfl_raw.dk_draftable_attributes` WHERE draft_group_id = @g AND pulled_at < @lock)""")
    fp = q("""SELECT name, team, position pos, fantasy_points fp FROM `nfl_raw.fantasy_points_dfs_projections`
              WHERE season = @s AND week = @w AND slate_id = @gs AND retrieved_at = (SELECT MAX(retrieved_at) FROM
              `nfl_raw.fantasy_points_dfs_projections` WHERE season = @s AND week = @w AND slate_id = @gs AND retrieved_at < @lock)""")
    act = q("""SELECT display_name, MAX(fpts) fpts FROM `nfl_raw.contest_ownership` WHERE season = @s AND week = @w GROUP BY 1""")
    dvp = q("""SELECT team, position pos, ANY_VALUE(opponent) opp, ANY_VALUE(qb_fp_allowed_adj_l6) qb, ANY_VALUE(rb_fp_allowed_adj_l6) rb,
               ANY_VALUE(wr_fp_allowed_adj_l6) wr, ANY_VALUE(te_fp_allowed_adj_l6) te FROM `nfl_features.player_week_inference`
               WHERE season = @s AND week = @w GROUP BY 1, 2""")
    print(f"OPRK capture {ok.pulled_at.max()} ({len(ok)} players); FP rows {len(fp)}; realized names {len(act)}")
    if ok.empty or fp.empty or act.empty:
        raise SystemExit("an input is empty: no read")
    ok = ok[ok.pos.isin(["QB", "RB", "WR", "TE"])].copy()
    ok["key"] = ok.display_name.map(canon) + "|" + ok.team + "|" + ok.pos
    fp["key"] = fp.name.map(canon) + "|" + fp.team.str.upper() + "|" + fp.pos.str.upper()
    act["n"] = act.display_name.map(canon); act = act[~act.n.duplicated(keep=False)]
    d = ok.merge(fp[["key", "fp"]].drop_duplicates("key"), on="key", how="inner")
    d = d.merge(act[["n", "fpts"]], left_on=d.display_name.map(canon), right_on="n", how="inner")
    e = dvp.groupby("team").opp.first()
    dv = dvp.assign(v=[r[r.pos.lower()] if r.pos.lower() in ("qb", "rb", "wr", "te") else np.nan for _, r in dvp.iterrows()])
    dvm = dict(zip(dv.team + "|" + dv.pos, dv.v))
    d["opp"] = d.team.map(e); d["game"] = ["-".join(sorted([t, o])) if isinstance(o, str) else t for t, o in zip(d.team, d.opp)]
    d["dvp"] = (d.team + "|" + d.pos).map(dvm)
    d = d[d.fp >= MIN_FP].reset_index(drop=True); d["resid"] = d.fpts - d.fp
    rng = np.random.default_rng(SEED)
    print(f"\nONE WEEK, DESCRIPTIVE, DECIDES NOTHING. {a.season} W{a.week}, group {a.group}, lock {a.lock_utc}; FP-projected >= {MIN_FP}: {len(d)} players")
    print("pos   n   Spearman(OPRK, residual) [95% game-bootstrap]    Spearman(our DvP, residual) [95%]")
    for pos in ("QB", "RB", "WR", "TE"):
        g = d[d.pos == pos].reset_index(drop=True)
        o = boot(g, "oprk", rng); v = boot(g, "dvp", rng)
        print(f"{pos:4} {len(g):3}   {o[0]:+.3f} [{o[1]:+.3f}, {o[2]:+.3f}]                {v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]")
    d["band"] = pd.cut(d.oprk, [0, 11, 21, 32], labels=["tough 1-11", "mid 12-21", "easy 22-32"])
    t = d.groupby("band", observed=True).agg(n=("fpts", "size"), mean_resid=("resid", "mean"), r20=("fpts", lambda s: (s >= 20).mean()),
                                             r30=("fpts", lambda s: (s >= 30).mean()))
    print("\nby OPRK band (all positions):"); print(t.round(3).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
