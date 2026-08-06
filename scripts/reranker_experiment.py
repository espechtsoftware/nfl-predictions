"""Workstream A: decision-focused residual reranker (scoring plan §7).

ONE nested comparison, preregistered before any result is viewed:
  A0  incumbent selector (unchanged simulated totals)
  A1  structure/provenance only
  A2  A1 + market/model disagreement
  A3  A2 + ownership / quantile uncertainty (all historical features)
  A4  A3 with features SHUFFLED WITHIN SLATE (negative control)

Target (primary): continuous residual = actual_score - sim_mean.
Model: ridge (low capacity; 107 slates cannot support more).
CV: leave-one-season-out; slate is the unit; scaling fit on train only.
Integration (§7.6): DO NOT sort by residual. Apply the predicted
shift to candidate world totals, then rerun the UNCHANGED coverage
selector so world-level diversification is preserved.

  python scripts/reranker_experiment.py <panel_run_id>
"""
import io
import json
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.optimizer.lineup import select_from_support  # noqa: E402

N_ENTRIES = 40
LINE = 194.0
SHIFT_CAP = 15.0   # bounded correction (§7.6), fitted-fold agnostic
TAGS = ("boom", "lev", "dark", "game", "qbvar", "hyper", "gumbel",
        "thesis", "wild", "qd", "midqb", "nostk", "lowsal")

A1 = ["sim_mean", "sim_sd", "sim_q50", "sim_q90", "sim_q99", "p_line",
      "salary", "n_tags", "stack_mates", "bring_back", "max_from_game",
      "n_games", "salary_left"] + [f"tag_{t}" for t in TAGS]
A2 = A1 + ["div_abs_sum", "div_abs_max", "div_signed_sum", "div_qb",
           "div_stack_sum", "market_covered"]
A3 = A2 + ["own_sum", "own_max", "own_n_low", "own_n_high",
           "q_width_sum", "q_width_max"]


def load(panel):
    cand = query_df(f"""
        SELECT season, week, cand_ix, tag, all_tags, selected, sim_mean,
               sim_sd, sim_q50, sim_q90, sim_q99, p_line, salary,
               actual_score, n_worlds, players, score_artifact_uri,
               clear_bits_194
        FROM `{settings.predictions}.replay_candidates`
        WHERE panel_run_id = '{panel}' AND research_eligible""")
    feats = query_df(f"""
        SELECT season, week, id, pos, team, opp, game_id, salary AS p_salary,
               proj, own_est, consensus_div, market_points, model_points_pre,
               proj_p10, proj_p90
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = '{panel}'""")
    return cand, feats


def build_features(cand: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    """Candidate aggregates from the immutable player snapshot."""
    rows = []
    for (s, w), g in cand.groupby(["season", "week"]):
        fp = feats[(feats.season == s) & (feats.week == w)].set_index("id")
        cols = {c: fp[c].to_dict() for c in
                ("proj", "own_est", "consensus_div", "market_points",
                 "proj_p10", "proj_p90", "p_salary")}
        pos = fp["pos"].to_dict()
        team = fp["team"].to_dict()
        opp = fp["opp"].to_dict()
        game = fp["game_id"].to_dict()
        for _, c in g.iterrows():
            ids = [x for x in str(c.players).split(",") if x]
            gv = lambda k: np.array(  # noqa: E731
                [cols[k].get(i, np.nan) for i in ids], dtype=float)
            div, own = gv("consensus_div"), gv("own_est")
            p10, p90 = gv("proj_p10"), gv("proj_p90")
            mkt = gv("market_points")
            qb = [i for i in ids if pos.get(i) == "QB"]
            qt = team.get(qb[0]) if qb else None
            qo = opp.get(qb[0]) if qb else None
            mates = sum(1 for i in ids
                        if team.get(i) == qt and pos.get(i) in ("WR", "TE", "RB"))
            bring = sum(1 for i in ids if team.get(i) == qo)
            gids = [game.get(i) for i in ids if game.get(i)]
            gc = pd.Series(gids).value_counts() if gids else pd.Series(dtype=int)
            stack_div = np.nansum([cols["consensus_div"].get(i, np.nan)
                                   for i in ids if team.get(i) == qt])
            tags = json.loads(c.all_tags) if isinstance(c.all_tags, str) else []
            r = {
                "season": s, "week": w, "cand_ix": c.cand_ix,
                "selected": c.selected, "actual_score": c.actual_score,
                "sim_mean": c.sim_mean, "sim_sd": c.sim_sd,
                "sim_q50": c.sim_q50, "sim_q90": c.sim_q90,
                "sim_q99": c.sim_q99, "p_line": c.p_line,
                "salary": c.salary, "salary_left": 50000 - c.salary,
                "n_tags": len(tags),
                "stack_mates": mates, "bring_back": bring,
                "max_from_game": int(gc.iloc[0]) if len(gc) else 0,
                "n_games": int(len(gc)),
                "div_abs_sum": np.nansum(np.abs(div)),
                "div_abs_max": np.nanmax(np.abs(div)) if np.isfinite(div).any() else np.nan,
                "div_signed_sum": np.nansum(div),
                "div_qb": (cols["consensus_div"].get(qb[0], np.nan)
                           if qb else np.nan),
                "div_stack_sum": stack_div,
                "market_covered": float(np.isfinite(mkt).mean()),
                "own_sum": np.nansum(own),
                "own_max": np.nanmax(own) if np.isfinite(own).any() else np.nan,
                "own_n_low": int(np.nansum(own <= 0.05)),
                "own_n_high": int(np.nansum(own >= 0.20)),
                "q_width_sum": np.nansum(p90 - p10),
                "q_width_max": (np.nanmax(p90 - p10)
                                if np.isfinite(p90 - p10).any() else np.nan),
            }
            for t in TAGS:
                r[f"tag_{t}"] = int(t in tags)
            rows.append(r)
    return pd.DataFrame(rows)


def slate_totals(uri: str, client) -> np.ndarray:
    bkt, _, path = uri.replace("gs://", "").partition("/")
    payload = client.bucket(bkt).blob(path).download_as_bytes()
    return np.load(io.BytesIO(payload))["totals"]


def evaluate(X: pd.DataFrame, cand: pd.DataFrame, cols, shuffle=False,
             seed=0) -> pd.DataFrame:
    """LOSO: fit on other seasons, predict residuals, apply a bounded
    shift to world totals, rerun the unchanged coverage selector."""
    from google.cloud import storage
    client = storage.Client()
    rng = np.random.default_rng(seed)
    X = X.copy()
    X["resid"] = X.actual_score - X.sim_mean
    out = []
    for season in sorted(X.season.unique()):
        tr = X[X.season != season]
        te = X[X.season == season].copy()
        sc = StandardScaler().fit(tr[cols].fillna(0.0))
        m = Ridge(alpha=10.0).fit(sc.transform(tr[cols].fillna(0.0)),
                                  tr.resid)
        te_feats = te[cols].fillna(0.0)
        if shuffle:  # negative control: permute WITHIN slate
            te_feats = te_feats.copy()
            for _, idx in te.groupby(["season", "week"]).groups.items():
                perm = rng.permutation(len(idx))
                te_feats.loc[idx, :] = te_feats.loc[idx, :].to_numpy()[perm]
        te["pred"] = np.clip(m.predict(sc.transform(te_feats)),
                             -SHIFT_CAP, SHIFT_CAP)
        for (s, w), g in te.groupby(["season", "week"]):
            cg = cand[(cand.season == s) & (cand.week == w)].sort_values("cand_ix")
            uri = cg.score_artifact_uri.iloc[0]
            totals = slate_totals(uri, client)
            g = g.sort_values("cand_ix")
            shift = g.pred.to_numpy()[:, None]
            adj = totals[g.cand_ix.to_numpy()] + shift
            clears = adj >= LINE
            picked = select_from_support(clears, clears.mean(axis=1),
                                         adj.mean(axis=1), N_ENTRIES)
            sel = g.iloc[picked]
            out.append({"season": s, "week": w,
                        "best": sel.actual_score.max(),
                        "oracle": g.actual_score.max()})
    return pd.DataFrame(out)


def main():
    panel = sys.argv[1]
    cand, feats = load(panel)
    print(f"panel {panel}: {len(cand):,} candidates, {len(feats):,} player rows")
    X = build_features(cand, feats)
    print(f"feature frame: {X.shape}")

    base = cand[cand.selected].groupby(["season", "week"]).agg(
        best=("actual_score", "max")).reset_index()
    orc = cand.groupby(["season", "week"]).agg(
        oracle=("actual_score", "max")).reset_index()
    b = base.merge(orc, on=["season", "week"])
    print(f"\nA0 incumbent: clears {int((b.best>=194).sum())}/{len(b)}  "
          f"mean {b.best.mean():.1f}  regret {(b.oracle-b.best).mean():.1f}")

    res = [{"arm": "A0 incumbent", "clears": int((b.best >= 194).sum()),
            "mean_best": round(b.best.mean(), 1),
            "regret": round((b.oracle - b.best).mean(), 1),
            "seasons_better": "-"}]
    for name, cols, sh in (("A1 structure", A1, False),
                           ("A2 +disagreement", A2, False),
                           ("A3 +ownership/unc", A3, False),
                           ("A4 shuffled (control)", A3, True)):
        r = evaluate(X, cand, cols, shuffle=sh)
        mm = r.merge(b[["season", "week", "best"]], on=["season", "week"],
                     suffixes=("", "_base"))
        better = int((mm.groupby("season").apply(
            lambda g: (g.best >= 194).sum() - (g.best_base >= 194).sum(),
            include_groups=False) > 0).sum())
        res.append({"arm": name, "clears": int((r.best >= 194).sum()),
                    "mean_best": round(r.best.mean(), 1),
                    "regret": round((r.oracle - r.best).mean(), 1),
                    "seasons_better": better})
        print(f"{name}: clears {int((r.best>=194).sum())}  "
              f"mean {r.best.mean():.1f}  regret {(r.oracle-r.best).mean():.1f}")
    out = pd.DataFrame(res)
    print("\n" + "=" * 70)
    print(out.to_string(index=False))
    out.to_csv("/home/erich/nfl-panels/reranker_results.csv", index=False)
    print("\nadoption (§7.8): needs a preregistered arm beating A0 in >=4 "
          "seasons, no catastrophic season, and beating A4.")


if __name__ == "__main__":
    main()
