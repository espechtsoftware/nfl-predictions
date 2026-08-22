# Fast-track decision: receiver/defender matchup intelligence

**Date:** 2026-08-22 (deployment lead)
**Source plan:**
[`2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md`](./2026-08-22-receiver-defender-matchup-intelligence-implementation-plan.md)
**Decision:** ADOPTED and fast-tracked as the Foundry's paid-data annotation
workstream, with the P0 outcome-blind support census executed today (results
below), one generalization, and an explicit priority interleave with the live
scoring chain. No fill/retrieval/policy authority is granted by this document.

## Why fast-track

The operator's standing question — what characterizes high-scoring lineups —
is currently answered in roster terms only. The paid sources (SIS defender
grain, FantasyPoints alignment/coverage, PFR nearest-defender) are ingested
but effectively unused for that question: the accepted phenotype artifact has
`easy_coverage.available=false` and zero annotated players. The plan closes
this with the correct laws (PIT roles, strictly-prior windows, missing-is-not-
neutral, matched denominators, closed-mechanism avoidance, one preregistered
historical read). It also fixes the annotation-contract permissiveness flagged
by the independent code review's interpretation cautions.

## P0 outcome-blind support census — EXECUTED 2026-08-22

Identity/eligibility/support counts only; no treatment effects, lifts, or
outcomes were read (per the preflight-support law in CLAUDE.md).

| Source table (`nfl_raw`) | Rows | Entities | Seasons | Season-weeks |
|---|---:|---:|---|---:|
| `sis_receiver_copula_player_game` (defender x game x alignment) | 15,477 | 376 defenders | 2022-2025 | 72 |
| `sis_receiver_copula_defense_prior` (strict-prior defense/alignment) | 3,324 | 2 alignments | 2022-2025 | 56 target-weeks |
| `pfr_advstats_def` (nearest-defender, weekly) | 62,345 | 2,320 defenders | 2018-2025 | 173 |
| `fantasy_points_alignment_player_l4` (W-4..W-1 Wide/Slot) | 16,482 | 602 receivers | 2022-2025 | 56 target-weeks |
| `fantasy_points_route_share` (weekly) | 27,305 | 1,029 players | 2022-2025 | 72 |
| `fantasy_points_receiver_coverage_prior` (prior-season) | 2,093 | 865 receivers | 2022-2025 | season-grain |
| `fantasy_points_defense_coverage_prior` (prior-season) | 128 | 32 teams | 2022-2025 | season-grain |
| `fantasy_points_advanced_prior` (prior-season) | 3,771 | 1,001 players | 2022-2025 | season-grain |

**Census verdict: GREEN for the full Foundry panel.** The 54-slate panel spans
seasons 2023-2025 (3 x 18 Sunday-main slates). Every weekly source provides
strictly-prior support for every panel slate, including season boundaries
(2023 W1 draws on retained 2022 rows; the plan's cross-season as-of
construction is feasible, not hypothetical). PFR extends team/secondary priors
to 2018 for deeper windows. The season-grain FantasyPoints products remain
prior-season components with material missingness, exactly as the plan
scopes them. No support threshold in the plan's §5 laws is infeasible on
these counts, so the definitions can freeze as written; per-component
missingness reasons carry the rest.

## One generalization (operator request)

The same architecture applies to every paid metric family, not only receiver
coverage. The v2 annotation contract will therefore be **metric-family
extensible from day one**: one versioned contract pattern (generation-pinned
source identities, lock/max-source times, exact field dictionary, missingness
reasons, forbidden-outcome scan, create-once publication) instantiated per
family — `receiver-matchup/v1` first, with the same pattern ready for
FantasyPoints advanced receiving, SIS run/pass team context for RB/QB
phenotypes, and any future vendor capture. A family is added by registering
its field dictionary and sources, never by loosening the contract.

## Priority interleave (unchanged chain-first law)

1. **Live chain remains priority zero** whenever actionable: v4 close ->
   v5 configure -> task-0 equivalence -> tasks 1..53.
2. **Compute-side critical path** (gates score reporting and the retrieval
   axis): the parametric-snapshot reader + machine-readable task-0
   equivalence comparator.
3. **Data-side workstream (this plan), runs in parallel with the batch**:
   P0 contract module (`receiver_matchup_contract.py`) -> P1 role +
   role-concession SQL/features with leakage tests -> P2 defender/alignment
   context -> P3 canonical annotations, verified outcome-blind against the
   real accepted task-0 player catalog and one governed winner slate.
   The winner-registry reconciliation is one shared deliverable with roadmap
   P0.2 (see the 2026-08-22 Data deficiency log row).
4. Analyses (P4) only after the batch supplies cross-slate corpora and the
   annotation layer is frozen; Foundry challengers (P6:
   `F5-matchup-supported-v1`, `R6-matchup-admission-v1`) only after P4 shows
   incremental held-out value; graph/UI (P5) alongside the phenotype adapter
   work already sequenced.

## Bindings into existing machinery

- Analysis C (simulated phenotype enrichment across slates) consumes the
  Foundry batch via the same parametric-snapshot adapter already sequenced —
  one reader serves retrieval presets, phenotype extraction, AND matchup
  annotation joins.
- `R6-matchup-admission-v1` composes with the frozen v2 retrieval laws: it is
  an admission sleeve in front of `expected-max-v1` /
  `block-supported-tail-ladder-v1` / `regime-robust-ladder-v1`, never a
  top-80 individual ranking (plan §8.2 matches the registry's set-selection
  law).
- The A/B/C/D matchup experiment uses the strategy registry's paired law,
  which the F4 fix made satisfiable on the fill axis today.
- The plan's §5.6 v2 annotation contract supersedes the permissive
  `corpus-gt200-context-annotations/v1` for all future annotation input, per
  review caution and plan alike.

## Not licensed

No lineup rule, fill sleeve, admission preset, or money-policy change from
this document or from descriptive enrichment alone; no revival of the closed
twelve-candidate FantasyPoints arm or the closed SIS copula calibration; no
`COVERED_BY` assignment edges without a direct-assignment source.
