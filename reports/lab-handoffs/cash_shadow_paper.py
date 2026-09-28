"""PAPER cash/double-up shadow for a live week: build before lock, score on Monday. Enters nothing.

Operator: a cash/double-up shadow BESIDE the tournament book, replacing nothing (2026-09-22). Production supports a
Week-3 paper run (HANDOFF b7f40a64) after the Week-1/Week-2 retrospective (both >= ~50% of mean-max stacked lineups
clearing the double-up line).

  build:  python cash_shadow_paper.py build <paid run dir> <out dir> [--n 20]
          Reads <run dir>/frame.parquet exactly as the Sunday build produced it (DK denylist applied, gated QBs
          already projected 0, production-centred `proj`), solves N mean-max lineups (optimize_many on `proj`,
          production QB+2+bring-back stack, max_overlap 7, production env), writes <out>/cash_shadow.csv and a
          receipt with sha256 of the frame and of the lineups. No outcome is read. Must run before lock.
  build-b: python cash_shadow_paper.py build-b <paid run dir> <out dir B> [--n 20]
          ARM B (production 4b004f8c, operator question: is L03's higher mean a cash lever?). The same N mean-max lineups
          from the same frame, but every row the live build priced (frame market_points present) is shifted by
          0.55 x (MEDIAN_BONUS - PLAIN) market points: both conversions come from ONE offline snapshot (prop_market
          market_points(minimum_markets=2), the latest pre-lock lines), so the shift isolates the conversion
          (MARKET_LINE_MEDIAN + MARKET_BONUS_AWARE) from snapshot timing. 0.55 is the live market weight (1 - 0.45).
          Needs a checkout whose prop_market has those flags (laptop/cash-arm-b-20260924). Paper only; enters nothing.
  score:  python cash_shadow_paper.py score <out dir> <season> <week>
          After the slate: realized DK points per lineup (Millionaire ownership file), and the share clearing each
          of the five largest real GPP fields' top-45% line (double-up depth) and median, next to the entered
          book's share. The same lines as the retrospective, so the three weeks are comparable.
Needs PYTHONPATH with the pinned nfl2 src (for the solver) and nfl-predictions src (for BigQuery reads).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


MARKET_WEIGHT = 0.55     # 1 - BLEND_MODEL_WEIGHT (0.45), the live Week-3 blend


def conversion_shift(fr: pd.DataFrame, plain: dict, converted: dict) -> tuple[pd.Series, dict]:
    """Per-row shift of `proj` for arm B: MARKET_WEIGHT x (converted - plain) on rows the live build priced."""
    g = fr.gsis_id.astype(str)
    priced = fr.market_points.notna() if "market_points" in fr else pd.Series(False, index=fr.index)
    ok = priced & g.isin(plain) & g.isin(converted)
    delta = pd.Series(0.0, index=fr.index)
    delta[ok] = MARKET_WEIGHT * (g[ok].map(converted) - g[ok].map(plain))
    return delta, {"rows_priced_live": int(priced.sum()), "rows_shifted": int(ok.sum()),
                   "rows_priced_live_without_offline_price": int((priced & ~ok).sum()),
                   "mean_shift_on_shifted": round(float(delta[ok].mean()), 4) if ok.any() else 0.0}


def offline_conversions(season: int, week: int) -> tuple[dict, dict]:
    """PLAIN and MEDIAN_BONUS market points (gsis_id -> points) for one week, from one offline snapshot."""
    import os
    from nfl_dfs.models import prop_market
    if not (hasattr(prop_market, "line_median") and hasattr(prop_market, "bonus_aware")):
        raise SystemExit("this nfl-predictions checkout has no MARKET_LINE_MEDIAN / MARKET_BONUS_AWARE; run arm B from "
                         "laptop/cash-arm-b-20260924")
    saved = {k: os.environ.get(k) for k in ("MARKET_LINE_MEDIAN", "MARKET_BONUS_AWARE")}
    out = {}
    try:
        for flag in ("0", "1"):
            os.environ["MARKET_LINE_MEDIAN"] = os.environ["MARKET_BONUS_AWARE"] = flag
            m = prop_market.market_points((season,), minimum_markets=2)
            m = m[m.week == week]
            out[flag] = dict(zip(m.gsis_id.astype(str), m.market_points.astype(float)))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return out["0"], out["1"]


def build(run_dir: str, out_dir: str, n: int = 20, arm_b: bool = False) -> None:
    from nfl2.core.lineup import optimize_many
    from nfl2.pipeline import PRODUCTION_ENV, PRODUCTION_STACK, _pool
    run, out = Path(run_dir), Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    frame_bytes = (run / "frame.parquet").read_bytes()
    rec = json.loads((run / "receipt.json").read_text())
    lock = pd.Timestamp(rec["lock_utc"]); now = pd.Timestamp.now("UTC")
    smoke = __import__("os").environ.get("CASH_SHADOW_SMOKE") == "1"   # mechanics test on a past week only
    if now >= lock and not smoke:
        raise SystemExit(f"lock {lock} has passed; a paper shadow built after lock is not a pre-lock test")
    fr = pd.read_parquet(run / "frame.parquet").reset_index(drop=True)
    conv = None
    if arm_b:
        plain, converted = offline_conversions(int(rec["season"]), int(rec["week"]))
        delta, conv = conversion_shift(fr, plain, converted)
        fr["proj"] = fr.proj + delta
    lus = optimize_many(_pool(fr), n, stack=PRODUCTION_STACK, objective_col="proj", env=dict(PRODUCTION_ENV))
    if len(lus) < n:
        raise SystemExit(f"only {len(lus)} of {n} cash lineups solved")
    rows = [{"rank": i + 1, "players": "|".join(sorted(str(p["name"]) for p in lu.players)),
             "ids": "|".join(sorted(str(p["id"]) for p in lu.players)), "salary": int(sum(p["salary"] for p in lu.players)),
             "proj": round(float(sum(p["proj"] for p in lu.players)), 2)} for i, lu in enumerate(lus)]
    df = pd.DataFrame(rows); csv = df.to_csv(index=False).encode()
    (out / "cash_shadow.csv").write_bytes(csv)
    expo = pd.Series([p for r in rows for p in r["players"].split("|")]).value_counts() / n
    receipt = {"kind": "SMOKE (post-lock, not a test)" if smoke else "paper cash shadow (entered nowhere)", "built_utc": str(now), "lock_utc": str(lock),
               "season": rec["season"], "week": rec["week"], "run_dir": str(run), "run_identity": rec.get("identity"),
               "frame_sha256": _sha(frame_bytes), "lineups_sha256": _sha(csv), "n": n,
               "objective": "mean proj" + (" (arm B: proj + 0.55 x (MEDIAN_BONUS - PLAIN), one offline snapshot)" if arm_b else ""),
               "arm": "B" if arm_b else "A", "conversion": conv, "stack": "production QB+2+bring-back", "max_overlap": 7,
               "mean_proj": round(float(df.proj.mean()), 2), "max_exposure": {k: round(float(v), 3) for k, v in expo.head(10).items()}}
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1))
    print(json.dumps(receipt, indent=1))


def score(out_dir: str, season: int, week: int) -> None:
    from nfl_dfs.bq import query_df
    out = Path(out_dir); rec = json.loads((out / "receipt.json").read_text())
    df = pd.read_csv(out / "cash_shadow.csv")
    if _sha((out / "cash_shadow.csv").read_bytes()) != rec["lineups_sha256"]:
        raise SystemExit("cash_shadow.csv changed after the pre-lock receipt; refusing to score")
    T = "`nfl-predictions-503414.nfl_raw.contest_entries`"
    mid = query_df(f"SELECT contest_id FROM {T} WHERE season={season} AND week={week} AND contest_name LIKE '%Millionaire%' "
                   "GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1").contest_id.iloc[0]
    own = query_df(f"""SELECT display_name, MAX(fpts) f FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
                       WHERE season={season} AND week={week} AND contest_id='{mid}' GROUP BY 1""")
    pts = dict(zip(own.display_name.astype(str), own.f.astype(float)))
    cash = np.array([sum(pts.get(p, 0.0) for p in r.split("|")) for r in df.players])
    gpps = query_df(f"""SELECT contest_id, ANY_VALUE(contest_name) nm, COUNT(*) n FROM {T} WHERE season={season} AND week={week}
                       AND NOT REGEXP_CONTAINS(LOWER(contest_name), r'sat|qualifier') GROUP BY 1 HAVING n >= 5000 ORDER BY n DESC LIMIT 5""")
    rows = []
    for cid, nm in zip(gpps.contest_id, gpps.nm.str.slice(0, 26)):
        f = query_df(f"SELECT points FROM {T} WHERE season={season} AND week={week} AND contest_id='{cid}'").points.to_numpy(float)
        du = np.quantile(f, 0.55)
        rows.append({"field": nm, "entries": len(f), "double-up line (top 45%)": round(du, 1), "median": round(float(np.median(f)), 1),
                     "cash shadow %": round(100 * float((cash >= du).mean()), 1)})
    print(f"paper cash shadow, {season} W{week}: n={len(cash)} mean {cash.mean():.1f} min {cash.min():.1f} max {cash.max():.1f} "
          f"(mean proj {df.proj.mean():.1f})")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    if sys.argv[1] in ("build", "build-b"):
        build(sys.argv[2], sys.argv[3], int(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[4] == "--n" else 20,
              arm_b=sys.argv[1] == "build-b")
    elif sys.argv[1] == "score":
        score(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        raise SystemExit(__doc__)
