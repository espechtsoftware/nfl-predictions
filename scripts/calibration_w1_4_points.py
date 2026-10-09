#!/usr/bin/env python3
"""The calibration's points diagnostic (descriptive): per week and contest class, the model's mean lineup score (the
average of the T-70 incumbent and corrected-hsim bank means) against the real DK points, for OUR entries and for the
real field (ours removed; up to 20,000 sampled per contest, fixed seed), plus the calibration run's expected vs realized
cashes and the mean PIT. Aggregates only, printed; no contest ids, no dollars.

  python scripts/calibration_w1_4_points.py <calibration run dir with entries.csv>
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402


def main() -> int:
    run_dir = Path(sys.argv[1])
    ent = pd.read_csv(run_dir / "entries.csv", dtype={"contest_id": str, "entry_id": str})
    cfg = MS.load_config()
    out = []
    for w in sorted(set(ent.week)):
        W = MS.load_week(cfg, int(w))
        run = Path(cfg["weeks"][str(w)]["t70_run"])
        fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
        mi = np.load(run / "incumbent_player_scores.npy").mean(axis=1)
        mh = np.load(run / "corrected_hsim_player_scores.npy").mean(axis=1)
        row = {n: i for i, n in enumerate(fr.display_name.map(MS.canon))}

        def model_mean(names):
            idx = [row.get(n) for n in names if n]
            return np.nan if any(i is None for i in idx) else 0.5 * (mi[idx].sum() + mh[idx].sum())

        ew = ent[ent.week == w]
        for cid in sorted(set(ew.contest_id)):
            cls = MS.contest_class((W.details.get(cid) or {}).get("name") or "")
            fc = W.field[W.field.contest_id == cid]
            mine = fc[fc.entry_id.isin(set(ew[ew.contest_id == cid].entry_id))]
            oth = fc[~fc.entry_id.isin(W.ours)]
            if len(oth) > 20_000:
                oth = oth.sample(20_000, random_state=1)
            om = np.array([model_mean(n) for n in oth.names]); orl = oth.points.to_numpy() / 100
            mm = np.array([model_mean(n) for n in mine.names]); mrl = mine.points.to_numpy() / 100
            ok = np.isfinite(om)
            e2 = ew[ew.contest_id == cid]
            out.append(dict(week=w, cls=cls, n=len(mine), ours_model=np.nanmean(mm), ours_real=mrl.mean(),
                            field_model=om[ok].mean(), field_real=orl[ok].mean(),
                            exp_cash=float((e2.p_cash_incumbent + e2.p_cash_hsim).sum() / 2), cash=int(e2.cash_real.sum()),
                            pit_sum=float(((e2.pit_incumbent + e2.pit_hsim) / 2).sum())))
    d = pd.DataFrame(out)

    def agg(g):
        n = g.n.sum()
        wm = lambda c: (g[c] * g.n).sum() / n  # noqa: E731
        return pd.Series({"entries": n, "ours_model": wm("ours_model"), "ours_real": wm("ours_real"),
                          "field_model": wm("field_model"), "field_real": wm("field_real"),
                          "edge_model": wm("ours_model") - wm("field_model"), "edge_real": wm("ours_real") - wm("field_real"),
                          "exp_cash": g.exp_cash.sum(), "cash": g.cash.sum(), "pit_mean": g.pit_sum.sum() / n})
    pd.set_option("display.width", 200)
    print(d.groupby("week").apply(agg).round(2).to_string())
    print()
    print(d.groupby(["week", "cls"]).apply(agg).round(2).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
