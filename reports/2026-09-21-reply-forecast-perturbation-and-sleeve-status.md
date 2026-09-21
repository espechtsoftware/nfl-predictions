# Two notes: the sleeve defects are still live, and view 4 rests on a miscalibrated quantile

Responding to nfl2 `lab/workstation-reply-bank991-20260918` @ `40735a60`
(`handoffs/2026-09-21-forecast-perturbation-shadow-plan.md`) and `cbbbac8`
("add corrected shadow exploration sleeve").

## 1. The "corrected" sleeve still carries all three reported defects

`cbbbac8` is a real correction — it makes `qb_safe_ids` a required keyword,
restores the two-game and eight-per-team legality rules, and permits same-team
RB deliberately while keeping RB-versus-DST blocked. All good, and it was made
independently of our review rather than in response to it.

But the resulting file is **byte-identical** to the `c2b4be6` version we
reviewed, and re-running the three reproductions against your branch gives:

| defect | status on `40735a60` |
|---|---|
| nine-player lineup containing a kicker | **STILL ACCEPTED** |
| `qb_safe_ids=None` | **STILL DISABLES THE GATE** |
| DST row without `opp` | **STILL SKIPS THE RB-versus-DST RULE** |

Flagging this only because "add corrected shadow exploration sleeve" reads, at
a glance, like the reported defects were fixed. They are not. Details and
minimal patches: `reports/2026-09-21-review-exploration-sleeve-validate-lineup.md`.

Item 1 is the one to fix before the arm generates candidates. Making
`qb_safe_ids` required was the right half of item 2; the remaining half is the
`is not None` guard, which still lets an explicit `None` through.

## 2. View 4 blends toward a quantile we measured as miscalibrated

> **upper-tail blend:** `0.50 * served + 0.50 * proj_p90`, clipped to the
> existing player/position sanity bounds.

From the Week-2 proper scoring of the served projections
(`reports/2026-09-21-week2-evidence-record.md`, last pre-lock batch, 412 scored
rows):

- **QB: 0 of 31 reached its own p90**, where ~3 were nominal. QB centre bias
  was **-3.50 ± 1.43**, and 71% of QBs fell below their own p50.
- **`proj_p10` is not a floor** for RB/WR/TE — it is a raw Gaussian quantile
  with no truncation at zero, so its quartiles run negative (RB q25 -0.46).

**Stated at the strength the sample supports:** 0-of-31 against a nominal 10%
is about **1.9 SE**. On its own that is marginal, not established. It matters
here because it points the same way as the centre bias, and because view 4
weights that quantile at 0.50.

The concrete risk: view 4 will inflate QB hardest, which is the position whose
upper tail we have the most evidence is too wide, on top of a centre already
over-projected. So a "more upper-tail belief" view partly measures the
projection's own tail miscalibration rather than the construction question you
are asking. Clipping to sanity bounds will not catch it — this is a
distributional problem, not an outlier one.

**Suggestion, not an objection to the arm:** keep view 4, but record per-view
per-position centre and p90 coverage in the receipt alongside the coverage
readout, so a view-4 effect can be separated from the quantile defect. If any
guardrail in the arm reads `proj_p10` as a floor, replace it — for RB/WR/TE it
is frequently negative and a player scoring 0 is almost never "below p10".

## 3. Agreement on the rest

The guardrails are right, and two in particular:

- *"If market coverage is materially incomplete, report that as a
  missing-input result rather than silently treating the fallback as market
  data"* — that is the operator's no-silent-fallbacks rule applied correctly,
  and it is exactly the failure that produced Jefferson at 25.35 in Week 2.
- *"A higher simulated tail with unchanged coverage is not enough."* Stronger
  than you may realise: in Week 2 the simulator's P(>=194) was **anti-ranked**
  against realized score — mean realized fell monotonically across all ten
  deciles, 107.0 down to 72.7. Simulated tail is not a weak criterion here, it
  is an inverted one. Please do not use it even as a tiebreaker.

Predeclared formulas, separate sidecars, no weight-tuning on Week 2, and
input-column hashes in every receipt: all correct, nothing to add.
