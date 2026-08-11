# Frozen served-position calibration lineup experiment

Date frozen: 2026-08-11, before either new lineup panel exists.

## Question

Does the independently fitted, final-served per-position calibration improve
the highest score among exactly 80 selected lineups per slate under the
operator's standing tail-first objective?

This is the one lineup comparison licensed by the passing calibration report
in
`reports/served-position-calibration-runs/20260811-served-position-calibration-v1/report.json`.
It is not permission to refit factors after seeing lineup results.

## Fixed treatment

Apply the following mean-invariant spread factors after TabPFN marginal
shaping, the 45/55 prop-market mean shift, and the identity global served-tail
scale:

| Position | Factor |
|---|---:|
| QB | 0.970 |
| RB | 1.005 |
| TE | 0.940 |
| WR | 1.070 |

The transformation is applied to both base and direct-role worlds. It may
change neither a player's served mean nor any player input. No other replay,
generator, selector, seed, or model setting may differ.

## Frozen books

- Accepted historical/incumbent source:
  `20260810-lockfix-e80-k1-role12union-8677d21`.
- New same-image control:
  `20260811-lockfix-e80-k1-role12-position-control-v1`.
- New same-image treatment:
  `20260811-lockfix-e80-k1-role12-position-scales-v1`.
- New panels contain only evaluation seasons 2023, 2024 and 2025 (54 slates).
- The full 107-slate control/challenger books retain accepted source seasons
  2019, 2021 and 2022 unchanged and splice in the corresponding new
  evaluation panel.
- Every new slate must select exactly 80 lineups with CE 0, direct-role 12,
  boom 40, line-194 selector, `MODEL_ENSEMBLE=1`, role-belief seed 7331,
  replacement slots 12, and the accepted role feature list.

The two new panels must execute from the same immutable container digest and
code commit. Control must use an explicit identity position scale; treatment
must use exactly the four factors above.

## Mechanical validity gates

Before scores may determine a result:

1. Both new panels contain the exact 54 evaluation slates and 80 selected
   lineups per slate, complete labels, one config and seed identity, and the
   expected code commit.
2. New control reproduces accepted-source evaluation selected weekly maxima.
   Persisted player inputs and served means must match within their documented
   storage tolerance; differences caused only by code identity are allowed.
3. New control and treatment have identical player rows and numeric inputs.
   Every player served mean must agree within `1e-10` before persistence and
   within `1e-4` in persisted candidate means. Shared rosters must have equal
   realized scores.
4. All persisted levers are equal except `SERVED_POSITION_SCALES`, which is
   identity in control and the exact frozen specification in treatment.
5. Historical accepted-source seasons are unchanged in both full books.

Any failure makes the experiment invalid, not negative. Mechanical repairs
may not regenerate books or change this score law.

## Frozen decision law

Compare the highest realized score among the 80 selected lineups on each of
the 107 slates. Count weeks clearing `240`, `230`, `220`, `210`, and `200`, in
that order.

At the first threshold whose counts differ, treatment passes only if its count
is higher. A gain cannot be accepted if treatment loses at any higher
threshold. A tie through 200 is neutral. This is the standing operator law and
replaces the older season-stability veto and the older rule that stopped at
210.

Counts at 194 and 187, mean, median, pool oracle, season slices, candidate
counts, changed weeks, and position contributions to changed winning rosters
are mandatory diagnostics but are not vetoes and cannot rescue a loss under
the primary law.

## Interpretation and prohibition

- Pass: licenses consideration for research-incumbent and live-policy adoption
  after mechanism review; it is not automatic production mutation.
- Neutral/fail: closes this exact four-factor arm. Do not tune any factor from
  lineup outcomes.
- No second position-factor grid, season-specific factor, or score-selected
  correction is permitted from this result.
