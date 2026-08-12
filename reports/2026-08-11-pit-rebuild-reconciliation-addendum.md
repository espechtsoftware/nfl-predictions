# PIT rebuild reconciliation addendum

Frozen 2026-08-11 before a second repaired warehouse build and before any
repaired lineup score was generated or queried.

## Why the first strict reconciliation stopped

The first rebuilt feature execution `build-features-nbzk8` completed cleanly,
but the independent before/after verifier correctly returned
`pit-repair-warehouse-invalid`. The intended usage, injury and vacancy repairs
had the exact expected keys and counts. The verifier also exposed two facts
that its initial allowlist did not model:

1. the pre-build warehouse snapshot still predated the already-landed exact
   player-week position repair in `defense_week_allowed`, which the tracked
   warehouse manifest explicitly identifies as an expected rebuild delta; and
2. the referee rolling window had only a partial `(season, week)` order. The
   raw officials source currently maps Scott Novak to two distinct 2024 week-8
   games, so BigQuery could order those tied rows differently on a rebuild.
   That changed `ref_flags_prior` on 144 training rows, by at most 0.55.

No score-bearing job was launched. This evidence was found from feature-table
keys and values alone.

## Frozen repair and revised outcome-free gate

The referee window now has the total order `(season, week, game_id)`. The
second build must pass the same dynamic source, universe and upcoming-row
checks as the first build. The post-build verifier remains fail closed, but
now recognizes the already-declared exact-week defense-position fields and
their downstream training columns. It separately requires:

- exact usage/training/defense natural keys and schemas;
- exactly 57,550 unique eligible injury rows and exactly 8,312 removed old
  injury keys;
- material changes only in the registered usage, injury/vacancy, derived xTD,
  vacated-capture, exact-week positional-defense and deterministic-referee
  fields;
- nonzero reach for every repaired mechanism; and
- no null drift and no absolute delta above `1e-12` for rebuild-only floating
  aggregation noise in defense EPA and `xfp_l4`.

The observed first-build `xfp_l4` maximum delta was
`7.105427357601002e-15`; defense EPA maxima were
`2.220446049250313e-16`. These are recorded as numerical recomputation noise,
not silently added as material feature changes. The xTD and vacated-capture
columns are deterministic descendants of the already-registered smoother and
injury/vacancy repairs.

The Tier-1/Tier-2 revalidation scope is unchanged: all accepted and dependent
lineages are already required to retrain from the final reconciled warehouse.
The extra referee determinism repair strengthens that requirement; it does not
reopen unrelated closed treatments.
