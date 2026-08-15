# Prospective latent-role live factory implementation

Date: 2026-08-15

Protocol: `reports/2026-08-15-prospective-latent-role-state-protocol.md`

Disposition: implementation complete locally; deployment remains prohibited
until the authenticated live-slate parity smoke passes.

## What is now implemented

The previously missing real scenario factory and separately named paired
runner now exist. The factory:

- loads only completed score-free usage rows strictly before target Week W;
- fits and create-only persists the checksum-bound multinomial transition
  artifact with the moving fit boundary and registered live-source SQL hash;
- takes same-week injury/practice only from timestamp-qualified
  `player_week_injury` rows available by the run as-of time and common lock;
- derives previous state strictly within season, leaving Week 1 `unknown`;
- predicts the canonical five-state probability simplex for the exact
  Sunday-main RB/WR/TE player pool;
- builds the frozen four cap-valid entropy promotions and up to 50 seeded
  joint-state attempts, preserving rejected-attempt identities;
- modifies only the six registered role fields before invoking the existing
  `tail_k1_role` K=1 component registry and unchanged simulator/marginal/market
  transforms; and
- returns four conditional-mean promotion objectives plus each cap-valid
  sampled world's highest-total skill-player draw. These vectors generate
  candidates only. The unchanged incumbent CBWU worlds still score and select
  every roster.

The paired runner builds a fresh exact-80 control and treatment from the same
five R0--R4 projection/world books. It fails closed unless every seed has one
score-free scenario receipt and an optimization ledger containing exactly four
accepted promotions plus eight accepted sampled rosters. It rejects an inert
candidate-identical treatment, retains exact 20/40/80 memberships, and writes
the transition artifact, both player-world/candidate artifacts, and one final
manifest with create-only GCS preconditions.

The normal money policy is unchanged. No job, scheduler, app endpoint or
production hook invokes this runner.

## Validation completed

- 49 focused latent-state, live-multiseed, paired-runner, tail-shadow and
  production-policy tests pass.
- All changed Python modules compile and `git diff --check` passes.
- The moving live transition query dry-runs successfully against the current
  BigQuery schemas at 36,902,297 bytes.
- The current `tail_k1_role` Week-33 registry artifact exists and its metadata
  includes all six required role fields with K=1 training through 2025.
- The target `player_week_inference` and `injury_snapshots` tables currently
  contain zero 2026 rows, as expected before Week 1. Therefore an honest
  authenticated live-slate parity smoke cannot run yet and was not faked with
  historical outcomes or a synthetic salary spine.

## Remaining gate

Run an exact clean-archive Cloud Build for the implementation SHA. After
DraftKings posts a real 2026 Sunday-main slate and the normal ingestion/feature
chain creates the corresponding inference rows, run the CLI command
`nfl-dfs shadow-latent-role-paired` manually from the validated image. The smoke
must prove exact salary/player/world alignment, five complete scenario and
optimization ledgers, a non-inert candidate treatment, exact 80 entries in
both arms, and create-only artifact/manifest persistence. Only that passing
receipt can license a Cloud Run job definition or paused scheduler.

## Operational hardening after implementation review

A post-commit review found that every conditional role world would otherwise
reload the same season-wide TabPFN marginal cache. With five seed books and up
to 54 conditional worlds per book, that could issue hundreds of redundant
BigQuery reads without changing a single draw. The repaired path loads the
licensed season cache once per paired run, passes an in-memory copy through
every conditional shaping call, and validates its season identity. An empty or
unavailable cache still takes the existing empirical-marginal fallback. The
scientific scenario, seed, marginal-shaping and selection rules are unchanged.
