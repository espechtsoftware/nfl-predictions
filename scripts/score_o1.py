"""PREREG-O1 reader (reports/2026-09-28-PREREG-O1-fp-ownership-prospective.md, amendments 1-2): each pre-lock ownership
source against LAG, on o1_common's target and population. Prints per arm: Spearman (all, skill), the gain over LAG on
the same players, MAE raw and rescaled (amendment 2's scale rule: a source rescaled to LAG's skill total on the same
players), and the top-15 overlap with the realized top 15. Decides nothing; the rule is applied once after Week 7 (with
the one interim after Week 5).

Arms: FP (newest pre-lock DK capture) and LINESTAR (newest pre-lock capture file) on the players they cover; BLEND_LS and
BLEND_FP = mean(LAG %, X %) where X covers the player, else LAG %, on LAG's full population; TABPFN descriptive.

Usage: score_o1.py --season 2026 --week 4 --group 154078 --contest <Millionaire id> --lock-utc 2026-10-04T17:00:00Z \
           --lag ownership_lag.csv [--linestar capture.csv] [--tabpfn ownership_tabpfn.csv]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import o1_common as O  # noqa: E402

SKILL = O.SKILL


def compare(arm: pd.DataFrame, lag: pd.DataFrame, real: pd.Series, name: str) -> dict:
    """arm and lag: key, pos, v (ownership %); compared on the players both carry within the O1 population."""
    m = arm.merge(lag[["key", "v"]].rename(columns={"v": "lag"}), on="key")
    m = m[m.key.isin(set(real.index))]
    r = real.reindex(m.key).to_numpy(float); out = {"arm": name, "n": len(m)}
    for lab, mask in (("all", slice(None)), ("skill", m.pos.isin(SKILL).to_numpy())):
        mm = m[mask]; rr = pd.Series(real.reindex(mm.key).to_numpy(float), index=mm.key)
        a = O.spearman(pd.Series(mm.v.to_numpy(float), index=mm.key), rr)
        l = O.spearman(pd.Series(mm.lag.to_numpy(float), index=mm.key), rr)
        out[f"sp_{lab}"] = round(a, 4); out[f"gain_{lab}"] = round(a - l, 4)
    sk = m.pos.isin(SKILL)
    scale = m.lag[sk].sum() / m.v[sk].sum() if m.v[sk].sum() > 0 else 1.0
    out["mae_raw"] = round(float((m.v - r).abs().mean()), 3)
    out["mae_rescaled"] = round(float((m.v * scale - r).abs().mean()), 3)
    out["mae_lag"] = round(float((m.lag - r).abs().mean()), 3)
    top_r = set(real.reindex(m.key).sort_values(ascending=False).index[:15])
    out["top15_arm"] = len(top_r & set(m.sort_values("v", ascending=False).key[:15]))
    out["top15_lag"] = len(top_r & set(m.sort_values("lag", ascending=False).key[:15]))
    return out


def blend(lag: pd.DataFrame, x: pd.DataFrame) -> pd.DataFrame:
    m = lag.merge(x[["key", "v"]].rename(columns={"v": "x"}), on="key", how="left")
    m["v"] = m[["v", "x"]].mean(axis=1).where(m.x.notna(), m.v)
    return m[["key", "pos", "v"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    for k in ("season", "week", "group"):
        ap.add_argument(f"--{k}", type=int, required=True)
    ap.add_argument("--contest", required=True); ap.add_argument("--lock-utc", required=True); ap.add_argument("--lag", required=True)
    ap.add_argument("--linestar"); ap.add_argument("--tabpfn")
    a = ap.parse_args(argv)
    from google.cloud import bigquery
    c = bigquery.Client(project=O.PROJECT)
    real = O.realized(c, a.season, a.week, a.contest); sl = O.slate(c, a.group, a.lock_utc)
    lag = O.attach(pd.read_csv(a.lag), sl, "pred_own").rename(columns={"pred_own": "v"})
    fp_raw = c.query(f"""SELECT name, team, projected_ownership_pct FROM `{O.PROJECT}.nfl_raw.fantasy_points_projected_ownership`
        WHERE season={a.season} AND week={a.week} AND operator='DraftKings' AND retrieved_at < TIMESTAMP('{a.lock_utc}')
        QUALIFY retrieved_at = MAX(retrieved_at) OVER ()""").to_dataframe()
    arms = {}
    if len(fp_raw):
        assert not fp_raw.duplicated(["name", "team"]).any(), "FP capture holds duplicate (name, team): more than one slate?"
        arms["FP"] = O.attach(fp_raw, sl, "projected_ownership_pct").rename(columns={"projected_ownership_pct": "v"})
    if a.linestar and Path(a.linestar).is_file():
        ls = pd.read_csv(a.linestar); ls = ls.rename(columns={"own_proj": "v"}) if "own_proj" in ls else ls
        arms["LINESTAR"] = O.attach(ls.rename(columns={"v": "v"}), sl, "v")
    if a.tabpfn and Path(a.tabpfn).is_file():
        arms["TABPFN (descriptive)"] = O.attach(pd.read_csv(a.tabpfn), sl, "pred_own").rename(columns={"pred_own": "v"})
    if "LINESTAR" in arms:
        arms["BLEND_LS"] = blend(lag, arms["LINESTAR"])
    if "FP" in arms:
        arms["BLEND_FP"] = blend(lag, arms["FP"])
    print(f"realized: {len(real)} players drafted; slate {a.group}: {len(sl)}; LAG matched {len(lag)}, in the population "
          f"{int(lag.key.isin(set(real.index)).sum())}")
    for k, v in arms.items():
        print(f"  {k}: matched to the slate {len(v)}, in the population {int(v.key.isin(set(real.index)).sum())}")
    print(pd.DataFrame([compare(v, lag, real, k) for k, v in arms.items()]).to_string(index=False))
    print("gain = Spearman(arm) - Spearman(LAG) on the same players; the O1 rule uses gain_all (interim after W5; final after W7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
