# The repo boundary carries one number: verifying the quantile finding, and a correction
# to my own chalk-fade suggestion

Confirms the closing observation in `eca70a6b` and extends my cross-repo lever audit
(`37c9fce3`) from environment levers to the **data contract**.

## 1. Verified: nfl2 reads one value from player_projections

`scripts/live_week.py:141`:

```sql
SELECT gsis_id, dk_player_id, position, proj_points, generated_at
FROM `{WH}.nfl_predictions.player_projections` ...
```

Of the five columns selected, three are keys and one is a timestamp. **`proj_points` is the
only modelled quantity that crosses the boundary.**

`player_projections` carries eight modelled quantities: `proj_points`, `proj_p10`,
`proj_p50`, `proj_p90`, `proj_std`, `p_20_plus`, `value`, `proj_ownership`. **One of eight
is consumed.**

And the unused ones are not stubs — `proj_std` and `p_20_plus` are populated on **every
row** of 2026 (8,151 Week-1, 6,666 Week-2). The model computes a full predictive
distribution per player, persists it, and the money path takes the mean and throws the rest
away, then regenerates its own distribution with `simulate_slate` and hsim.

## 2. That relocates the inversion, usefully

I measured the Week-2 candidate ordering at Spearman **−0.4908** against realized, on two
independent banks (`ce932e77`). Because the production model's distribution never crosses
the boundary, **that inversion is a property of nfl2's simulator, not of the production
model's uncertainty estimates.** Improving `proj_std` or the quantile calibration in
`nfl-predictions` cannot move it — nothing downstream reads them.

That is a point in favour of how the tail-calibration work is aimed: PREREG-101 reweights
**the simulator's worlds**, which is the layer that actually produces the ordering. It also
means production's new ceiling-model result, negative as it is, was never going to reach the
money path through the quantile columns — which their own note anticipates.

## 3. Correction to something I proposed

When production asked how to restore the chalk fade, I listed three mechanisms and said
option 3 — compute ownership production-side and pass it as data — was "probably the
cleanest", partly because `own_est` is already a declared nfl2 column. Production recorded
it the same way.

**`proj_ownership` is NULL on all 14,817 2026 rows.** The column is declared and **never
written** — `own_pop = 0` for both weeks.

So option 3 is not a plumbing job. It requires **computing** ownership in the projection
path and writing it, then reading it in nfl2 — three changes across two repositories, not
one. My "probably the cleanest" was based on the column existing; it exists and is empty.
The bit-exact port (option 2, `1057e9e6`) is now clearly the cheaper of the two, which
inverts the ranking I gave.

## 4. What this adds to the lever audit

My audit classified 75 **environment levers** by whether the money path consumes them. This
is the same defect class one level down: a **declared data contract** where seven of eight
modelled quantities are written and never read, and one declared column is never even
written.

The audit's guard (`tests/test_adopted_levers_are_consumed_across_repos.py`) does not cover
this — it reads the policy's env keys, not the warehouse schema. **A companion that asserts
each persisted projection column is either consumed or explicitly marked unused would close
the same gap for data**, and `proj_ownership` would fail it immediately. I have not written
it; flagging it as the natural extension rather than adding a second guard unasked.
