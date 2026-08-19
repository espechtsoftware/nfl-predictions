# Winner-world optima protocol (N1c) — FROZEN 2026-08-19

**Protocol id:** `20260819-winner-world-optima-v1`. Operator direction:
"please proceed as you recommend" (2026-08-19), following the frozen
N1/N1b winner-law audit and its same-day field-max-confound addendum.
One-shot: this protocol executes exactly once per version; any defect
found after execution requires a new version, never a silent rerun.

## Question

N1b proved every tracked winner outscores the registered pool in a
median 448 archived worlds (best boom ranks min 41 / median 57), but a
generating world only proves the winner beats OUR pool there. This audit
settles whether a per-world solver visiting that world would have BUILT
the winner: for each winner's best generating world, solve the world to
exact optimality and place the winner against the optimum.

## Method (implemented and unit-tested before this freeze)

For each of the 51 winners in the frozen N1 report: recompute per-block
winner totals and margins from the archived artifacts (identical code
path to N1b), take the world with the maximum winner-over-pool margin
(ties: first block, lowest world index), and fail closed unless the
recomputed margin equals the report's recorded `max_margin` (atol 1e-6).
Build the world player frame from the immutable snapshot plus the
schedules-derived opponent map, restricted to the artifact universe,
with `actual` = the world's simulated scores. Solve with the frozen
forensic CBC solver:

- **L (DraftKings-legal):** `solve_draftkings_legal_oracle` — roster
  shape, $50k cap, max 8 per team, two games; no strategy rules.
- **P (production contract):** `_solve_oracle` with QB stack >= 2,
  bring-back >= 1, $49k floor (the S1 exact-stack mirror, including the
  same-team-RB and RB-vs-DST prohibitions).

Per winner: legal/production optima and gaps, player overlaps, exact and
near-optimum flags (near = gap <= 2.0 simulated points, frozen), the
winner's own DK-legality and production-legality in our snapshot.

## Preregistered reading

1. Majority of winners exact or near the L optimum with overlap >= 7:
   boom DEPTH suffices to build winners; regret-targeted generation is
   the priority lane.
2. Winners far below their own worlds' L optima (median gap > 10): the
   law prefers non-winner builds even where winners dominate our pool;
   priority shifts to law repair (OT/DST/dependence, winner-implied
   calibration).
3. Between 2 and 10: mixed — depth finds winner-adjacent builds; report
   overlap distribution and route by it.
4. Production-contract findings are descriptive: winners violating the
   contract, and negative P gaps, measure how much the construction
   rules exclude winning rosters. They license no rule change by
   themselves.

## Governance

Sim-side diagnostic: no realized score is read (winner identities were
consumed and published by frozen N1). No historical-outcome lease is
required; this does not collide with the in-flight all-boom arm under
the one-active-experiment law. Output is create-only; the report pins
`uses_realized_outcomes: false`, `gate_decision: null`,
`production_change_licensed: false`. Runs locally, sequential
single-process (102 small CBC solves), matching the N1 execution mode.

## Reality smoke (rule-1, outcome-blind, run BEFORE this freeze)

`--smoke 2023:1` on the real artifacts: universe 773, candidates 255,
5 blocks x 10,000 worlds; winner resolved 9/9, DK-legal in snapshot
(salary 49,800), production-INVALID (recorded as a contract fact; the
full run quantifies across winners); both solvers returned Optimal
nine-player rosters at a fixed world (block 0, world 0) chosen without
reference to any margin. No margins or winner gaps were computed.

## Pins (sha256 prefixes)

- Module `src/nfl_dfs/analysis/winner_world_optima.py`: `d7b4d521f93f84b4`
- Runner `scripts/analyze_winner_world_optima.py`: `20f586729aa701a9`
- N1 report (winners + recorded margins): `c715cd78` (full sha in
  `reports/2026-08-19-winner-law-audit-result.md`)
- Local artifact manifest (content-verified 255/255 against the tracked
  uri/sha manifest `514b46b9…`): `915d4a06a586eb52`
- Snapshot features parquet: `20c48b58c8475e75`
- Opponent map (nfl_raw.schedules, closure-validated):
  `ddddc7e9eb0cd726`
- Output: `reports/winner-law-audit-runs/20260819-winner-world-optima-v1-report.json`
