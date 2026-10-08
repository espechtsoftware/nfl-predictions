#!/usr/bin/env python3
"""O-62b probe measures (design: reports/2026-10-08-o62b-probe-design.md, committed before any run).

    python probe_measure.py --live <run dir> --train <run dir> --live-seed <run dir> \
        --dump-live <rows.parquet> --dump-train <rows.parquet>

Each run dir is a live_week.py output (frame.parquet, incumbent_player_scores.npy = the selection bank after centring,
candidates.parquet). Prints aggregates only and the design's pre-stated line.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL = ("QB", "RB", "WR", "TE")
SD_LINE, JACCARD_LINE, TOP_N = 0.05, 0.70, 30


def assert_only_spread_differs(a: pd.DataFrame, b: pd.DataFrame) -> int:
    """The component rows of LIVE and TRAIN: identical but for `spread` (the design's assertion). Returns the rows whose
    spread differs."""
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        raise SystemExit("PROBE STOPPED: the two component-row dumps differ in shape or columns")
    pd.testing.assert_frame_equal(a.drop(columns=["spread"]).reset_index(drop=True),
                                  b.drop(columns=["spread"]).reset_index(drop=True), check_exact=True)
    return int((pd.to_numeric(a.spread, errors="coerce") != pd.to_numeric(b.spread, errors="coerce")).sum())


def load(run: Path) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    fr = pd.read_parquet(run / "frame.parquet")
    d = np.load(run / "incumbent_player_scores.npy")
    if d.shape[0] != len(fr):
        raise SystemExit(f"PROBE STOPPED: {run}: {d.shape[0]} draw rows vs {len(fr)} frame rows")
    return fr, d, pd.read_parquet(run / "candidates.parquet")


def draw_stats(fr: pd.DataFrame, d: np.ndarray) -> pd.DataFrame:
    s = pd.DataFrame({"id": fr["id"].astype(str), "pos": fr["pos"].astype(str), "team": fr["team"].astype(str),
                      "modeled": fr["pos"].isin(SKILL).to_numpy() & fr["has_features"].astype(bool).to_numpy(),
                      "mean": d.mean(axis=1), "sd": d.std(axis=1), "p90": np.percentile(d, 90, axis=1),
                      "p99": np.percentile(d, 99, axis=1)})
    return s.set_index("id")


def compare_draws(a: pd.DataFrame, b: pd.DataFrame, label: str) -> dict:
    """b relative to a, over the players modeled in both, by position."""
    j = a.join(b, rsuffix="_b", how="inner")
    j = j[j.modeled & j.modeled_b]
    out = {}
    print(f"   {label}: modeled skill players {len(j)}")
    for pos in SKILL:
        g = j[j.pos == pos]
        if g.empty:
            continue
        r = g.sd_b / g.sd
        rec = {"n": len(g), "sd_ratio_median": float(r.median()), "share_outside_5pct": float(((r - 1).abs() > SD_LINE).mean()),
               "median_abs_sd_dev": float((r - 1).abs().median()),
               "p90_diff_median": float((g.p90_b - g.p90).median()), "p90_diff_maxabs": float((g.p90_b - g.p90).abs().max()),
               "p99_diff_median": float((g.p99_b - g.p99).median()), "p99_diff_maxabs": float((g.p99_b - g.p99).abs().max()),
               "mean_diff_maxabs": float((g.mean_b - g["mean"]).abs().max())}
        out[pos] = rec
        print(f"      {pos}  n {rec['n']:3d}  sd ratio median {rec['sd_ratio_median']:.4f}  median |ratio-1| {rec['median_abs_sd_dev']:.4f}  "
              f"outside +/-5% {rec['share_outside_5pct']:.3f}  p90 diff median {rec['p90_diff_median']:+.3f} (max |.| "
              f"{rec['p90_diff_maxabs']:.3f})  p99 diff median {rec['p99_diff_median']:+.3f} (max |.| {rec['p99_diff_maxabs']:.3f})  "
              f"mean max |diff| {rec['mean_diff_maxabs']:.4f}")
    return out


def stack_corr(fr: pd.DataFrame, d: np.ndarray) -> dict:
    """Mean over teams of corr(QB draws, WR1 draws) and corr(QB, TE1), the players chosen by mean projection."""
    f = fr.reset_index(drop=True).assign(_i=np.arange(len(fr)), _m=pd.to_numeric(fr.mean_projection, errors="coerce"))
    out = {"QB-WR1": [], "QB-TE1": []}
    for _, t in f.groupby(f.team.astype(str)):
        qb = t[t.pos == "QB"].sort_values("_m", ascending=False).head(1)
        for lab, pos in (("QB-WR1", "WR"), ("QB-TE1", "TE")):
            x = t[t.pos == pos].sort_values("_m", ascending=False).head(1)
            if len(qb) and len(x) and d[qb._i.iloc[0]].std() > 0 and d[x._i.iloc[0]].std() > 0:
                out[lab].append(float(np.corrcoef(d[qb._i.iloc[0]], d[x._i.iloc[0]])[0, 1]))
    return {k: (float(np.mean(v)) if v else float("nan"), len(v)) for k, v in out.items()}


def lineups(c: pd.DataFrame, tag: str | None = None) -> set:
    c = c if tag is None else c[c.tag.astype(str) == tag]
    return {frozenset(p.split(",")) for p in c.players.astype(str)}


def jaccard(x: set, y: set) -> float:
    return len(x & y) / len(x | y) if (x or y) else float("nan")


def exposure(c: pd.DataFrame) -> pd.Series:
    ids = pd.Series([p for row in c.players.astype(str) for p in row.split(",")])
    return ids.value_counts() / len(c)


def pool_compare(ca: pd.DataFrame, cb: pd.DataFrame, label: str) -> dict:
    rec = {"all": jaccard(lineups(ca), lineups(cb))}
    for tag in sorted(set(ca.tag.astype(str)) | set(cb.tag.astype(str))):
        rec[tag] = jaccard(lineups(ca, tag), lineups(cb, tag))
    ea, eb = exposure(ca), exposure(cb)
    top = ea.sort_values(ascending=False).head(TOP_N).index
    dev = (eb.reindex(top).fillna(0.0) - ea.reindex(top)).abs()
    rec["top30_exposure_change_median"], rec["top30_exposure_change_max"] = float(dev.median()), float(dev.max())
    print(f"   {label}: candidates {len(ca)} vs {len(cb)}; Jaccard " + ", ".join(f"{k} {v:.3f}" for k, v in rec.items()
          if not k.startswith("top30")) + f"; top-{TOP_N} exposure |change| median {rec['top30_exposure_change_median']:.4f}"
          f" max {rec['top30_exposure_change_max']:.4f}")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    for k in ("--live", "--train", "--live-seed", "--dump-live", "--dump-train"):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args(argv)
    n_spread = assert_only_spread_differs(pd.read_parquet(a.dump_live), pd.read_parquet(a.dump_train))
    print(f"== O-62b PROBE  component rows: identical but for `spread` (asserted); spread differs on {n_spread} rows")
    (fl, dl, cl), (ft, dt, ct), (fs, ds, cs) = load(a.live), load(a.train), load(a.live_seed)
    in_cols = [c for c in fl.columns if c not in ("model_points_pre", "proj_tourney")]
    same_frame = all(fl[c].equals(ft[c]) for c in in_cols if c in ft.columns)
    print(f"   frames LIVE vs TRAIN identical on {len(in_cols)} input columns: {same_frame}")
    print("== DRAWS (selection bank after centring), by position")
    sl, st, ss = draw_stats(fl, dl), draw_stats(ft, dt), draw_stats(fs, ds)
    dr = compare_draws(sl, st, "TRAIN vs LIVE")
    compare_draws(sl, ss, "LIVE_SEED vs LIVE (the noise reference)")
    print("== STACK CORRELATION (mean over teams)")
    for lab, (f, d) in (("LIVE", (fl, dl)), ("TRAIN", (ft, dt)), ("LIVE_SEED", (fs, ds))):
        print(f"   {lab:9s} " + "  ".join(f"{k} {v:.4f} (teams {n})" for k, (v, n) in stack_corr(f, d).items()))
    print("== POOL (candidates.parquet)")
    pt = pool_compare(cl, ct, "TRAIN vs LIVE")
    ps = pool_compare(cl, cs, "LIVE_SEED vs LIVE (the noise reference)")
    worst = max(dr.items(), key=lambda kv: abs(kv[1]["sd_ratio_median"] - 1))
    crossed_a = any(abs(v["sd_ratio_median"] - 1) > SD_LINE for v in dr.values())
    crossed_b = pt["all"] < JACCARD_LINE and pt["all"] < ps["all"]
    print(f"== THE PRE-STATED LINE: (a) median |sd ratio - 1| > {SD_LINE:.0%} at any position: {'CROSSED' if crossed_a else 'below'} "
          f"(largest: {worst[0]} {abs(worst[1]['sd_ratio_median'] - 1):.4f}); (b) TRAIN/LIVE pool Jaccard {pt['all']:.3f} < "
          f"{JACCARD_LINE} AND below LIVE/LIVE_SEED {ps['all']:.3f}: {'CROSSED' if crossed_b else 'below'}")
    print("   VERDICT: " + ("CROSSED -- the operator gets options (a) W5 as is / (b) the TRAIN sign after a Friday rehearsal"
                            if (crossed_a or crossed_b) else "SMALL -- recorded; fixed after Week 5 with O-62"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
