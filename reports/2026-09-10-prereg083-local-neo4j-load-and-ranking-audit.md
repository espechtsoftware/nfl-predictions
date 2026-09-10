# PREREG-083 local Neo4j load and ranking audit

Date: 2026-09-10

Disposition: PASS as a localhost-only, read-only diagnostic projection. This
is not a production graph deployment and grants no scoring, selection,
promotion, or bankroll authority.

## Frozen source

The loaded release is the create-once PREREG-083 export rooted at:

`gs://nfl-2-506823-lab/results/prereg083/neo4j/fece63a5449985424c8b502fe387b2eebd1ae9a540694edf198fbc3eabf19d56/`

The tracked remote receipt pins:

- score result SHA-256 `fece63a5449985424c8b502fe387b2eebd1ae9a540694edf198fbc3eabf19d56`;
- `nodes.csv`: generation `1789077354637540`, 9,059,545 bytes, SHA-256
  `1213721c2b2a3192e1416153e94200caf2bf8458792221c592645c7e369468c5`;
- `edges.csv`: generation `1789077374391998`, 21,281,873 bytes, SHA-256
  `f514d68c90d6ae905782ec28f7430e1601181d5968119561e708ef9e91b5aa4e`;
- `load.cypher`: generation `1789077322471013`, SHA-256
  `19aed1cfcdee725d5afda4940876f1c122293fb08e51e0a2c582cb409ce85766`;
  and
- `receipt.json`: generation `1789077322562477`, SHA-256
  `0379eaac8e95ac4cdef5c0e3cc743618bd1b22495a5c2afd9a66a77ce4b871bb`.

The runtime copies of both CSVs reproduced their pinned hashes before load.

## Runtime and load

The existing localhost-only `nfl-kg-local-smoke` Neo4j 5.26.30 Community
fixture remains on immutable image digest
`sha256:037cf5756f0135cbfd66b739b6df7c7c4bb100f9ce11602f6f9538e17e02c74d`,
loopback-only ports, 1.5 CPU, and 2 GiB RAM. Authentication is disabled only
for this isolated fixture and must not be copied to a shared service.

Pre-load collision audit compared all 28,165 release node IDs to the existing
4,435-node fixture and found zero overlaps. The supplied node statement loaded
exactly 28,165 nodes. Its label-free relationship lookup was terminated after
8m35s while still running; that single atomic transaction rolled back to zero
relationships. An indexed `Prereg083Entity(id)` release label reduced endpoint
resolution to seconds. The first monolithic indexed attempt resolved all
165,889 rows but correctly rolled back at the 358.4 MiB transaction-memory
ceiling. The same immutable rows then loaded successfully in 5,000-row
transactions.

An identical second relationship pass processed all 165,889 source rows and
left the logical census unchanged. Final release census is exactly 28,165
nodes and 165,889 relationships; the shared local fixture is 32,600 nodes and
174,536 relationships. A full property comparison against both CSVs matched
all 28,165 node payloads and 165,889 relationship payloads, with zero duplicate
relationship triples. The canonical logical release digest is
`067cb2ef72537c3bebf5cd6aeb1f3bb691ea47b28409736cbb42c2c1d1f15c1f`
over 69,511,297 canonical bytes.

Structural checks found all 12,960 rosters have exactly nine player edges,
all 5,760 selected occurrences have exactly one selected-book edge, all 8,640
unselected occurrences have none, and every candidate has its exact arm,
roster, and slate lineage.

## What the graph says about scoring and ordering

Across 36 slates per arm, each arm contains 7,200 candidate occurrences and
2,880 selected K80 occurrences:

| Arm | Pool 200+ | K80 selected 200+ | Pool 220+ | K80 selected 220+ |
|---|---:|---:|---:|---:|
| control | 12 | 7 | 1 | 1 |
| treatment | 12 | 8 | 2 | 0 |

The treatment therefore supplied two realized 220+ candidates and selected
neither. This is selection loss, not a treatment-supply failure.

| K | control mean max | treatment mean max | control oracle regret | treatment oracle regret |
|---:|---:|---:|---:|---:|
| 1 | 116.214 | 122.693 | 68.339 | 63.230 |
| 3 | 140.071 | 150.051 | 44.157 | 35.872 |
| 5 | 144.965 | 153.881 | 39.123 | 32.042 |
| 10 | 154.895 | 159.531 | 29.778 | 26.392 |
| 20 | 166.191 | 168.508 | 18.159 | 17.415 |
| 40 | 172.456 | 174.231 | 12.798 | 11.692 |
| 57 | 174.785 | 177.231 | 10.402 | 8.692 |
| 80 | 178.792 | 180.922 | 6.281 | 5.001 |

Neither arm captured a 230+ week at any prefix. At K80, control captured six
200+ weeks and one 220+ week; treatment captured seven 200+ weeks and zero
220+ weeks. Treatment's early-prefix advantage is real, but the residual
oracle regret remains too large for a claim that ranking is solved.

Mean within-slate Spearman association with realized score was 0.217/0.240 for
served/simulated mean (control/treatment), 0.199/0.208 for q90, and only
0.167/0.167 for q99. Salary and simple team/game-count features were near
zero. A q99-only ranker is therefore not supported as the obvious answer;
PREREG-085's identical-population comparison of incumbent, mean, q90, q99 and
the frozen multimetric rule is the appropriate next test.

## Known/unknown boundary

The graph's explicit knowledge-gap node states that paid-source-named columns
are present, but PREREG-083 did not vary their source or consumer. It cannot
identify Fantasy Points/SIS completeness or their incremental scoring value.
Neo4j now makes that absence queryable; it does not fill the evidence gap.

Next action: use this loaded release for repeatable K-prefix recall/regret and
tail-phenotype queries while the lab implements PREREG-085. Keep immutable
JSON/CSV/GCS artifacts as numerical authority; do not make a mutable graph
query part of the live selector.
