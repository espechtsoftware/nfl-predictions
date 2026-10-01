"""Lev-solver acceptance (2026-10-01): re-run a Week-3 build's FULL lev batch under extra env settings (e.g.
LEV_CBC_THREADS=8) and compare it, lineup by lineup and in order, with the lev rows that build archived.

  PYTHONPATH=<nfl2 checkout>/src python lev_solver_acceptance.py <run dir> <out.json> [KEY=VAL ...] [--limit N]

Same reconstruction as lev_lazy_acceptance.py: optimize_many(_pool(frame.parquet), n_lineups, PRODUCTION_STACK,
"proj_tourney", PRODUCTION_ENV + MAX_PER_GAME from the receipt + the given settings). Progress is printed every 100
lineups by solving in prefix chunks? No: one batch call, timed; --limit runs only the first N (a smoke)."""
import json, re, sys, time
from pathlib import Path

import pandas as pd

from nfl2.core.lineup import optimize_many
from nfl2.pipeline import PRODUCTION_ENV, PRODUCTION_STACK, _pool


def main():
    args = sys.argv[1:]
    limit = None
    if "--limit" in args:
        i = args.index("--limit"); limit = int(args[i + 1]); del args[i:i + 2]
    run, out, extra = Path(args[0]), Path(args[1]), dict(a.split("=", 1) for a in args[2:])
    rec = json.loads((run / "receipt.json").read_text())
    n_lev = int(rec["config"]["lev"]) if limit is None else limit
    m = re.search(r'"max_per_game": (\d+)', json.dumps(rec)); mpg = int(m.group(1)) if m else None
    env = {**PRODUCTION_ENV, **({"MAX_PER_GAME": str(mpg)} if mpg is not None else {}), **extra}
    fr = pd.read_parquet(run / "frame.parquet"); cands = pd.read_parquet(run / "candidates.parquet")
    want = [frozenset(s.split(",")) for s in cands[cands.tag == "lev"].sort_values("cand").players][:n_lev]
    t0 = time.time()
    got = optimize_many(_pool(fr), n_lineups=n_lev, stack=PRODUCTION_STACK, objective_col="proj_tourney", env=env)
    secs = time.time() - t0
    gs = [frozenset(str(p["id"]) for p in lu.players) for lu in got]
    first = next((i for i, (a, b) in enumerate(zip(gs, want)) if a != b), None)
    res = {"run": run.name, "settings": extra, "n_lev": n_lev, "returned": len(gs), "identical_in_order": len(gs) == len(want) and first is None,
           "first_difference_at": first, "seconds": round(secs, 1), "archived_build_seconds": rec.get("seconds")}
    out.write_text(json.dumps(res, indent=1)); print(json.dumps(res))


if __name__ == "__main__":
    main()
