# K=1 model-only true-80 experiment

Preregistered: 2026-08-09 10:10 CDT, before creation of any treatment rows or
execution. Source results were already known. The treatment panel ID was
confirmed absent from staging at freeze time.

Status: **COMPLETED — valid mechanism, tail-first not supported; arm closed**.
This remains a historical exploratory experiment and outcome-informed
hypothesis.
The model-only arm is being revisited because the earlier K=3/40-entry A01
arm gained two weeks at 200 and the later K=1/80-entry portfolio became the
tail-first research baseline. Consequently, even a passing result is not
prospective confirmation and must not silently change production defaults.

## Frozen comparison

| Field | Source | Treatment |
|---|---|---|
| Panel | `20260808-e80-k1-c616390` | `20260809-e80-k1-modelonly-c616390` |
| Generation image | `nfl-dfs@sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6` | identical |
| Code SHA | `c616390` | identical |
| Seasons/slates | 2019, 2021–2025 / 107 | identical |
| Entries | 80 per slate | identical |
| Ensemble | K=1 | K=1 |
| Generation | `N_CE=0`, `N_EPISTEMIC=0`, `N_GUMBEL=0`, `N_BOOM=40`, candidate multiple 2 | identical |
| Simulation/selection | possession mode, 10,000 worlds, select at 194 | identical |
| Construction | $49,000 salary floor and existing stack/exposure defaults | identical |
| Mean target | 45% model / 55% prop market where covered | **model-only** (`BLEND_MODEL_WEIGHT=1.0`) |

The source has one config hash
`c632e60ef178c0818f1bd5a8ebd4affe03646fae035ca39480e0dfbc59a16a83`
and one seed identity: CE 1701, role belief 7331, Gumbel 4700, and K=1
LightGBM member 0 with library-default seeds. The treatment must reproduce
that config and non-treatment seed identity exactly. The only allowed lever
difference is `BLEND_MODEL_WEIGHT=1.0`.

Runner parameters are frozen as:

```text
PANEL_CODE_SHA=c616390
PANEL_ARM_LABEL=e80-k1-model-only
PANEL_ARM_ENV=MODEL_ENSEMBLE=1|BLEND_MODEL_WEIGHT=1.0
PANEL_N_ENTRIES=80
PANEL_ALLOW_TREATMENT=1
PANEL_MEMORY=16Gi
PANEL_TASK_TIMEOUT=10800
PANEL_SMOKE_SEASON=2022
family=e80k1mo
```

The 2022 one-week immutable-image smoke must pass before the six season jobs
launch. All generation stays on Cloud Run; no local simulation is allowed.

## Validity and mechanism gate

Before interpreting scores, require:

1. 107 aligned slates, exactly 80 selections on every slate, and single
   code/config/lever/seed identities.
2. Same generation digest and `c616390` code SHA as the source, identical
   config hash, and identical non-treatment seed provenance.
3. The purpose-built `blend` audit proves invariant market inputs,
   post-shaping model means, and DST projections; covered treatment means
   equal model-only means; uncovered player means do not move; no-market
   slates reproduce exactly; and all candidate/player mean joins are complete
   within the established tolerance.
4. Candidate artifacts and scores are complete. The generic baseline
   acceptance blend assertion is expected to reject an intentional
   model-only treatment; that expected assertion alone is not invalidation,
   but every other completeness/provenance check must pass.

Any other failure makes the arm invalid. Never promote this treatment panel.

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
"worthy of prospective confirmation." It does not adopt model-only scoring.
A historical failure closes this exact K=1/80 model-only arm; do not retune
the weight, entry count, selection line, K, or individual weeks in response.

## Result — 2026-08-09

The 2022 smoke `replay-e80k1mo-smoke-jswhj` passed. All six immutable season
executions completed cleanly; their durable IDs are in the panel-run manifest.
Reporting build `95911a3d-8925-4859-bee4-afa5bb69ad8c` passed 673 tests with
2 skipped and produced audit digest
`sha256:67e20d8308bd8bee20b436ff89dc3093445dcc559965f4527b3582ec7ed4f3f6`.

Check-only acceptance `accept-replay-panel-ggzqg` found 25,779 candidates,
107 slates, exactly 80 selected entries per slate, 50,098 unique feature rows,
zero missing or duplicate joins, and maximum candidate/player mean error
`2.57e-05`. It exited nonzero only on the baseline-specific assertion that
covered means equal the 45/55 blend, which the treatment intentionally
deleted. Purpose-built comparison `compare-adoption-panel-qlh5s` then passed
with no mechanism or panel failures:

- all 15,538 market-covered player-weeks moved by 0.941 points on average;
- model, market, and DST inputs were invariant;
- treatment covered means exactly equaled the model-only means;
- uncovered means did not move; and
- all 53 no-market slates reproduced exactly, including rosters, selections,
  actuals, p-line, and simulated means.

### Complete tail grid

| Metric | 45/55 K=1 source | Model-only K=1 |
|---|---:|---:|
| Selected >=187 | 36 | 33 |
| Selected >=194 | 22 | 21 |
| Selected >=200 | 12 | 12 |
| Selected >=210 | 6 | 7 |
| Selected >=220 | 3 | 4 |
| Selected >=230 | 1 | 1 |
| Selected >=240 | 1 | 1 |
| Pool oracle >=187 | 44 | 39 |
| Pool oracle >=194 | 30 | 27 |
| Pool oracle >=200 | 19 | 17 |
| Pool oracle >=210 | 9 | 9 |
| Pool oracle >=220 | 3 | 4 |
| Pool oracle >=230 | 1 | 1 |
| Pool oracle >=240 | 1 | 1 |
| Mean weekly maximum | 179.60 | 178.33 |
| Median weekly maximum | 178.82 | 177.00 |

The >=200 season counts are identical in every season:
`{2019:5, 2021:1, 2022:3, 2023:1, 2024:1, 2025:1}`. Differences are confined
to market-covered 2023–2025. Model-only loses one 194 clear and one pool
oracle >=200 in 2023; loses four 187 clears in 2024; and in 2025 trades one
200 week for another while adding one 210/220 week and losing one pool-oracle
>=200 week.

The 2025 trade is concrete:

- Week 9 improves from 187.60 to **220.48**. The winning model-only boom
  roster is new to that candidate pool, ranks 24th in coverage selection,
  costs $49,800, and is absent from the source candidate pool.
- Week 5 falls from **201.74** to 191.06. The source boom winner is absent
  from the model-only pool; model-only's best pool candidate scores only
  191.86. This is not a selector miss.

Model-only still misses five pool oracles >=200. Four (2019 Weeks 6/10/15
and 2021 Week 4) are exactly the same known source-pool misses and remain
deep by p-line rank (79/201/160/118). Its new 2025 Week 12 oracle is 202.86,
while the source pool had a stronger unselected 214.36 oracle that model-only
removed. Thus the arm does not repair the known high-score omissions.

The frozen tail-first gate fails: there is no +2 lift at 200 and pool-oracle
>=200 worsens by two. The modest 210/220 gain is real but comes from one
swapped week and does not justify adopting a smaller opportunity pool. Keep
the 45/55 K=1 research baseline, never promote this treatment, and do not
tune another blend weight from these results.

One progress-log query after all outputs were already immutable but before
the complete audit incidentally displayed a single 2022 weekly score line.
No configuration, gate, comparison, or next action changed in response; the
full protocol above had already been committed before launch.
