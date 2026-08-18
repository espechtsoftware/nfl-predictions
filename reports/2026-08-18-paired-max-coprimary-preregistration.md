# Paired weekly-max co-primary — preregistration (DRAFT for operator freeze)

**Protocol ID:** `20260818-paired-max-coprimary-v1`
**Status:** DRAFT — becomes standing policy when the operator approves and
pins this document's SHA-256. Intended to be in force BEFORE Week 1 so the
2026 season's ~18 slates are analyzed under the highest-power estimand
available from their first graded week.
**Origin:** N7 (and the Challenge 2 revision) in
`reports/2026-08-18-high-score-challenges-assessment.md`; extends the
already-accepted McNemar discordant-pair standard.

## What is preregistered

Every future paired arm report (historical or prospective) and every 2026
shadow grading spec reports, alongside its existing primary gate and the
full 240/230/220/210/200/194/187 grid, the **paired per-slate weekly-max
difference block** computed by
`research/paired_max_stats.paired_weekly_max_report`:

1. mean and median paired difference in realized weekly maximum;
2. counts of treatment-better / control-better / tied slates;
3. deterministic two-sided sign-flip p-values for the mean difference and
   the Wilcoxon signed-rank statistic — exact enumeration when nonzero
   differences ≤ 20, otherwise fixed-seed Monte Carlo
   (seed 20260818, 200,000 resamples, add-one convention);
4. per-threshold discordant pairs with exact McNemar binomial p
   (two-sided doubling convention, capped at 1).

All constants above are frozen by this preregistration and by module
constants; the implementation is offline-tested
(`tests/test_paired_max_stats.py`, including a hand-computed exact case).

## Why

Clear-counts discard magnitude: an effect of ~+2 mean points is invisible
to threshold counts on 54 slates and unresolvable on a season's ~18, while
paired continuous inference sometimes can resolve it. This partially
relieves the double measurement bind (Challenge 2) at zero data cost.

## Role and limits

- **Co-primary, not replacement:** the operator's frozen utility and each
  protocol's own primary gate still decide; this block calibrates how much
  weight a pass/fail can bear and surfaces effects the counts cannot see.
- It is a reporting standard, not a license: adding the block to a closed
  arm's reanalysis (the discordant-pair reanalysis lane) stays
  diagnostic-only and reverses no verdict.
- Zero differences count as ties and contribute no inference weight;
  slate keys, when supplied, must be unique and aligned.

## Adoption steps on freeze

1. Operator pins this document's SHA-256.
2. The CBWU-OI prospective shadow grading spec gains a rider (same
   pattern as the 100-entry rider) naming this block as co-primary; the
   frozen discordant-pairs-at-194 primary gate is unchanged.
3. Future arm protocols cite this document instead of restating the
   definitions.
