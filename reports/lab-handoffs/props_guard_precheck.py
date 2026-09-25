#!/usr/bin/env python3
"""Pre-check the live props guard before running project-slate (read-only; writes nothing).

Replays exactly what `run_projections.run()` does before blending (at whatever commit this checkout is on; use the
deployed shipping commit): upcoming_slate_features -> prop_market.market_points(minimum_markets=2, prefer_ids=slate) ->
prop_feed_player_names -> market_source.resolve_live_market. Prints PASSES with the coverage, or the exact
MarketMatchError the job would stop on (an unmatched name to alias, or coverage under the 30% floor).

Saturday: run it right after the 09:30 props pull, so a failure is known ~15 minutes before the 09:45 refresh.
    PYTHONPATH=<deployed-commit checkout>/src python reports/lab-handoffs/props_guard_precheck.py --season 2026 --week 3
Exit 0 = the guard passes; 1 = it would stop the run.
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    from nfl_dfs.inference.market_source import MarketMatchError, resolve_live_market
    from nfl_dfs.inference.run_projections import upcoming_slate_features
    from nfl_dfs.models.prop_market import market_points, prop_feed_player_names

    feats = upcoming_slate_features(a.season, a.week)
    ids = {str(g) for g in feats.get("gsis_id", pd.Series(dtype=object)).dropna().tolist() if str(g).strip()}
    pm = market_points((a.season,), minimum_markets=2, prefer_ids=ids)
    pm = pm[pm.week == a.week]
    names = prop_feed_player_names(a.season, a.week)
    print(f"slate rows {len(feats)}; >=2-market priced players {len(pm)}; feed names {len(names)}")
    try:
        _m, src = resolve_live_market(feats, pm[["gsis_id", "market_points"]], names)
    except MarketMatchError as exc:
        print(f"GUARD WOULD STOP THE RUN: {exc}")
        return 1
    vc = src.source.value_counts().to_dict()
    print(f"GUARD PASSES: {vc}; props coverage {vc.get('props', 0)}/{len(src)} = {vc.get('props', 0) / max(len(src), 1):.1%} "
          "(floor 30%, DSTs included in the denominator)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
