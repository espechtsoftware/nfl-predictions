# Score-free source-population contract repair

Date: 2026-08-15 CDT  
Affected future executions: CBWU-OI selector stability and exact-N  
Outcome values read: none

## Finding

The shared `SOURCE_SQL` in `scripts/run_cbwu_seed_order_audit.py` selected no
score, rank, ownership, payout or selection field, but it filtered candidate
rows with `AND labels_complete`. Completeness is outcome-derived metadata. It
is unnecessary for runners that reconstruct pre-lock candidate pools and
should not define a score-free source population.

## Read-only parity proof

Before changing the query, a BigQuery aggregate counted total versus complete
rows by panel and by `(panel, season, week)`. It read only candidate counts and
the completeness boolean.

| Panel | Total rows | Complete rows | Incomplete rows | Slate cells with a count difference |
|---|---:|---:|---:|---:|
| `20260813-sis-asoe-treatment-r0-v1` | 13,706 | 13,706 | 0 | 0 |
| `20260813-sis-asoe-treatment-r1-v1` | 13,696 | 13,696 | 0 | 0 |
| `20260813-sis-asoe-treatment-r2-v1` | 13,690 | 13,690 | 0 | 0 |
| `20260813-sis-asoe-treatment-r3-v1` | 13,703 | 13,703 | 0 | 0 |
| `20260813-sis-asoe-treatment-r4-v1` | 13,698 | 13,698 | 0 | 0 |
| **Total** | **68,493** | **68,493** | **0** | **0** |

Each panel has exactly 54 slate cells. Thus removing the predicate is an exact
row-set identity change: it alters no candidate, slate, panel, artifact URI or
artifact digest.

## Repair

- Removed `AND labels_complete` from the shared source query.
- Added `labels_complete` to the forbidden score-free query tokens so it
  cannot silently return.
- Moved selector stability onto the shared immutable-artifact preflight used
  by exact-N: one URI/digest per panel/slate, exact five-by-54 grid and source
  row counts.
- Strengthened selector and exact-N finishers to bind terminal execution-owned
  image, command, environment, resources, retries, timeout and service
  account, persist hashed execution JSON, and verify unique source grids.
- The selector finisher also downloads, hashes, decompresses and validates the
  create-only candidate-frequency artifact rather than trusting its
  self-reported receipt.

## Image consequence

The previously validated selector digest
`sha256:25e2bded0aebff43aa0205832417d069d48a2dad73ebb9c2341566953a59cb75`
and exact-N digest
`sha256:7185894cc4f09afb8626b0d8d027fe80fcfb1926392e64710c86cc15c73460ae`
contain the old source predicate. Their earlier test receipts remain valid for
the code they contain, but neither image may launch these future score-free
jobs. Build and fully validate one new exact clean-archive image from the
repaired commit, then use only its immutable digest and full code SHA.

No frozen protocol threshold, world sample, candidate identity, selector,
cardinality treatment or scientific gate changed.

