# PREREG-055 production cross-verification

Date: 2026-09-02  
Experiment: 086, D800 × context-matched no-bring-back tail sleeve  
Disposition: **independently reproduced FAIL; retain plain D800 for Week 1**

## Scope and authority

Production waited for the lab's formal first read in Action Note Update 15,
then ran only the frozen, fail-closed reader over the three exact accepted
cohort IDs:

- `086b600r1-20260902T111003Z`
- `086b601r1-20260902T111222Z`
- `086b602r1-20260902T121746Z`

The read used a clean detached worktree at canonical lab `origin/main` commit
`04191771c31813b5c33ee0df7d75fcf5ee76364c`, whose parent is the efficacy
binding commit `22ad2d90139e6e2a0756913083cb8053535e2e43`. The repaired reader
SHA-256 is
`bf35fceed4b89c78f1590c36d7a4b6c952f3f70e787a53afab93d6fc613b802c`.
The immutable experiment source remains
`b2ba460598026fc7110a1470b6eefca0db3c1e17`, with image digest
`sha256:8f874a9d4f4cfcd469c62949ecd9170faf86422dc2207bc64b72bc517ba7fbb1`.

The exact command was:

```bash
PYTHONPATH=src /home/erich/projects/nfl2-prereg055-launch-contract/.venv/bin/python \
  scripts/prereg055_report.py \
  086b600r1-20260902T111003Z \
  086b601r1-20260902T111222Z \
  086b602r1-20260902T121746Z
```

It exited 0 after reaching the final mixture/vacuity checks. The complete
stdout is preserved in
`reports/2026-09-02-prereg055-production-cross-verification-transcript.txt`
(3,184 bytes; SHA-256
`50562de9d8ae7f71f12c24d5baf840a53daafc1674ce74b03891de6a533f049d`).

## Independent result

The production read exactly reproduces the lab's reported decision values:

| Measure | D8_NOBB_TAIL − D8_BASE |
|---|---:|
| Preregistered K80 winner-utility proxy | -0.00107 |
| 95% family interval | [-0.00518, +0.00403] |
| Bank means (600 / 601 / 602) | -0.003124 / +0.001484 / -0.001568 |
| Weekly W / L / T | 28 / 31 / 13 |
| Sign-flip p | 0.6608 |
| Frozen verdict | **FAIL** |
| Raw weekly K80 maximum co-report | -0.578 [-1.561, +1.012] |

The treatment changes the pool and book materially (candidate Jaccard 0.738,
book Jaccard 0.548, and 4.64 players added on average), but that change does
not improve the adopted endpoint. It raises weeks at or above 194 from 14 to
17 while reducing weeks at or above 187 from 29 to 25 and produces no 230+
weekly maximum in either arm. Those threshold counts are descriptive and do
not supersede the frozen proxy verdict.

The fixed-delivered-count reference is also -0.00107. This supports the lab's
interpretation that the D400 sleeve result does not stack with the already
expanded D800 supply. The correct immediate decision is therefore plain
`D800_DEMAX`, not D800 plus the no-bring-back tail sleeve. Prospective 2026
settlement remains the adoption confirmation authority.

## Amendment 2 co-sign

Production **co-signs PREREG-055 Amendment 2 as a validation-only repair**.
The experiment constructs the reported book by passing the selected 80
lineups, their selected arrays, and `book_index=range(80)` into `SlateResult`.
Consequently, `SlateResult.book_rows()` emits `cand` as the within-book
position 0–79. The pre-lock trace's `cand_ix` is instead the original
candidate-pool index. Equating those fields was incorrect by construction.

The amendment correctly changes that local check to `cand == rank - 1` while
retaining the actual cross-artifact mapping through exact `roster_sha256` and
`tag`, the exact-key settlement join, and one-to-one K80 rank/roster censuses.
The read had failed closed before printing an endpoint, and the amendment does
not change an arm, score, result object, endpoint, decision rule, or
interpretation.

Validation supporting the co-sign:

- the PREREG-053 and PREREG-055 reader suites passed 22/22 at the canonical
  amendment commit;
- a separate synthetic probe selected a non-sequential original pool row into
  book rank 1, proved that roster/tag identity reconciles while book `cand`
  remains zero, and proved a non-position `cand` still fails closed;
- the full 086 reader reached exit 0 and all final natural-family engagement
  checks.

A permanent version of the non-sequential-pool regression would be useful but
is non-blocking because the experiment source and the independent probe already
establish the repaired semantics.

## Queue consequence

Both shared Cloud Run lanes are idle. No additional lab experiment is yet
launch-authorized in the current action note. The lab identifies KG-4
calibration and D800_WEMAX as its next builds; production should review and run
their frozen launch contracts when posted, without inventing an unfrozen arm.
The active production priority remains complete pre-lock lineage and
retrieval/conversion analysis, with scoring untouched.
