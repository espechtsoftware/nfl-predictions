"""Q11 part 3 (production, 2026-09-30): week-to-week variation of heavy users (>= 20 Millionaire entries in two or more
of W1-W3). Per user-week: the F2 anatomy (exposure of the top 1 / top 3 players, players at >= 25%, distinct players,
distinct QBs, the modal QB's share, mean pairwise overlap, share of pairs sharing >= 6) plus the chalk level (mean
REALIZED Millionaire ownership sum, known at lock) and the finish (mean percentile). For each pair of weeks: the
Spearman across users of each statistic, week A vs week B -- is a user's profile a stable target? -- for all heavy
users and for the persistent ones (top 20% of heavy users by mean finish in BOTH weeks). Player carryover: for players
on both weeks' Millionaire lists, Spearman of a user's exposure week A vs week B, against the same user's week-B
exposure vs the FIELD's week-A ownership (how much of the carryover is the user's own taste rather than shared chalk).
Prints aggregates only (no user names)."""
import itertools, json, os
import numpy as np, pandas as pd
from scipy.stats import spearmanr
os.environ.setdefault("OMP_NUM_THREADS", "1")
Q = os.path.expanduser("~/q11-study")
MILLY = {1: "193028206", 2: "195648007", 3: "195905122"}
STATS = ["exp_top1", "exp_top3", "n_ge25", "players_per_row", "n_qb_per_row", "qb_modal", "mean_overlap", "overlap_ge6", "own", "n"]


def main():
    d = pd.read_parquet(os.path.join(Q, "q11", "heavy_multiweek.parquet"))
    o = pd.read_csv(os.path.join(Q, "q", "B", "data", "contest_ownership_2026.csv"))
    pos = (o[o.roster_position != "FLEX"].groupby(["week", "display_name"]).roster_position.agg(lambda s: s.mode().iloc[0]))
    pos = {(int(w), n): p for (w, n), p in pos.items()}
    om = o[o.contest_id.astype(str).isin(MILLY.values())]
    own = {(int(w), n): p for (w, n), p in om.groupby(["week", "display_name"]).pct_drafted.sum().items()}
    d["pl"] = d.players_key.map(lambda s: s.split("|"))
    rows, expo = [], {}
    for (w, u), g in d.groupby(["week", "user"], sort=False):
        n = len(g); sets = [frozenset(x) for x in g.pl]
        cnt = pd.Series([p for s in sets for p in s]).value_counts() / n
        qbs = pd.Series([p for s in sets for p in s if pos.get((w, p)) == "QB"]).value_counts() / n
        pairs = np.array([len(a & b) for a, b in itertools.combinations(sets[:150], 2)])
        rows.append(dict(week=w, user=u, n=n, exp_top1=float(cnt.iloc[0]), exp_top3=float(cnt.iloc[:3].mean()), n_ge25=int((cnt >= .25).sum()),
                         players_per_row=len(cnt) / n, n_qb_per_row=len(qbs) / n, qb_modal=float(qbs.iloc[0]) if len(qbs) else np.nan,
                         mean_overlap=float(pairs.mean()), overlap_ge6=float((pairs >= 6).mean()),
                         own=float(np.mean([sum(own.get((w, p), 0.0) for p in s) for s in sets])),
                         pct=float((g["rank"] / g.n_field).mean() * 100)))
        expo[(w, u)] = cnt
    U = pd.DataFrame(rows)
    U["top20"] = U.groupby("week").pct.transform(lambda x: x <= x.quantile(0.2))
    out = {"user_weeks": U.groupby("week").size().to_dict()}
    field_own = {w: pd.Series({n: p for (ww, n), p in own.items() if ww == w}) for w in (1, 2, 3)}
    for a, b in ((1, 2), (2, 3), (1, 3)):
        A = U[U.week == a].set_index("user"); B = U[U.week == b].set_index("user")
        common = A.index.intersection(B.index)
        pers = [u for u in common if A.at[u, "top20"] and B.at[u, "top20"]]
        res = {"users": int(len(common)), "n_persistent": int(len(pers))}
        for grp, us in (("all", common), ("persistent", pers)):
            res[grp] = {s: round(float(spearmanr(A.loc[us, s], B.loc[us, s], nan_policy="omit")[0]), 3) for s in STATS} if len(us) > 5 else None
            res[grp + "_median_abs_change"] = {s: round(float((A.loc[us, s] - B.loc[us, s]).abs().median()), 3) for s in STATS} if len(us) else None
        # player carryover
        both = field_own[a].index.intersection(field_own[b].index)
        own_rho, field_rho = [], []
        for u in common:
            ea = expo[(a, u)].reindex(both).fillna(0); eb = expo[(b, u)].reindex(both).fillna(0)
            m = (ea > 0) | (eb > 0)
            if m.sum() < 10:
                continue
            own_rho.append(spearmanr(ea[m], eb[m])[0]); field_rho.append(spearmanr(field_own[a].reindex(both)[m], eb[m])[0])
        res["players_on_both_lists"] = int(len(both))
        res["carryover_user_A_vs_user_B_median_rho"] = round(float(np.nanmedian(own_rho)), 3)
        res["carryover_fieldown_A_vs_user_B_median_rho"] = round(float(np.nanmedian(field_rho)), 3)
        res["share_users_own_taste_beats_field"] = round(float(np.nanmean(np.array(own_rho) > np.array(field_rho))), 3)
        out[f"W{a}->W{b}"] = res
    out["levels_by_week_persistent_vs_all"] = U.groupby(["week", "top20"])[STATS].median().round(3).reset_index().to_dict(orient="records")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
