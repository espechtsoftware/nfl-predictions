# Prospective 220→210→200 selector shadow

Status: frozen before any 2026 outcome; implementation, full validation and
paused-job deployment complete. No off-season job was executed.

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
policy `tail-first-v6-20260810`. The prior books remain unchanged. A later
operator-policy amendment adds the same frozen extreme rule to the promoted
role-union candidate pool as a second prospective selector; the original K1
book and its no-outcome rule are unchanged.

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

## Deployment

Implementation commit `d1c9318` passed full Cloud Build
`9e3e6c14-f70a-4f8d-9863-7120c5fae74f` with 721 tests passed and 2 skipped.
Validated immutable digest:
`sha256:75daf1607c2f08197d1357c10702434161b1093cff2a21e8cdc7ca7d5bcdf95c`.

Only `shadow-k1`, `shadow-k1-nofloor`, `shadow-k3`, `freeze-tail-early` and
`freeze-tail-late` were repinned to that digest. The three generators record
`CODE_SHA=d1c9318` and retain their prior commands, variants, K, possession
mode, generator budgets, salary floors, 45/55 blend, 30,000 worlds, artifacts,
4 CPU / 8Gi, retry and timeout settings. The two freezers retain 1 CPU / 1Gi
and their exact early/late commands. All eight associated schedulers remain
PAUSED on their original Sunday CT schedules. No live app or adopted policy
changed.
