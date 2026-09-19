# Isolated TabPFN refresh and complete-pipeline rehearsal

Frozen before refreshed predictions or books are read. Purpose: determine whether the repaired feature chain can execute through the actual marginal-cache consumer, and measure its influence. No current lineup outcomes, bank 990/991 reads, live-table writes or adoption decision.

## Inputs and isolation

Use existing `tabpfn-gen` image `sha256:7eeff44e7c225fed62682b3649dfa86d77f86227e3e9858c967d132deff2a10a`. The image's actual `/app/gen.py` and `/app/features.txt` were extracted from content-verified OCI layers and match local production bytes exactly. Generator SHA is `0d8a355b270e2ef5f6097bef51ca5d3ff1715e20951b4c2762b5594a5b9c9a81`; feature SHA is `52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83`.

Control and repair sources are `nfl_features_control` and `nfl_features_salaryfix`. Exact row counts, modification times and etags are pinned in the [adapter](reviews/evidence/2026-09-19-tabpfn-scratch-refresh.py); refuse drift before reads and before/after the sole output write. All queries are read-only and limited to that arm's training/inference tables. The sole permitted write is create-only to that arm's absent `tabpfn_projections` table. No fallback to the live namespace. Preserve any failed attempt before amendment/retry.

Use per-execution overrides of the existing job only, after acquiring its launcher-registry lane. Workstation grants exclusive ownership in lab `d7f09ec`; release before Saturday 14:45 UTC refresh, with base job configuration verified unchanged. First run a mechanics execution that verifies source, destination absence and metadata but does no inference or writes. Then run the two arms serially, 1,200-second task timeout each, no automatic duplicate launch on ambiguous provider response. Expected cost is below $5 and total runtime below one hour based on the last successful 13-minute full refresh. [Cloud Run execution overrides](https://docs.cloud.google.com/run/docs/execute/jobs) apply to the execution rather than updating the base job.

## Two explicit differences from the deployed generator

The unchanged full-refresh algorithm uses four estimators, seed 7, maximum context 28,000 and its original six-season RNG progression. Common sorted training (season/week/GSIS) and inference (GSIS) order makes the two-arm context sampling reproducible; the deployed SELECTs do not specify an order. This controlled comparison is not a claim to reproduce the old live cache exactly.

**Strict target-week filtering occurs in SQL before downloading training labels.** Preflight job `d05ce003-2f4d-4f1a-94c2-9409873278b5` found repair training has 863 labeled rows in 2026 Week 1 and 43 in Week 2; control has no 2026 rows. Only season/week strictly before 2026/2 may enter this Week 2 rehearsal. The deployed upcoming path currently selects all nonnull labels without this filter. Its all-prior assumption must be corrected or enforced before using the repaired training table live. No values from the 43 Week 2 labels were opened; the preflight read only support counts.

Both arms use the same strict filter, so this is the salary repair effect under a common, valid pre-week context rule. It includes newly available prior-week context as well as changed inference features. It does not isolate usage alone; the earlier four-case hsim study did that separately.

## Prespecified checks and reporting

Require 928 unique Week 2 cache keys, complete finite means/13 quantiles, nondecreasing quantiles, no duplicate keys, source stability and identical image/source/feature contracts. Report row counts, historical keyed output parity and Week 2 mean/quantile absolute shifts and changed-row counts. Exact historical parity is a diagnostic of the co-run inputs and reproducibility, not a reason to change a threshold after seeing results. If it fails, investigate before attributing upcoming differences to the repair.

After cache creation, freeze the separate bounded full-CLI integration protocol before generating comparative books: route the feature/cache/projection reads to each scratch arm while preserving current salary/status/roster/game eligibility and source receipt gates. Use one shared snapshot of current non-arm inputs; no entries or files sent to DraftKings. Record changed frame columns, score-bank means/tails/dependence, candidate membership, selected book/order and all actual contest-block metrics where book size permits. Simulated differences remain conditional model evidence, not a real-world efficacy claim.

The adapter's [ten preflight checks](reviews/evidence/2026-09-19-tabpfn-scratch-refresh-check.json) cover actual source identity and both real filtered SQL dry-runs plus refusal of live reads/writes, scratch overwrite, DML and unfiltered training-label reads before provider access.
