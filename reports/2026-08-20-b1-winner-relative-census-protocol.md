# Frozen protocol: B1 generated-union versus the Milly winner

**Protocol ID:** `20260820-b1-winner-relative-census-v1`  
**Status:** FROZEN 2026-08-20 after the outcome-blind real-artifact smoke  
**Class:** one-shot descriptive census; outcome-facing; licenses no adoption,
rule change, selector change, fit, tuning, or family closure.

## One question

Across the exact frozen B1 union of 51 registered panels, 54 slates and
127,778 distinct DK-legal rosters that were actually generated, does the best
roster on each of the 51 slates with a tracked Millionaire-Maker winner beat,
tie, finish within 10, finish within 25, or finish farther than 25 points behind
that winner? If any generated roster beats or ties the winner, preserve its
exact identity, source family/panel/generator tags, selected status and
construction anatomy.

This is the missing drill-down beneath the committed B1 aggregate. The B1
result preserved union mean C=198.0956 and its score grid, but not per-slate
roster identities or same-week winner margins; it therefore cannot answer this
question without one source-locked read.

## Frozen population and sources

- Candidate population: the exact `ALL_PANELS` list in
  `scripts/run_b1_union_c_census.py`, queried from
  `nfl_predictions.replay_candidates_staging` with no panel added or removed.
- Canonical slate catalog: `nfl_predictions.slate_player_features`, panel
  `20260815-atlas-money-worlds-r0-v1`.
- Winner lines: the 51 2023-2025 entries in
  `src/nfl_dfs/backtest/real_lines.py`. The extra 2019 entries are outside the
  B1 slate intersection and are not evaluated.
- B1's legality contract is retained exactly: nine unique catalogued players,
  salary in `(0, 50000]`, one QB, one DST and the DK RB/WR/TE shape. The $49k
  floor and QB-stack/bring-back mandates are not re-imposed; B1 froze them as
  strategy constraints rather than DK legality.

The execution fails closed unless it reproduces all of these source facts:
51 panels, 54 slates, 127,778 distinct legal generated rosters, zero legality
drops, zero candidate-label versus canonical-snapshot score mismatches and 51
matched winner slates.

## Frozen computation

1. Canonicalize every generated roster as its sorted nine-player ID set. A
   roster appearing in several panels remains one roster with every source
   record retained.
2. Revalue it from the canonical snapshot's player actuals and require exact
   agreement at published hundredth-point precision with every stored
   `actual_score`. A mismatch aborts; it is never reconciled by choosing the
   larger value.
3. Normalize candidate and winner scores to integer hundredths before the
   comparison. Mutually exclusive best-roster classes are `beat` (>0 margin),
   `tie` (=0), `within_10_loss` (0 to -10 inclusive at -10),
   `within_25_loss` (below -10 through -25 inclusive), and `outside_25`.
   Cumulative within-10-or-better and within-25-or-better counts are also
   reported.
4. For every matched slate, retain the exact best roster(s), score/margin,
   count of all generated rosters in each winner-relative band, every source
   panel/family/tag, whether and where the roster was selected, and anatomy:
   players, salary and position spend, FLEX position, QB stack, bring-back,
   games/teams represented and maximum game/team concentration.
5. Preserve the same exact information for every distinct generated roster
   that beat or tied its same-week winner, plus their aggregate anatomy. No
   arbitrary top-N or representative sampling is allowed.

## Population separation (load-bearing)

`C` here means a roster actually emitted by one of the 51 B1 panels. `S` is
recorded only as that generated roster's pre-existing selected flag/rank. The
runner has no H/P/world-optimum input and the result must state:

- `contains_only_actually_generated_rosters=true`;
- `contains_hindsight_h_or_p=false`;
- `contains_simulated_world_optima=false`.

H, P and simulated-world optima may be discussed beside the result only in a
separately labeled comparison; they can never be counted as corpus members or
as a lineup the generator produced pre-lock.

## Exact pins

- Original B1 protocol:
  `2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789`
- Committed B1 report:
  `4e654a58563391ed3020b0b221756070cd07fb10e962fc80e4bbedfd5f2631b6`
- Original B1 runner:
  `fc12e2871d638995603258f16d9e1beeee68f8a885ba3a53f9f32790d62c608f`
- Winner-line source:
  `13b7a7a1647fe9070b1e8583c9fc579c8fe882b1124e85eaa53d587de2759eb5`
- Census module:
  `c5892baa372930a53a2a90961dde7bcf4d317e244be21e0bc2051c7f27edbbaa`
- Runner:
  `5c9fb3308108ab165270c70fd4243974e8c14aa84a1c4bd4d97056775cb59d09`
- Focused tests:
  `377fd768deae2aafe69a5ca2d645872315f2769c42a119fb4d28e8f0d87a7a4f`

## Outcome-blind real-artifact smoke (completed before freeze)

Exactly one smoke ran on 2023 Week 1. Its SQL selected candidate identities,
legality/catalog fields and selected metadata only; neither query selected
`actual` nor `actual_score`, and the receipt records
`realized_outcome_columns_read=[]`.

- Result: `OUTCOME_BLIND_REALITY_SMOKE_OK`
- Candidate rows: 13,008; panels: 51; selected rows: 4,080
- Canonical player rows: 773
- Candidate query job: `53f85813-b121-4d6a-82f2-aad6428b787b`
- Player query job: `4c5ac526-24b2-4c78-ac7f-51d6bf20f134`
- Create-only receipt:
  `reports/b1-winner-relative-census-runs/20260820-b1-winner-relative-census-v1/outcome-blind-smoke.json`
- Receipt SHA-256:
  `520310de8bc3e17a877f1b19ae6aeb9f7e53c7daa74fad45e7f7b7fa40b1a5bb`

## Execution and reading rule

Do not execute until the root orchestrator confirms the historical-outcome
lane is free. Then run the frozen runner once, locally and serially, with the
exact protocol SHA supplied. The runner records both BigQuery job IDs, query
hashes, table metadata, row counts and deterministic content hashes, and
writes the result plus SHA create-only.

The census is descriptive. A generated winner-beater is evidence about a
missed construction/selection case, not authorization to derive retrospective
weights from that roster. Zero winner-beaters is equally a result and does not
authorize relaxing a rule. Any production response still requires a separate
outcome-unseen, fixed-budget arm or prospective shadow under the standing
acceptance policy.
