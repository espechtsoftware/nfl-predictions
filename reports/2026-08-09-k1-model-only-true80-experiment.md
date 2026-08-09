# K=1 model-only true-80 experiment

Preregistered: 2026-08-09 10:10 CDT, before creation of any treatment rows or
execution. Source results were already known. The treatment panel ID was
confirmed absent from staging at freeze time.

Status: **historical exploratory experiment, outcome-informed hypothesis**.
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

