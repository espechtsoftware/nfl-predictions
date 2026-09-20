# Tail-selector experiment specification

The historical paid-source and admission studies leave the main measurable weakness in the selector. The simulated pool contains 194–202 point candidates, yet the current coverage selector does not consistently place those realized-tail candidates in the first entries. The next test should target that failure directly.

## Frozen comparison

Keep the delivered candidate pool, projection arrays, world draws, salary/roster rules, and entry count fixed. Compare:

1. the current `dual_emax`/coverage selector;
2. the registered `cap_prefix_then_fill` ladder (`194/200/210/220`, ladder lengths `1/2/6/12`, gamma `4`);
3. a tail-count blend that ranks by `mean_world_score + gamma * tail_count`, with gamma frozen before outcome reads;
4. a calibrated upper-tail probability rank, using only simulated-world scores and a calibration fit from earlier seasons.

The blend and calibration parameters must be frozen on pre-outcome seasons. No SIS, Fantasy Points, or realized-score fields may enter the selector.

## Primary read

For each slate and K = 20, 40, 80, report:

- realized maximum points;
- number and fraction of selected lineups scoring at least 220, 210, and 200;
- rank of the realized best lineup and the best 220+ lineup;
- whether any 220+ lineup appears in the first 20;
- finish percentile against the fixed ownership field.

The primary selector endpoint should be 220+ capture at K20, with realized K20 maximum as a co-primary. Average simulated score is diagnostic only, because it already fails to distinguish the relevant tail.

## Guardrails

Use paired weekly comparisons, season and leave-one-season-out intervals, and a frozen selector receipt containing code SHA, input hashes, parameter values, information cutoff, and candidate-pool identity. Read realized outcomes only after every selector book is frozen. A selector is eligible for prospective shadowing only if it improves 220+ K20 capture without materially reducing realized K20 maximum or causing infeasible books.

This test addresses the remaining selection gap directly. It should run independently of the paid-source renewal decision; the recovered paid-source artifacts remain frozen controls, not additional tuning inputs.

