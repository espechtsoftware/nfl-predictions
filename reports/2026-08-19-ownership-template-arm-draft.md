# Ownership-template carved-budget arm — DRAFT (B lane, NOT FROZEN)

**Status:** draft, 2026-08-19. Queued THIRD in the generation lane
(behind the all-boom read and the stack-relaxation arm) per the
one-lever-at-a-time law. Licenses nothing.

## Motivating evidence (winner anatomy B, report `597787ac…`)

All 51 tracked winners profiled from actual Millionaire ownership:
median cumulative ownership 104.5% (q25 79.4, q75 135.0) with a median
of 4 players under 10% — a recognizable chalk-core-plus-leverage
template, spanning 2.7% to 181% total. Finding A says our pool already
holds chalk and leverage but combines them toward winners no better
than chance; this arm tests whether imposing the measured SHAPE on a
carve of solves closes any of that gap.

## Proposed design (single lever, fixed budget)

- k of the 40 boom solves (k decided at freeze; same carve logic as the
  stack-relaxation arm, interleaved ranks) add two constraints in
  PREDICTED-ownership space (`own_est`, point-in-time by construction):
  at least one anchor at own_est >= 20% and at least 4 players at
  own_est < 10%.
- Implementation seam already exists: the dormant `MIN_LOWOWN` /
  `OWN_BARBELL_*` lever family in the engine's registered lever set —
  survey before freeze whether they express exactly this template or
  need one new lever (which must register in `_lever_keys`).
- Control: registered natives, exact-paired; co-primary scoring block;
  anatomy mechanism gate (winner-overlap vs chance null) mandatory.

## The honest dependency: predicted vs realized ownership

The template was measured in REALIZED ownership; generation can only
constrain PREDICTED. Before this arm freezes, grade the own_est →
realized mapping on the 51 winner slates (own_shadow machinery exists;
contest_ownership now covers 2022–2025): if own_est cannot separate
sub-10% from 20%+ players at useful precision, this arm is dead on
arrival and must wait for the Week-1+ field data. That grading is
descriptive and can run any time.

## Sequencing

All-boom read → stack-relaxation freeze/run → own_est calibration check
→ this arm's freeze (operator k + calibration verdict recorded). Any
combination with stack relaxation (open solves + template) is a LATER
factorial question, never a first test.
