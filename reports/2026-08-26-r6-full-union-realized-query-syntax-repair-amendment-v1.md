# R6 full-union realized-query syntax repair amendment v1

Date: 2026-08-26  
Status: frozen before any successful historical-outcome read  
Replacement run ID: `20260826-foundry-v12-r6-full-union-realized-v2`

## Why this amendment exists

The frozen v1 supply execution
`atlas-minimal-c-s2023-w1-v1-qcvnf` completed unsuccessfully at
`2026-08-26T19:31:46.660152Z`. Its one task exited 1 with no retry. The
create-once read-attempt preceded the fixed BigQuery job, but BigQuery rejected
that job during parsing:

```text
reason: invalidQuery
location: query
message: Syntax error: Expected ")" but got keyword AS at [5:108]
```

The registered SQL placed table aliases after `FOR SYSTEM_TIME AS OF`. The
GoogleSQL grammar is `table_name [as_alias] [FOR SYSTEM_TIME AS OF ...]`; the
alias must precede the temporal clause. This is a transport grammar defect,
not a scientific result or a data-dependent finding.

## Exact v1 failure boundary

- Run ID: `20260826-foundry-v12-r6-full-union-realized-v1`
- Panel root generation/bytes/object SHA-256:
  `1787756181440564` / `89879` /
  `57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467`
- Actual-root smoke generation/bytes/object SHA-256:
  `1787764720711291` / `67127` /
  `b513e7c93b95f3fab50edf76361ff2d5720e41339cc01b7f874153cfef1e50fe`
- Lease generation/bytes/SHA-256:
  `1787767352106912` / `388` /
  `c389ce641c7d0696f9bbfd438622252d2ab54579cf96e5173d97b17aaf705b11`
- Read-attempt generation/bytes/object SHA-256:
  `1787772701143485` / `4804` /
  `69ab97748dbfb43ea80a625e8fc11c45158a0dc6cf72af0304b725cc97afd0c9`
- Read-attempt self-hash:
  `8dcbcbb7c67e962dae47cba3a8aac8dc735c95b73508b2b57db38498b70f6bcd`
- Terminal execution file bytes/SHA-256:
  `5093` /
  `c1afc8b3aeeb0d4b778fbf5776fe053a52bf8770734d906091368895a2b9b4f7`
- Failed fixed job ID:
  `r6_full_union_realized_20260826_foundry_v12_r6_full_union_realized_v1_57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467`
- Failed SQL SHA-256:
  `226e8174b9ab5e046f9f43fae34f48581ca91d2a5630e1e5fdbcdf89010fcc11`
- BigQuery reports `state=DONE`, identical start/end millisecond
  `1787772702293`, empty query statistics and no
  `totalBytesProcessed`. No `query-evidence.json`, `realized-source.json`,
  `outcome-snapshot.json`, supply completion, grade shard, grade root or grade
  completion exists.

Consequently, the fixed query job was submitted but never parsed successfully;
there was no successful historical-outcome read, no outcome row delivered to
the runner, no lineup scoring and no strategy result to inspect. V1 is
terminally invalid and must never be relaunched or reused.

## Licensed mechanical repair

This amendment licenses only the following actions:

1. Move aliases before `FOR SYSTEM_TIME AS OF` in the registered player and
   DST query. Sweep the identical grammar defect from the two sibling LR8
   historical query builders and update their registered SQL hash.
2. Add exact regression assertions for the documented grammar and include the
   shared query sources/tests in the immutable R6 build inventory.
3. Compile the corrected exact SQL with a BigQuery server dry run before any
   new lease or fixed query. The compile gate may construct a BigQuery client
   and inspect schema/estimated bytes, but may not call `result()`, iterate
   rows, acquire a historical lease, create the fixed production job or score
   a lineup.
4. Archive and generation-match abandon only v1 lease generation
   `1787767352106912` after retaining the failed execution, read attempt and
   job error evidence.
5. Build a fresh immutable image from the pushed repair commit and start one
   fresh v2 lineage using the same registered Cloud Run Job resource. V2 must
   use a fresh smoke, lease, execution and deterministic BigQuery job ID.

## Scientific surface remains frozen

The repair does not alter or reselect:

- the 54-slate panel root, its slate membership or source order;
- any lineup, rank-80 book, rank-20/40/80 prefix or fit scope;
- the 2,592 books or 7,776 prefixes;
- the eight frozen strategies, their ordering or budgets;
- `strict-230-coverage-v1`, whose registered threshold remains strictly
  greater than 230 DK points;
- any realized-score conversion, roster summation, grade statistic, report
  interpretation or promotion rule;
- the four outcome snapshot source/test hashes except where a new immutable
  build truthfully binds changed code dependencies; or
- any graph, production, IAM, scheduler or corpus-fill state.

The corrected shared corpus/R6 SQL SHA-256 is
`03b5028dadbe4d92621103e2ccd6dcfe91e8e36fc351cf671f37e309951752cb`.
The corrected LR8 label SQL SHA-256 is
`85ba08f0ea06917ea1687b14cbabd25d0c85f6aa6eb57130fc310a9b00344364`.
No retry, retune, strategy amendment or decision authority is granted to v1.
V2 may proceed only after the failed-attempt closure, exact lease abandonment,
focused tests, immutable build and real BigQuery dry-run compile gate all pass.
