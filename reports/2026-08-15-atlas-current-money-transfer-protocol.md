# ATLAS current-money-law transfer protocol

**Frozen:** 2026-08-15 CDT, before the Phase S ATLAS result was harvested  
**Outcome use:** prohibited  
**Production impact:** none

## Question

Does the frozen ATLAS v1 roster-slot upper-bound ranking improve the exact
legal attainable-lineup quality of the 40 selected worlds under the adopted
production-multinomial simulation law?

The already-running ATLAS cell uses finite Dirichlet
`K=28.154043586960896` plus SIS-ASOE rank transport. That cell remains valid
for its exact Phase S law but cannot establish current-money transfer. This
protocol freezes the missing transfer test without looking at the Phase S
result or any realized player/lineup outcome.

## Source acquisition

Create five independent, point-in-time historical player-world blocks for all
54 Sunday-main slates in 2023--2025. The seed pairs are unchanged:

| Block | Projection seed | Role-belief seed |
|---|---:|---:|
| R0 | 0 | 7331 |
| R1 | 1137260708 | 2690847602 |
| R2 | 2875959182 | 1630284992 |
| R3 | 253722715 | 3374646876 |
| R4 | 1643280042 | 3977633467 |

Each block contains 10,000 worlds per slate. Acquisition derives its complete
environment from `ClassicProductionPolicy.engine_environment()` and changes
only infrastructure/provenance, the block's two registered random seeds, and
the following diagnostic controls:

- `MULTISEED_PORTFOLIO`, `MULTISEED_SEED_PAIRS`,
  `MULTISEED_WORLDS_PER_BLOCK`, and
  `MULTISEED_CANDIDATE_ENTRY_BASIS` are blank so one artifact represents one
  independent block rather than the production five-block wrapper;
- `CAND_ARTIFACT_PLAYER_WORLDS=1` retains the aligned player-by-world matrix;
- each run receives a new create-only `PANEL_RUN_ID`; and
- normal BigQuery/GCS replay destinations and exact code identity are added.

The player-world law must retain the adopted receipt: possession simulator,
team factors enabled, blank `GAME_SIM_USAGE`, no `DIRICHLET_K`, blank
`TD_LEDGER`, fitted widening, canonical point-in-time TabPFN marginal cache,
empirical fallback, fixed served position scales
`QB:0.970,RB:1.005,TE:0.940,WR:1.070`, direct-role family, and no SIS-ASOE or
other research transport. Candidate generation happens only because replay is
the audited artifact-producing path; its realized scores and selected books
are forbidden inputs to this diagnostic.

The earlier `20260813-game-team-mult-r0-v1` through `r4-v1` artifacts are not
valid substitutes. They verify the production-multinomial simulator branch,
but their immutable NPZ payloads contain candidate totals only and lack
`player_ids`/`player_draws`.

## Source preflight

Before the transfer analyzer downloads an object, fail closed unless:

1. exactly five declared panels and 270 unique panel/slate artifacts exist;
2. every panel contains the identical 54-slate grid and one artifact URI and
   digest per slate;
3. code SHA, immutable image, policy-environment hash, seed pair and complete
   effective lever receipt match the acquisition manifest;
4. every object digest verifies and contains unique `player_ids` plus a
   `(players, 10000)` finite `player_draws` matrix;
5. the point-in-time player catalog covers every artifact player exactly once;
   and
6. no actual score, rank, ownership, payout, selected membership or contest
   result is queried or loaded.

## Frozen comparison

For each of the 270 block/slate cells, apply the unchanged ATLAS v1 logic:

- control rank: sum of all player fantasy points in the world;
- treatment rank: the same position-count roster-slot upper bound;
- select the top 40 worlds under each ranking using one shared deterministic
  ordering helper;
- exact-solve the union under the same $49,000--$50,000 salary range, Classic
  positions, two-game minimum, QB+2 stack, bring-back, RB-vs-DST ban and
  same-team-two-RB ban; and
- compare exact legal optimum and structural diagnostics.

Ties at the world cutoff must be resolved by stable original world index in
both arms. Exact MILP identity ties use a shared second pass: retain the
primary optimum within `1e-6` DK points, then minimize the sum of stable
player-identity ranks. Player rows are sorted by string identity before both
passes. Repeated-run and player-row-permutation checks must reproduce
identities; any residual second-pass tie that violates that check fails the
cell.

## Transfer disposition

The primary transfer gate is the three frozen Part-A quality conditions:

1. aggregate mean exact legal optimum improves strictly;
2. mean exact legal optimum improves in at least three of five blocks; and
3. aggregate q25 exact legal optimum is non-worse.

The three original raw-top-40 diversity conditions remain fully reported but
are diagnostic in this transfer cell because ATLAS Part B is the explicit
matched-diversity mechanism. Also report proxy-minus-exact slack,
proxy/exact rank correlation, exact-quality win/tie/loss counts, top-8/20/40
overlap and cutoff tie counts.

A Part-A pass licenses only the fixed-budget matched-diversity ATLAS MVP as a
2026 pre-lock shadow. It does not adopt ATLAS, change production, or authorize
retrospective parameter tuning. A fail triggers the already-declared proxy
slack review and at most one separately frozen salary-Lagrangian proxy; it
does not retroactively change this cell.

## Evidence retention

The acquisition manifest, every Cloud Run execution identity, immutable image
digest, source-object generation/digest, execution metadata, machine report,
human interpretation and all hashes are retained in the repository or its
create-only GCS evidence path. No result is valid from partial source coverage
or a self-reported container identity alone.
