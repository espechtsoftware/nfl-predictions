"""Causal vacated-opportunity study (research round 9).

Event-study/DiD on 2019-2025: treatment = team-week where a target hog
(trailing target_share_l4 >= 0.18 in his last played week) is ABSENT
(no panel row while the team plays). Outcome = teammate actual target
share minus his own trailing expectation (target_share_l4). Uplift =
treated mean delta minus control mean delta (no-absence team-weeks),
per (teammate position x depth bucket). Same for carry hogs/shares.
Answers: WHO captures vacated opportunity, and how unevenly — vs the
team-level-sum assumption of team_vacated_target_share (018).
"""
import numpy as np
import pandas as pd

S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/92fae70e-759c-4586-8c83-323b1b737e75/scratchpad"
df = pd.read_parquet(f"{S}/panel.parquet")
df = df[df.position.isin(["QB", "RB", "WR", "TE"])].copy()
for c in ("y_targets", "target_share_l4", "y_carries", "carry_share_l4",
          "depth_rank"):
    df[c] = pd.to_numeric(df[c], errors="coerce")

# actual weekly shares from realized counts
tw = df.groupby(["team", "season", "week"]).agg(
    tot_tgt=("y_targets", "sum"), tot_car=("y_carries", "sum")).reset_index()
df = df.merge(tw, on=["team", "season", "week"])
df["act_tgt_share"] = df.y_targets / df.tot_tgt.clip(lower=1)
df["act_car_share"] = df.y_carries / df.tot_car.clip(lower=1)
df["d_tgt"] = df.act_tgt_share - df.target_share_l4
df["d_car"] = df.act_car_share - df.carry_share_l4

# detect absences: last played week per player vs team weeks played
played = df[["gsis_id", "position", "team", "season", "week",
             "target_share_l4", "carry_share_l4"]].copy()
team_weeks = df[["team", "season", "week"]].drop_duplicates()

# for each player-season: the set of weeks with rows; absence = team week
# after his first appearance and before his last+3 (mid-season gap) with
# no row and his prior trailing share over the hog threshold
rows = []
for (gid, season), g in played.groupby(["gsis_id", "season"]):
    wks = sorted(g.week)
    if len(wks) < 3:
        continue
    team_by_week = dict(zip(g.week, g.team))
    share_by_week = dict(zip(g.week, g.target_share_l4))
    cshare_by_week = dict(zip(g.week, g.carry_share_l4))
    for w in range(wks[0] + 1, wks[-1] + 1):
        if w in wks:
            continue
        prior = max(x for x in wks if x < w)
        team = team_by_week[prior]
        rows.append({"gsis_id": gid, "season": season, "week": w,
                     "team": team,
                     "prior_tgt_share": share_by_week.get(prior, np.nan),
                     "prior_car_share": cshare_by_week.get(prior, np.nan)})
ab = pd.DataFrame(rows).merge(team_weeks, on=["team", "season", "week"])
tgt_hogs = ab[ab.prior_tgt_share >= 0.18]
car_hogs = ab[ab.prior_car_share >= 0.35]
print(f"absence events: tgt-hog {len(tgt_hogs)}  car-hog {len(car_hogs)}")

df["depth_b"] = df.depth_rank.fillna(3).clip(1, 3).astype(int)


def uplift(hogs, delta_col):
    key = ["team", "season", "week"]
    treated_wk = hogs[key].drop_duplicates().assign(treated=1)
    d = df.merge(treated_wk, on=key, how="left")
    d["treated"] = d.treated.fillna(0).astype(int)
    # exclude the absent players themselves (they have no row anyway)
    out = []
    for (pos, depth), g in d.groupby(["position", "depth_b"]):
        t, c = g[g.treated == 1][delta_col].dropna(), g[g.treated == 0][delta_col].dropna()
        if len(t) < 30:
            continue
        up = t.mean() - c.mean()
        se = np.sqrt(t.var() / len(t) + c.var() / len(c))
        out.append({"pos": pos, "depth": depth, "n_treated": len(t),
                    "uplift_sharepts": round(100 * up, 2),
                    "t_stat": round(up / se, 1)})
    return pd.DataFrame(out).sort_values("uplift_sharepts", ascending=False)


print("\n=== TARGET-HOG ABSENT (>=18% trailing share): who captures? ===")
print(uplift(tgt_hogs, "d_tgt").to_string(index=False))
print("\n=== CARRY-HOG ABSENT (>=35% trailing carry share) ===")
print(uplift(car_hogs, "d_car").to_string(index=False))

# capture accounting: does the vacated share get fully redistributed?
key = ["team", "season", "week"]
vac = tgt_hogs.groupby(key).prior_tgt_share.sum().rename("vacated")
tot = df.merge(vac.reset_index(), on=key).groupby(key).agg(
    vacated=("vacated", "first"), captured=("d_tgt", "sum"))
print(f"\nvacated tgt share per treated week: mean {100*tot.vacated.mean():.1f} "
      f"sharepts; teammates' summed delta: {100*tot.captured.mean():.1f}")
print("CAUSAL_DONE", flush=True)
