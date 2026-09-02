# Bounded E0 aggregate integration

**Date:** 2026-09-02

**Branch:** `codex/neo4j-v2-integration`

**Status:** implementation complete; activation deliberately pending independent review

## Outcome

The production handoff's narrow integration delta is implemented:

1. one deterministic, create-once runner rebuilds the accepted E0 plan from
   the same 219 immutable source objects and writes the already reviewed
   `corpus-r6-historical-realized-summary/v1` aggregate; and
2. one isolated GET-only endpoint reopens and validates that aggregate on
   every request.

The endpoint is mounted, but it fails closed with HTTP 503 until an operator
explicitly configures the reviewed artifact path. No artifact was generated or
configured during implementation because the accepted handoff requires an
independent review first.

This change does not modify the existing E0 runner, the v1 or v2 graph
contracts/projections, React or static assets, packaging, Neo4j, cloud access,
scoring, lineup generation, selection, active experiments, or production
policy.

## Create-once materializer

`scripts/materialize_corpus_r6_historical_realized_summary_v1.py` accepts only:

- the local directory containing the accepted 219 staged objects;
- the exact tracked accepted-E0 receipt; and
- a new output path.

It derives both root identities from the accepted receipt, uses the existing
E0 source enumerator without changing it, independently rebuilds the graph
plan, and passes the exact receipt bytes, funnel bytes, and plan to the merged
summary core. That core already verifies the pinned source identities, complete
object/row census, plan and manifest hashes, classification partitions,
integer-micro arithmetic, and the self-hashed aggregate. The runner validates
the returned object again, serializes canonical JSON plus one terminal newline,
and opens the destination with exclusive creation. An existing file or symlink
is rejected before the expensive rebuild begins.

The runner has no Neo4j driver, query, network, cloud, scoring, or deployment
surface. Its stdout receipt explicitly records those non-actions.

After independent approval, create the production-readable local artifact
once with:

```bash
PYTHONPATH=src /home/erich/projects/nfl-predictions/.venv/bin/python \
  scripts/materialize_corpus_r6_historical_realized_summary_v1.py \
  --staging-dir /home/erich/projects/nfl-predictions/.scratch-neo4j-intelligence-20260901 \
  --accepted-e0-receipt reports/2026-09-01-r6-historical-neo4j-slice-e0-local-receipt.json \
  --output /home/erich/projects/nfl-predictions/.local-artifacts/e0/historical-realized-summary-v1.json
```

The review/activation check must require the already independently reproduced
internal summary SHA-256:

```text
c5bd768ed77c6d911e294b09e03743db86e1d530b7b0a76e24c213c2614dd856
```

If the destination already exists, do not remove or overwrite it. Review its
bytes and identity, then choose a new explicitly governed path if regeneration
is actually authorized.

## GET-only aggregate endpoint

The application mounts exactly one new route:

```text
GET /api/corpus-research/e0/historical-realized-summary
```

It reads only the path named by:

```text
CORPUS_RESEARCH_E0_HISTORICAL_SUMMARY_PATH
```

The reader rejects an unset path, missing file, symlink, non-regular file,
empty or over-1-MB body, concurrent file change, invalid JSON, noncanonical
bytes, or any aggregate that fails the production summary validator. It does
not cache an unchecked body: the exact artifact is reopened and validated on
every GET. Success returns the bounded aggregate beneath an explicit
read-only, summary-only, descriptive-development envelope. Failure returns a
503 envelope and no partial aggregate. Responses use `Cache-Control: no-store`.

There is no POST/PUT/PATCH/DELETE route, no arbitrary query parameter, no
Neo4j connection, and no lineup, roster, player, book, slate, node, or
relationship enumeration. `FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK` remains a
descriptive set-difference label, not a source selector rejection, causal
first loss, promised point gain, winner claim, or promotion signal.

## Review and activation checklist

1. Review the runner's reuse of the unchanged E0 `_inputs` enumerator and the
   API's second validation at the dependency boundary.
2. Confirm the diff contains no React/static, package-data, v1/v2 projection,
   Neo4j, cloud, scoring, experiment, or policy changes.
3. Run the focused tests and lint checks below from a fresh checkout.
4. Generate the artifact once using the command above; require summary SHA-256
   `c5bd768e...d856` and retain the stdout file SHA-256 as the activation
   receipt.
5. Set `CORPUS_RESEARCH_E0_HISTORICAL_SUMMARY_PATH` explicitly in the intended
   local service environment. Do not add a silent repository-relative default.
6. GET the endpoint and confirm the exact funnel reconciliation: 279 eligible
   200+ lineups, 38 observed in at least one final book, 241 first-observed
   absent, 29 opportunity slates, and 10 converted slates.
7. Keep the React observatory and full candidate-lineage work as separately
   reviewed future projects; neither is required to use this aggregate.

## Validation

The focused implementation/core/E0 regressions pass:

```text
33 passed
```

The checked set is:

```text
tests/test_materialize_corpus_r6_historical_realized_summary_v1.py
tests/test_corpus_research_e0.py
tests/test_corpus_r6_historical_realized_summary_v1.py
tests/test_corpus_r6_historical_neo4j_slice_v1.py
```

Ruff formatting/checks and `git diff --check` are clean for the implementation
files. No service, network, Neo4j, cloud, scoring, or experiment action was
performed by these validations.
