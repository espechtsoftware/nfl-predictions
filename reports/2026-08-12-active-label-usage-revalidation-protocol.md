# Active-only fitted-usage exact-80 revalidation

Frozen 2026-08-12 CDT after the active-only exact-80 result and fitted-K risk
review were known, but before generating or reading the registered multinomial
control below. This is a retrospectively required standing-law revalidation,
not an independent discovery experiment. The finite-K arm's existing weekly
scores are already known and that limitation must remain attached to the
result.

## Why this revalidation is required

Fitted `K=28.154043586960896` was selected before the active-only TabPFN cache
and its arm-specific walk-forward served-position schedule became the terminal
downstream marginal law. The repository rule that verdicts do not transfer
across a changed downstream stage therefore prevents treating the earlier
fitted-K exact-80 result as final production evidence.

G0 and G1 remain valid descriptions of the finite-K terminal book to which
they were pinned. This comparison decides whether finite K remains the
production research allocation after active-only labels. If it selects
multinomial, G0/G1 cannot license a production G2 without being rerun against
that changed terminal law.

## Fixed arms

- Immutable generation image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ad50fe19bde366ca11180b561127b09e2c79c97ec7dbbd5507282e33d2d5eb62`
  with embedded generation code `a12ab31`.
- Common historical splice:
  `20260811-pitclean-e80-k1-role12union-a12ab31`.
- Existing finite-K treatment:
  `20260812-pitclean-e80-selected-tabpfn-active-v2`.
- Write-once new multinomial control:
  `20260812-pitclean-e80-active-label-usage-multinomial-v1`.
- Evaluation seasons: exactly 2023, 2024 and 2025 (54 Sunday-main slates).
- Both return exactly 80 distinct legal selected lineups per slate.

Both arms use K1, the accepted direct-role union, 40 boom candidates, line-194
selector, active-only cache `tabpfn_active_label_treatment_v2`, 45/55 market
blend, the existing seeds, 10,000 worlds, and the exact active-only schedule
from final-served execution `tabpfn-active-label-final-served-v2-mbs5t`:

| target season | QB | RB | TE | WR |
|---:|---:|---:|---:|---:|
| 2023 | 0.965 | 0.990 | 0.945 | 1.030 |
| 2024 | 0.905 | 0.970 | 0.950 | 1.060 |
| 2025 | 0.925 | 0.960 | 0.940 | 1.040 |

The sole causal difference is within-team usage allocation:

- control: production conditional multinomial, with `GAME_SIM_USAGE` and
  `DIRICHLET_K` absent;
- treatment: `GAME_SIM_USAGE=dirichlet` and exact unrounded
  `DIRICHLET_K=28.154043586960896`.

The new control must use the same immutable image as the existing treatment.
The already-generated treatment is not rerun because its immutable panel and
full invariants are available; this reuse and its known scores are explicit
constraints, not concealed preregistration.

## Mechanical validity

Require one control smoke and all three complete control seasons before any
comparison. Then require:

1. 54 aligned evaluation slates, 80 distinct legal selections per slate,
   complete authoritative labels and one image/code/seed identity;
2. exact player keys, active-only cache, schedule, salary, actual, PIT input,
   market/model mean and pre-simulation mean parity;
3. only the registered distribution-derived fields may differ after allocation;
4. common-roster actuals and pre-selection simulated means are invariant within
   the existing absolute tolerance, while candidate membership changes; and
5. common 2019/2021/2022 history is byte-identical in both full books.

Any pre-score failure licenses only an operational repair preserving these
arms, schedule, K, seeds and decision. No K refit, scale refit, candidate dose,
selector or threshold change is allowed.

## Frozen decision and mandatory cost disclosure

Compare full 107-slate selected weekly maxima in order
`240,230,220,210,200,194,187`. At the first nonzero
finite-K-minus-multinomial count, select the higher arm. If every count ties,
select the higher mean weekly maximum; an exact tie retains finite K as the
incumbent.

Regardless of selection, report the evaluation-only grid, mean and median,
every paired crossing at all seven thresholds, whether several threshold gains
are supplied by the same slate, all absolute weekly deltas of at least ten
points, and the selected/pool overlap diagnostics. These are mandatory risk
disclosures but cannot override the frozen comparison after the fact.

No payout dollars or ROI may be imputed without a contest field score/rank
distribution and duplication/tie model. If such evidence later becomes
available, payout grading is a separately frozen diagnostic of these same
immutable books.
