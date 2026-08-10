# Corrected-history extreme-selector confirmation

Status: preregistered before any corrected K3 or K1 panel outcome was queried.
The selector was already frozen and deployed as a paused prospective 2026
shadow before this confirmation was defined.

## Question

The operator's utility compares the submitted weekly maximum at 240, then
230, 220 and 210, while the current production book selects 80 entries by
simulated coverage at 194. Does the already-frozen deterministic
220→210→200 selector improve the same final corrected candidate pool under
the operator's high-to-low tail law?

This is one confirmation, not a selector search. The 187/194/200 coverage,
top-p, one-swap, mixed-book and any new threshold or weighting variants are
excluded from this historical decision. They remain prospective shadows.

## Frozen source and construction

Wait for the point-in-time-corrected K3→K1→CE12→role-union chain to finish.
Use exactly the mechanically accepted generator pool selected by that chain;
do not choose a different source based on this selector's result. The source
must contain all 107 slates, authoritative actuals, complete 187/194/200/210/
220 support masks, and exactly 80 persisted selections per slate.

First reproduce the persisted 194-coverage book exactly. Then apply the
already-deployed `extreme_lexicographic_order` without modification:

1. maximize newly covered simulated worlds at 220;
2. then newly covered worlds at 210;
3. then newly covered worlds at 200;
4. break ties by individual probabilities at 220, 210 and 200, simulated
   mean, then lower candidate index; and
5. stop at exactly 80 unique lineups.

Candidate generation, simulated worlds, support masks, projections, actuals,
salary floor and entry count are identical. The pool oracle is therefore
identical by construction.

## Decision

After every mechanical check passes, compare realized weekly-maximum counts
from 240 downward through 230, 220 and 210. Promote the extreme selector if
the first nonzero difference is positive; retain 194 coverage if it is
negative or all four counts tie. Report 200/194/187, mean/median, paired
wins/ties/losses, season detail, selected-slot movement and the unchanged
pool oracle as diagnostics. A gain at a higher threshold can outweigh losses
below it, matching the operator's documented objective.

No selector parameter, threshold, ordering, source pool or retry may change
after the corrected score result is read. A valid rejection leaves the
prospective 2026 shadow in place but does not change the Week 1 UI policy.
