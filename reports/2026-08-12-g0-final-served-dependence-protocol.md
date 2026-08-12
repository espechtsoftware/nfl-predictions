# G0 final-served dependence premise protocol

Frozen 2026-08-12 before the terminal team-passing final-served result, before
the terminal cache selection, and before any G0 realized or simulated cell was
computed. This implements G0 from
`reports/2026-08-11-graph-dependence-research-queue.md` and incorporates the
accepted corrections in `reports/2026-08-11-graph-queue-review-notes.md`.

G0 is a score-free premise test. It reads player outcomes solely to grade the
already-generated final-served joint distribution. It does not generate,
select, or score lineups.

## Immutable terminal identity

G0 may launch only after the marginal queue writes
`reports/tabpfn-team-qb-runs/20260812-tabpfn-team-qb-exact80-v1-pit-clean/selected_team_qb.txt`.
The execution manifest must bind:

- the selected cache table and its complete table metadata/checksum;
- the selected repaired panel and selected evaluation panel;
- active-label, SCHED, team-passing and fitted-K terminal selection hashes;
- the team-passing final-served report hash and the selected arm's exact
  walk-forward position-factor schedule from that report;
- the immutable CPU image digest and code SHA;
- the common simulator, market-blend, seed and draw-count law.

The selected arm is resolved mechanically. Use the treatment schedule only
when `team_qb_selected=true`; otherwise use the control schedule. The cache
must equal the table in `selected_team_qb.txt`. If that selected cache or
served schedule changes before G2 launches, G0 and every dependent G1 artifact
are stale and must be rerun.

## Population and threshold

- Evaluation seasons: 2023, 2024 and 2025 only.
- Exact accepted Sunday-main, `research_eligible`, active player keys from the
  selected repaired panel; positions QB/RB/WR/TE.
- Reproduce the terminal cache, 45/55 model/market blend, accepted fitted-K
  usage law and target-season position factors with 10,000 draws and seed 0.
- A player's boom threshold is that row's point-in-time final-served q90 from
  those corrected draws. `actual > q90` is the realized flag; a simulated draw
  strictly above the identical row threshold is its simulated flag.
- The primary support includes rows whose final-served mean is at least 4.0
  DK points. A team-week must contain at least three supported players for
  multiplicity. QB-conditioned cells additionally require exactly one
  supported active QB for that team-week. No target outcome is used to define
  support or threshold.

The report must prove exact key/actual/team/position alignment, 100% selected
cache coverage, finite ordered draws, exact selected schedule identity, and
maximum mean drift at most `1e-10` before a scientific disposition is valid.

## Registered cells and estimands

The nine primary cells are fixed:

1. Team-week count of q90 exceeders at `>=2`, `>=3`, and `>=4`.
2. Same-team QB -> WR, QB -> TE, and QB -> RB conditional lift.
3. Same-team WR <-> WR, RB <-> RB, and TE <-> TE conditional lift.

For every team-week, compute the independent count distribution from its own
heterogeneous simulated player exceedance probabilities using exact
Poisson-binomial recursion. The multiplicity estimand is event rate divided by
the mean team-specific Poisson-binomial tail probability. Report a pooled
binomial comparison only as a labeled diagnostic; it is never a gate input.

For QB -> X, lift is
`P(X boom | QB boom) / P(X boom | QB not boom)` over supported same-team
QB/X pairs. For same-position cells, use both directed orientations of every
unordered teammate pair and compute
`P(B boom | A boom) / P(B boom | A not boom)`. Apply the identical pair set
and formula to realized flags and every simulated world. The comparison scale
for all cells is `log(simulated estimand / realized estimand)`.

## Support and uncertainty

- Each multiplicity cell requires at least 500 qualifying team-weeks; `>=4`
  additionally requires at least eight realized events and at least five
  Poisson-binomial expected events.
- Each conditional cell requires at least 500 directed pair-teamweeks, at
  least 30 realized conditioning-boom rows, and nonzero boom/non-boom
  denominators in both realized and simulated calculations.
- Estimate paired 95% intervals for each log gap with 2,000 deterministic
  bootstrap resamples of whole `(season, week)` slates, seed 1701. Resampling
  a slate retains all of its teams and player pairs. Monte Carlo worlds are
  not treated as independent observational evidence.

Unsupported cells remain reported but cannot establish equivalence or license
a dependence mechanism.

## Frozen equivalence and materiality bands

The symmetric practical-equivalence bands on absolute log gap are:

| Cell | Band |
|---|---:|
| multiplicity `>=2` | `log(1.10)` |
| multiplicity `>=3` | `log(1.15)` |
| multiplicity `>=4` | `log(1.25)` |
| QB -> WR/TE/RB | `log(1.15)` |
| WR-WR, RB-RB, TE-TE | `log(1.15)` |

A supported cell is **equivalent** only when its entire paired 95% interval is
inside its band. It is a **material miss** only when its point gap is outside
the band and its entire paired 95% interval is strictly on one side of zero.
This separates practical mismatch from sampling noise instead of declaring a
win from a tiny significant difference.

## Decision

- `dependence-premise-reproduced`: all nine cells are supported and
  equivalent. Close G1 and G2.
- `dependence-premise-miss`: at least one supported cell is a material miss.
  License the preregistered, score-free G1 walk-forward archetype topology.
- `dependence-premise-inconclusive`: neither rule holds. Do not license G1/G2
  from this sample; retain the diagnostic for additional prospective data.

The three directional predictions from the prior outcome-viewed review remain
falsifiable diagnostics, not extra gates: production overstates WR-WR lift,
understates QB-WR lift, and understates `>=4` multiplicity. G0 must report each
sign even if a different registered cell determines the disposition.

No cell, band, support rule, bootstrap setting, position/mean filter, or
decision branch may change after the first G0 outcome or simulated metric is
visible. Any later sensitivity analysis is labeled exploratory and cannot
license G1 or G2.
