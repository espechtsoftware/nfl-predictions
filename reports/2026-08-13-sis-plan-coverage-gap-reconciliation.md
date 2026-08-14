# Reconciliation: SIS plan coverage gap audit

Date: 2026-08-13. This reconciles
`reports/2026-08-13-sis-plan-coverage-gap-audit.md` before any new SIS
acquisition, model output, candidate score or lineup score is read.

## Decision

The central conclusion is accepted: the paid SIS surface is not exhausted.
The current warehouse contains broad team context, but the historical team
Receiving family is missing; no historical player-grain family has been
imported; pass-defense Boom%/Bust%, distinct pass-rush pressure and the passing
charting fields have not received a formal current-stack marginal test. This
reopens bounded SIS work. It does not revive either failed QB-line or RB
Points-Saved arm and does not authorize a broad column sweep.

## Corrections and scope

1. Boom%/Bust% was not entirely unnoticed. The strictly-prior run-context
   audit already evaluated both offensive and opponent rushing Boom%/Bust%; the
   offensive Boom% association was weak and changed sign in 2025. The exact RB
   arm nevertheless tested only opponent Points Saved/play. Pass-defense
   Boom%/Bust% and a formal tail-feature cache remain genuinely untested.
2. Pass-rush pressure was audited outcome-blind for redundancy and
   exploratorily against player outcomes. It was the least redundant team
   column (`r=0.4573` versus the existing pressure feature), but it never
   entered the failed two-column QB line treatment. Its source is therefore
   acquired and screened, not formally tested.
3. Player grain was planned and attempted, not silently dismissed. The paid
   player Pass Defense smoke already returned 11 valid 2025 Week-1 rows with
   stable identities and `Cov. Snaps`, proving that the denominator exists at
   player grain. The later alignment-specific sample exhausted seven of its
   twelve guarded calls without accepting an artifact and was preserved
   dormant. What remains unknown is filtered historical cap/cost/completeness,
   not whether SIS exposes coverage snaps at all.
4. ASOE is an allocation/dependence mechanism built from attempt composition,
   not another central-tendency feature. Its Phase S lineup result remains in
   flight and is not changed by this review.
5. Team Receiving was originally priority 1, then deliberately deferred one
   request window because Passing/Receiving overlap was expected and the
   tranche-2 rate budget was active. With tranche 2 complete, leaving Receiving
   absent is now an execution gap rather than an active prioritization choice.

## Verified source support

Outcome-free BigQuery checks find complete non-null source support in all 3,230
team-games for `pdef_boom_rate`, `pdef_bust_rate`, pass-rush pressure inputs,
`pass_catchable`, `pass_on_target`, `pass_intended_air_yards` and
`pass_pressures`. Pass-defense Boom% spans `0.000--0.607` and Bust% spans
`0.000--0.750`, so these are not constant or empty placeholders.

## Bounded next sequence

### S1 — existing-table pass-tail marginal screen

After Phase S fixes the terminal allocation law, create one current-stack
TabPFN marginal-channel treatment for active QB/WR/TE rows using exactly three
strictly-prior, volume-aware opponent fields:

- pass-defense Boom% over the last four completed games;
- pass-defense Bust% over the last four completed games; and
- pass-rush pressure rate over the last four completed games.

The common control is the Phase-S-selected marginal cache and allocation law.
First run an outcome-blind support/redundancy audit against the exact served
feature set. Then freeze a walk-forward score-free gate whose primary metrics
are q95/q99 pinball and tail Brier/reliability, with CRPS/MAE and position/
season folds diagnostic. A gate pass may license one exact-80 tail-first panel;
a fail closes this three-field bundle without adding passing chart fields or
changing positions after output.

The outcome-free prerequisite is now complete and passes: `10,018/11,435`
active QB/WR/TE rows are supported (`87.61%`), pressure correlation with the
existing pressure field is `0.4103`, and Boom/Bust correlations with existing
pass-defense EPA are `+0.5994/-0.5605`. The immutable interpretation is
`reports/2026-08-13-sis-pass-tail-support-result.md`; the model test is frozen
before output in
`reports/2026-08-13-sis-pass-tail-marginal-protocol.md`.

Passing `catchable`, `on_target`, intended-air-yards and pressure fields form a
separate offense-quality hypothesis. Screen their redundancy and reliability
without outcomes after S1; do not append them to S1 and lose attribution.

### S2 — acquire the missing team Receiving family

The tracked plan `automation/sis/plans/team-receiving-v1.json` is now the exact
research acquisition: team Receiving Totals/Value, seasons 2019 and 2021--2025,
three cap-safe six-week windows, 36 artifacts and a hard 160-request ceiling.
Do not run it until a fresh terminal login and provider-budget check. Raw rows
remain ignored. Add a write-once importer, backup coverage and a family × grain
× acquired × tested scoreboard before using any value.

The first score-free question after intake is novelty beyond the already owned
Fantasy Points route/target/advanced-receiving fields. ADoC and SIS receiver
Boom%/Bust% are candidates because their constructs are not already served;
routes, targets, ADoT and generic efficiency must pass redundancy before any
model arm.

### S3 — complete one player-grain filtered cost/schema sample

Do not reset or reuse the dormant alignment sample's `7/12` counter. Under a
new protocol and acquisition window, run one ordinary-UI player Pass Defense
Totals query for one preselected team-season and one preselected receiver
alignment, retaining `Cov. Snaps`, targets, stable player/team identity, row
count and cap evidence only. The already repaired response listener and fresh
session contract apply. This sample decides whether a bounded historical
player-grain acquisition is feasible; it reads no performance value and no
fantasy outcome.

### S4 — filtered receiver allocation only after S2/S3

If S3 is complete and cap-safe, freeze the smallest player Receiving/Pass
Defense acquisition for broad Man/Zone and Wide/Slot groups. Use strictly
prior denominators and predeclared shrinkage. Keep a marginal tail-descriptor
arm separate from a receiver-allocation/dependence arm. Do not mine individual
shells, routes or matchups after results.

Runs to Gap, Adjusted Blown Blocks and special teams remain deferred. Weekly
SIS automation remains disabled until an acquired mechanism passes its gate.

## Standing acquisition/test scoreboard

| Family | Grain | Acquired | Tested status | Next disposition |
|---|---|---|---|---|
| Passing | team/game | Totals only; Value quarantined | charting fields untested | separate redundancy screen after S1 |
| Rushing | team/game | Totals + Value | Boom/Bust exploratory; no tail arm | no immediate retry |
| Receiving | team/game | no | no | acquire S2 |
| Pass defense | team/game | Totals + Value | EPA/PS screened; ASOE attempts active; Boom/Bust untested | S1 |
| Pass rush | team/game | Totals + Value | pressure distinct/exploratory; no formal arm | S1 |
| Run defense | team/game | Totals + Value | Points-Saved exact arm failed; Boom/Bust exploratory | retain, no post-hoc add-on |
| Blocking | team/game | Totals + Value | QB line bundle failed | closed exact bundle |
| Passing | player/game | no historical table | no | behind S3/S4 |
| Receiving | player/game | no historical table | no | S4 if feasible |
| Pass defense | player/game | one valid smoke only | denominator proven; filtered history incomplete | S3 |
