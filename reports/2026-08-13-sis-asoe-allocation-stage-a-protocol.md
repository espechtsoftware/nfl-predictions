# SIS ASOE conditional target-allocation Stage A protocol

Date frozen: 2026-08-13, after the registered opportunity-only acquisition
passed but before any historical player target count, allocation likelihood,
dependence statistic, candidate score or lineup score is read for this arm.

## Question and control

Does a defense's strictly-prior Wide-versus-Slot attempt share, after
adjusting for the alignment tendencies of the offenses it faced, improve the
within-team allocation of targets to receivers with different Wide/Slot route
profiles?

The control is the accepted target-allocation law:

- the existing walk-forward component target means used by
  `analysis/usage_dirichlet_calibration.py`;
- within-team Dirichlet concentration
  `K = 28.154043586960896`; and
- historical panel identity
  `20260811-pitclean-e80-k1-role12union-a12ab31`.

Stage A is score-free. It may read actual target counts solely for the
conditional allocation likelihood below. It may not read fantasy points,
lineup scores, ownership, contest outcomes, candidate membership or weekly
maxima.

## Immutable point-in-time inputs

Use only the two completed, hash-bound acquisitions:

- SIS `team-pass-defense-asoe-v1`: Team Pass Defense Totals, game grain,
  receiver position WR, all coverage schemes, separately Wide and Slot,
  seasons 2022--2025; only `Att` and identity/scope fields are consumed.
- Fantasy Points run
  `20260813T202926Z__same-season-alignment-last-four-v1`: Receiving
  Separation by Alignment, Player context, target Weeks 5--18, with every
  source window exactly `W-4..W-1`; only Overall, Wide, Slot and Inline route
  counts plus identity/support fields are consumed.

For a target Week W, filter both sources to source weeks W-4 through W-1.
No target-week row is allowed. Reconstruct a missing SIS alignment cell as
zero only against a project-schedule team-game spine; never infer a missing
game from silence.

## Fixed ASOE construction

For each offense team and target week, compute its prior-window Wide share as

`off_wide = sum(Wide RTE) / sum(Wide RTE + Slot RTE)`

over WR/TE rows assigned to exactly one canonical team. The offense profile is
valid when its Wide+Slot route denominator is at least 80.

For each defense and target week:

1. sum its Wide and Slot SIS attempts over W-4..W-1;
2. require at least 40 combined attempts;
3. compute observed Wide share from those two buckets;
4. compute schedule-expected Wide share as the combined-attempt-weighted mean
   of the prior-window `off_wide` values for the offenses it faced;
5. require those offense profiles to cover at least 80% of its combined
   attempts; and
6. set
   `ASOE = (observed_wide - expected_wide) * attempts/(attempts + 40)`.

The shrinkage constant, denominators and support floors are fixed. No yard,
completion, touchdown, interception or SIS Value metric may enter ASOE.

For each resolved WR/TE, compute `player_wide = Wide RTE/(Wide RTE + Slot
RTE)` when the player has at least 20 such routes and belongs to exactly one
canonical team. Its matchup score is

`s_i = defense_ASOE * (player_wide - offense_wide)`.

RBs, unresolved/split rows and unsupported WR/TE rows receive score zero.

## Fixed conditional allocation law

Build the same active-player target groups and control probabilities as
`analysis/usage_dirichlet_calibration.py`. Retain target Weeks 5--18 only.
For each team-week group, map its opponent defense from the PIT-clean panel.
A group has valid ASOE geometry only when:

- its opponent defense ASOE is valid;
- at least two players have supported alignment scores;
- supported players contain at least 50% of the control target probability;
  and
- the supported scores are nonconstant.

Within a valid group, center scores under the control probabilities and form

`q_i(beta) = p_i * exp(beta * (s_i - sum_j p_j s_j)) / Z`.

Invalid groups fall back exactly to `q=p`. Control and treatment both use the
accepted Dirichlet concentration K; only their centers differ.

Fit one nonnegative beta on 2022 target groups only. Use bounds `[0, 8]`,
`scipy.optimize.minimize_scalar(method="bounded", xatol=1e-6)`, and objective

`mean Dirichlet-multinomial NLL + 0.01 * beta^2`.

Also score beta 0 and both endpoints; objective ties within `1e-10` select the
coefficient closest to zero. Seasons 2023--2025 are untouched evaluation.

## Tail-aligned Stage A gate

The arm passes Stage A only if all of the following hold:

1. all hashes/scopes validate, every joined source week is `< target_week`,
   the schedule join is one-to-one, and treatment probabilities are finite,
   positive and sum to one;
2. valid ASOE geometry covers at least 50% of retained target groups in each
   evaluation season;
3. fitted beta is at least 0.01 and produces at least two distinct treatment
   probability vectors in evaluation; and
4. aggregate 2023--2025 mean target-allocation NLL per group is lower for
   treatment than control.

Per-season changes and a fixed 2,000-resample team-week clustered bootstrap
(seed 8,113,126) are reported as diagnostics, not vetoes. That is deliberate:
the operator's objective is weekly portfolio tail capture, and the later
exact-80 comparison—not an average-stability proxy—must decide scoring value.

A pass licenses a separately frozen mean-preserving final-served treatment:
tilt only within-team target allocation centers by this fitted law, leave
carries and all other mechanisms unchanged, and transport the resulting draws
back to the accepted player marginal distributions before the exact-80
comparison. A failure closes only this team-ASOE conditional allocation law;
the already identified player-grain SIS denominator branch remains open and
must not be dismissed by this result.
