"""Workstream C dependence gate (scoring plan §9.4): does the Schaake
copula reproduce real joint behaviour better than the current
simulator, WITHOUT degrading marginals?

Three arms on a held-out season (plan §9.3):
  1. current simulator copula (control)
  2. unconditional historical templates
  3. similarity-conditioned templates

Screen (the production replay performs the proper realized variogram gate):
  - role-pair correlation closer to realized
  - marginal means/quantiles unchanged within tolerance
Failure here stops the workstream — no candidate or panel compute.

  python scripts/schaake_gate.py [--season 2025] [--sims 2000]
"""
import argparse
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.research.schaake import (apply_schaake_game,  # noqa: E402
                                      build_game_bank, match_templates)

ROLE_PAIRS = (("QB", "WR1", "same"), ("QB", "WR2", "same"),
              ("QB", "QB", "opp"), ("WR1", "WR2", "same"),
              ("RB1", "DST", "same"))


def load_games(seasons):
    s = ",".join(map(str, seasons))
    return query_df(f"""
      WITH base AS (
        SELECT a.season, a.week, a.gsis_id, a.dk_points,
               u.position AS pos, u.team, s.salary,
               sc.game_id, sc.total_line AS game_total,
               ABS(sc.spread_line) AS spread_abs,
               NULL AS pace_env_l6, NULL AS neutral_pass_rate_l6,
               NULL AS team_top2_target_share_l6
        FROM `nfl_features.player_week_actuals` a
        JOIN `nfl_features.player_week_usage` u USING (gsis_id, season, week)
        JOIN `nfl_features.dk_salary_week` s USING (gsis_id, season, week)
        JOIN `nfl_raw.schedules` sc
          ON sc.season = a.season AND sc.week = a.week
         AND (sc.home_team = u.team OR sc.away_team = u.team)
        WHERE a.season IN ({s}) AND a.week <= 18
          AND u.position IN ('QB','RB','WR','TE')
          AND sc.total_line IS NOT NULL)
      SELECT * FROM base""")


def add_roles(df):
    df = df.copy()
    df["role"] = None
    for (se, wk, tm, pos), g in df.groupby(["season", "week", "team", "pos"]):
        order = g.salary.rank(ascending=False, method="first")
        for idx, k in order.items():
            k = int(k)
            if pos == "QB" and k == 1:
                df.at[idx, "role"] = "QB"
            elif pos in ("RB", "WR") and k <= 3:
                df.at[idx, "role"] = f"{pos}{k}"
            elif pos == "TE" and k == 1:
                df.at[idx, "role"] = "TE1"
    return df


def realized_pairs(df):
    """Observed correlation per role pair (the target to match)."""
    out = {}
    for a, b, rel in ROLE_PAIRS:
        xs, ys = [], []
        for (se, wk, gid), g in df.groupby(["season", "week", "game_id"]):
            teams = g.team.unique()
            if rel == "same":
                for t in teams:
                    ga = g[(g.team == t) & (g.role == a)]
                    gb = g[(g.team == t) & (g.role == b)]
                    if len(ga) and len(gb) and not (a == b):
                        xs.append(ga.dk_points.iloc[0])
                        ys.append(gb.dk_points.iloc[0])
            elif rel == "opp" and len(teams) == 2:
                ga = g[(g.team == teams[0]) & (g.role == a)]
                gb = g[(g.team == teams[1]) & (g.role == b)]
                if len(ga) and len(gb):
                    xs.append(ga.dk_points.iloc[0])
                    ys.append(gb.dk_points.iloc[0])
        out[f"{a}-{b}-{rel}"] = (np.corrcoef(xs, ys)[0, 1]
                                 if len(xs) > 30 else np.nan)
    return out


def sim_pairs(draws, meta):
    """Same statistic computed on simulated draws."""
    out = {}
    for a, b, rel in ROLE_PAIRS:
        cs = []
        for (se, wk, gid), g in meta.groupby(["season", "week", "game_id"]):
            teams = g.team.unique()
            pairs = []
            if rel == "same":
                for t in teams:
                    ia = g[(g.team == t) & (g.role == a)].index
                    ib = g[(g.team == t) & (g.role == b)].index
                    if len(ia) and len(ib) and a != b:
                        pairs.append((ia[0], ib[0]))
            elif rel == "opp" and len(teams) == 2:
                ia = g[(g.team == teams[0]) & (g.role == a)].index
                ib = g[(g.team == teams[1]) & (g.role == b)].index
                if len(ia) and len(ib):
                    pairs.append((ia[0], ib[0]))
            for i, j in pairs:
                x, y = draws[i], draws[j]
                if x.std() > 0 and y.std() > 0:
                    cs.append(np.corrcoef(x, y)[0, 1])
        out[f"{a}-{b}-{rel}"] = float(np.mean(cs)) if cs else np.nan
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--sims", type=int, default=2000)
    ap.add_argument("--k", type=int, default=40)
    a = ap.parse_args()

    hist_seasons = [s for s in (2019, 2021, 2022, 2023, 2024) if s < a.season]
    df = add_roles(load_games(hist_seasons + [a.season]))
    hist = df[df.season != a.season]
    test = df[df.season == a.season].reset_index(drop=True)
    print(f"bank from {len(hist):,} player-weeks; held-out {a.season}: "
          f"{len(test):,}")

    bank = build_game_bank(hist)
    print(f"template bank: {len(bank):,} GAME units")

    # marginals: lognormal draws matched to each player's realized mean
    rng = np.random.default_rng(7)
    mu = test.dk_points.clip(lower=0.1).to_numpy()
    sd = np.maximum(mu * 0.85, 2.0)
    sig = np.sqrt(np.log1p((sd / np.maximum(mu, 0.1)) ** 2))
    base = rng.lognormal(
        (np.log(np.maximum(mu, 0.1)) - sig ** 2 / 2)[:, None],
        sig[:, None], size=(len(test), a.sims))

    real = realized_pairs(test)
    arms = {"control (independent marginals)": base}

    uncond = bank.sample(min(a.k * 5, len(bank)), random_state=1)
    unc_out = base.copy()
    for (wk, gid), g in test.groupby(["week", "game_id"]):
        idx = g.index.to_numpy()
        unc_out[idx] = apply_schaake_game(
            base[idx], test.role.iloc[idx], test.team.iloc[idx].to_numpy(),
            uncond, seed=int(wk))
    arms["unconditional templates"] = unc_out

    # similarity-conditioned: match per (season, week) context
    cond_out = base.copy()
    for (wk, gid), g in test.groupby(["week", "game_id"]):
        ctx = {"game_total": g.game_total.iloc[0],
               "spread_abs": g.spread_abs.iloc[0],
               "pace_env_l6": np.nan,
               "neutral_pass_rate_l6": np.nan,
               "team_top2_target_share_l6": np.nan}
        t = match_templates(bank, ctx, a.season, int(wk), k=a.k)
        if t.empty:
            continue
        idx = g.index.to_numpy()
        cond_out[idx] = apply_schaake_game(
            base[idx], test.role.iloc[idx], test.team.iloc[idx].to_numpy(),
            t, seed=int(wk))
    arms["similarity-conditioned"] = cond_out

    print("\nrole-pair correlation (realized vs simulated):")
    hdr = f"{'pair':<18}{'realized':>10}" + "".join(
        f"{k[:14]:>16}" for k in arms)
    print(hdr)
    scores = {k: 0.0 for k in arms}
    for pair in real:
        row = f"{pair:<18}{real[pair]:>10.3f}"
        for k, dr in arms.items():
            sp = sim_pairs(dr, test)[pair]
            row += f"{sp:>16.3f}"
            if np.isfinite(real[pair]) and np.isfinite(sp):
                scores[k] += abs(sp - real[pair])
        print(row)
    print(f"\n{'TOTAL |error| (lower better)':<28}" + "".join(
        f"{scores[k]:>16.3f}" for k in arms))

    print("\nmarginal preservation (must be exact per player):")
    for k, dr in arms.items():
        exact = all(np.array_equal(np.sort(base[i]), np.sort(dr[i]))
                    for i in range(len(base)))
        print(f"  {k:<32} exact={exact} mean {dr.mean():7.3f}  p90 "
              f"{np.percentile(dr, 90):7.3f}")

    best = min(scores, key=scores.get)
    ctrl = "control (independent marginals)"
    print(f"\nGATE: best arm = {best}")
    if best == ctrl:
        print("  RESULT: FAIL — no template arm beats the control; "
              "workstream C stops here (no panel compute).")
    else:
        print(f"  RESULT: PASS on dependence "
              f"({scores[best]:.3f} vs control {scores[ctrl]:.3f}) — "
              "proceed to candidate-oracle evaluation.")


if __name__ == "__main__":
    main()
