# Prospective 220→210→200 selector shadow

Status: frozen before any 2026 outcome; implementation and focused validation
complete, with full cloud validation and paused-job deployment pending.

## Motivation

The operator prefers one exceptional lineup from an 80-entry portfolio over
a higher average weekly maximum. The adopted selector greedily covers
simulated worlds at 194. Outcome-viewed historical diagnostics support
prospective 187 and 200 alternatives, but the accepted historical rows did
not retain exact 210/220 support masks and must not be resimulated or mined to
choose an extreme-tail rule.

This shadow is defined from the utility statement alone. It cannot replace
the adopted/UI 194 book based on historical scores.

## Frozen source and rule

The live K=1, K=1 no-floor and K=3 shadow generators keep their existing
model, slate, 80-entry, salary-floor, 194 selection, candidate-generation and
simulation settings. Candidate persistence adds exact full-length support
masks at 210 and 220 beside the existing 187/194/200 masks. This changes no
generated or selected source roster.

Only the K=1 source pool receives the new portfolio
`tail_k1_extreme_lex_220_210_200`. Starting with no covered worlds, choose the
next roster by the following lexicographic key:

1. newly covered 220-point worlds;
2. newly covered 210-point worlds;
3. newly covered 200-point worlds;
4. individual probability at 220, then 210, then 200;
5. simulated mean; and
6. lower persisted candidate index.

Update all three covered-world masks after each choice and repeat to 80
distinct rosters. Freeze at both existing early and late snapshots under
policy `tail-first-v5-20260810`. The prior eight books remain unchanged in
the same policy; this ninth book is additive.

## Validation and grading

Before deployment, prove:

- 210/220 masks decode to the complete declared world count;
- per candidate, support is nested 220 ⊆ 210 ⊆ 200;
- the lexicographic priority and all tiebreakers are deterministic;
- persisted 194 source selection still reproduces exactly;
- every book contains 80 distinct rosters; and
- the freezer fails closed if any source job still emits the older schema.

Do not execute an off-season freezer. During the season, grade only after
authoritative points arrive and report paired weekly maxima and the complete
187/194/200/210/220/230/240 grid versus the same-snapshot K=1 194 control.
No adoption threshold is invented before a useful number of independent live
weeks accumulates. This is prospective evidence collection, not a historical
arm or a reason to change the UI.
