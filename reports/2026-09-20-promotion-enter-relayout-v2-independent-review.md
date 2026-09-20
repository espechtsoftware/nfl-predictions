# Independent review: corrected ENTER re-layout row check

**Date:** 2026-09-20  
**Scope:** workstation commit `8ba10d2`, fixed tool SHA
`d07addc7f5de3f17dcde427266fbd19c3bc50ee257cffb09161b50171aed8a3d`  
**Evidence:** `reports/reviews/evidence/2026-09-20-relayout-enter-row-check-v2.py` and its result JSON

The earlier v2.1 guard compared each contest file with a contiguous slice of the promoted upload. That rejected the
actual keeper/fill layout and the top-per-contest layout. The workstation's v2 replacement computes the expected rows
with the layout rule before comparing them. I independently ran the exact bytes from the shared lab worktree against a
five-row synthetic upload and the production bundle verifier.

## Result

All four cases exited 0, published an `ENTER` symlink, and matched the expected rows exactly:

| case | mapping exercised | result |
|---|---|---|
| `ENTER_LAYOUT` unset | script default sequential: milly rows 1,3; flea rows 2,4,5 | pass |
| explicit `sequential` | keeper cursor plus fill tail | pass |
| explicit `top` | ordinary contests receive the upload prefix independently | pass |
| explicit `top`, flea `block: true` | ordinary milly repeats the prefix; the blocked flea consumes its own cursor block | pass |

The verifier also required both contest files to contain the configured number of rows and nine non-empty lineup cells.
The result JSON records the exact output rows, tool hash, verifier hash, stdout/stderr, and temporary fixture path. The
fixture contains no production lineups, realized outcomes, or provider data; `current_outcomes_read` is false.

The result hash is `ea4d0b3faaca1af2ab67852005d439bcd355a8fc53d1b84b96dbe15df8eb012c`. The full result is committed beside
the reader so the review can be repeated without relying on the temporary directory.

The workstation's additional layout log reports the same four mappings and a 13/13 byte-equivalent Week-2 fixture;
its runner log reports success, corrupt-upload refusal, and unavailable-player STOP, with the prior ENTER bundle retained
on the two failure paths. Those logs are useful corroboration, but the synthetic rerun here is independent of them.

## Disposition

The specific v2.1 row-check blocker is closed for the fixed tool. The corrected guard is appropriate for the current
Week-2 `sequential` policy and for the supported top/block layouts. This review does not authorize a live promotion or
certify the Sunday source, candidate, vetter, or final-player checks; those still require the fresh run's receipts and
the existing runner gates.
