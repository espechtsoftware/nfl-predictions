# SIS receiver-specific copula protocol

Date frozen: 2026-08-15 11:01 CDT  
Protocol: `20260815-sis-receiver-copula-v1`  
Status: pre-value, score-free dependence experiment; no lineup or production
license

## Question and prior

Can strictly prior receiver alignment and opponent CB pass-defense context
redistribute QB coupling toward the most relevant same-team WR without changing
any player marginal, while improving the repaired-path teammate-dependence book?

The prior is deliberately low. Previous SIS marginal feature arms failed, the
global Gumbel factor failed, and the repaired TD work showed that increasing a
team-wide factor can improve QB-WR while worsening WR-WR and multi-player boom
multiplicity. This protocol tests only a receiver-specific copula channel. SIS
values may not change projections, player means, salaries, ownership, candidate
generation or lineup selection.

The completed player-grain feasibility gate in
`reports/2026-08-15-sis-player-pass-defense-grain-feasibility-result.md`
licenses this one bounded acquisition. No additional SIS value was read before
this protocol was frozen.

## Frozen acquisition

The source is the ordinary SIS NFL Player Leaderboards, Pass Defense Totals.
Acquire the Cartesian product below in deterministic season/alignment/week
order:

- seasons: 2022, 2023, 2024 and 2025;
- regular-season target weeks: 1 through 18, one week per request;
- all teams;
- Split by Game enabled; playoffs disabled;
- defender position: CB (`PassDefenseFilters.DefenderPos=12`);
- receiver position: WR (`PassDefenseFilters.ReceiverPos=4`);
- target alignment: Wide (`TargetLinedUp=2`) and Slot
  (`TargetLinedUp=3`), in that order;
- minimum targets and attempts: zero; and
- report: Pass Defense Totals only.

There are exactly 144 required artifacts. Each API response and downloaded CSV
must contain 1--199 rows, have identical row counts, remain inside its exact
season/week/alignment scope, expose stable player and team identities, and be
unique at `(season, week, alignment, player_id, team_id)`. Exactly 200 rows is
a paid-cap failure. Required CSV fields are player, team, season, week, games,
coverage snaps, targets, completions, yards and touchdowns. `Games` must equal
one.

All Submit-triggered SIS API requests are blocked except while the exact
matching Submit is armed. A durable create-only request ledger has a hard
ceiling of 150: 144 scientific requests plus at most six identical operational
retries across the entire run. The ceiling may never be reset. Existing output
may be resumed only when protocol hash, completed artifact hashes and consumed
request count match. Raw licensed rows, API identities and browser state stay
gitignored under `sis/receiver-copula-v1/`; tracked records contain only code,
schema, hashes and aggregate audits.

Any scope, row-cap, schema, identity, parity or request-budget failure makes
the acquisition invalid/inconclusive and prohibits model fitting.

## Strictly prior context construction

The existing create-once Fantasy Points player alignment source is
`20260813T202926Z__same-season-alignment-last-four-v1`, represented by
`raw.fantasy_points_alignment_player_l4`. It contains target weeks 5--18 and
only source weeks W-4 through W-1. Rows must resolve one-to-one to the terminal
book by `(season, target_week, gsis_id)` and must carry at least 20 Wide+Slot
routes. No target-week Fantasy Points value is allowed.

For each target defense, target week and alignment, SIS source games are the
last eight available team games strictly before the target game, crossing the
season boundary when available. Calibration 2022 begins at Week 5 and may use
only earlier 2022 games; no unsupported Week 1--4 treatment is imputed. A
context cell requires at least four prior team games, positive coverage snaps
and positive targets.

At each target week, separately for Wide and Slot, compute from only the
available prior rows:

1. team coverage snaps `C`, targets `T`, completions `R`, yards `Y` and
   touchdowns `D`, summed across qualifying CBs;
2. league leave-team-in prior rates `r_t = sum(T)/sum(C)` and
   `r_p = sum(R + 0.1Y + 6D)/sum(T)` for that alignment;
3. empirical prior sample sizes `n_c` and `n_t`, the medians of positive team
   `C` and `T` denominators across supported defenses at that target week;
4. shrunk target exposure `(T + n_c*r_t)/(C + n_c)`;
5. shrunk DraftKings receiving points per target
   `(R + 0.1Y + 6D + n_t*r_p)/(T + n_t)`; and
6. alignment vulnerability equal to the product of steps 4 and 5.

The empirical medians are outcome-blind denominator geometry, not fitted
hyperparameters. A cell is unsupported if a required rate or median is absent
or nonfinite.

For an eligible WR, let `w` be the strictly prior Fantasy Points Wide share
and `s=1-w`. Its opponent context is
`v = w*vulnerability_wide + s*vulnerability_slot`. Its strictly prior route
mass is `m = overall_routes / sum(team eligible-WR overall_routes)`. The sole
receiver score is `a = m*v`. Within each `(season, week, game, offense)` group,
center `a` across eligible WRs and divide by the maximum absolute centered
value. A group is eligible only when it contains exactly one supported QB, at
least two supported WRs, supported Wide and Slot defense cells, at least 50%
of the team's supported-WR route mass, and nonconstant finite receiver scores.
Every unsupported player/group remains bit-exact control.

The canonical team crosswalk, source hashes, row counts, support failures and
all target/source week extrema must be included in the preprocessing receipt.
Every SIS and Fantasy Points source week must be less than its target week.

## Sole treatment and calibration

For each eligible group and world, convert the unchanged control QB and each
eligible WR row to stable ascending percentile ranks, with ascending world
index breaking exact ties. Let `q` be QB rank, `u_j` WR rank and `z_j` the
fixed receiver score scaled to [-1, 1] above. For candidate strength `lambda`,
the only treatment priority is:

`priority_j = u_j + lambda * z_j * (q - 0.5)`.

Stable-sort worlds by this priority and place WR `j`'s stable-sorted unchanged
control marginal into that order. QB, RB, TE, DST, unsupported WRs and all
other rows remain bit-exact. No SIS value is added to a draw or mean.

The immutable strength grid is `0, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00`.
Select once on 2022 Weeks 5--18 only. For every grid cell compute the repaired
G0/G1 dependence book on that calibration subset. A cell is eligible only if
QB-WR, WR-WR and multiplicity >=2 and >=3 are supported. Minimize, in order:

1. the equal-weight sum of their two-sided absolute log errors;
2. aggregate joint-q90 Brier;
3. aggregate p=0.5 variogram; and
4. lambda, ascending.

Numeric ties use absolute tolerance `1e-12`. The complete grid and selected
cell must be durably emitted and checksummed before any 2023--2025 outcome or
score book is queried. Lambda zero is allowed to win calibration, but an inert
treatment cannot pass the held-out gate. No feature, window, shrinkage,
strength, target or tiebreak may change after the grid is emitted.

## Fresh repaired-path reference

A separate reference execution must use code descended from repair `26e73c5`
and pin an immutable image digest and full code SHA. It must reconstruct the
current terminal 2023--2025 served book twice with:

- active cache `tabpfn_active_label_treatment_v2`;
- finite usage K `28.154043586960896`;
- accepted strict-prior served-position schedule;
- 45/55 model/market blend;
- 10,000 worlds and seed 0;
- evaluation panel `20260812-pitclean-e80-selected-tabpfn-active-v2`; and
- historical splice `20260811-pitclean-e80-k1-role12union-a12ab31`.

Frames, draws and terminal identities must be bit-exact on repeat. The full
untreated G0/G1 score book is generated anew, stored under a new run identity,
and canonically checksummed. Pre-repair numeric references and numeric values
embedded in failed TD reports are forbidden. Treatment must pin the reference
report/manifest hashes and reproduce the exact reference score checksum before
evaluation.

## Evaluation invariants and held-out gate

The held-out population is the complete 2023--2025 terminal served book. The
treatment may activate only in Weeks 5--18 where strictly prior context is
supported; all other rows remain control. Actual outcomes define only the
unchanged G0/G1 q90 dependence diagnostics and never enter a marginal,
candidate or lineup calculation.

Validity requires exact keys/outcomes/means and game metadata; bit-exact
control repetition; bit-exact treatment repetition; finite output; identical
stable-sorted marginal values for every row; maximum player-mean drift at most
`1e-10`; changes only in eligible WRs; at least one changed eligible row; all
source hashes and point-in-time checks; exact calibration receipt identity;
and exact fresh-reference reproduction.

For control and treatment, report aggregate proper scores and two-sided
absolute-log error for G1 and G0 QB-WR, QB-TE, WR-WR and RB-RB, every supported
G0 aggregate cell, and multiplicity >=2, >=3 and >=4. Multiplicity >=4 is
mandatory but ungated if its frozen support rule remains unmet; if supported,
it becomes a no-worsening guard. Also report every season, support/coverage,
changed rows/cells, and a 2,000-replicate seed-1703 paired whole-slate
bootstrap.

Conditional on every invariant, the arm passes only when all of these hold:

1. selected lambda is greater than zero and eligible WR ranks change;
2. aggregate joint-q90 Brier and p=0.5 variogram both strictly improve;
3. G1 and G0 QB-WR two-sided absolute-log errors strictly improve;
4. G1 and G0 WR-WR two-sided absolute-log errors do not worsen;
5. G1 and G0 QB-TE and RB-RB values remain unchanged within `1e-12`;
6. supported multiplicity >=2 and >=3 two-sided absolute-log errors do not
   worsen;
7. supported multiplicity >=4 does not worsen when it is supported;
8. no other supported teammate or aggregate G0/G1 absolute-log error worsens;
9. the supported G0 absolute-log-error sum strictly improves; and
10. the fixed-weight supported G1 absolute-log-error sum strictly improves.

Thus a favorable QB-WR movement cannot pass by worsening the already
over-coupled teammate or multiplicity cells. Season and bootstrap results are
mandatory disclosures but impose no season-stability gate.

Valid dispositions are `sis-receiver-copula-gate-passes`,
`sis-receiver-copula-gate-fails` and
`sis-receiver-copula-invalid-or-inconclusive`.

## Consequence

A valid pass licenses only a separately frozen paired 2026 prospective shadow,
beginning no earlier than Week 5 when the required W-4..W-1 alignment context
exists. It does not license a retrospective exact-80 lineup run, production
promotion, scheduler/deployment change or money-policy change. A fail closes
this exact SIS receiver-copula formula. Invalid/inconclusive permits only an
identity-preserving operational repair, never a scientific change.
