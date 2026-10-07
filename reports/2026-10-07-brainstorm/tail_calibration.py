"""Is the cheap edge a simulator tail miscalibration? W1-4 T-70 frames: each player's world draws (10,000, aligned to frame
rows) give P(points >= threshold); compare the summed probabilities with the realized counts (player_week_actuals), by salary
tier and position. Thresholds: absolute 20 / 25 / 30 DK points and value 4x / 5x salary-in-thousands. Aggregates only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
act = BQ.query("SELECT gsis_id, week, dk_points FROM `nfl_features.player_week_actuals` WHERE season = 2026 AND week BETWEEN 1 AND 4").to_dataframe()
snp = BQ.query("SELECT DISTINCT week, pfr_player_id, player, team, offense_snaps FROM `nfl_raw.snap_counts` WHERE season = 2026 AND game_type = 'REG' AND week BETWEEN 1 AND 4").to_dataframe()
R = []
for w in (1, 2, 3, 4):
    r = Path(CFG["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(r / "frame.parquet").reset_index(drop=True)
    for tag, fn in (("incumbent", "incumbent_player_scores.npy"), ("corrected", "corrected_hsim_player_scores.npy")):
        S = np.load(r / fn); assert S.shape[0] == len(fr), (w, tag, S.shape, len(fr))
        sal = fr.salary.astype(float).values[:, None] / 1000.0
        d = pd.DataFrame({"week": w, "src": tag, "row": np.arange(len(fr)), "dk_player_id": fr.dk_player_id.values, "gsis_id": fr.gsis_id.astype(str).values,
                          "pos": fr.pos.values, "salary": fr.salary.astype(float).values, "proj": pd.to_numeric(fr.mean_projection, errors="coerce").values,
                          "sim_mean": S.mean(1), "p20": (S >= 20).mean(1), "p25": (S >= 25).mean(1), "p30": (S >= 30).mean(1),
                          "pv4": (S >= 4 * sal).mean(1), "pv5": (S >= 5 * sal).mean(1), "p_2x": (S >= 2 * np.maximum(S.mean(1, keepdims=True), 1.0)).mean(1)})
        R.append(d)
D = pd.concat(R, ignore_index=True)
D = D[D.pos.isin(["QB", "RB", "WR", "TE"])].drop_duplicates(["week", "src", "dk_player_id"])
D = D.merge(act.rename(columns={"dk_points": "actual"}), on=["gsis_id", "week"], how="left")
D["played"] = D.actual.notna(); D["actual"] = D.actual.fillna(0.0)
D["tier"] = pd.cut(D.salary, [0, 3999, 5999, 7999, 99999], labels=["<4k", "4-5.9k", "6-7.9k", "8k+"])
D["o20"] = D.actual >= 20; D["o25"] = D.actual >= 25; D["o30"] = D.actual >= 30
D["ov4"] = D.actual >= 4 * D.salary / 1000; D["ov5"] = D.actual >= 5 * D.salary / 1000; D["o_2x"] = D.actual >= 2 * np.maximum(D.sim_mean, 1.0)
D = D[D.sim_mean >= 1.0]
def table(X, by):
    rows = []
    for k, g in X.groupby(by, observed=True):
        row = {"group": k if isinstance(k, str) else "/".join(map(str, k)), "n": len(g), "played": round(g.played.mean(), 2), "sim_mean": round(g.sim_mean.mean(), 2), "actual": round(g.actual.mean(), 2)}
        for p, o in (("p20", "o20"), ("p25", "o25"), ("p30", "o30"), ("pv4", "ov4"), ("pv5", "ov5"), ("p_2x", "o_2x")):
            e = g[p].sum(); v = (g[p] * (1 - g[p])).sum(); ob = g[o].sum()
            row[o] = f"{int(ob)}/{e:.1f} z{(ob - e) / np.sqrt(max(v, 1e-9)):+.1f}"
        rows.append(row)
    return pd.DataFrame(rows)
pd.set_option("display.width", 250)
for src in ("incumbent", "corrected"):
    X = D[D.src == src]
    print(f"\n=== {src} draws: observed/expected count of boom events, z = (obs - exp)/sd; players with sim mean >= 1, QB/RB/WR/TE, W1-4")
    print(table(X, "tier").to_string(index=False))
    print(table(X[X.tier == "<4k"], "pos").assign(group=lambda t: "<4k " + t.group).to_string(index=False, header=False))
    print(table(X[X.tier == "6-7.9k"], "pos").assign(group=lambda t: "6-7.9k " + t.group).to_string(index=False, header=False))
    print("  by week, <4k value-4x obs/exp: " + ", ".join(f"W{w} {int(g.ov4.sum())}/{g.pv4.sum():.1f}" for w, g in X[X.tier == "<4k"].groupby("week")) +
          "; 6-7.9k value-4x: " + ", ".join(f"W{w} {int(g.ov4.sum())}/{g.pv4.sum():.1f}" for w, g in X[X.tier == "6-7.9k"].groupby("week")))
