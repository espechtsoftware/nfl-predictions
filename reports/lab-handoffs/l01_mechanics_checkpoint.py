"""Outcome-blind mechanics checkpoint for the running L01 panel (never reads an outcome field).

Reads ~/.cache/laptop-agent/l01/results_bank<B>.jsonl and summarises ONLY mechanics: slates done, per-arm generation time,
infeasible / exhausted / error solves, delivered uniques, the max-per-game distribution of each pool, the lev share of
each book, and a projected finish time. Outcome keys (`*_pool_oracle`, `*_book_*`, `*_pool_ge*`) are dropped on read and
never printed, so running this mid-panel is not a peek. The decision read is only `nfl2 scripts/l01_report.py`, once.

  python l01_mechanics_checkpoint.py [results dir] [banks=1100,1101,1102] [workers=8]
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.cache/laptop-agent/l01").expanduser()
BANKS = [int(b) for b in (sys.argv[2] if len(sys.argv) > 2 else "1100,1101,1102").split(",")]
WORKERS = int(sys.argv[3]) if len(sys.argv) > 3 else 8
ARMS = ("CTRL", "ALLBOOM_CEIL", "MAXGAME4")
OUTCOME = ("_pool_oracle", "_book_max", "_book_mean", "_book_ge", "_pool_ge")

rows, walls = [], []
for b in BANKS:
    f = OUT / f"results_bank{b}.jsonl"
    if not f.exists():
        continue
    for line in f.read_text().splitlines():
        r = json.loads(line); m = r.get("result") or r.get("mechanics") or {}
        rows.append({k: v for k, v in m.items() if not any(s in k for s in OUTCOME)}); walls.append(r.get("wall_secs"))
errs = (OUT / "errors.jsonl").read_text().splitlines() if (OUT / "errors.jsonl").exists() else []
total = 54 * len(BANKS)
print(f"slate-banks done {len(rows)}/{total}; errors {len(errs)}")
if not rows:
    sys.exit(0)
for arm in ARMS:
    g = [r[f"secs_gen_{arm}"] for r in rows]
    bad = sum(r.get(f"status_infeasible_{arm}", 0) + r.get(f"status_exhausted_{arm}", 0) + r.get(f"status_error_{arm}", 0) for r in rows)
    n = [r[f"n_{arm}"] for r in rows]
    mpg = Counter()
    for r in rows:
        mpg.update({int(k): v for k, v in r[f"maxpergame_{arm}"].items()})
    tot = sum(mpg.values())
    print(f"  {arm:13s} gen {np.median(g)/60:5.1f} min median (max {max(g)/60:.1f}) | uniques {min(n)}-{max(n)} | "
          f"bad solves {bad} | max-per-game {', '.join(f'{k}:{100*v/tot:.0f}%' for k, v in sorted(mpg.items()))} | "
          f"book lev {np.mean([r[f'book_lev_{arm}'] for r in rows]):.1f}/80")
w = [x for x in walls if x]
if w:
    left = total - len(rows); eta = left * np.median(w) / WORKERS
    print(f"  median wall per slate-bank {np.median(w)/60:.0f} min; remaining {left} -> ~{eta/3600:.1f} h on {WORKERS} workers "
          f"(ETA {time.strftime('%a %H:%M', time.localtime(time.time() + eta))})")
