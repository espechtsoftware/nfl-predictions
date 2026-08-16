# ATLAS fixed-budget historical realized-score diagnostic protocol

Date frozen: 2026-08-16, before any repaired matched-diversity season
execution reached terminal state or any season output was opened  
Protocol ID: `20260816-atlas-historical-score-diagnostic-v1`  
Disposition class: retrospective diagnostic only; never a historical
promotion or a substitute for the 2026 pre-lock shadow

## Question

At exactly equal realized candidate budget, does replacing the incumbent boom
allocation with the already-frozen ATLAS matched-diversity allocation improve
the realized weekly maximum of either the complete candidate pool or the
unchanged exact-80 selected portfolio on the 54 registered 2023--2025 slates?

This is the downstream score-facing diagnostic that the score-free ATLAS MVP
does not perform. Its mechanism, source executions, selector, thresholds and
decision summary are frozen before the upstream outputs are visible. It will
run after mechanically valid upstream completion regardless of whether the
score-free ATLAS gate passes or fails. Therefore the score-free result cannot
select whether historical scoring is disclosed.

## Immutable upstream identity

- Code SHA: `44236483bb5bbf874da3f281a66af9e77dc3c9c9`.
- Image digest:
  `sha256:15916bf8d4ced52cc94f502a2a2979b9e386420aec943208ba0b933d51727771`.
- 2023 execution: `atlas-matched-diversity-2023-v1-repair1-hwj79`.
- 2024 execution: `atlas-matched-diversity-2024-v1-repair1-ghvxk`.
- 2025 execution: `atlas-matched-diversity-2025-v1-repair1-qmnmq`.
- Upstream prefix:
  `gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair1`.
- Control `P1` is order-invariant CBWU-OI with native boom candidates.
- Treatment `P2` is the same CBWU-OI construction and selector after the
  exact frozen 40-for-40 native-boom replacement by ATLAS.

The scorer must bind the strict upstream three-season report, all three
season objects, their create-only generations and SHA-256 values, the exact
execution metadata, the upstream protocol/amendment/repair hashes and the
common code/image identity. A terminal or receipt mismatch is invalid, not a
score result.

## Population and outcome source

The population is exactly 54 Sunday-main slates: Weeks 1--18 in 2023, 2024 and
2025. No slate, week or season may be removed.

Realized player points come only from column `actual` in
`nfl-predictions-503414.nfl_predictions.slate_player_features` for upstream
R0 panel `20260815-atlas-money-worlds-r0-v1`. Join on exact
`(season, week, id)`. Every player ID must resolve once, including DST IDs.
The scorer must independently prove that summing these player outcomes over
every one of the 72,520 registered native source candidate rows reproduces
`replay_candidates_staging.actual_score` exactly: nine slots, zero missing
players, one actual value per player-week and maximum absolute error zero.
This preflight was verified read-only before freezing the protocol and must be
recomputed in the immutable scorer.

Ownership, contest rank, payout, winner identity and standings are forbidden.
They are unnecessary for raw DraftKings-score evaluation.

## Reconstruction and invariants

The downstream scorer may not solve another ATLAS optimization or tune any
construction choice. It must:

1. reconstruct the five native books from the same immutable player-world
   artifacts and source candidate rows;
2. reconstruct `P1` with the frozen order-invariant CBWU-OI function;
3. read each seed's forty accepted ATLAS rosters from the upstream enumeration
   receipts, require exactly 200 unique global additions and rebuild the
   replacement books without another solve;
4. reconstruct `P2` with the identical CBWU-OI function;
5. require equal `P1`/`P2` candidate budgets on every slate;
6. rerun the unchanged 194-support exact-80 selector and require its ordered
   identities to equal the upstream `exact80_identities` byte-for-byte;
7. require 80 unique legal selected rosters per book and nine unique players
   per roster; and
8. score every candidate and selected roster as the exact sum of its nine
   player outcomes.

Any failure is mechanical invalidity. Candidate-count relaxation, missing-ID
substitution, a selector rerun at another line, a season subset or a new
ATLAS solve is prohibited.

## Frozen reporting

For both `P1` and `P2`, report separately for candidate pool `C` and selected
book `S`:

- weekly maximum on every one of the 54 slates;
- counts at `187/194/200/210/220/230/240`;
- mean and median weekly maximum;
- paired P2 wins, ties and losses using exact unrounded scores;
- mean, median, minimum and maximum paired delta;
- the complete per-season threshold grid and mean delta;
- distinct treatment-only and control-only threshold crossings;
- the largest positive and negative single-slate influence;
- leave-one-slate-out ranges for every threshold delta and mean delta; and
- exact candidate and selected identity overlap.

Also report the number and maximum score of ATLAS-created candidates, whether
each treatment-only candidate crossing survives exact-80 selection, and the
candidate-to-selection conversion count. These diagnostics explain a C-to-S
failure but cannot change the frozen disposition.

## Frozen tail-first signal rule

The primary comparison is `P2` versus `P1`; `P0` is not a decision arm. The
diagnostic records `historical-tail-signal-positive` only when all of these
hold for selected book `S`:

1. at least two additional distinct slates reach 200;
2. the aggregate number reaching 210 does not decline;
3. candidate-pool `C` does not lose a 200-point slate; and
4. no mechanical or scoring-source invariant fails.

The full higher-tail grid remains authoritative context. A one-slate change
at a threshold whose control count is below five must be labeled
`single-event-extreme-tail` and may not independently support a conclusion.
No alternate threshold weighting, season-sign veto, mean-score veto or
post-result selector is allowed.

## Consequence firewall

- A positive signal means the fixed mechanism produced a favorable historical
  diagnostic and strengthens the case for its already-declared 2026 shadow.
- A negative signal means the historical book did not convert the simulated
  premise; it does not authorize parameter tuning on these outcomes.
- A score-free upstream failure remains a score-free failure even if this
  realized diagnostic is positive.
- A positive result does not change production, the UI, the promoted 107-slate
  K=1 research baseline, or any money book.
- Only books frozen before 2026 kickoff can supply adoption evidence.

The output is create-only under
`gs://nfl-predictions-503414-raw/research/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v1/`.
