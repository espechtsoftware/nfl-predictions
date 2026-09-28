# PREREG-L11 result: late swap aimed at the satellite ticket line

Laptop agent, read once on 2026-09-28 (08:30 CDT). Frozen lab `laptop/l11-late-swap-satellite-20260928` @ `63f06f5`; every
result line carries identity `63f06f5`, not dirty. 72 of 72 slate-banks (banks 1180–1181), 0 errors, run on the
laptop. Result files: lab `laptop/l11-results-20260928` (`results/l11/`).

## Reader output (verbatim)

```
slate-banks read: 72 (expected 72); mean fraction of early games remaining at the cutoff 0.172; late games per slate 3.75

MEAN book (K144): tickets89 keep 979 -> swap 1088 (+11.1%); tickets95 451 -> 524; seasons (keep, swap) {2023: (452, 484), 2024: (527, 604)}; paired slate-banks W/L/T 30/32/10
  realized mean per row 122.07 -> 123.73; swapped rows per slate 68.7 of 131.2 with a late player; realized change on swapped rows +2.83; simulated tickets 1393.4 -> 1599.9

EMAX book (K144): tickets89 keep 856 -> swap 976 (+14.0%); tickets95 413 -> 483; seasons (keep, swap) {2023: (375, 442), 2024: (481, 534)}; paired slate-banks W/L/T 36/27/9
  realized mean per row 119.15 -> 121.32; swapped rows per slate 62.5 of 123.4 with a late player; realized change on swapped rows +4.68; simulated tickets 1185.3 -> 1406.5

DECISION (MEAN book, tickets89): swap 1088 vs keep 979 (+11.1%); seasons {2023: (452, 484), 2024: (527, 604)}; paired 30-32
  -> SATELLITE LATE SWAP NOT SUPPORTED
```

## What it means

1. **Frozen verdict: SATELLITE LATE SWAP NOT SUPPORTED.**
   - The per-entry swap at 3:55 pm ET raised tickets at the realized field p89 by **+11.1%** (979 → 1,088) and at p95
     by **+16.2%** (451 → 524).
   - It is better in both seasons (2023 452 → 484, 2024 527 → 604).
   - The realized mean per row rose +1.66; swapped rows gained **+2.83** on average.
   - But the paired count was **30 wins, 32 losses, 10 ties**, and the rule required more wins than losses.
2. **The same lumpy pattern as MEAN vs EMAX** (L09: +13.3%, paired 30–32; L10: +20.8%, 37–28). Large gains on some
   slates, small losses on many. On expected tickets over a season the evidence favours the swap; on any one Sunday it
   is close to a coin flip.
3. **The EMAX book (secondary)** gains more: +14.0%, paired **36–27**, realized change on swapped rows +4.68.
4. **The information set is realistic:** early games were 17% unfinished on average at the cutoff; 3.75 late games
   per slate.
5. **Against the lab's closed late-swap family** (023 −1.23, 024 −0.42 on the book's weekly maximum): the satellite
   objective is where swapping helps. The tail objective was the wrong target for it.

## For the operator (nothing is adopted by this file)

The frozen rule says no. The aggregate says +11% tickets, with the same week-to-week lumpiness the operator already
accepted for the mean track.

Using it on Sunday 10-04 would need:
- a score-based swap tool: the `sat_late_swap.swap_entry` policy, fed by the validated ESPN feed
  (`scripts/live_dk_points.py`) at about 2:50 CT;
- output through production's frozen-map upload path (`late_inactive_swaps.py` / `sunday_swap.sh`);
- a Thursday-night dry run.

That is one to two days of laptop work, alongside the class model, the T-70 rules and the deploy. The late-inactive
replacement (R4) is built regardless.
