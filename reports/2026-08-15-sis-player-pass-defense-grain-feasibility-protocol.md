# SIS player pass-defense grain feasibility protocol

Date frozen: 2026-08-15 05:50 CDT  
Protocol: `20260815-sis-player-pass-defense-grain-feasibility-v1`  
Status: outcome-blind acquisition/schema gate; not a model or lineup arm

## Question

Can the ordinary paid SIS Player Leaderboards surface return a cap-safe,
identity-stable player/game Pass Defense Totals view with coverage-snap and
target denominators under one receiver-alignment filter? A pass is the minimum
prerequisite for the separately proposed receiver-specific QB coupling
mechanism. It does not establish predictive value or scoring improvement.

This is distinct from the failed team-grain coverage schema gate and the
dormant 7/12 individual-crossing sample. The team gate asked for normalized
efficiency fields from Team Leaderboards. The dormant sample attempted six
WR/CB alignment slices and exhausted its operational budget before accepting
an artifact. This protocol asks only whether one player-grain denominator view
is retrievable and complete.

## Frozen query

- UI: NFL Player Leaderboards, Pass Defense Totals.
- Season: 2025, regular-season Weeks 1--18, no playoffs.
- Team: SIS team ID `1` (the first stable numeric SIS team identity; selected
  without reading performance or fantasy outcomes).
- Grain: Split by Game.
- Defender position: CB (`PassDefenseFilters.DefenderPos=12`).
- Receiver position: WR (`PassDefenseFilters.ReceiverPos=4`).
- Target alignment: Wide (`PassDefenseFilters.TargetLinedUp=2`).
- Minimum targets and attempts: zero.
- Exactly one visible Submit is the scientific query. Incidental UI refreshes
  are blocked. A durable three-request ceiling permits at most two identical
  operational retries and may never be reset.

The create-only private output directory is
`sis/player-pass-defense-grain-feasibility-v1/`. Raw licensed rows and browser
state remain gitignored. Only the protocol, code, tests, hashes, schema and
aggregate gate result may be tracked.

## Gate

The sample passes only if all of the following hold:

1. The exact submitted request scope above is independently recovered from the
   API request.
2. The response contains between 1 and 199 rows; exactly 200 is a paid-cap
   failure.
3. Every API row is season 2025, Weeks 1--18, Games=1 and SIS team ID 1.
4. The downloaded CSV independently matches season/week/game scope and exact
   API row count.
5. The CSV schema contains player name, a coverage-snap denominator
   (`Cov. Snaps` or `Coverage Snaps`) and a target denominator (`Tgts` or
   `Targets`).
6. The response supplies one non-null stable player ID per row, identities are
   unique at player/week grain, and every identity resolves to the CSV player
   name.
7. No performance value, fantasy point, candidate, lineup or contest outcome
   is read for the decision.

Failure closes this exact sample scope without spending a historical lineup
test. A pass licenses only a separately frozen, bounded acquisition design for
coarse player receiving/pass-defense alignment and coverage groups. That later
design must carry strictly-prior windows, shrink sparse cells, use the repaired
G0/G1 dependence scorecard and remain a 2026 paired shadow unless a genuinely
untouched outcome holdout is available.

