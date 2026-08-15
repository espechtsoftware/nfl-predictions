# Review of the overtime prediction assessment

Date: 2026-08-15

Reviewed document:
`reports/2026-08-15-overtime-prediction-assessment.md`

Authoritative project result:
`reports/2026-08-15-overtime-fantasy-and-vegas-result.md`

## Disposition

The assessment is directionally right that overtime is a shared game-level
event and that ordinary spread is, at best, a weak predictor. Its principal
empirical table cannot be used for this project, however, because it pools
2015--2021 into the user-defined 2022/2025 rule-regime scope. The 2022 rule
change applied to the postseason, while the 2025 change extended guaranteed
possessions to regular-season overtime; the user explicitly excluded every
season before 2022 before the frozen project test was run.

The completed project result remains authoritative:

- use 2022--2024 regular-season games only to train the probability of reaching
  overtime;
- use 2025 regular-season games once as the untouched held-out evaluation;
- measure current-rule fantasy uplift only from 2025 regular-season play by
  play; and
- keep postseason overtime separate.

No lineup-construction, marginal, dependence or winning-line production change
is licensed by the assessment.

## Corrected spread-band measurement

The assessment's spread bands were recomputed directly from
`nfl_raw.schedules`, restricted to regular-season games with a closing spread
in the allowed seasons. The training and held-out periods are kept separate.

| period | absolute closing spread | games | OT games | OT rate |
|---|---:|---:|---:|---:|
| 2022--2024 train | 0--2.5 | 205 | 10 | 4.878% |
| 2022--2024 train | 3--5.5 | 333 | 22 | 6.607% |
| 2022--2024 train | 6--9.5 | 196 | 12 | 6.122% |
| 2022--2024 train | 10+ | 81 | 5 | 6.173% |
| 2025 heldout | 0--2.5 | 70 | 6 | 8.571% |
| 2025 heldout | 3--5.5 | 99 | 3 | 3.030% |
| 2025 heldout | 6--9.5 | 69 | 4 | 5.797% |
| 2025 heldout | 10+ | 34 | 1 | 2.941% |

The pooled 2015--2025 claim that 10+ spreads are the one reliable negative
signal does not reproduce in 2022--2024: that band had essentially the same OT
rate as the 3--5.5 and 6--9.5 bands. Its low 2025 rate is based on one event in
34 games and was already part of the spent held-out season. The apparent
3--5.5 relationship also reversed sharply between training and heldout.

This instability agrees with the frozen out-of-sample test. On 2025, the
2022--2024 spread-plus-total model had ROC-AUC 0.507, was slightly worse than
the training-base-rate model on Brier score and log loss, and placed four OT
games in both its highest- and lowest-risk quartiles.

## What the assessment gets right

1. Overtime is a shared game-level duration event, not an independent
   player-level mean adjustment.
2. Adding an unconditional expected-point bonus would double count value
   already embedded in game and player markets.
3. The forensic construction deficit cannot be repaired merely by adding a
   game-environment feature.
4. A direct, pre-lock sportsbook price for regulation ending tied would be a
   cleaner probability input than attempting to infer overtime from spread and
   total.

## Required corrections and qualifications

### The fantasy effect should use the measured value

The assessment's heuristic of roughly one possession each way is unnecessary.
The reconciled 2025 scorer measured the same play by play with and without the
overtime periods. Overtime added 23.77 skill-player DraftKings points per OT
game on average, including 10.12 points across the three largest individual
gains. It is a material tail event when it occurs, even though a small change
in its pregame probability may have little marginal expected value.

### The dependence sign is not established by teammate multiplicity alone

The simulator's excess teammate-exceedance multiplicity is a legitimate guard
against blindly adding more within-team co-boom. Overtime can also create
opponent run-backs and whole-game duration dependence, so that one diagnostic
does not by itself prove every mean- and marginal-preserving duration treatment
is wrong-signed. This distinction does not alter the present disposition,
because the required pre-lock probability signal failed out of sample.

### A winning-line feature is not yet available for free

With only the failed spread/total model, expected OT count is approximately the
base rate times slate size and adds little beyond the number of games. It should
not enter a winning-line model merely because realized overtime raises slate
scoring; realized overtime is unavailable at lock.

A winning-line candidate becomes legitimate only if a direct pre-lock OT/Draw
price or a separately frozen prospective probability model is available. Its
incremental value must then be tested against slate size, totals and the other
pre-lock slate features, without reusing 2025 as a fresh holdout.

### Direct market availability remains unverified

Secondary betting articles are not sufficient evidence that the relevant
market is available through the project's vendor, books and timestamps. The
existing project result therefore keeps one bounded, quota-audited 2026
availability probe for a regulation `h2h_3_way` Draw or an explicitly named OT
market. This is an availability check, not authorization to purchase or deploy
the signal.

## Final queue decision

- Keep production unchanged.
- Do not create another retrospective spread/total overtime arm.
- Preserve the one bounded 2026 direct-market availability probe.
- If a direct market exists, freeze collection, calibration and incremental
  winning-line/duration tests before observing 2026 outcomes.
- If it does not exist, close overtime as a measured but presently
  unpredictable tail mechanism.
