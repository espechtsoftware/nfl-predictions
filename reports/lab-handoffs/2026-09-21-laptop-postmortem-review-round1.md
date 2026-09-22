# Independent Week-2 review: first findings and requested corrections

I am actively reviewing the 29e96ac post-mortem under Erich's instruction. The shared-handoff systemd monitor is active with a 300-second fetch interval. This is an initial review, not acceptance of the whole report or Tuesday handover.

## Bank attribution reproduced

Joined all 12,555 candidates one-to-one by cand, asserted roster display strings equal, verified both archived bank SHA256 values, and recomputed lineup means with original float32 roster summation. Outcomes are your released DK-derived table; this independently checks model scoring and attribution, not the original standings-to-player parsing.

| scoring mean | correlation with realized | bottom decile realized | top decile realized |
|---|---:|---:|---:|
| incumbent | -0.487938 | 109.357 | 69.818 |
| corrected HSIM | -0.087385 | 96.652 | 90.833 |
| equal-mass pooled | -0.332011 | 105.062 | 79.540 |
| stored sel_mean | -0.487938 | 109.357 | 69.818 |

`sel_mean` reproduces the incumbent correlation; it is not the pooled dual decision mean. Pooled minus stored means differ by up to 10.872 points. Both components need work, but the severe reported inversion is primarily incumbent. Within boom alone correlations are -0.359 incumbent, -0.037 HSIM, -0.196 pooled. This rules out generator-tag mixing as the whole explanation. No weight change follows from one slate. Evidence and executable are in receipts/2026-09-21-independent-review/.

## Corrections and next evidence requested

1. Trace Jefferson's actual pre-blend value and every downstream transform at the serving commit. Inverting a nominal 0.45 weight is not a substitute for the calculation. Season-partitioned windows alone do not prove a new defect or justify classifying cross-season training-feature changes as a repair; compare the training and serving contracts and historical cold-start behavior.
2. Report exact introduced commit, reproducer, affected outputs, regression test, and fixed-path replay for each confirmed bug. Separate missing telemetry from missing money-path inputs (zero own_shadow does not alone prove which ownership input generation consumed).
3. Compare caps using the SAME selector objective, eligible pool, statuses, K and contest assignment. Mean-sort with caps versus delivered dual Emax changes more than exposure policy. The present result is exploratory, not an isolated cap effect.
4. Verify the claimed stack counts: prior frozen delivery review counted 87 depth-2, 8 depth-3, 2 depth-4. Define whether stack depth includes TE/FLEX/RB before reporting 100% depth-2. Check pairwise overlap definition: six heavy exposures make the reported 1.60 worth reconciling directly from canonical nine-player sets.
5. Keep all proposed numerical caps/rules exploratory until compared fairly. Honor Erich's request to limit injured-player concentration; provide a concrete constrained-selection option, per-contest exposures, feasibility and score tradeoffs. Do not infer missing props equals medical unavailability; distinguish feed gaps and observation times.
6. Winner-only studies cannot establish an edge. Compare all entrants stratified by entry count, salary, and contest; separate player decisions from entry-volume advantage. Show pre-lock signals for misses and successes, not just retrospective winner traits. Avoid calling surprise players inherently unforecastable.
7. Standings validator: reconcile tie rows, entry counts, duplicate exports and rounded ownership summaries before widening tolerance. Preserve raw hashes and import rejected-row evidence. Never silently alter roster or FPTS reconciliation.
8. Tuesday handover needs actual deployed code/image identities, pending versus completed fixes, local/remote schedules, end-to-end rehearsal, and explicit unresolved risks.

Please send incremental fixes and evidence as completed. I will review each rather than wait for the final report. Main heavy-lifting ownership stays with production as Erich requested.
