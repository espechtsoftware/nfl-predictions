# Active-label exact-80 comparator invariant repair

Frozen 2026-08-12 after the first comparator stopped on its mechanical
invariance gate, and before any valid comparator report, selected weekly
maximum, tail-count decision, or active-label selection existed.

## What failed

All six registered exact-80 season books completed cleanly, and both panels
passed the independent replay/live mean and legal-lineup acceptance checks.
Comparator execution `compare-tabpfn-active-label-exact80-v2-nr296` then
returned `disposition=invalid` without calling the score comparison. Its only
failures were `player snapshots differ in mismatch_rows` and `player snapshot
invariant values differ`.

The invariant mistakenly registered only seven downstream player outputs as
allowed to respond to a different TabPFN marginal cache. Exact field-level
reconciliation found the omitted material differences were:

- `model_points_pre` on 28,411 rows: by construction, the mean of the treated
  marginal draws before the fixed market blend;
- `mean_projection` on the same 28,411 rows: by construction, the fixed 45/55
  blend of `model_points_pre` and the unchanged market value; and
- `consensus_div` on 10,923 rows: by construction,
  `model_points_pre - market_points` where a market value exists.

After treating those exact three deterministic descendants together with the
seven already registered outputs, all 29,605 player keys and every remaining
point-in-time input, actual, seed, and common lever are invariant at the
existing `1e-12` tolerance. The independently harvested acceptance reports
also show zero blend error and passing candidate-mean parity for both arms.
No panel needs regeneration; changing a cache while demanding that its
persisted mean and fixed market descendants remain unchanged was an impossible
validator contract.

## Prospective repair

The allowed output set is fixed at these ten fields before the repaired
comparator runs:

`consensus_div`, `mean_projection`, `model_points_pre`, `proj`,
`proj_tourney`, `own_est`, `proj_p10`, `proj_p50`, `proj_p90`, `proj_std`.

No raw input is added to the exclusions. The candidate panels, schedules,
cache tables, code SHA, seeds, exact-80 selections, threshold order
`240,230,220,210,200,194,187`, and first-nonzero/mean-tiebreak decision are
unchanged. The invalid raw report and execution id remain immutable evidence.
A new immutable audit image and new comparator execution must consume the
already completed panels; it may write a selection only if every repaired
mechanical check passes.

## Observer deviation

While diagnosing the completed acceptance artifacts, the operator agent
opened their ordinary summary text and thereby saw aggregate 187/194/200
counts for each 54-slate evaluation arm. No 240/230/220/210 counts, weekly
maxima, full 107-slate decision, or comparator selection was exposed. This was
unnecessary and is disclosed as an observer-blinding deviation.

The repair is nevertheless mechanical and score-independent: the three added
fields are direct deterministic descendants in `_market_blend_worlds`, all
other fields are still required invariant, and this repair was identified
from the invalid comparator's field reconciliation. The scoring rule is not
changed. The same ten-field contract is also frozen now for the not-yet-run
SCHED and team-passing comparisons so it cannot be chosen from their results.
