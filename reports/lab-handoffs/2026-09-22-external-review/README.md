# External review scripts (2026-09-22)

Evidence behind `reports/2026-09-22-external-review-suggestions.md`. Read-only against the warehouse;
nothing here touches the money path.

```bash
OUT=~/.cache/nfl-dfs-external-review            # anywhere OUTSIDE the repo (DK ownership + vendor data)
PY=~/projects/nfl-predictions/.venv/bin/python
$PY pull_inputs.py $OUT                           # BigQuery pulls + one polite LineStar pass (72 calls, ~3 min)
$PY crowd_and_gap.py $OUT                         # sections 1-5 of the report's crowd / book-vs-field numbers
RUN=<archived Week-2 run dir, e.g. review-evidence/overnight-20260918/d12800-archive-20260920>
$PY slate_ppc.py $RUN 2 $OUT --dual               # raw (+ combined bank)
$PY slate_ppc.py $RUN 2 $OUT --condition-availability
$PY slate_ppc.py $RUN 2 $OUT --condition-availability \
    --override "Justin Jefferson=17.27" --override "Zay Flowers=14.70" \
    --override "Ladd McConkey=14.82" --override "Jack Bech=7.11"
```

`slate_ppc.py` runs unchanged on the Week-1 run directory (`<run_dir> 1 <inputs>`); the Week-1 run is
not on the laptop. The overrides remove the Week-2 DK-PPG market stand-in (deleted from production on
2026-09-21): each is `(served − 0.55 × dk_ppg) / 0.45`, i.e. the served model-only value, except
Jefferson (`0.45 × 18.1 + 0.55 × 16.60`, his props restored).

Runtime: `crowd_and_gap.py` ~1 min; each `slate_ppc.py` call ~4 min (12,555 candidates × 20,000 worlds).
