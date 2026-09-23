# Cash/double-up shadow, second measurement: a mean-maximizing build lands near break-even on Week 2 — once one inflated projection is fixed

The operator asked for a cash/double-up shadow **beside** the tournament book, replacing nothing. The first
measurement (`2026-09-22-laptop-cash-shadow-first-measurement.md`) scored the tournament book against double-up
lines. This one asks what a *cash-built* book would have done, on Week 2 with the Week-3 availability fixes applied.
Script: `reports/lab-handoffs/2026-09-22-cash-shadow-mean-max.py <frame.parquet> <week>` (the criterion is in its
header).

## Design
- **Pool:** the Week-2 Saturday 15:30Z frame, minus every skill player with zero offensive snaps (86 removed). That is
  an *oracle* availability filter standing in for the Week-3 rules (which catch 56/57 of Week 2's entered
  non-players), so it is mildly optimistic.
- **Cash builds:** `optimize_many` on the **mean projection** (`proj`), 20 lineups, max overlap 7, (i) with no
  stack rule and (ii) with the production QB+2+bring-back stack.
- **Lines:** each of the five largest real GPP fields' top-45% score (the usual double-up depth). The real double-up
  fields are not in our data; they are sharper, so these lines are lenient.

## Result

| build | before the stand-in fix | **after the stand-in fix** |
|---|---:|---:|
| mean-max, production stack | 0% | **45–55%** (mean 109.9) |
| mean-max, no stack | 5–10% | 20–45% (mean 115.0) |
| the 97 entered lineups (unchanged) | 26–37% | 26–37% (mean 105.0) |

Share of lineups at or above each field's double-up line, across the five fields. The stand-in fix sets the three
inflated Week-2 projections to their props-or-nothing values, as fixed for Week 3: Jefferson 25.3 → 17.3,
McConkey 17.2 → 14.8, Bech 9.4 → 7.1 (production, Addendum 2 of `2026-09-22-simulator-calibration-is-the-defect.md`).

## Reading
1. **A cash build is extremely fragile to single-player errors.** Maximizing the mean puts the top-value players in
   nearly every lineup. One inflated projection (Jefferson, served 25.3, scored 8.5) took the stacked build from
   ~55% to 0%. The tournament book, which diversifies, was far less sensitive to the same error (26–37% either way).
2. **With Week 3's fixes, the stacked cash build sits near double-up break-even** (~55% needed at a ~1.8× payout),
   on lenient lines, one slate. That is not yet an edge, but it no longer looks like a rout.
3. **The production stack helped the cash build here** (45–55% vs 20–45%). One slate is not enough to know whether
   that holds.

## Next
- **Production: please run it on Week 1** (`<W1 run dir>/frame.parquet 1`; the frame has licensed columns, so run it
  privately). Week 1 was a high-scoring slate where our pool sat at the field median, so a cash build should clear
  far more often. If both weeks are ≥ 50%, a paper cash shadow for Week 3 is worth running: 20 mean-max stacked
  lineups built from the same served projections, entered nowhere, scored Monday against real fields.
- Fragility argues for a **cash exposure cap** (e.g. no player in > 60% of cash lineups) as the first variant to
  test, measured the same way.
