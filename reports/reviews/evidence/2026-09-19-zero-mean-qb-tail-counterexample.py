#!/usr/bin/env python3
"""Input-only algebraic probe; does not regenerate a model or predict lift."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from nfl2.core.blend import shift_draws_to_means
from nfl2.pipeline import proj_tourney_production


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    f = pd.read_parquet(a.run / "frame.parquet", columns=[
        "id", "display_name", "pos", "salary", "mean_projection"])
    bank = np.load(a.run / "incumbent_player_scores.npy", allow_pickle=False)
    mask = f.display_name.isin(["Tyson Bagent", "Case Keenum", "Cooper Rush",
                               "Trey Lance", "Davis Mills", "Aidan O'Connell"])
    ix = np.flatnonzero(mask)
    g = f.iloc[ix].copy()
    z = shift_draws_to_means(bank[ix].astype(float), np.zeros(len(ix)))
    g["mean_projection"] = 0.0
    punt, receipt = proj_tourney_production(g, z)
    rows = [dict(name=str(f.display_name.iloc[i]), id=str(f.id.iloc[i]),
                 salary=int(f.salary.iloc[i]), old_mean=float(bank[i].mean()),
                 zero_centered_mean=float(z[j].mean()),
                 zero_centered_p90=float(np.quantile(z[j], .9)),
                 zero_centered_p99=float(np.quantile(z[j], .99)),
                 positive_world_fraction=float(np.mean(z[j] > 0)),
                 zero_centered_punt_objective=float(punt[j]))
            for j, i in enumerate(ix)]
    payload = dict(kind="algebraic_saved_bank_counterexample_not_full_gate_build",
                   source_sha="2dc116ce95647a776ba9c36cf194f44d022d03a4",
                   source_run=str(a.run),
                   bank_sha256=hashlib.sha256((a.run / "incumbent_player_scores.npy").read_bytes()).hexdigest(),
                   frame_sha256=hashlib.sha256((a.run / "frame.parquet").read_bytes()).hexdigest(),
                   frame_columns_read=list(f.columns),
                   helper="nfl2.core.blend.shift_draws_to_means",
                   punt_helper="nfl2.pipeline.proj_tourney_production",
                   punt_receipt=receipt, rows=rows)
    a.out.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    main()
