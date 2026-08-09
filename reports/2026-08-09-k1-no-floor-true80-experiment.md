# K=1 no-salary-floor true-80 experiment

Preregistered: 2026-08-09 12:03 CDT, before creation of any treatment rows or
execution. Source results were already known. The treatment panel ID was
confirmed absent from staging at freeze time.

Status: **COMPLETE — valid mechanism; formal frozen gate fails; exact policy
retained only as a separate prospective shadow**. This is an outcome-informed
historical exploration, not prospective confirmation.
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
   within the established tolerance. Code review after launch confirmed that
   generic acceptance enforces the salary cap and roster reconstruction but
   does not require the default minimum salary, so it is expected to pass.
   Any acceptance failure invalidates the arm.

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

## Result — 2026-08-09

All six season executions completed successfully. Check-only acceptance
`accept-replay-panel-8m9hv` passed on reporting image
`sha256:67e20d8308bd8bee20b436ff89dc3093445dcc559965f4527b3582ec7ed4f3f6`:
25,904 candidates, 107 slates, exactly 8,560 selected rows, 50,098 player
feature rows, no missing roster joins, and candidate/live mean parity within
`2.34e-05`. Comparator `compare-adoption-panel-7c4cs` reported zero failures.

The salary mechanism is valid and active. The source has no candidate below
$49,000; the treatment has 5,967, including 1,256 selected rows. Source versus
treatment selected membership shares 6,164 slots and changes 2,396 in each
direction. Treatment candidate/selected minimum salary is $34,200/$41,400;
the medians are $49,800/$49,800. All upstream position, projection, pre-blend
model, and market fields match exactly.

| selected 194 coverage | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 | mean | median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| K=1, $49k floor | 36 | 22 | 12 | 6 | 3 | 1 | 1 | 179.60 | 178.82 |
| K=1, no floor | **37** | **24** | **16** | **8** | 3 | 1 | 1 | 179.11 | 177.52 |

At 200 the treatment gains five weeks and loses one: 2019w10 185.94→201.14,
2019w15 190.36→200.36, 2019w16 198.86→205.46, 2021w4 193.60→215.38, and
2025w12 199.06→206.06 are gained; 2019w4 223.78→196.50 is lost. The 210
grid additionally gains 2022w14 205.02→214.02 and 2023w9 200.40→226.10, so
net changes are +4 weeks at 200 and +2 at 210. The lost 223.78 week is offset
at the 220 grid by 2023w9's 226.10; 220/230/240 counts are unchanged.
Season deltas at 200 are `{2019:+2, 2021:+1, 2022:0, 2023:0, 2024:0,
2025:+1}`: three positive, three tied, none negative.

The candidate-pool oracle moves 44/30/19/9/3/1/1 to
43/28/**18**/9/3/1/1 on the same threshold grid. The lost 200-point oracle is
2023w16 (202.74→193.84). That violates the preregistered non-worsening oracle
safeguard; therefore both the formal high-tail and frozen tail-first
operational dispositions are **not supported**. Preserve that verdict and do
not promote this staging panel, tune an intermediate floor, combine this
result with a newly mined selector, or relabel it as a historical success.

The operator had already made selected weekly highs—not pool potential or
average—the primary utility. On that explicitly stated utility, five paired
gains versus one loss, 12→16 at 200, 6→8 at 210, and unchanged 220+ counts are
material enough to observe the **exact** rule prospectively. A separately
identified `tail_k1_nofloor` live shadow will therefore reuse the isolated
K=1 registry, change only `MIN_LINEUP_SALARY=0`, freeze 80 entries at 194,
and remain excluded from UI/production selection. This is a post-result
prospective research decision, not an exception to the historical verdict.
Only new pre-lock 2026 portfolios may confirm it.
