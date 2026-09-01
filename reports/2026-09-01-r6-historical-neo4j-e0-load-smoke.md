# R6 historical Neo4j E0 local load smoke

**Executed:** 2026-09-01T20:53:52Z  
**Evidence class:** descriptive development only  
**Plan SHA-256:** `e852521d97d3cb37d8e46c6336694f003114b72aa9908277ee7783a1fe1b6821`

The accepted E0 historical corpus plan was loaded into the existing localhost-only
`nfl-kg-local-smoke` Neo4j 5.26.30 Community fixture. The immutable image is
`neo4j@sha256:037cf5756f0135cbfd66b739b6df7c7c4bb100f9ce11602f6f9538e17e02c74d`.
No cloud, production service, application route, raw outcome source, winner source,
paid/live source, scoring policy, or deployment was touched.

## Load and idempotence result

The adapter first revalidated all 219 exact local source objects. Both identical
upsert passes accepted all rows:

| Pass | Node rows | Payload-matching nodes | Relationship rows | Payload-matching relationships |
|---:|---:|---:|---:|---:|
| 1 | 4,258 | 4,258 | 8,623 | 8,623 |
| 2 | 4,258 | 4,258 | 8,623 | 8,623 |

The label-scoped graph remained exactly 4,258 nodes and 8,623 relationships after
the second pass. The complete shared local fixture is now 4,435 nodes and 8,647
relationships: the prior 177-node/24-edge epistemics fixture plus this separately
labelled historical slice.

## Node and relationship census

| Node kind | Count |
|---|---:|
| `SourceAuthority` | 3 |
| `HistoricalCorpusSlice` | 1 |
| `Slate` | 54 |
| `LineupCandidate` | 279 |
| `PlayerSlate` | 951 |
| `GenerationDenominator` | 2,538 |
| `FinalFitBook` | 432 |

| Relationship type | Count |
|---|---:|
| `DERIVED_FROM` | 3 |
| `CONTAINS_SLATE` | 54 |
| `HAS_HIGH_SCORER` | 279 |
| `CONTAINS_PLAYER` | 2,511 |
| `HAS_DENOMINATOR` | 2,538 |
| `GENERATED_IN_CELL` | 574 |
| `HAS_FINAL_FIT_BOOK` | 432 |
| `SELECTED_HIGH_SCORER` | 105 |
| `MISSED_HIGH_SCORER` | 2,127 |

## Query acceptance

- 279 high-scoring lineup nodes were returned: 38 selected by at least one
  final-fit strategy and 241 missed by every final-fit strategy.
- 29 of 54 slates contained a 200+ opportunity; 10 had at least one captured
  opportunity.
- Every `LineupCandidate` has exactly nine `CONTAINS_PLAYER` relationships.
- Zero historical nodes carry a winner claim, promotion authority, or policy-feedback
  authority.

This smoke establishes queryability and idempotence for the bounded local slice. It
does not grant official-winner, experiment-promotion, corpus-fill, selector, live-money,
or production-service authority.
