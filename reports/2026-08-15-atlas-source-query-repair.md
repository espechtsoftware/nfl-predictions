# ATLAS source-query operational repair

Date frozen: 2026-08-15  
Failed execution: `atlas-world-ranking-scorefree-v1-8p92l`

The first ATLAS Cloud Run execution failed before loading any source rows or
running any diagnostic. BigQuery rejected the source receipt query with
`Aggregations of aggregations are not allowed at [10:23]`.

The query selected `ANY_VALUE(score_artifact_uri) AS score_artifact_uri` and
then referenced the same unqualified name inside `COUNT(DISTINCT
score_artifact_uri)` in `HAVING`. BigQuery resolved that reference to the
aggregate select alias rather than the underlying table field.

Repair only the SQL name binding:

- alias the source table as `source`;
- qualify both `ANY_VALUE` inputs; and
- qualify both `COUNT(DISTINCT ...)` inputs in `HAVING`.

No source population, field, filter, ordering, artifact, world, diagnostic,
gate, threshold or output schema changes. The failed run produced no GCS
result and queried no outcome field. The retry must use a separately tracked
`repair1` receipt directory, exact validated image/code, the same create-only
GCS target and the unchanged strict finisher.
