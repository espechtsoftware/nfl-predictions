# SIS receiver-copula reference population-grain repair

Date frozen: 2026-08-15 13:52 CDT  
Original run: `20260815-sis-receiver-copula-v1`  
Original execution: `sis-receiver-copula-reference-v1-xj64s`  
Original report SHA-256: `1cc1e38b4eea85ec583e7249975fafe605afee2323e55a924d4f26d7d3d0fb83`

## Defect

The original reference is terminally invalid/inconclusive and is preserved
without modification. Its only failing invariant applied one row-count
constant to two different grains:

- the complete terminal player/draw book contains 15,396 unique player-slate
  rows and has draw shape `15,396 x 10,000`;
- the downstream G0/G1 relationship scorebook intentionally filters that
  terminal book to 7,848 rows on 54 slates.

The implementation required the terminal book to contain 7,848 rows even
though the independently evaluated score population correctly required and
contained 7,848 rows. The terminal book, draws, terminal receipt, and
scorebook were all bit-exact on repeat. Player keys, game metadata, finite
values, simulation-law identity, 54-slate scope, and score population all
passed.

## Frozen repair

Replace the ambiguous `REFERENCE_ROWS` with two explicit constants:

- `REFERENCE_TERMINAL_ROWS = 15_396`
- `REFERENCE_SCORE_ROWS = 7_848`

Only terminal frame length and draw shape use the terminal count. Only the
post-filter score population check uses the score count. No source, historical
panel, evaluation panel, cache, simulation law, Dirichlet K, position
schedule, blend, world count, seed, copula treatment, calibration grid,
held-out gate, or adoption consequence changes.

The retry must use a new create-only run identity:
`20260815-sis-receiver-copula-v1-repair1`. It must be built from the exact
repair commit into an immutable image, pass the full test suite, reproduce the
same original frame/draw/terminal/score fingerprints, and pass every invariant
before calibration is licensed. A mismatch outside the corrected population
check invalidates the retry. The original invalid artifact may not be
overwritten or reinterpreted as passing.

No treatment strength, held-out treatment score, or candidate/lineup score was
read in diagnosing or freezing this repair.
