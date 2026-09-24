#!/usr/bin/env python3
"""Pre-lock predicted ownership and the LOW / CHALK player sets for the chalk-core boom sleeve.

External review 2026-09-22 (§2.4, §2.7) and production's response: top Millionaire finishers carry at most
one or two players under 5% ownership and at least one at 20%+, while ~90% of our Week-2 corpus carried 3+
sub-5% players. The laptop's nfl2 sleeve constrains boom solves with the sets written here.

The model is a walk-forward LightGBM on pre-lock inputs only (position, salary, served projection and p90,
value and its within-position ranks, implied team total), trained on the 2022-2025 Sunday Millionaire
ownership. Predictions compress (a 20%+ player is often predicted 12%), so the sets are defined by RANK:
CHALK is the top `round(chalk_share * n)` players by predicted ownership and LOW the bottom
`round(low_share * n_skill)` skill players, where the shares are the historical per-slate fractions of
players at >= 20% and skill players under 5%.

    python scripts/ownership_sets.py validate                      # walk-forward 2023-25 Spearman
    python scripts/ownership_sets.py sets --week 3 --group 153769 --out ~/week3-sunday/ownership_sets.csv
    python scripts/ownership_sets.py replay-sets --seasons 2023,2024 --out DIR   # walk-forward, one file per slate

Reads BigQuery; the output holds no DraftKings standings and may live on the build host.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PANEL = "20260811-pitclean-e80-k1-a12ab31"      # point-in-time replay projections, 2019/2021-2025
FEATURES = ["pos_c", "salary", "proj", "proj_p90", "value", "proj_rank", "value_rank", "sal_rank",
            "value_z", "implied_team_total"]
# Optional pre-lock lag inputs (2026-09-23): last week's Millionaire ownership, its 3-week mean, and the salary
# change vs last week. Walk-forward within-slate Spearman 2023/24/25: 0.751/0.768/0.767 base -> 0.781/0.786/0.789.
# OFF by default: the frozen L02 panel pins sets built with FEATURES; switch on only for a new frozen protocol.
LAG_FEATURES = ["own_prev", "own_prev_l3", "sal_delta"]
SKILL = ("QB", "RB", "WR", "TE")
LOW_PCT, CHALK_PCT = 5.0, 20.0


def norm(s: object) -> str:
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(s).lower())
    return re.sub(r"[^a-z]", "", s)


def add_features(x: pd.DataFrame, slate_cols: list[str]) -> pd.DataFrame:
    """Within-slate, within-position ranks and value; `x` needs pos, salary, proj, proj_p90,
    implied_team_total."""
    x = x.copy()
    x["value"] = x.proj / (x.salary / 1000.0)
    g = x.groupby(slate_cols + ["pos"])
    x["proj_rank"] = g.proj.rank(ascending=False)
    x["value_rank"] = g.value.rank(ascending=False)
    x["sal_rank"] = g.salary.rank(ascending=False)
    x["value_z"] = (x.value - g.value.transform("mean")) / g.value.transform("std")
    x["pos_c"] = x.pos.map({"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}).astype(float)
    return x


def set_shares(hist: pd.DataFrame) -> tuple[float, float]:
    """Mean per-slate fraction of all players at >= CHALK_PCT, and of skill players under LOW_PCT."""
    rows = []
    for _, s in hist.groupby(["season", "week"]):
        sk = s[s.pos.isin(SKILL)]
        rows.append(((s.own >= CHALK_PCT).mean(), (sk.own < LOW_PCT).mean()))
    a = np.array(rows)
    return float(a[:, 0].mean()), float(a[:, 1].mean())


def assign_sets(pred: pd.DataFrame, chalk_share: float, low_share: float) -> pd.DataFrame:
    """Rank-defined sets. `pred` needs pos and pred_own. CHALK: top round(chalk_share*n) of all players;
    LOW: bottom round(low_share*n_skill) of skill players; the rest MID. Ties break by input order."""
    out = pred.copy()
    out["pred_rank"] = out.pred_own.rank(ascending=False, method="first").astype(int)
    n_chalk = max(1, int(round(chalk_share * len(out))))
    skill = out.pos.isin(SKILL)
    n_low = int(round(low_share * int(skill.sum())))
    out["set"] = "MID"
    out.loc[out.pred_rank <= n_chalk, "set"] = "CHALK"
    low_idx = out[skill].sort_values("pred_own", kind="stable").index[:n_low]
    out.loc[low_idx, "set"] = "LOW"
    return out


def stable_order(spf: pd.DataFrame) -> pd.DataFrame:
    """BigQuery returns rows in no fixed order, and 78 name keys of the 2022-25 panel map to more than one row, so an
    unsorted drop_duplicates (and LightGBM's row order) made the sets depend on the query's row order (found 2026-09-24:
    a rebuild of L02's walk-forward sets differed in 266 labels). Sort on every column first."""
    cols = [c for c in ("season", "week", "key", "gsis_id", "id", "salary", "proj", "name") if c in spf.columns]
    return spf.sort_values(cols, na_position="last", kind="stable").reset_index(drop=True)


def training_frame(query_df, project: str) -> pd.DataFrame:
    own = query_df(f"""
        WITH c AS (
          SELECT season, week, contest_id, ANY_VALUE(contest_name) nm,
                 SAFE_CAST(REGEXP_EXTRACT(ANY_VALUE(contest_name), r"\\[(\\d+) entries") AS INT64) ent
          FROM `{project}.nfl_raw.contest_ownership` WHERE season BETWEEN 2022 AND 2025 GROUP BY 1,2,3),
        pick AS (
          SELECT season, week, ARRAY_AGG(STRUCT(contest_id, ent) ORDER BY ent DESC LIMIT 1)[OFFSET(0)] AS p
          FROM c WHERE REGEXP_CONTAINS(nm, r"Fantasy Football Millionaire")
            AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555") GROUP BY 1,2)
        SELECT o.season, o.week, o.display_name, MAX(o.pct_drafted) pct
        FROM `{project}.nfl_raw.contest_ownership` o
        JOIN pick ON o.season = pick.season AND o.week = pick.week AND o.contest_id = pick.p.contest_id
        GROUP BY 1,2,3""")
    own["key"] = own.display_name.map(norm)
    own = own.groupby(["season", "week", "key"], as_index=False).pct.max()
    spf = query_df(f"""
        SELECT season, week, id, gsis_id, name, team, pos, salary, mean_projection AS proj, proj_p90, implied_team_total
        FROM `{project}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = "{PANEL}" AND season BETWEEN 2022 AND 2025""")
    spf["key"] = spf.name.map(norm)
    spf = stable_order(spf)
    d = spf[spf.salary.notna() & spf.proj.notna()].drop_duplicates(["season", "week", "key"])
    have = set(map(tuple, own[["season", "week"]].drop_duplicates().to_numpy()))
    d = d[[(s, w) in have for s, w in zip(d.season, d.week)]]
    d = d.merge(own, on=["season", "week", "key"], how="left")
    d["own"] = d.pct.fillna(0.0)
    d = add_lag_features(d)
    return add_features(d, ["season", "week"])


def lag_lookup(history: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """The lag inputs for each target row, by CALENDAR week (2026-09-23 alignment; one definition for training and live).

    history: one row per (key, season, week) the player was ON that week's main slate, with `own` (his Millionaire
    ownership there, 0 when he was on the slate but absent from the ownership file) and `salary`.
    targets: rows with key, season, week (and salary for sal_delta).
    own_prev = own at week - 1 (NaN if he was not on that slate); own_prev_l3 = mean own over the weeks week-3..week-1
    he was on (NaN if none); sal_delta = salary - salary at week - 1 (NaN if not on that slate)."""
    h = history.groupby(["key", "season", "week"], as_index=True)[["own", "salary"]].mean()
    t = pd.MultiIndex.from_frame(targets[["key", "season", "week"]].astype({"season": int, "week": int}))
    prev = [h.reindex(pd.MultiIndex.from_arrays([t.get_level_values(0), t.get_level_values(1), t.get_level_values(2) - k]))
            for k in (1, 2, 3)]
    out = pd.DataFrame(index=targets.index)
    out["own_prev"] = prev[0].own.to_numpy()
    win = np.column_stack([p.own.to_numpy(dtype=float) for p in prev]).reshape(len(targets), 3)
    cnt = np.isfinite(win).sum(axis=1)
    out["own_prev_l3"] = np.where(cnt > 0, np.nansum(win, axis=1) / np.maximum(cnt, 1), np.nan)
    out["sal_delta"] = pd.to_numeric(targets.salary, errors="coerce").to_numpy(dtype=float) - prev[0].salary.to_numpy(dtype=float)
    return out


def add_lag_features(d: pd.DataFrame) -> pd.DataFrame:
    """Training lag inputs: every panel row is a player on that week's main slate, with own = pct.fillna(0), so the
    panel itself is the history (calendar week - 1, never 'the previous row'). Row order is untouched."""
    d = d.copy()
    lag = lag_lookup(d[["key", "season", "week", "own", "salary"]], d)
    for c in LAG_FEATURES:
        d[c] = lag[c]
    return d


def fit(train: pd.DataFrame, features: list[str] | None = None):
    import lightgbm as lgb
    f = FEATURES if features is None else features
    m = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=40,
                          verbose=-1, random_state=20260922).fit(train[f], np.log(train.own + 0.1))
    m.feature_list_ = list(f)
    return m


def predict(model, x: pd.DataFrame) -> np.ndarray:
    return np.exp(model.predict(x[getattr(model, "feature_list_", FEATURES)])) - 0.1


def validate(d: pd.DataFrame, features: list[str] | None = None) -> dict[int, float]:
    from scipy.stats import spearmanr
    out = {}
    for y in (2023, 2024, 2025):
        m = fit(d[d.season < y], features)
        te = d[d.season == y].copy()
        te["pred"] = predict(m, te)
        r = [spearmanr(g.pred, g.own).statistic for _, g in te[te.proj >= 3].groupby("week")]
        out[y] = float(np.mean(r))
    return out


def slate_frame(query_df, settings, week: int, group: int) -> pd.DataFrame:
    """The Sunday-main slate's served projections (latest generation) with the implied team total."""
    x = query_df(f"""
        WITH latest AS (SELECT MAX(pulled_at) ts FROM `{settings.raw}.dk_salaries`
                        WHERE draft_group_id = {int(group)}),
        slate AS (SELECT DISTINCT dk_player_id FROM `{settings.raw}.dk_salaries`, latest
                  WHERE draft_group_id = {int(group)} AND pulled_at = latest.ts),
        proj AS (SELECT * FROM `{settings.predictions}.player_projections_current` WHERE week = {int(week)})
        SELECT p.gsis_id, p.dk_player_id, p.display_name, p.position AS pos, p.team, p.salary,
               p.proj_points AS proj, p.proj_p90, f.implied_team_total
        FROM proj p JOIN slate s ON CAST(p.dk_player_id AS STRING) = CAST(s.dk_player_id AS STRING)
        LEFT JOIN `{settings.features}.player_week_inference` f
          ON f.gsis_id = p.gsis_id AND f.week = {int(week)}""")
    if x.empty:
        raise SystemExit(f"no served projections for week {week} on draft group {group}; "
                         "run the projection refresh first")
    x["slate"] = int(group)
    return add_features(x, ["slate"])


def main_slate_players(query_df, settings, season: int, week: int) -> pd.DataFrame:
    """(dk_player_id, display_name, salary) of a PAST week's Sunday main slate: the largest all-Sunday classic draft group
    on that week's Sunday (tail_shadow.sunday_main_group's rule), latest pull per player. dk_salaries.week is NULL for
    2026, so the week's Sunday comes from the schedule."""
    from nfl_dfs.inference.tail_shadow import sunday_main_group
    sun = query_df(f"""SELECT DISTINCT PARSE_DATE('%Y-%m-%d', gameday) d FROM `{settings.raw}.schedules`
                       WHERE season = {int(season)} AND week = {int(week)} AND game_type = 'REG' AND weekday = 'Sunday'""")
    if sun.empty:
        return pd.DataFrame(columns=["dk_player_id", "display_name", "salary"])
    sunday = pd.to_datetime(sun.d.iloc[0]).date()
    rows = query_df(f"""
        SELECT draft_group_id, CAST(dk_player_id AS STRING) dk_player_id, display_name, team_abbr, salary, game_start, pulled_at
        FROM `{settings.raw}.dk_salaries`
        WHERE CAST(season AS INT64) = {int(season)} AND slate_type = 'classic'
          AND DATE(game_start, 'America/New_York') = DATE('{sunday.isoformat()}')""")
    if rows.empty:
        return pd.DataFrame(columns=["dk_player_id", "display_name", "salary"])
    groups = rows.groupby(["draft_group_id", "game_start"]).agg(teams=("team_abbr", "nunique"),
                                                               players=("dk_player_id", "nunique")).reset_index()
    # a group is all-Sunday only if none of its rows fall on another day; rows on other days were filtered out above,
    # so drop groups that also carry players on other dates
    other = query_df(f"""SELECT DISTINCT draft_group_id FROM `{settings.raw}.dk_salaries`
                         WHERE draft_group_id IN ({", ".join(str(int(g)) for g in groups.draft_group_id.unique())})
                           AND DATE(game_start, 'America/New_York') != DATE('{sunday.isoformat()}')""")
    groups = groups[~groups.draft_group_id.isin(set(other.draft_group_id))]
    gid = sunday_main_group(groups, sunday)
    g = rows[rows.draft_group_id == gid].sort_values("pulled_at").groupby("dk_player_id").tail(1)
    return g[["dk_player_id", "display_name", "salary"]].reset_index(drop=True)


def live_lag_features(query_df, settings, x: pd.DataFrame, season: int, week: int) -> pd.DataFrame:
    """Lag inputs for a live slate with the TRAINING definition (lag_lookup): for each of the three prior weeks, the
    players on that week's main slate, with their Sunday-Millionaire ownership (2026 rows are one per roster SLOT, so
    ownership is SUMMED per player) or 0 when on the slate but absent from the file; NaN for a player not on it."""
    own = query_df(f"""
        WITH c AS (SELECT week, contest_id, ANY_VALUE(contest_name) nm, COUNT(*) n
                   FROM `{settings.raw}.contest_ownership` WHERE season = {int(season)} AND week < {int(week)}
                   GROUP BY 1, 2),
        pick AS (SELECT week, ARRAY_AGG(contest_id ORDER BY n DESC LIMIT 1)[OFFSET(0)] cid FROM c
                 WHERE REGEXP_CONTAINS(nm, r"Millionaire") AND NOT REGEXP_CONTAINS(nm, r"\\(Thu\\)|MEGA|\\$555")
                 GROUP BY 1),
        slots AS (SELECT o.week, o.display_name, o.roster_position, ANY_VALUE(o.pct_drafted) p
                  FROM `{settings.raw}.contest_ownership` o JOIN pick ON o.week = pick.week AND o.contest_id = pick.cid
                  WHERE o.season = {int(season)} GROUP BY 1, 2, 3)
        SELECT week, display_name, SUM(p) own FROM slots GROUP BY 1, 2""")
    if len(own):
        own["key"] = own.display_name.map(norm)
    hist = []
    for k in (1, 2, 3):
        wk = int(week) - k
        if wk < 1:
            continue
        on = main_slate_players(query_df, settings, season, wk)
        if on.empty:
            continue                      # no main-slate record that week: every player is NaN for it, as in training
        on = on.assign(key=on.display_name.map(norm), season=int(season), week=wk)
        pct = own[own.week == wk].groupby("key").own.sum() if len(own) else pd.Series(dtype=float)
        if pct.empty:
            continue                      # no ownership file that week: unknown, not 0
        on["own"] = on.key.map(pct).fillna(0.0)
        hist.append(on[["key", "season", "week", "own", "salary"]])
    x = x.copy()
    x["key"] = x.display_name.map(norm)
    tgt = x.assign(season=int(season), week=int(week))
    if hist:
        lag = lag_lookup(pd.concat(hist, ignore_index=True), tgt)
        for c in LAG_FEATURES:
            x[c] = lag[c]
    else:
        for c in LAG_FEATURES:
            x[c] = np.nan
    return x


def replay_frame(query_df, project: str, seasons: list[int]) -> pd.DataFrame:
    """Every player of each replay slate, deduplicated on gsis_id -- NOT the name key training uses: the panel table
    has players with no name (minimum-salary fringe rows), and a name-key dedup collapses all of them into one row,
    which would leave the sets file unable to cover the slate (the sleeve's loader fails closed on that)."""
    spf = query_df(f"""
        SELECT season, week, id, gsis_id, name, team, pos, salary, mean_projection AS proj, proj_p90, implied_team_total
        FROM `{project}.nfl_predictions.slate_player_features`
        WHERE panel_run_id = "{PANEL}" AND season IN ({", ".join(str(int(v)) for v in seasons)})""")
    spf = stable_order(spf)
    x = spf[spf.salary.notna() & spf.proj.notna() & spf.gsis_id.notna()].drop_duplicates(["season", "week", "gsis_id"])
    return add_features(x, ["season", "week"])


def replay_lag_features(pred_frame: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Lag inputs for replay prediction rows (L05, 2026-09-24): the training panel `d` is the history, exactly as in
    training (add_lag_features), keyed by the same name key; weeks W-1..W-3 only, so a W row sees no week >= W.
    Nameless fringe rows get NaN lags rather than the panel's one nameless history row."""
    x = pred_frame.copy()
    named = x.name.notna() & (x.name.astype(str).str.strip() != "")
    x["key"] = x.name.map(norm)
    lag = lag_lookup(d[["key", "season", "week", "own", "salary"]], x)
    for c in LAG_FEATURES:
        x[c] = lag[c].where(named)
    return x


def replay_sets(d: pd.DataFrame, seasons: list[int], out_dir: Path, pred_frame: pd.DataFrame | None = None,
                features: list[str] | None = None) -> list[dict]:
    """Walk-forward historical sets for the replay panel (laptop, 2026-09-22): for season S the model AND the rank-rule
    shares are fit on seasons < S only (training frame `d`, unchanged), then every S slate that has Millionaire
    ownership in `d` is predicted from its pre-lock inputs in `pred_frame` (all players; see replay_frame).
    One file per slate, the live schema plus the lab's frame `id`, keyed by gsis_id so nfl2 frames join."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_frame = d if pred_frame is None else pred_frame
    receipts = []
    for season in seasons:
        train = d[d.season < season]
        if train.empty:
            raise SystemExit(f"no seasons before {season} to fit on; walk-forward sets need a prior fold")
        chalk_share, low_share = set_shares(train)
        model = fit(train, features)
        matched = set(d[d.season == season].week.unique())
        for week, x in pred_frame[(pred_frame.season == season) & pred_frame.week.isin(matched)].groupby("week"):
            x = x.copy(); x["pred_own"] = predict(model, x)
            sets = assign_sets(x, chalk_share, low_share)
            f = out_dir / f"{season}-w{int(week):02d}.csv"
            cols = ["gsis_id", "id", "name", "pos", "team", "salary", "proj", "pred_own", "pred_rank", "set"]
            sets[cols].sort_values("pred_rank").rename(columns={"name": "display_name"}).to_csv(f, index=False)
            receipts.append({"season": season, "week": int(week), "file": str(f), "players": len(sets),
                             "chalk": int((sets.set == "CHALK").sum()), "low": int((sets.set == "LOW").sum()),
                             "fit_seasons": sorted(int(v) for v in train.season.unique())})
    return receipts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["validate", "sets", "replay-sets"])
    ap.add_argument("--seasons", default="2023,2024")
    ap.add_argument("--week", type=int)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--group", type=int)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--min-spearman", type=float, default=0.70)
    ap.add_argument("--lag-features", action="store_true",
                    help="add last week's ownership and salary change (NOT for sets feeding the frozen L02 panel)")
    a = ap.parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings
    d = training_frame(query_df, settings.project)
    feats = FEATURES + LAG_FEATURES if a.lag_features else FEATURES
    val = validate(d, feats)
    print("walk-forward within-slate Spearman:", {k: round(v, 3) for k, v in val.items()})
    if min(val.values()) < a.min_spearman:
        raise SystemExit(f"ownership model below the {a.min_spearman} gate on history; refusing to write sets")
    if a.mode == "validate":
        return
    if a.mode == "replay-sets":
        if not a.out:
            raise SystemExit("replay-sets needs --out DIR")
        seasons = [int(v) for v in a.seasons.split(",")]
        pred = replay_frame(query_df, settings.project, seasons)
        if a.lag_features:
            pred = replay_lag_features(pred, d)
        recs = replay_sets(d, seasons, a.out, pred_frame=pred, features=feats)
        import json
        (a.out / "receipt.json").write_text(json.dumps({"panel": PANEL, "features": feats, "validation": val,
                                                        "slates": recs}, indent=1))
        print(f"wrote {len(recs)} slate files to {a.out}")
        return
    if not (a.week and a.group and a.out):
        raise SystemExit("sets needs --week, --group and --out")
    chalk_share, low_share = set_shares(d)
    x = slate_frame(query_df, settings, a.week, a.group)
    # the live slate too: assign_sets breaks rank ties by input order, and BigQuery's row order is not fixed
    x = x.sort_values([c for c in ("dk_player_id", "gsis_id", "name") if c in x.columns], kind="stable").reset_index(drop=True)
    if a.lag_features:
        x = live_lag_features(query_df, settings, x, a.season, a.week)
    x["pred_own"] = predict(fit(d, feats), x)
    s = assign_sets(x, chalk_share, low_share)
    cols = ["gsis_id", "dk_player_id", "display_name", "pos", "team", "salary", "proj", "pred_own",
            "pred_rank", "set"]
    a.out.parent.mkdir(parents=True, exist_ok=True)
    s[cols].sort_values("pred_rank").to_csv(a.out, index=False)
    print(f"wrote {a.out}: {len(s)} players; CHALK {int((s.set == 'CHALK').sum())} "
          f"(share {chalk_share:.3f}), LOW {int((s.set == 'LOW').sum())} skill (share {low_share:.3f})")


if __name__ == "__main__":
    sys.exit(main())
