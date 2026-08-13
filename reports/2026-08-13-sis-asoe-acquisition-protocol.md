# SIS alignment share over expectation acquisition protocol

Date frozen: 2026-08-13, before any historical SIS alignment-attempt value,
target-allocation likelihood, dependence metric, candidate score or lineup
score is read. Operational accounting was amended later the same day, still
before any artifact or historical attempt value was persisted or read, as
described below.

## Question and relation to the failed schema screen

Can historical SIS team/game Pass Defense Totals support a strictly-prior
receiver-alignment composition for a separately specified alignment share over
expectation (ASOE) allocation mechanism?

The completed team Pass Defense schema test remains a valid failure for its
registered per-coverage-snap estimand. This protocol does not substitute `Att`
into that test. It defines a distinct composition estimand for which the
denominator is the sum of Wide and Slot attempts. Therefore that exact export
route is closed for per-snap efficiency but open for this separately frozen
attempt-share mechanism.

## Exact historical SIS acquisition

Use the paid normal SIS Team Leaderboards UI, Pass Defense Totals, regular
season, all teams and Split by Game. Every Submit must set:

- receiver position WR (`PassDefenseFilters.ReceiverPos=4`);
- target alignment to exactly Wide (`2`) or Slot (`3`);
- all seven mutually exhaustive coverage schemes (`0,1,2,3,4,5,6`);
- minimum targets and attempts to zero; and
- one season and one of the disjoint source windows Weeks 1--6, 7--12 or
  13--17.

Collect seasons 2022--2025, for 24 planned artifacts total. Six-week windows
cap the theoretical all-team maximum at 192 game rows, below the paid
200-row limit. Week 18 is not acquired: the latest target Week 18 input is
Weeks 14--17. Incidental UI refreshes are blocked. Only an explicitly armed
Submit may consume the request meter. The hard durable ceiling is 27 requests;
it may not be spent on another season, week, alignment, shell, report, entity
or value view.

The ceiling was originally 26 for 24 planned artifacts plus two identical
operational retries. During response-listener repair, two routed submits and
one identical manual scope-capture submit reached the normal SIS endpoint.
None produced an artifact, and no historical attempt or performance value was
persisted or read. The durable counter is therefore corrected to three and the
ceiling to 27 so the same 24-file scientific grid can finish. This is an
operational-accounting amendment only: the report, entity, seasons, windows,
alignments, shells, fields, row cap and downstream decision law are unchanged.

Each raw licensed CSV remains gitignored under
`sis/team-pass-defense-asoe-v1/`. Its manifest must bind the protocol hash,
exact submitted payload, season/window/alignment, stable SIS team identities,
row count, retrieval time and SHA-256. Fail closed on the 200-row cap, mixed
scope, duplicates, missing identities, missing `Att`, a negative/non-integral
attempt count or a changed artifact. Only identity columns and `Att` may be
parsed; completions, yards, touchdowns, interceptions, air yards and all other
performance values remain unread.

## Matching Fantasy Points acquisition

Run the tracked plan
`automation/fantasy_points/plans/same-season-alignment-last-four-v1.json`.
It contains exactly 56 Receiving Separation by Alignment exports: seasons
2022--2025 crossed with target Weeks 5--18, where every source window is
exactly W-4 through W-1. Each export must pass the existing applied-filter,
Season/G, hash and manifest contracts. The route fields consumed later are
only Overall, Wide, Slot and Inline `RTE`; no target-week row is allowed.

## Acquisition gate and next branch

The acquisition passes only if all 24 SIS artifacts and all 56 Fantasy Points
artifacts validate, every SIS artifact is below cap, and the two sources can be
resolved to the project schedule without using target-week data. A pass
licenses implementation of the separately frozen ASOE construction and its
score-free allocation/dependence gate. It does not itself license a score
comparison or production change.

A valid acquisition failure closes only this exact team-attempt-share input
route. It does not broaden the earlier per-snap closure and does not license
post-hoc player-grain or shell mining.
