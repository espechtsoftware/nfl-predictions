# PREREG-049 / experiment 079: success interpretation and tonight outlook

**Date:** 2026-09-01
**Status checked:** 2026-09-01 17:03 CDT
**Purpose:** Reconcile the apparently conflicting statements that 079 was a
success and that its formal verdict was `UNPASSED_NEAR_MISS`, then record the
immediate decision and expected results.

## Executive finding

Both descriptions refer to different questions:

- **079 was a successful mechanism discovery.** Legal-relevance scheduling
  produced a large, coherent positive raw K80 signal, every raw-score bank was
  positive, and the allocation crossing localized nearly all of the movement
  to scheduling rather than to the 80/320 versus 40/360 solve split.
- **079 was not a formal preregistered pass.** Its frozen design tested three
  treatments against one control and required each passing treatment's
  98.33% family-adjusted interval to exclude zero. None did.
- **079 is not yet a current-objective adoption result.** Its frozen primary
  was raw weekly K80 maximum. `GLOBAL_WEMAX_PROXY`, now the primary objective,
  was descriptive in 079 and had a small negative sign in bank 532.

The recommended language is:

> **079 was a successful, high-value mechanism discovery and a strong positive
> near-miss, but not a formal family-adjusted pass or an adoption confirmation.**

The formal ledger label should not be changed after seeing the results. What
should be reconsidered is any language implying that the scheduling idea
failed or is low priority. It is currently the program's highest-priority
unconfirmed scoring lever.

## What 079 actually found

The four natural cells used exact K80, 400 requested solves, the same
dual-law expected-max critic, and the same three banks:

| Cell or contrast | Raw K80 delta | Interpretation |
|---|---:|---|
| `A8032_TOTAL` | control | 80 leverage / 320 boom, total-sum schedule |
| `A4036_TOTAL - A8032_TOTAL` | +0.515 | Allocation change under total scheduling |
| `A8032_LEGAL - A8032_TOTAL` | **+1.900** | Pure scheduling effect at 80/320 |
| `A4036_LEGAL - A8032_TOTAL` | **+2.021** | Combined allocation-and-scheduling cell versus control |
| `A4036_LEGAL - A4036_TOTAL` | approximately **+1.506** | Implied pure scheduling effect at 40/360 |
| `A4036_LEGAL - A8032_LEGAL` | +0.120 | Allocation change under legal scheduling |
| Factorial interaction | approximately -0.39 | No evidence that allocation adds to scheduling |

One correction to earlier shorthand is important: `+2.021` is not a second
pure scheduling contrast. It compares `A4036_LEGAL` with the original
`A8032_TOTAL` control and therefore changes both factors. The two clean
schedule-only estimates are about `+1.900` at 80/320 and `+1.506` at 40/360.

The strongest supporting facts are:

- `A8032_LEGAL` was +1.900, all three banks positive, with 44 weekly wins,
  27 losses, and one tie. Its unadjusted sign-flip p-value was 0.0495.
- `A4036_LEGAL` was +2.021 versus the original control, all three banks
  positive, with 48 wins, 24 losses, and no ties. Its unadjusted sign-flip
  p-value was 0.0389.
- The legal cells produced 187–192 roster hits at 187+ versus 149 for the
  control, and 103–107 roster hits at 194+ versus 89–91 for the total-order
  cells.
- The allocation decision was effectively a wash. That makes scheduling,
  rather than merely moving 40 solves between leverage and boom, the likely
  source of the improvement.
- The schedule mechanics engaged under a fixed 400-solve budget; this was not
  an extra-compute comparison.

The two legal cells are correlated views on the same historical slates and
simulator banks, not independent replications. Their agreement strengthens
mechanism attribution, but it must not be counted as two independent
confirmations.

## Why the formal verdict was a near-miss

PREREG-049 froze three treatments versus `A8032_TOTAL`. It therefore used a
Bonferroni family level of:

```text
1 - 0.05 / 3 = 0.983333...
```

The frozen reader required all of the following for `PASS`:

1. positive point estimate;
2. family-adjusted lower interval bound above zero;
3. every bank nonnegative; and
4. no more than one negative leave-one-season-out estimate.

`UNPASSED_NEAR_MISS` was explicitly defined as a positive point estimate with
every bank nonnegative but a family-adjusted lower bound at or below zero.
That is exactly what occurred.

The nominal sign-flip p-values, 0.0495 and 0.0389, are below 0.05 but not below
the three-comparison family threshold of approximately 0.0167. Calling the
miss “purely a family-size artifact” would overstate the case: multiplicity is
why the formal threshold was not crossed, but the correction was a
preregistered safeguard, and the nominal evidence itself is close to 0.05.

Changing the label now would move the goalposts. Preserving it protects the
credibility of later passes. It does **not** require treating the effect as
unimportant.

## Current-objective qualification

079 was grandfathered under raw weekly K80 maximum as its frozen primary.
Under the subsequently adopted `GLOBAL_WEMAX_PROXY`, the legal cells improved
descriptively by approximately +0.0081 and +0.0086, but bank 532 was
marginally negative.

That matters because the new objective places more relative value on the
winner-score range than the old raw-maximum mean. The raw result strongly
suggests better schedules, but it has not yet established that the extra
points consistently land where the current utility values them most.

## Recommended decision

1. **Do not retroactively relabel 079 as `PASS`.** Keep the immutable formal
   result as `UNPASSED_NEAR_MISS`.
2. **Treat it operationally as a success worth immediate confirmation.** It
   graduates the legal scheduler from an idea to the top unconfirmed lever.
3. **Run PREREG-052 / experiment 083 next.** It is the clean reconsideration:
   one schedule-only contrast, exact 80/320 D400 control, fresh banks 580–582,
   and `GLOBAL_WEMAX_PROXY` as the primary endpoint. With one contrast, it
   does not carry 079's three-arm multiplicity penalty.
4. **Prepare both Week-1 schedule variants.** Until 083 resolves, the legal
   book can be produced as a shadow or explicitly bounded exploratory sleeve
   without replacing the entire entered policy.
5. **Do not mechanically add effects.** D800's approximately +1.216 and the
   scheduler's approximately +1.5 to +1.9 are complementary in theory, but
   “about +3 combined” is a hypothesis until a compatibility crossing or a
   prospectively frozen book measures it.

Recommended 083 interpretation:

- **Pass under the proxy primary:** make legal scheduling eligible for the
  live D400 package and freeze prospective 2026 grading; test compatibility
  with D800 rather than assuming additivity.
- **Positive proxy near-miss with coherent banks:** retain a bounded
  prospective shadow/sleeve and let 2026 settlement decide; do not call it a
  historical confirmation.
- **Bank reversal or negative result:** do not adopt; retain 079 as a useful
  development discovery that failed fresh-bank/current-objective transport.

## Results expected tonight

### E4 broad-corpus admission

The only result definitely computing at the status check was production E4
execution `atlas-cbc-32g-full-2023-w8-v1-7zpd4`, UID
`cada1617-0e2c-4a2a-b33b-c2aec97a2c69`.

- It started at 13:00:50 CDT with one running task and a six-hour timeout.
- It should reach a terminal state by approximately 19:00:50 CDT.
- On success, the exact-name finisher will validate the fixed-corpus A250/A500
  admission comparison: modeled-tail reference, source-quota/disagreement,
  past-only walk-forward ridge where available, and fixed-budget blends.
- It measures admitted-pool realized maximum and 194–240 retention. It is
  important corpus-admission intelligence, but it is not an entered K80
  selector result.
- Because the independent reopen is already close to its time envelope, a
  timeout rather than a sealed score remains a material possibility.

### PREREG-052 / experiment 083

083 was frozen and launch-ready but **not running** at the status check. It
still required an immutable build/binding, coordinated outcome-disabled
mechanics gate, and three-bank launch.

Once launched, the three-bank result is plausibly 2–3 hours away under the
two-execution capacity limit. If 079 transports, a reasonable directional
expectation is roughly +0.008 winner utility and about +1.5 to +1.9 raw K80
points. This is a forecast, not evidence; bank 532's proxy sign makes an
unresolved result entirely plausible.

No other scoring result was honestly imminent at the status check. 080–082
remained held, E5 had not launched, and KG-2 topology, participation, and KG-4
leverage calibration were engineering/design priorities rather than active
efficacy executions.

## Source references

- Lab preregistration: `../nfl2/PREREG-049.md`
- Frozen reader: `../nfl2/scripts/prereg049_report.py`
- Sealed result summary: `../nfl2/LEDGER.md`, PREREG-049 row
- Confirmation design: `../nfl2/PREREG-052.md`
- Lab priority decision: `../nfl2/reports/2026-09-01-priority-ranking.md`
- Production cloud/status record: `HANDOFF.md`
