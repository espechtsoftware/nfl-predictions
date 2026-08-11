# Recommendation scoreboard / pivot reconciliation

Date: 2026-08-11

This tracked note reconciles the operator-supplied, untracked
`2026-08-11-recommendation-scoreboard-and-pivot.md` against the repository's
experiment ledger and code. It does not modify that outside review.

## Findings retained

- The review correctly retracts the pre-shaper `2.7x` q99 headline. The final
  served path exceeds q90/q95/q99 at `10.5794% / 5.4627% / 1.4774%`.
- The factor-1.025 Stage B result is mechanistically informative: it changed
  the 200 count `11 -> 13` but tied the incumbent at 210/220/230/240
  (`7/5/3/2`). Marginal widening is not the remaining 210+ lever.
- Re-slicing the closed marginal vendor families is not justified. Route Share
  remains a prospective centre-distribution shadow, not a demonstrated
  high-score promotion.
- Contest-aware expected-payout/duplication selection is genuinely distinct,
  but cannot be validated from winner-only rosters or aggregate ownership.
  It still requires full standings, contest size and payout metadata.

## Material correction: within-team allocation was already tested

Section 4.1 calls mean-preserving within-team Dirichlet allocation the one
structurally untested mechanism. That is factually inconsistent with the
tracked code and experiment ledger:

- `src/nfl_dfs/models/simulate.py` and `game_sim.py` implement
  `GAME_SIM_USAGE=dirichlet`, allocating team opportunity with a
  mean-preserving Dirichlet draw.
- The K=20 2025 arm scored mean weekly best `177.3` and `3/17` weeks at or
  above 194 versus the then-adopted possession-team control's `188.4` and
  `7/17`.
- The explicit K=8 retry later produced 11 tail weeks and mean `175.0`, a
  severe regression. The tracked disposition says not to tune another
  concentration on the known outcomes.
- The related corrected team touchdown-allocation ledger subsequently lost
  `19` versus `27` tail weeks on the full panel and is also closed.

Therefore the review's proposed cheap allocation diagnostic is not a new arm
and must not be rerun under a new label. The joint-tail diagnosis can be right
without making this already-failed mechanism new evidence.

## Infrastructure correction and action

The review also describes the 2026 Route Share infrastructure as fully built.
At review time, the weekly import, strict-prior features, operating contract
and gate were built, but the exact paired live registries and immutable
pre-candidate player-distribution capture were still only specified. The
current implementation milestone closes that gap with:

- isolated `tail_k1_route` and `tail_k1_route_role` registries;
- exact feature-contract checks preventing control/treatment contamination;
- Week 1 prior-season-only support and Week 2+ exact-W-1 fail-closed support;
- source-file SHA propagation into inference;
- create-only aligned base/role draw and component artifacts for both arms;
- a separate `shadow-k1-route-roleunion` command/job at the control times;
- no Route Share exposure to the production registry or submitted policy.

The remaining honest directions are prospective Route Share grading and the
contest/payout objective after complete 2026 standings exist. All previously
launched historical non-Fantasy-Points arms have concluded; live K1/K3/floor/
role/selector and data-collection shadows remain pending by design until real
2026 slates and outcomes arrive.
