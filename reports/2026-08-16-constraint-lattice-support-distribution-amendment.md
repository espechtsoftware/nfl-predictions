# Constraint-lattice support-distribution amendment

Date frozen: 2026-08-16, before the control-support census was launched and
before any support shard or count existed.

Applies to:
`20260816-constraint-lattice-control-support-census-v1`.

This amendment adds outcome-blind distribution diagnostics to the already
frozen support census. It does not alter the 230/220/210 anchor order or the
predeclared adequacy law of at least 540 control events and at least 41/54
positive slates in every R0--R4 block.

## Added output

For each block and each p194/p210/p220/p230 threshold, the strict aggregate
must retain the complete 54-slate control-count vector and report:

- event count and number of positive slates;
- share of events contributed by the top 1, 3, 5 and 10 slates;
- Herfindahl concentration across the 54 slate shares and its reciprocal
  effective-slate count; and
- median and maximum event count among positive slates.

For each threshold it must also report the ten pairwise Pearson correlations
between the 54-slate count vectors for R0--R4, plus the mean and maximum
absolute finite correlation. A zero-variance pair is reported as `null`, not
coerced to zero.

These quantities use only simulated control-book coverage. Treatment,
exception, effect and realized-outcome fields remain forbidden.

## Interpretation boundary

The positive-slate minimum is the frozen concentration guard. The newly added
top-share, effective-slate and fold-correlation values are descriptive and
must be published regardless of disposition; they may not introduce a new
cutoff after the counts are observed. In particular, the five held-out block
statistics share the same slates, players, salaries and features. Their
correlation must be explicit, and a 3-of-5 scientific result may be described
as seed robustness only--never as five independent replications or evidence
against simulator misspecification.

If the existing support law selects p220/p210 or declares insufficient
support, a new scientific design must still be frozen before treatment. The
added diagnostics cannot be used to rescue p230 or choose a different anchor.
