# SIS receiver/defender alignment feasibility protocol

Status: frozen 2026-08-13 before downloading or inspecting the sample rows.
This is an outcome-blind data-mechanism check. It cannot select a model arm,
change production or license a lineup-score comparison.

## Question

Can the ordinary paid SIS UI produce sufficiently concentrated, player-level
receiver and cornerback alignment distributions to support an inferred
individual matchup/conditional-allocation mechanism, rather than another
diffuse team-average coverage feature?

The preceding UI-only schema audit used three NFL query calls and confirmed
these exact controls:

- `ReceivingFilters.RecAlignment`: Left `1`, Left Slot `2`, Left TE `3`,
  Right TE `4`, Right Slot `5`, Right `6`, Back `7`;
- `PassDefenseFilters.DefenderPos`: CB `12`;
- `PassDefenseFilters.TargetLinedUp`: Wide `2`, Slot `3`, TE `4`;
- `PassDefenseFilters.ReceiverPos`: WR `4`, TE `5`; and
- `PassDefenseFilters.DefenderLinedUp`: LCB `1`, RCB `2`, SCB `3`, S `4`,
  LB `5`, DL `6`.

The controls are technically queryable. They do not identify a true shadow
assignment; any crossing remains an alignment-based inference.

## Frozen sample

- Season/week: 2025 Week 1.
- Game: Arizona at New Orleans (`2025_01_ARI_NO`). This is the
  lexicographically first 2025 Week-1 game in the accepted training schedule,
  chosen without reference to SIS metrics or player fantasy outcomes.
- Offense/team filter: Arizona, SIS team ID `1`.
- Defense/team filter: New Orleans, SIS team ID `20`.
- Grain: split by game, regular season, no playoffs.
- Receiver report: player Receiving Totals. Submit four mutually exclusive
  buckets: Left (`1`), Left Slot (`2`), Right Slot (`5`) and Right (`6`).
  Inline-TE and Back are not part of the WR/CB crossing denominator.
- Defender report: player Pass Defense Totals, defender position CB (`12`).
  Submit LCB (`1`), RCB (`2`) and SCB (`3`) separately.

Every mutation must be followed by the visible Submit action. Every submitted
response and downloaded CSV must pass the existing season/week/team,
split-by-game, row-cap, table/schema and identity-sidecar guards. Raw licensed
rows remain under gitignored `sis/`. The acquisition must stop after at most
12 additional SIS NFL query calls; no retry may reset that counter.

## Frozen concentration calculation

Use receiver `Routes` and defender `Cov. Snaps` as volume denominators; targets,
yards, fantasy points, Points Earned/Saved, EPA, Boom%, Bust% and all other
outcomes are forbidden for this feasibility decision.

1. For each Arizona WR, form normalized route shares over
   `(Left, Right, Slot=Left Slot+Right Slot)`. Require at least five summed
   routes. Select the WR with most summed routes, breaking a tie by stable SIS
   player ID.
2. For each New Orleans CB, form normalized coverage-snap shares over
   `(LCB, RCB, SCB)`. Require at least five summed coverage snaps. Retain the
   two CBs with the most summed snaps, breaking ties by stable SIS player ID.
3. Map receiver Right to LCB, receiver Left to RCB, and receiver Slot to SCB.
   For each retained CB, compute alignment overlap as the dot product of the
   mapped receiver share vector and that CB's share vector.

The sample is **concentrated enough to continue** only if:

- the selected WR's largest bucket share is at least `0.55`;
- at least one retained CB's largest bucket share is at least `0.55`; and
- the best WR/CB alignment overlap is at least `0.50`.

Otherwise the individual-crossing path closes as too diffuse on this frozen
feasibility screen. A pass licenses only a separately frozen, budgeted
2023--2025 acquisition design and conditional-allocation protocol. It does not
establish shadow coverage, predictive value or scoring improvement.

