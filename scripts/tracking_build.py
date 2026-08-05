"""Workstream C v0 driver: BDB 2026 tracking -> trait aggregates (§7.3, §7.6).

Streams train/input_2023_w*.csv ONE FILE AT A TIME (this box crashes
under load — never hold two week frames at once; explicit dtypes and
usecols keep a week at ~40MB, whole run well under 2GB), folds each
into a TraitAccumulator, and writes:

- traits CSV: one row per (nfl_id, position, season=2023) with v0
  receiver/defender traits + §7.6 coverage metadata;
- coverage CSV: per-week rows/plays/players processed.

Both are written to the BDB DATA directory (research artifact, not
repo). The nfl_id -> gsis_id crosswalk is a separate step
(research.tracking_ids.build_id_map — needs BigQuery).

Usage:
    python scripts/tracking_build.py [--limit-weeks N]
        [--data-dir DIR] [--out CSV] [--coverage-out CSV]
"""

from __future__ import annotations

import argparse
import gc
import re
import resource
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.research.tracking_traits import (  # noqa: E402
    TraitAccumulator, canonicalize, read_week_file)

DEFAULT_DATA_DIR = Path(
    "/home/erich/projects/other-nfl-projects/nfl-big-data-bowl-2026")
SEASON = 2023


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--limit-weeks", type=int, default=None,
                    help="process only the first N week files")
    ap.add_argument("--out", type=Path, default=None,
                    help=f"traits CSV (default: DATA_DIR/tracking_traits_{SEASON}_v0.csv)")
    ap.add_argument("--coverage-out", type=Path, default=None,
                    help=f"coverage CSV (default: DATA_DIR/tracking_coverage_{SEASON}_v0.csv)")
    args = ap.parse_args(argv)

    files = sorted((args.data_dir / "train").glob(f"input_{SEASON}_w*.csv"))
    if args.limit_weeks:
        files = files[: args.limit_weeks]
    if not files:
        print(f"no input_{SEASON}_w*.csv under {args.data_dir}/train", file=sys.stderr)
        return 1
    out = args.out or args.data_dir / f"tracking_traits_{SEASON}_v0.csv"
    cov_out = (args.coverage_out
               or args.data_dir / f"tracking_coverage_{SEASON}_v0.csv")

    acc = TraitAccumulator()
    coverage = []
    t0 = time.monotonic()
    for path in files:
        week = int(re.search(r"_w(\d+)\.csv$", path.name).group(1))
        tw = time.monotonic()
        df = read_week_file(path)          # ONE file in memory at a time
        stats = acc.update(canonicalize(df), week)
        del df
        gc.collect()
        stats["seconds"] = round(time.monotonic() - tw, 1)
        coverage.append(stats)
        print(f"week {week:2d}: {stats['rows']:7d} rows "
              f"{stats['plays']:5d} plays {stats['players']:4d} players "
              f"({stats['seconds']}s)")

    traits = acc.finalize(SEASON)
    traits.to_csv(out, index=False)
    pd.DataFrame(coverage).to_csv(cov_out, index=False)

    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"\n{len(files)} week(s) in {time.monotonic() - t0:.1f}s, "
          f"peak RSS {peak_mb:.0f}MB")
    print(f"traits:   {len(traits)} players -> {out}")
    print(f"coverage: {cov_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
