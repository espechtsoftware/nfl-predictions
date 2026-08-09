# K=1 no-salary-floor true-80 experiment

Preregistered: 2026-08-09 12:03 CDT, before creation of any treatment rows or
execution. Source results were already known. The treatment panel ID was
confirmed absent from staging at freeze time.

Status: **RUNNING — immutable execution IDs frozen; no score-bearing output
inspected**. This is an outcome-informed historical exploration, not
prospective confirmation.
The arm is being revisited because the earlier K=3/40-entry salary-floor
deletion added two weeks at 200 under the later tail-first utility, after the
K=1/80-entry portfolio became the research baseline. All three of that old
arm's 200+ weeks already occur in the current K=1 book, so this is a
lower-priority and deliberately final test of the exact floor deletion.

## Frozen comparison

| Field | Source | Treatment |
|---|---|---|
| Panel | `20260808-e80-k1-c616390` | `20260809-e80-k1-nofloor-c616390` |
| Generation image | `nfl-dfs@sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6` | identical |
| Code SHA | `c616390` | identical |
| Seasons/slates | 2019, 2021–2025 / 107 | identical |
| Entries | 80 per slate | identical |
| Ensemble | K=1 | K=1 |
| Generation | `N_CE=0`, `N_EPISTEMIC=0`, `N_GUMBEL=0`, `N_BOOM=40`, candidate multiple 2 | identical |
| Simulation/selection | possession mode, 10,000 worlds, select at 194 | identical |
| Mean target | 45% model / 55% prop market where covered | identical |
| Minimum lineup salary | $49,000 | **$0** (`MIN_LINEUP_SALARY=0`) |

The source has one config hash
`c632e60ef178c0818f1bd5a8ebd4affe03646fae035ca39480e0dfbc59a16a83`
and one seed identity: CE 1701, role belief 7331, Gumbel 4700, and K=1
LightGBM member 0 with library-default seeds. The treatment must preserve all
non-treatment settings, features, and seed provenance. The only allowed
lever difference is `MIN_LINEUP_SALARY=0`; `MODEL_ENSEMBLE=1` merely
identifies the already-frozen K=1 source configuration.

Runner parameters are frozen as:

```text
PANEL_CODE_SHA=c616390
PANEL_ARM_LABEL=e80-k1-no-floor
PANEL_ARM_ENV=MODEL_ENSEMBLE=1|MIN_LINEUP_SALARY=0
PANEL_N_ENTRIES=80
PANEL_ALLOW_TREATMENT=1
PANEL_MEMORY=16Gi
PANEL_TASK_TIMEOUT=10800
PANEL_SMOKE_SEASON=2022
family=e80k1nf
```

The 2022 one-week immutable-image smoke must pass before the six season jobs
launch. All generation stays on Cloud Run; no local simulation is allowed.

## Validity and mechanism gate

Before interpreting scores, require:

1. 107 aligned slates, exactly 80 selections on every slate, and single
   code/config/lever/seed identities within each panel.
2. Same generation digest and `c616390` code SHA as the source, with all
   non-treatment configuration and seed provenance invariant.
3. The purpose-built `salary` audit proves identical upstream player
   position, projection, pre-blend model, and market features; a $49,000
   source floor and zero treatment floor; complete salary values; actual
   sub-$49,000 candidate generation in the treatment; and a changed selected
   portfolio. Report candidate and selected salary distributions and roster
   overlap.
4. Candidate artifacts, realized scores, and player-mean joins are complete
   within the established tolerance. The generic baseline acceptance may
   reject the intentional treatment floor; any other completeness or
   provenance failure invalidates the arm.

Never promote this treatment panel directly.

## Frozen tail-first disposition

The known source portfolio has 12 weeks at or above 200, 6 at or above 210,
and a candidate-pool oracle count of 19 at or above 200. Historical support
for the hypothesis requires all of:

- at least 14 selected weeks at or above 200 (aggregate lift of at least 2);
- at least 6 selected weeks at or above 210;
- at least 19 pool-oracle weeks at or above 200; and
- the validity/mechanism gate above.

Report selected counts at 187/194/200/210/220/230/240, pool-oracle counts on
the same grid, season-level deltas, mean and median weekly maximum, and the
weeks gained/lost at 200. Season signs and mean are diagnostics, not vetoes.
Prefer non-worsening 220/230/240 counts; an extreme-tail tradeoff keeps the
arm research-only pending a prospectively defined payout utility.

Because this is outcome-informed historical exploration, a pass means only
"worthy of prospective confirmation." It does not adopt a zero salary floor.
A failure closes this exact K=1/80 no-floor arm. Do not use these outcomes to
tune an intermediate floor, entry count, selection line, K, or individual
weeks.

## Execution — 2026-08-09

The 2022 immutable-image smoke `replay-e80k1nf-smoke-7rrbr` passed before the
panel launch. The six season executions are:

- 2019: `replay-e80k1nf-2019-nrw5b`
- 2021: `replay-e80k1nf-2021-zjwt8`
- 2022: `replay-e80k1nf-2022-rdvll`
- 2023: `replay-e80k1nf-2023-57cw8`
- 2024: `replay-e80k1nf-2024-gdx9t`
- 2025: `replay-e80k1nf-2025-2bpt5`

The tracked manifest under
`reports/panel-runs/20260809-e80-k1-nofloor-c616390/` records the exact image,
configuration, and execution mapping. All IDs were recorded before any
score-bearing output was inspected. Monitor only completion conditions and
row/slate counts until every execution is immutable; then run check-only
acceptance and the purpose-built `salary` comparator.
