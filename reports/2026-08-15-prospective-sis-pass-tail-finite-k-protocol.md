# Prospective SIS pass-tail finite-K shadow protocol

Frozen 2026-08-15 before any 2026 NFL outcome is available to this mechanism.
This protocol operationalizes the selected historical result in
`2026-08-14-sis-pass-tail-exact80-result.md` without changing the K=1 CBWU
money policy or reopening the closed 2019--2025 arm search.

## Identity and boundary

- Protocol/runner identity: `prospective-sis-pass-tail-finite-k-v1`.
- Money lineups remain `classic-k1-role12-boom40-poscal-cbwu-v4`.
- This is a separately labeled, outcome-unseen 2026 shadow. It may not feed
  the UI's money book, recourse policy, structural-archetype shadow, or any
  production projection table.
- The control and treatment use isolated live cache tables
  `tabpfn_sis_pass_tail_live_control_v1` and
  `tabpfn_sis_pass_tail_live_treatment_v1`. Historical write-once tables are
  never appended, truncated, or otherwise repurposed.
- No 2019--2025 outcome may be queried to refit, tune, stop, promote, or alter
  this mechanism. Historical evidence is used only to freeze the already
  selected identities below.

## Frozen arms

Both arms inherit the historical active-only TabPFN label law, one-member
component registry, possession simulation, 12 alternate-role candidates, 40
boom candidates, exact 80-entry selection, the Phase-S ASOE target-allocation
law, and five registered seed pairs. The only arm differences are the
TabPFN cache and served-position schedule.

| setting | control | treatment |
|---|---|---|
| TabPFN cache | live control v1 | live treatment v1 |
| 2026 served scale | `QB:0.85,RB:0.895,TE:0.96,WR:1.04` | `QB:0.92,RB:0.965,TE:0.945,WR:1.04` |
| extra TabPFN fields | none | `sis_pass_def_boom_rate_l4`, `sis_pass_def_bust_rate_l4`, `sis_pass_rush_pressure_rate_l4` |

The 2026 schedules are the last prospectively selected strictly-prior
schedules (the target-2025 schedules). Carrying them forward was chosen now,
before 2026 outcomes, instead of fitting a new post-closure schedule.

Common fixed settings:

- `DIRICHLET_K=28.154043586960896`;
- `SIS_ASOE_BETA=0.07771181538347656`;
- tail line 194; 80 entries; 10,000 worlds per book;
- seeds R0 `(0,7331)`, R1 `(1137260708,2690847602)`, R2
  `(2875959182,1630284992)`, R3 `(253722715,3374646876)`, and R4
  `(1643280042,3977633467)`;
- no CBWU union, archetype reallocation, route features, no-floor policy,
  ownership treatment, or other unregistered interaction.

## Point-in-time feature and cache law

For target week W, the three SIS features are opponent-team, same-season,
volume-weighted aggregates over at most the four completed games with source
week `< W`; at least two completed games are required. A target-week spine is
constructed explicitly, so no target-week game row is needed and any row with
week `>= W` is excluded before aggregation. The target inference row must have
`available_at <= generated_at` where such timestamps exist.

The control and treatment train on identical active-only labeled rows and
predict the same 2026 target player keys. The treatment adds exactly the three
registered fields; unsupported fields remain missing and are handled by
TabPFN. Each weekly cache write is append-only for a previously absent
season/week, with immutable code SHA, feature-contract SHA, source table
identity/checksum, source-week end, generation timestamp, and unique
season/week/player keys. Missing, duplicated, late, target-week, or
source-unidentified data fail closed. The canonical `tabpfn_projections` table
is never read as a treatment substitute and never written by this job.

Because both pass-tail context and the common ASOE law need early-season
history, scoring shadows begin only when all common inputs pass their frozen
minimum-support checks; an ineligible week is an explicit no-run, never a
fallback to a different mechanism. No cross-season fallback is allowed.

## Paired book and grading law

For each eligible pre-lock snapshot, build control then treatment for each
registered seed pair from the same salary/draft-group identity, model-registry
identity, feature build, vendor source identities, and pre-lock market
snapshot. Persist all candidate/world artifacts and exact 80 memberships with
create-only objects and a hash-addressed manifest. Any identity drift or
partial five-seed/arm grid invalidates that snapshot.

Grade after outcomes land at Weeks 4, 8, 13, and 18. Report control/treatment
weekly maximum counts at 240/230/220/210/200/194/187, distinct improving and
worsening calendar slates, mean weekly maximum, exact-80 overlap, candidate
overlap, source coverage, and operational failures. Intermediate checkpoints
cannot promote the treatment. Any adoption/composition decision requires the
full preregistered 2026 evidence or a separately frozen rule written before
the relevant outcomes.

