# Local Neo4j Compatibility Smoke

**Date:** 2026-09-01  
**Disposition:** PASS for the lab packet as a local Neo4j compatibility
fixture; this is not a production deployment or a governed graph release

## Runtime

- Docker Engine package: `docker.io 29.1.3-0ubuntu4.1`
- Docker daemon: active and enabled under systemd
- Neo4j: Community `5.26.30`
- Immutable image:
  `neo4j@sha256:037cf5756f0135cbfd66b739b6df7c7c4bb100f9ce11602f6f9538e17e02c74d`
- Primary container: `nfl-kg-local-smoke`
- Persistent data volume: `nfl-kg-local-smoke-data`
- Resource cap: 1.5 CPU, 2 GiB RAM
- Browser: `http://127.0.0.1:7474`
- Bolt: `bolt://127.0.0.1:7687`
- Both published ports are loopback-only.
- Authentication is disabled for this localhost-only disposable compatibility
  fixture. This configuration is forbidden for a shared or production graph.
- Import packet is a runtime copy under
  `/home/erich/.local/share/nfl-kg-local-smoke/import-v1`; the lab repository
  artifacts were not made writable by the container.

## Inputs

The smoke loaded the lab packet at commit `cd873f1` / handoff commit
`af945c2`:

- base `nodes.csv`, `edges.csv`, and `load_v1.cypher`;
- 078 slice `nodes_run_078m520r3-20260901T182923Z.csv`,
  `edges_run_078m520r3-20260901T182923Z.csv`, and its Cypher loader.

Base was loaded before the run slice because the run-to-experiment edge
depends on base node `exp:078`.

## First load

The actual Neo4j loader returned:

- base nodes processed: 171;
- base relationships processed: 19;
- run nodes processed: 6; and
- run relationships processed: 5.

The live graph census was exactly:

- 177 nodes; and
- 24 relationships.

Node census:

| Label | Count |
|---|---:|
| Claim | 12 |
| Experiment | 80 |
| ExperimentRun | 1 |
| Hold | 2 |
| Preregistration | 48 |
| ProposalAttemptAggregate | 4 |
| Question | 13 |
| Read | 16 |
| Slate | 1 |

Relationship census:

| Type | Count |
|---|---:|
| BLOCKED_BY | 4 |
| EVIDENCED_BY | 15 |
| PROPOSED_IN | 5 |

Duplicate checks found zero duplicate/null node IDs and zero repeated
`(start-id, relationship-type, end-id)` triples.

## Idempotent replay

Both loaders were executed a second time against the same database. Loader
output again reported the CSV row counts, while the logical database remained
exactly 177 nodes and 24 relationships. No duplicate IDs or relationships
appeared.

## Zero-state rebuild and persistence

A second Neo4j container with a fresh independent data volume loaded the same
base and run packet from zero. Both databases produced the same complete
graph-record digest:

`4070367bee451b0df0d43f259555f02b8cf972c088f9ee160a98826f90f18f59`

That digest covers 1,082 ordered label, property, and relationship records.
An independent canonical JSON representation of all labels, node properties,
and relationship triples also matched between databases at:

`574ac4722f982690ac718367d8e0536125611a5086a8164ad6f41be90696daf4`

The primary container was then restarted. Its census remained 177/24 and its
graph-record digest remained unchanged, proving persistence through the named
data volume.

The exact disposable rebuild container and its independent data volume were
removed after comparison. They are recoverable by repeating the documented
zero-state load. The validated primary container and volume remain running.

## Query smoke

Initial knowledge queries returned coherent results:

- 13 open questions across beliefs, construction, field, objective,
  selection, and supply;
- all 12 claims have evidence, represented by 15 evidence links;
- `hold:registry-v2` blocks three experiments and `hold:082-binding` blocks
  one;
- the 078 run resolves to `exp:078` with four reconciled ledgers and zero
  violations; and
- four proposal-attempt aggregates resolve to `slate:2021-w01`, all with a
  true reconciliation value.

## What this proves

This proves that the current lab CSV/Cypher packet:

- is accepted by a real pinned Neo4j 5 server with APOC;
- loads with the expected complete endpoint census;
- is logically idempotent under a second load;
- persists through restart;
- rebuilds deterministically from zero; and
- answers the initial epistemics and run-lineage queries.

## What this does not prove

This does not close the production-readiness gaps recorded in
`reports/2026-09-01-lab-neo4j-readiness-production-review.md`:

- loader row counts still do not distinguish created, matched, rejected, and
  final-database counts;
- the lab release manifest remains incomplete and lacks exact source-object
  identities;
- per-run discovery still needs fail-closed hardening;
- the raw loader writes CSV control columns and typed values as string
  properties and supplies no production uniqueness constraints;
- the lab and production observatory schemas still require a governed mapping;
- no candidate-lineup/player/trait/settlement/winner-gap population exists;
  and
- no dedicated authenticated, least-privilege, backed-up production service
  has been provisioned.

## Next action

Use this passing local fixture as the Phase-B integration target. From a fresh
current-main worktree, add the versioned lab-to-production epistemics/lineage
adapter and complete release/source bindings, then repeat this double-load and
zero-state gate through the production transport before any graph pointer or
React route is activated.
