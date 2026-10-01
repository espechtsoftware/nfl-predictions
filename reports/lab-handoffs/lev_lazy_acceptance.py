"""LEV_LAZY_CUTS acceptance (laptop task 2026-09-26; delegated to production 2026-10-01, HANDOFF 60c66851): re-run a
Week-3 build's FULL lev batch with lazy overlap cuts and compare it, lineup by lineup and in order, with the lev rows
that build archived. Pass = identical content and order. Reports wall time, active vs total cuts and re-solves.

  PYTHONPATH=<nfl2 checkout @ 89708c9>/src python lev_lazy_acceptance.py <run dir> <window> <out.json>

The frame is the run dir's frame.parquet (live_week.py writes the generation frame); the env is PRODUCTION_ENV plus the
receipt's arm max_per_game, as live_week.py built `_arm_env`; the batch is optimize_many(_pool(frame), n_lineups=lev,
stack=PRODUCTION_STACK, objective_col="proj_tourney", env) exactly as generate_candidates calls it."""
import json, logging, re, sys, time
from pathlib import Path

import pandas as pd

from nfl2.core.lineup import optimize_many
from nfl2.pipeline import PRODUCTION_ENV, PRODUCTION_STACK, _pool


class _Grab(logging.Handler):
    def __init__(self):
        super().__init__(logging.INFO); self.msgs = []
    def emit(self, rec):
        self.msgs.append(rec.getMessage())


def main():
    run, window, out = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    rec = json.loads((run / "receipt.json").read_text())
    n_lev = int(rec["config"]["lev"])
    mpg = rec["config"].get("arm", {}).get("max_per_game")
    if mpg is None:
        m = re.search(r'"max_per_game": (\d+)', json.dumps(rec)); mpg = int(m.group(1)) if m else None
    env = {**PRODUCTION_ENV, **({"MAX_PER_GAME": str(mpg)} if mpg is not None else {}), "LEV_LAZY_CUTS": "1", "LEV_LAZY_WINDOW": str(window)}
    fr = pd.read_parquet(run / "frame.parquet")
    cands = pd.read_parquet(run / "candidates.parquet")
    lev = cands[cands.tag == "lev"].sort_values("cand")
    want = [frozenset(str(p) for p in s.split(",")) for s in lev.players]
    if len(want) != n_lev:
        raise SystemExit(f"archive holds {len(want)} lev rows, the receipt says {n_lev}")
    grab = _Grab(); logging.getLogger().addHandler(grab); logging.getLogger().setLevel(logging.INFO)
    t0 = time.time()
    got = optimize_many(_pool(fr), n_lineups=n_lev, stack=PRODUCTION_STACK, objective_col="proj_tourney", env=env)
    secs = time.time() - t0
    gs = [frozenset(str(p["id"]) for p in lu.players) for lu in got]
    first_diff = next((i for i, (a, b) in enumerate(zip(gs, want)) if a != b), None)
    same = len(gs) == len(want) and first_diff is None
    stats = next((m for m in grab.msgs if m.startswith("lazy overlap cuts")), None)
    res = {"run": run.name, "window": window, "n_lev": n_lev, "max_per_game": mpg, "returned": len(gs), "identical_in_order": same,
           "first_difference_at": first_diff, "same_set_any_order": set(gs) == set(want), "seconds": round(secs, 1),
           "lazy_stats": stats, "archived_build_seconds": rec.get("seconds")}
    if first_diff is not None:
        a, b = gs[first_diff], want[first_diff]
        res["diff_detail"] = {"only_new": sorted(a - b), "only_archived": sorted(b - a)}
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
