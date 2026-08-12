# PIT-repair and team-passing review reconciliation

Date: 2026-08-12. This reconciles the operator-supplied review
`2026-08-12-pit-repair-and-team-qb-feature-review.md` against the current
repository and durable results. No team-passing side-table execution, cache,
prediction, calibration metric, candidate, or lineup score existed when these
dispositions were fixed.

## Result correction

The review was written through commit `24c742a`, while the repaired fitted-
usage comparison was still running. Its fitted-K rejection note is therefore
superseded. The complete 107-week exact-80 comparison subsequently selected
the fitted Dirichlet `K=28.154043586960896` at the first threshold in the
frozen tail-first order: selected weekly maxima at 240 changed from 2 to 3.
The treatment was adopted in commit `213e963`. Lower thresholds and mean were
not permitted to veto that first nonzero tail improvement.

## Dispositions

1. **Cross-season provenance: accepted before the arm.** The treatment is now
   the two-column logical bundle `team_qb_cpoe_l6` plus
   `team_qb_cpoe_cross_season`. The indicator is one only when a supported game
   in the six-game window comes from a prior season, zero when all supported
   games are same-season, and null when CPOE has no support. SQL, independent
   Python/SQL reconstruction, the generator contract, cache validator, audit
   output, and tests all use the same definition. The old team-QB images are
   superseded before execution and must be rebuilt from this amended tree.

2. **Meaning of the signal: accepted.** The frozen protocol now calls this
   team passing efficiency rather than pure quarterback quality and explicitly
   notes that receivers contribute to prior team CPOE. A primary-passer-
   identity variant is predesignated as a separately frozen follow-up only if
   the complete two-column bundle passes; it cannot be substituted after a
   result is seen.

3. **Dead efficiency CTE: accepted.** The unused, same-week, unweighted
   `qb_quality`/`team_cpoe` CTE was removed from `015`. The only team CPOE
   implementation is now the isolated, weighted, strictly-prior side table.

4. **End-of-season position fallback: accepted with an exposure audit.** A
   read-only warehouse reconstruction of the `014` usage spine found 102,927
   rows, zero null positions, and zero unsupported positions. The fallback was
   therefore unreachable in the repaired lineage. It was removed from future
   `014` builds, which now use the already-present exact salary/role position.
   This code edit does not mutate the current repaired warehouse. The next
   coordinated full build must require byte-equivalent usage/training output;
   any unexpected delta reopens revalidation. `022` retains its final-season
   position deliberately and now says why: it is rear-view UI, not a model
   input.

5. **Sunday-main lock coverage: accepted with a data-aware invariant.** All
   209 modeled `(season, week)` rows have a non-null common Sunday-main lock.
   There are 191 weeks with at least one eligible pre-lock injury source and 18
   valid empty weeks: all 2025 weeks have raw revisions but none timestamped by
   that historical lock. Requiring a nonzero built row in every week would
   falsely fail those source-empty weeks. The mandatory leakage suite now
   requires a lock for every modeled week and nonzero built rows whenever an
   independently counted pre-lock source exists. This closes the silent-null
   lock failure without inventing unavailable data. The feature remains
   explicitly Sunday-main-only.

6. **Structural upcoming-spine guarantee: valid and queued.** Existing dynamic
   checks already cover the four repaired team-context tables, but they are an
   enumerated list. Before final preseason closure, add a manifest-driven
   contract for every inference join at its proper player/team/opponent grain,
   then require target-week support from every table whose semantics promise an
   upcoming row. This broader change is independent of, and does not delay, the
   current active-label/SCHED sequence.

## Validation

- Focused feature, leakage, and team-passing tests pass: 110 passed, one
  expected rear-view dashboard skip.
- BigQuery dry runs pass for changed `014`, `015`, and `017l` SQL at
  33,940,058 / 45,573,241 / 24,914,131 bytes; the independent team-passing
  reconstruction also dry-runs at 24,914,131 bytes.
- The new injury-lock coverage query passes all 209 modeled weeks.
- No current training table, cache, prediction table, candidate panel, or
  lineup result was changed or inspected by this reconciliation.
