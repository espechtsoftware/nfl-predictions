# Mechanical repair: ATLAS MVP runner image packaging

**Frozen:** 2026-08-16 02:58 CDT, after all three original executions failed
at container startup and before any source query, candidate construction or
MVP effect output existed.

## Observed mechanical failure

Clean-archive build `a7ff5515-7ff8-454a-adbd-4514528e40d7` passed the complete
1,591-test suite and built immutable image
`sha256:00ce36b7debd344a7fd264df6d00b9a37184abcc9e24285a658968289b38f251`
from code `6be659bbd4dd6436fd89291af230cadb06dc1546`. The Dockerfile uses an
explicit script allowlist and omitted
`scripts/run_atlas_matched_diversity_mvp.py`.

The three create-only executions consequently failed with exit code 2 and the
same message before Python could import the runner:

`/usr/local/bin/python: can't open file '/app/scripts/run_atlas_matched_diversity_mvp.py': [Errno 2] No such file or directory`

- `atlas-matched-diversity-2023-v1-zsfl4`
- `atlas-matched-diversity-2024-v1-gd46z`
- `atlas-matched-diversity-2025-v1-8bt6t`

No season output object or aggregate report was created. These executions are
terminally invalid mechanical attempts and carry no effect disposition.

## Permitted repair only

1. Add exactly the frozen MVP season runner to the Dockerfile's script
   allowlist.
2. Add a post-build container smoke that runs
   `python scripts/run_atlas_matched_diversity_mvp.py --help` in the built
   image, plus a focused source test for that packaging contract.
3. Bind this repair document by SHA-256 in the season runner.
4. Change only create-only destination identities to
   `20260816-atlas-matched-diversity-mvp-v1-repair1` and job names ending in
   `-v1-repair1`.
5. Rerun the complete clean-archive validation and use only its new immutable
   digest and exact source commit.

The original ATLAS protocol, pair-reach amendment, source panels, repaired
R3/2025 Week 1 receipts, player worlds, native candidates, 8x5 enumeration,
interaction pricing, candidate budgets, CBWU-OI admission, exact-80 selector,
tail grid and all disposition conditions remain byte-for-byte and logically
unchanged. A change outside this list invalidates repair1.

## Relaunch requirements

- All three original executions must remain preserved in the evidence index.
- The new output prefix and all three season objects must be absent before
  launch.
- The image smoke and complete suite must pass.
- The new launcher must record the repair-document hash, exact image digest,
  source commit and new execution identities.
- Only the strict three-season finisher may interpret repair1 after all three
  executions are terminal successful.
